---
uuid: sale-management-module-v19
module: sale_management
tags:
  - #odoo
  - #odoo19
  - #modules
  - #sales
  - #sale_management
  - #templates
  - #quotation
  - #portal
  - #workflow
created: 2026-04-11
updated: 2026-04-11
author: Roedl
description: Sale Management - quotation/contract templates, optional products, portal confirmation, digest KPIs
related_modules:
  - sale
  - digest
see_also:
  - "[[Modules/sale]]"
  - "[[Core/BaseModel]]"
  - "[[Core/Fields]]"
---

# sale_management

## Overview

**Module:** `sale_management`
**Category:** Sales/Sales
**Depends:** `sale`, `digest`
**License:** LGPL-3
**Author:** Odoo S.A.

The `sale_management` module extends the base `sale` module with quotation template capabilities. It allows creating reusable templates containing predefined products, sections, notes, and terms that can be applied to new sale orders with a single selection. This standardizes quote creation, reduces encoding errors, and enables consistent upselling through optional product sections. It also adds a sales KPI to the digest system and exposes portal endpoints for customer-controlled quantity updates on optional lines.

---

## Module Architecture

### File Tree

```
sale_management/
├── __init__.py                      # Hooks: pre_init, post_init, uninstall
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── sale_order_template.py       # sale.order.template model
│   ├── sale_order_template_line.py  # sale.order.template.line model
│   ├── sale_order.py                # Extension of sale.order
│   ├── sale_order_line.py           # Extension of sale.order.line
│   ├── res_company.py               # Extension of res.company
│   ├── res_config_settings.py       # Settings wizard
│   └── digest.py                    # Digest KPI extension
├── controllers/
│   ├── __init__.py
│   └── portal.py                    # Portal endpoint for optional line updates
├── views/
│   ├── sale_order_template_views.xml  # Template form/list/search + action
│   ├── sale_order_views.xml           # Template field injected into SO form
│   ├── res_config_settings_views.xml  # Settings panel for template toggle
│   ├── sale_portal_templates.xml      # QWeb portal quantity override
│   ├── digest_views.xml               # KPI checkbox added to digest form
│   └── sale_management_menus.xml      # Menu and sale root activation
├── security/
│   ├── ir.model.access.csv
│   └── sale_management_security.xml   # Group + record rule
├── data/
│   ├── digest_data.xml              # Default digest enable + 2 tips
│   └── sale_order_template_demo.xml  # Demo template + group assignment
└── static/src/
    ├── fields/sale_order_line_field/
    │   └── sale_order_line_field.xml  # "Set/Unset Optional" dropdown item
    └── fields/sale_order_template_line_field/
        └── sale_order_template_line_field.xml  # Same for template lines
```

### Dependencies Chain

```
sale_management
  └── sale (base SO model)
      └── product (product.product)
      └── account (journal_id on template)
      └── currency
  └── digest (kpi_all_sale_total)
```

---

## Hook Functions (`__init__.py`)

### `pre_init_hook(env)` -- Fast-Track Column Creation

```python
def pre_init_hook(env):
    """Do not compute the sale_order_template_id field on existing SOs."""
    if not column_exists(env.cr, "sale_order", "sale_order_template_id"):
        create_column(env.cr, "sale_order", "sale_order_template_id", "int4")
```

**Purpose (L3):** Avoids the ORM `init()` method from recomputing `sale_order_template_id` across all existing sale orders during module installation. The column is created as a raw `int4` (no `NOT NULL`, no default), and the compute will populate values lazily on first access.

**Performance (L4):** Without this hook, a production database with 500K+ sale orders would experience a potentially multi-minute lock during `pre_init`. Direct SQL column creation bypasses ORM overhead. The `column_exists` guard makes this idempotent and safe for multi-install.

**L4 edge case:** If `sale_order` is already loaded into the registry before the column exists (module upgrade scenario), the `create_column` call must succeed before Odoo refreshes the registry. This is why the hook runs at the SQL level, not the ORM level.

### `uninstall_hook(env)` -- Deactivate Sale Menus

```python
def uninstall_hook(env):
    res_ids = env['ir.model.data'].search([
        ('model', '=', 'ir.ui.menu'),
        ('module', '=', 'sale')
    ]).mapped('res_id')
    env['ir.ui.menu'].browse(res_ids).update({'active': False})
```

**Purpose (L3):** When `sale_management` is uninstalled, the `sale` menu items (which were re-activated by `post_init_hook`) are hidden again to maintain a clean state.

**L4 edge case:** The hook targets ALL `ir.ui.menu` records from the `sale` module, not just those modified by `post_init_hook`. This is safe because setting already-inactive menus to `False` is a no-op, and it ensures no stale "active" flags remain if other modules have added sale menus.

### `post_init_hook(env)` -- Restore Sale Menu Active State

```python
def post_init_hook(env):
    res_ids = env['ir.model.data'].search([
        ('model', '=', 'ir.ui.menu'),
        ('module', '=', 'sale'),
    ]).mapped('res_id')
    env['ir.ui.menu'].browse(res_ids).update({'active': True})
```

**Purpose (L3):** Re-activates sale menu items after installation. This is the inverse of `uninstall_hook`. The pair exists because `sale_management` modifies `sale.sale_menu_root` to set `active=True` via `data/sale_order_template_demo.xml` (non-noupdate), so on reinstall the menus must be re-enabled.

---

## Models

### 1. `sale.order.template`

**File:** `models/sale_order_template.py`
**Inherits:** None (standalone model)
**Description:** Represents a reusable quotation template. Contains lines, terms, and confirmation settings.

#### L1: Field Definitions

```python
class SaleOrderTemplate(models.Model):
    _name = 'sale.order.template'
    _description = "Quotation Template"
    _order = 'sequence, id'
```

