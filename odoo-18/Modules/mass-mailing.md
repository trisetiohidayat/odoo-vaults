---
Module: mass_mailing
Version: Odoo 18
Type: Business
Tags: [email, marketing, mailing, campaign, newsletter, utm]
---

# mass_mailing — Email Marketing and Mailing Lists

## Overview

**Addon key:** `mass_mailing`
**Version:** 2.7
**Depends:** `contacts`, `mail`, `utm`, `link_tracker`, `web_editor`, `social_media`, `web_tour`, `digest`
**Application:** `True`
**Source path:** `~/odoo/odoo18/odoo/addons/mass_mailing/`

The mass mailing module handles bulk email campaigns. It manages mailing lists, contacts, campaign statistics, A/B testing, and tracking of emails (sent/delivered/opened/clicked/bounced). It does NOT send SMS directly — SMS support is in the separate `mass_mailing_sms` module.

---

## Module Map

```
mass_mailing
├── models/
│   ├── mailing.py                  ← mailing.mailing (campaign, A/B testing, statistics, send)
│   ├── mailing_list.py            ← mailing.list (static lists), _fetch_contact_statistics
│   ├── mailing_contact.py         ← mailing.contact (name, email, subscription_ids)
│   ├── mailing_subscription.py     ← mailing.subscription (join table, opt_out)
│   ├── mailing_subscription_optout.py ← mailing.subscription.optout (reasons)
│   ├── mailing_trace.py           ← mailing.trace (per-recipient statistics)
│   ├── mailing_filter.py          ← mailing.filter (saved domain filters)
│   ├── link_tracker.py            ← link.tracker (link click tracking)
│   ├── mail_blacklist.py          ← mail.blacklist extension (opt_out_reason_id)
│   ├── mail_thread.py             ← mail.thread extension (bounce tracking, reply detection)
│   ├── mail_mail.py               ← mail.mail extension (mailing_id link)
│   ├── ir_mail_server.py         ← ir.mail_server extension
│   ├── ir_http.py                 ← ir.http (UTM on landing pages)
│   └── [others: utm_campaign, utm_medium, utm_source, res_partner, res_users, res_company, res_config_settings, ir_model, mail_render_mixin]
├── wizard/
│   ├── mail_compose_message.py
│   ├── mailing_contact_import.py ← text-based bulk import wizard
│   ├── mailing_contact_to_list.py
│   ├── mailing_list_merge.py      ← merge mailing lists SQL
│   ├── mailing_mailing_test.py    ← test send to few recipients
│   ├── mailing_mailing_schedule_date.py
│   └── [others]
└── controllers/main.py            ← public unsubscribe/opt-in/unsubscribe endpoints
```

---

## Model: `mailing.mailing`

**File:** `models/mailing.py`
**Inheritance:** `mail.thread`, `mail.activity.mixin`, `mail.render.mixin`, `utm.source.mixin`

The central model for email campaigns. Holds campaign metadata, body content, recipients targeting, scheduling, and computed statistics.

### Core Identity Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | `Char` | Mailing name (campaign title) |
| `subject` | `Char` | Email subject line. Required |
| `preview` | `Char` | Email preview text (displayed in inbox next to subject) |
| `body_arch` | `Html` | Raw QWeb/HTML body editor content |
| `body_html` | `Html` | Rendered body (QWeb → HTML, post-processed) |
| `email_from` | `Char` | Sender email address |
| `reply_to` | `Char` | Reply-to address |

### Scheduling

| Field | Type | Notes |
|-------|------|-------|
| `schedule_type` | `Selection` | `'now'` (send immediately) or `'scheduled'` (send at `schedule_date`) |
| `schedule_date` | `Datetime` | Scheduled send datetime |
| `calendar_date` | `Datetime` (compute) | Actual send date for display: `sent_date` (if done), `next_departure` (if in queue), `now` (if sending) |
| `sent_date` | `Datetime` | When the mailing was actually sent |
| `state` | `Selection` | `'draft'` → `'in_queue'` → `'sending'` → `'done'` |

### Recipients

