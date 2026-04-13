---
uid: purchase_stock
tags:
  - #odoo
  - #odoo19
  - #modules
  - #purchase
  - #stock
  - #logistics
aliases:
  - Modules/purchase_stock
description: Bridges purchase orders and stock operations — auto-creates receipts on PO confirmation, tracks qty_received from stock moves, routes procurement via buy rules, and enables three-way matching valuation.
---

# purchase_stock

> Bridges `purchase` and `stock` modules. Auto-creates receipts on PO confirmation, tracks received quantity from stock moves, computes on-time delivery rates, and drives the three-way matching (PO / receipt / vendor bill) valuation flow.

**Category:** Supply Chain / Purchase
**Module Code:** `purchase_stock`
**Location:** `odoo/addons/purchase_stock/`
**Depends:** `stock_account`, `purchase`
**Auto-install:** `True` (installs automatically when both dependencies are present)
**License:** LGPL-3

---

## Module Overview

`purchase_stock` is the integration layer between Odoo's procurement intent (`purchase`) and physical operations (`stock`). Without it, a PO is a purely commercial document; with it, confirming a PO automatically creates a `stock.picking` (incoming shipment), and validating that shipment updates `stock.quant` quantities and generates accounting entries for inventory valuation.

The module also powers **automated procurement**: when a reorder rule fires, `stock.rule` with `action='buy'` generates RFQs or converts them to POs directly, grouping lines by vendor and scheduling by the vendor's lead time.

### Dependency Chain

```
purchase_stock
├── depends: stock_account   (inventory valuation entries)
└── depends: purchase        (PO model, PO line model)
        └── depends: stock  (stock.picking, stock.move, stock.rule)
```

`purchase_stock` does **not** depend on `sale_stock` directly, but the dropship flow requires `stock_dropshipping` to be installed separately (`module_stock_dropshipping` setting).

---

## Files Reference

| File | Model(s) Extended | Purpose |
|---|---|---|
| `models/purchase_order.py` | `purchase.order` | Receipt creation, picking linkage, cancellation, vendor suggestions |
| `models/purchase_order_line.py` | `purchase.order.line` | Stock move creation, qty_received from moves, procurement values |
| `models/stock.py` | `stock.picking`, `stock.warehouse`, `stock.lot`, `stock.return.picking`, `stock.warehouse.orderpoint` | `purchase_id` link, buy route, orderpoint vendor |
| `models/stock_move.py` | `stock.move` | `purchase_line_id`, `created_purchase_line_ids`, valuation sourcing |
| `models/stock_rule.py` | `stock.rule`, `stock.route` | `action='buy'`, PO generation from procurement |
| `models/account_invoice.py` | `account.move` | Anglo-Saxon price difference journal items, incoterm location |
| `models/account_move_line.py` | `account.move.line` | `_get_stock_moves` — trace invoice line to stock moves |
| `models/product.py` | `product.product`, `product.template`, `product.supplierinfo` | `suggested_qty`, `monthly_demand`, vendor display name |
| `models/res_partner.py` | `res.partner` | `on_time_rate`, `group_rfq` |
| `models/res_company.py` | `res.company` | `days_to_purchase` |
| `models/res_config_settings.py` | `res.config.settings` | Settings view |
| `models/stock_reference.py` | `stock.reference` | `purchase_ids` many2many link |
| `models/stock_replenish_mixin.py` | `stock.replenish.mixin` | `show_vendor` for replenish wizard |
| `wizard/stock_replenishment_info.py` | `stock.replenishment.info`, `stock.replenishment.option` | Vendor tab on replenishment info |
| `wizard/product_replenish.py` | `product.replenish` | Vendor-aware date planning |
| `report/stock_forecasted.py` | `stock.forecasted_product_product` | Draft purchase qty in forecast |
| `report/vendor_delay_report.py` | `vendor.delay.report` | Per-vendor, per-product on-time report |
| `report/purchase_report.py` | `purchase.report` | Effective date, days-to-arrival on Purchase Analysis |

---

## `purchase.order` — Extended

**File:** `models/purchase_order.py`
**Inheritance:** Classic (`_inherit = 'purchase.order'`)

### Fields Added by purchase_stock

| Field | Type | Default | Stored | Description |
|---|---|---|---|---|
| `picking_type_id` | Many2one `stock.picking.type` | `_default_picking_type` | Yes | Operation type for the receipt. Domain filters to incoming types. Changing company triggers a new picking type via `_onchange_company_id`. |
| `dest_address_id` | Many2one `res.partner` | `False` | Yes | Drop-ship destination address. Only set when `picking_type_id.code == 'dropship'`. Computed and cleared when picking type changes to non-customer usage via `_compute_dest_address_id`. |
| `incoterm_location` | Char | `False` | Yes | Free-text incoterm delivery location (e.g. "Port of Rotterdam"). Passed through to the vendor bill via `_prepare_invoice`. |
| `picking_ids` | Many2many `stock.picking` | — | Yes | All receipts linked to this PO. Computed via `_compute_picking_ids` from `order_line.move_ids.picking_id`. Store=True ensures it is queryable for domain filters (e.g. late receipt search). |
| `incoming_picking_count` | Integer | — | No | Count of `picking_ids`. Plain `_compute_incoming_picking_count`. |
| `is_shipped` | Boolean | — | No | True when all pickings are `done` or `cancel`. Computed via `_compute_is_shipped`. |
| `effective_date` | Datetime | `False` | Yes | `date_done` of the first completed receipt (excluding returns to supplier). Used to compute on-time delivery by comparing against `date_planned`. Filter: `picking.location_dest_id.usage != 'supplier'`. |
| `receipt_status` | Selection | `False` | Yes | `pending` / `partial` / `full`. `False` when all pickings are cancelled. Computed via `_compute_receipt_status` with full dependency chain on `picking_ids` and their states. |
| `on_time_rate` | Float (related) | — | No | Related to `partner_id.on_time_rate`. `compute_sudo=False` means it is computed with the current user's ACL. |
| `default_location_dest_id_usage` | Selection (related) | — | No | Technical field. Exposes `picking_type_id.default_location_dest_id.usage` to control whether the Drop Ship Address field is shown in the form. |
| `reference_ids` | Many2many `stock.reference` | — | Yes | External references (e.g. delivery notes, carrier tracking). Linked to the picking via `_prepare_picking`. |

