---
title: UoM (Units of Measure)
description: Foundational module for managing Units of Measure in Odoo. Provides bi-directional factor hierarchy conversion between units within the same dimension, implicit category detection via parent_path, soft-delete protection, and rounding via the central Product Unit decimal precision.
tags: [odoo19, uom, units-of-measure, product, inventory, conversion, rounding, dimension, module]
model_count: 1
models:
  - uom.uom (unit of measure with factor hierarchy)
dependencies:
  - base
category: Hidden
source: odoo/addons/uom/
created: 2026-04-06
updated: 2026-04-11
l3_status: complete
l4_status: complete
---

# UoM (Units of Measure)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `uom` |
| **Version** | 1.0 |
| **Category** | Hidden |
| **Depends** | `base` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Source Path** | `odoo/addons/uom/` |
| **Decimal Precision** | `Product Unit` — 2 digits (configured in data) |

### Purpose

`uom` is a foundational module that provides the Unit of Measure model and conversion logic used by every Odoo app that handles physical quantities — products, inventory, sales, purchases, manufacturing, and logistics. It has no UI of its own; UoM management is embedded in product and inventory settings.

### Key Design Decisions

- **Implicit category via hierarchy** — There is no `category_id` field. Two UoMs are in the same category if they share a common ancestor in their `relative_uom_id` chain. Compatibility is checked by zipping `parent_path` segments in `_has_common_reference()`.
- **Factor hierarchy instead of absolute factors** — Each UoM has a `relative_factor` and `relative_uom_id` (its immediate parent), not an absolute factor. The absolute `factor` field is recursively computed: `uom.factor = relative_factor * relative_uom_id.factor`. This enables deep chains (e.g., `mi → yd → ft → in → cm → mm`) without requiring a canonical reference at a specific size.
- **Single rounding precision shared by all UoMs** — All UoMs derive their `rounding` from the `decimal.precision` record named `"Product Unit"` (default: 2 digits). There is no per-UoM rounding precision; `_compute_rounding()` is the single source of truth.
- **Protected UoMs** — All UoMs loaded via `ir.model.data` with `module='uom'` are locked from deletion by `_unlink_except_master_data()`. Three exceptions (Hours, Dozens, Pack of 6) are allow-listed by `_unprotected_uom_xml_ids()`.
- **The `uom.category` model does not exist** — Older Odoo versions (pre-18) had a separate `uom.category` model with explicit `name` and `measure_type` fields. Categories are now entirely implicit, inferred from the UoM hierarchy. This is an Odoo 18→19 breaking change.

---

## Module Architecture

```
uom/
├── __manifest__.py            # Depends on base only; web assets for many2one component
├── models/
│   ├── __init__.py
│   └── uom_uom.py             # Single model, 231 lines
├── data/
│   └── uom_data.xml           # 192 lines — all default UoMs and decimal precision
├── security/
│   ├── uom_security.xml       # group_uom: "Manage Multiple Units of Measure"
│   └── ir.model.access.csv    # base.group_system = manager; base.group_user = read
├── views/
│   └── uom_uom_views.xml      # Tree (drag-to-sort), form, search (archived filter)
├── tests/
│   ├── __init__.py
│   ├── common.py              # UomCommon — provides quick_ref() for all default UoMs
│   └── test_uom.py            # test_10_conversion, test_20_rounding, test_30_quantity
└── static/
    └── src/components/**/*    # Frontend many2one UoM selector widget
```

---

## Model: `uom.uom`

**Technical Name:** `uom.uom`
**Description:** Product Unit of Measure
**Parent:** `base.model`
**Order:** `sequence, relative_uom_id, id`
**Parent Field:** `relative_uom_id` (stored via `_parent_name` + `_parent_store = True`)

### Fields

