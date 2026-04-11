---
Module: crm_livechat
Version: Odoo 18
Type: Integration
---

# CRM Live Chat Integration (`crm_livechat`)

Bridges live chat visitor conversations and chatbot scripts into the CRM lead pipeline. Creates `crm.lead` records from livechat sessions via chatbot steps or the `/lead` channel command.

**Source path:** `~/odoo/odoo18/odoo/addons/crm_livechat/`
**Depends:** `crm`, `im_livechat`
**Auto-installs:** `True`

---

## Models

### `discuss.channel` — EXTENDED (crm_livechat module)

Adds the `/lead` slash command for operators to manually create a lead from a livechat conversation.

#### `execute_command_lead(**kwargs)`

Responds to the `/lead` channel command:

- `/lead` alone → shows usage instructions (formatted markup message)
- `/lead <title>` → creates a `crm.lead` with the given title

The method distinguishes between public users (anonymous visitors) and share partners:
- If any channel participant is a public user → lead `partner_id` is set to the anonymous visitor
- Otherwise → `partner_id` set to the non-operator share partners

#### `_convert_visitor_to_lead(partner, key)`

Called by `execute_command_lead` to create a lead from the operator's input:

```python
def _convert_visitor_to_lead(self, partner, key):
    # key = full input body, e.g. "/lead Some Lead Title"
    utm_source = self.env.ref('crm_livechat.utm_source_livechat')
    return self.env['crm.lead'].create({
        'name': html2plaintext(key[5:]),   # strip "/lead " prefix
        'partner_id': customers[0].id,     # first non-operator share partner
        'user_id': False,
        'team_id': False,
        'description': self._get_channel_history(),
        'referred': partner.name,          # operator name as referrer
        'source_id': utm_source.id,
    })
```

**Field mapping:**

| Lead Field | Value | Source |
|------------|-------|--------|
| `name` | Stripped text after `/lead` | Operator input |
| `partner_id` | First non-public, non-operator channel participant | Livechat session |
| `description` | Full channel message history | `_get_channel_history()` |
| `referred` | Operator's partner name | `self.env.user.partner_id` |
| `source_id` | `crm_livechat.utm_source_livechat` | UTM source record |
| `user_id` | `False` | Unassigned |
| `team_id` | `False` | Unassigned |

#### L4: Channel History and Lead Description

The `_get_channel_history()` method (inherited from `mail.discuss.channel`) returns the full conversation transcript as HTML. This is stored in the lead's `description` field, giving sales reps full context of the livechat conversation when they follow up on the lead.

---

### `chatbot.script` — EXTENDED (crm_livechat module)

Adds lead-generation statistics to chatbot scripts.

| Field | Type | Notes |
|-------|------|-------|
| `lead_count` | Integer (compute) | Total leads created from this script's `source_id` |

#### `_compute_lead_count()`

