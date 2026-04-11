---
Module: hr_org_chart
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_org_chart
---

## Overview
HR Org Chart. Adds an organizational chart widget to the employee form showing N+1 (manager), N+2, ..., direct subordinates, and indirect subordinates. Exposes a JSON controller endpoint consumed by the JS org chart component. Auto-installed with `hr`.

## Models

### hr.employee.base (Extension)
Inherits from: `hr.employee.base`
File: `~/odoo/odoo18/odoo/addons/hr_org_chart/models/hr_org_chart_mixin.py`

| Field | Type | Description |
|-------|------|-------------|
| child_all_count | Integer | `compute='_compute_subordinates'`, `recursive=True`, `compute_sudo=True`. Total indirect subordinates count |
| department_color | Integer | Related from `department_id.color` |
| child_count | Integer | `compute='_compute_child_count'`, `recursive=True`, `compute_sudo=True`. Direct subordinates count |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_subordinates | self, parents=None | recordset | Recursive helper: returns all subordinates (direct + indirect), excluding `parents`. Handles recursive hierarchy (CEO managed by CTO who is also managed by CEO) |
| _compute_subordinates | self | None | Sets both `subordinate_ids` and `child_all_count` via `_get_subordinates` |
| _compute_is_subordinate | self | None | `search='_search_is_subordinate'`: True if current user is in employee's subordinate tree |
| _search_is_subordinate | operator, value | domain | Supports `=` and `!=` on `is_subordinate`; uses double negation pattern |
| _compute_child_count | self | None | Uses `_read_group` to count children per parent in one query |

### hr.employee (Extension)
Inherits from: `["hr.employee"]` (list form — prototype inheritance)
File: `~/odoo/odoo18/odoo/addons/hr_org_chart/models/hr_employee.py`

| Field | Type | Description |
|-------|------|-------------|
| subordinate_ids | One2many(hr.employee) | Direct + indirect subordinates; `compute='_compute_subordinates'`, `compute_sudo=True` |
| is_subordinate | Boolean | `compute="_compute_is_subordinate"`, `search="_search_is_subordinate"` |

### hr.employee.public (Extension)
Inherits from: `["hr.employee.public"]` (prototype inheritance)
File: `~/odoo/odoo18/odoo/addons/hr_org_chart/models/hr_employee.py`

| Field | Type | Description |
|-------|------|-------------|
| subordinate_ids | One2many(hr.employee.public) | Same as above, for public employee view |
| is_subordinate | Boolean | Same as above |

## Controllers

### hr_org_chart (HTTP Controller)
File: `~/odoo/odoo18/odoo/addons/hr_org_chart/controllers/hr_org_chart.py`

| Route | Type | Auth | Description |
|-------|------|------|-------------|
| /hr/get_redirect_model | JSON | user | Returns `'hr.employee'` if user has read access, else `'hr.employee.public'` |
| /hr/get_org_chart | JSON | user | Returns managers (N+1..N+5), self, and direct children for an employee |
| /hr/get_subordinates | JSON | user | Returns subordinate IDs filtered by `subordinates_type`: direct/indirect/all |

**`get_org_chart` Logic:**
- Walks up the manager chain from `employee_id` to root (max_level=6)
- Uses `child_ids` from the employee record (direct reports)
- `_managers_level = 5` — shows up to 5 levels of management
- `new_parent_id` context param allows showing a virtual org position (e.g., during drag-drop)

**`get_subordinates` Logic:**
- `direct`: `employee.child_ids - employee`
- `indirect`: `employee.subordinate_ids - employee.child_ids`
- `None/other`: all `subordinate_ids`

## Critical Notes
- **`subordinate_ids` on `hr.employee` and `hr.employee.public`:** Both are computed from `_get_subordinates()` which walks the `parent_id` hierarchy recursively
- **Recursive protection:** The `_get_subordinates` method handles circular manager relationships gracefully (CEO managed by CTO managed by CEO)
- **`_compute_child_count`:** Uses `_read_group` (single query) instead of `search_count` per employee — critical for performance on large orgs
- **`is_subordinate`:** Supports domain searching `['is_subordinate', '=', True]` — useful for ACLs and UI filters
- **v17→v18:** No breaking changes; same architecture
