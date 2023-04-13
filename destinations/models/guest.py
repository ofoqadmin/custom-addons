# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError, Warning
import datetime
import pytz
from pytz import timezone, UTC
import json
from lxml import etree
import math
from odoo.tools import float_compare, format_datetime, format_time


class DestinationGuest(models.Model):
    _name = "destination.guest"
    _description = "Guest Access Token"
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
    partner_id = fields.Many2one('res.partner', string="Member Partner", related='member_id.partner_id')
    membership_id = fields.Many2one('destination.membership', string='Rental', ondelete='restrict', related='member_id.membership_id')
    access_products_ids = fields.Many2many('product.product',string="Access Products", compute="_get_access_products", store=False)
    
    @api.onchange('member_id', 'guest_id')
    @api.depends('member_id', 'guest_id')
    def _get_access_products(self):
        for record in self:
            if record.member_id and record.guest_id:
                if record.membership_id.dest_product_access_rule == 'standard':
                    accessprods = record.membership_id.product_id.access_products_ids.product_ids.product_variant_id.filtered(lambda r: r.access_product_guest == True)
                else:
                    accessprods = record.membership_id.dest_product_access_cap.filtered(lambda r: r.state == 'active').product_ids.product_variant_id.filtered(lambda r: r.access_product_guest == True)
                record.access_products_ids = accessprods
            else:
                accessprods = []
                record.access_products_ids = accessprods
            
                                           
    
    pricerule_id = fields.Many2one('destination.price', tracking=True, string="Price Rule", domain="[('product_id','=',product_id),('validity_datetime_start','<=',access_date),('validity_datetime_end','>=',access_date)]")
    is_forced_pricerule = fields.Boolean("Is Forced Price Rule", related='pricerule_id.is_forced')
    
    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict', domain="[('id','in',access_products_ids),('access_product_guest','=',True),'|','|',('dest_guest_gender_male','=',is_male),('dest_guest_gender_female','=',is_female),'&',('dest_guest_gender_male','=',False),('dest_guest_gender_female','=',False)]", tracking=True, store=True, copy=True, required=True)
    token_type = fields.Selection([('guest', 'Guest Pay'),('free', 'Free'),('member', 'Member Pay')], string="Token Type", copy=True, tracking=True, required=True, default='guest')
            
                       
    access_date = fields.Datetime(string="Token Start", tracking=True, required=True, copy=True, default=lambda self: fields.Datetime.now(self.env.user.tz) + relativedelta(minutes=1))
    access_date_date = fields.Date(string="Token Start Date")
    access_date_month = fields.Integer(string="Token Start Month")
    access_date_weekday = fields.Integer(string="Token Start Weekday")
    access_date_time = fields.Float(string="Token Start Time")
    
    expiry_date = fields.Datetime(string="Token Expiry", tracking=True)    

    guestquota = fields.Integer(string="Guest Quota", related='member_id.membership_id.actual_dest_daily_guest_count')
    usedguestquota = fields.Integer(string="Used Guest Quota")
    maleguestquota = fields.Integer(string="Male Guest Quota", related='member_id.membership_id.actual_dest_daily_guest_male_count')
    usedmaleguestquota = fields.Integer(string="Used Male Guest Quota")
    femaleguestquota = fields.Integer(string="Female Guest Quota", related='member_id.membership_id.actual_dest_daily_guest_female_count')
    usedfemaleguestquota = fields.Integer(string="Used Female Guest Quota")
    guestquotafree = fields.Integer(string="Free Quota", related='member_id.membership_id.actual_dest_month_free_guest_count')
    usedguestquotafree = fields.Integer(string="Used Free Quota")
    malesingleguestquota = fields.Integer(string="Single Male Guest Quota", related='member_id.membership_id.product_id.dest_daily_guest_male_single_count')
    usedmalesingleguestquota = fields.Integer(string="Single Used Male Guest Quota")
    
    guest_id = fields.Many2one('res.partner', tracking=True, string='Guest', ondelete='restrict', store=True, copy=False, required=True, domain="[('is_company','=',False)]")
    guest_name = fields.Char('Guest Name', related='guest_id.name')
    guest_phone = fields.Char('Guest Phone', related='guest_id.phone')
    guest_mobile = fields.Char('Guest Mobile', related='guest_id.mobile')
    guest_id_number = fields.Char('Guest ID Number', related='guest_id.id_number')
    guest_gender = fields.Selection([('male', 'Male'), ('female','Female')], string="Gender", related="guest_id.partnergender")
    #is_single_male = fields.Boolean('Is Single Male', related='product_id.dest_guest_single_male', store=True)
    is_male = fields.Boolean('Is Male', compute='getgender')
    is_female = fields.Boolean('Is Female', compute='getgender')
    
    
    processin_date = fields.Datetime(string="Process-In Date", tracking=True)
    checkin_date = fields.Datetime(string="Check-In Date", tracking=True)
    checkout_date = fields.Datetime(string="Check-Out Date", tracking=True)
    close_date = fields.Datetime(string="Close Date", tracking=True)
    
    registration_user_id = fields.Many2one('res.users', string='Registration User', index=True, tracking=True, default=lambda self: self.env.user)
    processin_user_id = fields.Many2one('res.users', string='Process-In User', index=True, tracking=True)
    checkin_user_id = fields.Many2one('res.users', string='Check-In User', index=True, tracking=True)
    checkout_user_id = fields.Many2one('res.users', string='Check-Out User', index=True, tracking=True)
    
    
    access_partner_default_category_ids = fields.Many2many('res.partner.category', 'destination_access_default_ids',string='Access Partner Default Tags', related='dest_id.access_partner_default_category_ids')
    access_default_payment_method_id = fields.Many2one('destination.payment.method',string='Default Access Payment Method', related='dest_id.access_default_payment_method_id')

    
    note = fields.Char(string="Note", tracking=True)
    
    unit_price = fields.Float(string="Token Price", digits='Product Price', tracking=True)

    access_exceptions = fields.Text(string="Exceptions")
    
    access_code = fields.Many2one('destination.access.code', ondelete='set null', string='Token Code', tracking=True)  
    
    is_expired = fields.Boolean(compute='_compute_is_expired', string="Is expired")
    is_late = fields.Boolean(string="Late")
    is_today = fields.Boolean(compute='_compute_is_today', string="Today")
    
    access_sales_journal_id = fields.Many2one('account.journal', string="Sales Journal", store=True, domain="[('company_id', '=', company_id), ('type', '=', 'sale')]")
    access_payment_method_id = fields.Many2one('destination.payment.method',string='Payment Method')    

    
    state = fields.Selection([
    ('new', 'Registered'),
    ('pending', 'Pending'),
    ('blacklist', 'Blacklist'),
    ('inprocess', 'In-Process'),
    ('checked-in', 'Checked-in'),
    ('checked-out', 'Checked-Out'),
    ('late', 'Late'),
    ('expired', 'Expired'),
    ('done', 'Done'),
    ('cancel','Cancelled'),
    ], string='Status', readonly=True, copy=False, tracking=True, default='new')
    
    is_manager = fields.Boolean(string="Is Manager", compute='_is_manager')
    
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id', depends=['product_id.currency_id'], store=True, string='Currency', readonly=True)
    
    invoice_count = fields.Integer(string='Invoice Count', compute='compute_invoice_count', readonly=True)
    invoice_ids = fields.Many2many("account.move", string='Invoices', copy=False, tracking=True)
    
    #guest_batch_id = fields.Many2one('destination.guest.batch', "Guest Batch", ondelete='cascade')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_date = None
            memberid = vals.get('member_id') or self.env.context.get('default_member_id')
            memberrec = self.env['destination.membership.member'].search([('id','=',memberid)])
            if 'access_date' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['access_date']))
            vals['name'] = memberrec.membership_id.dest_id.code + '/' + memberrec.membership_id.product_id.dest_product_code + (('/' + memberrec.membership_id.membership_code) if memberrec.membership_id.membership_code else '') + '/' + (self.env['ir.sequence'].next_by_code('destination.guest', sequence_date=seq_date) or _('New'))
        result = super(DestinationGuest, self).create(vals)
        return result   
    
    
    
    def unlink(self):
        for record in self:
            if record.state not in ['new','pending','cancel','blacklist','expired']:
                raise UserError(_("Delete is not allowed.  Please archive if necessary."))
        return super(DestinationGuest, self).unlink()

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
        action['context'] = {'create':0,'edit':0}
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
           
            name = record.guest_id.name + ' (' + record.name + ')'
            res.append((record.id, name))
        return res
        return super(DestinationGuest, self).name_get()
    
    @api.onchange('guest_id','guest_gender')
    @api.depends('guest_id','guest_gender')
    def getgender(self):
        for record in self:
            if record.guest_gender == 'male':
                record.is_male = True
            else:
                record.is_male = False

            if record.guest_gender == 'female':
                record.is_female = True
            else:
                record.is_female = False
    
    @api.onchange('guest_id','guest_gender')
    def get_applicable_product_list(self):
        self.product_id = False        
    
    @api.onchange('product_id','access_date','guest_id')
    @api.depends('product_id','access_date','guest_id')
    def get_applicable_pricerule_list(self):
        self.pricerule_id = False
        tranch = self.env['destination.price'].search([('id','!=',False)]).filtered(lambda r: r.product_id == self.product_id and r.validity_datetime_start <= self.access_date and r.validity_datetime_end >= self.access_date)
        tranch = tranch - tranch.filtered(lambda r: r.customer_apply_on == 'active' if self.guest_id.has_active_membership == False else None)
        tranch = tranch - tranch.filtered(lambda r: r.customer_apply_on == 'select' and self.guest_id not in r.partner_ids)
        getforcedrule = tranch.filtered(lambda r: r.is_forced == True)
        if len(getforcedrule) == 1:
            self.pricerule_id = getforcedrule.id
        return {'domain':{'pricerule_id':[('id','in',tranch.ids)]}}
    
    """
    @api.onchange('guest_id','guest_gender')
    @api.depends('guest_id','guest_gender')
    def get_applicable_product_list(self):
        self.product_id = False
        if self.guest_gender == 'male':
            return {'domain':{'product_id':[('dest_ok','=',True),('dest_product_group','=','access'),('dest_id','=',self.dest_id.id),('dest_guest_gender_male','=',True)]}}
        elif self.guest_gender == 'female':
            return {'domain':{'product_id':[('dest_ok','=',True),('dest_product_group','=','access'),('dest_id','=',self.dest_id.id),('dest_guest_gender_female','=',True)]}}
        else:
            return {'domain':{'product_id':[('dest_ok','=',True),('dest_product_group','=','access'),('dest_id','=',self.dest_id.id)]}}
    """
    
    @api.onchange('state','expiry_date')
    @api.depends('state','expiry_date')
    def _compute_is_expired(self):
        today = fields.Datetime.now()
        for record in self:
            record.is_expired = record.state in ['new','pending'] and record.expiry_date and record.expiry_date < today
    
    @api.onchange('state','expiry_date')
    @api.depends('state','expiry_date')        
    def _compute_is_today(self):
        today_start = fields.Datetime.now() + relativedelta(hours=3) + relativedelta(hour=0, minute=0, second=0) 
        today_end = fields.Datetime.now() + relativedelta(hours=3) + relativedelta(hour=23, minute=59, second=59)
        for record in self:
            if record.expiry_date:
                expiry_date = record.expiry_date + relativedelta(hours=3)
                record.is_today = record.state in ['new','pending'] and expiry_date and expiry_date >= today_start and expiry_date <= today_end            
            else:
                record.is_today = False
            
    @api.constrains('guest_id', 'membership_id', 'access_date_date','id','guest_id.partnergender','product_id.dest_guest_gender_female','product_id.dest_guest_gender_male')
    def _check_guest_duplication(self):
        if self.guest_id and self.membership_id and self.access_date_date and self.env['destination.guest'].search_count([('guest_id', '=', self.guest_id.id),('dest_id','=',self.dest_id.id),('access_date_date','=',self.access_date_date),('state','!=','cancel')]) > 1:
            raise ValidationError(_('Guest is already registered for the same date.'))
        if self.dest_id.partner_id_required and not self.guest_id.id_number:
            raise ValidationError(_('Guest ID is required.'))
        if self.dest_id.partner_gender_required and not self.guest_id.partnergender:
            raise ValidationError(_('Guest Gender is required.'))
        if self.dest_id.partner_email_required and not self.guest_id.email:
            raise ValidationError(_('Guest Email is required.'))
        if self.dest_id.partner_phone_required and not self.guest_id.phone:
            raise ValidationError(_('Guest Phone is required.'))
        if self.dest_id.partner_mobile_required and not self.guest_id.mobile:
            raise ValidationError(_('Guest Mobile is required.'))
        if self.is_male and not self.product_id.dest_guest_gender_male:
            raise ValidationError(_('Guest Gender & Product do not match.'))
        if self.is_female and not self.product_id.dest_guest_gender_female:
            raise ValidationError(_('Guest Gender & Product do not match.'))
        #if self.guest_batch_id and (self.access_date_date != self.guest_batch_id.access_date_date):
        #    raise ValidationError(_('Access Date of Guest [' + self.guest_id.name + '] and Batch Date do not match.'))
            
    def compute_expiry_date(self, access_date, product, pricerule):
        for record in self:
            access_date_date = (access_date + relativedelta(hours=3)).date()
            access_date_month = (access_date + relativedelta(hours=3)).month
            access_date_weekday = (access_date + relativedelta(hours=3)).weekday()
            access_date_time = float((access_date + relativedelta(hours=3)).time().strftime('%H')) + (float((access_date + relativedelta(hours=3)).time().strftime('%M'))/60*100/100)

            if product:
                if pricerule:
                    if pricerule.dest_custom_price == 'weekday_rate':
                        if pricerule.rule_type == 'price':
                            pricerulerecord = record.env['destination.price.access.lines'].search([('pricerule_id','=',pricerule.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                            if len(pricerulerecord) != 1:
                                raise ValidationError(_('Pricing Error, please revise Price Rule pricing.'))
                            else:
                                return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(pricerulerecord.access_time_start * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(pricerulerecord.access_duration), minutes=(pricerulerecord.access_duration % 1 * 60))    
                        else:
                            pricelinerecord = record.env['destination.product.access.price.lines'].search([('product_id','=',product.product_tmpl_id.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                            if len(pricelinerecord) != 1:
                                raise ValidationError(_('Pricing Error, please revise Product pricing.'))
                            else:
                                return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(pricelinerecord.access_time_start * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(pricelinerecord.access_duration), minutes=(pricelinerecord.access_duration % 1 * 60))    
                    else:
                        if pricerule.service_timeonly_start > 0 or pricerule.service_timeonly_end > 0:
                            if access_date_time >= pricerule.service_timeonly_start and access_date_time <= pricerule.service_timeonly_end:
                                return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(pricerule.dest_access_start_time * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(pricerule.dest_access_duration), minutes=(pricerule.dest_access_duration % 1 * 60))    
                            else:
                                return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(product.dest_access_start_time * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(product.dest_access_duration), minutes=(product.dest_access_duration % 1 * 60))    
                        else:
                            return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(pricerule.dest_access_start_time * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(pricerule.dest_access_duration), minutes=(pricerule.dest_access_duration % 1 * 60))    
                else:
                    if product.dest_custom_price == 'weekday_rate':
                        pricelinerecord = record.env['destination.product.access.price.lines'].search([('product_id','=',product.product_tmpl_id.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                        if len(pricelinerecord) != 1:
                            raise ValidationError(_('Pricing Error, please revise Product pricing.'))
                        else:
                            return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(pricelinerecord.access_time_start * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(pricelinerecord.access_duration), minutes=(pricelinerecord.access_duration % 1 * 60))    
                    else:
                        return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(product.dest_access_start_time * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(product.dest_access_duration), minutes=(product.dest_access_duration % 1 * 60))    
            else:
                return 0
    
    @api.onchange('access_date')
    @api.depends('access_date')
    def compute_dates(self):
        for record in self:
            if record.access_date:
                #if record.access_date < datetime.datetime.now():
                #    raise UserError(_("Access Date/Time cannot be in the past."))
                    
                record.access_date_date = (record.access_date + relativedelta(hours=3)).date()
                record.access_date_month = (record.access_date + relativedelta(hours=3)).month
                record.access_date_weekday = (record.access_date + relativedelta(hours=3)).weekday()
                record.access_date_time = float((record.access_date + relativedelta(hours=3)).time().strftime('%H')) + (float((record.access_date + relativedelta(hours=3)).time().strftime('%M'))/60*100/100)
            else:
                record.access_date_date = False
                record.access_date_month = False
                record.access_date_weekday = False
                record.access_date_time = False

    @api.onchange('access_date','product_id','pricerule_id')
    @api.depends('access_date','product_id','pricerule_id')
    def get_expiry_date(self):
        for record in self:
            access_date = record.access_date
            product = record.product_id
            pricerule = record.pricerule_id
            record.expiry_date = record.compute_expiry_date(access_date, product, pricerule)
    
    @api.onchange('access_date','member_id','guest_id','token_type','product_id','pricerule_id')            
    def compute_state(self):
        
        for record in self:
            nts = []
            exceptions = []
            exceptions1 = []
            exceptions2 = []
            exceptions3 = []
            exceptions4 = []
            
            
            #access cap exceptions
            
            if record.membership_id.dest_product_access_rule == 'standard':
                memcaps = record.membership_id.product_id.access_products_ids
            else:
                memcaps = record.membership_id.dest_product_access_cap.filtered(lambda r: r.state == 'active')
                
            for recs in memcaps:
                counter = 0
                for prod in recs.product_ids:
                    if recs.free_guest == True:
                        if recs.period == 'day':
                            counter = counter + self.env['destination.guest'].search_count([('state','not in',['cancel','pending','blacklist']),('membership_id','=',record.membership_id.id),('access_date_date','=',record.access_date_date),('product_id','=',prod.product_variant_id._origin.id),('token_type','=','free'),('id','!=',record._origin.id)]) + (1 if (record.product_id.id == prod.product_variant_id._origin.id and record.token_type == 'free') else 0)
                        elif recs.period == 'month':
                            counter = counter + self.env['destination.guest'].search_count([('state','not in',['cancel','pending','blacklist']),('membership_id','=',record.membership_id.id),('access_date_month','=',record.access_date_month),('product_id','=',prod.product_variant_id._origin.id),('token_type','=','free'),('id','!=',record._origin.id)]) + (1 if (record.product_id.id == prod.product_variant_id._origin.id and record.token_type == 'free') else 0)
                    else:
                        if recs.period == 'day':
                            counter = counter + self.env['destination.guest'].search_count([('state','not in',['cancel','pending','blacklist']),('membership_id','=',record.membership_id.id),('access_date_date','=',record.access_date_date),('product_id','=',prod.product_variant_id._origin.id),('id','!=',record._origin.id)]) + (1 if record.product_id.id == prod.product_variant_id._origin.id else 0)
                        elif recs.period == 'month':
                            counter = counter + self.env['destination.guest'].search_count([('state','not in',['cancel','pending','blacklist']),('membership_id','=',record.membership_id.id),('access_date_month','=',record.access_date_month),('product_id','=',prod.product_variant_id._origin.id),('id','!=',record._origin.id)]) + (1 if record.product_id.id == prod.product_variant_id._origin.id else 0)
                #nts.append(str(recs.cap) + '/' + str(counter))
                #record.note = nts

                if counter > recs.cap and record.product_id.id in recs.product_ids.mapped('product_variant_id.id'):
                    prodslist = recs.product_ids.mapped('name')
                    prodnames = ', '.join('(' + x + ')' for x in prodslist)
                    exceptions1.append(str('[' + prodnames + ']') + _(' cap exceeded [') + str(counter) +'/'+ str(recs.cap) + ']')
                else:
                    exceptions1.clear
            
            # weekday access exceptions
            dayslist = []
            if record.membership_id.product_id.dest_member_access_monday:
                dayslist.append(0)
            if record.membership_id.product_id.dest_member_access_tuesday:
                dayslist.append(1)
            if record.membership_id.product_id.dest_member_access_wednesday:
                dayslist.append(2)
            if record.membership_id.product_id.dest_member_access_thursday:
                dayslist.append(3)
            if record.membership_id.product_id.dest_member_access_friday:
                dayslist.append(4)
            if record.membership_id.product_id.dest_member_access_saturday:
                dayslist.append(5)
            if record.membership_id.product_id.dest_member_access_sunday:
                dayslist.append(6)
                
            if record.member_id and record.access_date_weekday not in dayslist:
                exceptions2.append(_("Member does not have access on selected Access Date."))
            else:
                exceptions2.clear
                
            # hold exceptions
            if record.member_id.membership_state == 'hold':
                exceptions3.append(_("Rental is on Hold."))
            else:
                exceptions3.clear
                
                
            #blacklist exceptions
            if self.env['destination.blacklist'].search_count([('partner_id','=',record.guest_id.id),('state','=','active'),('start_date','<=',record.access_date),('end_date','>=',record.access_date)]) > 0:
                exceptions4.append(_("Guest is blacklisted."))
            else:
                exceptions4.clear
            
            #print exceptions and compute state
            if exceptions1:
                exceptions.append('*1* ' + ','.join(exceptions1))
            if exceptions2:
                exceptions.append('*2* ' + ','.join(exceptions2))
            if exceptions3:
                exceptions.append('*3* ' + ','.join(exceptions3))
            if exceptions4:
                exceptions.append('*4* ' + ','.join(exceptions4))
            
            if exceptions:
                record.access_exceptions = '\n'.join(exceptions)
                record.state = 'pending'
            else:
                record.access_exceptions = False
                record.state = 'new'
                    
                    
    
    @api.onchange('product_id','access_date','pricerule_id','token_type')
    @api.depends('product_id','access_date','pricerule_id','token_type')
    def compute_unit_price(self):   
        for record in self:
            access_date = record.access_date
            product = record.product_id
            pricerule = record.pricerule_id
            
            if record.token_type != 'free':
                record.unit_price = record.compute_guest_price(access_date, product, pricerule)
            else:
                record.unit_price = 0

    
    @api.onchange('product_id','access_date')
    def change1(self):
        for record in self:
            record.pricerule_id = False        

    @api.onchange('dest_id')
    def change2(self):
        for record in self:
            
            record.product_id = False if not self.env.context.get('default_product_id') else record.product_id
            record.member_id = False if not self.env.context.get('default_member_id') else record.member_id
            record.token_type = 'guest' if not self.env.context.get('default_token_type') else record.token_type
            record.pricerule_id = False if not self.env.context.get('default_pricerule_id') else record.pricerule_id
            
    @api.onchange('member_id')
    def change3(self):
        for record in self:
            record.product_id = False
            record.token_type = 'guest'
            record.pricerule_id = False


    def request_approval(self):
        self.state = 'pending'
        check_authorizer = self.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'authorizer')
        
        if check_authorizer:
            managers = check_authorizer
        else:
            managers = self.dest_id.manager_ids
        
        for manager in managers:
            
        
            todos = {
            'res_id': self.id,
            'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.guest')]).id,
            'user_id': manager.user_id.id,
            'summary': 'Request Access Approval',
            'note': self.name + '\nPlease review the following exception(s):\n' + self.access_exceptions,
            'activity_type_id': 4,
            'date_deadline': self.access_date,
            }
            sfa = self.env['mail.activity'].create(todos)
        
    def approve_guest(self):
        is_manager = (True if self.env.user.id in self.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'manager').user_id.ids else False) 
        
        if is_manager:
            self.state = 'new'
            getrequests = self.env['mail.activity'].search([
                            ('res_id','=',self.id),
                            ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.guest')]).id),
                            ('summary','=','Request Access Approval'),
                            ('activity_type_id','=',4)
                        ])
            if getrequests:
                getrequests.action_feedback(feedback='Approved')
        else:
            getrequests = self.env['mail.activity'].search([
                            ('res_id','=',self.id),
                            ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.guest')]).id),
                            ('summary','=','Request Access Approval'),
                            ('activity_type_id','=',4)
                        ])
            if getrequests:
                getrequests.action_feedback(feedback='Authorized')
            
            managers = self.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'manager')

            for manager in managers:
                todos = {
                    'res_id': self.id,
                    'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.guest')]).id,
                    'user_id': manager.user_id.id,
                    'summary': 'Request Access Approval',
                    'note': self.name + '\nPlease review the following exception(s):\n' + self.access_exceptions,
                    'activity_type_id': 4,
                    'date_deadline': self.access_date,
                    }

                sfa = self.env['mail.activity'].create(todos)
            
        
    def reject_guest(self):
        self.state = 'cancel'
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.guest')]).id),
                        ('summary','=','Request Access Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.action_feedback(feedback='Rejected')
            
        
    def cancel_guest(self):
        self.state = 'cancel'
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.guest')]).id),
                        ('summary','=','Request Access Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.action_feedback(feedback='Cancelled')
        
    def checkout_guest(self):
        context = {
                'default_guest_id': self.id,
                'default_access_code': self.access_code.display_name,
                'default_access_function': "out",
            }

        return {
            'name': 'Check-Out Guest',
            'view_mode': 'form',
            'res_model': 'destination.access.code.checkin.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }
        
        
    def done_guest(self):
        for record in self:
            if not record.is_manager and record.total_due != 0:
                raise UserError(_("Please settle outstanding dues."))
            else:
                self.close_date = fields.Datetime.now()
                self.state = 'done'
              
  
    def process_guest(self):
        
        context = {
            'default_guest_id': self.id,
            'default_product_id': self.product_id.id,
            'default_pricerule_id': self.pricerule_id.id,
            'default_unit_price': self.unit_price,
            'default_member_id' : self.member_id.id,
            'default_membership_id' : self.membership_id.id,
            'default_dest_id': self.dest_id.id,
            'default_token_type': self.token_type,
            'default_access_payment_method_id': self.access_default_payment_method_id.id,
            }
        return {
            'name': _('Process Guest'),
            'view_mode': 'form',
            'res_model': 'destination.access.code.process.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }
        
    def checkin_guest(self):
        context = {
                'default_guest_id': self.id,
                'default_access_function': "in",
            }

        return {
            'name': _('Check-In Guest'),
            'view_mode': 'form',
            'res_model': 'destination.access.code.checkin.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }
        

    def compute_guest_price(self, access_date, product, pricerule):
        for record in self:
            if access_date:
                access_date_date = (access_date + relativedelta(hours=3)).date()
                access_date_month = (access_date + relativedelta(hours=3)).month
                access_date_weekday = (access_date + relativedelta(hours=3)).weekday()
                access_date_time = float((access_date + relativedelta(hours=3)).time().strftime('%H')) + (float((access_date + relativedelta(hours=3)).time().strftime('%M'))/60*100/100)

                if product:
                    if pricerule:
                        if pricerule.rule_type == 'price':
                            if pricerule.dest_custom_price == 'weekday_rate':
                                pricerulerecord = pricerule.dest_access_pricing_ids.search([('pricerule_id','=',pricerule.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                                if len(pricerulerecord) != 1:
                                    raise ValidationError(_('Pricing Error, please revise Price Rule pricing.'))
                                else:
                                    return pricerulerecord.price
                            else:
                                if pricerule.service_timeonly_start > 0 or pricerule.service_timeonly_end > 0:
                                    if access_date_time >= pricerule.service_timeonly_start and access_date_time <= pricerule.service_timeonly_end:
                                        return pricerule.list_price
                                    else:
                                        return product.lst_price
                                else:
                                    return pricerule.list_price
                        else:
                            if pricerule.dest_custom_price == 'weekday_rate':
                                
                                pricelinerecord = product.dest_access_pricing_ids.search([('product_id','=',product.product_tmpl_id.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                                if len(pricelinerecord) != 1:
                                    raise ValidationError(_('Pricing Error, please revise Product pricing.'))
                                else:
                                    return pricelinerecord.price - (pricelinerecord.price * pricerule.discount / 100) 
                                
                            else:
                                if pricerule.service_timeonly_start > 0 or pricerule.service_timeonly_end > 0:
                                    if access_date_time >= pricerule.service_timeonly_start and access_date_time <= pricerule.service_timeonly_end:
                                        return product.lst_price - (product.lst_price * pricerule.discount / 100) 
                                    else:
                                        return product.lst_price
                                else:
                                    return product.lst_price - (product.lst_price * pricerule.discount / 100) 
                            
                    else:
                        if product.dest_custom_price == 'weekday_rate':
                            pricelinerecord = product.dest_access_pricing_ids.search([('product_id','=',product.product_tmpl_id.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                            if len(pricelinerecord) != 1:
                                raise ValidationError(_('Pricing Error, please revise Product pricing.'))
                            else:
                                return pricelinerecord.price
                        else:
                            return product.lst_price
                else:
                    return 0
            else:
                return 0
            
            

    def unprocess_guest(self):
        self.state = 'new'
        
        
    def clone_guest(self):
        context = {
                'default_dest_id': self.dest_id.id,
                'default_access_date': self.access_date,
                'default_member_id': self.member_id.id,
                'default_token_type': self.token_type,
            }

        return {
            'view_mode': 'form',
            'res_model': 'destination.guest',
            'type': 'ir.actions.act_window',
            'context': context
        }
        
                
        
