---
tags: [odoo, odoo17, module, base, research_depth]
research_depth: deep
---

# Base Module -- Deep Research

**Source:** `addons/base/models/`
**Actual path:** `/Users/tri-mac/odoo/odoo17/odoo/odoo/addons/base/models/`
**Files examined:** 38 model files, all read in full

## Overview

The `base` module (`base`) is the foundational module upon which all other Odoo modules depend. It provides core entity models -- `res.partner`, `res.users`, `res.company`, `res.currency`, `res.country` -- and critical infrastructure for the entire system: module management (`ir.module.module`), system parameters (`ir.config_parameter`), scheduled jobs (`ir.cron`), attachment storage (`ir.attachment`), access control groups (`res.groups`), and more.

Without `base`, no other module can function. It ships with demo data and is automatically installed on every new Odoo database.

---

## Module Architecture Map

```
base
├── res.partner         -- contacts and companies (also: partner category, industry, title)
├── res.users            -- user accounts (inherits res.partner via _inherits)
├── res.company          -- company entities (parent/branch hierarchy)
├── res.country / res.country.state -- geographic reference data
├── res.currency / res.currency.rate -- monetary reference data
├── res.partner.bank / res.bank      -- banking reference data
├── res.lang             -- language reference data
├── res.groups           -- access control groups
├── res.users.settings   -- per-user preferences
├── res.users.log        -- login history
├── res.users.deletion    -- deferred user deletion queue
├── ir.module.module / ir.module.category -- module lifecycle
├── ir.module.module.dependency -- module dependency tree
├── ir.module.module.exclusion  -- module exclusion tree
├── ir.config_parameter   -- per-database key/value store
├── ir.cron / ir.cron.trigger -- scheduled job system
├── ir.attachment         -- binary/blob storage (file or db)
├── ir.default            -- user-defined field defaults
├── ir.filters            -- saved search filters
├── ir.exports / ir.exports.line -- export templates
├── ir.logging            -- application logging to DB
├── ir.actions.*          -- action record types
├── ir.ui.view / ir.ui.menu / ir.rule / ir.sequence
├── format.address.mixin  -- address formatting (used by res.partner, res.company)
├── avatar.mixin          -- avatar image generation (used by res.partner, res.users)
└── image.mixin           -- image field handling
```

---

## res.partner -- Complete Reference

**File:** `addons/base/models/res_partner.py:177`
**Inherits:** `format.address.mixin`, `avatar.mixin`
**Order:** `complete_name ASC, id DESC`

### All Fields

| Field | Type | Description | Line |
|-------|------|-------------|------|
| `id` | Many2one(self) | Magical self-reference for QWeb views | 301 |
| `name` | Char | Contact/company name | 209 |
| `complete_name` | Char | `parent_id.name / Name` formatted | 210 |
| `date` | Date | Arbitrary date field (indexed) | 211 |
| `title` | Many2one | Partner title (Mr, Mrs, Dr...) | 212 |
| `parent_id` | Many2one(res.partner) | Related company (for contacts) | 213 |
| `parent_name` | Char(related) | Related company name | 214 |
| `child_ids` | One2many | Contacts belonging to this company | 215 |
| `ref` | Char | Internal reference code (indexed) | 216 |
| `lang` | Selection | Language for communications | 217 |
| `active_lang_count` | Integer | Number of active languages in DB | 219 |
| `tz` | Selection | Timezone (from pytz) | 220 |
| `tz_offset` | Char | Computed tz offset string e.g. `+0100` | 225 |
| `user_id` | Many2one(res.users) | Salesperson/responsible user | 226 |
| `vat` | Char | Tax ID / VAT number (indexed) | 232 |
| `same_vat_partner_id` | Many2one | Partner sharing same VAT | 233 |
| `same_company_registry_partner_id` | Many2one | Partner sharing same company registry | 234 |
| `company_registry` | Char | Registry/registration number | 235 |
| `bank_ids` | One2many | Bank accounts | 237 |
| `website` | Char | Website URL | 238 |
| `comment` | Html | Notes | 239 |
| `category_id` | Many2many | Partner tags/categories | 241 |
| `active` | Boolean | Active flag | 243 |
| `employee` | Boolean | Is this an employee contact | 244 |
| `function` | Char | Job position/title | 245 |
| `type` | Selection | Address type: `contact\|invoice\|delivery\|other` | 246 |
| `street` | Char | Address line 1 | 258 |
| `street2` | Char | Address line 2 | 259 |
| `zip` | Char | ZIP/postal code | 260 |
| `city` | Char | City | 261 |
| `state_id` | Many2one(res.country.state) | State/province | 262 |
| `country_id` | Many2one(res.country) | Country | 263 |
| `country_code` | Char(related) | Country ISO code | 264 |
| `partner_latitude` | Float | Geo latitude | 265 |
| `partner_longitude` | Float | Geo longitude | 266 |
| `email` | Char | Email address | 267 |
| `email_formatted` | Char | `"Name <email@domain>"` formatted | 268 |
| `phone` | Char | Phone (no unaccent) | 271 |
| `mobile` | Char | Mobile (no unaccent) | 272 |
| `is_company` | Boolean | Is this a company (not a person) | 273 |
| `is_public` | Boolean | Is a public-contact partner | 275 |
| `industry_id` | Many2one | Partner industry | 276 |
| `company_type` | Selection | Interface: `person\|company` | 278 |
| `company_id` | Many2one(res.company) | Owning company | 281 |
| `color` | Integer | Color index for kanban | 282 |
| `user_ids` | One2many | Users linked to this partner | 283 |
| `partner_share` | Boolean | Is a sharing partner (customer) | 284 |
| `contact_address` | Char | Full formatted address string | 288 |
| `commercial_partner_id` | Many2one | Top-level commercial entity | 291 |
| `commercial_company_name` | Char | Company name from commercial entity | 295 |
| `company_name` | Char | Manual company name override | 297 |
| `barcode` | Char | Barcode identifier | 298 |

