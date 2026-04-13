---
type: module
module: stock_landed_costs
tags: [odoo, odoo19, stock, account, landed, costs, valuation, stock_valuation]
created: 2026-04-11
---

# WMS Landed Costs

## Overview

| Property | Value |
|----------|-------|
| **Name** | WMS Landed Costs |
| **Technical** | `stock_landed_costs` |
| **Category** | Supply Chain/Inventory |
| **Version** | 1.1 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Odoo Version** | 19.0 |

## Description

The `stock_landed_costs` module allows you to **allocate extra costs** (freight, insurance, customs duties, handling fees) onto received stock pickings and incorporate those costs into **product stock valuation**. When a landed cost is validated, Odoo automatically creates accounting entries to move the cost from an expense account into the stock valuation account, effectively increasing the cost of the received goods.

This is essential for accurate COGS calculation: goods received at $100 with $15 freight should be valued at $115 per unit for inventory purposes.

## Dependencies

```
stock_landed_costs
    ├── stock_account      (real-time stock valuation)
    └── purchase_stock     (receipt-to-purchase integration)
```

Requires **real-time stock valuation** (`product.valuation = "real_time"`) and **FIFO or Average costing method** on products.

## Core Business Flow

1. **Goods received** via a stock.picking (incoming receipt)
2. **Vendor invoice** arrives with additional charges (freight, duty, insurance)
3. **Landed Cost created** via:
   - Manual creation from Inventory > Valuation > Landed Costs
   - Or from a vendor bill: select invoice lines marked as "Landed Cost", click "Create Landed Costs"
4. **Cost lines added** -- one per cost type (e.g., Freight, Insurance, Duty)
5. **Validate** -- Odoo computes the allocation per stock move, creates accounting entries, updates `standard_price` for affected products
6. **Stock valuation increases** -- the received goods' valuation now includes the landed costs

## Key Concepts

### Five Split Methods

When allocating a cost across multiple stock moves (i.e., multiple products received), the module supports five allocation algorithms:

| Method | Formula | Use Case |
|--------|---------|----------|
| `equal` | `cost / total_lines` | One flat fee shared equally |
| `by_quantity` | `cost / total_qty * line_qty` | Per-unit freight |
| `by_weight` | `cost / total_weight * line_weight` | Weight-based shipping |
| `by_volume` | `cost / total_volume * line_volume` | Volume-based shipping |
| `by_current_cost_price` | `cost / total_former_cost * line_former_cost` | Proportional to product cost |

### Valuation Adjustment Lines

For every pair of (stock move, cost line), a `stock.valuation.adjustment.lines` record is created. Each line carries:
- The original move cost (`former_cost`)
- The allocated additional cost (`additional_landed_cost`)
- The new value (`final_cost = former_cost + additional_landed_cost`)

### Only Real-Time Valuation Products

Accounting entries are **only created for products with `valuation = "real_time"`**. Products using manual or phantom valuation are skipped silently during validation.

### Rounding and Rounding Diffs

Costs are split using `tools.float_round(value, rounding_method='HALF-UP')`. Any residual rounding difference (due to division) is added to the last valuation line to ensure the total exactly matches the cost.

## Models

### `stock.landed.cost` (Primary Model)

**File:** `models/stock_landed_cost.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Auto-generated from sequence `stock.landed.cost`, format `LC/YYYY/NNNN` |
| `date` | Date | Cost date (default: today) |
| `target_model` | Selection | Currently only `picking` (Transfers). Extensible for future models |
| `picking_ids` | Many2many `stock.picking` | Receipt pickings to apply costs to |
| `cost_lines` | One2many `stock.landed.cost.lines` | Individual cost items (Freight, Duty, Insurance, etc.) |
| `valuation_adjustment_lines` | One2many `stock.valuation.adjustment.lines` | Computed per (move, cost_line) pair |
| `description` | Text | Internal notes |
| `amount_total` | Monetary | Sum of all `cost_lines.price_unit` (computed, stored) |
| `state` | Selection | `draft` -> `done` -> `cancel` |
| `account_move_id` | Many2one `account.move` | Generated journal entry (index: btree_not_null) |
| `account_journal_id` | Many2one | Journal for the accounting entry (default: `company.lc_journal_id` or stock journal fallback) |
| `company_id` | Many2one `res.company` | Company |
| `vendor_bill_id` | Many2one `account.move` | Linked vendor bill (domain: `move_type = in_invoice`) |
| `currency_id` | Many2one | Related from `company_id.currency_id` |

#### State Machine

```
draft ──[button_validate()]──→ done
  │
  └──[button_cancel()]──→ cancel
