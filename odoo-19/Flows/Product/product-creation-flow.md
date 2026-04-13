---
type: flow
title: "Product Creation Flow"
primary_model: product.product
trigger: "User action — Products → Create"
cross_module: false
models_touched:
  - product.product
  - product.template
  - product.category
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Product/pricelist-computation-flow](odoo-19/Flows/Product/pricelist-computation-flow.md)"
source_module: product
created: 2026-04-07
version: "1.0"
---

# Product Creation Flow

## Overview

This flow describes the full lifecycle of creating a product variant (`product.product`) in Odoo 19, from filling the form fields through the onchange cascade that propagates defaults from the product category, unit of measure, and optional product template. The primary entry point is the user clicking "Create" from `Settings → Products → Products`. The flow covers the `create()` call on `product.product`, all triggered onchange methods, route assignment, and any cross-module side effects such as stock valuation account propagation. Understanding this flow is essential before customizing product creation or writing automated tests that simulate product form submission.

## Trigger Point

**User action:** Navigate to `Settings → Products → Products` and click the **Create** button. The form opens with empty/default fields. Every field change triggers an onchange method, and clicking **Save** executes the final `create()` call.

**Alternative triggers:**
- Import via CSV/XLS (triggers `create()` directly without onchange cascade)
- Duplicating an existing product via the **Action → Duplicate** menu
- API call to `product.product.create(vals)` from external integration

---

## Complete Method Chain

```
1. product.product.create(vals)
   │
   ├─► 2. product.template.create(vals_tmpl)
   │     └─► 3. _check_company_domain() validated
   │           └─► 4. Fields from vals_tmpl written to new record
   │
   ├─► 5. IF categ_id in vals:
   │      └─► 6. _onchange_categ_id() called on template
   │            ├─► 7. picking_type_id ← categ_id.property_stock_procurement_method
   │            ├─► 8. property_stock_valuation_account_id ← categ_id.property_stock_valuation_account_id
   │            └─► 9. property_account_expense_id ← categ_id.property_account_expense_categ_id
   │                  └─► 10. property_account_income_id ← categ_id.property_account_income_categ_id
   │
   ├─► 11. IF uom_id in vals:
   │       └─► 12. _onchange_uom() called on template
   │             ├─► 13. IF type == 'service':
   │             │      └─► 14. procurement_jit ← True (auto-JIT)
   │             └─► 15. uom_po_id ← uom_id (suggested purchase UoM)
   │
   ├─► 16. IF product_variant_ids in vals (template set separately):
   │       └─► 17. _onchange_product_template_id() called on variant
   │             ├─► 18. name ← product_tmpl_id.name
   │             ├─► 19. list_price ← product_tmpl_id.list_price
   │             ├─► 20. standard_price ← product_tmpl_id.standard_price
   │             ├─► 21. description ← product_tmpl_id.description_sale
   │             └─► 22. description_purchase ← product_tmpl_id.description_purchase
   │
   ├─► 23. IF type == 'consu' OR type == 'product':
   │       └─► 24. Route selection via stock.location.route.rule matching
   │             ├─► 25. SELECT route_id FROM stock_location_route_rule
   │             │      WHERE categ_id = categ_id OR categ_id IS NULL
   │             │        AND company_id = current_company
   │             └─► 26. IF fiscal_position_id set:
   │                    └─► 27. product.product.write({'taxes_id': mapped(taxes_id)})
   │                          └─► 28. supplier_taxes_id also mapped
   │
   └─► 29. CREATE product.product record (single variant for non-configurable)
         └─► 30. Fields from vals written to product_product table
               └─► 31. Cache invalidation via env.registry.clear_caches()
```

---

## Decision Tree