### SQL Constraints

```python
# Line 303-305
_sql_constraints = [
    ('check_name', "CHECK( (type='contact' AND name IS NOT NULL) or (type!='contact') )",
     'Contacts require a name'),
]
```

### Commercial Partner Pattern

**Purpose:** The `commercial_partner_id` is the top-level partner in a partner hierarchy. For companies, it points to themselves. For individual contacts under a company, it points to the root company.

**The `_compute_commercial_partner` method (lines 431-437):**

```python
@api.depends('is_company', 'parent_id.commercial_partner_id')
def _compute_commercial_partner(self):
    for partner in self:
        if partner.is_company or not partner.parent_id:
            partner.commercial_partner_id = partner
        else:
            partner.commercial_partner_id = partner.parent_id.commercial_partner_id
```

**When to use commercial_partner_id vs partner_id:**
- Use `commercial_partner_id` when you need the company-level entity for business logic (e.g., computing VAT, credit limits, commercial fields like `vat`, `industry_id`, `company_registry`)
- Use `partner_id` directly when you need the specific contact record (e.g., for messaging, addressing)

**Commercial fields** (line 606-612) -- fields synced from commercial entity to all its contacts:

```python
@api.model
def _commercial_fields(self):
    return ['vat', 'company_registry', 'industry_id']
```

**Commercial sync methods:**
- `_commercial_sync_from_company()` (line 621) -- syncs commercial fields FROM the parent commercial entity TO the current partner
- `_commercial_sync_to_children()` (line 652) -- propagates commercial fields DOWN to all non-company children
- `_company_dependent_commercial_sync()` (line 631) -- handles company-specific overrides via `ir.property`

### Address Fields

The `format.address.mixin` abstract model (lines 45-120) provides country-specific address formatting:

```python
class FormatAddressMixin(models.AbstractModel):
    _name = "format.address.mixin"
    # Key method: formats address according to country's address_format
    def _display_address(self, without_company=False):
        # Uses country_id.address_format or default:
        # "%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s"
```

Address field list: `('street', 'street2', 'zip', 'city', 'state_id', 'country_id')` (line 33)

`_address_fields()` returns this tuple and is used throughout for syncing addresses between parent companies and their contacts.

### Key Methods

| Method | Line | Description |
|--------|------|-------------|
| `default_get()` | 192 | Sets parent company + lang as defaults |
| `_compute_complete_name()` | 365 | Builds `Name` or `Company, Name` |
| `_compute_same_vat_partner_id()` | 395 | Detects duplicate VAT/registry |
| `_compute_contact_address()` | 423 | Computes full address via `_display_address()` |
| `_check_parent_id()` | 459 | `@api.constrains` recursion check |
| `copy()` | 464 | Appends ` (copy)` to name on duplicate |
| `onchange_parent_id()` | 471 | Syncs address from parent, warns on company change |
| `_onchange_parent_id_for_lang()` | 496 | Propagates parent's language |
| `_compute_email_formatted()` | 523 | Builds `"Name <email>"` string |
| `_compute_company_type()` | 556 | Maps `is_company` to selection |
| `_write_company_type()` | 561 | Inverse: writes `is_company` from selection |
| `_address_fields()` | 591 | Returns list of address field names |
| `_commercial_fields()` | 606 | Returns list of commercial field names |
| `_fields_sync()` | 663 | Called in `create()`/`write()` to sync commercial + address fields |
| `_children_sync()` | 679 | Syncs commercial fields and address to children |
| `_handle_first_contact_creation()` | 697 | When first contact is created for a company with no address, copies contact address to parent |
| `write()` | 720 | Handles active=False with user protection; company_id consistency check; sudo write for is_company |
| `create()` | 775 | Website cleaning, company_name clearing, _fields_sync after creation |
| `_load_records_create()` | 813 | Batch-optimized version of create-time sync for data loading |
| `create_company()` | 851 | Creates parent company from contact |
| `open_commercial_entity()` | 865 | Button to open the commercial partner |
| `open_parent()` | 875 | Button to open the parent partner |
| `name_create()` | 907 | Parses `"Name <email>"` format to create partner |
| `find_or_create()` | 931 | Finds partner by email or creates; used by mail, etc. |
| `address_get()` | 974 | DFS search for address of given type (contact/invoice/delivery) |
| `_display_address()` | 1054 | Formats address per country template |
| `_prepare_display_address()` | 1035 | Builds context dict for `%`-formatting address |
| `_check_import_consistency()` | 1080 | During import, validates state belongs to country |

