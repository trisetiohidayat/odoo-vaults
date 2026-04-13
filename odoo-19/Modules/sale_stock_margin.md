---
tags:
  - #odoo19
  - #modules
  - #sale
  - #stock
  - #margin
---

# sale_stock_margin — Stock-Valuated Cost in Sale Margin

**Module:** `sale_stock_margin`
**Technical Name:** `sale_stock_margin`
**Category:** Sales/Sales
**Depends:** `sale_stock`, `sale_margin`
**License:** LGPL-3
**Version:** `0.1`
**Odoo Version:** 19.0
**Auto-install:** `True` (installs automatically when both dependencies are present)

## Overview

The `sale_stock_margin` module extends the `purchase_price` computation on `sale.order.line` to use **actual stock valuation costs** instead of (or in addition to) `product.standard_price`. When products are received into stock, their actual landed costs are recorded in stock valuation layers. This module reads those real costs — blended with any remaining `standard_price` quantities — and writes them to the SOL's `purchase_price`, giving an **exact margin** that reflects what was actually paid for the goods.

The key insight is that this module operates at the intersection of **stock valuation** and **sale margin**:
- For **FIFO and Average Cost** products: `purchase_price` reflects actual received costs
- For **Standard Cost** products: `purchase_price` stays as `standard_price` (no override)
- For **mixed receipt/delivered scenarios**: a weighted average of delivered costs and remaining standard costs is computed

```
sale_stock_margin/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── sale_order_line.py     # Overrides _compute_purchase_price
└── tests/
    ├── __init__.py
    └── test_sale_stock_margin.py  # 12 test cases covering all scenarios
```

---

## Module Dependencies

```
sale_stock_margin
    └── sale_stock        (provides: stock.picking, stock.move, valued move tracking)
        └── sale           (provides: sale.order, sale.order.line)
        └── stock         (provides: stock.quant, stock.valuation.layer)
    └── sale_margin        (provides: purchase_price field, margin computation)
        └── sale_management
```

**Dependency chain for `purchase_price`:**
```
sale.order.line.purchase_price (defined by sale_margin)
  │
  └── _compute_purchase_price (overridden by sale_stock_margin for valued products)
        └── sale_stock_margin override (this module)
              └── product.stock_move_ids (valued moves from stock module)
              └── _get_price_unit() from stock.move
```

---

## Model: sale.order.line

**File:** `models/sale_order_line.py`
**Inheritance:** `_inherit = 'sale.order.line'` (classical extension)
**Method Override:** `_compute_purchase_price`

### Overriding `_compute_purchase_price`

```python
@api.depends('move_ids', 'move_ids.value', 'move_ids.picking_id.state')
def _compute_purchase_price(self):
    line_ids_to_pass = set()
    for line in self:
        product = line.product_id.with_company(line.company_id)
        if not line.has_valued_move_ids():
            line_ids_to_pass.add(line.id)
        elif line.product_id and line.product_id.categ_id \
                and line.product_id.categ_id.property_cost_method != 'standard':
            # don't overwrite any existing value unless non-standard cost method
            qty_from_delivery = line.qty_delivered
            price_unit_from_delivery = (
                line.move_ids.filtered(
                    lambda m: m.state == 'done'
                )._get_price_unit() if qty_from_delivery > 0 else 0
            )
            if qty_from_delivery <= 0:
                purch_price = product.standard_price
            else:
                qty_from_std_price = max(line.product_uom_qty - qty_from_delivery, 0)
                purch_price = (
                    qty_from_delivery * price_unit_from_delivery
                    + qty_from_std_price * product.standard_price
                ) / (qty_from_delivery + qty_from_std_price)
            purch_price_uom = line.product_id.uom_id._compute_price(
                purch_price, line.product_uom_id
            )
            line.purchase_price = line._convert_to_sol_currency(
                purch_price_uom,
                product.cost_currency_id,
            )
        elif not line.product_uom_qty and line.qty_delivered:
            # if line added from delivery and standard price, pass to super
            line_ids_to_pass.add(line.id)
    return super(SaleOrderLine, self.browse(line_ids_to_pass))._compute_purchase_price()
```

