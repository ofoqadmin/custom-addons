from odoo import api, fields, models, _, tools
import math
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError

class ProductCategory(models.Model):
    _inherit = 'product.category'
    
    
    
    
    user_ids = fields.Many2many('destination.user',string="Excluded Users") 
    
    