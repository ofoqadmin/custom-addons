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



class ProductTemplateDestReport(models.TransientModel):
    _name = 'destination.product.report'
    _description = 'Destination Report'
    
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id', depends=['product_id.currency_id'], store=True, string='Currency')
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, default=lambda self: self.env.user)
    
    rental_status = fields.Selection([('actual','Booked'),('plan','Pipeline')],"Rental Status")
    
    product_id = fields.Many2one('product.product', string='Product', domain="[('dest_ok','=',True)]", required=True)
    product_quantity = fields.Integer("Product Quantity", related="product_id.dest_quantity", default=0, store=True)
    product_categ_id = fields.Many2one('product.category', "Product Category", related="product_id.categ_id", store=True)
    dest_product_group = fields.Selection([('accommodation', 'Rental'), ('membership', 'Membership'), ('access', 'Access'), ('others', 'Others')], string="Product Group", related='product_id.dest_product_group',  store=True)
    dest_custom_price = fields.Selection([('weekday_rate', 'Variable Weekday Rate'), ('daily_rate', 'Variable Daily Rate'), ('fixed', 'Fixed Rate')], string="Pricing Type", related='product_id.dest_custom_price',   store=True)
    dest_id = fields.Many2one('destination.destination', string='Entity', related='product_id.dest_id', store=True)
    
    start_date = fields.Datetime("Start Date", default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hour=0) - timedelta(hours=3))
    end_date = fields.Datetime("End Date", default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hour=0, days=1) - timedelta(hours=3))
        
    days_range = fields.Float("Days Range", compute="compute_stats", default=0, store=True)
    hours_range = fields.Float("Hours Range", compute="compute_stats", default=0, store=True)
    minutes_range = fields.Float("Minutes Range", compute="compute_stats", default=0, store=True)
    time_range = fields.Float("Time Range", compute="compute_stats", default=0, store=True)
    
    days_available = fields.Float("Days Available", compute="compute_stats", default=0, store=True)
    hours_available = fields.Float("Hours Available", compute="compute_stats", default=0, store=True)
    minutes_available = fields.Float("Minutes Available", compute="compute_stats", default=0, store=True)
    time_available = fields.Float("Time Available", compute="compute_stats", default=0, store=True)
    
    days_occupied = fields.Float("Days Occupied", compute="compute_stats", default=0, store=True)
    hours_occupied = fields.Float("Hours Occupied", compute="compute_stats", default=0, store=True)
    minutes_occupied = fields.Float("Minutes Occupied", compute="compute_stats", default=0, store=True)
    time_occupied = fields.Float("Time Occupied", compute="compute_stats", default=0, store=True)
    
    expected_days_occupied = fields.Float("Pipeline Days Occupied", compute="compute_stats", default=0, store=True)
    expected_hours_occupied = fields.Float("Pipeline Hours Occupied", compute="compute_stats", default=0, store=True)
    expected_minutes_occupied = fields.Float("Pipeline Minutes Occupied", compute="compute_stats", default=0, store=True)
    expected_time_occupied = fields.Float("Pipeline Time Occupied", compute="compute_stats", default=0, store=True)
    
    total_days_occupied = fields.Float("Total Days Occupied", compute="compute_stats", default=0, store=True)
    total_hours_occupied = fields.Float("Total Hours Occupied", compute="compute_stats", default=0, store=True)
    total_minutes_occupied = fields.Float("Total Minutes Occupied", compute="compute_stats", default=0, store=True)
    total_time_occupied = fields.Float("Total Time Occupied", compute="compute_stats", default=0, store=True)
    
    membership_ids = fields.One2many('destination.membership', string='Rentals', compute='get_memberships')
    membership_lines = fields.One2many('destination.membership.line', string='Rental Lines', compute='get_memberships')
    
    membership_count = fields.Integer("Rental Count", compute='get_memberships', default=0, store=True)
    expected_membership_count = fields.Integer("Pipeline Rental Count", compute='get_memberships', default=0, store=True)
    total_membership_count = fields.Integer("Total Rental Count", compute="get_memberships", default=0, store=True)
    
    occupancy_rate = fields.Float("Occupancy Rate", compute="compute_stats", default=0, store=True)
    expected_occupancy_rate = fields.Float("Pipeline Occupancy Rate", compute="compute_stats", default=0, store=True)
    total_occupancy_rate = fields.Float("Forecasted Occupancy Rate", compute="compute_stats", default=0, store=True)
    
    amount_untaxed = fields.Monetary(string='Untaxed Amount',  compute='_amount_all', default=0, tracking=True, store=True)
    amount_tax = fields.Monetary(string='Taxes Amount',  compute='_amount_all', default=0, tracking=True, store=True)
    amount_total = fields.Monetary(string='Total Amount',  compute='_amount_all', default=0, tracking=True, store=True)
    
    expected_amount_untaxed = fields.Monetary(string='Pipeline Untaxed Amount',  compute='_amount_all', default=0, tracking=True, store=True)
    expected_amount_tax = fields.Monetary(string='Pipeline Taxes Amount',  compute='_amount_all', default=0, tracking=True, store=True)
    expected_amount_total = fields.Monetary(string='Pipeline Total Amount',  compute='_amount_all', default=0, tracking=True, store=True)
    
    total_amount_untaxed = fields.Monetary(string='Total Untaxed Amount',  compute='_amount_all', default=0, tracking=True, store=True)
    total_amount_tax = fields.Monetary(string='Total Taxes Amount',  compute='_amount_all', default=0, tracking=True, store=True)
    total_amount_total = fields.Monetary(string='Total Total Amount',  compute='_amount_all', default=0, tracking=True, store=True)
    
    average_per_day = fields.Monetary(string='Avg/Day',  compute='_amount_all', default=0, tracking=True, store=True)
    average_per_count = fields.Monetary(string='Avg/Count',  compute='_amount_all', default=0, tracking=True, store=True)
    
    expected_average_per_day = fields.Monetary(string='Pipeline Avg/Day',  compute='_amount_all', default=0, tracking=True, store=True)
    expected_average_per_count = fields.Monetary(string='Pipeline Avg/Count',  compute='_amount_all', default=0, tracking=True, store=True)
    
    total_average_per_day = fields.Monetary(string='Total Avg/Day',  compute='_amount_all', default=0, tracking=True, store=True)
    total_average_per_count = fields.Monetary(string='Total Avg/Count',  compute='_amount_all', default=0, tracking=True, store=True)
            
            
    @api.depends('start_date','end_date','product_id')
    def get_memberships(self):
        for record in self:
            record.membership_ids = False
            record.membership_lines = False
            record.membership_count = False
            
            if record.product_id and record.start_date and record.end_date:
                if record.rental_status == 'actual':
                    membership_ids = record.env['destination.membership'].search([('state','in',['active','hold','checked-out','done','late'])]).filtered(lambda r: r.product_id == record.product_id and r.start_date < record.end_date and r.end_date > record.start_date)
                    membership_lines = record.env['destination.membership.line'].search([('membership_id','in',membership_ids.ids)]).filtered(lambda r: r.product_id == record.product_id and r.start_date < record.end_date and r.end_date > record.start_date)
                    record.membership_count = len(membership_ids)
                else:
                    membership_ids = record.env['destination.membership'].search([('state','=','confirmed')]).filtered(lambda r: r.product_id == record.product_id and r.start_date < record.end_date and r.end_date > record.start_date)
                    membership_lines = record.env['destination.membership.line'].search([('membership_id','in',membership_ids.ids)]).filtered(lambda r: r.product_id == record.product_id and r.start_date < record.end_date and r.end_date > record.start_date)
                    record.expected_membership_count = len(membership_ids)
                    
                if membership_ids:
                    record.write({'membership_ids': [(6, 0, membership_ids.ids)], 'membership_lines':[(6, 0, membership_lines.ids)]})
                    
                record.total_membership_count = record.membership_count + record.expected_membership_count
                    
            
                    
    @api.depends('start_date','end_date','product_id')
    def compute_stats(self):
        for record in self:   
                
            if record.start_date and record.end_date and record.product_id and record.product_quantity:
                record.days_range = (record.end_date - record.start_date).days
                record.time_range = (record.end_date - record.start_date).seconds
                record.hours_range = record.time_range / 60 / 60
                record.minutes_range = (record.time_range / 60) - record.hours_range * 60

                if record.rental_status == 'actual':
                    if record.product_id.dest_checkout_time > record.product_id.dest_checkin_time:
                        secperday = (record.product_id.dest_checkout_time - record.product_id.dest_checkin_time) * 3600
                        record.time_available = (record.days_range * secperday * record.product_quantity) + (record.time_range * record.product_quantity)
                        record.days_available = record.time_available / 86400
                        record.time_occupied = sum(((line.end_date if line.end_date <= record.end_date else record.end_date) - (line.start_date if line.start_date > record.start_date else record.start_date)).seconds + (((line.end_date if line.end_date <= record.end_date else record.end_date) - (line.start_date if line.start_date > record.start_date else record.start_date)).days * secperday) for line in record.membership_ids)
                        record.days_occupied = record.time_occupied / 86400
                        record.occupancy_rate = record.time_occupied / record.time_available * 100
                    else:
                        record.days_available = (record.days_range * record.product_quantity)
                        record.time_available = record.days_available * 86400
                        record.days_occupied = sum((((line.end_date if line.end_date <= record.end_date else record.end_date) - (line.start_date if line.start_date > record.start_date else record.start_date)).days) for line in record.membership_ids)
                        record.time_occupied = record.days_occupied * 86400
                        record.occupancy_rate = record.days_occupied / record.days_available * 100
                else:
                    if record.product_id.dest_checkout_time > record.product_id.dest_checkin_time:
                        secperday = (record.product_id.dest_checkout_time - record.product_id.dest_checkin_time) * 3600
                        record.time_available = (record.days_range * secperday * record.product_quantity) + (record.time_range * record.product_quantity)
                        record.days_available = record.time_available / 86400
                        record.expected_time_occupied = sum(((line.end_date if line.end_date <= record.end_date else record.end_date) - (line.start_date if line.start_date > record.start_date else record.start_date)).seconds + (((line.end_date if line.end_date <= record.end_date else record.end_date) - (line.start_date if line.start_date > record.start_date else record.start_date)).days * secperday) for line in record.membership_ids)
                        record.expected_days_occupied = record.expected_time_occupied / 86400
                        record.expected_occupancy_rate = record.expected_time_occupied / record.time_available * 100
                    else:
                        record.days_available = (record.days_range * record.product_quantity)
                        record.time_available = record.days_available * 86400
                        record.expected_days_occupied = sum((((line.end_date if line.end_date <= record.end_date else record.end_date) - (line.start_date if line.start_date > record.start_date else record.start_date)).days) for line in record.membership_ids)
                        record.expected_time_occupied = record.expected_days_occupied * 86400
                        record.expected_occupancy_rate = record.expected_days_occupied / record.days_available * 100
                
                
                record.total_days_occupied = record.days_occupied + record.expected_days_occupied
                record.total_hours_occupied = record.hours_occupied + record.expected_hours_occupied
                record.total_minutes_occupied = record.minutes_occupied + record.expected_minutes_occupied
                record.total_time_occupied = record.time_occupied + record.expected_time_occupied
                
                record.total_occupancy_rate = record.occupancy_rate + record.expected_occupancy_rate
                
                
                
                
    @api.depends('membership_lines.price_total')
    def _amount_all(self):
        for order in self:
            if order.product_id and order.start_date and order.end_date and order.rental_status == 'actual':
                amount_untaxed = amount_tax = 0.0
                if order.membership_lines:
                    for line in order.membership_lines:
                        amount_untaxed += line.price_subtotal
                        amount_tax += line.price_tax
                    order.amount_untaxed = amount_untaxed
                    order.amount_tax = amount_tax
                    order.amount_total = amount_untaxed + amount_tax
            if order.product_id and order.start_date and order.end_date and order.rental_status == 'plan':
                amount_untaxed = amount_tax = 0.0
                if order.membership_lines:
                    for line in order.membership_lines:
                        amount_untaxed += line.price_subtotal
                        amount_tax += line.price_tax
                    order.expected_amount_untaxed = amount_untaxed
                    order.expected_amount_tax = amount_tax
                    order.expected_amount_total = amount_untaxed + amount_tax
            
       
            order.total_amount_untaxed = order.amount_untaxed + order.expected_amount_untaxed
            order.total_amount_tax = order.amount_tax + order.expected_amount_tax
            order.total_amount_total = order.amount_total + order.expected_amount_total

            if order.days_occupied > 0:
                order.average_per_day = order.amount_total / order.days_occupied
            
            if order.expected_days_occupied > 0:
                order.expected_average_per_day = order.expected_amount_total / order.expected_days_occupied
            
            if order.total_days_occupied > 0:
                order.total_average_per_day = order.total_amount_total / order.total_days_occupied

            if order.membership_count > 0:
                order.average_per_count = order.amount_total / order.membership_count

            if order.expected_membership_count > 0:
                order.expected_average_per_count = order.expected_amount_total / order.expected_membership_count

            if order.total_membership_count > 0:
                order.total_average_per_count = order.total_amount_total / order.total_membership_count