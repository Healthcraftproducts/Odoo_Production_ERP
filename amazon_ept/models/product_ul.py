# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ProductUlEpt(models.Model):
    _name = "product.ul.ept"
    _description = 'product.ul.ept'

    dimension_unit = fields.Selection([('inches', 'Inches'), ('centimeters', 'Centimeters'), ],
                                      default='centimeters')
    name = fields.Char(index=True, required=True, translate=True)
    type = fields.Selection( \
        [('unit', 'Unit'), ('pack', 'Pack'), ('box', 'Box'), ('pallet', 'Pallet')], required=True)
    height = fields.Float('Package Height', help='The height of the package')
    width = fields.Float('Package Width', help='The width of the package')
    length = fields.Float('Package Length', help='The length of the package')
    weight = fields.Float('Empty Package Weight')
