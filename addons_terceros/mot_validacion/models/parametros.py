from odoo import models, fields, api

from datetime import datetime, timedelta

class ParametroValidacion(models.Model):
    _name = 'mot_validacion.parametro'
    _description = 'Parámetros del módulo de validación'
    _rec_name = 'nombre'

    nombre = fields.Char(string='Nombre') 
    descripcion = fields.Text(string='Descripción')

    # BORRABLES, COMODIN, CATEGORIA_INTERCAMBIABLE, CATEGORIA_NO_ORPHAN
    prod_categ_ids = fields.Many2many(string="Categorías", comodel_name="product.category")

    # BORRABLES, COMODIN
    producto_ids = fields.Many2many(string='Productos', comodel_name="product.product")

    # MEDIOS_BORRABLES
    mediopago_ids = fields.Many2many(string="Medios de pago",comodel_name='motgama.mediopago')

    # FACTURA_ANOMALIA, DETALLE_DCTO_FACT_HOSPEDAJE, DETALLE_DCTO_FACT_INVENTARIOS
    valor_boolean = fields.Boolean(string="Si/No")

    # %REDUCCIONxHOSPEDAJE
    reduc_hospedaje = fields.One2many(string="Reducción por hospedaje",comodel_name="mot_validacion.parametro.reduchospedaje",inverse_name="parametro_id")

    # %REDUCCIONxINVENTARIO
    reduc_inventario = fields.One2many(string="Reducción por categorías de inventario",comodel_name="mot_validacion.parametro.reducinventario",inverse_name="parametro_id")

    # %PONDERACIONxDESCONTABLE
    borrables = fields.Integer(string="BORRABLES")
    hospedaje = fields.Integer(string="HOSPEDAJE")
    inventario = fields.Integer(string="INVENTARIO")
    techo_borrables = fields.Integer(string="Techo Borrables")
    techo_hospedaje = fields.Integer(string="Techo Hospedaje")
    techo_inventario = fields.Integer(string="Techo Inventario")

    # HORA_INICIO_PROCESO, RAZON_ALIAS, FRASE_OVERRIDE_HAB, EMAIL_ALERTAS
    valor_char = fields.Char(string="Valor")

    # PERIODICIDAD_PROCESO, ROLLBACK_MAX, STORE_ROLLBACK
    valor_float = fields.Float(string="Valor ")

    # %REDUCCION, PERIOD_DEL_ROLLBACK
    valor_int = fields.Integer(string="Valor   ")

    # %REDUCCION
    porc_error = fields.Float(string="Porcentaje aceptable de error",help="Define el porcentaje que será aceptable de la diferencia entre el Landvalue y la suma de los aportes de las facturas, esto permite definir un valor aceptable al aumentar la ponderación hasta su techo")
    paso_reduc = fields.Integer(string="Incremento de porcentajes de reducción")

    # ALIAS_IMPUESTO
    alias_impuestos = fields.One2many(string="Alias para impuestos",comodel_name="mot_validacion.parametro.aliasimpuesto",inverse_name="parametro_id")

    # ALIAS_CATEGORIA
    alias_categorias = fields.One2many(string="Alias para categorías",comodel_name="mot_validacion.parametro.aliascateg",inverse_name="parametro_id")

    # PROD_DESC
    prod_desc_hosp = fields.Many2one(string="Producto de descuento para hospedaje",comodel_name="product.product")
    prod_desc_inven = fields.Many2one(string="Producto de descuento para inventario",comodel_name="product.product")

    # REDONDEA
    redondeo = fields.Selection(string="Redondeo",selection=[('no','Sin redondeo'),('cent','A centenas'),('mil','A miles')],default="no")

    @api.multi
    def write(self,values):
        if self.id == self.env.ref('mot_validacion.parametro_HORA_INICIO_PROCESO').id and 'valor_char' in values:
            hoy = fields.Datetime.now()
            h_ini = datetime.strptime(values['valor_char'],"%H:%M")
            fecha = datetime(hoy.year,hoy.month,hoy.day,h_ini.hour,h_ini.minute,0,0) + timedelta(hours=5)
            self.env.ref('mot_validacion.proceso_reduccion').sudo().write({
                'nextcall': fecha if datetime.now() < fecha else fecha + timedelta(days=1)
            })
        if self.id == self.env.ref('mot_validacion.parametro_PERIODICIDAD_PROCESO').id and 'valor_float' in values:
            horas = 24.0 * values['valor_float']
            self.env.ref('mot_validacion.proceso_reduccion').sudo().write({
                'interval_number': round(horas),
                'interval_type': 'hours'
            })
        if self.id == self.env.ref('mot_validacion.parametro_PERIOD_DEL_ROLLBACK').id and 'valor_float' in values:
            self.env.ref('mot_validacion.proceso_store_rollback').sudo().write({
                'interval_number': round(values['valor_float']),
                'interval_type': 'hours'
            })
        return super().write(values)

class ParametroReducHospedaje(models.Model):
    _name = 'mot_validacion.parametro.reduchospedaje'
    _description = 'Parámetro Reducción x Hospedaje'

    parametro_id = fields.Many2one(string="Parámetro",comodel_name="mot_validacion.parametro")
    tipo_id = fields.Many2one(string="Tipo de habitación",comodel_name="motgama.tipo")
    porcentaje = fields.Integer(string="Porcentaje")
    sequence = fields.Integer(string="Secuencia")

class ParametroReducInventario(models.Model):
    _name = 'mot_validacion.parametro.reducinventario'
    _description = 'Parámetro Reducción x Inventario'

    parametro_id = fields.Many2one(string="Parámetro",comodel_name="mot_validacion.parametro")
    categ_id = fields.Many2one(string="Categoría de producto",comodel_name="product.category")
    porcentaje = fields.Integer(string="Porcentaje")
    sequence = fields.Integer(string="Secuencia")

class ParametroAliasImpuesto(models.Model):
    _name = 'mot_validacion.parametro.aliasimpuesto'
    _description = 'Parámetro Alias de Impuesto'

    parametro_id = fields.Many2one(string="Parámetro",comodel_name="mot_validacion.parametro")
    impuesto_id = fields.Many2one(string="Impuesto",comodel_name="account.tax")
    alias = fields.Char(string="Alias")

class ParametroAliasCategoria(models.Model):
    _name = 'mot_validacion.parametro.aliascateg'
    _description = 'Parámetro Alias de Categoría'

    parametro_id = fields.Many2one(string="Parámetro",comodel_name="mot_validacion.parametro")
    categ_id = fields.Many2one(string="Categoría",comodel_name="product.category")
    alias = fields.Char(string="Alias")