---
tags: [odoo, odoo17, module, mass_mailing]
---

# Mass Mailing Module

**Source:** `addons/mass_mailing/models/`

## Overview

Email marketing campaign engine. Allows creating, scheduling, and tracking bulk email campaigns with mailing lists, A/B testing, and blacklisting support.

## Key Models

| Model | File | Description |
|-------|------|-------------|
| `mailing.mailing` | `mailing.py` | Email campaign definition and sending |
| `mailing.contact` | `mailing_contact.py` | Individual contact in a mailing list |
| `mailing.list` | `mailing_list.py` | Mailing list containing contacts |
| `mailing.trace` | `mailing_trace.py` | Delivery/open/click tracking records |
| `mailing.subscription` | `mailing_subscription.py` | Join table linking contacts to lists |
| `mailing.filter` | `mailing_filter.py` | Saved domain filters |
| `utm.campaign` | `utm_campaign.py` | UTM campaign tracking |

## mailing.mailing

Core model for email campaigns. Inherits from `mail.thread`, `mail.activity.mixin`, `mail.render.mixin`, and `utm.source.mixin`.

### Key Fields

- `subject` — Email subject line (required)
- `preview` — Email preview text shown in inbox
- `body_arch` / `body_html` — HTML email body (QWeb rendered)
- `mailing_type` — Currently only `mail` (SMS moved to `mass_mailing_sms`)
- `contact_list_ids` — Many2many target mailing lists
- `mailing_model_id` / `mailing_domain` — Alternative: target any model with domain filter
- `mailing_filter_id` — Saved favorite filter
- `campaign_id` — UTM campaign association
- `medium_id` — UTM medium (email)
- `reply_to_mode` — `update` (thread to document) or `new` (specific email)
- `reply_to` — Reply-to email address
- `schedule_type` — `now` or `scheduled`
- `schedule_date` — Scheduled send datetime
- `state` — `draft` / `in_queue` / `sending` / `done`
- `ab_testing_enabled` — Enable A/B testing split
- `ab_testing_pc` — Percentage of recipients for A/B test (default 10)
- `mail_server_id` — Outgoing mail server override
- `attachment_ids` — Email attachments
- `keep_archives` — Whether to keep mail.mail records after sending

### Lifecycle / Actions

- `action_launch` — Put mailing in queue (draft -> in_queue)
- `action_cancel` — Cancel a mailing
- `action_retry` — Retry failed mailings
- `action_duplicate` — Clone a mailing
- `_process_mass_mailing` — Cron job that processes queue and sends emails

## mailing.contact

Lightweight contact record separate from `res.partner` to avoid bloating partner table with bulk mailing contacts.

### Key Fields

- `name`, `email` — Basic contact info
- `company_name` — Company name (separate from partner)
- `title_id` — Partner title (Mr/Ms/etc)
- `country_id` — Country
- `tag_ids` — Partner tags
- `list_ids` — Many2many to `mailing.list`
- `subscription_ids` — One2many subscription records (with opt-out flag)
- `opt_out` — Computed from subscription, search-enabled per-list context

### Key Methods

- `add_to_list(name, list_id)` — Static method to add contact by name+email
- `_message_get_default_recipients` — Returns `email_to` (no partner_ids)

## mailing.list

A mailing list groups `mailing.contact` records.

### Key Fields

- `name` — List name
- `active` — Archive toggle (prevents archiving if used in active campaign)
- `contact_ids` — Many2many to `mailing.contact`
- `is_public` — Allow recipients to manage their subscription preferences
- `contact_count` / `contact_count_email` / `contact_count_opt_out` / `contact_count_blacklisted` — Statistics computed via SQL

### Key Methods

- `action_send_mailing` — Open mailing form with this list pre-selected
- `action_view_contacts` — Jump to contacts in this list
- `action_merge(src_lists, archive)` — SQL-based merge of multiple lists, deduplicates by email
- `_update_subscription_from_email(email, opt_out, force_message)` — Opt-in/out via subscription management page

## See Also

- [Modules/mail](mail.md) — Messaging foundation used by mass_mailing
- [Modules/portal](portal.md) — Portal for subscription management
