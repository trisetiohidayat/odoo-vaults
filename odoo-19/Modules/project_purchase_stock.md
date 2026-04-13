# project_purchase_stock

## Overview

| Attribute | Value |
|---|---|
| **Name** | Project - Purchase - Stock |
| **Version** | 1.0 |
| **Category** | Services/Project |
| **Depends** | `project_purchase`, `project_stock` |
| **Auto-install** | Yes |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description

`project_purchase_stock` bridges the gap between `purchase.order` and `stock.picking` in a project context. It ensures that when a purchase order linked to a project generates a stock picking (incoming receipt), that picking carries the same `project_id`, completing the full chain:

```
Project → Purchase Order → Stock Picking
```

Without this module, POs linked to projects produce pickings without a project reference, breaking project-centric visibility into stock operations.

## Architecture

### Dependency Chain

```
stock.rule (stock)
        │
        ├── project_purchase_stock.stock_rule
        │       └── _prepare_purchase_order()  → injects project_id into PO vals
        │       └── _make_po_get_domain()       → groups by project_id in PO search
        │
purchase.order (purchase)
        │
        ├── project_purchase.purchase_order
        │       └── project_id: Many2one('project.project')
        │
        └── project_purchase_stock.purchase_order
                └── _prepare_picking()          → injects project_id into picking vals

stock.picking (project_stock)
        └── project_id: Many2one('project.project')
```

### Module Structure

```
project_purchase_stock/
├── __init__.py
├── __manifest__.py
└── models/
    ├── __init__.py
    ├── purchase_order.py    # extends purchase.order
    └── stock_rule.py        # extends stock.rule
```

## Models

### `purchase.order` — extends `purchase.order`

**Inherited from**: `purchase.purchase` (standard purchase module)
**Also extended by**: `project_purchase` (adds `project_id` field)

#### Method: `PurchaseOrder._prepare_picking()`

```python
def _prepare_picking(self) -> dict
```

**Purpose**: Called by `purchase_stock.PurchaseOrder._create_picking()` when the PO reaches `purchase` state and has consumable/storable products. Builds the `stock.picking` creation dictionary.

**Inheritance chain**:
1. `purchase_stock/models/purchase_order.py` provides the base implementation (returns picking fields: `picking_type_id`, `partner_id`, `location_id`, etc.)
2. `project_purchase_stock` overrides and appends `project_id`

**Logic**:
```python
def _prepare_picking(self):
    res = super()._prepare_picking()
    if not self.project_id:           # guard: only inject if PO has a project
        return res
    return {
        **res,                          # spread base values
        'project_id': self.project_id.id,  # inject project reference
    }
```

**Trigger**: When `purchase.order` button "Receive Products" (`action_create_picking`) is executed, or automatic picking creation on PO confirmation.

**Failure modes**:
- If `project_id` is `False` (no project set), the guard `if not self.project_id` silently returns the base dict without project injection.
- Template projects (`is_template = True`) are excluded from the `project_id` domain on `purchase.order` and `stock.picking`, so pickings from template-linked POs will have `project_id = False`.

---

### `stock.rule` — extends `stock.rule`

**Inherited from**: `stock/stock_rule.py` (base stock rule)
**Also extended by**: `purchase_stock/models/stock_rule.py` (buy-rule procurement)

#### Method: `StockRule._prepare_purchase_order(company_id, origins, values) -> dict`

```python
def _prepare_purchase_order(self, company_id, origins, values) -> dict
```

**Purpose**: Called during the buy-type procurement run (`_run_buy`). Builds the `purchase.order` creation dictionary when no existing PO matches the procurement group domain.

**Inheritance chain**:
1. `stock/stock_rule.py` base method returns `{}` (stub/placeholder).
2. `purchase_stock/models/stock_rule.py` provides the full implementation (partner, currency, date_order, etc.).
3. `project_purchase_stock` overrides to inject `project_id`.

**Logic**:
```python
def _prepare_purchase_order(self, company_id, origins, values):
    res = super()._prepare_purchase_order(company_id, origins, values)
    if values[0].get('project_id'):           # values is a list of procurement value dicts
        res['project_id'] = values[0].get('project_id')
    return res
```

**Parameters**:
- `company_id`: `res.company` record — the procurement company
- `origins`: list of strings — procurement origins (used for PO `.origin` field)
- `values`: list of dicts — each dict is the `procurement.values` for one procurement group; `values[0]` is the first (arbitrary) procurement's values, used for shared fields

**Trigger**: When a procurement rule with `action = 'buy'` runs and no existing PO satisfies `_make_po_get_domain`.

**Edge cases**:
- `values[0].get('project_id')` can be `False` or absent — the guard only acts if `project_id` is truthy (non-empty, non-False).
- If `project_id` is set on the procurement values, it is carried into the PO.
- `values` is a list; the code reads `values[0]` to get shared project context (first procurement wins). This means a single PO generated from multiple procurements will inherit `project_id` from whichever procurement happened to be processed first — which is acceptable since all grouped procurements share the same project origin.

---

#### Method: `StockRule._make_po_get_domain(company_id, values, partner) -> list`

