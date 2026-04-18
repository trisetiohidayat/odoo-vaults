---
type: module
module: l10n_latam_check
tags: [odoo, odoo19, accounting, localization, latam, checks]
created: 2026-04-06
---

# LATAM Check Management (`l10n_latam_check`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Own Checks Management |
| **Technical** | `l10n_latam_check` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | ADHOC SA |
| **Version** | 1.0.0 |

## Description

This module extends Odoo's check printing base to manage both own checks (issued by the company) and third-party checks (received from customers) commonly used in Latin American countries. It provides comprehensive tracking of check lifecycle including issue, deposit, rejection, and void operations.

### Own Checks

- Allow using own checks that are not printed but filled manually by the user
- Support deferred or electronic checks where printing is disabled and the check number is set manually
- Add an optional "Check Cash-In Date" for post-dated checks (deferred payments)
- Provide a menu to track own checks

### Third Party Checks

The module adds two main payment methods:

**New Third Party Checks** — Payments received from a customer via check. When received, the check is tracked as an asset. Operations include:
- Deposit the check at the bank
- Transfer between journals (e.g., shop-to-shop)
- Reject/return to customer

**Existing Third Party Checks** — Track moves of checks that have already been received. Operations include:
- Use a check to pay a vendor
- Deposit the check on the bank
- Get the check back from the bank (rejection)
- Get the check back from the vendor (return)
- Transfer between journals

All operations can be performed on multiple checks at once.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Core accounting, payment model |
| `base_vat` | VAT/TAX number validation for check issuer |

## Payment Method Codes

| Code | Type | Purpose |
|------|------|---------|
| `own_checks` | Own Check | Company-issued checks for vendor payment |
| `new_third_party_checks` | Inbound | Checks received from customers (asset) |
| `in_third_party_checks` | Move | Checks already in possession being deposited/transferred |
| `out_third_party_checks` | Outbound | Checks delivered to vendors |
| `return_third_party_checks` | Return | Checks returned by bank or vendor |

## Architecture

### Models

```
l10n_latam.check          # Main check tracking model
    └─ account.payment    # Payments linked to checks

account.move.line         # Journal items linked to checks (outstanding_line_id)
```

### Check State Lifecycle

```
handed (own checks) ──► debited ──► voided
         │
         └── (third party) ──► deposited ──► rejected ──► re-deposited
                          └─► transferred ──► out
```

## Models

### `l10n_latam.check`

Main model for LATAM check management. Stores check metadata and tracks operations.

**Inherited from:** `mail.thread`, `mail.activity.mixin`

| Field | Type | Description |
|-------|------|-------------|
| `payment_id` | Many2one | Original payment that created this check (required, ondelete cascade) |
| `operation_ids` | Many2many | All payment operations performed with this check |
| `current_journal_id` | Many2one | Journal where the check currently resides (computed) |
| `name` | Char | Check number (8-digit zero-padded) |
| `bank_id` | Many2one | Bank of the check issuer (computed for new third-party checks) |
| `issuer_vat` | Char | Tax ID of the check issuer (computed from partner) |
| `payment_date` | Date | Post-dated payment date (for deferred checks) |
| `amount` | Monetary | Check amount |
| `outstanding_line_id` | Many2one | The journal item this check is attached to as outstanding |
| `issue_state` | Selection | Current state: `handed`, `debited`, `voided` (computed) |
| `payment_method_code` | Char | Related from `payment_id.payment_method_code` |
| `partner_id` | Many2one | Check issuer/receiver partner |
| `original_journal_id` | Many2one | Journal where the check was originally received |
| `company_id` | Many2one | Company from payment |
| `currency_id` | Many2one | Currency from payment |
| `payment_method_line_id` | Many2one | Payment method configuration |

#### Computed Fields

**`_compute_issue_state`** — Determines check state based on outstanding line:
```python
@api.depends('outstanding_line_id.amount_residual')
def _compute_issue_state(self):
    for rec in self:
        if not rec.outstanding_line_id:
            rec.issue_state = False
        elif rec.amount and not rec.outstanding_line_id.amount_residual:
            if any(line.account_id.account_type in ['liability_payable', 'asset_receivable']
                   for line in rec.outstanding_line_id.matched_debit_ids.debit_move_id.move_id.line_ids):
                rec.issue_state = 'voided'
            else:
                rec.issue_state = 'debited'
        else:
            rec.issue_state = 'handed'
```

