---
Module: event_crm
Version: Odoo 18
Type: Integration
Tags: [odoo, odoo18, crm, event, lead-generation, automation]
RelatedModules: [event, crm]
---

# event_crm — Event CRM Lead Generation

> Converts event registrations into CRM leads and opportunities automatically. Bridges the gap between event attendance and sales pipeline.

**Depends:** `event`, `crm`
**Category:** Marketing/Events
**auto_install:** `True`

---

## Overview

The `event_crm` module automatically creates CRM leads or opportunities when visitors register for, confirm, or attend events. It provides configurable rules (`event.lead.rule`) to control when, how, and for whom leads are generated. The system supports both B2C (per-attendee lead creation) and B2B (per-order/group lead creation) modes.

---

## Models

### `event.lead.rule` — Lead Generation Rules

Primary model for configuring automatic lead creation. Each rule defines a trigger (when), a scope (which events/registrations), and defaults for the resulting lead.

```python
class EventLeadRule(models.Model):
    _name = "event.lead.rule"
    _description = "Event Lead Rules"
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required) | Human-readable rule name |
| `active` | Boolean (default=True) | Enable/disable the rule |
| `lead_ids` | One2many `crm.lead` | Leads created by this rule (reverse of `event_lead_rule_id`) |
| `lead_creation_basis` | Selection (required, default=`attendee`) | `attendee` = one lead per registration (B2C); `order` = one lead per group/batch (B2B) |
| `lead_creation_trigger` | Selection (required, default=`create`) | `create` = on registration creation; `confirm` = on state=open; `done` = on attendance |
| `event_type_ids` | Many2many `event.type` | Filter: only apply to these event templates (OR logic with `event_id`) |
| `event_id` | Many2one `event.event` | Filter: only apply to this specific event (OR logic with `event_type_ids`) |
| `company_id` | Many2one `res.company` | Filter: event must belong to this company |
| `event_registration_filter` | Text (domain string) | Custom domain filter applied to registrations |
| `lead_type` | Selection (required, default=lead/opportunity based on user groups) | `lead` or `opportunity` — type assigned to created leads |
| `lead_sales_team_id` | Many2one `crm.team` | Assign created leads to this sales team |
| `lead_user_id` | Many2one `res.users` | Assign created leads to this salesperson |
| `lead_tag_ids` | Many2many `crm.tag` | Tags automatically added to created leads |

#### Key Methods

**`_run_on_registrations(registrations)`**
Main execution method. Called by event.registration hooks. Performs:
1. Deduplication — skips registrations already linked to a lead for this rule
2. Filtering — applies `event_type_ids`, `event_id`, `company_id`, and `event_registration_filter`
3. Grouping — for `order`-based rules, groups registrations by (event, create_date)
4. Lead creation — attendee-based: creates one lead per registration; order-based: creates one lead per group, or updates existing

```python
# Simplified logic
for rule in self:
    if rule.lead_creation_basis == 'attendee':
        for registration in matching_registrations:
            lead_vals_list.append(registration._get_lead_values(rule))
    else:  # order-based
        for (existing_lead, group_key, group_registrations) in groups:
            if existing_lead:
                existing_lead.write({'registration_ids': [(4, r.id) for r in group_registrations]})
            else:
                lead_vals_list.append(group_registrations._get_lead_values(rule))
return self.env['crm.lead'].create(lead_vals_list)
```

**`_filter_registrations(registrations)`**
Applies all rule conditions. Key logic:
- `event_registration_filter` → evaluated as domain via `filtered_domain()`
- `company_id` → `registration.company_id == rule.company_id`
- `event_id` / `event_type_ids` → OR relationship: matches if event_id equals OR event_type_id is in event_type_ids
- If neither event nor event_type filter set → all events pass

#### Trigger Selection Guide

| Trigger | When It Fires | Best For |
|---------|--------------|----------|
| `create` | `event.registration.create()` | Website event registration, instant lead gen |
| `confirm` | `write({'state': 'open'})` | Manual confirmations, sales team validates attendees |
| `done` | `write({'state': 'done'})` | High-confidence leads, attended confirmed |

---

### `event.registration` — Extended

`event_crm` extends `event.registration` with lead-generation hooks and contact tracking fields.

```python
class EventRegistration(models.Model):
    _inherit = 'event.registration'
