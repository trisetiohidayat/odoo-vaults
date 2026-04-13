---
description: Bridges Project management and MRP Manufacturing by routing MO costs and work order labor into project-level analytic accounting, surfacing them in the project profitability panel.
tags:
  - odoo
  - odoo19
  - modules
  - project_mrp_account
  - mrp_account
  - project_mrp
  - analytic-accounting
  - profitability
---

# project_mrp_account

Bridges Project management and MRP Manufacturing by routing Manufacturing Order (MO) costs and work order labor charges into project-linked analytic accounts, so they appear in the **Project Profitability** panel alongside sales, costs, and bills.

---

## Module Hierarchy

```
project_mrp_account
├── depends: ['mrp_account', 'project_mrp']
├── auto_install: True
└── category: Services/Project
```

**Dependency chain:**
- `mrp_account` — defines `manufacturing_order` AAL category, WIP journal entries, work order analytic lines, and MO cost fields (`extra_cost`, `wip_move_ids`)
- `project_mrp` — provides `project_id` on `mrp.production` (derived from BoM), project stat buttons for MOs and BoMs, and action links
- `project_mrp_account` — wires AAL costs into the project profitability panel and handles MO re-linking analytic migration on `project_id` change

**No security CSV files.** Access control inherits from `project` and `mrp`.

---

## L1 — Core Functionality

This module's purpose is to make MO-derived costs visible in the Project Profitability panel. Without it, MO costs are tracked via `mrp_account` analytic lines but those costs are siloed — they do not appear alongside sales revenue, service costs, and purchase costs in the project's financial overview.

The mechanism is a **category tag** on analytic lines (`category = 'manufacturing_order'`) combined with a **separate profitability bucket** that queries only those tagged lines, excluding them from the base analytic query.

---

## L2 — Field Types, Defaults, Constraints

### `mrp.production` Extension — `has_analytic_account`

```python
has_analytic_account = fields.Boolean(compute='_compute_has_analytic_account')
```

| Property | Value |
|----------|-------|
| Type | `boolean` |
| Stored | Yes (computed) |
| Compute | `_compute_has_analytic_account` |
| Depends | `project_id` |

**Computation logic:**
```python
@api.depends('project_id')
def _compute_has_analytic_account(self):
    has_analytic_account_per_project_id = {
        p.id: bool(p._get_analytic_accounts())
        for p in self.project_id
    }
    for production in self:
        production.has_analytic_account = has_analytic_account_per_project_id.get(
            production.project_id.id, False
        )
```

- Uses a **dictionary lookup** to avoid N+1 recomputation when multiple MOs share the same project.
- `_get_analytic_accounts()` (from `project`) returns all analytic accounts linked to the project (via multiple plan columns).
- Returns `False` if `project_id` is `False`, or if the project has no analytic accounts configured.
- Used to conditionally show the "Analytic Accounts" smart button on the MO form.

### `stock.move` Extension — `_get_analytic_distribution`

```python
def _get_analytic_distribution(self):
    distribution = self.raw_material_production_id.project_id._get_analytic_distribution()
    return distribution or super()._get_analytic_distribution()
```

| Property | Value |
|----------|-------|
| Return type | `dict` or `False` |
| Context | `raw_material_production_id` must be set |

- Intercepts `stock_account`'s distribution lookup for raw material consumption moves.
- Returns the project's distribution if the move belongs to an MO with a project.
- Falls back to `super()` (product analytic distribution, then location fallback) if no project.

### `stock.move` Extension — `_prepare_analytic_line_values`

```python
def _prepare_analytic_line_values(self, account_field_values, amount, unit_amount):
    res = super()._prepare_analytic_line_values(account_field_values, amount, unit_amount)
    if self.raw_material_production_id:
        res['category'] = 'manufacturing_order'
    return res
```

| Property | Value |
|----------|-------|
| Return type | `dict` (AAL field values) |
| Modified field | `category` on `account.analytic.line` |

