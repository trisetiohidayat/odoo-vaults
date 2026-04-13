---
type: module
module: digest
tags: [odoo, odoo19, digest, kpi, reporting, email]
---

# KPI Digests (digest)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `digest` |
| **Version** | 1.1 |
| **Category** | Marketing |
| **Dependencies** | `mail`, `portal`, `resource` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

`digest` is Odoo's periodic KPI email reporting system. It sends scheduled email digests to users summarizing key performance indicators (KPIs) over configurable time periods, along with tips to encourage feature adoption. It is a generic framework where each installed app can contribute its own KPI fields.

> **Location**: `~/odoo/odoo19/odoo/addons/digest/`

---

## Architecture Overview

The digest system works by:

1. **Cron job** (`_cron_send_digest_email`) runs daily and selects all activated digests whose `next_run_date <= today`
2. For each digest, **`_action_send`** iterates over each subscribed user and calls **`_action_send_to_user`**
3. Each user email is rendered with **`_compute_kpis`**, **`_compute_tips`**, and **`_compute_preferences`**
4. The rendered HTML email is encapsulated in a layout and sent as `mail.mail` with List-Unsubscribe headers

```
ir_cron (_cron_send_digest_email)
  └── search([('next_run_date', '<=', today), ('state', '=', 'activated')])
      └── for each digest: action_send()
          └── _action_send()
              └── for each user: _action_send_to_user()
                  ├── _compute_kpis(user.company_id, user)    # KPI data
                  ├── _compute_tips(user.company_id, user)     # Tips
                  └── _compute_preferences(user.company_id, user)  # Preferences
              └── Update next_run_date
```

---

## Models

### digest.digest

The main KPI digest definition.

```python
class DigestDigest(models.Model):
    _name = 'digest.digest'
    _description = 'Digest'
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Digest name (required, translatable) |
| `user_ids` | Many2many `res.users` | Recipients (domain: `share = False`) |
| `periodicity` | Selection | `daily`, `weekly`, `monthly`, `quarterly` |
| `next_run_date` | Date | Next mailing date |
| `company_id` | Many2one `res.company` | Company scope |
| `currency_id` | Many2one (related) | Currency from company |
| `state` | Selection | `activated` / `deactivated` |
| `kpi_res_users_connected` | Boolean | Toggle for "Connected Users" KPI |
| `kpi_res_users_connected_value` | Integer | Computed value for connected users |
| `kpi_mail_message_total` | Boolean | Toggle for "Messages Sent" KPI |
| `kpi_mail_message_total_value` | Integer | Computed value for messages |
| `available_fields` | Char | Computed: list of enabled KPI value fields |
| `is_subscribed` | Boolean | Computed: is current user subscribed |

**KPI Boolean + Value Pair Pattern:**

Every KPI follows a boolean-value pair pattern:

```python
# Boolean: user toggles this in the UI to include/exclude the KPI
kpi_mail_message_total = fields.Boolean('Messages Sent')

# Value: automatically computed when the digest is rendered
kpi_mail_message_total_value = fields.Integer(
    compute='_compute_kpi_mail_message_total_value'
)
```

The `_compute_available_fields` method dynamically finds all boolean fields starting with `kpi_`, `x_kpi_`, or `x_studio_kpi_` and builds the list of corresponding `_value` fields.

**Periodicity and Next Run Date:**

```python
def _get_next_run_date(self):
    if self.periodicity == 'daily':
        delta = relativedelta(days=1)
    elif self.periodicity == 'weekly':
        delta = relativedelta(weeks=1)
    elif self.periodicity == 'monthly':
        delta = relativedelta(months=1)
    else:
        delta = relativedelta(months=3)
    return date.today() + delta
