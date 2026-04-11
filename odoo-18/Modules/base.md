---
title: base
description: Core foundational models — partners, companies, users, configuration, sequences, cron, attachments, actions, views, and more
version: Odoo 18
tags: [odoo, base, core, orm, orm-fields, security, actions, views]
source: ~/odoo/odoo18/odoo/addons/base/models/
---

# base

The `base` module is the foundation of all Odoo applications. It provides the core data models for partners/contacts, companies, users, access control, system parameters, attachments, scheduled actions, sequences, mail servers, and the action/view infrastructure used throughout the ORM.

**No addons depend on `base`** — `base` is the root dependency for everything.

---

## Model Inventory

| Model | File | Purpose |
|-------|------|---------|
| `res.partner` | `res_partner.py` | People and organizations (contacts, companies) |
| `res.partner.category` | `res_partner.py` | Partner tags/categories |
| `res.partner.title` | `res_partner.py` | Partner honorifics (Mr, Mrs, etc.) |
| `res.company` | `res_company.py` | Business entities with hierarchy |
| `res.users` | `res_users.py` | User accounts with auth/group management |
| `res.groups` | `res_users.py` | Access control groups |
| `res.users.log` | `res_users.py` | Login timestamps |
| `res.currency` | `res_currency.py` | Currencies + rates |
| `res.currency.rate` | `res_currency.py` | Per-date currency rates |
| `res.country` | `res_country.py` | Countries |
| `res.country.group` | `res_country.py` | Country groupings |
| `res.country.state` | `res_country.py` | States/provinces |
| `res.lang` | `res_lang.py` | Languages and locales |
| `res.config.settings` | `res_config.py` | Configuration wizard base |
| `ir.config.parameter` | `ir_config_parameter.py` | Global key-value store |
| `ir.model` | `ir_model.py` | Model registry/introspection |
| `ir.model.field` | `ir_model.py` | Field definitions |
| `ir.model.access` | `ir_model.py` | Per-group CRUD permissions |
| `ir.rule` | `ir_model.py` | Record-level access rules |
| `ir.module.module` | `ir_module.py` | Module registry |
| `ir.module.category` | `ir_module.py` | Application categories |
| `ir.ui.menu` | `ir_ui_menu.py` | Menu hierarchy |
| `ir.ui.view` | `ir_ui_view.py` | View/XML templates |
| `ir.actions.actions` | `ir_actions.py` | Action base |
| `ir.actions.act_window` | `ir_actions.py` | Window actions |
| `ir.actions.report` | `ir_actions_report.py` | Report actions |
| `ir.actions.server` | `ir_actions.py` | Server actions (code/loop) |
| `ir.actions.client` | `ir_actions.py` | Client actions |
| `ir.actions.act_url` | `ir_actions.py` | URL redirect actions |
| `ir.cron` | `ir_cron.py` | Scheduled jobs |
| `ir.cron.trigger` | `ir_cron.py` | Ad-hoc cron triggers |
| `ir.cron.progress` | `ir_cron.py` | Cron batch progress tracking |
| `ir.mail.server` | `ir_mail_server.py` | SMTP server configs |
| `ir.attachment` | `ir_attachment.py` | File/binary attachments |
| `ir.sequence` | `ir_sequence.py` | Number sequence generators |
| `ir.sequence.date_range` | `ir_sequence.py` | Per-period sequence ranges |
| `ir.default` | `ir_default.py` | User-defined default values |
| `ir.filter` | `ir_filters.py` | Saved filters |

---

## `res.partner`

**File:** `res_partner.py` (delegation: `_inherits={'res.partner': 'partner_id'}`)

The partner model uses **delegation inheritance** (`_inherits`) — `res.partner` stores contact-specific fields while `res.users` stores user-specific fields via the `partner_id` delegation key. A partner record is the authoritative store for name, address, email, phone, and commercial entity data.

### Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | Char | No | — | Contact name; required when `type='contact'` |
| `complete_name` | Char | — | — | Stored compute: `Parent / Name` for contacts |
| `title` | Many2one | No | — | `res.partner.title` (Mr, Mrs, Dr, ...) |
| `parent_id` | Many2one | No | — | Reference to company partner |
| `child_ids` | One2many | — | — | Contact addresses belonging to this company |
| `ref` | Char | No | — | Internal reference code |
| `lang` | Selection | No | — | ISO language code for this contact |
| `tz` | Selection | No | — | Timezone (from `pytz.all_timezones`) |
| `tz_offset` | Char | — | — | Computed current offset `+0530` |
| `user_id` | Many2one | No | — | Salesperson responsible |
| `vat` | Char | No | — | Tax ID; `/` means not subject to tax |
| `company_registry` | Char | No | — | National company ID; unique per country |
| `bank_ids` | One2many | — | — | `res.partner.bank` records |
| `website` | Char | No | — | URL |
| `comment` | Html | No | — | Internal notes |
| `category_id` | Many2many | No | — | `res.partner.category` tags |
| `active` | Boolean | — | `True` | — |
| `employee` | Boolean | — | `False` | Contact is an employee |
| `function` | Char | No | — | Job position |
| `type` | Selection | — | `'contact'` | `contact`, `invoice`, `delivery`, `other` |
| `street` | Char | No | — | — |
| `street2` | Char | No | — | — |
| `zip` | Char | No | — | — |
| `city` | Char | No | — | — |
| `state_id` | Many2one | No | — | `res.country.state` with domain `country_id` |
| `country_id` | Many2one | No | — | `res.country` |
| `country_code` | Char | — | — | Related from `country_id.code` |
| `partner_latitude` | Float | — | — | Geo latitude |
| `partner_longitude` | Float | — | — | Geo longitude |
| `email` | Char | No | — | — |
| `email_formatted` | Char | — | — | `"Name <email@domain>"` |
| `phone` | Char | No | — | — |
| `mobile` | Char | No | — | — |
| `is_company` | Boolean | — | `False` | `True` = company entity |
| `industry_id` | Many2one | No | — | `res.partner.industry` |
| `company_type` | Selection | — | — | `person` / `company`; compute+inverse |
| `company_id` | Many2one | No | — | Operating company |
| `user_ids` | One2many | — | — | Users linked to this partner |
| `partner_share` | Boolean | — | — | `True` if no internal user exists |
| `contact_address` | Char | — | — | Full formatted address |
| `commercial_partner_id` | Many2one | — | — | Root company in hierarchy (stored, recursive) |
| `commercial_company_name` | Char | — | — | Stored compute: company name from root |
| `company_name` | Char | No | — | Company name field |
| `barcode` | Char | No | — | Company-dependent, nullable index |
| `self` | Many2one | — | — | Hack: `partner.self = partner.id` for QWeb |