##### Basic Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | `Char` | Yes | -- | Template display name, e.g. "Standard Consultancy Package" |
| `active` | `Boolean` | No | `True` | Archive/unarchive toggle without deletion |
| `company_id` | `Many2one(res.company)` | No | `self.env.company` | Owning company for multi-company scoping |
| `sequence` | `Integer` | No | `10` | Sort order in template listing |
| `note` | `Html` | No | -- | Terms and conditions content; fully translatable (`translate=True`) |
| `mail_template_id` | `Many2one(mail.template)` | No | -- | Email template sent on order confirmation |
| `number_of_days` | `Integer` | No | -- | Quotation validity duration in days |

##### Confirmation / Workflow Fields

| Field | Type | Compute | Store | Default | Description |
|-------|------|---------|-------|---------|-------------|
| `require_signature` | `Boolean` | Yes (`_compute_require_signature`) | Yes | From `company.portal_confirmation_sign` | Request online signature for auto-confirmation |
| `require_payment` | `Boolean` | Yes (`_compute_require_payment`) | Yes | From `company.portal_confirmation_pay` | Request online payment for auto-confirmation |
| `prepayment_percent` | `Float` | Yes (`_compute_prepayment_percent`) | Yes | From `company.prepayment_percent` | Percentage of order total required as prepayment |

##### Relational Fields

| Field | Type | Inverse | Description |
|-------|------|---------|-------------|
| `sale_order_template_line_ids` | `One2many` | -- | Template lines (products, sections, notes) |
| `journal_id` | `Many2one(account.journal)` | -- | Invoicing journal for SOs using this template |

#### L2: Field Details

**`require_signature` -- Online Signature Flag**

- **Compute:** `_compute_require_signature` depends on `company_id`
- **Storage:** `store=True, readonly=False` -- allows manual override
- **Inheritance chain:** Template value is propagated to `sale.order.require_signature` via `_compute_require_signature` on the SO model when a template is set
- **Purpose:** When `True`, the portal forces the customer to provide an electronic signature before the SO can auto-confirm

**`require_payment` -- Online Payment Flag**

- **Compute:** `_compute_require_payment` depends on `company_id`
- **Storage:** `store=True, readonly=False` -- allows manual override
- **Purpose:** When `True`, the portal requires an online payment (e.g., Stripe, Adyen) before the SO auto-confirms
- **Mutual exclusion:** Setting `prepayment_percent = 0` or falsy automatically sets `require_payment = False` via `_onchange_prepayment_percent`

**`prepayment_percent` -- Payment Proportion**

- **Compute:** `_compute_prepayment_percent` depends on `company_id` and `require_payment`
- **Storage:** `store=True, readonly=False`
- **Valid range:** `0 < prepayment_percent <= 1.0` when `require_payment` is `True`
- **Constraint:** `_check_prepayment_percent` enforces the valid percentage range
- **Error:** `ValidationError(_("Prepayment percentage must be a valid percentage."))`

**`journal_id` -- Invoicing Journal**

- **Domain:** `[('type', '=', 'sale')]`
- **Attributes:** `company_dependent=True, check_company=True`
- **Purpose:** If set, SOs using this template invoice through the specified journal; otherwise the lowest-sequence sales journal is used

**`sale_order_template_line_ids` -- Template Lines**

- **Inverse:** `sale_order_template_line.sale_order_template_id`
- **Copy:** `copy=True` -- lines are duplicated when the template is duplicated

#### L3: Method Signatures and Edge Cases

##### `_compute_require_signature()`
```python
@api.depends('company_id')
def _compute_require_signature(self):
    for order in self:
        order.require_signature = (order.company_id or order.env.company).portal_confirmation_sign
```
- **Edge case:** Handles `False` company (null) by falling back to `self.env.company`
- **Override pattern:** Since `store=True, readonly=False`, the computed value can be manually overwritten on the form; Odoo persists the manual override

##### `_compute_require_payment()`
```python
@api.depends('company_id')
def _compute_require_payment(self):
    for order in self:
        order.require_payment = (order.company_id or order.env.company).portal_confirmation_pay
```
- **Edge case:** Same null-company fallback as `_compute_require_signature`

##### `_compute_prepayment_percent()`
```python
@api.depends('company_id', 'require_payment')
def _compute_prepayment_percent(self):
    for template in self:
        template.prepayment_percent = (
            template.company_id or template.env.company
        ).prepayment_percent
```
- **Edge case:** `require_payment` is in the `@api.depends` but the compute does not check it -- it always mirrors the company value. The onchange `_onchange_prepayment_percent` handles clearing `require_payment` when the percent is set to 0.

##### `_onchange_prepayment_percent()`
```python
@api.onchange('prepayment_percent')
def _onchange_prepayment_percent(self):
    for template in self:
        if not template.prepayment_percent:
            template.require_payment = False
```
- **Trigger:** Fires when user clears the prepayment percent field
- **Effect:** Automatically disables the `require_payment` toggle when percent is zero/empty

##### `_check_company_id() -- Cross-Model Multi-Company Validation`
```python
@api.constrains('company_id', 'sale_order_template_line_ids')
def _check_company_id(self):
    for template in self:
        restricted_products = template.sale_order_template_line_ids.product_id.filtered('company_id')
        if not restricted_products:
            continue
        if not template.company_id:
            raise ValidationError(_("Your template cannot contain products from specific companies..."))
        authorized_products = restricted_products.filtered_domain(
            self.env['product.product']._check_company_domain(template.company_id)
        )
        if unauthorized_products := restricted_products - authorized_products:
            # raises ValidationError with specific company names
```
- **Cross-model validation:** Validates that all products in template lines belong to the template's company (or have no company restriction)
- **Edge case (L3):** Templates with `company_id=False` (shared templates) cannot contain company-restricted products
- **Edge case (L3):** Uses `walrus operator` (Python 3.8+) for concise unauthorized-product detection
- **Failure mode:** Raises `ValidationError` with a message listing inaccessible product companies

