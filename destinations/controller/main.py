# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError

class GuestForm(http.Controller):
    
    @http.route(['/memberships'], type='http', auth="user", website=True)
    def memberships_portal(self, **post):
        partner = request.env['res.users'].browse(request.env.uid).partner_id
        #members = request.env['destination.membership.member'].sudo().search([]).filtered(lambda r: r.membership_id.state == 'active' and r.state == 'active' and r.membership_type in ['super','main'] and r.partner_id == partner)
        members = request.env['destination.membership.member'].search([])
        return request.render("destinations.dest_online_memberships", {'partner':partner,'members':members})
    
    @http.route(['/guest-time'], type='http', auth="user", website=True)
    def memberships_guest_time(self, **post):
        partner = request.env['res.users'].browse(request.env.uid).partner_id
        member = request.env['destination.membership.member'].sudo().search([('id','=',post.get('member_id'))])
        getcurdate = datetime.now().strftime("%Y-%m-%d")
        getcurtime = datetime.now().strftime("%H:%M")
        
        return request.render("destinations.dest_online_guests_datetime", {'partner':partner,'member':member,'getcurdate':getcurdate,'getcurtime':getcurtime})
    
    @http.route(['/guest'], type='http', auth="user", website=True)
    def memberships_guests(self, **post):
        partner = request.env['res.users'].browse(request.env.uid).partner_id
        member = request.env['destination.membership.member'].sudo().search([('id','=',post.get('member_id'))])
        access_date = post.get('access_date')
        access_time = post.get('access_time')
        
        return request.render("destinations.dest_online_guests", {'partner':partner,'member':member,'access_date':access_date,'access_time':access_time})


    @http.route(['/guest/form'], type='http', auth="user", website=True)
    def guest_form(self, **post):
        partner = request.env['res.users'].browse(request.env.uid).partner_id
        member = post.get('member_id')
        access_date = post.get('access_date')
        access_time = post.get('access_time')
        getcurdate = datetime.strptime(access_date+'T'+access_time,"%Y-%m-%dT%H:%M")

        return request.render("destinations.tmp_guest_form", {'partner':partner,'member':member,'getcurdate':getcurdate})
    
    
    @http.route(['/guest/form/submit'], type='http', auth="user", website=True)
    def guest_form_submit(self, **post):
        partner = request.env['res.users'].browse(request.env.uid).partner_id
        member = request.env['destination.membership.member'].sudo().search([('id','=',post.get('member_id'))])
            
        if member.partner_id.id != partner.id:
            vals = {}
            return request.render("destinations.tmp_guest_form_error", vals)
            
        guest = request.env['destination.guest.invite'].sudo().create({
        
            'name': member.name + '(' + post.get('guest_name') + ')',
            'partner_id': partner.id,
            'member_id': member.id,
            'access_date': datetime.strptime(post.get('access_date'),"%Y-%m-%dT%H:%M"),
            
            'guest_name': post.get('guest_name'),
            'guest_mobile': post.get('guest_mobile'),
            'guest_id_number': post.get('guest_id_number'),
            'guest_gender': post.get('guest_gender'),
            
            'guest_age': post.get('guest_age'),
            'guest_type': post.get('guest_type'),
            'token_type': post.get('token_type'),
            'is_helper': post.get('is_helper'),
            'is_favorite': post.get('is_favorite'),
            
        })
        vals = {
            'guest': guest,
        }
        return request.render("destinations.tmp_guest_form_success", vals)
    

    
    @http.route(['/guest/form-favorite'], type='http', auth="user", website=True)
    def fav_guest_form(self, **post):
        partner = request.env['res.users'].browse(request.env.uid).partner_id
        member = post.get('member_id')
        access_date = post.get('access_date')
        access_time = post.get('access_time')
        getcurdate = datetime.strptime(access_date+'T'+access_time,"%Y-%m-%dT%H:%M")
        favorites = request.env['destination.guest.invite'].sudo().search([('partner_id','=',partner.id),('is_favorite','=',True)])
        return request.render("destinations.fav_guest_form", {'partner':partner,'member':member,'getcurdate':getcurdate,'favorites':favorites})
    
    
    @http.route(['/guest/form-favorite/submit'], type='http', auth="user", website=True)
    def fav_guest_form_submit(self, **post):
        partner = request.env['res.users'].browse(request.env.uid).partner_id
        member = request.env['destination.membership.member'].sudo().search([('id','=',post.get('member_id'))])
        fav_guest = request.env['destination.guest.invite'].sudo().search([('id','=',post.get('fav_guest_id'))])
            
        if member.partner_id.id != partner.id:
            vals = {}
            return request.render("destinations.tmp_guest_form_error", vals)
            
        guest = request.env['destination.guest.invite'].sudo().create({
        
            'name': fav_guest.member_id.name + '(' + fav_guest.guest_name + ')',
            'partner_id': partner.id,
            'member_id': member.id,
            'access_date': datetime.strptime(post.get('access_date'),"%Y-%m-%dT%H:%M"),
            
            'guest_name': fav_guest.guest_name,
            'guest_mobile': fav_guest.guest_mobile,
            'guest_id_number': fav_guest.guest_id_number,
            'guest_gender': fav_guest.guest_gender,
            
            'guest_age': fav_guest.guest_age,
            'guest_type': post.get('guest_type'),
            'token_type': post.get('token_type'),
            'is_helper': fav_guest.is_helper,
            
        })
        vals = {
            'guest': guest,
        }
        return request.render("destinations.tmp_guest_form_success", vals)