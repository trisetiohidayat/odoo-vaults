---
Module: event_booth
Version: Odoo 18
Type: Business
Tags: [odoo, odoo18, event, booth, sponsor, event-management]
RelatedModules: [event]
---

# event_booth — Event Booth & Sponsor Management

> Manages individual booths, booth categories, and booth reservations within events. Used by event organizers to sell/rent physical or virtual booth spaces to sponsors and exhibitors.

**Depends:** `event`
**Category:** Marketing/Events
**Version:** 1.1

---

## Overview

`event_booth` provides a complete booth management system for events. It supports:
- Defining booth templates at the **event type** (template) level
- Instantiating booths at the **event** level
- Assigning booths to partners (sponsors/renters) with contact tracking
- Workflow: available → unavailable (booked/confirmed)
- Mail tracking and activity logging per booth

The booth model inherits from `event.type.booth` (a mixin/template class) and adds event-specific fields and workflow methods.

---

## Models

### `event.booth.category` — Booth Type Master Data

Master data for booth categories (e.g., "Gold Sponsor", "Silver Booth", "Startup Table"). Lives independently of any specific event — reusable across all events.

```python
class EventBoothCategory(models.Model):
    _name = 'event.booth.category'
    _description = 'Event Booth Category'
    _inherit = ['image.mixin']
    _order = 'sequence ASC'
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean (default=True) | Archive/restore categories |
| `name` | Char (required, translate=True) | Category display name |
| `sequence` | Integer (default=10) | Sort order in lists |
| `description` | Html (translate=True, sanitize_attributes=False) | Rich description for website/portal display |
| `booth_ids` | One2many `event.booth` (inverse) | All booths using this category |

#### Inherited (via `image.mixin`)

| Field | Type | Description |
|-------|------|-------------|
| `image_128` | Binary | Small image (128px) for category thumbnails |
| `image_256` | Binary | Medium image (256px) |
| `image_512` | Binary | Large image (512px) |
| `image_1024` | Binary | Extra-large image (1024px) |

#### Notes

- `booth_ids` is a virtual inverse — categories are not required to know their booths for filtering; the booth's `booth_category_id` is the forward link.
- `description` uses `sanitize_attributes=False` to allow rich formatting in published pages.
- Booth categories are used to drive availability checks (`event_booth_category_available_ids`) on the event.

---

### `event.type.booth` — Booth Template (Event Type Level)

Abstract-ish template class that defines what fields a booth needs. It is the `_inherits` source for `event.booth` and is also stored as `event_type_booth_ids` on `event.type`.

```python
class EventBooth(models.Model):
    _name = 'event.type.booth'
    _description = 'Event Booth Template'
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required, translate=True) | Booth name within the event type template |
| `event_type_id` | Many2one `event.type` (ondelete=cascade, required) | Parent event type |
| `booth_category_id` | Many2one `event.booth.category` (ondelete=restrict, required) | Category for default pricing/description |

#### Methods

**`_get_default_booth_category()`**
If only one booth category exists in the system, auto-assigns it as the default for new template lines.

**`_get_event_booth_fields_whitelist()`**
Returns `['name', 'booth_category_id']` — the set of fields synchronized from `event.type.booth` to `event.booth` when an event type is applied to an event.

#### Synchronization Logic

When `event_id.event_type_id` is set/changed:
1. All `available` booths on the event are removed (`Command.unlink`)
2. All `event.type.booth` lines are copied as new `event.booth` records
3. Only `name` and `booth_category_id` are copied (no partner_id, no state)
4. This emulates an onchange — event type changes propagate booth templates, but booked booths (unavailable) are preserved

---

### `event.booth` — Individual Booth

Core model. Represents a single booth instance within a specific event. Inherits from `event.type.booth` (mixin) plus `mail.thread` and `mail.activity.mixin`.

