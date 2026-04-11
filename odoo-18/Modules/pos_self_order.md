---
Module: pos_self_order
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_self_order #self_order #kiosk #qr_menu
---

## Overview

Self-ordering system for restaurants and retail: QR-code menu browsing, kiosk mode ordering, and mobile table-ordering. Adds `pos_self_order.custom_link`, extends `pos.config`, `pos.session`, `pos.order`, `pos.order.line`, `pos.category`, `product.product`, `product.template`, `restaurant.floor`, `restaurant.table`, `account.fiscal.position`, `ir.http`.

**Depends:** `pos_restaurant`, `website` (for translations)

**Key Feature:** "Consultation" (QR menu only), "mobile" (QR menu + ordering), "kiosk" (standalone terminal) self-order modes.

---

## Models

### `pos.config` (Extension)
**Inheritance:** `pos.config`

| Field | Type | Notes |
|---|---|---|
| `self_ordering_url` | Char (compute) | Full URL to self-order page |
| `self_ordering_takeaway` | Boolean | Enable self-takeaway |
| `self_ordering_mode` | Selection | `nothing` (disable), `consultation` (QR menu), `mobile` (QR+ordering), `kiosk` |
| `self_ordering_service_mode` | Selection | `counter` (pickup zone), `table` (table service) |
| `self_ordering_default_language_id` | Many2one `res.lang` | Default kiosk language |
| `self_ordering_available_language_ids` | Many2many `res.lang` | Available languages |
| `self_ordering_image_home_ids` | Many2many `ir.attachment` | Splash screen images |
| `self_ordering_default_user_id` | Many2one `res.users` | User context for self-order session |
| `self_ordering_pay_after` | Selection | `meal` (pay at end), `each` (pay per order). Each requires Enterprise. |
| `self_ordering_image_brand` | Image | Brand logo, max 1200x250 |
| `self_ordering_image_brand_name` | Char | Brand name text |
| `has_paper` | Boolean | Default True |

**Computed:** `status` -> `'active'` if `has_active_session` else `'inactive'`

**Methods:**
- `_self_order_kiosk_default_languages()` -> returns installed languages as default for `self_ordering_available_language_ids`
- `_self_order_default_user()` -> searches for first user with `group_pos_manager`
- `_update_access_token()` -> regenerates `access_token` (16 hex chars) and calls `_update_identifier()` on all tables
- `create(vals_list)` -> calls `_prepare_self_order_splash_screen` and `_prepare_self_order_custom_btn`
- `_prepare_self_order_splash_screen(vals_list)` -> auto-attaches landing images 01/02/03 if not provided
- `_prepare_self_order_custom_btn()` -> creates "Order Now" custom link if not exists
- `write(vals)` -> validates kiosk constraints (no cash in kiosk), auto-sets `self_ordering_pay_after='each'` for kiosk/mobile-counter modes
- `_compute_selection_pay_after()` -> adds "(require Odoo Enterprise)" label to "Each" option if `server_version_info[-1] == ''`
- `_check_default_user()` -> validates default user has POS group
- `_onchange_payment_method_ids()` -> raises ValidationError if cash payment in kiosk mode
- `_get_qr_code_data()` -> builds floor/table structure for QR code generation (table mode) or generic list (default mode)
- `_get_self_order_route(table_id)` -> builds route: `/pos-self/{id}` + `?access_token=...` + `&table_identifier=...` (if table and mobile+table mode)
- `_get_self_order_url(table_id)` -> URL-encoded version of `_get_self_order_route`
- `preview_self_order_app()` -> opens `_get_self_order_route` in new tab
- `_get_self_ordering_attachment(images)` -> base64-decodes attachment data for frontend
- `_load_self_data_models()` -> list of all models loaded for self-order page (includes custom_link, restaurant.floor, restaurant.table)
- `load_self_data()` -> orchestrates loading all self-order data, wraps in AccessError handling per model
- `_split_qr_codes_list(floors, cols)` -> groups floors into rows of `cols` tables for PDF layout
- `_compute_self_ordering_url()` -> sets `self_ordering_url`
- `action_close_kiosk_session()` -> unlinks non-paid/invoiced orders, sends 'closed' status notification, calls closing control
- `_compute_status()` -> sets status from `has_active_session`
- `action_open_wizard()` -> creates session if needed, triggers `install_kiosk_pwa` client action
- `get_kiosk_url()` -> returns `self_ordering_url`
- `load_onboarding_kiosk_scenario()` -> creates demo kiosk POS config
- `__generate_single_qr_code(url)` -> generates QR code image
- `get_pos_qr_order_data()` -> generates ZIP of QR code PNGs for mobile/consultation modes