### `_compute_receipt_status` Logic

```
if no picking_ids or all cancel   → False
if all done or cancel            → 'full'
if any done                      → 'partial'
otherwise                        → 'pending'
```

### `_compute_effective_date` Logic

```python
pickings = self.picking_ids.filtered(
    lambda x: x.state == 'done'
    and x.location_dest_id.usage != 'supplier'   # exclude returns-to-supplier
    and x.date_done
)
self.effective_date = min(pickings.mapped('date_done'), default=False)
```

**Edge case:** If multiple receipts complete on the same day, `min()` correctly returns the earliest. If all receipts are cancelled, `effective_date` remains `False`.

### `_log_decrease_ordered_quantity` — Performance-Critical Method

Called via `write()` when `order_line` quantity is decreased on an already-confirmed PO (`state == 'purchase'`). This method:

1. Collects all affected PO lines (those whose `product_qty` decreased)
2. Groups their stock moves by `(picking_id, product_id.responsible_id)`
3. Renders a QWeb template `purchase_stock.exception_on_po` as a note
4. Posts the note as an activity on the impacted pickings via `_log_activity`

**Performance implication:** The `_log_activity_get_documents` call inside this method iterates all moves linked to affected lines. On a PO with hundreds of lines and thousands of moves, batch-posting avoids N individual notes but still triggers `move_ids.mapped('picking_id')` which is a SQL query per line.

### `_create_picking` — The Central Business Method

```python
def _create_picking(self):
    for order in self.filtered(lambda po: po.state == 'purchase'):
        # Only for consumable/storable products
        if any(product.type == 'consu' for product in order.order_line.product_id):
            # Reuse existing draft/cancel pickings; only create new if none exist
            pickings = order.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
            if not pickings:
                picking = StockPicking.with_user(SUPERUSER_ID).create(order._prepare_picking())
                pickings = picking
            else:
                picking = pickings[0]
            moves = order.order_line._create_stock_moves(picking)
            moves = moves.filtered(...)._action_confirm()
            # Confirm forward pickings generated by push rules
            forward_pickings = StockPicking._get_impacted_pickings(moves)
            (pickings | forward_pickings).action_confirm()
```

**Key behaviors:**
- **Reuses draft pickings**: If a picking exists in draft, new moves are added to it rather than creating a new picking. This avoids orphaned draft receipts.
- ** SUPERUSER_ID**: Picking creation runs as `SUPERUSER_ID` because the picking's `company_id` may differ from the current user's company (multi-company scenario).
- **`_action_confirm` before `_action_assign`**: Moves are confirmed first so that the assignment logic correctly handles routes and warehouse constraints.
- **Push-rule pickings**: `_get_impacted_pickings` traverses downstream moves created by push rules and confirms them as well, ensuring the full chain is activated.

### `button_approve` Override

```python
def button_approve(self, force=False):
    result = super(PurchaseOrder, self).button_approve(force=force)
    self._create_picking()
    return result
```

Called after the parent `button_approve`. The parent changes state `'to approve' → 'purchase'`. Only then does `_create_picking` fire. If `force=True` (multi-company escalation), picking is still created.

### `button_cancel` Override — Cancellation Cascade

The cancellation logic in purchase_stock is the most complex method in the module. It handles four layers:

1. **Picking cancellation**: All non-done, non-cancel pickings are cancelled.
2. **Move cancellation** (MTO path): Moves linked to MTO procurement are cancelled directly.
3. **Move recompute** (non-MTO downstream): Moves on non-reception routes have their `procure_method` switched from `'make_to_order'` to `'make_to_stock'`, breaking the MTO chain and allowing manual PO creation to re-link.
4. **Unlinking purchase-created moves**: Moves that have `created_purchase_line_ids` more than 1 are unlinked from the PO line rather than cancelled, preserving the reverse-MTO chain.

**Edge case — Done pickings**: If a picking is `done`, it cannot be cancelled. The method logs a note on the picking's chatter instead:

```python
picking.message_post(body=_("The purchase order %s this receipt is linked to was cancelled."))
```

### `retrieve_dashboard` — OTD Calculation

Adds on-time delivery (OTD) metrics to the Purchase dashboard (the kanban view accessible from the app). Looks back 3 months and computes:

```
OTD = count(PO where effective_date <= date_planned) / count(all POs in window) * 100
```

The window and per-user breakdown are computed in Python rather than SQL for readability.

---

## `purchase.order.line` — Extended

**File:** `models/purchase_order_line.py`
**Inheritance:** Classic (`_inherit = 'purchase.order.line'`)

### Fields Added by purchase_stock

