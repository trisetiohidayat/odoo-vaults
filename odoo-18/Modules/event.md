---
Module: event
Version: Odoo 18
Type: Business
Tags: #event, #registration, #ticketing, #mail-scheduler
---

# event — Event Management

Full-featured event management covering event creation, ticket types, attendee registration with barcodes, automated email/SMS scheduling, and post-event reporting.

**Addon path:** `~/odoo/odoo18/odoo/addons/event/`

---

## Data Model Overview

```
event.type (event template)
    ├── event.type.ticket (ticket template)
    ├── event.type.mail (mail schedule template)
    └── event.question (template questions)

event.event (the event)
    ├── event.tag  (categorization)
    │     └── event.tag.category
    ├── event.event.ticket (ticket type for event)
    ├── event.mail (mail scheduler per event)
    ├── event.question (questions per event)
    └── event.registration (attendee)
          ├── event.mail.registration (per-registration mail log)
          └── event.registration.answer (attendee answers)
                └── event.question.answer (suggested answer option)

res.partner  ──< event.registration  (partner_id)
event.event  ──< event.registration  (event_id)
```

---

## `event.type` — Event Template

Pre-configured event templates that auto-fill new events with tickets, tags, mail schedules, and questions. Changing an event's template after creation **does not** automatically update the event — it only fills defaults when `event_type_id` is first set.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Template name, required |
| `note` | Html | Internal notes |
| `sequence` | Integer | Default 10 |
| `event_type_ticket_ids` | One2many → `event.type.ticket` | Default tickets for events |
| `tag_ids` | Many2many → `event.tag` | Default tags |
| `has_seats_limitation` | Boolean | Toggle for seats_max |
| `seats_max` | Integer | Compute: set only when `has_seats_limitation` is True |
| `default_timezone` | Selection `_tz_get` | Default display timezone |
| `event_type_mail_ids` | One2many → `event.type.mail` | Default mail schedules |
| `ticket_instructions` | Html | Printed on tickets |
| `question_ids` | One2many → `event.question` | Default registration questions |

### Default Mail Schedule

Templates ship with three default schedulers:
1. **Immediately on registration** (`interval_type='after_sub'`, unit=`now`) — sends `event_subscription` email
2. **1 hour before event** — sends `event_reminder` email
3. **3 days before event** — sends `event_reminder` email

### Default Questions

Templates auto-add three questions: Name (mandatory), Email (mandatory), Phone (optional). All three use special `question_type` values (`name`, `email`, `phone`) that auto-populate from the registration form.

---

## `event.event` — Event

