---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #purchase
  - #stock
  - #procurement
  - #mto
  - #requisition
  - #blanket-order
---

# purchase_requisition_stock

# Module Overview

| Attribute | Value |
|-----------|-------|
| Technical Name | `purchase_requisition_stock` |
| Category | Supply Chain / Purchase |
| Version | 1.2 |
| Depends | `purchase_requisition`, `purchase_stock` |
| Auto-install | Yes |
| License | LGPL-3 |
| Author | Odoo S.A. |
| Application | No |

`purchase_requisition_stock` is a tie-down module that bridges two layers:

1. **Warehouse-aware requisitions**: Adds `warehouse_id` and `picking_type_id` to `purchase.requisition` so that blanket orders and purchase templates can drive warehouse-specific incoming receipts.
2. **Procurement chain propagation**: Ensures that `stock.rule` (the "buy" route) creates purchase orders linked to the correct blanket order, propagates downstream `stock.move` targets through PO lines, and surfaces requisitions in the upstream-document traceability chain.

It is **auto-installed** because `purchase_requisition` and `purchase_stock` are frequently co-deployed and the stock/warehouse linkage is assumed to be required when both are present.

**Module path:** `~/odoo/odoo19/odoo/addons/purchase_requisition_stock/`

---

## L1 — purchase.requisition Extensions: How Stock Moves and Replenishment Feed into Purchase Requisitions

### The Business Problem

In a warehouse replenishment scenario using the MTO (Make to Order) + Buy route:

1. A `stock.warehouse.orderpoint` triggers a procurement when product quantity falls below the minimum threshold.
2. The buy route's `stock.rule` runs, selecting a vendor. If the vendor has a confirmed blanket order for that product, the PO should be linked to the blanket order and use the blanket order's negotiated price and currency.
3. When the PO is confirmed and goods are received, the receipt's stock move must be chained to the origin procurement move so that downstream internal transfers fire automatically.
4. The `purchase.requisition` record (the blanket order) must be visible in the upstream traceability of the stock move.

Without `purchase_requisition_stock`, steps 2–4 are broken or incomplete: the PO has no `requisition_id`, the `move_dest_ids` chain is missing, and stock users cannot see the requisition in the traceability view.

### How Stock Moves Feed into Purchase Requisitions

```
stock.warehouse.orderpoint (min-max replenishment)
  └─ stock.rule.run_scheduler()
        └─ procurement created
              └─ stock.rule._run_buy()
                    └─ _make_po_get_domain()  ← adds requisition_id filter
                    └─ _prepare_purchase_order()  ← injects requisition_id, currency, partner_ref
                          └─ PO created, linked to blanket order
                                └─ stock.move (incoming) created on PO confirm
                                      └─ move_dest_ids linked to origin procurement move
                                            └─ MTO downstream fires on receipt validate
```

The blanket order does not "receive" stock moves — rather, the procurement system uses the blanket order as a vendor/price source when creating the PO, and the PO's receipt becomes part of the stock move chain.

### Dependency Chain

```
stock
  └── purchase_stock              (stock.rule _run_buy, _prepare_purchase_order, _make_po_get_domain)
        └── purchase_requisition   (purchase.requisition, purchase.requisition.line,
                                    purchase.requisition.create.alternative wizard)
              └── purchase_requisition_stock   ← this module

sale_purchase  (not a dependency, but related: sale → PO for subcontracted services)
```

This module has **no dependency on `sale_purchase`** — it operates purely in the stock/purchase/procurement space.

---

## L2 — Field Types, Defaults, Constraints

### `purchase.requisition` Extensions (file: `models/purchase_requisition.py`)

#### `warehouse_id`

```python
warehouse_id = fields.Many2one(
    'stock.warehouse',
    string='Warehouse',
    domain="[('company_id', '=', company_id)]"
)
```

| Attribute | Value |
|-----------|-------|
| Type | `Many2one(stock.warehouse)` |
| Company constraint | Domain restricts to same company as the requisition |
| Default | Set via `ir.default` in `data/purchase_requisition_stock_data.xml` to `stock.warehouse0` |
| Purpose | Route incoming goods to a specific warehouse when PO is created from this requisition |

