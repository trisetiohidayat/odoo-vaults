# event_booth — Events Booths

**Module:** `event_booth`
**Depends:** `event`
**Category:** Marketing/Events
**Version:** 1.1
**License:** LGPL-3
**Author:** Odoo S.A.

Manages physical booth stands rented to exhibitors at events. Provides booth categories, reservation tracking, contact management per booth, and chatter integration for booking notifications. Pricing and e-commerce flows are handled by the companion module `event_booth_sale`.

---

## Architecture

Five models are defined or extended:

| Model | Kind | Description |
|---|---|---|
| `event.booth` | Concrete | A single rentable booth at a specific event |
| `event.booth.category` | Concrete | Typology of booth (Standard, Premium, VIP) |
| `event.type.booth` | Abstract template | Booth template stored on `event.type`, used to pre-populate events |
| `event.event` | Extended (core) | Adds computed booth counts and a "Booths" stat button |
| `event.type` | Extended (core) | Adds `event_type_booth_ids` one2many for template booths |

The inheritance chain of `event.booth`:

```python
class EventBooth(models.Model):
    _name = 'event.booth'
    _inherit = [
        'event.type.booth',    # name, booth_category_id (from base template)
        'mail.thread',         # chatter, message_post, subtypes
        'mail.activity.mixin' # activity_ids
    ]
```

---

## Model: `event.booth`

**`_name`** = `event.booth`
**`_description`** = `Event Booth`

### Fields

#### Identity / Naming

- **`name`** (Char, required, translate=True) — Inherited from `event.type.booth`. Human-readable booth name, e.g. `"Booth A1"`, `"Premium Showbooth 1"`. Set when booths are generated from event type templates or entered manually.

#### Relations

- **`event_id`** (Many2one to `event.event`, required, cascade delete, indexed) — The event this booth belongs to. `ondelete='cascade'` means deleting the event deletes all its booths.

- **`booth_category_id`** (Many2one to `event.booth.category`, inherited from `event.type.booth`, required) — The booth category/tier. Controls pricing (via `event_booth_sale`), image, and description. `ondelete='restrict'` on the template side prevents accidental category deletion while booths reference it.

- **`event_type_id`** (Many2one to `event.type`, optional, `ondelete='set null'`) — Present on `event.type.booth` but **not actively used on `event.booth`** in the core module. Exists via the `event.type.booth` mixin but is not populated at event level; its primary role is on the template model.

- **`partner_id`** (Many2one to `res.partner`, copy=False, `tracking=True`) — The renting company/contact. When set, the booth transitions to `unavailable`. This field is the primary driver of booth state.

#### Contact (computed from `partner_id`, stored)

These three fields are **computed** (`readonly=False, store=True`). They auto-populate from `partner_id` on first write but are user-editable thereafter. `copy=False` prevents copying renter details when duplicating a booth.

- **`contact_name`** (Char) — `partner_id.name`.
- **`contact_email`** (Char) — `partner_id.email`.
- **`contact_phone`** (Char) — `partner_id.phone`.

#### State

- **`state`** (Selection, required, default=`'available'`, `tracking=True`, `group_expand=True`)
  - `'available'` — Booth is free to reserve.
  - `'unavailable'` — Booth has been booked/rented.

- **`is_available`** (Boolean, computed, searchable) — `True` when `state == 'available'`. Implements a custom `_search_is_available` that rewrites the domain to `state = 'available'/'unavailable'`. Supports only `in`/`not in` operators; returns `NotImplemented` for others.

### Methods

#### `create(vals_list)`

```python
@api.model_create_multi
def create(self, vals_list):
    res = super().create(vals_list)
    unavailable_booths = res.filtered(lambda b: not b.is_available)
    unavailable_booths._post_confirmation_message()
    return res
```

**Behavior:** Passes `mail_create_nosubscribe=True` to prevent auto-subscribing all booth creators to the event chatter. After record creation, any booths created with `state='unavailable'` immediately trigger the booking notification message.

#### `write(vals)`

```python
def write(self, vals):
    to_confirm = self.filtered(lambda b: b.state == 'available')
    res = super().write(vals)
    if vals.get('state') == 'unavailable':
        to_confirm._action_post_confirm(vals)
    return res
```

**Behavior:** Identifies booths transitioning from `available` to `unavailable` before the write. After the write succeeds, those booths receive the booking notification. Note: if `vals` sets `state='unavailable'` but some in `to_confirm` were already `unavailable`, only the newly confirmed ones trigger the message.

#### `action_confirm(additional_values=None)`

```python
def action_confirm(self, additional_values=None):
    write_vals = dict({'state': 'unavailable'}, **(additional_values or {}))
    self.write(write_vals)
```

**Workflow entry point.** Sets `state='unavailable'` and merges any additional field values (e.g. `partner_id`). Calls `write`, which triggers `_action_post_confirm` and the confirmation message.

#### `_action_post_confirm(vals)`

```python
def _action_post_confirm(self, write_vals):
    self._post_confirmation_message()
```

Called internally after a confirmed write. Dispatches to `_post_confirmation_message`.

#### `_post_confirmation_message()`

