from odoo import models, fields, api
from odoo.exceptions import Warning

class ProductCategory(models.Model):
    _inherit = 'product.category'

    llevaComanda = fields.Boolean(string='¿Lleva Comanda?',default=False)
    es_hospedaje = fields.Boolean(string='Servicio de hospedaje',default=False)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    es_hospedaje = fields.Boolean(string='Servicio de hospedaje',default=False)

    @api.onchange('categ_id')
    def _onchange_categ(self):
        for record in self:
            if record.categ_id:
                record.es_hospedaje = record.categ_id.es_hospedaje

    @api.model
    def create(self,values):
        if not self.env.ref('motgama.motgama_crear_productos') in self.env.user.permisos:
            raise Warning('No tiene permitido crear productos, contacte al administrador')
        record = super().create(values)
        return record
        
    
    def write(self,values):
        if not self.env.ref('motgama.motgama_editar_productos') in self.env.user.permisos:
            raise Warning('No tiene permitido editar productos, contacte al administrador')
        write = super().write(values)
        return write


    