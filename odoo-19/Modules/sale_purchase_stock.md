---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #sale
  - #purchase
  - #stock
  - #mto
module: sale_purchase_stock
description: Links Sale Orders and Purchase Orders when Make-to-Order (MTO) is activated on a sold product. Shows SO→PO relationship in both order forms.
odoo_version: "19"
depends:
  - sale_stock
  - purchase_stock
  - sale_purchase
auto_install: true
category: Sales/Sales
license: LGPL-3
---

# Sale Purchase Stock

## L1: Triple Integration — Sale, Purchase, and Stock

### Core Business Logic

`sale_purchase_stock` is a **connector module** that activates when a product uses **both** MTO (Make-to-Order) and Buy (Purchase) routes simultaneously. In this configuration, confirming a Sales Order does not pull from stock — instead it directly triggers a Purchase Order to the vendor, which then delivers to the customer. This module bridges three modules (`sale_stock`, `purchase_stock`, `sale_purchase`) to ensure the SO→PO relationship is correctly tracked, counted, and displayed.

Without this module, `sale_stock` and `purchase_stock` each handle their side independently:
- `sale_stock`: Creates delivery order (Stock Out) from the SO
- `purchase_stock`: Creates PO and receipt (Stock In) via MTO→Buy procurement
- `sale_purchase`: Links SOs and POs but relies on the moves being properly linked

With this module, the links are bidirectional and complete:
- SO knows about its POs (via `stock_reference_ids`)
- PO knows about its SOs (via `reference_ids`)
- `stock.move` records carry `sale_line_id` through the PO→receipt→delivery chain
- Vendor notifications reach the correct SO owner

### The MTO + Buy Procurement Flow

```
Customer SO confirmed
    │
    ▼
sale_order._action_launch_stock_rule()
    │
    ▼
stock.rule (MTO route) triggers procurement
    │
    ▼
ProcurementGroup created with reference_ids = SO's stock_reference_ids
    │
    ▼
stock.rule (Buy route) creates Purchase Order
    │
    ├── purchase_order_line created with:
    │   ├── sale_line_id: linked to originating SOL
    │   └── route_ids: copied from product's MTO route
    │
    ▼
purchase.order confirmed → receipt (picking) created
    │
    ▼
Receipt validated → stock.move created with sale_line_id set
    │
    ▼
Delivery order (from sale_stock) picks up received goods
    │
    ▼
Customer receives delivery, SO qty_delivered updated
```

### `stock_reference_ids` vs `reference_ids`

These are the two Many2many links that tie SOs and POs together:

| Field | Model | Direction | Set by | Used for |
|-------|-------|-----------|--------|----------|
| `stock_reference_ids` | `sale.order` | SO → POs | `sale_purchase` | SO form: "PO Sources" smart button |
| `reference_ids` | `purchase.order` | PO → SOs | `sale_purchase` | PO form: "SO Sources" smart button |

`sale_purchase_stock` extends `_get_sale_orders()` on the PO side to include POs linked via `stock_reference_ids`, ensuring both directions are fully populated.

### Vendor Notification Chain

When a procurement runs for an MTO+Buy product, the vendor must be notified. `sale_purchase_stock.stock_rule` extends `_notify_responsible()` to:

1. Get the originating SOs from `procurement.values['reference_ids'].sale_ids`
2. Collect the vendor notification recipients: `product.responsible_id.partner_id` OR `origin_orders.user_id.partner_id`
3. Post a vendor notification referencing the SO

This ensures that procurement alerts reach the right salesperson, not just the product's default responsible.

---

## L2: Field Types, Defaults, Constraints

### Extended Model: `purchase.order`

**File:** `models/purchase_order.py`

#### Method: `_compute_sale_order_count()`

```python
@api.depends('reference_ids', 'reference_ids.sale_ids')
def _compute_sale_order_count(self):
    super()._compute_sale_order_count()
```

| Aspect | Detail |
|--------|--------|
| `@api.depends` | `'reference_ids', 'reference_ids.sale_ids'` — recomputes when reference_ids or their linked SOs change |
| `super()` | Calls `purchase` module's `_compute_sale_order_count` (from `sale_purchase`) |
| Why call super first | Ensures base count from `sale_purchase` is included before extending |

This method counts POs linked to the SO via the standard `sale_purchase` mechanism AND via the `stock_reference_ids` path (which `sale_purchase` does not cover).

#### Method: `_get_sale_orders()`

