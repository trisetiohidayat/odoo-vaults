# MRP Bill of Materials (BoM) - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/mrp/models/mrp_bom.py`
**Lines:** ~844

---

## Model Overview

`mrp.bom` (internal name `mrp.bom`) is the Bill of Materials model. It defines the components (lines), byproducts, and operations required to manufacture a product. Supports multi-level phantom BoMs, variant-specific BoMs, and operation routing.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | BoM name |
| `active` | Boolean | Archive/unarchive |
| `type` | Selection | `'normal'` (manufacture), `'phantom'` (kit), `'subassembly'` (subcontract) |
| `product_tmpl_id` | Many2one | `product.template`; product template this BoM is for |
| `product_id` | Many2one | `product.product`; specific variant. Mutually exclusive with `product_tmpl_id` |
| `product_qty` | Float | Quantity produced per BoM cycle |
| `product_uom_id` | Many2one | `uom.uom`; unit of measure |
| `bom_line_ids` | One2many | `mrp.bom.line`; component lines |
| `byproduct_ids` | One2many | `mrp.bom.byproduct`; coproducts |
| `operation_ids` | One2many | `mrp.routing.workcenter`; routing operations |
| `ready_to_produce` | Selection | `'all_available'` (consume when all available), `'asap'` (as soon as possible) |
| `consumption` | Selection | `'flexible'` (allow deviation), `'warning'` (warn on deviation), `'strict'` (block deviation) |
| `allow_operation_dependencies` | Boolean | Enable blocking dependencies between operations |
| `sequence` | Integer | Priority for BoM selection when multiple exist |
| `company_id` | Many2one | `res.company` |
| `picking_type_id` | Many2one | `stock.picking.type`; for component delivery |
| `produce_delay` | Float | Lead time in days |

### BoM Line (`mrp.bom.line`)
| Field | Type | Notes |
|---|---|---|
| `product_id` | Many2one | `product.product`; component |
| `product_qty` | Float | Quantity of component per BoM cycle |
| `product_uom_id` | Many2one | `uom.uom`; unit |
| `bom_id` | Many2one | Parent BoM |
| `operation_id` | Many2one | `mrp.routing.workcenter`; operation consuming this component |
| `child_bom_id` | Many2one | `mrp.bom`; computed sub-BoM for phantom kits |
| `manual_consumption` | Boolean | Force manual quantity entry (override flexible consumption) |
| `bom_product_template_attribute_value_ids` | Many2many | Variant-specific configuration |
| `sequence` | Integer | Sort order |

### Byproduct (`mrp.bom.byproduct`)
| Field | Type | Notes |
|---|---|---|
| `product_id` | Many2one | `product.product`; byproduct |
| `product_qty` | Float | Quantity produced per cycle |
| `product_uom_id` | Many2one | `uom.uom` |
| `bom_id` | Many2one | Parent BoM |
| `operation_id` | Many2one | `mrp.routing.workcenter`; operation producing this |
| `cost_share` | Float | Percentage of cost allocation (must sum to <= 100% across all byproducts) |

---

## Key Methods

### `_check_bom_cycle(cycle)`
**Purpose:** Recursive cycle detection in BoM hierarchy.
**Logic:** DFS traversal of `child_bom_id` links. Raises `ValidationError` if the current BoM is encountered during traversal.
**Called by:** `write()` and `create()` via `@api.constrains('bom_line_ids')`.
**Performance note:** Full recursive traversal on every write. Can be slow for deep BoM hierarchies.

### `explode(product, quantity, picking_type=False)`
**Purpose:** Explode a BoM into flat stock moves.
**Logic:**
1. For each `bom_line`:
   a. If component has a sub-BoM (`product_id.bom_ids`):
      - If sub-BoM is `phantom`: recursively explode it (phantom sub-assemblies are dissolved into their components).
      - If sub-BoM is `normal`/`subassembly`: include the sub-BoM as a `child_bom_id` move (produces the sub-assembly as a semi-finished good).
   b. If component has no sub-BoM: add as a raw material move.
