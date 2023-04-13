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

class MembershipAccessCodesWizard(models.TransientModel):
    _name = 'destination.access.code.wizard'
    _description = 'Generate Access Codes'

    dest_id = fields.Many2one('destination.destination', string='Entity', tracking=True, index=True, copy=True, default=lambda self: self._get_default_dest_id())
    def _get_default_dest_id(self):
        conf = self.env['destination.destination'].search(['|',('user_ids.user_id','=',self.env.user.id),('manager_ids.user_id','=',self.env.user.id)], limit=1)
        return conf.id
    
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    
    code_letter = fields.Char(string='Token Letter', required=True, size=1)
    code_number_from = fields.Integer(string='Token From Number', required=True, size=3)
    code_number_to = fields.Integer(string='Token To Number', required=True, size=3)

    
    def apply(self):
        if self.code_number_to and self.code_number_from and self.code_number_to > self.code_number_from:
            seqrange = []
            seqrange = self.code_number_to - self.code_number_from
            for line in range(seqrange +1):
                lines_dict = {
                                        'dest_id' : self.dest_id.id,
                                        'code_letter' : self.code_letter,
                                        'code_number' : self.code_number_from + line,
                                        'name' : str(self.code_letter) + str(self.code_number_from + line),

                                    }

                self.env['destination.access.code'].create(lines_dict)
            return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            }
           
        
        
