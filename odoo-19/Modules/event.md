---
type: module
module: event
tags: [odoo, odoo19, event, registration, ticket, attendance, badges, ical, mail-scheduler, seats-availability]
created: 2026-04-06
updated: 2026-04-11
---

# Event Module (`event`)

**Module:** `event`
**Path:** `odoo/addons/event/`
**Version:** 1.9 (Odoo 19)
**Category:** Marketing/Events
**Depends:** `barcodes`, `base_setup`, `mail`, `phone_validation`, `portal`, `utm`
**License:** LGPL-3

Complete event management with registration tracking, ticket types, multi-slot events, automated email scheduling, badge printing, question/answer surveys, and iCal export. Supports single-event and multi-slot (multi-session) formats with full attendee tracking, barcode check-in, and UTM campaign integration.

---

## Module Architecture

The module uses a **template - instance** pattern. `event.type` is a reusable event configuration template that auto-fills event fields (tickets, mail schedules, tags, questions, seats) when assigned to an `event.event`. Changes to the type after an event is created are not automatically propagated; the event must be manually re-synced.

**Load order (enforced in `models/__init__.py`):** type models first, then event models. `event.event` and `event.event.ticket` depend on type fields being already defined.

```python
# models/__init__.py — Load order is intentional
from . import event_type           # 1st: type models
from . import event_type_mail     # 2nd: type sub-models
from . import event_type_ticket   # 3rd: type ticket

from . import event_event         # 4th: event depends on type fields
from . import event_mail          # 5th: schedulers
from . import event_mail_registration
from . import event_mail_slot
from . import event_registration
from . import event_slot
from . import event_stage
from . import event_tag
from . import event_ticket
from . import mail_template
from . import res_config_settings
from . import res_partner
from . import event_question_answer
from . import event_registration_answer
from . import event_question
```

**Python dependency:** `vobject` (for iCal generation; if missing, ICS export is skipped with a `_logger.warning`).

---

## Model Inventory

| Model | Table | Purpose |
|---|---|---|
| `event.type` | `event_type` | Reusable event template |
| `event.type.ticket` | `event_type_ticket` | Ticket template within a type; also the inherited base class for `event.event.ticket` |
| `event.type.mail` | `event_type_mail` | Mail schedule template within a type |
| `event.event` | `event_event` | Concrete event instance |
| `event.event.ticket` | `event_event_ticket` | Concrete ticket; inherits all fields from `event.type.ticket` |
| `event.mail` | `event_mail` | Automated email scheduler for an event |
| `event.mail.registration` | `event_mail_registration` | Per-registration tracking (used when `interval_type='after_sub'`) |
| `event.mail.slot` | `event_mail_slot` | Per-slot tracking (used for multi-slot events with event-based schedules) |
| `event.registration` | `event_registration` | Attendee registration record |
| `event.registration.answer` | `event_registration_answer` | Attendee's answer to a question |
| `event.question` | `event_question` | Question definition (simple_choice, text_box, name, email, phone, company_name) |
| `event.question.answer` | `event_question_answer` | Suggested answer for `simple_choice` questions |
| `event.slot` | `event_slot` | Time slot within a multi-slot event |
| `event.stage` | `event_stage` | Kanban pipeline stage |
| `event.tag` | `event_tag` | Tag for categorizing events |
| `event.tag.category` | `event_tag_category` | Tag category/group |
| `res.partner` | `res_partner` | Extended with `event_count`, `static_map_url` |
| `res.config.settings` | `res_config_settings` | Event module configuration (barcode, Google Maps, sub-modules) |

---

## L1: Model-by-Model Reference

### 1. `event.tag.category`

**File:** `models/event_tag.py`

Groups event tags into named categories for organizational display in the kanban view.

```python
class EventTagCategory(models.Model):
    _name = 'event.tag.category'
    _description = "Event Tag Category"
    _order = "sequence"
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `name` | `Char` | Category name, required, translatable |
| `sequence` | `Integer` | Display ordering; default via `_default_sequence()` |
| `tag_ids` | `One2many` (`event.tag`, `category_id`) | Tags in this category |

**`_default_sequence()`** — Returns one more than the current maximum sequence. Uses a direct search rather than a stored field on `event.tag` to avoid JOIN overhead:

```python
def _default_sequence(self):
    return (self.search([], order="sequence desc", limit=1).sequence or 0) + 1
```

---

### 2. `event.tag`

**File:** `models/event_tag.py`

Individual tags attached to events for filtering and categorization.

```python
class EventTag(models.Model):
    _name = 'event.tag'
    _description = "Event Tag"
    _order = "category_sequence, sequence, id"
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `name` | `Char` | Tag name, required, translatable |
| `sequence` | `Integer` | Within-category ordering (default 0) |
| `category_id` | `Many2one` (`event.tag.category`) | Parent category, required, cascade delete, indexed |
| `category_sequence` | `Integer` (related, stored) | Mirrors `category_id.sequence`; enables cross-category sorting without JOIN |
| `color` | `Integer` | Tag color index (1-11), random default via `_default_color()` |

**Design Pattern: Stored Related for Sorting**

`category_sequence` is a stored related field that flattens the category sort into the tag table. Without it, Odoo's kanban sort on `category_sequence` would require a JOIN on `event_tag_category` for every row. By storing it directly on `event_tag`, the `_order = "category_sequence, sequence, id"` resolves as a pure index scan on `event_tag_category_sequence_idx` (or equivalent).

**`_default_color()`** — Returns a random integer 1-11 (inclusive). Assigned once at creation and persists because the field is not computed:

```python
def _default_color(self):
    return randint(1, 11)
```

Color 0 (the default for the `color` `Integer` field) means tags are internal and not displayed in kanban/front-end.

---

### 3. `event.type`

**File:** `models/event_type.py`

Reusable event template. When `event_type_id` is assigned to an `event.event`, tickets, mail schedules, tags, seats, timezone, and questions are auto-populated from the type. Field synchronization is implemented via `depends('event_type_id')` compute fields.

```python
class EventType(models.Model):
    _name = 'event.type'
    _description = 'Event Template'
    _order = 'sequence, id'
```

**Fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `Char` | required | Template name, translatable |
| `note` | `Html` | — | Internal notes; not synced to events |
| `sequence` | `Integer` | 10 | Ordering |
| `event_type_ticket_ids` | `One2many` | — | Ticket templates |
| `tag_ids` | `Many2many` | — | Default tags |
| `has_seats_limitation` | `Boolean` | — | Whether to limit seats |
| `seats_max` | `Integer` | computed | Maximum registrations; 0 if `has_seats_limitation=False` |
| `default_timezone` | `Selection` | `user.tz or 'UTC'` | Default display timezone |
| `event_type_mail_ids` | `One2many` | `_default_event_mail_type_ids()` | Mail schedule templates |
| `ticket_instructions` | `Html` | — | Text printed on tickets |
| `question_ids` | `Many2many` | `_default_question_ids()` | Default registration questions |

**Default Mail Schedules (`_default_event_mail_type_ids`):**

Creates three default mail schedules when a new event type is created:

| # | `interval_type` | `interval_nbr` | `interval_unit` | Template |
|---|---|---|---|---|
| 1 | `after_sub` | 0 | `now` | `event.event_subscription` (immediate on registration) |
| 2 | `before_event` | 1 | `hours` | `event.event_reminder` (1 hour before) |
| 3 | `before_event` | 3 | `days` | `event.event_reminder` (3 days before) |

**`_compute_seats_max()`** — Sets `seats_max` to 0 when `has_seats_limitation` is `False`. This is a stored computed (not just `default`): when a user checks `has_seats_limitation`, the `seats_max` value is immediately persisted and editable. When unchecked, `seats_max` is forced to 0:

```python
@api.depends('has_seats_limitation')
def _compute_seats_max(self):
    for template in self:
        if not template.has_seats_limitation:
            template.seats_max = 0
```

**`_default_question_ids()`** — Searches for all `event.question` records where `is_default=True` and `active=True`. Called both from `event.type.question_ids` default and from `event.event._compute_question_ids()` when no type is set and no answers exist.

---

### 4. `event.type.ticket`

**File:** `models/event_type_ticket.py`

Ticket template defined within an event type. Also the base class (via `_inherit`) for `event.event.ticket`. Shares all field definitions and `_get_event_ticket_fields_whitelist()`.

```python
class EventTypeTicket(models.Model):
    _name = 'event.type.ticket'
    _description = 'Event Template Ticket'
    _order = 'sequence, name, id'
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `sequence` | `Integer` | Display order (default 10) |
| `name` | `Char` | Ticket name; defaults to `_('Registration')` |
| `description` | `Text` | Ticket description shown to customers |
| `event_type_id` | `Many2one` (`event.type`) | Parent type, cascade delete |
| `seats_limited` | `Boolean` (computed, stored, readonly) | True if `seats_max > 0` |
| `seats_max` | `Integer` | Maximum tickets; 0 = unlimited |

**`_compute_seats_limited()`** — Stored computed field that evaluates `seats_max > 0`. Stored so that `event.event.ticket` (which inherits this field) can reference it without recomputing from the base `seats_max` on each read:

```python
@api.depends('seats_max')
def _compute_seats_limited(self):
    for ticket in self:
        ticket.seats_limited = ticket.seats_max