| Field | Type | Notes |
|-------|------|-------|
| `mailing_type` | `Selection` | `'mail'` (Email). Default. SMS is in `mass_mailing_sms` |
| `mailing_model_id` | `Many2one(ir.model)` | Target model. Default: `mailing.list`. Domain: `is_mailing_enabled=True` |
| `mailing_model_real` | `Char` (compute) | Actual model: `mailing.contact` if model is `mailing.list`, else the model itself |
| `mailing_on_mailing_list` | `Boolean` (compute) | True if targeting `mailing.list` |
| `mailing_domain` | `Char` (compute+store) | Domain filter on recipients |
| `contact_list_ids` | `Many2many(mailing.list)` | Mailing lists to target |
| `mailing_filter_id` | `Many2one(mailing.filter)` | Saved filter to apply |
| `mailing_filter_domain` | `Char` (related) | The filter's domain string |

### Statistics Computes — `_compute_statistics()`

All statistics come from `mailing.trace` records, grouped by `trace_status`. This runs via `_read_group` on every form view load:

```
trace_status = 'outgoing' → 'scheduled' (count)
trace_status = 'pending'  → 'pending'
trace_status = 'sent'     → 'sent'
'outgoing'/'process'/'pending'/'sent'/'open'/'reply'/'bounce'/'error'/'cancel'
```

**Key derived calculations:**
- `expected = sum(all statuses except links_click_datetime)`
- `delivered = sent + open + reply`
- `opened = open + reply`
- `received_ratio = 100 * delivered / expected`
- `opened_ratio = 100 * opened / (expected - canceled - bounced - failed)`
- `bounced_ratio = 100 * bounced / (expected - canceled - failed)`

`clicks_ratio` uses a separate direct SQL query (not `_read_group`) for performance.

### `_get_recipients()` — Recipient Resolution

```
1. Compute mailing_domain via _get_recipients_domain()
2. Search target model with that domain → res_ids
3. If A/B testing enabled:
   - Randomly sample (ab_testing_pc)% of recipients
   - Subtract already-mailed recipients from campaign
   - Pick at least 1 if any remain
```

### `_get_recipients_domain()` — Domain Parsing

Returns `_parse_mailing_domain()` (internal). The domain is composed from:
- Mailing list filter: `('list_ids', 'in', contact_list_ids.ids)` via `mailing.list._mailing_get_default_domain()`
- Applied saved filter: `literal_eval(mailing_filter_id.mailing_domain)`
- Custom domain set manually by user

### A/B Testing Fields

| Field | Type | Notes |
|-------|------|-------|
| `ab_testing_enabled` | `Boolean` | Enable A/B test mode |
| `ab_testing_pc` | `Integer` | Percentage of recipients for this variant (0–100) |
| `ab_testing_schedule_datetime` | `Datetime` | When to evaluate winner and send final mailing |
| `ab_testing_winner_selection` | `Selection` | `'opened_ratio'`, `'replied_ratio'`, `'clicks_ratio'`, `'manual'` |
| `ab_testing_completed` | `Boolean` (related) | From `campaign_id.ab_testing_completed` |
| `ab_testing_is_winner_mailing` | `Boolean` (compute) | True if this is the campaign's winner |
| `ab_testing_mailings_count` | `Integer` (related) | Sibling mailings in the campaign |
| `is_ab_test_sent` | `Boolean` (compute) | Any sibling A/B mailing is in `done` state |
| `kpi_mail_required` | `Boolean` | Trigger statistics email after send |

### `_action_send_mail()` — Send Flow

```
1. Compute mailing_res_ids via _get_remaining_recipients()
2. Create mail.compose.message in 'mass_mail' composition_mode
3. Set auto_delete, reply_to_mode, attachments, mailing_list_ids, mass_mailing_id
4. composer._action_send_mail(auto_commit=not testing)
5. Write state='done', sent_date=now
6. cr.commit() if auto_commit
```

**Auto-commit in production:** Uses threading.current_thread().testing flag to detect test mode and skip commit.

### `_process_mass_mailing_queue()` — Cron Entry Point

The `ir_cron_mass_mailing_queue` cron. Searches for mailings with `state in ('in_queue', 'sending')` and `schedule_date <= now()`. For each:
- Sets `state = 'sending'` and calls `_action_send_mail()`
- On completion, marks `state = 'done'` and schedules KPI report

The KPI email (`_action_send_statistics()`) is sent 1–5 days after completion if `mass_mailing.mass_mailing_reports` config param is set.

### `_get_opt_out_list()` — Suppression List

```
1. If target model has _mailing_get_opt_out_list():
   → calls it (e.g., mailing.list._mailing_get_opt_out_list())
2. Returns set of opted-out email addresses
3. Those addresses are excluded during mail composer _prepare_body()
```

