---
tags:
  - odoo
  - odoo19
  - modules
  - project
  - purchase
  - profitability
  - analytic
---

# project_purchase

> Monitor and manage purchase orders directly within project context. Provides purchase visibility in the project dashboard, links purchase lines to project analytic accounts, and surfaces costs in the project profitability report.

---

## Module Overview

| Property | Value |
|---|---|
| **Technical Name** | `project_purchase` |
| **Version** | `1.0` |
| **Category** | `Services/Project` |
| **License** | `LGPL-3` |
| **Auto-install** | `True` |
| **Depends** | `purchase`, `project_account` |
| **Author** | Odoo S.A. |

### Purpose

`project_purchase` bridges the **Project** and **Purchase** apps. It allows project managers to:

- Link a `purchase.order` directly to a `project.project`
- Auto-apply the project's analytic account to purchase order lines at creation time
- Count confirmed purchase orders on a project (via direct link and analytic account match)
- Surface purchase costs in the project profitability panel with proper billing/invoice reconciliation
- Open purchase orders from project dashboard smart buttons and embedded action tabs

### Dependencies Explained

- **`purchase`**: Provides `purchase.order`, `purchase.order.line`, all PO workflow states (`draft`, `sent`, `purchase`, `done`, `cancel`), and the `purchase.group_purchase_user` security group.
- **`project_account`**: Provides `project.project`'s analytic account integration (`account_id`), the profitability computation infrastructure (`_get_profitability_items`, `_add_purchase_items`, `_get_stat_buttons`, `_get_profitability_aal_domain`), and the `other_purchase_costs` section. `project_purchase` **overrides** the `_add_purchase_items` stub in `project_account` with a real implementation (`_add_purchase_items` returns `False`), disabling the fallback costs-from-vendor-bill approach for confirmed PO lines — those are handled directly by `project_purchase` via the `purchase_order` section.

**Auto-install rationale**: `auto_install: True` means the module is pulled in automatically whenever both `purchase` and `project_account` (transitively, since `project_account` depends on `project`) are installed. This is semantically correct: `project_purchase` has no purpose without both dependencies present.

---

## Model Extensions

All three extended models live in `models/` and are imported in order by `models/__init__.py`:

```
project_purchase/models/
  purchase_order.py       # purchase.order + project_id field
  purchase_order_line.py  # purchase.order.line + _compute_analytic_distribution
  project_project.py      # project.project + PO count, actions, profitability
```

---

## `purchase.order` — `models/purchase_order.py`

```python
class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    project_id = fields.Many2one('project.project', domain=[('is_template', '=', False)])
```

### Field: `project_id`

| Property | Value |
|---|---|
| **Type** | `Many2one` |
| **Target model** | `project.project` |
| **Domain** | `[('is_template', '=', False)]` |
| **ondelete** | Not declared (no cascade) |

**Why it exists**: Provides a first-class, persistent link between a PO and a project. Used by `_compute_purchase_orders_count` to enumerate POs attached to a project via direct link, and by `_get_profitability_items` as a fallback tie-breaker when a line has no analytic distribution.

**Project template exclusion**: The domain `[('is_template', '=', False)]` prevents linking POs to project templates, which do not represent real work and have no analytic account.

**Security**: The field is only visible to users in `project.group_project_user` via the inherited form view in `views/purchase_order.xml`. Purchase-only users (without project access) cannot see or set the project on a PO. The field itself is not restricted at ORM level — it is purely a UI gate.

**No `ondelete` cascade**: Archiving or deleting a project does not affect linked POs. This is intentional: the PO may still need to be processed (delivered, invoiced) independently of the project lifecycle.

### UI Injection

The field is added to the PO form via view inheritance in `views/purchase_order.xml`:

