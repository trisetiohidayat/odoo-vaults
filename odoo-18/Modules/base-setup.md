---
Module: base_setup
Version: Odoo 18
Type: Core Extension
Tags: #odoo18, #orm, #modules, #configuration
---

# base_setup

Initial setup wizard for company configuration: `res.config.settings` extensions, user creation helpers, KPI provider abstraction, and session info injection.

## Module Overview

- **Primary models:** `res.config.settings`, `res.users`
- **Abstract model:** `kpi.provider`
- **HTTP extension:** `ir.http` (session_info override)
- **Dependency:** `base`

---

## Models

### `res.config.settings` (extension)

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_id = fields.Many2one('res.company', string='Company',
        required=True, default=lambda self: self.env.company)
    is_root_company = fields.Boolean(compute='_compute_is_root_company')
    user_default_rights = fields.Boolean(
        "Default Access Rights",
        config_parameter='base_setup.default_user_rights')
    module_base_import = fields.Boolean("Allow users to import data from CSV/XLS/XLSX/ODS files")
    module_google_calendar = fields.Boolean(
        string='Allow the users to synchronize their calendar with Google Calendar')
    module_microsoft_calendar = fields.Boolean(
        string='Allow the users to synchronize their calendar with Outlook Calendar')
    module_mail_plugin = fields.Boolean(
        string='Allow integration with the mail plugins')
    module_auth_oauth = fields.Boolean("Use external authentication providers (OAuth)")
    module_auth_ldap = fields.Boolean("LDAP Authentication")
    module_account_inter_company_rules = fields.Boolean("Manage Inter Company")
    module_voip = fields.Boolean("VoIP")
    module_web_unsplash = fields.Boolean("Unsplash Image Library")
    module_sms = fields.Boolean("SMS")
    module_partner_autocomplete = fields.Boolean("Partner Autocomplete")
    module_base_geolocalize = fields.Boolean("GeoLocalize")
    module_google_recaptcha = fields.Boolean("reCAPTCHA")
    module_website_cf_turnstile = fields.Boolean("Cloudflare Turnstile")
    report_footer = fields.Html(related="company_id.report_footer", ...)
    group_multi_currency = fields.Boolean(...)
    external_report_layout_id = fields.Many2one(related="company_id.external_report_layout_id")
    show_effect = fields.Boolean(string="Show Effect",
        config_parameter='base_setup.show_effect')
    company_count = fields.Integer('Number of Companies',
        compute="_compute_company_count")
    active_user_count = fields.Integer('Number of Active Users',
        compute="_compute_active_user_count")
    language_count = fields.Integer('Number of Languages',
        compute="_compute_language_count")
    company_name = fields.Char(related="company_id.display_name")
    company_informations = fields.Text(compute="_compute_company_informations")
    company_country_code = fields.Char(related="company_id.country_id.code", readonly=True)
    profiling_enabled_until = fields.Datetime("Profiling enabled until",
        config_parameter='base.profiling_enabled_until')
    module_product_images = fields.Boolean("Get product pictures using barcode")
```

**Key fields:**

| Field | Type | Description |
|-------|------|-------------|
| `company_id` | Many2one `res.company` | Current company |
| `is_root_company` | Boolean | True if company has no parent |
| `user_default_rights` | Boolean | Config param — reduces default groups to "Employee" only |
| `module_*` | Boolean | Module install flags (trigger immediate install on save) |
| `report_footer` | Html | Related from company, editable |
| `company_informations` | Text | Computed formatted company address string |
| `profiling_enabled_until` | Datetime | Enables profiling via config parameter |

**Computed fields:**

| Field | Compute | Description |
|-------|---------|-------------|
| `_compute_company_count` | `company_id` | Total number of companies (sudo) |
| `_compute_active_user_count` | `company_id` | Non-share users (sudo) |
| `_compute_language_count` | `company_id` | Installed language count |
| `_compute_company_informations` | `company_id` | Formatted address block with VAT |
| `_compute_is_root_company` | `company_id` | True if `parent_id` is False |

**Action buttons:**

- `open_company()` — Opens `res.company` form for current company
- `open_default_user()` — Opens the default user template (`base.default_user` record). Raises `UserError` if template not found.
- `edit_external_header()` — Opens the external report layout view
- `_prepare_report_view_action(template)` — Utility returning `ir.ui.view` form action

---

### `res.users` (extension)

```python
class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def web_create_users(self, emails):
        """ Create or reactivate users from email addresses. """