---

## L1: How Purchase Price Is Computed from Stock

### The Three Scenarios (L2: Field Logic)

The override handles three distinct cases based on the state of the order line's **stock moves**:

#### Scenario 1: No Valued Moves (`has_valued_move_ids() = False`)

```
Condition: line.has_valued_move_ids() returns False
  → delegate entirely to super() (sale_margin base computation)
  → purchase_price = product.standard_price
```

Called when:
- No stock moves exist for this line yet (SO not confirmed)
- The product is a service (no stock tracking)
- The product has `type != 'product'` (not storable)

#### Scenario 2: Standard Cost Method Product

```
Condition: product.categ_id.property_cost_method == 'standard'
  → delegate to super()
  → purchase_price = product.standard_price (unchanged)
```

For standard-cost products, the product's configured cost is always used. Actual receipt costs do not affect margin. This is the correct behavior because standard cost products have a **predetermined** cost that is not influenced by actual purchase prices.

#### Scenario 3: Non-Standard Cost (Average/FIFO) — Weighted Average Blend

```
Condition: has_valued_move_ids() == True
         AND cost_method != 'standard'
         AND qty_delivered > 0
```

```
price_unit_from_delivery = done_moves._get_price_unit()
qty_from_delivery        = line.qty_delivered
qty_from_std_price       = max(product_uom_qty - qty_delivered, 0)

purch_price = (
    qty_from_delivery   * price_unit_from_delivery
  + qty_from_std_price * product.standard_price
) / (qty_from_delivery + qty_from_std_price)
```

**Weighted average formula:**

| Component | Formula | Meaning |
|---|---|---|
| `price_unit_from_delivery` | `stock.move._get_price_unit()` | Average cost from actual receipt valuation layers |
| `qty_from_delivery` | `line.qty_delivered` | Units already shipped/received |
| `qty_from_std_price` | `max(product_uom_qty - qty_delivered, 0)` | Units not yet delivered |
| Blended cost | weighted avg of delivered + undelivered portions | Smooths margin across partial deliveries |

**Special case: `qty_delivered <= 0` (no deliveries yet):**
```
purch_price = product.standard_price
```
Falls back to standard price if delivery has not yet occurred.

---

### `has_valued_move_ids` Method (L3: Cross-Model)

`has_valued_move_ids()` is defined in the `sale_stock` module on `sale.order.line`. It returns `True` when:
- The SOL has associated `stock.move` records
- At least one move is in state `done`
- The product's category uses **average** or **FIFO** cost method

This check ensures that only products with actual stock valuation layers get the stock-based cost.

### `_get_price_unit` on `stock.move` (L3: Cross-Model)

Defined in `stock/models/stock_move.py`, this method returns the **average valuation cost** from the move's valuation layers:

```python
def _get_price_unit(self):
    """Returns average price from valuation layers for this move."""
    if self.product_id.cost_method in ('average', 'fifo'):
        layers = self.stock_valuation_layer_ids
        if layers:
            return sum(layers.mapped('value')) / sum(layers.mapped('quantity'))
    return self.product_id.standard_price
```

For FIFO products: returns the actual cost of the specific lots consumed.
For Average Cost products: returns the current average cost at time of delivery.

---

## L2: Field Types, Defaults, Constraints

### The `purchase_price` Field (inherited from sale_margin)

All attributes from `sale_margin` are inherited. Key attributes:

| Attribute | Value | Notes |
|---|---|---|
| Type | `fields.Float` | Non-Monetary; cost per unit |
| Store | `True` | Persisted to DB |
| Readonly | `False` | User can manually override |
| Copy | `False` | Not copied on SOL duplication |
| Precompute | `True` (sale_margin) | Eagerly computed at record creation |
| Groups | `base.group_user` | Visible to internal users |

