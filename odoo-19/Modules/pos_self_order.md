---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #pos
  - #self-order
---

# pos_self_order

## Overview

| Attribute | Value |
|-----------|-------|
| **Name** | POS Self Order |
| **Category** | Sales/Point Of Sale |
| **Version** | 1.0 |
| **Depends** | `pos_restaurant`, `http_routing`, `link_tracker` |
| **Auto-install** | `pos_restaurant` |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |

## Description

The POS Self Order module enables customers to browse menus and place orders independently via three distinct modes:

- **Consultation** (`consultation`): QR code links to a read-only menu (no ordering) — introduced in Odoo 19
- **Mobile** (`mobile`): Full ordering via customer smartphone, table-linked via QR code
- **Kiosk** (`kiosk`): Dedicated self-service terminal, no cash payments, "pay after each order" forced

The customer-facing interface is a standalone web app served at `/pos-self/<config_id>/products` (or `/pos-self/<config_id>/products?access_token=...&table_identifier=...` for table-linked orders). Data is loaded once at session start via `load_self_data()` and synchronized via WebSocket long-polling (`_notify`, `_send_notification`).

---

## Module Dependencies and Architecture

```
pos_self_order
├── depends: pos_restaurant, http_routing, link_tracker
│   ├── pos_restaurant   → restaurant.table, restaurant.floor, pos.preset
│   ├── http_routing     → routing for /pos-self/* public routes
│   └── link_tracker     → short URL generation for QR codes
└── auto_install: pos_restaurant
```

**`pos.load.mixin`** is the central architectural pattern. Every model that participates in the self-order data stream implements three mixin methods:

```python
@api.model
def _load_pos_self_data_search_read(self, data, config):  # filter + search + read
@api.model
def _load_pos_self_data_domain(self, data, config):       # filter records
@api.model
def _load_pos_self_data_fields(self, config):             # which fields to send
def _load_pos_self_data_read(self, records, config):      # read them (override point)
```

This is a parallel to `_load_pos_data_*` but scoped to self-order's needs (e.g., `product.template` filters `self_order_available=True`, `res.partner` returns `False` meaning "don't send partners at all").

### Inheriting from `pos.load.mixin`

The module's own `PosLoadMixin` (`pos_self_order/models/pos_load_mixin.py`) inherits the base `pos.load.mixin` (from `point_of_sale/models/pos_load_mixin.py`) and provides the default delegation chain:

```python
class PosLoadMixin(models.AbstractModel):
    _inherit = "pos.load.mixin"

    @api.model
    def _load_pos_self_data_search_read(self, data, config):
        domain = self._load_pos_self_data_domain(data, config)
        if domain is False:
            return []
        records = self.search(domain)
        return self._load_pos_self_data_read(records, config)

    @api.model
    def _load_pos_self_data_domain(self, data, config):
        return self._load_pos_data_domain(data, config)  # defaults to base POS domain

    @api.model
    def _load_pos_self_data_read(self, records, config):
        fields = self._load_pos_self_data_fields(config)
        return records.read(fields, load=False) or []

    @api.model
    def _load_pos_self_data_fields(self, config):
        return self._load_pos_data_fields(config)  # defaults to base POS fields
```

Every model extended by `pos_self_order` inherits this mixin and overrides one or more of these methods to customize what is sent to the self-order frontend.

---

## Models

### `pos.config` — Extended

Inherits from `pos.config`. Adds all self-ordering configuration.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `self_ordering_mode` | Selection | `"nothing"` | `nothing`, `consultation`, `mobile`, `kiosk`. Controls which self-order mode is active. Changing to `kiosk` forces `self_ordering_pay_after = 'each'`. |
| `self_ordering_service_mode` | Selection | `"counter"` | `counter` (pickup zone) or `table` (dine-in). When `mobile` + `counter`, forces `pay_after = 'each'`. |
| `self_ordering_default_language_id` | Many2one `res.lang` | Current user lang | Default language displayed on the self-order screen. Auto-added to `available_language_ids` if missing. |
| `self_ordering_available_language_ids` | Many2many `res.lang` | All installed languages | Languages the customer can switch between on the self-order UI. |
| `self_ordering_image_home_ids` | Many2many `ir.attachment` | Splash slideshow images | Splash screen images shown as a slideshow. Auto-created as 3 URLs (`landing_01/02/03.jpg`) on first config creation. Made `public=True` by `_ensure_public_attachments`. |
| `self_ordering_image_background_ids` | Many2many `ir.attachment` | `kiosk_background.jpg` | Background image for the self-order UI. Made `public=True`. |
| `self_ordering_image_brand` | Image | — | Brand logo, max 1200x250 px. Displayed on the self-order screen header. |
| `self_ordering_image_brand_name` | Char | — | Brand name text, alternative to logo image. |
| `self_ordering_default_user_id` | Many2one `res.users` | First POS manager found | User whose ACL is used when the public self-order site is visited with no active POS session. Must belong to `point_of_sale.group_pos_user` or `group_pos_manager`. Enforced by `_check_default_user`. |
| `self_ordering_pay_after` | Selection | `"meal"` | `meal` (pay at end) or `each` (pay per order). Read-only in kiosk mode or when service mode is `counter`+`mobile`. |
| `has_paper` | Boolean | `True` | Whether the kiosk terminal has a receipt printer. |
| `status` | Selection | computed | `active`/`inactive` based on `has_active_session`. Displayed in the POS config list view. |
| `self_ordering_url` | Char | computed | Full base URL + self-order route. Used by `get_kiosk_url()`. |

> **L3 cross-model note**: `self_ordering_default_user_id` is the security boundary for all public-access operations. When a non-authenticated customer hits `/pos-self/*`, Odoo runs as this user. If unset or invalid, `UserError` is raised via `_check_default_user` constraint.

#### Key Methods

**`_get_self_order_route(table_id: int | None) -> str`**
Generates the internal route path. Logic:
- `consultation` mode: returns `/pos-self/<id>` (no token, no table)
- `mobile` + table: appends `&table_identifier=<table.identifier>` (8-char hex token)
- Always appends `?access_token=<config.access_token>`

