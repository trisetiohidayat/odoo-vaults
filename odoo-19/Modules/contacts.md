---
uid: modules.contacts
title: Contacts Module
description: Comprehensive documentation for the Odoo 19 Contacts module
date: 2026-04-11
tags:
  - odoo
  - odoo19
  - modules
  - contacts
  - crm
  - base
---

# Contacts Module (`contacts`)

## Module Overview

The **Contacts** module (`contacts`) is a core Odoo 19 application module that provides a centralized address book for managing partners, customers, vendors, and other contacts. It extends the foundational `res.partner` model from the `base` module with a dedicated application interface, menu structure, and user experience enhancements.

### Manifest

| Attribute | Value |
|-----------|-------|
| **Technical Name** | `contacts` |
| **Category** | Sales/CRM |
| **Sequence** | 150 |
| **Depends** | `base`, `mail` |
| **Application** | `True` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Summary** | Centralize your address book |

### File Structure

```
contacts/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── res_partner.py       # ResPartner extension (1 method)
│   └── res_users.py         # ResUsers extension (1 method)
├── views/
│   └── contact_views.xml    # Window actions, views, menus
├── data/
│   └── mail_demo.xml        # Demo data for mail integration
├── i18n/                    # Translations
├── static/
│   └── tests/               # JS tour tests
└── tests/
    └── test_ui.py           # UI tests (2 test cases)
```

### Dependencies

The `contacts` module depends on:

- **`base`**: Provides the foundational `res.partner` model, `res.partner.category`, `res.partner.title`, `res.partner.industry`, and all base views (tree, form, kanban, search) referenced by the contacts action.
- **`mail`**: Enables mail messaging capabilities on partner records (chatter, followers, activities, activity views). This is why the action `view_mode` includes `activity`.

### Design Philosophy

The `contacts` module demonstrates Odoo's **progressive extension** pattern. Rather than building a monolithic contact management system, it layers features through a minimalist orchestration layer:

1. **Layer 1: `base`** - `res.partner` provides all contact fields, hierarchy, address management, commercial field synchronization, and base views.
2. **Layer 2: `contacts`** - Adds the Contacts app as a top-level backend menu, customizes the systray activity icon, and reuses all base views.
3. **Layer 3: business modules** - `crm`, `sale`, `purchase`, `account`, etc. extend `res.partner` with domain-specific fields and behaviors.

The contacts module adds **no database fields** to `res.partner`. Its entire value comes from UX orchestration and integration points.

---

## Models

### 1. `ResPartner` Extension (`contacts.models.res_partner`)

**Inheritance:** Classical inheritance (`_inherit = 'res.partner'`)

**File:** `/odoo/addons/contacts/models/res_partner.py`

The contacts module extends `res.partner` with a single method that integrates the Contacts application into the Odoo backend menu system.

#### Method: `_get_backend_root_menu_ids`

```python
def _get_backend_root_menu_ids(self) -> list[int]
```

**Purpose:** Appends the Contacts application menu (`contacts.menu_contacts`) to the list of backend root menus, making the Contacts app appear as a top-level app in the Odoo app launcher alongside Sales, Purchase, Inventory, etc.

**Override Pattern:** This method is called by the parent implementation in `base` and returns an extended list that includes the contacts menu ID. The parent method in `base` returns the standard menu set; this extension appends the contacts-specific menu.

**L3 - Edge Cases:**

- **Menu reference failure:** If `self.env.ref('contacts.menu_contacts')` fails (e.g., module not fully loaded, menu ID changed, or registry not initialized), this raises a `ValueError`. In production deployments with complex module ordering or during upgrade scripts, the menu might not yet be registered when the method executes. This is mitigated by Odoo's dependency resolution system which loads modules in dependency order.
- **Duplicate prevention:** If multiple `res.partner` records trigger this method, the list concatenation could theoretically add the same menu ID multiple times. However, since the menu system deduplicates root menus at the UI rendering level, this is cosmetic rather than functional.
- **Portal users:** This method is called in a context where the user may be a portal user. Portal users do not see the contacts menu by default unless they have `base.group_user` or `base.group_partner_manager` membership, which is enforced by the menu's `groups` attribute in the XML definition.
- **Called on recordset:** This method is called on a recordset, but its behavior is not record-dependent - it always returns the same result. This is a design artifact where the method is defined on the model but uses the environment's registry to resolve the menu ID.

**L4 - Performance:** This method is called during the initialization of the Odoo backend home menu, specifically when building the menu tree for the sidebar. It uses `self.env.ref()` which performs a database lookup for the external ID (`ir.model.data` table). The result is cached by Odoo's model registry and the menu registry, so the performance impact is negligible after initial load. The method does not iterate over records, so it is O(1).

---

### 2. `ResUsers` Extension (`contacts.models.res_users`)

**Inheritance:** Classical inheritance (`_inherit = 'res.users'`)

**File:** `/odoo/addons/contacts/models/res_users.py`

The contacts module extends `res.users` to customize the system tray (systray) activity icon for `res.partner` activities.

#### Method: `_get_activity_groups`

```python
@api.model
def _get_activity_groups(self) -> list[dict]
```

**Purpose:** Overrides the default activity group icon for `res.partner` to use the Contacts module's custom icon instead of the base partner icon. This provides visual consistency - when a user sees pending activities related to partners, the icon matches the Contacts app icon.

**Source Code:**
```python
@api.model
def _get_activity_groups(self):
    activities = super()._get_activity_groups()
    for activity in activities:
        if activity['model'] != 'res.partner':
            continue
        activity['icon'] = modules.module.Manifest.for_addon('contacts').icon
    return activities
```

**Decorator:** `@api.model` - This method operates in a model-level context without a specific record. It uses `self.env` for registry access but does not require record-level data.

**L3 - Edge Cases:**

- **Missing icon:** If `Manifest.for_addon('contacts')` cannot find the contacts module manifest (e.g., during a module upgrade in progress where the module is temporarily uninstalled), this raises a `KeyError` or returns a fallback icon. The `Manifest.for_addon()` method is designed to be resilient and falls back to a default Odoo icon.
- **Activity model mismatch:** The method checks `activity['model'] != 'res.partner'` to avoid modifying icons for other models. If the activity dictionary structure changes in future Odoo versions (e.g., key renamed from `'model'` to `'model_name'`), this could silently fail or raise a `KeyError`.
- **Multiple activities for same model:** If there are multiple activity groups for `res.partner` (e.g., from different installed apps that register partner-related activities), all of them will have their icons replaced with the contacts module icon. This is generally the desired behavior for consistency.
- **Icon path changes:** If the contacts module's icon file path changes in the manifest (e.g., from `static/description/icon.png` to a different path), the `Manifest.for_addon()` call would return the new path automatically.

**L4 - Performance:** This method is called every time the system tray activity dropdown is rendered, which occurs on every backend page load. The `Manifest.for_addon()` call result is cached by the module manifest system after the first call, so subsequent calls are O(1) dictionary lookups. However, the method iterates through all activity groups - on systems with many installed apps, this could mean iterating through 50-100+ activity dictionaries per page load. This is a minor but real cost.

---

## Inherited Models from `base`

The `contacts` module's functional depth comes entirely from the **base** module's `res.partner` model and its related models. Understanding the full scope requires examining these inherited structures.

---

### `res.partner` (from `base`)

**Model Technical Name:** `res.partner`
**Description:** Contact
**Inherits:** `format.address.mixin`, `format.vat.label.mixin`, `avatar.mixin`, `properties.base.definition.mixin`
**Order:** `complete_name ASC, id DESC`
**Record Names Search:** `complete_name`, `email`, `ref`, `vat`, `company_registry`
**Class:** `ResPartner(models.Model)`

**Important Flags:**
```python
_allow_sudo_commands = False   # Disables sudo() from bypassing access rights
_check_company_auto = True      # Enables automatic company domain checking
_check_company_domain = models.check_company_domain_parent_of  # Company domain validator
```

This is the central data model for all parties in Odoo: customers, suppliers, employees, companies, and individuals. It is one of the most fundamental and heavily-used models in the entire system.