### SQL Constraints

```sql
CHECK( (type='contact' AND name IS NOT NULL) or (type!='contact') )
-- Contacts must have a name; address records may not
```

### Key Methods

```python
def address_get(self, adr_pref=None):
    # Resolve address: self or parent contact's address of preferred type.
    # adr_pref defaults to ['contact', 'invoice', 'delivery', 'other']
    # Used by res.company to sync address fields from partner.

def _display_address(self, address_format=None):
    # Render address using country's address_format string.
    # Fields: street, street2, city, state_code, state_name,
    #         zip, country_name, country_code, company_name
    # Used in reports and partner cards.

def _formatting_address_fields(self):
    # Returns ['street', 'street2', 'zip', 'city', 'state_id', 'country_id']

def name_create(self, name, default_code_values=None):
    # Parse "Name <email@domain>" format. Returns (id, display_name).
    # Used by many imports.

def find_or_create(self, name, assert_company_exists=True, ...):
    # Find existing partner by email/name or create new contact.

def _commercial_fields(self):
    # Returns list of field names synced up to commercial_partner_id.
    # Override in extensions to add commercial fields.

def _fields_sync(self, vals):
    # Sync commercial fields from company to contacts when parent changes.
    # Called in write() and create() for non-company partners.

def _compute_commercial_partner(self):
    # If is_company or no parent -> self; else -> parent.commercial_partner_id
```

### Commercial Partner Mechanism (L4)

The `commercial_partner_id` is the root company in the partner hierarchy. For a company partner, `commercial_partner_id = self`. For a contact, `commercial_partner_id = parent_id.commercial_partner_id`. Fields returned by `_commercial_fields()` are kept in sync on all contacts sharing the same commercial partner.

Commercial fields are used by `account.move` (and other modules) to compute `commercial_partner_id` as the partner for fiscal position and VAT number lookups. This ensures that when you invoice a contact, Odoo uses the company-level VAT and fiscal position — not the individual contact's.

### Relations

- **One2many:** `child_ids` (self-referential, inverse of `parent_id`)
- **One2many:** `bank_ids` (`res.partner.bank`)
- **One2many:** `user_ids` (`res.users` via `partner_id`)
- **Many2one:** `parent_id` (self)
- **Many2one:** `commercial_partner_id` (self, recursive stored)
- **Many2one:** `user_id` (`res.users` — salesperson)
- **Many2one:** `state_id`, `country_id`
- **Many2many:** `category_id` (`res.partner.category`)

### Performance Notes (L4)

- `commercial_partner_id` is stored with `index=True` and `recursive=True` — the ORM stores it on create and updates it whenever the partner hierarchy changes.
- `_visible_menu_ids` on `ir.ui.menu` and `_get_active_by` on `res.lang` use `@ormcache` keyed on user groups and language code respectively.
- `_compute_same_vat_partner_id` uses `sudo()` + `active_test=False` to find duplicates even for inactive partners.

---

## `res.company`

**File:** `res_company.py` | `_inherit=['format.address.mixin', 'format.vat.label.mixin']`

Multi-company support with hierarchy. Root companies delegate `currency_id` to all branches; branches cannot change delegated fields independently.

### Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | Char | Yes | — | Related to `partner_id.name` |
| `active` | Boolean | — | `True` | — |
| `sequence` | Integer | — | `10` | Ordering for company switcher |
| `parent_id` | Many2one | No | — | Parent company (hierarchy root) |
| `child_ids` | One2many | — | — | Branch companies |
| `all_child_ids` | One2many | — | — | All descendants (active_test=False) |
| `parent_path` | Char | — | — | Materialized path for hierarchy queries |
| `parent_ids` | Many2many | — | — | Computed from `parent_path` |
| `root_id` | Many2one | — | — | Topmost ancestor |
| `partner_id` | Many2one | Yes | — | Linked `res.partner` record |
| `logo` | Binary | — | — | Related from `partner_id.image_1920` |
| `logo_web` | Binary | — | — | 180px processed thumbnail |
| `uses_default_logo` | Boolean | — | — | `True` if using default logo |
| `currency_id` | Many2one | Yes | User's company currency | **Delegated to root** |
| `user_ids` | Many2many | — | — | `res.users` with access |
| `street`, `street2`, `zip`, `city` | Char | — | — | Computed from `partner_id` via `_compute_address` |
| `state_id` | Many2one | No | — | Computed/inversed via partner |
| `country_id` | Many2one | No | — | Computed/inversed via partner |
| `country_code` | Char | — | — | Related from `country_id.code` |
| `email`, `phone`, `mobile` | Char | — | — | Related from `partner_id` |
| `website`, `vat`, `company_registry` | Char | — | — | Related from `partner_id` |
| `paperformat_id` | Many2one | — | `base.paperformat_euro` | Report paper format |
| `external_report_layout_id` | Many2one | No | — | QWeb template for reports |
| `font` | Selection | — | `"Lato"` | — |
| `primary_color`, `secondary_color` | Char | — | — | — |
| `layout_background` | Selection | — | `"Blank"` | — |
| `layout_background_image` | Binary | No | — | — |
| `color` | Integer | — | — | Inverse through root's partner color |
| `uninstalled_l10n_module_ids` | Many2many | — | — | Auto-installable l10n modules by country |

