---
type: core
module: api
tags: [odoo, odoo19, api, decorator, orm]
created: 2026-04-06
updated: 2026-04-06
version: "1.1"
---

# API Decorators

## Overview

Decorators untuk Odoo ORM methods. Semua decorator ini mengontrol bagaimana method dipanggil, diakses, dan di-cache oleh ORM.

**Location:** `~/odoo/odoo19/odoo/odoo/api.py`

> **📖 Deep Dive:** Untuk dokumentasi method chain lengkap, lihat [Flows/TEMPLATE-flow](Flows/TEMPLATE-flow.md).

---

## Quick Reference

| Decorator | Trigger | Context | Cache | Side Effect |
|-----------|---------|---------|-------|-------------|
| `@api.depends` | Field write | Current user | Stored in DB | Auto-recompute |
| `@api.onchange` | UI field change | Current user | Memory only | UI update |
| `@api.constrains` | Create/Write | Current user | — | Blocks save |
| `@api.model` | Manual/API call | Superuser | — | No record context |
| `@api.model_create_multi` | Create call | Current user | — | Multiple records |

---

## @api.depends

### Purpose
Recompute stored computed fields when any dependency field changes. Results are **stored in database** and cached.

### Basic Syntax

```python
@api.depends('field_a', 'field_b')
def _compute_field(self):
    for rec in self:
        rec.field = rec.field_a + rec.field_b
```

### Cascade Propagation

`@api.depends` dapat berantai — satu computed field berubah → memicu computed field lain yang depend padanya:

```
partner_id written
  └─► @api.depends('partner_id')
        └─► _compute_partner_name()
              └─► @api.depends('partner_id.name')
                    └─► _compute_display_name()
                          └─► cascade continues
```

### Multi-Level Cascade Example

```
sale.order.line.product_id written
  │
  ├─► @api.depends('product_id')
  │      └─► _compute_product_uom_id()
  │            └─► UOM auto-set from product
  │
  ├─► @api.depends('product_id')
  │      └─► _compute_price_unit()
  │            └─► Price auto-filled from product pricelist
  │
  └─► @api.depends('product_id', 'product_uom_qty')
         └─► _compute_price_subtotal()
               └─► price_unit × quantity calculated
                     └─► _compute_tax_id()
                           └─► Taxes auto-applied from product fiscal position
```

### Stored vs Non-Stored

| Type | Stored | Recompute Trigger |
|------|--------|------------------|
| Regular computed | ✅ Yes (DB) | `@api.depends` field change |
| Computed + `store=True` | ✅ Yes (DB) | `@api.depends` field change |
| Computed only | ❌ No (memory) | Every access |

```python
# Stored — recomputed only when dependencies change
margin = fields.Float(compute='_compute_margin', store=True)

# Non-stored — recomputed every read (expensive for complex computation)
computed_view = fields.Char(compute='_compute_view')
```

### Extension Point

```python
# WRONG — replaces entire computation
@api.depends('list_price', 'standard_price')
def _compute_margin(self):
    for rec in self:
        rec.margin = rec.list_price - rec.standard_price

# CORRECT — extend with super()
@api.depends('list_price', 'standard_price', 'discount')
def _compute_margin(self):
    # Your custom computation
    for rec in self:
        rec.margin = rec.list_price - rec.standard_price
```

> **⚠️ Deprecated pattern:** `@api.multi` on computed methods. Odoo 19 handles recordsets automatically.

---

## @api.onchange

### Purpose
Trigger method when a field changes in the Odoo UI form view. Results are **NOT stored** — only used for UI feedback and auto-fill.

### Basic Syntax

```python
@api.onchange('partner_id')
def _onchange_partner(self):
    if self.partner_id:
        self.partner_invoice_id = self.partner_id.address_get(['invoice'])['invoice']
```

### Cascade Chain

`@api.onchange` dapat memicu `@api.depends` computed fields, dan onchange lain dapat cascade:

```
User changes: partner_id
  │
  ├─► _onchange_partner()  [@api.onchange]
  │      ├─► self.partner_invoice_id = ...
  │      └─► self.partner_shipping_id = ...
  │            └─► ⚡ Triggers _compute_delivery_address()
  │                  └─► ⚡ Triggers @api.depends cascade
  │
  └─► _onchange_partner_shipping_id()  [@api.onchange on partner_shipping_id]
         └─► delivery address onchange fires
```

### What Can Be Done in @api.onchange

| ✅ Allowed | ❌ NOT Allowed |
|-----------|---------------|
| Set field values | Direct `write()` calls |
| Raise UserError | `create()` on same model |
| Return domain for field | Complex business logic |
| Return warning dialog | External API calls |
| Modify displayed values | State transitions |

### Return Value

```python
@api.onchange('partner_id')
def _onchange_partner(self):
    if not self.partner_id:
        return {}

    # Auto-fill
    self.invoice_address = self.partner_id.address_get(['invoice'])['invoice']

    # Return domain for next field
    if self.partner_id.country_id:
        return {
            'domain': {
                'fiscal_position': [
                    ('country_ids', 'in', self.partner_id.country_id.ids)
                ]
            }
        }

    # Show warning
    if self.partner_id.debt > 0:
        return {
            'warning': {
                'title': 'Warning',
                'message': 'Partner has outstanding debt'
            }
        }
```

### Security Context
`@api.onchange` runs as the **current logged-in user**. ACL applies — onchange cannot set fields the user doesn't have write access to.

### Transaction Boundary
`@api.onchange` changes are **NOT written to database**. They exist only in the browser session. On form save, `@api.depends` recalculates, then `create()`/`write()` commits to DB.

---

## @api.constrains

### Purpose
Validate data on `create()` and `write()`. If validation fails, the entire transaction is **rolled back**.

### Basic Syntax

```python
@api.constrains('start_date', 'end_date')
def _check_dates(self):
    for rec in self:
        if rec.start_date and rec.end_date:
            if rec.start_date > rec.end_date:
                raise ValidationError(
                    'Start date must be before end date'
                )
```

### Flow Diagram

```
write({'start_date': X, 'end_date': Y})
  │
  ├─► Field value updated in ORM
  │
  ├─► @api.constrains('_check_dates') triggered
  │      ├─► IF start_date > end_date:
  │      │      └─► raise ValidationError("Start must be before end")
  │      │            └─► Transaction ROLLED BACK
  │      │                  └─► User sees error, form not saved
  │      │
  │      └─► IF valid:
  │            └─► Continue
  │
  └─► write() completes → commit
```

### Multiple @api.constrains

Multiple `@api.constrains` decorators can exist on the same model. ALL must pass:

```
create(vals) / write(vals)
  │
  ├─► @api.constrains('field_a', 'field_b')
  │      └─► Check 1
  │            └─► IF fail → rollback
  │
  ├─► @api.constrains('field_c')
  │      └─► Check 2
  │            └─► IF fail → rollback
  │
  └─► @api.constrains('field_d', 'field_e')
         └─► Check 3
               └─► IF fail → rollback
```

### Error Scenarios

| Decorator | When Triggered | What Happens on Failure |
|-----------|--------------|----------------------|
| `@api.constrains` | create() or write() | Transaction rollback |
| SQL constraint | create() or write() | Database error |
| `@api.onchange` | UI field change | Warning shown, can proceed |

### Extension Point

```python
# Extend constraint with super()
@api.constrains('start_date', 'end_date')
def _check_dates(self):
    # Call parent constraint first
    super()._check_dates()
    # Add custom validation
    for rec in self:
        if rec.start_date and rec.end_date:
            if (rec.end_date - rec.start_date).days > 365:
                raise ValidationError('Contract cannot exceed 365 days')
```

---

## @api.model

### Purpose
Method executes as **superuser** (bypassing ACL), with **no active record** (`self` is empty recordset).

### When to Use

| Use Case | `@api.model` | `@api.depends` |
|----------|-------------|---------------|
| Default values | ✅ Yes | ❌ No |
| Name search | ✅ Yes | ❌ No |
| Cascading unlink | ✅ Yes | ❌ No |
| Active record logic | ❌ No | ✅ Yes |

### Basic Syntax

