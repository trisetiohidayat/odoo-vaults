---
type: module
module: product
tags: [odoo, odoo19, product, pricelist, variants, inventory]
updated: 2026-04-11
version: "4.0"
odoo_version: 19
level: 4
---

## Quick Access

### Flows (Technical)
- [Flows/Product/product-creation-flow](flows/product/product-creation-flow.md) - Product creation: template, variants, attributes
- [Flows/Product/pricelist-computation-flow](flows/product/pricelist-computation-flow.md) - Pricelist price computation: rule matching, formula

### Related Modules
- [Modules/Stock](modules/stock.md) - Inventory valuation
- [Modules/Sale](modules/sale.md) - Sales pricing and order lines
- [Modules/Purchase](modules/purchase.md) - Vendor supplierinfo
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) - Variant/product patterns

---

## Module Overview

| Property | Value |
|----------|-------|
| **Name** | Product & Pricelist |
| **Version** | 19.0 (manifest `1.2`) |
| **Category** | Sales/Sales |
| **Summary** | Product management, variants, and pricing rules |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Application** | Yes |

## Dependencies

```
base ─┬─ mail ───────── Messaging (mail.thread, mail.activity.mixin)
       ├─ uom ────────── Unit of Measure
       └─ product ────── Self (circular-safe in data)
```

---

## Data Model Architecture

### Template vs Variant Pattern

```
product.template (1) ────── 1:N ────── product.product (N)
     │                                       │
     │ _inherits:                           │ _inherits
     │ delegates fields                      │ delegates fields
     ▼                                       ▼
  Single record                          Per-variant record
  (name, description, category,         (barcode, default_code,
   attributes, seller_ids)                 standard_price, image)
```

- `product.template` holds shared data and attribute configuration
- `product.product` represents individual product variants
- Product variants store variant-specific values (price, barcode, weight, image)
- Variant fields are inherited via `_inherits`; template fields are delegated
- Both inherit `mail.thread` and `mail.activity.mixin` for chatter and activity tracking

### Delegation Inheritance: How `_inherits` Works

`product.product` uses `_inherits = {'product.template': 'product_tmpl_id'}`:

1. `product.product` has its own database table (`product_product`)
2. Template fields (name, description, list_price, categ_id, etc.) are transparently accessible on variant records
3. `product_tmpl_id` is the Many2one FK pointing back to the template (cascade delete)
4. Delegation is read-through: reading `variant.name` executes `variant.product_tmpl_id.name`
5. Write-through for simple fields, but some have custom inverse logic (standard_price, lst_price, etc.)

This differs from classical `_inherit = 'product.template'` which adds fields to the SAME table.

---

## File Structure

```
product/
├── __manifest__.py              # version 1.2, depends: base, mail, uom
├── models/
│   ├── product_template.py      # product.template (MAIN model, ~1200 lines)
│   ├── product_product.py      # product.product (~900 lines)
│   ├── product_category.py     # product.category
│   ├── product_pricelist.py    # product.pricelist
│   ├── product_pricelist_item.py # product.pricelist.item
│   ├── product_supplierinfo.py # product.supplierinfo
│   ├── product_attribute.py     # product.attribute
│   ├── product_attribute_value.py # product.attribute.value
│   ├── product_template_attribute_line.py  # PTAL
│   ├── product_template_attribute_value.py # PTAV
│   ├── product_template_attribute_exclusion.py # PTAL exclusions
│   ├── product_tag.py          # product.tag
│   ├── product_combo.py        # product.combo
│   ├── product_combo_item.py   # product.combo.item
│   ├── product_catalog_mixin.py # Catalog search mixin
│   ├── product_document.py     # product.document (_inherits ir.attachment)
│   ├── product_uom.py          # product.uom (packaging barcode)
│   ├── ir_attachment.py        # Attachment extensions
│   ├── res_partner.py          # partner pricelist field
│   ├── res_company.py          # Company pricelist auto-creation
│   ├── res_config_settings.py  # Pricelist group settings
│   └── res_country_group.py    # Geo-pricing support
├── controllers/
│   └── catalog.py              # JSONRPC catalog endpoints
├── report/
│   ├── product_label_report.py # Label reports (DYMO, 2x7, 4x7, 4x12)
│   └── product_pricelist_report.py # Pricelist PDF/HTML report
└── wizard/
    ├── product_label_layout.py  # Label layout wizard
    └── update_product_attribute_value.py # Batch price update
```

---

## Key Models

### 1. product.template

**File:** `odoo/addons/product/models/product_template.py`

#### Model Definition

```python
class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = "Product"
    _order = "is_favorite desc, name"
    _check_company_auto = True
    _check_company_domain = models.check_company_domain_parent_of
```

#### All Fields

**Identification:**
| Field | Type | Index | Default | Description |
|-------|------|-------|---------|-------------|
| `name` | Char | trigram | required | Product name (translate=True) |
| `sequence` | Integer | - | 1 | Display order |
| `default_code` | Char | store+compute | - | Internal reference (synced from variants) |
| `barcode` | Char | compute | - | Barcode (synced from single variant) |
| `active` | Boolean | - | True | Hide vs remove |
| `color` | Integer | - | - | Kanban color |
| `is_favorite` | Boolean | partial index | - | Favorite flag |
| `_is_favorite_index` | Index | `(is_favorite) WHERE is_favorite IS TRUE` | - | Partial B-tree |

**Descriptions (translate=True):**
| Field | Type | Description |
|-------|------|-------------|
| `description` | Html | Internal notes |
| `description_purchase` | Text | Purchase description |
| `description_sale` | Text | Copied to SO/DO/Invoice |

**Pricing:**
| Field | Type | Store | Default | Description |
|-------|------|-------|---------|-------------|
| `list_price` | Float | Yes | 1.0 | Sales price (user-defined) |
| `standard_price` | Float | compute+inverse | - | Cost (company_dependent, synced from variant) |
| `currency_id` | Many2one | compute | company | Sales currency |
| `cost_currency_id` | Many2one | compute | company | Cost currency |

**Measurements:**
| Field | Type | Store | Description |
|-------|------|-------|-------------|
| `volume` | Float | store+compute | Volume (synced from single variant) |
| `weight` | Float | store+compute | Weight (synced from single variant) |
| `volume_uom_name` | Char | compute | Volume UoM label |
| `weight_uom_name` | Char | compute | Weight UoM label |
| `uom_id` | Many2one | - | Default UoM (required, default: Unit) |
| `uom_ids` | Many2many | - | Additional packagings |

**Variant Management:**
| Field | Type | Store | Description |
|-------|------|-------|-------------|
| `attribute_line_ids` | One2many | - | PTALs for variant generation |
| `valid_product_template_attribute_line_ids` | Many2many | compute | PTALs with at least one value |
| `product_variant_ids` | One2many | - | All product variants |
| `product_variant_id` | Many2one | compute | First/prefetched variant |
| `product_variant_count` | Integer | compute | Variant count |
| `has_configurable_attributes` | Boolean | compute | Has configurable attr lines |
| `is_dynamically_created` | Boolean | compute | Has dynamic attributes |
| `combo_ids` | Many2many | - | Combos containing this product |

**Organization:**
| Field | Type | Description |
|-------|------|-------------|
| `categ_id` | Many2one | Product category |
| `company_id` | Many2one | Company |
| `seller_ids` | One2many | Vendor info (product.supplierinfo) |
| `type` | Selection | `consu`/`service`/`combo` (default=`consu`) |
| `service_tracking` | Selection | `no` (computed for non-services) |
| `sale_ok` | Boolean | Can be sold (default=True) |
| `purchase_ok` | Boolean | Can be purchased (computed, default=True) |

**Documents:**
| Field | Type | Description |
|-------|------|-------------|
| `product_document_ids` | One2many | product.document records |
| `product_document_count` | Integer | Computed document count |

**Images:**
| Field | Type | Description |
|-------|------|-------------|
| `image_1920` | Image | Main image (from image.mixin) |
| `can_image_1024_be_zoomed` | Boolean | Zoom available if 1920 > 1024 |

**Other:**
| Field | Type | Description |
|-------|------|-------------|
| `product_tooltip` | Char | Compute tooltip text |
| `is_product_variant` | Boolean | Always False (computed) |
| `product_tag_ids` | Many2many | product.tag |
| `product_properties` | Properties | Category-defined properties |
| `pricelist_rule_ids` | One2many | product.pricelist.item |

#### Key Methods

**Compute Methods (L2 detail):**

