from odoo import models, fields, api
from odoo.exceptions import Warning
from datetime import datetime, timedelta

class WizardReporteHospedaje(models.TransientModel):
    _name = 'motgama.wizard.reportehospedaje'

    fecha_inicial = fields.Datetime(string='Fecha Inicial',required=True)
    fecha_final = fields.Datetime(string= 'Fecha final',required=True)
    recepcion = fields.Many2one(string='Recepcion',comodel_name='motgama.recepcion')

    @api.model
    def check_permiso(self):
        if self.env.ref('motgama.motgama_informe_ocupaciones') not in self.env.user.permisos:
            raise Warning('No tiene permitido generar este informe')
        
        return {
            'type': 'ir.actions.act_window',
            'name': "Reporte de ocupaciones",
            'res_model': "motgama.wizard.reportehospedaje",
            'view_mode': "form",
            'target': "new"
        }

    @api.multi
    def get_report(self):
        self.ensure_one()

        paramOcasional = self.env['motgama.parametros'].search([('codigo','=','CODHOSOCASIO')],limit=1)
        if not paramOcasional:
            raise Warning('No se ha definido el parámetro CODHOSOCASIO, contacte al administrador')
        paramAmanecida = self.env['motgama.parametros'].search([('codigo','=','CODHOSAMANE')],limit=1)
        if not paramAmanecida:
            raise Warning('No se ha definido el parámetro CODHOSAMANE, contacte al administrador')
        paramAdicional = self.env['motgama.parametros'].search([('codigo','=','CODHOSADCNAL')],limit=1)
        if not paramAmanecida:
            raise Warning('No se ha definido el parámetro CODHOSADCNAL, contacte al administrador')

        movimientos = self.env['motgama.movimiento'].search([('asignafecha','>',self.fecha_inicial),('asignafecha','<',self.fecha_final),('asignatipo','in',['OO','OA']),'|',('active','=',True),('active','=',False)])
        if not movimientos:
            raise Warning('No hay movimientos que mostrar')

        hospedajes = self.env['motgama.reportehospedaje'].search([])
        for hospedaje in hospedajes:
            hospedaje.unlink()

        ids = []
        for movimiento in movimientos:
            if not self.recepcion:
                ids.append(movimiento)
            else:
                if movimiento.habitacion_id.zona_id.recepcion_id.id == self.recepcion.id:
                    ids.append(movimiento)
        
        for movimiento in ids:
            factura = movimiento.factura
            if not factura:
                continue

            fecha_inicial = self.fecha_inicial - timedelta(hours=5)
            fecha_inicial_format = datetime(fecha_inicial.year,fecha_inicial.month,fecha_inicial.day,fecha_inicial.hour,fecha_inicial.minute, fecha_inicial.second)

            fecha_final = self.fecha_final - timedelta(hours=5)
            fecha_final_format = datetime(fecha_final.year,fecha_final.month,fecha_final.day,fecha_final.hour,fecha_final.minute, fecha_final.second)

            fecha_mov = movimiento.asignafecha - timedelta(hours=5) 
            fecha_mov_format = datetime(fecha_mov.year,fecha_mov.month,fecha_mov.day,fecha_mov.hour,fecha_mov.minute, fecha_mov.second)

            for line in factura.invoice_line_ids:
                valores = {
                    'fecha_inicial': fecha_inicial_format,
                    'fecha_final': fecha_final_format,
                    'recepcion_reporte': self.recepcion.nombre if self.recepcion else False,
                    'recepcion': movimiento.habitacion_id.zona_id.recepcion_id.nombre,
                    'fecha': fecha_mov_format,
                    'habitacion': movimiento.habitacion_id.codigo,
                    'usuario': movimiento.recauda_uid.name
                }
                if line.product_id.default_code == paramOcasional.valor:
                    valores.update({'tipoHospedaje':'O'})
                elif line.product_id.default_code == paramAmanecida.valor:
                    valores.update({'tipoHospedaje':'AM'})
                elif line.product_id.default_code == paramAdicional.valor:
                    valores.update({'tipoHospedaje':'AD','cantidad':line.quantity})
                else:
                    continue
                valores.update({'valor':line.price_unit * line.quantity})
                nuevo = self.env['motgama.reportehospedaje'].create(valores)
                if not nuevo:
                    raise Warning('No se pudo crear el reporte')

        return{
            'name': 'Reporte de hospedaje',
            'view_mode':'tree',
            'view_id': self.env.ref('motgama.tree_reporte_hospedaje').id,
            'res_model': 'motgama.reportehospedaje',
            'type': 'ir.actions.act_window',
            'context': {'search_default_groupby_tipo': 1},
            'target': 'main'
        } 

class ReporteHospedaje(models.TransientModel):
    _name = 'motgama.reportehospedaje'

    fecha_inicial = fields.Datetime(string='Fecha inicial')
    fecha_final = fields.Datetime(string='Fecha final')
    recepcion_reporte = fields.Char(string='Recepción del reporte')

    recepcion = fields.Char(string='Recepción')
    fecha = fields.Datetime(string='Fecha')
    habitacion = fields.Char(string='Habitación')
    tipoHospedaje = fields.Selection(string='Tipo de hospedaje',selection=[('O','Hospedaje Ocasional'),('AM','Hospedaje Amanecida'),('AD','Hospedaje Adicional')])
    cantidad = fields.Float(string="Cantidad",default=1)
    valor = fields.Float(string='Valor')
    usuario = fields.Char(string='Usuario')

class PDFReporteHospedaje(models.AbstractModel):
    _name = 'report.motgama.reportehospedaje'

    @api.model
    def _get_report_values(self,docids,data=None):
        docs = self.env['motgama.reportehospedaje'].browse(docids)

        hospedajes = {}
        total = 0
        for doc in docs:
            tipoHospedaje = 'Hospedaje Ocasional' if doc.tipoHospedaje == 'O' else 'Hospedaje Amanecida' if doc.tipoHospedaje == 'AM' else 'Hospedaje Adicional' if doc.tipoHospedaje == 'AD' else ''
            if tipoHospedaje in hospedajes:
                hospedajes[tipoHospedaje]['cantidad'] += doc.cantidad
                hospedajes[tipoHospedaje]['valor'] += doc.valor
            else:
                hospedajes[tipoHospedaje] = {'cantidad': doc.cantidad, 'valor': doc.valor}
            total += doc.valor

        for hospedaje in hospedajes:
            hospedajes[hospedaje]['valor'] = "{:0,.2f}".format(hospedajes[hospedaje]['valor']).replace(',','¿').replace('.',',').replace('¿','.')
        
        return {
            'company': self.env['res.company']._company_default_get('account.invoice'),
            'sucursal': self.env['motgama.sucursal'].search([],limit=1),
            'docs': docs,
            'hospedajes': hospedajes,
            'total': "{:0,.2f}".format(total).replace(',','¿').replace('.',',').replace('¿','.')
        }