##### `_check_prepayment_percent() -- Prepayment Constraint`
```python
@api.constrains('prepayment_percent')
def _check_prepayment_percent(self):
    for template in self:
        if template.require_payment and not (0 < template.prepayment_percent <= 1.0):
            raise ValidationError(_("Prepayment percentage must be a valid percentage."))
```
- **Cross-field dependency:** Only validates when `require_payment == True`
- **Failure mode:** `ValidationError` if percent is zero, negative, or greater than 1.0

##### `create(vals_list)`
```python
@api.model_create_multi
def create(self, vals_list):
    records = super().create(vals_list)
    records._update_product_translations()
    return records
```
- **Post-create hook:** Synchronizes product descriptions across all active languages

##### `write(vals)`
```python
def write(self, vals):
    if 'active' in vals and not vals.get('active'):
        companies = self.env['res.company'].sudo().search([('sale_order_template_id', 'in', self.ids)])
        companies.sale_order_template_id = None
    result = super().write(vals)
    self._update_product_translations()
    return result
```
- **Side effect:** Archiving a template (`active=False`) automatically clears it from any `res.company` records that reference it as their default template

##### `_update_product_translations() -- Multi-Language Sync`
```python
def _update_product_translations(self):
    languages = self.env['res.lang'].search([('active', '=', True)])
    for lang in languages:
        for line in self.sale_order_template_line_ids:
            if line.name == line.product_id.get_product_multiline_description_sale():
                line.with_context(lang=lang.code).name = (
                    line.product_id.with_context(lang=lang.code)
                    .get_product_multiline_description_sale()
                )
```
- **Purpose:** Keeps template line descriptions synchronized with product descriptions in all active languages
- **Edge case (L3):** Only updates lines where `line.name` currently equals the default product description; manually overridden descriptions are preserved
- **Performance (L4):** Iterates over all languages and all template lines; for templates with many lines and many languages, this is O(languages * lines) but the set of languages is typically small

##### `_demo_configure_template()`
```python
@api.model
def _demo_configure_template(self):
    demo_template = self.env.ref('sale_management.sale_order_template_1', raise_if_not_found=False)
    if not demo_template or demo_template.sale_order_template_line_ids:
        return
    # Creates lines via Command.create() including optional products section
```
- **Purpose:** Demo data initialization; adds lines to the "Office Furnitures" demo template
- **Creates:** 8 lines -- 4 regular products (some with qty=8), 1 optional section, 3 optional products with qty=0

---

### 2. `sale.order.template.line`

**File:** `models/sale_order_template_line.py`
**Inherits:** None (standalone model)
**Description:** Individual line items within a quotation template: products, sections, subsections, or notes.

#### L1: Field Definitions

```python
class SaleOrderTemplateLine(models.Model):
    _name = 'sale.order.template.line'
    _description = "Quotation Template Line"
    _order = 'sale_order_template_id, sequence, id'
```

##### Basic Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `sale_order_template_id` | `Many2one` | Yes | -- | Parent template reference |
| `sequence` | `Integer` | No | `10` | Display order within the template |
| `company_id` | `Many2one(res.company)` | -- | Related to template | Company scoping |
| `name` | `Text` | No | -- | Custom description; fully translatable |

##### Product Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `product_id` | `Many2one(product.product)` | Conditional | -- | Product to add to SO |
| `product_uom_id` | `Many2one(uom.uom)` | Conditional | From product | Unit of measure |
| `product_uom_qty` | `Float` | Yes | `1` | Quantity to pre-fill |
| `allowed_uom_ids` | `Many2many(uom.uom)` | -- | Computed | UoMs compatible with the product |

##### Display / Layout Fields

| Field | Type | Selection Values | Default | Description |
|-------|------|-------------------|---------|-------------|
| `display_type` | `Selection` | `line_section`, `line_subsection`, `line_note` | `False` | Type of line; determines UI rendering |
| `parent_id` | `Many2one(self)` | -- | Computed | Parent section for hierarchy |
| `is_optional` | `Boolean` | -- | `False` | Whether the line/section is optional in the portal |

#### L2: Field Details

**`display_type` -- Line Type Classification**

Three distinct types control how the line renders:

| Value | Meaning | Product Required | Qty Required | UoM Required |
|-------|---------|-----------------|-------------|-------------|
| `False` (default) | Normal product line | Yes | Yes | Yes |
| `line_section` | Section header grouping lines | No | No (must be 0) | No (must be null) |
| `line_subsection` | Sub-section under a section | No | No (must be 0) | No (must be null) |
| `line_note` | Informational note | No | No (must be 0) | No (must be null) |

**`is_optional` -- Portal Editability Flag**

- **Default:** `False`
- **Copy:** `True` -- copied when template line is duplicated
- **Purpose (L3):** Lines or sections marked optional are editable in the customer portal (quantity can be changed from 0 to a positive value)
- **Edge case (L3):** An optional line nested under a non-optional section is NOT optional from the portal's perspective; `_is_line_optional()` on `sale.order.line` implements this hierarchical check

**`parent_id` -- Section Hierarchy**

- **Compute:** `_compute_parent_id` walks the template's lines in sequence order
- **Algorithm:** Tracks `last_section` and `last_sub` as it iterates; assigns `parent_id` as follows:
  - Section (`line_section`) -> `parent_id = False` (sections are root-level)
  - Subsection (`line_subsection`) -> `parent_id = last_section`
  - Regular line -> `parent_id = last_sub or last_section`
- **Edge case (L3):** Lines before the first section have `parent_id = False`

**`allowed_uom_ids` -- Dynamic UoM Domain**

```python
@api.depends('product_id', 'product_id.uom_id', 'product_id.uom_ids')
def _compute_allowed_uom_ids(self):
    for option in self:
        option.allowed_uom_ids = option.product_id.uom_id | option.product_id.uom_ids
```
- **Computation:** Union of the product's `uom_id` and its additional `uom_ids` (alternate units)
- **UI Effect:** The `product_uom_id` field uses `domain="[('id', 'in', allowed_uom_ids)]"` to restrict available UoMs

