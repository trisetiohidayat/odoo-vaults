---
type: module
name: account
version: Odoo 18
models_count: ~30
documentation_date: 2026-04-11
tags: [account, accounting, invoice, journal, payment, tax]
---

# Account

Core accounting module — journal entries, invoices, payments, taxes, fiscal positions, and chart of accounts.

## Models

### account.move

Journal entry / Invoice / Vendor Bill. `move_type` distinguishes the kind.

**move_type values:**
- `entry` — General journal entry
- `invoice` — Customer invoice (out_invoice, out_refund)
- `receipt` — Customer receipt / payment
- `out_invoice`, `out_refund`, `in_invoice`, `in_refund`

**Key Fields:**
- `name` — Entry reference (auto from journal sequence, or `/` for draft)
- `move_type` — Entry classification
- `date` — Accounting date
- `journal_id` (`account.journal`) — Journal
- `line_ids` (`account.move.line`, one2many) — Journal items
- `state` — `draft`, `posted`, `cancel`
- `amount_total`, `amount_untaxed`, `amount_tax` — Totals
- `currency_id` (`res.currency`)
- `invoice_date`, `invoice_date_due` — For invoices
- `invoice_payment_term_id` (`account.payment.term`) — Due date terms
- `invoice_partner_display_name` — Computed from partner
- `commercial_partner_id` (`res.partner`) — Company-level partner (for multi-company)
- `fiscal_position_id` (`account.fiscal.position`) — Auto-detected from partner
- `invoice_source_email` — Email from which invoice was created
- `is_storno` (`Boolean`) — Storno accounting (reversed debit/credit)
- `reversal_move_id` — Link to reversal entry

**L3 State Machine:**
- `draft` → `posted`: `_post()` validates and locks the entry
  1. Calls `_check_fiscal_year_lock_date()` — prevents posting in locked period
  2. Calls `_check_lock_date()` — checks period lock
  3. Calls `_check_balance_control()` — ensures debit = credit (within tolerance)
  4. Sets `state = 'posted'`, assigns `name` from sequence
- `posted` → `cancel`: `button_cancel()` — only if no reconciliation with posted payments
- Reversal: `reverse_moves()` — creates `account.move` with `reversal_move_id` link; sets `is_storno` based on company

**L3 Storno Accounting:**
When `is_storno=True` on company: debit/credit fields are swapped in display. `_check_balance_control()` computes `abs(debit - credit)` tolerance.

### account.move.line

**Key Fields:**
- `account_id` (`account.account`) — Target account
- `debit`, `credit`, `balance` — Amounts in company currency
- `amount_currency` — Amount in foreign currency
- `currency_id` (`res.currency`) — Foreign currency
- `partner_id` (`res.partner`)
- `analytic_distribution` (`Json`) — Analytic account distribution {account_id: percentage}
- `tax_line_id` (`account.tax`) — Tax account for tax lines
- `tax_ids` (`account.tax`, many2many) — Taxes applicable to this line
- `tax_tag_ids` (`account.account.tag`, many2many) — Tax grid tags
- `date_maturity` — Due date for payable/receivable
- `amount_residual` — Remaining unreconciled amount
- `full_reconcile_id` (`account.full.reconcile`) — Complete reconciliation
- `matched_debit_ids`, `matched_credit_ids` — Partial reconciliation records
- `is_storno` — Line is from storno entry

**L3 Constraints:**
- SQL constraint: `(debit * credit) = 0` — can't have both debit and credit on same line
- `company_id` must match parent `account.move`
- Cascading delete: delete line → unlink `matched_*` records → recompute residual on counterpart lines

### account.journal

**Key Fields:**
- `name`, `code` — Short code (e.g., "SUPP", "CUST")
- `type` — `sale`, `purchase`, `cash`, `bank`, `general`
- `default_account_id` (`account.account`) — Default debit/credit account
- `currency_id` (`res.currency`) — Currency (for bank/cash journals)
- `loss_account_id`, `profit_account_id` — For exchange difference
- `invoice_reference_model` — How invoice references are generated
- `show_on_dashboard` — Show on accounting dashboard
- `sequence_override_regex` — Custom sequence pattern

