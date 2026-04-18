---
title: "Account Peppol"
module: account_peppol
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Account Peppol

## Overview

Module `account_peppol` — auto-generated from source code.

**Source:** `addons/account_peppol/`
**Models:** 9
**Fields:** 41
**Methods:** 16

## Models

### account.edi.common (`account.edi.common`)

—

**File:** `account_edi_common.py` | Class: `AccountEdiCommon`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account_edi_proxy_client.user (`account_edi_proxy_client.user`)

Save new documents in an accounting journal, when one is specified on the company.

        :param attachment: the new document
        :param peppol_state: the state of the received Peppol document
 

**File:** `account_edi_proxy_user.py` | Class: `Account_Edi_Proxy_ClientUser`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `proxy_type` | `Selection` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.edi.xml.ubl_20 (`account.edi.xml.ubl_20`)

When generating the XML on behalf of the parent peppol company,
        use the parent company details on the XML.

**File:** `account_edi_ubl_xml.py` | Class: `AccountEdiXmlUbl_20`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### account.journal (`account.journal`)

—

**File:** `account_journal.py` | Class: `AccountJournal`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `account_peppol_proxy_state` | `Selection` | Y | — | Y | — | — |
| `is_peppol_journal` | `Boolean` | Y | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `button_fetch_in_einvoices` | |
| `button_refresh_out_einvoices_status` | |


### account.move (`account.move`)

—

**File:** `account_move.py` | Class: `AccountMove`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `peppol_message_uuid` | `Char` | — | — | — | — | — |
| `peppol_move_state` | `Selection` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_send_and_print` | |
| `action_cancel_peppol_documents` | |


### account.move.send (`account.move.send`)

By default, we use the sending method set on the partner or email and peppol.

**File:** `account_move_send.py` | Class: `AccountMoveSend`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_what_is_peppol_activate` | |


### account_edi_proxy_client.user (`account_edi_proxy_client.user`)

Gets the closest parent company (relative from the current)
        that has an active peppol connection.
        :return: res.company record: containing single company if found, empty if not.

**File:** `res_company.py` | Class: `ResCompany`

#### Fields (15)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `account_peppol_contact_email` | `Char` | Y | — | Y | Y | — |
| `account_peppol_migration_key` | `Char` | Y | — | — | Y | — |
| `account_peppol_phone_number` | `Char` | Y | — | — | Y | — |
| `account_peppol_proxy_state` | `Selection` | — | — | — | — | — |
| `account_peppol_edi_user` | `Many2one` | Y | — | Y | — | — |
| `peppol_eas` | `Selection` | — | — | Y | — | — |
| `peppol_endpoint` | `Char` | Y | — | Y | — | — |
| `peppol_purchase_journal_id` | `Many2one` | Y | — | — | Y | — |
| `peppol_external_provider` | `Char` | Y | — | — | — | — |
| `peppol_can_send` | `Boolean` | Y | — | — | — | — |
| `peppol_parent_company_id` | `Many2one` | Y | — | — | — | — |
| `peppol_metadata` | `Json` | — | — | — | — | — |
| `peppol_metadata_updated_at` | `Datetime` | — | — | — | — | — |
| `peppol_activate_self_billing_sending` | `Boolean` | — | — | — | — | — |
| `peppol_self_billing_reception_journal_id` | `Many2one` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `create` | |
| `write` | |


### res.config.settings (`res.config.settings`)

Register the existing user as a receiver.

**File:** `res_config_settings.py` | Class: `ResConfigSettings`

#### Fields (15)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `account_peppol_edi_user` | `Many2one` | Y | — | Y | — | — |
| `account_peppol_edi_mode` | `Selection` | Y | — | Y | — | — |
| `account_peppol_contact_email` | `Char` | Y | — | Y | — | — |
| `account_peppol_eas` | `Selection` | — | — | Y | — | — |
| `account_peppol_edi_identification` | `Char` | — | — | Y | — | — |
| `account_peppol_endpoint` | `Char` | — | — | Y | — | — |
| `account_peppol_migration_key` | `Char` | — | — | Y | — | — |
| `account_peppol_phone_number` | `Char` | — | — | Y | — | — |
| `account_peppol_proxy_state` | `Selection` | — | — | Y | — | — |
| `account_peppol_purchase_journal_id` | `Many2one` | Y | — | Y | — | — |
| `peppol_external_provider` | `Char` | Y | — | Y | — | — |
| `peppol_use_parent_company` | `Boolean` | Y | — | Y | — | — |
| `peppol_parent_company_name` | `Char` | Y | — | Y | — | — |
| `account_is_token_out_of_sync` | `Boolean` | — | — | Y | — | — |
| `peppol_participation_role` | `Selection` | Y | — | — | — | — |


#### Methods (7)

| Method | Description |
|--------|-------------|
| `action_open_peppol_form` | |
| `button_open_peppol_config_wizard` | |
| `button_peppol_disconnect_branch_from_parent` | |
| `button_peppol_register_sender_as_receiver` | |
| `button_reconnect_this_database` | |
| `button_disconnect_this_database` | |
| `button_peppol_deregister` | |


### res.partner (`res.partner`)

<ul>
                <li>
                    <span class='o-mail-Message-trackingOld me-1 px-1 text-muted fw-bold'>{old}</span>
                    <i class='o-mail-Message-trackingSeparator fa fa-lo

**File:** `res_partner.py` | Class: `ResPartner`

#### Fields (6)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `invoice_sending_method` | `Selection` | Y | — | — | — | — |
| `peppol_eas` | `Selection` | Y | — | — | — | — |
| `available_peppol_sending_methods` | `Json` | Y | — | — | — | — |
| `available_peppol_edi_formats` | `Json` | Y | — | — | — | — |
| `peppol_verification_state` | `Selection` | — | — | — | — | — |
| `body` | `Markup` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `create` | |
| `button_account_peppol_check_partner_endpoint` | |




## Related

- [[Modules/Base]]
- [[Modules/Account]]
