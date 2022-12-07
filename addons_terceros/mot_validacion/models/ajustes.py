from odoo import models, fields, api

class WizardAjustes(models.TransientModel):
    _name = 'mot_validacion.wizard.ajustes'
    _description = 'Wizard Ajustes'

    reduc_porcentaje = fields.Integer(string="Porcentaje de Reducción", default=lambda self: self._get_reduccion())
    reduc_hosp = fields.Many2many(string="Reducción por hospedaje", comodel_name="mot_validacion.wizard.ajustes.hosp", relation="mot_validacion_rel_ajustes_hosp", default=lambda self: self._get_reduc_hosp())
    reduc_inven = fields.Many2many(string="Reducción por inventario", comodel_name="mot_validacion.wizard.ajustes.inven", relation="mot_validacion_rel_ajustes_inven", default=lambda self: self._get_reduc_inven())

    estado_proceso = fields.Selection(string="Estado del proceso",selection=[('iniciado','Iniciado'),('detenido','Detenido')],default=lambda self: self._get_estado())

    @api.model
    def _get_reduccion(self):
        return self.env.ref('mot_validacion.parametro_REDUCCION').valor_int

    @api.model
    def _get_reduc_hosp(self):
        valores_tipos = []
        for linea in self.env.ref('mot_validacion.parametro_REDUCCIONxHOSPEDAJE').reduc_hospedaje:
            valores = {
                'tipo_id': linea.tipo_id.id,
                'porcentaje': linea.porcentaje
            }
            valores_tipos.append(valores)
        return [(0,0,valores) for valores in valores_tipos] if len(valores_tipos) > 0 else False

    @api.model
    def _get_reduc_inven(self):
        valores_inven = []
        for linea in self.env.ref('mot_validacion.parametro_REDUCCIONxINVENTARIO').reduc_inventario:
            valores = {
                'categ_id': linea.categ_id,
                'porcentaje': linea.porcentaje
            }
            valores_inven.append(valores)
        return [(0,0,valores) for valores in valores_inven] if len(valores_inven) > 0 else False

    @api.model
    def _get_estado(self):
        if self.env.ref('mot_validacion.proceso_reduccion').active:
            return 'iniciado'
        else:
            return 'detenido'

    @api.multi
    def editar(self):
        self.ensure_one()

        if self.reduc_porcentaje != self.env.ref('mot_validacion.parametro_REDUCCION').valor_int:
            self.env.ref('mot_validacion.parametro_REDUCCION').sudo().write({'valor_int': self.reduc_porcentaje})

        for linea in self.reduc_hosp:
            no_hay = True
            for line in self.env.ref('mot_validacion.parametro_REDUCCIONxHOSPEDAJE').reduc_hospedaje:
                if line.tipo_id == linea.tipo_id and line.porcentaje == linea.porcentaje:
                    no_hay = False
                elif line.tipo_id == linea.tipo_id and line.porcentaje != linea.porcentaje:
                    line.sudo().write({'porcentaje': linea.porcentaje})
                    no_hay = False
            if no_hay:
                valores = {
                    'tipo_id': tipo_id,
                    'porcentaje': porcentaje
                }
                self.env.ref('mot_validacion.parametro_REDUCCIONxHOSPEDAJE').sudo().write({'reduc_hospedaje': [(0,0,valores)]})

    @api.multi
    def start(self):
        self.ensure_one()

        cron = self.env.ref('mot_validacion.proceso_reduccion')
        if not cron.active:
            cron.sudo().write({'active':True})

    @api.multi
    def stop(self):
        self.ensure_one()

        cron = self.env.ref('mot_validacion.proceso_reduccion')
        if cron.active:
            cron.sudo().write({'active':False})

    @api.multi
    def panic(self):
        self.ensure_one()

        self.env['mot_validacion.invoice'].deleteall()
        self.env['mot_validacion.log'].deleteall()

class WizardAjustesHospedaje(models.TransientModel):
    _name = 'mot_validacion.wizard.ajustes.hosp'
    _description = 'Wizard Ajustes Hospedaje'

    tipo_id = fields.Many2one(string="Tipo de habitación",comodel_name="motgama.tipo")
    porcentaje = fields.Integer(string="Porcentaje")

class WizardAjustesInventario(models.TransientModel):
    _name = 'mot_validacion.wizard.ajustes.inven'
    _description = 'Wizard Ajustes Inventario'

    categ_id = fields.Many2one(string='Categoría',comodel_name="product.category")
    porcentaje = fields.Integer(string="Porcentaje")