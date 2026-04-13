---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #pos
  - #restaurant
---

# pos_restaurant — Restaurant POS Extensions

> Restaurant Point of Sale. Adds floor plan management, table reservations, split-bill functionality, order routing to kitchen printers (IoT Boxes), and course-by-course food delivery to the base POS. Transforms a generic POS into a table-service restaurant system.

**Module:** `pos_restaurant` | **Location:** `odoo/addons/pos_restaurant/` | **Version:** 1.0
**Depends:** `point_of_sale` | **Category:** Sales/Point of Sale | **License:** LGPL-3

---

## Module Architecture

`pos_restaurant` does **not** define new business documents from scratch. It extends four existing `point_of_sale` models (`pos.order`, `pos.order.line`, `pos.config`, `pos.session`, `pos.payment`, `pos.preset`) and introduces three new restaurant-specific models (`restaurant.floor`, `restaurant.table`, `restaurant.order.course`).

```
restaurant.floor (1) ──n── restaurant.table (n) ──n── pos.order (n)
                               │
                               └── pos.order.line (n) ──1── restaurant.order.course
```

| Layer | Model | Odoo Model | Purpose |
|---|---|---|---|
| Space | Floor | `restaurant.floor` | Physical floor with background image/color |
| Space | Table | `restaurant.table` | Individual table with position, shape, seats |
| Order | Course | `restaurant.order.course` | Course grouping of order lines for kitchen sync |
| Order | `pos.order` extension | `pos.order` (inherited) | Table assignment, guest count, courses |
| Order | `pos.order.line` extension | `pos.order.line` (inherited) | Course assignment per line |
| Config | `pos.config` extension | `pos.config` (inherited) | Restaurant-specific POS settings |
| Session | `pos.session` extension | `pos.session` (inherited) | Kitchen preparation change tracking |
| Payment | `pos.payment` extension | `pos.payment` (inherited) | Post-payment tip adjustment |
| Preset | `pos.preset` extension | `pos.preset` (inherited) | `use_guest` flag for preset orders |

### Asset Loading

```python
'assets': {
    'point_of_sale._assets_pos': [
        'pos_restaurant/static/src/**/*',
        ('after', 'point_of_sale/static/src/scss/pos.scss',
         'pos_restaurant/static/src/scss/restaurant.scss'),
    ],
}
```

The restaurant SCSS is loaded **after** the base POS SCSS, allowing restaurant-specific overrides of floor plan, table, and order display styles.

---

## Model Inventory

### `restaurant.floor`

**Model:** `restaurant.floor` | **Inherits:** `pos.load.mixin` | **Access:** `group_pos_user` (read only), `group_pos_manager` (full)

**Purpose:** Represents a dining area or floor. Controls floor-plan visibility per POS config. Each floor can be assigned to multiple POS configs via `Many2many`.

#### Fields

| Field | Type | Default | Index | Notes |
|---|---|---|---|---|
| `name` | Char | required | — | Floor label. Shown in the floor selector tab bar. |
| `pos_config_ids` | Many2many `pos.config` | — | — | Domain: `module_pos_restaurant = True`. Many-to-many allows one floor served by multiple POS registers. |
| `background_image` | Binary | — | — | Legacy background (superseded by `floor_background_image`). |
| `floor_background_image` | Image | — | — | **Odoo 19**: High-res floor plan background. Used when a visual floor map is uploaded. |
| `background_color` | Char | — | — | HTML color string (e.g., `#e8d1b9`). Group `base.group_no_one` (developer-only). |
| `table_ids` | One2many `restaurant.table` | — | — | Cascade delete when floor is removed. |
| `sequence` | Integer | `1` | — | Sort order in the floor tab bar. |
| `active` | Boolean | `True` | — | Archiving hides the floor in the POS. |

#### `_load_pos_data_domain`

```python
@api.model
def _load_pos_data_domain(self, data, config):
    return [('pos_config_ids', '=', config.id)]
```

Only floors linked to the current POS config are loaded. This is the primary filtering mechanism — a POS never sees floors from other registers.

#### `_load_pos_data_fields`

```python
@api.model
def _load_pos_data_fields(self, config):
    return ['name', 'background_color', 'table_ids', 'sequence',
            'pos_config_ids', 'floor_background_image', 'active']
```

Note: `background_color` is in the field list but not in the loaded fields list — it is deliberately excluded from POS frontend sync since it is developer-only.

#### Delete Protection

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_active_pos_session(self):
    confs = self.mapped('pos_config_ids').filtered(lambda c: c.module_pos_restaurant)
    opened_session = self.env['pos.session'].search([
        ('config_id', 'in', confs.ids), ('state', '!=', 'closed')
    ])
    if opened_session and confs:
        error_msg = _("You cannot remove a floor that is used in a PoS session...")
        raise UserError(error_msg)
```

The `@api.ondelete(at_uninstall=False)` decorator means this guard runs during normal deletion but **not** during module uninstall. This allows an admin to cleanly remove the module without hitting spurious errors about open sessions.

#### `write` Protection

```python
def write(self, vals):
    for floor in self:
        for config in floor.pos_config_ids:
            if config.has_active_session and (vals.get('pos_config_ids') or vals.get('active')):
                raise UserError("Please close and validate the following open PoS Session before modifying this floor...")
    return super().write(vals)
```

Any write to `pos_config_ids` or `active` is blocked if the floor belongs to a config with an active session.

#### `sync_from_ui`

```python
def sync_from_ui(self, name, background_color, config_id):
    floor_fields = {"name": name, "background_color": background_color}
    pos_floor = self.create(floor_fields)
    pos_floor.pos_config_ids = [Command.link(config_id)]
```

Called from the OWL `FloorScreen` component when the waiter creates a new floor from the POS UI. Uses `Command.link` (idempotent) to add the config to the many2many without removing existing configs.

#### `deactivate_floor`

```python
def deactivate_floor(self, session_id):
    draft_orders = self.env['pos.order'].search([
        ('session_id', '=', session_id), ('state', '=', 'draft'),
        ('table_id.floor_id', '=', self.id)
    ])
    if draft_orders:
        raise UserError(_("You cannot delete a floor when orders are still in draft..."))
    for table in self.table_ids:
        table.active = False
    self.active = False