```python
def _post_confirmation_message(self):
    for booth in self:
        booth.event_id.message_post_with_source(
            'event_booth.event_booth_booked_template',
            render_values={'booth': booth},
            subtype_xmlid='event_booth.mt_event_booth_booked',
        )
```

Posts a chatter message on the parent `event.event` record using the `event_booth_booked_template` QWeb template. The message displays the booth name (linked), the renter/partner name (linked), and if a `partner_id` is set, lists `contact_name`, `contact_email`, and `contact_phone`. Uses the `mt_event_booth_booked` mail subtype (defined in `mail_message_subtype_data.xml`, model-scoped to `event.event`).

#### `_search_is_available(operator, value)`

```python
def _search_is_available(self, operator, value):
    if operator not in ('in', 'not in'):
        return NotImplemented
    return [('state', '=', 'available' if operator == 'in' else 'unavailable')]
```

Enables domain filters like `[('is_available', '=', True)]` in the UI and action domains. Only `in`/`not in` are supported — equality operators return `NotImplemented`.

#### Computed Helpers

- `_compute_contact_name`: Sets `contact_name = partner_id.name` only if `contact_name` is currently empty.
- `_compute_contact_email`: Sets `contact_email = partner_id.email` only if empty.
- `_compute_contact_phone`: Sets `contact_phone = partner_id.phone` only if empty.
- `_compute_is_available`: `is_available = (state == 'available')`.

---

## Model: `event.booth.category`

**`_name`** = `event.booth.category`
**`_description`** = `Event Booth Category`
**`_inherit`** = `['image.mixin']`
**`_order`** = `sequence ASC`

Represents a booth tier/type (e.g. Standard Booth, Premium Booth, VIP Booth). Carries an image and HTML description for use in the website/event public pages.

### Fields

- **`name`** (Char, required, translate=True) — Display name of the booth category.
- **`sequence`** (Integer, default=10) — Controls ordering in lists. Used by the `handle` widget in the list view.
- **`description`** (Html, translate=True, `sanitize_attributes=False`) — HTML-formatted details shown on the public event page. `sanitize_attributes=False` preserves class attributes used by the Bootstrap list-group styling in demo data.
- **`active`** (Boolean, default=True) — Allows archiving categories. Archived categories are hidden from UI but remain referenced by existing booths.
- **`image_1920`**, **`image_1024`**, **`image_512`**, **`image_128`** — Inherited from `image.mixin`. Booth category images (e.g. photography of the physical booth layout).
- **`booth_ids`** (One2many to `event.booth`, inverse of `booth_category_id`) — All booths of this category. `groups='event.group_event_registration_desk'` means only registration desk users see this field on the form.

### Demo Data (noupdate)

Three categories are pre-loaded on module install:

| External ID | Name | Sequence |
|---|---|---|
| `event_booth_category_standard` | Standard Booth | 1 |
| `event_booth_category_premium` | Premium Booth | 2 |
| `event_booth_category_vip` | VIP Booth | 3 |

Standard Booth includes: 1 branded booth, 4m², 46" display screen, 1 desk, logo & link on website.
Premium adds: 50-word description on website, 10+1 passes.
VIP adds: 2 branded booths, 8m², 2x46" screens, 2 desks, 100-word description, 10+1 passes.

### Extension by `event_booth_sale`

The companion module `event_booth_sale` extends `event.booth.category` with:

- **`product_id`** (Many2one `product.product`, `domain=[('service_tracking', '=', 'event_booth')]`) — The invoicable product for this booth category.
- **`price`** (Float, computed from `product_id.list_price + product_id.price_extra`, `readonly=False`) — Can be overridden manually.
- **`price_incl`** (Float, computed incl. tax) — Price including tax.
- **`currency_id`** (Many2one, related to `product_id.currency_id`) — Pricing currency.
- **`price_reduce`** / **`price_reduce_taxinc`** (Float, computed with pricelist context) — Active price after discounts.

### Extension by `website_event_booth_sale`

Adds a `_default_product_id` method that auto-links a `product.product` with `service_tracking='event_booth'` to the category when only one such product exists.

---

## Model: `event.type.booth` (Booth Template)

**`_name`** = `event.type.booth`
**`_description`** = `Event Booth Template`

Abstract template model. Stores the default booth configuration on `event.type`. When an `event.event` is assigned an `event_type_id`, booths are generated from these templates.

### Fields

- **`name`** (Char, required, translate=True) — Template booth name, e.g. `"First Booth Alley 1"`.
- **`event_type_id`** (Many2one to `event.type`, required, cascade delete, indexed) — The event type this template belongs to. `ondelete='cascade'`: deleting the event type removes all its booth templates.
- **`booth_category_id`** (Many2one to `event.booth.category`, required, `ondelete='restrict'`) — Default category assigned to booths generated from this template.

### Methods

#### `_get_default_booth_category()`

```python
def _get_default_booth_category(self):
    category_id = self.env['event.booth.category'].search([])
    if category_id and len(category_id) == 1:
        return category_id
```

Auto-assigns the single existing booth category as default when creating a new template — reduces friction when only one category exists. Returns `False` (no default) if zero or multiple categories exist.

#### `_get_event_booth_fields_whitelist()`

```python
@api.model
def _get_event_booth_fields_whitelist(self):
    return ['name', 'booth_category_id']
```

