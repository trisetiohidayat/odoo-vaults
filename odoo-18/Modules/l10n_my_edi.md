---
Module: l10n_my_edi
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #malaysia #myinvois #einvoice
---

# l10n_my_edi

## Overview
Malaysia's **MyInvois** e-invoicing integration via the LHDN (Lembaga Hasil Dalam Negeri) API. MyInvois is Malaysia's mandatory e-invoice system for all businesses, with phased implementation starting July 2024. This module generates and submits invoices in the MyInvois UBL 2.1 format via a proxy service.

## EDI Format / Standard
**MyInvois UBL 2.1** — Malaysian extension of UBL 2.1. Format defined by LHDN. Uses `account_edi_proxy_client` for API communication. Submission via IAP proxy (to handle authentication and network). Maximum **100 invoices per batch**. Supports self-billing and foreign customer TIN management.

## Dependencies
- `l10n_my` — Malaysian chart
- `l10n_my_ubl_pint` — Malaysian PINT profile (pre-norm invoice format)
- `account_edi_proxy_client` — Proxy service for EDI communication
- `l10n_my_edi_extended` — Extended features (auto-install)

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountEdiProxyClientUser` | `account.edi.proxy_client.user` | `account.edi.proxy_client.user` | MyInvois proxy user: registers company with LHDN, manages API tokens |
| `AccountEdiXmlUBLMyInvoisMY` | `account.edi.xml.ubl_myinvois_my` | `account.edi.xml.ubl_20` | MyInvois UBL format generator; extends base UBL with Malaysian fields |
| `AccountMove` | `account.move` | `account.move` | Full state machine: `in_progress/valid/rejected/invalid/cancelled`. Fields: uuid, submission_uid, validation_time, file, exemption_reason, custom_form_reference |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Batch send via proxy |
| `AccountTax` | `account.tax` | `account.tax` | Malaysian tax type (E exempt, Z zero-rate, S standard) and exemption codes |
| `L10nMyEdiIndustryClassification` | `l10n_my_edi.industry_classification` | `base` | MSTAR industry classification codes |
| `ProductTemplate` | `product.template` | `product.template` | Industry classification on products |
| `ResCompany` | `res.company` | `res.company` | Proxy user association, LHDN credentials |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `ResPartner` | `res.partner` | `res.partner` | TIN management, foreign TIN validation |

## Data Files
- `data/ir_cron.xml` — Cron: `_cron_l10n_my_edi_synchronize_myinvois` (status sync, max 25 submissions per run)
- `data/l10n_my_edi.industry_classification.csv` — MSTAR industry codes
- `data/my_ubl_templates.xml` — Malaysian UBL template overrides
- `wizard/l10n_my_edi_status_update_wizard.xml` — Status update wizard (cancel/reject)

## How It Works

### Submission Flow
1. Invoice posted → state `in_progress`
2. `_l10n_my_edi_submit_documents()` — batches up to 100 invoices
3. `AccountEdiProxyClientUser._l10n_my_edi_contact_proxy()` — sends via IAP
4. LHDN validates; assigns UUID and submission ID
5. `_l10n_my_edi_fetch_updated_statuses()` — polls for final status (valid/invalid)
6. On `valid`: `validation_time` stored, 72h cancellation window starts
7. On `invalid`: hash stored for retry deduplication

### State Machine
- `in_progress`: Awaiting validation
- `valid`: Confirmed by LHDN; 72h to cancel/reject
- `rejected`: Vendor bill rejected by recipient
- `invalid`: Validation failed; must issue corrected invoice
- `cancelled`: Cancelled within 72h window

### Cron Synchronization
`_cron_l10n_my_edi_synchronize_myinvois` processes up to 25 submissions per run:
- Fetches `in_progress` invoices immediately
- Fetches `valid` invoices validated within 74 hours (with `retry_at` pacing)

### Error Handling
Error codes: `internal_server_error`, `invalid_tin`, `rate_limit_exceeded`, `hash_resubmitted`, `document_tin_not_found`, `document_tin_mismatch`, `multiple_documents_id`, `multiple_documents_tin`, `update_incorrect_state`, `update_period_over`, `update_active_documents`, `update_forbidden`, `document_not_found`, `submission_too_large`.

## Installation
Standard module install. Extended features from `l10n_my_edi_extended` auto-install.

## Historical Notes
- **Odoo 17**: MyInvois integration not available
- **Odoo 18**: First complete MyInvois integration. Malaysia mandated e-invoicing via LHDN starting July 2024. Phase-in by revenue brackets.
- Uses IAP proxy to bridge corporate network to LHDN API
- Industry classification codes sourced from MSTAR (Malaysian Securities Commission)