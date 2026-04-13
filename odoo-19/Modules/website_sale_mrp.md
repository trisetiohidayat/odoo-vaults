---
title: website_sale_mrp
tags:
  - odoo
  - odoo19
  - modules
  - website
  - mrp
  - stock
  - ecommerce
  - availability
  - kits
  - bom
description: "Kit product availability on eCommerce — BOM-based inventory for phantom products on the website"
---

# website_sale_mrp

> **Kit Availability** — Manage Kit (BoM) product inventory and availability status on your eCommerce store. Handles phantom BoM stock resolution, cross-kit component sharing, nested kits, and non-storable component exclusion.

## Module Information

| Property | Value |
|----------|-------|
| **Technical Name** | `website_sale_mrp` |
| **Category** | Website/Website |
| **Version** | 1.0 |
| **Summary** | Manage Kit product inventory & availability |
| **Depends** | `website_sale_stock`, `sale_mrp` |
| **Auto-install** | True |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

---

## L1: Business Concept — How Kit Products with BoM Are Sold Online

The module solves four critical availability problems when selling kit (phantom BoM) products on a website:

1. **Kit product availability**: A kit with 20 units in stock might only have 5 available if only 5 sets of components can be assembled
2. **Component cross-contamination**: When two different kits share a component, adding one kit to the cart reduces available stock for the other
3. **Nested kit resolution**: A super-kit containing a sub-kit requires both BoM levels to be exploded for correct availability
4. **Non-storable exclusion**: Consumable or service components do not consume physical warehouse stock and must be excluded

The module does **not** create any new database models. It extends `sale.order` with one method and adds one JSON-RPC endpoint. All value is in the `_get_unavailable_quantity_from_kits()` algorithm.

---

## L2: Field Types, Defaults, Constraints

No new fields are introduced by this module. It extends existing models.

### `sale.order` (extended from `website_sale_stock`)

Defined in: `models/sale_order.py`

**Single method added:**

```python
def _get_unavailable_quantity_from_kits(self, product):
    """
    Compute the quantity of `product` that is unavailable due to kit
    products already in the cart (whether `product` itself is a kit, or
    is a component of another kit in the cart).
    """
```

**Returns**: `float` — units of `product` to subtract from `product.free_qty` to get the purchasable quantity.

**Precondition**: `self.ensure_one()` — operates on a single sale order (the current website cart).

**Algorithm phases**:

1. **Phase 1** (if `product.is_kits`): Explode the kit's phantom BoM once (`explode(product, 1.0)`), building two dicts: `unavailable_component_qties` (direct cart reservations per component) and `qty_per_kit` (UoM-converted quantity per component per kit). Non-storable components and zero-qty lines are skipped.

2. **Phase 2** (all cart lines): For each cart line that is a kit (different from `product`), explode that kit and add the target product's contribution to `unavailable_qty`. If `product.is_kits`, also accumulate component sharing across kits.

3. **Phase 3** (if `product.is_kits`): Recompute kit availability from scratch using component free quantities minus all reservations. `unavailable_qty = free_qty - max_free_kit_qty`.

**Key guards**:
- `float_is_zero(bom_line_data['qty'], ...)` prevents division by zero from zero-qty BOM lines
- `if not bom_line.product_id.is_storable: continue` excludes consumables
- `sudo()` used on `_bom_find()` and `product.sudo().free_qty` for public product availability

---

## L3: Cross-Model Integration, Override Patterns, Workflow Triggers

### Cross-Model Map

| From | To | Integration |
|------|----|-------------|
| `sale.order` | `mrp.bom` (via `_bom_find()`) | Phantom BoM lookup for kit product |
| `sale.order` | `mrp.bom.line` (via `explode()`) | Component decomposition |
| `sale.order` | `product.product` (via `is_kits`, `is_storable`, `free_qty`) | Kit detection, storable check, stock availability |
| `sale.order` | `sale.order.line` (via `order_line`) | Cart line iteration for reservation tracking |
| `sale.order.line` (from `sale_mrp`) | `mrp.bom` (via `_get_bom_component_qty()`) | Cross-kit component extraction |

### Override Patterns

| Model | Pattern | Override Method |
|-------|---------|-----------------|
| `sale.order` | `_inherit = 'sale.order'` | `_get_unavailable_quantity_from_kits()` |
| `WebsiteSaleMrpVariantController` | Extends `WebsiteSaleStockVariantController` | `GET /website_sale_mrp/get_unavailable_qty_from_kits` |
| `VariantMixin` (JS) | Extends from `website_sale_stock` | `_getUnavailableQty()` |

### Controller: `WebsiteSaleMrpVariantController`

**File**: `controllers/variant.py`

```python
@route('/website_sale_mrp/get_unavailable_qty_from_kits', type='jsonrpc', auth='public', website=True)
def get_unavailable_qty_from_kits(self, product_id=None, *args, **kwargs):
    so = request.cart
    if not so:
        return 0
    product = request.env['product.product'].browse(product_id)
    return so._get_unavailable_quantity_from_kits(product)
```

| Attribute | Value | Purpose |
|-----------|-------|---------|
| **Path** | `/website_sale_mrp/get_unavailable_qty_from_kits` | Unique endpoint |
| **Type** | `jsonrpc` | JSON-RPC 2.0 |
| **Auth** | `public` | No login required |
| **Website** | `True` | Sets `website_id` in context; multi-website aware |

### Workflow Trigger: Kit Availability at Product Page Load

