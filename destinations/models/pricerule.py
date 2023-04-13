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

PERIOD_RATIO = {
    'hour': 1,
    'day': 24,
    'week': 24 * 7
}

class DestinationPrice(models.Model):
    _name = "destination.price"
    _description = "Price Rule"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(String="Name", required=True, copy=True, tracking=True)
    
    is_forced = fields.Boolean(string="Is Forced", tracking=True)
    
    rule_type = fields.Selection([('price', 'Custom Price'),('discount','Discount')], string='Rule Type', default='price', required=True, copy=True, tracking=True)
    
    discount = fields.Float(string="Discount", tracking=True)
    
    validity_datetime_start = fields.Datetime(string="Validity Start", copy=True, tracking=True, required=True, default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hours=1))
    validity_datetime_end = fields.Datetime(string="Validity End", copy=True, tracking=True, required=True, default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hours=1, days=1))
    
    dest_guest_gender_male = fields.Boolean(string="Male", default=True, tracking=True)
    dest_guest_gender_female = fields.Boolean(string="Female", default=True, tracking=True)
    
    @api.onchange('validity_datetime_start','validity_datetime_end')
    def check_validity_dates(self):
        if self.validity_datetime_end and self.validity_datetime_start and self.validity_datetime_end <= self.validity_datetime_start:
            raise ValidationError('Validity Date Error.')
    
    service_datetime_start = fields.Datetime(string="Service Start", copy=True, tracking=True)
    service_datetime_end = fields.Datetime(string="Service End", copy=True, tracking=True)
    
    @api.onchange('service_datetime_start','service_datetime_end')
    def check_service_dates(self):
        if self.service_datetime_end and self.service_datetime_start and self.service_datetime_end <= self.service_datetime_start:
            raise ValidationError('Service Date Error.')
    
    service_timeonly_start = fields.Float(string="Time Start", copy=True, tracking=True)
    service_timeonly_end = fields.Float(string="Time End", copy=True, tracking=True)
    
    dest_checkin_time = fields.Float(string="Check-In Time", store=True, copy=True, default=0.0, tracking=True)
    dest_checkout_time = fields.Float(string="Check-Out Time", store=True, copy=True, default=0.0, tracking=True)

    
    dest_access_start_time = fields.Float(string="Access Start Time", store=True, copy=True, default=0.0, tracking=True)
    dest_access_duration = fields.Float(string="Access Duration", store=True, copy=True, default=0.0, tracking=True)

    dest_id = fields.Many2one('destination.destination', string='Entity', tracking=True, index=True, copy=True, default=lambda self: self._get_default_dest_id())
    def _get_default_dest_id(self):
        conf = self.env['destination.destination'].search(['|',('user_ids.user_id','=',self.env.user.id),('manager_ids.user_id','=',self.env.user.id)], limit=1)
        return conf.id
    
    
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    
    lock_dest_id = fields.Boolean(store=False, copy=False, default=False)
    
    product_id = fields.Many2one('product.product', string='Product', domain="[('dest_ok','=',True),('dest_id','=',dest_id)]", ondelete='restrict', tracking=True, store=True, copy=True, required=True)
    product_tmpl_id = fields.Many2one('product.template', related='product_id.product_tmpl_id')
    lock_product_id = fields.Boolean(store=False, copy=False, default=False) 
    
    partner_ids = fields.Many2many('res.partner', string='Customer', ondelete='restrict', tracking=True, store=True, copy=True, required=True)
    customer_apply_on = fields.Selection([('all', 'All Customers'),('active','Active Members'),('select', 'Select Customer(s)')], string="Customer, Apply On", required=True, default='all', store=True, copy=True, tracking=True)                                             
    referral_apply_on = fields.Selection([('all', 'All Referrers'),('active','Active Members')], string="Referrer, Apply On", required=True, default='all', store=True, copy=True, tracking=True)                                          

    dest_product_group = fields.Selection([('accommodation', 'Rental'), ('membership', 'Membership'), ('access', 'Access'), ('others', 'Others')], related='product_id.dest_product_group')    
    dest_custom_price = fields.Selection([('weekday_rate', 'Variable Weekday Rate'), ('daily_rate', 'Variable Daily Rate'), ('fixed', 'Fixed Rate')], related='product_id.dest_custom_price')
    dest_product_code = fields.Char(string='Code', related='product_id.dest_product_code')
    
    dest_price_monday = fields.Float(string="Price Monday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_tuesday = fields.Float(string="Price Tuesday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_wednesday = fields.Float(string="Price Wednesday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_thursday = fields.Float(string="Price Thursday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_friday = fields.Float(string="Price Friday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_saturday = fields.Float(string="Price Saturday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_sunday = fields.Float(string="Price Sunday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    
    dest_rental_pricing_ids = fields.One2many('destination.price.lines', 'pricerule_id',string="Rental Pricings", auto_join=True, copy=True)
    dest_access_pricing_ids = fields.One2many('destination.price.access.lines', 'pricerule_id', string="Access Pricings", copy=True)

    list_price = fields.Float(string="Price", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id', depends=['product_id.currency_id'], store=True, string='Currency', readonly=True)

    @api.onchange('dest_id')
    def reset_product_id(self):
        if 'default_product_id' in self.env.context:
            if not self.env.context['default_product_id']:
                self.product_id = False
        else:
            self.product_id = False
            
    @api.constrains('is_forced','product_id','id','service_datetime_start','service_datetime_end','validity_datetime_start','validity_datetime_end','service_timeonly_start','service_timeonly_end')
    def _check_duplicate_forced(self):
        getrecs = []
        if self.is_forced:
            if self.product_id.dest_product_group in ['accommodation','membership','others']:
                getrecs = self.search([('product_id', '=', self.product_id.id),('is_forced','=',True),('id', '!=', self.id),('service_datetime_start','<=',self.service_datetime_end),('service_datetime_end','>=',self.service_datetime_start)])
                if len(getrecs) >= 1:
                    raise ValidationError("There is another forced rule with matching service dates")

            if self.product_id.dest_product_group == 'access' and self.product_id.dest_custom_price == 'weekday_rate':
                getrecs = self.search([('product_id', '=', self.product_id.id),('is_forced','=',True),('id', '!=', self.id),('validity_datetime_start','<=',self.validity_datetime_end),('validity_datetime_end','>=',self.validity_datetime_start)])
                if len(getrecs) >= 1:
                    raise ValidationError("There is another forced rule with matching validity dates")

            if self.product_id.dest_product_group == 'access' and self.product_id.dest_custom_price != 'weekday_rate':
                getrecs = self.search([('product_id', '=', self.product_id.id),('is_forced','=',True),('id', '!=', self.id),('service_timeonly_start','<=',self.service_timeonly_end),('service_timeonly_end','>=',self.service_timeonly_start)])
                if len(getrecs) >= 1:
                    raise ValidationError("There is another forced rule with matching service times")

                
                
    def _get_best_dest_pricing_rule(self, **kwargs):
        """Return the best pricing rule for the given duration.

        :param float duration: duration, in unit uom
        :param str unit: duration unit (hour, day, week)
        :param datetime start_date:
        :param datetime end_date:
        :return: least expensive pricing rule for given duration
        :rtype: destination.price.lines
        """
        self.ensure_one()
        best_pricing_rule = self.env['destination.price.lines']
        if not self.dest_rental_pricing_ids:
            return best_pricing_rule
        start_date, end_date = kwargs.get('start_date', False), kwargs.get('end_date', False)
        duration, unit = kwargs.get('duration', False), kwargs.get('unit', '')
        pricelist = kwargs.get('pricelist', self.env['product.pricelist'])
        currency = kwargs.get('currency', self.env.company.currency_id)
        company = kwargs.get('company', self.env.company)
        if start_date and end_date:
            duration_dict = self.env['destination.price.lines']._compute_duration_vals(start_date, end_date)
        elif not(duration and unit):
            return best_pricing_rule  # no valid input to compute duration.
        min_price = float("inf")  # positive infinity
        available_pricings = self.dest_rental_pricing_ids
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
    
  
    
    @api.onchange('pricerule_start_date', 'pricerule_end_date')
    @api.depends('pricerule_start_date', 'pricerule_end_date')
    def _compute_pricerule_pricing(self):
            self.pricerule_pricing_id = self._get_best_dest_pricing_rule(
                    start_date=self.pricerule_start_date,
                    end_date=self.pricerule_end_date,
                    pricelist=self.pricelist_id,
                    company=self.company_id) 
    
    