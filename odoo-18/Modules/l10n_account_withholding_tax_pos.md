---
Module: l10n_account_withholding_tax_pos
Version: 18.0
Type: l10n/accounting
Tags: #odoo18 #l10n #accounting #pos #withholding
---

# l10n_account_withholding_tax_pos

## Overview
Extends the generic `l10n_account_withholding_tax` module to make withholding taxes available within the Point of Sale. By adding the `is_withholding_tax_on_payment` field to the POS tax field list, the POS client can correctly handle withholding taxes when computing order totals at payment time.

## EDI Format / Standard
Not an EDI module. Complements the withholding tax engine for POS use.

## Dependencies
- `l10n_account_withholding_tax` -- generic withholding tax module
- `point_of_sale` -- POS framework

## Key Models

### `account.tax` (`l10n_account_withholding_tax_pos.account_tax`)
Inherits: `account.tax`

- `_load_pos_data_fields()` -- adds `is_withholding_tax_on_payment` to the POS data field list so it is shipped to the POS client and available in `batch_for_taxes_computation`

## Data Files
None.

## How It Works
The POS client computes taxes in JavaScript. By including `is_withholding_tax_on_payment` in the field list returned by `_load_pos_data_fields()`, the client-side tax computation engine receives the flag and correctly processes withholding taxes when processing POS orders.

## Installation
Auto-installs with `l10n_account_withholding_tax`. Install after both dependencies.

## Historical Notes
In Odoo 17, the POS did not have a mechanism to propagate `is_withholding_tax_on_payment` to the client. The POS-side computation was unaware of withholding taxes, potentially causing totals to be incorrect. Odoo 18 introduced `_load_pos_data_fields()` as the mechanism to inject any additional tax-related fields needed by the client.
