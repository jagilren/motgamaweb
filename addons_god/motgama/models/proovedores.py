from odoo import models, fields, api
from odoo.exceptions import Warning

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def create(self,values):
        if not self.env.ref('motgama.motgama_crear_proovedores') in self.env.user.permisos:
            raise Warning('No tiene permitido crear proovedores, contacte al administrador')
        record = super().create(values)
        return record
        
    
    def write(self,values):
        if not self.env.ref('motgama.motgama_editar_proovedores') in self.env.user.permisos:
            raise Warning('No tiene permitido editar proovedores, contacte al administrador')
        write = super().write(values)
        return write

