from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.osv import expression
import requests, json
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
from datetime import date, datetime
import logging


class Partner(models.Model):
    _inherit = "res.partner"

    irs_no = fields.Char('IRS No')
    mid = fields.Char('MID')
    type_hcp = fields.Char('Type')
    pnc_email = fields.Char('PNCEmail')
