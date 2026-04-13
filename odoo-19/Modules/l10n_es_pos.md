# Spain - Point of Sale (`l10n_es_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Spain - Point of Sale |
| **Technical** | `l10n_es_pos` |
| **Category** | Accounting/Localizations/POS |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `point_of_sale`, `l10n_es` |

## Description
Spanish-specific POS configuration and invoice handling. Handles simplified invoices (facturas simplificadas) for anonymous customers, maps POS orders to Spanish simplified invoice journals, and manages the Spanish invoice number sequence.

## Technical Notes
- Country code: `es` (Spain)
- Core concern: Spanish simplified invoice (Factura Simplificada) for POS

## Models

### `pos.order` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `is_l10n_es_simplified_invoice` | Boolean | Flag indicating this POS order generates a simplified invoice |
| `l10n_es_simplified_invoice_number` | Char | Computed invoice number derived from `account_move.name` |

**Key methods:**
- `_compute_l10n_es_simplified_invoice_number()` — Derives the simplified invoice number from the linked account move's name
- `_generate_pos_order_invoice()` — EXTENDS `point_of_sale`. For Spanish POS (`config_id.is_spanish`), auto-assigns the `simplified_partner_id` if invoicing a simplified invoice with no customer
- `_prepare_invoice_vals()` — EXTENDS `point_of_sale`. Routes simplified invoices to the `l10n_es_simplified_invoice_journal_id` configured on the POS config
- `get_invoice_name()` — Returns `account_move.name` for the linked invoice

## Related
- [Modules/point_of_sale](point_of_sale.md) — Base POS module
- [Modules/l10n_es](l10n_es.md) — Core Spanish accounting
- [Modules/l10n_es_edi_verifactu](l10n_es_edi_verifactu.md) — Veri*Factu fiscal module
- [Modules/l10n_es_edi_verifactu_pos](l10n_es_edi_verifactu_pos.md) — Veri*Factu integration for POS
