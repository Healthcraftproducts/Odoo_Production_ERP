//odoo.define('bom_structure_in_excel.mrp_bom_excel', function (require) {
//"use strict";
//
//var core = require('web.core');
//var framework = require('web.framework');
//var MrpBomReport = require('stock.stock_report_generic');
//var ajax = require('web.ajax');
//var core = require('web.core');
//var rpc = require('web.rpc');
//
//var QWeb = core.qweb;
//var _t = core._t;
//
//
//var MrpBomReportExt = MrpBomReport.include({
//
//    set_excel: function() {
//        var self = this;
//        return this._super().then(function () {
//            self.$('.o_content').html(self.data.lines);
//            self.renderSearchExcel();
//            self.update_excel();
//        });
//    },
//    update_excel: function () {
//        var status = {
//            cp_content: {
//                $buttons: this.$buttonPrint,
//            },
//        };
//        return this.updateControlPanel(status);
//    },
//    renderSearchExcel: function () {
//        this.$buttonPrint = $(QWeb.render('mrp.button'));
//        this.$buttonPrint.find('.o_mrp_bom_print_excel').on('click', this._onClickPrint());
//    },
//     _onClickPrint: function (){
//                return this._rpc({
//                        model: 'mrp.bom',
//                        method: 'custom_print_bom_structure_excel',
//                        args: [],
//                }) .then(function () {
////                    self.data = result;
//                });
//        });
//
//});
//core.action_registry.add('mrp_bom_excel', MrpBomReportExt);
//return MrpBomReportExt;
//});