```

Only `draft` landed costs can be validated. Validated costs cannot be cancelled; instead, create a negative correcting landed cost.

#### Key Methods

| Method | Description |
|--------|-------------|
| `create()` | Auto-generates name via `ir.sequence` |
| `button_validate()` | Main validation entry point |
| `button_cancel()` | Cancels draft-only landed costs |
| `compute_landed_cost()` | Builds valuation adjustment lines by iterating moves and cost lines |
| `get_valuation_lines()` | Returns list of `{product_id, move_id, qty, former_cost, weight, volume}` per stock move |
| `_get_targeted_move_ids()` | Returns `picking_ids.move_ids` (can be overridden for other target models) |
| `_check_can_validate()` | Ensures state=draft and has targeted moves |
| `_check_sum()` | Validates total of all `additional_landed_cost` equals `amount_total` |

#### `button_validate()` -- Validation Flow

1. **Check state and moves** via `_check_can_validate()`
2. **Compute adjustment lines** -- if not already present, call `compute_landed_cost()`
3. **Validate totals** via `_check_sum()` -- raises `UserError` if mismatched
4. **For each landed cost:**
   - Create `account.move` with journal entries for real-time products
   - Credit: expense account (from cost line's `account_id`)
   - Debit: stock valuation account (from product's `stock_valuation` account)
   - Post the move
   - Update valuation layer values via `move_id._set_value()`
5. Update state to `done`, link the `account_move_id`

#### `compute_landed_cost()` -- Allocation Algorithm

```
For each cost:
  For each stock move in pickings:
    create valuation_adjustment_line with qty, former_cost, weight, volume
    accumulate totals: total_qty, total_weight, total_volume, total_cost

  For each cost_line:
    For each valuation_adjustment_line:
      switch split_method:
        equal:       value = price_unit / total_lines
        by_quantity: value = (price_unit / total_qty) * line_qty
        by_weight:   value = (price_unit / total_weight) * line_weight
        by_volume:   value = (price_unit / total_volume) * line_volume
        by_current_cost_price: value = (price_unit / total_cost) * line_former_cost
    apply rounding, distribute rounding diff to last line
```

### `stock.landed.cost.lines`

**File:** `models/stock_landed_cost.py`

Represents one cost item within a landed cost (e.g., Freight $50, Customs Duty $120).

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Description (auto-set from product on `onchange_product_id`) |
| `cost_id` | Many2one | Parent `stock.landed.cost` |
| `product_id` | Many2one `product.product` | Service product (landed_cost_ok=True) |
| `price_unit` | Monetary | Cost amount |
| `split_method` | Selection | Allocation algorithm (from product template default or manual) |
| `account_id` | Many2one `account.account` | Expense account for the credit side |
| `currency_id` | Many2one | Related from `cost_id` |

#### `onchange_product_id()`

When a product is selected, this auto-fills:
- `name` from product name
- `split_method` from `product.product_tmpl_id.split_method_landed_cost` (falls back to existing value or `'equal'`)
- `price_unit` from product's `standard_price`
- `account_id` from product template's expense account via `get_product_accounts()['expense']`

### `stock.valuation.adjustment.lines`

**File:** `models/stock_landed_cost.py`

The working table for cost allocation. One record per (stock move, cost line) combination.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Computed: `{cost_line.name} - {product.code or product.name}` |
| `cost_id` | Many2one | Parent landed cost |
| `cost_line_id` | Many2one | Source cost line |
| `move_id` | Many2one `stock.move` | The stock move this adjustment applies to |
| `product_id` | Many2one `product.product` | Product |
| `quantity` | Float | Move quantity in product UOM |
| `weight` | Float | `quantity * product.weight` |
| `volume` | Float | `quantity * product.volume` |
| `former_cost` | Monetary | Original move value before landed cost |
| `additional_landed_cost` | Monetary | Allocated cost from this landed cost |
| `final_cost` | Monetary | `former_cost + additional_landed_cost` (computed, stored) |

#### `final_cost` Computation

```python
@api.depends('former_cost', 'additional_landed_cost')
def _compute_final_cost(self):
    for line in self:
        line.final_cost = line.former_cost + line.additional_landed_cost