```

`_onchange_periodicity` automatically updates `next_run_date` when periodicity changes.

---

### digest.tip

Motivational tips displayed in digest emails to encourage feature adoption.

```python
class DigestTip(models.Model):
    _name = 'digest.tip'
    _description = 'Digest Tips'
    _order = 'sequence'
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Display order |
| `name` | Char | Tip name (translatable) |
| `tip_description` | Html | Tip content (translatable, no sanitize) |
| `user_ids` | Many2many `res.users` | Users who have already received this tip (for rotation) |
| `group_id` | Many2one `res.groups` | Only show to users in this group (default: `base.group_user`) |

**Tip Rotation Logic:**

Tips are selected so each user sees a new tip each time. The query excludes tips the current user has already received:

```python
def _compute_tips(self, company, user, tips_count=1, consumed=True):
    tips = self.env['digest.tip'].search([
        ('user_ids', '!=', user.id),  # User hasn't received this tip yet
        '|',
        ('group_id', 'in', user.all_group_ids.ids),
        ('group_id', '=', False)
    ], limit=tips_count)
    # ... render tip descriptions
    if consumed:
        tips.user_ids += user  # Mark tips as consumed for this user
    return tip_descriptions
```

---

### res.users Extension

`res.users` is extended to auto-subscribe new employees to the default digest.

```python
class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        default_digest_emails = self.env['ir.config_parameter'].sudo().get_param('digest.default_digest_emails')
        default_digest_id = self.env['ir.config_parameter'].sudo().get_param('digest.default_digest_id')
        users_to_subscribe = users.filtered_domain([('share', '=', False)])
        if default_digest_emails and default_digest_id and users_to_subscribe:
            digest = self.env['digest.digest'].sudo().browse(int(default_digest_id)).exists()
            digest.user_ids |= users_to_subscribe
        return users
```

New internal users (non-share) are automatically subscribed to the default digest if enabled in settings.

---

### res.config.settings Extension

Allows global configuration of default digest for new users:

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    digest_emails = fields.Boolean(string="Digest Emails", config_parameter='digest.default_digest_emails')
    digest_id = fields.Many2one('digest.digest', string='Digest Email', config_parameter='digest.default_digest_id')
```

---

## KPI Computation System

### KPI Field Naming Convention

Modules that contribute KPIs to the digest system must follow this naming convention:

```python
# In the digest model (or any inherited model):
kpi_module_kpi_name = fields.Boolean('Display Name')           # Toggle
kpi_module_kpi_name_value = fields.Integer(                   # Computed value
    compute='_compute_kpi_module_kpi_name_value'
)
```

For example, `helpdesk` adds `kpi_helpdesk_ticket_closed_value`.

The `kpi_res_id_field` concept: When a KPI needs to display a link to the relevant records (e.g., a link to "View Leads" in CRM), the digest system uses `kpi_action` in the KPI data dict. This is populated by `_compute_kpis_actions()`, which returns a dict mapping field names to XML IDs of window actions. The email template then renders these as clickable links: `/odoo/action-{action}`. The `kpi_res_id_field` pattern is not a formal Odoo field attribute — it is an informal convention where the KPI's `_value` field may reference a `res_id` or record context that the action links to.

### The `_get_kpi_compute_parameters` Method

All KPI compute methods receive their date range from context:

```python
def _get_kpi_compute_parameters(self):
    companies = self.company_id
    if any(not digest.company_id for digest in self):
        companies |= self.env.company
    return (
        fields.Datetime.to_string(self.env.context.get('start_datetime')),
        fields.Datetime.to_string(self.env.context.get('end_datetime')),
        companies,
    )
