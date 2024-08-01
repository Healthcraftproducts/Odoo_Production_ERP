/** @odoo-module **/

import BarcodeModel from '@stock_barcode/models/barcode_model';
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";

console.log("BARCODE MODULE LOADED");

/*  Modify the BarcodeModel prototype */
BarcodeModel.prototype.createNewLine = function (params) {
    console.log("test-log-9898", params, this)
    return new Promise((resolve, reject) => {
        this.dialogService.add(ConfirmationDialog, {
            body: "Test",
            title: "Wrong product",
            cancel: reject,
            close: reject,
        });
    })
}

export default class ConfirmBarcodeModel extends BarcodeModel {
    constructor(...args) {
        super(...args);
        console.log("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$");
        this.dialogService = useService('dialog');
        // Add custom properties or override initial values here
    }
    createNewLine(params) {
        console.log("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        const product = params.fieldsParams.product_id;
        
        if (this.askBeforeNewLinesCreation(product)) {
            const confirmationPromise = new Promise((resolve, reject) => {
                const body = product.code ?
                    sprintf(
                        _t("product [%s] %s is not reserved for this transfer"),
                        product.code, product.display_name
                    ) :
                    sprintf(
                        _t(" product %s is not reserved for this transfer"),
                        product.display_name
                    );

                this.isBarcodeGroupUser = this.user.hasGroup("hcp_contact_ext.custom_barcode_admin");
                if (isBarcodeGroupUser){
                    this.dialogService.add(ConfirmationDialog, {
                        body, title: _t("Wrong product"),
                        cancel: reject,
                        confirm: reject,
                        close: reject,
                    });
                }
                else{
                    this.dialogService.add(ConfirmationDialog, {
                        body, title: _t("Wrong Product"),
                        cancel: reject,
                        confirm: reject,
                        close: reject,
                    });
                }
            });
            return confirmationPromise;
        } else {
            return this._createNewLine(params);
        }
    }
}