The `category` field is a `Selection` on `account.analytic.line` added by `mrp_account`. Possible values include `'general'`, `'manufacturing_order'`, `'stock_account'` etc. Setting it to `'manufacturing_order'` marks these lines for routing to the MRP profitability bucket.

### `stock.move` Extension — `_prepare_analytic_lines`

```python
def _prepare_analytic_lines(self):
    res = super()._prepare_analytic_lines()
    if res and self.raw_material_production_id:
        project = self.raw_material_production_id.project_id
        mandatory_plans = project._get_mandatory_plans(
            self.company_id, business_domain='manufacturing_order'
        )
        missing_plan_names = [
            plan['name'] for plan in mandatory_plans
            if not project[plan['column_name']]
        ]
        if missing_plan_names:
            raise ValidationError(_(
                "'%(missing_plan_names)s' analytic plan(s) required "
                "on the project '%(project_name)s' linked to the "
                "manufacturing order.",
                missing_plan_names=missing_plan_names,
                project_name=project.name,
            ))
    return res
```

| Property | Value |
|----------|-------|
| Return type | `list[dict]` or falsy |
| Raises | `ValidationError` if mandatory plans missing |
| Guard | Only runs when `raw_material_production_id` is set |

**Mandatory plans** are defined via `account.analytic.applicability` records:
```python
# Example applicability record (from mrp_account)
{
    'business_domain': 'manufacturing_order',
    'analytic_plan_id': plan_id,
    'applicability': 'mandatory',  # or 'optional'
}
```

`_get_mandatory_plans` returns all plans where applicability for `manufacturing_order` is `'mandatory'`.

### `mrp.workorder` Extension — `_create_or_update_analytic_entry_for_record`

```python
def _create_or_update_analytic_entry_for_record(self, value, hours):
    super()._create_or_update_analytic_entry_for_record(value, hours)
    project = self.production_id.project_id
    mo_analytic_line_vals = self.env['account.analytic.account']._perform_analytic_distribution(
        project._get_analytic_distribution(), value, hours,
        self.mo_analytic_account_line_ids, self
    )
    if mo_analytic_line_vals:
        self.sudo().mo_analytic_account_line_ids = [
            Command.create(line_val) for line_val in mo_analytic_line_vals
        ]
```

| Property | Value |
|----------|-------|
| Target field | `mo_analytic_account_line_ids` (Many2many, from `mrp_account`) |
| ACL bypass | Uses `sudo()` for the Many2many write |
| Purpose | Post work order labor costs to the MO's project analytic account |

`value` is computed by `mrp_account` as: `-(hours * wo.workcenter_id.costs_hour)`. `_perform_analytic_distribution` (from `account_analytic`) creates or updates analytic lines using the project's distribution and the existing `mo_analytic_account_line_ids` to avoid duplication.

### `mrp.production.write()` — Re-analytic on Project Change

```python
def write(self, vals):
    res = super().write(vals)
    for production in self:
        if 'project_id' in vals and production.state != 'draft':
            production.move_raw_ids._create_analytic_move()
            production.workorder_ids._create_or_update_analytic_entry()
    return res
```

| Guard condition | `vals` contains `'project_id'` AND `production.state != 'draft'` |
|----------------|--------------------------------------------------------------|

When a confirmed (or later state) MO's `project_id` is changed, the module regenerates all analytic entries:
- `move_raw_ids._create_analytic_move()` — re-generates raw material AALs under the new project
- `workorder_ids._create_or_update_analytic_entry()` — re-generates work order labor AALs under the new project

Both are safe for draft MOs because no moves or time entries exist yet.

### `stock.rule._prepare_mo_vals` — Preserve `project_id` on Auto-MO Creation

```python
def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom):
    res = super()._prepare_mo_vals(product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom)
    if values.get('project_id'):
        res['project_id'] = values['project_id']
    return res
```

When MOs are created via procurement rules (e.g., from a project task linked to a BoM), `values['project_id']` is passed in the procurement context. This override ensures the newly created MO carries that project forward.