```python
class EventBooth(models.Model):
    _name = 'event.booth'
    _description = 'Event Booth'
    _inherit = [
        'event.type.booth',   # provides name, booth_category_id
        'mail.thread',
        'mail.activity.mixin'
    ]
```

#### Fields

**Ownership**

| Field | Type | Description |
|-------|------|-------------|
| `event_type_id` | Many2one (ondelete=set null, required=False) | From `event.type.booth` — parent type (may be null on manually-created booths) |
| `event_id` | Many2one `event.event` (ondelete=cascade, required) | The event this booth belongs to |

**Customer / Renter**

| Field | Type | Description |
|-------|------|-------------|
| `partner_id` | Many2one `res.partner` (tracking=True) | The sponsor/renter assigned to this booth |
| `contact_name` | Char (computed, store=True, readonly=False) | Auto-filled from `partner_id.name` if empty |
| `contact_email` | Char (computed, store=True, readonly=False) | Auto-filled from `partner_id.email` if empty |
| `contact_phone` | Char (computed, store=True, readonly=False) | Auto-filled from `partner_id.phone` or `mobile` if empty |

**State**

| Field | Type | Description |
|-------|------|-------------|
| `state` | Selection (default=`available`, required, tracking=True) | `available` = free; `unavailable` = booked/confirmed |
| `is_available` | Boolean (computed, searchable) | `True` if `state == 'available'` |

#### State Machine

```
available ──────────────────► unavailable
   │                                ▲
   │   (action_confirm called       │
   │    or partner_id assigned      │
   │    or write state='unavailable')│
   └────────────────────────────────┘
     (write state='available')
```

**Computed Fields:**
- `_compute_contact_name()` → `partner_id.name` if empty
- `_compute_contact_email()` → `partner_id.email` if empty
- `_compute_contact_phone()` → `partner_id.phone` or `mobile` if empty
- `_compute_is_available()` → `state == 'available'`

**Search Method:**
- `_search_is_available()` → converts domain `is_available = True` to `state = 'available'`

#### Key Methods

**`create(vals_list)`**
- Calls `super()` with `mail_create_nosubscribe=True` (no auto-follow on creation)
- For booths created with `state='unavailable'`: immediately calls `_post_confirmation_message()`

**`write(vals)`**
```python
def write(self, vals):
    to_confirm = self.filtered(lambda b: b.state == 'available')

    # Track partner changes for message subscribe/unsubscribe
    wpartner = dict((booth, booth.partner_id.ids) for booth in self.filtered(lambda b: b.partner_id))

    res = super().write(vals)

    # Subscribe new partner to booth chatter
    if vals.get('state') == 'unavailable' or vals.get('partner_id'):
        for booth in self:
            booth.message_subscribe(booth.partner_id.ids)

    # Unsubscribe old partners
    for booth in self:
        if wpartner.get(booth) and booth.partner_id.id not in wpartner[booth]:
            booth.message_unsubscribe(wpartner[booth])

    # Post confirmation message for newly unavailable booths
    if vals.get('state') == 'unavailable':
        to_confirm._action_post_confirm(vals)

    return res
```

**`action_confirm(additional_values=None)`**
Convenience method — sets state to `unavailable` and optionally applies extra values:
```python
def action_confirm(self, additional_values=None):
    write_vals = dict({'state': 'unavailable'}, **additional_values or {})
    self.write(write_vals)
```

**`_action_post_confirm(vals)`**
Calls `_post_confirmation_message()` — posts a mail.message to the event using template `event_booth.event_booth_booked_template` with subtype `event_booth.mt_event_booth_booked`.

**`_post_confirmation_message()`**
Posts to `booth.event_id` using `message_post_with_source()`:
```python
booth.event_id.message_post_with_source(
    'event_booth.event_booth_booked_template',
    render_values={'booth': booth},
    subtype_xmlid='event_booth.mt_event_booth_booked',
)
```

---

### `event.type` — Extended

