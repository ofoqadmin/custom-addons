from odoo import api, fields, models, _, tools
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import datetime
import pytz
from pytz import timezone, UTC
import json, simplejson
from lxml import etree
import math
from odoo.tools import float_compare, format_datetime, format_time

class MembershipMemberActivityWizard(models.TransientModel):
    _name = 'destination.membership.member.activity.wizard'
    _description = 'Register Member Activity'

    
    # configuration fields
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    is_manager = fields.Boolean(string="Is Manager", compute='_is_manager')
    
    @api.onchange('dest_id')
    @api.depends('dest_id')
    def _is_manager(self):
        for record in self:
            record.is_manager = (True if record.env.user.id in record.dest_id.manager_ids.user_id.ids else False)
            
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id', depends=['product_id.currency_id'], store=True, string='Currency', readonly=True)
    state = fields.Selection([
        ('new', 'Registered'),
        ('pending', 'Pending'),
        ('blacklist', 'Blacklist'),
        ('inprocess', 'In-Process'),
        ('checked-in', 'Checked-in'),
        ('checked-out', 'Checked-Out'),
        ('late', 'Late'),
        ('expired', 'Expired'),
        ('done', 'Done'),
        ('cancel','Cancelled'),
        ], string='Status', readonly=True, copy=False, tracking=True)
    access_function = fields.Char("Access Function")
    
    #member data
    member_id = fields.Many2one('destination.membership.member', string="Member", ondelete='restrict', store=True, copy=True, required=True)
    
    member_name = fields.Char('Member Name', related='member_id.partner_id.name')
    member_phone = fields.Char('Member Phone', related='member_id.partner_id.phone')
    member_mobile = fields.Char('Member Mobile', related='member_id.partner_id.mobile')
    member_id_number = fields.Char('Member ID Number', related='member_id.partner_id.id_number')
    member_gender = fields.Selection([('male', 'Male'), ('female','Female')], string="Gender", related="member_id.partner_id.partnergender")
    is_male = fields.Boolean('Is Male', compute='getgender')
    is_female = fields.Boolean('Is Female', compute='getgender')
    
    
    dest_id = fields.Many2one('destination.destination', string='Entity', related='member_id.dest_id')
    membership_id = fields.Many2one('destination.membership', string='Rental', related='member_id.membership_id')

    access_products_ids = fields.Many2many('product.product',string="Access Products", compute="_get_access_products", store=False)
    
    @api.onchange('member_id')
    @api.depends('member_id')
    def _get_access_products(self):
        for record in self:
            if record.membership_id.dest_product_access_rule == 'standard':
                if record.member_id.membership_type == 'guest':
                    accessprods = record.membership_id.product_id.access_products_ids.product_ids.product_variant_id.filtered(lambda r: r.access_product_guest == True)
                else:
                    accessprods = record.membership_id.product_id.access_products_ids.product_ids.product_variant_id.filtered(lambda r: r.access_product_member == True)
            else:
                if record.member_id.membership_type == 'guest':
                    accessprods = record.membership_id.dest_product_access_cap.filtered(lambda r: r.state == 'active').product_ids.product_variant_id.filtered(lambda r: r.access_product_guest == True)
                else:
                    accessprods = record.membership_id.dest_product_access_cap.filtered(lambda r: r.state == 'active').product_ids.product_variant_id.filtered(lambda r: r.access_product_member == True)
            record.access_products_ids = accessprods
        
    #Activity_id data
    active = fields.Boolean(string="Active", tracking=True, default=True)
    name = fields.Text(string='Reference', copy=False, readonly=True, compute='assign_activity_name')

    #Access code data
    access_date = fields.Datetime(string="Date", required=True, copy=True, default=lambda self: fields.Datetime.now())
    product_id = fields.Many2one('product.product', string='Token Product', domain="[('id','in',access_products_ids),'|','|',('dest_guest_gender_male','=',is_male),('dest_guest_gender_female','=',is_female),'&',('dest_guest_gender_male','=',False),('dest_guest_gender_female','=',False)]")
    pricerule_id = fields.Many2one('destination.price', string="Price Rule", domain="[('product_id','=',product_id),('validity_datetime_start','<=',access_date),('validity_datetime_end','>=',access_date)]")
    is_payment = fields.Boolean("Payment", default=True)   
    access_payment_method_id = fields.Many2one('destination.payment.method', string='Payment Method', domain="[('id','in',access_payment_method_ids)]")       
    access_code = fields.Char(string='Token Code', size=4)
    
    is_forced_pricerule = fields.Boolean("Is Forced Price Rule", related='pricerule_id.is_forced')
    
    access_payment_method_ids = fields.Many2many('destination.payment.method',string='Payment Methods', related='dest_id.access_payment_method_ids')
    access_default_payment_method_id = fields.Many2one('destination.payment.method',string='Default Access Payment Method', related='dest_id.access_default_payment_method_id')
    access_date_date = fields.Date(string="Token Start Date")
    access_date_month = fields.Integer(string="Token Start Month")
    access_date_weekday = fields.Integer(string="Token Start Weekday")
    access_date_time = fields.Float(string="Token Start Time")   
    expiry_date = fields.Datetime(string="Token Expiry")    
    unit_price = fields.Float(string="Token Price", digits='Product Price', store=True, copy=True)
    membership_access_weekdays_allowed = fields.Boolean("Weekday Access Permission", related='member_id.access_permission')
    
    
    processin_date = fields.Datetime(string="Process-In Date", tracking=True)
    checkin_date = fields.Datetime(string="Check-In Date", tracking=True)
    checkout_date = fields.Datetime(string="Check-Out Date", tracking=True)
    close_date = fields.Datetime(string="Close Date", tracking=True)
    
    def assign_activity_name(self):
        for record in self:
            record.name = record.membership_id.dest_id.code + '/' + record.membership_id.product_id.dest_product_code + '/' + (self.env['ir.sequence'].next_by_code('destination.membership.member.activity', sequence_date=record.access_date_date))
    
    @api.onchange('member_id','member_gender')
    @api.depends('member_id','member_gender')
    def getgender(self):
        for record in self:
            if record.member_gender == 'male':
                record.is_male = True
            else:
                record.is_male = False

            if record.member_gender == 'female':
                record.is_female = True
            else:
                record.is_female = False
    
    @api.depends('membership_id','access_date')
    def compute_weekdays_access_allowed(self):
        for record in self:
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
                
            if record.access_date_weekday in dayslist:
                record.membership_access_weekdays_allowed = True
            else:
                record.membership_access_weekdays_allowed = False
                
                
    
    @api.onchange('product_id','access_date','member_id')
    @api.depends('product_id','access_date','member_id')
    def get_applicable_pricerule_list(self):
        self.pricerule_id = False
        tranch = self.env['destination.price'].search([('id','!=',False)]).filtered(lambda r: r.product_id == self.product_id and r.validity_datetime_start <= self.access_date and r.validity_datetime_end >= self.access_date)
        tranch = tranch - tranch.filtered(lambda r: r.customer_apply_on == 'active' if self.member_id.partner_id.has_active_membership == False else None)
        tranch = tranch - tranch.filtered(lambda r: r.customer_apply_on == 'select' and self.member_id.partner_id not in r.partner_ids)
        getforcedrule = tranch.filtered(lambda r: r.is_forced == True)
        if len(getforcedrule) == 1:
            self.pricerule_id = getforcedrule.id
        return {'domain':{'pricerule_id':[('id','in',tranch.ids)]}}
    
    """
    @api.onchange('member_id')
    @api.depends('member_id')
    def get_applicable_product_list(self):
        if self.member_id.partner_id.partnergender == 'male':
            return {'domain':{'product_id':[('dest_ok','=',True),('dest_product_group','=','access'),('dest_id','=',self.dest_id.id),('dest_guest_gender_male','=',True)]}}
        elif self.member_id.partner_id.partnergender == 'female':
            return {'domain':{'product_id':[('dest_ok','=',True),('dest_product_group','=','access'),('dest_id','=',self.dest_id.id),('dest_guest_gender_female','=',True)]}}
        else:
            return {'domain':{'product_id':[('dest_ok','=',True),('dest_product_group','=','access'),('dest_id','=',self.dest_id.id)]}}
    """
    
    @api.onchange('access_date')
    @api.depends('access_date')
    def compute_dates(self):
        for record in self:
            if record.access_date:
                if record.access_date < fields.Datetime.now():
                    raise UserError("Access Date/Time cannot be in the past.")
                record.access_date_date = (record.access_date + relativedelta(hours=3)).date()
                record.access_date_month = (record.access_date + relativedelta(hours=3)).month
                record.access_date_weekday = (record.access_date + relativedelta(hours=3)).weekday()
                record.access_date_time = float((record.access_date + relativedelta(hours=3)).time().strftime('%H')) + (float((record.access_date + relativedelta(hours=3)).time().strftime('%M'))/60*100/100)
            else:
                record.access_date_date = False
                record.access_date_month = False
                record.access_date_weekday = False
                record.access_date_time = False

    @api.onchange('access_date','product_id','pricerule_id')
    @api.depends('access_date','product_id','pricerule_id')
    def get_expiry_date(self):
        for record in self:
            access_date = record.access_date
            product = record.product_id
            pricerule = record.pricerule_id
            record.expiry_date = record.compute_expiry_date(access_date, product, pricerule)
    
    

    
    @api.onchange('product_id','access_date','pricerule_id')
    @api.depends('product_id','access_date','pricerule_id')
    def compute_unit_price(self):   
        for record in self:
            access_date = record.access_date
            product = record.product_id
            pricerule = record.pricerule_id
            record.unit_price = record.compute_price(access_date, product, pricerule)
            
    
    @api.onchange('product_id','access_date')
    def change1(self):
        for record in self:
            record.pricerule_id = False        

    def compute_price(self, access_date, product, pricerule):
        for record in self:
            if access_date:
                access_date_date = (access_date + relativedelta(hours=3)).date()
                access_date_month = (access_date + relativedelta(hours=3)).month
                access_date_weekday = (access_date + relativedelta(hours=3)).weekday()
                access_date_time = float((access_date + relativedelta(hours=3)).time().strftime('%H')) + (float((access_date + relativedelta(hours=3)).time().strftime('%M'))/60*100/100)

                if product:
                    if pricerule:
                        if pricerule.rule_type == 'price':
                            if pricerule.dest_custom_price == 'weekday_rate':
                                pricerulerecord = pricerule.dest_access_pricing_ids.search([('pricerule_id','=',pricerule.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                                if len(pricerulerecord) != 1:
                                    raise ValidationError(_('Pricing Error, please revise Price Rule pricing.'))
                                else:
                                    return pricerulerecord.price
                            else:
                                if pricerule.service_timeonly_start > 0 or pricerule.service_timeonly_end > 0:
                                    if access_date_time >= pricerule.service_timeonly_start and access_date_time <= pricerule.service_timeonly_end:
                                        return pricerule.list_price
                                    else:
                                        return product.lst_price
                                else:
                                    return pricerule.list_price
                        else:
                            if pricerule.dest_custom_price == 'weekday_rate':
                                
                                pricelinerecord = product.dest_access_pricing_ids.search([('product_id','=',product.product_tmpl_id.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                                if len(pricelinerecord) != 1:
                                    raise ValidationError(_('Pricing Error, please revise Product pricing.'))
                                else:
                                    return pricelinerecord.price - (pricelinerecord.price * pricerule.discount / 100) 
                                
                            else:
                                if pricerule.service_timeonly_start > 0 or pricerule.service_timeonly_end > 0:
                                    if access_date_time >= pricerule.service_timeonly_start and access_date_time <= pricerule.service_timeonly_end:
                                        return product.lst_price - (product.lst_price * pricerule.discount / 100) 
                                    else:
                                        return product.lst_price
                                else:
                                    return product.lst_price - (product.lst_price * pricerule.discount / 100) 
                            
                    else:
                        if product.dest_custom_price == 'weekday_rate':
                            pricelinerecord = product.dest_access_pricing_ids.search([('product_id','=',product.product_tmpl_id.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                            if len(pricelinerecord) != 1:
                                raise ValidationError(_('Pricing Error, please revise Product pricing.'))
                            else:
                                return pricelinerecord.price
                        else:
                            return product.lst_price
                else:
                    return 0
            else:
                return 0        
    
    def compute_expiry_date(self, access_date, product, pricerule):
        for record in self:
            access_date_date = (access_date + relativedelta(hours=3)).date()
            access_date_month = (access_date + relativedelta(hours=3)).month
            access_date_weekday = (access_date + relativedelta(hours=3)).weekday()
            access_date_time = float((access_date + relativedelta(hours=3)).time().strftime('%H')) + (float((access_date + relativedelta(hours=3)).time().strftime('%M'))/60*100/100)

            if product:
                if pricerule:
                    if pricerule.dest_custom_price == 'weekday_rate':
                        pricerulerecord = record.env['destination.price.access.lines'].search([('pricerule_id','=',pricerule.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                        if len(pricerulerecord) != 1:
                            raise ValidationError(_('Pricing Error, please revise Price Rule pricing.'))
                        else:
                            return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(pricerulerecord.access_time_start * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(pricerulerecord.access_duration), minutes=(pricerulerecord.access_duration % 1 * 60))    
                    else:
                        if pricerule.service_timeonly_start > 0 or pricerule.service_timeonly_end > 0:
                            if access_date_time >= pricerule.service_timeonly_start and access_date_time <= pricerule.service_timeonly_end:
                                return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(pricerule.dest_access_start_time * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(pricerule.dest_access_duration), minutes=(pricerule.dest_access_duration % 1 * 60))    
                            else:
                                return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(product.dest_access_start_time * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(product.dest_access_duration), minutes=(product.dest_access_duration % 1 * 60))    
                        else:
                            return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(pricerule.dest_access_start_time * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(pricerule.dest_access_duration), minutes=(pricerule.dest_access_duration % 1 * 60))    
                else:
                    if product.dest_custom_price == 'weekday_rate':
                        pricelinerecord = record.env['destination.product.access.price.lines'].search([('product_id','=',product.product_tmpl_id.id),('access_weekday','=',access_date_weekday),('access_time_start','<=',access_date_time),('access_time_end','>',access_date_time)])
                        if len(pricelinerecord) != 1:
                            raise ValidationError(_('Pricing Error, please revise Product pricing.'))
                        else:
                            return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(pricelinerecord.access_time_start * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(pricelinerecord.access_duration), minutes=(pricelinerecord.access_duration % 1 * 60))    
                    else:
                        return datetime.datetime.combine(access_date_date, datetime.datetime.fromtimestamp(product.dest_access_start_time * 3600).time()) - relativedelta(hours=3) + relativedelta(hours=int(product.dest_access_duration), minutes=(product.dest_access_duration % 1 * 60))    
            else:
                return 0
    
    
    def member_check_in(self):
        if self.access_function == 'check-in':
            activity_dict = {
                'name': self.name,
                'dest_id': self.dest_id.id,
                'member_id': self.member_id.id,
                'pricerule_id': self.pricerule_id.id,
                'product_id': self.product_id.id,
                'access_date': self.access_date,
                'expiry_date': self.expiry_date,
                'checkin_date': self.access_date,
                'unit_price': self.unit_price,
                'checkin_user_id': self.env.user.id,
            }

            newactivity = self.member_id.member_activity_ids.create(activity_dict)
            self.member_id.write({'member_access_status':'checked-in',
                                  'current_access_date': self.access_date,
                                  'current_expiry_date': self.expiry_date,
                                  'current_checkin_date': self.access_date,
                                  'current_checkout_date': False,
                                 'current_activity_id': newactivity.id,
                                  
                                 })

            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
    
    
    def member_check_out(self):
        if self.access_function == 'check-out':

            activity_dict = {
                'checkout_date': self.access_date,
                'checkout_user_id': self.env.user.id,
            }

            self.member_id.current_activity_id.write(activity_dict)
            self.member_id.write({'member_access_status':'checked-out',
                                  'current_access_date': False,
                                  'current_expiry_date': False,
                                  'current_checkin_date': False,
                                  'current_processin_date': False,
                                  'current_checkout_date': False,
                                 'current_activity_id': False,
                                  
                                 })

            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

   
    
        
    def member_process_in(self):
        if self.access_date > self.expiry_date:
            raise UserError(_("Expiry Date Error, please check Access product"))
        
        activity_dict = {
            'name': self.name,
            'dest_id': self.dest_id.id,
            'member_id': self.member_id.id,
            'pricerule_id': self.pricerule_id.id,
            'product_id': self.product_id.id,
            'access_date': self.access_date,
            'expiry_date': self.expiry_date,
            'processin_date': self.access_date,
            'unit_price': self.unit_price,
            'processin_user_id': self.env.user.id,
        }
        
        newactivity = self.member_id.member_activity_ids.create(activity_dict)
        self.member_id.write({'member_access_status':'inprocess',
                                'current_access_date': self.access_date,
                                  'current_expiry_date': self.expiry_date,
                                  'current_processin_date': self.access_date,
                                  'current_checkout_date': False,
                                 'current_activity_id': newactivity.id,
                              
                             
                                 })
        
        self.ensure_one()
        journal = self.dest_id.access_sales_journal_id.id
        if not journal:
            raise UserError(_('Please define an accounting sales journal for the entity %s (%s).', self.dest_id.name, self.dest_id.id))

        lines_dict = {
                'move_type': 'out_invoice',
                'date': self.access_date_date,
                'einv_sa_delivery_date': self.access_date_date,
                'partner_id': self.member_id.partner_id.id,
                'invoice_date': self.access_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None),
                'currency_id': self.product_id.currency_id.id,
                'invoice_payment_term_id': self.product_id.payment_term_id.id,
                'invoice_origin': self.name,
                'journal_id': journal,
                'invoice_line_ids': [(0, None, {
                    'name': 'Member Access Token - ' + str(self.member_id.name),
                    'product_id': self.product_id.id,
                    'product_uom_id': self.product_id.uom_id.id,
                    'quantity': 1,
                    'price_unit': self.unit_price,
                    'tax_ids': self.product_id.taxes_id,
                    'analytic_account_id': self.product_id.income_analytic_account_id.id,
                }),
                                    ]}

        newinv = self.env['account.move'].sudo().create(lines_dict)
        newinv.message_post_with_view('mail.message_origin_link', values={'self': newinv, 'origin': newactivity}, subtype_id=self.env.ref('mail.mt_note').id)



        newactivity.write({'invoice_ids': [(4, newinv.id)]})
        
        newinv.sudo().action_post()

        if self.is_payment:
            invoice_object = newinv
            ctx = dict(active_ids=invoice_object.ids, # Use ids and not id (it has to be a list)
                        active_model='account.move',
                            )
            values = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': newinv.partner_id.id,
            'amount': self.unit_price,
            'payment_date': datetime.date.today(),
            'currency_id': newinv.currency_id.id,
            'journal_id': self.access_payment_method_id.journal_id.id,
            'communication': newinv.payment_reference,
            }
            wizard = self.env['account.payment.register'].with_context(ctx).sudo().create(values)
            wizard.sudo()._create_payments()


        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    
    def member_check_in_counter(self):
        if self.member_id.member_access_status == 'inprocess' and self.access_function == 'check-in-counter':
            getaccesscode = self.env['destination.access.code'].search([('name','=',self.access_code),('dest_id','=',self.dest_id.id)])
            if getaccesscode:
                if not getaccesscode.is_used:
                    getaccesscode.write({
                        'is_used':True,
                        'source_document': '% s,% s'% ('destination.membership.member.activity', self.member_id.current_activity_id.id),
                        'name': self.member_id.current_activity_id.name + '/' + self.access_code,
                        'link_date': self.access_date,
                        
                    })
                    self.member_id.current_activity_id.write({
                        'access_code': getaccesscode.id,
                        'checkin_date' : self.access_date,
                        'checkin_user_id': self.env.user.id,
                    })
                    self.member_id.write({'member_access_status':'checked-in',
                                 'current_checkin_date': self.access_date,
                                          'current_checkout_date': False,
                                          
                                         })
                    return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                    }
                else:
                    raise UserError(_("Access Code has been used."))
            else:
                raise UserError(_("Access Code not found"))
        
        
        
        
        
    