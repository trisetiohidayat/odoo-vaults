---
Module: website_sale_collect
Version: Odoo 18
Type: Integration
Tags: #odoo18, #e-commerce, #click-collect, #pickup, #in-store, #stock
Related Modules: [website_sale_stock](Modules/website-sale-stock.md), [website_sale](Modules/website-sale.md), [delivery](Modules/delivery.md), [stock](Modules/stock.md), [sale_stock](Modules/sale-stock.md)
See Also: [Modules/Stock](modules/stock.md) [Modules/website-sale](modules/website-sale.md) [Modules/website-sale-stock](modules/website-sale-stock.md)
---

# website_sale_collect — Click & Collect (Pickup in Store)

> **Module naming note:** In Odoo 18, this feature is named `website_sale_collect` (Click & Collect). In earlier versions it was called `website_sale_picking`. The `delivery_type` value used is `'in_store'`.

**Addon path:** `~/odoo/odoo18/odoo/addons/website_sale_collect/`
**Module key:** `website_sale_collect`
**Summary:** Allows customers to check in-store stock, pay on site, and pick up orders at the shop.
**Depends on:** `base_geolocalize`, `payment_custom`, `website_sale_stock`

---

## Architecture Overview

```
website_sale_collect
  ├── models/
  │     ├── delivery_carrier.py    ← delivery.carrier: in_store type, warehouse_ids
  │     ├── sale_order.py           ← sale.order: pickup store selection + stock check
  │     ├── payment_provider.py    ← payment.provider: on_site payment mode
  │     ├── payment_transaction.py ← payment.transaction: auto-confirm on on_site payment
  │     ├── product_template.py    ← product.template: in-store stock in combination info
  │     ├── stock_warehouse.py      ← stock.warehouse: opening_hours field
  │     ├── website.py              ← website: in_store_dm_id computed field
  │     └── res_config_settings.py  ← res.config.settings: link to delivery methods
  ├── controllers/
  │     ├── delivery.py             ← InStoreDelivery: pickup location + set location routes
  │     ├── main.py                 ← WebsiteSaleCollect: checkout + product page overrides
  │     └── payment.py              ← OnSitePaymentPortal: payment validation
  └── utils.py                      ← format_product_stock_values(), calculate_partner_distance()
        const.py                    ← DEFAULT_PAYMENT_METHOD_CODES = {'pay_on_site'}
```

**Dependency chain:**
```
website_sale_collect
  depends on: base_geolocalize, payment_custom, website_sale_stock
    └── website_sale_stock
          depends on: website_sale, sale_stock, stock_delivery
            └── website_sale
                  depends on: website, sale, delivery, ...
```

---

## Core Concept: `in_store` Delivery Type

The module extends `delivery.carrier` with a new delivery type value: `'in_store'` ("Pick up in store").

```
delivery.carrier.delivery_type:
  'fixed'           → Fixed price
  'base_on_rule'    → Rule-based pricing
  'in_store'        → [website_sale_collect] Pick up in store
```

When a carrier has `delivery_type = 'in_store'`:
- It is **excluded from express checkout** (no location picker in payment form)
- It uses `warehouse_ids` to determine which stores are available
- Its `rate_shipment()` always returns `price = product_id.list_price` (no delivery fee)
- A **pickup location** (specific warehouse) must be selected by the customer
- The selected warehouse's `opening_hours` are displayed in the location picker

---

## Models

### `delivery.carrier` (Extended by `website_sale_collect`)

**Module:** `website_sale_collect` | **Inherits:** `delivery.carrier`

#### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `delivery_type` | `Selection` | Extended with `('in_store', "Pick up in store")`. `ondelete={'in_store': 'set default'}` |
| `warehouse_ids` | `Many2many(stock.warehouse)` | Stores where customers can pick up orders. Required when published. |

#### Constraints

**`_check_in_store_dm_has_warehouses_when_published`**
```python
@api.constrains('delivery_type', 'is_published', 'warehouse_ids')
def _check_in_store_dm_has_warehouses_when_published(self):
    if any(self.filtered(
        lambda dm: dm.delivery_type == 'in_store'
        and dm.is_published
        and not dm.warehouse_ids
    )):
        raise ValidationError(
            _("The delivery method must have at least one warehouse to be published.")
        )
```
- A published in-store carrier must have at least one warehouse

