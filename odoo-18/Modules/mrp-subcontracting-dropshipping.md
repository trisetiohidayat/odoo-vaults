---
Module: mrp_subcontracting_dropshipping
Version: Odoo 18
Type: Integration
Tags: #odoo, #odoo18, #mrp, #subcontracting, #dropshipping, #inventory
Related Modules: mrp_subcontracting, stock_dropshipping, stock_purchase
---

# MRP Subcontracting Dropshipping (`mrp_subcontracting_dropshipping`)

## Module Overview

**Location:** `~/odoo/odoo18/odoo/addons/mrp_subcontracting_dropshipping/`
**Depends:** `mrp_subcontracting`, `stock_dropshipping`
**Category:** Inventory/Purchase
**License:** LGPL-3
**Auto-install:** Yes

This bridge module combines two supply chain patterns — **subcontracting** and **dropshipping** — so that a component vendor can ship parts directly to a subcontractor, rather than through the manufacturer's warehouse. The finished product still arrives at the manufacturer (or customer) via the normal subcontracting route.

---

## Business Flow

```
Vendor (component supplier)
    │
    │  PO: Buy, Dropship Subcontractor route
    │  Location: Supplier → Subcontractor's location
    │
    ▼
Subcontractor (receives components, manufactures finished goods)
    │
    │  MO: subcontract, receives components, produces finished product
    │
    ▼
Manufacturer / Customer
```

**Scenario:** You subcontract manufacturing of product "X" to Subcontractor SC. X requires component "A". Rather than stocking A in your warehouse and delivering it to SC, you PO A from Vendor V with **Dropship Subcontractor on Order** route: V ships A directly to SC. SC uses A to make X, then delivers X to you.

---

## Route: `Dropship Subcontractor on Order`

**External ID:** `mrp_subcontracting_dropshipping.route_subcontracting_dropshipping`
**Type:** `stock.route` — product-selectable
**Sequence:** 5

```
Supplier Location → Subcontractor Location (Partner Stock) → Production Location
```

This is a **Make-to-Stock** (MTS) procurement route at the supplier → subcontractor leg. The pull rule from subcontractor location to production location is **Make-to-Order** (MTO) — controlled by `subcontracting_dropshipping_pull_id` on `stock.warehouse`.

---

## Models

### `res.company` — Extended

**File:** `models/res_company.py`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `dropship_subcontractor_pick_type_id` | Many2one → `stock.picking.type` | Per-company picking type for dropship-to-subcontractor receipts |

#### Company Setup Methods

| Method | Description |
|--------|-------------|
| `_create_subcontracting_dropshipping_sequence()` | Creates `ir.sequence` with code `mrp.subcontracting.dropshipping`, prefix `DSC/` |
| `_create_subcontracting_dropshipping_picking_type()` | Creates `stock.picking.type` with code `dropship`, warehouse=False, src=`stock.location_suppliers`, dest=`company.subcontracting_location_id` |
| `_create_subcontracting_dropshipping_rules()` | Creates `stock.rule` for supplier→subcontractor-location with `action=buy` |
| `_create_missing_subcontracting_dropshipping_sequence()` | Idempotent — only creates if not exists |
| `_create_missing_subcontracting_dropshipping_picking_type()` | Idempotent per company |
| `_create_missing_subcontracting_dropshipping_rules()` | Idempotent per company |

The picking type is named **"Dropship Subcontractor"** with sequence code `DSC`. It is **per company** but not linked to a specific warehouse.

#### Hooks into Base Company Creation

| Hook | Calls |
|------|-------|
| `_create_per_company_sequences()` | `_create_subcontracting_dropshipping_sequence()` |
| `_create_per_company_picking_types()` | `_create_subcontracting_dropshipping_picking_type()` |
| `_create_per_company_rules()` | `_create_subcontracting_dropshipping_rules()` |

---

### `stock.warehouse` — Extended

**File:** `models/stock_warehouse.py`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `subcontracting_dropshipping_to_resupply` | Boolean, default=`True` | Enable/disable dropship resupply for this warehouse's subcontracting location |
| `subcontracting_dropshipping_pull_id` | Many2one → `stock.rule` | MTO pull rule: subcontractor location → production location |

#### Methods

