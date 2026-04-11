# stock_account — Stock Accounting

**Tags:** #odoo #odoo18 #stock #account #valuation #anglo-saxon #cogs
**Odoo Version:** 18.0
**Module Category:** Stock + Account Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`stock_account` is the core module bridging Stock and Account. It enables real-time (automated) inventory valuation, COGS journal entry generation for Anglo-Saxon accounting, lot-level valuation, price difference handling, and analytic accounting integration for stock moves. It defines the `stock.valuation.layer` model as its central record of every stock value change.

**Technical Name:** `stock_account`
**Python Path:** `~/odoo/odoo18/odoo/addons/stock_account/`
**Depends:** `stock`, `account`
**Inherits From:** `stock.move`, `stock.quant`, `stock.lot`, `account.move`, `stock.location`, `res.company`, etc.

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/stock_valuation_layer.py` | `stock.valuation.layer` | Core SVL model with valuation logic |
| `models/account_move.py` | `account.move`, `account.move.line` | COGS lines, anglo-saxon reconciliation |
| `models/stock_move.py` | `stock.move` | SVL creation, accounting entry posting, in/out detection |
| `models/stock_move_line.py` | `stock.move.line` | SVL creation on qty changes, lot validation |
| `models/stock_quant.py` | `stock.quant` | Value computation, accounting date handling |
| `models/stock_lot.py` | `stock.lot` | Lot-level valuation, avg cost, revaluation action |
| `models/stock_picking.py` | `stock.picking` | Country code, SVL action |
| `models/stock_location.py` | `stock.location` | Valuation account overrides per location |
| `models/res_company.py` | `res.company` | WIP overhead accounts |
| `models/res_config_settings.py` | `res.config.settings` | Module toggles, group settings |
| `models/product.py` | `product.template`, `product.product` | Lot valuated, valuation at date |
| `models/analytic_account.py` | `account.analytic.plan`, `account.analytic.account` | Analytic distribution for stock moves |
| `models/account_chart_template.py` | `account.chart.template` | WIP account loading |
| `models/template_generic_coa.py` | `account.chart.template` | Stock journal + stock property defaults |

---

## Models Reference

### `stock.valuation.layer` (models/stock_valuation_layer.py)

#### Inheritance

Core model defined in `stock_account` (not extending existing, this IS the model).

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `company_id` | Many2one | Required, readonly |
| `product_id` | Many2one | Required, readonly |
| `categ_id` | Many2one | Related to product |
| `product_tmpl_id` | Many2one | Related to product |
| `quantity` | Float | readonly |
| `uom_id` | Many2one | Related to product |
| `currency_id` | Many2one | Related to company |
| `unit_cost` | Float | readonly, 'Product Price' digits |
| `value` | Monetary | readonly |
| `remaining_qty` | Float | readonly |
| `remaining_value` | Monetary | readonly |
| `description` | Char | readonly |
| `stock_valuation_layer_id` | Many2one | Linked SVL (for SVL chains) |
| `stock_valuation_layer_ids` | One2many | Child SVL layers |
| `stock_move_id` | Many2one | Source stock move |
| `account_move_id` | Many2one | Journal entry (btree_not_null) |
| `account_move_line_id` | Many2one | Invoice line (btree_not_null) |
| `reference` | Char | Related from stock_move |
| `price_diff_value` | Float | Invoice value correction |
| `warehouse_id` | Many2one | Computed from move location |
| `lot_id` | Many2one | Lot/serial number |

#### Methods

| Method | Behavior |
|--------|----------|
| `init()` | Creates two indexes: `stock_valuation_layer_index`, `stock_valuation_company_product_index` |
| `_compute_warehouse_id()` | Sets warehouse from location_id or location_dest_id |
| `_search_warehouse_id()` | Search by warehouse_id |
| `_get_related_product()` | Returns `product_id` |
| `_validate_accounting_entries()` | Creates account moves for SVLs, reconciles |
| `_validate_analytic_accounting_entries()` | Calls `stock_move_id._account_analytic_entry_move()` |
| `action_open_journal_entry()` | Opens linked account move |
| `action_valuation_at_date()` | Opens valuation at date wizard |
| `action_open_reference()` | Opens stock move reference |
| `_consume_specific_qty()` | FIFO consumption logic: skip valued qty, consume remaining |
| `_consume_all()` | Totals all SVL qty/value, deducts consumed, returns unit cost |
| `_change_standart_price_accounting_entries()` | Creates revaluation account moves |
| `_should_impact_price_unit_receipt_value()` | Always returns True |

---

### `account.move` (models/account_move.py — AccountMove class)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `stock_move_id` | Many2one | Link to stock move (btree_not_null) |
| `stock_valuation_layer_ids` | One2many | SVL layers on this move |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_show_reset_to_draft_button()` | Hides reset-to-draft if SVL exists |
| `_get_lines_onchange_currency()` | Excludes COGS lines |
| `copy_data()` | Excludes COGS lines when copying |
| `_post()` | Creates COGS lines, runs anglo-saxon reconciliation |
| `button_draft()` | Unlinks COGS lines |
| `button_cancel()` | Unlinks COGS lines |
| `_stock_account_prepare_anglo_saxon_out_lines_vals()` | Builds COGS vals dict (interim + expense debit/credit) |
| `_get_anglo_saxon_price_ctx()` | Override point for price context |
| `_stock_account_get_last_step_stock_moves()` | Returns stock moves related to invoice |
| `_stock_account_anglo_saxon_reconcile_valuation()` | Reconciles interim account entries with SVL moves |
| `_get_invoiced_lot_values()` | Returns lot values for invoice |

