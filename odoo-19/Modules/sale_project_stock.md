# sale_project_stock — Project-Stock-SO Tracer

> **aka**: "Sale Project - Sale Stock" | **category**: Sales
> **depends**: `sale_project`, `sale_stock`, `project_stock_account`
> **auto_install**: `True` | **license**: LGPL-3

Links stock picking operations to project profitability by wiring the SO-to-project chain (`sale_project`) with the SO-to-picking chain (`sale_stock`) and the picking-to-analytic-account chain (`project_stock_account`). Without this module, material costs from stock moves do not appear in the project profitability panel.

---

## L1: Project-Stock Business Context

### Why This Module Exists

In a project-based services company, a project may consume **materials** — physical products that are shipped, delivered, or consumed as part of project work. These material costs must flow into the project's profitability report so that the project manager sees a complete picture of actual project cost: labor (timesheets), materials (stock), and third-party costs (vendor bills).

Before Odoo 19, there was no clean path from `stock.picking` → `project.project` → **profitability panel**. Each chain existed independently:
- `sale_project`: SO → project via `project_id` on SO
- `sale_stock`: SO → stock picking via `sale_line_id` on stock moves
- `project_stock`: stock picking → project via `project_id` on picking
- `project_stock_account`: picking → analytic lines → profitability

**`sale_project_stock`** sits atop this stack and does three critical things:

1. **Propagates `project_id` into stock moves and pickings** so that the picking knows which project it belongs to
2. **Creates SOLs automatically on picking validation** for products flagged with `expense_policy in {'cost', 'sales_price'}` — this is the "reinvoice" path
3. **Wires the Transfers button** on the SOL smart-button row so users can see which stock moves relate to each product line

### The Reinvoice Pattern

The core business concept here is **cost reinvoicing**: a company purchases or consumes materials for a project, then re-bills those materials to the customer through the project's linked Sales Order. The flow is:

```
Vendor delivers materials → Receipt picking (linked to project) → Validated
Customer invoiced for materials → Delivery picking → Validated
```

`sale_project_stock` handles the second leg: when a delivery picking is validated, if the project's `reinvoiced_sale_order_id` is set, the module creates SOLs for reinvoicable products on that SO.

### L1 Data Flow Diagram

```
┌─────────────┐    project_id     ┌──────────────────┐   reinvoiced_   ┌────────────────┐
│ sale.order  │ ────────────────→ │  project.project │ ←── sale_order_id─── │ sale.order    │
│ (confirmed) │  sale_project      │                  │                 │ (billing SO)   │
└──────┬──────┘                   └────────┬─────────┘                 └──────▲─────────┘
       │                                     │                                  │
       │ sale_line_id                       │ project_id                       │
       ▼                                     │ (sale_project_stock wires it)     │ SOLs created
┌──────────────┐                      ┌──────▼──────────┐                        │
│sale.order   │                      │ stock.picking   │ ──────────────────────────┘
│.line        │                      │ (analytic_costs) │
└──────┬──────┘                      └──────┬──────────┘
       │                                     │
       │ sale_line_id                       │ _prepare_analytic_lines
       ▼                                     ▼
┌──────────────┐                   ┌─────────────────────┐
│ stock.move   │ ─────────────────→ │ account.analytic.line│
│ (linked to   │   analytic_costs   │ (category=          │
│  sale_line)  │   + project_id     │  'picking_entry')    │
└──────────────┘                   └──────────┬──────────┘
                                               │
                                               │ flows into
                                               ▼
                                    ┌─────────────────────┐
                                    │ project profitability│
                                    │ panel: "Materials"   │
                                    └─────────────────────┘
```

---

## L2: Field Types, Defaults, Constraints

### No New Fields Defined by `sale_project_stock`

`sale_project_stock` does **not** define any new `fields.*` on its own models. It extends existing models' methods and overrides pickings' `button_validate()`. All field-level details come from the modules it depends on.

### Field Resolution Chain (Critical Fields)

The reinvoice and traceability flows depend entirely on these fields existing and being populated:

| Field | Model | Source | Default | Constraint |
|---|---|---|---|---|
| `stock.picking.project_id` | `stock.picking` | `project_stock` module | `False` | Must be set for reinvoice |
| `stock.picking.type.analytic_costs` | `stock.picking.type` | `project_stock_account` | `False` | Must be `True` to generate analytic lines and trigger reinvoice |
| `project.project.reinvoiced_sale_order_id` | `project.project` | `sale_project` module | `False` | Must be set to trigger SOL auto-creation |
| `product.product.expense_policy` | `product.product` | `sale` module | `False` | Must be `'cost'` or `'sales_price'` for reinvoice |
| `stock.move.quantity` | `stock.move` | Set at validate time | `0.0` | Zero qty → price `0.0` in reinvoice |
| `stock.move.product_uom_qty` | `stock.move` | From original SOL | — | Used for `product_uom_qty` on new SOL |
| `sale.order.state` | `sale.order` | `sale` module | `'draft'` | Must be `'sale'` (confirmed) for reinvoice |

### Field Defaults from Upstream

#### From `project_stock` — `stock.picking.project_id`

```python
# project_stock/models/stock_picking.py
project_id = fields.Many2one('project.project', domain=[('is_template', '=', False)])
```

No default — must be set manually or via the `_get_new_picking_values` / `_assign_picking_values` overrides in `sale_project_stock`.

#### From `sale_stock` — `stock.move.sale_line_id`

```python
# sale_stock/models/stock.py
sale_line_id = fields.Many2one('sale.order.line', 'Sale Line', index='btree_not_null')
```

Set when a stock rule is triggered from an SOL or when `_action_synch_order` matches a move to an existing SOL product.

#### From `project_stock_account` — `stock.picking.type.analytic_costs`

```python
# project_stock_account/models/stock_picking_type.py
analytic_costs = fields.Boolean(
    help="Validating stock pickings will generate analytic entries "
         "for the selected project. Products set for re-invoicing "
         "will also be billed to the customer."
)
```

**Default:** `False`. Must be explicitly enabled on the picking type.

### Constraint Analysis

`sale_project_stock` does not define `@api.constrains` or `_sql_constraints` directly. Constraints are enforced through the `UserError` exceptions in `button_validate()`:

```python
# stock_picking.py — UserError gates in button_validate
if sale_order.state in ('draft', 'sent'):
    raise UserError("The Sales Order ... must be validated before validating the stock picking.")
elif sale_order.state == 'cancel':
    raise UserError("The Sales Order ... is cancelled. You cannot validate a stock picking on a cancelled Sales Order.")
elif sale_order.locked:
    raise UserError("The Sales Order ... is currently locked. Please create a new SO linked to this Project.")
```

These are **runtime validation errors**, not database constraints. They fire at `button_validate()` time.

---

## L3: Cross-Module Architecture

### Cross-Module Dependency Graph

```
                          sale_project
                          (SO → project_id)
                               │
                               ▼
                        ┌─────────────┐
                        │sale_project_ │
                        │stock         │  ← THIS MODULE
                        └──────┬──────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        sale_stock        project_stock_    project_stock_
        (SO → sale_        account           account
         line_id on                    (picking → analytic
         stock.move)                       line → profitability)
              │                │
              ▼                ▼
        stock.move        account.analytic.line
        (sale_line_id,    (category=
         project_id)        'picking_entry')
              │
              ▼
        stock.picking
        (project_id)
```

### Cross-Module Method Call Chain

#### Path 1: Picking Validation → SOL Creation (Reinvoice)

```
stock.picking.button_validate()
  └─→ super() validates the picking first
  └─→ sale_project_stock.button_validate():
        1. Reads picking.project_id
        2. Reads project.sudo().reinvoiced_sale_order_id
        3. Checks picking_type_id.analytic_costs == True
        4. Filters moves: product_id.expense_policy in {'sales_price', 'cost'}
        5. Validates SO state (must be 'sale', not draft/locked/cancel)
        6. For each reinvoicable move:
             a. stock_move._sale_get_invoice_price(sale_order)   ← defined here
             b. stock_move._sale_prepare_sale_line_values(...)  ← defined here
        7. Batch create: sale.order.line.sudo().create(list_of_values)
```

#### Path 2: Project Picking Actions

```
project.project._get_picking_action()
  └─→ super() builds base action dict from project_stock
  └─→ sale_project_stock._get_picking_action():
        Adds default_picking_type_id from user.property_warehouse_id
```