```

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `lead_ids` | Many2many `crm.lead` (readonly) | Leads generated from this registration (B2C mode) |
| `lead_count` | Integer (computed) | Count of linked leads |

#### Methods — Lead Generation Triggers

**`create(vals_list)`**
- Calls `super().create(vals_list)`
- Calls `registrations._apply_lead_generation_rules()` unless context `event_lead_rule_skip` is set
- Handles `create` trigger rules immediately

**`write(vals)`**
- If `state` transitions to `open` → runs rules with `lead_creation_trigger = 'confirm'`
- If `state` transitions to `done` → runs rules with `lead_creation_trigger = 'done'`
- If tracked fields change (contact info) → calls `_update_leads()` to sync changes
- Uses `sudo()` for lead updates to bypass event ACL restrictions for CRM users

**`_apply_lead_generation_rules()`**
- Searches all active rules for each trigger type (`create`, `confirm`, `done`)
- Only processes registrations in the matching state
- Returns created leads

**`_update_leads(new_vals, lead_tracked_vals)`**
- Called when registration contact fields are updated
- Distinguishes `attendee`-based leads (update per-registration) from `order`-based leads (update per-group)
- Re-computes contact info if `partner_id` changed
- Appends update descriptions to lead body

#### Methods — Contact Extraction

**`_get_lead_values(rule)`**
Builds the dictionary for `crm.lead` creation:
```python
{
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
    # + contact vals (partner or raw contact)
    # + description HTML
}
```

**`_get_lead_contact_values()`**
Smart contact resolution:
- Finds first non-public-partner registration → use that `partner_id`
- If single registration with partner: validates email/phone match before assigning partner
  - Uses `tools.email_normalize()` for email comparison
  - Uses `_phone_format()` for phone comparison
- If partner valid: calls `crm.lead._prepare_values_from_partner()`
- If no partner: uses raw `name`, `email`, `phone` from registration
- Lead name: `{event_name} - {contact_name}`

**`_get_lead_description(prefix, line_counter, line_suffix)`**
- Generates HTML description: `<prefix><br/><ol><li>registration info...</li>...</ol>`
- Each `<li>` includes name, email, phone
- Used for both initial creation and update appends

**`_get_lead_grouping(rules, rule_to_new_regs)`**
- Groups registrations by `(create_date, event_id)`
- Returns list of groups for each order-based rule
- Each group is a tuple: `(existing_lead, group_key, group_registrations)`

**`_get_lead_tracked_values()`**
- Returns pre-write field values for contact + description fields
- Union of `_get_lead_contact_fields()` and `_get_lead_description_fields()`
- Used by `_update_leads()` to detect what changed

#### Tool Methods

| Method | Purpose |
|--------|---------|
| `_get_lead_contact_fields()` | Returns `['name', 'email', 'phone', 'partner_id']` — fields that affect lead contact |
| `_get_lead_description_fields()` | Returns `['name', 'email', 'phone']` — fields that affect lead description |
| `_find_first_notnull(field_name)` | Returns first non-null value for a field across the recordset |
| `_convert_value(value, field_name)` | Converts relational field values to plain IDs for write() |

---

### `crm.lead` — Extended

```python
class Lead(models.Model):
    _inherit = 'crm.lead'
```

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `event_lead_rule_id` | Many2one `event.lead.rule` | The rule that created this lead |
| `event_id` | Many2one `event.event` (index btree_not_null) | Source event |
| `registration_ids` | Many2many `event.registration` | All registrations feeding into this lead |
| `registration_count` | Integer (computed) | Count of linked registrations |

#### Methods

**`_compute_registration_count()`**
Simply `len(record.registration_ids)`.

**`_merge_dependences(opportunities)`**
When merging leads via CRM merge wizard:
- Uses `sudo()` to merge `registration_ids` across all opportunities
- Bypasses event access rights (CRM users may not have event registration ACLs)

**`_merge_get_fields()`**
Adds `event_lead_rule_id` and `event_id` to the list of fields preserved during merge (from base `crm.lead`).

---

### `event.event` — Extended

```python
class EventEvent(models.Model):
    _name = "event.event"
    _inherit = "event.event"
