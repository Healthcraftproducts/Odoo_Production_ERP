# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from _datetime import datetime
from collections import defaultdict
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import date_utils, float_compare, float_round, float_is_zero
import logging
import os
from odoo.modules.module import get_module_resource


class QCImageUploadWizard(models.TransientModel):
    _name = "qc.image.upload"
    _description = "Qc Image Upload"

    upload_image = fields.Binary('Upload Image')

    def upload_qc_image(self):
        work_order_ids = self.env['mrp.workorder'].sudo().search(
            [('id', '=', self.env.context.get('default_workorder_id'))])
        logging.info('%s--------------work_order_ids', work_order_ids)
        for work_order in work_order_ids.filtered(lambda self: self.state not in ['done', 'cancel']):
            work_order.write({
                'qc_image_ids': [(0, 0, {'image': self.upload_image})]
            })
        return True


class MrpWorkOrderQCImages(models.Model):
    _name = 'mrp.workorder.qc.images'
    _description = "Workorder Qc Images"

    image = fields.Binary(string='Image')
    workorder_id = fields.Many2one('mrp.workorder', string='Workorder ID')


class MrpWorkOrderInherit(models.Model):
    _inherit = 'mrp.workorder'
    qc_image_ids = fields.One2many('mrp.workorder.qc.images', 'workorder_id', string='QC Images')


class MrpProductionWorkcenterLine(models.Model):
    _inherit = 'mrp.workorder'

    def action_upload_qc_image(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qc.image.upload',
            'views': [[self.env.ref('hcp_mrp_module.qc_image_upload_wizard').id, 'form']],
            'name': _('QC Images Upload'),
            'target': 'new',
            'context': {
                'default_workcenter_id': self.workcenter_id,
                'default_workorder_id': self.id,
            }
        }

    def record_production(self):
        if not self:
            return True

        self.ensure_one()
        self._check_company()
        if any(x.quality_state == 'none' for x in self.check_ids if x.test_type != 'instructions'):
            raise UserError(_('You still need to do the quality checks!'))
        if float_compare(self.qty_producing, 0, precision_rounding=self.product_uom_id.rounding) <= 0:
            raise UserError(_('Please set the quantity you are currently producing. It should be different from zero.'))

        if self.production_id.product_id.tracking != 'none' and not self.finished_lot_id and self.move_raw_ids:
            raise UserError(_('You should provide a lot/serial number for the final product'))

        backorder = False
        # Trigger the backorder process if we produce less than expected
        if float_compare(self.qty_producing, self.qty_remaining, precision_rounding=self.product_uom_id.rounding) == -1 and self.is_first_started_wo:
            backorder = self.production_id._split_productions()[1:]
            for workorder in backorder.workorder_ids:
                if workorder.product_tracking == 'serial':
                    workorder.qty_producing = 1
                else:
                    workorder.qty_producing = workorder.qty_remaining
            self.production_id.product_qty = self.qty_producing
        else:
            if self.operation_id:
                backorder = (self.production_id.procurement_group_id.mrp_production_ids - self.production_id).filtered(
                    lambda p: p.workorder_ids.filtered(lambda wo: wo.operation_id == self.operation_id).state not in ('cancel', 'done')
                )[:1]
            else:
                index = list(self.production_id.workorder_ids).index(self)
                backorder = (self.production_id.procurement_group_id.mrp_production_ids - self.production_id).filtered(
                    lambda p: index < len(p.workorder_ids) and p.workorder_ids[index].state not in ('cancel', 'done')
                )[:1]

        self.button_start()

        if backorder:
            for wo in (self.production_id | backorder).workorder_ids:
                if wo.state in ('done', 'cancel'):
                    continue
                if not wo.current_quality_check_id or not wo.current_quality_check_id.move_line_id:
                    wo.current_quality_check_id.update(wo._defaults_from_move(wo.move_id))
                if wo.move_id:
                    wo.current_quality_check_id._update_component_quantity()
            if not self.env.context.get('no_start_next'):
                if self.operation_id:
                    return backorder.workorder_ids.filtered(lambda wo: wo.operation_id == self.operation_id).open_tablet_view()
                else:
                    index = list(self.production_id.workorder_ids).index(self)
                    return backorder.workorder_ids[index].open_tablet_view()
        return True



