
from odoo import api, fields, models

class PurchaseTransportGroup(models.Model):
    _name = 'purchase.transport.group'
    _description = 'Purchase Transport Group'

    name = fields.Char(default='New', copy=False)
    state = fields.Selection([
        ('draft','Draft'),
        ('active','Active'),
        ('done','Done'),
        ('cancel','Cancel')
    ], default='draft')

    line_ids = fields.One2many('purchase.transport.group.line','group_id')

    note_summary = fields.Text(compute='_compute_note')

    @api.model
    def create(self, vals):
        if vals.get('name') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('purchase.transport.group')
        return super().create(vals)

    def _compute_note(self):
        for rec in self:
            text = ''
            for l in rec.line_ids:
                text += f"{l.purchase_order_id.name} - {l.name}: {l.qty_assigned}\n"
            rec.note_summary = text


class PurchaseTransportGroupLine(models.Model):
    _name = 'purchase.transport.group.line'

    group_id = fields.Many2one('purchase.transport.group')
    purchase_line_id = fields.Many2one('purchase.order.line')

    purchase_order_id = fields.Many2one(
        'purchase.order', related='purchase_line_id.order_id', store=True
    )

    name = fields.Text(related='purchase_line_id.name', store=True)

    qty_assigned = fields.Float()