#### Path 3: SOL Smart Button → Transfers

```
sale.order.line._get_action_per_item()
  └─→ super() returns base action per SOL
  └─→ sale_project_stock._get_action_per_item():
        Adds Transfers action for non-service SOLs with stock moves
        (user must be in stock.group_stock_user)
```

### Override Pattern Analysis

`sale_project_stock` uses **extension overrides** throughout — every method calls `super()` and extends or replaces the return value.

| Model | Method | Pattern | Purpose |
|---|---|---|---|
| `stock.move` | `_get_new_picking_values()` | Dict merge | Set `project_id` on new pickings |
| `stock.move` | `_assign_picking_values(picking)` | Dict merge | Set `project_id` on existing pickings |
| `stock.move` | `_prepare_procurement_values()` | Dict extend | Propagate `project_id` to procurement |
| `stock.move` | `_sale_get_invoice_price(order)` | Full override | Determine reinvoice price |
| `stock.move` | `_sale_prepare_sale_line_values(...)` | Full replacement | Build SOL create dict |
| `stock.picking` | `button_validate()` | Pre/Post super | Auto-create SOLs on validate |
| `sale.order.line` | `_get_action_per_item()` | Dict extend | Add Transfers button |
| `project.project` | `_get_picking_action()` | Dict extend | Add warehouse-based picking type |

### Workflow Triggers

| Trigger | Event | Result |
|---|---|---|
| SO confirmed | `sale.order._action_confirm()` | `sale_project` creates project; `sale_stock` creates pickings |
| Pickings assigned | `_assign_picking_values()` | `project_id` written onto picking |
| Picking confirmed | `stock.picking.action_confirm()` | Moves set to reserved |
| Picking validated | `button_validate()` | **Reinvoice logic fires here** if conditions met |
| Picking validated | `stock_account` AAL hook | Analytic lines created with `category='picking_entry'` |
| Analytic lines created | `project_project._get_profitability_items()` | "Materials" row appears in profitability panel |

### Key Extension Points for Customization

1. **`_sale_get_invoice_price`**: Override to change how reinvoice price is determined (e.g., use a different pricing rule)
2. **`button_validate`**: Override to add custom validation before/after SOL creation
3. **`_sale_prepare_sale_line_values`**: Override to add custom SOL fields during reinvoice
4. **`_get_action_per_item`**: Extend to add more action buttons per SOL type

---

## L4: Odoo 18 → Odoo 19 Changes

### Module Status: Net-New in Odoo 19

`sale_project_stock` is a **net-new Odoo 19 module**. There is no equivalent module in Odoo 18. Its functionality — the complete traceability chain from SO → project → picking → profitability — did not exist as a coherent unit in prior versions.

The closest prior-state components were:
- `sale_project` (Odoo 14+): SO → project linkage
- `sale_stock` (Odoo 14+): SO → stock move linkage
- `project_stock` (Odoo 17+): picking → project linkage (added `project_id` field to `stock.picking`)

None of these individually connected to the profitability panel or performed reinvoice SOL auto-creation from pickings.

### Odoo 18 → 19: New Capabilities

| Capability | Odoo 18 State | Odoo 19 (`sale_project_stock`) |
|---|---|---|
| Picking linked to project | `project_stock` added `project_id` field | Propagated automatically via `_get_new_picking_values` |
| Picking linked to reinvoice SO | Not available | Auto-detected from `project.reinvoiced_sale_order_id` |
| SOL auto-created from picking | Manual only | Automatic on `button_validate()` |
| Transfers button on SOL | Not available | Added via `_get_action_per_item` override |
| Material costs in profitability | Manual or via vendor bills | Automatic via `project_stock_account` AAL + category |
| User warehouse picking type defaults | Not available | Added via `_get_picking_action` override |
| Multi-currency reinvoice pricing | Not handled | Proper `_convert()` with SO currency and date |

### Odoo 19.0 Version Entry Points

| Version | Manifest | Key State |
|---|---|---|
| `1.0` | Initial Odoo 19 release | All features as currently coded |

### API Stability Notes for Customization

Since this is a new module in Odoo 19, no API deprecation history exists. However, the following methods are designed as extension hooks and are expected to be stable for override:

- `_sale_get_invoice_price(order)` — core pricing logic, likely override target
- `_sale_prepare_sale_line_values(order, price, last_sequence)` — likely override for custom SOL fields
- `button_validate()` — likely override for pre/post validation logic

The `project_id` propagation methods (`_get_new_picking_values`, `_assign_picking_values`, `_prepare_procurement_values`) are implementation details that upstream modules (`sale_stock`) also call — override with caution.

### Internal Odoo 19 Revisions to Watch

The test `test_sale_project_stock_profitability` references `ValuationReconciliationTestCommon` and tests COGS-based profitability with Anglo-Saxon accounting. This indicates the module was updated mid-Odoo 19 lifecycle to support the **COGS cost section** (`cost_of_goods_sold`) in the profitability panel, separate from the **Materials section** (`other_costs`).

```python
# test asserts cost_of_goods_sold for storable products
panel_data['profitability_items']['costs']['data']  # contains cost_of_goods_sold
# vs.
# _get_items_from_aal_picking adds other_costs (Materials) from picking_entry AALs
```

The two are **separate sections** in the profitability panel:
- `cost_of_goods_sold`: Invoice-level COGS from Anglo-Saxon valuation (auto-valuated products)
- `other_costs` / `Materials`: Stock picking costs from `project_stock_account` analytic lines

---

## Model Reference

### Files in `sale_project_stock`

```
addons/sale_project_stock/
├── __init__.py
├── __manifest__.py          # depends: sale_project, sale_stock, project_stock_account
├── models/
│   ├── __init__.py
│   ├── project_project.py   # _get_picking_action override
│   ├── sale_order_line.py   # _get_action_per_item override
│   ├── stock_move.py        # price, picking values, procurement
│   └── stock_picking.py      # button_validate override
├── views/
│   └── stock_move_views.xml  # Transfers ir.actions.act_window
└── tests/
    ├── __init__.py
    ├── test_reinvoice.py                           # reinvoice flow
    └── test_sale_project_stock_profitability.py    # COGS profitability
```

---

## Related Modules

| Module | Role | Key Dependency |
|---|---|---|
| [Modules/sale_project](odoo-18/Modules/sale_project.md) | SO → project linkage, `reinvoiced_sale_order_id`, `project_id` on SOL | Required |
| [Modules/sale_stock](odoo-18/Modules/sale_stock.md) | SO → stock.move via `sale_line_id`, `_action_synch_order` | Required |
| [Modules/project_stock](odoo-18/Modules/project_stock.md) | `stock.picking.project_id` field, `_get_picking_action` base | Required |
| [Modules/project_stock_account](odoo-18/Modules/project_stock_account.md) | `analytic_costs` flag, picking → analytic line, profitability panel | Required |
| [Modules/Stock](odoo-18/Modules/stock.md) | Core picking and move models | Base |
| [Modules/Project](odoo-18/Modules/project.md) | `project.project` base model | Base |
| [Modules/Sale](odoo-18/Modules/sale.md) | `sale.order`, `sale.order.line` base models | Base |

---

## Test Coverage

### `test_reinvoice.py` — `TestReInvoice`

Full end-to-end reinvoice test:
1. Creates project with `reinvoiced_sale_order_id` pointing to confirmed SO
2. Creates outgoing picking with `analytic_costs=True` type, linked to project
3. Two products: `expense_policy='cost'` (standard_price=100) and `expense_policy='sales_price'` (list_price=500)
4. Confirms and validates picking as stock user
5. Asserts exactly 2 SOLs created
6. Asserts `price_unit` = 100 for cost product, 500 for sales_price product
7. Asserts `qty_delivered = product_uom_qty = moved qty`
8. Asserts `qty_delivered_method = 'stock_move'`

### `test_sale_project_stock_profitability.py` — `TestSaleProjectStockProfitability`

Anglo-Saxon valuation + profitability test:
1. Creates SO with service product + two storable AVCO products
2. Confirms SO → delivery picking auto-created
3. Sets `move.quantity = 10` and validates picking
4. Creates and posts invoice
5. Asserts profitability `costs` section contains `cost_of_goods_sold` entry with `billed=-280.0`
   - (10 units × 12.0) + (10 units × 16.0) = 120 + 160 = 280

---

## Tags

#odoo19 #modules #sale #stock #project #profitability #reinvoice