**`product_uom_id` -- Unit of Measure**

- **Compute:** `_compute_product_uom_id` defaults to `product_id.uom_id`
- **Store:** `store=True, readonly=False, precompute=True`
- **Domain:** Restricted to `allowed_uom_ids`

#### L3: Constraints

```python
_accountable_product_id_required = models.Constraint(
    'CHECK(display_type IS NOT NULL OR (product_id IS NOT NULL AND product_uom_id IS NOT NULL))',
    'Missing required product and UoM on accountable sale quote line.',
)
_non_accountable_fields_null = models.Constraint(
    'CHECK(display_type IS NULL OR (product_id IS NULL AND product_uom_qty = 0 AND product_uom_id IS NULL))',
    'Forbidden product, quantity and UoM on non-accountable sale quote line',
)
```

- **Odoo 18 to 19 Change (L4):** Constraints are defined using `models.Constraint` class instead of `_sql_constraints` tuples. This is the new declarative syntax in Odoo 19.
- **`_accountable_product_id_required`:** For regular product lines (`display_type=False`), both `product_id` AND `product_uom_id` must be set
- **`_non_accountable_fields_null`:** For section/note lines (`display_type` set), `product_id`, `product_uom_qty`, and `product_uom_id` must all be null/zero

#### L3: CRUD Method Overrides

##### `create(vals_list)`
```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('display_type', self.default_get(['display_type'])['display_type']):
            vals.update(product_id=False, product_uom_qty=0, product_uom_id=False)
    return super().create(vals_list)
```
- **Auto-clearing:** If `display_type` is set (section/note), automatically nullifies `product_id`, `product_uom_qty`, and `product_uom_id` to enforce constraint compliance
- **Edge case (L3):** Uses `default_get` as fallback when `display_type` is not in `vals`

##### `write(vals)`
```python
def write(self, vals):
    if 'display_type' in vals and self.filtered(lambda line: line.display_type != vals.get('display_type')):
        raise UserError(_("You cannot change the type of a sale quote line..."))
    return super().write(vals)
```
- **Protection:** Prevents changing `display_type` on existing lines (would violate constraints); user must delete and recreate
- **Failure mode:** `UserError` with message about recreating the line

#### L3: `_product_id_domain()` -- Combo Product Exclusion
```python
@api.model
def _product_id_domain(self):
    return [('sale_ok', '=', True), ('type', '!=', 'combo')]
```
- **Cross-model:** Filters out `combo` product types from the template line product picker
- **Reason:** Combo products require the configurator and cannot be preconfigured in templates
- **Edge case (L3):** Portal combo lines behave differently and are handled separately

#### L3: `_prepare_order_line_values()` -- Template-to-SO Conversion
```python
def _prepare_order_line_values(self):
    self.ensure_one()
    vals = {
        'display_type': self.display_type,
        'product_id': self.product_id.id,
        'product_uom_qty': self.product_uom_qty,
        'product_uom_id': self.product_uom_id.id,
        'is_optional': self.is_optional,
        'sequence': self.sequence,
    }
    if self.name:
        vals['name'] = self.name
    return vals
```
- **Return type:** `dict` -- create values for `sale.order.line`
- **Naming:** Only copies `name` if non-empty; empty name lets the SO line's `_compute_name` fall back to product description
- **Edge case (L3):** Does not copy `parent_id` (section hierarchy is recomputed on the SO line side via `sale_order_line._compute_parent_id`)

---

### 3. `sale.order` (Extended)

**File:** `models/sale_order.py`
**Inherits:** `sale.order` (from `sale` module)
**Description:** Adds `sale_order_template_id` field and all its cascading computes to the sale order.

#### L1: Field Addition

```python
sale_order_template_id = fields.Many2one(
    comodel_name='sale.order.template',
    string="Quotation Template",
    compute='_compute_sale_order_template_id',
    store=True, readonly=False, check_company=True, precompute=True,
    domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
```

##### Field Attributes

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `compute` | `_compute_sale_order_template_id` | Derives from company default |
| `store` | `True` | Persisted so it can be manually overridden |
| `readonly` | `False` | Allows manual template selection |
| `check_company` | `True` | Enforces company consistency |
| `precompute` | `True` | Computed eagerly on load (Odoo 18 to 19 optimization) |
| `domain` | Multi-company filter | Only show templates from current or no company |

#### L2: Cascading Compute Chain

When `sale_order_template_id` changes, multiple fields on the SO are updated:

```python
# Template note replaces SO note (if template note is non-empty)
@api.depends('partner_id', 'sale_order_template_id')
def _compute_note(self): ...

# Template's require_signature overrides SO setting
@api.depends('sale_order_template_id')
def _compute_require_signature(self): ...

# Template's require_payment overrides SO setting
@api.depends('sale_order_template_id')
def _compute_require_payment(self): ...

# Template's prepayment_percent (only if require_payment is True)
@api.depends('sale_order_template_id')
def _compute_prepayment_percent(self): ...

# Template's validity days -> SO validity_date
@api.depends('sale_order_template_id')
def _compute_validity_date(self): ...

# Template's invoicing journal
@api.depends('sale_order_template_id')
def _compute_journal_id(self): ...
```

#### L3: Onchange: `_onchange_sale_order_template_id()`

```python
@api.onchange('sale_order_template_id')
def _onchange_sale_order_template_id(self):
    if not self.sale_order_template_id:
        return

    sale_order_template = self.sale_order_template_id.with_context(lang=self.partner_id.lang)

    order_lines_data = [fields.Command.clear()]
    order_lines_data += [
        fields.Command.create(line._prepare_order_line_values())
        for line in sale_order_template.sale_order_template_line_ids
    ]

    # set first line to sequence -99, so a resequence on first page doesn't cause
    # following page lines (that all have sequence 10 by default) to get mixed in the first page
    if len(order_lines_data) >= 2:
        order_lines_data[1][2]['sequence'] = -99

    self.order_line = order_lines_data
```

