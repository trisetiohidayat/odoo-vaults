---
uuid: stock-delivery-l3
tags:
  - #odoo
  - #odoo19
  - #modules
  - #shipping
  - #delivery
  - #logistics
created: 2026-04-11
modified: 2026-04-11
module: stock_delivery
module_version: "19.0"
module_category: Logistics/Sales
module_type: Odoo Community (CE)
module_location: ~/odoo/odoo19/odoo/addons/stock_delivery/
module_dependencies:
  - stock
  - sale
---

# stock_delivery Module

## Overview

The `stock_delivery` module adds shipping carrier management capabilities to the Odoo stock and sales stack. It extends `delivery.carrier` with external shipping provider integration, adds physical shipping attributes (weight, volume, tracking) to `stock.picking`, and manages the flow of delivery costs back to the sale order. It is the bridge between the sales order's delivery line and the physical shipment process.

> **Location:** `~/odoo/odoo19/odoo/addons/stock_delivery/`
> **Key models extended:** `delivery.carrier`, `stock.picking`, `stock.move`, `stock.move.line`, `sale.order`, `sale.order.line`
> **External integrations:** Plug-in architecture for DHL, FedEx, UPS, etc. (via provider-specific modules)

---

## Module Structure

```
stock_delivery/
├── models/
│   ├── __init__.py
│   ├── delivery_carrier.py      # delivery.carrier extensions: send/cancel/tracking, packages
│   ├── stock_picking.py         # stock.picking: carrier fields, weight, send_to_shipper
│   ├── stock_move.py            # stock.move: weight field, _get_new_picking_values
│   ├── stock_move_line.py       # stock.move.line: sale_price, destination_country
│   ├── stock_package.py         # stock.package: shipping_weight, carrier_id
│   ├── stock_package_type.py    # package type with base_weight, max_weight
│   ├── product_template.py       # product.template: weight, volume fields
│   ├── sale_order.py            # sale.order: set_delivery_line, _create_delivery_line
│   ├── delivery_request_objects.py  # DeliveryCommodity, DeliveryPackage value objects
│   └── __init__.py
└── views/
    ├── stock_picking_views.xml
    └── delivery_carrier_views.xml
```

---

## delivery.carrier Extensions (`delivery_carrier.py`)

### New Fields on `delivery.carrier`

| Field | Type | Description |
|-------|------|-------------|
| `route_ids` | Many2many | `stock.route` records this carrier can use |
| `invoice_policy` | Selection | Added `('real', 'Real cost')` — invoices actual cost post-delivery |

### Shipping Provider API Methods

The module defines a plug-in interface for shipping providers. Each provider implements specific methods by name convention (`{delivery_type}_send_shipping`, etc.):

**`send_shipping(pickings)`** — Entry point for shipping API calls:
```python
def send_shipping(self, pickings):
    self.ensure_one()
    if hasattr(self, '%s_send_shipping' % self.delivery_type):
        return getattr(self, '%s_send_shipping' % self.delivery_type)(pickings)
    return None
```
Returns a list of dicts: `[{ 'exact_price': float, 'tracking_number': str }]`

**`get_tracking_link(picking)`** — Returns carrier's tracking URL:
```python
def get_tracking_link(self, picking):
    self.ensure_one()
    if hasattr(self, '%s_get_tracking_link' % self.delivery_type):
        return getattr(self, '%s_get_tracking_link' % self.delivery_type)(picking)
    return None
```

**`cancel_shipment(pickings)`** — Cancels shipment with carrier:
```python
def cancel_shipment(self, pickings):
    self.ensure_one()
    if hasattr(self, '%s_cancel_shipment' % self.delivery_type):
        return getattr(self, '%s_cancel_shipment' % self.delivery_type)(pickings)
```

**`get_return_label(pickings, tracking_number, origin_date)`** — Generates return shipping label:
- Calls `{delivery_type}_get_return_label()` if implemented
- Generates access token for portal download if `get_return_label_from_portal` is True

### Label and Document Helpers

- **`get_return_label_prefix()`** — Returns `'LabelReturn-{delivery_type}'`
- **`_get_delivery_label_prefix()`** — Returns `'LabelShipping-{delivery_type}'`
- **`_get_default_custom_package_code()`** — Override point for carrier-specific package prefix requirements

---

## Fixed-Price Provider Implementation

For carriers with `delivery_type = 'fixed'`:

**`fixed_send_shipping(pickings)`** — Returns the carrier's `fixed_price`:
```python
def fixed_send_shipping(self, pickings):
    res = []
    for p in pickings:
        res.append({
            'exact_price': p.carrier_id.fixed_price,
            'tracking_number': False,
        })
    return res
```

