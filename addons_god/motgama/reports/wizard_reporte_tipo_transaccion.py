from odoo import fields, models, api
from odoo.exceptions import Warning
import logging, os, shutil, base64
_logger = logging.getLogger(__name__)


class WizardReporteTipoTransaccion(models.TransientModel):
    _name = 'motgama.wizard.reportetipotransaccion'
    _description = 'Wizard del Reporte Tipo de Transacción'

    fecha_inicial = fields.Datetime(string='Fecha inicial', required=True)
    fecha_final = fields.Datetime(string='Fecha final', required=True)
    filtro_transaccion = fields.Many2many(string='Filtro Transacción', comodel_name='stock.picking.type')
    resumido = fields.Boolean(string="Resumido")

    @api.model
    def check_permiso(self):
        if self.env.ref('motgama.motgama_reporte_tipo_transaccion') not in self.env.user.permisos:
            raise Warning('No tiene permitido generar este informe')
        
        return {
            'type': 'ir.actions.act_window',
            'name': "Reporte ",
            'res_model': "motgama.wizard.reportetipotransaccion",
            'view_mode': "form",
            'target': "new"
        }

    @api.multi
    def get_report(self):
        _logger.info("Se llega al get report del tipo de transaccion")
        self.ensure_one()
        reporte = self.env['motgama.reportetipotransaccion'].search([])
        for x in reporte:
            x.unlink()
        pickings = self.env['stock.picking'].search([('date_done','>=',self.fecha_inicial),('date_done','<=', self.fecha_final),('picking_type_id','=',self.filtro_transaccion.ids)])
        for picking in pickings:
            for move in picking.move_ids_without_package:
                valores = {
                    'currency_id':self.env.user.company_id.currency_id.id,
                    'fecha_inicial':self.fecha_inicial,
                    'fecha_final':self.fecha_final,
                    'fecha1':picking.date_done,
                    'usuario':picking.create_uid.name, 
                    'dcto':picking.name,
                    'referencia':move.product_id.name,
                    'cantidad':move.quantity_done,
                    'valor_unitario':move.product_id.standard_price,
                    'valor_total':move.quantity_done * move.product_id.standard_price,
                    'impuesto_total':move.product_id.supplier_taxes_id.amount/100 * move.quantity_done * move.product_id.standard_price,
                    'valor_total_general': move.quantity_done * move.product_id.standard_price + move.product_id.supplier_taxes_id.amount/100 * move.quantity_done * move.product_id.standard_price,
                    'tipo_transaccion': picking.picking_type_id.name,
                    'categoria':move.product_id.categ_id.name,
                    'resumido':self.resumido
                }
                nuevo = self.env['motgama.reportetipotransaccion'].create(valores)
                if not nuevo:
                    raise Warning('No fue posible generar el reporte')
        
        return {
                'name': 'Reporte Tipo de Transacción',
                'view_mode':'tree',
                'view_id': self.env.ref('motgama.tree_reporte_tipo_transaccion').id,
                'res_model': 'motgama.reportetipotransaccion',
                'type': 'ir.actions.act_window',
                'target': 'main'
            }




class MotgamaReporteTipoTransaccion(models.TransientModel):
    _name = 'motgama.reportetipotransaccion'
    _description = 'Reporte Tipo de Transacción'

    currency_id = fields.Many2one(string='Moneda',comodel_name='res.currency')
    fecha_inicial = fields.Datetime(string="Fecha inicial")
    fecha_final = fields.Datetime(string="Fecha final")
    fecha1 = fields.Datetime(string="Fecha")
    usuario = fields.Char(string="Usuario")
    dcto = fields.Char(string="Documento")
    referencia = fields.Char(string="Referencia")
    cantidad = fields.Integer(string="Cantidad")
    valor_unitario = fields.Monetary(string="Valor Unitario")
    valor_total = fields.Monetary(string="Valor Total")
    impuesto_total = fields.Monetary(string="Impuesto Total")
    valor_total_general = fields.Monetary(string="Valor Total General")
    tipo_transaccion = fields.Char(string="Tipo Transacción")
    categoria = fields.Char(string="Categoría")
    resumido = fields.Boolean(string="Resumido")