```

The context keys `start_datetime` and `end_datetime` are set by `_compute_timeframes` when iterating over time periods.

### Generic KPI Computation: `_calculate_company_based_kpi`

```python
def _calculate_company_based_kpi(self, model, digest_kpi_field,
                                  date_field='create_date',
                                  additional_domain=None, sum_field=None):
    """Generic method that computes the KPI on a given model.

    :param model: Model on which we will compute the KPI
        This model must have a "company_id" field
    :param digest_kpi_field: Field name on which we will write the KPI
    :param date_field: Field used for the date range
    :param additional_domain: Additional domain
    :param sum_field: Field to sum to obtain the KPI,
        if None it will count the number of records
    """
    start, end, companies = self._get_kpi_compute_parameters()

    base_domain = Domain([
        ('company_id', 'in', companies.ids),
        (date_field, '>=', start),
        (date_field, '<', end),
    ])

    if additional_domain:
        base_domain &= Domain(additional_domain)

    values = self.env[model]._read_group(
        domain=base_domain,
        groupby=['company_id'],
        aggregates=[f'{sum_field}:sum'] if sum_field else ['__count'],
    )

    values_per_company = {company.id: agg for company, agg in values}
    for digest in self:
        company = digest.company_id or self.env.company
        digest[digest_kpi_field] = values_per_company.get(company.id, 0)
```

This is the base pattern used by `_compute_kpi_res_users_connected_value` and can be used by any module to add KPIs.

### KPI Rendering in Emails

The `_compute_kpis` method renders data for each time period (Last 24 hours, Last 7 Days, Last 30 Days) and computes margin vs. the previous period:

```python
def _compute_kpis(self, company, user):
    # For each timeframe, compute KPIs with context set to that period's date range
    for col_index, (tf_name, tf) in enumerate(self._compute_timeframes(company)):
        digest = self.with_context(
            start_datetime=tf[0][0], end_datetime=tf[0][1]
        ).with_user(user).with_company(company)
        previous_digest = self.with_context(
            start_datetime=tf[1][0], end_datetime=tf[1][1]
        ).with_user(user).with_company(company)
        # KPI values are computed within each context -> naturally scoped to the period
        compute_value = digest[field_name + '_value']
        previous_value = previous_digest[field_name + '_value']
        margin = self._get_margin_value(compute_value, previous_value)
```

> **L4 / AccessError handling:** The `_compute_kpis` method wraps each KPI value read in a `try/except AccessError`. If a user lacks read access to a model contributing a KPI, that specific KPI is silently excluded from the rendered email (`invalid_fields` list). This prevents a single access restriction from breaking the entire digest for a user.

---

## Timeframes

`_compute_timeframes` generates three time periods with timezone awareness:

```python
def _compute_timeframes(self, company):
    start_datetime = datetime.utcnow()
    tz_name = company.resource_calendar_id.tz
    if tz_name:
        start_datetime = pytz.timezone(tz_name).localize(start_datetime)
    return [
        ('Last 24 hours', (
            (start_datetime + relativedelta(days=-1), start_datetime),
            (start_datetime + relativedelta(days=-2), start_datetime + relativedelta(days=-1))
        )),
        ('Last 7 Days', (
            (start_datetime + relativedelta(weeks=-1), start_datetime),
            (start_datetime + relativedelta(weeks=-2), start_datetime + relativedelta(weeks=-1))
        )),
        ('Last 30 Days', (
            (start_datetime + relativedelta(months=-1), start_datetime),
            (start_datetime + relativedelta(months=-2), start_datetime + relativedelta(months=-1))
        ))
    ]
```

Each timeframe tuple contains `(current_period, previous_period)` for margin computation. The company's timezone (`resource_calendar_id.tz`) is used to localize the start time, meaning the "last 24 hours" window is anchored to the company's local midnight, not UTC.

---

## Auto-Slowdown (Tone-Down) System

The digest system automatically reduces email frequency if recipients do not log in:

```python
def _check_daily_logs(self):
    """Check user logs and slowdown digest emails based on recipients being away."""
    today = datetime.now().replace(microsecond=0)
    to_slowdown = self.env['digest.digest']
    for digest in self:
        if digest.periodicity == 'daily':     limit_dt = today - relativedelta(days=2)
        elif digest.periodicity == 'weekly':  limit_dt = today - relativedelta(days=7)
        elif digest.periodicity == 'monthly': limit_dt = today - relativedelta(months=1)
        elif digest.periodicity == 'quarterly': limit_dt = today - relativedelta(months=3)
        users_logs = self.env['res.users.log'].sudo().search_count([
            ('create_uid', 'in', digest.user_ids.ids),
            ('create_date', '>=', limit_dt)
        ])
        if not users_logs:
            to_slowdown += digest
    return to_slowdown