```

#### `_create_accounting_entries(remaining_qty)`

For each valuation line targeting a real-time product:

1. Get `stock_valuation` account from product template
2. Get `expense` account from cost line's product or the landed cost product
3. Build journal entry lines:
   - **Debit**: `stock_valuation` account (or reversed for negative costs)
   - **Credit**: `expense` account (or reversed for negative costs)
4. `quantity=0` on both lines (landed cost entries are non-inventory)

The `remaining_qty` parameter handles partial receipts: `diff = additional_landed_cost * (remaining_qty / quantity)`.

### `product.template` (Extension)

**File:** `models/product.py`

| Field | Type | Description |
|-------|------|-------------|
| `landed_cost_ok` | Boolean | Marks this product as a landed cost service (appears in "Landed Costs" section on vendor bills) |
| `split_method_landed_cost` | Selection | Default split method when this product is used as a landed cost |

#### Constraint on `landed_cost_ok`

Changing `landed_cost_ok` to `False` or changing `type` away from `service` is blocked if the product has been used in any `is_landed_costs_line` account move line:

```python
if product.type == 'service' and product.landed_cost_ok:
    if self.env['account.move.line'].search_count([('product_id', 'in', product.product_variant_ids.ids),
                                                    ('is_landed_costs_line', '=', True)]):
        raise UserError(_("You cannot change the product type or disable landed cost option because the product is used in an account move line."))
