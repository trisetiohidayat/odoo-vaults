---
tags: [odoo, odoo17, module, product]
---

# Product Module

**Source:** `addons/product/models/`

## Key Models

| Model | _name | File | Description |
|-------|-------|------|-------------|
| `` `product.template` `` | `product.template` | `product_template.py` | Product master record |
| `` `product.product` `` | `product.product` | `product_product.py` | Individual product variants |
| `` `product.category` `` | `product.category` | `product_category.py` | Hierarchical product grouping |

## product.template

The product master record. One template may generate multiple `product.product` variants through attribute lines.

> Inherits from `mail.thread`, `mail.activity.mixin`, `image.mixin`.

### Product Types (`detailed_type`)
| Value | Label | Stock Managed |
|-------|-------|---------------|
| `consu` | Consumable | No |
| `service` | Service | No |

> Note: `stockable` product type (`type = 'product'`) requires the `stock` module to be installed; without it, only `consu` and `service` are available.

### Key Fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Product name (required, translated) |
| `detailed_type` | Selection | consumable / service |
| `categ_id` | Many2one | Product category |
| `list_price` | Float | Sales price |
| `standard_price` | Float | Cost (AVCO valuation; computed/inversible) |
| `seller_ids` | One2many | Vendor list (`product.supplierinfo`) |
| `uom_id` | Many2one | Default unit of measure |
| `uom_po_id` | Many2one | Purchase unit of measure |
| `sale_ok` | Boolean | Can be sold (default True) |
| `purchase_ok` | Boolean | Can be purchased (default True) |
| `company_id` | Many2one | Company (multi-company) |
| `attribute_line_ids` | One2many | Attribute lines for variant generation |
| `product_variant_ids` | One2many | `product.product` variants |

### Descriptions
| Field | Description |
|-------|-------------|
| `description` | Internal notes (HTML) |
| `description_sale` | Sales description (copied to SO, DO, invoice) |
| `description_purchase` | Purchase description |

## product.product

Individual product variants. Created automatically from `product.template` + `product.template.attribute.line`.

> Uses `_inherits = {'product.template': 'product_tmpl_id'}` — stores variant-specific fields (`standard_price`, `volume`, `weight`, `barcode`) on `product.product` itself; inherited fields (name, list_price, etc.) are delegated to the parent template.

### Key Fields
| Field | Type | Description |
|-------|------|-------------|
| `product_tmpl_id` | Many2one | Parent template (cascade delete) |
| `default_code` | Char | Internal reference / SKU |
| `barcode` | Char | EAN/UPC barcode |
| `standard_price` | Float | Variant cost (company-dependent) |
| `volume` / `weight` | Float | Physical dimensions |
| `lst_price` | Float | Catalog sales price (template + variant extra) |
| `price_extra` | Float | Sum of variant attribute extra prices |

## product.category

Hierarchical product categories. Used for default accounting properties, group-based pricing, and stock valuation settings.

### Fields
| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Category name (required) |
| `parent_id` | Many2one | Parent category (cascade delete) |
| `child_id` | One2many | Child categories |
| `complete_name` | Char | Full path e.g. `All / Electronics / Phones` |
| `parent_path` | Char | Materialized path for efficient hierarchy queries |
| `product_count` | Integer | Products directly in this category |
| `product_properties_definition` | Properties | Dynamic properties definition |

### Constraints
- Recursive categories are forbidden (`_check_category_recursion`)
- `product.product_category_all` (All) cannot be deleted
- `product.cat_expense` and `product.product_category_1` (Saleable) also protected

## See Also
- [Modules/sale](sale.md) — Product in sale orders
- [Modules/purchase](purchase.md) — Product in purchase orders
- [Modules/stock](stock.md) — Product quantities and valuation
