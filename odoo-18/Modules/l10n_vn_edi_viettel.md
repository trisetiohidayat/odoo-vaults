---
Module: l10n_vn_edi_viettel
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #vietnam #sinvoice #viettel
---

# l10n_vn_edi_viettel

## Overview
Vietnamese e-invoicing module integrating with **SInvoice** (Hóa đơn điện tử) by Viettel, one of Vietnam's accredited e-invoice service providers. Vietnam mandates e-invoice reporting for all businesses, with phased implementation. SInvoice is the Viettel platform for issuing, managing, and submitting invoices to the General Department of Taxation (GDT).

## EDI Format / Standard
**SInvoice JSON API** — Custom JSON format over HTTPS POST. Not UBL-based. Fields include: `transactionUuid`, `invoiceType`, `templateCode`, `invoiceSeries`, `invoiceIssuedDate`, `buyerInfo`, `sellerInfo`, `itemInfo`, `taxBreakdowns`. API endpoint: `https://api-vinvoice.viettel.vn/services/einvoiceapplication/api/`.

## Dependencies
- `l10n_vn` — Vietnamese chart of accounts

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountMove` | `account.move` | `account.move` | Full state: invoice_state (ready_to_send/sent/payment_state_to_update/canceled/adjusted/replaced), transaction_id, symbol (sinvoice.symbol), invoice_number, reservation_code, issue_date, file fields, adjustment/replacement fields |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard |
| `ResCompany` | `res.company` | `res.company` | SInvoice credentials: username, password, token, token_expiry |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `ResPartner` | `res.partner` | `res.partner` | Default SInvoice symbol on partner |
| `SInvoiceTemplate` | `l10n_vn_edi_viettel.sinvoice.template` | `base` | Invoice template (1-6 per Circular 78): value-added, sales, public assets, national reserve, etc. |
| `SInvoiceSymbol` | `l10n_vn_edi_viettel.sinvoice.symbol` | `base` | Invoice symbol: template + series (e.g., "KCTT/24") with validation constraints |

## Data Files
- `security/ir.model.access.csv` — Access control
- `views/account_move_views.xml` — Invoice form
- `views/res_config_settings_views.xml` — Settings
- `views/res_partner_views.xml` — Partner symbol default
- `views/sinvoice_views.xml` — Template and symbol management
- `wizard/account_move_reversal_view.xml` — Reversal wizard
- `wizard/l10n_vn_edi_cancellation_request_views.xml` — Cancellation wizard

## How It Works

### SInvoice API
Direct REST API calls to Viettel SInvoice. Authentication via username/password → access token (5-minute validity, cached). Requests signed with token in cookie.

### Invoice Symbols
Vietnamese invoices require:
- **Template code** (6 types per Circular 78): 1=Value-added, 2=Sales, 3=Public assets, 4=National reserve, 5=National reserve invoice, 6=Warehouse release
- **Symbol** (series): format like "KCST/24", first char C=K (no tax authority code), followed by 2-digit year

### Document State
1. Invoice posted → `ready_to_send`
2. Send: API call → transaction UUID stored
3. Lookup on API: invoice number, reservation code, issue date assigned → `sent`
4. Payment update triggers `payment_state_to_update` → API sync

### Cancellation
Cancellation requests sent to SInvoice with reason, agreement document name/date. On success, Odoo invoice cancelled.

### Adjustment Types
- Type 1: Money adjustment (already issued invoice with wrong amount)
- Type 2: Information adjustment (wrong data, kept invoice number)

### Replacement
`l10n_vn_edi_replacement_origin_id` links replacement invoice to original. Adjustment type 3 (replacement) on SInvoice side.

### Timeout
SInvoice API timeout recommended 60-90 seconds (module uses 60s). Retry with lookup to avoid duplicates.

## Installation
Standard module install. No post-init hook.

## Historical Notes
- **Odoo 17**: Vietnamese e-invoicing not available
- **Odoo 18**: First complete SInvoice/Viettel integration. Vietnam mandated e-invoicing via accredited platforms (of which SInvoice/Viettel is one). Invoice symbol and template management enables compliance with Vietnamese invoice numbering rules.