---
tags: [odoo, odoo17, module, stock_account, valuation]
research_depth: medium
---

# Stock Account Module — Deep Reference

**Source:** `addons/stock_account/models/`

## Overview

Links inventory valuation movements to accounting journal entries. When a `stock.move` is validated (`_action_done`), this module creates `stock.valuation.layer` records and, for real-time valuation, auto-posts `account.move` entries debiting the stock valuation account and crediting the stock input/output account. Required for **automated (real-time) inventory valuation**.

Also implements **Anglo-Saxon accounting**: additional COGS journal entries are generated when customer invoices are posted, with an interim stock account used for reconciliation.

## Files

| File | Class Extended | Purpose |
|------|---------------|---------|
| `stock_valuation_layer.py` | `stock.valuation.layer` | Valuation layer model + accounting entry validation |
| `account_move.py` | `account.move`, `account.move.line` | COGS lines for Anglo-Saxon, stock move links |
| `product.py` | `product.template`, `product.product` | Valuation/cost method changes with stock replenishment |
| `stock_move.py` | `stock.move` | SVL creation, `_account_entry_move`, `_action_done` override |
| `stock_move_line.py` | `stock.move.line` | Excludes tracked lot/serial from valuation |
| `stock_location.py` | `stock.location` | Location-level stock accounts |
| `stock_quant.py` | `stock.quant` | Quant-level valuation adjustments |

## Key Models

### stock.valuation.layer

The core record of inventory valuation. Every stock movement that changes quantity creates one or more SVLs.

#### Fields
| Field | Type | Description |
|-------|------|-------------|
| `product_id` | Many2one | Product being valued |
| `quantity` | Float | Quantity (positive=in, negative=out) |
| `value` | Monetary | Total valuation change |
| `unit_cost` | Float | Cost per unit |
| `remaining_qty` | Float | Qty remaining after this layer (AVCO/FIFO) |
| `remaining_value` | Monetary | Value remaining |
| `stock_move_id` | Many2one | Source `stock.move` |
| `account_move_id` | Many2one | Generated `account.move` |
| `account_move_line_id` | Many2one | Invoice line linked (for price diff corrections) |
| `stock_valuation_layer_id` | Many2one | Parent SVL (for price corrections) |
| `stock_valuation_layer_ids` | One2many | Child SVLs from price corrections |
| `price_diff_value` | Float | Invoice currency correction |
| `warehouse_id` | Many2one | Receipt warehouse (computed) |

#### Methods
| Method | Purpose |
|--------|---------|
| `_validate_accounting_entries()` | Creates + posts `account.move` for real-time valuation |
| `_validate_analytic_accounting_entries()` | Creates `account.analytic.line` from stock moves |
| `_consume_specific_qty()` | FIFO: consumes specific SVL layers up to qty |
| `_consume_all()` | Consumes all SVL to get avg cost for a qty |

### stock.move (Extended)

#### Fields Added
| Field | Type | Description |
|-------|------|-------------|
| `account_move_ids` | One2many | Journal entries created by this move |
| `stock_valuation_layer_ids` | One2many | Valuation layers from this move |
| `analytic_account_line_ids` | Many2many | Analytic lines from this move |
| `to_refund` | Boolean | Trigger qty decrease on linked SO/PO |

#### Valuation Entry Flow (`_action_done`)

```
stock.move._action_done()
  1. Build valued_moves dict by valued_type (in/out/dropshipped/dropshipped_returned)
  2. AVCO: product_price_update_before_done() → update standard_price
  3. super()._action_done()
  4. _create_<type>_svl() → creates stock.valuation.layer records (sudo)
  5. SVL._validate_accounting_entries() → posts account.move per layer
  6. SVL._validate_analytic_accounting_entries() → creates analytic lines
  7. product._run_fifo_vacuum() → reconcile closed FIFO layers
```

#### `_account_entry_move(qty, description, svl_id, cost)`
Creates the journal entry for a single valuation layer:

| Direction | Debit | Credit |
|----------|-------|--------|
| Receipt (`_is_in`) | Stock Valuation (`stock_valuation`) | Stock Input (`stock_input`) |
| Delivery (`_is_out`) | Stock Output (`stock_output`) | Stock Valuation (`stock_valuation`) |
| Return receipt | Stock Input (`stock_input`) | Stock Valuation (`stock_valuation`) |
| Return delivery | Stock Valuation (`stock_valuation`) | Stock Output (`stock_output`) |

#### Dropship Anglo-Saxon
When `company_id.anglo_saxon_accounting = True` and move is dropshipped:
- Extra entry: stock_input → stock_valuation (or stock_valuation → stock_output)

### account.move (Extended)

#### Fields Added
| Field | Type | Description |
|-------|------|-------------|
| `stock_move_id` | Many2one | Stock move that generated this entry |
| `stock_valuation_layer_ids` | One2many | SVLs linked to this move |

