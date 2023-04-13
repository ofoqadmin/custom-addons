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



class AccessReportWizard(models.TransientModel):
    _name = 'destination.access.report.wizard'
    _description = 'Access Report Wizard'
    
    
    start_date = fields.Datetime("Start Date", default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hour=0) - timedelta(hours=3))
    end_date = fields.Datetime("End Date", default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hour=0, days=1) - timedelta(hours=3))
    
    
    
    
    def generate_access_report(self):
        
        #clear records
        delrecs = self.env['destination.access.report'].search([('report_user','=',self.env.user.id)])
        if delrecs:
            delrecs.unlink()
            

        #get member access lines
        memberactivityrecs = self.env['destination.membership.member.activity'].search([('active','=',True)]).filtered(lambda r: r.access_date <= self.end_date and r.access_date >= self.start_date)
        
        for prods in memberactivityrecs:
            lines_dict = {
                'date': prods.access_date,
                'source_document': '% s,% s'% ('destination.membership.member.activity', prods.id),
                'source_type': 'member',
                'product_id': prods.product_id.id,
                'membership_id': prods.membership_id.id,
                'partner_id' : prods.member_id.partner_id.id,
                'amount': prods.total_invoiced,
                'dest_id':prods.dest_id.id,
                'access_payment_method_id': prods.access_payment_method_id.id,
                'processin_date': prods.processin_date,
                'checkin_date': prods.checkin_date,
                'checkout_date': prods.checkout_date,
                'registration_user_id': prods.registration_user_id.id,
                'processin_user_id': prods.processin_user_id.id,
                'checkin_user_id': prods.checkin_user_id.id,
                'checkout_user_id': prods.checkout_user_id.id,
                'name': 'Access Report - ' + str(self.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + ' >> ' + str(self.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                
            }
            self.env['destination.access.report'].create(lines_dict)
        
        #get guest access lines
        guestrecs = self.env['destination.guest'].search([('active','=',True)]).filtered(lambda r: r.state in ['inprocess','checked-in','checked-out','late','done'] and r.access_date <= self.end_date and r.access_date >= self.start_date)
        
        for prods in guestrecs:
            lines_dict = {
                'date': prods.access_date,
                'source_document': '% s,% s'% ('destination.guest', prods.id),
                'source_type': 'guest',
                'product_id': prods.product_id.id,
                'membership_id': prods.membership_id.id,
                'partner_id' : prods.guest_id.id,
                'amount': prods.total_invoiced,
                'dest_id':prods.dest_id.id,
                'access_payment_method_id': prods.access_payment_method_id.id,
                'processin_date': prods.processin_date,
                'checkin_date': prods.checkin_date,
                'checkout_date': prods.checkout_date,
                'registration_user_id': prods.registration_user_id.id,
                'processin_user_id': prods.processin_user_id.id,
                'checkin_user_id': prods.checkin_user_id.id,
                'checkout_user_id': prods.checkout_user_id.id,
                'name': 'Access Report - ' + str(self.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + ' >> ' + str(self.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
            }
            
            self.env['destination.access.report'].create(lines_dict)
               
        
        return {
                        'type': 'ir.actions.act_window',
                        'view_type': 'pivot',
                        'view_mode': 'pivot,search',
                        'res_model': 'destination.access.report',
                        'name': 'Access Report - ' + str(self.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)) + ' >> ' + str(self.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None)),
                        'domain':[('report_user','=',self.env.user.id)],
                        'context':{'report_user':self.env.user.id},

                    }
        
        
        
        

    