```

The periodicity escalation chain:

```
daily -> weekly -> monthly -> quarterly
```

After three consecutive periods with no user login, a daily digest degrades to quarterly. The digest email includes a preference message informing the user of the automatic change.

---

## Email Rendering and Sending

### Rendering Pipeline

```python
def _action_send_to_user(self, user, tips_count=1, consume_tips=True):
    unsubscribe_token = self._get_unsubscribe_token(user.id)

    rendered_body = self.env['mail.render.mixin']._render_template(
        'digest.digest_mail_main',
        'digest.digest',
        self.ids,
        engine='qweb_view',
        add_context={
            'title': self.name,
            'top_button_url': self.get_base_url(),
            'company': user.company_id,
            'user': user,
            'unsubscribe_token': unsubscribe_token,
            'kpi_data': self._compute_kpis(user.company_id, user),
            'tips': self._compute_tips(user.company_id, user, tips_count=tips_count, consumed=consume_tips),
            'preferences': self._compute_preferences(user.company_id, user),
        },
        options={'preserve_comments': True, 'post_process': True},
    )[self.id]

    full_mail = self.env['mail.render.mixin']._render_encapsulate(
        'digest.digest_mail_layout',
        rendered_body,
        add_context={'company': user.company_id, 'user': user},
    )
```

Key details:
- `engine='qweb_view'` uses QWeb templates from XML files (not inline template strings)
- `post_process=True` runs HTML sanitization and formatting
- The layout template (`digest_mail_layout`) wraps the main body in the digest branding with responsive CSS
- The email is sent with `List-Unsubscribe` and `List-Unsubscribe-Post` headers for RFC 8058 compliance
- The `mail.mail` record is created in `outgoing` state; the standard mail queue cron handles actual SMTP delivery

### Email Template Architecture

The email is assembled from two QWeb templates:

1. **`digest.digest_mail_main`** — the main body containing:
   - Header with company name, connect button, date
   - Tips section (if any)
   - KPI rows (one row per enabled KPI, three columns: Last 24h / 7 Days / 30 Days)
   - Preferences section
   - Footer with unsubscribe links

2. **`digest.digest_mail_layout`** — the HTML shell with responsive CSS, applied via `_render_encapsulate()`. It receives the rendered body via the `body` variable.

3. **`digest.digest_tool_kpi`** — a reusable sub-template called per KPI cell that renders the value, subtitle, and margin indicator (green for positive, red for negative).

The `List-Unsubscribe` header is critical for email deliverability and CAN-SPAM compliance. The one-click unsubscribe (RFC 8058) uses a POST-only route to prevent accidental unsubscribes from link scanners.

### Unsubscribe Token Security

Tokens are HMAC-based to prevent URL forgery:

```python
def _get_unsubscribe_token(self, user_id):
    return tools.hmac(self.env(su=True), 'digest-unsubscribe', (self.id, user_id))
```

The HMAC secret is stored server-side via `ir.config_parameter`. The token is verified in the portal controller using constant-time comparison (`consteq`).

---

## Cron Configuration

The digest cron is defined in `data/ir_cron_data.xml`:

```xml
<record id="ir_cron_digest_scheduler_action" model="ir.cron">
    <field name="name">Digest Emails</field>
    <field name="model_id" ref="model_digest_digest"/>
    <field name="state">code</field>
    <field name="code">model._cron_send_digest_email()</field>
    <field name="user_id" ref="base.user_root"/>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
    <field name="nextcall" eval="(DateTime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')"/>