**`fixed_get_tracking_link(picking)`** — Substitutes `<shipmenttrackingnumber>` in `tracking_url`:
```python
def fixed_get_tracking_link(self, picking):
    if self.tracking_url and picking.carrier_tracking_ref:
        return self.tracking_url.replace("<shipmenttrackingnumber>", picking.carrier_tracking_ref)
    return False
```

**`fixed_cancel_shipment(pickings)`** — Raises `NotImplementedError` (no automatic cancellation for fixed carriers).

---

## Rule-Based Carrier (`base_on_rule`)

For carriers with `delivery_type = 'base_on_rule'` (internal routing):

**`base_on_rule_send_shipping(pickings)`** — Matches delivery rules:
```python
def base_on_rule_send_shipping(self, pickings):
    for p in pickings:
        carrier = self._match_address(p.partner_id)  # Apply delivery.grid rules
        if not carrier:
            raise ValidationError(_('There is no matching delivery rule.'))
        res.append({
            'exact_price': p.carrier_id._get_price_available(p.sale_id),
            'tracking_number': False,
        })
```

---

## Package and Commodity Management

### DeliveryPackage Value Object (`delivery_request_objects.py`)

`DeliveryPackage` encapsulates a single shipping package with all required carrier data:

```python
DeliveryPackage(
    commodities: list[DeliveryCommodity],  # Items in this package
    weight: float,                        # Package weight (kg/lb)
    package_type_id: stock.package.type,   # Package type record
    name: str = None,                     # Package name (for pre-built packages)
    total_cost: float,                     # Declared value for customs
    currency: res.currency,
    order: sale.order = None,             # Source order
    picking: stock.picking = None,         # Source picking
)
```

`DeliveryCommodity` holds customs data for a product:

```python
DeliveryCommodity(
    product: product.product,
    amount: int,                          # Number of units
    monetary_value: float,               # Total value
    country_of_origin: str,              # ISO country code
)
```

### `_get_packages_from_order(order, default_package_type)`

Splits an order into packages based on weight:

1. Sums total cost of non-delivery order lines
2. Computes total weight: `sum(order_line.qty * product.weight) + package_type.base_weight`
3. Divides into packages based on `package_type.max_weight`
4. Distributes declared value uniformly across packages
5. Splits commodities proportionally across packages

### `_get_packages_from_picking(picking, default_package_type)`

Handles three scenarios:

1. **Return picking:** Creates single package from `move_line_ids`
2. **Pre-packed packages:** Iterates `picking.move_line_ids.result_package_id` — each existing package becomes a `DeliveryPackage`
3. **Bulk (no packages):** Creates single `DeliveryPackage` using `picking.weight_bulk`
4. **No weight:** Raises `UserError` — all products must have a weight

### `_get_commodities_from_order(order)` / `_get_commodities_from_stock_move_lines(move_lines)`

Builds customs commodity list from order lines or stock move lines:
- Filters `product.type == 'consu'` (consumable/storable)
- Converts UoM quantities
- Uses `product.country_of_origin` or warehouse country as origin
- Uses `price_reduce_taxinc` as monetary value

### `_product_price_to_company_currency(quantity, product, company)`

Converts product cost to company currency for customs value:
```python
return company.currency_id._convert(
    quantity * product.standard_price,
    product.currency_id,
    company,
    fields.Date.today()
)
```

---

## stock.picking Extensions (`stock_picking.py`)

### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `carrier_price` | Float | Actual shipping cost from carrier |
| `delivery_type` | Selection (related) | Mirrors `carrier_id.delivery_type` |
| `allowed_carrier_ids` | Many2many | Carriers compatible with this picking (compute) |
| `carrier_id` | Many2one | The selected delivery carrier |
| `weight` | Float (compute) | Total weight = `sum(move.weight for move in move_ids)` |
| `carrier_tracking_ref` | Char | Carrier tracking number |
| `carrier_tracking_url` | Char (compute) | Full tracking URL |
| `weight_uom_name` | Char (compute) | Weight UOM label |
| `is_return_picking` | Boolean (compute) | `True` if carrier supports returns and picking contains returns |
| `return_label_ids` | One2many (compute) | Attachments that are return labels |
| `destination_country_code` | Char (related) | `partner_id.country_id.code` |
| `integration_level` | Selection (related) | From `carrier_id.integration_level` |

### `_compute_allowed_carrier_ids()`

