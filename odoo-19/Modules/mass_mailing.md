---
tags:
  - #odoo19
  - #modules
  - #mass-mailing
  - #marketing
  - #orm
  - #fields
  - #api
  - #workflow
  - #security
---

# Mass Mailing Module

**Module:** `mass_mailing`
**Path:** `~/odoo/odoo19/odoo/addons/mass_mailing/`
**Odoo Version:** 19.0
**Category:** Marketing/Email Marketing
**Version:** 2.7
**License:** LGPL-3
**Application:** True

## Overview

The `mass_mailing` module provides comprehensive email marketing capabilities in Odoo. It enables users to design emails in a visual builder, send to contact lists or dynamic recipient domains, track opens/clicks/replies/bounces, and run A/B testing campaigns. Statistics are stored in a separate `mailing.trace` table to allow `mail.mail` records to be deleted without losing tracking data.

## Dependencies

```
contacts          → mailing.contact (res.partner base)
mail              → mail.mail, mail.thread, mail.blacklist, mail.compose.message
html_builder      → QWeb-based email body rendering in the builder
utm               → utm.campaign, utm.source, utm.medium (UTM tracking)
link_tracker      → Click tracking, shortened URLs
social_media      → Social media links in company footer
web_tour          → Onboarding tours
digest            → KPI statistics email templates
```

Also extends: `res.partner`, `res.company`, `ir.model`, `mail.thread`, `mail.render.mixin`, `mail.mail`, `mail.blacklist`, `link.tracker`, `link.tracker.click`, `utm.campaign`, `utm.medium`, `utm.source`.

## Key Design Principles

- **`_mailing_enabled = True`** class attribute marks any model as a valid mailing target. Applied to: `mailing.contact`, `mailing.list`, `res.partner`.
- **`_unrestricted_rendering = True`** on `mailing.mailing` allows rendering any template field (bypasses standard record rule checks during QWeb rendering for mass mail).
- Statistics are stored in **`mailing.trace`** — a separate table from `mail.mail` so that deleting sent emails does not destroy tracking data.
- **`mail_blacklist`** is the global suppression list; **`mailing.subscription`** with `opt_out` is per-list opt-out. Both are respected during send.
- **`properties.base.definition.mixin`** is inherited by `mailing.contact` to support property fields on contacts.
- **Two-body architecture**: `body_arch` stores raw HTML from the builder (editable); `body_html` stores the QWeb-rendered version used for actual sending.

## Module Loading Order

```python
ir_http
ir_mail_server
ir_model
link_tracker
mail_blacklist
mailing_subscription   # must load before mailing_contact and mailing_list
mailing_contact
mailing_list
mailing_subscription_optout
mailing_trace
mailing               # main model
mailing_filter
mail_mail
mail_render_mixin
mail_thread
res_company
res_config_settings
res_partner
res_users
utm_campaign
utm_medium
utm_source
```

---

## Models

### `mailing.mailing` — Mass Mailing

Central model representing a single email campaign (or reusable template). Inherits `mail.thread`, `mail.activity.mixin`, `mail.render.mixin`, and `utm.source.mixin`.

#### Fields

**Identity & Content**

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | required | Campaign name shown in list/kanban view |
| `subject` | Char | required | Email subject line |
| `preview` | Char | — | Preview text (shown next to subject in inboxes). Rendered via `inline_template`, `post_process=True` |
| `email_from` | Char | computed | Sender address. Falls back to: user email → mail server's `from_filter` match → notification email |
| `reply_to` | Char | computed | Reply-to address based on `reply_to_mode` |
| `reply_to_mode` | Selection | computed | `'update'` = replies go to document thread; `'new'` = replies go to specific email. Auto-set: `res.partner`, `mailing.list`, `mailing.contact` get `'new'` |
| `body_arch` | Html | — | Raw HTML from the email builder. `sanitize='email_outgoing'`, `translate=False` |
| `body_html` | Html | — | QWeb-rendered body for sending. `render_engine='qweb'`, `post_process=True` |
| `is_body_empty` | Boolean | computed | True when `body_arch` is empty/void |
| `attachment_ids` | Many2many `ir.attachment` | — | `bypass_search_access=True`; owned by the mailing record |

**Scheduling**

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `state` | Selection | `'draft'` | `'draft'` → `'in_queue'` → `'sending'` → `'done'` |
| `schedule_type` | Selection | `'now'` | `'now'` or `'scheduled'` |
| `schedule_date` | Datetime | computed/false | Cleared when `schedule_type = 'now'` |
| `calendar_date` | Datetime | computed | Unified display: `sent_date` if done, `next_departure` if queued, now if sending |
| `sent_date` | Datetime | — | When mailing finished sending (written on state=done) |
| `next_departure` | Datetime | computed | Cron pickup time. `max(schedule_date, now())` to guard past dates |
| `next_departure_is_past` | Boolean | computed | Flags overdue mailings stuck in queue |
| `keep_archives` | Boolean | `False` | If True, `mail.mail` records are kept after send |

