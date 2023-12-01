/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import MenuPopup from '@mrp_workorder/components/menuPopup';
import Tablet from '@mrp_workorder/components/tablet';
import { Component, xml, onWillStart } from "@odoo/owl";
import { patch } from 'web.utils';
console.log("MENU POPUPPPPPPPPPPPPPPPPPPPPPP");

//export class MyCustomMenuPopup extends MenuPopup {
//
//    setup() {
//        super.setup();
//        this.user = useService("user");
//        onWillStart(async () => {
//            this.isSystemUsers = await this.user.hasGroup('mrp.group_mrp_manager');
//        });
//    }
//}

//export class MyTablet extends Tablet {
patch(Tablet.prototype, 'hcp_operator_customization', {
    setup() {
        // You can call the setup method of the parent class using super.setup()
       this._super();
        this.user = useService("user");
        onWillStart(async () => {
            await this._onWillStart();
            this.isSystemUsers = await this.user.hasGroup('mrp.group_mrp_manager');
        });
    },

     openMenuPopup() {
        this.showPopup({
            title: 'Menu',
            workcenterId: this.data['mrp.workorder'].workcenter_id,
            selectedStepId: this.state.selectedStepId,
            workorderId: this.workorderId,
            has_bom: this.data['has_bom'],
            isSystemUser: this.isSystemUsers,
        }, 'menu');
    }
});
