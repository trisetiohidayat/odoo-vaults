# quality

**Module Type:** Enterprise (`enterprise/suqma-19.0-20250204/enterprise/quality/`)
**Version:** 1.0
**Odoo:** 19.0 (Enterprise Edition)
**Category:** Supply Chain / Quality

## Overview

`quality` is a lightweight but powerful quality management base module for Odoo 19 Enterprise Edition. It provides the foundational infrastructure for quality control points, quality checks, and quality alerts — integrated with the stock module (stock picking, lots/serials, locations).

**Key Features:**
- Define quality control points (`quality.point`) that generate quality checks on stock pickings
- Create and manage quality checks (`quality.check`) with pass/fail tracking
- Record and track quality alerts (`quality.alert`) as issues arise
- Multi-company support with security rules
- Mail integration (chatter, activity, alias) for team notifications
- Extensible via `quality_mrp` (adds checks to manufacturing work orders) and `quality_control` sub-modules

**Dependencies:** `stock` (core dependency — quality checks are attached to stock pickings and lots)

**Extension Points:** The `quality` module is designed to be extended. Common extensions include `quality_mrp` (manufacturing), `quality_control` (measurements with tolerance), and `quality_iot` (IoT device integration).

---

## Models

### quality.point

**Model:** `quality.point` | **Table:** `quality_point` | **Inherits:** `mail.thread`

Quality control point. Defines where and when a quality check should be triggered on a stock operation.

#### Fields (L1)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Reference (auto-sequence `quality.point`, prefix `QCP`) |
| `sequence` | Integer | Sort order |
| `title` | Char | Human-readable title |
| `team_id` | Many2one (`quality.alert.team`) | Quality team responsible |
| `product_ids` | Many2many (`product.product`) | Products this point applies to (domain: `type='consu'`) |
| `product_category_ids` | Many2many (`product.category`) | Product categories this point applies to |
| `picking_type_ids` | Many2many (`stock.picking.type`) | Operations (warehouse operation types) this applies to |
| `company_id` | Many2one (`res.company`) | Company (multi-company support, index=True, required, default=`env.company`) |
| `user_id` | Many2one (`res.users`) | Responsible person (domain: users in `group_quality_user`) |
| `active` | Boolean | Archive flag (default `True`) |
| `test_type_id` | Many2one (`quality.point.test_type`) | Type of check (required, default from `_get_default_test_type_id`, tracking=True) |
| `test_type` | Char (related: `test_type_id.technical_name`) | Technical name of test type, readonly |
| `note` | Html | Instructions for the quality check |
| `reason` | Html | Why this check is needed (explanatory note) |
| `failure_location_ids` | Many2many (`stock.location`) | Available failure destination locations (domain: `usage='internal'`) |
| `show_failure_location` | Boolean (computed) | Show failure location only when test type is not `instructions` or `picture` |
| `check_count` | Integer (computed) | Number of checks created from this point |
| `check_ids` | One2many (`quality.check`, `point_id`) | Back-reference to checks |

#### Methods (L1)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `_get_default_team_id()` | `self → int` | Returns default quality team for company via `_get_quality_team` |
| `_get_default_test_type_id()` | `self → int` | Returns first available test type from `quality.point.test_type` |
| `_compute_check_count()` | `self → None` | Counts checks per point using `_read_group` |
| `_compute_show_failure_location()` | `self → None` | Hides failure location for `instructions`/`picture` test types |
| `create()` | `@api.model_create_multi` | Auto-assigns sequence `quality.point` code if name not provided |
| `check_execute_now()` | `self → bool` | Stub for override; returns `True` (L3 escalation: may be overridden in `quality_mrp` to check workorder readiness) |
| `_get_type_default_domain()` | `@api.model` | Returns empty domain `[]`; overridden in sub-modules |

#### L2 Field Details

