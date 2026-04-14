from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseTransportGroupWizard(models.TransientModel):
    _name = "purchase.transport.group.wizard"
    _description = "Wizard agrupación transporte"

    group_mode = fields.Selection(
        [("new", "Nueva agrupación"), ("existing", "Agrupación existente")],
        string="Modo",
        default="new",
        required=True,
    )
    group_id = fields.Many2one(
        "purchase.transport.group",
        string="Agrupación existente",
        domain=[("state", "in", ("draft", "active"))],
    )
    carrier_partner_id = fields.Many2one(
        "res.partner",
        string="Transportista",
        domain=[("supplier_rank", ">", 0)],
    )
    line_ids = fields.One2many(
        "purchase.transport.group.wizard.line",
        "wizard_id",
        string="Líneas",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        active_model = self.env.context.get("active_model")
        if active_model != "purchase.order.line" or not active_ids:
            return res

        po_lines = self.env["purchase.order.line"].browse(active_ids).filtered(lambda l: not l.display_type)
        line_vals = []
        for line in po_lines:
            if line.transport_state == "done":
                continue
            line_vals.append((0, 0, {
                "purchase_line_id": line.id,
                "qty_available": line.qty_transport_available,
                "qty_to_assign": line.qty_transport_available,
            }))
        res["line_ids"] = line_vals
        return res

    def _build_no_available_message(self):
        details = []
        for wl in self.line_ids:
            pol = wl.purchase_line_id
            reasons = []
            if pol.transport_hold:
                reasons.append(_("retenida"))
            if pol.transport_state == "grouped":
                reasons.append(_("agrupada completamente"))
            if pol.transport_state == "done":
                reasons.append(_("finalizada"))
            groups = pol.transport_group_line_ids.filtered(
                lambda g: g.line_state != "cancel" and g.group_id.state != "cancel"
            )
            group_txt = ", ".join("%s (%.2f)" % (g.group_id.name, g.qty_assigned) for g in groups) or _("sin agrupaciones activas")
            details.append(
                "- %s / %s | disponible=%s | estado=%s | agrupaciones=%s%s" % (
                    pol.order_id.name or "-",
                    (pol.product_id.display_name or pol.name or "").strip(),
                    wl.qty_available,
                    pol.transport_state or "-",
                    group_txt,
                    (" | motivo=%s" % ", ".join(reasons)) if reasons else "",
                )
            )
        return _("No hay líneas con cantidad a asignar.\n\n%s") % "\n".join(details[:20])

    def action_create_group(self):
        self.ensure_one()
        selected_lines = self.line_ids.filtered(lambda l: l.qty_to_assign > 0)
        if not selected_lines:
            raise UserError(self._build_no_available_message())

        errors = []
        for line in selected_lines:
            pol = line.purchase_line_id
            if pol.transport_hold:
                errors.append(
                    "- %s / %s -> %s" % (
                        pol.order_id.name or "-",
                        pol.product_id.display_name or pol.name or "-",
                        _("línea retenida para transporte"),
                    )
                )
            elif line.qty_to_assign > line.qty_available:
                groups = pol.transport_group_summary or _("sin agrupaciones")
                errors.append(
                    "- %s / %s -> %s: %s, %s: %s, %s: %s" % (
                        pol.order_id.name or "-",
                        pol.product_id.display_name or pol.name or "-",
                        _("disponible"),
                        line.qty_available,
                        _("solicitado"),
                        line.qty_to_assign,
                        _("agrupaciones"),
                        groups,
                    )
                )

        if errors:
            raise ValidationError(_("No se puede crear la agrupación:\n\n%s") % "\n".join(errors[:20]))

        if self.group_mode == "existing":
            if not self.group_id:
                raise UserError(_("Debes indicar una agrupación existente."))
            group = self.group_id
        else:
            group = self.env["purchase.transport.group"].create({
                "carrier_partner_id": self.carrier_partner_id.id,
            })

        for wiz_line in selected_lines:
            self.env["purchase.transport.group.line"].create({
                "group_id": group.id,
                "purchase_line_id": wiz_line.purchase_line_id.id,
                "qty_assigned": wiz_line.qty_to_assign,
                "line_state": "included",
            })

        return {
            "type": "ir.actions.act_window",
            "name": _("Agrupación de transporte"),
            "res_model": "purchase.transport.group",
            "view_mode": "form",
            "res_id": group.id,
            "target": "current",
        }


class PurchaseTransportGroupWizardLine(models.TransientModel):
    _name = "purchase.transport.group.wizard.line"
    _description = "Wizard línea agrupación transporte"

    wizard_id = fields.Many2one("purchase.transport.group.wizard", required=True, ondelete="cascade")
    purchase_line_id = fields.Many2one("purchase.order.line", string="Línea de compra", required=True)
    purchase_order_id = fields.Many2one("purchase.order", related="purchase_line_id.order_id", readonly=True, string="Pedido")
    product_id = fields.Many2one("product.product", related="purchase_line_id.product_id", readonly=True, string="Producto")
    name = fields.Text(related="purchase_line_id.name", readonly=True, string="Descripción")
    product_uom = fields.Many2one("uom.uom", related="purchase_line_id.product_uom", readonly=True, string="UdM")
    qty_available = fields.Float(string="Disponible", digits="Product Unit of Measure", readonly=True)
    qty_to_assign = fields.Float(string="Cantidad a agrupar", digits="Product Unit of Measure")
    transport_state = fields.Selection(related="purchase_line_id.transport_state", readonly=True, string="Estado transporte")
    transport_group_summary = fields.Char(related="purchase_line_id.transport_group_summary", readonly=True, string="Agrupaciones")
