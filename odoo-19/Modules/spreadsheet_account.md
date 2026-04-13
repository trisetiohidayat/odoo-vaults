---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #spreadsheet
  - #account
  - #ce
---

# spreadsheet_account (Spreadsheet Accounting Formulas)

## Module Overview

**Module Name:** `spreadsheet_account`  
**Type:** Community (CE)  
**Location:** `odoo/addons/spreadsheet_account/`  
**Category:** Accounting  
**License:** LGPL-3  
**Auto-install:** Yes (installs automatically with `spreadsheet` + `account`)

**Summary:** This module registers Odoo Accounting data as **spreadsheet formula providers**, enabling accountants and financial analysts to build live financial reports inside Odoo's spreadsheet editor using formulas like `ODOO.BALANCE`, `ODOO.DEBIT`, `ODOO.CREDIT`, and `ODOO.PARTNER.BALANCE`.

**Key Value Proposition:**
- Pulls live accounting data directly into spreadsheet cells
- Supports fiscal year, quarter, month, and day period selection
- Filter by account codes, account tags, or partner
- Cell audit: click any formula cell to drill down to journal entries
- Replaces manual Excel export/import cycles for financial reporting

**Dependencies:** `spreadsheet`, `account`

---

## Architecture

### Formula Provider Pattern

Odoo's spreadsheet system has a plugin architecture. `spreadsheet_account` contributes accounting data by registering a **JavaScript bundle** (`spreadsheet_account/static/src/**/*.js`) that defines custom spreadsheet functions.

On the Python/ORM side, it exposes `@api.model` methods decorated with `@api.readonly` that act as the backend handlers for these functions. The flow:

```
Spreadsheet cell: =ODOO.BALANCE("4000", "year", 2024)
        │
        ▼ (JS client)
RPC call: account.account.spreadsheet_fetch_debit_credit([{...}])
        │
        ▼ (Python ORM)
Read account.move.line records, aggregate debit/credit
        │
        ▼
Return: {debit: 150000, credit: 120000}
        │
        ▼ (JS client)
Cell value updated: 30000 (net balance)
```

### What It Does NOT Do

This module does **not** create spreadsheet templates itself. It only provides the data access layer. The actual P&L, Balance Sheet, and trial balance templates are created using Odoo's spreadsheet editor UI, where users type formulas like `=ODOO.BALANCE(...)` and configure periods via dropdowns.

---

## Key Models

### 1. `account.account` Extensions

All spreadsheet formula methods are attached to `account.account` via `_inherit = 'account.account'`. This model is used as the carrier for the RPC endpoints because:
- Every accounting formula starts from account data
- The model is always available in accounting contexts

---

## Spreadsheet Formulas

### Supported Functions

| Function | Description | Return Type |
|----------|-------------|-------------|
| `ODOO.DEBIT` | Sum of debit amounts for matching move lines | Number |
| `ODOO.CREDIT` | Sum of credit amounts for matching move lines | Number |
| `ODOO.BALANCE` | Net balance (debit - credit) | Number |
| `ODOO.RESIDUAL` | Sum of residual (unpaid) amounts | Number |
| `ODOO.PARTNER.BALANCE` | Partner-specific balance for matching accounts | Number |
| `ODOO.BALANCE.TAG` | Balance filtered by account tag instead of code | Number |

### Formula Parameters

Each function accepts a **params object**:

```javascript
// Example: Get 2024 balance for account codes starting with "400"
=ODOO.BALANCE({
    codes: ["400"],
    date_range: {range_type: "year", year: 2024},
    company_id: 1,
    include_unposted: false
})
```

| Parameter | Type | Description |
|----------|------|-------------|
| `codes` | `string[]` | Account codes to include (prefix match with `LIKE`). Empty = use default accounts (receivable/payable) |
| `account_tag_ids` | `string[]` | Account tag IDs (for `ODOO.BALANCE.TAG` only) |
| `date_range.range_type` | `string` | `year`, `month`, `quarter`, `day` |
| `date_range.year` | `int` | Calendar year |
| `date_range.month` | `int` | Month number 1-12 (required for `month`, `quarter`, `day`) |
| `date_range.quarter` | `int` | Quarter 1-4 (required for `quarter`) |
| `date_range.day` | `int` | Day of month (required for `day`) |
| `company_id` | `int` | Company ID (default: current company) |
| `include_unposted` | `bool` | Include draft (non-posted) journal entries |
| `partner_ids` | `int[]` | Filter to specific partners (for `ODOO.PARTNER.BALANCE`) |

---

## Core Methods

### `_get_date_period_boundaries(date_period, company)`

Converts a spreadsheet period selection into concrete PostgreSQL date range `(start, end)`, respecting the company's **fiscal year** settings (`fiscalyear_last_day`, `fiscalyear_last_month`).