| Field | Default | Required | Index | Notes |
|-------|---------|----------|-------|-------|
| `name` | `_('New')` via sequence | Yes | — | Copy=False |
| `sequence` | 0 | No | — | Drag-drop ordering in list view |
| `title` | None | No | — | Optional human label |
| `team_id` | via `_get_default_team_id` | Yes | Yes (company domain) | `check_company=True` |
| `product_ids` | — | No | — | `check_company=True`, domain restricts to consumable products |
| `product_category_ids` | — | No | — | Used together with `product_ids` (OR logic in matching) |
| `picking_type_ids` | — | Yes | — | `check_company=True` |
| `company_id` | `self.env.company` | Yes | Yes | Required field |
| `user_id` | None | No | — | Domain limits to `group_quality_user` members, excludes portal users |
| `active` | `True` | No | — | Soft archive |
| `test_type_id` | first test type | Yes | — | `tracking=True`; links to test type master data |
| `note` | None | No | — | Html, placeholder in view |
| `reason` | None | No | — | Html |
| `failure_location_ids` | — | No | — | Only visible when `show_failure_location=True` |

#### L3 Edge Cases

**workflow_trigger:** `create()` — calls `ir.sequence.next_by_code` for auto-naming. If sequence is deleted/corrupted, creation will raise UserError from `_get_quality_team` (line 136). The sequence is defined in `quality_data.xml` with prefix `QCP`.

**cross_model:** `failure_location_ids` → `stock.location` (usage='internal'); `picking_type_ids` → `stock.picking.type`. Both enforce `check_company=True`, which triggers multi-company domain filtering.

**failure_mode:** `check_execute_now()` — stub returns `True`. In `quality_mrp` (manufacturing module), this method is overridden to check if the workorder is in a ready state before allowing the check to be executed.

#### L4 Historical Notes

- `_check_company_auto = True` was added in Odoo 15+ for all models with `company_id`. Quality models use this flag.
- The `test_type_id` field uses `quality.point.test_type` model (configurable test types) rather than a simple selection field — this was changed from Odoo 14 to allow dynamic test type definitions per installation.
- `quality_state` field (pass/fail) was renamed from `test_result` in earlier versions.

---

### quality.point.test_type

**Model:** `quality.point.test_type` | **Table:** `quality_point_test_type`

Master data for quality test types. Used as a Many2one on `quality.point` rather than a selection field — enables per-instance customization of test types without modifying code.

| Field | Type | Default | Required | Notes |
|-------|------|---------|----------|-------|
| `name` | Char | — | Yes | `translate=True` |
| `technical_name` | Char | — | Yes | Programmatic identifier (e.g., `instructions`, `picture`, `measure`) |
| `active` | Boolean | `True` | No | Soft archive |

Default records (from `quality_data.xml`):
| ID | Name | Technical Name |
|----|------|----------------|
| `quality.test_type_instructions` | Instructions | `instructions` |
| `quality.test_type_picture` | Take a Picture | `picture` |

Additional test types (e.g., `measure`, `register_checks`) are defined in `quality_control` module.

---

### quality.check

**Model:** `quality.check` | **Table:** `quality_check` | **Inherits:** `mail.thread`, `mail.activity.mixin`

A single quality check instance. Can be linked to a stock picking or standalone. Created automatically by `stock.picking` when a matching `quality.point` is found.