```

Note: `seats_limited` is a boolean where `seats_limited=True` means seats are capped. The inversion (True = limited) mirrors `has_seats_limitation` on `event.type`.

**`_get_event_ticket_fields_whitelist()`** — Returns the list of fields copied from `event.type.ticket` to `event.event.ticket` when syncing from type:

```python
@api.model
def _get_event_ticket_fields_whitelist(self):
    return ['sequence', 'name', 'description', 'seats_max']
```

Notably absent from the whitelist: `event_type_id` (cleared), `start_sale_datetime`, `end_sale_datetime`, `limit_max_per_order`, `color`. Those are event-specific and must be set manually.

**L4: `event.type.ticket` is a Shared Base Class**

`event.type.ticket` is not only a template model — it is the **single Python class** that serves as the base for both template and concrete tickets. `event.event.ticket` inherits it with `_inherit = ['event.type.ticket']`. This means:

- The `_get_event_ticket_fields_whitelist()` whitelist method is defined on `event.type.ticket` and called from both contexts
- `seats_limited` is a stored computed on `event.type.ticket` so that `event.event.ticket` can reference it without recomputing from `seats_max` on every read
- `limit_max_per_order` is defined on `event.event.ticket` only — it is not in the whitelist and is not synced from type

---

### 5. `event.type.mail`

**File:** `models/event_type_mail.py`

Mail schedule template within an event type. Copied to `event.mail` records when the type is assigned.

```python
class EventTypeMail(models.Model):
    _name = 'event.type.mail'
    _description = 'Mail Scheduling on Event Category'
```

**Fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `event_type_id` | `Many2one` | required | Parent type |
| `interval_nbr` | `Integer` | 1 | Interval quantity |
| `interval_unit` | `Selection` | `'hours'` | `now`, `hours`, `days`, `weeks`, `months` |
| `interval_type` | `Selection` | `'before_event'` | Trigger type |
| `notification_type` | `Selection` (computed) | `'mail'` | Currently only mail |
| `template_ref` | `Reference` | required | Reference to `mail.template` |

**Interval Units:**

| Unit | Semantics |
|---|---|
| `now` | Send immediately (used with `after_sub` only) |
| `hours` | N hours before/after trigger |
| `days` | N days before/after trigger |
| `weeks` | N weeks before/after trigger |
| `months` | N months before/after trigger |

**Trigger Types:**

| Type | Description |
|---|---|
| `after_sub` | Per-registration; a `event.mail.registration` tracks each attendee |
| `before_event` | N units before `event_id.date_begin` |
| `after_event_start` | N units after `event_id.date_begin` |
| `after_event` | N units after `event_id.date_end` |
| `before_event_end` | N units before `event_id.date_end` |

**`_prepare_event_mail_values()`** — Returns a dict suitable for `event.mail` creation:

```python
def _prepare_event_mail_values(self):
    self.ensure_one()
    return {
        'interval_nbr': self.interval_nbr,
        'interval_unit': self.interval_unit,
        'interval_type': self.interval_type,
        'template_ref': '%s,%i' % (self.template_ref._name, self.template_ref.id),
    }
```

---

### 6. `event.event`

**File:** `models/event_event.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`
**Order:** `date_begin, id`
**Key constant:** `EVENT_MAX_TICKETS = 30`

The central model. Every field from the event type is either copied at type assignment time (via compute fields with `depends('event_type_id')`) or manually overridden.

#### Fields

**Identity & Organization:**

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `Char` | required | Event title, translatable |
| `note` | `Html` | computed | Internal notes; synced from type if empty |
| `description` | `Html` | `_default_description()` | Public description |
| `active` | `Boolean` | `True` | Archive control |
| `user_id` | `Many2one` | `env.user` | Responsible user, tracked |
| `company_id` | `Many2one` | `env.company` | Owning company |
| `organizer_id` | `Many2one` | `company.partner_id` | Organizer contact, tracked |
| `event_type_id` | `Many2one` | — | Template; changing triggers field sync |

**Kanban Pipeline:**

| Field | Type | Default | Description |
|---|---|---|---|
| `stage_id` | `Many2one` (`event.stage`) | `_get_default_stage_id()` | Pipeline stage, tracked |
| `kanban_state` | `Selection` | `'normal'` | `normal`, `done`, `blocked`, `cancel`; computed reset on stage change |

**Type-synced Fields (all `store=True, readonly=False`):**

| Field | Sync Logic |
|---|---|
| `seats_max` | Copied from type; 0 if no type |
| `seats_limited` | Synced from type's `has_seats_limitation` |
| `event_mail_ids` | Removes unsent schedules without registrations; adds from type |
| `tag_ids` | Only copied if event has no tags |
| `event_ticket_ids` | Removes tickets without registrations; creates new from whitelist |
| `note` | Only if empty and type has non-empty note |
| `ticket_instructions` | Only if empty and type has instructions |
| `question_ids` | Removes questions without answers; adds from type |
| `date_tz` | Inherited from type; falls back to `user.tz` or `'UTC'` |

**Seats (computed, `stored=False`):**

| Field | Type | Description |
|---|---|---|
| `seats_max` | `Integer` | If `is_multi_slots`, multiplied by `event_slot_count` |
| `seats_limited` | `Boolean` | Whether limit is enforced |
| `seats_reserved` | `Integer` | Count of `state='open'` registrations |
| `seats_used` | `Integer` | Count of `state='done'` registrations |
| `seats_taken` | `Integer` | `seats_reserved + seats_used` |
| `seats_available` | `Integer` | `max(0, seats_max - seats_taken)` |

**Multi-Slot Support:**

| Field | Type | Description |
|---|---|---|
| `is_multi_slots` | `Boolean` | Enable multiple time slots; seat/accounting shifts to slot level |
| `event_slot_ids` | `One2many` | Time slots |
| `event_slot_count` | `Integer` (computed) | Number of slots; used in seat calculations |

**Ticketing:**

| Field | Type | Description |
|---|---|---|
| `event_ticket_ids` | `One2many` | Available ticket types |
| `start_sale_datetime` | `Datetime` (computed) | Earliest `start_sale_datetime` of all tickets |
| `event_registrations_started` | `Boolean` (computed) | Current datetime >= `start_sale_datetime` (timezone-aware) |
| `event_registrations_open` | `Boolean` (computed, sudo) | Whether new registrations can be accepted |
| `event_registrations_sold_out` | `Boolean` (computed, sudo) | Whether event is fully sold |

**Date & Time:**

| Field | Type | Default | Description |
|---|---|---|---|
| `date_tz` | `Selection` | required | Display timezone |
| `date_begin` | `Datetime` | required | Event start; rounded to nearest half-hour in `default_get` |
| `date_end` | `Datetime` | required | Event end |
| `is_ongoing` | `Boolean` (computed, searchable) | — | `date_begin <= now < date_end` |
| `is_one_day` | `Boolean` (computed) | — | Same calendar day in event timezone |
| `is_finished` | `Boolean` (computed, searchable) | — | `date_end <= now` |

**Location:**

| Field | Type | Description |
|---|---|---|
| `address_id` | `Many2one` (`res.partner`) | Venue address |
| `address_search` | `Many2one` (computed+search) | Alias for address with free-text search across address fields |
| `address_inline` | `Char` (computed) | Single-line formatted venue address |
| `country_id` | `Many2one` | Related to address |
| `event_url` | `Char` | Online event URL; auto-cleared if `address_id` is set |
| `event_share_url` | `Char` (computed) | URL for sharing; fallback to `event_url`; overridable by `website_event` |

**Badge / Report:**

| Field | Type | Default | Description |
|---|---|---|---|
| `badge_format` | `Selection` | `'A6'` | Format: `A4_french_fold` (A4 foldable), `A6`, `four_per_sheet` |
| `badge_image` | `Image` | — | Badge background; max 1024x1024 px; applied to badge PDF templates |
| `ticket_instructions` | `Html` (computed, stored) | Printed on tickets; synced from type |

**Registration:**

| Field | Type | Description |
|---|---|---|
| `registration_ids` | `One2many` | Attendee registrations |
| `general_question_ids` | `Many2many` (domain) | Questions with `once_per_order=True` |
| `specific_question_ids` | `Many2many` (domain) | Questions with `once_per_order=False` |
| `question_ids` | `Many2many` | All questions; computed from type |
| `registration_properties_definition` | `PropertiesDefinition` | Schema for per-registration custom properties |

#### Computed Field Details

**`_compute_seats()` — L4 Performance Critical**

Executes a single SQL `GROUP BY` query to aggregate registration counts per state. Avoids the N+1 problem of iterating registrations in Python:

```python
@api.depends('event_slot_count', 'is_multi_slots', 'seats_max',
             'registration_ids.state', 'registration_ids.active')
def _compute_seats(self):
    # initialize to 0
    for event in self:
        event.seats_reserved = event.seats_used = event.seats_available = 0
    # aggregate via raw SQL
    if self.ids:
        query = """ SELECT event_id, state, count(event_id)
                    FROM event_registration
                    WHERE event_id IN %s AND state IN ('open', 'done') AND active = true
                    GROUP BY event_id, state """
        self.env['event.registration'].flush_model(['event_id', 'state', 'active'])
        self.env.cr.execute(query, (tuple(self.ids),))
        for event_id, state, num in self.env.cr.fetchall():
            results[event_id][state_field[state]] = num
    # compute availability
    for event in self:
        seats_max = event.seats_max * event.event_slot_count if event.is_multi_slots else event.seats_max
        if seats_max > 0:
            event.seats_available = seats_max - (event.seats_reserved + event.seats_used)
        event.seats_taken = event.seats_reserved + event.seats_used