```python
def _get_date_period_boundaries(self, date_period, company):
    period_type = date_period["range_type"]
    if period_type == "year":
        # Uses company.fiscalyear_last_day/month
        fiscal_day = company.fiscalyear_last_day
        fiscal_month = int(company.fiscalyear_last_month)
        start, end = date_utils.get_fiscal_year(current, fiscal_day, fiscal_month)
    elif period_type == "month":
        start = date(year, month, 1)
        end = start + relativedelta(months=1, days=-1)
    elif period_type == "quarter":
        first_month = quarter * 3 - 2
        start = date(year, first_month, 1)
        end = start + relativedelta(months=3, days=-1)
    # ...
    return start, end
```

**Key insight:** This correctly handles custom fiscal years (e.g., July-June for UK companies) and partial years.

---

### `_build_spreadsheet_formula_domain(formula_params)`

Constructs the Odoo `Domain` object for querying `account.move.line` records based on spreadsheet formula parameters.

```python
def _build_spreadsheet_formula_domain(self, formula_params, default_accounts=False):
    # 1. Determine date range
    start, end = self._get_date_period_boundaries(...)

    # 2. Build balance vs P&L domain
    # Balance accounts: include initial balance (from before start date)
    balance_domain = Domain([
        ("account_id.include_initial_balance", "=", True),
        ("date", "<=", end),
    ])
    # P&L accounts: only current period
    pnl_domain = Domain([
        ("account_id.include_initial_balance", "=", False),
        ("date", ">=", start),
        ("date", "<=", end),
    ])
    period_domain = balance_domain | pnl_domain

    # 3. Filter by account codes (prefix LIKE match)
    # codes = ["400", "500"] → code LIKE '400%' OR code LIKE '500%'
    if 'codes' in formula_params:
        code_domain = Domain.OR(
            Domain("code", "=like", f"{code}%")
            for code in codes
        )
        account_ids = self.env["account.account"].search(code_domain).ids
        account_id_domain = [("account_id", "in", account_ids)]

    # 4. Filter by account tags
    elif 'account_tag_ids' in formula_params:
        tag_ids = [int(t) for t in formula_params["account_tag_ids"]]
        account_id_domain = Domain('account_id.tag_ids', 'in', tag_ids)

    # 5. Posted vs all entries
    posted_domain = [("move_id.state", "=", "posted")]  # or "!=", "cancel"
```

**Key insight:** For P&L accounts, only the current period is included. For balance sheet accounts (asset/liability with `include_initial_balance=True`), the query spans from the beginning of time up to `end`, capturing the running balance.

---

### `spreadsheet_fetch_debit_credit(args_list)`

Handles `ODOO.DEBIT`, `ODOO.CREDIT`, and `ODOO.BALANCE`.

```python
@api.readonly
@api.model
def spreadsheet_fetch_debit_credit(self, args_list):
    results = []
    for args in args_list:
        domain = self._build_spreadsheet_formula_domain(args)
        MoveLines = self.env["account.move.line"].with_company(company_id)
        [(debit, credit)] = MoveLines._read_group(
            domain,
            aggregates=['debit:sum', 'credit:sum']
        )
        results.append({'debit': debit or 0, 'credit': credit or 0})
    return results
```

Uses `_read_group` for efficient single-query aggregation.

---

### `spreadsheet_fetch_residual_amount(args_list)`

Handles `ODOO.RESIDUAL` — returns the sum of `amount_residual` for matching move lines (useful for accounts receivable/payable reports showing outstanding invoices).

```python
@api.model
def spreadsheet_fetch_residual_amount(self, args_list):
    results = []
    for args in args_list:
        domain = self._build_spreadsheet_formula_domain(args, default_accounts=True)
        MoveLines = self.env["account.move.line"].with_company(company_id)
        [(amount_residual,)] = MoveLines._read_group(
            domain,
            aggregates=['amount_residual:sum']
        )
        results.append({'amount_residual': amount_residual or 0})
    return results
```

---

### `spreadsheet_fetch_partner_balance(args_list)`

Handles `ODOO.PARTNER.BALANCE` — returns balance for specific partners.

```python
@api.model
def spreadsheet_fetch_partner_balance(self, args_list):
    results = []
    for args in args_list:
        partner_ids = [p for p in args.get('partner_ids', []) if p]
        if not partner_ids:
            results.append({'balance': 0})
            continue
        domain = self._build_spreadsheet_formula_domain(args, default_accounts=True)
        MoveLines = self.env["account.move.line"].with_company(company_id)
        [(balance,)] = MoveLines._read_group(
            domain,
            aggregates=['balance:sum']
        )
        results.append({'balance': balance or 0})
    return results
```

---

### `spreadsheet_fetch_balance_tag(args_list)`

Handles `ODOO.BALANCE.TAG` — filters accounts by fiscal reporting tags (e.g., "Operating Revenue", "Current Assets") rather than by account codes.

