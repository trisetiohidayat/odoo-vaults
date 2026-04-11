---
Module: l10n_bg_ledger
Version: 18.0
Type: l10n/bulgaria-report
Tags: #odoo18 #l10n #accounting
---

# l10n_bg_ledger

## Overview
Companion module to `[[Modules/l10n_bg]]` that adds Bulgarian-specific report ledger and journal views for enhanced financial reporting compliance.

## Country
Bulgaria

## Dependencies
- l10n_bg

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_journal.py | `AccountJournal` | (base) |
| account_move.py | `AccountMove` | (base) |

Extends `AccountJournal` and `AccountMove` with Bulgarian-specific view definitions.

## Data Files
No CSV data files — module consists of view definitions (XML) only.

## Chart of Accounts
Inherits chart of accounts from `[[Modules/l10n_bg]]` (332 accounts).

## Tax Structure
Inherits tax structure from `[[Modules/l10n_bg]]`.

## Fiscal Positions
Inherits fiscal positions from `[[Modules/l10n_bg]]`.

## EDI/Fiscal Reporting
Bulgarian report ledger views for VAT declaration and audit trail reporting.

## Installation
Auto-installed as a dependency of `[[Modules/l10n_bg]]` (`auto_install: True`). Installs automatically when l10n_bg is loaded.

## Historical Notes
- Introduced in Odoo 18 as a separate module to cleanly separate chart-of-accounts data from report view definitions.
