---
type: module
module: l10n_my
tags: [odoo, odoo19, l10n, localization, malaysia]
created: 2026-04-06
---

# Malaysia Localization (l10n_my)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Malaysia - Accounting |
| **Technical** | `l10n_my` |
| **Category** | Localization / Account Charts |
| **Country** | Malaysia |
| **Author** | Odoo PS |
| **Version** | 1.1 |
| **License** | LGPL-3 |
| **Countries** | Malaysia (MY) |

## Description

Base accounting localization module for Malaysia. Provides Malaysian-specific chart of accounts, tax templates, and account tags that are required for Malaysian businesses to maintain compliant accounting records.

The module establishes the foundation for Malaysia's Goods and Services Tax (GST) / Sales and Service Tax (SST) reporting structures and integrates with the [Modules/l10n_my_edi](modules/l10n_my_edi.md) module for e-invoicing.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account](modules/account.md) | Core accounting |
| [Modules/account_tax_python](modules/account_tax_python.md) | Python-based tax computation |

## Key Models

### `account.chart.template` (template_my.py)
Extends chart of accounts with Malaysian-specific template data:
- Malaysian account code structure
- Tax accounts for SST (Sales and Service Tax)
- Account tags for Malaysian tax reporting

### `product.template` (product_template.py)
Extends product with Malaysian-specific fields:
- **l10n_my_category_code**: Malaysian product category codes for e-invoice classification
- Product classification needed for MyInvois submissions

## Tax Structure

### SST (Sales and Service Tax)
- Standard SST rates (6% service tax, varying sales tax)
- Zero-rated and exempt supplies
- Account tags for proper tax line classification

### Tax Reporting
- Account tags assigned to taxes for LHDN (Lembaga Hasil Dalam Negeri) reporting
- Support for both SST and GST (if transitioning)
- Tax report data structure compatible with Malaysian tax authority formats

## Data Files

- `data/account_tax_report_data.xml` - Malaysian tax report structures
- `data/account.account.tag.csv` - Account tags for tax classification
- `views/product_template_view.xml` - Product form customization
- `demo/demo_company.xml` - Demo company data

## Related

- [Modules/account](modules/account.md) - Core accounting module
- [Modules/l10n_my_edi](modules/l10n_my_edi.md) - Malaysia e-invoicing (MyInvois)
- [Modules/l10n_my_edi_pos](modules/l10n_my_edi_pos.md) - POS e-invoicing integration
- [Modules/l10n_my_ubl_pint](modules/l10n_my_ubl_pint.md) - Malaysia UBL PINT format for Peppol