---

## L3 — Cross-Model, Override Pattern, Workflow Triggers

### Cross-Module Integration Map

```
project_mrp_account
│
├── project_mrp
│   ├── mrp.production : project_id (from BoM via _compute_project_id)
│   ├── project.project : bom_count, production_count stat fields
│   └── action_view_mrp_production / action_view_mrp_bom (stat buttons)
│
├── mrp_account
│   ├── account.analytic.line : category += 'manufacturing_order'
│   ├── account.analytic.applicability : business_domain += 'manufacturing_order'
│   ├── mrp.production : extra_cost, wip_move_ids, show_valuation
│   ├── mrp.workorder : mo_analytic_account_line_ids, wc_analytic_account_line_ids
│   │       └─ _create_or_update_analytic_entry() → posts AAL with category='manufacturing_order'
│   └── account.move : wip_production_ids (WIP journal entries)
│
├── stock_account
│   └── stock.move : _get_analytic_distribution()     [OVERRIDDEN by project_mrp_account]
│                   : _create_analytic_move()          [CALLED by project_mrp_account.write]
│                   : _prepare_analytic_lines()         [GUARDED by project_mrp_account]
│
└── project
    └── project.project : profitability panel
        └─ _get_profitability_items()   [EXTENDED by project_mrp_account]
        └─ _get_profitability_aal_domain() [FILTERS OUT manufacturing_order from base query]
```

### Override Pattern Summary

| Model | Method | Override Type | Purpose |
|-------|--------|---------------|---------|
| `project.project` | `_get_profitability_labels` | Extend dict | Add `'manufacturing_order': 'Manufacturing Orders'` |
| `project.project` | `_get_profitability_sequence_per_invoice_type` | Extend dict | Add `sequence = 12` for MO costs |
| `project.project` | `_get_profitability_aal_domain` | Replace + extend | Exclude `category = 'manufacturing_order'` from base AAL query |
| `project.project` | `_get_profitability_items` | Append to `costs.data` | Add MO cost bucket with currency conversion |
| `mrp.production` | `_compute_has_analytic_account` | New computed field | Show/hide analytic button |
| `mrp.production` | `action_view_analytic_accounts` | New action | Open project's analytic accounts |
| `mrp.production` | `write()` | Extend with re-analytic | Regenerate AALs on project change |
| `stock.move` | `_get_analytic_distribution` | Replace primary branch | Pull from MO's project |
| `stock.move` | `_prepare_analytic_line_values` | Append to result | Tag AAL with `category='manufacturing_order'` |
| `stock.move` | `_prepare_analytic_lines` | Guard with validation | Check mandatory project plans |
| `mrp.workorder` | `_create_or_update_analytic_entry_for_record` | Extend super call | Post work order labor to project |
| `stock.rule` | `_prepare_mo_vals` | Inject into vals | Preserve project_id from procurement context |

### Workflow Trigger: Analytic Line Lifecycle

**For one MO raw material move:**

```
1. MO confirmed (action_confirm)
      └─ mrp.production.move_raw_ids created (reservation, not yet consumed)

2. Components consumed (move action_done)
      └─ stock_account.stock.move._create_analytic_move()
            └─ _get_analytic_distribution()         [project_mrp_account]
                  └─ returns project._get_analytic_distribution()
                        (falls back to super() if no project)

            └─ _prepare_analytic_lines()             [project_mrp_account]
                  └─ validates mandatory plans on project
                        raises ValidationError if missing

            └─ _prepare_analytic_line_values()       [project_mrp_account]
                  └─ sets category = 'manufacturing_order'

            └─ account.analytic.line created
                  ├─ auto_account_id = project's auto-generated AA
                  ├─ category = 'manufacturing_order'
                  └─ amount = -(consumed_qty * product.standard_price)

3. Project profitability panel (_get_profitability_items)
      └─ base query: AAL WHERE auto_account_id IN project.account_id.ids
                         AND category != 'manufacturing_order'  [filtered by project_mrp_account]
      └─ MO bucket: AAL WHERE auto_account_id IN project.account_id.ids
                        AND category = 'manufacturing_order'
                     → SUM(amount) → displayed as 'Manufacturing Orders' cost
```

