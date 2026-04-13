# Product — Products & Pricelists

Dokumentasi Odoo 15 untuk Product module. Source: `addons/product/models/`

## Models

| Model | File | Description |
|---|---|---|
| `product.template` | `product_template.py` | Product Template |
| `product.product` | `product.py` | Product Variant |
| `product.category` | `product_category.py` | Product Category |
| `product.pricelist` | `product_pricelist.py` | Pricelist |
| `product.pricelist.item` | `product_pricelist.py` | Pricelist Item |
| `product.attribute` | `product_attribute.py` | Attribute |
| `product.attribute.value` | `product_attribute.py` | Attribute Value |
| `product.template.attribute.line` | `product_attribute.py` | Attribute Line |
| `product.template.attribute.value` | `product_attribute.py` | Attribute Value (ptav) |
| `uom.uom` | `uom_uom.py` | Unit of Measure |
| `uom.category` | `uom_uom.py` | UoM Category |

## ProductTemplate

```python
class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin', 'product.archive.mixin']
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Product Name |
| `type` | Selection | consumable/service (computed from detailed_type) |
| `detailed_type` | Selection | product/consumable/service |
| `categ_id` | Many2one(product.category) | Category |
| `default_code` | Char | Internal Reference (SKU) |
| `code` | Char | Reference |
| `barcode` | Char | Barcode |

### Pricing Fields

| Field | Type | Description |
|---|---|---|
| `list_price` | Float | Sales Price |
| `standard_price` | Float | Cost |
| `lst_price` | Float | Sales Price (same as list_price) |
| `property_account_income_id` | Many2one | Revenue account |
| `property_account_expense_id` | Many2one | Expense account |

### Unit & Quantity

| Field | Type | Description |
|---|---|---|
| `uom_id` | Many2one(uom.uom) | Unit of Measure (sales) |
| `uom_po_id` | Many2one(uom.uom) | Purchase Unit |
| `uos_id` | Many2one(uom.uom) | Secondary unit |
| `uos_coeff` | Float | UoS → UoM coefficient |

### Variants

| Field | Type | Description |
|---|---|---|
| `product_variant_ids` | One2many(product.product) | Variants |
| `product_variant_id` | Many2one(product.product) | One variant (if only 1) |
| `attribute_line_ids` | One2many(product.template.attribute.line) | Attributes |
| `is_product_variant` | Boolean | Is variant (for search) |

### Routes & Controls

| Field | Type | Description |
|---|---|---|
| `sale_ok` | Boolean | Can be sold |
| `purchase_ok` | Boolean | Can be purchased |
| `active` | Boolean | Active |
| `company_id` | Many2one(res.company) | Company |
| `route_ids` | Many2many(stock.route) | Routes |
| `categ_id` | Many2one(product.category) | Category |

### Inventory Fields

| Field | Type | Description |
|---|---|---|
| `type` | Selection | product/consumable/service (computed) |
| `seller_ids` | One2many(product.supplierinfo) | Vendor Pricelist |
| `seller_delay` | Integer | Delivery lead time |

### Weights & Dimensions

| Field | Type | Description |
|---|---|---|
| `volume` | Float | Volume (m³) |
| `weight` | Float | Weight (kg) |
| `weight_uom_id` | Many2one(uom.uom) | Weight unit |
| `volume_uom_id` | Many2one(uom.uom) | Volume unit |

## ProductProduct (Variant)

```python
class ProductProduct(models.Model):
    _name = "product.product"
    _description = "Product"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Product Name (computed from template) |
| `default_code` | Char | Internal Reference |
| `barcode` | Char | Barcode |
| `product_tmpl_id` | Many2one(product.template) | Parent template |
| `active` | Boolean | Active |

### Combination Fields

| Field | Type | Description |
|---|---|---|
| `product_template_attribute_value_ids` | Many2many(product.template.attribute.value) | Attribute combination |
| `combination_indices` | Char | Index for combination |

### Pricing

| Field | Type | Description |
|---|---|---|
| `list_price` | Float | Sales price (from template) |
| `standard_price` | Float | Cost (from template) |

## ProductCategory

```python
class ProductCategory(models.Model):
    _name = "product.category"
    _description = "Product Category"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Category name |
| `parent_id` | Many2one(product.category) | Parent category |
| `complete_name` | Char | Full path name |
| `property_account_income_categ_id` | Many2one | Income account |
| `property_account_expense_categ_id` | Many2one | Expense account |
| `sequence` | Integer | Sequence |

**Hierarchical structure** (parent_id → tree of categories).

## ProductPricelist

```python
class Pricelist(models.Model):
    _name = "product.pricelist"
    _description = "Pricelist"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Pricelist name |
| `active` | Boolean | Active |
| `company_id` | Many2one(res.company) | Company |
| `currency_id` | Many2one(res.currency) | Currency |
| `item_ids` | One2many(product.pricelist.item) | Pricelist items |

### Pricelist Item

```python
class PricelistItem(models.Model):
    _name = "product.pricelist.item"
    _description = "Pricelist Item"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `pricelist_id` | Many2one(product.pricelist) | Parent pricelist |
| `name` | Char | Rule name |
| `active` | Boolean | Active |
| `base` | Selection | List price/base_pricelist/public_price |
| `base_pricelist_id` | Many2one(product.pricelist) | Base pricelist |
| `categ_id` | Many2one(product.category) | Category filter |
| `product_tmpl_id` | Many2one(product.template) | Product template |
| `product_id` | Many2one(product.product) | Product variant |
| `min_quantity` | Float | Minimum quantity |
| `fixed_price` | Float | Fixed price |
| `percent_price` | Float | Discount % |
    - `price_discount` | Float | Discount %
    - `price_round` | Float | Rounding
    - `price_surcharge` | Float | Surcharge
    - `date_start` | Date | Start date
    - `date_end` | Date | End date

### Computation Method

| Field | Type | Description |
|---|---|---|
| `compute_price` | Selection | fixed/percentage/formula |
| `applied_on` | Selection | 3_global/2_product_category/1_product |

## Unit of Measure (uom.uom)

```python
class UomUom(models.Model):
    _name = "uom.uom"
    _description = "Unit of Measure"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | UoM name |
| `category_id` | Many2one(uom.category) | Category |
| `factor` | Float | Factor to reference UoM |
| `factor_inv` | Float | Inverse factor |
| `rounding` | Float | Rounding precision |
| `uom_type` | Selection | bigger/reference/smaller |

### UoM Categories

- **Reference UoM** in each category (factor=1)
- **Bigger** than reference (factor < 1)
- **Smaller** than reference (factor > 1)

## ProductSupplierinfo (Vendor Pricelist)

```python
class ProductSupplierinfo(models.Model):
    _name = "product.supplierinfo"
    _description = "Vendor Pricelist"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Many2one(res.partner) | Vendor |
| `product_name` | Char | Vendor product name |
| `product_code` | Char | Vendor product code |
| `sequence` | Integer | Priority |
| `product_tmpl_id` | Many2one(product.template) | Product template |
| `product_id` | Many2one(product.product) | Product variant |
| `min_qty` | Float | Minimum quantity |
| `price` | Float | Vendor price |
    - `delay` | Integer | Delivery lead time (days)

## See Also
- [Modules/Sale](odoo-18/Modules/sale.md) — Sales price from product
- [Modules/Purchase](odoo-18/Modules/purchase.md) — Vendor price
- [Modules/Stock](odoo-18/Modules/stock.md) — Inventory management
- [Modules/MRP](odoo-18/Modules/mrp.md) — BoM production