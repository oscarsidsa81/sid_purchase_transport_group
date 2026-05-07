from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    transport_purchase_line_ids = fields.One2many("purchase.order.line", "sale_order_id", string="Líneas compra transporte")
    transport_purchase_count = fields.Integer(string="Compras transporte", compute="_compute_transport_purchase_info")
    transport_cost_total = fields.Monetary(string="Coste transporte", compute="_compute_transport_purchase_info", currency_field="currency_id")

    @api.depends("transport_purchase_line_ids.price_subtotal", "transport_purchase_line_ids.order_id")
    def _compute_transport_purchase_info(self):
        for rec in self:
            lines = rec.transport_purchase_line_ids.filtered(
                lambda l: l.order_id.state != "cancel" and bool(l.transport_group_id)
            )
            rec.transport_purchase_count = len(lines.mapped("order_id"))
            rec.transport_cost_total = sum(lines.mapped("price_subtotal"))

    def action_view_transport_purchases(self):
        self.ensure_one()
        action = self.env.ref("purchase.purchase_rfq").read()[0]
        action["domain"] = [("order_line.sale_order_id", "=", self.id), ("order_line.transport_group_id", "!=", False)]
        return action
