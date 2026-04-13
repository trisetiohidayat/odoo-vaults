---
type: flow
title: "EDI/Peppol Invoice Flow"
primary_model: account.move
trigger: "System — EDI document received via Peppol AP / User — Send Invoice via Peppol button"
cross_module: true
models_touched:
  - account.move
  - account.edi.document
  - account.edi.proxy.user
  - account.edi.document
  - res.partner
  - mail.mail
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Account/invoice-post-flow](Flows/Account/invoice-post-flow.md)"
  - "[Flows/Account/payment-flow](Flows/Account/payment-flow.md)"
  - "[Flows/Purchase/purchase-withholding-flow](Flows/Purchase/purchase-withholding-flow.md)"
source_module: account_edi_ubl_cii
source_path: ~/odoo/odoo19/odoo/addons/account_edi_ubl_cii/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# EDI/Peppol Invoice Flow

## Overview

The EDI/Peppol Invoice Flow automates the exchange of invoices between trading partners via the Peppol e-delivery network (Peppol BIS Billing 3.0). Peppol is the global standard for business document exchange used in over 40 countries. In Odoo 19, the flow is bidirectional: invoices can be **received** from vendors (import path) and **sent** to customers (export path). The flow relies on UBL 2.1 XML format, the Peppol Proxy Service (`account_edi_proxy_user`), and automatic partner matching via Peppol EDI identities.

---

## Trigger Point

**Inbound (Receive):** The Peppol Proxy Service polls the Peppol Access Point (AP) periodically via `account_edi_proxy_user._receive_from_peppol()`. This is driven by an `ir.cron` scheduler (default: every 15 minutes). An incoming AS4/MQ message containing a signed UBL 2.1 XML document is received and decoded.

**Outbound (Send):** A user clicks the **Send & Print** button on a posted `account.move` (invoice), which calls `account.move._check_peppol_export_settings()` and then `account_edi_proxy_user._send_to_peppol()`. This applies only when the partner has a valid Peppol EDI identity (`peppol_edi_identity` on `res.partner`).

---

## Complete Method Chain

```
INBOUND — Peppol Document Received
───────────────────────────────────
1. account_edi_proxy_user._receive_from_peppol()
      │
      ├─► 2. Download Peppol AS4 message (signed UBL 2.1 XML)
      │        └─► Peppol network (external)
      │
      ├─► 3. account.move.import_edi_doc(xml_content)
      │        └─► 4. l10n_ro_edi.extract_ubl(xml_tree)
      │              ├─► 5. UBL 2.1 schema validation (XSD)
      │              ├─► 6. Extract: supplier_name, supplier_vat, peppol_endpoint
      │              └─► 7. Extract: customer_name, invoice_number, date, lines
      │                    └─► 8. Parse tax lines (VAT rate, withholding)
      │
      ├─► 9. res.partner._match_partner_peppol(peppol_endpoint, company_id)
      │        ├─► 10. Search res_partner with peppol_endpoint = endpoint
      │        │         └─► 11. IF peppol_eas + peppol_endpoint match
      │        │               └─► 12. Partner found → proceed
      │        └─► 13. IF no match:
      │                 └─► 14. ValidationError: "Peppol participant not found"
      │
      ├─► 15. account.move.create({
      │            move_type='in_invoice',
      │            partner_id=matched_partner_id,
      │            invoice_line_ids=[...],
      │            l10n_peppol_is_demo=...
      │      })
      │        └─► 16. account.edi.document.create({
      │                  move_id=new_invoice_id,
      │                  edi_format_id=peppol_format_id,
      │                  state='sent_received'
      │            })
      │              └─► 17. State: 'to_send' or 'sent_received' (draft)
      │
      └─► 18. mail.mail.create({
                 from='peppol@odoo.com',
                 subject='Invoice Received: {number}',
                 body='EDI document parsed and ready for review',
                 recipient_id=accountant_user_id
           })

OUTBOUND — Invoice Sent via Peppol
───────────────────────────────────
19. User clicks "Send & Print" on posted account.move
      │
      ├─► 20. account.move._check_peppol_export_settings()
      │        ├─► 21. Check: company has Peppol participant ID
      │        ├─► 22. Check: partner has peppol_endpoint + peppol_eas
      │        └─► 23. IF any check fails → UserError raised
      │
      ├─► 24. account_edi_proxy_user._send_to_peppol(move_id)
      │        ├─► 25. Generate UBL 2.1 XML from account.move
      │        │         └─► 26. l10n_ro_ubl_cii.export_ubl_xml(move)
      │        │               └─► 27. Include: invoice number, date,
      │        │                     tax breakdown, payment terms
      │        ├─► 28. Sign XML with company Peppol certificate
      │        ├─► 29. POST to Peppol AP (AS4 endpoint)
      │        └─► 30. account.edi.document.write({
                      state='outgoing',
                      attachment_ids=[new_attachment_id]
                 })
      │
      └─► 31. Peppol acknowledgment (async callback):
               └─► 32. account_edi_proxy_user._receive_from_peppol()
                     └─► 33. account.edi.document.write({state: 'sent'})
                           └─► 34. mail.mail → accountant: "Invoice delivered"
```