class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    production = fields.Char(string="Manufacturing Order", related='production_id.name')
    work_order = fields.Char(string="Work Order", related='workorder_id.name')


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    release_date = fields.Date(string='Release Date')
    priority = fields.Selection([('0', 'Low'), ('1', 'Medium'), ('2', 'High'), ('3', 'Very High')], 'Priority',
                                readonly=False, states={'done': [('readonly', True)]}, default='1')


    def get_attachment(self):
        import base64
        default_image_path = get_module_resource('hcp_mrp_module', 'static/src/pdf', 'QC_Template.pdf')
        file_content = open(default_image_path, 'rb').read()
        result = base64.b64encode(file_content)
        # get base url
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        attachment_obj = self.env['ir.attachment']
        attachment_avail = self.env['ir.attachment'].search([('name', '=', 'qc_report')])
        attachment_count = self.env['ir.attachment'].search_count([('name', '=', 'qc_report')])
        # print(attachment_avail)
        # create attachment
        if attachment_count == 0:
            attachment_id = attachment_obj.create(
                {'name': "qc_report", 'type': 'binary', 'datas': result})
            # prepare download url
            download_url = '/web/content/' + str(attachment_id.id) + '?download=true'
            # download
            return {
                "type": "ir.actions.act_url",
                "url": str(base_url) + str(download_url),
                "target": "new",
            }
        else:
            att = attachment_avail.id
            download_url = '/web/content/' + str(att) + '?download=true'
            # download
            return {
                "type": "ir.actions.act_url",
                "url": str(base_url) + str(download_url),
                "target": "new",
            }


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    cycle_time = fields.Float(string='Cycle Time Old')
    shiftid = fields.Selection(
        [('production', 'Production'), ('outside_pro', 'Outside Pro'), ('inventory', 'Inventory')], string='ShiftId')
    time_stop = fields.Float('Cycle Time', help="Time in minutes for the cleaning.")
    department = fields.Selection(
        [('assembly', 'Assembly'), ('machining', 'Machining'), ('welding', 'Welding'), ('fabrication', 'Fabrication'),
         ('paint', 'Paint')], string='Department')

    def name_get(self):
        res = []
        for category in self:
            names = []
            name = category.name
            code = category.code
            if code:
                name = '[%s] %s' % (code, name)
            res.append((category.id, name))
        return res

    #@api.model
    #def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
     #   args = args or []
      #  if name:
       #     # Be sure name_search is symmetric to name_get
        #    name = name.split(' / ')[-1]
         #   args = [('name', operator, name)] + args
        #partner_category_ids = self._search(args, limit=limit, access_rights_uid=name_get_uid)
        #return self.browse(partner_category_ids).name_get()


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    setup_time = fields.Float(string='Setup Time')
    custom_batch_size = fields.Integer(string="Batch Size")
    batch_size = fields.Integer(string="Partial Batch Size")
    done_by = fields.Char(string='Done By')
    cycle_time = fields.Float(string='Cycle Time Old')
    operator = fields.Char(string='Operator')
    setuptime_per_unit = fields.Float(string='Setuptime Per Unit(Mins)', compute='_compute_setuptime_per_unit')
    runtime_per_unit = fields.Float(string='Runtime Per Unit(Mins)')
    total_time = fields.Float(string='Total Time(Mins)', compute='_compute_total_time')

    @api.depends('setup_time', 'custom_batch_size')
    def _compute_setuptime_per_unit(self):
        for line in self:
            if line.setup_time and line.custom_batch_size:
                line.setuptime_per_unit = (line.setup_time / line.custom_batch_size)
            else:
                line.setuptime_per_unit = 0

    @api.depends('setup_time', 'custom_batch_size', 'runtime_per_unit')
    def _compute_total_time(self):
        setuptime_per_unit = 0
        runtime_per_unit = 0
        for line in self:
            if line.setup_time and line.custom_batch_size:
                setuptime_per_unit = (line.setup_time / line.custom_batch_size)
            if line.runtime_per_unit:
                runtime_per_unit = line.runtime_per_unit
            line.total_time = setuptime_per_unit + runtime_per_unit


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    attachments_id = fields.Many2many(comodel_name="ir.attachment", relation="m2m_ir_attachment_relation",
                                      column1="m2m_id", column2="attachment_id", string="Attachments")


