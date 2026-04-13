---
type: module
module: mrp_subcontracting_account
tags: [odoo, odoo19, mrp, subcontracting, account, valuation]
created: 2026-04-06
---

# MRP Subcontracting Account (`mrp_subcontracting_account`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Subcontracting Management with Stock Valuation |
| **Technical** | `mrp_subcontracting_account` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Category** | Supply Chain/Manufacturing |
| **Depends** | `mrp_subcontracting`, `mrp_account` |
| **Auto-installs with** | `mrp_subcontracting` + `mrp_account` both present |
| **Odoo Version** | 19 (CE) |

## Description

This bridge module connects the subcontracting manufacturing workflow (`mrp_subcontracting`) with Odoo's stock valuation engine (`stock_account`). It enables accurate cost accounting for subcontracted manufacturing orders, separating the raw material component cost from the subcontracting service fee. Without this module, subcontracted products are valued only at component cost; the subcontracting labor/processing fee is invisible to the valuation layer.

## Module File Tree

```
mrp_subcontracting_account/
├── __init__.py                                  # Imports models
├── __manifest__.py                              # auto_install=True
├── models/
│   ├── __init__.py
│   ├── mrp_production.py    # _cal_price override for extra_cost
│   ├── stock_move.py         # _get_aml_value override for component moves
│   └── product_product.py    # _compute_bom_price override for subcontract BoM
├── security/
│   ├── mrp_subcontracting_account_security.xml  # Portal ACL for analytic accounts
│   └── ir.model.access.csv
└── tests/
    └── test_subcontracting_account.py           # Valuation and cost tests
```

---

## Architecture

The module is a **bridge**: it does not introduce any new models. It overrides three existing methods across three models to wire up the cost flow:

| Model Extended | Method | Purpose |
|---|---|---|
| `mrp.production` | `_cal_price()` | Extracts subcontracting PO/bill price; sets `extra_cost` |
| `stock.move` | `_get_aml_value()` | Subtracts `extra_cost` from component move valuation |
| `product.product` | `_compute_bom_price()` | Adds subcontracting supplier price into BoM cost rollup |

### Dependencies Interaction

```
mrp_subcontracting
  └── provides: subcontracting workflow, is_subcontract flag, MO creation
      + subcontracting PO generation
mrp_account
  └── provides: _cal_price base (cost rollup), extra_cost field on mrp.production
mrp_subcontracting_account
  └── _cal_price override: intercepts base, injects subcontracting fee
  └── _get_aml_value override: prevents double-counting in Anglo-Saxon mode
  └── _compute_bom_price override: adds subcontracting vendor price to BoM cost
```

The `auto_install=True` flag means the module installs automatically when both `mrp_subcontracting` and `mrp_account` are in the system — no manual activation needed.

---

## Extended Models Detail

### 1. `mrp.production` — Cost Calculation with Subcontracting Fee

**File:** `models/mrp_production.py`

#### L3: `_cal_price` — Extracting Subcontracting Cost from Receipt

```python
def _cal_price(self, consumed_moves):
    finished_move = self.move_finished_ids.filtered(
        lambda x: x.product_id == self.product_id
        and x.state not in ('done', 'cancel')
        and x.quantity > 0)
    # Take the price unit of the reception move
    last_done_receipt = finished_move.move_dest_ids.filtered(
        lambda m: m.state == 'done')[-1:]
    if last_done_receipt.is_subcontract:
        quantity = last_done_receipt.quantity
        bill_data = last_done_receipt._get_value_from_account_move(quantity)
        po_data = last_done_receipt._get_value_from_quotation(quantity - bill_data['quantity'])
        if not bill_data['value'] and not po_data['value']:
            self.extra_cost = last_done_receipt.price_unit
        else:
            self.extra_cost = (bill_data['value'] + po_data['value']) / quantity
    return super()._cal_price(consumed_moves=consumed_moves)
```

**Step-by-step logic:**

1. **Identify the finished goods move:** Filters `move_finished_ids` to the move for `self.product_id` that is not yet done and has positive quantity.
2. **Find the done subcontracting receipt:** `finished_move.move_dest_ids` are the downstream moves chained from the finished move. For a subcontracting MO, the finished move's destination is the subcontracting receipt move. The `[-1:]` takes the most recently done receipt (handles partial receipts/backorders correctly).
3. **Guard on `is_subcontract`:** If the receipt is not a subcontract move (e.g., a regular MO), the base cost calculation runs without modification.
4. **Extract billed amount:** `_get_value_from_account_move(quantity)` reads the linked vendor bill (account move) and returns `{'value': total_billed_amount, 'quantity': billed_qty}`. This handles cases where only part of the receipt has been invoiced.
5. **Extract PO amount (unbilled remainder):** `_get_value_from_quotation(remaining_qty)` reads the open purchase order line and returns the PO value for the unbilled portion. The sum of both gives the total subcontracting cost.
6. **Compute `extra_cost`:** `(billed_value + po_value) / quantity` gives the per-unit subcontracting fee. This is stored in `self.extra_cost`, a field defined in `mrp_account`.
7. **Fallback:** If neither bill nor PO exists (`not bill_data['value'] and not po_data['value']`), the receipt's `price_unit` is used directly as the extra cost.