### Partner Categories

**File:** `addons/base/models/res_partner.py:123`

```python
class PartnerCategory(models.Model):
    _name = 'res.partner.category'
    _parent_store = True
    # Fields: name, color, parent_id, child_ids, active, parent_path
    # Key constraint:
    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('You can not create recursive tags.'))
```

### Partner Titles

**File:** `addons/base/models/res_partner.py:168`

```python
class PartnerTitle(models.Model):
    _name = 'res.partner.title'
    # Fields: name (translate), shortcut (translate)
```

### Partner Industries

**File:** `addons/base/models/res_partner.py:1114`

```python
class ResPartnerIndustry(models.Model):
    _name = "res.partner.industry"
    _order = "name"
    # Fields: name (translate), full_name (translate), active
```

---

## res.users -- Complete Reference

**File:** `addons/base/models/res_users.py:321`
**Inherits:** `res.partner` via `_inherits = {'res.partner': 'partner_id'}`
**Order:** `name, login`

### The _inherits Pattern

```python
# Line 331
_inherits = {'res.partner': 'partner_id'}
```

**Why this matters:**
- `res.users` stores only technical data (login, password, groups, company)
- Partner data (name, email, address, avatar, lang) lives in `res.partner`
- The `partner_id` field links a user to their partner record
- Accessing `user.name` actually reads `user.partner_id.name`
- When a user is deleted, the partner is NOT automatically deleted (unless via `res.users.deletion`)

### Password Security

**passlib CryptContext (line 1202-1221):**

```python
@tools.ormcache()
def _crypt_context(self):
    cfg = self.env['ir.config_parameter'].sudo()
    return CryptContext(
        ['pbkdf2_sha512', 'plaintext'],
        deprecated=['auto'],
        pbkdf2_sha512__rounds=max(MIN_ROUNDS, int(cfg.get_param('password.hashing.rounds', 0))),
    )
```

- `MIN_ROUNDS = 600_000` (line 91)
- Default rounds configurable via ICP `password.hashing.rounds`
- `pbkdf2_sha512` is the primary scheme; `plaintext` is for legacy support
- `deprecated='auto'` flags passwords for rehashing on next login

**Password initialization hook (lines 419-434):**

On first server start, `init()` detects plaintext passwords and auto-hashes them:

```python
def init(self):
    cr = self._cr
    cr.execute(r"""
        SELECT id, password FROM res_users
        WHERE password IS NOT NULL
          AND password !~ '^\$[^$]+\$[^$]+\$.'
    """)
    if self._cr.rowcount:
        Users = self.sudo()
        for uid, pw in cr.fetchall():
            Users.browse(uid).password = pw
```

### SELF_READABLE_FIELDS / SELF_WRITEABLE_FIELDS

These properties (lines 340-358) control what fields a user can read/write on their own record:

```python
@property
def SELF_READABLE_FIELDS(self):
    return [
        'signature', 'company_id', 'login', 'email', 'name', 'image_1920',
        'image_1024', 'image_512', 'image_256', 'image_128', 'lang', 'tz',
        'tz_offset', 'groups_id', 'partner_id', 'write_date', 'action_id',
        'avatar_1920', 'avatar_1024', 'avatar_512', 'avatar_256', 'avatar_128',
        'share',
    ]

@property
def SELF_WRITEABLE_FIELDS(self):
    return ['signature', 'action_id', 'company_id', 'email', 'name', 'image_1920', 'lang', 'tz']
```

The `read()` method (line 640) and `check_field_access_rights()` (line 648) use these to allow self-service writes without access rights errors.

### @check_identity Decorator

**Lines 138-175:** Decorator for sensitive action methods that requires recent password re-entry:

```python
def check_identity(fn):
    @wraps(fn)
    def wrapped(self):
        if not request:
            raise UserError(_("This method can only be accessed over HTTP"))
        # Check if password was verified in last 10 minutes
        if request.session.get('identity-check-last', 0) > time.time() - 10 * 60:
            return fn(self)
        # Show identity check wizard
        w = self.sudo().env['res.users.identitycheck'].create({...})
        return {
            'type': 'ir.actions.act_window', 'res_model': 'res.users.identitycheck',
            'res_id': w.id, 'name': _("Security Control"),
            'target': 'new', 'views': [(False, 'form')],
        }
```

Used by `preference_change_password()` (line 1067) and `ChangePasswordOwn.change_password()` (line 2098).

### All Fields (res.users core)

