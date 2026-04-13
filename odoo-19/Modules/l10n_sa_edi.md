---
type: module
module: l10n_sa_edi
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Saudi Arabia Accounting Localization (`l10n_sa_edi`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | E-invoice implementation for Saudi Arabia; Integration with ZATCA |
| **Technical** | `l10n_sa_edi` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
E-invoice implementation for Saudi Arabia; Integration with ZATCA

## Dependencies
| Module | Purpose |
|--------|---------|
| `account_edi` | Dependency |
| `account_edi_ubl_cii` | Dependency |
| `l10n_sa` | Dependency |
| `base_vat` | Dependency |
| `certificate` | Dependency |

## Technical Notes
- Country code: `sa` (Saudi Arabia)
- Localization type: e-invoicing (ZATCA)
- Custom model files: account_tax.py, account_move.py, account_edi_format.py, certificate.py, ir_attachment.py, account_move_send.py, account_journal.py, res_company.py, account_edi_document.py, account_chart_template.py, res_config_settings.py, account_edi_xml_ubl_21_zatca.py, res_partner.py

## Models

### `account.edi.xml.ubl_21.zatca` (Abstract)
Saudi ZATCA-compliant UBL 2.1 e-invoice format.

**Inherits:** `account.edi.xml.ubl_21`

- `_name = 'account.edi.xml.ubl_21.zatca'`
- Extends UBL 2.1 with ZATCA-specific requirements
- Cryptographic signing for ZATCA compliance
- Phase 2 compliance (continuous invoicing)

### `account.edi.document` (Extended)
ZATCA document state tracking.

### `account.move` (Extended)
Saudi e-invoice fields:
- ZATCA submission ID, UUID
- Invoice hash, QR code generation

### `res.company` (Extended)
ZATCA credentials, VAT number, company branch ID.

### `res.partner` (Extended)
Saudi partner fields (CR number, VAT).

## Related
- [Modules/l10n_sa](l10n_sa.md) — Core Saudi accounting
- [Modules/l10n_sa_edi_pos](l10n_sa_edi_pos.md) — POS e-invoicing for Saudi Arabia
- [Modules/certificate](certificate.md) — X.509 certificate for ZATCA signing