---
Module: project_mrp_sale
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_mrp_sale #project #mrp #sale
---

## Overview

**Module:** `project_mrp_sale`
**Depends:** `project_mrp`, `sale_mrp`, `sale_project` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_mrp_sale/`
**License:** LGPL-3
**Purpose:** Technical bridge ensuring that when `sale_mrp` (sale order ↔ MO) and `sale_project` (sale order ↔ project) are both installed alongside `project_mrp`, the project link flows through the full sale-to-manufacturing chain without conflicts. No Python models.

---

## Architecture

This module has **no Python model files**. It serves as a dependency aggregator:
- `project_mrp` provides: BoM → project, MO → project, procurement → project propagation
- `sale_mrp` provides: sale order line → MO link
- `sale_project` provides: sale order line → project link
- `project_mrp_sale` chains them: when all three are present, an SO line can generate an MO that inherits the project from the SO line

No `models/` directory; no `__init__.py` with model imports (only the top-level module `__init__.py` which is empty).

---

## Security / Data

No `ir.model.access.csv`. No data XML files. No Python files beyond the empty `__init__.py`.

---

## Critical Notes

- This is a **pure technical bridge** — no ORM behavior.
- Installs automatically when `project_mrp`, `sale_mrp`, and `sale_project` are all present.
- v17→v18: No breaking changes.