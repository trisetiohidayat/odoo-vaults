---
tags: [odoo, odoo19, modules, website, portal, hr, timesheet, project]
description: "Portal timesheet visibility control — toggles timesheet section visibility in the customer portal by interrogating the active state of the hr_timesheet portal home view"
---

# website_timesheet

> **Hide Portal Timesheet Information** — Controls whether the timesheet section is rendered on portal pages by reading the `active` state of `hr_timesheet.portal_my_home_timesheet`, enabling administrators to hide all timesheet data from portal users without modifying access rights or deleting records.

---

## Module Information

| Property | Value |
|----------|-------|
| Category | Website/Website |
| Version | 1.0 |
| Depends | `website`, `hr_timesheet` |
| Auto-install | `True` |
| Author | Odoo S.A. |
| License | LGPL-3 |
| Module path | `odoo/addons/website_timesheet` |

---

## Purpose

`website_timesheet` is a **thin visibility-switch module**. It does not introduce new models, fields, controllers, or data files. Its sole purpose is to override one method on `account.analytic.line` so that the portal-facing timesheet rendering can be globally suppressed.

The design uses the **view active state as a toggle switch** — an administrator deactivates the `hr_timesheet.portal_my_home_timesheet` view in Settings, and the entire timesheet portal section disappears without touching ACLs or deleting data.

---

## Dependency Chain

```
website_timesheet
  ├── website              ← website / portal rendering infrastructure
  └── hr_timesheet         ← account.analytic.line model + portal templates + controller
       ├── project         ← project.task, project.project (allow_timesheets flag)
       └── account (analytic) ← account.analytic.line base model
```

`auto_install = True` means this module installs automatically whenever both `website` and `hr_timesheet` are present on the system — ensuring the visibility control is always wired up.

---

## L1: project.project Extensions — How Timesheet Entries Are Made via Website Portal

### Portal Timesheet Entry Flow

When a portal user (customer contact) accesses the project portal and creates a timesheet entry, the complete flow is:

```
Portal User visits /my/timesheets or /my/task/<id>
  │
  ├─→ TimesheetCustomerPortal.portal_my_timesheets()
  │       │
  │       ├─→ _prepare_home_portal_values() → timesheet_count
  │       │
  │       └─→ Timesheet._timesheet_get_portal_domain()
  │               │  (see L3 section below)
  │               │
  │               └─→ Returns filtered domain based on:
  │                       • Is user internal employee? → ir.rule domain
  │                       • Is portal user? → partner_id or message_partner_id
  │                         must be child_of user's commercial_partner_id
  │                       • project_id.privacy_visibility ∈ {invited_users, portal}
  │
  └─→ QWeb template renders timesheet list
          │
          └─→ For each timesheet: display date, employee, project, task, description, unit_amount
```

**Key insight:** Portal timesheet entries are standard `account.analytic.line` records. The portal templates in `hr_timesheet/views/hr_timesheet_portal_templates.xml` render them read-only. Portal users cannot create timesheets directly from the portal — timesheet creation happens in the internal Odoo UI by employees. The portal provides **read-only visibility**.

### What Gets Rendered in the Portal

The portal templates render a read-only table of `account.analytic.line` records:

```xml
<!-- hr_timesheet_portal_templates.xml — portal_my_timesheets -->
<tr t-foreach="timesheets" t-as="timesheet">
    <td t-if="not groupby == 'date'"><span t-field="timesheet.date"/></td>
    <td t-if="not groupby == 'employee_id'"><span t-field="timesheet.employee_id"/></td>
    <td t-if="not groupby == 'project_id'"><span t-field="timesheet.project_id"/></td>
    <td t-if="not groupby == 'task_id'"><span t-field="timesheet.task_id"/></td>
    <td><span t-esc="timesheet.name"/></td>
    <td class="text-end">
        <span t-if="is_uom_day"
              t-esc="timesheet._get_timesheet_time_day()"
              t-options='{"widget": "timesheet_uom"}'/>
        <span t-else="" t-field="timesheet.unit_amount"
              t-options='{"widget": "float_time"}'/>
    </td>
</tr>
```

Columns shown depend on the `groupby` parameter: by date, employee, project, task, or parent task.

### Portal Homepage Card

The `portal_my_home_timesheet` view (inserted into `/my`) shows a shortcut card:

```xml
<!-- hr_timesheet_portal_templates.xml — portal_my_home_timesheet -->
<t t-call="portal.portal_docs_entry">
    <t t-set="icon" t-value="'/hr_timesheet/static/img/timesheet.svg'"/>
    <t t-set="title">Timesheets</t>
    <t t-set="url" t-value="'/my/timesheets'"/>
    <t t-set="text">Review all timesheets related to your projects</t>
    <t t-set="placeholder_count" t-value="'timesheet_count'"/>
</t>
```

The `website_timesheet` module controls whether this card appears by toggling the base view's `active` state.

---

## L2: Field Types, Defaults, Constraints

The `website_timesheet` module itself introduces no new fields, models, or database-level constraints. Its single Python override operates entirely in application code. However, understanding the fields on the consumed model is essential.

### `account.analytic.line` — Key Fields Consumed by Portal Templates

**Base model:** `hr_timesheet/models/hr_timesheet.py`, inherits from `account_analytic_line` in `account`

| Field | Type | Portal Role | Notes |
|---|---|---|---|
| `date` | `Date` | Groupable column | Logged date of timesheet entry |
| `employee_id` | `Many2one hr.employee` | Groupable column | The employee who logged time |
| `project_id` | `Many2one project.project` | Groupable column | Project the time was logged against |
| `task_id` | `Many2one project.task` | Groupable column | Task (optional) |
| `name` | `Char` | Free-text column | Description of work done |
| `unit_amount` | `Float` | Read-only display | Hours/minutes logged (displayed via `float_time` widget) |
| `company_id` | `Many2one res.company` | Implicit | Multi-company scoping |
| `user_id` | `Many2one res.users` | Implied | Derived from `employee_id.user_id` |

### The Controlling Field: `ir.ui.view.active`

| Field | Type | Default | Notes |
|---|---|---|---|
| `active` | `Boolean` | `True` | Controls whether this view is active. Archived views (`active=False`) are excluded from normal searches but visible with `active_test=False`. |

**No constraints** are introduced by `website_timesheet`. The only constraint on `active` is the standard Odoo boolean constraint (not null, defaults to True).

---

## L3: Cross-Module Integration — Website, Timesheet, and Project

### Override Pattern

`website_timesheet` uses the **base-stub override pattern** — `hr_timesheet` provides a no-op stub returning `True`; `website_timesheet` replaces it with a view-state query.

```
hr_timesheet (base stub, always runs first conceptually)
    ↓  _inherit = 'account.analytic.line'
website_timesheet (override)
    ↓  _inherit = 'account.analytic.line'
Both inherit from account.analytic.line (account module)
```

Python inheritance resolves to the **most specific** class. Since `website_timesheet` explicitly inherits from `account.analytic.line` and `hr_timesheet` also inherits from the same base, the MRO (Method Resolution Order) gives `website_timesheet` priority when it is loaded after `hr_timesheet`. Odoo loads modules alphabetically within a dependency chain, but because `website_timesheet` explicitly names `hr_timesheet` as a dependency, it loads **after** `hr_timesheet`, ensuring its override takes effect.

### The Base Stub in `hr_timesheet`

```python
# hr_timesheet/models/hr_timesheet.py, line 526–530
@api.model
def _show_portal_timesheets(self):
    """
    Determine if we show timesheet information in the portal.
    Meant to be overridden in website_timesheet.
    """
    return True
```

This stub exists in `hr_timesheet` specifically to be overridden. Without `website_timesheet`, portal timesheets are always visible.

### The Override in `website_timesheet`

```python
# website_timesheet/models/account_analytic_line.py
@api.model
def _show_portal_timesheets(self):
    domain = [("key", "=", "hr_timesheet.portal_my_home_timesheet")]
    return (
        self.env["ir.ui.view"]
        .sudo()
        .with_context(active_test=False)
        .search(domain)
        .filter_duplicate()
        .active
    )
```

**Step-by-step execution:**

| Step | Operation | Purpose |
|---|---|---|
| 1 | `domain = [("key", "=", "hr_timesheet.portal_my_home_timesheet")]` | Locates the canonical view key |
| 2 | `.sudo()` | Bypasses ACL on `ir.ui.view` — portal users cannot read view records |
| 3 | `.with_context(active_test=False)` | Finds archived views too; otherwise archived view = not found = crash |
| 4 | `.search(domain)` | Returns recordset; normally exactly 1 |
| 5 | `.filter_duplicate()` | Resolves to the base (non-inherited) view record |
| 6 | `.active` | Returns boolean: `True` = show, `False` = hide |

