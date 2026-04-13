---
tags: [odoo, odoo19, module, mass_mailing, event, mailing, integration]
description: L4 full-depth documentation for mass_mailing_event module
---

# Mass Mailing Event (`mass_mailing_event`)

## Overview

**Technical Name:** `mass_mailing_event`
**Category:** Marketing/Email Marketing
**Version:** 1.0
**Author:** Odoo S.A.
**License:** LGPL-3
**Auto-Install:** Yes
**Module Path:** `odoo/addons/mass_mailing_event/`

`mass_mailing_event` is a **bridge module** that connects two standalone Odoo apps -- `event` (Event Management) and `mass_mailing` (Email Marketing) -- to enable event organizers to send mass emails directly from the event form. It adds two action buttons to the `event.event` form view (`Invite` and `Contact Attendees`) and registers `event.registration` as a mailing-compatible model so that the mass mailing engine can target attendees as recipients.

It does **not** define any new database table, new fields, or new access rights. All functionality is achieved through:
- **Classical inheritance** (`_inherit`) on `event.event` and `event.registration`
- **View extension** (XPath-based) adding buttons to the event form
- The `_mailing_enabled` class attribute mechanism from `mass_mailing`

```
event.event                          (from: event)
  └── mass_mailing_event/models/event_event.py
        _inherit = "event.event"
        + action_mass_mailing_attendees()   # button: targets event.registration
        + action_invite_contacts()           # button: targets res.partner

event.registration                   (from: event)
  └── mass_mailing_event/models/event_registration.py
        _inherit = "event.registration"
        + _mailing_enabled = True            # class attr: enables mailing UI
        + _mailing_get_default_domain()      # default recipient filter

mailing.mailing                      (from: mass_mailing)
        [consumes _mailing_enabled and _mailing_get_default_domain]

mailing.trace                        (from: mass_mailing)
        [created at send time; links each mailing to target registrations]
```

---
---

## Module Manifest

**File:** `__manifest__.py`

```python
{
    'name': 'Mass mailing on attendees',
    'category': 'Marketing/Email Marketing',
    'version': '1.0',
    'description': """
Mass mail event attendees
=========================

Bridge module adding UX requirements to ease mass mailing of event attendees.
    """,
    'depends': ['event', 'mass_mailing'],
    'data': [
        'views/event_views.xml'
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

### `auto_install` Design Rationale

Setting `auto_install: True` means that when both `event` and `mass_mailing` are installed (or about to be installed), Odoo will automatically install `mass_mailing_event` as well. This is appropriate because:
1. The module provides pure UX enhancement -- there is no reason to have both `event` and `mass_mailing` installed without this bridge.
2. It has no standalone value; it only makes sense as an integration.
3. The `depends` declaration guarantees the prerequisite modules are present.

The order of installation is: `event` and `mass_mailing` install first (satisfying the `depends`), then `mass_mailing_event` auto-installs.

### `data` -- Single XML File

The `data` list contains only `views/event_views.xml`. There are no CSV security files, no demo data, and no workflow definitions. This is consistent with the module's role as a pure extension layer -- it does not introduce new records, only modifies existing views.

---

## Dependencies

| Module | Role |
|--------|------|
| `event` | Provides `event.event` and `event.registration` base models; seat management, registration states, computed fields (`is_finished`, `event_registrations_open`, `seats_taken`) |
| `mass_mailing` | Provides `mailing.mailing` form and engine, `mailing.trace` tracking, `ir.model.is_mailing_enabled` computed field, `_get_default_mailing_domain` call site |

The dependency chain through `mass_mailing` includes: `mail`, `mass_mailing_track`, and ultimately `mail_thread` for delivery tracking. This is transparent to `mass_mailing_event`.

---

## Module File Structure

```
mass_mailing_event/
├── __init__.py                      # Imports models/ package
├── __manifest__.py                  # Metadata, depends, data
├── models/
│   ├── __init__.py                  # Imports event_event, event_registration
│   ├── event_event.py               # event.event extension (action methods)
│   └── event_registration.py        # event.registration extension (_mailing_enabled)
├── views/
│   └── event_views.xml              # View inheritance (button additions)
└── i18n/
    ├── mass_mailing_event.pot        # Master translation template
    └── [40+ locale .po files]        # Translated strings
