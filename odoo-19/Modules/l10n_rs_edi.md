---
type: module
module: l10n_rs_edi
tags: [odoo, odoo19, l10n, localization, serbia, edi, einvoicing, efaktura]
created: 2026-04-06
---

# Serbia EDI / eFaktura (`l10n_rs_edi`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Serbia - eFaktura E-invoicing |
| **Technical** | `l10n_rs_edi` |
| **Category** | Accounting/Localizations/EDI |
| **Country** | Serbia (RS) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |

## Description

This module provides Serbian e-invoice compliance through the **eFaktura** system (Електронски фискални рачун / Electronic Fiscal Invoice). It implements a UBL 2.1 based format for mandatory B2G e-invoicing in Serbia.

### Key Capabilities

- **UBL 2.1 RS Format**: Serbian extension of EN 16931
- **eFaktura Integration**: B2G mandatory e-invoicing
- **Public Funds Reporting**: Support for JBKJS (Javni budžet) codes
- **Credit Note Support**: Structured credit note with billing reference

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/account_edi_ubl_cii]] | UBL/CII EDI framework |
| [[Modules/l10n_rs]] | Serbian base accounting |

## Auto-Install

Auto-installs with `l10n_rs_edi` when dependencies are met.

## Key Components

### EDI XML Builder: `account.edi.xml.ubl.rs`

Custom UBL 2.1 format for Serbia:

```
Customization ID: urn:cen.eu:en16931:2017#compliant#urn:mfin.gov.rs:srbdt:2022#conformant#urn:mfin.gov.rs:srbdtext:2022
```

Inherits from `account.edi.xml.ubl_21`.

## Models

### `account.move` Fields

Extends [[account.move]] with Serbian EDI fields.

### `res.partner` Fields

Extends [[Modules/res.partner]] with Serbian EDI fields:

```python
# Public funds identifier (JBKJS - Jedinstveni biro konstante računa)
l10n_rs_edi_public_funds = fields.Char(
    string="Public Funds (JBKJS)",
    help="Unique identifier for public budget accounts"
)

# Company registration number for EDI
l10n_rs_edi_registration_number = fields.Char(
    string="Registration Number (EDI)",
    help="Company registration number for Serbian eFaktura"
)
```

### Other Extended Models

| Model | File | Purpose |
|-------|------|---------|
| `account.move.send` | `account_move_send.py` | EDI send flow |
| `res.company` | `res_company.py` | Company EDI settings |
| `res.config.settings` | `res_config_settings.py` | EDI configuration |

## CIUS RS / eFaktura Requirements

### Customization ID

```
urn:cen.eu:en16931:2017#compliant#urn:mfin.gov.rs:srbdt:2022#conformant#urn:mfin.gov.rs:srbdtext:2022
```

### Mandatory Fields

| Field | Description |
|-------|-------------|
| Endpoint ID | Serbian TIN with scheme `9948` |
| Company Registration | For legal entity identification |
| JBKJS | For public sector (budget) entities |
| Tax Date Obligations Code | Invoice period classification |
| Billing Reference | For credit notes (references original invoice) |

### Endpoint ID Scheme

Serbian invoices use scheme ID `9948` for the endpoint identifier:
```python
party_node['cbc:EndpointID'] = {
    '_text': vat_number,  # Serbian PIB
    'schemeID': '9948',
}
```

## Invoice Period / Tax Obligations

For Serbian invoices, the `InvoicePeriod` node includes a `DescriptionCode`:

| Code | Meaning |
|------|---------|
| `0` | Credit note (reversal) |
| `l10n_rs_tax_date_obligations_code` | Standard invoice period code |

## Related Modules

| Module | Relationship |
|--------|-------------|
| [[Modules/l10n_rs]] | Base Serbian accounting |
| [[Modules/account_edi_ubl_cii]] | UBL/CII framework |

## Configuration

1. Install `l10n_rs` first
2. Install `l10n_rs_edi`
3. Configure Serbian EDI settings in company settings:
   - PIB (company tax ID)
   - Registration number
4. Set JBKJS codes on public sector partners
5. Configure EDI journal for e-invoice exchange

## Technical Notes

- Serbia uses UBL 2.1 (not 2.0 or BIS 3)
- Scheme ID `9948` for Serbian endpoint identification
- PIB (Matični broj) is the primary identifier
- Serbia is not in the EU, so separate CIUS
- VAT number can contain numeric-only values (handled by stripping country prefix)

## See Also

- [[Modules/l10n_rs]] - Serbian accounting