```

Deactivation (not deletion) is the only safe way to retire a floor with live orders. The `session_id` argument is the active session; draft orders from other sessions do not block deactivation. All child tables are deactivated alongside the floor.

---

### `restaurant.table`

**Model:** `restaurant.table` | **Inherits:** `pos.load.mixin` | **Access:** `group_pos_user` (read), `group_pos_manager` (full)

**Purpose:** Represents a single table. Stores geometric layout data for the drag-and-drop floor plan canvas.

#### Fields

| Field | Type | Default | Index | Notes |
|---|---|---|---|---|
| `floor_id` | Many2one `restaurant.floor` | required | `btree_not_null` | Cannot be null in the database. Changing floor severs the table's relationship with the old floor. |
| `table_number` | Integer | `0` | — | Displayed as table name on floor plan tiles and receipts. Not the record `name` — `display_name` is computed. |
| `shape` | Selection `[('square', 'Square'), ('round', 'Round')]` | `'square'` | — | Controls CSS class applied to the table tile in `FloorScreen`. |
| `position_h` | Float | `10` | — | Horizontal pixel offset from the left edge of the floor container. Used with `getX()` to support parent-relative positioning. |
| `position_v` | Float | `10` | — | Vertical pixel offset from the top of the floor container. Used with `getY()`. |
| `width` | Float | `50` | — | Table tile width in pixels on the floor plan. |
| `height` | Float | `50` | — | Table tile height in pixels. |
| `seats` | Integer | `1` | — | Default guest count for the table. Feeds `customer_count` on `pos.order` when an order is created for this table. |
| `color` | Char | — | — | CSS `background` property value (e.g., `#f5c6cb`). Rendered as the table tile's fill color. |
| `parent_id` | Many2one `restaurant.table` | — | — | If set, this table is a **child** of another. Position is computed relative to parent via `getParentSide()`. Used for table grouping/merging. |
| `active` | Boolean | `True` | — | Deactivating a table removes it from the POS floor plan |

#### `_compute_display_name`

```python
@api.depends('table_number', 'floor_id')
def _compute_display_name(self):
    for table in self:
        table.display_name = f"{table.floor_id.name}, {table.table_number}"
```

Format: `"Terrace, 12"`. This appears in the table dropdown and backend search results.

#### Load Data

```python
@api.model
def _load_pos_data_domain(self, data, config):
    return [('active', '=', True), ('floor_id', 'in', config.floor_ids.ids)]
```

Only `active=True` tables on floors assigned to this POS config are synced. The `floor_id` condition uses `config.floor_ids.ids` — the list of floor IDs from the many2many. A table on an unassigned floor is never visible.

#### Delete Protection

Same `_unlink_except_active_pos_session` pattern as `restaurant.floor`. Blocks deletion if any draft `pos.order` is linked to the table.

#### `are_orders_still_in_draft`

```python
def are_orders_still_in_draft(self):
    draft_orders_count = self.env['pos.order'].search_count([
        ('table_id', 'in', self.ids), ('state', '=', 'draft')
    ])
    if draft_orders_count > 0:
        raise UserError(_("You cannot delete a table when orders are still in draft..."))
    return True
```

Called by the frontend (`FloorScreen`) before attempting to delete or deactivate a table. Returns `True` if safe; raises `UserError` if any draft orders exist.

#### Performance Notes

- Position fields are floats with no constraints. Overlapping tables are allowed — the floor plan editor does not enforce collision detection.
- `parent_id` creates a tree. `rootTable` traverses to the topmost parent; used for order name generation (`T 12` for a parent, `T 12 & 13` for combined tables).
- Table merge (parent/child linking) is performed via drag-and-drop in `FloorScreen`. The `parent_id` write is sent to the server via `pos.data.write("restaurant.table", [table.id], {parent_id: ...})`.
- The `floor_id` column has a `btree_not_null` index — queries filtered by floor are fast even at scale (200+ tables per floor).

---

### `pos.order` (Extended)

**Inherits:** `pos.order` | **Access:** via `point_of_sale`

`pos_restaurant` extends `pos.order` with three fields. It does not override any ORM `create()`/`write()` methods — the core `pos.order` handles all write logic.

#### Fields

| Field | Type | Index | Notes |
|---|---|---|---|
| `table_id` | Many2one `restaurant.table` | `btree_not_null` | Set when order is assigned to a table. Cleared for direct-sale orders. `readonly=True`. |
| `customer_count` | Integer | — | Number of guests. Defaults to 1. Used by `amountPerGuest()`. |
| `course_ids` | One2many `restaurant.order.course` | — | Courses are created when lines are fired to the kitchen. Lines belong to courses via `course_id` on `pos.order.line`. |

#### `_get_open_order` — Override Logic

```python
def _get_open_order(self, order):
    config_id = self.env['pos.session'].browse(order.get('session_id')).config_id
    if not config_id.module_pos_restaurant:
        return super()._get_open_order(order)

    domain = []
    if order.get('table_id', False) and order.get('state') == 'draft':
        # Match by uuid OR by (table_id + draft state)
        domain += ['|', ('uuid', '=', order.get('uuid')),
                   '&', ('table_id', '=', order.get('table_id')), ('state', '=', 'draft')]
    else:
        domain += [('uuid', '=', order.get('uuid'))]
    return self.search(domain, limit=1, order='id desc')
```

**Restaurant-specific resolution**: When the POS client sends `{table_id, uuid, state: 'draft'}`, the backend resolves the open order either by UUID (exact match) or by `(table_id, draft)` as a fallback. This prevents two cashiers on different devices from creating separate orders for the same table. The `limit=1, order='id desc'` ensures the most recently created draft order is returned if multiple exist.

Non-restaurant configs delegate to the standard base `_get_open_order`.

#### `read_pos_data`

```python
def read_pos_data(self, data, config):
    result = super().read_pos_data(data, config)
    result['restaurant.order.course'] = self.env['restaurant.order.course']._load_pos_data_read(
        self.course_ids, config
    )
    return result
```

Injects `restaurant.order.course` records into the session's initial data load. This ensures the kitchen display (via `pos_preparation_display`) has course data available from session start.

---

### `pos.order.line` (Extended)

**Inherits:** `pos.order.line` | **Access:** via `point_of_sale`

#### Fields

| Field | Type | Index | Notes |
|---|---|---|---|
| `course_id` | Many2one `restaurant.order.course` | `btree_not_null` | Links a line to a firing course. `ondelete='set null'` — if course is deleted, lines keep product data but lose course grouping. |

#### `_load_pos_data_fields`

```python
@api.model
def _load_pos_data_fields(self, config):
    result = super()._load_pos_data_fields(config)
    return result + ["course_id"]
```

