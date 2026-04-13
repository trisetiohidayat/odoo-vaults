# website_crm_livechat

#odoo #odoo19 #module #website #crm #livechat #im_livechat

## Overview

- **Module**: `website_crm_livechat`
- **Name**: Lead Livechat Sessions
- **Category**: Website/Website
- **Summary**: View livechat sessions for leads
- **Version**: 1.0
- **Depends**: `website_crm`, `website_livechat`
- **Auto-install**: `True` (installs automatically when both dependencies are present)
- **License**: LGPL-3
- **Source**: `odoo/addons/website_crm_livechat/`

## Description

Bridges the gap between live chat conversations and CRM lead management. When a visitor initiates a livechat session on a website, this module ensures the resulting lead is automatically linked back to the website visitor, enabling full conversation history tracking and session attribution. It adds a Sessions stat button on the lead form view so salespeople can instantly access livechat sessions tied to that lead.

This module only activates when **both** `website_crm` (visitor-lead linking infrastructure) and `website_livechat` (livechat on website) are installed. It augments two separate lead creation pathways: the `/lead` chat command and the chatbot "Create Lead" step type.

## Module Structure

```
website_crm_livechat/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── crm_lead.py                  # crm.lead extension: session count + stat button action
│   ├── discuss_channel.py           # discuss.channel extension: visitor-to-lead linking
│   └── chatbot_script_step.py       # chatbot.script.step extension: chatbot lead naming
└── views/
    └── website_crm_lead_views.xml   # Form view: adds Sessions stat button after Page Views
```

## Dependency Chain

The module participates in a two-level override chain on top of `crm_livechat`:

```
discuss.channel
  └── crm_livechat  (defines _convert_visitor_to_lead for /lead command)
        └── website_crm_livechat  (augments: links visitor + copies country)

chatbot.script.step
  └── crm_livechat  (defines _chatbot_crm_prepare_lead_values + create_lead step type)
        └── website_crm_livechat  (augments: overrides name + links visitor)
```

| Module | Provides |
|--------|----------|
| `im_livechat` | Base `discuss.channel` + base `chatbot.script.step`; `livechat_operator_id`; channel history |
| `crm_livechat` | `_convert_visitor_to_lead()`; `create_lead`/`create_lead_and_forward` step types; lead creation from `/lead` command |
| `website_livechat` | `discuss.channel.livechat_visitor_id` Many2one to `website.visitor`; `livechat_channel_id`; session field storage |
| `website_crm` | `crm.lead.visitor_ids` Many2many to `website.visitor`; page view tracking |
| `website_crm_livechat` | Visitor linking on lead creation; Sessions stat button on lead form |

---

## Models

### `crm.lead` — CRM Lead Extension

**File**: `models/crm_lead.py`
**Inheritance**: `_inherit = 'crm.lead'` (extends the `website_crm` extension)

#### Fields Added

| Field | Type | Label | Groups | Description |
|-------|------|-------|--------|-------------|
| `visitor_sessions_count` | `Integer` | `# Sessions` | `im_livechat.im_livechat_group_user` | Total livechat `discuss.channel` sessions belonging to all website visitors linked to this lead, including sessions with no messages. Hidden on the form when the count is 0. |

**Design notes**:
- The `groups` attribute restricts both read access to the field and visibility of the stat button to livechat users only. Salespeople without livechat access see neither the button nor the number.
- The field label is `# Sessions` (with a leading `#`) — Odoo's convention for countable stat buttons.
- The `string` parameter on `fields.Integer` is the button label, not the field's human-readable name (which would appear in CSV exports).

---

#### `_compute_visitor_sessions_count()`

```python
@api.depends('visitor_ids.discuss_channel_ids')
def _compute_visitor_sessions_count(self):
    for lead in self:
        lead.visitor_sessions_count = len(lead.visitor_ids.discuss_channel_ids)
```

**Dependency chain**: `crm.lead` → `visitor_ids` (Many2many from `website_crm`) → `discuss_channel_ids` (Many2many from `im_livechat` on `website.visitor`)