class PDFReporteTipoTransaccion(models.AbstractModel):
    _name = 'report.motgama.reportetipotransaccion'


    @api.model
    def _get_report_values(self,docids,data=None):
        docs = self.env['motgama.reportetipotransaccion'].browse(docids)
        tipos={}
        totales = {
            'cantidad':0,
            'valor_unitario':0,
            'valor_total':0,
            'impuesto':0,
            'valor_total_general':0
        }
        for doc in docs:
            if doc.tipo_transaccion in tipos:
                tipos[doc.tipo_transaccion]['docs'].append(doc)
                if doc.categoria in tipos[doc.tipo_transaccion]['categorias']:
                    tipos[doc.tipo_transaccion]['categorias'][doc.categoria]['cantidad']+=doc.cantidad
                    tipos[doc.tipo_transaccion]['categorias'][doc.categoria]['valor_unitario']+=doc.valor_unitario
                    tipos[doc.tipo_transaccion]['categorias'][doc.categoria]['valor_total']+=doc.valor_total
                    tipos[doc.tipo_transaccion]['categorias'][doc.categoria]['impuesto']+=doc.impuesto_total
                    tipos[doc.tipo_transaccion]['categorias'][doc.categoria]['valor_total_general']+=doc.valor_total_general
                else:
                    tipos[doc.tipo_transaccion]['categorias'][doc.categoria]={
                            'cantidad':doc.cantidad,
                            'valor_unitario':doc.valor_unitario, 
                            'valor_total':doc.valor_total,
                            'impuesto':doc.impuesto_total,
                            'valor_total_general':doc.valor_total_general
                        }
                tipos[doc.tipo_transaccion]['totales']['cantidad']+=doc.cantidad
                tipos[doc.tipo_transaccion]['totales']['valor_unitario']+=doc.valor_unitario
                tipos[doc.tipo_transaccion]['totales']['valor_total']+=doc.valor_total
                tipos[doc.tipo_transaccion]['totales']['impuesto']+=doc.impuesto_total
                tipos[doc.tipo_transaccion]['totales']['valor_total_general']+=doc.valor_total_general
            else:
                tipos[doc.tipo_transaccion] = {
                    'docs':[doc],
                    'categorias':{
                        doc.categoria:{
                            'cantidad':doc.cantidad,
                            'valor_unitario':doc.valor_unitario, 
                            'valor_total':doc.valor_total,
                            'impuesto':doc.impuesto_total,
                            'valor_total_general':doc.valor_total_general
                        }
                    },
                    'totales':{
                        'cantidad':doc.cantidad,
                        'valor_unitario':doc.valor_unitario,
                        'valor_total':doc.valor_total,
                        'impuesto':doc.impuesto_total,
                        'valor_total_general':doc.valor_total_general
                    }
                }
            totales['cantidad']+=doc.cantidad
            totales['valor_unitario']+=doc.valor_unitario
            totales['impuesto']+=doc.impuesto_total
            totales['valor_total']+=doc.valor_total
            totales['valor_total_general']+=doc.valor_total_general

            
            
        
        totales['valor_unitario'] = "$ {:0,.2f}".format(totales['valor_unitario']).replace(',','¿').replace('.',',').replace('¿','.')
        totales['valor_total'] = "$ {:0,.2f}".format(totales['valor_total']).replace(',','¿').replace('.',',').replace('¿','.')
        totales['impuesto'] = "$ {:0,.2f}".format(totales['impuesto']).replace(',','¿').replace('.',',').replace('¿','.')
        totales['valor_total_general'] = "$ {:0,.2f}".format(totales['valor_total_general']).replace(',','¿').replace('.',',').replace('¿','.')  

        for tipo in tipos:
            tipos[tipo]['totales']['valor_unitario'] = "$ {:0,.2f}".format( tipos[tipo]['totales']['valor_unitario']).replace(',','¿').replace('.',',').replace('¿','.')
            tipos[tipo]['totales']['valor_total'] = "$ {:0,.2f}".format( tipos[tipo]['totales']['valor_total']).replace(',','¿').replace('.',',').replace('¿','.')
            tipos[tipo]['totales']['impuesto'] = "$ {:0,.2f}".format( tipos[tipo]['totales']['impuesto']).replace(',','¿').replace('.',',').replace('¿','.')
            tipos[tipo]['totales']['valor_total_general'] = "$ {:0,.2f}".format( tipos[tipo]['totales']['valor_total_general']).replace(',','¿').replace('.',',').replace('¿','.')

            for categoria in tipos[tipo]['categorias']:
                tipos[tipo]['categorias'][categoria]['valor_unitario']="$ {:0,.2f}".format(tipos[tipo]['categorias'][categoria]['valor_unitario']).replace(',','¿').replace('.',',').replace('¿','.')
                tipos[tipo]['categorias'][categoria]['valor_total']="$ {:0,.2f}".format(tipos[tipo]['categorias'][categoria]['valor_total']).replace(',','¿').replace('.',',').replace('¿','.')
                tipos[tipo]['categorias'][categoria]['impuesto']="$ {:0,.2f}".format(tipos[tipo]['categorias'][categoria]['impuesto']).replace(',','¿').replace('.',',').replace('¿','.')
                tipos[tipo]['categorias'][categoria]['valor_total_general']="$ {:0,.2f}".format( tipos[tipo]['categorias'][categoria]['valor_total_general']).replace(',','¿').replace('.',',').replace('¿','.')

        
        

        return {
                'tipos': tipos,
                'totales': totales,
                'fecha_inicial':docs[0].fecha_inicial,
                'fecha_final': docs[0].fecha_final,
                'usuario':docs[0].usuario
            }