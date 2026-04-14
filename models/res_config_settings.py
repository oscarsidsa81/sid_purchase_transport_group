from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    transport_service_product_id = fields.Many2one(
        "product.product",
        string="Producto transporte",
        domain=[("purchase_ok", "=", True)],
    )
    transport_supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor transporte por defecto",
        domain=[("supplier_rank", ">", 0)],
    )

    def set_values(self):
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(
            "sid_purchase_transport_group.transport_service_product_id",
            self.transport_service_product_id.id or False,
        )
        icp.set_param(
            "sid_purchase_transport_group.transport_supplier_id",
            self.transport_supplier_id.id or False,
        )

    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        res.update(
            transport_service_product_id=int(
                icp.get_param("sid_purchase_transport_group.transport_service_product_id") or 0
            ),
            transport_supplier_id=int(
                icp.get_param("sid_purchase_transport_group.transport_supplier_id") or 0
            ),
        )
        return res