Filters carriers based on:
- Company (`_check_company_domain`)
- Partner country
- `max_weight` / `max_volume` constraints
- `must_have_tag_ids` / `excluded_tag_ids` matching `product_tag_ids`

### `_cal_weight()`

```python
@api.depends('move_ids.weight')
def _cal_weight(self):
    for picking in self:
        picking.weight = sum(move.weight for move in picking.move_ids if move.state != 'cancel')
```

> `move.weight` itself is computed from `product_id.weight * product_uom_qty` (see `stock_move.py`).

---

## Key Picking Methods

### `send_to_shipper()`

Called during `button_validate()` for `integration_level = 'rate_and_ship'`:

```python
def send_to_shipper(self):
    self.ensure_one()
    res = self.carrier_id.send_shipping(self)[0]   # Call carrier API

    # Free shipping if order total >= free_over threshold
    if self.carrier_id.free_over and self.sale_id:
        amount_without_delivery = self.sale_id._compute_amount_total_without_delivery()
        if self.carrier_id._compute_currency(...) >= self.carrier_id.amount:
            res['exact_price'] = 0.0

    self.carrier_price = self.carrier_id._apply_margins(res['exact_price'], self.sale_id)

    # Aggregate tracking refs across related pickings (same origin sale)
    if res['tracking_number']:
        related_pickings = self._get_all_related_pickings()
        ...

    self._add_delivery_cost_to_so()
```

### `_add_delivery_cost_to_so()`

Called after `send_to_shipper()` to sync actual cost to sale order:

```python
def _add_delivery_cost_to_so(self):
    if self.carrier_id.invoice_policy == 'real' and self.carrier_price:
        delivery_lines = self._get_matching_delivery_lines()  # Zero-cost delivery SOL
        if not delivery_lines:
            delivery_lines = self.sale_id._create_delivery_line(...)
        delivery_lines[0].write({'price_unit': self.carrier_price})
```

### `_send_confirmation_email()`

Wraps `super()` and adds automatic `send_to_shipper()` call:

```python
def _send_confirmation_email(self):
    for pick in self:
        if pick.carrier_id.integration_level == 'rate_and_ship' and ...:
            pick.sudo().send_to_shipper()
        pick._check_carrier_details_compliance()
    return super()._send_confirmation_email()
```

> **Note:** If `send_to_shipper()` raises `UserError` and some pickings were already processed, the error is demoted to a mail activity warning instead of failing the entire transaction.

### `cancel_shipment()`

Calls `carrier_id.cancel_shipment(self)` and clears the tracking reference.

### `print_return_label()`

Calls `carrier_id.get_return_label(self)` to generate and attach the return label.

### `open_website_url()`

Opens the carrier's tracking page in a new tab. Supports both single URLs and JSON arrays of `(name, url)` pairs.

---

## stock.move Extensions (`stock_move.py`)

### New Fields on `stock.move`

| Field | Type | Description |
|-------|------|-------------|
| `weight` | Float (compute, store) | `product_qty * product_id.weight` |

The `weight` field is created via `_auto_init()` using a raw SQL `UPDATE` for performance on large databases, then updated on each move change via `_cal_move_weight()`.

### Carrier Propagation on Picking Creation

**`_get_new_picking_values()`** — When a stock.rule triggers creation of a new picking:
```python
def _get_new_picking_values(self):
    vals = super()._get_new_picking_values()
    carrier_id = self.reference_ids.sale_ids.carrier_id.id
    vals['carrier_id'] = any(rule.propagate_carrier for rule in self.rule_id) and carrier_id
    return vals
```

**`_key_assign_picking()`** — Groups moves into pickings by adding `carrier_id` as a grouping key:
```python
def _key_assign_picking(self):
    keys = super()._key_assign_picking()
    return keys + (self.sale_line_id.order_id.carrier_id,)
```

> **Key insight:** If `propagate_carrier = True` on the stock.rule, the carrier set on the sale order is automatically propagated to downstream pickings.

---

## stock.move.line Extensions (`stock_move_line.py`)

| Field | Type | Description |
|-------|------|-------------|
| `sale_price` | Float (compute) | `quantity * price_reduce_taxinc` for customs value |
| `destination_country_code` | Char (related) | `picking_id.destination_country_code` |
| `carrier_id` | Many2one (related) | `picking_id.carrier_id` |

---

## sale.order Extensions (`sale_order.py`)

### `set_delivery_line(carrier, amount)`