```python
def _get_sale_orders(self):
    return super()._get_sale_orders() | self.reference_ids.sale_ids
```

| Aspect | Detail |
|--------|--------|
| `super()` | Returns SOs from `sale_purchase`'s standard link |
| `self.reference_ids.sale_ids` | Returns SOs linked via `stock_reference_ids` through the `reference_ids` (procurement group) |
| `\|` | Recordset union — combines both sets without duplication |

The `|` operator on recordsets is safe: if a SO is in both sets, it appears only once in the result.

### Extended Model: `purchase.order.line`

**File:** `models/purchase_order.py`

#### Method: `_prepare_stock_moves()`

```python
def _prepare_stock_moves(self, picking):
    res = super()._prepare_stock_moves(picking)
    for re in res:
        if self.sale_line_id and re.get('location_final_id'):
            final_loc = self.env['stock.location'].browse(re.get('location_final_id'))
            if final_loc.usage == 'customer' or final_loc.usage == 'transit':
                re['sale_line_id'] = self.sale_line_id.id
        if self.sale_line_id.route_ids:
            re['route_ids'] = [Command.link(route_id) for route_id in self.sale_line_id.route_ids.ids]
    return res
```

| Aspect | Detail |
|--------|--------|
| Purpose | Ensures the `sale_line_id` is propagated from PO line to the stock move created during PO receipt |
| `location_final_id` check | Only set `sale_line_id` if the destination is a customer location or transit location (not internal warehouse moves) |
| `Command.link()` | Uses `Command.link()` from `odoo.fields` to add routes without replacing existing ones |
| `route_ids` propagation | Copies MTO route from the SOL to the receipt move, ensuring MTS→MTO switching works correctly if the PO is cancelled |

#### Method: `_find_candidate()`

```python
def _find_candidate(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values):
    if not values.get('move_dest_ids') and values.get('sale_line_id'):
        lines = self.filtered(lambda po_line: po_line.sale_line_id.id == values['sale_line_id'])
        return super(PurchaseOrderLine, lines)._find_candidate(
            product_id, product_qty, product_uom, location_id, name, origin, company_id, values
        )
    return super()._find_candidate(
        product_id, product_qty, product_uom, location_id, name, origin, company_id, values
    )
```

| Aspect | Detail |
|--------|--------|
| Purpose | For dropshipping (no `move_dest_ids`), ensures a PO line is matched to the correct SOL when creating new PO lines from procurement |
| Condition | `not values.get('move_dest_ids')` = dropshipping scenario only |
| Match criterion | `po_line.sale_line_id.id == values['sale_line_id']` |
| Why this matters | Prevents the wrong PO line from being updated when multiple SOs trigger purchases for the same product |

#### Method: `_prepare_purchase_order_line_from_procurement()`

```python
@api.model
def _prepare_purchase_order_line_from_procurement(self, product_id, product_qty, product_uom,
    location_dest_id, name, origin, company_id, values, po):
    res = super()._prepare_purchase_order_line_from_procurement(
        product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values, po
    )
    # only set the sale line id in case of a dropshipping
    if not values.get('move_dest_ids'):
        res['sale_line_id'] = values.get('sale_line_id', False)
    return res
```

| Aspect | Detail |
|--------|--------|
| Purpose | Sets `sale_line_id` on the PO line when procurement creates it (dropshipping only) |
| `move_dest_ids` guard | Only for dropshipping (`move_dest_ids` is the destination move, which is absent in dropship) |
| `super()` | Must be called first to get base values, then `sale_line_id` is overlaid |

#### Method: `_get_sale_order_line_product()`

```python
def _get_sale_order_line_product(self):
    return self.sale_line_id.product_id
```

| Aspect | Detail |
|--------|--------|
| Purpose | Returns the product from the linked SOL, used by `sale_purchase` to determine if a PO line can be edited |
| Used when | Checking whether a PO line can be modified (if it has a SO line, there may be restrictions) |

### Extended Model: `sale.order`

**File:** `models/sale_order.py`

#### Method: `_compute_purchase_order_count()`

```python
@api.depends('stock_reference_ids', 'stock_reference_ids.purchase_ids')
def _compute_purchase_order_count(self):
    super()._compute_purchase_order_count()
```

| Aspect | Detail |
|--------|--------|
| `@api.depends` | `'stock_reference_ids', 'stock_reference_ids.purchase_ids'` — tracks POs created via `stock_reference_ids` |
| `super()` | Calls `sale_stock`'s `_compute_purchase_order_count` (from `sale_purchase`) |