- `_compute_standard_price()` — Delegates to `_compute_template_field_from_variant_field('standard_price')`. Falls back to 0 if no variant. Depends on `force_company` context because `standard_price` is company_dependent on `product.product`.
- `_compute_template_field_from_variant_field(fname, default=False)` — For single-variant products, reads field from variant; for multi-variant, uses `default`; for zero active variants, retries with `active_test=False`.
- `_set_standard_price()` / `_set_product_variant_field(fname)` — Propagates value to variant only when exactly one variant exists; handles archived variants.
- `_compute_barcode()` / `_set_barcode()` — Same single-variant sync pattern.
- `_compute_default_code()` / `_set_default_code()` — Same sync pattern.
- `_compute_volume()` / `_set_volume()` — Same sync pattern.
- `_compute_weight()` / `_set_weight()` — Same sync pattern.
- `_compute_product_variant_count()` — `len(product_variant_ids)`.
- `_compute_product_variant_id()` — `product_variant_ids[:1]` for prefetch performance.
- `_compute_currency_id()` — `company_id.currency_id` or main company currency.
- `_compute_cost_currency_id()` — Same pattern.
- `_compute_has_configurable_attributes()` — True if any attribute line has 2+ values, dynamic attributes, multi-checkbox display type, or custom values.
- `_compute_is_dynamically_created()` — True if any PTAL has attribute with `create_variant='dynamic'`.
- `_compute_service_tracking()` — Sets `service_tracking='no'` for non-service types. Marked `store=True` so it persists.
- `_compute_product_tooltip()` / `_prepare_tooltip()` — Returns tooltip for combos explaining the selection behavior.
- `_compute_can_image_1024_be_zoomed()` — `is_image_size_above(image_1920, image_1024)`.
- `_compute_display_name()` — Context-aware: respects `display_default_code`, `formatted_display_name`; formats as `[default_code] name` or `name \t--default_code--`.
- `_compute_product_document_count()` — Searches product.document with template's `_get_product_document_domain()`.

**Onchange Methods (L2 detail):**

- `_onchange_standard_price()` — Validates `>= 0`; raises `ValidationError` if negative.
- `_onchange_default_code()` — Warns via notification if another template already uses the code.
- `_onchange_uom_id()` — Warns about UoM conversion impact on existing records. Checks `_trigger_uom_warning()` on variants first.
- `_onchange_type()` — For `type='combo'`: prevents attributes, prevents being a combo item, sets `purchase_ok=False`.

**Variant Generation Methods (L3 detail):**

- `_create_variant_ids()` — The main variant (re)generation engine. Called on template `create()` and `write()` when `attribute_line_ids` changes or when archiving a template with no variants. Uses `itertools.product` over active PTALs to generate all combinations. Bypasses generation entirely for dynamic attributes (those variants are created on-demand). Respects `product.dynamic_variant_limit` config param (default 1000). Calls `_unlink_or_archive()` for removed variants. Clears `combo_ids` on affected variants.
- `_prepare_variant_values(combination)` — Builds dict: `product_tmpl_id`, `product_template_attribute_value_ids` (6,0,ids), `active` from template.
- `_get_possible_variants(parent_combination)` — Returns existing variants filtered by `_is_variant_possible()`. **Performance warning**: can be slow for many variants; avoid calling in loops.
- `_get_attribute_exclusions(parent_combination, parent_name, combination_ids)` — Returns full exclusions dict: `exclusions` (self), `archived_combinations`, `parent_exclusions`, `mapped_attribute_names`. Used by the configurator.
- `_complete_inverse_exclusions(exclusions)` — Bidirectional exclusion completion (A excludes B implies B excludes A).
- `_get_own_attribute_exclusions(combination_ids)` — Reads from `exclude_for` filtered to self template.
- `_get_parent_attribute_exclusions(parent_combination)` — Reads exclusions from parent product's PTAVs.
- `_filter_combinations_impossible_by_config(combination_tuples, ignore_no_variant)` — Filters out invalid combinations using exclusions, dynamic attributes, and attribute constraints. Returns a generator or list.
- `has_dynamic_attributes()` — Returns `any(a.create_variant == 'dynamic' for a in valid_ptal.attribute_id)`.

**CRUD Methods:**

- `create(vals_list)` — Calls `super().create()`, then `_create_variant_ids()` if context `create_product_product=True`. Syncs related variant fields (barcode, weight, volume, etc.) from vals to the first variant.
- `write(vals)` — Handles UoM change (updates variants with `skip_uom_conversion=True`). Triggers `_create_variant_ids()` when `attribute_line_ids` changes or when archiving with no variants. Cascades `active=False` to variants. Clears combo associations when type changes away from `combo`.
- `copy(default)` — Copies template + matches `price_extra` from original PTAVs to copied PTAVs. Returns the first variant.
- `action_open_label_layout()` — Raises `ValidationError` for service products. Opens label layout wizard.
- `action_open_documents()` — Opens product.document kanban/list/form for the template.

**Price Computation:**

- `_price_compute(price_type, uom, currency, company, date)` — Low-level. For `standard_price`: fetches as `sudo()` (for non-group_user access) and falls back to first variant's cost if template has no cost. For `list_price`: adds `_get_attributes_extra_price()`. Handles UoM conversion and currency conversion. Returns `{template_id: price}`.
- `_get_product_price_context(combination)` — Returns dict with `current_attributes_price_extra` tuple for price context.
- `_get_attributes_extra_price()` — Sums context's `current_attributes_price_extra` tuple.

#### Standard Price Inverse Pattern (L4 detail)

```
Write standard_price on template
  → _set_standard_price() called
  → _set_product_variant_field('standard_price')
  → If exactly 1 active variant exists:
      variant.standard_price = template.standard_price
  → If 0 active but 1 archived variant:
      archived_variants[0].standard_price = template.standard_price
  → Otherwise: no-op (multi-variant templates store cost per-variant)
```

This design means multi-variant templates have per-variant `standard_price` (company_dependent), while single-variant templates auto-sync. The `company_dependent` flag means each company gets its own cost per variant.

#### Weight/Volume UoM Config (L4 detail)

Weight and volume UoMs are read from `ir.config_parameter` at compute time, not stored:
- `product.weight_in_lbs` = `'1'` → pounds, else kg
- `product.volume_in_cubic_feet` = `'1'` → cubic feet, else cubic meters

Changing these parameters **does not** convert existing stored values — it only changes interpretation of the stored Float. This is a common misconfiguration risk.

#### Image Inheritance (L3 detail)

`image.mixin` provides `image_1920/1024/512/256/128` on template. `product.product` adds `image_variant_1920` (technical, not displayed by default) plus computed fallbacks:

```
product.product:
  image_1920 = image_variant_1920 or product_tmpl_id.image_1920
  image_1024 = image_variant_1024 or product_tmpl_id.image_1024
  ... (same for all sizes)

product.product._compute_write_date():
  write_date = max(self.write_date, product_tmpl_id.write_date)
  → Ensures variant's HTTP cache is invalidated when template image changes
```

Template image changes call `invalidate_model()` on product.product image fields to bust browser cache.

#### product.product Variant Sync on Template Write (L3 detail)

Template `write()` behavior for shared fields (`barcode`, `default_code`, `standard_price`, `volume`, `weight`, `product_properties`):
- **Single variant**: value propagates to the variant
- **No variants (all archived)**: value propagates to the one archived variant if exactly one exists
- **Multiple variants**: value stays on template; variants retain their own values

This prevents accidentally overwriting per-variant data when writing from the template form.

---

### 2. product.product (Product Variant)

**File:** `odoo/addons/product/models/product_product.py`

#### Model Definition

```python
class ProductProduct(models.Model):
    _name = 'product.product'
    _description = "Product Variant"
    _inherits = {'product.template': 'product_tmpl_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'default_code, name, id'
    _check_company_domain = models.check_company_domain_parent_of

    # Unique constraint: at most one active variant per combination
    _combination_unique = models.UniqueIndex(
        "(product_tmpl_id, combination_indices) WHERE active IS TRUE"
    )
```

#### Variant-Specific Fields (not delegated via _inherits, or overridden)

| Field | Type | Store | Description |
|-------|------|-------|-------------|
| `product_tmpl_id` | Many2one | btree | Parent template (required, cascade, bypass_search_access) |
| `combination_indices` | Char | btree | Encoded PTAV IDs as comma-separated sorted string (computed, stored) |
| `price_extra` | Float | compute | Sum of all PTAV price_extras |
| `lst_price` | Float | compute+inverse | `list_price + price_extra` (UoM-aware via context) |
| `default_code` | Char | btree | Internal reference (direct, not computed from template) |
| `code` | Char | compute | Supplier reference (based on context partner_id) |
| `partner_ref` | Char | compute | Full customer-specific name+ref |
| `barcode` | Char | btree_not_null | Barcode (no company uniqueness here; checked in _check_barcode_uniqueness) |
| `standard_price` | Float | company_dependent | Cost (not synced from template — stored per-variant per-company) |
| `volume` | Float | - | Volume (direct, variant-specific) |
| `weight` | Float | - | Weight (direct, variant-specific) |
| `product_uom_ids` | One2many | store | product.uom (packaging barcodes) |
| `product_template_attribute_value_ids` | Many2many | - | PTAVs defining this variant (Many2many via `product_variant_combination`) |
| `product_template_variant_value_ids` | Many2many | - | PTAVs from multi-value lines only |
| `active` | Boolean | - | Active (direct, not delegated; affects uniqueness constraint) |
| `is_product_variant` | Boolean | compute | Always True |
| `is_favorite` | Boolean | store+related | Synced from template with readonly=False |
| `pricelist_rule_ids` | One2many | compute+inverse | Variant-specific pricelist rules |
| `product_document_ids` | One2many | - | Documents |
| `additional_product_tag_ids` | Many2many | - | Tags specific to this variant |
| `all_product_tag_ids` | Many2many | compute+search | Union of template tags + variant tags |
| `image_variant_1920` | Image | - | Variant image (overrides template) |
| `image_variant_1024/512/256/128` | Image | store | Resized variants of image_variant_1920 |
| `can_image_variant_1024_be_zoomed` | Boolean | store | Zoom check |
| `write_date` | Datetime | store | Synced from template write_date for cache busting |

