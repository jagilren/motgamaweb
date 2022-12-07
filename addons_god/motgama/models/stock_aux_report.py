from odoo import models, fields, api
from odoo.exceptions import Warning

class stock_aux_report(models.TransientModel):
    _inherit="stock_aux_report.stock_aux_report_wizard"

    @api.multi
    def get_report(self):
        if not self.env.ref('motgama.motgama_reporte_auxiliar_inventario') in self.env.user.permisos:
            raise Warning('No tiene permitido generar reporte auxiliar de inventario, contacte al administrador')
        return super().get_report()

class inventory_report(models.TransientModel):
     _inherit="stock.quantity.history"

     @api.multi
     def open_table(self):
        if not self.env.ref('motgama.motgama_reporte_saldos_inventario') in self.env.user.permisos:
            raise Warning('No tiene permitido generar reporte de saldos de inventario , contacte al administrador')
        return super().open_table()
        

    