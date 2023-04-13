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



class DestinationPriceLines(models.Model):
    _name = "destination.price.lines"
    _description = "Price Rule Line"
    _order = 'price'   
  
    pricerule_id = fields.Many2one('destination.price', string="Price Rule")
    dest_id = fields.Many2one('destination.destination', string='Entity', compute='get_dest_id')
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    
    
    membership_id = fields.Many2one('destination.membership', ondelete='cascade', string="Rental")
    
    duration = fields.Integer(
        string="Duration", required=True,
        help="Minimum duration before this rule is applied. If set to 0, it represents a fixed rental price.")
    
    unit = fields.Selection([("minute","Minutes"), ("hour", "Hours"), ("day", "Days"), ("week", "Weeks"), ("month", "Months")], string="Unit", required=True, default='day')

    price = fields.Monetary(string="Price", required=True, default=1.0)
    currency_id = fields.Many2one(
        'res.currency', 'Currency',
        default=lambda self: self.env.company.currency_id.id,
        required=True)
    
    product_template_id = fields.Many2one('product.template', string='Product Templates', related='pricerule_id.product_id.product_tmpl_id')


    product_variant_ids = fields.Many2many(
        'product.product', string="Product Variants",
        help="Select Variants of the Product for which this rule applies."
        "\n Leave empty if this rule applies for any variant of this template.")
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    company_id = fields.Many2one('res.company', related='pricelist_id.company_id')

    @api.depends('pricerule_id','membership_id')
    def get_dest_id(self):
        for record in self:
            if record.pricerule_id:
                record.dest_id = record.pricerule_id.dest_id.id
            if record.membership_id:
                record.dest_id = record.membership_id.dest_id.id
    
    @api.onchange('pricelist_id')
    def _onchange_pricelist_id(self):
        for pricing in self.filtered('pricelist_id'):
            pricing.currency_id = pricing.pricelist_id.currency_id

    def _compute_price(self, duration, unit):
        """Compute the price for a specified duration of the current pricing rule.

        :param float duration: duration in hours
        :param str unit: duration unit (hour, day, week)
        :return float: price
        """
        self.ensure_one()
        if duration <= 0 or self.duration <= 0:
            return self.price
        if unit != self.unit:
            if unit == 'month' or self.unit == 'month':
                raise ValidationError(_("Conversion between Months and another duration unit are not supported!"))
            converted_duration = math.ceil((duration * PERIOD_RATIO[unit]) / (self.duration * PERIOD_RATIO[self.unit]))
        else:
            converted_duration = math.ceil(duration / self.duration)
        return self.price * converted_duration

    def name_get(self):
        result = []
        uom_translation = dict()
        for key, value in self._fields['unit']._description_selection(self.env):
            uom_translation[key] = value
        for pricing in self:
            label = ""
            if pricing.currency_id.position == 'before':
                label += pricing.currency_id.symbol + str(pricing.price)
            else:
                label += str(pricing.price) + pricing.currency_id.symbol
            label += "/ %s" % uom_translation[pricing.unit]
            result.append((pricing.id, label))
        return result



    _sql_constraints = [
        ('rental_pricing_duration',
            "CHECK(duration >= 0)",
            "The pricing duration has to be greater or equal to 0."),
        ('rental_pricing_price',
            "CHECK(price >= 0)",
            "The pricing price has to be greater or equal to 0."),
    ]

    def applies_to(self, product):
        """Check whether current pricing applies to given product.

        :param product.product product:
        :return: true if current pricing is applicable for given product, else otherwise.
        :rtype: bool
        """
        return (
            self.product_template_id == product.product_id
            and (
                not self.product_variant_ids
                or product in self.product_variant_ids))

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