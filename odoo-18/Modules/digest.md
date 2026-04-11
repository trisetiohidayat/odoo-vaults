---
Module: digest
Version: Odoo 18
Type: Integration
Tags: [digest, kpi, dashboard, reporting, email, metrics]
---

# Digest — KPI Dashboard & Email Digests

Periodic KPI email system that sends aggregated metrics to users on a configurable schedule (daily, weekly, monthly, quarterly). Digest emails display KPI values across three timeframes (last 24h, last 7 days, last 30 days) with margin comparisons, plus contextual tips from `digest.tip`.

**Module path:** `~/odoo/odoo18/odoo/addons/digest/`
**Core models:** `digest.digest`, `digest.tip`
**Extensions:** `res.users` (auto-subscribe on creation)

---

## Models

### `digest.digest` — Digest Configuration

Main digest configuration. Each record represents one digest (e.g., "Sales Manager Daily", "Management Weekly").

#### Field Inventory

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Digest name (required, translateable) |
| `user_ids` | Many2many(res.users) | Recipients; domain `share=False` (no portal) |
| `periodicity` | Selection | `daily`, `weekly`, `monthly`, `quarterly`; default `daily` |
| `next_run_date` | Date | Next scheduled send date; updated after each send |
| `company_id` | Many2one(res.company) | Operating company; defaults to `env.company` |
| `currency_id` | Many2one(res.currency) | Related from `company_id` |
| **KPI booleans** | | |
| `kpi_res_users_connected` | Boolean | Enable "Connected Users" KPI |
| `kpi_res_users_connected_value` | Integer | Computed connected users count |
| `kpi_mail_message_total` | Boolean | Enable "Messages Sent" KPI |
| `kpi_mail_message_total_value` | Integer | Computed message count |
| **State** | | |
| `state` | Selection | `activated` or `deactivated`; readonly; default `activated` |
| `is_subscribed` | Boolean | Compute: current user in `user_ids` |
| `available_fields` | Char | Compute: list of enabled `_value` field names |

**Custom KPI fields:** Any field starting with `kpi_`, `x_kpi_`, or `x_studio_kpi_` that is a boolean + has a corresponding `<field_name>_value` field is auto-detected by `_get_kpi_fields()`.

#### KPI Computation Architecture

**`_get_kpi_compute_parameters()`** — Returns tuple for all KPI compute methods:
```python
(start_datetime, end_datetime, companies)
```
- `start_datetime` / `end_datetime`: from context `start_datetime` / `end_datetime`
- `companies`: union of all `digest.company_id` records + `self.env.company` if any digest has no company

**`_compute_kpi_res_users_connected_value`** — Company-based KPI:
- Uses `_calculate_company_based_kpi('res.users', 'kpi_res_users_connected_value', date_field='login_date')`
- Counts `res.users` records with `login_date` in the time window and matching company

**`_compute_kpi_mail_message_total_value`** — Message count:
```python
self.env['mail.message'].search_count([
    ('create_date', '>=', start),
    ('create_date', '<', end),
    ('subtype_id', '=', self.env.ref('mail.mt_comment').id),
    ('message_type', 'in', ('comment', 'email', 'email_outgoing')),
])
```
Filters to actual comment/email messages only (not notes, notifications, etc.).

#### Email Composition — `_action_send_to_user(user)`

1. **Generate unsubscribe token:** `tools.hmac(env(su=True), 'digest-unsubscribe', (self.id, user_id))`
2. **Render body:** `mail.render.mixin._render_template('digest.digest_mail_main', 'digest.digest', self.ids, engine='qweb_view')` with context:
   - `title`, `top_button_label`, `top_button_url`, `company`, `user`
   - `unsubscribe_token`, `tips_count`, `formatted_date`
   - `kpi_data`: result of `_compute_kpis(user.company_id, user)`
   - `tips`: result of `_compute_tips(user.company_id, user, tips_count)`
   - `preferences`: result of `_compute_preferences(user.company_id, user)`
3. **Encapsulate:** `_render_encapsulate('digest.digest_mail_layout', ...)` wraps in layout
4. **Create mail:** `mail.mail` record with:
   - `auto_delete=True`
   - `headers['List-Unsubscribe']: <{unsub_url}>` (one-click)
   - `headers['List-Unsubscribe-Post']: List-Unsubscribe=One-Click`
   - `headers['X-Auto-Response-Suppress']: OOF`
   - `state='outgoing'`

#### `_compute_kpis(company, user)` — KPI Data Assembly

