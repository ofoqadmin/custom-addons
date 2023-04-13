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



class MembershipLineReportWizard(models.TransientModel):
    _name = 'destination.membership.line.report.wizard'
    _description = 'Profitability Report Wizard'
    
    
    start_date = fields.Date("Start Date")
    end_date = fields.Date("End Date")
    no_of_breaks = fields.Integer("Processing Breaks", default=1)
    
    
    current_break = fields.Integer("Current Break", default=0)
    initial_no_of_days = fields.Integer("Initial Days Delta")
    initial_no_of_breaks = fields.Integer("Initial Processing Breaks", default=0)
    initial_start_date = fields.Date("Initial Start Date")
    initial_end_date = fields.Date("Initial End Date")
    show_report = fields.Boolean("Show Report", default=False)
    
    
    
    def generate_membership_line_report(self):
        
        range_days = (self.end_date - self.start_date).days + 1
        
        if self.current_break == 0:
            batch_breaks = math.ceil(range_days / self.no_of_breaks)
            self.initial_no_of_days = batch_breaks
            self.initial_start_date = self.start_date
            self.initial_end_date = self.end_date
            self.initial_no_of_breaks = self.no_of_breaks
            self.end_date = self.start_date + timedelta(days = batch_breaks - 1)
        else:
            batch_breaks = math.ceil(range_days / self.initial_no_of_breaks)
            
        
        
        
        
        
        """
        date_batches = []
        for day in range(range_days):
            date_batches.append(self.start_date + timedelta(days = day))
            if day+1 >= batch_breaks:
                raise Warning(_("Customer has balance!"))
        """
        
        
        
        
        
        
        #clear records
        if self.current_break == 0:
            delrecs = self.env['destination.membership.line.report'].search([('report_user','=',self.env.user.id)])
            if delrecs:
                delrecs.unlink()
        
            
        #get products (new)
        range_days = (self.end_date - self.start_date).days + 1
        
        prodrecs = self.env['product.product'].search([('dest_ok','=',True),('dest_product_group','in',['accommodation','membership'])])
        
        if range_days > 0:
            for prods in prodrecs:
                for day in range(range_days):
                    unavailabledates = self.env['destination.product.unavailability'].search([('product_id','=',prods.product_tmpl_id.id)])
                    datelist = []
                    for rec in unavailabledates:
                        datelist.extend([rec.start_date+timedelta(days=x) for x in range((rec.end_date-rec.start_date).days + 1)])
                    
                    if (self.start_date + timedelta(days = day)) not in datelist:


                        lines_dict = {
                            'start_date': self.start_date + timedelta(days = day),
                            'end_date': self.start_date + timedelta(days = day + (0 if prods.dest_checkout_time > prods.dest_checkin_time else 1)),
                            'product_id': prods.id,
                            'source_type': 'membership',
                            'units_available': prods.dest_quantity,
                            'time_available': (((prods.dest_checkout_time - prods.dest_checkin_time) *60*60) if prods.dest_checkout_time > prods.dest_checkin_time else 24*60*60) * prods.dest_quantity,
                            'days_available': (((prods.dest_checkout_time - prods.dest_checkin_time) / 24 ) if prods.dest_checkout_time > prods.dest_checkin_time else 1) * prods.dest_quantity,
                            'user_id':self.env.user.id,
                            'dest_id':prods.dest_id.id,

                        }
                        self.env['destination.membership.line.report'].create(lines_dict)

                        lines_dict = {
                            'start_date': self.start_date + timedelta(days = day),
                            'end_date': self.start_date + timedelta(days = day + (0 if prods.dest_checkout_time > prods.dest_checkin_time else 1)),
                            'product_id': prods.id,
                            'source_type': 'member',
                            'units_available': prods.dest_quantity,
                            'days_available': prods.dest_member_count * prods.dest_quantity,
                            'user_id':self.env.user.id,
                            'dest_id':prods.dest_id.id,

                        }
                        self.env['destination.membership.line.report'].create(lines_dict)

                        lines_dict = {
                            'start_date': self.start_date + timedelta(days = day),
                            'end_date': self.start_date + timedelta(days = day + (0 if prods.dest_checkout_time > prods.dest_checkin_time else 1)),
                            'product_id': prods.id,
                            'source_type': 'guest',
                            'units_available': prods.dest_quantity,
                            'days_available': prods.dest_daily_guest_count * prods.dest_quantity,
                            'user_id':self.env.user.id,
                            'dest_id':prods.dest_id.id,

                        }
                        self.env['destination.membership.line.report'].create(lines_dict)

                
        """
        #get products (working)
        range_days = (self.end_date - self.start_date).days
        
        prodrecs = self.env['product.product'].search([('dest_ok','=',True)])
        for prods in prodrecs:
            if range_days > 0:
                
                lines_dict = {
                    'start_date': self.start_date,
                    'end_date': self.end_date,
                    'product_id': prods.id,
                    'source_type': 'membership',
                    'units_available': prods.dest_quantity,
                    'time_available': ((prods.dest_checkout_time - prods.dest_checkin_time) *60*60 * prods.dest_quantity * range_days) if prods.dest_checkout_time > prods.dest_checkin_time else 24*60*60 * prods.dest_quantity * range_days,
                    'days_available': ((prods.dest_checkout_time - prods.dest_checkin_time) / 24 * prods.dest_quantity * range_days ) if prods.dest_checkout_time > prods.dest_checkin_time else 1 * prods.dest_quantity * range_days,
                    'members_available': prods.dest_member_count * prods.dest_quantity,
                    'guests_available': prods.dest_daily_guest_count * range_days * prods.dest_quantity,

                }
                self.env['destination.membership.line.report'].create(lines_dict)
        """            
                    
           
        #get membership lines
        membershiprecs = self.env['destination.membership'].search([('active','=',True),('state','in',['active','hold','late','checked-out','done'])])
        membershiprecslines = self.env['destination.membership.line'].search([('membership_id','in',membershiprecs.ids)]).filtered(lambda r: r.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() <= self.end_date and r.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() >= self.start_date)
        for prods in membershiprecslines:
            
            prodstartdate = prods.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date()
            prodenddate = prods.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date()
            prodstarttime = prods.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).time()
            prodendtime = prods.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).time()
            proddays = (prodenddate - prodstartdate).days
            
            if proddays > 0:
                for day in range(proddays):
                    
                    datez = prods.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() + timedelta(days = day)
                    datey = prods.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None) + timedelta(days = day)
                    if datez >= self.start_date and datez <= self.end_date:
               
                        lines_dict = {
                            'start_date': datez,
                            'end_date': datez + relativedelta(days=1),
                            'source_document': '% s,% s'% ('destination.membership.line', prods.id),
                            'source_type': 'membership',
                            'product_id': prods.product_id.id,
                            'membership_id': prods.membership_id.id,
                            'partner_id' : prods.membership_id.partner_id.id,
                            'amount': (prods.price_total / proddays),
                            'time_occupied': 1*24*60*60,
                            'days_occupied': 1,
                            'user_id':prods.membership_id.user_id.id,
                            'dest_id':prods.membership_id.dest_id.id,
                        }
                        self.env['destination.membership.line.report'].create(lines_dict)
                        
                        lines_dict = {
                            'start_date': datez,
                            'end_date': datez + relativedelta(days=1),
                            'source_document': '% s,% s'% ('destination.membership.line', prods.id),
                            'source_type': 'member',
                            'product_id': prods.product_id.id,
                            'membership_id': prods.membership_id.id,
                            'partner_id' : prods.membership_id.partner_id.id,
                            'user_id':prods.membership_id.user_id.id,
                            'dest_id':prods.membership_id.dest_id.id,
                            'days_available': max(prods.membership_id.actual_dest_member_count,prods.product_id.dest_member_count),
                        }
                        self.env['destination.membership.line.report'].create(lines_dict)
                        
                        existprodmemberrec = self.env['destination.membership.line.report'].search([('start_date','=',datez),('source_document','=',False),('source_type','=','member'),('product_id','=',prods.product_id.id),('membership_id','=',False),('report_user','=',self.env.user.id)])
                        existprodmemberrec.write({'days_available': (prods.product_id.dest_member_count * prods.product_id.dest_quantity) - max(prods.membership_id.actual_dest_member_count,prods.product_id.dest_member_count)})
                        
                        lines_dict = {
                            'start_date': datez,
                            'end_date': datez + relativedelta(days=1),
                            'source_document': '% s,% s'% ('destination.membership.line', prods.id),
                            'source_type': 'guest',
                            'product_id': prods.product_id.id,
                            'membership_id': prods.membership_id.id,
                            'partner_id' : prods.membership_id.partner_id.id,
                            'user_id':prods.membership_id.user_id.id,
                            'dest_id':prods.membership_id.dest_id.id,
                            'days_available': max(prods.membership_id.actual_dest_daily_guest_count,prods.product_id.dest_daily_guest_count),
                        }
                        self.env['destination.membership.line.report'].create(lines_dict)
                        
                        existprodguestrec = self.env['destination.membership.line.report'].search([('start_date','=',datez),('source_document','=',False),('source_type','=','guest'),('product_id','=',prods.product_id.id),('membership_id','=',False),('report_user','=',self.env.user.id)])
                        existprodguestrec.write({'days_available':(prods.product_id.dest_daily_guest_count * prods.product_id.dest_quantity) - max(prods.membership_id.actual_dest_daily_guest_count,prods.product_id.dest_daily_guest_count)})
                        
            else:
                proddays = 1
                
                for day in range(proddays):
                    
                    
                    lines_dict = {
                        'start_date': prods.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date(),
                        'end_date': prods.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date(),
                        'source_document': '% s,% s'% ('destination.membership.line', prods.id),
                        'source_type': 'membership',
                        'product_id': prods.product_id.id,
                        'membership_id': prods.membership_id.id,
                        'partner_id' : prods.membership_id.partner_id.id,
                        'amount': prods.price_total,
                        'time_occupied': (((prods.end_date - prods.start_date).days *24*60*60)+(prods.end_date - prods.start_date).seconds),
                        'days_occupied': (((prods.end_date - prods.start_date).days *24*60*60) + (prods.end_date - prods.start_date).seconds)/24/60/60,
                        'user_id':prods.membership_id.user_id.id,
                        'dest_id':prods.membership_id.dest_id.id,
                    }
                    self.env['destination.membership.line.report'].create(lines_dict)
                    
                    lines_dict = {
                        'start_date': prods.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date(),
                        'end_date': prods.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date(),
                        'source_document': '% s,% s'% ('destination.membership.line', prods.id),
                        'source_type': 'member',
                        'product_id': prods.product_id.id,
                        'membership_id': prods.membership_id.id,
                        'partner_id' : prods.membership_id.partner_id.id,
                        'user_id':prods.membership_id.user_id.id,
                        'dest_id':prods.membership_id.dest_id.id,
                        'days_available': max(prods.membership_id.actual_dest_member_count,prods.product_id.dest_member_count),
                    }
                    self.env['destination.membership.line.report'].create(lines_dict)
                    
                    existprodmemberrec = self.env['destination.membership.line.report'].search([('start_date','=',prods.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date()),('source_document','=',False),('source_type','=','member'),('product_id','=',prods.product_id.id),('membership_id','=',False),('report_user','=',self.env.user.id)])
                    existprodmemberrec.write({'days_available':(prods.product_id.dest_member_count * prods.product_id.dest_quantity) - max(prods.membership_id.actual_dest_member_count,prods.product_id.dest_member_count)})
                    
                    lines_dict = {
                        'start_date': prods.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date(),
                        'end_date': prods.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date(),
                        'source_document': '% s,% s'% ('destination.membership.line', prods.id),
                        'source_type': 'guest',
                        'product_id': prods.product_id.id,
                        'membership_id': prods.membership_id.id,
                        'partner_id' : prods.membership_id.partner_id.id,
                        'user_id':prods.membership_id.user_id.id,
                        'dest_id':prods.membership_id.dest_id.id,
                        'days_available': max(prods.membership_id.actual_dest_daily_guest_count,prods.product_id.dest_daily_guest_count),
                    }
                    self.env['destination.membership.line.report'].create(lines_dict)
                    
                    existprodguestrec = self.env['destination.membership.line.report'].search([('start_date','=',prods.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date()),('source_document','=',False),('source_type','=','guest'),('product_id','=',prods.product_id.id),('membership_id','=',False),('report_user','=',self.env.user.id)])
                    existprodguestrec.write({'days_available': (prods.product_id.dest_daily_guest_count * prods.product_id.dest_quantity) - max(prods.membership_id.actual_dest_daily_guest_count,prods.product_id.dest_daily_guest_count)})
            
            
            
        #get membership extra lines
        membershiprecs = self.env['destination.membership'].search([('active','=',True),('state','in',['active','hold','late','checked-out','done'])])
        membershiprecslines = self.env['destination.membership.extra.line'].search([('membership_id','in',membershiprecs.ids)]).filtered(lambda r: r.extra_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() <= self.end_date and r.extra_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() >= self.start_date)
        for prods in membershiprecslines:
                    
            datez = prods.extra_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date()
            if datez >= self.start_date and datez <= self.end_date:
                lines_dict = {
                    'start_date': datez,
                    'end_date': datez,
                    'source_document': '% s,% s'% ('destination.membership.extra.line', prods.id),
                    'source_type': 'others',
                    'product_id': prods.product_id.id,
                    'membership_id': prods.membership_id.id,
                    'partner_id' : prods.membership_id.partner_id.id,
                    'amount': prods.unit_price,
                    'user_id':prods.membership_id.user_id.id,
                    'dest_id':prods.membership_id.dest_id.id,
                }
                self.env['destination.membership.line.report'].create(lines_dict)

                
            
            
            
            
            
        #get member access lines
        memberactivityrecs = self.env['destination.membership.member.activity'].search([('active','=',True)]).filtered(lambda r: r.access_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() <= self.end_date and r.access_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() >= self.start_date)
        
        for prods in memberactivityrecs:
            lines_dict = {
                'start_date': prods.access_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date(),
                'end_date': prods.access_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date(),
                'source_document': '% s,% s'% ('destination.membership.member.activity', prods.id),
                'source_type': 'member',
                'product_id': prods.product_id.id,
                'membership_id': prods.membership_id.id,
                'partner_id' : prods.member_id.partner_id.id,
                'amount': prods.total_invoiced,
                'time_occupied': (1*24*60*60),
                'days_occupied': 1,
                'user_id':prods.membership_id.user_id.id,
                'dest_id':prods.membership_id.dest_id.id,
            }
            self.env['destination.membership.line.report'].create(lines_dict)
            
        #get guest access lines
        guestrecs = self.env['destination.guest'].search([('invoice_ids','!=',False)]).filtered(lambda r: r.access_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() <= self.end_date and r.access_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() >= self.start_date)
        
        for prods in guestrecs:
            lines_dict = {
                'start_date': prods.access_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date(),
                'end_date': prods.expiry_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date(),
                'source_document': '% s,% s'% ('destination.guest', prods.id),
                'source_type': 'guest',
                'product_id': prods.product_id.id,
                'membership_id': prods.membership_id.id,
                'partner_id' : prods.guest_id.id,
                'amount': prods.total_invoiced,
                'time_occupied': (1*24*60*60),
                'days_occupied': 1,
                'user_id':prods.membership_id.user_id.id,
                'dest_id':prods.membership_id.dest_id.id,
            }
            self.env['destination.membership.line.report'].create(lines_dict)
            
            
            
            
            
        #get other sales
        sorecs = self.env['sale.order'].search([('dest_source','=','others')]).filtered(lambda r: r.date_order.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() <= self.end_date and r.date_order.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date() >= self.start_date)
        solrecs = self.env['sale.order.line'].search([('order_id','in',sorecs.ids)])
                           
                           
        for prods in solrecs:
            lines_dict = {
                'start_date': prods.order_id.date_order,
                'end_date': prods.order_id.date_order,
                'source_document': '% s,% s'% ('sale.order.line', prods.id),
                'source_type': 'others',
                'product_id': prods.product_id.id,
                'membership_id': prods.order_id.membership_id.id,
                'partner_id' : prods.order_id.partner_id.id,
                'amount': prods.price_total,
                'user_id':prods.order_id.user_id.id,
                'dest_id':prods.order_id.dest_id.id,
            }
            self.env['destination.membership.line.report'].create(lines_dict)
        
        if (self.end_date + timedelta(days = self.initial_no_of_days)) > self.initial_end_date:
            enddate = self.initial_end_date
        else:
            enddate = self.end_date + timedelta(days = self.initial_no_of_days)
        
        if (self.current_break + 1) - self.initial_no_of_breaks > 0:
            showreport = 1
        else:
            showreport = 0
        
        return {
                        'type': 'ir.actions.act_window',
                        'view_mode': 'form',
                        'res_model': 'destination.membership.line.report.wizard',
                        'target': 'new',
                        'domain':[],
                        'context':{
                            'default_initial_start_date': self.initial_start_date,
                            'default_initial_end_date': self.initial_end_date,
                            'default_initial_no_of_breaks':self.initial_no_of_breaks,
                            'default_initial_no_of_days':self.initial_no_of_days,
                            'default_current_break': self.current_break + 1,
                            'default_start_date': self.end_date + timedelta(days = 1),
                            'default_show_report': showreport,
                            'default_end_date': enddate,
                            
                                  
                                  },

                    }
        
        
    def view_report(self):
            
        return {
                        'type': 'ir.actions.act_window',
                        'view_type': 'dashboard',
                        'view_mode': 'dashboard,search',
                        'res_model': 'destination.membership.line.report',
                        'name': 'Profitability Report - ' + str(self.initial_start_date) + ' >> ' + str(self.initial_end_date),
                        'domain':[('report_user','=',self.env.user.id)],
                        'context':{'report_user':self.env.user.id},

                    }
        
        
        
        

    