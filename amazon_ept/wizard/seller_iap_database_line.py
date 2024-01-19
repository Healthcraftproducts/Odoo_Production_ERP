from odoo import fields, models, api

class SellerIapDatabasesLine(models.TransientModel):
    """
    Used to contain database lines
    """
    _name = "amazon.seller.iap.database.line"
    _description = 'Iap Database'

    db_uid = fields.Char('Database UId', index=True)
    name = fields.Char("App Token", index=True)
    account_type = fields.Selection([('sandbox', 'SandBox'), ('production', 'Production')])
    is_db_active = fields.Boolean(string="Is Active")
    iap_database_id = fields.Many2one(string='Iap_database', comodel_name='amazon.seller.iap.database')
    state = fields.Selection([('new', 'New'),
                              ('run', 'Running'),
                              ('block', 'Blocked'),
                              ('expire', 'Expired')])
