---
type: module
module: l10n_vn_edi_viettel
tags: [odoo, odoo19, l10n, localization, vietnam, edi, einvoice]
created: 2026-04-06
---

# Vietnam EDI - E-invoicing via Viettel (l10n_vn_edi_viettel)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Vietnam - E-invoicing |
| **Technical** | `l10n_vn_edi_viettel` |
| **Category** | Localization / EDI |
| **Country** | Vietnam |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Vietnam (VN) |

## Description

Vietnamese e-invoicing module that integrates with Viettel SInvoice platform. This module enables businesses in Vietnam to submit electronic invoices directly to the tax authority through Viettel's SInvoice service, which is one of the authorized e-invoice service providers in Vietnam.

The module handles the complete e-invoice lifecycle including issuance, cancellation requests, and invoice adjustments in compliance with Vietnam's electronic invoice regulations.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/l10n_vn](Modules/l10n_vn.md) | Base Vietnamese accounting localization |
| [Modules/account](Modules/Account.md) | Core accounting |
| [Modules/account_edi](Modules/account_edi.md) | EDI framework for electronic invoice exchange |

## Key Models

### `l10n_vn_edi.viettel.sinvoice` (sinvoice.py)
Main Viettel SInvoice model for managing invoice data exchange with Viettel's platform.

**Fields**:
- Invoice identification and numbering
- Seller/supplier information
- Buyer information
- Line items and tax calculations
- Signature and certification status

### `account.move` (account_move.py)
Extends `account.move` with Viettel-specific fields and methods:
- E-invoice status tracking (draft, submitted, validated, cancelled)
- Viettel-specific invoice reference numbers
- Integration with the SInvoice API

### `account.move.send` (account_move_send.py)
Extends invoice sending workflow to support Viettel SInvoice submission.

### `res.company` (res_company.py)
Company-level configuration for Viettel SInvoice credentials:
- API endpoint settings
- Authentication credentials
- Branch/office identification

### `res.config.settings` (res_config_settings.py)
Settings view for Viettel EDI configuration at company level.

### `res.partner` (res_partner.py)
Extends partner with fields needed for e-invoice submission:
- Tax identification numbers
- Company registration information

## Country-Specific Features

### E-invoice Lifecycle
1. **Draft**: Invoice created in Odoo
2. **Submit**: Invoice sent to Viettel SInvoice platform
3. **Validate**: Invoice confirmed by tax authority
4. **Cancel**: Cancellation request submitted (with tax authority approval)

### Viettel SInvoice Integration
- SOAP/REST API communication with Viettel servers
- XML/JSON invoice format conversion
- Digital signature support
- Status polling and synchronization

### Invoice Types Supported
- Commercial invoices
- Retail invoices
- Export invoices
- Credit notes / adjustments

## Data Files

- `security/ir.model.access.csv` - Access rights for EDI models
- `views/account_move_views.xml` - Invoice form views
- `views/res_config_settings_views.xml` - Configuration views
- `views/res_partner_views.xml` - Partner view updates
- `views/sinvoice_views.xml` - SInvoice management views
- `wizard/account_move_reversal_view.xml` - Invoice reversal wizard
- `wizard/l10n_vn_edi_cancellation_request_views.xml` - Cancellation request wizard

## Uninstall Hook

Cleans up Viettel-specific data and configurations when the module is uninstalled.

## Related

- [Modules/l10n_vn](Modules/l10n_vn.md) - Core Vietnamese accounting localization
- [Modules/account_edi](Modules/account_edi.md) - EDI framework
- [Modules/account_edi_ubl_cii](Modules/account_edi_ubl_cii.md) - UBL/CII invoice format support
