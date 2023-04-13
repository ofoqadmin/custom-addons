# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
import math
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class ProductAccessCap(models.Model):
    _name = "product.access.cap"
    _description = "Product Access Caps"
    _order = "sequence"
    
    sequence = fields.Integer("Sequence")
    product_id = fields.Many2one("product.template", "Product")
    dest_id = fields.Many2one('destination.destination', string='Entity', related="product_id.dest_id")
    
    cap = fields.Integer("Cap", store=True, copy=True)
    period = fields.Selection([('day', 'Day'), ('month', 'Month')], string="Period", default='day', store=True, copy=True)
    free_guest = fields.Boolean("Free")
    product_ids = fields.Many2many("product.template", string="Products", domain="[('dest_product_group','=','access'),('dest_id','=',dest_id)]", store=True, copy=True)
    used_cap = fields.Integer("Used Cap", store=False)

    

    

    
    
    

  