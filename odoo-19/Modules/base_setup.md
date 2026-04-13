---
uid: base_setup
title: Initial Setup Tools
type: module
category: Hidden
version: 1.0
created: 2026-04-06
modified: 2026-04-11
dependencies:
  - base
  - web
author: Odoo S.A.
license: LGPL-3
summary: Settings dashboard, KPI provider abstraction, user onboarding, HTTP session effect control, and partner kanban enhancement for the general settings screen
auto_install: true
installable: true
tags:
  - odoo
  - odoo19
  - configuration
  - settings
  - res_config_settings
  - kpi_provider
  - web_create_users
  - ir_http
  - session_info
---

# Base Setup Module (`base_setup`)

## Overview

The `base_setup` module is a **hidden-category** Odoo 19 module that owns the general Settings dashboard. It is auto-installed on every new database and serves as the central hub for initial configuration: company details, user management, language setup, integration toggles, and performance tools.

It extends `res.config.settings` (a `TransientModel`), adds an HTTP session overlay for UI effects, provides an abstract KPI provider interface used by other modules, and patches the partner kanban view to surface contact categories.

**Module path:** `odoo/addons/base_setup/`

---

## Module Metadata

| Property | Value |
|---|---|
| Version | 1.0 |
| Category | Hidden |
| Depends | `base`, `web` |
| Auto-install | `True` (installed automatically on new databases) |
| Installable | `True` |
| License | LGPL-3 |
| Author | Odoo S.A. |

**Data files loaded:**
- `data/base_setup_data.xml` — creates the `ir.config_parameter` key `base_setup.show_effect` with default `True`
- `views/res_config_settings_views.xml` — settings form view with priority 0, inheriting `base.res_config_settings_view_form`
- `views/res_partner_views.xml` — partner kanban kanban extension adding `category_id` widget

**Static assets:**
- `web.assets_backend`: all files under `static/src/views/**/*` (Vue/web component assets for the settings UI)

---

## Models

### `res.config.settings` — Extended

**File:** `models/res_config_settings.py`
**Inheritance:** `_inherit = 'res.config.settings'` (from `base` module)
**Model type:** `TransientModel` (never persisted permanently; auto-cleaned by the ORM)

This is the core settings wizard. It does not store data directly — configuration is written either to `res.company` fields (via `related=`), to `ir.config_parameter` (via `config_parameter=`), or triggers module installation via `module_*` boolean fields.

#### All Fields (Exact Signatures)