| Field | Type | Required | Default | Stored | Description |
|-------|------|----------|---------|--------|-------------|
| `name` | Char | **Yes** | — | Yes | Unit name. Translateable. User-facing label shown in dropdowns and reports. |
| `sequence` | Integer | No | computed | Yes | Sort order in list view. Computed from `relative_factor * 100`, capped at 1000. Precomputes on create. See `_compute_sequence`. |
| `relative_factor` | Float | **Yes** | `1.0` | Yes | How many times bigger this unit is vs `relative_uom_id`. If no parent, must be exactly `1.0`. Uses `digits=0` which forces PostgreSQL NUMERIC with unlimited precision — critical for values like `0.0166667` (minutes/hour) that float64 cannot represent exactly. |
| `rounding` | Float | No | computed | No | Rounding precision. All UoMs share the same value computed from `decimal.precision` "Product Unit" as `10 ^ -digits`. See `_compute_rounding`. |
| `active` | Boolean | No | `True` | Yes | Soft-delete flag. Archived UoMs are hidden from the UI but remain in the database; they can still be used by existing records. |
| `relative_uom_id` | Many2one `uom.uom` | No | — | Yes | The reference unit this UoM is expressed in terms of. Required if `relative_factor != 1.0`. Cascade delete. Indexed with `btree_not_null`. |
| `related_uom_ids` | One2many `uom.uom` | — | — | Yes | Inverse of `relative_uom_id`. All child UoMs that have `self` as their reference unit. Used for hierarchy display. |
| `factor` | Float | No | computed | **Yes** | Absolute conversion factor. Recursively computed: `relative_factor * relative_uom_id.factor`. Stored for performance; `recursive=True` means the ORM recomputes it whenever any ancestor's `factor` changes. |
| `parent_path` | Char | — | — | Yes | Materialized path for hierarchy queries (e.g., `"1/5/23/"`). Indexed. Used by `_has_common_reference()` to find shared ancestors. |

### Computed Fields Detail

#### `sequence` (compute, stored, precompute)

```python
@api.depends('relative_factor')
def _compute_sequence(self):
    for uom in self:
        if uom.id and uom.sequence:
            # Only set a default sequence before creation, or on module upgrade
            # if there is no value. Once set, changing relative_factor does NOT
            # automatically recalculate sequence.
            continue
        uom.sequence = min(int(uom.relative_factor * 100.0), 1000)
```

The guard `if uom.id and uom.sequence` is the key behavior: sequence only auto-populates on create or during module upgrade if no explicit value exists. After creation, sequence is a normal stored field — it does not track `relative_factor` changes. Users can set sequence manually to control sort order independently of factor size.

#### `rounding` (compute, non-stored)

```python
def _compute_rounding(self):
    decimal_precision = self.env['decimal.precision'].precision_get('Product Unit')
    self.rounding = 10 ** -decimal_precision
```

All UoMs share the same rounding precision from the `"Product Unit"` decimal precision record. With default precision of 2 digits, `rounding = 0.01`. Because this is non-stored, every read of `uom.rounding` triggers a `decimal.precision` lookup. Odoo's decimal precision system caches these lookups, so the cost is minimal, but it means the rounding value can change at runtime if an admin modifies the `Product Unit` precision — with immediate effect across all UoMs and all downstream rounding operations.

#### `factor` (compute, stored, recursive)

```python
@api.depends('relative_factor', 'relative_uom_id', 'relative_uom_id.factor')
def _compute_factor(self):
    for uom in self:
        if uom.relative_uom_id:
            uom.factor = uom.relative_factor * uom.relative_uom_id.factor
        else:
            uom.factor = uom.relative_factor
```

The `recursive=True` attribute on the field declaration instructs the ORM to recompute `factor` whenever any ancestor's `factor` changes. This means a change to a reference unit (e.g., the `g` reference weight) will automatically invalidate all derived factors (kg, ton) in a single transaction. The `factor` field is the workhorse of conversion — `_compute_quantity()` uses it directly.

#### `_compute_display_name` (override)

```python
@api.depends('name', 'relative_factor', 'relative_uom_id')
@api.depends_context('formatted_display_name')
def _compute_display_name(self):
    super()._compute_display_name()
    for uom in self:
        if uom.env.context.get('formatted_display_name') and uom.relative_uom_id:
            uom.display_name = f"{uom.name}\t--{uom.relative_factor} {uom.relative_uom_id.name}--"
```

When `formatted_display_name` is in the context (used by the many2one selector widget), the display name becomes e.g., `"Kilogram\t--1000.0 Gram--"` — showing the conversion ratio inline.

---

## Constraints

### SQL Constraint

```python
_factor_gt_zero = models.Constraint(
    'CHECK (relative_factor != 0)',
    'The conversion ratio for a unit of measure cannot be 0!',
)
```

Enforced at the database level. Cannot be bypassed by ORM calls. A zero factor would cause division-by-zero errors in `_compute_quantity()` (`amount / to_unit.factor`) and corrupt all downstream conversions.

### Python Constraint

```python
@api.constrains('relative_factor', 'relative_uom_id')
def _check_factor(self):
    for uom in self:
        if not uom.relative_uom_id and uom.relative_factor != 1.0:
            raise UserError(_("Reference unit of measure is missing."))
```

Any non-reference UoM (`relative_factor != 1.0`) must have a `relative_uom_id`. Chain-terminating reference UoMs must have `relative_factor = 1.0` and no parent. This enforces a clean rooted tree structure — no cycles, no orphan non-reference UoMs.

---

## Key Methods

