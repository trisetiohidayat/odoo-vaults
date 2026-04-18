---
type: module
module: l10n_bg_ledger
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Bulgaria Accounting Localization (`l10n_bg_ledger`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Report ledger for Bulgaria |
| **Technical** | `l10n_bg_ledger` |
| **Category** | Accounting/Localizations/Account Charts |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Report ledger for Bulgaria

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_bg` | Dependency |

## Technical Notes
- Country code: `bg` (Bulgaria)
- Localization type: accounting ledger reports
- Custom model files: account_move.py, account_journal.py

## Models

### `account.journal` (Extended)
Extends journal with Bulgaria-specific fields (VAT numbers, invoice type codes).

### `account.move` (Extended)
Extends journal entry with Bulgaria-specific fields for VAT ledger reporting.

## Related
- [Modules/l10n_bg](Modules/l10n_bg.md) — Core Bulgarian accounting chart