```python
# ── Company context ──────────────────────────────────────────────────────────
company_id = fields.Many2one(
    'res.company',
    string='Company',
    required=True,
    default=lambda self: self.env.company,
)
# Stores the current company for all related/dependent fields.
# Required=True ensures every settings record is scoped to a company.
# default=lambda self: self.env.company → auto-set to the user's current company.

is_root_company = fields.Boolean(
    compute='_compute_is_root_company',
)
# True when company_id.parent_id is falsy (no parent company above it).
# Used to conditionally show/hide parent-company-only features.

company_name = fields.Char(
    related="company_id.display_name",
    string="Company Name",
)
# Read-only mirror of the company's display_name.
# Stored in: res.company.display_name

company_informations = fields.Text(
    compute="_compute_company_informations",
    string="Company Informations",
)
# Human-readable block: street, street2, zip, city, state, country, VAT.
# Recomputed whenever company_id changes.

company_country_code = fields.Char(
    related="company_id.country_id.code",
    string="Company Country Code",
    readonly=True,
)
# ISO country code (e.g., "US", "FR"). Comes from res.country.code.

company_country_group_codes = fields.Json(
    related="company_id.country_id.country_group_codes",
)
# List of regional group codes the country's region belongs to (e.g. ["eu"]).

# ── Stats (read-only, recomputed) ────────────────────────────────────────────
company_count = fields.Integer(
    'Number of Companies',
    compute="_compute_company_count",
)
# Total count of all records in res.company (sudo'd, no domain filter).
# Used in the UI to show the "Manage Companies" button with singular/plural.

active_user_count = fields.Integer(
    'Number of Active Users',
    compute="_compute_active_user_count",
)
# Count of res.users where active=True AND share=False (internal users only).
# Portal/external users are excluded. Sudo'd for superuser access.

language_count = fields.Integer(
    'Number of Languages',
    compute="_compute_language_count",
)
# len(lang.get_installed()) — count of languages with state 'installed'.

# ── Module toggles (install/uninstall modules on save) ────────────────────────
module_base_import = fields.Boolean(
    string="Allow users to import data from CSV/XLS/XLSX/ODS files"
)
# Installs/uninstalls base_import module.
# Controls access to Data Import feature (Settings → Permissions → Import & Export).
# Hidden behind base.group_no_one (developer mode only in UI).

module_google_calendar = fields.Boolean(
    string='Allow the users to synchronize their calendar with Google Calendar'
)
# Installs google_calendar module. Adds Google auth credentials fields.

module_microsoft_calendar = fields.Boolean(
    string='Allow the users to synchronize their calendar with Outlook Calendar'
)
# Installs microsoft_calendar module. Adds OAuth2 credentials for Outlook.

module_mail_plugin = fields.Boolean(
    string='Allow integration with the mail plugins'
)
# Installs mail_plugin module. Enables the Outlook/Gmail plugin sidebars.

module_auth_oauth = fields.Boolean(
    string="Use external authentication providers (OAuth)"
)
# Installs auth_oauth. Adds the OAuth providers list (Google, GitHub, etc.)
# in Settings → Integrations → OAuth Authentication.
# Saved value triggers a deferred warning shown after save: "Save and come back here..."

module_auth_ldap = fields.Boolean(
    string="LDAP Authentication"
)
# Installs auth_ldap. Adds LDAP server configuration under Integrations.
# Requires server hostname, port, admin DN, and password.

module_account_inter_company_rules = fields.Boolean(
    string="Manage Inter Company"
)
# Installs account_inter_company_rules. Enables automatic SO→PO creation
# between your own companies. Only shown when base.group_multi_company applies.

module_voip = fields.Boolean(
    string="Phone"
)
# Installs the VoIP module stack (module_voip + voip_* related modules).

module_web_unsplash = fields.Boolean(
    string="Unsplash Image Library"
)
# Installs web_unsplash. Activates Unsplash image picker in the media library.

module_sms = fields.Boolean(
    string="SMS"
)
# Installs sms module. Does NOT auto-create SMS gateway config —
# user must return to Settings after save to configure the provider.

module_partner_autocomplete = fields.Boolean(
    string="Partner Autocomplete"
)
# Installs partner_autocomplete. Enables IAP-based company data enrichment on partners.

module_base_geolocalize = fields.Boolean(
    string="GeoLocalize"
)
# Installs base_geolocalize. Adds geo-tagging button on partner and stock location forms.

module_google_recaptcha = fields.Boolean(
    string="reCAPTCHA"
)
# Installs google_recaptcha. Adds site key / secret key config fields (website forms).

module_website_cf_turnstile = fields.Boolean(
    string="Cloudflare Turnstile"
)
# Installs website_cf_turnstile. Adds Turnstile site/secret key config (alternative to reCAPTCHA).

module_google_address_autocomplete = fields.Boolean(
    string="Google Address Autocomplete"
)
# Installs google_address_autocomplete. Adds Google Places API key field.

# ── Group implication toggles ────────────────────────────────────────────────
group_multi_currency = fields.Boolean(
    string='Multi-Currencies',
    implied_group='base.group_multi_currency',
    help="Allows to work in a multi currency environment",
)
# Implies the base.group_multi_currency group to the current user when enabled.
# Unlike module_* fields, this does not install a module — it grants/revokes a group.
# Also propagates to the default user template (all future users inherit the group).
# UI location: Settings → Permissions → Default Access Rights area.

# ── Company-scoped config (related to res.company) ──────────────────────────
report_footer = fields.Html(
    related="company_id.report_footer",
    string='Custom Report Footer',
    help="Footer text displayed at the bottom of all reports.",
    readonly=False,
)
# Mirrors res.company.report_footer. Supports multi-company: each company has its own footer.
# Setting this writes directly to res.company.report_footer.

external_report_layout_id = fields.Many2one(
    related="company_id.external_report_layout_id",
)
# QWeb report layout selection (e.g., "Modern", "Boxed", "Professional").
# Mirrors res.company.external_report_layout_id.

# ── Global config parameters (ir.config_parameter) ──────────────────────────
show_effect = fields.Boolean(
    string="Show Effect",
    config_parameter='base_setup.show_effect',
)
# Controls the "fun feedback" effects (confetti, animations) in the Odoo UI.
# Value stored in ir.config_parameter (key: 'base_setup.show_effect').
# Loaded into the HTTP session via ir.http.session_info() for internal users.

profiling_enabled_until = fields.Datetime(
    string="Profiling enabled until",
    config_parameter='base.profiling_enabled_until',
)
# When set, activates Odoo profiling for the current user until this datetime.
# Hidden behind base.group_no_one (developer mode).
# Performance impact: profiling adds significant overhead; must auto-expire.
```

