---
Module: mrp_subcontracting_account
Version: Odoo 18
Type: Integration
Tags: #odoo, #odoo18, #mrp, #subcontracting, #accounting, #valuation
Related Modules: mrp_subcontracting, mrp_account, stock_landed_costs, stock_account
---

# MRP Subcontracting Account (`mrp_subcontracting_account`)

## Module Overview

**Location:** `~/odoo/odoo18/odoo/addons/mrp_subcontracting_account/`
**Depends:** `mrp_subcontracting`, `mrp_account`
**Category:** Hidden
**License:** LGPL-3
**Auto-install:** Yes

This bridge module connects subcontracting manufacturing with accounting and inventory valuation. It splits the landed cost of a subcontracted product into two components — **component cost** and **subcontracting service cost** — and creates separate accounting entries for each. It also ensures subcontracting costs flow correctly into the BOM price calculation.

---

## Valuation Architecture

In standard subcontracting, the finished product is valued at the subcontracting service cost from the PO. In `mrp_subcontracting_account`, the total cost is decomposed:

```
Total Finished Product Cost = Component Costs + Subcontracting Service Cost
```

| Cost Element | Source | Accounting Entry |
|-------------|--------|-----------------|
| **Component cost** | Stock valuation layers on `move_raw_ids` | Credit: `stock_valuation` account (from components) → Debit: `stock_output` / `stock_valuation` of finished product |
| **Subcontracting service cost** | `extra_cost` on MO, derived from PO receipt price | Credit: `stock_input` (subcontractor payable) → Debit: `stock_valuation` of finished product |

---

## Models

### `stock.move` — Extended

**File:** `models/stock_move.py`

#### Overrides

##### `_should_force_price_unit()`
Returns `True` for subcontract moves, forcing the move to use the actual subcontracting cost (from PO price) rather than the product's standard cost:

```python
def _should_force_price_unit(self):
    return self.is_subcontract or super()._should_force_price_unit()
```

##### `_generate_valuation_lines_data(partner_id, qty, debit_value, credit_value, debit_account_id, credit_account_id, svl_id, description)`
**Critical override.** Splits the subcontracting credit entry into two separate lines:

**When triggered:** When `is_subcontract=True` and the production has a `subcontractor_id` AND `qty > 0`.

```python
subcontract_production = self.production_id.filtered(lambda p: p.subcontractor_id)
rounding = self.product_id.uom_id.rounding
if not subcontract_production or float_compare(qty, 0, precision_rounding=rounding) < 0:
    return rslt  # Delegates to parent for non-subcontract or negative qty
```

**Cost split logic:**

```python
if self.product_id.cost_method == 'standard':
    # Standard price: component cost = sum of SVL values on raw moves
    component_cost = abs(currency.round(
        sum(subcontract_production.move_raw_ids.stock_valuation_layer_ids.mapped('value'))
    ))
    subcontract_service_cost = credit_value - component_cost
else:
    # Average/FIFO: subcontract_service_cost = extra_cost × qty
    subcontract_service_cost = currency.round(subcontract_production.extra_cost * qty)
    component_cost = credit_value - subcontract_service_cost
```

**Journal entry generation:**

```python
# Original credit line deleted
del rslt['credit_line_vals']

# Two new credit lines replace it:
rslt['subcontract_credit_line_vals'] = {          # Subcontracting service
    'name': description,
    'product_id': self.product_id.id,
    'quantity': qty,
    'product_uom_id': self.product_id.uom_id.id,
    'ref': description,
    'partner_id': partner_id,
    'balance': -subcontract_service_cost,        # Negative = credit
    'account_id': service_cost_account,           # stock_input account
}

rslt['component_credit_line_vals'] = {            # Component costs
    'name': description,
    'product_id': self.product_id.id,
    'quantity': qty,
    'product_uom_id': self.product_id.uom_id.id,
    'ref': description,
    'partner_id': partner_id,
    'balance': -component_cost,                   # Negative = credit
    'account_id': credit_account_id,              # Original stock_valuation
}
```

**Correction path:** If the SVL passed is not directly linked to the move (i.e., this is a valuation correction), the credit always goes to `stock_input` to properly add value to the subcontracted product.

