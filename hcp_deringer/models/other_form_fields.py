# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.osv import expression
import requests, json
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
from datetime import date, datetime
import logging
_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    mid = fields.Char('MID')
    irs_number = fields.Char('IRS No.')

class ResPartner(models.Model):
    _inherit = "res.partner"

    irs_number = fields.Char('IRS No.')   
 
class AccountMove(models.Model):
    _inherit = "account.move"
    
    deringer_shipping_done = fields.Boolean('Deringer Shipment Done?',readonly=1,default=False)

    def unlink_deringer_shipment(self):
        res={}
        self.write({'deringer_shipping_done':False})
        return res
