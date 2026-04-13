---
type: module
module: account
tags: [odoo, odoo19, account, invoice, payment, journal, reconciliation]
updated: 2026-04-11
version: "3.0"
---

## Quick Access

### Flows (Technical)
- [Flows/Account/invoice-creation-flow](odoo-19/Flows/Account/invoice-creation-flow.md) - Draft invoice creation
- [Flows/Account/invoice-post-flow](odoo-19/Flows/Account/invoice-post-flow.md) - Post invoice (draft to posted)
- [Flows/Account/payment-flow](odoo-19/Flows/Account/payment-flow.md) - Register payment and reconciliation
- [Flows/Cross-Module/sale-stock-account-flow](odoo-19/Flows/Cross-Module/sale-stock-account-flow.md) - Sale to Stock to Invoice
- [Flows/Cross-Module/purchase-stock-account-flow](odoo-19/Flows/Cross-Module/purchase-stock-account-flow.md) - PO to Receipt to Bill

### Related Modules
- [Modules/Sale](odoo-18/Modules/sale.md) - Customer invoice source
- [Modules/Purchase](odoo-18/Modules/purchase.md) - Vendor bill source
- [Modules/Stock](odoo-18/Modules/stock.md) - Inventory valuation
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) - State machine pattern

---

## Module Overview

| Property | Value |
|----------|-------|
| **Name** | Invoicing |
| **Technical Name** | account |
| **Version** | 19.0 |
| **Category** | Accounting/Accounting |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Application** | Yes |

## Dependencies

```
base ─┬─ base_setup ─── Base Setup
       ├─ onboarding ─── Onboarding wizard
       ├─ product ────── Product management
       ├─ analytic ───── Analytic Accounting
       ├─ portal ─────── Portal access
       └─ digest ─────── KPI email digests
```

**Odoo 18→19 changes:** `base_setup` was split from `base`; `onboarding` and `product.catalog.mixin` were added as direct dependencies. The `account` module no longer depends directly on `mail` — threading uses `mail.thread.main.attachment` mixin.

---

## Key Models

### 1. account.move (Journal Entry)

**File:** `odoo/addons/account/models/account_move.py`

Central model for all accounting entries: invoices, bills, journal entries, credit/debit notes, receipts.

```python
class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = [
        'portal.mixin',
        'mail.thread.main.attachment',
        'mail.activity.mixin',
        'sequence.mixin',
        'product.catalog.mixin',
        'account.document.import.mixin',
    ]
    _description = "Journal Entry"
    _order = 'date desc, name desc, invoice_date desc, id desc'
    _mail_post_access = 'read'
    _check_company_auto = True
    _sequence_index = "journal_id"
    _rec_names_search = ['name', 'partner_id.name', 'ref']
    _mailing_enabled = True
```

#### Core Fields (L1/L2)

| Field | Type | Index | Default | Stored | Description |
|-------|------|-------|---------|--------|-------------|
| `name` | Char | trigram | computed | yes | Number (sequence-based, `/` for draft) |
| `name_placeholder` | Char | - | computed | - | Preview of next sequence number |
| `ref` | Char | trigram | - | - | External reference (vendor bill number) |
| `date` | Date | btree | today | yes | Accounting date |
| `state` | Selection | - | `draft` | yes | `draft` / `posted` / `cancel` |
| `move_type` | Selection | btree | `entry` | yes | Document type (immutable after create) |
| `journal_id` | Many2one | btree | auto | yes | Journal (auto-selected by type) |
| `company_id` | Many2one | btree | current | yes | Company |
| `line_ids` | One2many | - | - | - | Journal items (account.move.line) |
| `partner_id` | Many2one | btree | - | yes | Customer or vendor |
| `currency_id` | Many2one | - | company | yes | Document currency |
| `company_currency_id` | Many2one | - | computed | - | Company's default currency |
| `fiscal_position_id` | Many2one | - | auto | yes | Fiscal position (country-based) |
| `invoice_payment_term_id` | Many2one | - | partner | yes | Payment terms |
| `invoice_date` | Date | btree | - | yes | Invoice/bill date |
| `invoice_date_due` | Date | btree | computed | yes | Due date |
| `delivery_date` | Date | btree | - | yes | Delivery date (sale orders) |
| `taxable_supply_date` | Date | - | - | yes | VAT supply date |
| `auto_post` | Selection | - | `no` | yes | `no` / `at_date` / `monthly` / `quarterly` / `yearly` |
| `auto_post_until` | Date | - | - | yes | Recurring end date |
| `auto_post_origin_id` | Many2one | btree_not_null | - | yes | First recurring entry reference |
| `payment_reference` | Char | trigram | - | yes | Payment reference / reconciliation key |
| `is_storno` | Boolean | - | computed | yes | Storno accounting (company flag) |
| `reversed_entry_id` | Many2one | btree_not_null | - | yes | Entry this is reversing |
| `narration` | Html | - | company | yes | Terms and conditions |
| `invoice_user_id` | Many2one | - | partner/commercial | yes | Salesperson |
| `invoice_origin` | Char | - | - | yes | Source document (SO, PO name) |
| `invoice_incoterm_id` | Many2one | - | - | yes | Incoterms |
| `invoice_cash_rounding_id` | Many2one | - | - | yes | Cash rounding method |
| `quick_edit_mode` | Boolean | - | company | - | Fiduciary mode (quick invoice entry) |
| `quick_edit_total_amount` | Monetary | - | - | - | Total used in fiduciary mode |
| `restrict_mode_hash_table` | Boolean | related | journal | - | Hash immutability enabled |
| `secure_sequence_number` | Integer | btree | - | yes | Inalterability sequence # |
| `inalterable_hash` | Char | btree_not_null | - | yes | Hash for audit trail |
| `checked` | Boolean | btree (partial) | - | yes | Reviewed flag (dashboards) |
| `posted_before` | Boolean | - | - | yes | Has been posted before |
| `is_move_sent` | Boolean | - | - | yes | PDF generated / sent |
| `is_being_sent` | Boolean | - | computed | - | Async sending in progress |
| `no_followup` | Boolean | - | - | yes | Exclude from follow-up reports |
| `invoice_pdf_report_id` | Many2one | - | computed | - | Cached PDF attachment |
| `sending_data` | Json | - | - | yes | Async send metadata |

#### Monetary Fields (computed, stored)

| Field | Currency | Description |
|-------|----------|-------------|
| `amount_untaxed` | `currency_id` | Sum of product line subtotals |
| `amount_tax` | `currency_id` | Sum of tax lines |
| `amount_total` | `currency_id` | `amount_untaxed + amount_tax` |
| `amount_residual` | `currency_id` | Remaining due (after reconciliation) |
| `amount_untaxed_signed` | `company_currency_id` | Signed untaxed (credit notes negate) |
| `amount_tax_signed` | `company_currency_id` | Signed tax |
| `amount_total_signed` | `company_currency_id` | Signed total (negative for AP/AR) |
| `amount_residual_signed` | `company_currency_id` | Signed residual |
| `amount_total_in_currency_signed` | `currency_id` | Signed total in document currency |
| `amount_untaxed_in_currency_signed` | `currency_id` | Signed untaxed in document currency |
| `direction_sign` | Integer | `+1` for outbound/entry, `-1` for inbound |

#### Payment State

| `payment_state` Value | Trigger Condition |
|-----------------------|-------------------|
| `not_paid` | Default for posted invoices with open residual |
| `in_payment` | Some payments matched, all in `in_process` state |
| `paid` | `amount_residual == 0` and at least one payment |
| `partial` | `amount_residual != 0` and some reconciliation exists |
| `reversed` | Fully reversed by credit note of correct type |
| `blocked` | Manually blocked by user (`action_toggle_block_payment`) |
| `invoicing_legacy` | Inherited from old invoicing module (stable only) |

**`_compute_payment_state` (L3):** Runs a raw SQL query with `UNION ALL` over `account_partial_reconcile` joining to `account.move.line` and `account.payment`. It distinguishes payable/receivable lines only, filtering by `account_type IN ('asset_receivable', 'liability_payable')`. Payment state depends on `is_matched` flag of the payment — `in_payment` means payments are matched but not all in `paid` state.

#### Move Types

| `move_type` Value | Label | Direction | Partner Role | Journal Type |
|-------------------|-------|-----------|--------------|-------------|
| `entry` | Journal Entry | neutral | optional | `general` |
| `out_invoice` | Customer Invoice | debit AR | customer | `sale` |
| `out_refund` | Customer Credit Note | credit AR | customer | `sale` |
| `in_invoice` | Vendor Bill | credit AP | vendor | `purchase` |
| `in_refund` | Vendor Credit Note | debit AP | vendor | `purchase` |
| `out_receipt` | Sales Receipt | cash | customer | `sale` |
| `in_receipt` | Purchase Receipt | cash | vendor | `purchase` |

**L3 — `move_type` immutability:** `move_type` is `readonly=True` after creation. It determines the sign of monetary amounts (`direction_sign`): `out_*` uses `+1`, `in_*` uses `-1` (inverts totals). `move_type` is indexed (`btree`) because it's used to filter invoice lists heavily.

#### State Workflow

```
draft ──(action_post)──> posted ──(button_cancel)──> cancel
  │                          │
  │                          └──(button_draft)───────┘
  │
  └────(delete, if draft only)
```

**`action_post()` (L3):**
1. Checks abnormal amount/date warnings — if any, opens `validate.account.move` wizard (unless `disable_abnormal_invoice_detection` context is set to `False`)
2. Validates all invoices: partner required, invoice_date required for purchase, no negative total, bank account active
3. For future-dated or `restrict_mode_hash_table` journals, calls `action_validate_moves_with_confirmation` wizard
4. Writes `state = 'posted'`, `posted_before = True`
5. Calls `line_ids._create_analytic_lines()` in batch (performance optimization)
6. Handles recurring invoice copying: `auto_post not in ('no', 'at_date')` triggers `_copy_recurring_entries()`
7. Reconciles draft reverse moves: `draft_reverse_moves.reversed_entry_id._reconcile_reversed_moves()`
8. Reconciles marked lines: `line_ids._reconcile_marked()`
9. Auto-assigns `group_partial_purchase_deductibility` if any line has `deductible_amount != 100`
10. **Auto-post logic:** If `soft=True` (default), future-dated moves are deferred with `auto_post = 'at_date'` and a chatter message posted; only `to_post` (today or past) receives the state change

**`button_draft()` (L3):**
- Validates: only `posted` or `cancel` moves allowed; `need_cancel_request` moves blocked
- Calls `_check_draftable()`: rejects exchange difference moves, tax cash basis moves, and hash-locked moves
- Unlinks analytic lines: `analytic_line_ids.with_context(skip_analytic_sync=True).unlink()`
- Detaches PDF attachments: renames them with `(detached by {user} on {date})` suffix
- Clears `sending_data` to abort async sends
- Sets `state = 'draft'`