**Recipients**

| Field | Type | Notes |
|-------|------|-------|
| `mailing_model_id` | Many2one `ir.model` | Target model; domain: `is_mailing_enabled = True`. Default: `mailing.list` |
| `mailing_model_name` | Char (related) | The actual model name string |
| `mailing_model_real` | Char (computed) | Resolves `mailing.list` → `mailing.contact`; otherwise equals `mailing_model_name` |
| `mailing_on_mailing_list` | Boolean (computed) | True when `mailing_model_id = mailing.list` |
| `contact_list_ids` | Many2many `mailing.list` | Direct list selection; used when targeting `mailing.list` |
| `mailing_domain` | Char | Stored as `repr(domain)` (string); parsed at send time via `_parse_mailing_domain()` |
| `mailing_filter_id` | Many2one `mailing.filter` | Saved filter; constrained to same model as mailing |
| `mailing_filter_domain` | Char (related) | Domain from the saved filter |
| `mailing_filter_count` | Integer | Count of saved filters available for this model |

**UTM / Campaign**

| Field | Type | Notes |
|-------|------|-------|
| `campaign_id` | Many2one `utm.campaign` | Groups related mailings; `ondelete='set null'` |
| `medium_id` | Many2one `utm.medium` | Auto-set to `email` for `mailing_type='mail'` |
| `source_id` | Many2one (inherited `utm.source.mixin`) | UTM source |

**A/B Testing**

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `ab_testing_enabled` | Boolean | `False` | Each enabled mailing is a campaign variant |
| `ab_testing_pc` | Integer | `10` | % of contacts receiving this variant. Constraint: 0–100 |
| `ab_testing_schedule_datetime` | Datetime | now+1day | When to evaluate and send winner |
| `ab_testing_winner_selection` | Selection | `'opened_ratio'` | `'manual'`, `'opened_ratio'`, `'clicks_ratio'`, `'replied_ratio'` |
| `ab_testing_is_winner_mailing` | Boolean | computed | True if `campaign_id.ab_testing_winner_mailing_id == self` |
| `ab_testing_completed` | Boolean | related | From `campaign_id.ab_testing_completed` |
| `ab_testing_mailings_count` | Integer | related | From `campaign_id` |
| `ab_testing_description` | Html | computed | Rendered A/B info panel (`mass_mailing.ab_testing_description` QWeb) |
| `is_ab_test_sent` | Boolean | computed | True when any sibling A/B variant is in `state='done'` |
| `kpi_mail_required` | Boolean | — | Flag to send 24H stats email to responsible |

**Mail Server**

| Field | Type | Notes |
|-------|------|-------|
| `mail_server_id` | Many2one `ir.mail_server` | Per-mailing override; falls back to lowest-sequence active server |
| `mail_server_available` | Boolean | Computed from `mass_mailing.outgoing_mail_server` config param |
| `warning_message` | Char | Non-matching `email_from` + server from-filter warning |

**Statistics (all computed, read from `mailing.trace`)**

| Field | Type | Computation |
|-------|------|-------------|
| `total` | Integer | `search_count` on recipient model with domain; reduced by `ab_testing_pc` for A/B |
| `scheduled` | Integer | traces with `trace_status='outgoing'` |
| `expected` | Integer | Sum of all traces (total targeted) |
| `canceled` | Integer | `trace_status='cancel'` |
| `sent` | Integer | `COUNT(sent_datetime)` (SMTP-accepted = delivered) |
| `process` | Integer | `trace_status='process'` (SMS: held at IAP) |
| `pending` | Integer | `trace_status='pending'` (SMS: sent but unconfirmed) |
| `delivered` | Integer | `sent + open + reply` |
| `opened` | Integer | `open + reply` (reply implies open) |
| `clicked` | Integer | `COUNT(links_click_datetime)` (unique clicks) |
| `replied` | Integer | `trace_status='reply'` |
| `bounced` | Integer | `trace_status='bounce'` |
| `failed` | Integer | `trace_status='error'` |
| `received_ratio` | Float | `100 * delivered / expected` |
| `opened_ratio` | Float | `100 * opened / (expected - canceled - bounced - failed)` |
| `replied_ratio` | Float | Same denominator as `opened_ratio` |
| `bounced_ratio` | Float | `100 * bounced / (expected - canceled - failed)` |
| `clicks_ratio` | Float | Raw SQL: distinct clicks / distinct delivered emails |
| `link_trackers_count` | Integer | Count of `link.tracker` records |

**Other**

