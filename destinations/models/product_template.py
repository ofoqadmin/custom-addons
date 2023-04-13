# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
import math
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"
    dest_ok = fields.Boolean(string="Destination Product", copy=True, index=True, tracking=True)
    lock_dest_ok = fields.Boolean(store=False, copy=False, default=False)
    dest_id = fields.Many2one('destination.destination', string='Entity', tracking=True, index=True, copy=True)
    
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    
    dest_publish = fields.Boolean(string="Destination Publish", copy=True, default=True)
    product_unavailability = fields.One2many('destination.product.unavailability','product_id',string="Product Unavailability", auto_join=True, copy=True, tracking=True)
    lock_dest_id = fields.Boolean(store=False, copy=False, default=False)
    dest_quantity = fields.Integer(string="Quantity", copy=True, default='1', tracking=True)
    dest_price_monday = fields.Float(string="Price Monday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_tuesday = fields.Float(string="Price Tuesday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_wednesday = fields.Float(string="Price Wednesday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_thursday = fields.Float(string="Price Thursday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_friday = fields.Float(string="Price Friday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_saturday = fields.Float(string="Price Saturday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_price_sunday = fields.Float(string="Price Sunday", digits='Product Price', default='1', store=True, copy=True, tracking=True)
    dest_product_group = fields.Selection([('accommodation', 'Rental'), ('membership', 'Membership'), ('access', 'Access'), ('others', 'Others')], string="Product Group", default='accommodation', store=True, copy=True, tracking=True)
    dest_custom_price = fields.Selection([('weekday_rate', 'Variable Weekday Rate'), ('daily_rate', 'Variable Daily Rate'), ('fixed', 'Fixed Rate')], string="Pricing Type", default='fixed', store=True, copy=True, tracking=True)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', ondelete='restrict', tracking=True, store=True, copy=True)
    dest_product_code = fields.Char(string='Code', required=True, size=4, copy=False, tracking=True)
    dest_member_count = fields.Integer(string="Max. Capacity", copy=True, size="3", tracking=True)
    dest_member_male_count = fields.Integer(string="Male Cap", copy=True, size="3", tracking=True)
    dest_member_female_count = fields.Integer(string="Female Cap", copy=True, size="3", tracking=True)
    
    dest_member_access_monday = fields.Boolean(store=True, copy=True, string="Monday", default=True, tracking=True)
    dest_member_access_tuesday = fields.Boolean(store=True, copy=True, string="Tuesday", default=True, tracking=True)
    dest_member_access_wednesday = fields.Boolean(store=True, copy=True, string="Wednesday", default=True, tracking=True)
    dest_member_access_thursday = fields.Boolean(store=True, copy=True, string="Thursday", default=True, tracking=True)
    dest_member_access_friday = fields.Boolean(store=True, copy=True, string="Friday", default=True, tracking=True)
    dest_member_access_saturday = fields.Boolean(store=True, copy=True, string="Saturday", default=True, tracking=True)
    dest_member_access_sunday = fields.Boolean(store=True, copy=True, string="Sunday", default=True, tracking=True)
    
    dest_guest_gender_male = fields.Boolean(string="Male", default=True, tracking=True)
    dest_guest_single_male = fields.Boolean(string="Single Male", default=False, tracking=True)
    dest_guest_gender_female = fields.Boolean(string="Female", default=True, tracking=True)
    dest_guest_count_rule = fields.Boolean(string="Count as Guest?", default=True, tracking=True)
    
    dest_daily_guest_count = fields.Integer(string="Daily Guest Allocation", copy=True, tracking=True)
    dest_daily_guest_male_count = fields.Integer(string="Daily Male Guest Allocation", copy=True, tracking=True)
    dest_daily_guest_male_single_count = fields.Integer(string="Daily Single Male Guest Allocation", copy=True, tracking=True)
    dest_daily_guest_female_count = fields.Integer(string="Daily Female Guest Allocation", copy=True, tracking=True)
    
    dest_month_free_guest_count = fields.Integer(string="Monthly Free Guest Allocation", copy=True, tracking=True)
    dest_product_security_deposit = fields.Selection([('percent', 'Percentage'), ('fixed', 'Fixed Amount')], store=True, copy=True, string="Security Deposit", tracking=True)
    dest_product_security_deposit_product = fields.Many2one('product.product', string="Security Deposit Product", ondelete='restrict', store=True, copy=True, tracking=True)
    dest_product_security_deposit_amount = fields.Float(string="Deposit Amount", digits='Product Price', default='500', store=True, copy=True, tracking=True)
    dest_product_security_deposit_percent = fields.Float(string="Deposit Percentage", default='30', store=True, copy=True, tracking=True)
    dest_invoice_policy = fields.Selection([('order', 'At Order'), ('return', 'At Return')], string="Invoice Policy", required=True, default='order', store=True, copy=True, tracking=True)                                          
    dest_rental_pricing_ids = fields.One2many('destination.product.variabledaily.lines', 'product_template_id',string="Rental Pricings", auto_join=True, copy=True, tracking=True)
    dest_checkin_time = fields.Float(string="Check-In Time", store=True, copy=True, default=0.0, tracking=True)
    dest_checkout_time = fields.Float(string="Check-Out Time", store=True, copy=True, default=0.0, tracking=True)
    
    dest_access_start_time = fields.Float(string="Access Start Time", store=True, copy=True, default=0.0, tracking=True)
    dest_access_duration = fields.Float(string="Access Duration", store=True, copy=True, default=0.0, tracking=True)
    
    dest_access_pricing_ids = fields.One2many('destination.product.access.price.lines', 'product_id', string="Access Pricings", copy=True, tracking=True)
    dest_access_clone_pricing_ids = fields.Many2one('product.template', domain="[('dest_id','=',dest_id),('dest_product_group','=','access')]", string="Clone From", store=True)
    
    membership_ids = fields.One2many('destination.membership', 'product_tmpl_id', string='Rentals', tracking=True, groups='destinations.destination_admin_group,destinations.destination_super_admin_group,destinations.destination_accounting_group,destinations.destination_sales_group,destinations.destination_guest_process_group,destinations.destination_guest_checking_group,destinations.destination_guest_registration_group')
    membership_count = fields.Integer('Rentals', compute='count_membership')
    
    pricerule_ids = fields.One2many('destination.price', 'product_tmpl_id', string = 'Price Rule')
    pricerule_count = fields.Integer(string='Price Rule Count', compute='count_pricerule')
    
    approval_required_product = fields.Boolean("Check-In Approval", tracking=True)
    approval_required_product_member = fields.Boolean("Member Approval", tracking=True)
    
    #access_products
    access_products_ids = fields.One2many('product.access.cap','product_id', string="Access Products", tracking=True)
    access_products_clone_product_id = fields.Many2one('product.template', domain="[('dest_id','=',dest_id),('dest_product_group','in',['accommodation','membership'])]", string="Clone From", store=True)
    access_product_member = fields.Boolean("Member Access", default=True, copy=True, tracking=True)
    access_product_guest = fields.Boolean("Guest Access", default=True, copy=True, tracking=True)
    access_product_code_required = fields.Boolean("Access Code Required", default=True, copy=True, tracking=True)
    
    # Location field 
    location_custom = fields.Char("Location", tracking=True)
    
    def count_membership(self):
        for record in self:
            record.membership_count = len(record.membership_ids)
            
    def count_pricerule(self):
        for record in self:
            record.pricerule_count = len(record.pricerule_ids)

    def action_view_pricerule(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "destination.price",
            "domain": [('product_id', '=', self.id)],
            "context": {'default_dest_id':self.dest_id.id, 'default_lock_dest_id':True, 'default_product_id':self.product_variant_id.id, 'default_lock_product_id':True},
            "name": "Price Rules",
            "view_mode": "tree,form",
             }
        return result
        
    def action_view_membership(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "destination.membership",
            "domain": [('product_tmpl_id', '=', self.id)],
            "context": {'default_dest_id':self.dest_id.id, 'default_lock_dest_id':True, 'default_product_id':self.product_variant_id.id, 'default_lock_product_id':True},
            "name": "Rentals",
            "view_mode": "tree,form,calendar",
             }
        return result
            
    @api.constrains('dest_id','dest_product_code')
    def _check_duplicate_dest(self):
        for record in self:
            prodids = self.search([('dest_id', '=', record.dest_id.id),('dest_product_code','=',self.dest_product_code), ('id', '!=', record.id)])
            if len(prodids) >= 1 and record.dest_ok:
                raise ValidationError("Product Code must be unique within each Entity")
       
    
    def action_view_dest(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "destination.destination",
            "res_id": self.dest_id.id,
            "view_mode": "form",
             }
        return result
    
    
    
    
    def action_view_calendar(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "destination.membership",
            "domain": [('product_tmpl_id','=',self.id)],
            "view_mode": "calendar",
             }
        return result
    
    def clone_access_products(self):
        
        if self.access_products_clone_product_id:
                self.write({'access_products_ids': [(5, 0, 0)]})
                getcaprecs = self.access_products_clone_product_id.access_products_ids
                for line in getcaprecs:
                    line_dict = {'sequence':line.sequence,
                                 'cap':line.cap,
                                 'period':line.period,
                                 'free_guest':line.free_guest,
                                 'product_ids': line.product_ids,
                                }
                    self.write({'access_products_ids': [(0, 0, line_dict)]})
                    
    def clone_access_pricings(self):
        
        if self.dest_access_clone_pricing_ids:
                self.write({'dest_access_pricing_ids': [(5, 0, 0)]})
                getcaprecs = self.dest_access_clone_pricing_ids.dest_access_pricing_ids
                for line in getcaprecs:
                    line_dict = {'sequence':line.sequence,
                                 'product_id':line.product_id,
                                 'access_weekday':line.access_weekday,
                                 'access_time_start':line.access_time_start,
                                 'access_time_end': line.access_time_end,
                                 'access_duration': line.access_duration,
                                 'duration': line.duration,
                                 'weekday_duration': line.weekday_duration,
                                 'check': line.check,
                                 'price': line.price,
                                }
                    self.write({'dest_access_pricing_ids': [(0, 0, line_dict)]})
            

