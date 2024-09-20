from importlib.metadata import requires

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError, ValidationError


class StockPickingInherit(models.Model):
    _inherit = "stock.picking"

    def _set_delivery_package_type(self,batch_pack=False):
        """ This method returns an action allowing to set the package type and the shipping weight
        on the stock.quant.package.
        """
        self.ensure_one()
        view_id = self.env.ref('delivery.choose_delivery_package_view_form').id
        context = dict(
            self.env.context,
            current_package_carrier_type=self.carrier_id.delivery_type,
            default_picking_id=self.id,
            default_weight=self.weight,  # Include weight in the context
            weight_uom_name=self.weight_uom_name
        )
        # As we pass the `delivery_type` ('fixed' or 'base_on_rule' by default) in a key who
        # correspond to the `package_carrier_type` ('none' to default), we make a conversion.
        # No need conversion for other carriers as the `delivery_type` and
        # `package_carrier_type` will be the same in these cases.
        if context['current_package_carrier_type'] in ['fixed', 'base_on_rule']:
            context['current_package_carrier_type'] = 'none'
        return {
            'name': _('Package Details'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'choose.delivery.package',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': context,
        }

class ChooseDeliveryPackage(models.TransientModel):
    _inherit = 'choose.delivery.package'

    def _get_default_length_uom(self):
        return self.env['product.template']._get_length_uom_name_from_ir_config_parameter()

    def _compute_length_uom_name(self):
        self.length_uom_name = ""

    weight = fields.Float(string="Weight")
    length_uom_name = fields.Char(string='Length unit of measure label', compute='_compute_length_uom_name', default=_get_default_length_uom)
    packaging_length = fields.Integer('Length', help="Packaging Length",required=True)
    height = fields.Integer('Height', help="Packaging Height",required=True)
    width = fields.Integer('Width', help="Packaging Width",required=True)

    def action_put_in_pack(self):
        move_line_ids = self.picking_id._package_move_lines()
        delivery_package = self.picking_id._put_in_pack(move_line_ids)
        # write shipping weight and package type on 'stock_quant_package' if needed
        if self.delivery_package_type_id:
            delivery_package.package_type_id = self.delivery_package_type_id
        if self.shipping_weight:
            delivery_package.shipping_weight = self.shipping_weight

        if self.packaging_length and self.height and self.width != 0:
            self.delivery_package_type_id.packaging_length = self.packaging_length
            self.delivery_package_type_id.height = self.height
            self.delivery_package_type_id.width = self.width
            delivery_package.packaging_length = self.packaging_length
            delivery_package.height = self.height
            delivery_package.width = self.width
        else:
            raise ValidationError(_("Dimensions are Empty !! Kindly update Dimensions"))
        if self.shipping_weight:
            self.delivery_package_type_id.base_weight = self.shipping_weight
        elif self.weight:
            self.delivery_package_type_id.base_weight = self.weight
        else:
            self.delivery_package_type_id.base_weight = 0

    class StockQuantPackage(models.Model):
        _inherit = 'stock.quant.package'

        def _get_default_length_uom(self):
            return self.env['product.template']._get_length_uom_name_from_ir_config_parameter()

        def _compute_length_uom_name(self):
            self.length_uom_name = ""

        length_uom_name = fields.Char(string='Length unit of measure label', compute='_compute_length_uom_name', default=_get_default_length_uom)
        packaging_length = fields.Integer('Length', help="Packaging Length")
        height = fields.Integer('Height', help="Packaging Height")
        width = fields.Integer('Width', help="Packaging Width")

