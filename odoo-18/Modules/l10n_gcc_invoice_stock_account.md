---
Module: l10n_gcc_invoice_stock_account
Version: 18.0
Type: l10n/gcc
Tags: #odoo18 #l10n #accounting #gcc
---

# l10n_gcc_invoice_stock_account

## Overview
Extension of `l10n_gcc_invoice` that adds Arabic/English invoice report support for companies using stock/lot tracking (stock valuation, landed costs, or serial number management). Combines the bilingual invoice report from `l10n_gcc_invoice` with `stock_account` functionality.

## Region
Gulf Cooperation Council (GCC) — shared framework

## Dependencies
- l10n_gcc_invoice
- stock_account

## Key Models
No Python model classes — pure data/UI extension.

## Data Files
- `views/report_invoice.xml` — overrides `arabic_english_invoice` report to include lot/SN columns for inventory-tracked products on the invoice print layout

## Chart of Accounts
No chart of accounts.

## Tax Structure
No taxes.

## Installation
Auto-installed (`auto_install: True`) when both dependencies are present. Intended for GCC companies running warehouse/stock management alongside accounting.

## Historical Notes
- Version 1.0 in Odoo 18
- Split from `l10n_gcc_invoice` to isolate WMS (Warehouse Management System) concerns from the core bilingual invoice report
