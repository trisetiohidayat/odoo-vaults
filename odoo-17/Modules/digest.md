---
tags: [odoo, odoo17, module, digest, kpi, reporting, email]
research_depth: medium
---

# Digest Module — Deep Reference

**Source:** `addons/digest/models/`

## Overview

Automated periodic KPI emails sent to users. Digest emails summarize business metrics (sales, messages, connected users, etc.) over configurable timeframes (daily, weekly, monthly, quarterly). Each user can subscribe to one or more digest configurations and receives HTML-formatted emails with inline KPIs and margin comparisons against previous periods.

## Key Models

### digest.digest — Digest Configuration

**File:** `digest.py`

The main model. One record = one digest report configuration.

#### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required, translate) | Digest name displayed in emails |
| `user_ids` | Many2many res.users | Recipients — non-share users only |
| `periodicity` | Selection | `daily`, `weekly`, `monthly`, `quarterly` |
| `next_run_date` | Date | When the cron will next trigger sending |
| `company_id` | Many2one res.company | Scope for KPI queries |
| `state` | Selection | `activated` or `deactivated` |
| `is_subscribed` | Boolean (compute) | Is current user a recipient? |
| `available_fields` | Char (compute) | Comma-separated list of active KPI fields |

#### KPI Boolean Fields

These are the "enable/disable" toggles for each metric. When `True`, the corresponding `_value` field is computed and included in the email.

| Field | Default KPI |
|-------|-----------|
| `kpi_res_users_connected` | Users who logged in |
| `kpi_mail_message_total` | Messages / emails sent |

Enterprise modules extend this with `kpi_sale_order_total`, `kpi_account_invoice_total`, `kpi_helpdesk_tickets`, etc. Third-party modules can add KPIs by defining a boolean field starting with `kpi_` and a corresponding `_value` compute.

#### KPI Value Fields

| Field | Type | Description |
|-------|------|-------------|
| `kpi_res_users_connected_value` | Integer (compute) | Count of connected users in period |
| `kpi_mail_message_total_value` | Integer (compute) | Count of messages (comment/email/email_outgoing) |

## Cron Scheduling

### `_cron_send_digest_email`

Run by `ir.cron` on active digests where `next_run_date <= today`. Sends emails to all recipients. On `MailDeliveryException`, logs and reschedules — no email is lost.

### `_action_send` — Main Send Loop

```python
# 1. Check daily logs → slowdown digests with inactive users
to_slowdown = self._check_daily_logs()

# 2. For each digest, for each user:
for digest in self:
    for user in digest.user_ids:
        digest.with_context(
            digest_slowdown=digest in to_slowdown,
            lang=user.lang
        )._action_send_to_user(user)
    # Slowdown: demote periodicity (daily→weekly→monthly→quarterly)
    digest.periodicity = digest._get_next_periodicity()[0]
    digest.next_run_date = digest._get_next_run_date()
```

### Slowdown Logic (`_check_daily_logs`)

If a digest's recipients have not logged in within the period, Odoo automatically demotes the periodicity. For example, a daily digest with no logins for 2 days becomes weekly. Prevents sending "stale" emails to inactive users.

## Email Rendering

### `_action_send_to_user`

1. Generate unsubscribe token via `_get_unsubscribe_token(user_id)` — HMAC of `(digest.id, user_id)` with the digest's secret key
2. Render template `digest.digest_mail_main` (QWeb view, `engine='qweb_view'`) with context:
   - `kpi_data` — computed KPI values for 3 timeframes
   - `tips` — random digest tips (consumed so each user sees each tip once)
   - `preferences` — unsubscribe link, periodicity demotion warning, "customize this email" link
3. Encapsulate in `digest.digest_mail_layout` (email wrapper with logo, company info)
4. Create `mail.mail` record (sudo, outgoing state)
5. Set `List-Unsubscribe` header for one-click unsubscribe

### Templates

- `digest.digest_mail_main` — main email body with KPI table and tips
- `digest.digest_mail_layout` — outer wrapper with company logo and footer

### Unsubscribe

One-click unsubscribe via `/digest/{id}/unsubscribe_oneclik?token=...&user_id=...` — validates HMAC token and removes user from `user_ids`.

## KPI Computation Architecture

### Timeframes

`_compute_timeframes(company)` returns 3 periods for comparison:

| Column | Current Period | Previous Period |
|--------|---------------|-----------------|
| Col 1 | Last 24 hours | 24–48 hours ago |
| Col 2 | Last 7 days | 7–14 days ago |
| Col 3 | Last 30 days | 30–60 days ago |

### `_compute_kpis`

For each enabled KPI boolean field, computes the current and previous period values, calculates the margin percentage, and formats:
```python
kpis = [
    {
        'kpi_name': 'kpi_mail_message_total',
        'kpi_fullname': 'Messages Sent',  # translated field description
        'kpi_action': False,  # optional action URL
        'kpi_col1': {'value': '47', 'margin': 23.5, 'col_subtitle': 'Last 24 hours'},
        'kpi_col2': {'value': '312', 'margin': -5.2, 'col_subtitle': 'Last 7 Days'},
        'kpi_col3': {'value': '1,847', 'margin': 12.1, 'col_subtitle': 'Last 30 Days'},
    },
    ...
]
```

Errors (access denied on a model) are silently skipped per-user — ensures the email still sends even if a user lacks access to a KPI's source model.

### Margin Calculation

```python
margin = (current - previous) / previous * 100
# 0.0 if either value is 0
# Rounded to 2 decimal places
```

### `_calculate_company_based_kpi` — Generic KPI Pattern

```python
def _calculate_company_based_kpi(self, model, digest_kpi_field,
                                  date_field='create_date',
                                  additional_domain=None, sum_field=None):
```

Generic method used by `kpi_res_users_connected_value`. Searches the target model grouped by `company_id` within the date range, summing or counting records. Accepts:
- `model` — model name with `company_id` field
- `digest_kpi_field` — field to write the result to
- `date_field` — field to filter on
- `additional_domain` — extra filter criteria
- `sum_field` — if set, sum that field; otherwise count records

### Digest Tips (`digest.tip`)

**File:** `digest_tip.py`

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Display order |
| `name` | Char (translate) | Tip title |
| `user_ids` | Many2many res.users | Users who already received this tip |
| `tip_description` | Html (translate) | Tip content (rendered as QWeb template) |
| `group_id` | Many2one res.groups | Show tip only to this group (default: `base.group_user`) |

Tips are randomly selected, marked as consumed (added to `user_ids`), and rendered using `mail.render.mixin._render_template(engine='qweb')`.

## Extensibility

Third-party modules can add KPIs to a digest by:
1. Adding a boolean field `x_kpi_my_metric` on `digest.digest`
2. Adding a computed `_value` field `x_kpi_my_metric_value`
3. Optionally extending `_compute_kpis_actions` to link the KPI to an Odoo action

## See Also

- [[Modules/mail]] — email sending infrastructure
- [[Modules/account]] — financial KPI extensions
- [[Modules/sale]] — sales KPI extensions