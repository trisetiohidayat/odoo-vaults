---
tags:
  - "#odoo19"
  - "#modules"
  - "#sale"
  - "#stock"
  - "#logistics"
description: Links sales orders to warehouse operations — picking generation, delivery scheduling, stock reservation, and automatic procurement triggering.
---

# sale_stock — Sales and Warehouse Management

> **aka**: "Sales and Warehouse Management" | **category**: Sales/Sales
> **depends**: `sale`, `stock_account`
> **auto_install**: `True` (installed automatically when both `sale` and `stock_account` are present)
> **license**: LGPL-3

Links the **sale order lifecycle** to **warehouse and stock operations**. This is the core integration point between the CRM/Sales funnel and the inventory/logistics layer. Without it, confirmed sale orders generate no pickings, no delivery scheduling occurs, and no automatic procurement is triggered.

---

## Module Architecture

```
sale_stock
├── models/
│   ├── sale_order.py          # sale.order extensions: warehouse, picking_policy, dates
│   ├── sale_order_line.py     # sale.order.line extensions: routes, qty widgets, stock rule launch
│   ├── stock.py               # stock.* extensions: move↔SO linking, picking→SO auto-create
│   ├── account_move.py         # account.move extensions: lot reporting, incoterms on invoice
│   ├── product_template.py    # product.template: locks expense_policy and service_type for storable
│   ├── res_company.py         # res.company: security_lead field
│   ├── res_config_settings.py # Settings: default_picking_policy, use_security_lead
│   ├── res_users.py           # res.users: property_warehouse_id (per-user default warehouse)
│   └── stock_reference.py     # stock.reference: sale_ids link (sale↔stock reference join table)
└── data/
    └── sale_stock_data.xml    # Sets sale_selectable=True on stock.route_warehouse0_mto
```

---

## Models

### `sale.order` — Extended by sale_stock

**Inherits**: `sale.order` (from `sale` module)

sale_stock extends the sale order with everything related to physical fulfillment: the warehouse, shipping policy, delivery dates, and delivery status tracking.

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `incoterm` | `Many2one(account.incoterms)` | — | International Commercial Terms. Documents which party bears shipping risk/cost. Shown on sale order form, printed on PDF reports, and propagated to the customer invoice. |
| `incoterm_location` | `Char` | — | Free-text location appended to the Incoterm (e.g., "Port of Hamburg"). Displayed only when set; printed alongside the incoterm code on the report. |
| `picking_policy` | `Selection([direct, one])` | `'direct'` | Controls when pickings are generated. `'direct'` = ship each line as soon as it is ready (partial deliveries, back orders allowed). `'one'` = wait until all lines are ready, then ship everything at once. |
| `warehouse_id` | `Many2one(stock.warehouse)` | computed (see below) | The warehouse used for all stock operations on this order. Determines which `stock.warehouse`'s routes, picking types, and locations are used. |
| `picking_ids` | `One2many(stock.picking, 'sale_id')` | — | All `stock.picking` records linked to this order. Inverse of `stock.picking.sale_id`. Populated via `_compute_sale_id` on `stock.picking` (not directly by the SO). |
| `delivery_count` | `Integer` (computed) | — | Count of `picking_ids`. Displayed in the stat button on the SO form. |
| `delivery_status` | `Selection` (computed, stored) | `False` | One of: `'pending'` (no picking done), `'started'` (some done), `'partial'` (some done AND some lines partially delivered), `'full'` (all done or cancelled). Evaluated against `picking_ids` states and `order_line.qty_delivered`. Color-coded in list view: blue/orange/green. |
| `late_availability` | `Boolean` (computed, searchable) | — | `True` if any related picking has `products_availability_state == 'late'` (i.e., stock was unavailable when the picking was supposed to be confirmed). Used in the search filter "Late Availability". |
| `stock_reference_ids` | `Many2many(stock.reference)` | — | Links the SO to `stock.reference` records. Used to track cross-document references (e.g., HS codes, customs info) shared between purchase receipts and sales deliveries. |
| `effective_date` | `Datetime` (computed, stored) | — | The `date_done` of the **first** completed customer delivery picking (`location_dest_id.usage == 'customer'`). Set when a delivery is validated. Propagated to `account.move.delivery_date` on the customer invoice. |
| `expected_date` | `Datetime` | — | Delivery date promised to the customer, computed from lead times. The `sale_stock` override of the base `_compute_expected_date` defers to the parent method but respects `picking_policy`. In `'direct'` mode it takes the minimum lead time; in `'one'` mode it takes the maximum lead time across all lines. |
| `json_popover` | `Char` (computed) | — | JSON blob for the `stock_rescheduling_popover` widget. Contains list of late pickings with `id`, `name`, and `model`. Only shown when `show_json_popover` is `True`. |
| `show_json_popover` | `Boolean` (computed) | — | `True` if any picking has a `delay_alert_date` set. Triggers the late-delivery popover widget on the SO form's "Other Information" tab. |

#### `warehouse_id` Computation — `_compute_warehouse_id`

The warehouse is determined by this priority chain:

1. **Per-company `ir.default`** — if a system default is set for `warehouse_id` on `sale.order`, that wins.
2. **User's `property_warehouse_id`** — the sales person's personal default warehouse (from `res.users.property_warehouse_id`).
3. **Fallback** — `stock.warehouse.search([], limit=1)` (first active warehouse for the company).

The `_init_column` hook bypasses the normal ORM `default_get` during first install/migration to avoid a crash when `property_warehouse_id` (a property field created at `__init__` time) does not yet exist as a column.

#### `expected_date` Computation — `_compute_expected_date` + `_select_expected_date`

```
direct policy  → min(lead_times)          # ship whatever is ready first
one policy     → max(lead_times)          # wait for everything
```

This is why changing `picking_policy` after order confirmation still shifts the expected delivery date — the computation is re-evaluated whenever `picking_policy` changes.

#### `delivery_status` Logic — `_compute_delivery_status`

```
if no pickings or all cancelled         → False
elif all done or cancelled               → 'full'
elif any done AND any line qty_delivered → 'partial'
elif any done                           → 'started'
else                                    → 'pending'
```

The `'partial'` state specifically requires that at least one SO line has a non-zero `qty_delivered` — this covers the case where a line is partially shipped but not fully delivered.

#### `effective_date` Computation — `_compute_effective_date`

Only pickings where:
- `state == 'done'`
- `location_dest_id.usage == 'customer'`

are considered. The `min()` of all their `date_done` values is taken — the **earliest** completed delivery. This is the delivery date shown on the printed invoice and the one used in reporting.

