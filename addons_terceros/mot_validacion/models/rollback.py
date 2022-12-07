from odoo import models, fields, api

from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

class Rollback(models.TransientModel):
    _name = 'mot_validacion.rollback'
    _description = 'Rollback'

    tipo = fields.Selection(string="Tipo de rollback",selection=[('log','Por histórico'),('facturas','Por facturas específicas'),('fechas','Por rango de fechas de facturas')],default='log')
    historico_id = fields.Many2one(string="Histórico a hacer rollback",comodel_name="mot_validacion.log")
    fecha_inicial = fields.Datetime(string="Fecha inicial")
    fecha_final = fields.Datetime(string="Fecha final")
    factura_ids = fields.Many2many(string='Facturas',comodel_name='mot_validacion.invoice')
    invoice_ids = fields.Many2many(string='Invoices',comodel_name='mot_validacion.invoice',compute='_compute_invoices',store=True)

    # Carga las facturas según el tipo de rollback que se desea realizar
    @api.depends('tipo','historico_id','fecha_inicial','fecha_final','factura_ids')
    def _compute_invoices(self):
        for record in self:
            if record.tipo == 'log' and record.historico_id:
                record.invoice_ids = [(6,0,record.historico_id.rollback_ids.ids)]
            elif record.tipo == 'facturas' and len(record.factura_ids) > 0:
                record.invoice_ids = [(6,0,record.factura_ids.ids)]
            elif record.tipo == 'fechas' and record.fecha_inicial and record.fecha_final and record.fecha_final > record.fecha_inicial:
                facturas = self.env['mot_validacion.invoice'].search([('factura_creada','>=',record.fecha_inicial),('factura_creada','<=',record.fecha_final)])
                record.invoice_ids = [(6,0,facturas.ids)]
            else:
                record.invoice_ids = [(5)]

    @api.multi
    def rollback(self):
        self.ensure_one()

        # Genera un nuevo log de proceso tipo rollback
        valores_log = {
            'fecha': fields.Datetime().now(),
            'proceso': 'rollback',
            'resultado': 'proceso'
        }
        log = self.env['mot_validacion.log'].sudo().create(valores_log)

        # Carga las facturas seleccionadas en el wizard del rollback
        facturas = self.invoice_ids if self.invoice_ids else self.env['mot_validacion.invoice'].search([])

        docs = []
        # Comienza el proceso por cada factura
        for factura in facturas:
            _logger.info('Factura ' + str(factura.invoice_id.number))

            # Guarda los id de las facturas modificadas para el log
            docs.append(factura.invoice_id.id)

            # Carga el parámetro de máximo rollback y evita facturas anteriores al máximo permitido
            param_max = self.env.ref('mot_validacion.parametro_ROLLBACK_MAX').valor_float
            horas = 24.0 * param_max
            if factura.create_date < fields.Datetime().now() - timedelta(hours=round(horas)):
                continue
            _logger.info('Factura pagos')
            _logger.info(factura.pagos)
            # Cancela y modifica los pagos de la factura para devolverlos a su estado original
            for payment in factura.pagos:
                _logger.info('Pago ' + payment.payment_id.name + ', estado: ' + payment.payment_id.state)
                payment.payment_id.sudo().cancel()
                _logger.info('Pago ' + payment.payment_id.name + ', estado: ' + payment.payment_id.state)
                payment.payment_id.sudo().action_draft()
                _logger.info('Pago ' + payment.payment_id.name + ', estado: ' + payment.payment_id.state)
                _logger.info('Pago ' + payment.payment_id.name + ', valor: ' + str(payment.payment_id.amount))
                payment.payment_id.sudo().write({'amount': payment.importe})
                _logger.info('Pago ' + payment.payment_id.name + ', valor: ' + str(payment.payment_id.amount))

            # Cancela y modifica la factura para devolverla a su estado original
            _logger.info('Factura ' + str(factura.invoice_id.number) + ', estado: ' + factura.invoice_id.state)
            factura.invoice_id.action_invoice_cancel()
            _logger.info('Factura ' + str(factura.invoice_id.number) + ', estado: ' + factura.invoice_id.state)
            factura.invoice_id.action_invoice_draft()
            factura.invoice_id.sudo().compute_taxes()
            _logger.info('Factura ' + str(factura.invoice_id.number) + ', estado: ' + factura.invoice_id.state)
            factura.invoice_id.sudo().write({
                'asignafecha': factura.ingreso,
                'liquidafecha': factura.salida,
                'habitacion_id': factura.habitacion_id.id if factura.habitacion_id else False,
                'origin': factura.doc if factura.doc else ''
            })

            # Modifica las líneas de factura para devolverlas a su estado original
            ids = []
            for line in factura.lineas:
                line.line_id.sudo().write({
                    'invoice_id': line.invoice_id.invoice_id.id,
                    'product_id': line.producto.id,
                    'name': line.descripcion,
                    'quantity': line.cantidad,
                    'price_unit': line.precio,
                    'invoice_line_tax_ids': [(6,0,line.impuestos.ids)]
                })
                ids.append(line.line_id.id)
            # Desvincula cualquier línea que haya sido agregada a la factura por el proceso de reducción
            for line in factura.invoice_id.invoice_line_ids:
                if line.id not in ids:
                    line.sudo().write({'invoice_id': False})
            
            # Vuelve a calcular los valores de la factura y la valida con la información original
            factura.invoice_id.sudo().write({'date': factura.invoice_id.date,'validada': False})
            _logger.info('Factura ' + str(factura.invoice_id.number) + ', estado: ' + factura.invoice_id.state)
            factura.invoice_id.action_invoice_cancel()
            _logger.info('Factura ' + str(factura.invoice_id.number) + ', estado: ' + factura.invoice_id.state)
            factura.invoice_id.action_invoice_draft()
            factura.invoice_id.compute_taxes()
            _logger.info('Factura ' + str(factura.invoice_id.number) + ', estado: ' + factura.invoice_id.state)
            factura.invoice_id.action_invoice_open()
            _logger.info('Factura ' + str(factura.invoice_id.number) + ', estado: ' + factura.invoice_id.state)

            # Publica los pagos con la información original
            for payment in factura.pagos:
                _logger.info('Factura ' + str(factura.invoice_id.number) + ', estado: ' + factura.invoice_id.state)
                _logger.info('Factura ' + str(factura.invoice_id.number) + ', valor: ' + str(factura.invoice_id.amount_total))
                _logger.info('Pago ' + payment.payment_id.name + ', valor: ' + str(payment.payment_id.amount))
                payment.payment_id.sudo().post()
            for pago in factura.recibo.pagos:
                pago.pago.sudo().write({'valor': pago.valor})

            # Actualiza el recaudo con sus valores originales
            factura.recibo.recaudo.sudo().write({
                'movimiento_id': factura.recibo.movimiento_id.id if factura.recibo.movimiento_id else False,
                'habitacion_id': factura.recibo.habitacion_id.id if factura.recibo.habitacion_id else False,
                'total_pagado': factura.recibo.total,
                'valor_pagado': factura.recibo.pagado
            })
            factura.sudo().unlink()
        
        # Al finalizar actualiza el log
        log.sudo().write({
            'doc_ids': [(6,0,docs)],
            'resultado': 'ok'
        })
        
        return {
            'name': 'Histórico',
            'view_mode': 'tree,form',
            'res_model': 'mot_validacion.log',
            'type': 'ir.actions.act_window',
            'target':'main'
        }

    # Proceso de eliminación automática de facturas rollback
    @api.model
    def auto_delete(self):
        param_max = self.env.ref('mot_validacion.parametro_STORE_ROLLBACK').valor_float
        horas = 24.0 * param_max
        fecha_delete = fields.Datetime().now() - timedelta(hours=horas)
        rollbacks = self.env['mot_validacion.invoice'].search([('create_date','<',fecha_delete)])
        for factura in rollbacks:
            for pago in factura.recibo.pagos:
                pago.sudo().unlink()
            factura.recibo.sudo().unlink()
            for pago in factura.pagos:
                pago.sudo().unlink()
            for linea in factura.lineas:
                linea.sudo().unlink()
            factura.sudo().unlink()