### Key Action Methods

| Method | Behavior |
|--------|----------|
| `action_launch()` | Sets `schedule_type='now'` + calls `action_put_in_queue()` |
| `action_put_in_queue()` | Sets `state='in_queue'`, triggers cron |
| `action_cancel()` | Resets to `draft`, clears schedule |
| `action_retry_failed()` | Unlinks failed `mail.mail` + traces, requeues |
| `action_duplicate()` | Clones mailing (with same contact_list_ids) |
| `action_test()` | Opens `mailing.mailing.test` wizard |
| `action_schedule()` | Opens `mailing.mailing.schedule.date` wizard |
| `action_send_winner_mailing()` | Evaluates A/B winner, selects as winner, sends final 100% mailing |
| `action_select_as_winner()` | Copies mailing with `ab_testing_pc=100`, sets as campaign winner, sends |
| `action_compare_versions()` | Opens kanban of all sibling A/B mailings in campaign |
| `convert_links()` | Calls `_shorten_links()` on body_html to register link trackers |

---

## Model: `mailing.list`

**File:** `models/mailing_list.py`
**Inheritance:** `mail.thread`

A contact list (static or dynamic). The primary container for targeting email campaigns.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | `Char` | List name. Required |
| `active` | `Boolean` | Can be archived; blocked if used in ongoing mailing |
| `contact_ids` | `Many2many(mailing.contact)` | Direct contact membership (via `mailing_subscription` m2m) |
| `subscription_ids` | `One2many(mailing.subscription)` | Full subscription records (including opt-out) |
| `contact_count` | `Integer` (compute) | Total contacts |
| `contact_count_email` | `Integer` (compute) | Contacts with valid email, not opted out, not blacklisted |
| `contact_count_opt_out` | `Integer` (compute) | Opted-out contacts |
| `contact_count_blacklisted` | `Integer` (compute) | Blacklisted contacts |
| `contact_pct_opt_out` | `Float` (compute) | Percentage opted out |
| `contact_pct_blacklisted` | `Float` (compute) | Percentage blacklisted |
| `contact_pct_bounce` | `Float` (compute) | Percentage with `message_bounce > 0` |
| `mailing_count` | `Integer` (compute) | Mailings using this list |
| `is_public` | `Boolean` | Allow recipients to self-subscribe via portal |
| `display_name` | `Char` (compute) | Format: `"Name (count)"` |

### `_fetch_contact_statistics()` — SQL Statistics

Uses direct SQL (not ORM) for performance. Runs against `mailing_subscription` table with joins on `mailing_contact` and `mailing_blacklist`. Computes per-list:
- `contact_count`: COUNT(*)
- `contact_count_email`: SUM(CASE WHEN email_normalized IS NOT NULL AND opt_out=FALSE AND bl.id IS NULL)
- `contact_count_opt_out`: SUM(CASE WHEN opt_out=TRUE)
- `contact_count_blacklisted`: SUM(CASE WHEN bl.id IS NOT NULL)

Bounce percentage uses a separate SQL query.

### `_mailing_get_default_domain(mailing)`

Returns `[('list_ids', 'in', mailing.contact_list_ids.ids)]` — the domain applied to `mailing.contact` when this list is targeted.

### `_mailing_get_opt_out_list(mailing)`

Checks all subscriptions for this list's contacts. Returns normalized email addresses where the contact has `opt_out = True` for ANY of the involved lists (handles shared email across lists correctly).

### `action_merge(src_lists, archive)` — List Merging

SQL-based merge of multiple lists into `self`. Deduplicates by email_normalized, respects opt-outs, excludes blacklisted emails. Optionally archives source lists after merge.

### `_update_subscription_from_email(email, opt_out, force_message)` — Self-Service Opt-Out/In

Public-facing method for unsubscribe links and portal preference management:
- **opt_out=True**: Sets all subscriptions for this contact/lists to `opt_out=True`
- **opt_out=False**: Sets opted-out subscriptions back to active, and creates new subscriptions for missing public lists

---

## Model: `mailing.contact`

**File:** `models/mailing_contact.py`
**Inheritance:** `mail.thread.blacklist`

