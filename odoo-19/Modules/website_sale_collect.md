---
title: website_sale_collect (Click & Collect)
draft: false
tags:
  - #odoo
  - #odoo19
  - #modules
  - #website
  - #e-commerce
  - #click-and-collect
  - #stock
  - #payment
created: 2026-04-11
description: Enable customers to check in-store stock, pay on site, and pick up orders at the physical store (Click & Collect / Buy Online, Pick up in Store).
---

# website_sale_collect

> **Display Name:** Click & Collect  
> **Version:** 1.0  
> **Category:** Website/Website  
> **License:** LGPL-3  
> **Author:** Odoo S.A.  
> **Module Path:** `odoo/addons/website_sale_collect/`

## Overview

`website_sale_collect` implements the **Click & Collect** (Buy Online, Pick up in Store) feature. Customers can check real-time in-store stock, select a pickup location based on proximity, pay online or on-site, and collect their order at a physical store.

**Dependencies:** `base_geolocalize`, `payment_custom`, `website_sale_stock`

**Module structure:**

```
website_sale_collect/
├── __init__.py              # post_init_hook, uninstall_hook
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── main.py              # WebsiteSaleCollect (extends WebsiteSale)
│   ├── delivery.py          # InStoreDelivery (extends Delivery)
│   └── payment.py           # OnSitePaymentPortal (extends PaymentPortal)
├── models/
│   ├── __init__.py
│   ├── delivery_carrier.py  # delivery_type='in_store'
│   ├── payment_provider.py  # custom_mode='on_site'
│   ├── payment_transaction.py
│   ├── product_template.py
│   ├── res_config_settings.py
│   ├── sale_order.py
│   ├── stock_warehouse.py
│   └── website.py
├── data/
│   ├── delivery_carrier_data.xml
│   ├── payment_method_data.xml
│   ├── payment_provider_data.xml
│   ├── product_product_data.xml
│   └── demo.xml
├── views/
│   ├── delivery_carrier_views.xml
│   ├── delivery_form_templates.xml
│   ├── res_config_settings_views.xml
│   ├── stock_picking_views.xml
│   ├── stock_warehouse_views.xml
│   └── templates.xml
├── utils.py                 # format_product_stock_values(), calculate_partner_distance()
├── const.py                 # DEFAULT_PAYMENT_METHOD_CODES = {'pay_on_site'}
└── static/src/
    ├── interactions/         # OWL components (ClickAndCollectAvailability)
    ├── js/
    ├── tests/
    └── xml/
```

---

## L1: Sale Order Extensions for In-Store Collection

### Extended Models Summary

| Model | Kind | Key Extension |
|-------|------|---------------|
| `delivery.carrier` | Extended | Added `delivery_type='in_store'` and `warehouse_ids` |
| `sale.order` | Extended | Overrode 8 methods for warehouse, fiscal position, and stock validation |
| `stock.warehouse` | Extended | Added `opening_hours` (resource.calendar) |
| `website` | Extended | Added computed `in_store_dm_id` and stock qty methods |
| `product.template` | Extended | Added Click & Collect availability info to `_get_additionnal_combination_info` |
| `payment.provider` | Extended | Added `custom_mode='on_site'` selection option |
| `payment.transaction` | Extended | Auto-confirm draft orders on on-site payment completion |
| `res.config.settings` | Extended | Added `action_view_in_store_delivery_methods` |

### Core Business Flow

```
Customer selects product on website
  ↓
Widget: ClickAndCollectAvailability
  → Calls _in_store_get_close_locations()
  → Sorts warehouses by Haversine distance
  → Displays stock per warehouse
  ↓
Customer selects pickup location / auto-selected if single warehouse
  → sale_order._set_pickup_location()
  → warehouse_id set from pickup_location_data
  → fiscal_position_id recomputed
  ↓
Checkout: stock validated per selected warehouse
  → sale_order._check_cart_is_ready_to_be_paid()
  ↓
Payment (two options):
  A) Online: standard payment flow → order confirmed → picking created
  B) On-site: custom payment provider with custom_mode='on_site'
     → payment_transaction._post_process()
     → auto-confirms draft sale order
     → picking created immediately
  ↓
Customer picks up order at store (stock.picking validated in warehouse)
```

