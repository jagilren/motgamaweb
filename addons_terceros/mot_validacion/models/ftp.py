from odoo import models, fields, api

class FTPServer(models.Model):
    _name = 'mot_validacion.ftpserver'
    _description = 'FTP Server'
    _rec_name = 'nombre'

    nombre = fields.Char(string='Nombre',required=True)
    host = fields.Char(string='Host',required=True)
    user = fields.Char(string='Usuario',required=True)
    passwd = fields.Char(string='Contraseña',required=True)
    directory = fields.Char(string='Directorio FTP')
    active = fields.Boolean(string='Activo',default=True)