from odoo import models, fields, api
from odoo.exceptions import Warning
from datetime import datetime, timedelta

class MotgamaWizardReporteAnomalias(models.TransientModel):
    _name = 'motgama.wizard.reporteanomalias'
    _description = 'Wizard Reporte Anomalías'

    tipo = fields.Selection(string="Tipo de reporte",selection=[('factura','Por fecha de factura'),('anomalia','Por fecha de anomalía')],default='factura')
    fecha_inicial = fields.Datetime(string="Fecha inicial", required=True)
    fecha_final = fields.Datetime(string="Fecha final", required=True)

    @api.model
    def check_permiso(self):
        if self.env.ref('motgama.motagama_informe_anomalias') not in self.env.user.permisos:
            raise Warning('No tiene permitido generar este informe')
        
        return {
            'type': 'ir.actions.act_window',
            'name': "Reporte de anomalías",
            'res_model': "motgama.wizard.reporteanomalias",
            'view_mode': "form",
            'target': "new"
        }

    @api.multi
    def get_report(self):
        self.ensure_one()

        domain = [('factura_anomalia','=',True)]
        if self.tipo == 'factura':
            domain.append(('create_date','>=',self.fecha_inicial))
            domain.append(('create_date','<=',self.fecha_final))
        elif self.tipo == 'anomalia':
            domain.append(('fecha_anomalia','<=',self.fecha_final))
            domain.append(('fecha_anomalia','>=',self.fecha_inicial))
        else:
            raise Warning('Debe seleccionar un tipo de reporte')

        facturas = self.env['account.invoice'].search(domain)
        if not facturas:
            raise Warning('No hay facturas con anomalía dentro del rango de fechas especificado')

        reporte = self.env['motgama.reporteanomalias'].search([])
        for o in reporte:
            o.unlink()
        
        fecha_anomalia = facturas[0].fecha_anomalia - timedelta(hours=5)
        fecha_anomalia_format = datetime(fecha_anomalia.year,fecha_anomalia.month,fecha_anomalia.day,fecha_anomalia.hour,fecha_anomalia.minute, fecha_anomalia.second)

        fecha_inicial = self.fecha_inicial 
        fecha_inicial_format = datetime(fecha_inicial.year,fecha_inicial.month,fecha_inicial.day,fecha_inicial.hour,fecha_inicial.minute, fecha_inicial.second)

        fecha_final =self.fecha_final 
        fecha_final_format = datetime(fecha_final.year,fecha_final.month,fecha_final.day,fecha_final.hour,fecha_final.minute, fecha_final.second)

        for factura in facturas:
            valores = {
                'fecha_inicial': fecha_inicial_format,
                'fecha_final': fecha_final_format,
                'numero': factura.number,
                'fecha_factura': factura.date_invoice,
                'fecha_anomalia': fecha_anomalia_format,
                'motivo_anomalia': factura.motivo_anomalia
            }
            reporte = self.env['motgama.reporteanomalias'].create(valores)
            if not reporte:
                raise Warning('No fue posible generar el reporte')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Reporte de anomalías',
            'res_model': 'motgama.reporteanomalias',
            'view_mode': 'tree'
        }

class MotgamaReporteAnomalias(models.TransientModel):
    _name = 'motgama.reporteanomalias'
    _description = 'Reporte de Anomalías'

    fecha_inicial = fields.Datetime(string="Fecha inicial")
    fecha_final = fields.Datetime(string="Fecha final")
    numero = fields.Char(string="Número")
    fecha_factura = fields.Date(string="Fecha de factura")
    fecha_anomalia = fields.Datetime(string="Fecha de anomalía")
    motivo_anomalia = fields.Text(string="Motivo de anomalía")

class PDFReporteAnomalias(models.AbstractModel):
    _name = 'report.motgama.plantilla_reporte_anomalias'

    @api.model
    def _get_report_values(self,docids,data=None):
        docs = self.env['motgama.reporteanomalias'].browse(docids)

        fecha_inicial = docs[0].fecha_inicial - timedelta(hours=5)
        fecha_inicial_format = datetime(fecha_inicial.year,fecha_inicial.month,fecha_inicial.day,fecha_inicial.hour,fecha_inicial.minute, fecha_inicial.second)

        fecha_final = docs[0].fecha_final - timedelta(hours=5)
        fecha_final_format = datetime(fecha_final.year,fecha_final.month,fecha_final.day,fecha_final.hour,fecha_final.minute, fecha_final.second)

        return {
            'docs': docs,
            'fecha_inicial': fecha_inicial_format,
            'fecha_final': fecha_final_format
        }