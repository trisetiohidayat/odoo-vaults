# Odoo 18 Product Module - L3 Documentation

## Module Overview
**Path:** `~/odoo/odoo18/odoo/addons/product/models/`
**Purpose:** Product management, pricing, variants, and attributes

---

## Core Models

### 1. product.template (Product Template)

Master product definition that can have multiple variants.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Product name (required, translatable) |
| `type` | Selection | consu (goods), service, combo |
| `categ_id` | Many2one | Product category |
| `list_price` | Float | Sales price |
| `standard_price` | Float | Cost price |
| `volume` | Float | Volume (m³) |
| `weight` | Float | Weight |
| `uom_id` | Many2one | Unit of measure |
| `uom_po_id` | Many2one | Purchase unit |
| `company_id` | Many2one | Company |
| `active` | Boolean | Active status |
| `default_code` | Char | Internal reference |
| `barcode` | Char | Barcode |
| `description` | Html | Description |
| `description_sale` | Text | Sales description |
| `description_purchase` | Text | Purchase description |
| `sale_ok` | Boolean | Can be sold |
| `purchase_ok` | Boolean | Can be purchased |
| `attribute_line_ids` | One2many | Product attributes |
| `product_variant_ids` | One2many | Product variants |
| `product_variant_count` | Integer | Number of variants |
| `seller_ids` | One2many | Vendor information |
| `packaging_ids` | One2many | Package types |
| `combo_ids` | Many2many | Combo items |
| `service_tracking` | Selection | no (for non-services) |
| `product_tag_ids` | Many2many | Product tags |
| `product_properties` | Properties | Dynamic properties |

#### Product Types

| Type | Description | Inventory |
|------|-------------|-----------|
| `consu` | Consumable/Goods | Tracked |
| `service` | Service product | Not tracked |
| `combo` | Combo/bundle product | Not tracked |

#### Service Tracking (Odoo 18 has simplified)

```python
# For services:
service_tracking = 'no'  # Default, only option for non-services
```

#### Key Methods

**`_compute_template_field_from_variant_field(fname, default)`**
- Copies value from unique variant to template
- Used for barcode, weight, volume, standard_price

**`_set_product_variant_field(fname)`**
- Propagates template value to unique variant

**`_get_default_category_id()`**
- Returns 'All' category (cached)
- Cannot be deleted

**`_get_default_uom_id()`**
- Returns 'Unit(s)' (cached)
- Cannot be deleted

#### Cross-Model Relationships

| Relationship | Model | Purpose |
|--------------|-------|---------|
| `product_variant_id` | product.product | First variant |
| `categ_id` | product.category | Category |
| `seller_ids` | product.supplierinfo | Vendor pricing |

#### Edge Cases

1. **Single variant**: Propagates fields between template and variant
2. **No variants**: Template fields used directly
3. **Archived variants**: Counted with `active_test=False`
4. **Company-specific**: UoM category must match
5. **Barcode uniqueness**: Checked across variants

---

### 2. product.product (Product Variant)

Specific product with combination of attributes.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `product_tmpl_id` | Many2one | Parent template (required, cascade delete) |
| `default_code` | Char | Internal reference |
| `barcode` | Char | Barcode (unique per company) |
| `standard_price` | Float | Cost (company dependent) |
| `volume` | Float | Volume |
| `weight` | Float | Weight |
| `price_extra` | Float | Extra price from attributes |
| `lst_price` | Float | Sales price (computed) |
| `product_template_attribute_value_ids` | Many2many | Attribute combination |
| `combination_indices` | Char | Stored combination hash |
| `packaging_ids` | One2many | Package types |
| `active` | Boolean | Active status |

#### Inheritance

Uses `_inherits` to inherit from `product.template`:
```python
_inherits = {'product.template': 'product_tmpl_id'}
```

#### Price Computation

```python
lst_price = list_price + price_extra

# Where:
# - list_price: from template
# - price_extra: sum of attribute value extras
```

#### Key Methods

**`_compute_product_lst_price()`** - Computes sale price
```python
lst_price = list_price + price_extra
# With UoM conversion if context uom specified
```

**`_compute_product_price_extra()`** - Sums attribute extras
```python
price_extra = sum(attribute_value_ids.mapped('price_extra'))
```

**`_check_barcode_uniqueness()`** - Validates barcode
- Unique per company
- Checks both products and packagings

**`create(vals_list)`** - Special handling
```python
# Clears cache after creation
self.env.registry.clear_cache()
```

