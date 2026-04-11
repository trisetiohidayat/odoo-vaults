---
Module: stock_landed_costs
Version: Odoo 18
Type: Integration
---

# Stock Landed Costs (`stock_landed_costs`)

Allocates extra costs (freight, insurance, customs, handling) to received goods. Landed costs are split across stock moves using configurable methods, updating product valuations and creating accounting entries.

**Depends:** `stock_account`, `purchase_stock`
**Category:** Inventory/Inventory
**Source:** `~/odoo/odoo18/odoo/addons/stock_landed_costs/`

---

## Models

### `stock.landed.cost` — Landed Cost Record

Central record. Represents a single landed cost document applied to one or more stock pickings.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Auto-generated sequence (e.g. `LC/00001`) |
| `date` | Date | Effective date of the landed cost |
| `target_model` | Selection | Always `'picking'` (Transfers) in Odoo 18 |
| `picking_ids` | Many2many | Stock pickings to which costs are applied |
| `cost_lines` | One2many | Individual cost component lines (`stock.landed.cost.lines`) |
| `valuation_adjustment_lines` | One2many | Computed per-product/per-move cost allocations |
| `description` | Text | Free-text description |
| `amount_total` | Monetary | Sum of all cost line `price_unit` values (computed) |
| `state` | Selection | `'draft'`, `'done'`, `'cancel'` |
| `account_move_id` | Many2one | Journal entry created on validation |
| `account_journal_id` | Many2one | Journal for the accounting entry |
| `vendor_bill_id` | Many2one | Source vendor bill (for auto-created costs) |
| `stock_valuation_layer_ids` | One2many | Valuation layers created from this cost |
| `company_id` | Many2one | Company |
| `currency_id` | Many2one | Related to `company_id.currency_id` |

#### Key Methods

**`compute_landed_cost()`** — Core computation. Generates `stock.valuation.adjustment.lines` records for each combination of cost line and stock move.

Algorithm:
1. Deletes existing valuation adjustment lines for this cost
2. Calls `get_valuation_lines()` to get all targeted moves with their weight/volume/qty
3. Creates one `stock.valuation.adjustment.lines` per cost line per valuation line
4. Computes `additional_landed_cost` per adjustment line using the cost line's `split_method`:
   - `equal`: `price_unit / total_lines`
   - `by_quantity`: `qty * (price_unit / total_qty)`
   - `by_weight`: `weight * (price_unit / total_weight)`
   - `by_volume`: `volume * (price_unit / total_volume)`
   - `by_current_cost_price`: `former_cost * (price_unit / total_former_cost)`
5. Rounds values and handles rounding diff (adds remainder to the first line)