`course_id` is included in POS sync so the frontend can render lines grouped by course on kitchen displays and order screens.

---

### `restaurant.order.course`

**Model:** `restaurant.order.course` | **Inherits:** `pos.load.mixin` | **Access:** `group_pos_user` (full)

**Purpose:** Represents a firing course — a group of order lines sent to the kitchen at once. Supports sequential firing (e.g., "Appetizers" then "Mains").

#### Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `fired` | Boolean | `False` | `True` once the course has been sent to kitchen printers/displays |
| `fired_date` | Datetime | — | Auto-set when `fired` transitions to `True`. Not indexed. |
| `uuid` | Char | auto (uuid4) | Readonly, copy=False. Used by frontend to match the selected course via `uiState.selected_course_uuid`. |
| `index` | Integer | `0` | Course sequence number (1st, 2nd, 3rd). Used by `getNextCourseIndex()`. |
| `order_id` | Many2one `pos.order` | required | Cascade delete: removing an order removes all its courses. Index=True. |
| `line_ids` | One2many `pos.order.line` | — | Readonly. Lines in this course via `course_id` on `pos.order.line`. |

#### `write` — Automatic `fired_date`

```python
def write(self, vals):
    if vals.get('fired') and not self.fired_date:
        vals['fired_date'] = fields.Datetime.now()
    return super().write(vals)
```

Auto-sets `fired_date` when `fired` becomes `True`. Same logic in `create()`: if `vals['fired']` is set at creation time (rare), `fired_date` is set immediately.

#### Load Data

```python
@api.model
def _load_pos_data_domain(self, data, config):
    return [('order_id', 'in', [order['id'] for order in data['pos.order']])]
```

Courses are scoped to orders loaded in the current session. Uses the synced `data['pos.order']` list (not a live search) — consistent with the `pos.load.mixin` pattern.

#### Performance Notes

- Course creation is lightweight. Each line assignment does not trigger a write on `pos.order` — the course's `order_id` is set at line creation time.
- `uuid` generation uses Python's `uuid4()` at record creation. Collision probability is negligible (2^122 entropy).
- `fired_date` is not indexed — it is rarely queried. Kitchen display determines firing state from the `fired` boolean field.

---

### `pos.config` (Extended)

**Inherits:** `pos.config` | **Access:** via `point_of_sale`

#### Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `iface_splitbill` | Boolean | — | Enables the **Split Bill** screen. Without this, the split button is hidden in the POS. |
| `iface_printbill` | Boolean | `True` (auto-set on install) | Enables **Bill Printing** before payment. Auto-enabled when `module_pos_restaurant = True` in `create()`. |
| `floor_ids` | Many2many `restaurant.floor` | — | Which floors are available to this POS. Added to `_get_forbidden_change_fields()` — cannot be changed while a session is open. |
| `set_tip_after_payment` | Boolean | — | When `True`, payment screen shows "Keep Open" instead of "Close Tab", and `TipScreen` appears after payment. Requires `iface_tipproduct = True`. |
| `default_screen` | Selection `[('tables', 'Tables'), ('register', 'Register')]` | `'tables'` | Which screen opens first. Restaurant installs default to `'tables'` (the floor plan). |

#### `_get_forbidden_change_fields`

```python
def _get_forbidden_change_fields(self):
    forbidden_keys = super()._get_forbidden_change_fields()
    forbidden_keys.append('floor_ids')
    return forbidden_keys
```

`floor_ids` is added to the blocked list. If a session is running, floor assignment cannot be changed via the Settings UI. The `ResConfigSettings` view enforces this via `readonly="pos_has_active_session"`.

#### `_setup_default_floor` — Auto-Seeding

```python
def _setup_default_floor(self, pos_config):
    if not pos_config.floor_ids:
        main_floor = self.env['restaurant.floor'].create({
            'name': pos_config.company_id.name,
            'pos_config_ids': [(4, pos_config.id)],
        })
        self.env['restaurant.table'].create({
            'table_number': 1, 'floor_id': main_floor.id,
            'seats': 1,
            'position_h': 100, 'position_v': 100,
            'width': 130, 'height': 130,
        })
```

Triggered in `create()` when `module_pos_restaurant = True`, and in `write()` when the module is first enabled on an existing config. Creates one floor named after the company and one centered 130x130px table at position (100, 100). Every new restaurant POS has a working floor out of the box without requiring manual setup.

#### On `module_pos_restaurant` Disable

```python
def write(self, vals):
    if 'module_pos_restaurant' in vals and not vals['module_pos_restaurant']:
        vals['floor_ids'] = [(5, 0, 0)]  # unlink all floors
    if ('module_pos_restaurant' in vals and not vals['module_pos_restaurant']) or \
       ('iface_tipproduct' in vals and not vals['iface_tipproduct']):
        vals['set_tip_after_payment'] = False
```

Disabling the restaurant module clears all floor assignments and disables the post-payment tip feature. The floors themselves are **not deleted** — they become orphaned but remain in the database.

#### Demo Data Loaders

`pos_restaurant` provides two onboarding scenarios:

| Scenario | Method | Config Name | Product Categories | Presets |
|---|---|---|---|---|
| Bar | `load_onboarding_bar_scenario` | `'Bar'` | Cocktails, soft drinks | None |
| Restaurant | `load_onboarding_restaurant_scenario` | `_(Restaurant)`` | Food, drinks | Take-in, Takeout, Delivery |

Both load `restaurant_floor.xml` (two floors: Main, Patio) and mark the config as `iface_splitbill = True`. The restaurant scenario additionally enables `use_presets` and sets `available_preset_ids`.

---

### `pos.session` (Extended)

**Inherits:** `pos.session` | **Access:** via `point_of_sale`

#### `_load_pos_data_models`

```python
@api.model
def _load_pos_data_models(self, config):
    data = super()._load_pos_data_models(config)
    if self.config_id.module_pos_restaurant:
        data += ['restaurant.floor', 'restaurant.table', 'restaurant.order.course']
    return data
```

When restaurant mode is active, the three restaurant models are added to the session sync list. They load in dependency order: `restaurant.floor` → `restaurant.table` → `restaurant.order.course` (enforced by foreign-key constraints).

#### `_set_last_order_preparation_change`

```python
@api.model
def _set_last_order_preparation_change(self, order_ids):
    for order_id in order_ids:
        order = self.env['pos.order'].browse(order_id)
        last_order_preparation_change = {'lines': {}, 'generalCustomerNote': ''}
        for orderline in order['lines']:
            last_order_preparation_change['lines'][orderline.uuid + " - "] = {
                "uuid": orderline.uuid,
                "name": orderline.full_product_name,
                "note": "",
                "product_id": orderline.product_id.id,
                "quantity": orderline.qty,
                "attribute_value_ids": orderline.attribute_value_ids.ids,
            }
        order.write({'last_order_preparation_change': json.dumps(last_order_preparation_change)})