#### `picking_type_id`

```python
picking_type_id = fields.Many2one(
    'stock.picking.type',
    'Operation Type',
    required=True,
    default=_default_picking_type_id,
    domain="['|', ('warehouse_id', '=', False), ('warehouse_id.company_id', '=', company_id)]"
)
```

| Attribute | Value |
|-----------|-------|
| Type | `Many2one(stock.picking.type)` |
| Required | Yes |
| Default | `_default_picking_type_id()` — first incoming picking type for the company |
| Readonly | When `state != 'draft'` |
| Purpose | Sets the `stock.picking.type` (incoming receipt) on POs created from this requisition |
| Domain | Allows both warehouse-scoped and company-level picking types |

#### `_default_picking_type_id()`

```python
def _default_picking_type_id(self):
    picking_type = self.env['stock.picking.type'].search([
        ('warehouse_id.company_id', '=', self.env.company.id),
        ('code', '=', 'incoming')
    ], limit=1)
    if not picking_type:
        self.env['stock.warehouse']._warehouse_redirect_warning()
    return picking_type
```

- Searches for **any** incoming picking type belonging to the current company. `limit=1` means the selection is non-deterministic if multiple warehouses have incoming types.
- If zero incoming picking types exist for the company, calls `_warehouse_redirect_warning()` (shows a warning banner) but still returns a falsy value.
- Since the field is `required=True`, record creation may fail if no incoming picking type exists.

---

### `purchase.requisition.line` Extensions (file: `models/purchase_requisition.py`)

#### `move_dest_id`

```python
move_dest_id = fields.Many2one(
    'stock.move',
    'Downstream Move',
    index='btree_not_null'
)
```

| Attribute | Value |
|-----------|-------|
| Type | `Many2one(stock.move)` |
| Index | `btree_not_null` — partial B-tree index on non-null values |
| Purpose | The stock move that this requisition line is intended to fulfil. Acts as the `move_dest_ids` source for the generated PO line. |

**Reverse relationship:** `stock.move.requisition_line_ids` is the O2M side.

**Index type `btree_not_null`:** Creates a partial B-tree index on `move_dest_id` only where it is non-null. This is a targeted, efficient index for queries filtering on "has a destination move" — common in the MTO chain.

#### `_prepare_purchase_order_line()` Override

```python
def _prepare_purchase_order_line(self, name, product_qty=0.0, price_unit=0.0, taxes_ids=False):
    res = super(PurchaseRequisitionLine, self)._prepare_purchase_order_line(
        name, product_qty, price_unit, taxes_ids
    )
    res['move_dest_ids'] = self.move_dest_id and [(4, self.move_dest_id.id)] or []
    return res
```

| Step | Action |
|------|--------|
| Parent builds base PO line dict | `product_id`, `product_uom_id`, `product_qty`, `price_unit`, `tax_ids`, `date_planned`, `analytic_distribution` |
| Bridge appends | `move_dest_ids: [Command.link(move_dest_id.id)]` |
| Guard | Empty list written if `self.move_dest_id` is falsy |

`[(4, id)]` is `Command.link()` — adds the downstream stock move to the PO line's `move_dest_ids`, creating the chain link.

---

### `stock.rule` Extensions (file: `models/stock.py`)

#### `_prepare_purchase_order()` Override

```python
def _prepare_purchase_order(self, company_id, origins, values):
    res = super(StockRule, self)._prepare_purchase_order(company_id, origins, values)
    values = values[0]
    res['partner_ref'] = values['supplier'].purchase_requisition_id.name
    res['requisition_id'] = values['supplier'].purchase_requisition_id.id
    if values['supplier'].purchase_requisition_id.currency_id:
        res['currency_id'] = values['supplier'].purchase_requisition_id.currency_id.id
    return res
```

| Key Added | Source | Purpose |
|-----------|--------|---------|
| `partner_ref` | `values['supplier'].purchase_requisition_id.name` | Vendor-facing reference on PO (blanket order name) |
| `requisition_id` | `values['supplier'].purchase_requisition_id.id` | Links PO to blanket order for traceability |
| `currency_id` | `values['supplier'].purchase_requisition_id.currency_id` | Overrides base (supplier/company) currency with blanket order's negotiated currency |