#### Fields (L1)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Reference (auto-sequence `quality.check`, prefix `QC`) |
| `point_id` | Many2one (`quality.point`) | Control point that generated this check, index=`btree_not_null` |
| `title` | Char | Title (computed from `point_id.title`, stored, writable) |
| `quality_state` | Selection (`none/pass/fail`) | Status (tracking=True, default=`none`, copy=False) |
| `control_date` | Datetime | When the check was performed (tracking=True, copy=False) |
| `product_id` | Many2one (`product.product`) | Product being checked (domain: `type='consu'`) |
| `picking_id` | Many2one (`stock.picking`) | Stock picking this check belongs to, index=`btree_not_null` |
| `partner_id` | Many2one (related: `picking_id.partner_id`) | Vendor/customer from picking, string=`Partner` |
| `lot_ids` | Many2many (`stock.lot`) | Lot/serial numbers (domain filtered by `product_id`) |
| `user_id` | Many2one (`res.users`) | Person responsible (tracking=True) |
| `team_id` | Many2one (`quality.alert.team`) | Team (required, computed from `point_id.team_id`, stored, writable) |
| `company_id` | Many2one (`res.company`) | Company (required, default=`env.company`) |
| `alert_ids` | One2many (`quality.alert`, `check_id`) | Linked alerts |
| `alert_count` | Integer (computed) | Number of linked alerts |
| `note` | Html | Instructions (computed from `point_id.note`, stored, writable) |
| `test_type_id` | Many2one (`quality.point.test_type`) | Type of check (computed from `point_id`, stored, precomputed) |
| `test_type` | Char (related: `test_type_id.technical_name`) | Technical name, readonly |
| `picture` | Binary (attachment=True) | Captured image |
| `additional_note` | Text | Additional remarks |
| `failure_location_id` | Many2one (`stock.location`) | Where failed products are moved |

#### Methods (L1)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `_get_default_team_id()` | `self → int` | Returns default quality team for company |
| `_get_default_test_type_id()` | `self → int` | Returns first test type as default |
| `_compute_alert_count()` | `self → None` | Count alerts via `_read_group` |
| `_compute_title()` | `@api.depends('point_id')` | Syncs `point_id.title` |
| `_compute_note()` | `@api.depends('point_id')` | Syncs `point_id.note` |
| `_compute_team_id()` | `@api.depends('point_id')` | Syncs `point_id.team_id` |
| `_compute_test_type_id()` | `@api.depends('point_id')` | Syncs `point_id.test_type_id` or default |
| `_is_pass_fail_applicable()` | `self → bool` | Returns `False`; overridden in sub-modules |
| `create()` | `@api.model_create_multi` | Auto-assigns sequence `quality.check` code if name not provided |
| `write()` | override | If `quality_state` is set to `pass`/`fail`, calls `do_pass()`/`do_fail()` and sets `user_id`/`control_date` |
| `do_fail()` | `self → bool` | Sets `quality_state='fail'`, `user_id=env.user`, `control_date=now` |
| `do_pass()` | `self → bool` | Sets `quality_state='pass'`, `user_id=env.user`, `control_date=now` |
| `_get_type_default_domain()` | `@api.model` | Returns `[]` |

#### L2 Field Details

| Field | Default | Required | Index | Notes |
|-------|---------|----------|-------|-------|
| `name` | `_('New')` via sequence | No (auto) | — | Copy=False |
| `quality_state` | `'none'` | No | — | Tracking, copy disabled |
| `control_date` | None | No | — | Set automatically on pass/fail |
| `team_id` | via `_get_default_team_id` | Yes | Yes (company domain) | Computed+stored, writable |
| `test_type_id` | via `_get_default_test_type_id` | Yes | — | Store, compute, precompute; copy=True |
| `note` | from `point_id.note` | No | — | Store, compute, writable |
| `title` | from `point_id.title` | No | — | Store, compute, writable |
| `picture` | None | No | — | attachment=True (stored as attachment) |

#### L3 Edge Cases

**workflow_trigger:** `write()` (lines 274-281) — When `quality_state` changes via write, it automatically calls `do_pass()` or `do_fail()`. This creates a cascading workflow: write state → set user+date. Also, `do_pass()`/`do_fail()` call `write()` again — but only set the three fields (state, user, date) so no infinite loop occurs.

**cross_model:** `picking_id` → `stock.picking`; `lot_ids` → `stock.lot`; `failure_location_id` → `stock.location`. The `lot_ids` domain filters by `product_id` dynamically (per-row in tree view). `partner_id` is a related field from the picking, so access follows picking access rules.

**failure_mode:** `create()` sequence error — if `ir.sequence` for `quality.check` is missing, creation fails with UserError from `_get_quality_team` at line 185 (no quality team found). This could happen in a fresh database before `quality_data.xml` is loaded.

#### L4 Historical Notes

