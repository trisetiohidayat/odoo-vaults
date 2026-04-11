---
Module: account_accountant
Version: Odoo 18 (Enterprise)
Type: Integration
---

# Accounting Enhancements (`account_accountant`)

Enterprise-grade accounting features: bank reconciliation widget, reconciliation models with advanced matching rules, automatic/manual reconciliation wizards, deferred expense/revenue management, lock date controls with exceptions, and invoicing switch threshold.

**Depends:** `account`, `mail_enterprise`, `web_tour`
**Category:** Accounting/Accounting
**Auto-install:** True (with `account`, `mail_enterprise`)
**Source:** `~/odoo/enterprise/18.0-20250812/enterprise/account_accountant/`

---

## Models

### `bank.rec.widget` — Bank Reconciliation Widget

Transient model (`_auto=False`). Provides a live reconciliation interface for a single bank statement line.

> This model is never persisted. `_auto=False` and `_table_query = "0"` prevent PostgreSQL table creation.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `st_line_id` | Many2one | The `account.bank.statement.line` being reconciled |
| `move_id` | Many2one | Related `account.move` from the statement line |
| `st_line_checked` | Boolean | Related from statement line's `move_id.checked` |
| `st_line_is_reconciled` | Boolean | Whether the statement line is fully reconciled |
| `st_line_journal_id` | Many2one | Statement line's journal |
| `st_line_transaction_details` | Html | Computed transaction metadata display |
| `transaction_currency_id` | Many2one | Currency of the statement line |
| `journal_currency_id` | Many2one | Currency of the journal |
| `company_currency_id` | Many2one | Company's default currency |
| `company_id` | Many2one | Company from statement line |
| `partner_id` | Many2one | Partner set on the wizard |
| `method_id` | Many2one | Reconciliation method |
| `available_method_id` | Many2one | Currently selected method |
| `form_index` | Char | Index of the currently edited line (controls `_compute_*` for that line) |
| `state` | Selection | `'valid'`, `'reconciled'`, `'invalid'`, `'cancelled'` |

#### Key Methods

**`_compute_st_line_transaction_details()`** — Builds HTML display of transaction metadata from the statement line.

**`_compute_transaction_currency_id()`** — Resolves to: foreign currency (if set on ST line) else journal's currency else company's currency.

**`_load_wizard_line()`** — Loads existing AMLs linked to the statement line's move (from previous partial reconciliations) and appends them as `bank.rec.widget.line` records.

**`_action_reconcile()`** — Main reconciliation action. Orchestrates:
1. Validates all wizard lines
2. Detects which lines have changed (`manually_modified`)
3. Creates/updates AMLs on the statement move
4. Reconciles with counterpart AMLs
5. Handles exchange difference entries
6. Updates the statement line's `is_reconciled` state

**`_create_write_off(lines)`** — Creates a write-off journal entry for the current set of wizard lines. Uses `account.reconcile.wizard` logic.

**`_check_aml_propositions(wizard_lines)`** — Validates that the sum of debit and credit columns balances (zero out the difference).

**`_attempt_autoreconcile()`** — Applies reconciliation models (`account.reconcile.model`) to find matching AMLs for unreconciled lines.

**`_get_reconciliation_proposition(st_line)`** — Returns suggested AMLs from reconciliation models for a given statement line.

**`_get_statement_line_for_reconciliation(st_line)`** — Prepares the statement line with resolved partner and currency.

#### L4 Notes

- The `form_index` field drives compute method behavior. Lines whose `index == form_index` get their `_compute_*` methods applied to them in the UI context.
- `available_method_id` is a dynamic method that changes based on the context (bank rec widget vs. manual reconciliation).
- The wizard uses `manually_modified` flag to distinguish user-edited lines from auto-suggested ones.

---

### `bank.rec.widget.line` — Bank Reconciliation Widget Line

Transient model (`_auto=False`). Represents a single line (source AML or manually added) in the bank reconciliation widget.

