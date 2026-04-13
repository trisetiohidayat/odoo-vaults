# POS Sale Loyalty

## Overview

- **Name:** POS - Sales Loyalty
- **Category:** Sales/Point of Sale
- **Version:** 1.0
- **Depends:** `pos_sale`, `pos_loyalty`
- **Auto-install:** True
- **Author:** Odoo S.A.
- **License:** LGPL-3

## L1 — What This Module Does

`pos_sale_loyalty` is a **link/hub module** that resolves a behavioral conflict when both `pos_sale` and `pos_loyalty` are simultaneously installed. It ensures that loyalty reward data flows correctly from POS orders into sale orders during the POS-to-Sale synchronization process.

**The specific problem it solves:**

When `pos_sale` is installed, `SaleOrderLine._get_sale_order_fields()` returns the list of fields that get synced from `pos.order.line` back to `sale.order.line` when a POS order is linked to a quotation. `pos_loyalty` adds a `reward_id` field (and related fields) to `pos.order.line`. However, `pos_sale`'s `_get_sale_order_fields()` does not know about these loyalty fields. Without this link module, loyalty reward information is silently dropped during the POS-to-Sale sync.

---

## L2 — Field Types, Defaults, Constraints

### Models Extended

#### `sale.order.line` (via `_inherit = 'sale.order.line'`)
Inherits from `sale.order.line` (which is extended by `pos_sale`). No new fields are created; instead, the module **extends an existing method**.

### Field Additions via Method Extension

The module does not define new database fields. It extends the `_get_sale_order_fields()` method to **include additional field names** in the returned list:

| Field Name | Type | Purpose |
|------------|------|---------|
| `reward_id` | `Many2one(loyalty.reward)` | Links a POS loyalty reward to the sale order line |
| *(implicit via super())* | — | Other loyalty fields from `pos_loyalty`'s `SaleOrderLine` already added via `pos_loyalty`'s own `_load_pos_data_fields()` override |

### Defaults

No new defaults are defined. All behavior flows from the method override.

### Constraints

No new `SQL` or `@api.constrains` constraints are defined. This module relies purely on method extension.

---

## L3 — Cross-Model, Override Pattern, Workflow Trigger

### Cross-Model Architecture

```
pos_loyalty/models/pos_order_line.py
  SaleOrderLine extends sale.order.line
    ├── is_reward_line           → Boolean
    ├── reward_id                 → Many2one(loyalty.reward)
    ├── coupon_id                 → Many2one(loyalty.card)
    ├── reward_identifier_code    → Char
    └── points_cost              → Float

pos_sale/models/sale_order.py
  SaleOrderLine extends sale.order.line
    └── _get_sale_order_fields()  → returns hardcoded list WITHOUT reward_id

pos_sale_loyalty/models/sale_order.py
  SaleOrderLine extends sale.order.line  (via _inherit='sale.order.line')
    └── _get_sale_order_fields()  → calls super() + appends 'reward_id'
```

**Sync chain:**

```
pos.order.line (has reward_id, coupon_id, points_cost, is_reward_line, reward_identifier_code)
  → read() using fields from _get_sale_order_fields()
  → sale.order.line (reward_id now synced when both pos_sale + pos_loyalty installed)
```

### Override Pattern

**Pattern used:** `super()` chain — method extension (NOT field shadowing).

The module uses the classic Odoo inheritance pattern for Python method overriding:

```python
# pos_sale/models/sale_order.py — base implementation
class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'pos.load.mixin']

    def _get_sale_order_fields(self):
        # Returns a HARDCODED list of 12 field names
        return ["product_id", "display_name", "price_unit", ... "is_downpayment"]

    def read_converted(self):
        field_names = self._get_sale_order_fields()  # Called here
        ...
```

```python
# pos_sale_loyalty/models/sale_order.py — extension
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_sale_order_fields(self):
        field_names = super()._get_sale_order_fields()  # Gets base list
        field_names.append('reward_id')                  # Adds loyalty field
        return field_names
```

**Why this pattern works:** The `super()` call dynamically resolves through Python's MRO (Method Resolution Order), so even if other modules also extend `_get_sale_order_fields()`, the full chain of extensions is preserved. `read_converted()` in `pos_sale` calls `self._get_sale_order_fields()`, so any module in the MRO chain that extends the method will contribute its fields.

### Workflow Trigger

This module is triggered during the **POS-to-Sale synchronization flow**:

```
1. POS Operator creates/loads a Sale Order (quotation) in POS
   └─ pos_sale: SaleOrderLine._load_pos_data_fields() includes fields

2. POS user selects products, applies loyalty rewards
   └─ pos_loyalty: pos.order.line gets reward_id set

3. POS session closes / order synced
   └─ pos_sale: SaleOrderLine.read_converted() called
        └─ self._get_sale_order_fields() called
             └─ pos_sale_loyalty: appends 'reward_id'
             └─ reward_id data included in sale order line

4. sale.order.line in backoffice now carries loyalty reward info
```

---

## L4 — Version Changes: Odoo 18 to Odoo 19

`pos_sale_loyalty` is a minimal module. In both Odoo 18 and Odoo 19, its implementation is identical.

### What Changed in the Odoo 18 to Odoo 19 Transition

The `pos_sale_loyalty` module itself **did not change** between Odoo 18 and Odoo 19. The behavior is identical.

**However, key upstream changes in the dependency chain are worth noting:**

| Component | Odoo 18 Change | Odoo 19 Impact on This Module |
|-----------|----------------|-------------------------------|
| `sale.order.line._get_sale_order_fields()` | Still present in `pos_sale` | Module still correctly appends `'reward_id'` |
| `pos_loyalty` fields | Still defines `reward_id`, `coupon_id`, etc. on `sale.order.line` | These fields still need to be in the field list for sync |
| `_load_pos_data_fields()` in `pos_loyalty` | Still extends `super()` and adds loyalty fields | Module correctly handles the gap in `_get_sale_order_fields()` |
| `sale.order.line.read_converted()` | Still calls `self._get_sale_order_fields()` | Extension point still valid |

### Odoo 19 API Changes Relevant to This Module

| API Element | Odoo 18 | Odoo 19 | Notes |
|-------------|---------|---------|-------|
| `@api.model` on `_get_sale_order_fields` | Not decorated | Not decorated | Method has always been a regular recordset method |
| `super()` in inheritance | Standard Python MRO | Unchanged | Extension pattern is stable |
| Field list format | List of strings | Unchanged | `append()` still works |

### Conclusion

`pos_sale_loyalty` is **stable across Odoo 18 to 19**. The module exists purely as a compatibility shim and does not require changes. The underlying mechanism (`_get_sale_order_fields` as an extension hook) remains the same.

---

## Assets

- `point_of_sale._assets_pos`: Frontend assets for combined sale + loyalty POS flow
- `web.assets_tests`: Test tours for the combined flow

---

## Related

- [Modules/pos_sale](pos_sale.md) — POS + Sale integration (defines `_get_sale_order_fields`)
- [Modules/pos_loyalty](pos_loyalty.md) — POS Loyalty (defines `reward_id` field on `sale.order.line`)
