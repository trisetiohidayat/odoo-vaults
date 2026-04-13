---
type: module
module: account_test
tags: [odoo, odoo19, account, invoicing, accounting, test, reporting]
created: 2026-04-06
updated: 2026-04-11
---

# Accounting Consistency Tests

## Overview

| Property | Value |
|----------|-------|
| **Name** | Accounting Consistency Tests |
| **Technical** | `account_test` |
| **Category** | Accounting/Accounting |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `account` |
| **Source** | `odoo/addons/account_test/` |

## Description

Allows accountants to write arbitrary SQL-based consistency checks via the UI. Each test is stored as a record of `accounting.assert.test` with a Python code block executed against the live database via `safe_eval`. Results are rendered in a QWeb PDF report. Access: **Reporting > Accounting > Accounting Tests** (requires developer mode / `base.group_no_one`).

## Architecture

```
account_test/
├── models/
│   └── accounting_assert_test.py     # Thin model: only fields, no methods
├── report/
│   ├── report_account_test.py        # Abstract model: _execute_code() + helpers
│   └── report_account_test_templates.xml  # QWeb PDF template
├── views/
│   └── accounting_assert_test_views.xml   # Tree, form, search views
├── data/
│   └── accounting_assert_test_data.xml    # Demo test records
└── security/
    └── ir.model.access.csv           # ACL for accounting.assert.test
```

The critical architectural point: `accounting.assert.test` is a pure data container with **no custom Python methods**. All test execution logic lives in the `report.account_test.report_accounttest` abstract model.

---

## L1: Module Purpose and Scope

The module serves as an in-database accounting audit framework. It is not a unit-test framework (those live in `tests/` directories); instead it allows end-users (accountants, auditors) to define and run SQL-query-based consistency checks directly from the Odoo UI.

**Use cases:**
- Detect unbalanced journal entries
- Find invoices in inconsistent states (paid but still "open")
- Check that reconciled journal items belong to reconciled invoices
- Verify bank statement closing balance arithmetic

**Security model:** Only accessible to users in `base.group_no_one` (effectively developer mode). The `code_exec` field contains raw Python code that runs with the database cursor — this is intentionally restricted to trusted technical users.

---

## L2: Field Types, Defaults, Constraints

### `accounting.assert.test`

**File:** `models/accounting_assert_test.py`

```python
class AccountingAssertTest(models.Model):
    _name = 'accounting.assert.test'
    _description = 'Accounting Assert Test'
    _order = "sequence"              # Sort by sequence in list views
```

| Field | Type | Required | Default | Storage | Notes |
|-------|------|---------|---------|---------|-------|
| `name` | `Char` | Yes | — | DB | Test name; translatable (`translate=True`) |
| `desc` | `Text` | No | — | DB | Test description; translatable |
| `code_exec` | `Text` | Yes | `CODE_EXEC_DEFAULT` | DB | Python/SQL code block |
| `active` | `Boolean` | — | `True` | DB | Toggle test on/off |
| `sequence` | `Integer` | — | `10` | DB | Display order |

**No `@api.constrains`, no `@api.onchange`, no custom methods** — the model is intentionally minimal.

**`CODE_EXEC_DEFAULT`:**
```python
CODE_EXEC_DEFAULT = '''\
res = []
cr.execute("select id, code from account_journal")
for record in cr.dictfetchall():
    res.append(record['code'])
result = res
'''
```

**ACL:** `ir.model.access.csv` grants full CRUD to `base.group_no_one` only.

### `report.account_test.report_accounttest` (Abstract Model)

**File:** `report/report_account_test.py`

```python
class ReportAccount_TestReport_Accounttest(models.AbstractModel):
    _name = 'report.account_test.report_accounttest'
    _description = 'Account Test Report'
```

The `_execute_code` method provides the runtime context for user-supplied Python code:

```python
context = {
    'cr':        self.env.cr,          # Database cursor
    'uid':       self.env.uid,          # Current user ID
    'result':    None,                  # Output variable
    'column_order': None,               # Display column order hint
    'reconciled_inv': reconciled_inv,    # Helper: IDs of reconciled moves
    '_': lambda *a, **kw: self.env._(*a, **kw),  # Translation function
}
safe_eval(code_exec, context, mode="exec")
```

**Result handling:**
- `result` must be a `list`, `tuple`, or `set`
- Empty list = test passed successfully (displays "The test was passed successfully")
- Non-empty list = test failed; each item is formatted as a string
- Dictionary items use `column_order` to control display order
- `_execute_code` returns a list of display strings

**`reconciled_inv()` helper:**
```python
def reconciled_inv():
    return self.env['account.move'].search([('reconciled', '=', True)]).ids
```
Returns IDs of all moves marked as reconciled.

---