#### Computed Methods

**`_compute_is_root_company`** — `@api.depends('company_id')`
```python
record.is_root_company = not record.company_id.parent_id
```
Returns `True` when the company has no parent. Controls visibility of certain multi-company features.

**`_compute_company_count`** — `@api.depends('company_id')`
```python
company_count = self.env['res.company'].sudo().search_count([])
```
Counts ALL companies in the system regardless of current user's company_ids. Sudo'd to bypass record rules. The `company_id` dependency is a formality — the value is always the same system-wide.

**`_compute_active_user_count`** — `@api.depends('company_id')`
```python
active_user_count = self.env['res.users'].sudo().search_count([
    ('share', '=', False)
])
```
Counts all internal users (`share=False`). Excludes portal/external users. Sudo'd. The `company_id` dependency is a trigger stub — the count is system-wide, not company-scoped. This is a known Odoo design quirk: the `depends` forces re-computation when the user switches company in the settings UI.

**`_compute_language_count`** — `@api.depends('company_id')`
```python
language_count = len(self.env['res.lang'].get_installed())
```
Calls `lang.get_installed()` which returns list of installed `res.lang` records.

**`_compute_company_informations`** — `@api.depends('company_id')`
Builds a `\n`-joined address string:
```
{street}
{street2}
{zip}[ - {city}]
{state}
{country}
VAT: {vat}
```
Uses `country_id.vat_label` (country-specific VAT label, e.g. "ABN" in Australia) if present, otherwise falls back to `_('VAT')`. This method deliberately avoids `record.company_id` iteration in the loop body for performance — all records share the same `company_id` in normal usage.

#### Action Methods

**`open_company()`** — button handler
Opens `res.company` form for the current `env.company.id` in the same window (`target: current`). Used from the company information block.

**`open_new_user_default_groups()`** — button handler
1. Looks up `base.default_user_group` via `env.ref()` (noupdate XML id)
2. If not found, creates it programmatically: `res.groups` + corresponding `ir.model.data` entry
3. Opens the group's form in a modal (`target: new`)
4. Any group implied by this default group is automatically granted to new users

**`edit_external_header()`** — button handler
Used from "Edit Layout" button in Document Layout section. Calls `_prepare_report_view_action()` which does a `self.env.ref(template)` and returns a window action opening `ir.ui.view` for the QWeb layout template's header.

**`execute()`** — inherited from parent `res.config.settings`
Not overridden in base_setup, but inherited from the base model's implementation:
- Reads all field values from the wizard record
- For `module_*` fields set to `True`: triggers `ir.module.module.button_immediate_install()` for the named module
- For `group_*` fields: updates `res.groups` implied_ids
- For `related=` fields: writes directly to the target `res.company` record
- For `config_parameter=` fields: calls `ir.config_parameter.set_param()`
- Then invalidates the wizard record (transient → deleted)

---

### `kpi.provider` — Abstract Model

**File:** `models/kpi_provider.py`
**Inheritance:** `_name = 'kpi.provider'` (own name, not extending a base)
**Model type:** `AbstractModel` — meant to be mixed into other models

This is a **mixin/extension point** for other modules to contribute KPI cards to the Odoo database dashboard (the apps/remote databases list view in the Odoo.com context, and potentially the local home dashboard).

#### Method Signature

```python
@api.model
def get_kpi_summary(self):
    """
    Returns: list[dict]
    Each dict has keys:
        - id: str  — unique identifier for this KPI
        - type: 'integer' | 'return_status'
        - name: str  — translated display name
        - value: int | str  — numeric or status string
    """
    return []
```

