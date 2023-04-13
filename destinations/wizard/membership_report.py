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



class MembershipReport(models.TransientModel):
    _name = 'destination.membership.report'
    _description = 'Membership Report'
    
    membership_id = fields.Many2one('destination.membership', string='Rental')
    
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id', depends=['product_id.currency_id'], store=True, string='Currency')
    report_user = fields.Many2one('res.users', string='Report User', index=True, default=lambda self: self.env.user)
    
    name = fields.Text(string='Reference', compute="compute_stats", store=True)
    state = fields.Selection([('new', 'Draft'),('pending', 'Pending Approval'),('approved', 'Approved'),('confirmed', 'Confirmed'),('active', 'Active'),('hold', 'On Hold'),('checked-out', 'Checked-Out'),('expired', 'Expired'),('done', 'Done'),('cancel','Cancelled'),('late','Late')], string='Status', compute="compute_stats", store=True)
    members_lines = fields.One2many('destination.membership.member',  string = 'Members', compute="compute_stats")
    total_members = fields.Integer('Total Members', compute="compute_stats", store=True)
    total_invoiced = fields.Monetary(string="Total Invoiced", compute="compute_stats", store=True)
    total_invoiced_untaxed = fields.Monetary(string="Total Untaxed", compute="compute_stats", store=True)
    total_due = fields.Monetary(string="Total Due", compute="compute_stats", store=True)
    total_sales = fields.Monetary(string="Total Sales", compute="compute_stats", store=True)
    total_deposit = fields.Monetary(string="Security Deposit", compute="compute_stats", store=True)
    total_deposit_due = fields.Monetary(string="Security Deposit Due", compute="compute_stats", store=True)
    invoice_count = fields.Integer(string='Invoice Count', compute="compute_stats", store=True)
    guest_ids = fields.One2many('destination.guest', string = 'Guest Access', compute="compute_stats")
    guest_count = fields.Integer(string='Guest Access', compute="compute_stats", store=True)
    guest_total_invoiced = fields.Monetary(string="Guest Invoiced", compute="compute_stats", store=True)
    guest_total_untaxed = fields.Monetary(string="Guest Untaxed", compute="compute_stats", store=True)
    guest_total_due = fields.Monetary( string="Guest Dues", compute="compute_stats", store=True)
    member_activity_ids = fields.One2many('destination.membership.member.activity',  string = 'Member Access', compute="compute_stats")
    member_activity_count = fields.Integer(string='Member Access', compute="compute_stats", store=True)
    member_total_invoiced = fields.Monetary(string="Member Invoiced", compute="compute_stats", store=True)
    member_total_untaxed = fields.Monetary(string="Member Untaxed", compute="compute_stats", store=True)
    member_total_due = fields.Monetary(string="Member Dues", compute="compute_stats", store=True)
    date_order = fields.Datetime(string='Order Date', compute="compute_stats", store=True)
    date_expiry = fields.Datetime(string='Expiration Date', compute="compute_stats", store=True)
    start_date = fields.Datetime(string="Start", compute="compute_stats", store=True)
    end_date = fields.Datetime(string="End", compute="compute_stats", store=True)
    dest_checkin_time = fields.Datetime(string="Check-In Time", compute="compute_stats", store=True)
    dest_checkout_time = fields.Datetime(string="Check-Out Time", compute="compute_stats", store=True)
    dest_id = fields.Many2one('destination.destination', string='Entity', compute="compute_stats", store=True)
    product_id = fields.Many2one('product.product', string='Product', compute="compute_stats", store=True)
    product_tmpl_id = fields.Many2one('product.template', related='product_id.product_tmpl_id')
    product_id_code = fields.Char(string='Product Code', compute="compute_stats", store=True)
    product_id_dest_code = fields.Char(string='Entity Code', compute="compute_stats", store=True)  
    partner_id = fields.Many2one('res.partner', string='Customer', compute="compute_stats", store=True)
    referral_partner_id = fields.Many2one('res.partner', string='Referred By', compute="compute_stats", store=True)
    product_categ_id = fields.Many2one('product.category', "Product Category", compute="compute_stats", store=True)
    dest_product_group = fields.Selection([('accommodation', 'Rental'), ('membership', 'Membership'), ('access', 'Access'), ('others', 'Others')], string="Product Group", compute="compute_stats", store=True)
    dest_custom_price = fields.Selection([('weekday_rate', 'Variable Weekday Rate'), ('daily_rate', 'Variable Daily Rate'), ('fixed', 'Fixed Rate')], string="Pricing Type", compute="compute_stats", store=True)
    actual_dest_member_count = fields.Integer(string="Applied Max. Capacity", compute="compute_stats", store=True)  
    actual_dest_member_male_count = fields.Integer(string="Applied Male Cap", compute="compute_stats", store=True)
    actual_dest_member_female_count = fields.Integer(string="Applied Female Cap", compute="compute_stats", store=True)
    actual_dest_daily_guest_count = fields.Integer(string="Applied Guests / Day", compute="compute_stats", store=True)
    actual_dest_daily_guest_male_count = fields.Integer(string="Applied Male Guests / Day", compute="compute_stats", store=True) 
    actual_dest_daily_guest_female_count = fields.Integer(string="Applied Female Guests / Day", compute="compute_stats", store=True) 
    actual_dest_month_free_guest_count = fields.Integer(string="Applied Free Guests / Month", compute="compute_stats", store=True) 
    so_id = fields.Many2one('sale.order', string='Sale Order', compute="compute_stats", store=True)
    so_state = fields.Selection([('draft', 'Quotation'),('sent', 'Quotation Sent'),('sale', 'Sales Order'),('done', 'Locked'),('cancel', 'Cancelled'),], string='SO Status', compute="compute_stats", store=True)
    membership_lines = fields.One2many('destination.membership.line', 'membership_id', string = 'Rental Lines', compute="compute_stats")
    amount_untaxed = fields.Monetary(string='Untaxed Amount', compute="compute_stats", store=True)
    amount_tax = fields.Monetary(string='Taxes Amount', compute="compute_stats", store=True)
    amount_total = fields.Monetary(string='Total Amount', compute="compute_stats", store=True)
    user_id = fields.Many2one('res.users', string='Salesperson', compute="compute_stats", store=True)
    
    
    
    @api.depends('membership_id')
    def compute_stats(self):
        for record in self:
            record.name = record.membership_id.name
            record.user_id = record.membership_id.user_id
            record.state = record.membership_id.state
            record.members_lines = record.membership_id.members_lines
            record.total_members = record.membership_id.total_members
            record.total_invoiced = record.membership_id.total_invoiced
            record.total_invoiced_untaxed = record.membership_id.total_invoiced_untaxed
            record.total_due = record.membership_id.total_due
            record.total_sales = record.membership_id.total_sales
            record.total_deposit = record.membership_id.total_deposit
            record.total_deposit_due = record.membership_id.total_deposit_due
            record.invoice_count = record.membership_id.invoice_count
            record.guest_ids = record.membership_id.guest_ids
            record.guest_count = record.membership_id.guest_count
            record.guest_total_invoiced = record.membership_id.guest_total_invoiced
            record.guest_total_untaxed = record.membership_id.guest_total_untaxed
            record.guest_total_due = record.membership_id.guest_total_due
            record.member_activity_ids = record.membership_id.member_activity_ids
            record.member_activity_count = record.membership_id.member_activity_count
            record.member_total_invoiced = record.membership_id.member_total_invoiced
            record.member_total_untaxed = record.membership_id.member_total_untaxed
            record.member_total_due = record.membership_id.member_total_due
            record.date_order = record.membership_id.date_order
            record.date_expiry = record.membership_id.date_expiry
            record.start_date = record.membership_id.start_date
            record.end_date = record.membership_id.end_date
            record.dest_checkin_time = record.membership_id.dest_checkin_time
            record.dest_checkout_time = record.membership_id.dest_checkout_time
            record.dest_id = record.membership_id.dest_id
            record.product_id = record.membership_id.product_id
            record.product_tmpl_id = record.membership_id.product_tmpl_id
            record.product_id_code = record.membership_id.product_id_code
            record.product_id_dest_code = record.membership_id.product_id_dest_code
            record.partner_id = record.membership_id.partner_id
            record.referral_partner_id = record.membership_id.referral_partner_id
            record.product_categ_id = record.membership_id.product_categ_id
            record.dest_product_group = record.membership_id.dest_product_group
            record.dest_custom_price = record.membership_id.dest_custom_price
            record.actual_dest_member_count = record.membership_id.actual_dest_member_count
            record.actual_dest_member_male_count = record.membership_id.actual_dest_member_male_count
            record.actual_dest_member_female_count = record.membership_id.actual_dest_member_female_count
            record.actual_dest_daily_guest_count = record.membership_id.actual_dest_daily_guest_count
            record.actual_dest_daily_guest_male_count = record.membership_id.actual_dest_daily_guest_male_count
            record.actual_dest_daily_guest_female_count = record.membership_id.actual_dest_daily_guest_female_count
            record.actual_dest_month_free_guest_count = record.membership_id.actual_dest_month_free_guest_count
            record.so_id = record.membership_id.so_id
            record.so_state = record.membership_id.so_state
            record.membership_lines = record.membership_id.membership_lines
            record.amount_untaxed = record.membership_id.amount_untaxed
            record.amount_tax = record.membership_id.amount_tax
            record.amount_total = record.membership_id.amount_total
            record.user_id = record.membership_id.user_id
        