Returns the list of fields synced from `event.type.booth` to `event.booth` when an event is created or its event type changes. Only `name` and `booth_category_id` are synced — notably **not** `event_type_id` (which is meaningless on a concrete booth).

### View Architecture

`event.type.booth` uses a two-view primary/inherited pattern to handle two contexts:

- **From `event.type` form** (`event_type_booth_view_form_from_type`, priority 32): shows only `name` + `booth_category_id` — the event type context is implicit.
- **From standalone `event.type.booth` action** (`event_type_booth_view_form`, priority 16, inherits above): prepends the `event_type_id` field so the template's parent type is visible.

---

## Model: `event.type` (Extended)

**`_name`** = `event.type`
**`_inherit`** = `event.type`

### Fields Added

- **`event_type_booth_ids`** (One2many to `event.type.booth`, `event_type_id` inverse, `store=True`) — Template booths that define the default booth layout for events using this type. `store=True` ensures the count is always computed without a dependency on the form being loaded.

### UI Placement

Rendered as a "Booths" tab (`page_booth`) on the `event.type` form view, positioned after the "Communication" tab. Uses context-aware sub-views (`list_view_ref` and `form_view_ref` pointing to the `*_from_type` variants) so the `event_type_id` field is hidden in the embedded list/form — it would be redundant since it is already set by the parent form context.

---

## Model: `event.event` (Extended)

**`_name`** = `event.event`
**`_inherit`** = `event.event`

### Fields Added

- **`event_booth_ids`** (One2many to `event.booth`, `event_id` inverse, copy=True, `compute='_compute_event_booth_ids'`, `store=True`, `precompute=True`) — All booths for this event. `copy=True` allows duplicating an event to also duplicate its booths. `store=True, precompute=True` make the field storable with early computation on creation.

- **`event_booth_count`** (Integer, computed) — Total number of booths (`available` + `unavailable`).

- **`event_booth_count_available`** (Integer, computed) — Count of booths with `state='available'`.

- **`event_booth_category_ids`** (Many2many to `event.booth.category`, computed) — All distinct categories used by this event's booths.

- **`event_booth_category_available_ids`** (Many2many to `event.booth.category`, computed) — Categories that have at least one `available` booth. Used by the website frontend to show only bookable booth types.

### `_compute_event_booth_ids`

```python
@api.depends('event_type_id')
def _compute_event_booth_ids(self):
    for event in self:
        if not event.event_type_id and not event.event_booth_ids:
            event.event_booth_ids = False
            continue

        # booths to keep: those that are not available
        booths_to_remove = event.event_booth_ids.filtered(lambda b: b.is_available)
        command = [Command.unlink(booth.id) for booth in booths_to_remove]

        if event.event_type_id.event_type_booth_ids:
            command += [
                Command.create({
                    attribute_name: line[attribute_name]
                    if not isinstance(line[attribute_name], models.BaseModel)
                    else line[attribute_name].id
                    for attribute_name in self.env['event.type.booth']._get_event_booth_fields_whitelist()
                }) for line in event.event_type_id.event_type_booth_ids
            ]
        event.event_booth_ids = command
```

**Trigger:** Only depends on `event_type_id` itself — not on any sub-fields of the event type. This deliberately mimics an `onchange` rather than a true reactive `@api.depends`. Changing template booths in `event.type` does **not** retroactively regenerate event booths.

**Sync logic:**
1. If event has no `event_type_id` and no existing booths: clear booths.
2. Remove all `available` booths (free/unconfirmed booths are treated as stale and regenerated from the type template).
3. Create new booth records from the event type's `event_type_booth_ids`, mapping `name` and `booth_category_id`. Relational fields (Many2one) are converted to IDs before `Command.create`.

**Edge case — preserving confirmed booths:** If `event_type_id` is cleared on an event that has already-confirmed (`unavailable`) booths, those booths are preserved because they are not in the `available` filter. Only the available ones are wiped.

**Edge case — new/onchange mode:** When `event_booth_ids` is computed on a new record (no `id` yet), `_get_booth_stat_count` is skipped and the count is derived directly from `event.event_booth_ids` in memory.

### `_get_booth_stat_count()`

```python
def _get_booth_stat_count(self):
    elements = self.env['event.booth'].sudo()._read_group(
        [('event_id', 'in', self.ids)],
        ['event_id', 'state'], ['__count']
    )
    elements_total_count = defaultdict(int)
    elements_available_count = dict()
    for event, state, count in elements:
        if state == 'available':
            elements_available_count[event.id] = count
        elements_total_count[event.id] += count
    return elements_available_count, elements_total_count
```

Uses a single `sudo()._read_group` query to count booths grouped by `event_id` and `state`. Runs as superuser because event kanban/list views may be accessed by users who do not have direct read access to booths. Returns two dicts mapping `event_id` → count.

---

## Security (ir.model.access.csv)

