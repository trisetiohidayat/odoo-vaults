---
tags:
  - #odoo19
  - #modules
  - #sale
  - #mrp
  - #margin
---

# sale_mrp_margin — BoM-Based Cost in Sale Margin

**Module:** `sale_mrp_margin`
**Technical Name:** `sale_mrp_margin`
**Category:** Sales/Sales
**Depends:** `sale_mrp`, `sale_stock_margin`
**License:** LGPL-3
**Version:** `0.1`
**Odoo Version:** 19.0

## Overview

The `sale_mrp_margin` module extends the sale margin computation to account for **Bill of Materials (BoM) costs**. When a product is manufactured (rather than purchased), its cost is not a simple `standard_price` — it must be calculated by exploding the BoM structure and summing the costs of all components. This module integrates that manufactured cost into the `purchase_price` field on `sale.order.line`, so that the margin calculation reflects the **true manufacturing cost** rather than a potentially stale or inapplicable standard price.

The module has **no Python model files** of its own. It achieves its goal entirely through a **test file** that validates the BoM cost computation behavior. The actual BoM cost propagation is implemented by `sale_mrp` overriding `_compute_purchase_price`, and `sale_mrp_margin` exists as a test + documentation layer confirming that behavior.

```
sale_mrp_margin/
├── __init__.py
├── __manifest__.py
├── tests/
│   ├── __init__.py
│   └── test_sale_mrp_flow.py   # Extends sale_mrp's test to verify margin integration
└── (no models/, no views/, no data/)
```

---

## Module Dependencies

```
sale_mrp_margin
    └── sale_mrp          (provides: mrp.production, mrp.bom, BoM cost propagation into SOL purchase_price)
        └── sale
        └── mrp
            └── sale_stock
                └── sale_margin      (provides: purchase_price field on SOL, margin fields)
                    └── sale_management
```

The chain of inheritance:
1. `sale.order.line` gains `purchase_price` from `sale_margin`
2. `sale_mrp` overrides `_compute_purchase_price` to handle BoM products
3. `sale_stock_margin` overrides `_compute_purchase_price` to handle stock-valuated products
4. `sale_mrp_margin` tests the full integration across all three

---

## How BoM Cost Propagates into SOL Margin (L1)

### The Override Chain

`sale_mrp` (file: `addons/sale_mrp/models/sale_order_line.py`) overrides `_compute_purchase_price` to inject BoM logic. The chain is:

```
sale.order.line._compute_purchase_price (called via @api.depends)
  │
  ├── Product has a BoM? (type='phantom' kit)
  │     → button_bom_cost() or action_bom_cost()
  │       recursively sums component costs through entire BoM tree
  │       result: purchase_price = total BoM cost per unit
  │
  └── Product has no BoM?
        → falls through to sale_margin's base computation
          → product.standard_price
```

### Phantom BoM: Kit Products

When a product has a **phantom BoM** (`type='phantom'`), it is treated as a "kit" — at the time of sale order confirmation (or at BoM cost button press), the kit's cost is computed by exploding all sub-assemblies:

```
Super Kit (phantom BoM)
  └── 2x Component A (phantom BoM)
        └── 3x Component B @ $10 each
              → Component A cost = 3 × $10 = $30
  └── 2x Component A
        → Super Kit cost = 2 × $30 = $60
```

This is the scenario tested in `test_kit_cost_calculation`:
- Component B `standard_price = $10`
- Component A `button_bom_cost()` → cost = 3 × $10 = $30 (via nested phantom BoM)
- Super Kit `button_bom_cost()` → cost = 2 × $30 = $60

### When BoM Cost Is Applied

The `button_bom_cost()` method on `product.product` / `product.template` triggers the BoM explosion and updates `product.standard_price` with the computed total cost. This can be done:
1. **Manually** by the user clicking "Update Cost" → "BoM Cost" on the product form
2. **Programmatically** via `product.action_bom_cost()`

Once `standard_price` reflects the BoM cost, `sale_margin`'s `_compute_purchase_price` will read it and propagate it to the SOL's `purchase_price`.