**`_check_warehouses_have_same_company`**
```python
@api.constrains('delivery_type', 'company_id', 'warehouse_ids')
def _check_warehouses_have_same_company(self):
    for dm in self:
        if dm.delivery_type == 'in_store' and dm.company_id and any(
            wh.company_id and dm.company_id != wh.company_id for wh in dm.warehouse_ids
        ):
            raise ValidationError(
                _("The delivery method and a warehouse must share the same company")
            )
```

#### Lifecycle Hooks

**`create(vals_list)` / `write(vals)`**
```python
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('delivery_type') == 'in_store':
            vals['integration_level'] = 'rate'  # Always rate-only for in_store
    return super().create(vals_list)

def write(self, vals):
    if vals.get('delivery_type') == 'in_store':
        vals['integration_level'] = 'rate'
    return super().write(vals)
```
- `integration_level` is forced to `'rate'` (never `'rate_and_ship'`) for in-store delivery

#### Key Methods

**`in_store_rate_shipment(order)`**

```python
def in_store_rate_shipment(self, *_args):
    return {
        'success': True,
        'price': self.product_id.list_price,  # Fixed: store pickup is free
        'error_message': False,
        'warning_message': False,
    }
```

- The delivery fee is always the product's `list_price`
- The "delivery fee" is really the **pickup fee** (could represent a booking fee or service charge)

**`_in_store_get_close_locations(partner_address, product_id=None)`**

Returns all warehouses in `warehouse_ids`, sorted by distance to the customer's address:

```python
def _in_store_get_close_locations(self, partner_address, product_id=None):
    # 1. Geo-localize the customer address
    partner_address.geo_localize()

    # 2. For each warehouse, compute stock + distance
    for wh in self.warehouse_ids:
        if product:  # Called from product page
            in_store_stock_data = utils.format_product_stock_values(product, wh.id)
        else:        # Called from checkout
            in_store_stock_data = {'in_store_stock': order_sudo._is_in_stock(wh.id)}

        wh_location = wh.partner_id
        pickup_location_values = {
            'id': wh.id,
            'name': wh_location.name.title(),
            'street': wh_location.street.title(),
            'city': wh_location.city.title(),
            'zip_code': wh_location.zip or '',
            'country_code': wh_location.country_code,
            'state': wh_location.state_id.code,
            'latitude': wh_location.partner_latitude,
            'longitude': wh_location.partner_longitude,
            'additional_data': {'in_store_stock': in_store_stock_data},
            'opening_hours': {dayofweek: [slots], ...},
            'distance': utils.calculate_partner_distance(partner_address, wh_location),
        }

    return sorted(pickup_locations, key=lambda k: k['distance'])
```

- Distance calculated via **Haversine formula** (in kilometers)
- `geo_localize()` uses OpenStreetMap (Nominatim) to geocode addresses
- Returns warehouses even if they have no stock (stock data included in `additional_data`)

---

### `sale.order` (Extended by `website_sale_collect`)

**Module:** `website_sale_collect` | **Inherits:** `sale.order`

#### Key Override: `_compute_warehouse_id()`

```python
def _compute_warehouse_id(self):
    # Skip orders where warehouse was set by pickup_location_data
    in_store_orders_with_pickup_data = self.filtered(
        lambda so: (
            so.carrier_id.delivery_type == 'in_store' and so.pickup_location_data
        )
    )
    super(SaleOrder, self - in_store_orders_with_pickup_data)._compute_warehouse_id()
    for order in in_store_orders_with_pickup_data:
        order.warehouse_id = order.pickup_location_data['id']  # Use selected store
```

- For in-store orders with a selected location: sets `warehouse_id` from `pickup_location_data['id']`
- This ensures **stock picking** is generated from the **chosen store's warehouse**

#### Key Override: `_set_delivery_method()`

```python
def _set_delivery_method(self, delivery_method, rate=None):
    was_in_store_order = (
        self.carrier_id.delivery_type == 'in_store'
        and delivery_method.delivery_type != 'in_store'
    )
    super()._set_delivery_method(delivery_method, rate=rate)
    if was_in_store_order:
        self._compute_warehouse_id()        # Reset warehouse
        self._compute_fiscal_position_id()  # Reset fiscal position
```