| Field | Type | Description | Line |
|-------|------|-------------|------|
| `partner_id` | Many2one | Link to res.partner (required, ondelete='restrict') | 368 |
| `login` | Char | Unique login username | 370 |
| `password` | Char | Computed/inverse -- never stored in cleartext | 371 |
| `new_password` | Char | Set password (write-only) | 374 |
| `signature` | Html | Email signature | 379 |
| `active` | Boolean | Active flag | 380 |
| `active_partner` | Boolean(related) | Partner active state | 381 |
| `action_id` | Many2one | Home action on login | 382 |
| `groups_id` | Many2many | Access groups (default from template user) | 384 |
| `log_ids` | One2many | Login history records | 385 |
| `login_date` | Datetime(related) | Last login time | 386 |
| `share` | Boolean | Is portal/external user | 387 |
| `companies_count` | Integer | Total company count | 389 |
| `tz_offset` | Char | Computed timezone offset | 390 |
| `res_users_settings_ids` | One2many | User settings | 391 |
| `res_users_settings_id` | Many2one | Singleton settings record | 393 |
| `company_id` | Many2one | Current/active company | 398 |
| `company_ids` | Many2many | Allowed companies | 400 |
| `name` | Char(related, inherited) | From partner | 405 |
| `email` | Char(related, inherited) | From partner | 406 |
| `accesses_count` | Integer | Count of model access rights | 408 |
| `rules_count` | Integer | Count of record rules | 410 |
| `groups_count` | Integer | Count of groups | 412 |

### Key Methods

| Method | Line | Description |
|--------|------|-------------|
| `_check_company()` | 554 | `@api.constrains` -- `company_id` must be in `company_ids` |
| `_check_action_id()` | 565 | Prevents dangerous home actions |
| `_check_one_user_type()` | 589 | Users cannot be in multiple user-type groups |
| `_has_multiple_groups()` | 601 | SQL query to check group overlap |
| `read()` | 640 | Allows self-read of SELF_READABLE_FIELDS via sudo |
| `check_field_access_rights()` | 648 | Same self-access bypass |
| `_search()` | 662 | Blocks searching on USER_PRIVATE_FIELDS |
| `_fetch_query()` | 545 | Obscures USER_PRIVATE_FIELDS values |
| `create()` | 669 | Sets partner company/active; generates SVG avatar |
| `write()` | 692 | Prevents self-deactivation; handles company_id changes; SELF_WRITEABLE_FIELDS bypass |
| `context_get()` | 802 | Builds context dict with lang, tz, uid |
| `_get_company_ids()` | 839 | `@ormcache` -- IDs of companies user belongs to |
| `_login()` | 879 | Classmethod: authenticates user, updates tz, logs login |
| `authenticate()` | 905 | Classmethod: verifies + sets web.base.url on first login |
| `check()` | 933 | `@ormcache` -- verifies uid/password for RPC |
| `_compute_session_token()` | 951 | HMAC-SHA256 of session ID using db secret |
| `change_password()` | 972 | Changes own password (requires old password) |
| `_change_password()` | 991 | Internal password setter with logging |
| `_deactivate_portal_user()` | 1006 | Portal self-deletion: anonymizes login, queues for deletion |
| `has_group()` | 1088 | `@api.model` check if user in group by XML ID |
| `_has_group()` | 1098 | `@ormcache` direct SQL check via `res_groups_users_rel` |
| `_is_internal()` | 1174 | `not sudo().share` -- is an internal user |
| `_is_portal()` / `_is_public()` / `_is_system()` / `_is_admin()` / `_is_superuser()` | 1178-1196 | Role checks |
| `_crypt_context()` | 1202 | passlib CryptContext (see above) |
| `_assert_can_auth()` | 1223 | Login rate-limiting context manager |
| `_on_login_cooldown()` | 1292 | Determines if login should be blocked |

### Groups and Implied Groups

**File:** `addons/base/models/res_users.py:1345` (class `GroupsImplied`)

```python
class GroupsImplied(models.Model):
    _inherit = 'res.groups'
    implied_ids = fields.Many2many(  # direct inheritance
        'res.groups', 'res_groups_implied_rel', 'gid', 'hid',
        string='Inherits',
    )
    trans_implied_ids = fields.Many2many(  # transitive closure computed
        string='Transitively inherits',
        compute='_compute_trans_implied', recursive=True,
    )
```

The `write()` method (line 1371) uses a recursive SQL CTE to atomically add implied groups to all users of a group.

### Reified Group Fields

The `UsersView` class (line 1728) dynamically generates form view fields for groups:
- Boolean `in_group_ID` -- True iff user is in group ID
- Selection `sel_groups_ID1_ID2_..._IDk` -- Which role is selected

Generated in `_update_user_groups_view()` (line 1535) which rewrites the `base.user_groups_view` XML.

---

## res.company -- Complete Reference

**File:** `addons/base/models/res_company.py:15`
**Order:** `sequence, name`

### Root Company Pattern

Companies form a hierarchy: a root company with optional branch subsidiaries.

```python
# Delegated fields -- identical across ALL branches of a company
def _get_company_root_delegated_field_names(self):  # line 89
    return ['currency_id']  # currency must be same across all branches
```

When a root company changes `currency_id`, all branches are automatically updated (lines 324-332 in `write()`).

`root_id` (line 39) and `parent_ids` (line 38) are computed from `parent_path` (line 109-112):

