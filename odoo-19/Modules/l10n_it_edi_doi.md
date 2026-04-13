---
type: module
module: l10n_it_edi_doi
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Italy Accounting Localization (`l10n_it_edi_doi`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Add support for the Declaration of Intent (Dichiarazione di Intento) to the Italian localization. |
| **Technical** | `l10n_it_edi_doi` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Add support for the Declaration of Intent (Dichiarazione di Intento) to the Italian localization.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_it_edi` | Dependency |
| `sale` | Dependency |

## Technical Notes
- Country code: `it` (Italy)
- Localization type: accounting (Declaration of Intent / Dichiarazione di Intento)
- Custom model files: account_tax.py, account_move.py, sale_order.py, declaration_of_intent.py, res_company.py, account_chart_template.py, account_fiscal_position.py, res_partner.py

## Models

### `l10n_it_edi_doi.declaration_of_intent` (Declaration of Intent)
Tracks Italian "Dichiarazione di Intento" — exporter declarations for zero-rated VAT exports.

**Inherits:** `mail.thread.main.attachment`, `mail.activity.mixin`

**Fields:**
- `partner_id` — Customer/supplier
- `company_id`, `date_from`, `date_to` — Validity period
- `invoice_type` — `in_invoice`, `out_invoice`
- `fiscal_position_id` — Associated fiscal position
- `tax_ids` — Applicable taxes
- `amount_total` — Maximum amount covered by the declaration
- `used_amount`, `residual_amount` — Usage tracking
- `state` — `active`, `expired`, `cancelled`
- `sequence`

### `account.move` (Extended)
DOI-aware invoice processing (checks remaining DOI amounts).

### `account.fiscal.position` (Extended)
DOI fiscal position handling.

### `sale.order` (Extended)
DOI support in sales orders.

## Related
- [Modules/l10n_it_edi](Modules/l10n_it_edi.md) — Italian e-invoicing (SDI)
- [Modules/l10n_it](Modules/l10n_it.md) — Core Italian accounting