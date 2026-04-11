# mrp_landed_costs — Manufacturing Landed Costs

**Module:** `mrp_landed_costs`
**Odoo Version:** 18
**Source:** `~/odoo/odoo18/odoo/addons/mrp_landed_costs/`
**Depends:** `stock_landed_costs`, `mrp_account`
**Category:** Manufacturing/Manufacturing
**Auto-install:** False

---

## Purpose

The `mrp_landed_costs` module extends `stock_landed_costs` to allow **landed costs to be applied to manufacturing orders** in addition to stock pickings. It adds a third `target_model` option (`'manufacturing'`) to the `stock.landed.cost` form, and wires the MO's finished product moves into the landed cost validation pipeline.

**Use cases:**
- **Custom duties** on raw materials imported for manufacturing — applied at MO receipt
- **Shipping/freight costs** for components that go directly into production
- **Tooling/mold costs** amortized across manufactured units
- **Quality inspection fees** allocated to finished products

---

## Module Structure

```
stock_landed_costs (base)
  └── stock.landed.cost          # target_model = 'picking' only by default
  └── stock.landed.cost.lines
  └── stock.valuation.adjustment.lines

mrp_account (also depends on stock_landed_costs)
  └── mrp.production cost fields
  └── stock.move valuation overrides

mrp_landed_costs
  └── Extends stock.landed.cost
        ├── target_model: adds 'manufacturing'
        ├── mrp_production_ids: M2M to mrp.production
        └── _get_targeted_move_ids(): includes finished moves from MOs
```

**Dependency chain:**
```
stock_account
  └── stock_landed_costs
        └── mrp_landed_costs

mrp
  └── mrp_account
        └── (requires stock_landed_costs for full WIP)
```

---

## Model: `stock.landed.cost` (Extended by mrp_landed_costs)

**File:** `models/stock_landed_cost.py`

The base `stock.landed.cost` model is defined in `addons/stock_landed_costs/models/stock_landed_cost.py`.

### Fields Added by mrp_landed_costs

| Field | Type | Description |
|-------|------|-------------|
| `target_model` | `Selection` (extended) | Added `'manufacturing'` option: `"Apply On" = "Manufacturing Orders"` |
| `mrp_production_ids` | `Many2many` | Manufacturing orders selected for cost allocation. Visible when `target_model = 'manufacturing'`. `copy=False`, `groups='stock.group_stock_manager'` |

### `target_model` Selection (full, after extension)

| Value | Label | Notes |
|-------|-------|-------|
| `'picking'` | Transfers | Base `stock_landed_costs` default |
| `'manufacturing'` | Manufacturing Orders | Added by `mrp_landed_costs` |

### Key Methods

#### `_onchange_target_model()`

```python
@api.onchange('target_model')
def _onchange_target_model(self):
    super()._onchange_target_model()
    if self.target_model != 'manufacturing':
        self.mrp_production_ids = False  # Clear MOs when switching away
```

When the user switches `target_model` away from `'manufacturing'`, the `mrp_production_ids` field is cleared (since `super()._onchange_target_model()` handles clearing `picking_ids` for the `'picking'` case).

#### `_get_targeted_move_ids()`

```python
def _get_targeted_move_ids(self):
    return super()._get_targeted_move_ids() | self.mrp_production_ids.move_finished_ids
```

**L4 — How MO Moves Enter Landed Cost:**

```
stock.landed.cost (target_model='manufacturing')
  └── mrp_production_ids: [MO/001, MO/002]
        └── MO/001.move_finished_ids
              └── Move for product FG (the finished product receipt move)
                    └── Included in get_valuation_lines()

get_valuation_lines() (base):
  For each targeted move:
    - Skip if product cost_method not in ('fifo', 'average')
    - Skip if move.state == 'cancel'
    - Skip if move.quantity == 0
    - Create valuation adjustment line with:
        product_id, move_id, quantity, former_cost (= sum SVL values)
```

The `super()._get_targeted_move_ids()` returns `self.picking_ids.move_ids`. This method extends it with `self.mrp_production_ids.move_finished_ids` — the receipt moves for finished products.

**Key constraint:** Only finished product moves (`move_finished_ids`) are targeted, not raw material consumption moves. This is intentional — landed costs for manufacturing apply to the **finished product**, not the components.

---

## How Landed Costs Work: The Full Pipeline

### Step 1: Create the Landed Cost Record

```
stock.landed.cost
  ├── target_model = 'manufacturing'
  ├── mrp_production_ids = [MO/001]     ← Select the MO(s)
  ├── cost_lines = [
  │     {product: Freight Service, price_unit: 500, split_method: 'by_quantity'}
  │   ]
  └── state = 'draft'
```

### Step 2: `compute_landed_cost()` (shared base logic)

The base `stock.landed.cost.button_validate()` calls `compute_landed_cost()` which:

1. Calls `get_valuation_lines()` → returns adjustment lines per finished move
2. For each cost line, distributes its cost across adjustment lines using the `split_method`:
   - `'equal'`: divide equally across all moves
   - `'by_quantity'`: divide by `quantity` field on each line
   - `'by_weight'`: divide by `weight` field
   - `'by_volume'`: divide by `volume` field
   - `'by_current_cost_price'`: divide by `former_cost` (current product cost)

