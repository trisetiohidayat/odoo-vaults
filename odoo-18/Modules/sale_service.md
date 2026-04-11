# sale_service — Sale Service

**Tags:** #odoo #odoo18 #sale #service #name-search #performance
**Odoo Version:** 18.0
**Module Category:** Sale + Service Extension
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_service` enhances the `sale.order.line` model with service-specific display logic and performance optimizations for service product name searches. It adds an `is_service` boolean field to SOL with a PostgreSQL-stored column, optimizes service line name search with a covering index, and formats service line display names with grouped pricing.

**Technical Name:** `sale_service`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_service/`
**Depends:** `sale_management`
**Inherits From:** `sale.order.line`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order_line.py` | `sale.order.line` | `is_service` field, name search optimization, grouped display name |

---

## Models Reference

### `sale.order.line` (models/sale_order_line.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `is_service` | Boolean | Stored compute: True if `product_id.type == 'service'`; PostgreSQL column created in `_auto_init()` to avoid ORM-level compute slowness |

---

#### Methods

| Method | Line | Behavior |
|--------|------|----------|
| `_domain_sale_line_service()` | 18 | Returns a canonical domain for service lines: `[('is_service', '=', True)]`. Accepts kwargs to optionally filter out expenses and non-sale state lines |
| `_compute_is_service()` | 35 | Sets `is_service = True` when `product_id.type == 'service'` |
| `_auto_init()` | 41 | Creates the PostgreSQL `is_service` column directly with SQL + `create_column`, then backfills with a JOIN on `product_template` — avoids slow ORM compute on upgrade |
| `init()` | 56 | Creates a partial index `sale_order_line_name_search_services_index` on `(order_id DESC, sequence, id)` WHERE `is_service = True` — accelerates service-specific name searches |
| `_additional_name_per_id()` | 64 | Adds grouped service display: when multiple SOLs share the same order+product and all are services, formats each line as `- <price>` (grouped pricing display) |
| `name_search()` | 83 | Optimized: when the search domain contains `('is_service', '=', True)` with `ilike` operator, uses `search_fetch()` with the covering index and `order='order_id.id DESC, sequence, id'` to avoid expensive JOIN on `sale_order` |

#### Performance Design: `_auto_init()` vs ORM

The `_auto_init()` method is a low-level PostgreSQL optimization:
```python
# Direct SQL (fast on large tables):
CREATE COLUMN IF NOT EXISTS sale_order_line.is_service ...
UPDATE sale_order_line SET is_service = (pt.type = 'service') FROM product_template pt ...

# vs ORM (slow on large tables):
@api.depends('product_id.type')
def _compute_is_service(self):
    for line in self:
        line.is_service = line.product_id.type == 'service'
```

The direct SQL approach avoids loading all SOLs into memory during upgrade/migration.

---

## Security File

No security file.

---

## Data Files

None.

---

## Critical Behaviors

1. **`is_service` Stored Column**: Rather than computing on the fly, `is_service` is stored in PostgreSQL. This makes `name_search()` and `_domain_sale_line_service()` fast for large order volumes, and enables the partial index on service lines.

2. **Partial Index for Service Search**: `sale_order_line_name_search_services_index` is a partial index — only service lines are indexed. This keeps the index small while dramatically speeding up `name_search()` for service lines specifically.

3. **Grouped Service Display**: `_additional_name_per_id()` detects groups of service lines for the same product on the same order and formats them as `- <amount>` (without the product name repeated). This produces cleaner SO print reports when the same service appears multiple times with different UoM or discounts.

4. **Domain Factory**: `_domain_sale_line_service()` is a reusable domain helper used by other modules (e.g., `sale_timesheet`, `sale_project`) to filter SOL to only service lines.

---

## v17→v18 Changes

- `is_service` field moved from transient compute to stored PostgreSQL column with `_auto_init()` direct SQL for upgrade performance on large databases
- `name_search()` optimized to use `search_fetch()` with partial index
- `_additional_name_per_id()` grouped service display logic enhanced

---

## Notes

- `sale_service` is a hidden module — not visible in the Apps list
- The `is_service` field is a key building block for `sale_timesheet`, `sale_project`, `sale_purchase` — all of which depend on `sale_management` (which transitively loads `sale_service`)
- The PostgreSQL-only column creation in `_auto_init()` is a pattern used in high-scale Odoo modules to avoid ORM bottlenecks during schema migration
