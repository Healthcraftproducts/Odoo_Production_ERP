# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models

from psycopg2 import sql

ALL_QUEUE_TABLES = [
    # All connector Queues
  'woo_coupon_data_queue_ept', 'woo_customer_data_queue_ept','woo_export_stock_queue_ept','woo_order_data_queue_ept','woo_product_data_queue_ept',
  'shopify_customer_data_queue_ept', 'shopify_export_stock_queue_ept', 'shopify_order_data_queue_ept', 'shopify_product_data_queue_ept',
  'ebay_import_product_queue', 'ebay_order_data_queue_ept',
  'walmart_order_queue_ept',
  'bol_queue_ept', 'bol_shipped_data_queue_ept',
  'magento_export_stock_queue_ept', 'magento_customer_data_queue_ept', 'magento_order_data_queue_ept', 'sync_import_magento_product_queue', 'woo_coupon_data_queue_line_ept',

  # All connector queuelines
  'woo_customer_data_queue_line_ept', 'woo_export_stock_queue_line_ept', 'woo_order_data_queue_line_ept', 'woo_product_data_queue_line_ept',
  'ebay_order_data_queue_line_ept', 'ebay_import_product_queue_line',
  'walmart_order_queue_line_ept',
  'shopify_customer_data_queue_line_ept', 'shopify_export_stock_queue_line_ept', 'shopify_order_data_queue_line_ept', 'shopify_product_data_queue_line_ept',
  'bol_order_data_queue_line_ept', 'bol_shipped_data_queue_line_ept',
  'magento_customer_data_queue_line_ept', 'magento_export_stock_queue_line_ept', 'magento_order_data_queue_line_ept', 'sync_import_magento_product_queue_line'
]


class QueueLineDashboard(models.AbstractModel):
    _name = "queue.line.dashboard"
    _description = "Queue Line Dashboard"

    def retrieve_dashboard(self, *args, **kwargs):
        return {}

    def get_data(self, **kwargs):
        """
        This method is use to prepare data for the queue line dashboard.
        :param: kwargs: dict {}
        :return: dashboard_data: It will return the list of data like
        [{'state': {'duration': [len of record, [queue_line_ids]]}},]
        """

        table = kwargs.get('table', '').replace('.', '_')
        data = dict()
        for duration in ['all', 'today', 'yesterday']:
            count, all_ids = 0, list()
            for state in ['draft', 'done', 'failed', 'cancel']:
                key = f"{duration}_{state}"
                line_ids = self._prepare_query(duration, state, table)
                count += len(line_ids)
                all_ids += line_ids
                data.update({key: [len(line_ids), line_ids]})
            data.update({duration: [count, all_ids]})
        data.update({'model': kwargs.get('table')})
        return data

    def _prepare_query(self, duration, state, table):
        """
        Prepare query to retrieve data from the given table based on duration and state.
        :param duration: selected record duration (e.g., 'today', 'yesterday')
        :param state: record state
        :param table: table name
        :return: list of record ids
        """
        # Base query, using SQL and Identifier for the table name
        if table not in ALL_QUEUE_TABLES:
            return []

        qry = sql.SQL("SELECT id FROM {} WHERE state = %s").format(sql.Identifier(table))
        if duration == 'today':
            qry += sql.SQL(" AND create_date >= CURRENT_DATE")
        elif duration == 'yesterday':
            qry += sql.SQL(" AND create_date BETWEEN CURRENT_DATE - INTERVAL '1' DAY AND CURRENT_DATE")
        self._cr.execute(qry,(state,))

        # Fetch the results and return the list of ids
        line_ids = self._cr.dictfetchall()
        return [line_id.get('id') for line_id in line_ids]