| ID | Model | Group | R | W | C | D |
|---|---|---|---|---|---|---|
| `access_event_booth_category` | `event.booth.category` | — (public) | No | No | No | No |
| `access_event_booth_category_desk` | `event.booth.category` | `event.group_event_registration_desk` | Yes | No | No | No |
| `access_event_booth_category_manager` | `event.booth.category` | `event.group_event_manager` | Yes | Yes | Yes | Yes |
| `access_event_booth_all` | `event.booth` | — (public) | No | No | No | No |
| `access_event_booth_desk` | `event.booth` | `event.group_event_registration_desk` | Yes | No | No | No |
| `access_event_booth_user` | `event.booth` | `event.group_event_user` | Yes | Yes | Yes | Yes |
| `access_event_booth_manager` | `event.booth` | `event.group_event_manager` | Yes | Yes | Yes | Yes |
| `access_event_type_booth_user` | `event.type.booth` | `event.group_event_registration_desk` | Yes | No | No | No |
| `access_event_type_booth_manager` | `event.type.booth` | `event.group_event_manager` | Yes | Yes | Yes | Yes |

**Key observations:**
- Public users have **zero access** to booth models.
- `event.group_event_registration_desk` (event user) can **read** booths but not write or create — appropriate for staff who need to see booth availability without modifying bookings.
- `event.group_event_user` can create/write booths — for staff who manage bookings.
- `event.group_event_manager` has full CRUD on all booth models.
- `event_booth_sale` (if installed) extends these permissions when linking booths to sale order lines.

---

## Mail / Chatter Integration

### Message Subtype

`mt_event_booth_booked` — defined in `mail_message_subtype_data.xml` with `res_model = 'event.event'`. This means the subtype is scoped to the event model; it appears in the event's chatter "Tracking" menu but not globally. `default=False` means it is not auto-subscribed when followers are added.

### Notification Template: `event_booth_booked_template`

A QWeb template rendered server-side via `message_post_with_source`. Displays:
- Booth name (linked to the booth record via `t-att-data-oe-model`).
- Renter type: `"booked by"` if `partner_id` exists, otherwise `"has been reserved by"` (then uses `booth.env.user.partner_id`).
- If `partner_id` exists: bullet list of `contact_name`, `contact_email`, `contact_phone`.

---

## Menu Structure

| Menuitem | Action | Parent | Groups |
|---|---|---|---|
| Booth Categories | `event_booth_category_action` | `event.menu_event_configuration` (seq 20) | — |
| Booths | `event_booth_action` | `event.menu_event_configuration` (seq 21) | `base.group_no_one` |

The "Booths" menu is hidden from all standard users (`group_no_one` effectively restricts to technical/bypass users). Booth management is primarily done via the "Booths" button on the event form, not the configuration menu.

### Event Form Integration

A stat button is added to `event.event` form (`event_event_view_form`, priority 4, inherits `event.view_event_form`). It shows:
- `event_booth_count_available / event_booth_count` (e.g. `3 / 5`) when booths exist.
- `event_booth_count` alone when count is zero (the available count span is hidden).
- Clicking opens `event_booth_action_from_event` with domain `[('event_id', '=', active_id)]`.

---

## Action Definitions

| Action ID | Model | Default View | Key Context |
|---|---|---|---|
| `event_booth_action` | `event.booth` | kanban, list, form, graph, pivot | `search_default_group_by_state: 1` |
| `event_booth_action_from_event` | `event.booth` | kanban (first), list, form | `default_event_id: active_id`, domain `event_id = active_id` |
| `event_booth_category_action` | `event.booth.category` | list, form | — |
| `event_type_booth_action` | `event.type.booth` | list, form | — |

`event_booth_action_from_event` has three explicit `ir.actions.act_window.view` records (kanban seq 1, list seq 2, form seq 3) ensuring the kanban view is always the entry point when accessed from the event form. The kanban is grouped by `state`, showing Available and Unavailable columns.

---

## Odoo 18 → 19 Changes

- **`event_booth_ids` moved from stored `One2many` to computed+stored:** In Odoo 18 the field was a plain stored `One2many`. In Odoo 19 it became `compute='_compute_event_booth_ids', store=True, readonly=False, precompute=True`. This aligns with the Odoo 19 `precompute=True` pattern for faster form loading while preserving ORM write-through when users edit the field directly.

- **`event_type_id` dependency tightening:** The `@api.depends` was changed to depend only on `event_type_id` itself rather than its sub-fields. In Odoo 18, editing template booths in `event.type` would retroactively regenerate event booths. In Odoo 19, this does not happen — the sync only triggers when the event's own `event_type_id` field changes. This is a deliberate conservative change to prevent accidental mass data mutations.

- **Optimized booth counting with `_read_group`:** The `_get_booth_stat_count` method was introduced to replace a per-record iteration pattern, using a single `sudo()._read_group` query grouped by `event_id` and `state` to populate both count fields across all events in one database round-trip.

- **Module version bump: 1.0 → 1.1.**

---

## Performance Considerations

- **`_get_booth_stat_count` with `sudo()`:** Runs as superuser because event kanban/list views may be accessed by users who do not have direct read access to booths. In multi-company or multi-record-rule environments, `sudo()` bypasses record rules — this could theoretically leak booth availability counts to unauthorized users. The risk is low since counts are aggregate and do not expose partner names, but it is worth auditing if stricter record rules are applied to booths.

- **`precompute=True` on `event_booth_ids`:** Triggers early computation on record creation before other fields are fully initialized. The `if not event.event_type_id and not event.event_booth_ids` guard handles unsaved/new records gracefully.