**L4: `_get_value_from_account_move` and `_get_value_from_quotation`**

These helper methods are defined on `stock.move` (not in this module). They perform the accounting data extraction:
- `_get_value_from_account_move(qty)`: Looks for an `stock.account.move.line` linked to the move via the Anglo-Saxon valuation chain. Returns the invoiced debit/credit value and quantity for that portion.
- `_get_value_from_quotation(qty)`: Reads the `purchase_order_line_id.price_unit * qty` for the portion not yet billed. If the PO is fully billed, returns zero.

The split between billed and unbilled is critical for partial invoicing scenarios — if only 5 of 10 units have been invoiced, the first 5 units use the bill value and the remaining 5 use the PO value.

**L4: `extra_cost` role in stock valuation**

The `extra_cost` field (from `mrp_account`) is added to the MO's finished product valuation layer. In the `stock.valuation.layer` record created when the receipt is validated, the `value` field = `(component_costs + extra_cost) * quantity`. This layer is what drives the inventory valuation reports and the Anglo-Saxon journal entries.

---

### 2. `stock.move` — Anglo-Saxon Valuation Adjustment

**File:** `models/stock_move.py`

#### L3: `_get_aml_value` — Avoid Double-Counting Subcontracting Fee

```python
def _get_aml_value(self):
    value = super()._get_aml_value()
    if (
        self.production_id
        and self.move_dest_ids.filtered(lambda m: m.state == "done")[-1:].is_subcontract
        and self.product_id.cost_method != "standard"
    ):
        value -= self.production_id.extra_cost * self.product_uom._compute_quantity(
            self.quantity, self.product_id.uom_id)
    return value
```

**Why this override is necessary:**

In **Anglo-Saxon (automated) valuation**, when a stock move is done, Odoo generates account journal entries to record the inventory change. The base `_get_aml_value()` computes the monetary value of the move based on the product's cost method (FIFO/average). For a component consumption move in a regular MO, this returns `quantity * unit_cost`.

For **subcontracting component moves**, the complication is:
- The component move represents materials delivered TO the subcontractor.
- Its normal value (based on component cost) is correct — that should be recorded.
- BUT the finished product move (`move_dest_ids`) also carries the subcontracting fee (`extra_cost`).
- If `_get_aml_value` for the component move ALSO included the `extra_cost`, the subcontracting fee would be counted twice in the journal entries.

**What the condition checks:**
1. `self.production_id` — This move is a raw material move for a production order (not a finished goods move).
2. `self.move_dest_ids[-1:].is_subcontract` — The downstream move (finished goods receipt) is a subcontracting receipt. This is the signal that we're in a subcontracting context.
3. `self.product_id.cost_method != "standard"` — Only applies to non-standard-cost products. For standard-cost products, the `extra_cost` is not added in `_cal_price` (or behaves differently), so this adjustment is not needed.

**What the subtraction does:**
- Subtracts `extra_cost * qty_in_product_uom` from the component move's journal entry value.
- This effectively zeroes out the subcontracting fee portion from the component move, leaving only the raw component cost.
- The subcontracting fee is captured exclusively in the finished goods receipt's valuation.

**Example:** For a finished product requiring 1x Component A (cost=10) + 1x Component B (cost=20) + subcontracting fee (30):
- Component A move: `value -= 30 * 1` → removes subcontracting fee from component A's journal entry
- Component B move: `value -= 30 * 1` → removes subcontracting fee from component B's journal entry
- Finished goods move: records `value = 30 (components) + 30 (extra_cost) = 60`

**L4: Impact on the test assertions**

The `test_subcontracting_account_flow_1` test confirms this behavior:
- `mo1.move_finished_ids.value == 60` — MO finished move = component cost (30) + extra_cost (30)
- `picking_receipt.move_ids.value == 0` — receipt move = 0 because the bill handles the fee
- Account move lines show only component-level entries (A/P debit/credit, no finished goods receipt line)

---

### 3. `product.product` — BoM Cost with Subcontracting Price

**File:** `models/product_product.py`

#### L3: `_compute_bom_price` — Including Subcontracting Vendor Price