> Never persisted. Computed and editable per-session.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `wizard_id` | Many2one | Parent `bank.rec.widget` |
| `flag` | Selection | Type of line: `liquidity`, `new_aml`, `aml`, `exchange_diff`, `tax_line`, `manual`, `early_payment`, `auto_balance` |
| `account_id` | Many2one | Account (computed from `source_aml_id` or editable) |
| `date` | Date | Effective date |
| `name` | Char | Line label |
| `partner_id` | Many2one | Partner |
| `currency_id` | Many2one | Foreign currency |
| `amount_currency` | Monetary | Amount in foreign currency |
| `balance` | Monetary | Amount in company currency |
| `debit` | Monetary | Debit (computed from `balance > 0`) |
| `credit` | Monetary | Credit (computed from `balance < 0`) |
| `source_aml_id` | Many2one | Source AML for `aml`/`new_aml` flags |
| `tax_repartition_line_id` | Many2one | Tax repartition line for tax lines |
| `tax_ids` | Many2many | Taxes on the line |
| `tax_tag_ids` | Many2many | Tags for tax accounting |
| `reconcile_model_id` | Many2one | Model that suggested this line |
| `analytic_distribution` | Json | Analytic distribution (mixin field) |
| `source_amount_currency` | Monetary | Original amount from source AML |
| `source_balance` | Monetary | Original balance from source AML |
| `source_rate` | Float | Exchange rate of the source transaction |
| `display_stroked_amount_currency` | Boolean | Show amount discrepancy in foreign currency |
| `display_stroked_balance` | Boolean | Show balance discrepancy |
| `suggestion_html` | Html | Suggestion text for amount matching |
| `suggestion_amount_currency` | Monetary | Suggested amount in foreign currency |
| `suggestion_balance` | Monetary | Suggested amount in company currency |
| `manually_modified` | Boolean | User has edited this line |

#### Key Methods

**`_compute_suggestion()`** — Generates HTML suggesting full or partial reconciliation:
- For fully reconciled: "Invoice X with open amount Y will be entirely paid"
- For partial: suggests partial payment or partial reconciliation
- Includes buttons to apply the suggestion

**`_compute_analytic_distribution()`** — For `liquidity`/`aml` flags: copies from `source_aml_id`. For others: applies `account.analytic.distribution.model` rules based on partner/account/company.

**`_get_aml_values(**kwargs)`** — Returns a dict of AML field values for writing to the actual `account.move.line`. Used when the widget creates real journal entries.

#### L4 Notes

- `flag` determines which compute methods populate the fields. For example, `liquidity` lines pull from the statement line's data; `aml` lines pull from the matched AML.
- `suggestion_html` shows a helper message to the user when the matched AML amount differs from the ST line amount.
- The widget creates real `account.move.line` records on the statement's `account.move` via `bank_move_line_ids`.

---

### `account.move` (EXTENDED — Deferred Management)

Adds deferred expense/revenue journal entry tracking to `account.move`.

#### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `deferred_move_ids` | Many2many | Entries created from this invoice's deferral plan |
| `deferred_original_move_ids` | Many2many | Original invoices that created deferred entries from this move |
| `deferred_entry_type` | Selection | `'expense'` or `'revenue'` |
| `payment_state_before_switch` | Char | Caches previous `payment_state` when switching invoicing mode |

#### Key Methods

**`_check_fiscalyear_lock_date()`** — Extended to account for deferred journal entries that may need to be posted after the lock date.

**`_check_tax_lock_date()`** — Extended with deferred management checks.

**`_get_fiscal_year_dates_to_lock()`** — Returns a list of date ranges that should be locked based on deferred entry configurations.

---

### `account.reconcile.model` (EXTENDED)

Extends `account.reconcile.model` with enhanced bank reconciliation matching logic.

#### Key Methods

**`_apply_lines_for_bank_widget(residual_amount_currency, partner, st_line)`** — Applies reconciliation model lines to a statement line in the bank widget. Iterates model lines, computes `amount_currency` per line, subtracts from residual, returns vals list.

**`_apply_rules(st_line, partner)`** — Main entry point for bank reconciliation. Iterates all models sorted by `sequence`. For each applicable model:
- `invoice_matching`: calls `_get_invoice_matching_rules_map()` to find candidates
- `writeoff_suggestion`: returns write-off status

Returns dict with `amls`, `model`, `status`, `auto_reconcile`.

**`_is_applicable_for(st_line, partner)`** — Checks if model applies to a given statement line. Filters on:
- `match_journal_ids`
- `match_nature`: `'amount_received'` or `'amount_paid'`
- `match_amount`: `'lower'`, `'greater'`, `'between'` with min/max
- `match_partner`: requires partner to be set
- `match_text_location_*`: label/note/reference text matching

**`_get_invoice_matching_amls_candidates(st_line, partner)`** — Finds AMLs matching a statement line. Uses two strategies:
1. **Text-based matching**: Tokenizes payment_ref/narration/ref to find AMLs with matching text tokens (requires PostgreSQL `unnest` + `regexp_split_to_array`). Tokens must be at least 4 characters.
2. **Amount matching**: For each candidate AML, looks for exact balance match in the same currency.

