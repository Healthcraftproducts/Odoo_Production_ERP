odoo.define('stock_barcode.LinesWidgetExt', function (require) {
'use strict';

var LinesWidget = require('stock_barcode.LinesWidget');

var LinesWidgetExt = LinesWidget.include({

    events: _.extend({}, LinesWidget.prototype.events, {
        'click .o_back_custom3': '_backToPage3',
    }),

    init: function (parent, page, pageIndex, nbPages) {
        this._super.apply(this, arguments);
    },

     _backToPage3: function (ev) {
        ev.stopPropagation();
        this.trigger_up('exit');
    },    
});

return LinesWidgetExt;


});