**What it counts**: All `discuss.channel` records of `channel_type = 'livechat'` linked to any visitor in `lead.visitor_ids`. This includes:
- Sessions with zero messages (the `has_message = False` filter is applied only in the action domain, not here)
- Sessions that were abandoned before the visitor typed anything
- Repeated sessions from the same visitor (each session is a separate channel)

**Performance considerations**:
- `len()` on a recordset triggers a `search()` under the hood. In a loop over many leads, this generates N SQL `SELECT` queries against `discuss_channel`, one per lead.
- There is no `_compute_visitor_sessions_count` invalidation cache on the `website.visitor` side, so any new channel creation for a visitor invalidates all leads linked to that visitor.
- For leads with no visitors (`self.visitor_ids` empty recordset), `discuss_channel_ids` returns an empty recordset and `len()` is cheap — no DB query is issued.
- In a batch of 100 leads with distinct visitors, this generates up to 100 additional `discuss_channel` counts. Consider adding a `compute_sudo = True` or batching via SQL for large lead lists.

---

#### `action_redirect_to_livechat_sessions()`

```python
def action_redirect_to_livechat_sessions(self):
    visitors = self.visitor_ids
    action = self.env["ir.actions.actions"]._for_xml_id(
        "website_livechat.website_visitor_livechat_session_action"
    )
    action['domain'] = [
        ('livechat_visitor_id', 'in', visitors.ids),
        ('has_message', '=', True)
    ]
    return action
```

**Action used**: `website_livechat.website_visitor_livechat_session_action` — a window action for `discuss.channel` pre-filtered to livechat sessions.

**Domain filters applied**:
| Filter | Effect |
|--------|--------|
| `('livechat_visitor_id', 'in', visitors.ids)` | Restricts to channels whose visitor is in the lead's visitor set |
| `('has_message', '=', True)` | Excludes channels with zero messages (abandoned/empty sessions) |

**Why `has_message` is not in the computed field**: The stat button shows the raw count for quick reference; filtering empty sessions is a UX choice deferred to the list view. This prevents confusion where a visitor has 3 abandoned sessions but the button shows "3" and the list shows "0".

**Failure modes**:
- If `visitors.ids` is empty (lead has no visitors), the domain becomes `('livechat_visitor_id', 'in', [])` which matches nothing — the action opens an empty list. This is correct (no sessions to show).
- If the action ID `website_livechat.website_visitor_livechat_session_action` is deleted from the database (e.g., module upgrade without demo data), the `_for_xml_id` call raises `ValueError`.

---

### `discuss.channel` — Livechat Visitor-to-Lead Linking

**File**: `models/discuss_channel.py`
**Inheritance**: `_inherit = 'discuss.channel'`
**Parent method**: `crm_livechat.models.discuss_channel._convert_visitor_to_lead()`

#### `_convert_visitor_to_lead(partner, key)`

```python
def _convert_visitor_to_lead(self, partner, key):
    """ When website is installed, we can link the created lead from /lead command
     to the current website_visitor. We do not use the lead name as it does not correspond
     to the lead contact name."""
    lead = super()._convert_visitor_to_lead(partner, key)
    visitor_sudo = self.livechat_visitor_id.sudo()
    if visitor_sudo:
        visitor_sudo.write({'lead_ids': [(4, lead.id)]})
        lead.country_id = lead.country_id or visitor_sudo.country_id
    return lead
```

**Trigger**: Called when an operator or visitor types `/lead [title]` in a livechat session. This is triggered by `crm_livechat`'s `execute_command_lead()` method.

**Full execution chain**:
```
Operator types /lead My Lead Title
  → crm_livechat.DiscussChannel.execute_command_lead()
    → crm_livechat.DiscussChannel._convert_visitor_to_lead()
        → Creates crm.lead with name="My Lead Title"
          origin_channel_id=self.id
          source_id=utm_source_livechat
          referred=operator_name
          description=channel history
        → website_crm_livechat._convert_visitor_to_lead() (this method)
            → Writes lead.id into visitor.lead_ids  (4 = link command)
            → Copies visitor.country_id to lead.country_id if lead has none
            → Returns lead
```