**For one work order:**

```
1. Work order started (time tracking begins)
      └─ wo._create_or_update_analytic_entry()
            ├─ base (mrp_account): value = -(duration_hours * wc.costs_hour)
            │     └─ creates wc_analytic_account_line_ids (work center costs)
            │
            └─ project_mrp_account override:
                  ├─ project = self.production_id.project_id
                  ├─ mo_analytic_line_vals = _perform_analytic_distribution(
                  │       project._get_analytic_distribution(),
                  │       value, hours,
                  │       self.mo_analytic_account_line_ids, self
                  │   )
                  └─ sudo().mo_analytic_account_line_ids += [Command.create(...)]
                        └─ creates mo_analytic_account_line_ids (MO labor → project AA)

2. Work order finished (button_finish)
      └─ wo._create_or_update_analytic_entry() with final duration
            └─ AAL amounts updated to reflect total hours

3. MO done (button_mark_done)
      └─ mrp_account._post_labour() → WIP account.move (not analytic)
      └─ mrp_account._cal_price() → finished move price_unit updated
```

---

## L4 — Version Change: Odoo 18 → Odoo 19

### Module Status

`project_mrp_account` has had **no breaking changes** between Odoo 18 and Odoo 19. The core mechanism — routing AAL costs into the project profitability panel via a category tag — is unchanged.

### Key Areas of Stability

#### `Domain` Class for `AND` Composition

The `_get_profitability_aal_domain()` method uses `Domain.AND()`:

```python
from odoo.fields import Domain

def _get_profitability_aal_domain(self):
    return Domain.AND([
        super()._get_profitability_aal_domain(),
        Domain('category', '!=', 'manufacturing_order'),
    ])
```

In Odoo 18, domain tuples were lists of triples: `[('field', 'operator', value)]`. The `Domain` class is a programmatic, composable alternative introduced in Odoo 18 and used consistently in Odoo 19. Both approaches produce the same SQL, but `Domain.AND()` is the preferred Odoo 19 pattern.

**Backward compatibility:** If the parent `super()` still returns a legacy list-of-tuples domain, `Domain.AND()` accepts both types, so this is not a breaking change.

#### `auto_account_id` Field Stability

The `auto_account_id` field on `account.analytic.line` (the anchor for profitability queries) was introduced in earlier versions and remains stable. No changes in Odoo 19.

#### `business_domain = 'manufacturing_order'` Applicability

The `account.analytic.applicability` record with `business_domain = 'manufacturing_order'` is created by `mrp_account` in this module chain. No changes to this mechanism in Odoo 19.

### Subtle Changes to Be Aware Of

#### `_get_profitability_items` Multi-Company Currency Conversion

The `_get_profitability_items()` method performs currency conversion:
```python
total_amount += currency._convert(amount_summed, self.currency_id, self.company_id)
```

Odoo 19 introduced stricter multi-company validation on `_convert()`. If the AAL's `company_id` is different from the project's `company_id`, the conversion requires that both companies share a rate in `res.currency.rate`. If no rate exists, the conversion returns 0 silently. This is consistent behavior but may surface previously hidden data gaps.

#### `sudo()` Usage in `_get_profitability_items`

```python
mrp_aal_read_group = self.env['account.analytic.line'].sudo()._read_group(...)
```

Uses `sudo()` to bypass potential AAL record rules. This is unchanged from Odoo 18 but the rationale is important: AAL access rules may differ from project access rules. A project manager may not have direct read access to analytic lines but should still see the profitability total.

#### `Command.create` for Many2many Writes

The `mrp_workorder.py` override uses:
```python
self.sudo().mo_analytic_account_line_ids = [
    Command.create(line_val) for line_val in mo_analytic_line_vals
]
```

