---
type: module
module: pos_discount
tags: [odoo, odoo19, pos, discount, point_of_sale, retail, pricing]
created: 2026-04-14
uuid: d9b3f6c2-7e1a-4d8b-9f2c-3a5e7b1d4f6a
---

# POS Discounts (`pos_discount`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Point of Sale Discounts |
| **Technical** | `pos_discount` |
| **Category** | Sales / Point of Sale |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **Depends** | `point_of_sale` |

The `pos_discount` module adds a global percentage-based discount capability to the Point of Sale application. It enables cashiers to apply a single, configurable discount to an entire order with one tap — ideal for promotional sales, loyalty discounts, staff discounts, or end-of-day markdowns. The discount is implemented as a dedicated discount product recorded on the order line, making it fully traceable in Odoo's accounting and reporting system.

Unlike per-line discounts (which many POS terminals support natively), this module applies a discount to the entire order at once. This is particularly useful for store-wide promotions, where the same percentage discount must apply to all items regardless of their individual pricing.

## Architecture

### Design Philosophy

The module takes a product-based approach to discounts: instead of storing a raw discount percentage on the order, it creates an actual `pos.order.line` record with a negative amount linked to a designated discount product. This approach has several advantages:

1. **Accounting traceability**: The discount appears as a proper invoice line in Odoo's accounting system, with a tax ID and account code, making it easy to reconcile at month-end.
2. **Reporting compatibility**: Standard Odoo reports (sales by product, revenue analysis) can include or exclude the discount line by filtering on the discount product.
3. **Tax compliance**: Tax calculations on the order automatically account for the discount because the discount is a proper order line with tax IDs.

### Module Structure

```
pos_discount/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── pos_config.py          # PosConfig extension + discount fields
│   ├── product_template.py     # ProductTemplate extension for POS data loading
│   └── res_config_settings.py  # ResConfigSettings for global settings
├── views/
│   ├── pos_config_views.xml   # POS config form extension
│   └── res_config_settings_views.xml
├── data/
│   └── pos_discount_data.xml  # Default discount product
├── static/
│   ├── src/                   # JavaScript for discount button
│   └── tests/                 # QUnit tests
└── tests/
    └── test_taxes_global_discount.py
```

## Models

### `pos.config` (Extended)

**File:** `pos_discount/models/pos_config.py`

The `PosConfig` model is extended to add three new configuration fields that control the discount feature's behavior at the POS terminal level.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `iface_discount` | Boolean | Enable/disable the global discount button in the POS UI |
| `discount_pc` | Float | Default discount percentage, applied when the cashier taps the discount button (default: 10.0) |
| `discount_product_id` | Many2one | The product used to represent the discount on the order line |

#### `iface_discount`

```python
iface_discount = fields.Boolean(
    string='Order Discounts',
    help='Allow the cashier to give discounts on the whole order.')
```

This boolean acts as an on/off switch for the discount feature. When `False`, the discount button does not appear in the POS terminal's UI, and the `_get_special_products()` method (see below) excludes the discount product from the terminal's product catalog.

#### `discount_pc`

```python
discount_pc = fields.Float(
    string='Discount Percentage',
    help='The default discount percentage when clicking on the Discount button',
    default=10.0)
```

The default percentage applied when the cashier activates the discount. This is a float field (e.g., 10.0 for 10%) and can be any value from 0 to 100. The cashier can typically override this value in the POS UI before applying the discount, depending on the frontend implementation.

#### `discount_product_id`

```python
discount_product_id = fields.Many2one(
    'product.product',
    string='Discount Product',
    domain=[('sale_ok', '=', True)],
    help='The product used to apply the discount on the ticket.')
```

The discount product is a regular `product.product` record — it has a name, internal reference, and is linked to income and tax accounts. The product's `sale_ok` flag must be True because the discount line will be recorded as a sale line with a negative amount. The product's `type` should be `service` since no physical goods are involved.

The module ships with a default discount product defined in `data/pos_discount_data.xml`:

```xml
<!-- product_product_consumable: -10% Discount -->
<record id="product_product_consumable" model="product.product">
    <field name="name">Discount</field>
    <field name="type">service</field>
    <field name="sale_ok">True</field>
    <field name="purchase_ok">False</field>
    <field name="list_price">0.01</field>
    <!-- Tax and account fields set appropriately -->
</record>
```

