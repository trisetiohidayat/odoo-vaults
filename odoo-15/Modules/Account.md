# Modules/Account.md

# Account Module — Odoo 15

Dokumentasi Odoo 15 untuk Account module. Source: `addons/account/models/`

## Overview

**Module**: `account` (Invoicing)
**Manifest**: `addons/account/__manifest__.py`
**Version**: Odoo 15 (`'version': '1.2'`)
**Depends**: `base_setup`, `product`, `analytic`, `portal`, `digest`

The Account module provides invoicing, payment tracking, reconciliation, tax management, and financial reporting.

---

## Core Models

| Model | _name | Source File | Description |
|-------|-------|-------------|-------------|
| `AccountAccount` | `account.account` | `account_account.py` | Chart of accounts |
| `AccountAccountTag` | `account.account.tag` | `account_account_tag.py` | Account/tax tags |
| `AccountJournal` | `account.journal` | `account_journal.py` | Journals |
| `AccountMove` | `account.move` | `account_move.py` | Journal entries / invoices |
| `AccountMoveLine` | `account.move.line` | `account_move.py` | Journal items |
| `AccountTax` | `account.tax` | `account_tax.py` | Tax definitions |
| `AccountTaxRepartitionLine` | `account.tax.repartition.line` | `account_tax.py` | Tax distribution |
| `AccountTaxGroup` | `account.tax.group` | `account_tax.py` | Tax grouping |
| `AccountTaxReport` | `account.tax.report` | `account_tax_report.py` | Tax report structure |
| `AccountTaxReportLine` | `account.tax.report.line` | `account_tax_report.py` | Tax report lines |
| `AccountPayment` | `account.payment` | `account_payment.py` | Payments |
| `AccountPartialReconcile` | `account.partial.reconcile` | `account_partial_reconcile.py` | Partial reconciliation |
| `AccountFullReconcile` | `account.full.reconcile` | `account_full_reconcile.py` | Full reconciliation |
| `AccountReconcileModel` | `account.reconcile.model` | `account_reconcile_model.py` | Auto-reconciliation rules |
| `AccountAnalyticDefault` | `account.analytic.default` | `account_analytic_default.py` | Default analytic settings |
| `AccountAnalyticLine` | `account.analytic.line` | `account_analytic_line.py` | Analytic entries |
| `AccountCashRounding` | `account.cash.rounding` | `account_cash_rounding.py` | Cash rounding |
| `AccountIncoterms` | `account.incoterms` | `account_incoterms.py` | Incoterms |
| `AccountPaymentTerm` | `account.payment.term` | `account_payment_term.py` | Payment terms |
| `AccountReconcileModel` | `account.reconcile.model` | `account_reconcile_model.py` | Reconciliation templates |
| `AccountBankStatement` | `account.bank.statement` | `account_bank_statement.py` | Bank statements |
| `MailThread` | `account.mail.thread` | `mail_thread.py` | Chatter for account models |
| `res.currency` | `res.currency` | `res_currency.py` | Currency management |

---

## AccountMove (`account.move`)

Journal Entry / Invoice — model fundamental untuk semua transaksi akuntansi.

```python
class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'sequence.mixin']
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Entry number (from sequence, auto-computed) |
| `date` | Date | Entry date (required) |
| `ref` | Char | Reference |
| `state` | Selection | `draft` / `posted` / `cancel` |
| `move_type` | Selection | entry/invoice/refund/receipt |
| `journal_id` | Many2one `account.journal` | Journal |
| `line_ids` | One2many `account.move.line` | Journal items |
| `partner_id` | Many2one `res.partner` | Partner |
| `commercial_partner_id` | Many2one | Commercial entity (computed) |
| `amount_untaxed` | Monetary | Untaxed amount (computed) |
| `amount_tax` | Monetary | Tax amount (computed) |
| `amount_total` | Monetary | Total amount (computed) |
| `amount_residual` | Monetary | Outstanding amount (computed) |
| `currency_id` | Many2one `res.currency` | Currency |
| `payment_state` | Selection | Payment status |

### States

```
draft ──► posted ──► cancel
                  └──► reversed