`values['supplier']` is the `product.supplierinfo` record selected by `_get_matching_supplier()`. The `purchase_requisition_id` on supplierinfo points to the `purchase.requisition.line` that was confirmed and created that supplierinfo (via `_create_supplier_info()`).

#### `_make_po_get_domain()` Override

```python
def _make_po_get_domain(self, company_id, values, partner):
    domain = super(StockRule, self)._make_po_get_domain(company_id, values, partner)
    if 'supplier' in values and values['supplier'].purchase_requisition_id:
        domain += (
            ('requisition_id', '=', values['supplier'].purchase_requisition_id.id),
        )
    return domain
```

Extends the PO search domain (from `purchase_stock`) to also filter by `requisition_id`. This ensures that **procurements triggered against a blanket order supplierinfo will only match an existing draft PO that is also linked to the same blanket order**. Without this, the base `purchase_stock` domain could match any draft PO to the same vendor and add lines to the wrong PO.

**Critical for correctness:** If a vendor has both a blanket order and a standalone supplierinfo for the same product, separate procurements should go to different POs. This domain enforces that segregation.

---

### `stock.move` Extensions (file: `models/stock.py`)

#### `requisition_line_ids`

```python
requisition_line_ids = fields.One2many(
    'purchase.requisition.line',
    'move_dest_id'
)
```

| Attribute | Value |
|-----------|-------|
| Type | `One2many(purchase.requisition.line, 'move_dest_id')` |
| Purpose | Reverse O2M of `move_dest_id`. Lists all requisition lines targeting this stock move as downstream destination. |
| Inverse | `purchase.requisition.line.move_dest_id` |

#### `_get_upstream_documents_and_responsibles()` Override

```python
def _get_upstream_documents_and_responsibles(self, visited):
    requisition_lines_sudo = self.sudo().requisition_line_ids
    if requisition_lines_sudo:
        return [(req_line.requisition_id, req_line.requisition_id.user_id, visited)
                for req_line in requisition_lines_sudo
                if req_line.requisition_id.state not in ('done', 'cancel')]
    else:
        return super(StockMove, self)._get_upstream_documents_and_responsibles(visited)
```

| Aspect | Detail |
|--------|--------|
| `sudo()` | Bypasses purchase ACLs to access `requisition_line_ids` — required because a stock user may trigger a move originating from a blanket order without having purchase order read rights |
| Return | Tuples of `(requisition, user_id, visited)` for requisitions in `draft` or `confirmed` state |
| Exclusion | `done` and `cancel` requisitions excluded — they no longer represent active responsibility |
| Fallback | If no requisition lines linked, delegates to standard upstream traversal (likely `stock.move` -> `stock.picking` -> `procurement_group`) |

---

### `purchase.order` Extensions (file: `models/purchase.py`)

#### `on_time_rate_perc`

```python
on_time_rate_perc = fields.Float(
    string="OTD",
    compute="_compute_on_time_rate_perc"
)

@api.depends('on_time_rate')
def _compute_on_time_rate_perc(self):
    for po in self:
        if po.on_time_rate >= 0:
            po.on_time_rate_perc = po.on_time_rate / 100
        else:
            po.on_time_rate_perc = -1
```

| Attribute | Value |
|-----------|-------|
| Type | `Float` (decimal fraction 0.0–1.0) |
| Depends | `on_time_rate` (stored integer, 0–100 or sentinel `-1`) |
| Purpose | Converts the stored integer `on_time_rate` to a true decimal fraction for the `percentage` widget |
| Display | Hidden when value is `-1` (N/A state) |

**Why a separate computed field?** The `percentage` widget in the web client expects a value in `[0, 1]` range. The stored `on_time_rate` is an integer 0–100 or `-1` sentinel. Separating them avoids the need to store a computed float and preserves the original integer for filtering/sorting.

#### `_onchange_requisition_id()` Override

```python
@api.onchange('requisition_id')
def _onchange_requisition_id(self):
    super(PurchaseOrder, self)._onchange_requisition_id()
    if self.requisition_id:
        self.picking_type_id = self.requisition_id.picking_type_id.id
```