```python
@api.depends('parent_path')
def _compute_parent_ids(self):
    for company in self.with_context(active_test=False):
        company.parent_ids = self.browse(
            int(id) for id in company.parent_path.split('/') if id
        )
        company.root_id = company.parent_ids[0]
```

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char(related) | From partner_id.name |
| `partner_id` | Many2one | Required; created automatically on company create |
| `parent_id` | Many2one | Parent/root company -- IMMUTABLE after creation (line 311) |
| `child_ids` | One2many | Branch companies |
| `currency_id` | Many2one | Root-delegated; same for all branches |
| `logo` | Binary(related) | From partner_id.image_1920 |
| `logo_web` | Binary | Processed thumbnail for web (180px wide) |
| `paperformat_id` | Many2one | Report paper format |
| `external_report_layout_id` | Many2one | Report template view |
| `font`, `primary_color`, `secondary_color` | Selection/Char | Report branding |
| `report_header`, `report_footer`, `company_details` | Html | Report header/footer content |
| `vat`, `company_registry` | Char(related) | From partner |

### Key Methods

| Method | Line | Description |
|--------|------|-------------|
| `copy()` | 21 | Duplication is forbidden |
| `create()` | 230 | Auto-creates partner; sets currency active; adds companies to user |
| `write()` | 299 | Prevents parent_id change; cascades currency to branches; archives children |
| `_check_active()` | 341 | Cannot archive if active users exist |
| `_check_root_delegated_fields()` | 358 | Branches must have same currency as root |
| `init()` | 80 | Sets default paper format on companies missing one |
| `_accessible_branches()` | 412 | Returns branches the current user can access (cached) |
| `_all_branches_selected()` | 415 | Returns True if all branches of root are selected |
| `_get_public_user()` | 438 | Gets/creates the public user for this company |

### Company cannot be deleted if it has branches (line 286):

```python
@api.ondelete(at_uninstall=False)
def _unlink_if_company_has_no_children(self):
    if any(company.child_ids for company in self):
        raise UserError(_("Companies that have associated branches cannot be deleted..."))
```

---

## res.currency / res.currency.rate -- Complete Reference

**File:** `addons/base/models/res_currency.py:22`

### res.currency Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char(3) | ISO 4217 currency code |
| `full_name` | Char | Full currency name |
| `symbol` | Char | Currency sign ($, EUR, etc.) |
| `rate` | Float | Computed current rate (depends on context date/company) |
| `inverse_rate` | Float | 1/rate |
| `rate_string` | Char | Display: `1 EUR = 0.854321 USD` |
| `rate_ids` | One2many | Historical rates |
| `rounding` | Float | Rounding factor (default 0.01) |
| `decimal_places` | Integer | Computed from rounding |
| `active` | Boolean | Active flag |
| `position` | Selection | Symbol position: `after\|before` |
| `date` | Date | Latest rate date |
| `currency_unit_label` | Char | Label for main unit |
| `currency_subunit_label` | Char | Label for subunit |
| `is_current_company_currency` | Boolean | Is this the company currency |

### Key Methods

```python
# Rate computation (lines 163-177)
def _compute_current_rate(self):
    # Uses _get_rates() for multi-currency SQL query
    currency_rates = (self + to_currency)._get_rates(company, date)
    for currency in self:
        currency.rate = (rates.get(currency.id) or 1.0) / rates.get(to_currency.id)

# Conversion (lines 287-306)
def _convert(self, from_amount, to_currency, company=None, date=None, round=True):
    if from_amount:
        to_amount = from_amount * self._get_conversion_rate(self, to_currency, company, date)
    return to_currency.round(to_amount) if round else to_amount

# Text rendering (lines 192-219)
def amount_to_text(self, amount):
    # Uses num2words library to render e.g. "One Hundred Twenty-Three Euros and 45 Cents"
```

### res.currency.rate

| Field | Type | Description |
|-------|------|-------------|
| `name` | Date | Rate date (unique per currency/company per day) |
| `rate` | Float | Rate value (rate of this currency in company currency) |
| `company_rate` | Float | Rate relative to company currency |
| `inverse_company_rate` | Float | Inverse of company_rate |
| `currency_id` | Many2one | Which currency |
| `company_id` | Many2one | Company-specific rate (NULL = global) |

**Constraint (line 383):** Only one rate per currency per day per company: `unique (name,currency_id,company_id)`

**Critical constraint (line 472):** Rates can only be created for main/root companies (not branches):

```python
@api.constrains('company_id')
def _check_company_id(self):
    for rate in self:
        if rate.company_id.sudo().parent_id:
            raise ValidationError("Currency rates should only be created for main companies")
```

### Auto Multi-Currency Group

When >1 currency is active, `_toggle_group_multi_currency()` (line 84) automatically enables `base.group_multi_currency`:

```python
def _toggle_group_multi_currency(self):
    active_currency_count = self.search_count([('active', '=', True)])
    if active_currency_count > 1:
        self._activate_group_multi_currency()
    elif active_currency_count <= 1:
        self._deactivate_group_multi_currency()
```

---

## ir.module.module -- Complete Reference

**File:** `addons/base/models/ir_module.py:159`

### 6 Lifecycle States

| State | Label | Description |
|-------|-------|-------------|
| `uninstallable` | Not Installable | Missing dependencies or errors |
| `uninstalled` | Not Installed | On disk, not loaded in registry |
| `installed` | Installed | Loaded in registry, data initialized |
| `to upgrade` | To be Upgraded | Upgrade pending |
| `to remove` | To be Removed | Removal pending |
| `to install` | To be Installed | Installation pending |

### All Button Methods