**`button_cancel()` (L3):**
- If `state == 'posted'`, calls `button_draft()` first, then checks again
- Only `draft` moves proceed to cancellation
- Unlinks reconciliations: `line_ids.remove_move_reconcile()`
- Cancels related payments: `payment_ids.state = 'canceled'`
- Writes `state = 'cancel'`, `auto_post = 'no'`

#### Indexes (L4)

| Index | Columns | Type | Purpose |
|-------|---------|------|---------|
| `_unique_name` | `(name, journal_id)` WHERE `state='posted' AND name!='/'` | Unique | Prevents duplicate posted names |
| `_payment_idx` | `(journal_id, state, payment_state, move_type, date)` | btree | Dashboard filters |
| `_made_gaps` | `(journal_id, state, payment_state, move_type, date)` WHERE `made_sequence_gap=TRUE` | btree | Find sequence gaps |
| `_journal_id_company_id_idx` | `(journal_id, company_id, date)` | btree | Company-scoped queries |
| `_duplicate_bills_idx` | `(ref)` WHERE `move_type IN ('in_invoice', 'in_refund')` | btree | Vendor bill deduplication |

#### Constraints (L3/L4)

| Constraint | Trigger | Error |
|-----------|---------|-------|
| `_unique_name` UniqueIndex | `(name, journal_id)` for posted moves with name != `/` | "Another entry with the same name already exists." |
| `_check_fiscal_year_lock_date` | `write({'date': ...})` on posted move | Prevents backdating past lock date |
| `_check_tax_lock_date` | Tax-affecting fields written on posted move | Prevents modifying taxes past tax lock |
| `_check_reconciliation_date` | Reconciliation on locked date | Prevents reconciling past lock |

**L4 — Balance validation:** `_get_unbalanced_moves()` uses `HAVING ROUND(SUM(balance), currency.decimal_places) != 0` after flushing debit/credit/balance/currency fields. This ensures entries are balanced to the currency's precision before posting. The `ROUND(..., decimal_places)` handles multi-currency entries where rounding at different precisions could produce false imbalances.

**L4 — Lock date sentinel:** `BYPASS_LOCK_CHECK = object()` is a module-level sentinel (empty singleton). `_check_fiscal_lock_dates()` checks `self.env.context.get('bypass_lock_check') is BYPASS_LOCK_CHECK` to short-circuit all lock date checks. This is the canonical safe way to bypass locks programmatically without using raw SQL.

**L4 — Hash immutability:** When `journal_id.restrict_mode_hash_table = True`, each posted entry is hashed using SHA-256 of `(previous_hash + current_data)`. The hash chain extends backwards to the last hashed entry whenever a new entry is posted. `MAX_HASH_VERSION = 4` tracks 4 hash algorithm versions for upgrade compatibility. The `secure_sequence_number` is a gap-free counter enforced by `_made_gaps` partial index (indexes only lines with `made_sequence_gap = TRUE`).

#### Key Methods (L2/L3)

| Method | Signature | Description |
|--------|-----------|-------------|
| `_compute_name` | `()` | Assigns sequence number if `state != 'draft'` and `date` is set |
| `_get_sequence` | `()` | Returns the `ir.sequence` record for this journal/type |
| `_affect_tax_report` | `()` | Returns `True` if move has tax lines affecting tax report |
| `_get_accounting_date` | `(date, affect_tax, lock_dates)` | Returns locked-date-compliant accounting date |
| `_get_violated_lock_dates` | `(date, affect_tax)` | Returns lock dates that would be violated |
| `_collect_tax_cash_basis_values` | `()` | Returns CABA reconciliation values if any |
| `_reconcile_reversed_moves` | `(reversed_moves, move_reverse_cancel)` | Auto-reconciles a reversal entry with original |
| `_inverse_name` | `()` | Writes `name` back to sequence (for `*` prefix handling) |
| `_compute_quick_encoding_vals` | `()` | Computes single-line invoice vals for fiduciary mode |
| `_get_invoice_computed_reference` | `()` | Generates `invoice_reference_model`-based reference |

---

### 2. account.move.line (Journal Item)

**File:** `odoo/addons/account/models/account_move_line.py`

```python
class AccountMoveLine(models.Model):
    _name = 'account.move.line'
    _inherit = ["analytic.mixin"]
    _description = "Journal Item"
    _order = "date desc, move_name desc, id"
    _check_company_auto = True
    _rec_names_search = ['name', 'move_id', 'product_id']
```

#### Core Fields (L1/L2)

| Field | Type | Index | Stored | Description |
|-------|------|-------|--------|-------------|
| `move_id` | Many2one | btree | yes | Parent journal entry (`ondelete=cascade`) |
| `journal_id` | Many2one | btree | yes (precompute) | Related journal (via `move_id`) |
| `company_id` | Many2one | btree | yes (precompute) | Company (via `move_id`) |
| `company_currency_id` | Many2one | - | yes (precompute) | Company currency |
| `move_name` | Char | btree | yes (related) | Move number |
| `parent_state` | Selection | - | yes (related) | Parent move state |
| `date` | Date | btree | yes (related) | Accounting date |
| `ref` | Char | trigram | yes (related) | Move reference |
| `account_id` | Many2one | - (covered by custom idx) | computed | Account (`ondelete=restrict`) |
| `name` | Char | - | computed | Line label (product name or payment term) |
| `debit` | Monetary | - | computed | Debit amount |
| `credit` | Monetary | - | computed | Credit amount |
| `balance` | Monetary | - | computed/stored | `debit - credit` in company currency |
| `cumulated_balance` | Monetary | - | computed | Running balance for display |
| `amount_currency` | Monetary | - | computed/stored | Amount in foreign currency |
| `currency_id` | Many2one | - | computed/stored | Foreign currency |
| `currency_rate` | Float | - | computed | Rate from company to document currency |
| `partner_id` | Many2one | btree | computed | Commercial partner |
| `commercial_partner_country` | Many2one | - | yes (related) | Partner's country |
| `date_maturity` | Date | btree | yes | Due date for AR/AP lines |
| `product_id` | Many2one | btree | yes | Product |
| `product_uom_id` | Many2one | - | computed/stored | Unit of measure |
| `quantity` | Float | - | computed/stored | Line quantity |
| `price_unit` | Float | - | computed/stored | Unit price |
| `discount` | Float | - | 0.0 | Discount percentage |
| `price_subtotal` | Monetary | - | computed | Subtotal (excl. tax) |
| `price_total` | Monetary | - | computed | Total (incl. tax) |
| `tax_ids` | Many2many | - | computed/stored | Taxes applied |
| `tax_line_id` | Many2one | - | yes (related) | Tax that generated this line (for tax lines) |
| `tax_repartition_line_id` | Many2one | btree_not_null | yes | Tax distribution line |
| `tax_tag_ids` | Many2many | - | yes | Tags from tax distribution |
| `tax_group_id` | Many2one | - | yes (related) | Tax group |
| `tax_base_amount` | Monetary | - | yes | Base amount for tax line |
| `group_tax_id` | Many2one | btree_not_null | yes | Originator group tax |
| `analytic_distribution` | Json | - | yes | Analytic distribution `{account_id: percentage}` |
| `analytic_line_ids` | One2many | - | - | Generated analytic lines |
| `display_type` | Selection | - | computed/stored | Line type (product/tax/discount/payment_term/...) |
| `collapse_composition` | Boolean | - | - | Hide sub-lines in section |
| `collapse_prices` | Boolean | - | - | Hide prices in section |
| `parent_id` | Many2one | - | computed | Parent section line |
| `amount_residual` | Monetary | - | computed/stored | Residual after reconciliation |
| `amount_residual_currency` | Monetary | - | computed/stored | Residual in foreign currency |
| `reconciled` | Boolean | - | computed/stored | Fully reconciled flag |
| `full_reconcile_id` | Many2one | btree_not_null | yes | Full reconciliation record |
| `matched_debit_ids` | One2many | - | - | Debits matched against this line |
| `matched_credit_ids` | One2many | - | - | Credits matched against this line |
| `matching_number` | Char | btree | - | `P` (partial) or full reconcile name |
| `is_account_reconcile` | Boolean | - | related | From `account_id.reconcile` |
| `reconcile_model_id` | Many2one | - | yes | Reconciliation model that created this line |
| `payment_id` | Many2one | btree_not_null | yes (related) | Originator payment |
| `statement_line_id` | Many2one | btree_not_null | yes (related) | Bank statement line origin |
| `statement_id` | Many2one | btree_not_null | yes (related) | Bank statement |
| `tax_cash_basis_rec_id` | Many2one | btree_not_null | yes | Cash basis reconciliation record |
| `tax_cash_basis_origin_move_id` | Many2one | btree_not_null | yes | Original move for CABA |
| `tax_cash_basis_created_move_ids` | One2many | - | - | CABA journal entries generated |
| `always_tax_exigible` | Boolean | - | computed/stored | No AR/AP line means always exigible |
| `discount_date` | Date | - | yes | Last date for early payment discount |
| `discount_amount_currency` | Monetary | - | yes | Discounted amount in foreign currency |
| `discount_balance` | Monetary | - | yes | Discounted balance in company currency |
| `payment_date` | Date | - | computed | Closest date (discount_date vs date_maturity) |
| `is_refund` | Boolean | - | computed | Derived from `move_type` |
| `no_followup` | Boolean | - | computed/stored | From move, excludes from follow-up |
| `is_imported` | Boolean | - | - | Captured via import/OCR |
| `sequence` | Integer | - | computed/stored | Line sequence |
| `is_storno` | Boolean | - | computed/stored | Storno accounting flag |
| `checked` | Boolean | - | computed/stored | Reviewed flag |
| `deductible_amount` | Float | - | 100 | Deductibility percentage |
| `term_key` | Binary | - | computed | Payment term grouping key |
| `epd_key` | Binary | - | computed | Early payment discount grouping key |
| `epd_needed` | Binary | - | computed | Whether EP discount applies |
| `discount_allocation_key` | Binary | - | computed | Discount allocation grouping key |
| `extra_tax_data` | Json | - | - | Tax computation engine extra data |
| `has_invalid_analytics` | Boolean | - | computed | Analytic account validity |
| `invoice_line_ids` | One2many | - | - | Subset: product/section/note lines |

#### Display Types (L2)

| Value | Label | Balance | Used For |
|-------|-------|---------|----------|
| `product` | Product | `debit` or `credit` | Invoice lines |
| `cogs` | Cost of Goods Sold | `credit` | COGS entries |
| `tax` | Tax | `credit` | Tax amount lines |
| `non_deductible_tax` | Non Deductible Tax | `credit` | Non-deductible portion |
| `non_deductible_product` | Non Deductible Products | `debit/credit` | Non-deductible base |
| `non_deductible_product_total` | Non Deductible Products Total | varies | Total non-deductible |
| `discount` | Discount | negative credit | Line discounts |
| `rounding` | Rounding | varies | Cash rounding |
| `payment_term` | Payment Term | residual credit | Amount due breakdown |
| `line_section` | Section | 0 | Grouping header |
| `line_subsection` | Subsection | 0 | Nested grouping |
| `line_note` | Note | 0 | Free-text note |
| `epd` | Early Payment Discount | varies | EP discount lines |

