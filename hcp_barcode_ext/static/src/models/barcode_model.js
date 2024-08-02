/** @odoo-module **/

import BarcodeModel from '@stock_barcode/models/barcode_model';
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { sprintf } from '@web/core/utils/strings';
import { _t } from 'web.core';

/*  Modify the BarcodeModel prototype */
BarcodeModel.prototype.createNewLine = function (params) {
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
//                custom_barcode_admin
                if (this.groups.group_barcode_admin){
                    this.dialogService.add(ConfirmationDialog, {
                        body, title: _t("Add extra product?"),
                        cancel: reject,
                        confirm: async () => {
                            const newLine = await this._createNewLine(params);
                            resolve(newLine);
                        },
                        close: reject,
                        confirmClass: 'btn-danger',
                    });
                    }
                 else{
                    this.dialogService.add(ConfirmationDialog, {
                        body, title: _t("Add extra product?"),
                        cancel: reject,
                        confirm: reject,
                        confirmClass: 'btn-danger',
                        close: reject,
                    });
                }
            });
            return confirmationPromise;
        } else {
            return this._createNewLine(params);
        }
    }