**`(4, lead.id)` link command**: The `(4, id)` ORM command is `LINK_TO` — it adds `lead.id` to the Many2many `lead_ids` without removing existing links. A visitor can accumulate multiple leads over time (one per livechat session that used `/lead`).

**`.sudo()` usage**: `self.livechat_visitor_id.sudo()` is used when writing to `lead_ids` because the operator (livechat agent) may not have write access on `website.visitor` records. The returned `lead` object operates in the normal (non-sudo) environment of the caller.

**Country inheritance**:
```python
lead.country_id = lead.country_id or visitor_sudo.country_id
```
- Uses short-circuit `or` — only sets country if `lead.country_id` is falsy (False, None, or unset).
- If the operator manually set a country before typing `/lead`, that value is preserved.
- `visitor_sudo.country_id` is the visitor's geolocated or manually set country on the `website.visitor` record.

**Edge cases**:
- `self.livechat_visitor_id` is a `False` M2O record (not None, but an empty recordset) when the channel was created via internal operator chat (not website livechat). In that case, `if visitor_sudo:` evaluates to falsy and the block is skipped.
- If the visitor record is deleted between the `super()` call and the `write()`, the `sudo()` record becomes a new empty recordset and `if visitor_sudo:` is again falsy — no crash.
- `lead.country_id` write is done without `sudo()` — if the operator lacks write access on `crm.lead`, this line could raise an `AccessError`. In practice, operators who type `/lead` in livechat have CRM write access.

---

### `chatbot.script.step` — Chatbot Lead Naming and Visitor Linking

**File**: `models/chatbot_script_step.py`
**Inheritance**: `_inherit = 'chatbot.script.step'`
**Parent method**: `crm_livechat.models.chatbot_script_step._chatbot_crm_prepare_lead_values()`

#### `_chatbot_crm_prepare_lead_values(discuss_channel, description)`

```python
def _chatbot_crm_prepare_lead_values(self, discuss_channel, description):
    values = super()._chatbot_crm_prepare_lead_values(discuss_channel, description)
    if discuss_channel.livechat_visitor_id:
        values['name'] = _("%s's New Lead", discuss_channel.livechat_visitor_id.display_name)
        values['visitor_ids'] = [(4, discuss_channel.livechat_visitor_id.id)]
    return values
```

**Trigger**: Called from `crm_livechat.ChatbotScriptStep._process_step_create_lead()` when the chatbot reaches a step of type `create_lead` or `create_lead_and_forward`. The parent `crm_livechat` method builds the base lead values dict; this method patches two fields if a livechat visitor exists.

**Parent method (`crm_livechat`) summary** — returns a dict with:
| Key | Source |
|-----|--------|
| `name` | `"%s's New Lead" % chatbot_title` (or first free-input message body, max 100 chars) |
| `description` | provided `description` param + `discuss_channel._get_channel_history()` |
| `origin_channel_id` | `discuss_channel.id` |
| `source_id` | `chatbot_script_id.source_id` (UTM source from chatbot) |
| `team_id` | `crm_team_id` from step, or blank |
| `user_id` | `False` (unassigned) |
| `type` | `'lead'` or `'opportunity'` depending on team settings |

**What this extension patches**:

1. **`values['name']`** — Replaces the parent's chatbot-title-based name with `"VisitorName's New Lead"`:
   ```python
   values['name'] = _("%s's New Lead", discuss_channel.livechat_visitor_id.display_name)
   ```
   - `display_name` on `website.visitor` falls back to `"Visitor #<id>"` if no friendly name is set.
   - `_()` (odoo translate function) allows the `"'s New Lead"` suffix to be translated.
   - The leading name portion (`VisitorName`) is NOT passed through `_()` — it is raw visitor data.