**`get_valuation_lines()`** — Returns a list of dicts, one per stock move targeted by the pickings:
- `product_id`, `move_id`, `quantity` (in product's UoM), `former_cost` (sum of SVL values), `weight`, `volume`
- Skips cancelled moves and moves with zero quantity
- Skips products not using `'fifo'` or `'average'` cost method
- Raises `UserError` if no valid lines found

**`_get_targeted_move_ids()`** — Returns `stock.move` records from `picking_ids`.

**`_check_can_validate()`** — Validates that:
- All costs are in `draft` state
- At least one picking/move is targeted

**`_check_sum()`** — Validates accounting balance:
- Total of all `additional_landed_cost` equals `amount_total`
- Each cost line's total matches its `price_unit`
- Returns `False` if mismatched

**`button_validate()`** — Main validation action:
1. Checks can validate
2. Calls `compute_landed_cost()` if no adjustment lines exist
3. Checks sum
4. For each cost record:
   a. For each adjustment line with a move, creates `stock.valuation.layer` records
   b. Prorates the cost by remaining qty in stock (goods already sold get expensed)
   c. For lot-valuated products: creates per-lot SVL records and updates `remaining_value`
   d. For AVCO/FIFO products: updates `standard_price` on `product.product` (and per-lot `standard_price` if lot-valuated)
   e. Creates journal entry with debit (stock valuation) / credit (stock input or expense) lines
   f. Posts the journal entry
   g. Calls `reconcile_landed_cost()`

**`reconcile_landed_cost()`** — For vendor bills with Anglo-Saxon accounting enabled:
- Gets all AMLs from the vendor bill and the landed cost's journal entry
- Filters to `stock_input` account
- Reconciles them (calls `reconcile()` on the AMLs)

**`button_cancel()`** — Only allowed from `draft` state. Sets `state = 'cancel'`. Raises error if any cost is `done`.

**`action_view_stock_valuation_layers()`** — Opens the SVL list view filtered to this landed cost's layers.

#### L4 Notes

- `amount_total` is the sum of `cost_lines.price_unit`. It does NOT equal the sum of `additional_landed_cost` on adjustment lines until `compute_landed_cost()` is called.
- The `_check_sum()` method must pass before validation. If rounding causes a mismatch, rounding diffs are distributed to the first adjustment line.
- When products are partly out of stock, the landed cost is split: the portion of goods still in stock is added to SVL `remaining_value`; the portion already delivered is expensed via the journal entry.

---

### `stock.landed.cost.lines` — Cost Component Line

One line per landed cost type (freight, insurance, customs duty, etc.).

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Description |
| `cost_id` | Many2one | Parent `stock.landed.cost` |
| `product_id` | Many2one | Product representing this cost type |
| `price_unit` | Monetary | Amount of this cost line |
| `split_method` | Selection | How to divide this cost across products |
| `account_id` | Many2one | Credit account for journal entry (usually stock input) |
| `currency_id` | Many2one | Related from `cost_id.currency_id` |

#### Split Methods

| Value | Label | Formula |
|-------|-------|---------|
| `equal` | Equal | `price_unit / total_adjustment_lines` |
| `by_quantity` | By Quantity | `adj_line.qty * (price_unit / total_qty)` |
| `by_weight` | By Weight | `adj_line.weight * (price_unit / total_weight)` |
| `by_volume` | By Volume | `adj_line.volume * (price_unit / total_volume)` |
| `by_current_cost_price` | By Current Cost | `adj_line.former_cost * (price_unit / total_former_cost)` |

#### Key Methods

**`onchange_product_id()`** — Auto-fills:
- `name`: product's display name
- `split_method`: from product's `split_method_landed_cost` or `'equal'`
- `price_unit`: product's `standard_price`
- `account_id`: product's `stock_input` account

#### L4 Notes

- `split_method` is per-line. Different cost lines can use different split methods. For example, freight by weight, customs by value (current cost).
- The `account_id` is the credit account. For real-time valuation products, the debit goes to `stock_valuation` account; for manual valuation, no journal entry is created.

---

### `stock.valuation.adjustment.lines` — Valuation Adjustment Lines

Computed lines showing how each landed cost is allocated to each product/move.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Computed: `${cost_line.name} - ${product.display_name}` |
| `cost_id` | Many2one | Parent landed cost |
| `cost_line_id` | Many2one | Source cost line |
| `move_id` | Many2one | Target stock move |
| `product_id` | Many2one | Product being adjusted |
| `quantity` | Float | Quantity received (in product UoM) |
| `weight` | Float | `product.weight * quantity` |
| `volume` | Float | `product.volume * quantity` |
| `former_cost` | Monetary | Original cost from SVL (`value` from existing SVLs) |
| `additional_landed_cost` | Monetary | Cost allocated to this product/move |
| `final_cost` | Monetary | `former_cost + additional_landed_cost` (computed) |

#### Key Methods

**`_create_accounting_entries(move, qty_out)`** — Creates the journal entry lines for this adjustment:

**Debit side:**
- Product stock valuation account: `additional_landed_cost` (or pro-rated for `qty_out` already delivered)

**Credit side:**
- `cost_line_id.account_id` (stock input account)
- OR for dropshipped moves: expense account

**For Anglo-Saxon accounting (goods already out):**
- Additional debit to expense account
- Additional credit to stock output account

**`_prepare_account_move_line_values()`** — Base values dict: `name`, `product_id`, `quantity=0`.

**`_create_account_move_line(...)`** — Builds the command list for `account.move.line` creation.

---

### `stock.valuation.layer` (EXTENDED)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `stock_landed_cost_id` | Many2one | Landed cost that created this layer |

#### Key Methods

**`_should_impact_price_unit_receipt_value()`** — Returns `False` if the SVL is linked to a landed cost with a vendor bill. Prevents double-updating of product cost when landed costs come from a vendor bill.

#### L4 Notes

- When a landed cost is created from a vendor bill (via `button_create_landed_costs`), the vendor bill's posted move triggers `_update_price_unit_on_avg_methods` on the SVL. This method prevents that update if the SVL already came from a landed cost (which would double-update the price).
- SVLs created from landed costs have `stock_landed_cost_id` set. SVLs from the initial receipt do not.

---

### `stock.move` (EXTENDED)

#### Methods

**`_get_stock_valuation_layer_ids()`** — Returns the SVL IDs for this move. Used by landed cost computation to get the existing SVLs for `former_cost` calculation.

---

### `product.template` (EXTENDED)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `landed_cost_ok` | Boolean | Marks this product as a landed cost type |
| `split_method_landed_cost` | Selection | Default split method for this product when used in landed costs |

#### Key Methods

**`write(vals)`** — Constrains `landed_cost_ok`:
- Cannot disable `landed_cost_ok` if the product is used in any `account.move.line` with `is_landed_costs_line = True`
- Changing `type` from service to non-service clears `landed_cost_ok`

---

### `purchase.order.line` (EXTENDED)

#### Methods

**`_prepare_account_move_line(move=False)`** — Adds `is_landed_costs_line = product_id.landed_cost_ok` to the AML values. This propagates the landed cost flag to the vendor bill lines so they can be converted into landed cost records.

---

### `account.move` (EXTENDED — Vendor Bill Landed Cost Creation)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `landed_costs_ids` | One2many | `stock.landed.cost` records linked to this vendor bill |
| `landed_costs_visible` | Boolean | Compute: True if any AML has `is_landed_costs_line = True` |

#### Methods

**`button_create_landed_costs()`** — Creates a `stock.landed.cost` from vendor bill lines marked as landed costs:
- `vendor_bill_id` set to `self`
- One cost line per landed cost AML
- `price_unit` converted from bill currency to company currency
- `split_method` from product's `split_method_landed_cost` or `'equal'`
- `account_id` from product's `stock_input` account

**`_post(soft=True)`** — After posting, calls `reconcile_landed_cost()` on all linked landed costs.

**`_update_order_line_info(product_id, quantity, **kwargs)`** — When vendor bill line is updated, sets `is_landed_costs_line` from product's `landed_cost_ok`.

---

### `account.move.line` (EXTENDED)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `product_type` | Selection | Related: `product_id.type` |
| `is_landed_costs_line` | Boolean | This line represents a landed cost product |

#### Methods

**`_onchange_product_id_landed_costs()`** — Sets `is_landed_costs_line = True` if the product has `landed_cost_ok = True`.

**`_onchange_is_landed_costs_line()`** — Forces `is_landed_costs_line = False` if the product type is not `'service'`. Landed cost products must be services.

**`_get_stock_valuation_layers(move)`** — Filters out SVLs that belong to a landed cost. Prevents duplicate valuation from landed cost SVLs.

**`_eligible_for_cogs()`** — Extended: service products with `landed_cost_ok = True` and real-time valuation are eligible for COGS recognition.

---

### `res.company` (EXTENDED)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `lc_journal_id` | Many2one | Default journal for landed cost journal entries |

---

### `res.config.settings` (EXTENDED)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `lc_journal_id` | Many2one | Default landed cost journal (related to company) |

---

## Landed Cost Valuation Flow

```
1. Vendor bills goods → vendor bill lines with landed cost products
                            ↓
2. User clicks "Create Landed Costs" on vendor bill
                            ↓
3. stock.landed.cost created with:
   - vendor_bill_id = vendor bill
   - cost_lines from landed cost AMLs
   - picking_ids = open receipts for same products
                            ↓
4. User clicks "Validate" (button_validate)
                            ↓
5. compute_landed_cost() generates adjustment lines
   └─ Per split_method: equal / by_quantity / by_weight / by_volume / by_current_cost_price
                            ↓
6. button_validate() creates:
   a. stock.valuation.layer records
      └─ Updates remaining_value on linked SVLs
      └─ For AVCO: updates product.standard_price
      └─ For FIFO: remaining_value updated, future receipts priced correctly
   b. account.move (journal entry):
      Debit:  stock_valuation account (or expense if qty_out > 0)
      Credit: stock_input account (from cost_line.account_id)
                            ↓
7. reconcile_landed_cost()
   └─ Vendor bill AMLs reconciled with landed cost journal entry AMLs
                            ↓
8. Product standard_price updated
   └─ Future receipts priced at new average cost
```

---

## Valuation Impact by Cost Method

| Cost Method | Effect of Landed Cost |
|-------------|----------------------|
| `fifo` | `remaining_value` of SVL increases; cost of next moves correct |
| `average` | `standard_price` increases (batch update); future receipts average |
| `standard` | No automatic update (manual) |
| `manual` | No journal entry created |

## Landed Cost Journal Entry (Real-Time Valuation)

For a landed cost `LC` applied to a receipt of product `P`:

```
Journal: Landed Cost Journal
Date: cost.date

Debit  |  Stock Valuation (P)     |  LC_amount_remaining_in_stock
Credit |  Stock Input (LC product)|  LC_amount_remaining_in_stock

[If some qty already delivered:]
Debit  |  Expense (COGS)          |  LC_amount_already_sold
Credit |  Stock Output (P)        |  LC_amount_already_sold

[Anglo-Saxon additional entries:]
Debit  |  Expense (P)             |  LC_amount_already_sold
Credit |  Stock Output (P)         |  LC_amount_already_sold
```

## Key Constraints

- Products must use `fifo` or `average` cost method
- `landed_cost_ok` products must be of type `service`
- `stock_input` account must be configured on the product's category
- `stock_valuation` account must allow SVL creation
- Only `draft` landed costs can be cancelled

---

**Tags:** `#stock_landed_costs` `#landed_costs` `#product_valuation` `#split_method` `#average_cost` `#fifo`