```
User visits product page (is_kits=True or product is component of a kit)
    ↓ (combination change event)
VariantMixin._getUnavailableQty(combination)
    ↓ RPC
/website_sale_mrp/get_unavailable_qty_from_kits {product_id}
    ↓
sale_order._get_unavailable_quantity_from_kits(product)
    ↓ (returns float)
Frontend: combination.free_qty -= unavailableQty
    ↓
add_qty max set, availability message shown
```

---

## L4: Odoo 18 → 19 Changes, Security

### Version Changes Odoo 18 → 19

**New module**: `website_sale_mrp` was **not present as a standalone module in Odoo 18**. Kit availability logic was embedded within `website_sale_stock`'s `_verify_updated_quantity` and related methods.

**Odoo 19 architectural changes**:

1. **Dedicated module extraction**: `website_sale_mrp` created as a standalone module for better separation of concerns
2. **Centralized algorithm**: `_get_unavailable_quantity_from_kits()` provides a single, comprehensive algorithm
3. **Clean JSON-RPC API**: `/website_sale_mrp/get_unavailable_qty_from_kits` provides a clear API contract
4. **`is_kits` field**: The computed boolean on `product.product` and `product.template` (refined in Odoo 19 MRP) is the foundation for kit detection
5. **`is_storable` field**: Replaces the older `type='product'` check with a more semantically clear indicator

**Key fields used from Odoo 19 MRP:**

| Field | Model | Type | Purpose |
|-------|-------|------|---------|
| `is_kits` | `product.product`, `product.template` | `Boolean` (computed) | True if product has a phantom BoM |
| `is_storable` | `product.product` | `Boolean` | True if product is tracked as physical inventory |
| `free_qty` | `product.product` | `Float` (computed) | On-hand minus reserved quantity |
| `type` | `mrp.bom` | `Selection` | `'phantom'` for kit-type BoM |

### Security

| Aspect | Status | Notes |
|--------|--------|-------|
| SQL Injection | Safe | ORM exclusively; no raw SQL |
| Access Control | Acceptable | Uses `sudo()` for BOM and stock; intentional for public product availability |
| CSRF | Safe | JSON-RPC protocol; `type='jsonrpc'` handles CSRF |
| Input Validation | Minimal | `product_id` from client; no validation before `browse()` |
| Mass Assignment | Safe | Method doesn't use `write()` or `create()` |

**`sudo()` rationale**:
- `_bom_find()` with `sudo()`: Public visitors need BOM data for availability. Phantom BoMs are public product structure.
- `product.sudo().free_qty`: For websites with public product visibility enabled, this is acceptable.

### Performance

| Operation | Queries per Call |
|-----------|-----------------|
| `_bom_find(product)` | 1 sudo search |
| `explode(product, 1.0)` | 1–2 internal searches |
| `_bom_find()` per other kit | 1 per kit line |
| `_get_bom_component_qty()` per other kit | 1 per kit line |
| `product.sudo().free_qty` | 1 |
| `component.free_qty` reads (Phase 3) | 1 per unique component |

**Worst case**: O(N + M) queries where N = kit lines in cart, M = components per kit. For typical carts (10–50 lines, 5–10 components per kit): 15–60 queries per product displayed.

**Algorithmic complexity**: O(N * M) time, O(K) space where K = unique components. Acceptable for e-commerce use cases.

### Multi-Company Considerations

Both `_bom_find()` calls pass `company_id=self.company_id.id`. This filters the BoM search to only the sale order's company — a product can have multiple phantom BoMs (one per company), and passing the wrong `company_id` could return a BoM from a different company's manufacturing rules.

### No Order State Filtering

The method operates on `self.order_line` without any state filter — all order lines are considered. In normal e-commerce usage, the cart is a `draft` sale order. This is safe because `request.cart` always returns the current session's draft cart.

---

## Data Flow Diagram

```
+------------------+  1. User selects variant
| Product Page     |     on kit product
| (website)        |
+--------+---------+
         | RPC call
         v
+------------------+  2. Controller receives
| Controller       |     /website_sale_mrp/get_unavailable_qty_from_kits
| variant.py       |     Gets request.cart (current SO)
+--------+---------+
         | call
         v
+------------------+  3. For kit product: explode BOM
| sale.order       |     Get all components (including nested)
| _get_unavailable_|     For each component: check cart lines
| quantity_from_   |     and other kits in cart
| kits()           |  4. For component product:
|                  |     Find all kits in cart that contain it
|                  |     Sum component reservation per kit
+--------+---------+
         | unavailable_qty (float)
         v
+------------------+  5. Frontend subtracts from free_qty
| VariantMixin     |     Sets add_qty max attribute
| JS              |     Shows/hides Add to Cart button
|                  |     Displays availability message
+------------------+
```

---

## Related

- [Modules/website_sale_stock](odoo-18/Modules/website_sale_stock.md) — Parent module providing base stock display on website
- [Modules/sale_mrp](odoo-18/Modules/sale_mrp.md) — Sale order + BoM integration; provides `_get_bom_component_qty()`
- [Modules/mrp](odoo-18/Modules/mrp.md) — Manufacturing module; defines `is_kits`, phantom BoMs, `explode()`
- [Modules/website_sale](odoo-18/Modules/website_sale.md) — Base eCommerce controller and variant system
- [Modules/stock](odoo-18/Modules/stock.md) — Inventory management; provides `free_qty`, `stock.quant`
- [Core/Fields](odoo-18/Core/Fields.md) — Field types used: computed Boolean (`is_kits`), Float (`free_qty`)
