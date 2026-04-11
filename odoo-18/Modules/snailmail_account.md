---
Module: snailmail_account
Version: 18.0.0
Type: addon
Tags: #odoo18 #snailmail_account #account #postal
---

## Overview

`snailmail_account` extends the base `snailmail` module with account-specific postal letter sending. Integrates with the `account.move.send` wizard to offer "Send by Post" as a payment/communication method for invoices and other account documents. Automatically validates partner address and shows alerts if address is incomplete before sending.

## Models

### account.move.send (extends base)
**Inheritance:** `account.move.send` (abstract, extends `account` module)

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_alerts | self, moves, moves_data | dict | **Extends account:** Adds `snailmail_account_partner_invalid_address` alert if any move has `snailmail` in sending_methods but partner has invalid address. Level is 'danger' for single, 'warning' for multiple |
| _prepare_snailmail_letter_values | self, move | dict | Returns letter values: `partner_id`, `model='account.move'`, `res_id=move.id`, `company_id`, `report_template=account_invoices report` |
| _is_applicable_to_move | self, method, move, **move_data | bool | Returns False for `snailmail` if partner address is invalid (`_is_valid_address()` returns False). For valid addresses, calls `super()` |
| _hook_if_success | self, moves_data | None | **Extends account:** After successful email/web sending, checks for `snailmail` in `sending_methods`. Creates `snailmail.letter` records with values from `_prepare_snailmail_letter_values()` (using `author_user_id` from move_data). Triggers `_snailmail_print(immediate=False)` for batch processing |

### res.partner (extends base)
**Inheritance:** `res.partner` (classic `_inherit`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| invoice_sending_method | Selection | Adds `'snailmail'` (Send by Post) as a sending method option |

### account.move.send.batch.wizard (extends base)
**Inheritance:** `account.move.send.batch.wizard` (abstract)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| send_by_post_stamps | Integer | Computed count of move partners with valid snailmail addresses |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_send_by_post_stamps | self | None | Counts `move_ids.partner_id` records that pass `_is_valid_address()`. Used to display stamp count in batch summary |
| _compute_summary_data | self | None | **Extends account:** Updates snailmail summary entry with stamp count `(Stamps: N)` in the extra field |

## Security / Data

**Security:** No separate ACLs. Inherits snailmail's access model. No additional security directory.

**Data:** None.

## Critical Notes

- **Address validation at alert time:** `_get_alerts` flags invalid addresses before the user attempts to send, preventing failed letter creation.
- **Immediate vs deferred printing:** `_hook_if_success` passes `immediate=False` to `_snailmail_print()` so letters are queued rather than printed synchronously.
- **Batch wizard integration:** The stamp count (`send_by_post_stamps`) lets users see how many snailmail stamps will be consumed before committing.
- **Report template:** Always uses the standard account invoices report (`account.account_invoices`) — not configurable per letter.
- **Author tracking:** Uses `author_user_id` from the move_data context to attribute the letter to the sending user.
- **v17→v18:** No breaking changes observed. The `_prepare_snailmail_letter_values` pattern is consistent with other account send integrations.
