---
tags:
  - #odoo19
  - #modules
  - #website
  - #crm
  - #events
---

# website_event_crm

> Two-way bridge between website event registrations and CRM lead generation. Propagates visitor identity, preferred language, and survey answers into CRM leads.

## Module Overview

| Property | Value |
|----------|-------|
| Module | `website_event_crm` |
| Path | `odoo/addons/website_event_crm/` |
| Category | Website / Website |
| Version | `1.0` |
| Depends | `event_crm`, `website_event` |
| Auto-install | `True` |
| License | LGPL-3 |
| Author | Odoo S.A. |

**Purpose:** Allow per-order lead creation mode (enables `lead_creation_basis = 'order'` in the UI) and propagate visitor identity, preferred language, and registration question answers into CRM leads generated from website event registrations.

---

## Module Hierarchy

```
event_crm (base)                    website_event (peer dependency)
├── event.registration              ├── event.registration (+ visitor_id)
├── event.lead.rule                 └── website.visitor
└── crm.lead (+ registration_*)

website_event_crm (overlay)
├── event.registration             ← _get_lead_values (visitor + lang)
│                                   ← _get_lead_description_registration (answers)
│                                   ← _get_lead_description_fields (+ registration_answer_ids)
└── event.lead.rule views           ← make lead_creation_basis visible in UI
```

### What This Module Does Not Do

This module is intentionally thin. It does **not**:
- Introduce any new models.
- Handle lead creation directly — that is the job of `event_crm`'s `event.lead.rule._run_on_registrations()`.
- Add security rules — it reuses `event_crm`'s ACLs.
- Define cron jobs or background scheduling.

---

## Dependencies Explained

### `event_crm`

The foundation module that provides:
- `event.lead.rule` model — configuration for lead generation rules
- `lead_ids` / `lead_count` fields on `event.registration`
- `_get_lead_values`, `_get_lead_contact_values`, `_get_lead_description` methods on `event.registration`
- `_run_on_registrations` on `event.lead.rule` — the rule execution engine
- `crm.lead` extensions: `event_lead_rule_id`, `event_id`, `registration_ids`

### `website_event`

Provides:
- `event.registration.visitor_id` — Many2one to `website.visitor`, populated automatically on website registration
- `event.registration.registration_answer_ids` — One2many to `event.registration.answer`, populated from website survey questions
- The `visitor_id` field is indexed `btree_not_null` for efficient filtering

---

## Model Extensions

### `event.registration` — `website_event_crm`

File: `~/odoo/odoo19/odoo/addons/website_event_crm/models/event_registration.py`

Three method overrides on the `event.registration` model:

---

#### `_get_lead_values(rule)` — `L3: visitor and language propagation`

```python
def _get_lead_values(self, rule):
    lead_values = super()._get_lead_values(rule)
    if self.visitor_id:
        lead_values['visitor_ids'] = self.visitor_id
    if self.visitor_id.lang_id:
        lead_values['lang_id'] = self.visitor_id.lang_id[0].id
    return lead_values
```

**Called from:** `event.lead.rule._run_on_registrations()` — once per registration group when creating a lead.

**Return value:** A `dict` of field names to values, passed directly to `crm.lead.create()`.

**What each field means on the lead:**

- **`visitor_ids`** (Many2many, `crm.lead` → `website.visitor`): Links the lead to the website visitor who made the registration. The `website_event_contact_form` module (part of `website_event`) automatically subscribes the visitor to the lead's chatter as a follower, enabling tracking emails and lead scoring based on visitor behavior. Multiple registrations from the same visitor accumulate on the same Many2many set.

- **`lang_id`** (Many2one, `crm.lead` → `res.lang`): Sets the lead's preferred language. This drives:
  - Email template language selection when the lead triggers an automated email
  - The lead's `lang_id` computed field used by `mail.template` to select the correct translated template
  - Reporting and segmentation by language in the CRM pipeline

**L4 Edge Case — Multiple registrations, different languages:**