---

## L2: Field-Level Documentation

### `delivery.carrier` — Extended Fields

**File:** `models/delivery_carrier.py`  
**Inherits:** `delivery.carrier`

| Field | Type | Required | Default | Ondelete | Description |
|-------|------|----------|---------|----------|-------------|
| `delivery_type` | Selection | — | — | — | Extended: added `('in_store', 'Pick up in store')`; `ondelete={'in_store': 'set default'}` |
| `warehouse_ids` | Many2many `stock.warehouse` | No | — | — | Stores (warehouses) available for this in-store delivery method |

**`ondelete={'in_store': 'set default'}` behavior:** If the `in_store` delivery type is removed from the selection (e.g., a module uninstall), any carrier with `delivery_type='in_store'` falls back to the first available selection option.

**Constraints:**

```python
@api.constrains('delivery_type', 'is_published', 'warehouse_ids')
def _check_in_store_dm_has_warehouses_when_published(self):
    # Published in-store carrier must have at least one warehouse
    if any(dm for dm in self
           if dm.delivery_type == 'in_store' and dm.is_published
           and not dm.warehouse_ids):
        raise ValidationError(
            _("The delivery method must have at least one warehouse to be published.")
        )

@api.constrains('delivery_type', 'company_id', 'warehouse_ids')
def _check_warehouses_have_same_company(self):
    # Carrier and all its warehouses must share the same company
    for dm in self:
        if dm.delivery_type == 'in_store' and dm.company_id:
            if any(wh.company_id and dm.company_id != wh.company_id
                   for wh in dm.warehouse_ids):
                raise ValidationError(_(
                    "The delivery method and a warehouse must share the same company"
                ))
```

**`create()` hook for `delivery_type='in_store'`:**

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('delivery_type') == 'in_store':
            vals['integration_level'] = 'rate'     # No live rate fetch
            vals['allow_cash_on_delivery'] = False  # Explicitly disabled

            # Auto-assign warehouses from the carrier's company
            if 'company_id' in vals:
                company_id = vals.get('company_id')
            else:
                company_id = (
                    self.env['product.product'].browse(vals.get('product_id')).company_id.id
                    or self.env.company.id
                )
            warehouses = self.env['stock.warehouse'].search(
                [('company_id', 'in', company_id)]
            )
            vals.update({
                'warehouse_ids': [Command.set(warehouses.ids)],
                'is_published': bool(warehouses),  # Auto-publish if warehouses found
            })
    return super().create(vals_list)
```

**`write()` hook for `delivery_type='in_store'`:**

```python
def write(self, vals):
    if vals.get('delivery_type') == 'in_store':
        vals['integration_level'] = 'rate'
        vals['allow_cash_on_delivery'] = False
    return super().write(vals)
```

---

### `sale.order` — Overridden Methods

**File:** `models/sale_order.py`  
**Inherits:** `sale.order` (from `sale`)

#### `_compute_warehouse_id`

```python
def _compute_warehouse_id(self):
    # Partition: skip recompute for in_store orders that already have pickup_location_data
    in_store_orders = self.filtered(
        lambda so: so.carrier_id.delivery_type == 'in_store' and so.pickup_location_data
    )
    # Compute normally for all others
    super(SaleOrder, self - in_store_orders)._compute_warehouse_id()
    # For in_store orders: set warehouse directly from stored pickup_location_data
    for order in in_store_orders:
        order.warehouse_id = order.pickup_location_data['id']
```

**Purpose:** Prevents `website_sale_stock` from overwriting the warehouse selected by the pickup location with the website's default warehouse.

#### `_compute_fiscal_position_id`

```python
def _compute_fiscal_position_id(self):
    in_store_orders = self.filtered(
        lambda so: so.carrier_id.delivery_type == 'in_store' and so.pickup_location_data
    )
    AccountFiscalPosition = self.env['account.fiscal.position'].sudo()
    for order in in_store_orders:
        # Use warehouse partner as delivery address for fiscal position
        order.fiscal_position_id = AccountFiscalPosition._get_fiscal_position(
            order.partner_id, delivery=order.warehouse_id.partner_id
        )
    super(SaleOrder, self - in_store_orders)._compute_fiscal_position_id()