**`_get_self_order_url(table_id) -> str`**
Wraps `_get_self_order_route` in the full base URL, then passes through `link.tracker.search_or_create()` to generate a UTM-tracked short URL. This is the URL encoded into QR codes.

**`_update_access_token()`**
```python
def _update_access_token(self):
    self.access_token = uuid.uuid4().hex[:16]   # 16-char hex token
    self.floor_ids.table_ids._update_identifier() # regenerate all table identifiers
```
Called on config `write()` (every write, not conditional) and from the "Reset QR Codes" button in settings. **Changing the access token invalidates all previously printed QR codes.**

**`_get_qr_code_data() -> list[dict]`**
Returns floor/table structure for QR code page generation:
- `mobile` + restaurant + table service: one entry per floor, with per-table `{identifier, id, name, url}`
- Otherwise: 6 generic QR code entries with no table context

**`get_pos_qr_order_data() -> dict`**
Generates a ZIP containing PNG + SVG QR code images for every table. Uses `qrcode` library (error correction level L, 10px box size). Returns `{'success', 'table_data', 'self_ordering_mode', 'db_name', 'redirect_url', 'zip_archive'}`.

**`load_self_data() -> dict`**
The primary data-loading entry point. Calls `_load_pos_self_data_search_read` on every model in `_load_self_data_models()` (36 models total). Wraps each call in `try/except AccessError` — if the current user lacks read access to a model, that model returns `[]` rather than crashing the entire load:

```python
def load_self_data(self):
    response = {}
    response['pos.config'] = self.env['pos.config']._load_pos_self_data_search_read(response, self)
    for model in self._load_self_data_models():
        try:
            response[model] = self.env[model]._load_pos_self_data_search_read(response, self)
        except AccessError:
            response[model] = []
    return response
```

**`_load_self_data_models() -> list[str]`** — complete model list:
```python
['pos.session', 'pos.preset', 'resource.calendar.attendance', 'pos.order', 'pos.order.line',
 'pos.payment', 'pos.payment.method', 'res.partner', 'res.currency', 'pos.category',
 'product.template', 'product.product', 'product.combo', 'product.combo.item', 'res.company',
 'account.tax', 'account.tax.group', 'pos.printer', 'res.country', 'product.category',
 'product.pricelist', 'product.pricelist.item', 'account.fiscal.position', 'res.lang',
 'product.attribute', 'product.attribute.custom.value', 'product.template.attribute.line',
 'product.template.attribute.value', 'product.tag', 'decimal.precision', 'uom.uom',
 'pos_self_order.custom_link', 'restaurant.floor', 'restaurant.table',
 'account.cash.rounding', 'res.country.state', 'mail.template']
```

> **L4 note**: `mail.template` is included specifically because `pos.preset` references it via `mail_template_id`. The base `pos.session._load_pos_data_models` is also extended to add `mail.template`.

**`load_data_params()` — Introspection endpoint**
Returns the schema (fields + relations) for all loaded models. Used by the frontend to know which related fields to prefetch. Calls `_load_pos_self_data_fields` and `pos.session._load_pos_data_relations` for each model.

**`action_open_wizard() / get_kiosk_url()`**
For kiosk mode: creates a new POS session if none exists, then opens the kiosk URL. In kiosk mode, `close_ui()` redirects to `action_close_kiosk_session()`.

**`action_close_kiosk_session()`**
Cancels all draft orders in the current session (`filter` + `unlink`, not just `unlink`), broadcasts `STATUS: {status: 'closed'}` via WebSocket, then calls standard session closing control:
```python
def action_close_kiosk_session(self):
    if self.current_session_id and self.current_session_id.order_ids:
        self.current_session_id.order_ids.filtered(lambda o: o.state == 'draft').unlink()
    self._notify('STATUS', {'status': 'closed'})
    return self.current_session_id.action_pos_session_closing_control()
```

**`has_valid_self_payment_method() -> bool`**
```python
if self.self_ordering_mode == 'mobile':
    return False   # mobile uses online payment, not terminal
return any(pm.use_payment_terminal in ['adyen', 'razorpay', 'stripe', 'pine_labs']
           for pm in self.payment_method_ids)
```
Kiosk requires a configured payment terminal. `mobile` orders use online payment flows (handled by `pos_online_payment_self_order`).

**`_check_default_user` constraint**
Fires when `self_ordering_mode != 'nothing'` and the default user is either unset or lacks POS group membership. Raises `UserError`.

**`_onchange_payment_method_ids` constraint**
Fires in kiosk mode when a cash payment method is added. Raises `ValidationError`. Also enforced in `res.config.settings` via `_onchange_pos_payment_method_ids`.

**`_compute_selection_pay_after()`**
Dynamic selection values: `'each'` gets a "(require Odoo Enterprise)" suffix appended when the current db is not Enterprise (checked via `service.common.exp_version()['server_version_info'][-1]`).

**`_load_pos_self_data_read()` — config enrichment**
The config's `read()` result is enriched before being sent to the frontend:
```python
record['_self_ordering_image_home_ids'] = config.self_ordering_image_home_ids.ids
record['_self_ordering_image_background_ids'] = config.self_ordering_image_background_ids.ids
record['_pos_special_products_ids'] = config._get_special_products().ids
record['_self_ordering_style'] = {
    'primaryBgColor': self.env.company.email_secondary_color,
    'primaryTextColor': self.env.company.email_primary_color,
}
record['_self_order_pos'] = True
```

**`write()` — multi-trigger pay_after forcing**
The `write()` method enforces pay_after='each' in multiple scenarios (not just on kiosk activation):
1. Kiosk mode activation
2. Mobile + counter service mode activation
3. Restaurant module not active + mobile mode
4. `pay_after='meal'` while `service_mode='counter'` and mode is `mobile`

**`_prepare_self_order_custom_btn()` — auto-creates default link**
On config `create()` and `write()`, ensures a default "Order Now" link exists:
```python
exists = self.env['pos_self_order.custom_link'].search_count([
    ('pos_config_ids', 'in', record.id),
    ('url', '=', f'/pos-self/{record.id}/products')
])
if not exists:
    self.env['pos_self_order.custom_link'].create({...})
```
The "Order Now" button is auto-created on first config activation and re-created if manually deleted.

