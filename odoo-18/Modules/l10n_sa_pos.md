---
Module: l10n_sa_pos
Version: 18.0
Type: l10n/saudi #pos
Tags: #odoo18 #l10n #accounting #saudi #gcc #pos
---

# l10n_sa_pos

## Overview
Saudi Arabia Point of Sale localization. Extends the POS order-to-invoice flow to populate ZATCA confirmation datetime on POS invoices, ensuring they comply with Saudi e-invoicing requirements. Adds ZXing barcode library for QR code generation in receipts.

See also: [Modules/l10n_sa](modules/l10n_sa.md) (accounting), [Modules/l10n_gcc_pos](modules/l10n_gcc_pos.md) (GCC POS framework)

## Country
Kingdom of Saudi Arabia

## Dependencies
- l10n_gcc_pos
- l10n_sa

## Key Models

### `pos_config` (`pos.config`)
Inherits `pos.config`. Overrides `open_ui()` to validate that the company has a country set before opening a POS session (via `l10n_gcc_pos`).

### `POSOrder` (`pos.order`)
Inherits `pos.order`. Overrides `_prepare_invoice_vals()` — when creating invoice vals for a POS order from a Saudi company, copies `l10n_sa_confirmation_datetime` from `date_order`. This ensures POS receipts carry the ZATCA-compliant confirmation timestamp from the moment of sale.

## Data Files
No XML data files.

## Static Assets
- `web/static/lib/zxing-library/zxing-library.js` — JavaScript library for QR code generation in POS receipts
- `l10n_sa_pos/static/src/**/*` — Saudi-specific POS UI components
- `l10n_sa_pos/static/tests/**/*` — tour and unit tests for Saudi POS

## Chart of Accounts
No chart of accounts — depends on `l10n_sa` for the chart.

## Tax Structure
No taxes — inherits from `l10n_sa`.

## Installation
`auto_install: True` — automatically installed when `l10n_sa` is installed (POS and `l10n_gcc_pos` are also required).

## Historical Notes
- Odoo 18 new module (no equivalent in Odoo 17)
- QR code generation in POS receipts uses the ZXing library loaded as a web asset