#### SQL Constraints (L2/L4)

```sql
-- Both debit and credit cannot be non-zero simultaneously (per line)
CHECK(display_type IN ('line_section', ...) OR credit * debit = 0)

-- amount_currency sign must match balance sign
CHECK(display_type IN (...) OR (
    (balance <= 0 AND amount_currency <= 0)
    OR (balance >= 0 AND amount_currency >= 0)
))

-- Non-accountable lines (sections/notes) must have zero monetary values
CHECK(display_type IN ('line_section', ...) OR (
    amount_currency = 0 AND debit = 0 AND credit = 0 AND account_id IS NULL
))
```

**L4 — Why `credit * debit = 0`?** Odoo uses a single-entry system where each line is either fully debit or fully credit. This is enforced at DB level, not just ORM. The `balance` field is derived: `debit - credit` (stored, inverse-capable). Allowing both non-zero would create double-counting. The third constraint ensures section/note lines have no financial impact.

#### Custom Database Indexes (L4)

```python
_partner_id_ref_idx = models.Index("(partner_id, ref)")
_date_name_id_idx = models.Index("(date desc, move_name desc, id)")
_unreconciled_index = models.Index("(account_id, partner_id) WHERE reconciled IS NOT TRUE")
_journal_id_neg_amnt_residual_idx = models.Index("(journal_id) WHERE amount_residual < 0")
_account_id_date_idx = models.Index("(account_id, date)")
_checked_idx = models.Index("(journal_id) WHERE checked IS NOT TRUE")
```

**L4 — `_unreconciled_index` partial index:** Only indexes unreconciled lines, which are the ones targeted by reconciliation queries. This makes bank reconciliation widget queries fast even on large move line tables (millions of rows). The partial index avoids bloating the index with reconciled lines that will never be used in reconciliation lookups.

**L4 — `_journal_id_neg_amnt_residual_idx` partial index:** Indexes only lines with negative residual (outstanding amounts due to the company for AR, or owed to vendors for AP). Dashboard queries for overdue invoices use this to filter quickly without scanning all lines.

**L4 — `_checked_idx` partial index:** Indexes unchecked entries per journal, enabling the "mark as checked" workflow for review processes without scanning the full journal.

#### Key Methods (L3)

| Method | Description |
|--------|-------------|
| `_compute_balance` | `balance = debit - credit`; handles storno (reversed sign if `is_storno`) |
| `_compute_debit_credit` | Inverse of balance; splits into debit/credit ensuring one is zero |
| `_compute_amount_residual` | `amount_residual = balance - sum(reconciled amounts)` via `_read_group` |
| `_compute_account_id` | Auto-assigns account: payment_term→receivable/payable from partner/company; product→income/expense from product; fallback→journal default |
| `_compute_name` | Sets label: product name from `product.description_sale/purchase`; payment term → `payment_reference` or `ref` |
| `_compute_display_type` | Infers from context: `tax_line_id` → `tax`; receivable/payable → `payment_term`; otherwise → `product` |
| `_compute_tax_ids` | Reads taxes from product (sale/purchase), fiscal position mapping, account defaults |
| `_inverse_analytic_distribution` | Triggers `_create_analytic_lines()` / `_update_analytic_lines()` to sync |
| `_create_analytic_lines` | Batch-creates `account.analytic.line` records from distribution JSON |
| `_check_constrains_account_id_journal_id` | Validates lines don't mix incompatible account types with journal |
| `_reconcile_lines` | Core reconciliation: finds counterpart lines, creates partial/full reconcile |
| `_add_reconciliation_line` | Adds write-off line for partial reconciliation |
| `_prepare_reconciliation_lines` | Prepares matching data for `_reconcile_lines` |

---

### 3. account.account (Chart of Accounts)

**File:** `odoo/addons/account/models/account_account.py`

```python
class AccountAccount(models.Model):
    _name = 'account.account'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Account"
    _order = "code, placeholder_code"
    _check_company_auto = True
    _check_company_domain = models.check_companies_domain_parent_of
```

#### Core Fields (L1/L2)

| Field | Type | Index | Default | Description |
|-------|------|-------|---------|-------------|
| `name` | Char | trigram | required | Account name (translated) |
| `description` | Text | - | - | Internal notes |
| `code` | Char | stored in `code_store` | computed | Account code (company-dependent) |
| `code_store` | Char | - | - | Company-dependent code storage |
| `placeholder_code` | Char | - | computed | Code shown in UI (company-specific or company-prefixed) |
| `account_type` | Selection | btree | computed | Financial type (required) |
| `internal_group` | Selection | - | computed | Group: `asset`, `liability`, `income`, `expense`, `equity`, `off` |
| `reconcile` | Boolean | - | computed | Allow reconciliation |
| `currency_id` | Many2one | - | - | Forced currency (bank accounts) |
| `company_currency_id` | Many2one | - | computed | Company currency |
| `company_ids` | Many2many | - | current | Companies sharing this account |
| `tax_ids` | Many2many | - | - | Default taxes |
| `tag_ids` | Many2many | - | computed/stored | Account tags (for tax reports) |
| `group_id` | Many2one | - | computed | Account group (from code prefix) |
| `root_id` | Many2one | - | computed | Account root (from code prefix) |
| `note` | Text | - | - | Internal notes (tracked) |
| `active` | Boolean | - | `True` | Active flag |
| `used` | Boolean | - | computed | Has journal items (searchable) |
| `include_initial_balance` | Boolean | - | computed | Bring balance forward in reports |
| `current_balance` | Float | - | computed | Live balance from journal items |
| `opening_debit` | Monetary | - | computed | Opening debit |
| `opening_credit` | Monetary | - | computed | Opening credit |
| `opening_balance` | Monetary | - | computed | Net opening balance |
| `related_taxes_amount` | Integer | - | computed | Count of related taxes |
| `non_trade` | Boolean | - | `False` | Non-trade receivable/payable |
| `display_mapping_tab` | Boolean | - | computed | Show code mapping tab |
| `code_mapping_ids` | One2many | - | - | Multi-company code mappings |

#### Account Types (L2/L4)

| `account_type` Value | Label | `internal_group` | `reconcile` Default | `include_initial_balance` Default |
|---------------------|-------|-----------------|---------------------|----------------------------------|
| `asset_receivable` | Receivable | `asset` | `True` (enforced) | `True` |
| `asset_cash` | Bank and Cash | `asset` | `False` | `True` |
| `asset_current` | Current Assets | `asset` | `False` | `True` |
| `asset_non_current` | Non-current Assets | `asset` | `False` | `True` |
| `asset_prepayments` | Prepayments | `asset` | `False` | `True` |
| `asset_fixed` | Fixed Assets | `asset` | `False` | `True` |
| `liability_payable` | Payable | `liability` | `True` (enforced) | `True` |
| `liability_credit_card` | Credit Card | `liability` | `False` | `True` |
| `liability_current` | Current Liabilities | `liability` | `False` | `True` |
| `liability_non_current` | Non-current Liabilities | `liability` | `False` | `True` |
| `equity` | Equity | `equity` | `False` | `True` |
| `equity_unaffected` | Current Year Earnings | `equity` | `False` | `False` |
| `income` | Income | `income` | `False` | `False` |
| `income_other` | Other Income | `income` | `False` | `False` |
| `expense` | Expenses | `expense` | `False` | `False` |
| `expense_other` | Other Expenses | `expense` | `False` | `False` |
| `expense_depreciation` | Depreciation | `expense` | `False` | `False` |
| `expense_direct_cost` | Cost of Revenue | `expense` | `False` | `False` |
| `off_balance` | Off-Balance Sheet | `off` | `False` | `False` |

**L4 — `account_type` vs `internal_group` distinction (critical):** `account_type` is the primary stored `fields.Selection` (19 values including `off_balance`). `internal_group` is a computed `Selection` that extracts the prefix via `_get_internal_group()`:

```python
def _get_internal_group(self, account_type):
    return account_type.split('_', maxsplit=1)[0]
```

This maps `asset_receivable` → `asset`, `liability_payable` → `liability`, `income` → `income`, `off_balance` → `off`. The distinction matters because:
- `account_type` is stored, used for filtering, required for fiscal reporting
- `internal_group` is computed from `account_type` at runtime (not stored) and used for logical grouping in reports and domain filtering
- The `_search_internal_group()` method translates a search on `internal_group` into a `LIKE` query on `account_type` (e.g., `internal_group = 'asset'` becomes `account_type LIKE 'asset%'`)
- `_compute_include_initial_balance` uses `internal_group`: P&L accounts (`income`, `expense`) default to `False`

**L4 — `account_type` compute chain:** `account_type` is `store=True, readonly=False, precompute=True`. It auto-derives from `code` prefix using `_compute_account_type()` which calls `_get_closest_parent_account()`. Only accounts without an existing `account_type` are processed, so user overrides are preserved.

**L3 — `reconcile` compute:** `False` for `income`, `expense`, `equity`, `off_balance` groups (hardcoded in `_compute_reconcile`). `True` for `asset_receivable` and `liability_payable` (enforced by `_check_reconcile` SQL constraint). For other asset/liability types, no automatic change is made.

#### Multi-Company Code System (L4)

**L4 — The problem:** In multi-company setups, the same account can have different codes per company due to different chart of accounts.

**L4 — The solution:** `code` is NOT a plain Char field. It is:

```python
code = fields.Char(
    string="Code", size=64, tracking=True,
    compute='_compute_code', search='_search_code',
    inverse='_inverse_code'
)
code_store = fields.Char(company_dependent=True)  # stored, per-company JSON-like
```

- `code_store` stores `{root_company_id: code}` as a JSON string (using Postgres JSONB behavior via `->>`)
- `_compute_code()` reads from `code_store` for the current `company.root_id`
- `_inverse_code()` writes back to `code_store` for the current `company.root_id`
- `_search_code()` searches via `with_company(root_id).sudo()` to use the correct company's code

**L4 — `_field_to_sql` override (the critical mechanism):**