```

### Move Types

| Type | Direction | Description |
|------|-----------|-------------|
| `entry` | General | Journal Entry |
| `out_invoice` | Customer | Customer Invoice |
| `out_refund` | Customer | Customer Credit Note |
| `in_invoice` | Vendor | Vendor Bill |
| `in_refund` | Vendor | Vendor Credit Note |
| `out_receipt` | Customer | Sales Receipt |
| `in_receipt` | Vendor | Purchase Receipt |

### Payment State Values

| State | Description |
|-------|-------------|
| `not_paid` | Not paid |
| `in_payment` | Payment in progress |
| `paid` | Fully paid |
| `partial` | Partially paid |
| `reversed` | Reversed |
| `invoicing_legacy` | Legacy invoicing |

---

## AccountMoveLine (`account.move.line`)

Journal Item — individual lines within a journal entry.

```python
class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _description = "Journal Item"
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `move_id` | Many2one `account.move` | Parent entry |
| `account_id` | Many2one `account.account` | Account |
| `partner_id` | Many2one `res.partner` | Partner |
| `name` | Char | Line label |
| `debit` | Monetary | Debit amount |
| `credit` | Monetary | Credit amount |
| `balance` | Monetary | Balance (computed: debit - credit) |
| `quantity` | Float | Quantity |
| `product_id` | Many2one `product.product` | Product |
| `product_uom_id` | Many2one `uom.uom` | Unit of measure |
| `analytic_account_id` | Many2one `account.analytic.account` | Analytic account |
| `analytic_tag_ids` | Many2many `account.analytic.tag` | Analytic tags |
| `tax_ids` | Many2many `account.tax` | Taxes on regular lines |
| `tax_line_id` | Many2one `account.tax` | Tax (for tax lines) |
| `tax_repartition_line_id` | Many2one `account.tax.repartition.line` | Tax distribution |
| `tax_tag_ids` | Many2many `account.account.tag` | Tax tags (from repartition) |
| `tax_base_amount` | Monetary | Base amount for tax |
| `currency_id` | Many2one `res.currency` | Currency |
| `amount_currency` | Monetary | Amount in foreign currency |
| `reconciled` | Boolean | Is reconciled (computed) |
| `full_reconcile_id` | Many2one `account.full.reconcile` | Full reconciliation |
| `matched_debit_ids` | One2many | Partial debit reconciliations |
| `matched_credit_ids` | One2many | Partial credit reconciliations |
| `amount_residual` | Monetary | Residual amount (computed) |
| `amount_residual_currency` | Monetary | Residual in foreign currency |
| `payment_id` | Many2one `account.payment` | Payment |
| `statement_line_id` | Many2one `account.bank.statement.line` | Bank statement line |

---

## Account (`account.account`)

Chart of Accounts.