#### `write()` — Special Behaviors

**`commitment_date` propagation**:
```python
if 'commitment_date' in values:
    for order in self:
        moves = order.order_line.move_ids.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.location_dest_id.usage == 'customer'
        )
        moves.date_deadline = values.get('commitment_date') or order.expected_date
```
Changing the commitment date retroactively updates the `date_deadline` on all **undone** outgoing moves. This is a one-way propagation — moves already done are not adjusted.

**Quantity decrease on confirmed SO**:
When `order_line` vals are written and the SO is already `sale`, it pre-fetches the old quantities, then after `super().write()` compares them. Any line whose `product_uom_qty` decreased triggers `_log_decrease_ordered_quantity()` via the stock picking activity system. This creates a warning activity on the related picking for a user to review.

**`partner_shipping_id` change**:
- Without `update_delivery_shipping_partner` context: schedules a mail activity on pending pickings warning that the partner may need updating.
- With `update_delivery_shipping_partner` context: silently updates `picking_ids.partner_id`.

#### `_action_confirm()` — Trigger Point for Stock Rules

```python
def _action_confirm(self):
    self.order_line._action_launch_stock_rule()   # THIS triggers procurement
    return super()._action_confirm()
```

This is the **critical integration hook**. When a SO moves from Quotation → Sales Order, it calls `_action_launch_stock_rule` on each line, which creates procurement orders and (if routes are configured) triggers `stock.rule.run()` — producing `stock.picking` records, purchase orders (for MTO/buy routes), or manufacturing orders (for make-to-order routes).

#### `_action_cancel()` — Cascading Cancel

1. Collects all SO lines with their current `product_uom_qty`.
2. Calls `picking_ids.filtered(state != 'done').action_cancel()` — cancels all pending pickings.
3. Calls `_log_decrease_ordered_quantity(..., cancel=True)` — logs cancellation activity on cancelled pickings.

#### `action_view_delivery()` → `_get_action_view_picking()`

Returns the `stock.action_picking_tree_all` action, constrained to this order's `picking_ids`. If exactly one picking, opens in form view; if multiple, opens in list view. Sets `default_partner_id` and `default_picking_type_id` in context. Prefers the outgoing picking if one exists.

#### `_prepare_invoice()` — Incoterms and Delivery Date to Invoice

```python
def _prepare_invoice(self):
    invoice_vals = super()._prepare_invoice()
    invoice_vals['invoice_incoterm_id'] = self.incoterm.id
    invoice_vals['delivery_date'] = self.effective_date
    return invoice_vals
```

The `effective_date` is the first completed delivery date — used as the invoice's `delivery_date` for fiscal reporting in some countries (e.g., Italy, Spain for intracommunity VAT).

---

### `sale.order.line` — Extended by sale_stock

**Inherits**: `sale.order.line` (from `sale` module)

#### Fields

| Field | Type | Computation | Description |
|---|---|---|---|
| `qty_delivered_method` | `Selection` | extended | Adds `'stock_move'` as an option. Consumable products (`type == 'consu'`) that are not expenses use `stock_move` delivery tracking. |
| `route_ids` | `Many2many(stock.route)` | — | Stock routes applied to this line. Domain: `sale_selectable = True`. Constrained by `ondelete='restrict'` — routes cannot be deleted if used on an SO line. Controls which `stock.rule` entries are fired on confirmation. |
| `move_ids` | `One2many(stock.move, 'sale_line_id')` | — | All `stock.move` records created from this SO line. Set automatically by `stock.rule.run()` when procurement runs. |
| `virtual_available_at_date` | `Float` | `_compute_qty_at_date` | Virtual stock at the scheduled delivery date (accounts for other expected moves). Used in the qty-at-date widget. |
| `scheduled_date` | `Datetime` | `_compute_qty_at_date` | The delivery date used for the qty computation: `commitment_date` if set, else `order_id.expected_date`. Used in the qty-at-date widget display. |
| `forecast_expected_date` | `Datetime` | `_compute_qty_at_date` | When the stock is expected to arrive based on in-flight moves. Computed from `stock.move.forecast_expected_date` rolling up the move chain. |
| `free_qty_today` | `Float` | `_compute_qty_at_date` | Immediate available stock (on-hand minus reserved). Used in the qty-at-date widget. |
| `qty_available_today` | `Float` | `_compute_qty_at_date` | Total on-hand stock today. Used in the qty-at-date widget. |
| `warehouse_id` | `Many2one(stock.warehouse)` | `_compute_warehouse_id` (stored) | The warehouse for this line. Usually mirrors `order_id.warehouse_id` but is overridden if a `route_id` pulls from a different warehouse (e.g., cross-warehouse dropship route). |
| `qty_to_deliver` | `Float` | `_compute_qty_to_deliver` | `product_uom_qty - qty_delivered`. Negative values indicate over-delivery. |
| `is_mto` | `Boolean` | `_compute_is_mto` | `True` if the product's route includes the warehouse's MTO route. When `True`, the availability check in the qty widget is skipped (MTO/dropship products are not checked against warehouse stock). |
| `display_qty_widget` | `Boolean` | `_compute_qty_to_deliver` | `True` only for storable products in `draft/sent/sale` states where some qty remains undelivered and at least one move is not `done`/`cancel`. Controls whether the qty-at-date widget is rendered on the form. |
| `is_storable` | `Boolean` | related to `product_id.is_storable` | Read-only convenience flag. |
| `customer_lead` | `Float` | `_compute_customer_lead` / `_inverse_customer_lead` | Delivery lead time in days from `product_id.sale_delay`. Precomputed on line creation and editable. The `_inverse_customer_lead` propagates the value as `date_deadline` on related stock moves when the SO is in `sale` state and has no `commitment_date`. |

#### `_compute_qty_at_date()` — How the Qty Widget Works

This is the most complex computed method in the module. It runs in two distinct modes:

**Mode 1 — `state == 'sale'` (confirmed order):**
```
Roll up move chain via _rollup_move_origs()
  → Filter moves for this line's product, state not in (done, cancel)
  → forecast_expected_date = max(move.forecast_expected_date for all rolled-up moves)
  → qty_available_today    = sum(move.quantity for in-flight moves)
  → free_qty_today          = sum(move.product_id.forecast_availability for each move)
  → virtual_available_at_date = False (not needed for confirmed orders)
```
This mode reads from **already-created stock moves** because the picking exists and moves have already been generated. It shows what is already in motion for this specific line.