The central event record. Inherits `mail.thread` and `mail.activity.mixin`.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translatable |
| `note` | Html | Stored, computed from type |
| `description` | Html | Sanitized (no iframe/scripts), default template rendered |
| `active` | Boolean | Soft-delete |
| `user_id` | Many2one → `res.users` | Responsible; defaults to current user |
| `company_id` | Many2one → `res.company` | Defaults to `self.env.company` |
| `organizer_id` | Many2one → `res.partner` | Defaults to `company.partner_id` |
| `event_type_id` | Many2one → `event.type` | Template; triggers compute cascades on change |
| `stage_id` | Many2one → `event.stage` | Kanban stage; `pipe_end=True` = ended stage |
| `kanban_state` | Selection | `normal` (In Progress), `done` (Done), `blocked` (Blocked) |
| `kanban_state_label` | Char | Computed from stage legend |
| `legend_blocked/done/normal` | Char | Related from `stage_id` |
| `date_tz` | Selection `_tz_get` | Display timezone; computed from type or user |
| `date_begin` | Datetime | Required; defaults to now rounded to next half-hour |
| `date_end` | Datetime | Required; defaults to `date_begin + 1 day` |
| `date_begin_located` | Char | `date_begin` formatted in `date_tz` |
| `date_end_located` | Char | `date_end` formatted in `date_tz` |
| `is_ongoing` | Boolean | Compute: `date_begin <= now < date_end` |
| `is_one_day` | Boolean | Compute: same calendar day in `date_tz` |
| `is_finished` | Boolean | Compute: `date_end < now` (in timezone) |
| `address_id` | Many2one → `res.partner` | Venue; defaults to company partner |
| `address_search` | Many2one → `res.partner` | Searchable version of `address_id` |
| `address_inline` | Char | Single-line formatted address |
| `country_id` | Many2one → `res.country` | Related from `address_id`, writable |
| `lang` | Selection | Email translation language |
| `seats_limited` | Boolean | Compute+store; synced from type's `has_seats_limitation` |
| `seats_max` | Integer | Compute+store from type; 0 = unlimited |
| `seats_reserved` | Integer | Compute: count of `state='open'` registrations |
| `seats_available` | Integer | Compute: `seats_max - (reserved + used)` |
| `seats_used` | Integer | Compute: count of `state='done'` registrations |
| `seats_taken` | Integer | Compute: `reserved + used` |
| `registration_ids` | One2many → `event.registration` | All registrations |
| `event_ticket_ids` | One2many → `event.event.ticket` | Tickets; compute+store from type |
| `event_mail_ids` | One2many → `event.mail` | Mail schedulers; compute+store from type |
| `tag_ids` | Many2many → `event.tag` | Compute+store from type |
| `question_ids` | One2many → `event.question` | Compute+store from type |
| `general_question_ids` | One2many | Domain: `once_per_order=True` |
| `specific_question_ids` | One2many | Domain: `once_per_order=False` |
| `event_registrations_started` | Boolean | At least one ticket sale has begun |
| `event_registrations_open` | Boolean | Compute: event not ended, seats available, tickets available |
| `event_registrations_sold_out` | Boolean | Compute: event seats full OR all tickets sold out |
| `start_sale_datetime` | Datetime | Compute: earliest `start_sale_datetime` of all tickets |
| `badge_format` | Selection | `A4_french_fold`, `A6`, `four_per_sheet`, `96x82`, `96x134` |
| `badge_image` | Image | Background image for badge printing |
| `ticket_instructions` | Html | Compute from type if empty |
| `registration_properties_definition` | PropertiesDefinition | Schema for `event.registration.registration_properties` |
| `use_barcode` | Boolean | Compute: reads `event.use_event_barcode` config param |

### Stage Pipeline

`event.stage` controls Kanban board columns:

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required |
| `description` | Text | |
| `sequence` | Integer | Default 1 |
| `fold` | Boolean | Folded in kanban view |
| `pipe_end` | Boolean | Events auto-moved here when `date_end` passes |
| `legend_blocked/done/normal` | Char | Kanban color labels |

### Computed Cascades from `event_type_id`

When `event_type_id` changes, the following are **only recomputed from the type if the event's field is currently falsy** (emulates an onchange, not a hard sync):

| Event Field | Type Field | Notes |
|------------|------------|-------|
| `seats_max` | `seats_max` | Only if event has no seats_max |
| `seats_limited` | `has_seats_limitation` | |
| `date_tz` | `default_timezone` | |
| `event_ticket_ids` | `event_type_ticket_ids` | Tickets with registrations are preserved |
| `event_mail_ids` | `event_type_mail_ids` | Mails already sent/linked are preserved |
| `tag_ids` | `tag_ids` | Only if event has no tags |
| `question_ids` | `question_ids` | Questions with answers are preserved |
| `note` | `note` | Only if event.note is empty |
| `ticket_instructions` | `ticket_instructions` | Only if event is empty |

### Registration Open Logic (`event_registrations_open`)

Registrations are open when ALL of:
1. `event_registrations_started` — ticket sale datetime has passed
2. Event has not ended (`date_end > now` in timezone)
3. Seats not limited, OR seats are available
4. No tickets defined, OR at least one ticket is `sale_available`

### Constraints

- `_check_closing_date`: `date_end >= date_begin`
- `_check_seats_availability`: `seats_available >= minimal_availability` (used by registrations too)

### Key Methods

- `action_set_done()`: Moves event to first `pipe_end=True` stage; `@api.autovacuum _gc_mark_events_done` cron runs this automatically for all past-due events.
- `mail_attendees(template_id)`: Sends a mail.template to all non-cancelled/non-draft registrations.
- `_get_ics_file()`: Generates iCalendar `.ics` content using `vobject`; returns dict `{event_id: bytes}`.
- `_get_date_range_str()`: Human-readable: "today", "tomorrow", "in 3 days", "next week", "next month", or formatted date.
- `_get_external_description()`: Strips HTML, truncates to 1900 chars for URL-safe use.
- `get_kiosk_url()`: Returns `base_url + "/odoo/registration-desk"` for badge scanning kiosk.
- `_set_tz_context()`: Returns `self.with_context(tz=self.date_tz or 'UTC')` for timezone-aware formatting.