### Key Methods

```python
def _get_company_root_delegated_field_names(self):
    # Returns {'currency_id'} — fields copied from root to all branches.
    # Branches cannot independently change these fields.

def _get_company_address_field_names(self):
    # Returns ['street', 'street2', 'city', 'zip', 'state_id', 'country_id']

def _compute_address(self):
    # Reads partner's contact address and syncs into company fields.

def _compute_parent_ids(self):
    # Parses parent_path to compute parent_ids + root_id.

def init(self):
    # Assigns paperformat_euro to companies missing one.
```

### SQL Constraints

```sql
unique(name)
-- Cannot have two companies with the same name
```

### L4 Notes

- **Currency delegation:** `currency_id` is delegated to root via `_get_company_root_delegated_field_names()`. `_onchange_parent_id()` copies root's `currency_id` to new branches. A `CHECK` constraint (`_check_root_delegated_fields`) prevents branch divergence.
- **`_check_active`:** Cannot archive a company that has active users whose `company_id` is that company.
- **Company hierarchy is immutable:** `write()` raises `UserError` if `parent_id` is changed after creation.
- **Address fields:** All address fields are computed from and inverse-writen to the linked `partner_id` record. The partner is created automatically if not provided.

---

## `res.users`

**File:** `res_users.py` | `_inherits={'res.partner': 'partner_id'}` | **~1300 lines**

### Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `partner_id` | Many2one | Yes | — | Delegation key; required, ondelete=restrict |
| `login` | Char | Yes | — | UNIQUE — used for authentication |
| `password` | Char | — | — | Computed/inversed; never stored plain-text |
| `new_password` | Char | — | — | Write-only; triggers auto-hash in `_set_password` |
| `signature` | Html | No | — | Email signature; stored on partner |
| `active` | Boolean | — | `True` | — |
| `action_id` | Many2one | No | — | Home action opened at login |
| `groups_id` | Many2many | — | `_default_groups()` | From `base.default_user` template |
| `log_ids` | One2many | — | — | Login history (`res.users.log`) |
| `device_ids` | One2many | — | — | `res.device` records |
| `login_date` | Datetime | — | — | Related from `log_ids.create_date` |
| `share` | Boolean | — | — | External portal user (no internal group) |
| `company_id` | Many2one | Yes | `self.env.company` | Current active company |
| `company_ids` | Many2many | — | `self.env.company.ids` | Companies user can access |
| `res_users_settings_ids` | One2many | — | — | User settings records |
| `res_users_settings_id` | Many2one | — | — | Computed current settings |
| `name` | Char | — | — | Inherited from `partner_id.name`, readonly=False |
| `email` | Char | — | — | Inherited from `partner_id.email`, readonly=False |

### Properties

```python
@property
def SELF_READABLE_FIELDS(self):
    # Fields a user can read on their own record.
    # Includes: signature, company_id, login, email, name, image_*, lang, tz,
    # groups_id, partner_id, action_id, avatar_*, share, device_ids

@property
def SELF_WRITEABLE_FIELDS(self):
    # Fields a user can write on their own record.
    # Includes: signature, action_id, company_id, email, name,
    #          image_1920, lang, tz
```

### Key Methods

```python
def _check_credentials(self, credential, env):
    # Verifies password against stored bcrypt/scrypt hash.
    # Raises AccessDenied on mismatch.
    # Used by _login() and Session._authenticate().

def _compute_password(self):
    # Reads stored encrypted password (readable in sudo only).

def _set_password(self):
    # Hashes new_password via CryptContext and writes to res_users.
    # Auto-converts legacy MD5 passwords on init().

def _check_identity(self):
    # @check_identity decorator wrapper — used by sensitive actions
    # like 2FA setup, password change, API key management.
    # Requires identity check within last 10 minutes.

def authenticate(self, db, login, password, base_location=None):
    # Classmethod. Validates login+password, returns uid or raises
    # AccessDenied. Also handles PEP 247 password upgrade on login.

def _login(self, db, login, password):
    # Returns {'uid': uid} or raises AccessDenied/UserError.
    # Records login in res.users.log.

def has_group(self, group_ext_id):
    # Returns True if user belongs to group (full XMLID check).
    # sudo() is required if called from non-admin context.

def _has_group(self, group_xmlid):
    # Core implementation. Checks transitive implied groups.

def context_get(self):
    # Returns dict with keys: tz, uid, lang, allowed companies.

def _get_company_ids(self):
    # Returns company_ids based on active company and branches.
    # Used in company-dependent domain contexts.

def _get_group_ids(self):
    # Returns ids of all groups the user belongs to (transitive).

def context_get(self):
    # Sets lang, tz from user preferences, company from company_id.

@check_identity
def action_revoke_all_devices(self):
    # Clears all sessions (res.device records).

@check_identity
def action_change_password(self, old_password, new_password):
    # Changes password after verifying old one.
```