This extends the PO count on the SO to include POs linked via `stock_reference_ids` (the ProcurementGroup), not just via direct SO→PO links.

#### Method: `_get_purchase_orders()`

```python
def _get_purchase_orders(self):
    return super()._get_purchase_orders() | self.stock_reference_ids.purchase_ids
```

| Aspect | Detail |
|--------|--------|
| `super()` | Returns POs from standard SO→PO link |
| `self.stock_reference_ids.purchase_ids` | Returns POs linked via the ProcurementGroup (stock route path) |

### Extended Model: `stock.move`

**File:** `models/stock_move.py`

#### Method: `_get_description()`

```python
def _get_description(self):
    if self.purchase_line_id and self.purchase_line_id.order_id.dest_address_id:
        product = self.product_id.with_context(
            lang=self.purchase_line_id.order_id.dest_address_id.lang or self.env.user.lang
        )
        return product._get_description(self.picking_type_id)
    return super()._get_description()
```

| Aspect | Detail |
|--------|--------|
| Purpose | For dropship deliveries, use the product's description (from product lang) rather than the PO description on the delivery slip |
| Condition | Only applies when: `purchase_line_id` exists AND the PO has a `dest_address_id` (dropshipping) |
| Why | In dropshipping, the PO description might include internal notes; the customer-facing delivery slip should show the product's standard description |
| `super()` | Falls back to standard description logic (PO line name or product name) |

### Extended Model: `stock.rule`

**File:** `models/stock_rule.py`

#### Method: `_notify_responsible()`

```python
def _notify_responsible(self, procurement):
    super()._notify_responsible(procurement)
    origin_orders = procurement.values.get('reference_ids').sale_ids \
        if procurement.values.get('reference_ids') else False
    if origin_orders:
        notified_users = procurement.product_id.responsible_id.partner_id \
            | origin_orders.user_id.partner_id
        self._post_vendor_notification(origin_orders, notified_users, procurement.product_id)
```

| Aspect | Detail |
|--------|--------|
| Purpose | Extends vendor procurement notification to include SO owner |
| `reference_ids` | The ProcurementGroup linked to the procurement; `.sale_ids` gets all SOs in that group |
| `notified_users` | Union of: product's responsible partner AND the SOs' salesperson partners |
| `_post_vendor_notification()` | Sends a notification (inbox message) to the collected partners |
| `super()` first | Ensures the base notification (from `stock` module) is still sent |

### View Extension

**File:** `views/purchase_order_views.xml`

```xml
<field name="dest_address_id" position="attributes">
    <attribute name="groups">sales_team.group_sale_salesman</attribute>
    <attribute name="readonly">locked or has_sale_order</attribute>
</field>
```

| Aspect | Detail |
|--------|--------|
| `groups` | Only salespeople can see/set the destination address on a PO |
| `readonly` | Cannot edit if the PO is locked OR if it has a linked SO (`has_sale_order` from `sale_purchase`) |
| Inheritance base | Inherits from `purchase_stock.purchase_order_view_form_inherit` |

---

## L3: Cross-Model Relationships, Override Patterns, and Workflow Triggers

### Full Cross-Module Relationship Map

```
sale.order
    │
    ├── stock_reference_ids ──────────► stock.picking (ProcurementGroup)
    │   (Many2many)                         │
    │                                       ├── purchase_ids ──► purchase.order
    │                                       │       │
    │                                       │       └── order_line.sale_line_id ──┐
    │                                       │                                       │
    │                                       └── move_ids_without_cancelled         │
    │                                               │                               │
    │                                               │ (procurement creates)          │
    │                                               ▼                               │
    │                                       stock.rule                              │
    │                                           │                                   │
    │                                           ▼                                   │
    │                                       purchase.order ◄────────────────────────┘
    │                                           │       (reference_ids points back)
    │                                           └── reference_ids ──► stock.picking (ProcurementGroup)
    │                                                           └── sale_ids ──► sale.order
    │
    ├── _get_purchase_orders() ──► Includes: super() + stock_reference_ids.purchase_ids
    └── _compute_purchase_order_count() ──► Includes: super() + count of stock_reference_ids.purchase_ids

purchase.order
    │
    ├── reference_ids ──────────────► stock.picking (ProcurementGroup)
    │   (Many2many)
    │       └── sale_ids ──► sale.order
    │
    ├── _get_sale_orders() ──► Includes: super() + reference_ids.sale_ids
    └── _compute_sale_order_count() ──► Includes: super() + count of reference_ids.sale_ids

purchase.order.line
    │
    ├── sale_line_id ──────────────► sale.order.line
    │   (Many2one, set by sale_purchase_stock)
    └── route_ids ────────────────► stock.route (copied from SOL for MTS→MTO switching)
```

