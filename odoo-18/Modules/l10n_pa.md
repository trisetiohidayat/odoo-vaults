---
Module: l10n_pa
Version: 18.0
Type: l10n/panama
Tags: #odoo18 #l10n #accounting #panama
---

# l10n_pa — Panama Accounting

## Overview
Panamanian accounting localization providing the Panamanian chart of accounts and tax templates. Co-authored by AHMNET CORP. Panama's accounting follows IFRS (NIIF) as they have been adopted in Panama. No specific mandatory chart of accounts by law.

## Country/Region
Panama (country code: PA)

## Dependencies
- account

## Key Models
No custom Python model classes. Template loader in `models/template_pa.py` loads the Panamanian chart of accounts.

## Chart of Accounts
Panamanian chart of accounts via `template_pa.py`. IFRS-aligned account structure.

## Tax Structure
Panama uses the territorial tax system (no VAT/income tax on foreign-sourced income). Basic tax templates configured for Panamanian requirements.

## Data Files
- `demo/demo_company.xml`: Demo company

## Installation
Install with accounting.

## Historical Notes
Panama has a territorial tax system — income tax is only applied to Panamanian-source income. There is no VAT (ITBMS is applied at 7% on goods and some services at final consumption). The module provides a basic chart that aligns with IFRS as Panama fully adopted NIIF.
