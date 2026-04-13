---
tags: [odoo, odoo19, modules, website, e-commerce, inventory, stock, sale]
description: "Product inventory display and availability management on eCommerce storefront"
---

# website_sale_stock

> **Product Availability** — Manage product inventory & availability status in the eCommerce store. Supports out-of-stock blocking, threshold warnings, back-in-stock notifications, combo product stock limits, multi-warehouse per website, and Google Merchant Center integration.

## Module Information

| Property | Value |
|----------|-------|
| Category | Website/Website |
| Depends | `website_sale`, `sale_stock`, `stock_delivery` |
| Auto-install | True |
| Author | Odoo S.A. |
| License | LGPL-3 |

## Purpose

`website_sale_stock` bridges [Modules/stock](Modules/stock.md) (warehouse/inventory) and [Modules/website_sale](Modules/website_sale.md) (eCommerce storefront). It makes real-time stock quantities visible to online shoppers and enforces inventory-based selling rules: blocking checkout when stock is insufficient, capping cart quantities, notifying customers on replenishment, and computing combo product limits.

Unlike `sale_stock` (which provides `free_qty` on products) or `stock` (which manages quants and moves), this module does **not** implement its own stock tracking. It purely consumes `free_qty` from the ORM and enriches it with website-specific context, cart integration, and UI concerns.

---

## Table of Contents