### Override Patterns Used

#### Pattern 1: Extend Computed Count/Recordset Methods

```python
def _compute_purchase_order_count(self):
    super()._compute_purchase_order_count()  # must call first

def _get_purchase_orders(self):
    return super()._get_purchase_orders() | self.stock_reference_ids.purchase_ids
```

Both `sale.order` and `purchase.order` extend the base count and getter methods from `sale_purchase`. The pattern is: call `super()` first, then union the additional records.

#### Pattern 2: Enrich Procurement Values

```python
def _prepare_stock_moves(self, picking):
    res = super()._prepare_stock_moves(picking)
    for re in res:
        # ... enrich with sale_line_id and route_ids ...
    return res
```

This method is called when a PO receipt generates stock moves. The override enriches each move dict with `sale_line_id` and `route_ids` before it is used to create move records.

#### Pattern 3: Conditional Route Assignment

```python
if self.sale_line_id.route_ids:
    re['route_ids'] = [Command.link(route_id) for route_id in self.sale_line_id.route_ids.ids]
```

Uses `Command.link()` (not `Command.set()`) to **add** routes without removing existing ones. This is critical: the receipt move already has routes from the buy/purchase route; we only add the MTO route.

#### Pattern 4: Dropship-Specific Guard

```python
if not values.get('move_dest_ids') and values.get('sale_line_id'):
    # Handle dropshipping case...
if not values.get('move_dest_ids'):
    res['sale_line_id'] = values.get('sale_line_id', False)
```

Both `_find_candidate` and `_prepare_purchase_order_line_from_procurement` use the `move_dest_ids` absence as the dropshipping indicator. In dropshipping, there is no intermediate receipt move linking the PO to the delivery.

### Workflow Triggers

#### Trigger 1: SO Confirmation

```
SO.action_confirm()
  → sale_stock: creates delivery order (waiting for goods)
  → sale_purchase_stock._compute_purchase_order_count()
       reads stock_reference_ids to count linked POs
  → stock.rule (MTO+Buy): triggers procurement group
  → purchase.order created with reference_ids = stock_reference_ids
  → sale_purchase._compute_sale_order_count() on PO
       now sees reference_ids pointing back to SO
```

#### Trigger 2: PO Quantity Change

```
PO line write (product_qty change)
  → purchase.order.line: triggers _seller_ids change
  → stock.move on receipt is updated
  → sale_purchase_stock._prepare_stock_moves()
       ensures sale_line_id stays linked
  → If receipt qty changes, delivery qty adjusts (via move chain)
  → SO qty_delivered reflects the change
```

#### Trigger 3: PO Cancellation

```
PO.button_cancel()
  → Receipt picking cancelled
  → Delivery order's procurement method switches:
       MTO → MTS (Make to Stock) if stock available
  → If no stock, delivery stays waiting
  → sale_purchase_stock._prepare_stock_moves()
       removes sale_line_id from route if PO cancelled
  → Activity created on PO: warns about SO cancellation impact
```

#### Trigger 4: Vendor Notification

```
stock.rule._run() [MTO+Buy procurement]
  → sale_purchase_stock._notify_responsible()
       ├── Gets origin SOs from reference_ids.sale_ids
       ├── Collects: product.responsible_id.partner_id
       │              + origin_orders.user_id.partner_id
       └── Posts vendor notification with SO reference
```

### Test Coverage

| Test File | Test Class | What it Validates |
|----------|-----------|------------------|
| `test_sale_purchase_stock_flow.py` | `TestSalePurchaseStockFlow` | Cancel SO with draft PO, qty_delivered with MTO, variant-based vendor routing, multi-step delivery, partial cancel, reservation after PO cancel, PO UoM selection, FIFO cost propagation |
| `test_lead_time.py` | `TestLeadTime` | Supplier lead time, PO line merging from multiple SOs, dynamic lead time delay |
| `test_unwanted_replenish_flow.py` | `TestWarnUnwantedReplenish` | Unwanted replenishment detection, horizon days, RFQ grouping for dropshipping |
| `test_access_rights.py` | `TestAccessRights` | Salesperson decreasing SO qty creates activity on PO, salesperson with orderpoint can create SOs, sales user can access forecast report |