| Order of execution | Action |
|-------------------|--------|
| Parent runs first | Populates `partner_id`, `fiscal_position_id`, `payment_term_id`, `currency_id`, `origin`, `note`, `date_order`, and creates PO lines from the requisition's line items |
| Bridge runs second | Sets `picking_type_id` from the requisition |

This override is the counterpart to the `stock.rule` `_prepare_purchase_order` override. It handles the **manual** flow (buyer sets `requisition_id` on the PO form). The `stock.rule` path (scheduler-triggered) does not go through this `onchange`.

---

### `purchase.order.line` Extensions (file: `models/purchase.py`)

#### `on_time_rate_perc`

```python
on_time_rate_perc = fields.Float(
    string="OTD",
    related="order_id.on_time_rate_perc"
)
```

Mirrors the PO-level OTD percentage onto each line for display in the line comparison view. This is a UX convenience — when comparing PO lines across alternative RFQs via `action_compare_alternative_lines`, buyers can see vendor reliability directly on each line.

---

## L3 — Cross-Model Integration: Stock ↔ Purchase Requisition

### Cross-Module Integration Map

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Blanket Order confirmed (purchase.requisition, state='confirmed')           │
│    └── purchase.requisition.line._create_supplier_info()                   │
│          └── product.supplierinfo created with purchase_requisition_line_id │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │ procurement triggered (MTO + buy route)
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  stock.rule._run_buy()                                                       │
│    ├── _make_po_get_domain() ──► + requisition_id filter                   │
│    │     (ensures blanket-order PO is isolated from standalone supplierinfo) │
│    └── _prepare_purchase_order()                                             │
│          ├── partner_ref = blanket_order.name                                │
│          ├── requisition_id = blanket_order.id                              │
│          └── currency_id = blanket_order.currency_id                          │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │ PO created / matched
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  purchase.requisition (via picking_type_id on requisition or rule)          │
│    └─ purchase.order.picking_type_id = requisition.picking_type_id           │
│         (receipt uses correct warehouse operation)                            │
│                                                                              │
│  stock.move (requisition_line_ids O2M) ←───────────────────────┐            │
│         ▲                                                     │            │
│         │ move_dest_id (M2O on purchase.requisition.line)    │            │
│         │                                                     │            │
│  purchase.requisition.line                                    │            │
│    └── _prepare_purchase_order_line()                          │            │
│          └── move_dest_ids = [link to stock.move]              │            │
│                                                               │            │
│  stock.move._get_upstream_documents_and_responsibles() ───────┘            │
│    └── Returns (requisition, user_id) via sudo()                           │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │ PO confirmed → receipt created
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  stock.picking (incoming receipt)                                            │
│    └── stock.move (picking_type_id = requisition.picking_type_id)           │
│          └── move_orig_ids = origin stock.move (chained automatically)        │
│                └─ MTO downstream fires → internal/output move created         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Override Pattern Summary

| Class Extended | File | Methods/Fields Added |
|----------------|------|----------------------|
| `purchase.requisition` | `models/purchase_requisition.py` | `warehouse_id`, `picking_type_id`, `_default_picking_type_id()` |
| `purchase.requisition.line` | `models/purchase_requisition.py` | `move_dest_id`, `_prepare_purchase_order_line()` |
| `stock.rule` | `models/stock.py` | `_prepare_purchase_order()`, `_make_po_get_domain()` |
| `stock.move` | `models/stock.py` | `requisition_line_ids`, `_get_upstream_documents_and_responsibles()` |
| `purchase.order` | `models/purchase.py` | `on_time_rate_perc`, `_compute_on_time_rate_perc()`, `_onchange_requisition_id()` |
| `purchase.order.line` | `models/purchase.py` | `on_time_rate_perc` (related) |
| `purchase.requisition.create.alternative` | `wizard/purchase_requisition_create_alternative.py` | `_get_alternative_values()`, `_get_alternative_line_value()` |

### Workflow Triggers