```

The `flush_model()` calls ensure registration state is committed to the DB before the aggregate query runs. With 10,000 registrations, this remains a single indexed query.

**L4 nuances**: The `state IN ('open', 'done') AND active = true` filter means cancelled registrations (`state='cancel'`) are excluded from seat counts even if they remain in the database. This is intentional: cancelled registrations free up seats. The `active` check means soft-deleted registrations also free seats. The SQL runs on `self.ids` — if called on a recordset with no IDs (new record), the entire block is skipped and all counts stay at 0.

For multi-slot events, `seats_max` is multiplied by `event_slot_count` — this means the event-level limit applies per slot, not across all slots combined.

**`_compute_event_registrations_open()` — L4 Complexity**

All conditions for accepting new registrations must be simultaneously true:

1. `kanban_state != 'cancel'` — event not cancelled
2. `event_registrations_started` — current datetime >= earliest ticket `start_sale_datetime` (timezone-aware)
3. `date_end >= current_datetime` (compared in event timezone via `context_timestamp`)
4. `not seats_limited or not seats_max or seats_available > 0`
5. No tickets exist, OR at least one ticket with `sale_available = True`

For multi-slot events, additionally calls `_get_seats_availability()` for each slot+ticket combination, checking that at least one slot has availability for at least one non-expired, launched ticket.

**L4 edge case**: `event_registrations_open` is `compute_sudo=True` (runs as superuser) because seat availability checks require seeing all registrations regardless of access rights. The timezone comparison uses `context_timestamp` which converts naive UTC `date_end` into the event's timezone for accurate comparison against the current time.

**L4 design**: The `is_multi_slots` condition changes the check from "any saleable ticket" to "any slot+ticket combo with availability". This prevents the "Register" button from showing on multi-slot events when no slots have been created yet (`event_slot_count == 0`). The full condition for multi-slot requires: slots exist AND (no tickets OR at least one launched, non-expired ticket with slot availability).

**`_compute_event_registrations_sold_out()` — L4 Ticket-level Sold-Out Logic**

```python
event.event_registrations_sold_out = (
    (event.seats_limited and event.seats_max and not event.seats_available > 0)
    or (event.event_ticket_ids and (
        not any(availability is None or availability > 0
            for availability in event._get_seats_availability([
                (slot, ticket)
                for slot in event.event_slot_ids
                for ticket in event.event_ticket_ids
            ])
        )
        if event.is_multi_slots else
        all(ticket.is_sold_out for ticket in event.event_ticket_ids)
    ))
)
```

**L4 nuance**: For multi-slot events, `_get_seats_availability()` is called for every combination of slot and ticket, returning `None` for unconstrained or a positive integer for available seats. The `not any(availability is None or availability > 0)` expression evaluates to `True` only when every combination is sold out. For non-multi-slot events, it falls back to `all(ticket.is_sold_out for ticket in event.event_ticket_ids)`, meaning sold out only when every ticket type is sold out.

**`_get_seats_availability(slot_tickets)` — L4 Per-Combination Availability**

```python
def _get_seats_availability(self, slot_tickets):
    """ Returns a list of availabilities for each (slot, ticket) combination.
    None denotes no limit. """
    self.ensure_one()
    if not (all(len(item) == 2 for item in slot_tickets)):
        raise ValueError('Input should be a list of tuples containing slot, ticket')

    if any(slot for (slot, _ticket) in slot_tickets):
        # Bulk read registrations grouped by (slot, ticket)
        slot_tickets_nb_registrations = {
            (slot.id, ticket.id): count
            for (slot, ticket, count) in self.env['event.registration'].sudo()._read_group(
                domain=[('event_slot_id', '!=', False), ('event_id', 'in', self.ids),
                        ('state', 'in', ['open', 'done']), ('active', '=', True)],
                groupby=['event_slot_id', 'event_ticket_id'],
                aggregates=['__count']
            )
        }

    availabilities = []
    for slot, ticket in slot_tickets:
        available = None
        # Event-level constraint
        if self.seats_limited and self.seats_max:
            available = slot.seats_available if slot else self.seats_available
        # Ticket-level constraint
        if available != 0 and ticket and ticket.seats_max:
            if slot:
                ticket_available = ticket.seats_max - slot_tickets_nb_registrations.get((slot.id, ticket.id), 0)
            else:
                ticket_available = ticket.seats_available
            available = min(available, ticket_available) if available else ticket_available
        availabilities.append(available)
    return availabilities
```

**`_verify_seats_availability(slot_tickets)` — L4 Pre-registration Check**

Called before confirming a registration. Takes a list of `(slot, ticket, count)` tuples and raises `ValidationError` if any combination has insufficient seats. The `count` parameter enables checking that adding N more registrations does not overflow limits.

```python
def _verify_seats_availability(self, slot_tickets):
    self.ensure_one()
    availabilities = self._get_seats_availability([(item[0], item[1]) for item in slot_tickets])
    for (slot, ticket, count), available in zip(slot_tickets, availabilities, strict=True):
        if available is None:  # unconstrained
            continue
        if available < count:
            sold_out.append((name, count - available))
    if sold_out:
        # Raise ValidationError listing each sold-out item
```

**L4 nuance**: `strict=True` on `zip()` (Python 3.10+) ensures the lengths match — if `slot_tickets` and `availabilities` have different lengths, a `ValueError` is raised rather than silently truncating.

#### Constraints

| Constraint | Logic |
|---|---|
| `_check_slots_dates` | All slots must be within `[date_begin, date_end]` for multi-slot events |
| `_check_closing_date` | `date_end >= date_begin` |
| `_check_event_url` | If `event_url` is set, must have valid scheme + netloc |

#### Onchange Details

**`_onchange_seats_max()`** — Warning only, not a hard block. Triggers when `seats_limited=True`, `seats_max` is set, but `seats_available <= 0`. The message warns that the event will become sold out and extra registrations will remain.

**`_onchange_event_url()`** — Auto-corrects URL by prepending `https://` if scheme is missing:

```python
@api.onchange('event_url')
def _onchange_event_url(self):
    for event in self.filtered('event_url'):
        parsed_url = urlparse(event.event_url)
        if parsed_url.scheme not in ('http', 'https'):
            event.event_url = 'https://' + event.event_url
```

#### Default Values

`date_begin` rounds to the nearest half-hour to produce cleaner calendar display (e.g., 08:17 becomes 08:30, 08:37 becomes 09:00). `date_end` defaults to `date_begin + 1 day`.

---

### 7. `event.event.ticket`

**File:** `models/event_ticket.py`
**Inherits:** `event.type.ticket` (shares all fields from the base class)

```python
class EventEventTicket(models.Model):
    _name = 'event.event.ticket'
    _inherit = ['event.type.ticket']
    _description = 'Event Ticket'
    _order = "event_id, sequence, name, id"
```

**Additional Fields (event-specific):**

| Field | Type | Description |
|---|---|---|
| `event_type_id` | `Many2one` | Cleared when synced from type; `ondelete='set null'` |
| `event_id` | `Many2one` | Parent event; cascade delete, required, indexed |
| `company_id` | `Many2one` | Related to event |
| `start_sale_datetime` | `Datetime` | When ticket goes on sale |
| `end_sale_datetime` | `Datetime` | When ticket sales end |
| `is_launched` | `Boolean` (computed) | Current datetime >= `start_sale_datetime` |
| `is_expired` | `Boolean` (computed) | Current datetime > `end_sale_datetime` |
| `sale_available` | `Boolean` (computed, sudo) | `is_launched and not is_expired and not is_sold_out` |
| `registration_ids` | `One2many` | Registrations using this ticket |
| `seats_reserved` | `Integer` (computed) | `state='open'` registrations |
| `seats_used` | `Integer` (computed) | `state='done'` registrations |
| `seats_available` | `Integer` (computed) | `max(0, seats_max - seats_taken)` |
| `seats_taken` | `Integer` (computed) | `seats_reserved + seats_used` |
| `limit_max_per_order` | `Integer` | Max per order; 0=unlimited; capped at `EVENT_MAX_TICKETS` (30) |
| `is_sold_out` | `Boolean` (computed) | `seats_limited and not seats_available OR event.sold_out` |
| `color` | `Char` | CSS color for display |

**Computed Seat Aggregation** — Same single-query SQL pattern as `event.event._compute_seats()`:

```python
@api.depends('seats_max', 'registration_ids.state', 'registration_ids.active')
def _compute_seats(self):
    # Single GROUP BY query on event_registration
    # for event_ticket_id, state
    for ticket in self:
        if ticket.seats_max > 0:
            ticket.seats_available = ticket.seats_max - (ticket.seats_reserved + ticket.seats_used)
        ticket.seats_taken = ticket.seats_reserved + ticket.seats_used
```

**Constraints:**

| Constraint | Validation |
|---|---|
| `_constrains_dates_coherency` | `start_sale_datetime <= end_sale_datetime` |
| `_constrains_limit_max_per_order` | `limit_max_per_order <= seats_max`, `limit_max_per_order <= EVENT_MAX_TICKETS`, `limit_max_per_order >= 0` |