**Status strings for `type='return_status'`:**
| Value | Meaning |
|---|---|
| `late` | At least one return is past its deadline |
| `longterm` | Nearest incomplete return deadline > 3 months away |
| `to_do` | Nearest incomplete return deadline < 3 months away |
| `to_submit` | Return is ready but still needs action |
| `done` | All foreseeable returns are completed |

**Override pattern:** Other modules (e.g., `l10n_*` country-specific modules) override this method. The method is called by the databases module controller to populate dashboard data sent to the frontend.

**Important:** The docstring explicitly states this is called by "the databases module" — this refers to the `databases` module in Odoo's online/enterprise infrastructure (apps.odoo.com dashboard), not a standard on-premise module.

---

### `ir.http` — Extended

**File:** `models/ir_http.py`
**Inheritance:** `_inherit = 'ir.http'` (abstract model, HTTP routing/kernel)

#### Method

**`session_info(self)`** — overrides the parent `ir.http` session_info
```python
def session_info(self):
    result = super().session_info()   # include base fields: user_id, partner_id, company_id, etc.
    if self.env.user._is_internal():  # internal user (not portal/share)
        result['show_effect'] = bool(
            self.env['ir.config_parameter'].sudo().get_param('base_setup.show_effect')
        )
    return result
```

**L4 Details:**
- Uses `sudo()` on `ir.config_parameter` because config params are system-level, not user-scoped
- Only injects `show_effect` for internal users — portal/share users see no effects regardless of the setting
- The `_is_internal()` check is equivalent to `share == False`
- `show_effect` is passed to the frontend JS session object; the web client reads it and enables/disables CSS animation classes (e.g., `o_notification_effect`)
- **Security:** No access rights issue here — `ir.config_parameter` is public read for all authenticated users

---

### `res.users` — Extended

**File:** `models/res_users.py`
**Inheritance:** `_inherit = 'res.users'`

#### Method

**`web_create_users(self, emails)`** — `@api.model`
```python
@api.model
def web_create_users(self, emails):
    emails_normalized = [tools.mail.parse_contact_from_email(email)[1] for email in emails]
    if 'email_normalized' not in self._fields:
        raise UserError(...)  # requires Discuss/mail module

    # Step 1: Reactivate deactivated users matching any provided email
    deactivated_users = self.with_context(active_test=False).search([
        ('active', '=', False),
        '|',
            ('login', 'in', emails + emails_normalized),
            ('email_normalized', 'in', emails_normalized)
    ])
    for user in deactivated_users:
        user.active = True
    done = deactivated_users.mapped('email_normalized')

    # Step 2: Create new users for remaining emails
    new_emails = set(emails) - set(deactivated_users.mapped('email'))
    for email in new_emails:
        name, email_normalized = tools.mail.parse_from_email(email)
        if email_normalized in done:
            continue
        default_values = {
            'login': email_normalized,
            'name': name or email_normalized,
            'email': email_normalized,
            'active': True
        }
        user = self.with_context(signup_valid=True).create(default_values)

    return True
```

