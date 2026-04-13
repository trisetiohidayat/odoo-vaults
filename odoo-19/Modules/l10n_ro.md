---
type: module
module: l10n_ro
tags: [odoo, odoo19, l10n, localization, romania, accounting, ANAF]
created: 2026-04-06
---

# Romania Accounting Localization (`l10n_ro`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Romania - Accounting |
| **Technical** | `l10n_ro` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Romania (RO) |
| **Currency** | RON (Romanian Leu) |
| **License** | LGPL-3 |
| **Author** | Fekete Mihai (NextERP Romania SRL) & Odoo S.A. |
| **Version** | 1.0 |

## Description

Romanian accounting chart and localization module. Manages the Accounting Chart of Accounts, VAT structure, Fiscal Position, and Tax Mapping for Romanian compliance. Also adds the Registration Number field for Romania in [Modules/res.partner](res.partner.md).

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](Account.md) | Core accounting framework |
| [Modules/base_vat](base_vat.md) | Romanian CIF (Cod de Identificare Fiscala) validation |
| [Modules/account_edi_ubl_cii](account_edi_ubl_cii.md) | UBL/CII EDI framework for e-invoicing |

## Auto-Install

Auto-installs with `account` when the company's country is set to Romania.

## Key Components

### Chart of Accounts

Romanian accounting follows the OMFP 1802/2019 regulations:
- Analytic accounts for cost tracking
- VAT synchronization accounts
- Third-party accounts (clients, suppliers)
- Fixed assets classification

### Tax Structure

Romanian VAT (TVA - Tax pe Valoarea Adăugată) rates:
- **19%** - Standard rate
- **9%** - Reduced rate (food, books, medical)
- **5%** - Special reduced rate (housing, new construction)

Reverse charge applies to:
- B2B intra-EU acquisitions
- Specific domestic transactions (energy, construction)

### Fiscal Positions

Pre-configured for:
- Domestic B2B with VAT
- B2B Intra-EU (reverse charge)
- B2C (no VAT for small businesses)
- Export outside EU (0%)

## Models

### Extended: `res.partner`

```python
# Inherits from base to add Romanian-specific fields
# CIF (Cod de Identificare Fiscala) validation
# Company Registration Number (ONRC)
# Trade Register number
```

### Template: `template_ro`

Loads Romanian-specific:
- Chart of accounts data
- Tax templates with TVA rates
- Account tags for Romanian reporting

## Romanian-Specific Fields

### CIF (Cod de Identificare Fiscala)

Romanian VAT/Tax ID:
- Format: `RO` + 2-10 digits (e.g., `RO12345678`)
- Used for both VAT and tax identification
- Validated via [Modules/base_vat](base_vat.md)

### Additional Partner Fields

| Field | Description |
|-------|-------------|
| `company_registry` | Trade Register / ONRC number |
| `l10n_ro_e_invoice` | E-invoice opt-in flag |
| `l10n_ro_edi_registration_number` | Registration number for EDI |

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_ro_edi](l10n_ro_edi.md) | ANAF e-Factura EDI integration |
| [Modules/l10n_ro_cpv_code](l10n_ro_cpv_code.md) | CPV product classification |
| [Modules/l10n_ro_edi_stock](l10n_ro_edi_stock.md) | e-Transport (stock/inventory) |
| [Modules/l10n_ro_edi_stock_batch](l10n_ro_edi_stock_batch.md) | e-Transport batch processing |

## Configuration

1. Install the module via Apps
2. Set company country to Romania
3. Configure Romanian VAT number (CIF) in company settings
4. Install [Modules/l10n_ro_edi](l10n_ro_edi.md) for ANAF e-Factura compliance
5. Install [Modules/l10n_ro_cpv_code](l10n_ro_cpv_code.md) for product classification

## Technical Notes

- Romanian account numbers may include Romanian characters (ș, ț) in company names
- ANAF requires structured electronic invoices (e-Factura)
- Bucharest addresses use SECTOR 1-6 format in city field
- UBL-based EDI via [Modules/account_edi_ubl_cii](account_edi_ubl_cii.md)

## See Also

- [Modules/l10n_ro_edi](l10n_ro_edi.md) - Romanian ANAF e-Factura
- [Modules/l10n_ro_cpv_code](l10n_ro_cpv_code.md) - CPV product classification
- [Modules/l10n_ro_edi_stock](l10n_ro_edi_stock.md) - Romanian e-Transport