**`_get_current_limit_per_order(event_slot, event)`** — Computes the maximum purchasable quantity per order, considering both the ticket's `limit_max_per_order` and the slot/event availability. Returns a dict mapping `ticket.id` to the limit, or `{False: ...}` if called on empty recordset.

**Deletion Protection (`_unlink_except_if_registrations`)** — Raises `UserError` if any ticket being deleted has existing registrations. Prevents data loss.

---

### 8. `event.mail`

**File:** `models/event_mail.py`

Automated email scheduler for events. Replaces all legacy field-based and workflow-based email scheduling. A cron job (`event.event_mail_scheduler`) runs every 24 hours and calls `schedule_communications()`.

```python
class EventMail(models.Model):
    _name = 'event.mail'
    _rec_name = 'event_id'
    _description = 'Event Automated Mailing'
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `event_id` | `Many2one` | Parent event; cascade delete, indexed |
| `sequence` | `Integer` | Display order |
| `interval_nbr` | `Integer` | Interval quantity (default 1) |
| `interval_unit` | `Selection` | `now`, `hours`, `days`, `weeks`, `months` (default `hours`) |
| `interval_type` | `Selection` | `after_sub`, `before_event`, `after_event_start`, `after_event`, `before_event_end` |
| `scheduled_date` | `Datetime` (computed, stored) | When to send; recomputed when event dates change |
| `error_datetime` | `Datetime` | Timestamp of last error |
| `last_registration_id` | `Many2one` | Cursor for batched sending (attendee-based only) |
| `mail_registration_ids` | `One2many` | Per-registration tracking records |
| `mail_slot_ids` | `One2many` | Per-slot tracking records |
| `mail_done` | `Boolean` | Whether sent (event-based only) |
| `mail_state` | `Selection` (computed) | `running`, `scheduled`, `sent`, `error`, `cancelled` |
| `mail_count_done` | `Integer` | Number of emails sent |
| `notification_type` | `Selection` (computed) | Always `mail` |
| `template_ref` | `Reference` | `mail.template` reference; cascade delete |

**`_compute_scheduled_date()` — L4 Date Computation**

The scheduled date is computed from the trigger type and interval:

| `interval_type` | Base date | Sign |
|---|---|---|
| `after_sub` | `event_id.create_date` | +1 |
| `before_event` | `event_id.date_begin` | -1 |
| `after_event_start` | `event_id.date_begin` | +1 |
| `after_event` | `event_id.date_end` | +1 |
| `before_event_end` | `event_id.date_end` | -1 |

After computing, it triggers the cron to wake up earlier if the new `scheduled_date` is sooner than the current nextcall.

**`_compute_mail_state()` — L4 State Machine**

```python
def _compute_mail_state(self):
    for scheduler in self:
        if scheduler.error_datetime:
            scheduler.mail_state = 'error'
        elif not scheduler.mail_done and scheduler.event_id.kanban_state == 'cancel':
            scheduler.mail_state = 'cancelled'
        elif scheduler.interval_type == 'after_sub':
            scheduler.mail_state = 'running'
        elif scheduler.mail_done:
            scheduler.mail_state = 'sent'
        else:
            scheduler.mail_state = 'scheduled'
```

**L4 nuance**: For `interval_type='after_sub'`, the state is always `'running'` because each new registration triggers a new `event.mail.registration` record. For event-based types, once `mail_done=True` the state becomes `'sent'` permanently.

**Cron Search Domain (`schedule_communications()`):**

```python
schedulers = self.search([
    ('event_id.active', '=', True),       # skip archived events
    ('event_id.kanban_state', '!=', 'cancel'),  # skip cancelled
    ('scheduled_date', '<=', Datetime.now()),    # due now
    ('mail_done', '=', False),            # not already sent
    '|',
        ('interval_type', '!=', 'after_sub'),  # event-based
        ('event_id.date_end', '>', cr.now())   # attendee-based: only while event is ongoing
])
```

**L4 nuance**: The `interval_type != 'after_sub'` OR `date_end > now` condition prevents the `after_sub` scheduler from running indefinitely after an event ends. However, `mail_done=False` on `after_sub` schedulers means they remain in `'running'` state indefinitely — they do not auto-complete when the event ends.

---

### 9. `event.mail.registration`

**File:** `models/event_mail_registration.py`

Per-registration tracking record created when `interval_type='after_sub'`. One record per (scheduler, registration) pair.

```python
class EventMailRegistration(models.Model):
    _name = 'event.mail.registration'
    _description = 'Registration Mail Scheduler'
    _rec_name = 'scheduler_id'
    _order = 'scheduled_date DESC, id ASC'
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `scheduler_id` | `Many2one` | Parent `event.mail`; cascade delete |
| `registration_id` | `Many2one` | Target registration; cascade delete |
| `scheduled_date` | `Datetime` (computed, stored) | When to send: `registration.create_date + interval` |
| `mail_sent` | `Boolean` | Whether email was sent |

**`_compute_scheduled_date()`** — `registration.create_date + _INTERVALS[scheduler.interval_unit](scheduler.interval_nbr)`. For `interval_unit='now'`, the interval is `relativedelta(hours=0)` — immediately due.

**`_get_skip_domain()`** — Returns the domain for records to skip:

```python
def _get_skip_domain(self):
    return [
        ("mail_sent", "=", False),
        ("scheduled_date", "!=", False),
        ("scheduled_date", "<=", self.env.cr.now()),
    ]
```

Records are skipped if already sent, if no scheduled date, or if the scheduled date is still in the future.

---

### 10. `event.mail.slot`

**File:** `models/event_mail_slot.py`

Per-slot tracking record for multi-slot events. Created dynamically when an event-based scheduler runs against a multi-slot event.

```python
class EventMailRegistration(models.Model):  # note: class name reuse (typo in original)
    _name = 'event.mail.slot'
    _description = 'Slot Mail Scheduler'
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `event_slot_id` | `Many2one` | Target slot; cascade delete |
| `scheduler_id` | `Many2one` | Parent `event.mail`; cascade delete |
| `scheduled_date` | `Datetime` (computed, stored) | Based on slot start/end datetime |
| `last_registration_id` | `Many2one` | Cursor for batched sending |
| `mail_count_done` | `Integer` | Emails sent for this slot |
| `mail_done` | `Boolean` | Whether all slot emails are sent |

**`_compute_scheduled_date()`** — For `before_event`/`after_event_start`: uses `event_slot_id.start_datetime`. For `after_event`/`before_event_end`: uses `event_slot_id.end_datetime.

---

### 11. `event.registration`

**File:** `models/event_registration.py`

**Inherits:** `mail.thread`, `mail.activity.mixin`
**Order:** `id desc`
**Key feature:** `_mail_defaults_to_email = True` — outbound emails use the registration's email field rather than the partner's.

**Fields:**

| Field | Type | Description |
|---|---|---|
| `event_id` | `Many2one` | Parent event; required, indexed |
| `is_multi_slots` | `Boolean` (related) | Mirror of event flag |
| `event_slot_id` | `Many2one` | Selected slot; required for multi-slot events; `index='btree_not_null'` |
| `event_ticket_id` | `Many2one` | Selected ticket type; `index='btree_not_null'` |
| `active` | `Boolean` | Soft delete (default True); affects seat counts |
| `barcode` | `Char` | Auto-generated 8-byte random number; unique constraint |
| `utm_campaign_id` | `Many2one` | UTM campaign tracking |
| `utm_source_id` | `Many2one` | UTM source tracking |
| `utm_medium_id` | `Many2one` | UTM medium tracking |
| `partner_id` | `Many2one` | Booked by partner; `index='btree_not_null'` |
| `name` | `Char` | Attendee name; computed from `partner_id` if not set; trigram indexed |
| `email` | `Char` | Attendee email; computed from `partner_id` if not set; tracked |
| `phone` | `Char` | Attendee phone; computed from `partner_id` if not set; tracked |
| `company_name` | `Char` | Company; computed from `partner_id` if not set; tracked |
| `date_closed` | `Datetime` | When attendee checked in (`state='done'`); auto-set by compute |
| `event_begin_date` | `Datetime` (computed, searchable) | `event_slot_id.start_datetime` or `event_id.date_begin` |
| `event_end_date` | `Datetime` (computed, searchable) | `event_slot_id.end_datetime` or `event_id.date_end` |
| `event_date_range` | `Char` (computed) | Human-readable: "tomorrow", "in 5 days", etc. |
| `event_organizer_id` | `Many2one` (related) | Event organizer |
| `event_user_id` | `Many2one` (related) | Event responsible |
| `company_id` | `Many2one` | Event's company |
| `state` | `Selection` | `draft` (Unconfirmed), `open` (Registered), `done` (Attended), `cancel` (Cancelled) |
| `registration_answer_ids` | `One2many` | Answers to questions |
| `registration_answer_choice_ids` | `One2many` (domain) | Filtered to `question_type='simple_choice'` |
| `mail_registration_ids` | `One2many` | Mail scheduler records for this registration |
| `registration_properties` | `Properties` | Custom properties defined by event |

**State Machine:**

```
draft (Unconfirmed)
    ↓ action_confirm()
open (Registered)
    ↓ action_set_done()
done (Attended)
    ↓ (terminal)
cancel (Cancelled)
    ↓ action_set_draft()
draft
```