**L4 Details:**
- Called from the frontend "Invite Users" widget on the settings dashboard
- `tools.mail.parse_contact_from_email()` extracts the normalized email from an RFC-822 address string
- The `email_normalized` field check guards against running on a database without the `mail` module installed (the field is added by `mail`; `base` has no `email_normalized`)
- `with_context(active_test=False)` is critical — without it, `search()` would exclude inactive users by default
- `signup_valid=True` context bypasses the email signup token generation (users created from admin don't need to confirm via email)
- Returns `True` (no recordset returned) — the caller handles UI feedback
- **Performance:** Loop-and-create rather than batch `create()` — each user triggers `res.partner` creation (via `_create_portal_user` signal or standard `res.users` creation). On bulk invites (e.g., 50 emails), this generates 50 partner records in sequence.

---

## Controllers

### `base_setup.controllers.main.BaseSetup`

**File:** `controllers/main.py`

#### Route: `/base_setup/data`

```python
@http.route('/base_setup/data', type='jsonrpc', auth='user')
def base_setup_data(self, **kw):
    if not request.env.user.has_group('base.group_erp_manager'):
        raise AccessError(_("Access Denied"))
    ...
```

**Authorization:** Requires `base.group_erp_manager` (Administrator access level). Raises `AccessError` for non-managers.

**Data returned:**
```python
{
    'active_users': int,           # count of active internal users
    'pending_count': int,          # users who never logged in (no res_users_log entry)
    'pending_users': list,         # up to 10 (id, login) tuples of pending users
    'action_pending_users': dict,  # action dict to open pending users list view
}
```

**SQL queries:**
```sql
-- active_users: active AND share=False
SELECT count(*) FROM res_users WHERE active=true AND share=false;

-- pending_users: active internal users with NO res_users_log record
-- (never logged in after account creation)
SELECT count(u.*)
  FROM res_users u
 WHERE active=true
   AND share=false
   AND NOT EXISTS(SELECT 1 FROM res_users_log WHERE create_uid=u.id);

-- pending_users list (LIMIT 10, ordered by id DESC)
SELECT id, login
  FROM res_users u
 WHERE active=true
   AND share=false
   AND NOT EXISTS(SELECT 1 FROM res_users_log WHERE create_uid=u.id)
 ORDER BY id DESC
 LIMIT 10;
```

**L4 Notes:**
- Direct SQL used (not ORM) because `res_users_log` is performance-critical and bypasses ORM overhead
- The `pending_count` is used by the UI to show a "pending users" alert badge on the Settings dashboard
- `action_pending_users` is constructed via `res.users.browse(...)._action_show()` which generates a client-side action dict

#### Route: `/base_setup/demo_active`

```python
@http.route('/base_setup/demo_active', type='jsonrpc', auth='user')
def base_setup_is_demo(self, **kwargs):
    demo_active = bool(
        request.env['ir.module.module'].search_count([('demo', '=', True)])
    )
    return demo_active
```

**Purpose:** Checks if demo data is loaded in the database. Called from the settings dashboard to determine whether to show the "Load Demo Data" button. The button is only shown if `demo_active == False` (i.e., no module currently has `demo=True`).

---

## XML Views

### `res_config_settings_view_form` (priority 0, inherits `base.res_config_settings_view_form`)

This view is loaded at priority 0 so it appears **before** most other inherited views, giving `base_setup` a chance to set the base layout before other modules append their settings blocks.

**App sections and settings blocks:**

| App / Block | Setting IDs | Description |
|---|---|---|
| `app[name=general_settings]` | — | Top-level container; contains all main settings |
| `block[title=Users]` | `invite_users_setting`, `active_user_setting` | User invite widget + active user count |
| `block[title=Languages]` | `languages_setting` | Installed language count + add/manage buttons |
| `block[title=Companies]` | `company_details_settings`, `companies_setting`, `document_layout_setting`, `inter_company` | Company name/info, count, report layout, inter-company rules |
| `block[title=Contacts]` | `sms`, `partner_autocomplete` | SMS and partner autocomplete module toggles |
| `block[title=Permissions]` | `access_rights`, API Keys, `allow_import`, `feedback_motivate_setting` | Default access rights, API key management, import toggle, show_effect |
| `block[title=Progressive Web App]` | `pwa_settings` | Web app name field |
| `block[title=Integrations]` | `mail_plugin`, `module_auth_oauth`, `module_auth_ldap`, `unsplash`, `base_geolocalize`, `recaptcha`, `cf-turnstile`, `google_address_autocomplete` | All integration toggles |
| `block[title=Performance]` | `profiling_enabled_until` | Profiling toggle (developer only) |
| `block[title=About]` | `res_config_edition` widget | Odoo edition/version info |

**Key UI patterns:**
- `<setting company_dependent="1">` — field value is scoped to the current company
- `<widget name='res_config_invite_users'/>` — custom JS widget posting to `/base_setup/data`
- `<widget name='res_config_dev_tool'/>` — developer tools (technical features)
- `<widget name='res_config_edition'/>` — shows current Odoo edition
- `documentation="/applications/..."` attribute — links to online Odoo documentation
- `groups="base.group_no_one"` — restricts UI element to debug/developer mode

### `res_partner_kanban_view`

Inherits `base.res_partner_kanban_view` and adds the `category_id` field as a `many2many_tags` widget in the kanban footer (before the kanban footer close tag). This surfaces contact categories (tags) in the partner kanban view without modifying the core view structure.

---

## Data Files

### `base_setup_data.xml`

Creates a single noupdate `ir.config_parameter`:

```xml
<record model="ir.config_parameter" id="show_effect" forcecreate="False">
    <field name="key">base_setup.show_effect</field>
    <field name="value">True</field>
</record>
```

**`forcecreate="False"`**: The record is only created if it doesn't already exist. This means on first install, `show_effect=True` (effects on). On subsequent upgrades, the existing value is preserved (never reset to True). This is correct for a user preference — resetting it on upgrade would be unwanted.

---

## Security Considerations

| Area | Detail |
|---|---|
| `/base_setup/data` route | Auth: `auth='user'` + manual `base.group_erp_manager` check |
| `/base_setup/demo_active` route | Auth: `auth='user'` only — any logged-in internal user can query demo status |
| `ir.config_parameter` read in `session_info()` | Public read; no sensitive data exposed (just a boolean) |
| Module toggle fields | Require save (execute()) to trigger installation; no direct state change |
| `group_multi_currency` toggle | Affects all existing internal users via group assignment; propagates to default user template |
| `show_effect` config param | User preference; no security implications |

---

## Performance Implications

| Operation | Impact |
|---|---|
| `_compute_company_count` / `_compute_active_user_count` / `_compute_language_count` | Called on every `depends` re-trigger (company change). Each triggers a `sudo().search_count()`. The `company_id` dependency is decorative — it forces recomputation on company switch in the UI. For large user counts (10k+), the `search_count` queries can add measurable latency. |
| `company_informations` compute | Single record, minimal cost. String concatenation is O(n) where n = address field count. |
| `ir.http.session_info()` | Called on every page load (session init). One `get_param` call. Negligible cost. |
| `/base_setup/data` JSON-RPC | Two `SELECT count(*)` + two `SELECT` queries. Runs under `auth='user'`. Fine for a dashboard endpoint. |
| `web_create_users()` | O(n) loop with per-user `create()` call. Each user creation triggers `res.partner` creation (via `res.users` `partner_id` creation). For bulk invites of 50+ users, consider batching. |

---

## Odoo 18 → Odoo 19 Changes in base_setup

| Area | Change |
|---|---|
| Module toggles | Several new toggles added: `module_mail_plugin`, `module_website_cf_turnstile`, `module_google_address_autocomplete` (introduced in Odoo 18 or earlier, but present in 19) |
| `_compute_language_count` | Now uses `self.env['res.lang'].get_installed()` — language list is cached by the `lang` object |
| KPI provider | Status `return_status` type values refined; `done` status added |
| Partner kanban | `category_id` widget addition is new in this module's XML, not in base |
| `profiling_enabled_until` | Datetime field (not Char) for precise expiration |

---

## Extension Points

### Adding a module toggle to Settings

```python
# 1. In models/res_config_settings.py
module_my_module = fields.Boolean(string="Enable My Module")

# 2. In views/res_config_settings_views.xml
<setting id="my_module_setting" string="My Module"
         help="Tooltip description"
         documentation="/applications/my_app/...">
    <field name="module_my_module"/>
</setting>

# 3. On execute() (inherited from base), Odoo automatically:
#    - Detects fields named module_*
#    - Compares current field value to module.state ('installed'/'uninstalled')
#    - Calls button_immediate_install/uninstall on the matching ir.module.record
```

### Adding a group toggle

```python
group_my_group = fields.Boolean(
    string='My Group',
    implied_group='my_module.group_my_group',
    help="Description",
)
# On save: implies the group for all internal users + sets default on user template
```

### Adding a config parameter field

```python
my_setting = fields.Boolean(
    string="My Setting",
    config_parameter='my_module.my_setting_key',
)
# Stored in ir.config_parameter; survives module upgrades
```

---

## Related Documentation

- [Core/BaseModel](odoo-18/Core/BaseModel.md) — TransientModel lifecycle and auto-cleanup behavior
- [Core/Fields](odoo-18/Core/Fields.md) — `config_parameter` attribute, `related` field pattern
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — group implication, access rights defaults
- [Modules/base](odoo-18/Modules/base.md) — parent `res.config.settings` model from which base_setup inherits

---

## Tags

`#odoo` `#odoo19` `#configuration` `#settings` `#res_config_settings` `#res_users` `#kpi_provider` `#ir_http` `#session_info` `#transient_model` `#config_parameter`