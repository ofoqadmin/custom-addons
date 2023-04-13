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

class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    
    is_manager = fields.Boolean(string="Is Manager", compute='_is_manager', default=False)
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    
    dest_source = fields.Selection([('rental', 'Rental/Membership'), ('access','Access'), ('others','Others')], string="Order Source", copy=False, tracking=True)
    
    dest_id = fields.Many2one('destination.destination', string='Entity', tracking=True, index=True, copy=False)
    lock_dest_id = fields.Boolean(store=False, copy=False, default=False)
    
    rental_id = fields.Many2one('destination.membership', string='Linked Rental', ondelete='restrict', copy=False)
    membership_id = fields.Many2one('destination.membership', string='Rental', ondelete='restrict', copy=False, domain="[('dest_id','=',dest_id)]")
    
    dest_payment_method_id = fields.Many2one('destination.payment.method',string='Payment Method')
    security_deposit_amount = fields.Float("Security Deposit Amount")
    
    
    
    def _is_manager(self):
        for e in self:
            if e.membership_id:
                e.is_manager = (True if e.env.user.id in e.membership_id.product_id.dest_id.manager_ids.user_id.ids else False)
            else:
                e.is_manager = False

        
    """
    @api.ondelete(at_uninstall=False)
    def _revert_membership_state(self):
        for order in self:
            if order.membership_id:
                membershipid = self.env['destination.membership'].search([('id','=',order.membership_id.id)])
                membershipid.update({'state':'new'})
    """    
                
    @api.onchange('dest_id')
    def reset_domain_fields(self):
        self.membership_id = False