When `lead_creation_basis = 'order'` (grouped mode), multiple registrations from different visitors can land on the same lead. The test `test_visitor_language_propagation` confirms the behavior:

```python
# grouped lead: first found visitor's language wins
global_lead = leads.filtered(lambda l: l.event_lead_rule_id == self.test_rule_order)
self.assertEqual(global_lead.lang_id, self.test_lang_visitor.lang_id)
# visitor_ids accumulates all visitors (Many2many, not overwrite)
self.assertEqual(global_lead.visitor_ids, self.test_lang_visitor + self.test_lang_visitor_fr)
```

The `lang_id` is set from `self.visitor_id.lang_id[0].id` — the `[0]` index picks the first record from the recordset. On a single registration, this is the visitor's language. On a grouped lead created from multiple registrations, only the first registration's visitor contributes `lang_id`; subsequent registrations' visitors are added to `visitor_ids` but do not overwrite `lang_id`. This is by design: the lead has one language, determined by the first visitor.

**L4 Performance note:** `_get_lead_values` is called inside `crm.lead.create()` loop. The `visitor_id.lang_id` read is a single related field access (one ORM query for the `lang_id` Many2one on `website.visitor`). At typical event registration volumes (hundreds to low thousands per batch), there is no performance concern. The `super()._get_lead_values(rule)` call already performs UTM field lookups and contact value computation; the website additions are marginal.

**L4 Failure mode:** If `website_event` is uninstalled after registrations exist with `visitor_id` set, those registrations will have a stale `visitor_id` pointing to a deleted record (`ondelete='set null'` was not used on the original field definition in `website_event`). In that scenario, `self.visitor_id` returns an empty recordset and both conditionals silently skip. No error is raised.

---

#### `_get_lead_description_registration(line_suffix='')` — `L3: answer enrichment`

```python
def _get_lead_description_registration(self, line_suffix=''):
    reg_description = super(...)._get_lead_description_registration(line_suffix=line_suffix)
    if not self.registration_answer_ids:
        return reg_description

    answer_descriptions = []
    for answer in self.registration_answer_ids:
        answer_value = (
            answer.value_answer_id.name
            if answer.question_type == "simple_choice"
            else answer.value_text_box
        )
        answer_value = Markup("<br/>").join(["    %s" % line for line in answer_value.split('\n')])
        answer_descriptions.append(
            Markup("  - %s<br/>%s") % (answer.question_id.title, answer_value)
        )
    return Markup("%s%s<br/>%s") % (
        reg_description,
        _("Questions"),
        Markup('<br/>').join(answer_descriptions)
    )
```

**Called from:** `_get_lead_description()` in `event_crm` — once per registration in the batch when building the full lead description.

**Return value:** An HTML-formatted string (`Markup`) for one registration's line in the lead description.

**Two question types handled:**

| `question_type` | Value source | Example |
|---|---|---|
| `simple_choice` | `value_answer_id.name` | "Which session? → Morning Workshop" |
| `text_box` | `value_text_box` | "Dietary requirements: Vegetarian, no nuts" |

Multi-line text answers are preserved with `<br/>` between lines and 4-space indentation.

**Output format per answer:**

```
  - <Question Title>
    <answer value>
```

All answers are grouped under a "Questions" section header appended to the base registration line (name, email, phone).

**L4 HTML escaping / XSS prevention — critical:**

The test `test_event_registration_lead_description` explicitly validates the escaping strategy:

```python
# User-submitted answer containing HTML markup → must be escaped
self.assertIn(
    f'&lt;div&gt;answer from {customer_data.get("name", "no_name")}&lt;/div&gt;',
    order_lead.description,
    "Answers should be escaped"
)
# Server-generated structural HTML → must NOT be escaped
self.assertIn('<li>', order_lead.description,
    'HTML around the text box value should not be escaped')
```