---

### `pos.order` — Extended

Tracks self-service orders. Adds source attribution and table linkage.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `table_stand_number` | Char | Stand/pickup number assigned at order time (for counter service). |
| `self_ordering_table_id` | Many2one `restaurant.table` | Table the order was placed at. `readonly=True`. When `write()` transfers the order to a new `table_id`, this field is updated to the new table to keep the reference in sync. |
| `source` | Selection | Added values: `'mobile'` (Self-Order Mobile), `'kiosk'` (Self-Order Kiosk). |

#### Key Methods

**`sync_from_ui(orders) -> dict`**
Called when self-order app sends new/modified orders. Calls parent, extracts created order IDs, then calls `_send_notification`. Parent returns a dict of `{model: [{id, ...}, ...]}`.

**`remove_from_ui(server_ids)`**
Cancels orders removed by the customer from the self-order app. Sets `state = 'cancel'` (not `unlink`) so audit trail is preserved, then notifies the POS.

**`action_pos_order_cancel()`**
Standard cancel action. After super() call, extracts successfully cancelled orders and notifies them.

**`_send_notification(order_ids)`**
```python
def _send_notification(self, order_ids):
    config_ids = order_ids.config_id
    for config in config_ids:
        config.notify_synchronisation(config.current_session_id.id, self.env.context.get('device_identifier', 0))
        config._notify('ORDER_STATE_CHANGED', {})
```
Notifies every active POS session handling self-orders. `notify_synchronisation` is a broadcast to the specific IoT/device. `_notify` is the WebSocket broadcast to all connected POS instances.

**`_send_self_order_receipt()`**
Called on payment success. Sends the confirmation email via `action_send_self_order_receipt` using the `preset_id.mail_template_id`. Swallows `UserError` (e.g., SMTP misconfigured) with a `_logger.warning` rather than propagating — prevents self-order flow from breaking due to email failures.

**`_send_payment_result(payment_result)`**
Sends the payment result to the self-order frontend via WebSocket:
```python
self.config_id._notify('PAYMENT_STATUS', {
    'payment_result': payment_result,
    'data': {
        'pos.order': self.read(self._load_pos_self_data_fields(self.config_id), load=False),
        'pos.order.line': self.lines.read(self.lines._load_pos_self_data_fields(self.config_id), load=False),
    }
})
if payment_result == 'Success':
    self._send_order()
```
On `'Success'`, also calls `_send_order()` (which triggers cooking, receipt printing, etc. in the base POS flow).

**`_load_pos_self_data_domain()` — returns False (orders are never pre-loaded)**
```python
def _load_pos_self_data_domain(self, data, config):
    return [('id', '=', False)]
```
Orders are synced on-demand via `sync_from_ui()` and fetched via `get_orders_by_access_token()`, never pre-loaded with the config data.

---

### `pos.order.line` — Extended

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `combo_id` | Many2one `product.combo` | The combo this line belongs to. |

**`combo_parent_uuid` — Transient UUID-based resolution**

The self-order app sends `combo_parent_uuid` (the line UUID string) in vals during sync. The backend resolves it to `combo_parent_id` (the database ID) via `self.search([('uuid', '=', combo_parent_uuid)])` before calling super:

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('combo_parent_uuid'):
            vals.update([
                ('combo_parent_id', self.search([('uuid', '=', vals.get('combo_parent_uuid'))]).id)
            ])
        if 'combo_parent_uuid' in vals:
            del vals['combo_parent_uuid']  # remove transient field
    return super().create(vals_list)
```

The same pattern applies in `write()`. The UUID mechanism allows the JS frontend to reference lines that haven't been persisted yet (since the parent line is created before its child combo lines).

---

### `pos.preset` — Extended

Presets (e.g., Dine-in, Takeout, Delivery) are selectable service modes shown in the self-order UI.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `available_in_self` | Boolean | `False` | Whether this preset is selectable in self-order. |
| `service_at` | Selection | `"counter"` | `counter`, `table`, or `delivery`. Controls service mode presentation. |
| `mail_template_id` | Many2one `mail.template` | — | Email template for order confirmation. `domain="[('model', '=', 'pos.order')]"`. |

#### Data (preset_data.xml)

```xml
pos_restaurant.pos_takein_preset    → available_in_self=True,  service_at=table,     image=dine_in.jpg
pos_restaurant.pos_takeout_preset   → available_in_self=True,  service_at=counter,    mail=takeout_email_template, image=take_out.jpg
pos_restaurant.pos_delivery_preset  → available_in_self=True,  service_at=delivery,   mail=delivery_email_template, image=delivery.jpg
```

#### Domain Logic

```python
def _load_pos_self_data_domain(self, data, config):
    return ['|',
        ('id', '=', config.default_preset_id.id),       # always include default preset
        '&', ('available_in_self', '=', True),
            ('id', 'in', config.available_preset_ids.ids)  # plus all available_in_self presets
    ]
```

#### Field Extension

The `_load_pos_self_data_fields` extends the base POS fields to add `['service_at', 'mail_template_id']`. The base `_load_pos_data_fields` also adds `mail_template_id`, so it appears in both regular POS and self-order data loads.

---

### `product.template` / `product.product` — Extended

#### Fields (product.template)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `self_order_available` | Boolean | `True` | Controls visibility in self-order. Automatically set to `False` when `available_in_pos = False` via `_on_change_available_in_pos` onchange. |
| `self_order_visible` | Boolean | computed | `True` only when at least one active self-order config exists. Hides the field in the form if no self-order is configured. |

#### Domain and Data Loading (product.template)

```python
def _load_pos_self_data_domain(self, data, config):
    domain = super()._load_pos_self_data_domain(data, config)
    return Domain.AND([domain, [('self_order_available', '=', True)]])