#### Image Fallback (L3 detail)

```
image_variant_1920 exists?
  YES: use variant image for all sizes
  NO:  delegate to product_tmpl_id.image_1920
```

All image sizes (`1024/512/256/128`) use the same fallback chain. When a template image is updated, the `write_date` of all its variants is also updated (via `_compute_write_date`), which triggers HTTP cache invalidation in the browser.

#### Image Setter Logic (`_set_template_field`) (L4 detail)

When setting `image_1920` on a variant, the setter decides whether to write on the variant image or the template image based on:
1. If neither variant nor template has the field set → clear variant, set template
2. If template field is not set → write on template
3. If only one active variant exists on template → write on template
4. Otherwise → write on the variant itself

This prevents overwriting shared template images when a user sets a per-variant image.

#### Key Methods

**Compute Methods:**

- `_compute_product_price_extra()` — `sum(PTAV.price_extra for PTAV in product_template_attribute_value_ids)`. No context dependency.
- `_compute_product_lst_price()` — Context `uom` triggers UoM conversion: `uom_id._compute_price(list_price, context_uom) + price_extra`. Without context: `list_price + price_extra`.
- `_set_product_lst_price()` (inverse) — Reads context `uom`, converts, subtracts `price_extra`, writes back `list_price` on template.
- `_compute_combination_indices()` — `PTAV._ids2str()` → `','.join(sorted(str(id) for id in ids))`. This is the stored value that drives the unique index.
- `_compute_product_code()` — Uses `seller_ids` filtered by context `partner_id`. Falls back to `default_code`. Needs `product.supplierinfo` read access.
- `_compute_partner_ref()` — Builds `"[code] name"` from supplier info or `display_name`.
- `_compute_write_date()` — `max(variant.write_date, template.write_date)`. Framework normally prevents write_date assignment, but the compute method bypasses this restriction.
- `_compute_all_product_tag_ids()` — `product_tag_ids | additional_product_tag_ids`, sorted by sequence.
- `_compute_pricelist_rule_ids()` — Filters template's `pricelist_rule_ids` to those where `product_id <= current product` (variant is in scope).
- `_inverse_pricelist_rule_ids()` — Merges variant rules with template rules, keeping rules for other variants.
- `_compute_product_document_count()` — Counts documents with `res_model='product.product'` and `res_id in self.ids`.

**CRUD Methods:**

- `create(vals_list)` — Calls `super()` with `create_product_product=False` context, then clears the ORM registry cache (needed because `_get_variant_id_for_combination` depends on existing variants).
- `write(vals)` — Clears registry cache when `product_template_attribute_value_ids` or `active` changes (both affect `_get_variant_id_for_combination` cache key).
- `action_archive()` — Archives variant, then archives template if it has no remaining active variants.
- `action_unarchive()` — Unarchives variant, then unarchives template if it was deactivated due to having no active variants.
- `unlink()` — If variant is the last one and template has no dynamic attributes: also deletes template. Moves variant image to template if template has no image. Clears registry cache.
- `_filter_to_unlink()` — Hook; returns `self` by default. Can be overridden to exclude some variants from deletion.
- `_unlink_or_archive(check_access=True)` — **L4 performance method**: Tries batch unlink first; on exception, uses dichotomy (splits in half, recursively retries) to isolate blocking records. Falls back to archive if even single-record unlink fails. This handles real-world cases like stock moves referencing the variant.
- `copy(default=None)` — Does **not** copy the variant directly. Instead copies the template and returns `new_template.product_variant_id` (or creates first variant if dynamic). This preserves variant generation logic.

**Search Methods:**

- `_search_display_name(operator, value)` — Complex multi-model search across template name, variant default_code, barcode, and supplier info (product_name, product_code). Builds `UNION ALL` query for performance. Disables `active_test` for subqueries.
- `name_search(name, domain, operator, limit)` — Progressive search: exact default_code → exact barcode → prefix match on default_code/barcode/name. Avoids single large search with OR on name which would hit translation table badly.
- `_search_all_product_tag_ids(operator, operand)` — Searches both template tags and variant tags via OR domain.
- `_search_is_in_selected_section_of_order(operator, value)` — Context-driven: uses `order_id`, `product_catalog_order_model`, `child_field` to find products in a specific order line section.
- `_search(domain)` — Adds `child_of` domain on `categ_id` when `search_default_categ_id` is in context.

**Barcode Uniqueness (L4 detail):**

`_check_barcodes_by_company()` groups barcodes by company, then calls:
- `_check_duplicated_product_barcodes()` — Raises if same barcode assigned to multiple `product.product` records within company scope.
- `_check_duplicated_packaging_barcodes()` — Raises if same barcode on any `product.uom` packaging within company.

GS1 nomenclature means products and packagings share barcode namespace, so cross-model uniqueness is enforced.

---

### 3. product.category

**File:** `odoo/addons/product/models/product_category.py`

```python
class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['mail.thread']
    _parent_name = 'parent_id'
    _parent_store = True  # Populates parent_path on write
    _rec_name = 'complete_name'
    _order = 'complete_name'
```

| Field | Type | Index | Description |
|-------|------|-------|-------------|
| `name` | Char | trigram | Category name (required) |
| `complete_name` | Char | store | Full hierarchical path (Parent / Child) |
| `parent_id` | Many2one | btree | Parent category (cascade) |
| `parent_path` | Char | btree | Materialized path `'1/5/23/'` for `child_of` queries |
| `child_id` | One2many | - | Child categories |
| `product_count` | Integer | - | Count of products (recursive, includes children) |
| `product_properties_definition` | PropertiesDefinition | - | Schema for product.properties on this category |

**Key Methods:**

- `_compute_complete_name()` — Recursive: `parent.complete_name + ' / ' + name`. Uses `store=True` so it does not recompute on every read.
- `_compute_product_count()` — Uses `_read_group` on `product.template` with `child_of` domain, then sums per-subcategory. **Note**: `product_count` includes children but `_compute_product_count` iterates `search([('id', 'child_of', categ.ids)])` per category which can be slow for deep hierarchies. Consider denormalizing with a `product.category.count` computed field if performance is a concern.
- `_check_category_recursion()` — Uses `_has_cycle()` (parent mixin) to prevent circular parent chains.
- `name_create(name)` — Convenience: creates category from just a name string.

**Display naming**: Respects `hierarchical_naming` context. When `False`, shows just the category name (not the full path).

---

### 4. product.pricelist

**File:** `odoo/addons/product/models/product_pricelist.py`

```python
class ProductPricelist(models.Model):
    _name = 'product.pricelist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_names_search = ['name', 'currency_id']
    _order = "sequence, id, name"
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Pricelist name (translate, required) |
| `active` | Boolean | Active status |
| `sequence` | Integer | Display order |
| `currency_id` | Many2one | Currency (required, default: company currency) |
| `company_id` | Many2one | Company (default: current company) |
| `country_group_ids` | Many2many | Country groups for geo-pricing |
| `item_ids` | One2many | Pricelist rules (domain: active pricelist) |

**Item domain**: `_domain_item_ids()` returns `['|', ('product_tmpl_id', '=', None), ('product_tmpl_id.active', '=', True), '|', ('product_id', '=', None), ('product_id.active', '=', True)]`. Items pointing to inactive products/templates are excluded from rule matching.

#### Price Computation Methods

**`get_html(data)` / `_get_report_data(data, report_type)` (report only)**

**`_get_product_price(product, qty, ...)`** — Single product price. Delegates to `_compute_price_rule()`. `ensure_one()` on self.

**`_get_products_price(products, qty, ...)`** — Multi-product prices. Returns `{product_id: price}`.

**`_get_product_price_rule(product, qty, ...)`** — Returns `(price, rule_id)` tuple.

**`_get_product_rule(product, qty, ...)`** — Returns only rule ID (skips price computation when `compute_price=False`).

**`_compute_price_rule(products, qty, uom, date, compute_price)` (L3 detail)**

The core algorithm:

```
1. Fetch applicable rules via _get_applicable_rules() (single DB query)
2. For each product:
   a. Convert quantity to product UoM (pricelist rules are in product UoM)
   b. Iterate rules in search order (most specific first)
   c. For first matching rule: compute price via rule._compute_price()
   d. If no rule matches: return (0.0, False)