```

### `account.move` (Extension)

**File:** `models/account_move.py`

| Field | Type | Description |
|-------|------|-------------|
| `landed_costs_ids` | One2many `stock.landed.cost` | Linked via `vendor_bill_id` |
| `landed_costs_visible` | Boolean (computed) | True if landed costs can be created from this invoice |

#### `button_create_landed_costs()`

Creates a `stock.landed.cost` from invoice lines marked as `is_landed_costs_line=True`. Each such line becomes one cost line in the landed cost, with:
- `product_id` from invoice line
- `price_unit` converted to company currency (with sign flip for refunds: `-1`)
- `split_method` from product
- `account_id` from the product's stock valuation account

#### `landed_costs_visible` Computation

```python
if landed_costs_ids: visible = False  # already linked
else: visible = any(line.is_landed_costs_line for line in line_ids)
```

### `account.move.line` (Extension)

**File:** `models/account_move.py`

| Field | Type | Description |
|-------|------|-------------|
| `is_landed_costs_line` | Boolean | Marks this line as a landed cost service on a vendor bill |

#### `_onchange_product_id_landed_costs()`

Auto-sets `is_landed_costs_line = True` when the selected product has `landed_cost_ok = True`.

#### `_onchange_is_landed_costs_line()`

Protects against mis-selection: if a user manually checks `is_landed_costs_line` but the product type is not `service`, the flag is reset to `False`.

#### `_eligible_for_stock_account()`

Extended to return `True` for service products that are landed costs AND have real-time valuation. This allows landed cost service products to create stock journal entries.

### `purchase.order.line` (Extension)

**File:** `models/purchase.py`

| Method | Description |
|--------|-------------|
| `_prepare_account_move_line()` | Adds `is_landed_costs_line = product_id.landed_cost_ok` to the generated vendor bill line values |

### `stock.move` (Extension)

**File:** `models/stock_move.py`

| Method | Description |
|--------|-------------|
| `_get_landed_cost(at_date)` | Returns all done `stock.valuation.adjustment.lines` for this move, optionally filtered by date |
| `_get_value_from_extra()` | Overrides parent to add landed cost value to the move's accounting data. Appends a description line listing the landed costs and their vendor bills |

## Accounting Entries: Double-Entry Detail

When `button_validate()` creates an `account.move`:

| Line | Account | Debit | Credit |
|------|---------|-------|--------|
| 1 | Stock Valuation (`stock_valuation` from product) | X | |
| 2 | Expense/Stock Expense (`account_id` from cost line) | | X |

For **negative costs** (corrections/reversals), the entry is reversed:
- Debit the expense account
- Credit the stock valuation account

Both lines use `quantity = 0` because landed cost entries are **non-inventory journal entries**.

## Product Valuation Impact

When a landed cost is validated:

1. The `additional_landed_cost` on each valuation line is added to the product's `standard_price` (for average/fifo products)
2. New `stock.valuation.layer` records are created with the increased value
3. The product's average cost or FIFO layers now reflect the true landed cost

This means future deliveries of the same product will use the updated cost basis.

## Configuration

| Setting | Location | Description |
|---------|----------|-------------|
| Default LC Journal | Settings > Inventory > Landed Costs > Default Journal | Journal used for LC accounting entries, stored on `res.company.lc_journal_id` |
| Landed Cost Product | Create a product of type "Service" with `landed_cost_ok = True` | Used as the cost line product |
| Split Method | Product Template or manual per cost line | Default allocation algorithm |
| Expense Account | Per cost line product | Credited when LC is validated |

### Journal Default Fallback Chain

When no journal is configured on the landed cost, `_default_account_journal_id()` resolves in this order:

1. `self.env.company.lc_journal_id` (dedicated landed cost journal on the company)
2. Falls back to `product.category.property_stock_journal` (the general stock journal)

This means a company does not need to configure a dedicated LC journal; the stock journal is always a valid fallback.

## Data Files

| File | Purpose |
|------|---------|
| `security/ir.model.access.csv` | ACL for landed cost models |
| `security/stock_landed_cost_security.xml` | Record rules |
| `data/stock_landed_cost_data.xml` | Sequence `stock.landed.cost` prefix `LC/YYYY/` |
| `views/account_move_views.xml` | "Create Landed Costs" button, "Landed Costs" smart button |
| `views/product_views.xml` | `landed_cost_ok` and `split_method_landed_cost` fields |
| `views/stock_landed_cost_views.xml` | Form, list, kanban views for landed costs |
| `views/res_config_settings_views.xml` | Default LC journal setting |

---

## L4: Depth Escalation

### Performance Implications

#### `compute_landed_cost()` -- Deletion/Recreation Pattern

```python
AdjustementLines.search([('cost_id', 'in', self.ids)]).unlink()
```

This is called **every time** `button_validate()` runs, even if adjustment lines already exist from a prior manual "Compute" press. The `unlink()` is batched (single SQL DELETE) but Odoo's ORM still prefetches and invalidates caches for all affected records. For landed costs with hundreds of stock moves and multiple cost lines, the N×M number of `stock.valuation.adjustment.lines` records created in the subsequent loop can become significant.

**Mitigation**: Always click "Compute" manually before validating if working with large pickings -- the recomputation on validate is idempotent but not free.

#### Record-by-Record `create()` in a Loop

```python
for val_line_values in all_val_line_values:
    for cost_line in cost.cost_lines:
        val_line_values.update({'cost_id': cost.id, 'cost_line_id': cost_line.id})
        self.env['stock.valuation.adjustment.lines'].create(val_line_values)
```

This creates N×M records via individual ORM `create()` calls. For M cost lines and N valuation lines, this means M×N SQL INSERTs. There is no `create_batch` call here. With large receipts (e.g., 50 line items × 4 cost types = 200 adjustment lines), this is a measurable round-trip. Odoo's ORM does prefetch IDs across the loop, but the SQL cost scales linearly with the product of moves and cost lines.

#### `_get_landed_cost()` Uses Efficient `_read_group`

```python
landed_cost_group = self.env['stock.valuation.adjustment.lines']._read_group(
    domain, ['move_id'], ['id:recordset'])
```

This is the correct pattern -- group-by on the database side rather than iterating in Python. The returned dict maps `move_id` to a recordset, so downstream code gets fully-loaded records in one query. Performance here is acceptable even for large move sets.

#### `button_validate()` Posts All Moves Upfront, Then Calls `_post()`

```python
move = move.create(move_vals)
cost_vals.update({'account_move_id': move.id})
cost.write(cost_vals)
if cost.account_move_id:
    move._post()
