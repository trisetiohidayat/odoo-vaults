---
type: module
module: l10n_account_edi_ubl_cii_tests
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# ACCOUNT Accounting Localization (`l10n_account_edi_ubl_cii_tests`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This module tests the module 'account_edi_ubl_cii', it is separated since dependencies to some |
| **Technical** | `l10n_account_edi_ubl_cii_tests` |
| **Category** | Accounting/Accounting |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This module tests the module 'account_edi_ubl_cii', it is separated since dependencies to some
localizations were required. Its name begins with 'l10n' to not overload runbot.

The test files are separated by sources, they were taken from:

* the factur-x doc (form the FNFE)
* the peppol-bis-invoice-3 doc (the github repository: https://github.com/OpenPEPPOL/peppol-bis-invoice-3/tree/master/rules/examples contains examples)
* odoo, these files pass all validation tests (using ecosio or the FNFE validator)

We test that the external examples are correctly imported (currency, total amount and total tax match).
We also test that generating xml from odoo with given parameters gives exactly the same xml as the expected,
valid ones.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account_edi_ubl_cii` | Dependency |
| `l10n_fr_account` | Dependency |
| `l10n_be` | Dependency |
| `l10n_de` | Dependency |
| `l10n_nl` | Dependency |
| `l10n_au` | Dependency |

## Technical Notes
- Country code: `account`
- Localization type: accounting chart, taxes, and fiscal positions

## Related