Returns list of KPI dicts with 3-column timeframes:
```python
[{
    'kpi_name': 'kpi_mail_message',
    'kpi_fullname': 'Messages',
    'kpi_action': False,
    'kpi_col1': {'value': '12', 'margin': 32.36, 'col_subtitle': 'Last 24 hours'},
    'kpi_col2': {'value': '87', 'margin': -5.2, 'col_subtitle': 'Last 7 Days'},
    'kpi_col3': {'value': '341', 'margin': 12.1, 'col_subtitle': 'Last 30 Days'},
}]
```

**Process:**
1. `_get_kpi_fields()` — detect all enabled boolean KPI fields
2. For each of 3 timeframes (`_compute_timeframes(company)`):
   - Create digest record with context: `{start_datetime, end_datetime}`
   - Evaluate each `field_name + '_value'` compute
   - Invalidate after each to force recompute for next timeframe
   - Compare to previous period via `_get_margin_value()`
   - Format: monetary fields → `format_decimalized_amount()` + currency; float → `%.2f`
3. Look up optional action via `_compute_kpis_actions()` per KPI
4. Skip KPIs that raise `AccessError` for current user

**`_compute_timeframes(company)`** — Returns 3 tuples:
- `(tf_name, ((current_start, current_end), (previous_start, previous_end)))`
- Uses company's resource calendar timezone for localization
- Last 24h: 1-day offset; Last 7 Days: 1-week offset; Last 30 Days: 1-month offset
- Previous period is always exactly one period before

#### `_compute_tips(company, user, tips_count, consumed)` — Tip Selection

```python
tips = self.env['digest.tip'].search([
    ('user_ids', '!=', user.id),  # not already seen by this user
    '|', ('group_id', 'in', user.groups_id.ids), ('group_id', '=', False)
], limit=tips_count)
```

- Tips already seen by user (`user_ids`) are excluded
- Tips without `group_id` are shown to all internal users
- Group-restricted tips only shown to members of that group
- Each tip's `tip_description` is rendered via `mail.render.mixin._render_template(..., engine='qweb', options={'post_process': True})` then sanitized
- If `consumed=True`, tips are added to `user_ids` (mark as seen for next time)

#### `_compute_preferences(company, user)` — Preference/CTA Rendering

Returns list of HTML strings for email footer:
- **Slowdown warning:** If user hasn't logged in recently, show automatic periodicity reduction notice
- **Upgrade periodicity:** Daily digest users who are ERP managers see "Prefer broader overview? Switch to weekly"
- **Customize link:** ERP managers see "Want to customize this email? Choose the metrics you care about" with link to digest form

#### Cron — `_cron_send_digest_email()`

```python
digests = self.search([('next_run_date', '<=', fields.Date.today()), ('state', '=', 'activated')])
for digest in digests:
    try:
        digest.action_send()
    except MailDeliveryException as e:
        _logger.warning(...)
```

- Runs daily (or as configured in `ir_cron_data.xml`)
- Catches `MailDeliveryException` to avoid endless retries on bad email
- `action_send()` calls `_action_send(update_periodicity=True)` which:
  - Checks user logs for slowdown candidates
  - Sends to each user with user-specific lang
  - Downgrades periodicity for inactive users
  - Updates `next_run_date`

#### `_check_daily_logs()` — Inactive User Slowdown

For each digest, based on periodicity:
- **daily:** inactive if no log in last 2 days
- **weekly:** inactive if no log in last 7 days
- **monthly:** inactive if no log in last 30 days
- **quarterly:** inactive if no log in last 90 days

Inactive digest → periodicity automatically upgraded (daily→weekly→monthly→quarterly).

#### `_calculate_company_based_kpi()` — Generic KPI Pattern

```python
def _calculate_company_based_kpi(self, model, digest_kpi_field,
                                  date_field='create_date',
                                  additional_domain=None, sum_field=None):
```