| Field | Type | Notes |
|-------|------|-------|
| `mailing_trace_ids` | One2many `mailing.trace` | All tracking records for this mailing |
| `use_exclusion_list` | Boolean | `True` default; disables blacklist checking if False |
| `favorite` | Boolean | Starred/pinned mailing templates |
| `favorite_date` | Datetime | When the mailing was favorited |
| `active` | Boolean | Allows archiving mailings |
| `color` | Integer | Kanban color |
| `user_id` | Many2one `res.users` | Responsible; context user during send |
| `mailing_type` | Selection | Currently only `'mail'` (SMS in sub-module) |
| `mailing_type_description` | Char | Human-readable type label |

#### Constraints

```python
CHECK(ab_testing_pc >= 0 AND ab_testing_pc <= 100)
CHECK(email_from IS NOT NULL OR mailing_type != 'mail')  # email_from required for email
```

#### Key Methods

**Lifecycle / Actions**

- **`action_launch()`** — Sets `schedule_type='now'`, calls `action_put_in_queue()`.
- **`action_schedule()`** — Opens schedule date wizard if date is in the future, otherwise calls `action_put_in_queue()`.
- **`action_put_in_queue()`** — Sets `state='in_queue'`, triggers `ir_cron_mass_mailing_queue` at each mailing's `schedule_date`.
- **`action_cancel()`** — Resets to draft, clears `schedule_date`, `schedule_type`, `next_departure`.
- **`action_retry_failed()`** — Deletes failed `mail.mail` records + traces in batches of 1000, then re-queues. Prevents memory exhaustion on large mailings.
- **`action_duplicate()`** — Duplicates mailing including `contact_list_ids`.
- **`action_set_favorite()` / `action_remove_favorite()`** — Toggle pinned state.

**Statistics / Tracing Views**

- **`action_view_traces_scheduled/canceled/failed/process/sent()`** — Open `mailing.trace` list filtered by status.
- **`action_view_opened/replied/clicked/bounced/delivered()`** — Reverse-maps `mailing.trace.res_id` to actual business records via `_action_view_documents_filtered()`. Uses `mailing.trace` `res_id` as the domain filter against the real recipient model.

**A/B Testing**

- **`action_compare_versions()`** — Opens kanban/list of all A/B variants in same campaign: `Domain.AND([campaign_id, ab_testing_enabled, mailing_type])`.
- **`action_send_winner_mailing()`** — Called by cron or manually. Sorts sibling mailings (by the configured winner metric, or manually selected) and calls `action_select_as_winner()` on the best performer. Raises if no variant has been sent yet.
- **`action_select_as_winner()`** — Copies mailing with `ab_testing_pc=100`, adds `"(final)"` suffix to name, sets it as `campaign_id.ab_testing_winner_mailing_id`, then calls `action_launch()`. The copy is the actual final mailing sent to 100% of the remaining campaign audience.
- **`_get_ab_testing_siblings_mailings()`** — Returns `campaign_id.mailing_mail_ids.filtered(ab_testing_enabled)`.
- **`_get_ab_testing_winner_selection()`** — Returns `{value, description}` dict for the configured metric.

**Sending Pipeline**

- **`_get_recipients()`** — Evaluates `mailing_domain` via `_get_recipients_domain()` into record IDs. For A/B tests: randomly picks `ab_testing_pc`% of contacts, excluding already-mailed contacts from the campaign (via `_get_mailing_recipients()`).
- **`_get_remaining_recipients()`** — Subtracts already-traced `res_id`s from `_get_recipients()`. For winner mailings, subtracts all sibling traces across all variants.
- **`_get_recipients_domain()`** — Delegates to `_parse_mailing_domain()` → `_get_default_mailing_domain()`. Overrideable by sub-modules.
- **`_action_send_mail(res_ids)`** — Creates a `mail.compose.message` in `mass_mail` composition mode and calls `_action_send_mail` on it. Sets `state=done`, `sent_date`. Auto-commits outside of test mode.
- **`_process_mass_mailing_queue()`** — Cron job. Picks up `state in ('in_queue','sending')` where `schedule_date <= now`. Processes each mailing, then checks for and sends KPI statistics emails if `mass_mailing.mass_mailing_reports` config param is set. Calls `ir.cron._commit_progress(processed=1)` after each mailing.

**Recipient Token / Unsubscribe**

- **`_generate_mailing_recipient_token(document_id, email)`** — HMAC-SHA512 using `database.secret`, dbname, mailing ID, document ID, and email. Used for unsubscribe/view URL authentication.
- **`_get_unsubscribe_url(email_to, res_id)`** — `/mailing/{id}/unsubscribe?...` — email-specific unsubscribe link.
- **`_get_unsubscribe_oneclick_url(email_to, res_id)`** — `/mailing/{id}/unsubscribe_oneclick?...` — POST-based RFC 8058 one-click unsubscribe.
- **`_get_view_url(email_to, res_id)`** — `/mailing/{id}/view?...` — email-specific view-in-browser link.

**Inline Images**