`sale_stock_margin` does **not** add new fields — it only overrides the compute method. The `margin` and `margin_percent` fields on the SOL are unchanged.

### Dependency on `move_ids`

The override adds `@api.depends('move_ids', 'move_ids.value', 'move_ids.picking_id.state')` to the already-existing dependency on `'product_id', 'company_id', 'currency_id', 'product_uom_id'`. This means `purchase_price` will **automatically recompute** whenever:
- A delivery picking is validated (`state` changes to `done`)
- The valuation layers of a move change (`value` changes)
- A move is added to the SOL

---

## L3: Cross-Module Integration (sale_margin ↔ stock)

### Integration Points

```
sale_stock_margin._compute_purchase_price
    │
    ├──→ sale.order.line.move_ids
    │       └── stock.move records linked to this SOL
    │       └── state: draft → confirmed → done → cancelled
    │
    ├──→ stock.move._get_price_unit()
    │       └── Reads stock.valuation.layer records
    │       └── Returns average unit cost from valuation layers
    │
    ├──→ product.categ_id.property_cost_method
    │       └── 'standard' → skip override
    │       └── 'average'  → use override
    │       └── 'fifo'     → use override
    │
    └──→ sale_margin._compute_purchase_price (super())
            └── Falls back to product.standard_price for:
                  - Service products
                  - Standard cost products
                  - Lines without valued moves
```

### Delivery-Added SOLs

When a product is added directly to a **delivery order** (not the original SO):

```
User adds product X to an existing delivery picking
  → Creates a new SOL on the existing SO (product_uom_qty = 0, qty_delivered = added qty)
  → sale_stock_margin._compute_purchase_price is called
  → Since product_uom_qty = 0, falls through to super() → standard_price
  → BUT if the product has valued moves, the override uses the move cost
```

Special case (line 31-34):
```python
elif not line.product_uom_qty and line.qty_delivered:
    # if line added from delivery and standard price, pass to super
    line_ids_to_pass.add(line.id)
```
This correctly delegates to `sale_margin`'s base computation for delivery-added lines with standard cost method, while still computing from stock valuation for average/FIFO products.

---

## L3: Workflow Triggers

### When Does `purchase_price` Update?

| Event | `purchase_price` Result | Trigger |
|---|---|---|
| SO created (draft) | `product.standard_price` | `@api.depends` |
| SO confirmed / delivery created | Unchanged | — |
| Delivery partially validated | Blended cost | `move_ids.picking_id.state` |
| Delivery fully validated | Blended cost | `move_ids.picking_id.state` |
| Delivery cancelled | Reverts | `picking_id.state` change |
| Return receipt validated | Negative qty in blend | `qty_delivered` change |
| Product `standard_price` changed | Blended cost recalculates | `product_id` dependency |

### Critical Trigger: Delivery Validation

When a delivery is validated:
1. `stock.move.quantity` is set to done
2. `stock.valuation.layer` records are created with actual cost
3. `move.picking_id.state` changes to `done`
4. The `@api.depends('move_ids.picking_id.state')` on the SOL fires
5. `_compute_purchase_price` re-reads `stock.move._get_price_unit()`
6. `purchase_price` updates to reflect the actual landed cost

This is the **exact margin** moment — after delivery validation, the margin reflects what was actually paid.

---

## L3: Failure Modes

| Scenario | Behavior | Risk |
|---|---|---|
| No stock moves for a non-standard cost product | Falls back to `standard_price` | Margin may be inaccurate |
| Standard cost product with valued moves | Override skipped; `standard_price` always used | Intentional — standard cost is fixed |
| Multi-currency receipts | `_get_price_unit()` returns in company currency; `_convert_to_sol_currency()` handles FX | Should be correct |
| Partial delivery of 1 unit from a batch of 100 | Weighted avg uses `qty_delivered=1` in numerator | Small skew in margin |
| Return receipt (negative `qty_delivered`) | Blend includes negative qty | Margin can become negative |
| Product changed on existing SOL | Recomputes from new product's stock cost | Intentional |
| User manually edited `purchase_price` | Field is `readonly=False`; manual value persists | User must be aware that delivery validation may overwrite it |
| Confirmed SO cancelled and set to draft | Moves cancelled; fallback to `standard_price` | Margin reverts |