The `Markup()` calls are carefully applied only to server-generated content. `answer_value` (from `value_text_box` or `value_answer_id.name`) is raw user input and is included by string interpolation inside an already-wrapped `Markup()`, which causes Odoo/markupsafe to escape it. Structural tags (`<li>`, `<br/>`, `<ol>`) are added after the `Markup()` wrapper is applied, so they pass through unescaped.

If the escaping strategy is accidentally changed (e.g., `Markup(answer_value)` instead of raw interpolation), user-submitted HTML would render as live HTML in the lead description, creating an XSS vector visible in the chatter.

**L4 `registration_answer_ids` structure:**

Each `event.registration.answer` record has:
- `registration_id` → parent `event.registration`
- `question_id` → `event.question` (the question text is in `question_id.title`)
- `question_type` → `simple_choice` or `text_box`
- `value_answer_id` → `event.question.answer` (for simple choice; the selected option)
- `value_text_box` → `str` (for text_box; free-text input)

---

#### `_get_lead_description_fields()` — `L3: tracked field expansion`

```python
def _get_lead_description_fields(self):
    res = super(...)._get_lead_description_fields()
    res.append('registration_answer_ids')
    return res
```

**Called from:** `_get_lead_tracked_values()` in `event_crm`, which is called by `_update_leads()` during `write()` on registrations.

**Effect:** When any field in `['name', 'email', 'phone', 'registration_answer_ids']` changes on an existing registration, the lead's description is updated with a new appended block:

```
Updated registrations
<ol>
  <li><registration info including new answers></li>
</ol>
```

The prefix "Updated registrations" (translated) signals to the salesperson that this is not the original registration data.

**L4 How One2many tracking works:**

`registration_answer_ids` is a One2many. In `_get_lead_tracked_values`, the base `event_crm` method calls `_convert_value()` for each tracked field. For One2many fields, `_convert_value` returns a list of IDs:

```python
if isinstance(value, models.BaseModel) and self._fields[field_name].type in ['many2many', 'one2many']:
    return value.ids
```

So the comparison in `_update_leads` is: `old_answer_ids` vs `new_answer_ids` (both lists of IDs). If the lists differ (answers added, removed, or changed), the description update fires. Note: this detects answer *set* changes but does not diff which specific answer changed — the entire registration's description block is re-rendered.

---

## View Overrides

File: `~/odoo/odoo19/odoo/addons/website_event_crm/views/event_lead_rule_views.xml`

Two inheritance records target `event.lead.rule`:

### Tree view — `event_lead_rule_view_tree`

```xml
<xpath expr="//field[@name='lead_creation_basis']" position="attributes">
    <attribute name="column_invisible">False</attribute>
</xpath>
```

In `event_crm`, `lead_creation_basis` has `column_invisible="True"` in the list view. This override makes it visible as a column, showing `Per Attendee` or `Per Order` for each rule.

**Why hidden in `event_crm`?** The `'order'` option only makes sense when registrations are created in batch — `event_crm`'s `_get_lead_grouping` groups by `(create_date, event_id)`, which is meaningful in the website flow. Without `website_event`, there is no batch registration concept, so the column is noise.

### Form view — `event_lead_rule_view_form`

```xml
<xpath expr="//group[@name='lead_creation_basis']" position="attributes">
    <attribute name="invisible">0</attribute>
</xpath>
```

In `event_crm`, the group named `lead_creation_basis` (containing the `lead_creation_basis` radio widget) is `invisible="1"`. This override removes the invisible flag, making the radio button visible in the form. The `lead_creation_trigger` group is not affected.

---

## Demo Data

File: `data/event_crm_demo.xml`

Creates one `event.lead.rule` named `"Rule per order"`:
- `lead_creation_basis`: `order`
- `event_id`: `event.event_0`
- `lead_user_id`: `base.user_demo`
- `lead_tag_ids`: `sales_team.categ_oppor3` and `sales_team.categ_oppor6`

This demonstrates the order-based grouping mode with a real demo user.

---

## Lead → Registration Sync (Inherited from `event_crm`)

