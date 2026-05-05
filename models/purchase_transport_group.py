from collections import OrderedDict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseTransportGroup(models.Model):
    _name = "purchase.transport.group"
    _description = "Purchase Transport Group"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(string="Referencia", required=True, copy=False, default="New", readonly=True, tracking=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("active", "Activa"), ("done", "Finalizada"), ("cancel", "Cancelada")],
        default="draft", string="Estado", tracking=True
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, tracking=True)
    carrier_partner_id = fields.Many2one("res.partner", string="Transportista", domain=[("supplier_rank", ">", 0)], tracking=True)
    transport_purchase_id = fields.Many2one("purchase.order", string="RFQ transporte", copy=False, readonly=True, tracking=True)
    line_ids = fields.One2many("purchase.transport.group.line", "group_id", string="Líneas", copy=True)
    line_count = fields.Integer(string="Nº líneas", compute="_compute_line_count")
    note_summary = fields.Text(string="Resumen", compute="_compute_note_summary", store=True)
    packing_line_ids = fields.One2many("purchase.transport.packing.line", "group_id", string="Packing list")
    packing_count = fields.Integer(string="Nº packings", compute="_compute_packing_totals")
    total_weight_kg = fields.Float(string="Peso total (kg)", compute="_compute_packing_totals", store=True)
    total_volume_m3 = fields.Float(string="Volumen total (m³)", compute="_compute_packing_totals", store=True)
    transport_type_id = fields.Many2one("purchase.transport.packing.type", string="Tipo transporte")
    capacity_weight_kg = fields.Float(string="Capacidad peso (kg)")
    capacity_volume_m3 = fields.Float(string="Capacidad volumen (m³)")
    ref_length_cm = fields.Float(related="transport_type_id.ref_length_cm", readonly=True, string="Largo ref. (cm)")
    ref_width_cm = fields.Float(related="transport_type_id.ref_width_cm", readonly=True, string="Ancho ref. (cm)")
    ref_height_cm = fields.Float(related="transport_type_id.ref_height_cm", readonly=True, string="Alto ref. (cm)")
    occupancy_weight_pct = fields.Float(string="Ocupación peso %", compute="_compute_occupancy")
    occupancy_volume_pct = fields.Float(string="Ocupación volumen %", compute="_compute_occupancy")
    occupancy_max_pct = fields.Float(string="Ocupación total %", compute="_compute_occupancy")

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends(
        "line_ids.purchase_order_id",
        "line_ids.purchase_order_id.partner_id",
        "line_ids.purchase_line_id",
        "line_ids.qty_assigned",
        "line_ids.line_state",
    )
    def _compute_note_summary(self):
        for group in self:
            supplier_map = OrderedDict()
            for line in group.line_ids.filtered(lambda l: l.line_state != "cancel"):
                po = line.purchase_order_id
                supplier = po.partner_id
                contact = po.partner_id.child_ids.filtered(lambda c: c.type == "delivery")[:1] or po.partner_id
                key = (supplier.id, contact.id)
                supplier_map.setdefault(key, {
                    "supplier_name": supplier.display_name or _("Sin proveedor"),
                    "address": contact.contact_address or _("Sin dirección"),
                    "pl_map": OrderedDict(),
                })
                pl_name = line.purchase_line_id.display_name or line.name or _("Sin PL")
                supplier_map[key]["pl_map"].setdefault(pl_name, 0.0)
                supplier_map[key]["pl_map"][pl_name] += line.qty_assigned
            blocks = []
            for info in supplier_map.values():
                blocks.append(info["supplier_name"])
                blocks.append(_("- Dirección recogida: %s") % info["address"])
                blocks.append(_("- Resumen PL asociados:"))
                for pl_name, qty in info["pl_map"].items():
                    blocks.append("  • %s: %s" % (pl_name, qty))
                blocks.append("")
            group.note_summary = "\n".join(blocks).strip()


    @api.depends("packing_line_ids.weight_kg", "packing_line_ids.volume_m3")
    def _compute_packing_totals(self):
        for rec in self:
            rec.packing_count = len(rec.packing_line_ids)
            rec.total_weight_kg = sum(rec.packing_line_ids.mapped("weight_kg"))
            rec.total_volume_m3 = sum(rec.packing_line_ids.mapped("volume_m3"))

    @api.depends("total_weight_kg", "total_volume_m3", "capacity_weight_kg", "capacity_volume_m3")
    def _compute_occupancy(self):
        for rec in self:
            rec.occupancy_weight_pct = (rec.total_weight_kg / rec.capacity_weight_kg) if rec.capacity_weight_kg else 0.0
            rec.occupancy_volume_pct = (rec.total_volume_m3 / rec.capacity_volume_m3) if rec.capacity_volume_m3 else 0.0
            rec.occupancy_max_pct = max(rec.occupancy_weight_pct, rec.occupancy_volume_pct)

    @api.onchange("transport_type_id")
    def _onchange_transport_type_id(self):
        for rec in self:
            if rec.transport_type_id:
                rec.capacity_weight_kg = rec.transport_type_id.max_weight_kg
                rec.capacity_volume_m3 = rec.transport_type_id.max_volume_m3

    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("purchase.transport.group") or "New"
        return super().create(vals)

    def action_activate(self):
        self.write({"state": "active"})

    def action_done(self):
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_reset_draft(self):
        self.write({"state": "draft"})

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

    def action_view_lines(self):
        self.ensure_one()
        action = self.env.ref("sid_purchase_transport_group.action_purchase_transport_group_line").read()[0]
        action["domain"] = [("group_id", "=", self.id)]
        action["context"] = {"default_group_id": self.id}
        return action

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
            "notes": self._prepare_transport_rfq_notes(),
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


    def _prepare_transport_rfq_notes(self):
        self.ensure_one()
        lines = [self.note_summary or "", "", _("PACKING LIST"), _("Peso total: %.2f kg") % self.total_weight_kg, _("Volumen total: %.3f m³") % self.total_volume_m3]
        for pack in self.packing_line_ids:
            lines.append(_("- %s | PO: %s | Bultos: %s | Peso: %.2f kg | Volumen: %.3f m³") % (
                pack.description, pack.purchase_order_id.name, pack.package_count, pack.weight_kg, pack.volume_m3
            ))
        return "\n".join([l for l in lines if l is not False])

    def action_view_packing_lines(self):
        self.ensure_one()
        action = self.env.ref("sid_purchase_transport_group.action_purchase_transport_packing_line").read()[0]
        action["domain"] = [("group_id", "=", self.id)]
        action["context"] = {"default_group_id": self.id}
        return action