| Event | Chain of calls |
|-------|---------------|
| Blanket order confirmed | `action_confirm()` → `_create_supplier_info()` → `product.supplierinfo` created with `purchase_requisition_line_id` |
| Procurement scheduler runs | `stock.rule.run_scheduler()` → `stock.rule._run_buy()` → `_make_po_get_domain()` (with requisition_id filter) → `_prepare_purchase_order()` (with requisition_id, currency) → PO created |
| MTO move triggers buy rule | `stock.move._action_assign()` → procurement → `stock.rule._run_buy()` → same as above |
| PO created from requisition manually | PO form: set `requisition_id` → `_onchange_requisition_id()` → `picking_type_id` set from requisition → PO lines built from requisition lines with `move_dest_ids` |
| Alternative PO created | `action_create_alternative()` → `_get_alternative_values()` → `picking_type_id` + `reference_ids` + `move_dest_ids` propagated to alt PO lines |
| Incoming receipt validated | `stock.picking.button_validate()` → downstream MTO move fires → internal move created with `move_orig_ids` linked |
| Stock user views upstream chain | `stock.move._get_upstream_documents_and_responsibles()` → `requisition_id` + `user_id` returned via `sudo()` |

### Failure Modes

| Scenario | Failure Without Bridge | What the Module Does |
|----------|----------------------|---------------------|
| PO from blanket order vendor merges with standalone PO | Wrong PO gets the blanket order line added | `_make_po_get_domain()` adds `requisition_id` filter — POs from blanket orders are isolated |
| Blanket order currency ignored | PO uses vendor/company currency | `_prepare_purchase_order()` sets `currency_id` from blanket order |
| PO has no `requisition_id` link | Blanket order doesn't appear in PO traceability | `_prepare_purchase_order()` sets `requisition_id` on PO creation |
| MTO chain broken on receipt | Downstream internal move does not fire after receipt | `_prepare_purchase_order_line()` sets `move_dest_ids` linking receipt to origin move |
| Alternative PO loses warehouse receipt type | Receipt assigned to wrong warehouse | `_get_alternative_values()` propagates `picking_type_id` to alt PO |
| Alternative PO breaks MTO chain | Receipt not chained to origin move | `_get_alternative_line_value()` propagates `move_dest_ids` to alt PO lines |
| Stock user cannot see upstream blanket order | Procurement traceability incomplete | `_get_upstream_documents_and_responsibles()` returns requisition via `sudo()` |

---

## L4 — Version Change Odoo 18 → 19, Security, and Complete Test Coverage

### Odoo 18 → 19 Changes

The `purchase_requisition_stock` module saw **no structural changes** between Odoo 18 and Odoo 19. All field definitions, method overrides, and behaviors are identical.

The underlying `purchase_requisition` module (Odoo 18 → 19) had significant changes:
- Replaced `procurement.group`-based PO grouping with the new `purchase.order.group` technical model
- Split sequence codes into `purchase.requisition.blanket.order` and `purchase.requisition.purchase.template`
- Changed `product.supplierinfo` link from `purchase_requisition_id` (direct FK) to `purchase_requisition_line_id` (Many2one chain through `purchase.requisition.line`)

These `purchase_requisition` changes are fully compatible with this module's overrides — the `values['supplier'].purchase_requisition_id` in `_prepare_purchase_order()` resolves through the new chain and correctly points to the blanket order.

### Security Analysis

#### ACL File: `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_purchase_requisition_stock_manager,purchase.requisition,purchase_requisition.model_purchase_requisition,stock.group_stock_manager,1,0,1,0
access_purchase_requisition_line_stock_manager,purchase.requisition.line,purchase_requisition.model_purchase_requisition_line,stock.group_stock_manager,1,0,1,0
```

| ACL | Model | Group | Permissions |
|-----|-------|-------|-------------|
| `access_purchase_requisition_stock_manager` | `purchase.requisition` | `stock.group_stock_manager` | Read, Create (no Write, no Unlink) |
| `access_purchase_requisition_line_stock_manager` | `purchase.requisition.line` | `stock.group_stock_manager` | Read, Create (no Write, no Unlink) |

**Security rationale:**
- Stock managers need to **create** requisitions from the warehouse/procurement context (e.g., generating a blanket order from a procurement rule)
- Stock managers should **not edit or delete** active requisitions — those operations remain the purview of purchase managers
- Read access is granted so stock users can see requisition details in the traceability chain
- Both records have `perm_write=0` and `perm_unlink=0`

#### `sudo()` Usage

| Location | `sudo()` Scope | Justification |
|----------|----------------|---------------|
| `stock.move._get_upstream_documents_and_responsibles()` | `self.sudo().requisition_line_ids` | A stock user may trigger a move that originated from a blanket order. They should be able to see the requisition in traceability without needing purchase order read rights. This is a deliberate trade-off: traceability is needed across the stock/purchase boundary. |

#### Data Default: `data/purchase_requisition_stock_data.xml`

```xml
<function model="ir.default" name="set"
    eval="('purchase.requisition', 'warehouse_id', ref('stock.warehouse0'))"/>