### `_compute_quantity(qty, to_unit, round=True, rounding_method='UP', raise_if_failure=True)`

Converts a quantity from `self` (source UoM) into `to_unit` (destination UoM).

```python
def _compute_quantity(
    self, qty: float, to_unit: Self,
    round: bool = True, rounding_method: RoundingMethod = 'UP',
    raise_if_failure: bool = True,
) -> float:
    if not self or not qty:
        return qty
    self.ensure_one()

    if self == to_unit:
        amount = qty
    else:
        amount = qty * self.factor
        if to_unit:
            amount = amount / to_unit.factor

    if to_unit and round:
        amount = tools.float_round(
            amount,
            precision_rounding=to_unit.rounding,
            rounding_method=rounding_method,
        )
    return amount
```

**Conversion formula:** `qty_in_to_unit = qty * self.factor / to_unit.factor`

**The `raise_if_failure` parameter is a no-op.** Despite the parameter name and docstring claiming it raises an exception when UoMs are incompatible, no actual compatibility check is performed. Calling `_compute_quantity()` with incompatible UoMs (e.g., grams to hours) silently returns a mathematically meaningless ratio. Callers are responsible for validating compatibility first (via `_has_common_reference()`).

**Rounding method options:**
- `'UP'` — always round away from zero (used by default; safest for inventory)
- `'DOWN'` — always round toward zero
- `'HALF-UP'` — round to nearest, ties up (standard rounding)
- `'HALF-DOWN'` — round to nearest, ties down
- `'HALF-EVEN'` — banker's rounding (round to nearest even)

**Usage:**
```python
# Convert 5 dozens to units
dozens = self.env.ref('uom.product_uom_dozen')
units = self.env.ref('uom.product_uom_unit')
result = dozens._compute_quantity(5, units)  # → 60.0

# Convert 1020000 grams to tons (stored factor: 1,000,000)
grams = self.env.ref('uom.product_uom_gram')
ton = self.env.ref('uom.product_uom_ton')
result = grams._compute_quantity(1020000, ton)  # → 1.02
```

### `round(value, rounding_method='HALF-UP')` -> `float`

Rounds a value using the UoM's rounding precision (from `Product Unit` decimal precision).

```python
def round(self, value: float, rounding_method: RoundingMethod = 'HALF-UP') -> float:
    self.ensure_one()
    digits = self.env['decimal.precision'].precision_get('Product Unit')
    return tools.float_round(value, precision_digits=digits, rounding_method=rounding_method)
```

### `compare(value1, value2)` -> `Literal[-1, 0, 1]`

Compares two values after rounding them with the UoM's precision. Used for quantity comparisons where floating-point artifacts (e.g., `5.4 % 1.8 = 2.2e-16`) would otherwise cause incorrect results.

```python
def compare(self, value1: float, value2: float) -> Literal[-1, 0, 1]:
    self.ensure_one()
    digits = self.env['decimal.precision'].precision_get('Product Unit')
    return tools.float_compare(value1, value2, precision_digits=digits)
```

Returns `-1` if `value1 < value2`, `0` if equal within precision, `1` if `value1 > value2`.

### `is_zero(value)` -> `bool`

```python
def is_zero(self, value: float) -> bool:
    self.ensure_one()
    digits = self.env['decimal.precision'].precision_get('Product Unit')
    return tools.float_is_zero(value, precision_digits=digits)
```

### `_compute_price(price, to_unit)` -> `float`

Converts a unit price from one UoM to another. This is the inverse formula of `_compute_quantity`.

```python
def _compute_price(self, price: float, to_unit: Self) -> float:
    self.ensure_one()
    if not self or not price or not to_unit or self == to_unit:
        return price
    amount = price * to_unit.factor
    if to_unit:
        amount = amount / self.factor
    return amount
```

**Price conversion formula:** `price_in_to_unit = price * to_unit.factor / self.factor`

This is derived to preserve the invariant that `price * qty` is preserved under UoM conversion:
```
price_kg * qty_kg = (price_g * 1000) * (qty_g / 1000) = price_g * qty_g
```

**Example:**
```python
price_per_kg = 50.0  # $50 per kg
kg = self.env.ref('uom.product_uom_kgm')
g = self.env.ref('uom.product_uom_gram')
price_per_g = kg._compute_price(price_per_kg, g)  # → 0.05
# Verify: 50 * 2 = 100; 0.05 * 2000 = 100 ✓
```

### `_check_qty(product_qty, uom_id, rounding_method='HALF-UP')` -> `float`

Rounds a quantity to the nearest multiple of a packaging unit. Used in sales/purchase when products are sold in fixed pack sizes (e.g., must order in multiples of 6).