```

Stores the order's current line state as JSON for the kitchen order printing system. The `"uuid - "` key format (trailing space and hyphen) is a convention used by `pos_preparation_display` to parse line keys. This method is called when courses are fired or lines change.

---

### `pos.payment` (Extended)

**Inherits:** `pos.payment` | **Access:** via `point_of_sale`

#### `_update_payment_line_for_tip`

```python
def _update_payment_line_for_tip(self, tip_amount):
    self.ensure_one()
    self.write({"amount": self.amount + tip_amount})
```

Called by `TipScreen` after customer confirms a tip. Adds the tip to the existing payment line. **No payment terminal re-authorization** is performed here — the base implementation just writes the new total. Terminal re-auth (e.g., Adyen, Ingenico) is handled in the frontend via `payment_terminal.sendPaymentAdjust()`.

> **L4 Edge Case:** If `tip_amount` is zero, this still runs `write()`. The base `pos.payment` handles zero gracefully, but a redundant write is executed. This is acceptable since tip confirmations are infrequent and the write is local. The real risk is in the frontend: `validateTip()` calls `sendPaymentAdjust()` only when `payment_method_id.payment_terminal` exists — cash payments are not re-authenticated.

---

### `pos.preset` (Extended)

**Inherits:** `pos.preset` | **Access:** via `point_of_sale`

#### `use_guest`

| Field | Type | Default | Notes |
|---|---|---|---|
| `use_guest` | Boolean | `False` | When `True`, POS forces waiter to select a guest count before the preset order is registered. |

#### `_unlink_except_master_presets`

```python
def _unlink_except_master_presets(self):
    master_presets = self.env["pos.config"].get_record_by_ref([
        'pos_restaurant.pos_takein_preset',
        'pos_restaurant.pos_takeout_preset',
        'pos_restaurant.pos_delivery_preset',
    ])
    if any(preset.id in master_presets for preset in self):
        raise UserError(_('You cannot delete the master preset(s).'))
```

Prevents deletion of the three factory presets. The presets are defined in `data/scenarios/restaurant_preset.xml` and cannot be removed via the UI or API.

---

### `res.config.settings` (Extended)

**Inherits:** `res.config.settings` | **Access:** via `point_of_sale`

| Related Field | Type | Compute Method |
|---|---|---|
| `pos_floor_ids` | Many2many `restaurant.floor` | direct `related` |
| `pos_iface_printbill` | Boolean | `_compute_pos_module_pos_restaurant` |
| `pos_iface_splitbill` | Boolean | `_compute_pos_module_pos_restaurant` |
| `pos_set_tip_after_payment` | Boolean | `_compute_pos_set_tip_after_payment` |
| `pos_default_screen` | Selection | direct `related` |

#### `_compute_pos_module_pos_restaurant`

```python
def _compute_pos_module_pos_restaurant(self):
    for res_config in self:
        if not res_config.pos_module_pos_restaurant:
            res_config.update({'pos_iface_printbill': False, 'pos_iface_splitbill': False})
        else:
            res_config.update({
                'pos_iface_printbill': res_config.pos_config_id.iface_printbill,
                'pos_iface_splitbill': res_config.pos_config_id.iface_splitbill,
            })