```python
class AccountAccount(models.Model):
    _name = "account.account"
    _check_company_auto = True
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Account name |
| `code` | Char | Account code (unique per company) |
| `user_type_id` | Many2one `account.account.type` | Account type (required) |
| `internal_type` | Selection | Derived from `user_type_id.type` |
| `internal_group` | Selection | Derived from `user_type_id.internal_group` |
| `company_id` | Many2one `res.company` | Company (required) |
| `currency_id` | Many2one `res.currency` | Foreign currency |
| `reconcile` | Boolean | Allow reconciliation (default: False) |
| `deprecated` | Boolean | Deprecated flag |
| `tag_ids` | Many2many `account.account.tag` | Account tags |
| `tax_ids` | Many2many `account.tax` | Default taxes |
| `current_balance` | Float | Computed from posted move lines |
| `opening_debit` | Monetary | Opening debit |
| `opening_credit` | Monetary | Opening credit |
| `is_off_balance` | Boolean | Off-balance indicator |

### Account Types (from `account.account.type`)

| Type | Internal Group | Reconcile | Description |
|------|---------------|-----------|-------------|
| `receivable` | asset | **True** | Customer AR |
| `payable` | liability | **True** | Vendor AP |
| `credit_card` | asset | False | Credit card |
| `bank` | asset | False | Bank accounts |
| `cash` | asset | False | Cash accounts |
| `current` | asset | False | Current assets |
| `non_current` | asset | False | Non-current assets |
| `prepayments` | asset | False | Prepaid expenses |
| `fixed` | asset | False | Fixed assets |
| `off_balance` | — | False | Off-balance (contingency) |
| `equity_unaffected` | equity | False | Current year earnings |
| `equity` | equity | False | Equity |
| `income` | income | False | Revenue |
| `income_other` | income | False | Other income |
| `expense` | expense | False | Expenses |
| `expense_depreciated` | expense | False | Depreciated expenses |
| `cost_of_goods_sold` | expense | False | COGS |

### Business Rules

- `code` UNIQUE per company (SQL constraint)
- Receivable/payable accounts MUST have `reconcile=True`
- Only one "Current Year Earnings" account per company
- Off-balance accounts cannot be reconcilable or have taxes

---

## AccountJournal (`account.journal`)

Journals — containers for journal entries.

```python
class AccountJournal(models.Model):
    _name = "account.journal"
    _inherit = ['mail.thread', 'mail.activity.mixin']
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Journal name |
| `code` | Char(5) | Short code (unique per company) |
| `type` | Selection | sale/purchase/cash/bank/general |
| `company_id` | Many2one `res.company` | Company |
| `currency_id` | Many2one `res.currency` | Currency (for bank/cash) |
| `default_account_id` | Many2one | Default account |
| `suspense_account_id` | Many2one | Suspense account |
| `profit_account_id` | Many2one | Profit account (cash journals) |
| `loss_account_id` | Many2one | Loss account (cash journals) |
| `bank_account_id` | Many2one | Bank account |
| `bank_statements_source` | Selection | Bank feed source |
| `restrict_mode_hash_table` | Boolean | Hash lock for posted entries |
| `sequence` | Integer | Dashboard order |
| `inbound_payment_method_line_ids` | One2many | Inbound payment methods |
| `outbound_payment_method_line_ids` | One2many | Outbound payment methods |
| `alias_id` | Many2one `mail.alias` | Email alias for bills |

### Journal Types

| Type | Description |
|------|-------------|
| `sale` | Sales Journal (Customer Invoices) |
| `purchase` | Purchase Journal (Vendor Bills) |
| `cash` | Cash Journal |
| `bank` | Bank Journal |
| `general` | General Journal |

---

## AccountTax (`account.tax`)

Tax definitions.

```python
class AccountTax(models.Model):
    _name = 'account.tax'
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tax name (required) |
| `type_tax_use` | Selection | `sale` / `purchase` / `none` |
| `tax_scope` | Selection | `service` / `consu` (exemption) |
| `amount_type` | Selection | `group` / `fixed` / `percent` / `division` |
| `amount` | Float | Tax rate (digits 16,4) |
| `price_include` | Boolean | Included in unit price |
| `include_base_amount` | Boolean | Affects subsequent taxes |
| `is_base_affected` | Boolean | Affected by previous taxes |
| `company_id` | Many2one | Company |
| `children_tax_ids` | Many2many | Child taxes (for groups) |
| `sequence` | Integer | Application order |
| `tax_group_id` | Many2one | Tax group |
| `tax_exigibility` | Selection | `on_invoice` / `on_payment` (CABA) |
| `cash_basis_transition_account_id` | Many2one | CABA transition account |
| `invoice_repartition_line_ids` | One2many | Invoice distribution |
| `refund_repartition_line_ids` | One2many | Refund distribution |
| `country_id` | Many2one | Country |
| `analytic` | Boolean | Force analytic account |

### Amount Type Formulas

| Type | Formula |
|------|---------|
| `percent` | `base * amount / 100` |
| `fixed` | `amount * quantity` |
| `division` | `base / (1 - amount/100) - base` |
| `group` | Sum of children taxes |

### Tax Eligibility

| Mode | Description |
|------|-------------|
| `on_invoice` (default) | Tax recognized when invoice is posted |
| `on_payment` (CABA) | Tax recognized when payment is received |

### Key Methods

- `_compute_amount()` — compute single tax
- `compute_all()` — compute all taxes including children
- `flatten_taxes_hierarchy()` — flatten group taxes
- `get_tax_tags()` — get tax tags for refund/invoice
- `name_get()` — returns `"Name (type/scope)"` format

---

## AccountTaxRepartitionLine (`account.tax.repartition.line`)

Distribution of tax amounts to accounts.

```python
class AccountTaxRepartitionLine(models.Model):
    _name = 'account.tax.repartition.line'
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `tax_id` | Many2one `account.tax` | Parent tax |
| `invoice_type` | Selection | `invoice` / `refund` (via `tax_id`) |
| `factor_percent` | Float | Percentage (default: 100) |
| `account_id` | Many2one `account.account` | Account to post tax |
| `tag_ids` | Many2many `account.account.tag` | Tax tags for tax report |

