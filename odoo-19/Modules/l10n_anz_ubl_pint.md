---
type: module
module: l10n_anz_ubl_pint
tags: [odoo, odoo19, l10n, localization, australia, newzealand, edi, einvoice, ubl, peppol]
created: 2026-04-06
---

# ANZ UBL PINT - Australia & New Zealand Peppol E-invoice Format (l10n_anz_ubl_pint)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Australia & New Zealand - UBL PINT |
| **Technical** | `l10n_anz_ubl_pint` |
| **Category** | Localization / EDI |
| **Countries** | Australia (AU), New Zealand (NZ) |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |

## Description

UBL PINT (Peppol International) e-invoicing format specification for Australia and New Zealand. This module defines the Peppol BIS Billing 3.0 compliant UBL XML format for ANZ countries.

The PINT format adapts the Peppol BIS Billing standard for use in Australia and New Zealand, supporting both countries' specific invoicing requirements including GST/sales tax reporting, ABN/NZBN identifiers, and Peppol network integration.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account_edi_ubl_cii](account_edi_ubl_cii.md) | UBL/CII invoice format framework |

## Key Models

### `account.edi.xml.pint_anz` (account_edi_xml_pint_anz.py)
UBL XML document generator for ANZ PINT format.

**Inherits:** `account.edi.xml.ubl_bis3`

Extends Peppol BIS3 with Australia/New Zealand-specific rules:
- Peppol BIS Billing 3.0 UBL 2.1 structure
- Australian GST (10%) line item support
- New Zealand GST (15%) line item support
- ABN (AU) and NZBN (NZ) identifier scheme
- BAS-ready tax line classification

### `res.partner` (res_partner.py)
Extends partner with ANZ-specific EDI fields:
- Peppol participant identifier (Endpoint ID)
- Australian Business Number (ABN) for Australia
- New Zealand Business Number (NZBN) for New Zealand

## Country-Specific Features

### PINT Format for Australia
- Peppol BIS Billing 3.0 UBL 2.1 structure
- Australian GST (10%) line item support
- ABN identifier scheme
- BAS-ready tax line classification
- Invoice types for different transaction categories

### PINT Format for New Zealand
- Peppol BIS Billing 3.0 UBL 2.1 structure
- New Zealand GST (15%) line item support
- NZBN identifier scheme
- GST return-ready formatting

### Peppol Network Integration
- Peppol Service Metadata Publisher (SMP) lookup
- Access Point configuration
- Participant identifier scheme (ISO 6523)
- Supports both AU and NZ Peppol endpoints

### Tax Mapping

**Australia**:
- GST (10%) - taxable supplies
- GST-free (0%) - exempt supplies
- Input-taxed supplies

**New Zealand**:
- GST (15%) - standard-rated supplies
- Zero-rated (0%) - exports, specific supplies
- Exempt supplies

## Related

- [Modules/account_edi_ubl_cii](account_edi_ubl_cii.md) - UBL/CII framework
- [Modules/l10n_au](l10n_au.md) - Australian accounting
- [Modules/l10n_nz](l10n_nz.md) - New Zealand accounting
- [Modules/account_edi_proxy_client](account_edi_proxy_client.md) - EDI proxy for Peppol
- [Peppol](https://peppol.org)
- [AU e-invoicing](https://www.austroads.com.au)
- [NZ e-invoicing](https://www.nz.govt.nz)