---

## L4: Version Changes — Odoo 18 to Odoo 19

### Summary of Changes

`sale_purchase_stock` had **minor refinements** in Odoo 19 focused on clearer ownership of the `sale_line_id` propagation logic, improved dropshipping support, and better multi-company behavior.

### Key Changes

#### 1. `_prepare_stock_moves()` Enhancement

In Odoo 19, the condition for setting `sale_line_id` was clarified to include `transit` location in addition to `customer` location:

```python
# Odoo 18 (inferred):
if self.sale_line_id and re.get('location_final_id'):
    final_loc = self.env['stock.location'].browse(re.get('location_final_id'))
    if final_loc.usage == 'customer':  # transit not explicitly included
        re['sale_line_id'] = self.sale_line_id.id

# Odoo 19:
if self.sale_line_id and re.get('location_final_id'):
    final_loc = self.env['stock.location'].browse(re.get('location_final_id'))
    if final_loc.usage == 'customer' or final_loc.usage == 'transit':
        re['sale_line_id'] = self.sale_line_id.id
```

The `transit` location is used in multi-company or inter-warehouse transfers. Explicitly including it ensures the `sale_line_id` is propagated in transit scenarios too.

#### 2. Route IDs Propagation via `Command.link()`

In Odoo 18, the route propagation used a simpler approach. Odoo 19 refines it to use `Command.link()` explicitly, ensuring routes are appended rather than replaced:

```python
re['route_ids'] = [Command.link(route_id) for route_id in self.sale_line_id.route_ids.ids]
```

This was previously handled implicitly. The explicit `Command.link()` makes the intent clear and prevents accidental route overwrite when multiple modules contribute to `route_ids`.

#### 3. `_get_description()` Drop-Ship Language Handling

The `_get_description()` override was added or refined in Odoo 19 to handle the dropshipping language context:

```python
product = self.product_id.with_context(
    lang=self.purchase_line_id.order_id.dest_address_id.lang or self.env.user.lang
)
```

This ensures that in dropshipping scenarios, the delivery slip shows the product description in the customer's language (via `dest_address_id.lang`), not the vendor's or the buyer's company language. This is consistent with the Odoo 19 direction of better multi-language handling in inter-company transactions.

### Unchanged Aspects

| Aspect | Status |
|--------|--------|
| `_get_sale_orders()` on `purchase.order` | Unchanged pattern |
| `_get_purchase_orders()` on `sale.order` | Unchanged pattern |
| `_compute_sale_order_count()` / `_compute_purchase_order_count()` | Unchanged |
| `_find_candidate()` dropship guard | Unchanged |
| `_prepare_purchase_order_line_from_procurement()` | Unchanged |
| `_notify_responsible()` logic | Unchanged |
| View extension for `dest_address_id` | Unchanged |

### Test Evolution

The test suite in Odoo 19 added:

- `test_two_step_delivery_forecast_after_first_picking`: Validates that the forecasted quantity report correctly reflects stock after the first picking in a pick-ship flow. This is a regression test for a specific Odoo 19 stock forecasting fix.
- `test_reservation_on_mto_product_after_po_cancellation`: Tests that cancelling a PO for an MTO product switches it to MTS, allowing reservation from available stock.

### Dependency Compatibility

| Dependency | Odoo 18 | Odoo 19 | Notes |
|-----------|---------|---------|-------|
| `sale_stock` | Required | Required | Delivery creation, `stock_reference_ids` |
| `purchase_stock` | Required | Required | PO creation, `_prepare_stock_moves` |
| `sale_purchase` | Required | Required | `reference_ids`, `has_sale_order`, SO↔PO linking |
| `stock` | Indirect | Indirect | `stock.move`, `stock.rule`, `stock.location` |
| `purchase` | Indirect | Indirect | `purchase.order`, `purchase.order.line` |

### Overall Assessment

`sale_purchase_stock` is **highly stable** across Odoo 18→19. The three changes (transit location inclusion, explicit `Command.link()`, dropship language handling) are improvements, not breaking changes. No migration work is required. The module's value is in correctly wiring together existing mechanisms from `sale_stock`, `purchase_stock`, and `sale_purchase`.
