# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError, Warning
import datetime
import pytz
from pytz import timezone, UTC
import json
from lxml import etree
import math
from odoo.tools import float_compare, format_datetime, format_time


class DestinationGuestInvite(models.Model):
    _name = "destination.guest.invite"
    _description = "Guest Invite"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "access_date"

    name = fields.Text(string='Reference')
    
    partner_id = fields.Many2one('res.partner', string='Partner')
    
    member_id = fields.Many2one('destination.membership.member', domain="[('partner_id','=', partner_id)]")
    membership_id = fields.Many2one('destination.membership', string='Rental', ondelete='restrict', related='member_id.membership_id')
    dest_id = fields.Many2one('destination.destination', string='Entity', related='member_id.membership_id.dest_id')

    access_date = fields.Datetime(string="Token Start")
    access_date_date = fields.Datetime(string="Token Start")
  
    guest_name = fields.Char('Guest Name')
    guest_mobile = fields.Char('Guest Mobile')
    guest_id_number = fields.Char('Guest ID Number')
    guest_gender = fields.Selection([('male', 'Male'), ('female','Female')], string="Gender")
    
    guest_age = fields.Selection([('adult', 'Adult (16+)'), ('teenager','Teenager (13-15)'), ('child','Child (< 13)')], string="Age Group", default='adult')
    guest_type = fields.Selection([('single', 'Single'), ('couple','Couple')], string="Entry", default='single')
    token_type = fields.Selection([('guest', 'Guest Pay'),('free', 'Free'),('member', 'Member Pay')], string="Payment", default='guest')
    is_helper = fields.Boolean("Domestic Helper")
    is_favorite = fields.Boolean("Add to Favorite")
    