3. Return {product_id: (price, rule_id)}
```

Key detail: rules are iterated in database order (`applied_on` in `_order` sorts most-specific first). The **first matching rule wins**, not the best match.

**`_get_applicable_rules(products, date)`** — Calls `_get_applicable_rules_domain()` and executes `search()`.

**`_get_applicable_rules_domain(products, date)` (L4 detail)**

```
[
  ('pricelist_id', '=', self.id),
  '|', ('categ_id', '=', False), ('categ_id', 'parent_of', products.categ_id.ids),
  '|', ('product_tmpl_id', '=', False), (product_tmpl_id domain),
  '|', ('product_id', '=', False), (product_id domain),
  '|', ('date_start', '=', False), ('date_start', '<=', date),
  '|', ('date_end', '=', False), ('date_end', '>=', date),
]
```

The `parent_of` operator uses `parent_path` (materialized path) for efficient hierarchical category matching without recursive CTEs.

**`_compute_price_rule_multi(products, qty, uom, date)`** — Multi-pricelist version. If `self` is empty, searches all pricelists first.

**`_get_country_pricelist_multi(country_ids)` (L3 detail)**

Geo-pricing resolution order:
1. Pricelist matching partner's country group
2. Fallback: pricelist with no country group
3. Further fallback: `ir.config_parameter res.partner.property_product_pricelist_{company_id}`
4. Further fallback: `ir.config_parameter res.partner.property_product_pricelist`
5. Final fallback: first available active pricelist for the company

Context `country_code` can override the partner's country for public users.

**`_get_partner_pricelist_multi(partner_ids)` (L3 detail)**

For each partner:
1. Check `specific_property_product_pricelist` (company-dependent field, set when partner has explicit pricelist)
2. Else: group by country, resolve via `_get_country_pricelist_multi()`
3. If pricelist feature is disabled (group not enabled): return empty recordset

This is called from `res.partner._compute_product_pricelist()`.

**`action_open_pricelist_report()`** — Returns client action `'generate_pricelist_report'` which triggers JS report generation.

---

### 5. product.pricelist.item (Pricelist Rule)

**File:** `odoo/addons/product/models/product_pricelist_item.py`

```python
class ProductPricelistItem(models.Model):
    _name = 'product.pricelist.item'
    _order = "applied_on, min_quantity desc, categ_id desc, id desc"
    _check_company_auto = True
```

**Sort order logic (L3 detail):**
- `applied_on`: `0_` variants → `1_` templates → `2_` categories → `3_global` (most specific first)
- `min_quantity desc`: larger quantities first (more specific volume discounts)
- `categ_id desc`: null (global) after specific categories (avoids nulls sorting first)
- `id desc`: newest rules win within same priority

This ordering ensures the most specific, highest-quantity rule is evaluated first and wins.

#### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `pricelist_id` | Many2one | Parent pricelist (cascade, default: first active) |
| `applied_on` | Selection | `3_global`/`2_category`/`1_product`/`0_variant` |
| `display_applied_on` | Selection | `1_product`/`2_category` (UI variant picker) |
| `categ_id` | Many2one | Category (if applied_on=`2_category`) |
| `product_tmpl_id` | Many2one | Template (if applied_on=`1_product`) |
| `product_id` | Many2one | Variant (if applied_on=`0_variant`) |
| `product_variant_count` | Integer | Related template's variant count |
| `base` | Selection | `list_price`/`standard_price`/`pricelist` |
| `base_pricelist_id` | Many2one | Other pricelist (if base=`pricelist`) |
| `compute_price` | Selection | `fixed`/`percentage`/`formula` (default=`fixed`) |
| `fixed_price` | Float | Fixed price value |
| `percent_price` | Float | Percentage off (negative = markup) |
| `price_discount` | Float | Discount % for formula mode |
| `price_round` | Float | Rounding multiple |
| `price_surcharge` | Float | Fixed fee (added after rounding) |
| `price_markup` | Float | Markup % (inverse of discount, compute+inverse, store) |
| `price_min_margin` | Float | Minimum margin over base price |
| `price_max_margin` | Float | Maximum margin over base price |
| `min_quantity` | Float | Minimum quantity (in product UoM) |
| `date_start` | Datetime | Rule validity start |
| `date_end` | Datetime | Rule validity end |
| `company_id` | Many2one | Computed from pricelist or template |
| `currency_id` | Many2one | Computed from pricelist or company |
| `name` | Char | Computed rule description |
| `price` | Char | Computed human-readable price/rule |
| `rule_tip` | Char | Formula example (e.g. "100 * 0.9 + 5 → 95") |

#### Onchange Methods (L3 detail)

**`_onchange_base()`** — Resets `price_discount` and `price_markup` to 0 when base changes.

**`_onchange_base_pricelist_id()`** — If `compute_price='percentage'` and `base_pricelist_id` is set: auto-switches `base` to `'pricelist'`.

**`_onchange_compute_price()`** — Cascading reset: sets `base_pricelist_id=False` always; clears fixed/percentage/formula fields based on new compute mode.

**`_onchange_display_applied_on()`** — Maps UI picker to `applied_on` and clears incompatible fields (e.g., switching to category clears product_id and product_tmpl_id).

**`_onchange_product_id()`** — Auto-fills `product_tmpl_id` from the variant. Sets `applied_on='0_variant'` if context `default_applied_on='1_product'` and variant is specified.

**`_onchange_rule_content()`** — Auto-sets `applied_on` based on which product reference field is filled. This is the primary UX mechanism: filling in a variant sets `applied_on='0_variant'`, filling in a template sets `applied_on='1_product'`, etc.

#### Constraint Methods (L3 detail)

**`_check_base_pricelist_id()`** — Requires `base_pricelist_id` if `base='pricelist'`.

**`_check_pricelist_recursion()`** — DFS path detection: follows `base_pricelist_id` links to detect cycles. Raises with a rendered path of rule names in the cycle.

**`_check_date_range()`** — `date_end` must be strictly after `date_start`.

**`_check_margin()`** — `price_min_margin <= price_max_margin`.

**`_check_product_consistency()`** — Enforces that `applied_on` matches the presence of the corresponding product/category field.

#### Price Computation (`_compute_price`) (L3 detail)

```python
# UoM conversion for the fixed price
if product_uom != uom:
    convert = lambda p: product_uom._compute_price(p, uom)
else:
    convert = lambda p: p

if compute_price == 'fixed':
    price = convert(fixed_price)
elif compute_price == 'percentage':
    price = base_price * (1 - percent_price / 100) or 0.0
elif compute_price == 'formula':
    discount = price_discount if base != 'standard_price' else -price_markup
    price = base_price - (base_price * (discount / 100))
    if price_round:
        price = float_round(price, precision_rounding=price_round)
    if price_surcharge:
        price += convert(price_surcharge)  # surcharge in product UoM
    if price_min_margin:
        price = max(price, price_limit + convert(price_min_margin))
    if price_max_margin:
        price = min(price, price_limit + convert(price_max_margin))
```

**Key edge case**: `percentage` mode with `percent_price=100` results in `0.0` price (not a free product, but explicitly zero). The `or 0.0` guard handles this.

**Base price sources (`_compute_base_price`)**:
- `list_price`: `product.currency_id`, `product._price_compute('list_price', ...)`
- `standard_price`: `product.cost_currency_id`, `product._price_compute('standard_price', ...)` as `sudo()` (for non-group_user)
- `pricelist`: recursively calls `base_pricelist_id._get_product_price()` with that pricelist's currency

Currency conversion uses `src_currency._convert(price, target_currency, company, date, round=False)`.

**Margin constraints**: `price_limit` is set to `base_price` before discount. Min/max margins are relative to this base, not the discounted price. The `convert()` lambda handles UoM conversion for margin values (expressed in product UoM).

**`_compute_price_before_discount()`** — Chases `base='pricelist'` links through multiple levels, stopping at the first `compute_price='percentage'` rule. Used for displaying "was X, now Y" discount labels.

---

### 6. product.supplierinfo (Vendor Pricelist)

**File:** `odoo/addons/product/models/product_supplierinfo.py`

```python
class ProductSupplierinfo(models.Model):
    _name = 'product.supplierinfo'
    _order = 'sequence, min_qty DESC, price, id'
    _rec_name = 'partner_id'
