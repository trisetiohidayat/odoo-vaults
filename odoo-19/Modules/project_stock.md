# Project Stock

## Overview

| Attribute       | Value                    |
|-----------------|--------------------------|
| **Name**        | Project Stock            |
| **Category**    | Services/Project         |
| **Depends**     | `stock`, `project`       |
| **Auto-install**| Yes                      |
| **License**     | LGPL-3                   |
| **Author**      | Odoo S.A.               |
| **Version**     | 1.0                     |

## Purpose

Links `stock.picking` records to `project.project` records, enabling warehouse managers and project teams to view, filter, and navigate directly to stock operations from within a project context. It adds zero new tables — it is purely a relational binding layer with UI integration.

## Architecture

```
stock.picking                    project.project
  project_id (M2O) ───────────────┬── action_open_deliveries()
                                  ├── action_open_receipts()
                                  └── action_open_all_pickings()
```

The module does **not** add `picking_ids`, `stock_move_count`, or `stock_quant_count` to `project.project` — those fields belong to sibling modules such as `project_stock_account` and `project_mrp_stock_landed_costs`.

---

## Models

### `stock.picking` — extended from `stock`

**File:** `models/stock_picking.py`

```python
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    project_id = fields.Many2one('project.project', domain=[('is_template', '=', False)])
```

#### `project_id`

| Property       | Value                                      |
|----------------|--------------------------------------------|
| Type           | `Many2one`                                 |
| Target model   | `project.project`                          |
| Domain         | `[('is_template', '=', False)]`           |
| Ondelete       | `set null` (default Odoo M2o behavior)     |
| Store          | Yes (stored column on `stock_picking`)     |

**Why it exists:** Provides the relational anchor between a stock operation and the project that owns or requests it. Every picking linked to a project gets the project context propagated to all related stock moves, move lines, and quants.

**Domain constraint:** Templates are excluded via `is_template = False`. This prevents pickings from being attached to project templates (used for recurring/subletted project structures), which would pollute the stock planning of actual project instances.

**Performance note:** This field is stored and indexed at the `stock.picking` level. Filtering pickings by project uses the standard `stock.picking` index on `project_id`. No cross-table joins are required for the basic filtering used in the action methods.

**Security note (L4):** The form widget in the picking view is shown only to members of `project.group_project_user`. However, the underlying `project_id` field is writable by any user with write access to the picking (i.e., stock users). This is an intentional UX separation — any stock user may link a picking to a project, but only project users see the field in the UI.

---

### `project.project` — extended from `project`

**File:** `models/project_project.py`

```python
class ProjectProject(models.Model):
    _inherit = 'project.project'

    def action_open_deliveries(self)
    def action_open_receipts(self)
    def action_open_all_pickings(self)
    def _get_picking_action(self, action_name, picking_type=None)
```

All four methods are called on a single-record `self` via `ensure_one()`, consistent with action-window-style UX patterns.

#### `action_open_deliveries()`

Opens the list of outgoing pickings (`picking_type_id.code = 'outgoing'`) for the current project.

```python
def action_open_deliveries(self):
    self.ensure_one()
    return self._get_picking_action(_('From WH'), 'outgoing')
```

- Returns action for `stock.picking` with `domain: [('project_id', '=', self.id), ('picking_type_id.code', '=', 'outgoing')]`
- Sets context: `default_project_id`, `default_partner_id` (from `self.partner_id`)
- Sets `restricted_picking_type_code = 'outgoing'`
- View mode: `list,kanban,form,calendar` (no activity tab for outgoing)

#### `action_open_receipts()`

Opens incoming pickings (`picking_type_id.code = 'incoming'`) for the current project.

```python
def action_open_receipts(self):
    self.ensure_one()
    return self._get_picking_action(_('To WH'), 'incoming')
```

- Returns action with `domain: [('project_id', '=', self.id), ('picking_type_id.code', '=', 'incoming')]`
- Sets context: `default_project_id`, `restricted_picking_type_code = 'incoming'`
- View mode: `list,kanban,form,calendar,activity`

#### `action_open_all_pickings()`