```

Domain is AND-combined with the base POS domain (POS-type products, active, etc.).

**`_load_pos_self_data_read()` — combo items and image processing**

```python
def _load_pos_self_data_read(self, data, config):
    domain = self._load_pos_self_data_domain(data, config)
    fields = set(self._load_pos_self_data_fields(config))
    products = self.search_read(
        domain, fields,
        limit=config.get_limited_product_count(),
        order='sequence,default_code,name',
        load=False
    )

    # Also fetch combo-choice products (products used as combo_item_ids)
    combo_products = self.browse((p['id'] for p in products if p["type"] == "combo"))
    combo_products_choice = self.search_read(
        [("id", 'in', combo_products.combo_ids.combo_item_ids.product_id.product_tmpl_id.ids),
         ("id", "not in", [p['id'] for p in products])],
        fields, limit=config.get_limited_product_count(),
        order='sequence,default_code,name', load=False
    )
    products.extend(combo_products_choice)
    self._process_pos_self_ui_products(products)
    return products
```

This ensures combo items (optional choices within a combo product) are available in the self-order UI even if they are not themselves "available in POS".

**`_process_pos_self_ui_products()`**
Converts image blobs to booleans (`image_128` becomes `True`/`False` only) and backfills archived attribute combinations via `_add_archived_combinations`.

**`write()` — availability propagation**
```python
if 'self_order_available' in vals:
    for record in self:
        for product in record.product_variant_ids:
            product._send_availability_status()
```
When a template's self-order availability changes, all its variants call `_send_availability_status()`.

---

### `_send_availability_status()` — Real-time Product Updates

```python
def _send_availability_status(self):
    config_self = self.env['pos.config'].sudo().search([('self_ordering_mode', '!=', 'nothing')])
    for config in config_self:
        if config.current_session_id and config.access_token:
            records = self.env["product.template"].load_product_from_pos(
                config.id, [('id', '=', self.product_tmpl_id.id)]
            )
            payload = {model: records[model] for model in records if model in self_models}
            config._notify('PRODUCT_CHANGED', payload)
```

> **L4 performance note**: This method searches ALL active self-order configs (no company/domain filter), then for each config loads the product via `load_product_from_pos`. In a database with many POS configs and frequent availability changes, this could generate significant background load. The `config.current_session_id and config.access_token` guard prevents notifying configs without an active session. The `sudo()` call bypasses ACL for the search, then switches back to the config's regular user.

---

### `restaurant.table` — Extended

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `identifier` | Char | 8-char hex from `uuid.uuid4().hex[:8]` | Security token embedded in the QR code URL for table-linkage. Unique per table. |

#### `_update_identifier()`

```python
@api.model
def _update_identifier(self):
    tables = self.env["restaurant.table"].search([])
    for table in tables:
        table.identifier = self._get_identifier()
```

Called:
1. On module install via `data/init_access.xml` — ensures all existing tables get an identifier
2. Whenever `pos.config._update_access_token()` is called (every config write, and "Reset QR Codes" button)

> **L4 security note**: The identifier is 8 hex characters (4 bytes of entropy = 65,536 possibilities). It is not cryptographically secret but serves as an anti-csrf token — without knowing the table identifier, an attacker cannot place orders attributed to a different table. The `access_token` on the config adds another layer (16 hex chars, 8 bytes = 4.3 billion possibilities). The combination of both tokens makes URL-guessing impractical for an external attacker.

---

### `pos_self_order.custom_link`

A configurable button/link displayed on the self-order landing page (e.g., "Order Now", "Menu", "Website"). Inherits `pos.load.mixin`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required | Link label, translatable. |
| `url` | Char | required | Destination URL. |
| `pos_config_ids` | Many2many `pos.config` | empty (= all) | Restricts which POS configs show this link. Empty = show on all configs with self-order enabled. |
| `style` | Selection | `"primary"` | Bootstrap button style: `primary`, `secondary`, `success`, `warning`, `danger`, `info`, `light`, `dark`. |
| `link_html` | Html | computed | Preview of the rendered button. Computed via `_compute_link_html` from `name` + `style`. `store=True` so it is not recomputed on every read. |
| `sequence` | Integer | `1` | Display order. |

#### `_load_pos_self_data_domain()`

```python
def _load_pos_self_data_domain(self, data, config):
    return [('pos_config_ids', 'in', config.id)]
```

Only links associated with this config (or unassociated links, since empty `pos_config_ids` means "all") are sent.

#### Security

Access is granted separately from `pos.config`:
- Manager (`group_pos_manager`): CRUD
- User (`group_pos_user`): Read-only

The `pos_config_ids` domain filter in `custom_link_action()` (settings) is `['|', ('pos_config_ids', 'in', config_id), ('pos_config_ids', '=', False)]` — shows links scoped to the current config plus links scoped to "all".

---

### `res.config.settings` — Extended

All self-ordering fields are `related` fields pointing back to `pos_config_id.*`, with `readonly=False` so they are editable from the settings form.

#### Special Onchanges

**`_onchange_pos_self_order_kiosk()`** — When kiosk mode is activated:
- Sets `is_kiosk_mode = True`
- Unsets `module_pos_restaurant = False` (kiosk mode disables restaurant-specific features)
- Forces `pay_after = "each"`
- Removes all cash payment methods from the selection

**`_onchange_pos_self_order_service_mode()`** — Counter service forces pay-after-each.

**`_onchange_pos_self_order_kiosk_default_language()`** — Auto-adds the default language to available languages if not present.

**`_onchange_pos_self_order_pay_after()`** — Validates pay_after constraints:
- Kiosk mode can only use `each`
- Counter + mobile mode forces `each`

**`_compute_pos_pricelist_id()`** — In kiosk mode, all pricelists matching the journal's currency are made available (not just the limited selection). Uses `Domain.AND` with `_check_company_domain`.

#### QR Code Actions

| Method | Description |
|--------|-------------|
| `generate_qr_codes_page()` | Renders a printable QR code page via `report_self_order_qr_codes_page` (QWeb report). Uses `split_every(3, floor["tables"])` to arrange 3 per row. |
| `generate_qr_codes_zip()` | Generates a ZIP with PNG/SVG QR codes + an Excel file (`Table_url.xlsx`) mapping floors, tables, and shortened URLs. Deletes any prior attachment named `self_order_qr_code.zip`. |
| `get_pos_qr_stands()` | Client action `pos_qr_stands` that downloads a pre-generated ZIP (calls `pos.config.get_pos_qr_order_data()`). |

---

### `ir_http` — Extended

Handles language negotiation for the public-facing self-order site, overriding the website module's language resolution when the referer or path contains `/pos-self/`.

```python
def get_nearest_lang(self, lang_code):
    referer_url = request.httprequest.headers.get('Referer', '')
    path = request.httprequest.path

    if '/pos-self/' in path:
        path_with_config = path
    elif '/website/translations' in path and '/pos-self/' in referer_url:
        path_with_config = referer_url
    else:
        path_with_config = None

    if path_with_config:
        config_id_match = re.search(r'/pos-self(?:/data)?/(\d+)', path_with_config)
        if config_id_match:
            pos_config = request.env['pos.config'].sudo().browse(int(config_id_match[1]))
            if pos_config.self_ordering_available_language_ids:
                self_order_langs = pos_config.self_ordering_available_language_ids.mapped('code')
                if lang_code in self_order_langs:
                    return lang_code
                # Try short code match (en_US -> en)
                short_code = lang_code.partition('_')[0]
                matched_code = next((code for code in self_order_langs if code.startswith(short_code)), None)
                if matched_code:
                    return matched_code
    return super().get_nearest_lang(lang_code)