```

The `_post()` call is synchronous and performs balance checking, tax recomputation, and write locking on the move. For landed costs with many real-time valuation products (each generating two lines in `line_ids`), the posting phase is the dominant cost. Plan for this when validating landed costs with large picking sets.

#### `remaining_qty` from `stock.move`

The `remaining_qty` is read from each stock move at validation time:

```python
remaining_qty = line.move_id.remaining_qty
```

`remaining_qty` on `stock.move` is a computed field that reflects how much of the move's quantity has already been valued. It can be 0 for fully-valued moves or negative in edge cases (delivery of goods not fully received). This read is not cached at the time `compute_landed_cost()` runs, so it reflects the current state at the moment of validation.

---

### Odoo 18 to Odoo 19 Changes

#### New in Odoo 19: `by_current_cost_price` Split Method

The `by_current_cost_price` split method was introduced in Odoo 19. It allocates landed costs **proportionally to each product's current unit cost** (the `standard_price` or FIFO layer value at time of receipt). This is distinct from `by_quantity` (equal per unit regardless of unit price) and gives a more accurate cost allocation for heterogeneous product mixes where expensive items should bear a proportionally larger share of freight/duty.

```python
elif line.split_method == 'by_current_cost_price' and total_cost:
    per_unit = (line.price_unit / total_cost)
    value = valuation.former_cost * per_unit
```

`total_cost` here is the sum of all `former_cost` values across all valuation lines, already rounded per currency.

#### New in Odoo 19: `vendor_bill_id` and Landed Cost from Invoice Flow

In Odoo 18, landed costs were created entirely manually and linked to pickings. Odoo 19 introduced `vendor_bill_id` on `stock.landed.cost` and the `button_create_landed_costs()` action on `account.move`. This creates a direct traceability path from vendor bill lines to landed cost records.

#### New in Odoo 19: `stock.move._get_landed_cost()` and `_get_value_from_extra()`

These methods on `stock.move` are new in Odoo 19. They expose landed cost information from the move side, enabling the valuation layer to report the landed cost contribution per move. Previously, the only way to trace landed costs back to moves was through the `stock.valuation.adjustment.lines` recordset.

#### New in Odoo 19: `account.move.landed_costs_ids` and `landed_costs_visible`

These fields and the "Create Landed Costs" button on vendor bill forms are new in Odoo 19, replacing a more manual workflow.

#### New in Odoo 19: `remaining_qty` Parameter in Accounting Entry Creation

The `remaining_qty` parameter was already present in Odoo 18 but its use in `_create_accounting_entries()` became more significant in Odoo 19 as the `_get_value_from_extra()` chain started using it for prorated landed cost reporting.

#### Continuity: `is_landed_costs_line` on `account.move.line`

The `is_landed_costs_line` field was introduced in earlier versions and is continued in Odoo 19. The Odoo 18→19 evolution adds the onchange protection `_onchange_is_landed_costs_line()` that prevents non-service products from being marked as landed cost lines.

---

### Security Considerations

#### ACL Design: Stock Manager Only

All three landed cost models use `stock.group_stock_manager` as the sole permitted group for all four permissions (read, write, create, unlink):

```
stock.landed.cost              --> stock.group_stock_manager  (full)
stock.landed.cost.lines        --> stock.group_stock_manager  (full)
stock.valuation.adjustment.lines --> stock.group_stock_manager (full)
```

This is correct because landed cost validation creates real accounting entries. A user who can validate a landed cost can, by misconfiguration of cost line `account_id`, credit any expense account and debit any stock valuation account. The power of the Stock Manager role is warranted here.

#### Multi-Company Record Rule

```xml
<field name="domain_force">[('company_id', 'in', company_ids)]</field>
```

Standard Odoo multi-company rule. Landed costs are scoped to a single company (no `company_id` on pickings means they inherit from the picking). Users can only see landed costs for companies they belong to. This rule is defined as `noupdate="1"` so it is not overwritten on module upgrades.

#### ACLs Do Not Cover Product Template Extension

The ACL CSV only covers the three explicit landed cost models. The `product.template` extension (adding `landed_cost_ok` and `split_method_landed_cost`) is governed by the existing `product.template` ACLs. A user with write access to product templates can enable `landed_cost_ok` on any service product, but cannot validate landed costs without Stock Manager rights.

#### Write Protection After Validation

Once `state = 'done'`, the landed cost is effectively locked:
- `date` becomes read-only in the form view
- `picking_ids` becomes read-only
- `cost_lines` becomes read-only
- `account_journal_id` becomes read-only

The `button_cancel()` method additionally raises an error if any cost in `self` has `state == 'done'`. There is no `write` protection via ir.rule -- a Stock Manager with direct SQL access could theoretically modify a done landed cost. In practice, the ORM buttons enforce the lock.

#### `_eligible_for_stock_account()` -- Service Product Stock Entries

```python
def _eligible_for_stock_account(self):
    return super()._eligible_for_stock_account() or (
        self.product_id.type == "service"
        and self.product_id.landed_cost_ok
        and self.product_id.valuation == "real_time"
    )
