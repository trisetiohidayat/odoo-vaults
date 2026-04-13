---
type: module
module: l10n_tr_nilvera_einvoice_extended
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Turkey Accounting Localization (`l10n_tr_nilvera_einvoice_extended`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | This module enhances the core Nilvera integration by adding additional invoice scenarios and types required for Turkish e-Invoicing compliance. |
| **Technical** | `l10n_tr_nilvera_einvoice_extended` |
| **Category** | Accounting/Accounting |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
This module enhances the core Nilvera integration by adding additional invoice scenarios and types required for Turkish e-Invoicing compliance.

Features include:
    1.Support for invoice scenarios: Basic, Export, and Public Sector
    2.Support for invoice types: Sales, Withholding, Tax Exempt, and Registered for Export
    3.Configuration of withholding reasons and exemption reasons
    4.Addition of Tax Offices.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_tr_nilvera_einvoice` | Dependency |
| `contacts` | Dependency |

## Technical Notes
- Country code: `tr`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: account_tax.py, account_move.py, account_move_send.py, account_move_line.py, product_template.py, product_product.py, res_company.py, l10n_tr_nilvera_einvoice_extended_tax_office.py, l10n_tr_nilvera_einvoice_extended_account_tax_code.py, res_config_settings.py, account_edi_xml_ubl_tr.py, template_tr.py, res_partner.py

## Related
- [Modules/l10n_tr](odoo-18/Modules/l10n_tr.md) - Core accounting