```

| Field | Type | Description |
|-------|------|-------------|
| `partner_id` | Many2one | Vendor (res.partner, cascade, required, check_company) |
| `product_name` | Char | Vendor's product name (for RFQ printing) |
| `product_code` | Char | Vendor's product code |
| `sequence` | Integer | Priority (default=1) |
| `product_uom_id` | Many2one | Vendor's unit (computed from product/variant) |
| `min_qty` | Float | Minimum qty for this price (default=0.0, digits: Product Unit) |
| `price` | Float | Unit price |
| `price_discounted` | Float | Price after discount (computed: UoM-converted, discounted) |
| `company_id` | Many2one | Company (default: current) |
| `currency_id` | Many2one | Currency (default: company currency) |
| `date_start` | Date | Price validity start |
| `date_end` | Date | Price validity end |
| `product_id` | Many2one | Specific variant (optional; null = all variants) |
| `product_tmpl_id` | Many2one | Product template (required, cascade) |
| `product_variant_count` | Integer | Related template's variant count |
| `delay` | Integer | Lead time in days (default=1, for scheduler) |
| `discount` | Float | Discount % (digits: Discount) |

**Key Compute Logic:**

- `_compute_product_uom_id()` — Falls back to `product_id.uom_id` if variant set, else `product_tmpl_id.uom_id`. Marked `precompute=True` (fills on create).
- `_compute_price()` — Auto-fills `price` from the variant's or template's `standard_price` as a convenience.
- `_compute_price_discounted()` — `product_uom_id._compute_price(price, product_uom) * (1 - discount/100)`. The UoM conversion is from vendor UoM to product UoM.
- `_compute_product_tmpl_id()` — Derives template from variant if `product_id` is set.
- `_compute_product_id()` — If `default_product_id` in context or only one variant exists, auto-selects it. Prevents null-forcing when template already has a specific variant.

**`_sanitize_vals(vals)`** — Called in `create()` and `write()`. Adds `product_tmpl_id` from `product_id` if not present. This ensures the bidirectional link is always consistent even during imports.

**`_get_filtered_supplier(company_id, product_id, params)`** — Filters: company match (or null), active partner, product match (variant-specific or template-wide).

Used by Purchase module's `_select_seller()` which sorts by `sequence, min_qty DESC, price` and filters by date range.

---

### 7. product.attribute

**File:** `odoo/addons/product/models/product_attribute.py`

```python
class ProductAttribute(models.Model):
    _name = 'product.attribute'
    _order = 'sequence, id'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Attribute name (translate, required) |
| `active` | Boolean | Active status (default=True) |
| `create_variant` | Selection | `always` (instant) / `dynamic` / `no_variant` (never) |
| `display_type` | Selection | `radio`/`pills`/`select`/`color`/`multi`/`image` |
| `sequence` | Integer | Display order (default=20) |
| `value_ids` | One2many | product.attribute.value records |
| `template_value_ids` | One2many | PTAVs using this attribute |
| `attribute_line_ids` | One2many | PTALs using this attribute |
| `product_tmpl_ids` | Many2many | Templates using this attribute (computed) |
| `number_related_products` | Integer | Count of active templates (computed) |

**Constraint**: Multi-checkbox display type (`display_type='multi'`) requires `create_variant='no_variant'`.

**Write protection (L3 detail)**: Changing `create_variant` is blocked if `number_related_products > 0`. This prevents invalidating existing variant configurations without explicit user action. The `number_related_products` count uses `_read_group` on PTAL filtered by `active=True` templates.

**Delete protection**: `_unlink_except_used_on_product()` prevents deletion if used on any product.

**`_without_no_variant_attributes()`** — Filter to attributes with `create_variant != 'no_variant'`. Used throughout variant generation to skip irrelevant attributes.

---

### 8. product.attribute.value

**File:** `odoo/addons/product/models/product_attribute_value.py`

```python
class ProductAttributeValue(models.Model):
    _name = 'product.attribute.value'
    _order = 'attribute_id, sequence, id'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Value name (translate, required) |
| `sequence` | Integer | Display order |
| `attribute_id` | Many2one | Parent attribute (cascade, required, index) |
| `pav_attribute_line_ids` | Many2many | PTALs using this PAV (via M2M table) |
| `default_extra_price` | Float | Default extra price when added to products |
| `is_custom` | Boolean | Allow free-text customer input |
| `html_color` | Char | HTML color for swatch (e.g. `#ff0000`) |
| `color` | Integer | Color index for palette (1-11, default: random) |
| `display_type` | Selection | Related from attribute |
| `image` | Image | Color swatch image (max 70x70) |
| `active` | Boolean | Active status (default=True) |
| `is_used_on_products` | Boolean | Computed: linked to any active PTAL |
| `default_extra_price_changed` | Boolean | Computed: differs from PTAV price_extra |

**`_compute_display_name()`** — In default context: `"attribute_name: value_name"`. When `show_attribute=False` in context: raw value name only (used on product template form where attribute is already visible in the line).

**Delete/archive behavior (L3 detail)**: `unlink()` checks if the PAV is linked to any active product variants. If yes (archived variants only): archives the PAV instead of deleting. If no linked products at all: deletes normally. This preserves historical data while cleaning up the UI.

**`action_add_to_products()`** — Opens `update.product.attribute.value` wizard in `'add'` mode to add this value to multiple products.

**`action_update_prices()`** — Opens `update.product.attribute.value` wizard in `'update_extra_price'` mode to set PTAV price_extras across all products using this value.

---

### 9. product.template.attribute.line (PTAL)

**File:** `odoo/addons/product/models/product_template_attribute_line.py`

```python
class ProductTemplateAttributeLine(models.Model):
    _name = 'product.template.attribute.line'
    _rec_name = 'attribute_id'
    _order = 'sequence, attribute_id, id'
```

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Active status (default=True) |
| `product_tmpl_id` | Many2one | Template (cascade, required) |
| `sequence` | Integer | Display order (default=10) |
| `attribute_id` | Many2one | Attribute (restrict, required) |
| `value_ids` | Many2many | Allowed PAVs (domain: same attribute) |
| `value_count` | Integer | Count of value_ids (computed, stored) |
| `product_template_value_ids` | One2many | Generated PTAVs (active and archived) |

**Constraints:**
- `_check_valid_values()` — Active lines must have at least one value; all values must match the attribute.
- Line's `attribute_id` cannot be changed after creation (blocked in `write()`).
- Line's `product_tmpl_id` cannot be changed after creation.

**`create()` — Reactivation pattern (L3 detail):**

When creating a PTAL that matches an archived PTAL (same template + same attribute), instead of creating a duplicate, the existing archived line is reactivated and updated with the new values. This preserves existing PTAVs and variants, allowing clean reactivation of attribute configurations.

**`_onchange_attribute_id()`**:
- If attribute is `no_variant`: auto-populates all existing PAVs for that attribute
- Otherwise: filters existing value_ids to only those matching the new attribute

**`_update_product_template_attribute_values()` (L3 detail):**

This is the bridge between PTAL configuration and PTAV records. For each line:
1. Existing PTAVs not in new `value_ids` → marked `ptav_active=False`, then `unlink()`
2. Existing archived PTAVs matching new values → reactivated
3. New PAVs not yet having a PTAV → `create()` with `price_extra = pav.default_extra_price`
4. Calls `product_tmpl_id._create_variant_ids()` at the end

**`unlink()` — Graceful archive fallback (L3 detail):**

Tries SQL delete first (fast path). On exception (foreign key, etc.): archives the line instead. After deletion, calls `_create_variant_ids()` on surviving templates to regenerate their variants.

---

### 10. product.template.attribute.value (PTAV)

**File:** `odoo/addons/product/models/product_template_attribute_value.py`

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
| `ptav_active` | Boolean | Active flag (not `active` — avoids `active_test` behavior) |
| `name` | Char | Related PAV name |
| `product_attribute_value_id` | Many2one | Source PAV (cascade) |
| `attribute_line_id` | Many2one | Source PTAL (cascade) |
| `price_extra` | Float | Extra price for this attribute value (default=0.0) |
| `currency_id` | Many2one | Related from template's currency |
| `exclude_for` | One2many | Exclusion rules (product.template.attribute.exclusion) |
| `product_tmpl_id` | Many2one | Related template (stored, index) |
| `attribute_id` | Many2one | Related attribute (stored, index) |
| `ptav_product_variant_ids` | Many2many | Variants using this PTAV (via `product_variant_combination`) |
| `html_color` | Char | Related from PAV |
| `is_custom` | Boolean | Related from PAV |
| `display_type` | Selection | Related from PAV |
| `color` | Integer | Palette color (1-11, random default) |
| `image` | Image | Related from PAV |

**Why `ptav_active` instead of `active`?** (L4 detail)

Using a custom `ptav_active` field instead of the ORM's built-in `active` avoids the `active_test` domain filter automatically applied by the ORM. This gives explicit control over which PTAVs should be considered during variant generation without fighting the ORM's global filtering mechanism.

**`unlink()` — Cascading cleanup (L3 detail):**

1. For single-value PTALs: removes PTAV from `product_template_attribute_value_ids` on variants (Command.unlink)
2. Calls `ptav_product_variant_ids._unlink_or_archive()` to clean up affected variants
3. Tries SQL delete; on exception: archives the PTAV (`ptav_active=False`)