---

## Test Coverage (L2-L4)

**File:** `tests/test_sale_mrp_flow.py`

This module's tests **extend** `sale_mrp.tests.test_sale_mrp_flow.TestSaleMrpFlowCommon`, adding margin-specific assertions on top of the standard manufacturing flow tests from `sale_mrp`.

### `test_kit_cost_calculation`

**Tests a 2-level phantom BoM scenario:**

```
BOM 1 (phantom):
  - 1x "super kit"
    └── 2x "component a"

BOM 2 (phantom):
  - 1x "component a"
    └── 3x "component b" @ $10 each
```

```
component_b.standard_price = 10
component_a.button_bom_cost()    # cost = 3 × $10 = $30
super_kit.button_bom_cost()      # cost = 2 × $30 = $60
```

Assertions at each stage:

| Stage | `purchase_price` | `margin` | Notes |
|---|---|---|---|
| After SOL creation (before SO confirm) | `60` | Based on sale price | BoM cost already applied to product |
| After `action_confirm()` | `60` | Unchanged | No change at SO confirmation |
| After receipt validation | `60` | Unchanged | Kit margin stays accurate post-delivery |

### `test_kit_cost_calculation_2`

**Tests a multi-level kit with multiple UoMs and mixed BoM types:**

```
Lovely Kit BOM (qty 1, type=phantom):
  - 10x Sub Kit
  - 10x Component B @ $10

Sub Kit BOM (qty 1, type=phantom):
  - 1x Component A @ $30
  - 2x Component B @ $10
```

```
component_a.standard_price = 30
component_b.standard_price = 10
sub_kit.action_bom_cost()   # = 1×30 + 2×10 = $50
kit.action_bom_cost()       # = 10×50 + 10×10 = $600
```

Then creates an SO with 3 units of `kit` at `product_uom=uom_ten` (tens, not units):
- `purchase_price = 600` per kit (not per unit)
- After receipt validation: `purchase_price` stays at `600`

This test verifies:
1. **Multi-level BoM explosion** works correctly
2. **Mixed UoM** (tens vs units) does not break the cost calculation
3. **Post-delivery margin** remains accurate when the delivery is confirmed

---

## How sale_mrp Implements BoM Cost (L3: Override Pattern)

### The Override Location

`sale_mrp/models/sale_order_line.py` (in the `sale_mrp` module, not `sale_mrp_margin`):

```python
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id', 'company_id', 'currency_id', 'product_uom_id')
    def _compute_purchase_price(self):
        # BoM cost calculation logic
        ...
        # Falls through to super() for non-Kit products
```

The method:
1. Checks if the product has an active BoM of type `phantom` (kit)
2. If so, calls `_get_bom_price()` which recursively resolves component costs
3. Converts to line currency and UoM
4. Stores in `purchase_price`
5. For non-Kit products, calls `super()` to delegate to `sale_margin` or `sale_stock_margin`

### `button_bom_cost` Method

Located on `product.template` (and delegated to variants):

```python
def button_bom_cost(self):
    """Update standard_price based on BoM cost."""
    self.ensure_one()
    price = self._get_bom_price()
    self.write({'standard_price': price})
```

This is the **user-facing action** that triggers BoM cost propagation. The cost is written back to `standard_price`, so `sale_margin`'s `_compute_purchase_price` picks it up on the next SOL create/edit.

---

## L3: Cross-Module Integration (sale_margin ↔ mrp)

### Data Flow

```
1. User sets component costs (standard_price)
      └── product.component_b.standard_price = 10

2. User clicks "BoM Cost" on kit product
      └── kit.button_bom_cost()
      └── Explodes BoM tree, sums component costs
      └── Writes total to kit.standard_price = 60

3. User creates SO with kit product
      └── sale_margin._compute_purchase_price (sale_mrp override)
      └── Reads kit.standard_price = 60
      └── Sets SOL.purchase_price = 60

4. User adds sale price
      └── SOL.margin computed = price_subtotal - (60 × qty)

5. User confirms SO
      └── Creates mrp.production (if make-to-order)
      └── Receipt validates → standard BoM cost confirmed in margin

6. User validates receipt
      └── sale_stock_margin._compute_purchase_price (separate override)
      └── purchase_price may update based on actual landed costs
```