```

Sets a global `ir.default` so newly created `purchase.requisition` records automatically have `warehouse_id = stock.warehouse0` pre-filled. Uses `noupdate="1"` — does not overwrite existing user-defined defaults on upgrade.

**Security note:** `ir.default` is a system-wide default, not a company-scoped one. If multiple companies exist, all new requisitions across all companies will default to `stock.warehouse0`. This may not be correct in multi-company setups.

---

### Complete Test Coverage

File: `tests/test_purchase_requisition_stock.py`

Class: `TestPurchaseRequisitionStock` (inherits `TestPurchaseRequisitionCommon` from `purchase_requisition.tests.common`)

---

#### `test_02_purchase_requisition_stock` — Blanket Order Supplier Priority

```
Setup:
  - vendor1 with supplierinfo price=50 for product_test
  - vendor2 (no existing supplierinfo)
  - product_test has buy+MTO routes

Scenario:
  1. Create stock move (MTO, procure_to_stock)
     └─ _action_confirm() triggers procurement

  2. PO created for vendor1 at price=50
     └─ Confirms base supplierinfo is selected (no blanket order yet)

  3. Create and confirm blanket order for vendor2, price=50
     └─ Creates supplierinfo with purchase_requisition_line_id set
     └─ Sequence: vendor1=2, vendor2=1 (vendor2 has lower sequence)

  4. Create second stock move → procurement triggers again
     └─ vendor1 PO quantity grows to 20 (same PO reused)
     └─ Confirms same-price supplierinfos from different sources don't change PO

  5. Change sequence: vendor1=2, vendor2=1
     └─ vendor2's blanket order supplierinfo now has higher priority (lower seq#)

  6. Create third stock move
     └─ New PO created for vendor2 linked to blanket order
     └─ Confirms _make_po_get_domain filter works correctly

Assertions:
  - purchase1.order_line.product_qty == 20  (same PO, accumulated)
  - len(purchase2) == 1  (separate PO for blanket order)
  - purchase2.requisition_id == requisition_blanket  (PO linked to blanket)
  - purchase2.order_line.price_unit == 50  (correct price from blanket)
```

---

#### `test_03_purchase_requisition_stock` — Two Blanket Orders → Two Separate POs

```
Setup:
  - vendor1 with two blanket orders (requisition_1, requisition_2)
  - Each blanket order has different product (product_1, product_2)
  - Both blanket orders confirmed before procurement runs

Scenario:
  1. Create stock move for product_1 and product_2 (MTO)
  2. Each procurement selects the blanket order supplierinfo
  3. _make_po_get_domain filter ensures each PO is isolated by requisition_id

Assertions:
  - POL1.order_id != POL2.order_id  (two separate POs)
  - Each PO correctly linked to its respective blanket order
  - Lines from blanket order use correct price_unit

Post-verification:
  - Add product_2 line to product_1's PO manually
  - supplierinfo without requisition_id (regular vendor1 supplierinfo) is selected
  - Confirms the domain filter only applies when purchase_requisition_id is set
```

---

#### `test_04_purchase_requisition_stock` — Alternative PO Copies PO Values

```
Setup:
  - Create PO with product_09, picking_type_id=outgoing, dest_address_id set

Scenario:
  1. Call action_create_alternative() with same vendor
  2. Wizard copies products (copy_products=True)