- **Effect (L3):** Completely replaces all existing order lines with template lines
- **Language:** Uses `partner_id.lang` context so product descriptions render in the customer's language
- **Sequence hack (L3):** First real line gets `sequence=-99` to prevent it from being grouped onto page 1 with section headers that have the default `sequence=10`
- **`Command.clear()`:** Clears existing lines before adding new ones

#### L3: Onchange: `_onchange_partner_id()` -- Template Reload

```python
@api.onchange('partner_id')
def _onchange_partner_id(self):
    if self._origin or not self.sale_order_template_id:
        return

    def line_eqv(line, t_line):
        return line and t_line and all(
            line[fname] == t_line[fname]
            for fname in ['product_id', 'product_uom_id', 'product_uom_qty', 'display_type']
        )

    lines = self.order_line
    t_lines = self.sale_order_template_id.sale_order_template_line_ids

    if all(starmap(line_eqv, zip_longest(lines, t_lines))):
        self._onchange_sale_order_template_id()
```

- **Purpose:** If the partner changes and the user has not modified the order lines, reapply the template with the new partner's language
- **Check:** Uses `zip_longest` to compare lines pairwise; considers a line "unmodified" only if `product_id`, `product_uom_id`, `product_uom_qty`, and `display_type` all match
- **Guard:** `_origin` check prevents firing on already-saved records (their lines are considered "intentionally set")

#### L3: Onchange: `_onchange_company_id()`

```python
@api.onchange('company_id')
def _onchange_company_id(self):
    """Trigger quotation template recomputation on unsaved records company change"""
    super()._onchange_company_id()
    if self._origin.id:
        return
    self._compute_sale_order_template_id()
```

- **Purpose:** Manually recomputes template assignment when the company changes on an unsaved order
- **Note (L3):** The comment explains why `_compute_sale_order_template_id` does NOT use `@api.depends('company_id')` -- it would create a dependency loop when the compute itself sets `company_id` on new orders

#### L3: `_get_confirmation_template()`

```python
def _get_confirmation_template(self):
    self.ensure_one()
    return self.sale_order_template_id.mail_template_id or super()._get_confirmation_template()
```
- **Override:** Returns the template-specific email template if set; falls back to the default SO confirmation template

#### L3: `action_confirm()` -- Template Mail on Backend Confirmation

```python
def action_confirm(self):
    res = super().action_confirm()

    if self.env.context.get('send_email'):
        return res

    for order in self:
        if order.sale_order_template_id.mail_template_id:
            order._send_order_notification_mail(order.sale_order_template_id.mail_template_id)
    return res
```
- **Trigger:** Fires when confirming from backend (not portal) without the `send_email` context flag
- **Reasoning:** Portal confirmation sends the email automatically via `send_email=True` context; backend confirmation with a template-defined mail template needs explicit sending
- **Edge case (L3):** Checks `send_email` context to avoid double-sending when super already sent

---

### 4. `sale.order.line` (Extended)

**File:** `models/sale_order_line.py`
**Inherits:** `sale.order.line` (from `sale` module)
**Description:** Adds optional line support and template-aware description handling.

#### L1: Field Addition

```python
is_optional = fields.Boolean(
    string="Optional Line",
    copy=True,
    default=False,
)
```

#### L2: `_compute_name()` Override -- Template Description

```python
@api.depends('product_id')
def _compute_name(self):
    # Take the description on the order template if the product is present in it
    super()._compute_name()
    for line in self:
        if line.product_id and line.order_id.sale_order_template_id and line._use_template_name():
            for template_line in line.order_id.sale_order_template_id.sale_order_template_line_ids:
                if line.product_id == template_line.product_id and template_line.name:
                    lang = line.order_id.partner_id.lang
                    line.name = (
                        template_line.with_context(lang=lang).name
                        + line.with_context(lang=lang)._get_sale_order_line_multiline_description_variants()
                    )
                    break
```

- **Precedence:** Template-specific description overrides the default product description
- **Language:** Uses `partner_id.lang` for proper translation
- **Composition:** Template name + variant descriptions (appended via `_get_sale_order_line_multiline_description_variants()`)
- **Break condition:** Uses first matching template line; subsequent matches are ignored

#### L3: `_use_template_name()` -- Hook for Configured Products

```python
def _use_template_name(self):
    self.ensure_one()
    return True
```

- **Purpose (L3):** Extension point for modules like `event` or `sale_product_configurator` where template descriptions should be suppressed in favor of configuration-specific descriptions
- **Override pattern (L3):** Event tickets and booth lines return `False` to use their own description logic

#### L3: `_is_line_optional()` -- Hierarchical Optional Check

```python
def _is_line_optional(self):
    self.ensure_one()
    return (
        self.parent_id.is_optional
        or (
            self.parent_id.display_type == 'line_subsection'
            and self.parent_id.parent_id.is_optional
        )
    )
```

- **Logic:** A line is optional if its immediate parent section is optional, OR if its parent is a subsection AND the grandparent (root section) is optional
- **Edge case (L3):** Lines without a parent (root-level) or with non-optional parents return `False`

#### L3: `_can_be_edited_on_portal()` -- Portal Editability Gate

```python
def _can_be_edited_on_portal(self):
    return super()._can_be_edited_on_portal() and self._is_line_optional()
```

- **Purpose (L3):** Combines the parent model's editability check with the optional-line check; portal users can only edit quantities on optional lines
- **Effect (L4):** This prevents non-optional line quantities from being modified in the portal, enforcing the quote-as-signed integrity

---

### 5. `res.company` (Extended)

