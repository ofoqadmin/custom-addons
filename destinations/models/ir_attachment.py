# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools

class Attachment(models.Model):
    _inherit = 'ir.attachment'
    
    membership_ids = fields.Many2many('destination.membership', string = "Membership")
    member_ids = fields.Many2many('destination.membership.member', string = "Member")