After confirming an SO (state = 'sale'), syncs the carrier to all pending pickings:
```python
def set_delivery_line(self, carrier, amount):
    res = super().set_delivery_line(carrier, amount)
    for order in self:
        if order.state != 'sale':
            continue
        pending = order.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
                      and not any(m.origin_returned_move_id for m in p.move_ids)
        )
        pending.carrier_id = carrier.id
    return res
```

### `_create_delivery_line(carrier, price_unit)`

For `invoice_policy = 'real'`, sets initial SOL price to `0` with estimated cost in description:
```python
name = "%s (Estimated Cost: %s)" % (carrier.name, currency.format(price_unit))
```

The actual price is updated via `_add_delivery_cost_to_so()` after delivery is confirmed.

---

## sale.order.line Extensions

### `_prepare_procurement_values()`

Adds carrier route to procurement values:
```python
def _prepare_procurement_values(self):
    values = super()._prepare_procurement_values()
    if not values.get("route_ids") and self.order_id.carrier_id.route_ids:
        values['route_ids'] = self.order_id.carrier_id.route_ids
    return values
```

---

## Carrier Integration Levels

| Level | Description | Behavior |
|-------|-------------|---------|
| `rate_only` | Quote only | Shows rate on SO, no API call at validation |
| `rate_and_ship` | Quote + ship | Calls `send_shipping()` at validation, generates label |

---

## Configuration Checklist

1. **Install** `delivery` module (base carrier model)
2. **Install** `stock_delivery` module
3. **Create carrier:** `Inventory > Delivery > Carriers`
   - Set `delivery_type` (fixed, base_on_rule, or provider-specific)
   - Set `product_id` (the delivery product used on SO)
   - Set `integration_level` (rate_only or rate_and_ship)
   - For `base_on_rule`: define delivery.grid with zone rules
4. **Product weights:** Ensure all shippable products have `weight` and `volume` set
5. **Routes:** If using routing-based carriers, configure `stock.route` with `shipping_selectable = True`
6. **Shipping cost on SO:** Carrier rate is added as delivery SOL when order is confirmed

---

## Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                  DELIVERY CARRIER FLOW                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  SO Confirmed                                                         │
│      │                                                                 │
│      ▼                                                                 │
│  sale.order.set_delivery_line(carrier, rate)                        │
│      │                                                                 │
│      ├─► Creates sale.order.line (is_delivery=True)                  │
│      └─► Picks up pending pickings: picking.carrier_id = carrier.id   │
│                                                                   │
│  Picking Validated (button_validate)                                │
│      │                                                                 │
│      ▼                                                                 │
│  stock.picking._send_confirmation_email()                            │
│      │                                                                 │
│      └─► If integration_level == 'rate_and_ship':                    │
│              │                                                        │
│              ▼                                                        │
│          picking.send_to_shipper()                                    │
│              │                                                        │
│              ├─► carrier_id.send_shipping(pickings)                  │
│              │     │ (calls {provider}_send_shipping)               │
│              │     └─► { exact_price, tracking_number }             │
│              │                                                        │
│              ├─► carrier_price = exact_price                        │
│              │                                                        │
│              ├─► carrier_tracking_ref = tracking_number             │
│              │                                                        │
│              └─► _add_delivery_cost_to_so()                         │
│                    │                                                  │
│                    └─► Updates SOL price_unit to real cost            │
│                          (only if invoice_policy='real')             │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- [[Modules/Stock]] — Core stock picking management
- [[Modules/Sale]] — Sales order delivery line management
- [[Patterns/Workflow Patterns]] — Carrier state machine

---

## Performance Considerations

### Weight Computation — SQL vs ORM

**File:** `models/stock_move.py`, `_auto_init()`

The `stock.move` table gets a `weight` column created via raw SQL during module install:

```python
self.env.cr.execute("""
    UPDATE stock_move move
    SET weight = move.product_qty * product.weight
    FROM product_product product
    WHERE move.product_id = product.id
    AND move.state != 'cancel'
    """)
```

**L4 rationale:** This raw SQL bypasses ORM to avoid loading potentially millions of move rows into Python memory. For a large database (millions of `stock.move` rows), iterating in Python would exhaust RAM and likely OOM-kill the Odoo process. The SQL `UPDATE ... FROM` performs the join and multiplication in PostgreSQL, which handles it in a single pass.

**Performance implication:** After a product's weight is updated, existing `stock.move` rows retain their stale `weight` value until either (a) the move's `product_uom_qty` changes (triggering `_cal_move_weight` recompute) or (b) a manual database update is run. This means picking-level weight (`stock.picking.weight`) can be stale if only the product weight changed. The recomputation happens lazily — only when a picking is accessed and its `_cal_weight` is called.