</record>
```

The cron runs daily (once per day), scheduled as `base.user_root` (superuser). Since `next_run_date` is checked in `_cron_send_digest_email`, digests with longer periodicity simply skip most days. The initial `nextcall` is set to 2 hours from installation to avoid stampede on server restart.

---

## Portal Controllers

The portal controller handles unsubscribe flows with security:

```python
class DigestController(Controller):

    @route('/digest/<int:digest_id>/unsubscribe_oneclick',
           type='http', website=True, auth='public',
           methods=['POST'], csrf=False)
    def digest_unsubscribe_oneclick(self, digest_id, token=None, user_id=None):
        # One-click unsubscribe (RFC 8058 compliant)
        self.digest_unsubscribe(digest_id, token=token, user_id=user_id)
        return Response(status=200)

    @route('/digest/<int:digest_id>/unsubscribe',
           type='http', website=True, auth='public', methods=['GET', 'POST'])
    def digest_unsubscribe(self, digest_id, token=None, user_id=None, one_click=None):
        # Three unsubscribe modes:
        # 1. Token + user_id (secure, from email link)
        # 2. No token, logged-in user (from preferences page)
        # 3. One-click POST (RFC 8058)
        if one_click and int(one_click) and request.httprequest.method != "POST":
            raise Forbidden()
        # Verify HMAC token before unsubscribing...
```

**CSRF is disabled** on unsubscribe routes because they are called by Mail User Agents (MUAs) with unpredictable sessions.

---

## Security: Which KPIs Are Visible to Whom

### Access Control on KPI Values

The `_compute_kpis` method has a critical `AccessError` guard:

```python
try:
    compute_value = digest[field_name + '_value']
    previous_value = previous_digest[field_name + '_value']
except AccessError:  # no access rights -> skip that KPI
    invalid_fields.append(field_name)
    continue
```

This means:
- If a user lacks read access to the model a KPI queries (e.g., `helpdesk.ticket`), that KPI is silently dropped from their digest email.
- The digest configuration (which boolean KPIs are enabled) is shared across all users — if an admin enables a helpdesk KPI, users without helpdesk access simply do not see it in their email.
- There is **no per-user KPI visibility configuration** built into the digest itself.

### ACL Requirements for Receiving Digests

- Users must have `share = False` (internal users) to be added as digest recipients.
- The `action_subscribe` / `action_unsubscribe` methods check `_is_internal()` before allowing self-subscription changes.
- Portal users (`share = True`) cannot be added to digest recipients at all.

### Unsubscribe Security

- The unsubscribe URL contains a HMAC token scoped to `(digest_id, user_id)`.
- The token is verified with `consteq` (constant-time comparison) to prevent timing attacks.
- A logged-in user without a token can unsubscribe via the preferences page.
- One-click unsubscribe requires POST method only, preventing accidental/automated unsubscriptions from email link scanners.

---

## Failure Modes

### `_cron_send_digest_email` Failures

```python
@api.model
def _cron_send_digest_email(self):
    digests = self.search([('next_run_date', '<=', fields.Date.today()), ('state', '=', 'activated')])
    for digest in digests:
        try:
            digest.action_send()
        except MailDeliveryException as e:
            _logger.warning(
                'MailDeliveryException while sending digest %d. Digest is now scheduled for next cron update.',
                digest.id
            )