**Mode 2 — `state in ('draft', 'sent')` (quotation):**
```
Group lines by (warehouse_id, scheduled_date)
  → Batch-read qty_available, free_qty, virtual_available for all products
  → Subtract already-processed qty per product to avoid double-counting across lines
  → Apply UoM conversion if product_uom differs from product's default UoM
```
The batched read is a performance optimization — reading product quantities per group rather than per line, then subtracting already-allocated quantities per product to prevent over-reporting when multiple lines reference the same product.

The `scheduled_date` for quotation lines is `order_id.commitment_date or line._expected_date()` — the same date that will become the delivery deadline.

#### `_compute_warehouse_id()` — Route-Driven Warehouse Override

If `route_ids` are set, it searches `stock.rule` for rules on those routes that pull to the customer's location, then selects the `location_src_id.warehouse_id` of the best matching rule. This allows a SO to drive procurement from a warehouse other than the one on the order header (e.g., a vendor's warehouse for a dropship route).

Preference order for rules:
1. Rules whose `location_src_id.warehouse_id` matches `order_id.warehouse_id`
2. Rules with no warehouse restriction
3. All others (sorted by `route_sequence`, then `sequence`)

#### `_compute_is_mto()` — When Is MTO Detected?

```
is_mto = True  iff:
  1. display_qty_widget is True (storable product on active SO)
  2. warehouse_id.mto_pull_id.route_id exists OR 'stock.route_warehouse0_mto' global route exists
  3. That MTO route is in (line.route_ids + product.route_ids + product.categ_id.total_route_ids)
```

If the MTO route is found on the product or its category, the line is flagged as MTO and the stock availability check is bypassed — because MTO products are procured specifically for this order and their availability is guaranteed by the procurement, not by warehouse stock.

#### `_get_outgoing_incoming_moves(strict=True)` — Delivery Qty Calculation

This is the core logic for `_prepare_qty_delivered()`. It separates moves into outgoing (going to customer) and incoming (returns from customer).

**`strict=True` (default)**:
- Outgoing: `location_dest_id._is_outgoing()` — standard delivery move logic.
- Incoming: `to_refund=True` AND (`_is_incoming()` OR `location_id._is_outgoing()`) — return/refund moves.

**`strict=False`**:
- Only considers moves triggered by the **initial rule** (first rule that started the chain). This supports push mechanisms where intermediate moves are created after the initial procurement — those intermediate moves are not counted as triggering moves.
- Tracks `triggering_rule_ids` per warehouse to identify which rule started each move chain.

The `strict=False` mode is used by `_action_launch_stock_rule` to determine how much was already procured (for recomputation after a qty change on a confirmed order).

#### `_action_launch_stock_rule()` — Procurement Trigger

```
Called from:
  - sale_order._action_confirm()        [on order confirmation]
  - sale_order_line.create()            [on new line added to confirmed SO]
  - sale_order_line.write(product_uom_qty) [on qty change of confirmed SO line]

Logic per line:
  1. Skip if: state != 'sale', order locked, or product.type != 'consu'
  2. Compute qty = _get_qty_procurement(previous_product_uom_qty)
     (compares existing moves to current product_uom_qty)
  3. If qty < product_uom_qty → create procurement for the delta
  4. Adjust UoM for the procurement (line UoM → product's default UoM)
  5. Run stock.rule.run(procurements) → fires applicable stock.rule records
  6. Confirm any pending pickings on the parent order (scheduler trigger)
```

The final step — confirming pending pickings after procurement — is specifically noted as a workaround. Normally the scheduler is triggered by picking confirmation, but this module also triggers it from stock.move confirmation. This ensures chained procurements (e.g., MTO → buy → receipt) are properly sequenced.

#### `_prepare_procurement_values()` — What Gets Passed to Stock Rule

```python
{
    'origin': self.order_id.name,              # SO reference on PO/MO/transfer
    'reference_ids': self.order_id.stock_reference_ids,  # HS codes, refs
    'sale_line_id': self.id,                   # back-link to SO line
    'date_planned': date_deadline - timedelta(days=company_id.security_lead),
    'date_deadline': date_deadline,            # commitment_date or expected_date
    'route_ids': self.route_ids,               # routes for this line
    'warehouse_id': self.warehouse_id,         # warehouse (possibly overridden)
    'partner_id': self.order_id.partner_shipping_id.id,  # delivery address
    'location_final_id': self.order_id.partner_shipping_id.property_stock_customer,
    'product_description_variants': ...,       # localized product name
    'company_id': self.order_id.company_id,
    'sequence': self.sequence,                  # preserves SO line ordering
    'never_product_template_attribute_value_ids': self.product_no_variant_attribute_value_ids,
    'packaging_uom_id': self.product_uom_id,   # UoM for packaging
}
```

