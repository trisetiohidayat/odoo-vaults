---
tags:
  - odoo
  - odoo19
  - modules
  - mrp
  - stock
  - landed_costs
  - subcontracting
---

# MRP Subcontracting Landed Costs

## Overview

| Property | Value |
|----------|-------|
| **Module** | `mrp_subcontracting_landed_costs` |
| **Edition** | Community Edition |
| **Category** | Supply Chain / Manufacturing |
| **Summary** | View improvements to identify subcontracting orders when applying landed costs |
| **Version** | `19.0.1.0.0` (manifest: `1.0`) |
| **Depends** | `stock_landed_costs`, `mrp_subcontracting` |
| **Auto-install** | `True` — installs automatically when both dependencies are present |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## L1 — How Landed Costs Apply to Subcontracting

### Background: What Are Landed Costs?

Landed costs (`stock.landed.cost`) represent extra charges incurred when receiving goods — freight, insurance, customs duties, handling fees, etc. In Odoo, they are applied to stock pickings (receipts) to distribute these extra costs onto the product valuation.

### The Subcontracting Problem

When a company uses **subcontracting** (`mrp_subcontracting`), the subcontractor is an external vendor who manufactures products on behalf of the company. The flow is:

```
Company (Owner)
  └── Send raw materials to subcontractor  (subcontracting Receipt in)
  └── Subcontractor performs work
  └── Receive finished goods from subcontractor  (subcontracting Delivery out)
```