- When switching **away from** in-store delivery: resets warehouse and fiscal position
- This is critical for correct tax calculation when switching from in-store to home delivery

#### Key Override: `_set_pickup_location()`

```python
def _set_pickup_location(self, pickup_location_data):
    res = super()._set_pickup_location(pickup_location_data)
    if self.carrier_id.delivery_type != 'in_store':
        return res

    self.pickup_location_data = json.loads(pickup_location_data)
    if self.pickup_location_data:
        self.warehouse_id = self.pickup_location_data['id']
        # Apply fiscal position based on the warehouse's address
        AccountFiscalPosition = self.env['account.fiscal.position'].sudo()
        self.fiscal_position_id = AccountFiscalPosition._get_fiscal_position(
            self.partner_id, delivery=self.warehouse_id.partner_id
        )
    else:
        self._compute_warehouse_id()

    return res
```

- When a pickup location is selected: sets `warehouse_id` AND recalculates fiscal position
- Fiscal position uses the **warehouse's partner address** (not the customer's)
- This handles B2B intra-EU transactions correctly when picking up from a branch in a different country

#### Key Override: `_get_pickup_locations()`

```python
def _get_pickup_locations(self, zip_code=None, country=None, **kwargs):
    # Ensure country is provided when zip_code is present
    if zip_code and not country:
        country_code = None
        if self.pickup_location_data:
            country_code = self.pickup_location_data['country_code']
        elif request.geoip.country_code:
            country_code = request.geoip.country_code
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        if not country:
            zip_code = None  # Reset to skip the parent's assert
    return super()._get_pickup_locations(zip_code=zip_code, country=country, **kwargs)
```

- If the GeoIP country lookup fails, the zip code is cleared so the parent's assertion doesn't fail
- Falls back to previously selected location's country

#### Key Override: `_get_cart_and_free_qty()`

```python
def _get_cart_and_free_qty(self, product, line=None):
    cart_qty, free_qty = super()._get_cart_and_free_qty(product, line=line)
    if self.carrier_id.delivery_type == 'in_store':
        # Get free_qty from the SELECTED WAREHOUSE, not the website's default
        free_qty = (product or line.product_id).with_context(
            warehouse_id=self.warehouse_id.id
        ).free_qty
    return cart_qty, free_qty
```

- When `in_store` carrier is selected: `free_qty` is checked against **the selected store's warehouse**, not the website's default warehouse
- This enables accurate "only X available" warnings for the specific pickup location

#### Key Override: `_check_cart_is_ready_to_be_paid()`

```python
def _check_cart_is_ready_to_be_paid(self):
    if (
        self._has_deliverable_products()
        and self.carrier_id.delivery_type == 'in_store'
        and not self._is_in_stock(self.warehouse_id.id)
    ):
        raise ValidationError(_("Some products are not available in the selected store."))
    return super()._check_cart_is_ready_to_be_paid()
```

- Called during payment processing
- Raises if any product is out of stock at the selected pickup store

#### Stock Check Methods

**`_is_in_stock(wh_id)`** — Returns `True` if all storable products in the cart are in stock at the warehouse.

**`_get_unavailable_order_lines(wh_id)`** — Returns order lines where `product_uom_qty > free_qty` at the warehouse.

---

### `stock.warehouse` (Extended by `website_sale_collect`)

**Module:** `website_sale_collect` | **Inherits:** `stock.warehouse`

#### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `opening_hours` | `Many2one(resource.calendar)` | Opening hours schedule for this store. Used in location picker. |

```python
opening_hours = fields.Many2one(
    string="Opening Hours",
    comodel_name='resource.calendar',
    check_company=True
)
```

- Displayed in the store location selector as day-by-day time slots
- Hours are formatted using `odoo.tools.misc.format_duration()`

---

### `website` (Extended by `website_sale_collect`)

**Module:** `website_sale_collect` | **Inherits:** `website`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `in_store_dm_id` | `Many2one(delivery.carrier)` | Computed: the active in-store delivery method for this website |