#### Methods
| Method | Purpose |
|--------|---------|
| `_stock_account_prepare_anglo_saxon_out_lines_vals()` | Creates COGS debit/credit pair per invoice line |
| `_stock_account_anglo_saxon_reconcile_valuation()` | Reconciles interim stock account with SVL entries |
| `_stock_account_get_last_step_stock_moves()` | Returns stock moves linked to this invoice |

### account.move.line (Extended)

#### Fields Added
| Field | Type | Description |
|-------|------|-------------|
| `stock_valuation_layer_ids` | One2many | SVLs linked to this line |
| `cogs_origin_id` | Many2one | Originating invoice line for COGS entries |

#### Key Method: `_stock_account_get_anglo_saxon_price_unit()`
Used for COGS computation. For vendor refunds, looks up the original COGS line price. Otherwise delegates to product.

#### `_eligible_for_cogs()`
Only returns True when `product_id.type == 'product'` and `valuation == 'real_time'`.

## Anglo-Saxon Accounting (COGS)

When `company_id.anglo_saxon_accounting = True`, on `account.move._post()`:

### Customer Invoice
```
Standard entry (from sale):
  DR Account Receivable  $110
  CR Product Sales             $110

Anglo-Saxon COGS entry:
  DR Expenses (COGS)      $95    (or stock_output)
  CR Stock Interim (Delivered)  $95  (display_type='cogs')
```

### Customer Refund
```
Standard entry:
  DR Product Sales         $110
  CR Account Receivable         $110

Anglo-Saxon reversal:
  DR Stock Interim (Delivered)  $95
  CR Expenses (COGS)           $95
```

The COGS lines use `display_type = 'cogs'` and carry `cogs_origin_id` linking back to the originating invoice line. They are automatically unlinked when the invoice is reset to draft.

Reconciliation happens in `_stock_account_anglo_saxon_reconcile_valuation()`: invoice COGS lines are matched against the stock move's posted valuation lines on the same interim account.

## Valuation Methods

| Method | How Unit Cost Is Set |
|--------|---------------------|
| `standard` | Fixed `product.standard_price` |
| `average` (AVCO) | Weighted average of receipts, updated by `product_price_update_before_done()` |
| `fifo` | Cost of oldest remaining layer |

### AVCO Price Update (`product_price_update_before_done`)
```python
new_std_price = ((current_std_price * qty_on_hand) + (unit_cost * qty_received)) / (qty_on_hand + qty_received)
```
Runs before `super()._action_done()` on incoming moves.

## Manual Valuation (Periodic)

When `property_valuation = 'manual_periodic'` (not real-time):
- No automatic journal entries on move validation
- SVL records still created for qty/value tracking
- User posts manual entries via `stock.valuation.revaluation` wizard

## Product Template Extensions

Changing `categ_id` (category) triggers stock replenishment when cost method or valuation method changes:

1. Write current stock value to a "before" SVL
2. Empty all existing SVLs
3. Replenish by running a physical inventory at new cost

Also overrides `copy_data()` to exclude Anglo-Saxon COGS lines when copying an account.move.

### Exchange Gain/Loss on Real-Time Valuation

When a valuation journal entry is posted in a foreign currency, Odoo handles exchange differences:

```python
# account_move_line._get_exchange_journal()
# If the AML is linked to a stock valuation layer with real_time valuation:
return self.product_id.categ_id.property_stock_journal

# account_move_line._get_exchange_account()
# If the AML is linked to a stock valuation layer:
return self.product_id.categ_id.property_stock_valuation_account_id
```

This ensures that exchange differences on stock entries are posted to the stock valuation account rather than the default exchange difference account.

### Vendor Bill Handling

For vendor bills with real-time valuation (`_compute_account_id()` override on `AccountMoveLine`):

```python
# When move_id is a purchase document and company uses anglo_saxon:
if line.move_id.is_purchase_document():
    accounts = product.product_tmpl_id.get_product_accounts(fiscal_pos=fiscal_pos)
    if accounts['stock_input']:
        line.account_id = accounts['stock_input']
```

This auto-assigns the `stock_input` account on vendor bill lines, which is then debited when the receipt is validated (stock entry credit against `stock_input`).

## Configuration: Per-Location Valuation Accounts

`stock.location` is extended in `stock_account/models/stock_location.py` to allow setting location-specific valuation accounts:

| Field | Purpose |
|-------|---------|
| `valuation_in_account_id` | Override stock_input for receipts to this location |
| `valuation_out_account_id` | Override stock_output for deliveries from this location |

When set on a location involved in a stock move, the move's `_prepare_account_move_line()` uses these instead of the product category defaults.

## See Also
- [Modules/Stock](modules/stock.md) — `stock.move`, `stock.quant`, `stock.location`
- [Modules/Account](modules/account.md) — `account.move`, journal entries
- [Modules/analytic](modules/analytic.md) — `account.analytic.line`
- [Modules/purchase](modules/purchase.md) — vendor bill Anglo-Saxon price unit hook
- [Modules/sale_timesheet](modules/sale_timesheet.md) — service product profitability
