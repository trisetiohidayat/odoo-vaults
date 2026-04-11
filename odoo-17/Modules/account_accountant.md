---
tags: [odoo, odoo17, module, account_accountant]
---

# Account Accountant Module

**Status: NOT PRESENT in Odoo 17**

In Odoo 17, the `account_accountant` module has been removed. Its features have been consolidated into the core `account` module.

## Historical Context

In Odoo versions prior to 17, `account_accountant` provided:
- Bank statement import (CAMT, CSV, OFX)
- Recurring journal entries
- Deferred revenue/expense management
- Lock dates for period closing
- Enhanced chart of accounts views

## Odoo 17 Replacement

In Odoo 17, these features are now part of `account`:

| Old `account_accountant` Feature | Odoo 17 Location |
|----------------------------------|------------------|
| Bank statement import | `account.account_bank_statement_import` |
| Recurring entries | `account.account_reconcile_model` (scheduled) |
| Deferred revenue/expenses | `account.deferred.amount` |
| Lock dates | `account.move` / company settings |
| Accountant dashboard | Built into `account` dashboard |

## See Also
- [[Modules/Account]] — Core accounting in Odoo 17
