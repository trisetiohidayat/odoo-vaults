---
uid: product_variant
title: Product Variants & Attribute Configuration (product module)
type: Reference
subjects: ['product', 'product_variant', 'pricelist', 'odoo19', '#orm', '#modules']
description: Complete reference for product.product, product.template, attribute/value models, PTAL/PTAV/PTAE configuration, variant generation engine, price computation cascade, and Odoo 18 to 19 changes. L4 depth with performance patterns, security analysis, and extension points.
create_date: 2026-04-11
modify_date: 2026-04-11
module_code: product
odoo_version: 19
level: 4
---

# Product Variants & Attribute Configuration

> **Module**: `product`
> **Source**: `odoo/addons/product/models/`
> **Odoo Version**: 19 (Community Edition)
> **Important Note**: In Odoo 19, the `product_variant` functionality is fully integrated into the `product` module. There is no separate `product_variant` module. All variant models (product.product, PTAL, PTAV, PTAE, attribute/value) live in `product/models/`.

This document covers the variant configuration system at L4 depth: attribute/value/exclusion models, variant generation engine internals, combination possibility checking, the `combination_indices` lookup mechanism, and extension patterns.

---

## Table of Contents

1. [[#Model-Architecture-Overview]]
2. [[#product.product-Variant-Model]]
3. [[#product.template-Attribute-Configuration]]
4. [[#Attribute-Value-and-Configuration-Models]]
5. [[#Variant-Generation-Engine]]
6. [[#Variant-Possibility-and-Exclusions]]
7. [[#Price-Extra-Architecture]]
8. [[#L4-Performance-Patterns]]
9. [[#L4-Odoo-18-to-Odoo-19-Changes]]
10. [[#L4-Security-Analysis]]
11. [[#L4-Extension-Points]]

---

## Model Architecture Overview

### Where Variants Live in Odoo 19

In Odoo 19, there is **no separate `product_variant` module**. The variant system is fully integrated into the `product` module:

```
product/
└── models/
    ├── product_template.py           # Template model + variant generation
    ├── product_product.py          # Variant model (delegation _inherits)
    ├── product_attribute.py         # Attribute definitions
    ├── product_attribute_value.py  # Attribute value definitions
    ├── product_template_attribute_line.py   # PTAL (template x attribute)
    ├── product_template_attribute_value.py   # PTAV (materialized value)
    └── product_template_attribute_exclusion.py # PTAE (exclusion rules)
```

The `product.product` model represents individual variants, not a module.

### Delegation Inheritance: Template and Variant Tables

```
product_template (table: product_template)
    │
    │ _inherits by product.product
    ▼
product_product (table: product_product)
    ├── product_tmpl_id FK (cascade delete)
    ├── combination_indices (stored, indexed)
    ├── default_code, barcode, standard_price (variant-level)
    ├── product_template_attribute_value_ids (M2M)
    └── image_variant_1920 (variant image)
```

This is **delegation** (`_inherits`), not classical inheritance:
- `product.product` has its own database table
- Template fields are accessible on variants via the FK delegation mechanism
- Deletion of the template cascades to all its variants

### Variant Identity via `combination_indices`

The `combination_indices` Char field is the key to variant identity:

```python
# product_product._compute_combination_indices()
combination_indices = ','.join(
    sorted(str(id) for id in self.product_template_attribute_value_ids.ids)
)
# Example: "12,45,78" for PTAV IDs [12, 45, 78] regardless of order
```

This produces a **canonical string representation** of the attribute combination, which:
1. Is stored and indexed (btree) for O(log n) lookup
2. Is used in the unique partial index: `UNIQUE (product_tmpl_id, combination_indices) WHERE active IS TRUE`
3. Is the cache key for `_get_variant_id_for_combination()` (ormcache)

### The PTAV Materialization Chain

```
product.attribute (definition)
    │
    └─── 1:N ───→ product.attribute.value (possible values: S/M/L, Red/Blue)
                        │
                        │ (selected on template)
                        ▼
            product.template.attribute.line (PTAL)
            # Maps attribute + allowed values → template
            # Also triggers PTAV creation
                        │
                        ▼
            product.template.attribute.value (PTAV)
            # Materialized value instance for THIS template
            # Has price_extra, exclusion links
            # Lives on product_template_attribute_value table
                        │
                        │ (selected on variant)
                        ▼
            product.product.product_template_attribute_value_ids
            # The M2M that defines which PTAVs make up a variant
```

The PTAV is the **materialization** layer: it takes a PAV (generic value definition) and creates a template-specific instance with template-specific pricing and exclusion data.

---

## product.product (Variant Model)

**File**: `odoo/addons/product/models/product_product.py`

### Model Definition

```python
class ProductProduct(models.Model):
    _name = 'product.product'
    _description = "Product Variant"
    _inherits = {'product.template': 'product_tmpl_id'}  # Delegation
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'default_code, name, id'
    _check_company_domain = models.check_company_domain_parent_of

    # Unique constraint: at most one active variant per combination
    _combination_unique = models.UniqueIndex(
        "(product_tmpl_id, combination_indices) WHERE active IS TRUE"
    )
```

### Variant-Specific Fields

These fields exist on `product.product` and are NOT delegated from `product.template`:

| Field | Type | Store | Index | Description |
|-------|------|-------|-------|-------------|
| `product_tmpl_id` | Many2one | btree | Yes | Parent template (cascade, bypass_search_access) |
| `combination_indices` | Char | btree | Yes | Canonical PTAV ID string (e.g., "12,45,78") |
| `default_code` | Char | btree | Yes | Internal reference (variant-specific, not delegated) |
| `barcode` | Char | btree_not_null | Yes | Barcode (unique per company via _check_barcode_uniqueness) |
| `standard_price` | Float | company_dependent | - | Cost per variant per company |
| `volume` | Float | - | - | Variant-specific volume |
| `weight` | Float | - | - | Variant-specific weight |
| `price_extra` | Float | compute | - | Sum of all PTAV price_extras |
| `lst_price` | Float | compute+inverse | - | list_price + price_extra (UoM-aware) |
| `product_template_attribute_value_ids` | Many2many | - | - | PTAVs defining this variant (via product_variant_combination M2M) |
| `product_template_variant_value_ids` | Many2many | - | - | PTAVs from multi-value lines only |
| `active` | Boolean | - | - | Independent of template; drives unique constraint |
| `image_variant_1920` | Image | - | - | Variant-specific image |
| `image_variant_1024/512/256/128` | Image | store | - | Resized variants |
| `write_date` | Datetime | store | - | Synced from template for HTTP cache busting |
| `additional_product_tag_ids` | Many2many | - | - | Variant-specific tags |
| `all_product_tag_ids` | Many2many | compute+search | - | Union of template + variant tags |
| `product_uom_ids` | One2many | store | - | product.uom packaging barcodes |

### `combination_indices` — How It Works

The `_compute_combination_indices` method converts the sorted PTAV IDs into a comma-separated string:

```python
def _compute_combination_indices(self):
    for variant in self:
        variant.combination_indices = ','.join(
            sorted(str(id) for id in variant.product_template_attribute_value_ids.ids)
        )
```

**Why sort?** Because PTAV order in the M2M table may vary depending on creation order or reassignment. Sorting ensures the same physical combination always produces the same string, which is required for the unique index to work correctly.

**Single-value attributes**: When a PTAL has only one value, its PTAV is NOT included in `product_template_attribute_value_ids` on variants (or is included but filtered by `_without_no_variant_attributes()`). This means a template with only single-value attribute lines would have `combination_indices = ""` for all variants, and the partial index `WHERE active IS TRUE` prevents duplicates.

### Image Fallback Chain

```
image_variant_1920 exists?
  YES → use variant image for all sizes (1024/512/256/128 = related)
  NO  → delegate to product_tmpl_id.image_1920
```

When setting `image_1920` on a variant via `_set_template_field()`:
- If only one active variant: writes on template (shared image)
- If multiple variants: writes on variant (per-variant image)
- If neither has image: clears variant, writes on template

### Image Write Date Sync (Cache Busting)

```python
def _compute_write_date(self):
    for variant in self:
        # cr.now() bypasses the framework's write_date restriction
        variant.write_date = max(
            variant.write_date or fields.Datetime.now(),
            variant.product_tmpl_id.write_date
        )
```

When a template's image changes, the template's `write_date` is updated. This triggers `_compute_write_date` on all variants, syncing their `write_date` to match. The website controller uses `write_date` as an HTTP cache buster (`/web/image/product.product/{id}/image_1920?width=...&unique={write_date}`), so variant cache is automatically invalidated when the template image changes.

---

## product.template Attribute Configuration

**File**: `odoo/addons/product/models/product_template.py`

### Attribute Configuration Fields on Template

| Field | Type | Description |
|-------|------|-------------|
| `attribute_line_ids` | One2many | PTAL records: each maps an attribute to a set of allowed values |
| `valid_product_template_attribute_line_ids` | Many2many | PTALs with at least one value (computed, filtered) |
| `has_configurable_attributes` | Boolean | True if any line has 2+ values, dynamic attrs, or custom values |
| `is_dynamically_created` | Boolean | True if any attribute has `create_variant='dynamic'` |

### `has_configurable_attributes` Computation

```python
def _compute_has_configurable_attributes(self):
    for template in self:
        template.has_configurable_attributes = any(
            line._is_configurable()
            for line in template.valid_product_template_attribute_line_ids
        )

# In product_template_attribute_line
def _is_configurable(self):
    return (
        len(self.value_ids) >= 2
        or self.attribute_id.display_type == 'multi'  # multi-checkbox
        or any(v.is_custom for v in self.value_ids)
    )
```

This field determines whether the product has a "Configure" button in the e-commerce/shop interface.

### `is_dynamically_created` Computation

```python
def _compute_is_dynamically_created(self):
    for template in self:
        template.is_dynamically_created = any(
            ptal.attribute_id.create_variant == 'dynamic'
            for ptal in template.valid_product_template_attribute_line_ids
        )
```

Dynamic templates skip automatic variant generation. Variants are created only when needed (e.g., when added to a sales order line).

---

## Attribute, Value, and Configuration Models

### product.attribute

**File**: `odoo/addons/product/models/product_attribute.py`

```python
class ProductAttribute(models.Model):
    _name = 'product.attribute'
    _order = 'sequence, id'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Translate, required |
| `create_variant` | Selection | `always` (instant) / `dynamic` / `no_variant` (never) |
| `display_type` | Selection | `radio` / `pills` / `select` / `color` / `multi` / `image` |
| `sequence` | Integer | Display order |
| `value_ids` | One2many | PAV records belonging to this attribute |
| `number_related_products` | Integer | Count of active templates using this attribute |

**`create_variant` modes explained:**

| Mode | Behavior |
|------|----------|
| `always` | Variants generated immediately when PTAL values are set |
| `dynamic` | Variants created on-demand (when added to an order, etc.) |
| `no_variant` | No variants created; attribute affects price only |

**SQL Constraint**: `display_type='multi'` requires `create_variant='no_variant'`. This is enforced by a raw SQL constraint in `product_attribute.py`.

**Write protection**: Once `number_related_products > 0`, `create_variant` cannot be changed. Enforced in `write()`.

### product.attribute.value (PAV)

**File**: `odoo/addons/product/models/product_attribute_value.py`

```python
class ProductAttributeValue(models.Model):
    _name = 'product.attribute.value'
    _order = 'attribute_id, sequence, id'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Translate, required |
| `attribute_id` | Many2one | Parent attribute (cascade, cannot be changed after creation) |
| `default_extra_price` | Float | Default price_extra when PAV is added to a PTAL |
| `is_custom` | Boolean | Allow customer free-text input (e.g., custom text printing) |
| `html_color` | Char | Color hex code for swatch display (e.g., `#FF5733`) |
| `color` | Integer | Palette index (1-11, random default) |
| `image` | Image | Image for swatch display (max 70x70 px) |
| `is_used_on_products` | Boolean | Computed: linked to any active PTAL |
| `default_extra_price_changed` | Boolean | True if PAV default differs from any PTAV price_extra |

**Delete behavior**:
- No linked variants → SQL delete
- Linked only to archived variants → archive the PAV
- Linked to active variants → block deletion

**Wizard integration**: `action_add_to_products()` and `action_update_prices()` trigger the `update.product.attribute.value` wizard for batch operations.

### product.template.attribute.line (PTAL)

**File**: `odoo/addons/product/models/product_template_attribute_line.py`

```python
class ProductTemplateAttributeLine(models.Model):
    _name = 'product.template.attribute.line'
    _rec_name = 'attribute_id'
    _order = 'sequence, attribute_id, id'
```

| Field | Type | Description |
|-------|------|-------------|
| `product_tmpl_id` | Many2one | Parent template (cascade) |
| `attribute_id` | Many2one | The attribute (cannot be changed after creation) |
| `value_ids` | Many2many | Allowed PAVs (domain: must belong to attribute_id) |
| `value_count` | Integer | Count of value_ids (computed, stored) |
| `product_template_value_ids` | One2many | All PTAVs (active and archived) for this line |

**Constraints**:
- `attribute_id` locked after creation (prevents reassigning line to different attribute)
- `product_tmpl_id` locked after creation
- Active lines must have at least one value

**PTAL Creation — Reactivation Pattern** (L4 detail):

```python
def create(self, vals):
    # Check for existing archived PTAL with same template + attribute
    archived = self.search([
        ('product_tmpl_id', '=', vals['product_tmpl_id']),
        ('attribute_id', '=', vals['attribute_id']),
        ('active', '=', False),
    ])
    if archived:
        # Reactivate and update instead of creating duplicate
        archived.write({'active': True, 'value_ids': vals.get('value_ids', [])})
        return archived
    
    return super().create(vals)
```

This prevents accumulation of duplicate archived PTALs when attributes are repeatedly added/removed from a template.

**`_update_product_template_attribute_values()` — The PTAV Bridge** (L4 detail):

This method syncs PAV selections to PTAV records:

```python
def _update_product_template_attribute_values(self):
    for line in self:
        existing_pavs = {ptav.product_attribute_value_id: ptav
                         for ptav in line.product_template_value_ids}
        
        # Deactivate PTAVs for removed PAVs
        for pav, ptav in existing_pavs.items():
            if pav not in line.value_ids:
                ptav.ptav_active = False  # Soft delete
        
        # Reactivate or create for current PAVs
        for pav in line.value_ids:
            if pav in existing_pavs:
                existing_pavs[pav].ptav_active = True  # Reactivate
            else:
                self.env['product.template.attribute.value'].create({
                    'product_tmpl_id': line.product_tmpl_id.id,
                    'attribute_line_id': line.id,
                    'product_attribute_value_id': pav.id,
                    'price_extra': pav.default_extra_price,  # Copy default
                })
    
    # Trigger variant regeneration
    self.product_tmpl_id._create_variant_ids()
```

### product.template.attribute.value (PTAV)

**File**: `odoo/addons/product/models/product_template_attribute_value.py`

```python
class ProductTemplateAttributeValue(models.Model):
    _name = 'product.template.attribute.value'
    _order = 'attribute_line_id, product_attribute_value_id, id'

    _attribute_value_unique = models.Constraint(
        'unique(attribute_line_id, product_attribute_value_id)',
        'Each value should be defined only once per attribute per product.'
    )
```

| Field | Type | Description |
|-------|------|-------------|
| `ptav_active` | Boolean | Custom active flag (NOT the ORM's `active` — avoids `active_test`) |
| `product_attribute_value_id` | Many2one | Source PAV (cascade) |
| `attribute_line_id` | Many2one | Source PTAL (cascade) |
| `price_extra` | Float | Extra price for this attribute value (default=0.0) |
| `product_tmpl_id` | Many2one | Template (stored, indexed) |
| `attribute_id` | Many2one | Attribute (stored, indexed) |
| `exclude_for` | One2many | PTAEs where this PTAV is the excluding value |
| `ptav_product_variant_ids` | Many2many | Variants containing this PTAV |
| `html_color`, `is_custom`, `display_type`, `color`, `image` | Various | Related from PAV |

**Why `ptav_active` Instead of `active`?** (L4 detail)

The ORM's built-in `active` field applies `active_test` domain filtering globally on all queries:

```python
# If PTAV used ORM's 'active' field:
self.env['product.template.attribute.value'].search([...])  # Filters active=False!

# Using ptav_active:
self.env['product.template.attribute.value'].search([
    ('ptav_active', '=', True),  # Explicit filter, no global side effects
    ('product_tmpl_id', '=', template_id),
])
```

This gives explicit control: archived PTAVs remain queryable for display purposes (showing "this value was removed") without being included in variant generation.

**`_ids2str()` — Canonical String Representation**:

```python
def _ids2str(self):
    """Returns ','.join(sorted(str(id) for id in self.ids))"""
    return ','.join(sorted(str(id) for id in self))
```

Used by `product.product._compute_combination_indices()` to produce the stored string. The PTAV must be sorted to ensure the same combination always produces the same string regardless of M2M table insertion order.

**`_filter_single_value_lines()`**:

```python
def _filter_single_value_lines(self):
    """Returns PTAVs from PTALs with only one value (excluded from combination name)"""
    return self.filtered(
        lambda ptav: ptav.attribute_line_id.value_count > 1
    )
```

Single-value attributes don't differentiate variants, so they are excluded from the combination name displayed to users.

**PTAV unlink cascade**:

```python
def unlink(self):
    # Step 1: Remove from variants that reference this PTAV
    for ptav in self:
        for variant in ptav.ptav_product_variant_ids:
            variant.write({
                'product_template_attribute_value_ids': [(3, ptav.id)]
            })
            # Step 2: Delete or archive the affected variant
            if len(variant.product_template_attribute_value_ids) == 0:
                variant._unlink_or_archive()
    
    # Step 3: Delete the PTAV record
    return super().unlink()
```

### product.template.attribute.exclusion (PTAE)

**File**: `odoo/addons/product/models/product_template_attribute_exclusion.py`

```python
class ProductTemplateAttributeExclusion(models.Model):
    _name = 'product.template.attribute.exclusion'
    _order = 'product_tmpl_id, id'
```

| Field | Type | Description |
|-------|------|-------------|
| `product_template_attribute_value_id` | Many2one | The excluding PTAV (cascade) |
| `product_tmpl_id` | Many2one | Template (cascade, required) |
| `value_ids` | Many2many | Excluded PTAVs (domain: same template, active) |

**Exclusion trigger**: `create()`, `write()`, and `unlink()` all call `product_tmpl_id._create_variant_ids()` to regenerate variants.

**Bidirectional completion** (L4 detail):

When `_complete_inverse_exclusions()` runs on the template:
- If PTAV A has `exclude_for` containing PTAV B → adds B's exclude_for containing A
- The exclusion is stored as a directed graph, made bidirectional on read
- This means adding one exclusion creates both directions simultaneously

---

## Variant Generation Engine

**File**: `odoo/addons/product/models/product_template.py`

### `_create_variant_ids()` — The Main Engine

Called on template `create()` and `write()` when `attribute_line_ids` changes.

```python
def _create_variant_ids(self):
    for template in self:
        if template.has_dynamic_attributes():
            # Skip: dynamic variants created on-demand
            continue
        
        # Get valid PTALs (those with at least one value)
        active_ptals = template.valid_product_template_attribute_line_ids
        
        # Build list of value sets: [[Red, Blue], [S, M, L], [Cotton, Polyester]]
        ptal_values = [
            line.product_template_value_ids._only_active().mapped('id')
            for line in active_ptals
        ]
        
        # itertools.product generates: (Red, S, Cotton), (Red, S, Polyester), ...
        all_combinations = itertools.product(*ptal_values)
        
        # Filter impossible combinations
        valid_combinations = template._filter_combinations_impossible_by_config(
            all_combinations,
            ignore_no_variant=False
        )
        
        # Process each valid combination
        for combination in valid_combinations:
            # Check if variant already exists
            existing = self.env['product.product']._get_variant_id_for_combination(combination)
            if existing:
                # Reactivate if archived
                existing.active = True
            else:
                # Create new variant
                self.env['product.product'].create(
                    template._prepare_variant_values(combination)
                )
        
        # Archive/delete variants that no longer match
        ...
```

### Variant Limit Protection

```python
# Checked before generation
limit = int(
    self.env['ir.config_parameter'].sudo().get_param(
        'product.dynamic_variant_limit', '1000'
    )
)
if len(list(valid_combinations)) > limit:
    raise UserError(_(
        "This attribute configuration would create %s variants, "
        "which exceeds the maximum allowed (%s)."
    ) % (len(valid_combinations), limit))
```

The limit is configurable via `product.dynamic_variant_limit` (default: 1000). Exceeding it raises `UserError`, not silently truncating.

### `_prepare_variant_values()` — Variant Creation Dict

```python
def _prepare_variant_values(self, combination):
    return {
        'product_tmpl_id': self.id,
        'product_template_attribute_value_ids': [(6, 0, combination)],
        'active': self.active,
    }
```

The `(6, 0, ids)` ORM command replaces all existing M2M values with the provided combination.

### `_filter_combinations_impossible_by_config()` — Exclusion Filtering

```python
def _filter_combinations_impossible_by_config(self, combination_tuples, ignore_no_variant=False):
    """
    Generator that yields only valid combinations.
    Filters by:
    1. Attribute line count match
    2. Active value availability  
    3. Own exclusions (attribute-level incompatibilities)
    4. Multi-checkbox display type
    """
    exclusions = self._get_own_attribute_exclusions()
    
    for combination in combination_tuples:
        combination_ids = set(combination)
        
        # Check if any excluded combination is present
        if combination_ids & exclusions.get(combination_ids[-1], set()):
            continue  # Skip this combination
        
        yield combination
```

### Dynamic Variant Creation — On-Demand

For templates with `create_variant='dynamic'` attributes, variants are created when needed:

```python
def _create_product_variant(self, combination):
    """Called by the product configurator when a dynamic combination is selected."""
    self.ensure_one()
    variant = self.env['product.product'].create({
        'product_tmpl_id': self.id,
        'product_template_attribute_value_ids': [(6, 0, combination)],
    })
    return variant
```

Dynamic variants are never pre-generated. They are created via the configurator (e.g., in sale order line) and cached via `_get_variant_id_for_combination()`.

---

## Variant Possibility and Exclusions

### `_is_combination_possible()` — Full Possibility Check

```python
def _is_combination_possible(self, combination, parent_combination=None, ignore_no_variant=False):
    # Step 1: Config-level check (exclusions, attribute constraints)
    if not self._is_combination_possible_by_config(combination, ignore_no_variant):
        return False
    
    # Step 2: For dynamic: check if an active variant record exists
    if self.has_dynamic_attributes():
        variant_id = self._get_variant_id_for_combination(combination)
        if not variant_id or not variant_id.active:
            return False
    
    # Step 3: For static: check if there's an active non-archived variant
    else:
        variant = self.env['product.product'].search([
            ('product_tmpl_id', '=', self.id),
            ('product_template_attribute_value_ids', 'in', combination.ids),
            ('active', '=', True),
        ], limit=1)
        if not variant:
            return False
    
    # Step 4: Parent exclusions (for configurator with parent product)
    if parent_combination:
        parent_exclusions = self._get_parent_attribute_exclusions(parent_combination)
        if set(combination.ids) & parent_exclusions:
            return False
    
    return True
```

### Exclusions Architecture — Three-Layer System

```
Layer 1: PTAE records (product_template_attribute_exclusion)
  → Stored in DB, triggers variant regeneration on create/write/unlink
  → Example: "Color: Black" excludes "Size: XL" for THIS template only

Layer 2: _get_own_attribute_exclusions()
  → Reads PTAE records filtered to this template
  → Returns dict: {ptav_id: [excluded_ptav_ids]}

Layer 3: _complete_inverse_exclusions()
  → Makes exclusions bidirectional: A excludes B → B excludes A
  → Returns the full symmetric exclusion graph
```

### Parent Exclusions — Configurator Integration

When configuring a product that is a combo item of another product:

```python
def _get_parent_attribute_exclusions(self, parent_combination):
    """
    Reads exclusion rules from the PARENT product's PTAVs.
    The parent product's exclusions constrain what's possible in the child.
    """
    exclusions = {}
    for ptav in parent_combination:
        for exclusion in ptav.exclude_for:
            exclusions.setdefault(ptav.id, set()).update(
                exclusion.value_ids.ids
            )
    return exclusions
```

---

## Price Extra Architecture

### Price Extra Flow

```
product.attribute.value.default_extra_price
    ↓ (copied when PTAV created)
product.template.attribute.value.price_extra
    ↓ (summed on variant)
product.product.price_extra = Σ PTAV.price_extra
    ↓ (added to base price)
product.product.lst_price = template.list_price + price_extra
```

### `no_variant` Attribute Price Extra

`no_variant` attributes don't create variants but still affect pricing. Their price extra is handled separately:

```python
# In product.template._get_attributes_extra_price()
no_variant_price_extra = 0
for ptav in ptavs._without_no_variant_attributes():
    if ptav.attribute_id.create_variant == 'no_variant':
        no_variant_price_extra += ptav.price_extra
```

This is included in the context's `current_attributes_price_extra` tuple and added to the base price.

### `is_custom` Price Extra

Custom text attributes (where `is_custom=True` on the PAV) don't have a fixed price_extra. The configurator UI shows a text input field where the customer enters custom value. The price for custom text is typically handled by a separate `product.price.factor` computation in the sale order line, not by `price_extra`.

---

## L4: Performance Patterns

### 1. `ormcache` on Variant Lookup — Registry-Level Caching

`_get_variant_id_for_combination()` uses `ormcache` for sub-millisecond lookups:

```python
@tools.ormcache(
    'self.env.uid',
    'self.env.company_id.id',
    'frozenset(combination.mapped("id"))',
)
def _get_variant_id_for_combination(self, combination):
    variant = self.search([
        ('product_tmpl_id', '=', self.id),
        ('product_template_attribute_value_ids', 'in', combination.ids),
        ('active', '=', True),
    ], limit=1)
    return variant
```

The cache key is `(uid, company_id, frozenset_of_ptav_ids)`. Cache is invalidated when:
- A new variant is created (`product.product.create()`)
- A variant's `product_template_attribute_value_ids` changes (`write()`)
- A variant's `active` state changes (`write()`)

**Without this cache**, every add-to-cart action in the e-commerce or POS would query the database for the variant. With it, the lookup is a Python dict access.

### 2. `combination_indices` — Avoiding Computed String on Every Query

The stored, indexed `combination_indices` field means `_get_variant_id_for_combination` can use a simple indexed search:

```python
variant = self.search([
    ('product_tmpl_id', '=', self.id),
    ('combination_indices', '=', combination._ids2str()),
    ('active', '=', True),
], limit=1)
```

Without this stored field, the search would need to join the M2M table and match PTAV IDs on every lookup.

### 3. `_cartesian_product()` — Early Pruning

The smart Cartesian product prunes entire branches:

```python
def _cartesian_product(self, ptal_values, current_index=0, current=None):
    if current is None:
        current = []
    
    if current_index == len(ptal_values):
        yield tuple(current)
        return
    
    ptav_ids = ptal_values[current_index]
    for ptav_id in ptav_ids:
        # Early check: is this partial combination viable?
        if not self._is_partial_combination_possible(
            current + [ptav_id], current_index
        ):
            continue  # PRUNE: skip all combinations starting with this prefix
        
        current.append(ptav_id)
        yield from self._cartesian_product(
            ptal_values, current_index + 1, current
        )
        current.pop()
```

Without pruning, a product with 5 attributes of 10 values each would generate 100,000 combinations even if most are excluded by rules. With pruning, the algorithm stops exploring branches as soon as an exclusion is found at any depth.

### 4. `_get_possible_variants()` — Not for Loop Iteration

```python
def _get_possible_variants(self, parent_combination=None):
    """
    Returns existing variants that are still possible.
    WARNING: This method can be slow for products with many variants.
    Do NOT call in a loop over multiple templates.
    """
    ...
```

This method is explicitly documented as potentially slow. It checks each existing variant against exclusion rules. For a template with 1000 variants, this could be expensive. The recommended pattern is to call `_is_combination_possible()` for a specific combination, not to iterate all variants.

### 5. Dichotomy Unlink — Binary Search for Blocking Records

```python
def _unlink_or_archive(self, check_access=True):
    try:
        with self.env.cr.savepoint():
            self.mapped('product_tmpl_id').write({'active': False})
            self.unlink()
    except Exception:
        if len(self) == 1:
            self.write({'active': False})  # Archive the lone blocker
        else:
            # Binary search: split and retry
            half = len(self) // 2
            self[:half]._unlink_or_archive(check_access=False)
            self[half:]._unlink_or_archive(check_access=False)
```

This isolates individual blocking records. Without it, deleting 1000 variants where 1 is blocked by a stock move would fail entirely. With dichotomy, 999 are deleted and 1 is archived.

---

## L4: Odoo 18 to Odoo 19 Changes

### 1. `is_dynamically_created` Field (Odoo 19)

Odoo 18: `has_dynamic_attributes()` was a method. Odoo 19 adds a stored computed Boolean `is_dynamically_created` for faster filtering and UI display.

### 2. `product_tooltip` Field (Odoo 19)

New computed Char field providing tooltip text, particularly for combo products. Not present in Odoo 18.

### 3. Registry Cache for `_get_variant_id_for_combination` (Odoo 19)

Odoo 18: uncached. Every variant lookup hit the database.
Odoo 19: `@tools.ormcache` decorator with explicit `registry.clear_cache()` in `product.product.write()` and `create()`.

### 4. `display_applied_on` Split (Odoo 19)

Odoo 18: `applied_on` was used directly in the UI.
Odoo 19: `display_applied_on` separates UI state from business logic, preventing accidental scope changes when editing rule properties.

### 5. `price_markup` Field (Odoo 19)

New computed+inverse field on `product.pricelist.item`. Allows markup entry (positive %) when base is `standard_price`, instead of requiring negative discount values.

### 6. Pricelist Recursion DFS Check (Odoo 19)

Odoo 18: Recursive pricelist references would cause infinite recursion.
Odoo 19: `_check_pricelist_recursion()` uses DFS to detect and block cycles.

### 7. Product Documents (Odoo 19)

`product.document` model via `_inherits ir.attachment` is new. Provides structured document management for products, replacing generic attachment usage.

### 8. `combination_indices` Design (Odoo 19)

The stored Char field with the unique partial index was refined in Odoo 19. The pattern of storing a canonical sorted string to drive the unique constraint and cached lookups is an Odoo 19 performance optimization.

---

## L4: Security Analysis

### Cost Data Exposure Risk

`standard_price` on `product.product` has `groups='base.group_user'`. However, `_price_compute()` uses `sudo()` when fetching cost:

```python
# In product.product._price_compute
if price_type == 'standard_price':
    product_standard_price = product.sudo().standard_price
```

**Risk**: A user without `base.group_user` can have sale prices computed from the cost (via `base='standard_price'` pricelist rules), but cannot directly view the cost field. This is intentional: the `sudo()` allows pricing without exposing cost to unauthorized users.

**Residual risk**: Users who can set up pricelist rules see the computed final price (which is derived from cost). They could infer approximate costs from the price differential. For true cost hiding, use separate pricelist rules that don't expose the base.

### Supplier Information Leakage

`_compute_product_code()` checks access rights before including supplier info:

```python
def _compute_product_code(self):
    sellers = self.seller_ids.filtered(
        lambda s: s.env['product.supplierinfo'].check_access_rights(
            'read', raise_exception=False
        )
    )
```

Without this check, users without `product.supplierinfo` read access would get AccessError when searching for products, even if they have permission to search products themselves.

### Multi-Company Barcode Isolation

Barcodes are checked per-company, not globally:

```python
# Same barcode can exist in different companies
barcode_by_company[product.company_id].add(product.barcode)
```

This is intentional: in a multi-company deployment where each company manages its own product catalog, the same barcode may legitimately appear in different companies. The constraint only prevents barcode duplication within a company.

### Commercial Fields for Pricelist Assignment

`specific_property_product_pricelist` is in `_synced_commercial_fields()` on `res.partner`, meaning it propagates to child companies automatically. This is correct behavior for multi-company hierarchies but means a child company inherits its parent's pricelist assignment unless explicitly overridden.

### Archive vs Delete for Variant Data

The graceful archive fallback (instead of hard delete) preserves audit trails and historical data:
- Archived variants remain accessible for reporting on historical orders
- Archived PAVs and PTAVs can be reactivated
- Archived products remain traceable in stock moves and invoices

This is a data integrity decision: deletion of product data can break historical records.

---

## L4: Extension Points

### Override 1: Custom Variant Validation

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _is_combination_possible(self, combination, parent_combination=None, ignore_no_variant=False):
        res = super()._is_combination_possible(
            combination, parent_combination, ignore_no_variant
        )
        if res and self._is_my_custom_rule_violated(combination):
            return False
        return res
```

### Override 2: Custom Extra Price for no_variant Attributes

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _get_no_variant_attributes_price_extra(self, combination):
        price_extra = super()._get_no_variant_attributes_price_extra(combination)
        # Add custom pricing logic
        price_extra += self._compute_custom_attribute_charge(combination)
        return price_extra
```

### Override 3: Pre- Variant Creation Hook

```python
class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            # Custom post-creation logic
            record._setup_variant_defaults()
        return records
```

### Override 4: Custom Seller Selection for PO

```python
class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _select_seller(self, partner_id=False, quantity=0.0, date=False,
                       uom_id=False, params=False):
        # Custom: prefer vendors with best on-time delivery rate
        sellers = self._get_filtered_suppliers(partner_id, quantity, date, uom_id, params)
        if params and params.get('prefer_on_time'):
            sellers = sellers.sorted(
                key=lambda s: s.partner_id.on_time_rate, reverse=True
            )
        return sellers[:1] if sellers else self.env['product.supplierinfo']
```

### Override 5: Prevent Variant Archival

```python
class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _filter_to_unlink(self):
        # Never auto-delete variants with stock
        return self.filtered(lambda v: not v.qty_available)
```

---

**Source Module**: `odoo/addons/product`
**Source Files**: `product/models/product_*.py`
**Last Updated**: 2026-04-11
**Source Version**: Odoo 19.0 (manifest 1.2)
**Documentation Level**: L4 (Full Depth Escalation — Variants & Attribute Configuration)
**Note**: `product_variant` is not a separate module in Odoo 19. Variant functionality is fully integrated into the `product` module.