class PurchaseTransportGroupLine(models.Model):
    _name = "purchase.transport.group.line"
    _description = "Purchase Transport Group Line"
    _order = "group_id, purchase_order_id, id"

    group_id = fields.Many2one("purchase.transport.group", string="Agrupación", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", related="group_id.company_id", store=True, readonly=True)
    purchase_line_id = fields.Many2one(
        "purchase.order.line", string="Línea de compra", required=True, ondelete="restrict",
        domain=[("display_type", "=", False)]
    )
    purchase_order_id = fields.Many2one("purchase.order", related="purchase_line_id.order_id", store=True, readonly=True)
    partner_id = fields.Many2one("res.partner", related="purchase_order_id.partner_id", store=True, readonly=True)
    product_id = fields.Many2one("product.product", related="purchase_line_id.product_id", store=True, readonly=True)
    name = fields.Text(related="purchase_line_id.name", store=True, readonly=True, string="Descripción")
    product_uom = fields.Many2one("uom.uom", related="purchase_line_id.product_uom", store=True, readonly=True)
    qty_po = fields.Float(string="Cantidad pedido", related="purchase_line_id.product_qty", store=True, readonly=True,
                          digits="Product Unit of Measure")
    qty_received = fields.Float(string="Cantidad recibida", related="purchase_line_id.qty_received", store=True, readonly=True,
                                digits="Product Unit of Measure")
    qty_available = fields.Float(string="Disponible para agrupar", compute="_compute_qty_available",
                                 digits="Product Unit of Measure")
    qty_assigned = fields.Float(string="Cantidad agrupada", required=True, digits="Product Unit of Measure")
    qty_done = fields.Float(string="Cantidad movida", digits="Product Unit of Measure")
    line_state = fields.Selection(
        [("included", "Incluida"), ("hold", "Retenida"), ("done", "Finalizada"), ("cancel", "Cancelada")],
        default="included", string="Estado línea"
    )
    purchase_transport_state = fields.Selection(related="purchase_line_id.transport_state", readonly=True,
                                                string="Estado línea compra")

    @api.depends("purchase_line_id.qty_transport_available", "qty_assigned", "purchase_line_id")
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
            duplicate = self.search_count([
                ("id", "!=", line.id),
                ("group_id", "=", line.group_id.id),
                ("purchase_line_id", "=", line.purchase_line_id.id),
                ("line_state", "!=", "cancel"),
            ])
            if duplicate:
                raise ValidationError(_("La misma línea de compra no puede repetirse en la misma agrupación."))