**File:** `models/res_company.py`
**Inherits:** `res.company`
**Description:** Adds the `sale_order_template_id` field for setting a company-wide default quotation template.

```python
class ResCompany(models.Model):
    _inherit = "res.company"
    _check_company_auto = True

    sale_order_template_id = fields.Many2one(
        "sale.order.template", string="Default Sale Template",
        domain="['|', ('company_id', '=', False), ('company_id', '=', id)]",
        check_company=True,
    )
```

- **`_check_company_auto = True`:** Enables automatic company consistency validation on all related fields across the model
- **`check_company=True`:** Ensures the template belongs to the same company as the record
- **`domain`:** Only templates from the same company (or no company) are selectable
- **Effect:** New sale orders created for this company automatically inherit this template via `sale.order._compute_sale_order_template_id()`

---

### 6. `res.config.settings` (Extended)

**File:** `models/res_config_settings.py`
**Inherits:** `res.config.settings`
**Description:** Settings wizard that controls the template feature toggle and default template assignment.

#### Fields

```python
group_sale_order_template = fields.Boolean(
    "Quotation Templates", implied_group='sale_management.group_sale_order_template')

company_so_template_id = fields.Many2one(
    related="company_id.sale_order_template_id", string="Default Template",
    readonly=False,
    domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
```

#### `set_values()` -- Side Effect on Disable

```python
def set_values(self):
    if not self.group_sale_order_template:
        if self.company_so_template_id:
            self.company_so_template_id = False
        companies = self.env['res.company'].sudo().search([
            ('sale_order_template_id', '!=', False)
        ])
        if companies:
            companies.sale_order_template_id = False
    super().set_values()
```

- **Side effect:** Disabling the "Quotation Templates" feature (`group_sale_order_template=False`) clears the default template from all companies
- **`sudo()`:** Required because the wizard may run as a non-admin user who cannot write to `res.company` directly
- **Ordering:** Clears template before calling `super().set_values()` to avoid stale references

---

### 7. `digest.digest` (Extended)

**File:** `models/digest.py`
**Inherits:** `digest.digest`
**Description:** Adds the `kpi_all_sale_total` KPI to the digest emails, showing total sales amount for the period.

#### Fields

```python
kpi_all_sale_total = fields.Boolean('All Sales')
kpi_all_sale_total_value = fields.Monetary(
    compute='_compute_kpi_sale_total_value')
```

#### `_compute_kpi_sale_total_value()`

```python
def _compute_kpi_sale_total_value(self):
    if not self.env.user.has_group('sales_team.group_sale_salesman_all_leads'):
        raise AccessError(_("Do not have access, skip this data for user's digest email"))

    self._calculate_company_based_kpi(
        'sale.report',
        'kpi_all_sale_total_value',
        date_field='date',
        additional_domain=[('state', 'not in', ['draft', 'cancel', 'sent'])],
        sum_field='price_total',
    )
```

- **Security:** Raises `AccessError` if the user lacks `group_sale_salesman_all_leads`; this prevents leaking sales data to users without sales access
- **Domain filter:** Only counts orders in states other than `draft`, `cancel`, and `sent` (i.e., confirmed/sale/done orders)
- **Aggregation:** Uses `sale.report` model which denormalizes the `price_total` from confirmed orders

#### `_compute_kpis_actions()`

```python
def _compute_kpis_actions(self, company, user):
    res = super()._compute_kpis_actions(company, user)
    res['kpi_all_sale_total'] = 'sale.report_all_channels_sales_action?menu_id=%s' % self.env.ref('sale.sale_menu_root').id
    return res
```
- **Drill-down action:** The KPI value in the digest email links to the "Sales Analysis" report

---

## Controllers

### `sale_management.controllers.portal.CustomerPortal`

**File:** `controllers/portal.py`
**Inherits:** `sale.controllers.portal.CustomerPortal`
**Description:** Extends the portal controller with an endpoint for customers to update optional line quantities from the customer portal.

#### `portal_quote_option_update()` -- JSON-RPC Endpoint

```python
@route(['/my/orders/<int:order_id>/update_line_dict'], type='jsonrpc', auth="public", website=True)
def portal_quote_option_update(self, order_id, line_id, access_token=None, remove=False, input_quantity=False, **kwargs):
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `order_id` | `int` | `sale.order` database ID |
| `line_id` | `int` | `sale.order.line` database ID |
| `access_token` | `str` | Portal access token for the order |
| `remove` | `bool` | If `True`, decrement quantity by 1 |
| `input_quantity` | `float` | Direct quantity value to set (overrides `remove`) |
| `**kwargs` | `dict` | Unused parameters (forward compatibility) |

**Security flow (L3):**
1. `_document_check_access('sale.order', order_id, access_token=access_token)` verifies the caller has portal rights
2. `order_sudo._can_be_edited_on_portal()` double-checks the order-level editability
3. `order_line._can_be_edited_on_portal()` verifies the specific line is optional
4. The `order_line.order_id != order_sudo` check prevents cross-order manipulation

**Business logic:**

```python
if input_quantity is not False:
    quantity = input_quantity
else:
    number = -1 if remove else 1
    quantity = max((order_line.product_uom_qty + number), 0)

if order_line.product_type == 'combo':
    # for combo products, we update the quantities of the combo items too
    combo_item_lines = order_line._get_linked_lines().filtered('combo_item_id')
    combo_item_lines.update({'product_uom_qty': quantity})