The full update machinery lives in `event_crm`'s `event.registration`:

| Hook | Trigger | Action |
|---|---|---|
| `_apply_lead_generation_rules` | `create()` | Fires `create` trigger rules |
| `_apply_lead_generation_rules` | `write(state='open')` | Fires `confirm` trigger rules |
| `_apply_lead_generation_rules` | `write(state='done')` | Fires `done` trigger rules |
| `_update_leads` | `write()` on any tracked field | Updates existing leads |

`website_event_crm` contributions integrate as follows:
- `visitor_ids` / `lang_id` are written at **creation time** via `_get_lead_values`; they are **not** re-tracked for updates (not in `_get_lead_contact_fields` or `_get_lead_description_fields`).
- `registration_answer_ids` changes trigger **description updates only** (appended blocks), not contact info changes.

---

## Test Coverage

### `test_event_registration.py`

#### Setup (`setUpClass` additions beyond `TestEventCrmCommon`)

- Adds a `text_box` question to `event_0` for answer rendering tests
- Grants `group_sale_salesman` to `user_eventmanager` (enables lead access checks)
- Creates two test websites with EN/FR languages
- Creates two test visitors: English (`test_lang_visitor`) and French (`test_lang_visitor_fr`)

#### `test_event_registration_lead_description`

- Creates 5 registrations, each with a text answer containing literal HTML: `<div>answer from ...</div>`
- Verifies answers are **escaped** in the final lead description (`&lt;div&gt;`)
- Verifies structural `<li>` tags are **not escaped**
- Covers both per-attendee and per-order lead creation modes

#### `test_event_registration_generation_from_existing`

- Uses `event_lead_rule_skip=True` context to create 4 registrations without triggering rules
- Calls `test_rule_order._run_on_registrations(attendees_1 + attendees_2)` manually (simulating manual rule execution)
- Confirms **2 separate leads** are created (one per `(create_date, event)` group)
- Confirms each lead has its correct `registration_ids` subset

#### `test_visitor_language_propagation`

- Creates 3 registrations: 2 from English visitor, 1 from French visitor (same event)
- Confirms 4 total leads (3 attendee-based + 1 order-based)
- **Order-based lead:** `visitor_ids` = both visitors; `lang_id` = English (first found)
- **Attendee-based leads:** each lead has its own `visitor_ids` and `lang_id`

### `test_visitor_propagation.py`

A placeholder class inheriting `TestEventCrmCommon`. The real propagation assertions are in `test_event_registration.py`.

---

## L4 Security Considerations

| Risk | Details | Mitigation |
|---|---|---|
| Visitor data in CRM | `visitor_ids` links leads to `website.visitor` records containing tracking data (cookies, pages visited, UTM history) | `website.visitor` ACLs restrict access to website management roles; `event_crm` grants `sales_team.group_sale_salesman` read access to `lead_ids` on registrations |
| Language-driven emails | Setting `lang_id` on a lead influences email template language; a French-speaking visitor may receive emails in French that the assigned salesperson cannot read | The `lang_id` field is informational on the lead; sales teams should use translation tools or assign leads to multilingual salespeople |
| HTML injection in descriptions | `value_text_box` answers are user-submitted and could contain malicious HTML | The `Markup()` wrapping strategy escapes user content; any future change to this pattern must maintain escaping for `answer_value` |
| `event_lead_rule_skip` context | Used during data imports and tests to suppress rule execution | Production imports should also use this context to avoid spurious lead creation during data bootstrapping |

---

## L4 Performance Implications

| Operation | Complexity | Notes |
|---|---|---|
| Registration creation | O(N) lead creates | Each registration in a batch fires rules; `_get_lead_values` reads `visitor_id.lang_id` per registration (1 extra query per registration) |
| Order-based grouping | O(N log N) sort | `_get_lead_grouping` groups by `(create_date, event_id)` using Python `groupby` after sorting by ID; registrations are sorted twice (by ID, then by create_date) |
| Lead description update | O(N) description rebuild | Full description is reconstructed from scratch; existing description is appended to, not replaced in-place |
| `_get_lead_description_registration` | O(A) per registration | Where A = number of registration answers; each answer causes a `question_id` and `value_answer_id` read |