---

### `stock.move` (models/stock_move.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `to_refund` | Boolean | Trigger qty decrease on SO/PO |
| `account_move_ids` | One2many | Account moves from valuation |
| `stock_valuation_layer_ids` | One2many | Valuation layers |
| `analytic_account_line_ids` | Many2many | Analytic lines from stock moves |

#### Methods

| Method | Behavior |
|--------|----------|
| `_filter_anglo_saxon_moves()` | Filter by product |
| `action_get_account_moves()` | Opens linked account moves |
| `_get_valued_types()` | Returns `['in', 'out', 'dropshipped', 'dropshipped_returned']` |
| `_get_move_directions()` | Determines which moves are in/out/transit |
| `_get_in_move_lines()` | Returns incoming move lines |
| `_is_in()` | True if entering valued location |
| `_get_out_move_lines()` | Returns outgoing move lines |
| `_is_out()` | True if leaving valued location |
| `_is_dropshipped()` | True if supplier→customer/transit |
| `_is_dropshipped_returned()` | True if customer→supplier/transit |
| `_prepare_common_svl_vals()` | Builds common SVL vals dict |
| `_create_in_svl()` | Creates incoming SVL |
| `_create_out_svl()` | Creates outgoing SVL |
| `_get_out_svl_vals()` | Builds outgoing SVL vals (handles lots) |
| `_create_dropshipped_svl()` | Creates dropship SVL (in + out pair) |
| `_create_dropshipped_returned_svl()` | Calls `_create_dropshipped_svl` |
| `_action_done()` | Main SVL creation orchestrator: sorts moves by type, calls `_create_*_svl()` |
| `_sanity_check_for_valuation()` | Validates company consistency |
| `product_price_update_before_done()` | Updates standard_price for AVCO |
| `_product_price_update_after_done()` | Updates lot standard_price |
| `_get_accounting_data_for_valuation()` | Gets journal, accounts for valuation |
| `_get_in_svl_vals()` | Builds incoming SVL vals |
| `_prepare_account_move_line()` | Generates account.move.line vals |
| `_prepare_analytic_lines()` | Builds analytic line vals |
| `_prepare_analytic_line_values()` | Prepares single analytic line vals |
| `_generate_valuation_lines_data()` | Builds debit/credit line vals |
| `_account_analytic_entry_move()` | Creates analytic lines |
| `_account_entry_move()` | Main entry point for valuation journal entries |
| `_prepare_anglosaxon_account_move_vals()` | Dropship account move vals |
| `_get_all_related_aml()` | Returns all related account move lines |
| `_get_all_related_sm()` | Filters by product |
| `_get_layer_candidates()` | Returns stock_valuation_layer_ids |

---