### Integration with `sale_mrp`

`sale_mrp` does two things relevant to margin:
1. **Override `_compute_purchase_price`** to read BoM costs
2. **Create `mrp.production`** records linked to the SOL when manufacturing is needed

### Integration with `sale_stock_margin`

After a receipt or manufacturing order is validated, `sale_stock_margin` may update `purchase_price` based on actual landed costs (for non-standard cost method products). For BoM products, this blend can include:
- Actual component purchase costs from receipts
- Manufacturing operation costs
- Overhead allocations

---

## L4: Performance Considerations

### BoM Explosion Cost

`_get_bom_price()` traverses the entire BoM tree recursively. For deeply nested kits (3+ levels), this can be expensive if called repeatedly. In practice:
- It is called **on-demand** when the user clicks "BoM Cost" or when a product with a BoM is added to an SOL
- Results are **cached in `standard_price`** — the SOL's `purchase_price` reads from `standard_price`, not from live BoM recalculation
- No live BoM explosion occurs when opening a confirmed SO — the cost was already stored at SOL creation

### Compound Computed Field Triggers

`sale_mrp`'s override uses the same `@api.depends` as `sale_margin`:
```python
@api.depends('product_id', 'company_id', 'currency_id', 'product_uom_id')
```
This means changing the BoM, updating component costs, or changing the product UoM on the SOL will **trigger a recompute** of `purchase_price`.

---

## L4: Version Change Odoo 18 to 19

### Changes in Odoo 19

`sale_mrp_margin` is a lightweight module — its main content is its test suite. Key aspects:

1. **`version = '0.1'`** in the manifest — this module was in earlier versions too, but is simple enough that structural changes are minimal

2. **`sale_mrp` module changes (affecting BoM margin behavior):**
   - Odoo 19 improved the BoM cost computation to better handle multi-level kits
   - The `_get_bom_price()` method in `sale_mrp` was refactored to support more complex routing scenarios (operation costs, work centers)
   - Phantom BoM behavior is unchanged — kits are still exploded at BoM cost button time

3. **No model/field changes** in `sale_mrp_margin` itself between versions

4. **Test inheritance pattern** — the test extends `sale_mrp.tests.test_sale_mrp_flow.TestSaleMrpFlowCommon`, meaning it automatically benefits from any changes to the parent test class in `sale_mrp`

---

## Limitations

1. **BoM cost must be manually triggered** — `button_bom_cost()` is not automatic. Users must explicitly click to update product cost from BoM
2. **Phantom BoM only** — non-phantom (manufacturing or subcontract) BoMs are not automatically used in `purchase_price` computation
3. **Standard cost method dependency** — the module assumes the product's cost method is `standard` (BoM cost is written to `standard_price`). For `average` or `FIFO` products, `sale_stock_margin` may override the BoM cost with actual landed costs
4. **No live BoM update on component cost change** — if a component's `standard_price` changes, existing confirmed SOs retain their stored `purchase_price` (stored field)
5. **Manufacturing lead time not in margin** — labor and overhead costs from `mrp.workcenter` operations are not included in the BoM cost unless explicitly configured as component costs

---

## See Also

- [Modules/Sale](odoo-18/Modules/sale.md) — `sale.order.line` with `purchase_price` and margin fields
- [Modules/MRP](odoo-18/Modules/mrp.md) — `mrp.bom`, `mrp.production`, BoM cost computation
- [Modules/sale_stock_margin](odoo-18/Modules/sale_stock_margin.md) — `purchase_price` from stock valuation layers
- [Modules/sale_margin](odoo-18/Modules/sale_margin.md) — Base margin computation (`margin`, `margin_percent`)
- [Core/API](odoo-18/Core/API.md) — Override pattern via `_inherit` and `super()`
- [Modules/Product](odoo-18/Modules/product.md) — `standard_price`, BoM types, product cost methods
