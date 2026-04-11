# sale_purchase_project — Sale Purchase Project

**Tags:** #odoo #odoo18 #sale #purchase #project
**Odoo Version:** 18.0
**Module Category:** Sale + Purchase + Project Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_purchase_project` extends `sale_purchase` to propagate project/analytic distribution from sale order lines to generated purchase orders and lines. This ensures that service products purchased from vendors are correctly charged to the correct project/analytic account, enabling project-based cost tracking.

**Technical Name:** `sale_purchase_project`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_purchase_project/`
**Depends:** `sale_purchase`, `sale_project`
**Inherits From:** `sale.order.line`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order_line.py` | `sale.order.line` | Project/analytic distribution propagation |

---

## Models Reference

### `sale.order.line` (models/sale_order_line.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_purchase_service_prepare_line_values()` | Adds `analytic_distribution` from the SOL's project to POL vals |
| `_purchase_service_prepare_order_values()` | Adds `project_id` from the SO to PO vals |

---

## Critical Behaviors

1. **Project on PO**: The PO's `project_id` is set from `sale_order_id.project_id`, making the PO directly visible in the project dashboard.

2. **Analytic on POL**: The SOL's `analytic_distribution` (e.g., 60% Project A, 40% Project B) is copied to the POL, so vendor invoices are charged to the correct analytic accounts.

3. **Combined with `sale_purchase`**: This module only overrides two methods from `sale_purchase`'s `_purchase_service_*` methods to add project/analytic propagation. The core PO generation logic is unchanged.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified.

---

## Notes

- Thin module (2 method overrides) completing the project-cost chain: SOL → PO → analytic line
- Works with `sale_purchase` as the base; this module adds the project dimension
- Useful for professional services firms that purchase subcontractor services charged to client projects