**Mitigation:** If you change product weights on a large dataset, run a SQL update to refresh stale values:
```sql
UPDATE stock_move move
SET weight = move.product_qty * product.weight
FROM product_product product
WHERE move.product_id = product.id
AND move.state NOT IN ('cancel', 'done');
```

### `_compute_allowed_carrier_ids` — N+1 Potential

**File:** `models/stock_picking.py`

```python
def _compute_allowed_carrier_ids(self):
    for picking in self:
        carriers = self.env['delivery.carrier'].search(
            self.env['delivery.carrier']._check_company_domain(picking.company_id)
        )
        picking.allowed_carrier_ids = carriers.available_carriers(
            picking.partner_id, picking
        ) if picking.partner_id else carriers
```

**L4 analysis:**
- This is called as a `compute` method on every picking form load — O(n) search per picking.
- `available_carriers()` (defined in the `delivery` base module) applies domain filtering in Python (not SQL). For carriers with many tag-based exclusions, this can be expensive.
- **Mitigation:** The `allowed_carrier_ids` field is a `Many2many` stored on memory — it does not cause additional queries when accessed, only when computed. If a picking list view shows the carrier domain dropdown, this recomputes per record.

### `_get_aggregated_product_quantities` — HS Code Extension

**File:** `models/stock_move.py`, `StockMoveLine._get_aggregated_product_quantities`

The `_get_aggregated_product_quantities` override adds `hs_code` to the aggregated product data returned for shipping label generation and customs declarations. This is O(n) over all move lines — acceptable for typical pickings (10-100 lines) but may cause noticeable latency on bulk pickings with 1000+ lines.

### `send_to_shipper` — Carrier API Round-Trip

**File:** `models/stock_picking.py`

The `send_to_shipper()` method is the heaviest operation in the flow:

```python
def send_to_shipper(self):
    self.ensure_one()
    res = self.carrier_id.send_shipping(self)[0]  # HTTP call to carrier API
    # ...
    self.carrier_price = self.carrier_id._apply_margins(res['exact_price'], self.sale_id)
    if res['tracking_number']:
        related_pickings = ...  # Walk move graph O(depth)
    self._add_delivery_cost_to_so()
```

**L4 breakdown:**
- `send_shipping()` delegates to the provider-specific method (`dhl_send_shipping`, `fedex_send_shipping`, etc.). Each provider implementation makes an HTTP request to the carrier's API. The timeout and retry behaviour is provider-dependent.
- Walking the `move_orig_ids` / `move_dest_ids` graph to propagate tracking references is O(depth) where depth is the number of chained stock moves. For a typical drop-shipment (Purchase → Output → Delivery), depth = 3. For complex multi-step routes (Pick → Pack → Ship), depth can be 4-5.
- `_add_delivery_cost_to_so()` performs a `write` on a sale order line. This is a lightweight ORM write.
- **Failure handling:** If `send_shipping` raises `UserError`, Odoo rolls back the entire transaction. However, `_send_confirmation_email` catches `UserError` after the first successful picking to prevent cascading failures in a batch.

### `_send_confirmation_email` — Error Demotion Pattern

**File:** `models/stock_picking.py`

```python
for pick in self:
    try:
        if pick.carrier_id and pick.carrier_id.integration_level == 'rate_and_ship' and ...:
            pick.sudo().send_to_shipper()
    except (UserError) as e:
        if processed_carrier_picking:
            # Demote to activity warning
            pick.message_post(body=exception_message, ...)
            pick.sudo().activity_schedule(...)
        else:
            raise e
```

**L4 rationale:** The `processed_carrier_picking` flag prevents a `UserError` from rolling back pickings that were already successfully submitted to the carrier. Without this, a failure on picking #3 of a batch would undo the label generation for pickings #1 and #2. The demotion to a mail activity (rather than raising) ensures the user is notified asynchronously without blocking the UI.

### Tracking Reference Propagation — Graph Walk

**File:** `models/stock_picking.py`, `send_to_shipper()`

```python
accessed_moves = previous_moves = self.move_ids.move_orig_ids
while previous_moves:
    related_pickings |= previous_moves.picking_id
    previous_moves = previous_moves.move_orig_ids - accessed_moves
    accessed_moves |= previous_moves
```

**L4 analysis:** This is a breadth-first traversal of the stock move DAG (directed acyclic graph) through `move_orig_ids`. It avoids revisiting nodes using the `accessed_moves` set. The worst case is O(V) where V = total moves in the chain. For standard Odoo routes (2-5 moves deep), this is negligible. For complex manufacturing routes, it could be 10+ moves deep.

