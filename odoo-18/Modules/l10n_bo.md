---
Module: l10n_bo
Version: 18.0
Type: l10n/bolivia
Tags: #odoo18 #l10n #accounting #bolivia
---

# l10n_bo — Bolivia Accounting

## Overview
Minimal accounting chart for Bolivia, providing the PCGE (Plan Contable Boliviano) structure and basic tax templates. Bolivia has no mandatory chart of accounts by law; this module provides a recommended structure aligned with SIENT (Sistema Informatico de Normalizacion Empresarial). Co-authored by Cubic ERP.

## Country/Region
Bolivia (country code: BO)

## Dependencies
- account

## Key Models
No custom model classes. Only template data loaded via `__init__.py` from `models/template_bo.py` (chart of account template loader).

## Chart of Accounts
Plan Contable Boliviano aligned with SIENT norms. 4-digit account structure covering assets, liabilities, equity, revenue, and expenses.

## Tax Structure
Basic tax templates for Bolivia. Specific rates and types configured via chart template data. Contact [Modules/l10n_latam_base](modules/l10n_latam_base.md) for extended identification types if needed.

## Data Files
- `data/account_tax_report_data.xml`: Tax report structure
- `demo/demo_company.xml`: Demo company "BO Company" with chart installed

## Installation
Install with accounting module. Chart template is loaded via demo data. The module has no custom Python model classes.

## Historical Notes
Version 2.0. Minimal module — Bolivia's accounting regulation does not mandate a specific chart, so Odoo's default provides a starting point that can be customized per company need.
