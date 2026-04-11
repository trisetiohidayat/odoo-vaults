---
Module: hr_org_chart
Version: Odoo 18
Type: Core
Tags: #hr #org-chart #hierarchy #frontend #widget
Related Modules: hr, web_hierarchy
---

# hr_org_chart — Organization Chart

**Addon Key:** `hr_org_chart`
**Depends:** `hr`, `web_hierarchy`
**Auto-install:** `['hr']` (installed with `hr`)
**Category:** Hidden
**License:** LGPL-3

## Purpose

`hr_org_chart` extends the employee form with an embedded **organization chart widget** and adds a **hierarchy view mode** to the employee kanban/list. It renders the reporting chain (N+1 manager, N+2, etc.) and direct subordinates directly on the employee form, plus exposes the full org hierarchy via a dedicated hierarchy view.

The module has three major components:
1. **Python model extensions** — computed subordinate counts and search for `is_subordinate`
2. **XML view overrides** — embeds the `hr_org_chart` widget on employee forms; adds hierarchy view mode
3. **Web client (OWL/JS)** — the `hr_org_chart` field widget fetches org data via RPC and renders the chart

---

## Models Extended

### `hr.employee.base` — Employee Base (Abstract)

**Inherited from:** `hr.employee.base` (abstract)
**File:** `models/hr_org_chart_mixin.py`

#### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `child_all_count` | `Integer` | **Indirect** subordinates count (all levels below this employee) |
| `department_color` | `Integer` | Related from `department_id.color` |
| `child_count` | `Integer` | **Direct** subordinates count (immediate `child_ids`) |

#### Compute Methods

**`_get_subordinates(parents=None)`**
```python
def _get_subordinates(self, parents=None) -> hr.employee
```
Recursive helper to compute `subordinate_ids`. Handles the case where an employee might also be their own manager (recursive hierarchy, e.g., CEO manages everyone but is also managed by the CTO who reports to the CEO).

Algorithm:
1. Start with `direct_subordinates = self.child_ids - parents`
2. Recurse into each direct subordinate, passing `parents |= self`
3. Return `indirect_subordinates | direct_subordinates`

**`_compute_subordinates()`**
```python
@api.depends('child_ids', 'child_ids.child_all_count')
def _compute_subordinates(self)
```
Sets `subordinate_ids` (defined on the concrete `Employee` model) and `child_all_count` via `_get_subordinates()`.