---

## Test Coverage (L4: All Scenarios)

**File:** `tests/test_sale_stock_margin.py`
**Test Class:** `TestSaleStockMargin` (extends `TestStockValuationCommon`)
**Tagged:** `post_install`, `-at_install`

All tests use `stock_account` (`TestStockValuationCommon`) to provide actual stock valuation. The test harness creates incoming stock moves (receipts) before creating SOs, simulating real receipt-then-deliver scenarios.

### `test_sale_stock_margin_1` — Single Receipt, Single Delivery

```
Stock: IN 2 @ $35 → OUT 1
SO: 1 unit @ $50
```

| Stage | `purchase_price` | `margin` |
|---|---|---|
| After SO confirm | `35` (from receipt) | `15` |
| After delivery validation | `35` (unchanged — 1 of 2 received already accounted) | `15` |

### `test_sale_stock_margin_2` — Two Batches, Partial Delivery

```
Stock: IN 2 @ $32 → IN 5 @ $17 → OUT 1
SO: 2 units @ $50
```

| Stage | `purchase_price` | `margin` | Notes |
|---|---|---|---|
| After SO confirm | `19.50` | `61` | Blended: (1×32 + 1×7) from last layer average |
| After delivery validation | `24.50` | `51` | Both units delivered at blended cost of 24.50 |

Math: After full delivery of 2 units, the weighted average uses 1 from layer 1 ($32) + 1 from layer 2's average ($17), but test 2 shows `24.5`. This reflects the actual layer costs after the OUT move: the remaining layer (6 units at avg cost ~$18.33) blended back.

### `test_sale_stock_margin_3` — Full Receipt, Partial Delivery

```
Stock: IN 2 @ $10 → OUT 1
SO: 2 units @ $20
```

| Stage | `purchase_price` | `margin` |
|---|---|---|
| After SO confirm | `10` | `20` |
| After partial delivery | `10` | `20` (unchanged) |

### `test_sale_stock_margin_4` — Two Different Batches, Partial Delivery

```
Stock: IN 2 @ $10 → IN 1 @ $20 → OUT 1
SO: 2 units @ $20
```

| Stage | `purchase_price` | `margin` |
|---|---|---|
| After SO confirm | `15` | `10` (blended avg of remaining layers) |
| After partial delivery | `15` | `10` (unchanged after delivery) |

### `test_sale_stock_margin_5` — Two Products, Multi-Line SO

```
Product 1: IN 2 @ $35 → IN 1 @ $51 → OUT 1
Product 2: IN 2 @ $17 → IN 1 @ $11 → OUT 1
SO: 2x Product1 @ $60, 4x Product2 @ $20
```

| Stage | `purchase_price` | `margin` |
|---|---|---|
| After confirm | P1=$43, P2=$14 | P1=34, P2=24, Total=58 |
| After delivery | P1=$43, P2=$12.5 | P1=34, P2=30, Total=64 |

Note: After delivery of 1 unit of each (remaining 1 of each at blended cost), purchase prices converge toward remaining layer costs.

### `test_sale_stock_margin_6` — Service Product in SO

Tests that service products (no stock moves) correctly use `sale_margin`'s base computation:
```
Service: cost=50, price=100 → margin=50
Product: cost=40, price=80 → margin=40
```
Manual override of `purchase_price` on service line is preserved after SO confirm.

### `test_so_and_multicurrency` — Multi-Currency SO

When SO uses a different currency than the product's cost currency:
- `product.standard_price = 100` (USD, company currency)
- `so.currency_id = EUR` (pricelist)
- `so_line.price_unit = 400` (EUR, based on EUR pricelist)
- `so_line.purchase_price = 200` (converted from USD cost, NOT the sale price)
- Margin = 400 - 200 (in EUR) = 200 EUR

