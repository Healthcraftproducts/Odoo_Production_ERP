odoo.define('hcp_mrp_customization.qweb_template', function (require) {
'use strict';
    var core = require('web.core');
    var ajax = require('web.ajax');
    var qweb = core.qweb;
    ajax.loadXML('/hcp_mrp_customization/static/src/xml/qweb_template.xml', qweb);
});
