---
tags:
  - odoo
  - odoo19
  - modules
  - crm
  - events
---

# event_crm

> Create leads from event registrations. Bridge module between `event` and `crm`.

- **Depends**: `event`, `crm`
- **Category**: Marketing/Events
- **Auto-install**: `True` — installs automatically when both `event` and `crm` are present
- **License**: LGPL-3
- **Website**: https://www.odoo.com/app/events

---

## Overview

`event_crm` bridges the [[Modules/event]] and [[Modules/CRM]] modules. When attendees register for events (or confirm attendance, or attend), the module can automatically create `crm.lead` records — typed either as `lead` or `opportunity` — pre-populated with contact information from the registration.

The core mechanism is the **Lead Generation Rule** (`event.lead.rule`), a configurable object that defines:
- **When** to trigger (on creation, confirmation, or attendance)
- **Whether** to create one lead per attendee or one lead per order/batch
- **Which** events or event categories to match
- **What defaults** to apply to the created lead

All generated leads carry a back-reference to the generating `event.lead.rule` and the `event.event`, enabling full CRM attribution and event-source reporting.

---

## Architecture

```
event.registration  ──(create/write)──>  event.lead.rule  ──>  crm.lead
       │                                        │
       │                                        ├── lead_creation_trigger: create | confirm | done
       │                                        ├── lead_creation_basis:  attendee | order
       │                                        ├── event_registration_filter (domain)
       │                                        └── lead_type / lead_user_id / lead_tag_ids
       │
       └── lead_ids (Many2many), lead_count (computed)

event.event  ──lead_ids / lead_count──>  crm.lead
crm.lead    ──event_lead_rule_id / event_id / registration_ids──>  event
```

---

## Module Files

| File | Role |
|---|---|
| `__manifest__.py` | Auto-install on event+crm; loads security, data, views |
| `models/event_registration.py` | Core: extends `event.registration` with lead lifecycle hooks |
| `models/event_lead_rule.py` | Rule model: trigger conditions, defaults, `_run_on_registrations` |
| `models/event_lead_request.py` | Batch/CRON technical model for large events |
| `models/crm_lead.py` | Extends `crm.lead`: event attribution, merge support |
| `models/event_event.py` | Extends `event.event`: lead_ids, lead_count, action_generate_leads |
| `models/event_question_answer.py` | Quick-action to create rule from a question answer |
| `security/ir.model.access.csv` | ACLs for `event.lead.rule` and `event.lead.request` |
| `security/event_crm_security.xml` | Multi-company `ir.rule` on `event.lead.rule` |
| `data/ir_cron_data.xml` | CRON job definition for batch lead generation |
| `data/ir_action_data.xml` | Server action `action_generate_leads` bound to `event.event` |
| `data/crm_lead_merge_template.xml` | Merge summary QWeb template inheritance |
| `views/*.xml` | Form/list/search views for all models |

---

## Models

### event.registration (extended)

**File**: `models/event_registration.py`

The central model. Every registration write that changes contact info or state may trigger lead generation or lead updates.

#### Fields added by event_crm

| Field | Type | Groups | Notes |
|---|---|---|---|
| `lead_ids` | `Many2many('crm.lead')` | `sales_team.group_sale_salesman` | All leads generated from this registration; `copy=False`, `readonly=True` |
| `lead_count` | `Integer` (computed, `compute_sudo=True`) | — | Count of `lead_ids`; `_compute_lead_count` |

#### `_compute_lead_count`

```python
@api.depends('lead_ids')
def _compute_lead_count(self):
    for record in self:
        record.lead_count = len(record.lead_ids)
```

`compute_sudo=True` means the count is always computed with elevated privileges — critical because a CRM user who lacks event desk access must still see lead counts on their registrations.

#### `create(vals_list)` — Override

```python
@api.model_create_multi
def create(self, vals_list):
    registrations = super(EventRegistration, self).create(vals_list)
    if not self.env.context.get('event_lead_rule_skip'):
        registrations._apply_lead_generation_rules()
    return registrations
```

**L3 — State-aware trigger**: Registrations created with `state='open'` (already confirmed) will immediately trigger both `create` rules and `confirm` rules. Registrations created with `state='done'` trigger all three trigger types. This is handled dynamically in `_apply_lead_generation_rules`.