2. **`values['visitor_ids']`** — Adds visitor linking via Many2many link command:
   ```python
   values['visitor_ids'] = [(4, discuss_channel.livechat_visitor_id.id)]
   ```
   - The link command `(4, id)` adds without replacing — same visitor can be linked to multiple leads.
   - This is a **context-time modification** of the dict returned by `super()` — the actual `create()` call happens in `crm_livechat._process_step_create_lead()` after this method returns.
   - A single `visitor_ids` field with `[(4, id)]` in vals is equivalent to `visitor_ids = visitor` on the create call.

**Visitor name vs. lead name mismatch**: The docstring in `discuss_channel.py` explicitly notes: *"We do not use the lead name as it does not correspond to the lead contact name."* This refers to the `/lead` command where the operator provides a free-text title. For chatbot leads, the module deliberately uses the visitor's display name as the lead name — not the chatbot title — for immediate recognizability in the CRM pipeline.

**Edge cases**:
- If `discuss_channel.livechat_visitor_id` is a False/empty recordset (e.g., chatbot running in internal discuss, not website livechat), the `if` block is skipped — lead is created without visitor linking and with the parent's chatbot-title name.
- `display_name` can be transliterated/ASCII-folded for non-Latin script visitors, depending on `website.visitor.name` encoding.

---

## Views

### `website_crm_lead_views.xml`

**Extends**: `website_crm.crm_lead_view_form` (the form view from `website_crm`)

**XPath target**: The Page Views stat button (`//button[@name='action_redirect_to_page_views']`)

**Placement**: `position="after"` — the Sessions button is inserted immediately after the Page Views button, grouping all visitor-attribution buttons together on the lead form.

```xml
<button name="action_redirect_to_livechat_sessions"
        type="object"
        class="oe_stat_button"
        icon="fa-comment"
        invisible="visitor_sessions_count == 0"
        groups="im_livechat.im_livechat_group_user">
    <field name="visitor_sessions_count" widget="statinfo" string="Sessions"/>
</button>
```

**Button attributes**:
| Attribute | Value | Effect |
|-----------|-------|--------|
| `type="object"` | Calls `action_redirect_to_livechat_sessions()` on single record | Uses `ensure_one()` implicitly via button behavior |
| `class="oe_stat_button"` | Odoo stat button CSS | Displays as a clickable card with icon and count |
| `icon="fa-comment"` | FontAwesome `fa-comment` | Comment icon (distinct from `fa-eye` on Page Views) |
| `invisible="visitor_sessions_count == 0"` | Hides when no sessions | Prevents empty-button confusion |
| `groups="im_livechat.im_livechat_group_user"` | Livechat user group | Hides entire button for non-livechat users |

**Widget**: `widget="statinfo"` renders the integer value next to the label. The field must be read-compatible for the user — since `visitor_sessions_count` has `groups` set, non-livechat users get an `AccessError` if they try to read it directly (though the `invisible` domain also prevents the button from rendering).

**Security note**: The `groups` on the button AND the `groups` on the field definition are redundant but both needed — the field needs its own `groups` for any API context where the field is read without the button's view wrapping.

---

## Data Flow Diagrams

### Pathway 1: `/lead` Command (Operator-Initiated)

```
Visitor (website.visitor, browsing website)
  │
  ├─ Opens livechat widget
  │    → discuss.channel created with livechat_visitor_id = visitor
  │
  ├─ Chats with operator (human agent)
  │
  └─ Operator types: /lead "Interested in Enterprise Plan"
       │
       └→ crm_livechat.execute_command_lead()
              │
              └→ crm_livechat._convert_visitor_to_lead()
                     │  Creates crm.lead:
                     │    name = "Interested in Enterprise Plan"
                     │    origin_channel_id = channel.id
                     │    source_id = utm_source_livechat
                     │    description = full chat history
                     │    partner_id = anonymous visitor partner or False
                     │
                     └→ website_crm_livechat._convert_visitor_to_lead()
                            │  visitor_sudo.lead_ids += lead  (4, lead.id)
                            │  lead.country_id |= visitor.country_id
                            └→ Returns lead
                                   └→ Bus notification sent to operator
```