### `test_so_and_multicompany` — Multi-Company

Confirms that when a user in one company confirms an SO belonging to another company, the `purchase_price` is computed in the **SO's company context**, not the user's context.

### `test_purchase_price_changes` — Manual Override + Currency Change

Tests the interaction between manual `purchase_price` edits and automatic recompute:
1. User manually sets `purchase_price = 15` (default was 20)
2. Email quote is sent (state → `sent`)
3. SO is confirmed — manual value preserved (`15`)
4. SO is cancelled and set to draft
5. Currency is changed → `purchase_price` recomputes to 40 (double, from currency change)

### `test_add_product_on_delivery_price_unit_on_sale` — Add to Delivery

Tests adding a product directly to a delivery picking (not the original SO):
- New SOL created on existing SO with `product_uom_qty=0`, `qty_delivered=10`
- `purchase_price` correctly set from `standard_price` (10, from earlier receipt)
- `price_unit` from product's `list_price`
- `margin_percent` = 0.5 (50%)

### `test_add_standard_product_on_delivery_cost_on_sale_order` — Standard Cost Added in Delivery

When a **standard cost** product is added to a delivery:
- `purchase_price` = `standard_price` (override skipped — standard cost method)
- Confirms that delivery-added standard cost products still compute margin correctly

### `test_add_avco_product_on_delivery_cost_on_sale_order` — Average Cost Added in Delivery

Same as above but for **average cost** product:
- `purchase_price` = `standard_price` (which reflects the average cost)
- Confirms override works for delivery-added average cost products

### `test_avco_does_not_mix_products_on_compute_avg_price`

Stress test: what happens when a delivery move's product is changed?
- Confirms that when a move's product is changed, the sale line linkage is cleared
- A new SOL is created for the new product
- The original SOL's `purchase_price` remains correct (10)

### `test_avco_different_uom` — Non-Default UoM

Tests that the purchase price UoM conversion works correctly:
- Product AVCO = 1 per unit, but ordered in dozens
- `purchase_price = 1` per unit → `margin = 12` per dozen (12 × (3-1))

### `test_avco_calc` — Complete AVCO Lifecycle (Complex)

The most detailed test — tracks a single AVCO product through multiple receipts, deliveries, and returns:

| Step | Action | AVCO Cost | `purchase_price` | `margin` | Notes |
|---|---|---|---|---|---|
| 1 | IN 2 @ $20, IN 2 @ $40 | $30 | `30` | `140` | avg = (2×20+2×40)/4 |
| 2 | SO confirm, deliver 1 | $30 | `30` | `140` | No change until delivery |
| 3 | Backorder created | — | — | — | 1 unit remains |
| 4 | IN 2 @ $142.50 | $75 | `30` (unchanged) | `140` | AVCO jumps but SOL not updated |
| 5 | Deliver 2 (backorder) | — | `60` | `80` | Purchase price now reflects current AVCO |
| 6 | Return 3 (negative qty) | $33 | — | — | AVCO adjusts for returned qty |
| 7 | SOL qty reduced to 0 | — | — | — | Margin based on qty_delivered |

### `test_avco_zero_quantity` — Zero Quantity SOL Edge Cases

Tests the most complex edge cases:
- `product_uom_qty = 0, qty_delivered = 0`: margin = 0
- `product_uom_qty = 0, qty_delivered = -2` (return): margin negative (cost for returned goods)
- After all returns, AVCO settles to a stable value
- Products added **from delivery** with `product_uom_qty = 0` correctly use standard price as fallback

---

## L4: Performance Implications

### When Override Does NOT Recompute

`sale_stock_margin` is designed to minimize recomputation. It **skips** (`line_ids_to_pass`) any line where:
1. No valued moves exist (no stock involved)
2. Product uses standard cost method (no need for stock-based cost)
3. Line was added from delivery and uses standard price

Only lines with actual valued moves and non-standard cost methods execute the full stock-based computation.

