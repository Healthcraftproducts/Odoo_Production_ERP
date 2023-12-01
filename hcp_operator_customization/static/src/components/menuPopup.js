/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
const { Component } = owl;

class MyCustomMenuPopup extends Component {

    setup() {
        // You can call the setup method of the parent class using super.setup()
        super.setup();
            onWillStart(async () => {
            this.isSystemUsers = await this.user.hasGroup('hcp_operator_customization.group_mrp_new_operator');
        });

    }

}

// Inherit from the MenuPopup class using the extend method
MyCustomMenuPopup.template = 'hcp_operator_customization.MyCustomMenuPopup';
MyCustomMenuPopup.components = { MenuPopup: 'mrp_workorder.MenuPopup' };

export default MyCustomMenuPopup;