```

This extension allows service products marked as landed costs to go through the stock journal (create stock-style accounting entries). Without this, landed cost service products would bypass the stock valuation account. The triple condition (service + landed_cost_ok + real_time) ensures only genuine landed cost services get this treatment.

#### `write()` Constraint on Product Template

The `write()` override on `product.template` is a data-integrity constraint disguised as a business rule. It prevents disabling `landed_cost_ok` on a product that has already been used in a landed cost journal entry:

```python
if self.env['account.move.line'].search_count([('product_id', 'in', product.product_variant_ids.ids),
                                                ('is_landed_costs_line', '=', True)]):
    raise UserError(_("You cannot change the product type or disable landed cost option..."))
```

This is an O(1) indexed search on `product_id` + `is_landed_costs_line`. It does not check whether the linked landed cost is still in draft state -- any historical usage locks the product configuration permanently.

---

### Edge Cases

#### Empty Pickings / Zero Quantity Moves

```python
if move.state == 'cancel' or not move.quantity:
    continue
```

Moves with `quantity = 0` (e.g., a picking confirmed with no qty done, or partially processed moves where the remaining qty is zero) are silently skipped. This means landed costs allocated to a picking with zero-received quantity contribute nothing.

#### Cancelled Moves

Cancelled moves (`state == 'cancel'`) are skipped in `get_valuation_lines()`. If a picking is cancelled after a landed cost is created but before validation, the validation will raise `UserError` via `_check_can_validate()` because there are no targeted moves remaining.

#### Products Not Using Real-Time Valuation

```python
if product.valuation != "real_time":
    continue
```

Products with `valuation = 'manual'` or `valuation = 'phantom'` are silently skipped in `button_validate()`. No accounting entry is created for them, and their valuation is not updated. This means manual-valuation companies get the landed cost information in the valuation adjustment lines for reference but no automatic accounting action.

#### Negative `remaining_qty` -- Delivered Products Not Originally Received

```python
remaining_qty = line.move_id.remaining_qty
diff = self.additional_landed_cost * (remaining_qty / self.quantity)
if diff > 0:
    debit_line['debit'] = diff
    credit_line['credit'] = diff
else:
    # negative cost, reverse the entry
    debit_line['credit'] = -diff
    credit_line['debit'] = -diff
```

If `remaining_qty` is negative (the move is an outgoing delivery of products that were not in stock at receipt time), the `diff` becomes negative and the journal entry is reversed. This handles the edge case of landed costs applied to moves representing negative stock (e.g., dropshipped goods tracked through receipts but consumed before valuation). This scenario is rare but the reversal logic is correct and necessary for integrity.

#### Vendor Refunds (`in_refund`) Sign Handling

```python
sign = -1 if self.move_type in ['in_refund'] else 1
...
'price_unit': sign * l.currency_id._convert(...)
```

When creating a landed cost from a vendor credit note (refund), the `price_unit` is negated. This means a refund of $50 freight creates a landed cost line of -$50, which when validated produces a negative journal entry that reverses the original landed cost's accounting impact. This correctly matches the accounting reality of the refund.

#### Vendor Bill Already Has Landed Costs

```python
if account_move.landed_costs_ids:
    account_move.landed_costs_visible = False