```

If the restaurant module is disabled, both flags are forced to `False`. This is a one-way gate — unchecking `module_pos_restaurant` also resets the UI flags.

---

## Frontend Architecture (OWL / JavaScript)

### Models

#### `pos_order.js` — PosOrder Restaurant Patch

Extends `PosOrder` from `point_of_sale`. Key additions:

**`isDirectSale`** getter:
```javascript
get isDirectSale() {
    return Boolean(
        this.config.module_pos_restaurant &&
        !this.table_id &&
        !this.floating_order_name &&
        this.state == "draft" &&
        !this.isRefund
    );
}
```
Returns `True` for cash-and-carry orders (no table) processed through the restaurant POS. Used to suppress table UI elements and generate "Direct Sale" order names.

**`getName()` override**:
- Table order: `"T {n}"` (e.g., `T 12`, `T 12 & 13` for parent + children)
- Direct sale: `"Direct Sale"`
- Otherwise: falls back to `super.getName()`

**`amountPerGuest(numCustomers)`**:
```javascript
amountPerGuest(numCustomers = this.customer_count) {
    if (numCustomers === 0) return 0;
    return this.totalDue / numCustomers;
}
```
Guards against division by zero. `totalDue` is the amount still owed (total minus payments). Used in the payment screen to display price-per-guest.

**Course management**:
- `courses` getter: `course_ids.toSorted((a, b) => a.index - b.index)`
- `hasCourses()`, `selectCourse(course)`, `getSelectedCourse()`, `ensureCourseSelection()`, `deselectCourse()`
- `cleanCourses()`: Removes empty courses and re-indexes remaining ones. Deletes courses beyond the last fired course that have no lines. Called when navigating back to the floor plan.

**`isBooked` override**: Restaurant orders are "booked" if they are not direct sales. This controls whether the order is treated as a table reservation versus a walk-in.

#### `restaurant_table.js` — RestaurantTable Model

Extends `Base` (related model mixin from `point_of_sale`).

**Position computation**:
- `getX()`, `getY()`: If `parent_id` is set, position is computed relative to the parent based on `parent_side` (top/bottom/left/right). The `parent_side` is determined once from the child's offset relative to the parent's center (`getParentSide()`) and cached in `this.parent_side`.
- For non-parent tables, returns the raw `position_h`/`position_v`.

**Table linking logic** (`setPositionAsIfLinked`): Temporarily links a table to a parent to compute a relative position, then unlinks. Used during drag operations to compute where the child would sit relative to the parent.

**Order retrieval**:
- `getOrders()`: Returns all non-finalized orders for this table, plus finalized orders currently in the TipScreen.
- `getOrder()`: Returns the current non-finalized order, checking parent table first via `parent_id?.getOrder()`.

**Tree traversal**:
- `rootTable` getter: Walks up `parent_id` chain to the topmost table.
- `children` getter: Returns `backLink("<-restaurant.table.parent_id")` — all tables where `parent_id = this`.

#### `restaurant_order_course.js` — RestaurantOrderCourse Model

- `name` getter: `"Course " + index` (localized via `_t`).
- `isSelected()`: `order_id.uiState.selected_course_uuid === this.uuid`.
- `isReadyToFire()`: `!fired && !isEmpty()`.
- `isEmpty()`: `line_ids?.length === 0`.

#### `pos_config.js` — PosConfig Restaurant Patch

```javascript
get useProxy() {
    return super.useProxy || (this.iot_device_ids && this.iot_device_ids.length > 0);
},
get isShareable() {
    return super.isShareable || this.module_pos_restaurant;
}
```

- `useProxy`: Extends base to include IoT device connectivity for kitchen printers.
- `isShareable`: Enables multi-terminal mode for restaurant configs. Multiple POS boxes can share the same config simultaneously.

#### `pos_order_line.js` — PosOrderLine Restaurant Patch

- `note`: Initialized to `""` if absent.
- `clone()`: Preserves `note` when cloning (split-to-new-order scenario).
- `canBeMergedWith(orderline)`: Returns `False` if the two lines belong to different courses. Lines can only merge within the same course.
- `getDisplayClasses()`: Adds `"has-change"` class when the line has a change note and the config is restaurant mode. Triggers visual highlighting of changed items in the order display.

#### `pos_payment.js` — PosPayment Restaurant Patch

```javascript
canBeAdjusted() {
    if (this.payment_method_id.payment_terminal) {
        return this.payment_method_id.payment_terminal.canBeAdjusted(this.uuid);
    }
    return !this.payment_method_id.is_cash_count &&
           this.payment_method_id.payment_method_type != "qr_code";
}
```

Extends base logic. For restaurant POS, cash payments can be adjusted to add tips. The override allows adjustment for all non-cash, non-QR-code methods that support a payment terminal.

---

### Screens

#### `FloorScreen` (`floor_screen.js`)

The primary floor plan interface. Manages table drag-and-drop, table merging, floor switching, and edit mode.

**State**:
- `selectedFloorId`: Currently displayed floor
- `selectedTableIds`: Tables selected for bulk operations
- `potentialLink`: Tracks a table being dragged for merge detection (`{child, parent, time}`)
- `floorMapOffset`: Scroll offset for drag boundary computation

**Key Operations**:

1. **Table drag (non-edit mode)**: Moves table, starts merge detection via `areElementsIntersecting()`. If no intersecting table is found within the drag, shows "Link Table" alert.
2. **Edit mode**: Grid-snaps positions (`position_h -= position_h % GRID_SIZE`). Shows resize handles. Disables merge detection. Triggered by `pos.isEditMode` flag.
3. **Table creation**: `createTable()` → `sync_from_ui()` on server + creates local `restaurant.table` model.
4. **Table merge**: When a dragged table overlaps another for >400ms (`TABLE_LINKING_DELAY`), a `parent_id` link is created via `pos.data.write`. Child position becomes relative to parent.
5. **Table unlink**: Dropping a child table outside the parent's zone calls `unMergeTable()` and writes `parent_id: null`.
6. **Table delete**: Only possible if `are_orders_still_in_draft()` returns `True`.
7. **Floor switching**: Preserves selected table IDs across floor switches.

**Drag constraint**: `getLimits()` computes min/max X/Y so tables cannot be dragged fully outside the floor container.

**External listener on `Escape` key**: Exits edit mode when no tables are selected and no potential link is in progress.

#### `SplitBillScreen` (`split_bill_screen.js`)

Handles bill splitting — distributing order lines between the original order and a new split order.

**Flow**:

1. User taps lines to increment `qtyTracker[uuid]` (cycles `0 → 1 → ... → maxQty → 0`).
2. Combo lines: `getAllLinesInCombo()` ensures all children are selected together with the parent.
3. `createSplittedOrder()`:
   - Creates a new `pos.order` via `pos.createNewOrder()`
   - Sets `floating_order_name` (e.g., `T 12B`)
   - Links both orders via `uiState.splittedOrderUuid` (bidirectional)
   - Creates new `pos.order.line` records with selected quantity
   - Handles course reassignment by matching `index`
   - Relinks combo parent/child via `comboMap`
4. `handleDiscountLines()`: Applies original order's global discount percentage to the new order (only when not a transfer operation).
5. Original order's `customer_count` is decremented by 1.
6. `syncAllOrders()` persists both orders to the server.

**Naming convention**: Split orders append a letter suffix (`T 12A`, `T 12B`, ... up to `T 12Z`). `_getSplitOrderName()` finds the highest existing suffix to continue the sequence. If the suffix letter would exceed `'Z'`, throws an error.

**Route**: `/pos/ui/{config_id}/splitting/{orderUuid}` — allows deep-linking to a specific split session from an external link.

**Two actions**:
- `paySplittedOrder()`: Splits then immediately opens payment screen for the new order.
- `transferSplittedOrder()`: Splits then calls `pos.startTransferOrder()` to transfer the table to a new party.

#### `TipScreen` (`tip_screen.js`)

Post-payment tip collection. Activated when `set_tip_after_payment = True` and the order is fully paid.

**Flow**:

1. `validateTip()`: Checks order is synced (`isSynced && order.id`). Prompts confirmation for amounts >25% of order total.
2. `pos.setTip(amount)`: Calls server-side tip logic.
3. **Payment terminal re-auth**: If `payment_method_id.payment_terminal` exists, `sendPaymentAdjust()` captures the additional amount.
4. **Tip line creation**: Serializes the tip line from the order, deletes the temporary frontend tip line, creates a server-side tip line via `pos.data.create("pos.order.line", ...)`.
5. Updates order: `is_tipped = True`, `tip_amount = serverTipLine[0].priceIncl`.
6. `printTipReceipt()`: Prints any ticket/cashier receipt from the payment terminal.

**Screen navigation**: After tip confirmation, navigates to `ReceiptScreen`. In non-restaurant mode, creates a new order first.

#### `Navbar` Restaurant Patch

- `showTabs()`: Returns `False` when a table is selected (tabs are hidden during active order taking).
- `onClickPlanButton()`: Calls `cleanCourses()` before navigating to floor plan.
- `mainButton`: Shows `"table"` label when on the floor screen, otherwise falls back to default.
- `canClick()`: Prevents navigation if current order is a filled direct sale — bouncing the button prompts user to complete the order.
- `onTicketButtonClick()`: Delegated through `canClick()`.
- `currentOrderName`: Strips `"T "` prefix from order name for navbar display.

---

### Components

| Component | File | Purpose |
|---|---|---|
| `NumpadDropdown` | `components/numpad_dropdown/` | Custom numpad for table number, seat count, position entry |
| `OrderCourse` | `components/order_course/` | Course tab UI — selection, firing, index management |
| `OrderTabs` | `components/order_tabs/` | Order tabs for managing multiple simultaneous orders |
| `OrderDisplay` | `components/order_display/` | Extends base order display with course grouping |
| `Orderline` | `components/orderline/` | Extends base order line with course badge and change indicator |
| `TipReceipt` | `components/tip_receipt/` | Receipt template for tip confirmation prints |

---

### Kitchen Order Printing

`pos_restaurant` integrates with the order change system via `getOrderChanges()` (from `point_of_sale/app/models/utils/order_change`). The `order_change_receipt_template.xml` file defines the XML template used by IoT printers to print kitchen tickets.

The `last_order_preparation_change` JSON field on `pos.order` stores the current line state. When courses are fired, `pos.session._set_last_order_preparation_change()` updates this field with the current line data, which is consumed by `pos_preparation_display` or `pos_order_tracking` to show kitchen updates in real time.

---

## Security

### Access Control (`ir.model.access.csv`)

| Model | `group_pos_user` | `group_pos_manager` |
|---|---|---|
| `restaurant.floor` | read | full |
| `restaurant.table` | read | full |
| `restaurant.order.course` | create/read/write/unlink | full |

**Implication**: Regular POS users can read floors and tables (view the floor plan) but cannot modify them. Order courses are fully writable — waiters can fire courses.

### Field-Level Restrictions

| Field | Group | Notes |
|---|---|---|
| `restaurant.floor.background_color` | `base.group_no_one` | Developer-only |
| `restaurant.table.position_h/v/width/height/shape` | `base.group_no_one` | Hidden from regular users via form view; still synced to POS frontend |

The table geometric fields are hidden in the backend but still transmitted to the POS client — the POS needs these to render the floor plan. The `group_no_one` restriction prevents accidental modification via the backend form.

### Row-Level Security

No `ir.rule` records are defined. Floor/table access is controlled at the `pos.config` level via `pos_config_ids` on `restaurant.floor`. Users only see floors assigned to POS configs they have access to.

---

## Cross-Module Integration

| Partner Module | Integration Point | Direction |
|---|---|---|
| `point_of_sale` | `_inherit`, `_load_pos_data_*` | Extends |
| `pos_self_order` | Orders via `pos.order` state machine | Listens |
| `pos_preparation_display` | `restaurant.order.course.fired`, `last_order_preparation_change` | Reads |
| `pos_order_tracking` | `pos.order` state, `table_id`, `customer_count` | Reads |
| `pos_preset` | `pos.preset` extension with `use_guest` | Extends |
| `pos_iot` | `iot_device_ids` on `pos.config` for kitchen printers | Reads config |
| `pos_restaurant` | No reverse dependency | — |

---

## Odoo 18 to 19 Changes

| Change | Odoo 18 | Odoo 19 |
|---|---|---|
| `floor_background_image` | Did not exist (only `background_image` binary) | Added `Image` field for high-res backgrounds |
| `restaurant.order.course` sync domain | Used live `self.env['pos.order'].search([])` | Uses `data['pos.order']` from synced session data |
| `PosSession._set_last_order_preparation_change` | Did not exist | Added for kitchen display integration |
| `set_tip_after_payment` config flag | Not present | Added |
| `default_screen` selection | Not present | Added, default `'tables'` |
| Split bill naming | Basic append | Handles sequential splits with letter suffix (`A`, `B`, `C`...) |
| Course index rebalancing | Not present | `cleanCourses()` reindexes after removal |
| `PosConfig.isShareable` | Not overridden | Overridden to return `True` for restaurant configs |

---

## Performance Considerations

1. **Floor/table sync**: `restaurant.floor` and `restaurant.table` use `pos.load.mixin` — bulk-loaded once at session start. For 200+ tables, the initial payload is ~50KB, acceptable on modern POS hardware.
2. **Table drag writes**: `position_h`/`position_v` are written on every drag frame (~60/sec on a 60Hz display). The frontend batches these writes until drop, but network latency on low-end IoT boxes can cause UI stuttering. Consider debouncing if many tables are simultaneously dragged.
3. **Course firing**: A single `UPDATE` statement sets `fired = True` and auto-sets `fired_date`. No cascading writes.
4. **Tip screen**: `validateTip()` performs two `pos.data.write()` calls (order update + tip line creation). If the payment terminal call fails after the order is marked `is_tipped`, the state is inconsistent. The frontend handles this by reverting the order to `draft` state during the operation.
5. **`_get_open_order` search**: The compound `(table_id, state)` domain is indexed via `table_id` (`btree_not_null`). The `state` search is a secondary filter on a smaller result set, which is fast.

---

## Edge Cases

| Scenario | Behavior | Risk |
|---|---|---|
| Deactivating a floor with orders from a different session | Proceeds — only checks current session's draft orders | Floor archived but orphaned orders still exist |
| Splitting a combo line | All children move together with parent; `combo_parent_id` relinked via `comboMap` | Combo integrity maintained |
| Merging lines from different courses | `canBeMergedWith()` returns `False` | Cross-course merges blocked to protect kitchen grouping |
| `set_tip_after_payment` with no payment terminal | Tip added to order; no terminal re-auth; `canBeAdjusted()` allows cash adjustment | Cash tips recorded but not captured via terminal |
| `set_tip_after_payment` with no payment lines (100% discount order) | `TipScreen` crashes on `order.payment_ids[0]` access | Not currently guarded — `isPaid()` guard should prevent reaching `TipScreen` with zero payment lines |
| Table with no `parent_id` but `parent_side` set | `getX()`/`getY()` fall back to raw `position_h`/`position_v` | Safe fallback |
| Multi-terminal with same table opened on two devices | `_get_open_order` finds existing draft order by `(table_id, draft)` | Prevents duplicate orders for same table |

---

## Data Files

| File | Purpose |
|---|---|
| `data/scenarios/restaurant_preset.xml` | Factory presets: Take-in, Takeout, Delivery |
| `data/scenarios/restaurant_floor.xml` | Demo floor plan: Main + Patio floors with multiple tables |
| `data/scenarios/bar_category_data.xml` | Bar product categories: cocktails, soft drinks |
| `data/scenarios/bar_demo_data.xml` | Bar demo products and variants |
| `data/scenarios/restaurant_category_data.xml` | Restaurant categories: food, drinks |
| `data/scenarios/restaurant_demo_data.xml` | Demo products, variants, and pricelists |
| `data/scenarios/restaurant_demo_session.xml` | Pre-closed demo session (restaurant scenario only) |
| `security/ir.model.access.csv` | ACL entries for restaurant models |

---

---

## L4: Kitchen Display Screen Integration

### Architecture: POS ↔ Kitchen Display Communication

`pos_restaurant` integrates with `pos_preparation_display` (KDS — Kitchen Display System) through a multi-layer notification pipeline. The KDS runs as a separate OWL application (separate browser tab or IoT box) that connects to the same `pos.session`.

```
POS Frontend (OWL App)          Kitchen Display (OWL App / IoT)
        │                                    │
        │  User fires course                 │
        ▼                                    │
