---
Module: l10n_dk_nemhandel
Version: 18.0
Type: l10n/denmark-edi
Tags: #odoo18 #l10n #accounting #edi
---

# l10n_dk_nemhandel

## Overview
Danish EDI module enabling sending and receiving electronic invoices via the **Nemhandel** network in **OIOUBL 2.1** format. Nemhandel is the Danish national e-invoicing infrastructure based on OIOUBL (OIO = Offentlig Information Online). Required for B2G (business-to-government) invoicing in Denmark.

## Country
Denmark

## Dependencies
- account_edi_proxy_client
- account_edi_ubl_cii
- l10n_dk

## Key Models

| File | Class | Inheritance |
|------|-------|-------------|
| account_edi_proxy_user.py | `AccountEdiProxyClientUser` | (extends) |
| account_edi_xml_oioubl_21.py | `AccountEdiXmlOIOUBL21` | (extends) |
| account_journal.py | `AccountJournal` | (extends) |
| account_move.py | `AccountMove` | (extends) |
| account_move_send.py | `AccountMoveSend` | (extends) |
| res_company.py | `ResCompany` | (extends) |
| res_config_settings.py | `ResConfigSettings` | (extends) |
| res_partner.py | `ResPartner` | (extends) |

### AccountEdiXmlOIOUBL21
Generates OIOUBL 2.1 compliant XML invoices. OIOUBL is the Danish profile of UBL 2.0 adapted for Danish business requirements. Extends the UBL/CII EDI framework from `account_edi_ubl_cii`.

## Data Files
- `data/cron.xml` — scheduled jobs for EDI proxy communication
- `data/neutralize.sql` — database neutralization for multi-company support
- `data/nemhandel_onboarding_tour.xml` — onboarding tour data

## Chart of Accounts
Inherits chart of accounts from `[Modules/l10n_dk](odoo-18/Modules/l10n_dk.md)`.

## Tax Structure
Inherits tax structure from `[Modules/l10n_dk](odoo-18/Modules/l10n_dk.md)`.

## Fiscal Positions
Inherits fiscal positions from `[Modules/l10n_dk](odoo-18/Modules/l10n_dk.md)`.

## EDI/Fiscal Reporting
**Nemhandel OIOUBL 2.1** — Danish national e-invoicing format via the Peppol network. Mandatory for B2G invoicing. The module:
- Sends invoices through the `account_edi_proxy_client` service
- Validates partner VAT numbers against the Danish CVR registry
- Supports both public and private sector document exchange

## Installation
Install after `l10n_dk`. Requires EDI proxy configuration for Peppol network access.

## Historical Notes
- Odoo 17→18: Updated from OIOUBL 2.0 to OIOUBL 2.1 format.
- OIOUBL 2.1 aligns with Peppol BIS Billing 3.0.
- The separate `l10n_dk_oioubl` module provides OIOUBL 2.01 (older format) for backward compatibility.