---

### `pos.session` (Extension)
**Inheritance:** `pos.session`

**Methods:**
- `create(vals_list)` -> calls `_create_pos_self_sessions_sequence`
- `_create_pos_self_sessions_sequence(sessions)` -> creates `ir.sequence` per session: `code='pos.order_{session.id}'`, `padding=4`, `number_next=1`
- `@api.autovacuum _gc_session_sequences()` -> unlinks sequences for closed sessions to prevent bloat
- `_load_pos_self_data_domain(data)` -> `config_id=id AND state='opened'`
- `_load_pos_self_data(data)` -> adds `_base_url` to session data
- `_load_pos_data(data)` -> adds `_self_ordering` flag (True if any config in company has kiosk/mobile mode)

---

### `pos.order` (Extension)
**Inheritance:** `pos.order`

| Field | Type | Notes |
|---|---|---|
| `table_stand_number` | Char | Table stand number for self-order |

**Methods:**
- `_load_pos_self_data_domain(data)` -> returns `[('id', '=', False)]` (no pre-existing orders)
- `sync_from_ui(orders)` -> preserves `takeaway` from existing orders when re-syncing; sends notification via `_send_notification`
- `remove_from_ui(server_ids)` -> sets state to `cancel`, sends notification
- `_send_notification(order_ids)` -> calls `config.notify_synchronisation` + `config._notify('ORDER_STATE_CHANGED', {})`

---

### `pos.order.line` (Extension)
**Inheritance:** `pos.order.line`

| Field | Type | Notes |
|---|---|---|
| `combo_id` | Many2one `product.combo` | Combo reference |

**Methods:**
- `create(vals_list)` -> maps `combo_parent_uuid` -> `combo_parent_id` via uuid search before calling super
- `write(vals)` -> same uuid->id mapping for `combo_parent_uuid`

---

### `pos.category` (Extension)
**Inheritance:** `pos.category`

| Field | Type | Notes |
|---|---|---|
| `hour_until` | Float | Availability until hour (0-24), default 24.0 |
| `hour_after` | Float | Availability after hour (0-24), default 0.0 |

**Methods:**
- `_load_pos_data_fields(config_id)` -> adds `hour_until`, `hour_after`
- `_check_hour()` -> `@api.constrains`: validates 0<=hour<=24, and `hour_until > hour_after`

---

### `product.template` (Extension)
**Inheritance:** `product.template`

| Field | Type | Notes |
|---|---|---|
| `self_order_available` | Boolean | Available in self order screens, default True |

**Methods:**
- `_on_change_available_in_pos()` -> `@api.onchange('available_in_pos')`: sets `self_order_available=False` when unavailable_in_pos
- `write(vals_list)` -> if `available_in_pos=False`, sets `self_order_available=False`; if `self_order_available` changed, calls `_send_availability_status()` on variants

---

### `product.product` (Extension)
**Inheritance:** `product.product`

