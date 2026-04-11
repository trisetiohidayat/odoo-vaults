# stock_landed_costs - WMS Landed Costs

**Module:** `stock_landed_costs`
**Depends:** `stock_account`, `purchase_stock`
**Category:** Inventory/Inventory

---

## Purpose

Allows adding extra landed costs (freight, insurance, customs duties, handling fees) to stock pickings. Costs are split across stock moves using various allocation methods (equal, by quantity, by weight, by volume, by current cost), then posted to accounting and incorporated into product valuation via `stock.valuation.layer` records.

---

## Core Models

### stock.landed.cost

**File:** `models/stock_landed_cost.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`

| Field | Type | Description |
|---|---|---|
| `name` | `Char` | Auto-generated sequence, default "New" |
| `date` | `Date` | Cost date, default today |
| `target_model` | `Selection` | `'picking'` (only option) |
| `picking_ids` | `Many2many` | Transfers to apply costs to |
| `cost_lines` | `One2many` | Cost line definitions |
| `valuation_adjustment_lines` | `One2many` | Computed cost allocations per move |
| `description` | `Text` | Internal notes |
| `amount_total` | `Monetary` | Sum of cost line price_units (computed) |
| `state` | `Selection` | `'draft'` / `'done'` / `'cancel'` |
| `account_move_id` | `Many2one` | Posted journal entry |
| `account_journal_id` | `Many2one` | Journal for the entry |
| `company_id` | `Many2one` | Company |
| `stock_valuation_layer_ids` | `One2many` | All SVLs created by this cost |
| `vendor_bill_id` | `Many2one` | Linked vendor bill (`account.move` of type `in_invoice`) |
| `currency_id` | `Many2one` | Company currency |

**State Flow:** `draft` -> `done` (via `button_validate()`)

---

### stock.landed.cost.lines

**File:** `models/stock_landed_cost.py`

| Field | Type | Description |
|---|---|---|
| `name` | `Char` | Line description |
| `cost_id` | `Many2one` | Parent landed cost |
| `product_id` | `Many2one` | Product (must be a landed cost type) |
| `price_unit` | `Monetary` | Cost amount |
| `split_method` | `Selection` | How to allocate this cost |
| `account_id` | `Many2one` | Expense account (defaulted from stock_input) |
| `currency_id` | `Many2one` | Inherited from cost_id |

**Split Methods (SPLIT_METHOD):**

```python
SPLIT_METHOD = [
    ('equal', 'Equal'),
    ('by_quantity', 'By Quantity'),
    ('by_current_cost_price', 'By Current Cost'),
    ('by_weight', 'By Weight'),
    ('by_volume', 'By Volume'),
]
```

