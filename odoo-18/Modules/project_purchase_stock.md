---
Module: project_purchase_stock
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_purchase_stock #project #purchase #stock
---

## Overview

**Module:** `project_purchase_stock`
**Depends:** `project_purchase`, `project_stock` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_purchase_stock/`
**License:** LGPL-3
**Category:** Hidden
**Purpose:** Technical bridge propagating project context from purchase orders into stock pickings. Ensures purchase orders (which carry `project_id`) generate stock pickings that also reference the project.

---

## Architecture

**No Python model files.** This is a pure dependency bridge.

- `project_purchase` adds `project_id` to `purchase.order` and `purchase.order.line`
- `project_stock` adds `project_id` to `stock.picking` and provides project stock actions
- `project_purchase_stock` chains them so that procurement rules using PO as origin propagate project context to pickings

The module exists to complete the project→PO→picking chain when all three modules are present. No `models/` directory.

---

## Security / Data

No `ir.model.access.csv`. No data XML files. No Python files beyond empty `__init__.py`.

---

## Critical Notes

- **Pure technical bridge** — no ORM behavior.
- Auto-installed when `project_purchase` and `project_stock` are both present.
- v17→v18: No breaking changes.