### Where `_show_portal_timesheets()` Is Called

The method is evaluated inside QWeb templates at render time. It is called via `t-value` expressions, meaning it runs server-side during template rendering, not client-side in JavaScript.

#### 1. Task Portal Page — `portal_my_task` (hr_timesheet)

```xml
<!-- hr_timesheet/views/project_task_portal_templates.xml, line 6 -->
<t t-set="show_portal_timesheets"
   t-value="timesheets and timesheets[0].env['account.analytic.line']._show_portal_timesheets()"/>
```

Controls: the timesheet tab on `/my/task/<id>`, including the progress bar, time-spent table, and "Timesheets" nav link.

#### 2. Tasks List — `portal_tasks_list_inherit` (hr_timesheet)

```xml
<!-- hr_timesheet/views/project_task_portal_templates.xml, line 46 -->
<t t-set="show_portal_timesheets"
   t-value="grouped_tasks[0][0].env['account.analytic.line']._show_portal_timesheets()"/>
```

Controls: whether the "Time Spent" column and subtotal rows appear in `/my/tasks`.

#### 3. Sale Order Portal — `sale_order_portal_content_inherit` (sale_timesheet)

```xml
<!-- sale_timesheet/views/sale_timesheet_portal_templates.xml, line 6 -->
<t t-if="sale_order.timesheet_count > 0
         and sale_order.state == 'sale'
         and sale_order.env['account.analytic.line']._show_portal_timesheets()">
    <a class="btn btn-light flex-grow-1" ...>View Timesheets</a>
</t>
```

Controls: the "View Timesheets" button on confirmed Sale Order portal pages.

#### 4. Invoice Portal — `portal_invoice_page_inherit` (sale_timesheet)

```xml
<!-- sale_timesheet/views/sale_timesheet_portal_templates.xml, line 76 -->
<t t-if="invoice.timesheet_count > 0
         and invoice.env['account.analytic.line']._show_portal_timesheets()">
```

Controls: timesheet-linked section on invoice portal pages.

### The AAL (Account Analytic Line) Creation Chain

Timesheet entries (AAL records) flow into billing via several paths. `website_timesheet` only controls portal visibility; the actual creation and billing integration is in `hr_timesheet` and `sale_timesheet`.

```
Employee creates timesheet in Odoo UI
  │
  └─→ account.analytic.line.create()
          │
          ├─→ _timesheet_preprocess_values()
          │       │  (determines project_id, task_id, employee_id, company_id)
          │       │
          │       └─→ _timesheet_preprocess_get_accounts()
          │               │  (maps project to analytic account from plan)
          │               │
          │               └─→ project_id.account_id (or plan-based account)
          │
          ├─→ [sale_timesheet installed]
          │       └─→ Links to task.sale_line_id
          │               │
          │               └─→ Links to sale.order.line
          │                       │
          │                       └─→ _compute_qty_delivered()
          │                               │  (for milestone/timesheet delivery)
          │                               │
          │                               └─→ sale.order._create_invoices()
          │                                       │  (creates account.move)
          │                                       │
          │                                       └─→ customer invoice generated
          │
          └─→ project.task.effective_hours updated (via recompute)
                  └─→ project.task.remaining_hours recalculated
                          └─→ shown on task portal as "Time Remaining"
```

**The `website_timesheet` module plays no role in AAL creation.** It only controls whether the resulting AAL records are shown in portal templates. If the view is deactivated, the AAL records still exist and still drive billing and project tracking.

### `_timesheet_get_portal_domain()` — What the Portal Actually Sees

This method (in `hr_timesheet`) determines which timesheet records a portal user can access:

```python
# hr_timesheet/models/hr_timesheet.py, line 404–414
def _timesheet_get_portal_domain(self):
    if self.env.user.has_group('hr_timesheet.group_hr_timesheet_user'):
        # Internal employee: use standard ir.rule
        return self.env['ir.rule']._compute_domain(self._name)
    return (
        Domain(
            'message_partner_ids', 'child_of',
            [self.env.user.partner_id.commercial_partner_id.id]
        )
        | Domain(
            'partner_id', 'child_of',
            [self.env.user.partner_id.commercial_partner_id.id]
        )
        & Domain('project_id.privacy_visibility', 'in',
                 ['invited_users', 'portal'])
    )
```

**Portal user access rules:**
- Timesheet must belong to a project with `privacy_visibility = 'portal'` or `'invited_users'`
- AND the timesheet's `partner_id` OR `message_partner_ids` must be in the user's commercial partner's hierarchy
- This is evaluated via `sudo()` in the portal controller before rendering