**Important**: Tax amount is split proportionally by `factor_percent` across multiple repartition lines.

---

## AccountAccountTag (`account.account.tag`)

Tags for accounts and taxes — fundamental for **Tax Grid**.

```python
class AccountAccountTag(models.Model):
    _name = 'account.account.tag'
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name (required) |
| `applicability` | Selection | `accounts` / `taxes` / `products` |
| `color` | Integer | Color index |
| `active` | Boolean | Active flag |
| `tax_report_line_ids` | Many2many | Tax report lines using this tag |
| `tax_negate` | Boolean | Negate tax balance |
| `country_id` | Many2one | Country |

### Applicability Values

| Value | Usage |
|-------|-------|
| `accounts` | Tags for financial reports |
| `taxes` | **Tax Grid tags** — link tax to tax report |
| `products` | Tags for product categorization |

### Tax Tag Naming

Tax tags untuk tax grid menggunakan prefix `+` atau `-`:
- `+tax_name` — positive balance (tax payable)
- `-tax_name` — negative balance (tax receivable/credit)

---

## Tax Grid System

### Overview

Tax Grid adalah sistem tagging di Odoo yang menghubungkan **tax amounts** dari invoice ke **baris-baris di Tax Report**. Ini adalah mekanisme utama untuk reporting pajak yang akurat.

### Arsitektur

```
account.tax.report
    │
    └── account.tax.report.line
            │
            ├── name = "PPN Keluaran 11%"
            ├── tag_name = "tax_11_output"
            │       │
            │       └── Creates: +tax_11_output AND -tax_11_output
            │
            └── account.account.tag (applicability='taxes')
                    │
                    └── account.move.line.tax_tag_ids
                            │
                            └── Tax Report reads all lines with these tags
                                    └─► SUM(+)tag - SUM(-)tag = balance
```

### Alur Kerja

1. **Invoice Posted** → tax lines created dengan `tax_tag_ids`
2. **Tax report** reads all move lines dengan tag tertentu
3. `+tag` di-sum, `-tag` di-subtract → net balance per report line

### Tag Creation

Ketika `account.tax.report.line.tag_name` di-set, Odoo otomatis membuat:

```python
# Membuat:
minus_tag = {
    'name': '-' + tag_name,        # e.g., '-tax_11_output'
    'applicability': 'taxes',
    'tax_negate': True,
    'country_id': report.country_id,
}
plus_tag = {
    'name': '+' + tag_name,        # e.g., '+tax_11_output'
    'applicability': 'taxes',
    'tax_negate': False,
    'country_id': report.country_id,
}
```

### Repartition Lines & Tags

Setiap tax punya `invoice_repartition_line_ids` dan `refund_repartition_line_ids`:

```
account.tax: PPN 11%

invoice_repartition_line_ids:
┌────┬──────────┬──────────────┬─────────────────────┐
│ #  │ Type    │ Factor      │ Tag                 │
├────┼──────────┼──────────────┼─────────────────────┤
│ 1  │ Base    │ 100%        │ +tax_11_output     │
│ 2  │ Tax     │ 100%        │ +tax_11_output     │
└────┴──────────┴──────────────┴─────────────────────┘

