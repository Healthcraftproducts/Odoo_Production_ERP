from odoo import fields, models, api, _
from odoo.addons.iap.tools import iap_tools

class SellerIapDatabases(models.TransientModel):
    """
    Wizard to view and update the databases to active and inactive
    """
    _name = "amazon.seller.iap.database"
    _description = 'Iap Database'

    iap_database_line_ids = fields.One2many(comodel_name='amazon.seller.iap.database.line',
                                            inverse_name='iap_database_id')
    current_database_state = dict()
    updated_database_state = dict()
    seller_data = dict()
    currently_active = []

    @api.model
    def default_get(self, fields):
        """
        Sets the data to iap database lines
        :param fields:
        :return:
        """
        res = {}
        if self._context.get('databases', False) and self._context.get('staging_limit'):
            databases = []
            for database in self._context.get('databases'):
                database.update({'is_db_active': True if database.get('state') in ['new', 'run'] else False})
                databases.append((0, 0, database))
                self.current_database_state.update({database.get('db_uid'): {'is_db_active': database.get(
                    'is_db_active'), 'state': database.get('state')}})
                if database.get('state') == 'run' and database.get('account_type') == 'sandbox':
                    self.currently_active.append(database.get('db_uid'))
            res.update({'iap_database_line_ids': databases})
            self.seller_data.update({'staging_limit': self._context.get('staging_limit'),
                                'seller': self._context.get('seller', ''),
                                'account_token': self._context.get('account_token', ''),
                                'dbuuid': self._context.get('dbuuid', '')})

        return res

    def update_database_status(self):
        """
        update the status of database in the iap.
        :return: notification
        """
        update_log = dict()
        update_data = dict()
        updated_by = f"Updated By : {self.create_uid.name}, with User ID : {self.create_uid.id}"
        for db_uid, data in self.updated_database_state.items():
            if data.get('is_db_active') != self.current_database_state.get(db_uid).get('is_db_active'):
                update_log.update({db_uid: [self.current_database_state.get(db_uid).get('state'),
                                            data.get('account_type')]})
                update_data.update({db_uid: {'db_uid': db_uid,
                                             'name': data.get('name'),
                                             'account_type': data.get('account_type'),
                                             'is_db_active': data.get('is_db_active')
                                             }})
        kwargs = {'update_data': update_data, 'update_log': update_log,
                  'updated_by': updated_by, 'database': 'update', 'seller': self.seller_data.get('seller')}
        kwargs.update(self.seller_data)
        response = {}
        if update_log:
            response = iap_tools.iap_jsonrpc('https://iap.odoo.emiprotechnologies.com/iap_databases',
                                             params=kwargs, timeout=1000)
        merchant_id = self.seller_data.get('seller')
        self.current_database_state.clear()
        self.updated_database_state.clear()
        self.seller_data.clear()
        self.currently_active.clear()
        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'target': 'new',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
        if not response:
            action.get('params').update({'title': _('No Change'),
                                         'type': 'warning',
                                         'message': 'No Changes Made to the databases',
                                         'sticky': False})
            return action
        if response.get('error'):
            action.get('params').update({'title': _('Error'),
                                         'type': 'danger',
                                         'message': response.get('error'),
                                         'sticky': True})
            return action
        else:
            message = ''
            seller = self.env['amazon.seller.ept'].search([('merchant_id', '=', merchant_id)])
            if update_log:
                current_state = {'new': 'New', 'run': 'Running', 'block': 'Blocked', 'expire': 'Expired'}
                message = message + f"{updated_by}<br/><table><tr><th>DB-UID</th><th>&ensp;STATUS</th></tr>"
                for dbuid, update in update_log.items():
                    message = message + f"<tr><td>   {dbuid}</td><td>&ensp;{current_state.get(update[0])} &rarr; " \
                                        f"{update[1]}</td></tr>"
                message = message + "</table>"
                seller.sudo().message_post(body=message)
            action.get('params').update({'title': _('Success'),
                                         'type': 'success',
                                         'message': 'Databases Updated Successfully',
                                         'sticky': False})
        return action

    @api.onchange('iap_database_line_ids')
    def onchange_is_active_toggle(self):
        """
        validate the staging limit.
        :return:
        """
        if self.seller_data.get('staging_limit'):
            active_database = self.iap_database_line_ids.filtered(lambda db: db.is_db_active and db.account_type ==
                                                                             'sandbox')
            toggle_count = len(active_database)
            if toggle_count > self.seller_data.get('staging_limit'):
                active_db = active_database.filtered(lambda db:db.db_uid in self.currently_active)
                if active_db:
                    active_db[0].is_db_active = False
        self.currently_active.clear()
        for database in self.iap_database_line_ids:
            self.updated_database_state.update({database.db_uid: {
                'name': database.name,
                'account_type': 'Running' if database.is_db_active else 'Expired',
                'is_db_active': database.is_db_active,
            }})
            if database.is_db_active and database.account_type == 'sandbox':
                self.currently_active.append(database.db_uid)
