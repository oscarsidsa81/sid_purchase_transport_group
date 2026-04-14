
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    transport_service_product_id = fields.Many2one(
        'product.product',
        config_parameter='sid.transport.product'
    )
