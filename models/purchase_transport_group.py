from collections import OrderedDict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseTransportGroup(models.Model):
    _name = "purchase.transport.group"
    _description = "Purchase Transport Group"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        default="New",
        readonly=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("active", "Activa"),
            ("done", "Finalizada"),
            ("cancel", "Cancelada"),
        ],
        default="draft",
        string="Estado",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    carrier_partner_id = fields.Many2one(
        "res.partner",
        string="Transportista",
        domain=[("supplier_rank", ">", 0)],
        tracking=True,
    )
    transport_purchase_id = fields.Many2one(
        "purchase.order",
        string="RFQ transporte",
        copy=False,
        readonly=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        "purchase.transport.group.line",
        "group_id",
        string="Líneas",
        copy=True,
    )
    line_count = fields.Integer(
        string="Nº líneas",
        compute="_compute_line_count",
    )
    note_summary = fields.Text(
        string="Resumen",
        compute="_compute_note_summary",
        store=True,
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends(
        "line_ids.purchase_order_id",
        "line_ids.name",
        "line_ids.qty_assigned",
        "line_ids.line_state",
    )
    def _compute_note_summary(self):
        for group in self:
            po_map = OrderedDict()
            valid_lines = group.line_ids.filtered(lambda l: l.line_state != "cancel")
            for line in valid_lines:
                po_name = line.purchase_order_id.name or _("Sin pedido")
                po_map.setdefault(po_name, OrderedDict())
                desc = (line.name or "").strip()
                po_map[po_name].setdefault(desc, 0.0)
                po_map[po_name][desc] += line.qty_assigned

            blocks = []
            for po_name, desc_map in po_map.items():
                blocks.append(po_name)
                for desc, qty in desc_map.items():
                    if desc:
                        blocks.append("- %s: %s" % (desc, qty))
                blocks.append("")
            group.note_summary = "\n".join(blocks).strip()

    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("purchase.transport.group") or "New"
        return super().create(vals)

    def action_activate(self):
        for rec in self:
            rec.state = "active"

    def action_done(self):
        for rec in self:
            rec.state = "done"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancel"

    def action_reset_draft(self):
        for rec in self:
            rec.state = "draft"

    def action_view_transport_purchase(self):
        self.ensure_one()
        if not self.transport_purchase_id:
            raise UserError(_("La agrupación no tiene RFQ de transporte."))
        return {
            "type": "ir.actions.act_window",
            "name": _("RFQ transporte"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": self.transport_purchase_id.id,
            "target": "current",
        }

    def action_create_transport_purchase(self):
        self.ensure_one()
        if self.transport_purchase_id:
            return self.action_view_transport_purchase()

        icp = self.env["ir.config_parameter"].sudo()
        product_id = int(icp.get_param("sid_purchase_transport_group.transport_service_product_id") or 0)
        supplier_id = int(icp.get_param("sid_purchase_transport_group.transport_supplier_id") or 0)

        if not product_id:
            raise UserError(_("Configura el producto de transporte en Ajustes de Compras."))
        if not supplier_id:
            raise UserError(_("Configura el proveedor de transporte por defecto en Ajustes de Compras."))

        product = self.env["product.product"].browse(product_id)
        supplier = self.env["res.partner"].browse(supplier_id)

        po = self.env["purchase.order"].create({
            "partner_id": supplier.id,
            "company_id": self.company_id.id,
            "notes": self.note_summary or "",
            "origin": self.name,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "name": _("Transporte agrupación %s") % self.name,
                "product_qty": 1.0,
                "product_uom": product.uom_po_id.id or product.uom_id.id,
                "price_unit": 0.0,
                "date_planned": fields.Datetime.now(),
            })],
        })
        self.transport_purchase_id = po.id
        return self.action_view_transport_purchase()


class PurchaseTransportGroupLine(models.Model):
    _name = "purchase.transport.group.line"
    _description = "Purchase Transport Group Line"
    _order = "group_id, purchase_order_id, id"

    group_id = fields.Many2one(
        "purchase.transport.group",
        string="Agrupación",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        related="group_id.company_id",
        store=True,
        readonly=True,
    )
    purchase_line_id = fields.Many2one(
        "purchase.order.line",
        string="Línea de compra",
        required=True,
        ondelete="restrict",
        domain=[("display_type", "=", False)],
    )
    purchase_order_id = fields.Many2one(
        "purchase.order",
        related="purchase_line_id.order_id",
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        related="purchase_order_id.partner_id",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        related="purchase_line_id.product_id",
        store=True,
        readonly=True,
    )
    name = fields.Text(
        related="purchase_line_id.name",
        store=True,
        readonly=True,
        string="Descripción",
    )
    product_uom = fields.Many2one(
        "uom.uom",
        related="purchase_line_id.product_uom",
        store=True,
        readonly=True,
    )
    qty_po = fields.Float(
        string="Cantidad pedido",
        related="purchase_line_id.product_qty",
        store=True,
        readonly=True,
        digits="Product Unit of Measure",
    )
    qty_received = fields.Float(
        string="Cantidad recibida",
        related="purchase_line_id.qty_received",
        store=True,
        readonly=True,
        digits="Product Unit of Measure",
    )
    qty_available = fields.Float(
        string="Disponible para agrupar",
        compute="_compute_qty_available",
        digits="Product Unit of Measure",
    )
    qty_assigned = fields.Float(
        string="Cantidad agrupada",
        required=True,
        digits="Product Unit of Measure",
    )
    qty_done = fields.Float(
        string="Cantidad movida",
        digits="Product Unit of Measure",
    )
    line_state = fields.Selection(
        [
            ("included", "Incluida"),
            ("hold", "Retenida"),
            ("done", "Finalizada"),
            ("cancel", "Cancelada"),
        ],
        default="included",
        string="Estado línea",
    )
    purchase_transport_state = fields.Selection(
        related="purchase_line_id.transport_state",
        readonly=True,
        string="Estado línea compra",
    )

    @api.depends(
        "purchase_line_id.qty_transport_available",
        "qty_assigned",
        "purchase_line_id",
    )
    def _compute_qty_available(self):
        for line in self:
            if not line.purchase_line_id:
                line.qty_available = 0.0
                continue
            available = line.purchase_line_id.qty_transport_available
            if line.id:
                available += line.qty_assigned
            line.qty_available = max(available, 0.0)

    @api.constrains("qty_assigned")
    def _check_qty_assigned(self):
        for line in self:
            if line.qty_assigned <= 0:
                raise ValidationError(_("La cantidad agrupada debe ser mayor que cero."))
            if line.qty_assigned > line.qty_available:
                raise ValidationError(_("La cantidad agrupada no puede superar la disponible para agrupar."))
            if line.purchase_line_id.transport_hold:
                raise ValidationError(_("La línea de compra está retenida para transporte."))

    @api.constrains("purchase_line_id", "group_id")
    def _check_unique_purchase_line_per_group(self):
        for line in self:
            if not line.purchase_line_id or not line.group_id:
                continue
            duplicate = self.search_count([
                ("id", "!=", line.id),
                ("group_id", "=", line.group_id.id),
                ("purchase_line_id", "=", line.purchase_line_id.id),
                ("line_state", "!=", "cancel"),
            ])
            if duplicate:
                raise ValidationError(_("La misma línea de compra no puede repetirse en la misma agrupación."))