```

---

## Models

### 1. `event.event` -- Extended by `mass_mailing_event`

**File:** `models/event_event.py`
**Inheritance Type:** Classical (`_inherit = "event.event"`)
**No new fields defined.** The class adds two action methods that open a `mailing.mailing` form pre-populated with context values.

#### Method: `action_mass_mailing_attendees()`

Opens the `mailing.mailing` form pre-configured to send emails to **registered, confirmed attendees** of the current event(s).

```python
def action_mass_mailing_attendees(self):
    return {
        'name': 'Mass Mail Attendees',
        'type': 'ir.actions.act_window',
        'res_model': 'mailing.mailing',
        'view_mode': 'form',
        'target': 'current',
        'context': {
            'default_mailing_model_id': self.env.ref('event.model_event_registration').id,
            'default_mailing_domain': repr([('event_id', 'in', self.ids),
                                           ('state', 'not in', ['cancel', 'draft'])]),
            'default_subject': _("Event: %s", self.name),
        },
    }
```

**Context Values Set:**

| Key | Value | Purpose |
|-----|-------|---------|
| `default_mailing_model_id` | `self.env.ref('event.model_event_registration').id` | Tells `mailing.mailing` to treat recipients as `event.registration` records. The `mailing.mailing` model stores this in its `mailing_model_id` Many2one field. The engine then uses `event.registration` to resolve email addresses and track delivery via `mailing.trace` |
| `default_mailing_domain` | `repr([('event_id', 'in', self.ids), ('state', 'not in', ['cancel', 'draft'])])` | Pre-populates the **Recipients** domain field in the mailing form. The `mailing.mailing` model's `_compute_mailing_domain` stores this in `mailing_domain` (a Char field). The `repr(...)` call serializes the domain list to a string; `_parse_mailing_domain()` later calls `ast.literal_eval` to deserialize it back |
| `default_subject` | `_("Event: %s", self.name)` | Pre-fills the email subject line with the event name, localized via `_()`. Uses the `format()` style `%s` placeholder |

**L3 -- Multi-record action call:**
`self.ids` may contain more than one event ID if the user selects multiple events in the list view and clicks the button from the list action (rather than the form). The domain `('event_id', 'in', self.ids)` correctly handles both single and multi-record scenarios. The mailing engine resolves this domain against `event.registration` and targets registrations for all selected events.

**L3 -- Failure mode: zero registrations:**
If the domain matches zero registrations (all attendees cancelled, or no one registered), the mailing's recipient count will be zero. `mailing.mailing` handles this gracefully -- the user can still save the mailing and adjust the domain manually before sending. No error is raised.

**L3 -- Failure mode: event without registrations:**
The button is visible when `seats_taken > 0` (defined in the view). Since `seats_taken = seats_reserved + seats_used`, this means at least one confirmed or checked-in attendee exists. However, if registrations were later cancelled down to zero, the button would remain visible (visibility is computed at form load time). The mailing domain then correctly returns zero recipients.

**L4 -- Performance of `self.env.ref(...)` call:**
`self.env.ref('event.model_event_registration')` performs an `ir.model` search by XML ID on each action call. This is a single low-cost SQL query with a unique key lookup on the XML ID column. Cached after first call. Negligible overhead.

#### Method: `action_invite_contacts()`

Opens the `mailing.mailing` form pre-configured to send to **all contacts** (`res.partner` records), not limited to registered attendees. Used to invite people who have not yet registered.

```python
def action_invite_contacts(self):
    return {
        'name': 'Mass Mail Invitation',
        'type': 'ir.actions.act_window',
        'res_model': 'mailing.mailing',
        'view_mode': 'form',
        'target': 'current',
        'context': {
            'default_mailing_model_id': self.env.ref('base.model_res_partner').id,
            'default_subject': _("Event: %s", self.name),
        },
    }
