# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import datetime
import pytz
from pytz import timezone, UTC
import json, simplejson
from lxml import etree
import math
from odoo.tools import float_compare, format_datetime, format_time


class DestinationMemberActivity(models.Model):
    _name = "destination.membership.member.activity"
    _description = "Member Access Token"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "access_date"

    #input fields
    active = fields.Boolean(string="Active", tracking=True, default=True)
    name = fields.Text(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    dest_id = fields.Many2one('destination.destination', string='Entity', tracking=True, index=True, copy=True)
    member_id = fields.Many2one('destination.membership.member', tracking=True, string="Member", ondelete='restrict', store=True, copy=True, required=True)
    partner_id = fields.Many2one('res.partner', string="Member Partner", related='member_id.partner_id')
    pricerule_id = fields.Many2one('destination.price', tracking=True, string="Price Rule")
    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict', domain="[('dest_ok','=',True),('dest_product_group','=','access'),('dest_id','=',dest_id)]", tracking=True, store=True, copy=True)
    access_date = fields.Datetime(string="Token Start", tracking=True)

    expiry_date = fields.Datetime(string="Token Expiry", tracking=True)   
    
    processin_date = fields.Datetime(string="Process-In Date", tracking=True)
    checkin_date = fields.Datetime(string="Check-In Date", tracking=True)
    checkout_date = fields.Datetime(string="Check-Out Date", tracking=True)
    close_date = fields.Datetime(string="Close Date", tracking=True)
    
    registration_user_id = fields.Many2one('res.users', string='Registration User', index=True, tracking=True, default=lambda self: self.env.user)
    processin_user_id = fields.Many2one('res.users', string='Process-In User', index=True, tracking=True)
    checkin_user_id = fields.Many2one('res.users', string='Check-In User', index=True, tracking=True)
    checkout_user_id = fields.Many2one('res.users', string='Check-Out User', index=True, tracking=True)
    
    
    note = fields.Char(string="Note")
    unit_price = fields.Float(string="Token Price", digits='Product Price', tracking=True)
    access_exceptions = fields.Text(string="Exceptions")
    access_code = fields.Many2one('destination.access.code', ondelete='set null', string='Token Code', tracking=True)  
    
    access_payment_method_id = fields.Many2one('destination.payment.method',string='Payment Method')  
    
    #related fields
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    membership_id = fields.Many2one('destination.membership', string='Rental', ondelete='restrict', related='member_id.membership_id')
    is_forced_pricerule = fields.Boolean("Is Forced Price Rule", related='pricerule_id.is_forced')
    access_sales_journal_id = fields.Many2one('account.journal', string="Sales Journal", store=True, related='dest_id.access_sales_journal_id')    
    

    is_late = fields.Char(compute='compute_is_late', string="Token Status")
    
    access_date_date = fields.Date(string="Token Start Date", compute="compute_dates")
    access_date_month = fields.Integer(string="Token Start Month", compute="compute_dates")
    access_date_weekday = fields.Integer(string="Token Start Weekday", compute="compute_dates")
    access_date_time = fields.Float(string="Token Start Time", compute="compute_dates")
    
    is_manager = fields.Boolean(string="Is Manager", compute='_is_manager')
    
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id', depends=['product_id.currency_id'], store=True, string='Currency', readonly=True)
    
    invoice_count = fields.Integer(string='Invoice Count', compute='compute_invoice_count', readonly=True)
    invoice_ids = fields.Many2many("account.move", string='Invoices', copy=False, tracking=True)
    
     
    
    
    @api.depends('access_date')
    def compute_dates(self):
        for record in self:
                record.access_date_date = (record.access_date + relativedelta(hours=3)).date()
                record.access_date_month = (record.access_date + relativedelta(hours=3)).month
                record.access_date_weekday = (record.access_date + relativedelta(hours=3)).weekday()
                record.access_date_time = float((record.access_date + relativedelta(hours=3)).time().strftime('%H')) + (float((record.access_date + relativedelta(hours=3)).time().strftime('%M'))/60*100/100)
            
    @api.depends('invoice_ids')
    def compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(record.invoice_ids)
    
    def action_view_invoice(self):
        invoices = self.mapped('invoice_ids')
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
    
    total_invoiced = fields.Monetary(compute='_invoice_total', string="Total Invoiced", readonly=True)
    
    def _invoice_total(self):
        for record in self:
            invoices = record.invoice_ids.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
            record.total_invoiced = sum(line.amount_total_signed for line in invoices.filtered(lambda r: r.state =='posted'))

    total_due = fields.Monetary(compute='_due_total', string="Total Due", readonly=True)
    
    def _due_total(self):
        for record in self:
            invoices = record.invoice_ids.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
            record.total_due = sum(line.amount_residual_signed for line in invoices.filtered(lambda r: r.state =='posted'))
        
        
        
        
        
     
    @api.depends('expiry_date','checkout_date')
    def compute_is_late(self): 
        for record in self:
            now = record.checkout_date or fields.Datetime.now()
            if record.expiry_date and now:
                if now > record.expiry_date:
                    record.is_late = 'Late'
                    
                else:
                    record.is_late = False
                   
            else:
                record.is_late = False
                
        
        
        
    
    @api.onchange('dest_id')
    @api.depends('dest_id')
    def _is_manager(self):
        for record in self:
            record.is_manager = (True if record.env.user.id in record.dest_id.manager_ids.user_id.ids else False)
            

    def name_get(self):
        res = []
        for record in self:
           
            name = record.name
            res.append((record.id, name))
        return res
        return super(DestinationMemberActivity, self).name_get()
    
    
    
                
    