- `point_id` index=`btree_not_null` added in Odoo 16 to optimize queries that filter by `point_id` while allowing NULL (NULL values excluded from btree_not_null index, improving query planner decisions).
- `test_type_id` `precompute=True` added in Odoo 17 for performance — computed at record creation time rather than on demand.
- `mail.activity.mixin` added to `quality.check` in Odoo 15 (was not present in older versions).

---

### quality.alert

**Model:** `quality.alert` | **Table:** `quality_alert` | **Inherits:** `mail.thread.cc`, `mail.activity.mixin`

Quality issue or non-conformance report. Can be created standalone or linked to a `quality.check`. Part of a Kanban-based workflow with stages.

#### Fields (L1)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Reference (auto-sequence `quality.alert`, prefix `QA`, default=`_('New')`, copy=False) |
| `description` | Html | Description/details of the alert |
| `stage_id` | Many2one (`quality.alert.stage`) | Kanban stage (on delete restrict, group_expand via `_read_group_stage_ids`, tracking=True) |
| `company_id` | Many2one (`res.company`) | Company (required, default=`env.company`) |
| `reason_id` | Many2one (`quality.reason`) | Root cause (string=`Root Cause`) |
| `tag_ids` | Many2many (`quality.tag`) | Tags for categorization |
| `date_assign` | Datetime | When alert was assigned |
| `date_close` | Datetime | When alert was closed (set when stage becomes `done`) |
| `picking_id` | Many2one (`stock.picking`) | Related stock picking, index=`btree_not_null` |
| `action_corrective` | Html | Corrective action taken |
| `action_preventive` | Html | Preventive action to avoid recurrence |
| `user_id` | Many2one (`res.users`) | Responsible person (tracking=True, default=`env.user`) |
| `team_id` | Many2one (`quality.alert.team`) | Team (required, default via `_get_default_team_id`) |
| `partner_id` | Many2one (`res.partner`) | Vendor (check_company=True) |
| `check_id` | Many2one (`quality.check`) | Linked quality check, index=`btree_not_null` |
| `product_tmpl_id` | Many2one (`product.template`) | Product (domain: `type='consu'`) |
| `product_id` | Many2one (`product.product`) | Product variant (domain based on `product_tmpl_id`) |
| `lot_ids` | Many2many (`stock.lot`) | Lots (domain filtered by product/variant) |
| `priority` | Selection (`0/1/2/3`) | Priority (Normal/Low/High/Very High), index=True |

#### Methods (L1)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `_get_default_stage_id()` | `self → int` | Returns default stage for team using Domain helper |
| `_get_default_team_id()` | `self → int` | Returns default team for company via `_get_quality_team` |
| `create()` | `@api.model_create_multi` | Auto-assigns sequence `quality.alert` if name not provided |
| `write()` | override | When writing `stage_id` and `stage_id.done=True`, sets `date_close=now` |
| `onchange_product_tmpl_id()` | `@api.onchange` | Auto-sets `product_id` to first variant |
| `onchange_team_id()` | `@api.onchange` | Syncs `company_id` from team |
| `_read_group_stage_ids()` | `@api.model` | Dynamically filters available stages by team context |

#### L2 Field Details

| Field | Default | Required | Index | Notes |
|-------|---------|----------|-------|-------|
| `name` | `_('New')` | No | — | Copy=False; auto via sequence |
| `stage_id` | via `_get_default_stage_id` | No | — | `ondelete='restrict'`; `group_expand`; `tracking=True` |
| `company_id` | `self.env.company` | Yes | Yes | Required |
| `user_id` | `self.env.user` | No | — | `tracking=True` |
| `team_id` | via `_get_default_team_id` | Yes | Yes | `check_company=True` |
| `date_close` | None | No | — | Auto-set when stage becomes `done` |
| `partner_id` | None | No | — | String=`Vendor` |
| `priority` | `'0'` (Normal) | No | Yes | Selection index |

#### L3 Edge Cases