```xml
<record id="view_order_form_inherit_project_purchase" model="ir.ui.view">
    <field name="name">purchase.order.form.purchase.project</field>
    <field name="model">purchase.order</field>
    <field name="inherit_id" ref="purchase.purchase_order_form"/>
    <field name="priority">10</field>
    <field name="arch" type="xml">
        <field name="origin" position="after">
            <field name="project_id" groups="project.group_project_user"/>
        </field>
    </field>
</record>
```

Placed after `origin`, between the sourcing fields and the virtual fields (like `invoice_count`). Priority 10 is low enough to override the base purchase view but not so low as to be overridden by other third-party modules.

---

## `purchase.order.line` — `models/purchase_order_line.py`

```python
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.depends('product_id', 'order_id.partner_id', 'order_id.project_id')
    def _compute_analytic_distribution(self):
        super()._compute_analytic_distribution()
        ProjectProject = self.env['project.project']
        for line in self:
            project_id = line.env.context.get('project_id')
            project = ProjectProject.browse(project_id) if project_id else line.order_id.project_id
            if line.display_type or not project:
                continue
            if line.analytic_distribution:
                applied_root_plans = self.env['account.analytic.account'].browse(
                    list({int(account_id) for ids in line.analytic_distribution
                          for account_id in ids.split(",")})
                ).root_plan_id
                if accounts_to_add := project._get_analytic_accounts().filtered(
                        lambda account: account.root_plan_id not in applied_root_plans
                ):
                    line.analytic_distribution = {
                        f"{account_ids},{','.join(map(str, accounts_to_add.ids))}": percentage
                        for account_ids, percentage in line.analytic_distribution.items()
                    }
            else:
                line.analytic_distribution = project._get_analytic_distribution()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._recompute_recordset(fnames=['analytic_distribution'])
        return lines
```

### `_compute_analytic_distribution` — L3/L4 Analysis