```

If a vendor bill already has linked landed costs (via `vendor_bill_id`), the "Create Landed Costs" button is hidden. This prevents double-allocation. The reverse direction is also protected: once a landed cost has a `vendor_bill_id`, changing the vendor bill on the landed cost is not explicitly blocked but would create an inconsistent state.

#### `_check_sum()` Rounding Tolerance

```python
if not landed_cost.currency_id.is_zero(total_amount - landed_cost.amount_total):
    return False
```

The sum check uses `currency_id.is_zero()` which applies the currency's rounding precision. If the total rounding difference across all lines is within one subunit of the currency (e.g., $0.001 for USD), the check passes. This prevents spurious rejection of valid landed costs due to floating-point accumulation.

#### Rounding Diff Distribution to Last Line

```python
rounding_diff = cost.currency_id.round(line.price_unit - value_split)
if not cost.currency_id.is_zero(rounding_diff):
    towrite_dict[max(towrite_dict.keys())] += rounding_diff
```

After computing the allocated value for each valuation line, the accumulated `value_split` may differ from `line.price_unit` by a small amount due to floating-point division. The difference is added to the last valuation line (identified by `max(towrite_dict.keys())`, which is the highest ID in the set of lines for this cost line). This ensures that when all lines are summed, they exactly equal `line.price_unit`.

**Edge case**: If `towrite_dict` is empty (no valuation lines for this cost line), `max()` would raise a `ValueError`. However, `get_valuation_lines()` would have already raised a `UserError` in this case, so this code path is never reached during normal operation.

#### In-Refund Landed Cost on Non-Refund Vendor Bill

The `button_create_landed_costs()` uses `move_type` to determine the sign, but there is no validation preventing a landed cost created manually (not from invoice) from being validated with a different accounting impact. The sign is only applied when creating from a refund. Manual landed costs always use positive `price_unit`.

#### No Expense Account Configured

```python
if not credit_account_id:
    raise UserError(_('Please configure Stock Expense Account for product: %s.', cost_product.name))
```

If a cost line's product has no expense account configured (neither on the cost line `account_id` nor via `cost_product._get_product_accounts()['expense']`), validation raises a `UserError`. This is a blocking validation that prevents posting an unbalanced entry.

#### Domain Filter on `picking_ids` in Form View

```xml
domain="[('company_id', '=', company_id), '|', ('move_ids.is_in', '!=', False), ('move_ids.is_out', '!=', False)]"
```

In the form view, the picking selector only shows pickings that have either incoming or outgoing moves. This is a UX filter -- it prevents selecting pickings with only internal moves (which have no valuation impact). Empty pickings or purely internal transfers are excluded from the selector.

---

### Architecture Notes

#### Target Model Extensibility

The `target_model` field on `stock.landed.cost` is a selection that currently only offers `picking`. The `_get_targeted_move_ids()` method is designed to be overridden so other document types (e.g., manufacturing orders) can support landed costs in the future. The `targeted_move_ids` method is the single integration point.

#### Why `stock_valuation` from Product, Not Cost Line

The debit side of the landed cost journal entry uses the **receiving product's** `stock_valuation` account, not the cost line's expense account. This correctly increases the value of the received inventory.

The **credit side** uses the cost line's `account_id` (expense), which moves the cost from an expense account into inventory value.

#### Roundtrip Through `purchase.order.line`

When a vendor bill line with `is_landed_costs_line=True` is created from a purchase order line, `_prepare_account_move_line()` on `purchase.order.line` copies `is_landed_costs_line = product_id.landed_cost_ok` into the invoice line.

#### Sequence is Per-Company

```xml
<field name="company_id" eval="False"/>
```

The `ir.sequence` for landed costs has no company绑定 (`company_id = False`), meaning it generates a globally unique sequence across all companies. This is unusual -- most inventory sequences are per-company. If multiple companies generate landed costs in the same year, the sequence numbers could collide visually (though the internal ID is unique). The `LC/YYYY/NNNN` format mitigates year collisions.

---

## Related

- [Modules/stock_account](stock_account.md) -- Real-time stock valuation layer
- [Modules/purchase_stock](purchase_stock.md) -- Receipt integration with purchases
- [Modules/Stock](Stock.md) -- Base warehouse and inventory
- [Modules/mrp_landed_costs](mrp_landed_costs.md) -- Manufacturing landed costs
- [Modules/project_stock_landed_costs](project_stock_landed_costs.md) -- Project-landed cost integration