**Methods:**
- `_load_pos_data_fields(config_id)` -> adds `self_order_available`
- `_load_pos_self_data_fields(config_id)` -> adds `public_description`, `list_price`
- `_load_pos_self_data_domain(data)` -> adds `self_order_available=True` filter via AND
- `_load_pos_self_data(data)` -> loads products with formula tax fields, archived combinations, and price computation via pricelist. Adds `_product_default_values` to config data.
- `_compute_product_price_with_pricelist(products, config_id)` -> applies `pricelist_id._get_product_price` per product; handles archived combinations
- `_filter_applicable_attributes(attributes_by_ptal_id)` -> filters attributes by `attribute_line_ids`
- `write(vals_list)` -> calls `_send_availability_status` on each record when `self_order_available` changes
- `_send_availability_status()` -> broadcasts `PRODUCT_CHANGED` notification to all open self-order configs (sudos to find `self_ordering_mode != 'nothing'` configs)

---

### `restaurant.floor` (Extension)
**Inheritance:** `restaurant.floor`

**Methods:**
- `_load_pos_self_data_fields(config_id)` -> `['name', 'table_ids']`
- `_load_pos_self_data_domain(data)` -> `id in floor_ids` (only floors assigned to this config)

---

### `restaurant.table` (Extension)
**Inheritance:** `restaurant.table`

| Field | Type | Notes |
|---|---|---|
| `identifier` | Char | Security token, copy=False, required, default=`uuid.hex[:8]` |

**Methods:**
- `_get_identifier()` -> `uuid.uuid4().hex[:8]`
- `_update_identifier()` -> refreshes identifier on all tables (called when access token changes)
- `_load_pos_self_data_fields(config_id)` -> `['table_number', 'identifier', 'floor_id']`
- `_load_pos_self_data_domain(data)` -> `floor_id in [floor_ids]`

---

### `account.fiscal.position` (Extension)
**Inheritance:** `account.fiscal.position`

**Methods:**
- `_load_pos_self_data(data)` -> delegates to `_load_pos_data(data)` (same domain as normal POS)

---

### `pos.payment.method` (Extension)
**Inheritance:** `pos.payment.method`

**Methods:**
- `_payment_request_from_kiosk(order)` -> base no-op stub (overridden by payment terminal extensions)
- `_load_pos_self_data_domain(data)` -> if kiosk mode: `[('use_payment_terminal', 'in', ['adyen', 'stripe']), ('id', 'in', payment_method_ids)]` else `[('id', '=', False)]`

---

### `pos_self_order.custom_link` (New Model)
**Inheritance:** `pos.load.mixin`

Custom links displayed on self-order screens.

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Label, required, translate=True |
| `url` | Char | URL, required |
| `pos_config_ids` | Many2many `pos.config` | Domain: `self_ordering_mode != 'nothing'` |
| `style` | Selection | `primary/secondary/success/warning/danger/info/light/dark`, default `primary` |
| `link_html` | Html (compute+store) | Preview button HTML |
| `sequence` | Integer | Default 1 |

**Methods:**
- `_load_pos_self_data_domain(data)` -> `pos_config_ids` includes current config
- `_load_pos_self_data_fields(config_id)` -> `['name', 'url', 'style', 'link_html', 'sequence']`
- `_compute_link_html()` -> `@api.depends('name', 'style')`: generates `<a class="btn btn-{style} w-100">{name}</a>`

---

### `ir.http` (Extension)
**Inheritance:** `ir.http`

**Methods:**
- `_get_translation_frontend_modules_name()` -> adds `'pos_self_order'` for translation loading
- `get_nearest_lang(lang_code)` -> intercepts `/pos-self/` paths to return nearest language from `self_ordering_available_language_ids` instead of website defaults

---

### `ir.binary` (Extension)
**Inheritance:** `ir.binary`

**Methods:**
- `_find_record_check_access(record, access_token, field)` -> for `product.product` and `pos.category` with `image_128`/`image_512`, returns `record.sudo()` (allows anonymous product image access in self-order)

---

### `pos.load.mixin` (Extension)
**Inheritance:** `pos.load.mixin`

