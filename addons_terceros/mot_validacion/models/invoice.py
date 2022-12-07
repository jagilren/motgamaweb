from odoo import models, fields, api

from odoo.exceptions import Warning

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    validada = fields.Boolean(string="Validada",default=False)
    consumo = fields.Boolean(string="Consumo",default=False)

    @api.multi
    def registro_anomalia(self):
        self.ensure_one()
        if not self.env.ref('mot_validacion.parametro_FACTURA_ANOMALIA').sudo().valor_boolean:
            raise Warning('La opción de marcar facturas con anomalías está deshabilitada, contacte al administrador')
        elif self.validada:
            raise Warning('Esta factura no se puede marcar como anomalía')
        else:
            return super().registro_anomalia()

    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
        rollback = self.env['mot_validacion.invoice'].sudo().search([('invoice_id','=',invoice.id)],limit=1)
        if invoice.validada and rollback:
            raise Warning('Se deberá hacer un rollback en la llave para poder generar una rectificativa a esta factura')
        return super()._prepare_refund(invoice,date_invoice=date_invoice,date=date,description=description,journal_id=journal_id)

class InvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    # Ya no se usa
    desc_line_id = fields.Many2one(string='Línea de descuento',comodel_name='account.invoice.line')
    # Si se usa
    desc_line_ids = fields.One2many(string="Líneas de descuento",comodel_name='account.invoice.line',inverse_name="base_line")

class InvoiceRollback(models.Model):
    _name = 'mot_validacion.invoice'
    _description = 'Factura Rollback'
    _rec_name = 'invoice_id'

    invoice_id = fields.Many2one(string='Factura',comodel_name='account.invoice')
    fecha_factura = fields.Date(string='Fecha')
    factura_creada = fields.Datetime(string="Fecha de creación")
    cliente = fields.Many2one(string='Cliente',comodel_name='res.partner')
    ingreso = fields.Datetime(string="Ingreso")
    salida = fields.Datetime(string="Salida")
    lineas = fields.One2many(string="Líneas",comodel_name="mot_validacion.invoice.line",inverse_name="invoice_id")
    base = fields.Float(string="Base imponible")
    impuestos = fields.Float(string="Impuestos")
    total = fields.Float(string="Total")
    pagos = fields.One2many(string="Pagos",comodel_name="mot_validacion.invoice.payment",inverse_name='invoice_id')
    recibo = fields.Many2one(string="Recibo de pago",comodel_name="mot_validacion.invoice.recibo")
    doc = fields.Char(string="Documento origen")
    habitacion_id = fields.Many2one(string='Habitación',comodel_name='motgama.flujohabitacion')

    @api.model
    def deleteall(self):
        records = self.env['mot_validacion.invoice.recibo.pago'].search([])
        for record in records:
            record.sudo().unlink()
        records = self.env['mot_validacion.invoice.recibo'].search([])
        for record in records:
            record.sudo().unlink()
        records = self.env['mot_validacion.invoice.payment'].search([])
        for record in records:
            record.sudo().unlink()
        records = self.env['mot_validacion.invoice.line'].search([])
        for record in records:
            record.sudo().unlink()
        records = self.env['mot_validacion.invoice'].search([])
        for record in records:
            record.sudo().unlink()

class InvoiceRollbackLine(models.Model):
    _name = 'mot_validacion.invoice.line'
    _description = 'Línea Factura Rollback'

    invoice_id = fields.Many2one(string="Factura",comodel_name="mot_validacion.invoice",ondelete="cascade")
    line_id = fields.Many2one(string='Línea de factura',comodel_name='account.invoice.line')
    producto = fields.Many2one(string="Producto",comodel_name="product.product")
    descripcion = fields.Char(string="Descripción")
    cantidad = fields.Float(string="Cantidad")
    precio = fields.Float(string="Precio")
    impuestos = fields.Many2many(string="Impuestos",comodel_name="account.tax")
    subtotal = fields.Float(string="Subtotal")

class InvoicePayment(models.Model):
    _name = 'mot_validacion.invoice.payment'
    _description = 'Pago Factura Rollback'
    _rec_name = 'payment_id'

    invoice_id = fields.Many2one(string="Factura",comodel_name="mot_validacion.invoice",ondelete="cascade")
    payment_id = fields.Many2one(string="Pago",comodel_name="account.payment")
    metodo = fields.Many2one(string="Método de pago",comodel_name="account.journal")
    importe = fields.Float(string="Importe")
    
class InvoiceRecibo(models.Model):
    _name = 'mot_validacion.invoice.recibo'
    _description = 'Recibo Factura Rollback'
    _rec_name = 'recaudo'

    invoice_id = fields.Many2one(string="Factura",comodel_name="mot_valicacion.invoice",ondelete="cascade")
    recaudo = fields.Many2one(string="Recaudo",comodel_name="motgama.recaudo")
    movimiento_id = fields.Many2one(string="Movimiento",comodel_name="motgama.movimiento")
    habitacion_id = fields.Many2one(string="Habitación",comodel_name="motgama.flujohabitacion")
    pagos = fields.One2many(string="Pagos",comodel_name="mot_validacion.invoice.recibo.pago",inverse_name="recibo_id")
    total = fields.Float(string="Total")
    pagado = fields.Float(string="Pagado")

class InvoiceReciboPago(models.Model):
    _name = 'mot_validacion.invoice.recibo.pago'
    _description = 'Pago Recibo Factura Rollback'
    _rec_name = 'pago'

    pago = fields.Many2one(string="Pago",comodel_name="motgama.pago")
    recibo_id = fields.Many2one(string="Recibo",comodel_name="mot_validacion.invoice.recibo",ondelete="cascade")
    mediopago = fields.Many2one(string="Medio de pago",comodel_name="motgama.mediopago")
    valor = fields.Float(string="Valor pagado")