---

### `stock.picking` — Extended

**File:** `models/stock_picking.py`

#### Overrides

##### `action_view_stock_valuation_layers()`
Extends the valuation layer view to include SVLs from the subcontracted MO's raw and finished moves:

```python
def action_view_stock_valuation_layers(self):
    action = super(StockPicking, self).action_view_stock_valuation_layers()
    subcontracted_productions = self._get_subcontract_production()
    if not subcontracted_productions:
        return action
    domain = action['domain']
    # Adds SVL domain for subcontract MO raw + finished moves
    domain_subcontracting = [(
        'id', 'in',
        (subcontracted_productions.move_raw_ids | subcontracted_productions.move_finished_ids)
            .stock_valuation_layer_ids.ids
    )]
    domain = OR([domain, domain_subcontracting])
    return dict(action, domain=domain)
```

**L4 Note:** When viewing SVLs from a subcontracting receipt picking, this now shows:
1. The finished product SVL on the receipt move
2. The component SVLs from the MO's raw moves
3. Any compensation SVLs from `mrp_subcontracting_dropshipping`

---

### `mrp.production` — Extended

**File:** `models/mrp_production.py`

#### Overrides

##### `_cal_price(consumed_moves)`
Updates `extra_cost` on the MO from the last done subcontracting receipt move:

```python
def _cal_price(self, consumed_moves):
    finished_move = self.move_finished_ids.filtered(
        lambda x: x.product_id == self.product_id
        and x.state not in ('done', 'cancel')
        and x.quantity > 0
    )
    last_done_receipt = finished_move.move_dest_ids.filtered(lambda m: m.state == 'done')[-1:]
    if last_done_receipt.is_subcontract:
        self.extra_cost = next(iter(last_done_receipt._get_price_unit().values()))
    return super()._cal_price(consumed_moves=consumed_moves)
```

**Effect:** After the subcontracting PO receipt is validated, the MO's `extra_cost` is updated to match the PO's unit cost for that product. This `extra_cost` is used in `_generate_valuation_lines_data` for average/FIFO products to determine the subcontracting service cost.

---

### `product.product` — Extended

**File:** `models/product_product.py`

#### Overrides

##### `_compute_bom_price(bom, boms_to_recompute=False, byproduct_bom=False)`
For subcontract BOMs, adds the **subcontracting supplier price** to the BOM cost roll-up:

```python
def _compute_bom_price(self, bom, boms_to_recompute=False, byproduct_bom=False):
    price = super()._compute_bom_price(bom, boms_to_recompute, byproduct_bom)
    if bom and bom.type == 'subcontract':
        seller = self._select_seller(
            quantity=bom.product_qty,
            uom_id=bom.product_uom_id,
            params={'subcontractor_ids': bom.subcontractor_ids}
        )
        if seller:
            seller_price = seller.currency_id._convert(
                seller.price,
                self.env.company.currency_id,
                (bom.company_id or self.env.company),
                fields.Date.today()
            )
            price += seller.product_uom._compute_price(seller_price, self.uom_id)
    return price
```

**L4 Note:** For a subcontract BOM, the price is the sum of:
1. Component costs (from component BoMs, if any are kit products)
2. Subcontracting service cost (from `seller.price` on the subcontractor vendor)

The `_select_seller()` call uses `subcontractor_ids` parameter to match the correct vendor (the subcontractor).

---

## L4: Subcontracting Valuation — Detailed Flow

### Standard Cost Method

```
MO receipt (finished product):
  Finished product Qty: 10
  Component SVLs: raw move SVLs total = $500 (10 × component cost)
  PO unit price: $120 (total subcontracting service for 10 units)
  credit_value (total): $620

Split:
  Component credit:  -$500 → stock_valuation account (component origin)
  Service credit:    -$120 → stock_input account (subcontractor payable)

Result:
  Finished product inventory value = $620 (10 × $62/unit)
  Components removed from stock_valuation = $500
  Liability to subcontractor = $120 (stock_input)
```

### Average/FIFO Cost Method

