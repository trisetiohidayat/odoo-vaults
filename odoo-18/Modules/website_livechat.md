---
Module: website_livechat
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_livechat
---

## Overview

Website live chat widget integration. Links livechat channels to websites, tracks visitor sessions, enables chat request initiation from the operator to website visitors, and passes visitor context (country, history, page) to the operator's chat window.

**Key Dependencies:** `im_livechat`, `website`, `website_crm_livechat`

**Python Files:** 8 model files

---

## Models

### im_livechat_channel.py — ImLivechatChannel

**Inheritance:** `im_livechat.channel`, `website.published.mixin`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `website_description` | Html | Yes | Translated, displayed on website channel page |

**Methods:**

| Method | Description |
|--------|-------------|
| `_compute_website_url()` | Returns `/livechat/channel/{slug}` |
| `_get_livechat_discuss_channel_vals()` | Adds `livechat_visitor_id` to channel vals, deletes conflicting chat requests |

---

### discuss_channel.py — DiscussChannel

**Inheritance:** `discuss.channel`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `livechat_visitor_id` | Many2one | Yes | `website.visitor`, btree_not_null index |

**Methods:**

| Method | Description |
|--------|-------------|
| `channel_pin()` | Override: unlinks empty livechat channels on unpin (cleanup) |
| `_to_store(store)` | Adds visitor info (name, country, history, website, lang, partner) to channel data |
| `_get_visitor_history_data(visitor)` | Returns last 3 `website.track` page visits for visitor info banner |
| `_get_visitor_history(visitor)` | Formats visitor history as arrow-separated string |
| `_format_visitor_history(history_data)` | Formats as `"Page Name (HH:MM) → Page Name (HH:MM)"` |
| `_get_visitor_leave_message()` | Returns visitor leave notification message |
| `message_post()` | Updates visitor's last visit on visitor message (not operator message) |

---

### website_visitor.py — WebsiteVisitor

**Inheritance:** `website.visitor`

| Field | Type | Store | Index | Notes |
|-------|------|-------|-------|-------|
| `livechat_operator_id` | Many2one | Yes | btree_not_null | Current livechat operator |
| `livechat_operator_name` | Char | No | — | Related operator name |
| `discuss_channel_ids` | One2many | Yes | readonly | Visitor's livechat channels |
| `session_count` | Integer | No | — | Count of channels with messages |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_auto_init()` | — | Creates `livechat_operator_id` column manually (skips ORM compute on install) |
| `_compute_livechat_operator_id()` | `@api.depends('discuss_channel_ids.*')` | Finds active livechat operator from channels |
| `_compute_session_count()` | `@api.depends('discuss_channel_ids')` | Counts channels with at least one message |
| `action_send_chat_request()` | — | Operator-initiated chat request: creates discuss_channel with livechat_active=True |
| `_merge_visitor(target)` | — | Moves discuss_channel_ids to target; updates channel partner links |
| `_upsert_visitor()` | — | Links visitor to discuss_channel from cookie on upsert |

---

### website.py — Website

**Inheritance:** `website`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `channel_id` | Many2one | Yes | `im_livechat.channel` — the livechat channel for this website |

**Methods:**

| Method | Description |
|--------|-------------|
| `_get_livechat_channel_info()` | Returns channel info dict; includes `force_thread` for active chat requests |
| `_get_livechat_request_session()` | Checks for active chat request for current visitor; handles guest switching |
| `get_suggested_controllers()` | Adds `('Live Support', '/livechat', 'website_livechat')` |

---

### chatbot_script.py — ChatbotScript

**Inheritance:** `chatbot.script`

| Method | Description |
|--------|-------------|
| `action_test_script()` | Returns URL action to `/chatbot/{id}/test` for testing |

---

### chatbot_script_step.py — ChatbotScriptStep

**Inheritance:** `chatbot.script.step`

| Method | Description |
|--------|-------------|
| `_chatbot_prepare_customer_values(discuss_channel, ...)` | Enriches partner values with visitor email, phone, country from `livechat_visitor_id` |

---

### ir_http.py — IrHttp

**Inheritance:** `ir.http`

| Method | Description |
|--------|-------------|
| `_get_translation_frontend_modules_name()` | Adds `'im_livechat'` to frontend translation modules |

---

### res_config_settings.py — ResConfigSettings

**Inheritance:** `res.config.settings`

| Field | Type | Notes |
|-------|------|-------|
| `channel_id` | Many2one | Related `website_id.channel_id`, readonly=False |

---

## Security / Data

**Security File:** `security/website_livechat.xml`

- `im_livechat_channel_rule_public`: Public/portal read only where `website_published=True`

**Access Control (`ir.model.access.csv`):**
- `chat.room`: No access (blank), User read, System full
- Various livechat channel and visitor permissions

**Data Files:**
- `data/website_livechat_data.xml`: Default channel configuration
- `data/website_livechat_chatbot_demo.xml`: Demo chatbot scripts

---

## Critical Notes

- `livechat_operator_id` is computed from the most recent active livechat channel for the visitor
- `action_send_chat_request` creates a `discuss.channel` with `livechat_active=True` and `livechat_visitor_id` set; if visitor has no partner, creates a `mail.guest`
- `channel_pin` override: when operator unpins an empty livechat channel, it is unlinked — this prevents orphaned empty channels
- `_to_store` wraps visitor info with try/except `AccessError` to prevent exposing restricted visitor data
- `_upsert_visitor` reads `im_livechat_uuid` cookie to link the new upserted visitor to an existing livechat session
- Chat request flow: operator sends request → creates channel with `livechat_active=True` → visitor navigates → `_handle_webpage_dispatch` picks up the request
- v17→v18: `discuss_channel.livechat_visitor_id` replaces older `livechat_visitor_id` linking mechanism; `mail.guest` integration was added
