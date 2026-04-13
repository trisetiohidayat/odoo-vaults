---
Module: pos_discount
Version: Odoo 18
Type: Business
Tags: #pos #discount #point-of-sale #sales
Related: [Modules/PointOfSale](modules/pointofsale.md), [Modules/Account](modules/account.md)
---

# pos_discount — POS Global Discount

## Overview

**Category:** Sales/Point of Sale | **Sequence:** 6
**Depends:** `point_of_sale`
**Data:** `data/pos_discount_data.xml`, `views/pos_config_views.xml`, `views/res_config_settings_views.xml`

`pos_discount` adds **order-level percentage discounts** to the Point of Sale. The cashier can apply a single configurable discount percentage to the entire order with one tap. The discount is implemented as a **negative order line** using a dedicated discount product — not a simple arithmetic adjustment — which means it flows naturally through the accounting and inventory pipeline.

---

## Models

### `pos.config` (EXTENDED by pos_discount)

> Base model: `point_of_sale.pos.config`. `pos_discount` adds three fields and two methods.

#### Fields Added

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `iface_discount` | `Boolean` | `False` | Enables the "Discount" button in the POS UI. When `True`, the cashier sees a button to apply a discount to the current order. |
| `discount_pc` | `Float` | `10.0` | The default discount percentage applied when the Discount button is clicked. A float from 0 to 100. |
| `discount_product_id` | `Many2one(product.product)` | `False` | The **discount product** used to represent the discount as a negative line on the order. Must be `sale_ok=True`. On install, defaults to `pos_discount.product_product_consumable`. |

#### Methods

**`_default_discount_value_on_module_install()`** (`@api.model`, called via data XML)

> On module installation, this function sets `discount_product_id` on all POS configs (that have `module_pos_discount=True` and no open sessions) to the default `product_product_consumable` "Discount" product.

Logic:
1. Searches all `pos.config` records
2. Identifies which have open POS sessions (these are skipped — live configs are not modified)
3. For all others with `module_pos_discount=True`, assigns the default discount product if it exists and belongs to the same company or no company

```python
for conf in (configs - open_configs):
    conf.discount_product_id = product if conf.module_pos_discount and product ...
```

**`open_ui()`**

> Validates that a discount product is configured before allowing the POS session to open. Raises `UserError` if `module_pos_discount=True` but no `discount_product_id` is set. Prevents the cashier from being stuck without a working discount product.

**`_get_special_products()`**

> Extends the base POS special products list. Adds all configured `discount_product_id` values (from all POS configs) and the default discount product to the list of products excluded from certain POS operations (e.g., they are not shown in the product grid, but can be used programmatically).

---

### `product.product` (EXTENDED by pos_discount)

> Base model: `product.product`.

#### Methods

**`_load_pos_data(self, data)`**

> On POS session start, the POS front-end loads all required data from the server via `_load_pos_data`. This method intercepts that process to inject the discount product into the data sent to the POS.

Logic:
1. Checks if `module_pos_discount=True` on the current config
2. Checks if `discount_product_id` is NOT already in the loaded product set
3. If not present, searches the discount product by ID and processes it through `_process_pos_ui_product_product()`
4. Appends it to the `res['data']` array

