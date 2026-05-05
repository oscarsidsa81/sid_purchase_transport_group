from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    transport_packing_line_ids = fields.One2many(
        "purchase.transport.packing.line", "purchase_order_id", string="Packing lines transporte"
    )
    transport_packing_count = fields.Integer(compute="_compute_transport_packing_count")

    @api.depends("transport_packing_line_ids")
    def _compute_transport_packing_count(self):
        for rec in self:
            rec.transport_packing_count = len(rec.transport_packing_line_ids)

    def action_view_transport_packing_lines(self):
        self.ensure_one()
        action = self.env.ref("sid_purchase_transport_group.action_purchase_transport_packing_line").read()[0]
        action["domain"] = [("purchase_order_id", "=", self.id)]
        action["context"] = {"default_purchase_order_id": self.id}
        return action
