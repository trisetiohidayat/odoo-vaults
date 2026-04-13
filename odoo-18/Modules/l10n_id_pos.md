---
Module: l10n_id_pos
Version: 18.0
Type: l10n/indonesia
Tags: #odoo18 #l10n #accounting #pos #indonesia
---

# l10n_id_pos — Indonesian Point of Sale

## Overview
Indonesian POS extension adding QRIS payment verification support to the Point of Sale module. Works in conjunction with [Modules/l10n_id](Modules/l10n_id.md) to enable QRIS-based payment and order tracking at POS terminals.

## Country
Indonesia

## Dependencies
- l10n_id
- point_of_sale

## Key Models

### `PosOrder` (`pos.order`)
- `_inherit = 'pos.order'`
- Inherits QRIS transaction linkage from `l10n_id` via `l10n_id.qris.transaction`

### `PosPaymentMethod` (`pos.payment.method`)
- `_inherit = 'pos.payment.method'`
- Adds `l10n_id_verify_qris_status(trx_uuid)` — verifies QRIS payment status by transaction UUID
- Calls `l10n_id.qris.transaction._get_latest_transaction('pos.order', trx_uuid)`
- Returns `True` if paid, raises `UserError` if no transaction found

### `QRISTransaction` (`l10n_id.qris.transaction`)
- `_inherit = 'l10n_id.qris.transaction'`
- Extends the QRIS transaction model from base `l10n_id` for POS-specific usage (pos.order linkage)

## Data Files
No separate data files — inherits all QRIS data structures from [Modules/l10n_id](Modules/l10n_id.md).

## QRIS POS Flow
1. POS order payment via QRIS method → transaction UUID recorded
2. Customer scans QRIS code and completes payment
3. POS calls `l10n_id_verify_qris_status(trx_uuid)` to check payment status
4. Order status updated based on QRIS payment result

## Installation
Auto-installs with its dependencies. Part of the Indonesian POS stack: `l10n_id` + `point_of_sale` + `l10n_id_pos`.

## Historical Notes
Version 1.0 in Odoo 18. Extends the QRIS payment mechanism from [Modules/l10n_id](Modules/l10n_id.md) into the POS workflow.