```

**Purpose:** Fiscal position is determined by the **pickup store's address** (warehouse partner), not the customer's shipping address. This ensures correct B2B/B2C tax calculation when the store is in a different region than the customer.

#### `_set_delivery_method`

```python
def _set_delivery_method(self, delivery_method, rate=None):
    was_in_store_order = (
        self.carrier_id.delivery_type == 'in_store'
        and delivery_method.delivery_type != 'in_store'
    )
    super()._set_delivery_method(delivery_method, rate=rate)
    if was_in_store_order:  # Switching away from in-store
        self._compute_warehouse_id()         # Reset warehouse to default
        self._compute_fiscal_position_id()    # Reset fiscal position
```

**Purpose:** When customer switches from Click & Collect to home delivery, warehouse and fiscal position are recalculated from the website defaults.

#### `_set_pickup_location`

```python
def _set_pickup_location(self, pickup_location_data):
    super()._set_pickup_location(pickup_location_data)
    if self.carrier_id.delivery_type != 'in_store':
        return

    self.pickup_location_data = json.loads(pickup_location_data)
    if self.pickup_location_data:
        self.warehouse_id = self.pickup_location_data['id']
        self._compute_fiscal_position_id()
    else:  # Location cleared
        self._compute_warehouse_id()
```

#### `_get_pickup_locations`

```python
def _get_pickup_locations(self, zip_code=None, country=None, **kwargs):
    # GeoIP fallback: if zip_code present but country missing, derive from
    # stored pickup_location_data or request's GeoIP country code
    if zip_code and not country:
        country_code = (
            self.pickup_location_data['country_code']
            if self.pickup_location_data
            else request.geoip.country_code
        )
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        if not country:
            zip_code = None  # Skip parent's assert to prevent crash
    return super()._get_pickup_locations(zip_code=zip_code, country=country, **kwargs)
```

#### `_check_cart_is_ready_to_be_paid`

```python
def _check_cart_is_ready_to_be_paid(self):
    if (self._has_deliverable_products()
            and self.carrier_id.delivery_type == 'in_store'
            and not self._is_in_stock(self.warehouse_id.id)):
        raise ValidationError(self.env._(
            "Some products are not available in the selected store."
        ))
    return super()._check_cart_is_ready_to_be_paid()
```

#### `_verify_updated_quantity`

```python
def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
    product = self.env['product.product'].browse(product_id)
    if (product.is_storable
            and not product.allow_out_of_stock_order
            and self.website_id.in_store_dm_id):
        return new_qty, ''  # Skip stock check during cart update
    return super()._verify_updated_quantity(order_line, product_id, new_qty, uom_id, **kwargs)
```

**Purpose:** Skips the immediate stock check (from `website_sale_stock`) when Click & Collect is enabled. Stock is validated later at checkout (`_check_cart_is_ready_to_be_paid`) to allow customers to add out-of-stock items temporarily.

---

### `sale.order` — Utility Methods

#### `_prepare_in_store_default_location_data`

```python
def _prepare_in_store_default_location_data(self):
    """Prepare default pickup locations for in-store delivery methods.
    Only auto-pre-selects a warehouse if a delivery method has exactly 1 warehouse."""
    default_pickup_locations = {}
    for dm in self._get_delivery_methods():
        if (dm.delivery_type == 'in_store'
                and dm.id != self.carrier_id.id
                and len(dm.warehouse_ids) == 1):
            pickup_location_data = dm.warehouse_ids[0]._prepare_pickup_location_data()
            if pickup_location_data:
                default_pickup_locations[dm.id] = {
                    'pickup_location_data': pickup_location_data,
                    'insufficient_stock_data': self._get_insufficient_stock_data(
                        pickup_location_data['id']
                    ),
                }
    return {'default_pickup_locations': default_pickup_locations}
