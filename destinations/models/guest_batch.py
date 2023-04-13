# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError, Warning
import datetime
import pytz
from pytz import timezone, UTC
import json, simplejson
from lxml import etree
import math
from odoo.tools import float_compare, format_datetime, format_time


class DestinationGuestBatch(models.Model):
    _name = "destination.guest.batch"
    _description = "Guest Batch"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "access_date"

    active = fields.Boolean(string="Active", tracking=True, default=True)
    name = fields.Text(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))

    dest_id = fields.Many2one('destination.destination', string='Entity', tracking=True, index=True, copy=True, default=lambda self: self._get_default_dest_id())
    def _get_default_dest_id(self):
        conf = self.env['destination.destination'].search(['|',('user_ids.user_id','=',self.env.user.id),('manager_ids.user_id','=',self.env.user.id)], limit=1)
        return conf.id
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    lock_dest_id = fields.Boolean(store=False, copy=False, default=False)
    
    active_membership_ids = fields.Many2many('destination.membership', string="Active Memberships", compute='get_active_memberships')

    member_id = fields.Many2one('destination.membership.member', domain="[('dest_id','=', dest_id),('membership_id','in',active_membership_ids),('membership_type','in',['super','main'])]", tracking=True, string="Member", ondelete='restrict', store=True, copy=True, required=True)
    membership_id = fields.Many2one('destination.membership', string='Rental', ondelete='restrict', related='member_id.membership_id')
    
    access_products_ids = fields.Many2many('product.access.cap',string="Access Products", compute="_get_access_products")
    
    @api.depends('guest_ids','member_id')
    @api.onchange('guest_ids','member_id')
    def _get_access_products(self):
        for record in self:
            if record.membership_id.dest_product_access_rule == 'standard':
                accessprods = record.membership_id.product_id.access_products_ids
            else:
                accessprods = record.membership_id.dest_product_access_cap.filtered(lambda r: r.state == 'active')
                
            accessprods = record.member_id.membership_id.product_id.access_products_ids
            record.access_products_ids = accessprods

            
    guest_batch_products_ids = fields.Many2many('destination.guest.access.cap',string="Access Products", compute="_get_guest_caps")
    
    @api.depends('guest_ids','member_id')
    @api.onchange('guest_ids','member_id')
    def _get_guest_caps(self):
        for record in self:
            
            record.write({'guest_batch_products_ids': [(5, 0, 0)]})
            
            if record.membership_id.dest_product_access_rule == 'standard':
                accessprods = record.membership_id.product_id.access_products_ids
            else:
                accessprods = record.membership_id.dest_product_access_cap.filtered(lambda r: r.state == 'active')
                
            
            for cap in accessprods:
                
                lines_dict = {
                    'guest_batch_id' : record.id,
                    'cap' : cap.cap,
                    'period' : cap.period,
                    'free_guest': cap.free_guest,
                    'product_ids': cap.product_ids,
                    
                                }
                record.write({'guest_batch_products_ids': [(0, 0, lines_dict)]})
                
                
            
            
                
    
    access_date = fields.Datetime(string="Token Start", tracking=True, required=True, copy=True, default=lambda self: fields.Datetime.now(self.env.user.tz) + relativedelta(minutes=1))
    access_date_date = fields.Date(string="Token Start Date")
    access_date_month = fields.Integer(string="Token Start Month")
    access_date_weekday = fields.Integer(string="Token Start Weekday")
    access_date_time = fields.Float(string="Token Start Time")
    
    expiry_date = fields.Datetime(string="Token Expiry", tracking=True)    

    guestquota = fields.Integer(string="Guest Quota", related='member_id.membership_id.actual_dest_daily_guest_count')
    usedguestquota = fields.Integer(string="Used Guest Quota", compute='calcstats')
    maleguestquota = fields.Integer(string="Male Guest Quota", related='member_id.membership_id.actual_dest_daily_guest_male_count')
    usedmaleguestquota = fields.Integer(string="Used Male Guest Quota", compute='calcstats')
    femaleguestquota = fields.Integer(string="Female Guest Quota", related='member_id.membership_id.actual_dest_daily_guest_female_count')
    usedfemaleguestquota = fields.Integer(string="Used Female Guest Quota", compute='calcstats')
    guestquotafree = fields.Integer(string="Free Quota", related='member_id.membership_id.actual_dest_month_free_guest_count')
    usedguestquotafree = fields.Integer(string="Used Free Quota", compute='calcstats')
    malesingleguestquota = fields.Integer(string="Single Male Guest Quota", related='member_id.membership_id.product_id.dest_daily_guest_male_single_count')
    usedmalesingleguestquota = fields.Integer(string="Single Used Male Guest Quota", compute='calcstats')
    
    
    
    note = fields.Char(string="Note")

    is_manager = fields.Boolean(string="Is Manager", compute='_is_manager')
    
    
    
    guest_ids = fields.One2many('destination.guest', 'guest_batch_id', string = 'Guests')
    
    notes = fields.Text("Notes")
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_date = None
            memberid = vals.get('member_id') or self.env.context.get('default_member_id')
            memberrec = self.env['destination.membership.member'].search([('id','=',memberid)])
            if 'access_date' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['access_date']))
            vals['name'] = memberrec.membership_id.dest_id.code + '/' + memberrec.membership_id.product_id.dest_product_code + (('/' + memberrec.membership_id.membership_code) if memberrec.membership_id.membership_code else '') + '/' + (self.env['ir.sequence'].next_by_code('destination.guest', sequence_date=seq_date) or _('New'))
        result = super(DestinationGuestBatch, self).create(vals)
        #raise UserError(str(vals))
        return result   
    
    
    def unlink(self):
        for record in self.guest_ids:
            if record.state not in ['new','pending','cancel','blacklist','expired']:
                raise UserError(_("Delete is not allowed.  Please archive if necessary."))
        return super(DestinationGuestBatch, self).unlink()
    

    
    @api.onchange('access_date')
    def fix_date(self):
        if not self.access_date or self.access_date == False:
            self.access_date = fields.Datetime.now(self.env.user.tz) + relativedelta(minutes=1)
            self.access_date_date = (self.access_date + relativedelta(hours=3)).date()
            self.access_date_month = (self.access_date + relativedelta(hours=3)).month
            self.access_date_weekday = (self.access_date + relativedelta(hours=3)).weekday()
            self.access_date_time = float((self.access_date + relativedelta(hours=3)).time().strftime('%H')) + (float((self.access_date + relativedelta(hours=3)).time().strftime('%M'))/60*100/100)
        
    @api.depends('dest_id')
    @api.onchange('dest_id')
    def get_active_memberships(self):
        for record in self:
            record.active_membership_ids = record.dest_id.membership_ids.filtered(lambda r: r.state in ['active','hold'])
      
    
    @api.onchange('dest_id')
    @api.depends('dest_id')
    def _is_manager(self):
        for record in self:
            record.is_manager = (True if record.env.user.id in record.dest_id.manager_ids.user_id.ids else False)
            

    def name_get(self):
        res = []
        for record in self:
           
            name = record.member_id.name + ' (' + record.name + ')'
            res.append((record.id, name))
        return res
        return super(DestinationGuestBatch, self).name_get()
    
    
    
    @api.onchange('access_date')
    @api.depends('access_date')
    def compute_dates(self):
        for record in self:
            if record.access_date:
                if record.access_date < datetime.datetime.now():
                    raise UserError(_("Access Date/Time cannot be in the past."))
                    
                record.access_date_date = (record.access_date + relativedelta(hours=3)).date()
                record.access_date_month = (record.access_date + relativedelta(hours=3)).month
                record.access_date_weekday = (record.access_date + relativedelta(hours=3)).weekday()
                record.access_date_time = float((record.access_date + relativedelta(hours=3)).time().strftime('%H')) + (float((record.access_date + relativedelta(hours=3)).time().strftime('%M'))/60*100/100)
            else:
                record.access_date_date = False
                record.access_date_month = False
                record.access_date_weekday = False
                record.access_date_time = False

    

    @api.onchange('dest_id')
    def change2(self):
        for record in self:
            record.member_id = False
            
    
    
            
    
    