### SQL Constraints

```sql
UNIQUE(login)
-- Cannot have duplicate logins across the system
```

### L4 Notes

- **Password auto-hash on init:** `init()` scans for passwords not matching the extended MCF format and passes them through passlib for automatic upgrade. This handles legacy MD5 hashes.
- **`_default_groups`:** Returns groups from `base.default_user` template user, enabling the "template user" pattern for standard employee group assignment.
- **`SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS`:** Implemented as `@property` (not methods) so extensions can override via `super()` chaining. These control what fields the user can access on their own record via `/web/session/change_password` or profile editing.
- **`share` compute:** `True` when user has no non-share groups (i.e., no internal access beyond portal).
- **`_check_one_user_type`:** Called via `res.groups` constraint — ensures a partner with one internal user cannot have additional users.

---

## `res.currency`

**File:** `res_currency.py`

### `res.currency`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | Char | Yes | — | ISO 4217 code (3 chars) |
| `iso_numeric` | Integer | No | — | ISO numeric code |
| `full_name` | Char | No | — | Full currency name |
| `symbol` | Char | Yes | — | Currency sign ($, EUR, ...) |
| `rate` | Float | — | — | Current rate to company currency (computed) |
| `inverse_rate` | Float | — | — | 1/rate (computed) |
| `rate_string` | Char | — | — | Display string `"1 USD = 0.92 EUR"` |
| `rate_ids` | One2many | — | — | `res.currency.rate` records |
| `rounding` | Float | — | `0.01` | Must be > 0 |
| `decimal_places` | Integer | — | — | Computed from rounding factor |
| `active` | Boolean | — | `True` | Deactivating company currency raises error |
| `position` | Selection | — | `'after'` | Symbol position |
| `date` | Date | — | — | Latest rate date (computed) |
| `currency_unit_label` | Char | No | — | Translateable unit name |
| `currency_subunit_label` | Char | No | — | Translateable subunit name |
| `is_current_company_currency` | Boolean | — | — | Computed from env.company |

### SQL Constraints

```sql
unique(name)
CHECK(rounding > 0)
```

### Key Methods

```python
def _get_rates(self, company, date):
    # Returns dict {currency_id: rate} for self + to_currency.
    # Uses subquery for latest rate per company (or global False).

def _compute_current_rate(self):
    # Computes rate using context: date, company, to_currency.
    # Falls back to 1.0 if no rate found.

def amount_to_text(self, amount):
    # Converts amount to words using num2words library.
    # Integrals + "and" + fractional parts with subunit labels.

def format(self, amount):
    # Returns locale-formatted string per language settings.

def round(self, amount):
    # Rounds using self.rounding precision.

def compare_amounts(self, amount1, amount2):
    # Returns -1/0/1 after rounding comparison.

def is_zero(self, amount):
    # True if amount rounds to zero.
```

### `res.currency.rate`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | Date | Yes | — | Rate date; unique per (currency, company) |
| `rate` | Float | Yes | `1.0` | Rate to currency of rate 1 |
| `currency_id` | Many2one | Yes | — | `res.currency` |
| `company_id` | Many2one | No | — | Company-scoped rate; False = global |

### SQL Constraints

```sql
unique(name, currency_id, company_id)
-- One rate per date per currency per company
```

---

## `res.country`

### `res.country`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | Char | Yes | — | Translateable country name |
| `code` | Char | Yes | — | 2-char ISO code, uppercased on create/write |
| `address_format` | Text | No | Country-specific | Format string for `_display_address` |
| `address_view_id` | Many2one | No | — | Custom partner address form view |
| `currency_id` | Many2one | No | — | Default currency |
| `image_url` | Char | — | — | Flag image URL (computed) |
| `phone_code` | Integer | No | — | Country calling code |
| `country_group_ids` | Many2many | No | — | `res.country.group` |
| `state_ids` | One2many | No | — | `res.country.state` |
| `name_position` | Selection | — | `'before'` | Name before/after address in reports |
| `vat_label` | Char | No | — | Custom VAT label override |
| `state_required` | Boolean | — | `False` | — |
| `zip_required` | Boolean | — | `True` | — |

### SQL Constraints

```sql
unique(name)
unique(code)
```

### `res.country.state`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `country_id` | Many2one | Yes | — | — |
| `name` | Char | Yes | — | State name |
| `code` | Char | Yes | — | State code (unique per country) |

### SQL Constraints

```sql
unique(country_id, code)
```

### Key Behaviors

- `name_search` on `res.country` prioritizes exact 2-char code matches before normal name search.
- `name_search` on `res.country.state` prioritizes code prefix matches.
- States display as `"California (US)"` — `display_name` is computed.

---

## `res.lang`

**File:** `res_lang.py`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | Char | Yes | — | Display name (e.g., "English (US)") |
| `code` | Char | Yes | — | Locale code (e.g., `en_US`) |
| `iso_code` | Char | No | — | ISO code for `.po` translation files |
| `url_code` | Char | Yes | — | URL-safe code; auto-set to shortest variant |
| `active` | Boolean | — | — | — |
| `direction` | Selection | Yes | `'ltr'` | `ltr` / `rtl` |
| `date_format` | Char | Yes | `'%m/%d/%Y'` | Python strftime format |
| `time_format` | Char | Yes | `'%H:%M:%S'` | — |
| `short_time_format` | Char | Yes | `'%H:%M'` | Without seconds |
| `week_start` | Selection | Yes | `'7'` | 1=Mon ... 7=Sun |
| `grouping` | Char | Yes | `'[]'` | JSON array: `[3,2,-1]` thousand separators |
| `decimal_point` | Char | Yes | `'.'` | — |
| `thousands_sep` | Char | — | `','` | — |
| `flag_image` | Image | No | — | Custom flag |
| `flag_image_url` | Char | — | — | Computed URL to flag image |

