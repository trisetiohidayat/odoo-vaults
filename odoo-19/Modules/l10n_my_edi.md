---
type: module
module: l10n_my_edi
tags: [odoo, odoo19, l10n, localization, malaysia, edi, einvoice]
created: 2026-04-06
---

# Malaysia EDI - MyInvois E-invoicing (l10n_my_edi)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Malaysia - E-invoicing |
| **Technical** | `l10n_my_edi` |
| **Category** | Localization / EDI |
| **Country** | Malaysia |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Malaysia (MY) |

## Description

Malaysian e-invoicing module that integrates with the MyInvois system mandated by LHDN (Lembaga Hasil Dalam Negeri), the Malaysian tax authority. Under the Malaysian e-invoicing mandate, businesses are required to submit invoices electronically through the MyInvois portal.

This module enables:
- Generation of compliant e-invoices in UBL PINT format
- Direct submission to the MyInvois system via API
- Real-time status tracking of submitted invoices
- Submission through the Peppol network

The module depends on [Modules/l10n_my_ubl_pint](modules/l10n_my_ubl_pint.md) for the underlying UBL format and reuses fields defined there.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/l10n_my](modules/l10n_my.md) | Base Malaysian accounting localization |
| [Modules/l10n_my_ubl_pint](modules/l10n_my_ubl_pint.md) | UBL PINT format for e-invoice generation |
| [Modules/account_edi_proxy_client](modules/account_edi_proxy_client.md) | EDI proxy client for API communication |
| [Modules/account_edi](modules/account_edi.md) | EDI framework |

## Key Models

### `myinvois.document` (myinvois_document.py)
Core model managing MyInvois document lifecycle:
- Document creation and submission
- Status tracking (Pending, Valid, Invalid, Cancelled)
- API communication with MyInvois/LHDN
- Encryption and signing of documents

**Document States**:
- `pending`: Awaiting response from MyInvois
- `valid`: Accepted and validated by LHDN
- `invalid`: Rejected with errors
- `cancelled`: Cancelled after LHDN approval

### `account.move` (account_move.py)
Extends `account.move` with MyInvois fields:
- E-invoice submission status
- MyInvois document reference
- Validation state from LHDN
- QR code for invoice verification

### `account.move.send` (account_move_send.py)
Extends the invoice send workflow to include MyInvois submission.

### `account.edi.proxy.user` (account_edi_proxy_user.py)
EDI proxy user configuration for MyInvois API:
- API credentials management
- Company identification for LHDN
- Secure credential storage

### `res.company` (res_company.py)
Company settings for MyInvois:
- LHDN identification number (TIN / BRN)
- Company registration details
- E-invoice configuration

### `res.partner` (res_partner.py)
Extends partner with fields for e-invoice:
- MyInvois buyer identification
- TIN and BRN fields
- Contact information for e-invoice delivery

### `product.template` (product_template.py)
Extends product with classification for e-invoice:
- HS (Harmonized System) code classification
- Product category mapping for MyInvois

### `l10n_my_edi.industry.classification` (l10n_my_edi_industry_classification.py)
Industry classification codes required for MyInvois:
- MSIC (Malaysia Standard Industrial Classification) codes
- Industry-specific classification

## Country-Specific Features

### MyInvois Submission Flow
1. **Generate**: Create UBL invoice in PINT format
2. **Sign**: Digitally sign the invoice
3. **Submit**: Send to MyInvois via API or Peppol
4. **Validate**: LHDN validates the invoice
5. **Receive**: Obtain validated invoice with QR code
6. **Share**: Invoice shared with buyer

### Mandatory Fields
- Seller TIN and BRN
- Buyer TIN or IC number
- Invoice line details with HS codes
- Tax breakdown (SST amounts)
- Industry classification code

### Peppol Network
- Supports submission via Peppol BIS Billing 3.0 (PINT format)
- Peppol Service Metadata Publisher (SMP) registration
- Access point configuration

## Data Files

- `data/ir_cron.xml` - Scheduled jobs for status synchronization
- `data/l10n_my_edi.industry.classification.csv` - MSIC industry codes
- `security/ir.model.access.csv` - Access rights
- `security/myinvois_security.xml` - Record rules
- `views/account_move_view.xml` - Invoice form updates
- `views/account_tax_view.xml` - Tax form updates
- `views/myinvois_document_views.xml` - Document management views
- `views/product_template_view.xml` - Product updates
- `views/report_invoice.xml` - Invoice report with QR code
- `views/res_company_view.xml` - Company settings
- `views/res_config_settings_view.xml` - Configuration
- `views/res_partner_view.xml` - Partner updates
- `views/account_portal_templates.xml` - Customer portal views
- `wizard/myinvois_consolidate_invoice_wizard.xml` - Consolidation wizard
- `wizard/myinvois_document_status_update_wizard.xml` - Status update wizard

## Related

- [Modules/l10n_my](modules/l10n_my.md) - Core Malaysian accounting
- [Modules/l10n_my_ubl_pint](modules/l10n_my_ubl_pint.md) - UBL PINT format
- [Modules/l10n_my_edi_pos](modules/l10n_my_edi_pos.md) - POS e-invoicing integration
- [Modules/account_edi_proxy_client](modules/account_edi_proxy_client.md) - EDI proxy framework
