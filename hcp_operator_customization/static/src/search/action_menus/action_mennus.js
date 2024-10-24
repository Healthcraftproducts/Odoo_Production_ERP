/** @odoo-module **/
import {patch} from "@web/core/utils/patch";
import {ActionMenus} from "@web/search/action_menus/action_menus";
import {useService} from "@web/core/utils/hooks";

patch(ActionMenus.prototype, "hcp_operator_customization.ActionMenus", {
  setup() {
    this._super(...arguments)
    this.userService = useService('user')
  },
  async setActionItems(props) {
    let model_props = this.props.resModel
    let result = await this._super(...arguments)
    let hide_delete = await this.userService.hasGroup('hcp_operator_customization.group_hide_delete')
    if (hide_delete && model_props == 'stock.warehouse.orderpoint') {
      result = result.filter(item => item.key !== 'delete');
    }
    return result
  }
});