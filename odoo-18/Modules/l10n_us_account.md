---
Module: l10n_us_account
Version: 18.0
Type: l10n/united_states
Tags: #odoo18 #l10n #accounting #united_states
---

# l10n_us_account — United States Accounting

## Overview
The United States accounting extension module builds on `l10n_us` to add full accounting chart capabilities for US companies. It combines the base US localization with `account` to provide the accounting framework. It currently has no Python model files — it acts purely as a meta-module that wires `l10n_us` and `account` together and marks itself auto-installable.

## Country
United States of America (`US`)

## Dependencies
- `l10n_us`
- [account](modules/account.md)

## Key Models
No Python model files. No chart template is defined here — the US chart of accounts is likely defined in the `account` module itself or in a separate data package.

## Data Files
None (no `data/` directory in this module).

## Chart of Accounts
No chart template is defined in this module. The US chart of accounts structure (taxes, accounts, fiscal positions) is loaded from the `account` module's bundled `l10n_us` data when the company is configured for the US. This is a notable architectural choice — US accounting data lives in `account` rather than in `l10n_us_account`.

## Tax Structure
No taxes defined in this module. US sales tax (which is origin-based or destination-based depending on state) is typically managed through the `l10n_us` data files in `account` or through fiscal positions on partners.

## Installation
Install automatically with `account` when a US company is configured. The module has no standalone installable configuration beyond its dependency chain.

## Historical Notes
- **Odoo 17 → 18:** The module structure is unchanged from Odoo 17. It serves as a thin wiring layer.
- This module does not include a chart template; users needing US accounting charts install this module alongside `account` and the chart template is loaded from the account module's internal l10n data.