### account.payment

**Key Fields:**
- `payment_type` — `inbound`, `outbound`
- `partner_type` — `customer`, `vendor`
- `partner_id` (`res.partner`)
- `amount`, `currency_id`
- `journal_id` (`account.journal`)
- `date`, `date_deadline` — Payment date and due date
- `ref` — Reference
- `move_id` (`account.move`) — One2one to the move created
- `payment_method_id` (`account.payment.method`)
- `payment_transaction_id` (`payment.transaction`) — Link to online payment
- `state` — `draft`, `posted`, `cancelled`

**L3 Workflow:**
- `_post()` — Creates `account.move` with two lines:
  1. Liquidity line: `account_id = journal.default_account_id`
  2. Counterpart line: `account_id = partner's receivable/payable account`
- Reconciles with invoice: `line_id.reconcile()` matches payment against invoice lines
- Online payments: `payment.transaction._create_payment_entries()` creates the move

### account.tax

**Key Fields:**
- `name`, `type_tax_use` — `sale`, `purchase`, `none`
- `tax_scope` — `None`, `ancestry` (for product-type taxes)
- `amount_type` — `group`, `percent`, `fixed`, `division`, `taxes`
- `amount` — Rate (e.g., 10.0 for 10%)
- `include_base_amount` — Tax is included in base for compound taxes
- `is_base_affected` — Base amount affected by other taxes
- `children_tax_ids` — Sub-taxes (for tax groups)
- `invoice_repartition_line_ids`, `refund_repartition_line_ids` — Distribution to accounts
- `tax_exigibility` — `on_invoice` or `on_payment`
- `cash_basis_transition_account_id` — Account for CABA

**L3 Tax Groups (`amount_type='group'`):**
- `children_tax_ids` are applied sequentially
- `include_base_amount`: child's base = parent's base + parent's tax
- Compound: one tax's `tax_ids` includes another tax

**L3 Cash Basis Tax (`tax_exigibility='on_payment'`):**
- When invoice posted: creates temporary lines on `cash_basis_transition_account_id`
- When payment received: moves tax amounts to actual tax accounts
- `account.tax.repartition.line` controls which accounts receive the cash basis tax

### account.fiscal.position

**Key Fields:**
- `name`, `auto_apply`, `vat_required`
- `company_id`
- `account_ids` (`account.fiscal.position.account`) — Map source account → destination account
- `tax_ids` (`account.fiscal.position.tax`) — Map source tax → destination tax

**L3:** `auto_apply` triggers via `_get_fiscal_position()` when:
- Partner's `country_id` matches, or
- Partner's `state_id` matches (more specific)
- `vat_required` adds VAT number check

### account.payment.term

**Key Fields:**
- `name`, `note` — Terms description
- `early_payment_discount_mode` — Apply EPD even when paying after due date
- `compute_method` — `percentages` (default) or `fixed`
- `early_discount` — Enable early payment discount
- `line_ids` (`account.payment.term.line`) — Installment lines

### account.payment.term.line

**Key Fields:**
- `value` — `percent` or `fixed`
- `amount` — Percentage or fixed amount
- `delay_type` — `days_after` or `days_after_end_of_month`
- `days` — Number of days
- `end_month` — If true, count from end of invoice month

### account.partial.reconcile

Links partial payments to invoice lines. Tracks `debit_move_id`, `credit_move_id`, `amount`, `currency_id`, `exchange_date`, `exchange_move_id`.

### account.full.reconcile

Complete reconciliation. `partial_reconcile_ids`, `reconciled_line_ids`.

## Code

- Models: `~/odoo/odoo18/odoo/addons/account/models/`
