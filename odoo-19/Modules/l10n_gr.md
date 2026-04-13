---
type: module
module: l10n_gr
tags: [odoo, odoo19, l10n, localization, greece, accounting]
created: 2026-04-06
---

# Greece Accounting Localization (`l10n_gr`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Greece - Accounting |
| **Technical** | `l10n_gr` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Greece (GR) |
| **Currency** | EUR (Euro) |
| **License** | LGPL-3 |
| **Author** | P. Christeas & Odoo S.A. |

## Description

Base module for Greek accounting. Manages the accounting chart, fiscal positions, and tax structure for Greek compliance.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](Account.md) | Core accounting framework |
| [Modules/base_iban](base_iban.md) | Greek IBAN validation |
| [Modules/base_vat](base_vat.md) | Greek AFM (Αριθμός Φορολογικού Μητρώου) validation |
| [Modules/account_edi_ubl_cii](account_edi_ubl_cii.md) | UBL/CII EDI framework |

## Auto-Install

Auto-installs with `account` when the company's country is set to Greece.

## Key Components

### Chart of Accounts

Greek accounting structure:
- Greek Revenue Classification (KAEK)
- Cost center accounts
- VAT-synchronized accounts
- Third-party accounts

### Tax Structure

Greek VAT (ΦΠΑ - Φόρος Προστιθέμενης Αξίας) rates:
- **24%** - Standard rate
- **13%** - Reduced rate (food, energy, transport)
- **6%** - Super-reduced rate (medicine, books, newspapers)

### Data File

`data/account_tax_report_data.xml` - Greek tax reporting structure for VAT returns and fiscal documentation.

## Greek-Specific Fields

### AFM (Αριθμός Φορολογικού Μητρώου)

Greek Tax Identification Number:
- 9-digit number
- Format: `123456789`
- Used for both VAT and tax registration
- Validated via [Modules/base_vat](base_vat.md)

### Greek IBAN

Greek bank accounts:
- 27 characters
- Country prefix: `GR`
- BBAN: 21 characters (bank + account)
- Validated via [Modules/base_iban](base_iban.md)

## Models

### Template: `template_gr`

Loads Greek-specific:
- Chart of accounts data
- Tax templates with ΦΠΑ rates
- Account tags for Greek reporting

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_gr_edi](l10n_gr_edi.md) | myDATA e-invoicing and tax reporting |

## Configuration

1. Install the module via Apps
2. Set company country to Greece
3. Configure Greek AFM in company settings
4. Set up Greek bank accounts (GR IBAN)
5. Install [Modules/l10n_gr_edi](l10n_gr_edi.md) for myDATA compliance

## Technical Notes

- Greece is an EU member using Euro (EUR)
- AFM is the primary tax identifier
- Greek accounting follows EU standards
- [Modules/l10n_gr_edi](l10n_gr_edi.md) provides mandatory myDATA tax reporting
- Community-maintained module (P. Christeas)

## See Also

- [Modules/l10n_gr_edi](l10n_gr_edi.md) - Greek myDATA e-invoicing