### Caching (L4)

```python
@tools.ormcache('field')
def _get_active_by(self, field):
    # Returns LangDataDict: {field_value: LangData} for active langs.
    # Cached by field name. LangData is a ReadonlyDict-like for fast access.
    # Invalidated on: create, write, unlink, toggle_active.
```

`toggle_active()` auto-calls `ir.module.module._update_translations()` to load `.po` files for newly activated languages.

### Key Methods

```python
def format(self, percent, value, grouping=False):
    # Locale-aware number formatting. Applies grouping and separators.

def install_lang(self):
    # Called during DB bootstrap from res_lang_data.xml.
    # Loads language from config or creates from system locale.

def _create_lang(self, lang, lang_name=None):
    # Creates language by probing system locale via locale.setlocale.
    # Maps C library format strings to Python strftime via DATETIME_FORMATS_MAP.
```

---

## `ir.config.parameter`

**File:** `ir_config_parameter.py` | **System key-value store**

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `key` | Char | Yes | — | Unique parameter key |
| `value` | Text | Yes | — | Stored value |

### Default Parameters

```python
_default_parameters = {
    "database.secret": lambda: str(uuid.uuid4()),
    "database.uuid": lambda: str(uuid.uuid1()),
    "database.create_date": fields.Datetime.now,
    "web.base.url": lambda: "http://localhost:%s" % config.get('http_port'),
    "base.login_cooldown_after": lambda: 10,
    "base.login_cooldown_duration": lambda: 60,
}
```

### Key Methods

```python
@ormcache('key')
def _get_param(self, key):
    # Bypasses ORM for perf; direct SQL SELECT.
    # Cleared on create/write/unlink via registry.clear_cache().

def get_param(self, key, default=False):
    # Public API. check_access('read') then _get_param.

def set_param(self, key, value):
    # Upsert: update existing or create new. Returns old value.

def init(self, force=False):
    # Initializes _default_parameters on new database.
    # force=True will overwrite existing values.
```

### L4 Notes

- `_get_param` is cached with `@ormcache` — high-traffic reads (e.g., `web.base.url`) are served from memory.
- Cannot delete keys that are in `_default_parameters` (protected via `@api.ondelete(at_uninstall=False)`).
- Changing a `key` that exists in `_default_parameters` raises `ValidationError`.

---

## `ir.model` + `ir.model.field`

**File:** `ir_model.py` | **Model introspection**

### `ir.model`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Human-readable model name |
| `model` | Char | Technical name (`x_model.name`) |
| `order` | Char | Default ORDER BY clause |
| `field_id` | One2many | Field definitions for this model |
| `info` | Text | Model description |
| `state` | Selection | `manual` (custom) / `base` |
| `transient` | Boolean | True for TransientModel |

### Key Methods

```python
def _instanciate(self, model_data):
    # Creates the Python class for custom models at runtime.
    # Used when loading custom model definitions from ir.model.

def _reflect_models(self):
    # Syncs ir.model registry with actual loaded models.
    # Called via registry._on_dummy_models_loaded at startup.
```

### `ir.model.field`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Field name |
| `model` | Char | Model name |
| `model_id` | Many2one | `ir.model` reference |
| `field_description` | Char | Human-readable description |
| `ttype` | Selection | Odoo field type |
| `state` | Selection | `manual` / `base` |
| `required` | Boolean | — |
| `readonly` | Boolean | — |
| `relation` | Char | For x2one fields: target model |
| `on_delete` | Char | For Many2one: CASCADE/RESTRICT/SET NULL |
| `group_ids` | Many2many | Restrict visibility to groups |
| `serialization_field_id` | Many2one | For `serialized` type |

### SQL Constraints

```sql
unique(model, name)
unique(code, company_id)  -- on res.currency.rate
check_sort_json           -- on ir.filters: sort must be JSON array
check_strictly_positive_interval -- on ir.cron
```

---

## `ir.module.module`

**File:** `ir_module.py`

### States

```python
STATES = [
    ('uninstallable', 'Not Installable'),
    ('uninstalled',   'Not Installed'),
    ('installed',    'Installed'),
    ('to upgrade',    'To Upgrade'),
    ('to remove',     'To Remove'),
    ('to install',    'To Install'),
]
```

### Key Methods

```python
def button_immediate_install(self):
    # Triggers immediate installation of module and dependencies.
    # Runs in a new registry (self.env.reset()).

def button_immediate_uninstall(self):
    # Uninstalls module, cascades to dependents.

def _check_migrations(self):
    # Detects migration scripts and sets 'to upgrade' state.

def button_install(self):
    # Sets state='to install'; actual install happens at next startup
    # or via button_immediate_install.
```

### Auto-Install Logic

Modules with `auto_install=True` and matching `country_ids` are automatically suggested when a company sets its country. `install_l10n_modules()` is triggered in `res.company` `create()` and `write()` when `country_id` changes.

---

## `ir.ui.menu`