`Command` is the Odoo 16+ API for writing to `Many2many` and `One2many` fields. In older versions this was done with `(0, 0, vals)` tuples. The `Command` class is preferred in Odoo 19 for clarity and IDE support. This is stable across 18→19.

### Things That Did NOT Change

- `mrp.production.project_id` — the field linking MOs to projects is unchanged
- `mrp.workorder.production_id.project_id` — traversal path unchanged
- `_create_analytic_move()` signature and behavior in `stock_account`
- AAL `category` values and their meaning
- The profitability panel JSON structure returned by `_get_profitability_items`

### Migration Checklist

| Check | Detail |
|-------|--------|
| Currency rates | Ensure `res.currency.rate` records exist for all company/currency combinations used in MO → project cost tracking |
| Mandatory plans | Verify all projects linked to MOs have required analytic plans configured |
| MRP group for drill-down | The "View Manufacturing Orders" action requires `mrp.group_mrp_user`; project managers without MRP access see costs but not the action |
| Demo data | `data/project_mrp_account_demo.xml` creates two MOs and marks one done; safe for re-import |

---

## L4 — Test Coverage Deep Dive

### `test_analytic_account.py` — `TestAnalyticAccount`

Extensive test suite covering every major code path. Key scenarios:

#### `test_mo_analytic`
- Creates MO linked to a project with an analytic account
- Confirms MO, verifies no AAL at confirmation time (analytic lines created only on consumption)
- Increases `qty_producing` from 0 → 5 → 10, verifying AAL amount updates: -50, -100
- Marks WO done, verifies state transitions and AAL amounts remain consistent
- Marks MO done, verifies AAL amounts stable post-completion

**Key assertion:** `mo.move_raw_ids.analytic_account_line_ids.amount` reflects the current consumed quantity at each step, not the planned quantity.

#### `test_mo_analytic_backorder`
- Creates MO with `qty_producing = 5` then calls `button_mark_done().action_backorder()`
- After backorder, the original MO should have AAL for 5 units (half), not 10
- Verifies AAL is correctly scoped to actual consumed quantity in the closed MO

#### `test_workcenter_different_analytic_account`
- Sets a workcenter with a **different** analytic distribution from the MO's project
- When WO duration changes, two sets of AAL are created:
  - `wc_analytic_account_line_ids` — work center cost attributed to WC's AA
  - `mo_analytic_account_line_ids` — MO labor cost attributed to project's AA
- Both sets of lines are verified to have correct amounts and correct analytic accounts
- Confirms no duplication when WC and MO share the same AA

#### `test_changing_mo_analytic_account`
- Creates and confirms MO with project A
- Marks done, verifies AAL exists on project A's AA
- Changes MO's project to project B (non-draft MO)
- Verifies AAL lines are **deleted** from project A and **recreated** under project B
- Removes project entirely (`project_id = False`)
- Verifies all AAL lines deleted
- Re-assigns project, verifies AAL recreated
- **This is the primary test for the `write()` re-analytic override.**

#### `test_mandatory_analytic_plan_production`
- Sets a plan's applicability to `mandatory` for `business_domain = 'manufacturing_order'`
- Removes that plan from the project
- Adds a different plan to the project
- Confirms MO, then attempts `button_mark_done()`
- Asserts `ValidationError` is raised with the missing plan name

#### `test_cross_analytics`
- Creates a project with **two** analytic plans and accounts (plan1/account1, plan2/account2)
- Creates and processes MO linked to that project
- Verifies AAL lines have **both** accounts set (cross-analytic distribution)
- This exercises the multi-plan path in `_get_analytic_distribution()`

#### `test_mo_qty_analytics`
- Creates and confirms MO, refills components
- Tests quantity oscillation: producing qty 5 → 0 → 5
- Verifies AAL balance goes -50 → 0 → -50 as consumed quantity changes
- **Critical edge case:** qty_producing = 0 should result in zero AAL even after confirmation

