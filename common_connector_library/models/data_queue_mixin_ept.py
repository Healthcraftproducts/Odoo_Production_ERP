# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import itertools
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
  'magento_customer_data_queue_line_ept', 'magento_export_stock_queue_line_ept', 'magento_order_data_queue_line_ept', 'sync_import_magento_product_queue_line',
  'common_log_book_ept'
]

class DataQueueMixinEpt(models.AbstractModel):
    _name = 'data.queue.mixin.ept'
    _description = 'Data Queue Mixin'

    def delete_data_queue_ept(self, queue_detail=[], is_delete_queue=False):
        """  Uses to delete unused data of queues and log book. logbook deletes which created before 7 days ago.
            @param queue_detail: list of queue records, like product, order queue [['product_queue',
            'order_queue']]
            @param is_delete_queue: Identification to delete queue
        """
        if queue_detail:
            try:
                queue_detail += ['common_log_book_ept']
                queue_detail = list(set(queue_detail))
                for tbl_name in queue_detail:
                    if tbl_name not in ALL_QUEUE_TABLES:
                        return True
                    self.delete_data_queue_schedule_activity_ept(tbl_name, is_delete_queue)
                    if is_delete_queue:
                        query = sql.SQL("delete from {}").format(sql.Identifier(tbl_name))
                        self._cr.execute(query)
                        continue
                    query = sql.SQL("delete FROM {} where cast(create_date as Date) <= current_date - %s").format(
                        sql.Identifier(tbl_name))
                    params = (7,)
                    self._cr.execute(query, params)
            except Exception as error:
                return error
        return True
    def delete_data_queue_schedule_activity_ept(self, tbl_name, is_delete_queue=False):
        """
        Define this method for delete schedule activity for the deleted data queues or
        log book records.
        :param tbl_name: deleted table name
        :param is_delete_queue: True or False
        :return: Boolean (TRUE/FALSE)
        """
        log_book_obj = self.env['common.log.book.ept']
        model_name = tbl_name.replace('_', '.')
        model = log_book_obj._get_model_id(model_name)
        if tbl_name not in ALL_QUEUE_TABLES:
            return True
        if is_delete_queue:
            query = """delete from mail_activity where res_model_id=%s"""
            self._cr.execute(query, model.id)
            query = """DELETE FROM mail_message WHERE model = %s"""
            self._cr.execute(query, model_name)
        else:
            query = sql.SQL("select id from {} where cast(create_date as Date) <= current_date - %s").format(
                sql.Identifier(tbl_name))
            params = (7,)
            results = self._cr.execute(query, params)
            results = self._cr.fetchall()
            records = tuple(set(list(itertools.chain(*results))))
            if records:
                if len(records) == 1:
                    query1 = """delete from mail_activity where res_id=%s and res_model_id=%s"""
                    params1 = (records[0], model.id)
                    query = """delete from mail_message where res_id=%s and model = %s"""
                    params = (records[0], model_name)
                    self._cr.execute(query, params)
                else:
                    query1 = """delete from mail_activity where res_id in %s and res_model_id=%s"""
                    params1 = (records, model.id)
                    query = """delete from mail_message where res_id in %s and model = %s"""
                    params = (records, model_name)
                    self._cr.execute(query, params)
                self._cr.execute(query1, params1)
        return True