**File:** `ir_ui_menu.py`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Menu label (translateable) |
| `parent_id` | Many2one | Parent menu (restrict delete) |
| `child_id` | One2many | Child menus |
| `sequence` | Integer | — |
| `groups_id` | Many2many | Restrict to groups |
| `action` | Reference | `ir.actions.act_window`, `ir.actions.report`, etc. |
| `complete_name` | Char | Full path (computed recursive) |
| `web_icon` | Char | Icon spec: `"module,path"` or `"fa,pink"` |
| `web_icon_data` | Binary | Base64-encoded icon image |
| `active` | Boolean | — |

### Key Methods

```python
@ormcache('frozenset(self.env.user.groups_id.ids)', 'debug')
def _visible_menu_ids(self, debug=False):
    # Returns set of visible menu IDs for current user.
    # Filters by groups, then validates action access via ir.model.access.
    # Uses ir.ui.menu.full_list context to bypass visibility filter during search.

def _filter_visible_menus(self):
    # Returns recordset of menus in self that pass _visible_menu_ids.

def search_fetch(self, domain, field_names, ...):
    # Overrides search to apply _filter_visible_menus by default.
```

### L4 Notes

- `complete_name` is computed recursively with no stored limit — `_get_full_name(level=6)` caps recursion depth.
- Menu deletion orphans child menus (sets `parent_id=False`) rather than cascading, because `ondelete=set null` is incompatible with `_parent_store`.
- The `full_list` context disables visibility filtering for the initial menu tree load.

---

## `ir.ui.view`

**File:** `ir_ui_view.py`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | View name |
| `model` | Char | Target model (for constraint checking) |
| `key` | Char | Module key for file-based views |
| `priority` | Integer | Lower = higher priority; default 16 |
| `type` | Selection | `form`, `tree`, `kanban`, `search`, `qweb`, ... |
| `inherit_id` | Many2one | Parent view to inherit from |
| `arch` | Xml | View XML as string |
| `arch_db` | Xml | Stored view XML (file-based override in arch_fs) |
| `arch_fs` | Char | Path to XML file for dev mode |
| `mode` | Selection | `primary` (standalone) / `extension` (inherits) |
| `active` | Boolean | — |
| `groups_id` | Many2many | Groups that can see this view |
| `xml_id` | Char | External ID for inherited views |

### Key Methods

```python
def _compute_arch(self):
    # In dev-xml mode, reads from arch_fs. Otherwise returns arch_db.
    # arch is the cached result of this.

def reset_arch(self, model=None):
    # Soft reset: clears arch_db and triggers recompute.
    # Hard reset (model=True): also resets from arch_fs.

def _valid_in_view(self):
    # Checks if the view tree is consistent (nodes exist, etc.).
    # Called by get_views for validation.
```

---

## `ir.actions.act_window`

**File:** `ir_actions.py`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Action label |
| `type` | Char | Always `'ir.actions.act_window'` |
| `res_model` | Char | Target model |
| `target` | Selection | `current`, `new`, `fullscreen`, `main` |
| `view_mode` | Char | CSV list: `tree,form,kanban,...` |
| `view_ids` | One2many | Ordered view IDs for this action |
| `domain` | Char | Domain as Python expression string |
| `context` | Char | Context as Python expression dict |
| `limit` | Integer | Default list view limit |
| `sequence` | Integer | — |
| `groups_id` | Many2many | Groups with access |
| `binding_model_id` | Many2one | Auto-bind to model sidebar |
| `binding_type` | Selection | `action` / `report` |
| `search_view_id` | Many2one | Associated search view |
| `filter` | Boolean | Show in sidebar automatically |

---

## `ir.actions.report`

**File:** `ir_actions_report.py`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Report name |
| `model` | Char | Target model |
| `report_type` | Selection | `qweb-pdf`, `qweb-html`, `qweb-text` |
| `report_name` | Char | QWeb report template ref (e.g., `module.report_name`) |
| `attachment_use` | Boolean | Use cached report if defined |
| `attachment` | Char | Expression for auto-saving report: `"obj.name + '.pdf'"` |
| `paperformat_id` | Many2one | Override paper format |
| `binding_model_id` | Many2one | — |
| `groups_id` | Many2many | — |

---

## `ir.cron`

**File:** `ir_cron.py`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `ir_actions_server_id` | Many2one | — | Delegate to `ir.actions.server` (required) |
| `cron_name` | Char | — | Stored compute from server action name |
| `user_id` | Many2one | `self.env.user` | Scheduler user |
| `active` | Boolean | `True` | — |
| `interval_number` | Integer | `1` | Must be > 0 |
| `interval_type` | Selection | `'months'` | `minutes`, `hours`, `days`, `weeks`, `months` |
| `nextcall` | Datetime | `fields.Datetime.now` | Next scheduled execution |
| `lastcall` | Datetime | — | Last successful execution |
| `priority` | Integer | `5` | Lower = higher priority |
| `failure_count` | Integer | `0` | Consecutive failures |
| `first_failure_date` | Datetime | — | First failure timestamp |

### SQL Constraints

```sql
CHECK(interval_number > 0)
```

### Locking (L4)

```python
FOR NO KEY UPDATE SKIP LOCKED
```
Crons use `NO KEY UPDATE` row lock (not `FOR UPDATE`) because some modules may hold `KEY SHARE` locks via FK references to cron jobs. The `NO KEY UPDATE` lock prevents concurrent processing while allowing FK `KEY SHARE` concurrent access.

### Cron Job Processing