### Pathway 2: Chatbot "Create Lead" Step

```
Visitor (website.visitor)
  │
  ├─ Engages chatbot on website (discuss.channel with livechat_visitor_id)
  │
  ├─ Chatbot collects email/phone via question_* steps
  │
  └─ Chatbot reaches step with step_type = "create_lead"
         │
         └→ crm_livechat._process_step_create_lead()
                │
                ├─ _chatbot_prepare_customer_values()
                │     Extracts email, phone from chat messages
                │     Creates res.partner for public user
                │
                └─ _chatbot_crm_prepare_lead_values()
                       │  super() → base values dict
                       │    name = "ChatbotTitle's New Lead"
                       │    origin_channel_id, source_id, team_id, ...
                       │
                       └→ website_crm_livechat._chatbot_crm_prepare_lead_values()
                              │  Patches name = "VisitorName's New Lead"
                              │  Patches visitor_ids = [(4, visitor.id)]
                              └→ Returns patched values
                                     └→ crm.lead.create(vals)
                                            ├─ lead created with visitor linked
                                            └→ _assign_userless_lead_in_team()
```

### Pathway 3: Stat Button Navigation (Read-Only, Post-Creation)

```
Salesperson opens crm.lead form
  │
  ├─ visitor_sessions_count computed
  │     = len(lead.visitor_ids.discuss_channel_ids)
  │     Counts all livechat channels for all linked visitors
  │
  └─ Clicks Sessions stat button
         └→ action_redirect_to_livechat_sessions()
                │  Loads website_livechat.website_visitor_livechat_session_action
                │  Domain: livechat_visitor_id in lead.visitor_ids
                │           AND has_message = True
                └→ Opens filtered discuss.channel list view
```

---

## Cross-Model Relationship Map

```
crm.lead (this module adds)
  visitor_ids ──────Many2many──→ website.visitor (from website_crm)
  visitor_sessions_count (computed from visitor_ids → discuss_channel_ids)

website.visitor (from website_crm)
  lead_ids ─────────Many2many──→ crm.lead (inverse of visitor_ids)
  discuss_channel_ids ────────Many2many──→ discuss.channel (from im_livechat)

discuss.channel (this module extends)
  livechat_visitor_id ───────Many2one──→ website.visitor (from website_livechat)
  origin_channel_id ────────Many2one──→ crm.lead (from crm_livechat)
```

The bidirectional `visitor ↔ lead` link is maintained by `website_crm` on `website.visitor.lead_ids` and `crm.lead.visitor_ids`. This module writes to the visitor side (`visitor.lead_ids`) at lead creation time.

---

## Security Considerations

| Concern | Detail |
|---------|--------|
| **Field-level groups** | `visitor_sessions_count` is restricted to `im_livechat.im_livechat_group_user`. Users outside this group get an `AccessError` on direct field read; the button's `invisible` domain prevents rendering for them. |
| **Visitor access via sudo** | `self.livechat_visitor_id.sudo()` is used in `_convert_visitor_to_lead` to write `lead_ids`. This bypasses ACL for the write to `website.visitor.lead_ids` only — the lead creation itself runs with normal user context. |
| **Lead country write** | `lead.country_id = ...` assignment is NOT sudo-wrapped. If the operator lacks `write` access on `crm.lead`, this line raises `AccessError`. In practice, livechat operators have CRM create access (needed to handle leads). |
| **Session count info leakage** | Even with the button hidden, a technically sophisticated contact with API access could infer that a lead has livechat sessions (count > 0) by observing the button's presence/absence in the form's `invisible` domain evaluation. This is low severity. |
| **Chat history in lead description** | The full conversation transcript is written to `lead.description` by `crm_livechat`. This may include personal data entered by the visitor (email, phone). Standard CRM access rules apply — only users with read access to the lead see the description. |