### `product.template` (Extended)

**File:** `pos_discount/models/product_template.py`

This extension ensures that the discount product is loaded into the POS terminal's product catalog, even if it would not normally appear in the search results.

#### `_load_pos_data_read()`

```python
@api.model
def _load_pos_data_read(self, records, config):
    read_data = super()._load_pos_data_read(records, config)
    discount_product_id = config.discount_product_id.id
    product_ids_set = {product['id'] for product in read_data}

    if config.module_pos_discount and discount_product_id not in product_ids_set:
        productModel = self.env['product.template'].with_context(
            {**self.env.context, 'display_default_code': False})
        fields = self.env['product.template']._load_pos_data_fields(config)
        product = productModel.search_read(
            [('id', '=', discount_product_id)], fields=fields, load=False)
        read_data.extend(product)

    return read_data
```

**Why this extension is needed:** The POS terminal only loads products that match certain criteria (e.g., `sale_ok=True`, active, belongs to the current company). The discount product — which may not match the terminal's normal product query — must be explicitly included in the loaded data so the cashier can select it when applying a discount.

The method checks:
1. Is the discount module enabled for this terminal (`config.module_pos_discount`)?
2. Is the discount product already in the loaded data? (It might be if it happens to match the query.)
3. If not, it searches for the discount product's `product.template` record and adds it to the loaded data.

### `res.config.settings` (Extended)

**File:** `pos_discount/models/res_config_settings.py`

This extension provides a global settings page for the POS discount feature, allowing administrators to configure the default discount percentage and product from the general settings screen rather than going into each POS terminal's configuration.

#### `_compute_pos_discount_product_id()`

```python
@api.depends('company_id', 'pos_module_pos_discount', 'pos_config_id')
def _compute_pos_discount_product_id(self):
    default_product = self.env.ref(
        "pos_discount.product_product_consumable",
        raise_if_not_found=False) or self.env['product.product']
    for res_config in self:
        discount_product = res_config.pos_config_id.discount_product_id or default_product
        if res_config.pos_module_pos_discount and (
            not discount_product.company_id
            or discount_product.company_id == res_config.company_id
        ):
            res_config.pos_discount_product_id = discount_product
        else:
            res_config.pos_discount_product_id = False
```

This computed field determines which discount product to show in the global settings:
- If the POS discount module is enabled and the configured discount product exists and belongs to the current company (or has no company restriction), it is shown.
- Otherwise, the field is cleared, preventing configuration of a discount product that the current user cannot access.

## Key Methods

### `open_ui()` — Validation Hook

```python
def open_ui(self):
    for config in self:
        if (not self.current_session_id
                and config.module_pos_discount
                and not config.discount_product_id):
            raise UserError(_(
                'A discount product is needed to use the Global Discount feature. '
                'Go to Point of Sale > Configuration > Settings to set it.'))
    return super().open_ui()
```

**Purpose:** This method is called when a POS session is about to open. It acts as a guard clause that prevents a cashier from opening the POS terminal if the discount feature is enabled but no discount product is configured. This prevents a runtime error when the frontend tries to create a discount order line.

The check is only performed when:
1. There is no current session open for this terminal (`not self.current_session_id`), which means the terminal is being started fresh.
2. The discount module is installed (`config.module_pos_discount`).
3. No discount product is assigned (`not config.discount_product_id`).

This design allows the terminal to open without a discount product if the discount module is not being used.

### `_get_special_products()` — Product Catalog Extension

```python
def _get_special_products(self):
    res = super()._get_special_products()
    default_discount_product = self.env.ref(
        'pos_discount.product_product_consumable',
        raise_if_not_found=False) or self.env['product.product']
    return (
        res
        | self.env['pos.config'].search([]).mapped('discount_product_id')
        | default_discount_product
    )
```

**Purpose:** This method returns all "special products" that should always be available in the POS terminal — even if they are not active or do not match the normal product search criteria. The discount product is included here to ensure it appears in the product selector regardless of its active status or company assignment.

The method returns the union of:
1. The base special products (from `super()`, which includes things like loyalty programs).
2. All discount products configured across all POS terminals.
3. The default discount product from the module's data file.