A lightweight contact record (separate from `res.partner`) optimized for large mailing lists.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | `Char` (compute+store) | Computed from `first_name` + `last_name` |
| `first_name` | `Char` | Populated if split-name view is active |
| `last_name` | `Char` | Used with `first_name` if split name enabled |
| `company_name` | `Char` | Company affiliation |
| `title_id` | `Many2one(res.partner.title)` | Title (Mr/Ms/Dr) |
| `email` | `Char` | Email address |
| `list_ids` | `Many2many(mailing.list)` | Direct list membership (write-side of subscription) |
| `subscription_ids` | `One2many(mailing.subscription)` | Full subscription records |
| `country_id` | `Many2one(res.country)` | Country for segmentation |
| `tag_ids` | `Many2many(res.partner.category)` | Tags |
| `opt_out` | `Boolean` (compute+search) | Per-list opt-out; context-dependent `default_list_ids` required |

### `_compute_name` / `_compute_opt_out`

Both use `default_list_ids` context. If exactly one list is in context, `opt_out` shows that specific subscription's value. This is a context-gated compute pattern.

### `add_to_list(name, list_id)` — Classmethod Utility

Parses `"Name <email>"` format and creates a contact + subscription in one call.

### `_message_get_default_recipients()`

Returns `email_to` (sanitized) with empty `partner_ids` — contacts don't have partner records.

---

## Model: `mailing.subscription`

**File:** `models/mailing_subscription.py`
**Inheritance:** (base)

The join table between `mailing.contact` and `mailing.list`. Stores the per-subscription opt-out state.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `contact_id` | `Many2one(mailing.contact)` | Ondelete cascade |
| `list_id` | `Many2one(mailing.list)` | Ondelete cascade |
| `opt_out` | `Boolean` | Subscription-level opt-out flag |
| `opt_out_reason_id` | `Many2one(mailing.subscription.optout)` | Ondelete restrict |
| `opt_out_datetime` | `Datetime` (compute+store) | Auto-set when `opt_out` becomes True |
| `message_bounce` | `Integer` (related, readonly=False) | From `contact_id.message_bounce` |
| `is_blacklisted` | `Boolean` (related) | From `contact_id.is_blacklisted` |

### SQL Constraint

`unique(contact_id, list_id)` — a contact can only subscribe once per list.

### `create()` / `write()` — Auto-Set opt_out

If either `opt_out_datetime` or `opt_out_reason_id` is set during create/write, `opt_out` is automatically set to `True`. This allows setting the reason without explicitly setting the boolean.

---

## Model: `mailing.trace`

**File:** `models/mailing_trace.py`
**Inheritance:** (base)

Per-recipient statistics record. Stored separately from `mail.mail` so statistics survive email deletion.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `trace_type` | `Selection` | `'mail'` (default). SMS in mass_mailing_sms |
| `mass_mailing_id` | `Many2one(mailing.mailing)` | Campaign link |
| `campaign_id` | `Many2one(utm.campaign)` | Via `mass_mailing_id.campaign_id` |
| `email` | `Char` | Normalized recipient email |
| `message_id` | `Char` | RFC 2392 Message-ID of the sent email |
| `model` | `Char` | Target model (e.g., `mailing.contact`) |
| `res_id` | `Many2oneReference` | Target record ID |
| `trace_status` | `Selection` | `'outgoing'` → `'process'` → `'pending'` → `'sent'` → `'open'` → `'reply'` → `'bounce'` / `'error'` / `'cancel'` |
| `sent_datetime` | `Datetime` | When email was sent |
| `open_datetime` | `Datetime` | When first opened |
| `reply_datetime` | `Datetime` | When replied to |
| `links_click_datetime` | `Datetime` | Last click timestamp |
| `links_click_ids` | `One2many(link.tracker.click)` | Click records for this trace |
| `failure_type` | `Selection` | `'mail_bounce'`, `'mail_email_invalid'`, `'mail_smtp'`, `'mail_bl'`, `'mail_optout'`, `'mail_dup'`, etc. |
| `failure_reason` | `Text` | Human-readable failure description |

### SQL Constraint

`CHECK(res_id IS NOT NULL AND res_id != 0)` — traces must have a valid target record.

### Status Transition Methods

| Method | Effect |
|--------|--------|
| `set_sent()` | `trace_status='sent'`, `sent_datetime=now`, `failure_type=False` |
| `set_opened()` | `trace_status='open'`, `open_datetime=now` (skips if already open/replied) |
| `set_clicked()` | `links_click_datetime=now` (also set by `set_opened` when links clicked) |
| `set_replied()` | `trace_status='reply'`, `reply_datetime=now` |
| `set_bounced()` | `trace_status='bounce'`, `failure_type='mail_bounce'`, `failure_reason=bounce_message` |
| `set_failed()` | `trace_status='error'`, `failure_type=failure_type` |
| `set_canceled()` | `trace_status='cancel'` |

