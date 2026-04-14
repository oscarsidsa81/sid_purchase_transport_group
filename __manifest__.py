{
    "name": "Purchase Transport Group",
    "version": "15.0.3.0.0",
    "summary": "Agrupa lineas de compra para transporte y genera RFQ de transporte",
    "category": "Purchases",
    "author": "OpenAI",
    "license": "LGPL-3",
    "depends": ["purchase", "stock", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/purchase_transport_group_views.xml",
        "views/purchase_order_line_views.xml",
        "views/res_config_settings_views.xml",
        "views/purchase_transport_group_wizard_views.xml"
    ],
    "installable": True,
    "application": False
}