- **`mail_create_nosubscribe=True` on booth creation:** Prevents polluting the event's follower list with every booth creator. The booking notification posted later is the intentional subscription mechanism.

- **No computed price fields in core module:** Booth pricing is entirely delegated to `event_booth_sale`. The core module has no monetary fields, no currency handling, and no fiscal integration — keeping it lean for event-only deployments that do not sell booths.

---

## Related Modules

| Module | Relationship |
|---|---|
| `event_booth_sale` | Extends `event.booth.category` with `product_id`, `price`, `price_incl`, `price_reduce`. Links booths to sale order lines for invoicing. |
| `website_event_booth_sale` | Extends `event_booth_sale` with website booking flow, e-commerce cart, and `sale.order` integration for online booth reservations. |
| `event` | Hard dependency. Provides `event.event`, `event.type`, event stages, and `event.*` security groups. |
| `mail` | Inherited by `event.booth` via `mail.thread`. Provides chatter, subtypes, and message posting. |
| `mail_activity` | Inherited by `event.booth` via `mail.activity.mixin`. Provides activity scheduling on booths. |

---

## Field Summary by Model

### `event.booth` (core fields only)

| Field | Type | Required | Stored | Computed | Default |
|---|---|---|---|---|---|
| `name` | Char | Yes | Yes | — | — |
| `event_id` | Many2one | Yes | Yes | — | — |
| `booth_category_id` | Many2one | Yes | Yes | — | — |
| `event_type_id` | Many2one | No | Yes | — | — |
| `partner_id` | Many2one | No | Yes | — | — |
| `contact_name` | Char | No | Yes | Yes (auto-fill) | — |
| `contact_email` | Char | No | Yes | Yes (auto-fill) | — |
| `contact_phone` | Char | No | Yes | Yes (auto-fill) | — |
| `state` | Selection | Yes | Yes | — | `'available'` |
| `is_available` | Boolean | — | — | Yes | — |

### `event.booth.category` (core fields only)

| Field | Type | Required | Default |
|---|---|---|---|
| `name` | Char | Yes | — |
| `sequence` | Integer | No | 10 |
| `description` | Html | No | — |
| `active` | Boolean | No | `True` |
| `image_1920/1024/512/128` | Binary | — | from `image.mixin` |
| `booth_ids` | One2many | — | — |

### `event.type.booth`

| Field | Type | Required | Default |
|---|---|---|---|
| `name` | Char | Yes | — |
| `event_type_id` | Many2one | Yes | — |
| `booth_category_id` | Many2one | Yes | `_get_default_booth_category` |

**Tags:** `#event`, `#event_booth`, `#orm`, `#modules`

---

## L4: Constraint Analysis

### SQL Constraints

`event_booth` defines no `sql_constraints` of its own. Data integrity relies entirely on:
- ORM-level `required=True` on `event_id`, `booth_category_id`, `name`
- `ondelete='cascade'` on `event_id` (booth gone when event deleted)
- `ondelete='restrict'` on `booth_category_id` in `event.type.booth` (prevents category deletion while booths reference it)

### API Constraints (`@api.constrains`)

`event_booth` defines no `@api.constrains` methods. Validation is implicit through the state machine: booths move from `available` to `unavailable` via explicit action methods only — direct `write` calls that bypass `action_confirm` can set `state` but do not trigger the confirmation message.

### Implicit Constraints

1. **Booth name uniqueness is not enforced.** Two booths at the same event can have the same `name`. This is intentional — names like "Booth 1" are common across event types. Uniqueness is enforced at the UX level through naming conventions.

2. **No constraint on `partner_id` being a supplier.** Any `res.partner` record can be assigned to a booth. The core module makes no assumptions about partner type. `event_booth_sale` does not enforce this either.

3. **Category deletion is protected at template level only.** Deleting an `event.booth.category` record is blocked only if `event.type.booth` records reference it (`ondelete='restrict'`). Existing `event.booth` records that reference the category are not blocked — this creates orphaned booth records with `booth_category_id = NULL` if the category is manually deleted via SQL.

---

## L4: Failure Modes

Understanding how the system degrades under error conditions is critical for support and customization.

### Failure 1: Race condition on booth confirmation

**Scenario:** Two visitors select the same booth and submit simultaneously.

**Odoo 19 behavior (via `event_booth_sale`):** The `event.booth.registration` model uses a SQL unique constraint on `(sale_order_line_id, event_booth_id)`. When the first registration is created and confirmed, the second will fail at `unlink()` time because the booth is already assigned to the first confirmed registration. The `sale_order_line_id` uniqueness prevents duplicate registrations per order line, but does not prevent two different order lines from creating registrations for the same booth simultaneously.

**Mitigation:** `event_booth_sale`'s `_update_event_booths()` calls `action_confirm()` which does a `write()` on `state`. The ORM uses row-level locking in PostgreSQL when writing, so the second concurrent write will wait and then fail the `unavailable` check. In practice, this means one visitor's cart will fail at checkout with a ValidationError ("The following booths are unavailable").

**Risk level:** Medium. Checkout flow catches the error, but the user experience of reaching payment and then failing is poor.