```

This is critical when the website module is installed — without this override, the website's default language would override the kiosk's configured languages.

---

### `pos.session` — Extended

| Field | Purpose |
|--------|---------|
| `_self_ordering` | Boolean injected into session data read: `True` if any active config in the company has `self_ordering_mode` of `kiosk` or `mobile`. Used by the POS frontend to conditionally render self-order UI components. |

```python
def _load_pos_data_read(self, records, config):
    read_records = super()._load_pos_data_read(records, config)
    if not read_records:
        return read_records
    record = read_records[0]
    record['_self_ordering'] = (
        self.env["pos.config"].sudo().search_count(
            [*self.env["pos.config"]._check_company_domain(self.env.company),
             '|', ("self_ordering_mode", "=", "kiosk"),
             ("self_ordering_mode", "=", "mobile")],
            limit=1,
        ) > 0
    )
    return read_records
```

The session also adds `'mail.template'` to the data models loaded for the POS session (in `_load_pos_data_models`).

---

### `pos.category` — Extended

`pos_config_ids` (Many2many `pos.config`): Links category visibility to specific POS configs. This allows per-config category filtering in the self-order UI.

`_can_return_content()` is overridden to allow public (unauthenticated) access to `image_128` and `image_512` for category icons.

---

### `res.partner` — Extended

`_load_pos_self_data_domain()` returns `False` — meaning **no partner data is sent to the self-order frontend at all**. Self-order orders are anonymous unless the customer explicitly provides contact details for email receipts. This is a deliberate security/design decision: prevents enumeration of the customer database via the public-facing self-order endpoint.

---

### `res.country` — Extended

Extends the base `_load_pos_self_data_fields` to include `state_ids`. Used for delivery address entry in the delivery preset flow:

```python
def _load_pos_self_data_fields(self, config):
    fields = super()._load_pos_self_data_fields(config)
    return fields + ["state_ids"]
```

---

### `mail.template` — Extended

Loaded into the POS session data only when referenced by a preset's `mail_template_id`:
```python
def _load_pos_data_domain(self, data, config):
    return [('id', 'in', [preset['mail_template_id'] for preset in data['pos.preset']])]
```
This avoids loading all mail templates — only those needed for order confirmations are sent to the frontend.

---

### `pos.payment.method` — Extended

Returns `[('id', '=', False)]` for self-order domain (no payment methods are pre-loaded). Declares the stub for `_payment_request_from_kiosk()` which is overridden by payment terminal addons (see Payment Terminal Integration section).

---

## Controllers

### `PosSelfKiosk` — Landing Page Controller (`controllers/self_entry.py`)

Serves the self-order web app.

**`/pos-self/<config_id>` (and `/pos-self/<config_id>/<subpath>`)**
- Route: `auth="public"`, `website=True`, `sitemap=True`
- Calls `_verify_entry_access()` to validate the config and access token
- Determines the `config_access_token` to pass to the frontend based on mode:
  - `mobile` + active session: returns the config's real access token
  - `kiosk`: returns the config's real access token
  - `consultation` or `mobile` without active session: returns empty string
- Renders `pos_self_order.index` template with session info and initial config data
- Also handles translation loading via `get_frontend_session_info()`

**`/pos-self/data/<config_id>` — Full data load**
- Route: `type='jsonrpc'`, `auth='public'`
- Returns `pos_config.load_self_data()` — the complete data payload for all 36 models
- The access_token returned in `pos.config[0]` is the validated `config_access_token` (empty string for consultation mode)

**`/pos-self/relations/<config_id>` — Schema introspection**
- Returns `pos_config.load_data_params()` — field lists and relations for all models

**`_verify_entry_access()` — Token resolution logic**

```python
def _verify_entry_access(self, config_id=None, access_token=None, table_identifier=None):
    # 1. Find the config (with or without token)
    if access_token:
        pos_config_sudo = request.env["pos.config"].sudo().search([
            ("id", "=", config_id), ('access_token', '=', access_token)], limit=1)
        config_access_token = True  # token was provided, mark as validated
    else:
        pos_config_sudo = request.env["pos.config"].sudo().search([
            ("id", "=", config_id)], limit=1)
        config_access_token = False  # no token provided

    # 2. Reject if mode is 'nothing' or config not found
    if not pos_config_sudo or pos_config_sudo.self_ordering_mode == 'nothing':
        raise werkzeug.exceptions.NotFound()

    # 3. Apply company/user context
    company = pos_config_sudo.company_id
    user = pos_config_sudo.self_ordering_default_user_id
    pos_config = pos_config_sudo.sudo(False).with_company(company).with_user(user)...

    # 4. For mobile mode with active session, resolve table and exchange token
    if pos_config.has_active_session and pos_config.self_ordering_mode == 'mobile':
        if config_access_token:
            config_access_token = pos_config.access_token  # exchange for real token
        table_sudo = request.env["restaurant.table"].sudo().search([
            ("identifier", "=", table_identifier), ("active", "=", True)], limit=1)
        # handle parent table delegation...
    elif pos_config.self_ordering_mode == 'kiosk':
        config_access_token = pos_config.access_token if config_access_token else ''
    else:
        config_access_token = ''  # consultation mode

    return pos_config, table, config_access_token