```

**Context Values Set:**

| Key | Value | Purpose |
|-----|-------|---------|
| `default_mailing_model_id` | `self.env.ref('base.model_res_partner').id` | Recipients are `res.partner` contacts, resolved by email |
| `default_subject` | `_("Event: %s", self.name)` | Pre-fills subject with event name |

**Critical difference from `action_mass_mailing_attendees`:** No `default_mailing_domain` is set. The mailing domain must be configured manually by the user. This is intentional because event invitations are sent to a **curated partner segment** (e.g., a mailing list, a country filter, a tag filter) rather than all contacts in the database.

**L3 -- Why two separate actions instead of one?**

Using the same action with conditional logic to determine the mailing model would require reading button context to know which target model to use, conditionally setting `default_mailing_domain`, and conditionally setting `default_subject`. Separating into two explicit actions is cleaner and more maintainable. The business intent ("invite contacts" vs. "contact attendees") is different, so the UX distinction is appropriate.

**L3 -- No `check_access_rights` in action methods:**

The action methods do not call `self.check_access_rights()` before returning the window action. This is acceptable because: (1) the user is already viewing the `event.event` form (implies event read access), (2) the `mailing.mailing` form opened is subject to its own access controls, and (3) sending the mailing later is gated by `mass_mailing.group_mass_mailing_user` on the view buttons, not on the action method.

**L4 -- `self.name` in multi-record context:**

When `self` is a recordset of multiple events (invoked from a list view), `self.name` returns the name of the first record in the recordset (Odoo's recordset `.name` returns the first record's display name by convention). This means the pre-filled subject will show only the first event's name in a multi-event mailing. This is a known limitation and is consistent with Odoo's standard behavior for multi-record action context.

---

### 2. `event.registration` -- Extended by `mass_mailing_event`

**File:** `models/event_registration.py`
**Inheritance Type:** Classical (`_inherit = "event.registration"`)
**Defined in:** `models/event_registration.py` (imported by `models/__init__.py` via `from . import event_registration`)

The `models/__init__.py` file correctly imports both model files:

```python
# models/__init__.py
from . import event_event          # defines EventEvent class
from . import event_registration    # defines EventRegistration class
```

The `EventRegistration` class body lives in `models/event_registration.py`:

```python
# models/event_registration.py
import ast
from odoo import models

class EventRegistration(models.Model):
    _inherit = 'event.registration'
    _mailing_enabled = True

    def _mailing_get_default_domain(self, mailing):
        default_mailing_model_id = self.env.context.get('default_mailing_model_id')
        default_mailing_domain = self.env.context.get('default_mailing_domain')
        if (default_mailing_model_id
                and mailing.mailing_model_id.id == default_mailing_model_id
                and default_mailing_domain):
            return ast.literal_eval(default_mailing_domain)
        return [('state', 'not in', ['cancel', 'draft'])]
```

The `ast` import is at the top of `models/event_registration.py`, not in `models/__init__.py`.

#### Class Attribute: `_mailing_enabled = True`

This is a **class-level attribute** (not an `odoo.fields` field). It is read via Python introspection by the `mass_mailing` module to determine whether `event.registration` can appear as a selectable **Mailing Model** in the `mailing.mailing` form.

**L4 -- How `_mailing_enabled` is consumed:**

The `mass_mailing` module defines `ir.model.is_mailing_enabled` as a computed field:

```python
# mass_mailing/models/ir_model.py
def _compute_is_mailing_enabled(self):
    for model in self:
        model.is_mailing_enabled = getattr(self.env[model.model], '_mailing_enabled', False)
```

In the `mailing.mailing` form, the `mailing_model_id` selection widget has `domain=[('is_mailing_enabled', '=', True)]`. Without `_mailing_enabled = True` on `event.registration`, the `ir.model` record for `event.registration` would have `is_mailing_enabled = False` and would be silently absent from the dropdown.

**L4 -- Performance:**

There is zero database overhead. The `_mailing_enabled` check is an in-memory Python class attribute lookup (`getattr(model_class, '_mailing_enabled', False)`). No extra SQL queries are generated.

**L3 -- What models have `_mailing_enabled`:**

In a standard Odoo 19 installation, the following models typically have `_mailing_enabled = True`:
- `mailing.contact` (from `mass_mailing`)
- `mailing.list` (from `mass_mailing`)
- `res.partner` (from `mass_mailing` or `contacts`)
- `event.registration` (from `mass_mailing_event`)
- `crm.lead` (from `crm` or `mass_mailing_crm`)
- `hr.applicant` (from `hr_recruitment` or `mass_mailing_recruitment`)
- `slide.channel.partner` (from `website_slides`)

**L4 -- `_mail_defaults_to_email = True`:**

`event.registration` inherits `_mail_defaults_to_email = True` from its `_inherit = ['mail.thread', ...]` declaration. This tells the mail tracking system to use the `email` field of the record as the recipient address for mail threads. When a mailing is sent to a registration, Odoo uses `registration.email` as the `To:` address, not `registration.partner_id.email`. This is intentional -- registrations may be made by people without Odoo partner accounts.

#### Method: `_mailing_get_default_domain(mailing)`

**Signature:** `def _mailing_get_default_domain(self, mailing) -> list`

**Purpose:** Supplies the default recipient filter when a `mailing.mailing` record is created with model `event.registration`, or when the mailing model's compute method re-evaluates. Called by `mailing.mailing._get_default_mailing_domain()`.

```python
def _mailing_get_default_domain(self, mailing):
    default_mailing_model_id = self.env.context.get('default_mailing_model_id')
    default_mailing_domain = self.env.context.get('default_mailing_domain')
    if (default_mailing_model_id
            and mailing.mailing_model_id.id == default_mailing_model_id
            and default_mailing_domain):
        return ast.literal_eval(default_mailing_domain)
    return [('state', 'not in', ['cancel', 'draft'])]