```python
def _field_to_sql(self, alias: str, field_expr: str, query: Query | None = None) -> SQL:
    if field_expr == 'internal_group':
        return SQL("split_part(%s, '_', 1)", self._field_to_sql(alias, 'account_type', query))
    if field_expr == 'code':
        # Redirect 'code' column to 'code_store' using the current company's root_id
        return self.with_company(self.env.company.root_id).sudo()._field_to_sql(
            alias, 'code_store', query
        )
    if field_expr == 'placeholder_code':
        # Shows company-specific code, or code (Company Name) if no code for current company
        return SQL(
            """COALESCE(
                %(code_store)s->>%(active_company_root_id)s,
                %(code_store)s->>%(account_first_company_root_id)s || ' (' || %(account_first_company_name)s || ')'
            )""",
            code_store=SQL.identifier(alias, 'code_store'),
            active_company_root_id=str(self.env.company.root_id.id),
            account_first_company_name=SQL.identifier('account_first_company', 'company_name'),
            account_first_company_root_id=SQL.identifier('account_first_company', 'root_company_id'),
            ...
        )
```

This override ensures that ORM queries, domain filters, and `name_search()` all use the correct company's code without manual SQL injection.

**L4 — `placeholder_code` for multi-company display:** When an account is shared across companies but has no code for the current company, Odoo shows `code (Company Name)` by looking up the first company in the hierarchy that does have a code, via a `DISTINCT ON` JOIN.

#### Binary Search for Parent Account Type (L4)

**L4 — `_get_closest_parent_account` algorithm:**

```python
def _get_closest_parent_account(self, accounts_to_process, field_name, default_value):
    all_accounts = self.search_read(
        domain=self._check_company_domain(self.env.company),
        fields=['code', field_name],
        order='code',
    )
    accounts_with_codes = {account['code']: account[field_name] for account in all_accounts}
    for account in accounts_to_process:
        codes_list = list(accounts_with_codes.keys())
        closest_index = bisect_left(codes_list, account.code) - 1
        account[field_name] = accounts_with_codes[codes_list[closest_index]] \
            if closest_index != -1 else default_value
```

This uses Python's `bisect_left` (binary search) on the sorted list of account codes. For a new account `code='102500'`, it finds the immediate predecessor account in the chart — e.g., `102400` (a parent group account) — and copies its `account_type`. Falls back to `default_value='asset_current'` if no predecessor exists. Complexity is `O(log n)` instead of `O(n)` for a naive linear scan.

#### name_search() Optimization (L4)

```python
def name_search(self, name='', domain=None, operator='ilike', limit=100):
    move_type = self.env.context.get('move_type')
    ...
    digit_in_search_term = any(c.isdigit() for c in name)
    if digit_in_search_term:
        domain = Domain.AND([search_domain, domain])  # Full search for code searches
    else:
        # No digits → assume it's a name search, restrict by account type
        move_type_accounts = {
            'out': ['income'],          # outbound: customer payment → income account
            'in': ['expense', 'asset_fixed'],  # inbound: vendor bill → expense or asset
        }
        allowed_account_types = move_type_accounts.get(move_type.split('_')[0])
        domain = Domain.AND([search_domain, type_domain, domain])

    # Sort by partner frequency (preferred accounts first)
    records = self.with_context(preferred_account_ids=suggested_accounts)...
```

**Why the digit check matters:** If the user types a code (contains digits), the search does a full `ilike` on name+code. If they type only letters (name-only search), Odoo restricts to relevant account types for that direction. This prevents a "Bank" search in an outbound invoice from suggesting `4-digit expense accounts` instead of `income` accounts.

The `preferred_account_ids` context is also used in `_order_to_sql()` to push frequently-used accounts to the top of results.

#### Constraints (L3/L4)

| Constraint | Condition | Error |
|-----------|-----------|-------|
| `_check_reconcile` | `asset_receivable` or `liability_payable` without `reconcile=True` | "You cannot have a receivable/payable account that is not reconcilable" |
| `_constrains_reconcile` | `off_balance` with `reconcile=True` | "An Off-Balance account can not be reconcilable" |
| `_constrains_reconcile` | `off_balance` with `tax_ids` | "An Off-Balance account can not have taxes" |
| `_check_company_consistency` | `asset_cash` shared between multiple companies | "Bank & Cash accounts cannot be shared between companies" |
| `_check_account_type_sales_purchase_journal` | Receivable/Payable account used in sale/purchase journal | "The account is already in use in a 'sale' or 'purchase' journal" |
| `_check_account_is_bank_journal_bank_account` | Account set as bank journal default and changed to receivable/payable | "You cannot change the type of an account set as Bank Account" |

#### Key Methods (L3)

| Method | Description |
|--------|-------------|
| `_search_new_account_code(start_code, cache)` | Increments code to find unused code (handles numeric: `102100→102101`; alphanumeric: `10.01.97→10.01.98`; alpha: `hello→hello.copy`) |
| `_ensure_code_is_unique()` | Validates uniqueness per company and that all companies have a code |
| `_compute_account_tags` | Derives `tag_ids` from account type + country-specific fiscal position mapping |
| `_get_closest_parent_account(records, field_name, default_value)` | Finds nearest parent with a value for `field_name` by code prefix matching |
| `_order_accounts_by_frequency_for_partner(company_id, partner_id, move_type)` | Returns account IDs ordered by partner usage frequency, using raw SQL with `_field_to_sql` |

---

### 4. account.journal (Journal)

**File:** `odoo/addons/account/models/account_journal.py`

```python
class AccountJournal(models.Model):
    _name = 'account.journal'
    _inherit = [
        'portal.mixin',
        'mail.alias.mixin.optional',
        'mail.thread',
        'mail.activity.mixin',
    ]
    _description = "Journal"
    _order = 'sequence, type, code'
    _check_company_auto = True
    _check_company_domain = models.check_company_domain_parent_of
    _rec_names_search = ['name', 'code']
```

#### Core Fields (L1/L2)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required | Journal display name (translated) |
| `name_placeholder` | Char | computed | Short placeholder name |
| `code` | Char | required | Short code (max 5 chars), used as sequence prefix |
| `type` | Selection | required | `sale`/`purchase`/`cash`/`bank`/`credit`/`general` |
| `active` | Boolean | `True` | Active flag |
| `is_self_billing` | Boolean | - | Self-billing journal (separate sequence per partner) |
| `default_account_id` | Many2one | computed | Default account for this journal |
| `default_account_type` | Char | computed | Type of default account |
| `suspense_account_id` | Many2one | computed | Suspense account for bank/cash |
| `non_deductible_account_id` | Many2one | - | Private share account for mixed expenses |
| `restrict_mode_hash_table` | Boolean | - | Enable hash immutability |
| `sequence` | Integer | `10` | Dashboard ordering |
| `invoice_reference_type` | Selection | `invoice` | `partner` (customer-based) or `invoice` (number-based) |
| `invoice_reference_model` | Selection | `odoo` | Reference format: `odoo`/`euro`/`number` |
| `refund_sequence` | Boolean | computed | Separate sequence for refunds |
| `payment_sequence` | Boolean | computed | Separate sequence for payments |
| `currency_id` | Many2one | - | Journal currency (for bank/cash) |
| `company_id` | Many2one | current | Company |
| `country_code` | Char | related | Company country code |
| `account_fiscal_country_group_codes` | Json | related | Company's fiscal country group codes |
| `sequence_override_regex` | Text | - | Regex to enforce complex sequence composition |
| `invoice_template_pdf_report_id` | Many2one | computed | PDF report template |
| `available_invoice_template_pdf_report_ids` | One2many | computed | Available PDF templates |
| `display_invoice_template_pdf_report_id` | Boolean | computed | Show template selector |
| `alias_id` | Many2one | - | Email alias for incoming invoices |
| `show_on_dashboard` | Boolean | `True` | Show on accounting dashboard |
| `color` | Char | - | Dashboard color |
| `inbound_payment_method_line_ids` | One2many | computed | Available inbound payment methods |
| `outbound_payment_method_line_ids` | One2many | computed | Available outbound payment methods |
| `show_fetch_in_einvoices_button` | Boolean | computed | Show Peppol fetch button |
| `show_refresh_out_einvoices_status_button` | Boolean | computed | Show Peppol refresh button |
| `incoming_einvoice_notification_email` | Char | - | Email routing address |

#### Journal Types and Defaults (L3)

| Type | Default Account Type | Suspense Account | `invoice_reference_model` default |
|------|---------------------|-------------------|----------------------------------|
| `sale` | `income` / `income_other` | not used | based on country |
| `purchase` | `expense` / `expense_depreciation` / `expense_direct_cost` | not used | based on country |
| `cash` | `asset_cash` | created if missing | not used |
| `bank` | `asset_cash` / `liability_credit_card` | created if missing | not used |
| `credit` | `liability_credit_card` | not used | not used |
| `general` | any type | not used | not used |

**L3 — `_onchange_type()` behavior:**
- `sale`/`purchase`: sets `refund_sequence = True`
- `cash`/`bank`: creates `suspense_account_id` from `account.account` template if missing; sets `default_account_id` domain
- `credit`: sets `default_account_type = 'liability_credit_card'`
- `general`: no special defaults

#### Key Methods (L2/L3)

| Method | Description |
|--------|-------------|
| `_get_default_account_domain` | Returns domain for `default_account_id` based on journal type |
| `_default_invoice_reference_model` | Detects country-specific reference model (e.g., `fr` → `euro`) |
| `_check_company_consistency` | Ensures journal's account currencies match journal currency |
| `_search_default_journal` | Finds suitable journal for a move type (resolves currency) |

#### AccountJournalGroup

```python
class AccountJournalGroup(models.Model):
    _name = 'account.journal.group'
```

Allows excluding specific journals from the accounting dashboard grouping. Key field: `excluded_journal_ids` (Many2many to `account.journal`).

---

### 5. account.tax (Tax)

**File:** `odoo/addons/account/models/account_tax.py`

```python
class AccountTax(models.Model):
    _name = 'account.tax'
    _inherit = ['mail.thread']
    _description = 'Tax'
    _order = 'sequence, id'
    _check_company_auto = True
    _rec_names_search = ['name', 'description', 'invoice_label']
    _check_company_domain = models.check_company_domain_parent_of
```