**`_compute_current_journal`** — Tracks which journal holds the check:
```python
def _get_last_operation(self):
    self.ensure_one()
    return (self.payment_id + self.operation_ids).filtered(
            lambda x: x.state not in ['draft', 'canceled']).sorted(
            key=lambda payment: (payment.date, payment.write_date, payment._origin.id))[-1:]

@api.depends('payment_id.state', 'operation_ids.state')
def _compute_current_journal(self):
    for rec in self:
        last_operation = rec._get_last_operation()
        if not last_operation:
            rec.current_journal_id = False
            continue
        if last_operation.payment_type == 'inbound':
            rec.current_journal_id = last_operation.journal_id
        else:
            rec.current_journal_id = False
```

**`_compute_bank_id`** — Auto-fills bank from partner's bank account (new third-party checks only):
```python
@api.depends('payment_method_line_id.code', 'payment_id.partner_id')
def _compute_bank_id(self):
    new_third_party_checks = self.filtered(
        lambda x: x.payment_method_line_id.code == 'new_third_party_checks')
    for rec in new_third_party_checks:
        rec.bank_id = rec.partner_id.bank_ids[:1].bank_id
    (self - new_third_party_checks).bank_id = False
```

**`_compute_issuer_vat`** — Auto-fills VAT from partner:
```python
@api.depends('payment_method_line_id.code', 'payment_id.partner_id')
def _compute_issuer_vat(self):
    new_third_party_checks = self.filtered(
        lambda x: x.payment_method_line_id.code == 'new_third_party_checks')
    for rec in new_third_party_checks:
        rec.issuer_vat = rec.payment_id.partner_id.vat
    (self - new_third_party_checks).issuer_vat = False
```

#### Key Methods

**`_prepare_void_move_vals`** — Prepares journal entry to void a check:
```python
def _prepare_void_move_vals(self):
    return {
        'ref': 'Void check',
        'journal_id': self.outstanding_line_id.move_id.journal_id.id,
        'line_ids': [
            Command.create({
                'name': "Void check %s" % self.outstanding_line_id.name,
                'date_maturity': self.outstanding_line_id.date_maturity,
                'amount_currency': self.outstanding_line_id.amount_currency,
                'currency_id': self.outstanding_line_id.currency_id.id,
                'debit': self.outstanding_line_id.debit,
                'credit': self.outstanding_line_id.credit,
                'partner_id': self.outstanding_line_id.partner_id.id,
                'account_id': self.payment_id.destination_account_id.id,
            }),
            Command.create({
                'name': "Void check %s" % self.outstanding_line_id.name,
                'date_maturity': self.outstanding_line_id.date_maturity,
                'amount_currency': -self.outstanding_line_id.amount_currency,
                'currency_id': self.outstanding_line_id.currency_id.id,
                'debit': -self.outstanding_line_id.debit,
                'credit': -self.outstanding_line_id.credit,
                'partner_id': self.outstanding_line_id.partner_id.id,
                'account_id': self.outstanding_line_id.account_id.id,
            }),
        ],
    }
```

**`action_void`** — Executes the void by creating and posting the reversal entry:
```python
def action_void(self):
    for rec in self.filtered('outstanding_line_id'):
        void_move = rec.env['account.move'].create(rec._prepare_void_move_vals())
        void_move.action_post()
        (void_move.line_ids[1] + rec.outstanding_line_id).reconcile()
```

#### Constraints

**`_constrains_min_amount`** — Ensures check amount is positive:
```python
@api.constrains('amount')
def _constrains_min_amount(self):
    min_amount_error = self.filtered(lambda x: x.amount <= 0)
    if min_amount_error:
        raise ValidationError(_('The amount of the check must be greater than 0'))
```

**`_check_issuer_vat`** — Validates issuer VAT using partner VAT check utility:
```python
@api.constrains('issuer_vat')
def _check_issuer_vat(self):
    for rec in self.filtered(lambda x: x.issuer_vat and x.company_id.country_id):
        self.env['res.partner']._run_vat_checks(rec.company_id.country_id, rec.issuer_vat, partner_name='Check Issuer VAT')
```

#### Delete Protection

```python
@api.ondelete(at_uninstall=False)
def _unlink_if_payment_is_draft(self):
    if any(check.payment_id.state != 'draft' for check in self):
        raise UserError(self.env._("Can't delete a check if payment is In Process!"))
```

#### Unique Constraint

```python
_unique = models.UniqueIndex("(name, payment_method_line_id) WHERE outstanding_line_id IS NOT NULL")
```

Ensures no duplicate check numbers for the same payment method when the check is outstanding.

