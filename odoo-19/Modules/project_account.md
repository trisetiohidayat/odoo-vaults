---
type: module
module: project_account
tags: [odoo, odoo19, project, account, profitability, analytic, vendor-bill]
created: 2026-04-06
updated: 2026-04-11
---

# Project - Account

## Overview

| Property | Value |
|----------|-------|
| Category | Accounting/Accounting |
| Depends | `account`, `project` |
| Author | Odoo S.A. |
| License | LGPL-3 |
| Auto-install | True |

## Description

The `project_account` module is the foundational accounting bridge for project profitability. It links projects to analytic accounts and computes cost and revenue sections from:

1. **Vendor bills** (without purchase orders) flowing through analytic distribution
2. **Other costs and revenues** from `account.analytic.line` records not tied to move lines

It provides the core profitability data structures that higher-level modules like `sale_timesheet` extend with their own billing-specific sections.

**Auto-install behavior**: Because `auto_install: True`, this module is installed automatically when both `account` and `project` are present. This means every Odoo 19 installation with projects and accounting gets project profitability by default.

## Module Dependency Chain

```
project_account
  ├── project (provides project.project, project.task)
  └── account (provides account.move.line, analytic distribution)

Higher layers extending project_account:
  sale_project     → _add_purchase_items() overridden to False; still calls _get_costs_items_from_purchase()
  project_purchase → _add_purchase_items() fully overridden with PO + vendor bill logic
  sale_timesheet   → extends profitability with timesheet billing sections
```

## Core Concept: Analytic Distribution

Project costs and revenues flow through **analytic distribution** on account move lines. When a vendor bill (or other invoice) is posted, its `analytic_distribution` field maps amounts to one or more analytic accounts via a JSON dictionary: `{account_id_str: percentage, ...}`. If a line's distribution includes the project's analytic account, that amount contributes to the project's profitability.

```
vendor_bill.post()
    │
    ▼
account.move.line records
  - balance (positive = debit, negative = credit)
  - analytic_distribution: {"123": 50.0, "456": 50.0}  # 50% each to two accounts
  - move_id (links to vendor bill)
    │
    ▼
For each line with project's analytic account:
  - amount contributed = balance * sum_of_matching_percentages / 100
  - If move.state == 'posted' → categorized as 'billed'
  - If move.state == 'draft'  → categorized as 'to_bill'
```

### Analytic Distribution Key Format

The `analytic_distribution` field stores account IDs as **string keys** (not integers). The value is the percentage (float). When multiple lines in an analytic distribution reference the same account, the percentages are summed:

```python
# From move line's analytic_distribution:
# {"123": 50.0, "789": 25.0, "789,456": 25.0}
# Project account ID = 789
# Matching keys: "789" → 25.0, "789,456" → 25.0
# Contribution: 50.0 / 100 = 0.5
analytic_contribution = sum(
    percentage
    for ids, percentage in move_line.analytic_distribution.items()
    if str(self.account_id.id) in ids.split(',')
) / 100.
```

This handles the split-distribution case where an account appears with different partners (e.g., "789" standalone and "789,456" with a partner).

## How Costs Flow Into the Project

### 1. Vendor Bills Without Purchase Orders

The module computes costs from vendor bills (`in_invoice`, `in_refund`) that reference the project's analytic account but are **not** linked to a purchase order. (Purchase order-linked bills are handled by `project_purchase`.)

```python
def _get_add_purchase_items_domain(self):
    purchase_line_ids = self._get_already_included_profitability_invoice_line_ids()
    return [
        ('move_type', 'in', ['in_invoice', 'in_refund']),
        ('parent_state', 'in', ['draft', 'posted']),
        ('price_subtotal', '>', 0),
        ('id', 'not in', purchase_line_ids),  # exclude lines already in PO profitability
    ]
```

The domain includes `price_subtotal > 0` to exclude zero-amount lines (which can arise from credit notes or credit memo reversals that cancel out but still exist in the ledger).

### 2. Analytic Line Processing (`_get_costs_items_from_purchase`)

The `_get_costs_items_from_purchase()` method is the shared core used by both `sale_project` and `project_purchase`. It reads all `account.move.line` records matching the domain, then:

