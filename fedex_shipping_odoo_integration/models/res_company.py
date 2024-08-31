import requests
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ResCompany(models.Model):
    _inherit = "res.company"
    use_fedex_shipping_provider = fields.Boolean(copy=False, string="Are You Use FedEx Shipping Provider.?",
                                                 help="If use fedEx shipping provider than value set TRUE.",
                                                 default=False)
    fedex_api_url = fields.Char(string="FedEx API URL", copy=False, default="https://apis-sandbox.fedex.com")
    fedex_client_id = fields.Char(string="FedEx Client ID", copy=False)
    fedex_client_secret = fields.Char(string="FedEx Client Secret", copy=False)
    fedex_account_number = fields.Char(copy=False, string='Account Number',
                                       help="The account number sent to you by Fedex after registering for Web Services.")
    fedex_access_token = fields.Char(string="FedEx Access Token", copy=False)

    def auto_generate_fedex_access_token(self):
        for company_id in self.search([('use_fedex_shipping_provider', '!=', False)]):
            company_id.generate_fedex_access_token()

    def generate_fedex_access_token(self):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        api_url = "%s/oauth/token" % (self.fedex_api_url)
        if not self.fedex_client_id or not self.fedex_client_secret:
            raise ValidationError("Please enter correct credentials")
        data = {
            'client_id': self.fedex_client_id,
            'client_secret': self.fedex_client_secret,
            'grant_type': 'client_credentials',
        }
        try:
            response_data = requests.request("POST", api_url, headers=headers, data=data)
            if response_data.status_code in [200, 201]:
                response_data = response_data.json()
                if response_data.get('access_token'):
                    self.fedex_access_token = response_data.get('access_token')
                    return {
                        'effect': {
                            'fadeout': 'slow',
                            'message': "Yeah! Token has been retrieved.",
                            'img_url': '/web/static/img/smile.svg',
                            'type': 'rainbow_man',
                        }
                    }
                else:
                    raise ValidationError(response_data)
        except Exception as e:
            raise ValidationError(e)
