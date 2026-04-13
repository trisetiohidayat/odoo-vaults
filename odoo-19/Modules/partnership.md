---
tags: [odoo, odoo19, modules, partnership, membership, crm, sale]
description: Partner membership program with grade-based pricing for Odoo 19 CE - Full depth L4 documentation
---

# Partnership / Membership Module (`partnership`)

> **Community Edition** | License: LGPL-3
> Odoo 19 CE module for partner membership program with tiered pricing.
> Depends: `crm`, `sale` | Application: No
> Path: `odoo/addons/partnership/`

---

## Table of Contents

1. [L1 - Models Inventory](#1-l1---models-inventory)
2. [L2 - Field Types, Defaults, Constraints](#2-l2---field-types-defaults-constraints)
3. [L3 - Cross-Module, Override Patterns, Workflow Triggers](#3-l3---cross-module-override-patterns-workflow-triggers)
4. [L4 - Version Change Odoo 18 to 19](#4-l4---version-change-odoo-18-to-19)

---

## 1. L1 - Models Inventory

### 1.1 Model Overview

| Model | Type | File | Description |
|-------|------|------|-------------|
| `res.partner.grade` | Concrete | `res_partner_grade.py` | Membership tier definition |
| `res.partner` | Extended | `res_partner.py` | Adds `grade_id` field to partner |
| `sale.order` | Extended | `sale_order.py` | Auto-upgrade partner grade on confirm |
| `product.template` | Extended | `product_template.py` | Adds `service_tracking='partnership'` and `grade_id` |
| `product.pricelist` | Extended | `product_pricelist.py` | Adds `partners_count` and `partners_label` |
| `res.company` | Extended | `res_company.py` | Adds `partnership_label` (company-specific terminology) |
| `res.config.settings` | Extended | `res_config_settings.py` | Configures `partnership_label` |

### 1.2 `res.partner.grade`

Defines a membership tier (e.g., Bronze, Silver, Gold, Platinum).

```python
class ResPartnerGrade(models.Model):
    _name = 'res.partner.grade'
    _order = 'sequence'
    _description = 'Partner Grade'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    name = fields.Char('Level Name', translate=True)
    company_id = fields.Many2one('res.company', 'Company',
                                  default=lambda self: self.env.company)
    default_pricelist_id = fields.Many2one('product.pricelist')
    partners_count = fields.Integer(compute='_compute_partners_count')
    partners_label = fields.Char(related='company_id.partnership_label')
```

**Key role:** Each grade has a `default_pricelist_id`. When a partner's grade is set (or auto-updated), the grade's pricelist is applied to that partner.

**Computed `partners_count`** uses `_read_group` aggregation for efficiency:
```python
def _compute_partners_count(self):
    partners_data = self.env['res.partner']._read_group(
        domain=[('grade_id', 'in', self.ids)],
        groupby=['grade_id'],
        aggregates=['__count'],
    )
    mapped_data = {grade.id: count for grade, count in partners_data}
    for grade in self:
        grade.partners_count = mapped_data.get(grade.id, 0)
```

### 1.3 `res.partner` (Extended)

Adds `grade_id` field to the standard partner model.

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    grade_id = fields.Many2one(
        'res.partner.grade',
        'Partner Level',
        tracking=True,
        group_expand='_read_group_expand_full'
    )
```

The `group_expand` method ensures all grades appear in grouped list views, even if no partner has that grade yet.

### 1.4 `sale.order` (Extended)

Automatically upgrades a partner's grade when a sale order with a partnership product is confirmed.

```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    assigned_grade_id = fields.Many2one(
        'res.partner.grade',
        compute='_compute_partnership',
    )

    @api.constrains('order_line')
    def _constraint_unique_assigned_grade(self):
        for so in self:
            if len(set(so.order_line.mapped('product_id.grade_id'))) > 1:
                raise ValidationError(so.env._(
                    "You cannot confirm Sale Order %(sale_order_name)s because there are products "
                    "assigning different grades.", sale_order_name=so.name,
                ))

    @api.depends('order_line.product_id')
    def _compute_partnership(self):
        for so in self:
            partnership_lines = so.order_line.filtered(
                lambda l: l.service_tracking == 'partnership'
            )
            so.assigned_grade_id = partnership_lines.mapped('product_id.grade_id')[:1]

    def action_confirm(self):
        res = super().action_confirm()
        self._add_partnership()
        return res

    def _add_partnership(self):
        for so in self:
            if not so.assigned_grade_id:
                continue
            so.partner_id.commercial_partner_id.grade_id = so.assigned_grade_id
```

### 1.5 `product.template` (Extended)

Adds partnership service tracking option and grade assignment to products.

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    service_tracking = fields.Selection(
        selection_add=[('partnership', 'Membership / Partnership')],
        ondelete={'partnership': 'set default'}
    )
    grade_id = fields.Many2one('res.partner.grade', string="Assigned Level")

    @api.model
    def _get_saleable_tracking_types(self):
        return super()._get_saleable_tracking_types() + ['partnership']
```

### 1.6 `product.pricelist` (Extended)

```python
class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    partners_count = fields.Integer(compute='_compute_partners_count')
    partners_label = fields.Char(related='company_id.partnership_label')

    def _compute_partners_count(self):
        partners_data = self.env['res.partner']._read_group(
            domain=[('specific_property_product_pricelist', 'in', self.ids)],
            groupby=['specific_property_product_pricelist'],
            aggregates=['__count'],
        )
        mapped_data = {pricelist.id: count for pricelist, count in partners_data}
        for pricelist in self:
            pricelist.partners_count = mapped_data.get(pricelist.id, 0)
```

### 1.7 `res.company` and `res.config.settings`

```python
# res_company.py
class ResCompany(models.Model):
    _inherit = 'res.company'
    partnership_label = fields.Char(
        default=lambda s: s.env._('Members'), translate=True,
        help="Name used to refer to affiliates: partners, members, alumnis, etc...",
    )

# res_config_settings.py
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    partnership_label = fields.Char(
        related='company_id.partnership_label', required=True, readonly=False
    )

    @api.onchange('partnership_label')
    def _onchange_partnership_label(self):
        crm_menu = self.env.ref('partnership.crm_menu_partners', raise_if_not_found=False)
        if crm_menu:
            crm_menu.name = self.partnership_label
```

---

## 2. L2 - Field Types, Defaults, Constraints

### 2.1 Key Field Defaults

| Field | Default | Source |
|-------|---------|--------|
| `res_partner_grade.sequence` | `10` | Field default |
| `res_partner_grade.active` | `True` | Field default |
| `res.company.partnership_label` | `'Members'` (translated) | `default=lambda` |
| `product_template.service_tracking` (partnership) | `'set default'` ondelete | Field definition |
| `product_template.grade_id` | None | Field default |

### 2.2 API Constraints

**`sale.order`:**
```python
@api.constrains('order_line')
def _constraint_unique_assigned_grade(self):
    for so in self:
        if len(set(so.order_line.mapped('product_id.grade_id'))) > 1:
            raise ValidationError(...)
```

This constraint runs on every `order_line` change and prevents a sale order from containing products that would assign different grades. The check uses `set()` of grade_ids to handle None values correctly.

**`res.partner` (write override):**
```python
def write(self, vals):
    if vals.get('grade_id'):
        grade = self.env['res.partner.grade'].browse(vals['grade_id'])
        if grade.default_pricelist_id:
            pricelist = vals.get('specific_property_product_pricelist') or vals.get('property_product_pricelist')
            if pricelist and pricelist != grade.default_pricelist_id.id:
                raise UserError(...)
            else:
                vals['specific_property_product_pricelist'] = grade.default_pricelist_id.id
    return super().write(vals)
```

This is a write-override (not `@api.constrains`) because it needs to modify `vals` before calling `super()`. It auto-applies the grade's pricelist, raising an error if the partner already has a conflicting explicit pricelist.

### 2.3 Computed Fields

**`sale_order.assigned_grade_id`:**
```python
@api.depends('order_line.product_id')
def _compute_partnership(self):
    for so in self:
        partnership_lines = so.order_line.filtered(
            lambda l: l.service_tracking == 'partnership'
        )
        so.assigned_grade_id = partnership_lines.mapped('product_id.grade_id')[:1]
```

Only looks at lines where `service_tracking == 'partnership'`. Takes the first grade found (`:[:1]` on mapped result). Ignores lines with `grade_id = False` (those are filtered naturally since `mapped()` on empty returns empty).

**`product_pricelist.partners_count`:**
Counts partners where this pricelist is set as `specific_property_product_pricelist` -- the partner-specific override. Does NOT count partners using this pricelist as their company-level `property_product_pricelist`.

### 2.4 `group_expand` Pattern

```python
grade_id = fields.Many2one(
    'res.partner.grade', 'Partner Level',
    tracking=True,
    group_expand='_read_group_expand_full'
)
```

The `_read_group_expand_full` method (from base, inherited by `res.partner`) ensures all grades appear as group headers in list views, regardless of whether any partner is assigned that grade. This makes it easy to see empty grades.

---

## 3. L3 - Cross-Module, Override Patterns, Workflow Triggers

### 3.1 Cross-Module Dependencies

**Dependency tree:**
```
partnership
├── crm          (CRM menu, partner views)
└── sale         (sale.order, sale.order.line with service_tracking)
        └── product (product.template with service_tracking field)
        └── product_pricelist (pricelist model)
```

**Partnership does NOT depend on `product_pricelist` explicitly**, but `res_partner_grade.default_pricelist_id` is a Many2one to `product.pricelist`. This creates a soft dependency at the ORM level.

### 3.2 How `service_tracking = 'partnership'` Works

The `service_tracking` selection field on `product.template` originally comes from `sale` or `sale_management`. The partnership module extends it with a new option:

```python
service_tracking = fields.Selection(
    selection_add=[('partnership', 'Membership / Partnership')],
    ondelete={'partnership': 'set default'}
)
```

When `ondelete='set default'`, if a product variant with `service_tracking='partnership'` is deleted, the product template falls back to the default value (`'no'` in the base sale module, meaning no tracking).

### 3.3 Workflow Trigger: Sale Order Confirmation

The complete flow when a partner purchases a membership product:

```
1. Product configured:
   service_tracking = 'partnership'
   grade_id = 'Gold Partner' (a res.partner.grade)

2. Sale order created with that product:
   _compute_partnership()
   → filters order_line where service_tracking == 'partnership'
   → assigned_grade_id = product.grade_id = 'Gold Partner'

3. User clicks "Confirm Sale":
   action_confirm()
     → super().action_confirm()   [creates picking, invoice draft, etc.]
     → _add_partnership()

4. _add_partnership():
   → partner.commercial_partner_id.grade_id = 'Gold Partner'

5. res.partner.write() override:
   → grade.default_pricelist_id applied as specific_property_product_pricelist
   → All subsequent orders use Gold Partner pricelist
```

### 3.4 `commercial_partner_id` Usage

```python
so.partner_id.commercial_partner_id.grade_id = so.assigned_grade_id
```

This is critical: `partner_id` on a sale order may be a child contact (e.g., `partner_id = Contact A`, which belongs to `Commercial Entity B`). Setting `grade_id` on the contact would be wrong -- the grade belongs to the commercial entity. Using `commercial_partner_id` ensures the grade is set on the correct record.

### 3.5 Pricelist Auto-Application Logic

The write override on `res.partner` handles this sequence:

```
Case 1: Partner has NO explicit pricelist
  → grade's default_pricelist_id applied automatically
  → vals['specific_property_product_pricelist'] = grade.default_pricelist_id.id

Case 2: Partner has explicit pricelist SAME as grade's
  → No conflict, auto-apply proceeds

Case 3: Partner has explicit pricelist DIFFERENT from grade's
  → UserError raised: "You are trying to assign two different pricelists"

Case 4: Grade has no default_pricelist_id
  → No auto-application, grade is set without changing pricelist
```

### 3.6 `partnership_label` Configuration

The `partnership_label` field on `res.company` enables terminology customization without modifying code:

- Default: `'Members'` (translated via `lambda s: s.env._('Members')`)
- Can be changed to `'Partners'`, `'Affiliates'`, `'Clients'`, etc.
- The `_onchange_partnership_label` method also updates the CRM menu name:
  ```python
  crm_menu = self.env.ref('partnership.crm_menu_partners', raise_if_not_found=False)
  if crm_menu:
      crm_menu.name = self.partnership_label
  ```
  Uses `raise_if_not_found=False` to gracefully handle cases where the menu reference doesn't exist.

### 3.7 `sale_partner` Module Dependency

The `grade_id` field on `product.product` (not `product.template`) is typically added by the `sale_partner` module (part of the sale apps). The partnership module only adds `grade_id` to `product.template`. In practice, both are needed for full functionality: the template's grade propagates to variants.

---

## 4. L4 - Version Change Odoo 18 to 19

### 4.1 Overview of Changes

The `partnership` module is a lightweight extension module. Most of the Odoo 18 to 19 changes relevant here are in the base `sale`, `product`, and `res.partner` models that partnership extends. The module itself has minimal Odoo 18 to 19 specific changes in its own code.

### 4.2 Changes in Odoo 19 Affecting Partnership

#### 4.2.1 `sale.order.line` Product Variant Resolution

In **Odoo 18**, the `service_tracking` field was on `product.product` (variant level). In **Odoo 19**, it moved to `product.template` with `sale_management` extending it. The partnership module extends `product.template`:

```python
service_tracking = fields.Selection(
    selection_add=[('partnership', 'Membership / Partnership')],
    ondelete={'partnership': 'set default'}
)
```

This means in Odoo 19, the `grade_id` on the template is the authoritative source, and variants inherit from the template unless explicitly set differently.

#### 4.2.2 `product.template` `_get_saleable_tracking_types` Extension

```python
@api.model
def _get_saleable_tracking_types(self):
    return super()._get_saleable_tracking_types() + ['partnership']
```

This method (added by partnership module) ensures that `'partnership'` is recognized as a valid saleable service tracking type in product configuration UIs and reports.

#### 4.2.3 `_read_group_expand_full` Availability

The `group_expand='_read_group_expand_full'` on `grade_id` works correctly in Odoo 19 because `_read_group_expand_full` is defined in `base` and available for all partner searches. This was the same in Odoo 18.

#### 4.2.4 `res.partner` Write Override Pattern

The write override in Odoo 19 (and Odoo 18) uses `vals` modification before calling `super()`:

```python
def write(self, vals):
    if vals.get('grade_id'):
        # Modify vals before calling super
        vals['specific_property_product_pricelist'] = grade.default_pricelist_id.id
    return super().write(vals)
```

This is the correct Odoo ORM pattern. The same pattern works in Odoo 18 and 19. No API changes were needed for this module.

### 4.3 Module Structure (No Manifest Changes)

```python
{
    'name': 'Partnership / Membership',
    'version': '1.0',
    'category': 'Sales/CRM',
    'depends': ['crm', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/res_partner_grade_data.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/res_partner_grade_views.xml',
        'views/product_template_views.xml',
        'views/product_pricelist_views.xml',
        'views/partnership_menu.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

Notable: No `'demo'` key and no `'installable'` (defaults to True). No hooks or migration scripts needed -- the module is purely declarative.

### 4.4 Performance Characteristics

| Operation | Performance Impact |
|-----------|-------------------|
| `_compute_partners_count` on `res_partner_grade` | O(n) where n = partners per grade, using `_read_group` (single SQL query) |
| `_compute_partners_count` on `product_pricelist` | O(m) where m = partners per pricelist, using `_read_group` |
| `sale.order` confirmation with `_add_partnership` | O(1) write on partner record |
| `res.partner` write with `grade_id` change | O(1) but may cascade to pricelist computation |

The module is extremely lightweight -- all heavy lifting (pricelist application) happens at the ORM level through the standard Odoo pricing engine.

### 4.5 Extension Points

| Point | Method | Notes |
|-------|--------|-------|
| Add custom grade validation | Override `write()` on `res.partner.grade` | e.g., require minimum partner count |
| Prevent downgrade | Override `_add_partnership` on `sale.order` | Add check comparing current vs assigned grade |
| Custom grade propagation | Override `_compute_partnership` | e.g., look at multiple product grades |
| Add grade-based discount | Override product pricelist logic | Use `sale_order.assigned_grade_id` in `_compute_price_unit` |

### 4.6 Security

Access to `res.partner.grade` is controlled by `security/ir.model.access.csv`. The module does not define any record rules -- grade visibility follows standard partner visibility.

Key ACL considerations:
- `grade_id` on `res.partner` is `tracking=True` -- changes are logged in chatter
- No company-dependent fields on `res_partner_grade` (has `company_id` but no `company_dependent=True`)
- Pricelist application happens server-side in `write()` override, not in onchange

### 4.7 Key Files Reference

| File | Content |
|------|---------|
| `models/res_partner_grade.py` | Grade model with `partners_count` compute |
| `models/res_partner.py` | Partner extension with grade field and write override |
| `models/sale_order.py` | Sale order extension with grade assignment on confirm |
| `models/product_template.py` | Template extension with `service_tracking` and `grade_id` |
| `models/product_pricelist.py` | Pricelist extension with `partners_count` |
| `models/res_company.py` | Company extension with `partnership_label` |
| `models/res_config_settings.py` | Settings page with `partnership_label` |
| `data/res_partner_grade_data.xml` | Demo grades (Bronze, Silver, Gold) |

### 4.8 Related Documentation

- [Modules/Sale](Modules/sale.md) -- sale.order and service_tracking
- [Modules/Product](Modules/product.md) -- product.template variants and pricing
- [Modules/res.partner](Modules/res.partner.md) -- Partner model
- [Modules/CRM](Modules/CRM.md) -- CRM integration

---