```

#### `_is_in_stock` and `_get_insufficient_stock_data`

```python
def _is_in_stock(self, wh_id):
    """True if all storable products have sufficient stock in warehouse."""
    return not self._get_insufficient_stock_data(wh_id)

def _get_insufficient_stock_data(self, wh_id):
    """Maps order lines with insufficient stock to max available quantity.
    Also sets shop_warning on the order line."""
    insufficient_stock_data = {}
    for product, ols in self.order_line.grouped('product_id').items():
        if not product.is_storable or product.allow_out_of_stock_order:
            continue
        free_qty = product.with_context(warehouse_id=wh_id).free_qty
        for ol in ols:
            free_qty_in_uom = max(int(product.uom_id._compute_quantity(
                free_qty, ol.product_uom_id, rounding_method="DOWN"
            )), 0)
            line_qty_in_uom = ol.product_uom_qty
            if line_qty_in_uom > free_qty_in_uom:
                insufficient_stock_data[ol] = free_qty_in_uom
                ol.shop_warning = self.env._(
                    "%(available_qty)s/%(line_qty)s available at this location",
                    available_qty=free_qty_in_uom, line_qty=int(line_qty_in_uom),
                )
            free_qty -= ol.product_uom_id._compute_quantity(line_qty_in_uom, product.uom_id)
    return insufficient_stock_data
```

Key detail: free quantity is **decremented per order line** (for multiple lines of the same product), so total stock is correctly split across lines.

---

### `stock.warehouse` — Extended Fields

**File:** `models/stock_warehouse.py`  
**Inherits:** `stock.warehouse`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `opening_hours` | Many2one `resource.calendar` | No | Business hours used to display store availability in the widget |

#### `_prepare_pickup_location_data`

```python
def _prepare_pickup_location_data(self):
    # 1. Geo-localize if coordinates are missing
    wh_location = self.partner_id
    if (wh_location.partner_latitude, wh_location.partner_longitude) == (0, 0):
        wh_location.geo_localize()
        if still missing: assign (1000, 1000) to prevent OpenStreetMap spam

    # 2. Format address values (title-case)
    pickup_location_values = {
        'id': self.id,
        'name': wh_location['name'].title(),
        'street': wh_location.street.title(),
        'city': wh_location.city.title(),
        'state': wh_location.state_id.code or '',
        'zip_code': wh_location.zip or '',
        'country_code': wh_location.country_code,
        'latitude': wh_location.partner_latitude,
        'longitude': wh_location.partner_longitude,
    }

    # 3. Format opening hours from resource.calendar
    if self.opening_hours:
        opening_hours_dict = {str(i): [] for i in range(7)}  # Mon–Sun
        for att in self.opening_hours.attendance_ids:
            if att.day_period in ('morning', 'afternoon', 'full_day'):
                opening_hours_dict[att.dayofweek].append(
                    f'{format_duration(att.hour_from)} - {format_duration(att.hour_to)}'
                )
        pickup_location_values['opening_hours'] = opening_hours_dict
    else:
        pickup_location_values['opening_hours'] = {}
    return pickup_location_values
```

---

### `website` — Extended Fields

**File:** `models/website.py`  
**Inherits:** `website`

| Field | Type | Stored | Description |
|-------|------|--------|-------------|
| `in_store_dm_id` | Many2one `delivery.carrier` | No (computed) | First published `in_store` carrier matching this website and company |

```python
def _compute_in_store_dm_id(self):
    in_store_delivery_methods = self.env['delivery.carrier'].search([
        ('delivery_type', '=', 'in_store'),
        ('is_published', '=', True),
    ])
    for website in self:
        website.in_store_dm_id = in_store_delivery_methods.filtered_domain([
            '|', ('website_id', '=', False), ('website_id', '=', website.id),
            '|', ('company_id', '=', False), ('company_id', '=', website.company_id.id),
        ])[:1]