- **`_convert_inline_images_to_urls(html_content)`** — Finds `data:image/...;base64,...` URLs in `img` tags, inline styles, and MS Office VML comments. For each: creates an `ir.attachment` on `mailing.mailing` (deduplicates by checksum), replaces data URL with `/web/image/{id}?access_token=...`. Also fetches and crops VML images via `requests.Session`.
- **`_create_attachments_from_inline_images(b64images)`** — Creates or reuses existing `ir.attachment` records by checksum. Generates access tokens. Returns list of access URLs.

**Create / Write Overrides**

- **`create(vals_list)`** — Triggers A/B cron if `ab_testing_schedule_datetime` is set. Calls `_create_ab_testing_utm_campaigns()`. Calls `_fix_attachment_ownership()` to set `res_model=mailing.mailing` on attachments. Converts inline images in both `body_arch` and `body_html`.
- **`write(vals)`** — Converts inline images. Validates that removing a campaign from an A/B-enabled mailing raises. Triggers A/B cron if schedule changes. Calls `_create_ab_testing_utm_campaigns()` if A/B newly enabled.

#### Performance Considerations

- `_compute_statistics()` uses a single `_read_group` query to fetch all trace statuses.
- `_compute_clicks_ratio()` uses raw SQL for efficiency.
- `action_retry_failed()` processes in batches of 1000.
- `_process_mass_mailing_queue()` commits after each mailing to avoid long transactions.
- Inline image deduplication by checksum avoids creating duplicate attachment records.

#### Odoo 18 to 19 Changes

- `contact_ab_pc` field and UI removed; A/B testing now uses `ab_testing_pc` directly on `mailing.mailing`.
- `body_arch` / `body_html` two-field architecture formalized: `body_arch` = raw builder output, `body_html` = QWeb rendered.
- `is_wizard` field and wizard code removed.
- `action_send_mailing()` on `mailing.list` now explicitly passes `default_mailing_type='mail'`.

---

### `mailing.contact` — Mailing Contact

A lightweight contact model separate from `res.partner`. Holds only name, email, and metadata to avoid bloating the partner database when emailing large lists.

**Inherits:** `mail.thread.blacklist` (gives `is_blacklisted`, `message_bounce`), `properties.base.definition.mixin`.

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | `compute='_compute_name'`, `store=True`; joined from `first_name` + `last_name` |
| `first_name` | Char | Hidden if `mailing_contact_view_tree_split_name` view is not active |
| `last_name` | Char | Same as above |
| `company_name` | Char | Free-text company name (not a Many2one to `res.partner`) |
| `email` | Char | Stored email; `email_normalized` auto-computed by `mail.thread.blacklist` |
| `list_ids` | Many2many `mailing.list` | Through `mailing_subscription` |
| `subscription_ids` | One2many `mailing.subscription` | Per-list subscription records |
| `country_id` | Many2one `res.country` | For geolocation segmentation |
| `tag_ids` | Many2many `res.partner.category` | Reuses partner tags |
| `opt_out` | Boolean | `compute='_compute_opt_out'`, `search='_search_opt_out'`. **Context-dependent**: only meaningful with exactly 1 `default_list_ids` |

#### Key Methods

- **`_compute_name()`** — Joins `first_name` and `last_name` with a space; skips falsy parts.
- **`_search_opt_out()`** — Custom search. Returns `Domain.FALSE` unless exactly 1 `default_list_ids` is in context; otherwise returns contacts with opted-out subscriptions to that list.
- **`_compute_opt_out()`** — Looks up subscription to the single active list in context and returns its `opt_out` value.
- **`_is_name_split_activated()`** — Checks if `mailing_contact_view_tree_split_name` view is active.
- **`name_create(name)`** — Parses `Name <email>` via `tools.parse_contact_from_email()`.
- **`add_to_list(name, list_id)`** — Utility: parses name from email-style string, creates contact with subscription.

#### `create()` Override — `list_ids` / `subscription_ids` Duality

When `default_list_ids` is in context and `list_ids` is not in vals, automatically promotes `default_list_ids` into `subscription_ids` (so that `opt_out` can be computed from subscriptions). Raises `UserError` if both are provided. After creation, manually invalidates `subscription_ids` / `list_ids` cache because the M2M through table does not auto-update the ORM cache for the paired field.

---

### `mailing.list` — Mailing List

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required |
| `active` | Boolean | Cannot archive if used by a mailing with `state != 'done'` |
| `contact_ids` | Many2many `mailing.contact` | Through `mailing_subscription` |
| `subscription_ids` | One2many `mailing.subscription` | `depends=['contact_ids']` |
| `mailing_ids` | Many2many `mailing.mailing` | Through `mail_mass_mailing_list_rel` |
| `contact_count` | Integer | All subscribed contacts (including opted-out, blacklisted) |
| `contact_count_email` | Integer | Valid email + not opted-out + not blacklisted |
| `contact_count_opt_out` | Integer | Opted-out contacts |
| `contact_count_blacklisted` | Integer | Blacklisted contacts |
| `contact_pct_opt_out / _blacklisted / _bounce` | Float | Percentage calculations |
| `mailing_count` | Integer | Mailings using this list |
| `is_public` | Boolean | If True, shown in portal subscription management page |