```

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `lead_ids` | One2many `crm.lead` | Leads generated from this event |
| `lead_count` | Integer (computed) | Count of linked leads |
| `has_lead_request` | Boolean (computed sudo) | True if a `event.lead.request` is currently processing for this event |

#### Methods

**`action_generate_leads()`**
Manual action triggered by the event manager. Logic:
- Counts non-draft/non-cancelled registrations
- If count <= `_REGISTRATIONS_BATCH_SIZE` (200): runs synchronously
- If count > 200: creates `event.lead.request` record + triggers CRON `event_crm.ir_cron_generate_leads`
- Returns display notification with result count

**`_compute_lead_count()`** — `_read_group` on `crm.lead` grouped by `event_id`
**`_compute_has_lead_request()`** — checks `event.lead.request` record existence

---

### `event.lead.request` — Batch Processing Queue

Technical model for handling large-volume lead generation asynchronously.

```python
class EventLeadRequest(models.Model):
    _name = "event.lead.request"
    _log_access = False
    _rec_name = "event_id"
    _order = "id asc"
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | Many2one `event.event` (required, ondelete=cascade) | Target event |
| `processed_registration_id` | Integer | ID of the last processed registration — cursor for resumption |

#### SQL Constraints

```python
_sql_constraints = [
    ('uniq_event', 'unique(event_id)',
     'You can only have one generation request per event at a time.')
]
```

#### CRON: `_cron_generate_leads(job_limit=100, registrations_batch_size=None)`

Processes pending requests in batches:
1. Searches all `event.lead.request` records
2. For each: loads next batch of registrations (up to `_REGISTRATIONS_BATCH_SIZE` = 200)
3. Calls `registrations._apply_lead_generation_rules()`
4. If batch incomplete → updates `processed_registration_id` cursor
5. If batch complete → unlinks the request record
6. Auto-commits after each batch/request (avoids duplicating emails)
7. If requests remain → re-triggers itself via `ir_cron_generate_leads`

---

## Integration Flow

```
Visitor registers to event
         │
         ▼
event.registration.create()
         │
         ├── trigger=create ──► event.lead.rule._run_on_registrations()
         │
         ▼
Registration confirmed (state='open')
         │
         ├── trigger=confirm ──► event.lead.rule._run_on_registrations()
         │
         ▼
Attendee marked done (state='done')
         │
         ├── trigger=done ──► event.lead.rule._run_on_registrations()
         │
         ▼
crm.lead created/updated
  • event_id linked
  • registration_ids linked
  • contact from registration/partner
  • UTM fields from registration
  • tags/team/user from rule defaults
```

---

## L4: Architecture Notes

**No duplicate creation:** Before creating, `_run_on_registrations()` searches for existing leads with matching `(registration_ids, event_lead_rule_id)`. Existing leads are updated instead.

**Commercial trigger avoidance:** Import operations (`_load_records_create`, `_load_records_write`) skip rule execution entirely via `event_lead_rule_skip` context. Prevents bootstrapping data from spawning spurious leads.

**B2B grouping:** Order-based rules group registrations by `(create_date, event_id)`. This handles the `website_event` batch-creation flow where multiple registrations are created in a single `create_multi` call. When a new group arrives, it creates a new lead; subsequent batches append registrations to the same lead.

**CRM ↔ Event ACL bridge:** Lead updates use `sudo()` because CRM users (sales team) may lack `event.registration` access rights. The registration → lead link is always established via `sudo()`.

**UTM propagation:** `_get_lead_values()` extracts `campaign_id`, `source_id`, `medium_id` from the first registration in the batch via `_find_first_notnull()`. Registrations carry these from the website session tracking.

**Phone normalization:** `_get_lead_contact_values()` uses the partner's `country_id` to format the registration phone before comparing, avoiding false mismatches due to country-code differences.

---

## Security

- `event_lead_rule.lead_ids`: `sales_team.group_sale_salesman`
- `crm.lead.registration_ids`: `event.group_event_registration_desk`
- `event.event.lead_ids`: `sales_team.group_sale_salesman`
- Merge operations use `sudo()` to traverse event registration links

## Data Files

- `data/crm_lead_merge_template.xml` — lead merge template
- `data/ir_cron_data.xml` — CRON scheduling for batch lead generation
- `security/event_crm_security.xml` — record rules
