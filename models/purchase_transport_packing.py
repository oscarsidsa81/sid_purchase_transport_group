from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseTransportPackingType(models.Model):
    _name = "purchase.transport.packing.type"
    _description = "Transport Capacity Template"
    _order = "name"

    name = fields.Char(required=True)
    max_weight_kg = fields.Float(string="Peso máximo (kg)")
    max_volume_m3 = fields.Float(string="Volumen máximo (m³)")
    ref_length_cm = fields.Float(string="Largo referencia (cm)")
    ref_width_cm = fields.Float(string="Ancho referencia (cm)")
    ref_height_cm = fields.Float(string="Alto referencia (cm)")
    active = fields.Boolean(default=True)

    @api.constrains("max_weight_kg", "max_volume_m3", "ref_length_cm", "ref_width_cm", "ref_height_cm")
    def _check_positive_capacity(self):
        for rec in self:
            if rec.max_weight_kg < 0 or rec.max_volume_m3 < 0:
                raise ValidationError(_("Las capacidades no pueden ser negativas."))
            if rec.ref_length_cm < 0 or rec.ref_width_cm < 0 or rec.ref_height_cm < 0:
                raise ValidationError(_("Las dimensiones de referencia no pueden ser negativas."))


class PurchaseTransportPackingLine(models.Model):
    _name = "purchase.transport.packing.line"
    _description = "Purchase Transport Packing Line"
    _order = "group_id, purchase_order_id, id"

    group_id = fields.Many2one("purchase.transport.group", required=True, ondelete="cascade", string="Agrupación")
    purchase_order_id = fields.Many2one("purchase.order", required=True, string="Pedido compra")
    available_purchase_order_ids = fields.Many2many("purchase.order", compute="_compute_available_purchase_order_ids")
    description = fields.Char(string="Descripción", required=True)
    package_count = fields.Integer(string="Nº bultos", default=1, required=True)
    length_cm = fields.Float(string="Largo (cm)", required=True)
    width_cm = fields.Float(string="Ancho (cm)", required=True)
    height_cm = fields.Float(string="Alto (cm)", required=True)
    weight_kg = fields.Float(string="Peso (kg)", required=True)
    volume_m3 = fields.Float(string="Volumen (m³)", compute="_compute_volume_m3", store=True)
    company_id = fields.Many2one(related="group_id.company_id", store=True, readonly=True)


    @api.depends("group_id", "group_id.line_ids.purchase_order_id")
    def _compute_available_purchase_order_ids(self):
        for rec in self:
            rec.available_purchase_order_ids = rec.group_id.line_ids.mapped("purchase_order_id")

    @api.depends("package_count", "length_cm", "width_cm", "height_cm")
    def _compute_volume_m3(self):
        for rec in self:
            rec.volume_m3 = (rec.package_count * rec.length_cm * rec.width_cm * rec.height_cm) / 1000000.0

    @api.constrains("package_count", "length_cm", "width_cm", "height_cm", "weight_kg")
    def _check_positive_values(self):
        for rec in self:
            if rec.package_count <= 0:
                raise ValidationError(_("El número de bultos debe ser mayor que cero."))
            if rec.length_cm <= 0 or rec.width_cm <= 0 or rec.height_cm <= 0:
                raise ValidationError(_("Las dimensiones deben ser mayores que cero."))
            if rec.weight_kg <= 0:
                raise ValidationError(_("El peso debe ser mayor que cero."))

    @api.constrains("purchase_order_id", "group_id")
    def _check_purchase_order_in_group(self):
        for rec in self:
            if rec.group_id.line_ids and rec.purchase_order_id not in rec.group_id.line_ids.mapped("purchase_order_id"):
                raise ValidationError(_("El pedido debe estar incluido en líneas de la agrupación."))
