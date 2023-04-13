from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import datetime
import pytz
import json




class MembershipMembers(models.Model):
    _name = "destination.membership.member"
    _description = "Member"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    partner_id = fields.Many2one('res.partner', string='Member', ondelete='restrict', tracking=True, store=True, copy=True, required=True, domain="[('is_company','=',False)]")    
    lock_partner_id = fields.Boolean(store=False, copy=False, default=False)
    partnergender = fields.Selection([('male', 'Male'), ('female','Female')], string="Partner Gender", related='partner_id.partnergender', store=True, tracking=True)
    name = fields.Text(string='Reference', required=True, copy=False, default=lambda self: _('New'), tracking=True)
    membership_id = fields.Many2one('destination.membership', string='Rental', ondelete='cascade', tracking=True, domain="[('dest_id','=',dest_id)]", required=True)
    lock_membership_id = fields.Boolean(store=False, copy=False, default=False)
    membership_type = fields.Selection([('super', 'Super Member'), ('main', 'Main Member'), ('member', 'Member'),('guest', 'Guest Member')], store=True, copy=True, required=True, default='member', tracking=True)
    active = fields.Boolean(string="Active", tracking=True, default=True)
    product_id = fields.Many2one('product.product', string='Product', related='membership_id.product_id', store=True)
    product_categ_id = fields.Many2one('product.category', "Product Category", related="product_id.categ_id", store=True)
    dest_product_group = fields.Selection([('accommodation', 'Rental'), ('membership', 'Membership'), ('access', 'Access'), ('others', 'Others')], string="Product Group", related='product_id.dest_product_group',  store=True)
    dest_custom_price = fields.Selection([('weekday_rate', 'Variable Weekday Rate'), ('daily_rate', 'Variable Daily Rate'), ('fixed', 'Fixed Rate')], string="Pricing Type", related='product_id.dest_custom_price',   store=True)
    member_image = fields.Binary(string="Image", related='partner_id.image_1920')
    dest_id = fields.Many2one('destination.destination', string='Entity', tracking=True, index=True, copy=True, default=lambda self: self._get_default_dest_id())
    def _get_default_dest_id(self):
        conf = self.env['destination.destination'].search(['|',('user_ids.user_id','=',self.env.user.id),('manager_ids.user_id','=',self.env.user.id)], limit=1)
        return conf.id
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    lock_dest_id = fields.Boolean(store=False, copy=False, default=False)
    product_id_dest_code = fields.Char(string='Entity Code', related='product_id.dest_id.code')
    start_date = fields.Datetime(string='Start Date', related='membership_id.start_date')
    end_date = fields.Datetime(string='End Date', related='membership_id.end_date')
    state = fields.Selection([('active', 'Active'), ('inactive','Inactive'),('pending', 'Pending Approval')], string="Member Status", readonly=True, required=True, tracking=True, default='pending')
    is_manager = fields.Boolean(string="Is Manager", compute='_is_manager')
    rental_partner_default_category_ids = fields.Many2many('res.partner.category', 'destination_rental_default_ids',string='Rental Partner Default Tags', related='dest_id.rental_partner_default_category_ids')
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")
    membership_code = fields.Char(string='Code', related="membership_id.membership_code")   
    
    #kanban fields
    member_name = fields.Char("Name", related='partner_id.name')
    member_phone = fields.Char('Member Phone', related='partner_id.phone')
    member_mobile = fields.Char('Member Mobile', related='partner_id.mobile')
    member_id_number = fields.Char('Member ID Number', related='partner_id.id_number')
    
    
    dest_product = fields.Char("Destination", compute='compute_dest_product')
    is_blacklist = fields.Boolean("Blacklist", compute='compute_blacklist', default=False)
    access_permission = fields.Boolean("Access Permission", compute='compute_access_permission', default=False)
    is_access_late = fields.Boolean("Is Late", compute='compute_is_late', default=False)
    member_activity_ids = fields.One2many('destination.membership.member.activity','member_id',string="Activities")
    current_activity_id = fields.Many2one('destination.membership.member.activity', string="Last Activity", ondelete='restrict')
    
    #current session fields
    current_access_date = fields.Datetime(string="Token Start", tracking=True)
    current_expiry_date = fields.Datetime(string="Token Expiry", tracking=True) 
    current_processin_date = fields.Datetime(string="Process-In Date", tracking=True)
    current_checkin_date = fields.Datetime(string="Check-In Date", tracking=True)
    current_checkout_date = fields.Datetime(string="Check-Out Date", tracking=True)
    
    member_access_status = fields.Selection([
        ('inprocess', 'In-Process'),
        ('checked-in', 'Checked-In'),
        ('checked-out', 'Checked-Out'),
        ], string='Access Status', default='checked-out', tracking=True)
    
    approval_required = fields.Boolean(string="Approval Required", copy=True, compute="get_approval_rules")
    
    
    @api.onchange('product_id','dest_id')
    @api.depends('product_id','dest_id')
    def get_approval_rules(self):
        for record in self:
            if record.product_id and record.dest_id:
                if record.product_id.approval_required_product_member or record.dest_id.approval_required_dest_member or (record.product_id.dest_product_group == 'accommodation' and record.dest_id.approval_required_dest_accommodation_member) or (record.product_id.dest_product_group == 'membership' and record.dest_id.approval_required_dest_membership_member):
                    record.approval_required = True
                else:
                    record.approval_required = False
            else:
                record.approval_required = False
    
    
    def write(self, vals):
        
        if ('dest_id' in vals or 'membership_id' in vals or 'partner_id' in vals or 'membership_type' in vals) and self.approval_required == True:
            vals['state'] = 'pending'
        result = super(MembershipMembers, self).write(vals)
        return result  

    
    
    @api.onchange('dest_id')
    @api.depends('dest_id')
    def _is_manager(self):
        for record in self:
            record.is_manager = (True if record.env.user.id in record.dest_id.manager_ids.user_id.ids else False)
    
    
    membership_state = fields.Selection([
    ('new', 'Draft'),
    ('pending', 'Pending Approval'),
    ('approved', 'Approved'),
    ('confirmed', 'Confirmed'),
    ('active', 'Active'),
    ('hold', 'On Hold'),
    ('checked-out', 'Checked-Out'),
    ('expired', 'Expired'),
    ('done', 'Done'),
    ('cancel','Cancelled'),
    ('late','Late'),
    ], string='Rental Status', tracking=True, related='membership_id.state')
    
    membership_active = fields.Boolean("Active", related='membership_id.active')
    
    @api.onchange('dest_id')
    def reset_membership_id(self):
        if 'default_membership_id' in self.env.context:
            if not self.env.context['default_membership_id']:
                self.membership_id = False
        else:
            self.membership_id = False
            

    
    
    def compute_dest_product(self):
        for record in self:
            record.dest_product = '%s (%s)' % (record.dest_id.code, record.product_id.dest_product_code) 
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            partnerid = vals.get('partner_id')
            membershipid = vals.get('membership_id') or self.env.context.get('default_membership_id')
            partnerrec = self.env['res.partner'].search([('id','=',partnerid)])
            membershiprec = self.env['destination.membership'].search([('id','=',membershipid)])
            if membershiprec.membership_code:
                vals['name'] = partnerrec.name + ' (' + membershiprec.dest_id.code + '/' + membershiprec.product_id.dest_product_code + '/' + membershiprec.membership_code + ')'
            else:
                vals['name'] = partnerrec.name + ' (' + membershiprec.dest_id.code + '/' + membershiprec.product_id.dest_product_code + ')'
            
        if 'membership_id' in vals or 'default_membership_id' in self.env.context:
            partnerid = vals.get('partner_id')
            partnerrec = self.env['res.partner'].search([('id','=',partnerid)])
            membershipid = vals.get('membership_id') or self.env.context.get('default_membership_id')
            quota = self.env['destination.membership'].search([('id','=',membershipid)]).dest_member_count
            malequota = self.env['destination.membership'].search([('id','=',membershipid)]).dest_member_male_count
            femalequota = self.env['destination.membership'].search([('id','=',membershipid)]).dest_member_female_count
            actualcount = len(self.env['destination.membership.member'].search([('membership_id','=',membershipid)]))
            actualmalecount = len(self.env['destination.membership.member'].search([('membership_id','=',membershipid)]).filtered(lambda r: r.partner_id.partnergender == 'male'))
            actualfemalecount = len(self.env['destination.membership.member'].search([('membership_id','=',membershipid)]).filtered(lambda r: r.partner_id.partnergender == 'female'))
            if partnerrec.partnergender == 'male':
                if actualcount < quota and actualmalecount < malequota:
                    vals['state'] = 'active'
                else:
                    vals['state'] = 'pending'
            elif partnerrec.partnergender == 'female':
                if actualcount < quota and actualfemalecount < femalequota:
                    vals['state'] = 'active'
                else:
                    vals['state'] = 'pending'
            else:
                raise UserError("Gender is not defined!")
        result = super(MembershipMembers, self).create(vals)
        return result         
    
    @api.onchange('partner_id')
    @api.depends('partner_id')
    def change_name(self):
        for record in self:
            if record.partner_id and record.membership_id:
                if record.membership_id.membership_code:
                    record.name = record.partner_id.name + ' (' + record.membership_id.dest_id.code + '/' + record.membership_id.product_id.dest_product_code + '/' + record.membership_id.membership_code + ')' or _('New')
                else:
                    record.name = record.partner_id.name + ' (' + record.membership_id.dest_id.code + '/' + record.membership_id.product_id.dest_product_code + ')' or _('New')
    
   
    @api.constrains('membership_id', 'partner_id')
    def _check_duplicate(self):
        for record in self:
            member_ids = self.search([('membership_id', '=', record.membership_id.id), ('partner_id','=',record.partner_id.id), ('id', '<>', record.id)])
            if len(member_ids) >= 1:
                raise ValidationError("Cannot add same member twice.")
            if self.dest_id.partner_id_required and not self.partner_id.id_number:
                raise ValidationError(_('Member ID is required.'))
            if self.dest_id.partner_gender_required and not self.partner_id.partnergender:
                raise ValidationError(_('Member Gender is required.'))
            if self.dest_id.partner_email_required and not self.partner_id.email:
                raise ValidationError(_('Member Email is required.'))
            if self.dest_id.partner_phone_required and not self.partner_id.phone:
                raise ValidationError(_('Member Phone is required.'))
            if self.dest_id.partner_mobile_required and not self.partner_id.mobile:
                raise ValidationError(_('Member Mobile is required.'))
            
    
    def name_get(self):
        res = []
        for record in self:
            if record.membership_id.membership_code:
                name = '%s (%s/%s/%s)' % (record.partner_id.name, record.membership_id.dest_id.code, record.membership_id.product_id.dest_product_code, record.membership_id.membership_code)
            else:
                name = '%s (%s/%s)' % (record.partner_id.name, record.membership_id.dest_id.code, record.membership_id.product_id.dest_product_code)
            res.append((record.id, name))
        return res
        return super(MembershipMembers, self).name_get()
 
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.search(['|','|','|',('membership_code', operator, name),('member_phone', operator, name),('member_mobile', operator, name),('member_id_number', operator, name)] + args, limit=limit)
        if not recs.ids:
            return super(MembershipMembers, self).name_search(name=name, args=args,
                                                       operator=operator,
                                                       limit=limit)
        return recs.name_get()

    
    
    @api.onchange('partner_id')
    def check_partner_values(self):
        
        
        return {'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'res.partner',
                'res_id': self.partner_id.id,
        }
                
    
    def request_approval(self):
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership.member')]).id),
                        ('summary','=','Request Member Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.unlink()
            
        self.state = 'pending'
        
        check_authorizer = self.product_id.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'authorizer')
        
        if check_authorizer:
            managers = check_authorizer
        else:
            managers = self.product_id.dest_id.manager_ids
        
        for manager in managers:
            todos = {
            'res_id': self.id,
            'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.membership.member')]).id,
            'user_id': manager.user_id.id,
            'summary': 'Request Member Approval',
            'note': self.name,
            'activity_type_id': 4,
            'date_deadline': fields.Datetime.now(),
            }
            sfa = self.env['mail.activity'].create(todos)
        
    def approve_member(self):
        is_manager = (True if self.env.user.id in self.product_id.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'manager').user_id.ids else False) 
        
        if is_manager:
            self.state = 'active'
            getrequests = self.env['mail.activity'].search([
                            ('res_id','=',self.id),
                            ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership.member')]).id),
                            ('summary','=','Request Member Approval'),
                            ('activity_type_id','=',4)
                        ])
            if getrequests:
                getrequests.action_feedback(feedback='Approved')
        else:
            getrequests = self.env['mail.activity'].search([
                            ('res_id','=',self.id),
                            ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership.member')]).id),
                            ('summary','=','Request Member Approval'),
                            ('activity_type_id','=',4)
                        ])
            if getrequests:
                getrequests.action_feedback(feedback='Authorized')
                
            managers = self.product_id.dest_id.manager_ids.filtered(lambda r: r.manager_role == 'manager')

            for manager in managers:
                todos = {
                    'res_id': self.id,
                    'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'destination.membership.member')]).id,
                    'user_id': manager.user_id.id,
                    'summary': 'Request Member Approval',
                    'note': self.name,
                    'activity_type_id': 4,
                    'date_deadline': fields.Datetime.now(),
                    }
                sfa = self.env['mail.activity'].create(todos)
            
        
    def reject_member(self):
        self.state = 'inactive'
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership.member')]).id),
                        ('summary','=','Request Member Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.action_feedback(feedback='Rejected')
            
    def deactivate_member(self):
        self.state = 'inactive'
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership.member')]).id),
                        ('summary','=','Request Member Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.action_feedback(feedback='Deactivated')
        
    def activate_member(self):
        self.state = 'active'
        getrequests = self.env['mail.activity'].search([
                        ('res_id','=',self.id),
                        ('res_model_id','=',self.env['ir.model'].sudo().search([('model', '=', 'destination.membership.member')]).id),
                        ('summary','=','Request Member Approval'),
                        ('activity_type_id','=',4)
                    ])
        if getrequests:
            getrequests.action_feedback(feedback='Activated')



    
    
    
    def checkin_member(self):
        context = {
            'default_access_function': "check-in",
            'default_member_id' : self.id,
            'default_access_payment_method_id': self.dest_id.access_default_payment_method_id.id,
            }

        return {
            'name': 'Check-In Member',
            'view_mode': 'form',
            'res_model': 'destination.membership.member.activity.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }

    def checkin_counter_member(self):
        context = {
            'default_access_function': "check-in-counter",
            'default_member_id' : self.id,
            'default_access_payment_method_id': self.dest_id.access_default_payment_method_id.id,
            }

        return {
            'name': 'Check-In Member',
            'view_mode': 'form',
            'res_model': 'destination.membership.member.activity.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }
    
    def processin_member(self):
        context = {
            'default_access_function': "process-in",
            'default_member_id' : self.id,
            'default_access_payment_method_id': self.dest_id.access_default_payment_method_id.id,
            }

        return {
            'name': 'Process-In Member',
            'view_mode': 'form',
            'res_model': 'destination.membership.member.activity.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }
    
    def checkout_member(self):
        context = {
            'default_access_function': "check-out",
            'default_member_id' : self.id,
            'default_access_payment_method_id': self.dest_id.access_default_payment_method_id.id,
            }

        return {
            'name': 'Check-Out Member',
            'view_mode': 'form',
            'res_model': 'destination.membership.member.activity.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }
    
    
    @api.depends('membership_id')
    def compute_access_permission(self):
        for record in self:
            weekdaynow = (fields.Datetime.now() + relativedelta(hours=3)).weekday()
            dayslist = []
            if record.membership_id.product_id.dest_member_access_monday:
                dayslist.append(0)
            if record.membership_id.product_id.dest_member_access_tuesday:
                dayslist.append(1)
            if record.membership_id.product_id.dest_member_access_wednesday:
                dayslist.append(2)
            if record.membership_id.product_id.dest_member_access_thursday:
                dayslist.append(3)
            if record.membership_id.product_id.dest_member_access_friday:
                dayslist.append(4)
            if record.membership_id.product_id.dest_member_access_saturday:
                dayslist.append(5)
            if record.membership_id.product_id.dest_member_access_sunday:
                dayslist.append(6)
                
            if weekdaynow in dayslist and record.membership_type != 'guest':
                record.access_permission = True
            else:
                record.access_permission = False
                
                
    @api.depends('partner_id')
    def compute_blacklist(self):
        for record in self:
            if record.env['destination.blacklist'].search_count([('partner_id','=',record.partner_id.id),('state','=','active')]) > 0:
                record.is_blacklist = True
            else:
                record.is_blacklist = False
                
    
    
            
            
    @api.depends('member_access_status','member_activity_ids')
    def compute_is_late(self):
        for record in self:
            if record.member_access_status in ['checked-in','process-in']:
                if record.current_expiry_date:
                    if record.current_expiry_date < fields.Datetime.now():
                        record.is_access_late = True
                    else:
                        record.is_access_late = False
                else:
                    record.is_access_late = False
            else:
                record.is_access_late = False
        