order_line.product_uom_qty = quantity
```

- **Combo product handling (L3):** When the optional line is a combo product, updating its quantity also updates all linked `combo_item` child lines to the same quantity. This maintains combo integrity on the portal.
- **Floor:** Quantity cannot go below 0
- **Return:** Method returns `None` (no value) on any failure, which the JS frontend interprets as a silent no-op

**Auth:** `auth="public", website=True` -- allows unauthenticated portal users with a valid `access_token` to update their own optional line quantities.

---

## Security

### Access Control Lists

**File:** `security/ir.model.access.csv`

| ID | Model | Group | R | W | C | D |
|----|-------|-------|---|---|---|---|
| `access_sale_order_template` | `sale.order.template` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 |
| `access_sale_order_template_manager` | `sale.order.template` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |
| `access_sale_order_template_system` | `sale.order.template` | `base.group_system` | 1 | 0 | 0 | 0 |
| `access_sale_order_template_line` | `sale.order.template.line` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 |
| `access_sale_order_template_line_manager` | `sale.order.template.line` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |

**Key observations (L4):**

- Salespersons can only READ templates; they cannot create/edit/delete -- enforces template standardization
- Only managers can modify templates
- The `base.group_system` entry grants read-only system-level access (e.g., for automated reports)
- The `is_optional` field on `sale.order.line` has no ACL restrictions -- it is copyable by salespersons but only managers can edit the template definitions

### Record Rules

**File:** `security/sale_management_security.xml`

```xml
<record id="sale_order_template_rule_company" model="ir.rule">
    <field name="name">Quotation Template multi-company</field>
    <field name="model_id" ref="model_sale_order_template"/>
    <field name="domain_force">[('company_id', 'in', company_ids + [False])]</field>
</record>
```

- **Multi-company scoping:** Templates without a company (`company_id=False`) are visible to all companies
- **Template lines inherit:** `sale.order.template.line` has no explicit record rule; it inherits from its `sale_order_template_id` through `company_id` relation

### Security Groups

```xml
<record id="group_sale_order_template" model="res.groups">
    <field name="name">Quotation Templates</field>
</record>
```

- **Group:** `sale_management.group_sale_order_template`
- **Default:** Automatically assigned to all internal users (`base.group_user`) via demo data on module install
- **Purpose:** Controls visibility of the template field on sale order forms and the "Quotation Templates" menu

---

## Views

### `sale.order.template` Form View

**Key structural elements:**

- **Notebook tabs:** "Lines" (with `so_template_line_o2m` widget) and "Terms & Conditions"
- **`so_template_line_o2m` widget:** Custom field widget rendering template lines with subsection support
- **Line list controls:** "Add a product", "Add a section", "Add a note" action buttons
- **`is_optional` column:** Hidden in the list (`column_invisible="True"`) but used by the JS dropdown for toggling
- **Sections:** Grouped into "Sale Info" (general settings) and "SO Confirmation" (signature/payment)
- **`number_of_days`:** Displayed with a "days" label suffix for clarity
- **`mail_template_id`:** Rendered with `context="{'default_model': 'sale.order'}"` pre-fill
- **`journal_id`:** Company-dependent journal picker restricted to `type='sale'`

### `sale.order` Form View Extension

**Template field placement:** Inserted after `partner_shipping_id` in the form header, before the order lines.

```xml
<field name="sale_order_template_id"
    options="{'no_create': True}"
    readonly="state in ['cancel', 'sale']"
    groups="sale_management.group_sale_order_template"/>
```

- **`readonly`:** Locked once the order is cancelled or confirmed
- **`no_create`:** Users must select from existing templates (prevents accidental template creation from the SO form)
- **`groups`:** Only visible to users with the template group

**Optional section toggle (L3):** The `is_optional` field on `sale.order.line` is shown in a hidden group and controlled via the JS dropdown:

```xml
<field name="is_optional"
    invisible="display_type not in ['line_section', 'line_subsection']"
    readonly="1"/>
```

---

## Static Web Assets

### JS Templates for Optional Line Toggle

**`sale_order_line_field.xml`** and **`sale_order_template_line_field.xml`** both inject a `DropdownItem` into the list record row's action dropdown:

```xml
<DropdownItem
    onSelected="() => this.toggleIsOptional(record)"
    attrs="{ 'class': disableOptionalButton ? 'disabled' : '' }"
>
    <span t-if="record.data.is_optional">Unset Optional</span>
    <span t-else="">Set Optional</span>
</DropdownItem>
```

- **Behavior (L3):** Toggles `is_optional` between `True` and `False` via the `toggleIsOptional` method
- **`disableOptionalButton`:** Returns `True` for lines that cannot be made optional (e.g., non-section lines that are already optional product lines)
- **Inheritance mode difference:** Template lines use `t-inherit-mode="primary"` (replaces the target), while SO lines use `t-inherit-mode="extension"` (modifies in place)

### Portal Templates

**`sale_order_portal_optional_product_quantity`:** Customizes the quantity input in the customer portal for optional lines.

- **Condition:** Only shows the +/- quantity controls when `line._can_be_edited_on_portal()` returns `True`
- **Otherwise:** Renders as read-only quantity + UoM display
- **Replaces:** Both the regular product quantity cell (`td_product_quantity`) and combo product cell (`td_combo_quantity`)
- **XPath targets:**
  - `//td[@name='td_product_quantity']/div[@id='quote_qty']` -- standard product lines
  - `//td[@name='td_combo_quantity']/div[@id='quote_qty']` -- combo product lines

---

## Data

### Demo Data

**`data/sale_order_template_demo.xml`:**

1. Adds `group_sale_order_template` to all `base.group_user` members (makes template feature visible by default in demo)
2. Creates `sale_order_template_1` named "Office Furnitures" with `number_of_days=45`
3. Calls `_demo_configure_template()` to populate 8 lines:
   - 4 standard products (2 with `product_uom_qty=8`)
   - 1 optional section (`display_type='line_section'`, `is_optional=True`)
   - 3 optional products (`product_uom_qty=0`)

### Digest Data

**`data/digest_data.xml`:**

1. Enables `kpi_all_sale_total` on the default digest (`digest.digest_digest_default`)
2. Registers two digest tips for sales managers: "Configurable Products" and "Matrix Grid"

---

## Odoo 18 to Odoo 19 Changes (L4)