The `security_lead` (company's Sales Safety Days) shifts `date_planned` earlier by that many days — ensuring the company always has a buffer before the promised delivery date.

#### `_update_line_quantity()` — Guard Against Reducing Below Delivered

```python
if float_compare(new_qty, max(line_products.mapped('qty_delivered')), ...) < 0:
    raise UserError("The ordered quantity of a sale order line cannot be decreased
                     below the amount already delivered.")
```
This prevents a sales person from reducing the ordered qty below what has already been shipped. To reduce an over-shipped line, a return must be created in inventory.

---

### `stock.route` — Extended by sale_stock

**Inherits**: `stock.route` (from `stock` module)

#### Fields

| Field | Type | Description |
|---|---|---|
| `sale_selectable` | `Boolean` | Set to `True` by this module. Marks the route as available for selection on `sale.order.line.route_ids`. The MTO route (`stock.route_warehouse0_mto`) is specifically marked selectable via `sale_stock_data.xml`. |

---

### `stock.move` — Extended by sale_stock

**Inherits**: `stock.move` (from `stock` module)

#### Fields

| Field | Type | Description |
|---|---|---|
| `sale_line_id` | `Many2one(sale.order.line)` | The SO line that originated this move. Indexed `btree_not_null`. Used throughout the ORM to link moves back to their selling counterpart — this is the primary join key between `stock` and `sale`. |

#### `_action_synch_order()` — Auto-Create SO Line from Picking

Triggered when a delivery picking is validated without being linked to an existing SO line (e.g., a manual delivery note). It:

1. Finds the `sale_id` from the picking's `reference_ids.sale_ids`.
2. If a SO line already exists for this product on the SO, links the move to it.
3. If no SO line exists, **creates a new SO line** with:
   - `product_uom_qty = 0` (no ordered qty — this was a delivery not tied to an order)
   - `qty_delivered = move.quantity` (or negated for returns)
   - `price_unit = so_line[0].price_unit` if the product uses `invoice_policy == 'delivery'`, else `0`
4. Bypasses procurement with `skip_procurement=True` context.

This is the mechanism that allows ad-hoc deliveries to be later matched to a sale order, or for returned products to automatically create a return SO line.

#### `_prepare_merge_moves_distinct_fields()`

Adds `sale_line_id` to the list of fields that prevent move merging. Moves from different SO lines are **never merged**, even if all other attributes match. This ensures accurate SO line → move tracking.

#### `_get_related_invoices()`

```python
invoices = self.mapped('picking_id.sale_id.invoice_ids').filtered(lambda x: x.state == 'posted')
```
Overridden from `stock_account` to include customer invoices linked through the picking's `sale_id` (in addition to those found via `stock.move.invoice_lines`). This ensures invoice traceability for COGS and Anglo-Saxon valuation even when the move-to-invoice link is indirect.

#### `_assign_picking_post_process()`

Posts a `mail.message_origin_link` note on the picking linking it back to the originating SO. The message is rendered using the `mail.message_origin_link` template, creating a visible "Linked to Sale Order X" banner on the picking.

#### `_prepare_procurement_values()`

Passes `sale_line_id` through to child procurements (e.g., from a stock move to a purchase order line or manufacturing order). This preserves the lineage from the final delivery all the way back to the MTO/buy/manufacture procurement.

#### `_reassign_sale_lines()` — Picking→SO Reassignment

When a picking is manually reassigned to a different SO (via the `sale_id` inverse on `stock.picking`), this method propagates the reassignment to all moves:

```python
# For each move, find a matching product line in the new SO
line_ids_by_product = {
    product_id: [line_id, ...]  # from new SO
}
# Assign to first matching line, or unlink if none exists
```

#### `write()` — Product Change Unlinks Sale Line

If `product_id` is changed on a move that already has a `sale_line_id`, the `sale_line_id` is set to `False`. The move is no longer attributable to the original order line, and the old link is severed.

---

### `stock.picking` — Extended by sale_stock

**Inherits**: `stock.picking` (from `stock` module)

#### Fields

| Field | Type | Description |
|---|---|---|
| `sale_id` | `Many2one(sale.order)` (computed/inverse, stored, indexed) | The SO linked to this picking. Computed from `move_ids.sale_line_id.order_id` or from `reference_ids.sale_ids`. Has a manual setter `_set_sale_id` that creates a `stock.reference` record if needed and calls `_reassign_sale_lines()`. |

#### `_compute_sale_id()` — Dual Source Resolution

The SO is found by:
1. Following `move_ids.sale_line_id.order_id` (preferred — traverses the move chain).
2. If no moves have a `sale_line_id`, falls back to `reference_ids.sale_ids`.

This handles both rule-generated pickings (with `sale_line_id`) and manually created pickings (with only `stock.reference`).

#### `_compute_move_type()` — Picking Move Type from SO Policy

```python
if any so.picking_policy == "direct" → picking.move_type = "direct"
else                                  → picking.move_type = "one"
```
Mirrors the SO's `picking_policy` into the picking's `move_type` so that the delivery behaves consistently with the order's shipping preference.

#### `_action_done()` — Auto-Create SO Line from Validated Picking

Same logic as `stock.move._action_synch_order()` but executed in the picking's `_action_done()` flow. Creates new SO lines (with `product_uom_qty=0`) for any picking move that arrives at the customer without a pre-existing SO line link. Skips moves that already have a `sale_line_id`, moves not yet marked as picked (`not move.picked`), and moves with downstream destinations (`move.move_dest_ids`).

#### `_log_less_quantities_than_expected()`

Overridden to log activity on the **sale order** (grouped by `sale_line_id.order_id` and `order_id.user_id`) when fewer units were processed than expected on a delivery. The rendered QWeb template `sale_stock.exception_on_picking` is used. The parent call to `super()` handles the stock-level logging.

#### `_can_return()`

```python
return super()._can_return() or self.sale_id
```
Extends the return-ability check: a picking linked to a SO can always be returned (even if the parent `stock.picking` logic would block it for other reasons). This ensures full return-from-delivery functionality is available for all sale-related pickings.

---

### `stock.lot` — Extended by sale_stock

**Inherits**: `stock.lot` (from `stock` module)

#### Fields

| Field | Type | Description |
|---|---|---|
| `sale_order_ids` | `Many2many(sale.order)` (computed) | All SOs whose deliveries included this lot. Computed by searching done `stock.move.line` records with this lot, filtered to moves with a `sale_line_id` and where `location_dest_id.usage in ('customer', 'transit')`. Includes an access check — only adds SO the current user can read. |
| `sale_order_count` | `Integer` (computed) | Count of `sale_order_ids`. Displayed in the stat button on the lot form. |

---

### `stock.rule` — Extended by sale_stock

**Inherits**: `stock.rule` (from `stock` module)

#### `_get_custom_move_fields()`

Adds `sale_line_id`, `partner_id`, `sequence`, and `to_refund` to the list of fields copied from the procurement into the generated `stock.move`. This ensures these fields are propagated correctly when the stock rule creates its move.

---

### `stock.move.line` — Extended by sale_stock

**Inherits**: `stock.move.line` (from `stock` module)

#### `_should_show_lot_in_invoice()`

```python
return 'customer' in {location_id.usage, location_dest_id.usage} \
   or inter_company_location in (location_id, location_dest_id)
```
Overridden to include moves **from** the customer (returns) alongside standard **to** the customer (deliveries). Both directions are relevant to lot-based invoicing.

---

### `account.move` — Extended by sale_stock

**Inherits**: `account.move` (from `account` module)

#### `_stock_account_get_last_step_stock_moves()`

Augments the parent from `stock_account` to handle returns. For `out_refund`, it includes both:
- Moves from `reversed_entry_id.invoice_line_ids.sale_line_ids.move_ids` (the original delivery)
- Moves from `invoice_line_ids.sale_line_ids.move_ids` (the refund's own SO line moves)

This ensures the Anglo-Saxon COGS entry correctly references the original delivery move even for refunds.

#### `_get_invoiced_lot_values()` — Lot Reporting on Invoice PDF

Complex reconciliation logic that matches lot-level move lines to invoiced quantities. Key behaviors:

- **Pagination**: Uses `all_invoices_amls[:index]` to determine which lots were on prior invoices — only shows lots from the **current invoice** that have not been fully allocated to previous invoices.
- **Returns handled**: For `out_refund`, signs are swapped (negative qties printed). For `out_invoice`, it filters out invoices that have been fully reversed (`payment_state == 'reversed'`).
- **Stock return detection**: A move from `customer → internal` on an invoice is a stock return, and its lot qty is reconciled against the return flow.
- **Over-delivery on returns**: If a return asks for more than was delivered, the surplus is zeroed out.
- **Sudo access**: The lot record is accessed as superuser to avoid access errors when the invoice user lacks stock permissions.

#### `_compute_delivery_date()`

```python
effective_date_res = max(sale_order_effective_date)  # for multiple SOs
if effective_date_res:
    move.delivery_date = effective_date_res
```
Takes the **maximum** `effective_date` across all SOs on the invoice (the latest completed delivery among all lines). Propagated from `sale.order.effective_date`.

#### `_compute_incoterm_location()`

Takes the **first non-empty** `incoterm_location` from any SO line on the invoice (via `next()` short-circuit). Propagated from `sale.order.incoterm_location`.

#### `_get_anglo_saxon_price_ctx()`

Adds `move_is_downpayment=True` to the Anglo-Saxon price computation context when any invoice line has an `is_downpayment` SO line. This prevents downpayment lines from distorting the COGS calculation.

#### `_get_protected_vals()` — Permanent Field Protection

Extends the field protection list to permanently protect `delivery_date` from any write on `account.move.line` records that belong to this move. This prevents localization or automation rules from accidentally overwriting the delivery date.

---

### `account.move.line` — Extended by sale_stock

**Inherits**: `account.move.line` (from `account` module)

#### `_get_stock_moves()`

```python
return super() | self.sale_line_ids.move_ids
```
Adds moves from SO lines to the stock move set used for COGS and Anglo-Saxon valuation. This extends the parent method from `stock_account` to include moves directly linked to the invoice line's SO lines.

#### `_sale_can_be_reinvoice()`

Blocks `entry` move types and `cogs` display type lines from being considered for sale reinvoicing. The `cogs` lines are automatically generated by Anglo-Saxon accounting and should not be reinvoiced.

#### `_get_cogs_qty()` / `_get_posted_cogs_value()`

Augmented to include **already-posted** COGS from `out_invoice` lines of the same SO. The `posted_cogs_qty` and `posted_cogs_value` are accumulated from all posted customer invoices for the same product in the same SO, preventing double-counting of COGS when multiple invoices are created for one SO.

---

### `product.template` — Extended by sale_stock

**Inherits**: `product.template` (from `product` module)

#### `_compute_expense_policy()`

```python
self.filtered(lambda t: t.is_storable).expense_policy = 'no'
```
**L4 — Performance/Integrity**: Storable (stockable) products are **hardlocked** to `expense_policy = 'no'`. This prevents service-type expense tracking on physical goods, which would produce meaningless data. This is a one-way lock: storable products cannot have an expense policy.

#### `_compute_service_type()`

```python
self.filtered(lambda t: t.is_storable).service_type = 'manual'
```
Similarly locks `service_type` to `'manual'` for storable products, preventing them from being automatically classified as time-based services.

---

### `stock.reference` — Extended by sale_stock

**Inherits**: `stock.reference` (from `stock` module)

#### Fields

| Field | Type | Description |
|---|---|---|
| `sale_ids` | `Many2many(sale.order)` | Many-to-many link table. Join table: `stock_reference_sale_rel`. Enables a single `stock.reference` record to track references across both purchase receipts and sales deliveries (e.g., a customs HS code shared between a PO line and the resulting SO line). |

---

### `res.company` — Extended by sale_stock

**Inherits**: `res.company` (from `base` module)

#### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `security_lead` | `Float` | `0.0` | Sales Safety Days. Buffer subtracted from delivery deadlines before scheduling procurement. For example, `security_lead = 2` means the system schedules procurement to arrive 2 days before the promised date, providing a buffer for handling unexpected delays. Applied in `_prepare_procurement_values()` as `date_planned = date_deadline - timedelta(days=security_lead)`. |

---

### `res.users` — Extended by sale_stock

**Inherits**: `res.users` (from `base` module)

#### Fields

| Field | Type | Description |
|---|---|---|
| `property_warehouse_id` | `Many2one(stock.warehouse)` (company-dependent) | Per-user default warehouse. Checked in `sale.order._compute_warehouse_id()`. Allows sales people to default to their assigned warehouse even if the system has other warehouses configured. Used when the per-company `ir.default` is not set. |

---

## View Integration

### Sale Order Form (`sale.order.form`)

**Warehouse selector** (`warehouse_id`): Displayed in the "Delivery" group alongside `incoterm`, `incoterm_location`, and `picking_policy`. Readonly after `state == 'sale'`.

**Incoterm block**: `incoterm` (no open, no create) + `incoterm_location` (free text) are shown in the delivery group before `picking_policy`.

**Delivery stat button**: `action_view_delivery` button with truck icon. Shows `delivery_count`. Only visible when `delivery_count > 0`.

**Expected date span**: Conditional visibility: hidden when both `effective_date` and `commitment_date` are set.

**Delivery status badge**: Rendered inline in the form beneath the commitment date. Color-coded (blue/orange/green) via CSS decoration attributes.

**Late delivery popover**: `stock_rescheduling_popover` widget rendered on the "Other Information" tab when `show_json_popover` is `True`.

**SO Line form**: `route_ids` (many2many_tags, `stock.group_adv_location`) and `qty_at_date_widget` inserted into the line's form view.

**SO Line list/kanban**: `route_ids` shown as tags column (optional, hidden by default). `qty_at_date_widget` replaces the qty_delivered cell as a widget.

### Sale Order List Views

- **`sale_order_tree`**: Adds optional `warehouse_id` column (hidden by default, `stock.group_stock_multi_warehouses`).
- **`view_order_tree`**: Adds `delivery_status` badge column (colored, optional) and conditional `commitment_date` red decoration for overdue/partial deliveries.

### Picking Form (`stock.picking.form`)

Adds `sale_id` field before `move_type`. Provides the SO link directly on the picking header.

### Lot Form (`stock.lot.form`)

Adds "Sales" stat button (same style as "Moves" button) showing `sale_order_count`. Clicking opens the SO list filtered to SOs that delivered this lot.

---

## Security Model

### Record Rules

**`stock_picking_rule_portal`** (Portal users only):
```
domain_force: '|',
    ('partner_id', '=', user.partner_id.id),
    ('sale_id.partner_id', '=', user.partner_id.id)
```
Portal users see pickings where **either** the picking's partner is themselves **or** the picking's linked SO's partner is themselves. This covers both direct and indirect (SO-mediated) access.

### Access Control List Entries

| Record | Model | Group | R | W | C | D |
|---|---|---|---|---|---|---|
| `access_stock_picking_salesman` | `stock.picking` | `sales_team.group_sale_salesman` | 1 | 1 | 1 | 0 |
| `access_stock_move_salesman` | `stock.move` | `sales_team.group_sale_salesman` | 1 | 1 | 1 | 0 |
| `access_stock_move_manager` | `stock.move` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |
| `access_sale_order_stock_worker` | `sale.order` | `stock.group_stock_user` | 1 | 1 | 0 | 0 |
| `access_sale_order_line_stock_worker` | `sale.order.line` | `stock.group_stock_user` | 1 | 1 | 0 | 0 |
| `access_stock_picking_sales` | `stock.picking` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |
| `access_stock_picking_portal` | `stock.picking` | `base.group_portal` | 1 | 0 | 0 | 0 |
| `access_stock_warehouse_user` | `stock.warehouse` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 |
| `access_stock_location_user` | `stock.location` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 |
| `access_stock_warehouse_orderpoint_sale_salesman` | `stock.warehouse.orderpoint` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 |
| `access_stock_rule_salemanager` | `stock.rule` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |
| `access_stock_rule` | `stock.rule` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 |
| `access_stock_package_type_salesman` | `stock.package_type` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 |

**Key insight**: Sales people can **read/write** `stock.picking` and `stock.move` but cannot **create** or **delete** them. Only `sales_team.group_sale_manager` has full access. Conversely, `stock.group_stock_user` (warehouse workers) can read/write SOs but not create or delete them. This is a cross-functional read/write ACL, not a security boundary.

---

## Configuration Settings

| Setting | Field | Scope | Description |
|---|---|---|---|
| Default Picking Policy | `default_picking_policy` | Company default | Sets `'direct'` or `'one'` as the default for new SOs. Shown in Settings → Sales → Delivery. |
| Sales Safety Days | `use_security_lead` + `security_lead` | Company | Enables/disables and sets the safety lead time. When disabled, `security_lead` is reset to `0.0`. Shown in Settings → Inventory → Routes. |

---

## Cross-Module Integration Map

```
sale.order ─────────────────────────────────────────────────────
  │  warehouse_id          → stock.warehouse
  │  incoterm              → account.incoterms
  │  picking_policy        → stock.picking.move_type
  │  commitment_date       → stock.move.date_deadline
  │  effective_date        → account.move.delivery_date
  │
  ├─ sale.order.line ────────────────────────────────────────
  │    route_ids           → stock.route (sale_selectable)
  │    move_ids            → stock.move (sale_line_id back-link)
  │    warehouse_id        → stock.warehouse (per-line override)
  │    customer_lead       → stock.move.date_deadline
  │    qty_delivered       ← stock.move (stock_move method)
  │    is_mto              ← stock.route (MTO detection)
  │
  └─ stock.picking ────────────────────────────────────────────
       sale_id             → sale.order (compute+inverse)
       reference_ids       → stock.reference ← sale.order.stock_reference_ids
       move_type           ← sale.order.picking_policy

stock.move ─────────────────────────────────────────────────────
  sale_line_id            → sale.order.line (via stock.rule)
  procurement values      → sale_line_id passed to PO/MO

account.move ───────────────────────────────────────────────────
  delivery_date           ← sale.order.effective_date
  incoterm_location      ← sale.order.incoterm_location
  _stock_account_...     ← stock.move (via sale_line_id chain)
  _get_invoiced_lot_values ← stock.move.line.lot_id

stock.lot ─────────────────────────────────────────────────────
  sale_order_ids         ← stock.move.line (done, to_customer)
```

---

## Performance Considerations

### SQL Query Optimization

1. **`_compute_qty_at_date()` batched reads by `(warehouse, scheduled_date)`**: This is the primary performance optimization in the module. When in quotation mode (`state in ('draft', 'sent')`), lines sharing the same `(warehouse_id, scheduled_date)` group share a single SQL read for product quantities — rather than one query per line. The UoM conversion subtraction is done in Python per line. Without this grouping, a 50-line SO would trigger 50 separate product quantity reads.

2. **`_init_column` migration hook**: Bypasses the ORM `default_get` during first install. The field `property_warehouse_id` on `res.users` is created as a property field (ir.property) at `__init__` time, before the column exists in the DB. A direct SQL `UPDATE` assigns warehouses company-by-company, avoiding an ORM crash on the first `default_get` call.

3. **`display_qty_widget = False` for fully delivered lines**: On a confirmed SO, if all moves for a line are `done` or `cancel`, the widget is suppressed. This prevents unnecessary re-evaluation of `virtual_available_at_date`, `free_qty_today`, and `qty_available_today` for fully delivered lines on every form reload.

4. **`skip_procurement=True` recursion guard**: Both `_action_synch_order()` (on `stock.move`) and `_action_done()` (on `stock.picking`) auto-create SO lines for ad-hoc deliveries. The context flag prevents the `stock.rule` scheduler from running as a side-effect of those auto-created moves, which would cause infinite procurement recursion.

5. **`sudo()` on `stock.lot` in `_get_invoiced_lot_values`**: The lot record is accessed as superuser to avoid access errors when the invoice user lacks stock permissions. This is a deliberate privilege elevation to ensure lot names are available on the invoice PDF regardless of the user's stock ACL. The lot data is used only for display; no write operations are performed as sudo.

6. **`_auto_init()` on `stock.picking` — direct SQL column creation**: The `sale_id` column is created directly via `cr.execute` rather than through the ORM `compute`/`related` mechanism. For large databases, this avoids computing the full `move_ids.sale_line_id.order_id` chain on all existing pickings during module installation. An index is also added via `CREATE INDEX CONCURRENTLY`.

7. **`_search_days_to_arrive` GIN index on `json_detail`**: The `stock.picking` model registers a `json_detail` field as a `tsvector` (GIN-indexed) for full-text search. The `_search_days_to_arrive` method also adds an index via `CREATE INDEX IF NOT EXISTS`. These are SQL-level indexes that speed up kanban card sorting.

8. **Mode 1 `_rollup_move_origs()` traversal depth**: When `_compute_qty_at_date` runs in `'sale'` mode (confirmed order), it traverses the full origin chain via `_rollup_move_origs()`. For deep push-rule chains (e.g. SO → delivery → internal transfer → receipt), each move potentially traverses its entire upstream chain. The `visited` set prevents infinite loops but does not memoize intermediate values — if the same move chain is accessed multiple times, it is re-traversed.

### ORM and Memory

9. **`previous_product_uom_qty` delta computation**: `_action_launch_stock_rule` pre-fetches the old `product_uom_qty` of all lines before `super().write()`, then compares against the new values to compute only the delta to procure. This two-pass approach (read all, then compare and write) is more efficient than checking per-line in a write hook, but requires that the old values are available in the recordset cache.

10. **`_get_outgoing_incoming_moves(strict=False)` — `triggering_rule_ids` traversal**: The `strict=False` path identifies the initial rule that started each move chain by traversing `triggering_rule_ids` per warehouse. For move chains with many intermediate push moves, this adds O(n) traversal cost per call.

### Integration Performance

11. **`_get_invoiced_lot_values` O(n log n) lot reconciliation**: The method iterates `stock_move_lines` in sorted order (`sml.date, sml.id`) and accumulates quantities per lot in `qties_per_lot` dicts. For invoices with many lots, the dict lookups are O(1), giving an overall O(n log n) sort cost for n lines. The pagination via `all_invoices_amls[:index]` correctly handles multi-invoice lot allocation.

12. **`_compute_cumulated_delay` on `stock.warehouse`**: Called from `stock.warehouse.orderpoint._compute_days_to_order`. For each orderpoint, it adds `company.days_to_purchase` to the delay chain. This is a lightweight compute but triggers a cascade of `stock.warehouse` recompute if `days_to_purchase` changes.

---

## Security Considerations

### ACL and Privilege Escalation

1. **`sudo()` on lot access in `_get_invoiced_lot_values`**: When building lot-value lists for the invoice PDF, the lot record is accessed as `lot.sudo()`. This is necessary because an accountant or manager creating invoices typically does not have stock permissions, yet needs to display lot names from validated pickings. No write operations use `sudo()` here — only reads.

2. **`compute_sudo=False` on `on_time_rate` related field**: In sale_stock, `on_time_rate` appears on `sale.order` via the related chain `partner_id.on_time_rate`. `compute_sudo=False` means the field is computed as the current user (the SO's salesperson), not as superuser. However, the underlying `res.partner.on_time_rate` compute runs `sudo()` internally — meaning a salesperson without vendor-access ACL can still read on-time rates for all vendors whose SOs they own.

3. **Portal user picking access via `stock_picking_rule_portal`**: The record rule `'|', ('partner_id', '=', user.partner_id.id), ('sale_id.partner_id', '=', user.partner_id.id)'` allows portal users to see pickings linked to SOs where they are the customer partner. This is an indirect ACL — the picking is accessible through the SO rather than directly.

4. **`stock.group_stock_user` read/write on SOs**: The ACL `access_sale_order_stock_worker` grants `stock.group_stock_user` (warehouse workers) read and write access to `sale.order` and `sale.order.line`, but not create or delete. This means a warehouse worker can confirm a draft SO, but only if the action originates from within stock. The inverse is also true: `sales_team.group_sale_salesman` can read and write stock pickings and moves.

5. **`skip_procurement=True` context in auto-create flows**: `_action_done()` and `_action_synch_order()` use this context to bypass ACL enforcement when auto-creating SO lines from ad-hoc deliveries. This is safe because the picking itself was already ACL-authorized before validation; the SO line creation is a downstream side-effect, not a new user action.

6. **`_set_sale_id` inverse on `stock.picking`**: When a user manually sets `sale_id` on a picking, `_set_sale_id` creates a `stock.reference` record if none exists and calls `_reassign_sale_lines()`. This runs with the current user's ACL, meaning a warehouse worker reassigning a picking to an SO they can see is performing a valid business action.

7. **`_reassign_sale_lines()` product-matching ACL**: The reassignment method searches for matching product lines in the new SO using the current user's access rights. A user who cannot see a product in the new SO (e.g., due to product category restrictions) will not have the move assigned to that line.

---

## Odoo 18 → 19 Changes

| Area | Change |
|---|---|
| **`stock.reference` model** | New base model in Odoo 19. sale_stock links SOs to `stock.reference` via `sale_ids` Many2many. Enables a single reference record to be shared across both purchase receipts and sales deliveries — e.g., a customs HS code appearing on both a PO receipt and the resulting SO delivery. |
| **`_action_synch_order()` new on `stock.move`** | New method in Odoo 19. Previously, validating a delivery picking without a pre-existing SO line link was handled only in `stock.picking._action_done()`. The `stock.move` override allows the synch behavior to fire when individual moves are marked as picked, not just when the whole picking is validated. |
| **`display_qty_widget` explicit `done`/`cancel` check** | The condition now explicitly checks `all(m.state in ['done', 'cancel'] for m in line.move_ids)` on `'sale'` state lines. This is more precise than the Odoo 18 check and prevents the widget from incorrectly appearing for fully delivered lines. |
| **`json_popover` / `show_json_popover` late-delivery alerts** | New in Odoo 19. Relies on `stock.picking.delay_alert_date`. Shows a QWeb popover widget on the SO form when any linked picking is behind schedule. |
| **`sale.portal_my_orders` portal template** | Updated for Odoo 19: shows a "Shipping Status" badge column with color-coded delivery status, and `delivery_order` cards with return PDF download links. |
| **`is_storable` replaces `type == 'product'`** | The deprecated `type == 'product'` pattern is replaced with `is_storable` boolean throughout. Consumable checks (`type == 'consu'`) are retained. |
| **`_compute_move_type()` on `stock.picking`** | New override: if any linked SO has `picking_policy == 'direct'`, the picking's `move_type` is `'direct'`. Previously the move type defaulted to `'one'`. |
| **`_get_protected_vals()` on `account.move`** | New in Odoo 19. Permanently protects `delivery_date` from any write originating on `account.move.line` records. Prevents localization or automation rules from overwriting the delivery date after invoice creation. |
| **`delivery_status` `'partial'` state** | The `'partial'` status (some done AND some lines partially delivered) was formalized as a distinct state in Odoo 19. Previously this case fell into `'started'`. |
| **`_get_anglo_saxon_price_ctx` downpayment guard** | Sets `move_is_downpayment=True` in the Anglo-Saxon context when any invoice line has an `is_downpayment` SO line, preventing downpayment invoice lines from distorting COGS. |

---

## Failure Modes and Edge Cases

### Order Confirmation and Procurement

| Scenario | Behavior |
|---|---|
| Decrease ordered qty below delivered qty | `UserError` in `_update_line_quantity()` — the only way to reduce is via a return, not an SO line edit |
| Change `commitment_date` on confirmed SO | `date_deadline` on all **undone** outgoing moves (`state not in ('done', 'cancel')`, `location_dest_id.usage == 'customer'`) is updated to the new value. Done moves retain their original deadline. |
| Add new line to confirmed SO | `_action_launch_stock_rule()` fires on `sale.order.line.create()`, triggering procurement for the new line only via `previous_product_uom_qty = 0` |
| Change qty on confirmed SO line | Delta computed via `_get_qty_procurement(strict=False)` comparing existing move quantities to new `product_uom_qty`; only the delta is procured |
| MTO product with zero stock | `is_mto=True` bypasses the availability check in the qty widget — the product is shown as available because MTO guarantees procurement will occur |

### Picking and Delivery

| Scenario | Behavior |
|---|---|
| Picking validated without pre-linked SO line | `_action_done()` on the picking (and `_action_synch_order()` on each move) auto-creates a SO line with `product_uom_qty=0`, `qty_delivered=move.quantity`. Bypasses procurement via `skip_procurement=True`. |
| Return a delivery picking | `to_refund=True` on return moves causes negative qty subtraction from `qty_delivered`. If the return exceeds what was delivered, the surplus is zeroed out. |
| Change `partner_shipping_id` on confirmed SO | A mail activity is scheduled on pending pickings as a warning. The picking's `partner_id` is **not** auto-updated unless `update_delivery_shipping_partner` context is passed. |
| Product changed on a stock move with `sale_line_id` | `sale_line_id` is set to `False` — the move is orphaned from the original order line and no longer appears in its `move_ids`. |
| Multiple SOs on one picking (manual assignment) | `_set_sale_id()` picks the first `sale_id` from the SO list; `_compute_sale_id()` picks the first from `move_ids.sale_line_id.order_id`. Only one SO is linked even if multiple match. |
| SO cancellation with pending pickings | All non-`done` pickings are cancelled; `_log_decrease_ordered_quantity(cancel=True)` logs a cancellation activity on the cancelled pickings. |

### Product and Inventory Configuration

| Scenario | Behavior |
|---|---|
| Storable product with existing `expense_policy` or `service_type` | Locked to `expense_policy='no'` and `service_type='manual'` by `_compute_expense_policy()` and `_compute_service_type()` on `product.template`. These are one-way locks with no UI override available. |
| Consumable product (not storable) | `display_qty_widget` is shown. `qty_delivered_method` uses `'stock_move'`. Delivery tracking is via done stock moves. |
| Route pulling from a different warehouse than `order_id.warehouse_id` | `_compute_warehouse_id` overrides to `rule.location_src_id.warehouse_id`. The procurement is launched from the source warehouse, not the SO's warehouse. |

### Account and Invoice

| Scenario | Behavior |
|---|---|
| Invoice PDF for lots across multiple deliveries | `_get_invoiced_lot_values` correctly paginates — only lots from the current invoice (not previously invoiced lots) are shown, via `all_invoices_amls[:index]` indexing. |
| Out-refund for a partially delivered SO | `_stock_account_get_last_step_stock_moves` augments the parent method with refund flow, including both the reversed entry's SO line moves and the refund's own SO line moves for `out_refund` with downpayment. |
| Downpayment invoice lines | `_get_anglo_saxon_price_ctx` adds `move_is_downpayment=True` to prevent downpayment lines from distorting COGS calculations. The `cogs` display type lines are blocked from reinvoicing by `_sale_can_be_reinvoice()`. |
| Multiple SOs on one invoice | `effective_date` takes the **maximum** `sale.order.effective_date` across all SOs. `incoterm_location` takes the **first** non-empty value. Both correctly handle multi-SO invoices (e.g., from a sale package). |
| Manual write to `account.move.line.delivery_date` | Protected by `_get_protected_vals()` — Odoo raises an access error if a user or automation rule tries to write `delivery_date` from a line write context. |

### Lot Traceability

| Scenario | Behavior |
|---|---|
| Lot delivered on SO then returned via `out_refund` | `_should_show_lot_in_invoice()` extends the parent to include customer-originating moves (returns). For `out_refund`, `_get_invoiced_lot_values` swaps the sign of returned lot quantities, printing negative values on the refund PDF. |
| Over-delivery on returns | If a return asks for more units than were originally delivered, `quantity` becomes zero after subtracting the returned surplus. The lot qty entry is skipped (`lot.product_uom_id.compare(qty, 0) <= 0`). |
---

## Key Workflow: Order-to-Delivery

```
Quotation (draft)
  ├─ commitment_date optional (sets explicit deadline)
  ├─ warehouse_id (user's default or system default)
  ├─ picking_policy (direct=partial OK, one=all at once)
  └─ route_ids on each line (MTO, Dropship, Make-to-Order)
       ↓  [Confirm Order]
Sales Order (sale)
  └─ _action_confirm() → _action_launch_stock_rule()
       └─ stock.rule.run(procurements)
            ├─ Creates stock.picking (delivery)
            ├─ Creates purchase.order (MTO buy route)
            └─ Creates mrp.production (MTO manufacture route)
       ↓  [Validate Picking]
  └─ _action_done() on picking
       ├─ qty_delivered updated on SO line (via _compute_qty_delivered)
       ├─ effective_date set (first done picking date_done)
       └─ Auto-creates SO line if picking not pre-linked (synch scenario)
       ↓  [Create Invoice]
  └─ _prepare_invoice()
       ├─ invoice_incoterm_id = incoterm
       ├─ delivery_date = effective_date
       └─ Lot numbers shown on invoice PDF via _get_invoiced_lot_values
```

---

## Related Documentation

- [Core/API](odoo-18/Core/API.md) — ORM decorators, `@api.depends`, `@api.onchange`
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine, action methods
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — ACL CSV, `ir.rule`, field groups
- [Modules/Sale](odoo-18/Modules/sale.md) — `sale.order`, `sale.order.line` base models
- [Modules/Stock](odoo-18/Modules/stock.md) — `stock.picking`, `stock.move`, `stock.route`, `stock.rule`
- [Modules/Account](odoo-18/Modules/account.md) — `account.move`, Anglo-Saxon valuation
- [Modules/Product](odoo-18/Modules/product.md) — `product.template`, `is_storable` flag
