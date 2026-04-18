---
tags: [odoo, odoo19, spreadsheet, dashboard, sale-timesheet, timesheet, project, billing]
---

# spreadsheet_dashboard_sale_timesheet

## Overview

| Property | Value |
|----------|-------|
| Technical Name | `spreadsheet_dashboard_sale_timesheet` |
| Category | Productivity/Dashboard |
| Depends | `spreadsheet_dashboard`, `sale_timesheet` |
| Auto-install trigger | `sale_timesheet` |
| License | LGPL-3 |
| Module type | Data-only (no Python models) |

Provides a pre-configured [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) template named "Timesheets" for service businesses that bill customers based on time logged. Bridges three data domains: project time tracking, sales orders, and billing. Auto-installs when `sale_timesheet` is active and appears in the Project dashboard group at sequence 200.

## Module Architecture

Pure data module — no Python model code.

```
spreadsheet_dashboard_sale_timesheet/
├── __init__.py               # empty
├── __manifest__.py           # depends on sale_timesheet, auto_install
└── data/
    ├── dashboards.xml        # creates spreadsheet.dashboard record
    └── files/
        ├── timesheet_dashboard.json        # live dashboard spreadsheet
        └── timesheet_sample_dashboard.json # sample shown when no data
```

## Dashboard Record Definition

Source: `/data/dashboards.xml`

```xml
<record id="spreadsheet_dashboard_timesheet" model="spreadsheet.dashboard">
    <field name="name">Timesheets</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_sale_timesheet/data/files/timesheet_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('analytic.model_account_analytic_line')),
                  (4, ref('project.model_project_project')),
                  (4, ref('sale.model_sale_order'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_sale_timesheet/data/files/timesheet_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_project"/>
    <field name="group_ids"
           eval="[Command.link(ref('hr_timesheet.group_hr_timesheet_approver'))]"/>
    <field name="sequence">200</field>
    <field name="is_published">True</field>
</record>
```

### Record Properties

| Field | Value | Significance |
|-------|-------|--------------|
| `name` | "Timesheets" | Dashboard navigation label |
| `dashboard_group_id` | `group_project` | Appears under "Project" section |
| `group_ids` | `hr_timesheet.group_hr_timesheet_approver` | Timesheet Approvers only |
| `sequence` | 200 | Appears after "Project" dashboard (sequence 100) in the same group |
| `main_data_model_ids` | 3 models (see below) | All three checked for empty-data fallback |
| `is_published` | True | Visible immediately |

## Three-Model Empty-Data Check

This module registers **three** models in `main_data_model_ids`:
1. `account.analytic.line` — timesheet entries
2. `project.project` — projects
3. `sale.order` — sales orders

`_dashboard_is_empty()` checks **any** of these. The framework considers the dashboard empty if `search_count([], limit=1) == 0` for any of the three models. In a fresh database, all three would be empty.

In practice, if `project.project` or `sale.order` are empty, there can be no meaningful timesheet billing data, so the fallback to the sample dashboard is appropriate.

When any of these three models returns zero records, the framework serves `timesheet_sample_dashboard.json`.

## Comparison with hr_timesheet Dashboard

| Aspect | spreadsheet_dashboard_hr_timesheet | This Module |
|--------|-------------------------------------|-------------|
| Focus | Internal project time tracking | Billable time on sales orders |
| Main models | None set | analytic.line + project + sale.order |
| Sample file | No | Yes |
| Sequence | 100 | 200 |
| Dashboard name | "Project" | "Timesheets" |
| Key differentiator | All time entries | Only billable entries (linked to SO) |

Both appear in the Project dashboard group but serve different audiences: the "Project" dashboard for project managers tracking all time, the "Timesheets" dashboard for service delivery managers tracking billable revenue.

## Data Sources and KPI Structure

The `sale_timesheet` module links timesheet entries to sale order lines via the `so_line` field on `account.analytic.line`. This is the central relationship the dashboard exploits.

### Model 1: `account.analytic.line` (timesheet entries)

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `employee_id` | Many2one | Employee dimension |
| `project_id` | Many2one | Project dimension |
| `task_id` | Many2one | Task dimension |
| `date` | Date | Time period dimension |
| `unit_amount` | Float | Hours logged (core measure) |
| `so_line` | Many2one | Linked sale order line (from sale_timesheet) |
| `timesheet_invoice_type` | Selection | Billing type classification |
| `timesheet_invoice_id` | Many2one | Invoice if line is billed |
| `name` | Char | Activity description |

### Model 2: `project.project`

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `name` | Char | Project name |
| `partner_id` | Many2one | Customer |
| `sale_order_id` | Many2one | Linked sale order |
| `allow_billable` | Boolean | Billability toggle |
| `billable_type` | Selection | Billing method |
| `remaining_hours` | Float | Budget vs. actual tracking |
| `allocated_hours` | Float | Budget hours |
| `effective_hours` | Float | Hours logged so far |

