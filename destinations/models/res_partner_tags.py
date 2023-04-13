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


class PartnerTags(models.Model):
    _name = "res.partner.category"
    _inherit = ['res.partner.category']
    

    destination_rental_default_ids = fields.Many2many('destination.destination', 'rental_partner_default_category_ids',string='Rental Default Tags')
    destination_access_default_ids = fields.Many2many('destination.destination', 'access_partner_default_category_ids',string='Access  Default Tags')
