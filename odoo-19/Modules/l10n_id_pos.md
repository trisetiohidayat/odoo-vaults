# Indonesia - Point of Sale (`l10n_id_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Indonesia - Point of Sale |
| **Technical** | `l10n_id_pos` |
| **Category** | Accounting/Localizations/POS |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_id`, `point_of_sale` |

## Description
Indonesian Point of Sale with QRIS (Quick Response Code Indonesian Standard) payment integration. QRIS is the national QR code standard mandated by BI (Bank Indonesia) for cashless payments. Links POS orders to QRIS transactions for tracking and reconciliation.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_id` | Core Indonesian accounting (includes QRIS transaction model) |
| `point_of_sale` | Base POS module |

## Technical Notes
- Country code: `id` (Indonesia)
- Payment: QRIS (Quick Response Code Indonesian Standard)
- Core model: `l10n_id.qris.transaction` (inherited from `l10n_id`)

## Models

### `pos.order` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `l10n_id_qris_transaction_ids` | Many2many | QRIS transactions linked to this POS order (referenced in `l10n_id` QRIS model for payment flow tracking) |

### `l10n_id.qris.transaction` (Extended)
QRIS transaction model from `l10n_id` is extended to support POS.

**Key methods:**
- `_get_supported_models()` — EXTENDS `l10n_id`. Adds `'pos.order'` to the list of models that can initiate QRIS payments
- `_get_record()` — OVERRIDES `l10n_id`. Resolves a QRIS transaction to its source `pos.order` by searching on `uuid`

### `pos.payment.method` (Extended)
Adds QRIS as a payment method type for POS terminals in Indonesia.

## QRIS Payment Flow
1. POS order total is converted to QRIS code
2. Customer scans QRIS with any BI-compliant e-wallet/banking app
3. QRIS transaction record is created and linked to `pos.order` via `l10n_id_qris_transaction_ids`
4. Transaction state tracked via `l10n_id.qris.transaction` model

## Related
- [Modules/l10n_id](modules/l10n_id.md) — Core Indonesian accounting (contains QRIS model)
- [Modules/point_of_sale](modules/point_of_sale.md) — Base POS module
