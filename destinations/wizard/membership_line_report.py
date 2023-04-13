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



class MembershipLineReport(models.TransientModel):
    _name = 'destination.membership.line.report'
    _description = 'Profitability Report'
    
    start_date = fields.Date("Date")
    end_date = fields.Date("End Date", store=False)
    source_document = fields.Reference (selection = [('destination.guest', 'Guest'),('destination.membership.member.activity', 'Member'),('destination.membership.line', 'Rental Line'),('destination.membership.extra.line', 'Extra Line'),('sale.order.line', 'SO Line')],string = "Source Document")
    source_type = fields.Selection([('membership', 'Rentals'), ('guest', 'Guest Access'), ('member', 'Member Access'),('others','Others')], string="Revenue Source")
    partner_id = fields.Many2one('res.partner', string='Customer')
    amount = fields.Monetary(string='Amount')
    
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id', store=True, string='Currency')
    report_user = fields.Many2one('res.users', string='Report User', default=lambda self: self.env.user)

    product_id = fields.Many2one('product.product', string='Product', store=True)
    product_categ_id = fields.Many2one('product.category', "Product Category", related="product_id.categ_id", store=True)
    dest_product_group = fields.Selection([('accommodation', 'Rental'), ('membership', 'Membership'), ('access', 'Access'), ('others', 'Others')], string="Product Group", related='product_id.dest_product_group',  store=True)
    dest_custom_price = fields.Selection([('weekday_rate', 'Variable Weekday Rate'), ('daily_rate', 'Variable Daily Rate'), ('fixed', 'Fixed Rate')], string="Pricing Type", related='product_id.dest_custom_price',   store=True)
    
    dest_id = fields.Many2one('destination.destination', string='Entity', store=True)
    
    membership_id = fields.Many2one('destination.membership', string='Rental')
    name = fields.Text(string='Reference', related="membership_id.name", store=True)
    user_id = fields.Many2one('res.users', string='Salesperson')
    membership_state = fields.Selection([('new', 'Draft'),('pending', 'Pending Approval'),('approved', 'Approved'),('confirmed', 'Confirmed'),('active', 'Active'),('hold', 'On Hold'),('checked-out', 'Checked-Out'),('expired', 'Expired'),('done', 'Done'),('cancel','Cancelled'),('late','Late')], string='Status', related="membership_id.state", store=True)

    units_available = fields.Float(string="Units Available", store=False)
    time_available = fields.Float(string="Time Available", store=False)
    days_available = fields.Float(string="Available")
    
    members_available = fields.Float(string="Members Available", store=False)
    guests_available = fields.Float(string="Guests Available", store=False)
    
    time_occupied = fields.Float(string="Time Occupied", store=False)
    days_occupied = fields.Float(string="Occupied")
    
    
    