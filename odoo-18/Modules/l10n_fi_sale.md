---
Module: l10n_fi_sale
Version: 18.0
Type: l10n/fi
Tags: #odoo18 #l10n #accounting
---

# l10n_fi_sale

## Overview
Finland sale extension for `l10n_fi` (Finnish base accounting). Adds Finnish-structured payment reference generation to sale orders using the Finnish reference format (viitenumero). The reference follows the Finnish banking standard: numeric base number + check digit calculated with 7-3-1 weighted sum.

## Country
[[Modules/Account|Finland]] 🇫🇮

## Dependencies
- l10n_fi
- sale

## Key Models

### SaleOrder
`models/sale.py` — extends `sale.order`
- `write()` — override: intercepts `reference` field writes and applies `compute_payment_reference_finnish()` to generate the check digit before saving
- `number2numeric(number)` — strips all non-digits, ensures 3-19 character length (pads short numbers with leading `11`)
- `get_finnish_check_digit(base_number)` — computes Finnish check digit: multiply digits from right-to-left with 7, 3, 1 repeating, sum, subtract from next decade (10 = 0)
- `compute_payment_reference_finnish(number)` — full pipeline: strip non-digits → validate length → compute check digit → return base + digit

## Data Files
No data files.

## Chart of Accounts
Inherits from [[Modules/Account|l10n_fi]].

## Tax Structure
Inherits from [[Modules/Account|l10n_fi]].

## Fiscal Positions
Inherits from [[Modules/Account|l10n_fi]].

## EDI/Fiscal Reporting
Finnish payment references generated here are used by `l10n_fi` invoice reference model for customer payment matching.

## Installation
`auto_install: True` — auto-installed with `sale` when `l10n_fi` is installed.

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.0; Finnish reference format has been stable
- The 7-3-1 weighted checksum algorithm is the standard Finnish bank reference algorithm (Finvoice EDI standard)
- Sale order reference generation complements `account.move` reference generation from `l10n_fi` for invoices

**Performance Notes:**
- Pure Python reference computation; no external libraries, no database queries
- Check digit calculation is O(n) where n = reference length (typically 7-19 digits)