### L4 Notes — Seats Model

- Event-level `seats_max` and ticket-level `seats_max` are **independent**. An event can have 100 seats globally and two tickets with 60 seats each — they are not constrained to sum to the event max.
- `seats_available` is computed by raw SQL aggregation on `event_registration` filtered by `state IN ('open', 'done') AND active = true`.
- When a registration is confirmed (`state → 'open'` or `'done'`), `_check_seats_availability()` is called on both the event and the ticket.

---

## `event.tag` / `event.tag.category` — Event Tags

Flat categorization for events with color support.

### `event.tag.category`

| Field | Type |
|-------|------|
| `name` | Char (required) |
| `sequence` | Integer |
| `tag_ids` | One2many → `event.tag` |

Sequence auto-increments: `max(existing_sequence) + 1`.

### `event.tag`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translatable |
| `sequence` | Integer | Default 0 |
| `category_id` | Many2one → `event.tag.category` | Required, cascade delete |
| `category_sequence` | Integer | Related+stored from `category_id.sequence` |
| `color` | Integer | Random 1–11 default |

Tags without a color (or `color=0`) are treated as internal/private and not shown in the public kanban or website.

Ordering: `ORDER BY category_sequence, sequence, id`

---

## `event.event.ticket` / `event.type.ticket` — Ticket Types

### `event.type.ticket` (template)

| Field | Type | Notes |
|-------|------|-------|
| `sequence` | Integer | Default 10 |
| `name` | Char | Default `'Registration'`, translatable |
| `description` | Text | Shown to customers |
| `event_type_id` | Many2one → `event.type` | Required, cascade delete |
| `seats_limited` | Boolean | Compute+store from `seats_max > 0` |
| `seats_max` | Integer | 0 = unlimited |

Only four fields are whitelisted for copying to event tickets: `sequence`, `name`, `description`, `seats_max`.

### `event.event.ticket` (event ticket)

Inherits `event.type.ticket`. Adds sale timing and per-ticket seat tracking.

| Field | Type | Notes |
|-------|------|-------|
| `event_type_id` | Many2one | Nullable, inherited from type (set null on delete) |
| `event_id` | Many2one → `event.event` | Required, cascade delete |
| `company_id` | Many2one | Related from `event_id.company_id` |
| `start_sale_datetime` | Datetime | Ticket goes on sale; `False` = immediately |
| `end_sale_datetime` | Datetime | Ticket sale ends; `False` = never |
| `is_launched` | Boolean | Compute: `start_sale_datetime <= now` |
| `is_expired` | Boolean | Compute: `end_sale_datetime < now` |
| `sale_available` | Boolean | Compute: launched AND NOT expired AND NOT sold out |
| `is_sold_out` | Boolean | Compute: `seats_limited AND seats_available <= 0` OR event sold out |
| `registration_ids` | One2many → `event.registration` | Attendees on this ticket |
| `seats_reserved` | Integer | Compute (SQL): count `state='open'` |
| `seats_used` | Integer | Compute (SQL): count `state='done'` |
| `seats_available` | Integer | Compute: `seats_max - (reserved + used)` |
| `seats_taken` | Integer | Compute: `reserved + used` |
| `color` | Char | Default `#875A7B`; used in badge printing |

### Seat Computation (SQL)

```sql
SELECT event_ticket_id, state, count(event_id)
  FROM event_registration
 WHERE event_ticket_id IN %s AND state IN ('open','done') AND active = true
 GROUP BY event_ticket_id, state
```

### Ticket Sale Lifecycle

1. `is_launched = False` while `start_sale_datetime > now`
2. `is_expired = True` once `end_sale_datetime < now`
3. `sale_available = False` when expired, not launched, or sold out
4. Registration blocked by `_check_seats_availability()` on ticket

### Constraints

- `_constrains_dates_coherency`: `start_sale_datetime <= end_sale_datetime`
- `_check_seats_availability(minimal_availability=0)`: Blocks if `seats_available < minimal_availability`
- `_unlink_except_if_registrations`: Tickets with any registration cannot be deleted