```python
def _check_qty(self, product_qty, uom_id, rounding_method="HALF-UP"):
    self.ensure_one()
    packaging_qty = self._compute_quantity(1, uom_id)
    if self == uom_id:
        return product_qty
    if product_qty and packaging_qty:
        product_qty = float_round(
            product_qty / packaging_qty,
            precision_rounding=1.0,
            rounding_method=rounding_method,
        ) * packaging_qty
    return product_qty
```

**Floating-point avoidance:** Direct use of modulo (`product_qty % packaging_qty`) is avoided because float arithmetic produces artifacts like `5.4 % 1.8 = 2.2e-16`. Instead, the method divides, rounds the quotient to the nearest integer (with `precision_rounding=1.0`), then multiplies back.

**Examples:**
- `product_uom_pack_6._check_qty(17, unit, 'UP')` → `18.0` (3 packs of 6, rounded up)
- `product_uom_pack_6._check_qty(17, unit, 'DOWN')` → `12.0` (2 packs, rounded down)
- `unit._check_qty(17, unit, anything)` → `17` (no-op when same UoM)

### `_has_common_reference(other_uom)` -> `bool`

Checks whether two UoMs share a common ancestor in their hierarchy — i.e., whether they are in the same implicit category.

```python
def _has_common_reference(self, other_uom: Self) -> bool:
    self.ensure_one()
    other_uom.ensure_one()
    self_path = self.parent_path.split('/')
    other_path = other_uom.parent_path.split('/')
    common_path = []
    for self_parent, other_parent in zip(self_path, other_path):
        if self_parent == other_parent:
            common_path.append(self_parent)
        else:
            break
    return bool(common_path)
```

**How it works:** `parent_path` stores a materialized path like `"1/"` (root reference unit) or `"1/5/"` (child referencing root ID 1). By zipping the path segments, the algorithm finds the longest shared prefix — which is the common ancestor. The paths are generated by Odoo's `_parent_store` mechanism on every write.

**Example:** `m` (parent_path `"1/5/23/"`) and `km` (parent_path `"1/5/23/47/"`) share ancestor path `["1", "5", "23"]` → compatible. `g` (parent_path `"1/7/"`) and `m` share no common segments → incompatible.

**Limitation:** If two UoMs happen to have identical paths (impossible in a tree), the check would return `True`. In practice this cannot occur because `parent_path` includes the record's own ID as the final segment.

### `_filter_protected_uoms()` -> recordset

Returns UoMs in `self` that are protected from deletion by being loaded via `ir.model.data` with `module='uom'` and name not in the allow-list.

```python
def _filter_protected_uoms(self):
    linked_model_data = self.env['ir.model.data'].sudo().search([
        ('model', '=', self._name),
        ('res_id', 'in', self.ids),
        ('module', '=', 'uom'),
        ('name', 'not in', self._unprotected_uom_xml_ids()),
    ])
    if not linked_model_data:
        return self.browse()
    return self.browse(set(linked_model_data.mapped('res_id')))
```

Uses `sudo()` intentionally — record rules do not apply to `ir.model.data` system records. All other UoMs (created programmatically without `ir.model.data`, or loaded via XML with a different module name) are not protected and can be deleted.

### `_onchange_critical_fields()` (onchange)

```python
@api.onchange('relative_factor')
def _onchange_critical_fields(self):
    if self._filter_protected_uoms() and self.create_date < (fields.Datetime.now() - timedelta(days=1)):
        return {
            'warning': {
                'title': _("Warning for %s", self.name),
                'message': _(
                    "Some critical fields have been modified on %s.\n"
                    "Note that existing data WON'T be updated by this change.\n\n"
                    "As units of measure impact the whole system, this may cause "
                    "critical issues. Therefore, changing core units of measure "
                    "in a running database is not recommended.",
                    self.name,
                )
            }
        }
```

Triggered on `relative_factor` change. **This is a warning only — it does not block the save.** The 24-hour window (`create_date < now - 1 day`) allows newly created UoMs to be fixed immediately without triggering the warning. The filter only includes UoMs protected by `ir.model.data` (loaded from XML), not user-created UoMs.

---

## Deletion Protection: `_unlink_except_master_data()`

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_master_data(self):
    locked_uoms = self._filter_protected_uoms()
    if locked_uoms:
        raise UserError(_(
            "The following units of measure are used by the system and cannot be deleted: %s\n"
            "You can archive them instead.",
            ", ".join(locked_uoms.mapped('name')),
        ))