| Method | Button | Line | Action |
|--------|--------|------|--------|
| `button_install()` | Install | 403 | Marks modules as `to install` + auto-installables |
| `button_immediate_install()` | -- | 465 | Installs now, commits, reloads registry |
| `button_install_cancel()` | Cancel | 484 | Resets state to `uninstalled` |
| `button_uninstall()` | Uninstall | 637 | Marks as `to remove`; cascades to dependents |
| `button_immediate_uninstall()` | -- | 628 | Uninstalls now |
| `button_uninstall_wizard()` | Uninstall | 651 | Opens `base.module.uninstall` wizard |
| `button_uninstall_cancel()` | Cancel | 662 | Resets to `installed` |
| `button_upgrade()` | Upgrade | 675 | Marks as `to upgrade`; cascades to dependencies |
| `button_immediate_upgrade()` | -- | 667 | Upgrades now |
| `button_upgrade_cancel()` | Cancel | 724 | Resets to `installed` |
| `module_uninstall()` | -- | 489 | Actual uninstall: removes data via `ir.model.data`, drops columns |

### update_list()

**Line 762:** Called to scan the `addons/` directory and sync `ir.module.module` records with what's on disk:

```python
@assert_log_admin_access
@api.model
def update_list(self):
    # Iterates modules.get_modules() -- all directories in addons/
    # Creates new ir.module.module records for new modules
    # Updates metadata from __manifest__.py (version, dependencies, etc.)
    # Returns [updated_count, added_count]
```

### Dependency Management

`ModuleDependency` (line 959): links `module_id` to dependency `name` (a Char, not a Many2one, because the dependency might not be installed).

`ModuleExclusion` (line 1003): prevents installing conflicting modules.

`auto_install` field: modules that auto-install when all dependencies are satisfied (line 305).

### `assert_log_admin_access` Decorator

**Line 62-77:** Every state-changing method is protected by this decorator:

```python
def assert_log_admin_access(method):
    def check_and_log(method, self, *args, **kwargs):
        user = self.env.user
        origin = request.httprequest.remote_addr if request else 'n/a'
        if not self.env.is_admin():
            _logger.warning('DENY access to module.%s on %s to user %s...', ...)
            raise AccessDenied()
        _logger.info('ALLOW access to module.%s on %s to user %s...', ...)
        return method(self, *args, **kwargs)
    return decorator(check_and_log, method)
```

### Module Categories

```python
class ModuleCategory(models.Model):  # line 79
    exclusive = fields.Boolean()  # only one module per category can be installed
    # e.g., "Invoicing" is exclusive -- you can only install one invoicing app
```

---

## ir.config_parameter -- Complete Reference

**File:** `addons/base/models/ir_config_parameter.py`

Per-database key-value store for system configuration.

### Built-in Default Parameters

Initialized on DB creation via `init()` (line 45):

| Key | Default | Purpose |
|-----|---------|---------|
| `database.secret` | `uuid.uuid4()` | HMAC secret for session tokens |
| `database.uuid` | `uuid.uuid1()` | Unique DB identifier |
| `database.create_date` | `fields.Datetime.now` | DB creation timestamp |
| `web.base.url` | `http://localhost:PORT` | Base URL for redirects |
| `base.login_cooldown_after` | `10` | Failed attempts before cooldown |
| `base.login_cooldown_duration` | `60` | Cooldown duration in seconds |

### Performance Note: _get_param Bypasses ORM

**Line 72-79:** `_get_param()` is `@ormcache`'d and uses raw SQL to avoid ORM overhead:

```python
@api.model
@ormcache('key')
def _get_param(self, key):
    # bypass ORM -- called from field @depends contexts
    self.flush_model(['key', 'value'])
    self.env.cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", [key])
    result = self.env.cr.fetchone()
    return result and result[0]
```

This is critical: `get_param()` is used in `@api.depends` contexts (e.g., `ir_attachment.location`, `password.hashing.rounds`), so it must work even when the ORM is not fully initialized.

---

## ir.attachment -- Complete Reference

**File:** `addons/base/models/ir_attachment.py:28`

### Storage: File vs Database

`ir_attachment.location` ICP controls where binaries are stored (line 55):

- `'file'` (default): Store in filestore at `$FILESTORE/dbname/xx/xxx...` based on SHA1 hash
- `'db'`: Store directly in `db_datas` column (not recommended for large files)

### Full Path Computation

**Lines 96-101:**

```python
@api.model
def _full_path(self, path):
    path = re.sub('[.]', '', path)  # sanitize
    path = path.strip('/\\')
    return os.path.join(self._filestore(), path)  # filestore root + path
```

**Path structure (line 104-121):**
- Old: `sha[:3] + '/' + sha` (e.g., `abc/abcdef...`)
- New: `sha[:2] + '/' + sha` (e.g., `ab/abcdef...`) -- scatters across 256 subdirs

### store_fname

`store_fname` stores the relative path within filestore (e.g., `ab/abcdef123...`). The raw binary is reconstructed as `self._full_path(store_fname)`.

### Key Methods