class MembershipAccessCodesProcessWizard(models.TransientModel):
    _name = 'destination.access.code.process.wizard'
    _description = 'Guest Process'

    access_date = fields.Datetime(string="Token Start", required=True, copy=True, default=lambda self: fields.Datetime.now())
    guest_id = fields.Many2one('destination.guest', string="Guest")
    
    
    guest_name = fields.Char('Guest Name', related='guest_id.guest_id.name')
    guest_phone = fields.Char('Guest Phone', related='guest_id.guest_id.phone')
    guest_mobile = fields.Char('Guest Mobile', related='guest_id.guest_id.mobile')
    guest_id_number = fields.Char('Guest ID Number', related='guest_id.guest_id.id_number')
    guest_gender = fields.Selection([('male', 'Male'), ('female','Female')], string="Gender", related="guest_id.guest_id.partnergender")
    is_male = fields.Boolean('Is Male', compute='getgender')
    is_female = fields.Boolean('Is Female', compute='getgender')
    
    member_id = fields.Many2one('destination.membership.member', string="Member")
    dest_id = fields.Many2one('destination.destination', string='Entity')
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    is_manager = fields.Boolean(string="Is Manager", compute='_is_manager')
    
    access_products_ids = fields.Many2many('product.product',string="Access Products", compute="_get_access_products", store=False)
    
    @api.onchange('guest_id','member_id')
    @api.depends('guest_id','member_id')
    def _get_access_products(self):
        for record in self:
            if record.membership_id.dest_product_access_rule == 'standard':
                accessprods = record.membership_id.product_id.access_products_ids.product_ids.product_variant_id.filtered(lambda r: r.access_product_guest == True)
            else:
                accessprods = record.membership_id.dest_product_access_cap.filtered(lambda r: r.state == 'active').product_ids.product_variant_id.filtered(lambda r: r.access_product_guest == True)
            record.access_products_ids = accessprods
            

                
    membership_id = fields.Many2one('destination.membership', string='Rental')
    product_id = fields.Many2one('product.product', string='Token Product', domain="[('id','in',access_products_ids),('access_product_guest','=',True),'|','|',('dest_guest_gender_male','=',is_male),('dest_guest_gender_female','=',is_female),'&',('dest_guest_gender_male','=',False),('dest_guest_gender_female','=',False)]", required=True)
    pricerule_id = fields.Many2one('destination.price', string="Price Rule", domain="[('product_id','=',product_id),('validity_datetime_start','<=',access_date),('validity_datetime_end','>=',access_date)]")
    is_forced_pricerule = fields.Boolean("Is Forced Price Rule", related='pricerule_id.is_forced')
    token_type = fields.Selection([('guest', 'Guest'),('free', 'Free'),('member', 'Member')], string="Token Type", copy=True, tracking=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id', depends=['product_id.currency_id'], store=True, string='Currency', readonly=True)
    
    is_payment = fields.Boolean("Payment", default=True)
    
    access_sales_journal_id = fields.Many2one('account.journal', string="Sales Journal", store=True, domain="[('company_id', '=', company_id), ('type', '=', 'sale')]", related='dest_id.access_sales_journal_id')
    access_payment_method_ids = fields.Many2many('destination.payment.method',string='Payment Methods', related='dest_id.access_payment_method_ids')
    access_payment_method_id = fields.Many2one('destination.payment.method',string='Payment Method', domain="[('id','in',access_payment_method_ids)]")    
    
    access_default_payment_method_id = fields.Many2one('destination.payment.method',string='Default Access Payment Method', related='dest_id.access_default_payment_method_id')

    access_date_date = fields.Date(string="Token Start Date")
    access_date_month = fields.Integer(string="Token Start Month")
    access_date_weekday = fields.Integer(string="Token Start Weekday")
    access_date_time = fields.Float(string="Token Start Time")
    
    expiry_date = fields.Datetime(string="Token Expiry")    
    
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
        ], string='Status', readonly=True, copy=False, tracking=True, related='guest_id.state')

    unit_price = fields.Float(string="Token Price", digits='Product Price', store=True, copy=True)
    
    @api.onchange('dest_id')
    @api.depends('dest_id')
    def _is_manager(self):
        for record in self:
            record.is_manager = (True if record.env.user.id in record.dest_id.manager_ids.user_id.ids else False)
            
    @api.onchange('guest_id','guest_gender')
    @api.depends('guest_id','guest_gender')
    def getgender(self):
        for record in self:
            if record.guest_gender == 'male':
                record.is_male = True
            else:
                record.is_male = False

            if record.guest_gender == 'female':
                record.is_female = True
            else:
                record.is_female = False
    
    @api.onchange('product_id','access_date','guest_id')
    @api.depends('product_id','access_date','guest_id')
    def get_applicable_pricerule_list(self):
        self.pricerule_id = False
        tranch = self.env['destination.price'].search([('id','!=',False)]).filtered(lambda r: r.product_id == self.product_id and r.validity_datetime_start <= self.access_date and r.validity_datetime_end >= self.access_date)
        tranch = tranch - tranch.filtered(lambda r: r.customer_apply_on == 'active' if self.guest_id.guest_id.has_active_membership == False else None)
        tranch = tranch - tranch.filtered(lambda r: r.customer_apply_on == 'select' and self.guest_id.guest_id not in r.partner_ids)
        getforcedrule = tranch.filtered(lambda r: r.is_forced == True)
        if len(getforcedrule) == 1:
            self.pricerule_id = getforcedrule.id
        return {'domain':{'pricerule_id':[('id','in',tranch.ids)]}}
    
    """
    @api.onchange('guest_id')
    @api.depends('guest_id')
    def get_applicable_product_list(self):
        if self.guest_id.guest_id.partnergender == 'male':
            return {'domain':{'product_id':[('dest_ok','=',True),('dest_product_group','=','access'),('dest_id','=',self.dest_id.id),('dest_guest_gender_male','=',True)]}}
        elif self.guest_id.guest_id.partnergender == 'female':
            return {'domain':{'product_id':[('dest_ok','=',True),('dest_product_group','=','access'),('dest_id','=',self.dest_id.id),('dest_guest_gender_female','=',True)]}}
        else:
            return {'domain':{'product_id':[('dest_ok','=',True),('dest_product_group','=','access'),('dest_id','=',self.dest_id.id)]}}
    """ 
    
    @api.onchange('access_date')
    @api.depends('access_date')
    def compute_dates(self):
        for record in self:
            if record.access_date:
                if record.access_date < fields.Datetime.now() and record.is_manager == False:
                    raise UserError(_("Access Date/Time cannot be in the past."))
                if record.access_date + relativedelta(hours=3) > record.guest_id.expiry_date + relativedelta(hours=3) and record.is_manager == False:
                    raise UserError(_("Access Date/Time does not match registered Date/Time"))
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
            record.expiry_date = record.guest_id.compute_expiry_date(access_date, product, pricerule)
    
    

    
    @api.onchange('product_id','access_date','pricerule_id','token_type')
    @api.depends('product_id','access_date','pricerule_id','token_type')
    def compute_unit_price(self):   
        for record in self:
            access_date = record.access_date
            product = record.product_id
            pricerule = record.pricerule_id
            
            if record.token_type != 'free':
                record.unit_price = record.guest_id.compute_guest_price(access_date, product, pricerule)
            else:
                record.unit_price = 0

    
    @api.onchange('product_id','access_date')
    def change1(self):
        for record in self:
            record.pricerule_id = False        
            
            
            
            
            
        
    def apply(self):
        
        if (self.access_date >= self.guest_id.expiry_date or self.access_date_date < self.guest_id.access_date_date) and self.is_manager == False:
            raise UserError("Token Date/Time before or after registered Token Date/Time")
        else:
            if self.guest_id.state != 'new':
                raise UserError("Token cannot be processed.")
            else:
                if self.guest_id.token_type == 'member':
                    partnerid = self.guest_id.member_id.partner_id
                    guestid = self.guest_id.guest_id
                    invdesc = (_('Guest - ')) + str(guestid.name)
                else:
                    partnerid = self.guest_id.guest_id
                    guestid = self.guest_id.member_id.partner_id
                    invdesc = (_('Guest of - ')) + str(self.guest_id.member_id.name)
                
                self.ensure_one()
                journal = self.dest_id.access_sales_journal_id.id
                if not journal:
                    raise UserError(_('Please define an accounting sales journal for the entity %s (%s).', self.dest_id.name, self.dest_id.id))
                
                lines_dict = {
                        'move_type': 'out_invoice',
                        'date': self.access_date_date,
                        'einv_sa_delivery_date': self.access_date_date,
                        'partner_id': partnerid.id,
                        'invoice_date': self.access_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None),
                        'currency_id': self.product_id.currency_id.id,
                        'invoice_payment_term_id': self.product_id.payment_term_id.id,
                        'invoice_origin': self.guest_id.name,
                        'journal_id': journal,
                        'invoice_line_ids': [(0, None, {
                            'name': invdesc,
                            'product_id': self.product_id.id,
                            'product_uom_id': self.product_id.uom_id.id,
                            'quantity': 1,
                            'price_unit': self.unit_price,
                            'tax_ids': self.product_id.taxes_id,
                            'analytic_account_id': self.product_id.income_analytic_account_id.id,
                        }),
                                            ]}
                
                newinv = self.env['account.move'].sudo().create(lines_dict)
                newinv.message_post_with_view('mail.message_origin_link', values={'self': newinv, 'origin': self.guest_id}, subtype_id=self.env.ref('mail.mt_note').id)
                
                
                
                self.guest_id.write({'invoice_ids': [(4, newinv.id)]})
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
                
                
                
                
                
                
                updateguest = self.guest_id.write({
                    'state':'inprocess',
                    'processin_date': fields.Datetime.now(),
                    'access_date' : self.access_date,
                    'access_date_date' : self.access_date_date,
                    'access_date_month' : self.access_date_month,
                    'access_date_weekday' : self.access_date_weekday,
                    'access_date_time' : self.access_date_time,
                    'expiry_date' : self.expiry_date,
                    'product_id': self.product_id,
                    'pricerule_id': self.pricerule_id,
                    'unit_price': self.unit_price,
                    'access_payment_method_id':self.access_payment_method_id if self.is_payment else False,
                    'processin_user_id': self.env.user.id,
                })
                
                
                
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
        
        

        
        