### Model 3: `sale.order`

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `name` | Char | Order reference |
| `partner_id` | Many2one | Customer |
| `amount_total` | Monetary | Contract value |
| `invoiced_amount` | Monetary | Revenue recognized so far |
| `state` | Selection | Order status |
| `user_id` | Many2one | Salesperson/account manager |

## Key KPIs Tracked

**Revenue Recognition**
- Revenue recognized this period: hours logged × rate
- Revenue by project
- Revenue by customer
- Revenue by salesperson/account manager
- Total contract value vs. billed to date

**Hours Sold vs. Delivered**

This is the core service business metric:
```
Hours sold (from sale.order.line.product_uom_qty)
    vs.
Hours delivered (account.analytic.line.unit_amount WHERE so_line IS NOT NULL)
```

- Hours sold: what was committed in the sales order
- Hours delivered: what has actually been logged
- Delta: over/under-delivery (risk indicator)
- Delivery rate %: `hours_delivered / hours_sold × 100`

**Billability**

Not all logged hours are billable. The `timesheet_invoice_type` field classifies each entry:
- `billable_time` — billed at hourly rate
- `billable_fixed` — part of a fixed-price deliverable
- `non_billable` — internal/non-billable time
- `non_billable_project` — project-level non-billable

Dashboard KPIs:
- Billable hours ratio: `billable_hours / total_hours × 100`
- Non-billable hours (internal overhead)
- Employee billability rate
- Project billability rate

**Margin Analysis**

For time-and-materials projects where both cost (employee hourly rate from `hr.employee.hourly_cost`) and revenue (from sale order line price) are known:
- Margin per project: revenue − (hours × cost rate)
- Margin % per project
- Margin by employee type

**Invoice Status**
- Uninvoiced billable hours (pending billing)
- Hours invoiced this period
- Revenue in `timesheet_invoice_id` (already billed)
- Projects with large uninvoiced amounts (billing backlog)

## sale_timesheet Billing Methods

`sale_timesheet` supports multiple billing models that affect how the dashboard interprets data:

| Billing Type | `sale.order.line.product_id.invoice_policy` | Dashboard Impact |
|-------------|---------------------------------------------|-----------------|
| Time & Materials | `timesheet` | Revenue = hours × unit price |
| Fixed Price | `fixed_price` | Revenue recognized at delivery milestone |
| Prepaid Hours | `manual` | Deduct from prepaid hour block |

The "Timesheets" dashboard is most meaningful for time & materials billing. Fixed-price projects appear in the dashboard but their revenue recognition follows a different logic.

## Project Profitability View

A key use case is project profitability analysis:

```
For each project.project:
    Contract value = sale.order.amount_total
    Actual cost = SUM(analytic_line.unit_amount × employee.hourly_cost)
    Revenue recognized = invoiced_amount
    Profitability = revenue_recognized - actual_cost
```

The dashboard surfaces these calculations per project, allowing managers to identify under-performing engagements early.

## Auto-Install Behavior

```python
'auto_install': ['sale_timesheet'],
```

`sale_timesheet` is the integration module connecting sales orders with project time tracking. When a company bills by the hour and uses Odoo for both CRM/sales and project management, `sale_timesheet` is typically installed. This dashboard auto-installs alongside it.

## Dependencies Chain

```
spreadsheet_dashboard_sale_timesheet
├── spreadsheet_dashboard   # base framework
└── sale_timesheet          # depends on:
    ├── sale                # sale.order, sale.order.line
    ├── hr_timesheet        # account.analytic.line (timesheet variant)
    └── project             # project.project, project.task
```

## Project Group Context

Within the Project dashboard group, the two dashboards complement each other:

1. **"Project" (sequence 100)** from `spreadsheet_dashboard_hr_timesheet`: All hours, internal focus
2. **"Timesheets" (sequence 200)** from this module: Billable hours, customer-facing focus

Service delivery managers typically check the "Timesheets" dashboard before billing cycles to verify all billable hours are captured and invoiced.

## Customization

1. **Client-specific view**: Add a slicer by `project_id.partner_id` to show only one customer's projects
2. **Budget alerts**: Add a conditional format highlighting projects where `effective_hours > allocated_hours`
3. **Weekly billing report**: Configure the time dimension to show weekly periods with cumulative billing
4. **Employee cost import**: Add a VLOOKUP table with employee cost rates for detailed margin calculation

## Related Modules

- [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Dashboard framework
- [spreadsheet_dashboard_hr_timesheet](Modules/spreadsheet_dashboard_hr_timesheet.md) — Internal project time tracking
- [spreadsheet_account](Modules/spreadsheet_account.md) — Accounting integration for revenue recognition
- `sale_timesheet` — Links timesheets to sales orders and manages billability

## Source Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_sale_timesheet/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_sale_timesheet/data/dashboards.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_sale_timesheet/data/files/timesheet_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_sale_timesheet/data/files/timesheet_sample_dashboard.json`