Opens all pickings regardless of type for the current project.

```python
def action_open_all_pickings(self):
    self.ensure_one()
    return self._get_picking_action(_('Stock Moves'))
```

- Returns action with `domain: [('project_id', '=', self.id)]` — no type filter
- Sets context: `default_project_id`
- View mode: `list,kanban,form,calendar` (no activity tab)

#### `_get_picking_action(action_name, picking_type=None)`

Generic factory method that builds a `ir.actions.act_window` dictionary. Both `action_open_deliveries` and `action_open_receipts` delegate to it; `action_open_all_pickings` calls it with `picking_type=None`.

```python
def _get_picking_action(self, action_name, picking_type=None):
    domain = Domain('project_id', '=', self.id)
    context = {'default_project_id': self.id}
    if picking_type:
        domain &= Domain('picking_type_id.code', '=', picking_type)
        context['restricted_picking_type_code'] = picking_type
        if picking_type == 'outgoing':
            context['default_partner_id'] = self.partner_id.id
    view_mode = "list,kanban,form,calendar"
    if picking_type != 'outgoing':
        view_mode += ",activity"
    return {
        'name': action_name,
        'type': 'ir.actions.act_window',
        'res_model': 'stock.picking',
        'view_mode': view_mode,
        'domain': domain,
        'context': context,
        'help': self.env['ir.ui.view']._render_template(
            'stock.help_message_template', {
                'picking_type_code': picking_type,
            }
        ),
    }
```

**Domain construction:** Uses the new `Domain` sentinel object (Odoo 18+) rather than a plain list. The `&=` operator performs safe domain concatenation (avoids invalid empty-condition edge cases when `picking_type` is falsy).

**Context keys and their effects:**

| Context Key | Set When | Purpose |
|---|---|---|
| `default_project_id` | Always | Pre-fills `project_id` when creating a new picking from the project view |
| `default_partner_id` | `picking_type == 'outgoing'` | Pre-fills partner on new delivery orders |
| `restricted_picking_type_code` | `picking_type` is not None | Tells the stock UI to restrict the picking type selector to the given code |

**Help template:** Renders `stock.help_message_template` with `picking_type_code` to show contextual onboarding text in the list view header (e.g., "Create a delivery order" vs "Create a receipt").

---

## Embedded Actions (UI Integration)

**File:** `views/stock_picking_views.xml`

The module registers six `ir.embedded.actions` records. Embedded actions appear as smart buttons/pages inside the parent action's view. This is the Odoo 18+ mechanism for injecting contextual pages into related models without modifying the parent model's XML.

### Task List Embedded Actions

These are attached to `project.act_project_project_2_project_task_all` (the "Tasks" smart button action on the project form).

| External ID | Sequence | Name | Python Method |
|---|---|---|---|
| `project_embedded_action_from_wh` | 80 | `From WH` | `action_open_deliveries` |
| `project_embedded_action_to_wh` | 90 | `To WH` | `action_open_receipts` |
| `project_embedded_action_all_pickings` | 92 | `Stock Moves` | `action_open_all_pickings` |

### Project Dashboard Embedded Actions

These are attached to `project.project_update_all_action` (the project update/status dashboard action).

| External ID | Sequence | Name | Python Method |
|---|---|---|---|
| `project_embedded_action_from_wh_dashboard` | 80 | `From WH` | `action_open_deliveries` |
| `project_embedded_action_to_wh_dashboard` | 90 | `To WH` | `action_open_receipts` |
| `project_embedded_action_all_pickings_dashboard` | 92 | `Stock Moves` | `action_open_all_pickings` |

**Group restriction:** All six records carry `groups_ids = stock.group_stock_user`. Only users in this group see the embedded stock pages. This means the stock links appear on the project for warehouse staff, but not for purely administrative project-only users.

**Visibility evaluation (L4):** `_compute_is_visible` on `ir.embedded.actions` checks `parent_res_id` (active project ID from context), `user_id`, and `domain` at render time. Because `parent_res_id` is left empty (False) in all six records, the embedded actions are shown for **all** project records of that model, not just a specific project. This is the correct pattern for context-dependent actions that already encode the active project ID in their domain.