##### `_generate_global_route_rules_values() → updates`
Extends base warehouse rule generation to add the dropship subcontracting pull rule:

```python
'subcontracting_dropshipping_pull_id': {
    'depends': ['subcontracting_dropshipping_to_resupply'],
    'create_values': {
        'procure_method': 'make_to_order',   # MTO from subcontractor to production
        'action': 'pull',                    # Pull components from subcontractor loc
        'route_id': route_id.id,             # Dropship Subcontractor on Order
        'location_dest_id': production_location_id.id,
        'location_src_id': subcontract_location_id.id,
        'picking_type_id': self.subcontracting_type_id.id,
    },
    'update_values': {'active': self.subcontracting_dropshipping_to_resupply}
}
```

##### `write(vals)`
When `subcontracting_dropshipping_to_resupply` changes, calls `_update_dropship_subcontract_rules()` and `update_global_route_dropship_subcontractor()`.

##### `_update_dropship_subcontract_rules()`
Archives or unarchives pull rules matching the route + warehouse + subcontracting locations.

##### `update_global_route_dropship_subcontractor()`
Toggles the global route `route_subcontracting_dropshipping` active state based on whether any active pull rules exist. Also toggles the company-level picking type active state.

**L4 Note:** Disabling `subcontracting_dropshipping_to_resupply` on a warehouse archives the pull rules but leaves the push rule (supplier→subcontractor) intact. This allows dropship purchases to still arrive at the subcontractor but prevents automatic MO triggering from the subcontractor location.

---

### `stock.rule` — Extended

**File:** `models/stock_rule.py`

#### Overrides

##### `_prepare_purchase_order(company_id, origins, values)`
If `partner_id` is not already set and the rule's destination is a subcontracting location, pulls the partner from the procurement group's partner:

```python
if 'partner_id' not in values[0] \
    and (company_id.subcontracting_location_id.parent_path in self.location_dest_id.parent_path
         or self.location_dest_id.is_subcontracting_location):
    values[0]['partner_id'] = values[0]['group_id'].partner_id.id
```

**Effect:** The PO for the dropshipped component is automatically addressed to the subcontractor as the delivery address (`dest_address_id`), ensuring V ships to SC.

##### `_make_po_get_domain(company_id, values, partner)`
Adds `dest_address_id` to the PO merge domain when a `partner_id` is set:

```python
domain += (('dest_address_id', '=', values.get('partner_id')),)
```

This ensures that each subcontractor gets their own PO even if the same component+vendor combination exists for other flows.

---

### `stock.move` — Extended

**File:** `models/stock_move.py`

#### Methods Overridden

##### `_prepare_procurement_values()`
If the move originates from a subcontracting location and no `partner_id` is set in procurement values, pulls from `group_id.partner_id`:

```python
def _prepare_procurement_values(self):
    vals = super()._prepare_procurement_values()
    partner = self.group_id.partner_id
    if not vals.get('partner_id') and partner and self.location_id.is_subcontracting_location:
        vals['partner_id'] = partner.id
    return vals
```

##### `_is_dropshipped()`
Extends the dropship detection to include the **subcontractor dropship** pattern:

```python
def _is_dropshipped(self):
    res = super()._is_dropshipped()
    return res or (
        self.partner_id.property_stock_subcontractor.parent_path
        and self.partner_id.property_stock_subcontractor.parent_path in self.location_id.parent_path
        and self.location_dest_id.usage == 'customer'
    )
```