```

---

### `payment.provider` — Extended Fields

**File:** `models/payment_provider.py`  
**Inherits:** `payment.provider`

| Field | Type | Added Value | Description |
|-------|------|-------------|-------------|
| `custom_mode` | Selection | `[('on_site', 'Pay on site')]` | New payment mode for in-store collection |

#### `_get_compatible_providers` override

On-site payment providers are **filtered out** unless:
1. The order's delivery type is `'in_store'`, **AND**
2. The order contains at least one consumable (`type='consu'`) product

```python
compatible_providers = super()._get_compatible_providers(...)
order = self.env['sale.order'].browse(sale_order_id).exists()

if order.carrier_id.delivery_type != 'in_store' \
   or not any(product.type == 'consu' for product in order.order_line.product_id):
    # Remove on_site providers from compatible list
    compatible_providers = compatible_providers.filtered(
        lambda p: p.code != 'custom' or p.custom_mode != 'on_site'
    )
    payment_utils.add_to_report(
        report,
        unfiltered_providers - compatible_providers,
        available=False,
        reason=_("no in-store delivery methods available"),
    )
```

---

## L3: Cross-Module, Override Patterns, and Workflow Triggers

### Cross-Module Dependency Chain

```
website_sale_collect
├── base_geolocalize          # geo_localize() on partners
├── payment_custom            # custom payment provider support
│   └── payment               # payment.provider, payment.transaction
│       └── sale              # sale.order is source for payment
└── website_sale_stock        # stock per warehouse on website
    ├── website_sale           # e-commerce base
    │   └── website            # website model
    └── stock                 # stock.warehouse
        └── product           # product.product (free_qty)
```

### Key Override Patterns

#### Pattern 1: Conditional Method Partition

Many overrides in `sale_order.py` use a **partition pattern** — filter records matching the in-store condition, handle those specially, then delegate the rest to `super()`:

```python
def _compute_warehouse_id(self):
    in_store = self.filtered(lambda so: so.carrier_id.delivery_type == 'in_store'
                             and so.pickup_location_data)
    super(SaleOrder, self - in_store)._compute_warehouse_id()  # Normal handling
    for order in in_store:
        order.warehouse_id = order.pickup_location_data['id']  # Custom handling
```

This avoids repeating the entire parent method and only injects in-store-specific logic.

#### Pattern 2: Stateful Warehouse Assignment via `pickup_location_data`

The `pickup_location_data` JSON field (inherited from `website_sale`) acts as a **state carrier**. Once set, `_compute_warehouse_id` skips reassignment, preserving the customer's store selection even when other computed fields are refreshed.

#### Pattern 3: Stock Check Deferred to Checkout

```python
def _verify_updated_quantity(...):
    # Skip stock check during cart update
    if product.is_storable and ... and self.website_id.in_store_dm_id:
        return new_qty, ''
    return super()._verify_updated_quantity(...)
```

Contrast with `website_sale_stock` which raises immediately on insufficient stock. This allows customers to add items to cart even if a store location temporarily runs out.

#### Pattern 4: Fiscal Position from Warehouse Partner

```python
order.fiscal_position_id = AccountFiscalPosition._get_fiscal_position(
    order.partner_id, delivery=order.warehouse_id.partner_id
)
```

Fiscal position is computed from the **store's address** (warehouse's partner) rather than the customer's delivery address. This handles cases where a store is in a special economic zone or different tax jurisdiction than the customer's location.

#### Pattern 5: Auto-Confirm on On-Site Payment

```python
def _post_process(self):
    on_site_pending_txs = self.filtered(
        lambda tx: tx.provider_id.custom_mode == 'on_site'
                   and tx.state == 'pending'
    )
    on_site_pending_txs.sale_order_ids.filtered(
        lambda so: so.state == 'draft'
    ).with_context(send_email=True).action_confirm()
    super()._post_process()
