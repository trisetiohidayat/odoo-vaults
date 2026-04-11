---
Module: l10n_hu_edi
Version: 18.0
Type: l10n/hu/edi
Tags: #odoo18 #l10n #edi #hungary #nav
---

# l10n_hu_edi

## Overview
Hungarian e-invoicing module for reporting invoices to NAV (Nemzeti Adó- és Vámhivatal, Hungarian Tax and Customs Authority). Supports three modes:
1. **Invoice reporting** for paper invoices (NAV 3.0 format)
2. **Tax audit export** (Adóhatósági Ellenőrzési Adatszolgáltatás) in NAV 3.0 format
3. **Cancellation** of previously reported invoices

Hungary mandates electronic invoice reporting for all taxable persons from 2021. This module handles the complex NAV XML format with invoice splitting, merging, and chunked HTTP submissions.

## EDI Format / Standard
**NAV 3.0 XML** — Hungarian government e-invoice format (InvoiceData, LineDatas). Uses chunked HTTP POST, base64-encoded content, signature in header. Custom HTTP API with token-based authentication.

## Dependencies
- `account_debit_note` — Debit note support
- `base_iban` — IBAN validation
- `l10n_hu` — Hungarian chart of accounts

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `L10nHuEdiConnection` | — | — | Core HTTP client: chunked upload, query status, cancel. State machine: false → sent → confirmed/rejected → cancel_sent → cancelled |
| `L10nHuEdiConnectionError` | — | `Exception` | Custom exception for NAV connection failures |
| `AccountMove` | `account.move` | `account.move` | Hungarian EDI state (`l10n_hu_edi_state`), payment mode, split/merge logic |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard integration |
| `AccountTax` | `account.tax` | `account.tax` | Tax type for NAV reporting |
| `ProductTemplate` | `product.template` | `product.template` | Product-level NAV classification |
| `ResCompany` | `res.company` | `res.company` | NAV credentials, username, signature key, passphrase |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `ResPartner` | `res.partner` | `res.partner` | Partner IBAN for direct debit |
| `AccountChartTemplate` | `account.chart.template` | `account.chart.template` | HU tax template loading |
| `ProductUoM` | `uom.uom` | `uom.uom` | UoM code mapping for NAV |
| `L10nHuEdiCancellation` | `l10n_hu_edi.cancellation` | `wizard` | Cancellation wizard |
| `L10nHuEdiTaxAuditExport` | `l10n_hu_edi.tax_audit_export` | `wizard` | Tax audit export wizard |

## Data Files
- `data/uom.uom.csv` — UoM code mapping
- `data/account_cash_rounding.xml` — Cash rounding accounts
- `data/template_requests.xml` — QWeb template for NAV request XML
- `data/template_invoice.xml` — Invoice XML template
- `data/ir_cron.xml` — Cron for status polling and batch send

## How It Works

### State Machine
```
False/rejected/cancelled --[upload]--> sent
sent --[query_status]--> confirmed / confirmed_warning / rejected
confirmed/confirmed_warning --[request_cancel]--> cancel_sent
```

### Invoice Processing
1. On posting: `l10n_hu_edi_state` set to `False` (pending)
2. `action_l10n_hu_edi_send` triggers upload
3. For split invoices: multiple `account.edi.document` records created
4. Chunked HTTP POST to NAV with base64-encoded, compressed XML
5. NAV assigns `invoice_qty` (quantity) and `invoice_eid` (entity ID)
6. Status queried periodically via `action_l10n_hu_edi_query_status()`
7. Timeout at 72 hours: document marked as `send_timeout`

### Splitting
NAV requires each invoice line to have at most one tax rate. If a line has mixed taxes, it is automatically split into separate NAV invoice lines.

### Tax Audit Export
Wizards for exporting invoice data in NAV 3.0 format for tax audit purposes. Uses Zeep for WSDL-based SOAP calls (separate from the main HTTP API).

## Installation
Post-init hook sets up default company settings. Demo data: `demo/demo_partner.xml`.

## Historical Notes
- **Odoo 17**: Hungarian e-invoicing existed with NAV 2.0 format
- **Odoo 18**: Updated to NAV 3.0 format; Zeep integration for tax audit; improved chunked upload; state machine refined; timeout handling added