#### Core Fields (L1/L2)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required | Tax name (translated, tracked) |
| `type_tax_use` | Selection | `sale` | `sale` / `purchase` / `none` |
| `tax_scope` | Selection | - | `service` / `consu` (product type restriction) |
| `amount_type` | Selection | `percent` | `group` / `fixed` / `percent` / `division` |
| `amount` | Float | `0.0` | Rate or fixed amount (4 decimal precision) |
| `sequence` | Integer | `1` | Application order |
| `company_id` | Many2one | current | Company |
| `country_id` | Many2one | computed | Country of applicability |
| `country_code` | Char | related | Country code |
| `active` | Boolean | `True` | Active flag |
| `children_tax_ids` | Many2many | - | Child taxes (for group type) |
| `price_include` | Boolean | computed | Included in product price |
| `price_include_override` | Selection | - | Override company's default: `tax_included`/`tax_excluded` |
| `include_base_amount` | Boolean | `False` | Affects base of subsequent taxes |
| `is_base_affected` | Boolean | `True` | Affected by previous taxes |
| `analytic` | Boolean | `False` | Include in analytic cost |
| `tax_group_id` | Many2one | computed | Tax group (country-filtered) |
| `tax_exigibility` | Selection | `on_invoice` | `on_invoice` / `on_payment` (cash basis) |
| `cash_basis_transition_account_id` | Many2one | - | CABA transition account |
| `invoice_repartition_line_ids` | One2many | auto-created | Invoice distribution (base + tax lines) |
| `refund_repartition_line_ids` | One2many | auto-created | Refund distribution |
| `repartition_line_ids` | One2many | - | All distribution lines |
| `fiscal_position_ids` | Many2many | - | Fiscal positions where this tax is used |
| `original_tax_ids` | Many2many | - | Domestic taxes replaced by this one |
| `replacing_tax_ids` | Many2many | - | Taxes this one replaces (readonly) |
| `is_domestic` | Boolean | computed | True if not in any fiscal position |
| `is_used` | Boolean | computed | Has transactions or child taxes |
| `repartition_lines_str` | Char | computed | Formatted string of repartition for tracking |
| `invoice_legal_notes` | Html | - | Legal notes for invoices |
| `has_negative_factor` | Boolean | computed | Has repartition line with negative percentage |
| `description` | Html | - | Tax description |
| `invoice_label` | Char | - | Custom label on invoices |
| `deductible_amount` | Float | `100` | Deductibility percentage (Odoo 18→19) |

#### Tax Amount Computation (L3/L4)

| `amount_type` | Formula | Use Case |
|---------------|---------|----------|
| `percent` | `base * amount / 100` | Standard VAT (e.g., 20%) |
| `fixed` | `amount * quantity` | Flat fee per unit |
| `division` | `base * amount / (100 - amount)` | Tax-included: `180 / (1 - 10%) = 200` base |
| `group` | Sum of `children_tax_ids` | Compound taxes (e.g., state + federal) |

**L4 — `division` amount_type gotcha:** The formula `base * amount / (100 - amount)` divides by zero if `amount >= 100`. Odoo allows it but it produces infinity values. Odoo 18+ added `has_negative_factor` to flag repartition lines with negative percentages (e.g., `+100%, -100%`) which are used in reverse-charge scenarios.

**L4 — `deductible_amount` (Odoo 18→19):** The `deductible_amount` field (default `100`) enables partial deductibility. Values `< 100` trigger `_post()` to generate additional display-type lines:
- `non_deductible_tax`: non-deductible tax portion
- `non_deductible_product`: non-deductible base portion  
- `non_deductible_product_total`: total non-deductible line

These lines use the journal's `non_deductible_account_id` to redirect the non-deductible portion to a specific account.

#### Repartition Lines (L2/L3)

Each tax has `invoice_repartition_line_ids` and `refund_repartition_line_ids`, each containing lines of two types:

| `repartition_type` | Description | Used For |
|-------------------|-------------|----------|
| `base` | Base amount distribution | Multi-account base allocation |
| `tax` | Tax amount distribution | Tax payable split across accounts (e.g., partial VAT) |

Fields on `account.tax.repartition.line`:
- `account_id`: Destination account (optional; if omitted, uses tax group account)
- `factor_percent`: Percentage of the tax/base to allocate (e.g., `50` = half)
- `use_in_tax_closing`: Include in tax report (`True` by default)
- `tag_ids`: `account.account.tag` for tax report mapping
- `document_type`: `invoice` or `refund`

**L3 — Default auto-creation:** When a tax is created, Odoo auto-populates two lines: one `base` and one `tax`, each at `100%` with no account and no tags. The user must customize these for country-specific reporting requirements.

#### Tax Exigibility / Cash Basis (L3/L4)

| Setting | Tax Recognition | Account Impact |
|---------|-----------------|----------------|
| `on_invoice` | Invoice validation | Tax amount goes directly to tax payable account |
| `on_payment` | Payment receipt | Tax amount goes to `cash_basis_transition_account_id` until payment |

**L4 — CABA workflow:**
1. Invoice posted with `on_payment` tax → tax line created with `tax_cash_basis_origin_move_id`
2. Payment received → `account.partial.reconcile` created linking payment to invoice line
3. `account.partial.reconcile._collect_tax_cash_basis_values()` computes percentage of invoice paid
4. CABA entry generated: Dr `tax_cash_basis_transition_account_id`, Cr `tax_payable_account_id`
5. When invoice is cancelled → CABA entry is automatically reversed

**L4 — `always_tax_exigible` compute (Odoo 18→19):** Added to optimize tax tag assignment. Lines without AR/AP accounts are marked always exigible even during invoice encoding, avoiding unnecessary cash basis tracking.

**Constraint:** `cash_basis_transition_account_id.reconcile` must be `True`. Enforced by `_constrains_cash_basis_transition_account`.

#### Tax Group (L2/L3)

| Field on `account.tax.group` | Description |
|------------------------------|-------------|
| `name` | Group name (translated) |
| `sequence` | Display order |
| `company_id` | Company |
| `country_id` | Country (computed from company) |
| `tax_payable_account_id` | Credited when tax is due (liability) |
| `tax_receivable_account_id` | Debited when tax is paid (asset) |
| `advance_tax_payment_account_id` | For downpayments on tax account |
| `preceding_subtotal` | Subtotal label before this group in invoice |

**L3 — Country-filtered tax groups:** `tax_group_id` domain is `[('country_id', 'in', (tax.country_id, False))]`. When not set or mismatched, `_compute_tax_group_id` searches for a matching group by country/company, falling back to a country-agnostic group.

#### Constraints (L3/L4)

| Constraint | Condition | Error |
|-----------|-----------|-------|
| `_constrains_name` | Same `name`, `type_tax_use`, `tax_scope`, `country_id` within company hierarchy | "Tax names must be unique!" |
| `validate_tax_group_id` | Tax group's country differs from tax's country | "The tax group must have the same country_id" |
| `_constrains_cash_basis_transition_account` | `on_payment` without reconcilable transition account | "The cash basis transition account needs to allow reconciliation" |

**L4 — Tax uniqueness batch processing:** `_constrains_name()` splits all taxes into batches of 100 records for validation, avoiding N+1 queries on large tax tables. Each batch checks uniqueness within that batch only.

---

### 6. account.payment (Payment)

**File:** `odoo/addons/account/models/account_payment.py`

```python
class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['mail.thread.main.attachment', 'mail.activity.mixin']
```

#### Core Fields (L1/L2)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Payment number (computed from sequence) |
| `date` | Date | Payment date |
| `amount` | Monetary | Payment amount |
| `payment_type` | Selection | `inbound` / `outbound` |
| `partner_type` | Selection | `customer` / `supplier` |
| `partner_id` | Many2one | Customer or vendor |
| `journal_id` | Many2one | Payment journal |
| `company_id` | Many2one | Company |
| `currency_id` | Many2one | Payment currency |
| `payment_method_line_id` | Many2one | Payment method (manual, SEPA, etc.) |
| `state` | Selection | `draft`/`in_process`/`paid`/`canceled`/`rejected` |
| `move_id` | Many2one | Generated journal entry |
| `destination_account_id` | Many2one | Computed counterpart account |
| `paired_internal_transfer_payment_id` | Many2one | For internal transfer pairing |
| `is_reconciled` | Boolean | Fully reconciled |
| `is_matched` | Boolean | Matched with bank statement |
| `is_sent` | Boolean | Sent to PSP |
| `available_partner_bank_ids` | Many2many | Computed partner bank accounts |
| `partner_bank_id` | Many2one | Source/destination bank account |
| `qr_code` | Html | SEPA QR code URL |
| `origin_payment_id` | Many2one | Payment that created this entry |
| `matched_payment_ids` | Many2many | Payments linked to invoice |
| `preferred_payment_method_line_id` | Many2one | Preferred method for invoice |
| `outstanding_account_id` | Many2one | Computed outstanding account from journal |

#### Payment States (L3)

| State | Trigger | Effects |
|-------|---------|---------|
| `draft` | Created | Editable, no journal entry |
| `in_process` | `action_post` called | Journal entry created in `draft`, awaiting reconciliation |
| `paid` | Fully reconciled | `is_reconciled = True` |
| `canceled` | `action_cancel` | Journal entry reversed |
| `rejected` | Bank rejection | Needs re-processing |

**L3 — Payment reconciliation:** When `action_post` is called, `_create_payment_entry(amount)` creates a journal entry with two lines: one on the journal's payment account (debited for outbound, credited for inbound), one on the `destination_account_id` (counterpart). The payment stays in `in_process` until both lines are reconciled with the invoice lines.

**L4 — Payment state transition:** `account.partial.reconcile.create()` calls `_get_to_update_payments(from_state='in_process')` which iterates all partials, finds matched payments, and sets them to `paid` when fully matched. `account.partial.reconcile.unlink()` resets them back to `in_process`.

**L4 — `_seek_for_lines()`:** Returns a `(debit_line, credit_line)` tuple from `move_id` sorted by amount. Used by `action_reconcile` to find which line to match against.

#### Key Methods (L2/L3)

| Method | Description |
|--------|-------------|
| `_compute_name` | Payment number from journal's payment sequence |
| `_compute_journal_id` | Default journal from payment type + available methods |
| `_compute_partner_bank_id` | Default bank from partner (preferred: same currency as journal) |
| `_create_payment_entry(amount)` | Creates journal entry for payment |
| `_seek_for_lines()` | Returns (debit_line, credit_line) tuple from `move_id` |
| `action_post` | Validates payment, creates journal entry |
| `action_cancel` | Cancels payment, reverses journal entry |
| `action_draft` | Resets to draft |

---

### 7. account.payment.term (Payment Terms)

**File:** `odoo/addons/account/models/account_payment_term.py`

#### Core Fields (L1/L2)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Terms name |
| `active` | Boolean | Active status |
| `note` | Html | Description on invoice |
| `line_ids` | One2many | Terms lines |
| `company_id` | Many2one | Company |
| `early_discount` | Boolean | Early payment discount available |
| `discount_percentage` | Float | Discount % for early payment |
| `discount_days` | Integer | Days for early payment discount |
| `early_pay_discount_computation` | Selection | `included`/`excluded`/`mixed` |

#### Payment Term Line (`account.payment.term.line`)

| Field | Type | Description |
|-------|------|-------------|
| `payment_term_id` | Many2one | Parent payment term |
| `value` | Selection | `fixed` / `percent` / `balance` |
| `value_amount` | Float | Amount or percentage |
| `nb_days` | Integer | Days after invoice date |
| `delay` | Integer | Alternative to `nb_days` |
| `company_id` | Many2one | Company |

**`_compute_terms()` (L3):** Computes payment term installments returning a dict with:
- `line_ids`: List of `{date, company_amount, foreign_amount, discount_date, discount_balance, discount_amount_currency}`
- `discount_date`: Last date for early payment discount
- `discount_balance`: Amount due if paid on `discount_date`
- `discount_amount_currency`: Discounted foreign currency amount

