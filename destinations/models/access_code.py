from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import datetime
import pytz
import json

class DestinationAccessCodes(models.Model):
    _name = "destination.access.code"
    _description = "Access Token Code"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    dest_id = fields.Many2one('destination.destination', string='Entity', tracking=True, index=True, copy=True, default=lambda self: self._get_default_dest_id())
    def _get_default_dest_id(self):
        conf = self.env['destination.destination'].search(['|',('user_ids.user_id','=',self.env.user.id),('manager_ids.user_id','=',self.env.user.id)], limit=1)
        return conf.id
    
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    
    name = fields.Char(string='Name', default=lambda self: _('New'))
    code_letter = fields.Char(string='Code Letter', required=True, size=1, tracking=True)
    code_number = fields.Integer(string='Code Number', required=True, size=3, tracking=True)
    activity_id = fields.Many2one('destination.membership.member.activity', string="Member Activity")
    source_document = fields.Reference (selection = [('destination.guest', 'Guest'),('destination.membership.member.activity', 'Member')], ondelete='restrict', string = "Source Document")  
    is_used = fields.Boolean(string="Used", default=False, tracking=True)
    link_date = fields.Datetime(string="Token Link Date")
    active = fields.Boolean(string="Active", tracking=True, default=True)
    
    @api.model
    def create(self, vals):
        vals['name'] = str(vals['code_letter']) + str(vals['code_number'])
        result = super(DestinationAccessCodes, self).create(vals)
        return result    
    
    def unlink(self):
        for record in self:
            if record.is_used:
                raise UserError("Cannot delete a linked Access Token.")
        return super(DestinationAccessCodes, self).unlink()
    
    
    def name_get(self):
        res = []
        for record in self:
           
            name = '%s%s' % (record.code_letter, record.code_number)
            res.append((record.id, name))
        return res
        return super(DestinationAccessCodes, self).name_get()

    
    def register_codes(self):
        return {
            'name': 'Generate Access Codes',
            'view_mode': 'form',
            'res_model': 'destination.access.code.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }

    @api.constrains('name')
    def _check_duplicate_codes(self):
        for record in self:
            if record.search_count([('name', '=', record.name),('is_used','=',False),('dest_id','=',record.dest_id.id)]) > 1:
                raise ValidationError("Access Code (" + record.name + ") already exist")
