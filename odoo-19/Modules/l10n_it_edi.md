---
type: module
module: l10n_it_edi
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Italy Accounting Localization (`l10n_it_edi`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | E-invoice implementation |
| **Technical** | `l10n_it_edi` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
E-invoice implementation

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_it` | Dependency |
| `account_edi_proxy_client` | Dependency |
| `account_debit_note` | Dependency |

## Technical Notes
- Country code: `it` (Italy)
- Localization type: e-invoicing (FatturaPA / SDI)
- Custom model files: ddt.py, account_tax.py, account_move.py, account_payment_method_line.py, account_move_send.py, l10n_it_document_type.py, account_edi_proxy_user.py, res_company.py, res_config_settings.py, res_partner.py

## Models

### `l10n_it.document.type` (Italian Document Type)
Taxonomy of Italian fiscal document types.

**Fields:**
- `name`, `code` — Document type name and code (e.g., TD01, TD02)

### `account.move` (Extended)
Italian e-invoice fields for SDI/FatturaPA:
- Electronic invoice data (Cessionario, Cedente details)
- Transmission status to SDI
- `l10n_it_state` — SDI status: `ready`, `sent`, `delivered`, `error`

### `res.partner` (Extended)
Italian partner-specific fields:
- `l10n_it_codice_fiscale` — Italian personal tax code
- `l10n_it_pa_index` — PA PEC destination code
- `l10n_it_einvoice_code` — Unique e-invoice code

### `account_edi_proxy_client.user` (Extended)
SDI proxy user for Italian electronic invoice transmission via Intermediario.

### `account.tax` (Extended)
Italian tax-specific fields (nature, law reference).

### `ddt` (Extended)
Transport Document (DDT) integration with Italian e-invoices.

## Related
- [Modules/l10n_it](l10n_it.md) — Core Italian accounting
- [Modules/l10n_it_edi_doi](l10n_it_edi_doi.md) — Italian Direct Import module
- [Modules/account_edi_proxy_client](account_edi_proxy_client.md) — EDI proxy framework
- [Modules/account_debit_note](account_debit_note.md) — Debit note support