### 1. `models.Constraint` Class Replaces `_sql_constraints`

In Odoo 18, constraints used `_sql_constraints` tuples:

```python
# Odoo 18
_sql_constraints = [
    ('check_product_required', CHECK(...), 'Error message'),
]
```

In Odoo 19, `models.Constraint` class is used as a class-level declarative declaration:

```python
# Odoo 19
_accountable_product_id_required = models.Constraint(
    'CHECK(...)',
    'Error message',
)
```

This change moves constraint definitions from a list of tuples to declarative class attributes, improving readability and consistency with other Odoo 19 ORM features.

### 2. `precompute=True` on Template UoM Fields

The `product_uom_id` field on `sale.order.template.line` uses `precompute=True`:

```python
product_uom_id = fields.Many2one(
    comodel_name='uom.uom',
    string="Unit",
    domain="[('id', 'in', allowed_uom_ids)]",
    compute='_compute_product_uom_id',
    store=True, readonly=False, precompute=True)
```

- **Odoo 18:** `precompute` was introduced but not consistently used in templates
- **Odoo 19:** Eager computation eliminates flicker and ensures the UoM is available immediately on form load

### 3. `is_optional` Field for Portal-Editable Optional Sections (L4)

The `is_optional` field on both `sale.order.template.line` and `sale.order.line` was enhanced in Odoo 19:

- The field exists in Odoo 18 but the portal integration was improved
- The `_can_be_edited_on_portal()` override on `sale.order.line` combines with `_is_line_optional()` for a two-level check (direct + hierarchical)
- The JS `toggleIsOptional` dropdown in list views uses the `disableOptionalButton` guard to prevent invalid state transitions

### 4. Section Hierarchy (`parent_id`) Computation

The `_compute_parent_id` method on `sale.order.template.line` was enhanced to properly track the `last_sub` (subsection) state across iterations, enabling proper three-level hierarchy: section > subsection > product line.

### 5. `sale_order_template_id` Precompute on `sale.order`

The `sale_order_template_id` field uses `precompute=True`:

```python
sale_order_template_id = fields.Many2one(
    ...
    compute='_compute_sale_order_template_id',
    store=True, readonly=False, check_company=True, precompute=True,
    ...)
```

- **Effect:** The default template is computed immediately when the SO form loads, before any user interaction
- **Performance (L4):** Reduces form load time by avoiding deferred compute recalculation

### 6. Portal Combo Product Quantity Update (L4)

In Odoo 19, the portal optional line update endpoint (`portal_quote_option_update`) was enhanced to handle `combo` product types:

```python
if order_line.product_type == 'combo':
    combo_item_lines = order_line._get_linked_lines().filtered('combo_item_id')
    combo_item_lines.update({'product_uom_qty': quantity})
```

When a customer updates the quantity of an optional combo product from the portal, all child `combo_item` lines are updated to the same quantity. This ensures the combo structure remains consistent after portal-side edits.

---

## Performance Considerations (L4)

1. **`_update_product_translations()`:** O(languages * template_lines). With 10 languages and 100 lines, performs 1,000 string comparisons and assignments. Typically negligible.

2. **`_compute_parent_id()`:** O(template_lines) per template, uses `grouped()` to batch by template. Efficient for typical template sizes.

3. **`_onchange_sale_order_template_id()`:** Creates N `sale.order.line` records in a single `Command.clear()` + `Command.create()` batch. The `sequence=-99` hack avoids a separate resequence RPC.

4. **`kpi_all_sale_total_value`:** Uses the denormalized `sale.report` table which is pre-computed; no complex JOINs at digest email generation time.

5. **`precompute=True` on template fields:** Trades startup compute cost for faster form rendering, especially beneficial when many SOs are created per session.

6. **`pre_init_hook` bypasses ORM init:** The SQL-level column creation in `pre_init_hook` avoids the ORM recomputing `sale_order_template_id` across potentially millions of existing sale orders on install. This can reduce install time from minutes to milliseconds on large databases.

7. **`portal_quote_option_update` combo update:** The combo item batch `update()` call is more efficient than looping and writing one line at a time; it generates a single SQL `UPDATE` for all combo child lines.

---

## Edge Cases and Known Limitations (L4)

### Template Language Switching
When `_onchange_partner_id()` re-applies the template due to language change, it only triggers if lines are "unmodified" (exact match on 4 fields). A user who manually changed `product_uom_qty` from 1 to 3 will not get the template re-applied, even if switching to a partner with a different language. Workaround: select a new template to fully reset lines.

### Archived Template Cleanup
Archiving a template (`active=False`) clears it from all `res.company` records that reference it, but it does NOT prevent already-confirmed SOs from keeping their line copies. Confirmed orders retain a snapshot of the template lines at confirmation time -- they are not invalidated when the template is archived.

### Combo Products in Templates
The `_product_id_domain()` on template lines excludes `combo` product types. Customers who need combo products in templates must use the `sale_product_configurator` flow instead, which handles combo configuration separately.

### Multi-Company Product Restriction
The `_check_company_id()` constraint on `sale.order.template` uses `product.product._check_company_domain()` for authorization. This checks product-specific company restrictions (if `company_id` is set on the product). However, products without company restrictions (`company_id=False`) are always authorized regardless of template company -- this is intentional, allowing shared products across all companies.

### Template Lines Display Type Change
Once a template line record is created with a `display_type` value (section/note/product), its `display_type` can never be changed via `write()`. The `write()` method raises `UserError` if a type change is attempted. Users must delete and recreate the line. This is enforced at the ORM level to prevent constraint violations.

### Digest KPI AccessError Silent Fail
When `_compute_kpi_sale_total_value()` encounters a user without `group_sale_salesman_all_leads`, it raises `AccessError` rather than returning 0 or filtering the KPI. The digest framework catches this and skips the KPI for that user. The KPI checkbox remains visible in the digest form, but no value is emailed to unauthorized users.