Uses `_read_group` on `crm.lead` grouped by `source_id` (the chatbot's linked UTM source). Counts leads across all scripts sharing the same source.

#### `action_view_leads()`

Opens the CRM lead list filtered to this chatbot's source. Equivalent to clicking "Generated Lead Count" in the script form.

---

### `chatbot.script.step` — EXTENDED (crm_livechat module)

Adds a `create_lead` step type to chatbot scripts, allowing visitors to trigger automatic lead creation during a chatbot conversation.

#### New Fields

| Field | Type | Notes |
|-------|------|-------|
| `step_type` | Selection | Adds `create_lead` to inherited options |
| `crm_team_id` | M2O `crm.team` | Sales team to assign the created lead |

The `step_type` selection now includes:

| Value | Label | Behavior |
|-------|-------|---------|
| `create_lead` | Create Lead | Triggers automatic lead creation |

#### `_chatbot_crm_prepare_lead_values(discuss_channel, description)`

Returns the base lead creation values used by `_process_step_create_lead`:

```python
def _chatbot_crm_prepare_lead_values(self, discuss_channel, description):
    return {
        'description': description + discuss_channel._get_channel_history(),
        'name': _("%s's New Lead", self.chatbot_script_id.title),
        'source_id': self.chatbot_script_id.source_id.id,
        'team_id': self.crm_team_id.id,
        'type': 'lead' if self.crm_team_id.use_leads else 'opportunity',
        'user_id': False,
    }
```

Key behavior:
- `type` is determined by the CRM team's `use_leads` flag: if the team uses leads → create a lead; otherwise create an opportunity
- `description` concatenates the chatbot-collected description (email, phone, free-input text) with the full channel history

#### `_process_step_create_lead(discuss_channel)`

Extracts visitor information and creates the lead:

1. Calls `_chatbot_prepare_customer_values(discuss_channel, create_partner=False, update_partner=True)` to get:
   - `email`: visitor's email
   - `phone`: visitor's phone
   - `description`: free-input text collected during chatbot session

2. Creates lead differently based on user type:
   - **Public user** (anonymous): Sets `email_from` and `phone` directly on lead
   - **Authenticated user**: Sets `partner_id` and `company_id` from `env.user.partner_id`

3. Merges with `_chatbot_crm_prepare_lead_values()` values

4. Creates `crm.lead` record

---

## Data Records

### UTM Source

`crm_livechat.utm_source_livechat` — the UTM source record used for all leads created from livechat. This allows CRM reporting to attribute leads to the livechat channel.

---

## L4: Lead Creation Flow — Chatbot vs. `/lead` Command

### Chatbot (`create_lead` step)

```
Visitor starts livechat
  → chatbot script loads
  → chatbot collects: email, phone, free-input description
  → visitor reaches 'create_lead' step
  → _process_step_create_lead():
       ├─ Extract email/phone/description from chatbot context
       ├─ If public user → set email_from, phone on lead
       ├─ If logged-in user → set partner_id, company_id on lead
       ├─ Build lead name: "ScriptTitle's New Lead"
       ├─ Assign team (and type: lead vs opportunity) from crm_team_id
       ├─ Set source_id from chatbot script
       └─ Concatenate chatbot description + full channel history
  → crm.lead created
  → Visitor sees confirmation in chatbot
```

### `/lead` Command

```
Operator in livechat channel
  → Operator types: /lead My Lead Title
  → execute_command_lead():
       ├─ _convert_visitor_to_lead():
       │   ├─ Find non-public, non-operator channel participants
       │   ├─ name = "My Lead Title" (html2plaintext)
       │   ├─ partner_id = first visitor partner
       │   ├─ description = full channel history
       │   ├─ referred = operator name
       │   └─ source_id = crm_livechat.utm_source_livechat
       └─ Send confirmation transient message to operator
  → crm.lead created
  → Operator sees confirmation in channel
```

---

## L4: What Fields Are Mapped from Livechat to Lead

| Lead Field | Chatbot Source | `/lead` Command |
|-----------|--------------|----------------|
| `name` | `"ScriptTitle's New Lead"` | Operator input after `/lead` |
| `partner_id` | `env.user.partner_id` (if authenticated) | First non-public visitor |
| `email_from` | `customer_values['email']` (if public user) | — |
| `phone` | `customer_values['phone']` (if public user) | — |
| `description` | chatbot description + channel history | Channel history |
| `source_id` | `chatbot_script_id.source_id` | `crm_livechat.utm_source_livechat` |
| `team_id` | `crm_team_id` from step | `False` |
| `type` | `'lead'` or `'opportunity'` based on `use_leads` flag | `False` (default) |
| `user_id` | `False` | `False` |
| `referred` | — | Operator name |

The chatbot `_chatbot_prepare_customer_values()` method (from `im_livechat.chatbot`) collects the visitor's email and phone from the chatbot step responses, making them available as `customer_values` to `_process_step_create_lead`. If the visitor is a public (anonymous) user, these are stored directly on the lead's standard contact fields. If the visitor is logged in, the partner record is linked directly.

---

## L4: `im_livechat.channel` Extension

The `crm_livechat` module does **not** directly extend `im_livechat.channel`. Instead, it extends `chatbot.script.step` to add a CRM team assignment field, and extends `discuss.channel` for the `/lead` command. The `im_livechat.channel` model remains untouched by `crm_livechat`.

The actual link between livechat channels and CRM teams is via the chatbot script step's `crm_team_id` field — a chatbot script is attached to a livechat channel, and each step in that script can optionally specify a CRM team for leads created at that step.

---

## Tags

#crm #crm-livechat #livechat #chatbot #lead #integration #odoo18
