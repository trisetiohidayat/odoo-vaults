---
type: module
name: product
version: Odoo 18
models_count: ~20
documentation_date: 2026-04-11
tags: [product, inventory, pricing, variant, attribute, pricelist]
---

# Product

Product master data, variants, attributes, pricing, and barcode management.

## Models

### product.template

Master product definition. One `product.template` can have multiple `product.product` variants.

**Key Fields:**
- `name`, `type` — `consu` (consumable), `service`, `storable` (stockable), `combo`
- `categ_id` (`product.category`) — Category
- `list_price`, `standard_price` — Pricing
- `seller_ids` (`product.supplierinfo`) — Vendor pricing
- `variant_seller_ids` — Variant-specific vendor pricing
- `description`, `description_sale`, `description_purchase` — Text fields
- `UOM_id`, `UOM_po_id` (`uom.uom`) — Sales and Purchase units
- `invoice_policy` — `order` (invoice what you order) or `delivered` (invoice what's delivered)
- `expense_policy` — `no`, `at_cost`, `FAI` (at factor cost)
- `service_type` — `manual` or `task` (timesheet billing)
- `tracking` — `none`, `serial`, `batch`
- `service_tracking` — `no`, `task_in_project`, `task_global_project`, `project_only`
- `responsible_id` (`res.users`) — Person responsible
- `calendar_id` (`resource.calendar`) — For service scheduling
- `quoted_delivery_date` — Promised delivery date
- `product_pricing_ids` — Tiered pricing rules
- `categ_id` — Sets `property_cost_method`, `property_valuation`
- `attribute_line_ids` — Defines variant generation

**L3 Variant Generation:**
- `attribute_line_ids` creates `product.template.attribute.line` per attribute
- `value_ids` on each line defines which values generate variants
- `combination_indices` (char) — Hash of selected attribute values; triggers `_create_variant_ids()`
- `create_variant_ids()` — Creates `product.product` records for each combination
- `dynamic`: `_create_variant_ids()` waits for first order before creating variant
- `_is_combination_possible()` — Checks if a combination is valid (not excluded by attribute)

**L3 Price Computation:**
1. `list_price` is base
2. `product.pricelist.item` rules modify: discounts, formulas
3. `_price_compute('list_price', ...)` uses `product.tmpl_id._price_get()` → `pricelist._price_get()`

### product.product

Product variant. Created from `product.template` + attribute values. Uses `_inherits = {'product.template': 'product_tmpl_id'}`.

**Key Fields:**
- `product_tmpl_id` (`product.template`) — Parent template (delegate)
- `default_code` — Internal reference
- `barcode` — EAN/UPC barcode
- `active`
- `product_template_attribute_value_ids` — Selected attribute values
- `combination_indices` — Hash of attribute values (matches template's index)
- `lst_price`, `standard_price` — Inherited from template, can be overridden
- `volume`, `weight` — Physical dimensions

**L3 Variant Exclusion:**
- `product.template.attribute.value` can set `exclude_for` → prevents certain combinations
- `combination_problem` is the set of all excluded combinations

**L3 Barcode Uniqueness:**
SQL constraint: `UNIQUE(barcode)` across all products. Raise error if duplicate.

### product.category

**Key Fields:**
- `name`, `parent_id` — Hierarchical (MPTT-like via `parent_path`)
- `complete_name` — Full path name
- `property_valuation` — `manual_periodic` or `real_time`
- `property_cost_method` — `standard`, `average`, `fifo`
- `property_stock_journal_id` — For real-time valuation
- `property_account_income_categ_id`, `property_account_expense_categ_id` — Default accounts

**L3:** Category-level settings cascade to products. Changing `cost_method` on category recalculates product standard prices.

### product.pricelist

**Key Fields:**
- `name`, `country_group_ids` — Geographic restriction
- `discount_policy` — `with_discount` (show discounted price) or `without_discount` (show full + discount)
- `currency_id` (`res.currency`)
- `item_ids` (`product.pricelist.item`) — Price rules
- `version_ids` — Historical versions

**L3 Price Selection:**
1. If `country_group_ids` set, only applies to partners in those countries
2. `item_ids` matched in priority order (lowest `sequence` first)
3. First matching rule wins

### product.pricelist.item

**Key Fields:**
- `pricelist_id`, `name`
- `applied_on` — `0_global`, `1_product`, `2_product_category`, `3_bugs` (variants)
- `product_tmpl_id`, `product_id`, `categ_id` — Scope
- `min_quantity` — Minimum qty for rule to apply
- `base` — Base price: `list_price`, `standard_cost`, `pricelist`, `public_category`
- `price` — Fixed price (when `compute_price='fixed'`)
- `percent_price` — Discount percentage (when `compute_price='percentage'`)
- `price_max_discount` — Max allowed discount
- `date_start`, `date_end` — Validity period
- `compute_price` — `fixed`, `percentage`, `formula`
- `base_pricelist_id` — Parent pricelist for formula base
- **Formula variables:** `p`=list_price, `dp`=discounted_price, `ps`=sale_price, `pc`=cost, `pa`=alternative_cost, `u`=factor
- `price_discount` — Additional discount on top of base
- `price_surcharge` — Fixed surcharge
- `discount_restriction` — Can't be combined with other discounts?

**L3 Price Computation Formula:**
```python
price = p * u + price_surcharge  # u is markup/factor
# For percentage:
price = p * (1 - percent_price/100) * u + surcharge
```

### product.attribute

**Key Fields:**
- `name`, `display_type` — `radio`, `select`, `multi`, `color`
- `create_variant` — `always` (create upfront), `dynamic` (on first order), `no_variants` (never)
- `value_ids` — Available values

### product.attribute.value

**Key Fields:**
- `name`, `sequence`
- `attribute_id`
- `html_color` — Hex color for `display_type='color'`
- `is_custom` — Allows free-text custom value?

### product.template.attribute.line

Links attribute to template, defines which values apply.

### product.template.attribute.value

Links a specific value to a template for a specific line.

**Key Fields:**
- `product_tmpl_id`, `attribute_id`, `attribute_line_id`
- `product_attribute_value_id`
- `price_extra` — Additional price for this value
- `html_color`

### product.combo (Odoo 18 new)

Combo/bundle products — sell multiple products as a package.
- `combo_item_ids` — Items in the combo
- `combo_price` — Total combo price
- `combo_ids` — Other combos containing this product

## Product Pricing (product_product_pricing)

`product.product.pricing` / `product.pricing` — Tiered pricing:
- `product_ids` (m2o to `product.product`) or `product_tmpl_id`
- `min_quantity`, `price`
- `applied_on` — `1_product`, `2_product_category`, `0_product`

## Integrations

- **Sale/Purchase**: Vendor info from `product.supplierinfo` (seller_ids)
- **Stock**: `tracking` field controls lot/serial management
- **MRP**: `type='service'` triggers `service_tracking` behavior
- **Account**: `property_account_income/expense_categ_id` for default posting

## Code

- Models: `~/odoo/odoo18/odoo/addons/product/models/`