Returns `{'amls': ..., 'allow_auto_reconcile': bool}`.

**`_get_invoice_matching_st_line_tokens(st_line)`** — Tokenizes statement line text into:
- `numerical_tokens`: digits-only tokens (>= 4 chars)
- `exact_tokens`: full text + word tokens (>= 4 chars)
- `text_tokens`: alphanumeric tokens

**`_get_invoice_matching_rules_map()`** — Returns priority map of matching rules. Priority 10: `_get_invoice_matching_amls_candidates`.

**`_check_rule_propositions(st_line, amls_values_list)`** — Validates that a batch of AMLs satisfies payment tolerance rules:
- Zero tolerance → `rejected`
- Fixed tolerance: residual ≤ tolerance → `allow_write_off, allow_auto_reconcile`
- Percentage tolerance: residual% ≤ tolerance% → `allow_write_off, allow_auto_reconcile`

**`_get_partner_from_mapping(st_line)`** — For `invoice_matching` or `writeoff_suggestion` models: matches statement line against `partner_mapping_line_ids` using regex on `payment_ref` and `narration`.

**`run_auto_reconciliation()`** — Triggers cron-based auto-reconciliation with a 3-minute time limit.

#### L4 Notes

- When no partner is identified, the matching algorithm tries to match by amount AND currency. When a partner is set, it returns all unreconciled AMLs for that partner sorted by date.
- The `match_text_location_*` fields allow matching on `payment_ref` (label), `narration` (note), and `ref` (reference).
- Auto-reconciliation is allowed only when text tokens produce a match (exact or numerical). Pure amount matching without text does not trigger auto-reconciliation.

---

### `account.reconcile.model.line` (EXTENDED)

Extends `account.reconcile.model.line` with the bank widget's write-off line generation.

#### Key Methods

**`_apply_in_bank_widget(residual_amount_currency, partner, st_line)`** — Generates AML vals for bank reconciliation:
- `percentage_st_line`: percentage of the statement line amount (or journal amount, depending on model type)
- `regex`: extracts amount from payment_ref using regex named group
- Applies fiscal position for taxes
- Sets `analytic_distribution`, `tax_ids`, `reconcile_model_id`

---

### `res.company` (EXTENDED)

#### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `invoicing_switch_threshold` | Date | Entries before this date are marked `invoicing_legacy` |
| `predict_bill_product` | Boolean | Enable AI prediction of vendor bill products |
| `sign_invoice` | Boolean | Display signing field on invoices |
| `signing_user` | Many2one | User whose signature is used for all invoices |
| `deferred_expense_journal_id` | Many2one | Journal for deferred expense entries |
| `deferred_expense_account_id` | Many2one | Default account for deferred expenses |
| `deferred_revenue_journal_id` | Many2one | Journal for deferred revenue entries |
| `deferred_revenue_account_id` | Many2one | Default account for deferred revenues |
| `generate_deferred_expense_entries_method` | Selection | `'on_validation'` or `'manual'` |
| `deferred_expense_amount_computation_method` | Selection | `'day'`, `'month'`, `'full_months'` |
| `generate_deferred_revenue_entries_method` | Selection | `'on_validation'` or `'manual'` |
| `deferred_revenue_amount_computation_method` | Selection | `'day'`, `'month'`, `'full_months'` |

#### Key Methods

**`write(vals)`** — When `invoicing_switch_threshold` changes:
- If new threshold set: cancels all posted moves before the threshold (marking them `invoicing_legacy`) and re-posts moves after the threshold that were previously `invoicing_legacy`
- SQL queries update `account_move` and `account_move_line` tables directly

**`compute_fiscalyear_dates(current_date)`** — Overrides to look up `account.fiscal.year` records first, then falls back to computed fiscal year from `fiscalyear_last_day/month`.

---

### `res.config.settings` (EXTENDED)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `fiscalyear_last_day` | Integer | Last day of fiscal year (related to company) |
| `fiscalyear_last_month` | Selection | Last month of fiscal year |
| `use_anglo_saxon` | Boolean | Anglo-Saxon accounting (related) |
| `invoicing_switch_threshold` | Date | Invoicing switch threshold |
| `group_fiscal_year` | Boolean | Enable fiscal year records (`implied_group`) |
| `predict_bill_product` | Boolean | Enable AI bill product prediction |
| `sign_invoice` | Boolean | Enable invoice signing |
| `signing_user` | Many2one | Signature user |
| `module_sign` | Boolean | Computed: sign module status |
| `deferred_expense_journal_id` | Many2one | Deferred expense journal |
| `deferred_expense_account_id` | Many2one | Deferred expense account |
| `deferred_revenue_journal_id` | Many2one | Deferred revenue journal |
| `deferred_revenue_account_id` | Many2one | Deferred revenue account |
| `generate_deferred_expense_entries_method` | Selection | Deferred expense generation method |
| `deferred_expense_amount_computation_method` | Selection | Deferred expense computation basis |
| `generate_deferred_revenue_entries_method` | Selection | Deferred revenue generation method |
| `deferred_revenue_amount_computation_method` | Selection | Deferred revenue computation basis |