| Method | Line | Description |
|--------|------|-------------|
| `_storage()` | 55 | Returns ICP `ir_attachment.location` value |
| `_filestore()` | 59 | Returns `config.filestore(dbname)` |
| `_full_path()` | 96 | Converts store_fname to full OS path |
| `_get_path()` | 104 | Gets/creates path with SHA-based collision check |
| `_file_read()` | 124 | Reads binary from filestore |
| `_file_write()` | 134 | Writes binary to filestore; registers for GC |
| `_gc_file_store()` | 166 | Auto-vacuum: removes orphaned files via checklist |
| `_compute_raw()` | 241 | Reads from store_fname or db_datas |
| `_get_datas_related_values()` | 268 | Computes checksum, index_content, store_fname |
| `_postprocess_contents()` | 329 | Auto-resizes images > max_resolution |
| `check()` | 458 | Access control: attachment inherits document permissions |
| `_search()` | 530 | Custom search: filters by document access rights |

### Garbage Collection

Files are never deleted immediately on attachment deletion. Instead:
1. `unlink()` calls `_file_delete(fname)` which calls `_mark_for_gc(fname)` (line 148-164)
2. `_mark_for_gc()` creates a "checklist" entry in `filestore/checklist/XX/XXXXX...`
3. `_gc_file_store()` (line 166, `@api.autovacuum`) runs periodically
4. It reads all checklist entries, checks which store_fname values exist in DB, and deletes orphans

This prevents data loss from rolled-back transactions.

---

## ir.cron -- Complete Reference

**File:** `addons/base/models/ir_cron.py:41`

### Cron Architecture

`ir_cron` inherits from `ir.actions.server` via `delegate=True` on `ir_actions_server_id` (line 57). Every cron is backed by a server action.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `ir_actions_server_id` | Many2one | Delegate to server action (name, model_id, code) |
| `cron_name` | Char | Computed from server action name |
| `user_id` | Many2one | User to execute as (determines company context) |
| `active` | Boolean | Enable/disable |
| `interval_number` | Integer | Repeat every N units |
| `interval_type` | Selection | `minutes\|hours\|days\|weeks\|months` |
| `nextcall` | Datetime | Next scheduled execution |
| `lastcall` | Datetime | Previous successful execution |
| `priority` | Integer | Lower = runs first (default 5) |
| `numbercall` | Integer | Max calls (-1 = infinite) |
| `doall` | Boolean | Run missed occurrences on restart |

### Key Methods

| Method | Line | Description |
|--------|------|-------------|
| `_process_jobs()` | 114 | Classmethod: main cron worker loop |
| `_get_all_ready_jobs()` | 203 | SQL query for due jobs + triggered jobs |
| `_acquire_one_job()` | 222 | `FOR NO KEY UPDATE SKIP LOCKED` -- prevents double-run |
| `_process_job()` | 298 | Executes one job, computes nextcall, handles missed runs |
| `_callback()` | 378 | Runs the server action, logs timing |
| `_try_lock()` | 413 | Row-level lock to prevent concurrent modification |
| `_trigger()` / `_trigger_list()` | 473 | Schedule cron to run at specific time |

### Missed Call Handling

`_process_job()` (lines 297-370) computes how many calls were missed:

```python
# Example: cron every 30 minutes, last ran at 15, now is 135
# Missed: 4 calls (at 30, 60, 90, 120)
# effective_call_count = min(missed_call_count, numbercall)
```

If `doall=False` (default), runs only once regardless of how many were missed.

---

## ir.filters -- Complete Reference

**File:** `addons/base/models/ir_filters.py`

Saved search filters. Users can create personal filters or share them globally.

```python
@api.model
def create_or_replace(self, vals):  # line 120
    # Upsert logic: if filter with same (name, model, user, action) exists, update it
    # Handles is_default: setting new default unsets other defaults
```

SQL unique index (line 164): `model_id, COALESCE(user_id,-1), COALESCE(action_id,-1), lower(name)`

---

## ir.default -- Complete Reference

**File:** `addons/base/models/ir_default.py`

User-defined default values for fields. Values are JSON-encoded.

```python
@api.model
def _get_model_defaults(self, model_name, condition=False):  # line 150
    # @ormcache('self.env.uid', 'self.env.company.id', 'model_name', 'condition')
    # Returns dict of {field_name: value}
    # Priority order: user-specific > company-specific > global
```

Scope: field + user_id + company_id + condition. The most specific wins.

---

## ir.exports / ir.exports.line

**File:** `addons/base/models/ir_exports.py`

Export column definitions. Each export template has one `export_fields` line per column to export.

---

## ir.logging

**File:** `addons/base/models/ir_logging.py`

Application logging to database. NOT the normal Python logging -- this stores log entries in a table for the log database feature (`--log-db`).

Special `init()` method (line 36): drops a problematic FK constraint on `write_uid` to prevent deadlock during module installation.

---

## res.partner.bank / res.bank

**File:** `addons/base/models/res_bank.py`

### res.bank

Bank institution record: `name`, `bic` (SWIFT code), `city`, `country`, `state`, address fields.

### res.partner.bank

Bank account linked to a partner:

```python
sanitized_acc_number = fields.Char(compute='_compute_sanitized_acc_number', store=True)
# Sanitization: remove all non-alphanumeric, uppercase
# Used in unique constraint:
_sql_constraints = [
    ('unique_number', 'unique(sanitized_acc_number, partner_id)',
     'The combination Account Number/Partner must be unique.')
]
```

