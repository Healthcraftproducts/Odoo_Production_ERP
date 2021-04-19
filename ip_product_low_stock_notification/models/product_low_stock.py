# -*- encoding: utf-8 -*-
from odoo import api, fields, models
from ast import literal_eval


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    minimum_qty = fields.Float(string="Minimum Quantity")
    maximum_qty = fields.Float(string="Maximum Quantity")

class IrCron(models.Model):
    _inherit = 'ir.cron'

    @api.model
    def product_low_stock_notification_send_email(self):
        get_param = self.env['ir.config_parameter'].sudo().get_param
        user_ids = literal_eval(get_param('ip_product_low_stock_notification.notification_user_ids'))
        if user_ids:
            ctx = {}
            email_list = [user.email for user in self.env['res.users'].search([('id', 'in', user_ids)])]
            if email_list:
                ctx['email_to'] = ','.join([email for email in email_list if email])
                ctx['email_from'] = self.env.user.email
                ctx['send_email'] = True
                template = self.env.ref('ip_product_low_stock_notification.email_template_low_stock_notification')
                template.with_context(ctx).send_mail(self.env.user.id, force_send=True, raise_exception=False)
                return True