#### Key Methods

**`_check_fiscalyear()`** — Validates that the fiscal year date exists (checks in leap year 2020). Applied via `@api.constrains`.

**`create(vals_list)`** — Batches `fiscalyear_last_day` and `fiscalyear_last_month` writes to company to prevent constraint failure from sequential single-field writes.

---

### `account.account` (EXTENDED)

#### Methods

**`action_open_reconcile()`** — Opens the posted-unreconciled move lines view filtered to this account. Builds domain from `account.action_move_line_posted_unreconciled`.

---

### `account.chart.template` (EXTENDED)

#### Methods

**`_get_account_accountant_res_company(chart_template)`** — Returns company data for deferred journals/accounts during chart template installation. Looks up deferred journal IDs from chart template data and falls back to first general journal / first `asset_current` account.

**`_get_chart_template_data(chart_template)`** — Overrides to inject default `deferred_expense_journal_id`, `deferred_revenue_journal_id`, `deferred_expense_account_id`, `deferred_revenue_account_id` into `res.company` template data.

---

## Wizards

### `account.change.lock.date` — Change Lock Date Wizard

Controls lock dates with support for time-limited exceptions.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `fiscalyear_lock_date` | Date | "Lock Everything" date |
| `tax_lock_date` | Date | "Lock Tax Return" date |
| `sale_lock_date` | Date | "Lock Sales" date |
| `purchase_lock_date` | Date | "Lock Purchases" date |
| `hard_lock_date` | Date | Irreversible lock date |
| `fiscalyear_lock_date_for_me` | Date | Earliest active exception for current user |
| `fiscalyear_lock_date_for_everyone` | Date | Earliest active exception for all users |
| `exception_applies_to` | Selection | `'me'` or `'everyone'` |
| `exception_duration` | Selection | `'5min'`, `'15min'`, `'1h'`, `'24h'`, `'forever'` |
| `exception_reason` | Char | Reason for the exception |
| `show_draft_entries_warning` | Boolean | Draft entries exist in locked period |

#### Key Methods

**`_compute_lock_date_exceptions()`** — Looks up `account.lock_exception` records with active `end_datetime > now` for each lock date field. Computes the minimum exception date for current user (`_for_me`) and all users (`_for_everyone`).

**`_prepare_lock_date_values(exception_vals_list=None)`** — Returns dict of changed lock date fields. Raises `UserError` if attempting to decrease or remove `hard_lock_date`.

**`_prepare_exception_values()`** — Creates `account.lock_exception` records for time-limited lock date overrides. Handles durations via `end_datetime`. Does not create exceptions for `'everyone'` + `'forever'` (those are normal changes).

**`change_lock_date()`** — Creates exceptions if needed, then writes lock dates to company. Requires `account.group_account_manager`.

**`_get_draft_moves_in_locked_period_domain()`** — Returns domain for draft moves that fall within any locked period. Used for the warning banner.

#### L4 Notes

- The `hard_lock_date` is irreversible: it can only be increased, never decreased or removed.
- Lock exceptions (`account.lock_exception`) allow temporary overrides of soft locks (fiscal year, tax, sale, purchase). They are searched by `_get_active_exceptions_domain` which filters on `end_datetime > now` and `state = 'open'`.
- The wizard can revoke exceptions via action buttons: `action_revoke_min_*_exception_for_me` and `action_revoke_min_*_exception_for_everyone`.

---

### `account.auto.reconcile.wizard` — Automatic Reconciliation Wizard

Batch-reconciles AMLs using two strategies.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `line_ids` | Many2many | Source AMLs for preset generation |
| `from_date` | Date | Start of reconciliation period |
| `to_date` | Date | End of reconciliation period |
| `account_ids` | Many2many | Accounts to reconcile (only `reconcile=True`, non-deprecated) |
| `partner_ids` | Many2many | Partners to include |
| `search_mode` | Selection | `'one_to_one'` (perfect match) or `'zero_balance'` (clear account) |

