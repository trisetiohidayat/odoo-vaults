---
Module: account_test
Version: 18.0
Type: addon
Tags: #account, #test
---

# account_test — Accounting Consistency Tests

## Module Overview

**Category:** Accounting/Accounting
**Depends:** `account`
**License:** LGPL-3
**Installable:** True

Allows manual execution of accounting consistency checks. Administrators can write SQL queries as test cases and generate PDF reports of results from **Reporting > Accounting > Accounting Tests**.

## Data Files

- `security/ir.model.access.csv` — ACL for `accounting.assert.test`
- `views/accounting_assert_test_views.xml` — Form/list views for test definitions
- `report/accounting_assert_test_reports.xml` — Report action definitions
- `data/accounting_assert_test_data.xml` — Default test records
- `report/report_account_test_templates.xml` — QWeb report templates

## Models

### `accounting.assert.test` (`accounting.assert.test`)

Stores named SQL-based accounting test definitions.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Test name (required, indexed, translatable) |
| `desc` | Text | Test description (indexed, translatable) |
| `code_exec` | Text | Python code executed via `safe_eval`; default queries `account_journal` codes |
| `active` | Boolean | Whether the test is active (default: True) |
| `sequence` | Integer | Display order (default: 10) |

**Notes:**
- The default `code_exec` queries all journal codes and stores results in a `result` variable.
- Helper function `reconciled_inv()` is injected into the eval context — returns IDs of reconciled invoices.
- Helper `order_columns(item, cols)` formats dict output with columns in specified order.

### `report.account_test.report_accounttest` (Abstract Report Model)

Abstract model (`_name = 'report.account_test.report_accounttest'`) that provides the PDF report logic.

**Methods:**

**`@api.model _execute_code(code_exec)`**
Executes a test's Python code in a sandboxed `safe_eval` context with:
- `cr` — database cursor
- `uid` — current user ID
- `result` — output variable (list/dict/set), displayed in the PDF
- `column_order` — optional list of field names for dict result ordering
- `reconciled_inv()` — helper function
- `_` — translation function

Returns a list of formatted result strings. Returns `['The test was passed successfully']` if result is empty/falsy.

**`@api.model _get_report_values(docids, data)`**
Called by the report framework. Loads the `accounting.assert.test` records and returns a dict of values including `execute_code` callable for use in QWeb templates.

## What It Extends

- Extends `account` with a test harness for running arbitrary SQL queries against the accounting schema and rendering results in PDF.

## Key Behavior

- Tests run in `exec` mode (not `eval`) — full Python statements allowed.
- SQL is executed directly via `cr.execute()` inside the safe eval context.
- Results must be a `list`, `tuple`, or `set` of strings or dicts.
- The PDF report lists all tests with their results.

## See Also

- [Modules/Account](Modules/Account.md) — the base accounting module
- [Core/ORM Operations](Core/ORM-Operations.md) — safe_eval context