---

## Security Considerations

### Carrier API Credentials

The `delivery.carrier` model stores provider credentials (API keys, passwords) in the database. These are stored as plaintext Char fields in `delivery.carrier` (defined in the `delivery` base module, not this module). **L4 action:** Ensure the `delivery.carrier` table has appropriate ACL restrictions — only `stock.group_stock_manager` should have write access.

### `sudo()` Usage in `send_to_shipper`

**File:** `models/stock_picking.py`

```python
pick.sudo().send_to_shipper()
```

**L4 analysis:** `send_to_shipper()` runs as `sudo()` because the method may need to access records or trigger operations that the current user does not have explicit ACL rights for (e.g., creating attachments for shipping labels, writing to `carrier_tracking_ref`). This is a common pattern for background-like operations triggered from a UI action. The `sudo()` context is limited to the single `send_to_shipper()` call — it does not persist after the method returns.

**Security implication:** If a user can trigger `button_validate` on a picking, they can trigger `send_to_shipper()`. The carrier's API will be called with the configured credentials. There is no per-user access control on which carrier a user can use. **Recommendation:** Restrict carrier assignment (`carrier_id` write access) to `stock.group_stock_manager`.

### `_add_delivery_cost_to_so` — SO Write Without ACL Check

**File:** `models/stock_picking.py`

```python
def _add_delivery_cost_to_so(self):
    delivery_lines[0].write({'price_unit': self.carrier_price})
```

**L4 analysis:** This write is performed with the current user's rights. If a user can cause `send_to_shipper` to be called (e.g., by setting `integration_level = 'rate_and_ship'` on a carrier), they can write to the sale order line's price. The actual financial risk depends on whether the user can independently confirm the SO and create an invoice. For high-security deployments, wrap this in a `sudo()` + audit log, or require `stock.group_stock_manager` to set carriers with `rate_and_ship`.

### ACL Entries (`security/ir.model.access.csv`)

**File:** `security/ir.model.access.csv`

| ID | Model | Group | R | W | C | D | Notes |
|---|---|---|---|---|---|---|---|
| `delivery_stock.delivery_carrier` | `delivery.carrier` | `stock.group_stock_user` | 1 | 1 | 1 | 1 | Full access for stock users |

**L4 analysis:** Stock users get full CRUD on `delivery.carrier` records. This includes the ability to set carrier credentials (API keys, passwords) stored on the carrier. Consider restricting `Create` and `Unlink` to `stock.group_stock_manager` if carrier records should be managed centrally.

### No Company Security on Carrier Assignment

**L4 gap:** `carrier_id` on `stock.picking` has no company-level security enforced. A picking in Company A can have a carrier configured for Company B. The `domain` on `allowed_carrier_ids` does filter by company on search, but the `carrier_id` field itself does not enforce company restriction in `write`. If a user in Company A manipulates the domain or uses direct SQL, they could assign a Company B carrier. This is a minor risk but worth noting in multi-company deployments.

---

## Odoo 18 → Odoo 19 Changes

### `_auto_init` Column Creation — Breaking Change

**Change:** In Odoo 18, `stock.move.weight` was introduced as a stored computed field. In Odoo 19, the `_auto_init` hook was updated to create the column manually with raw SQL rather than relying on the ORM to initialize it.

**L4 rationale:** On databases with millions of `stock.move` rows, the ORM's automatic column creation plus `_auto_init` recomputation can cause an upgrade to run very slowly or run out of memory. By creating the column with raw SQL and computing values in a single UPDATE, Odoo 19 avoids loading all rows into Python memory.

### `invoice_policy` — New `('real', 'Real cost')` Option

**Change:** The `delivery.carrier.invoice_policy` selection added a `real` option. Previously, only `estimated` existed.

**Migration:** Existing `delivery.carrier` records retain their default (blank/estimated behaviour). After upgrade, set `invoice_policy = 'real'` on carriers where you want the actual shipping cost to be invoiced post-delivery.

### `route_ids` — New Many2many on `delivery.carrier`

**Change:** A new `stock.route` Many2many was added to `delivery.carrier`. This allows associating a carrier with specific stock routes (`shipping_selectable = True` routes). This is used in `_prepare_procurement_values` on `sale.order.line` to pass route IDs to procurement.

### `set_delivery_line` — Backward-Incompatible Post-Confirm Sync

**Change:** In Odoo 19, `sale.order.set_delivery_line()` was extended to sync `carrier_id` to all pending pickings when the order is already in `sale` state.