```python
def _compute_bom_price(self, bom, boms_to_recompute=False, byproduct_bom=False):
    price = super()._compute_bom_price(bom, boms_to_recompute, byproduct_bom)
    if bom and bom.type == 'subcontract':
        seller = self._select_seller(
            quantity=bom.product_qty, uom_id=bom.product_uom_id,
            params={'subcontractor_ids': bom.subcontractor_ids})
        if seller:
            seller_price = seller.currency_id._convert(
                seller.price, self.env.company.currency_id,
                (bom.company_id or self.env.company), fields.Date.today())
            price += seller.product_uom_id._compute_price(seller_price, self.uom_id)
    return price
```

**Purpose:** When the product's **standard price** is re-computed from its BoM (via `button_bom_cost` or `action_bom_cost`), this override adds the subcontracting vendor's processing price to the BoM cost.

**Step-by-step:**
1. Runs the base `_compute_bom_price` (from `mrp_account`) which sums component costs at their standard/average cost.
2. If the BoM type is `subcontract`:
   a. Calls `_select_seller(..., params={'subcontractor_ids': bom.subcontractor_ids})` to find the vendor price. This passes the `subcontractor_ids` as a filter parameter, ensuring only vendors listed in the BoM's subcontractor_ids are considered. This is the same `_prepare_sellers` override from `mrp_subcontracting` in action.
   b. Converts the seller price to the company's currency using today's exchange rate.
   c. Converts the seller's price unit (which may be per dozen, per hundred, etc.) to the product's unit of measure using `_compute_price`.
   d. Adds the converted vendor price to the BoM cost.

**L4: Unit of measure handling**

The `seller.product_uom_id` may differ from `self.uom_id`. For example:
- A subcontracting service is priced per **dozen** (`seller.product_uom_id = uom.dozen`)
- The finished product is manufactured in **units** (`self.uom_id = uom.unit`)
- `seller.product_uom_id._compute_price(seller_price, self.uom_id)` converts: `150 per dozen / 12 = 12.50 per unit`

The test `test_01_compute_price_subcontracting_cost` exercises exactly this: `table_head` has a subcontracting price of 120/dozen, which converts to 10/unit when computing the BoM cost.

---

## Security

**File:** `security/mrp_subcontracting_account_security.xml`

Two portal record rules extend subcontractor access to analytic accounting:

```xml
<record model="ir.rule" id="analytic_accout_subcontractor_rule">
    <field name="name">Analytic Account Subcontractor</field>
    <field name="model_id" ref="mrp_account.model_account_analytic_account"/>
    <field name="domain_force">[('bom_ids', 'in', user.partner_id.commercial_partner_id.bom_ids.ids)]</field>
    <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
</record>

<record model="ir.rule" id="analytic_accout_line_subcontractor_rule">
    <field name="name">Analytic Account Line Subcontractor</field>
    <field name="model_id" ref="mrp_account.model_account_analytic_line"/>
    <field name="domain_force">[('account_id.bom_ids', 'in', user.partner_id.commercial_partner_id.bom_ids.ids)]</field>
    <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
</field>
```

- **`account.analytic.account` rule:** Grants portal users read access to analytic accounts that are linked to any of their subcontracting BoMs (via `bom_ids`). This allows subcontractors to view cost/analytic data relevant to their work.
- **`account.analytic.line` rule:** Grants portal users read access to analytic lines belonging to those accounts. Without these rules, subcontractors would get AccessError when navigating to analytic cost views from the portal MO page.
- The domain uses `commercial_partner_id.bom_ids` — matching the same pattern used throughout `mrp_subcontracting` security rules, ensuring consistency across the subcontracting portal.

---

## L3: Complete Subcontracting Valuation Flow

This diagram shows where each override acts in the end-to-end flow:

```
1. Receipt Picking Confirmed
   │
2. Subcontracting MO Created (via mrp_subcontracting._subcontracted_produce)
   │
3. Resupply Picking delivers components to subcontractor
   │   Components valued at: component standard_price
   │   Journal Entry: DR Inventory Valuation  CR A/P Subcontractor
   │
4. Subcontractor produces and ships finished goods
   │
5. Receipt Picking Validated
   │
   ├── Component moves done (consumed at subcontractor)
   │   ├── Base _get_aml_value returns: component_qty * component_cost
   │   └── mrp_subcontracting_account._get_aml_value SUBTRACTS extra_cost
   │       Result: component_qty * component_cost (no double-count)
   │       JE: DR Production  CR Inventory Valuation (at component cost)
   │
   ├── Finished goods move done
   │   └── mrp_account._cal_price called on MO
   │       └── mrp_subcontracting_account._cal_price:
   │           extracts subcontracting fee from bill + PO
   │           sets extra_cost = (bill_value + po_value) / qty
   │       JE: DR Finished Goods  CR Production (at component cost + extra_cost)
   │
   └── Vendor Bill Created / Updated
       └── PO line price_unit * qty matched to receipt
           JE: DR A/P Subcontractor  CR Inventory Valuation (subcontracting fee)
```

