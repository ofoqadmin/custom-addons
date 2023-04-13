# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
import math
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError, Warning

class GuestAccessCap(models.Model):
    _name = "destination.guest.access.cap"
    _description = "Guest Access Caps"
    _order = "sequence"
    
    
    guest_batch_id = fields.Many2one("destination.guest.batch", "Guest Batch")
    membership_id = fields.Many2one('destination.membership', string='Rental', related='guest_batch_id.membership_id')
    access_date = fields.Datetime(string="Token Start",related='guest_batch_id.access_date')
    access_date_date = fields.Date(string="Token Start Date", related='guest_batch_id.access_date_date')
    access_date_month = fields.Integer(string="Token Start Month", related='guest_batch_id.access_date_month')
    
    dest_id = fields.Many2one('destination.destination', string='Entity', related="guest_batch_id.dest_id")
    
    cap = fields.Integer("Cap")
    period = fields.Selection([('day', 'Day'), ('month', 'Month')], string="Period", default='day')
    free_guest = fields.Boolean("Free")
    product_ids = fields.Many2many("product.template", domain="[('dest_product_group','=','access'),('dest_id','=',dest_id)]", store=True, copy=True)
    used_cap = fields.Integer("Used Cap", compute="_get_guest_stats")
    
    
    def _get_guest_stats(self):
        for record in self:
            #raise UserError(record.membership_id)
            counter = 0
            for prod in record.product_ids:
                if record.free_guest == True:
                    if record.period == 'day':
                        counter = counter + self.env['destination.guest'].search_count([('state','not in',['cancel','pending','blacklist']),('membership_id','=',record.membership_id.id),('access_date_date','=',record.access_date_date),('product_id','=',prod.product_variant_id._origin.id),('token_type','=','free')])
                    elif record.period == 'month':
                        counter = counter + self.env['destination.guest'].search_count([('state','not in',['cancel','pending','blacklist']),('membership_id','=',record.membership_id.id),('access_date_month','=',record.access_date_month),('product_id','=',prod.product_variant_id._origin.id),('token_type','=','free')])
                else:
                    if record.period == 'day':
                        counter = counter + self.env['destination.guest'].search_count([('state','not in',['cancel','pending','blacklist']),('membership_id','=',record.membership_id.id),('access_date_date','=',record.access_date_date),('product_id','=',prod.product_variant_id._origin.id)])
                    elif record.period == 'month':
                        counter = counter + self.env['destination.guest'].search_count([('state','not in',['cancel','pending','blacklist']),('membership_id','=',record.membership_id.id),('access_date_month','=',record.access_date_month),('product_id','=',prod.product_variant_id._origin.id)])
                
                
            record.used_cap = counter

    

    

    
    
    

  