**Detection logic:** A move is a subcontractor dropship when:
- The source location's parent path starts with the subcontractor's `property_stock_subcontractor` location path (i.e., the move originates from a location inside the subcontractor's partner record)
- The destination is a customer (direct delivery to end customer)

##### `_is_dropshipped_returned()`
Mirrors `_is_dropshipped()` for return moves:

```python
def _is_dropshipped_returned(self):
    res = super()._is_dropshipped_returned()
    return res or (
        self.location_id.usage == 'customer'
        and self.partner_id.property_stock_subcontractor.parent_path
        and self.partner_id.property_stock_subcontractor.parent_path in self.location_dest_id.parent_path
    )
```

##### `_is_purchase_return()`
Extends purchase return detection to include dropship returns:

```python
def _is_purchase_return(self):
    res = super()._is_purchase_return()
    return res or self._is_dropshipped_returned()
```

---

### `stock.picking` — Extended

**File:** `models/stock_picking.py`

#### Overrides

##### `_compute_is_dropship()`
Adds dropship subcontractor pickings to the `is_dropship` flag:

```python
def _compute_is_dropship(self):
    dropship_subcontract_pickings = self.filtered(
        lambda p: p.location_dest_id.is_subcontracting_location and p.location_id.usage == 'supplier'
    )
    dropship_subcontract_pickings.is_dropship = True
    super(StockPicking, self - dropship_subcontract_pickings)._compute_is_dropship()
```

**Recognition:** A picking is a dropship subcontractor picking if its destination is the subcontracting location and its source is the supplier.

##### `_get_warehouse(subcontract_move)`
Determines which warehouse to use for a subcontract move with a `sale_line_id`:

```python
def _get_warehouse(self, subcontract_move):
    if subcontract_move.sale_line_id:
        return subcontract_move.sale_line_id.order_id.warehouse_id
    return super(StockPicking, self)._get_warehouse(subcontract_move)
```

**Effect:** When the finished subcontracted product is being dropshipped to a customer via a sale order, the correct warehouse (and thus correct picking types) are used.

##### `_action_done()`
Handles **stock valuation layer compensation** for dropshipped subcontract moves:

```python
def _action_done(self):
    res = super()._action_done()
    svls = self.env['stock.valuation.layer']
    for move in self.move_ids:
        if not (move.is_subcontract and move._is_dropshipped() and move.state == 'done'):
            continue
        # Gets SVL value from the MO (subcontract SVL) vs. dropship SVL
        # If MO cost > dropship cost, creates a compensating SVL with value = -(diff)
        # This prevents double-counting of component costs
```

**Key logic:**
- A dropshipped subcontract move has two SVL sets: the MO's component cost layers and the dropship receipt's landed cost layer
- If `subcontract_value > dropship_value`, the difference is a negative SVL (credit) on the dropship move to avoid inflating inventory value
- Handles backorder chains correctly via `backorder_sequence`

##### `_prepare_subcontract_mo_vals(subcontract_move, bom)`
Ensures the subcontract MO is created with a picking type even when the subcontract move has no explicit warehouse:

```python
def _prepare_subcontract_mo_vals(self, subcontract_move, bom):
    res = super()._prepare_subcontract_mo_vals(subcontract_move, bom)
    if not res.get('picking_type_id') and (
            subcontract_move.location_dest_id.usage == 'customer'
            or subcontract_move.location_dest_id.is_subcontracting_location
    ):
        default_warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', subcontract_move.company_id.id)], limit=1
        )
        res['picking_type_id'] = default_warehouse.subcontracting_type_id.id,
    return res
```

**Effect:** When a subcontract PO for a dropshipped product (delivered directly to customer) is confirmed, the MO is still created with a valid picking type.

---

### `purchase.order` — Extended

**File:** `models/purchase.py`

#### Computed/Related Fields

| Field | Type | Derivation |
|-------|------|------------|
| `default_location_dest_id_is_subcontracting_loc` | Boolean | Related to `picking_type_id.default_location_dest_id.is_subcontracting_location` |

#### Methods

##### `_compute_dest_address_id()`
When the PO's picking type delivers to a subcontracting location, sets `dest_address_id` to the single subcontractor (if only one is associated with that location):

```python
def _compute_dest_address_id(self):
    dropship_subcontract_pos = self.filtered(lambda po: po.default_location_dest_id_is_subcontracting_loc)
    for order in dropship_subcontract_pos:
        subcontractor_ids = order.picking_type_id.default_location_dest_id.subcontractor_ids
        order.dest_address_id = subcontractor_ids if len(subcontractor_ids) == 1 else False
    super(PurchaseOrder, self - dropship_subcontract_pos)._compute_dest_address_id()
```

##### `onchange_picking_type_id()`
Warns the user when the picking type is set to a subcontracting type:

```python
def onchange_picking_type_id(self):
    if self.default_location_dest_id_is_subcontracting_loc:
        return {
            'warning': {
                'title': _('Warning'),
                'message': _('Please note this purchase order is for subcontracting purposes.')
            }
        }
```

##### `_get_destination_location()`
Returns the subcontractor's `property_stock_subcontractor` location when the PO is for subcontracting:

```python
def _get_destination_location(self):
    self.ensure_one()
    if self.default_location_dest_id_is_subcontracting_loc:
        return self.dest_address_id.property_stock_subcontractor.id
    return super()._get_destination_location()
```

---

### `stock.replenish.mixin` — Extended

**File:** `models/stock_replenish_mixin.py`

##### `_get_allowed_route_domain()`
Excludes the dropship subcontracting route from the replenishment UI:

```python
def _get_allowed_route_domain(self):
    domains = super()._get_allowed_route_domain()
    return expression.AND([
        domains,
        [('id', '!=', self.env.ref('mrp_subcontracting_dropshipping.route_subcontracting_dropshipping').id)]
    ])
```

**Reason:** The dropship subcontracting route should only be triggered automatically by the subcontracting BOM logic, not by manual reorder rules in the replenishment widget.

---

### `stock.warehouse.orderpoint` — Extended

**File:** `models/stock_orderpoint.py`

##### `_prepare_procurement_values(date, group)`
When an orderpoint triggers procurement for a subcontracting location with exactly one subcontractor, pre-populates `partner_id` in the procurement values:

```python
def _prepare_procurement_values(self, date=False, group=False):
    vals = super()._prepare_procurement_values(date, group)
    if not vals.get('partner_id') and self.location_id.is_subcontracting_location \
            and len(self.location_id.subcontractor_ids) == 1:
        vals['partner_id'] = self.location_id.subcontractor_ids.id
    return vals
```

---

## L4: End-to-End Flow (Vendor Dropships Components to Subcontractor)

### Step 1: BOM Configuration
Product P is a subcontracted product. Its BOM:
- Type: `subcontract`
- subcontractor: `Subcontractor SC`
- Components: `[Comp A × 2]`

The `Dropship Subcontractor on Order` route is enabled on the warehouse (default).

### Step 2: Automatic PO Creation
When a MO for P is confirmed, the subcontracting flow triggers a procurement for Comp A with the `Dropship Subcontractor on Order` route. This creates a PO:
- Vendor: `Vendor V` (from Comp A's vendor list)
- Delivery address: `Subcontractor SC` (via `dest_address_id`)
- Picking type: `Dropship Subcontractor` (code `DSC`)
- Route: `Dropship Subcontractor on Order`

### Step 3: Component Delivery
Vendor V ships Comp A directly to Subcontractor SC's location.

### Step 4: MO Processing
Subcontractor SC receives Comp A, manufactures P, and delivers it. The MO is processed normally:
- Receipt of P at warehouse (or direct to customer if sale order attached)
- Component consumption: Comp A is consumed from SC's subcontracting location

### Step 5: Valuation
When the dropship subcontracting picking is validated (`_action_done()`):
- The dropship SVL records the landed cost of P
- The MO SVL records the component costs
- If MO cost > dropship cost, a compensating negative SVL is created to avoid double-counting

---

## L4: Route Configuration Details

| Route Element | Type | Procurement Method | Location Src | Location Dest |
|--------------|------|-------------------|-------------|---------------|
| **Push** (buy rule) | `stock.rule`, `action=buy` | `make_to_stock` | Supplier | Subcontractor location |
| **Pull** (subcontract rule) | `stock.rule`, `action=pull` | `make_to_order` | Subcontractor location | Production location |
| **Dropship Subcontractor** | `stock.route` | — | — | — |

The **push rule** is company-wide (not per-warehouse). The **pull rule** is per-warehouse and controlled by `subcontracting_dropshipping_to_resupply` on `stock.warehouse`.

---

## L4: Interaction with Sale Orders

When a sale order line with a subcontracted product that has `Dropship Subcontractor on Order` route is confirmed:
1. A PO is created for the component via the dropship subcontracting rule
2. The finished product move uses `_get_warehouse(sale_line_id)` to determine the warehouse
3. If the SO has `warehouse_id` set, that warehouse's subcontracting picking type is used
4. The finished product can be delivered directly to the customer (`location_dest_id.usage == 'customer'`)