#### `test_bom_aal_generation`
- Sets `project_id` on the **BoM** itself, not just the MO
- Sets `operation_id` on BoM line to link it to a routing operation
- Marks WO done before MO done
- Verifies AAL is created **once** (not duplicated) when both WO finish and MO done fire

#### `test_update_components_qty_to_0`
- Creates and processes MO, marks done
- Sets component `quantity = 0` on a done move
- Verifies AAL is **deleted** when the consumed quantity drops to zero
- Verifies `analytic_account.debit` drops to 0

#### `test_category_analytic_line_mrp`
- Confirms and marks MO done
- Verifies `mo.move_raw_ids.analytic_account_line_ids.category == 'manufacturing_order'`
- This is the primary test for the `_prepare_analytic_line_values` category tagging

### `test_project_profitability.py` — `TestSaleProjectProfitabilityMrp`

**Extends:** `TestProjectProfitabilityCommon` from `project`

**`test_profitability_mrp_project`:**
- Creates a project and its analytic account
- Creates AAL with `category = 'manufacturing_order'` linked to that account
- Verifies profitability dict structure: `{'costs': {'data': [{'id': 'manufacturing_order', 'sequence': 12, 'billed': X}], 'total': {'billed': X}}}`
- **Multi-currency test:** Creates AAL with `company_id = foreign_company` (different currency), verifies conversion to project currency: 500 + 100 (foreign) = 120.0 (after conversion at rate ~5.0)
- Adds AAL with `company_id = current_company`, verifies total updated: 120 + 500 + 200 = 820.0

### `test_project_stock.py` — `TestProjectStock`

**`test_check_company`:**
- Tests cross-model Many2one assignment: `project.partner_id = new_partner`
- Creates a warehouse linked to that partner
- Ensures no company mismatch error occurs

---

## Data File — Demo Setup

**`data/project_mrp_account_demo.xml`** creates:

```xml
<!-- A storable product: Dining Table -->
product_product_dinning_table:
    name: "Dining Table"
    standard_price: 100.0
    list_price: 110.50
    is_storable: True

<!-- Draft MO: drawer (linked to existing mrp.bom_drawer) -->
mrp_production_drawer_1:
    product_id: product_product_27 (drawer)
    product_qty: 5
    bom_id: mrp.mrp_bom_drawer

<!-- Done MO: dining table (linked to existing mrp.bom_wood_panel) -->
mrp_production_dinning_table_2:
    product_id: project_mrp_account.product_product_dinning_table
    product_qty: 5
    bom_id: mrp.mrp_bom_wood_panel

<!-- Confirm both MOs -->
function: action_confirm → [drawer_1, dinning_table_2]

<!-- Mark dining table MO done (triggers AAL generation) -->
function: button_mark_done → [dinning_table_2]
```

This exercises the full chain: raw material consumption generating AAL lines under the project's analytic distribution, work order duration generating MO labor AAL lines, and the WIP entry created by `mrp_account._post_labour()`.

Note: No project is explicitly set on the demo MOs — the `bom_id` sets the project via `project_mrp`'s compute. The demo validates that the BoM → MO → project pipeline works end-to-end.

---

## Security Considerations (L4)

| Concern | Detail |
|---------|--------|
| AAL cost visibility | Project managers (`project.group_project_manager`) see all MO costs in profitability regardless of MRP group membership |
| Action button visibility | `action_view_mrp_production` requires `mrp.group_mrp_user` — non-MRP users see the cost number but cannot click through to MOs |
| Analytic line writes | `mrp_workorder._create_or_update_analytic_entry_for_record` uses `sudo()` to bypass work order ACL restrictions when writing analytic lines |
| MO re-linking | `mrp_production.write()` calls `_create_analytic_move()` in `sudo()` context (from `stock_account`); analytic entries may be created for moves the user cannot directly access |
| `wip_production_ids` | `account.move.wip_production_ids` is populated by `mrp_account` WIP logic; no extra ACL needed beyond existing `account` model rules |
| Mandatory plan validation | `ValidationError` is raised if mandatory plans are missing — this blocks move completion, not just a silent misallocation |

