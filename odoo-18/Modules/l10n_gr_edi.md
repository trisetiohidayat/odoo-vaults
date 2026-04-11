---
Module: l10n_gr_edi
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #greece #mydata
---

# l10n_gr_edi

## Overview
Integrates with Greece's **myDATA** platform (Μητρώο Διαβίβασης Αναλυτικών Δεδομένων Φορολογίας) operated by IAPR (Independent Authority for Public Revenue). myDATA digitizes all business tax and accounting information transmission to the tax authority. This module sends invoice data and expense classifications.

## EDI Format / Standard
**myDATA XML** — Custom XML format defined by IAPR. API endpoints: `SendInvoices` (outgoing invoices), `SendExpensesClassification` (vendor bill expense codes), `RequestDocs` (fetch third-party invoices). HTTPS POST with `aade-user-id` and `ocp-apim-subscription-key` headers.

## Dependencies
- `l10n_gr` — Greek chart of accounts

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `GreeceEDIDocument` | `l10n_gr_edi.document` | `base` | Tracks all sent XML; state: invoice_sent/bill_fetched/bill_sent; stores mydata_mark, mydata_cls_mark, mydata_url |
| `AccountFiscalPosition` | `account.fiscal.position` | `account.fosition` | Maps fiscal positions to myDATA classification codes |
| `AccountMove` | `account.move` | `account.move` | Submit invoices; fetch vendor bill classifications |
| `AccountMoveLine` | `account.move.line` | `account.move.line` | Expense classification codes per line |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard |
| `AccountTax` | `account.tax` | `account.tax` | Tax classification for myDATA |
| `PreferredClassification` | `l10n_gr_edi.preferred_classification` | `base` | Partner/product preferred expense classification |
| `ProductTemplate` | `product.template` | `product.template` | Product-level classification |
| `ResCompany` | `res.company` | `res.company` | myDATA credentials: test_env flag, AADE user ID, AADE key |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `ResPartner` | `res.partner` | `res.partner` | Partner classification preferences |

## Data Files
- `data/ir_cron.xml` — Cron job for batch sending and status sync
- `data/template.xml` — QWeb invoice XML template for myDATA

## How It Works

### Invoice Submission
1. On `action_l10n_gr_edi_send_invoices()`: builds myDATA XML
2. POST to `mydatapi.aade.gr/myDATA/SendInvoices`
3. Response parsed: `invoiceMark` (unique ID), `qrUrl`, optional `classificationMark`
4. Document record updated with mark and URL

### Vendor Bill Classification
1. Vendor bill posted → `l10n_gr_edi.document` in `bill_fetched` state
2. User sets expense classification on lines (via fiscal position or product preference)
3. `action_l10n_gr_edi_send_expenses()` sends classification to myDATA
4. Classification mark stored

### RequestDocs
For vendor bills issued by third parties: `action_l10n_gr_edi_request_docs()` fetches invoices matching criteria from myDATA.

### myDATA API
- Test environment: `mydataapidev.aade.gr`
- Production: `mydatapi.aade.gr`
- Headers: `aade-user-id`, `ocp-apim-subscription-key`
- Timeout: 10 seconds
- Response: XML with `<response><index>`, `<statusCode>` (Success/Error), `<invoiceMark>`, `<classificationMark>`, `<qrUrl>`

## Installation
Auto-installs with `l10n_gr`. No post-init hook.

## Historical Notes
- **Odoo 18**: New module for myDATA compliance. Greece mandated electronic invoice reporting through myDATA for all businesses. The platform supports both B2C and B2B scenarios with QR code generation for verification.