Onchange `product_id`: auto-fills `name`, `split_method` (from product's `split_method_landed_cost`), `price_unit` (from `standard_price`), and `account_id` (from stock_input).

---

### stock.valuation.adjustment.lines

**File:** `models/stock_landed_cost.py`

| Field | Type | Description |
|---|---|---|
| `name` | `Char` | Computed: `{cost_line.name} - {product.display_name}` |
| `cost_id` | `Many2one` | Parent landed cost |
| `cost_line_id` | `Many2one` | Source cost line |
| `move_id` | `Many2one` | Target stock.move |
| `product_id` | `Many2one` | Product |
| `quantity` | `Float` | Move qty in product UoM |
| `weight` | `Float` | `product_id.weight * quantity` |
| `volume` | `Float` | `product_id.volume * quantity` |
| `former_cost` | `Monetary` | Original SVL value before landed cost |
| `additional_landed_cost` | `Monetary` | Allocated landed cost amount |
| `final_cost` | `Monetary` | Computed: `former_cost + additional_landed_cost` |
| `currency_id` | `Many2one` | Company currency |

---

## Key Methods

### `get_valuation_lines()`

Returns the base valuation lines for all moves in `picking_ids`:

- Only includes moves where `product_id.cost_method` in `('fifo', 'average')` and `state != 'cancel'` and `quantity > 0`
- For each move, computes: `qty`, `former_cost`, `weight`, `volume`

Raises `UserError` if no valid lines found.

### `compute_landed_cost()`

Splits each cost line across all valuation adjustment lines:

| Split Method | Formula |
|---|---|
| `equal` | `line.price_unit / total_line_count` |
| `by_quantity` | `line.price_unit / total_qty * line.quantity` |
| `by_weight` | `line.price_unit / total_weight * line.weight` |
| `by_volume` | `line.price_unit / total_volume * line.volume` |
| `by_current_cost_price` | `line.price_unit / total_cost * line.former_cost` |

Creates `stock.valuation.adjustment.lines` records. Handles rounding differences by adding residual to the first line.

### `button_validate()`

**Workflow:**

1. Calls `compute_landed_cost()` if no valuation lines exist
2. Validates `_check_sum()` - cost line totals must match adjustment totals
3. For each adjustment line with a `move_id`:
   - Computes remaining_qty = SVL remaining_qty (prorated to what's still in stock)
   - cost_to_add = `remaining_qty / move_qty * additional_landed_cost`
   - Creates SVL with `value = cost_to_add` and `stock_landed_cost_id = self`
   - For lot-valued products, creates per-lot SVLs
   - Updates linked SVL's `remaining_value`
4. For average/FIFO products: updates `standard_price` of product and lots
5. Creates `account.move` with journal entries for real_time products
6. Calls `reconcile_landed_cost()` for Anglo-Saxon accounting
7. Sets state to `done`

### `reconcile_landed_cost()`

For companies with Anglo-Saxon accounting + vendor bill posted:
- Reconciles `vendor_bill_id.line_ids` with `account_move_id.line_ids` on the `stock_input` account

### `_check_sum()`

Validates:
- Sum of all `additional_landed_cost` in valuation lines == `amount_total`
- Sum of `additional_landed_cost` per cost line == that cost line's `price_unit`

---

## account.move Extension

**File:** `models/account_move.py`

| Field | Type | Description |
|---|---|---|
| `landed_costs_ids` | `One2many` | Linked `stock.landed.cost` records (reverse of `vendor_bill_id`) |
| `landed_costs_visible` | `Boolean` | Computed - True if any line is a landed costs line |

**Methods:**

- `button_create_landed_costs()` - Creates a `stock.landed.cost` from landed cost lines in the vendor bill:
  - `vendor_bill_id` = self
  - `cost_lines` from `line_ids` where `is_landed_costs_line = True`
  - `split_method` from `product_id.split_method_landed_cost`

- `action_view_landed_costs()` - Opens related landed costs

- `_post()` - Calls `reconcile_landed_cost()` on landed costs after posting

---

## account.move.line Extension

**File:** `models/account_move.py`

| Field | Type | Description |
|---|---|---|
| `product_type` | `Selection` | Related to `product_id.type` |
| `is_landed_costs_line` | `Boolean` | Set by `_update_order_line_info()` for landed cost products |

**Onchange:** `_onchange_product_id_landed_costs` sets `is_landed_costs_line = True` if `product_id.landed_cost_ok`

**Methods:**

- `_get_stock_valuation_layers()` - Excludes SVLs linked to a landed cost
- `_eligible_for_cogs()` - Returns True for landed cost service products with real_time valuation

---

## stock.valuation.layer Extension

**File:** `models/stock_valuation_layer.py`

| Field | Type | Description |
|---|---|---|
| `stock_landed_cost_id` | `Many2one` | Link back to the landed cost that created this SVL |

**Method:** `_should_impact_price_unit_receipt_value()` - Returns False if SVL has a landed cost linked, preventing double-counting of vendor bill valuation.

---

## Validation and Constraints

- `button_validate` raises `UserError` if:
  - Not in draft state
  - No targeted moves (`picking_ids` is empty)
  - `_check_sum()` fails (total mismatch)
- Validated landed costs cannot be cancelled; user must create a negative (reversal) landed cost instead
- Vendor bill must be posted before reconciliation occurs

---

## Accounting Entries

On validate, for each product with real_time valuation:

**Entry for goods still in stock:**
```
Debit:  Stock Valuation Account
Credit: Cost Line Account (e.g., Freight Expense)
```

**Entry for goods already consumed/sold:**
```
Debit:  COGS / Expense Account
Credit: Stock Valuation Account
```

The split between "in stock" and "already out" is computed based on SVL `remaining_qty`.

---

## Related Modules

| Module | Purpose |
|---|---|
| `project_stock_landed_costs` | Landed costs on project stock moves |
| `project_mrp_stock_landed_costs` | Landed costs on manufacturing stock moves |
| `mrp_subcontracting_landed_costs` | Landed costs for subcontracted production |