# Saudi Arabia - Point of Sale (`l10n_sa_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Saudi Arabia - Point of Sale |
| **Technical** | `l10n_sa_pos` |
| **Category** | Accounting/Localizations/POS |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_gcc_pos`, `l10n_sa` |

## Description
Saudi Arabian POS localization. Enforces company country setup before opening POS, and loads ZATCA refund reason codes into the POS session for display to cashiers during refund transactions.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_gcc_pos` | Gulf Cooperation Council POS base |
| `l10n_sa` | Core Saudi accounting |

## Technical Notes
- Country code: `sa` (Saudi Arabia)
- ZATCA Phase 2: Requires refund reason selection on POS refunds

## Models

### `pos.config` (Extended)
**`open_ui()`** — OVERRIDES `point_of_sale`. Enforces that the company has a country set before opening the POS session.

**`_load_pos_data_read()`** — EXTENDS `point_of_sale`. For Saudi companies, adds `_zatca_refund_reasons` to POS session data — a list of ZATCA refund reason values and names sourced from `account.move.l10n_sa_reason` field selections.

### `pos.order` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `l10n_sa_reason` | Selection | ZATCA refund reason code (from `ADJUSTMENT_REASONS`) |
| `l10n_sa_reason_value` | Char | Human-readable label for the reason (computed) |

**`_prepare_invoice_vals()`** — EXTENDS `point_of_sale`. For Saudi companies:
- Validates that all orders in a batch have the same ZATCA reason (blocks consolidated invoices with mixed reasons)
- Sets `l10n_sa_confirmation_datetime` on the invoice
- Propagates `l10n_sa_reason` to the generated invoice

**`_compute_l10n_sa_reason_value()`** — Maps the reason code to its translated display name

## Related
- [[Modules/l10n_sa]] — Core Saudi accounting
- [[Modules/l10n_sa_edi]] — ZATCA e-invoicing
- [[Modules/l10n_sa_edi_pos]] — ZATCA e-invoicing for POS
- [[Modules/l10n_gcc_pos]] — GCC POS base