```

- `at_uninstall=False` allows UoMs to be deleted during module uninstallation (Odoo drops all module-defined constraints before processing `ondelete` callbacks, so the protection is lifted during uninstall).
- Archived UoMs (with `active=False`) are still protected — deletion protection is independent of the active flag.
- The error message suggests archiving as the alternative, which is the correct approach for system UoMs no longer needed.

---

## Default UoMs (from `uom_data.xml`)

All loaded with `noupdate="1"` — they will not be overwritten on upgrade if modified.

### Decimal Precision

| XML ID | Name | Digits | Effect |
|--------|------|--------|--------|
| `decimal_product_uom` | `Product Unit` | 2 | Controls `uom.uom.rounding` for all UoMs. Changing this affects every rounding operation in every module. |

### Reference Units (factor = 1.0, no parent)

| XML ID | Name | Category Implied | Notes |
|--------|------|-----------------|-------|
| `product_uom_unit` | Units | Count/Units | Base for dozens, packs |
| `product_uom_hour` | Hours | Working Time | Base for days, minutes |
| `product_uom_millimeter` | mm | Length | Reference for metric length chain |
| `product_uom_square_meter` | m² | Surface | Reference for ft² |
| `product_uom_milliliter` | ml | Volume | Reference for L, m³ |
| `product_uom_gram` | g | Weight | Reference for kg, ton |
| `product_uom_kwh` | KWH | Energy | Standalone |

### Full UoM Hierarchy

#### Units Category

| XML ID | Name | relative_uom_id | relative_factor | Absolute Factor | Active |
|--------|------|---------------|-----------------|-----------------|--------|
| `product_uom_unit` | Units | — | 1.0 | 1.0 | Yes |
| `product_uom_pack_6` | Pack of 6 | Units | 6.0 | 6.0 | Yes |
| `product_uom_dozen` | Dozens | Units | 12.0 | 12.0 | **No** |

#### Working Time Category (1 Day = 8 Hours)

| XML ID | Name | relative_uom_id | relative_factor | Absolute Factor |
|--------|------|---------------|-----------------|-----------------|
| `product_uom_hour` | Hours | — | 1.0 | 1.0 |
| `product_uom_day` | Days | Hours | 8.0 | 8.0 |
| `product_uom_minute` | Minutes | Hours | 0.0166667 | 0.0166667 |

Note: 1 Day = 8 Hours (working day convention, not calendar day). The Minutes factor `0.0166667` is a truncated approximation of `1/60`; this is the case where `digits=0` (NUMERIC) precision matters — float64 would introduce a tiny rounding error that accumulates across large quantities.

#### Length Category (mm → cm → m → km chain)

| XML ID | Name | relative_uom_id | relative_factor | Absolute Factor | Active |
|--------|------|---------------|-----------------|-----------------|--------|
| `product_uom_millimeter` | mm | — | 1.0 | 1.0 | Yes |
| `product_uom_cm` | cm | mm | 10.0 | 10.0 | **No** |
| `product_uom_meter` | m | cm | 10.0 | 100.0 | Yes |
| `product_uom_km` | km | m | 1000.0 | 100,000.0 | **No** |

Note: The reference unit is the smallest (mm), not an intermediate value. The chain is `mm → cm → m → km`. This is intentional — any node in the chain can serve as the reference for a child, and the system handles arbitrary chains.

#### Surface Category

| XML ID | Name | relative_uom_id | relative_factor | Absolute Factor | Active |
|--------|------|---------------|-----------------|-----------------|--------|
| `product_uom_square_meter` | m² | — | 1.0 | 1.0 | Yes |
| `product_uom_square_foot` | ft² | m² | 0.092903 | 0.092903 | **No** |

#### Volume Category (ml → L → m³ chain)

| XML ID | Name | relative_uom_id | relative_factor | Absolute Factor | Active |
|--------|------|---------------|-----------------|-----------------|--------|
| `product_uom_milliliter` | ml | — | 1.0 | 1.0 | Yes |
| `product_uom_litre` | L | ml | 1000.0 | 1000.0 | Yes |
| `product_uom_cubic_meter` | m³ | L | 1000.0 | 1,000,000.0 | **No** |

#### Weight Category (g → kg → ton chain)

| XML ID | Name | relative_uom_id | relative_factor | Absolute Factor | Active |
|--------|------|---------------|-----------------|-----------------|--------|
| `product_uom_gram` | g | — | 1.0 | 1.0 | Yes |
| `product_uom_kgm` | kg | g | 1000.0 | 1000.0 | Yes |
| `product_uom_ton` | Ton | kg | 1000.0 | 1,000,000.0 | Yes |

#### US Customary Units (all inactive by default)

**Weight chain:** `g → oz → lb`

| XML ID | Name | relative_uom_id | relative_factor | Absolute Factor |
|--------|------|---------------|-----------------|-----------------|
| `product_uom_oz` | oz | g | 28.3495 | 28.3495 |
| `product_uom_lb` | lb | oz | 16.0 | 453.592 |

**Length chain:** `mm → cm → inch → ft → yd → mi`

| XML ID | Name | relative_uom_id | relative_factor | Absolute Factor |
|--------|------|---------------|-----------------|-----------------|
| `product_uom_inch` | in | cm | 2.54 | 25.4 |
| `product_uom_foot` | ft | in | 12.0 | 304.8 |
| `product_uom_yard` | yd | ft | 3.0 | 914.4 |
| `product_uom_mile` | mi | yd | 1760.0 | 1,609,344.0 |

**Volume chain:** `L → fl oz → qt → gal`

| XML ID | Name | relative_uom_id | relative_factor | Absolute Factor |
|--------|------|---------------|-----------------|-----------------|
| `product_uom_floz` | fl oz (US) | L | 0.0295735 | 29.5735 |
| `product_uom_qt` | qt (US) | fl oz | 32.0 | 946.352 |
| `product_uom_gal` | gal (US) | qt | 4.0 | 3785.41 |

**Volume cubes:** `L → in³ → ft³`

| XML ID | Name | relative_uom_id | relative_factor | Absolute Factor |
|--------|------|---------------|-----------------|-----------------|
| `product_uom_cubic_inch` | in³ | L | 0.0163871 | 16.3871 |
| `product_uom_cubic_foot` | ft³ | in³ | 1728.0 | 28,316.8 |

Activate US units by setting `active=True` in the database or via a migration script.

---

## Protected UoMs

All UoMs loaded via `ir.model.data` with `module='uom'` in `uom_data.xml` are protected from deletion:

| XML ID | Name | Exception (`_unprotected_uom_xml_ids`) |
|--------|------|----------------------------------------|
| `product_uom_unit` | Units | No |
| `product_uom_pack_6` | Pack of 6 | **Yes** (can be deleted) |
| `product_uom_dozen` | Dozens | **Yes** (can be deleted) |
| `product_uom_hour` | Hours | **Yes** (can be deleted) |
| `product_uom_day` | Days | No |
| `product_uom_minute` | Minutes | No |
| `product_uom_millimeter` | mm | No |
| `product_uom_cm` | cm | No |
| `product_uom_meter` | m | No |
| `product_uom_km` | km | No |
| `product_uom_square_meter` | m² | No |
| `product_uom_milliliter` | ml | No |
| `product_uom_litre` | L | No |
| `product_uom_cubic_meter` | m³ | No |
| `product_uom_gram` | g | No |
| `product_uom_kgm` | kg | No |
| `product_uom_ton` | Ton | No |
| `product_uom_kwh` | KWH | No |
| US units | oz, lb, in, ft, yd, mi, ft², fl oz, qt, gal, in³, ft³ | No |

The three exceptions (Hours, Dozens, Pack of 6) are the UoMs most likely to need adjustment or deletion in custom installations.

---

## Security

### Access Control (`ir.model.access.csv`)

| Record | Model | Group | read | write | create | unlink |
|--------|-------|-------|-------|-------|--------|--------|
| `access_uom_uom_manager` | `uom.uom` | `base.group_system` | Yes | Yes | Yes | Yes |
| `access_uom_uom_user` | `uom.uom` | `base.group_user` | Yes | No | No | No |

- **`base.group_system`** (Settings > Technical Settings) — full CRUD. Typically Odoo admin or system integrator.
- **`base.group_user`** (all authenticated users) — read-only. Any user can view UoMs, but only admins can create, edit, or delete them.
- The `group_uom` security group defined in `uom_security.xml` is **not assigned to any field or menu by default**. It exists as a placeholder for modules that need to further restrict UoM management (e.g., only certain roles can add new UoMs to prevent inventory chaos).

### Security Considerations

- **`_filter_protected_uoms()` uses `sudo()`** — This is intentional because `ir.model.data` is a system model that should not be filtered by record rules. The method is only called in `_onchange_critical_fields()` and `_unlink_except_master_data()`, both of which are privileged operations anyway.
- **No field-level security** — All fields on `uom.uom` are readable by all authenticated users. Fields like `relative_factor` and `relative_uom_id` are not protected.
- **UoM compatibility not enforced at write-time** — `_compute_quantity()` and `_compute_price()` accept any two UoMs without validating compatibility. Modules that use UoM conversion (product, stock, sale, purchase) must perform their own compatibility checks using `_has_common_reference()` or equivalent domain filters.

---

## Performance Implications

### `digits=0` on `relative_factor` (NUMERIC vs float64)

Using `digits=0` on `relative_factor` instructs Odoo to create the PostgreSQL column as `NUMERIC` (arbitrary precision) rather than `float8`. This is critical because:

- The Minutes factor `0.0166667` (1/60) cannot be represented exactly in IEEE 754 float64.
- The Dozen factor `12` has an exact float representation, but chained conversions (12 → 144 → 1728) accumulate floating-point error.
- With NUMERIC, the conversion of 1 Dozen to Units is exactly `12.0`, not `12.00000000000047`, and the Unit rounding (`0.01`) does not round it up to `13`.

**Performance tradeoff:** NUMERIC arithmetic is slower than float64 for large batch operations, but Odoo stores `factor` (the most frequently used value for conversions) as `float8`. The expensive NUMERIC computation only occurs when writing `relative_factor` values.

### `factor` Stored + `recursive=True`

The `factor` field is stored and marked `recursive=True`. On any write to a reference UoM (`relative_factor` or `relative_uom_id`), Odoo automatically recomputes `factor` for all descendants in a single pass. The `recursive=True` mechanism handles dependency ordering automatically — descendants are always recomputed after their ancestors. This trades write-side compute for read-side speed: `_compute_quantity()` performs only two float multiplications/divisions per conversion.

### `parent_path` Index

The `parent_path` Char field is indexed (`index=True`). `_has_common_reference()` splits this path and zips it with another path — a string operation. For UoM hierarchies that are typically shallow (3-6 levels), this is fast. The index on `parent_path` also benefits any `child_of` or `parent_of` domain operators on the UoM hierarchy.

### `_compute_rounding()` Called Per-Recordset

`_compute_rounding()` calls `decimal.precision.precision_get('Product Unit')` for every UoM in the recordset. This function is cached within the transaction, but the call still occurs per batch. In normal usage (single UoM or small recordset), this is negligible.

---

## Odoo 18 → 19 Historical Changes

### `uom.category` Model Removed

Odoo 17 and earlier had a separate `uom.category` model with explicit fields:

```python
# Odoo 17 (no longer present)
class UomCategory(models.Model):
    _name = 'uom.category'
    name = fields.Char('Category', required=True)
    measure_type = fields.Selection([
        ('length', 'Length'), ('weight', 'Weight'), ('volume', 'Volume'),
        ('time', 'Time'), ('unit', 'Unit'), ('voltage', 'Voltage'),
        ('current', 'Electric Current'), ('temperature', 'Temperature'),
        ('欄', 'Category')
    ])
