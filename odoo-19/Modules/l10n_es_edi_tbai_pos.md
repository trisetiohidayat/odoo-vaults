# Spain - TicketBAI for Point of Sale (`l10n_es_edi_tbai_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Spain - TicketBAI for Point of Sale |
| **Technical** | `l10n_es_edi_tbai_pos` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_es_edi_tbai`, `point_of_sale` |

## Description
TicketBAI fiscal receipt compliance for Point of Sale in Spain (Basque Country). Submits electronic receipts to the TicketBAI government gateway on order payment. Supports simplified invoices, refunds (R5 reason), and automatic chain recovery when a submission fails.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_es_edi_tbai` | Core TicketBAI document engine |
| `point_of_sale` | Base POS module |

## Technical Notes
- Country code: `es` (Spain — Basque Country)
- Format: TicketBAI XML (submitted to government gateway)
- Auto-submit: On `action_pos_order_paid()` when no invoicing
- Chain integrity: Retries chain head on failure before retrying current order

## Models

### `pos.order` (Extended)
Fields:

| Field | Type | Description |
|-------|------|-------------|
| `l10n_es_tbai_state` | Selection | `to_send`, `sent` |
| `l10n_es_tbai_chain_index` | Integer | Index in TicketBAI chain (related to document) |
| `l10n_es_tbai_post_document_id` | Many2one | Linked `l10n_es_edi_tbai.document` |
| `l10n_es_tbai_post_file` | Binary | XML attachment data (related) |
| `l10n_es_tbai_post_file_name` | Char | XML filename (related) |
| `l10n_es_tbai_is_required` | Boolean | From `company_id.l10n_es_tbai_is_enabled` |
| `l10n_es_tbai_refund_reason` | Selection | Refund reason code (TBAI_REFUND_REASONS) |

**`_compute_l10n_es_tbai_state()`** — `to_send` if TicketBAI required and no account_move yet; `sent` if document accepted

**`_process_saved_order()`** — Validates: above-limit orders must be invoiced; refunds require linked order invoicing

**`action_pos_order_paid()`** — EXTENDS `point_of_sale`. Posts to TicketBAI when paid without invoicing; on failure, retries the chain head then re-posts current order

**`_prepare_invoice_vals()`** — Blocks mixing TicketBAI-required and non-required orders in one batch; propagates refund reason

**`get_l10n_es_pos_tbai_qrurl()`** — Returns TicketBAI QR code URL from the accepted document

**`_l10n_es_tbai_post()`** — Creates `l10n_es_edi_tbai.document` if needed; posts via `_post_to_web_service()`; deletes rejected documents on retry

**`_l10n_es_tbai_get_values()`** — Builds XML values with base lines, gross prices, sign handling for refunds

## Related
- [Modules/l10n_es_edi_tbai](modules/l10n_es_edi_tbai.md) — Core TicketBAI document engine
- [Modules/l10n_es_pos](modules/l10n_es_pos.md) — Spanish POS base
- [Modules/point_of_sale](modules/point_of_sale.md) — Base POS module