```

**Logic breakdown:**

**Step 1 -- Read context:**
Reads two context values that `action_mass_mailing_attendees()` set before opening the mailing form:
- `context['default_mailing_model_id']` = the `ir.model` ID of `event.registration`
- `context['default_mailing_domain']` = `repr([('event_id', 'in', self.ids), ('state', 'not in', ['cancel', 'draft'])])`

**Step 2 -- Guard conditions (all must be true):**
All three must be true. This ensures the domain is only auto-applied when: (1) the mailing was created through the event button (context is set), AND (2) the mailing's model is still `event.registration` (not changed to something else), AND (3) a non-empty domain string was passed.

**Step 3 -- Deserialize and return:**
`ast.literal_eval()` safely converts the string back to a Python list. It accepts only Python literals (lists, tuples, strings, numbers, booleans, `None`) and raises `ValueError` on any expression containing identifiers, operators, or function calls.

**Step 4 -- Fallback domain:**
If any guard condition fails (e.g., mailing created directly from the mass mailing app menu), the fallback is:
```python
return [('state', 'not in', ['cancel', 'draft'])]
```
This still prevents emailing cancelled or draft registrations in manual mailing creation scenarios.

**L3 -- Why use `repr()` + `ast.literal_eval()`?**

Domain expressions cannot be passed directly through the action context because context values must be primitive types (strings, numbers, booleans). `repr()` serializes the domain list to a string representation, and `ast.literal_eval()` deserializes it safely on the other side. This is the standard Odoo pattern for transporting domains through contexts and `default_get` flows.

**L3 -- Registration states in `event.registration`:**

The `event` module defines the `state` Selection field on `event.registration`. The canonical states are:

| State | Meaning | Included in Mailing? |
|-------|---------|---------------------|
| `draft` | Registration started but not confirmed | **No** |
| `open` | Confirmed, counted toward capacity | **Yes** |
| `done` | Attendee checked in at event | **Yes** |
| `cancel` | Registration cancelled | **No** |

The fallback domain `[('state', 'not in', ['cancel', 'draft'])]` excludes cancelled and draft registrations. Note: `event.registration` does not use a `blocked` state in the base `event` module; the only states are `draft`, `open`, `done`, `cancel`. The base model's `_check_seats_availability` constraint can move a registration to a `blocked` state only through an explicit write operation if the event's workflow is customized. In the standard module, the state domain is sufficient.

**L4 -- `ast.literal_eval` Security:**

This is safe because: (1) the source string originates from `repr(...)` in `action_mass_mailing_attendees` -- pure server-side code, not user-supplied, (2) a malicious actor cannot inject values into the context between the action method and this method because context is server-side, and (3) `ast.literal_eval` does not execute arbitrary Python -- it only parses Python data literals. No raw SQL is used anywhere in the module.

**L4 -- `mailing.mailing._get_default_mailing_domain` call site:**

```python
# mass_mailing/models/mailing.py
def _get_default_mailing_domain(self):
    mailing_domain = Domain.TRUE
    if hasattr(self.env[self.mailing_model_name], '_mailing_get_default_domain'):
        mailing_domain = Domain(
            self.env[self.mailing_model_name]._mailing_get_default_domain(self)
        )
    return mailing_domain
```

The `hasattr` check ensures that only models with `_mailing_get_default_domain` defined (like `event.registration` after this module is installed) get a custom domain. Models without it fall back to `Domain.TRUE` (no filtering).

The `_compute_mailing_domain` method on `mailing.mailing` re-evaluates on every `mailing_model_id` change and stores the result as a Char field:

```python
@api.depends('mailing_model_id', 'mailing_domain')
def _compute_mailing_domain(self):
    for mailing in self:
        if not mailing.mailing_model_id:
            mailing.mailing_domain = ''
        elif mailing.mailing_filter_id:
            mailing.mailing_domain = mailing.mailing_filter_id.mailing_domain
        else:
            mailing.mailing_domain = repr(mailing._get_default_mailing_domain() or [])