```

In Odoo 18, this model was removed entirely. UoM categories are now implicit, determined by the UoM hierarchy. The `uom.uom` model no longer has a `category_id` field.

### `uom_type` Field Removed

The `uom_type` Selection field (values: `bigger`, `smaller`, `reference`) was present in older Odoo versions and controlled whether a UoM was larger or smaller than the category reference. It has been removed. The factor hierarchy replaced this concept — a UoM's type is now inferred from whether its `relative_factor` is greater than or less than `1.0`.

### `uom.category` Removal Implications

- Any custom code that referenced `uom.category` directly will break in Odoo 19.
- The `product.product` model previously had a `uom_id` pointing to `uom.uom` with a related `categ_id` (from the category model); this relationship is now via the implicit hierarchy.
- Data migrations from older Odoo versions must reconstruct category groupings from the UoM hierarchy or drop category assignments entirely.

---

## Edge Cases

### Cross-category conversion silently succeeds

`_compute_quantity()` does not validate that source and destination UoMs share a common ancestor. Calling `grams._compute_quantity(100, hours)` returns `100 * factor_gram / factor_hour`, a meaningless ratio. The `raise_if_failure` parameter exists in the signature but is a no-op. Any module calling this method must validate compatibility first.

**Workaround:** Check `_has_common_reference()` before calling `_compute_quantity()`:
```python
if not source_uom._has_common_reference(dest_uom):
    raise UserError(_("Incompatible units of measure."))