```

> **L4 note**: For consultation mode, `config_access_token` is returned as empty string, and the frontend receives an empty token. The route is accessible without a token because `auth="public"` + `website=True`. This allows QR codes printed for consultation mode to simply link to `/pos-self/<id>` with no query parameters.

### `PosSelfOrderController` — Order Processing API (`controllers/orders.py`)

All routes use `auth="public"`, `type="jsonrpc"`, `website=True`.

#### `/pos-self-order/process-order/<device_type>/`

The primary order creation endpoint. `device_type` is either `'kiosk'` or `'mobile'`.

```python
def process_order(self, order, access_token, table_identifier, device_type):
    pos_config, table = self._verify_authorization(access_token, table_identifier, order)

    # Strip fields that should not come from the frontend
    if 'picking_type_id' in order: del order['picking_type_id']
    if 'name' in order: del order['name']

    # Generate reference numbers with device-type prefix
    pos_reference, tracking_number = pos_config._get_next_order_refs()
    prefix = f"K{pos_config.id}-" if device_type == "kiosk" else "S"
    order['pos_reference'] = pos_reference
    order['source'] = 'kiosk' if device_type == 'kiosk' else 'mobile'
    order['tracking_number'] = f"{prefix}{tracking_number}"
    order['floating_order_name'] = ...  # table name or tracking number
    order['user_id'] = request.session.uid
    order['date_order'] = str(fields.Datetime.now())
    order['fiscal_position_id'] = preset_id.fiscal_position_id.id if preset_id else ...
    order['pricelist_id'] = preset_id.pricelist_id.id if preset_id else ...
    order['self_ordering_table_id'] = table.id if table else False

    # Sync to database
    results = pos_config.env['pos.order'].sudo().with_company(pos_config.company_id.id).sync_from_ui([order])
    order_ids = pos_config.env['pos.order'].browse([order['id'] for order in results['pos.order']])

    # Verify and compute combo prices server-side
    self._verify_line_price(line_ids, pos_config, preset_id)

    # Set state and amounts
    amount_total, amount_untaxed = self._get_order_prices(order_ids.lines)
    order_ids.write({
        'state': 'paid' if amount_total == 0 else 'draft',
        'amount_tax': amount_total - amount_untaxed,
        'amount_total': amount_total,
    })

    if amount_total == 0:
        order_ids._process_saved_order(False)  # auto-confirm free orders

    if preset_id and preset_id.mail_template_id:
        order_ids._send_self_order_receipt()

    return self._generate_return_values(order_ids, pos_config)
```

**L4 security note**: Orders from the self-order frontend bypass the normal POS access control. The `sudo().with_company()` call elevates privileges to create orders. The `access_token` and `table_identifier` are verified before any data is processed. The `user_id` is set to `request.session.uid` — if the customer is unauthenticated (public access), this is the `portal`/`public` user, not a POS employee.

**L4 failure mode — payment failure**: This endpoint creates the order in `draft` state (unless `amount_total == 0`). If payment subsequently fails (detected via the payment terminal flow calling `_send_payment_result('Failed')`), the order remains in `draft` state. The POS employee can see the order and handle it manually. There is no automatic cancellation or cleanup of draft orders created from failed payment attempts.

**L4 failure mode — session closed mid-order**: If the POS session is closed via `action_close_kiosk_session()` while a customer is in the middle of placing an order, the next `sync_from_ui()` call will succeed (the config still exists), but the order will be created in a session that is being closed. The `action_close_kiosk_session()` unlinks all draft orders at close time, which means the customer's pending order could be silently deleted.

#### `_compute_combo_price()` — Server-side Combo Price Computation

This method is a Python reimplementation of the JS `compute_combo_items.js`. It is called when an order is received from the self-order frontend to verify and correct combo pricing:

```python
def _compute_combo_price(self, parent_line, pricelist, fiscal_position):
    child_lines = parent_line.combo_line_ids
    # Separate child lines into "free" (counted toward qty_free) and "extra" (always charged)
    child_lines_by_combo = {}
    for line in child_lines:
        combo = line.combo_item_id.combo_id
        child_lines_by_combo.setdefault(combo, []).append(line)

    for combo, child_lines in child_lines_by_combo.items():
        # Proportional price distribution across "free" items
        # based on each combo item's base_price ratio to total base_price
        ...
```

> **L4 architecture note**: This is a deliberate duplication of JS logic in Python. The JS frontend computes prices client-side for UX responsiveness. The server re-computes them on order receipt to prevent tampering. The fiscal position is applied server-side only here (tax IDs are set on the line). The fiscal position from the preset overrides the config's default.

#### `/pos-self-order/validate-partner`

Creates or retrieves a `res.partner` for the customer's email receipt. Called when the customer enters their contact details.

```python
def validate_partner(self, access_token, name, phone, street, zip, city, country_id, state_id=None, partner_id=None, email=None):
    pos_config = self._verify_pos_config(access_token)
    existing_partner = pos_config.env['res.partner'].sudo().browse(int(partner_id)) if partner_id else False
    if existing_partner and existing_partner.exists():
        return {'res.partner': self.env['res.partner']._load_pos_self_data_read(existing_partner, pos_config)}
    # Creates new partner under the POS company
    partner_sudo = request.env['res.partner'].sudo().create({...})
    return {'res.partner': self.env['res.partner']._load_pos_self_data_read(partner_sudo, pos_config)}
