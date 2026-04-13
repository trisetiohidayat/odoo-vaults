---
type: module
module: l10n_account_withholding_tax
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# ACCOUNT Accounting Localization (`l10n_account_withholding_tax`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Allows to register withholding taxes during the payment of an invoice or bill. |
| **Technical** | `l10n_account_withholding_tax` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Allows to register withholding taxes during the payment of an invoice or bill.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |

## Technical Notes
- Country code: generic (withholding tax framework)
- Localization type: withholding tax framework
- Custom model files: account_tax.py, product_template.py, account_payment.py, account_payment_withholding_line.py, res_company.py, res_config_settings.py, account_withholding_line.py

## Models

### `account.withholding.line` (Abstract, Analytic Mixin)
Abstract model for withholding tax lines in the payment/register wizard.

**Fields:**
- `name` — Sequence number
- `placeholder_type` — `given_by_sequence`, `given_by_name`, `not_defined`
- `tax_id` — The withholding tax (filtered to `is_withholding_tax_on_payment=True`)
- `withholding_sequence_id` — Related from `tax_id`
- `source_base_amount_currency`, `source_base_amount` — Base amount
- `source_tax_amount_currency`, `source_tax_amount` — Tax amount
- `base_amount` — Computed withholding base
- `amount` — Computed withholding amount
- `source_currency_id`, `source_tax_id`
- `original_base_amount`, `original_tax_amount`

**Key Methods:**
- `_compute_placeholder_type()`, `_compute_type_tax_use()`
- `_compute_original_amounts()` — From invoice lines
- `_compute_base_amount()` — Withholding base computation
- `_compute_amount()` — Withholding amount computation

### `account.tax` (Extended)
Adds withholding-specific fields:
- `is_withholding_tax_on_payment` — Marks tax as withholding
- `withholding_sequence_id` — IrSequence for numbering

### `account.payment` (Extended)
Extends payment with withholding lines:
- `withholding_line_ids` — One2many to `account.payment.withholding.line`

### `account.payment.withholding.line` (Concrete)
Concrete implementation of `account.withholding.line` on payments.

### `product.template` (Extended)
Excludes products from withholding base when configured.

### `res.company` (Extended)
Per-company withholding account configuration.

## Related
- [Modules/Account](Modules/account.md) — Core accounting
- [Modules/account_tax_python](Modules/account_tax_python.md) — Tax computation in Python