### `_default_discount_value_on_module_install()`

```python
@api.model
def _default_discount_value_on_module_install(self):
    configs = self.env['pos.config'].search([])
    open_configs = (
        self.env['pos.session']
        .search(['|', ('state', '!=', 'closed'), ('rescue', '=', True)])
        .mapped('config_id')
    )
    product = self.env.ref("pos_discount.product_product_consumable",
                           raise_if_not_found=False)
    for conf in (configs - open_configs):
        conf.discount_product_id = (
            product if conf.module_pos_discount and product
            and (not product.company_id or product.company_id == conf.company_id)
            else False
        )
```

**Purpose:** This method is called automatically when the module is installed (via the `@api.model` decorator pattern). It attempts to assign the default discount product to all POS terminals where the discount module is enabled, but only for terminals that do not have an open session.

## How the Discount Is Applied (Frontend)

The JavaScript frontend (in `static/src/`) handles the discount button and creates the actual discount order line. The general flow is:

1. Cashier taps the "Discount" button in the POS UI.
2. The frontend uses the `discount_pc` from the terminal's configuration as the default value.
3. The cashier can optionally adjust the percentage.
4. The frontend creates a `pos.order.line` record with:
   - `product_id` = `discount_product_id` (the discount product)
   - `price_unit` = negative value (e.g., -10 for a 10% discount on a 100-unit order)
   - `qty` = 1
   - The line is added to the order, reducing the order's subtotal.

Because the discount product has a tax ID, the tax computation automatically adjusts. The resulting order has the same structure as any other Odoo POS order, with full auditability.

## Tax Handling

When a discount is applied, it flows through Odoo's standard tax computation engine. The discount line uses the discount product's tax ID (which should be set to the same tax as regular products for net-zero tax effect, or to a specific discount tax account). This ensures that:

1. The discount reduces the order's taxable amount.
2. The tax amount is reduced proportionally.
3. The accounting entry debits the discount product's income account and credits the tax account.

If your jurisdiction requires a specific tax treatment for discounts (e.g., tax-excluded discounts), configure the discount product's tax IDs accordingly in **Accounting > Configuration > Taxes**.

## Accounting Entry Example

For a $100 order with a 10% discount and 10% tax:

```
Order Line: Product A     Dr  $100.00   (Revenue)
Order Line: Discount -10%  Cr  $10.00    (Discount Revenue)

Tax on $90.00 @ 10%       Dr  $9.00     (Tax Payable)
Net Revenue               $81.00
```

The discount product's account codes determine whether it appears as a separate discount line in financial reports or is netted against product revenue.

## Business Impact

### Operational Efficiency

The single-tap discount eliminates the need for cashiers to manually adjust prices on individual line items during promotions. For a 20-item promotion, this saves significant time and reduces the risk of manual entry errors.

### Auditability

Because discounts are stored as proper order lines, every discount applied at a POS terminal leaves a traceable record. Managers can run reports on discount usage by cashier, terminal, date, and product category.

### Promotional Campaigns

The configurable default percentage means that the same POS terminal can be used for different promotions by simply changing the `discount_pc` value — no POS restart required in many configurations. This supports rapid promotional rollouts across store locations.

## Configuration Checklist

1. **Install the module** via Apps.
2. **Verify the discount product** exists at **Inventory > Products > Products** (named "Discount" from the module's data file).
3. **Configure each POS terminal**: Go to **Point of Sale > Configuration > Point of Sale**, open a terminal, and:
   - Enable **Order Discounts** (`iface_discount`).
   - Set the **Discount Percentage** (`discount_pc`).
   - Verify the **Discount Product** is set.
4. **Set up tax accounts** on the discount product in **Accounting**.
5. **Test the POS session** by opening the terminal and applying a discount.

## Related

- [Modules/point_of_sale](point_of_sale.md) — Base POS module: sessions, orders, payments
- [Modules/pos_loyalty](pos_loyalty.md) — Loyalty programs and rewards in POS
- [Modules/pos_restaurant](pos_restaurant.md) — Restaurant-specific POS features
- [Modules/account](Account.md) — Accounting: taxes, invoices, journal entries