This ensures the discount product is available in the POS front-end even though `available_in_pos=False` (it's a hidden/conceptual product, not shown in the catalog). The product has:
- `list_price = 0.0` — it has no positive revenue
- `standard_price = 0.0` — no cost
- `type = 'consu'` — consumable (no inventory tracking)
- `purchase_ok = False` — not purchasable
- `available_in_pos = False` — not shown in the product grid

---

### `res.config.settings` (EXTENDED by pos_discount)

> Transient wizard. Inherits from POS settings.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `pos_discount_pc` | `Float` (related) | `related='pos_config_id.discount_pc', readonly=False`. Mirrors the discount percentage to the settings form. |
| `pos_discount_product_id` | `Many2one(product.product)` (computed/stored) | The discount product, computed from config or default, stored back to config on save. |

#### Methods

**`_compute_pos_discount_product_id()`**

> Computed field. When the module is enabled (`pos_module_pos_discount=True`), sets `pos_discount_product_id` to the config's existing `discount_product_id` or the default "Discount" product. When disabled, sets to `False`. Also validates company_id match.

---

## Data: The Discount Product

### `product_product_consumable` (created in `data/pos_discount_data.xml`)

| Property | Value |
|----------|-------|
| `name` | "Discount" |
| `default_code` | `DISC` |
| `type` | `consu` (consumable) |
| `sale_ok` | `True` (required for use in POS orders) |
| `purchase_ok` | `False` |
| `available_in_pos` | `False` (hidden from product grid) |
| `list_price` | `0.00` |
| `standard_price` | `0.00` |
| `categ_id` | `product_category_pos` (POS category) |
| `uom_id` / `uom_po_id` | `product_uom_unit` |

This product serves as a **fiscal placeholder** — it exists to generate a negative order line with the correct accounting impact. It is never visible to the cashier as a sellable product.

---

## How the Discount Flow Works (L4)

### Step-by-Step: Applying a Discount at POS

```
Cashier has an order totaling $100
    ↓
Taps "Discount" button (visible when iface_discount=True)
    ↓
POS UI applies discount_pc (e.g., 10%) to the order
    ↓
A NEGATIVE order line is added:
  - product_id: discount_product_id (product_product_consumable, "Discount")
  - qty: 1
  - price_unit: -10.00  (negative!)
  - tax_ids: [] (no tax on the discount line)
  ↓
Order total now shows: $100.00 → $90.00
    ↓
Receipt prints the discount line:
  "Discount              -$10.00"
```

### Discount as a Negative Line

The discount is **not** a simple arithmetic subtraction. It is a real `pos.order.line` record with a negative `price_unit`. This has important implications:

1. **Tax behavior**: The discount line has no `tax_ids` set. The base `point_of_sale` module handles tax computation at the order level — since the discount reduces the subtotal before tax calculation, the tax amount is also reduced proportionally (Odoo's standard tax computation applies the discount % to the tax base).

2. **Accounting**: When the POS session is closed and the order is invoiced or posted to the journal:
   - The discount line posts to the same revenue account as the product lines, but with a negative amount
   - Net effect: reduced revenue

3. **No separate discount account**: There is no dedicated "Sales Discount" account. The discount line uses the same account as the normal sale lines, resulting in a net lower revenue entry.

### Tax Interaction (L4)

The tax treatment of POS discounts follows Odoo's standard tax calculation model:

- Tax is computed on `(order amount - discount)` — i.e., discount reduces both the taxable base and the tax amount
- The discount line itself carries no taxes — it is a pure price adjustment
- If the original order lines had taxes, those taxes are recomputed based on the post-discount amounts
- This is the same behavior as manual price adjustments at POS

### Discount % Limits

- `discount_pc` is a float, so any value from 0 to 100 is technically valid
- Odoo's POS JavaScript does not enforce an upper limit on the client side
- Business logic validation should be done via POS access rights (cashiers vs. managers) or a custom module
- The default value is `10.0`%

### Multiple Discounts

Only **one discount line** is permitted per order in the standard POS flow. Tapping the Discount button multiple times replaces the existing discount line rather than stacking discounts. This is enforced by the POS front-end logic (not the Python backend).

---

## POS Frontend (JavaScript)

The POS JavaScript bundle (`pos_discount/static/src/`) is loaded via the `point_of_sale._assets_pos` asset bundle. The JS code:

- Reads `iface_discount` to show/hide the Discount button
- Reads `discount_pc` for the default percentage
- Adds a `DiscountButton` widget to the POS action pad
- On click: invokes the discount action which adds/modifies the discount order line

---

## Key Design Notes

- **The discount product is not for sale**: `available_in_pos=False` means it never appears in the product search/catalog. It is injected directly into the POS data on session start via `_load_pos_data`.
- **One discount per order**: Standard behavior is one discount line per order. Stacking discounts requires custom code.
- **No tax on the discount line**: The discount line carries no taxes — it reduces the tax base, not the tax itself.
- **`open_ui` guard**: Prevents opening a POS session without a configured discount product, which would cause errors when the cashier tries to apply a discount.
- **Install migration**: `_default_discount_value_on_module_install` is called via `noupdate="1"` data XML, so it runs once on install. For existing POS configs with open sessions, it is skipped to avoid race conditions.
- **Category assignment**: The discount product is placed in `product_category_pos` so it benefits from any POS-specific accounting configuration on that category.
