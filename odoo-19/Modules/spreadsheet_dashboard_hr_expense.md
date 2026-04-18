---
tags: [odoo, odoo19, spreadsheet, dashboard, expenses, hr_expense, finance]
---

# spreadsheet_dashboard_hr_expense

## Overview

| Property | Value |
|----------|-------|
| Technical Name | `spreadsheet_dashboard_hr_expense` |
| Category | Productivity/Dashboard |
| Depends | `spreadsheet_dashboard`, `sale_expense` |
| Auto-install trigger | `sale_expense` |
| License | LGPL-3 |
| Module type | Data-only (no Python models) |

Provides a pre-configured [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) template for finance and HR managers to monitor employee expense submissions, approval workflows, and expense re-invoicing to customers. Auto-installs when `sale_expense` is active.

## Module Architecture

This is a pure data module with no Python model code. Its sole contribution is inserting a `spreadsheet.dashboard` record via XML.

```
spreadsheet_dashboard_hr_expense/
├── __init__.py               # empty
├── __manifest__.py           # metadata, depends on sale_expense
└── data/
    ├── dashboards.xml        # creates spreadsheet.dashboard record
    └── files/
        ├── expense_dashboard.json        # live dashboard spreadsheet
        └── expense_sample_dashboard.json # shown when no expense data exists
```

## Dashboard Record Definition

Source: `/data/dashboards.xml`

```xml
<record id="spreadsheet_dashboard_expense" model="spreadsheet.dashboard">
    <field name="name">Expenses</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_hr_expense/data/files/expense_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('hr_expense.model_hr_expense'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_hr_expense/data/files/expense_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_finance"/>
    <field name="group_ids"
           eval="[Command.link(ref('hr_expense.group_hr_expense_manager'))]"/>
    <field name="sequence">40</field>
    <field name="is_published">True</field>
</record>
```

### Record Properties

| Field | Value | Significance |
|-------|-------|--------------|
| `name` | "Expenses" | Displayed in dashboard menu |
| `dashboard_group_id` | `group_finance` | Appears under "Finance" section |
| `group_ids` | `hr_expense.group_hr_expense_manager` | Only Expense Managers can see it |
| `sequence` | 40 | Positioned early in Finance group (high priority) |
| `main_data_model_ids` | `hr.expense` | Empty-check triggers sample data fallback |
| `is_published` | True | Visible immediately upon install |

## Framework Integration

### Empty-Data Fallback

`_dashboard_is_empty()` checks whether `hr.expense` has any records. When no expenses exist, the framework serves `expense_sample_dashboard.json` with pre-populated demo values. This is critical for HR modules where a fresh database would show blank charts.

### Access Control

Only users with `hr_expense.group_hr_expense_manager` see the Expenses dashboard. Regular employees with only the basic expense group (`group_hr_expense_user`) cannot access this dashboard — they submit their own expenses but cannot view company-wide analytics.

### Finance Group Placement

`spreadsheet_dashboard_group_finance` is the Finance dashboard group from the base `spreadsheet_dashboard` module. Sequence 40 positions Expenses before most other Finance dashboards, reflecting that expense monitoring is a frequent finance team task.

## Data Sources and KPI Structure

The spreadsheet reads expense data using ODOO.PIVOT formulas that aggregate across the expense models introduced by `hr_expense` and extended by `sale_expense`.

### Primary Model: `hr.expense`

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `name` | Char | Expense description |
| `employee_id` | Many2one | Breakdown by employee |
| `department_id` | Many2one (via employee) | Department-level aggregation |
| `product_id` | Many2one | Expense category/type |
| `total_amount` | Monetary | Expense amount |
| `date` | Date | Period filtering |
| `state` | Selection | Approval funnel stage |
| `sheet_id` | Many2one | Expense report grouping |
| `company_id` | Many2one | Multi-company filter |

### Secondary Model: `hr.expense.sheet`

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `name` | Char | Report reference |
| `employee_id` | Many2one | Submitter |
| `total_amount` | Monetary | Report total |
| `state` | Selection | Approval status |
| `accounting_date` | Date | Posting date |

### sale_expense Integration

The `sale_expense` dependency adds re-invoicing fields to expenses. When an expense is linked to a sale order via `sale_order_id`, it can be billed to the customer. The dashboard tracks:

| Model | Field | Dashboard Use |
|-------|-------|---------------|
| `hr.expense` | `sale_order_id` | Link to customer order |
| `sale.order` | `amount_total` | Revenue from re-invoiced expenses |
| `account.move` | linked via sheet | Accounting entries |

## Key KPIs Tracked

**Submission Volume**
- Total expenses submitted this period (count and amount)
- Expenses by employee and department
- Average expense per employee
- Expense submission trend month-over-month

**Approval Funnel**
Expense states in Odoo: `draft` → `reported` → `approved` → `posted` → `done`

- Draft (not yet submitted): expenses being prepared
- Reported (submitted): waiting for manager approval
- Approved: manager-approved, awaiting payment
- Posted: accounting entry created
- Done: reimbursement paid

The dashboard shows the count and amount at each stage, highlighting bottlenecks (e.g., large amount sitting in "Approved" waiting for payment).

**Expense Categories**
- Breakdown by `product_id` (Travel, Meals, Accommodation, etc.)
- Top expense categories by total amount
- Category trends over time

**Re-invoiced Expenses (sale_expense)**
- Expenses linked to sale orders
- Re-invoicing amount vs. total expense amount
- Margin on re-invoiced expenses (if selling price differs)
- Expenses not yet billed to customers

**Department/Employee Analysis**
- Expense totals per department
- Top spenders by employee
- Average expense per transaction by category
- Employees with pending expense reports

## Approval Workflow Monitoring

A core value of this dashboard is spotting workflow stalls:

```
Employee submits expense
    ↓ state = 'reported'
Manager reviews → Approves
    ↓ state = 'approved'
Finance posts payment
    ↓ state = 'posted'
Reimbursement made
    ↓ state = 'done'
```

The dashboard typically shows aging analysis — how long expenses sit in each state — to identify managers who are slow to approve or finance teams with posting backlogs.

## Auto-Install Behavior

```python
'auto_install': ['sale_expense'],
```

`sale_expense` itself depends on both `hr_expense` and `sale`. When the combination of expense + sales features is active, the Expenses dashboard auto-installs. This covers the common scenario of companies that both track employee expenses AND re-invoice some expenses to customers.

Note: the dependency is on `sale_expense`, not just `hr_expense`. Companies using only basic expense management without re-invoicing would need to install this module manually.

## Dependencies Chain

```
spreadsheet_dashboard_hr_expense
├── spreadsheet_dashboard   # base framework
└── sale_expense            # depends on:
    ├── hr_expense          # hr.expense, hr.expense.sheet
    └── sale                # sale.order (for re-invoicing)
```

## Customization

**Common use cases for customization:**
1. Add department filter: Edit the spreadsheet to add a department slicer
2. Expense policy compliance: Add a KPI showing expenses above policy limits
3. Custom categories: Add pivot rows for company-specific expense types
4. Manager-specific views: Create separate dashboards per department using the Copy action

## Related Modules

- [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Framework providing `spreadsheet.dashboard` model
- [spreadsheet_account](Modules/spreadsheet_account.md) — Accounting formulas for financial integration
- `hr_expense` — Expense model, approval workflow, reimbursement
- `sale_expense` — Links expenses to sale orders for customer billing

## Source Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_hr_expense/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_hr_expense/data/dashboards.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_hr_expense/data/files/expense_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_hr_expense/data/files/expense_sample_dashboard.json`
