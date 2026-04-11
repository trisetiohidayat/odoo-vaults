# sale_product_matrix — Sale Product Matrix

**Tags:** #odoo #odoo18 #sale #product #matrix #configurator
**Odoo Version:** 18.0
**Module Category:** Sale / Product Configurator
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_product_matrix` enables the "matrix" (grid) product configuration mode for sale orders. When a product template is set to `product_add_mode='matrix'`, the SO form displays an interactive grid (product variant matrix) allowing inline editing of all variant combinations and their quantities. This is an alternative to the classic product configurator wizard.

**Technical Name:** `sale_product_matrix`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_product_matrix/`
**Depends:** `sale`
**Inherits From:** `product.template`, `sale.order`, `sale.order.line`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/product_template.py` | `product.template` | Matrix mode selection |
| `models/sale_order.py` | `sale.order` | Grid loading, cell application |
| `models/sale_order_line.py` | `sale.order.line` | Related product_add_mode |

---

## Models Reference

### `product.template` (models/product_template.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `product_add_mode` | Selection | `'configurator'` (wizard) or `'matrix'` (grid) |

---

### `sale.order` (models/sale_order.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `report_grids` | Boolean | Show grid in reports |
| `grid_product_tmpl_id` | Many2one | Template for current grid |
| `grid_update` | Char | Pending cell updates |
| `grid` | Char | Grid data snapshot |

#### Methods

| Method | Behavior |
|--------|----------|
| `_set_grid_up()` | `@api.onchange('grid_product_tmpl_id')`: loads variant matrix for selected template |
| `_apply_grid()` | `@api.onchange('grid', 'grid_update')`: applies cell changes: creates/finds variant, updates qty, handles zero qty removal |
| `_get_matrix()` | Returns matrix data: headers (attr values), rows (variant records), cell data (qty, price, discount) |

---

### Matrix Workflow

```
User selects product in SO
  → _set_grid_up() onchange loads matrix
    → Grid displayed with attribute columns × variant rows
    → User edits qty cells inline

Grid changes → grid_update string updated
  → _apply_grid() onchange processes:
    → For each cell with qty > 0: find/create variant, update/create SOL with qty
    → For each cell with qty == 0 and existing SOL: unlink SOL
    → For each cell with qty > 0 and no existing SOL: create new SOL
```

---

## v17→v18 Changes

No significant changes from v17 to v18 identified.

---

## Notes

- `product_add_mode` defaults to `'configurator'` for backward compatibility
- Matrix mode only works for product templates with `type='consu'` or `type='product'` and active attributes
- The `grid` field stores a serialized JSON snapshot of the grid state
- `_get_matrix()` returns structured data used by the web controller to render the grid view