**`write(values)`** - Clears cache if attributes change

**`unlink()`** - Cascades to template if last variant

#### Variant Creation Logic

```python
# When all variants deleted, template remains
# When last variant deleted, can optionally delete template
# combination_indices determines uniqueness
```

---

### 3. product.category (Product Category)

Hierarchical category structure.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Category name |
| `complete_name` | Char | Full path (computed) |
| `parent_id` | Many2one | Parent category |
| `child_id` | One2many | Child categories |
| `product_count` | Integer | Products in category |
| `product_properties_definition` | Properties | Dynamic properties |

#### Hierarchy

- Uses `_parent_store = True` for efficient hierarchy queries
- `parent_path` field stores full path
- Recursive computation for `complete_name`

#### Key Methods

**`_compute_complete_name()`**
```python
complete_name = parent.complete_name + ' / ' + name
```

**`_compute_product_count()`** - Counts products
- Includes products in child categories
- Uses `search([('id', 'child_of', categ.ids)])`

#### Undeleteable Categories

```python
# Cannot delete these:
- product_category_all (All)
- cat_expense (Expenses)
- product_category_1 (All / Saleable)
```

---

### 4. product.pricelist (Pricelist)

Defines pricing rules for products.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Pricelist name |
| `active` | Boolean | Active status |
| `sequence` | Integer | Priority |
| `currency_id` | Many2one | Currency |
| `company_id` | Many2one | Company |
| `country_group_ids` | Many2many | Country groups |
| `item_ids` | One2many | Pricing rules |

#### Country-Based Selection

Pricelists can be restricted to country groups.
If no group matches, falls back to:
1. Country-specific pricelist
2. Default pricelist
3. First active pricelist

#### Key Methods

**`_compute_price_rule(products, quantity, ...)`** - Core pricing
```python
# Returns: {product_id: (price, rule_id)}
# 1. Fetch applicable rules
# 2. Find first matching rule
# 3. Compute price from rule
```

**`_get_applicable_rules(products, date)`**
```python
# Searches rules matching:
# - Pricelist
# - Category (with parent_of)
# - Product/template
# - Date range
```

**`_get_products_price(products, ...)`**
```python
# Returns: {product_id: price}
```

**`_get_product_price(product, ...)`**
```python
# Returns: price (float)
```

**`_get_partner_pricelist_multi(partner_ids)`**
```python
# Priority order:
# 1. Specific property (res.partner property)
# 2. Country group pricelist
# 3. Default property
# 4. First active pricelist
```

---

### 5. product.pricelist.item (Pricing Rule)

Single rule within a pricelist.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `pricelist_id` | Many2one | Parent pricelist |
| `applied_on` | Selection | 3_global, 2_product_category, 1_product, 0_product_variant |
| `categ_id` | Many2one | Category (if applied_on=2) |
| `product_tmpl_id` | Many2one | Template (if applied_on=1) |
| `product_id` | Many2one | Variant (if applied_on=0) |
| `min_quantity` | Float | Minimum quantity |
| `date_start` | Datetime | Rule start date |
| `date_end` | Datetime | Rule end date |
| `base` | Selection | list_price, standard_price, pricelist |
| `base_pricelist_id` | Many2one | Base pricelist (if base=pricelist) |
| `compute_price` | Selection | fixed, percentage, formula |
| `fixed_price` | Float | Price (if compute_price=fixed) |
| `percent_price` | Float | Discount % (if compute_price=percentage) |
| `price_discount` | Float | Discount % (if compute_price=formula) |
| `price_surcharge` | Float | Extra fee |
| `price_round` | Float | Rounding precision |
| `price_min_margin` | Float | Minimum margin |
| `price_max_margin` | Float | Maximum margin |

#### Applied On Hierarchy

```
3_global: All products (lowest priority)
2_product_category: Category products
1_product: Specific template
0_product_variant: Specific variant (highest priority)
```

#### Price Computation Methods

**`fixed`**: Direct price
```python
price = fixed_price
```

**`percentage`**: Discount from base
```python
price = base_price * (1 - percent_price/100)
```

**`formula`**: Complex calculation
```python
# price = base_price * (1 - price_discount/100) + price_surcharge
# With margins applied
# With rounding
```

#### Formula Variables

| Variable | Description |
|----------|-------------|
| `p` | Base price |
| `dp` | Discounted price |
| `ps` | Surcharge |
| `pc` | Price with costs |
| `pa` | Price with margin |
| `u` | Unit of measure factor |