```

When a customer selects "Pay on Site" and the payment transaction transitions to `pending` (payment instruction received), the draft order is **automatically confirmed** and a picking is created — even though actual payment happens at the physical counter.

### Workflow Triggers

| Event | Location | Effect |
|-------|----------|--------|
| Delivery type set to `'in_store'` | `delivery.carrier.create()` | Auto-assigns warehouses, sets `is_published=True`, `integration_level='rate'` |
| Pickup location selected | `sale_order._set_pickup_location()` | Sets `warehouse_id`, recomputes `fiscal_position_id` |
| Pickup location cleared | `sale_order._set_pickup_location()` | Resets `warehouse_id` to computed default |
| Switching from in-store to delivery | `sale_order._set_delivery_method()` | Resets warehouse and fiscal position |
| Checkout payment attempted | `sale_order._check_cart_is_ready_to_be_paid()` | Validates stock per selected warehouse; raises if insufficient |
| On-site payment pending | `payment_transaction._post_process()` | Auto-confirms draft sale order |
| Geo-localization on warehouse | `stock_warehouse._prepare_pickup_location_data()` | Calls `partner_id.geo_localize()` if coordinates missing |

### Modules Extended By `website_sale_collect`

| Module | Extension | What Is Added |
|--------|-----------|---------------|
| `delivery.carrier` | Field + methods | `delivery_type='in_store'`, `warehouse_ids`, `_in_store_get_close_locations`, `in_store_rate_shipment` |
| `sale.order` | 8 method overrides | In-store warehouse, fiscal position, stock validation |
| `stock.warehouse` | Field + method | `opening_hours`, `_prepare_pickup_location_data` |
| `website` | Field + methods | `in_store_dm_id`, `_compute_in_store_dm_id`, `_get_product_available_qty`, `_get_max_in_store_product_available_qty` |
| `product.template` | Method override | `show_click_and_collect_availability`, stock data for widget |
| `payment.provider` | Field + method | `custom_mode='on_site'`, `_get_compatible_providers` |
| `payment.transaction` | Method override | Auto-confirm draft orders on on-site payment |
| `res.config.settings` | Method | Action to view in-store delivery methods |

### OWL Component: `ClickAndCollectAvailability`

The frontend widget (`static/src/interactions/click_and_collect_availability.js`) calls `sale_order._in_store_get_close_locations()` via `_in_store_get_close_locations` RPC, which internally calls `utils.calculate_partner_distance()` using the **Haversine formula**:

```python
# Haversine distance in kilometers (utils.py)
R = 6371  # Earth radius
d = 2 * R * atan2(sqrt(arcsin), sqrt(1 - arcsin))
```

Locations are sorted by distance and returned as a list of dicts containing `{id, name, street, city, state, zip_code, country_code, latitude, longitude, distance, opening_hours, additional_data}`.

---

## L4: Version Change Odoo 18 to 19

### Changes in `website_sale_collect` (Odoo 18 → 19)

`website_sale_collect` is a **new module in Odoo 19**. It did not exist in Odoo 18 as a standalone module. The Click & Collect functionality was previously part of `website_sale_stock` in Odoo 18. This is a significant architectural change.

#### Odoo 18: Click & Collect embedded in `website_sale_stock`

In Odoo 18, the `website_sale_stock` module contained the `in_store` delivery type and related logic. The key files were `delivery_carrier.py` and `sale_order.py` within `website_sale_stock`.

#### Odoo 19: Standalone `website_sale_collect` module

Odoo 19 extracted Click & Collect into its own module with these implications:

| Aspect | Odoo 18 (inside `website_sale_stock`) | Odoo 19 (standalone `website_sale_collect`) |
|--------|----------------------------------------|---------------------------------------------|
| Module name | `website_sale_stock` | `website_sale_collect` (separated) |
| Dependencies | `website_sale` + `stock` | `website_sale_stock` + `payment_custom` + `base_geolocalize` |
| Installation | Part of website_sale | Separate install required |
| Stock validation | Inside `website_sale_stock` | Inside `website_sale_collect` |
| On-site payment | In `payment_custom` | In `website_sale_collect` |

#### Data Files Added

Odoo 19 introduces several data files that were not present in Odoo 18:

```xml
<!-- payment_method_data.xml -->
<!-- Creates payment.method 'pay_on_site' (code: pay_on_site) -->

<!-- payment_provider_data.xml -->
<!-- Creates payment.provider with code='custom', custom_mode='on_site' -->
<!-- Depends on payment_method 'pay_on_site' -->