### Failure 2: `_compute_event_booth_ids` silently removes confirmed booths

**Scenario:** An event manager changes `event_type_id` on an event that already has confirmed (unavailable) booths.

**Odoo 19 behavior:** The sync logic only removes booths where `is_available == True` (i.e., `state == 'available'`). Confirmed booths (`state == 'unavailable'`) are preserved. This is correct behavior.

**Odoo 18 behavior (pre-fix):** Before the `@api.depends` tightening, editing the template booths in `event.type` would retroactively regenerate event booths, potentially creating duplicate confirmed booths or removing availability tracking. This was a significant data integrity risk that Odoo 19's design prevents.

### Failure 3: `partner_id` cleared without state change

**Scenario:** User sets `partner_id = False` on a booth that is already `unavailable`.

**Odoo 19 behavior:** The `write()` method only triggers `_action_post_confirm` when `vals.get('state') == 'unavailable'`. Clearing `partner_id` alone does not post any message and leaves the booth in `unavailable` state. The booth remains booked but has no renter contact — a silent data inconsistency.

**Detection:** Query for `state = 'unavailable' AND partner_id IS NULL`.

**Mitigation:** Always set `state = 'available'` before clearing `partner_id`, or use `action_confirm({'partner_id': False})` to release the booth properly.

### Failure 4: `write()` ordering dependency in `action_confirm`

**Scenario:** `action_confirm(additional_values={'partner_id': some_partner, 'state': 'available'})` is called — the additional values include a conflicting `state`.

**Code behavior:**
```python
def action_confirm(self, additional_values=None):
    write_vals = dict({'state': 'unavailable'}, **(additional_values or {}))
    self.write(write_vals)
```

Because `additional_values` is merged last, if `additional_values` contains `state='available'`, it overrides the hardcoded `state='unavailable'`. The booth would be confirmed (contacts set, message posted) but remain in `available` state — a logical inconsistency.

**Risk level:** Low. No caller in the codebase passes `state` in `additional_values`. Custom integrations should be audited.

### Failure 5: `booth_category_id` orphaned on manual SQL deletion

**Scenario:** A database administrator deletes an `event.booth.category` record directly in PostgreSQL.

**Behavior:** Booth records retain their `booth_category_id` integer value (orphaned FK). Subsequent reads of those booth records will fail with a foreign key violation if the ORM tries to access the `booth_category_id` relation. This cannot happen through the Odoo UI because of the `ondelete='restrict'` on `event.type.booth`, but direct SQL bypasses this.

**Risk level:** Low but severe. Only possible via direct DB access.

---

## L4: Security Analysis

### Access Control (ir.model.access.csv)

The ACL table is defined in `security/ir.model.access.csv`. Key design decisions:

| ID | Model | Group | R | W | C | D | Design rationale |
|---|---|---|---|---|---|---|---|
| `access_event_booth_all` | `event.booth` | — (public) | 0 | 0 | 0 | 0 | Zero public access |
| `access_event_booth_desk` | `event.booth` | `event.group_event_registration_desk` | 1 | 0 | 0 | 0 | Read-only for event staff who need visibility |
| `access_event_booth_user` | `event.booth` | `event.group_event_user` | 1 | 1 | 1 | 1 | Event managers get full CRUD |
| `access_event_booth_category_all` | `event.booth.category` | — (public) | 0 | 0 | 0 | 0 | Zero public access |
| `access_event_booth_category_desk` | `event.booth.category` | `event.group_event_registration_desk` | 1 | 0 | 0 | 0 | Desk staff can view categories for booth UI |
| `access_event_booth_category_manager` | `event.booth.category` | `event.group_event_manager` | 1 | 1 | 1 | 1 | Full CRUD for category setup |

**Notable:** `event.group_event_registration_desk` (event user) has read but not write access to booths — appropriate for registration desk staff who need to see availability but should not modify bookings.

### Record Rules

The module does not define any `ir.rule` records. Record-level security for booths relies entirely on:
- `event.event` record rules (booths inherit access through `event_id`)
- If strict per-event-access is needed, a custom `ir.rule` on `event.booth` with domain `[('event_id', 'in', allowed_event_ids)]` must be added

### Potential Information Disclosure

**`_get_booth_stat_count`** runs `sudo()._read_group()`. In environments with custom record rules on `event.booth` that restrict access based on booth attributes (e.g., hiding booths for certain events), `sudo()` bypasses those rules. The method only returns aggregate counts, not record data, so the disclosure risk is limited to counts per event. However, in contexts where event existence itself is sensitive, the count could reveal information about event popularity.

**Recommendation:** If booth counts per event are sensitive, replace `sudo()` with an explicit access check using `self.env.user._is_system()` or a dedicated flag.

### Mail/Chatter Security

`message_post_with_source` is called on `booth.event_id`, posting to the event's chatter. The `mail_create_nosubscribe=True` context prevents automatic subscription of the booth creator to the event. The message is rendered server-side using the `event_booth_booked_template`, which only exposes booth and partner names — no sensitive financial data.

### Web Security

The core `event_booth` module has no HTTP routes. Security of the website-facing booth registration flow is handled by `website_event_booth` and `website_event_booth_sale`, which implement CSRF protection, email normalization, and partner lookup validation.