### Step 3: `button_validate()` (shared base logic)

1. Creates `stock.valuation.layer` records for each adjustment line with `additional_landed_cost`
2. For average/FIFO products: updates `product.standard_price`:
   ```python
   product.standard_price += cost_to_add_byproduct[product] / product.quantity_svl
   ```
3. Creates journal entry (for real-time products):
   - DR `stock_valuation` account (landed cost added to inventory value)
   - CR `stock_input` or cost line's `account_id` (expense/payable)

### Step 4: Reconciliation (if vendor bill linked)

`reconcile_landed_cost()` reconciles the vendor bill's `stock_input` lines with the landed cost journal entry's `stock_input` lines under anglo-saxon accounting.

---

## Landed Cost vs Purchase Landed Cost (Comparison)

| Aspect | Purchase Landed Cost | Manufacturing Landed Cost |
|--------|---------------------|---------------------------|
| `target_model` | `'picking'` | `'manufacturing'` |
| Source document | `stock.picking` (receipt) | `mrp.production` |
| Targeted moves | `picking_ids.move_ids` (all receipt moves) | `mrp_production_ids.move_finished_ids` (finished product moves only) |
| Typical costs | Freight, insurance, customs on PO | Customs on imported components, shipping to production, tooling |
| When applied | After validating receipt picking | After validating MO |
| Effect on valuation | Increases component cost (AVCO/FIFO) | Increases finished product cost |
| Accounting entry | DR Stock Valuation / CR Stock Input | DR Stock Valuation / CR Stock Input |

---

## How Landed Costs Affect Product Standard Price

For average cost (AVCO) and FIFO products, `button_validate()` calls:

```python
# In base stock_landed_costs button_validate():
for product in products:  # only products with cost_method in ('average', 'fifo')
    if not float_is_zero(product.quantity_svl, precision_rounding=product.uom_id.rounding):
        product.sudo().with_context(disable_auto_svl=True).standard_price += (
            cost_to_add_byproduct[product] / product.quantity_svl
        )
```

**L4 — Prorated SVL Update:**

The landed cost is prorated based on the **remaining quantity in stock**:
```python
remaining_qty = sum(line.move_id._get_stock_valuation_layer_ids().mapped('remaining_qty'))
move_qty = line.move_id.product_uom._compute_quantity(line.move_id.quantity, ...)
cost_to_add = (remaining_qty / move_qty) * line.additional_landed_cost
```

This means:
- If all finished product is still in stock → full cost added to `standard_price`
- If half is sold/delivered → only half the cost is added (remaining half already matched to delivered goods)
- The `remaining_value` on the SVL is updated to reflect the added cost

---

## Allocation Methods for Manufacturing

| Split Method | Formula | Best For |
|-------------|---------|---------|
| `equal` | `cost / num_products` | When each unit incurs equal landed cost |
| `by_quantity` | `cost × (product_qty / total_qty)` | Different production volumes |
| `by_weight` | `cost × (weight / total_weight)` | Heavy vs light finished products |
| `by_volume` | `cost × (volume / total_volume)` | Bulky vs compact products |
| `by_current_cost_price` | `cost × (former_cost / total_former_cost)` | Higher-cost items bear more of the landed cost |

**L4 — Manufacturing-specific consideration:**
Since landed costs for manufacturing are applied to **finished products** (not components), the `by_current_cost_price` method allocates based on the finished product's current cost — meaning more expensive products absorb more of the landed cost. This is useful when multiple products share the same production line and you want costs distributed proportionally.

---

## WIP Interaction

When a landed cost is applied to an **in-progress MO** (MO not yet done):

1. The finished move may not yet have SVLs (no receipt recorded)
2. `get_valuation_lines()` will still include the move if `move.quantity > 0`
3. However, without SVLs, `former_cost = 0`, so the full landed cost becomes the product's cost
4. After the MO is done: the landed cost is already reflected in `standard_price` or as an additional SVL

**Best practice:** Apply landed costs only to **completed** MOs or after receiving the finished goods, to avoid distorted `standard_price` before all costs are known.

---

## Verified Source Files

| File | Key Elements Verified |
|------|----------------------|
| `addons/mrp_landed_costs/models/stock_landed_cost.py` | Full extension: `target_model` selection add, `mrp_production_ids`, `_onchange_target_model()`, `_get_targeted_move_ids()` |
| `addons/mrp_landed_costs/models/__init__.py` | Imports only `stock_landed_cost` |
| `addons/stock_landed_costs/models/stock_landed_cost.py` | Base landed cost model (full 506-line file): `button_validate()`, `compute_landed_cost()`, `get_valuation_lines()`, `reconcile_landed_cost()`, `_get_targeted_move_ids()`, all accounting entries, SVL creation |

---

## Tags

`#odoo18` `#modules` `#mrp` `#landed-costs` `#valuation` `#manufacturing-accounting`
