# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Added to create queue or amazon shipped order and process to import orders in odoo.
"""

from odoo import models


class AmazonQueueProcessWizardEpt(models.TransientModel):
    """
    Added to store the shipped order data in queue.
    """
    _name = 'amazon.queue.process.wizard.ept'
    _description = 'Amazon Queue Process Wizard Ept'

    def process_orders_queue_manually(self):
        """
        This method is get the selected queue orders.
        """
        sale_order_obj = self.env['sale.order']
        shipped_order_queue_obj = self.env['shipped.order.data.queue.ept']
        order_queue_ids = self._context.get('active_ids', False)

        for order_queue_id in order_queue_ids:
            data_queue = shipped_order_queue_obj.browse(order_queue_id)
            sale_order_obj.amz_create_sales_order(data_queue)
            data_queue.amz_delete_processed_data_queue_lines(data_queue)
            self._cr.commit()
        return True