### ACL Inheritance Without CSV

Since no `security/ir.model.access.csv` exists, all model access inherits from:
- `mrp_account` — `mrp_production`, `mrp_workorder`, `account_move` for WIP
- `project_mrp` — no new ACL
- `project` — `project_project`, `account_analytic_line`

A user who can access a project automatically sees MO costs in the profitability panel if they can see the project.

---

## Edge Cases (L4)

### 1. MO with no project (`project_id = False`)

`_get_analytic_distribution()` falls back to `super()` — no AAL lines created, no profitability entry. `has_analytic_account` is `False`, hiding the analytic accounts button.

**No error raised** — this is the default behavior when MOs are created without a BoM or without project-linked BoMs.

### 2. MO with project but no analytic accounts on project

`_compute_has_analytic_account` returns `False`. `stock_move._get_analytic_distribution()` returns `{}` (empty dict). `stock_account` creates no AAL lines. No error raised.

**Result:** MO costs are tracked via `mrp_account` WIP journal entries but not via analytic lines. Project profitability panel shows no MO costs.

### 3. Changing `project_id` on a non-draft MO

Triggers analytic re-generation. If mandatory plans are missing on the new project, `_prepare_analytic_lines()` raises `ValidationError` and the `write()` is rolled back. The user must configure the new project's plans before assigning it.

**This is a safety mechanism** — assigning a project with incomplete analytic configuration should not silently misallocate costs.

### 4. Phantom BoM (Kit Products)

`mrp_account.stock.move._get_all_related_sm()` extends the kit product explosion logic; analytic distribution is applied per component at the kit's price unit. This is inherited by `project_mrp_account` without additional override. Each exploded component move gets the same distribution from the MO's project.

### 5. Multi-Currency AAL

`_get_profitability_items()` groups AAL by `currency_id` and converts each group to the project's `currency_id` and `company_id`. If no exchange rate exists between the AAL's currency and the project currency, the conversion returns 0 silently.

**Test `test_profitability_mrp_project` validates this:** AALs created with `foreign_company` currency (500 + 100 = 600 foreign) are converted at the rate between the foreign currency and EUR (default rate ≈ 5), yielding 120 in the project currency.

### 6. WIP Journal Entries vs. Analytic Lines

`mrp_account._post_labour()` creates WIP `account.move` lines but **does NOT create analytic lines** (those are the work order labor AALs from `project_mrp_account`). The WIP entry is linked to the MO via `wip_move_ids` / `wip_production_ids` but is a **separate accounting entry** from the analytic lines used in profitability.

The WIP entry is visible in the accounting entries but not in the project profitability panel (which only reads analytic lines).

### 7. MO without components (service-type BoM)

MOs without `move_raw_ids` (e.g., service BoMs or subcontracting) have no raw material consumption moves. Work order labor AALs are still generated via `mrp_workorder`. The `_get_analytic_distribution()` override handles this correctly because it only affects moves with `raw_material_production_id` set.

### 8. Negative Quantity Consumption (Scrap/Returns)

When components are consumed in negative quantities (e.g., return of components, scrap adjustments), the same `_get_analytic_distribution()` is used. AAL amounts will be positive (credit) instead of negative (debit), reducing the project's MO cost. This is correct accounting behavior.

---

## Related

- [Modules/mrp_account](Modules/mrp_account.md) — MO costing, WIP journal entries, work order analytic lines, `manufacturing_order` AAL category
- [Modules/project_mrp](Modules/project_mrp.md) — `project_id` on MO (from BoM), project stat buttons for MOs and BoMs
- [Modules/Stock](Modules/stock.md) — Stock move costing and `_create_analytic_move()` from `stock_account`
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine pattern (MO workflow: draft → confirmed → done)