Uses `recursive=True` — meaning that when `child_ids.child_all_count` changes (any subordinate's indirect count updates), this recomputes.

**`_compute_is_subordinate()`**
```python
@api.depends_context('uid', 'company')
@api.depends('parent_id')
def _compute_is_subordinate(self)
```
Checks if the current employee is in `self.env.user.employee_id.subordinate_ids`. This allows the system to know whether the current user is subordinate to a given employee.

**`_search_is_subordinate(operator, value)`**
```python
def _search_is_subordinate(self, operator, value)
```
Domain search method that supports `is_subordinate` in filter domains. If `value=False` (asking "is NOT a subordinate"), returns `[('id', '!=', current_user.id)]`. Otherwise, returns `[('id', 'in', subordinate_ids)]`.

Only supports `=` and `!=` operators with boolean values.

**`_compute_child_count()`**
```python
def _compute_child_count(self)
```
Uses `_read_group` on `hr.employee` with `parent_id in self.ids` to count children per parent in a single efficient query, then assigns to each employee.

#### `_prepare_employee_data()` (Controller Helper)

Not on the model — defined in the controller (`HrOrgChartController._prepare_employee_data()`). Returns a dict:
```python
dict(
    id=employee.id,
    name=employee.name,
    link='/mail/view?model=%s&res_id=%s' % ('hr.employee.public', employee.id),
    job_id=job.id,
    job_name=job.name or '',
    job_title=employee.job_title or '',
    direct_sub_count=len(employee.child_ids - employee),
    indirect_sub_count=employee.child_all_count,
)
```

---

### `hr.employee` — Employee (Concrete)

**Inherited from:** `hr.employee` (prototype inheritance)
**File:** `models/hr_employee.py`

#### Fields Added

| Field | Type | Notes |
|-------|------|-------|
| `subordinate_ids` | `One2many(hr.employee, ...)` (compute) | Direct + indirect subordinates |
| `is_subordinate` | `Boolean` (compute+search) | Is current user subordinate to this employee |

```python
class Employee(models.Model):
    _inherit = ["hr.employee"]

    subordinate_ids = fields.One2many(
        'hr.employee',
        string='Subordinates',
        compute='_compute_subordinates',
        help="Direct and indirect subordinates",
        compute_sudo=True)

    is_subordinate = fields.Boolean(
        compute="_compute_is_subordinate",
        search="_search_is_subordinate")
```

Also extends `hr.employee.public` with the same fields.

---

## RPC Controller: `hr_org_chart`

**File:** `controllers/hr_org_chart.py`
**Route:** `/hr/get_org_chart` — JSON
**Route:** `/hr/get_subordinates` — JSON
**Route:** `/hr/get_redirect_model` — JSON

### `get_org_chart(employee_id, **kw)`

```python
@http.route('/hr/get_org_chart', type='json', auth='user')
def get_org_chart(self, employee_id, **kw)
```

**Algorithm:**

1. `_check_employee(employee_id)` — verifies the current user has read access to the employee; falls back to `hr.employee.public` if `hr.employee` is not accessible
2. Reads `kw['context']['new_parent_id']` and `kw['context']['max_level']`
3. Walks **up** the hierarchy: starting from `employee`, follows `parent_id` up to `_managers_level` levels, collecting `ancestors`
4. Returns:
   - `self`: current employee data (via `_prepare_employee_data`)
   - `managers`: ancestor list (up to `max_level - 1`)
   - `managers_more`: boolean — true if there are more managers beyond the limit
   - `children`: list of direct children from `employee.child_ids` (excluding self)

**Limits:**
- `_managers_level = 5` (FP = 5)
- `max_level` can be overridden by the frontend to fetch all managers when "more" is clicked

### `get_subordinates(employee_id, subordinates_type=None, **kw)`

```python
@http.route('/hr/get_subordinates', type='json', auth='user')
def get_subordinates(self, employee_id, subordinates_type=None, **kw)
```

Returns employee IDs filtered by type:
- `direct`: `employee.child_ids - employee`
- `indirect`: `employee.subordinate_ids - employee.child_ids`
- `None` (all): `employee.subordinate_ids.ids`

Used by the org chart popover ("See All" → team kanban view).

### `get_redirect_model()`

```python
@http.route('/hr/get_redirect_model', type='json', auth='user')
def get_redirect_model(self)
```

Returns `'hr.employee'` if the current user has read access to `hr.employee`, otherwise `'hr.employee.public'`. Used to determine which model to redirect to when clicking employee avatars.

---

## Web Client: `hr_org_chart` Field Widget

**File:** `static/src/fields/hr_org_chart.js`

**Type:** OWL Component registered as `web.fields/hr_org_chart`
**Template:** `hr_org_chart.hr_org_chart` (QWeb XML in `static/src/fields/hr_org_chart.xml`)

### Component: `HrOrgChart`

**State:**
```javascript
state.employee_id    // current employee record ID
lastParent           // previous parent_id (to re-fetch when manager changes)
max_level            // current max manager depth
view_employee_id     // last fetched employee ID (used in diff check)
```

**`fetchEmployeeData(employeeId, force = false)`**

1. Calls `/hr/get_org_chart` via `rpc()` with:
   ```javascript
   { employee_id, context: { ...user.context, max_level, new_parent_id: lastParent } }
   ```
2. Stores `managers`, `children`, `self`, `managers_more` on component
3. Calls `render(true)` to re-render

Uses `useRecordObserver` to watch for `parent_id` and `employee_id` changes on the parent record. When `lastParent !== newParentId` or `employee_id` changes, it refetches.

**Display limits in template:**
- Shows up to **19 subordinates** (`emp_count < 20` condition in template)
- If `children.length + managers.length > 19`: shows "See All" button → triggers `_onEmployeeSubRedirect`
- Manager priority over subordinates when space is limited (7-person maximum: 1 self + up to 6 people)

### Popover: `HrOrgChartPopover`

**Template:** `hr_org_chart.hrorgchart_emp_popover`
Triggered by clicking the indirect-subordinate badge (blue pill with count).

Shows a table with:
- Direct subordinates count (clickable)
- Indirect subordinates count (clickable)
- Total subordinates (clickable)

Each row links to `onEmployeeSubRedirect` with `data-type='direct'/'indirect'/'total'`.

---

## Views Added

### Hierarchy View (XML)

**`hr_employee_hierarchy` view** — uses `web_hierarchy` JS widget (`js_class="hr_employee_hierarchy"`):

```xml
<hierarchy child_field="child_ids" js_class="hr_employee_hierarchy" icon="fa-users" draggable="1">
```

Fields displayed: `name`, `job_id`, `department_color`, `hr_icon_display`, `department_id`, `image_1024`

Node template: colored header by `department_color`, avatar image, name + job title, presence indicator.

**`hr_employee_public_hierarchy`** — same but `draggable="0"` (public employees can't be dragged).

**`hr_department_hierarchy_view`** — department hierarchy with `child_field="child_ids"`, shows manager + employee count button.

### Form Embed

On `hr.employee` form (`hr_views.xml`):
```xml
<div id="o_employee_right" class="col-lg-4 px-0 ps-lg-5 pe-lg-0">
    <separator string="Organization Chart"/>
    <field name="child_ids" widget="hr_org_chart" readonly="1" nolabel="1"/>
</div>
```

The org chart widget is embedded in the right column of the employee form, below the main details.

**Button:** "Org Chart" button in the form's button_box links to `/hr/get_org_chart` action with `hierarchy_res_id: id` context.

---

## L4 — How the Org Chart is Rendered

### Data Flow

```
hr.employee form loads
    → form view renders field "child_ids" with widget="hr_org_chart"
        → HrOrgChart component initializes
            → useRecordObserver sees current record (resId = employee.id)
            → extract newParentId = record.data.parent_id?.[0]
            → extract newEmployeeId = record.resId
            → fetchEmployeeData(newEmployeeId)
                → rpc('/hr/get_org_chart', {employee_id, context})
                    → HrOrgChartController.get_org_chart()
                        → reads employee.parent_id chain (up to 5 levels)
                        → reads employee.child_ids (direct)
                        → returns {self, managers[], children[], managers_more}
                → component stores data
                    → this.managers = orgData.managers
                    → this.children = orgData.children
                    → this.self = orgData.self
                    → this.render()
                        → QWeb template renders managers → self → children
```

### Hierarchy View Data Flow

```
User opens: HR → Employees → [switch to Hierarchy view]
    → action with view_mode="hierarchy"
        → view_id=hr_employee_hierarchy (arch: <hierarchy child_field="child_ids">)
            → web_hierarchy JS widget reads child_field="child_ids"
                → loads all hr.employee records
                → builds tree from parent_id relationships
                → renders nodes with avatar + department color
```

The hierarchy view does **not** use the OWL `hr_org_chart` widget — it uses the generic `web_hierarchy` widget configured via XML arch. Only the **embedded org chart** on the employee form uses the OWL widget.

### Key Design Decisions

- **`subordinate_ids` is a computed One2many.** It is not stored in the DB — it is computed on the fly from `parent_id` chains. For large organizations, this could be slow; `child_all_count` uses `recursive=True` to propagate changes.
- **`hr.employee.public` is used in controllers** for external/portal access. The controller checks `has_access('read')` and falls back to `hr.employee.public` to avoid exposing internal employee data to public users.
- **Popover clicks → "Team" kanban view.** The "See All" / subordinate counts in the popover trigger `onEmployeeSubRedirect()` which opens a kanban view of subordinates filtered by `id in subordinateIds`. `default_parent_id` is set so the view opens pre-filtered.
- **No real-time updates.** The org chart widget uses `useRecordObserver` to react to form field changes (e.g., changing the manager), but there is no live push — the chart refetches via RPC on change.

---

## SCSS / Assets

- `static/src/scss/variables.scss` — SCSS variables for photo sizes
- `static/src/scss/hr_org_chart.scss` — Layout styles for the embedded org chart: avatar sizing, tree lines, RTL flip
- `static/src/fields/hr_org_chart.xml` — QWeb templates for the chart and popover
- `static/src/fields/hooks.js` — `onEmployeeSubRedirect()` utility exported as a reusable hook

---

## File Reference

| File | Purpose |
|------|---------|
| `__manifest__.py` | Hidden category, depends on `hr` + `web_hierarchy`, lazy assets |
| `__init__.py` | Imports `controllers` |
| `models/__init__.py` | Imports `hr_employee`, `hr_org_chart_mixin` |
| `models/hr_org_chart_mixin.py` | `HrEmployeeBase` abstract with `_get_subordinates`, `_compute_subordinates`, etc. |
| `models/hr_employee.py` | Concrete `hr.employee` and `hr.employee.public` extensions with `subordinate_ids`, `is_subordinate` |
| `controllers/__init__.py` | Imports `hr_org_chart` |
| `controllers/hr_org_chart.py` | JSON-RPC controller: `/hr/get_org_chart`, `/hr/get_subordinates`, `/hr/get_redirect_model` |
| `views/hr_views.xml` | Form embed, hierarchy view, pivot/graph additions, org chart button |
| `views/hr_employee_public_views.xml` | Public employee form embed + hierarchy view |
| `views/hr_department_views.xml` | Department hierarchy view |
| `views/hr_org_chart_menus.xml` | Menu item under `hr.menu_hr_employee_payroll` |
| `static/src/fields/hr_org_chart.js` | OWL component + registry |
| `static/src/fields/hr_org_chart.xml` | QWeb templates (chart, employee row, popover) |
| `static/src/fields/hooks.js` | `onEmployeeSubRedirect()` reusable hook |
| `static/src/scss/hr_org_chart.scss` | Layout styles |
| `static/src/scss/variables.scss` | Size variables |
| `tests/test_org_chart.py` | Unit tests |