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



class ProductTemplateDestReportWizard(models.TransientModel):
    _name = 'destination.product.report.wizard'
    _description = 'Destination Report Wizard'
    
    
    start_date = fields.Datetime("Start Date", default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hour=0) - timedelta(hours=3))
    end_date = fields.Datetime("End Date", default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hour=0, days=1) - timedelta(hours=3))
    
    
    def generate_rental_report(self):
        
        delrecs = self.env['destination.product.report'].search([('user_id','=',self.env.user.id)])
        if delrecs:
            delrecs.unlink()
        
        prodrecs = self.env['product.product'].search([('dest_ok','=',True),('dest_product_group','!=','access')])
        
        for prods in prodrecs:
            lines_dict = {
                'product_id' : prods.id,
                'start_date' : self.start_date,
                'end_date' : self.end_date,
                'rental_status': 'actual',
            }

            self.env['destination.product.report'].create(lines_dict)
            
            lines_dict = {
                'product_id' : prods.id,
                'start_date' : self.start_date,
                'end_date' : self.end_date,
                'rental_status': 'plan',
            }

            self.env['destination.product.report'].create(lines_dict)
            
        return {
                        'type': 'ir.actions.act_window',
                        'view_type': 'dashboard',
                        'view_mode': 'dashboard,search',
                        'res_model': 'destination.product.report',
                        'domain':[],
                        'context':{},
                        'name': 'Occupancy Report - ' + str(self.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date()) + ' >> ' + str(self.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date()),

                    }
        
            