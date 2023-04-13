# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError


class Destination(models.Model):
    _name = "destination.destination"
    _description = "Entity"
    _inherit = ['mail.thread', 'mail.activity.mixin']


    name = fields.Char(string='Name', required=True, translate=True, tracking=True,  index=True, copy=True)
    active = fields.Boolean(string="Active", tracking=True, default=True)
    sequence = fields.Integer(string="Sequence")
    code = fields.Char(string='Code', required=True, size=4, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Contact', ondelete='restrict', tracking=True,  copy=True)
    image = fields.Binary(string='Image', tracking=True,  copy=True)
    company_image = fields.Binary(string='Company Image', tracking=True,  copy=True)
    product_tmpl_ids = fields.Many2many('product.template', 'dest_id', string = 'Products', store=True)
    product_count = fields.Integer(string="Products Count", compute='_compute_dest_product_count')
      
    membership_ids = fields.One2many('destination.membership', 'dest_id', string='Rentals', tracking=True)
    membership_count = fields.Integer('Rentals', compute='count_membership')
    member_ids = fields.One2many('destination.membership.member', 'dest_id', string = 'Members')
    member_count = fields.Integer(string='Members Count', compute='count_member')
    guest_ids = fields.One2many('destination.guest', 'dest_id', string = 'Guests')
    guest_count = fields.Integer(string='Guest Count', compute='count_guest')
    member_activity_ids = fields.One2many('destination.membership.member.activity', 'dest_id', string = 'Member Access')
    member_activity_count = fields.Integer(string='Member Access', compute='count_member_activity')
    
    active_membership_count = fields.Integer('Rentals', compute='count_membership')
    active_member_count = fields.Integer(string='Members Count', compute='count_member')
    checkedin_guest_count = fields.Integer(string='Checked-in Guests', compute='count_guest')
    checkedin_member_count = fields.Integer(string='Checked-in Members', compute='count_member_activity')
    
    pricerule_ids = fields.One2many('destination.price', 'dest_id', string = 'Price Rule')
    pricerule_count = fields.Integer(string='Price Rule Count', compute='count_pricerule')
    
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)

    manager_ids = fields.One2many('destination.user', 'dest_manager_ids', string='Managers', tracking=True,  copy=True) 
    user_ids = fields.One2many('destination.user', 'dest_user_ids', string='Users', tracking=True,  copy=True) 
    
    rental_sales_journal_id = fields.Many2one('account.journal', string="Rental Sales Journal", domain="[('company_id', '=', company_id), ('type', '=', 'sale')]")
    rental_deposit_journal_id = fields.Many2one('account.journal', string="Rental Deposit Journal", domain="[('company_id', '=', company_id), ('type', '=', 'sale')]")
    access_sales_journal_id = fields.Many2one('account.journal', string="Access Sales Journal", domain="[('company_id', '=', company_id), ('type', '=', 'sale')]")
    
    rental_payment_method_ids = fields.Many2many('destination.payment.method', 'rental_payment_method_ids',string='Rental Payment Methods', store=True)
    rental_default_payment_method_id = fields.Many2one('destination.payment.method',string='Default Rental Payment Method', domain="[('id','in',rental_payment_method_ids)]")
    access_payment_method_ids = fields.Many2many('destination.payment.method', 'access_payment_method_ids', string='Access Payment Methods', store=True)
    access_default_payment_method_id = fields.Many2one('destination.payment.method',string='Default Access Payment Method', domain="[('id','in',access_payment_method_ids)]")

    rental_partner_default_category_ids = fields.Many2many('res.partner.category', 'destination_rental_default_ids',string='Rental Partner Default Tags', store=True)
    access_partner_default_category_ids = fields.Many2many('res.partner.category', 'destination_access_default_ids',string='Access Partner Default Tags', store=True)
    
    partner_id_required = fields.Boolean("ID Required", tracking=True)
    partner_gender_required = fields.Boolean("Gender Required", tracking=True)
    partner_email_required = fields.Boolean("Email Required", tracking=True)
    partner_phone_required = fields.Boolean("Phone Required", tracking=True)
    partner_mobile_required = fields.Boolean("Mobile Required", tracking=True)
    
    approval_required_dest = fields.Boolean("All Check-In Approval Required", tracking=True)
    approval_required_membership = fields.Boolean("Memberships Check-In Approval Required", tracking=True)
    approval_required_accommodation = fields.Boolean("Rentals Check-In Approval Required", tracking=True)
    approval_required_dest_member = fields.Boolean("All Members Approval Required", tracking=True)
    approval_required_dest_membership_member = fields.Boolean("Membership Member Approval Required", tracking=True)
    approval_required_dest_accommodation_member = fields.Boolean("Rental Member Approval Required", tracking=True)
    
    def count_pricerule(self):
        for record in self:
            record.pricerule_count = len(record.pricerule_ids)
            
    def count_member(self):
        for record in self:
            record.member_count = len(record.member_ids.filtered(lambda r: r.membership_active))
            record.active_member_count = len(record.member_ids.filtered(lambda r: r.membership_state == 'active' and r.membership_active))
    
    def count_guest(self):
        for record in self:
            getrealcount = record.guest_ids.filtered(lambda r: r.checkin_date and r.state != 'cancel')
            record.guest_count = len(getrealcount)
            record.checkedin_guest_count = len(record.guest_ids.filtered(lambda r: r.state == 'checked-in'))
    
    def count_member_activity(self):
        for record in self:
            getrealcount = record.member_activity_ids.filtered(lambda r: r.checkin_date)
            record.member_activity_count = len(getrealcount)
            record.checkedin_member_count = len(record.member_ids.filtered(lambda r: r.member_access_status == 'checked-in'))
    
    def count_membership(self):
        for record in self:
            record.membership_count = len(record.membership_ids)
            record.active_membership_count = len(record.membership_ids.filtered(lambda r: r.state == 'active'))
            
    def action_view_pricerule(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "destination.price",
            "domain": [('dest_id', '=', self.id)],
            "context": {'default_dest_id':self.id, 'default_lock_dest_id':True},
            "name": "Price Rules",
            "view_mode": "tree,form",
             }
        return result
    
    def action_view_membership(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "destination.membership",
            "domain": [('dest_id', '=', self.id)],
            "context": {'default_dest_id':self.id, 'default_lock_dest_id':True},
            "name": "Rentals",
            "view_mode": "tree,form",
             }
        return result
    
    def action_view_member(self):
        self.ensure_one()
        result = {
            "name": "Members",
            "type": "ir.actions.act_window",
            "res_model": "destination.membership.member",
            "domain": [('dest_id', '=', self.id),('membership_active','=',True)],
            "context": {'default_dest_id':self.id, 'default_lock_dest_id':True},
            "view_mode": "tree,form,search",
             }
        return result
    
    def action_view_guest(self):
        self.ensure_one()
        treeview = self.env.ref("destinations.destination_guest_list_view").id
        formview = self.env.ref("destinations.destination_guest_form_view").id
        searchview = self.env.ref("destinations.destination_guest_search_view").id
        result = {
            "name": "Guest Access",
            "type": "ir.actions.act_window",
            "res_model": "destination.guest",
            "domain": [('dest_id', '=', self.id)],
            "context": {'default_dest_id':self.id, 'default_lock_dest_id':True},
            'views' : [(treeview,'tree'),(formview,'form'),(searchview,'search')],
            "view_mode": "tree,form,search",
             }
        return result
    
    def action_view_member_activity(self):
        self.ensure_one()
        result = {
            "name": "Member Activities",
            "type": "ir.actions.act_window",
            "res_model": "destination.membership.member.activity",
            "domain": [('dest_id', '=', self.id)],
            "context": {'default_dest_id':self.id},
            "view_mode": "tree",
             }
        return result
    
    @api.onchange('product_tmpl_ids')
    def _compute_dest_product_count(self):
        for record in self:
            matchingproduct = self.env['product.template'].search([('dest_ok','=',True),('dest_id','=',record.id)])
            record.product_count = len(matchingproduct)
    
    
    def action_view_product(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "domain": [('dest_id', '=', self.id)],
            "context": {'default_dest_ok':True, 'default_lock_dest_ok':True, 'default_dest_id':self.id, 'default_lock_dest_id':True},
            "name": "Products",
            "view_mode": "tree,form",
             }
        return result
    
    


    def name_get(self):
        res = []
        for record in self:
            name = record.name
            if record.code:
                name = '%s (%s)' % (name, record.code)
            res.append((record.id, name))
        return res
        return super(Destination, self).name_get()
 
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs.ids:
            return super(Destination, self).name_search(name=name, args=args,
                                                       operator=operator,
                                                       limit=limit)
        return recs.name_get()