**Methods:**
- `_load_pos_self_data_domain(data)` -> delegates to `_load_pos_data_domain(data)`
- `_load_pos_self_data_fields(config_id)` -> delegates to `_load_pos_data_fields(config_id)`
- `_load_pos_self_data(data)` -> generic implementation: `search_read(domain, fields, load=False)`

---

### `res.config.settings` (Extension)
**Inheritance:** `res.config.settings`

All fields are related to `pos_config_id` counterparts:
- `pos_self_ordering_takeaway`, `pos_self_ordering_service_mode`, `pos_self_ordering_mode`, `pos_self_ordering_default_language_id`, `pos_self_ordering_available_language_ids`, `pos_self_ordering_image_home_ids`, `pos_self_ordering_image_brand`, `pos_self_ordering_image_brand_name`, `pos_self_ordering_pay_after`, `pos_self_ordering_default_user_id`

**Methods:**
- `_onchange_default_user()` -> validates POS user group for mobile mode
- `_onchange_pos_self_order_service_mode()` -> forces `pay_after='each'` when service_mode='counter'
- `_onchange_pos_self_order_kiosk_default_language()` -> ensures default is in available list
- `_onchange_pos_self_order_kiosk()` -> for kiosk: sets `module_pos_restaurant=False`, `pay_after='each'`, removes cash payment methods
- `_onchange_pos_payment_method_ids()` -> blocks cash methods in kiosk
- `_onchange_pos_self_order_pay_after()` -> blocks 'meal' in kiosk; enables `module_pos_preparation_display` when needed
- `custom_link_action()` -> opens `pos_self_order.custom_link` list view filtered to current config
- `generate_qr_codes_zip()` -> generates and downloads ZIP of QR PNGs
- `generate_qr_codes_page()` -> renders QR codes page report
- `preview_self_order_app()` -> delegates to `pos_config_id.preview_self_order_app()`
- `update_access_tokens()` -> calls `pos_config_id._update_access_token()`
- `_compute_pos_pricelist_id()` -> for kiosk mode, uses company currency for available pricelists (no foreign currency restriction)

---

## Security / Data

**ir.model.access.csv:**
```
access_pos_self_order_custom_link_manager, model_pos_self_order_custom_link, group_pos_manager, 1,1,1,1
access_pos_self_order_custom_link_user, model_pos_self_order_custom_link, group_pos_user, 1,0,0,0
```

**Data files:**
- `data/init_access.xml` (noupdate): calls `_update_identifier` on all restaurant.table records on module install
- `data/kiosk_demo_data.xml` (noupdate): calls `pos.config.load_onboarding_kiosk_scenario`

---

## Critical Notes

1. **`access_token` security:** The `access_token` (16 hex chars) is regenerated on config write and embedded in every self-order URL. Combined with per-table `identifier` tokens, this provides isolation between tables and sessions.

2. **Sequence per session:** `ir.sequence` created per session with `code='pos.order_{session.id}'` ensures self-order order numbering is isolated per session. Garbage-collected by `@api.autovacuum _gc_session_sequences`.

3. **Kiosk vs mobile payment:** In kiosk mode, only Adyen/Stripe payment terminals are loaded (via `_load_pos_self_data_domain`). In mobile/consultation modes, no terminal is loaded — payment is handled via online payment or cash.

4. **`formula_decoded_info` tax support:** `_load_pos_self_data` on `product.product` adds custom fields for 'formula' tax computation, enabling dynamic tax calculation on the frontend without server round-trips.

5. **`module_pos_restaurant` dependency:** Even in non-restaurant (retail) self-order, the module depends on `pos_restaurant` for the `restaurant.floor`/`restaurant.table` models. When used in retail, no floors/tables are created.

6. **`pos_self_order_epson_printer` auto_install:** This meta-module (`pos_self_order_epson_printer`) auto-installs when both `pos_epson_printer` and `pos_self_order` are present, adding Epson printer support to the kiosk frontend.