refund_repartition_line_ids:
┌────┬──────────┬──────────────┬─────────────────────┐
│ #  │ Type    │ Factor      │ Tag                 │
├────┼──────────┼──────────────┼─────────────────────┤
│ 1  │ Base    │ 100%        │ -tax_11_output     │
│ 2  │ Tax     │ 100%        │ -tax_11_output     │
└────┴──────────┴──────────────┴─────────────────────┘
```

---

## Tax Report Models

### AccountTaxReport (`account.tax.report`)

Tax report definition.

```python
class AccountTaxReport(models.Model):
    _name = "account.tax.report"
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Report name |
| `country_id` | Many2one | Country (required) |
| `line_ids` | One2many | Report lines |

### AccountTaxReportLine (`account.tax.report.line`)

Lines in a tax report.

```python
class AccountTaxReportLine(models.Model):
    _name = "account.tax.report.line"
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Line name |
| `tag_ids` | Many2many | Tax tags populating this line |
| `tag_name` | Char | Tag name (creates +/- tags) |
| `report_id` | Many2one | Parent report |
| `parent_id` | Many2one | Parent line |
| `children_line_ids` | One2many | Child lines |
| `sequence` | Integer | Display order |
| `code` | Char | Unique code for formula reference |
| `formula` | Char | Python expression (total lines only) |
| `carry_over_condition_method` | Selection | Carryover condition |
| `carry_over_destination_line_id` | Many2one | Carryover target |
| `is_carryover_persistent` | Boolean | Persistent carryover |
| `is_carryover_used_in_balance` | Boolean | Used in balance |

### Formula Lines

Lines dengan `formula` adalah **total lines** yang menghitung dari line codes lain:

```python
# Line: "NET PPN"
formula = "tax_11_output - tax_11_input"
# Tidak punya tag_name, hanya formula
```

### Carryover Conditions

| Method | Description |
|--------|-------------|
| `no_negative_amount_carry_over_condition` | Negatives carried over |
| `always_carry_over_and_set_to_0` | Always carry, reset to 0 |

---

## Cash Basis Accounting (CABA)

Untuk taxes dengan `tax_exigibility='on_payment'`.

### Models Involved

- `account.tax` — `cash_basis_transition_account_id`
- `account.partial.reconcile` — creates CABA entries
- `account.move` — `tax_cash_basis_rec_id`

### Flow

```
Invoice Posted (on_payment tax)
    │
    └─► Tax line created with tag
        amount_residual = tax_amount (not paid)

Payment Registered
    │
    └─► account.partial.reconcile created
        └─► _create_tax_cash_basis_moves()
            └─► CABA Journal Entry:
                ├─► Base line: tax base amount
                ├─► Tax line: tax amount
                └─► Counterpart: transition account
