---
type: pattern
name: Workflow Patterns
version: Odoo 18
tags: [patterns, workflow, state-machine, actions]
---

# Workflow Patterns

## State Field Pattern

```python
class SaleOrder(models.Model):
    _name = 'sale.order'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', copy=False, tracking=True,
       group_expand='_group_expand_states')

    def _group_expand_states(self, states, domain, order):
        # Show all states in Kanban groupby
        return self.env['sale.order']._fields['state'].selection
```

## Action Methods

```python
    def action_confirm(self):
        """Confirm the sales order."""
        for order in self:
            if order.state not in ('draft', 'sent'):
                raise UserError('Order cannot be confirmed in current state.')
            order.write({'state': 'sale'})
            order._action_confirm()
        return True

    def action_cancel(self):
        for order in self:
            if order.state == 'done':
                raise UserError('Done orders cannot be cancelled.')
            order._action_cancel()
        return self.write({'state': 'cancel'})

    def action_draft(self):
        # Reset to draft — unlink previous invoice
        self.write({'state': 'draft'})
        return True
```

## Confirmation with Signal

```python
    def _action_confirm(self):
        """Internal confirmation logic — called after state write."""
        self.ensure_one()
        # Create procurement
        if not self.env.context.get('procurement_bypass'):
            self._create_delivery_orders()
        # Send mail
        self._send_order_confirmation_mail()
        return True
```

## Button XML

```xml
<form>
    <header>
        <button name="action_confirm" string="Confirm" class="btn-primary"
                type="object" invisible="state != 'draft'"/>
        <button name="action_cancel" string="Cancel" class="btn-secondary"
                type="object" invisible="state in ('done', 'cancel')"/>
        <field name="state" widget="statusbar" statusbar_visible="draft,sent,sale"/>
    </header>
</form>
```

## State Transitions

```
draft ──[confirm]──→ sale ──[done]──→ done
  │                  │
  └──[cancel]──→ cancel ←──[cancel]──┘
```

---

## Related Links
- [Modules/Sale](Modules/sale.md) — Sale order state machine
- [Modules/Stock](Modules/stock.md) — Picking state transitions
- [Modules/Purchase](Modules/purchase.md) — Purchase order workflow
