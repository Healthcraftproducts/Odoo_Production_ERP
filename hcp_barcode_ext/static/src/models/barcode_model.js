/** @odoo-module **/

import BarcodeModel from '@stock_barcode/models/barcode_model';
console.log("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")


export default class ConfirmBarcodeModel extends BarcodeModel {
createNewLine(params) {
    console.log("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        const product = params.fieldsParams.product_id;
        if (this.askBeforeNewLinesCreation(product)) {
            const confirmationPromise = new Promise((resolve, reject) => {
                const body = product.code ?
                    sprintf(
                        _t("Scanned product [%s] %s is not reserved for this transfer. Are you sure you want to add it?"),
                        product.code, product.display_name
                    ) :
                    sprintf(
                        _t("Scanned product %s is not reserved for this transfer. Are you sure you want to add it?"),
                        product.display_name
                    );

                this.isBarcodeGroupUser = this.user.hasGroup("hcp_contact_ext.custom_barcode_admin");
                if (isBarcodeGroupUser){
                    this.dialogService.add(ConfirmationDialog, {
                        body, title: _t("Add extra product?"),
                        cancel: reject,
                        confirm: async () => {
                            const newLine = await this._createNewLine(params);
                            resolve(newLine);
                        },
                        close: reject,
                    });
                }
                else{
                    this.dialogService.add(ConfirmationDialog, {
                        body, title: _t("Add extra product?"),
                        cancel: reject,
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