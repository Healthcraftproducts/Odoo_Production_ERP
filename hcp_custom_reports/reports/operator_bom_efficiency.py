from odoo import api, fields, models, _


class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    finished_product_id = fields.Char(related='workorder_id.production_id.product_id.default_code', string='Item Code',
                                      store=True)
    mrp_production_id = fields.Many2one(related='workorder_id.production_id', string='MO #',
                                        store=True)
    work_order_name = fields.Char(related='workorder_id.name', string='Operations', store=True)
    qty_produced = fields.Float(related='workorder_id.qty_produced', string='QTY Produced', store=True)

    department = fields.Selection(related='workorder_id.workcenter_department', string='Department', store=True)

    workcenter_code = fields.Char(related='workcenter_id.code', string='Workcenter', store=True)

    mrp_setup_time = fields.Float(related='workorder_id.operation_id.setuptime_per_unit', string='Setup Time(in min)',
                                  store=True)
    mrp_cycle_time = fields.Float(related='workorder_id.operation_id.total_time', string='Cycle Time(in min)',
                                  store=True)
    total_cycle_time = fields.Float(string='Total Cycle Time(in min)', compute='_total_cycle_time', store=True)

    duration_expected = fields.Float(related='workorder_id.duration_expected', string='Expected Time(in min)',
                                     store=True)
    real_duration = fields.Float(related='workorder_id.duration', string='Real Time(in min)', store=True)
    duration_efficiency = fields.Float(string='BOM Efficiency', compute='duration_expected_efficiency', store=True)

    efficiency = fields.Float(string='Efficiency', compute='_total_efficiency_time', store=True)

    @api.depends('duration_expected', 'real_duration')
    def duration_expected_efficiency(self):
        for rec in self:
            if rec.duration_expected and rec.real_duration:
                rec.duration_efficiency = (rec.duration_expected / rec.real_duration) * 100
            else:
                rec.duration_efficiency = 0.00

    @api.depends('qty_produced', 'mrp_cycle_time')
    def _total_cycle_time(self):
        for rec in self:
            # if rec.qty_produced and rec.cycle_time:
            rec.total_cycle_time = rec.qty_produced * rec.mrp_cycle_time
        # else:
        #     rec.total_cycle_time = 0.00

    @api.depends('total_cycle_time', 'real_duration')
    def _total_efficiency_time(self):
        for rec in self:
            if (rec.total_cycle_time) != 0.00 and (rec.real_duration) != 0.00:
                rec.efficiency = (rec.total_cycle_time)/(rec.real_duration) * 100
            else:
                rec.efficiency = 0.00
