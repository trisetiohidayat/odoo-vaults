---
Module: pos_restaurant
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_restaurant #restaurant #pos
---

## Overview

Core restaurant POS module. Extends `pos.config` with floor/table management, bill splitting, and takeaway support. Introduces `restaurant.floor` and `restaurant.table` models loaded via `pos.load.mixin`. Depends on `point_of_sale`.

**Key Feature:** Restaurant-specific order fields (table, customer count, takeaway) and floor/table visual layout management.

**Depends:** `point_of_sale`

---

## Models

### `restaurant.floor` (Standalone Model)
**Inheritance:** `pos.load.mixin`

Restaurant floor/room for table placement.

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required |
| `pos_config_ids` | Many2many `pos.config` | Domain: `module_pos_restaurant = True` |
| `background_image` | Binary | Legacy field |
| `background_color` | Char | HTML color, default `rgb(249,250,251)` |
| `table_ids` | One2many `restaurant.table` | Reverse of `floor_id` |
| `sequence` | Integer | Default 1 |
| `active` | Boolean | Default True |
| `floor_background_image` | Image | New in Odoo 18 |

**Methods:**
- `_load_pos_data_domain(data)` -> filters by current POS config
- `_load_pos_data_fields(config_id)` -> `['name', 'background_color', 'table_ids', 'sequence', 'pos_config_ids', 'floor_background_image']`
- `_unlink_except_active_pos_session()` -> `@api.ondelete(at_uninstall=False)`: prevents deletion if floor used in open session
- `write(vals)` -> prevents write if POS session open on any linked config
- `rename_floor(new_name)` -> rename a floor by name
- `sync_from_ui(name, background_color, config_id)` -> `Command.link` config, returns floor dict with id, name, color, tables
- `deactivate_floor(session_id)` -> soft delete: sets all tables + floor `active=False`, raises if draft orders exist

---

### `restaurant.table` (Standalone Model)
**Inheritance:** `pos.load.mixin`

Restaurant table on a floor plan.

| Field | Type | Notes |
|---|---|---|
| `floor_id` | Many2one `restaurant.floor` | Required |
| `table_number` | Integer | Required, default 0 |
| `shape` | Selection `[('square','Square'),('round','Round')]` | Required, default `square` |
| `position_h` | Float | Horizontal px position, default 10 |
| `position_v` | Float | Vertical px position, default 10 |
| `width` | Float | Table width in px, default 50 |
| `height` | Float | Table height in px, default 50 |
| `seats` | Integer | Default 1 |
| `color` | Char | CSS `background` property value, default `#35D374` |
| `parent_id` | Many2one `restaurant.table` | For grouped tables |
| `active` | Boolean | Default True |

**Computed:** `display_name` -> `"floor.name, table_number"` via `_compute_display_name`

**Methods:**
- `_load_pos_data_domain(data)` -> `active=True` + `floor_id in [floor_ids]`
- `_load_pos_data_fields(config_id)` -> full list of all table fields
- `are_orders_still_in_draft()` -> raises UserError if draft orders exist for table
- `_unlink_except_active_pos_session()` -> `@api.ondelete(at_uninstall=False)`: prevents removal if table used in open POS session

---

### `pos.config` (Extension)
**Inheritance:** `pos.config`

| Field | Type | Notes |
|---|---|---|
| `iface_splitbill` | Boolean | Enables bill splitting |
| `iface_printbill` | Boolean | Allows printing bill before payment |
| `floor_ids` | Many2many `restaurant.floor` | Copy=False |
| `set_tip_after_payment` | Boolean | Tip capture after customer leaves or end of day |
| `module_pos_restaurant_appointment` | Boolean | Table booking feature |
| `takeaway` | Boolean | Allow takeaway orders |
| `takeaway_fp_id` | Many2one `account.fiscal.position` | Alternative fiscal position for takeaway tax rates |

**Methods:**
- `_get_forbidden_change_fields()` -> adds `'floor_ids'` to parent list
- `create(vals_list)` -> auto-enables `iface_splitbill=True` for restaurant configs; auto-creates default floor/table if none exist
- `write(vals)` -> clears `floor_ids` when `module_pos_restaurant=False`; resets `set_tip_after_payment` when restaurant/tip disabled; auto-creates default floor when enabled
- `_setup_default_floor(config)` -> creates Main Floor with one table (num 1, 1 seat, 130x130px at position 100,100)
- `_load_bar_data()` -> loads `scenarios/bar_data.xml`
- `_load_restaurant_data()` -> loads `scenarios/restaurant_data.xml`
- `load_onboarding_bar_scenario()` -> creates "Bar" POS config with default bar categories
- `load_onboarding_restaurant_scenario()` -> creates "Restaurant" POS config; loads demo floor data; on main company creates closed sessions with demo orders