```

Note that `mailing_domain` has `store=True` -- once computed and stored, it will not re-evaluate unless `mailing_model_id` or `mailing_filter_id` changes. This means manually editing the domain in the form and then switching the model away and back will reset the domain to the `_mailing_get_default_domain` result.

---

## View Extension

**File:** `views/event_views.xml`

```xml
<record id="event_event_view_form_inherit_mass_mailing" model="ir.ui.view">
    <field name="name">event.event.view.form.inherit.mass.mailing</field>
    <field name="model">event.event</field>
    <field name="priority" eval="4"/>
    <field name="inherit_id" ref="event.view_event_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='stage_id']" position="before">
            <field name="event_registrations_open" invisible="1"/>
            <button name="action_invite_contacts" type="object" string="Invite"
                class="btn btn-primary"
                groups="mass_mailing.group_mass_mailing_user"
                invisible="is_finished or not event_registrations_open"/>
            <button name="action_invite_contacts" type="object" string="Invite"
                class="btn btn-secondary"
                groups="mass_mailing.group_mass_mailing_user"
                invisible="is_finished or event_registrations_open"/>
            <button name="action_mass_mailing_attendees" type="object" string="Contact Attendees"
                groups="mass_mailing.group_mass_mailing_user"
                invisible="seats_taken == 0"/>
        </xpath>
    </field>