```

#### `/pos-self-order/get-user-data` — Order State Sync

Called by the frontend to check if the customer's existing orders have changed:

```python
def get_orders_by_access_token(self, access_token, order_access_tokens, table_identifier=None):
    pos_config = self._verify_pos_config(access_token)
    table = pos_config.env["restaurant.table"].search([('identifier', '=', table_identifier)], limit=1)

    # Build domain based on table and token
    if not table_identifier or pos_config.self_ordering_pay_after == 'each':
        domain = [(False, '=', True)]  # pay-after-each: don't filter by table
    else:
        # Only orders at this table, not owned by this customer
        domain = ['&', '&', ('table_id', '=', table.id), ('state', '=', 'draft'),
                  ('access_token', 'not in', [data.get('access_token') for data in order_access_tokens])]

    # Add clauses for each of the customer's order access tokens
    for data in order_access_tokens:
        domain = Domain.OR([domain, ['&',
            ('access_token', '=', data['access_token']),
            '|', ('write_date', '>', data.get('write_date')),
               ('state', '!=', data.get('state')),
        ]])

    orders = pos_config.env['pos.order'].search(domain)
    return self._generate_return_values(orders, pos_config)
```

#### `/kiosk/payment/<int:pos_config_id>/<device_type>` — Kiosk Terminal Payment

Triggers the payment terminal's `_payment_request_from_kiosk()` method. The terminal-specific addon (stripe, adyen, etc.) provides this implementation.

#### `/pos-self-order/remove-order` — Customer Order Cancellation

```python
def remove_order(self, access_token, order_id, order_access_token):
    pos_config = self._verify_pos_config(access_token)
    pos_order = pos_config.env['pos.order'].browse(order_id)
    if not pos_order.exists() or not consteq(pos_order.access_token, order_access_token):
        raise MissingError("Your order does not exist or has been removed")
    if pos_order.state != 'draft':
        raise Unauthorized("You are not authorized to remove this order")
    pos_order.remove_from_ui([pos_order.id])
```

> **L4 failure mode — token mismatch**: `consteq()` is used for token comparison (constant-time comparison) to prevent timing attacks. An attacker who knows a valid `order_id` cannot brute-force the `order_access_token` via timing side-channels.

#### `/pos-self/ping` — Session Keepalive

```python
def pos_ping(self, access_token):
    self._verify_pos_config(access_token, check_active_session=False)
    return {'response': 'pong'}
```

Used by the frontend as a keepalive/health check. Note `check_active_session=False` — this endpoint works even when the POS session is closed (unlike most other endpoints).

#### `_verify_pos_config()` — Privileged Context Setup

```python
def _verify_pos_config(self, access_token, check_active_session=True):
    pos_config_sudo = request.env['pos.config'].sudo().search([
        ('access_token', '=', access_token)], limit=1)
    if self._verify_config_constraint(pos_config_sudo, check_active_session):
        raise Unauthorized("Invalid access token")
    company = pos_config_sudo.company_id
    user = pos_config_sudo.self_ordering_default_user_id
    return pos_config_sudo.sudo(False).with_company(company).with_user(user).with_context(
        allowed_company_ids=company.ids)
```

The returned record has:
- No `sudo()` — respects normal record rules for the default user
- `with_company(company)` — enforces single-company context
- `with_user(user)` — runs as the configured default user
- `allowed_company_ids=company.ids` — restricts multi-company visibility

---

## Security Considerations

### Access Token System

The self-order URL format is:
```
/pos-self/<config_id>?access_token=<config.access_token>&table_identifier=<table.identifier>
```

Both tokens are short hex strings. For kiosk mode with an active POS session, the access token is validated server-side against the session. For mobile/consultation modes, the access token prevents unauthorized access but provides no cryptographic protection — the URL should only be distributed to legitimate customers (e.g., via QR codes placed at tables).

**Token entropy analysis (L4)**:
- `config.access_token`: 16 hex chars = 16^16 = 3.4 x 10^19 possibilities (65 bits)
- `table.identifier`: 8 hex chars = 16^8 = 4.3 x 10^9 possibilities (32 bits)
- Combined (for mobile + table): 16^24 = 7.9 x 10^28 (97 bits)

Brute-force protection is adequate for URL-guessing but the tokens are not intended as secret credentials — anyone with the QR code URL can place orders attributed to that table.

### Partner Data Isolation

`res.partner` returns `False` domain for self-order data loading — customers cannot be enumerated. However, when a customer places an order and provides their email for a receipt, that email address is stored on the `pos.order` record. The `validate_partner` endpoint creates new partner records on-demand under the POS company.

### Default User ACL

The `self_ordering_default_user_id` defines the effective permissions for all self-order operations. It must be a POS user. Misconfiguration (no user set, or wrong permissions) blocks activation of self-order via `_check_default_user`.

**L4 security risk**: If the default user has elevated permissions (e.g., `group_pos_manager`), all self-order operations run with those elevated permissions. An attacker who compromises the self-order URL could potentially exploit manager-level ACLs. Best practice: use a dedicated low-privilege user for self-order operations.

### Cash Payment Restriction

Kiosk mode explicitly prohibits cash payment methods at the constraint level (`_onchange_payment_method_ids` and `_onchange_pos_payment_method_ids`). This is enforced in both `pos.config` and `res.config.settings`. This prevents a cash drawer exploit in an unattended kiosk environment.

### Image Access

`ir.attachment` records for self-order images are made `public=True` by `_ensure_public_attachments()` so they can be served to unauthenticated customers visiting the self-order site.

---

## Workflow Summary

### Mobile Order Flow

```
Customer scans QR code → /pos-self/<id>?access_token=<token>&table_identifier=<table.id>
    ↓
/pos-self/<config_id> renders index.html (landing page)
    ↓
/pos-self/data/<config_id> loads load_self_data() → all data fetched once (products, categories, combos, etc.)
    ↓
Customer selects preset (Dine-in/Takeout/Delivery)
    ↓
Customer builds order (adds products, attributes, combos)
    ↓
Customer enters contact info (email for receipt)
    ↓
POST /pos-self-order/process-order/mobile → creates pos.order in draft state
    ↓
If amount > 0: redirect to online payment (pos_online_payment_self_order)
   If amount = 0: auto-process (order state='paid', _process_saved_order called)
    ↓
Payment confirmed → _send_payment_result('Success') → _notify('PAYMENT_STATUS') to frontend
    ↓
Order forwarded to kitchen display / bar via POS sync
    ↓
