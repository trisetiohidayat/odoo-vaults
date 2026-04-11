---
type: module
module: l10n_hr
tags: [odoo, odoo19, l10n, localization, croatia, accounting]
created: 2026-04-06
---

# Croatia Accounting Localization (`l10n_hr`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Croatia - Accounting (Euro) |
| **Technical** | `l10n_hr` |
| **Category** | Accounting/Localizations/Account Charts |
| **Country** | Croatia (HR) |
| **Currency** | EUR (adopted 2023-01-01) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 13.0 |

## Description

Croatian Chart of Accounts based on the RRIF (Računovodstvo, revizija, financije i kontroling) standard, version 2021. The module provides the complete accounting chart, tax structure, and fiscal positions required for Croatian compliance.

Sources:
- [RRIF Chart of Accounts 2016](https://www.rrif.hr/dok/preuzimanje/Bilanca-2016.pdf)
- [RRIF-RP2021](https://www.rrif.hr/dok/preuzimanje/RRIF-RP2021.PDF)
- [RRIF-RP2021 English](https://www.rrif.hr/dok/preuzimanje/RRIF-RP2021-ENG.PDF)

## Dependencies

| Module | Purpose |
|--------|---------|
| [[Modules/Account]] | Core accounting framework |
| [[Modules/base_vat]] | VAT number validation for Croatian VAT (OIB) |

## Auto-Install

This module auto-installs with `account` when the company's country is set to Croatia.

## Key Components

### Chart of Accounts

The module installs the RRIF 2021 Croatian Chart of Accounts with:
- Full account hierarchy (6-digit account codes)
- Account types matching Croatian legal requirements
- Analytic account tags for cost tracking

### Tax Structure

Croatian VAT rates implemented:
- **25%** - Standard rate (PDV stopa 25%)
- **13%** - Reduced rate (PDV stopa 13%)
- **5%** - Super-reduced rate (PDV stopa 5%)
- **0%** - Zero rate (oslobođeno)

### Fiscal Positions

Pre-configured fiscal positions for:
- Domestic B2B transactions
- EU intra-community supplies
- Export outside EU
- B2C sales

## Models

### `account.chart.template`

Inherited from [[Modules/Account]] to provide Croatian-specific chart of accounts data.

```python
class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    # Installs RRIF 2021 chart of accounts
    # Configures Croatian tax templates
```

## Croatian-Specific Fields

### VAT / OIB (Osobni identifikacijski broj)

Croatia uses the **OIB** (Personal Identification Number) as the VAT number:
- 11-digit number
- Used for both company and personal tax identification
- Validated via [[Modules/base_vat]]

### Tax Reporting

The module configures `account_tax_report_data.xml` which provides:
- PDV (VAT) return report structure
- Intrastat reporting data structure
- Annual financial report mapping

## Related Modules

| Module | Relationship |
|--------|-------------|
| [[Modules/l10n_hr_edi]] | EDI/e-invoicing integration (MojEracun + Fiscalization) |
| [[Modules/l10n_hr_kuna]] | Historical Kuna currency module (pre-Euro, deprecated) |

## Technical Notes

- Croatia transitioned from HRK (Kuna) to EUR (Euro) on **2023-01-01**
- The `l10n_hr_kuna` module provides legacy Kuna support
- All new implementations should use this `l10n_hr` module with EUR
- RRIF account codes follow the standard: X-XXXX-XXXXXX pattern

## Configuration

1. Install the module via Apps
2. Set company country to Croatia
3. The chart of accounts and taxes will auto-install
4. Configure fiscal positions based on business type

## See Also

- [[Modules/l10n_hr_edi]] - Croatian e-invoicing and fiscalization
- [[Modules/l10n_hr_kuna]] - Historical Kuna currency module