```python
class EventType(models.Model):
    _inherit = 'event.type'
```

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `event_type_booth_ids` | One2many `event.type.booth` | Booth template lines for this event type |

Each `event.type.booth` line defines one booth template (name + booth_category_id).

---

### `event.event` — Extended

```python
class Event(models.Model):
    _inherit = 'event.event'
```

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `event_booth_ids` | One2many `event.booth` (compute + store) | All booths on this event; auto-synced from type on change |
| `event_booth_count` | Integer (computed) | Total number of booths |
| `event_booth_count_available` | Integer (computed) | Number of available (unbooked) booths |
| `event_booth_category_ids` | Many2many `event.booth.category` (computed) | All categories with booths on this event |
| `event_booth_category_available_ids` | Many2many `event.booth.category` (computed) | Categories with at least one available booth (for frontend filtering) |

#### Booth Synchronization (`_compute_event_booth_ids`)

Triggered by: `event_type_id` change only.

```
On event_type_id change:
  1. Remove all available booths (keep unavailable = booked ones)
  2. Create new booths from event_type.event_type_booth_ids
     using only name + booth_category_id from template
```

This means switching an event's type will clear any unbooked booths but preserve already-booked ones.

#### Count Computation (`_get_booth_stat_count`)

Uses `sudo()._read_group` on `event.booth`:
- Groups by `event_id` and `state`
- Returns two dicts: `available_count` and `total_count` per event
- Optimized for batch (all events loaded together) vs. onchange (single event)

---

## L4: Booth Pricing

Pricing is **not** managed within `event_booth` itself. The module does not define price fields. Pricing is typically handled in one of two ways:

1. **Manual quotation:** Sales team creates a sale order or quotation referencing the booth
2. **event_sale integration:** When `event_sale` is installed, booths can be associated with products and sold through the e-commerce flow

The `booth_category_id` links to `event.booth.category`, which can hold description and image data. Price is derived from the associated product in a sale order, not from the booth itself.

---

## L4: Partner Assignment Flow

When a booth is assigned to a partner:

```
Partner selected (e.g., via website or backend form)
         │
         ▼
booth.write({'partner_id': partner})
         │
         ├── contact_name/email/phone auto-filled from partner
         ├── message_subscribe(partner.ids) ──► partner follows booth chatter
         └── state remains 'available'
                  OR
         ▼
action_confirm() called (or state set to 'unavailable')
         │
         ├── state = 'unavailable'
         ├── message_subscribe(partner.ids) (if not already)
         └── _action_post_confirm()
                    │
                    ▼
         Mail posted to event chatter:
         "Booth [name] has been booked by [partner name]"
```

---

## L4: Booth Availability for Frontend

The computed fields `event_booth_category_ids` and `event_booth_category_available_ids` are the primary interface for website/event portal queries. They enable:

- Displaying only booth categories that actually have booths at the event
- Graying out categories where all booths are booked
- Filtering the booth selection widget to only show available booths

The `is_available` computed/searchable field allows standard Odoo domain filtering: `[('is_available', '=', True)]`.

---

## Mail/Chatter Integration

All booths inherit `mail.thread` — every booth record has its own chatter thread. The confirmation message is posted to the **parent event's** chatter (via `event_id.message_post_with_source()`), not to the booth's own thread.

Mail templates:
- `event_booth.event_booth_booked_template` — rendered with `booth` render value
- `event_booth.mt_event_booth_booked` — mail.message.subtype for the notification

Activity mixin is available for follow-up tasks on booths (e.g., "Send contract", "Confirm payment").

---

## Security

| Model | Access Group |
|-------|-------------|
| `event.booth` | `event.group_event_registration_desk` |
| `event.booth.category` | (standard event access) |
| `event.type.booth` | (standard event access) |

## Demo Data

- `data/event_booth_demo.xml` — sample booths
- `data/event_type_demo.xml` — event type with booth templates
- `data/event_booth_category_data.xml` — sample categories
