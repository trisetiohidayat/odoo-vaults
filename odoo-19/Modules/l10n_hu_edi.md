---
type: module
module: l10n_hu_edi
tags: [odoo, odoo19, l10n, localization, hungary, edi, nav, einvoicing]
created: 2026-04-06
---

# Hungary EDI / NAV E-Invoicing (`l10n_hu_edi`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Hungary - E-invoicing |
| **Technical** | `l10n_hu_edi` |
| **Category** | Accounting/Localizations/EDI |
| **Country** | Hungary (HU) |
| **License** | LGPL-3 |
| **Author** | DO Tech (OdooTech Zrt.), BDSC Business Consulting Kft. & Odoo S.A. |
| **Version** | 1.0.0 |

## Description

This module enables electronic invoicing compliance for Hungary through the **NAV (Nemzeti Adó- és Vámhivatal)** Online Invoice System (Online Számla). It provides:

- **NAV 3.0 Format**: Generates invoices in NAV 3.0 compliant XML format
- **Electronic Reporting**: Real-time reporting of invoices to NAV when issuing paper invoices
- **Tax Audit Export**: Adóhatósági Ellenőrzési Adatszolgáltatás in NAV 3.0 format
- **Debit Notes**: Structured debit note handling via `account_debit_note`
- **Cash Rounding**: Hungarian-specific cash rounding for retail transactions

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account_debit_note](modules/account_debit_note.md) | Debit note support |
| [Modules/base_iban](modules/base_iban.md) | IBAN validation for Hungarian bank accounts |
| [Modules/l10n_hu](modules/l10n_hu.md) | Hungarian base accounting |

## Auto-Install

Auto-installs with `l10n_hu`.

## Key Components

### NAV 3.0 Invoice Format

Hungarian e-invoices use the NAV 3.0 XML schema:
- Full invoice header with supplier/customer details
- Line items with VAT classification
- Payment information
- Invoice totals with tax breakdown

### API Connection: `l10n_hu_edi_connection`

Handles all NAV Online Invoice System API communication:

```python
class L10nHuEdiConnection:
    """Manages NAV API connection and request/response handling"""

    # Endpoints:
    # - Invoice reporting (számla beküldés)
    # - Status query (állapot lekérdezés)
    # - Cancellation (érvénytelenítés)
    # - Tax audit export
```

### EDI State Machine

The `l10n_hu_edi_state` field on [account.move](account.move.md) tracks invoice lifecycle:

```
[pending] --[upload]--> [sent] --[query_status]--> [confirmed / confirmed_warning / rejected]
[confirmed/confirmed_warning] --[request_cancel]--> [cancel_sent] --[query_status]--> [cancelled]
```

## Models

### `account.move` Fields

```python
l10n_hu_edi_state = fields.Selection([
    # State diagram:
    # False, rejected, cancelled --[upload]--> False, sent, send_timeout
    # sent --[query_status]--> sent, confirmed, confirmed_warning, rejected
    # confirmed, confirmed_warning --[request_cancel]--> cancel_sent, cancel_pending
    # cancel_sent, cancel_pending --[query_status]--> confirmed_warning, cancel_pending, cancelled
], string="NAV EDI State")

l10n_hu_payment_mode = fields.Selection([
    ("TRANSFER", "Transfer"),
    ("CASH", "Cash"),
    ("CARD", "Credit/debit card"),
    ("VOUCHER", "Voucher"),
    ("OTHER", "Other"),
], string="Payment mode", help="NAV expected payment mode of the invoice.")
```

### Other Extended Models

| Model | File | Purpose |
|-------|------|---------|
| `account.tax` | `account_tax.py` | NAV tax category mapping |
| `account.move.send` | `account_move_send.py` | EDI sending to NAV |
| `res.company` | `res_company.py` | Company EDI credentials & settings |
| `res.partner` | `res_partner.py` | Partner NAV-specific data |
| `product.template` | `product.py` | NAV product classification |
| `uom.uom` | `uom_uom.py` | NAV unit of measure mapping |
| `res.config.settings` | `res_config_settings.py` | EDI configuration |
| `template.hu` | `template_hu.py` | Hungarian EDI templates |

## Wizards

### `l10n_hu_edi_cancellation`

Request invoice cancellation via NAV:

```python
class L10nHuEdiCancellation(models.TransientModel):
    """Wizard to request NAV invoice cancellation"""
    # Allows user to specify cancellation reason
    # Triggers NAV cancellation request API call
```

### `l10n_hu_edi_tax_audit_export`

Perform Tax Audit Export (Adóhatósági Ellenőrzési Adatszolgáltatás):

```python
class L10nHuEdiTaxAuditExport(models.TransientModel):
    """Export invoice data in NAV 3.0 format for tax audit"""
    # Generates NAV 3.0 compliant XML for tax authority review
```

### `account_move_debit`

Extends standard debit note for Hungarian compliance.

### `account_move_reversal`

Handles credit note reversal in NAV format.

## Configuration

1. Install `l10n_hu` first
2. Install `l10n_hu_edi`
3. Configure NAV credentials in **Settings > Accounting > Settings > Hungarian EDI**:
   - Technical user credentials
   - NAV API endpoint (test/production)
4. Set up invoice sequences in NAV format
5. Configure UoM mappings if using non-standard units
6. Set up cash rounding method for retail journals

## Security

Access rights via `security/ir.model.access.csv`:
- EDI document access for accounting users
- Company-level configuration for admin users

## Data Files

| File | Purpose |
|------|---------|
| `uom.uom.csv` | Unit of measure category mappings |
| `account_cash_rounding.xml` | Hungarian cash rounding methods |
| `template_requests.xml` | NAV request XML templates |
| `template_invoice.xml` | NAV invoice XML template |
| `ir_cron.xml` | Scheduled status query jobs |

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_hu](modules/l10n_hu.md) | Base Hungarian accounting |
| [Modules/account_debit_note](modules/account_debit_note.md) | Debit note support |

## Technical Notes

- Uses `post_init` hook for initial configuration
- NAV 3.0 uses UTF-8 encoded XML
- Hungarian VAT (ÁFA) categories mapped to NAV codes
- Supports both B2B and B2G invoice reporting
- Cash rounding for retail transactions using Hungarian conventions