**L4 — Skip context**: The `event_lead_rule_skip` flag prevents rule execution during:
- Data imports (`_load_records_create` / `_load_records_write`)
- Demo data bootstrap
- Any programmatic batch where rule execution is undesirable

#### `write(vals)` — Override

```python
def write(self, vals):
    to_update, event_lead_rule_skip = False, self.env.context.get('event_lead_rule_skip')
    if not event_lead_rule_skip:
        to_update = self.filtered(lambda reg: reg.lead_count)
    if to_update:
        lead_tracked_vals = to_update._get_lead_tracked_values()

    res = super(EventRegistration, self).write(vals)

    if not event_lead_rule_skip and to_update:
        self.env.flush_all()
        to_update.sudo()._update_leads(vals, lead_tracked_vals)

    # handle triggers based on state
    if not event_lead_rule_skip:
        if vals.get('state') == 'open':
            self.env['event.lead.rule'].search([
                ('lead_creation_trigger', '=', 'confirm')]).sudo()._run_on_registrations(self)
        elif vals.get('state') == 'done':
            self.env['event.lead.rule'].search([
                ('lead_creation_trigger', '=', 'done')]).sudo()._run_on_registrations(self)

    return res
```

**L3 — Dual purpose**: `write` handles both lead *creation* (state transitions) and lead *update* (contact field changes). The order of operations:
1. Capture old tracked values **before** write
2. Perform the write
3. `flush_all()` to recompute partner-based computed fields
4. Update existing leads with new contact info if relevant fields changed
5. Search and run rules matching the new state

**L4 — Performance**: `flush_all()` inside a write is intentional but expensive. It ensures partner-based computed fields on registration are flushed to the DB before `_update_leads` reads them. In high-volume batch writes (e.g., website_event portals), consider batching outside the ORM to reduce flush overhead.

**L4 — Idempotency guard**: Only registrations that already have `lead_count > 0` are considered for lead updates. New registrations without leads skip the update path entirely.

#### `_apply_lead_generation_rules(event_lead_rules=False)`

```python
def _apply_lead_generation_rules(self, event_lead_rules=False):
    leads = self.env['crm.lead']
    open_registrations = self.filtered(lambda reg: reg.state == 'open')
    done_registrations = self.filtered(lambda reg: reg.state == 'done')

    if not event_lead_rules:
        search_triggers = ['create']
        if open_registrations:   search_triggers.append('confirm')
        if done_registrations:   search_triggers.append('done')
        event_lead_rules = self.env['event.lead.rule'].search([
            ('lead_creation_trigger', 'in', search_triggers)])

    create_lead_rules   = event_lead_rules.filtered(lambda r: r.lead_creation_trigger == 'create')
    leads += create_lead_rules.sudo()._run_on_registrations(self)
    if open_registrations:
        leads += confirm_lead_rules.sudo()._run_on_registrations(open_registrations)
    if done_registrations:
        leads += done_lead_rules.sudo()._run_on_registrations(done_registrations)
    return leads
```

**L3 — Smart trigger selection**: If no explicit `event_lead_rules` are passed, the method dynamically determines which trigger types to search for based on the actual states in `self`. Registrations in `draft` or `cancel` state are excluded entirely from rule execution.

#### `_get_lead_values(rule)`

```python
def _get_lead_values(self, rule):
    sorted_self = self.sorted("id")
    lead_values = {
        'type': rule.lead_type,
        'user_id': rule.lead_user_id.id,
        'team_id': rule.lead_sales_team_id.id,
        'tag_ids': rule.lead_tag_ids.ids,
        'event_lead_rule_id': rule.id,
        'event_id': self.event_id.id,
        'referred': self.event_id.name,
        'registration_ids': self.ids,
        'campaign_id': sorted_self._find_first_notnull('utm_campaign_id'),
        'source_id': sorted_self._find_first_notnull('utm_source_id'),
        'medium_id': sorted_self._find_first_notnull('utm_medium_id'),
    }
    lead_values.update(sorted_self._get_lead_contact_values())
    lead_values['description'] = sorted_self._get_lead_description(...)
    return lead_values
```