#### `_compute_mailing_list_statistics()` — Three-Phase SQL

1. **`_fetch_contact_statistics()`** — Raw SQL via `_get_contact_statistics_fields()` / `_get_contact_statistics_joins()`. Runs `flush_all()` first. Returns dict keyed by list ID. This architecture (separate queries, overridable helpers) allows `mass_mailing_sms` to override the field/join definitions.

2. **Bounce SQL** — Separate query counting contacts with `message_bounce > 0` joined through `mailing_subscription`.

3. **Assignment** — Sets all count/pct fields; guards division by zero.

#### Key Methods

- **`action_merge(src_lists, archive)`** — SQL merge using `row_number() OVER (PARTITION BY email)`. Picks one contact per email. Excludes opted-out and blacklisted. If `archive=True`, archives absorbed lists.
- **`_update_subscription_from_email(email, opt_out, force_message)`** — Portal unsubscribe handler. Opt-out: sets `opt_out=True` on subscriptions to this list. Opt-in: reverses opted-out subscriptions AND creates new subscription records for missing lists (if those lists are public). Logs a note on the contact via `message_post()`.
- **`_mailing_get_default_domain(mailing)`** — `[('list_ids', 'in', mailing.contact_list_ids.ids)]`.
- **`_mailing_get_opt_out_list(mailing)`** — Returns set of `email_normalized` opted-out on ANY involved list. Uses symmetric set difference: opt-out emails not also opted-in.

---

### `mailing.subscription` — Subscription (Join Table)

Intermediate model and M2M through table for `mailing.contact` ↔ `mailing.list`.

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `contact_id` | Many2one `mailing.contact` | `ondelete='cascade'` |
| `list_id` | Many2one `mailing.list` | `ondelete='cascade'`, indexed |
| `opt_out` | Boolean | `False` by default |
| `opt_out_reason_id` | Many2one `mailing.subscription.optout` | `ondelete='restrict'` |
| `opt_out_datetime` | Datetime | `compute='_compute_opt_out_datetime'`, `store=True`; set to `now()` when `opt_out=True` |
| `message_bounce` | Integer | Related from `contact_id` |
| `is_blacklisted` | Boolean | Related from `contact_id` |

#### `create()` / `write()` Override

If either `opt_out_datetime` or `opt_out_reason_id` is provided, `opt_out` is forced to `True`. Allows setting reason without explicitly passing `opt_out=True`.

#### Constraint

`unique(contact_id, list_id)` at DB level — prevents duplicate subscriptions.

---

### `mailing.subscription.optout` — Opt-Out Reason

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Reason description (translatable) |
| `sequence` | Integer | Display order |
| `is_feedback` | Boolean | Triggers free-text feedback prompt in portal |

---

### `mailing.trace` — Mailing Statistics

One record per email sent. Separate table from `mail.mail` to preserve tracking data when mail records are deleted.

#### `trace_status` Lifecycle

```
outgoing → process → pending → sent → open → reply
                              ↘ bounce
           ↘ error
           ↘ cancel
```

| Status | Meaning |
|--------|---------|
| `outgoing` | Created, not yet processed |
| `process` | Held at IAP (SMS; email typically skips this) |
| `pending` | Sent, delivery not confirmed (SMS) |
| `sent` | SMTP accepted = delivered |
| `open` | Tracking pixel fired |
| `reply` | Gateway reply detected (implies open) |
| `bounce` | Delivery permanently failed |
| `error` | Exception during send |
| `cancel` | Canceled before send |

#### `failure_type` Values

**Generic:** `unknown`
**Email:** `mail_bounce`, `mail_spam`, `mail_email_invalid`, `mail_email_missing`, `mail_from_invalid`, `mail_from_missing`, `mail_smtp`
**Mass-mode blocks:** `mail_bl` (blacklisted), `mail_dup` (duplicate in campaign), `mail_optout`
**SMS (mass_mailing_sms):** `sms_number_missing`, `sms_number_format`, `sms_credit`, `sms_server`, `sms_acc`, `sms_country_not_supported`, `sms_registration_needed`, `sms_blacklist`, `sms_duplicate`, `sms_optout`

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `trace_type` | Selection | Only `'mail'` in this module |
| `is_test_trace` | Boolean | Excluded from statistics |
| `mail_mail_id` | Many2one `mail.mail` | The actual email record |
| `mail_mail_id_int` | Integer | Survives `mail.mail` deletion; needed by controllers |
| `email` | Char | Normalized email address |
| `message_id` | Char | RFC 2392 Message-ID of sent email |
| `model` | Char | Target model name |
| `res_id` | Many2oneReference | Target record ID |
| `mass_mailing_id` | Many2one `mailing.mailing` | `ondelete='cascade'` |
| `campaign_id` | Many2one (related, stored) | From `mass_mailing_id.campaign_id`; stored for efficient filtering |
| `trace_status` | Selection | Status values above |
| `sent_datetime` | Datetime | When SMTP accepted |
| `open_datetime` | Datetime | When tracking pixel fired |
| `reply_datetime` | Datetime | When gateway reply detected |
| `links_click_datetime` | Datetime | Last click (for multi-click) |
| `failure_type` | Selection | Error classification |
| `failure_reason` | Text | Human-readable failure detail |
| `links_click_ids` | One2many `link.tracker.click` | Click records |