class MembershipAccessCodesCheckinWizard(models.TransientModel):
    _name = 'destination.access.code.checkin.wizard'
    _description = 'Guest Check-In'

    guest_id = fields.Many2one('destination.guest', string="Guest")
    
    guest_name = fields.Char('Guest Name', related='guest_id.guest_id.name')
    guest_phone = fields.Char('Guest Phone', related='guest_id.guest_id.phone')
    guest_mobile = fields.Char('Guest Mobile', related='guest_id.guest_id.mobile')
    guest_id_number = fields.Char('Guest ID Number', related='guest_id.guest_id.id_number')
    guest_gender = fields.Selection([('male', 'Male'), ('female','Female')], string="Gender", related="guest_id.guest_id.partnergender")
    is_male = fields.Boolean('Is Male', compute='getgender')
    is_female = fields.Boolean('Is Female', compute='getgender')
    
    
    access_code = fields.Char(string='Token Code', size=4)
    
    access_date = fields.Datetime(string="Token Start", related='guest_id.access_date')
    member_id = fields.Many2one('destination.membership.member', string="Member", related='guest_id.member_id')
    dest_id = fields.Many2one('destination.destination', string='Entity', related='guest_id.dest_id')
    manager_ids = fields.One2many('destination.user', string='Managers', related='dest_id.manager_ids') 
    user_ids = fields.One2many('destination.user', string='Users', related='dest_id.user_ids') 
    is_manager = fields.Boolean(string="Is Manager", compute='_is_manager')
    
    membership_id = fields.Many2one('destination.membership', string='Rental', related='guest_id.membership_id')
    product_id = fields.Many2one('product.product', string='Token Product', related='guest_id.product_id')
    access_product_code_required = fields.Boolean("Access Code Required", related='guest_id.product_id.access_product_code_required')
    pricerule_id = fields.Many2one('destination.price', string="Price Rule", related='guest_id.pricerule_id')
    is_forced_pricerule = fields.Boolean("Is Forced Price Rule", related='pricerule_id.is_forced')
    token_type = fields.Selection([('guest', 'Guest'),('free', 'Free'),('member', 'Member')], string="Token Type", related='guest_id.token_type')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='product_id.currency_id')
    
    access_date_date = fields.Date(string="Token Start Date", related='guest_id.access_date_date')
    access_date_month = fields.Integer(string="Token Start Month", related='guest_id.access_date_month')
    access_date_weekday = fields.Integer(string="Token Start Weekday", related='guest_id.access_date_weekday')
    access_date_time = fields.Float(string="Token Start Time", related='guest_id.access_date_time')
    
    expiry_date = fields.Datetime(string="Token Expiry", related='guest_id.expiry_date')
    
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
        ], string='Status', related='guest_id.state')

    unit_price = fields.Float(string="Token Price", related='guest_id.unit_price')
    
    access_function = fields.Char("Access Function")
    
    def getgender(self):
        for record in self:
            if record.guest_gender == 'male':
                record.is_male = True
            else:
                record.is_male = False

            if record.guest_gender == 'female':
                record.is_female = True
            else:
                record.is_female = False
                
    @api.onchange('dest_id')
    @api.depends('dest_id')
    def _is_manager(self):
        for record in self:
            record.is_manager = (True if record.env.user.id in record.dest_id.manager_ids.user_id.ids else False)
                
    def apply(self):
        if self.guest_id.state == 'inprocess' and self.access_function == 'in':
            if self.access_product_code_required:
                getaccesscode = self.env['destination.access.code'].search([('name','=',self.access_code),('dest_id','=',self.dest_id.id),('is_used','=',False)])
                if getaccesscode:

                    getaccesscode.write({
                        'is_used':True,
                        'source_document': '% s,% s'% ('destination.guest', self.guest_id.id),
                        'link_date': fields.Datetime.now(),

                    })
                    self.guest_id.write({
                        'access_code':getaccesscode.id,
                        'checkin_date' : self.access_date,
                        'checkin_user_id': self.env.user.id,
                        'state' : 'checked-in',
                    })
                    return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                    }

                else:
                    raise UserError("Access Code not found")
            else:
                self.guest_id.write({
                    'checkin_date' : self.access_date,
                    'checkin_user_id': self.env.user.id,
                    'state' : 'checked-in',
                })
                return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                }
        elif self.guest_id.state == 'checked-in' and self.access_function == 'out':
            
            self.guest_id.write({

                'checkout_date' : self.access_date,
                'checkout_user_id': self.env.user.id,
                'state' : 'checked-out',
            })
            return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            }
         
        else:
            raise UserError("Guest not found, please refreash the screen.")
        
           
            
            
            