Assertions:
  - alt_po.picking_type_id == orig_po.picking_type_id
    └─ Confirms _get_alternative_values() propagates picking_type_id
  - alt_po.dest_address_id == orig_po.dest_address_id
    └─ From parent wizard (sale_purchase doesn't affect this)
  - alt_po.order_line.product_id == orig_po.order_line.product_id
  - alt_po.order_line.product_qty == orig_po.order_line.product_qty
  - len(alt_po.alternative_po_ids) == 2
    └─ Confirms purchase.order.group correctly links origin + alt

Post-confirm:
  - Confirm alt PO → warning wizard shows alternatives
  - action_cancel_alternatives() cancels origin PO
  - Confirms button_confirm() warning logic handles alternatives correctly
```

---

#### `test_05_move_dest_links_alternatives` — MTO Chain Through Alternative PO

```
Setup:
  - Warehouse with two-step reception (incoming only)
  - product with buy route
  - vendor_1 with supplierinfo
  - Orderpoint (RR): min_qty=1, max_qty=10

Scenario:
  1. Run scheduler → orderpoint creates procurement
  2. In two-step reception: first move is internal (Input→Stock),
     but since buy route is MTO, _run_buy() creates PO first
  3. PO created for vendor_1 (origin_po)

  4. Create alternative PO for vendor_2
     └─ copy_products=True
     └─ Confirms alt PO is linked via purchase_group_id

  5. Confirm alt PO, cancel alternatives
     └─ alt_po.state == 'purchase'
     └─ orig_po.state == 'cancel'

  6. Validate alt PO's incoming receipt (set qty done, button_validate)
     └─ Incoming move done

Assertions:
  - int_move.quantity == 10
    └─ MTO downstream internal move received correct quantity
  - int_move.move_orig_ids == incoming_move.id
    └─ _get_alternative_line_value() correctly propagated move_dest_ids
    └─ MTO chain is intact through the alternative PO flow

This is the most critical test for the MTO bridge aspect:
WITHOUT _get_alternative_line_value()'s move_dest_ids propagation,
the internal move would NOT fire after receipt validation.
```

---

#### `test_group_id_alternative_po` — `reference_ids` Propagation

```
Setup:
  - Create origin PO (no special reference_ids)

Scenario:
  1. action_create_alternative() with same vendor
  2. copy_products=True
  3. Confirm action_create_alternative()

Assertion:
  - alt_po.reference_ids == orig_po.reference_ids
    └─ Confirms _get_alternative_values() propagates reference_ids
```

---

## Data Files

### `data/purchase_requisition_stock_data.xml`

Sets global `ir.default` for `purchase.requisition.warehouse_id = stock.warehouse0`. See L4 Security section above.

### `views/purchase_requisition_views.xml`

Extends `purchase.requisition` form view. Injects `picking_type_id` field after `reference`:

```xml
<field name="picking_type_id"
    options="{'no_open': True, 'no_create': True}"
    groups="stock.group_adv_location"
    readonly="state != 'draft'"/>
```

| Attribute | Effect |
|-----------|--------|
| `options="no_open, no_create"` | Prevents opening or creating picking types from requisition form |
| `readonly="state != 'draft'"` | Only editable in draft state |
| `groups="stock.group_adv_location"` | Hidden from users without advanced location features |

### `views/purchase_views.xml`

**PO form patch** — Adds `on_time_rate_perc` column to the Alternative POs page:

```xml
<xpath expr="...alternative_po_ids...partner_id" position="after">
    <field name='on_time_rate_perc' widget="percentage" invisible="on_time_rate_perc &lt; 0"/>
</xpath>
```

**PO line compare tree patch** — Adds `on_time_rate_perc` column to the line comparison grid opened by `action_compare_alternative_lines`. Allows buyers to factor vendor reliability into the selection decision.

---

## Edge Cases and Failure Modes

| # | Scenario | Behavior |
|---|----------|----------|
| 1 | No incoming picking type configured for company | `_default_picking_type_id` returns `False`; field is `required=True` so record creation may fail. `_warehouse_redirect_warning()` shows a banner but does not prevent the failure. |
| 2 | `stock.warehouse0` deleted or wrong company | The `ir.default` silently fails; `warehouse_id` is empty. `picking_type_id` still defaults via `_default_picking_type_id` independently. |
| 3 | Same product+partner has both blanket order and regular supplierinfo | `_make_po_get_domain` filter isolates blanket-order PO. Regular supplierinfo used for non-blanket procurements. Sequence determines priority when both are available. |
| 4 | Blanket order confirmed, then currency changed on vendor | Existing supplierinfo retains the original currency. New procurements use the blanket order's `currency_id`. |
| 5 | Downstream move already `done` when PO line is created | `move_dest_ids` link persists in DB, but MTO chain does not fire on receipt validation because the move is no longer chainable. |
| 6 | Stock user views traceability of MTO move | `_get_upstream_documents_and_responsibles()` uses `sudo()` to access requisition; they see the blanket order and its `user_id` as responsible. If requisition has no `user_id`, returned `user_id` is `False`. |
| 7 | Alternative PO from PO created by scheduler | `picking_type_id` and `move_dest_ids` both propagated correctly. Receipt uses correct warehouse operation. |
| 8 | Multiple orderpoints for same product+vendor | Each creates separate procurement; `_make_po_get_domain` groups them into the same blanket-order PO if within the same company. |
| 9 | `reference_ids` propagation causes unintended PO merge | `purchase_stock._make_po_get_domain` uses `reference_ids` for grouping when `partner.group_rfq == 'default'` or dropship. Propagation may cause alternatives from different orderpoints to merge. Likely acceptable in the call-to-tenders workflow. |
| 10 | `on_time_rate` is `-1` sentinel | `on_time_rate_perc` set to `-1`; `invisible="on_time_rate_perc < 0"` hides the percentage widget in both PO form and compare tree. |

---

## Performance Notes

| Area | Observation |
|------|-------------|
| `_prepare_purchase_order` and `_make_po_get_domain` | Both read `values[0]` only — safe because all procurements sharing the same blanket order have the same `product.supplierinfo` |
| `move_dest_id` index `btree_not_null` | Partial B-tree index is small and efficient; only indexed where non-null |
| `on_time_rate_perc` | Stored computed float; recalculates when `on_time_rate` changes on the PO |
| `ir.default` | Applies to every new `purchase.requisition` creation globally; no company-scoped optimization |

---

## File Paths

| File | Absolute Path |
|------|--------------|
| Manifest | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/__manifest__.py` |
| Models `__init__` | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/models/__init__.py` |
| `purchase.requisition` extensions | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/models/purchase_requisition.py` |
| `purchase.order` extensions | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/models/purchase.py` |
| `stock.rule` / `stock.move` extensions | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/models/stock.py` |
| Wizard override | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/wizard/purchase_requisition_create_alternative.py` |
| Tests | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/tests/test_purchase_requisition_stock.py` |
| Security ACL | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/security/ir.model.access.csv` |
| Data defaults | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/data/purchase_requisition_stock_data.xml` |
| View patches | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/views/purchase_views.xml` |
| Requisition view patch | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_stock/views/purchase_requisition_views.xml` |
| Parent `purchase_requisition` | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition/` |
| Parent `purchase_stock` | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_stock/` |
| Parent `stock` | `/Users/tri-mac/odoo/odoo19/odoo/addons/stock/` |

---

## Related Modules

- `[Modules/Stock](modules/stock.md)` — `stock.move`, `stock.rule`, `stock.picking`, `stock.warehouse`, MTO route
- `[Modules/Purchase](modules/purchase.md)` — `purchase.order`, `purchase.order.line`, `stock.rule._run_buy()`
- `[Modules/purchase_requisition](modules/purchase_requisition.md)` — blanket orders, purchase templates, alternative PO wizard, `purchase.order.group`, `purchase.requisition.create.alternative`
- `purchase_stock` — base stock/purchase bridge: `stock.rule._run_buy()`, PO creation from procurement, supplierinfo selection
- `sale_purchase` — related but not a dependency: creates PO from `service_to_purchase` SOL on SO confirmation
- `[Modules/Sale](modules/sale.md)` — sale order → subcontracted service → PO flow