The receipt of finished goods from the subcontractor creates a **stock picking** (type: `subcontracting` reception). To properly value the finished product, the company needs to add **landed costs** (subcontractor's processing fee, shipping, etc.) to the receipt.

**The problem**: In the standard `stock.landed.cost` form, the **Pickings** field (`picking_ids`) shows all pickings indiscriminately. When there are many pickings, finding the subcontracting-related receipts is difficult. The `mrp_subcontracting_landed_costs` module solves this by:

1. **Pre-filtering** the picking selection to show only pickings with subcontracting moves
2. **Showing the associated subcontracting production order** (`mrp_production`) as a dedicated, searchable field

## L2 — Field Types, Defaults, Constraints

This is a **zero-model, view-only extension module** — no Python models, no custom fields. All changes are pure XML view inheritance on `stock.landed.cost`.

### Extended Model: `stock.landed.cost`

The module modifies two fields on the base `stock.landed.cost` model (from `stock_landed_costs`):

| Field | Type | Original Behavior | Modified Behavior |
|-------|------|-----------------|-------------------|
| `mrp_production_ids` | `many2many` (`mrp.production`) | Not present in base `stock_landed_costs` form | Added via `mrp_landed_costs` module with search/list view refs |
| `picking_ids` | `many2many` (`stock.picking`) | All company pickings shown | Domain applied: only subcontracting pickings |

#### `mrp_production_ids` Field (Added by `mrp_landed_costs`)

From `mrp_landed_costs/views/stock_landed_costs_views.xml`, this field is added to the landed cost form with:
- `widget="many2many_tags"` — displays linked production orders as tags
- `invisible="target_model != 'manufacturing'"` — only visible when the landed cost targets manufacturing
- `domain="[('company_id', '=', company_id), ('move_finished_ids.is_in', '!=', False)]"` — only manufacturing orders with finished goods receipts
- `readonly="state == 'done'"` — cannot change once the cost is validated

#### `picking_ids` Domain Filter (Modified by `mrp_subcontracting_landed_costs`)

The `picking_ids` field is modified to apply this domain:

```python
domain="[('company_id', '=', company_id),
         '|', '|',
             ('move_ids.is_in', '!=', False),
             ('move_ids.is_out', '!=', False),
         '&',
             ('move_ids.is_subcontract', '!=', False),
             ('move_ids.state', '=', 'done')]"
```

Breaking this down:

```python
# OR group: pickings with inbound moves OR outbound moves
#   OR: ('move_ids.is_in', '!=', False)      → pickings with incoming moves
#   OR: ('move_ids.is_out', '!=', False)    → pickings with outgoing moves
#   OR: ('move_ids.is_subcontract', '!=', False) AND ('move_ids.state', '=', 'done')
#                                                       → subcontracting moves that are done
```

This ensures:
- **Subcontracting receipts** (`is_in=True`, `is_subcontract=True`) appear
- **Subcontracting deliveries** (`is_out=True`, `is_subcontract=True`) appear  
- **Done state check** on the subcontracting moves ensures only completed subcontracting operations are shown
- Regular inbound/outbound pickings (non-subcontracting) are also included via the first two OR conditions

### `mrp_production_ids` Context (Added by `mrp_subcontracting_landed_costs`)

```python
context="{'search_view_ref': 'mrp_subcontracting.mrp_production_subcontracting_filter',
          'list_view_ref': 'mrp_subcontracting.mrp_production_subcontracting_tree_view'}"
```

When the user opens the MRP production selector for `mrp_production_ids`, the module forces the search and list views to use the **subcontracting-specific views** from `mrp_subcontracting`:
- `mrp_production_subcontracting_filter` — filters to show only subcontracting manufacturing orders
- `mrp_production_subcontracting_tree_view` — shows the subcontracting-optimized list columns

### Base View Inheritance Chain

```
stock_landed_costs/view_stock_landed_cost_form
    ↑ inherits
mrp_landed_costs/view_mrp_landed_costs_form  (adds mrp_production_ids field)
    ↑ inherits
mrp_subcontracting_landed_costs/view_mrp_landed_costs_form  (modifies picking_ids domain + mrp_production_ids context)
```

### No SQL Constraints

This module introduces no new models and therefore no SQL constraints.

## L3 — Cross-Module, Override Pattern, Workflow Trigger

### Cross-Module Dependency Chain

```
mrp_subcontracting_landed_costs
├── stock_landed_costs          (provides stock.landed.cost model + base form)
│   ├── stock_account           (valuation integration)
│   └── purchase_stock          (PO→receipt integration)
└── mrp_subcontracting          (provides subcontracting models + views)
    └── mrp                     (manufacturing core)
        ├── stock
        └── mrp_workorder
```

And also depends on `mrp_landed_costs` indirectly through the inheritance chain:
```
mrp_landed_costs
├── stock_landed_costs
└── mrp
```

### Override Pattern: XML View Inheritance

This module uses the **XML view inheritance** pattern (`<field ... position="attributes">`):

```xml
<record id='view_mrp_landed_costs_form' model='ir.ui.view'>
    <field name="inherit_id" ref="mrp_landed_costs.view_mrp_landed_costs_form"/>
    <field name="arch" type="xml">
        <!-- Modify mrp_production_ids field: add context attribute -->
        <field name="mrp_production_ids" position="attributes">
            <attribute name="context">{'search_view_ref': ...,
                                      'list_view_ref': ...}</attribute>
        </field>
        <!-- Modify picking_ids field: replace domain attribute -->
        <field name="picking_ids" position="attributes">
            <attribute name="domain">[...subcontracting domain...]</attribute>
        </field>
    </field>
</record>
```

This is a **pure view-level change** — no Python model overrides. The module modifies the presentation of existing data, not the data model itself.

### Workflow Trigger

There is no workflow defined in this module. Its trigger is purely **UI-contextual**:

1. User opens a `stock.landed.cost` record (form view)
2. User clicks the `picking_ids` field's selection widget → picking search dialog opens with the subcontracting domain pre-applied
3. User clicks the `mrp_production_ids` field's selection widget → MRP production search dialog opens using the subcontracting-specific search/list views

### Extension Points

| Extension Point | How to Extend |
|----------------|---------------|
| Add more pickings to domain | Modify the `domain` attribute on `picking_ids` — add additional `('move_ids.X', '=', value)` conditions |
| Change production view | Modify the `context` on `mrp_production_ids` to point to different `search_view_ref` or `list_view_ref` |
| Add a new field to the landed cost form | Add a `<field>` entry inside the `<form>` arch, after inheriting from a broader base view |

## L4 — Version Change: Odoo 18 to 19

### Changes Identified

#### Module Name / Version

| | Odoo 18 | Odoo 19 |
|--|---------|---------|
| Manifest version | Likely `1.0` | `1.0` |
| Module name | `mrp_subcontracting_landed_costs` | Same |

No version bump occurred — the module's scope and implementation appear identical between Odoo 18 and 19.

#### Inheritance Chain Stability

The inheritance chain is stable:
- `stock_landed_costs → view_stock_landed_cost_form` — unchanged in Odoo 19
- `mrp_landed_costs → view_mrp_landed_costs_form` — unchanged in Odoo 19
- `mrp_subcontracting_landed_costs` inherits from `mrp_landed_costs.view_mrp_landed_costs_form` — unchanged

The external IDs used in the inheritance are all stable Odoo APIs:
- `stock_landed_costs.view_stock_landed_cost_form`
- `mrp_landed_costs.view_mrp_landed_costs_form`
- `mrp_subcontracting.mrp_production_subcontracting_filter`
- `mrp_subcontracting.mrp_production_subcontracting_tree_view`

#### `is_subcontract` Field Stability

The `move_ids.is_subcontract` field (used in the domain filter) is a stable field on `stock.move` introduced by `mrp_subcontracting` in Odoo 15+ and has not changed in Odoo 19.

#### Domain Logic Review

The domain applied to `picking_ids` in Odoo 19:

```python
[('company_id', '=', company_id),
 '|', '|',
     ('move_ids.is_in', '!=', False),
     ('move_ids.is_out', '!=', False),
 '&',
     ('move_ids.is_subcontract', '!=', False),
     ('move_ids.state', '=', 'done')]
```

**Interpretation**: This is a union of three conditions:
1. Any picking with at least one inbound move (company pickings)
2. Any picking with at least one outbound move
3. Any picking with a done subcontracting move

The domain is logically sound for Odoo 19's stock move state machine.

#### Migration Notes

- **No data migration needed** — pure view module, no persistent data.
- **No Python changes needed** — the module has no Python code.
- **Verify view inheritance** when upgrading: if `mrp_landed_costs` or `stock_landed_costs` views change significantly, the domain and context attributes may need adjustment.
- The module's `auto_install: True` combined with its two hard dependencies (`stock_landed_costs` and `mrp_subcontracting`) means it is automatically installed whenever both dependencies are present — this behavior is unchanged from Odoo 18.

## Related

- [Modules/stock_landed_costs](stock_landed_costs.md) — Base landed costs module (`stock.landed.cost` model)
- [Modules/mrp_subcontracting](mrp_subcontracting.md) — Subcontracting manufacturing orders and pickings
- [Modules/mrp_landed_costs](mrp_landed_costs.md) — MRP-specific landed cost views (adds `mrp_production_ids` field)
- [Modules/stock_account](stock_account.md) — Valuation and landed cost accounting integration