- Builds domain: `company_id in companies`, `date_field >= start`, `date_field < end`
- Optionally ANDs `additional_domain`
- Uses `_read_group` with `company_id` groupby
- Returns sum of `sum_field` if `sum_field` provided, otherwise count
- Writes result to `digest_kpi_field` per digest record (using digest's own company)

#### Actions

| Method | Description |
|--------|-------------|
| `action_subscribe()` | Current user subscribes (if internal) |
| `action_unsubscribe()` | Current user unsubscribes |
| `action_activate()` | Set `state = 'activated'` |
| `action_deactivate()` | Set `state = 'deactivated'` |
| `action_set_periodicity(p)` | Change periodicity |
| `action_send()` | Trigger send (cron or manual) |
| `action_send_manual()` | Manual send without periodicity update |

---

### `digest.tip` — Actionable Tip Templates

Tips are shown in digest emails to encourage feature adoption.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Display order |
| `name` | Char | Tip name (translateable) |
| `user_ids` | Many2many(res.users) | Users who have already received this tip |
| `tip_description` | Html | Tip content; rendered as QWeb template; `sanitize=False` |
| `group_id` | Many2one(res.groups) | Optional: only show to members of this group; default `base.group_user` |

**Rendering:** `_compute_tips()` renders each tip_description via `_render_template(engine='qweb')` with `post_process=True`, then `tools.html_sanitize()`.

**Tip lifecycle:** Tips are shown once per user (until `user_ids` updated). New users see tips relevant to their group membership.

---

### `res.users` Extension — Auto-Subscribe

```python
@api.model_create_multi
def create(self, vals_list):
    users = super().create(vals_list)
    default_digest_emails = get_param('digest.default_digest_emails')
    default_digest_id = get_param('digest.default_digest_id')
    users_to_subscribe = users.filtered_domain([('share', '=', False)])
    if default_digest_emails and default_digest_id and users_to_subscribe:
        digest = self.env['digest.digest'].sudo().browse(int(default_digest_id)).exists()
        digest.user_ids |= users_to_subscribe
    return users
```

When a new internal user is created: if `digest.default_digest_emails=True` and `digest.default_digest_id` points to a valid digest, the user is automatically subscribed.

---

### `res.config.settings` Extension

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `digest_emails` | Boolean | `config_parameter='digest.default_digest_emails'` |
| `digest_id` | Many2one(digest.digest) | `config_parameter='digest.default_digest_id'` |

Controls whether new users are auto-subscribed to a default digest.

---

## L4: Adding Custom KPIs to Digest

### Step 1: Add Boolean Toggle Field

In your model:
```python
kpi_my_module_value = fields.Integer(
    compute='_compute_kpi_my_module_value',
    compute_sudo=True,  # critical: digest renders as sudo
)
kpi_my_module = fields.Boolean(
    string='My KPI',
    config_parameter='my_module.kpi_my_module_enabled',
)
```

### Step 2: Implement Compute

**Pattern A — Company-based count:**
```python
def _compute_kpi_my_module_value(self):
    self._calculate_company_based_kpi(
        'my.model',
        'kpi_my_module_value',
        date_field='create_date',
        additional_domain=[('state', '=', 'done')],
    )
```

**Pattern B — Custom computation using timeframes:**
```python
def _compute_kpi_my_module_value(self):
    start, end, companies = self._get_kpi_compute_parameters()
    count = self.env['my.model'].search_count([
        ('company_id', 'in', companies.ids),
        ('create_date', '>=', start),
        ('create_date', '<', end),
        ('state', '=', 'done'),
    ])
    self.kpi_my_module_value = count
```

### Step 3: Integrate into Digest Form

The `config_parameter` attribute on the boolean field automatically appears in the digest configuration form under the relevant module's KPI section. The `_compute_available_fields()` method picks up any `kpi_*` boolean fields.

---

## L4: Email Template Rendering Flow

1. **Main template** (`digest.digest_mail_main`): renders per-digest data (QWeb views)
2. **Layout template** (`digest.digest_mail_layout`): wraps main content with header/footer
3. **Tip rendering**: each tip rendered independently via `engine='qweb'` (not `qweb_view`)
4. **Post-processing**: `post_process=True` triggers QWeb post-processing
5. **Unsubscribe**: one-click via `List-Unsubscribe` header pointing to `/digest/{id}/unsubscribe_oneclik?token=...&user_id=...`
6. **HMAC unsubscribe token:** Generated via `tools.hmac(sudo_env, 'digest-unsubscribe', (self.id, user_id))` for security

---

## Cron Configuration

`digest.ir_cron_digest_email` runs daily. Configured in `data/ir_cron_data.xml`:
- Calls `_cron_send_digest_email()`
- Checks `next_run_date` and `state='activated'` before sending

---

## Security

Access via `digest.group_digest_user`. Portal users excluded from `user_ids` via domain `[('share', '=', False)]`.

---

## Code Paths

| File | Description |
|------|-------------|
| `addons/digest/models/digest.py` | Core `digest.digest` model |
| `addons/digest/models/digest_tip.py` | `digest.tip` model |
| `addons/digest/models/res_users.py` | User auto-subscription on creation |
| `addons/digest/models/res_config_settings.py` | Digest settings |
| `addons/digest/data/ir_cron_data.xml` | Cron job definition |
| `addons/digest/data/digest_data.xml` | Default digest record |
| `addons/digest/data/digest_tips_data.xml` | Default tips |
| `addons/digest/views/digest_views.xml` | Form, kanban, tree views |
| `addons/digest/controllers/portal.py` | Unsubscribe endpoint |