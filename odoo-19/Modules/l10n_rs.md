---
type: module
module: l10n_rs
tags: [odoo, odoo19, l10n, localization, serbia, accounting]
created: 2026-04-06
---

# Serbia Accounting Localization (`l10n_rs`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Serbia - Accounting |
| **Technical** | `l10n_rs` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Serbia (RS) |
| **Currency** | RSD (Serbian Dinar) |
| **License** | LGPL-3 |
| **Author** | Modoolar & Odoo S.A. |
| **Version** | 1.0 |

## Description

Base module for Serbian accounting localization. Manages the chart of accounts and tax structure required for Serbian compliance.

Based on the official document:
> "Pravilnik o kontnom okviru i sadržini računa u kontnom okviru za privredna društva, zadruge i preduzetnike" (Sl. glasnik RS", br. 89/2020)

Source: [Paragraf.rs](https://www.paragraf.rs/propisi/pravilnik-o-kontnom-okviru-sadrzini-racuna-za-privredna-drustva-zadruge.html)

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](Modules/Account.md) | Core accounting framework |
| [Modules/base_vat](Modules/base_vat.md) | Serbian PIB (Matični broj) validation |

## Auto-Install

Auto-installs with `account` when the company's country is set to Serbia.

## Key Components

### Chart of Accounts

Serbian accounting follows the official chart per the 2020 regulation:
- Full account hierarchy
- Account types per Serbian law
- Cost center structure

### Tax Structure

Serbian VAT (Porez na dodatu vrednost / PDV) rates:
- **20%** - Standard rate
- **10%** - Reduced rate (food, medicine, books)

### Serbian-Specific Fields

#### PIB (Matični broj / Registration Number)

Serbian company registration number:
- 8-digit unique identifier
- Used for both VAT and business registration
- Format validated via [Modules/base_vat](Modules/base_vat.md)

## Models

### `account.move` Extension

Extends [account.move](account.move.md) for Serbian-specific fields:

```python
# Tax obligations code for Serbian e-invoicing
l10n_rs_tax_date_obligations_code = fields.Char(
    string="Tax Obligations Code",
    help="Code for Serbian tax date obligations in e-invoice"
)
```

### Template: `template_rs`

Loads Serbian-specific:
- Chart of accounts data
- Tax templates with PDV rates
- Account tags for Serbian reporting

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_rs_edi](Modules/l10n_rs_edi.md) | Serbian eFaktura EDI integration |

## Configuration

1. Install the module via Apps
2. Set company country to Serbia
3. Configure Serbian registration number (PIB) in company settings
4. Install [Modules/l10n_rs_edi](Modules/l10n_rs_edi.md) for eFaktura compliance

## Technical Notes

- Serbia is not an EU member - different EDI requirements
- Uses Serbian Dinar (RSD) for accounting
- Serbian Cyrillic/Latin text support in addresses
- PIB is the primary business identifier
- Tax date obligations tracked for e-invoice reporting

## See Also

- [Modules/l10n_rs_edi](Modules/l10n_rs_edi.md) - Serbian eFaktura