---

## L4: Complete Cross-Module Architecture

### Full Model Dependency Graph

```
event.event (core)
  └─ event_type_id ──────────────────────────────→ event.type (core)
       event_type_booth_ids (1) ────────────────→ event.type.booth (this module)
                                                    ├─ booth_category_id ───────→ event.booth.category (this module)
                                                    └─ event_type_id (FK, cascade)

event.event (this module, extended)
  ├─ event_booth_ids (computed, store) ─────────→ event.booth (this module)
  │   ├─ event_id (FK, cascade) ◄──────────────────┘
  │   ├─ booth_category_id ───────────────────────→ event.booth.category
  │   ├─ partner_id ─────────────────────────────→ res.partner
  │   ├─ sale_order_line_id (event_booth_sale) ───→ sale.order.line
  │   └─ sale_order_line_registration_ids ───────→ sale.order.line
  ├─ event_booth_count (computed)
  ├─ event_booth_count_available (computed)
  ├─ event_booth_category_ids (computed, M2M)
  └─ event_booth_category_available_ids (computed, M2M)

event.booth.category (this module)
  ├─ booth_ids ──────────────────────────────────→ event.booth
  ├─ product_id (event_booth_sale) ──────────────→ product.product
  └─ image_1920 (image.mixin)

sale.order.line (event_booth_sale)
  ├─ event_booth_category_id ────────────────────→ event.booth.category
  ├─ event_booth_pending_ids (M2M, computed) ─────→ event.booth
  ├─ event_booth_registration_ids (O2M) ─────────→ event.booth.registration
  └─ event_booth_ids (O2M) ──────────────────────→ event.booth

event.booth.registration (event_booth_sale)
  ├─ sale_order_line_id ─────────────────────────→ sale.order.line
  └─ event_booth_id ─────────────────────────────→ event.booth
```

### Booth Lifecycle and State Transitions

```
event_booth module (core state machine):

  CREATE booth (state=available by default)
       │
       │ action_confirm({'partner_id': partner})
       ▼
  state=unavailable ──────────────────────────────────┐
       │                                                 │
       │ Booth is released when:                         │
       │ 1. event deleted (cascade)                     │
       │ 2. sale order cancelled (event_booth_sale)     │
       │ 3. manual write({'state': 'available'})        │
       ▼                                                 │
  state=available ◄─────────────────────────────────────┘

event_booth_sale module (confirmation from cart):

  Cart line created
    → event_booth_registration records created
    → booths remain state=available (tentative reservation)
         │
         │ SO confirmed OR payment received
         ▼
    event_booth_registration.action_confirm()
      → booth.action_confirm({'partner_id': partner, ...})
      → state=unavailable
      → _cancel_pending_registrations()
           → Other orders that booked the same booth → cancelled
```

### Key Integration Hooks

| Hook | Location | What it does | When triggered |
|---|---|---|---|
| `action_confirm()` | `event.booth` | Sets `state='unavailable'`, posts chatter message | External (website, manual) |
| `_post_confirmation_message()` | `event.booth` | Renders `event_booth_booked_template` to event chatter | After confirmed write |
| `_compute_event_booth_ids()` | `event.event` | Syncs booths from `event.type.booth` templates | `event_type_id` changes |
| `_get_event_booth_fields_whitelist()` | `event.type.booth` | Returns `['name', 'booth_category_id']` | During booth creation from template |
| `event_booth_registration.action_confirm()` | `event_booth_sale` | Confirms booth + cancels conflicting carts | SO confirmation / payment |

---

## L4: Complete Workflow Trigger Reference

Every code path that changes booth state, and the side effects at each step.

### Path 1: Manual confirmation from event form

```
User clicks "Confirm" button on event.booth form
  → calls booth.action_confirm({'partner_id': id})
    → write({'state': 'unavailable', 'partner_id': id})
      → ORM sets state
      → write() detects state transition
        → _action_post_confirm(vals)
          → _post_confirmation_message()
            → event.message_post_with_source(
                'event_booth.event_booth_booked_template',
                subtype='event_booth.mt_event_booth_booked')
```

### Path 2: Website registration (website_event_booth)

```
Visitor POSTs to /event/<slug>/booth/confirm
  → controller._check_booth_registration_values()  [validates availability, email]
  → controller._prepare_booth_registration_partner_values()  [resolves partner]
  → booths.action_confirm(booth_values)
    [same as Path 1 above]
  → returns JSON success
```

### Path 3: Cart checkout (website_event_booth_sale)

```
Visitor adds booth to cart → sale order line created
  → event_booth_registration records created (tentative)
  → booths remain state=available

Visitor completes checkout
  → sale.order.action_confirm()
    → sale.order.line._update_event_booths()
      → event_booth_registration_ids.sudo().action_confirm()
        → booth.action_confirm({'partner_id': partner, ...})
        → _cancel_pending_registrations()
             [other carts with same booth → cancelled]
```

### Path 4: Booth regeneration from event type change

```
User changes event_type_id on event.event
  → _compute_event_booth_ids() triggered (depends only on event_type_id)
    → booths_to_remove = event_booth_ids.filtered(lambda b: b.is_available)
    → Command.unlink() removes available booths only
    → Command.create() creates new booths from type template
    [Confirmed/unavailable booths preserved]
```