**`_filter_single_value_lines()`** — Filters out PTAVs from PTALs with only one value. Used in `_get_combination_name()` to exclude single-value attributes from the displayed combination name (since they don't differentiate variants).

**`_without_no_variant_attributes()`** — Filters to PTAVs where `attribute_id.create_variant != 'no_variant'`.

**`_ids2str()`** — `"id1,id2,id3"` for sorted, comma-joined IDs. Used to populate `combination_indices` on variants.

---

### 11. product.template.attribute.exclusion

**File:** `odoo/addons/product/models/product_template_attribute_exclusion.py`

```python
class ProductTemplateAttributeExclusion(models.Model):
    _name = 'product.template.attribute.exclusion'
    _order = 'product_tmpl_id, id'
```

| Field | Type | Description |
|-------|------|-------------|
| `product_template_attribute_value_id` | Many2one | The excluding value (cascade) |
| `product_tmpl_id` | Many2one | The template (cascade, required) |
| `value_ids` | Many2many | Excluded PTAVs (domain: same template, active) |

**Trigger behavior**: `create()`, `write()`, `unlink()` all call `product_tmpl_id._create_variant_ids()` to regenerate variants respecting the new exclusion rules.

**Exclusion direction**: The rule means "if this PTAV is selected, the `value_ids` cannot be selected on the same variant." The `_complete_inverse_exclusions()` method on the template makes this bidirectional.

---

### 12. product.tag

**File:** `odoo/addons/product/models/product_tag.py`

```python
class ProductTag(models.Model):
    _name = 'product.tag'
    _order = 'sequence, id'

    _name_uniq = models.Constraint('unique (name)', 'Tag name already exists!')
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name (unique, translate, required) |
| `sequence` | Integer | Display order (default=10) |
| `color` | Char | CSS color (default `#3C3C3C`) |
| `product_template_ids` | Many2many | Templates with this tag (default: from context) |
| `product_product_ids` | Many2many | Variants with this tag (domain: must have attributes, not already in template_tags) |
| `product_ids` | Many2many | All variants (computed: template variants + variant-specific) |
| `visible_to_customers` | Boolean | Show to customers (default=True) |
| `image` | Image | Tag image (max 200x200) |

**Computed `product_ids`**: `product_template_ids.product_variant_ids | product_product_ids`. When template tag is added, all its existing and future variants inherit it through this computed field. Variant-specific tags are stored in `product_product_ids`.

**Constraint**: Tag name uniqueness is enforced at DB level via SQL constraint.

---

### 13. product.combo (Odoo 19)

**File:** `odoo/addons/product/models/product_combo.py`

A combo is a sellable bundle (product.template with `type='combo'`). The combo model defines the configuration, and the template links to it via `combo_ids`.

```python
class ProductCombo(models.Model):
    _name = 'product.combo'
    _order = 'sequence, id'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Combo name (required) |
| `sequence` | Integer | Display order (default=10, copy=False) |
| `company_id` | Many2one | Company |
| `combo_item_ids` | One2many | product.combo.item records |
| `combo_item_count` | Integer | Count of items (computed via _read_group) |
| `currency_id` | Many2one | Company currency (computed) |
| `base_price` | Float | Minimum price among items (computed, in combo currency) |

**`base_price` computation (L3 detail):** Converts each item's `lst_price` to combo currency using `currency_id._convert()`, then takes `min()`. This is the **minimum price prorate** — ensures the combo price is never less than choosing the cheapest items.

**Constraints:**
- `_check_combo_item_ids_not_empty()` — Combo must have at least one item.
- `_check_combo_item_ids_no_duplicates()` — No duplicate products within a combo.
- `_check_company_id()` — Validates company consistency on template combo_ids and combo_item product_ids.

---

### 14. product.combo.item (Odoo 19)

**File:** `odoo/addons/product/models/product_combo_item.py`

```python
class ProductComboItem(models.Model):
    _name = 'product.combo.item'
    _check_company_auto = True
```

| Field | Type | Description |
|-------|------|-------------|
| `company_id` | Many2one | Related from combo |
| `combo_id` | Many2one | Parent combo (cascade) |
| `product_id` | Many2one | Selected product (restrict, required, no combos) |
| `currency_id` | Many2one | Related from product |
| `lst_price` | Float | Related from product |
| `extra_price` | Float | Extra price for this item (default=0.0) |

**Constraint**: Product type must not be `'combo'` — combos cannot contain other combos.

---

### 15. product.document

**File:** `odoo/addons/product/models/product_document.py`

```python
class ProductDocument(models.Model):
    _name = 'product.document'
    _inherits = {'ir.attachment': 'ir_attachment_id'}
    _order = 'sequence, name'
```

| Field | Type | Description |
|-------|------|-------------|
| `ir_attachment_id` | Many2one | ir.attachment (cascade, required) |
| `active` | Boolean | Active status (default=True) |
| `sequence` | Integer | Display order (default=10) |

**Design pattern**: Uses `_inherits` to extend `ir.attachment` with product-specific behavior. All attachment fields (name, type, url, datas, etc.) come from the inherited model.

**URL validation**: `_onchange_url()` requires `https://`, `http://`, or `ftp://` prefix.

**Copy behavior**: `copy_data()` copies the underlying attachment with `no_document=True` context to prevent recursive document creation.

**Unlink**: Deletes both the document record and the underlying `ir_attachment_id`.

---

### 16. product.uom (Packaging Unit Barcode)

**File:** `odoo/addons/product/models/product_uom.py`

```python
class ProductUom(models.Model):
    _name = 'product.uom'
    _rec_name = 'barcode'
```

| Field | Type | Description |
|-------|------|-------------|
| `uom_id` | Many2one | uom.uom (cascade, required) |
| `product_id` | Many2one | product.product (cascade, required) |
| `barcode` | Char | Barcode (unique, btree_not_null) |
| `company_id` | Many2one | Company |

**`_barcode_uniq` constraint**: `unique(barcode)` at DB level.

**`_check_barcode_uniqueness()`** — Prevents barcode collision with `product.product` records (GS1 nomenclature shared namespace). Checks against all `product.product.barcode` and `product.uom.barcode` within company scope.

---

### 17. res.partner Extension

**File:** `odoo/addons/product/models/res_partner.py`

| Field | Type | Description |
|-------|------|-------------|
| `property_product_pricelist` | Many2one | Computed + inverse. Non-company-dependent but behaves like it. |
| `specific_property_product_pricelist` | Many2one | Company-dependent field holding the explicit partner pricelist. |

**`_compute_product_pricelist()`** — Delegates to `product.pricelist._get_partner_pricelist_multi()`. Respects `company` and `country_code` context.

**`_inverse_product_pricelist()`** — When partner form saves a new pricelist: compares against the country-default pricelist. If the chosen pricelist equals the country default, clears `specific_property_product_pricelist` (no need to store the default). Otherwise stores the partner-specific value.

This two-field design (`property_product_pricelist` + `specific_property_product_pricelist`) avoids storing company-dependent defaults in the company_dependent field, keeping the fallback resolution at the application layer.

---

### 18. res.company Extension

**File:** `odoo/addons/product/models/res_company.py`

**`_activate_or_create_pricelists()` (L3 detail)**

Called on company `create()` and when the pricelist feature group is activated:
1. Searches for existing empty-item pricelists matching the company's currency → unarchives them
2. Creates new "Default" pricelists for companies that still lack one
3. Uses `sudo()` to bypass access rights during creation

**`_get_default_pricelist_vals()`** — Returns vals for a default pricelist: name="Default", currency=company currency, company=company, sequence=10. Subclassed by `stock_landed_costs` to add landed cost valuation rules.

---

### 19. res.config.settings Extension

**File:** `odoo/addons/product/models/res_config_settings.py`

| Field | Type | Description |
|-------|------|-------------|
| `group_uom` | Boolean | Implied: `uom.group_uom` |
| `group_product_variant` | Boolean | Implied: `product.group_product_variant` |
| `module_loyalty` | Boolean | Implied: `loyalty.loyalty` |
| `group_product_pricelist` | Boolean | Implied: `product.group_product_pricelist` |
| `product_weight_in_lbs` | Selection | Config param: kg or lb |
| `product_volume_in_cubic_feet` | Selection | Config param: m3 or ft3 |

**On deactivating pricelist group**: Warns if any active pricelists exist. `set_values()`: if group was just enabled, calls `_activate_or_create_pricelists()` on all companies.

---

## Product Catalog Mixin

**File:** `odoo/addons/product/models/product_catalog_mixin.py`

Abstract mixin (`_name = 'product.catalog.mixin'`) for models that use the product catalog widget (Sale, Purchase, POS, etc.).

**Key methods that MUST be overridden by consumers:**

- `_get_product_catalog_domain()` — Returns domain for catalog search. Default: `company_id` match + `type != 'combo'`.
- `_get_product_catalog_record_lines(product_ids)` — Returns existing order lines grouped by product. Must return dict `{product: recordset}`.
- `_get_product_catalog_order_data(products, **kwargs)` — Returns dict of product data for products NOT yet in the order.
- `_update_order_line_info(product_id, quantity, **kwargs)` — Creates/updates order line. Returns unit price.
- `_is_readonly()` — Whether the order is read-only.

**HTTP JSONRPC endpoints** (catalog.py controller):
- `product_catalog_get_order_lines_info(res_model, order_id, product_ids)` → `_get_product_catalog_order_line_info()`
- `product_catalog_update_order_line_info(res_model, order_id, product_id, quantity)` → `_update_order_line_info()`

---

## Pricelist Report

**File:** `odoo/addons/product/report/product_pricelist_report.py`

**`report.product.report_pricelist`** — Renders HTML/PDF pricelist reports.

- Accepts `pricelist_id`, `active_ids` (products), `quantities` (list of qty values)
- Expands templates to variants if template has multiple variants
- Calls `pricelist._get_product_price(product, qty)` per product per quantity

---

## Label Reports

**File:** `odoo/addons/product/report/product_label_report.py`

Five report models:
- `report.product.report_producttemplatelabel2x7` — 2 rows x 7 columns
- `report.product.report_producttemplatelabel4x7` — 4 rows x 7 columns
- `report.product.report_producttemplatelabel4x12` — 4 rows x 12 columns
- `report.product.report_producttemplatelabel4x12noprice` — same but no price
- `report.product.report_producttemplatelabel_dymo` — DYMO-compatible

All delegate to `_prepare_data(env, docids, data)` which:
1. Reads `product.label.layout` wizard for layout params
2. Builds `quantity_by_product` dict from `quantity_by_product_in` data
3. Orders products by name desc (LIFO = correct label ordering on sheet)
4. Computes page count: `(total - 1) // (rows * columns) + 1`

---

## Model Relationship Summary

```
product.category (1) ───< (N) product.template
                              │
                              │ 1:N via _inherits
                              │ product_tmpl_id (cascade)
                              ▼
                       product.product ───< (N) product.pricelist.item
                              │                    ▲
          product.supplierinfo │                    │ N:1
          (vendor pricing)     │                    │ base_pricelist_id
                              ▼                    ▼
                       product.pricelist     product.pricelist.item
                              │
                              │ 1:N
                              ▼
                       product.pricelist.item
```

```
product.attribute (1) ───< (N) product.attribute.value
        │                           │
        │ 1:N                       │ 1:N
        ▼                           ▼
product.template.attribute.line ──── product.template.attribute.value
        │ (PTAL)                           │ (PTAV)
        │                           │
        │ N:1                          │ N:1
        ▼                           ▼
product.template ───────────────── product.product
        │
        │ N:N (via combo_ids)
        ▼
  product.combo ───< (N) product.combo.item ───> product.product

product.tag ─── N:N ─── product.template
                      └── N:N ─── product.product (additional)
```

---

## Key Computation Details

### Variant Generation: `has_dynamic_attributes()` vs Static

```
has_dynamic_attributes() == False:
  → All combinations generated via itertools.product at write time
  → Config parameter: product.dynamic_variant_limit (default 1000)
  → Exceeding limit raises UserError

has_dynamic_attributes() == True:
  → No automatic variant creation
  → Variants created on-demand via _create_product_variant(combination)
  → _get_possible_variants() only returns already-created variants
```

### Price Extra Inheritance

```
PTAV.price_extra (set on template attribute value)
  → Used as default when PTAL creates PTAV: price_extra = PAV.default_extra_price
  → Can be overridden per-PTAV without changing the PAV default
  → product.product.price_extra = sum(PTAV.price_extra for all PTAVs on variant)
  → lst_price = template.list_price + price_extra
```

When `default_extra_price_changed` is True on a PAV, it signals that the wizard should offer to update all related PTAV price_extras.

### Archive vs Delete Behavior

| Model | Delete | Archive behavior |
|-------|--------|-----------------|
| `product.attribute` | Blocked if used on products | Blocked if used on products |
| `product.attribute.value` | If no linked products: delete; if only archived variants: archive | N/A |
| `product.template.attribute.line` | Tries delete; on exception: archive | Clears value_ids |
| `product.template.attribute.value` | Tries delete; on exception: archive; cascades to variants | Sets ptav_active=False |
| `product.product` | Tries unlink; on exception: archive; if last variant + non-dynamic: also deletes template | Cascades to template if last variant |

### Standard Price and Costing Methods

The `product.template.standard_price` field is a computed+inverse field with deep integration:
- **AVCO (Average Cost)**: `stock.account` module automatically averages `standard_price` from incoming landed costs and manual updates
- **FIFO**: `stock_account` uses `standard_price` at time of receipt to compute landed cost
- **Manual**: Users directly edit `standard_price` (visible only to `base.group_user`)
- **Company dependency**: Each company gets its own cost per variant via the `company_dependent` flag

### Exclusions: Bidirectional Completion

When a PTAV A has an exclusion rule pointing to PTAV B:
1. The exclusion is stored as: `{A.id: [B.id]}`
2. `_complete_inverse_exclusions()` adds: `{B.id: [A.id]}` automatically
3. Variant generation filters out any combination containing both A and B

This means setting one exclusion creates two directional blocks in a single operation.

---

## L4: Performance Patterns and Optimizations

### 1. `product_variant_id` Field — Prefetch Optimization

The `product_variant_id` (Many2one to product.product) is computed as `product_variant_ids[:1]` — fetching only the first variant record. This avoids loading all variant IDs when only one is needed, which is the common case for single-variant products.

```python
@api.depends('product_variant_ids')
def _compute_product_variant_id(self):
    for template in self:
        template.product_variant_id = template.product_variant_ids[:1]
```

Without this field, views showing single-variant products would trigger `product_variant_ids` (the full One2many), loading all variant IDs even when only one exists.

### 2. `combination_indices` — Stored Indexed Variant Lookup

The `combination_indices` Char field is stored and indexed (btree) on `product.product`. It stores a comma-separated, sorted string of PTAV IDs:

```python
def _compute_combination_indices(self):
    for variant in self:
        variant.combination_indices = ','.join(
            sorted(str(id) for id in variant.product_template_attribute_value_ids.ids)
        )
```

The unique partial index `UNIQUE (product_tmpl_id, combination_indices) WHERE active IS TRUE` uses this stored field to enforce uniqueness without computing the combination on each insert/update. The `_get_variant_id_for_combination()` cached method uses this field for O(log n) lookups.

### 3. `@tools.ormcache` — Cached Variant Lookup

`_get_variant_id_for_combination()` and `_get_first_possible_variant_id()` use `ormcache` to cache results at the registry level:

```python
@tools.ormcache('self.env.uid', 'self.env.company_id.id', 'combination_key')
def _get_variant_id_for_combination(self, combination_key):
    ...
```

Cache invalidation happens in `product.product`:
- `create()`: `self.env.registry.clear_cache()`
- `write()` (when `product_template_attribute_value_ids` or `active` changes): `self.env.registry.clear_cache()`

This is critical because `_get_variant_id_for_combination` is called during sales/purchase order line creation (every time a product is added to an order). Without caching, each configurator call would hit the database.

**Odoo 19 addition**: The registry cache clearing was explicitly added because the previous uncached version caused N+1 query problems at scale.

### 4. `_unlink_or_archive()` Dichotomy Algorithm

When bulk-deleting variants (e.g., after removing an attribute value), the dichotomy algorithm handles real-world blockers (stock moves, sale lines):

```python
def _unlink_or_archive(self, check_access=True):
    if check_access:
        self.check_access('unlink')
    
    try:
        with self.env.cr.savepoint():
            self.mapped('product_tmpl_id').write({'active': False})
            self.unlink()
    except Exception:
        if len(self) == 1:
            # Single record: archive it
            self.write({'active': False})
        else:
            # Split in half and retry
            first_half = self[:len(self) // 2]
            second_half = self[len(self) // 2:]
            first_half._unlink_or_archive(check_access=False)
            second_half._unlink_or_archive(check_access=False)
```

The binary search pattern isolates individual blocking records. This is necessary because one blocking record (e.g., one variant referenced in a stock move) would prevent deletion of all other valid variants in a batch operation.

### 5. `_cartesian_product()` — Pruning Generator

The smart Cartesian product generator skips entire branches of the combination tree when exclusions are found early:

```python
def _cartesian_product(self, ptal_values, parent_combination=None, ...):
    # Standard itertools.product generates all combinations first
    # This version prunes branches where a partial combination is impossible
    for combination in self._cartesian_product(...):
        if self._is_combination_possible(combination[:current_depth], ...):
            yield combination
        # If impossible at depth N, skip all combinations starting with this prefix
```

This transforms a 10-attribute product with 5 values each from 9,765,625 naive combinations to a manageable set by pruning early when exclusions are found at intermediate depths.

### 6. Pricelist Rule — Single-Query Fetch

`_get_applicable_rules()` fetches ALL potentially applicable rules for ALL products in a single `search()` call:

```python
# Single DB query for all products
rule_ids = self.env['product.pricelist.item'].search(
    self._get_applicable_rules_domain(products, date)
)
```

This is more efficient than N queries for N products because:
- PostgreSQL can use the composite index `(pricelist_id, applied_on, min_quantity)` efficiently
- Rules are filtered in Python after fetching, avoiding complex OR domains with subqueries
- The domain `applied_on` sort order from `_order` gives correct priority without post-query sorting

### 7. `name_search` Progressive Strategy

The progressive name search avoids expensive translation table JOINs:

```python
def name_search(self, name, args, operator, limit):
    # Step 1: exact match on indexed default_code (fastest path)
    if name:
        domain = ['|', '|', '|',
            ('default_code', '=', name),   # exact, indexed
            ('barcode', '=', name),          # exact, indexed
            ('default_code', '=ilike', name + '%'),  # prefix, indexed
            ('name', 'ilike', '%' + name + '%')  # fallback
        ]
    results = self.search(domain, limit=limit)
    # If still not enough, search by supplier info in separate query
    ...
```

### 8. `_compute_product_count()` — Read Group Optimization

`product.category._compute_product_count()` uses `_read_group` with `child_of` to avoid N+1 queries:

```python
group_data = self.env['product.template']._read_group(
    [('categ_id', 'child_of', self.ids)],
    ['categ_id'],
    ['__count']
)
# Returns aggregated counts for each category including children
# Single query instead of N queries for N categories
```

---

## L4: Odoo 18 to Odoo 19 Changes

### 1. Combo Product Type (New in Odoo 19)

The `type='combo'` selection value and `product.combo` / `product.combo.item` models are entirely new in Odoo 19. Key behaviors:
- A combo template cannot have `attribute_line_ids`
- A combo template cannot be a `purchase_ok` product
- `product.combo.base_price` computes the minimum prorate as `min(item.lst_price)` converted to combo currency
- Combo items cannot themselves be combo products (enforced by `ondelete='restrict'`)

### 2. `product_tooltip` Field (Odoo 19)

New computed Char field returns tooltip text for product type:
- `type='combo'`: "This product is a combo: it includes several products that your customers can pick."
- Other types: empty or type-specific tooltip

### 3. `is_dynamically_created` Field (Odoo 19)

New computed Boolean on `product.template`: True if any PTAL has an attribute with `create_variant='dynamic'`. Previously, this could only be inferred by checking `attribute_line_ids` directly.

### 4. `display_applied_on` Field (Odoo 19)

New Selection field (`'1_product'` / `'2_category'`) separates UI picker state from the actual `applied_on` field value. This prevents the UI from inadvertently changing the rule's application scope when editing.

### 5. `is_product_variant` Field (Odoo 19)

Both `product.template` (always False) and `product.product` (always True) now explicitly mark their role. Previously, code had to check `_name` or use `isinstance()` checks.

### 6. Registry Cache Clearing for Variant Lookup (Odoo 19)

`_get_variant_id_for_combination()` gained `ormcache` in Odoo 19, requiring explicit cache clearing in `product.product.write()` and `create()`. Previously this was uncached, causing performance degradation for catalogs with many dynamic products.

### 7. Product Document Model (Odoo 19)

`product.document` via `_inherits ir.attachment` is new in Odoo 19. Provides product-specific document management separate from general attachments.

### 8. Pricelist Recursion DFS Check (Odoo 19)

`_check_pricelist_recursion()` using DFS path detection was added to prevent infinite loops when `base='pricelist'` creates circular references. Previously, such loops would cause infinite recursion at runtime.

### 9. `write_date` Sync for Image Cache Busting (Odoo 19)

`_compute_write_date()` on `product.product` (syncing variant write_date with template write_date for HTTP cache invalidation) was made explicit in this version.

### 10. `price_markup` Field (Odoo 19)

New computed+inverse Float field on `product.pricelist.item` that represents the inverse of `price_discount` when `base='standard_price'`. Allows markup entry in percentage form rather than requiring negative discount calculations.

---

## L4: Security Considerations

### 1. `standard_price` — Access Control on Cost Data

```python
# In _price_compute on product.product
if price_type == 'standard_price':
    # Use sudo() so non-cost-viewing users can still compute sale prices
    product_standard_price = product.sudo().standard_price
```

The `standard_price` field has `groups='base.group_user'` (restricted to employees). Without `sudo()`, a sales rep adding a product to a quotation would get an AccessError when the pricelist rule uses `base='standard_price'`. The `sudo()` call fetches the cost without raising an error, allowing price computation to succeed.

### 2. `product.supplierinfo` — ACL-Based Field Filtering

```python
def _compute_product_code(self):
    sellers = self.seller_ids.filtered(
        lambda s: s.env['product.supplierinfo'].check_access_rights('read', raise_exception=False)
    )
    # Only show supplier codes if user has read access
```

Without this check, users without `product.supplierinfo` read access would receive an AccessError when searching for products by supplier code, even if the search ultimately returns no results.

### 3. Commercial Fields Propagation

`specific_property_product_pricelist` on `res.partner` is in `_synced_commercial_fields()`:

```python
# In res_partner.py
property_product_pricelist = fields.Many2one(
    'product.pricelist',
    compute='_compute_product_pricelist',
    inverse='_inverse_product_pricelist',
    search='_search_product_pricelist',
)

specific_property_product_pricelist = fields.Many2one(
    'product.pricelist',
    company_dependent=True,
)

# The field is in commercial fields, so it auto-propagates to child companies
```

When a contact has a specific pricelist assigned, child companies inherit this assignment automatically.

### 4. Multi-Company Access Control

`product.product` uses `_check_company_domain = models.check_company_domain_parent_of`:
- This validates that when a product is assigned to a company, it can only be accessed by that company or parent companies
- Prevents cross-company product visibility in multi-company deployments
- Pricelist items use `_check_company_auto = True`, automatically validating company consistency on create/write

### 5. Barcode Uniqueness — Per-Company Scope

Barcode uniqueness is enforced **per company**, not globally:

```python
# In _check_barcodes_by_company
barcode_by_company = defaultdict(set)
for product in products:
    if product.barcode:
        barcode_by_company[product.company_id].add(product.barcode)
```

This allows the same barcode to be used on products belonging to different companies. This is intentional: in multi-company setups with separate product catalogs, barcode duplication within a company is the real constraint, not global uniqueness.

### 6. GS1 Barcode Namespace

`product.uom` (packaging barcodes) and `product.product.barcode` share the same barcode namespace because GS1 nomenclature does not distinguish between product barcodes and packaging barcodes. The `_check_barcode_uniqueness()` method checks both models together to prevent conflicts.

### 7. Invisible Fields by Group

Several fields have `groups` attributes to hide them from users without appropriate permissions:
- `standard_price`: `base.group_user` (cost visible only to employees)
- `seller_ids` visibility: controlled by `product.group_product_pricelist`

---

## L4: Failure Modes and Edge Cases

| Scenario | Behavior |
|----------|----------|
| Set `standard_price` on multi-variant template | Value set on template only; each variant retains its own cost |
| Delete attribute used on products | Blocked with UserError listing affected products |
| Delete attribute value used on archived variants only | Archives the value instead of deleting |
| Change UoM on template with existing transactions | Warning shown; must confirm. Stock module handles conversion. |
| Create PTAL matching an archived PTAL | Existing archived line is reactivated and updated |
| Variant delete fails (has stock moves) | Archives the variant instead |
| Last variant archived on template | Template also archived (and vice versa) |
| Price set via percentage discount = 100% | Results in `0.0` price (not free product, explicitly zero) |
| `price_min_margin > price_max_margin` | Constrained — raises ValidationError |
| Recursive pricelist reference | DFS cycle detection — raises ValidationError with cycle path |
| Barcode same as a packaging barcode | ValidationError — GS1 shared namespace enforcement |
| Copy product.product | Copies the template and returns the first variant |
| Dynamic attribute template variant count | Always 0 in `product_variant_count` (dynamic = not pre-generated) |
| Archive template with no variants | Triggers `_create_variant_ids()` (may create a default variant) |
| Change attribute `create_variant` on used attribute | Blocked — attribute must not be used on any active products |
| Multi-checkbox display type without no_variant | SQL constraint prevents creation |
| Set combo product as combo item | `ondelete='restrict'` on `product_id` prevents it |

---

## L4: Extension Points and Override Patterns

### Custom Cost Sources

The `product.template._price_compute` method calls `product._price_compute` on each product. To add a custom cost source (e.g., from a cost management module), override `_price_compute` on `product.product`:

```python
class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _price_compute(self, price_type, uom=None, currency=None, company=None, date=False):
        if price_type == 'standard_price' and self.env.context.get('use_my_cost_module'):
            # Custom cost computation
            return {p.id: p._get_my_custom_cost() for p in self}
        return super()._price_compute(price_type, uom, currency, company, date)
```

### Custom Variant Generation

Override `_create_variant_ids()` on `product.template` to add custom pre/post-processing:
- Pre-processing: modify PTAL values before generation
- Post-processing: set additional fields on newly created variants

### Custom Price Rules

Override `_is_applicable_for()` or `_compute_price()` on `product.pricelist.item` to add custom matching logic (e.g., time-of-day pricing, customer segment pricing).

### Custom Seller Selection

Override `_select_seller()` on `product.product` to customize vendor selection logic (e.g., prefer vendors with best delivery performance).

---

**Source Module**: `odoo/addons/product`
**Last Updated**: 2026-04-11
**Source Version**: Odoo 19.0 (manifest 1.2)
**Documentation Level**: L4 (Full Depth Escalation)