#### Key Methods

**`_is_applicable_for(product, quantity)`**
- Checks min_quantity
- Checks date range
- Checks applied_on matching

**`_compute_price(product, quantity, uom, date, currency)`**
```python
# 1. Get base price
# 2. Apply discount/formula
# 3. Apply rounding
# 4. Apply margins
# 5. Convert currency
```

#### Constraints

```python
# Cannot be own base pricelist
"CHECK NOT (base = 'pricelist' AND base_pricelist_id = pricelist_id)"

# Date range must be valid
"CHECK (date_start IS NULL OR date_end IS NULL OR date_start < date_end)"

# Margins must be valid
"CHECK (price_min_margin <= price_max_margin)"

# Must specify product/category based on applied_on
```

---

### 6. product.attribute (Attribute)

Defines attribute types for product variants.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Attribute name |
| `display_type` | Selection | radio, select, multi, color |
| `create_variant` | Selection | always, dynamic, variants_only |
| `value_ids` | One2many | Attribute values |

#### Create Variant Options

| Option | Description |
|--------|-------------|
| `always` | Create variants for all combinations |
| `dynamic` | Create variants on-demand |
| `variants_only` | Only create explicit combinations |

#### Display Types

| Type | UI | Use Case |
|------|-----|----------|
| `radio` | Radio buttons | Single selection |
| `select` | Dropdown | Single selection |
| `multi` | Checkboxes | Multiple selection |
| `color` | Color swatches | Color variants |

---

### 7. product.attribute.value (Attribute Value)

Values for an attribute.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Value name |
| `attribute_id` | Many2one | Parent attribute |
| `sequence` | Integer | Display order |
| `color` | Char | HTML color (for color type) |
| `html_color` | Char | Color code |
| `is_custom` | Boolean | Custom value allowed |

---

### 8. product.template.attribute.line (Template Attribute Line)

Links attributes to product templates.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `attribute_id` | Many2one | Attribute |
| `value_ids` | Many2many | Allowed values |
| `product_tmpl_id` | Many2one | Template |

#### Key Methods

**`_is_configurable()`** - Determines if line is configurable
```python
# True if:
# - Multiple values selected
# - Any value is custom
# - Display type is multi
```

---

### 9. product.template.attribute.value (Template Attribute Value)

Specific value assigned to a template.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `product_attribute_value_id` | Many2one | Attribute value |
| `product_tmpl_id` | Many2one | Template |
| `attribute_id` | Many2one | Attribute (computed) |
| `attribute_line_id` | Many2one | Line (computed) |
| `price_extra` | Float | Additional price |
| `html_color` | Char | Color (computed) |
| `ptav_active` | Boolean | Active flag |

---

## Variant Generation Logic

### Dynamic Variant Creation

When `create_variant='dynamic'`:

1. User selects attribute values
2. Variant created on-demand via `_get_variant_id_for_combination()`
3. No pre-generated combinations

### Always Variant Creation

When `create_variant='always'`:
1. All combinations generated upfront
2. `product.product` created for each combination
3. `combination_indices` unique per active variant

### Variants Only

When `create_variant='variants_only'`:
1. Only explicitly defined combinations created
2. No automatic generation

---

## Pricelist Resolution Algorithm

```
1. Get partner's applicable pricelist
2. For each product:
   a. Search applicable rules
   b. Sort by priority (applied_on)
   c. Find first matching rule
   d. Compute price from rule
3. Return prices
```

### Rule Priority (applied_on)

```
Highest: 0_product_variant (specific variant)
         1_product (specific template)
         2_product_category (category + parents)
Lowest:  3_global (all products)
```

### Price Calculation Formula

```python
# For formula type:
P = base_price * (1 - discount/100) + surcharge

# After rounding:
P = round(P, price_round)

# With margins:
if P < base_price + price_min_margin:
    P = base_price + price_min_margin
if P > base_price + price_max_margin:
    P = base_price + price_max_margin
```

---

## Pricing Context

### Price Context Keys

```python
PRICE_CONTEXT_KEYS = ['pricelist', 'quantity', 'uom', 'date']
```

### Usage in Computations

```python
# Get context
context = self.env.context

# Use in price computation
uom = context.get('uom')
quantity = context.get('quantity', 1.0)
date = context.get('date') or fields.Date.today()
```

---

## UoM Conversion in Pricing

```python
# Convert quantity to product's UoM
if target_uom != product_uom:
    qty_in_product_uom = target_uom._compute_quantity(
        quantity, product_uom, raise_if_failure=False
    )
```