- `_get_all_ready_jobs()` selects all crons where `nextcall <= now()` OR `id IN (SELECT cron_id FROM ir_cron_trigger WHERE call_at <= now())`.
- `_acquire_one_job()` uses `FOR NO KEY UPDATE SKIP LOCKED` to acquire a single job transactionally.
- After processing, `nextcall` is advanced by the interval. Triggers with past `call_at` are deleted.
- Partially-done crons (using `_notify_progress`) are rescheduled ASAP (`_reschedule_asap`).
- Auto-deactivation: `failure_count >= 5` AND `first_failure_date + 7 days < now` → `active = False`.

### `ir.cron.trigger`

| Field | Type | Notes |
|-------|------|-------|
| `cron_id` | Many2one | Target cron |
| `call_at` | Datetime | When to trigger (indexed) |

GC'd weekly: `WHERE call_at < now() - 1 week`.

### `ir.cron.progress`

| Field | Type | Notes |
|-------|------|-------|
| `cron_id` | Many2one | — |
| `remaining` | Integer | Records left to process |
| `done` | Integer | Records processed |
| `deactivate` | Boolean | Deactivate cron when done |
| `timed_out_counter` | Integer | Consecutive timeouts |

GC'd weekly.

---

## `ir.mail.server`

**File:** `ir_mail_server.py`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | — | Server name |
| `from_filter` | Char | — | Allowed From addresses/domains |
| `smtp_host` | Char | — | SMTP hostname |
| `smtp_port` | Integer | `25` | — |
| `smtp_authentication` | Selection | `'login'` | `login`, `certificate`, `cli` |
| `smtp_user` | Char | — | SMTP username (group: `base.group_system`) |
| `smtp_pass` | Char | — | SMTP password (group: `base.group_system`) |
| `smtp_encryption` | Selection | `'none'` | `none`, `starttls`, `ssl` |
| `smtp_ssl_certificate` | Binary | — | SSL/TLS certificate |
| `smtp_ssl_private_key` | Binary | — | SSL private key |
| `active` | Boolean | `True` | — |
| `sequence` | Integer | — | Priority order |

### Key Methods

```python
def build_email(self, email_from, email_to, subject, body, ...):
    # Constructs EmailMessage with RFC2047-compliant encoding.

def send_email(self, message, mail_server_id=None):
    # Sends email via selected SMTP server.
    # Handles STARTTLS, SSL, certificate auth.
    # Raises MailDeliveryException on failure.

def connect(self, smtp_server, smtp_port, ...):
    # Context manager for SMTP connection with SSL/TLS.
```

---

## `ir.attachment`

**File:** `ir_attachment.py`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Filename |
| `datas` | Binary | Base64-encoded content |
| `raw` | Binary | Raw content (not base64) |
| `mimetype` | Char | MIME type |
| `type` | Selection | `binary` / `url` |
| `url` | Char | For `type='url'` |
| `res_model` | Char | Linked model |
| `res_id` | Integer | Linked record ID |
| `res_field` | Char | Field the attachment came from |
| `store_fname` | Char | Filestore path (sha1[:2]/sha1) |
| `db_datas` | Binary | Data stored in DB (when storage='db') |
| `checksum` | Char | sha1 hash |
| `original_id` | Many2one | Original attachment for transformed copies |

### Storage (L4)

`ir_attachment.location` ICP controls storage backend:

- `'file'` (default): Files stored in `$FILESTORE/dbname/xx/xxxxxx...` — sha1-scattered across 256 subdirectories.
- `'db'`: Binary in `db_datas` column.

Garbage collection: `_mark_for_gc(fname)` adds to checklist, `_gc_file_store()` runs periodically to delete orphaned files.

### Access Control (L4)

`check()` overrides standard access: requires internal user (not portal/public) for attachments linked to records. The attachment itself must be readable regardless of linked record access if the user can see the record's name.

---

## `ir.sequence`

**File:** `ir_sequence.py`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | — | — |
| `code` | Char | — | Code for `next_by_code()` lookup |
| `implementation` | Selection | `'standard'` | `standard` (gaps OK) / `no_gap` (no gaps) |
| `active` | Boolean | `True` | — |
| `prefix` | Char | — | Python `%`-style interpolation |
| `suffix` | Char | — | — |
| `number_next` | Integer | `1` | Next number to use |
| `number_next_actual` | Integer | — | Computed actual next (from PG seq) |
| `number_increment` | Integer | `1` | Step size |
| `padding` | Integer | `0` | Zero-padding width |
| `company_id` | Many2one | `env.company` | — |
| `use_date_range` | Boolean | — | Per-period subsequences |
| `date_range_ids` | One2many | — | `ir.sequence.date_range` |

### Prefix/Suffix Interpolation

```python
def _get_prefix_suffix(self, date=None, date_range=None):
    # Keys: year, month, day, y, doy, woy, weekday, h24, h12, min, sec
    # Also: range_year, range_month, ... (from date_range context)
    #       current_year, ... (from now)
```

### Public APIs

```python
def next_by_id(self, sequence_date=None):
    # Get next value by sequence ID. Requires read access.

@api.model
def next_by_code(self, sequence_code, sequence_date=None):
    # Get next value by code. Looks up by company.
    # Returns False if no sequence found (logs debug).

@api.model
def get_id(self, code_or_id, code_or_id='id'):
    # DEPRECATED: use next_by_id / next_by_code.

@api.model
def get(self, code):
    # DEPRECATED: use next_by_code.
```

### L4 Notes

- **Standard implementation:** Creates a PostgreSQL sequence named `ir_sequence_%03d` — fast, gap-allowed, survives transaction rollback.
- **`no_gap`:** Uses `SELECT FOR UPDATE NOWAIT` to lock the row, then increments `number_next` in-memory. Slower but no gaps.
- `use_date_range`: Creates `ir.sequence.date_range` records per year automatically.
- Switching implementation drops/creates PG sequences.
- Date format interpolation uses `strftime` on the effective date (from context or argument).