`draft` is a pending state used notably with sale orders where payment is not yet confirmed. Registrations in `draft` state do not count toward seat usage.

**Registration Creation Flow (`create()`):**

```python
@api.model_create_multi
def create(self, vals_list):
    # 1. Format phone numbers based on country
    for values in vals_list:
        if not values.get('phone'):
            continue
        country = ...
        values['phone'] = self._phone_format(number=values['phone'], country=country) or values['phone']
    registrations = super().create(vals_list)
    # 2. Trigger after-submit mail schedulers
    registrations._update_mail_schedulers()
    return registrations
```

**L4 nuance**: `_update_mail_schedulers()` is called after `super().create()` so that the registration record exists before the scheduler logic runs. It finds all `event.mail` records with `interval_type='after_sub'` for the same event and either triggers the cron or runs the scheduler synchronously.

**Barcode Generation (`_get_random_barcode()`)** — Generates an 8-byte random number serialized as a decimal string. Decimal serialization produces shorter barcodes (Code128C) than hexadecimal (Code128A), compatible with all scanners:

```python
def _get_random_barcode(self):
    return str(int.from_bytes(os.urandom(8), 'little'))
```

**Constraint `_check_seats_availability()`** — Fires on `create()` and `write()` when `state in ('open', 'done') and active=True`. Groups registrations by (event_slot_id, event_ticket_id) and calls `event._verify_seats_availability()` for each group. Prevents overbooking.

**Constraint `_check_event_slot()`** — Validates that `event_slot_id.event_id == event_id` and that a slot is selected on multi-slot events.

**Constraint `_check_event_ticket()`** — Validates that `event_ticket_id.event_id == event_id`.

**Kiosk Check-in (`register_attendee(barcode, event_id)`)** — The barcode scanning endpoint. Returns a status dict:

| Status | Meaning |
|---|---|
| `invalid_ticket` | Barcode not found |
| `canceled_registration` | Registration is cancelled |
| `unconfirmed_registration` | Registration is in `draft` state |
| `not_ongoing_event` | Event has finished |
| `need_manual_confirmation` | Event ID mismatch — attendee registered for different event |
| `confirmed_registration` | Successfully checked in (`action_set_done()`) |
| `already_registered` | Already marked as attended |

**`_synchronize_partner_values(partner, fnames)`** — Syncs contact fields from `partner_id`. Uses `address_get(['contact'])` to find the contact address (not the company), then reads the specified fields. This prevents copying company-level fields into individual registrations.

**Mail-related Override (`_message_add_default_recipients()`)** — Prioritizes the registration's own `email` field over the partner's email when a single partner books multiple seats. Prevents all registrations from using the same email_to when the partner is shared.

---

### 12. `event.slot`

**File:** `models/event_slot.py`

Time slot for multi-slot events. Each slot has a `date` (date only) and `start_hour`/`end_hour` (float hours in event timezone). `start_datetime`/`end_datetime` are stored computed fields converting these into UTC-aware Datetimes.

```python
class EventSlot(models.Model):
    _name = "event.slot"
    _description = "Event Slot"
    _order = "event_id, date, start_hour, end_hour, id"
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `event_id` | `Many2one` | Parent event; cascade delete, indexed |
| `color` | `Integer` | Kanban color (default 0) |
| `date` | `Date` | Slot date; required |
| `date_tz` | `Selection` (related) | Mirrors `event_id.date_tz` |
| `start_hour` | `Float` | Start hour in event timezone (0.00 - 23.99) |
| `end_hour` | `Float` | End hour in event timezone (0.00 - 23.99) |
| `start_datetime` | `Datetime` (computed, stored) | UTC datetime of slot start |
| `end_datetime` | `Datetime` (computed, stored) | UTC datetime of slot end |
| `is_sold_out` | `Boolean` (computed) | `event_id.seats_limited and not seats_available` |
| `registration_ids` | `One2many` | Registrations in this slot |
| `seats_available` | `Integer` (computed) | Remaining seats |
| `seats_reserved` | `Integer` (computed) | `open` registrations |
| `seats_used` | `Integer` (computed) | `done` registrations |
| `seats_taken` | `Integer` (computed) | `seats_reserved + seats_used` |

**`_compute_datetimes()` — L4 Timezone Conversion**

```python
@api.depends("date", "date_tz", "start_hour", "end_hour")
def _compute_datetimes(self):
    for slot in self:
        event_tz = pytz.timezone(slot.date_tz)
        start = datetime.combine(slot.date, float_to_time(slot.start_hour))
        end = datetime.combine(slot.date, float_to_time(slot.end_hour))
        slot.start_datetime = event_tz.localize(start).astimezone(pytz.UTC).replace(tzinfo=None)
        slot.end_datetime = event_tz.localize(end).astimezone(pytz.UTC).replace(tzinfo=None)
```

**L4 nuance**: The conversion strips timezone info (`replace(tzinfo=None)`) because PostgreSQL stores `Datetime` fields as naive. The event module consistently uses naive UTC datetimes internally and handles timezone display via `context_timestamp()` in computed fields and reports.

**Constraints:**

| Constraint | Validation |
|---|---|
| `_check_hours` | `0 <= start_hour <= 23.99`, `0 <= end_hour <= 23.99`, `end_hour > start_hour` |
| `_check_time_range` | `event_id.date_begin <= start_datetime <= event_id.date_end` AND same for `end_datetime` |

---

### 13. `event.stage`

**File:** `models/event_stage.py`

Kanban pipeline stages for events. Odoo ships four default stages: `New`, `Booked`, `Announced`, `Ended`.

```python
class EventStage(models.Model):
    _name = 'event.stage'
    _description = 'Event Stage'
    _order = 'sequence, name'
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `name` | `Char` | Stage name, required, translatable |
| `description` | `Text` | Stage description, translatable |
| `sequence` | `Integer` | Ordering (default 1) |
| `fold` | `Boolean` | Folded in Kanban view |
| `pipe_end` | `Boolean` | End stage; events auto-moved here when `date_end` passes |

**`_autovacuum_gc_mark_events_done()`** — Cron `event.event_autovacuum` calls `action_set_done()` on events whose `date_end` has passed and are not already in an end stage. The `pipe_end=True` stage is typically named "Ended" with `fold=True`.

---

### 14. `event.question`

**File:** `models/event_question.py`

Question definition for registration surveys.

```python
class EventQuestion(models.Model):
    _name = 'event.question'
    _rec_name = 'title'
    _order = 'sequence,id'
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `title` | `Char` | Question text, required, translatable |
| `question_type` | `Selection` | `simple_choice` (dropdown), `text_box`, `name`, `email`, `phone`, `company_name` |
| `active` | `Boolean` | Archive control (default True) |
| `event_type_ids` | `Many2many` | Event types using this question |
| `event_ids` | `Many2many` | Events using this question |
| `event_count` | `Integer` (computed) | Number of events using this question |
| `is_default` | `Boolean` | Auto-added to new events |
| `is_reusable` | `Boolean` (computed, stored) | Can be used on multiple events; always True for `is_default` |
| `answer_ids` | `One2many` | Suggested answers (simple_choice only) |
| `sequence` | `Integer` | Ordering (default 10) |
| `once_per_order` | `Boolean` | Answer is shared across all attendees in one booking |
| `is_mandatory_answer` | `Boolean` | Registration blocked if no answer |

**SQL Constraint** — `is_default=True` implies `is_reusable=True`. A question cannot be a default but non-reusable.

**Deletion Protection:**
- Cannot delete a question that has existing answers (archive instead)
- Cannot delete a question that is a default question

**Question Types L4 Semantics:**

| Type | Answer Storage | `once_per_order` typical value |
|---|---|---|
| `simple_choice` | `event.question.answer` via `value_answer_id` | Yes (order-level) or No (per-attendee) |
| `text_box` | `value_text_box` (free text) | — |
| `name` | Auto-populated from `registration.name` | — |
| `email` | Auto-populated from `registration.email` | — |
| `phone` | Auto-populated from `registration.phone` | — |
| `company_name` | Auto-populated from `registration.company_name` | — |

For `name`, `email`, `phone`, `company_name` types, the answer is automatically synced from the registration's own field — no manual input required.

---

### 15. `event.question.answer`

**File:** `models/event_question_answer.py`

Suggested answer options for `simple_choice` questions.

```python
class EventQuestionAnswer(models.Model):
    _name = 'event.question.answer'
    _order = 'sequence,id'
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `name` | `Char` | Answer text, required, translatable |
| `question_id` | `Many2one` | Parent question; cascade delete |
| `sequence` | `Integer` | Ordering (default 10) |

Deletion protection: Cannot delete an answer that has been selected by any attendee.

---

### 16. `event.registration.answer`

**File:** `models/event_registration_answer.py`

Stores each attendee's response to event questions.