```

---

## AccountPayment (`account.payment`)

Payments — inherits from `account.move` via `_inherits`.

```python
class AccountPayment(models.Model):
    _name = "account.payment"
    _inherits = {'account.move': 'move_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `payment_type` | Selection | `inbound` / `outbound` |
| `partner_type` | Selection | `customer` / `supplier` |
| `amount` | Monetary | Payment amount |
| `partner_id` | Many2one | Customer/Supplier |
| `destination_account_id` | Many2one | Computed destination (AR/AP) |
| `outstanding_account_id` | Many2one | Computed outstanding (bank/cash) |
| `payment_method_line_id` | Many2one | Payment method |
| `is_internal_transfer` | Boolean | Internal transfer flag |
| `paired_internal_transfer_payment_id` | Many2one | Paired transfer payment |
| `is_reconciled` | Boolean | Fully reconciled |
| `is_matched` | Boolean | Matched with bank statement |
| `qr_code` | Char | Payment QR code (computed) |

### Journal Entry Structure

```
Payment Journal Entry:
┌─────────────────────────────────┬───────┬─────────┐
│ Account                        │ Debit │ Credit  │
├────────────────────────────────┼───────┼─────────┤
│ Bank/Cash (outstanding)        │ XXX   │         │ ← Liquidity
│ Receivable/Payable             │       │ XXX    │ ← Counterpart
│ Write-off (if any)             │       │ XXX    │ ← Optional
└────────────────────────────────┴───────┴─────────┘
```

---

## Reconciliation

### AccountPartialReconcile (`account.partial.reconcile`)

Partial match between journal lines.

```python
class AccountPartialReconcile(models.Model):
    _name = "account.partial.reconcile"
```

| Field | Type | Description |
|-------|------|-------------|
| `debit_move_id` | Many2one | Debit journal item |
| `credit_move_id` | Many2one | Credit journal item |
| `full_reconcile_id` | Many2one | Parent full reconciliation |
| `amount` | Monetary | Matched amount (company currency) |
| `debit_amount_currency` | Monetary | Debit (foreign currency) |
| `credit_amount_currency` | Monetary | Credit (foreign currency) |
| `max_date` | Date | Max date of matched lines |

### AccountFullReconcile (`account.full.reconcile`)

Full reconciliation — complete match.

```python
class AccountFullReconcile(models.Model):
    _name = "account.full.reconcile"
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Number (sequence) |
| `partial_reconcile_ids` | One2many | All partial reconciliations |
| `reconciled_line_ids` | One2many | All reconciled items |
| `exchange_move_id` | Many2one | Exchange rate entry |

### Amount Residual Calculation

```python
# account.move.line
amount_residual = debit - credit - sum(partial_reconcile.amount)
```

---

## AccountReconcileModel (`account.reconcile.model`)

Auto-reconciliation rules.

```python
class AccountReconcileModel(models.Model):
    _name = 'account.reconcile.model'
    _inherit = ['mail.thread']
```

### Rule Types

| Type | Description |
|------|-------------|
| `invoice_matching` | Match open invoices/bills |
| `writeoff_suggestion` | Suggest write-off account |
| `writeoff_button` | Manual write-off on demand |

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Model name |
| `rule_type` | Selection | Matching type |
| `auto_reconcile` | Boolean | Auto-validate |
| `match_nature` | Selection | `amount_received` / `amount_paid` / `both` |
| `match_same_currency` | Boolean | Same currency required |
| `allow_payment_tolerance` | Boolean | Payment tolerance |
| `payment_tolerance_param` | Float | Tolerance gap |
| `match_partner` | Boolean | Partner required |
| `line_ids` | One2many | Reconciliation lines |
| `partner_mapping_line_ids` | One2many | Regex partner mappings |

---

## Workflow

```
1. Create Invoice/Bill (draft)
       │
       └─► action_post()
               │
               ▼
2. Posted Invoice (creates journal entry)
       │
       └─► action_register_payment()
               │
               ▼
3. Register Payment
       │
       └─► action_post() on payment
               │
               ▼
4. Reconciliation (partial/full)
       │
       ▼
5. Fully Reconciled
```

---

## Post an Invoice

```python
def action_post(self):
    """Post invoice (draft → posted)"""
    self._post(soft=True)
    return True
```

Posting invoice:
- Validates constraints
- Recomputes tax lines
- Creates analytic lines
- Assigns sequence number
- Changes state to `posted`

---

## Create Payment

```python
def action_register_payment(self):
    """Open payment registration wizard"""
    return {
        'name': _('Register Payment'),
        'type': 'ir.actions.act_window',
        'res_model': 'account.payment.register',
        'view_mode': 'form',
        'target': 'new',
        'context': {
            'active_model': 'account.move',
            'active_ids': self.ids,
        },
    }
```

---

## Related Modules

- [Modules/Sale](Sale.md) — Customer Invoice from SO
- [Modules/Purchase](Purchase.md) — Vendor Bill from PO
- [Modules/Stock](Stock.md) — Stock valuation entries

## Related Flows

- [Flows/Account/invoice-creation-flow](invoice-creation-flow.md) — Invoice creation
- [Flows/Account/invoice-post-flow](invoice-post-flow.md) — Invoice posting
- [Flows/Account/payment-flow](payment-flow.md) — Payment registration
- [Flows/Cross-Module/sale-stock-account-flow](sale-stock-account-flow.md) — Sales → Delivery → Invoice → Payment
- [Business/Account/tax-grid-guide](tax-grid-guide.md) — Tax Grid guide