### L4 Notes — Badge Printing Colors

`_get_ticket_printing_color()` reads `event.ticket_text_colors` config parameter (JSON) to override per-ticket text color on badges. Falls back to `#000000`.

---

## `event.registration` — Attendee Registration

Links a person (or anonymous contact) to an event and optional ticket. Inherits `mail.thread` and `mail.activity.mixin`.

| Field | Type | Notes |
|-------|------|-------|
| `event_id` | Many2one → `event.event` | Required |
| `event_ticket_id` | Many2one → `event.event.ticket` | `ondelete='restrict'` |
| `active` | Boolean | Default True; `toggle_active()` triggers seat recheck |
| `barcode` | Char | Unique, auto-generated 8-byte random string (16 decimal digits); used at kiosk |
| `utm_campaign_id` | Many2one → `utm.campaign` | |
| `utm_source_id` | Many2one → `utm.source` | |
| `utm_medium_id` | Many2one → `utm.medium` | |
| `partner_id` | Many2one → `res.partner` | Booked by; used for name/email/phone sync |
| `name` | Char | Compute+store from partner; overridable |
| `email` | Char | Compute+store from partner; overridable |
| `phone` | Char | Compute+store from partner (tries `phone` then `mobile`); overridable |
| `company_name` | Char | Compute+store from partner |
| `date_closed` | Datetime | Compute: set to now when `state → done` |
| `event_begin_date` | Datetime | Related from `event_id.date_begin` |
| `event_end_date` | Datetime | Related from `event_id.date_end` |
| `event_date_range` | Char | Human-readable: "tomorrow", "in 3 days", etc. |
| `event_organizer_id` | Many2one | Related from `event_id.organizer_id` |
| `event_user_id` | Many2one | Related from `event_id.user_id` |
| `company_id` | Many2one | Related+store from `event_id` |
| `state` | Selection | `draft` (Unconfirmed), `open` (Registered), `done` (Attended), `cancel` (Cancelled) |
| `registration_answer_ids` | One2many → `event.registration.answer` | All answers |
| `registration_answer_choice_ids` | One2many | Domain: `question_type='simple_choice'` |
| `mail_registration_ids` | One2many → `event.mail.registration` | Per-registration mail log |
| `registration_properties` | Properties | Definition from `event_id.registration_properties_definition` |

### Registration States

| State | Meaning | Tracked |
|-------|---------|---------|
| `draft` | Unconfirmed; pending action (e.g., sale order not confirmed) | Yes |
| `open` | Registered and confirmed | Yes |
| `done` | Attendee marked as having attended | Yes |
| `cancel` | Cancelled manually | Yes |

### SQL Constraints

```sql
UNIQUE(barcode)  -- Every registration has a globally unique barcode
```

### Key Methods

- `_get_random_barcode()`: `int.from_bytes(os.urandom(8), 'little')` → 16-digit decimal string. Code128C barcode compatible.
- `register_attendee(barcode, event_id)`: Kiosk check-in method. Returns dict with `status` key:
  - `invalid_ticket`: barcode not found
  - `canceled_registration` / `unconfirmed_registration`: state check
  - `not_ongoing_event`: event has ended
  - `need_manual_confirmation`: different event than expected
  - `confirmed_registration`: state updated to `done`
  - `already_registered`: already marked attended
- `_synchronize_partner_values()`: Reads from partner's contact (not the company) via `address_get('contact')`.
- `_onchange_phone_validation()`: Formats phone based on partner country → event country → company country.
- `action_set_draft()` / `action_confirm()` / `action_set_done()` / `action_cancel()`: State transition methods.
- `action_send_badge_email()`: Opens email composer with `event.event_registration_mail_template_badge`.
- `_update_mail_schedulers()`: Called on `create()` and when confirming; triggers `after_sub` schedulers immediately (sync) or via cron (async based on `event.event_mail_async`).
- `_get_registration_summary()`: Returns dict for kiosk display including IoT printer info.
- `_get_registration_print_details()`: Returns dict for badge label generation.
- `_generate_esc_label_badges(is_small_badge)`: Generates ESC/POS printer commands for badge labels using IoT device.

### L4 Notes — Barcode Registration

