from odoo import fields, models, api
from odoo.exceptions import Warning
from datetime import datetime, timedelta
import logging, os, shutil, base64
_logger = logging.getLogger(__name__)
import socket

class WizardReporteVentas(models.TransientModel):
    _name = 'motgama.wizard.reporteventas'
    _description = 'Wizard del Reporte de Ventas'

    tipo_reporte = fields.Selection(string='Tipo de reporte',selection=[('fecha','Por fecha'),('documento','Por factura')],default='fecha')

    fecha_inicial = fields.Datetime(string='Fecha inicial')
    fecha_final = fields.Datetime(string='Fecha final')

    doc_inicial = fields.Many2one(string='Factura inicial',comodel_name='account.invoice')
    doc_final = fields.Many2one(string='Factura final',comodel_name='account.invoice')

    es_manual = fields.Boolean(string='Es manual',default=True)

    company = fields.Char(string='Company', default=lambda self:self.env['res.company']._company_default_get('account.invoice').name)

    primer_factura=0
    ultima_factura=0

    @api.model
    def check_permiso(self):
        if self.env.ref('motgama.motgama_informe_diariovtas') not in self.env.user.permisos:
            raise Warning('No tiene permitido generar este informe')
        
        return {
            'type': 'ir.actions.act_window',
            'name': "Reporte de ventas",
            'res_model': "motgama.wizard.reporteventas",
            'view_mode': "form",
            'target': "new"
        }

    @api.multi
    def get_report(self, numeroReporte=""):

        _logger.info("Este numero de reporte es el que esta llegando antes del condicional:"+str(numeroReporte))
        
        self.ensure_one()
        _logger.info("Numero de reporte en get report "+ str(numeroReporte))
        reporte = self.env['motgama.reporteventas'].search([])
        for x in reporte:
            x.unlink()

        if self.tipo_reporte == 'fecha':
            facturas = self.env['account.invoice'].search([('type','in',['out_invoice','out_refund']),('state','in',['open','paid']),('fecha','<=',self.fecha_final),('fecha','>=',self.fecha_inicial)], order='name asc, fecha asc')
        elif self.tipo_reporte == 'documento':
            facturas = self.env['account.invoice'].search([('type','in',['out_invoice','out_refund']),('state','in',['open','paid']),('id','<=',self.doc_final.id),('id','>=',self.doc_inicial.id)], order='name asc, fecha asc')
        else:
            facturas = []

            
            
        if not facturas:
            raise Warning('No hay datos que mostrar')
        _logger.info("Facturas Variable:"+str(facturas))
        for factura in facturas:
            valores = {
                'factura': factura.id,
                'fecha': factura.fecha,
                'fac': factura.number,
                'cliente': factura.partner_id.name,
                'habitacion': factura.habitacion_id.codigo or '',
                'valor': factura.amount_total,
                'usuario': factura.usuario_id.name if factura.usuario_id else factura.create_uid.name,
                'numero_reporte':numeroReporte,
                'fecha_salida':factura.liquidafecha,
                'company':self.company
                
            }
            if self.tipo_reporte == 'fecha':
                valores.update({
                    'fecha_inicial': self.fecha_inicial,
                    'fecha_final': self.fecha_final,
                    'doc_inicial': False,
                    'doc_final': False
                })
            elif self.tipo_reporte == 'documento':
                valores.update({
                    'doc_inicial': self.doc_inicial.name,
                    'doc_final': self.doc_final.name,
                    'fecha_inicial': False,
                    'fecha_final': False
                })
            primer_factura = facturas[0].id
            medios = []
            for pago in factura.recaudo.pagos:
                if pago.mediopago.tipo == 'prenda' and factura.prenda_id and factura.prenda_id.recaudo:
                    for pago1 in factura.prenda_id.recaudo.pagos:
                        if pago1.mediopago not in medios:
                            medios.append(pago1.mediopago)
                elif pago.mediopago.tipo == 'abono' and factura.movimiento_id:
                    for recaudo in factura.movimiento_id.recaudo_ids:
                        if recaudo.estado == 'anulado' or recaudo == factura.recaudo:
                            continue
                        for pago2 in recaudo.pagos:
                            if pago2.mediopago in ['prenda','abono']:
                                continue
                            if pago2.mediopago not in medios:
                                medios.append(pago2.mediopago)
                elif pago.mediopago in medios:
                    continue
                else:
                    medios.append(pago.mediopago)
            
            if len(medios) == 1:
                valores['medio_pago'] = medios[0].nombre
            else:
                med = ''
                for medio in medios:
                    if med != '':
                        med += '-'
                    cod = medio.cod if medio.cod else medio.nombre[:2].upper()
                    med += cod
                valores['medio_pago'] = med
            if factura.type == 'out_refund':
                valores['medio_pago'] = 'N/A'
            nuevo = self.env['motgama.reporteventas'].create(valores)
            if not nuevo:
                raise Warning('No fue posible generar el reporte')

        if self.es_manual:
            return {
                'name': 'Reporte de ventas',
                'view_mode':'tree',
                'view_id': self.env.ref('motgama.tree_reporte_ventas').id,
                'res_model': 'motgama.reporteventas',
                'type': 'ir.actions.act_window',
                'target': 'main'
            }
        else:
            return True


   

