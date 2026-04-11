---
type: module
module: base
submodule: res_partner
tags: [odoo, odoo19, base, partner, contact, company, address, commercial_entity]
created: 2026-04-11
source: ~/odoo/odoo19/odoo/odoo/addons/base/models/res_partner.py
related_modules: [base_address_extended, base_vat, base_geolocalize, mail, portal]
---

# res.partner — Contact & Partner Model

## Table of Contents

1. [Overview](#1-overview)
2. [Module Classification](#2-module-classification)
3. [L1 — All Fields & Method Signatures](#3-l1--all-fields--method-signatures)
4. [L2 — Field Types, Defaults, Constraints, Purpose](#4-l2--field-types-defaults-constraints-purpose)
5. [L3 — Edge Cases](#5-l3--edge-cases)
6. [L4 — Performance, Historical & Security](#6-l4--performance-historical--security)
7. [Key Design Patterns](#7-key-design-patterns)
8. [Related Models & Cross-Module Integration](#8-related-models--cross-module-integration)

---

## 1. Overview

**res.partner** is the foundational model in Odoo's `base` module. Every business object — customer, vendor, employee, company, or individual — is a `res.partner` record. It is the single point of identity management across the entire Odoo ecosystem.

**File location:** `~/odoo/odoo19/odoo/odoo/addons/base/models/res_partner.py`

**Key architectural roles:**
- Identity model for all external entities (customers, suppliers, companies, contacts)
- Commercial entity abstraction (parent/child hierarchy with `commercial_partner_id`)
- Address format management via `format.address.mixin`
- Avatar/photo management via `avatar.mixin`
- Properties support via `properties.base.definition.mixin`

**Mixins inherited:**
```python
class ResPartner(models.Model):
    _inherit = [
        'format.address.mixin',   # Country-specific address formatting
        'format.vat.label.mixin', # Country-specific VAT label rendering
        'avatar.mixin',           # Image fields (image_1920 through image_192)
        'properties.base.definition.mixin',  # Properties/fields inheritance
    ]
```

---

## 2. Module Classification

| Aspect | Value |
|--------|-------|
| Module name | `base` |
| Model technical name | `res.partner` |
| Model description | `Contact` |
| Table name | `res_partner` |
| Inherits | `format.address.mixin`, `format.vat.label.mixin`, `avatar.mixin`, `properties.base.definition.mixin` |
| Is population | Yes (core, installed by default) |
| Has `mail.thread` | No (added by `mail` module extension) |
| Has `activity` | No (added by `mail` module extension) |

---

## 3. L1 — All Fields & Method Signatures

### 3.1 Constants & Module-Level Declarations

```python
ADDRESS_FIELDS = ('street', 'street2', 'zip', 'city', 'state_id', 'country_id')

EU_EXTRA_VAT_CODES = {
    'GR': 'EL',  # Greece VAT prefix changed in EU
    'GB': 'XI',  # Northern Ireland post-Brexit
}

# Timezone list for Selection field — POSIX 'Etc/*' entries sorted last
_tzs = [(tz, tz) for tz in sorted(pytz.all_timezones, key=lambda tz: tz if not tz.startswith('Etc/') else '_')]
```

### 3.2 ResPartnerCategory — Partner Tags Model

```python
class ResPartnerCategory(models.Model):
    _name = 'res.partner.category'
    _description = 'Partner Tags'
    _order = 'name, id'
    _parent_store = True          # Enables child_of operator in searches

    name = fields.Char('Name', required=True, translate=True)
    color = fields.Integer(string='Color', default=_get_default_color, aggregator=False)
    parent_id: ResPartnerCategory = fields.Many2one(
        'res.partner.category',
        string='Category',
        index=True,
        ondelete='cascade'
    )
    child_ids: ResPartnerCategory = fields.One2many(
        'res.partner.category',
        'parent_id',
        string='Child Tags'
    )
    active = fields.Boolean(default=True)
    parent_path = fields.Char(index=True)  # Materialized path for hierarchy queries
    partner_ids: ResPartner = fields.Many2many(
        'res.partner',
        column1='category_id',
        column2='partner_id',
        string='Partners',
        copy=False
    )
```

### 3.3 ResPartnerIndustry — Industry Classification

```python
class ResPartnerIndustry(models.Model):
    _name = 'res.partner.industry'
    _description = 'Industry'
    _order = "name, id"

    name = fields.Char('Name', translate=True)
```

### 3.4 ResPartner — Contact Model

```python
class ResPartner(models.Model):
    _name = 'res.partner'
    _description = 'Contact'
    _inherit = [
        'format.address.mixin',
        'format.vat.label.mixin',
        'avatar.mixin',
        'properties.base.definition.mixin',
    ]
    _order = "complete_name ASC, id DESC"
    _rec_names_search = [
        'complete_name', 'email', 'ref', 'vat', 'company_registry'
    ]
    _allow_sudo_commands = False      # Prevents RPC sudo() abuse
    _check_company_auto = True        # Automatic company check on writes
    _check_company_domain = models.check_company_domain_parent_of

    # Display types whose label gets prepended in complete_name
    _complete_name_displayed_types = ('invoice', 'delivery', 'other')

    # --- IDENTITY FIELDS ---
    name = fields.Char(index=True, default_export_compatible=True)
    complete_name = fields.Char(compute='_compute_complete_name', store=True, index=True)

    # --- COMPANY/PERSON HIERARCHY ---
    is_company = fields.Boolean(
        string='Is a Company',
        default=False,
        help="Check if the contact is a company, otherwise it is a person"
    )
    company_type = fields.Selection(
        string='Company Type',
        selection=[('person', 'Person'), ('company', 'Company')],
        compute='_compute_company_type',
        inverse='_write_company_type'
    )

    # --- PARENT/CHILD RELATIONSHIP ---
    parent_id: ResPartner = fields.Many2one(
        'res.partner',
        string='Related Company',
        index=True,
        domain=[('is_company', '=', True)]
    )
    parent_name = fields.Char(related='parent_id.name', readonly=True, string='Parent name')
    child_ids: ResPartner = fields.One2many(
        'res.partner',
        'parent_id',
        string='Contact',
        domain=[('active', '=', True)],
        context={'active_test': False}
    )

    # --- COMMERCIAL ENTITY ---
    commercial_partner_id: ResPartner = fields.Many2one(
        'res.partner',
        string='Commercial Entity',
        compute='_compute_commercial_partner',
        store=True,
        recursive=True,    # Triggers recursive recomputation
        index=True
    )
    commercial_company_name = fields.Char(
        'Company Name Entity',
        compute='_compute_commercial_company_name',
        store=True
    )
    company_name = fields.Char('Company Name')  # Stored when person has parent

    # --- ADDRESS FIELDS ---
    street = fields.Char()
    street2 = fields.Char()
    zip = fields.Char(change_default=True)
    city = fields.Char()
    state_id: ResCountryState = fields.Many2one(
        "res.country.state",
        string='State',
        ondelete='restrict',
        domain="[('country_id', '=?', country_id)]"  # Optional domain
    )
    country_id: ResCountry = fields.Many2one(
        'res.country',
        string='Country',
        ondelete='restrict'
    )
    country_code = fields.Char(related='country_id.code', string="Country Code")
    contact_address = fields.Char(
        compute='_compute_contact_address',
        string='Complete Address'
    )
    type_address_label = fields.Char(
        'Address Type Description',
        compute='_compute_type_address_label'
    )

    # --- CONTACT TYPE ---
    type = fields.Selection(
        [('contact', 'Contact'),
         ('invoice', 'Invoice'),
         ('delivery', 'Delivery'),
         ('other', 'Other')],
        string='Address Type',
        default='contact'
    )

    # --- NAME/IDENTIFICATION ---
    ref = fields.Char(string='Reference', index=True)
    vat = fields.Char(
        string='Tax ID',
        index=True,
        help="The Tax Identification Number. Values here will be validated "
             "based on the country format. You can use '/' to indicate that "
             "the partner is not subject to tax."
    )
    vat_label = fields.Char(string='Tax ID Label', compute='_compute_vat_label')
    company_registry = fields.Char(
        string="Company ID",
        compute='_compute_company_registry',
        store=True,
        readonly=False,
        index='btree_not_null',
        help="The registry number of the company. Use it if it is different "
             "from the Tax ID. It must be unique across all partners of a "
             "same country"
    )
    company_registry_label = fields.Char(
        string='Company ID Label',
        compute='_compute_company_registry_label'
    )
    company_registry_placeholder = fields.Char(
        compute='_compute_company_registry_placeholder'
    )
    barcode = fields.Char(
        help="Use a barcode to identify this contact.",
        copy=False,
        company_dependent=True
    )

    # --- COMMUNICATION ---
    phone = fields.Char()
    email = fields.Char()
    email_formatted = fields.Char(
        'Formatted Email',
        compute='_compute_email_formatted',
        help='Format email address "Name <email@domain>"'
    )
    website = fields.Char('Website Link')
    comment = fields.Html(string='Notes')

    # --- USER/EMPLOYEE ---
    user_ids: ResUsers = fields.One2many(
        'res.users',
        'partner_id',
        string='Users',
        bypass_search_access=True
    )
    main_user_id: ResUsers = fields.Many2one(
        "res.users",
        string="Main User",
        compute="_compute_main_user_id",
        help="There can be several users related to the same partner. "
             "When a single user is needed, this field attempts to find "
             "the most appropriate one."
    )
    user_id: ResUsers = fields.Many2one(
        'res.users',
        string='Salesperson',
        compute='_compute_user_id',
        precompute=True,
        readonly=False,
        store=True,
        help='The internal user in charge of this contact.'
    )

    # --- CLASSIFICATION ---
    category_id: ResPartnerCategory = fields.Many2many(
        'res.partner.category',
        column1='partner_id',
        column2='category_id',
        string='Tags',
        default=lambda self: self._default_category()
    )
    industry_id = fields.Many2one(
        'res.partner.industry',
        'Industry'
    )
    function = fields.Char(string='Job Position')

    # --- GEO ---
    partner_latitude = fields.Float(string='Geo Latitude', digits=(10, 7))
    partner_longitude = fields.Float(string='Geo Longitude', digits=(10, 7))

    # --- FINANCIAL/ACCESS ---
    partner_share = fields.Boolean(
        'Share Partner',
        compute='_compute_partner_share',
        store=True,
        help="Either customer (not a user), either shared user. "
             "Indicates the current partner is a customer without access "
             "or with a limited access created for sharing data."
    )

    # --- LANGUAGE/TIMEZONE ---
    lang = fields.Selection(
        _lang_get,
        string='Language',
        compute='_compute_lang',
        readonly=False,
        store=True,
        help="All the emails and documents sent to this contact will be "
             "translated in this language."
    )
    active_lang_count = fields.Integer(compute='_compute_active_lang_count')
    tz = fields.Selection(
        _tzs,
        string='Timezone',
        default=lambda self: self.env.context.get('tz'),
        help="When printing documents and exporting/importing data, time "
             "values are computed according to this timezone. If not set, "
             "UTC is used. Anywhere else, time values are computed "
             "according to the time offset of your web client."
    )
    tz_offset = fields.Char(compute='_compute_tz_offset', string='Timezone offset')

    # --- COMPANY ---
    company_id: ResCompany = fields.Many2one(
        'res.company',
        'Company',
        index=True
    )

    # --- BANK ---
    bank_ids: ResPartnerBank = fields.One2many(
        'res.partner.bank',
        'partner_id',
        string='Banks'
    )

    # --- IMAGE/AVATAR ---
    # Provided by avatar.mixin (inherited):
    # image_1920, image_1024, image_512, image_256, image_128
    # avatar_1920, avatar_1024, avatar_512, avatar_256, avatar_128
    # (compute based on user_ids.share, image_1920, is_company, type)

    # --- STATE/FLAGS ---
    active = fields.Boolean(default=True)
    employee = fields.Boolean(help="Check this box if this contact is an Employee.")
    is_public = fields.Boolean(
        compute='_compute_is_public',
        compute_sudo=True
    )
    color = fields.Integer(string='Color Index', default=0)

    # --- TECHNICAL ---
    # hack to allow using plain browse record in qweb views, used in ir.qweb.field.contact
    self: ResPartner = fields.Many2one(
        comodel_name='res.partner',
        compute='_compute_get_ids'
    )
    application_statistics = fields.Json(
        string="Stats",
        compute="_compute_application_statistics"
    )

    # --- DUPLICATE DETECTION ---
    same_vat_partner_id: ResPartner = fields.Many2one(
        'res.partner',
        string='Partner with same Tax ID',
        compute='_compute_same_vat_partner_id',
        store=False
    )
    same_company_registry_partner_id: ResPartner = fields.Many2one(
        'res.partner',
        string='Partner with same Company Registry',
        compute='_compute_same_vat_partner_id',
        store=False
    )
```

### 3.5 All Method Signatures

#### Mixin Methods

```python
# FormatVatLabelMixin
@api.model
def _get_view(self, view_id=None, view_type='form', **options):
    """Override to inject country-specific VAT label into views."""

# FormatAddressMixin
def _extract_fields_from_address(self, address_line):
    """Parse format string to extract field names."""
def _view_get_address(self, arch):
    """Rewrite address node based on country's address_view_id."""
@api.model
def _get_view_cache_key(self, view_id=None, view_type='form', **options):
    """Cache key includes company to support per-company address views."""
@api.model
def _get_view(self, view_id=None, view_type='form', **options):
    """Inject address formatting into form view architecture."""
```

#### Category Methods

```python
def _get_default_color(self):
    """Return random color 1-11 for new categories."""
@api.constrains('parent_id')
def _check_parent_id(self):
    """Prevent recursive category hierarchies."""
@api.depends('parent_id')
def _compute_display_name(self):
    """Display name includes parent: 'Parent / Child / Grandchild'."""
@api.model
def _search_display_name(self, operator, value):
    """Support 'child_of' operator for hierarchy search."""
```

#### ResPartner — Computed Fields

```python
@api.depends('name', 'user_ids.share', 'image_1920', 'is_company', 'type')
def _compute_avatar_1920(self): ...
@api.depends('name', 'user_ids.share', 'image_1024', 'is_company', 'type')
def _compute_avatar_1024(self): ...
@api.depends('name', 'user_ids.share', 'image_512', 'is_company', 'type')
def _compute_avatar_512(self): ...
@api.depends('name', 'user_ids.share', 'image_256', 'is_company', 'type')
def _compute_avatar_256(self): ...
@api.depends('name', 'user_ids.share', 'image_128', 'is_company', 'type')
def _compute_avatar_128(self): ...
def _compute_avatar(self, avatar_field, image_field):
    """Core avatar computation logic — uses placeholder images for
    partners without image or internal user."""
def _avatar_get_placeholder_path(self):
    """Return placeholder image path based on partner type."""

def _get_complete_name(self):
    """Build full name: 'CompanyName, ContactName' for non-companies."""
@api.depends('is_company', 'name', 'parent_id.name', 'type', 'company_name', 'commercial_company_name')
def _compute_complete_name(self): ...

@api.depends('parent_id')
def _compute_lang(self): ...
@api.depends('lang')
def _compute_active_lang_count(self): ...
@api.depends('tz')
def _compute_tz_offset(self): ...
@api.depends('parent_id')
def _compute_user_id(self): ...
@api.depends_context("uid")
@api.depends("user_ids.active", "user_ids.share")
def _compute_main_user_id(self): ...
@api.depends('user_ids.share', 'user_ids.active')
def _compute_partner_share(self): ...
@api.depends('vat', 'company_id', 'company_registry', 'country_id')
def _compute_same_vat_partner_id(self): ...
@api.depends_context('company')
def _compute_vat_label(self): ...
@api.depends('parent_id', 'type')
def _compute_type_address_label(self): ...
@api.depends(lambda self: self._display_address_depends())
def _compute_contact_address(self): ...
def _compute_get_ids(self): ...
@api.depends('is_company', 'parent_id.commercial_partner_id')
def _compute_commercial_partner(self): ...
@api.depends('company_name', 'parent_id.is_company', 'commercial_partner_id.name')
def _compute_commercial_company_name(self): ...
def _compute_company_registry(self): ...  # exists to allow overrides
@api.depends('country_id')
def _compute_company_registry_label(self): ...
def _get_company_registry_labels(self): ...  # hook for overrides
def _compute_company_registry_placeholder(self): ...
@api.depends('is_company')
def _compute_company_type(self): ...
def _write_company_type(self): ...
@api.depends('name', 'email')
def _compute_email_formatted(self): ...
def _compute_is_public(self): ...
def _compute_application_statistics(self): ...
def _compute_application_statistics_hook(self):
    """Hook for override to add module-specific statistics."""
```

#### ResPartner — Validation Constraints

```python
_check_name = models.Constraint(
    "CHECK( (type='contact' AND name IS NOT NULL) or (type!='contact') )",
    "Contacts require a name",
)
@api.constrains('parent_id')
def _check_parent_id(self):
    """Prevent recursive partner hierarchies."""
@api.constrains('company_id')
def _check_partner_company(self):
    """Verify company on partner matches partner on company."""
@api.constrains('barcode')
def _check_barcode_unicity(self):
    """Ensure barcode uniqueness across all partners."""
```

#### ResPartner — Onchange Methods

```python
@api.onchange('parent_id')
def onchange_parent_id(self):
    """Copy parent address to contact when type='contact'."""
@api.onchange('country_id')
def _onchange_country_id(self):
    """Clear state when country changes."""
@api.onchange('state_id')
def _onchange_state(self):
    """Auto-fill country from state when state changes."""
@api.onchange('parent_id', 'company_id')
def _onchange_company_id(self):
    """Inherit company from parent."""
@api.onchange('company_type')
def onchange_company_type(self):
    """Toggle is_company from company_type selection."""
```

#### ResPartner — CRUD & Business Methods

```python
@api.model
def default_get(self, fields):
    """Add parent company as default when creating child partner."""

def copy_data(self, default=None):
    """Override to append '(copy)' suffix to name."""

def write(self, vals):
    """Handle partner write with:
    - Active user check before archive
    - Website URL cleaning
    - Company_name reset on parent change
    - Bank account holder name sync
    - Company_id validation + child propagation
    - is_company access-right bypass
    - Fields synchronization"""

@api.model_create_multi
def create(self, vals_list):
    """Handle partner creation with:
    - Website URL cleaning
    - Company_name reset on parent
    - Post-create lang sync
    - Post-create fields synchronization"""

@api.ondelete(at_uninstall=False)
def _unlink_except_user(self):
    """Prevent deletion of partners with linked active users."""

def _load_records_create(self, vals_list):
    """Batch-optimized version of create + _fields_sync.
    Groups partners by commercial_partner_id and parent_id to minimize writes."""

def create_company(self):
    """Create parent company from contact (action button)."""
def _create_contact_parent_company(self):
    """Internal method to create parent company."""
def open_commercial_entity(self):
    """Utility method to open commercial partner (action button)."""

# --- NAME SEARCH ---
@api.model
def name_create(self, name):
    """Parse email from name string, create partner with email."""
@api.model
def find_or_create(self, email, assert_valid_email=False):
    """Find existing partner by email, or create new one."""

# --- ADDRESS METHODS ---
def address_get(self, adr_pref=None):
    """Find addresses of specified types using DFS through hierarchy."""

@api.model
def _get_default_address_format(self):
    """Return default format: street\\nstreet2\\ncity state zip\\ncountry"""
@api.model
def _get_address_format(self):
    """Return country-specific address format."""
def _prepare_display_address(self, without_company=False):
    """Build format string and args dict for address rendering."""
def _display_address(self, without_company=False):
    """Return formatted address string using country format."""
def _display_address_depends(self):
    """Return list of fields that affect address display."""
def _get_country_name(self): ...

def _get_all_addr(self): ...

# --- COMMERCIAL FIELDS MANAGEMENT ---
@api.model
def _address_fields(self):
    """Returns list of address field names for synchronization."""
@api.model
def _formatting_address_fields(self):
    """Returns list of fields usable for address formatting."""
def _get_address_values(self): ...
def _update_address(self, vals): ...

@api.model
def _commercial_fields(self):
    """Returns list of commercial field names delegated to commercial entity."""
@api.model
def _synced_commercial_fields(self):
    """Returns list of commercial fields that sync upstream (to parent)."""
def _get_commercial_values(self): ...
def _get_synced_commercial_values(self): ...
@api.model
def _company_dependent_commercial_fields(self): ...

def _commercial_sync_from_company(self): ...
def _company_dependent_commercial_sync(self): ...
def _commercial_sync_to_descendants(self, fields_to_sync=None): ...
def _fields_sync(self, values): ...
def _children_sync(self, values): ...
def _handle_first_contact_creation(self): ...
def _clean_website(self, website): ...
def _convert_fields_to_values(self, field_names): ...

# --- SEARCH & DISPLAY ---
@api.depends('complete_name', 'email', 'vat', 'state_id', 'country_id',
             'commercial_company_name')
@api.depends_context(
    'show_address', 'partner_show_db_id',
    'show_email', 'show_vat', 'lang', 'formatted_display_name'
)
def _compute_display_name(self): ...

@api.model
def view_header_get(self, view_id, view_type): ...

@api.model
def get_import_templates(self): ...
@api.model
def _check_import_consistency(self, vals_list): ...
```

---

## 4. L2 — Field Types, Defaults, Constraints, Purpose

### 4.1 Core Identity Fields

#### `name` — Char
- **Type:** Char (string)
- **Default:** None (no default)
- **Index:** `index=True`
- **Constraint:** `CHECK(type='contact' AND name IS NOT NULL)` — only contacts require a name. Other types (invoice, delivery, other) can have null names as they inherit from parent.
- **Purpose:** Primary identifier. Used as `_rec_name` (default). Searchable via `name_create()` which can parse email addresses.
- **L4 Note:** `default_export_compatible=True` — this field is included in CSV exports by default.

#### `is_company` — Boolean
- **Default:** `False`
- **Constraint:** Cannot be `True` for a partner that has a `parent_id` pointing to another partner (inherited via `_check_company_domain`).
- **Purpose:** Distinguishes company entities (legal persons) from natural persons. Affects avatar selection, complete name computation, commercial partner resolution, and the company_type interface field.
- **Write protection:** Writing to `is_company` requires either `self.env.su` (superuser) or the user being in `base.group_partner_manager`. This is enforced in the `write()` method, not via field-level groups.

#### `company_type` — Selection (Interface)
- **Values:** `('person', 'Person')`, `('company', 'Company')`
- **Default:** None (computed from `is_company`)
- **Purpose:** User-friendly interface to toggle `is_company`. The `_compute_company_type` and `_write_company_type` inverse methods do the actual mapping between the two fields.
- **UI Pattern:** Often displayed as a radio button or toggle in partner forms. When user changes `company_type`, it sets `is_company` accordingly.

### 4.2 Parent/Child Hierarchy

#### `parent_id` — Many2one
- **Type:** `res.partner` (self-referential)
- **Index:** `index=True`
- **Domain:** Implicit `[('is_company', '=', True)]` (only companies can be parents)
- **Constraint:** `_check_parent_id` — prevents recursive hierarchies. Uses `_has_cycle()` inherited from `models.BaseModel`. The `CHECK(company_id)` also prevents cross-company parent cycles via `_check_company_domain_parent_of`.
- **Purpose:** Links a person/contact to their employing or associated company. When set on a non-company, `company_name` is cleared.

#### `child_ids` — One2many
- **Type:** Inverse of `parent_id`
- **Domain:** `[('active', '=', True)]` — only active children visible by default
- **Context:** `{'active_test': False}` — raw access to all children (active and inactive)
- **Purpose:** Lists all contacts that belong to a company. Only contacts (`is_company=False`) should appear here.

#### `commercial_partner_id` — Computed Many2one (Recursive)
- **Type:** `res.partner` pointing to the topmost company in the hierarchy
- **Store:** `store=True`
- **Recursive:** `recursive=True` — Odoo's ORM marks this field as requiring special recomputation handling
- **Index:** `index=True`
- **Computation logic:**
  ```python
  if partner.is_company or not partner.parent_id:
      commercial_partner_id = partner  # Self-reference for companies or root
  else:
      commercial_partner_id = partner.parent_id.commercial_partner_id  # Traverse up
  ```
- **L4 Cache:** Uses Odoo's `ormcache` via the ORM's recursive field mechanism. The `store=True` ensures database-level persistence, avoiding recursive recomputation on every access.

#### `commercial_company_name` — Computed Char
- **Store:** `store=True`
- **Logic:** Returns the commercial entity's `name` if it is a company, otherwise returns the child partner's `company_name`.
- **Purpose:** Used in address formatting to show the correct company name.

#### `company_name` — Char
- **Purpose:** Stores the company name for a person who is not yet linked to a company partner. When `parent_id` is set, this field is cleared. Used by `create_company()` to bootstrap the parent company.

### 4.3 Address Fields

#### `ADDRESS_FIELDS` Tuple
```python
ADDRESS_FIELDS = ('street', 'street2', 'zip', 'city', 'state_id', 'country_id')
```

#### `street`, `street2`, `city`, `zip` — Char
- Basic address components without explicit defaults.
- `zip` has `change_default=True` — changing this field triggers default value lookup for the new value.

#### `state_id` — Many2one (res.country.state)
- **ondelete:** `restrict` — cannot delete a state if partners reference it
- **Domain:** `[('country_id', '=?', country_id)]` — optional domain. The `=?` operator makes it conditional: the domain is only applied if `country_id` is truthy (non-False/Non). This allows the state dropdown to show all states when no country is selected.

#### `country_id` — Many2one (res.country)
- **ondelete:** `restrict`
- **Purpose:** Determines address format, VAT validation rules, state domain, and company registry label.

#### `country_code` — Related Char
- **Related:** `country_id.code`
- **Purpose:** Quick access to ISO country code without traversing the full relation.

#### `contact_address` — Computed Char
- **Depends:** All `_formatting_address_fields()` + `'country_id', 'company_name', 'state_id'`
- **Purpose:** Returns the complete formatted address string. Used in reports, documents, and the `street故居` legacy field compatibility.

### 4.4 Contact Type System

#### `type` — Selection
- **Values and purposes:**

| Value | Label | Purpose |
|-------|-------|---------|
| `contact` | Contact | General-purpose contact, inherits address from parent company |
| `invoice` | Invoice | Dedicated billing address, used by `address_get()` |
| `delivery` | Delivery | Dedicated shipping address, used by `address_get()` |
| `other` | Other | Generic purpose, used by `address_get()` |

- **Default:** `'contact'`
- **Constraint:** `CHECK(type='contact' AND name IS NOT NULL)` — contact-type partners MUST have a name.
- **Display name impact:** The `_complete_name_displayed_types = ('invoice', 'delivery', 'other')` means these three types prepend their label in the complete name when displayed as a child of a company (e.g., "Acme Corp - John Smith (Invoice)").

### 4.5 Partner Classification Fields

#### `category_id` — Many2many (res.partner.category)
- **Relation table:** `res_partner_category_rel` (auto-generated)
- **Default:** `_default_category()` — returns category from context key `category_id`
- **Purpose:** Tags for grouping/filtering partners. Supports hierarchical categories via `parent_id` on the category model.
- **Copy:** `copy=False` — tags are not duplicated when partner is duplicated.

#### `industry_id` — Many2one (res.partner.industry)
- **Purpose:** Industry classification (e.g., "Information Technology", "Manufacturing"). Used in reporting and segmentation.

#### `function` — Char
- **Purpose:** Job title/position (e.g., "CEO", "Sales Manager"). Used in address formatted display.

### 4.6 Communication Fields

#### `email` — Char
- **No validation** at field level — use `mail` module's email validation or `phone_validation` for enforcement.
- **Normalization:** `email_formatted` uses `tools.email_normalize_all()` which handles multiple emails, normalization, and format validation.

#### `email_formatted` — Computed Char
- **Format:** `"Name <email@domain.com>"`
- **Logic:**
  1. Normalize all emails using `email_normalize_all()`
  2. If valid normalized emails found, format with `formataddr()`
  3. If raw email exists but normalization fails, use raw email
  4. If no email, set to `False`
- **Handles:** Double-formatting prevention, multi-email preservation, invalid email retention.

#### `website` — Char
- **Cleaned on write:** `_clean_website()` adds `http://` scheme if missing. Uses `werkzeug.urls.url_parse`.

### 4.7 User/Employee Fields

#### `user_ids` — One2many (res.users)
- **Inverse:** `partner_id` on `res.users`
- **Purpose:** Links system users to their partner record. A partner can have multiple users (e.g., portal + internal user).
- **Bypass:** `bypass_search_access=True` — allows searching without full access rights (technical field).
- **L4 Note:** When partner is archived, the system checks for active linked users and raises `RedirectWarning` or `ValidationError` depending on caller access rights.

#### `main_user_id` — Computed Many2one
- **Depends:** `user_ids.active`, `user_ids.share`
- **Logic:**
  1. If current user is linked to this partner, return current user
  2. Otherwise, return first active user sorted by: internal users first (`share=False`), then by ID descending (newest first)
  3. Special case: `partner_root` (ODOOBOT) returns `user_root`
- **Purpose:** Provides a single "primary" user for scenarios where only one user is expected.

#### `user_id` — Computed Many2one (res.users)
- **Compute:** `_compute_user_id` — syncs `user_id` from parent for persons
- **Precompute:** `precompute=True` — computed at create time without triggering post-create recomputation
- **Purpose:** The "salesperson" field — the internal user responsible for this contact.

### 4.8 Partner Share & Access Control

#### `partner_share` — Computed Boolean
- **Store:** `store=True`
- **Logic:**
  ```python
  partner_share = not partner.user_ids or not any(
      not user.share for user in partner.user_ids
  )
  ```
  - `True` if: partner has no users, OR all users are portal/share users
  - `False` if: partner has at least one internal user
- **Purpose:** Distinguishes customer partners (no internal system access) from internal partners. Used by `portal` module to control document sharing.

### 4.9 Image/Avatar Fields (via avatar.mixin)

The `avatar.mixin` provides five image fields and five computed avatar fields:

| Image Field | Avatar Field | Storage |
|-------------|-------------|---------|
| `image_1920` | `avatar_1920` | Full 1920px |
| `image_1024` | `avatar_1024` | 1024px |
| `image_512` | `avatar_512` | 512px |
| `image_256` | `avatar_256` | 256px |
| `image_128` | `avatar_128` | 128px |

**Avatar computation logic (`_compute_avatar`):**
1. Partners with internal users OR type='contact' get the partner's own image
2. Partners without image get a placeholder based on type:
   - `is_company=True` → `base/static/img/company_image.png`
   - `type='delivery'` → `base/static/img/truck.png`
   - `type='invoice'` → `base/static/img/bill.png`
   - `type='other'` → `base/static/img/puzzle.png`
   - Default → inherited from `avatar.mixin` (person icon)

### 4.10 VAT & Company Registry

#### `vat` — Char
- **Index:** `index=True`
- **Validation:** Country-specific validation is done by `base_vat` module. The base field itself has no built-in format validation.
- **Help text:** `vat_label` is shown instead based on country (`_compute_vat_label` reads `company.country_id.vat_label`).
- **EU VAT handling:** `_compute_same_vat_partner_id` handles EU VAT prefix variations (GR→EL, GB→XI).

#### `company_registry` — Char
- **Index:** `'btree_not_null'` — partial B-tree index for null-excluded searches
- **Company-dependent:** Each company can set different labels via country settings
- **Constraint:** Not enforced at DB level; duplicates allowed across different countries.

---

## 5. L3 — Edge Cases

### 5.1 Parent/Child Relationship Edge Cases

**Edge case: Setting parent on a company**
A partner with `is_company=True` cannot have a `parent_id` set. The `_check_company_domain` constraint on the model enforces this: a company cannot be the child of another partner.

**Edge case: Circular hierarchy**
`_check_parent_id` calls `_has_cycle()` which detects recursive parent chains. For example, if A.parent_id = B and B.parent_id = A, the constraint raises `ValidationError(_('You cannot create recursive Partner hierarchies.'))`.

**Edge case: First contact creation**
When a company has no address but a child contact is created with an address, `_handle_first_contact_creation()` copies the contact's address to the company. This handles the common pattern where users create a contact first and later realize it should be the company.

**Edge case: Orphaned children when parent is archived**
Archiving a company does NOT automatically archive its children. The `active` field is independent. Children remain active and visible unless explicitly archived.

**Edge case: Parent change**
When `parent_id` changes, `company_name` is cleared (`write()` line 868). The new parent relationship triggers full commercial field and address synchronization.

### 5.2 Commercial Partner Computation Edge Cases

**Edge case: Orphaned company (is_company=True, no parent)**
Returns `self` — the company is its own commercial entity.

**Edge case: Deep hierarchy traversal**
A person → company A → company B → ... → company N chain all resolve to company N as the commercial entity. The recursive field ensures this chain is followed to the root.

**Edge case: Stored but must recompute on hierarchy change**
The `recursive=True` parameter tells the ORM to mark dependent records (`child_ids`) for recomputation when the commercial partner changes. When company A's VAT changes, all child contacts' `commercial_partner_id` correctly point to A (already stored), but the commercial fields (vat) on children are updated via `_commercial_sync_to_descendants()`.

### 5.3 Address Field Synchronization Edge Cases

**Edge case: Address sync from company to contact**
Only contacts (`type='contact'`) inherit address from the parent company. Invoice, delivery, and other types have independent addresses.

**Edge case: Bidirectional sync**
When a contact's address changes, the new address propagates BACK to the parent company ONLY if:
1. Contact is type='contact'
2. `parent_id` is set
3. At least one address field is different between contact and parent

This bidirectional sync is managed by `_fields_sync()`.

**Edge case: State/country mismatch prevention**
`_onchange_country_id` clears `state_id` if the new country doesn't match the state's country. `_onchange_state` auto-fills `country_id` from the state.

**Edge case: Country-specific address format**
`_view_get_address()` dynamically rewrites the form view architecture based on `company.country_id.address_view_id`. This allows different countries to have different address field layouts (e.g., some countries don't use street2, some use house number separately).

### 5.4 Duplicate Detection Edge Cases

**Edge case: EU VAT variations**
`_compute_same_vat_partner_id` handles the Greek VAT prefix change (`GR` → `EL`) and Northern Ireland post-Brexit prefix (`GB` → `XI`). It builds a list of equivalent VAT numbers and searches for any match.

**Edge case: Vies validation**
`check_vat_*` methods in `base_vat` module perform VIES web service calls. The base field only supports exact and prefix-variation matching.

**Edge case: Parent-child duplicate check**
The domain includes `'!', ('id', 'child_of', partner_id)` to exclude the partner and all its descendants from the duplicate check. This prevents false positives when a company and its contacts share the same VAT.

### 5.5 User/Partner Link Edge Cases

**Edge case: Multiple users per partner**
`main_user_id` resolves the "which user?" ambiguity by preferring internal users over portal users, and newer users over older ones.

**Edge case: Archived users**
`main_user_id` only considers `active=True` users. Archived users are excluded from the computation.

**Edge case: Self-partner matching**
`_compute_main_user_id` has special logic: if `self.env.user.partner_id == partner`, immediately return `self.env.user` (the current user). This ensures the logged-in user always sees themselves as the main user of their own partner record.

**Edge case: Odoobot partner**
The `partner_root` (ODOOBOT) is a special case: it has no active user normally, but `main_user_id` resolves it to `user_root` (the super-admin).

### 5.6 Import/Export Edge Cases

**Edge case: Inconsistent state during import**
`_check_import_consistency()` validates that imported `state_id` values actually belong to the imported `country_id`. If mismatched, it searches for a state with the same code in the correct country and replaces the value.

**Edge case: name_create with email parsing**
`name_create()` uses `tools.parse_contact_from_email()` to split "John Doe <john@example.com>" into name and email. If only an email is provided, the name becomes the email address.

### 5.7 Active/Inactive Partner Edge Cases

**Edge case: Searching inactive partners**
The `child_ids` domain `[('active', '=', True)]` hides inactive children in the standard display. However, `context={'active_test': False}` allows accessing inactive children when needed.

**Edge case: Deactivating partner with linked users**
`write()` with `active=False` triggers a check for active linked users. If found, raises `RedirectWarning` (for users with write access) or `ValidationError` (for non-privileged users), directing them to the user form.

### 5.8 Company-Dependent Fields Edge Cases

**Edge case: Barcode company dependency**
`barcode` has `company_dependent=True`. This means the same partner can have different barcodes for different companies. The uniqueness constraint checks across all partners regardless of company.

---

## 6. L4 — Performance, Historical & Security

### 6.1 Performance Implications

#### commercial_partner_id — Stored Recursive Field

**The `store=True, recursive=True` combination** is critical for performance:
- Without `store=True`, every access to `commercial_partner_id` would traverse the parent chain recursively.
- With `store=True` but no `recursive=True`, the ORM would compute it once at create time but never update descendants when the commercial entity changes.
- The `recursive=True` flag tells the ORM's invalidation system to mark all descendants for recomputation when the commercial entity is modified.

**In practice:** When you change `vat` on a company, `_commercial_sync_to_descendants()` propagates the change without needing to recompute `commercial_partner_id` (which is already stored correctly). The `vat` is synced via `_synced_commercial_fields()`.

#### _load_records_create — Batch Optimization

The `_load_records_create()` method (used during data import/loading) batches the synchronization logic:
```python
# Groups partners by (commercial_partner_id, parent_id) tuples
groups = collections.defaultdict(list)
for partner, vals in zip(partners, vals_list):
    groups[(cp_id, add_id)].append(partner.id)

# Single write per group instead of N writes
for (cp_id, add_id), children in groups.items():
    self.sudo().browse(children).write(to_write)
```
This reduces O(N) write operations to O(G) where G is the number of unique parent/commercial groups.

#### Avatar Computation

`_compute_avatar()` has two code paths:
1. **With image:** Directly assigns the image field value to the avatar field (fast, in-memory).
2. **Without image:** Groups partners by placeholder path, then encodes and assigns in batch. The `tools.groupby()` + `concat(*group)` pattern ensures only one base64 encoding per unique placeholder per batch.

#### partner_share — Store for Performance

`partner_share` is stored because it is used in `portal` module's record rules (`'partner_share': True` domain). Storing it avoids recomputation on every access check.

#### complete_name — Store + Index

`complete_name` has both `store=True` and `index=True`. This enables:
- Fast sorting in the list view (`_order = "complete_name ASC, id DESC"`)
- Fast filtering by name prefix

#### company_registry — btree_not_null Index

```python
company_registry = fields.Char(index='btree_not_null', ...)
```
This creates a PostgreSQL partial index: `CREATE INDEX ... WHERE company_registry IS NOT NULL`. It speeds up `WHERE company_registry = '...'` queries without consuming index space for the many null values.

#### Email Normalization

`email_normalize_all()` is called in `_compute_email_formatted`. For partners without email, the field short-circuits immediately. For the common case of single-email partners, normalization overhead is minimal.

### 6.2 Odoo 18 to Odoo 19 Changes

The following changes were introduced between Odoo 18 and 19 in `res_partner`:

| Change | Description |
|--------|-------------|
| `signup_token`, `signup_type`, `signup_expiration` removed | These fields were part of the auth_signup flow. In Odoo 19, they are no longer stored on `res.partner` directly — token management moved to `res.users` or the auth_signup module. |
| `last_employee_id` removed | This field was used by HR for tracking last employee added. No longer present in Odoo 19. |
| `responsible_id` removed | Field removed from base. Responsibility tracking now handled via `user_id` (salesperson). |
| `_display_name` override significantly expanded | The `display_name` computation now supports context-driven formatting with `show_email`, `show_address`, `show_vat`, `partner_show_db_id`, `formatted_display_name`. |
| `address_get()` algorithm unchanged | DFS through descendants, then ancestors, remains the same. |
| `find_or_create()` email comparison changed | Changed from `email` to `email,=ilike` (case-insensitive exact match) for more precise matching. |
| `_complete_name_displayed_types` introduced | Extracted as class attribute for extensibility. |
| `_lang_get` now uses `res.lang.get_installed()` | Dynamic language list from installed languages. |
| `application_statistics` field added | JSON field with hook `_compute_application_statistics_hook` for module-specific statistics. |
| `image_mixin` replaced by `avatar.mixin` | Image storage now uses `avatar.mixin` with multiple resolutions. |
| `partner_share` computation unchanged | Still `not any(not user.share for user in partner.user_ids)`. |
| `main_user_id` introduced | New field to resolve the ambiguity of multiple users per partner. |
| `_rec_names_search` extended | Now includes `company_registry` alongside `complete_name`, `email`, `ref`, `vat`. |

### 6.3 Historical Context

#### Why `commercial_partner_id` Exists

In Odoo versions before the commercial entity concept, all commercial fields (VAT, credit limit, property fields) had to be manually kept in sync across a company's contacts. The `commercial_partner_id` abstraction ensures that all contacts under a company share the same commercial data. This is fundamental to:
- Correct fiscal position determination (based on commercial partner's country)
- Credit limit checks (based on commercial partner)
- Property field resolution (`ir.property` looks at `commercial_partner_id`)

#### Why `address_get()` Uses DFS

The depth-first search algorithm for `address_get()` prioritizes finding addresses of the right type within the closest descendants first. This means if a company has multiple contacts of type 'invoice', the algorithm finds the first matching contact in the company's subtree before moving to parent companies. This matches the typical business expectation of "the billing department contact" before "the parent company's billing address."

#### The `street故居` Field

The `_display_address()` method includes a placeholder for `street故居` (street name in Chinese/Asian address formats where the name comes before the number). This field name with Chinese characters in the source code is part of Odoo's internationalization support for address formatting in East Asian countries.

### 6.4 Security Concerns

#### Access Control on is_company

Writing to `is_company` requires either:
1. Superuser mode (`self.env.su`), OR
2. Membership in `base.group_partner_manager`

This prevents regular users from converting companies to persons or vice versa without proper authorization. The check is in `write()`:
```python
if 'is_company' in vals and not self.env.su and \
        self.env.user.has_group('base.group_partner_manager'):
    result = super(ResPartner, self.sudo()).write({'is_company': ...})
```

#### partner_share and Portal Access

`partner_share = True` indicates a partner is either:
1. A customer with no system user, OR
2. A partner whose only system users are portal/share users

The `portal` module uses this field in record rules to share documents with customers. Misconfiguring this field could expose internal documents to external parties.

#### Unlinking Partners with Users

The `_unlink_except_user()` method prevents deletion of partners linked to active users. This prevents orphaned user records and maintains referential integrity.

#### SQL Injection

All database operations use the ORM (`search()`, `write()`, `create()`). No raw SQL with string concatenation. The only potential raw SQL usage would be through `tools.street_split()` but that function does not interact with the database.

#### website Field XSS

`_clean_website()` uses `werkzeug.urls.url_parse()` which only manipulates URL components safely. The URL is never rendered back into HTML without escaping in templates, so XSS risk is low.

#### VIES/Tax Validation

VAT validation via `base_vat` module's VIES web service calls are server-side and do not expose credentials or create client-side vulnerabilities.

---

## 7. Key Design Patterns

### 7.1 Commercial Fields Pattern

Odoo's commercial entity pattern uses three layers:

1. **Commercial fields** (`_commercial_fields()`): Fields that belong to the commercial entity. On a contact, these are "owned" by the parent company. On a company, they are owned by the company itself. Examples: `industry_id`, `company_registry`.

2. **Synced commercial fields** (`_synced_commercial_fields()`): A subset of commercial fields that propagate UPWARD from children to the commercial entity. Only `vat` is in this category. When a contact's VAT changes, it propagates to the parent company.

3. **Address fields** (`_address_fields()`): Fields that sync DOWNWARD from the commercial entity to contacts of type 'contact'. Examples: `street`, `city`, `country_id`.

The synchronization is triggered in `write()` via `_fields_sync()` and in `create()` via `_fields_sync()` called after record creation.

### 7.2 The _fields_sync() State Machine

`_fields_sync()` is called after every successful `write()`. It implements a three-phase synchronization:

```
Phase 1 (UPSTREAM from parent):
  - commercial_partner_id changed? → sync commercial fields FROM parent
  - parent_id changed and type='contact'? → sync address FROM parent

Phase 2 (UPSTREAM to parent):
  - contact address changed? → write address TO parent
  - synced commercial field changed? → write to commercial_partner_id (parent)

Phase 3 (DOWNSTREAM to children):
  - company changed? → sync commercial fields and address TO children
```

### 7.3 Avatar Selection Pattern

The avatar mixin computes different images based on context:
- Internal users see the partner's uploaded image
- Portal users see a placeholder
- Companies get the company placeholder
- Invoice/delivery/other contacts get type-specific placeholders

This is computed via `_compute_avatar()` which uses `groupby()` for efficiency when dealing with multiple partners.

### 7.4 Address Format Pattern

Country-specific address formatting works at two levels:
1. **Field layout** (`_view_get_address`): Replaces the address form section with a country-specific view (configured via `res.country.address_view_id`)
2. **Text format** (`_display_address`): Uses the country-specific format string to render the address as text

The format string uses Python's `%`-formatting with named placeholders:
```
"%(street)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s"
```

### 7.5 Name Resolution Pattern

Odoo resolves partner names through several layers:
1. `name` field (primary)
2. `display_name` computed field (uses `_get_complete_name()`)
3. `complete_name` stored computed field (full "Company, Contact" format)
4. `name_search()` / `name_create()` for quick creation

The `_rec_names_search` list determines which fields are searched when using `name_search()`:
```python
_rec_names_search = ['complete_name', 'email', 'ref', 'vat', 'company_registry']
```

---

## 8. Related Models & Cross-Module Integration

### 8.1 Direct Model Relations

| Related Model | Field on res.partner | Type | Purpose |
|---------------|---------------------|------|---------|
| `res.users` | `user_ids` | One2many | Link system users to partner |
| `res.partner.bank` | `bank_ids` | One2many | Bank accounts |
| `res.partner.category` | `category_id` | Many2many | Tags |
| `res.partner.industry` | `industry_id` | Many2one | Industry classification |
| `res.country` | `country_id` | Many2one | Country |
| `res.country.state` | `state_id` | Many2one | State/province |
| `res.company` | `company_id` | Many2one | Operating company |
| `res.lang` | `lang` | Selection | Language |
| `res.city` (base_address_extended) | `city_id` | Many2one | City with postal data |

### 8.2 Extended by Other Modules

| Module | Extension Type | Key Additions |
|--------|---------------|---------------|
| `base_address_extended` | Model inherit | `street_name`, `street_number`, `street_number2`, `city_id` |
| `base_vat` | Model inherit | VAT validation methods (`check_vat`, `check_vat_es`, etc.) |
| `base_geolocalize` | Model inherit | `geo_localize()` method |
| `mail` | Model inherit | `message_post()`, `message_subscribe()` |
| `portal` | Model inherit | Portal-specific record sharing |
| `crm` | Inherit | CRM leads from partners |
| `sale` | Inherit | `sale_order_count`, `sale_order_ids` |
| `purchase` | Inherit | `purchase_order_count`, `supplier_rank` |
| `account` | Inherit | `property_account_receivable_id`, `property_account_payable_id` |
| `stock` | Inherit | Delivery addresses |

### 8.3 base_address_extended Fields (When Installed)

The `base_address_extended` module adds these computed/inverse fields:

```python
street_name = fields.Char(
    'Street Name',
    compute='_compute_street_data',
    inverse='_inverse_street_data',
    store=True
)
street_number = fields.Char('House', ...)
street_number2 = fields.Char('Door', ...)
city_id = fields.Many2one('res.city', 'City ID')
```

These decompose the single `street` field into structured components. The `_compute_street_data` method uses `tools.street_split()` to parse "123 Main Street" into `{'street_name': 'Main Street', 'street_number': '123'}`. The `_inverse_street_data` method reassembles them.

### 8.4 Properties Integration

The `properties.base.definition.mixin` allows `res.partner` to have dynamic custom fields defined via the "Properties" concept in Odoo. These properties are stored separately in `ir.property` and resolved at runtime. This enables:
- Per-partner custom fields without schema changes
- Company-specific property definitions
- Properties that can be inherited through the commercial entity hierarchy

---

## Appendix A: Complete Field Reference Table

| Field | Type | Stored | Indexed | Required | Default | Copy |
|-------|------|--------|---------|----------|---------|------|
| `name` | Char | Yes | Yes | No* | None | Yes |
| `complete_name` | Char | Yes | Yes | No | None | No |
| `is_company` | Boolean | Yes | No | No | False | Yes |
| `company_type` | Selection | No | No | No | None | Yes |
| `parent_id` | Many2one | Yes | Yes | No | None | No |
| `child_ids` | One2many | Yes | No | No | None | No |
| `commercial_partner_id` | Many2one | Yes | Yes | No | None | No |
| `commercial_company_name` | Char | Yes | No | No | None | No |
| `company_name` | Char | Yes | No | No | None | Yes |
| `ref` | Char | Yes | Yes | No | None | Yes |
| `vat` | Char | Yes | Yes | No | None | Yes |
| `company_registry` | Char | Yes | Partial | No | None | Yes |
| `barcode` | Char | Yes | No | No | None | No |
| `street` | Char | Yes | No | No | None | Yes |
| `street2` | Char | Yes | No | No | None | Yes |
| `zip` | Char | Yes | No | No | None | Yes |
| `city` | Char | Yes | No | No | None | Yes |
| `state_id` | Many2one | Yes | No | No | None | Yes |
| `country_id` | Many2one | Yes | No | No | None | Yes |
| `country_code` | Char | No | No | No | None | No |
| `contact_address` | Char | No | No | No | None | No |
| `type` | Selection | Yes | No | No | 'contact' | Yes |
| `email` | Char | Yes | No | No | None | Yes |
| `email_formatted` | Char | No | No | No | None | No |
| `phone` | Char | Yes | No | No | None | Yes |
| `website` | Char | Yes | No | No | None | Yes |
| `comment` | Html | Yes | No | No | None | Yes |
| `user_ids` | One2many | Yes | No | No | None | No |
| `main_user_id` | Many2one | No | No | No | None | No |
| `user_id` | Many2one | Yes | No | No | None | Yes |
| `category_id` | Many2many | Yes | No | No | [] | No |
| `industry_id` | Many2one | Yes | No | No | None | Yes |
| `function` | Char | Yes | No | No | None | Yes |
| `partner_latitude` | Float | Yes | No | No | None | Yes |
| `partner_longitude` | Float | Yes | No | No | None | Yes |
| `partner_share` | Boolean | Yes | No | No | None | No |
| `lang` | Selection | Yes | No | No | None | Yes |
| `active_lang_count` | Integer | No | No | No | None | No |
| `tz` | Selection | Yes | No | No | Context | Yes |
| `tz_offset` | Char | No | No | No | None | No |
| `company_id` | Many2one | Yes | Yes | No | None | No |
| `bank_ids` | One2many | Yes | No | No | None | No |
| `active` | Boolean | Yes | No | No | True | Yes |
| `employee` | Boolean | Yes | No | No | False | Yes |
| `is_public` | Boolean | No | No | No | None | No |
| `color` | Integer | Yes | No | No | 0 | Yes |
| `self` | Many2one | No | No | No | None | No |
| `application_statistics` | Json | No | No | No | None | No |
| `same_vat_partner_id` | Many2one | No | No | No | None | No |
| `same_company_registry_partner_id` | Many2one | No | No | No | None | No |
| `vat_label` | Char | No | No | No | None | No |
| `company_registry_label` | Char | No | No | No | None | No |
| `company_registry_placeholder` | Char | No | No | No | None | No |
| `type_address_label` | Char | No | No | No | None | No |

*Contacts (type='contact') require a name per database constraint.

---

## Appendix B: Security Record Rules

Partners have these default record rules (from `base` module):

| Rule | Domain | Groups | Purpose |
|------|--------|--------|---------|
| Partner multi-company | `[('company_id', 'in', company_ids)]` | All | Restrict partners to user's companies |
| Portal partner read | `[('partner_share', '=', True)]` | Portal | Allow portal users to read customer partners |
| Employee read | `[('employee', '=', True)]` | Employee | Allow employees to read employee partners |

The `partner_share` field is critical for portal access — partners with `partner_share=True` are readable by portal users, while internal partners are not.

---

## Appendix C: Quick Reference — Commercial Fields vs Address Fields

**Commercial Fields** (delegated to `commercial_partner_id`, visible on all partners):
- `vat` (synced upstream: changes on children propagate to commercial entity)
- `company_registry`
- `industry_id`

**Address Fields** (synced from commercial entity to contacts of type='contact'):
- `street`
- `street2`
- `zip`
- `city`
- `state_id`
- `country_id`

**Independent Fields** (not synced, belong to the individual partner):
- `name`
- `email`
- `phone`
- `function`
- `type`
- `parent_id`
- `user_id` (computed from parent for persons)