```
User opens product form
│
├─► name field set?
│  ├─► NO → Name is REQUIRED — on save, ValidationError raised
│  └─► YES → proceed
│
├─► type selection (type field)?
│  ├─► 'consu' (Consumable):
│  │      └─► No stock tracking. Routes may still apply.
│  ├─► 'service' (Service):
│  │      ├─► procurement_jit forced True on UoM change
│  │      └─► No stock route assignment
│  └─► 'product' (Storable):
│         └─► Route assignment check → proceed to stock route selection
│
├─► categ_id set?
│  ├─► YES → _onchange_categ_id() fires:
│  │      ├─► property_stock_valuation_account_id pulled from category
│  │      ├─► property_account_income_id / expense_id pulled from category
│  │      └─► picking_type_id inherited
│  └─► NO → no category defaults applied, user must set manually
│
├─► uom_id set?
│  ├─► YES → _onchange_uom() fires:
│  │      ├─► uom_po_id suggested (= uom_id)
│  │      └─► IF service type → procurement_jit = True
│  └─► NO → unit defaults to 'product_uom_unit' (Unit(s))
│
├─► product_template_id set? (variant creation mode)
│  ├─► YES → _onchange_product_template_id() fires on variant
│  │      ├─► name, list_price, standard_price, description synced
│  │      └─► proceed to variant-specific fields
│  └─► NO → manual field entry for all variant properties
│
├─► fiscal_position_id set? (for tax mapping)
│  ├─► YES → taxes_id and supplier_taxes_id remapped via fiscal_position map
│  └─► NO → taxes_id written as-is from form
│
└─► ALWAYS on Save:
   └─► create() executes → product.product record written → product.template created/linked
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `product_template` | Created | `id`, `name`, `type`, `categ_id`, `list_price`, `standard_price`, `uom_id`, `active`, `company_id`, `description`, `description_sale`, `property_stock_valuation_account_id`, `property_account_income_id`, `property_account_expense_id` |
| `product_product` | Created | `id`, `product_tmpl_id`, `name`, `default_code`, `barcode`, `active`, `type`, `list_price`, `standard_price`, `uom_id`, `combination_indices` |
| `stock_location_route_product_rel` | Updated (if routes assigned) | `product_id`, `route_id` |
| `product_category` | Read (no change) | Category fields read to populate defaults |
| `uom_uom` | Read (no change) | UoM category checked for consistency |
| `account.account` | Read (no change) | Valuation account read from category |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Name not set on Save | `ValidationError` ("The name is required") | ORM `required=True` on `product.template.name` |
| Duplicate product name | `UserError` (warning dialog) | Duplicate name detection via `_onchange_default_code()` or custom constraint |
| UoM category mismatch | `UserError` ("Inconsistent UoM category") | UoM in `uom_po_id` must share same category as `uom_id` — enforced by `_onchange_uom()` |
| Negative list_price | `ValidationError` ("Price must be positive") | `@api.constrains('list_price')` on `product.template` |
| Negative standard_price | `UserError` ("Cost must be positive") | `_onchange_standard_price()` on variant |
| Circular category parent | `ValidationError` ("Error! You cannot create recursive categories.") | `_check_category_recursion()` on `product.category` |
| product_product barcode duplicate | `ValidationError` ("Barcode already assigned") | `_check_barcode_uniqueness()` via SQL constraint |
| `categ_id` points to inactive category | `UserError` ("Category is inactive") | `active = True` check in `_onchange_categ_id()` if category lookup fails |
| No company access for product creation | `AccessError` | ACL: `group_product_manager` or `base.group_user` required |
| Trying to delete product linked to open SO/PO | `UserError` | `unlink()` check via `stock.move.line` / `sale.order.line` existence |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Template created | `product.template` | One template record per product created (via `_inherits`) |
| Route assignment | `stock.location.route.product_rel` | Many2many link created if routes were set |
| Valuation account inherited | `product.template` | `property_stock_valuation_account_id` set from category on onchange |
| Incoming/outgoing picking type from category | `stock.picking.type` | Read by `_onchange_categ_id()` to suggest receipt/delivery types |
| Company-dependent standard_price | `product.product` | `standard_price` stored per company via `company_dependent` context |
| Mail follower subscription | `mail.followers` | Creator added as follower if `mail.thread` enabled |
| Activity created | `mail.activity` | If `mail.activity.mixin` active — product generates activity |
| Image stored | `ir_attachment` | Product image uploaded and linked as `ir.attachment` |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| Form open | Current user | Read on `product.product`, `product.template` | Kanban/list view ACL |
| `_onchange_categ_id()` | Current user | Read on `product.category`, `stock.location.route` | Only visible data used |
| `_onchange_uom()` | Current user | Read on `uom.uom` | No write |
| `_onchange_product_template_id()` | Current user | Read on `product.template` | No write during onchange |
| `create()` | Current user | Write on `product.product`, `product.template` | Requires `product.manager` group for full fields |
| Route assignment write | Current user | Write on `stock.location.route` | Needs `stock.group_stock_user` |
| Fiscal position mapping | Current user | Read on `account.fiscal.position` | Needs `account.group_account_user` |
| `write()` for tax mapping | Current user | Write on `product.product.taxes_id` | Requires tax write rights |

**Key principle:** All onchange methods run as the **current logged-in user**, respecting record rules. The `create()` call runs as the current user unless the code explicitly calls `sudo()` (not used in standard product creation).

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-6     ✅ INSIDE transaction  — product.template create + write
Steps 7-22    ✅ INSIDE transaction  — onchange methods (read-only or
                                         dependent field writes within same create())
Step 23-26    ✅ INSIDE transaction  — route matching and write
Step 27-28    ✅ INSIDE transaction  — fiscal position tax mapping write
Steps 29-31   ✅ INSIDE transaction  — product.product create + cache clear
Mail/Activity creation  ❌ Within ORM but logically part of transaction
                         (mail.followers written inside transaction via create())
Image upload   ❌ OUTSIDE transaction — via ir_attachment.create() + cron
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| `product.template.create()` | Atomic | Rollback entire transaction if template create fails |
| `_onchange_categ_id()` | Atomic (during create) | Rolled back if category lookup fails |
| `product.product.create()` | Atomic | Rollback on any constraint error |
| Route assignment `write()` | Atomic (same tx) | Rolled back with product creation |
| Fiscal position mapping | Atomic (same tx) | Rolled back with product creation |
| Mail follower write | Atomic (same tx via `create()`) | Rolled back with product creation |
| Image attachment upload | Outside ORM | Independent of product create; may orphan attachment |

**Rule of thumb:** All `product.product.create()` and its cascade — including all onchange-triggered field writes, route assignments, and tax mapping — execute **within a single database transaction**. The transaction commits only on successful form save. Any exception before commit causes a full rollback.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click Save button | Odoo 19 disables the save button after first click; only one `create()` fires. Safe. |
| Re-save product with same values | `write()` re-runs on existing record, no new record created, no error. |
| Duplicate action on same product | `copy()` creates a new product with "(copy)" suffix appended to name — no duplicate name constraint violation. |
| Calling `create()` with same vals twice in row | Two distinct records created; second has no name conflict unless unique constraint on `default_code + company_id` added |
| API call race condition: two `create()`s simultaneously | Both may succeed if name/default_code are different; unique constraint on `default_code + company_id` would cause one to fail |
| Re-trigger route assignment on already-saved product | `write()` re-runs route assignment — no side effect if routes already linked (idempotent for Many2many) |

**Non-idempotent operations in this flow:**
- **Sequence increment**: Not applicable to product creation (no sequence used)
- **Log creation**: If audit log module is installed, each create() logs a new entry — intended behavior
- **Image attachment**: Re-saving a product with a new image uploads a new attachment; old attachment is not auto-deleted

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Pre-create | `_fields_get()` or `default_get()` | Set dynamic defaults before form renders | self, fields_list | Extend `default_get()` on `product.product` |
| Pre-create | `_onchange_categ_id()` override | Add custom category-based defaults | self | `super()._onchange_categ_id()` then add fields |
| Pre-create | `_onchange_uom()` override | Customize UoM-dependent behavior | self | `super()._onchange_uom()` then add behavior |
| Variant sync | `_onchange_product_template_id()` | Customize what syncs from template to variant | self | Override with additional field syncs |
| Post-create | `create()` override | Add post-creation logic after record written | vals | `super().create(vals)` then custom write |
| Route assignment | `_search_routes_for_product()` | Custom route matching logic | self, categ_id, type | Replace route search domain |
| Tax mapping | `_get_product_taxes()` | Customize fiscal position mapping | self, taxes_id, fiscal_pos | Override fiscal position application |

**Standard override pattern:**
```python
# CORRECT — extends with super()
def _onchange_categ_id(self):
    result = super()._onchange_categ_id()
    # your additional field writes
    self.type = 'product'  # example: force type from category
    return result