```python
@api.model
def _default_stage_id(self):
    return self.env['crm.stage'].search([('name', '=', 'New')], limit=1)

@api.model
def name_search(self, name='', args=None, operator='ilike', limit=80):
    # name_search runs as superuser — no record context needed
    ...
```

### Security Context
`@api.model` methods run as **superuser** (`uid = 1` or `sudo()`). No ACL is checked. Use carefully — this bypasses all security.

### Idempotency
`@api.model` methods are generally **idempotent** — safe to call multiple times with same arguments.

---

## @api.model_create_multi

### Purpose
Override `create()` to efficiently create multiple records in one call. Odoo 19 standard pattern for batch creation.

### Basic Syntax

```python
@api.model_create_multi
def create(self, vals_list):
    # vals_list: list of dicts
    # Create records in batch
    records = super().create(vals_list)
    # Post-creation logic here
    for rec in records:
        rec._post_create_hook()
    return records
```

### Method Chain on Batch Create

```
Model.create([vals_a, vals_b, vals_c])
  │
  ├─► @api.model_create_multi triggers
  │      ├─► Pre-create hooks
  │      ├─► ir.sequence .next_by_code() — sequence consumed 3x
  │      ├─► For each vals:
  │      │      ├─► _compute_default_fields()
  │      │      ├─► @api.onchange() triggered
  │      │      ├─► _init() hook
  │      │      └─► SQL INSERT
  │      ├─► Post-create hooks per record
  │      └─► @api.depends triggered for computed fields
  │
  └─► Return recordset of 3 created records
```

---

## Security Context Summary

| Decorator | User Context | ACL Checked | Record Available |
|-----------|-------------|-------------|-----------------|
| `@api.depends` | Current user | ✅ Yes (read ACL on deps) | ✅ Yes |
| `@api.onchange` | Current user | ✅ Yes | ✅ Yes |
| `@api.constrains` | Current user | ✅ Yes | ✅ Yes |
| `@api.model` | **Superuser** | ❌ No | ❌ No |
| `@api.model_create_multi` | Current user | ✅ Yes | ❌ Before create |

---

## Transaction Boundary Summary

| Decorator | Inside Transaction | Rollback on Failure |
|-----------|------------------|-------------------|
| `@api.depends` | ✅ Yes (during write) | ✅ Yes |
| `@api.onchange` | ❌ No (UI only) | N/A |
| `@api.constrains` | ✅ Yes | ✅ Yes (blocks save) |
| `@api.model` | Depends on usage | Depends on usage |

---

## Common Anti-Patterns (Odoo 19)

| Anti-Pattern | Problem | Correct Alternative |
|-------------|---------|-------------------|
| `@api.multi` | Deprecated in Odoo 18+ | Remove — Odoo 19 handles recordsets |
| `@api.one` | Deprecated everywhere | Use `for rec in self:` loop |
| `@api.depends` without `store` | Recomputes every read (slow) | Add `store=True` if field is frequently accessed |
| `@api.model` for record logic | No record context | Use `@api.depends` instead |
| `@api.onchange` with `write()` | Transaction confusion | Set field values directly |

---

## Extension Points Quick Reference

| What to Extend | Override Method | Pattern |
|---------------|----------------|---------|
| Computed field logic | `_compute_<field>()` | `super()` then custom |
| Onchange cascade | `_onchange_<field>()` | `super()` then set values |
| Validation | `_check_<rule>()` | `super()` then custom check |
| Default values | `_default_<field>()` | `super()` then set default |
| Create logic | `create()` | `@api.model_create_multi` |
| Write logic | `write()` | Call `super()` first |

---

## Related

- [Flows/TEMPLATE-flow](Flows/TEMPLATE-flow.md) — Flow document template
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Workflow and state machine patterns
- [Core/BaseModel](Core/BaseModel.md) — Model foundation, inheritance, CRUD
- [Core/Fields](Core/Fields.md) — Field types, computed fields
- [Core/Exceptions](Core/Exceptions.md) — ValidationError, UserError
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — Sudo usage, ACL
- [Snippets/method-chain-example](Snippets/method-chain-example.md) — Method chain notation reference
