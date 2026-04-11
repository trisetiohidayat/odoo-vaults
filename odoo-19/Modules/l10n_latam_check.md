---
type: module
module: l10n_latam_check
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# LATAM Accounting Localization (`l10n_latam_check`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Own Checks Management |
| **Technical** | `l10n_latam_check` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Own Checks Management
---------------------

Extends 'Check Printing Base' module to manage own checks with more features:

* allow using own checks that are not printed but filled manually by the user
* allow to use deferred or electronic checks
  * printing is disabled
  * check number is set manually by the user
* add an optional "Check Cash-In Date" for post-dated checks (deferred payments)
* add a menu to track own checks

Third Party Checks Management
-----------------------------

Add new "Third party check Management" feature.

There are 2 main Payment Methods additions:

* New Third Party Checks:

  * Payments of this payment method represent the check you get from a customer when getting paid (from an invoice or a manual payment)

* Existing Third Party check.

  * Payments of this payment method are to track moves of the check, for eg:

    * Use a check to pay a vendor
    * Deposit the check on the bank
    * Get the check back from the bank (rejection)
    * Get the check back from the vendor (a rejection or return)
    * Transfer the check from one third party check journal to the other (one shop to another)

  * Those operations can be done with multiple checks at once

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |
| `base_vat` | Dependency |

## Technical Notes
- Country code: `latam`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_move.py, account_journal.py, account_move_line.py, account_payment_method.py, account_payment.py, account_chart_template.py, l10n_latam_check.py

## Related