---

## L4: Version Changes Odoo 18 → 19 and Security

### Version Changes: Odoo 18 → 19

The `website_timesheet` module structure is **functionally unchanged** between Odoo 18 and Odoo 19. No new fields, methods, or data files were introduced.

| Aspect | Odoo 18 | Odoo 19 | Change |
|---|---|---|---|
| Module location | `addons/website_timesheet` | Same | None |
| `_show_portal_timesheets()` signature | `@api.model def _show_portal_timesheets(self)` | Same | None |
| `sudo()` usage | Present | Present | None |
| `active_test=False` context | Present | Present | None |
| `filter_duplicate()` call | Present | Present | None |
| Dependency chain | `website`, `hr_timesheet` | Same | None |
| `auto_install` | `True` | Same | None |

**No behavioral changes.** The module was already fully implemented in Odoo 18. The `_show_portal_timesheets()` pattern (stub in `hr_timesheet`, override in `website_timesheet`) was established before Odoo 18.

### Portal Access Security

#### Who Can See What

| Actor | `_timesheet_get_portal_domain` scope | `_show_portal_timesheets()` result |
|---|---|---|
| Internal employee (`group_hr_timesheet_user`) | Standard `ir.rule` domain on `account.analytic.line` | Always `True` (employee portal uses different rendering) |
| Portal user (customer contact) | Partner hierarchy + project privacy | Determined by view `active` state |
| Public (no auth) | Cannot reach the page — `auth="user"` on all routes | N/A |

**Critical distinction:** The `_show_portal_timesheets()` check is a **display-layer toggle**, not an access-control layer. It only affects QWeb template rendering. The underlying ACL domain (`_timesheet_get_portal_domain()`) still governs which records the portal user can actually query.

```python
# Portal controller — hr_timesheet/controllers/portal.py
domain = Domain(Timesheet._timesheet_get_portal_domain())
Timesheet_sudo = Timesheet.sudo()
timesheets = Timesheet_sudo.search(domain, ...)  # Records found by domain
# _show_portal_timesheets() is called AFTER this in the template
# If False, the list is iterated but not rendered
```

#### What Happens When the View Is Deactivated

When `hr_timesheet.portal_my_home_timesheet` is set to `active=False`:

1. `website_timesheet._show_portal_timesheets()` returns `False`
2. All four consuming templates skip their timesheet sections
3. The `timesheet_count` in `_prepare_home_portal_values()` is **not** affected — it counts records accessible by domain, not by visibility toggle
4. The `/my/timesheets` route still works (the controller does not check `_show_portal_timesheets()`)
5. Direct navigation to `/my/task/<id>` shows the task but skips the timesheet tab

**Security note:** A technically sophisticated portal user who navigates directly to `/my/timesheets` will still see timesheet records they have domain-access to. The toggle suppresses UI elements but does **not** revoke data access.

#### Why `filter_duplicate()` Is Critical for Security

`filter_duplicate()` resolves to the **base view definition**, not any website-specific override:

```python
.filter_duplicate()  # Returns the master view record
.active               # Reads from master, not from theme override
```

This prevents a portal-specific website theme from independently hiding or showing timesheets. Only the base view's `active` state in the `hr_timesheet` module controls the behavior across all websites.

#### Access Model Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    Access Control Layers                      │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: HTTP Route (auth="user")                          │
│  └── Only authenticated portal users can reach /my/timesheets│
│                                                               │
│  Layer 2: ir.rule / _timesheet_get_portal_domain()           │
│  └── Which AAL records the user can query (partner/project)   │
│                                                               │
│  Layer 3: _show_portal_timesheets()                          │
│  └── Which sections are rendered in the QWeb output           │
│                                                               │
│  Layer 4: project_id.privacy_visibility                      │
│  └── Project must be 'portal' or 'invited_users'               │
└─────────────────────────────────────────────────────────────┘
```

`website_timesheet` operates at **Layer 3 only**. It does not modify Layers 1, 2, or 4.

---

## Performance Analysis

### Query Count Per Portal Page Render

Each call to `_show_portal_timesheets()` executes exactly **one SQL query**:

```sql
SELECT id FROM ir_ui_view
 WHERE key = 'hr_timesheet.portal_my_home_timesheet'
