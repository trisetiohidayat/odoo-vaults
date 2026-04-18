---
Module: l10n_ch_pos
Version: 18.0
Type: l10n/ch
Tags: #odoo18 #l10n #pos
---

# l10n_ch_pos

## Overview
Swiss Point of Sale localization. Extends `point_of_sale` and `l10n_ch` to handle Swiss-specific bank partner requirements in POS. Specifically, for Swiss POS orders, the partner bank account (required for QR payment/BIC IBAN) is only set when the payment method is not "Pay Later" — cash/card payments should not trigger the bank partner requirement.

## Country
[Switzerland](Modules/account.md) 🇨🇭 (non-EU)

## Dependencies
- l10n_ch
- point_of_sale

## Key Models

### PosOrder
`models/pos_order.py` — extends `pos.order`
- `_get_partner_bank_id()` — override: for Swiss orders (`company_id.country_code == 'CH'`), returns `False` (no partner bank) if any payment uses a method without a journal (i.e., "Pay Later"). Returns the standard `super()` result for cash/card payments. This prevents unnecessary bank partner validation on credit/revolving payments.

## Data Files
No data files.

## Chart of Accounts
Inherits from [l10n_ch](Modules/account.md) (Swiss chart).

## Tax Structure
Inherits from [l10n_ch](Modules/account.md) (Swiss VAT: 8.1% standard, 2.6% reduced, 0% exlude).

## Fiscal Positions
Inherits from [l10n_ch](Modules/account.md).

## EDI/Fiscal Reporting
Swiss QR-bill / ESR payment references handled by `l10n_ch`.

## Installation
`auto_install: True` — auto-installed for Swiss POS use cases.

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.0; Swiss POS localization is a lightweight adaptation
- Swiss Twint / QR-bill payment flows differ from EU SEPA credit transfer
- The Pay Later distinction prevents false validation errors on invoice-invoice settlements

**Performance Notes:**
- Very lightweight — single method override, no database queries