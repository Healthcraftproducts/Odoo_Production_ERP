from odoo import api, Command, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare, format_date
from odoo.tools.translate import _


class HolidaysRequest(models.Model):
    _inherit = "hr.leave"

    @api.constrains('state', 'number_of_days', 'holiday_status_id')
    def _check_holidays(self):
        for holiday in self:
            mapped_days = self.holiday_status_id.get_employees_days((holiday.employee_id | holiday.sudo().employee_ids).ids,
                                                                    holiday.date_from.date())
            if holiday.holiday_type != 'employee' \
                    or not holiday.employee_id and not holiday.sudo().employee_ids \
                    or holiday.holiday_status_id.requires_allocation == 'no':
                continue
            if holiday.employee_id:
                leave_days = mapped_days[holiday.employee_id.id][holiday.holiday_status_id.id]
                if float_compare(leave_days['remaining_leaves'], 0, precision_digits=2) == -1 \
                        or float_compare(leave_days['virtual_remaining_leaves'], 0, precision_digits=2) == -1:
                    pass
                    # raise ValidationError(_('The number of remaining time off is not sufficient for this time off type.\n'
                    #                         'Please also check the time off waiting for validation.'))
            else:
                unallocated_employees = []
                for employee in holiday.sudo().employee_ids:
                    leave_days = mapped_days[employee.id][holiday.holiday_status_id.id]
                    if float_compare(leave_days['remaining_leaves'], holiday.number_of_days, precision_digits=2) == -1 \
                            or float_compare(leave_days['virtual_remaining_leaves'], holiday.number_of_days,
                                             precision_digits=2) == -1:
                        unallocated_employees.append(employee.name)
                if unallocated_employees:
                    # raise ValidationError(_('The number of remaining time off is not sufficient for this time off type.\n'
                    #                         'Please also check the time off waiting for validation.')
                    #                       + _('\nThe employees that lack allocation days are:\n%s',
                    #                           (', '.join(unallocated_employees))))
                    pass