```

The cron wraps each digest's `action_send()` in a try/except. Only `MailDeliveryException` is caught and logged — other exceptions (e.g., KPI computation errors, database errors) will abort the entire cron run, leaving remaining digests unsent for that day.

The digest's `next_run_date` is **not updated** when `MailDeliveryException` occurs, meaning the digest will be retried on the next cron run.

### `action_send` / `_action_send_to_user` Failures

- **SMTP configuration error:** `MailDeliveryException` bubbles up to the cron, which catches it and retries next day.
- **Missing email on user:** If `user.email_formatted` is empty, `email_to` in the `mail.mail` record will be empty/invalid. The `mail.mail` creation may succeed but delivery will fail.
- **Template rendering error:** If a KPI compute method raises an exception, the entire email rendering fails and the digest is not sent.
- **AccessError on KPI:** Silently caught per-KPI (see above), the digest continues with remaining KPIs.

---

## Performance Considerations

### Company-Based KPI Queries

KPI values are computed per-company using `_read_group` with `groupby=['company_id']`. The result is a dictionary mapping company IDs to aggregate values, then each digest picks its own company's value. This avoids N queries for multi-company setups.

### Slowdown Detection

The `_check_daily_logs` query uses `search_count` with a limit on user IDs, making it efficient even for large user lists.

### Template Caching

The `post_process=True` flag in `_render_template` applies HTML sanitization and formatting. This is computationally expensive for large emails but ensures consistent output.

### Mail Queue

Digest emails are created as `mail.mail` records in `outgoing` state, letting the standard mail queue cron handle actual delivery. This decouples digest generation from SMTP delivery.

### KPI Computation Per User

`_compute_kpis` is called **per user per digest**, not per digest. If a digest has 100 recipients, KPI values are recomputed 100 times. However, since the KPI compute methods use context-based date ranges and `_calculate_company_based_kpi` with `_read_group` (which is generally efficient), the main cost is the repeated template rendering rather than database queries.

---

## Extending Digest with Custom KPIs

Modules contribute KPIs by adding boolean + computed value pairs to `digest.digest`:

```python
# In your module's model
class DigestDigest(models.Model):
    _inherit = 'digest.digest'

    kpi_my_kpi = fields.Boolean('My Custom KPI')

    @api.depends('company_id')
    def _compute_kpi_my_kpi_value(self):
        for digest in self:
            start, end, companies = digest._get_kpi_compute_parameters()
            digest.kpi_my_kpi_value = digest.env['my.model'].search_count([
                ('company_id', 'in', companies.ids),
                ('date_field', '>=', start),
                ('date_field', '<', end),
            ])
```

The compute method must use `_get_kpi_compute_parameters()` to get `start`, `end`, and `companies` from context. This is critical because `_compute_timeframes` sets the context before calling each KPI compute.

For KPIs that link to a report or view, override `_compute_kpis_actions`:

```python
def _compute_kpis_actions(self, company, user):
    actions = super()._compute_kpis_actions(company, user)
    actions['kpi_my_kpi'] = 'my_module.my_action'
    return actions
```

---

## Version Change: Odoo 18 to 19

### New in Odoo 19

- **`_action_unsubscribe_users` / `_action_subscribe_users`:** Made `sudo()` the default internal computation to bypass ACL performance overhead during bulk subscription management.
- **`DigestController` unsubscribe routes:** The `one_click` parameter and RFC 8058 compliance were enhanced in this period. The POST-only enforcement on one-click unsubscribe prevents spam filters from triggering accidental unsubscribes.
- **Tip rotation with `consume_tips` parameter:** The `consume_tips` flag in `_action_send_to_user` allows sending tips without marking them as consumed (for preview/testing scenarios).
- **HMAC-based unsubscribe tokens:** Secure token generation using `tools.hmac()` with `consteq` verification instead of any simpler token scheme.
- **`_format_currency_amount` method:** Added for consistent currency formatting in KPI displays.

### Persistent Design Decisions

- The cron always runs as `base.user_root` (superuser) to ensure digest emails can be sent regardless of recipient user permissions on the digest configuration.
- The digest system intentionally does **not** store per-user KPI preferences — all subscribed users receive the same set of enabled KPIs. This is a design trade-off between flexibility and simplicity.
- KPIs are computed in the context of the **recipient user** (`with_user(user)`), meaning access rights are applied per-recipient. A user who cannot read a particular model will simply not see that KPI's value.

---

## See Also

- [Modules/mail](modules/mail.md) - Email functionality
- [Core/API](core/api.md) - Cron jobs and scheduled actions
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) - State machine patterns
- [Modules/CRM](modules/crm.md) - CRM KPIs (extends digest)
- [Modules/Sale](modules/sale.md) - Sales KPIs (extends digest)