---

### `account.payment` (inherited)

Extends `account.payment` to integrate check management.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `l10n_latam_new_check_ids` | One2many | New checks created with this payment (`l10n_latam.check`) |
| `l10n_latam_move_check_ids` | Many2many | Existing checks being moved/operated by this payment |
| `l10n_latam_check_warning_msg` | Text | Computed warning messages for check operations |

#### Key Methods

**`_is_latam_check_payment`** — Identifies if payment uses check methods:
```python
def _is_latum_check_payment(self, check_subtype=False):
    if check_subtype == 'move_check':
        codes = ['in_third_party_checks', 'out_third_party_checks', 'return_third_party_checks']
    elif check_subtype == 'new_check':
        codes = ['new_third_party_checks', 'own_checks']
    else:
        codes = ['in_third_party_checks', 'out_third_party_checks',
                 'return_third_party_checks', 'new_third_party_checks', 'own_checks']
    return self.payment_method_code in codes
```

**`_get_latam_checks`** — Returns associated checks:
```python
def _get_latam_checks(self):
    self.ensure_one()
    if self._is_latam_check_payment(check_subtype='new_check'):
        return self.l10n_latam_new_check_ids
    elif self._is_latam_check_payment(check_subtype='move_check'):
        return self.l10n_latam_move_check_ids
    else:
        return self.env['l10n_latam.check']
```

**`_get_blocking_l10n_latam_warning_msg`** — Validates check operations and returns blocking messages for:
- Currency mismatch between payment and checks
- Amount mismatch between payment and check total
- Draft checks being moved (must be posted first)
- Outbound checks not in current journal
- Inbound checks already in hand
- Date ordering violations (move date before last operation date)

**`_l10n_latam_check_split_move`** — For own checks, splits the payment journal entry into one line per check when multiple checks are issued:
```python
def _l10n_latam_check_split_move(self):
    for payment in self.filtered(lambda x: x.payment_method_code == 'own_checks'
                                  and x.payment_type == 'outbound'):
        if len(payment.l10n_latam_new_check_ids) == 1:
            liquidity_line = payment._seek_for_lines()[0]
            payment.l10n_latam_new_check_ids.outstanding_line_id = liquidity_line.id
            continue
        # ... creates one move line per check
```

**`_compute_destination_account_id`** — For check transfers between journals, uses company transfer account:
```python
@api.depends('l10n_latam_move_check_ids')
def _compute_destination_account_id(self):
    super()._compute_destination_account_id()
    for payment in self:
        if payment.l10n_latam_move_check_ids and (not payment.partner_id
           or payment.partner_id == payment.company_id.partner_id):
            payment.destination_account_id = payment.company_id.transfer_account_id.id
```

**`_is_latam_check_transfer`** — Detects check journal transfers:
```python
def _is_latam_check_transfer(self):
    self.ensure_one()
    return not self.partner_id and self.destination_account_id == self.company_id.transfer_account_id
```

## Business Flows

### Own Check Payment Flow

1. User creates outbound payment with `own_checks` method
2. Payment creates journal entry with check info on liquidity line
3. `l10n_latam.check` record created via `l10n_latam_new_check_ids`
4. Outstanding line linked to check
5. When check is debited by bank → state becomes `debited`
6. Optionally, user can void the check before debit → state becomes `voided`

### Third Party Check Inbound Flow

1. Customer pays with check → inbound payment with `new_third_party_checks`
2. Check record created with bank/VAT auto-filled from partner
3. Check is in `handed` state (asset on balance sheet)
4. User deposits check → `in_third_party_checks` payment
5. User receives bank confirmation → state becomes `debited`
6. If rejected → check returns to company, can be re-deposited

### Third Party Check Outbound Flow

1. User has a received check (state `handed`)
2. Creates outbound payment with `out_third_party_checks` to pay vendor
3. Check moves to vendor
4. If vendor rejects → `return_third_party_checks` payment returns check

## Technical Notes

- Check numbers are zero-padded to 8 digits (`_onchange_name` → `name.zfill(8)`)
- VAT numbers are compacted using `stdnum` library per country format
- Date ordering violations produce warnings (not blocking) during check operations
- Cancel/draft actions on payments are blocked if any associated check is `debited` or `voided`
- Journal entry split for own checks uses proportional amounts based on check amount ratio

## Related

- [Modules/Account](Modules/Account.md) - Core accounting
- [Modules/l10n_latam_invoice_document](Modules/l10n_latam_invoice_document.md) - LATAM document types
