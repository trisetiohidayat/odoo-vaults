---
Module: l10n_dk_oioubl
Version: 18.0
Type: l10n/denmark-edi-legacy
Tags: #odoo18 #l10n #accounting #edi
---

# l10n_dk_oioubl

## Overview
Legacy Danish e-invoicing module providing **OIOUBL 2.01** format support (Offentlig Information Online UBL). This is the predecessor to the OIOUBL 2.1 format used by `[Modules/l10n_dk_nemhandel](l10n_dk_nemhandel.md)`. Offered for backward compatibility with existing integrations.

## Country
Denmark

## Dependencies
- account_edi_ubl_cii
- l10n_dk

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_edi_xml_oioubl_201.py | `AccountEdiXmlOIOUBL201` | (extends) |
| account_move.py | `AccountMove` | (extends) |
| res_partner.py | `ResPartner` | (extends) |

### AccountEdiXmlOIOUBL201
Generates OIOUBL 2.01 compliant XML invoices. This is the older Danish national e-invoicing profile.

## Data Files
- `data/oioubl_templates.xml` — OIOUBL 2.01 XML templates

## EDI/Fiscal Reporting
**OIOUBL 2.01** — Legacy Danish e-invoicing format. For new implementations, prefer `[Modules/l10n_dk_nemhandel](l10n_dk_nemhandel.md)` (OIOUBL 2.1). OIOUBL 2.01 is maintained for compatibility with existing Danish government portals that have not yet upgraded.

## Installation
Install separately as needed. For new Danish EDI setups, prefer `[Modules/l10n_dk_nemhandel](l10n_dk_nemhandel.md)`.

## Historical Notes
- OIOUBL 2.01 is being phased out in favor of OIOUBL 2.1 aligned with Peppol BIS Billing 3.0.
- Maintained for backward compatibility only.
