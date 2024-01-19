# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
"""
Added class to store the amazon instance details and prepare routes,
test instance connection and process unsellable and sellable operations
"""
import json
from datetime import date, datetime

from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError
from ..endpoint import VERIFY_ENDPOINT

AMZ_INSTANCE_EPT = 'amazon.instance.ept'
STOCK_LOCATION = 'stock.location'
STOCK_WAREHOUSE = 'stock.warehouse'
ACCOUNT_ACCOUNT = 'account.account'


class AmazonInstanceEpt(models.Model):
    """
    Added class to store the amazon instance details and perform amazon operations
    based on instance and added fields to store instance details and config the instance
    warehouse and others.
    """
    _name = 'amazon.instance.ept'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Amazon Instance Details'
    _order = 'sequence'

    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', required=True)
    marketplace_id = fields.Many2one('amazon.marketplace.ept', string='Marketplace', required=True,
                                     domain="[('seller_id','=',seller_id),"
                                            "('is_participated','=',True)]")
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position',
                                         help="Fiscal Position for Taxes calculation")
    name = fields.Char(size=120, required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    color = fields.Integer(string='Color Index')
    warehouse_id = fields.Many2one(comodel_name=STOCK_WAREHOUSE, string='Warehouse', required=True)
    pricelist_id = fields.Many2one(comodel_name='product.pricelist', string='Pricelist')
    lang_id = fields.Many2one('res.lang', string='Language')
    partner_id = fields.Many2one('res.partner', string='Default Customer')
    merchant_id = fields.Char(related="seller_id.merchant_id")
    market_place_id = fields.Char("Marketplace ID", related="marketplace_id.market_place_id", store=True)
    team_id = fields.Many2one('crm.team', 'Sales Team')
    country_id = fields.Many2one("res.country", "Country", related="marketplace_id.country_id")
    flag_url = fields.Char(string="Country Flag Url", related="country_id.image_url")
    active = fields.Boolean(default=True)
    amazon_property_account_payable_id = fields.Many2one(ACCOUNT_ACCOUNT,
                                                         string="Account Payable",
                                                         help='This account will be used instead '
                                                              'of the default one as the payable '
                                                              'account for the current partner')
    amazon_property_account_receivable_id = fields.Many2one(ACCOUNT_ACCOUNT,
                                                            string="Account Receivable",
                                                            help='This account will be used '
                                                                 'instead of the default one as '
                                                                 'the receivable account for the '
                                                                 'current partner')
    stock_field = fields.Selection([('free_qty', 'Free Quantity'), ('virtual_available', 'Forecast Quantity')],
                                   string="Stock Type", default='free_qty')

    settlement_report_journal_id = fields.Many2one('account.journal', string='Settlement Report Journal')
    ending_balance_account_id = fields.Many2one(ACCOUNT_ACCOUNT, string="Ending Balance Account")
    ending_balance_description = fields.Char()
    fba_warehouse_id = fields.Many2one(comodel_name=STOCK_WAREHOUSE, string='FBA Warehouse',
                                       help="Select Warehouse for Manage FBA Stock")
    inventory_last_sync_on = fields.Datetime("Last FBM Inventory Sync Time")
    removal_order_config_ids = fields.One2many("removal.order.config.ept", 'instance_id',
                                               string="Removal Order Configuration")
    is_allow_to_create_removal_order = fields.Boolean('Allow Create Removal Order In FBA?',
                                                      help="Allow to create removal order in FBA.")
    removal_warehouse_id = fields.Many2one(STOCK_WAREHOUSE, string="Removal Warehouse",
                                           help="Removal Warehouse")
    is_configured_rm_ord_routes = fields.Boolean(string="Configured Removal Order Routes",
                                                 default=False,
                                                 help="Configured Removal Order Routes")
    fba_order_count = fields.Integer(compute='_compute_orders_and_invoices',
                                     string="FBA Sales Orders Count")
    fbm_order_count = fields.Integer(compute='_compute_orders_and_invoices',
                                     string="FBM Sales Orders Count")
    fba_invoice_count = fields.Integer(compute='_compute_orders_and_invoices',
                                       string="FBA Sales Invoices Count")
    fbm_invoice_count = fields.Integer(compute='_compute_orders_and_invoices',
                                       string="FBM Sales Invoices Count")
    amz_tax_id = fields.Many2one('account.tax', string="Tax Account")
    is_use_percent_tax = fields.Boolean(string="Use Tax Percent?")

    stock_update_warehouse_ids = fields.Many2many(STOCK_WAREHOUSE, 'stock_warehouse_amazon_instance_rel',
                                                  'instance_id', 'warehouse_id', string="FBM Warehouse(S)",
                                                  copy=False, help="Warehouses which will fulfill the orders")
    amazon_order_data = fields.Text(compute="_compute_kanban_amazon_order_data")
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account (Marketplace)',
                                          help='Analytic Account for Amazon Marketplace.')
    sequence = fields.Integer(string='Sequence', help="Determine the display order")

    def write(self, vals):
        """
        This method is Overridden with super call
        to make a Logger Note about the changes that user have made in the current model
        :return super()
        """
        for amz_instance in self:
            msg = ""
            new = amz_instance.new(vals)
            for key, value in vals.items():
                if getattr(amz_instance, key) != getattr(new, key):
                    if isinstance(getattr(amz_instance, key), models.BaseModel) and \
                            getattr(amz_instance, key).ids == getattr(new, key).ids:
                        continue
                    if amz_instance.seller_id.amz_check_last_sync_field(key):
                        continue
                    msg += "<li><b>%s:  </b> %s  ->  %s</li>" % \
                           (amz_instance._fields.get(key).string,
                            amz_instance.env['ir.qweb']._get_field(amz_instance, key, '', '', {}, {})[1],
                            amz_instance.env['ir.qweb']._get_field(new, key, '', '', {}, {})[1])
            if msg and msg != "":
                amz_instance.message_post(body=msg)
        return super(AmazonInstanceEpt, self).write(vals)

    def _compute_kanban_amazon_order_data(self):
        """
        Use: Fetch data for the dashboard and prepare json data
        :return: json data
        """
        context = dict(self.env.context)
        if not self._context.get('sort', ''):
            context.update({'sort': 'week'})
        if not self._context.get('fulfillment_by', ''):
            context.update({'fulfillment_by': 'Both'})
        self.env.context = context
        for record in self:
            #Prepare where clause for fulfillment by as per selected
            fulfillment_by_where_clause = self.prepare_fulfillment_by_where_clause(record)
            # Prepare values for Graph
            values = self.get_graph_data(record, fulfillment_by_where_clause)
            data_type, comparison_value = self.get_compare_data(record, fulfillment_by_where_clause)
            # Total sales
            total_sales = round(sum([key['y'] for key in values]), 2)
            # Order count query
            fbm_order_data = self.get_fbm_total_orders(record, fulfillment_by_where_clause)
            fba_order_data = self.get_fba_total_orders(record, fulfillment_by_where_clause)
            # Product count query
            product_data = self.get_total_products(record)
            record.amazon_order_data = json.dumps({
                "values": values,
                "title": "",
                "key": "Order: Untaxed amount",
                "area": True,
                "color": "#875A7B",
                "is_sample_data": False,
                "total_sales": total_sales,
                "fbm_order_data": fbm_order_data,
                "fba_order_data": fba_order_data,
                "product_date": product_data,
                "sort_on": self._context.get('sort', ''),
                "fulfillment_by": self._context.get('fulfillment_by', ''),
                "currency_symbol": record.marketplace_id.currency_id.symbol or '',
                "graph_sale_percentage": {'type': data_type, 'value': comparison_value}
            })

    @staticmethod
    def get_fba_total_orders(record, fulfillment_by_where_clause):
        """
        This method will get the fba orders total
        :return:
        """
        def orders_of_current_week(record, fulfillment_by_where_clause):
            record._cr.execute("""select id from sale_order where date(date_order)
                                >= (select date_trunc('week', date(current_date)))
                                and amz_instance_id= {0} and state in ('sale','done') and amz_fulfillment_by = 'FBA' {1}
                                order by date(date_order)""" .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        def orders_of_current_month(record, fulfillment_by_where_clause):
            record._cr.execute("""select id from sale_order where date(date_order) >=
                                (select date_trunc('month', date(current_date)))
                                and amz_instance_id= {0} and state in ('sale','done') and amz_fulfillment_by = 'FBA' {1}
                                order by date(date_order)""" .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        def orders_of_current_year(record, fulfillment_by_where_clause):
            record._cr.execute("""select id from sale_order where date(date_order) >=
                                (select date_trunc('year', date(current_date)))
                                and amz_instance_id= {0} and state in ('sale','done') and amz_fulfillment_by = 'FBA' {1}
                                order by date(date_order)""" .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        def orders_of_all_time(record, fulfillment_by_where_clause):
            record._cr.execute(
                """select id from sale_order where amz_instance_id = {0} and state in ('sale','done') and
                amz_fulfillment_by = 'FBA' {1}""" .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        order_data = {}
        if record._context.get('sort', '') == "week":
            result = orders_of_current_week(record, fulfillment_by_where_clause)
        elif record._context.get('sort', '') == "month":
            result = orders_of_current_month(record, fulfillment_by_where_clause)
        elif record._context.get('sort', '') == "year":
            result = orders_of_current_year(record, fulfillment_by_where_clause)
        else:
            result = orders_of_all_time(record, fulfillment_by_where_clause)
        order_ids = [data.get('id', False) for data in result]
        view = record.env.ref('amazon_ept.action_amazon_fba_sales_order_ept').sudo().read()[0]
        action = record.prepare_action(view, [('id', 'in', order_ids)])
        order_data.update({'order_count': len(order_ids), 'order_action': action})
        return order_data

    @staticmethod
    def get_total_products(record):
        """
        This method will get the list of products exported from the connector
        :return: total number of products ids and action for products
        """
        product_data = {}
        record._cr.execute("""select count(id) as total_count from amazon_product_ept where
                        exported_to_amazon = True and instance_id = %s""" % record.id)
        result = record._cr.dictfetchall()
        if result:
            total_count = result[0].get('total_count', 0.0)
        view = record.env.ref('amazon_ept.action_amazon_product_ept').sudo().read()[0]
        action = record.prepare_action(view, [('exported_to_amazon', '=', True), ('instance_id', '=', record.id)])
        product_data.update({'product_count': total_count, 'product_action': action})
        return product_data

    @staticmethod
    def get_compare_data(record, fulfillment_by_where_clause):
        """
        :return: Comparison ratio of orders (weekly,monthly and yearly based on selection)
        """
        data_type = False
        total_percentage = 0.0

        def get_compared_week_data(record, fulfillment_by_where_clause):
            current_total = 0.0
            previous_total = 0.0
            day_of_week = date.weekday(date.today())
            record._cr.execute("""select sum(amount_untaxed) as current_week from sale_order
                                where date(date_order) >= (select date_trunc('week', date(current_date))) and
                                amz_instance_id={0} and state in
                                 ('sale','done') {1}""" .format(record.id, fulfillment_by_where_clause))
            current_week_data = record._cr.dictfetchone()
            current_total = current_week_data.get('current_week', 0.0) if current_week_data and current_week_data.get(
                'current_week', 0.0) else 0
            # Previous week data
            record._cr.execute("""select sum(amount_untaxed) as previous_week from sale_order
                            where date(date_order) between (select date_trunc('week', current_date) - interval '7 day') 
                            and (select date_trunc('week', (select date_trunc('week', current_date) - interval '7
                            day')) + interval '{0} day')
                            and amz_instance_id={1} and state in ('sale','done') {2}
                            """ .format(day_of_week, record.id, fulfillment_by_where_clause))

            previous_week_data = record._cr.dictfetchone()
            previous_total = previous_week_data.get(
                'previous_week', 0.0) if previous_week_data and previous_week_data.get('previous_week', 0.0) else 0
            return current_total, previous_total

        def get_compared_month_data(record, fulfillment_by_where_clause):
            current_total = 0.0
            previous_total = 0.0
            day_of_month = date.today().day - 1
            record._cr.execute("""select sum(amount_untaxed) as current_month from sale_order
                                where date(date_order) >= (select date_trunc('month', date(current_date)))
                                and amz_instance_id={0} and state in ('sale','done') {1}""".format(
                                    record.id, fulfillment_by_where_clause))
            current_data = record._cr.dictfetchone()
            current_total = current_data.get('current_month', 0.0) if current_data and current_data.get(
                'current_month', 0.0) else 0
            # Previous week data
            record._cr.execute("""select sum(amount_untaxed) as previous_month from sale_order where date(date_order)
                            between (select date_trunc('month', current_date) - interval '1 month') and
                            (select date_trunc('month', (select date_trunc('month', current_date) - interval
                            '1 month')) + interval '{0} days')
                            and amz_instance_id={1} and state in ('sale','done') {2}
                            """ .format(day_of_month, record.id, fulfillment_by_where_clause))
            previous_data = record._cr.dictfetchone()
            previous_total = previous_data.get('previous_month', 0.0) if previous_data and previous_data.get(
                'previous_month', 0.0) else 0
            return current_total, previous_total

        def get_compared_year_data(record, fulfillment_by_where_clause):
            current_total = 0.0
            previous_total = 0.0
            year_begin = date.today().replace(month=1, day=1)
            year_end = date.today()
            delta = (year_end - year_begin).days - 1
            record._cr.execute("""select sum(amount_untaxed) as current_year from sale_order
                                where date(date_order) >= (select date_trunc('year', date(current_date)))
                                and amz_instance_id={0} and state in
                                 ('sale','done') {1}""" .format(record.id, fulfillment_by_where_clause))
            current_data = record._cr.dictfetchone()
            current_total = current_data.get('current_year', 0.0) if current_data and current_data.get(
                'current_year', 0.0) else 0
            # Previous week data
            record._cr.execute("""select sum(amount_untaxed) as previous_year from sale_order where date(date_order)
                            between (select date_trunc('year', date(current_date) - interval '1 year')) and 
                            (select date_trunc('year', date(current_date) - interval '1 year') + interval '{0} days') 
                            and amz_instance_id={1} and state in ('sale','done') {2}
                            """ .format(delta, record.id, fulfillment_by_where_clause))

            previous_data = record._cr.dictfetchone()
            previous_total = previous_data.get('previous_year', 0.0) if previous_data and previous_data.get(
                'previous_year', 0.0) else 0
            return current_total, previous_total

        if record._context.get('sort', '') == 'week':
            current_total, previous_total = get_compared_week_data(record, fulfillment_by_where_clause)
        elif record._context.get('sort', '') == "month":
            current_total, previous_total = get_compared_month_data(record, fulfillment_by_where_clause)
        elif record._context.get('sort', '') == "year":
            current_total, previous_total = get_compared_year_data(record, fulfillment_by_where_clause)
        else:
            current_total, previous_total = 0.0, 0.0
        if current_total > 0.0:
            if current_total >= previous_total:
                data_type = 'positive'
                total_percentage = (current_total - previous_total) * 100 / current_total
            if previous_total > current_total:
                data_type = 'negative'
                total_percentage = (previous_total - current_total) * 100 / current_total
        return data_type, round(total_percentage, 2)

    @staticmethod
    def get_graph_data(record, fulfillment_by_where_clause):
        """
        This method will get the details of sale orders and total amount month wise or year wise to prepare the graph
        :return: sale order date or month and sum of sale orders amount of current instance
        """

        def get_current_week_date(record, fulfillment_by_where_clause):
            record._cr.execute("""SELECT to_char(date(d.day),'DAY'), t.amount_untaxed as sum
                                FROM  (
                                   SELECT day
                                   FROM generate_series(date(date_trunc('week', (current_date)))
                                    , date(date_trunc('week', (current_date)) + interval '6 days')
                                    , interval  '1 day') day
                                   ) d
                                LEFT   JOIN 
                                (SELECT date(date_order)::date AS day, sum(amount_untaxed) as amount_untaxed
                                   FROM   sale_order
                                   WHERE  date(date_order) >= (select date_trunc('week', date(current_date)))
                                   AND    date(date_order) <= (select date_trunc('week', date(current_date)) 
                                   + interval '6 days')
                                   AND amz_instance_id={0} and state in ('sale','done') {1}
                                   GROUP  BY 1
                                   ) t USING (day)
                                ORDER  BY day""" .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        def graph_of_current_month(record, fulfillment_by_where_clause):
            record._cr.execute("""select EXTRACT(DAY from date(date_day)) :: integer,sum(amount_untaxed) from (
                        SELECT 
                          day::date as date_day,
                          0 as amount_untaxed
                        FROM generate_series(date(date_trunc('month', (current_date)))
                            , date(date_trunc('month', (current_date)) + interval '1 MONTH - 1 day')
                            , interval  '1 day') day
                        union all
                        SELECT date(date_order)::date AS date_day,
                        sum(amount_untaxed) as amount_untaxed
                          FROM   sale_order
                        WHERE  date(date_order) >= (select date_trunc('month', date(current_date)))
                        AND date(date_order)::date <= (select date_trunc('month', date(current_date)) 
                        + '1 MONTH - 1 day')
                        and amz_instance_id = {0} and state in ('sale','done') {1}
                        group by 1
                        )foo 
                        GROUP  BY 1
                        ORDER  BY 1""" .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        def graph_of_current_year(record, fulfillment_by_where_clause):
            record._cr.execute("""select TRIM(TO_CHAR(DATE_TRUNC('month',month),'MONTH')),sum(amount_untaxed) from
                                (SELECT DATE_TRUNC('month',date(day)) as month,
                                  0 as amount_untaxed
                                FROM generate_series(date(date_trunc('year', (current_date)))
                                , date(date_trunc('year', (current_date)) + interval '1 YEAR - 1 day')
                                , interval  '1 MONTH') day
                                union all
                                SELECT DATE_TRUNC('month',date(date_order)) as month,
                                sum(amount_untaxed) as amount_untaxed
                                  FROM   sale_order
                                WHERE  date(date_order) >= (select date_trunc('year', date(current_date))) AND 
                                date(date_order)::date <= (select date_trunc('year', date(current_date)) 
                                + '1 YEAR - 1 day')
                                and amz_instance_id = {0} and state in ('sale','done') {1}
                                group by DATE_TRUNC('month',date(date_order))
                                order by month
                                )foo 
                                GROUP  BY foo.month
                                order by foo.month""" .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        def graph_of_all_time(record, fulfillment_by_where_clause):
            record._cr.execute("""select TRIM(TO_CHAR(DATE_TRUNC('month',date_order),'YYYY-MM')),sum(amount_untaxed)
                                from sale_order where amz_instance_id = {0} and state in ('sale','done') {1}
                                group by DATE_TRUNC('month',date_order) 
                                order by DATE_TRUNC('month',date_order)""" .format(
                                    record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        # Prepare values for Graph
        if record._context.get('sort', '') == 'week':
            result = get_current_week_date(record, fulfillment_by_where_clause)
        elif record._context.get('sort', '') == "month":
            result = graph_of_current_month(record, fulfillment_by_where_clause)
        elif record._context.get('sort', '') == "year":
            result = graph_of_current_year(record, fulfillment_by_where_clause)
        else:
            result = graph_of_all_time(record, fulfillment_by_where_clause)
        values = [{"x": ("{}".format(data.get(list(data.keys())[0], []))),
                   "y": data.get('sum', 0.0) or 0.0} for data in result]
        return values

    @staticmethod
    def prepare_fulfillment_by_where_clause(record):
        """
        Define method for the prepare fulfillment by where clause
        :return: where cluse string
        """
        if record._context.get('fulfillment_by') == 'FBA':
            fulfillment_whare_cluse = """AND amz_fulfillment_by = 'FBA'"""
        elif record._context.get('fulfillment_by') == 'FBM':
            fulfillment_whare_cluse = """AND amz_fulfillment_by = 'FBM'"""
        else:
            fulfillment_whare_cluse = """AND amz_fulfillment_by in ('FBM', 'FBA')"""
        return fulfillment_whare_cluse

    @staticmethod
    def get_fbm_total_orders(record, fulfillment_by_where_clause):
        """
        This method fetch data of fbm orders
        :return: list of dict
        """

        def orders_of_current_week(record, fulfillment_by_where_clause):
            record._cr.execute("""select id from sale_order where date(date_order)
                                >= (select date_trunc('week', date(current_date)))
                                and amz_instance_id= {0} and state in ('sale','done') and amz_fulfillment_by = 'FBM' {1}
                                order by date(date_order)
                        """  .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        def orders_of_current_month(record, fulfillment_by_where_clause):
            record._cr.execute("""select id from sale_order where date(date_order) >=
                                (select date_trunc('month', date(current_date)))
                                and amz_instance_id= {0} and state in ('sale','done') and amz_fulfillment_by = 'FBM' {1}
                                order by date(date_order)
                        """ .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        def orders_of_current_year(record, fulfillment_by_where_clause):
            record._cr.execute("""select id from sale_order where date(date_order) >=
                                (select date_trunc('year', date(current_date)))
                                and amz_instance_id= {0} and state in ('sale','done') and amz_fulfillment_by = 'FBM' {1}
                                order by date(date_order)"""
                               .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        def orders_of_all_time(record, fulfillment_by_where_clause):
            record._cr.execute(
                """select id from sale_order where amz_instance_id = {0} and state in ('sale','done') and 
                amz_fulfillment_by = 'FBM' {1}""" .format(record.id, fulfillment_by_where_clause))
            return record._cr.dictfetchall()

        order_data = {}
        if record._context.get('sort', '') == "week":
            result = orders_of_current_week(record, fulfillment_by_where_clause)
        elif record._context.get('sort', '') == "month":
            result = orders_of_current_month(record, fulfillment_by_where_clause)
        elif record._context.get('sort', '') == "year":
            result = orders_of_current_year(record, fulfillment_by_where_clause)
        else:
            result = orders_of_all_time(record, fulfillment_by_where_clause)
        order_ids = [data.get('id', False) for data in result]
        view = record.env.ref('amazon_ept.action_amazon_fbm_sales_order_ept').sudo().read()[0]
        action = record.prepare_action(view, [('id', 'in', order_ids)])
        order_data.update({'order_count': len(order_ids), 'order_action': action})
        return order_data

    @staticmethod
    def prepare_action(view, domain):
        """
        Use: To prepare action dictionary
        :return: action details
        """
        action = {
            'name': view.get('name', ''),
            'type': view.get('type', ''),
            'domain': domain,
            'view_mode': view.get('view_mode', ''),
            'view_id': view.get('view_id', False)[0] if view.get('view_id', False) else False,
            'views': view.get('views', ''),
            'res_model': view.get('res_model', ''),
            'target': view.get('target', ''),
        }

        if 'tree' in action['views'][0]:
            action['views'][0] = (action['view_id'], 'list')
        return action

    def _compute_orders_and_invoices(self):
        """
        Count Orders and Invoices via sql query from database because of increase speed of Dashboard.
        :return:
        """
        for instance in self:
            self._cr.execute(
                "SELECT count(*) AS row_count FROM sale_order WHERE amz_fulfillment_by = 'FBA' "
                "and state not in ('draft','sent','cancel') and amz_instance_id = %s" % (instance.id))
            instance.fba_order_count = self._cr.fetchall()[0][0]

            self._cr.execute(
                "SELECT count(*) AS row_count FROM sale_order WHERE amz_fulfillment_by = 'FBM' "
                "and state not in ('draft','sent','cancel') and amz_instance_id = %s" % (instance.id))
            instance.fbm_order_count = self._cr.fetchall()[0][0]

            self._cr.execute(
                "SELECT count(*) AS row_count FROM account_move WHERE amz_fulfillment_by = 'FBM' "
                "and amazon_instance_id = %s" % (instance.id))
            instance.fbm_invoice_count = self._cr.fetchall()[0][0]

            self._cr.execute(
                "SELECT count(*) AS row_count FROM account_move WHERE amz_fulfillment_by = 'FBA' "
                "and amazon_instance_id = %s" % instance.id)
            instance.fba_invoice_count = self._cr.fetchall()[0][0]

    def test_amazon_connection(self):
        """
        Test Amazon Connection from merchant_id
        :return: Boolean
        :Mod: set odoo version in seller details for check Amazon connection
        """
        iap_account_obj = self.env['iap.account']
        ir_config_parameter_obj = self.env['ir.config_parameter']
        account = iap_account_obj.search([('service_name', '=', 'amazon_ept')])
        dbuuid = ir_config_parameter_obj.sudo().get_param('database.uuid')
        kwargs = {'merchant_id': self.merchant_id and str(self.merchant_id) or False,
                  'app_name': 'amazon_ept_spapi',
                  'account_token': account.account_token,
                  'emipro_api': 'load_marketplace_sp_api',
                  'dbuuid': dbuuid,
                  'amazon_selling': self.seller_id.amazon_selling,
                  'amazon_marketplace_code': self.country_id.amazon_marketplace_code or self.country_id.code,
                  'odoo_version': 'v16'
                  }
        response = iap_tools.iap_jsonrpc(VERIFY_ENDPOINT, params=kwargs, timeout=1000)
        if response.get('result', False):
            flag = response.get('result', {})
        else:
            raise UserError(_(response.get('error', '')))
        if flag:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'target': 'new',
                    'title': _('Success'),
                    'type': 'success',
                    'message': 'Service working properly',
                    'sticky': False
                }
            }
        return True

    def toggle_active(self):
        """ Inverse the value of the field ``active`` on the records in ``self``. """
        for record in self:
            record.active = not record.active

    def export_stock_levels(self):
        """
        This Method relocates prepare envelop using operation.
        :return: This Method return Boolean(True/False).
        """
        self.env['amazon.product.ept'].export_amazon_stock_levels_operation(self)
        self.write({'inventory_last_sync_on': datetime.now()})
        return True

    @api.constrains('is_allow_to_create_removal_order')
    def check_removal_config(self):
        """
        This Method check removal order configuration if more then one try to configure removal
        order configuration raise UserError.
        """
        if len(self.env[AMZ_INSTANCE_EPT].search(
                [('is_allow_to_create_removal_order', '=', True),
                 ('seller_id', '=', self.seller_id.id)]).ids) > 1:
            raise UserError(_("Default Removal configuration allow only marketplace per seller"))

    def configure_amazon_removal_order_routes(self):
        """
        The Method will create removal order routes and pull/procurement rules for Amazon Removal
        Order If is_allow_to_create_removal_order and removal_order_config_ids found in current
        marketplace this cases update unsellable route.
        :return: True
        :rtype: boolean
        """
        self.ensure_one()
        stock_picking_type_obj = self.env['stock.picking.type']
        stock_location_obj = self.env[STOCK_LOCATION]
        stock_picking_type = stock_picking_type_obj.search([('warehouse_id', '=', self.fba_warehouse_id.id),
                                                              ('code', '=', 'outgoing')], limit=1)
        if self.is_allow_to_create_removal_order and self.removal_order_config_ids:
            fba_warehouse_id = self.fba_warehouse_id or False
            self.update_unsellable_route(fba_warehouse_id, self.removal_order_config_ids)

        if self.is_allow_to_create_removal_order and not self.removal_order_config_ids and \
                (self.removal_warehouse_id and self.fba_warehouse_id):
            unsellable_route_id = self.create_unsellable_route(self.removal_warehouse_id,
                                                               self.fba_warehouse_id) or False
            sellable_route_id = self.create_sellable_route(self.removal_warehouse_id,
                                                           self.fba_warehouse_id) or False
            if unsellable_route_id and sellable_route_id:
                routes_value = self.prepare_unsellable_route_value('Return', unsellable_route_id.id,
                                                                   sellable_route_id.id)
                self.removal_order_config_ids = [(0, 0, routes_value)]
            disp_location_id = stock_location_obj.search([('usage', '=', 'inventory'),
                                                          ('scrap_location', '=', True)], limit=1)
            if stock_picking_type and disp_location_id:
                disposal_vals = self.prepare_disposal_value('Disposal', disp_location_id.id, stock_picking_type.id)
                self.removal_order_config_ids = [(0, 0, disposal_vals)]
        if not self.removal_order_config_ids.filtered(lambda l: l.removal_disposition == 'Liquidations'):
            cust_location_id = stock_location_obj.search([('usage', '=', 'customer')], limit=1)
            liquidation_vals = self.prepare_disposal_value('Liquidations', cust_location_id.id,
                                                           stock_picking_type.id)
            self.removal_order_config_ids = [(0, 0, liquidation_vals)]
        return True

    @staticmethod
    def prepare_unsellable_route_value(removal_disposition_return, unsellable_routes_id, sellable_routes_id):
        """
        This Method prepare dictionary unsellable routes 'return' value.
        :param removal_disposition_return: This arguments relocates removal disposition 'return'.
        :param unsellable_routes_id: This arguments relcocates unsellable route id.
        :param sellable_routes_id: This argumentes sellable routes id.
        :return: This Method return unsellable route value dictionary.
        """
        unsellable_routes_vals = {
            'removal_disposition': removal_disposition_return,
            'unsellable_route_id': unsellable_routes_id,
            'sellable_route_id': sellable_routes_id,
        }
        return unsellable_routes_vals

    @staticmethod
    def prepare_disposal_value(removal_disposition, disposal_location_id, disposal_picking_type_id):
        """
        This Method prepare dictionary disposal value.
        :param removal_disposition: This arguments relocates removal disposition 'disposal'.
        :param disposal_location_id: This arguments relocates disposal location id.
        :param disposal_picking_type_id: This argument disposal picking type id.
        :return: This Method return disposal value dictionary.
        """
        disposal_vals = {
            'removal_disposition': removal_disposition,
            'location_id': disposal_location_id,
            'picking_type_id': disposal_picking_type_id,
        }
        return disposal_vals

    def create_unsellable_route(self, warehouse_id, fba_warehouse_id):
        """
        This Method relocates to create unsellable routes and pull/procurement rules for an amazon
        removal order.
        :param warehouse_id: This Arguments relocates removal warehouse id of amazon.
        :param fba_warehouse_id: This Argument relocates FBA warehouse id of amazon.
        :return: This Method return boolean(True/False).
        If fba_unsellable_location_id and unsellable_location_id found in this cases return
        unsellable_route_id object or False return.
        """
        stock_location_route_obj = self.env['stock.route']
        stock_location_obj = self.env[STOCK_LOCATION]
        stock_picking_type_obj = self.env['stock.picking.type']
        unsellable_route = False
        fba_unsellable_location_id = fba_warehouse_id.unsellable_location_id if fba_warehouse_id else False
        unsellable_location_id = warehouse_id.unsellable_location_id if warehouse_id else False
        if not unsellable_location_id:
            unsellable_location_id = self.env[STOCK_LOCATION].search([('scrap_location', '=', True)], limit=1)
        if fba_unsellable_location_id and unsellable_location_id:
            location_id = stock_location_obj.search(['|', ('company_id', '=', False),
                                                     ('company_id', '=', fba_warehouse_id.company_id.id),
                                                     ('usage', '=', 'transit')], limit=1)
            stock_picking_type_id = fba_warehouse_id.out_type_id
            pull1_vals = {
                'name': '%s Unsellable to Transit' % (fba_warehouse_id.code),
                'action': 'pull',
                'location_src_id': fba_unsellable_location_id.id,
                'procure_method': 'make_to_stock',
                'location_dest_id': location_id and location_id.id or False,
                'picking_type_id': stock_picking_type_id and stock_picking_type_id.id or False,
                'warehouse_id': warehouse_id.id
            }
            pull2_stock_picking_type_id = stock_picking_type_obj.search(
                [('code', '=', 'incoming'), ('warehouse_id', '=', warehouse_id.id)], limit=1)
            pull2_vals = {
                'name': '%s to %s Transit' % (fba_warehouse_id.code, warehouse_id.code),
                'action': 'pull',
                'location_src_id': location_id and location_id.id or False,
                'procure_method': 'make_to_order',
                'location_dest_id': unsellable_location_id and unsellable_location_id.id or False,
                'picking_type_id': pull2_stock_picking_type_id and pull2_stock_picking_type_id.id or False,
                'warehouse_id': warehouse_id.id,
            }
            vals = {
                'name': '%s Unsellable to %s Unsellable' % (fba_warehouse_id.code, warehouse_id.code),
                'is_removal_order': True,
                'supplied_wh_id': warehouse_id.id,
                'supplier_wh_id': fba_warehouse_id.id,
                'rule_ids': [(0, 0, pull1_vals), (0, 0, pull2_vals)]
            }
            unsellable_route = stock_location_route_obj.create(vals)
        return unsellable_route

    def create_sellable_route(self, warehouse_id, fba_warehouse_id):
        """
        This Method relocates to create sellable routes and pull/procurement rules for an
        amazon removal order.
        :param warehouse_id: This Arguments relocates removal warehouse id of amazon.
        :param fba_warehouse_id: This Argument relocates FBA warehouse id of amazon.
        :return: This Method return boolean(True/False).
        If sellable_location_id and fba_sellable_location_id found in this cases return
        sellable_route_id object or False return.
        """
        stock_location_route_obj = self.env['stock.route']
        stock_location_obj = self.env[STOCK_LOCATION]
        sellable_route = False
        fba_sellable_location_id = fba_warehouse_id.lot_stock_id if fba_warehouse_id else False
        sellable_location_id = warehouse_id.lot_stock_id if warehouse_id else False
        if sellable_location_id and fba_sellable_location_id:
            location_id = stock_location_obj.search(['|', ('company_id', '=', False),
                                                     ('company_id', '=', fba_warehouse_id.company_id.id),
                                                     ('usage', '=', 'transit')], limit=1)
            s2t_vals = self._prepare_sellable_to_transit_vals_ept(warehouse_id, fba_warehouse_id,
                                                                  location_id)
            t2t_vals = self._prepare_transit_to_transit_vals_ept(warehouse_id, location_id)
            s2s_vals = self._prepare_sellable_to_sellable_vals_ept(warehouse_id, fba_warehouse_id,
                                                                   s2t_vals, t2t_vals)
            sellable_route = stock_location_route_obj.create(s2s_vals)
        return sellable_route

    def update_unsellable_route(self, fba_warehouse_id, removal_order_config_ids):
        """
        This Method relocates update unsellable routes and pull/procurement rules for amazon
        removal order If unsellable_route_id found in this case write pull_id.
        :param fba_warehouse_id: stock.warehouse()
        :param removal_order_config_ids: removal.order.config.ept()
        :return: True
        """
        stock_location_obj = self.env[STOCK_LOCATION]
        unsellable_route_id = False
        for removal_order_config_id in removal_order_config_ids:
            if removal_order_config_id.removal_disposition == "Return":
                unsellable_route_id = removal_order_config_id.unsellable_route_id or False
        if unsellable_route_id:
            location_id = stock_location_obj.search(['|', ('company_id', '=', False),
                                                     ('company_id', '=', fba_warehouse_id.company_id.id),
                                                     ('usage', '=', 'transit')], limit=1)
            for pull_id in unsellable_route_id.rule_ids:
                if pull_id.procure_method == "make_to_stock":
                    cha_pull1_vals = self._prepare_unsellable_to_transit_vals(fba_warehouse_id, location_id)
                    pull_id.write(cha_pull1_vals)
        return True

    @staticmethod
    def _prepare_unsellable_to_transit_vals(fba_warehouse_id, location_id):
        """
        Prepare values for Unsellable to Transit Route.
        :param fba_warehouse_id: stock.warehouse()
        :param location_id: stock.location()
        :return: dict {}
        """
        return {
            'name': '%s Unsellable to Transit' % fba_warehouse_id.code,
            'location_src_id': fba_warehouse_id.unsellable_location_id.id if fba_warehouse_id.unsellable_location_id else False,
            'location_dest_id': location_id.id if location_id else False,
            'picking_type_id': fba_warehouse_id.out_type_id.id if fba_warehouse_id.out_type_id else False
        }

    @staticmethod
    def _prepare_sellable_to_transit_vals_ept(warehouse_id, fba_warehouse_id, location_id):
        """
        Prepare Values for Sellable to Transit route
        :param warehouse_id:
        :param fba_warehouse_id:
        :param location_id:
        :return:
        """
        return {
            'name': '%s Sellable to Transit' % fba_warehouse_id.code,
            'action': 'pull',
            'location_src_id': fba_warehouse_id.lot_stock_id.id if fba_warehouse_id.lot_stock_id else False,
            'procure_method': 'make_to_stock',
            'location_dest_id': location_id and location_id.id or False,
            'picking_type_id': fba_warehouse_id.out_type_id.id if fba_warehouse_id.out_type_id else False,
            'warehouse_id': warehouse_id.id
        }

    @staticmethod
    def _prepare_transit_to_transit_vals_ept(warehouse_id, location_id):
        return {
            'name': 'Transit to %s Transit' % warehouse_id.code,
            'action': 'pull',
            'location_src_id': location_id.id if location_id else False,
            'procure_method': 'make_to_order',
            'location_dest_id': warehouse_id.lot_stock_id.id if warehouse_id.lot_stock_id else False,
            'picking_type_id': warehouse_id.in_type_id.id if warehouse_id.in_type_id else False,
            'warehouse_id': warehouse_id.id
        }

    @staticmethod
    def _prepare_sellable_to_sellable_vals_ept(warehouse_id, fba_warehouse_id, s2t_vals, t2t_vals):
        return {
            'name': '%s Sellable to %s Sellable' % (fba_warehouse_id.name, warehouse_id.name),
            'rule_ids': [(0, 0, s2t_vals), (0, 0, t2t_vals)],
            'supplied_wh_id': warehouse_id.id,
            'supplier_wh_id': fba_warehouse_id.id
        }

    @api.model
    def perform_operation(self, record_id):
        """
        Use: To prepare amazon operation action
        :return: Amazon operation action details
        """
        instance_id = self.env[AMZ_INSTANCE_EPT].browse(record_id)
        seller_id = instance_id.seller_id
        view = self.env.ref('amazon_ept.action_wizard_amazon_import_export_operations').sudo().read()[0]
        action = self.prepare_action(view, [])
        action.update({'context': {'default_seller_id': seller_id.id,
                                   'default_selling_on': 'fba_fbm' if seller_id.amazon_selling == 'Both' else seller_id.amazon_selling}})
        return action