---

## `ir.filters`

**File:** `ir_filters.py`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Filter name (unique within model/user/action scope) |
| `user_id` | Many2one | Private filter owner (False = global) |
| `domain` | Text | Domain expression |
| `context` | Text | Context expression dict |
| `sort` | Char | Sort expression array |
| `model_id` | Selection | Model name (from `_list_all_models`) |
| `is_default` | Boolean | Default filter for this scope |
| `action_id` | Many2one | Associated menu action (False = global) |
| `embedded_action_id` | Many2one | Embedded action reference |
| `embedded_parent_res_id` | Integer | Record ID for embedded action scope |
| `active` | Boolean | — |

### Key Methods

```python
def create_or_replace(self, vals):
    # Upsert: finds existing filter by (name, model, user, action, embedded_action)
    # lowercase name comparison, and updates it.
    # If is_default: unsets other defaults for same scope.

def get_filters(self, model, action_id=None, embedded_action_id=None, embedded_parent_res_id=None):
    # Returns list of filters visible to current user for this model.
    # Includes: private filters (user_id=uid) + global filters (user_id=False).

def _get_action_domain(self, action_id, embedded_action_id, embedded_parent_res_id):
    # Returns domain component for matching filters by action context.
    # Handles embedded action scoping: embedded_parent_res_id can be 0 or False
    # when not in an embedded action context (both are equivalent).
```

### SQL Constraints

```sql
unique(model_id, user_id, action_id, embedded_action_id, embedded_parent_res_id, lower(name))
-- Unique filter name per model/user/action scope (case-insensitive)

CHECK(NOT (embedded_parent_res_id IS NOT NULL AND embedded_action_id IS NULL))
-- embedded_parent_res_id requires embedded_action_id

CHECK(sort IS NULL OR jsonb_typeof(sort::jsonb) = 'array')
-- sort must be JSON array
```

---

## `ir.default`

**File:** `ir_default.py`

| Field | Type | Notes |
|-------|------|-------|
| `field_id` | Many2one | Target `ir.model.fields` |
| `user_id` | Many2one | User-specific (False = all users) |
| `company_id` | Many2one | Company-specific (False = all companies) |
| `condition` | Char | Optional condition string |
| `json_value` | Char | JSON-encoded default value |

### Key Methods

```python
@api.model
def set(self, model_name, field_name, value, user_id=False, company_id=False, condition=False):
    # Defines default. JSON-encodes value. User/company scopes resolved to current.
    # Upserts: updates existing record for same scope.

@api.model
def _get(self, model_name, field_name, user_id=False, company_id=False, condition=False):
    # Returns default value or None.

@api.model
@ormcache('uid', 'company.id', 'model_name', 'condition')
def _get_model_defaults(self, model_name, condition=False):
    # Returns all defaults for model as {field_name: value}.
    # Priority: user > company > global (ORDER BY user_id, company_id, id).
```

### Priority Resolution (L4)

Defaults are resolved in this order: user-specific > company-specific > global. `ORDER BY d.user_id, d.company_id, d.id` ensures user defaults are applied first; within the same category, the most recently created default wins.

---

## Mixins

### `format.address.mixin`

```python
def _get_view(self, view_id=None, view_type='form', **options):
    # Overrides _get_view to apply country-specific address_format.
    # Reorders street/city/state/zip fields in the form view based on format.
    # Also renders custom address_view_id if set on company.country_id.
```

### `format.vat.label.mixin`

```python
def _get_view(self, view_id=None, view_type='form', **options):
    # Overrides field label for 'vat' to use country-specific vat_label.
```

### `avatar.mixin`

Adds `avatar_1920/1024/512/256/128` computed fields. For partners with internal users, uses the user's avatar. Otherwise falls back to generated placeholder (company, truck, money icons per type).

---

## Version Changes (Odoo 17 → 18)

1. **`ir.cron` progress API:** Odoo 18 adds `ir.cron.progress` for batch progress tracking, `ir.cron.trigger` for ad-hoc scheduling, and `CONSECUTIVE_TIMEOUT_FOR_FAILURE` detection. Odoo 17 crons had no progress reporting.
2. **`res.company` currency delegation:** `_get_company_root_delegated_field_names()` in Odoo 18 returns `{'currency_id'}` — branches inherit currency from root. Odoo 17 did not have this restriction.
3. **`res.company` color:** Odoo 18 computes color from root's `partner_id.color`. Odoo 17 had no `_inverse_color`.
4. **`ir.actions.actions` path field:** Odoo 18 adds `path` field with unique constraint across all action tables (via shared table in PostgreSQL inheritance).
5. **`res.partner.company_type`:** Odoo 17 used `company_type` as a simple selection. Odoo 18 uses `compute+inverse` pattern.
6. **`ir.sequence` `number_next_actual`:** Odoo 18 added `_predict_nextval()` to read the PostgreSQL sequence without consuming it, for accurate display of actual next number.
7. **`res.lang` url_code auto-shortening:** Odoo 18 automatically sets URL code to shortest variant when activating a language.
8. **`res.users` `device_ids`:** Odoo 18 adds `res.device` model for session revocation. Odoo 17 had no device tracking.
9. **`ir.attachment` original_id:** Odoo 18 adds `original_id` for tracking transformed attachment chains.
10. **`res.partner barcode`:** Odoo 18 adds nullable btree-not-null index with company-dependent storage.