```python
def _compute_in_store_dm_id(self):
    in_store_delivery_methods = self.env['delivery.carrier'].search([
        ('delivery_type', '=', 'in_store'),
        ('is_published', '=', True)
    ])
    for website in self:
        website.in_store_dm_id = in_store_delivery_methods.filtered_domain([
            '|', ('website_id', '=', False), ('website_id', '=', website.id),
            '|', ('company_id', '=', False), ('company_id', '=', website.company_id.id),
        ])[:1]
```

- Searches all published `in_store` carriers
- Filters by: website matches AND company matches
- Returns the first matching carrier (or empty)

#### Key Methods

**`_get_product_available_qty(product)`**

```python
def _get_product_available_qty(self, product, **kwargs):
    free_qty = super()._get_product_available_qty(product, **kwargs)
    if self.warehouse_id and self.sudo().in_store_dm_id:
        # Include stock from in-store warehouses
        free_qty = max(free_qty, self._get_max_in_store_product_available_qty(product))
    return free_qty
```

- Returns the maximum free quantity across both the website warehouse and in-store warehouses
- This prevents "out of stock" on the product page when another store has availability

**`_get_max_in_store_product_available_qty(product)`**

```python
def _get_max_in_store_product_available_qty(self, product):
    return max([
        product.with_context(warehouse_id=wh.id).free_qty
        for wh in self.sudo().in_store_dm_id.warehouse_ids
    ], default=0)
```

- Maximum stock across all in-store warehouses
- Used on the product page to show "available at other stores"

---

### `payment.provider` (Extended by `website_sale_collect`)

**Module:** `website_sale_collect` | **Inherits:** `payment.provider`

#### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `custom_mode` | `Selection` | Extended with `('on_site', "Pay on site")` |

#### Key Override: `_get_compatible_providers()`

```python
def _get_compatible_providers(self, company_id, ..., sale_order_id=None, ...):
    compatible_providers = super()._get_compatible_providers(...)

    order = self.env['sale.order'].browse(sale_order_id).exists()

    # Show on-site only if in-store delivery AND physical products exist
    if order.carrier_id.delivery_type != 'in_store' or not any(
        product.type == 'consu' for product in order.order_line.product_id
    ):
        # Remove on-site providers from the compatible list
        compatible_providers = compatible_providers.filtered(
            lambda p: p.code != 'custom' or p.custom_mode != 'on_site'
        )
        payment_utils.add_to_report(
            report,
            unfiltered_providers - compatible_providers,
            available=False,
            reason=_("no in-store delivery methods available"),
        )

    return compatible_providers
```

- `on_site` payment is only shown when:
  1. The order uses `in_store` delivery, AND
  2. The order contains physical/consumable products

---

### `payment.transaction` (Extended by `website_sale_collect`)

**Module:** `website_sale_collect` | **Inherits:** `payment.transaction`

#### Key Override: `_post_process()`

```python
def _post_process(self):
    on_site_pending_txs = self.filtered(
        lambda tx: tx.provider_id.custom_mode == 'on_site' and tx.state == 'pending'
    )
    on_site_pending_txs.sale_order_ids.filtered(
        lambda so: so.state == 'draft'
    ).with_context(send_email=True).action_confirm()
    super()._post_process()
```

- When an `on_site` payment is marked as `pending` (e.g., cash on pickup): the order is **automatically confirmed**
- This is the "pay at pickup" flow — no online payment needed

---

### `product.template` (Extended by `website_sale_collect`)

**Module:** `website_sale_collect` | **Inherits:** `product.template`

#### Key Override: `_get_additionnal_combination_info()`

Adds in-store stock data to product page combination info:

```python
def _get_additionnal_combination_info(self, product_or_template, quantity, date, website):
    res = super()._get_additionnal_combination_info(...)

    if (
        bool(website.sudo().in_store_dm_id)       # Click & Collect is enabled
        and product_or_template.is_product_variant
        and product_or_template.is_storable
    ):
        res['show_click_and_collect_availability'] = True

        order_sudo = website.sale_get_order()
        if (
            order_sudo
            and order_sudo.carrier_id.delivery_type == 'in_store'
            and order_sudo.pickup_location_data
        ):
            # Show stock at the selected store
            res['in_store_stock'] = utils.format_product_stock_values(
                product_or_template.sudo(),
                wh_id=order_sudo.pickup_location_data['id']
            )
        else:
            # Show max stock across all stores
            res['in_store_stock'] = utils.format_product_stock_values(
                product_or_template.sudo(),
                free_qty=website.sudo()._get_max_in_store_product_available_qty(
                    product_or_template.sudo()
                )
            )

    return res
```

