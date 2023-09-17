/** @odoo-module **/

import MainComponent from '@stock_barcode/components/main';
import { patch } from 'web.utils';

patch(MainComponent.prototype, 'hcp_barcode_ext', {
    _backToPage3: function (ev) {
        console.log("-----------------------")
        ev.stopPropagation();
        window.history.back();
    },
});