The `early_pay_discount_computation` modes:
- `included`: Discount reduces the tax base proportionally
- `excluded`: Discount applies only to untaxed amount
- `mixed`: Discount applies to total but tax amounts are unchanged

---

### 8. account.bank.statement (Bank Statement)

**File:** `odoo/addons/account/models/account_bank_statement.py`

#### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Reference (computed) |
| `reference` | Char | External reference |
| `date` | Date | Statement date |
| `balance_start` | Monetary | Starting balance |
| `balance_end` | Monetary | Computed ending balance |
| `balance_end_real` | Monetary | Actual ending balance |
| `journal_id` | Many2one | Bank/cash journal |
| `line_ids` | One2many | Statement lines |
| `is_complete` | Boolean | All lines reconciled |
| `is_valid` | Boolean | Balance matches |
| `company_id` | Many2one | Company |
| `move_id` | Many2one | Generated journal entry |

#### account.bank.statement.line

| Field | Type | Description |
|-------|------|-------------|
| `statement_id` | Many2one | Parent statement |
| `date` | Date | Transaction date |
| `amount` | Monetary | Transaction amount (positive=credit, negative=debit) |
| `amount_currency` | Monetary | Foreign currency amount |
| `currency_id` | Many2one | Foreign currency |
| `partner_id` | Many2one | Partner |
| `partner_name` | Char | Partner name (if not matched) |
| `payment_ref` | Char | Payment reference |
| `narration` | Text | Notes |
| `transaction_type` | Char | Transaction type |
| `ref` | Char | External reference |
| `is_reconciled` | Boolean | Line reconciled |
| `move_name` | Char | Generated entry name |
| `journal_id` | Many2one | Statement journal |
| `sequence` | Integer | Line order |
| `foreign_currency_id` | Many2one | Statement line currency |
| `amount_currency` | Monetary | Amount in foreign currency |

---

### 9. account.reconcile.model (Reconciliation Model)

**File:** `odoo/addons/account/models/account_reconcile_model.py`

Automates bank statement line matching and write-off entry creation.

```python
class AccountReconcileModel(models.Model):
    _name = 'account.reconcile.model'
    _inherit = ['mail.thread']
```

#### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Rule name |
| `active` | Boolean | Active status |
| `sequence` | Integer | Priority |
| `company_id` | Many2one | Company |
| `trigger` | Selection | `manual` / `auto_reconcile` |
| `match_journal_ids` | Many2many | Journals to match |
| `match_amount_min` | Float | Minimum amount |
| `match_amount_max` | Float | Maximum amount |
| `match_label` | Char | Label pattern (regex) |
| `match_same_currency` | Boolean | Same currency required |
| `match_partner_ids` | Many2many | Partner filter |
| `match_partner_category_ids` | Many2many | Partner category filter |
| `line_ids` | One2many | Model lines (write-off entries) |
| `past_months_limit` | Integer | Lookback period |
| `decimal_separator` | Char | Amount decimal separator |

#### account.reconcile.model.line

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | Many2one | Parent model |
| `sequence` | Integer | Line order |
| `account_id` | Many2one | Write-off account |
| `journal_id` | Many2one | Journal for write-off entry |
| `label` | Char | Write-off entry label |
| `amount_type` | Selection | `fixed` / `percentage` / `percentage_st_line` / `regex` |
| `amount_string` | Char | Amount value or regex |
| `tax_ids` | Many2many | Taxes |
| `analytic_distribution` | Json | Analytic distribution |
| `note` | Text | Internal notes |

**L4 — `regex` amount_type:** `amount_string` is compiled via `re.compile()` in `_validate_amount()`. The regex is matched against the bank statement line's `ref` field to extract a numeric amount.

---

### 10. account.payment.method (Payment Method)

**File:** `odoo/addons/account/models/account_payment_method.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Method name (translated) |
| `code` | Char | Internal code |
| `payment_type` | Selection | `inbound` / `outbound` |

**SQL Constraint:** `unique(code, payment_type)` — prevents duplicate code/payment_type combos.

**Auto-linking:** On create, if mode is `'multi'`, auto-creates payment method lines on all matching journals.

---

### 11. account.cash.rounding (Cash Rounding)

**File:** `odoo/addons/account/models/account_cash_rounding.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Rounding name |
| `rounding` | Float | Precision (e.g., `0.05`) |
| `strategy` | Selection | `biggest_tax` (modify tax) / `add_invoice_line` (add rounding line) |
| `profit_account_id` | Many2one | Profit account for rounding |
| `loss_account_id` | Many2one | Loss account for rounding |
| `rounding_method` | Selection | `UP` / `DOWN` / `HALF-UP` |

**Constraint:** `rounding > 0`

---

### 12. account.incoterms (Incoterms)

**File:** `odoo/addons/account/models/account_incoterms.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Incoterm name (e.g., "EXW - Ex Works") |
| `code` | Char | Incoterm code (e.g., "EXW") |

---

### 13. account.full.reconcile (Full Reconciliation)

**File:** `odoo/addons/account/models/account_full_reconcile.py`

Groups multiple `account.partial.reconcile` records into a single full reconciliation.

```python
class AccountFullReconcile(models.Model):
    _name = 'account.full.reconcile'
    _description = "Full Reconcile"
```

| Field | Type | Description |
|-------|------|-------------|
| `partial_reconcile_ids` | One2many | All partial reconciliations in this full reconciliation |
| `reconciled_line_ids` | One2many | All journal items in this full reconciliation |

**L4 — Batch SQL update:** `create()` uses `cr.execute_values()` with `page_size=1000` to batch-update `full_reconcile_id` on all `account.move.line` and `account.partial.reconcile` records in a single SQL statement, avoiding N+1 ORM overhead.

---

### 14. account.partial.reconcile (Partial Reconciliation)

**File:** `odoo/addons/account/models/account_partial_reconcile.py`

Tracks individual reconciliation links between journal items.

```python
class AccountPartialReconcile(models.Model):
    _name = 'account.partial.reconcile'
    _description = "Partial Reconcile"
```

#### Core Fields (L1/L2)

| Field | Type | Description |
|-------|------|-------------|
| `debit_move_id` | Many2one | Debit journal item |
| `credit_move_id` | Many2one | Credit journal item |
| `full_reconcile_id` | Many2one | Full reconciliation this belongs to |
| `exchange_move_id` | Many2one | Exchange difference move generated |
| `amount` | Monetary | Matched amount in company currency |
| `debit_amount_currency` | Monetary | Matched amount in debit line's foreign currency |
| `credit_amount_currency` | Monetary | Matched amount in credit line's foreign currency |
| `max_date` | Date | Max of both line dates (for aged receivable reports) |
| `company_id` | Many2one | Company |
| `draft_caba_move_vals` | Json | CABA draft entry values (used to detect changes) |

#### Reconciliation Graph & Union-Find Algorithm (L4)

**L4 — The matching number problem:** When multiple payments reconcile with multiple invoice lines in a cascade, all involved lines share one matching number. This is modeled as a graph where nodes are `account.move.line` records and edges are `account.partial.reconcile` records.

**L4 — `_update_matching_number()` union-find algorithm:**

```python
def _update_matching_number(self, amls):
    amls = amls._all_reconciled_lines()
    all_partials = amls.matched_debit_ids | amls.matched_credit_ids

    # Each graph is keyed by the minimum partial ID in that graph
    number2lines = {}   # min_partial_id → [line_ids]
    line2number = {}   # line_id → min_partial_id

    for partial in all_partials.sorted('id'):
        debit_min = line2number.get(partial.debit_move_id.id)
        credit_min = line2number.get(partial.credit_move_id.id)

        if debit_min and credit_min:  # Merge two graphs
            if debit_min != credit_min:
                min_id = min(debit_min, credit_min)
                max_id = max(debit_min, credit_min)
                for line_id in number2lines[max_id]:
                    line2number[line_id] = min_id
                number2lines[min_id].extend(number2lines.pop(max_id))

        elif debit_min:  # Add credit node to existing graph
            number2lines[debit_min].append(partial.credit_move_id.id)
            line2number[partial.credit_move_id.id] = debit_min

        elif credit_min:  # Add debit node to existing graph
            number2lines[credit_min].append(partial.debit_move_id.id)
            line2number[partial.debit_move_id.id] = credit_min

        else:  # Create new graph (single partial = two lines)
            number2lines[partial.id] = [partial.debit_move_id.id, partial.credit_move_id.id]
            line2number[partial.debit_move_id.id] = partial.id
            line2number[partial.credit_move_id.id] = partial.id

    # Batch SQL update with page_size=1000
    self.env.cr.execute_values("""
        UPDATE account_move_line l
           SET matching_number = CASE
                   WHEN l.full_reconcile_id IS NOT NULL THEN l.full_reconcile_id::text
                   ELSE 'P' || source.number
               END
          FROM (VALUES %s) AS source(number, ids)
         WHERE l.id = ANY(source.ids)
    """, list(number2lines.items()), page_size=1000)
