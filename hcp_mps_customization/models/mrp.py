# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import namedtuple, OrderedDict, defaultdict
from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import api, fields, models, registry, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import split_every
from psycopg2 import OperationalError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_is_zero, float_round


from werkzeug.urls import url_encode

class MrpBOM(models.Model):
    _inherit = 'mrp.bom'
    
    is_main_bom = fields.Boolean('Is this main BOM?')

 
class MrpProduction(models.Model):
    _inherit = 'mrp.production'
    
    mo_reference = fields.Char('MPS Reference')

class MrpProductionSchedule(models.Model):
    _inherit = 'mrp.production.schedule'
    

    def _get_procurement_extra_values(self, forecast_values):
        """ Extra values that could be added in the vals for procurement.

        return values pass to the procurement run method.
        rtype dict
        """
        next_sequence= self.env['ir.sequence'].with_context(force_company=self.company_id.id).next_by_code('mrp.production.schedule') or _('New')
        return {
            'date_planned': forecast_values['date_start'],
            'warehouse_id': self.warehouse_id,
            'mo_reference': next_sequence,
        }
            
class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom):
        vals = super(StockRule ,self)._prepare_mo_vals(product_id, product_qty, product_uom, location_id, name, origin, company_id, values,bom)
        mo_reference = values.get('mo_reference')
        if origin != 'MPS':
            mrp_obj = self.env['mrp.production'].search([('name','=', origin)])
            mps_origin = mrp_obj.mo_reference
            if mps_origin:
                mo_reference = mps_origin
        vals.update({'mo_reference': mo_reference})
        return vals


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_procurement_values(self):
        values = super(StockMove, self)._prepare_procurement_values()
        values.update({
            'mo_reference': False
        })
        return values
    

class ProductReplenish(models.TransientModel):
    _inherit = 'product.replenish'

    def _prepare_run_values(self):
        values = super(ProductReplenish, self)._prepare_run_values()
        values.update({'mo_reference': False})
        return values
