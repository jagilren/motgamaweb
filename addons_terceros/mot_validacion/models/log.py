from odoo import models, fields, api

class Log(models.Model):
    _name = 'mot_validacion.log'
    _description = 'Log'
    _rec_name = 'fecha'
    _order = 'fecha desc'

    active = fields.Boolean(string="Activo",default=True)
    fecha = fields.Datetime(string="Fecha de ejecución")
    fecha_inicial = fields.Datetime(string="Fecha inicial")
    fecha_final = fields.Datetime(string="Fecha final")
    proceso = fields.Selection(string="Proceso realizado",selection=[('validacion','Validación'),('rollback','Rollback')])
    resultado = fields.Selection(string="Resultado",selection=[('ok','Correcto'),('proceso','En proceso'),('error','Error')])
    doc_ids = fields.Many2many(string="Documentos procesados",comodel_name="account.invoice")
    rollback_ids = fields.Many2many(string="Documentos disponibles para Rollback",comodel_name="mot_validacion.invoice")
    auto = fields.Boolean(string="Automático",default=False)

    @api.multi
    def panic(self):
        self.env['mot_validacion.invoice'].deleteall()
        self.env['mot_validacion.log'].deleteall()

    @api.model
    def deleteall(self):
        regs = self.env['mot_validacion.log'].search([])
        for reg in regs:
            reg.sudo().write({'active': False})
        
        return {
            'name': 'Histórico',
            'view_mode': 'tree,form',
            'res_model': 'mot_validacion.log',
            'type': 'ir.actions.act_window',
            'target':'main'
        }

class LogReduccion(models.Model):
    _name = 'mot_validacion.log.reduccion'
    _description = 'Log de Reducción'

    fecha = fields.Datetime(string="Fecha de proceso")
    log_id = fields.Many2one(string="Histórico de proceso", comodel_name="mot_validacion.log")
    reduc_max = fields.Float(string="Valor máximo posible de reducción")
    reduc_param = fields.Float(string="Meta de reducción")

    @api.model
    def create(self,values):
        if values['reduc_max'] < values['reduc_param']:
            valores = {
                'asunto': 'No se cumplió la meta de reducción del proceso de llave',
                'descripcion': 'El proceso de llave no pudo reducir la cantidad parametrizada en el parámetro %REDUCCION \n\tValor a reducir: $ ' + str(values['reduc_param']) + ' \n\tValor reducido: $ ' + str(values['reduc_max'])
            }
            self.env['mot_validacion.notificacion'].create(valores)
        return super().create(values)

class Notificacion(models.Model):
    _name = "mot_validacion.notificacion"
    _description = 'Notificación'

    fecha = fields.Datetime(string="Fecha de notificación",default=lambda self: fields.Datetime().now())
    asunto = fields.Char(string="Asunto",required=True)
    descripcion = fields.Text(string="Descripción del evento",required=True)
    correo = fields.Char(string='Correo enviado a')

    @api.model
    def create(self, values):
        values['asunto'] = self.env['motgama.sucursal'].search([],limit=1).nombre + ': ' + values['asunto']
        values['descripcion'] = self.env['motgama.sucursal'].search([],limit=1).nombre + ': ' + values['descripcion']
        values['correo'] = self.env.ref('mot_validacion.parametro_EMAIL_ALERTAS').valor_char
        mailserver = self.env['ir.mail_server'].sudo().search([],limit=1)
        if not mailserver:
            email_from = ''
        else:
            email_from = mailserver.smtp_user
        valoresCorreo = {
            'subject': values['asunto'],
            'email_from': email_from,
            'email_to': values['correo'],
            'body_html': '<h3>' + values['descripcion'] + '</h3>',
            'author_id': False
        }
        correo = self.env['mail.mail'].sudo().create(valoresCorreo)
        if correo:
            correo.sudo().send()
        return super().create(values)