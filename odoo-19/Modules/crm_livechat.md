---
type: module
module: crm_livechat
tags: [odoo, odoo19, crm, livechat, chatbot, lead]
created: 2026-04-06
---

# CRM Livechat

## Overview
| Property | Value |
|----------|-------|
| **Name** | CRM Livechat |
| **Technical** | `crm_livechat` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Creates CRM leads directly from livechat conversations using a `/lead` chatbot command or automatic conversion rules.

## Dependencies
- `crm`
- `im_livechat`

## Models

### crm.lead
Inherits `crm.lead`. Extends lead with livechat origin tracking.

**Fields:**
- `origin_channel_id` (Many2one `discuss.channel`) — The livechat session the lead was created from

**Key Methods:**
- `create()` — Validates that the user has read access to the channel
- `write()` — Validates access before linking a channel
- `action_open_livechat()` — Sends a bus notification to open the originating livechat channel in the UI via `Store` (Odoo's real-time bus)

### discuss.channel
Inherits `discuss.channel`. Livechat channels can be linked to leads via `origin_channel_id`.

**Key Methods:**
- `create()` — Sets `lead_ids` when channel is created with a lead
- `_get_message_values()` — Ensures `lead_ids` is set on lead creation
- `_chatbot_create_lead()` — Creates a lead from chatbot step data
- `_chatbot_create_lead_and_forward()` — Creates a lead and forwards to CRM team

### chatbot.script.step
Inherits `chatbot.script.step`. Adds lead creation step types.

**Key Methods:**
- `_chatbot_step_validate()` — For `create_lead` step type: creates a lead from the visitor's answers; for `create_lead_and_forward` type: also assigns to the selected CRM team

## Key Features

### Lead Creation from Livechat
- Leads store a reference to the originating `discuss.channel`
- Chatbot script steps define the lead creation flow via `/lead` command
- `create_lead` and `create_lead_and_forward` step types allow visitors to submit lead info through the chatbot

### Chatbot Integration
- `crm_livechat_chatbot_data.xml` defines chatbot steps for lead creation
- Steps handle the `/lead` command flow
- Data includes: question steps (name, email, company, country), contact preference, and lead creation steps

## Security
- Lead creation linked to a channel requires read access to that channel
- Group: `event.group_event_registration_desk` controls registration_id visibility

## Related
- [[Modules/crm]] — CRM base
- [[Modules/im_livechat]] — Live chat
- [[Modules/crm_mail_plugin]] — CRM email plugin