```

**L4 — Why sorted by `id`?** The algorithm assigns the minimum partial ID as the graph key. Sorting ensures deterministic results — the same graph always produces the same matching number regardless of database order.

**L4 — Matching number format:** Partial reconciliations get `'P' + min_partial_id` (e.g., `P42`). Full reconciliations use the full reconcile's ID as text. This allows quick identification of which partial record links a set of lines.

#### Life Cycle Hooks (L3/L4)

**`create()` (L3):**
1. Creates the partial record
2. Finds fully-matched payments → sets them to `paid` via `_get_to_update_payments()`
3. Calls `_update_matching_number()` to refresh all affected line graphs

**`unlink()` (L3/L4):**
1. Retrieves all affected payments (resets to `in_process`)
2. Collects CABA and exchange difference moves to reverse
3. Unlinks the partial (flushes `full_reconcile_id`)
4. Unlinks the full reconcile (cascade)
5. Reverses CABA/exchange moves (posted → reversal entry; draft → delete)
6. Updates matching numbers for all affected lines
7. Resets matched payments to `in_process`

**`_collect_tax_cash_basis_values()` (L3):** Called after partial reconciliation creation to generate CABA entries. Computes the percentage of the invoice paid (`partial_amount / total_balance`) and generates proportional tax entries.

---

### 15. account.analytic.plan / account.analytic.account / account.analytic.line

**File:** `odoo/addons/account/models/account_analytic_plan.py`

#### account.analytic.plan

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Plan name |
| `default_plan` | Boolean | Default plan for new accounts |
| `company_id` | Many2one | Company |
| `account_ids` | One2many | Accounts in this plan |

#### account.analytic.account

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Account name |
| `code` | Char | Account code |
| `plan_id` | Many2one | Analytic plan |
| `company_id` | Many2one | Company |
| `active` | Boolean | Active status |
| `partner_id` | Many2one | Related partner |

#### account.analytic.line

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | Many2one | Analytic account |
| `product_id` | Many2one | Product |
| `product_uom_id` | Many2one | Unit of measure |
| `unit_amount` | Float | Quantity |
| `amount` | Monetary | Amount (can be positive or negative) |
| `company_id` | Many2one | Company |
| `date` | Date | Date |
| `move_line_id` | Many2one | Source journal item |
| `ref` | Char | Reference |
| `name` | Char | Description |
| `general_account_id` | Many2one | Related account |

---

### 16. account.analytic.distribution.model (Analytic Distribution Template)

**File:** `odoo/addons/account/models/account_analytic_distribution_model.py`

Stores reusable analytic distribution templates.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Template name |
| `account_ids` | Many2many | Accounts |
| `percentage` | Float | Percentage per account |
| `company_id` | Many2one | Company |
| `partner_id` | Many2one | Partner filter |

**Analytic Distribution JSON format:**
```json
{"analytic_account_id_1": 40.0, "analytic_account_id_2": 60.0}
```
Percentages must sum to 100. Enforced via `_check_analytic_distribution()` on `account.move.line`.

---

### 17. account.fiscal.position (Fiscal Position)

**File:** `odoo/addons/account/models/account_fiscal_position.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Position name |
| `auto_apply` | Boolean | Detect automatically |
| `vat_required` | Boolean | VAT required |
| `country_id` | Many2one | Country |
| `country_group_id` | Many2one | Country group |
| `state_ids` | Many2many | Federal states |
| `zip_from` / `zip_to` | Char | ZIP range |
| `account_ids` | One2many | Account mappings |
| `tax_ids` | Many2many | Tax mappings |

#### account.fiscal.position.account

Maps source account to destination account.

#### account.fiscal.position.tax

Maps source tax to destination tax.

#### Key Methods

| Method | Description |
|--------|-------------|
| `_get_fiscal_position(partner, company, delivery=None)` | Detects applicable fiscal position based on partner country/state/zip |
| `map_tax()` | Maps taxes based on position |
| `map_account()` | Maps accounts based on position |

---

### 18. account.lock.exception (Lock Date Exception)

**File:** `odoo/addons/account/models/account_lock_exception.py`

**Odoo 18→19:** New model. Allows users to override soft lock dates for specific users without changing the company's global lock date.

```python
class AccountLock_Exception(models.Model):
    _name = 'account.lock_exception'
    _description = "Account Lock Exception"
```

#### Core Fields (L1/L2)

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Active flag |
| `state` | Selection | `active`/`expired`/`revoked` (compute/search) |
| `company_id` | Many2one | Company (readonly, required) |
| `user_id` | Many2one | User (optional; null = all users) |
| `reason` | Char | Reason for exception |
| `end_datetime` | Datetime | Expiry datetime (optional; null = never expires) |
| `lock_date_field` | Selection | Which soft lock date is overridden |
| `lock_date` | Date | New lock date value |
| `company_lock_date` | Date | Original company lock date at exception creation |

#### Computed Lock Date Fields

`fiscalyear_lock_date`, `tax_lock_date`, `sale_lock_date`, `purchase_lock_date` are computed fields on the exception that return either the exception's `lock_date` (if this exception covers that field) or `date.max` (so the original company date takes effect for other fields).

#### State Compute (L3)

```python
def _compute_state(self):
    for record in self:
        if not record.active:
            record.state = 'revoked'
        elif record.end_datetime and record.end_datetime < self.env.cr.now():
            record.state = 'expired'
        else:
            record.state = 'active'
```

The `_search_state()` method translates searches into domain conditions on `active` and `end_datetime`.

#### Partial Index (L4)

```python
_company_id_end_datetime_idx = models.Index(
    "(company_id, user_id, end_datetime) WHERE active IS TRUE"
)
```

Indexes only active exceptions, enabling fast lookup for lock date resolution. Expired/revoked exceptions are excluded from the index since they are no longer relevant.

#### Lock Date Resolution (L4)

When checking if a user can post/reconcile on a given date, `res.company._get_user_lock_date()` is called:
1. Gets the company's soft lock date for the field
2. Searches `account.lock_exception` for matching `(company_id, user_id, active=True)` records
3. If an exception exists, its `lock_date` takes precedence over the company default
4. `end_datetime` allows time-limited overrides (e.g., "allow until Friday")

---

### 19. account.report / account.report.column / account.report.line (Financial Reports)

**File:** `odoo/addons/account/models/account_report.py`

#### account.report

Defines financial report templates with multiple engine types for computation.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Report name |
| `line_ids` | One2many | Report line definitions |
| `column_ids` | One2many | Column definitions (e.g., debit, credit, balance) |
| `root_report_id` | Many2one | Parent report for variants |
| `section_report_ids` | Many2many | Child section reports |
| `section_main_report_ids` | Many2many | Parent section relationships |
| `use_sections` | Boolean | Composite report (multiple sections) |

**Report engine types (line `engine_type`):**
- `tax_tags`: Uses `account.account.tag` to sum tagged tax lines
- `account_codes`: Uses account code patterns (prefix matching)
- `account_type`: Uses `account.account.account_type` filter
- `aggregation`: Formula-based aggregation of other lines
- `external_value`: Pulls data from another report
- `none`: Static text or empty

**L4 — Account code engine patterns:**
```python
ACCOUNT_CODES_ENGINE_SPLIT_REGEX = re.compile(r"'split\(([^)]+)\)'")
ACCOUNT_CODES_ENGINE_TERM_REGEX = re.compile(r"'domain\(([^)]+)\)'")
```

Lines can use `split()` to divide a single account range into sub-rows, or `domain()` to apply Odoo domain filters directly.

**L4 — Aggregation engine formula:**
```python
AGGREGATION_ENGINE_FORMULA_REGEX = re.compile(r"(?:(?!_|-|\+)).*\(([^)]+)\)")
```

Supports arithmetic formulas referencing other line codes: `line_A + line_B - line_C`.

---

### 20. account.code.mapping (Multi-Company Code Mapping)

**File:** `odoo/addons/account/models/account_code_mapping.py`

Stores per-company account codes for multi-company charts of accounts.

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | Many2one | `account.account` |
| `company_id` | Many2one | `res.company` |
| `code` | Char | Company-specific account code |

---

### 21. Partner Extensions

**File:** `odoo/addons/account/models/partner.py`

Extends `res.partner` with accounting fields:

| Field | Type | Description |
|-------|------|-------------|
| `property_account_receivable_id` | Many2one | Default AR account |
| `property_account_payable_id` | Many2one | Default AP account |
| `property_account_position_id` | Many2one | Default fiscal position |
| `property_payment_method_id` | Many2one | Preferred payment method |
| `invoice_warn` | Selection | Invoice warning level |
| `invoice_warn_msg` | Html | Warning message |
| `trusted_connector_ids` | Many2many | Peppol trusted endpoints |

---

### 22. Company Extensions

**File:** `odoo/addons/account/models/company.py`

Extends `res.company` with accounting configuration:

| Field | Type | Description |
|-------|------|-------------|
| `fiscalyear_lock_date` | Date | Global lock date |
| `tax_lock_date` | Date | Tax return lock date |
| `sale_lock_date` | Date | Sales lock date |
| `purchase_lock_date` | Date | Purchase lock date |
| `hard_lock_date` | Date | Hard lock (cannot be overridden) |
| `account_storno` | Boolean | Storno accounting enabled (computed from country) |
| `display_account_storno` | Boolean | Show storno option |
| `tax_calculation_rounding_method` | Selection | `round_globally` / `round_per_line` |
| `anglo_saxon_accounting` | Boolean | Anglo-Saxon (stock) accounting |
| `bank_account_code_prefix` | Char | Prefix for bank account codes |
| `cash_account_code_prefix` | Char | Prefix for cash account codes |
| `default_cash_difference_expense_account_id` | Many2one | Rounding loss account |
| `default_cash_difference_income_account_id` | Many2one | Rounding gain account |
| `account_sale_tax_id` | Many2one | Default sale tax |
| `account_purchase_tax_id` | Many2one | Default purchase tax |
| `currency_exchange_journal_id` | Many2one | Exchange difference journal |
| `tax_cash_basis_journal_id` | Many2one | CABA journal |

---

## Payment State Selection

| State | Description |
|-------|-------------|
| `not_paid` | Not Paid |
| `in_payment` | In Payment |
| `paid` | Paid |
| `partial` | Partially Paid |
| `reversed` | Reversed |
| `blocked` | Blocked |
| `invoicing_legacy` | Invoicing App Legacy |

---

## File Structure

```
account/
├── __manifest__.py                  # v1.4, depends: base_setup, onboarding, product, analytic, portal, digest
├── models/
│   ├── __init__.py
│   ├── account_move.py              # account.move (MAIN) — 3000+ lines
│   ├── account_move_line.py         # account.move.line — 2000+ lines
│   ├── account_journal.py             # account.journal + account.journal.group
│   ├── account_payment.py             # account.payment
│   ├── account_payment_method.py      # account.payment.method + account.payment.method.line
│   ├── account_account.py             # account.account + account.root + account.group
│   ├── account_account_tag.py        # account.account.tag
│   ├── account_tax.py                 # account.tax + account.tax.group + account.tax.repartition.line
│   ├── account_payment_term.py       # account.payment.term + account.payment.term.line
│   ├── account_reconcile_model.py    # account.reconcile.model + account.reconcile.model.line
│   ├── account_bank_statement.py     # account.bank.statement
│   ├── account_bank_statement_line.py # account.bank.statement.line
│   ├── account_full_reconcile.py     # account.full.reconcile
│   ├── account_partial_reconcile.py  # account.partial.reconcile
│   ├── account_cash_rounding.py       # account.cash.rounding
│   ├── account_incoterms.py           # account.incoterms
│   ├── account_analytic_plan.py     # account.analytic.plan, .account, .line
│   ├── account_analytic_distribution_model.py  # distribution template
│   ├── account_move_send.py           # invoice send wizard
│   ├── account_move_line_tax_details.py  # tax computation details
│   ├── account_chart_template.py     # chart of accounts template
│   ├── template_generic_coa.py       # generic COA template
│   ├── account_report.py             # financial reports
│   ├── account_lock_exception.py      # lock date exception (Odoo 18→19)
│   ├── account_code_mapping.py        # multi-company code mapping
│   ├── chart_template.py             # template loading
│   ├── account_document_import_mixin.py  # import mixin
│   ├── sequence_mixin.py             # number sequence mixin
│   ├── partner.py                    # res.partner extensions
│   ├── company.py                    # res.company extensions
│   ├── res_partner_bank.py           # res.partner.bank extensions
│   ├── res_config_settings.py        # settings view
│   ├── res_currency.py               # res.currency extensions
│   ├── product.py                    # product extensions
│   ├── product_catalog_mixin.py      # catalog mixin
│   ├── decimal_precision.py          # decimal.precision
│   ├── digest.py                    # digest extensions
│   ├── kpi_provider.py               # KPI provider
│   ├── res_users.py                  # res.users extensions
│   ├── ir_attachment.py             # ir.attachment extensions
│   ├── ir_actions_report.py         # ir.actions.report extensions
│   ├── ir_http.py                    # ir.http extensions
│   ├── ir_module.py                 # ir.module.extension
│   ├── mail_message.py               # mail.message extensions
│   ├── mail_template.py             # mail.template extensions
│   ├── mail_tracking_value.py       # tracking extensions
│   ├── merge_partner_automatic.py   # partner merge wizard
│   ├── onboarding_onboarding_step.py # onboarding
│   └── uom_uom.py                    # uom extensions
├── views/
│   ├── account_move_views.xml
│   ├── account_journal_views.xml
│   ├── account_account_views.xml
│   ├── account_tax_views.xml
│   ├── account_payment_view.xml
│   ├── account_bank_statement_views.xml
│   ├── account_reconcile_model_views.xml
│   └── ... (60+ XML files)
├── wizards/
│   ├── account_automatic_entry_wizard.py    # reversal / adjustment
│   ├── account_autopost_bills_wizard.py
│   ├── account_unreconcile_view.py
│   ├── account_move_reversal_view.py
│   ├── account_resequence_views.py
│   ├── account_payment_register_views.py
│   ├── account_validate_move_view.py
│   ├── setup_wizards_view.py
│   ├── account_move_send_wizard.py
│   ├── account_move_send_batch_wizard.py
│   ├── account_secure_entries_wizard.py
│   ├── accrued_orders.xml
│   └── account_merge_wizard_views.py
├── data/
│   ├── account_data.xml             # Default accounts, journals, taxes
│   ├── ir_sequence.xml
│   └── ... (30+ data files)
└── static/src/
    ├── js/
    ├── css/
    └── tests/
```