</record>
```

### `priority="4"` -- Inheritance Loading Order

The view has `priority="4"` (lower than the default priority 16). Odoo loads views in ascending priority order. This means `mass_mailing_event`'s view extension loads **before** the base `event.view_event_form`, giving it the opportunity to add buttons before other modules that might also extend the same form.

**L4 -- Why `priority="4"` specifically?**

The `event` module itself likely uses a higher priority (e.g., 14 or 16). Using priority 4 ensures this bridge module's extensions are established early, avoiding conflicts with other modules that might use the same `stage_id` XPath anchor. It is a defensive design choice that prioritizes predictability over convenience.

**L4 -- Overriding `priority="4"` with a higher priority view:**

If another module adds an event form extension with `priority < 4` (loading even earlier), its additions would appear before these buttons. If another module uses `priority > 4` (loading later), its XPath modifications target the *already-modified* form, so it will see the buttons from this module. This is standard Odoo view inheritance behavior.

### Button Visibility Matrix

| Button | `invisible` Expression | Visible When | Button Style |
|--------|----------------------|--------------|--------------|
| Invite (1) | `is_finished or not event_registrations_open` | Event not finished AND registrations open | `btn-primary` (prominent) |
| Invite (2) | `is_finished or event_registrations_open` | Event finished OR registrations closed | `btn-secondary` (subdued) |
| Contact Attendees | `seats_taken == 0` | At least one seat taken (seats_reserved > 0 OR seats_used > 0) | Default (no explicit class) |

The **two Invite buttons with mutually-exclusive `invisible` domains** achieve a UX pattern where the button's visual weight changes based on context, but both call the same underlying action. This is a common Odoo UI pattern: primary style when registration is currently open (strong call to action to invite more people); secondary style when registration is closed or the event is over (subdued action, as the primary goal of getting registrations is no longer relevant).

### Fields Used in Visibility Conditions

These are **existing computed fields** from `event/models/event_event.py`, not fields added by `mass_mailing_event`:

| Field | Type | Compute | Used In |
|-------|------|---------|---------|
| `event_registrations_open` | `Boolean` | `kanban_state != 'cancel' and event_registrations_started and (date_end not passed) and (not seats_limited or seats_available) and (tickets have sale_available)` | Invite button visibility |
| `is_finished` | `Boolean` | `datetime_end <= current_datetime` (timezone-aware) | Invite button visibility |
| `seats_taken` | `Integer` | `seats_reserved + seats_used` (marked `store=False`, computed on the fly) | Contact Attendees visibility |

**L3 -- Invisible field as state carrier:**
The `<field name="event_registrations_open" invisible="1"/>` element is placed in the form but rendered invisible. Its purpose is purely to make the computed field's value available for use in the button's `invisible` attribute. In Odoo, a field must be present in the view's `<field>` nodes (even if invisible) for its value to be accessible in `invisible` expressions. Without this line, the XPath would still work for the first load, but Odoo's web client may not reliably track the field's value for conditional rendering.

**L3 -- `groups="mass_mailing.group_mass_mailing_user"`:**
All three buttons require the `mass_mailing.group_mass_mailing_user` group. Users without this group see neither button. The action methods themselves do not perform their own access rights checks; the view-level `groups` attribute is the gate.

**L4 -- Performance of `invisible` evaluation:**
Odoo's web client evaluates `invisible` expressions client-side using the field values loaded with the form. These three fields are already fetched as part of the form's default read. There is no additional network request when the visibility changes. The button visibility is purely client-side DOM manipulation. `seats_taken` is marked `store=False`, which means it is always computed fresh on form load rather than being stored in the database, so it always reflects current registration counts.

---

## Mass Mailing Engine Integration

### How `_mailing_get_default_domain` is Called

When a `mailing.mailing` record has `mailing_model_id` set to `event.registration`:

1. `_compute_mailing_domain` fires (triggered by `mailing_model_id` change)
2. No `mailing_filter_id` is set (from the event button), so it calls `_get_default_mailing_domain()`
3. `_get_default_mailing_domain` does `hasattr(self.env['event.registration'], '_mailing_get_default_domain')` -- returns `True`
4. Calls `self.env['event.registration']._mailing_get_default_domain(self)` with the `default_mailing_model_id` and `default_mailing_domain` context keys still present
5. Returns the event-scoped domain `[('event_id', 'in', event_ids), ('state', 'not in', ['cancel', 'draft'])]`
6. `mailing_domain` is stored as `repr(...)` of this domain

### Recipient Resolution at Send Time

When the user clicks **Send** on a `mailing.mailing`:

```python
# mailing.py: _get_recipients()
mailing_domain = self._get_recipients_domain()   # parses mailing.mailing_domain (stored as repr string)
res_ids = self.env[mailing.mailing_model_real].search(mailing_domain).ids
```

For `event.registration`, `mailing.mailing_model_real` resolves to `'event.registration'`. The `search()` call:
1. Applies the domain `[('event_id', 'in', event_ids), ('state', 'not in', ['cancel', 'draft'])]`
2. Returns confirmed attendee records for the targeted event(s)
3. Each record's `email` field (computed from `partner_id.email` if not set, stored on write) is extracted as the recipient address
4. `mailing.trace` records are created linking each registration to the mailing for tracking

**L4 -- Email normalization at send time:**

When a mailing is scheduled or sent, `mailing.mailing` calls `_get_recipients` which filters registrations through `mail.blacklist` (global email blacklist) and checks `partner_id.blacklisted` on the linked partner. If a registration's email is on the blacklist, that registration is silently excluded from the recipient list. This is handled by `mass_mailing`, not `mass_mailing_event`.

### `mailing.trace` -- The Tracking Model

`mailing.trace` (from `mass_mailing` module) records the outcome of each individual email send:

| Field | Purpose |
|-------|---------|
| `mailing_id` | The `mailing.mailing` record |
| `model` | `'event.registration'` |
| `res_id` | The `event.registration` ID |
| `email` | Recipient email (copied from registration at send time) |
| `state` | `outgoing`, `sent`, `delivered`, `opened`, `clicked`, `replied`, `bounced`, `canceled` |
| `failure_type` | If bounced: `SMTP`, `unknown`, `mail_email_missing` |
| `trace_status` | Computed from `state` for UI display |

`mass_mailing_event` does **not** extend `mailing.trace`. The trace model is shared across all mailing-enabled models.

**L4 -- Trace creation and `email` field copy:**

When a trace is created at send time, the `email` field is copied from `registration.email` **at that moment**. If the registration's email is later changed, the trace record retains the old email address. This is important for auditing and for bounce handling -- bounce notifications use the email stored in the trace, not the current registration email.

**L4 -- `mailing.trace` and `mailing.trace.failure` multi-record insert:**

The mass mailing engine batches trace creation using `create_batch` (SQL multi-insert) for performance. Trace records are created after the email is queued in the outgoing mail queue (via `mail.mail` records). If an email fails at the SMTP level after trace creation, the trace is updated to `bounced` state via an async `mail.thread` notification handler. This means trace status can lag slightly behind actual delivery status if the SMTP server is slow or retries.

---

## Security

### Access Control Matrix

| Entity | ACL Source | Gate |
|--------|-----------|------|
| `event.event` read | `event` module | Users with event access |
| `event.registration` read | `event` module | Users with registration access |
| `mailing.mailing` create/write | `mass_mailing` module | `mass_mailing.group_mass_mailing_user` |
| Mass mailing event buttons | View-level `groups` | `mass_mailing.group_mass_mailing_user` |

**L3 -- Record rules on `event.registration`:**

When a mailing is sent, the mass mailing engine runs the recipient domain as the mailing user. If record rules are defined on `event.registration` (e.g., restricting access to registrations within the user's company via `ir.rule`), those rules are applied. Registrations outside the user's access scope are silently excluded from the recipient list. This can result in fewer recipients than expected if record rules are unexpectedly broad or restrictive.

**L4 -- Partner ACL for invite contacts:**

When `action_invite_contacts` is used, the mailing targets `res.partner`. Standard partner record rules apply. Users with restricted partner access will only mail their accessible partners. No extra ACL check is performed by `mass_mailing_event`.

### SQL Injection Prevention

The `ast.literal_eval(default_mailing_domain)` call in `_mailing_get_default_domain` is safe because: (1) the domain string originates from `repr(...)` in `action_mass_mailing_attendees` -- pure server-side code, (2) no user-supplied data enters this flow, (3) `ast.literal_eval` rejects any expression containing identifiers, operators, or function calls, and (4) no raw SQL is used anywhere in the module.

### CSRF

The action methods return an `ir.actions.act_window` dictionary, not an HTTP response. CSRF protection applies only to HTTP controller routes decorated with `@http.route`, which this module does not use.

---

## Odoo 18 to Odoo 19 Changes

### Overall Assessment

The `mass_mailing_event` module is **unchanged between Odoo 18 and Odoo 19**. All code is byte-for-byte identical in both versions. No modifications were required.

### Why No Changes Were Needed

1. **Model structure:** Both `event.event` and `event.registration` retained their field definitions, inheritance, and API in Odoo 19. The `state` Selection field, `email` Char field, `partner_id` Many2one, and all computed fields remain identical.

2. **`_mailing_enabled` mechanism:** This class attribute pattern was introduced in Odoo 15 and remains the primary extension point for making models mailing-eligible in Odoo 19. The `mass_mailing` module's `_get_default_mailing_domain` and `hasattr` check remain identical.

3. **View inheritance:** The XPath `//field[@name='stage_id']` insertion point remains valid in `event.view_event_form` in Odoo 19. The button placement has not changed.

