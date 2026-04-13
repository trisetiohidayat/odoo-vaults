---
type: module
module: account_peppol
tags: [odoo, odoo19, account, invoicing, peppol, edi]
created: 2026-04-06
---

# Peppol

## Overview
| Property | Value |
|----------|-------|
| **Name** | Peppol |
| **Technical** | `account_peppol` |
| **Category** | Accounting/Accounting |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Module for sending and receiving documents via the PEPPOL network in Peppol BIS Billing 3.0 format. Supports 27 European countries (AT, BE, CH, CY, CZ, DE, DK, EE, ES, FI, FR, GR, IE, IS, IT, LT, LU, LV, MT, NL, NO, PL, PT, RO, SE, SI). Auto-installs when `account_edi_ubl_cii` is installed and a company exists in a PEPPOL-supported country.

## Dependencies
- `account_edi_proxy_client`
- `account_edi_ubl_cii`
- External: `phonenumbers` (python3-phonenumbers)

## Key Models
| Model | Type | Description |
|-------|------|-------------|
| `account.move` | Extension | Invoice with `peppol_message_uuid` and `peppol_move_state` |
| `account.move.send` | Extension | PEPPOL sending method, pre-send hook, webhook proxy calls |
| `account.edi.proxy.client.user` | Extension | PEPPOL proxy type, crons, document import/send |
| `account.edi.common` | Extension | Peppol UUID logging on invoice import |
| `account.edi.xml.ubl_20` | Extension | Parent company details in generated XML |
| `account.journal` | Extension | `is_peppol_journal` flag, fetch/refresh buttons |
| `res.company` | Extension | PEPPOL registration state, EAS/endpoint, migration key |
| `res.partner` | Extension | `peppol_verification_state`, sending methods, endpoint lookup |

## `account.move`
### Fields
| Field | Type | Description |
|-------|------|-------------|
| `peppol_message_uuid` | Char | PEPPOL message UUID received from the proxy |
| `peppol_move_state` | Selection | `ready`, `to_send`, `processing`, `done`, `error` |

### Key Methods
- `_compute_peppol_move_state` — Auto-sets `ready` when partner is on Peppol and move is posted sale doc
- `action_cancel_peppol_documents` — Cancels pending documents (not yet `processing`/`done`)
- `action_send_and_print` — Triggers partner Peppol endpoint check before sending

## `account.edi.proxy.client.user` (Extension)
### Crons
| Cron | Schedule | Purpose |
|------|----------|---------|
| `_cron_peppol_get_new_documents` | Incoming | Fetch and import received Peppol documents |
| `_cron_peppol_get_message_status` | Outgoing | Poll status of sent messages |
| `_cron_peppol_get_participant_status` | Periodic | Update local PEPPOL registration state |
| `_cron_peppol_webhook_keepalive` | Periodic | Refresh webhook registration |

### Key Methods
- `_peppol_import_invoice` — Decrypt and create `account.move` from Peppol XML; handles self-billed invoices
- `_peppol_get_new_documents` — Batch-fetch messages from proxy, create moves, acknowledge
- `_peppol_get_message_status` — Poll processing/done/error status per message UUID
- `_peppol_register_sender_as_receiver` — Upgrade sender to receiver role on Peppol
- `_peppol_deregister_participant` — Full deregistration and cleanup
- `_peppol_reset_webhook` — Re-register webhook endpoint
- `_generate_webhook_token` / `_get_user_from_token` — Webhook authentication

## `res.company` (Extension)
### Fields
| Field | Type | Description |
|-------|------|-------------|
| `account_peppol_proxy_state` | Selection | `not_registered`, `sender`, `smp_registration`, `receiver`, `rejected` |
| `account_peppol_edi_user` | Many2one | Related EDI proxy user record |
| `peppol_eas` | Related | EAS code from partner |
| `peppol_endpoint` | Char | Peppol participant ID |
| `peppol_purchase_journal_id` | Many2one | Journal for incoming Peppol invoices |
| `peppol_external_provider` | Char | External Peppol service provider name |
| `peppol_can_send` | Boolean | Computed: proxy state in sender/receiver domain |
| `peppol_parent_company_id` | Many2one | Parent company with active Peppol connection |
| `peppol_metadata` | Json | IAP-driven metadata about the participant |
| `account_peppol_migration_key` | Char | Key for migrating from another Peppol provider |

## `res.partner` (Extension)
### Fields
| Field | Type | Description |
|-------|------|-------------|
| `invoice_sending_method` | Selection | Adds `peppol` option |
| `peppol_verification_state` | Selection | `not_verified`, `not_valid`, `not_valid_format`, `valid` |
| `available_peppol_sending_methods` | Json | Computed sending methods per company |
| `available_peppol_edi_formats` | Json | Computed EDI formats when Peppol selected |

### Key Methods
- `button_account_peppol_check_partner_endpoint` — Trigger Peppol network lookup
- `_get_peppol_verification_state` — NAPTR DNS lookup via Odoo proxy; returns state
- `_peppol_lookup_participant` — Query Odoo proxy for participant info
- `_check_document_type_support` — Verify participant supports given EDI format

## Peppol Move State Flow
```
draft → (posted + valid partner) → ready
ready → _do_peppol_pre_send → to_send
to_send → proxy call → processing
processing → proxy status poll → done | error
```

## Related
- [Modules/account_edi_ubl_cii](Modules/account_edi_ubl_cii.md)
- [Modules/account_edi_proxy_client](Modules/account_edi_proxy_client.md)
- [Modules/account](Modules/account.md)
