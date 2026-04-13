---
type: module
name: uom
version: Odoo 18
tags: [module, uom, units, measurement, product]
source: ~/odoo/odoo18/odoo/addons/uom/
---

# UoM — Units of Measure

Unit of measure categories and conversion between units.

**Source:** `addons/uom/`
**Depends:** `base`

---

## Models

### `uom.category` — UoM Categories

```python
class UoMCategory(models.Model):
    _name = 'uom.category'
    _description = 'Product UoM Categories'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Category name (required, translate) |
| `uom_ids` | One2many | `uom.uom` lines in this category |
| `reference_uom_id` | Many2one | Reference unit for conversion (not stored) |

**Key Methods:**
- `_onchange_uom_ids()` — Enforce one reference unit per category; update conversion factors

---

### `uom.uom` — Unit of Measure

```python
class UoM(models.Model):
    _name = 'uom.uom'
    _description = 'Product Unit of Measure'
    _order = 'factor DESC, id'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | UoM name (required, translate) |
| `category_id` | Many2one | `uom.category`, required |
| `factor` | Float | Conversion factor (default 1.0), **numeric precision** |
| `factor_inv` | Float | Inverse factor (computed) |
| `rounding` | Float | Rounding precision (default 0.01) |
| `active` | Boolean | Default True |
| `uom_type` | Selection | `bigger` / `reference` / `smaller` |
| `ratio` | Float | Combined ratio (computed, inverse of `_set_ratio`) |
| `color` | Integer | Computed color for reference type |

**_sql_constraints:**
- `factor_gt_zero` — CHECK(factor != 0)
- `rounding_gt_zero` — CHECK(rounding > 0)
- `factor_reference_is_one` — CHECK((uom_type='reference' AND factor=1.0) OR (uom_type!='reference'))

**Key Methods:**
- `_check_category_reference_uniqueness()` — Ensure exactly one reference unit per category
- `_compute_factor_inv()` — Compute inverse factor
- `_compute_ratio()` / `_set_ratio()` — Combined ratio with inverse
- `_compute_color()` — Color coding for reference type
- `_onchange_uom_type()` — Set factor to 1.0 when set as reference
- `_onchange_critical_fields()` — Warning if changed after 24h (may affect stock)
- `_compute_quantity(from_uom, qty, to_uom)` — Convert quantity between UoMs
- `_compute_price(product, qty, to_uom)` — Convert product price to target UoM
- `_filter_protected_uoms()` — Get protected UoM records
- `_unlink_except_master_data()` — Prevent deletion of master data
- `_unprotected_uom_xml_ids()` — Returns: `["product_uom_hour", "product_uom_dozen"]`

---

## Default Data (`uom_data.xml`)

### Categories

| Category | Reference UoM | Type |
|----------|--------------|------|
| Unit | Units | reference |
| Weight | kg | reference |
| Working Time | Days | reference |
| Length/Distance | m | reference |
| Surface | m² | reference |
| Volume | L | reference |

### Units per Category

| Category | Units |
|----------|-------|
| Unit | Units, Dozen |
| Weight | kg, lb (bigger), oz (smaller) |
| Working Time | Days, Hours (smaller) |
| Length | m, km (bigger), cm, mm, mi, ft, in, yd (smaller) |
| Surface | m², km², cm², mm², ft², yd², in² |
| Volume | L, m³, gallon (US), fl oz, qt, pint, c, mm³, cm³ |

---

## Conversion Logic

```
# factor: how many reference units = 1 this UoM
# smaller UoM → factor < 1 (e.g., hour: 0.125 days when reference=days)
# bigger UoM → factor > 1 (e.g., dozen: 12 units when reference=units)

qty_in_reference = qty * factor
qty_in_target = qty_in_reference / target_factor
```

---

## Cross-Module Relations

| Module | Integration |
|--------|-------------|
| `product` | `product.product.uom_id`, `product.product.uom_po_id` |
| `stock` | `stock.move.product_uom`, quantity conversions on moves |
| `sale` | `sale.order.line.product_uom` |
| `purchase` | `purchase.order.line.product_uom` |
| `mrp` | `mrp.bom.line.product_uom_id` |
| `account` | `account.move.line.product_uom_id` |

---

## Odoo 18 vs Odoo 19 Differences

| Feature | Odoo 18 | Odoo 19 |
|---------|---------|---------|
| `uom.category` | Explicit model | **Removed** |
| `factor` field | Direct numeric | `relative_factor` + `relative_uom_id` hierarchy |
| `uom_type` | `reference`/`bigger`/`smaller` | **Removed** |
| Category detection | Via `category_id` | Via `parent_path` |

---

## Related Links
- [Modules/Product](odoo-18/Modules/product.md) — Product with UoM
- [Modules/Stock](odoo-18/Modules/stock.md) — Stock move quantities
- [Modules/Sale](odoo-18/Modules/sale.md) — Sales order line UoM
- [Modules/Purchase](odoo-18/Modules/purchase.md) — Purchase order line UoM
