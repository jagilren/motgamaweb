from odoo import models, fields, api

class MotgamaReporteVentas(models.TransientModel):
    _inherit = 'motgama.reporteventas'

    @api.model
    def create(self, values):
        fac = self.env['account.invoice'].search([('number','=',rec.fac)],limit=1)
        if fac.consumo:
            values['habitacion'] = self.env.ref('mot_validacion.parametro_FRASE_OVERRIDE_HAB').valor_char
        return super().create(values)

class MotgamaWizardReporteVentas(models.TransientModel):
    _inherit = 'motgama.wizard.reporteventas'

    @api.multi
    def get_report(self):
        reporte = self.env['mot_validacion.report'].search([])
        for x in reporte:
            x.unlink()
        b = super().get_report()
        ventas = self.env['motgama.reporteventas'].search([])
        for x in ventas:
            valores = {
                'factura': x.factura.id if x.factura else False,
                'fecha_inicial': x.fecha_inicial,
                'fecha_final': x.fecha_final,
                'doc_inicial': x.doc_inicial,
                'doc_final': x.doc_final,
                'fecha': x.fecha,
                'fac': x.fac,
                'cliente': x.cliente,
                'habitacion': x.habitacion,
                'valor': x.valor,
                'medio_pago': x.medio_pago,
                'usuario': x.usuario
            }
            self.env['mot_validacion.report'].create(valores)
        return b

class ReporteIngresos(models.TransientModel):
    _name = 'mot_validacion.report'
    _inherit = 'motgama.reporteventas'
    _description = 'Reporte de Ingresos'

    """
    factura = fields.Many2one(string='Factura',comodel_name='account.invoice')

    fecha_inicial = fields.Datetime(string="Fecha inicial")
    fecha_final = fields.Datetime(string="Fecha final")
    doc_inicial = fields.Char(string='Factura inicial')
    doc_final = fields.Char(string='Factura final')

    fecha = fields.Datetime(string='Fecha')
    fac = fields.Char(string='Factura')
    cliente = fields.Char(string='Cliente')
    habitacion = fields.Char(string='Habitación')
    valor = fields.Float(string='Valor Total')
    medio_pago = fields.Char(string='Medio de pago')
    usuario = fields.Char(string='Usuario') 
    """

class PDFReporteIngresos(models.AbstractModel):
    _name = 'report.mot_validacion.reporte_ingresos'

    @api.model
    def _get_report_values(self,docids,data=None):
        docs = self.env['motgama.reporteventas'].browse(docids)

        razon = self.env.ref('mot_validacion.parametro_RAZON_ALIAS').valor_char
        categ_alias = {}
        for categ in self.env.ref('mot_validacion.parametro_ALIAS_CATEGORIA').alias_categorias:
            categ_alias.update({categ.categ_id:alias})
        imp_alias = {}
        for imp in self.env.ref('mot_validacion.parametro_ALIAS_IMPUESTO').alias_impuestos:
            imp_alias.update({imp.impuesto_id:imp.alias})

        total = 0
        prods = {}
        medios = {}
        imps = {}
        for doc in docs:
            total += doc.valor

            for linea in doc.factura.invoice_line_ids:
                if linea.product_id.categ_id in categ_alias:
                    categ = categ_alias[linea.product_id.categ_id]
                else:
                    categ = "Desconocido"
                if categ in prods:
                    prods[categ] += linea.price_unit * linea.quantity
                else:
                    prods[categ] = linea.price_unit * linea.quantity

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
                if linea_impuesto.tax_id in imp_alias:
                    imp = imp_alias[linea_impuesto.tax_id]
                else:
                    imp = "Desconocido"
                if linea_impuesto.tax_id in imps:
                    imps[imp] += linea_impuesto.amount_total
                else:
                    imps[imp] = linea_impuesto.amount_total

        for prod in prods:
            prods[prod] = "$ {:0,.2f}".format(prods[prod]).replace(',','¿').replace('.',',').replace('¿','.')
        for medio in medios:
            medios[medio] = "$ {:0,.2f}".format(medios[medio]).replace(',','¿').replace('.',',').replace('¿','.')
        for imp in imps:
            imps[imp] = "$ {:0,.2f}".format(imps[imp]).replace(',','¿').replace('.',',').replace('¿','.')

        return {
            'docs': docs,
            'count': len(docs),
            'total': "{:0,.2f}".format(total).replace(',','¿').replace('.',',').replace('¿','.'),
            'prods': prods,
            'medios': medios,
            'imps': imps,
            'razon_alias': razon
        }