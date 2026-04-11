---
Module: l10n_in_withholding_payment
Version: 18.0
Type: l10n/india
Tags: #odoo18 #l10n #accounting #india #tds #withholding #payment
---

# l10n_in_withholding_payment — Indian TDS for Payment

## Overview
Extends `l10n_in_withholding` to integrate TDS deduction tracking into the Payment app. Enables automatic TDS deduction when processing vendor payments, matches TDS certificates, and reconciles TDS payable entries. Part of the Indian withholding tax workflow.

## Country
India

## Dependencies
- l10n_in_withholding

Auto-install: `True`

## Key Models

### `AccountMove` (`account.move`) — account_move.py
- `_inherit = "account.move"`
- Integrates TDS tracking into payment journal entries

### `AccountPayment` (`account.payment`) — account_payment.py
- `_inherit = "account.payment"`
- `_compute_l10n_in_total_withholding_amount()` — computes TDS deducted in payment
- TDS fields on payments: `l10n_in_withholding_line_ids` (from `l10n_in_withholding`)

## Installation
`auto_install = True`. Auto-installs as part of Indian withholding tax stack (l10n_in_withholding + account).

## Historical Notes
New in Odoo 18. Integrates the TDS withholding mechanism with the payment reconciliation workflow, allowing automatic TDS certificate matching against payments.