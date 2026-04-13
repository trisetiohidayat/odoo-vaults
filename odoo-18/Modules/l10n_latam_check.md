---
Module: l10n_latam_check
Version: 18.0
Type: l10n/latam-checks
Tags: #odoo18 #l10n #accounting #latam #checks
---

# l10n_latam_check — Third Party and Deferred/Electronic Checks Management

## Overview
Manages both own (company-issued) and third-party checks within the LATAM accounting framework. Extends the base `account_check_printing` module with deferred/electronic check support, post-dated check cash-in dates, split move line generation for multiple checks, and a full operations trail (handed → deposited → rejected → returned → voided). Originated in Argentine localization; generalized for all LATAM countries. Used by [Modules/l10n_ar](odoo-18/Modules/l10n_ar.md) for AFIP-compliant check workflows.

## Country/Region
Multi-country (LATAM)

## Dependencies
- account
- base_vat

## Key Models

### `l10n_latam.check`
Inherits: `models.Model`, `mail.thread`, `mail.activity.mixin`
- `_name`: `l10n_latam.check`
- `_check_company_auto`: True
- `_table`: no custom table (uses `l10n_latam_check_account_payment_rel` m2m relation)

Fields:
- `payment_id` (Many2one account.payment, required, cascade delete): The originating payment
- `operation_ids` (Many2many account.payment): All operations performed on this check
- `current_journal_id` (Many2one account.journal, computed+stored): Journal where check currently resides (last inbound operation)
- `name` (Char): Check number, auto-zero-padded to 8 digits on change
- `bank_id` (Many2one res.bank, computed): Bank from partner for third-party checks
- `issuer_vat` (Char, computed): VAT of check issuer (third-party checks); cleaned via `stdnum`
- `payment_date` (Date, required): For deferred/post-dated checks
- `amount` (Monetary): Check amount
- `outstanding_line_id` (Many2one account.move.line): The suspense/reconcilable line; used to detect debited/voided state
- `issue_state` (Selection: handed | debited | voided, computed+stored): State derived from reconciliation
- Related fields: `payment_method_code`, `partner_id`, `original_journal_id`, `company_id`, `currency_id`, `payment_method_line_id`

SQL constraint: `l10n_latam_check_unique` on `(name, payment_method_line_id)` WHERE `outstanding_line_id IS NOT NULL` — prevents duplicate check numbers.

Methods:
- `_auto_init()`: Creates the unique index
- `_onchange_name()`: Zero-pads check number to 8 digits
- `_prepare_void_move_vals()`: Creates voiding journal entry (debits outstanding account, credits payable)
- `_compute_issue_state()`: If outstanding_line has no residual and is reconciled with a payable/receivable line → `voided`; if no residual but reconciled with non-payable → `debited`; otherwise → `handed`
- `action_void()`: Creates void move and reconciles with outstanding line
- `_get_last_operation()`: Returns most recent non-draft/cancelled payment operation, sorted by date and origin id
- `_compute_current_journal()`: Inbound payments track journal; outbound = False
- `button_open_payment()` / `button_open_check_operations()` / `action_show_reconciled_move()` / `action_show_journal_entry()`: Navigation actions
- `_get_reconciled_move()`: Returns the move containing the reconciliation counterpart
- `_constrains_min_amount()`: Validates amount > 0
- `_compute_bank_id()` / `_compute_issuer_vat()`: For new third-party checks only (third-party checks only)
- `_clean_issuer_vat()`: Onchange that compacts VAT via stdnum per country
- `_check_issuer_vat()`: Validates VAT format against base_vat per country
- `_unlink_if_payment_is_draft()`: Prevents deletion of non-draft check payments

### `account.payment` (Extended)
Inherits: `account.payment`
Added fields:
- `l10n_latam_new_check_ids` (One2many l10n_latam.check): Own checks or new third-party checks
- `l10n_latam_move_check_ids` (Many2many l10n_latam.check): Checks being moved/operated
- `l10n_latam_check_warning_msg` (Text, computed): Warning for invalid operations
- `amount` (Monetary, computed, readonly=False): Computed from linked checks

Methods:
- `_is_latam_check_payment()`: Checks if payment method code is any check type
- `_get_latam_checks()`: Returns linked checks based on payment type
- `_get_blocking_l10n_latam_warning_msg()`: Validates currency match, amount match, check state, date ordering, journal consistency
- `_get_reconciled_checks_error()`: Prevents cancel/re-open of payments with debited/voided checks
- `_l10n_latam_check_split_move()`: For own checks with multiple checks: creates one liquidity line per check with payment_date as maturity
- `_l10n_latam_check_unlink_split_move()`: Deletes split move on draft reset
- `_prepare_move_line_default_vals()`: Adds check name and date to liquidity line for own checks
- `_compute_destination_account_id()`: For transfers without partner, uses transfer account
- `_is_latam_check_transfer()`: Detects inter-journal check transfers
- `_get_trigger_fields_to_synchronize()`: Includes `l10n_latam_new_check_ids`

### `account.move` (Extended)
Inherits: `account.move`
Method `button_draft()`: Unlinks split move when resetting own-check payments to draft.

### `account.journal` (Extended)
Inherits: `account.journal`
Methods:
- `_default_outbound_payment_methods()`: Adds own_checks and return_third_party_checks for AR companies
- `_get_reusable_payment_methods()`: Allows multiple own_checks instances in a journal
- `create()`: Auto-sets default payment accounts for check journals (1.1.1.02.003 inbound checks account, 1.1.1.02.004 outbound checks account) for AR bank/cash journals

## Payment Methods
Defined in `data/account_payment_method_data.xml`:
- `own_checks`: Company-issued checks (deferred/electronic)
- `new_third_party_checks`: Checks received from customers
- `in_third_party_checks`: Incoming third-party checks on hand
- `out_third_party_checks`: Third-party checks delivered to vendors
- `return_third_party_checks`: Returned/rejected third-party checks

## How It Works
1. Payment with own_checks method: creates `l10n_latam.check` with `outstanding_line_id` pointing to the suspense line; if multiple checks, creates split move with per-check liquidity lines
2. Third-party checks: received via `new_third_party_checks`, held in journal, deposited or delivered
3. Operations linked via `operation_ids`: deposit, rejection (by bank), return (from vendor), transfer between journals
4. `_compute_issue_state()` auto-transitions: `handed` → `debited` (settled) or `voided` (voided by issuer)
5. Void action creates reversing journal entry and reconciles with outstanding line
6. Mass transfer wizard batches multiple check operations

## Data Files
- `data/account_payment_method_data.xml`: Payment method definitions
- `wizards/l10n_latam_payment_mass_transfer_views.xml`: Mass transfer wizard
- `wizards/account_payment_register_views.xml`: Payment register wizard
- `security/ir.model.access.csv`: ACL for l10n_latam.check
- `security/security.xml`: Record rules
- `views/account_payment_view.xml`: Check fields on payment form
- `views/l10n_latam_check_view.xml`: Check list/form views

## Installation
Install after `account`. Works standalone for any LATAM company. Required by `l10n_ar` for AFIP-compliant check workflows.

## Historical Notes
The check management module originated in the Argentine localization where paper checks are still widely used alongside electronic transfers. The key design insight: the `l10n_latam.check` model is separate from `account.payment` to allow multiple operations (deposit, rejection, return, transfer) on a single check while keeping the payment immutable. The `outstanding_line_id` pattern (tracking the reconcilable suspense line) enables automatic state detection without custom state fields. The split move feature for multiple own checks on a single payment was added because Argentine businesses frequently issue multiple post-dated checks at once.