1. Filters lines whose `analytic_distribution` contains the project's analytic account
2. Computes the **analytic contribution**: for each line, sums the percentage points where the project account appears
3. Converts line `balance` to project currency using the line's `date` (historical rate)
4. Distributes into `billed` (posted) or `to_bill` (draft) based on `parent_state`

```python
def _get_costs_items_from_purchase(self, domain, profitability_items, with_action=True):
    account_move_lines = self.env['account.move.line'].sudo().search_fetch(
        domain + [('analytic_distribution', 'in', self.account_id.ids)],
        ['balance', 'parent_state', 'company_currency_id', 'analytic_distribution', 'move_id', 'date'],
    )
    if account_move_lines:
        amount_invoiced = amount_to_invoice = 0.0
        for move_line in account_move_lines:
            line_balance = move_line.company_currency_id._convert(
                from_amount=move_line.balance,
                to_currency=self.currency_id,
                date=move_line.date,          # historical rate on move date
            )
            analytic_contribution = sum(
                percentage
                for ids, percentage in move_line.analytic_distribution.items()
                if str(self.account_id.id) in ids.split(',')
            ) / 100.

            if move_line.parent_state == 'draft':
                amount_to_invoice -= line_balance * analytic_contribution   # 'to_bill'
            else:  # posted
                amount_invoiced -= line_balance * analytic_contribution       # 'billed'
```