```

**`web_create_users(emails)`**

Parses email addresses, reactivates any existing deactivated users, and creates new users from new emails. Requires `email_normalized` field (installed with Discuss). Uses `signup_valid=True` context.

**`_default_groups()`**

```python
def _default_groups(self):
    """Default groups for employees.
    If base_setup.default_user_rights is set, only the "Employee" group is used"""
    if not str2bool(self.env['ir.config_parameter'].sudo().get_param("base_setup.default_user_rights"), default=False):
        employee_group = self.env.ref("base.group_user")
        return employee_group | employee_group.trans_implied_ids
    return super()._default_groups()
```

When `base_setup.default_user_rights` is **False** (default), all implied groups of "Employee" are granted (standard Odoo behavior). When **True**, only the base "Employee" group is assigned, giving new users minimal rights.

**`_apply_groups_to_existing_employees()`**

```python
def _apply_groups_to_existing_employees(self):
    if not str2bool(... "base_setup.default_user_rights", ...):
        return False  # skip default behavior
    return super()._apply_groups_to_existing_employees()
```

When `default_user_rights` is True, prevents Odoo from automatically applying new default groups to existing users.

---

### `kpi.provider` (abstract)

```python
class KpiProvider(models.AbstractModel):
    _name = 'kpi.provider'
    _description = 'KPI Provider'
```

Provides a hook for other modules (e.g., `l10n_account_report` in account_reports) to contribute KPIs to the database dashboard.

**`get_kpi_summary()`**

```python
@api.model
def get_kpi_summary(self):
    """
    Override to return a list of dicts with keys:
    - id: unique identifier
    - type: 'integer' or 'return_status'
    - name: translated display name
    - value: numeric value (type=integer) or status string (type=return_status)
      Status values: 'late', 'longterm', 'to_do', 'to_submit', 'done'
    """
    return []
```

Called by the database module to retrieve dashboard KPI data. Other modules override this to append their KPIs.

---

## `ir.http` Extension

```python
class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        result = super(IrHttp, self).session_info()
        if self.env.user._is_internal():
            result['show_effect'] = bool(
                self.env['ir.config_parameter'].sudo().get_param('base_setup.show_effect'))
        return result
```

Injects `show_effect` (confetti/snow animation toggle) into the session info sent to the web client. Only visible to internal users.

---

## L4 Notes

- **`base_setup.default_user_rights`:** This config parameter is a master switch that fundamentally changes Odoo's default security posture for new users. When enabled, users get only the "Employee" group and must be explicitly granted additional rights. This is intended for organizations that want to start with minimal permissions.
- **`show_effect`:** Controls the confetti/snow animations on successful actions. Stored as `ir.config_parameter` (`base_setup.show_effect`), not a field on the company. Injected into `session_info` so the web client can conditionally load the animation scripts.
- **Transient model:** `res.config.settings` is a `TransientModel`. Records are not persisted long-term; they are used to capture configuration changes and apply them via `default_get` / `create` / `write` patterns when the user clicks "Save".
- **Module install flags:** Fields named `module_<module_name>` with `Boolean` type are special — when set to `True` and saved, Odoo's configuration system automatically installs the corresponding module. This is handled by the `res.config.settings` base logic.
- **`kpi.provider`:** This is an abstract model. Only concrete models that mix it in (via `_register_hook` in consuming modules) actually return data. The pattern is used by localization/accounting modules for tax filing status indicators.
