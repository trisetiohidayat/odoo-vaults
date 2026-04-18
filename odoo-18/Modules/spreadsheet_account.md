---
Module: spreadsheet_account
Version: 18.0
Type: addon
Tags: #spreadsheet, #account
---

# spreadsheet_account — Spreadsheet Accounting Formulas

## Module Overview

**Category:** Accounting
**Depends:** `spreadsheet`, `account`
**License:** LGPL-3
**Installable:** True
**Auto-install:** True

Integrates accounting data into Odoo Spreadsheets. Provides spreadsheet-safe RPC methods (`ODOO.CREDIT`, `ODOO.DEBIT`, `ODOO.BALANCE`, `ODOO.PARTNER.BALANCE`, `ODOO.RESIDUAL`, etc.) that execute against `account.move.line` data with fiscal date period support, account code matching, and optional partner filtering.

## Static Assets (o_spreadsheet bundle)

- All JS files under `spreadsheet_account/static/src/**/*.js` are injected after `spreadsheet/static/src/o_spreadsheet/o_spreadsheet.js`, registering accounting Odoo-specific spreadsheet formulas.

## Models

### `account.account` (`account.account`)

Extends with spreadsheet formula support methods. All methods are `@api.model` and execute with `with_company()` scoping.

**Methods:**

**`_get_date_period_boundaries(date_period, company)`**
Converts a date period specification (year/month/quarter/day) to `(start, end)` date tuple, applying company fiscal year settings:
- `year`: adds 1 to year if fiscal year end is not December 31, then computes fiscal year boundaries
- `month`: first day of month to last day of month
- `quarter`: first day of quarter to last day of quarter
- `day`: fiscal year start to the specified day

**`_build_spreadsheet_formula_domain(formula_params, default_accounts=False)`**
Builds a domain for `account.move.line` queries from spreadsheet formula parameters:
```python
{
    "date_range": {"range_type": "year"|"month"|"quarter"|"day", "year": int, ...},
    "company_id": int,
    "codes": str[],           # account code prefixes (LIKE match)
    "include_unposted": bool,
    "partner_ids": int[]      # optional
}
```
Logic:
1. Matches account codes via `code LIKE '{code}%'` OR (if `default_accounts=True`) matches payable/receivable account types
2. Separates balance accounts (`include_initial_balance=True`, date `<= end`) from P&L accounts (`include_initial_balance=False`, date range)
3. Filters by company and optional partner IDs
4. Filters by `move_id.state` (`posted` or non-cancelled)

Returns a domain list for `_read_group`.

**`spreadsheet_move_line_action(args)`**
Opens `account.move.line` list view filtered to the computed domain for cell audit (drill-down from spreadsheet cell).

**`spreadsheet_fetch_debit_credit(args_list)`**
For each args entry, returns `{'debit': float, 'credit': float}` via `_read_group(aggregates=['debit:sum', 'credit:sum'])`.

**`spreadsheet_fetch_residual_amount(args_list)`**
For each args entry, returns `{'amount_residual': float}` via `_read_group(aggregates=['amount_residual:sum'])`.

**`spreadsheet_fetch_partner_balance(args_list)`**
For each args entry, returns `{'balance': float}` filtered to specific partner IDs. If no partners, returns `{'balance': 0}`.

**`get_account_group(account_types)`**
Returns per-account-type arrays of account codes via `_read_group(
    [('account_type', 'in', account_types)],
    ['account_type'],
    ['code:array_agg']
)`.

### `res.company` (`res.company`)

**Methods:**

**`get_fiscal_dates(payload)`**
For each entry in `payload` (list of `{"company_id": int, "date": str}`), reads the company's `fiscalyear_last_day` and `fiscalyear_last_month`, then computes `{start: date, end: date}` via `date_utils.get_fiscal_year`.

## What It Extends

- `account.account` — spreadsheet formula evaluation methods
- `res.company` — fiscal date computation for spreadsheets

## Key Behavior

- All formulas run via `@api.model` methods as the current user with `with_company()`.
- Account code matching uses `expression.OR` on `code LIKE` patterns.
- Partner balance supports multi-partner filtering via IN clause.
- Balance accounts use `include_initial_balance=True` with end-date only for cumulative balance.
- P&L accounts use start+end dates for period-only balance.
- Per-company execution via `with_company(company_id)` ensures multi-company isolation.

## Spreadsheet Formula Reference

| Formula | Method | Description |
|---------|--------|-------------|
| `ODOO.CREDIT` | `spreadsheet_fetch_debit_credit` | Sum of credits for matched accounts/period |
| `ODOO.DEBIT` | `spreadsheet_fetch_debit_credit` | Sum of debits for matched accounts/period |
| `ODOO.BALANCE` | `spreadsheet_fetch_debit_credit` | Net balance (debit - credit) |
| `ODOO.PARTNER.BALANCE` | `spreadsheet_fetch_partner_balance` | Balance for specific partners |
| `ODOO.RESIDUAL` | `spreadsheet_fetch_residual_amount` | Residual amount (amount_residual sum) |
| `ODOO.ACCOUNT.GROUP` | `get_account_group` | List of account codes in a group |
| `ODOO.FISCAL.DATE` | `get_fiscal_dates` | Fiscal year start/end for a date |

## See Also

- [Modules/Spreadsheet](Modules/spreadsheet.md) (`spreadsheet`) — base spreadsheet engine
- [Modules/Spreadsheet Dashboard](Modules/Spreadsheet-Dashboard.md) (`spreadsheet_dashboard`) — dashboard container
- [Modules/Account](Modules/account.md) — accounting data source
