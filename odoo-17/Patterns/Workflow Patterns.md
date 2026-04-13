---
tags: [odoo, odoo17, patterns, workflow]
---

# Workflow Patterns

## State Machine Pattern

Odoo uses explicit state fields + action methods instead of XML workflows.

```python
state = fields.Selection([
    ('draft', 'Draft'),
    ('confirm', 'Confirmed'),
    ('done', 'Done'),
    ('cancel', 'Cancelled'),
], string='Status', default='draft', readonly=True)

def action_confirm(self):
    for rec in self:
        if rec.state != 'draft':
            raise UserError('Only draft can be confirmed')
        rec.write({'state': 'confirm'})
    return True
```

## Validation Pattern

Always validate before changing state:

```python
def _check_values(self):
    for rec in self:
        if not rec.line_ids:
            raise UserError('Order must have at least one line')

def action_done(self):
    self._check_values()
    return self.write({'state': 'done'})
```

## Button Actions

XML button that calls action method:

```xml
<button name="action_confirm" string="Confirm" type="object" class="btn-primary"/>
```

## Kanban State Indicators

```python
# In kanban view:
state = fields.Selection([
    ('draft', 'Gray'),
    ('progress', 'Blue'),
    ('done', 'Green'),
], string='State')

# decoration- attributes:
decoration-success="state == 'done'"
decoration-warning="state in ('draft', 'confirm')"
```

## See Also
- [Modules/sale](modules/sale.md) — sale.order workflow
- [Modules/purchase](modules/purchase.md) — purchase.order workflow
- [Modules/stock](modules/stock.md) — stock.picking workflow