```python
def _make_po_get_domain(self, company_id, values, partner) -> list
```

**Purpose**: Returns the domain used to search for an existing PO to group new procurement lines into. Adds `project_id` to the base domain to prevent cross-project PO merging.

**Inheritance chain**:
1. `stock/stock_rule.py` base method returns an empty list (stub).
2. `purchase_stock/models/stock_rule.py` provides the full domain (partner, state, picking_type, company, user, currency).
3. `project_purchase_stock` overrides to add `project_id` to that domain.

**Logic**:
```python
def _make_po_get_domain(self, company_id, values, partner):
    domain = super()._make_po_get_domain(company_id, values, partner)
    domain += (('project_id', '=', values.get('project_id', False)),)
    return domain
```

**Base domain from `purchase_stock`**:
```python
domain = [
    ('partner_id', '=', partner.id),
    ('state', '=', 'draft'),
    ('picking_type_id', '=', self.picking_type_id.id),
    ('company_id', '=', company_id.id),
    ('user_id', '=', partner.buyer_id.id),
    ('currency_id', '=', currency.id),
]
```

**`project_purchase_stock` augmentation**:
```python
domain += (('project_id', '=', values.get('project_id', False)),)
```

**Result**: PO matching domain includes project_id equality. This means:
- Procurements from Project A will never be merged into a PO for Project B.
- A procurement without a `project_id` (`values.get('project_id', False)` returns `False`) will only match POs that also have `project_id = False`.
- `project_id` is compared with `=`, not `in` — exact match only.

**Trigger**: Called in `_run_buy` before `_prepare_purchase_order` to check for existing POs. Also called for every procurement being grouped.

**Security considerations**:
- The domain uses exact project_id matching; users without access to a project cannot trigger procurement that would create or add to a project-linked PO. Standard Odoo record rules on `project.project` apply.
- `stock.rule` operations run as `SUPERUSER_ID` in `_run_buy` (line: `self.env['purchase.order'].sudo().search(...)`), bypassing ACL for PO creation. This is intentional — procurement scheduler runs as cron/superuser to avoid permission gaps.

## Cross-Module Integration

### Procurement Flow (Stock → Purchase)

```
Stock Replenishment / Orderpoint triggered
  → stock_rule.run()
    → _run_buy()
      → _make_po_get_domain()     [project_purchase_stock adds project_id clause]
      → search for existing PO     [finds PO with same project_id]
        or
      → _prepare_purchase_order()  [project_purchase_stock injects project_id]
        → purchase.order.create()
```

When a stock orderpoint generates a procurement for a product linked to a project (e.g., via `project_id` set on a `stock.move` or `stock.picking` that triggered the procurement), the `project_id` in `procurement.values` is carried through to `_prepare_purchase_order` and `_make_po_get_domain`.

### Direct PO Flow (Purchase → Stock)

```
User creates PO with project_id
  → PO confirmed (button: Confirm Order)
    → action_confirm()
      → _create_picking()
        → _prepare_picking()       [project_purchase_stock injects project_id]
          → stock.picking.create() [picking has project_id]
```

The PO's `project_id` (set by user) is propagated into the incoming receipt picking.

### Project Actions (from project_stock)

`project.project` has three action methods added by `project_stock`:
- `action_open_receipts()` — opens incoming pickings for the project
- `action_open_deliveries()` — opens outgoing pickings for the project
- `action_open_all_pickings()` — opens all pickings for the project

These use a `Domain('project_id', '=', self.id)` so they automatically pick up pickings created via `project_purchase_stock`.

## Performance

- The module adds two method overrides — one filter guard (`if not self.project_id`) and two domain augmentations. Zero performance impact under normal operations.
- `_make_po_get_domain` adds one tuple to the domain — the PostgreSQL planner will use the `project_id` index on `purchase_order` if one exists.
- Procurement grouping (via `_make_po_get_domain`) with project_id means smaller PO batches (one PO per project per vendor) vs. one PO per vendor — may result in slightly more POs but better project cost attribution accuracy.

## Odoo 18 → 19 Changes

`project_purchase_stock` had no significant behavioral changes between Odoo 18 and 19. The module's logic is stable:
- `_prepare_picking` has always been the injection point for PO-to-picking propagation.
- `_make_po_get_domain` project_id grouping was introduced alongside `project_stock` and `project_purchase` when those modules were first added in earlier versions.
- No new fields or API changes in Odoo 19 for this module.

## Related Modules

| Module | Role |
|---|---|
| [Modules/project_purchase](modules/project_purchase.md) | Adds `project_id` field to `purchase.order`; enables purchase cost tracking in project profitability |
| [Modules/project_stock](modules/project_stock.md) | Adds `project_id` field to `stock.picking`; adds project picking action menus |
| [Modules/purchase_stock](modules/purchase_stock.md) | Manages PO-to-receipt flow; base `_prepare_picking` and buy-rule procurement |
| [Modules/Stock](modules/stock.md) | Core stock module; `stock.rule` base model; `stock.picking` base model |
| [Modules/Purchase](modules/purchase.md) | Core purchase module; `purchase.order` base model |

## Tags

#odoo #odoo19 #project #purchase #stock #procurement #workflow