4. **Action return pattern:** The `ir.actions.act_window` dictionary format with `context` values is stable since Odoo 13.

5. **String formatting:** `_("Event: %s", self.name)` using Python `%s` formatting was already used in Odoo 18 and remains supported.

### Historical Context

`mass_mailing_event` was introduced in Odoo 13 when the modern `_mailing_enabled` mechanism was designed. Before Odoo 13, enabling a model for mass mailing required overriding `mailing.mailing`'s model selection method. The `_mailing_enabled` class attribute was introduced as the cleaner extension point and has remained stable since.

### Key Stability Signals

- No migration scripts in the module (it has no prior version-specific data to migrate)
- No deprecation warnings in Odoo 19 for any method or attribute used
- No reference to any Odoo 18-only API

---

## Performance Considerations

### Button Visibility

The three fields in button `invisible` expressions (`event_registrations_open`, `is_finished`, `seats_taken`) are computed fields on `event.event`:
- `event_registrations_open`: Multi-part boolean AND/OR, involves `kanban_state`, `date_end` comparison against `current_datetime`, seat availability, and ticket `sale_available` checks
- `is_finished`: Datetime comparison against `current_datetime` with timezone awareness (`pytz.timezone(event.date_tz)`)
- `seats_taken`: Integer addition (`seats_reserved + seats_used`), marked `store=False` so always computed fresh

These add minimal overhead to form load. `event_registrations_open` is marked `compute_sudo=True`, meaning it computes even for users without full technical access.

### `_mailing_get_default_domain` Called on Every Model Change

The `_compute_mailing_domain` method re-evaluates whenever `mailing_model_id` changes. For `event.registration`, this involves:
1. Two `dict.get()` context reads: O(1)
2. One integer comparison: O(1)
3. One `ast.literal_eval` on a small domain string: O(n) where n = string length (~80 chars typical)
4. One list comparison for fallback: O(k) where k = number of domain terms

Total: negligible.

### Recipient Search at Send Time