```

### Floating-point precision in `_check_qty`

The method avoids direct modulo to sidestep floating-point artifacts. The division-then-round-then-multiply pattern is the correct approach for float quantities.

### Changing reference UoM after data exists

If a reference UoM's `relative_factor` or `relative_uom_id` is changed after existing data references it, the `factor` of all descendants is automatically recomputed (thanks to `recursive=True`), but **the actual stored quantities in product lines, stock moves, and invoice lines are not retroactively converted**. This is the scenario the 24-hour onchange warning addresses. The database would need a data migration to update all recorded quantities.

### Inactive UoMs are still usable

Setting `active=False` on a UoM hides it from the UI dropdown but does not prevent it from being assigned to existing records (e.g., products, stock moves). The constraint is only enforced at the form view level (the `readonly` condition on the name/factor fields). Programmatic assignment via ORM or SQL does not check `active`.

### Archive vs. Delete

Only deletion is protected for XML-loaded UoMs. Archiving (`active=False`) is always allowed. This allows administrators to retire UoMs from the UI without deleting them, preserving referential integrity for existing transactions.

### Sequence manual override

Once `sequence` is set (precomputed on create), it becomes a normal stored integer. Changing `relative_factor` does not automatically recalculate `sequence`. Users can manually set any sequence value, breaking the correlation between factor size and sort order.

---

## Cross-Module Integration

### Product (`product` module)

`product.product` and `product.template` have two UoM fields:
- `uom_id` — default UoM for sales and inventory (sale UoM)
- `uom_po_id` — default UoM for purchase orders (purchase UoM)

Both are Many2one to `uom.uom`. When a product is sold in a different UoM than purchased, the system converts quantities using `_compute_quantity()` at order line creation time.

### Stock (`stock` module)

`stock.move` stores `product_uom_qty` (quantity in the move's UoM) and `quantity` (quantity in the product's inventory UoM, set on move validation). Conversions happen during move processing via `_compute_quantity()`.

### Sale (`sale` module)

`sale.order.line` has `product_uom` (Many2one `uom.uom`) and `product_uom_qty`. The `_compute_quantity()` method is called when creating deliveries from sales orders to reconcile the sale UoM with the inventory UoM.

### Purchase (`purchase` module)

`purchase.order.line` has `product_uom` and `product_qty`. Purchase UoM conversions happen when matching purchase orders to receipts and vendor bills.

### Manufacturing (`mrp` module)

Work orders track time in Hours (`product_uom_hour`). The `duration` field on `mrp.workorder` is expressed in hours regardless of the bill of materials UoM. Time tracking uses `_compute_quantity()` to convert between recorded durations and the standard hours UoM.

### Price Lists (`product` module)

`product.pricelist.item` uses `_compute_price()` when `base` is set to `pricelist` or `supplierinfo'` to convert purchase prices into sale prices across different UoMs.