Receipt emailed via _send_self_order_receipt() (if email provided and preset has mail_template_id)
```

### Kiosk Mode Session Lifecycle

```
Manager opens POS session → action_open_wizard() → creates session if needed
    ↓
/pos-self/<config_id> loads self-order app (kiosk browser)
    ↓
Customer places order(s) → POST /kiosk/payment/<device_type> → triggers terminal payment
    ↓
_on_kiosk_payment_done → _send_payment_result('Success') → _notify('PAYMENT_STATUS')
    ↓
Manager closes session → close_ui() → action_close_kiosk_session()
    ↓
All draft orders cancelled, STATUS:closed broadcasted, standard session close proceeds
```

### Online Payment Flow (Mobile, via `pos_online_payment_self_order`)

```
Mobile order created in draft state → payment URL generated → customer redirected to payment page
    ↓
Payment processed by online payment provider (e.g., Stripe)
    ↓
Webhook/payment confirmation → _send_payment_result('Success') on the order
    ↓
Order moves to next state (paid or invoiced depending on configuration)
```

---

## Email Templates

Two email templates are installed (noupdate, so they can be customized):

**`takeout_email_template`** — Used by `pos_takeout_preset`
- Subject: `Your {{ config_id.name }} receipt`
- Body: greeting, `tracking_number`, `format_amount(amount_total, currency)`, optional `preset_time`
- If `state == 'paid'`: receipt PDF attached

**`delivery_email_template`** — Used by `pos_delivery_preset`
- Same as takeout, plus delivery address (`street`, `state`, `city`, `zip`, `country_id`) displayed in the confirmation body

Both templates use `auto_delete=False` so the email content is preserved for debugging.

---

## Payment Terminal Integration

`pos.payment.method._payment_request_from_kiosk()` is stub-declared in `pos_payment_method.py`:
```python
def _payment_request_from_kiosk(self, order):
    pass  # will be overridden
```

Overridden by the payment terminal addons:
- `pos_self_order_stripe` → Stripe terminal
- `pos_self_order_adyen` → Adyen terminal
- `pos_self_order_razorpay` → Razorpay terminal
- `pos_self_order_pine_labs` → Pine Labs terminal
- `pos_self_order_qfpay` → QFPay

Each addon provides the concrete `_payment_request_from_kiosk` implementation for its terminal. Kiosk mode checks `has_valid_self_payment_method()` to ensure at least one terminal is configured.

---

## Odoo 18 to 19 Changes

| Feature | Odoo 18 | Odoo 19 |
|---------|---------|---------|
| Self-order modes | `nothing` / `mobile` / `kiosk` | `nothing` / `consultation` / `mobile` / `kiosk` |
| `consultation` mode | Not available | QR code menu without ordering (read-only) |
| `pos_self_order.custom_link` | Not available | New model for customizable landing page buttons |
| `restaurant.table.identifier` | Not available | 8-char hex security token for table identification |
| `self_order_available` on `product.template` | Not available | Product-level self-order visibility control |
| `product.combo` support in self-order | Partial | Full support via `combo_id` and `combo_parent_uuid` |
| `pos.preset` integration | Basic | `available_in_self`, `service_at`, `mail_template_id` |
| Pricelist in kiosk | Limited selection | All pricelists matching journal currency |
| `load_data_params()` introspection | Not available | Frontend schema introspection for offline support |
| `pos.session._self_ordering` | Not available | Boolean flag injected into session data |
| Payment terminal modules | `pos_self_order_stripe`, `pos_self_order_adyen` | + `pos_self_order_razorpay`, `pos_self_order_pine_labs`, `pos_self_order_qfpay` |
| `remove_order` endpoint | Basic | Added `consteq` for constant-time token comparison (timing attack prevention) |
| `generate_qr_codes_zip()` | Basic | Now includes Excel mapping file |

---

## Performance Considerations

### Data Loading Architecture

The self-order app loads data in two phases:
1. **Initial load** (`/pos-self/data/<config_id>`): `load_self_data()` fetches all 36 models in one request. Each model's `_load_pos_self_data_search_read()` runs a separate `search()` + `read()`. With 36 models, this can result in 36+ database queries on first load.
2. **Incremental sync** (`get_orders_by_access_token`): Only fetches orders that have changed since the last sync, using `write_date` comparison.

### Product Data Loading

`product.template._load_pos_self_data_read()` performs two `search_read()` calls:
1. Main products up to `config.get_limited_product_count()` limit
2. Combo-choice products (products used as `combo_item_ids` but not already in main set)

This can result in 2 queries per product template load, plus additional queries for archived attribute combinations (`_add_archived_combinations`).

### Real-time Updates via WebSocket

`_send_availability_status()` broadcasts `PRODUCT_CHANGED` events to all active kiosk sessions when a product's availability changes. The `_notify()` method uses the Odoo bus (longpolling) to push updates to the frontend without polling.

### `_send_notification()` Double Broadcast

```python
def _send_notification(self, order_ids):
    for config in config_ids:
        config.notify_synchronisation(config.current_session_id.id, device_identifier)
        config._notify('ORDER_STATE_CHANGED', {})
```

This calls both `notify_synchronisation()` (IoT/specific device broadcast) and `_notify()` (WebSocket to all POS instances). For IoT Box configurations, this means two separate push mechanisms are triggered for every order state change.

---

## Related Modules

- [[Modules/pos_restaurant]] — Base restaurant module (dependency; provides `restaurant.table`, `restaurant.floor`, `pos.preset`)
- [[Modules/pos_self_order_sale]] — Links self-order orders to SaleSubscriptions
- [[Modules/pos_self_order_stripe]] — Stripe terminal payment for kiosk
- [[Modules/pos_self_order_adyen]] — Adyen terminal payment for kiosk
- [[Modules/pos_self_order_razorpay]] — Razorpay terminal payment for kiosk
- [[Modules/pos_self_order_pine_labs]] — Pine Labs terminal payment for kiosk
- [[Modules/pos_self_order_qfpay]] — QFPay payment for kiosk
- [[Modules/pos_online_payment_self_order]] — Online card payment flow for mobile self-order (distinct from terminal payments)