---

## Technical Notes

### Sequence Mixing

`account.move` inherits from `sequence.mixin`, supporting multiple sequence modes:
- Monthly / yearly sequences
- Custom prefix via `sequence_override_regex`
- Fixed sequences
- Sequence prefix can include `%(year)s`, `%(month)s`, `%(day)s`, `%(range_year)s`

The journal's `code` field serves as the sequence prefix (max 5 chars). Separate sequences for refunds (`refund_sequence=True`) and payments (`payment_sequence=True`) are supported.

### Multi-Company Domain

All models use `_check_company_domain = models.check_companies_domain_parent_of` and `_check_company_auto = True` to enforce company-based record isolation. The `_check_company_domain_parent_of` variant (used on journals) allows a child company to access parent company records.

The `_check_companies_domain_parent_of` variant (used on accounts) enforces strict company isolation — accounts cannot be shared between unrelated companies.

### Tax Cash Basis

Taxes can be configured as:
- **On Invoice**: Tax recognized when invoice is validated; goes directly to tax payable account
- **On Payment**: Tax recognized when payment is received; held in transition account until reconciliation

**Odoo 18→19 change:** The `tax_exigibility` field and CABA mechanism remained stable but the `always_tax_exigible` compute was added to optimize tax tag assignment — lines without AR/AP lines are marked always exigible even during invoice encoding.

### Hash-Based Immutability (Restrict Mode)

When `journal_id.restrict_mode_hash_table = True`:
- Posted entries cannot be modified
- Each entry has a hash chain (`inalterable_hash`) for audit trail
- Uses `secure_sequence_number` as gap-free counter
- Any modification raises `UserError`
- `button_hash()` wizard can retroactively hash entries
- Hash version support: `MAX_HASH_VERSION = 4` (Odoo tracks 4 hash algorithm versions for upgrade compatibility)

### Analytic Distribution

Stored as JSON on `account.move.line.analytic_distribution`:
```json
{"analytic_account_id_1": 40.0, "analytic_account_id_2": 60.0}
```
Percentages must sum to 100. Enforced via `_check_analytic_distribution()`.

**L4 — Inverse mechanism:** Writing to `analytic_distribution` triggers `_inverse_analytic_distribution()` which calls `_create_analytic_lines()` or `_update_analytic_lines()` to sync `account.analytic.line` records. Batch creation in `_post()` is a key performance optimization — `to_post.line_ids._create_analytic_lines()` creates all analytic lines for all posted moves in a single batch operation.

### Storno Accounting

Companies can enable `account_storno = True` to use Storno accounting (credits negate debits, no double-entry inversion). Affects:
- `move.is_storno`: Refunds negate normally unless company uses storno
- `line.is_storno`: Line-level storno flag for invoices
- `balance` computation: Inverts sign for storno lines

**Country lists (from `company.py`):**
- **STORNO_MANDATORY_COUNTRIES**: `BA`, `CN`, `CZ`, `HR`, `PL`, `RO`, `RS`, `RU`, `SI`, `SK`, `UA` — storno is automatically enabled
- **STORNO_OPTIONAL_COUNTRIES**: `AT`, `CH`, `DE`, `IT` — storno option is shown but not enforced

### Non-Deductible Tax (Odoo 18→19 Feature)

Lines can carry a `deductible_amount` field (default `100`). Values `< 100` create additional `non_deductible_tax` and `non_deductible_product_total` display-type lines splitting the tax/base into deductible and non-deductible portions.

### Peppol / EDI Integration

**Country lists (from `company.py`):**
- **PEPPOL_DEFAULT_COUNTRIES** (27): `AT`, `BE`, `CH`, `CY`, `CZ`, `DE`, `DK`, `EE`, `ES`, `FI`, `FR`, `GR`, `IE`, `IS`, `IT`, `LT`, `LU`, `LV`, `MT`, `NL`, `NO`, `PL`, `PT`, `RO`, `SE`, `SI` — Peppol enabled by default
- **PEPPOL_MAILING_COUNTRIES** (5): `BE`, `LU`, `NL`, `SE`, `NO` — Peppol footnote added to mail sent invoices
- **PEPPOL_LIST** (total 52): Includes DEFAULT + `AD`, `AL`, `BA`, `BG`, `BL`, `GB`, `GF`, `GP`, `HR`, `HU`, `LI`, `MC`, `ME`, `MF`, `MK`, `MQ`, `NC`, `PF`, `PM`, `RE`, `RS`, `SK`, `SM`, `TF`, `TR`, `VA`, `WF`, `YT`

**Journal Peppol fields:**
- `show_fetch_in_einvoices_button`: Show "Fetch E-Invoices" button on journal
- `show_refresh_out_einvoices_status_button`: Show "Refresh Out E-Invoices Status" button
- `incoming_einvoice_notification_email`: Email address for routing incoming Peppol documents

---

## L4 Performance Considerations

### Batch Processing
- Analytic line creation is batched in `_post()` for all posted moves
- Tax computation (`_get_rounded_base_and_tax_lines`, `_prepare_tax_lines`) processes base lines together
- Balance computation on `account.account` uses `_read_group` aggregation over `account.move.line`
- Full reconciliation creation uses `cr.execute_values()` with `page_size=1000` to batch-update `full_reconcile_id` on AML and partials in single SQL statements
- Tax uniqueness constraint splits records into batches of 100

### Database Indexes
- `_unreconciled_index` partial index: only unreconciled lines are indexed on `(account_id, partner_id)` — critical for bank reconciliation performance
- `_journal_id_neg_amnt_residual_idx` partial index: only lines with negative residual for dashboard queries
- `_made_gaps` partial index: only gaps are indexed for fast gap detection
- Multi-column indexes on `(date, move_name, id)` and `(partner_id, ref)` for reconciliation widget
- `_checked_idx` partial index: only unchecked lines per journal

### CABA Performance
- Cash basis tax entries are generated lazily on reconciliation, not on invoice posting
- The `_collect_tax_cash_basis_values()` method avoids generating CABA entries if there are no payable/receivable lines
- CABA entries are reversed in bulk when partial reconciliations are deleted

### Sequence Gap Detection
- `made_sequence_gap` is computed using a SQL query checking sequence numbers minus 1 against known numbers — only stored if `True`
- The `_made_gaps` partial index enables fast gap detection across large move tables

### Reconciliation Algorithm Complexity
- `_update_matching_number()` is O(n log n) where n = number of partials in affected graphs, due to the union-find pattern with sorted iteration
- The `bisect_left` in `_get_closest_parent_account()` makes account type assignment O(log n) per account instead of O(n)

---

## L4 Security Considerations

### Field-Level Access
- `invoice_outstanding_credits_debits_widget`, `invoice_payments_widget`: restricted to `account.group_account_invoice` and `account.group_account_readonly`
- `partner_credit_warning`: restricted to same groups
- `account_move__account_payment` many2many relation: controls access to payment-to-invoice matching

### Lock Date Hierarchy (L4)

**Hard locks vs soft locks:**
- **Soft locks** (`fiscalyear_lock_date`, `tax_lock_date`, `sale_lock_date`, `purchase_lock_date`): Can be overridden per-user via `account.lock.exception` records
- **Hard lock** (`hard_lock_date`): Absolute, cannot be overridden. `_check_fiscal_lock_dates()` only checks `hard_lock_date` — not soft locks directly

**`account.lock.exception` flow:**
1. Admin creates exception: sets a different lock date for a specific user or all users
2. `_compute_lock_dates()` on the exception returns `date.max` for non-matching fields so other lock dates are unaffected
3. `res.company._get_user_lock_date()` queries both the company field and active exceptions to find the effective lock date

**BYPASS_LOCK_CHECK sentinel:** `BYPASS_LOCK_CHECK = object()` (module-level singleton) is the canonical safe way to bypass all lock checks. Pass `self.with_context(bypass_lock_check=BYPASS_LOCK_CHECK)` to any write/post operation.

### Audit Trail
- `inalterable_hash`: SHA-256 hash chain ensuring entry integrity
- `secure_sequence_number`: Gap-free sequence for hash chain ordering
- `audit_trail_message_ids`: `mail.message` records with `message_type = 'notification'` for audit log
- `mail.tracking.value` on tracked fields (tax repartition lines, amounts)
- `INTEGRITY_HASH_BATCH_SIZE = 1000`: Hash chain updates are processed in batches of 1000 using a Postgres cursor to avoid memory exhaustion on large journals

### Odoo 18→19 Security Changes
- `mail.thread` replaced with `mail.thread.main.attachment` — reduces notification overhead
- `account.lock.exception` model provides auditable, time-limited lock date overrides instead of direct database edits
- Trusted Peppol endpoints stored in `res.partner.trusted_connector_ids` for secure EDI routing

---

**Source Module**: `odoo/addons/account`
**Last Updated**: 2026-04-11