#### Key Methods

All status-setter methods accept an optional `domain` parameter to extend the recordset via search.

- **`set_sent(domain)`** — `trace_status='sent'`, `sent_datetime=now`, clears `failure_type`.
- **`set_opened(domain)`** — `trace_status='open'`, `open_datetime=now`. Skips already-opened or replied traces.
- **`set_clicked(domain)`** — Updates `links_click_datetime`.
- **`set_replied(domain)`** — `trace_status='reply'`, `reply_datetime=now`.
- **`set_bounced(domain, bounce_message)`** — `trace_status='bounce'`, `failure_type='mail_bounce'`, stores bounce message.
- **`set_failed(domain, failure_type)`** — `trace_status='error'`.
- **`set_canceled(domain)`** — `trace_status='cancel'`.

---

### `mailing.filter` — Saved Filters

Stores reusable domain filters for mailing recipient selection.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Filter name |
| `mailing_domain` | Char | Stored as string (repr of domain) |
| `mailing_model_id` | Many2one `ir.model` | Target model |
| `mailing_model_name` | Char (related) | Model name |

**Constraint:** `mailing_domain` is validated by executing `search_count()` on the target model.

---

### `link.tracker` — Link Tracker (Extended)

Added: `mass_mailing_id` Many2one — links shortened URLs to their parent mailing.

---

### `link.tracker.click` — Link Click (Extended)

Added: `mailing_trace_id` Many2one, `mass_mailing_id` Many2one.

When `add_click(code, mailing_trace_id=...)` is called:
1. Propagates `campaign_id` + `mass_mailing_id` into the click record.
2. Calls `mailing_trace_id.set_opened()` and `set_clicked()`.

This is how clicking a tracked link counts as "opened".

---

### `mail.mail` — Mail (Extended)

| Field Added | Type | Notes |
|-------------|------|-------|
| `mailing_id` | Many2one `mailing.mailing` | Parent mailing |
| `mailing_trace_ids` | One2many `mailing.trace` | Statistics records |

#### `_prepare_outgoing_body()` Override

Appends a 1x1 transparent GIF tracking pixel (`/mail/track/{id}/{token}/blank.gif`). Rewrites shortened URLs (`/r/{code}`) to include `/m/{trace_id}` so the trace can be identified on click.

#### `_prepare_outgoing_list()` Override

For each email in the batch:
- Replaces `/unsubscribe_from_list` placeholder with recipient-specific unsubscribe URL.
- Replaces `/view` placeholder with recipient-specific view-in-browser URL.
- Adds headers: `List-Unsubscribe`, `List-Unsubscribe-Post`, `Precedence: list`, `X-Auto-Response-Suppress: OOF`.

#### `_postprocess_sent_message()` Override

- If `failure_type` present: `mailing_trace_ids.set_failed(failure_type)`.
- Else: `mailing_trace_ids.set_sent()`.

#### `_gc_canceled_mail_mail()` — Auto-Vacuum

`@api.autovacuum`. Deletes `mail.mail` in `cancel` state older than `mass_mailing.cancelled_mails_months_limit` (default 6 months). Also unlinks associated `mail.message`. Limit: 10,000 per run.

---

### `mail.thread` — Mail Thread (Extended)

#### `_message_route_process()` Override

After routing an incoming email reply, searches `mailing.trace` for records matching `message_id` (from `References` header) and calls `set_opened()` + `set_replied()`. This tracks email replies as engagement.

#### `_routing_handle_bounce()` Override

1. Calls `mailing.trace.set_bounced()` for matching traces.
2. Auto-blacklist check: if email has bounced >= 5 times in last 13 weeks (bounces at least 1 week apart), auto-adds to `mail.blacklist`. `BLACKLIST_MAX_BOUNCED_LIMIT = 5`.
3. Bounce message stored in `mailing.trace.failure_reason`.

#### `message_new()` Override

When processing an incoming email that creates a new record (e.g., `crm.lead`), copies UTM data from the matching `mailing.trace` (`campaign_id`, `source_id`, `medium_id`) into the new record. Ensures UTM attribution from email replies.

---

### `mail.render.mixin` — Render Mixin (Extended)

#### `_render_template_postprocess()` Override