**Final stock value:** `component_cost + subcontracting_fee` per unit

---

## L4: Version Changes (Odoo 18 → 19)

The `mrp_subcontracting_account` module is largely stable across Odoo 18 → 19. Key observations:

- **Odoo 18:** The `_cal_price` method had a slightly different structure for handling partial billing. The split between `bill_data` and `po_data` using quantity arithmetic was introduced to properly handle partial vendor bill scenarios.
- **Odoo 19:** The `_get_aml_value` override added the `cost_method != "standard"` guard. In earlier versions, the subtraction ran for all cost methods, which caused incorrect entries for standard-cost subcontracted products.

---

## L4: Edge Cases

### 1. Partial vendor bill

When only part of the subcontracting receipt has been billed (e.g., 5 of 10 units invoiced), `_cal_price` splits the calculation:
- Billed portion: `bill_data['value'] / bill_data['quantity']` → `extra_cost` per billed unit
- Unbilled portion: `po_data['value'] / remaining_qty` → `extra_cost` per unbilled unit
- Final `extra_cost` is the weighted average of both

### 2. Receipt before PO

If the receipt is validated before a PO is created (`mrp_subcontracting_purchase` enterprise), `_cal_price` falls back to `last_done_receipt.price_unit` as the `extra_cost`. This requires the user to manually set the `price_unit` on the stock move before receipt.

### 3. No PO, no bill (VMI scenario)

If no PO or bill exists and no `price_unit` is set, `extra_cost` defaults to 0. The finished product is valued at component cost only. This is a known gap — the subcontracting fee is not captured without a PO/bill or manual price unit.

### 4. Standard-cost products

For products using `cost_method = 'standard'`, `_get_aml_value` does NOT subtract `extra_cost` (due to the `!= "standard"` guard). The `extra_cost` from `_cal_price` is still set on the MO, but its interaction with standard cost valuation depends on the `stock_account` configuration for standard products. In this case, the finished product's valuation is driven by `standard_price` rather than the actual subcontracting cost.

### 5. Backorder with partial bill

When a receipt is partially received and partially billed, and a backorder is created:
- `test_subcontracting_account_backorder` verifies that each finished goods valuation layer gets `value = qty * (component_cost + subcontracting_cost_per_unit)`.
- The `[-1:]` selector on `move_dest_ids.filtered(lambda m: m.state == "done")` ensures the calculation uses the most recently completed receipt, not all receipts.

### 6. No production account configured

`test_subcontract_without_prod_account` confirms that if the production location has no `valuation_account_id`, no account move lines are created at all. This is graceful — no error is raised, but the lack of journal entries means inventory valuation is not tracked for those moves.

---

## Test Coverage (`tests/test_subcontracting_account.py`)

| Test | Scenario | Key Assertion |
|---|---|---|
| `test_subcontracting_account_flow_1` | Full flow: components → receipt → bill; FIFO products | `mo.value=60`, `receipt.move.value=0`, correct AML entries |
| `test_subcontracting_account_backorder` | Tracked components + serial finished, 4 backorders | Each finished layer gets correct value including subcontracting fee |
| `test_tracked_compo_and_backorder` | FIFO, 3 partial receipts (10 → 5 → 3 → 2), lot tracking | Each backorder valued correctly at `(comp_cost + fee) * qty` |
| `test_subcontract_cost_different_when_standard_price` | Standard cost method, finished product cost differs from comp+fee | Correct AML entries despite standard cost method |
| `test_subcontract_without_prod_account` | No production account configured | No AMLs created (graceful degradation) |
| `test_01_compute_price_subcontracting_cost` | BoM cost rollup with subcontracting price | `standard_price = components + subcontracting_vendor_price` |
| `test_02_compute_price_subcontracting_cost` | BoM cost with foreign currency subcontracting vendor | Currency conversion applied correctly in rollup |

---

## Related Modules

| Module | Relationship |
|---|---|
| `[Modules/mrp_subcontracting](modules/mrp_subcontracting.md)` | Core dependency — provides the subcontracting workflow |
| `[Modules/mrp_account](modules/mrp_account.md)` | Core dependency — provides `extra_cost` field and base `_cal_price` |
| `stock_account` | Handles Anglo-Saxon journal entry generation; `_get_aml_value` is called by this module |
| `mrp_subcontracting_purchase` (EE) | Integrates subcontracting PO with receipt; enables full bill-based `_cal_price` flow |
| `stock_landed_costs` | Adds additional costs (freight, duty, insurance) on top of subcontracting valuation |

---

## Tags

#modules #mrp #subcontracting #account #valuation #stock #costing #odoo19