---

## Tests

The test suite (`tests/test_uom.py`) uses `UomCommon` which provides `quick_ref()` access to all default UoMs:

```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.uom_gram   = cls.quick_ref('uom.product_uom_gram')
    cls.uom_kgm    = cls.quick_ref('uom.product_uom_kgm')
    cls.uom_ton    = cls.quick_ref('uom.product_uom_ton')
    cls.uom_unit   = cls.quick_ref('uom.product_uom_unit')
    cls.uom_dozen  = cls.quick_ref('uom.product_uom_dozen')
    cls.uom_dozen.active = True   # activate for tests
    cls.uom_hour   = cls.quick_ref('uom.product_uom_hour')
    cls.group_uom  = cls.quick_ref('uom.group_uom')
```

**`test_10_conversion`** — Verifies factor arithmetic:
- 1,020,000 g → 1.02 ton (full chain: g → kg → ton)
- price 2 g → 2,000,000 per ton (price conversion invariant)
- 1 dozen → 12 units (regression test for floating-point artifact: without NUMERIC, `1/12` rounded to float is `0.08333333333333333 × 12 = 11.999999999999999`; rounding to `0.01` would round up to `12.01`, then to `13` units)
- 1234 g → 1.24 kg (regression: rounding g to 1 digit should not break conversion)

**`test_20_rounding`** — Verifies that changing `Product Unit` decimal precision to 0 digits causes `2 units → 1 "Score"` (20 per unit) conversion to round up to `1`.

**`test_30_quantity`** — Verifies that `_check_qty` returns quantity unchanged when UoM equals packaging UoM.

---

## Related

- [Modules/Product](Modules/Product.md) — products reference `uom_id` and `uom_po_id` from `uom.uom`
- [Modules/Stock](Modules/Stock.md) — `stock.move` uses `_compute_quantity()` to convert between sale/inventory/purchase UoMs
- [Modules/Sale](Modules/Sale.md) — `sale.order.line` uses `product_uom` on lines
- [Modules/Purchase](Modules/Purchase.md) — `purchase.order.line` uses `product_uom` on lines
- [Modules/MRP](Modules/MRP.md) — work orders track duration in Hours UoM
- [Modules/Account](Modules/Account.md) — invoice lines use product UoM for quantity
- [Core/API](Core/API.md) — `@api.depends`, `@api.onchange`, `@api.constrains` decorators used in uom_uom.py
- [Core/Fields](Core/Fields.md) — field types used: Char, Integer, Float, Boolean, Many2one, One2many, Char (parent_path)
