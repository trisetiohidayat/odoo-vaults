# India - Point of Sale (`l10n_in_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | India - Point of Sale |
| **Technical** | `l10n_in_pos` |
| **Category** | Accounting/Localizations/POS |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_in`, `point_of_sale` |

## Description
GST-compliant Point of Sale for India. Integrates Indian GST tax structure (HSN codes, CGST/SGST/IGST, composite/Reverse Charge) into the POS workflow. Handles GST registration validation, tax state computation, and HSN code propagation into account moves.

## Technical Notes
- Country code: `in` (India)
- Localization type: POS-specific model extensions (9 Python files)
- Key concerns: GST registration check, HSN code on move lines, state_id for POS journals

## Models

### `pos.config` (Extended)
| Field / Method | Type | Description |
|----------------|------|-------------|
| `_is_quantities_set()` | Method | Also passes if `company_id.l10n_in_is_gst_registered` is True — allows opening POS session without setting quantities when GST-registered |

### `pos.order` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `l10n_in_hsn_code` | Char (related) | Related to `account_move.l10n_in_hsn_code` |
| `l10n_in_state_id` | Selection (related) | Related to `account_move.l10n_in_state_id` |
| `l10n_in_gst_state` | Char (related) | Related to `account_move.l10n_in_gst_state` |

### `pos.order.line` (Extended)
Inherits from `pos.order.line`; adds HSN-aware product line handling (via `l10n_in` base localization).

### `account.move` (Extended — `l10n_in_pos/models/account_move.py`)
| Method | Description |
|--------|-------------|
| `_compute_l10n_in_state_id()` | EXTENDS `l10n_in`. For moves with `journal_id.type == 'general'` linked to POS sessions or reversed POS orders where country is India and state is unset, forces `l10n_in_state_id = company_id.state_id` |

### `account.move.line` (Extended)
HSN code field on invoice lines for GST reporting.

### `account.tax` (Extended)
India-specific tax computation rules for POS transactions.

### `product.template` (Extended)
HSN code association on products sold through POS.

### `pos.session` (Extended)
GST-registered company session handling.

### `pos.bill` (Extended)
Indian rupee denomination bills.

## Related
- [Modules/l10n_in](modules/l10n_in.md) — Core Indian accounting
- [Modules/l10n_in_edi](modules/l10n_in_edi.md) — Indian e-invoicing (e-Waybill)
- [Modules/l10n_in_purchase_stock](modules/l10n_in_purchase_stock.md) — Indian purchase flow
- [Modules/l10n_in_sale](modules/l10n_in_sale.md) — Indian sale flow
- [Modules/l10n_in_stock](modules/l10n_in_stock.md) — Indian warehouse/inventory
- [Modules/point_of_sale](modules/point_of_sale.md) — Base POS module