After standard rendering (relative→absolute URL conversion), applies the link shortener if `post_convert_links` is in context. Blacklists `/unsubscribe_from_list`, `/view`, `/cards` from shortening.

---

### `mail.blacklist` — Blacklist (Extended)

Added: `opt_out_reason_id` Many2one `mailing.subscription.optout`.

#### `_track_subtype()` Override

When `opt_out_reason_id` is set/changed, triggers `mail.mt_comment` subtype (creates a chatter message).

---

### `ir.model` — IrModel (Extended)

Added `is_mailing_enabled` Boolean (computed from `_mailing_enabled` class attribute). Domain for recipient model selection in the mailing form.

---

### `utm.campaign` — UTM Campaign (Extended)

| Field Added | Type | Notes |
|-------------|------|-------|
| `mailing_mail_ids` | One2many `mailing.mailing` | `domain=[('mailing_type','=','mail')]` |
| `mailing_mail_count` | Integer | Total mailings |
| `is_mailing_campaign_activated` | Boolean | User has `group_mass_mailing_campaign` |
| `ab_testing_mailings_count` | Integer | A/B variants in campaign |
| `ab_testing_completed` | Boolean | Winner selected |
| `ab_testing_winner_mailing_id` | Many2one `mailing.mailing` | The winning variant |
| `ab_testing_schedule_datetime` | Datetime | When to evaluate |
| `ab_testing_winner_selection` | Selection | `'manual'`, `'opened_ratio'`, `'clicks_ratio'`, `'replied_ratio'` |
| `received/opened/replied/bounced_ratio` | Float | Aggregated across all campaign mailings |

#### `_cron_process_mass_mailing_ab_testing()`

For each campaign where `ab_testing_schedule_datetime <= now`, `ab_testing_winner_selection != 'manual'`, and `ab_testing_completed = False`: calls `action_send_winner_mailing()` on the best-performing variant.

---

### `utm.medium` / `utm.source` — UTM Extensions

Both add `@api.ondelete(at_uninstall=False) _unlink_except_linked_mailings()`: prevents deletion if any `mailing.mailing` references them. Raises `UserError` with list of linked mailing subjects.

---

### `res.partner` — Partner (Extended)

Sets `_mailing_enabled = True`, enabling `res.partner` as a valid mailing recipient model.

---

### `res.company` — Company (Extended)

Adds `_get_social_media_links()` returning a dict of `social_facebook`, `social_linkedin`, `social_twitter`, `social_instagram`, `social_tiktok`. Used in email footer templates.

---

## Controller — `MassMailController`

All routes in `controllers/main.py`.

### Unsubscribe Flow

| Route | Auth | Method | Purpose |
|-------|------|--------|---------|
| `/mailing/{id}/unsubscribe_oneclick` | public | POST | RFC 8058 one-click unsubscribe |
| `/mailing/{id}/confirm_unsubscribe` | public | GET | Confirmation page before opt-out |
| `/mailing/{id}/unsubscribe` | public | GET | Full unsubscribe page with list preferences |
| `/mailing/confirm_unsubscribe` | public | POST | Backwards-compatible unsubscribe |
| `/mailing/list/update` | public | JSON | Update list subscriptions |
| `/mailing/feedback` | public | JSON | Submit opt-out reason + free-text feedback |

#### `_check_mailing_email_token()` — Token Validation Logic

```
hash_token REQUIRED if:
  - public user
  - logged-in user viewing specific mailing without group_mass_mailing_user

hash_token NOT REQUIRED if:
  - logged-in user with group_mass_mailing_user
  - generic page (no mailing_id)
```

Uses `hmac.compare` (constant-time) to prevent timing attacks.

#### `_mailing_unsubscribe_from_list()` vs `_mailing_unsubscribe_from_document()`

- **List-based mailing** (`mailing_on_mailing_list = True`): calls `contact_list_ids._update_subscription_from_email(email, opt_out=True)` — per-list opt-out.
- **Document-based mailing** (e.g., `crm.lead`, `sale.order`): adds email to global `mail.blacklist` — full suppression.

### Tracking

| Route | Auth | Purpose |
|-------|------|---------|
| `/mail/track/{id}/{token}/blank.gif` | public | Fires tracking pixel, marks trace as opened, returns 1x1 transparent GIF |
| `/r/{code}/m/{trace_id}` | public | Redirects shortened URL, records click, marks as opened/clicked |

### View in Browser

`/mailing/{id}/view` — Renders mailing HTML (QWeb post-process disabled), replaces placeholder URLs with recipient-specific ones, wraps in `mailing_view` template.

### Portal

| Route | Auth | Purpose |
|-------|------|---------|
| `/mailing/my` | user | Personal subscription management page |
| `/mailing/blocklist/add` | public | Add email to blacklist via portal |
| `/mailing/blocklist/remove` | public | Remove email from blacklist |
| `/mailing/report/unsubscribe` | public | Opt out of KPI statistics emails |

