# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import datetime
import pytz
from pytz import timezone, UTC
import json
from lxml import etree
import math
from odoo.tools import float_compare, format_datetime, format_time


class Partner(models.Model):
    _name = "res.partner"
    _inherit = ['res.partner']
    

    has_active_membership = fields.Boolean(string='Has Active Rentals', readonly=True, compute='compute_active_membership')
    id_number = fields.Char(string="ID Number", tracking=True)
    partnergender = fields.Selection([('male', 'Male'), ('female','Female')], string="Partner Gender", required=True, tracking=True)

    member_ids = fields.One2many('destination.membership.member', 'partner_id', string = 'Rentals', readonly=True)
    member_count = fields.Integer(string='Rental Count', compute='count_member', readonly=True)
    
    def count_member(self):
        for record in self:
            record.member_count = len(record.member_ids)

    
    membership_ids = fields.One2many('destination.membership', 'partner_id', string = 'Rental Orders', readonly=True)
    membership_count = fields.Integer(string='Rental Count', compute='count_membership', readonly=True)
    
    def count_membership(self):
        for record in self:
            record.membership_count = len(record.membership_ids)

    
    def compute_active_membership(self):
        for record in self:
            getmemberships = self.env['destination.membership.member'].search([('partner_id','=',record.id),('membership_state','=','active')])
            if getmemberships:
                record.has_active_membership = True
            else:
                record.has_active_membership = False
    
    def action_view_membership(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "destination.membership",
            "domain": [('partner_id', '=', self.id)],
            "context": {'default_partner_id':self.id, 'default_lock_partner_id':True},
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
            "domain": [('partner_id','=', self.id)],
            "context": {'default_partner_id':self.id, 'default_lock_partner_id':True},
            "view_mode": "tree,form,search",
             }
        return result
        
    def show_memberships(self):
        action = self.env['ir.actions.act_window']._for_xml_id('destinations.destination_memberships_act_window')
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = "{'edit': 0,'create': 0}"
        return action
    
    @api.constrains('id_number')
    def _check_id_number_unicity(self):
        if self.id_number and self.env['res.partner'].search_count([('id_number', '=', self.id_number)]) > 1:
            raise ValidationError('ID Number exist already!')
            
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.search(['|', ('id_number', operator, name), ('mobile', operator, name)] + args, limit=limit)
        if not recs.ids:
            return super(Partner, self).name_search(name=name, args=args,
                                                       operator=operator,
                                                       limit=limit)
        return recs.name_get()

    
    active_membership_ids = fields.Many2many('destination.membership', string="Active Memberships", compute='_get_active_memberships', search="_search_active_rental_ids")
    active_membership_ids_count = fields.Integer(string='Active Memberships Count', compute='_get_active_memberships')
    all_membership_ids = fields.Many2many('destination.membership', string="All Memberships", compute='_get_active_memberships', search="_search_all_rental_ids")
    all_membership_ids_count = fields.Integer(string='All Memberships Count', compute='_get_active_memberships')
    
    def _get_active_memberships(self):
        for record in self:
            activememberships = self.env['destination.membership.member'].search([('state','=','active')]).filtered(lambda r: r.partner_id == record).membership_id.filtered(lambda r: r.state == 'active')
            record.active_membership_ids = activememberships
            record.active_membership_ids_count = len(activememberships)
            
            allmemberships = self.env['destination.membership.member'].search([('state','=','active')]).filtered(lambda r: r.partner_id == record).membership_id.filtered(lambda r: r.state in ['active','hold','checked-out','late','done'])
            record.all_membership_ids = allmemberships
            record.all_membership_ids_count = len(allmemberships)
            
            
    def _search_active_rental_ids(self, operator, value):
        
        return [('member_ids.membership_id', operator, value)]
    
    def _search_all_rental_ids(self, operator, value):
        
        return [('member_ids.membership_id', operator, value)]
    
    
    guest_ids = fields.One2many('destination.guest', 'guest_id', string = 'Guest Access')
    guest_count = fields.Integer(string='Guest Access', compute='count_guest')
    
    member_activity_ids = fields.One2many('destination.membership.member.activity', 'partner_id', string = 'Member Access')
    member_activity_count = fields.Integer(string='Member Access', compute='count_member_activity')
    
    invitation_ids = fields.One2many('destination.guest', 'partner_id', string= 'Invitation')
    invitation_count = fields.Integer(string='Invitations', compute='count_guest')
    
    def count_guest(self):
        for record in self:
            getrealcount = record.guest_ids.filtered(lambda r: r.processin_date and r.state != 'cancel')
            record.guest_count = len(getrealcount)
            getrealcount2 = record.invitation_ids.filtered(lambda r: r.processin_date and r.state != 'cancel')
            record.invitation_count = len(getrealcount2)
            
    
    def count_member_activity(self):
        for record in self:
            getrealcount = record.member_activity_ids.filtered(lambda r: r.checkin_date)
            record.member_activity_count = len(getrealcount)
            
            
    def action_view_guest(self):
        self.ensure_one()
        treeview = self.env.ref("destinations.destination_guest_list_view").id
        formview = self.env.ref("destinations.destination_guest_form_view").id
        searchview = self.env.ref("destinations.destination_guest_search_view").id
        result = {
            "name": "Guest Registry",
            "type": "ir.actions.act_window",
            "res_model": "destination.guest",
            "domain": [('guest_id', '=', self.id)],
            "context": {'create':0},
            'views' : [(treeview,'tree'),(formview,'form'),(searchview,'search')],
            "view_mode": "tree,form,search",
             }
        return result
               
    def action_view_member_activity(self):
        self.ensure_one()
        result = {
            "name": "Member Registry",
            "type": "ir.actions.act_window",
            "res_model": "destination.membership.member.activity",
            "domain": [('partner_id', '=', self.id)],
            "context": {'create':0},
            "view_mode": "tree",
             }
        return result
    
    def action_view_invitation(self):
        self.ensure_one()
        treeview = self.env.ref("destinations.destination_guest_list_view").id
        formview = self.env.ref("destinations.destination_guest_form_view").id
        searchview = self.env.ref("destinations.destination_guest_search_view").id
        result = {
            "name": "Guest Registry",
            "type": "ir.actions.act_window",
            "res_model": "destination.guest",
            "domain": [('partner_id', '=', self.id)],
            "context": {'create':0},
            'views' : [(treeview,'tree'),(formview,'form'),(searchview,'search')],
            "view_mode": "tree,form,search",
             }
        return result
    
    
    def action_view_memberships(self):
        self.ensure_one()
        result = {
            "name": "Member Registry",
            "type": "ir.actions.act_window",
            "res_model": "destination.membership.member.activity",
            "domain": [('partner_id', '=', self.id)],
            "context": {'create':0},
            "view_mode": "tree",
             }
        return result
    
    def action_view_memberships(self):
        self.ensure_one()
        result = {
            "type": "ir.actions.act_window",
            "res_model": "destination.membership.member",
            "domain": [('partner_id', '=', self.id),('membership_state','in',['active','hold','checked-out','late','done'])],
            "context": {'create':0},
            "name": "Memberships",
            "view_mode": "tree",
             }
        return result