# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import datetime
import pytz
from pytz import timezone, UTC
import json
from lxml import etree
import math
from odoo.tools import float_compare, format_datetime, format_time

PERIOD_RATIO = {
    'minute': 1,
    'hour': 1 * 60,
    'day': 24 * 60,
    'week': 24 * 60 * 7
}

class Membership(models.Model):
    _name = "destination.membership"
    _description = "Rental"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    

    #header fields
    state = fields.Selection([('new', 'Draft'),('pending', 'Pending Approval'),('approved', 'Approved'),('confirmed', 'Confirmed'),('active', 'Active'),('hold', 'On Hold'),('checked-out', 'Checked-Out'),('expired', 'Expired'),('done', 'Done'),('cancel','Cancelled'),('late','Late')], string='Status', copy=False, tracking=True, default='new')
    previous_state = fields.Selection([('new', 'Draft'),('pending', 'Pending Approval'),('approved', 'Approved'),('confirmed', 'Confirmed'),('active', 'Active'),('hold', 'On Hold'),('checked-out', 'Checked-Out'),('expired', 'Expired'),('done', 'Done'),('cancel','Cancelled'),('late','Late')], string='Previous Status', default='new', copy=False)
    members_lines = fields.One2many('destination.membership.member', 'membership_id', string = 'Members', copy=True, tracking=True)   
    total_members = fields.Integer('Total Members', copy=False, compute='compute_totals_counts')   
    total_invoiced = fields.Monetary(compute='compute_totals_counts', string="Total Invoiced", digits=2)
    total_invoiced_untaxed = fields.Monetary(compute='compute_totals_counts', string="Total Untaxed", digits=2)
    total_due = fields.Monetary(compute='compute_totals_counts', string="Total Due", digits=2)
    total_sales = fields.Monetary(compute='compute_totals_counts', string="Total Sales", digits=2)
    total_deposit = fields.Monetary(compute='compute_totals_counts', string="Security Deposit", digits=2)
    total_deposit_due = fields.Monetary(compute='compute_totals_counts', string="Security Deposit Due", digits=2)
    invoice_count = fields.Integer(string='Invoice Count', compute='_get_invoiced')
    total_extras = fields.Monetary(compute='compute_totals_counts', string="Extras Invoiced", digits=2)
    total_extras_due = fields.Monetary(compute='compute_totals_counts', string="Extras Due", digits=2)
    color = fields.Integer(string="Color Code", compute='compute_color')
    progress = fields.Integer(string="Progress", compute='compute_color')
    
    guest_ids = fields.One2many('destination.guest', 'membership_id', string = 'Guest Access')
    guest_count = fields.Integer(string='Guest Access', compute='count_guest')
    guest_total_invoiced = fields.Monetary(compute='count_guest', string="Guest Invoiced", readonly=True, digits=2)
    guest_total_untaxed = fields.Monetary(compute='count_guest', string="Guest Untaxed", readonly=True, digits=2)
    guest_total_due = fields.Monetary(compute='count_guest', string="Guest Dues", readonly=True, digits=2)
    
    member_activity_ids = fields.One2many('destination.membership.member.activity', 'membership_id', string = 'Member Access')
    member_activity_count = fields.Integer(string='Member Access', compute='count_member_activity')
    member_total_invoiced = fields.Monetary(compute='count_member_activity', string="Member Invoiced", readonly=True, digits=2)
    member_total_untaxed = fields.Monetary(compute='count_member_activity', string="Member Untaxed", readonly=True, digits=2)
    member_total_due = fields.Monetary(compute='count_member_activity', string="Member Dues", readonly=True, digits=2)
    

    #configuration fields
    is_manager = fields.Boolean(string="Is Manager", compute='_is_manager')
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids')
    cat_user_ids = fields.Many2many('destination.user', string='Excluded Users', related='product_categ_id.user_ids')   
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments", tracking=True)
    name = fields.Text(string='Reference', required=False, copy=False, default=lambda self: _('New'))
    active = fields.Boolean(string="Active", tracking=True, default=True)
    sequence = fields.Integer(string="Sequence")
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id', depends=['product_id.currency_id'], store=True, string='Currency')
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    is_late = fields.Boolean("Late")
    rental_partner_default_category_ids = fields.Many2many('res.partner.category', 'destination_rental_default_ids',string='Rental Partner Default Tags', related='dest_id.rental_partner_default_category_ids')
    can_checkin = fields.Boolean("Can Check-in", compute='compute_can_checkin')
    
    #date fields
    date_order = fields.Datetime(string='Order Date', required=True, copy=False, tracking=True, default=fields.Datetime.now)
    date_expiry = fields.Datetime(string='Expiration Date', tracking=True)
    start_date = fields.Datetime(string="Start", required=True, tracking=True)
    end_date = fields.Datetime(string="End", required=True, tracking=True)
    pickup_date = fields.Datetime(string="Check In", tracking=True)
    return_date = fields.Datetime(string="Check Out", tracking=True)
    dest_checkin_time = fields.Datetime(string="Check-In Time", copy=True)
    dest_checkout_time = fields.Datetime(string="Check-Out Time", copy=True)  
    next_date = fields.Datetime(string="Next Action", compute='_compute_next_date')  
    product_availability = fields.Boolean("Availability", default=False, compute="compute_product_availability")
    
    #main fields
    dest_id = fields.Many2one('destination.destination', string='Entity', tracking=True, copy=True, index=True, default=lambda self: self._get_default_dest_id())
    lock_dest_id = fields.Boolean(store=False, copy=False, default=False)
    product_id = fields.Many2one('product.product', string='Product', domain="[('dest_ok','=',True),('dest_id','=',dest_id),('dest_product_group','in',['accommodation','membership'])]", ondelete='restrict', tracking=True,  copy=True, required=True)
    lock_product_id = fields.Boolean(store=False, copy=False, default=False)
    product_tmpl_id = fields.Many2one('product.template', related='product_id.product_tmpl_id')
    product_id_code = fields.Char(string='Product Code')
    product_id_dest_code = fields.Char(string='Entity Code')   
    membership_code = fields.Char(string='Code', size=4, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer', ondelete='restrict', tracking=True, copy=True, required=True)
    lock_partner_id = fields.Boolean(store=False, copy=False, default=False)   
    referral_partner_id = fields.Many2one('res.partner', string='Referred By', ondelete='restrict', tracking=True, copy=True, required=False)
    
    
    #product fields
    product_categ_id = fields.Many2one('product.category', "Product Category", related="product_id.categ_id", store=True)
    dest_product_group = fields.Selection([('accommodation', 'Rental'), ('membership', 'Membership'), ('access', 'Access'), ('others', 'Others')], string="Product Group",  copy=False)
    dest_custom_price = fields.Selection([('weekday_rate', 'Variable Weekday Rate'), ('daily_rate', 'Variable Daily Rate'), ('fixed', 'Fixed Rate')], string="Pricing Type",  copy=False)
    dest_invoice_policy = fields.Selection([('order', 'At Order'), ('return', 'At Return')], string="Invoice Policy")      
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', ondelete='restrict', tracking=True,  copy=False)
    applied_payment_term_id = fields.Many2one('account.payment.term', string='Applied Payment Terms', ondelete='restrict', tracking=True, copy=False)
    dest_member_count = fields.Integer(string="Max. Capacity")
    dest_member_male_count = fields.Integer(string="Male Cap", copy=True)
    dest_member_female_count = fields.Integer(string="Female Cap", copy=True)
    actual_dest_member_count = fields.Integer(string="Applied Max. Capacity", compute='compute_totals_counts')    
    actual_dest_member_male_count = fields.Integer(string="Applied Male Cap", compute='compute_totals_counts')
    actual_dest_member_female_count = fields.Integer(string="Applied Female Cap", compute='compute_totals_counts')
    dest_daily_guest_count = fields.Integer(string="Guests / Day")
    dest_daily_guest_male_count = fields.Integer(string="Male Guests / Day", copy=True)
    dest_daily_guest_female_count = fields.Integer(string="Female Guests / Day", copy=True)
    actual_dest_daily_guest_count = fields.Integer(string="Applied Guests / Day",  copy=True, tracking=True)  
    actual_dest_daily_guest_male_count = fields.Integer(string="Applied Male Guests / Day",  copy=True, tracking=True)    
    actual_dest_daily_guest_female_count = fields.Integer(string="Applied Female Guests / Day",  copy=True, tracking=True)    
    dest_month_free_guest_count = fields.Integer(string="Free Guests / Month")
    actual_dest_month_free_guest_count = fields.Integer(string="Applied Free Guests / Month",  copy=True)    
    dest_product_security_deposit = fields.Selection([('percent', 'Percentage'), ('fixed', 'Fixed Amount')],  string="Security Deposit")
    dest_product_security_deposit_product = fields.Many2one('product.product', string="Security Deposit Product", ondelete='restrict')
    dest_product_security_deposit_amount = fields.Float(string="Deposit Amount", digits='Product Price', default='500', )
    dest_product_security_deposit_percent = fields.Float(string="Deposit Percentage", default='30')   
    dest_product_access_rule = fields.Selection([('standard','Standard'),('custom','Custom')], default="standard", string="Access Rules", copy=True, tracking=True)
    dest_product_access_cap = fields.One2many('destination.membership.guest.access.cap', 'membership_id', string='Guest Access Caps')
    
    
    
    #sale order fields
    so_ids = fields.Many2many('sale.order','rental_id', string='Sale Order', tracking=True,  copy=False, required=False)
    so_ids_count = fields.Integer("Count of SOs", compute='compute_totals_counts')
    membership_lines = fields.One2many('destination.membership.line', 'membership_id', string = 'Rental Lines', copy=True)
    amount_untaxed = fields.Monetary(string='Rental Untaxed',  compute='_amount_all', tracking=True, store=True, digits=2)
    amount_tax = fields.Monetary(string='Rental Taxes',  compute='_amount_all', tracking=True, store=True, digits=2)
    amount_total = fields.Monetary(string='Rental Total',  compute='_amount_all', tracking=True, store=True, digits=2)
    
    extra_lines = fields.One2many('destination.membership.extra.line', 'membership_id', string = 'Extra Lines', copy=True)
    extra_amount_untaxed = fields.Monetary(string='Extras Untaxed',  compute='_amount_all', tracking=True, store=True, digits=2)
    extra_amount_tax = fields.Monetary(string='Extras Taxes',  compute='_amount_all', tracking=True, store=True, digits=2)
    extra_amount_total = fields.Monetary(string='Extras Total',  compute='_amount_all', tracking=True, store=True, digits=2)
    
    total_amount_untaxed = fields.Monetary(string='Total Untaxed',  compute='_amount_all', tracking=True, store=True, digits=2)
    total_amount_tax = fields.Monetary(string='Total Taxes',  compute='_amount_all', tracking=True, store=True, digits=2)
    total_amount_total = fields.Monetary(string='Total',  compute='_amount_all', tracking=True, store=True, digits=2)
    
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, tracking=True, default=lambda self: self.env.user)
    note_template = fields.Many2one('destination.note', "Note Template", tracking=True)
    note = fields.Html("Note", tracking=True)
    
    #invoice fields
    no_invoice = fields.Boolean("No Invoice", tracking=True)
    invoice_ids = fields.Many2many("account.move", string='Invoices', compute="_get_invoiced", copy=False, search="_search_invoice_ids")
    invoice_old_id = fields.Many2one("account.move", string="Existing Invoice", copy=False, tracking=True, domain="[('move_type','=','out_invoice'),('state','=','posted'),('partner_id','=',partner_id)]")
    deposit_id = fields.Many2one("account.move", string='Security Deposit', copy=False, tracking=True)
    rental_sales_journal_id = fields.Many2one('account.journal', string="Sales Journal", store=True, domain="[('company_id', '=', company_id), ('type', '=', 'sale')]", related='dest_id.rental_sales_journal_id')
    rental_deposit_journal_id = fields.Many2one('account.journal', string="Deposit Journal", store=True, domain="[('company_id', '=', company_id), ('type', '=', 'sale')]", related='dest_id.rental_deposit_journal_id')
    rental_payment_method_ids = fields.Many2many('destination.payment.method',string='Payment Methods', related='dest_id.rental_payment_method_ids')
    rental_payment_method_id = fields.Many2one('destination.payment.method',string='Rental Payment Method', domain="[('id','in',rental_payment_method_ids)]")
    rental_deposit_payment_method_id = fields.Many2one('destination.payment.method',string='Deposit Payment Method', domain="[('id','in',rental_payment_method_ids)]")

    
    #PRICING
    discount = fields.Float(string="Discount", copy=True)

    #PRICING #fixed
    unit_price = fields.Float(string="Rate", digits='Product Price',  copy=True)
    applied_unit_price = fields.Float(string="Applied Rate", digits='Product Price',  copy=True)
      
    #PRICING #daily_rate #duration
    dest_variable_daily_price = fields.One2many('destination.product.variabledaily.lines', 'membership_id', string='Variable Daily Prices')
    dest_custom_price_match = fields.Float(string="Rate", digits='Product Price')
    applied_dest_custom_price_match = fields.Float(string="Applied Rate", digits='Product Price', copy=True)
    pricing_id = fields.Many2one('destination.product.variabledaily.lines', string="Pricing")
    duration = fields.Integer(string="Duration")
    duration_unit = fields.Selection([("minute","Minute(s)"), ("hour", "Hour(s)"), ("day", "Night(s)"), ("week", "Week(s)"), ("month", "Month(s)")],string="Unit", required=True, compute="_compute_duration")
    unit_price_new = fields.Monetary(string="Unit Price", default=0.0, required=True)
    
    #PRICING #weekday_rate
    dest_price_monday = fields.Float(string="Rate Monday", digits='Product Price',  copy=True)
    dest_price_tuesday = fields.Float(string="Rate Tuesday", digits='Product Price', copy=True)
    dest_price_wednesday = fields.Float(string="Rate Wednesday", digits='Product Price',  copy=True)
    dest_price_thursday = fields.Float(string="Rate Thursday", digits='Product Price',  copy=True)
    dest_price_friday = fields.Float(string="Rate Friday", digits='Product Price',  copy=True)
    dest_price_saturday = fields.Float(string="Rate Saturday", digits='Product Price',  copy=True)
    dest_price_sunday = fields.Float(string="Rate Sunday", digits='Product Price',  copy=True)
    
    applied_dest_price_monday = fields.Float(string="Applied Rate Monday", digits='Product Price',  copy=True)
    applied_dest_price_tuesday = fields.Float(string="Applied Rate Tuesday", digits='Product Price',  copy=True)
    applied_dest_price_wednesday = fields.Float(string="Applied Rate Wednesday", digits='Product Price',  copy=True)
    applied_dest_price_thursday = fields.Float(string="Applied Rate Thursday", digits='Product Price',  copy=True)
    applied_dest_price_friday = fields.Float(string="Applied Rate Friday", digits='Product Price',  copy=True)
    applied_dest_price_saturday = fields.Float(string="Applied Rate Saturday", digits='Product Price',  copy=True)
    applied_dest_price_sunday = fields.Float(string="Applied Rate Sunday", digits='Product Price',  copy=True)
    
    
    #PRICING #pricerule fields
    pricerule_id = fields.Many2one('destination.price', string="Price Rule", domain="[('product_id','=',product_id),('validity_datetime_start','<=',date_order),('validity_datetime_end','>=',date_order)]")
    is_forced_pricerule = fields.Boolean("Is Forced Price Rule", related='pricerule_id.is_forced')
    service_datetime_start = fields.Datetime(string="Service Start", copy=True)
    service_datetime_end = fields.Datetime(string="Service End", copy=True)
    pricerule_dest_price_monday = fields.Float(string="Price Rule Monday", digits='Product Price',  copy=True)
    pricerule_dest_price_tuesday = fields.Float(string="Price Rule Tuesday", digits='Product Price',  copy=True)
    pricerule_dest_price_wednesday = fields.Float(string="Price Rule Wednesday", digits='Product Price',  copy=True)
    pricerule_dest_price_thursday = fields.Float(string="Price Rule Thursday", digits='Product Price',  copy=True)
    pricerule_dest_price_friday = fields.Float(string="Price Rule Friday", digits='Product Price',  copy=True)
    pricerule_dest_price_saturday = fields.Float(string="Price Rule Saturday", digits='Product Price',  copy=True)
    pricerule_dest_price_sunday = fields.Float(string="Price Rule Sunday", digits='Product Price',  copy=True)
    pricerule_unit_price = fields.Float(string="Price Rule Rate", digits='Product Price',  copy=True)
    pricerule_dest_variable_daily_price = fields.One2many('destination.price.lines', 'membership_id', string = 'Price Rule Daily Prices')
    pricerule_dest_custom_price_match = fields.Float(string="Price Rule Rate", digits='Product Price')
    pricerule_type = fields.Selection([('price', 'Custom Price'),('discount','Discount')], string='Rule Type')
    pricerule_discount = fields.Float(string="Price Rule Discount")
    pricerule_start_date = fields.Datetime(string="Price Rule Start Date", copy=True)
    pricerule_end_date = fields.Datetime(string="Price Rule End Date", copy=True)
    pricerule_pricing_id = fields.Many2one('destination.price.lines',string="Price Rule Pricing")
    pricerule_duration = fields.Integer(string="Price Rule Duration")
    pricerule_duration_unit = fields.Selection([("minute","Minute(s)"), ("hour", "Hour(s)"), ("day", "Night(s)"), ("week", "Week(s)"), ("month", "Month(s)")], string="Price Rule Unit", required=True, compute="_compute_pricerule_duration")
    pricerule_unit_price_new = fields.Monetary(string="Price Rule Unit Price", default=0.0, required=True)
    pricerule_pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    
    
    #approval fields
    check_discount = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_applied_payment_term_id = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_actual_dest_member_count = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_actual_dest_member_male_count = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_actual_dest_member_female_count = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_actual_dest_daily_guest_count = fields.Char(string="To Be Approved", copy=True,  default='0')   
    check_actual_dest_daily_guest_male_count = fields.Char(string="To Be Approved", copy=True,  default='0')   
    check_actual_dest_daily_guest_female_count = fields.Char(string="To Be Approved", copy=True,  default='0')   
    check_actual_dest_month_free_guest_count = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_applied_dest_price_monday = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_applied_dest_price_tuesday = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_applied_dest_price_wednesday = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_applied_dest_price_thursday = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_applied_dest_price_friday = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_applied_dest_price_saturday = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_applied_dest_price_sunday = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_applied_unit_price = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_applied_dest_custom_price_match = fields.Char(string="To Be Approved", copy=True,  default='0')
    check_approval = fields.Boolean(string="To Be Approved", copy=True,  default=False)
    amount_lt_invoice = fields.Boolean(string="Amount Less Than Invoice", copy=True,  default=False, compute='compute_amount_lt_invoice')
    amount_gt_invoice = fields.Boolean(string="Amount Greater Than Invoice", copy=True,  default=False, compute='compute_amount_gt_invoice')
    check_rental_refund_approval = fields.Boolean(string="To Approve Rental Refund", copy=True,  default=False)
    check_rental_recalc = fields.Boolean(string="To Recalculate", copy=True,  default=False)
    
    approval_required = fields.Boolean(string="Check-in Approval", copy=True, compute="get_checkin_rules")
    
    
    #model functions
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_date = None
            prodid = vals.get('product_id') or self.env.context.get('default_product_id')
            prodcode = self.env['product.product'].search([('id','=',prodid)]).dest_product_code
            proddestcode = self.env['product.product'].search([('id','=',prodid)]).dest_id.code
            if 'date_order' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_order']))
            vals['name'] = proddestcode + '/' + prodcode + (('/' + vals['membership_code']) if vals['membership_code'] else '') + '/' + (self.env['ir.sequence'].next_by_code('destination.membership', sequence_date=seq_date) or _('New'))
        result = super(Membership, self).create(vals)
        return result    
    
    def unlink(self):
        for record in self:
            if record.state not in ['new','pending']:
                raise UserError("Delete is not allowed.  Please archive if necessary.")
        return super(Membership, self).unlink()
    
    def name_get(self):
        res = []
        for record in self:
            if record.membership_code:
                name = record.partner_id.name + ' (' + record.dest_id.code + '/' + record.product_id.dest_product_code + '/' + record.membership_code + ')' + ' (' + record.name + ')'
            else:
                name = record.partner_id.name + ' (' + record.dest_id.code + '/' + record.product_id.dest_product_code + ')' + ' (' + record.name + ')'
            res.append((record.id, name))
        return res
        return super(Membership, self).name_get()
    
    @api.depends('dest_id','product_id')
    def get_user_excluded_product_categ_ids(self):
        for record in self:
            record.user_excluded_product_categ_ids = False
            if record.dest_id and record.product_id:
                getuser = record.dest_id.user_ids.filtered(lambda r: r.user_id.id == self.env.user.id)
                if getuser:
                    record.dest_user_id = getuser.id
                    record.user_excluded_product_categ_ids = getuser.user_excluded_product_categ_ids
                    
    @api.onchange('product_id','dest_id')
    @api.depends('product_id','dest_id')
    def get_checkin_rules(self):
        for record in self:
            if record.product_id and record.dest_id:
                if record.product_id.approval_required_product or record.dest_id.approval_required_dest or (record.product_id.dest_product_group == 'accommodation' and record.dest_id.approval_required_accommodation) or (record.product_id.dest_product_group == 'membership' and record.dest_id.approval_required_membership):
                    record.approval_required = True
                else:
                    record.approval_required = False
            else:
                record.approval_required = False
    
    @api.onchange('product_id')
    @api.depends('product_id')
    def _is_manager(self):
        for e in self:
            e.is_manager = (True if e.env.user.id in e.product_id.dest_id.manager_ids.user_id.ids else False)
        
            
    def compute_color(self):
        for record in self:
            if record.state == 'new':
                record.color = 3
                record.progress = 0
            elif record.state == 'pending':
                record.color = 2
                record.progress = 0
            elif record.state == 'approved':
                record.color = 4
                record.progress = 0
            elif record.state == 'confirmed':
                record.color = 7
                record.progress = 0
            elif record.state == 'active':
                record.color = 10
                record.progress = 100
            elif record.state == 'hold':
                record.color = 9
                record.progress = 100
            elif record.state == 'checked-out':
                record.color = 5
                record.progress = 100
            elif record.state == 'expired':
                record.color = 1
                record.progress = 100
            elif record.state == 'done':
                record.color = 8
                record.progress = 100
            elif record.state == 'cancel':
                record.color = 6
                record.progress = 100
            elif record.state == 'late':
                record.color = 2
                record.progress = 100
            else:
                record.color = 11
                record.progress = 0
                
    def _get_default_dest_id(self):
        conf = self.env['destination.destination'].search(['|',('user_ids.user_id','=',self.env.user.id),('manager_ids.user_id','=',self.env.user.id)], limit=1)
        return conf.id
    
    @api.depends('start_date')
    def compute_can_checkin(self):
        for record in self:
            record.can_checkin = False
            if record.start_date:
                nowdate = datetime.datetime.combine(fields.Datetime.now(), datetime.time(23,59,59))
                if record.start_date <= nowdate:
                    record.can_checkin = True
                    

    def count_guest(self):
        for record in self:
            getrealcount = record.guest_ids.filtered(lambda r: r.processin_date and r.state != 'cancel')
            record.guest_count = len(getrealcount)
            invoices = record.guest_ids.invoice_ids.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
            record.guest_total_invoiced = sum(line.amount_total_signed for line in invoices.filtered(lambda r: r.state =='posted'))
            record.guest_total_untaxed = sum(line.amount_untaxed_signed for line in invoices.filtered(lambda r: r.state =='posted'))
            record.guest_total_due = sum(line.amount_residual_signed for line in invoices.filtered(lambda r: r.state =='posted'))
    
    def count_member_activity(self):
        for record in self:
            getrealcount = record.member_activity_ids.filtered(lambda r: r.checkin_date)
            record.member_activity_count = len(getrealcount)
            invoices = record.member_activity_ids.invoice_ids.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
            record.member_total_invoiced = sum(line.amount_total_signed for line in invoices.filtered(lambda r: r.state =='posted'))
            record.member_total_untaxed = sum(line.amount_untaxed_signed for line in invoices.filtered(lambda r: r.state =='posted'))
            record.member_total_due = sum(line.amount_residual_signed for line in invoices.filtered(lambda r: r.state =='posted'))
            
    @api.onchange('note_template')
    def compute_note(self):
        for record in self:
            if record.note_template:
                record.note = record.note_template.note
                
                
    @api.depends('state', 'start_date','end_date')
    def _compute_next_date(self):
        for record in self:
            record.next_date = False
            if record.state in ['new','pending','approved','confirmed']:
                record.next_date = record.start_date or False
            if record.state in ['active','hold']:
                record.next_date = record.end_date or False
    
    ######onchange #Product
    
    @api.onchange('dest_id')
    def reset_domain_fields(self):
        self.rental_payment_method_id = self.dest_id.rental_default_payment_method_id or False
        self.rental_deposit_payment_method_id = self.dest_id.rental_default_payment_method_id or False
        if 'default_product_id' in self.env.context:
            if not self.env.context['default_product_id']:
                self.product_id = False
        else:
            self.product_id = False
            
            
    @api.onchange('product_id')
    def get_product_data(self):
        for record in self:
            record.dest_invoice_policy = record.product_id.dest_invoice_policy
            record.dest_product_group = record.product_id.dest_product_group
            record.dest_custom_price = record.product_id.dest_custom_price
            record.payment_term_id = record.product_id.payment_term_id
            record.dest_member_count = record.product_id.dest_member_count
            record.dest_member_male_count = record.product_id.dest_member_male_count
            record.dest_member_female_count = record.product_id.dest_member_female_count

            record.dest_daily_guest_count = record.product_id.dest_daily_guest_count
            record.dest_daily_guest_male_count = record.product_id.dest_daily_guest_male_count
            record.dest_daily_guest_female_count = record.product_id.dest_daily_guest_female_count
            
            record.dest_month_free_guest_count = record.product_id.dest_month_free_guest_count
            record.dest_price_monday = record.product_id.dest_price_monday
            record.dest_price_tuesday = record.product_id.dest_price_tuesday
            record.dest_price_wednesday = record.product_id.dest_price_wednesday
            record.dest_price_thursday = record.product_id.dest_price_thursday
            record.dest_price_friday = record.product_id.dest_price_friday
            record.dest_price_saturday = record.product_id.dest_price_saturday
            record.dest_price_sunday = record.product_id.dest_price_sunday
            record.unit_price = record.product_id.lst_price
            record.dest_product_security_deposit = record.product_id.dest_product_security_deposit
            record.dest_product_security_deposit_product = record.product_id.dest_product_security_deposit_product
            record.dest_product_security_deposit_amount = record.product_id.dest_product_security_deposit_amount
            record.dest_product_security_deposit_percent = record.product_id.dest_product_security_deposit_percent
            record.product_id_code = record.product_id.dest_product_code
            record.product_id_dest_code = record.product_id.dest_id.code    
            
            record.actual_dest_daily_guest_count = record.dest_daily_guest_count
            record.actual_dest_daily_guest_male_count = record.dest_daily_guest_male_count
            record.actual_dest_daily_guest_female_count = record.dest_daily_guest_female_count
            record.actual_dest_month_free_guest_count = record.dest_month_free_guest_count
            
            record.applied_dest_price_monday = record.dest_price_monday
            record.applied_dest_price_tuesday = record.dest_price_tuesday
            record.applied_dest_price_wednesday = record.dest_price_wednesday
            record.applied_dest_price_thursday = record.dest_price_thursday
            record.applied_dest_price_friday = record.dest_price_friday       
            record.applied_dest_price_saturday = record.dest_price_saturday
            record.applied_dest_price_sunday = record.dest_price_sunday
            
            record.applied_unit_price = record.unit_price
            record.applied_payment_term_id = record.payment_term_id
            
            record.write({'dest_variable_daily_price': [(5, 0, 0)]})
            getrecs = record.product_id.dest_rental_pricing_ids
            for line in getrecs:
                line_dict = {'duration':line.duration,'unit':line.unit,'price':line.price}
                record.write({'dest_variable_daily_price': [(0, 0, line_dict)]})
            
            record.generate_access_caps()
    
    def generate_access_caps(self):
        for record in self:
            if record.dest_product_access_rule == 'custom':
                    record.write({'dest_product_access_cap': [(5, 0, 0)]})
                    getcaprecs = record.product_id.access_products_ids
                    for line in getcaprecs:
                        line_dict = {'sequence':line.sequence,
                                     'cap':line.cap,
                                     'period':line.period,
                                     'free_guest':line.free_guest,
                                     'product_ids': line.product_ids,
                                     'state': 'active',
                                    }
                        record.write({'dest_product_access_cap': [(0, 0, line_dict)]})
            else:
                record.write({'dest_product_access_cap': [(5, 0, 0)]})
            
    

    
    @api.onchange('product_id', 'pricerule_id', 'start_date', 'end_date')
    def compute_checkinout_time(self):
        
        if self.end_date and self.start_date and self.end_date > self.start_date:
            if self.product_id:
                if self.pricerule_id:
                    if self.state in ['new','approved','confirmed']:
                        self.dest_checkin_time = datetime.datetime.combine((self.start_date + relativedelta(hours=3)).date(), datetime.datetime.fromtimestamp(self.pricerule_id.dest_checkin_time * 3600).time()) - relativedelta(hours=3)
                    if self.state in ['new','approved','confirmed','active','late','expired']:
                        self.dest_checkout_time = datetime.datetime.combine((self.end_date + relativedelta(hours=3)).date(), datetime.datetime.fromtimestamp(self.pricerule_id.dest_checkout_time * 3600).time()) - relativedelta(hours=3)
                else:
                    if self.state in ['new','approved','confirmed']:
                        self.dest_checkin_time = datetime.datetime.combine((self.start_date + relativedelta(hours=3)).date(), datetime.datetime.fromtimestamp(self.product_id.dest_checkin_time * 3600).time()) - relativedelta(hours=3)
                    if self.state in ['new','approved','confirmed','active','late','expired']:
                        self.dest_checkout_time = datetime.datetime.combine((self.end_date + relativedelta(hours=3)).date(), datetime.datetime.fromtimestamp(self.product_id.dest_checkout_time * 3600).time()) - relativedelta(hours=3)
        else:
            self.dest_checkin_time = False
            self.dest_checkout_time = False
            
    
            
    @api.onchange('product_id', 'pricerule_id', 'start_date', 'end_date')
    @api.depends('product_id', 'pricerule_id', 'start_date', 'end_date')
    def compute_product_availability(self):
        for record in self:
            if record.name=='New':
                record_ids = record.search([('start_date', '<', record.end_date), ('end_date', '>', record.start_date), ('product_id', '=', record.product_id.id),('state','not in',['new','cancel','done','checked-out'])])
            else:
                record_ids = record.search([('start_date', '<', record.end_date), ('end_date', '>', record.start_date), ('product_id', '=', record.product_id.id), ('id', '!=', record._origin.id),('state','not in',['new','cancel','done','checked-out'])])
            
            if len(record_ids) >= record.product_id.dest_quantity:
                record.product_availability = 0
            else:
                record.product_availability = 1
    
            
  
                
    ######onchange #pricing
    
    @api.onchange('start_date','end_date','product_id','dest_custom_price')
    @api.depends('start_date','end_date','product_id','dest_custom_price')
    def _compute_pricing(self):
        for record in self:
            if record.end_date and record.start_date and record.end_date <= record.start_date:
                record.start_date = ''
                record.end_date = ''
                
                
            
            record.pricing_id = False
            
            if record.product_id and record.dest_custom_price == 'daily_rate':
                record.pricing_id = record._get_best_dest_pricing_rule(
                    start_date=record.start_date,
                    end_date=record.end_date,
                    pricelist=record.pricelist_id,
                    company=record.company_id)
    
    @api.depends('dest_variable_daily_price','end_date','dest_custom_price')
    def _get_best_dest_pricing_rule(self, **kwargs):
        """Return the best pricing rule for the given duration.

        :param float duration: duration, in unit uom
        :param str unit: duration unit (hour, day, week)
        :param datetime start_date:
        :param datetime end_date:
        :return: least expensive pricing rule for given duration
        :rtype: destination.product.variabledaily.lines
        """
        
        
        
        self.ensure_one()
        if not isinstance(self.dest_variable_daily_price[0].id, models.NewId) or self.dest_variable_daily_price[0]._origin: 
            currentpriceset = self.dest_variable_daily_price._origin
        elif isinstance(self.dest_variable_daily_price[0].id, models.NewId) and not self.dest_variable_daily_price[0]._origin: 
            currentpriceset = self.product_id.dest_rental_pricing_ids
        best_pricing_rule = currentpriceset
        if not currentpriceset:
            return best_pricing_rule
        start_date, end_date = kwargs.get('start_date', False), kwargs.get('end_date', False)
        duration, unit = kwargs.get('duration', False), kwargs.get('unit', '')
        pricelist = kwargs.get('pricelist', self.env['product.pricelist'])
        currency = kwargs.get('currency', self.env.company.currency_id)
        company = kwargs.get('company', self.env.company)
        if start_date and end_date:
            duration_dict = self._compute_duration_vals(start_date, end_date)
        elif not(duration and unit):
            return best_pricing_rule  # no valid input to compute duration.
        min_price = float("inf")  # positive infinity
        available_pricings = currentpriceset
        for pricing in available_pricings:
            if duration and unit:
                price = pricing._compute_price(duration, unit)
            else:
                price = pricing._compute_price(duration_dict[pricing.unit], pricing.unit)

            if pricing.currency_id != currency:
                price = pricing.currency_id._convert(
                    from_amount=price,
                    to_currency=currency,
                    company=company,
                    date=date.today(),
                )

            if price < min_price:
                min_price, best_pricing_rule = price, pricing
        return best_pricing_rule            
    
    
    @api.model
    def _compute_duration_vals(self, pickup_date, return_date):
        duration = return_date - pickup_date
        vals = dict(minute=(duration.days * 1440 + duration.seconds / 60))
        vals['hour'] = math.ceil(vals['minute'] / 60)
        vals['day'] = math.ceil(vals['hour'] / 24)
        vals['week'] = math.ceil(vals['day'] / 7)
        duration_diff = relativedelta(return_date, pickup_date)
        months = 1 if duration_diff.days or duration_diff.hours or duration_diff.minutes else 0
        months += duration_diff.months
        months += duration_diff.years * 12
        vals['month'] = months
        return vals 
    

    
    
    def _compute_displayed_currency(self):
        for record in self:
            record.currency_id = record.pricelist_id.currency_id or record.pricing_id.currency_id

    @api.depends('start_date','end_date','pricing_id')
    def _compute_duration(self):
        for record in self:
            values = {
                'duration_unit': 'day',
                'duration': 1.0,
            }
            if record.start_date and record.end_date:
                duration_dict = self._compute_duration_vals(record.start_date, record.end_date)
                if record.pricing_id:
                    values = {
                        'duration_unit': record.pricing_id.unit,
                        'duration': duration_dict[record.pricing_id.unit]
                    }
                else:
                    values = {
                        'duration_unit': 'day',
                        'duration': duration_dict['day']
                    }
            record.update(values)

    @api.depends('pricing_id','duration','product_id','membership_lines')
    def _compute_unit_price(self):
        for record in self:
            if record.pricing_id and record.duration > 0:
                unit_price = record.pricing_id._compute_price(record.duration, record.duration_unit)
                if record.currency_id != record.pricing_id.currency_id:
                    record.unit_price_new = record.pricing_id.currency_id._convert(
                        from_amount=unit_price,
                        to_currency=record.currency_id,
                        company=record.company_id,
                        date=date.today())
                else:
                    record.unit_price_new = unit_price
            elif record.duration > 0:
                record.unit_price_new = record.product_id.lst_price

            product_taxes = record.product_id.taxes_id.filtered(lambda tax: tax.company_id.id == record.company_id.id)
            if record.membership_lines:
                product_taxes_after_fp = record.membership_lines.tax_id
            elif 'default_tax_ids' in self.env.context:
                product_taxes_after_fp = self.env['account.tax'].browse(self.env.context['default_tax_ids'] or [])
            else:
                product_taxes_after_fp = product_taxes

            # TODO : switch to _get_tax_included_unit_price() when it allow the usage of taxes_after_fpos instead
            # of fiscal position. We cannot currently use the fpos because JS only has access to the line information
            # when opening the record.
            product_unit_price = record.unit_price_new
            if set(product_taxes.ids) != set(product_taxes_after_fp.ids):
                flattened_taxes_before_fp = product_taxes._origin.flatten_taxes_hierarchy()
                if any(tax.price_include for tax in flattened_taxes_before_fp):
                    taxes_res = flattened_taxes_before_fp.compute_all(
                        product_unit_price,
                        quantity=1,
                        currency=record.currency_id,
                        product=record.product_id,
                    )
                    product_unit_price = taxes_res['total_excluded']

                flattened_taxes_after_fp = product_taxes_after_fp._origin.flatten_taxes_hierarchy()
                if any(tax.price_include for tax in flattened_taxes_after_fp):
                    taxes_res = flattened_taxes_after_fp.compute_all(
                        product_unit_price,
                        quantity=1,
                        currency=record.currency_id,
                        product=record.product_id,
                        handle_price_include=False,
                    )
                    for tax_res in taxes_res['taxes']:
                        tax = self.env['account.tax'].browse(tax_res['id'])
                        if tax.price_include:
                            product_unit_price += tax_res['amount']
                record.unit_price_new = product_unit_price
            record.dest_custom_price_match = record.unit_price_new / (record.duration or 1)
            record.applied_dest_custom_price_match = record.dest_custom_price_match
    
    
    ######onchange #pricerule
    
    @api.onchange('product_id','date_order','partner_id','referral_partner_id')
    @api.depends('product_id','date_order','partner_id','referral_partner_id')
    def get_applicable_pricerule_list(self):
        self.pricerule_id = False
        tranch = self.env['destination.price'].search([('id','!=',False)]).filtered(lambda r: r.product_id == self.product_id and r.validity_datetime_start <= self.date_order and r.validity_datetime_end >= self.date_order)
        tranch = tranch - tranch.filtered(lambda r: r.customer_apply_on == 'active' if self.partner_id.has_active_membership == False else None)
        tranch = tranch - tranch.filtered(lambda r: r.referral_apply_on == 'active' if self.referral_partner_id.has_active_membership == False else None)
        tranch = tranch - tranch.filtered(lambda r: r.customer_apply_on == 'select' and self.partner_id not in r.partner_ids)
        getforcedrule = tranch.filtered(lambda r: r.is_forced == True)
        if len(getforcedrule) == 1:
            self.pricerule_id = getforcedrule.id
        return {'domain':{'pricerule_id':[('id','in',tranch.ids)]}}

    
    @api.onchange('pricerule_id')
    def get_pricerule_data(self):
        for record in self:
            record.service_datetime_start = record.pricerule_id.service_datetime_start
            record.service_datetime_end = record.pricerule_id.service_datetime_end
            record.pricerule_dest_price_monday = record.pricerule_id.dest_price_monday
            record.pricerule_dest_price_tuesday = record.pricerule_id.dest_price_tuesday
            record.pricerule_dest_price_wednesday = record.pricerule_id.dest_price_wednesday
            record.pricerule_dest_price_thursday = record.pricerule_id.dest_price_thursday
            record.pricerule_dest_price_friday = record.pricerule_id.dest_price_friday
            record.pricerule_dest_price_saturday = record.pricerule_id.dest_price_saturday
            record.pricerule_dest_price_sunday = record.pricerule_id.dest_price_sunday
            record.pricerule_unit_price = record.pricerule_id.list_price
            record.pricerule_type = record.pricerule_id.rule_type
            record.pricerule_discount = record.pricerule_id.discount
            
            record.write({'pricerule_dest_variable_daily_price': [(5, 0, 0)]})
            getrecs = record.pricerule_id.dest_rental_pricing_ids
            for line in getrecs:
                line_dict = {'duration':line.duration,'unit':line.unit,'price':line.price}
                record.write({'pricerule_dest_variable_daily_price': [(0, 0, line_dict)]})
                
    
    def _compute_pricerule_dates(self):
        if self.pricerule_id and self.product_id and self.start_date and self.end_date:
            if self.service_datetime_start and self.service_datetime_end:
                if self.start_date >= self.service_datetime_end or self.end_date <= self.service_datetime_start:
                    self.pricerule_start_date = False
                    self.pricerule_end_date = False
                else:
                    if self.start_date < self.service_datetime_start:
                        self.pricerule_start_date = self.service_datetime_start
                    else:
                        self.pricerule_start_date = self.start_date

                    if self.end_date > self.service_datetime_end:
                        self.pricerule_end_date = self.service_datetime_end
                    else:
                        self.pricerule_end_date = self.end_date
            else:
                self.pricerule_start_date = self.start_date
                self.pricerule_end_date = self.end_date
        else:
            self.pricerule_start_date = False
            self.pricerule_end_date = False
    
    
    @api.depends('pricerule_start_date','pricerule_end_date','pricerule_id','dest_custom_price')
    def _compute_pricerule_pricing(self):
        self.pricerule_pricing_id = False
        for record in self:
            if record.pricerule_id and record.dest_custom_price == 'daily_rate':
                record.pricerule_pricing_id = record._get_best_dest_pricerule_pricing_rule(
                    start_date=record.pricerule_start_date,
                    end_date=record.pricerule_end_date,
                    pricelist=record.pricerule_pricelist_id,
                    company=record.company_id)

    def _get_best_dest_pricerule_pricing_rule(self, **kwargs):
        """Return the best pricing rule for the given duration.

        :param float duration: duration, in unit uom
        :param str unit: duration unit (hour, day, week)
        :param datetime start_date:
        :param datetime end_date:
        :return: least expensive pricing rule for given duration
        :rtype: destination.price.lines
        """
        
        self.ensure_one()
        if not isinstance(self.pricerule_dest_variable_daily_price[0].id, models.NewId) or self.pricerule_dest_variable_daily_price[0]._origin: 
            prcurrentpriceset = self.pricerule_dest_variable_daily_price._origin
        elif isinstance(self.pricerule_dest_variable_daily_price[0].id, models.NewId) and not self.pricerule_dest_variable_daily_price[0]._origin: 
            prcurrentpriceset = self.pricerule_id.dest_rental_pricing_ids
        best_pricing_rule = prcurrentpriceset
        if not prcurrentpriceset:
            return best_pricing_rule
        start_date, end_date = kwargs.get('start_date', False), kwargs.get('end_date', False)
        duration, unit = kwargs.get('duration', False), kwargs.get('unit', '')
        pricelist = kwargs.get('pricelist', self.env['product.pricelist'])
        currency = kwargs.get('currency', self.env.company.currency_id)
        company = kwargs.get('company', self.env.company)
        if start_date and end_date:
            duration_dict = self._compute_duration_vals(start_date, end_date)
        elif not(duration and unit):
            return best_pricing_rule  # no valid input to compute duration.
        min_price = float("inf")  # positive infinity
        available_pricings = prcurrentpriceset
        for pricing in available_pricings:
            if duration and unit:
                price = pricing._compute_price(duration, unit)
            else:
                price = pricing._compute_price(duration_dict[pricing.unit], pricing.unit)

            if pricing.currency_id != currency:
                price = pricing.currency_id._convert(
                    from_amount=price,
                    to_currency=currency,
                    company=company,
                    date=date.today(),
                )

            if price < min_price:
                min_price, best_pricing_rule = price, pricing
        return best_pricing_rule
                
    

    
    
    def _compute_displayed_currency(self):
        for record in self:
            record.currency_id = record.pricerule_pricelist_id.currency_id or record.pricerule_pricing_id.currency_id

    @api.depends('pricerule_start_date','pricerule_end_date','pricerule_pricing_id')
    def _compute_pricerule_duration(self):
        for record in self:
            values = {
                'pricerule_duration_unit': 'day',
                'pricerule_duration': 1.0,
            }
            if record.pricerule_start_date and record.pricerule_end_date:
                duration_dict = self._compute_duration_vals(record.pricerule_start_date, record.pricerule_end_date)
                if record.pricerule_pricing_id:
                    values = {
                        'pricerule_duration_unit': record.pricerule_pricing_id.unit,
                        'pricerule_duration': duration_dict[record.pricerule_pricing_id.unit]
                    }
                else:
                    values = {
                        'pricerule_duration_unit': 'day',
                        'pricerule_duration': duration_dict['day']
                    }
            record.update(values)

    @api.depends('pricerule_pricing_id','pricerule_duration','product_id','membership_lines')
    def _compute_pricerule_unit_price(self):
        for record in self:
            if record.pricerule_pricing_id and record.pricerule_duration > 0:
                unit_price = record.pricerule_pricing_id._compute_price(record.pricerule_duration, record.pricerule_duration_unit)
                if record.currency_id != record.pricerule_pricing_id.currency_id:
                    record.pricerule_unit_price_new = record.pricerule_pricing_id.currency_id._convert(
                        from_amount=unit_price,
                        to_currency=record.currency_id,
                        company=record.company_id,
                        date=date.today())
                else:
                    record.pricerule_unit_price_new = unit_price
            elif record.pricerule_duration > 0:
                record.pricerule_unit_price_new = record.pricerule_id.list_price

            product_taxes = record.product_id.taxes_id.filtered(lambda tax: tax.company_id.id == record.company_id.id)
            if record.membership_lines:
                product_taxes_after_fp = record.membership_lines.tax_id
            elif 'default_tax_ids' in self.env.context:
                product_taxes_after_fp = self.env['account.tax'].browse(self.env.context['default_tax_ids'] or [])
            else:
                product_taxes_after_fp = product_taxes

            # TODO : switch to _get_tax_included_unit_price() when it allow the usage of taxes_after_fpos instead
            # of fiscal position. We cannot currently use the fpos because JS only has access to the line information
            # when opening the record.
            product_unit_price = record.pricerule_unit_price_new
            if set(product_taxes.ids) != set(product_taxes_after_fp.ids):
                flattened_taxes_before_fp = product_taxes._origin.flatten_taxes_hierarchy()
                if any(tax.price_include for tax in flattened_taxes_before_fp):
                    taxes_res = flattened_taxes_before_fp.compute_all(
                        product_unit_price,
                        quantity=1,
                        currency=record.currency_id,
                        product=record.product_id,
                    )
                    product_unit_price = taxes_res['total_excluded']

                flattened_taxes_after_fp = product_taxes_after_fp._origin.flatten_taxes_hierarchy()
                if any(tax.price_include for tax in flattened_taxes_after_fp):
                    taxes_res = flattened_taxes_after_fp.compute_all(
                        product_unit_price,
                        quantity=1,
                        currency=record.currency_id,
                        product=record.product_id,
                        handle_price_include=False,
                    )
                    for tax_res in taxes_res['taxes']:
                        tax = self.env['account.tax'].browse(tax_res['id'])
                        if tax.price_include:
                            product_unit_price += tax_res['amount']
                record.pricerule_unit_price_new = product_unit_price
            record.pricerule_dest_custom_price_match = record.pricerule_unit_price_new / (record.pricerule_duration or 1)


    
    
    
               
    #GENERAL           
                
    #General Functions

    @api.depends('deposit_id','so_ids','members_lines')
    def compute_totals_counts(self):
        for record in self:
            reldepositrevs = record.deposit_id.reversal_move_id
            totalreldepositrevs = sum(line.amount_total_signed for line in reldepositrevs.filtered(lambda r: r.state =='posted'))
            
            reldepositrevspaid = record.deposit_id.reversal_move_id
            totalreldepositrevspaid = sum(line.amount_residual_signed for line in reldepositrevspaid.filtered(lambda r: r.state =='posted'))
            
            record.total_deposit_due = record.deposit_id.amount_residual if record.deposit_id.state == 'posted' else 0 + totalreldepositrevspaid
            record.total_deposit = record.deposit_id.amount_total_signed if record.deposit_id.state == 'posted' else 0 + totalreldepositrevs
            deposits = record.so_ids.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
            deposits = deposits + record.invoice_old_id
            record.total_due = sum(line.amount_residual_signed for line in deposits.filtered(lambda r: r.state =='posted'))
            invoices = record.so_ids.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
            invoices = invoices + record.invoice_old_id
            record.total_invoiced = sum(line.amount_total_signed for line in invoices.filtered(lambda r: r.state =='posted'))
            record.total_invoiced_untaxed = sum(line.amount_untaxed_signed for line in invoices.filtered(lambda r: r.state =='posted'))
            
            
            record.total_sales = sum(line.amount_total for line in record.so_ids.filtered(lambda r: r.state != 'cancel'))  
            record.total_members = len(record.members_lines.filtered(lambda r: r.state == 'active'))
            record.actual_dest_member_count = len(record.members_lines.filtered(lambda r: r.state == 'active'))
            record.actual_dest_member_male_count = len(record.members_lines.filtered(lambda r: r.state == 'active' and r.partner_id.partnergender == 'male'))
            record.actual_dest_member_female_count = len(record.members_lines.filtered(lambda r: r.state == 'active' and r.partner_id.partnergender == 'female'))
            record.so_ids_count = len(record.so_ids)
    
    #SO Functions
    @api.depends('membership_lines.price_total', 'extra_lines.price_total')
    @api.onchange('membership_lines.price_total', 'extra_lines.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.membership_lines:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            
            order.amount_untaxed = amount_untaxed
            order.amount_tax = amount_tax
            order.amount_total = amount_untaxed + amount_tax

            extra_amount_untaxed = extra_amount_tax = 0.0
            for line in order.extra_lines:
                extra_amount_untaxed += line.price_subtotal
                extra_amount_tax += line.price_tax
            
            order.extra_amount_untaxed = extra_amount_untaxed
            order.extra_amount_tax = extra_amount_tax
            order.extra_amount_total = extra_amount_untaxed + extra_amount_tax
            
            order.total_amount_untaxed = order.amount_untaxed + order.extra_amount_untaxed
            order.total_amount_tax = order.amount_tax + order.extra_amount_tax
            order.total_amount_total = order.extra_amount_untaxed + order.extra_amount_tax + order.amount_untaxed + order.amount_tax
           
    
    def update_so(self):
        for record in self:
            if not record.no_invoice:
                if record.so_ids:
                    record.so_ids.filtered(lambda r: r.state != 'cancel').sudo().action_cancel()



                depositamount = False
                if record.dest_product_security_deposit == 'percent':
                    depositamount = record.amount_untaxed * (record.dest_product_security_deposit_percent / 100)
                elif record.dest_product_security_deposit == 'fixed':
                    depositamount = record.dest_product_security_deposit_amount
                else:
                    depositamount = False

                so_dict = {'partner_id' : record.partner_id.id,
                           'payment_term_id' : record.applied_payment_term_id.id,
                           'validity_date' : record.date_expiry,
                           'membership_id' : record.id,
                           'rental_id' : record.id,
                           'origin' : record.name,
                           'analytic_account_id': record.product_id.income_analytic_account_id.id,
                           'dest_payment_method_id': record.rental_payment_method_id.id,
                           'security_deposit_amount': depositamount,
                           'note': record.note,
                           'date_order': record.date_order,
                           'dest_source': 'rental',
                           'dest_id': record.dest_id.id,
                          }
                mso = record.env['sale.order'].create(so_dict)

                mso.message_post_with_view('mail.message_origin_link', values={'self': mso, 'origin': record}, subtype_id=self.env.ref('mail.mt_note').id)

                record.write({'so_ids': [(4, mso.id)]})

                for line in record.membership_lines:
                    lines_dict = {
                          'order_id': mso.id,
                          'product_id' : line.product_id.id,
                          'name': line.name,
                         'product_uom_qty':line.quantity,
                        'price_unit' : line.unit_price,
                        'tax_id' : line.tax_id,
                        'discount': line.discount,
                      }
                    mso.order_line.create(lines_dict)


                for line in record.extra_lines:
                    lines_dict = {
                          'order_id': mso.id,
                          'product_id' : line.product_id.id,
                          'name': line.name,
                         'product_uom_qty':line.quantity,
                        'price_unit' : line.unit_price,
                        'tax_id' : line.tax_id,
                        'discount': line.discount,
                      }
                    mso.order_line.create(lines_dict)


                """
                return {
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'sale.order',
                    'res_id': mso.id,

                }
                """


    
    
    #INVOICE Functions
    def _search_invoice_ids(self, operator, value):
        if operator == 'in' and value:
            self.env.cr.execute("""
                SELECT array_agg(so.id)
                    FROM sale_order so
                    JOIN sale_order_line sol ON sol.order_id = so.id
                    JOIN sale_order_line_invoice_rel soli_rel ON soli_rel.order_line_id = sol.id
                    JOIN account_move_line aml ON aml.id = soli_rel.invoice_line_id
                    JOIN account_move am ON am.id = aml.move_id
                WHERE
                    am.move_type in ('out_invoice', 'out_refund') AND
                    am.id = ANY(%s)
            """, (list(value),))
            so_ids = self.env.cr.fetchone()[0] or []
            return [('id', 'in', so_ids)]
        elif operator == '=' and not value:
            order_ids = self._search([
                ('so_ids.order_line.invoice_lines.move_id.move_type', 'in', ('out_invoice', 'out_refund'))
            ])
            return [('id', 'not in', order_ids)]
        return ['&', ('so_ids.order_line.invoice_lines.move_id.move_type', 'in', ('out_invoice', 'out_refund')), ('so_ids.order_line.invoice_lines.move_id', operator, value)]
    
    @api.depends('so_ids.order_line.invoice_lines')
    def _get_invoiced(self):
        for order in self:
            invoices = order.so_ids.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
            if order.no_invoice and order.invoice_old_id:
                invoices = invoices + order.invoice_old_id
            
            order.invoice_ids = invoices
            order.invoice_count = len(invoices)
    
    def invoice_register_payment(self):
        for record in self:
            active_ids = record.invoice_ids.filtered(lambda r: r.state =='posted').ids
            return {
            'name': _('Register Payment'),
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.move',
                'active_ids': active_ids,
                'default_journal_id': record.rental_payment_method_id.journal_id.id,
                'dont_redirect_to_payments':True,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
            }
    
    def invoice_register_deposit_payment(self):
        for record in self:
            active_ids = record.deposit_id.id
            return {
            'name': _('Register Payment'),
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.move',
                'active_ids': active_ids,
                'default_journal_id': record.rental_deposit_payment_method_id.journal_id.id,
                'dont_redirect_to_payments':True,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
            }
        
    def reverse_deposit(self):
        for record in self:
            active_ids = record.deposit_id.id
            return {
            'name': _('Reverse Deposit'),
            'res_model': 'account.move.reversal',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.move',
                'active_ids': active_ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
            }
    
    
    #DEPOSIT Functions
    def create_deposit(self):
        for record in self:
            if not record.no_invoice:
                if not record.deposit_id:
                    depositamount = False
                    if record.dest_product_security_deposit == 'percent':
                        depositamount = record.amount_untaxed * (record.dest_product_security_deposit_percent / 100)
                    elif record.dest_product_security_deposit == 'fixed':
                        depositamount = record.dest_product_security_deposit_amount
                    else:
                        depositamount = False

                    if depositamount:
                        lines_dict = {
                            'move_type': 'out_invoice',
                            'date': record.date_order,
                            'journal_id': record.rental_deposit_journal_id.id,
                            'partner_id': record.partner_id.id,
                            'invoice_date': record.date_order,
                            'currency_id': record.product_id.currency_id.id,
                            'invoice_payment_term_id': False,
                            'invoice_origin': record.name,
                            'invoice_line_ids': [(0, None, {
                                'name': 'Security Deposit - ' + str(record.name),
                                'product_id': record.dest_product_security_deposit_product.id,
                                'analytic_account_id': record.dest_product_security_deposit_product.income_analytic_account_id.id,
                                'product_uom_id': record.product_id.uom_id.id,
                                'quantity': 1,
                                'price_unit': depositamount,
                                'tax_ids': record.dest_product_security_deposit_product.taxes_id,
                            }),
                                                ]}

                        newinvd = record.env['account.move'].create(lines_dict)
                        newinvd.message_post_with_view('mail.message_origin_link', values={'self': newinvd, 'origin': record}, subtype_id=record.env.ref('mail.mt_note').id)
                        record.deposit_id = newinvd
                        newinvd.sudo().action_post()



    
    
    ######onchange #approval

    
    @api.onchange('actual_dest_daily_guest_count','actual_dest_daily_guest_male_count','actual_dest_daily_guest_female_count','actual_dest_month_free_guest_count','applied_payment_term_id', 'discount', 'actual_dest_member_count','actual_dest_member_male_count','actual_dest_member_female_count', 'applied_dest_price_monday', 'applied_dest_price_tuesday','applied_dest_price_wednesday','applied_dest_price_thursday','applied_dest_price_friday','applied_dest_price_saturday','applied_dest_price_sunday','applied_dest_custom_price_match','applied_unit_price')
    def check_approvals_required(self):
        for record in self:
            check_monday = 0
            check_tuesday = 0
            check_wednesday = 0
            check_thursday = 0
            check_friday = 0
            check_saturday = 0
            check_sunday = 0
            check_unit_price = 0
            check_dest_custom_price_match = 0
            check_discount = 0
            check_approval = 0
            check_members_count = 0
            check_members_male_count = 0
            check_members_female_count = 0
            check_payment_term_id = 0
            check_guests = 0
            check_male_guests = 0
            check_female_guests = 0
            check_freeguests = 0

            if record.applied_dest_price_monday != record.dest_price_monday:
                check_monday = "Exception"
                check_approval = 1
            if record.applied_dest_price_tuesday != record.dest_price_tuesday:
                check_tuesday = "Exception"
                check_approval = 1
            if record.applied_dest_price_wednesday != record.dest_price_wednesday:
                check_wednesday = "Exception"
                check_approval = 1
            if record.applied_dest_price_thursday != record.dest_price_thursday:
                check_thursday = "Exception"
                check_approval = 1
            if record.applied_dest_price_friday != record.dest_price_friday:
                check_friday = "Exception"
                check_approval = 1
            if record.applied_dest_price_saturday != record.dest_price_saturday:
                check_saturday = "Exception"
                check_approval = 1
            if record.applied_dest_price_sunday != record.dest_price_sunday:
                check_sunday = "Exception"
                check_approval = 1
            if record.applied_unit_price != record.unit_price:
                check_unit_price = "Exception"
                check_approval = 1
            if record.applied_dest_custom_price_match != record.dest_custom_price_match:
                check_dest_custom_price_match = "Exception"
                check_approval = 1
            if record.discount != 0:
                check_discount = "Exception"
                check_approval = 1
            if record.actual_dest_member_count > record.dest_member_count:
                check_members_count = "Exception"
                check_approval = 1
            if record.actual_dest_member_male_count > record.dest_member_male_count:
                check_members_male_count = "Exception"
                check_approval = 1
            if record.actual_dest_member_female_count > record.dest_member_female_count:
                check_members_female_count = "Exception"
                check_approval = 1
            if record.applied_payment_term_id != record.payment_term_id:
                check_payment_term_id = "Exception"
                check_approval = 1
            if record.actual_dest_daily_guest_count != record.dest_daily_guest_count:
                check_guests = "Exception"
                check_approval = 1
            if record.actual_dest_daily_guest_male_count != record.dest_daily_guest_male_count:
                check_male_guests = "Exception"
                check_approval = 1
            if record.actual_dest_daily_guest_female_count != record.dest_daily_guest_female_count:
                check_female_guests = "Exception"
                check_approval = 1
            if record.actual_dest_month_free_guest_count != record.dest_month_free_guest_count:
                check_freeguests = "Exception"
                check_approval = 1

            record.update({
                'check_applied_dest_price_monday': check_monday,
                'check_applied_dest_price_tuesday': check_tuesday,
                'check_applied_dest_price_wednesday': check_wednesday,
                'check_applied_dest_price_thursday': check_thursday,
                'check_applied_dest_price_friday': check_friday,
                'check_applied_dest_price_saturday': check_saturday,
                'check_applied_dest_price_sunday': check_sunday,
                'check_applied_unit_price': check_unit_price,
                'check_applied_dest_custom_price_match': check_dest_custom_price_match,
                'check_discount': check_discount,
                'check_actual_dest_member_count': check_members_count, 
                'check_actual_dest_member_male_count': check_members_male_count, 
                'check_actual_dest_member_female_count': check_members_female_count, 
                'check_approval': check_approval,
                'check_applied_payment_term_id' : check_payment_term_id,
                'check_actual_dest_daily_guest_count' : check_guests,
                'check_actual_dest_daily_guest_male_count' : check_male_guests,
                'check_actual_dest_daily_guest_female_count' : check_female_guests,
                'check_actual_dest_month_free_guest_count' : check_freeguests,
            })
                
            
    

    ######onchange #Generate Lines

    
    @api.onchange('pricerule_id', 'pricerule_start_date','pricerule_end_date', 'start_date', 'end_date', 'product_id', 'discount', 'applied_dest_price_monday', 'applied_dest_price_tuesday','applied_dest_price_wednesday','applied_dest_price_thursday','applied_dest_price_friday','applied_dest_price_saturday','applied_dest_price_sunday','applied_dest_custom_price_match','applied_unit_price')
    def _generate_destination_membership_lines(self):
        if self.end_date and self.start_date and self.end_date <= self.start_date:
            raise ValidationError('Date Error.')
        else:
            self._compute_duration()
            self._compute_pricing()
            self._compute_unit_price()
            
            self._compute_pricerule_dates()
            self._compute_pricerule_duration()
            self._compute_pricerule_pricing()
            self._compute_pricerule_unit_price()
            
            if self.end_date and self.start_date:
                if len(self.membership_lines) > 0:
                    self.write({'membership_lines': [(5, 0, 0)]})
                if self.dest_custom_price == "weekday_rate":
                    start_date = self.start_date
                    end_date = self.end_date
                    
                    start = start_date
                    periods = self.duration
                    daterange = []
                    for day in range(periods):
                        ratecase = 0
                        discountcase = 0
                        namecase = ''
                        datez = (start.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None) + timedelta(days = day)).date()
                        datey = start + timedelta(days = day)
                        if datez.weekday() == 0:
                            if self.pricerule_id and datez >= (((self.service_datetime_start or self.start_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0) and datez < (((self.service_datetime_end or self.end_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0):
                                if self.pricerule_type == 'price':
                                    ratecase = self.pricerule_dest_price_monday
                                    namecase = '[' + str(self.pricerule_id.name) + ']\n' + 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                else:
                                    ratecase = self.applied_dest_price_monday
                                    namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                    discountcase = self.pricerule_discount
                            else:
                                ratecase = self.applied_dest_price_monday
                                namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                        if datez.weekday() == 1:
                            if self.pricerule_id and datez >= (((self.service_datetime_start or self.start_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0) and datez < (((self.service_datetime_end or self.end_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0):
                                if self.pricerule_type == 'price':
                                    ratecase = self.pricerule_dest_price_tuesday
                                    namecase = '[' + str(self.pricerule_id.name) + ']\n' + 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                else:
                                    ratecase = self.applied_dest_price_tuesday
                                    namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                    discountcase = self.pricerule_discount
                            else:
                                ratecase = self.applied_dest_price_tuesday
                                namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                        if datez.weekday() == 2:
                            if self.pricerule_id and datez >= (((self.service_datetime_start or self.start_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0) and datez < (((self.service_datetime_end or self.end_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0):
                                if self.pricerule_type == 'price':
                                    ratecase = self.pricerule_dest_price_wednesday
                                    namecase = '[' + str(self.pricerule_id.name) + ']\n' + 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                else:
                                    ratecase = self.applied_dest_price_wednesday
                                    namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                    discountcase = self.pricerule_discount
                            else:
                                ratecase = self.applied_dest_price_wednesday
                                namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                        if datez.weekday() == 3:
                            if self.pricerule_id and datez >= (((self.service_datetime_start or self.start_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0) and datez < (((self.service_datetime_end or self.end_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0):
                                if self.pricerule_type == 'price':
                                    ratecase = self.pricerule_dest_price_thursday
                                    namecase = '[' + str(self.pricerule_id.name) + ']\n' + 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                else:
                                    ratecase = self.applied_dest_price_thursday
                                    namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                    discountcase = self.pricerule_discount
                            else:
                                ratecase = self.applied_dest_price_thursday
                                namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                        if datez.weekday() == 4:
                            if self.pricerule_id and datez >= (((self.service_datetime_start or self.start_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0) and datez < (((self.service_datetime_end or self.end_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0):
                                if self.pricerule_type == 'price':
                                    ratecase = self.pricerule_dest_price_friday
                                    namecase = '[' + str(self.pricerule_id.name) + ']\n' + 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                else:
                                    ratecase = self.applied_dest_price_friday
                                    namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                    discountcase = self.pricerule_discount
                            else:
                                ratecase = self.applied_dest_price_friday
                                namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                        if datez.weekday() == 5:
                            if self.pricerule_id and datez >= (((self.service_datetime_start or self.start_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0) and datez < (((self.service_datetime_end or self.end_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0):
                                if self.pricerule_type == 'price':
                                    ratecase = self.pricerule_dest_price_saturday
                                    namecase = '[' + str(self.pricerule_id.name) + ']\n' + 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                else:
                                    ratecase = self.applied_dest_price_saturday
                                    namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                    discountcase = self.pricerule_discount
                            else:
                                ratecase = self.applied_dest_price_saturday
                                namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                        if datez.weekday() == 6:
                            if self.pricerule_id and datez >= (((self.service_datetime_start or self.start_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0) and datez < (((self.service_datetime_end or self.end_date).replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)).date() or 0):
                                if self.pricerule_type == 'price':
                                    ratecase = self.pricerule_dest_price_sunday
                                    namecase = '[' + str(self.pricerule_id.name) + ']\n' + 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                else:
                                    ratecase = self.applied_dest_price_sunday
                                    namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))
                                    discountcase = self.pricerule_discount
                            else:
                                ratecase = self.applied_dest_price_sunday
                                namecase = 'From: ' + str(datez) + '\n' + 'To: ' + str(datez + relativedelta(days=1))

                        lines_dict = {
                                    'product_id' : self.product_id.id,
                                    'membership_id' : self.id,
                                    'name': namecase,
                                    'start_date': datey,
                                    'end_date': datey + relativedelta(days=1),
                                    'quantity': 1,
                                    'discount': self.discount + discountcase,
                                    'unit_price' : ratecase,
                                    'tax_id' : self.product_id.taxes_id,
                                }
                        
                        self.write({'membership_lines': [(0, 0, lines_dict)]})
                        


                if self.dest_custom_price == 'daily_rate':

                    if self.pricerule_id and self.pricerule_start_date and self.pricerule_end_date:
                        if self.start_date < self.pricerule_start_date:
                            lines_dict = {
                            'product_id' : self.product_id.id,
                            'membership_id' : self.id,
                            'name': 'From: ' + str(self.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + '\n' + 'To: ' + str(self.pricerule_start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                            'start_date': self.start_date,
                            'end_date': self.pricerule_start_date,
                            'quantity': self._compute_duration_vals(self.start_date, self.pricerule_start_date)[self.duration_unit],
                            'discount': self.discount,
                            'unit_price' : self.applied_dest_custom_price_match,
                            'tax_id' : self.product_id.taxes_id,
                                    }
                            self.write({'membership_lines': [(0, 0, lines_dict)]})

                        if self.pricerule_start_date < self.pricerule_end_date and self.pricerule_type == 'price':
                            lines_dict = {
                            'product_id' : self.product_id.id,
                            'membership_id' : self.id,
                            'name': '[ ' + str(self.pricerule_id.name) + ' | Unit: ' + str(self.pricerule_duration_unit) + ' ]' + '\n' + 'From: ' + str(self.pricerule_start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + '\n' + 'To: ' + str(self.pricerule_end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                            'start_date': self.pricerule_start_date,
                            'end_date': self.pricerule_end_date,
                            'quantity': self._compute_duration_vals(self.pricerule_start_date, self.pricerule_end_date)[self.pricerule_duration_unit],
                            'discount': self.discount,
                            'unit_price' : self.pricerule_unit_price_new / self.pricerule_duration,
                            'tax_id' : self.product_id.taxes_id,
                                    }
                            self.write({'membership_lines': [(0, 0, lines_dict)]}) 
                            
                        if self.pricerule_start_date < self.pricerule_end_date and self.pricerule_type == 'discount':
                            lines_dict = {
                            'product_id' : self.product_id.id,
                            'membership_id' : self.id,
                            'name': '[ ' + str(self.pricerule_id.name) + ' | Unit: ' + str(self.pricerule_duration_unit) + ' ]' + '\n' + 'From: ' + str(self.pricerule_start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + '\n' + 'To: ' + str(self.pricerule_end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                            'start_date': self.pricerule_start_date,
                            'end_date': self.pricerule_end_date,
                            'quantity': self._compute_duration_vals(self.pricerule_start_date, self.pricerule_end_date)[self.pricerule_duration_unit],
                            'discount': self.discount + self.pricerule_discount,
                            'unit_price' : self.applied_dest_custom_price_match,
                            'tax_id' : self.product_id.taxes_id,
                                    }
                            self.write({'membership_lines': [(0, 0, lines_dict)]}) 


                        if self.pricerule_end_date < self.end_date:
                            lines_dict = {
                            'product_id' : self.product_id.id,
                            'membership_id' : self.id,
                            'name': 'From: ' + str(self.pricerule_end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + '\n' + 'To: ' + str(self.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                            'start_date': self.pricerule_end_date,
                            'end_date': self.end_date,
                            'quantity': self._compute_duration_vals(self.pricerule_end_date, self.end_date)[self.duration_unit],
                            'discount': self.discount,
                            'unit_price' : self.applied_dest_custom_price_match,
                            'tax_id' : self.product_id.taxes_id,
                                    }
                            self.write({'membership_lines': [(0, 0, lines_dict)]})
                    
                            
                    else:
                        
                        lines_dict = {
                            'product_id' : self.product_id.id,
                            'membership_id' : self.id,
                            'name': 'From: ' + str(self.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + '\n' + 'To: ' + str(self.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                            'start_date': self.start_date,
                            'end_date': self.end_date,
                            'quantity': self.duration,
                            'discount': self.discount,
                            'unit_price' : self.applied_dest_custom_price_match,
                            'tax_id' : self.product_id.taxes_id,
                                    }
                        self.write({'membership_lines': [(0, 0, lines_dict)]})

                    


                if self.dest_custom_price == 'fixed':
                    
                    if self.pricerule_id and self.pricerule_start_date and self.pricerule_end_date:
                        if self.start_date < self.pricerule_start_date:
                            lines_dict = {
                            'product_id' : self.product_id.id,
                            'membership_id' : self.id,
                            'name': 'From: ' + str(self.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + '\n' + 'To: ' + str(self.pricerule_start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                            'start_date': self.start_date,
                            'end_date': self.pricerule_start_date,
                            'quantity': 1,
                            'discount': self.discount,
                            'unit_price' : self.applied_unit_price,
                            'tax_id' : self.product_id.taxes_id,
                                    }
                            self.write({'membership_lines': [(0, 0, lines_dict)]})

                        if self.pricerule_start_date < self.pricerule_end_date and self.pricerule_type == 'price':
                            lines_dict = {
                            'product_id' : self.product_id.id,
                            'membership_id' : self.id,
                            'name': '[ ' + str(self.pricerule_id.name) + ' ]\n' + 'From: ' + str(self.pricerule_start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + '\n' + 'To: ' + str(self.pricerule_end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                            'start_date': self.pricerule_start_date,
                            'end_date': self.pricerule_end_date,
                            'quantity': 1,
                            'discount': self.discount,
                            'unit_price' : self.pricerule_unit_price,
                            'tax_id' : self.product_id.taxes_id,
                                    }
                            self.write({'membership_lines': [(0, 0, lines_dict)]}) 
                        
                        if self.pricerule_start_date < self.pricerule_end_date and self.pricerule_type == 'discount':
                            lines_dict = {
                            'product_id' : self.product_id.id,
                            'membership_id' : self.id,
                            'name': '[ ' + str(self.pricerule_id.name) + ' ]\n' + 'From: ' + str(self.pricerule_start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + '\n' + 'To: ' + str(self.pricerule_end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                            'start_date': self.pricerule_start_date,
                            'end_date': self.pricerule_end_date,
                            'quantity': 1,
                            'discount': self.discount + self.pricerule_discount,
                            'unit_price' : self.applied_unit_price,
                            'tax_id' : self.product_id.taxes_id,
                                    }
                            self.write({'membership_lines': [(0, 0, lines_dict)]}) 


                        if self.pricerule_end_date < self.end_date:
                            lines_dict = {
                            'product_id' : self.product_id.id,
                            'membership_id' : self.id,
                            'name': 'From: ' + str(self.pricerule_end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + '\n' + 'To: ' + str(self.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                            'start_date': self.pricerule_end_date,
                            'end_date': self.end_date,
                            'quantity': 1,
                            'discount': self.discount,
                            'unit_price' : self.applied_unit_price,
                            'tax_id' : self.product_id.taxes_id,
                                    }
                            self.write({'membership_lines': [(0, 0, lines_dict)]})       
                
                            
                    else:
                    
                        lines_dict = {
                            'product_id' : self.product_id.id,
                            'membership_id' : self.id,
                            'name': 'From: ' + str(self.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + '\n' + 'To: ' + str(self.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                            'start_date': self.start_date,
                            'end_date': self.end_date,
                            'quantity': 1,
                            'discount': self.discount,
                            'unit_price' : self.applied_unit_price,
                            'tax_id' : self.product_id.taxes_id,
                                    }
                        
                        
                        self.write({'membership_lines': [(0, 0, lines_dict)]})
                    
                    
                
       


                    
                    
                    
    ######ACTION Functions                
                    
    def cancel_order(self):
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                        ('summary','=','Request for Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.action_feedback(feedback='Cancelled')
                    
        return self.write({'previous_state':self.state,'state': 'cancel'})
    
    def reject_order(self):
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                        ('summary','=','Request for Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.action_feedback(feedback='Rejected')
                    
        return self.write({'previous_state':self.state,'state': 'new'})
    
    
    def revert_order_draft(self):
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                        ('summary','=','Request for Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.action_feedback(feedback='Cancelled')
        
        for record in self:
            record.check_approval = False
        
            if record.applied_dest_price_monday != record.dest_price_monday:
                record.check_applied_dest_price_monday = "Exception"
                record.check_approval = True
            if record.applied_dest_price_tuesday != record.dest_price_tuesday:
                record.check_applied_dest_price_tuesday = "Exception"
                record.check_approval = True
            if record.applied_dest_price_wednesday != record.dest_price_wednesday:
                record.check_applied_dest_price_wednesday = "Exception"
                record.check_approval = True
            if record.applied_dest_price_thursday != record.dest_price_thursday:
                record.check_applied_dest_price_thursday = "Exception"
                record.check_approval = True
            if record.applied_dest_price_friday != record.dest_price_friday:
                record.check_applied_dest_price_friday = "Exception"
                record.check_approval = True
            if record.applied_dest_price_saturday != record.dest_price_saturday:
                record.check_applied_dest_price_saturday = "Exception"
                record.check_approval = True
            if record.applied_dest_price_sunday != record.dest_price_sunday:
                record.check_applied_dest_price_sunday = "Exception"
                record.check_approval = True
            if record.applied_unit_price != record.unit_price:
                record.check_applied_unit_price = "Exception"
                record.check_approval = True
            if record.applied_dest_custom_price_match != record.dest_custom_price_match:
                record.check_applied_dest_custom_price_match = "Exception"
                record.check_approval = True
            if record.discount != 0:
                record.check_discount = "Exception"
                record.check_approval = True
            if record.actual_dest_member_count > record.dest_member_count:
                record.check_actual_dest_member_count = "Exception"
                record.check_approval = True
            if record.actual_dest_member_male_count > record.dest_member_male_count:
                record.check_actual_dest_member_male_count = "Exception"
                record.check_approval = True
            if record.actual_dest_member_female_count > record.dest_member_female_count:
                record.check_actual_dest_member_female_count = "Exception"
                record.check_approval = True
            if record.applied_payment_term_id != record.payment_term_id:
                record.check_applied_payment_term_id = "Exception"
                record.check_approval = True
            if record.actual_dest_daily_guest_count != record.dest_daily_guest_count:
                record.check_actual_dest_daily_guest_count = "Exception"
                record.check_approval = True
            if record.actual_dest_daily_guest_male_count != record.dest_daily_guest_male_count:
                record.check_actual_dest_daily_guest_male_count = "Exception"
                record.check_approval = True
            if record.actual_dest_daily_guest_female_count != record.dest_daily_guest_female_count:
                record.check_actual_dest_daily_guest_female_count = "Exception"
                record.check_approval = True
            if record.actual_dest_month_free_guest_count != record.dest_month_free_guest_count:
                record.check_actual_dest_month_free_guest_count = "Exception"
                record.check_approval = True

        
        
        return self.write({'previous_state':self.state,'state': 'new'})
    
    def approve_order(self):
        is_manager = (True if self.env.user.id in self.product_id.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'manager').user_id.ids else False) 
        
        if is_manager:
            getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                        ('summary','=','Request for Approval'),
                        ('activity_type_id','=',4)
            ])
            if getrequests:
                getrequests.action_feedback(feedback='Approved')

            if self.previous_state != 'new':
                prevstat = self.previous_state
            else:
                prevstat = 'approved'

            if self.check_applied_dest_price_monday == "Exception":
                self.check_applied_dest_price_monday = "Approved"
            if self.check_applied_dest_price_tuesday == "Exception":
                self.check_applied_dest_price_tuesday = "Approved"
            if self.check_applied_dest_price_wednesday == "Exception":
                self.check_applied_dest_price_wednesday = "Approved"
            if self.check_applied_dest_price_thursday == "Exception":
                self.check_applied_dest_price_thursday = "Approved"
            if self.check_applied_dest_price_friday == "Exception":
                self.check_applied_dest_price_friday = "Approved"
            if self.check_applied_dest_price_saturday == "Exception":
                self.check_applied_dest_price_saturday = "Approved"
            if self.check_applied_dest_price_sunday == "Exception":
                self.check_applied_dest_price_sunday = "Approved"
            if self.check_applied_unit_price == "Exception":
                self.check_applied_unit_price = "Approved"
            if self.check_applied_dest_custom_price_match == "Exception":
                self.check_applied_dest_custom_price_match = "Approved"
            if self.check_discount == "Exception":
                self.check_discount = "Approved"
            if self.check_actual_dest_member_count == "Exception":
                self.check_actual_dest_member_count = "Approved"
            if self.check_actual_dest_member_male_count == "Exception":
                self.check_actual_dest_member_male_count = "Approved"
            if self.check_actual_dest_member_female_count == "Exception":
                self.check_actual_dest_member_female_count = "Approved"
            if self.check_applied_payment_term_id == "Exception":
                self.check_applied_payment_term_id = "Approved"

            if self.check_actual_dest_daily_guest_count == "Exception":
                self.check_actual_dest_daily_guest_count = "Approved"
            if self.check_actual_dest_daily_guest_male_count == "Exception":
                self.check_actual_dest_daily_guest_male_count = "Approved"
            if self.check_actual_dest_daily_guest_female_count == "Exception":
                self.check_actual_dest_daily_guest_female_count = "Approved"
            if self.check_actual_dest_month_free_guest_count == "Exception":
                self.check_actual_dest_month_free_guest_count = "Approved"

            if self.members_lines.search([('state','=','pending')]):
                self.members_lines.search([('state','=','pending')]).write({'state':'active'})

            return self.write({'previous_state':self.state,'state': prevstat,'check_approval':0})

        else:
            

            for record in self:

                getrequests = self.env['mail.activity'].search([
                            ('res_id','=',record.id),
                            ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                            ('summary','=','Request for Approval'),
                            ('activity_type_id','=',4)
                ])
                if getrequests:
                    getrequests.action_feedback(feedback='Authorized')

            managers = self.product_id.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'manager')

            for manager in managers:
                todos = {
                    'res_id': self.id,
                    'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id,
                    'user_id': manager.user_id.id,
                    'summary': 'Request for Approval',
                    'note': 'Please review the highlighted Exception(s)',
                    'activity_type_id': 4,
                    'date_deadline': datetime.date.today(),
                    }

                sfa = self.env['mail.activity'].create(todos)

            
    def pick_order(self):
        for record in self:
            start_date_date = (record.start_date + relativedelta(hours=3)).date()
            now_date_date = (fields.Datetime.now() + relativedelta(hours=3)).date()
            if now_date_date >= start_date_date:
                record.previous_state = record.state
                record.state = 'active'
                getrequests = self.env['mail.activity'].search([
                            ('res_id','=',record.id),
                            ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                            ('summary','=','Check-In Rental'),
                            ('activity_type_id','=',4)
                ])
                if getrequests:
                    getrequests.action_feedback(feedback='Checked-In')
                getrequests = self.env['mail.activity'].search([
                            ('res_id','=',record.id),
                            ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                            ('summary','=','Request Check-In'),
                            ('activity_type_id','=',4)
                ])
                if getrequests:
                    getrequests.action_feedback(feedback='Checked-In')
            else:
                raise UserError("Cannot check-in before Start Date")
                
    def request_checkin(self):
        for record in self:
            getrequests = self.env['mail.activity'].search([
                                ('res_id','=',record.id),
                                ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                                ('summary','=','Request Check-In'),
                                ('activity_type_id','=',4)
                    ])
            if getrequests:
                getrequests.unlink()
            
        for manager in self.product_id.dest_id.manager_ids:
            todos = {
                'res_id': self.id,
                'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id,
                'user_id': manager.user_id.id,
                'summary': 'Request Check-In',
                'note': 'Please review rental order for Check-In',
                'activity_type_id': 4,
                'date_deadline': datetime.date.today(),
                }

            sfa = self.env['mail.activity'].create(todos)
             
    
    def return_order(self):
        for record in self:
            record.previous_state = record.state
            record.state = 'checked-out'
            getrequests = self.env['mail.activity'].search([
                        ('res_id','=',record.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                        ('summary','=','Check-Out Rental'),
                        ('activity_type_id','=',4)
            ])
            if getrequests:
                getrequests.action_feedback(feedback='Checked-out')
            
            if record.amount_gt_invoice and not record.no_invoice:
                record.recalc_order()
            
            
            
            
    def recalc_order(self):
        for record in self:
            
            record.update_so()
            currinvs = record.invoice_ids.filtered(lambda r: r.state =='posted')
            
            
            if currinvs:
                currinvs.sudo().button_draft()
                currinvs.sudo().button_cancel()
            
            currso = record.so_ids.filtered(lambda r: r.state != 'cancel')
            
            if currso and currso[0].state in ['draft','sent']:
                currso[0].sudo().action_confirm()
            if currso and currso[0].invoice_status == 'to invoice':
                currso[0].sudo()._create_invoices(final=True, grouped=True).action_post()
            
            
    
    ### refund rental
    
    @api.onchange('total_amount_total','total_invoiced')
    @api.depends('total_amount_total','total_invoiced')
    def compute_amount_lt_invoice(self):
        for record in self:
            if record.total_invoiced:
                if round(record.total_amount_total, 2) < round(record.total_invoiced, 2):
                    record.amount_lt_invoice = 1
                else:
                    record.amount_lt_invoice = 0
            else:
                record.amount_lt_invoice = 0
                
    @api.onchange('total_amount_total','total_invoiced')
    @api.depends('total_amount_total','total_invoiced')
    def compute_amount_gt_invoice(self):
        for record in self:
            if record.total_invoiced:
                if round(record.total_amount_total,2) > round(record.total_invoiced,2):
                    record.amount_gt_invoice = 1
                else:
                    record.amount_gt_invoice = 0
            else:
                record.amount_gt_invoice = 0
                
    def request_rental_refund(self):
        for record in self:
            record.check_rental_refund_approval = 1
            for manager in self.product_id.dest_id.manager_ids:
                todos = {
                    'res_id': self.id,
                    'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id,
                    'user_id': manager.user_id.id,
                    'summary': 'Rental Refund Approval',
                    'note': 'Request to refund total of ' + str('{:,.2f}'.format(record.total_invoiced - record.amount_total)) + ' ' + record.currency_id.symbol,
                    'activity_type_id': 4,
                    'date_deadline': datetime.date.today(),
                    }

                sfa = self.env['mail.activity'].create(todos)
    
    
    def approve_rental_refund(self):
        for record in self:
            record.recalc_order()
            record.check_rental_refund_approval = 0
            getrequests = self.env['mail.activity'].search([
                        ('res_id','=',record.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                        ('summary','=','Rental Refund Approval'),
                        ('activity_type_id','=',4)
            ])
            if getrequests:
                getrequests.action_feedback(feedback='Approved')
        
    def reject_rental_refund(self):
        for record in self:
            record.check_rental_refund_approval = 0
            getrequests = self.env['mail.activity'].search([
                        ('res_id','=',record.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                        ('summary','=','Rental Refund Approval'),
                        ('activity_type_id','=',4)
            ])
            if getrequests:
                getrequests.action_feedback(feedback='Rejected')
        
        
                
                
            
    def close_order(self):
        for record in self:
            if not record.is_manager and (record.total_due != 0 or record.total_deposit_due != 0):
                raise UserError("Cannot be marked as Done while there is outstanding balance")
            else:
                self.previous_state = self.state
                self.state = 'done'

                
    def hold_order(self):
        self.previous_state = self.state
        self.state = 'hold'
        
    def reactivate_order(self):
        prevstat = self.previous_state
        self.previous_state = self.state
        self.state = prevstat
            
        
    
    def confirm_order(self):
        for record in self:
            record_ids = record.search([('start_date', '<', record.end_date), ('end_date', '>', record.start_date), ('product_id', '=', record.product_id.id), ('id', '!=', record.id),('state','not in',['new','cancel','done','checked-out'])])
            
            if len(record_ids) >= record.product_id.dest_quantity:
                raise ValidationError("Product not available on these dates")
            else:   
                record.previous_state = self.state
                record.state = 'confirmed'
                
                
                    
                if record.dest_invoice_policy == 'order': 

                    record.create_deposit()
                    record.recalc_order()

                        

                else:

                    record.create_deposit()
                    record.update_so()
                    
                    

            

            
            todos = {
            'res_id': self.id,
            'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id,
            'user_id': self.user_id.id,
            'summary': 'Check-In Rental',
            'note': 'This is a reminder to Check-In: ' + self.name,
            'activity_type_id': 4,
            'date_deadline': self.start_date,
            }

            sfa = self.env['mail.activity'].create(todos)  
                
            


        
    def request_approval(self):
        self.previous_state = self.state
        self.state = 'pending'
        
        for record in self:
            
            getrequests = self.env['mail.activity'].search([
                        ('res_id','=',record.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                        ('summary','=','Request for Approval'),
                        ('activity_type_id','=',4)
            ])
            if getrequests:
                getrequests.unlink()
                
        check_authorizer = self.product_id.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'authorizer')
        
        if check_authorizer:
            managers = check_authorizer
        else:
            managers = self.product_id.dest_id.manager_ids
        
        for manager in managers:
            todos = {
                'res_id': self.id,
                'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id,
                'user_id': manager.user_id.id,
                'summary': 'Request for Approval',
                'note': 'Please review the highlighted Exception(s)',
                'activity_type_id': 4,
                'date_deadline': datetime.date.today(),
                }

            sfa = self.env['mail.activity'].create(todos)
       
    
                
    

    
                
                
    def action_view_guest(self):
        self.ensure_one()
        treeview = self.env.ref("destinations.destination_guest_list_view").id
        formview = self.env.ref("destinations.destination_guest_form_view").id
        searchview = self.env.ref("destinations.destination_guest_search_view").id
        result = {
            "name": "Guest Registry",
            "type": "ir.actions.act_window",
            "res_model": "destination.guest",
            "domain": [('membership_id', '=', self.id)],
            "context": {'default_membership_id':self.id},
            'views' : [(treeview,'tree'),(formview,'form'),(searchview,'search')],
            "view_mode": "tree,form,search",
             }
        return result
               
    def action_view_member_activity(self):
        self.ensure_one()
        result = {
            "name": "Member Registry",
            "type": "ir.actions.act_window",
            "res_model": "destination.membership.member.activity",
            "domain": [('membership_id', '=', self.id)],
            "context": {'default_membership_id':self.id},
            "view_mode": "tree",
             }
        return result

        
        
        
        
        
        
        
        
        


            
            
            

    

    
    
    ## VIEW Functions

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

        context = {
            'default_move_type': 'out_invoice',
        }
        if len(self) == 1:
            context.update({
                'default_partner_id': self.partner_id.id,
                'default_partner_shipping_id': self.partner_id.id,
                'default_invoice_payment_term_id': self.applied_payment_term_id.id or self.env['account.move'].default_get(['invoice_payment_term_id']).get('invoice_payment_term_id'),
                'default_invoice_origin': self.name,
                'default_user_id': self.env.user.id,
            })
        action['context'] = context
        return action
    
    def action_view_member(self):
        self.ensure_one()
        result = {
            "name": "Members",
            "type": "ir.actions.act_window",
            "res_model": "destination.membership.member",
            "domain": [('membership_id','=', self.id)],
            "context": {'default_membership_id':self.id, 'default_lock_membership_id':True,'default_dest_id':self.dest_id.id, 'default_lock_dest_id':True},
            "view_mode": "tree,form,search",
             }
        return result
    
    
    

    def action_view_so(self):
        self.ensure_one()
        result = {
            "name": "Sales Orders",
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "domain": [('rental_id','=', self.id)],
            "view_mode": "tree,form,search",
             }
        return result
    
    def action_view_deposit(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.deposit_id.id,
            "view_mode": "form",
             }
        return result
    
    
    def action_quotation_send(self):
        ''' Opens a wizard to compose an email, with relevant mail template loaded by default '''
        self.ensure_one()
        template_id = self.env.ref("destinations.destination_membership_sale_order_mail_template").id
        lang = self.env.context.get('lang')
        template = self.env['mail.template'].browse(template_id)
        if template.lang:
            lang = template._render_lang(self.ids)[self.id]
            
        currso = self.so_ids.filtered(lambda r: r.state != 'cancel')
                
        ctx = {
            'default_model': 'sale.order',
            'default_dest_source' : 'rental',
            'default_dest_id': self.dest_id.id,
            'default_res_id': currso[0].id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'custom_layout': "destinations.destination_membership_email_template",
            'proforma': self.env.context.get('proforma', False),
            'force_email': True,
            'model_description': currso[0].with_context(lang=lang).type_name,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }
    
    
    