When a mailing targets many registrations (e.g., 10,000+), the `search()` call:
```python
self.env['event.registration'].search([
    ('event_id', 'in', event_ids),
    ('state', 'not in', ['cancel', 'draft'])
]).ids
```
Benefits from the index on `event_id` (added by the `event` module's field definition with `index='btree_not_null'` on the relation field) and on `state` (standard index on Selection fields). For large-scale mailings, the dominant cost is email delivery (SMTP throughput), not the database query.

### `ir.model` Ref Lookup on Each Action Call

Each action method calls `self.env.ref('event.model_event_registration')` and `self.env.ref('base.model_res_partner')`. These are XML ID lookups (`ir.model.data` table). After the first call, they are cached in the Odoo registry. The overhead per call is a dictionary lookup into the cached registry, not a SQL query.

---

## Edge Cases and Known Limitations

### Multi-event action with `self.name`

When `action_mass_mailing_attendees` is called from a list view with multiple events selected, `self.name` returns the display name of the first record in the recordset. The pre-filled subject will show only the first event's name. Workaround: user manually edits the subject after the form opens.

### `seats_taken == 0` button visibility edge case

If all registrations are cancelled after the form is loaded, `seats_taken` recomputes to 0, but the "Contact Attendees" button visibility is only re-evaluated on form reload. On a live form session, the button would remain visible even though the mailing would target zero recipients. This is standard Odoo web client behavior for `invisible` on non-stored computed fields.

### Blocked registrations not excluded by default

The fallback domain `[('state', 'not in', ['cancel', 'draft'])]` does not exclude registrations in a `blocked` state. While `event.registration` doesn't have a `blocked` state by default, a customization or workflow could add one. If stricter filtering is needed, override `_mailing_get_default_domain` to use `[('state', '=', 'open')]`.

### `mailing_filter_id` bypasses `_mailing_get_default_domain`

If a user has a saved `mailing.filter` record for `event.registration`, selecting it in the mailing form's **Favorite Filter** field causes `_compute_mailing_domain` to use `mailing_filter_id.mailing_domain` instead of calling `_get_default_mailing_domain`. This means the event-specific domain set by `action_mass_mailing_attendees` would be replaced. The user must not select a conflicting filter.

### Email normalization and blacklist

`event.registration.email` is a plain Char field (not normalized). The mass mailing engine normalizes emails using `email_normalize` from `odoo.tools` before checking against the blacklist. This means `john.doe@example.com` and `John Doe <john.doe@example.com>` are treated as the same address. However, malformed emails stored in the registration may not be normalized correctly and could cause delivery failures.

---

## Extension Points

| Goal | How to Extend |
|------|--------------|
| Add tag-based recipient filter | Override `_mailing_get_default_domain` to add `[('partner_id.category_id', 'in', tag_ids)]` |
| Exclude registrations without partner | Override `_mailing_get_default_domain` to add `[('partner_id', '!=', False)]` |
| Exclude checked-in attendees (only open) | Override `_mailing_get_default_domain` to use `[('state', '=', 'open')]` instead of the fallback |
| Pre-select a mailing template | Add `default_body_template_id` to the action context |
| Pre-select a mailing list | Add `default_contact_list_ids` to the action context (for `res.partner` mailing) |
| Custom subject per event type | Override `action_mass_mailing_attendees` to read `event.event_type_id.name` and format the subject accordingly |
| Add "Remind No-Shows" button | Add to `event_views.xml` XPath and add corresponding method to `event_event.py` with `[('state', '=', 'done')]` domain |
| Custom partner segment for invites | Override `action_invite_contacts` to add `default_mailing_domain` for a specific partner segment |

---

## Related Documentation

- [Modules/event](event.md) -- `event.event`, `event.registration`, registration states, seat management, computed fields (`is_finished`, `event_registrations_open`, `seats_taken`)
- [Modules/mass_mailing](mass_mailing.md) -- `mailing.mailing`, `mailing.trace`, `mailing.filter`, `_mailing_get_default_domain` call site, recipient domain resolution, blacklist handling
- [Core/API](API.md) -- `@api.depends`, `@api.model`, computed fields, `_()` translation function, `@api.constrains`
- [Patterns/Inheritance Patterns](Inheritance Patterns.md) -- `_inherit` classical inheritance used here; `_inherits` vs. `_inherit` distinction
- [Core/Fields](Fields.md) -- Field type reference (`_mailing_enabled` is a class attribute, not a field)
- [Tools/ORM Operations](ORM Operations.md) -- `search()`, `browse()`, domain operators (`in`, `not in`)
- [Core/HTTP Controller](HTTP Controller.md) -- note: this module has no HTTP routes; all interactions are via ORM action methods

---

## Tags

`#odoo` `#odoo19` `#modules` `#mass_mailing` `#event` `#mailing` `#integration` `#bridge-module`