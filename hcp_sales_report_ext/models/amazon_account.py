import json
import logging

import dateutil.parser
import psycopg2
from werkzeug import urls

from odoo import _, api, exceptions, fields, models
from odoo.exceptions import UserError
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY as CONCURRENCY_ERRORS

from odoo.addons.sale_amazon import const, utils as amazon_utils
from odoo.addons.sale_amazon.controllers.onboarding import compute_oauth_signature

_logger = logging.getLogger(__name__)

class AmazonAccount(models.Model):
    _inherit = 'amazon.account'


    def _process_order_data(self, order_data):
        """ Process the provided order data and return the matching sales order, if any.

        If no matching sales order is found, a new one is created if it is in a 'synchronizable'
        status: 'Shipped' or 'Unshipped', if it is respectively an FBA or an FBA order. If the
        matching sales order already exists and the Amazon order was canceled, the sales order is
        also canceled.

        Note: self.ensure_one()

        :param dict order_data: The order data to process.
        :return: The matching Amazon order, if any, as a `sale.order` record.
        :rtype: recordset of `sale.order`
        """
        self.ensure_one()

        # Search for the sales order based on its Amazon order reference.
        amazon_order_ref = order_data['AmazonOrderId']
        order = self.env['sale.order'].search(
            [('amazon_order_ref', '=', amazon_order_ref)], limit=1
        )
        amazon_status = order_data['OrderStatus']
        if not order:  # No sales order was found with the given Amazon order reference.
            fulfillment_channel = order_data['FulfillmentChannel']
            if amazon_status in const.STATUS_TO_SYNCHRONIZE[fulfillment_channel]:
                # Create the sales order and generate stock moves depending on the Amazon channel.
                order = self._create_order_from_data(order_data)
                if order.amazon_channel == 'fba':
                    self._generate_stock_moves(order)
                elif order.amazon_channel == 'fbm':
                    order.with_context(mail_notrack=True).action_confirm()
                _logger.info(
                    "Created a new sales order with amazon_order_ref %s for Amazon account with "
                    "id %s.", amazon_order_ref, self.id
                )
            else:
                _logger.info(
                    "Ignored Amazon order with reference %(ref)s and status %(status)s for Amazon "
                    "account with id %(account_id)s.",
                    {'ref': amazon_order_ref, 'status': amazon_status, 'account_id': self.id},
                )
        else:  # The sales order already exists.
            if amazon_status == 'Canceled' and order.state != 'cancel':
                order._action_cancel()
                _logger.info(
                    "Canceled sales order with amazon_order_ref %s for Amazon account with id %s.",
                    amazon_order_ref, self.id
                )
            else:
                _logger.info(
                    "Ignored already synchronized sales order with amazon_order_ref %s for Amazon"
                    "account with id %s.", amazon_order_ref, self.id
                )
        return order

    def _create_order_from_data(self, order_data):
        """ Create a new sales order based on the provided order data.

        Note: self.ensure_one()

        :param dict order_data: The order data to create a sales order from.
        :return: The newly created sales order.
        :rtype: record of `sale.order`
        """
        self.ensure_one()

        # Prepare the order line values.
        shipping_code = order_data.get('ShipServiceLevel')
        shipping_product = self._find_matching_product(
            shipping_code, 'shipping_product', 'Shipping', 'service'
        )
        currency = self.env['res.currency'].with_context(active_test=False).search(
            [('name', '=', order_data['OrderTotal']['CurrencyCode'])], limit=1
        )
        amazon_order_ref = order_data['AmazonOrderId']
        contact_partner, delivery_partner = self._find_or_create_partners_from_data(order_data)
        fiscal_position = self.env['account.fiscal.position'].with_company(
            self.company_id
        )._get_fiscal_position(contact_partner, delivery_partner)
        order_lines_values = self._prepare_order_lines_values(
            order_data, currency, fiscal_position, shipping_product
        )

        # Create the sales order.
        fulfillment_channel = order_data['FulfillmentChannel']
        # The state is first set to 'sale' and later to 'done' to generate a picking if fulfilled
        # by merchant, or directly set to 'done' to generate no picking if fulfilled by Amazon.
        state = 'sale' if fulfillment_channel == 'AFN' else 'sale'
        purchase_date = dateutil.parser.parse(order_data['PurchaseDate']).replace(tzinfo=None)
        order_vals = {
            'origin': f"Amazon Order {amazon_order_ref}",
            'state': state,
            'date_order': purchase_date,
            'partner_id': contact_partner.id,
            'pricelist_id': self._find_or_create_pricelist(currency).id,
            'order_line': [(0, 0, order_line_values) for order_line_values in order_lines_values],
            'invoice_status': 'no',
            'partner_shipping_id': delivery_partner.id,
            'require_signature': False,
            'require_payment': False,
            'fiscal_position_id': fiscal_position.id,
            'company_id': self.company_id.id,
            'user_id': self.user_id.id,
            'team_id': self.team_id.id,
            'amazon_order_ref': amazon_order_ref,
            'amazon_channel': 'fba' if fulfillment_channel == 'AFN' else 'fbm',
        }
        if self.location_id.warehouse_id:
            order_vals['warehouse_id'] = self.location_id.warehouse_id.id
        return self.env['sale.order'].with_context(
            mail_create_nosubscribe=True
        ).with_company(self.company_id).create(order_vals)