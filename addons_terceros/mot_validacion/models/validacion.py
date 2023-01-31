from pydoc import describe
from odoo import models, fields, api
from odoo.exceptions import Warning

import random, math
from datetime import datetime, timedelta
import ftplib, logging, json
_logger = logging.getLogger(__name__)

# Esta función permite redondear los valores a centenas o miles
def roundToLow(x,exp):
    exp *= -1
    return math.floor(x/10**exp) * 10**exp

# Definición de variables para el proceso de reducción
class Validacion(models.TransientModel):
    _name = 'mot_validacion.validacion'
    _description = 'Proceso de Validacion'

    fecha_inicial = fields.Datetime(string="Fecha inicial", required=True)
    fecha_final = fields.Datetime(string="Fecha final", required=True, default=fields.Datetime().now())
    auto = fields.Boolean(string="Automático",default=False)

    ver_metas = fields.Boolean(string="Ver valores")

    meta = fields.Float(string="Meta",compute="_compute_valores")
    porc_reduc = fields.Char(string="% Reducción",compute="_compute_valores")
    landvalue = fields.Float(string="Landvalue",compute="_compute_valores")
    sum_aportes = fields.Float(string="Suma aportes",compute="_compute_valores")
    porc_borr = fields.Integer(string="Ponderación Borrables",compute="_compute_valores")
    porc_hosp = fields.Integer(string="Ponderación Hospedaje",compute="_compute_valores")
    porc_inven = fields.Integer(string="Ponderación Inventario",compute="_compute_valores")

    factura_ids = fields.Many2many(string="Facturas",comodel_name="account.invoice")
    borrables_ids = fields.Many2many(string="Borrables",comodel_name="account.invoice.line")
    hospedaje_ids = fields.Many2many(string="Hospedaje",comodel_name="account.invoice.line")
    inventario_ids = fields.Many2many(string="Inventario",comodel_name="account.invoice.line")
    descuentos = fields.Text(string="Descuentos")

    loading = fields.Boolean(string="Cargando...")

    @api.onchange('ver_metas')
    def _onchange_metas(self):
        if self.ver_metas:
            self.loading = True
        else:
            self.loading = False

    @api.depends('fecha_inicial','fecha_final','ver_metas')
    def _compute_valores(self):
        _logger.info("entro al compute")
        for record in self:
            if record.ver_metas and record.fecha_inicial and record.fecha_final:
                # Se cargan los parámetros
                # MEDIOS_BORRABLES = Medios de pago borrables
                mediosborrables = self.env.ref('mot_validacion.parametro_MEDIOS_BORRABLES').mediopago_ids
                # Productos borrables
                prodsborrables = self.env.ref('mot_validacion.parametro_BORRABLES').producto_ids
                # Categorías de productos borrables
                categborrables = self.env.ref('mot_validacion.parametro_BORRABLES').prod_categ_ids
                # Tipos de hospedaje (ocasional/amanecida)
                prod_ocasional = self.get_ocasional()
                prod_amanecida = self.get_amanecida()
                # % Reducción por tipo de habitación
                reduchosp = self.env.ref('mot_validacion.parametro_REDUCCIONxHOSPEDAJE').reduc_hospedaje
                # % Reducción por categoría de producto
                reducinv = self.env.ref('mot_validacion.parametro_REDUCCIONxINVENTARIO').reduc_inventario
                categsinv = reducinv.mapped('categ_id')
                # Categorías que no pueden quedar huérfanas
                categnoorphan = self.env.ref('mot_validacion.parametro_CATEGORIA_NO_ORPHAN').prod_categ_ids

                # % Reducción de la meta
                porc_reduc = self.env.ref('mot_validacion.parametro_REDUCCION').valor_int
                # % Aportes
                porc_borr = self.env.ref('mot_validacion.parametro_PONDERACIONxDESCONTABLE').borrables
                porc_hosp = self.env.ref('mot_validacion.parametro_PONDERACIONxDESCONTABLE').hospedaje
                porc_inven = self.env.ref('mot_validacion.parametro_PONDERACIONxDESCONTABLE').inventario
                techo_borr = self.env.ref('mot_validacion.parametro_PONDERACIONxDESCONTABLE').techo_borrables
                techo_hosp = self.env.ref('mot_validacion.parametro_PONDERACIONxDESCONTABLE').techo_hospedaje
                techo_inven = self.env.ref('mot_validacion.parametro_PONDERACIONxDESCONTABLE').techo_inventario

                # Redondeo
                param_redondeo = self.env.ref('mot_validacion.parametro_REDONDEO').redondeo
                redondeo = -2 if param_redondeo == 'cent' else -3 if param_redondeo == 'mil' else 2
                
                # Se cargan las facturas
                domain = [
                    ('create_date','>',self.fecha_inicial),
                    ('create_date','<',self.fecha_final),
                    ('state','=','paid'),
                    ('refund_invoice_id','=',False),
                    ('refund_invoice_ids','=',False),
                    ('validada','=',False),
                    ('factura_anomalia','=',False),
                    ('recaudo','!=',False)
                ]
                facturas = self.env['account.invoice'].search(domain)
                _logger.info("compute domain")
                # Inicializar valores
                meta = 0.0
                landvalue = 0.0
                sum_aportes = 0.0
                descuentos = {'lines':self.env['account.invoice.line']}
                borrables = {'lines':self.env['account.invoice.line'],'descuentos':self.env['account.invoice.line']}
                inventarios = {'lines':self.env['account.invoice.line'],'descuentos':self.env['account.invoice.line']}
                hospedajes = {'lines':self.env['account.invoice.line'],'descuentos':self.env['account.invoice.line']}
                no_orphan_lines = self.env['account.invoice.line']
                id_facturas = []
                no_orphan = self.env['account.invoice.line']
                _logger.info("compute values")
                for factura in facturas:
                    # Se descartan las facturas no pagadas en medios borrables
                    medios_borrables = True
                    for pago in factura.recaudo.pagos:
                        if not pago.mediopago in mediosborrables:
                            medios_borrables = False
                            break
                    if not medios_borrables:
                        continue

                    id_facturas.append(factura.id)
                    descuentos['lines'] += factura.invoice_line_ids.filtered(lambda r: r.price_unit < 0)
                    borrables['lines'] += factura.invoice_line_ids.filtered(lambda r: r.product_id in prodsborrables or r.product_id.categ_id in categborrables and r not in descuentos)
                    inventarios['lines'] += factura.invoice_line_ids.filtered(lambda r: r.product_id.categ_id in categsinv and r not in descuentos['lines'] + borrables['lines'])

                    porc = reduchosp.filtered(lambda r: r.tipo_id == factura.habitacion_id.tipo).porcentaje
                    no_orphan = factura.invoice_line_ids.filtered(lambda r: r.product_id.categ_id in categnoorphan and r not in borrables['lines'])
                    if not (porc == 100 and porc_hosp == 100 and no_orphan):
                        hospedajes['lines'] += factura.invoice_line_ids.filtered(lambda r: r.product_id in [prod_amanecida,prod_ocasional] and r not in descuentos['lines'] + borrables['lines'])
                        if no_orphan and porc == 100 and techo_hosp == 100:
                            no_orphan_lines += factura.invoice_line_ids.filtered(lambda r: r.product_id in [prod_amanecida,prod_ocasional] and r not in descuentos['lines'] + borrables['lines'])
                        
                    
                
                borrables['meta'] = sum([roundToLow(line.price_unit * line.quantity,redondeo) for line in borrables['lines']])
                inventarios['meta'] = sum([roundToLow(line.quantity * line.price_unit * reducinv.filtered(lambda r: r.categ_id == line.product_id.categ_id).porcentaje / 100, redondeo) for line in inventarios['lines']])
                hospedajes['meta'] = sum([roundToLow(line.quantity * line.price_unit * reduchosp.filtered(lambda r: r.tipo_id == line.invoice_id.habitacion_id.tipo).porcentaje / 100,redondeo) for line in hospedajes['lines']])
                descs = {}
                for line in descuentos['lines']:
                    base_line = line.sale_line_ids[0].base_line
                    base_line = self.env['account.invoice.line'].search([('sale_line_ids','=',base_line.id)],limit=1)
                    porc = 0
                    tipo_desc = ''
                    if base_line.id in borrables['lines'].ids:
                        porc = 100
                        tipo_desc = 'borr'
                        borrables['meta'] += roundToLow(line.price_unit * line.quantity,redondeo)
                    elif base_line.id in hospedajes['lines'].ids:
                        porc = reduchosp.filtered(lambda r: r.tipo_id == base_line.invoice_id.habitacion_id.tipo).porcentaje
                        tipo_desc = 'hosp'
                        hospedajes['meta'] += roundToLow(line.price_unit * line.quantity * porc / 100,redondeo)
                    elif base_line.id in inventarios['lines'].ids:
                        porc = line.price_unit * line.quantity * reducinv.filtered(lambda r: r.categ_id == base_line.product_id.categ_id).porcentaje
                        tipo_desc = 'inven'
                        inventarios['meta'] += roundToLow(line.price_unit * line.quantity * porc / 100,redondeo)
                    descs[line.id] = {'porc': porc, 'tipo_desc': tipo_desc, 'base': base_line.id}
                _logger.info("compute fin ifs")
                borrables['aporte'] = roundToLow(borrables['meta'] * porc_borr / 100,redondeo)
                hospedajes['aporte'] = roundToLow(hospedajes['meta'] * porc_hosp / 100,redondeo)
                inventarios['aporte'] = roundToLow(inventarios['meta'] * porc_inven / 100,redondeo)
                _logger.info("inventarios meta")
                _logger.info(inventarios['meta'])
                
                meta = borrables['meta'] + hospedajes['meta'] + inventarios['meta']
                _logger.info("meta antes de llegar")
                _logger.info(meta)
                _logger.info("porc reduc antes de llegar")
                _logger.info(porc_reduc)
                _logger.info("redondeo antes de llegar")
                _logger.info(redondeo)
                landvalue = roundToLow(meta * porc_reduc / 100, redondeo)
                _logger.info("land value despues del proceso")
                _logger.info(landvalue)
                sum_aportes = borrables['aporte'] + hospedajes['aporte'] + inventarios['aporte']
                _logger.info("sum_aportes")
                _logger.info(sum_aportes)

                # Iterar para acercarse al techo de reducción
                porc_error = self.env.ref('mot_validacion.parametro_REDUCCION').porc_error
                val_error = landvalue * porc_error / 100
                paso_reduc = self.env.ref('mot_validacion.parametro_REDUCCION').paso_reduc
                en_techo_hosp = False
                _logger.info("land value")
                _logger.info(landvalue)
                while paso_reduc > 0 and sum_aportes < landvalue - val_error:
                    _logger.info("Entre al while")
                    if porc_borr < techo_borr:
                        if porc_borr + paso_reduc < techo_borr:
                            porc_borr += paso_reduc
                        else:
                            porc_borr = techo_borr
                    elif porc_hosp < techo_hosp:
                        if porc_hosp + paso_reduc < techo_hosp:
                            porc_hosp += paso_reduc
                        else:
                            porc_hosp = techo_hosp
                    elif porc_inven < techo_inven:
                        if porc_inven + paso_reduc < techo_inven:
                            porc_inven += paso_reduc
                        else:
                            porc_inven = techo_inven
                    else:
                        break
                    borrables['aporte'] = roundToLow(borrables['meta'] * porc_borr / 100,redondeo)
                    inventarios['aporte'] = roundToLow(inventarios['meta'] * porc_inven / 100,redondeo)

                    if porc_hosp == 100 and not en_techo_hosp:
                        hospedajes['meta'] -= sum([roundToLow(line.price_unit * line.quantity,redondeo) for line in no_orphan_lines])
                        hospedajes['lines'] -= no_orphan_lines
                        remove_descs = []
                        for desc in descs:
                            if descs[desc]['base'] in no_orphan_lines.ids:
                                line = self.env['account.invoice.line'].browse(desc)
                                hospedajes['meta'] -= roundToLow(line.price_unit * line.quantity,redondeo)
                                remove_descs.append(desc)
                        for desc in remove_descs:
                            descs.pop(desc, None)
                        en_techo_hosp = True
                    hospedajes['aporte'] = roundToLow(hospedajes['meta'] * porc_hosp / 100,redondeo)

                    sum_aportes = borrables['aporte'] + hospedajes['aporte'] + inventarios['aporte']
                    meta = borrables['meta'] + hospedajes['meta'] + inventarios['meta']
                    _logger.info("Meta")
                    _logger.info(meta)
                    _logger.info("porc_reduc")
                    _logger.info(porc_reduc)
                    _logger.info("redondeo")
                    _logger.info(redondeo)
                    landvalue = roundToLow(meta * porc_reduc / 100,redondeo)
                    _logger.info("resultado land value")
                    _logger.info(landvalue)

                _logger.info(hospedajes['lines'].ids)
                record.loading = False
                record.meta = meta
                record.landvalue = landvalue
                record.sum_aportes = sum_aportes
                record.porc_reduc = porc_reduc
                record.porc_borr = porc_borr
                record.porc_hosp = porc_hosp
                record.porc_inven = porc_inven
                _logger.info("antes de facturas")
                record.factura_ids = [(6,0,id_facturas)]
                _logger.info("antes de borrables")
                record.borrables_ids = [(6,0,borrables['lines'].ids)]
                _logger.info("antes de hospedaje")
                record.hospedaje_ids = [(6,0,hospedajes['lines'].ids)]
                record.inventario_ids = [(6,0,inventarios['lines'].ids)]
                record.descuentos = json.dumps(descs)
                _logger.info("compute despues records")
                

    @api.model
    def get_ocasional(self):
        param_ocasional = self.env['motgama.parametros'].search([('codigo','=','CODHOSOCASIO')],limit=1)
        if not param_ocasional:
            raise Warning('No se ha definido el parámetro "CODHOSOCASIO" en Motgama')
        prod_ocasional = self.env['product.product'].search([('default_code','=',param_ocasional.valor)],limit=1)
        if not prod_ocasional:
            raise Warning('No existe el producto / servicio con Referencia interna "' + param_ocasional.valor + '"')
        return prod_ocasional

    @api.model
    def get_amanecida(self):
        param_amanecida = self.env['motgama.parametros'].search([('codigo','=','CODHOSAMANE')],limit=1)
        if not param_amanecida:
            raise Warning('No se ha definido el parámetro "CODHOSAMANE" en Motgama')
        prod_amanecida = self.env['product.product'].search([('default_code','=',param_amanecida.valor)],limit=1)
        if not prod_amanecida:
            raise Warning('No existe el producto / servicio con Referencia interna "' + param_amanecida.valor + '"')
        return prod_amanecida

    @api.multi
    # Proceso de reducción
    def reducir(self):
        self.ensure_one()

        # Se prepara el log del proceso
        valores_log = {
            'auto': self.auto,
            'fecha': fields.Datetime().now(),
            'fecha_inicial': self.fecha_inicial,
            'fecha_final': self.fecha_final,
            'proceso': 'validacion',
            'resultado': 'proceso',
        }
        auto = self.auto
        log = self.env['mot_validacion.log'].sudo().create(valores_log)

        # Se cargan los parámetros
        prodsborrables = self.env.ref('mot_validacion.parametro_BORRABLES').producto_ids
        prodscomodin = self.env.ref('mot_validacion.parametro_COMODIN').producto_ids
        categborrables = self.env.ref('mot_validacion.parametro_BORRABLES').prod_categ_ids
        categintercambiables = self.env.ref('mot_validacion.parametro_CATEGORIA_INTERCAMBIABLE').prod_categ_ids
        categnoorphan = self.env.ref('mot_validacion.parametro_CATEGORIA_NO_ORPHAN').prod_categ_ids
        categcomodin = self.env.ref('mot_validacion.parametro_COMODIN').prod_categ_ids
        reduchosp = self.env.ref('mot_validacion.parametro_REDUCCIONxHOSPEDAJE').reduc_hospedaje
        reducinv = self.env.ref('mot_validacion.parametro_REDUCCIONxINVENTARIO').reduc_inventario
        param_redondeo = self.env.ref('mot_validacion.parametro_REDONDEO').redondeo
        redondeo = -2 if param_redondeo == 'cent' else -3 if param_redondeo == 'mil' else 2

        comodines = []
        if len(prodscomodin) > 0:
            for producto in prodscomodin:
                comodines.append(producto)
        else:
            for categoria in categcomodin:
                prods = self.env['product.product'].search([('categ_id','=',categoria.id)])
                for prod in prods:
                    if prod in comodines:
                        continue
                    comodines.append(prod)
        
        # Se definen los mensajes de error
        error_asunto = 'Se ha presentado un error en la llave y fue necesario un rollback completo'
        error_msg = 'No ha sido posible terminar de ejecutar el proceso de reducción en la Llave y se ha realizado un rollback completo. Detalle del error:'
        error_end = 'Ningún documento ha sido afectado'
        error = False

        prod_ocasional = self.get_ocasional()
        prod_amanecida = self.get_amanecida()

        if not error:
            # Realiza los cálculos
            self.write({'ver_metas':True})
            self._compute_valores()
            # Carga las facturas
            facturas = self.factura_ids

            # Se cargan los productos de descuentos definidos en los parámetros
            prod_desc_hosp = False
            if self.env.ref('mot_validacion.parametro_DETALLE_DCTO_FACT_HOSPEDAJE').valor_boolean:
                prod_desc_hosp = self.env.ref('mot_validacion.parametro_PROD_DESC').prod_desc_hosp
            prod_desc_inven = False
            if self.env.ref('mot_validacion.parametro_DETALLE_DCTO_FACT_INVENTARIOS').valor_boolean:
                prod_desc_inven = self.env.ref('mot_validacion.parametro_PROD_DESC').prod_desc_inven

            # Se carga la información de los descuentos
            descuentos_dict = json.loads(self.descuentos)

            rollbacks = []
            # Se crean los rollback de facturas
            for factura in facturas:
                valores_linea = []
                for line in factura.invoice_line_ids:
                    valores = {
                        'line_id': line.id,
                        'producto': line.product_id.id,
                        'descripcion': line.name,
                        'cantidad': line.quantity,
                        'precio': line.price_unit,
                        'impuestos': [(4,imp.id) for imp in line.invoice_line_tax_ids],
                        'subtotal': line.price_subtotal
                    }
                    valores_linea.append(valores)
                    # Revisa si es descuento y lo marca
                    if line.price_unit < 0:
                        base_line = line.sale_line_ids[0].base_line
                        base_line = self.env['account.invoice.line'].search([('sale_line_ids','=',base_line.id)],limit=1)
                        line.sudo().write({'base_line': base_line.id})
                valores_payment = []
                for payment in factura.payment_ids:
                    valores = {
                        'payment_id': payment.id,
                        'metodo': payment.journal_id.id,
                        'importe': payment.amount
                    }
                    valores_payment.append(valores)
                valores_pagos = []
                for pago in factura.recaudo.pagos:
                    valores = {
                        'pago': pago.id,
                        'mediopago': pago.mediopago.id,
                        'valor': pago.valor
                    }
                    valores_pagos.append(valores)
                valores_recibo = {
                    'recaudo': factura.recaudo.id,
                    'movimiento_id': factura.recaudo.movimiento_id.id,
                    'habitacion_id': factura.recaudo.habitacion.id,
                    'pagos': [(0,0,valores) for valores in valores_pagos],
                    'total': factura.recaudo.total_pagado,
                    'pagado': factura.recaudo.valor_pagado
                }
                recibo = self.env['mot_validacion.invoice.recibo'].sudo().create(valores_recibo)
                if not recibo:
                    if auto:
                        valoresNotificacion = {
                            'asunto': error_asunto,
                            'descripcion': error_msg + '\n\tError: No fue posible generar registros para el rollback \n\t\tRecaudo # ' + factura.recaudo.nrorecaudo + '\n' + error_end,
                        }
                        self.env['mot_validacion.notificacion'].create(valoresNotificacion)
                        error = True
                    else:
                        raise Warning('No fue posible generar registros para el rollback')
                valores_factura = {
                    'invoice_id': factura.id,
                    'fecha_factura': factura.date_invoice,
                    'factura_creada': factura.create_date,
                    'cliente': factura.partner_id.id,
                    'ingreso': factura.asignafecha,
                    'salida': factura.liquidafecha,
                    'lineas': [(0,0,valores) for valores in valores_linea],
                    'base': factura.amount_untaxed,
                    'impuestos': factura.amount_tax,
                    'total': factura.amount_total,
                    'pagos': [(0,0,valores) for valores in valores_payment],
                    'recibo': recibo.id,
                    'doc': factura.origin,
                    'habitacion_id': factura.habitacion_id.id
                }
                rollback = self.env['mot_validacion.invoice'].sudo().create(valores_factura)
                if not rollback:
                    if auto:
                        valoresNotificacion = {
                            'asunto': error_asunto,
                            'descripcion': error_msg + '\n\tError: No fue posible generar registros para el rollback \n\t\tFactura # ' + factura.number + '\n' + error_end,
                        }
                        self.env['mot_validacion.notificacion'].create(valoresNotificacion)
                        error = True
                    else:
                        raise Warning('No fue posible generar registros para el rollback')
                recibo.sudo().write({'invoice_id': rollback.id})
                rollbacks.append(rollback.id)

                # Se arma una lista de pagos para llevar registro del porcentaje de la factura pagado con ese medio de pago
                recibo = factura.recaudo
                pagos = {}
                invoice_payments = self.env['account.payment']
                for pago in recibo.pagos:
                    pagos[pago] = pago.valor / factura.amount_total
                    if pago.pago_id:
                        invoice_payments += pago.pago_id

                # Se cancelan los pagos registrados y se dejan en borrador para permitir cancelar la factura
                payments = {}
                for pago in invoice_payments:
                    pago.move_line_ids.sudo().remove_move_reconcile()
                    pago.sudo().cancel()
                    pago.sudo().action_draft()
                    payments[pago] = pago.amount / factura.amount_total
                # Se cancela la factura y se pone en estado borrador
                number = factura.number
                factura.action_invoice_cancel()
                factura.action_invoice_draft()

                # Se cargan las líneas de la factura específica
                borrables = self.borrables_ids.filtered(lambda r: r.invoice_id.id == factura.id)
                hospedaje = self.hospedaje_ids.filtered(lambda r: r.invoice_id.id == factura.id)
                inventario = self.inventario_ids.filtered(lambda r: r.invoice_id.id == factura.id)

                # Se reducen los borrables
                for line in borrables:
                    if self.porc_borr >= 100:
                        line.sudo().write({'invoice_id':False})
                    else:
                        line.sudo().write({'price_unit': line.price_unit * (1 - self.porc_borr / 100)})

                # Se reducen los hospedajes
                for line in hospedaje:
                    porc = reduchosp.filtered(lambda r: r.tipo_id == line.invoice_id.habitacion_id.tipo).porcentaje
                    meta = line.price_unit * porc / 100
                    aporte = meta * self.porc_hosp / 100
                    new_val = roundToLow(line.price_unit - aporte,redondeo)
                    if new_val <= 0:
                        line.sudo().write({'invoice_id': False})
                        factura.write({
                            'asignafecha': False,
                            'liquidafecha': False,
                            'habitacion_id': False,
                            'consumo': True
                        })
                        factura.recaudo.sudo().write({
                            'habitacion': False,
                            'movimiento_id': False,
                        })
                    elif prod_desc_hosp:
                        # TODO: Nueva Línea
                        pass
                    else:
                        line.sudo().write({'price_unit': new_val})

                # Se reducen los productos de inventario
                for line in inventario:
                    porc = reducinv.filtered(lambda r: r.categ_id == base_line.product_id.categ_id).porcentaje
                    meta = line.price_unit * porc / 100
                    _logger.info("meta")
                    _logger.info(meta)
                    aporte = meta * self.porc_inven / 100
                    _logger.info("aporte")
                    _logger.info(aporte)
                    new_val = roundToLow(line.price_unit - aporte,redondeo)
                    _logger.info("new val")
                    _logger.info(new_val)
                    if new_val <= 0:
                        _logger.info("entre al if new val")
                        line.sudo().write({'invoice_id':False})
                    elif prod_desc_inven:
                        _logger.info("entre al elif new val")
                        # TODO: Nueva Línea
                        pass
                    else:
                        _logger.info("entre al else new val")
                        line.sudo().write({'price_unit': new_val})

                _logger.info("meta descuento inventario")
                _logger.info(meta)
                
                # Se reducen los descuentos
                for line in factura.invoice_line_ids.filtered(lambda r: r.price_unit < 0):
                    if line.id not in descuentos_dict:
                        continue
                    new_val = roundToLow(line.price_unit * (1 - descuentos_dict[line.id]['porc'] / 100),redondeo)
                    if new_val >= 0:
                        vals = {'invoice_id':False}
                    else:
                        vals = {'price_unit': new_val}
                    line.sudo().write(vals)

                # Se vuelven a calcular los impuestos de la factura
                factura.sudo().compute_taxes()
                # Si la factura quedó en un estado incoherente (Sin líneas o en valor total 0 o negativo) se revisa si es posible intercambiar productos con otras facturas
                _logger.info("Numero de lineas")
                _logger.info(len(factura.invoice_line_ids))
                if len(factura.invoice_line_ids) == 0 or factura.amount_total <= 0:
                    _logger.info("primer if factura.invoice linea ids")
                    for invoice in facturas:
                        linea = False
                        lineas_desc = []
                        for line in invoice.invoice_line_ids:
                            if line.product_id.categ_id in categintercambiables:
                                if line.desc_line_ids:
                                    if len(invoice.invoice_line_ids) < len(line.desc_line_ids) + 2:
                                        break
                                    lineas_desc.extend([linea_desc for linea_desc in line.desc_line_ids])
                                elif line.quantity > 1:
                                    val_line = {
                                        'product_id':line.product_id.id,
                                        'name':line.name,
                                        'quantity':line.quantity,
                                        'price_unit':line.price_unit,
                                        'invoice_line_tax_ids':[(6,0,line.invoice_line_tax_ids.ids)]
                                    }
                                    factura.sudo().write({'invoice_line_ids':[(0,0,val_line)]})
                                    line.write({'quantity':line.quantity-1})
                                    break
                                linea = line
                                break


                        if linea:
                            linea.sudo().write({'invoice_id': factura.id})
                            for linea_desc in lineas_desc:
                                linea_desc.sudo().write({'invoice_id': factura.id})
                            invoice.sudo().write({'date': invoice.date})
                            factura.sudo().write({'date': factura.date})
                            if invoice.amount_total <= 0:
                                linea.sudo().write({'invoice_id': invoice.id})
                                for linea_desc in lineas_desc:
                                    linea_desc.sudo().write({'invoice_id': invoice.id})
                                invoice.sudo().write({'date': invoice.date})
                                factura.sudo().write({'date': factura.date})
                            invoice.sudo().compute_taxes()
                        if factura.amount_total > 0:
                            break
                # Luego del proceso se calculan nuevamente los impuestos
                factura.sudo().compute_taxes()
                _logger.info("Numero de lineas despues de")
                _logger.info(len(factura.invoice_line_ids))
                hacer_rollback = False
                # Se vuelve a revisar si la factura es incoherente y si es así se agrega un producto comodín
                if len(factura.invoice_line_ids) == 0 or factura.amount_total <= 0:
                    _logger.info("despues del segundo if del comodin")
                    if len(comodines) > 0:
                        i = random.randrange(0,len(comodines))
                        valores = {
                            'product_id': comodines[i].id,
                            'name': comodines[i].name,
                            'quantity': 1,
                            'price_unit': roundToLow(comodines[i].lst_price,redondeo),
                            'invoice_line_tax_ids': [(4,tax.id) for tax in comodines[i].taxes_id],
                            'account_id': comodines[i].property_account_income_id.id if comodines[i].property_account_income_id else comodines[i].categ_id.property_account_income_categ_id.id
                        }
                        factura.sudo().write({'invoice_line_ids': [(0,0,valores)]})
                    else:
                        hacer_rollback = True
                # Se vuelven a calcular los impuestos
                factura.sudo().compute_taxes()
                # Si la factura sigue siendo incoherente, se debe hacer un rollback de todas las facturas
                if len(factura.invoice_line_ids) == 0 or factura.amount_total <= 0:
                    hacer_rollback = True
                
                # Si es necesario hacer rollback, se realiza el proceso dependiendo si era un proceso automático o manual (En el automático debe salir un correo de notificación, en el manual simplemente se muestra un Warning)
                if hacer_rollback:
                    if auto:
                        error = True
                        # Rollback
                        valores_rollback = {
                            'tipo': 'facturas',
                            'factura_ids': [(6,0,rollbacks)]
                        }
                        rollback = self.env['mot_validacion.rollback'].create(valores_rollback)
                        rollback.rollback()
                        valoresNotificacion = {
                            'asunto': error_asunto,
                            'descripcion': error_msg + '\n\tNo se pudo reducir la factura ' + number + ' o su estado era incoherente, por lo que se ha realizado un rollback completo \n' + error_end,
                        }
                        self.env['mot_validacion.notificacion'].create(valoresNotificacion)
                        break
                    else:
                        raise Warning('No se pudo reducir la factura ' + number + ' y su estado es incoherente por lo que se ha realizado un rollback completo')
                # Si no era necesario el rollback, se valida la factura y se modifican los pagos
                else:
                    factura.action_invoice_open()
                    for payment in payments:
                        payment.sudo().write({
                            'amount': factura.amount_total * payments[payment],
                            'invoice_ids': [(4,factura.id)]
                        })
                        payment.post()
                    
                    recibo.sudo().write({
                        'total_pagado': factura.amount_total,
                        'valor_pagado': factura.amount_total
                    })
                    for pago in pagos:
                        pago.sudo().write({'valor': factura.amount_total * pagos[pago]})

                    # Se elimina toda relación entre la factura y la orden de venta de la que venía
                    if factura.origin:
                        order = self.env['sale.order'].search([('name','=',factura.origin)],limit=1)
                        if order:
                            order.sudo().write({'invoice_ids': [(3,factura.id)]})
                        factura.sudo().write({'origin': ''})
            
            # Se revisa si después del proceso siguen existiendo facturas en valor 0
            facturas_cero = []
            for factura in facturas:
                if factura.amount_total <= 0:
                    if not auto:
                        raise Warning('Ha ocurrido un error en el proceso de validación: La factura ' + factura.number + ' ha quedado en cero y ha sido necesario hacer un rollback completo')
                    facturas_cero.append(factura)
            if auto and len(facturas_cero) > 0:
                error_msg = error_msg + '\n\tNo se pudo completar el proceso debido a que las siguientes facturas han quedado con valor CERO:\n'
                for fac in facturas_cero:
                    error_msg = error_msg + '\t\t- ' + fac.number + '\n'
                error_msg = error_msg + error_end
                error = True
                # Rollback
                valores_rollback = {
                    'tipo': 'facturas',
                    'factura_ids': [(6,0,rollbacks)]
                }
                rollback = self.env['mot_validacion.rollback'].create(valores_rollback)
                rollback.rollback()
                valoresNotificacion = {
                    'asunto': error_asunto,
                    'descripcion': error_msg
                }
                self.env['mot_validacion.notificacion'].create(valoresNotificacion)
            elif len(facturas_cero) > 0:
                error_msg = error_msg + '\n\tNo se pudo completar el proceso debido a que las siguientes facturas han quedado con valor CERO:\n'
                for fac in facturas_cero:
                    error_msg = error_msg + '\t\t- ' + fac.number + '\n'
                raise Warning(error_msg)
            
            # Todas las facturas que fueron procesadas se marcan como validadas
            for factura in facturas:
                factura.sudo().write({'validada': True})

            # Se registra el log de la reducción
            valores_log_reduccion = {
                'fecha': log.fecha,
                'log_id': log.id,
                'reduc_max': self.sum_aportes,
                'reduc_param': self.meta
            }
            self.env['mot_validacion.log.reduccion'].sudo().create(valores_log_reduccion)

        # Se termina de registrar el histórico del proceso
        if error:
            log.sudo().write({
                'resultado': 'error',
                'doc_ids': [(4,factura.id) for factura in facturas]
            })
        else:
            log.sudo().write({
                'resultado': 'ok',
                'doc_ids': [(4,factura.id) for factura in facturas],
                'rollback_ids': [(6,0,rollbacks)]
            })

        # Finaliza el proceso de reducción
        return {
            'name': 'Histórico',
            'view_mode': 'tree,form',
            'res_model': 'mot_validacion.log',
            'type': 'ir.actions.act_window',
            'target':'main'
        }

    @api.multi
    # Proceso de reducción
    def validar(self):
        self.ensure_one()
    
        # Se prepara el log del proceso
        valores_log = {
            'auto': self.auto,
            'fecha': fields.Datetime().now(),
            'fecha_inicial': self.fecha_inicial,
            'fecha_final': self.fecha_final,
            'proceso': 'validacion',
            'resultado': 'proceso',
        }
        auto = self.auto
   
        log = self.env['mot_validacion.log'].sudo().create(valores_log)
     
        # Se cargan los parámetros
        mediosborrables = self.env.ref('mot_validacion.parametro_MEDIOS_BORRABLES').mediopago_ids
        prodsborrables = self.env.ref('mot_validacion.parametro_BORRABLES').producto_ids
        prodscomodin = self.env.ref('mot_validacion.parametro_COMODIN').producto_ids
        categborrables = self.env.ref('mot_validacion.parametro_BORRABLES').prod_categ_ids
        categintercambiables = self.env.ref('mot_validacion.parametro_CATEGORIA_INTERCAMBIABLE').prod_categ_ids
        categnoorphan = self.env.ref('mot_validacion.parametro_CATEGORIA_NO_ORPHAN').prod_categ_ids
        categcomodin = self.env.ref('mot_validacion.parametro_COMODIN').prod_categ_ids
        reduchosp = self.env.ref('mot_validacion.parametro_REDUCCIONxHOSPEDAJE').reduc_hospedaje
        reducinv = self.env.ref('mot_validacion.parametro_REDUCCIONxINVENTARIO').reduc_inventario
        param_redondeo = self.env.ref('mot_validacion.parametro_REDONDEO').redondeo
        redondeo = -2 if param_redondeo == 'cent' else -3 if param_redondeo == 'mil' else 2
   
        comodines = []
        if len(prodscomodin) > 0:
            for producto in prodscomodin:
                comodines.append(producto)
        else:
            for categoria in categcomodin:
                prods = self.env['product.product'].search([('categ_id','=',categoria.id)])
                for prod in prods:
                    if prod in comodines:
                        continue
                    comodines.append(prod)

        # Se definen los mensajes de error
        error_asunto = 'Se ha presentado un error en la llave y fue necesario un rollback completo'
        error_msg = 'No ha sido posible terminar de ejecutar el proceso de reducción en la Llave y se ha realizado un rollback completo. Detalle del error:'
        error_end = 'Ningún documento ha sido afectado'
        error = False
        
        _logger.info("LLEGUE AL METODO part pte 2")
        # Se cargan los productos de hospedaje
        param_ocasional = self.env['motgama.parametros'].search([('codigo','=','CODHOSOCASIO')],limit=1)
        if not param_ocasional:
            if auto:
                valoresNotificacion = {
                    'asunto': error_asunto,
                    'descripcion': error_msg + '\n\tError: No se ha definido el parámetro "CODHOSOCASIO" en Motgama \n' + error_end,
                }
                self.env['mot_validacion.notificacion'].create(valoresNotificacion)
                error = True
            else:
                raise Warning('No se ha definido el parámetro "CODHOSOCASIO" en Motgama')
        param_amanecida = self.env['motgama.parametros'].search([('codigo','=','CODHOSAMANE')],limit=1)
        if not param_amanecida:
            if auto:
                valoresNotificacion = {
                    'asunto': error_asunto,
                    'descripcion': error_msg + '\n\tError: No se ha definido el parámetro "CODHOSAMANE" en Motgama \n' + error_end,
                }
                self.env['mot_validacion.notificacion'].create(valoresNotificacion)
                error = True
            else:
                raise Warning('No se ha definido el parámetro "CODHOSAMANE" en Motgama')
        prod_ocasional = self.env['product.product'].search([('default_code','=',param_ocasional.valor)],limit=1)
        if not prod_ocasional:
            if auto:
                valoresNotificacion = {
                    'asunto': error_asunto,
                    'descripcion': error_msg + '\n\tError: No existe el producto / servicio con Referencia interna "' + param_ocasional.valor + '" \n' + error_end,
                }
                self.env['mot_validacion.notificacion'].create(valoresNotificacion)
                error = True
            else:
                raise Warning('No existe el producto / servicio con Referencia interna "' + param_ocasional.valor + '"')
        prod_amanecida = self.env['product.product'].search([('default_code','=',param_amanecida.valor)],limit=1)
        if not prod_amanecida:
            if auto:
                valoresNotificacion = {
                    'asunto': error_asunto,
                    'descripcion': error_msg + '\n\tError: No existe el producto / servicio con Referencia interna "' + param_amanecida.valor + '" \n' + error_end,
                }
                self.env['mot_validacion.notificacion'].create(valoresNotificacion)
                error = True
            else:
                raise Warning('No existe el producto / servicio con Referencia interna "' + param_amanecida.valor + '"')
        _logger.info("LLEGUE AL METODO part pte 1")
        if not error:
            # Realiza los cálculos
            self.write({'ver_metas':True})
            self._compute_valores()
            # Carga las facturas
            domain = [
                ('create_date','>',self.fecha_inicial),
                ('create_date','<',self.fecha_final),
                ('state','=','paid'),
                ('refund_invoice_id','=',False),
                ('refund_invoice_ids','=',False),
                ('validada','=',False),
                ('factura_anomalia','=',False),
                ('recaudo','!=',False)
            ]
            facturas_all = self.env['account.invoice'].search(domain)
            facturas = []
            total_ingresos = 0.0
            _logger.info("LLEGUE AL METODO part pte")
            # Revisa factura por factura si puede ser procesada
            for factura in facturas_all:
                doc = self.env['sale.order'].search([('name','=',factura.origin)], limit=1)
                _logger.info("doc:")
                _logger.info(doc)
                if doc:
                    doc.sudo().write({'active': False})
                # Revisa que el recaudo haya sido todo en medios borrables
                medios_borrables = True
                for pago in factura.recaudo.pagos:
                    if not pago.mediopago in mediosborrables:
                        medios_borrables = False
                        break
                if not medios_borrables:
                    continue
                
                # Se revisan las líneas de factura para ver si la factura se puede agregar al lote que será modificado
                agregar = False
                for line in factura.invoice_line_ids:
                    sumado = False
                    # Si el producto es borrable, se marca la factura para agregar y se suma al total de ingresos a reducir
                    if line.product_id in prodsborrables or line.product_id.categ_id in categborrables:
                        agregar = True
                        if not sumado:
                            total_ingresos += line.quantity * line.price_unit
                            sumado = True
                    # Si el producto es hospedaje, se marca la factura para agregar y se suma al total de ingresos a reducir
                    elif line.product_id in [prod_amanecida,prod_ocasional]:
                        for hosp in reduchosp:
                            if factura.habitacion_id and factura.habitacion_id.tipo == hosp.tipo_id:
                                agregar = True
                                if not sumado:
                                    total_ingresos += line.quantity * line.price_unit
                                    sumado = True
                    # Si el producto es inventario, se marca la factura para agregar y se suma al total de ingresos a reducir
                    for inv in reducinv:
                        if line.product_id.categ_id == inv.categ_id:
                            agregar = True
                            if not sumado:
                                total_ingresos += line.quantity * line.price_unit
                                sumado = True
                    # Si el producto es intercambiable, se marca la factura para agregar, así puede estar disponible para intercambiar productos con otra
                    if line.product_id.categ_id in categintercambiables:
                        agregar=True
                
                if agregar:
                    facturas.append(factura)
           
            # Se calculan los porcentajes a reducir del total de ingresos reducibles
            porc_total = self.env.ref('mot_validacion.parametro_REDUCCION').valor_int
            porc_borr = self.env.ref('mot_validacion.parametro_PONDERACIONxDESCONTABLE').borrables
            porc_hosp = self.env.ref('mot_validacion.parametro_PONDERACIONxDESCONTABLE').hospedaje
            porc_inven = self.env.ref('mot_validacion.parametro_PONDERACIONxDESCONTABLE').inventario

            # Se cargan los productos de descuentos definidos en los parámetros
            prod_desc_hosp = False
            if self.env.ref('mot_validacion.parametro_DETALLE_DCTO_FACT_HOSPEDAJE').valor_boolean:
                prod_desc_hosp = self.env.ref('mot_validacion.parametro_PROD_DESC').prod_desc_hosp
            prod_desc_inven = False
            if self.env.ref('mot_validacion.parametro_DETALLE_DCTO_FACT_INVENTARIOS').valor_boolean:
                prod_desc_inven = self.env.ref('mot_validacion.parametro_PROD_DESC').prod_desc_inven
            
            # Se calculan las metas de reducción (En pesos) que se esperan alcanzar con el proceso
            meta_desc = total_ingresos * porc_total / 100
            meta_borr = meta_desc * porc_borr / 100
            meta_hosp = meta_desc * porc_hosp / 100
            meta_inven = meta_desc * porc_inven / 100
            _logger.info("meta_inven")
            _logger.info(meta_inven)

            
            

            desc_borr = meta_borr
            desc_hosp = meta_hosp
            desc_inven = meta_inven
            rollbacks = []
            valor_descontado = 0.0
            
            
            # Se crean los rollback de facturas
            for factura in facturas:
                
                valores_linea = []
                for line in factura.invoice_line_ids:
                    _logger.info("cantidad q")
                    _logger.info(line.quantity)
                    valores = {
                        'line_id': line.id,
                        'producto': line.product_id.id,
                        'descripcion': line.name,
                        'cantidad': line.quantity,
                        'precio': line.price_unit,
                        'impuestos': [(4,imp.id) for imp in line.invoice_line_tax_ids],
                        'subtotal': line.price_subtotal
                    }
                    valores_linea.append(valores)
                    # Revisa si es descuento y lo marca
                    if line.price_unit < 0:
                        base_line = line.sale_line_ids[0].base_line
                        base_line = self.env['account.invoice.line'].search([('sale_line_ids','=',base_line.id)],limit=1)
                        line.sudo().write({'base_line': base_line.id})
                valores_payment = []
                # Aqui está llegando vacío 
                valores_pagos = []
                for pago in factura.recaudo.pagos:
                    valores = {
                        'pago': pago.id,
                        'mediopago': pago.mediopago.id,
                        'valor': pago.valor
                    }
                    valores_pagos.append(valores)
                    payment = pago.pago_id
                    valores = {
                        'payment_id': payment.id,
                        'metodo': payment.journal_id.id,
                        'importe': payment.amount
                    }
                    valores_payment.append(valores)
                    _logger.info("payment values")
                    _logger.info(payment)
                
                valores_recibo = {
                    'recaudo': factura.recaudo.id,
                    'movimiento_id': factura.recaudo.movimiento_id.id,
                    'habitacion_id': factura.recaudo.habitacion.id,
                    'pagos': [(0,0,valores) for valores in valores_pagos],
                    'total': factura.recaudo.total_pagado,
                    'pagado': factura.recaudo.valor_pagado
                }
                recibo = self.env['mot_validacion.invoice.recibo'].sudo().create(valores_recibo)
                if not recibo:
                    if auto:
                        valoresNotificacion = {
                            'asunto': error_asunto,
                            'descripcion': error_msg + '\n\tError: No fue posible generar registros para el rollback \n\t\tRecaudo # ' + factura.recaudo.nrorecaudo + '\n' + error_end,
                        }
                        self.env['mot_validacion.notificacion'].create(valoresNotificacion)
                        error = True
                    else:
                        raise Warning('No fue posible generar registros para el rollback')
                valores_factura = {
                    'invoice_id': factura.id,
                    'fecha_factura': factura.date_invoice,
                    'factura_creada': factura.create_date,
                    'cliente': factura.partner_id.id,
                    'ingreso': factura.asignafecha,
                    'salida': factura.liquidafecha,
                    'lineas': [(0,0,valores) for valores in valores_linea],
                    'base': factura.amount_untaxed,
                    'impuestos': factura.amount_tax,
                    'total': factura.amount_total,
                    'pagos': [(0,0,valores) for valores in valores_payment],
                    'recibo': recibo.id,
                    'doc': factura.origin,
                    'habitacion_id': factura.habitacion_id.id
                }
                _logger.info("pagos lista")
                _logger.info(valores_factura['pagos'])
                rollback = self.env['mot_validacion.invoice'].sudo().create(valores_factura)
                if not rollback:
                    if auto:
                        valoresNotificacion = {
                            'asunto': error_asunto,
                            'descripcion': error_msg + '\n\tError: No fue posible generar registros para el rollback \n\t\tFactura # ' + factura.number + '\n' + error_end,
                        }
                        self.env['mot_validacion.notificacion'].create(valoresNotificacion)
                        error = True
                    else:
                        raise Warning('No fue posible generar registros para el rollback')
                recibo.sudo().write({'invoice_id': rollback.id})
                rollbacks.append(rollback.id)

            datosFactura = {}
            for factura in facturas: 

                borrables = []
                hospedaje = {}
                inventario = {}
                descuentos = {}
                # Se inicia el proceso de reducción
                for line in factura.invoice_line_ids:
                    _logger.info('entro al for line')
                    _logger.info(line)
                    # Si la línea es de un descuento la ignora, se procesa junto con la línea anteriormente relacionadas
                    if line.price_unit < 0:
                        _logger.info("entro a primer if")
                        continue
                    # Si la línea tiene un producto borrable, la agrega a la lista borrables junto con su descuento
                    if desc_borr > 0 and (line.product_id in prodsborrables or line.product_id.categ_id in categborrables):
                        _logger.info("entro a segundo if")
                        borrables.append(line)
                        desc_borr -= line.quantity * line.price_unit
                        for desc_line in line.desc_line_ids:
                            borrables.append(desc_line)
                            desc_borr += abs(line.quantity * desc_line.price_unit)
                    # Si la línea es de hospedaje, la agrega a la lista de hospedaje con el valor a descontar según el tipo de habitación
                    elif desc_hosp > 0 and line.product_id in [prod_amanecida,prod_ocasional]:
                        _logger.info("entro a primer elif")
                        reduc = 0
                        porc = 1
                        for tipo in reduchosp:
                            if factura.habitacion_id and factura.habitacion_id.tipo == tipo.tipo_id:
                                porc = tipo.porcentaje / 100
                                reduc = line.price_unit * porc
                                break
                        hospedaje[line] = reduc
                        desc_hosp -= line.quantity * reduc
                        # El descuento del hospedaje se agrega a la lista de descuentos con el valor a reducir
                        for desc_line in line.desc_line_ids:
                            desc_desc = abs(desc_line.price_unit * porc)
                            descuentos[desc_line] = 0 - desc_desc
                            desc_hosp += desc_desc
                    # Si la línea es de un producto inventariable, la agrega a la lista de inventario con el valor a descontar según la categoría del producto
                    # esta asi elif desc_inven > 0 and line.product_id.categ_id in reducinv.mapped('categ_id'):
                    
                    elif line.product_id.categ_id in reducinv.mapped('categ_id'):
                        _logger.info("list mapped categ id")
                        _logger.info(reducinv.mapped('categ_id'))
                        reduc = 0
                        porc = 0
                        for inv in reducinv:
                            if line.product_id.categ_id == inv.categ_id:
                                _logger.info("entro a descontar")
                                porc = inv.porcentaje / 100
                                reduc = line.price_unit * porc
                                break
                        inventario[line] = {
                            'valor': reduc,
                            'cantidad': line.quantity
                        }
                        
                        _logger.info("Inventario line:")
                        _logger.info(inventario[line])
                        desc_inven -= line.quantity * reduc
                        _logger.info("Descuentos inventario:")
                        _logger.info(desc_inven)
                        # El descuento del producto se agrega a la lista de descuentos con el valor a reducir
                        for desc_line in line.desc_line_ids:
                            desc_desc = abs(desc_line.price_unit * porc)
                            descuentos[desc_line] = 0 - desc_desc
                            desc_inven += desc_desc
                
                # Se arma una lista de pagos para llevar registro del porcentaje de la factura pagado con ese medio de pago
                recibo = factura.recaudo
                pagos = {}
                invoice_payments = self.env['account.payment']
                for pago in recibo.pagos:
                    pagos[pago] = pago.valor / factura.amount_total
                    if pago.pago_id:
                        invoice_payments += pago.pago_id

                # Se cancelan los pagos registrados y se dejan en borrador para permitir cancelar la factura
                payments = {}
                for pago in invoice_payments:
                    pago.move_line_ids.sudo().remove_move_reconcile()
                    pago.sudo().cancel()
                    pago.sudo().action_draft()
                    payments[pago] = pago.amount / factura.amount_total
                # Se cancela la factura y se pone en estado borrador
                number = factura.number
                factura.action_invoice_cancel()
                factura.action_invoice_draft()
                _logger.info("LLEGUE AL METODO part 9")
                # Se inicia el proceso de reducción con la lista de líneas borrables
                for line in borrables:
                    no_orphan = False
                    if line.product_id in [prod_amanecida,prod_ocasional]:
                         for linea in factura.invoice_line_ids:
                            if linea.product_id.categ_id in categnoorphan:
                                _logger.info("entró al fin del proceso categoria no orphan")
                                no_orphan = True
                                break         
                    if not no_orphan:
                        line.sudo().write({'invoice_id': False})
                        factura.sudo().write({'date':factura.date})
                # Continúa la lista de hospedaje aplicando la reducción
                _logger.info("Hospeda")
                for line in hospedaje:
                    no_orphan = False
                    # Si el hospedaje queda en 0, se revisa si en la factura hay servicios que no puedan quedar huérfanos
                    _logger.info("Hospedaje line")
                    _logger.info(hospedaje[line])
                    if line.price_unit - hospedaje[line] == 0:
                        for linea in factura.invoice_line_ids:
                            if linea.product_id.categ_id in categnoorphan:
                                _logger.info("entró al fin del proceso categoria no orphan")
                                no_orphan = True
                                break
                            
                       
                    # Si no hay productos huérfanos, continúa con la reducción
                    if not no_orphan:
                        del_line = False
                        # Si el parámetro de agregar detalle de descuento en hospedaje es verdadero se crea una línea descontando el valor a reducir del hospedaje
                        if self.env.ref('mot_validacion.parametro_DETALLE_DCTO_FACT_HOSPEDAJE').valor_boolean:
                            if line.price_unit - hospedaje[line] <= 0.0:
                                del_line = True
                            else:
                                valores_desc_hosp = {
                                    'product_id': prod_desc_hosp.id,
                                    'name': prod_desc_hosp.name,
                                    'quantity': 1,
                                    'price_unit': roundToLow(0 - hospedaje[line],redondeo),
                                    'invoice_line_tax_ids': [(4,tax.id) for tax in prod_desc_hosp.taxes_id],
                                    'account_id': prod_desc_hosp.property_account_income_id.id if prod_desc_hosp.property_account_income_id else prod_desc_hosp.categ_id.property_account_income_categ_id.id
                                }
                                factura.write({'invoice_line_ids': [(0,0,valores_desc_hosp)]})
                                valor_descontado += hospedaje[line]
                        # Si no se agrega descuento se reduce el valor de la línea
                        else:
                            factura.sudo().write({'invoice_line_ids': [(1,line.id,{'price_unit':roundToLow(line.price_unit - hospedaje[line],redondeo)})]})
                            # Si el valor queda en 0, se debe quitar toda relación que tenga con la habitación y el movimiento del hospedaje
                            if line.price_unit <= 0:
                                del_line = True
                            else:
                                valor_descontado += hospedaje[line]
                        if del_line:
                            line.sudo().write({'invoice_id': False})
                            factura.write({
                                'asignafecha': False,
                                'liquidafecha': False,
                                'habitacion_id': False,
                                'consumo': True
                            })
                            factura.recaudo.sudo().write({
                                'habitacion': False,
                                'movimiento_id': False,
                            })
                            valor_descontado += hospedaje[line]
                # El proceso continúa con la lista de líneas de productos inventariables
                _logger.info("len inventario")
                _logger.info(len(inventario))

                for line in inventario:
                    # Si el parámetro de agregar detalle de descuento en inventario es verdadero se crea una línea descontando el valor a reducir del producto
                    if self.env.ref('mot_validacion.parametro_DETALLE_DCTO_FACT_INVENTARIOS').valor_boolean:
                        if line.price_unit - inventario[line]['valor'] <= 0.0:
                            line.sudo().write({'invoice_id': False})
                        else:
                            valores_desc_inven = {
                                'product_id': prod_desc_inven.id,
                                'name': prod_desc_inven.name + ': ' + line.name,
                                'quantity': inventario[line]['cantidad'],
                                'price_unit': roundToLow(0 - inventario[line]['valor'],redondeo),
                                'invoice_line_tax_ids': [(4,tax.id) for tax in prod_desc_inven.taxes_id],
                                'account_id': line.account_id.id
                            }
                            factura.write({'invoice_line_ids': [(0,0,valores_desc_inven)]})
                            new_line = factura.invoice_line_ids.filtered(lambda x: x.name == valores_desc_inven['name'] and x.price_unit == valores_desc_inven['price_unit'])
                            for new in new_line.ids:
                                x = new
                            line.sudo().write({'desc_line_ids': [(4, x)]})
                            valor_descontado += inventario[line]['valor']
                    # Si no se agrega descuento se reduce el valor de la línea
                    else:
                        factura.sudo().write({'invoice_line_ids': [(1,line.id,{'price_unit':roundToLow(line.price_unit - inventario[line]['valor'],redondeo)})]})
                        # Si el valor resultante es 0, se separa la línea de la factura
                        if line.price_unit == 0:
                            line.sudo().write({'invoice_id': False})
                        valor_descontado += inventario[line]['valor']
                # El proceso de reducción sigue con los descuentos reduciendo el valor en proporción a la reducción de la línea a la que se aplicaba
                for line in descuentos:
                    factura.sudo().write({'invoice_line_ids': [(1,line.id,{'price_unit': roundToLow(line.price_unit - descuentos[line],redondeo)})]})
                    valor_descontado += descuentos[line]
                    if line.price_unit == 0:
                        line.sudo().write({'invoice_id': False})
                # Se vuelven a calcular los impuestos de la factura
                factura.sudo().compute_taxes()
                # Si la factura quedó en un estado incoherente (Sin líneas o en valor total 0 o negativo) se revisa si es posible intercambiar productos con otras facturas
                # Se vuelven a calcular los impuestos de la factura
                factura.sudo().compute_taxes()
                # Si la factura quedó en un estado incoherente (Sin líneas o en valor total 0 o negativo) se revisa si es posible intercambiar productos con otras facturas
                _logger.info("Numero de lineas")
                _logger.info(len(factura.invoice_line_ids))
                _logger.info("Estado de factura")
                _logger.info(factura.state)
                datosFactura[factura]={'pagos':pagos, 'payments':payments}

            for factura in facturas:
                _logger.info("Estado2 de factura")
                _logger.info(factura.state)
                if len(factura.invoice_line_ids) == 0 or factura.amount_total <= 0:
                    _logger.info("primer if factura.invoice linea ids")
                    for invoice in facturas:
                        linea = False
                        lineas_desc = []
                        nameProducts = {}
                        totalQuantity = 0
                        for line in invoice.invoice_line_ids:
                            totalQuantity += line.quantity


                        
                        for line in invoice.invoice_line_ids:
                            if line.product_id.categ_id in categintercambiables:
                                if totalQuantity > 1:
                                    if line.quantity > 1:
                                        if line.desc_line_ids and len(line.desc_line_ids)==1 and line.desc_line_ids[0].quantity==line.quantity:
                                            val_line_desc = {
                                            'product_id':line.desc_line_ids[0].product_id.id,
                                            'name':line.desc_line_ids[0].name,
                                            'account_id':line.desc_line_ids[0].account_id.id,
                                            'quantity':1,
                                            'price_unit':line.desc_line_ids[0].price_unit,
                                            'invoice_line_tax_ids':[(6,0,line.desc_line_ids[0].invoice_line_tax_ids.ids)]
                                            }
                                            factura.sudo().write({'invoice_line_ids':[(0,0,val_line_desc)]})
                                            line.desc_line_ids[0].sudo().write({'quantity':line.desc_line_ids[0].quantity-1})
                                            val_line = {
                                            'product_id':line.product_id.id,
                                            'name':line.name,
                                            'account_id':line.account_id.id,
                                            'quantity':1,
                                            'price_unit':line.price_unit,
                                            'invoice_line_tax_ids':[(6,0,line.invoice_line_tax_ids.ids)]
                                            }
                                            factura.sudo().write({'invoice_line_ids':[(0,0,val_line)]})
                                            line.sudo().write({'quantity':line.quantity-1})
                                            break
                                        elif not line.desc_line_ids:
                                            val_line = {
                                            'product_id':line.product_id.id,
                                            'name':line.name,
                                            'account_id':line.account_id.id,
                                            'quantity':1,
                                            'price_unit':line.price_unit,
                                            'invoice_line_tax_ids':[(6,0,line.invoice_line_tax_ids.ids)]
                                            }
                                            factura.sudo().write({'invoice_line_ids':[(0,0,val_line)]})
                                            line.sudo().write({'quantity':line.quantity-1})
                                            break
                                        
                                    elif line.desc_line_ids:
                                        if len(invoice.invoice_line_ids) < len(line.desc_line_ids) + 2:
                                            break
                                        lineas_desc.extend([linea_desc for linea_desc in line.desc_line_ids])
                                        linea = line
                                        break
                                    elif len(invoice.invoice_line_ids) > 1:
                                        linea = line
                                        break
                        
                        invoice.sudo().write({'date': invoice.date})
                        factura.sudo().write({'date': factura.date})
                        factura.sudo().compute_taxes()
                        invoice.sudo().compute_taxes()

                        if linea:
                            linea.sudo().write({'invoice_id': factura.id})
                            for linea_desc in lineas_desc:
                                linea_desc.sudo().write({'invoice_id': factura.id})
                            invoice.sudo().write({'date': invoice.date})
                            factura.sudo().write({'date': factura.date})
                            if invoice.amount_total <= 0:
                                linea.sudo().write({'invoice_id': invoice.id})
                                for linea_desc in lineas_desc:
                                    linea_desc.sudo().write({'invoice_id': invoice.id})
                                invoice.sudo().write({'date': invoice.date})
                                factura.sudo().write({'date': factura.date})
                        factura.sudo().compute_taxes()
                        invoice.sudo().compute_taxes()
                        if factura.amount_total > 0:
                            break
                        
                # Luego del proceso se calculan nuevamente los impuestos
                factura.sudo().compute_taxes()
                hacer_rollback = False
                # Se vuelve a revisar si la factura es incoherente y si es así se agrega un producto comodín
                factura.sudo().compute_taxes()
                _logger.info("Numero de lineas despues de")
                _logger.info(len(factura.invoice_line_ids))
                hacer_rollback = False
                # Se vuelve a revisar si la factura es incoherente y si es así se agrega un producto comodín
                if len(factura.invoice_line_ids) == 0 or factura.amount_total <= 0:
                    _logger.info("despues del segundo if del comodin")
                    if len(comodines) > 0:
                        i = random.randrange(0,len(comodines))
                        valores = {
                            'product_id': comodines[i].id,
                            'name': comodines[i].name,
                            'quantity': 1,
                            'price_unit': roundToLow(comodines[i].lst_price,redondeo),
                            'invoice_line_tax_ids': [(4,tax.id) for tax in comodines[i].taxes_id],
                            'account_id': comodines[i].property_account_income_id.id if comodines[i].property_account_income_id else comodines[i].categ_id.property_account_income_categ_id.id
                        }
                        factura.sudo().write({'invoice_line_ids': [(0,0,valores)]})
                        valor_descontado -= comodines[i].lst_price
                        '''
                        recepcion = False
                        if self.env.user.recepcion_id:
                            recepcion = self.env['stock.location'].search([('recepcion','=',self.env.user.recepcion_id.id)],limit=1)
                        if not recepcion:
                            recepcion = self.env['stock.location'].search([('recepcion','!=',False)],limit=1)
                        if recepcion:
                            valores_move = {
                                'name': comodines[i].name,
                                'product_id': comodines[i].id,
                                'product_uom_qty': 1,
                                'product_uom': comodines[i].uom_id.id,
                                'location_id': recepcion.id,
                                'location_dest_id': self.env.ref('stock.stock_location_customers').id
                            }
                            valores_picking = {
                                'partner_id': factura.partner_id.id,
                                'picking_type_id': self.env.ref('stock.picking_type_out').id,
                                'location_id': recepcion.id,
                                'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                                'move_ids_without_package': [(0,0,valores_move)]
                            }
                            picking = self.env['stock.picking'].create(valores_picking)
                            picking.action_confirm()
                            picking.action_assign()
                            valores_move_line = {
                                'location_id': picking.location_id.id,
                                'location_dest_id': picking.location_dest_id.id,
                                'product_uom_id': comodines[i].uom_id.id,
                                'qty_done': 1
                            }
                            picking.write({'move_line_ids': [(0,0,valores_move_line)]})
                            picking.button_validate()
                            '''
                    else:
                        hacer_rollback = True
                # Se vuelven a calcular los impuestos
                factura.sudo().compute_taxes()
                

                # Si la factura sigue siendo incoherente, se debe hacer un rollback de todas las facturas
                if len(factura.invoice_line_ids) == 0 or factura.amount_total <= 0:
                    hacer_rollback = True
                
                # Si es necesario hacer rollback, se realiza el proceso dependiendo si era un proceso automático o manual (En el automático debe salir un correo de notificación, en el manual simplemente se muestra un Warning)
                if hacer_rollback:
                    if auto:
                        error = True
                        # Rollback
                        valores_rollback = {
                            'tipo': 'facturas',
                            'factura_ids': [(6,0,rollbacks)]
                        }
                        rollback = self.env['mot_validacion.rollback'].create(valores_rollback)
                        rollback.rollback()
                        valoresNotificacion = {
                            'asunto': error_asunto,
                            'descripcion': error_msg + '\n\tNo se pudo reducir la factura ' + number + ' o su estado era incoherente, por lo que se ha realizado un rollback completo \n' + error_end,
                        }
                        self.env['mot_validacion.notificacion'].create(valoresNotificacion)
                        break
                    else:
                        raise Warning('No se pudo reducir la factura ' + number + ' y su estado es incoherente por lo que se ha realizado un rollback completo')
                # Si no era necesario el rollback, se valida la factura y se modifican los pagos
                else:
                    factura.sudo().compute_taxes()
                    _logger.info("factura untaxed")
                    _logger.info(factura.amount_untaxed)
                    _logger.info("factura amount total")
                    _logger.info(factura.amount_total)
                    _logger.info("amount_tax")
                    _logger.info(factura.amount_tax)
                    factura.action_invoice_open()
                    _logger.info("factura estado final")
                    _logger.info(factura.state)
                    
                    for payment in datosFactura[factura]['payments']:
                        _logger.info("Facturas payment estado")
                        _logger.info(factura.state)
                        payment.sudo().write({
                            'amount': factura.amount_total * datosFactura[factura]['payments'][payment],
                            'invoice_ids': [(4,factura.id)]
                        })
                        _logger.info("Facturas payment2 estado")
                        _logger.info(factura.state)
                        _logger.info(payment.amount)
                        _logger.info(factura.amount_total)
                        payment.post()
                    
                    factura.recaudo.sudo().write({
                        'total_pagado': factura.amount_total,
                        'valor_pagado': factura.amount_total
                    })
                    _logger.info("facturas recibo estado")
                    _logger.info(factura.state)
                    for pago in datosFactura[factura]['pagos']:
                        pago.sudo().write({'valor': factura.amount_total * datosFactura[factura]['pagos'][pago]})
                    _logger.info("facturas pago estado")
                    _logger.info(factura.state)
                    # Se elimina toda relación entre la factura y la orden de venta de la que venía
                    if factura.origin:
                        
                        order = self.env['sale.order'].search([('name','=',factura.origin)],limit=1)
                        if order:
                            order.sudo().write({'invoice_ids': [(3,factura.id)]})
                        factura.sudo().write({'origin': ''})
                        _logger.info("facturas if estado")
                        _logger.info(factura.state)
                    
                    _logger.info("Facturas total y cantidad")
                    _logger.info(factura.number)
                    _logger.info(factura.amount_total)
                    _logger.info(len(factura.invoice_line_ids))

                    # Si las metas ya se cumplieron, finalizar el proceso y no modificar más facturas
                    if desc_borr <= 0 and desc_hosp <= 0 and desc_inven <= 0:
                        break
            
            # Se revisa si después del proceso siguen existiendo facturas en valor 0
            facturas_cero = []
            for factura in facturas:
                _logger.info("Facturas Totales en cantidades")
                _logger.info(factura.number)
                _logger.info(factura.amount_total)
                _logger.info(len(factura.invoice_line_ids))
                if factura.amount_total <= 0:
                    if not auto:
                        raise Warning('Ha ocurrido un error en el proceso de validación: La factura ' + factura.number + ' ha quedado en cero y ha sido necesario hacer un rollback completo')
                    facturas_cero.append(factura)
            if auto and len(facturas_cero) > 0:
                error_msg = error_msg + '\n\tNo se pudo completar el proceso debido a que las siguientes facturas han quedado con valor CERO:\n'
                for fac in facturas_cero:
                    error_msg = error_msg + '\t\t- ' + fac.number + '\n'
                error_msg = error_msg + error_end
                error = True
                # Rollback
                valores_rollback = {
                    'tipo': 'facturas',
                    'factura_ids': [(6,0,rollbacks)]
                }
                rollback = self.env['mot_validacion.rollback'].create(valores_rollback)
                rollback.rollback()
                valoresNotificacion = {
                    'asunto': error_asunto,
                    'descripcion': error_msg
                }
                self.env['mot_validacion.notificacion'].create(valoresNotificacion)
            elif len(facturas_cero) > 0:
                error_msg = error_msg + '\n\tNo se pudo completar el proceso debido a que las siguientes facturas han quedado con valor CERO:\n'
                for fac in facturas_cero:
                    error_msg = error_msg + '\t\t- ' + fac.number + '\n'
                raise Warning(error_msg)
            
            # Todas las facturas que fueron procesadas se marcan como validadas
            for factura in facturas_all:
                if not error:
                    factura.sudo().write({'validada': True})

            # Se registra el log de la reducción
            valores_log_reduccion = {
                'fecha': log.fecha,
                'log_id': log.id,
                'reduc_max': valor_descontado,
                'reduc_param': meta_desc
            }
            self.env['mot_validacion.log.reduccion'].sudo().create(valores_log_reduccion)
        _logger.info("LLEGUE AL METODO part pte final if")
        # Se termina de registrar el histórico del proceso
        if error:
            log.sudo().write({
                'resultado': 'error',
                'doc_ids': [(4,factura.id) for factura in facturas]
            })
        else:
            log.sudo().write({
                'resultado': 'ok',
                'doc_ids': [(4,factura.id) for factura in facturas],
                'rollback_ids': [(6,0,rollbacks)]
            })

        # Finaliza el proceso de reducción
        return {
            'name': 'Histórico',
            'view_mode': 'tree,form',
            'res_model': 'mot_validacion.log',
            'type': 'ir.actions.act_window',
            'target':'main'
        }

    @api.model
    def auto(self, fecha_inicial, fecha_final):
        
        val = self.create({
            'fecha_inicial': fecha_inicial,
            'fecha_final': fecha_final,
            'auto': True
        })
        val.validar()
        _logger.info("LLEGUE AL VALIDAR")
        

    @api.multi
    def send_ftp(self,fecha,**kw):
        servers = self.env['mot_validacion.ftpserver'].search([])
        for server in servers:
            FTP_HOST = server.host
            FTP_USER = server.user
            FTP_PASS = server.passwd
        
            ftp = ftplib.FTP(FTP_HOST, FTP_USER, FTP_PASS)
            ftp.encoding = "utf-8"
            if server.directory or server.directory != '':
                ftp.cwd(server.directory)

            for arch in kw:
                nom_arch = fecha.strftime('%Y-%m-%d') + '.pdf'
                f = open('/tmp/' + nom_arch,'wb')
                f.write(arch)
                f.close
                f = open('/tmp/' + nom_arch,'rb')
                ftp.storbinary("STOR " + nom_arch,f)
                f.close