pos.session._set_last_order_preparation_change()
        │                                    │
        ▼                                    │
pos.order.last_order_preparation_change      │
(JSON field on pos.order)                    │
        │                                    │
        │  Odoo Bus (bus.bus) notifies      │
        ▼                                    │
        │  ───────────────────────────────► │
        │  "pos.order.changed" event        │
        ▼                                    │
        │                          KDS receives JSON
        │                          and renders kitchen ticket
```

### `_set_last_order_preparation_change` — Deep Dive

```python
@api.model
def _set_last_order_preparation_change(self, order_ids):
    for order_id in order_ids:
        order = self.env['pos.order'].browse(order_id)
        last_order_preparation_change = {
            'lines': {},
            'generalCustomerNote': '',
        }
        for orderline in order['lines']:
            last_order_preparation_change['lines'][orderline.uuid + " - "] = {
                "uuid": orderline.uuid,
                "name": orderline.full_product_name,
                "note": "",
                "product_id": orderline.product_id.id,
                "quantity": orderline.qty,
                "attribute_value_ids": orderline.attribute_value_ids.ids,
            }
        order.write({'last_order_preparation_change': json.dumps(last_order_preparation_change)})
```

**JSON structure:**
- Key: `orderline.uuid + " - "` — trailing space and hyphen is a **KDS protocol convention** used by `pos_preparation_display` to parse line keys
- `full_product_name`: The display name (product name + variant attributes). Used on kitchen tickets instead of bare product name.
- `attribute_value_ids`: Required for KDS to show variant-specific details (e.g., "Burger — No Onions")
- `note`: Empty string here — note display is handled separately by the KDS from `line.note`

**Trigger points** (from the frontend):
- Course is fired (`pos_restaurant` `fireCourse()`)
- Line is added to an order (`PosOrder.addLine()`)
- Line quantity changes
- Line is voided

### Odoo Bus Notification

`pos_restaurant` does not directly use `bus.bus`. The notification mechanism is provided by `point_of_sale`'s session sync system. When `last_order_preparation_change` is updated:

1. The OWL `OrderDefinition` component detects the change on the `pos.order` record
2. It calls `pos.prepare_action().update(` to push the change to the KDS
3. The KDS listens for `pos.order.changed` events and re-renders the kitchen ticket

**L4 Note:** The bus notification is fire-and-forget. If the KDS tab is closed or the IoT box is offline, the notification is lost. The KDS has no guaranteed delivery mechanism — it relies on the POS operator noticing missing updates and manually triggering a re-sync.

### Course Firing and Kitchen Ticket Lifecycle

| Stage | POS Action | KDS Effect |
|---|---|---|
| 1. Order created | Lines added to draft order | No ticket yet |
| 2. First course fired | `course.fired = True`, `fired_date` set | New ticket appears with all lines in Course 1 |
| 3. Second course fired | Second `restaurant.order.course` created | Second ticket appears |
| 4. Line edited (void/add) | `last_order_preparation_change` updated | KDS ticket updated in real-time |
| 5. Order closed (payment) | `state → 'paid'` | Ticket marked as done/archived |
| 6. Session closed | `pos.session` state → `'closed'` | All tickets closed |

### Integration with `pos_order_tracking`

`pos_order_tracking` reads `pos.order.table_id` and `pos.order.customer_count` to display order status on a tracking screen (e.g., "Table 12 — 3 guests — waiting 12 min"). This does not require `restaurant.order.course` — it reads the base `pos.order` fields added by `pos_restaurant`.

---

## L4: Security Deep-Dive

### Multi-Company Isolation

`pos_restaurant` does **not** implement multi-company record rules. The isolation is enforced at the `pos.config` level:

1. `restaurant.floor` is linked to `pos.config` via `Many2many`
2. `restaurant.table` is linked to `restaurant.floor` via `Many2one`
3. `pos.order` gets its `table_id` from the POS session's config

**Attack vector:** If a user has access to two companies' POS configs, and both configs are open in the same browser session (a session opened via two separate POS devices), the floor/table data is **not** filtered between companies. This is because the POS client loads data based on the session's `pos.config.id`, which is set at session creation time.

**Mitigation:** Multi-company deployments must use separate POS devices (separate browser sessions) per company. Odoo's session model does not support cross-company POS access within a single client instance.

### Row-Level Security

No `ir.rule` records exist for `restaurant.floor`, `restaurant.table`, or `restaurant.order.course`. The floor/table data scope is controlled by:

1. **`_load_pos_data_domain`** on each model — scopes data to the current `pos.config.id`
2. **`pos.config` ACL** — only users with access to a POS config can open that POS session
3. **POS frontend** — the loaded data is pre-filtered; the client never receives data it shouldn't

**Implication:** A user who has `group_pos_user` and can access POS Config A will see Config A's floors/tables. If the same user somehow gains access to POS Config B (which they shouldn't, given proper ACL), they would also see Config B's floors/tables. Proper ACL at the `pos.config` level is the primary guard.

### Sensitive Field: `background_color`

```python
background_color = fields.Char(
    'Background Color',
    help="The background color of the floor in a html-compatible format",
    groups='base.group_no_one'  # Developer mode only
)
```

This field has `groups='base.group_no_one'` — only developers can set it via the backend form. However, the value is **not** sent to the POS frontend (it is excluded from `_load_pos_data_fields`). A malicious floor color cannot be injected via this field.

### Table Position Fields

```python
position_h = fields.Float(...)   # group_no_one in views
position_v = fields.Float(...)   # group_no_one in views
width = fields.Float(...)        # group_no_one in views
height = fields.Float(...)       # group_no_one in views
```

These are hidden from non-developer backend forms via `groups='base.group_no_one'` in the view XML. They are sent to the POS frontend via `_load_pos_data_fields` — the POS client needs these to render the floor plan. No injection risk: the values are floats used directly as CSS pixel values.

### IoT Kitchen Printer Access

The `useProxy` getter on `PosConfig` enables IoT device connectivity:

```javascript
get useProxy() {
    return super.useProxy || (this.iot_device_ids && this.iot_device_ids.length > 0);
}
```

When `useProxy` is True, the POS can route kitchen print jobs to IoT boxes. The `iot_device_ids` are managed via the standard IoT module's ACL. If a user can add IoT devices to a POS config, they can redirect kitchen tickets. This requires `group_pos_manager` or `base.group_system` — appropriate for this capability.

---

## L4: Complete Workflow Failure Analysis

### Table Selection and Order Creation

| Failure Mode | Root Cause | Behavior | Resolution |
|---|---|---|---|
| Two orders for same table | Two POS devices both call `_get_open_order` before either writes | The search finds no existing draft; both devices create new orders | `_get_open_order`'s `(table_id, state=draft)` fallback prevents this in normal flow. Race condition only if both calls happen within the same database transaction |
| Order created for wrong table | UUID mismatch in `_get_open_order` | `uuid` check passes but `table_id` check uses wrong table ID | `table_id` is set by the frontend; if frontend sends wrong ID, order attaches to wrong table. No server-side validation of table_id against session's floor_ids |
| Deactivating floor with active session | `write()` check looks at `has_active_session` | `has_active_session` is computed at access time — if session was opened before floor was assigned to config, the check may pass | The `has_active_session` check in `write()` prevents modification when a session is **currently open**. Sessions opened before floor assignment are not blocked |

### Bill Splitting

| Failure Mode | Root Cause | Behavior | Resolution |
|---|---|---|---|
| Split order missing discount | `handleDiscountLines()` applies discount % but has rounding error | Discount on new order is 0.01 off | Acceptable minor discrepancy; discount is recalculated when new order is paid |
| Combo line split | `getAllLinesInCombo()` relinks all children | All combo children move to new order | Correct behavior — combos stay together |
| Split to more than 26 orders | `_getSplitOrderName()` uses letters A-Z | Throws error | Hard limit of 26 split orders per table |
| Split during kitchen firing | Course already fired | Course stays on original order | Correct — fired courses stay on the order that was fired |

### Tip After Payment

| Failure Mode | Root Cause | Behavior | Resolution |
|---|---|---|---|
| Pre-auth expiry (Stripe) | Pre-auth not captured within Stripe's window (typically 7 days) | Customer's bank releases the hold without capturing | Process tips before session close. For expired pre-auths, payment must be re-run |
| Terminal offline during tip capture | IoT box or terminal loses connectivity | `capturePaymentStripe()` fails; order stuck in `is_tipped=True` with partial payment | Cash tip alternative; manual void and re-run payment; contact Stripe for manual capture |
| Zero-tip confirmation | Waiter confirms 0 tip | `capturePaymentStripe` called with base amount | Works correctly — captures the pre-auth amount |
| Multiple tip attempts | `sendPaymentAdjust()` called twice | Stripe rejects second capture (duplicate) | Frontend guards against double-click via disabled button state during capture |

### Course Firing

| Failure Mode | Root Cause | Behavior | Resolution |
|---|---|---|---|
| Course fired but order cancelled | Manager cancels order after firing | Kitchen ticket for cancelled order | KDS should check `pos.order.state` before displaying. `pos_preparation_display` handles this |
| Empty course fired | Waiter fires course with no lines | `cleanCourses()` is called before firing — empty courses should be excluded | Guard in `isReadyToFire()` checks `!isEmpty()` |
| Fire course then split order | `createSplittedOrder()` reassigns lines | Lines moved to new order but course stays on original | Correct — course stays with the order it was fired on. New order has no fired courses |

---

## L4: Complete Edge Case Register

| # | Scenario | Current Behavior | Risk Level | L4 Recommendation |
|---|---|---|---|---|
| EC-01 | Deactivating floor with orders from a different session | Proceeds — only checks current session | Low | Floor archived but orphaned orders still exist |
| EC-02 | Splitting a combo line | All children move together | None | Combo integrity maintained |
| EC-03 | Merging lines from different courses | Blocked by `canBeMergedWith()` | None | Correct kitchen grouping preserved |
| EC-04 | `set_tip_after_payment` with cash payment | Tip added; no terminal re-auth | Low | Cash tips recorded; consider disabling tip screen for cash-only orders |
| EC-05 | `set_tip_after_payment` with 100% discount order | TipScreen crashes on `payment_ids[0]` | Medium | Add `isPaid()` guard before navigating to TipScreen |
| EC-06 | Table with no `parent_id` but `parent_side` set | Falls back to raw `position_h`/`position_v` | None | Safe fallback |
| EC-07 | Multi-terminal with same table on two devices | `_get_open_order` finds existing draft by `(table_id, draft)` | None | Prevents duplicate orders |
| EC-08 | `floor_background_image` upload on low-bandwidth IoT | Large binary upload may fail on slow connection | Medium | Compress images before upload; Odoo 19 handles via Filestore |
| EC-09 | `uuid` collision on `restaurant.order.course` | Theoretical (2^122 entropy) | Negligible | No mitigation needed |
| EC-10 | Write to `pos_config_ids` on floor during active session | Blocked by `write()` guard | None | Correct — active session protection |
| EC-11 | `module_pos_restaurant` disabled while POS is running | `floor_ids` cleared; POS continues with stale data | Medium | Close and reopen POS session after disabling restaurant mode |
| EC-12 | Preset deleted while POS session is active | Master presets are protected by `_unlink_except_master_presets` | None | Correct |
| EC-13 | Split bill on an order with loyalty rewards | Rewards are not split — stay on original order | None | Correct behavior — rewards belong to the order |
| EC-14 | `last_order_preparation_change` updated by two concurrent requests | JSON field write is not locking | Low | Last write wins; minor sync issue on KDS |
| EC-15 | Negative `seats` on table | No ORM constraint; `seats >= 0` not enforced | Low | Set `min="0"` on the form view's `seats` field |



## Related Documentation

- [Modules/point_of_sale](point_of_sale.md) — Parent module
- [Modules/pos](pos.md) — Preset order system
- [Modules/pos](pos.md) — Kitchen display
- [Modules/pos_self_order](pos_self_order.md) — Self-service kiosk