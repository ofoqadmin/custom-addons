from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import datetime
import pytz
import json

class DestinationBlacklist(models.Model):
    _name = "destination.blacklist"
    _description = "Blacklist"
    
    dest_id = fields.Many2one('destination.destination', string='Entity', tracking=True, index=True, copy=True, default=lambda self: self._get_default_dest_id())
    def _get_default_dest_id(self):
        conf = self.env['destination.destination'].search(['|',('user_ids.user_id','=',self.env.user.id),('manager_ids.user_id','=',self.env.user.id)], limit=1)
        return conf.id
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    
    partner_id = fields.Many2one('res.partner', string='Contact', domain="[('is_company','=',False)]", ondelete='restrict', tracking=100, store=True, copy=True, required=True)
    name = fields.Char(string='Name', translate=True)
    start_date = fields.Datetime(string="Start", required=True, default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hours=1))
    end_date = fields.Datetime(string="End", required=True, default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hours=1, days=1)) 
    state = fields.Selection([('active', 'Active'), ('inactive','Inactive')], string="Listing Status", required=True, default='active')

    @api.constrains('dest_id','partner_id')
    def _check_duplicate_blacklist(self):
        for record in self:
            if self.search_count([('dest_id', '=', record.dest_id.id),('partner_id','=',self.partner_id.id), ('id', '!=', record.id)]) > 1:
                raise ValidationError("Cannot add same member twice")

                
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.search([('id_number', operator, name)] + args, limit=limit)
        if not recs.ids:
            return super(DestinationBlacklist, self).name_search(name=name, args=args,
                                                       operator=operator,
                                                       limit=limit)
        return recs.name_get()
    
    def name_get(self):
        res = []
        for record in self:
            name = record.partner_id.name
            if record.dest_id.code:
                name = '%s (%s)' % (name, record.dest_id.code)
            res.append((record.id, name))
        return res
        return super(DestinationBlacklist, self).name_get()