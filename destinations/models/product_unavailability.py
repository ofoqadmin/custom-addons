# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
import math
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date


class ProductUnavailability(models.Model):
    _name = "destination.product.unavailability"
    _description = "Destination Product Unavailability"
    _order = 'start_date'   
  
    product_id = fields.Many2one('product.template', string="Product Templates")
    product_variant_ids = fields.Many2many('product.product', string="Product Variants")
    start_date = fields.Date(string="Start", required=True, tracking=True)
    end_date = fields.Date(string="End", required=True, tracking=True)
    reason = fields.Text(string="Reason")
    