**workflow_trigger:** `write()` (lines 366-370) — When stage changes to a `done=True` stage, `date_close` is automatically set to current datetime. This is the Kanban workflow: new → confirmed → action_proposed → solved (done). The done stage sets `folded=True` (collapsed in kanban) and `done=True`.

**cross_model:** `picking_id` → `stock.picking`; `check_id` → `quality.check`; `team_id` → `quality.alert.team`; `reason_id` → `quality.reason`; `lot_ids` → `stock.lot`. Alerts can be created directly from picking form (via smart button) or from quality check form.

**failure_mode:** `_read_group_stage_ids()` uses the `Domain` helper class (line 390-396) to build dynamic domain based on `team_id` context. If no team context is set and no stages without team_ids exist, this could return an empty set causing UI issues.

#### L4 Historical Notes

- `mail.thread.cc` mixin added to support CC functionality in chatter (Odoo 16+).
- `group_expand` on `stage_id` replaced the old `_group_expand_stages` method pattern starting Odoo 15.
- `Domain` class from `odoo.fields` used for constructing domain expressions programmatically (preferred over plain tuples in newer Odoo versions).

---

### quality.alert.team

**Model:** `quality.alert.team` | **Table:** `quality_alert_team` | **Inherits:** `mail.alias.mixin`, `mail.thread`

Team that owns quality alerts and checks.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | — | Required |
| `company_id` | Many2one (`res.company`) | — | Optional, index=True |
| `sequence` | Integer | — | Sort order |
| `check_count` | Integer (computed) | # of open checks for this team |
| `alert_count` | Integer (computed) | # of open alerts for this team |
| `color` | Integer | 1 | Kanban color |

**Methods:**
- `_compute_check_count()` — uses `_read_group` on `quality.check` filtered by `team_id` and `quality_state='none'`
- `_compute_alert_count()` — uses `_read_group` on `quality.alert` filtered by `team_id` and `stage_id.done=False`
- `_get_quality_team(domain)` — `classmethod` that searches for a team by domain; raises `UserError` if none found (used as default for many models)
- `_alias_get_creation_values()` — configures email alias so external emails create `quality.alert` records under this team

#### L3 Edge Cases

**failure_mode:** `_get_quality_team()` raises `UserError` with message "No quality teams found for this company! Head over to the configuration menu to create your first quality team." (line 136). This is a critical failure mode — if no team exists for a company, creating any quality point or check will fail. However, `quality_data.xml` creates a default "Main Quality Team" in noupdate=1 mode, so on fresh install this is fine. On custom company creation, the user must manually create a team.

**cross_model:** Inherits `mail.alias.mixin` — automatically creates `mail.alias` record pointing to `quality.alert` model. The alias is configured in `mail_alias_data.xml`. This allows external email to create quality alerts.

---

### quality.alert.stage

**Model:** `quality.alert.stage` | **Table:** `quality_alert_stage`

Kanban stages for quality alerts.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | — | Required, `translate=True` |
| `sequence` | Integer | — | Sort order |
| `folded` | Boolean | — | If True, collapses card in Kanban view |
| `done` | Boolean | — | If True, marks alert as processed (triggers `date_close` on alert) |
| `team_ids` | Many2many (`quality.alert.team`) | — | Teams this stage is available to (empty = all teams) |

Default stages from `quality_data.xml`:
| Name | Folded | Done |
|------|--------|------|
| New | No | No |
| Confirmed | No | No |
| Action Proposed | No | No |
| Solved | Yes | Yes |

---

### quality.reason

**Model:** `quality.reason` | **Table:** `quality_reason`

Root cause categorization for quality alerts.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | — | Required, `translate=True` |

Default reasons from `quality_data.xml`: Workcenter Failure, Parts Quality, Work Operation, Others.

---

### quality.tag

**Model:** `quality.tag` | **Table:** `quality_tag`

Tags for categorizing quality alerts.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char | — | Required |
| `color` | Integer | — | Kanban color index |

---

## Cross-Model Relationships