```
MO receipt:
  extra_cost = PO unit price for subcontracting service = $12/unit
  Finished product Qty: 10
  subcontract_service_cost = extra_cost × qty = $120
  credit_value = total SVL value from receipt = $620

Split:
  Component credit:  credit_value - subcontract_service_cost = $500
  Service credit:    subcontract_service_cost = $120

Result: Same as standard — different derivation path
```

---

## L4: BOM Cost Roll-Up

For a subcontracted product with a BOM:

```
Product P (subcontract, subcontractor=SC)
  BOM type: subcontract
  Components: none (or only non-kit components)

_compute_bom_price(P):
  1. Calls super() → component costs from sub-BOMs (if any)
  2. seller = _select_seller(subcontractor_ids=SC)
  3. price += seller.price (SC's unit price on PO)
  4. Returns: component_costs + subcontracting_unit_price
```

**L4 Note:** When the MO for P is confirmed, `mrp_production._cal_price()` updates `extra_cost` from the PO receipt. But when the MO is first created or when using `product.product._compute_bom_price()` for valuation estimates, the BOM roll-up uses the vendor's listed price (not the actual PO receipt price).

---

## Interaction with `stock_landed_costs`

The base `stock.landed.cost` model supports applying additional landed costs to receipt pickings. When applied to a subcontracting receipt:

| Model | Field | Role |
|-------|-------|------|
| `stock.landed.cost` | `picking_ids` | Target subcontracting receipt picking |
| `stock.landed.cost` | `cost_lines` | Additional cost lines (freight, duty, etc.) |
| `stock.valuation.adjustment.lines` | `move_id` | Links landed cost to the finished product receipt move |
| `stock.valuation.adjustment.lines` | `former_cost` | Current SVL value on the move |
| `stock.valuation.adjustment.lines` | `additional_landed_cost` | Prorated additional cost |

**Important:** `stock.landed.cost` lands on the **finished product receipt move**, not the component moves. The component costs are already captured via `move_raw_ids` SVLs.

The `mrp_subcontracting_landed_costs` module (separate) extends `_get_stock_valuation_layer_ids()` on `stock.move` to include subcontract MO finished move SVLs when viewing layers on the receipt picking.

---

## Interaction with `mrp_subcontracting_dropshipping`

When both `mrp_subcontracting_dropshipping` and `mrp_subcontracting_account` are installed:

1. The dropship component PO arrives at the subcontractor (no SVL at manufacturer)
2. The MO consumes components at subcontractor location (SVL created)
3. The finished product is dropshipped to customer or received at warehouse
4. `_action_done()` on `stock.picking` creates a **compensation SVL** if MO cost > dropship cost

```python
# Compensation logic in stock_picking._action_done() (mrp_subcontracting_dropshipping)
diff = subcontract_value - dropship_value
if diff > 0:
    svl_vals = {
        'value': -diff,         # Negative = reduces inventory value
        'quantity': 0,
        'stock_valuation_layer_id': dropship_svls[0].id,
    }
    svls |= self.env['stock.valuation.layer'].create(svl_vals)
```

This prevents the component costs (already counted in MO SVL) from being double-counted in the dropship receipt SVL.

---

## `stock.valuation.layer` Extension

`mrp_subcontracting_purchase/models/stock_valuation_layer.py` provides:

##### `_get_layer_price_unit()`
For a subcontracted product's SVL, returns the subcontracting cost **minus component values** (so the SVL unit price reflects only the service cost, not the full landed cost):

```python
def _get_layer_price_unit(self):
    components_price = 0
    production = self.stock_move_id.production_id
    if production.subcontractor_id and production.state == 'done':
        for move in production.move_raw_ids:
            components_price += abs(sum(move.sudo().stock_valuation_layer_ids.mapped('value'))) / production.product_uom_qty
    return super()._get_layer_price_unit() - components_price
```

**Purpose:** This gives a "pure" subcontracting unit price for use in AVCO recalculations and reporting, stripping out the component layer values that are tracked separately.

---

## Security

**Groups:** Inherited from `stock_account` and `mrp_account`:
- `stock_account.group_stock_accounting` — full access to valuation and landed costs
- `mrp_account.group_mrp_workorder` — access to MO cost fields

**Data:** `security/ir.model.access.csv` grants model-level access.