---

## Form View Extension

**File:** `views/stock_picking_views.xml`

A single view extension adds the `project_id` field to the picking form:

```xml
<record id="view_picking_form_inherit_project_stock" model="ir.ui.view">
    <field name="name">stock.picking.form.inherit.project_stock</field>
    <field name="model">stock.picking</field>
    <field name="inherit_id" ref="stock.view_picking_form"/>
    <field name="arch" type="xml">
        <xpath expr="//group[@name='other_infos']" position="inside">
            <field name="project_id" groups="project.group_project_user"/>
        </xpath>
    </field>
</record>
```

**Placement:** Inside the `other_infos` group — the right-hand side info box on the picking form header. This groups it with `owner_id`, `company_id`, `batch_id`, and other administrative fields.

**Group guard:** `groups="project.group_project_user"` — the field is completely invisible (not just read-only) to users who are not project users. This is intentional: stock-only users should not need to understand project assignment.

---

## Cross-Module Integration

### With `stock`
- `stock.picking` is the extended model. All picking operations (internal transfers, receipts, deliveries) can be linked to a project.
- The action methods filter by `picking_type_id.code` (`incoming`, `outgoing`, `internal`).

### With `project`
- `project.project` is the extended model. The embedded actions attach to the standard project task list action (`act_project_project_2_project_task_all`) and the project update action (`project_update_all_action`).
- `project_id` domain excludes templates: `[('is_template', '=', False)]`.

### With `project_stock_account`
Sibling module. If installed alongside `account`, it adds `stock_move_count` and `stock_analytic_accounting` items to the project dashboard. `project_stock` provides the `project_id` binding that `project_stock_account` counts against.

### With `project_mrp_stock_landed_costs`
Sibling module. Links manufacturing orders with landed costs back to projects. Relies on `project_id` being set on pickings to trace material consumption back to a project.

### With `project_purchase_stock`
Sibling module. Connects purchase receipts to projects. The `project_id` field added by `project_stock` is the join point for purchase-order-to-receipt traceability.

---

## Data Files

| File | Contents |
|---|---|
| `views/stock_picking_views.xml` | 1 form view extension + 6 `ir.embedded.actions` records |
| `views/project_project_views.xml` | Empty — no direct project view modifications |

No `data/` directory with CSV seed data or demo data exists in this module.

---

## Performance Considerations

- `project_id` on `stock.picking` is a standard stored Many2one. Index creation is handled by Odoo's ORM on column creation.
- The embedded action `_compute_is_visible` does a `search()` on `project.project` per user per render, with the active_id filter. This is a single-record lookup O(1) and not a performance concern.
- No computed fields are registered in this module, so there is no lazy/recompute overhead.
- No ORM queries are executed in the action methods themselves — they purely construct a domain and context and return an action dictionary. The database hit happens when the client renders the list view.
- The `Domain` sentinel is lightweight — it defers SQL construction to the ORM layer, avoiding string concatenation overhead.

---

## Version Change: Odoo 18 to 19

No breaking changes were identified between Odoo 18 and 19 for this module. The module is structurally identical in both versions:

| Aspect | Odoo 18 | Odoo 19 | Change |
|--------|---------|---------|--------|
| `stock.picking.project_id` field | Present | Present | None |
| `project.project` action methods | Present | Present | None |
| `ir.embedded.actions` records | Present | Present | None |
| `Domain` class usage | Present | Present | None — already using the new sentinel |

The `Domain` sentinel class (`odoo.fields.Domain`) was introduced in Odoo 18 and replaces plain Python list domains. The `_get_picking_action` method uses `Domain(...)` and `&=` operators — this module was written against Odoo 18 from the start.

If migrating a database from Odoo 17 or earlier, no data migration script is needed — the `project_id` column is added automatically by the ORM on module upgrade. However, the `ir.embedded.actions` mechanism is Odoo 18+ only; on earlier versions the module will install but the embedded stock pages will not appear.

---

## Security

No dedicated security CSV files exist. Security is enforced through:

1. **Record-level ACL**: `project_id` on `stock.picking` is subject to `stock.picking`'s ACL rules. Any user who can write a picking can set its `project_id`.
2. **Field visibility**: `project_id` on the picking form is gated by `project.group_project_user`.
3. **Embedded action visibility**: All stock picking links on the project are gated by `stock.group_stock_user`.

**Potential issue (L4):** There is no `ir.rule` enforcing that a user can only link a picking to a project they have access to. A stock manager with write access to a picking belonging to Project A could theoretically set `project_id = Project B`, even without Project B access. If strict project isolation is required, a record rule on `stock.picking` restricting `project_id` to accessible projects would need to be added.

**Supply chain attack surface (L4):** Because the `project_id` field is writable by any stock user without project ACL verification, a malicious stock user could assign pickings to confidential projects and potentially expose picking names/quantities in project embedded actions visible to project members. Mitigations: apply a record rule on `stock.picking` that restricts `project_id` to projects in the user's accessible project set, or add a `check_project_access` method that validates `project_id` access before write.

**ACL inheritance (L4):** When `stock.picking` is accessed via the project's embedded action, the action's ACL context is inherited from `stock.picking` — not from `project.project`. A user with project access but no stock access will still see the embedded action button but may get an access denied error when clicking it. Ensure `stock.group_stock_user` is granted alongside `project.group_project_user` for users who need end-to-end access.

---

## Edge Cases

1. **Picking without a project:** All three action methods return pickings with `project_id = self.id`. If `self.id` is a new/transient record, the domain evaluates to an empty set and the list appears empty — expected behavior.
2. **Template projects:** The `project_id` domain on `stock.picking` excludes template projects. A picking cannot be linked to a template project through the UI or `write()`. However, direct SQL could bypass this domain — the constraint is UI-enforced only.
3. **Multi-company:** If `project_id` is set on a picking that is then assigned to a warehouse in a different company, standard Odoo multi-company ACLs on `stock.picking` will prevent access. No explicit company check is performed.
4. **Partner pre-fill on delivery:** `default_partner_id` is set in context only when `picking_type == 'outgoing'`. For internal transfers and receipts, the partner is not pre-filled.
5. **Sequence ordering:** Embedded actions have sequences 80, 90, 92. The task list action (`act_project_project_2_project_task_all`) by default shows embedded items in ascending sequence order. Sequences 80 and 90 appear before any standard items at sequence 100+. This places the stock links in the top section of the embedded actions panel.
6. **Domain sentinel with `&=` on empty picking_type:** When `picking_type=None` (all pickings), the `domain &= Domain(...)` is skipped and the base `Domain('project_id', '=', self.id)` is returned unchanged. This correctly includes all picking types in the result.
7. **Deleted/archived projects:** If a project is archived, existing pickings retain their `project_id` reference. The embedded action still renders for archived projects (the `ir.embedded.actions` visibility does not filter by project active state), but the list will be empty since the project's task action may be hidden by the `portal.mixin` / project ACL layer.
8. **Multiple company_ids on a project:** `project.project` supports `company_ids` (multi-company sharing). The picking's `company_id` may or may not overlap with the project's companies. Standard stock picking ACLs enforce the picking's `company_id`, which is the effective access gate here.

---

## Related Modules

- [Modules/project](Modules/Project.md) — Core project management
- [Modules/stock](Modules/Stock.md) — Stock picking and warehouse operations
- [Modules/project_stock_account](Modules/project_stock_account.md) — Adds stock valuation and analytic accounting to project stock
- [Modules/project_purchase_stock](Modules/project_purchase_stock.md) — Purchase order to receipt traceability per project
- [Modules/project_mrp_stock_landed_costs](Modules/project_mrp_stock_landed_costs.md) — MRP material traceability via project stock
- [Modules/project_purchase](Modules/project_purchase.md) — Purchase orders linked to projects
- [Modules/project_mrp](Modules/project_mrp.md) — Manufacturing orders linked to projects

---

## Tags

`#odoo19` `#modules` `#project` `#stock` `#integration`
