---
Module: mass_mailing_event
Version: Odoo 18
Type: Integration
Tags: #odoo18, #mass-mailing, #event, #integration
---

# Mass Mailing Event Module (`mass_mailing_event`)

## Overview

**Category:** Hidden
**Depends:** `event`, `mass_mailing`
**Auto-install:** Yes
**License:** LGPL-3

The `mass_mailing_event` module bridges the **Event** and **Mass Mailing** modules. It enables organizers to send email campaigns directly to event registrants and to invite contacts to events, all without leaving the event form. It achieves this by:

1. Adding two action buttons to the `event.event` form view
2. Enabling `event.registration` as a valid mailing recipient model
3. Providing a context-aware default domain for mailing target selection

## Models Extended

### `event.event` — Extended by `mass_mailing_event`

**File:** `models/event_event.py`
**Inheritance:** `_inherit = 'event.event'`

Two action methods are added to open the mailing composer in target mode.

#### Methods

**`action_mass_mailing_attendees()`** — Object button action

Opens a new `mailing.mailing` form pre-configured to send to confirmed event attendees.

```python
context: {
    'default_mailing_model_id': self.env.ref('event.model_event_registration').id,
    'default_mailing_domain': repr([('event_id', 'in', self.ids),
                                     ('state', 'not in', ['cancel', 'draft'])]),
    'default_subject': _("Event: %s", self.name),
}
```

**Domain pre-populated:** `[('event_id', 'in', <current_event_ids>), ('state', 'not in', ['cancel', 'draft'])]`
- Excludes cancelled and draft registrations
- Supports multi-event selection (when button is on a kanban/list context with multiple selected events)

**`action_invite_contacts()`** — Object button action

Opens a new `mailing.mailing` form targeting all contacts in the database (res.partner), for sending event invitations. Unlike `action_mass_mailing_attendees`, this is for outreach to people who have NOT yet registered.

```python
context: {
    'default_mailing_model_id': self.env.ref('base.model_res_partner').id,
    # no default_mailing_domain — all partners are potential invitees
    'default_subject': _("Event: %s", self.name),
}
```

#### Buttons in the Form View

**File:** `views/event_views.xml`

The form extension adds three elements to `event.event` form (`event.view_event_form`):

| Element | Type | Condition | Style |
|---------|------|-----------|-------|
| `action_invite_contacts` | Button | Visible when `is_finished=False` and `event_registrations_open=True` | Primary (btn-primary) |
| `action_invite_contacts` | Button | Visible when `is_finished=False` and no open registrations | Secondary (btn-secondary) |
| `action_mass_mailing_attendees` | Button | Visible only when `seats_taken > 0` | Secondary |

The `event_registrations_open` field is a related/computed boolean from the event model (indicates whether registration is open). The button is invisible for finished events (`is_finished=True`).

---

### `event.registration` — Extended by `mass_mailing_event`

**File:** `models/event_registration.py`
**Inheritance:** `_inherit = 'event.registration'`

#### Class Attribute

**`_mailing_enabled = True`**

This is a class-level flag (not a field) that marks `event.registration` as a valid mailing recipient model. The `mass_mailing` module's `mailing.mailing.mailing_model_id` field has a domain of `is_mailing_enabled = True`. Setting `_mailing_enabled = True` on a model registers it as a mailing target without requiring any additional configuration.

#### Methods

**`_mailing_get_default_domain(mailing)`** — Mailing mixin method

Returns the default filter domain for a mailing that targets `event.registration`. Called by the mailing composer to pre-populate the "Targeted recipients" domain field.

```python
def _mailing_get_default_domain(self, mailing):
    default_mailing_model_id = self.env.context.get('default_mailing_model_id')
    default_mailing_domain = self.env.context.get('default_mailing_domain')
    if (default_mailing_model_id and
        mailing.mailing_model_id.id == default_mailing_model_id and
        default_mailing_domain):
        return ast.literal_eval(default_mailing_domain)
    return [('state', 'not in', ['cancel', 'draft'])]
```