---

## Odoo 18 → 19 Changes

No breaking changes specific to `website_event_crm` are documented. The module structure was stable across the version boundary:

- The `_get_lead_values` override (calling `super()` then patching) was present in both versions
- The `Markup` import from `markupsafe` is consistent between versions
- The `website.visitor.lang_id` field existed in Odoo 18
- The `event_lead_rule_skip` context key was already present in Odoo 18's `event_crm`

**One notable change in `event_crm` between versions (affecting this module):** In Odoo 18, `_get_lead_values` returned a wider set of lead fields. In Odoo 19, `event_crm` was refactored to push more logic into `_get_lead_contact_values` and `_get_lead_description`. `website_event_crm`'s overrides remain identical in function but the call chain is shallower.

---

## Relationship Diagram

```
website.visitor
  lang_id (res.lang)     ← visitor's preferred language
  website_id             ← which website they visited
       │
       │ (Many2one, ondelete='set null', indexed: btree_not_null)
       │
event.registration
  visitor_id ──────────────────────────────► website.visitor (from website_event)
  registration_answer_ids (O2M) ───────────► event.registration.answer
       │                                            question_id ──► event.question
       │ (One2many, tracked in description)            title
       │                                              question_type
  event_id ─────────────────────────────────► event.event
  partner_id (res.partner)
  email / name / phone
       │
       │ _apply_lead_generation_rules()
       │ _get_lead_values()
       │ (via event.lead.rule._run_on_registrations)
       ▼
crm.lead
  visitor_ids (M2M)  ← self.visitor_id propagated by website_event_crm
  lang_id (M2O)       ← self.visitor_id.lang_id propagated by website_event_crm
  registration_ids (M2M) ← all registrations that generated this lead
  event_lead_rule_id (M2O) ← rule that created the lead
  event_id (M2O)      ← event of source registrations
  description         ← enriched by _get_lead_description_registration (+ answers)
  type                ← 'lead' or 'opportunity' from rule.lead_type
  user_id / team_id   ← from rule.lead_user_id / rule.lead_sales_team_id
  tag_ids             ← from rule.lead_tag_ids
  campaign_id / source_id / medium_id  ← UTM from first registration
```

---

## Key Field Summary

| Field | On Model | Type | Origin | Purpose |
|---|---|---|---|---|
| `visitor_id` | `event.registration` | Many2one | `website_event` | Tracks which website visitor made the registration |
| `lang_id` | `crm.lead` | Many2one | `website_event_crm._get_lead_values` | Lead's preferred language from visitor |
| `visitor_ids` | `crm.lead` | Many2many | `website_event_crm._get_lead_values` | All visitors linked to this lead |
| `registration_answer_ids` | `event.registration` | One2many | `event` | Attendee answers to event questions |
| `registration_ids` | `crm.lead` | Many2many | `event_crm` | All registrations linked to this lead |
| `event_lead_rule_id` | `crm.lead` | Many2one | `event_crm` | The rule that generated this lead |
| `lead_creation_basis` | `event.lead.rule` | Selection | `event_crm` | `'attendee'` (1 lead/reg) or `'order'` (1 lead/batch) |

---

## See Also

- [Modules/event_crm](Modules/event_crm.md) — Base CRM lead generation from event registrations
- [Modules/website_event](Modules/website_event.md) — Website event pages, visitor tracking, registration form
- [Modules/Event](Modules/event.md) — Core event management (`event.registration`, `event.lead.rule`)
- [Modules/CRM](Modules/CRM.md) — CRM leads and opportunities
- [Core/Fields](Core/Fields.md) — Many2one, One2many, Many2many field behavior
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — Event state machine (create → confirm → done)
