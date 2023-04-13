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



class MembershipReportWizard(models.TransientModel):
    _name = 'destination.membership.report.wizard'
    _description = 'Membership Report Wizard'
    
    
    start_date = fields.Datetime("Start Date", default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hour=0) - timedelta(hours=3))
    end_date = fields.Datetime("End Date", default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hour=0, days=1) - timedelta(hours=3))
    
    
    def generate_membership_report(self):
        
        delrecs = self.env['destination.membership.report'].search([('report_user','=',self.env.user.id)])
        if delrecs:
            delrecs.unlink()
        
        membershiprecs = self.env['destination.membership'].search([('active','=',True),('state','in',['confirmed','active','hold','late','checked-out','done'])]).filtered(lambda r: r.start_date < self.end_date and r.end_date > self.start_date)
        
        for prods in membershiprecs:
            lines_dict = {
                'membership_id' : prods.id,
                
            }

            self.env['destination.membership.report'].create(lines_dict)
        
        
        return {
                        'type': 'ir.actions.act_window',
                        'view_type': 'dashboard',
                        'view_mode': 'dashboard,search',
                        'res_model': 'destination.membership.report',
                        'name': 'Rental Report - ' + str(self.start_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date()) + ' >> ' + str(self.end_date.replace(tzinfo=UTC).astimezone(timezone(self.env.user.tz or 'UTC')).replace(tzinfo=None).date()),
                        'domain':[],
                        'context':{},

                    }
        
        
        
        

    