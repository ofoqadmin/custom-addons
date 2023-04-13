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



class MembershipLines(models.Model):
    _name = "destination.membership.line"
    _description = "Rental Lines"
    
    code = fields.Char(string='Code', size=4)
    name = fields.Char(string='Name', translate=True)
    active = fields.Boolean(string="Active", tracking=True, default=True)
    membership_id = fields.Many2one('destination.membership', string='Rental', ondelete='cascade')
    dest_id = fields.Many2one('destination.destination', string='Entity', related='membership_id.dest_id')
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict')
    start_date = fields.Datetime(string='Start Date')
    end_date = fields.Datetime(string='End Date')
    state = fields.Char(string='Status')
    quantity = fields.Integer(string='Quantity')
    unit = fields.Many2one('uom.uom', string='Unit', ondelete='restrict', related='product_id.uom_id', readonly=True)
    discount = fields.Float(string='Discount')
    unit_price = fields.Float(string='Unit Price', digits='Product Price')
    tax_id = fields.Many2many('account.tax', string='Taxes')
    currency_id = fields.Many2one(related='product_id.currency_id', depends=['product_id.currency_id'], store=True, string='Currency', readonly=True)

    price_subtotal = fields.Monetary(compute='_compute_amount', string='Untaxed', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
            
            
    @api.depends('quantity', 'unit', 'discount', 'unit_price', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.quantity * line.unit_price * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.product_id.currency_id, line.unit.id, product=line.product_id, partner=line.membership_id.partner_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })