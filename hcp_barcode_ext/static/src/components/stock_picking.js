/** @odoo-module **/

import MainComponent from '@stock_barcode/components/main';
import { useService } from "@web/core/utils/hooks";
import { patch } from 'web.utils';
console.log("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
const { Component, useState, onWillStart, onWillUpdateProps } = owl;
patch(MainComponent.prototype, 'hcp_barcode_ext', {
 setup() {
        // Call the setup method of the parent class
        this._super();
        this.user = useService("user");
        onWillStart(async () => {
            // Check if the user belongs to the specific group
            this.isCustomGroupUser = await this.user.hasGroup("hcp_contact_ext.custom_barcode_admin");
            console.log(this.isCustomGroupUser,"userrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr")
        });


    },

    _backToPage3: function (ev) {
        console.log("-----------------------")
        ev.stopPropagation();
        window.history.back();
    },

});