```python
class EventRegistrationAnswer(models.Model):
    _name = 'event.registration.answer'
    _rec_names_search = ['value_answer_id', 'value_text_box']
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `question_id` | `Many2one` | Question; `ondelete='restrict'` |
| `registration_id` | `Many2one` | Registration; cascade delete, indexed |
| `partner_id` | `Many2one` (related) | Registration's partner |
| `event_id` | `Many2one` (related) | Registration's event |
| `question_type` | `Selection` (related) | Mirrors question type |
| `value_answer_id` | `Many2one` | Selected answer (simple_choice) |
| `value_text_box` | `Text` | Free-text answer (text_box) |

**SQL Constraint** — `value_answer_id IS NOT NULL OR COALESCE(value_text_box, '') <> ''` — at least one answer value must be provided.

**`_compute_display_name()`** — Returns `value_answer_id.name` for simple_choice, else `value_text_box`.

---

### 17. `res.partner` (extension)

**File:** `models/res_partner.py`

Extended with event-specific fields and methods.

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `event_count` | `Integer` (computed) | Number of events with registrations from this partner; restricted to `group_event_registration_desk` |
| `static_map_url` | `Char` (computed) | Google Maps signed static image URL for the partner's address |
| `static_map_url_is_valid` | `Boolean` (computed) | Whether the static map URL is accessible |

**`_compute_static_map_url()`** — Uses `_google_map_signed_img()` which requires `google_maps.signed_static_api_key` and `google_maps.signed_static_api_secret` ir.config_parameters. Returns `None` if keys are not configured.

**`_google_map_signed_img()` — L4 Google Maps Signature**

Generates a signed static map URL using the Google Maps Static API with a cryptographic signature. Steps:

1. Builds the unsigned path with location, markers, size, and zoom
2. Signs it with HMAC-SHA1 using the base64-decoded API secret
3. Appends the signature to the URL

This prevents unauthorized use of the API key. If `google_maps.signed_static_api_secret` is not valid base64, returns `None`.

**`action_event_view()`** — Returns the event action filtered to registrations where the partner is a contact or part of the partner's commercial entity (`'child_of'` domain).

---

## L2: Constraints, Defaults, and State Machine

### Seat Availability Constraints

**`event.event._check_slots_dates()`** — Multi-slot events only. Validates all slots fall within `[date_begin, date_end]`. Uses `_read_group` to find the min/max slot datetime per event in a single query.

**`event.registration._check_seats_availability()`** — Fires on create/write of registrations in `open` or `done` state. Groups by `(event_slot_id, event_ticket_id)` and calls `event._verify_seats_availability()` for each group.

**`_verify_seats_availability(slot_tickets)`** — For each `(slot, ticket, count)` combination:
- `available is None` (unconstrained): always OK
- `available >= count`: OK
- `available < count`: raises `ValidationError` listing the deficit per slot/ticket

**L4 edge case**: In multi-slot events, the same attendee can register for multiple slots. Seat counts are independent per slot — registering for slot A does not consume a seat in slot B.

### Registration State Machine

```
draft ──── action_confirm() ───→ open
                                 ↓ action_set_done()
                                 done
                                 ↓ action_cancel()
open ──── action_cancel() ────→ cancel
              ↓ action_set_draft()
             draft
```

- `draft` state does not consume seats (seat count queries filter on `state IN ('open', 'done')`)
- `cancel` state frees seats (same filter)
- `action_set_draft()` allows reopening cancelled registrations
- `action_done()` sets `date_closed` via `_compute_date_closed()`
- `_update_mail_schedulers()` is called on transition to `open` (confirming draft or reopening cancel)

### Ticket Sale Constraints

- `start_sale_datetime <= end_sale_datetime`
- `limit_max_per_order <= seats_max`
- `limit_max_per_order <= EVENT_MAX_TICKETS (30)`
- `limit_max_per_order >= 0`
- `event.event.ticket` cannot be deleted if it has registrations

---

## L3: Cross-Module Integration

### Event - Calendar

The module has no direct dependency on `calendar` (a separate `event_calendar` module handles that). However, `event.event` exposes `action_open_slot_calendar()` which opens a calendar view of `event.slot` records. The calendar is timezone-aware using `context_timestamp()` throughout.

### Event - Website

The base `event` module has no dependency on `website`. The `website_event` module (separate) adds:
- Public event pages with online registration
- Event listing and search
- Social sharing
- Live streaming
- Sponsor management
- Track/sub-session management

The `event.event` model defines `event_share_url` (computed) and `event_url` (online event link) which are consumed by `website_event`. The `event.event` also defines `use_barcode` which is `True` when `event.use_event_barcode` config parameter is set (typically by `website_event`).

### Event - Sale (event_sale module)

The base `event` module has no sale dependency. When `event_sale` is installed:
- `event.event.ticket` gains a `product_id` (linked product for e-commerce sales)
- `event.registration` creation triggers `sale.order.line` creation via the `event_sale` module
- Seat counting logic is shared — cancelled sale lines free up seats

### Event - UTM

The module explicitly depends on `utm`. Every `event.registration` tracks `utm_campaign_id`, `utm_source_id`, and `utm_medium_id` from the `utm.mixin` pattern. These are auto-populated from the context defaults when a registration is created from a website landing page or marketing campaign.

### Event - Barcode / Check-in

The module depends on `barcodes`. `event.registration` has a unique `barcode` field generated via `os.urandom(8)`. The `/event/init_barcode_interface` JSON-RPC endpoint initializes the kiosk check-in screen with event metadata. The `register_attendee()` method on `event.registration` processes barcode scans and transitions registrations to `done`.

### Event - Mail

The module depends on `mail`. All automated email is sent via `event.mail` schedulers using `mail.compose.message` in `mass_mail` composition mode. The `event.event` and `event.registration` both inherit `mail.thread` for discussion.

### Event - Portal

The module depends on `portal`. `event.registration` has `partner_id` linking to portal-accessible partner records. Portal users can view their own registrations and download badges.

### Event - Phone Validation

The module depends on `phone_validation`. `event.registration._onchange_phone_validation()` formats phone numbers based on country (partner country > event country > company country priority).

---

## L3: Override Patterns

### `event_type_id` Sync Pattern

The pattern used throughout `event.event` for syncing from type is `depends('event_type_id')` alone (not `depends('event_type_id', 'event_type_id.subfield')`). This means:

- Changing `event_type_id` to a new type triggers all sync compute methods
- Changing fields *within* the type (e.g., adding a ticket to the type) does NOT automatically update existing events — the event must be saved again or manually re-assigned

This is an intentional design: it prevents accidental data loss when a type is updated after events have already customized their configuration.

### Mail Scheduler Execution Pattern

Three execution modes based on `interval_type`:

**Attendee-based (`after_sub`):**
```
event.mail._execute_attendee_based()
  → creates event.mail.registration for each new registration
  → executes in batches (batch_size=50, cron_limit=1000)
  → commits after each batch
```

**Event-based (`before_event`, `after_event`, etc.) — single event:**
```
event.mail._execute_event_based()
  → fetches registrations in batches
  → sends mail to each batch
  → updates last_registration_id cursor
  → commits after each batch
```

**Event-based — multi-slot (`is_multi_slots=True`):**
```
event.mail._execute_slot_based()
  → creates event.mail.slot for each new slot
  → calls _execute_event_based(mail_slot=mail_slot) per slot
