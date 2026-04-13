---
type: module
module: l10n_my_ubl_pint
tags: [odoo, odoo19, l10n, localization, malaysia, edi, einvoice, ubl, peppol]
created: 2026-04-06
---

# Malaysia UBL PINT - Peppol E-invoice Format (l10n_my_ubl_pint)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Malaysia - UBL PINT |
| **Technical** | `l10n_my_ubl_pint` |
| **Category** | Localization / EDI |
| **Country** | Malaysia |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Malaysia (MY) |

## Description

UBL PINT (Peppol International) e-invoicing format specification for Malaysia. This module defines the Peppol BIS Billing 3.0 compliant UBL XML format tailored for Malaysian e-invoicing requirements through the MyInvois system.

The PINT format is part of the Peppol International (PINT) specification that adapts the Peppol BIS Billing standard for use in countries outside Europe, including Malaysia.

This module defines the XML schema and formatting rules. The actual API communication with MyInvois is handled by [Modules/l10n_my_edi](l10n_my_edi.md).

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account_edi_ubl_cii](account_edi_ubl_cii.md) | UBL/CII invoice format framework |

## Key Models

### `account.edi.xml.pint_my` (account_edi_xml_pint_my.py)
UBL XML document generator for Malaysian PINT format:
- Generates Peppol BIS Billing 3.0 compliant UBL XML
- Malaysian-specific field mappings
- Tax calculation per PINT specification
- Invoice line formatting for Malaysian requirements

### `res.company` (res_company.py)
Company configuration for PINT format:
- Peppol endpoint identification
- Company identifier for Peppol network

### `res.partner` (res_partner.py)
Partner configuration for PINT format:
- Peppol participant identifier (Endpoint ID)
- Peppol Access Point configuration
- Buyer identification fields

## Country-Specific Features

### PINT Format Details
The Malaysian PINT format includes:
- Peppol BIS Billing 3.0 UBL 2.1 structure
- Malaysian tax classifications (SST)
- MSIC (Malaysian Standard Industrial Classification) codes
- TIN and BRN (Business Registration Number) identifiers
- HS Code classification for products

### Peppol Network Integration
- Peppol Service Metadata Publisher (SMP) lookup
- Access Point configuration
- Participant identifier scheme (ISO 6523)

### Tax Mapping
- SST (Sales and Service Tax) line items
- Zero-rated and exempt supply classifications
- Tax total calculations per Malaysian requirements

## Data Files

- `views/report_invoice.xml` - Invoice report customization
- `views/res_company_view.xml` - Company configuration
- `views/res_partner_view.xml` - Partner view updates

## Uninstall Hook

Cleans up Malaysian PINT-specific configurations when uninstalled.

## Related

- [Modules/l10n_my_edi](l10n_my_edi.md) - MyInvois e-invoicing (uses this format)
- [Modules/account_edi_ubl_cii](account_edi_ubl_cii.md) - UBL/CII framework
- [Modules/account_edi_proxy_client](account_edi_proxy_client.md) - EDI proxy for Peppol
- [Peppol PINT Specification](https://peppol.org)