# def get_attachment(self):
# 	# import pdb
# 	# pdb.set_trace()
# 	# import os
# 	import base64
# 	# output is where you have the content of your file, it can be
# 	# any type of content

# 	output = open(r"src/user/hcp_mrp_module/QC_Template.pdf", "rb").read()

# 	# path = r'hcp_mrp_module\QC_Template.pdf'
# 	# output = path.encode('ascii')
# 	# encode
# 	result = base64.b64encode(output)
# 	# get base url
# 	base_url = self.env['ir.config_parameter'].get_param('web.base.url')
# 	attachment_obj = self.env['ir.attachment']
# 	attachment_avail = self.env['ir.attachment'].search([('name','=','qc_report')])
# 	attachment_count = self.env['ir.attachment'].search_count([('name','=','qc_report')])
# 	# print(attachment_avail)
# 	# create attachment
# 	if attachment_count==0:
# 		attachment_id = attachment_obj.create(
# 		{'name': "qc_report", 'type': 'binary', 'datas': result})
# 		# prepare download url
# 		download_url = '/web/content/' + str(attachment_id.id) + '?download=true'
# 		# download
# 		return {
# 			"type": "ir.actions.act_url",
# 			"url": str(base_url) + str(download_url),
# 			"target": "new",
# 				}
# 	else:
# 		att= attachment_avail.id
# 		# attachment_id = attachment_obj.write(
# 		# {'id':att,'name': "qc_report", 'type': 'binary', 'datas': result})
# 		download_url = '/web/content/' + str(att) + '?download=true'
# 		# download
# 		return {
# 			"type": "ir.actions.act_url",
# 			"url": str(base_url) + str(download_url),
# 			"target": "new",
# 				}


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def update_main_bom(self):
        if self.product_uom_id:
            for line in self:
                line.product_uom_id = line.product_tmpl_id.uom_id

    def update_bom(self):
        if self.bom_line_ids:
            for line in self.bom_line_ids:
                line.product_uom_id = line.product_id.uom_id


# class ReportBomStructure(models.AbstractModel):
# 	_inherit = 'report.mrp.report_bom_structure'

# 	def _get_operation_line(self, routing, qty, level):
# 		operations = []
# 		total = 0.0
# 		for operation in routing.operation_ids:
# 			operation_cycle = float_round(qty / operation.workcenter_id.capacity, precision_rounding=1, rounding_method='UP')
# 			duration_expected = operation_cycle * operation.time_cycle + operation.workcenter_id.time_stop + operation.workcenter_id.time_start + operation.setup_time
# 			total = ((duration_expected / 60.0) * operation.workcenter_id.costs_hour)
# 			operations.append({
# 				'level': level or 0,
# 				'operation': operation,
# 				'name': operation.name + ' - ' + operation.workcenter_id.name,
# 				'duration_expected': duration_expected,
# 				'total': self.env.company.currency_id.round(total),
# 			})
# 		return operations


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    custom_ids = fields.One2many("mrp_workorder.additional.product", 'custom_id')
    hcp_priority = fields.Selection('Production Priority', readonly=True, related='production_id.priority',
                                    help='Technical: used in views only.')
    workcenter_department = fields.Selection('Department', readonly=True, related='workcenter_id.department')

    def name_get(self):
        return [(wo.id, "%s - %s - %s" % (wo.production_id.name, wo.product_id.display_name, wo.name)) for wo in self]

class MrpWorkorderAdditionalProduct(models.TransientModel):
    _inherit="mrp_workorder.additional.product"

    custom_id = fields.Many2one("mrp.workorder","custom ID")

    @api.onchange('product_id')
    def onchange_product_tmpl_id(self):
        bom_product_id = [rec.product_id.id for rec in self.workorder_id.production_id.move_raw_ids]
        return {'domain': {'product_id': [('id', 'in', bom_product_id)]}}
   
