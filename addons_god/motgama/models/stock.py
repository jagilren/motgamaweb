from odoo import models, fields, api
from odoo.exceptions import Warning

class StockLocation(models.Model):
    _inherit = 'stock.location'

    recepcion = fields.Many2one(string='Recepción',comodel_name='motgama.recepcion',ondelete='cascade')
    permite_consumo = fields.Boolean(string='¿Permite Consumo?',default=False)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_scrap(self):
         if not self.env.ref('motgama.motgama_btndesechable') in self.env.user.permisos:
            raise Warning('No tiene permitido desechar inventarios, contacte al administrador')

    @api.multi
    def copy(self,default=None):
        if not self.env.ref('motgama.motgama_duplicar_inventario') in self.env.user.permisos:
            raise Warning('No tiene permitido duplicar inventario, contacte al administrador')
        return super().copy(default)

    @api.multi
    def unlink(self):
        if not self.env.ref('motgama.motgama_suprimir_inventario') in self.env.user.permisos:
            raise Warning('No tiene permitido suprimir inventario, contacte al administrador')
        return super().unlink()

    @api.multi
    def action_toggle_is_locked(self):
        if not self.env.ref('motgama.motgama_desbloquear_inventario') in self.env.user.permisos:
            raise Warning('No tiene permitido desbloquear inventario, contacte al administrador')



    