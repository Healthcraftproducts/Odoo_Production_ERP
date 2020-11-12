from odoo import models, api

class DeringerXmlReport(models.TransientModel):
   _name = "report.hcp_deringer.deringer_xml_report"
   
   @api.model
   def _get_report_values(self, docids, data=None):
       #start_date = data['start_date']
       #end_date = data['end_date']
       cr = self._cr
       query = """select name from account_move"""
       cr.execute(query)
       dat = cr.dictfetchall()
       return {
                'dat': dat
            }