---

## Product Properties (Dynamic Fields)

Products can have dynamic properties defined at category level.

### Definition

```python
# On product.category:
product_properties_definition = fields.PropertiesDefinition()

# On product.template:
product_properties = fields.Properties(
    definition='categ_id.product_properties_definition'
)
```

### Usage

- Defined per category
- Inherited by child categories
- Available on product template
- Used for custom data (e.g., dimensions, certifications)

---

## Packaging

### product.packaging

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Package name |
| `qty` | Float | Units per package |
| `barcode` | Char | Package barcode |
| `product_id` | Many2one | Product |
| `product_tmpl_id` | Many2one | Template |
| `company_id` | Many2one | Company |

#### Constraints

- Barcode unique across products and packagings
- Shares same barcode pattern (GS1 nomenclature)

---

## Product Document Management

### product.document

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Document name |
| `res_model` | Char | Model reference |
| `res_id` | Integer | Record ID |
| `ir_attachment_id` | Many2one | Attachment |

---

## Combo Products (Odoo 18)

### product.combo

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Combo name |
| `combo_item_ids` | One2many | Items in combo |
| `list_price` | Float | Combo price |
| `product_template_id` | Many2one | Combo product template |

### product.combo.item

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `combo_id` | Many2one | Parent combo |
| `product_id` | Many2one | Product variant |
| `quantity` | Float | Quantity in combo |
| `extra_price` | Float | Additional price |

---

## Product Tags

### product.tag

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name |
| `color` | Integer | Color index |
| `sequence` | Integer | Display order |

---

## Barcode Handling

### Validation Rules

```python
# GS1 nomenclature used
# Barcodes unique per company
# Checked for both products and packagings
```

### Search Methods

```python
def _get_barcodes_by_company(self):
    # Groups barcodes by company
    return [(company_id, [barcodes])]

def _check_barcode_uniqueness(self):
    # Validates no duplicates within company
```

---

## Image Handling

### Image Priority

```
product_product.image_variant_1920 > product_template.image_1920
```

### Computed Fallback

```python
def _compute_image_1920(self):
    # Uses variant image if set
    # Falls back to template image
    self.image_1920 = self.image_variant_1920 or self.product_tmpl_id.image_1920
```

### Write Cache Invalidation

```python
# When template image updated:
# Product's write_date updated to match
# Forces browser cache refresh
```

---

## Company-Dependent Fields

### Standard Price

Stored per company on `product.product`:
```python
standard_price = fields.Float(company_dependent=True)
```

### Resolution

```python
# Resolved via ir.property
# Falls back to template value
# Company context affects resolution
```

---

## Security

### Access Groups

| Field | Group | Access |
|-------|-------|--------|
| `standard_price` | base.group_user | Read only |
| `cost` | product.group_costing_access | Full |

---

## Performance Considerations

### Caching

- `tools.ormcache()` for default category/UoM
- Computed fields with strategic dependencies
- Batch price computation

### Database Indexes

```sql
-- Variant combination uniqueness
CREATE UNIQUE INDEX product_product_combination_unique
ON product_product (product_tmpl_id, combination_indices)
WHERE active is true

-- Barcode indexes
CREATE INDEX product_product_barcode ON product_product (barcode)
WHERE barcode IS NOT NULL
```

### Optimization Strategies

1. **Combination indices**: String stored for fast lookup
2. **Batch variant creation**: Registry cache cleared once
3. **Price computation**: Single query for multiple products
4. **Category product count**: Cached read_group

---

## Extension Points

### Custom Pricing

```python
# Override _compute_price_rule in Pricelist
class CustomPricelist(models.Model):
    _inherit = 'product.pricelist'

    def _compute_price_rule(self, products, ...):
        # Custom pricing logic
        return super()._compute_price_rule(products, ...)
```

### Custom Attributes

```python
# Extend product.template.attribute.value
class CustomAttributeValue(models.Model):
    _inherit = 'product.template.attribute.value'

    # Add custom fields
    # Override price_extra computation
```

### Variant Creation Hook

```python
# After variant created
def _create_product_variant(self):
    # Custom logic after variant creation
```

---

## Related Modules

- `sale`: Sales order integration
- `purchase`: Purchase order integration
- `stock`: Inventory management
- `mrp`: Manufacturing
- `product_email_template`: Email templates
- `product_images`: Additional images
- `product_expiry`: Expiration tracking
- `product_margin`: Margin analysis
