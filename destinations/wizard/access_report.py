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



class AccessReport(models.TransientModel):
    _name = 'destination.access.report'
    _description = 'Access Report'
    
    date = fields.Datetime(string="Date")
    source_document = fields.Reference (selection = [('destination.guest', 'Guest'),('destination.membership.member.activity', 'Member')],string = "Source Document")
    source_type = fields.Selection([('guest', 'Guest Access'), ('member', 'Member Access')], string="Revenue Source")
    partner_id = fields.Many2one('res.partner', string='Customer')
    amount = fields.Monetary(string='Amount')
    access_payment_method_id = fields.Many2one('destination.payment.method',string='Payment Method')   
    
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id', store=True, string='Currency')
    report_user = fields.Many2one('res.users', string='Report User', default=lambda self: self.env.user)

    product_id = fields.Many2one('product.product', string='Product', store=True)
    product_categ_id = fields.Many2one('product.category', "Product Category", related="product_id.categ_id", store=True)
    
    dest_id = fields.Many2one('destination.destination', string='Entity', store=True)
    
    membership_id = fields.Many2one('destination.membership', string='Rental')
    name = fields.Text(string='Reference')
    
    membership_state = fields.Selection([('new', 'Draft'),('pending', 'Pending Approval'),('approved', 'Approved'),('confirmed', 'Confirmed'),('active', 'Active'),('hold', 'On Hold'),('checked-out', 'Checked-Out'),('expired', 'Expired'),('done', 'Done'),('cancel','Cancelled'),('late','Late')], string='Status', related="membership_id.state", store=True)
        
    processin_date = fields.Datetime(string="Process-In Date")
    checkin_date = fields.Datetime(string="Check-In Date")
    checkout_date = fields.Datetime(string="Check-Out Date")
    close_date = fields.Datetime(string="Close Date")
    
    registration_user_id = fields.Many2one('res.users', string='Registration User', index=True)
    processin_user_id = fields.Many2one('res.users', string='Process-In User', index=True)
    checkin_user_id = fields.Many2one('res.users', string='Check-In User', index=True)
    checkout_user_id = fields.Many2one('res.users', string='Check-Out User', index=True)