# Snailmail Account

## Overview
- **Name:** Snail Mail - Account
- **Version:** 0.1
- **Category:** Hidden/Tools
- **Summary:** Send invoices by post via snailmail
- **Dependencies:** `account`, `snailmail`
- **Auto-install:** Yes
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Overview

Bridge module between Accounting and Snailmail. Allows users to send printed invoices through the postal service directly from the invoice send wizard. Integrates the snailmail letter creation into the `account.move.send` flow.

## Models

### `account.move` (Extension)
Extends invoice deletion to also remove associated snailmail letters.

**Methods:**
- `unlink_snailmail_letters()` — When an invoice is deleted, cascades delete all linked `snailmail.letter` records (with `model='account.move'`, `res_id` in self.ids).

### `account.move.send` (Extension)
Integrates snailmail as a sending method in the invoice send wizard.

**Key Methods:**
- `_get_alerts()` — Extends alerts: if any selected invoices have snailmail as sending method but the partner has no valid address, shows a danger/warning alert listing the affected invoices.
- `_prepare_snailmail_letter_values(move)` — Builds the letter creation dict: `partner_id`, `model`, `res_id`, `company_id`, `report_template` (account invoice report).
- `_is_applicable_to_move(method, move)` — Snailmail is only applicable if `snailmail.letter._is_valid_address(partner)` returns True.
- `_hook_if_success(moves_data)` — After successful send, creates `snailmail.letter` records for all moves that had snailmail selected and passed address validation, then triggers `._snailmail_print(immediate=False)`.

### `res.partner` (Extension)
Extends partner invoice sending method to include postal option.

**Fields:**
- `invoice_sending_method` — Adds `'snailmail'` / `'by Post'` to the selection (from `account` module's standard selection).

## Snailmail Send Flow

1. User selects invoices in Accounting and clicks "Send"
2. In the send wizard, selects "by Post" (snailmail) as sending method
3. `_get_alerts()` warns if any partners have invalid addresses
4. On confirm, `_hook_if_success()` creates `snailmail.letter` records
5. Letters are printed via the `snailmail` module's IAP infrastructure

## Related
- [Modules/snailmail](snailmail.md)
- [Modules/Account](Account.md)