**L4 impact:** Previously, setting a delivery line on a confirmed SO did not update existing pending pickings. Custom code that relied on this behaviour (e.g., picking assignment being a separate manual step) will now happen automatically. This could surprise integrations that expect pickings to retain their previous carrier.

### `button_validate` Carrier Propagation Enhancement

**Change:** The carrier propagation logic was enhanced in `button_validate` to cover more scenarios. Previously, carrier was propagated to downstream pickings only when pickings were created. In Odoo 19, if a carrier is assigned to a picking at a later stage (after creation), the `button_validate` step propagates it forward.

```python
# Odoo 19 adds:
if picking.carrier_id:
    picking._get_next_transfers().filtered(
        lambda p: not p.carrier_id and any(rule.propagate_carrier for rule in p.move_ids.rule_id)
    ).write({'carrier_id': picking.carrier_id.id, 'carrier_tracking_ref': ...})
```

### Deprecated `_format_currency_amount`

**Change:** The `_format_currency_amount` method on `sale.order` is marked `# to remove in master` (Odoo 20). It formats a monetary amount with currency symbol placement. No new code should use this method.

### `free_over` Margin Calculation

**Change:** The `free_over` threshold check in `send_to_shipper` was updated to use `_compute_currency` and compare against `amount` field. This replaces older logic that directly compared amounts without currency conversion.

### `weight_bulk` Handling

**Change:** In `_get_packages_from_picking`, the `weight_bulk` case (products shipped without packages) is now handled with proper commodity extraction and package creation. Previously, this case could silently produce zero-weight packages.

### `_get_aggregated_product_quantities` — HS Code Extension

**Change:** A new override adds `hs_code` (from `product_tmpl_id.hs_code`) to the aggregated product data returned by `stock.move.line._get_aggregated_product_quantities`. This enables customs declarations to include harmonized system codes without requiring a separate query.

---

## send_to_shipper() Deep Dive

### Full Execution Flow

```
button_validate()
  └─► _pre_action_done_hook()         (stock base)
       └─► send_to_shipper()           (stock_delivery extension via _send_confirmation_email)
            │
            ├─► carrier_id.send_shipping(self)
            │     └─► {provider}_send_shipping(pickings)
            │           ├─► Build DeliveryPackage list
            │           │     └─► _get_packages_from_picking()
            │           │           ├─► Existing result_package_ids
            │           │           ├─► weight_bulk package
            │           │           └─► Commodity extraction
            │           │
            │           ├─► Build DeliveryCommodity list
            │           │     └─► _get_commodities_from_stock_move_lines()
            │           │
            │           ├─► HTTP POST to carrier API
            │           │
            │           └─► Returns: { exact_price, tracking_number, labels[] }
            │
            ├─► Apply free_over discount (if applicable)
            │     └─► exact_price = 0.0 if threshold met
            │
            ├─► Apply margins via _apply_margins()
            │     └─► carrier_price = margin-adjusted exact_price
            │
            ├─► Propagate tracking_number to related pickings
            │     └─► Walk move_orig_ids / move_dest_ids DAG
            │           └─► Concatenate if multiple tracking refs
            │
            ├─► Post confirmation message to picking chatter
            │     └─► "Shipment sent to carrier {name} with tracking {ref}"
            │           "Cost: {price} {currency}"
            │
            └─► _add_delivery_cost_to_so()
                  └─► Update or create delivery SOL with real price
```

### Provider Method Resolution

```python
def send_shipping(self, pickings):
    self.ensure_one()
    if hasattr(self, '%s_send_shipping' % self.delivery_type):
        return getattr(self, '%s_send_shipping' % self.delivery_type)(pickings)
    return None
```

**L4 mechanics:** The `hasattr` check is a dynamic method lookup. The method name is constructed as `{delivery_type}_send_shipping`. For a carrier with `delivery_type = 'fedex'`, this resolves to `fedex_send_shipping`. The method is called directly on the carrier recordset. Return value is a list of dicts, one per picking.

**Return contract:**
```python
[{
    'exact_price': float,       # Shipping cost in company currency
    'tracking_number': str,     # Carrier tracking reference
    # Future: 'labels': [base64 encoded PDFs]
}]
```

### Return Label Generation

```python
def get_return_label(self, pickings, tracking_number=None, origin_date=None):
    self.ensure_one()
    if self.can_generate_return:
        res = getattr(self, '%s_get_return_label' % self.delivery_type)(...)
        if self.get_return_label_from_portal:
            pickings.return_label_ids.generate_access_token()
        return res
```