---

## Decision Tree

```
EDI DOCUMENT RECEIVED (inbound)        INVOICE POSTED (outbound)
           │                                      │
           ▼                                      ▼
    ┌──────────────┐                        ┌─────────────────┐
    │  Parse XML   │                        │ Check Peppol    │
    │  UBL 2.1 OK? │                        │ export settings │
    └──────┬───────┘                        └───────┬─────────┘
           │ NO                                    │ FAIL
           ▼                                       ▼
    ┌──────────────┐                        ┌─────────────────┐
    │ Raise: Invalid│                       │ UserError —     │
    │ XML Schema   │                        │ Missing config  │
    └──────────────┘                        └─────────────────┘
           │ YES                                     │ OK
           ▼                                         ▼
    ┌──────────────────┐                    ┌─────────────────┐
    │ Match partner    │                    │ Generate UBL    │
    │ via Peppol ID?   │                    │ 2.1 XML         │
    └────┬────────┬────┘                    └────────┬────────┘
         │ NO     │ YES                            │
         ▼        ▼                                ▼
  ┌─────────────┐  ┌─────────────┐         ┌─────────────────┐
  │ ERROR:      │  │ Create draft│         │ POST to Peppol  │
  │ Partner not │  │ invoice     │         │ Access Point    │
  │ found       │  │ account.move│         └────────┬────────┘
  └─────────────┘  └──────┬──────┘                  │
                          ▼                  ┌──────┴───────┐
                   ┌──────────────┐           │ Ack received │
                   │ Accountant   │           │ within 24h?  │
                   │ reviews →    │           └──────┬───────┘
                   │ action_post  │                  │ NO
                   └──────┬───────┘                  ▼
                          │                 ┌──────────────────┐
                          ▼                 │ Retry via cron  │
                   ┌──────────────┐         │ (max 3 attempts)│
                   │ Post → send  │         └──────────────────┘
                   │ via Peppol   │
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │ Peppol ack   │
                   │ received     │
                   │ → mail.mail  │
                   └──────────────┘
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `account_move` | Created (draft) | `move_type='in_invoice'`, `partner_id`, `state='draft'`, `l10n_peppol_is_demo` |
| `account_edi_document` | Created | `move_id`, `edi_format_id`, `state='sent_received'/'sent'` |
| `account_edi_proxy_user` | Read/Updated | `peppol_endpoint`, `proxy_endpoint`, `account_token` |
| `res_partner` | Read | `peppol_edi_identity`, `peppol_eas`, `peppol_endpoint` matched |
| `ir_attachment` | Created | `name='UBL_Invoice_{number}.xml'`, `datas` (XML binary) |
| `mail_mail` | Created | Notification queued to accountant user |
| `account_move` (outbound) | Updated | `edi_document_ids` state transitions: `to_send` → `outgoing` → `sent` |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Peppol participant not registered | `UserError` "No Peppol participant found for endpoint..." | `peppol_endpoint` not set on partner |
| Invalid XML schema (XSD fail) | `ValidationError` "Invalid EDI document format" | UBL 2.1 schema validation in `l10n_ro_edi` |
| Supplier partner not matched | `UserError` "Partner not found. Create a contact with Peppol ID..." | `_match_partner_peppol()` returns empty recordset |
| Duplicate invoice detected | `UserError` "This invoice has already been received" | MD5/UBL-InvoiceID dedup check in `import_edi_doc()` |
| Company Peppol not configured | `UserError` "Peppol is not configured for your company" | `_check_peppol_export_settings()` fails |
| Network timeout on send | No error raised | Cron retries up to 3 times; `state` remains `to_send` |
| Wrong Peppol EAS scheme | `UserError` "Unsupported Peppol EAS" | Only `0007` (GLN), `0151` (NACE), `0195` (ISO 6523) supported |
| Missing tax on invoice line | `UserError` "Line missing tax — cannot generate valid UBL" | UBL export requires at least one tax per line |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Partner matched | `mail.followers` | Accountant (assigned user) subscribed as follower |
| EDI document created | `ir_attachment` | UBL XML attached to `account.move` as attachment |
| Peppol state updated | `account_edi_document` | State transitions: `to_send` → `outgoing` → `sent` or `sent_received` |
| Mail notification sent | `mail.mail` | Async queue sends email to accountant on receive |
| Sequence consumed | `ir_sequence` | Invoice number consumed (for outbound) |
| Peppol token updated | `account_edi_proxy_user` | `account_token` refreshed on each successful call |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `_receive_from_peppol()` | `sudo()` (system) | No ACL | Cron runs as superuser; writes raw EDI |
| `import_edi_doc()` | `sudo()` | No ACL | Parses and creates move in system context |
| `_match_partner_peppol()` | `sudo()` | Read on `res.partner` | Searches all partners for Peppol ID match |
| `account.move.create()` | `sudo()` | No ACL | Draft invoice created; no user context |
| `action_post()` | Current user | `group_account_invoice` | User must have rights to post vendor bills |
| `_check_peppol_export_settings()` | Current user | `group_account_invoice` | Read-only settings check |
| `_send_to_peppol()` | `sudo()` | No ACL | External API call; system context |
| `mail.mail.create()` | `mail.group` | Public | Follower-based notification |

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside.*

```
Steps 1-18   ✅ INSIDE transaction  — atomic (all or nothing)
             import_edi_doc() creates account.move + edi.document + mail.mail
             together; rollback on any error

