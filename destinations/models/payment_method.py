from odoo import api, fields, models, _, tools



class DestinationPaymentMethod(models.Model):
    _name = "destination.payment.method"
    _description = "Payment Method"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Name', required=True, translate=True, store=True, index=True, copy=True, tracking=True)
    active = fields.Boolean(string="Active", tracking=True, default=True)
    sequence = fields.Integer(string="Sequence")
    
    journal_id = fields.Many2one('account.journal', ondelete='restrict', tracking=True, string="Payment Journal", store=True,
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank', 'cash'))]")
    
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)

    
    rental_payment_method_ids = fields.Many2many('destination.destination', 'rental_payment_method_ids',string='Rental Payment Methods')
    access_payment_method_ids = fields.Many2many('destination.destination', 'access_payment_method_ids', string='Rental Payment Methods')
    
    note = fields.Html("Description", translate=True, tracking=True)