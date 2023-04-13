from odoo import api, fields, models, _, tools



class DestinationNotes(models.Model):
    _name = "destination.note"
    _description = "Note Templates"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Name', required=True, translate=True, store=True, index=True, copy=True, tracking=True)
    active = fields.Boolean(string="Active", tracking=True, default=True)
    sequence = fields.Integer(string="Sequence")
    
    note = fields.Html("Description", translate=True, tracking=True)