**Trigger dependencies**: `product_id` (fires when a product is picked, triggering the parent class's ADM logic), `order_id.partner_id` (fires when the vendor changes, triggering partner-based ADMs), and `order_id.project_id` (fires when the project is set on the order).

**Two-source project resolution**:

1. First checks `self.env.context.get('project_id')` — set by the `ProjectPurchaseCatalogController` when a user creates a PO line from the in-project product catalog. This allows the project context to propagate into the line before the PO itself is saved.
2. Falls back to `line.order_id.project_id` — the direct Many2one on the parent order.

**Branch A — existing distribution present**: The line already has accounts from an Analytic Distribution Model (ADM) or a prior manual edit. The method extracts all account IDs from the JSON keys (splitting comma-separated strings), resolves them to `account.analytic.account` records, and reads their `root_plan_id`. Accounts from `project._get_analytic_accounts()` whose root plan is *not yet represented* are appended to each existing key.

Example: a line with `{account_A: 100}` from an ADM on Plan 1, and a project with accounts on Plan 2 and Plan 3, gets its distribution updated to `{account_A,project_account_plan2,project_account_plan3: 100}`. This preserves ADM-driven accounts while adding project accounts on new root plans. Note: if the ADM already assigned 100% to an account on the same root plan as a project account, the project account is silently skipped for that plan (the slot is taken).

**Branch B — no existing distribution**: `line.analytic_distribution = project._get_analytic_distribution()`. The project's default distribution is applied wholesale.

**Display type guard**: Section/note lines (`display_type` in `('line_section', 'line_note')`) are skipped — they carry no financial data and should not receive analytic accounts.

### `@api.model_create_multi` — Why It Is Necessary

The `@api.depends` on `_compute_analytic_distribution` only re-evaluates on **write** operations. When `super().create()` runs, `order_id` (and therefore `order_id.project_id`) may not yet be fully flushed to the database in the same transaction, so the ORM does not automatically trigger `_compute_analytic_distribution` after the initial create. Calling `lines._recompute_recordset(fnames=['analytic_distribution'])` explicitly forces re-computation of the dependent computed field on the newly created records, ensuring the project account is applied even in single-transaction PO creation flows.

---

## `project.project` — `models/project_project.py`

Extends `project.project` with purchase-order-related computed fields, action methods, dashboard integration, and profitability contribution.

### Computed Field: `purchase_orders_count`

```python
purchase_orders_count = fields.Integer(
    '# Purchase Orders',
    compute='_compute_purchase_orders_count',
    groups='purchase.group_purchase_user',
    export_string_translation=False,
)
```

Computed via two separate, mutually exclusive mechanisms and summed per project:

```python
def _compute_purchase_orders_count(self):
    # Mechanism 1: POs with project_id set directly (groupby yields project_id→[order_ids])
    purchase_orders_per_project = dict(
        self.env['purchase.order']._read_group(
            domain=[
                ('project_id', 'in', self.ids),
                ('order_line', '!=', False),
            ],
            groupby=['project_id'],
            aggregates=['id:array_agg'],
        )
    )
    # Mechanism 2: PO lines whose analytic_distribution keys contain project.account_id
    # Excludes POs already found by Mechanism 1 to prevent double-counting
    purchase_orders_count_per_project_from_lines = dict(
        self.env['purchase.order.line']._read_group(
            domain=[
                ('order_id', 'not in', [
                    order_id
                    for values in purchase_orders_per_project.values()
                    for order_id in values
                ]),
                ('analytic_distribution', 'in', self.account_id.ids),
            ],
            groupby=['analytic_distribution'],
            aggregates=['__count'],
        )
    )

    projects_no_account = self.filtered(lambda project: not project.account_id)
    for project in projects_no_account:
        # No analytic account: only direct project_id links qualify
        project.purchase_orders_count = len(purchase_orders_per_project.get(project, []))

    # Remap: Mechanism 1 results keyed by project_id → keyed by account_id
    purchase_orders_per_project = {
        project.account_id.id: len(orders)
        for project, orders in purchase_orders_per_project.items()
    }
    for project in (self - projects_no_account):
        project.purchase_orders_count = (
            purchase_orders_per_project.get(project.account_id.id, 0)
            + purchase_orders_count_per_project_from_lines.get(project.account_id.id, 0)
        )
```

**Mechanism 1 — Direct link**: Uses `_read_group` on `purchase.order` grouped by `project_id`, collecting order IDs per project. Only POs with at least one order line are counted.

**Mechanism 2 — Analytic match**: Uses `_read_group` on `purchase.order.line` with `analytic_distribution IN self.account_id.ids`. The `account_analytic_distribution` column is a PostgreSQL `jsonb`; the `IN` operator uses a GIN index when present, making this efficient even for large line tables. The domain explicitly excludes `order_id IN (mechanism1_order_ids)` to avoid double-counting POs that are both directly linked and whose lines also happen to match the analytic account.

**Projects without analytic accounts**: The `projects_no_account` branch handles the case where a project has no `account_id` set. Mechanism 2 cannot apply (no account IDs to match), so only direct `project_id` links are counted. If a project has no analytic account and no direct PO links, `purchase_orders_count` is zero — and no purchase section will appear in the profitability panel either.

**Performance**: Both mechanisms use `_read_group`, which executes a single SQL query per groupby with server-side aggregation. The result is a plain Python dict — no ORM `browse()` loop over project records.

---

## Actions

### `action_open_project_purchase_orders`

```python
def action_open_project_purchase_orders(self):
    purchase_orders = self.env['purchase.order.line'].search([
        '|',
            ('analytic_distribution', 'in', self.account_id.ids),
            ('order_id.project_id', '=', self.id),
    ]).order_id
```

Returns an `ir.actions.act_window` for `purchase.order` filtered to the found POs. Sets `default_project_id` in context so new POs opened from this view are pre-linked to the project.

**Single-record shortcut**: If exactly one PO is found and `from_embedded_action` is *not* in context, the action opens directly to the PO form view (no intermediate list). When opened via embedded action (the kanban tab or update panel), the list is always shown so users can switch between multiple POs.

**Embedded actions**: Two `ir.embedded.actions` records in `views/project_project.xml` register this method as a callable tab:

| Record ID | Parent Action | Purpose |
|---|---|---|
| `project_embedded_action_purchase_orders` | `project.act_project_project_2_project_task_all` | Adds "Purchase Orders" tab to the project task kanban view |
| `project_embedded_action_purchase_orders_dashboard` | `project.project_update_all_action` | Adds "Purchase Orders" section to the project update/dashboard panel |

Both are gated to `purchase.group_purchase_user`. Sequence 70 places them alongside other project sub-views (Tasks, Milestones, etc.).

### `action_profitability_items`

```python
def action_profitability_items(self, section_name, domain=None, res_id=False):
    if section_name == 'purchase_order':
        action = {
            'name': self.env._('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'context': {'create': False, 'edit': False},
        }
        if res_id:
            action['res_id'] = res_id
            action['views'] = `False, 'form'`
            action['view_mode'] = 'form'
        return action
    return super().action_profitability_items(section_name, domain, res_id)
```

Drill-down from the profitability panel. When called with a `domain` (many POs), opens a read-only list. When called with a `res_id` (single PO), opens directly to the form in read-only mode (`create: False, edit: False`), preventing users from modifying the PO from within the project profitability context.

---

## Profitability Integration

`project_purchase` contributes to the project cost structure through two mechanisms that must be understood together.

### `_add_purchase_items` — Override returning `False`

```python
def _add_purchase_items(self, profitability_items, with_action=True):
    return False
```

`project_account` defines this method as a stub that reads vendor bill lines with analytic distribution. Overriding to `False` disables that stub. The `_get_profitability_items` override in `project_purchase` handles confirmed PO lines directly, while vendor bills without a PO link are handled by `project_account._add_purchase_items` on a domain that explicitly excludes `purchase_line_id`-bearing lines.

### `_get_profitability_aal_domain` — Excluding PO-derived AALs

```python
def _get_profitability_aal_domain(self):
    return Domain.AND([
        super()._get_profitability_aal_domain(),
        ['|', ('move_line_id', '=', False), ('move_line_id.purchase_line_id', '=', False)],
    ])
```

This filter is applied to the `account.analytic.line` records used by `project_account`'s `other_costs_aal` section. By adding the clause `('move_line_id.purchase_line_id', '=', False)`, any analytic line that was generated from a confirmed PO's receipt (which carries a `purchase_line_id` on its move lines) is excluded from the AAL-based cost computation. This prevents the same purchase cost from being counted twice: once via the `purchase_order` section (directly from PO lines) and once via `other_costs_aal` (from the derived analytic lines).

### Section 1: `purchase_order` (sequence 10)

Tracks confirmed purchase order lines with analytic distribution matching the project account.

```python
def _get_profitability_items(self, with_action=True):
    profitability_items = super()._get_profitability_items(with_action)
    if self.account_id:
        purchase_lines = self.env['purchase.order.line'].sudo().search([
            ('analytic_distribution', 'in', self.account_id.ids),
            ('state', 'in', 'purchase')  # confirmed POs only
        ])
        purchase_order_line_invoice_line_ids = self._get_already_included_profitability_invoice_line_ids()
        with_action = with_action and (
            self.env.user.has_group('purchase.group_purchase_user')
            or self.env.user.has_group('account.group_account_invoice')
            or self.env.user.has_group('account.group_account_readonly')
        )
        if purchase_lines:
            amount_invoiced = amount_to_invoice = 0.0
            purchase_order_line_invoice_line_ids.extend(purchase_lines.invoice_lines.ids)
            for purchase_line in purchase_lines:
                # Convert to project company currency
                price_subtotal = purchase_line.currency_id._convert(
                    purchase_line.price_subtotal, self.currency_id, self.company_id
                )
                # Proportional contribution of this project account
                analytic_contribution = sum(
                    percentage
                    for ids, percentage in purchase_line.analytic_distribution.items()
                    if str(self.account_id.id) in ids.split(',')
                ) / 100.
                purchase_line_amount_to_invoice = price_subtotal * analytic_contribution

                # Reconcile against vendor bills derived from this PO line
                invoice_lines = purchase_line.invoice_lines.filtered(
                    lambda l:
                        l.parent_state != 'cancel'
                        and l.analytic_distribution
                        and any(
                            key == str(self.account_id.id)
                            or key.startswith(str(self.account_id.id) + ",")
                            for key in l.analytic_distribution
                        )
                )
                if invoice_lines:
                    invoiced_qty = sum(invoice_lines.filtered(lambda l: not l.is_refund).mapped('quantity'))
                    if invoiced_qty < purchase_line.product_qty:
                        amount_to_invoice -= purchase_line_amount_to_invoice * (
                            (purchase_line.product_qty - invoiced_qty) / purchase_line.product_qty
                        )
                    for line in invoice_lines:
                        # ... redistribute billed vs to_bill by invoice state ...
                else:
                    amount_to_invoice -= purchase_line_amount_to_invoice

            # Append to costs dict
            costs['data'].append({
                'id': 'purchase_order',
                'sequence': 10,
                'billed': amount_invoiced,
                'to_bill': amount_to_invoice,
                'action': {...} if with_action else None,
            })
            costs['total']['billed'] += amount_invoiced
            costs['total']['to_bill'] += amount_to_invoice

        # Vendor bills WITHOUT a PO line link → other_purchase_costs
        self._get_costs_items_from_purchase(domain, profitability_items, with_action=with_action)
    return profitability_items
```

**States tracked**: Only `state = 'purchase'` (confirmed). `draft` and `sent` RFQs are excluded; `done` lines (locked) are included but typically have no remaining balance.

**Analytic contribution ratio**: When `analytic_distribution` contains multiple accounts (e.g., `{account_1: 60, account_2: 40}` or cross-plan `{account_1,account_2: 100}`), only the sum of percentages where `account_id.id` appears in the key is counted. For a single-account line at 100%, this equals the full `price_subtotal`. For a 60/40 split, only 60% of the cost flows to the project.

**Invoice reconciliation logic**:

1. `amount_to_invoice` starts as the full `price_subtotal * contribution_ratio`.
2. If there are invoice lines linked to this PO line, compute `invoiced_qty`.
3. If `invoiced_qty < product_qty`, only the uninvoiced portion remains in `to_bill`.
4. Each invoice line is then re-processed: if `parent_state == 'posted'` it flows to `amount_invoiced`; if draft it flows to `amount_to_invoice`. This means partially invoiced POs can have costs split across both columns simultaneously.

**`sudo()` usage**: `self.env['purchase.order.line'].sudo()` bypasses record rules on `purchase.order.line`. In typical deployments, `purchase` manages its own access via `group_purchase_user`. In multi-company or locked-down deployments, verify that `sudo()` does not expose lines the current user should not see.

**Currency conversion**: `currency_id._convert(price_subtotal, self.currency_id, self.company_id)` uses the company's currency as the target. For foreign-currency POs, this applies the current active rate — not the historical rate at PO confirmation. For long-running projects, this can cause the profitability total to drift from the original transaction value.

**`with_action` guard**: The drill-down action is only attached when the user has `purchase.group_purchase_user` OR `account.group_account_invoice` OR `account.group_account_readonly`. Users who can only see project costs (e.g., project managers without purchase rights) see the amounts but cannot open the PO list.

### Section 2: `other_purchase_costs`

Handled by `project_account._add_purchase_items`, called at the end of `project_purchase._get_profitability_items`. The domain is:

```python
domain = [
    ('move_id.move_type', 'in', ['in_invoice', 'in_refund']),
    ('parent_state', 'in', ['draft', 'posted']),
    ('price_subtotal', '!=', 0),
    ('id', 'not in', purchase_order_line_invoice_line_ids),
]
```

This reads vendor bills (account moves of type `in_invoice`/`in_refund`) that have analytic distribution but are **not** linked to a confirmed PO line. The `purchase_order_line_invoice_line_ids` exclusion prevents re-counting vendor bills that were generated from POs tracked in the `purchase_order` section above.

---

## Project Dashboard Button

```python
def _get_stat_buttons(self):
    buttons = super()._get_stat_buttons()
    if self.env.user.has_group('purchase.group_purchase_user'):
        buttons.append({
            'icon': 'credit-card',
            'text': self.env._('Purchase Orders'),
            'number': self.purchase_orders_count,
            'action_type': 'object',
            'action': 'action_open_project_purchase_orders',
            'show': self.purchase_orders_count > 0,
            'sequence': 36,
        })
    return buttons
```

Renders a "Purchase Orders" smart button on the project form with a `credit-card` icon. Hidden when `purchase_orders_count == 0` (no purchase data yet). Sequence 36 places it after "Tasks" and "Milestones" in the stat button row.

---

## Product Catalog Controller — `controllers/catalog.py`

```python
class ProjectPurchaseCatalogController(ProductCatalogController):

    @route()
    def product_catalog_update_order_line_info(
        self, res_model, order_id, product_id, quantity=0, **kwargs
    ):
        if (project_id := kwargs.get('project_id')):
            request.update_context(project_id=project_id)
        return super().product_catalog_update_order_line_info(
            res_model, order_id, product_id, quantity, **kwargs
        )
```

Extends the `product_catalog_update_order_line_info` route (from `product.controllers.catalog.ProductCatalogController`). When a user adds a product from the project-scoped product catalog (available inside the Project app when `purchase` is installed), the HTTP request carries `project_id` as a kwarg. The override forwards it into the request context via `request.update_context(project_id=project_id)`. The `purchase.order.line`'s `_compute_analytic_distribution` then reads `self.env.context.get('project_id')` to auto-populate the project's analytic distribution on the new line before the PO is saved. This creates a seamless "add to PO" experience within the project context without requiring the user to manually set the project or analytic account.

---

## Demo Data — `data/project_purchase_demo.xml`

Demo data is tagged `noupdate="1"` — installed on first module setup, then preserved on subsequent upgrades.

Creates:
- Three products (Cement, Sand, Bricks) under `product.product_category_construction` with standard costs
- One draft `purchase.order` (no `project_id` set — not automatically linked to the construction demo project)
- Three PO lines, each with `analytic_distribution = {project.analytic_construction: 100}` — linked to the construction project's analytic account

The demo PO is in `draft` state, so it does not appear in profitability until confirmed. This provides a realistic starting state where a project manager can review the pending purchase before locking it in.

---

## Test Coverage

All tests are post-install (`-at_install` excluded) and live in `tests/`.

### `tests/test_project_profitability.py` — `TestProjectPurchaseProfitability`

Inherits from `TestProjectProfitabilityCommon` (project base), `TestPurchaseToInvoiceCommon` (PO→invoice flow), and `AccountTestInvoicingCommon` (currency/company setup).

| Test | What It Validates |
|---|---|
| `test_bills_without_purchase_order_are_accounted_in_profitability_project_purchase` | Draft bills → `other_purchase_costs.to_bill`; confirmed PO → `purchase_order.to_bill`; PO invoice created (draft) → still in `purchase_order.to_bill`; PO invoice posted → moves to `purchase_order.billed`. The `purchase_order` and `other_purchase_costs` sections are mutually exclusive for PO-derived bills. |
| `test_account_analytic_distribution_ratio` | A line with `{project_account: 60, other_account: 40}` at 100% line distribution: only 60% of `price_subtotal` appears in profitability. |
| `test_multi_currency_for_project_purchase_profitability` | Foreign-currency PO lines and vendor bills are converted to the project company currency at the current rate. Validates that `to_bill` and `billed` amounts reflect converted values. |
| `test_project_purchase_order_smart_button` | With one PO linked via `project_id`, `action_open_project_purchase_orders` returns `res_id` pointing directly to the form. |
| `test_analytic_distribution_with_included_tax` | Profitability uses `amount_untaxed` of the PO, not the tax-included amount. Same for vendor bills. |
| `test_analytic_distribution_with_mismatched_uom` | Changing `product_uom_id` on a confirmed PO line (e.g., to dozens) does not produce an incorrect profitability total — the `price_subtotal` already reflects the UoM conversion. |
| `test_cross_analytics_contribution` | A multi-plan key like `{project_account_id,cross_account_id: 42}` correctly computes the contribution ratio as 42% (the full key weight), not twice 42%. |
| `test_vendor_credit_note_profitability` | A reversed vendor bill moves the posted cost back to `to_bill` (draft reversal); posting the reversal moves it out of `billed` entirely. Confirms credit notes net to zero when fully processed. |
| `test_project_purchase_profitability_without_analytic_distribution` | When a vendor bill line has its `analytic_distribution` manually cleared after creation, the confirmed PO line still drives the `purchase_order` section — the cleared invoice line does not prevent counting. |

### `tests/test_project_purchase.py` — `TestProjectPurchase`

| Test | What It Validates |
|---|---|
| `test_project_on_pol_with_analytic_distribution_model` | Assigning `project_id` to a PO that already has ADM-applied distribution: project accounts on *new* root plans are appended; accounts on already-represented root plans are skipped. Validates that both the ADM account and the project account coexist in the distribution. |
| `test_compute_purchase_orders_count` | 3 POs: 1 via direct link, 2 via analytic distribution match → count = 3. Projects without analytic accounts only count direct links. |

---

## L4 Edge Cases and Failure Modes

### 1. PO confirmed before project is set

If a user confirms a PO and then sets `project_id`, `_compute_analytic_distribution` fires (the `order_id.project_id` dependency detects the write) but the PO is already in `purchase` state. The line's `analytic_distribution` may now be populated or updated, and profitability will correctly pick up the confirmed line — but only if the distribution was actually recomputed. Since `_compute_analytic_distribution` is not decorated with `@api.constrains`, it does not block the state transition. In practice, the distribution should be set before confirmation for auditability.

### 2. Multi-plan analytic distributions and plan collision

The `analytic_distribution` JSON field stores keys as comma-separated account ID strings: `{"12,34": 100}`. The code splits on `,` throughout, which works correctly for single-plan keys. For cross-plan keys (`"12,34: 100"` where 12 is on Plan A and 34 is on Plan B), the split produces both IDs, and `root_plan_id` deduplication correctly prevents adding a second Plan-A project account when one from Plan A is already present. However, if an ADM already assigned 100% of a line to a Plan-A account, the project account on the same plan is silently ignored — the full 100% slot is consumed.

### 3. Projects without an analytic account

`purchase_orders_count` falls back to direct `project_id` links only for projects with no `account_id`. The profitability method has an explicit `if self.account_id:` guard — if the project has no analytic account, **no** `purchase_order` section appears at all, and `other_purchase_costs` also cannot match (no account to match). This means a project created without "analytic accounting" enabled will not show any purchase costs, even if POs are linked to it. The workaround is to create an analytic account for the project (via `project_account`'s `_create_analytic_account()`) before linking purchases.

### 4. Currency conversion timing

`_get_profitability_items` converts all amounts to the project company's currency at **computation time** (when the project form is opened), not at the time of PO creation. For long-running projects with foreign-currency POs, the profitability panel will reflect current exchange rates. Past performance reports may differ from what was actually recorded at the time of purchase.

### 5. Vendor bill lines without `purchase_line_id`

`project_account._add_purchase_items` counts vendor bills that have `analytic_distribution` matching the project account but lack a `purchase_line_id`. This handles the case of manually entered vendor bills (not generated from a PO) that reference the project analytically. Since these have no PO link, they appear in `other_purchase_costs` separately from the `purchase_order` section. Both sections can appear simultaneously in the same project.

### 6. Credit notes and partial reversals

The profitability logic uses `parent_state` to determine billed vs. to_bill: `posted` credit notes flow to `billed` with a negative sign (reducing total cost); draft credit notes flow to `to_bill`. A fully reversed posted bill nets to zero in profitability. Partial reversals proportionally reduce the billed amount.

### 7. `sudo()` in multi-company/multi-record-rule environments

`self.env['purchase.order.line'].sudo()` bypasses record rules for purchase order lines. In deployments with custom record rules on `purchase.order.line` (e.g., restricting visibility by company or purchase team), this can expose lines that should not be visible. The `sudo()` is necessary to aggregate costs across all companies for the project profitability panel, but it should be reviewed in strict multi-company setups.

---

## Cross-Module Flow Diagram

```
project.project
  │
  ├─ purchase_orders_count
  │     Mechanism 1: purchase.order.project_id IN self.ids
  │     Mechanism 2: purchase.order.line.analytic_distribution IN self.account_id.ids
  │                   (excludes POs already counted via Mechanism 1)
  │
  ├─ action_open_project_purchase_orders()
  │     → ir.actions.act_window (purchase.order)
  │     → domain: PO IDs from lines matching project account OR project_id link
  │     → context: default_project_id
  │
  ├─ _get_stat_buttons()  + Purchase Orders button (sequence 36, icon: credit-card)
  │
  ├─ _get_profitability_aal_domain()  + filter: exclude AALs from PO receipts
  │
  └─ _get_profitability_items()
        ├─ purchase_order section (sequence 10)
        │     Source: purchase.order.line (state='purchase', analytic_distribution match)
        │     Billed: posted vendor bill lines derived from PO
        │     To Bill: confirmed but uninvoiced qty + draft vendor bills
        │     Action: opens purchase.order list/form (read-only if no purchase rights)
        │
        └─ other_purchase_costs section
              Source: account.move.line (in_invoice/in_refund, no purchase_line_id)
              Delegated to: project_account._add_purchase_items()

purchase.order
  └─ project_id  (domain: is_template=False, groups: project.group_project_user)

purchase.order.line
  └─ _compute_analytic_distribution()
        ├─ Reads project_id from context (catalog controller) OR order_id.project_id
        ├─ If existing distribution: append project accounts on new root plans
        └─ If no distribution: apply project._get_analytic_distribution()
  └─ @api.model_create_multi → _recompute_recordset(['analytic_distribution'])

catalog controller (http route)
  └─ product_catalog_update_order_line_info()
        → request.update_context(project_id=...)
        → triggers _compute_analytic_distribution on new line via context
```

---

## Related Modules

| Module | Relationship |
|---|---|
| `project_account` | Hard dependency; provides analytic account infrastructure, profitability base, `other_purchase_costs` |
| `purchase` | Hard dependency; provides PO model, workflow, `group_purchase_user` |
| `project_purchase_stock` | Extends this module; adds automatic PO creation from task "Record Negative" (procurement flow) |
| `purchase_requisition` | Purchase agreements that can be linked to projects via analytic distribution |
| `sale_purchase_project` | Bidirectional links between sale orders and purchase orders via project |

## Summary

`project_purchase` is a lean integration module that links purchase orders to projects through two channels: a direct `project_id` Many2one on `purchase.order`, and automatic propagation of the project's analytic account onto purchase order lines. It contributes two cost sections to the project profitability panel (`purchase_order` for confirmed PO lines, `other_purchase_costs` for manual vendor bills), and surfaces purchase data through dashboard smart buttons and embedded action tabs. Its core value is closing the loop between project planning (tasks, milestones) and project procurement (purchase orders, vendor bills).
