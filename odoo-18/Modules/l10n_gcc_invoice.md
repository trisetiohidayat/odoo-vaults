---
Module: l10n_gcc_invoice
Version: 18.0
Type: l10n/gcc
Tags: #odoo18 #l10n #accounting #gcc
---

# l10n_gcc_invoice

## Overview
GCC framework module providing bilingual Arabic/English invoice report layouts for all Gulf Cooperation Council countries. This module is a dependency for most individual GCC country modules (`l10n_sa`, `l10n_ae`, `l10n_bh`, etc.) and extends `account.move` to support RTL Arabic formatting, dual-language product names, and tax amount computation on invoice lines.

## Region
Gulf Cooperation Council (GCC) — shared framework for Bahrain, Kuwait, Oman, Qatar, Saudi Arabia, UAE

## Dependencies
- account

## Key Models

### `AccountMove` (`account.move`)
Inherits `account.move`. Adds the following computed and translated fields:

- `l10n_gcc_invoice_tax_amount` — computed tax amount per line (`price_total - price_subtotal`)
- `l10n_gcc_line_name` — product name resolved in partner's language (`ar_001` or `en_US`)
- `narration` — Html-translated payment terms field
- `_get_name_invoice_report()` — overrides report selection: returns `l10n_gcc_invoice.arabic_english_invoice` for GCC country companies
- `_num2words(number, lang)` — converts numeric amounts to words using `num2words` library (with graceful fallback if library is missing)
- `_load_narration_translation()` — loads per-company English/Arabic payment terms translation into the narration field cache

### `AccountMoveLine` (`account.move.line`)
Inherits `account.move.line`.

- `l10n_gcc_invoice_tax_amount` — `Float`, computed via `_compute_tax_amount()`
- `l10n_gcc_line_name` — `Char`, computed via `_compute_l10n_gcc_line_name()` — resolves product display name in partner language when name matches the product's canonical Arabic or English name

### `ProductProduct` (`product.product`)
Inherits `product.product`. Overrides `_compute_display_name()` to insert a double-space between numeral-terminated substrings and Arabic-character-prefixed substrings (bidirectional text fix for Arabic numeral rendering in mixed-language reports).

## Data Files
- `views/report_invoice.xml` — QWeb report template `arabic_english_invoice` with dual-language (Arabic RTL / English LTR) tax invoice layout, tax totals table, and company/partner address blocks

## Chart of Accounts
No chart of accounts — this is a shared framework module. Individual country modules (`l10n_sa`, `l10n_ae`, etc.) provide country-specific charts.

## Tax Structure
No taxes defined — this module only provides the bilingual invoice report. Taxes are defined in individual country modules.

## Installation
Installed as a dependency by country-specific GCC modules (e.g., `l10n_sa` declares `l10n_gcc_invoice` in its `depends`). Can also be installed independently to enable bilingual invoice layouts for any GCC country company.

## Historical Notes
- Version 1.0.1 in Odoo 18
- `num2words` library dependency added for Arabic amount-to-text functionality
- `l10n_gcc_line_name` computed field solves display name inconsistency when products are defined in both Arabic and English