### Placeholders

| Route | Auth | Purpose |
|-------|------|---------|
| `/unsubscribe_from_list` | public | Placeholder; redirects to `/mailing/my` (no language prefix, `sitemap=False`) |
| `/view` | user | Placeholder example for "view in browser" link in builder |
| `/mailing/mobile/preview` | user | Mobile preview iframe content |

---

## Cron Jobs

| Cron | Model | Trigger | Purpose |
|------|-------|---------|---------|
| `ir_cron_mass_mailing_queue` | `mailing.mailing` | On `action_put_in_queue()` and at `schedule_date` | Picks up queued mailings and sends them |
| `ir_cron_mass_mailing_ab_testing` | `utm.campaign` | At `ab_testing_schedule_datetime` | Evaluates A/B test and sends winner |
| `@api.autovacuum _gc_canceled_mail_mail` | `mail.mail` | Automatic | Deletes old canceled mail records |

---

## Security

### Access Control

`mass_mailing.group_mass_mailing_user` — primary group for all operations:
- Full CRUD: `mailing.contact`, `mailing.list`, `mailing.subscription`, `mailing.mailing`, `mailing.trace`, `mailing.filter`, `mailing.subscription.optout`, `utm.campaign`, `utm.source`, `utm.medium`, `mail.blacklist`, `link.tracker`
- Read-only: `ir.model`, `ir.mail_server`
- `mailing.mailing` also writable by `base.group_system`

`mass_mailing.group_mass_mailing_campaign` — required for campaign-level features; checked via `is_mailing_campaign_activated` computed field.

### Record Rules

`properties_base_definition_rule_mailing_user` — restricts access to `properties_base_definition` records for mailing users to only those whose `properties_field_id` points to `mailing.contact`'s properties field.

### Unsubscribe Security

HMAC-SHA512 tokens based on `database.secret` prevent unsubscribe URL forgery. Tokens validated using constant-time comparison (`consteq` from `odoo.tools`).

### GDPR / Bounce Auto-Blacklist

- Per-list opt-out vs global blocklist: same email can be opted-out on one list but active on another.
- Auto-blacklist: 5+ bounces in 13 weeks with bounces at least 1 week apart. Prevents permanent suppression from temporary server errors.

---

## Performance Implications

- **Statistics queries**: `_compute_statistics()` and `_compute_clicks_ratio()` use raw SQL to avoid N+1 and ORM overhead with potentially millions of traces.
- **Batch processing**: `_process_mass_mailing_queue()` commits after each mailing to avoid long transactions.
- **Failed mail retry**: batched unlink of 1000 at a time to prevent memory exhaustion.
- **Inline image deduplication**: by checksum — avoids creating duplicate attachment records for the same image used multiple times.
- **A/B recipient selection**: `random.sample()` on Python side — acceptable since domain evaluation already loads contacts into memory.
- **Link shortener**: runs at render time; each shortened link creates a `link.tracker` record. Click counting uses SQL join on `mailing_trace_id`.
- **Statistics KPI emails**: only sent if `mass_mailing.mass_mailing_reports` config param is True, and only for mailings sent within the last 5 days.

---

## Edge Cases

- **Same email, different lists**: A contact can be opted-out on List A but opted-in on List B. `_mailing_get_opt_out_list()` uses symmetric set difference to handle this correctly.
- **Blacklist supersedes opt-out**: `is_blacklisted` is checked during recipient resolution; blacklisted contacts never receive mail regardless of opt-out state.
- **Duplicate send prevention**: `_get_seen_list()` queries `mailing_trace` for emails already sent in the same campaign (A/B) or same mailing.
- **Bounce auto-blacklist timing**: bounces must be at least 1 week apart to avoid suppressing from temporary mail server errors.
- **`body_arch` vs `body_html`**: `body_arch` = raw builder output (editable); `body_html` = QWeb rendered (used for send). `_convert_inline_images_to_urls()` applied to both on save.
- **`mailing_domain` stored as string**: stored as `repr(domain)`; `_parse_mailing_domain()` uses `literal_eval()`. Invalid domains → `[('id', 'in', [])]`.
- **`keep_archives=False`**: `mail.mail` deleted after send; `mailing.trace` preserved.
- **Reply-to `update` mode**: for document-based mailings, `auto_delete_keep_log=True` keeps the sent email so replies can be followed in document chatter.
- **Portal subscription merge conflict**: if both `list_ids` and `subscription_ids` are provided when creating a contact, `UserError` is raised.
- **Test traces**: `is_test_trace=True` traces are excluded from statistics computations.
- **Empty body guard**: `is_body_empty` prevents sending mailings with no content.
- **Overdue queue**: `next_departure_is_past` flags mailings stuck in `in_queue` past their scheduled time; `action_reload()` button (currently empty) is available for manual intervention UX.