2. If `picking_type` is provided, creates a `stock.picking` for components.
3. **Phantom BoM:** Fully dissolved. The phantom's components replace the phantom in the final move list. If a phantom has another phantom, recursion continues until non-phantom components are reached.

**Edge cases:**
- Phantom BoM inside a phantom: nested phantoms are recursively dissolved.
- Multi-level BoM: A normal BoM with a sub-assembly component retains the sub-assembly as a separate move (not dissolved).
- Component with multiple BoMs: Uses `_select_best_bom()` to pick the most appropriate (variant-specific > template-level).
- If no BoM found for a component and the component has no BoM: added as raw material.

### `_select_best_bom()`
Selects the best matching BoM for a product.
**Priority:**
1. BoM with matching product variant (`product_id` set)
2. BoM with matching template (`product_tmpl_id` set)
3. Among equal priorities, lowest `sequence`

**Returns:** `False` if no BoM exists for the product.

### `_get_bom_product_quantity(product, quantity, picking_type=False, branch)`
Recursive helper for `explode()`.

### `action_duplicateBom()`
**Returns:** Action to open the BoM duplication wizard (`mrp.bom.change_product_qty`).

### `_check_cost_share()`
**Constraint:** Sum of all `cost_share` values in `byproduct_ids` must be <= 100%.
**Applies to:** `mrp.bom.byproduct`

### `_check_bom_products()`
**Constraint:** A BoM's own product cannot be used as a component (prevents infinite recursion through non-phantom BoMs).

---

## BoM Type Semantics

| Type | Behavior |
|---|---|
| `normal` | Standard manufacturing. Components consumed, finished product produced. Sub-assemblies created as separate semi-finished goods. |
| `phantom` | Kit/kit. Fully dissolved into components when parent is exploded. The phantom product itself is never produced as a stockable item. |
| `subassembly` | Similar to normal but used for subcontracting scenarios. May have special picking type routing. |

---

## Cross-Model Relationships

### With `product.product`
- `product_id` / `product_tmpl_id`: The product being manufactured.
- Component lines reference component products.

### With `mrp.routing.workcenter`
- `operation_ids`: Routing operations (work sequence) for the BoM.
- Operations define workcenters, cycle times, and blocking dependencies.

### With `mrp.production`
- `bom_id` on MO references the BoM.
- MO's `move_raw_ids` and `workorder_ids` are generated from BoM.

---

## Edge Cases & Failure Modes

1. **Multiple BoMs for same product:** `_select_best_bom()` picks the lowest sequence variant BoM. If two variants have the same sequence, the one with `product_id` set (specific variant) is chosen over template-level.
2. **Phantom BoM referencing itself:** `_check_bom_cycle()` prevents this via recursive DFS. But the check only runs on `bom_line_ids` write, not on `bom_line_ids` creation via the constraint. On create, the constraint should fire; on write, it fires.
3. **BoM with no components:** Valid (produces product from nothing). Could be used for service/subcontract items.
4. **Variant-specific BoM and `product_id`:** When a BoM has `product_id` set (variant-specific), it coexists with template-level BoMs. The `_select_best_bom()` will prefer the variant-specific one.
5. **`cost_share` validation:** The constraint `_check_cost_share` only validates on `mrp.bom.byproduct`. It does not prevent sum of cost_share > 100 in the parent BoM's write method; it relies on the constraint.
6. **`manual_consumption=True` with `consumption='strict'`:** `manual_consumption=True` bypasses automatic quantity computation. This can still be combined with `consumption='strict'` but only if the user manually enters the quantity.
7. **BoM explosion and product_uom:** Quantities are converted using `product_uom_id`. If the BoM's `product_uom_id` differs from the component's `uom_id`, the quantity conversion must be accurate or the moves will have wrong quantities.
8. **Operation dependencies across phantom levels:** If a phantom BoM has operations, those operations are NOT included in the exploded output — phantom BoMs do not carry their routing operations to the parent MO. Only the non-phantom BoM's operations are used.
9. **Inactive BoM:** A BoM with `active=False` is not considered by `_select_best_bom()`.
10. **Delete with existing MOs:** Standard `unlink()` raises a foreign key error if any `mrp.production` references the BoM.