- `register_attendee()` checks in to the **registration's own event** unless `event_id` is passed as the kiosk event — then it requires the events match, or returns `need_manual_confirmation`.
- Barcode is generated on creation and is **immutable** (copy=False, readonly=True).
- Badge printing supports ESC/POS label printers via the `iot.device` IoT module integration.

---

## `event.mail` — Automated Mail Scheduler

Event-level mail scheduling. Template-sourced from `event.type.mail`.

| Field | Type | Notes |
|-------|------|-------|
| `event_id` | Many2one → `event.event` | Required, cascade delete |
| `sequence` | Integer | Display order |
| `interval_nbr` | Integer | Numeric interval |
| `interval_unit` | Selection | `now`, `hours`, `days`, `weeks`, `months` |
| `interval_type` | Selection | `after_sub` (per registration), `before_event`, `after_event` |
| `scheduled_date` | Datetime | Compute: `date_begin` + offset (before), `date_end` + offset (after), `create_date` + offset (after_sub) |
| `last_registration_id` | Many2one → `event.registration` | Pagination cursor for batch sending |
| `mail_registration_ids` | One2many → `event.mail.registration` | Per-registration mail records |
| `mail_done` | Boolean | Global "sent" flag (only for event-based, not after_sub) |
| `mail_state` | Selection | Compute: `running` (after_sub), `scheduled`, `sent` |
| `mail_count_done` | Integer | Count of sent emails |
| `notification_type` | Selection | Always `mail` (computed from template) |
| `template_ref` | Reference → `mail.template` | Required, cascade delete |

### Cron Execution: `schedule_communications()`

The `event.event_mail_scheduler` cron runs `schedule_communications()` which:
1. Finds all schedulers where `scheduled_date <= now`, `mail_done = False`
2. Skips `after_sub` schedulers if `event_id.date_end <= now`
3. Calls `scheduler.execute()` per scheduler

### `execute()` — Two Modes

| Mode | `interval_type` | Behavior |
|------|----------------|---------|
| Event-based | `before_event`, `after_event` | One-shot; sends to all open registrations via cursor pagination |
| Attendee-based | `after_sub` | Creates `event.mail.registration` per new attendee, then sends |

### `_execute_event_based()`

Batches registrations by `batch_size` (config: `mail.batch_size`, default 50), commits per batch, triggers cron reschedule if `cron_limit` exceeded. Uses `mail.render.cron.limit` (default 1000) for batch scheduling.

### `_execute_attendee_based()`

1. Creates missing `event.mail.registration` records for new open registrations.
2. Executes mailing in batches, unlinking drafts/cancels.
3. Updates `mail_count_done` and `mail_done` flags.

### `event.type.mail` (template)

Mirrors `event.mail` fields (minus `event_id`, `scheduled_date`, state fields). `_prepare_event_mail_values()` copies the template values when a type is applied to an event.

---

## `event.mail.registration` — Per-Registration Mail Log

Created automatically for `after_sub` schedulers. Tracks mail sent status per registration.

| Field | Type | Notes |
|-------|------|-------|
| `scheduler_id` | Many2one → `event.mail` | Required, cascade delete |
| `registration_id` | Many2one → `event.registration` | Required, cascade delete |
| `scheduled_date` | Datetime | Compute: `registration.create_date + scheduler interval` |
| `mail_sent` | Boolean | Set to True after successful send |

### Skip Domain

Records are skipped if: `mail_sent = False` is no longer true, `scheduled_date` is unset, or `scheduled_date > now`.

---

## `event.question` — Registration Questions

Questions shown to registrants. Can be attached to an event or an event type (XOR constraint).

| Field | Type | Notes |
|-------|------|-------|
| `title` | Char | Required, translatable |
| `question_type` | Selection | `simple_choice` (dropdown), `text_box`, `name`, `email`, `phone`, `company_name` |
| `event_type_id` | Many2one → `event.type` | XOR with `event_id` |
| `event_id` | Many2one → `event.event` | XOR with `event_type_id` |
| `answer_ids` | One2many → `event.question.answer` | Options for `simple_choice` |
| `sequence` | Integer | Default 10 |
| `once_per_order` | Boolean | If True, asked once per order and propagated to all attendees |
| `is_mandatory_answer` | Boolean | Requires non-empty answer |

### Special Question Types

The types `name`, `email`, `phone`, `company_name` auto-populate the corresponding registration field from the answer value.