### Path 5: Booth creation (initial, no type)

```
User clicks "Create" on event.booth list
  → booth created with state='available' by default
  → create() with mail_create_nosubscribe
    → if state already 'unavailable' → _post_confirmation_message()
    [No message for newly created available booths]
```

---

## L4: Odoo 18 → 19 Deep Dive

### Full Change Analysis

#### Change 1: `_compute_event_booth_ids` design rationale

**Odoo 18 (pre-19):**
```python
@api.depends('event_type_id', 'event_type_id.event_type_booth_ids',
             'event_type_id.event_type_booth_ids.name',
             'event_type_id.event_type_booth_ids.booth_category_id')
def _compute_event_booth_ids(self):
    # Would re-run whenever ANY sub-field of event_type_id changed
```

**Odoo 19 (current):**
```python
@api.depends('event_type_id')  # Only depends on the FK itself
def _compute_event_booth_ids(self):
    # Sync only when event_type_id assignment changes
```

**Why this matters:** In Odoo 18, an event manager editing template booth names in `event.type` would retroactively regenerate booths on every event that used that type. In practice, this caused booths to be silently recreated with new names even if existing booths had been confirmed — a destructive, silent bug. Odoo 19's design makes the sync one-directional only at event type assignment time.

#### Change 2: Introduction of `precompute=True`

The `precompute=True` attribute on `event_booth_ids` tells the ORM to compute this field as early as possible during `create()` — before the full record is initialized. This enables:
- Booth IDs to be available for `onchange` handlers during form creation
- Faster form rendering (booths shown immediately without deferred computation)

The guard `if not event.event_type_id and not event.event_booth_ids` specifically handles the new-record case where neither `event_type_id` nor existing booths are set.

#### Change 3: `Command.create` with relational field conversion

```python
for attribute_name in self.env['event.type.booth']._get_event_booth_fields_whitelist():
    value = line[attribute_name]
    if not isinstance(value, models.BaseModel):
        attribute_value = value  # primitive: Char, Integer
    else:
        attribute_value = value.id  # Many2one: extract the ID
```

This pattern is required because `Command.create()` does not accept unsaved model instances — only plain dicts with primitive values or ID integers. If a Many2one field is passed as an unsaved record, the ORM raises a validation error.

#### Change 4: `_get_booth_stat_count` with `sudo()._read_group`

The method uses `sudo()` because event kanban views (which show `event_booth_count` and `event_booth_count_available`) may be accessed by users with `event.group_event_registration_desk` permissions — who do not have direct read access to `event.booth` records.

The `defaultdict(int)` pattern for `elements_total_count` ensures events with zero booths still get a count of 0 (rather than being absent from the dict). Without this, events without booths would show `False` in the stat button.

### Odoo 19 Specific ORM Patterns Used

| Pattern | Where used | Why |
|---|---|---|
| `store=True, compute='...' ` | `event_booth_ids`, contact fields | Persist computed values in DB |
| `precompute=True` | `event_booth_ids` | Early field initialization on create |
| `readonly=False` on computed | `event_booth_ids` | Allow ORM write-through after compute |
| `Command` list | `_compute_event_booth_ids` | Atomic batch of create/unlink operations |
| `defaultdict` | `_get_booth_stat_count` | Zero-fill missing keys |
| `filtered()` | Multiple methods | Functional filtering without loop index management |
| `@api.depends` on FK only | `_compute_event_booth_ids` | Deliberate narrow dependency for conservative sync |

---

## L4: Test Coverage Analysis

### Test Files

| File | Purpose | Key coverage |
|---|---|---|
| `tests/common.py` | Shared `TestEventBoothCommon` base class | Creates 2 booth categories |
| `tests/test_event_booth_internals.py` | Core booth behavior | Contact auto-fill, partial contact update, partner overwrite |
| `tests/test_event_internals.py` | Event-type sync | Booth generation from type, type switching with confirmed booths preserved |

### Covered Scenarios

| Test | File | Scenario |
|---|---|---|
| `test_event_booth_contact` | `test_event_booth_internals.py` | Auto-fill contact from partner on create; partial update preserves existing; switching partner doesn't wipe already-set contact fields |
| `test_event_configuration_booths_from_type` | `test_event_internals.py` | No booths from type-without-booths; manual booth creation; partner write doesn't affect availability; state change affects availability; confirmed booths preserved on type change |

### Uncovered Scenarios (gaps for custom extensions)

1. **Concurrent confirmation:** No test for two simultaneous `action_confirm` calls on the same booth.
2. **`is_available` search operator edge cases:** `_search_is_available` only supports `in`/`not in` — no test for unexpected operators returning `NotImplemented`.
3. **Category deletion with active booths:** `ondelete='restrict'` on template but not on concrete booths — no test for the orphan scenario.
4. **`write()` ordering in `action_confirm`:** No test for passing `state` in `additional_values`.
5. **Message posting on bulk confirmation:** `_post_confirmation_message` iterates per-booth — no test for a single `message_post` with multiple booths in a loop.

---

**Tags:** `#event`, `#event_booth`, `#orm`, `#modules`