**Key behavior:** Search on `acc_number` is automatically rewritten to search on `sanitized_acc_number` (lines 136-149).

---

## res.users.settings / res.users.log / res.users.deletion

### res.users.settings (line `/Users/tri-mac/odoo/odoo17/odoo/odoo/addons/base/models/res_users_settings.py`)

Per-user preference singleton:

```python
class ResUsersSettings(models.Model):
    _name = 'res.users.settings'
    # singleton per user via SQL UNIQUE(user_id)
    @api.model
    def _find_or_create_for_user(self, user):  # creates if missing
    def set_res_users_settings(self, new_settings):  # partial update
    def _res_users_settings_format(self, fields_to_format=None):  # serialize
```

### res.users.log (line 302)

`res.users.log` records are auto-created on each login via `_update_last_login()` (line 861). The `create_uid` and `create_date` magical fields give login timestamp. Garbage-collected by `_gc_user_logs()` (line 309) which removes duplicate entries.

### res.users.deletion (line `/Users/tri-mac/odoo/odoo17/odoo/odoo/addons/base/models/res_users_deletion.py`)

Deferred user deletion queue. Portal users request self-deletion via `_deactivate_portal_user()` which:
1. Anonymizes login (`__deleted_user_{id}_{timestamp}`)
2. Clears password
3. Removes API keys
4. Archives user + partner
5. Queues deletion via `res.users.deletion`

`_gc_portal_users()` cron (line 40) processes in batches of 10, deleting user then partner separately (partner deletion may fail if linked to invoices, so it never blocks user deletion).

---

## avatar.mixin -- Complete Reference

**File:** `addons/base/models/avatar_mixin.py`

Inherited by `res.partner` and `res.users`. Generates SVG avatars from initials when no image is uploaded:

```python
def _avatar_generate_svg(self):  # line 64
    initial = self[self._avatar_name_field][0].upper()  # e.g., "J" for "John"
    bgcolor = get_hsl_from_seed(self[self._avatar_name_field] + str(self.create_date.timestamp()))
    # Returns base64 SVG: colored rectangle + white initial letter
```

Color is deterministic from name + creation timestamp (HSL with SHA512 seed).

---

## Key Architectural Patterns

### 1. Delegation Inheritance (_inherits)
`res.users -> res.partner`: User-specific fields in `res_users`, partner fields via `_inherits`.

### 2. Root-Delegated Fields
`res.company`: `currency_id` must be identical across all branches. The `_get_company_root_delegated_field_names()` pattern propagates writes from root to branches automatically.

### 3. Commercial Partner Hierarchy
`res.partner`: Every partner hierarchy has a single "commercial entity" at the root. Commercial fields (`vat`, `industry_id`, `company_registry`) are company-level and propagate to all contacts.

### 4. ORM + Raw SQL Hybrid
`ir_config_parameter._get_param()` bypasses ORM with direct SQL (and is `@ormcache`'d) because it's used inside `@api.depends` contexts that run before the ORM is fully initialized.

### 5. Filestore GC Checklist
`ir.attachment` never immediately deletes files. Files are marked for GC via a checklist; the autovacuum runs later. This prevents data loss from rolled-back transactions.

### 6. Cron Locking
Crons use `FOR NO KEY UPDATE SKIP LOCKED` to prevent double-execution across workers. `_try_lock()` prevents manual edits during active execution.

### 7. Implied Groups via SQL CTE
Adding a group to `implied_ids` triggers a recursive SQL CTE that atomically adds the implied group to all users of the parent group.

### 8. SELF_READABLE/SELF_WRITEABLE Fields
Users can edit their own profile fields (name, email, avatar, tz, lang, signature) without access rights errors via the `SELF_WRITEABLE_FIELDS` bypass in `write()`.

### 9. Company-Dependent Defaults
`ir.default` supports scoping by `user_id` and `company_id`, with priority: user > company > global. This is cached per (uid, company_id, model, condition).

### 10. Reified Group Fields
Groups are dynamically added to the user form view as boolean/selection fields (`in_group_N`, `sel_groups_N_M_K`) by rewriting `base.user_groups_view` XML on every group change.

---

## See Also

- [Core/API](Core/API.md) -- ORM decorators like `@api.depends`, `@api.constrains`
- [Core/BaseModel](Core/BaseModel.md) -- Model foundation, `_name`, `_inherit`, CRUD methods
- [Patterns/Security Patterns](Patterns/Security Patterns.md) -- ACL CSV, ir.rule, field groups
- [Tools/ORM Operations](Tools/ORM Operations.md) -- `search()`, `browse()`, `create()`, `write()`, domain operators
- [Modules/Stock](Modules/stock.md) -- Warehouse/Inventory (uses res.partner, res.company extensively)
- [Modules/Purchase](Modules/purchase.md) -- Purchase orders (uses res.partner)
- [Modules/Account](Modules/account.md) -- Accounting (uses res.partner, res.company, res.currency)
- [Modules/Sale](Modules/sale.md) -- Sales (uses res.partner, commercial_partner_id)
