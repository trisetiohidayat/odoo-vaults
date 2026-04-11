---
Module: website_crm_livechat
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_crm_livechat
---

## Overview

Bridges livechat conversations and CRM leads. When livechat visitors convert to leads (via `/lead` chatbot command or operator action), the visitor record and its country are linked to the created lead. Also exposes the visitor's livechat session count on the lead form.

**Key Dependencies:** `website_livechat`, `crm`, `im_livechat`

**Python Files:** 3 model files

---

## Models

### crm_lead.py — Lead

**Inheritance:** `crm.lead`

| Field | Type | Store | Groups | Notes |
|-------|------|-------|--------|-------|
| `visitor_sessions_count` | Integer | No | im_livechat group | Count of livechat discuss_channel records |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_compute_visitor_sessions_count()` | `@api.depends('visitor_ids.discuss_channel_ids')` | Counts `visitor_ids.discuss_channel_ids` |
| `action_redirect_to_livechat_sessions()` | — | Opens filtered list of livechat sessions for the lead's visitors |

---

### discuss_channel.py — DiscussChannel

**Inheritance:** `discuss.channel`

| Method | Description |
|--------|-------------|
| `_convert_visitor_to_lead(partner, key)` | Overrides parent to link `livechat_visitor_id` to created lead and set country from visitor |

---

### chatbot_script_step.py — ChatbotScriptStep

**Inheritance:** `chatbot.script.step`

| Method | Description |
|--------|-------------|
| `_chatbot_crm_prepare_lead_values(discuss_channel, description)` | Enriches lead values: sets lead name to `"{visitor_name}'s New Lead"` and links `visitor_ids` |

---

## Security / Data

No dedicated security XML files.

---

## Critical Notes

- `visitor_sessions_count` counts sessions across ALL visitors linked to the lead (a lead can have multiple visitors)
- `action_redirect_to_livechat_sessions` uses `livechat_visitor_id` domain on `discuss.channel` — filters to channels with messages (`has_message=True`)
- `_convert_visitor_to_lead` also sets `country_id` from the visitor's country (overrides lead's country only if lead has no country)
- The chatbot lead creation uses the visitor's display name as the lead name for better traceability
- v17→v18: No major architectural changes; `visitor_ids` field on `crm.lead` was introduced in earlier versions and this module extends it