**Logic:**

1. If the mailing was opened via `action_mass_mailing_attendees()` (from an event form), both `default_mailing_model_id` and `default_mailing_domain` are set in the context.
2. The method evaluates the domain safely using `ast.literal_eval()` and returns it.
3. If the mailing was opened directly (not from an event), it returns a generic fallback domain: `[('state', 'not in', ['cancel', 'draft'])]` — excluding cancelled and draft registrations across all events.

## Views

### Form Extension: `event.event`

**File:** `views/event_views.xml`

Extends `event.view_event_form` with three elements injected via XPath at `//field[@name='stage_id']`:

```xml
<field name="event_registrations_open" invisible="1"/>
<button name="action_invite_contacts" type="object" string="Invite"
    class="btn btn-primary"
    groups="mass_mailing.group_mass_mailing_user"
    invisible="is_finished or not event_registrations_open"/>
<button name="action_invite_contacts" type="object" string="Invite"
    class="btn btn-secondary"
    groups="mass_mailing.group_mass_mailing_user"
    invisible="is_finished or event_registrations_open"/>
<button name="action_mass_mailing_attendees" type="object"
    string="Contact Attendees"
    groups="mass_mailing.group_mass_mailing_user"
    invisible="seats_taken == 0"/>
```

**Security:** All three buttons require `mass_mailing.group_mass_mailing_user`. The `event_registrations_open` field is hidden (`invisible="1"`) — it's only used as a dependency for button visibility conditions.

## L4: Event Attendee Email Targeting — Deep Dive

### How the Mailing Model System Works

The mass mailing system uses a registration pattern for mailing-enabled models:

```
Model._mailing_enabled = True
        |
        v
ir.model.is_mailing_enabled  --> computed from model's _mailing_enabled
        |
        v
mailing.mailing.mailing_model_id  --> domain: [('is_mailing_enabled', '=', True)]
```

When a model sets `_mailing_enabled = True`, it becomes selectable in the mailing composer as a target model. The mailing trace system (`mailing.trace`) then automatically creates trace records for each recipient record.

### Registration State Flow

`event.registration` states:
- `draft` — Registration started but not confirmed
- `open` — Registration confirmed, attendee registered
- `done` — Attendee checked in at event
- `cancel` — Registration cancelled

**Default mailing domain:** `[('state', 'not in', ['cancel', 'draft'])]`

This means only `open` and `done` registrations receive mass mailing emails — draft registrations are unconfirmed, and cancelled registrations have explicitly opted out.

### Invite vs. Contact Attendees

| Action | Target Model | Recipients | Domain |
|--------|-------------|------------|--------|
| `action_invite_contacts` | `res.partner` | All partners in DB | None (full DB) |
| `action_mass_mailing_attendees` | `event.registration` | Confirmed registrants for selected event(s) | `event_id in ids, state not in cancel/draft` |

The invite action is intentionally unscoped — it's a broad invitation blast to all contacts, with no pre-filter. The subject line is pre-filled with the event name so the user can personalise the invitation body.

### Multi-Event Mailing

Both action methods use `self.ids` (not `self.id`) in the domain, meaning if multiple event records are selected (e.g., from a kanban view), the resulting mailing will target attendees from ALL selected events simultaneously:

```python
'domain': repr([('event_id', 'in', self.ids), ('state', 'not in', ['cancel', 'draft'])])
```

This enables cross-event campaigns (e.g., a series of webinars) where one mailing goes to registrants of any selected event.

### Traceability

When `event.registration` is the mailing model, the `mailing.trace` records link to individual `event.registration` IDs. The mailing trace system then:
- Tracks delivery status (sent, bounced, delivered)
- Records clicks and opens (via tracking pixels and link rewriting)
- Updates the registration's communication history

The `event.registration` record also carries a reference to `partner_id`, so even though mailing traces point to registration records, the actual email is sent to the partner's email address.
