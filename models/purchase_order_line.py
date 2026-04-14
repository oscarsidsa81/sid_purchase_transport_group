from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    transport_group_line_ids = fields.One2many(
        "purchase.transport.group.line",
        "purchase_line_id",
        string="Líneas agrupación transporte",
    )
    transport_hold = fields.Boolean(
        string="Retener para transporte",
        help="Si está marcada, la línea no podrá asignarse a agrupaciones.",
    )
    transport_state = fields.Selection(
        [
            ("available", "Disponible"),
            ("partial", "Parcialmente agrupada"),
            ("grouped", "Totalmente agrupada"),
            ("hold", "Retenida"),
            ("done", "Finalizada"),
        ],
        string="Estado transporte",
        compute="_compute_transport_state",
        store=True,
    )
    qty_transport_assigned = fields.Float(
        string="Cantidad agrupada total",
        compute="_compute_transport_qtys",
        store=True,
        digits="Product Unit of Measure",
    )
    qty_transport_available = fields.Float(
        string="Disponible para agrupar",
        compute="_compute_transport_qtys",
        store=True,
        digits="Product Unit of Measure",
    )

    @api.depends(
        "transport_group_line_ids.qty_assigned",
        "transport_group_line_ids.line_state",
        "transport_group_line_ids.group_id.state",
        "product_qty",
        "qty_received",
    )
    def _compute_transport_qtys(self):
        for line in self:
            assigned = sum(
                group_line.qty_assigned
                for group_line in line.transport_group_line_ids
                if group_line.line_state != "cancel" and group_line.group_id.state != "cancel"
            )
            pending = max(line.product_qty - line.qty_received, 0.0)
            line.qty_transport_assigned = assigned
            line.qty_transport_available = max(pending - assigned, 0.0)

    @api.depends(
        "transport_hold",
        "qty_received",
        "product_qty",
        "qty_transport_assigned",
        "qty_transport_available",
    )
    def _compute_transport_state(self):
        for line in self:
            pending = max(line.product_qty - line.qty_received, 0.0)
            if line.transport_hold:
                line.transport_state = "hold"
            elif pending <= 0:
                line.transport_state = "done"
            elif line.qty_transport_assigned <= 0:
                line.transport_state = "available"
            elif line.qty_transport_available > 0:
                line.transport_state = "partial"
            else:
                line.transport_state = "grouped"
