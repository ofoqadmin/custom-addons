from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import datetime
import pytz
import json




class DestinationUser(models.Model):
    _name = "destination.user"
    _description = "Users"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    
    name = fields.Text(string='Name', copy=False, store=True, compute="compute_name")
    user_id = fields.Many2one('res.users', string="User", required=True, ondelete='cascade')

    manager_role = fields.Selection([
    ('manager', 'Manager'),
    ('authorizer', 'Authorizer'),
    ], string='Role', tracking=True, default='authorizer')
    
    dest_manager_ids = fields.Many2one('destination.destination', string="Manager")
    dest_user_ids = fields.Many2one('destination.destination', string="User")
    
    cat_user_ids = fields.Many2many('product.category',string="Excluded Category")
    
    
    @api.depends('user_id')
    def compute_name(self):
        for record in self:
            record.name = record.user_id.name
    
    def name_get(self):
        res = []
        for record in self:
           
            name = record.name
            res.append((record.id, name))
        return res
        return super(DestinationUser, self).name_get()
    
    
    @api.constrains('dest_manager_ids', 'dest_user_ids')
    def _check_duplicate(self):
        for record in self:
            if record.dest_manager_ids:
                user_ids = self.search([('user_id', '=', record.user_id.id),('dest_manager_ids', '=', record.dest_manager_ids.id), ('id', '<>', record.id)])
                if len(user_ids) >= 1:
                    raise ValidationError("Cannot add same Manager twice.")
            if record.dest_user_ids:
                user_ids = self.search([('user_id', '=', record.user_id.id),('dest_user_ids', '=', record.dest_user_ids.id), ('id', '<>', record.id)])
                if len(user_ids) >= 1:
                    raise ValidationError("Cannot add same User twice.")