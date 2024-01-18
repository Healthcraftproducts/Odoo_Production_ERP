# -*- coding: utf-8 -*-pack
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Inherited class to set the FBM and FBA groups in user and based on amazon selling updated the
groups in users.

"""
from odoo import models, api
from odoo import SUPERUSER_ID

AMAZON_USER_GROUP = 'amazon_ept.group_amazon_user_ept'
AMAZON_MANAGER_GROUP = 'amazon_ept.group_amazon_manager_ept'


class ResUsers(models.Model):
    """
    Inherited class to set the FBA and FBM groups in user based on amazon selling
    """
    _inherit = 'res.users'

    def set_user_fba_fbm_group(self, company_ids):
        """"
        Will set the FBA and FBM groups in user based on amazon selling
        """
        self = self.with_user(SUPERUSER_ID)
        amazon_seller_obj = self.env['amazon.seller.ept']
        amazon_fba_group = self.env.ref('amazon_ept.group_amazon_fba_ept')
        amazon_fbm_group = self.env.ref('amazon_ept.group_amazon_fbm_ept')
        amazon_fba_fbm_group = self.env.ref('amazon_ept.group_amazon_fba_and_fbm_ept')
        amazon_user_group = self.env.ref(AMAZON_USER_GROUP)
        amazon_manager_group = self.env.ref(AMAZON_MANAGER_GROUP)
        user_list = list(set(amazon_user_group.users.ids + amazon_manager_group.users.ids))
        amazon_selling_both = amazon_seller_obj.search([('amazon_selling', '=', 'Both')])
        amazon_selling_fba = amazon_seller_obj.search([('amazon_selling', '=', 'FBA')])
        amazon_selling_fbm = amazon_seller_obj.search([('amazon_selling', '=', 'FBM')])
        amazon_selling = 'Both'
        if amazon_selling_fba:
            other_seller_both = amazon_selling_both
            seller_company = other_seller_both.filtered(lambda x: x.company_id.id in company_ids)
            if other_seller_both and seller_company:
                amazon_selling = 'Both'
            else:
                other_seller_fbm = amazon_selling_fbm
                seller_company = other_seller_fbm.filtered(lambda x: x.company_id.id in company_ids)
                if other_seller_fbm and seller_company:
                    amazon_selling = 'Both'
                else:
                    amazon_selling = 'FBA'
        elif amazon_selling_fbm:
            other_seller_both = amazon_selling_both
            seller_company = other_seller_both.filtered(lambda x: x.company_id.id in company_ids)
            if other_seller_both and seller_company:
                amazon_selling = 'Both'
            else:
                other_seller_fba = amazon_selling_fba
                seller_company = other_seller_fba.filtered(lambda x: x.company_id.id in company_ids)
                if other_seller_fba and seller_company:
                    amazon_selling = 'Both'
                else:
                    amazon_selling = 'FBM'

        if amazon_selling == 'FBM':
            amazon_fbm_group.write({'users': [(6, 0, user_list)]})
            amazon_fba_group.write({'users': [(6, 0, [])]})
            amazon_fba_fbm_group.write({'users': [(6, 0, [])]})
        elif amazon_selling == 'FBA':
            amazon_fba_group.write({'users': [(6, 0, user_list)]})
            amazon_fbm_group.write({'users': [(6, 0, [])]})
            amazon_fba_fbm_group.write({'users': [(6, 0, [])]})
        elif amazon_selling == 'Both':
            amazon_fba_fbm_group.write({'users': [(6, 0, user_list)]})
            amazon_fba_group.write({'users': [(6, 0, user_list)]})
            amazon_fbm_group.write({'users': [(6, 0, user_list)]})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        Inherited this method to set the created user into Amazon groups.
        """
        amazon_seller_obj = self.env['amazon.seller.ept']
        users = super(ResUsers, self).create(vals_list)
        for user in users:
            if user.has_group(AMAZON_USER_GROUP) or user.has_group(AMAZON_MANAGER_GROUP):
                company_ids = user.company_ids.ids
                self.set_user_fba_fbm_group(company_ids)
                if user.has_group('analytic.group_analytic_accounting'):
                    amazon_seller_obj.amz_create_analytic_account()
        return users

    def write(self, vals):
        """
        Inherited this method to set the updated user into the Amazon groups.
        """
        amazon_seller_obj = self.env['amazon.seller.ept']
        res = super(ResUsers, self).write(vals)
        for user in self:
            if user.has_group(AMAZON_USER_GROUP) or user.has_group(AMAZON_MANAGER_GROUP):
                company_ids = user.company_ids.ids
                user.set_user_fba_fbm_group(company_ids)
                if user.has_group('analytic.group_analytic_accounting'):
                    amazon_seller_obj.amz_create_analytic_account()
        return res
