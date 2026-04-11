# purchase_product_matrix — Purchase Product Matrix

**Tags:** #odoo #odoo18 #purchase #product-matrix #variant-grid #configurable-product
**Odoo Version:** 18.0
**Module Category:** Purchase + Product Configuration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`purchase_product_matrix` adds the product matrix (variant grid) feature to purchase orders, mirroring the same matrix UI from `sale_product_matrix` and `product_matrix`. It allows buyers to configure configurable products (with product variants) directly from the PO using an interactive grid — creating all variant lines at once rather than one-by-one.

**Technical Name:** `purchase_product_matrix`
**Python Path:** `~/odoo/odoo18/odoo/addons/purchase_product_matrix/`
**Depends:** `purchase`, `product_matrix`
**Inherits From:** `purchase.order`, `purchase.order.line`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/purchase.py` | `purchase.order` | Matrix fields, grid loading, grid apply, matrix report |
| `models/purchase_order_line.py` | `purchase.order.line` | Template/variant attribute fields, description override |

---

## Models Reference

### `purchase.order` (models/purchase.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `report_grids` | Boolean | If True, print variant grids on PO report |
| `grid_product_tmpl_id` | Many2one (`product.template`) | Technical: the template whose matrix is open |
| `grid_update` | Boolean | Technical: whether the grid contains new data to apply |
| `grid` | Char | Technical: JSON-encoded grid data |

#### Methods

| Method | Line | Behavior |
|--------|------|----------|
| `_set_grid_up()` | 27 | Onchange on `grid_product_tmpl_id`: loads the matrix from `_get_matrix()` into `grid` as JSON |
| `_must_delete_date_planned()` | 33 | Extends parent: also returns True for field `grid` (cleared when matrix opens) |
| `_apply_grid()` | 36 | Onchange on `grid`: parses changes, creates/updates variant PO lines from dirty cells. Validates no multi-line conflict |
| `_get_matrix()` | 121 | Builds the variant matrix for a `product.template`: uses `_get_template_matrix()` from `product_matrix`, then overlays existing PO line quantities |
| `get_report_matrixes()` | 144 | Returns matrix data for PO report printing (only if `report_grids` is True and template has multiple lines) |

#### Grid Apply Logic (`_apply_grid()`)

The core matrix logic processes each modified cell:
1. Parses `ptav_ids` (attribute value IDs) from the cell
2. Creates/finds the product variant via `_create_product_variant()`
3. Filters existing PO lines by product + no-variant attribute values
4. Computes the qty difference (new qty - old qty)
5. If `diff == 0`: skips
6. If existing line found: updates qty (or zeroes out if qty=0 and PO is draft/sent)
7. If no existing line: creates a new PO line with `product_id`, `product_qty`, `product_no_variant_attribute_value_ids`
8. Runs `_product_id_change()` on modified lines to recompute price/discount

**Validation:** Raises `ValidationError` if a variant appears in multiple PO lines (matrix requires one line per variant).

---

### `purchase.order.line` (models/purchase_order_line.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `product_template_id` | Many2one (`product.template`) | Related: `product_id.product_tmpl_id`, domain `purchase_ok=True` |
| `is_configurable_product` | Boolean | Related: `product_template_id.has_configurable_attributes` |
| `product_template_attribute_value_ids` | Many2many | Related from `product_id` (readonly) |
| `product_no_variant_attribute_value_ids` | Many2many | Attribute values that don't create variants (editable) |

#### Methods

| Method | Line | Behavior |
|--------|------|----------|
| `_get_product_purchase_description()` | 171 | Extends parent: appends each `product_no_variant_attribute_value` as a new line to the product description (e.g., "Color: Blue") |

---

## Security File

No security file.

---

## Data Files

None.

---

## Critical Behaviors

1. **Matrix as JSON**: Unlike the JS-side matrix in `sale_product_matrix`, `purchase_product_matrix` is fully server-side. The matrix is rendered as a Char field and processed via `_apply_grid()` on the server. This bypasses JS framework limitations (only first 40 lines loaded) for large matrices.

2. **No-Variant Attributes**: `product_no_variant_attribute_value_ids` tracks attribute values that don't generate variants (e.g., "engraving text"). These are stored on the PO line directly rather than generating new product variants.

3. **Multi-Line Conflict Detection**: `_apply_grid()` raises a validation error if a product variant already exists on more than one PO line — the matrix requires exactly one line per variant.

4. **Price Recomputation**: After creating/updating lines, `_product_id_change()` is called to recompute price, discount, and taxes based on the vendor's product configuration.

5. **Report Matrix**: `get_report_matrixes()` is used by PO report templates to print the variant grid on paper — useful for supplier RFQs with configurable products.

---

## v17→v18 Changes

- No significant structural changes from v17 to v18
- `_must_delete_date_planned()` override added to properly clear the grid field
- `_get_product_purchase_description()` enhanced to display no-variant attribute values

---

## Notes

- `purchase_product_matrix` mirrors the same architecture as `sale_product_matrix` but for the purchasing context
- The server-side matrix approach (JSON char field) is more scalable than client-side for large variant grids (100+ combinations)
- `product_no_variant_attribute_value_ids` enables configuring products where some attribute values (e.g., custom text) don't create new variants but still need to be recorded
- The `report_grids` Boolean on `purchase.order` allows buyers to optionally include the matrix on printed RFQs