**L4:** `get_return_label` delegates to `{delivery_type}_get_return_label`. If `get_return_label_from_portal` is True, access tokens are generated on the attachment records so customers can download return labels from the portal.

---

## cancel_shipment() Deep Dive

### Execution Flow

```
picking.cancel_shipment()
  └─► carrier_id.cancel_shipment(self)
        └─► {provider}_cancel_shipment(pickings)
              └─► HTTP POST/DELETE to carrier API to void shipment
  └─► message_post: "Shipment {ref} cancelled"
  └─► carrier_tracking_ref = False  (clears tracking ref)
```

### Provider-Level Cancellation

```python
def cancel_shipment(self, pickings):
    self.ensure_one()
    if hasattr(self, '%s_cancel_shipment' % self.delivery_type):
        return getattr(self, '%s_cancel_shipment' % self.delivery_type)(pickings)
```

**L4:** The `fixed` and `base_on_rule` providers raise `NotImplementedError` — they have no API to cancel. Only real carrier integrations (DHL, FedEx, UPS, etc.) implement actual cancellation via their APIs. If cancellation is needed for fixed carriers, a custom override is required.

### `fixed_cancel_shipment` / `base_on_rule_cancel_shipment`

```python
def fixed_cancel_shipment(self, pickings):
    raise NotImplementedError()
```

**L4 rationale:** Fixed-price and rule-based carriers do not have API connections, so there is nothing to cancel at the carrier side. The tracking reference is still cleared on the Odoo side so the picking can be re-shipped with a new carrier.

### Post-Cancellation State

After `cancel_shipment()`:
- `carrier_tracking_ref` is cleared to `False`
- The `stock.picking` record itself is **not** cancelled — that must be done separately via `action_cancel()`
- Any `ir.attachment` records (shipping labels) attached to the picking are **not** deleted — they remain as historical records
- The delivery cost on the sale order line is **not** reversed automatically — an accountant must credit note the delivery line

### Error Handling

If the carrier's API fails to cancel (e.g., the shipment was already in transit and cannot be stopped), the provider's `_cancel_shipment` method should raise `UserError`. This propagates to `picking.cancel_shipment()` and surfaces to the user. The tracking reference is **not** cleared in this case, which is correct — the shipment is still active.

---

## Failure Modes

| Failure Mode | Symptom | Root Cause | Resolution |
|---|---|---|---|
| `send_shipping` returns `None` | No tracking number, no error | Provider method not implemented for `delivery_type` | Implement `{provider}_send_shipping` or use a different carrier |
| `free_over` threshold not applied | Customer charged when they should get free shipping | `sale_id` is `False` on the picking (e.g., internal transfer) | `free_over` only applies when `self.sale_id` exists |
| Zero `carrier_price` after validation | Delivery line shows 0 cost on SO | `invoice_policy = 'real'` but `exact_price = 0` from carrier | Check carrier API response; some carriers return 0 for domestic shipments |
| Carrier not propagating to downstream pickings | Sub-pickings have no carrier | `propagate_carrier = False` on the stock rule | Set `propagate_carrier = True` on relevant rules |
| `weight = 0` on picking | Shipping label rejected by carrier | Products have no weight defined | Set `weight` on all `product.product` records |
| Package creation fails | Error "total weight is 0.0 kg" | All products in picking have `weight = 0` AND `package_type.base_weight = 0` | Assign weights to products or use a package type with `base_weight > 0` |
| Tracking URL broken | "No redirect on courier website" error | `tracking_url` template missing or tracking ref not set | Set `tracking_url` on carrier with `<shipmenttrackingnumber>` placeholder |
| Return label not generating | No return label attachment | Carrier has `can_generate_return = False` | Enable return shipments on carrier configuration |

---

## Related Documentation
- [[Modules/Stock]] — Core `stock.picking` model, `button_validate` flow, move line operations
- [[Modules/Sale]] — `sale.order` delivery line, `set_delivery_line`, `_create_delivery_line`
- [[Modules/Delivery]] — `delivery.carrier` base model, `integration_level`, `free_over`, provider interface
- [[Modules/Fleet]] — Fleet vehicle model
- [[Core/API]] — `@api.depends`, `@api.constrains`, `@api.onchange` decorators
- [[Patterns/Workflow Patterns]] — Picking validation workflow, carrier state machine
- [[Patterns/Security Patterns]] — ACL CSV, record rules for carrier access
- [[Tools/ORM Operations]] — `write()`, `search()`, `browse()` performance patterns