## L3: Cross-Model, Override Patterns, Workflow Triggers

### Cross-Model Relationships

| Model | Relationship | Direction | Purpose |
|-------|-------------|-----------|---------|
| `accounting.assert.test` | Standalone | — | No cross-model FK fields; test code queries other models directly |
| `account.move` | Direct SQL join | Read | Test 3, 5, 5.2, 6 query `account_move` via `cr.execute()` |
| `account.move.line` | Direct SQL join | Read | Test 3, 4, 5.1, 5.2 query `account_move_line` via `cr.execute()` |
| `account.journal` | Direct SQL query | Read | Test 1 default code queries `account_journal` |
| `account.account` | Direct SQL join | Read | Test 3, 8 query `account_account` |
| `account.bank.statement` | Direct SQL join | Read | Test 7 queries `account_bank_statement` |

The module does **not** use Odoo's ORM for reads in tests; it uses raw `cr.execute()`. This bypasses record rules but is intentional — auditors need direct database access for consistency checks.

### Override Patterns

No override of existing models. This module only:
1. Creates a new model (`accounting.assert.test`)
2. Creates a new abstract report model (`report.account_test.report_accounttest`)
3. Registers QWeb report template and action

### Workflow Trigger

Test execution is triggered entirely from the **Print** button on the QWeb report action (`ir.actions.report` bound to `accounting.assert.test`):

```xml
<!-- report/accounting_assert_test_reports.xml -->
<record id="account_assert_test_report" model="ir.actions.report">
    <field name="name">Accounting Tests</field>
    <field name="model">accounting.assert.test</field>
    <field name="report_type">qweb-pdf</field>
    <field name="report_name">account_test.report_accounttest</field>
    <field name="binding_model_id" ref="model_accounting_assert_test"/>
    <field name="binding_type">report</field>
</record>
```

The QWeb template calls `_execute_code` to run each test:

```xml
<!-- report/report_account_test_templates.xml -->
<t t-foreach="execute_code(o.code_exec)" t-as="test_result">
    <span t-out="test_result"/>
</t>
```

### Demo Test Records (Data File)

The module ships 6 active demo tests in `data/accounting_assert_test_data.xml`:

| ID | Name | SQL Target | Status |
|----|------|-----------|--------|
| `account_test_01` | General balance | `account_move` — debit/credit sum | Active |
| `account_test_03` | Movement lines | `account_move` + `account_move_line` — balanced, date consistency | Active |
| `account_test_05` | Payable/Receivable reconciliation | `account_move` + `account_move_line` + `account_account` | Active |
| `account_test_05_2` | Reconciled invoices and accounts | Same models | Active |
| `account_test_06` | Invoices status | `account_move` — paid/reconciled not open | Active |
| `account_test_07` | Closing balance on bank statements | `account_bank_statement` — arithmetic check | Active |

Two tests are commented out (with `<!-- TODO -->`) because they use deprecated models:
- **Test 4** (reconciled items): uses `account_move_reconcile`, `account.period` (removed in Odoo 14+)
- **Test 8** (accounts and partners on moves): uses `account.period` (removed in Odoo 14+)

---

## L4: Version Changes Odoo 18 → 19

### Module-Level

No structural changes to `account_test` between Odoo 18 and Odoo 19. The module:
- Still uses `version: '1.0'` in `__manifest__.py`
- No changes to models, views, or data files
- ACL file still uses the same format

### Key Architectural Observations for Odoo 18+

**Demo tests use deprecated table names.** Several demo SQL queries reference `account_invoice` (consolidated into `account.move` in Odoo 14) and `account_bank_statement` (renamed `account.bank.statement` in Odoo 14). In practice:
- `account_move` replaced `account_invoice` as the base table for invoices
- `account_bank_statement` replaced `account_bank_statement` as the model name but the table name changed too

These demo tests will silently fail or return incorrect results on databases that have migrated fully to the new model structure. They are demo data, not production tests.

**Security note:** The `safe_eval` usage in `_execute_code` is intentionally limited — only whitelisted names (`cr`, `uid`, `result`, etc.) are passed in the context. However, `cr` gives full database write access. In Odoo 19, the access is still bounded by the PostgreSQL user permissions and the Odoo database user running the process.

### `account_test` in the Module Ecosystem

`account_tax_python/models/__init__.py` imports `accounting_assert_test`:
```python
from . import accounting_assert_test
```

This is a **load-order dependency**, not a functional one. The `account_tax_python` module's tests subclass `TestTaxCommonAccountTaxPython` which inherits from `TestTaxCommon` in the `account` module. The import of `accounting_assert_test` ensures the model is registered before `account_tax_python`'s test helpers try to reference it, but the model itself is not used by `account_tax_python`.

---

## Related

- [Modules/account](Account.md)