---

### `pos.order` (Extension)
**Inheritance:** `pos.order`

| Field | Type | Notes |
|---|---|---|
| `table_id` | Many2one `restaurant.table` | `index='btree_not_null'`, readonly |
| `customer_count` | Integer | Number of guests served, readonly |
| `takeaway` | Boolean | Default False |

**Methods:**
- `_get_open_order(order)` -> restaurant version: for draft orders with table, searches by uuid OR table+draft state
- `remove_from_ui(server_ids)` -> calls `send_table_count_notification(tables)` after parent unlink
- `sync_from_ui(orders)` -> calls parent then adds back other draft orders for the same tables (table_ids context)
- `send_table_count_notification(table_ids)` -> no-op (kept for stable compatibility)
- `action_pos_order_cancel()` -> calls parent then `send_table_count_notification` if table exists

---

### `pos.session` (Extension)
**Inheritance:** `pos.session`

**Methods:**
- `_load_pos_data_models(config_id)` -> adds `'restaurant.floor'`, `'restaurant.table'` to parent list when `module_pos_restaurant=True`
- `_set_last_order_preparation_change(order_ids)` -> writes `last_order_preparation_change` JSON blob per order: keys are `uuid + " - "` with product data, qty, attribute_value_ids

---

### `pos.payment` (Extension)
**Inheritance:** `pos.payment`

**Methods:**
- `_update_payment_line_for_tip(tip_amount)` -> adds `tip_amount` to `amount` field (for simple capture; Adyen/Stripe extensions override for terminal reauthorization)

---

### `account.fiscal.position` (Extension)
**Inheritance:** `account.fiscal.position`

**Methods:**
- `_load_pos_data_domain(data)` -> OR-concatenates parent domain with `takeaway_fp_id` inclusion

---

### `res.config.settings` (Extension)
**Inheritance:** `res.config.settings`

| Field | Type | Notes |
|---|---|---|
| `pos_floor_ids` | Many2many related to `pos_config_id.floor_ids` | readonly=False |
| `pos_iface_printbill` | Boolean compute+store | Depends on `pos_module_pos_restaurant` |
| `pos_iface_splitbill` | Boolean compute+store | Depends on `pos_module_pos_restaurant` |
| `pos_set_tip_after_payment` | Boolean compute+store | Depends on `pos_iface_tipproduct` and `pos_config_id` |
| `pos_module_pos_restaurant_appointment` | Boolean related |
| `pos_takeaway` | Boolean related |
| `pos_takeaway_fp_id` | Many2one related |

---

## Security / Data

**ir.model.access.csv:**
```
access_restaurant_floor,restaurant.floor.user,model_restaurant_floor,group_pos_user,1,0,0,0
access_restaurant_floor_manager,restaurant.floor.manager,model_restaurant_floor,group_pos_manager,1,1,1,1
access_restaurant_table,restaurant.table.user,model_restaurant_table,group_pos_user,1,0,0,0
access_restaurant_table_manager,restaurant.table.manager,model_restaurant_table,group_pos_manager,1,1,1,1
```

**Data files:**
- `data/restaurant_session_floor.xml` (noupdate=1): Demo restaurant with Main Floor (12 tables) + Patio (12 tables), demo closed sessions, demo orders, demo open session with draft orders
- `data/scenarios/restaurant_session_floor.xml`: Demo data for restaurant onboarding scenario

---

## Critical Notes

1. **pos.load.mixin inheritance:** Both `restaurant.floor` and `restaurant.table` inherit `pos.load.mixin` (via `_inherit = ['pos.load.mixin']`). This provides the `_load_pos_data_domain` and `_load_pos_data_fields` methods used during POS session data loading.

2. **Floor deletion protection:** `_unlink_except_active_pos_session` uses `@api.ondelete(at_uninstall=False)` — this only runs during normal ORM delete, NOT via `_unlink` triggered from `unlink()` cascade or raw SQL.

3. **Takeaway fiscal position:** `takeaway_fp_id` is specifically for restaurants with different tax rates for dine-in vs takeaway (e.g., VAT exemption on takeaway in some jurisdictions). The `account.fiscal.position` domain extends to include this position for self-order loading.

4. **Tip after payment:** When `set_tip_after_payment=True`, the payment capture happens in the `pos_restaurant_adyen` / `pos_restaurant_stripe` extensions. The base `_update_payment_line_for_tip` only updates the `amount` field — terminal capture is the extension's responsibility.

5. **`table_stand_number` missing:** Note that `pos.order` in the restaurant module does NOT have a `table_stand_number` field. That field is defined in `pos_self_order/models/pos_order.py` — a separate extension.