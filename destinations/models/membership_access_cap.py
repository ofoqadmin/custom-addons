# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
import math
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError, UserError


class MembershipAccessCap(models.Model):
    _name = "destination.membership.guest.access.cap"
    _description = "Membership Guest Access Caps"
    _order = "sequence"
    
    
    sequence = fields.Integer("Sequence")
    membership_id = fields.Many2one("destination.membership", "Rental")
    product_id = fields.Many2one("product.template", "Product", related='membership_id.dest_id')
    dest_id = fields.Many2one('destination.destination', string='Entity', related="membership_id.dest_id")
    is_manager = fields.Boolean(string="Is Manager", compute='_is_manager')
    @api.onchange('membership_id')
    @api.depends('membership_id')
    def _is_manager(self):
        for record in self:
            record.is_manager = (True if record.env.user.id in record.membership_id.dest_id.manager_ids.user_id.ids else False)
    
    cap = fields.Integer("Cap", store=True, copy=True)
    period = fields.Selection([('day', 'Day'), ('month', 'Month')], string="Period", default='day', store=True, copy=True)
    free_guest = fields.Boolean("Free")
    product_ids = fields.Many2many("product.template", string="Products", domain="[('dest_product_group','=','access'),('dest_id','=',dest_id)]", store=True, copy=True)
    
    state = fields.Selection([('active', 'Approved'), ('pending', 'Pending')], string="Status")
    
    @api.model
    def create(self, vals):
        if 'state' not in vals or vals['state'] == False:
            vals['state'] = 'pending'
        result = super(MembershipAccessCap, self).create(vals)
        return result    
    
    def write(self, vals):
        for record in self:
            if 'state' not in vals or vals['state'] == False:
                vals['state'] = 'pending'
        return super(MembershipAccessCap, self).write(vals)
            
    def request_approval(self):
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.membership_id.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                        ('summary','=','Request Cap Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.unlink()
            
        check_authorizer = self.membership_id.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'authorizer')
        
        if check_authorizer:
            managers = check_authorizer
        else:
            managers = self.membership_id.dest_id.manager_ids
        
        for manager in managers:
            todos = {
            'res_id': self.membership_id.id,
            'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id,
            'user_id': manager.user_id.id,
            'summary': 'Request Cap Approval',
            'note': self.membership_id.name,
            'activity_type_id': 4,
            'date_deadline': fields.Datetime.now(),
            }
            sfa = self.env['mail.activity'].create(todos)
            
    
    def approve_cap(self):
        is_manager = (True if self.env.user.id in self.membership_id.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'manager').user_id.ids else False) 
        
        if is_manager:
            self.state = 'active'
            getrequests = self.env['mail.activity'].search([
                            ('res_id','=',self.membership_id.id),
                            ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                            ('summary','=','Request Cap Approval'),
                            ('activity_type_id','=',4)
                        ])
            if getrequests:
                getrequests.action_feedback(feedback='Approved')
        else:
            getrequests = self.env['mail.activity'].search([
                            ('res_id','=',self.membership_id.id),
                            ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                            ('summary','=','Request Cap Approval'),
                            ('activity_type_id','=',4)
                        ])
            if getrequests:
                getrequests.action_feedback(feedback='Authorized')
                
            managers = self.membership_id.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'manager')

            for manager in managers:
                todos = {
                    'res_id': self.membership_id.id,
                    'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id,
                    'user_id': manager.user_id.id,
                    'summary': 'Request Cap Approval',
                    'note': self.membership_id.name,
                    'activity_type_id': 4,
                    'date_deadline': fields.Datetime.now(),
                    }

                sfa = self.env['mail.activity'].create(todos)
            
        
    def reject_cap(self):
        self.state = 'pending'
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.membership_id.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership')]).id),
                        ('summary','=','Request Cap Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.action_feedback(feedback='Rejected')
    

    
    
    

  