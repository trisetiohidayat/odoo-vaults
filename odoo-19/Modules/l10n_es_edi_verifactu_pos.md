# Spain - VeriFactu for Point of Sale (`l10n_es_edi_verifactu_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Spain - Veri*Factu for Point of Sale |
| **Technical** | `l10n_es_edi_verifactu_pos` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_es_edi_verifactu`, `point_of_sale` |

## Description
Veri*Factu fiscal compliance for Point of Sale in Spain. Creates and submits Veri*Factu documents (facturas) to the AEAT (Agencia Tributaria) for POS transactions. Supports both regular invoices and simplified invoices (facturas simplificadas), refund corrections (R1-R5 reasons), and automatic submission on order payment.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_es_edi_verifactu` | Core Veri*Factu document engine |
| `point_of_sale` | Base POS module |

## Technical Notes
- Country code: `es` (Spain)
- Format: Veri*Factu JSON (AEAT REST API)
- Invoice threshold: orders above `l10n_es_simplified_invoice_limit` must be invoiced (not just receipted)
- Tax applicability: single tax applicability per Veri*Factu document
- Refund reasons: R1, R2, R3, R4, R5 (Article 80 compliance)

## Models

### `pos.order` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `l10n_es_edi_verifactu_required` | Boolean (related) | From `company_id.l10n_es_edi_verifactu_required` |
| `l10n_es_edi_verifactu_document_ids` | One2many | Linked `l10n_es_edi_verifactu.document` records |
| `l10n_es_edi_verifactu_state` | Selection | `rejected`, `registered_with_errors`, `accepted`, `cancelled` |
| `l10n_es_edi_verifactu_warning_level` | Char | `warning`, `danger`, `info` — based on document errors |
| `l10n_es_edi_verifactu_warning` | Html | Human-readable warning messages |
| `l10n_es_edi_verifactu_qr_code` | Char | QR code URL for Veri*Factu (from document or account move) |
| `l10n_es_edi_verimen_refund_reason` | Selection | R1–R5 refund reason codes |

**Key methods:**
- `_compute_l10n_es_edi_verifactu_warning()` — Aggregates errors and waiting state into warning HTML
- `_compute_l10n_es_edi_verifactu_state()` — Computes state from linked documents
- `_compute_l10n_es_edi_verifactu_qr_code()` — Gets QR from invoice or last submission
- `_l10n_es_edi_verifactu_get_tax_applicability()` — Returns tax applicability (false if not required); validates single applicability
- `_l10n_es_edi_verifactu_get_clave_regimen()` — Derives fiscal regime Clave Regimen from tax applicability
- `_l10n_es_edi_verifactu_check()` — Validates order state (`paid` or `done`) for Veri*Factu generation
- `_l10n_es_edi_verifactu_get_record_values()` — Builds document creation vals: document type (submission/cancellation), refunded document links, tax details, clave regimen, simplified invoice flag
- `_l10n_es_edi_verifactu_create_documents()` — Batch-creates Veri*Factu documents for orders
- `_l10n_es_edi_verifactu_mark_for_next_batch()` — Creates documents and triggers next batch submission
- `_order_fields()` — EXTENDS `point_of_sale`. Reads `l10n_es_edi_verifactu_refund_reason` from UI order
- `_process_saved_order()` — Validates: refund reason required for refunds; partner required for non-R5 refunds; amount threshold forces invoicing
- `action_pos_order_paid()` — EXTENDS `point_of_sale`. For Veri*Factu-required POS with no invoicing, auto-creates Veri*Factu document on payment
- `_generate_pos_order_invoice()` — EXTENDS `point_of_sale`. Cancels existing Veri*Factu docs when re-invoicing; creates cancellation and new invoice documents
- `_prepare_invoice_vals()` — Sets `l10n_es_is_simplified = False` and refund reason on invoice vals; blocks order consolidation when Veri*Factu enabled
- `l10n_es_edi_verifactu_get_invoice_name()` — Returns account move name or `{config_id}/{sequence_number:06d}`
- `_update_sequence_number()` — OVERRIDE: blocked for Spanish POS with Veri*Factu enabled (no sequence number updates)

## Related
- [Modules/l10n_es_edi_verifactu](modules/l10n_es_edi_verifactu.md) — Core Veri*Factu document engine
- [Modules/l10n_es_pos](modules/l10n_es_pos.md) — Spanish POS base
- [Modules/point_of_sale](modules/point_of_sale.md) — Base POS module