| Field | Type | Default | Description |
|---|---|---|---|
| `move_ids` | One2many `stock.move` | — | All stock moves created from this line. Inverse of `stock.move.purchase_line_id`. `readonly=True, copy=False`. |
| `orderpoint_id` | Many2one `stock.warehouse.orderpoint` | `False` | Replenishment rule that triggered the PO line. Used by `_find_candidate` to merge like procurements. Indexed `btree_not_null` for performance. |
| `move_dest_ids` | Many2many `stock.move` | — | Downstream moves that consume this line's receipt. Used in `_prepare_stock_moves` to propagate `qty_to_attach` vs `qty_to_push`. Inverse of `stock.move.created_purchase_line_ids`. |
| `product_description_variants` | Char | `False` | Custom variant description passed from procurement values. Appended to line name for display. |
| `propagate_cancel` | Boolean | `True` | If `True`, cancelling this line cascades to downstream moves. If `False`, downstream moves have `procure_method` set to `'make_to_stock'`. Default `True`. |
| `forecasted_issue` | Boolean | `False` | Computed. True if `virtual_available` at `date_planned` (including this line's qty) is negative. Used in the PO line kanban card to show a warning. |
| `qty_received_method` | Selection | — | Added `('stock_moves', 'Stock Moves')` as a selection option alongside parent's `'manual'` and `'purchase'`. Set automatically for `type == 'consu'` via `_compute_qty_received_method`. |
| `is_storable` | Boolean (related) | — | Related to `product_id.is_storable`. Convenience field. |
| `location_final_id` | Many2one `stock.location` | `False` | Destination location from the procurement that created this line. Used in `_prepare_stock_move_vals` to override destination. |

### `_compute_qty_received_method` — Automatic stock_moves Assignment

```python
def _compute_qty_received_method(self):
    super()._compute_qty_received_method()
    for line in self.filtered(lambda l: not l.display_type):
        if line.product_id.type == 'consu':
            line.qty_received_method = 'stock_moves'
```

Runs at line creation. For `type == 'consu'` products (consumable or storable), the received quantity is tracked directly from `done` stock moves. Service products and lines with `display_type` are excluded.

### `_prepare_qty_received` — Received Qty from Stock Moves

```python
def _prepare_qty_received(self):
    # For stock_moves lines:
    for move in line._get_po_line_moves():
        if move.state == 'done':
            # Skip dropship returns that returned to stock (not to supplier)
            if move.origin_returned_move_id and move.origin_returned_move_id._is_dropshipped() and not move._is_dropshipped_returned():
                pass
            # Skip dropship return that was originally a purchase return
            elif move.origin_returned_move_id and move.origin_returned_move_id._is_purchase_return() and not move.to_refund:
                pass
            # Subtract purchase returns to supplier
            elif move._is_purchase_return():
                if not move.origin_returned_move_id or move.to_refund:
                    total -= move.product_uom._compute_quantity(...)
            else:
                total += move.product_uom._compute_quantity(...)
```

**Edge cases handled:**
- **Dropship returned to stock**: A dropship move whose origin was another dropship move is skipped to avoid double-counting.
- **Purchase returns**: Returns to the supplier subtract from received qty, but only if `to_refund=True` or the return has no origin (standalone return).
- **UoM conversion**: `move.product_uom._compute_quantity(move.quantity, line.product_uom_id)` converts to the PO line's UoM using `HALF-UP` rounding.

### `_get_stock_move_price_unit` — Discounted Price for Valuation

```python
def _get_stock_move_price_unit(self):
    price_unit = self.price_unit_discounted   # price_unit after all discount lines
    # If taxes exist, compute all-tax-inclusive total, then divide by qty
    if self.tax_ids:
        price_unit = self.tax_ids.compute_all(..., rounding_method="round_globally")['total_void'] / qty
    # UoM conversion to product's default UoM
    if self.product_uom_id != self.product_id.uom_id:
        price_unit /= self.product_uom_id.factor
        price_unit *= self.product_id.uom_id.factor
    # Currency conversion if PO currency != company currency
    if order.currency_id != order.company_id.currency_id:
        price_unit = order.currency_id._convert(price_unit, company_currency, company, conversion_date, round=False)
    return float_round(price_unit, precision_digits=price_unit_prec)
```

This method returns the **ex-tax, discounted, UoM-converted, currency-converted** unit price. It is called by both `_prepare_stock_move_vals` (to set `move.price_unit`) and `stock.move._get_value_from_quotation` (for pre-invoice valuation estimates).

**Performance note:** The currency conversion runs on every stock move creation. For a PO with many lines, this can be a bottleneck if the conversion rate requires an API call.

### `_prepare_stock_moves` — Splitting Logic

This method prepares one or two stock move val dictionaries per line:

```
qty_to_attach: qty that should be linked to downstream moves (push chain)
qty_to_push:   qty that should trigger downstream procurement

qty_to_attach = downstream_initial_demand - procurement_qty
qty_to_push   = product_qty - downstream_initial_demand
```

If `qty_to_push > 0`, a second move val dict is created with `move_dest_ids=False` (not linked to downstream moves). This allows the push rule to fire only for the "extra" quantity.

### `_create_or_update_picking` — Dynamic Picking Creation

Called on line `create()` and `write()` when the PO is in `purchase` state. Handles:
- Assigning lines to existing unassigned moves (`moves_to_assign.purchase_line_id = line.id`)
- Creating new stock moves for added/increased lines
- Scheduling an activity on the vendor bill if quantity drops below invoiced

### `_update_qty_received_method` — Migration Hook

```python
def _update_qty_received_method(self):
    self.search(['!', ('state', '=', 'purchase')])._compute_qty_received_method()
```

Called via a migration script (`__init__.py` hook) to retroactively set `qty_received_method = 'stock_moves'` for existing `purchase` state lines on modules that were installed before purchase_stock.

---

## `stock.move` — Extended

**File:** `models/stock_move.py`
**Inheritance:** Classic (`_inherit = 'stock.move'`)

### Fields Added by purchase_stock

| Field | Type | Description |
|---|---|---|
| `purchase_line_id` | Many2one `purchase.order.line` | The PO line that originated this move. `ondelete='set null'`, indexed `btree_not_null`. This is the primary join key between stock and purchase. |
| `created_purchase_line_ids` | Many2many `purchase.order.line` | PO lines created from this move (reverse MTO chain). Used when a stock move triggers PO creation via the `buy` procurement rule. |

### `_prepare_merge_moves_distinct_fields` / `_prepare_merge_negative_moves_excluded_distinct_fields`

Adds `purchase_line_id` and `created_purchase_line_ids` to the set of fields that prevent move merging. This ensures moves from different PO lines are not merged, even if all other attributes match.

**Performance implication:** This increases the cardinality of the move merge candidates. In high-volume receipt scenarios (e.g. receiving hundreds of PO lines on one picking), the merge step may slow down. However, it is necessary for correct invoice-to-receipt matching.

### `_action_synch_order` — Auto-Link Moves to PO Lines

Called when a picking is validated (`_action_done`). For each done move linked to a PO via `picking_id.purchase_id`:
1. If a matching PO line exists for the same product → link it directly.
2. If no matching line → create a new PO line with `product_qty=0` and `qty_received=move.quantity`.

This handles the case where a receipt is created without a pre-existing PO (e.g. receiving an unexpected delivery, then manually matching it to a PO).

### `_get_value_from_account_move` — Invoice-Weighted Valuation

This method is called by `stock_account` when generating valuation entries for moves that have been invoiced. It replaces the standard cost-based valuation with the **invoice-weighted average**:

```python
# Accumulate qty and value from posted invoice lines
for aml in self.purchase_line_id.invoice_lines:
    if aml.move_type == 'in_invoice':
        aml_quantity += aml.product_uom._compute_quantity(aml.quantity, ...)
        value += aml.currency_id._convert(aml.price_subtotal, company_currency, date=aml.date)
    elif aml.move_type == 'in_refund':
        aml_quantity -= ...
        value -= ...

# Subtract qty already valued by earlier moves in the same PO line
other_candidates_qty = sum(move._get_valued_qty() for earlier moves)

# Pro-rate value to the quantity being valued
value = value * ((aml_quantity - other_candidates_qty) / aml_quantity)
```

**Three-way matching at work:** The valuation entry uses the invoiced price rather than the PO price, capturing any price differences. When a vendor bills at a different price than the PO, the difference posts to the price difference account via `_stock_account_prepare_anglo_saxon_in_lines_vals`.

### `_get_value_from_quotation` — Pre-Invoice Valuation Estimate

Called for moves that are done but not yet invoiced. Uses the PO line's discounted price as the estimated value:

```python
price_unit = self.purchase_line_id._get_stock_move_price_unit()
cost_ratio = self._get_cost_ratio(quantity)   # returns quantity (trivial for purchases)
value = price_unit * cost_ratio
description = f"{value} for {quantity} {unit} from {PO name} (not billed)"
```

---

## `stock.picking` — Extended

**File:** `models/stock.py`
**Inheritance:** Classic (`_inherit = 'stock.picking'`)

### Fields Added

| Field | Type | Description |
|---|---|---|
| `purchase_id` | Many2one `purchase.order` (related) | Related to `move_ids.purchase_line_id.order_id`. The PO linked via the move chain. `readonly=True`. |
| `days_to_arrive` | Datetime (computed) | Alias for `date_done` when picking is done and not a return to supplier. Used in kanban card display. Searchable via `_search_days_to_arrive`. |
| `delay_pass` | Datetime (computed) | `purchase_id.date_order` or now. Used to sort receipt kanban cards by age. |

### `_action_done` Override

```python
def _action_done(self):
    self.purchase_id.sudo().action_acknowledge()
    return super()._action_done()
```

Calls `action_acknowledge()` on the PO (defined in the `purchase` base module) to update the received status after the picking completes. Runs as `sudo()` because the picking may have been validated by a user without PO write access.

---

## `stock.rule` — Extended

**File:** `models/stock_rule.py`
**Inheritance:** Classic (`_inherit = 'stock.rule'`)

### `action` Field Extension

Adds `('buy', 'Buy')` to the selection. `ondelete='cascade'` means deleting a buy rule cascades to its route rules.

### `run` Override — Reception Route Augmentation

```python
def run(self, procurements, raise_user_error=True):
    for procurement in procurements:
        routes = procurement.values.get('route_ids')
        if routes and any(r.action == 'buy' for r in routes.rule_ids):
            company = procurement.company_id
            # Add reception route to procurement values
            procurement.values['route_ids'] |= wh.reception_route_id
    return super().run(...)
```

Before delegating to the parent `run`, this method ensures the procurement's route set includes the warehouse's reception route. This allows the MTO chain to continue after the buy rule creates the PO.

### `_run_buy` — The Core Procurement Method

This is the method invoked when a procurement group's rule has `action='buy'`. It:

1. **Groups procurements by PO domain** — groupby `(partner_id, state, picking_type_id, company_id, user_id, currency_id)` plus optional RFQ grouping fields.
2. **Finds or creates a PO** — Uses `_make_po_get_domain` to search for an existing draft PO with matching fields. If found, appends origins. If not found, creates one.
3. **Merges procurement quantities** — `_get_procurements_to_merge` groups by `(product_id, product_uom, propagate_cancel, product_description_variants, orderpoint_id)`. This prevents splitting the same product into multiple PO lines.
4. **Finds or creates PO lines** — `_find_candidate` looks for an existing line with the same product and `propagate_cancel`. If found, updates `product_qty`. If not, creates a new line via `_prepare_purchase_order_line_from_procurement`.
5. **Adjusts PO date_order** — If the new line's `date_planned` minus vendor delay is earlier than the PO's `date_order`, the PO's `date_order` is shifted backward.

**No-supplier failure mode:**
```python
if not supplier:
    if moves.propagate_cancel:
        moves._action_cancel()
    moves.procure_method = 'make_to_stock'   # Break the MTO chain
    self._notify_responsible(procurement)    # Notify via sale_purchase_stock or purchase_mrp
    continue
```
Instead of raising an error, the procurement is silently converted to MTS and the responsible party is notified. This prevents blocking the entire scheduler for one product with no vendor.

### `_get_matching_supplier` — Vendor Selection

```python
def _get_matching_supplier(self, product_id, product_qty, product_uom, company_id, values):
    # Priority 1: explicit supplierinfo from orderpoint
    if values.get('supplierinfo_id'):
        supplier = values['supplierinfo_id']
    # Priority 2: supplier from orderpoint
    elif values.get('orderpoint_id') and values['orderpoint_id'].supplier_id:
        supplier = values['orderpoint_id'].supplier_id
    # Priority 3: _select_seller with quantity/date matching
    else:
        supplier = product_id.with_company(company_id)._select_seller(...)
    # Fallback: any supplier for the product (even with no price defined)
    supplier = supplier or product_id._prepare_sellers(False).filtered(...)[:1]
    return supplier
```

The fallback to a zero-price supplier prevents blocking procurement for products with vendor info but no price on the current date's tier.

### `_get_lead_days` — Cumulative Delay Addition

Adds vendor lead time and `days_to_purchase` to the cumulative delay:
```python
supplier_delay = seller[:1].delay
delays['total_delay'] += supplier_delay
delays['purchase_delay'] += supplier_delay

days_to_order = buy_rule.company_id.days_to_purchase
delays['total_delay'] += days_to_order
```

If no vendor is found, a 365-day placeholder delay is added to prevent orderpoints from being indefinitely stuck.

### RFQ Grouping via Partner Settings

The `_make_po_get_domain` method reads `partner.group_rfq` and `partner.group_on`:

| `group_rfq` | Behavior |
|---|---|
| `'default'` | Group by vendor, picking type, company, buyer, currency (plus `reference_ids` for dropship) |
| `'day'` | Above + `date_planned` on the same day |
| `'week'` | Above + same week (or same specific weekday if `group_on` is 1-7) |
| `'always'` | Same as `'default'` (never split) |

---

## `stock.warehouse` — Extended

**File:** `models/stock.py`
**Inheritance:** Classic (`_inherit = 'stock.warehouse'`)

### Fields Added

| Field | Type | Description |
|---|---|---|
| `buy_to_resupply` | Boolean | Computed from whether the buy route has `product_selectable` rules or is assigned to this warehouse. Inverse writes to `route.warehouse_ids`. Default `True`. |
| `buy_pull_id` | Many2one `stock.rule` | The buy procurement rule for this warehouse. Created/destroyed by `_generate_global_route_rules_values`. |

### `_generate_global_route_rules_values` — Buy Rule Generation

When a warehouse is created or its `reception_steps` / `buy_to_resupply` changes, this method generates the buy rule:

```python
'buy_pull_id': {
    'action': 'buy',
    'picking_type_id': self.in_type_id.id,       # Receipt operation type
    'route_id': buy_route.id,
    'propagate_cancel': self.reception_steps != 'one_step',  # Cancel downstream only for multi-step
}
```

**Odoo 18→19 change:** The `propagate_cancel` default was previously `False` (always). In Odoo 19, it is tied to `reception_steps` — in two-step or three-step receipt, cancelling the buy-side move should propagate to internal transfers.

### `buy_to_resupply` Inverse

When toggled off, the buy route is removed from the warehouse. This does **not** delete the rule or route — it simply unlinks the warehouse from the route, preventing the buy rule from applying to that warehouse.

---

## `res.partner` — Extended

**File:** `models/res_partner.py`
**Inheritance:** Classic (`_inherit = 'res.partner'`)

### Fields Added

| Field | Type | Default | Description |
|---|---|---|---|
| `on_time_rate` | Float | `False` | Percentage of ordered qty received on time (by `date_planned`). Computed from stock moves in the past X days (default 365, configurable via `purchase_stock.on_time_delivery_days` IR config parameter). Returns `-1` if no data. |
| `group_rfq` | Selection | `'default'` | RFQ grouping strategy. `'default'`: group by vendor (MTO excluded). `'day'`: same day. `'week'`: same week. `'always'`: never split. |
| `group_on` | Selection | `'default'` | For `'week'` grouping: which day of the week to group on. `'default'`: based on `date_planned`. `'1'`-`'7'`: specific weekday. |
| `suggest_days` | Integer | `7` | Default number of days to look back for purchase suggestions. |
| `suggest_percent` | Integer | `100` | Default percentage of shortage to suggest ordering. |
| `suggest_based_on` | Char | `'30_days'` | Basis for suggestion: `'30_days'`, `'one_year'`, `'three_months'`, `'actual_demand'`, etc. |

### `_compute_on_time_rate` — Algorithm

```python
# Look back window (default 365 days)
date_order_days_delta = int(config.get_param('purchase_stock.on_time_delivery_days', '365'))
order_lines = search([
    ('partner_id', 'in', self.ids),
    ('date_order', '>', today - delta),
    ('qty_received', '!=', 0),
    ('order_id.state', '=', 'purchase'),
    ('product_id.type', '!=', 'service')
])
# Build qty-on-time per line from done stock moves
moves = search([('purchase_line_id', 'in', order_lines.ids), ('state', '=', 'done')])
moves = moves.filtered(lambda m: m.date.date() <= m.purchase_line_id.date_planned.date())
# on_time_rate = sum(on_time_qty) / sum(ordered_qty) * 100
```

**Edge cases:**
- Lines with `qty_received == 0` are excluded (no data yet)
- Moves that arrived after `date_planned` count as late even if only by one second
- Partners with no qualifying lines get `-1` (displayed as "No data" in the UI)

---

## `product.product` / `product.template` — Extended

**File:** `models/product.py`

### Fields on `product.product`

| Field | Type | Description |
|---|---|---|
| `monthly_demand` | Float | Average monthly outbound qty for the product, computed from done stock moves over a configurable period (`suggest_based_on`). Used to compute `suggested_qty`. |
| `suggested_qty` | Integer | Recommended order qty for the product in the purchase catalog. Computed based on `suggest_based_on`, `suggest_days`, `suggest_percent`, and `warehouse_id` context. |
| `suggest_estimated_price` | Float | Total estimated cost for `suggested_qty` at the current vendor price. |
| `purchase_order_line_ids` | One2many | All PO lines for this product. Used to compute quantities in progress. |

### `suggested_qty` Computation (Three Modes)

**Mode 1 — `actual_demand`:**
```python
if product.virtual_available >= 0:
    continue  # No shortage, no suggestion
suggested_qty = max(ceil(-virtual_available * suggest_percent / 100), 0)
```

**Mode 2 — Historical period (`30_days`, `one_week`, `three_months`, `one_year`, or last-year same month):**
```python
monthly_ratio = suggest_days / (365.25 / 12)   # e.g. 7 days = 0.23 months
qty = monthly_demand * monthly_ratio * suggest_percent / 100
qty -= qty_available + incoming_qty
suggested_qty = max(ceil(qty), 0)
```

**Edge case:** If `suggest_days == 0` or `suggest_percent == 0`, `suggested_qty = 0` — no suggestion is shown.

### `_get_quantity_in_progress` — PO Lines Included in Demand

The purchase extension adds PO lines (both RFQ and confirmed POs) to the "quantity in progress" calculation, which feeds into reorder point checks:

```python
# Lines in draft/sent/to_approve states with this product
rfq_lines = search([
    ('state', 'in', ('draft', 'sent', 'to approve')),
    ('product_id', 'in', self.ids)
])
# Group by order's destination location
for line in rfq_lines:
    if line.orderpoint_id:
        location = line.orderpoint_id.location_id
    elif line.location_final_id:
        location = line.location_final_id
    else:
        location = line.order_id.picking_type_id.default_location_dest_id
    qty_by_product_location[(product.id, location.id)] += product_qty
```

This ensures that when checking whether to trigger a reorder rule, the system accounts for ordered-but-not-yet-received quantities.

---

## `stock.warehouse.orderpoint` — Extended

**File:** `models/stock.py`

### Fields Added

| Field | Type | Description |
|---|---|---|
| `supplier_id` | Many2one `product.supplierinfo` | Pre-selected vendor for this orderpoint. Inverse writes the buy route if `route_id` is empty. |
| `effective_vendor_id` | Many2one `res.partner` (computed) | The vendor used for procurement: `supplier_id` if set, otherwise the default vendor from `_get_default_supplier`. |
| `show_supplier` | Boolean (computed) | True if the effective route contains a buy rule. Used to show/hide the vendor column in the orderpoint kanban. |
| `vendor_ids` | One2many (related) | Related to `product_id.seller_ids`. Convenience for the UI. |

### `show_supplier` — Computed from Route

```python
def _compute_show_supplier(self):
    buy_route = self.env['stock.rule'].search_read([('action', '=', 'buy')], ['route_id'])
    buy_route_ids = [r['route_id'][0] for r in buy_route]
    for orderpoint in self:
        orderpoint.show_supplier = orderpoint.effective_route_id.id in buy_route_ids
```

Uses `search_read` (single query) rather than `search` + `mapped` for efficiency when there are many orderpoints.

---

## `account.move` — Extended

**File:** `models/account_invoice.py`
**Inheritance:** Classic (`_inherit = 'account.move'`)

### `_stock_account_prepare_anglo_saxon_in_lines_vals`

Generates additional journal items for **price difference** when a vendor bill is posted for a product with a different price than its valuation cost. This is the Anglo-Saxon accounting implementation for purchase:

```
Vendor bill (at vendor price):
  Dr. Stock Valuation     $100
  Cr. Accounts Payable              $100

Price difference (if vendor price > cost):
  Dr. Price Difference Exp.   $10
  Cr. Stock Valuation                  $10
```

The method iterates all `in_invoice` / `in_refund` lines and, for each line eligible for stock accounting:
1. Gets `price_unit_val_dif` = vendor price - valuation cost
2. Creates two balancing lines (debit to expense, credit to stock) if the difference is non-zero and the line's `price_unit` matches the PO (no manual discount has been applied)

**L4 edge case:** This method only fires for products with `cost_method == 'standard'`. For FIFO/Average cost methods, price differences are handled by the valuation layer itself, not as separate journal entries.

### `_compute_incoterm_location`

```python
for move in self:
    purchase_locations = move.line_ids.purchase_line_id.order_id.mapped('incoterm_location')
    incoterm_res = next((incoterm for incoterm in purchase_locations if incoterm), False)
```

Reads the `incoterm_location` from all related POs. For multi-PO bills, takes the first non-empty value.

---

## `account.move.line` — Extended

**File:** `models/account_move_line.py`

### `_get_stock_moves` Override

```python
def _get_stock_moves(self):
    return super()._get_stock_moves() | self.purchase_line_id.move_ids
```

Extends the base `_get_stock_moves` (from `stock_account`) by adding the moves linked directly to the invoice line's `purchase_line_id`. This enables the "Valuation" tab on vendor bill lines to show which stock moves received the invoiced goods.

---

## `stock.lot` — Extended

**File:** `models/stock.py`

### `purchase_order_ids` / `purchase_order_count`

```python
def _compute_purchase_order_ids(self):
    for move_line in self.env['stock.move.line'].search([
        ('lot_id', 'in', self.ids), ('state', '=', 'done')
    ]):
        move = move_line.move_id
        if move.picking_id.location_id.usage in ('supplier', 'transit') and move.purchase_line_id.order_id:
            purchase_orders[move_line.lot_id.id] |= move.purchase_line_id.order_id
```

Only lots received from supplier or transit locations are linked. Internal transfers and customer returns are excluded.

---

## Wizard: `stock.replenishment.info`

**File:** `wizard/stock_replenishment_info.py`

Extends the base replenishment info wizard with:
- `supplierinfo_id` — pre-filled from the orderpoint's `supplier_id`
- `supplierinfo_ids` — all vendors for the product (`product_id.seller_ids`)
- `show_vendor_tab` — True unless the orderpoint has a non-buy route (e.g. manufacturing route)

---

## Wizard: `product.replenish`

**File:** `wizard/product_replenish.py`

### `_compute_date_planned` — Vendor Delay Injection

```python
def _compute_date_planned(self):
    super()._compute_date_planned()
    for rec in self:
        if 'buy' in rec.route_id.rule_ids.mapped('action'):
            rec.date_planned = rec._get_date_planned(rec.route_id, supplier=rec.supplier_id, show_vendor=rec.show_vendor)
```

For buy routes, the date calculation uses the vendor's lead time plus `company.days_to_purchase`:
```python
def _get_date_planned(self, route_id, **kwargs):
    supplier = kwargs.get('supplier')
    delay = supplier.delay + self.env.company.days_to_purchase
    return fields.Datetime.add(date, days=delay)
```

---

## Report: `vendor.delay.report`

**File:** `report/vendor_delay_report.py`

A **non-transient** SQL view (`_auto = False`) that provides per-PO-line, per-product, per-vendor on-time metrics:

```sql
SELECT pol.id                   AS id,
       Min(m.date)              AS date,
       pol.product_id           AS product_id,
       pol.partner_id           AS partner_id,
       pol.product_uom_qty      AS qty_total,
       Sum(CASE WHEN m.state = 'done' AND pol.date_planned::date >= m.date::date
            THEN converted_quantity
            ELSE 0 END)        AS qty_on_time
FROM   stock_move m
JOIN   purchase_order_line pol ON pol.id = m.purchase_line_id
GROUP  BY pol.id
```

The `_read_group_select` override for `on_time_rate:sum` computes a **weighted average** (not a simple average):
```sql
CASE WHEN SUM(qty_total) != 0
     THEN SUM(qty_on_time) / SUM(qty_total) * 100
     ELSE 100 END
```

---

## Report: `purchase.report` Extension

**File:** `report/purchase_report.py`

Adds three columns to the Purchase Analysis report:

| Column | SQL Source | Description |
|---|---|---|
| `picking_type_id` | `spt.warehouse_id` | Warehouse of the receipt |
| `effective_date` | Subquery: `MIN(picking.date_done)` | First receipt completion date |
| `days_to_arrival` | `date_planned - COALESCE(effective_date, date_order)` | Days between planned date and actual arrival |

The subquery joins `stock_move → stock_picking` to find the earliest done receipt date for each PO.

---

## L4: Performance, Security, and Edge Cases

### Performance Considerations

1. **`_log_decrease_ordered_quantity` on bulk qty edits**: When `write({'order_line': ...})` is called on a confirmed PO (`state == 'purchase'`), the method pre-fetches all line quantities before `super().write()`, then computes the delta per line in a second loop before calling `_log_activity`. On POs with hundreds of lines, this is two full-ORM loops. Batch line quantity changes where possible.

2. **`_create_picking` reuse logic**: The `pickings = order.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))` query runs on every `_create_picking()` call, including when new lines are added to an existing PO. If a PO accumulates cancelled pickings, the filter must scan all of them each time. Odoo does not auto-vacuum cancelled pickings from the many2many.

3. **`_compute_on_time_rate` — two-pass sudo search**: The method runs a `sudo()` search across all PO lines in the 365-day window, then a second `sudo()` search across all stock moves. Both searches use `load=''` to bypass access rights checks, but a third loop over `order_lines` reads `date_planned`, `partner_id`, `product_uom_qty` as the current user — this is where `compute_sudo=False` applies. The computed value is then stored in the partner record, meaning subsequent reads are cached without re-executing the search.

4. **`suggested_qty` context-dependent `depends_context`**: `suggested_qty` and `monthly_demand` use `depends_context('suggest_days', 'suggest_based_on', 'suggest_percent', 'warehouse_id')`. The purchase catalog kanban triggers recompute for every visible product simultaneously when context values differ, which can cause a cascade of SQL reads across the product kanban.

5. **`vendor.delay.report` SQL view recreation**: The `INIT` method drops and recreates the view on every module upgrade. The view definition joins `stock_move`, `purchase_order_line`, `product_product`, `product_template`, `uom_uom`, `product_category`, `stock_move_line` — a 7-table join over potentially millions of rows. This can lock the table during recreation.

6. **`_prepare_purchase_order` date computation**: `purchase_date = min([value.get('date_order') or fields.Datetime.from_string(value['date_planned']) - relativedelta(days=int(value['supplier'].delay)) for value in values])` iterates all procurement values to find the earliest order date. For large batch procurements (e.g. 500+ orderpoints firing simultaneously), this min-scan is O(n).

7. **`SUPERUSER_ID` on PO line creation**: `_run_buy` creates PO lines via `sudo()` (`self.env['purchase.order.line'].sudo().create(po_line_values)`) to bypass access control for the portal user or stock-user who triggered the procurement. This is safe because the procurement originated from an authorized scheduler, but it means ACLs are not enforced at line creation time.

### Security Considerations

1. **`on_time_rate` implicit data access**: The field on `purchase.order` is defined as `fields.Float(related='partner_id.on_time_rate', compute_sudo=False)`. The related compute on `res.partner` runs `sudo()` to search all PO lines. A user with read access to `purchase.order` can therefore read `on_time_rate` for **every vendor** in the system — not only those on their own POs. This is an information-disclosure risk in multi-tenant or shared-database deployments.

2. **`SUPERUSER_ID` picking creation**: `_create_picking()` uses `with_user(SUPERUSER_ID)` when creating the incoming shipment. In multi-company scenarios, this bypasses inter-company stock restriction rules. The picker creation is intentional to allow warehouse workers without PO access to have receipts created on their behalf, but it means the picking's `company_id` derives solely from the PO's company — not the current user's active company.

3. **`buy_pull_id` post-init hook**: `__init__.py` calls `_create_buy_rules` after all modules are loaded, as `SUPERUSER_ID`. If warehouses already exist from earlier data migrations, the hook creates buy rules for all pre-existing warehouses simultaneously, regardless of the installing user's ACL.

4. **`product_description_variants` line-merge manipulation**: `_get_procurements_to_merge_groupby` uses `product_description_variants` as a merge key. A user with PO line write access can set a unique description variant to prevent their line from merging with others from the same vendor, effectively creating a separate PO for their procurement.

5. **`_get_value_from_account_move` price override**: This method computes valuation from posted invoice lines. If a user manually edits a posted vendor bill line's `price_unit` after posting, the stock valuation is not automatically recomputed — the `_stock_account_prepare_anglo_saxon_in_lines_vals` check on `line.price_unit == line.purchase_line_id.price_unit` prevents this, but any manual override that exactly matches the PO price is silently accepted.

### Historical Changes (Odoo 18 -> 19)

1. **`propagate_cancel` default tied to `reception_steps`**: Previously buy-rule `propagate_cancel` was always `False`. In Odoo 19, the default is `self.reception_steps != 'one_step'`, meaning in two-step or three-step receipt, cancelling the buy-side move propagates to the internal transfer. This is a behavior change that may cause unexpected cascading cancellations in existing deployments.

2. **`group_rfq` / `group_on` RFQ grouping settings**: New in Odoo 19. Before this, all RFQs for the same vendor were grouped into a single draft PO. Now vendors can opt into daily or weekly grouping, or opt out of grouping entirely (`'always'`). This changes the consolidation behavior of the procurement scheduler for existing deployments.

3. **`suggested_qty` context-driven kanban**: Odoo 18 rendered the purchase catalog as a standard tree view; Odoo 19 introduced a kanban view with `suggested_qty` computed directly per product card using context variables. This is a UI change that does not affect API behavior.

4. **`vendor.delay.report` weighted average by quantity**: Odoo 18 computed a simple arithmetic mean of per-line on-time rates. Odoo 19 computes `SUM(qty_on_time) / SUM(qty_total) * 100`, which better reflects actual delivery volume but produces different metrics from what existed in Odoo 18.

5. **`stock.reference` model**: New in Odoo 19. Before this, external references (carrier tracking, delivery note numbers) were stored only in `stock.picking.origin` or `mail.message`. The `stock.reference` model provides a structured join table (`stock_reference_purchase_rel`) linking POs to reference records that can be shared across both purchase receipts and sales deliveries.

6. **`action_add_from_catalog` replaces kanban view**: The purchase catalog entry point (`action_add_from_catalog`) now replaces the standard product kanban with the purchase-specific one. Previously the catalog used the default product view.

7. **`_get_anglo_saxon_price_ctx` downpayment guard**: New in Odoo 19. Sets `move_is_downpayment=True` in the Anglo-Saxon price context when any SO line on the invoice is a downpayment. This prevents downpayment invoice lines from distorting COGS calculations.

8. **SO line `qty_delivered_method` `stock_move` option**: The explicit `'stock_move'` option in the `qty_delivered_method` selection was formalized in Odoo 19. Previously, consumable product delivery tracking relied on the default method without an explicit option in the selection field.

### Edge Cases

1. **Partial receipt then partial invoice**: If a PO has three lines, two are partially received and billed, the third is fully received but not yet billed: `_get_value_from_account_move` correctly pro-rates valuation entries. The `other_candidates_qty` subtraction ensures each move is valued at `invoice_qty / total_invoice_qty * move_qty` on a pro-rata basis.

2. **Dropship return to customer (not to supplier)**: A dropshipped product returned to the customer's location (not back to the supplier) should not subtract from `qty_received`. This is handled by checking `not move._is_dropshipped_returned()` in `_prepare_qty_received`. The move origin is a dropship (supplier -> customer); the return reverses this. The return itself is not a purchase return, so it must not reduce PO received qty.

3. **Service products on PO**: Service lines (`product_id.type == 'service'`) are excluded from `_prepare_stock_moves` by the `type != 'consu'` guard. However they retain `orderpoint_id`, `move_dest_ids`, and `propagate_cancel` for procurement chain tracking. No stock move is ever created for them.

4. **MTO chain broken by cancelled buy move without `propagate_cancel`**: In single-step receipt (`reception_steps == 'one_step'`), `propagate_cancel = False`. When the buy-side move is cancelled, downstream MTO moves have `procure_method` set to `make_to_stock` but their `move_dest_ids` are retained (not cleared by `button_cancel`). This means a manually created PO for the same product can still be linked via `_find_candidate`.

5. **Vendor with no price tier for current date/quantity**: `_get_matching_supplier` falls back to any supplier record (even with `price == 0`) rather than raising an error. This allows procurement to proceed, but the resulting PO line has `price_unit = 0`. The PO must be corrected manually before sending.

6. **Company-currency mismatch at move creation**: `_get_stock_move_price_unit` applies currency conversion at the move creation date using `fields.Date.today()` as the conversion date. If the invoice is paid at a significantly different exchange rate, the valuation entry may differ from the vendor bill amount by the exchange difference.

7. **Zero-vendor-delay edge case**: If `seller.delay == 0` (same-day delivery vendor), `_get_lead_days` adds 0 to `total_delay`. The procurement is still scheduled — same-day arrivals are handled correctly.

8. **PO cancellation with done pickings**: When `button_cancel` is called on a PO that has one or more `done` pickings, those pickings are not cancelled. The method posts a note via `picking.message_post()` on each done picking instead: `"The purchase order %s this receipt is linked to was cancelled."`

9. **Multiple PO lines for same product with different `propagate_cancel`**: `_find_candidate` merges by `(product_id, product_uom, propagate_cancel, product_description_variants, orderpoint_id)`. Lines with the same product but different `propagate_cancel` values will never be merged — they create separate PO lines even within the same PO.

10. **Negative quantity procurement**: `_run_buy` skips procurement with `procurement.product_uom.compare(procurement.product_qty, 0) <= 0` — negative quantities never create PO lines. This prevents return-to-vendor flows from accidentally creating positive PO lines.
---

## See Also

- [Modules/Stock](Stock.md) — Core stock module (`stock.picking`, `stock.move`, `stock.quant`)
- [Modules/Purchase](Purchase.md) — Purchase order module (`purchase.order`, `purchase.order.line`)
- [Modules/stock_account](stock_account.md) — Inventory valuation accounting entries
- [Modules/sale_stock](sale_stock.md) — Sale order to delivery integration, including dropship
- [Modules/stock_dropshipping](stock_dropshipping.md) — Standalone dropshipping without sale order
- [Patterns/Workflow Patterns](Workflow Patterns.md) — State machine and action methods (relevant for `state` field lifecycle)
