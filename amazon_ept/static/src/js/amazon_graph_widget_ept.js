odoo.define('amazon_ept.graph', function (require) {
    "use strict";

    var fieldRegistry = require('web.field_registry');
    var AbstractField = require('web.AbstractField');
    var graph_ept = require('graph_widget_ept.graph');
    var core = require('web.core');
    var QWeb = core.qweb;
    var KanbanController = require('web.KanbanController');
    var KanbanView = require('web.KanbanView');
    var viewRegistry = require('web.view_registry');

    graph_ept.EmiproDashboardGraph.include({
        events: _.extend({}, graph_ept.EmiproDashboardGraph.prototype.events || {}, {
            'change #sort_order_data_amazone': '_sortAmazoneOrders',
            'click #instance_fbm_order': '_getFbmOrders',
            'click #instance_fba_order': '_getFbaOrders',
        }),

        _sortAmazoneOrders: function(e) {
          var self = this;
          this.context.fulfillment_by = e.currentTarget.value
            return this._rpc({model: self.model,method: 'read',args:[this.res_id],'context':this.context}).then(function (result) {
                if(result.length) {
                    self.graph_data = JSON.parse(result[0][self.match_key])
                    self.on_attach_callback()
                }
            })
        },

         /*Render action for  Sales Order */
                _getFbmOrders: function () {
                    return this.do_action(this.graph_data.fbm_order_data.order_action)
                },

        /*Render action for  Sales Order */
                        _getFbaOrders: function () {
                            return this.do_action(this.graph_data.fba_order_data.order_action)
                        },


    });
    var amazonDashboardKanbanController = KanbanController.extend();

    var AmazonDashboardGraphEptView = KanbanView.extend({
        config: _.extend({}, KanbanView.prototype.config, {
            Controller: amazonDashboardKanbanController,
        }),
    });

    viewRegistry.add('AmazonDashboardGraphEpt', AmazonDashboardGraphEptView);

});