```

With `active_test=False`, Odoo does not add `AND active = true` to this query. With `sudo()`, no ACL subquery is appended. The result is a single-row lookup that is cached by the ORM for the duration of the request.

### Batch Rendering

If a single HTTP request renders multiple portal templates that each check `_show_portal_timesheets()` (e.g., a project kanban with multiple cards), the ORM's request-level cache prevents multiple queries — the first call populates the cache, subsequent calls hit the cache.

### No Database Writes

`website_timesheet` performs **no database writes**. It is read-only. There is no risk of lock contention or write amplification under high concurrency.

---

## Edge Cases

### View Record Does Not Exist

If `hr_timesheet` is uninstalled or the view record was manually deleted:
```python
.search(domain)  # returns empty recordset
.filter_duplicate()  # returns empty recordset
.active  # raises AttributeError: 'False' object has no attribute 'active'
```
**Result:** Portal page rendering crashes with `AttributeError`. This is an unsupported configuration — `website_timesheet` requires `hr_timesheet` to be installed and the view record to exist.

### Multiple Views with the Same Key

If two `ir.ui.view` records somehow share the same `key` (data corruption or multi-install):
```python
.search(domain)  # returns recordset of N > 1
.filter_duplicate()  # returns first non-duplicate record (undefined order)
.active  # returns boolean of whichever record was returned
```
**Result:** Non-deterministic. Not a realistic production scenario.

### Archived View (active=False) — Intended Use Case

```python
.search(domain)  # finds the view even though archived
.with_context(active_test=False)  # ensures archived views are included
.filter_duplicate().active  # returns False → timesheets hidden
```
This is the **designed behavior** for hiding timesheets from the portal.

### Multi-Website Deployment

When Odoo runs multiple websites with different themes:
- The `active` state of the base view applies **uniformly** across all websites
- `website_timesheet` does not support per-website toggles
- A portal user on Website A and Website B sees the same timesheet visibility
- **Known limitation:** There is no `website_id` scoping on this control

### Batch Report Generation

When generating PDF reports (e.g., task timesheet reports):
- `_show_portal_timesheets()` is **not** applied in report generation
- Reports are controlled by data access rules (`ir.rule`) only
- An admin who hides the portal section still allows report generation for users with report access

---

## Configuration

### How to Hide Timesheets from the Portal

1. Go to **Settings > Technical > User Interface > Views**
2. Search for: `portal_my_home_timesheet`
3. Open the view record from module `hr_timesheet`
4. Uncheck the **Active** checkbox
5. Save
6. Refresh the portal homepage (`/my`) — the Timesheets card disappears

### Effect Matrix

| Portal Page | Without website_timesheet | With website_timesheet (view active) | With website_timesheet (view inactive) |
|---|---|---|---|
| `/my` homepage card | Always shown | Shown | Hidden |
| `/my/timesheets` list | Always rendered | Rendered | Rendered (URL still works) |
| `/my/task/<id>` timesheet tab | Always shown | Shown | Hidden |
| `/my/tasks` time-spent column | Always shown | Shown | Hidden |
| Sale Order portal "View Timesheets" btn | Shown if timesheets exist | Shown if timesheets exist | Hidden |
| Invoice portal timesheet section | Shown if timesheets exist | Shown if timesheets exist | Hidden |

---

## File Structure

```
website_timesheet/
├── __init__.py                           ← imports models package
├── __manifest__.py                      ← metadata, depends, auto_install
└── models/
    ├── __init__.py                       ← imports account_analytic_line
    └── account_analytic_line.py          ← _show_portal_timesheets() override
```

**No controllers, no XML views, no security CSV, no data XML** — this module is a pure Python model extension.

---

## See Also

- [Modules/hr_timesheet](hr_timesheet.md) — Core timesheet model (`account.analytic.line`), portal controller, and the base `_show_portal_timesheets()` stub returning `True`
- [Modules/project](Project.md) — Project and task models (`project.project`, `project.task`) that provide the `allow_timesheets` flag consumed in portal templates
- [Modules/sale_timesheet](sale_timesheet.md) — Consumed via `sale_timesheet_portal_templates.xml` which also gates its "View Timesheets" button on `_show_portal_timesheets()`
- [Modules/sale_project](sale_project.md) — Sale-Project bridge; SOL → project/task generation; timesheets linked to SOLs for billing
- [Patterns/Security Patterns](Security Patterns.md) — ACL design, ir.rule, record-level access
- [Core/Fields](Fields.md) — `ir.ui.view` model and the `key` + `active` + `inherit_id` fields
