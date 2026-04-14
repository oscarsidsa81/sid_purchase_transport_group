
from odoo import fields, models

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    transport_group_line_ids = fields.One2many(
        'purchase.transport.group.line',
        'purchase_line_id'
    )