1. [Architecture & Dependency Chain](modules/website_sale_stock#architecture.md)
2. [All Models — Full Field & Method Reference](modules/website_sale_stock#models-all.md)
3. [L3: Core Method Deep Dives](modules/website_sale_stock#method-deep.md)
4. [L4: Performance, Multi-Website, Odoo 18→19 Changes, Security](modules/website_sale_stock#l4-escalation.md)
   - [4.1 Performance Considerations](modules/website_sale_stock#l4-perf.md)
   - [4.2 Multi-Website Stock Isolation](modules/website_sale_stock#l4-multiwh.md)
   - [4.3 Odoo 18 to 19 Changes](modules/website_sale_stock#l4-o18-o19.md)
   - [4.4 Security Analysis](modules/website_sale_stock#l4-security.md)
   - [4.5 Edge Cases](modules/website_sale_stock#l4-edge.md)
   - [4.6 Schema.org / Structured Data](modules/website_sale_stock#l4-schema.md)
   - [4.7 The `isQuantityAllowed` System — Frontend Architecture](modules/website_sale_stock#l4-frontend-arch.md)
   - [4.8 Cron Job — `ir_cron_send_availability_email`](modules/website_sale_stock#l4-cron.md)
5. [Controllers](modules/website_sale_stock#controllers.md)
6. [JavaScript Frontend](modules/website_sale_stock#frontend.md)
7. [Views & XML](modules/website_sale_stock#views-xml.md)
8. [Test Coverage](modules/website_sale_stock#tests.md)
9. [Snippets & Recipes](modules/website_sale_stock#snippets.md)

---

## 1. Architecture & Dependency Chain

### 1.1 Dependency Tree

```
website_sale_stock
  ├── website_sale          ← Product display, cart, combination info framework
  ├── sale_stock            ← sale.order.warehouse_id, free_qty on product.product
  │     ├── sale
  │     ├── stock           ← free_qty, virtual_available fields
  │     └── product
  └── stock_delivery        ← Picking creation from website orders
```

**Key architectural note:** `sale_stock` provides `sale.order._compute_warehouse_id()`, which `website_sale_stock` overrides for website orders. Without `sale_stock`, that override would crash on a missing method. Similarly, `stock_delivery` provides picking creation logic that this module extends with `website_id` tracking.

### 1.2 File Map

```
website_sale_stock/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── main.py              ← /shop/add/stock_notification endpoint
│   ├── variant.py           ← Context injection for combination info
│   └── website_sale.py      ← _prepare_product_values override
├── models/
│   ├── __init__.py
│   ├── product_template.py  ← product.template extension
│   ├── product_product.py   ← product.product extension
│   ├── product_combo.py     ← product.combo extension
│   ├── product_feed.py      ← product.feed (GMC) extension
│   ├── product_ribbon.py     ← product.ribbon extension
│   ├── sale_order.py        ← sale.order extension
│   ├── sale_order_line.py   ← sale.order.line extension
│   ├── stock_picking.py      ← stock.picking extension
│   ├── website.py            ← website extension
│   └── res_config_settings.py ← res.config.settings extension
├── views/
│   ├── product_template_views.xml    ← Product form: stock fields
│   ├── res_config_settings_views.xml ← Settings: inventory defaults
│   ├── website_sale_stock_templates.xml
│   ├── stock_picking_views.xml        ← Picking: website_id field
│   └── website_pages_views.xml
├── data/
│   ├── ir_cron_data.xml          ← Cron: _send_availability_email() hourly
│   ├── template_email.xml         ← QWeb email for back-in-stock notification
│   └── website_sale_stock_demo.xml
├── tests/
│   ├── common.py                  ← Test base class
│   └── [11 test files]            ← Coverage for all major features
└── static/src/
    ├── interactions/website_sale.js ← WebsiteSale patch: stock notification UI
    ├── js/
    │   ├── variant_mixin.js       ← _onChangeCombinationStock handler
    │   ├── models/product_product.js ← ProductProduct.isQuantityAllowed
    │   ├── product/product.js      ← Product.isOutOfStock
    │   ├── product_card/product_card.js
    │   ├── combo_configurator_dialog/*
    │   ├── product_configurator_dialog/*
    │   └── tours/*
    └── xml/website_sale_stock_product_availability.xml ← QWeb template
```

---

## 2. All Models — Full Field & Method Reference

### 2.1 `product.template` — Extended

**Inherits:** `product.template`
**File:** `models/product_template.py`

Adds four fields controlling product availability display. All fields are `invisible="not is_storable"` in views — they are irrelevant for consumable/service products.

#### Fields Added

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `allow_out_of_stock_order` | `Boolean` | `True` | If `False`, the product cannot be added to the cart when `free_qty <= 0`. If `True`, selling continues regardless of stock. |
| `available_threshold` | `Float` | `5.0` | Quantity below which the "limited availability" warning badge appears. In the product's base UoM. |
| `show_availability` | `Boolean` | `False` | If `True`, the exact available quantity is rendered on the product page when below the threshold. |
| `out_of_stock_message` | `Html` | `False` | Custom HTML message shown instead of the default "Out of Stock" badge. Translated via `translate=html_translate`. |

#### Method Overrides

**`_is_sold_out()`**
```python
def _is_sold_out(self) -> bool
```
Returns `True` if:
1. The product is storable (`is_storable = True`)
2. `allow_out_of_stock_order` is `False`
3. The first variant's free quantity is zero

Non-storable products and products with `allow_out_of_stock_order = True` are never considered sold out.

**`_website_show_quick_add()`**
```python
def _website_show_quick_add(self) -> bool
```
Extends parent. Returns `False` when the product is sold out, preventing the "quick add" button from appearing.

**`_get_additionnal_combination_info(product_or_template, quantity, uom, date, website)`** *(L3 coverage below)*

**`_get_additional_configurator_data(product_or_template, date, currency, pricelist, *, uom=None, **kwargs)`** *(L3 coverage below)*

---

### 2.2 `product.product` — Extended

**Inherits:** `product.product`
**File:** `models/product_product.py`

#### Fields Added

| Field | Type | Relation | Description |
|-------|------|----------|-------------|
| `stock_notification_partner_ids` | `Many2many` | `res.partner` via `stock_notification_product_partner_rel` | Partners who requested an email notification when this product is back in stock |

#### Method Definitions

**`_has_stock_notification(partner)`**
```python
def _has_stock_notification(self, partner) -> bool
```
Returns `True` if the given partner is already in `stock_notification_partner_ids`. Used to avoid duplicate subscriptions.

**`_get_max_quantity(website, sale_order, **kwargs)`**
```python
def _get_max_quantity(self, website, sale_order, **kwargs) -> float | None
```
Returns the maximum quantity the customer can still add to the cart: `free_qty - cart_qty`. Returns `None` if the product is storable but does **not** enforce stock limits (`allow_out_of_stock_order = True`), meaning the cart is unlimited. Returns `None` for non-storable products.

**`_is_sold_out()`**
```python
def _is_sold_out(self) -> bool
```
Returns `True` if the product is storable, `allow_out_of_stock_order` is `False`, and `free_qty <= 0` under the current website's warehouse. Uses `self.env['website'].get_current_website()` to resolve the warehouse.

**`_website_show_quick_add()`**
```python
def _website_show_quick_add(self) -> bool
```
Extends parent. Returns `False` when the product is sold out.

**`_send_availability_email()`**
```python
def _send_availability_email()
```
Scheduled method (hourly cron). Iterates all products that have at least one partner in `stock_notification_partner_ids`. For each product that is **not** sold out, sends an availability email to all waiting partners and removes them from the list. Called with `model._send_availability_email()` from the cron XML.

**`_to_markup_data(website)`**
```python
def _to_markup_data(self, website) -> dict
```
Overrides the parent Schema.org structured data method to add `offers.availability`. If not sold out, sets `'https://schema.org/InStock'`; otherwise `'https://schema.org/OutOfStock'`. Only applies to storable product variants.

---

### 2.3 `sale.order` — Extended

**Inherits:** `sale.order`
**File:** `models/sale_order.py`

#### Method Overrides

**`_compute_warehouse_id()`**
```python
def _compute_warehouse_id()
```
Overrides the parent from `sale_stock`. For non-website orders, delegates to the parent. For website orders: uses `website_id.warehouse_id` if set, then falls back to the parent method, then to `user._get_default_warehouse_id()` if still unset.

**`_verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)`** *(L3 coverage below)*

**`_check_cart_is_ready_to_be_paid()`**
```python
def _check_cart_is_ready_to_be_paid() -> bool
```
Overrides parent. Iterates all order lines, calls `line._check_availability()` for each, collects non-empty `shop_warning` values, and raises `ValidationError(' '.join(warnings))` if any exist. This is the server-side last-resort guard before payment proceeds.

**`_filter_can_send_abandoned_cart_mail()`**
```python
def _filter_can_send_abandoned_cart_mail() -> recordset
```
Overrides parent. Chains to `super()` then filters to orders where `_all_product_available()` returns `True`. Ensures abandoned cart emails never promote products that are unavailable.

**`_all_product_available()`**
```python
def _all_product_available() -> bool
```
Returns `True` if there are no order lines or if no product in the order is sold out (`not any(product._is_sold_out() for product in lines.product_id)`).

#### Helper Methods

**`_get_cart_and_free_qty(product)`**
```python
def _get_cart_and_free_qty(self, product) -> tuple[float, float]
```
Returns `(cart_qty, free_qty)` for the product in the context of this order. Both quantities are in the product's base UoM. Calls `_get_cart_qty()` and `_get_free_qty()`.

**`_get_free_qty(product)`**
```python
def _get_free_qty(self, product) -> float
```
Returns `product.free_qty` using `_get_shop_warehouse_id()` in context. If no warehouse is set on the website, `free_qty` aggregates across all warehouses.

**`_get_shop_warehouse_id()`**
```python
def _get_shop_warehouse_id() -> int | False
```
Returns `self.website_id.warehouse_id.id`. If the website has no warehouse set, returns `False`, causing `free_qty` to be computed across all warehouses.

**`_get_cart_qty(product_id)`**
```python
def _get_cart_qty(self, product_id) -> float
```
Sums quantities of all order lines for the given product ID, with UoM conversion to the product's base UoM. Returns `0.0` for empty recordsets.

**`_get_common_product_lines(product_id=None)`**
```python
def _get_common_product_lines(self, product_id=None) -> recordset
```
Filters `order_line` to lines where `product_id.id == product_id`. Used by `_get_cart_qty()` to aggregate line quantities.

---

### 2.4 `sale.order.line` — Extended

**Inherits:** `sale.order.line`
**File:** `models/sale_order_line.py`

This model does not add new stored fields. It extends existing behavior by defining `_check_availability()` and helper methods. The `shop_warning` field used here is inherited from `sale_stock`'s extension of `sale.order.line`.

#### Method Definitions

**`_set_shop_warning_stock(desired_qty, new_qty, save=True)`**
```python
def _set_shop_warning_stock(self, desired_qty, new_qty, save=True) -> str
```
Constructs a translatable warning message: `"You ask for {desired_qty} {product_name} but only {new_qty} is available"`. If `save=True` (default), writes it to `self.shop_warning` and returns it. If `save=False`, returns it without persisting. The caller uses the return value as the RPC warning message.

**`_get_max_line_qty()`**
```python
def _get_max_line_qty(self) -> float | None
```
Returns the maximum quantity that can still be added to this line: `product_uom_qty + max_quantity`. Returns `None` if the product has no max quantity limit.

**`_get_max_available_qty()`**
```python
def _get_max_available_qty(self) -> float | None
```
For combo products: iterates `_get_lines_with_price()` (lines from the same order with the same combo price), filters to storable items that don't allow out-of-stock orders, and computes `(free_qty - cart_qty)` for each. Returns `min(max_quantities)` or `None` if any item has no limit. For non-combo products, delegates to `product._get_max_quantity()`.

**`_check_availability()`**
```python
def _check_availability(self) -> bool
```
Returns `True` if the line is OK. Returns `False` and sets `shop_warning` if: the product is storable, does not allow out-of-stock orders, and `cart_qty > free_qty`.

---

### 2.5 `stock.picking` — Extended

**Inherits:** `stock.picking`
**File:** `models/stock_picking.py`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `website_id` | `Many2one(website)` (related + stored) | Readonly field linked to `sale_id.website_id`; used for reporting and multi-website picking tracking |

The field is `readonly=True` and `store=True` with a `related` path. It appears in the picking form view via `stock_picking_views.xml`, grouped under the "Extra" page.

---

### 2.6 `product.combo` — Extended

**Inherits:** `product.combo`
**File:** `models/product_combo.py`

#### Method Overrides

**`_get_max_quantity(website, sale_order, **kwargs)`**
```python
def _get_max_quantity(self, website, sale_order, **kwargs) -> float | None
```
Returns the maximum quantity of this combo that can be added to the cart. The maximum is the **maximum** across all combo item max quantities — the least-constrained item sets the ceiling. If any combo item has no limit (`None`), the entire combo has no limit.

```python
max_quantities = [item.product_id._get_max_quantity(website, sale_order, **kwargs)
                  for item in self.combo_item_ids]
# If ANY item is unlimited (None), the combo is unlimited
# Otherwise: return the MAXIMUM across items (least constrained item)
return max(max_quantities) if (None not in max_quantities) else None
```

> Note: The `_get_max_quantity` on the combo returns the **maximum** (least constrained item). However, `product.template._get_additionnal_combination_info` then takes `min()` across all combos on the template — the **minimum** across combos (the most constrained combo). This two-level bottleneck: combo items are capped by their own stock, then the template takes the combo with the lowest ceiling.

---

### 2.7 `product.feed` — Extended

**Inherits:** `product.feed`
**File:** `models/product_feed.py`

#### Method Overrides

**`_prepare_gmc_stock_info(product)`**
```python
def _prepare_gmc_stock_info(self, product) -> dict
```
Overrides the Google Merchant Center (GMC) stock info from `website_sale`. If `product._is_sold_out()` returns `True`, sets `stock_info['availability'] = 'out_of_stock'`. Otherwise leaves the parent behavior unchanged.

---

### 2.8 `product.ribbon` — Extended

**Inherits:** `product.ribbon`
**File:** `models/product_ribbon.py`

#### Fields Modified

| Field | Modification | Purpose |
|-------|--------------|---------|
| `assign` | Added `selection_add=[('out_of_stock', "when out of stock")]` with `ondelete='cascade'` | New automatic ribbon assignment mode |

#### Method Overrides

**`_is_applicable_for(product, price_data)`**
```python
def _is_applicable_for(self, product, price_data) -> bool
```
Extends parent logic. Returns `True` if the ribbon's `assign == 'out_of_stock'` AND the product is sold out AND `allow_out_of_stock_order = False`. This makes the ribbon auto-apply when a non-continuously-sold product runs out of stock.

---

### 2.9 `res.config.settings` — Extended

**Inherits:** `res.config.settings`
**File:** `models/res_config_settings.py`

Provides system-wide defaults for newly created storable products.

#### Fields Added

| Field | Type | Default | Default Model | Description |
|-------|------|---------|---------------|-------------|
| `default_allow_out_of_stock_order` | `Boolean` | `True` | `product.template` | Applied as default when creating new storable products |
| `default_available_threshold` | `Float` | `5.0` | `product.template` | Applied as default threshold for new products |
| `default_show_availability` | `Boolean` | `False` | `product.template` | Applied as default visibility for new products |
| `website_warehouse_id` | `Many2one(stock.warehouse)` | — | — | Per-website warehouse; related to `website_id.warehouse_id` with `readonly=False` and company domain |

---

### 2.10 `website` — Extended

**Inherits:** `website`
**File:** `models/website.py`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `warehouse_id` | `Many2one(stock.warehouse)` | Warehouse whose stock is used for availability checks on this website |

#### Method Definitions

**`_get_product_available_qty(product, **kwargs)`**
```python
def _get_product_available_qty(self, product, **kwargs) -> float
```
Returns `product.free_qty` with the website's warehouse in context: `product.with_context(warehouse_id=self.warehouse_id.id).free_qty`. This is the primary stock lookup used before the checkout step (on the product page and product card). During checkout, `sale.order._get_free_qty()` uses the order's warehouse instead. If no warehouse is set, `free_qty` aggregates across all warehouses.

---

## 3. L3: Core Method Deep Dives

### 3.1 `_get_additionnal_combination_info` — How Stock Flows to the Frontend

> **Context key trigger:** `website_sale_stock_get_quantity`

This method (note: intentional Odoo typo, not `additional`) is called by the RPC endpoint that serves product combination info to the JavaScript frontend. Without the `website_sale_stock_get_quantity` context key, stock data is skipped entirely — this is the short-circuit guard.

**Call chain:**
```
VariantMixin._getCombinationInfo (JS, RPC /shop/combination_info)
  → WebsiteSaleStockVariantController.get_combination_info_website()
       [sets context: website_sale_stock_get_quantity=True]
  → WebsiteSaleVariantController.get_combination_info_website() [parent]
       → product.product._get_combination_info_variant() [parent]
            → product.template._get_additionnal_combination_info()
                 [website_sale_stock checks context here]
                 [adds stock fields to res dict]
```

**What gets added to `res` for storable product variants:**

```python
{
    'is_storable': True,
    'allow_out_of_stock_order': product_or_template.allow_out_of_stock_order,
    'available_threshold': product_or_template.available_threshold,
    # Only if is_product_variant:
    'free_qty': float_round(computed_qty, precision_digits=0, rounding_method='DOWN'),
    'cart_qty': product_uom._compute_quantity(request.cart._get_cart_qty(...), to_unit=uom),
    'uom_name': uom.name,
    'uom_rounding': uom.rounding,
    'show_availability': product_sudo.show_availability,
    'out_of_stock_message': product_sudo.out_of_stock_message,
    'has_stock_notification': has_stock_notification,
    'stock_notification_email': stock_notification_email,
}
```

**For non-variant (template-level) calls:** `free_qty` and `cart_qty` are both `0`. This is intentional — no meaningful stock info exists without a specific variant selected.

**For combo products:** `res['max_combo_quantity'] = min([combo._get_max_quantity() for ...])`. If none of the combos has a max quantity, this key is absent.

**The `has_stock_notification` logic:**
```python
has_stock_notification = (
    product_sudo._has_stock_notification(self.env.user.partner_id)  # Logged-in user
    or (
        request
        and product_sudo.id in request.session.get(
            'product_with_stock_notification_enabled', set()
        )
    )  # Public user (session-based)
)
```

### 3.2 `available_quantity` for Website — Warehouse Selection Per Website

The module implements a **two-tier warehouse selection strategy**:

**Tier 1 — Shop Display (product page, product card):**
```python
website._get_product_available_qty(product)
  └── product.with_context(warehouse_id=self.warehouse_id.id).free_qty
```

**Tier 2 — Cart/Checkout:**
```python
sale.order._get_free_qty(product)
  └── product.with_context(warehouse_id=self._get_shop_warehouse_id()).free_qty
        └── Returns self.website_id.warehouse_id.id
```

**Tier 3 — Order Confirmation (warehouse assignment):**
```python
sale.order._compute_warehouse_id()
  └── order.warehouse_id = order.website_id.warehouse_id  (if website has one)
```

**If no warehouse is set on the website:**
- `_get_shop_warehouse_id()` returns `False`
- `with_context(warehouse_id=False)` removes the warehouse filter
- `free_qty` aggregates across **all** warehouses (standard Odoo behavior)
- The picking created from the order will still use the order's assigned warehouse

### 3.3 Add to Cart Availability Check — `_verify_updated_quantity`

The algorithm for validating cart quantity changes:

```
Input: product_id, new_qty, uom_id, existing order_line (if updating)

Step 1: Fetch product + UoM
Step 2: Get (cart_qty, free_qty) for the product at the order's warehouse
Step 3: Convert both to requested UoM (cart_qty with rounding, free_qty without, then floor)
Step 4: Compute total_cart_qty = cart_qty + (new_qty - old_qty)
Step 5: If free_qty >= total_cart_qty:
           call super()  → allow the quantity
       Else:
           allowed_qty = free_qty - (cart_qty - old_qty)
           Generate contextual warning:
             - Line exists + allowed > 0: "You ask for N products but only M is available."
             - Line exists + allowed <= 0: "Some products became unavailable and your cart has been updated."
             - No line + allowed > 0: "You ask for N products but only M is available."
             - No line + allowed <= 0: "{product_name} has not been added to your cart since it is not available."
           Return (allowed_qty, warning)
```

**Critical nuance:** `allowed_line_qty` is recalculated from free quantity minus what's **already in the cart excluding the current line** (`cart_qty - old_qty`). This ensures the line's existing quantity is counted correctly when capping.

**UoM rounding notes:**
- `product_qty_in_cart` is converted to requested UoM with default rounding
- `available_qty` is converted **without rounding**, then rounded **down** (`float_round(..., rounding_method='DOWN')`) to an integer. This ensures fractional quantities never allow one extra unit due to floating-point imprecision

### 3.4 Checkout Stock Validation — `_check_cart_is_ready_to_be_paid`

This is the **final server-side guard** before payment. It is called during the payment processing step. The workflow:

```
Customer clicks "Pay"
  → _check_cart_is_ready_to_be_paid()
       → For each order_line:
            → line._check_availability()
                 → If cart_qty > free_qty:
                      → _set_shop_warning_stock(...)  [sets shop_warning]
                      → return False
       → Collect all non-empty shop_warning values
       → If any warnings: raise ValidationError(joined_warnings)
       → Else: super() → proceed to payment
```

This is a last-resort check because the frontend should already prevent exceeding available stock via `_onChangeCombinationStock` in JavaScript. However, race conditions (two customers adding the last item simultaneously) or direct API calls can bypass the frontend, making server-side validation essential.

### 3.5 Combo Product Stock — Ceiling Pattern (Combo Level) + Bottleneck (Template Level)

For a single combo, the max quantity is the **maximum** across its items (the least-constrained item sets the ceiling). If ANY combo item has no stock enforcement (`allow_out_of_stock_order = True`), the entire combo is unlimited.

```
Combo: Pizza + Drink + Dessert
  Pizza item max: free_qty=5
  Drink item max: unlimited (allow_out_of_stock_order=True)
  Dessert item max: free_qty=3

  => max(5, None, 3) = None  [unlimited because Drink is unlimited]
  => User can add unlimited combos
```

When all items enforce stock:
```
  => max(5, 10, 3) = 5  [Pizza is the ceiling — least constrained]
  => User can add at most 5 of this combo
```

Then, at the template level, `_get_additionnal_combination_info` takes `min()` across all combos:
```
  Combo A ceiling: 5 units
  Combo B ceiling: 2 units
  => template returns min(5, 2) = 2
  => max_combo_quantity = 2 (the most constrained combo)
```

The `sale.order.line._get_max_available_qty()` does the opposite: it takes `min()` across all **items** within a single combo line, reflecting that a single combo line's limit is the most constrained item within it. This distinction matters for the cart line-level vs. template-level computations.

### 3.6 Out-of-Stock Ribbon Auto-Assignment

The `product.ribbon` extension adds a new `assign = 'out_of_stock'` mode:
- Automatically displayed when: `assign == 'out_of_stock' AND not allow_out_of_stock_order AND _is_sold_out()`
- No manual product assignment needed — the ribbon self-activates based on stock state
- `ondelete='cascade'` ensures orphaned `'out_of_stock'` values are removed if ribbons are deleted

---

## 4. L4: Performance, Multi-Website, Odoo 18 to 19 Changes, Security {#l4-escalation}

### 4.1 Performance Considerations {#l4-perf}

#### 4.1.1 `_get_additionnal_combination_info` — Call Frequency and Cost

This method is invoked on **every variant combination change** — each time a customer selects a size/color on the product page, the JS makes an RPC call to `get_combination_info_website`. The server executes:

1. `website._get_product_available_qty(product)` → `product.with_context(warehouse_id=...).free_qty` → triggers `stock.quant` aggregation SQL
2. `request.cart._get_cart_qty(product_id)` → sum of order lines for this product
3. UoM conversion + float rounding
4. For combos: N × `_get_max_quantity()` calls, each triggering another `free_qty` query

**Typical query count per variant change (no combo):** 2-3 queries (product free_qty, cart lines sum, possibly warehouse resolution). For a combo product with 8 items: ~10 queries per variant change. This is acceptable for interactive use but can be a bottleneck on high-traffic product pages with complex combos.

**Context short-circuit guard:**
```python
if not self.env.context.get('website_sale_stock_get_quantity'):
    return res
```
Without the context set by `WebsiteSaleStockVariantController`, the entire stock computation block is skipped. This is intentional: it prevents stock queries during non-shop contexts like backend product form rendering or the product configurator preview (unless explicitly needed). The context is set only for the frontend combination info RPC.

#### 4.1.2 `_send_availability_email()` — Hourly N+1 Analysis

```python
for product in self.search([('stock_notification_partner_ids', '!=', False)]):
    if product._is_sold_out():
        continue
    for partner in product.stock_notification_partner_ids:
        # ... render email ...
        mail = self_ctxt.env['mail.mail'].sudo().create(mail_values)
        mail.send(raise_exception=False)
        product.stock_notification_partner_ids -= partner
```

This is an intentional O(n*m) operation. Breakdown:

| Operation | Cost |
|---|---|
| `self.search(...)` | 1 query returning all products with subscribers |
| Per product: `_is_sold_out()` | 1 `free_qty` query per product |
| Per product-partner: `mail.mail.create()` | 1 INSERT per email |
| Per product-partner: `mail.send()` | SMTP call |
| Per product-partner: M2m subtraction | 1 UPDATE on the relation table |
| `raise_exception=False` | A single email failure does not abort the remaining batch |

**Production recommendation:** For stores with thousands of subscribers, consider adding a domain filter to the cron to only check products modified in the last N hours:
```python
domain = [('stock_notification_partner_ids', '!=', False),
          ('write_date', '>', fields.Datetime.subtract(fields.Datetime.now(), hours=6))]
```
Or increase the `interval_type` to 2 hours.

#### 4.1.3 `free_qty` Computation — Trigger vs. On-Demand

`product.product.free_qty` is a stored computed field (defined in `sale_stock`, not this module). It is **not** recomputed on every `_get_product_available_qty()` call — it uses Odoo's lazy invalidation + on-demand recomputation triggered by `stock.move` writes.

- When a `stock.move` is confirmed (done), `stock.quant` records update → `free_qty` is marked dirty → the next read triggers `_compute_free_qty`
- The `stock.move` → `stock.quant` chain is asynchronous to the website. If a customer adds an item to their cart while a picking is being processed in the warehouse, the displayed `free_qty` could lag reality by a few seconds
- The `_check_cart_is_ready_to_be_paid()` guard exists precisely to catch this lag at checkout time

#### 4.1.4 Cart Page Load — `_get_cart_and_free_qty` Per Line

On every cart page render, `_get_free_qty()` is called per unique product in the cart. For a cart with 10 different products, this triggers 10 `free_qty` recomputations (or cache reads if recently computed). The `_get_cart_qty` computation is pure Python in-memory.

The `_verify_updated_quantity()` method (called on every cart qty change) is the heavier operation — it runs the full UoM conversion + float rounding + comparison logic. It is called from the JSON-RPC `/shop/cart/update_json` endpoint.

### 4.2 Multi-Website Stock Isolation {#l4-multiwh}

The `website.warehouse_id` field is the sole isolation mechanism. The module does **not** implement multi-website stock rules — it delegates to `stock.warehouse` scoping.

```python
website._get_product_available_qty(product)
  └── product.with_context(warehouse_id=self.warehouse_id.id).free_qty
```

**Three-tier warehouse resolution:**

| Layer | Method | Warehouse Used |
|---|---|---|
| Product page / combination info | `website._get_product_available_qty()` | `website.warehouse_id` |
| Cart qty display | `sale.order._get_free_qty()` | `website.warehouse_id` via `_get_shop_warehouse_id()` |
| SO confirmation / picking | `sale.order._compute_warehouse_id()` | `website.warehouse_id` (forced for website orders) |

**If no warehouse is set on the website:**

```python
website._get_product_available_qty(product)
  └── product.with_context(warehouse_id=False).free_qty
```

Setting `warehouse_id=False` in context causes Odoo's `stock.location` domain to return quants from **all** warehouses. The test `test_get_combination_info_free_qty_when_no_warehouse_is_set` confirms: WH1 (10 units) + WH2 (15 units) = `free_qty = 25` when no website warehouse is set.

**Critical edge case — warehouse mismatch:**

If the website has `warehouse_id=WH_Ams` but the SO's `warehouse_id` is later changed to `WH_Ber` (e.g., by a backend user or a delivery routing rule), the cart will show Ams stock while the picking ships from Berlin. The `_check_cart_is_ready_to_be_paid()` uses the website's warehouse, not the order's — so the cart check and the actual fulfillment use different warehouses. This can lead to:
- Cart allows adding 10 items (WH_Ams has 10)
- Picking ships from WH_Ber (which has 0)
- Order line is confirmed but picking cannot be done

Mitigation: never change a website SO's warehouse after creation, or disable the website warehouse feature if multi-warehouse routing is used post-checkout.

**Multi-website example — Amsterdam vs Berlin:**

| Product | WH: Amsterdam | WH: Berlin | Website A (Ams) | Website B (Ber) |
|---------|--------------|------------|------------------|-----------------|
| Widget A | 10 units | 5 units | 10 shown | 5 shown |
| Widget B | 8 units | 8 units | 8 shown | 8 shown |
| Widget C | 0 units | 20 units | OOS badge | 20 shown |

### 4.3 Odoo 18 to 19 Changes {#l4-o18-o19}

| Aspect | Odoo 18 | Odoo 19 | Impact |
|--------|---------|---------|--------|
| **Stock field for cart checks** | `virtual_available` (`on_hand - outgoing`) | `free_qty` (`on_hand - outgoing - reserved`) | `free_qty` excludes quantities reserved for other confirmed pickings. For eCommerce, this is more accurate: a product sitting in a delivery picking's demand is not available for new website orders |
| **Combo product stock** | No `_get_max_quantity` on combo | Full `_get_max_quantity` on `product.combo`, `_get_max_available_qty` on `sale.order.line` | Combo products now respect individual item stock limits. The "bottleneck item" pattern caps the combo quantity at the least-available item |
| **`product.combo` model** | Not present | New in Odoo 19 | Odoo 19 introduced the `product.combo` model as a first-class concept; `website_sale_stock` extends it for stock limits |
| **Ribbon `out_of_stock`** | Not available | New `selection_add` | Automatic "out of stock" ribbon without manual product assignment |
| **Context key mechanism** | Ambiguous | `website_sale_stock_get_quantity` explicit | `get_combination_info_website` in `variant.py` injects the context flag — only this route triggers stock computation |
| **UoM rounding** | `float_round` with default | `float_round(..., rounding_method='DOWN')` explicit | Downward rounding prevents `0.4` units from rounding to `1` and incorrectly allowing one more item |
| **`has_stock_notification`** | Partner only | Partner M2m + session-based for anonymous | Anonymous users can now register stock notifications via session storage, bridging the gap before account creation |
| **Abandoned cart email filter** | Basic | `_all_product_available()` check | Odoo 18's abandoned cart filter did not consider stock; Odoo 19 blocks emails for orders with unavailable products |
| **`_check_cart_is_ready_to_be_paid`** | Present in sale_stock | Same, unchanged | Final checkout guard; both versions use `ValidationError` |
| **Cron frequency** | Hourly | Hourly | No change |

### 4.4 Security Analysis {#l4-security}

#### 4.4.1 Public Endpoint — Email Registration

```python
@route('/shop/add/stock_notification', type='jsonrpc', auth='public', website=True)
def add_stock_email_notification(self, email, product_id):
    if not email_re.match(email):
        raise BadRequest(_("Invalid Email"))
    product = request.env['product.product'].browse(int(product_id))
    partner = request.env['mail.thread'].sudo()._partner_find_from_emails_single([email])
    if not product._has_stock_notification(partner):
        product.sudo().stock_notification_partner_ids += partner
```

| Risk | Assessment | Mitigation |
|---|---|---|
| Email enumeration | Low | Only confirms whether an email has an associated partner; the `has_stock_notification` state is not disclosed |
| Email injection | Low | `email_re` validates format before use |
| Mass subscription | Medium | Any IP can submit the form repeatedly; WAF/rate limiting recommended in production |
| Arbitrary product subscription | Low | Only subscribes the email owner; cannot subscribe others |
| `sudo()` on `stock_notification_partner_ids` | Medium | Any public user can write to this M2m via `+= partner`; however, the only write is adding a partner — not removing others or accessing data |

#### 4.4.2 `out_of_stock_message` — HTML Injection

```python
out_of_stock_message = fields.Html(string="Out-of-Stock Message", translate=html_translate)
```

`html_translate` allows a safe subset of HTML tags (`<b>`, `<i>`, `<u>`, `<br>`, `<p>`, `<span>`, `<a>`). The JS explicitly calls `markup()` on the message:

```javascript
combination.out_of_stock_message = markup(combination.out_of_stock_message);
```

`markup()` tells OWL/QWeb to treat the string as pre-sanitized HTML and not re-escape it. If the field is populated with `<script>alert(1)</script>` by an admin, it will execute in the browser. Since only users with product form write access can populate this field, this is an admin-trusted input — but be aware of this when integrating with third-party apps that programmatically create/update products.

#### 4.4.3 Session-Based Notification Tracking

```python
request.session['product_with_stock_notification_enabled'] = list(
    set(request.session.get('product_with_stock_notification_enabled', [])) | {product_id}
)
request.session['stock_notification_email'] = email
```

The session set grows without bound over a long browsing session. There is no cleanup of this set. In practice, the browser sends the session cookie on every request, and the session is stored server-side — high-volume stores should configure session storage limits.

#### 4.4.4 Cron Job — `sudo()` and ACLs

```python
mail = self_ctxt.env['mail.mail'].sudo().create(mail_values)
mail.send(raise_exception=False)
product.stock_notification_partner_ids -= partner
```

The cron uses `sudo()` to:
1. Bypass record rules on `product.product` (cron jobs run as the cron user, who may not have portal-access to all products)
2. Write to `mail.mail` without ACL checks
3. Modify `stock_notification_partner_ids` without write access

This is acceptable for a system-level scheduled job, but the cron user should be a member of `base.group_system` for this to work without errors.

#### 4.4.5 `stock.picking.website_id` — Information Disclosure

```python
website_id = fields.Many2one('website', related='sale_id.website_id', store=True, readonly=True)
```

The `website_id` field on `stock.picking` makes the eCommerce origin of any picking visible to all users who can access pickings — including warehouse operators who should not know which website generated an order. This is a minor information disclosure risk in multi-tenant/multi-website setups.

### 4.5 Edge Cases {#l4-edge}

#### 4.5.1 Multi-Variant Template — First Variant Only Check {#l4-edge-variant}

#### 4.5.1 Multi-Variant Template — First Variant Only Check

`_is_sold_out()` on `product.template` delegates to `product_variant_id._is_sold_out()`:

```python
return self.product_variant_id._is_sold_out()
```

`product_variant_id` returns the **first variant** (lowest ID). For a template with variants S/M/L where only M is in stock, if M is not the first variant, `_is_sold_out()` will incorrectly report `True` for the entire template.

**Affected callers:**
- Google Merchant Center feed (`product.feed._prepare_gmc_stock_info`)
- Ribbon applicability (`product.ribbon._is_applicable_for`)
- Abandoned cart check (`sale.order._all_product_available`)

**Workaround:** The frontend combination info (called via `_get_additionnal_combination_info`) correctly resolves stock per selected variant — only the template-level checks suffer from this.

#### 4.5.2 Concurrent Cart Updates — Race Condition {#l4-edge-race}

```python
# Order of operations:
# Request A: new_qty=5, free_qty=3 at time of check
# Request B: new_qty=5, free_qty=3 at time of check
# Both pass the free_qty >= total_cart_qty check
# Both write qty=5 to their order lines
# Result: qty=10 ordered when only 3 exist
```

`_verify_updated_quantity()` is not atomic. Two simultaneous `add_to_cart` requests can both pass the availability check before either commits. The `_check_cart_is_ready_to_be_paid()` guard catches this at checkout time and raises a `ValidationError` — the order cannot be paid for.

Odoo `sale_stock` uses `lock()` on the `sale_order_line` table during `write()` to mitigate concurrent writes, but this cannot prevent the application-level race condition where two separate HTTP requests both read `free_qty=3` before either writes.

**Production mitigation:** Use `picking_type_id.use_create_lots` + `stock.move` reservation to ensure physical stock exists at confirmation time, not at cart-add time.

#### 4.5.3 Anonymous → Authenticated Notification Gap {#l4-edge-anon}

A public user subscribes to a back-in-stock notification, then creates an account with the same email. The notification is stored in their session (`product_with_stock_notification_enabled`) but **not** linked to their partner record. After login, `has_stock_notification` will return `False` for this partner:

```python
has_stock_notification = (
    product_sudo._has_stock_notification(self.env.user.partner_id)  # partner has no M2m entry
    or (request and product_sudo.id in request.session.get(...))   # session may still exist
)
```

If the session expires or they log in from another browser, the notification is lost. The workaround is to promote the session-based subscription to a partner M2m entry at account creation time.

#### 4.5.4 UoM Rounding — Zero Stock but Shown as One {#l4-edge-uom}

```python
available_qty = float_round(available_qty, precision_digits=0, rounding_method='DOWN')
```

A product with `free_qty = 0.4` (less than one unit) rounds down to `0`. The `add_qty` input gets `data-max="0"` and `min=1` is the browser default, so the input shows `1` but the user cannot actually add it. The CTA is hidden (`free_qty < 1`). This is correct behavior but may confuse users who see "1" in the quantity input.

#### 4.5.5 Combo with Mixed Stock Enforcement Types {#l4-edge-combo}

If a combo includes items with `allow_out_of_stock_order = True` (unlimited) and items without:

```python
max_quantities = [
    item.product_id._get_max_quantity(website, sale_order)  # returns None for unlimited items
    for item in self.combo_item_ids
]
return max(max_quantities) if (None not in max_quantities) else None
```

Since `None in max_quantities` is True when any item is unlimited, the combo returns `None` (unlimited). This means a combo containing one non-storable or one unlimited-storable item becomes unlimited in total. The `min()` vs `max()` decision (bottleneck vs. ceiling) is key here — a combo's max is the **minimum** item availability, but if any item is unlimited, the whole combo is unlimited.

#### 4.5.6 Website Without Warehouse — All Warehouses Aggregated {#l4-edge-no-wh}

When `website.warehouse_id` is empty, `_get_shop_warehouse_id()` returns `False`:

```python
return self.website_id.warehouse_id.id  # returns False.id = False
```

This causes `free_qty` to aggregate quants from all warehouses, but the SO's `warehouse_id` may still be set to a specific warehouse by `_compute_warehouse_id()`. The cart shows "all warehouses" stock, but the picking ships from one specific warehouse. A mismatch is possible when no website warehouse is set but the system has multiple warehouses.

### 4.6 Schema.org / Structured Data {#l4-schema}

`_to_markup_data()` injects `offers.availability` into the JSON-LD block on product pages:

```python
if not self._is_sold_out():
    availability = 'https://schema.org/InStock'
else:
    availability = 'https://schema.org/OutOfStock'
markup_data['offers']['availability'] = availability
```

| Schema.org Value | Condition | Google Merchant Center Meaning |
|---|---|---|
| `https://schema.org/InStock` | `not _is_sold_out()` | Product can be shipped within 3 business days (configurable) |
| `https://schema.org/OutOfStock` | `_is_sold_out()` | Product is unavailable |

Products with `allow_out_of_stock_order = True` at zero stock still output `InStock` — this is correct for pre-order or made-to-order scenarios. Google Merchant Center accepts `InStock` with a `preorder` `availability_date` for future-dated availability.

The markup is consumed by Google's rich results testing tool and influences product listing ad eligibility and display.

### 4.7 The `isQuantityAllowed` System — Frontend Architecture {#l4-frontend-arch}

Odoo 19 introduces a cross-module `isQuantityAllowed` pattern where the `sale` module defines a shared interface and multiple modules patch it:

```
@sale/js/models/product_product  (base: checks nothing)
    └── website_sale_stock: patches isQuantityAllowed
        └── checks: this.free_qty >= quantity

@sale/js/product_product (combo variant)
    └── sale (combo base)
        └── website_sale_stock: patches selectComboItem, setQuantity, isComboQuantityAllowed
```

**`ProductProduct.isQuantityAllowed(quantity)`:**
```javascript
return this.free_qty === undefined || this.free_qty >= quantity;
```
- `undefined` → passes (non-storable or no stock data loaded)
- `free_qty >= quantity` → allowed
- `free_qty < quantity` → blocked

**`ComboConfiguratorDialog` integration:**
1. `selectComboItem()` — calls `isQuantityAllowed(1)` before allowing item selection; prevents selecting a combo item that would immediately exceed stock
2. `setQuantity()` — clamps to `min(free_qty of selected items)` if the target quantity would fail `isComboQuantityAllowed()`
3. `isComboQuantityAllowed()` — returns `True` only if **every** selected combo item's `isQuantityAllowed(quantity)` passes

This is the client-side complement to `_verify_updated_quantity()` — the frontend blocks invalid quantities before they reach the server.

### 4.8 Cron Job — `ir_cron_send_availability_email` {#l4-cron}

```xml
<field name="name">Product: send email regarding products availability</field>
<field name="interval_number">1</field>
<field name="interval_type">hours</field>
<field name="model_id" ref="model_product_product"/>
<field name="code">model._send_availability_email()</field>
```

| Property | Value |
|---|---|
| Model | `product.product` |
| Frequency | Every 1 hour |
| Method | `_send_availability_email()` |
| Execution user | Cron user (typically admin) |
| Transaction boundary | One transaction per email (each email send + M2m update is committed separately via `mail.send()`) |

The email is sent **one-shot** per product-partner pair: once a product is back in stock and the email is sent, the partner is removed from `stock_notification_partner_ids`. They must re-subscribe to be notified again on the next stock-out.

The email subject is translated to the recipient partner's language via `product_ctxt.with_context(lang=partner.lang)` — the product name in the subject line is locale-aware.

---

## 5. Controllers

### 5.1 `WebsiteSaleStock` — Stock Notification Subscription

**File:** `controllers/main.py`
**Route:** `/shop/add/stock_notification`
**Type:** `jsonrpc`
**Auth:** `public`

```python
def add_stock_email_notification(self, email, product_id):
    # 1. Validate email format
    if not email_re.match(email):
        raise BadRequest(_("Invalid Email"))

    # 2. Find/create partner from email
    product = request.env['product.product'].browse(int(product_id))
    partner = request.env['mail.thread'].sudo()._partner_find_from_emails_single([email])

    # 3. Subscribe partner to notification
    if not product._has_stock_notification(partner):
        product.sudo().stock_notification_partner_ids += partner

    # 4. Session tracking for public users
    if request.website.is_public_user():
        request.session['product_with_stock_notification_enabled'] = list(...)
        request.session['stock_notification_email'] = email
```

### 5.2 `WebsiteSaleStockVariantController` — Context Injection

**File:** `controllers/variant.py`
**Extends:** `WebsiteSaleVariantController`

```python
@route()
def get_combination_info_website(self, *args, **kwargs):
    request.update_context(website_sale_stock_get_quantity=True)
    return super().get_combination_info_website(*args, **kwargs)
```

This is the single point where the `website_sale_stock_get_quantity` context is set, triggering stock data inclusion in the combination info response.

### 5.3 `WebsiteSale` — Product Values Enrichment

**File:** `controllers/website_sale.py`
**Extends:** `main.WebsiteSale`

```python
def _prepare_product_values(self, product, category, **kwargs):
    values = super()._prepare_product_values(product, category, **kwargs)
    values['user_email'] = request.env.user.email or request.session.get('stock_notification_email', '')
    return values
```

Pre-fills the email input on the product page notification form for logged-in users (using `request.env.user.email`) and falls back to the session-stored email for public users.

---

## 6. JavaScript Frontend

### 6.1 `variant_mixin.js` — `_onChangeCombinationStock`

The primary frontend stock handler, mixed into the product page's combination change pipeline. Key responsibilities:

```javascript
// 1. Guard: only for main product on product page
if (!parent.matches('.js_main_product') || !combination.product_id) return;

// 2. Show CTA wrapper
const ctaWrapper = parent.querySelector('#o_wsale_cta_wrapper');
ctaWrapper.classList.replace('d-none', 'd-flex');
ctaWrapper.classList.remove('out_of_stock');

// 3. Subtract cart_qty from free_qty for "actually available" qty
const unavailableQty = await this.waitFor(VariantMixin._getUnavailableQty(combination));
combination.free_qty -= unavailableQty;

// 4. Set max attribute on quantity input
addQtyInput.dataset.max = combination.free_qty || 1;

// 5. Clamp quantity if exceeds available
if (qty > combination.free_qty) {
    addQtyInput.value = addQtyInput.dataset.max;
}

// 6. Show/hide CTA based on availability
if (combination.free_qty < 1) {
    ctaWrapper.classList.replace('d-flex', 'd-none');
    ctaWrapper.classList.add('out_of_stock');
}

// 7. Clear old availability messages and render new ones
document.querySelectorAll('.availability_message_' + product_template).forEach(el => el.remove());
this.el.querySelector('div.availability_messages').append(renderToFragment(
    'website_sale_stock.product_availability', combination
));
```

The `formatQuantity` helper formats the remaining quantity based on the product's UoM rounding precision.

### 6.2 `product_product.js` — `isQuantityAllowed`

```javascript
patch(ProductProduct.prototype, {
    isQuantityAllowed(quantity) {
        return this.free_qty === undefined || this.free_qty >= quantity;
    }
});
```

Used by the sale cart model (`@sale/js/models/product_product`) to validate whether a quantity can be added to the cart without exceeding available stock.

### 6.3 `product.js` — `isOutOfStock`

```javascript
patch(Product.prototype, {
    isOutOfStock() {
        return !this.env.isQuantityAllowed(this.props, 1);
    }
});
```

Used by the product card and product configurator components to conditionally apply out-of-stock CSS classes and disable "Add to Cart" buttons.

### 6.4 `website_sale.js` — `WebsiteSale` Interaction Patch

The main interaction patch on `WebsiteSale.prototype`:
- Binds click handlers for the stock notification message toggle and form submit button
- Chains `super._onChangeCombination()` then `this._onChangeCombinationStock()` to combine the base variant change logic with stock-specific logic
- After `onClickAdd` (add to cart), re-fetches combination info to refresh stock display (important for accurate `cart_qty` after adding)

---

## 7. Views & XML

### 7.1 Product Template Form (`product_template_views.xml`)

Extends `website_sale.product_template_form_view` to add the stock configuration section:

```xml
<!-- allow_out_of_stock_order: next to ribbon field -->
<field name="allow_out_of_stock_order" invisible="not is_storable"/>

<!-- show_availability + threshold inline row -->
<label for="show_availability" invisible="not is_storable" string="Show Available Qty"/>
<div invisible="not is_storable">
    <field name="show_availability" class="oe_inline"/>
    <span invisible="not show_availability">
        <label for="available_threshold" string="Below" class="o_light_label"/>
        <field name="available_threshold" class="oe_inline col-1"/>
    </span>
</div>

<!-- Custom out-of-stock message -->
<field name="out_of_stock_message" invisible="not is_storable"
        placeholder="e.g. 'Will be back soon'"/>
```

### 7.2 Settings Form (`res_config_settings_views.xml`)

Adds an "Inventory Defaults" section to the website settings with:
- Warehouse selection (with `stock.group_stock_multi_warehouses` visibility)
- Out-of-stock selling toggle (Continue Selling)
- Show availability quantity toggle + threshold input
- All fields use `default_model='product.template'` for system-wide defaults

### 7.3 Stock Email Template (`template_email.xml`)

QWeb email rendered by `_send_availability_email()`:
- Product image (`/web/image/product.product/{id}/image_1920`)
- Product name with variant names in parentheses
- `description_sale` text
- Styled "Order Now" button using `company_id.email_secondary_color` / `email_primary_color`
- "Order Now" link points to `product.website_url`

### 7.4 Stock Availability QWeb Template (`website_sale_stock_product_availability.xml`)

Three render states:

| Condition | CSS Class | Display |
|-----------|-----------|---------|
| `free_qty <= 0 and not cart_qty` | `text-bg-danger` | "Out of Stock" badge or custom message + notification form |
| `show_availability and free_qty <= available_threshold` | `text-bg-warning` | "N units in stock" + "(M in your cart)" if applicable |
| Default | — | Nothing rendered |

---

## 8. Test Coverage

### 8.1 Test Files

| Test File | Coverage |
|---------|---------|
| `test_website_sale_stock_product_warehouse.py` | Per-website warehouse stock isolation; cart qty enforcement with multi-warehouse |
| `test_website_sale_stock_product_product.py` | `_is_sold_out()`, `_get_max_quantity()`, ribbon OOS |
| `test_website_sale_stock_product_template.py` | Template-level OOS fields, threshold logic |
| `test_website_sale_stock_sale_order_line.py` | Cart line availability checking, `_check_availability()` |
| `test_website_sale_stock_stock_notification.py` | Email notification subscription, `_send_availability_email()` |
| `test_website_sale_stock_stock_message.py` | Warning message generation with UoM formatting |
| `test_website_sale_stock_delivery.py` | Picking creation from website orders, `website_id` on picking |
| `test_website_sale_stock_multilang.py` | i18n of availability messages |
| `test_website_sale_stock_abandoned_cart_email.py` | Abandoned cart filter respects stock |
| `test_website_sale_stock_configurators.py` | Configurator stock behavior |
| `test_website_sale_stock_product_combo.py` | Combo max quantity computation (bottleneck) |
| `test_website_sale_stock_gmc.py` | Google Merchant Center stock feed |
| `test_website_sale_stock_reorder_from_portal.py` | Portal reorder stock handling |

### 8.2 Key Test Patterns

**Multi-warehouse isolation:**
```python
def test_get_combination_info_free_qty_when_warehouse_is_set(self):
    self.website.warehouse_id = self.warehouse_2
    combination_info = self.product_A._get_combination_info_variant()
    self.assertEqual(combination_info['free_qty'], 15)  # Only WH2's 15 units

def test_get_combination_info_free_qty_when_no_warehouse_is_set(self):
    self.website.warehouse_id = False
    combination_info = self.product_A._get_combination_info_variant()
    self.assertEqual(combination_info['free_qty'], 25)  # WH1 (10) + WH2 (15) = 25
```

**Cart quantity capping:**
```python
def test_02_update_cart_with_multi_warehouses(self):
    so = self.env['sale.order'].create({website..., product_A qty=5...})
    values = so._cart_update_line_quantity(line_id=..., quantity=30)
    self.assertTrue(values.get('warning'))
    self.assertEqual(values.get('quantity'), 25)  # Capped to 25 total
```

---

## 9. Snippets & Recipes

### Check if a product is sold out

```python
product = self.env['product.product'].browse(product_id)
if product._is_sold_out():
    raise ValidationError(_("This product is currently out of stock."))
```

### Get stock for a specific website

```python
website = self.env['website'].get_current_website()
available = website._get_product_available_qty(product)
```

### Get max cart quantity for a product

```python
sale_order = request.cart  # current cart from session
max_qty = product._get_max_quantity(website, sale_order)
```

### Subscribe to stock notification

```python
partner = self.env['mail.thread'].sudo()._partner_find_from_emails_single([email])
if not product._has_stock_notification(partner):
    product.sudo().stock_notification_partner_ids += partner
```

### Force specific warehouse for availability check

```python
product_with_warehouse = product.with_context(warehouse_id=warehouse_id)
free_qty = product_with_warehouse.free_qty
```

### Check all products in an order are available

```python
so = self.env['sale.order'].browse(order_id)
if not so._all_product_available():
    raise ValidationError(_("Some products in your order are out of stock."))
```

### Validate cart before payment

```python
so = self.env['sale.order'].browse(order_id)
so._check_cart_is_ready_to_be_paid()  # raises ValidationError if any line has stock warning
```

### Render availability badge in QWeb

```xml
<t t-call="website_sale_stock.product_availability">
    <t t-set="combination" t-value="product._get_combination_info(...)"/>
</t>
```

---

## Related Modules

- [Modules/website_sale](Modules/website_sale.md) — Base eCommerce module (product display, cart)
- [Modules/sale_stock](Modules/sale_stock.md) — Sale + inventory integration (free_qty, warehouse_id on SO)
- [Modules/stock](Modules/stock.md) — Warehouse and inventory management (stock.quant, stock.move)
- [Modules/website_sale_mrp](Modules/website_sale_mrp.md) — Kit/BOM availability on eCommerce (extends this)
- [Modules/product](Modules/product.md) — Product master data (is_storable, free_qty, uom_id)
