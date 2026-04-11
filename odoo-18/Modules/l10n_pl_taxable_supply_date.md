---
Module: l10n_pl_taxable_supply_date
Version: 18.0
Type: l10n/pl
Tags: #odoo18 #l10n #accounting
---

# l10n_pl_taxable_supply_date

## Overview
Poland-specific extension to `l10n_pl` that adds support for the taxable supply date (data powstania obowiązku podatkowego). In Polish VAT law, the tax point can differ from the invoice date — this module ensures the accounting date and currency rate are based on the taxable supply date rather than the invoice date.

## Country
Poland

## Dependencies
- l10n_pl

## Key Models

### AccountMove
`models/account_move.py` — extends `account.move`
- `taxable_supply_date` (Date) — the date when VAT obligation arises (Polish tax point)
- `_get_accounting_date_source()` — override: if `country_code == 'PL'` and `taxable_supply_date` is set, returns `taxable_supply_date` instead of invoice date (determines accounting period)
- `_compute_date()` — recomputes accounting date when `taxable_supply_date` changes
- `_compute_invoice_currency_rate()` — recomputes currency rate based on taxable supply date (Polish tax law requires FX rate from tax point date)
- `_get_invoice_currency_rate_date()` — override: if PL and taxable supply date set, use it as rate date instead of invoice date

## Data Files
No data files.

## Chart of Accounts
Inherits chart from `l10n_pl`.

## Tax Structure
Inherits from `l10n_pl`.

## Fiscal Positions
Inherits from `l10n_pl`.

## EDI/Fiscal Reporting
SAF-T/JPK reports use the taxable supply date as the tax period determination date.

## Installation
`auto_install: True` — auto-installed with parent l10n_pl. No demo data.

## Historical Notes
**Odoo 17 → 18 changes:**
- New in recent versions; previously the taxable supply date had to be manually set via invoice date override
- Direct integration with `_compute_invoice_currency_rate` is a newer pattern ensuring correct foreign-currency VAT calculations under Polish law
- JPK_V7M and JPK_VAT declarations now reference the taxable supply date for correct period assignment

**Performance Notes:**
- Minimal overhead — only adds date computations on invoice write
- Does not trigger full recomputation; only dependent fields recalculate