### Constraints

- `_constrains_event`: A question cannot be linked to both an event and a type simultaneously.
- `_unlink_except_answered_question`: Cannot delete a question that has existing answers.
- Write protection: Cannot change `question_type` if answers exist.

### `action_view_question_answers()`

- For `simple_choice`: Opens graph + pivot + list view of answers.
- For `text_box`: Opens list view of text answers.

---

## `event.question.answer` — Answer Options

Options for `simple_choice` questions.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translatable |
| `question_id` | Many2one → `event.question` | Required, cascade delete |
| `sequence` | Integer | Default 10 |

### Constraint

- `_unlink_except_selected_answer`: Cannot delete an answer option that has been selected.

---

## `event.registration.answer` — Attendee Answer Record

Stores a registrant's response to an event question.

| Field | Type | Notes |
|-------|------|-------|
| `question_id` | Many2one → `event.question` | `ondelete='restrict'`, required |
| `registration_id` | Many2one → `event.registration` | Required, cascade delete |
| `partner_id` | Many2one → `res.partner` | Related from `registration_id.partner_id` |
| `event_id` | Many2one → `event.event` | Related from `registration_id.event_id` |
| `question_type` | Selection | Related from `question_id` |
| `value_answer_id` | Many2one → `event.question.answer` | For `simple_choice` |
| `value_text_box` | Text | For `text_box` and other types |

### SQL Constraint

```sql
CHECK(value_answer_id IS NOT NULL OR COALESCE(value_text_box, '') <> '')
```

### `display_name`

- `simple_choice`: returns `value_answer_id.name`
- Others: returns `value_text_box`

---

## `res.partner` Extension

Added by `event.models.res_partner`:

| Field | Type | Notes |
|-------|------|-------|
| `event_count` | Integer | Compute: count of events with registrations from partner or children |
| `static_map_url` | Char | Compute: Google Maps signed static image URL |
| `static_map_url_is_valid` | Boolean | Compute: verifies the URL returns successfully |

- `action_event_view()`: Opens event action filtered to this partner's registrations.

### Google Maps Signed URL

`_google_map_signed_img()` uses `google_maps.signed_static_api_key` and `google_maps.signed_static_api_secret` ir.config_parameters. Signs the URL per Google's digital signature spec. Falls back to `None` if keys are missing.

---

## Registration Mail Flow

```
event.registration.create()
    └─ _update_mail_schedulers()
          └─ event.mail (interval_type='after_sub').execute()
                └─ _execute_attendee_based()
                      └─ event.mail.registration.create() for each new registration
                            └─ _execute_on_registrations()
                                  └─ scheduler._send_mail(registrations)
                                        └─ mail.compose.message (mass_mail mode)
```

---

## Key Design Patterns

1. **Template inheritance (compute cascade)**: `event_type_id` change triggers `_compute_*` methods that only populate empty fields — preserving manual event customizations.
2. **Registration seat tracking via SQL**: Both `event.event` and `event.event.ticket` use raw SQL aggregation to avoid N+1 on registration counting.
3. **Barcode as registration identity**: Globally unique, randomly generated, immutable. Used for kiosk check-in.
4. **Mail scheduler cursor pagination**: Event-based mailers use `last_registration_id` to resume from where they left off, committing per batch.
5. **Timezone-aware everything**: `date_tz` context applied before any datetime comparison or formatting.
6. **Event auto-close via autovacuum**: `_gc_mark_events_done()` runs nightly and transitions past-due events to the first `pipe_end=True` stage.

---

## Configuration Parameters

| Key | Purpose |
|-----|---------|
| `event.use_event_barcode` | Enable barcode scanning on events |
| `event.event_mail_async` | Run mail schedulers via cron instead of sync |
| `event.ticket_text_colors` | JSON: `{"Ticket Name": "#RRGGBB"}` color overrides |
| `event.badge_printing_sponsor_text` | Text printed on badge footers |

---

## Related Files

- Model: `~/odoo/odoo18/odoo/addons/event/models/event_event.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/event_ticket.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/event_tag.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/event_stage.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/event_registration.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/event_mail.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/event_mail_registration.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/event_question.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/event_question_answer.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/event_registration_answer.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/res_partner.py`
- Model: `~/odoo/odoo18/odoo/addons/event/models/res_config_settings.py`