#### Methods

**`_get_amls_domain()`** — Builds domain for reconcilable AMLs:
- `parent_state = 'posted'`
- `display_type` not in sections/notes
- `date` within range
- `reconciled = False`
- `account_id.reconcile = True`
- `amount_residual != 0` (excludes exchange diff lines)
- Filters by `account_ids` and `partner_ids` if provided

**`_auto_reconcile_one_to_one()`** — Pairs positive AMLs with negative AMLs by (account, partner, currency, abs residual amount). Reconciles pairs with exact opposite amounts.

**`_auto_reconcile_zero_balance()`** — Groups AMLs by (account, partner, currency) and reconciles all groups where the total residual is zero.

**`auto_reconcile()`** — Executes the appropriate strategy and returns the reconciled AMLs (plus exchange diff related lines) in a list view.

---

### `account.reconcile.wizard` — Manual Reconciliation Wizard

Reconciles selected AMLs with optional transfer and/or write-off entries.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `move_line_ids` | Many2many | AMLs selected for reconciliation |
| `reco_account_id` | Many2one | The account to use for reconciliation |
| `amount` | Monetary | Total amount in company currency |
| `amount_currency` | Monetary | Total amount in foreign currency |
| `reco_currency_id` | Many2one | Currency used for reconciliation |
| `allow_partials` | Boolean | Allow partial reconciliation |
| `is_write_off_required` | Boolean | A write-off entry is needed to balance |
| `is_transfer_required` | Boolean | A transfer between accounts is needed |
| `date` | Date | Date for write-off/transfer entry |
| `journal_id` | Many2one | General journal for write-off |
| `account_id` | Many2one | Write-off account |
| `label` | Char | Label for the write-off entry |
| `tax_id` | Many2one | Tax to apply to write-off |
| `to_check` | Boolean | Mark reconciled entries to check |
| `reco_model_id` | Many2one | Selected reconciliation model (writeoff_button type) |

#### Methods

**`_compute_reco_wizard_data()`** — Core computation: determines currency, account, transfer data, and write-off amounts. Uses `_optimize_reconciliation_plan` to batch AMLs. Handles multi-currency by computing residual amounts in reconciliation currency.

**`_compute_write_off_taxes_data(partner)`** — Uses `account.tax._prepare_base_line_for_taxes_computation` to compute tax lines for the write-off entry. Handles `special_mode='total_included'`.

**`_create_write_off_lines(partner=None)`** — Generates `Command.create` list for write-off entry:
- Line 1: counterparty (to `reco_account_id`) with `-amount`
- Line 2: write-off (`account_id`) with `+amount` (or base + tax lines if tax set)

**`create_write_off()`** — Creates and posts the write-off move. Returns the move.

**`create_transfer()`** — Creates a transfer move between two accounts (when reconciling across different receivable/payable accounts). Splits by partner and currency to keep partner ledger accurate.

**`reconcile()`** — Orchestrates: optionally creates transfer, optionally creates write-off, then calls `_reconcile_plan` on the AML set. Returns reconciled lines.

#### L4 Notes

- `is_transfer_required` is True when the two AMLs are on different accounts. The wizard creates an intermediate transfer move to bring them to the same account before reconciling.
- `edit_mode` is enabled when only one AML is selected. Allows editing the write-off amount.
- The wizard detects lock date violations and auto-adjusts the entry date to the first date after the lock.
- `reco_model_autocomplete_ids` finds `writeoff_button` models with exactly one line (excluding sale/purchase counterpart types).

---

## Reconciliation Enhancement Details

### Payment Tolerance

`account.reconcile.model` supports `payment_tolerance_type` (`fixed_amount` or `percentage`) and `payment_tolerance_param`. When a statement line nearly matches an invoice (within tolerance), the system allows the match and generates a write-off for the difference.

### Text-Based Matching Priority

The bank reconciliation matching algorithm prioritizes rules by `sequence`. Within a rule, text token matching (requiring PostgreSQL `regexp_split_to_array`) produces candidates that enable **auto-reconciliation**. Amount-only matching without text does not auto-reconcile.

### Analytic Distribution and Reinvoice

`account.move.line._sale_determine_order()` is extended to map AMLs to SOs via the project's analytic account. When a stock move creates an analytic entry (for a reinvoicing picking), the AML is matched to the project's SO for automatic reinvoicing.

---

**Tags:** `#account_accountant` `#bank_reconciliation` `#reconciliation_models` `#deferred_management` `#lock_dates`
