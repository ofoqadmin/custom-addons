# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
import math
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class DestinationAccessCustomPrice(models.Model):
    _name = "destination.product.access.price.lines"
    _description = "Access Price Lines"
  
    sequence = fields.Integer(string="Sequence", copy=True)
    product_id = fields.Many2one('product.template', string="Product")
    dest_id = fields.Many2one('destination.destination', string='Entity', related='product_id.dest_id')
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    
    access_weekday = fields.Selection([
        ('6', 'Sunday'),
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday')], store=True, copy=True, string="Weekday")
    
    access_time_start = fields.Float(string="Session Start", copy=True)
    access_time_end = fields.Float(string="Session End", copy=True, default=(23 + (0.59/60*100)))
    access_duration = fields.Float(string="Session Duration", copy=True)
    
    duration = fields.Float(string="Delta", compute='compute_duration')    
    weekday_duration = fields.Float(string="Total Delta", compute='compute_weekday_duration')
    
    check = fields.Boolean(string="Check", compute='compute_weekday_duration')
    
    price = fields.Float(string="Price", digits='Product Price', store=True, copy=True)

    @api.onchange('access_time_end','access_time_start')
    def check_dates(self):
        if self.access_time_end and self.access_time_start and self.access_time_end <= self.access_time_start:
            raise ValidationError('Date Error.')
            
    @api.depends('access_time_end','access_time_start')
    def compute_duration(self):
        for record in self:
            record.duration = record.access_time_end - record.access_time_start
         
    def compute_weekday_duration(self):
        for record in self:
            samedayrecs = self.env['destination.product.access.price.lines'].search([('product_id','=',record.product_id.id),('access_weekday','=',record.access_weekday)])
            record.weekday_duration = sum(line.duration for line in samedayrecs)
            if math.ceil(record.weekday_duration) != 24:
                record.check = True
            else:
                record.check = False