**Currency conversion with line date**: The conversion uses `move_line.date` (the move's accounting date), not the current date. This ensures that exchange rates match the period in which the expense was recorded, which is critical for accurate historical reporting.

**Sign convention**: Amounts are negated (`-=`) because vendor bill lines typically have negative balances (credits from the company's perspective). The final section only appears if both `amount_invoiced != 0 or amount_to_invoice != 0`, meaning bills fully offset by vendor credits will be hidden.

### 3. Other Costs and Revenues (Non-Timesheet AAL)

The `_get_items_from_aal()` method handles `account.analytic.line` records that are **not** linked to a move line (`move_line_id = False`). This captures costs/revenues recorded directly in the analytic account:

```python
def _get_domain_aal_with_no_move_line(self):
    # sale_timesheet extends this with ('project_id', '=', False)
    return [('account_id', '=', self.account_id.id), ('move_line_id', '=', False)]

def _get_items_from_aal(self, with_action=True):
    domain = Domain.AND([
        self._get_domain_aal_with_no_move_line(),
        Domain('category', 'not in', ['manufacturing_order', 'picking_entry']),
    ])
    aal_other_search = self.env['account.analytic.line'].sudo().search_read(
        domain, ['id', 'amount', 'currency_id']
    )
    # ...
```

**Excluded categories**: AAL records with `category = 'manufacturing_order'` (from `mrp`) or `category = 'picking_entry'` (from `stock`) are excluded. These are automatically generated by manufacturing and inventory operations and belong to their own cost/profitability sections in those modules.

**Important limitation — to_bill/to_invoice always zero**: Comment in source explicitly states: "we dont know what part of the numbers has already been billed or not, so we have no choice but to put everything under the billed/invoiced columns. The to bill/to invoice ones will simply remain 0." This is a known design limitation: AAL-based profitability only shows already-billed amounts, never pending-to-bill.

**Multi-company AAL handling**: When AAL records belong to different companies than the project, amounts are aggregated per currency using a `defaultdict`, then each currency is converted to the project's currency individually. The test suite (`test_project_profitability.py`) verifies this with a foreign company currency scenario.

## Profitability Structure

### Profitability Sections Added by `project_account`

| Section ID | Label | Sequence | Category | Column |
|-----------|-------|----------|----------|--------|
| `other_purchase_costs` | Vendor Bills | 11 | Costs | billed / to_bill |
| `other_revenues_aal` | Other Revenues | 14 | Revenues | invoiced / to_invoice |
| `other_costs_aal` | Other Costs | 15 | Costs | billed / to_bill |

For reference, the base `project` module provides: `other_revenues` (seq 13), `other_costs` (seq 16). Sequence gaps at 11, 14, 15 are intentionally reserved for `project_account` additions.

### Section Ordering and Sorting

Sections are sorted by their `sequence` value at render time in `_get_profitability_values()`:

```python
profitability_items['revenues']['data'] = sorted(
    profitability_items['revenues']['data'], key=lambda k: k['sequence']
)
profitability_items['costs']['data'] = sorted(
    profitability_items['costs']['data'], key=lambda k: k['sequence']
)
```

### Action Handling per Section

```python
def action_profitability_items(self, section_name, domain=None, res_id=False):
    if section_name in ['other_revenues_aal', 'other_costs_aal', 'other_costs']:
        # Opens account.analytic.line list in pivot/graph view
        action = self.env["ir.actions.actions"]._for_xml_id(
            "analytic.account_analytic_line_action_entries"
        )
        action['context'] = {'group_by_date': True}
        # Replace list view with pivot/graph views if no res_id
        pivot_view_id = self.env['ir.model.data']._xmlid_to_res_id(
            'project_account.project_view_account_analytic_line_pivot'
        )
        graph_view_id = self.env['ir.model.data']._xmlid_to_res_id(
            'project_account.project_view_account_analytic_line_graph'
        )
        action['views'] = [
            (pivot_view_id, 'pivot') if view_type == 'pivot'
            else (graph_view_id, 'graph') if view_type == 'graph'
            else (view_id, view_type)
            for (view_id, view_type) in action['views']
        ]
        return action

    if section_name == 'other_purchase_costs':
        # Opens vendor bills (in_invoice type)
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_in_invoice_type"
        )
        action['domain'] = domain or []
        return action

    return super().action_profitability_items(section_name, domain, res_id)
```

**Single-record drill-down**: When `res_id` is provided (single record), the action opens in form view instead of list/pivot/graph.

## Project-Analytic Account Relationship

Every billable project has an **analytic account** (via `account_id` on `project.project`, created via `_create_analytic_account()` in the base `project` module). All costs and revenues for the project flow through this account.

```
project.project
  └── account_id → account.analytic.account
                       │
                       ├── account.analytic.line (timesheets via hr_timesheet, manual entries)
                       └── account.move.line (via analytic_distribution on vendor bills)
```

The module overrides `_get_domain_aal_with_no_move_line()` to return only AAL records linked to this project's analytic account, excluding timesheet lines (which are handled by `hr_timesheet` / `sale_timesheet`):

```python
def _get_domain_aal_with_no_move_line(self):
    # sale_timesheet adds ('project_id', '=', False) here, so we can't put it in project_account
    return [('account_id', '=', self.account_id.id), ('move_line_id', '=', False)]
```

The comment explicitly notes why `('project_id', '=', False)` is **not** added here: `sale_timesheet` needs to extend this domain, so the condition must live in the downstream module. This is a critical design decision that allows proper method overriding.

## Odoo 19 Web Panel: Embedded Actions

The module registers two **embedded actions** that appear in the Odoo 19 web project's action panel (right sidebar):

### Embedded Action: Analytic Items (from project form)

```xml
<record id="project_embedded_action_analytic_items" model="ir.embedded.actions">
    <field name="parent_res_model">project.project</field>
    <field name="sequence">105</field>
    <field name="name">Analytic Items</field>
    <field name="parent_action_id" ref="project.act_project_project_2_project_task_all"/>
    <field name="python_method">action_open_analytic_items</field>
    <field name="context">{"from_embedded_action": true}</field>
    <field name="groups_ids" eval="[(4, ref('analytic.group_analytic_accounting'))]" />
    <field name="domain">[('account_id', '!=', False)]</field>
</record>
```

- **Sequence 105**: Appears after the standard project task actions
- **Groups restriction**: Only visible to users with `analytic.group_analytic_accounting` — non-accounting users see neither the button nor the analytic items profitability sections
- **Domain filter**: Only shown when the project has an analytic account (`account_id != False`)
- **Parent action**: Attached to the "Tasks" main action (`act_project_project_2_project_task_all`)
- **Context flag**: `from_embedded_action: true` passed to `action_open_analytic_items()` to signal it came from the web panel

### Embedded Action: From Project Update Dashboard

```xml
<record id="project_embedded_action_analytic_items_dashboard" model="ir.embedded.actions">
    <field name="parent_res_model">project.project</field>
    <field name="sequence">105</field>
    <field name="name">Analytic Items</field>
    <field name="parent_action_id" ref="project.project_update_all_action"/>
    <field name="python_method">action_open_analytic_items</field>
    <field name="context">{"from_embedded_action": true}</field>
    <field name="groups_ids" eval="[(4, ref('analytic.group_analytic_accounting'))]" />
    <field name="domain">[('account_id', '!=', False)]</field>
</record>
```

Same action, but attached to the project update/status bar dashboard (`project.project_update_all_action`). This enables the "Analytic Items" button from both the task list view and the project update panel.

### `action_open_analytic_items` Implementation

```python
def action_open_analytic_items(self):
    action = self.env['ir.actions.act_window']._for_xml_id(
        'analytic.account_analytic_line_action_entries'
    )
    action['domain'] = [('account_id', '=', self.account_id.id)]
    context = literal_eval(action['context'])
    action['context'] = {
        **context,
        'create': self.env.context.get('from_embedded_action', False),
        'default_account_id': self.account_id.id,
    }
    return action
```

- **Domain**: Filters to the project's analytic account only
- **Create permission**: `create: from_embedded_action` — allows creating new analytic lines directly from the panel when triggered from the embedded action
- **Default account**: Pre-fills `default_account_id` so new lines automatically link to the project's analytic account

## Currency and Multi-Company Handling

### Vendor Bill Currency Conversion

Vendor bill amounts are converted from the line's `company_currency_id` (the vendor bill's currency) to the project's `currency_id` (the project's company currency) using the line's **accounting date** (`move_line.date`), not the current date:

