---
type: module
module: l10n_gr_edi
tags: [odoo, odoo19, l10n, localization, greece, edi, mydata, einvoicing, IAPR]
created: 2026-04-06
---

# Greece EDI / myDATA (`l10n_gr_edi`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Greece - myDATA |
| **Technical** | `l10n_gr_edi` |
| **Category** | Accounting/Localizations |
| **Country** | Greece (GR) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |

## Description

This module provides Greek tax compliance through the **myDATA** platform (my Digital Accounting Application). Created by Greece's tax authority, the **Independent Authority for Public Revenue (IAPR - ΑΑΔΕ - Ανεξάρτητη Αρχή Δημοσίων Εσόδων)**, myDATA digitizes business tax and accounting information declaration.

### Key Capabilities

- **myDATA API Integration**: Send invoice data to IAPR via REST API
- **Expense Classification**: Classify vendor bill expenses per Greek taxonomy
- **Classification Marks**: myDATA classification codes for invoices
- **Invoice QR Codes**: Include myDATA QR codes on printed invoices
- **B2G/B2B Compliance**: Mandatory transmission to tax authority

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/l10n_gr](l10n_gr.md) | Greek base accounting |

## Auto-Install

Auto-installs with `l10n_gr` when dependencies are met.

## myDATA API

### API Endpoints

```python
# Test environment
url = "https://mydataapidev.aade.gr/{endpoint}"

# Production environment
url = "https://mydatapi.aade.gr/myDATA/{endpoint}"
```

### Supported Endpoints

| Endpoint | Purpose |
|----------|---------|
| `SendInvoices` | Send customer invoices to myDATA |
| `SendExpensesClassification` | Send vendor bill expense classification |
| `RequestDocs` | Fetch third-party invoices issued to the company |

### Authentication

```
Headers:
  aade-user-id: <AADE User ID (username)>
  ocp-apim-subscription-key: <Subscription Key>
```

## Models

### `l10n_gr_edi.document`

Tracks all sent XML documents to myDATA:

```python
class L10nGrEdiDocument(models.Model):
    _name = 'l10n_gr_edi.document'
    _description = "Greece document object for tracking all sent XML to myDATA"

    move_id = fields.Many2one('account.move')
    state = fields.Selection([
        ('invoice_sent', "Invoice sent"),
        ('invoice_error', "Invoice send failed"),
        ('bill_fetched', "Expense classification ready to send"),
        ('bill_sent', "Expense classification sent"),
        ('bill_error', "Expense classification send failed"),
    ])
    datetime = fields.Datetime(default=fields.Datetime.now)
    attachment_id = fields.Many2one('ir.attachment')
    message = fields.Char()

    # Successful fields
    mydata_mark = fields.Char()  # myDATA invoice mark
    mydata_cls_mark = fields.Char()  # Classification mark
    mydata_url = fields.Char()  # QR code URL
```

### `account.move` Fields

Extends [account.move](account.move.md) with myDATA-specific fields:

```python
l10n_gr_edi_document_ids = fields.One2many(
    'l10n_gr_edi.document',
    inverse_name='move_id',
)
l10n_gr_edi_mark = fields.Char(string='myDATA Mark', readonly=True)
```

### Other Extended Models

| Model | File | Purpose |
|-------|------|---------|
| `account.move.send` | `account_move_send.py` | Send to myDATA |
| `account.move.line` | `account_move_line.py` | Line classification |
| `account.tax` | `account_tax.py` | Tax category mapping |
| `account.fiscal.position` | `account_fiscal_position.py` | Fiscal position classification |
| `res.company` | `res_company.py` | myDATA credentials |
| `res.config.settings` | `res_config_settings.py` | myDATA configuration |
| `res.partner` | `res_partner.py` | Partner myDATA data |
| `product.template` | `product_template.py` | Product classification |
| `preferred.classification` | `preferred_classification.py` | Default classification |

## myDATA Document Flow

### Invoice Sending (Sales)

```
[Post Invoice] -> [Generate myDATA XML] -> [Send to IAPR API]
-> [Receive mydata_mark] -> [Store on document]
-> [Include QR code on invoice report]
```

### Expense Classification (Purchases)

```
[Post Vendor Bill] -> [Mark as "ready to classify"] ->
[Fetch from myDATA via RequestDocs] -> [Match/Create Bill] ->
[Send classification back via SendExpensesClassification]
```

## Classification System

myDATA requires invoices to be classified by:
- **Income/Expense Category**: Greek classification taxonomy
- **Classification Type**:
  - `1` - Classification by amount
  - `2` - Classification by percentage
- **VAT Category**: Tax classification

## API Response Handling

### Success Response

```python
{
    'mydata_mark': '...'  # Invoice mark from IAPR
    'mydata_cls_mark': '...'  # Classification mark
    'mydata_url': '...'  # QR code URL
}
```

### Error Response

```python
{
    'error': '[error_code] Error message.'
}
```

## Configuration

1. Install `l10n_gr` first
2. Install `l10n_gr_edi`
3. Register at myDATA (IAPR/AADE):
   - Obtain user credentials (aade-user-id)
   - Obtain subscription key (ocp-apim-subscription-key)
4. Configure in **Settings > Accounting > Greek myDATA**:
   - Test/Production environment toggle
   - AADE credentials
   - Default classification categories
5. Set preferred classification on products and accounts
6. Configure [Modules/pos](pos.md) if using point of sale

## Data Files

| File | Purpose |
|------|---------|
| `data/ir_cron.xml` | Scheduled myDATA synchronization |
| `data/template.xml` | myDATA XML templates |
| `views/report_invoice.xml` | Invoice report with QR code |

## Related Modules

| Module | Relationship |
|--------|-------------|
| [Modules/l10n_gr](l10n_gr.md) | Base Greek accounting |
| [Modules/pos](pos.md) | Point of Sale integration |

## Technical Notes

- REST API with XML payload (application/xml)
- Timeout: 10 seconds per request
- Test/production environment per company
- Greek AFM is the primary identifier
- Invoice mark (mydata_mark) is mandatory for subsequent operations
- Classification marks are per line item on invoices
- Expense classification sends after invoice posting
- HTTP Basic Auth NOT used - header-based authentication only

## See Also

- [Modules/l10n_gr](l10n_gr.md) - Greek accounting
- [myDATA AADE Documentation](https://www.aade.gr/)