### Dependency Chain and Cascade

```
stock.picking.button_validate()
  → stock.move.quantity = done
  → stock.valuation.layer created
  → move.picking_id.state = 'done'
  → @api.depends('move_ids.picking_id.state') fires
  → sale.order.line._compute_purchase_price
  → sale_stock_margin override → _get_price_unit()
  → purchase_price updated
  → @api.depends('purchase_price') fires
  → sale.order.line._compute_margin
  → margin and margin_percent updated
```

This cascade is **single-record-scoped** for normal operations and batch-optimized by Odoo's ORM for bulk moves.

---

## L4: Security Considerations

`sale_stock_margin` adds no new fields and does not modify ACLs. It inherits all security from:
- `sale_margin` (cost field restricted to `base.group_user`)
- `sale_stock` (delivery picking access via standard record rules)
- `stock` (valuation layer access)

**Commercial sensitivity:** `purchase_price` reveals product costs. `sale_stock_margin` makes this even more sensitive by exposing actual receipt costs (possibly negotiated vendor prices). The `groups="base.group_user"` restriction should be reviewed for organizations where vendor pricing must be kept confidential.

---

## L4: Version Change Odoo 18 to 19

### Changes in Odoo 19

1. **`has_valued_move_ids` check improved** in `sale_stock`:
   - More robust detection of valued moves for average/FIFO products
   - Ensures the override only triggers for products with actual stock valuation

2. **Delivery-added line handling (line 31-34)**:
   - The special case for `product_uom_qty = 0, qty_delivered > 0` ensures that lines added directly to delivery pickings correctly fall through to `sale_margin`'s base computation
   - Prevents incorrect `purchase_price` for delivery-added standard-cost lines

3. **Weighted average formula remains stable** — the core blend formula (`qty_delivered × delivery_price + qty_from_std × std_price`) is unchanged from Odoo 18

4. **AVCO (Average Cost) handling improved**:
   - The `test_avco_calc` and `test_avco_zero_quantity` tests confirm that AVCO products behave correctly through complex multi-receipt, multi-delivery, and return scenarios
   - Negative delivery quantities are handled gracefully in the blend

---

## Limitations

1. **No Landed Costs**: Stock valuation layers record the purchase price, not landed costs (freight, duties, insurance). True landed cost margin requires `stock_landed_costs` module
2. **Standard Cost products unaffected**: Receipt costs do not change `purchase_price` for standard cost products — margin will always use the configured `standard_price`
3. **Manual overrides are overwritten**: If a user manually sets `purchase_price`, a subsequent delivery validation will overwrite it with the stock-based cost
4. **No future receipts in margin**: If ordered qty > delivered qty, the undelivered portion uses `standard_price` (which may be outdated). Only after all units are delivered does the full margin reflect actual cost
5. **Currency conversion timing**: `_get_price_unit()` returns in the product's `cost_currency_id`. If the product's cost currency differs from the SO's currency, conversion uses the rate at conversion time, not the rate at receipt time
6. **Returns reduce margin**: A return (negative `qty_delivered`) causes `purchase_price` to blend at a negative quantity, which can make the blended cost diverge significantly from the actual remaining inventory value

---

## See Also

- [Modules/Sale](Modules/Sale.md) — Parent `sale.order.line` model
- [Modules/sale_margin](Modules/sale_margin.md) — Base margin computation (`purchase_price`, `margin`, `margin_percent`)
- [Modules/sale_mrp_margin](Modules/sale_mrp_margin.md) — BoM-based cost for manufactured products
- [Modules/Stock](Modules/Stock.md) — `stock.move`, `stock.valuation.layer`, `has_valued_move_ids`
- [Modules/stock_account](Modules/stock_account.md) — Stock valuation, average/FIFO cost computation
- [Core/API](Core/API.md) — `@api.depends` cascade, computed field override patterns
- [Core/Fields](Core/Fields.md) — `fields.Float` with `store`, `copy`, `precompute`