---

## Performance Implications

| Operation | Concern | Severity |
|-----------|---------|----------|
| `_compute_visitor_sessions_count` loop | `len(recordset)` triggers individual SQL per lead in `for lead in self` | Medium on lead list views with many records |
| `visitor_ids.discuss_channel_ids` traversal | Two Many2many joins through `crm_lead_website_visitor_rel` and `discuss_channelWebsiteVisitor_rel` tables | Low-Medium |
| New session created | `website.visitor` write `(4, lead.id)` is a single SQL INSERT into the M2M relation table | Negligible |
| Lead form load | Stat button field must be computed; triggers dependent computation of `visitor_ids` (from `website_crm`) | Low |

**Optimization path**: If performance becomes an issue on large visitor/lead datasets, the `visitor_sessions_count` could be refactored to use a direct SQL query (similar to `website_crm`'s `_compute_visitor_page_count`) with a single `GROUP BY` to count channels per lead in one query.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `/lead` typed in a channel with no `livechat_visitor_id` (internal operator chat) | `super()` creates the lead; `if visitor_sudo:` is falsy; no visitor linking; country not copied |
| Chatbot "Create Lead" step in non-livechat context (internal discuss channel) | `if discuss_channel.livechat_visitor_id:` is falsy; name stays as chatbot title; no visitor linking |
| Visitor has multiple leads (multiple `/lead` or chatbot sessions) | All leads accumulate in `visitor.lead_ids`; each session creates a new lead |
| Lead already has a country set before `/lead` command | Country inheritance skipped due to `lead.country_id or` short-circuit |
| `website_livechat` not installed but `website_crm` is | Module auto-installs both; no partial behavior |
| Visitor deleted before `_convert_visitor_to_lead` completes | `visitor_sudo` becomes empty recordset; `if visitor_sudo:` is falsy; no crash |
| Lead merged (leads merged via CRM merge wizard) | `website_crm._merge_get_fields_specific()` merges `visitor_ids` via `[(6, 0, leads.visitor_ids.ids)]` — all visitors from all merged leads are consolidated on the surviving lead |
| Visitor converted to partner, then new livechat | Old behavior preserved; new livechat sessions create new leads linked to same visitor |

---

## Odoo 18 → 19 Changes

The `website_crm_livechat` module was introduced in Odoo 18 as part of the `website_livechat` + `website_crm` integration push. In Odoo 19 it is stable with no breaking changes. Minor observations:

- The `crm_livechat` module added `create_lead_and_forward` step type (Odoo 17+) and improved `_assign_userless_lead_in_team()` assignment logic (Odoo 19), both of which flow through this module's chatbot override.
- The `_convert_visitor_to_lead` method in `crm_livechat` gained UTM source assignment in a recent version — `website_crm_livechat`'s extension is compatible with that change.
- No `@api.model` deprecations or `api.model_create_multi` requirements affect this module's methods.

---

## Related

- [Modules/website_crm](odoo-18/Modules/website_crm.md) — `website.visitor.lead_ids`, `crm.lead.visitor_ids`, Page Views stat button
- [Modules/website_livechat](odoo-18/Modules/website_livechat.md) — `discuss.channel.livechat_visitor_id`, livechat session tracking
- [Modules/crm_livechat](odoo-17/Modules/crm_livechat.md) — `/lead` command, chatbot "Create Lead" step type, `origin_channel_id` on lead
- [Modules/im_livechat](odoo-17/Modules/im_livechat.md) — Base livechat channel, operator routing, `discuss.channel` base model
- [Modules/im_livechat](odoo-17/Modules/im_livechat.md) — Chatbot script engine, step types, `_process_step` dispatch
- [Modules/CRM](odoo-18/Modules/CRM.md) — `crm.lead` base model, merge wizard, assignment
- [Core/Fields](odoo-18/Core/Fields.md) — Many2many `(4, id)` link command, computed fields, `groups` attribute
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Lead creation from non-CRM contexts