---

## Model: `mailing.filter`

**File:** `models/mailing_filter.py`
**Inheritance:** (base)

Saves reusable domain filters for mailing targeting.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | `Char` | Filter name. Required |
| `mailing_domain` | `Char` | Domain expression string (e.g., `"[('country_id', '=', 1)]"`) |
| `mailing_model_id` | `Many2one(ir.model)` | The model this filter applies to |
| `mailing_model_name` | `Char` (related) | `mailing_model_id.model` |

### `_check_mailing_domain()` — Constraint

Validates the domain by calling `literal_eval` and running `search_count()` against the target model. Raises `ValidationError` if invalid.

---

## Model: `mailing.subscription.optout`

**File:** `models/mailing_subscription_optout.py`

Pre-defined reasons for unsubscribing or blacklisting.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | `Char` | Reason text (translatable) |
| `sequence` | `Integer` | Display order |
| `is_feedback` | `Boolean` | Whether this reason triggers a feedback form |

---

## Model: `mail.blacklist` (extension)

**File:** `models/mail_blacklist.py`
**Inheritance:** `_inherit = 'mail.blacklist'`

Adds opt-out reason tracking to the global email blacklist.

### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `opt_out_reason_id` | `Many2one(mailing.subscription.optout)` | Reason for blacklisting |

---

## Wizard: `mailing.contact.import`

**File:** `wizard/mailing_contact_import.py`

Text-based bulk import (not file upload).

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `mailing_list_ids` | `Many2many(mailing.list)` | Target lists |
| `contact_list` | `Text` | One email (or "Name <email>") per line |

### `action_import()`

1. Split input by newlines → parse with `tools.mail.email_split_tuples()`
2. If >5000 emails, redirect to `base_import` file import
3. Find existing contacts by `email_normalized` already in lists
4. Deduplicate: keep first non-empty name per email
5. For existing contacts not yet in these lists: add list membership
6. For new contacts: create `mailing.contact` with subscription records
7. Return notification with import count

---

## L4: Click/Open Rate Tracking

**Open tracking:** Relies on a 1x1 transparent GIF embedded in the email body. When the recipient's email client downloads the image, Odoo's web route `/mail/track/{tracking_id}/{unique_token}` calls `mailing.trace.set_opened()`.

**Click tracking:** Each URL in the body is shortened via `link.tracker`. When clicked, `/r/{short_code}` is intercepted, `link.tracker.click` is created, and `mailing.trace.set_clicked()` is called (which also triggers `set_opened()`).

**Reply tracking:** Gateway email replies are routed via `message_route()` → `mailing.trace.set_replied()` and `set_opened()`.

**Bounce handling:** `_routing_handle_bounce()` in `mail_thread.py` sets `trace_status='bounce'` and may auto-blacklist the email after 5+ bounces in 13 weeks with 1+ week gaps.

---

## L4: How `mailing_domain` is Applied

When a mailing targets `mailing.list`:
1. `mailing_model_real = 'mailing.contact'`
2. `mailing_domain = [('list_ids', 'in', contact_list_ids.ids)]` (via `_mailing_get_default_domain`)
3. This is the base domain; additionally filtered by saved `mailing_filter_id.mailing_domain`

When targeting a custom model (e.g., `res.partner`):
1. `mailing_model_real = 'res.partner'`
2. `mailing_domain` is set directly by the user or from a saved filter
3. The mailing goes to all partners matching the domain

The `mailing.contact` model inherits `mail.thread.blacklist`, which provides automatic bounce-blacklist integration via `_message_receive_bounce()`.

---

## L4: A/B Testing Flow

```
1. User enables ab_testing, sets percentage (e.g., 10%)
2. create() → _create_ab_testing_utm_campaigns() → creates utm.campaign with A/B config
3. User clicks "Send" → action_launch()
4. _get_recipients() randomly picks ab_testing_pc% of recipients
5. Mailing state → 'done' after sending (A/B variant sent)
6. Cron ir_cron_mass_mailing_ab_testing runs at ab_testing_schedule_datetime
7. _get_ab_testing_siblings_mailings() fetches all campaign variants
8. Winner selected by ab_testing_winner_selection (e.g., highest opened_ratio)
9. action_select_as_winner():
   - Copies mailing with ab_testing_pc=100, name+=" (final)"
   - Sets campaign.ab_testing_winner_mailing_id
   - Sends final mailing to remaining 90%
```