```

### `_action_confirm` Equivalent

The event module does not use a single `_action_confirm()`. Instead, state transitions are distributed:
- `event.registration`: `action_confirm()`, `action_set_done()`, `action_cancel()`, `action_set_draft()`
- `event.event`: `action_set_done()` moves events to the `pipe_end=True` stage
- `_autovacuum_gc_mark_events_done()` auto-transitions events to the ended stage

---

## L4: Performance Analysis

### Seats Availability Computation

**Critical path**: Reading `event.event` form view or list view triggers `_compute_seats()` on all displayed events. This runs a single `GROUP BY` SQL query per page load.

**Optimization**: The SQL query uses indexed columns `event_id`, `state`, `active` which should have indexes via the ORM's Many2one definitions. For events with 10,000+ registrations, this remains one query.

**`flush_model()` call**: Forces pending writes on `event.registration` to be flushed to the DB before the aggregate runs. Without this, in-progress transactions might see stale counts.

**Multi-slot complexity**: `_get_seats_availability()` runs a `_read_group` on `event.registration` grouped by `(event_slot_id, event_ticket_id)` for each event. With 50 slots and 5 tickets, this is 250 combinations. The `_read_group` is a single aggregated query — O(1) DB round-trips regardless of combination count.

**L4 recommendation**: For events with very high registration counts (>50,000), consider:
1. Adding a `event_id_state_active` partial index on `event_registration` filtered to `state IN ('open', 'done') AND active = true` — reduces scan size
2. Denormalizing seat counts into `event.event` via SQL triggers (advanced)

### Mass Mailing to Attendees

**`event.mail._execute_event_based_for_registrations()`** — Uses `mail.compose.message` in `mass_mail` mode, which batches rendering via `tools.split_every(batch_size, registrations)`. Default batch size is 50 (configurable via `mail.batch_size` ir.config_parameter).

**Performance knobs:**

| Parameter | Config Key | Default | Purpose |
|---|---|---|---|
| Batch size | `mail.batch_size` | 50 | Records per mail render commit |
| Cron limit | `mail.render.cron.limit` | 1000 | Max records processed per cron run |

**L4 nuance**: The cron is named `event.event_mail_scheduler` with `interval_type=hours` and `interval_number=24` (runs every 24 hours). For high-volume events, reducing `interval_number` to 1 and `interval_type` to `minutes` would make the scheduler more responsive.

**Auto-commit**: Each batch commits to the DB (`self.env.cr.commit()`), releasing locks and preventing long-running transactions. After commit, `self.env.invalidate_all()` clears the ORM cache to prevent stale reads.

**Ticket attachment generation**: If `mail.compose.message` renders QWeb templates containing ticket data, each email rendering triggers PDF generation for the badge/ticket. This is the most expensive operation. `website_event` passes `rendering_bundle=True` to avoid including all web assets in each email.

### Registration Creation

The `_check_seats_availability()` constraint runs on every `create()` and `write()` that affects `state`, `active`, `event_slot_id`, or `event_ticket_id`. In high-concurrency scenarios (e.g., multiple attendees registering simultaneously), this constraint alone does not prevent race conditions — it should be supplemented by a PostgreSQL `EXCLUDE` constraint or `SELECT FOR UPDATE` lock at the application level.

---

## L4: Odoo 18 to Odoo 19 Event Changes

### Architecture Changes

**Odoo 18**: The event module used a simpler model where `event.event` had a flat seat limit without multi-slot support. The seat management was a single-level calculation.

**Odoo 19**: Introduced multi-slot events (`is_multi_slots`) as a first-class concept. Seat management, ticket availability, and mail scheduling all have slot-aware variants.

### New Fields in Odoo 19

| Field | Model | Purpose |
|---|---|---|
| `is_multi_slots` | `event.event` | Enable multi-slot event format |
| `event_slot_ids` | `event.event` | Container for slots |
| `event_slot_count` | `event.event` | Slot count for seat calculations |
| `event.mail.slot` | (new model) | Per-slot mail tracking |
| `event_slot_id` | `event.registration` | Per-registration slot selection |
| `event_mail_slot_ids` | `event.mail` | Per-slot scheduler links |
| `registration_properties_definition` | `event.event` | Custom properties schema |
| `registration_properties` | `event.registration` | Custom properties values |
| `event_registrations_started` | `event.event` | Time-based sale gate |
| `start_sale_datetime` | `event.event.ticket` | Ticket-specific sale start |
| `is_launched` | `event.event.ticket` | Computed: sale has started |
| `limit_max_per_order` | `event.event.ticket` | Per-order quantity cap |

### Computed Field Changes

**`_compute_event_registrations_open()`** in Odoo 19 is significantly more complex than Odoo 18:
- Added `event_registrations_started` check (time-based gate)
- Added multi-slot availability checking
- Changed to `compute_sudo=True` for access control

**`_compute_seats()`** — Odoo 18 had a simpler seat count that did not handle multi-slot multiplication. Odoo 19 multiplies `seats_max * event_slot_count` for multi-slot events.

### iCal Generation

**`vobject` dependency added in Odoo 18/19**: The ICS file generation uses the `vobject` library. If missing, `_get_ics_file()` returns an empty dict and logs a warning. The ICS endpoint at `/event/<event>/ics` serves the generated file with `Content-Disposition: attachment`.

### Email Author Resolution

Odoo 19 improved the email author selection in `_send_mail()`:
```python
if self.event_id.organizer_id.email:
    author = self.event_id.organizer_id
elif self.env.company.email:
    author = self.env.company.partner_id
elif self.env.user.email:
    author = self.env.user.partner_id
else:
    author = self.env.ref('base.user_root').partner_id
```
Fallback chain: organizer > company > current user > admin.

---

## L4: Security Analysis

### Access Control Groups

| Group | Implied From | Typical Permissions |
|---|---|---|
| `event.group_event_registration_desk` | `base.group_user` | Read events, manage registrations, scan barcodes |
| `event.group_event_user` | `group_event_registration_desk` | Create/edit events, manage tickets |
| `event.group_event_manager` | `group_event_user` | Full access, delete, configure |

### Record Rules (Multi-Company)

All event models have multi-company record rules restricting access to records where `company_id` is in the user's allowed companies:

```python
# event_event_company_rule
domain_force = [('company_id', 'in', company_ids + [False])]

# event_registration_company_rule
domain_force = [('company_id', 'in', company_ids + [False])]

# ir_rule_event_event_ticket_company
domain_force = [('event_id.company_id', 'in', company_ids + [False])]
```

**L4 nuance**: `+ [False]` allows records with no company (NULL `company_id`) to be accessible by all users. This is intentional for shared/public events.

### Public Event Access

`event.event` does not inherently restrict public access. The `website_event` module (separate) typically adds `is_published` fields and access rules. Without `website_event`, the event form and list views are restricted to authenticated users with appropriate group membership.

### Badge/Ticket Access

The ticket download endpoint (`/event/<int:event_id>/my_tickets`) is `auth='public'` but protected by a cryptographic hash:
```python
hash_truth = event_sudo._get_tickets_access_hash(registration_ids)
if not consteq(tickets_hash, hash_truth):
    raise NotFound()
```
The hash is generated via `tools.hmac(env(su=True), 'event-registration-ticket-report-access', (self.id, sorted(registration_ids)))`. This prevents unauthorized access to attendee data via ID enumeration.

### SQL Injection Prevention

All user inputs are handled through the ORM (`self.env.cr.execute` with parameterized queries for the aggregate functions, and ORM `search`/`write` for all record operations). No raw SQL string interpolation with user input exists in the event module.

---

## L4: Event Mail Scheduler — When and How

### Cron Configuration

**`event.event_mail_scheduler`** runs `model.schedule_communications(autocommit=True)`:
- Interval: 24 hours (configurable)
- User: `base.user_root` (superuser — needed for mass mailing)
- First run: 15 minutes after module installation

The `autocommit=True` parameter causes each scheduler iteration to commit, releasing DB locks and preventing long transactions.

### Scheduler Execution Flow

```
schedule_communications()
  → Search for due schedulers
  → For each scheduler:
      execute()
        → _filter_template_ref()         [Validate template exists]
        → Branch on interval_type:
           'after_sub'     → _execute_attendee_based()
           is_multi_slots   → _execute_slot_based()
           else             → _execute_event_based()
        → _warn_error(exception)          [On failure, post to event chatter]
```

### `after_sub` (Attendee-based) Deep Dive

Triggered immediately after a registration is confirmed. The flow:

1. **`_update_mail_schedulers()`** called from `event.registration.create()` and state transitions to `open`
2. Looks for `event.mail` records with `interval_type='after_sub'`
3. If `event.event_mail_async` config is `True`: triggers the cron and returns
4. Otherwise: runs `execute()` synchronously for each scheduler

**`_execute_attendee_based()` steps:**
```
1. Find registrations since last cursor (last_registration_id)
2. Create event.mail.registration records for each new registration
3. In batches of 50:
   a. Filter out cancelled/draft registrations
   b. Delete mail_registration records for cancelled ones
   c. Call _execute_on_registrations() → sends email
   d. Update mail_count_done
   e. Commit and invalidate cache
4. If count > cron_limit: trigger next cron run
```

**`_create_missing_mail_registrations()`** uses `split_every(500, registrations)` to batch creation of `event.mail.registration` records. Creating 500 at a time is a deliberate balance — enough to amortize overhead, not so many as to cause lock contention.

### `before_event` / `after_event` (Event-based) Deep Dive

One-shot schedulers: once `mail_done=True`, they skip execution on subsequent cron runs.

```
_execute_event_based():
1. Search registrations since last_registration_id (batch of cron_limit + 1)
2. If count > cron_limit: reschedule cron and process only cron_limit
3. In batches of batch_size:
   a. _execute_event_based_for_registrations() → sends email
   b. Update last_registration_id cursor
   c. Refresh mail_count_done
   d. Commit and invalidate cache
4. If no more registrations: set mail_done = True
```

**Slot-based variant** (`_execute_slot_based()`):
1. Creates missing `event.mail.slot` records for new slots
2. For each slot's `scheduled_date <= now` and not `mail_done`: calls `_execute_event_based(mail_slot=slot)`

### Error Handling and Retry

Errors are caught in `schedule_communications()` and passed to `_warn_error()`:

```python
def _warn_error(self, exception):
    # Post a message to event chatter with error details
    # Set error_datetime to now
    # Only re-post if last error was > 1 hour ago
```

The scheduler continues to the next scheduler after an error. Error state is reflected in `mail_state = 'error'`.

### Template Rendering

Templates are rendered using `mail.compose.message` in `mass_mail` composition mode. This means:
- The template renders once per batch (not once per recipient)
- Partner-specific fields use batched rendering with `lang` fallback
- QWeb rendering errors are caught and reported via `_warn_error()`

---

## L4: iCal / ICS Generation

### Endpoint

`/event/<model("event.event"):event>/ics` — `auth='public'`

```python
def event_ics_file(self, event, **kwargs):
    lang = request.env.context.get('lang', request.env.user.lang)
    if request.env.user._is_public():
        lang = request.cookies.get('frontend_lang')
    event = event.with_context(lang=lang)
    slot_id = int(kwargs['slot_id']) if kwargs.get('slot_id') else False
    files = event._get_ics_file(slot=request.env['event.slot'].sudo().browse(slot_id))
    return request.make_response(content, [
        ('Content-Type', 'application/octet-stream'),
        ('Content-Disposition', content_disposition('%s.ics' % event.name))
    ])