### `stock.lot` (models/stock_lot.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `value_svl` | Float | Total SVL value |
| `quantity_svl` | Float | Total SVL quantity |
| `avg_cost` | Monetary | Average cost per unit |
| `total_value` | Monetary | Total lot value |
| `company_currency_id` | Many2one | Related currency |
| `stock_valuation_layer_ids` | One2many | SVL layers |
| `standard_price` | Float | Lot cost (company dependent) |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_value_svl()` | Aggregates SVL quantities and values |
| `create()` | Copies product standard_price if lot has none |
| `write()` | Calls `_change_standard_price()` on price change |
| `_change_standard_price()` | Creates revaluation SVL + account move |
| `action_revaluation()` | Opens revaluation wizard |
| `action_view_stock_valuation_layers()` | Opens SVL list |

---

### `stock.location` (models/stock_location.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `valuation_in_account_id` | Many2one | Override incoming valuation account |
| `valuation_out_account_id` | Many2one | Override outgoing valuation account |

#### Methods

| Method | Behavior |
|--------|----------|
| `_should_be_valued()` | True if `usage == 'internal'` or (`usage == 'transit'` and `company_id` set) |

---

### `product.template` (models/product.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `lot_valuated` | Boolean | Valuation by lot/serial (compute+store) |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_lot_valuated()` | Sets False when `tracking == 'none'` |
| `_onchange_standard_price()` | Warning when lot_valuated and qty_svl exists |
| `write()` | Handles lot revaluation on cost change |
| `action_update_product_cost()` | Updates lot standard prices |
| `_create_child_lot_svl()` | Creates SVL for lot revaluation |
| `_update_product_valued_lot_ids()` | Sets valued lot records |
| `write()` (lot_ids) | Updates lot standard prices |

---

## Security File: `security/stock_account_security.xml`

- **ir.rule**: `stock.valuation.layer` multi-company rule (`company_id in company_ids`)
- **Group**: `group_lot_on_invoice` (Display Serial & Lot Number on Invoices)
- **Group**: `group_stock_accounting_automatic` (Stock Accounting Automatic)

---

## Data Files

| File | Content |
|------|---------|
| `data/template_generic_coa_data.xml` | Stock valuation/accounting property defaults for generic COA |
| `data/stock_account_data.xml` | WIP accounts for production |

---

## Critical Behaviors

1. **SVL is the Central Record**: Every stock movement creates a `stock.valuation.layer` record. The SVL links back to the stock move (and optionally the invoice line) and carries `quantity`, `value`, `unit_cost`, and `remaining_qty`.

2. **AVCO (Average Cost)**: `_action_done()` calls `product_price_update_before_done()` which computes new `standard_price = (old_qty * old_price + new_qty * new_price) / (old_qty + new_qty)`. Both product-level and lot-level AVCO are supported.

3. **COGS Lines on Invoice**: `_post()` on `account.move` creates COGS journal entries when `anglo_saxon_accounting` is enabled. Each invoice line generates two entries: DR Expense / CR Stock Output (interim).

4. **Lot Valuated Products**: When `lot_valuated = True`, valuation tracks at the lot level. Unit cost is stored per lot. Average cost (`avg_cost`) and total value are computed from SVLs grouped by lot.

5. **Dropship Valuation**: Two SVLs are created — one for the "in" (from supplier to transit) and one for the "out" (transit to customer). In Anglo-Saxon mode, a direct entry from stock_input to stock_output is also created.

6. **Analytic Distribution**: Stock moves can carry analytic distribution. `_prepare_analytic_lines()` pulls amount from SVL's account move line and creates analytic lines with negative amounts (credit convention).

7. **Price Difference (PDiff)**: For `standard` cost method, when invoice price differs from PO price, `_apply_price_difference()` creates correction SVLs. For `average`, `standard_price` is updated directly.

8. **Location-Level Valuation Accounts**: `valuation_in_account_id` and `valuation_out_account_id` on `stock.location` allow virtual locations (e.g., customer returns, transit) to use specific accounts instead of the product's generic stock accounts.

---

## v17→v18 Changes

- `lot_valuated` field added at product.template level, replacing per-product tracking logic
- Lot-level AVCO now supported via `avg_cost` on `stock.lot`
- `_get_move_directions()` method added for move direction classification
- `_consume_specific_qty()` and `_consume_all()` SVL consumption methods added
- `_change_standart_price_accounting_entries()` method added for lot revaluation
- `stock.valuation.layer._should_impact_price_unit_receipt_value()` added (always True)
- `init()` now creates composite indexes for performance

---

## Notes

- `stock_account` is the foundation for all real-time inventory valuation
- The `stock.valuation.layer` model is the core data structure for every valuation transaction
- `_action_done()` on `stock.move` is the central orchestration point for all SVL creation
- Price difference handling is split: `purchase_stock` handles PO→receipt PDiff; `stock_account` handles the account move creation for both receipt and invoice PDiff
- The `group_stock_accounting_automatic` toggle allows switching from manual periodic to real-time valuation en masse