---

## L4: Blacklist Integration

Two suppression layers work together:
1. **`mail.blacklist`** — global hard block. Any address in the blacklist is skipped in the composer (`cancel` state, `mail_bl` failure type)
2. **`mailing.subscription.opt_out`** — per-list soft block. Contact is excluded from that specific list's send

Both are checked in `mailing.list._mailing_get_opt_out_list()` and by the `mail.thread.blacklist` mixin's `_mailing_blacklist_enabled` check during compose.

---

## L4: Dynamic Lists vs. Static Lists

There is NO `mailing.list.dynamic` model in the base `mass_mailing` module. Dynamic lists (auto-populated based on domain) are handled by the `mass_mailing` module's `mailing_domain` field combined with a saved `mailing.filter`. The domain-based targeting means the recipient set is re-evaluated at send time — no scheduled "list refresh" is needed. A true dynamic list (with automatic resubscription) requires the `mass_mailing` module's own domain filtering at send time rather than a separate model.

---

## Statistics Computed Fields on `mailing.mailing`

| Field | Compute | Definition |
|-------|---------|------------|
| `total` | `_compute_total` | `search_count(recipients_domain)` × A/B percentage |
| `scheduled` | `_compute_statistics` | Count where `trace_status = 'outgoing'` |
| `expected` | `_compute_statistics` | Sum of all non-link-click counts |
| `canceled` | `_compute_statistics` | `trace_status = 'cancel'` |
| `sent` | `_compute_statistics` | Count where `sent_datetime IS NOT NULL` |
| `pending` | `_compute_statistics` | `trace_status = 'pending'` |
| `delivered` | `_compute_statistics` | `sent + open + reply` |
| `opened` | `_compute_statistics` | `open + reply` |
| `clicked` | `_compute_statistics` | `links_click_datetime COUNT` |
| `replied` | `_compute_statistics` | `trace_status = 'reply'` |
| `bounced` | `_compute_statistics` | `trace_status = 'bounce'` |
| `failed` | `_compute_statistics` | `trace_status = 'error'` |
| `received_ratio` | `_compute_statistics` | `100 * delivered / expected` |
| `opened_ratio` | `_compute_statistics` | `100 * opened / (expected - canceled - bounced - failed)` |
| `clicks_ratio` | `_compute_clicks_ratio` | Direct SQL: `100 * distinct_clicks / distinct_mails` |

---

## Relations Summary

| From | To | O2M / M2O / M2M | Via |
|------|----|-----------|-----|
| `mailing.mailing` | `mailing.list` | M2M | `contact_list_ids` |
| `mailing.mailing` | `mailing.trace` | O2M | `mailing_trace_ids` |
| `mailing.mailing` | `utm.campaign` | M2O | `campaign_id` |
| `mailing.mailing` | `mailing.filter` | M2O | `mailing_filter_id` |
| `mailing.list` | `mailing.contact` | M2M | `mailing_subscription` |
| `mailing.list` | `mailing.subscription` | O2M | `subscription_ids` |
| `mailing.contact` | `mailing.subscription` | O2M | `subscription_ids` |
| `mailing.contact` | `mailing.list` | M2M | `list_ids` |
| `mailing.subscription` | `mailing.contact` | M2O | `contact_id` |
| `mailing.subscription` | `mailing.list` | M2O | `list_id` |
| `mailing.subscription` | `mailing.subscription.optout` | M2O | `opt_out_reason_id` |
| `mailing.trace` | `mailing.mailing` | M2O | `mass_mailing_id` |
| `mailing.trace` | `link.tracker.click` | O2M | `links_click_ids` |
| `mailing.trace` | `mail.mail` | M2O | `mail_mail_id` |

---

## See Also

- [Modules/Mail](mail.md) — mail.mail, mail.thread, mail.blacklist
- [Modules/UTM](utm.md) — utm.campaign, utm.source, utm.medium
- [Modules/Link Tracker](Modules/Link-Tracker.md) — link.tracker for click tracking
- [Patterns/Inheritance Patterns](Inheritance Patterns.md) — _inherit vs _inherits vs mixin
- [Core/API](API.md) — mail.render.mixin for QWeb template rendering