# CORRECT — extend create()
def create(self, vals):
    record = super().create(vals)
    if vals.get('type') == 'product':
        record._set_default_routes()
    return record
```

**Deprecated override points to avoid:**
- `@api.one` anywhere (removed in Odoo 19)
- `@api.multi` on overridden methods (deprecated, use regular def)
- Overriding `create()` to call `sudo()` unconditionally — breaks ACL tracking
- XML workflow `<record>` overrides for `create`/`write` (workflow engine deprecated)

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `create()` | `unlink()` | `record.unlink()` | Fails if product used in open SO/PO/stock moves; cascade deletes template |
| `create()` | `action_archive()` | `record.action_archive()` | Soft-delete: product and template set `active=False`; still queryable |
| Route assignment | `write({'route_ids': [(5,)]})` | `record.write({'route_ids': [(5, 0, 0)]})` | Removes all routes — unlinks from m2m, no cascade |
| Tax mapping write | `write({'taxes_id': False})` | `record.write()` | Resets taxes to no selection |
| Category change after create | `write({'categ_id': new_id})` | `record.write()` | Does NOT retroactively change valuation account — only future receipts inherit |
| UoM change after create | `write({'uom_id': new_id})` | `record.write()` | Changes UoM but does not convert existing stock quantities |

**Important:** Product creation is **fully reversible** until the product is used in a business transaction. Once the product appears in `stock.move`, `sale.order.line`, `purchase.order.line`, or `account.move.line`, deletion is blocked by ORM constraints and must be done via archiving.

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | Form create button | Interactive | Per product |
| Import | `base_import.import` records | CSV/XLS/SQL | Bulk |
| Duplicate | `product.product.copy()` | Action menu | Per product |
| API | `product.product.create(vals)` | External system | Per call |
| Automated action | `base.automation` rule | On condition match | Rule-based |
| BOM creation | `mrp.bom.create()` auto-creates components | MRP module | Per BOM |
| Kit product line | `sale.order.line` with kit product | SO confirmation | Per SO line |
| Product kit exploded | `mrp.bom.explode()` | MO production | Per MO |

**For AI reasoning:** When asked "what happens if X creates a product?", trace all paths — the form, API, and import channels all converge on the same `create()` method.

---

## Related

- [Modules/product](odoo-18/Modules/product.md) — Module reference
- [Flows/Product/pricelist-computation-flow](odoo-19/Flows/Product/pricelist-computation-flow.md) — Pricelist price computation after product created
- [Flows/Stock/receipt-flow](odoo-17/Flows/Stock/receipt-flow.md) — Stock receipt flow using product
- [Core/API](odoo-18/Core/API.md) — @api.depends, @api.onchange decorator patterns
- [Core/BaseModel](odoo-18/Core/BaseModel.md) — _inherit vs _inherits delegation pattern
- [Patterns/Inheritance Patterns](odoo-18/Patterns/Inheritance Patterns.md) — Delegation inheritance for product.product → product.template