---

## All Fields: `res.partner` (Base Model)

### 1. Basic Identification Fields

#### `name`
```python
name = fields.Char(index=True, default_export_compatible=True)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |
| **Index** | `btree` index |
| **Export** | Default compatible for import/export |
| **Constraint** | Required when `type == 'contact'` (via SQL CHECK) |

The primary name field. Indexed for fast search. The primary record identifier in most partner lookups.

#### `complete_name`
```python
complete_name = fields.Char(compute='_compute_complete_name', store=True, index=True)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` (computed, stored) |
| **Storage** | Stored in database |
| **Index** | `btree` index |
| **Dependencies** | `name`, `user_ids.share`, `image_1920`, `is_company`, `type` |

Returns the full display name including parent company name for contacts. Format: `"Company Name, Contact Name"` for non-company contacts under a parent. Stored for performance in list views.

#### `ref`
```python
ref = fields.Char(string='Reference', index=True)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |
| **Index** | `btree` index |

Internal reference code. Not validated; free-form text. Indexed for quick lookup by reference.

#### `barcode`
```python
barcode = fields.Char(
    help="Use a barcode to identify this contact.",
    copy=False,
    company_dependent=True
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |
| **Copy** | `False` (not copied on record duplication) |
| **Company Dependent** | `True` (value varies per company) |
| **Constraint** | `_check_barcode_unicity` - must be unique |

Barcode identifier for physical/scanning workflows. Not duplicated on copy. Company-dependent allows different values per company in multi-company setups.

#### `comment`
```python
comment = fields.Html(string='Notes')
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Html` |
| **Sanitization** | Default HTML sanitization applied |

Internal notes with rich text support. Not typically displayed in list views. Supports bold, italic, lists, and links.

---

### 2. Company/Contact Type Fields

#### `is_company`
```python
is_company = fields.Boolean(
    string='Is a Company',
    default=False,
    help="Check if the contact is a company, otherwise it is a person"
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Boolean` |
| **Default** | `False` |

Fundamental discriminator that affects hierarchy behavior, commercial field synchronization, avatar rendering, and UI display. When `True`, the partner is a legal entity that can have child contact records.

#### `company_type`
```python
company_type = fields.Selection(
    string='Company Type',
    selection=[('person', 'Person'), ('company', 'Company')],
    compute='_compute_company_type',
    inverse='_write_company_type'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Selection` (computed with inverse) |
| **Values** | `person`, `company` |
| **Interface** | UI-only field, do not use in business logic |

**L3 - Odoo 19 Change:** In Odoo 18, this was a regular `selection` field. In Odoo 19, it became a computed field with an inverse method, enabling a radio-button toggle in the UI that simultaneously updates `is_company`.

The inverse method `_write_company_type`:
```python
def _write_company_type(self):
    for partner in self:
        partner.is_company = partner.company_type == 'company'
```

#### `function`
```python
function = fields.Char(string='Job Position')
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |
| **Visibility** | Typically hidden on company-type partners |

Job title or position (e.g., "Sales Director", "CEO"). Used only for individual contacts within a company.

#### `company_name`
```python
company_name = fields.Char('Company Name')
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |

Used when an individual contact is created before the company record exists. When `parent_id` is set, `company_name` is automatically cleared. When `create_company()` is called, this value becomes the new company partner's `name`.

---

### 3. Hierarchy Fields (Parent-Child)

#### `parent_id`
```python
parent_id: ResPartner = fields.Many2one(
    'res.partner',
    string='Related Company',
    index=True
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `res.partner` |
| **Index** | `btree` index |
| **Constraint** | `_check_parent_id` - no cycles allowed |

Points to the parent company. Creates the partner hierarchy. When set:

- `company_name` is cleared
- `is_company` should be `False`
- Address fields may sync from parent (for `type='contact'`)
- Commercial fields (`vat`, `industry_id`, `company_registry`) sync from parent via `_commercial_sync_from_company()`

**L3 - Hierarchy Depth:** Odoo does not enforce a maximum hierarchy depth. However, deeply nested hierarchies (100+ levels) can cause performance issues in `address_get()` DFS traversal and `_has_cycle()` detection. In practice, hierarchies of 3-5 levels (company -> divisions -> departments -> contacts) are typical.

#### `child_ids`
```python
child_ids: ResPartner = fields.One2many(
    'res.partner',
    'parent_id',
    string='Contact',
    domain=[('active', '=', True)],
    context={'active_test': False}
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `One2many` to `res.partner` |
| **Inverse** | `parent_id` |
| **Domain** | `active = True` (filters visible children) |
| **Context** | `active_test: False` (inactive children still accessible) |

Returns all active child contacts for this company. The `active_test=False` context means inactive child contacts are also accessible (not filtered out). This is important for `_fields_sync()` which needs to update inactive children too.

#### `commercial_partner_id`
```python
commercial_partner_id: ResPartner = fields.Many2one(
    'res.partner',
    string='Commercial Entity',
    compute='_compute_commercial_partner',
    store=True,
    recursive=True,
    index=True
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` (computed, stored) |
| **Storage** | Stored in database |
| **Recursive** | `True` |
| **Index** | `btree` index |
| **Dependencies** | `is_company`, `parent_id.commercial_partner_id` |

The topmost commercial entity in the partner hierarchy. For companies (`is_company=True`), this is the partner itself. For contacts, this is the root company. Used throughout Odoo for:
- Determining commercial field values (VAT, payment terms, fiscal position)
- Access control scoping
- Reporting and analytics

The `recursive=True` attribute allows traversing the relation in SQL JOINs efficiently.

#### `commercial_company_name`
```python
commercial_company_name = fields.Char(
    'Company Name Entity',
    compute='_compute_commercial_company_name',
    store=True
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` (computed, stored) |
| **Dependencies** | `company_name`, `parent_id.is_company`, `commercial_partner_id.name` |

Stores the commercial entity's name separately, allowing the contact's `company_name` to remain independent while the commercial field always reflects the root company.

---

### 4. Contact Type Field

#### `type`
```python
type = fields.Selection(
    [('contact', 'Contact'),
     ('invoice', 'Invoice'),
     ('delivery', 'Delivery'),
     ('other', 'Other')],
    string='Address Type',
    default='contact'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Selection` |
| **Values** | `contact`, `invoice`, `delivery`, `other` |
| **Default** | `contact` |

Determines the purpose of this address within the company hierarchy. Used by `address_get()` to find the appropriate partner for different operations:

- `sale.order`: uses `type='delivery'` for shipping address, `type='invoice'` for billing
- `purchase.order`: uses `type='supplier'` equivalent for vendor addresses
- `stock.picking`: uses `type='delivery'` for delivery addresses

**SQL Constraint:**
```python
_check_name = models.Constraint(
    "CHECK( (type='contact' AND name IS NOT NULL) or (type!='contact') )",
    "Contacts require a name",
)
```
This SQL constraint (at database level) enforces that `type='contact'` records must have a `name` value. It cannot be bypassed by the ORM.

#### `type_address_label`
```python
type_address_label = fields.Char(
    'Address Type Description',
    compute='_compute_type_address_label'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` (computed) |
| **Dependencies** | `parent_id`, `type` |

Localized address type label. Values:

| `type` value | With `parent_id` | Without `parent_id` |
|---|---|---|
| `contact` | "Company Address" | "Address" |
| `invoice` | "Invoice Address" | "Invoice Address" |
| `delivery` | "Delivery Address" | "Delivery Address" |
| `other` | "Other Address" | "Other Address" |

---

### 5. Address Fields

All address fields are part of the `ADDRESS_FIELDS` tuple:

```python
ADDRESS_FIELDS = ('street', 'street2', 'zip', 'city', 'state_id', 'country_id')
```

These fields are subject to synchronization rules managed by `_fields_sync()`.

#### `street`
```python
street = fields.Char()
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |

Street address line 1 (house number, street name).

#### `street2`
```python
street2 = fields.Char()
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |

Street address line 2 (building, floor, suite).

#### `zip`
```python
zip = fields.Char(change_default=True)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |
| **change_default** | `True` - prompts for default value update on change |

ZIP or postal code. `change_default=True` triggers the "Set Default" debug menu prompt when the field value is changed.

#### `city`
```python
city = fields.Char()
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |

City name.

#### `state_id`
```python
state_id: ResCountryState = fields.Many2one(
    "res.country.state",
    string='State',
    ondelete='restrict',
    domain="[('country_id', '=?', country_id)]"
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `res.country.state` |
| **ondelete** | `restrict` |
| **Domain** | `country_id` (3-valued `=?` operator) |

State/province/region. The `=?` domain operator makes the country filter inactive when `country_id` is `False`, allowing the state field to show all states when no country is selected.

#### `country_id`
```python
country_id: ResCountry = fields.Many2one(
    'res.country',
    string='Country',
    ondelete='restrict'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `res.country` |
| **ondelete** | `restrict` |

Country. Changing the country triggers `_onchange_country_id()` which clears `state_id` if the new country doesn't match the current state.

#### `country_code`
```python
country_code = fields.Char(related='country_id.code', string="Country Code")
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` (related, readonly) |
| **Source** | `country_id.code` |

ISO 3166-1 alpha-2 country code (e.g., "US", "FR", "ID").

#### `contact_address`
```python
contact_address = fields.Char(
    compute='_compute_contact_address',
    string='Complete Address'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` (computed) |
| **Dependencies** | All address fields + country |

Formatted multi-line address string using the country's address format template. Computed via `_display_address()`.

#### `partner_latitude`, `partner_longitude`
```python
partner_latitude = fields.Float(string='Geo Latitude', digits=(10, 7))
partner_longitude = fields.Float(string='Geo Longitude', digits=(10, 7))
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Float` |
| **Digits** | `(10, 7)` - up to 10 digits total, 7 after decimal (~1.1cm precision) |

Geolocation coordinates. In Odoo 19, these are largely historical - the geo-encoding service Odoo used to provide has been deprecated. Modern integrations use native map widgets that call external geocoding APIs directly.

---

### 6. Contact Information Fields

#### `phone`
```python
phone = fields.Char()
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |
| **Widget** | `phone` (clickable `tel:` link in web client, SMS capable) |

Primary phone number. No format validation at field level. The `phone` widget enables click-to-call in supported browsers and SMS integration.

#### `email`
```python
email = fields.Char()
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |
| **Widget** | `email` (clickable `mailto:` link) |

Primary email address. No validation at field level. Used extensively in:
- `name_create()` for parsing `"Name <email>"` format strings
- `find_or_create()` for partner identification
- Mail threading and notifications

#### `email_formatted`
```python
email_formatted = fields.Char(
    'Formatted Email',
    compute='_compute_email_formatted',
    help='Format email address "Name <email@domain>"'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` (computed) |
| **Dependencies** | `name`, `email` |

Formats email as `"Display Name <email@domain.com>"` using Python's `email.utils.formataddr`. Handles:

- **Multi-email addresses:** Comma-separated addresses are each normalized individually
- **Already-formatted emails:** Recognized and not double-formatted
- **Invalid emails:** Preserved for error visibility and debugging
- **Empty emails:** Returns `False` (not an empty string)

**L3 - Double-formatting prevention:** The method uses `email_normalize_all()` to detect if the email field already contains a formatted address. If so, it uses the raw value rather than re-formatting it.

#### `website`
```python
website = fields.Char('Website Link')
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |
| **Widget** | `url` |
| **Processing** | `_clean_website()` adds `http://` scheme if missing |

Website URL. The `_clean_website()` method normalizes URLs:
```python
def _clean_website(self, website):
    url = urls.url_parse(website)
    if not url.scheme:
        if not url.netloc:
            url = url.replace(netloc=url.path, path='')
        website = url.replace(scheme='http').to_url()
    return website
```

This ensures that "example.com" becomes "http://example.com" for proper URL handling.

---

### 7. Tags/Category Fields

#### `category_id`
```python
category_id: ResPartnerCategory = fields.Many2many(
    'res.partner.category',
    column1='partner_id',
    column2='category_id',
    string='Tags',
    default=_default_category
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2many` to `res.partner.category` |
| **Relation Table** | Auto-generated (`res_partner_category_rel`) |
| **Default** | From context via `_default_category()` |

Tags for classifying partners. The `_default_category()` method:
```python
def _default_category(self):
    return self.env['res.partner.category'].browse(
        self.env.context.get('category_id')
    )
```

This enables pre-selecting a tag when creating a partner from a filtered view.

**L3 - Category Context Flow:**
1. User navigates to Contacts with a tag filter active
2. The filter sets `category_id` in the context (via `search_default_category_id`)
3. When creating a new partner from this view, the action's context includes `default_category_id`
4. The form's `_default_category()` picks it up via the context chain
5. The tag is pre-selected when the form opens

---

### 8. User/Sales Assignment Fields

#### `user_id`
```python
user_id: ResUsers = fields.Many2one(
    'res.users',
    string='Salesperson',
    compute='_compute_user_id',
    precompute=True,
    readonly=False,
    store=True,
    help='The internal user in charge of this contact.'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `res.users` |
| **Compute** | Yes |
| **Precompute** | `True` - computed on create before constraints |
| **Storage** | Stored in database |
| **Inverse** | Yes (writable) |

The salesperson/account manager responsible for this contact. The `precompute=True` attribute (Odoo 19 feature) means this is computed at create time before constraint checks, avoiding the need for a post-create write.

**L3 - Auto-sync from parent:** The compute method syncs from parent company:
```python
@api.depends('parent_id')
def _compute_user_id(self):
    for partner in self.filtered(
        lambda p: not p.user_id and p.company_type == 'person' and p.parent_id.user_id
    ):
        partner.user_id = partner.parent_id.user_id
```

This only applies to person-type contacts without an existing `user_id` whose parent has a `user_id` set.

#### `user_ids`
```python
user_ids: ResUsers = fields.One2many(
    'res.users',
    'partner_id',
    string='Users',
    bypass_search_access=True
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `One2many` to `res.users` |
| **Inverse** | `partner_id` on `res.users` |
| **Security** | `bypass_search_access=True` - bypasses access rules for search |

All internal and portal users linked to this partner. The `bypass_search_access=True` is necessary because partner search must work for all accessible partners, not just those the current user can directly read.

#### `main_user_id`
```python
main_user_id: ResUsers = fields.Many2one(
    "res.users",
    string="Main User",
    compute="_compute_main_user_id",
    help="There can be several users related to the same partner..."
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` (computed) |
| **Dependencies** | `user_ids.active`, `user_ids.share` |

Determines the "primary" user when multiple users are linked to the same partner. Selection priority:
1. Current user if their partner is this record
2. Active internal users (non-share), ordered by creation (most recent first)
3. Any active user

---

### 9. Company/VAT Fields

#### `vat`
```python
vat = fields.Char(
    string='Tax ID',
    index=True,
    help="The Tax Identification Number. Values here will be validated based on the country format."
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` |
| **Index** | `btree` index |
| **Validation** | Country-specific VAT format validation |
| **Special Value** | `'/'` indicates partner is not subject to tax |

Tax identification number. Subject to format validation by country (via `base_vat` module or country-specific l10n modules). Part of commercial fields (synced from parent).

**L3 - EU VAT Variations:** The `_compute_same_vat_partner_id()` method handles EU VAT format variations:

```python
# For a German partner with VAT "DE123456789"
# Searches for: "DE123456789", "123456789" (with country prefix stripped)
# For UK with VAT "GB123456789":
# Searches for: "GB123456789", "XI123456789" (post-Brexit Northern Ireland), "123456789"
```

#### `vat_label`
```python
vat_label = fields.Char(
    string='Tax ID Label',
    compute='_compute_vat_label'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` (computed) |
| **Dependencies** | Context (`company`) |

Returns the company-specific VAT label from `res.company.country_id.vat_label`. Falls back to `"Tax ID"`. Examples: "TVA" (France), "ABN" (Australia), "NIF" (Spain), "VAT" (default).

#### `same_vat_partner_id`
```python
same_vat_partner_id: ResPartner = fields.Many2one(
    'res.partner',
    string='Partner with same Tax ID',
    compute='_compute_same_vat_partner_id',
    store=False
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` (computed, not stored) |

Detects potential duplicate partners based on matching VAT number within the same country/company context. Excludes the current partner and its entire child hierarchy from the search.

#### `company_registry`
```python
company_registry = fields.Char(
    string="Company ID",
    compute='_compute_company_registry',
    store=True,
    readonly=False,
    index='btree_not_null',
    help="The registry number of the company..."
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Char` (computed, stored) |
| **Index** | `btree_not_null` (partial index for non-null values) |
| **Company Dependent** | `True` |

National company registration number. Part of commercial fields. The `btree_not_null` index only indexes non-null values, making lookups on null values fast while keeping the index compact.

#### `same_company_registry_partner_id`
```python
same_company_registry_partner_id: ResPartner = fields.Many2one(
    'res.partner',
    string='Partner with same Company Registry',
    compute='_compute_same_vat_partner_id',
    store=False
)
```

Detects duplicate partners by matching `company_registry` within the same company scope.

---

### 10. Industry and Classification

#### `industry_id`
```python
industry_id: ResPartnerIndustry = fields.Many2one(
    'res.partner.industry',
    'Industry'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `res.partner.industry` |

Industry classification. Part of commercial fields (synced from parent). Used for segmentation, reporting, and analytics.

#### `employee`
```python
employee = fields.Boolean(
    help="Check this box if this contact is an Employee."
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Boolean` |

Flags whether this partner is an employee. This is a marker field used by the HR module to distinguish employee contacts from external parties.

---

### 11. Financial Fields

#### `bank_ids`
```python
bank_ids: ResPartnerBank = fields.One2many(
    'res.partner.bank',
    'partner_id',
    string='Banks'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `One2many` to `res.partner.bank` |
| **Inverse** | `partner_id` |

Bank accounts associated with this partner. Managed via the `res.partner.bank` model which stores account numbers, bank names, and IBAN codes.

---

### 12. Company Assignment

#### `company_id`
```python
company_id: ResCompany = fields.Many2one(
    'res.company',
    'Company',
    index=True
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `res.company` |
| **Index** | `btree` index |

The company this partner belongs to in multi-company environments. When set on a parent company, it cascades to all children (enforced in `write()`):

```python
if 'company_id' in vals:
    for partner in self:
        if partner.child_ids:
            partner.child_ids.write({'company_id': company_id})
```

**L3 - Cascade behavior:** When a company's `company_id` is changed, all its child contacts are updated to the new company. This ensures consistency but can be slow for companies with many children (batch write).

#### `partner_share`
```python
partner_share = fields.Boolean(
    'Share Partner',
    compute='_compute_partner_share',
    store=True,
    help="Either customer (not a user), either shared user..."
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Boolean` (computed, stored) |
| **Dependencies** | `user_ids.share`, `user_ids.active` |

Indicates whether the partner is shared (has a portal user) or is an internal contact. A partner with no active internal users and at least one portal user has `partner_share=True`. The superuser's partner is always `False`.

---

### 13. Technical Fields

#### `tz`, `tz_offset`
```python
tz = fields.Selection(_tzs, string='Timezone',
    default=lambda self: self.env.context.get('tz'))
tz_offset = fields.Char(compute='_compute_tz_offset', string='Timezone offset')
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Selection` / `Char` (computed) |
| **Options** | All IANA timezone identifiers |

Partner's preferred timezone for document generation and data export. `tz_offset` computes the UTC offset string (e.g., `+0700`, `-0500`). Defaults to the user's timezone from context.

#### `lang`
```python
lang = fields.Selection(
    _lang_get,
    string='Language',
    compute='_compute_lang',
    readonly=False,
    store=True,
    help="All the emails and documents sent to this contact..."
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Selection` (computed, stored) |
| **Dependencies** | `parent_id` |

Partner's preferred language for document translation. For child contacts, auto-inherits from parent company. The `readonly=False` allows manual override.

#### `is_public`
```python
is_public = fields.Boolean(
    compute='_compute_is_public',
    compute_sudo=True
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Boolean` (computed) |
| **Sudo** | `True` (bypasses record rules for computation) |

Indicates whether any linked user is a public user (e.g., the public warehouse user). Used to identify system-level partners.

#### `self` (recursive reference)
```python
self: ResPartner = fields.Many2one(
    comodel_name='res.partner',
    compute='_compute_get_ids'
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `res.partner` (computed) |

A self-referential computed field that enables using plain browse records in QWeb views. Allows `record.self` to reference the record itself in templates, bypassing the need for `record.id` in some contexts.

#### `application_statistics`
```python
application_statistics = fields.Json(
    string="Stats",
    compute="_compute_application_statistics"
)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Json` (computed) |
| **Widget** | `contact_statistics` (kanban footer) |

**L3 - Odoo 19 Feature:** Provides per-application statistics as a JSON structure, shown in the kanban view footer. This is a hook method (`_compute_application_statistics_hook`) that modules override to inject their statistics:

```python
def _compute_application_statistics_hook(self):
    """ Hook for override. Returns defaultdict(list) mapping partner_id to stats list. """
    return defaultdict(list)
```

Modules like `sale`, `project`, `purchase` override this to add their statistics (order counts, task counts, etc.).

#### Avatar Fields (from `avatar.mixin`)
```python
image_1920 = fields.Image(max_width=1920, max_height=1920)    # Full size
image_1024 = fields.Image(max_width=1024, max_height=1024)    # Large preview
image_512 = fields.Image(max_width=512, max_height=512)       # Medium
image_256 = fields.Image(max_width=256, max_height=256)       # Thumbnail
image_128 = fields.Image(max_width=128, max_height=128)       # Small thumbnail
avatar_1920 = fields.Binary(compute='_compute_avatar_1920')   # Computed
avatar_1024 = fields.Binary(compute='_compute_avatar_1024')    # Computed
avatar_512 = fields.Binary(compute='_compute_avatar_512')     # Computed
avatar_256 = fields.Binary(compute='_compute_avatar_256')     # Computed
avatar_128 = fields.Binary(compute='_compute_avatar_128')     # Computed
```

**Avatar computation priority:**
1. Partner with internal (non-share) user: use user's avatar
2. Company without image: use `base/static/img/company_image.png`
3. Type-specific placeholders: `truck.png` (delivery), `bill.png` (invoice), `puzzle.png` (other)
4. Default contact avatar (gravatar-style initials)

#### `properties` (from `properties.base.definition.mixin`)
```python
properties = fields.Properties(
    string='Properties',
    definition='property_definition',
)
```

Odoo 19's dynamic property system. Allows defining custom fields per-record without schema changes. The `property_definition` field on the model defines the schema for these dynamic properties.

#### `active`
```python
active = fields.Boolean(default=True)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Boolean` |
| **Default** | `True` |

Soft-delete flag. Archived partners are hidden by default but remain in the database. Critical: archiving a partner does NOT archive linked `res.users` records.

#### `color`
```python
color = fields.Integer(string='Color Index', default=0)
```
| Attribute | Value |
|-----------|-------|
| **Type** | `Integer` |
| **Default** | `0` |

Used for color-coding partners in kanban views. Color is applied as `oe_kanban_color_{color % 11}` CSS class.

---

## All Methods: `res.partner` (Base Model)

### Computed Field Methods

#### `_compute_complete_name()`
```python
@api.depends('is_company', 'name', 'parent_id.name', 'type',
             'company_name', 'commercial_company_name')
def _compute_complete_name(self):
    for partner in self:
        partner.complete_name = partner.with_context({})._get_complete_name()
```

Formats the complete display name. The `_get_complete_name()` method implements the actual logic:

```python
def _get_complete_name(self):
    self.ensure_one()
    name = self.name or ''
    if self.company_name or self.parent_id:
        if not name and self.type in displayed_types:
            name = type_description[self.type]
        if not self.is_company and not self.env.context.get(
            'partner_display_name_hide_company'
        ):
            name = f"{self.commercial_company_name or self.sudo().parent_id.name}, {name}"
    return name.strip()
```

**L3 - Name format patterns:**

| Partner type | Name value | Result |
|---|---|---|
| Company | "Acme Corp" | "Acme Corp" |
| Contact, no parent | "John Doe" | "John Doe" |
| Contact, parent company | "John Doe" under "Acme Corp" | "Acme Corp, John Doe" |
| Contact (invoice type), no name | type='invoice' | "Invoice Address" |

#### `_compute_same_vat_partner_id()`
```python
@api.depends('vat', 'company_id', 'company_registry', 'country_id')
def _compute_same_vat_partner_id(self):
    for partner in self:
        partner_id = partner._origin.id
        Partner = self.with_context(active_test=False).sudo()
        vats = [partner.vat]
        should_check_vat = partner.vat and len(partner.vat) != 1

        if should_check_vat and partner.country_id:
            if partner.vat[:2].isalpha():
                vats.append(partner.vat[2:])
            else:
                vats.append(partner.country_id.code + partner.vat)
                if new_code := EU_EXTRA_VAT_CODES.get(partner.country_id.code):
                    vats.append(new_code + partner.vat)

        # ... search domain construction ...
        partner.same_vat_partner_id = should_check_vat and not partner.parent_id and \
            Partner.search(domain, limit=1)
```

**L3 - Key behaviors:**

- Uses `active_test=False` so archived partners are included in duplicate detection (allows reactivation instead of creating duplicates)
- Single-character VAT values are skipped (too short to be meaningful)
- EU prefix handling: adds variants with/without country prefix
- UK post-Brexit handling: adds `XI` prefix for Northern Ireland
- Excludes current partner and all its descendants from search

#### `_compute_contact_address()`
```python
@api.depends(lambda self: self._display_address_depends())
def _compute_contact_address(self):
    for partner in self:
        partner.contact_address = partner._display_address()
```

Delegates to `_display_address()` which uses country-specific formatting.

#### `_compute_email_formatted()`
```python
@api.depends('name', 'email')
def _compute_email_formatted(self):
    self.email_formatted = False
    for partner in self:
        emails_normalized = tools.email_normalize_all(partner.email)
        if emails_normalized:
            partner.email_formatted = tools.formataddr((
                partner.name or u"False",
                ','.join(emails_normalized)
            ))
        elif partner.email:
            partner.email_formatted = tools.formataddr((
                partner.name or u"False",
                partner.email
            ))
```

Uses `email_normalize_all()` which handles comma-separated multi-email strings by splitting and normalizing each one.

#### `_compute_partner_share()`
```python
@api.depends('user_ids.share', 'user_ids.active')
def _compute_partner_share(self):
    super_partner = self.env['res.users'].browse(api.SUPERUSER_ID).partner_id
    if super_partner in self:
        super_partner.partner_share = False
    for partner in self - super_partner:
        partner.partner_share = not partner.user_ids or \
            not any(not user.share for user in partner.user_ids)
```

Logic: partner is shared if it has no users OR all users are share users (portal). Having at least one internal user makes `partner_share=False`.

---

### Onchange Methods

#### `onchange_parent_id()`
```python
@api.onchange('parent_id')
def onchange_parent_id(self):
    if not self.parent_id:
        return
    result = {}
    partner = self._origin
    if (partner.type or self.type) == 'contact':
        if address_values := self.parent_id._get_address_values():
            result['value'] = address_values
    return result
```

When a parent company is selected, suggests the parent's address fields for the contact. The `type` check uses `partner.type` (from `_origin`) for existing records and `self.type` for new records.

**L3 - `_get_address_values()` check:** Only returns address if at least one field is non-empty. This prevents copying an empty address over an existing contact address.

#### `_onchange_country_id()`
```python
@api.onchange('country_id')
def _onchange_country_id(self):
    if self.country_id and self.country_id != self.state_id.country_id:
        self.state_id = False
```

Clears the state when country changes to an incompatible country.

#### `_onchange_state()`
```python
@api.onchange('state_id')
def _onchange_state(self):
    if self.state_id.country_id and self.country_id != self.state_id.country_id:
        self.country_id = self.state_id.country_id
```

Sets the country when a state is selected.

#### `_onchange_company_id()`
```python
@api.onchange('parent_id', 'company_id')
def _onchange_company_id(self):
    if self.parent_id:
        self.company_id = self.parent_id.company_id.id
```

Inherits company from parent when parent is set.

#### `onchange_company_type()`
```python
@api.onchange('company_type')
def onchange_company_type(self):
    self.is_company = (self.company_type == 'company')
```

UI-level toggle (radio buttons). Changes `is_company` based on selection.

---

### Constraint Methods

#### `_check_parent_id()`
```python
@api.constrains('parent_id')
def _check_parent_id(self):
    if self._has_cycle():
        raise ValidationError(_('You cannot create recursive Partner hierarchies.'))
```

Uses ORM's `_has_cycle()` for cycle detection. This uses a recursive CTE query on the `parent_id` field.

**L3 - Performance at scale:** For partners with thousands of child records, `_has_cycle()` executes a recursive SQL query. In practice, most partner hierarchies are shallow (3-5 levels), so this is fast.

#### `_check_partner_company()`
```python
@api.constrains('company_id')
def _check_partner_company(self):
    partners = self.filtered(lambda p: p.is_company and p.company_id)
    companies = self.env['res.company'].search_fetch(
        [('partner_id', 'in', partners.ids)],
        ['partner_id']
    )
    for company in companies:
        if company != company.partner_id.company_id:
            raise ValidationError(_('The company assigned to this partner...'))
```

Validates that a company-type partner that has a linked `res.company` record has a matching `company_id`.

#### `_check_barcode_unicity()`
```python
@api.constrains('barcode')
def _check_barcode_unicity(self):
    for partner in self:
        if partner.barcode and \
           self.env['res.partner'].search_count(
               [('barcode', '=', partner.barcode)]
           ) > 1:
            raise ValidationError(_('Another partner already has this barcode'))
```

**L4 - Performance concern:** Uses `search_count()` on every write where `barcode` is set. For large partner tables (millions of records), this is a full table scan. A database-level unique index would be more efficient.

---

### CRUD Methods

#### `create()`
```python
@api.model_create_multi
def create(self, vals_list):
    if self.env.context.get('import_file'):
        self._check_import_consistency(vals_list)
    for vals in vals_list:
        if vals.get('website'):
            vals['website'] = self._clean_website(vals['website'])
        if vals.get('parent_id'):
            vals['company_name'] = False
    partners = super().create(vals_list)
    # Manually compute lang because ir.default skips computed fields
    for partner, values in zip(partners, vals_list):
        if 'lang' not in values and partner.parent_id:
            partner._compute_lang()
    # Sync fields through hierarchy
    if not self.env.context.get('_partners_skip_fields_sync'):
        for partner, vals in zip(partners, vals_list):
            vals = self.env['res.partner']._add_missing_default_values(vals)
            partner._fields_sync(vals)
    return partners
```

**L3 - Key behaviors:**

1. **Website normalization:** URLs without scheme get `http://` prefix
2. **Company name clearing:** When parent is set, company_name is cleared
3. **Import consistency:** During import, validates state/country consistency
4. **Lang manual computation:** Because `lang` is computed-stored, `ir.default` doesn't apply defaults; manual computation handles parent inheritance
5. **Skip fields sync:** The `_partners_skip_fields_sync` context disables sync (used by `_load_records_create()` for batch optimization)
6. **Fields sync:** After creation, `_fields_sync()` propagates commercial fields and addresses through the hierarchy

#### `write()`
```python
def write(self, vals):
    # 1. Active=False: prevent archiving partner with active users
    if vals.get('active') is False:
        self.invalidate_recordset(['user_ids'])
        users = self.env['res.users'].sudo().search([('partner_id', 'in', self.ids)])
        if users:
            # Raises RedirectWarning or ValidationError
    # 2. Website normalization
    if vals.get('website'):
        vals['website'] = self._clean_website(vals['website'])
    # 3. Parent change: clear company_name
    if vals.get('parent_id'):
        vals['company_name'] = False
    # 4. Name change: update bank account holder names
    if vals.get('name'):
        for partner in self:
            for bank in partner.bank_ids:
                if bank.acc_holder_name == partner.name:
                    bank.acc_holder_name = vals['name']
    # 5. company_id change: cascade to children
    if 'company_id' in vals:
        company_id = vals['company_id']
        for partner in self:
            if company_id and partner.user_ids:
                # Validate company compatibility with all linked users
                company = self.env['res.company'].browse(company_id)
                companies = set(user.company_id for user in partner.user_ids)
                if len(companies) > 1 or company not in companies:
                    raise UserError(...)
            if partner.child_ids:
                partner.child_ids.write({'company_id': company_id})
    # 6. is_company change: requires manager rights
    if 'is_company' in vals and not self.env.su:
        if self.env.user.has_group('base.group_partner_manager'):
            result = super().sudo().write({'is_company': vals.get('is_company')})
            del vals['is_company']
            result = result and super().write(vals)
        else:
            result = super().write(vals)
    else:
        result = super().write(vals)
    # 7. Fields sync
    for partner, pre_values in zip(self, pre_values_list):
        updated = {fname: fvalue for fname, fvalue in vals.items()
                   if partner[fname] != pre_values.get(fname)}
        if updated:
            partner._fields_sync(updated)
    return result
```

**L3 - Write complexity analysis:**

| Step | Condition | Cost |
|------|----------|------|
| Active user check | `active=False` | O(n) where n = linked users |
| Website normalization | `website` in vals | O(1) |
| Company name clear | `parent_id` in vals | O(1) |
| Bank holder name update | `name` in vals | O(bank accounts) |
| Company cascade | `company_id` in vals | O(children) |
| is_company (sudo) | `is_company` in vals | O(1) + superuser call |
| Fields sync | Any field | O(children + commercial entity) |

**L4 - Security:** The `is_company` toggle requires `base.group_partner_manager` group. The check `not self.env.su` bypasses the group check only for the superuser (database admin). Regular users with the right group get a `sudo()` escalation for the `is_company` field only.

#### `_unlink_except_user()`
```python
@api.ondelete(at_uninstall=False)
def _unlink_except_user(self):
    users = self.env['res.users'].sudo().search([('partner_id', 'in', self.ids)])
    if not users:
        return
    if self.env['res.users'].sudo(False).has_access('write'):
        raise RedirectWarning(...)
    else:
        raise ValidationError(...)
```

`at_uninstall=False` means this constraint is NOT enforced during module uninstall, allowing cleanup scripts to proceed.

---

### Commercial Field Sync Methods

#### `_commercial_fields()`
```python
@api.model
def _commercial_fields(self):
    return self._synced_commercial_fields() + ['company_registry', 'industry_id']
```

Returns all commercial fields. Default includes: `vat` (synced), `company_registry`, `industry_id`. Overridable by other modules.

#### `_synced_commercial_fields()`
```python
@api.model
def _synced_commercial_fields(self):
    return ['vat']
```

Fields that sync from parent to child AND from child back to parent (bidirectional).

#### `_fields_sync()`
```python
def _fields_sync(self, values):
    """ Three-way sync: from parent, to parent, to children """
    # 1. From parent: sync commercial fields + address
    if values.get('parent_id') or values.get('type') == 'contact':
        if values.get('parent_id'):
            self.sudo()._commercial_sync_from_company()
        if self.parent_id and self.type == 'contact':
            if address_values := self.parent_id._get_address_values():
                self._update_address(address_values)

    # 2. To parent: sync address + commercial fields
    address_to_upstream = (
        bool(self.parent_id) and
        bool(self.type == 'contact') and
        (any(field in values for field in self._address_fields()) or 'parent_id' in values) and
        any(self[fname] != self.parent_id[fname] for fname in self._address_fields())
    )
    if address_to_upstream:
        new_address = self._get_address_values()
        self.parent_id.write(new_address)

    commercial_to_upstream = (
        bool(self.parent_id) and
        (self.commercial_partner_id != self) and
        (any(field in values for field in self._synced_commercial_fields()) or 'parent_id' in values) and
        any(self[fname] != self.parent_id[fname] for fname in self._synced_commercial_fields())
    )
    if commercial_to_upstream:
        new_synced_commercials = self._get_synced_commercial_values()
        self.parent_id.write(new_synced_commercials)

    # 3. To children
    self._children_sync(values)
```

**L3 - Sync Logic Complexity:** The three conditions for upstream sync (`address_to_upstream` and `commercial_to_upstream`) are designed to:

1. Prevent unnecessary writes when nothing changed
2. Prevent infinite recursion by checking if values actually differ
3. Only sync from contacts (not companies) to their parents

Without these guards, setting a contact's address would trigger updating the parent, which would trigger updating the contact again (because the contact's `_fields_sync` would see the parent's new address), creating infinite recursion.

**L3 - Real-world failure scenario:** If a custom module's `write()` override sets `vals['street'] = partner.street` (the same value), the write completes but `_fields_sync()` still runs. The `any(self[fname] != self.parent_id[fname])` check prevents the infinite loop by detecting that nothing actually changed.

---

### Address Methods

#### `_display_address()`
```python
def _display_address(self, without_company=False):
    address_format, args = self._prepare_display_address(without_company)
    return address_format % args
```

Formats address using country-specific format string. Example formats:

```python
# Default format
"%(street)s\n%(street2)s\n%(city)s %(state_code)s %(zip)s\n%(country_name)s"

# Some countries override this (defined on res.country.address_format)
# US: might include "City, State ZIP"
# Japan: might include prefecture and city
```

#### `_get_address_values()`
```python
def _get_address_values(self):
    address_fields = self._address_fields()
    if any(self[key] for key in address_fields):
        return self._convert_fields_to_values(address_fields)
    return {}
```

Only returns address if at least one address field is non-empty. Critical for preventing clearing a parent's complete address when a contact with a partial address is created.

---

### Hierarchy Navigation Methods

#### `address_get()`
```python
def address_get(self, adr_pref=None):
    """ Depth-first search through partner hierarchy """
    adr_pref = set(adr_pref or [])
    if 'contact' not in adr_pref:
        adr_pref.add('contact')
    result = {}
    visited = set()
    for partner in self:
        current_partner = partner
        while current_partner:
            to_scan = [current_partner]
            while to_scan:
                record = to_scan.pop(0)
                visited.add(record)
                if record.type in adr_pref and not result.get(record.type):
                    result[record.type] = record.id
                if len(result) == len(adr_pref):
                    return result
                to_scan = [c for c in record.child_ids
                           if c not in visited
                           if not c.is_company] + to_scan
            if current_partner.is_company or not current_partner.parent_id:
                break
            current_partner = current_partner.parent_id
    default = result.get('contact', self.id or False)
    for adr_type in adr_pref:
        result[adr_type] = result.get(adr_type) or default
    return result
```

**L3 - DFS algorithm analysis:**

1. **Starting point:** For each partner in the recordset, begin at that partner
2. **Scan strategy:** DFS through children, stopping at `is_company=True` nodes
3. **Stop conditions:** Found all requested address types OR visited all reachable nodes
4. **Fallback:** If a type is not found, fall back to `contact` type or the partner itself
5. **Always includes contact:** Even if `adr_pref` doesn't mention 'contact', it's always searched

**L3 - Usage in sale.order:**
```python
# When confirming a sale order:
addr = self.partner_id.address_get(['partner_invoice_id', 'partner_shipping_id'])
if not self.partner_invoice_id:
    self.partner_invoice_id = addr.get('partner_invoice_id')
if not self.partner_shipping_id:
    self.partner_shipping_id = addr.get('partner_shipping_id')
```

#### `find_or_create()`
```python
@api.model
def find_or_create(self, email, assert_valid_email=False):
    if not email:
        raise ValueError(...)
    parsed_name, parsed_email_normalized = tools.parse_contact_from_email(email)
    if not parsed_email_normalized and assert_valid_email:
        raise ValueError(...)

    if parsed_email_normalized:
        partners = self.search([('email', '=ilike', parsed_email_normalized)], limit=1)
        if partners:
            return partners

    create_values = {self._rec_name: parsed_name or parsed_email_normalized}
    if parsed_email_normalized:
        create_values['email'] = parsed_email_normalized
    return self.create(create_values)
```

Used throughout Odoo for:
- Processing incoming emails
- Creating leads from web forms
- Finding partners for mass mailing
- Partner auto-completion widgets

**L3 - Case sensitivity:** Uses `=ilike` for case-insensitive email matching. This is generally correct but may have edge cases with internationalized email addresses (IDN domains).

---

### Action Methods

#### `create_company()`
```python
def create_company(self):
    self.ensure_one()
    if (new_company := self._create_contact_parent_company()):
        self.write({
            'parent_id': new_company.id,
            'child_ids': [Command.update(
                partner_id,
                dict(parent_id=new_company.id)
            ) for partner_id in self.child_ids.ids]
        })
    return True
```

Creates a parent company from the contact's `company_name` and address, then re-parents the contact and its existing children to the new company. Uses `Command.update()` to update the `parent_id` on existing children without deleting/recreating them.

#### `open_commercial_entity()`
```python
def open_commercial_entity(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'res.partner',
        'view_mode': 'form',
        'res_id': self.commercial_partner_id.id,
        'target': 'current',
    }
```

Returns an action to open the root commercial partner's form. Used for contacts to quickly navigate to their parent/root company.

---

### Name and Search Methods

#### `name_create()`
```python
@api.model
def name_create(self, name):
    name, email_normalized = tools.parse_contact_from_email(name)
    if self.env.context.get('force_email') and not email_normalized:
        raise ValidationError(_("Couldn't create contact without email address!"))
    create_values = {self._rec_name: name or email_normalized}
    if email_normalized:
        create_values['email'] = email_normalized
    partner = self.create(create_values)
    return partner.id, partner.display_name
```

Parses input string for email format. Examples:

| Input | `name` | `email_normalized` |
|-------|--------|-------------------|
| `"John Doe"` | `"John Doe"` | `None` |
| `"John Doe <john@example.com>"` | `"John Doe"` | `"john@example.com"` |
| `"john@example.com"` | `"john@example.com"` | `"john@example.com"` |

---

## `res.partner.category` Model

**Model Technical Name:** `res.partner.category`
**Description:** Partner Tags
**Order:** `name, id`
**Features:** `_parent_store = True`

A hierarchical tag/category system for classifying partners. Supports multi-level parent-child relationships.

### Fields

| Field | Type | Key Attributes | Purpose |
|-------|------|----------------|---------|
| `name` | `Char` | `required=True`, `translate=True` | Tag name |
| `color` | `Integer` | `default=_get_default_color` | Random 1-11 for kanban color |
| `parent_id` | `Many2one` (self) | `index=True`, `ondelete='cascade'` | Parent tag |
| `child_ids` | `One2many` (self) | inverse of `parent_id` | Child tags |
| `parent_path` | `Char` | `index=True` | Materialized path "1/5/12/" |
| `partner_ids` | `Many2many` | `copy=False` | Partners with this tag |
| `active` | `Boolean` | `default=True` | Soft delete |

### Methods

#### `_check_parent_id()`
Prevents circular references in tag hierarchy using `_has_cycle()`.

#### `_compute_display_name()`
```python
@api.depends('parent_id')
def _compute_display_name(self):
    for category in self:
        names = []
        current = category
        while current:
            names.append(current.name or "")
            current = current.parent_id
        category.display_name = ' / '.join(reversed(names))
```

Formats as `"Parent / Child / GrandChild"`. The `while` loop walks up the tree, collecting names, then reverses to get root-to-leaf order.

#### `_search_display_name()`
```python
@api.model
def _search_display_name(self, operator, value):
    domain = super()._search_display_name(operator, value)
    if operator.endswith('like'):
        if operator.startswith('not'):
            return NotImplemented
        return [('id', 'child_of', tuple(self._search(domain)))]
    return domain
```

Enables hierarchical search. When searching `"Parent/Child"` with `ilike`, automatically converts to `child_of` operator using the materialized `parent_path` column.

---

## `res.partner.industry` Model

**Model Technical Name:** `res.partner.industry`
**Description:** Industry
**Order:** `name, id`

Industry classification for partners.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` (translate) | Industry name |
| `full_name` | `Char` (translate) | Full name |
| `active` | `Boolean` | Active flag |

Typical values: "Information Technology", "Manufacturing", "Retail Trade", "Construction", "Healthcare", "Education", etc.

---

## Views (`contacts.views.contact_views.xml`)

The contacts module defines its own window action and menus that reference the base views from the `base` module. This is a key design pattern: **contacts does NOT redefine views, it orchestrates existing ones**.

### Window Action: `action_contacts`

```xml
<record id="action_contacts" model="ir.actions.act_window">
    <field name="name">Contacts</field>
    <field name="path">contacts</field>
    <field name="res_model">res.partner</field>
    <field name="view_mode">list,kanban,form,activity</field>
    <field name="search_view_id" ref="base.view_res_partner_filter"/>
    <field name="context">{'default_is_company': True}</field>
</record>
```

**Key attributes:**

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `path` | `"contacts"` | Sets breadcrumb path in Odoo web client |
| `view_mode` | `list,kanban,form,activity` | Activity view enabled by `mail` dependency |
| `search_view_id` | `base.view_res_partner_filter` | Shared search view |
| `context` | `{'default_is_company': True}` | New partners default to company type |

**L3 - Kanban as default view:** The kanban view has sequence=1 (highest priority via `ir.actions.act_window.view` records), making it the **default view** when opening the Contacts app. This is different from the Customers/Vendors actions which open in list view.

### View Override via `ir.actions.act_window.view`

```xml
<!-- Kanban: sequence=1 (FIRST/default) -->
<record id="action_contacts_view_kanban" model="ir.actions.act_window.view">
    <field name="sequence" eval="1"/>
    <field name="view_mode">kanban</field>
    <field name="view_id" ref="base.res_partner_kanban_view"/>
    <field name="act_window_id" ref="action_contacts"/>
</record>

<!-- List: sequence=0 (SECOND) -->
<record id="action_contacts_view_tree" model="ir.actions.act_window.view">
    <field name="sequence" eval="0"/>
    <field name="view_mode">list</field>
    <field name="view_id" ref="base.view_partner_tree"/>
    <field name="act_window_id" ref="action_contacts"/>
</record>

<!-- Form: sequence=2 (THIRD) -->
<record id="action_contacts_view_form" model="ir.actions.act_window.view">
    <field name="sequence" eval="2"/>
    <field name="view_mode">form</field>
    <field name="view_id" ref="base.view_partner_form"/>
    <field name="act_window_id" ref="action_contacts"/>
</record>
```

**L3 - View priority nuance:** The `ir.actions.act_window.view` `sequence` field has inverted priority semantics in Odoo: **lower sequence = higher priority**. So sequence=0 (list) would normally appear first, but Odoo's view mode order (`list,kanban,form`) takes precedence. The combination means: list is shown in the view switcher first, but the initial render uses the first matching `ir.actions.act_window.view` record by sequence.

### Menu Structure

```
menu_contacts (root)
├── sequence: 20
├── web_icon: contacts,static/description/icon.png
├── groups: base.group_user, base.group_partner_manager
│
├── [Contacts]                    action=action_contacts     sequence=2
│   └── Opens: kanban (default) + list/form/activity
│
└── [Configuration]                groups=base.group_system   sequence=2
    ├── [Contact Tags]             action=base.action_partner_category_form
    ├── [Industries]              action=base.res_partner_industry_action
    └── [Localization]             sequence=5
        ├── [Countries]            action=base.action_country
        ├── [States]               action=base.action_country_state
        ├── [Country Groups]       action=base.action_country_group
        ├── [Bank Accounts]        sequence=6
        │   ├── [Banks]           action=base.action_res_bank_form
        │   └── [Bank Accounts]   action=base.action_res_partner_bank_account_form
```

---

## Tests (`contacts.tests.test_ui`)

### `test_set_defaults()`
Tests the "Set Defaults" debug menu feature on `res.partner`. Validates that:
1. `company_type` is a computed, non-readonly field (required for the feature to work)
2. The contacts action has `default_is_company=True` in context
3. Default value "Company" is active for new partners from this action

### `test_vat_label_string()`
Tests that changing `res.company.vat_label` is immediately reflected in partner form views. Validates the `FormatVatLabelMixin._get_view()` override dynamically updates the `vat` field's label string and its associated `<label>` element.

---

## L3: Edge Cases and Cross-Model Integration

### Address Hierarchy Sync Edge Cases

**Scenario 1: Parent with no address, contact with address**
When a contact has address data but the parent company does not, `_get_address_values()` returns empty dict (because not all address fields are set). The parent's address remains unchanged.

**Scenario 2: Multiple contacts under same parent with different addresses**
When multiple contacts have different addresses, `_fields_sync()` updates the parent address from the most recently saved contact. This can lead to unexpected parent address changes.

**Scenario 3: Inactive parent**
When a parent is archived (`active=False`), its active child contacts remain accessible. Commercial field synchronization still operates through `commercial_partner_id`, which points to the archived commercial entity.

**Scenario 4: Circular parent reference**
The `_has_cycle()` method prevents circular references. For very deep hierarchies (thousands of levels), this could cause performance issues or stack overflow.

### Cross-Model Integration Points

| Module | Integration Point | Method/Field |
|--------|------------------|--------------|
| `sale` | Customer orders | `partner_id`, `address_get()` |
| `purchase` | Vendor bills | `supplier_rank`, `purchase_order_count` |
| `stock` | Delivery addresses | `address_get(['delivery'])` |
| `account` | Invoice addresses | `property_account_receivable_id` |
| `mail` | Followers, messages | `mail.thread` (inherited) |
| `project` | Statistics hook | `_compute_application_statistics_hook()` |
| `hr` | Employee contacts | `employee` field |

### Override Patterns

The `res.partner` model is one of the most overridden models in Odoo. Common extension patterns:

1. **Add commercial fields:** Override `_commercial_fields()` to include new fields that should sync from parent
2. **Add address fields:** Override `_address_fields()` to include new address fields in synchronization
3. **Custom address format:** Override `_get_address_format()` for country-specific formatting
4. **Application statistics:** Override `_compute_application_statistics_hook()` to inject per-module statistics
5. **Vies fields:** Override `_compute_view_fields()` for custom view-dependent behavior

---

## L4: Odoo 18 to 19 Changes, Performance, and Security

### Odoo 18 to 19 Changes

**1. `company_type` computed field with inverse (Odoo 19)**

```python
# Odoo 18
company_type = fields.Selection([('person', 'Person'), ('company', 'Company')])

# Odoo 19
company_type = fields.Selection(
    selection=[('person', 'Person'), ('company', 'Company')],
    compute='_compute_company_type',
    inverse='_write_company_type'
)
```

Enables the radio-button toggle UI that simultaneously updates `is_company`.

**2. `application_statistics` JSON field (Odoo 19)**

Replaces scattered per-module statistics fields with a unified JSON-based statistics panel in the kanban view, controlled by the `contact_statistics` widget.

**3. `_parent_store = True` on categories**

Explicitly enables the materialized `parent_path` column for efficient hierarchical queries using `child_of` domain operator.

**4. `properties` field (Properties Definition Mixin)**

Odoo 19's dynamic property system adds the `properties` field for record-specific custom fields without schema changes.

**5. `avatar.mixin` integration**

Standardized avatar fields across models. Partner-specific enhancements include type-specific placeholder images.

**6. `_allow_sudo_commands = False`**

Explicitly disables `sudo()` from bypassing access rights on this sensitive model.

**7. Multi-email handling in `_compute_email_formatted`**

Odoo 19 improved email computation to handle comma-separated multi-email addresses using `tools.email_normalize_all()`.

**8. `precompute=True` on `user_id`**

Odoo 19's `precompute` attribute on computed fields enables computation at create time before constraint checks, avoiding post-create writes.

**9. `FormatVatLabelMixin` for dynamic VAT label**

The `format.vat.label.mixin` was added to dynamically show company-specific VAT labels (e.g., "TVA" in France, "NIP" in Poland) on partner forms.

### Performance Analysis

**Stored vs. Computed Fields:**

| Field | Type | Stored | Indexed | Notes |
|-------|------|--------|---------|-------|
| `complete_name` | computed | Yes | Yes | Fast list view sorting |
| `commercial_partner_id` | computed | Yes | Yes | Critical for commercial lookups |
| `user_id` | computed | Yes | No | Auto-sync from parent |
| `partner_share` | computed | Yes | No | User membership check |
| `lang` | computed | Yes | No | Inherited from parent |
| `vat` | regular | No | Yes | Duplicate detection |
| `ref` | regular | No | Yes | Internal reference |
| `barcode` | regular | No | Partial | `btree_not_null` on `company_registry` |

**N+1 Query Risks:**

1. **`address_get()` DFS:** For partners with many children, the DFS traversal queries `child_ids` at each level. With `active_test=False`, it fetches inactive children too.
2. **`_check_barcode_unicity`:** Uses `search_count()` on every barcode write, causing a full table scan on large tables.
3. **`same_vat_partner_id`:** Runs up to 3 separate searches for EU VAT variants.

**Batch Operations:**

The `_load_records_create()` method optimizes batch loading by:
1. Grouping partners by commercial entity and parent
2. Writing commercial and address fields in batch to grouped children
3. Processing children sync in a second pass

**Database Indexes:**

The partner table (typically one of the largest in Odoo) benefits from indexes on: `name`, `complete_name`, `parent_id`, `commercial_partner_id`, `company_id`, `vat`, `ref`, `user_id`, `country_id`, `state_id`, `industry_id`, `parent_path`.

### Security Analysis

**L4 - Access Control:**

`res.partner` contains sensitive personal data (names, addresses, phone numbers, emails). Access control considerations:

1. **Default ACL:** All internal users (`base.group_user`) can read/write all partners. There is no default record rule restricting access based on company or ownership.
2. **Portal access:** Portal users can only see partners they are followers of (via `mail.thread`).
3. **GDPR compliance:** The `active` field serves as a soft-delete mechanism for GDPR "right to erasure" - partners can be archived rather than deleted to preserve audit trails.
4. **Password fields:** No password fields exist on `res.partner` - password management is on `res.users` only.
5. **`_allow_sudo_commands = False`:** Prevents `sudo()` from bypassing access rights.

**L4 - Data Privacy:**

- `partner_share` helps identify partners who are portal users vs. internal-only contacts
- `is_public` identifies public-facing system users
- No field-level encryption at the model level - any encryption must be implemented at the database or field level
- The model does not store special categories of personal data (health, biometric, etc.) natively

**L4 - SQL Injection:**

All data access uses the ORM (`search`, `browse`, `read`, `write`, `create`, `unlink`). No raw SQL with string concatenation exists in the model. The only raw SQL consideration is through `_has_cycle()` which is handled internally by the ORM's CTE-based cycle detection.

**L4 - Input Validation:**

- Website URLs are normalized (scheme added if missing) via `_clean_website()`
- VAT numbers are validated at the module level (via `base_vat` or country-specific l10n modules)
- Email addresses are not validated at field level (normalized only when used in `email_formatted`)
- SQL constraint `_check_name` enforces `name` required for `type='contact'` at database level

---

## Related Documentation

- [Core/BaseModel](BaseModel.md) - Odoo ORM foundation
- [Core/Fields](Fields.md) - Field types reference
- [Core/API](API.md) - @api.depends, @api.onchange, @api.constrains
- [Modules/res.partner](res.partner.md) - Base partner model deep dive
- [Patterns/Security Patterns](Security Patterns.md) - ACL and record rules
- [Tools/ORM Operations](ORM Operations.md) - search(), browse(), write() operations
- [New Features/What's New](What's New.md) - Odoo 19 new features overview
