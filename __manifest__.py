
{
    'name': 'Purchase Transport Group',
    'version': '15.0.1.0.0',
    'summary': 'Agrupacion de lineas de compra para transporte',
    'category': 'Purchases',
    'author': 'Custom',
    'depends': ['purchase', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/purchase_transport_group_views.xml',
        'views/purchase_order_line_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
}