**L3**: UTM fields (`campaign_id`, `source_id`, `medium_id`) are populated from the registration's UTM links. The `referred` field stores the event name as the "referred" attribution field on the lead. Registration IDs are stored as a Many2many on the lead — the canonical link for lead↔registration tracking.

#### `_get_lead_contact_values()`

Handles complex partner-to-lead contact resolution.

**L3 — Partner matching rules** (mono-registration path, `len(self) == 1`):

1. Exclude `base.public_partner` — anonymous/public registrations are treated as no-partner
2. If a partner is found, validate **email normalization match**: strict `email_normalized` comparison; fallback to raw `email` string comparison if `email_normalized` is not set on the partner
3. If a partner is found, validate **phone format match**: both sides are normalized via `phone_validation` before comparison; if either side cannot be formatted, raw string comparison is used
4. If either email or phone mismatches, `valid_partner` is cleared and contact info is built from registration fields only

**L3 — Contact population**:
- If `valid_partner` exists: calls `crm.lead._prepare_values_from_partner()` (Odoo's standard partner-to-lead sync) and forces `email_from`/`phone` only if partner lacks those values
- If no `valid_partner`: builds contact from registration fields directly (`contact_name`, `email_from`, `phone`)

**L3 — Lead name**: Always constructed as `f"{event.name} - {contact_name}"` where `contact_name` is partner name, registration name, or first email — whichever is found first via `_find_first_notnull`.

#### `_get_lead_description(prefix='', line_counter=True, line_suffix='')`

Builds the HTML description block on the lead. Uses `<ol>` when `line_counter=True` (participant lists), `<ul>` when `line_counter=False` (update logs). Each line includes name, email, phone, and an optional suffix (e.g., `"(updated)"`).

#### `_update_leads(new_vals, lead_tracked_vals)`

Called after a registration write when the registration already has leads. Updates contact info and description on those leads.

**L3 — Attendee-based leads**: If any tracked contact or description field changed, recomputes and writes the new values. Description is appended (not replaced) — a new `<li>` entry is added with the `prefix` message.

**L3 — Order-based leads**: Only partner changes trigger a contact update. If the new partner differs from the lead's current partner, the new registration details are appended to the description.

#### `_get_lead_tracked_values()`

Captures the union of `_get_lead_contact_fields()` and `_get_lead_description_fields()` values **before** a write, for use in `_update_leads` to detect which fields actually changed.

#### `_get_lead_grouping(rules, rule_to_new_regs)` — Order-based grouping

```python
grouped_registrations = {
    (create_date, event): sub_registrations
    for event, registrations in self.grouped('event_id').items()
    for create_date, sub_registrations in registrations.grouped('create_date').items()
}
```

**L3**: Grouping key is `(create_date, event_id)` — registrations created in the same batch on the same event form one group. In the website_event flow, registrations are created in one `create_multi` call for the same website session. Using `create_date` at second-level precision prevents grouping registrations from different days.

#### Tool methods

```python
@api.model
def _get_lead_contact_fields(self):      # → ['name', 'email', 'phone', 'partner_id']

@api.model
def _get_lead_description_fields(self): # → ['name', 'email', 'phone']

def _find_first_notnull(self, field_name):  # Returns first non-False value across self

def _convert_value(self, value, field_name): # Handles many2one/many2many → ids
```

These are `@api.model` methods — extensible by further inheritance. For example, `event_sale` may add `sale_order_line_id` to `_get_lead_description_fields`.

---

### event.lead.rule

**File**: `models/event_lead_rule.py`

The primary configuration object for lead generation. Accessed via **Events → Configuration → Lead Generation**.

#### Fields

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | `Char` | Yes | — | `translate=True` for i18n |
| `active` | `Boolean` | — | `True` | Archiving disables the rule without deleting it |
| `lead_ids` | `One2many('crm.lead')` | — | — | Inverse of `event_lead_rule_id`; read-only in UI |
| `lead_creation_basis` | `Selection` | Yes | `'attendee'` | `'attendee'` = B2C (one lead/registration); `'order'` = B2B (one lead/group) |
| `lead_creation_trigger` | `Selection` | Yes | `'create'` | `'create'` / `'confirm'` / `'done'` |
| `event_type_ids` | `Many2many('event.type')` | — | — | Filter: match event category |
| `event_id` | `Many2one('event.event')` | — | — | Filter: specific event; domain restricted to `company_id` |
| `company_id` | `Many2one('res.company')` | — | — | Multi-company restriction |
| `event_registration_filter` | `Text` (domain string) | — | — | Custom filter on `event.registration` |
| `lead_type` | `Selection` | Yes | `(user pref)` | `'lead'` or `'opportunity'`; default via lambda checking `crm.group_use_lead` |
| `lead_sales_team_id` | `Many2one('crm.team')` | — | — | Default team on created leads |
| `lead_user_id` | `Many2one('res.users')` | — | — | Default salesperson; auto-filled from `lead_sales_team_id.user_id` |
| `lead_tag_ids` | `Many2many('crm.tag')` | — | — | Tags applied to all created leads |

#### `lead_type` Default Logic

```python
default=lambda self: 'lead' if self.env.user.has_group('crm.group_use_lead') else 'opportunity'
```

**L3**: If the current user (at rule creation time) has the "Lead" feature enabled in CRM settings, new leads default to type `lead`. Otherwise they default to `opportunity`. This is a one-time default evaluated at record creation; changing the rule later does not retroactively change already-created leads.

#### `_onchange_lead_sales_team_id`

When a sales team is set, `lead_user_id` is auto-populated from `team.user_id`. Setting a blank team clears `lead_user_id`.

#### `_filter_registrations(registrations)`

**L3 — Three-layer filter**:
1. **`event_registration_filter`**: Parsed with `literal_eval`, applied as `filtered_domain`. Example from demo: `[('email','ilike','@example.com')]`
2. **Company check**: Direct `company_id` comparison on the registration's event — no sub-search
3. **Event/category check**: OR relationship between `event_id` and `event_type_ids`. If both are set, either match passes. If neither is set, all events match

**L4**: The lambdas avoid a search in the common case where neither event nor type filters are set (`self.event_id or self.event_type_ids` is falsy → returns `True` for all registrations immediately, skipping all filtering overhead).

#### `_run_on_registrations(registrations)`

The main execution engine. Returns **newly created leads only**; updated leads are not in the return value.

**Deduplication logic**:
```python
existing_leads = self.env['crm.lead'].with_context(active_test=False).search([
    ('registration_ids', 'in', registrations.ids),
    ('event_lead_rule_id', 'in', self.ids)
])
```
`active_test=False` means even **lost leads** block duplicate creation. This prevents re-creating leads when a registration state changes back and forth.

**L3 — Multiple rules = multiple leads**: All matching rules are applied. A single registration can generate multiple leads if multiple rules match — this is intentional for maximum flexibility.

**L3 — Order-based update**: For `lead_creation_basis == 'order'`, existing leads are updated (not recreated) and new registrations are appended to the lead's description.

#### `action_execute_rule()`

```python
def action_execute_rule(self):
    events = self.event_id or self.env['event.event'].search([('is_finished', '!=', True)])
    return events.action_generate_leads(event_lead_rules=self)
```

**L3**: If the rule has a specific `event_id`, only that event is processed. If no event is set (applies to all events), all unfinished events are processed. Triggered by the **Execute Rule** button on the rule form.

---

### event.lead.request

**File**: `models/event_lead_request.py`

A **technical/ephemeral** model for large-scale batch lead generation. Not meant for direct user interaction beyond seeing progress indicators.

#### Design Pattern: Batch Processing with CRON Self-Trigger

```
User clicks "Generate Leads" on large event
  → Creates event.lead.request records (one per event)
  → Triggers ir_cron_generate_leads
    → Processes up to 100 requests per CRON run
    → Each request processes 200 registrations at a time
    → If not finished: updates processed_registration_id, commits, re-triggers CRON
    → If finished: unlinks the request
```

#### Fields

| Field | Type | Notes |
|---|---|---|
| `event_id` | `Many2one('event.event')`, required, `ondelete='cascade'` | |
| `event_lead_rule_ids` | `Many2many('event.lead.rule')` | Optional rule filter; empty = all active rules |
| `processed_registration_id` | `Integer` | Cursor: last processed registration ID; next batch starts after this |

#### `_REGISTRATIONS_BATCH_SIZE = 200`

Each CRON iteration processes at most 200 registrations per event. This keeps individual CRON runs short and prevents timeouts.

#### `_uniq_event` Constraint

```python
_uniq_event = models.Constraint(
    'unique(event_id)',
    'You can only have one generation request per event at a time.',
)
```

**L3**: Prevents duplicate batch requests for the same event. If a CRON is still running for event X, a second user cannot queue another batch for event X.

#### `_cron_generate_leads(job_limit=100, registrations_batch_size=None)`

**L4 — Auto-commit**: After every batch completion (whether a single event finishes or all 100 requests finish), `self.env.cr.commit()` is called. This is critical because lead creation can trigger email sending (e.g., CRM stage-change notifications), and CRON restarts must not re-send those emails.

**L4 — CRON self-trigger**: If there are still unfinished requests after processing 100, the method calls `self.env.ref('event_crm.ir_cron_generate_leads')._trigger()` to immediately schedule another run, chaining CRON executions without waiting for the next scheduled interval.

---

### crm.lead (extended)

**File**: `models/crm_lead.py`

#### Fields added by event_crm

| Field | Type | Index | Groups | Notes |
|---|---|---|---|---|
| `event_lead_rule_id` | `Many2one('event.lead.rule')` | `btree_not_null` | — | Rule that created this lead |
| `event_id` | `Many2one('event.event')` | `btree_not_null` | — | Source event |
| `registration_ids` | `Many2many('event.registration')` | — | `event.group_event_registration_desk` | Source registrations |
| `registration_count` | `Integer` (computed) | — | `event.group_event_registration_desk` | |

**L3**: The `btree_not_null` index type (Odoo 13+) creates a partial index that only indexes non-null values. This is important for CRM lead reporting queries that filter on `event_id IS NOT NULL` without the storage overhead of a full index on a large table.

#### `_compute_registration_count`

```python
@api.depends('registration_ids')
def _compute_registration_count(self):
    for record in self:
        record.registration_count = len(record.registration_ids)
```

#### `_merge_dependences(opportunities)` — Override

When merging leads via the CRM merge wizard, registrations from all merged opportunities are added to the target lead:

```python
self.sudo().write({
    'registration_ids': [(4, registration.id) for registration in opportunities.sudo().registration_ids]
})
```

**L3**: `sudo()` is required because CRM users may not have event desk access rights. The `(4, id)` operator adds to the Many2many without removing existing registrations. All registrations from all merged leads end up on the target lead.

#### `_merge_get_fields()` — Override

Adds `event_lead_rule_id` and `event_id` to the list of fields merged (values are taken from the dominant lead in the merge).

---

### event.event (extended)

**File**: `models/event_event.py`

#### Fields

| Field | Type | Groups | Notes |
|---|---|---|---|
| `lead_ids` | `One2many('crm.lead', 'event_id')` | `sales_team.group_sale_salesman` | All leads from this event |
| `lead_count` | `Integer` (computed, `_compute_lead_count`) | `sales_team.group_sale_salesman` | Uses `_read_group` aggregation |

#### `_compute_lead_count`

Uses `_read_group` aggregation — the recommended Odoo pattern for counting One2many relations efficiently without loading all records.

#### `action_generate_leads(event_lead_rules=False)`

Server action entry point bound to `event.event` via `ir.actions.server` in `ir_action_data.xml`. Only event managers (`event.group_event_manager`) can trigger bulk regeneration.

**Threshold logic**:
```python
if registrations_count <= self.env['event.lead.request']._REGISTRATIONS_BATCH_SIZE:
    # synchronous execution
    leads = self.env['event.registration'].search([...])._apply_lead_generation_rules(event_lead_rules)
else:
    # queue for CRON
    self.env['event.lead.request'].sudo().create([{'event_id': event.id, ...} for event in self])
    self.env.ref('event_crm.ir_cron_generate_leads')._trigger()
```

---

### event.question.answer (extended)

**File**: `models/event_question_answer.py`

Provides a convenience **"Add a rule"** button on each answer option in the event question editor.

#### `action_add_rule_button()`

Pre-fills a new `event.lead.rule` form with:
- `name`: the answer text
- `lead_user_id`: the current user
- `event_registration_filter`: a domain matching registrations that selected this specific answer

```python
action['context'] = {
    'default_name': self.name,
    'default_lead_user_id': self.env.user.id,
    'default_event_registration_filter': [
        '&',
        ('registration_answer_ids.question_id', 'in', self.question_id.ids),
        ('registration_answer_choice_ids.value_answer_id', 'in', self.ids)
    ]
}
```

**L3**: The filter uses two nested relational paths — `registration_answer_ids` (the answers given by each registration) and `value_answer_id` (the selected answer option). This enables creating targeted leads for attendees who answered a specific question with a specific value, for example: *"Create a lead for all attendees who answered 'Interested in Enterprise tier'"*.

---

## Security Model

### ACLs (`ir.model.access.csv`)

| ID | Name | Model | Group | CRUD |
|---|---|---|---|---|
| `access_event_crm_registration` | event.lead.rule.user | `model_event_lead_rule` | `event.group_event_registration_desk` | Read |
| `access_event_crm_user` | event.lead.rule.user | `model_event_lead_rule` | `event.group_event_user` | Read |
| `access_event_crm_manager` | event.lead.rule.manager | `model_event_lead_rule` | `event.group_event_manager` | Full |
| `access_event_crm_salesman` | event.lead.rule.salesman | `model_event_lead_rule` | `sales_team.group_sale_salesman` | Read |
| `access_event_lead_request_system` | event.lead.request.system | `model_event_lead_request` | `base.group_system` | Full |

**L3**: Only system administrators can manage `event.lead.request` records. Regular users never see this model directly — it's purely an internal technical model for CRON orchestration.

### ir.rule: Multi-Company

```xml
<record id="ir_rule_event_crm" model="ir.rule">
    <field name="name">Event CRM: Multi Company</field>
    <field name="model_id" ref="model_event_lead_rule"/>
    <field name="groups" eval="[(4, ref('base.group_multi_company'))]"/>
    <field name="domain_force">[('company_id', 'in', company_ids + [False])]</field>
</record>
```

**L3**: Applies only when multi-company is enabled. A rule without a `company_id` set is visible to all companies. Rules with a `company_id` are only visible to users who have access to that company.

---

## CRON Jobs

### `ir_cron_generate_leads`

| Property | Value |
|---|---|
| Model | `event.lead.request` |
| Method | `model._cron_generate_leads()` |
| Schedule | Daily (`interval_number=1`, `interval_type='days'`) |
| Active | `True` |
| Self-triggering | Yes — chains via `._trigger()` until all requests are fulfilled |

---

## Lead Generation Lifecycle

```
Registration Created
  │
  ├─ create trigger rules → _run_on_registrations → crm.lead created
  │
  └─ if state already 'open' → confirm trigger rules also fire

Registration Confirmed (state='open')
  │
  └─ confirm trigger rules → _run_on_registrations → crm.lead created

Registration Done (state='done')
  │
  └─ done trigger rules → _run_on_registrations → crm.lead created

Registration Contact Info Updated (while registration has existing leads)
  │
  ├─ _get_lead_tracked_values (capture old vals)
  ├─ write() completes
  ├─ flush_all()
  └─ _update_leads(new_vals, old_vals) → lead contact fields / description updated
```

---

## Registration → Lead Field Mapping

| `event.registration` field | `crm.lead` field | Via |
|---|---|---|
| `event_id` | `event_id`, `referred` | `_get_lead_values` |
| `utm_campaign_id` | `campaign_id` | `_find_first_notnull` |
| `utm_source_id` | `source_id` | `_find_first_notnull` |
| `utm_medium_id` | `medium_id` | `_find_first_notnull` |
| `name` / `email` / `phone` / `partner_id` | `name`, `contact_name`, `email_from`, `phone`, `partner_id` | `_get_lead_contact_values` |
| All registrations in group | `description` (HTML `<ol>`/`<ul>`) | `_get_lead_description` |
| Rule defaults | `event_lead_rule_id`, `type`, `team_id`, `user_id`, `tag_ids` | From rule fields |

---

## UI Integration Points

| View | Injection point | What it adds |
|---|---|---|
| `event.registration` form | Button box | `lead_count` stat button → lead list (create disabled) |
| `crm.lead` form | After "Schedule Meeting" | `registration_count` stat button → registration list |
| `event.event` form | After Registrations button | `lead_count` stat button → lead list |
| `event.event` list | After `user_id` | `lead_count` column (optional hide) |
| `event.question` form | After answer options | "Add a rule" button on each answer row |
| Lead merge summary QWeb | After Marketing section | Event name and rule displayed |

---

## Performance Considerations

1. **Batch size limit (200)**: `event.lead.request` enforces a hard cap of 200 registrations per CRON iteration. Combined with per-request auto-commit, this limits DB lock duration and prevents email duplication.

2. **`active_test=False` in deduplication**: The deduplication sub-search in `_run_on_registrations` uses `active_test=False` to include lost leads. In databases with very large lead tables, consider whether a composite partial index on `(event_lead_rule_id)` with a filter `WHERE registration_ids IS NOT NULL` would improve this sub-search.

3. **`flush_all()` in write**: Called inside `EventRegistration.write()` to ensure partner-based fields are computed before `_update_leads` reads them. In high-volume event registration portals (e.g., `website_event`), this `flush_all()` across the entire transaction can be a bottleneck.

4. **`_read_group` for lead_count**: On `event.event`, `lead_count` uses `_read_group` aggregation instead of `len(lead_ids)` to avoid loading all lead records into memory.

5. **No rule re-runs on import**: `_load_records_create` and `_load_records_write` skip rule execution entirely via the `event_lead_rule_skip` context. This prevents demo data or data migration imports from inadvertently creating thousands of leads.

6. **Registration ID cursor**: The `processed_registration_id` cursor on `event.lead.request` uses integer ID comparison (`'>'`) rather than offset pagination. This is safe against deleted records: deleted registrations leave a gap that the cursor simply skips over on the next batch.

---

## Edge Cases

1. **Registration without email**: `_find_first_notnull('email')` returns `False`; `contact_name` then falls back to registration `name`, and if that's also absent, the email address itself is used as the contact name.

2. **Public partner registration**: `base.public_partner` registrations are treated as having no partner, forcing lead creation with contact info only (no `partner_id` on the lead).

3. **Lost lead deduplication**: With `active_test=False`, a lost (archived) lead still blocks duplicate creation. Unarchiving the lost lead resumes normal behavior — no leads are lost permanently.

4. **Order-based rule without sale order**: `_get_lead_grouping` groups by `(create_date, event_id)`. Without a sale order to group on, registrations from the same website session (same `create_date`) still form one lead per session.

5. **CRON re-entrancy guard**: The `_uniq_event` constraint on `event.lead.request` raises `UserError` if a user clicks "Generate Leads" on an event that already has a pending request, preventing duplicate batch queues.

6. **Registration deleted after lead creation**: Deleting a registration does **not** cascade-delete the lead. The `registration_ids` on the lead shows fewer registrations. The lead remains intact.

7. **Merging leads with different event_ids**: `_merge_get_fields` includes `event_id`, meaning the dominant lead's event wins in a merge. The `registration_ids` from all merged leads are combined via `_merge_dependences`.

8. **Phone comparison edge case**: If either the registration phone or the partner phone cannot be formatted (returns `False`), a raw string comparison `self.phone != valid_partner.phone` is used as fallback. This means `"+1-202-555-0122"` and `"+1 202 555 0122"` would be considered different if formatting fails for one side.

---

## Odoo 18 → 19 Changes

- **Phone normalization**: `_get_lead_contact_values()` now uses `phone_validation` (Odoo's `phone_formatted` helper) for phone comparisons, correctly handling international number formats instead of raw string comparisons.
- **`btree_not_null` indexes**: The `event_lead_rule_id` and `event_id` fields on `crm.lead` use the `btree_not_null` index type, which is more efficient than a full index for queries filtering on `IS NOT NULL`.
- **`lead_creation_basis` / `lead_creation_trigger` terminology**: The field names and selection values are stable across Odoo 18→19; no breaking renames in this area.
- **Registration → lead link**: The `registration_ids` Many2many on `crm.lead` (instead of One2many) allows a lead to track registrations from multiple rules or events after a merge, which was a known gap in earlier versions.

---

## See Also

- [[Modules/event]] — Event management (registration, event, ticket models)
- [[Modules/CRM]] — CRM/leads/opportunities
- `website_event` — Public event website with batch registration (powers "per order" grouping)
- `event_sale` — Paid events with sale order integration (sale_order-based grouping via `event_lead_rule` B2B mode)