```
stock.picking
  ├── quality.check (one2many via picking_id)
  │     └── quality.alert (one2many via check_id)
  └── quality.alert (one2many via picking_id)

quality.alert.team
  ├── quality.alert (one2many via team_id)
  ├── quality.check (one2many via team_id)
  └── quality.point (one2many via team_id)

quality.point
  ├── quality.check (one2many via point_id)
  └── quality.point.test_type (many2one)

quality.alert.stage
  └── quality.alert (one2many via stage_id, filtered by team_ids)

stock.location (failure locations)
  └── quality.point (failure_location_ids, domain: usage='internal')
```

**Key Integration Points:**
- `stock.picking` creates `quality.check` records when matching `quality.point` is found (triggered by stock module's `_action_confirm` or `_ button_validate`)
- `quality.check` can be linked to `stock.lot` via `lot_ids` (lot tracking)
- `quality.alert` can be created standalone or from `quality.check` (via `do_fail()`)
- `quality.alert.team` has email alias for external alert creation (incoming email handler)

---

## Configuration

### Security Groups

From `security/quality.xml`:
- `quality.group_quality_user` — basic user, inherits from `base.group_user`. Can read/create/update quality checks and alerts. Cannot delete.
- `quality.group_quality_manager` — administrator, inherits from `group_quality_user`. Full CRUD including delete. Assigned to `base.user_root` and `base.user_admin`.
- `stock.group_stock_user` — implied_ids includes `quality.group_quality_user`, so stock users automatically get quality user access.

### Record Rules (Multi-Company)

| Model | Rule | Domain |
|-------|------|--------|
| `quality.alert` | `quality_alert_comp_rule` | `[('company_id', 'in', company_ids)]` |
| `quality.check` | `quality_check_comp_rule` | `['|', ('company_id', 'in', company_ids), ('point_id.company_id', 'in', company_ids)]` |
| `quality.point` | `control_point_comp_rule` | `[('company_id', 'in', company_ids)]` |
| `quality.alert.team` | `quality_team_comp_rule` | `[('company_id', 'in', company_ids + [False])]` |

### Sequences

| Code | Prefix | Padding |
|------|--------|---------|
| `quality.point` | `QCP` | 5 |
| `quality.check` | `QC` | 5 |
| `quality.alert` | `QA` | 5 |

---

## Common Patterns

### Creating a Quality Alert from a Check

```python
# In quality.check — when a check fails:
def do_fail(self):
    self.write({
        'quality_state': 'fail',
        'user_id': self.env.user.id,
        'control_date': datetime.now()
    })
    # Alert is NOT created automatically here.
    # Alert creation is handled by the UI or stock module.
```

### Quality Point Matching Logic

A `quality.point` matches a `stock.picking` when:
1. The picking's `picking_type_id` is in `point.picking_type_ids`
2. AND ( `point.product_ids` is empty OR picking's product is in `point.product_ids` )
3. AND ( `point.product_category_ids` is empty OR picking's product category is in `point.product_category_ids` )
4. AND `point.company_id` matches picking's company

### Stage-based Workflow (Alert)

```
New → Confirmed → Action Proposed → Solved
(folded=False, done=False)         (folded=True, done=True)
         └─ date_close set when done=True
```

---

## Dependencies

```
quality (base module)
  └── depends: stock
        └── depends: base, mail, stock_account (optional), product

Quality-related extensions (separate modules):
  quality_mrp       — adds checks to manufacturing work orders
  quality_control    — adds measurement types with tolerance checking
  quality_iot        — IoT device integration
  quality_report     — reporting/analytics
```

---

## Related Modules

| Module | Location | Purpose |
|--------|----------|---------|
| `stock` | `odoo/addons/stock` | Core — pickings create quality checks |
| `quality_mrp` | Enterprise | Manufacturing workorder quality checks |
| `quality_control` | Enterprise | Measurement type with min/max tolerance |
| `quality_iot` | Enterprise | IoT device triggers |
| `quality_report` | Enterprise | BI reports for quality metrics |

---

## Tags

#quality #quality-check #quality-alert #quality-point #stock #enterprise #quality-management
