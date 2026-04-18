---
type: module
module: l10n_dk_nemhandel
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Denmark Accounting Localization (`l10n_dk_nemhandel`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | - Send and receive documents via Nemhandel network in OIOUBL 2.1 format |
| **Technical** | `l10n_dk_nemhandel` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
- Send and receive documents via Nemhandel network in OIOUBL 2.1 format

## Dependencies
| Module | Purpose |
|--------|---------|
| `account_edi_proxy_client` | Dependency |
| `account_edi_ubl_cii` | Dependency |
| `l10n_dk` | Dependency |

## Technical Notes
- Country code: `dk` (Denmark)
- Localization type: e-invoicing (Nemhandel/OIOUBL 2.1)
- Custom model files: account_edi_xml_oioubl_21.py, account_move.py, account_move_send.py, account_journal.py, account_edi_proxy_user.py, res_company.py, res_config_settings.py, res_partner.py

## Models

### `account.edi.xml.oioubl_21` (Abstract)
Danish OIOUBL 2.1 e-invoicing format via Nemhandel network.

**Inherits:** `account.edi.xml.ubl_21`

- `_name = 'account.edi.xml.oioubl_21'`
- Extends UBL 2.1 with Danish Nemhandel-specific rules

### `account.move` (Extended)
Danish e-invoice fields (order reference, buyer reference).

### `account.journal` (Extended)
Danish journal settings.

### `account_edi_proxy_client.user` (Extended)
Nemhandel proxy user for sending/receiving OIOUBL documents.

## Related
- [Modules/l10n_dk](Modules/l10n_dk.md) — Core Danish accounting
- [Modules/l10n_dk_oioubl](Modules/l10n_dk_oioubl.md) — OIOUBL 2.0 (older format)
- [Modules/account_edi_proxy_client](Modules/account_edi_proxy_client.md) — EDI proxy framework