---

## Utilities

### `utils.py`

**`format_product_stock_values(product, wh_id=None, free_qty=None)`**

```python
def format_product_stock_values(product, wh_id=None, free_qty=None):
    if product.is_product_variant:
        if free_qty is None:
            free_qty = product.with_context(warehouse_id=wh_id).free_qty
        return {
            'in_stock': free_qty > 0,
            'show_quantity': product.show_availability and product.available_threshold >= free_qty,
            'quantity': free_qty,
        }
    else:
        return {}
```

**`calculate_partner_distance(partner1, partner2)`**

Haversine formula implementation. Returns distance in **kilometers**:
```python
R = 6371  # Earth's radius in km
d = 2 * R * atan2(sqrt(haversin), sqrt(1 - haversin))
```

---

## Checkout Flow for Click & Collect

```
1. Customer adds product → cart
2. Customer goes to checkout → /shop/checkout
3. Delivery methods displayed:
     ✓ Standard Delivery (FedEx, etc.)
     ✓ Pick up in store ← in_store carrier
4. Customer selects "Pick up in store"
5. Location picker shown:
     - Sorted by distance (Haversine)
     - Shows: name, address, opening hours, stock status
6. Customer selects a store
7. _set_pickup_location() called:
     - pickup_location_data set
     - warehouse_id = selected_store.id
     - fiscal_position recalculated for warehouse's country
8. Stock validation:
     - _is_in_stock(warehouse_id) called
     - If OOS: "Some products not available in selected store"
9. Payment:
     - If on_site: "Pay on site" option available
     - On pending tx: order auto-confirmed via _post_process()
10. Order confirmation:
     - _action_confirm() → creates stock.picking from selected_store warehouse
     - Customer receives pickup notification
```

---

## Controller Routes

### `website_sale_collect/controllers/delivery.py`

| Route | Method | Description |
|-------|--------|-------------|
| `GET /website_sale/get_pickup_locations` (override) | `website_sale_get_pickup_locations()` | Forces in_store carrier on order when called from product page |
| `POST /shop/set_click_and_collect_location` | `shop_set_click_and_collect_location()` | Set pickup location on current order |
| `POST /shop/express/shipping_address_change` (override) | `_get_delivery_methods_express_checkout()` | **Excludes in_store from express checkout** |

### `website_sale_collect/controllers/main.py`

| Route | Method | Description |
|-------|--------|-------------|
| Product page (override) | `_prepare_product_values()` | Includes `selected_wh_location` and `zip_code` for in-store stock display |
| Checkout page (override) | `_prepare_checkout_page_values()` | Includes `unavailable_order_lines` for selected pickup location |
| Payment validation (override) | `_get_shop_payment_errors()` | Adds error if pickup location not selected or out of stock |

---

## Key Takeaways

1. **`website_sale_collect` is the Odoo 18 Click & Collect module** — formerly `website_sale_picking`
2. **`in_store` delivery type** extends `delivery.carrier.delivery_type`; excluded from express checkout (no location picker)
3. **`warehouse_ids`** on carrier defines available pickup stores; must have at least one when published
4. **`pickup_location_data`** (JSON) stores the selected store's address, coordinates, opening hours, and stock status
5. **Fiscal position** is recalculated when a store is selected — uses the warehouse's country, not the customer's
6. **Stock is checked per-warehouse** — `free_qty` is computed against the selected store's warehouse
7. **`on_site` payment** is a `payment.provider.custom_mode` option — auto-confirms the order when payment is marked pending
8. **Opening hours** come from `resource.calendar` linked to `stock.warehouse`
9. **Distance sorting** uses Haversine formula between customer's address and warehouse's partner address
10. **Auto-install:** `website_sale_collect` has `auto_install: True` in `website_sale_stock`, making it available when `website_sale` is installed
