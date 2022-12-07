from odoo import models, fields, api
from odoo.exceptions import Warning

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.one
    def copy(self,default=None):
        if not self.env.ref('motgama.motgama_duplicar_compra') in self.env.user.permisos:
            raise Warning('No tiene permitido duplicar compras, contacte al administrador')
        return super().copy(default)

    @api.multi
    def unlink(self):
        if not self.env.ref('motgama.motgama_suprimir_compra') in self.env.user.permisos:
            raise Warning('No tiene permitido suprimir compras, contacte al administrador')
        return super().unlink()


    @api.model
    def create(self,values):
        if not self.env.ref('motgama.motgama_crear_compra') in self.env.user.permisos:
            raise Warning('No tiene permitido crear compras, contacte al administrador')
        record = super().create(values)
        return record
        
    
    def write(self,values):
        if not self.env.ref('motgama.motgama_editar_compra') in self.env.user.permisos:
            raise Warning('No tiene permitido editar compras, contacte al administrador')
        write = super().write(values)
        return write
    
    @api.multi
    def button_cancel(self):
        if not self.env.ref('motgama.motgama_cancelar_compra') in self.env.user.permisos:
            raise Warning('No tiene permitido cancelar compras, contacte al administrador')

    @api.multi
    def button_done(self):
        if not self.env.ref('motgama.motgama_bloquear_compra') in self.env.user.permisos:
            raise Warning('No tiene permitido bloquear compras, contacte al administrador')
