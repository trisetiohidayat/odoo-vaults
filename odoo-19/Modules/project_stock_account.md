---
tags: [#odoo, #odoo19, #modules, #project, #stock, #analytic, #profitability]
description: Bridge module that routes stock picking valuation costs into project profitability panels, introducing a dedicated Materials cost line driven by analytic account distribution on pickings linked to projects.
---

# project_stock_account

> **aka**: "Project Stock Account" | **category**: Services/Project
> **depends**: `stock_account`, `project_stock`
> **auto_install**: `True` | **license**: LGPL-3

**Category:** Services/Project
**Depends:** `stock_account`, `project_stock`
**Auto-install:** `True`
**License:** LGPL-3
**Author:** Odoo S.A.

---

## L1: Project-Stock Accounting Business Context

### Why This Module Exists

In a project-based services company, a project may consume **materials** — physical products that are ordered, received, or shipped as part of project delivery. These material costs must be tracked against the project's analytic account so that:

1. The project manager sees the **true cost** of the project in the profitability panel
2. Finance can reconcile **stock valuation** (what was consumed) with **analytic cost lines** (what was charged to the project)
3. Cost reports can be broken down by: labor, materials, vendor bills, and manufacturing

**`project_stock_account`** closes the loop between `stock_account` (stock valuation with analytic lines) and `project` (profitability reporting). It introduces a new concept: when a `stock.picking` is linked to a `project.project`, and the picking type has `analytic_costs` enabled, the picking's moves generate `account.analytic.line` entries that feed into the **Materials** section of the project's profitability panel.

### Core Concept: `analytic_costs` Flag

The `analytic_costs` boolean on `stock.picking.type` is the master switch. When enabled:
- Every stock move in a picking of that type generates **analytic lines** at validation
- The analytic distribution comes from the **project**, not the product
- The analytic lines carry `category = 'picking_entry'` (vs. other categories like `'manufacturing_order'`)
- These lines appear as **"Materials"** costs in the project profitability panel

### L1 Cost Flow

```
Receipt (incoming) ─────────────────────────────────────────────┐
   move: qty=10, price=12.00 (standard_price)                  │
   analytic line: amount = +120.00  (positive = asset received)  │
                                                                    │
Delivery (outgoing) ────────────────────────────────────────────┤
   move: qty=5, price=12.00 (standard_price)                    │
   analytic line: amount = -60.00  (negative = cost incurred)      │
                                                                    │
Both → project._get_profitability_items()
         → "Materials" section: billed = -60 + 120 = +60.00 net
```

> **Note**: Receipts increase inventory (positive amount in analytic), deliveries decrease inventory (negative amount). The profitability panel shows **net** cost impact. For most project scenarios, only outgoing deliveries are relevant.

### Analytic Applicability: Mandatory Plans

`sale_project_stock` (and `project_stock_account` indirectly) support Odoo's **analytic applicability** system. Administrators can register an `account.analytic.applicability` rule for `business_domain='stock_picking'` that marks a specific analytic plan as **mandatory**. If a picking is validated against a project that lacks the required plan account, the validation is **blocked** with a `ValidationError`.

---

## L2: Field Types, Defaults, Constraints

### Field: `stock.picking.type.analytic_costs`

**File:** `models/stock_picking_type.py`

```python
analytic_costs = fields.Boolean(
    help="Validating stock pickings will generate analytic entries "
         "for the selected project. Products set for re-invoicing "
         "will also be billed to the customer."
)
```

| Property | Value |
|---|---|
| Type | `Boolean` |
| Store | No (non-stored computed default) |
| Default | `False` |
| Required | No |
| Groups | `analytic.group_analytic_accounting` |
| UI Visibility | Only for `picking_type.code in ('incoming', 'outgoing')` |

**UI Context:** The field is **invisible** for `internal` transfer picking types. It only appears on Receipts and Delivery Orders.

### Field: `account.analytic.line.category`

**File:** `models/account_analytic_line.py`

```python
category = fields.Selection(
    selection_add=[('picking_entry', 'Inventory Transfer')]
)
```

Extends the `account.analytic.line.category` selection (which already has `'manufacturing_order'` from `mrp_account`). This is a **stateless discriminator** — it does not affect permissions, it only enables filtering in profitability queries.

### Field: `account.analytic.applicability.business_domain`

**File:** `models/analytic_applicability.py`

```python
business_domain = fields.Selection(
    selection_add=[
        ('stock_picking', 'Stock Picking'),
    ],
    ondelete={'stock_picking': 'cascade'},
)
```

Extends the applicability system's business domain list. `ondelete='cascade'` ensures that when a plan is deleted, its applicability rules for `stock_picking` are also deleted.

### L2 Defaults Summary

| Field | Model | Default | Set by |
|---|---|---|---|
| `analytic_costs` | `stock.picking.type` | `False` | Not set; user must enable manually |
| `category` | `account.analytic.line` | No default (added to selection) | Set in `_prepare_analytic_line_values` |
| `project_id` | `stock.picking` | `False` | `project_stock` module; or manually |
| `project.account_id` | `project.project` | `False` | `project_account` or `account_analytic_default` |

### L2 Constraints

`sale_project_stock` does not define `@api.constrains` or `_sql_constraints`. The only hard constraint is runtime:

```python
# stock_move.py — in _prepare_analytic_lines()
mandatory_plans = project._get_mandatory_plans(self.company_id, business_domain='stock_picking')
missing_plan_names = [plan['name'] for plan in mandatory_plans if not project[plan['column_name']]]
if missing_plan_names:
    raise ValidationError(_(
        "'%(missing_plan_names)s' analytic plan(s) required on the project '%(project_name)s' ..."
    ))
```

This is a **ValidationError** raised at picking `button_validate()` time. It blocks validation until all mandatory plans are configured on the project.

### Profitability Items Field Structure

The profitability panel's `costs` section uses this structure:

```python
costs = [{
    'id': 'other_costs',          # Section identifier
    'sequence': 12,                # Display order
    'billed': total_costs,        # Net amount (negative for costs)
    'to_bill': 0.0,               # Always 0 for picking entries
    'action': {                   # Only if user has account.readonly
        'type': 'object',
        'name': 'action_profitability_items',
        'args': '["other_costs_aal", ...]'  # Routes to AAL list
    }
}]
```

---

## L3: Cross-Module Architecture

### Cross-Module Dependency Graph

```
                        ┌──────────────────────────┐
                        │     project_stock_account │
                        │     (THIS MODULE)         │
                        └──────────────┬───────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
     ┌─────────────────┐     ┌──────────────────┐    ┌──────────────────┐
     │  stock_account  │     │   project_stock  │    │     analytic     │
     │ (base analytic  │     │  (stock.picking. │    │(account.analytic │
     │  line gen on    │     │   project_id)    │    │  .applicability)│
     │  stock moves)   │     └────────┬─────────┘    └────────┬─────────┘
     └────────┬────────┘              │                       │
              │                        │                       │
              │              ┌─────────▼─────────┐             │
              │              │   stock.picking    │             │
              │              │   (project_id +    │             │
              │              │    analytic_costs)  │             │
              │              └─────────┬─────────┘             │
              │                        │                       │
              │              ┌─────────▼─────────┐             │
              │              │    stock.move      │             │
              │              │ (_prepare_analytic_  │             │
              │              │  lines override)     │             │
              │              └─────────┬─────────┘             │
              │                        │                       │
              └────────────────────────┼───────────────────────┘
                                       │
                              ┌────────▼──────────┐
                              │ account.analytic.   │
                              │ line (category =   │
                              │ 'picking_entry')   │
                              └────────┬──────────┘
                                       │
                              ┌────────▼──────────┐
                              │ project.profitability│
                              │ panel: "Materials"   │
                              └─────────────────────┘
```

### Cross-Module Method Call Chain

When `stock.picking.button_validate()` is called:

```
button_validate()
  └─→ stock_move._action_done()  (parent of stock.picking)
        └─→ stock_move._prepare_analytic_lines()
              ├─→ project_stock_account._get_valid_moves_domain()
              │     Returns: ['&', ('picking_id.project_id', '!=', False),
              │                   ('picking_type_id.analytic_costs', '!=', False)]
              │     → Filters which moves generate analytic lines
              │
              ├─→ project_stock_account._get_analytic_distribution()
              │     If analytic_costs=True:
              │       distribution = project_id._get_analytic_distribution()
              │     Else:
              │       returns super() (product-level defaults)
              │
              ├─→ project_stock_account._prepare_analytic_line_values()
              │     Adds: name = picking_id.name
              │     Adds: category = 'picking_entry'
              │
              ├─→ project_stock_account._prepare_analytic_lines()
              │     Mandatory plan validation:
              │       mandatory_plans = project._get_mandatory_plans(
              │         company_id, business_domain='stock_picking')
              │       → ValidationError if any plan missing
              │
              └─→ stock_account creates account.analytic.line records
```

When the project profitability panel is opened:

```
project_project.get_panel_data()
  └─→ project_project._get_profitability_items()
        ├─→ super() → project_account._get_profitability_items()
        │     (includes service costs, other_costs_aal, etc.)
        │
        └─→ project_stock_account._get_items_from_aal_picking()
              domain = (
                _get_domain_aal_with_no_move_line()  # account_id=project.account_id, no AML link
                & [('category', '=', 'picking_entry')]
              )
              → search_read: id, amount, currency_id
              → Group by currency, convert to project currency
              → Returns: [{'id': 'other_costs', 'sequence': 12,
                           'billed': total, 'to_bill': 0.0}]
              → Appended to profitability_items['costs']['data']
```

### Override Pattern Analysis

`sale_project_stock` uses three types of overrides:

| Type | Methods | Notes |
|---|---|---|
| **Domain replacement** | `_get_valid_moves_domain()` | Replaces parent domain entirely, not AND'd |
| **Conditional delegation** | `_get_analytic_distribution()` | Delegates to project; falls back to super if no project distribution |
| **Post-process extension** | `_prepare_analytic_line_values()` | Modifies parent dict in-place, returns modified dict |
| **Post-process validation** | `_prepare_analytic_lines()` | Runs mandatory plan check after parent creates AAL dicts |
| **Dict merge** | `_get_profitability_items()`, `_get_picking_action()` | Merges into parent dict's lists/dicts |

### Workflow Triggers

| Trigger | Event | Result |
|---|---|---|
| Picking type configured | Admin enables `analytic_costs` on picking type | All future pickings of this type eligible for analytic lines |
| Project configured | Analytic account set on project | Distribution available for analytic line generation |
| Picking validated | `button_validate()` on picking with `analytic_costs=True` + project set | Analytic lines created with `category='picking_entry'` |
| Picking validated | `button_validate()` on picking with missing mandatory plans | `ValidationError` blocks validation |
| Profitability panel opened | `get_panel_data()` on project | "Materials" section shows summed picking costs |

---

## L4: Odoo 18 → Odoo 19 Changes

### Module Status: Net-New in Odoo 19

`project_stock_account` is a **net-new Odoo 19 module**. There is no equivalent module in Odoo 18. The concept of routing stock picking valuation costs into a project's profitability panel did not exist as a coherent module.

Prior Odoo versions had:
- `stock_account`: Stock moves generate analytic lines based on product-level `analytic_distribution`
- `project_account`: Project profitability with revenue, service costs, vendor bills
- `project_stock`: `project_id` field on `stock.picking` (added Odoo 17)

But the **bridge** — picking type `analytic_costs` flag, picking-entry analytic category, Materials row in profitability, and mandatory plan enforcement — did not exist.

### Odoo 18 → 19: New Capabilities

| Capability | Odoo 18 State | Odoo 19 (`project_stock_account`) |
|---|---|---|
| `analytic_costs` on picking type | Not available | New boolean field on `stock.picking.type` |
| Business domain for applicability | Only `purchase`, `sale`, `lease` | New `'stock_picking'` domain |
| `category='picking_entry'` on AAL | Not available | `'Inventory Transfer'` option on `account.analytic.line.category` |
| Project-linked analytic distribution | Product-level defaults only | Delegated to `project_id._get_analytic_distribution()` |
| "Materials" row in profitability | Not available | `other_costs` at sequence 12 in profitability panel |
| Mandatory analytic plan enforcement | Not available | `ValidationError` on picking validate if missing |
| Receipt picking costs | Not tracked at project level | Positive amounts for receipts (incoming) |
| Delivery picking costs | Tracked via `cost_of_goods_sold` (invoice side) | Negative amounts for deliveries (via analytic lines) |

### Distinction: `cost_of_goods_sold` vs `Materials`

Two cost types appear in the project profitability panel:

| Section | ID | Source | Trigger | Sign |
|---|---|---|---|---|
| **Cost of Goods Sold** | `cost_of_goods_sold` | `sale_project._get_items_from_invoices()` | Vendor bill posted with project analytic distribution | Negative (cost) |
| **Materials** | `other_costs` | `project_stock_account._get_items_from_aal_picking()` | Picking validated with `analytic_costs=True` | Negative (delivery) / Positive (receipt) |

The two are **intentionally separate**:
- `cost_of_goods_sold`: From invoice/purchase side (what you paid the vendor)
- `Materials`: From stock valuation side (what left/enters inventory)

In an Anglo-Saxon environment with auto-valuated products, the same product movement may generate both a COGS journal entry and an analytic line. The separation in the profitability panel ensures both are visible and auditable.

### Sequence Order in Profitability Panel

```
Sequence 1-10:  Revenue sections (service, materials, downpayments, etc.)
Sequence 11:    Vendor Bills (project_account: other_purchase_costs)
Sequence 12:    Materials (project_stock_account: other_costs)  ← NEW
Sequence 13-14: Reserved for future use
Sequence 15:    Other Costs AAL (project_account: other_costs_aal) — excludes picking_entry
```

### API Stability Notes

Since this is a new module in Odoo 19, no deprecation history exists. However, the following are extension points that custom modules may override:

- `_get_valid_moves_domain()` — filter which moves generate analytic lines
- `_get_analytic_distribution()` — change how distribution is resolved
- `_prepare_analytic_line_values()` — add/modify fields on the AAL dict
- `_prepare_analytic_lines()` — add validation logic before AAL creation
- `_get_items_from_aal_picking()` — change how picking costs appear in profitability
- `_get_profitability_labels()` — change the "Materials" label

### Internal Odoo 19 Revisions

The test `test_analytics.py` is decorated with `@skip('Temporary to fast merge new valuation')`, indicating the module was under active development during the Odoo 19 release cycle and the test suite was temporarily disabled for CI purposes. The tests themselves remain valid and cover the expected behavior.

---

## Files Reference

```
addons/project_stock_account/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── analytic_applicability.py     # business_domain += 'stock_picking'
│   ├── stock_move.py                 # _get_analytic_distribution,
│   │                                   # _prepare_analytic_line_values,
│   │                                   # _get_valid_moves_domain,
│   │                                   # _prepare_analytic_lines
│   ├── stock_picking_type.py         # analytic_costs boolean field
│   ├── project_project.py            # profitability: Materials row (other_costs)
│   └── account_analytic_line.py     # category += 'picking_entry'
├── views/
│   └── stock_picking_type_views.xml  # analytic_costs field in picking type form
└── tests/
    └── test_analytics.py             # delivery/receipt/mandatory-plan tests (skipped)
```

---

## Related Modules

| Module | Role |
|---|---|
| [[Modules/project_stock]] | Adds `project_id` to `stock.picking`; action buttons on project form |
| [[Modules/stock_account]] | Core stock valuation; `_prepare_analytic_lines`, `_get_analytic_distribution` on `stock.move` |
| [[Modules/project_account]] | Base project profitability; `other_costs_aal` row; `_get_items_from_aal`; `_get_action_for_profitability_section` |
| [[Modules/analytic]] | `account.analytic.applicability`, `account.analytic.line` |
| [[Modules/account_analytic]] | Provides `_get_analytic_distribution` on `project.project` |
| [[Modules/sale_project]] | SO → project linkage; `reinvoiced_sale_order_id`; project profitability integration |
| [[Modules/sale_project_stock]] | Wires `stock.picking.project_id`; auto-creates SOLs on picking validate |