class MotgamaReporteVentas(models.TransientModel):
    _name = 'motgama.reporteventas'
    _description = 'Reporte de Ventas'

    factura = fields.Many2one(string='Factura',comodel_name='account.invoice')

    fecha_inicial = fields.Datetime(string="Fecha inicial")
    fecha_final = fields.Datetime(string="Fecha final")
    doc_inicial = fields.Char(string='Factura inicial')
    doc_final = fields.Char(string='Factura final')
    #este lo agregue
    numero_reporte = fields.Char(string='Numero reporte')
    fecha_salida = fields.Datetime(string="Fecha Salida")
    fecha = fields.Datetime(string='Fecha')
    fac = fields.Char(string='Factura')
    cliente = fields.Char(string='Cliente')
    habitacion = fields.Char(string='Habitación')
    valor = fields.Float(string='Valor Total')
    medio_pago = fields.Char(string='Medio de pago')
    usuario = fields.Char(string='Usuario')
    company = fields.Char(string='Company')

class PDFReporteVentas(models.AbstractModel):
    _name = 'report.motgama.reporteventas'

    @api.model
    def _get_report_values(self,docids,data=None):
        docs = self.env['motgama.reporteventas'].browse(docids)
        total = 0
        prods = {}
        facs = {}
        medios = {}
        imps = {}
        c_fact = 0
        c_rect = 0
        valor_notas_credito = 0
        valor_facturas = 0
        val_bool = False
        val_bool_fac = False
        primer_nota_credito = ""
        ultima_nota_credito = ""
        primer_factura = ""
        ultima_factura = ""
       
        for doc in docs:
            _logger.info("EL NUMERO DE REPORTE ES:"+doc.numero_reporte)
            factor = 0
            
            if doc.factura.type == 'out_refund':
                c_rect += 1
                factor = -1
                valor_notas_credito += doc.factura.amount_total
                if val_bool==False:
                    primer_nota_credito = doc.fac
                    val_bool = True
                else:
                    ultima_nota_credito = doc.fac
            elif doc.factura.type == 'out_invoice':
                c_fact += 1
                factor = 1
                valor_facturas += doc.factura.amount_total
                if val_bool_fac==False:
                    primer_factura = doc.fac
                    val_bool_fac = True
                else:
                   ultima_factura = doc.fac
                

           

            total += doc.valor * factor

            for linea in doc.factura.invoice_line_ids:
                valor = linea.price_unit * linea.quantity * factor
                if doc.factura in facs:
                    if linea.product_id.categ_id in facs[doc.factura]:
                        facs[doc.factura][linea.product_id.categ_id]+=valor
                    else:
                         facs[doc.factura][linea.product_id.categ_id]=valor
                else:
                    facs[doc.factura]={linea.product_id.categ_id:valor}
                        
                if linea.product_id.categ_id in prods:
                    if docs[0].numero_reporte == "2":
                        prods[linea.product_id.categ_id] += valor / (1 + linea.product_id.taxes_id.amount/ 100) 
                    elif docs[0].numero_reporte == "1":
                        prods[linea.product_id.categ_id] += valor
                    else:
                        prods[linea.product_id.categ_id] += valor /(1 + linea.product_id.taxes_id.amount/ 100)
                else:
                    if docs[0].numero_reporte == "2":
                        prods[linea.product_id.categ_id] = valor / (1 + linea.product_id.taxes_id.amount/ 100)
                    elif docs[0].numero_reporte == "1":
                        prods[linea.product_id.categ_id] = valor
                    else:
                        prods[linea.product_id.categ_id] = valor / (1 + linea.product_id.taxes_id.amount/ 100)

               
            
            
            


            if doc.factura.recaudo.estado != 'anulado':
                for pago in doc.factura.recaudo.pagos:
                    if pago.mediopago.tipo == 'prenda' and doc.factura.prenda_id and doc.factura.prenda_id.recaudo:
                        for pago1 in doc.factura.prenda_id.recaudo.pagos:
                            if pago1.mediopago in medios:
                                medios[pago1.mediopago] += pago1.valor
                            else:
                                medios[pago1.mediopago] = pago1.valor
                    elif pago.mediopago.tipo == 'abono' and doc.factura.movimiento_id:
                        for recaudo in doc.factura.movimiento_id.recaudo_ids:
                            if recaudo.estado == 'anulado' or recaudo == doc.factura.recaudo:
                                continue
                            for pago2 in recaudo.pagos:
                                if pago2.mediopago in ['prenda','abono']:
                                    continue
                                if pago2.mediopago in medios:
                                    medios[pago2.mediopago] += pago2.valor
                                else:
                                    medios[pago2.mediopago] = pago2.valor
                    elif pago.mediopago in medios:
                        medios[pago.mediopago] += pago.valor
                    else:
                        medios[pago.mediopago] = pago.valor
            
            for linea_impuesto in doc.factura.tax_line_ids:
                if linea_impuesto.tax_id in imps:
                    imps[linea_impuesto.tax_id]['total'] += linea_impuesto.amount_total * factor
                    imps[linea_impuesto.tax_id]['base'] += linea_impuesto.base * factor

                else:
                    imps[linea_impuesto.tax_id] = {"total": linea_impuesto.amount_total * factor, "base": linea_impuesto.base * factor}
                
                linea_impuesto.tax_id
                    
            
        if ultima_factura == "":
                    ultima_factura = primer_factura
        total_impuestos_base=0
        valor_impuestos_total = 0

        for prod in prods:
            prods[prod] = "$ {:0,.2f}".format(prods[prod]).replace(',','¿').replace('.',',').replace('¿','.')
        for medio in medios:
            medios[medio] = "$ {:0,.2f}".format(medios[medio]).replace(',','¿').replace('.',',').replace('¿','.')
        for imp in imps:
            valor = imps[imp]['base']
            valor_total = imps[imp]['total']
            total_impuestos_base += valor
            valor_impuestos_total += valor_total
        for imp in imps:
            imps[imp]['total']= "$ {:0,.2f}".format(imps[imp]['total']).replace(',','¿').replace('.',',').replace('¿','.')
            imps[imp]['base'] = "$ {:0,.2f}".format(imps[imp]['base']).replace(',','¿').replace('.',',').replace('¿','.')
            
        
        total_impuestos_base = "$ {:0,.2f}".format(total_impuestos_base).replace(',','¿').replace('.',',').replace('¿','.')
        valor_impuestos_total = "$ {:0,.2f}".format(valor_impuestos_total).replace(',','¿').replace('.',',').replace('¿','.')
        valor_notas_credito = "$ {:0,.2f}".format(valor_notas_credito).replace(',','¿').replace('.',',').replace('¿','.')
        valor_facturas = "$ {:0,.2f}".format(valor_facturas).replace(',','¿').replace('.',',').replace('¿','.')
         
        _logger.info("Variables prods" + str(prods))
        _logger.info("Variables medios" + str(medios))
        _logger.info("Variables imps" + str(imps))
        _logger.info("Variables docs" + str(docs))
        _logger.info("Variables docs" + str(facs))
        terminal = socket.gethostname()
        fecha_generacion=datetime.now() - timedelta(hours=5)
        alias_impuesto = {

        }
        for alias in self.env.ref('mot_validacion.parametro_ALIAS_IMPUESTO').alias_impuestos:
            alias_impuesto[alias.impuesto_id]=alias.alias

            



        
        
       
        
           

        
        return {
            'primer_nota_credito':primer_nota_credito,
            'ultima_nota_credito':ultima_nota_credito,
            'valor_notas_credito':valor_notas_credito,
            'alias_impuesto':alias_impuesto,
            'valor_factura':valor_facturas,
            'total_facturas': c_fact,
            'total_notas_credito': c_rect,
            'valor_impuestos_total': valor_impuestos_total,
            'total_impuestos_base':total_impuestos_base,
            'terminal': terminal,
            'fecha_generacion':fecha_generacion,
            'facs':facs,
            'numero_reporte': docs[0].numero_reporte,
            'primer_factura': primer_factura,
            'ultima_factura': ultima_factura,
            'razon_social': self.env['res.company']._company_default_get('account.invoice').company_registry,
            'company': docs[0].company,
            'logo': self.env['res.company']._company_default_get('account.invoice').logo,
            'nit': self.env['res.company']._company_default_get('account.invoice').vat,
            'sucursal': self.env['motgama.sucursal'].search([],limit=1),
            'docs': docs,
            'rectificativas':c_rect,
            'count': {'facturas':c_fact,'rectificativas':c_rect},
            'total': "{:0,.2f}".format(total).replace(',','¿').replace('.',',').replace('¿','.'),
            'prods': prods,
            'medios': medios,
            'fecha_inicial': docs[0].fecha_inicial - timedelta(hours=5),
            'fecha_final': docs[0].fecha_final  - timedelta(hours=5),
            'doc_inicial': docs[0].doc_inicial,
            'doc_final': docs[0].doc_final,
            'imps': imps
        }