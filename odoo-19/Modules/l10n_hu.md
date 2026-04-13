---
type: module
module: l10n_hu
tags: [odoo, odoo19, l10n, localization, hungary, accounting, nav]
created: 2026-04-06
---

# Hungary Accounting Localization (`l10n_hu`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Hungary - Accounting |
| **Technical** | `l10n_hu` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Hungary (HU) |
| **Currency** | HUF (Hungarian Forint) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 3.0 |

## Description

Hungarian accounting chart and localization module providing the complete chart of accounts, tax structure, and fiscal positions required for Hungarian compliance. The module integrates with [Modules/l10n_hu_edi](l10n_hu_edi.md) for mandatory NAV (Nemzeti Adó- és Vámhivatal - Hungarian Tax and Customs Authority) e-invoicing.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/Account](Account.md) | Core accounting framework |
| [Modules/base_vat](base_vat.md) | Hungarian VAT (Adószám) validation |

## Auto-Install

Auto-installs with `account` when the company's country is set to Hungary.

## Key Components

### Chart of Accounts

Hungarian accounting follows the Hungarian Chart of Accounts (Szamvitel Tv.):
- 4-digit account codes
- Class 1-8 structure per Hungarian law
- Mandatory cost center tagging

### Tax Structure

Hungarian VAT (ÁFA) rates:
- **27%** - Standard rate (alap)
- **18%** - Reduced rate (kedvezmenyezett)
- **5%** - Super-reduced rate

Additional Hungarian taxes:
- **Rehabilitation contribution** (Rehabdíj)
- **Innovation fee** (Innovációs járulék)
- **Personal income tax** (Személyi jövedelemadó / SZJA)

### Fiscal Positions

Pre-configured for:
- Domestic B2B (EU country code HU)
- EU intra-community (VIES validation)
- Export outside EU (0% reverse charge)
- Reverse charge domestic transactions

## Models

### Extended: `account.move`

Extends [account.move](account.move.md) for Hungarian-specific behavior:

```python
# EXTENDS account
def _compute_show_delivery_date(self):
    # Show delivery date only for Hungarian sale documents
    super()._compute_show_delivery_date()
    for move in self:
        if move.country_code == 'HU':
            move.show_delivery_date = move.is_sale_document()

def _post(self, soft=True):
    # Auto-set delivery date for Hungarian sales invoices
    res = super()._post(soft)
    for move in self:
        if move.country_code == 'HU' and move.is_sale_document() and not move.delivery_date:
            move.delivery_date = move.invoice_date
    return res
```

### `res.partner` Extension

Hungarian-specific partner fields for EDI:
- VAT number format validation (format: 12345678-1-12)
- Company registration number
- EU VAT number handling

### Template: `template_hu`

Loads Hungarian-specific:
- Chart of accounts data (CSV/XML)
- Tax templates with proper ÁFA rates
- Account tags for Hungarian reporting

## Hungarian-Specific Fields

### Tax ID / VAT Number

Hungarian VAT number (Adószám) structure:
- Company identification number (8 digits)
- VAT office code (1-2 digits)
- Check digit (2 digits)
- Format: `12345678-1-12`

### Delivery Date Requirement

Hungarian law requires delivery date on all B2B sale invoices. The module:
- Shows delivery date field for HU sales invoices
- Auto-fills delivery date = invoice date on posting
- Required for NAV e-invoice reporting

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_hu_edi](l10n_hu_edi.md) | NAV e-invoicing and Tax Audit Export |

## Configuration

1. Install the module via Apps
2. Set company country to Hungary
3. Configure Hungarian VAT number in company settings
4. The chart of accounts and taxes auto-install
5. Install [Modules/l10n_hu_edi](l10n_hu_edi.md) for NAV compliance

## Technical Notes

- Hungary uses HUF (no decimals) for accounting currency
- EU VAT number format validated via [Modules/base_vat](base_vat.md)
- Delivery date is mandatory for Hungarian e-invoicing
- ANAF (NAV) = Nemzeti Adó- és Vámhivatal

## See Also

- [Modules/l10n_hu_edi](l10n_hu_edi.md) - Hungarian NAV e-invoicing