```python
@api.model
def spreadsheet_fetch_balance_tag(self, args_list):
    results = []
    for args in args_list:
        tag_ids = [t for t in args.get('account_tag_ids', []) if t]
        if not tag_ids:
            results.append({'balance': 0})
            continue
        domain = self._build_spreadsheet_formula_domain(args)
        MoveLines = self.env["account.move.line"].with_company(company_id)
        [(balance,)] = MoveLines._read_group(domain, aggregates=['balance:sum'])
        results.append({'balance': balance or 0.0})
    return results
```

---

### `spreadsheet_move_line_action(args)`

Handles **cell audit** — when a user clicks on a formula cell, this opens a list view of matching journal entries.

```python
@api.readonly
@api.model
def spreadsheet_move_line_action(self, args):
    domain = self._build_spreadsheet_formula_domain(args, default_accounts=True)
    return {
        "type": "ir.actions.act_window",
        "res_model": "account.move.line",
        "view_mode": "list",
        "domain": domain,
        "name": _("Cell Audit"),
    }
```

---

### `get_account_group(account_types)`

Returns array of account codes grouped by account type. Used by spreadsheet templates to build dynamic account lists.

```python
@api.model
def get_account_group(self, account_types):
    data = self._read_group(
        [*self._check_company_domain(self.env.company),
         ("account_type", "in", account_types)],
        ['account_type'],
        ['code:array_agg'],
    )
    mapped = dict(data)
    return [mapped.get(at, []) for at in account_types]
```

---

## `res.company` Extensions

`spreadsheet_account` also extends `res.company` with:

```python
class ResCompany(models.Model):
    _inherit = "res.company"

    @api.readonly
    @api.model
    def get_fiscal_dates(self, payload):
        # Converts {date: "2024-06-15"} into {start: date, end: date}
        # using the company's fiscal year settings
        for data, company in zip(payload, companies):
            start, end = date_utils.get_fiscal_year(
                fields.Date.to_date(data["date"]),
                day=company.fiscalyear_last_day,
                month=int(company.fiscalyear_last_month),
            )
            results.append({"start": start, "end": end})
        return results
```

This allows the spreadsheet UI to display fiscal period labels correctly.

---

## Balance Sheet vs P&L Logic

A critical design detail in `_build_spreadsheet_formula_domain`:

**Balance Sheet accounts** (assets, liabilities — where `include_initial_balance = True`):
- Query: `date <= end` — includes all entries from the beginning of the fiscal year up to the period end
- This gives the **running/cumulative balance**

**P&L accounts** (revenue, expenses — where `include_initial_balance = False`):
- Query: `date >= start AND date <= end` — only the current period
- This gives the **period activity only**

This is what allows a single `ODOO.BALANCE("4000", "month", 6, 2024)` call to return the June revenue (not the cumulative revenue from Jan-Jun).

---

## Common Reporting Patterns

### Balance Sheet (Year-to-Date)

```
Assets:     =ODOO.BALANCE({"codes": ["1"], "date_range": {"range_type": "month", "month": 12, "year": 2024}})
Liabilities:=ODOO.BALANCE({"codes": ["2"], "date_range": {"range_type": "month", "month": 12, "year": 2024}})
Equity:     =ODOO.BALANCE({"codes": ["3"], "date_range": {"range_type": "month", "month": 12, "year": 2024}})
```

### P&L (Current Month)

```
Revenue:    =ODOO.BALANCE({"codes": ["4000"], "date_range": {"range_type": "month", "month": 6, "year": 2024}})
Expenses:   =ODOO.BALANCE({"codes": ["6000"], "date_range": {"range_type": "month", "month": 6, "year": 2024}})
Net Profit: =ODOO.BALANCE({"codes": ["4000"], ...}) - ODOO.BALANCE({"codes": ["6000"], ...})
```

### Accounts Receivable Aging

```
Jan Invoices: =ODOO.RESIDUAL({"codes": ["130000"], "date_range": {"range_type": "month", "month": 1, "year": 2024}})
```

---

## Key Design Decisions

1. **Batched queries**: `spreadsheet_fetch_debit_credit` accepts `args_list` (plural), allowing the JS client to batch multiple formula evaluations into a single RPC call for performance.

2. **`@api.readonly` decorator**: All RPC methods are decorated with `@api.readonly`, which automatically raises `AccessError` if called from non-readonly context. This is intentional — these methods should never modify data.

3. **`with_company(company_id)`**: Each formula execution switches to the target company's environment, ensuring correct data isolation in multi-company setups.

4. **`Domain` objects**: Uses the newer Odoo 16+ `Domain` class (from `odoo.fields`) instead of plain Python lists, enabling AND/OR composition for complex filters.

---

## See Also

- [Modules/Account](odoo-18/Modules/account.md) — account.move, account.move.line data model
- [Core/API](odoo-18/Core/API.md) — @api.model, @api.readonly decorators
- [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md) — Dashboard spreadsheets built on top of this module
- [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) — _read_group, Domain composition