Step 19      ✅ INSIDE transaction  — action_post() atomic

Steps 24-30  ❌ OUTSIDE transaction — HTTP POST to Peppol AP (external)
             If POST fails: state stays 'outgoing', cron retries

Step 31-34   ❌ OUTSIDE transaction — async Peppol callback (webhook/queue)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-18 (inbound) | ✅ Atomic | Rollback: no partial invoice created |
| Steps 19-22 | ✅ Atomic | Rollback: posting reversed on error |
| `_send_to_peppol()` | ❌ External HTTP | State stays 'outgoing'; cron retries |
| Peppol acknowledgment | ❌ Async queue | Retried by Peppol AP; mail sent on success |
| Mail notification | ❌ Async queue | Retried by `ir.mail.server` cron |

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Duplicate Peppol message (network retry) | MD5 hash dedup in `_receive_from_peppol()` — second message silently dropped |
| Re-import same invoice XML | `UserError` "This invoice has already been received" — dedup by `ubl_invoice_id` |
| Re-send invoice (double-click) | Second call fails silently if state is already 'outgoing' or 'sent' |
| Peppol AP timeout, retry succeeds | Idempotent: document already delivered; Peppol AP returns same ack |
| Partner re-matched on re-import | Partner matching is deterministic; same endpoint always matches same partner |

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 4 | `_extract_ubl_xml()` | Custom XML parsing for non-standard fields | `self`, `xml_tree` | `super()` then extend |
| Step 9 | `_match_partner_peppol()` | Custom partner matching logic | `endpoint`, `company` | Replace or extend with `super()` |
| Step 15 | `create()` hook | Pre-create invoice adjustment | `vals` | Override `create()` with vals dict |
| Step 20 | `_check_peppol_export_settings()` | Add custom validation | `self` | Extend with `super()` |
| Step 26 | `_generate_ubl_xml()` | Add custom UBL fields (e.g., `Invoice/cac:PaymentMeans`) | `move` | Override in `l10n_ro_ubl_cii` |
| Pre-notification | `_notify_received()` | Custom notification behavior | `move`, `document` | Extend `account.edi.document._notify_received()` |

**Standard override pattern:**
```python
# Extend partner matching with custom scheme
class AccountEdiProxyUser(models.Model):
    _inherit = 'account.edi.proxy.user'

    def _match_partner_peppol(self, endpoint, company_id):
        # Check standard Peppol first
        partner = super()._match_partner_peppol(endpoint, company_id)
        if partner:
            return partner
        # Fallback: match by custom scheme (e.g., VIES VAT number)
        return self.env['res.partner'].search([
            ('l10n_id_vat', '=', endpoint),
            ('company_id', '=', company_id)
        ], limit=1)
```

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Inbound: draft invoice created | Delete draft | `account.move.unlink()` | Only in draft state; no accounting impact |
| Inbound: invoice posted | Reverse via credit note | `account.move._reverse_moves()` | Creates `account.move` type 'refund' |
| Outbound: sent via Peppol | Cancel Peppol (if not delivered) | `account_edi_proxy_user._cancel_peppol()` | Only works before delivery acknowledgment |
| Outbound: already delivered | Issue credit note | `account.move._reverse_moves()` + resend | Original invoice remains in Peppol inbox |
| Peppol state 'sent_received' | Reset to 'to_send' | `account.edi.document.write({state: 'to_send'})` | Re-triggers send workflow |

**Note:** Once an invoice is delivered and acknowledged via Peppol, it is considered legally delivered. Reversal requires a credit note sent through the same channel.

---

## Alternative Triggers

> *All the ways this flow can be initiated.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| Cron scheduler | `_receive_from_peppol()` | Server startup | Every 15 min (configurable) |
| User action (send) | `action_send_and_print()` | Interactive button | On-demand |
| Demo mode | `_send_to_peppol()` with `l10n_peppol_is_demo=True` | Testing | Manual |
| Webhook callback | Peppol AP → Odoo endpoint | External | On delivery |
| Manual import | `account.move.import_edi_doc()` | File upload | On-demand |
| Automated action | `base.automation` on `account.move` | Rule triggered | On state change |

---

## Related

- [Modules/Account](Modules/Account.md) — `account.move` field and method reference
- [Flows/Account/invoice-post-flow](Flows/Account/invoice-post-flow.md) — Invoice posting and journal entry creation
- [Flows/Account/payment-flow](Flows/Account/payment-flow.md) — Payment reconciliation after invoice
- [Flows/Purchase/purchase-withholding-flow](Flows/Purchase/purchase-withholding-flow.md) — Withholding tax on vendor bills
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — State machine design patterns
- [Core/API](Core/API.md) — `@api.model` vs `@api.depends` decorators