```

### `_get_ics_file()` Implementation

Uses `vobject` to build a valid iCalendar:

```python
def _get_ics_file(self, slot=False):
    for event in self:
        cal = vobject.iCalendar()
        cal_event = cal.add('vevent')
        start = slot.start_datetime or event.date_begin
        end = slot.end_datetime or event.date_end
        cal_event.add('created').value = now_utc
        cal_event.add('dtstart').value = start.astimezone(pytz.timezone(event.date_tz))
        cal_event.add('dtend').value = end.astimezone(pytz.timezone(event.date_tz))
        cal_event.add('summary').value = event.name
        cal_event.add('description').value = event._get_external_description()
        if event.address_id:
            cal_event.add('location').value = event.address_inline
        result[event.id] = cal.serialize().encode('utf-8')
    return result
```

**L4 nuance**: Datetimes in iCalendar (VEVENT) must be in local timezone — the code explicitly converts UTC `date_begin`/`date_end` to `event.date_tz` using `pytz`.

**`_get_external_description()`** — Truncates HTML description to 1900 characters to stay within URL limits when the ICS is used in hyperlinks. Includes the `event_share_url` as a hyperlink if set.

---

## L4: Additional Models and Sub-Systems

### `event.stage` Default Stages

Four stages shipped via `data/event_data.xml`:

| Stage | `sequence` | `pipe_end` | `fold` | Description |
|---|---|---|---|---|
| New | 1 | False | False | Freshly created |
| Booked | 2 | False | False | — |
| Announced | 3 | False | False | Publicly announced |
| Ended | 5 | **True** | **True** | Auto-moved by cron when `date_end` passes |

The `pipe_end=True` on "Ended" triggers the kanban state color change (green) and folding in the kanban view.

### `mail.template` Integration

**`event.event_subscription`** — Sent immediately on registration (`after_sub`, `now`). Template model: `event.registration`.

**`event.event_reminder`** — Sent as reminder before event (`before_event`). Template model: `event.registration`.

**`event.event_registration_mail_template_badge`** — Badge email for `action_send_badge_email()`. Template model: `event.registration`.

When a `mail.template` with these XML IDs is deleted, the `event_mail` module's `mail_template.py` override ensures that `event.mail` and `event.type.mail` records referencing that template are also cascade-deleted.

### Cron Jobs

| Cron | Model | Action | Interval |
|---|---|---|---|
| `event.event_mail_scheduler` | `event.mail` | `schedule_communications()` | 24 hours |
| `event.event_autovacuum` | (implicit) | `action_set_done()` on expired events | Daily |

### Configuration Parameters

| Key | Type | Default | Purpose |
|---|---|---|---|
| `event.use_event_barcode` | Boolean | False | Enable barcode check-in feature |
| `event.event_mail_async` | Boolean | False | Run mail schedulers via cron instead of synchronously |
| `google_maps.signed_static_api_key` | String | — | Google Maps API key for venue static images |
| `google_maps.signed_static_api_secret` | String | — | Google Maps API secret for URL signing |
| `mail.batch_size` | Integer | 50 | Emails per DB commit in mass mailing |
| `mail.render.cron.limit` | Integer | 1000 | Max registrations processed per cron run |

---

## L4: Failure Modes

### Overbooking

**Symptom**: More registrations than `seats_max`

**Root cause**: The `_check_seats_availability()` constraint fires on `create()` and `write()` but does not use `SELECT FOR UPDATE` — concurrent transactions can both pass the check simultaneously.

**Fix**: Use `FOR UPDATE NOWAIT` on the event record during registration, or implement a PostgreSQL exclusion constraint on `(event_id, event_slot_id, event_ticket_id)` with a `GIST` index.

### Sold-Out Event Still Accepting Registrations

**Symptom**: `event_registrations_sold_out=True` but new registrations can still be created.

**Root cause**: The `_check_seats_availability()` constraint checks if the *additional* registration would push the count over the limit. If seats are exactly at the limit and a constraint fires on the last seat-holder being cancelled and re-registered, the check may pass incorrectly.

**Fix**: Re-check `seats_available > 0` at the time of `action_confirm()` or at final registration write.

### Mail Scheduler Stuck in Running State

**Symptom**: `interval_type='after_sub'` scheduler always shows `mail_state='running'` after event ends.

**Root cause**: This is by design — `after_sub` schedulers have no natural end condition. They remain `'running'` indefinitely.

**Fix**: Manually archive or delete the scheduler after the event ends.

### Mail Not Sent for New Registrations

**Symptom**: Registration confirmed but no confirmation email received.

**Root cause paths**:
1. No `event.mail` record with `interval_type='after_sub'` exists for the event (all were deleted)
2. `event.event_mail_async` is `True` but the cron has not yet run
3. Template referenced in `event.mail` was deleted (cascade-deleted per `mail_template.py`)
4. Registration is in `draft` state (mail scheduler only processes `state not in ('draft', 'cancel')`)

### ICS Download Returns Empty File

**Symptom**: `/event/<id>/ics` downloads a 0-byte file.

**Root cause**: `vobject` library is not installed. `_get_ics_file()` returns an empty dict, and `event.id` is not in the result, triggering `NotFound()`.

**Fix**: `pip install vobject`

### Multi-Slot: Slot Deleted with Existing Registrations

**Symptom**: Cannot delete a slot because it has registrations.

**Root cause**: `_unlink_except_if_registrations()` on `event.slot` raises `UserError` if `registration_ids` is non-empty.

**Fix**: First cancel or reassign all registrations in the slot, then delete the slot.

### Questions Changed After Attendees Answered

**Symptom**: Changing a question's type raises `UserError`.

**Root cause**: `event.question.write()` explicitly blocks changing `question_type` if any `event.registration.answer` exists for that question.

**Fix**: Archive the old question and create a new one with the correct type.

---

## L4: Event Slot Location Model

`event.slot` does not have a dedicated `location` field — location is stored on `event.event.address_id`. All registrations in any slot share the same venue. For per-slot venues (e.g., different rooms), the `event_speaker` or `website_event` modules handle room assignments separately.

---

## Appendix: Complete Field Reference by Model

### `event.event` complete field list

| Field | Type | Store | Compute | Description |
|---|---|---|---|---|
| `name` | Char | Yes | — | Event title |
| `note` | Html | Yes | Yes (type sync) | Internal notes |
| `description` | Html | Yes | — | Public description |
| `active` | Boolean | Yes | — | Archive control |
| `user_id` | Many2one | Yes | — | Responsible user |
| `company_id` | Many2one | Yes | — | Owning company |
| `organizer_id` | Many2one | Yes | — | Organizer contact |
| `event_type_id` | Many2one | Yes | — | Template reference |
| `stage_id` | Many2one | Yes | — | Kanban stage |
| `kanban_state` | Selection | Yes | Yes (reset on stage) | Kanban state |
| `seats_max` | Integer | Yes | Yes (type sync) | Max registrations |
| `seats_limited` | Boolean | Yes | Yes (type sync) | Enable limit |
| `seats_reserved` | Integer | No | Yes | Open registrations |
| `seats_available` | Integer | No | Yes | Available seats |
| `seats_used` | Integer | No | Yes | Done registrations |
| `seats_taken` | Integer | No | Yes | Total taken |
| `is_multi_slots` | Boolean | Yes | — | Multi-slot format |
| `event_slot_ids` | One2many | Yes | — | Time slots |
| `event_slot_count` | Integer | No | Yes | Slot count |
| `event_ticket_ids` | One2many | Yes | Yes (type sync) | Ticket types |
| `start_sale_datetime` | Datetime | No | Yes | Earliest ticket sale start |
| `event_registrations_started` | Boolean | No | Yes | Sale time gate passed |
| `event_registrations_open` | Boolean | No | Yes (sudo) | Can accept registrations |
| `event_registrations_sold_out` | Boolean | No | Yes (sudo) | Fully sold |
| `date_tz` | Selection | Yes | Yes (type sync) | Display timezone |
| `date_begin` | Datetime | Yes | — | Event start |
| `date_end` | Datetime | Yes | — | Event end |
| `is_ongoing` | Boolean | No | Yes | Currently happening |
| `is_one_day` | Boolean | No | Yes | Same-day event |
| `is_finished` | Boolean | No | Yes | Past event |
| `address_id` | Many2one | Yes | — | Venue address |
| `address_search` | Many2one | No | Yes | Searchable address |
| `address_inline` | Char | No | Yes | Formatted address |
| `country_id` | Many2one | Yes | — | Venue country |
| `event_url` | Char | Yes | Yes (auto-clear) | Online event URL |
| `event_share_url` | Char | No | Yes | Sharing URL |
| `lang` | Selection | Yes | — | Email language |
| `event_mail_ids` | One2many | Yes | Yes (type sync) | Mail schedulers |
| `tag_ids` | Many2many | Yes | Yes (type sync) | Tags |
| `badge_format` | Selection | Yes | — | Badge size |
| `badge_image` | Image | Yes | — | Badge background |
| `ticket_instructions` | Html | Yes | Yes (type sync) | Printed on tickets |
| `registration_ids` | One2many | Yes | — | Attendee list |
| `general_question_ids` | Many2many | Yes | — | Order-level questions |
| `specific_question_ids` | Many2many | Yes | — | Per-attendee questions |
| `question_ids` | Many2many | Yes | Yes (type sync) | All questions |
| `registration_properties_definition` | PropertiesDef | Yes | — | Custom fields schema |
| `use_barcode` | Boolean | No | Yes | Barcode feature active |