```python
line_balance = move_line.company_currency_id._convert(
    from_amount=move_line.balance,
    to_currency=self.currency_id,
    date=move_line.date,  # historical date ensures correct historical rate
)
```

**Edge case**: If the vendor bill is in a foreign currency, `company_currency_id` is the **company's** currency, not the invoice's foreign currency. The `balance` field is already expressed in company currency (after the automatic currency conversion in Odoo's `account.move.line`). Therefore the conversion handles the case where the vendor bill's company is different from the project's company.

### AAL Currency Conversion

AAL records can belong to different companies with different currencies. The module aggregates by `currency_id`, then converts each group to the project's currency:

```python
dict_amount_per_currency_id = defaultdict(
    lambda: {'costs': 0.0, 'revenues': 0.0}
)
set_currency_ids = {self.currency_id.id}

for aal in aal_other_search:
    set_currency_ids.add(aal['currency_id'][0])
    aal_amount = aal['amount']
    if aal_amount < 0.0:
        dict_amount_per_currency_id[aal['currency_id'][0]]['costs'] += aal_amount
    else:
        dict_amount_per_currency_id[aal['currency_id'][0]]['revenues'] += aal_amount

for currency_id, dict_amounts in dict_amount_per_currency_id.items():
    currency = self.env['res.currency'].browse(currency_id).with_prefetch(dict_amount_per_currency_id)
    total_revenues += currency._convert(dict_amounts['revenues'], self.currency_id, self.company_id)
    total_costs += currency._convert(dict_amounts['costs'], self.currency_id, self.company_id)
```

The `with_prefetch(dict_amount_per_currency_id)` optimizes the browse context to prefetch only the currencies being converted, avoiding a full currency table load.

### Project Currency

Project currency defaults to `company_id.currency_id` (set on `project.project` in the `project` module). When `with_action=False` is passed (as in `_get_profitability_values()`), the system uses the account's currency instead of the project's.

## Security Model and Access Control

### Group-Based Feature Gating

Three group checks gate different aspects of the profitability display:

| Check | Groups Required | Effect |
|-------|----------------|--------|
| `_add_purchase_items` | `account.group_account_invoice` OR `account.group_account_readonly` | Whether vendor bills section appears |
| `_get_items_from_aal` action | `account.group_account_readonly` | Whether clickable action is added to AAL sections |
| Embedded actions | `analytic.group_analytic_accounting` | Whether "Analytic Items" button appears in web panel |

**L4 Security Consideration**: Users without `analytic.group_analytic_accounting` see neither the embedded "Analytic Items" button nor the profitability sections derived from analytic account data. However, the raw data (AAL records, vendor bills) may still be accessible through other menus depending on their access rights. The profitability section itself is hidden at the UI level but underlying records remain queryable via direct record rules.

### `sudo()` Usage

Both `_get_costs_items_from_purchase` and `_get_items_from_aal` use `.sudo()` to bypass record-level ACLs when reading data:

```python
account_move_lines = self.env['account.move.line'].sudo().search_fetch(...)
aal_other_search = self.env['account.analytic.line'].sudo().search_read(...)
```

This allows project managers to see profitability data even when they lack direct read access to individual vendor bills or analytic lines, relying instead on the analytic account's access rights. **L4 Risk**: If a user has project access but not invoice access, `sudo()` silently bypasses invoice-level security. The `group_account_readonly` check provides a soft gate but does not prevent data visibility for authorized group members.

## Performance Considerations

### `sudo()` + `search_fetch` Pattern

```python
account_move_lines = self.env['account.move.line'].sudo().search_fetch(
    domain + [('analytic_distribution', 'in', self.account_id.ids)],
    ['balance', 'parent_state', 'company_currency_id', 'analytic_distribution', 'move_id', 'date'],
)
```

`search_fetch` (Odoo 16+) fetches only the specified fields in a single query, avoiding the overhead of reading all fields from the `account.move.line` table. Combined with `sudo()`, this is optimized for bulk profitability computation.

### Currency Conversion in Loops

For vendor bills: a single conversion per move line using the line's date.

For AAL: grouped by currency to minimize conversion calls — only one conversion per distinct `currency_id` rather than per AAL record. The `defaultdict` pattern collects amounts by currency first, then converts in a second pass.

### N+1 Risk in Action Generation

```python
if with_action:
    bills_costs['action'] = self._get_action_for_profitability_section(
        account_move_lines.move_id.ids,  # reads move_id for each line
        section_id
    )
```

`account_move_lines.move_id.ids` triggers a prefetch of the `move_id` relation across all lines. This is acceptable at current scale but could degrade on projects with hundreds of vendor bill lines.

### Domain Index Efficiency

The `analytic_distribution` field uses a JSON/PostgreSQL GIN index in Odoo 19. The query `('analytic_distribution', 'in', self.account_id.ids)` can leverage this index when the analytic account IDs are cast to strings (the JSON key format). The `account_id` field on `account.analytic.line` is a standard integer Many2one with a btree index.

## Edge Cases and Known Behaviors

### 1. Zero-balance Lines Excluded

The domain `('price_subtotal', '>', 0)` excludes lines with zero amount. However, lines from partially-reversed invoices may have small non-zero amounts that still appear.

### 2. Credit Notes (in_refund) Included

Both `in_invoice` and `in_refund` types are included, so vendor credit memos appear in the vendor bills section with negative contributions (reducing the total cost).

### 3. Draft Vendor Bills Classified as "to_bill"

Draft invoices (`parent_state = 'draft'`) are placed in the `to_bill` column, not `billed`. Only posted invoices reach `billed`. This aligns with the general accounting principle that unrecognized liabilities should not appear as realized costs.

### 4. AAL Without Move Line → Always "Billed/Invoiced"

As noted above, AAL-derived sections never show `to_bill`/`to_invoice` amounts because there is no billing lifecycle state tracked on plain AAL records. All AAL amounts land in the `billed`/`invoiced` columns.

### 5. Sub-account Matching in Analytic Distribution

The split-`','`-check for analytic distribution keys handles the case where a distribution key includes the project account as part of a multi-account split. For example, key `"789,456"` matches project account ID 789 via `str(789) in "789,456".split(',')` → `True`. This is necessary because `analytic_distribution` stores combined account keys as comma-separated IDs.

### 6. Overlapping Sections with `sale_timesheet`

When `sale_timesheet` is installed, the override of `_get_domain_aal_with_no_move_line()` adds `('project_id', '=', False)` to exclude timesheet-generated AALs from the generic "Other Costs/Revenues" section. These timesheet AALs are instead routed to timesheet-specific billing sections (billable_fixed, billable_time, etc.).

### 7. `other_costs_aal` Billed Value is Negative

The `billed` value for `other_costs_aal` is negative (negative AAL amount = cost). The test assertion:
```python
'billed': -30.0
```
confirms that negative costs are stored as negative numbers in the `billed` column, not converted to positive amounts.

## Data Flow Summary

```
Vendor Bill Created (not linked to PO)
    │
    ▼
account.move.line records created
  - Has analytic_distribution pointing to project.account_id
    │
    ▼
project._get_profitability_items() called
    │
    ├─► sale_project._add_purchase_items() → False (skipped)
    │     └─► project_purchase._add_purchase_items() [when project_purchase installed]
    │           ├─► Computes PO costs from purchase.order.line
    │           └─► Calls _get_costs_items_from_purchase() [from project_account]
    │                 └─► account.move.line search + analytic contribution
    │
    └─► _get_items_from_aal() [project_account override]
          └─► account.analytic.line search
              ├── Filter: account_id = project.account_id, move_line_id = False
              ├── Exclude: manufacturing_order, picking_entry categories
              ├── Classify: negative = cost, positive = revenue
              └── Convert: to project currency

Profitability Dashboard (sections by sequence):
  10 - purchase_order         [project_purchase]
  11 - other_purchase_costs    [project_account: vendor bills via AML]
  14 - other_revenues_aal      [project_account: AAL positive amounts]
  15 - other_costs_aal         [project_account: AAL negative amounts]
```

## Key Models

### `project.project` (Inherited)

**Profitability Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `_add_purchase_items` | `(profitability_items, with_action=True)` | Entry point. In `project_account` it calls `_get_costs_items_from_purchase()`. Overridden to `False` in `sale_project` to suppress duplicate PO billing. |
| `_get_add_purchase_items_domain` | `()` | Returns domain for non-PO vendor bills: `in_invoice/in_refund`, `draft/posted`, `price_subtotal > 0`, excludes already-included invoice lines. |
| `_get_costs_items_from_purchase` | `(domain, profitability_items, with_action=True)` | Core computation: reads account.move.line via analytic_distribution, computes analytic contribution per line, converts to project currency, categorizes by `parent_state`. Returns nothing; appends directly to `profitability_items['costs']`. |
| `_get_action_for_profitability_section` | `(record_ids, name)` | Generates action dict `{'name': 'action_profitability_items', 'type': 'object', 'args': json.dumps([name, domain])}` for clicking a profitability section. Passes `res_id` when `len(record_ids) == 1` for form view fallback. |
| `_get_profitability_labels` | `()` | Extends parent with: `other_purchase_costs: Vendor Bills`, `other_revenues_aal: Other Revenues`, `other_costs_aal: Other Costs` |
| `_get_profitability_sequence_per_invoice_type` | `()` | Extends parent with sequences: `11, 14, 15` |
| `_get_items_from_aal` | `(with_action=True)` | Reads non-move-line AAL for the project, aggregates by currency, converts to project currency, returns revenues/costs dicts. Adds action for `group_account_readonly` users. |
| `_get_domain_aal_with_no_move_line` | `()` | Returns `[('account_id', '=', self.account_id.id), ('move_line_id', '=', False)]`. Extended by `sale_timesheet` to exclude timesheet AALs. |
| `action_profitability_items` | `(section_name, domain=None, res_id=False)` | Dispatches to AAL pivot/graph for `other_revenues_aal/other_costs_aal/other_costs`, vendor bill list for `other_purchase_costs`, else delegates to parent. |
| `action_open_analytic_items` | `()` | Opens `account.analytic.line` filtered to project's analytic account. Sets `create` from embedded action context. |

## Integration with Other Modules

### `sale_project`

`sale_project` overrides `_add_purchase_items()` to return `False`, suppressing the vendor bills section because it computes PO-linked costs separately and does not use `_get_costs_items_from_purchase()`. However, it still calls the parent chain which eventually reaches `project_account`'s `_get_items_from_aal()` for the AAL-based sections.

### `project_purchase`

`project_purchase` overrides `_add_purchase_items()` fully. It computes PO costs directly from `purchase.order.line` records, then calls `project_account._get_costs_items_from_purchase()` for the vendor bills without PO:

```python
def _add_purchase_items(self, profitability_items, with_action=True):
    # ... compute PO costs ...
    domain = [
        ('move_id.move_type', 'in', ['in_invoice', 'in_refund']),
        ('parent_state', 'in', ['draft', 'posted']),
        ('price_subtotal', '!=', 0),
        ('id', 'not in', purchase_order_line_invoice_line_ids),
    ]
    self._get_costs_items_from_purchase(domain, profitability_items, with_action=with_action)
```

This is the only module that **does not** exclude PO-linked invoice lines from the vendor bills domain (it passes `('price_subtotal', '!=', 0)` instead of `('price_subtotal', '>', 0)`).

### `sale_timesheet`

`sale_timesheet` extends `project_account`'s profitability with timesheet-specific sections (billable_fixed, billable_time, billable_milestones, billable_manual, non_billable). It overrides:

- `_get_domain_aal_with_no_move_line()` — adds `('project_id', '=', False)` to exclude timesheet-generated AALs from the generic "Other Costs/Revenues" section
- `_get_profitability_aal_domain()` — adds `('project_id', 'in', self.ids)` to include timesheet AALs in billing sections
- `_get_items_from_aal()` — provides its own implementation that handles timesheet billing categorization

### `hr_expense`

Expense entries contribute to project costs via analytic distribution on vendor bill lines. When an expense is validated and its vendor bill is posted, the expense's `analytic_distribution` creates `account.move.line` records that flow into the vendor bills section via `_get_costs_items_from_purchase`.

### `mrp` (Manufacturing)

Manufacturing orders generate analytic lines with `category = 'manufacturing_order'`. These are explicitly excluded from `_get_items_from_aal` via the domain filter. Manufacturing costs appear in the project's profitability only through the analytic account's direct entries or via vendor bills with manufacturing-related analytic distributions.

## Key Files

| File | Description |
|------|-------------|
| `models/project_project.py` | All profitability computation logic (184 lines) |
| `models/__init__.py` | Imports only `project_project` |
| `views/project_project_views.xml` | List/form view inherit (partner_id context) + 2 embedded actions |
| `views/project_task_views.xml` | Task form/list inherits (partner_id context) |
| `views/project_sharing_project_task_views.xml` | Project sharing task form inherit (partner_id context) |
| `views/account_analytic_line_views.xml` | Custom pivot/graph views for AAL, with group_by_date support |
| `tests/test_project_profitability.py` | Tests verifying multi-currency AAL → profitability conversion |

## View Architecture

### Custom AAL Views (`account_analytic_line_views.xml`)

Two custom views extend the base `analytic` module's AAL views specifically for project profitability drill-down:

**Graph view** (`project_view_account_analytic_line_graph`):
- Adds `date` as a row grouping field
- Removes the default `account_id` field replacement to show project-specific data
- Mode: `primary` (not an extension; a full override)

**Pivot view** (`project_view_account_analytic_line_pivot`):
- Adds `date` as a row grouping field
- Hides `partner_id` when `group_by_date` context is set (avoids visual clutter)
- Removes `account_id` from the visible pivot columns

Both views are registered with `mode = 'primary'` to prevent inheritance chain issues and ensure they override the base analytic views entirely.

### Partner Context Override

All form/list views (project, task, project sharing task) override the `partner_id` field to add `{'res_partner_search_mode': 'customer'}` context. This restricts the partner dropdown to customer-type partners rather than all partners, matching the expectation that project-related contacts are primarily customers.

## Tests

```python
# tests/test_project_profitability.py
@tagged('-at_install', 'post_install')
class TestProjectAccountProfitability(TestProjectProfitabilityCommon):

    def test_project_profitability(self):
        # 1. Create project with analytic account
        project = self.env['project.project'].create({'name': 'test'})
        project._create_analytic_account()

        # 2. Empty project returns zeroed-out profitability
        project._get_profitability_items(False)  # no sections

        # 3. AAL from foreign company → converted to project currency
        self.env['account.analytic.line'].create([{
            'name': 'extra revenues 1',
            'account_id': project.account_id.id,
            'amount': 100,
            'company_id': foreign_company.id,  # different currency
        }, {
            'name': 'extra costs 1',
            'account_id': project.account_id.id,
            'amount': -100,
            'company_id': foreign_company.id,
        }])
        # Result: other_revenues_aal.invoiced = 30, other_costs_aal.billed = -30
        # (converted from foreign currency to project currency)

        # 4. AAL from project company (base currency)
        self.env['account.analytic.line'].create([{...}, {...}])
        # Total: invoiced = 180, billed = -180 (2x the foreign company amounts)
```

**Test class hierarchy**: `TestProjectAccountProfitability` inherits from `TestProjectProfitabilityCommon` (from `project.tests.test_project_profitability`), which provides the base `project_profitability_items_empty` fixture and common setup including the `foreign_currency` used in multi-currency tests.

## Related

[Project.md](Modules/project.md), [Account.md](Modules/account.md), [Analytic.md](Modules/analytic.md), [Sale Project.md](Modules/sale-project.md), [Project Purchase.md](Project-Purchase.md.md), [Sale Timesheet.md](Modules/sale-timesheet.md)