<!-- product_product_data.xml -->
<!-- Creates the "Pick-up in Store" product (used as carrier product) -->

<!-- delivery_carrier_data.xml -->
<!-- Creates the default in-store delivery method -->
<!-- Depends on product 'Pick-up in Store' and module 'product_pick_up_in_store' -->
```

#### `const.py` Introduction

Odoo 19 introduces a `const.py` module (not present in Odoo 18's embedded implementation):

```python
# const.py
DEFAULT_PAYMENT_METHOD_CODES = {'pay_on_site'}
```

This is used by `payment_provider.py` to activate the correct payment method when the on-site provider is configured.

#### `post_init_hook` and `uninstall_hook`

```python
# __init__.py
def post_init_hook(env):
    # After installation: set up the 'custom' provider as on_site mode
    setup_provider(env, 'custom', custom_mode='on_site')

def uninstall_hook(env):
    # After uninstallation: reset the provider
    reset_payment_provider(env, 'custom', custom_mode='on_site')
```

In Odoo 18, this configuration was done directly in `payment_custom`. In Odoo 19, it is managed by the hooks.

#### `utils.py` — Haversine Formula Stable

The `calculate_partner_distance()` function and `format_product_stock_values()` are **unchanged** in behavior from Odoo 18 — they were simply moved from the embedded location to `utils.py`.

#### `stock_warehouse` Extension: `opening_hours` Field

The `opening_hours` Many2one field on `stock.warehouse` is **new in Odoo 19**. In Odoo 18, opening hours were not exposed as a dedicated field on the warehouse model — they were computed inline in the delivery module.

#### Stock Validation: `_get_insufficient_stock_data` New in Odoo 19

The grouping of order lines by product and decrementing free quantity per line is **new**:

```python
for product, ols in self.order_line.grouped('product_id').items():
    # grouped() groups lines by product_id (new in Odoo 19 OrderedSlice)
    for ol in ols:
        ...
        free_qty -= ol.product_uom_id._compute_quantity(line_qty_in_uom, product.uom_id)
```

The `.grouped()` method on recordset (introduced in Odoo 16) is used here. It returns a `defaultdict` mapping each unique value of the given field to the records having that value.

#### `_verify_updated_quantity`: Skipped Stock Check

In Odoo 18, `website_sale_stock` performed immediate stock validation on every cart quantity update, which could block adding out-of-stock items. Odoo 19's `website_sale_collect` **defers** this check to checkout, allowing more flexible cart management.

### Migration Notes for Upstream Customizations

If you have custom code that extended `website_sale_stock` to add Click & Collect functionality in Odoo 18:

1. **Module dependency:** Update `depends` from `['website_sale_stock']` to `['website_sale_collect']` in `__manifest__.py`
2. **Field references:** `delivery.carrier.delivery_type='in_store'` is unchanged
3. **Hook installation:** The `post_init_hook` now lives in `website_sale_collect`; if you had custom hook code, consolidate it with the new hook
4. **Payment provider:** On-site payment provider is now auto-created by `payment_provider_data.xml` — do not duplicate in custom data files
5. **Warehouse `opening_hours`:** Configure `resource.calendar` on warehouses if you want opening hours displayed in the widget

### Breaking Changes

- **Standalone module:** `website_sale_collect` must be installed separately from `website_sale_stock`; Click & Collect features are not available until it is installed
- **Data-driven configuration:** The default on-site payment provider and delivery method are created via XML data; if your migration imports data that conflicts with these xmlids (`website_sale_collect.payment_provider_on_site`, etc.), the data will be duplicated or the hook will fail

### Related Documentation

- [[Modules/website_sale]] — Base e-commerce
- [[Modules/website_sale_stock]] — Stock per warehouse (parent dependency)
- [[Modules/Stock]] — `stock.warehouse`, picking lifecycle
- [[Modules/account_payment]] — `payment.provider`, `payment.transaction`
- [[Core/Fields]] — Many2many, computed fields
- [[Tools/ORM Operations]] — `grouped()` on recordsets
