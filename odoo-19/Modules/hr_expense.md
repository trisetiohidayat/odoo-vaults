---
tags:
  - odoo
  - odoo19
  - modules
  - hr
  - accounting
  - expense
  - payroll
---

# hr_expense — Employee Expense Management

**Module:** `hr_expense`
**Version:** 2.1
**Category:** Human Resources/Expenses
**Depends:** `account`, `web_tour`, `hr`
**Author:** Odoo S.A.
**License:** LGPL-3
**Application:** True

---

## Overview

The `hr_expense` module manages employee expense claims end-to-end: from submission through approval, accounting entry creation, to reimbursement payment. It integrates with `account` for journal entries, `hr` for employee/manager data, `product` for expense categories, and `analytic` for cost allocation. The module supports email-based expense submission via mail gateway, Stripe company card integration (`hr_expense_stripe`), and OCR-based receipt digitization (`hr_expense_extract`).

> **Odoo 19 breaking change:** `hr.expense.sheet` was entirely removed. The primary unit is individual `hr.expense` records. `former_sheet_id` (Integer) is retained for migration compatibility. The XML workflow engine was replaced with explicit Python `action_*` methods.

---

## Module Architecture

```
hr_expense/
├── models/
│   ├── hr_expense.py          # Core: hr.expense model + workflow
│   ├── hr_employee.py         # expense_manager_id on hr.employee
│   ├── hr_department.py       # expenses_to_approve_count
│   ├── account_move.py        # account.move extensions
│   ├── account_move_line.py   # expense_id on account.move.line
│   ├── account_payment.py     # account.payment extensions
│   ├── account_tax.py         # Tax computation hooks
│   ├── analytic.py            # Analytic applicability + unlink protection
│   ├── product_product.py     # standard_price update warnings
│   ├── product_template.py    # can_be_expensed flag
│   ├── res_company.py         # expense_journal_id, payment methods
│   ├── res_config_settings.py  # Settings page
│   └── ir_actions_report.py   # PDF report attachment merging
├── wizard/
│   ├── hr_expense_split.py         # hr.expense.split (transient line model)
│   ├── hr_expense_split_wizard.py  # hr.expense.split.wizard
│   ├── hr_expense_refuse_reason.py # hr.expense.refuse.wizard
│   ├── hr_expense_post_wizard.py   # hr.expense.post.wizard
│   ├── hr_expense_approve_duplicate.py  # hr.expense.approve.duplicate
│   └── account_payment_register.py # account.payment.register extensions
├── security/
│   ├── hr_expense_security.xml  # Groups: Team Approver, All Approver, Administrator
│   ├── ir_rule.xml              # Record rules per group
│   └── ir.model.access.csv      # ACL per group
├── data/
│   ├── hr_expense_data.xml      # Demo products (Meals, Travel, Mileage, Gifts, Communication)
│   ├── hr_expense_sequence.xml  # ir.sequence: EXP/ prefix
│   ├── hr_expense_cron.xml      # Weekly submitted-expenses email cron
│   └── mail_*.xml               # Aliases, activity types, templates
└── views/
    └── ...                      # Form, list, kanban, search, dashboard views
```

---

## Security Groups

Defined in `security/hr_expense_security.xml` with a four-level inheritance chain:

| Group | ID | Implied Groups | Core Rights |
|---|---|---|---|
| Employee | `base.group_user` | — | Submit own drafts; edit own drafts only |
| Team Approver | `group_hr_expense_team_approver` | `base.group_user` | View team expenses; approve/refuse; read `account.move` |
| All Approver | `group_hr_expense_user` | `group_hr_expense_team_approver` | Cross-department approval; write non-posted |
| Administrator | `group_hr_expense_manager` | `group_hr_expense_user` | Unrestricted; edit `analytic_distribution` |

### Record Rules (`security/ir_rule.xml`)

**`ir_rule_hr_expense_manager`** — global scope for `account.group_account_user` + `group_hr_expense_user`: full CRUD `[1,1,1,1]`.

**`ir_rule_hr_expense_approver`** (`group_hr_expense_team_approver`):
```
['|', '|', '|', '|',
    ('employee_id.user_id', '=', user.id),                          # own expense
    ('employee_id.department_id.manager_id.user_id', '=', user.id), # dept manager
    ('employee_id', 'child_of', user.employee_ids.ids),            # subordinates
    ('employee_id.expense_manager_id', '=', user.id),              # designated approver
    ('manager_id', '=', user.id)]                                  # explicit manager
```

**`ir_rule_hr_expense_employee`** (`base.group_user`): read all; write draft only for own employee.

**`ir_rule_hr_expense_employee_not_draft`** (`base.group_user`): blocks write/unlink on non-draft own expenses (perm_create=False, perm_write=False, perm_unlink=False).

**`hr_expense_comp_rule`** — global multi-company rule: `company_id in company_ids`.

**`hr_expense_team_approver_account_move_rule`** — grants `group_hr_expense_team_approver` read access to `account.move` where `expense_ids` is not empty.

**`hr_expense_team_approver_account_move_line_rule`** — grants read access to `account.move.line` where `expense_id` is set.

**Split wizard rules** — five rules on `hr.expense.split.wizard` tied to expense state and approver relationship, ranging from employee-only (draft, own/manager) to accountant (up to approved state).

---

## Core Model: `hr.expense`

**File:** `models/hr_expense.py`
**Inherits:** `mail.thread.main.attachment`, `mail.activity.mixin`, `analytic.mixin`
**`_name`:** `hr.expense`
**`_check_company_auto`:** `True`
**`_order`:** `date desc, id desc`

### Field Definitions

#### Identity Fields

**`name`** (`Char`, computed/store/precompute, `copy=True`, `required=True`)
- Default: `product_id.display_name`. Overridable by user before submission. Used as the first 64 characters of account move line labels via `_get_move_line_name()`.

**`date`** (`Date`, default=`context_today`)
- Drives `currency_rate` computation. Used as the accounting date if not overridden by the post wizard.

**`employee_id`** (`Many2one(hr.employee)`, required, `check_company=True`, domain=`[('filter_for_expense', '=', True)]`)
- **L2:** `default=_default_employee_id` raises `ValidationError` if no linked employee AND user lacks `group_hr_expense_team_approver` (this allows config officers to create expenses for employees).
- **L3:** Domain `filter_for_expense` uses a custom `search()` on `hr.employee`: regular employees see only themselves; Team Approvers see their subordinates and those where they are `expense_manager_id`; All Approvers see all in their company.

**`department_id`** (`Many2one(hr.department)`, computed from `employee_id`, `store=True`)
- **L3:** Used in `_compute_expenses_to_approve_count` on `hr.department`.

**`manager_id`** (`Many2one(res.users)`, computed/store, `tracking=True`)
- **L2:** Domain restricts to non-share users who are either `expense_manager_id` on some employee or members of `group_hr_expense_team_approver`.
- **L3:** Cascade chain in `_get_default_responsible_for_approval`: `expense_manager_id` → `department_id.manager_id` → `parent_id.user_id` (team leader). Each step excludes the employee themselves. Written automatically by `action_submit()` if empty.

**`company_id`** (`Many2one(res.company)`, required, readonly, `default=lambda self: self.env.company`)
- **L3:** All company-dependent computations scope to this field. `_check_company_auto=True` enforces company-scoping on all `check_company` fields.

**`product_id`** (`Many2one(product.product)`, domain=`[('can_be_expensed', '=', True)]`, `ondelete='restrict'`)
- **L2:** Not required on the model (enables mail-gateway creation without a product), but enforced on the view. `ondelete='restrict'` prevents product deletion while linked.
- **L3:** Changing product cascades through `_compute_tax_ids` (re-derives from `product_id.supplier_taxes_id`), `_compute_account_id`, `_compute_from_product`, and `_compute_analytic_distribution`. Does NOT reset `quantity` to 1 — that only happens via `_onchange_product_has_cost`.

**`product_description`** (`Html`, computed from `product_id.description`)

**`product_uom_id`** (`Many2one(uom.uom)`, computed from `product_id.uom_id`, `store=True`, `copy=True`)
- Drives the `product_uom_id` on move lines.

**`product_has_cost`** (`Boolean`, computed)
- True when `product_id` exists and `standard_price != 0`. Determines whether `_needs_product_price_computation()` is True and whether `currency_id` resets to `company_currency_id` on product change.

**`product_has_tax`** (`Boolean`, computed)
- True when `product_id.supplier_taxes_id` filtered by company is non-empty.

**`quantity`** (`Float`, required, default=`1`, digits=`Product Unit`)
- Only meaningful when `product_has_cost` is True. Resets to 1 via `_onchange_product_has_cost` when switching from cost to no-cost product.

**`description`** (`Text`, string="Internal Notes")
- Not copied to accounting entries. Internal annotations only.

#### Amount Fields (all `Monetary`)

**`total_amount_currency`** (`Monetary`, `currency_field='currency_id'`, computed/inverse, `store=True`, `precompute=True`, `tracking=True`)
- **L2:** When `product_has_cost`: computed as tax-inclusive total from `price_unit * quantity` via `_compute_total_amount_currency`. When NOT `product_has_cost`: editable via inverse `_inverse_total_amount_currency`, which sets `price_unit = total_amount / quantity`. Blocked when `is_editable = False`.
- **L3:** Changing this triggers `_compute_currency_rate` when currency, amount, or date changes from origin values.

**`total_amount`** (`Monetary`, `currency_field='company_currency_id'`, computed/inverse, `store=True`, `precompute=True`, `tracking=True`)
- **L2:** Multi-currency: `total_amount = total_amount_currency * currency_rate`. Mono-currency: equals `total_amount_currency`. Inverse `_inverse_total_amount` recalculates `currency_rate = total_amount / total_amount_currency` and `price_unit = total_amount / quantity`.
- **L3:** This is the amount recorded on the accounting entry. Manual `currency_rate` override allows locking the exchange rate.

**`untaxed_amount_currency`** / **`untaxed_amount`** (`Monetary`, computed, stored)
- **L2:** Computed via `_compute_tax_amount_currency` / `_compute_tax_amount`. Derived via `_prepare_base_line_for_taxes_computation` with `special_mode='total_included'`.

**`tax_amount_currency`** / **`tax_amount`** (`Monetary`, computed, stored)
- **L2:** `tax_details['total_included_currency'] - tax_details['total_excluded_currency']`. Computed after `total_amount` in the dependency chain.

**`price_unit`** (`Float`, computed (draft only) / stored, required, readonly, digits=`Product Price`)
- **L2:** When `_needs_product_price_computation()` (i.e., `product_has_cost`): reads `product_id.standard_price`. Otherwise: `total_amount / quantity`. Frozen once state is not `draft` — prevents retroactive price changes after accounting entry creation.
- **L3:** Stored readonly after first non-draft state. Any write to `price_unit` after submission is ignored.

**`currency_id`** (`Many2one(res.currency)`, required, `default=company.currency_id`, computed/stored)
- **L2:** When `product_has_cost` and state is `draft`: resets to `company_currency_id`. Locked after submission.
- **L3:** Changing `currency_id` triggers `_set_expense_currency_rate()` then `_compute_total_amount()` which converts via the new rate.

**`currency_rate`** (`Float`, digits=`(16, 9)`, computed, tracked)
- **L2:** `res.currency._get_conversion_rate(from_currency, to_currency, company, date)`. If currency/amount/date drift from origin values, recomputed from rate table. If stable, rate = `total_amount / total_amount_currency` (locked rate). Mono-currency: `rate=1.0`, label hidden.
- **L3:** Tracked field — full audit trail of rate changes.

**`label_currency_rate`** (`Char`, computed)
- Display "1 EUR = 1.234567 USD". Hidden in mono-currency mode.

**`is_multiple_currency`** (`Boolean`, computed)
- True when `currency_id != company_currency_id`. Shortcut that skips conversion math throughout all compute methods.

**`amount_residual`** (`Monetary`, related to `account_move_id.amount_residual`)
- **L3:** Used in `_compute_state` to distinguish `in_payment` from `paid` when `payment_state == 'partial'`.

#### Accounting Fields

**`tax_ids`** (`Many2many(account.tax)`, computed from `product_id.supplier_taxes_id`, `store=True`, `precompute=True`, domain=`[('type_tax_use', '=', 'purchase')]`, `check_company=True`)
- **L2:** Filtered to the expense's `company_id`. All taxes behave as price-included for expenses — achieved via `special_mode='total_included'` in `_prepare_base_line_for_taxes_computation`.
- **L3:** Overridden in `AccountMove._prepare_product_base_line_for_taxes_computation` specifically when `payment_mode == 'own_account'`. The `account_tax` model also hooks `_prepare_base_line_grouping_key` to include `expense_id.id`, preventing cross-expense tax aggregation.

**`account_id`** (`Many2one(account.account)`, computed cascade, `store=True`, domain excludes receivable/payable/cash/credit_card)
- Cascade: `product_id.product_tmpl_id._get_product_accounts()['expense']` → `company_id.expense_account_id` → `journal.default_account_id` (purchase journals only). Raises `RedirectWarning` if all fallbacks fail.

**`payment_mode`** (`Selection`, required, default=`'own_account'`)
- `'own_account'`: Employee paid out of pocket → creates `account.move` of type `in_receipt` for reimbursement.
- `'company_account'`: Company credit card/direct payment → creates a payment journal entry. Exactly one expense per move — enforced by `_check_expense_ids`.

**`journal_id`** (`Many2one(account.journal)`, related to `payment_method_line_id.journal_id`, readonly)
- Only relevant for `company_account` mode.

**`payment_method_line_id`** (`Many2one(account.payment.method.line)`, computed from company settings, `store=True`)
- Falls back to first outbound payment method line for the company. Restricted by `company_id.company_expense_allowed_payment_method_line_ids`.

**`selectable_payment_method_line_ids`** (`Many2many(account.payment.method.line)`, computed)
- If `company_expense_allowed_payment_method_line_ids` is set, uses those; otherwise searches all outbound payment method lines for the company.

**`account_move_id`** (`Many2one(account.move)`, readonly, `index='btree_not_null'`)
- Links to the generated receipt (own_account) or the payment's move (company_account). The `btree_not_null` index enables efficient lookups for state computation.

**`vendor_id`** (`Many2one(res.partner)`)
- Set as the supplier partner on move lines. For `own_account`: `partner_id = employee.work_contact_id`. For `company_account`: `partner_id = vendor_id` (the actual vendor, not the employee).

#### State Fields

**`state`** (`Selection`, computed, `store=True`, `index=True`, `readonly=True`, `tracking=True`)
- **NOT stored as writeable** — derived from `approval_state`, `account_move_id.state`, and `account_move_id.payment_state`:

| Value | Trigger Condition |
|---|---|
| `draft` | Default; or `approval_state = False` with no move |
| `submitted` | `approval_state = 'submitted'` and no move |
| `approved` | `approval_state = 'approved'` and no move |
| `posted` | Move exists, `move.state == 'draft'` OR `payment_state == 'not_paid'` |
| `in_payment` | Move posted with `payment_state in ('in_payment', 'partial' + residual > 0)` |
| `paid` | `move.state == 'cancel'` OR `payment_mode == 'company_account'` OR fully paid |
| `refused` | `approval_state = 'refused'` |

- **L3:** `company_account` mode shortcuts directly to `paid` since the company has already paid — employees never see `posted` in that flow. The `approved` → accounting transition is invisible to the user.

**`approval_state`** (`Selection`, stored, readonly)
- `False` (default), `'submitted'`, `'approved'`, `'refused'`. Tracks the human-approval sub-state independently of accounting state.

**`approval_date`** (`Datetime`, readonly)
- Set to `Datetime.now()` by `_do_approve()`.

#### Security / UX Computed Fields (all readonly)

**`is_editable`** — `True` if: HR admin (always); own draft; approver/manager of non-own expense. Blocks write of `tax_ids`, `analytic_distribution`, `account_id`, `manager_id` when False.

**`can_reset`** — `True` if: All Approver or Manager; or the employee's `expense_manager_id`; or employee on `draft`/`submitted`. Checks `company_id in valid_company_ids`.

**`can_approve`** — Inverse of `_get_cannot_approve_reason()`. Checks: same company; is approver/team approver; not self; is current manager or in hierarchy.

#### Warning / Duplicate Fields

**`attachment_ids`** (`One2many(ir.attachment)`, inverse on `res_model='hr.expense'`)
- `nb_attachment` is a count for display. Attachments deep-copied to `account.move` on posting (both receipt and company-account paths). On split, all original attachments are copied to every child expense.

**`same_receipt_expense_ids`** (`Many2many(hr.expense)`, computed via `_read_group` on checksum)
- Finds all other expenses sharing any attachment checksum. Used for a UI warning banner on potentially duplicate receipts.

**`duplicate_expense_ids`** (`Many2many(hr.expense)`, computed via raw SQL)
- Finds expenses with identical `employee_id`, `product_id`, `date`, `total_amount_currency`, `company_id`, `currency_id`. Used to trigger the `hr_expense_approve_duplicate` wizard on approval.

**`split_expense_origin_id`** (`Many2one(hr.expense)`)
- Points to the original expense when created via split. Prevents same-receipt detection from crossing split boundaries.

**`former_sheet_id`** (`Integer`, string="Former Report")
- Legacy field from removed `hr.expense.sheet` model. Retained for migration compatibility.

---

## Workflow and Actions

### State Transition Diagram

```
[draft] --action_submit()--> [submitted]
                              |
                   (auto-validation: no manager assigned)
                              |
                              v
                         [approved] --action_post()--> [posted]--payment-->[in_payment]-->[paid]
                              |
                              v
                         [refused] (terminal)

[draft] --action_submit()--> (via _can_be_autovalidated):
                             if manager_id == employee.user_id
                             or no manager at all
                             --> [approved] directly
```

### `action_submit()`
1. Validates `product_id` is set.
2. If no `manager_id`, calls `_get_default_responsible_for_approval()` to assign one.
3. If `_can_be_autovalidated()` (no manager OR `manager_id == employee.user_id`), bypasses `approval_state='submitted'` and calls `_do_approve(check=False)` directly.
4. Otherwise sets `approval_state='submitted'`.
5. Schedules `mail_act_expense_approval` activity on `manager_id`.

**Auto-validation edge case:** `manager_id == employee.user_id` passes `_can_be_autovalidated()`, bypassing human approval. Assigning a different approver disables this.

### `action_approve()`
1. Calls `_check_can_approve()` — validates user authority.
2. Validates analytic distribution via `_validate_distribution()`.
3. If `duplicate_expense_ids` exist in non-draft states, opens `hr_expense_approve_duplicate` wizard.
4. Otherwise calls `_do_approve(check=False)`.

### `_do_approve(check=True/False)`
Writes `approval_state='approved'`, `manager_id=current_user`, `approval_date=now()`. Triggers activity completion via `update_activities_and_mails()`.

### `action_refuse()`
Opens `hr_expense.refuse.wizard` modal. Wizard calls `_do_refuse(reason)`:
- Deletes any draft `account_move_id` (raises if any move is posted).
- Sets `approval_state='refused'`.
- Posts a message with the refusal reason using `hr_expense_template_refuse_reason` template.

### `action_post()`
1. Calls `_check_can_create_move()` — only `state == 'approved'` allowed; `payment_mode` must be set.
2. **Company-account expenses:** calls `_create_company_paid_moves()`, then `action_post()` on the resulting payment.
3. **Employee-paid expenses:** opens `hr_expense.post.wizard` modal. Wizard calls `_prepare_receipts_vals()` with chosen journal and accounting date, then creates and posts the `account.move` in_receipt.

### `_create_company_paid_moves()`
- Each expense gets its own `account.move` + outbound `account.payment` pair (enforced by `_check_expense_ids`).
- Move is linked via `origin_payment_id` on the move. Payment's `outstanding_account_id` computed via `_get_expense_account_destination()`.
- Created with `sudo()` because the calling user (Team Approver) may lack direct `account.move` create rights.

### `_prepare_receipts_vals()`
- Groups expenses by `employee_id` — one receipt per employee.
- Sets `move_type='in_receipt'`, `partner_id=employee.work_contact_id`, `currency_id=company_currency`.
- Each expense gets one `Command.create` line via `_prepare_move_lines_vals()`. Attachments are deep-copied to the move.

### `action_reset()`
- Validates via `_check_can_reset_approval()`: user has rights AND no move is posted.
- Reverses (cancels) non-draft moves via `_reverse_moves()`. Unlinks draft moves.
- Clears `approval_state`, `approval_date`, `account_move_id` via `_do_reset_approval()`.

### `action_split_wizard()`
- Only callable when `state` in `{'draft', 'submitted', 'approved'}` (not posted) and `is_editable`.
- Creates two `hr.expense.split` records via `_get_split_values()`: splits `total_amount_currency` into halves using `float_round` UP and DOWN (handles odd cents).
- `action_split_expense()`: first split overwrites original expense; remaining splits create new records via `copy()` with shared `split_expense_origin_id`. All attachments are copied to every child.

### `action_approve_duplicates()`
- Posts a `mail.mt_comment` message on each duplicate confirming the approver verified it.

---

## Accounting Integration

### `account.move` Extensions

**`expense_ids`** (`One2many` inverse) — links the move back to expenses. Used in `_compute_commercial_partner_id`, `_compute_needed_terms`, `_reverse_moves`.

**`_compute_commercial_partner_id()`** — for `own_account` moves, sets `commercial_partner_id` to the employee's partner (unless it equals `company_id.partner_id`).

**`_check_expense_ids()`** — raises if any `company_account` expense is grouped with other expenses. Each such expense requires a dedicated move.

**`_compute_needed_terms()`** — for `company_account` expenses, overrides auto-computed payment term to use `_get_expense_account_destination()` as the destination account.

**`_prepare_product_base_line_for_taxes_computation()`** — sets `special_mode='total_included'` for `own_account` payment mode.

**`_reverse_moves()` / `button_cancel()`** — clears `expense_ids` from the move before reversing/cancelling, preventing the expense from remaining in "posted" state.

### `account.move.line` Extensions

**`expense_id`** (`Many2one(hr.expense)`, `index='btree_not_null'`, `copy=True`) — links each line back to its expense.

**`_check_payable_receivable()`** — skips payable/receivable account type checks for `company_account` expense lines.

**`_compute_totals()`** — forces `force_price_include=True` for expense lines so taxes are price-included.

**`_get_extra_query_base_tax_line_mapping()`** — SQL: `AND (base_line.expense_id IS NULL OR account_move_line.expense_id = base_line.expense_id)`. Ensures tax lines only match their own expense's base line.

### `account.payment` Extensions

**`_compute_outstanding_account_id()`** — for `company_account` payments, sets `outstanding_account_id` to employee/vendor destination account.

**`_compute_show_require_partner_bank()`** — disables `require_partner_bank_account` for expense-linked payments.

**`write()`** — prevents modification of date, amount, payment type, partner, journal, etc. when linked to an expense.

---

## Tax Computation Architecture

The expense module hooks deeply into `account.tax` to enforce price-included behavior for all taxes regardless of tax definition:

1. **`HrExpense._prepare_base_line_for_taxes_computation`** — passes `special_mode='total_included'` as the default for all expense tax computations.
2. **`AccountMove._prepare_product_base_line_for_taxes_computation`** — overrides `special_mode='total_included'` specifically for `own_account` payment mode.
3. **`AccountTax._prepare_base_line_for_taxes_computation`** — copies `expense_id` onto the tax base line dict.
4. **`AccountTax._prepare_tax_line_for_taxes_computation`** — copies `expense_id` onto tax lines.
5. **`AccountTax._prepare_base_line_grouping_key`** — includes `expense_id.id` in the grouping key, ensuring each expense's taxes are computed separately and never cross-aggregated.
6. **`AccountTax._prepare_tax_line_repartition_grouping_key`** — same for tax repartition lines.
7. **`AccountTax._hook_compute_is_used`** — queries `expense_tax` table to determine which taxes are in use, preventing accidental tax deletion.

The implication: even if a tax definition has `price_include=False`, Odoo treats it as price-included for all expense lines. This is intentional — employees enter the total amount they paid, and taxes are computed backward.

---

## Wizard Models

### `hr.expense.split` (Transient)
Mirrors `hr.expense` for a split line: `name`, `product_id`, `tax_ids`, `total_amount_currency` (computed from product price if `product_has_cost`, otherwise editable), `employee_id`, `approval_state`, `approval_date`, `manager_id`, `analytic_distribution`, `product_has_cost`, `product_has_tax`. The `_get_values()` method builds the dict for `copy()`, applying the currency rate conversion for `total_amount`.

### `hr.expense.split.wizard` (Transient)
Holds parent `expense_id` and `expense_split_line_ids` (one2many). `split_possible` is True only when the sum of split line amounts equals the original via `currency_id.compare_amounts()`. `action_split_expense()` distributes attachments and sets `split_expense_origin_id` on all children.

### `hr.expense.refuse.wizard` (Transient)
Single `reason` Char + `expense_ids`. `action_refuse()` calls `expense_ids._do_refuse(self.reason)`.

### `hr.expense.post.wizard` (Transient)
`employee_journal_id` (purchase journal, default from `company.expense_journal_id`), `accounting_date` (Date, default today). `action_post_entry()` calls `expenses._prepare_receipts_vals()` with wizard's journal and date, creates and posts moves, sets `company.expense_journal_id` as a default if previously unset.

### `hr.expense.approve.duplicate` (Transient)
`expense_ids` pre-filled from context. `action_approve()` approves submitted duplicates; `action_refuse()` refuses with reason "Duplicate Expense".

---

## Product Integration

### `product.template`

**`can_be_expensed`** (`Boolean`, computed from `type`/`purchase_ok`, `store=True`, `readonly=False`)
- Auto-cleared when `type not in ('consu', 'service')` or `purchase_ok = False`. Auto-sets `purchase_ok = True` when a user enables it.
- `_auto_init()` creates the column with a SQL migration that sets `can_be_expensed = False` for non-consu/service products.

### `product.product`

**`standard_price_update_warning`** (`Char`, computed)
- Scans draft expenses using this product. If updating `standard_price` would change any draft expense's amount, shows a warning. Prevents inadvertent price changes after employees have recorded expenses.

**`write()` hook on `standard_price`**
- Updates all draft expenses using this product: sets `product_has_cost`, `price_unit` (if product has cost), or `quantity=1` and `price_unit=total_amount` (if switching to zero-cost).

---

## Employee Integration (`hr.employee`)

**`expense_manager_id`** (`Many2one(res.users)`, computed from `parent_id`, stored)
- Auto-populated from `parent_id.user_id` when manager changes. The expense's approver chain checks this first. Stored — can be manually overridden.
- `_get_user_m2o_to_empty_on_archived_employees()` includes this field; archiving an employee clears their linked `expense_manager_id`.

**`filter_for_expense`** (search-only boolean)
- Custom `search()`: regular employees see only themselves; Team Approvers see themselves, subordinates, and those where they are `expense_manager_id`; All Approvers see all employees in their company.

---

## Analytic Integration

**`account.analytic.applicability`** extended with `('expense', 'Expense')` business domain. For expense domain, `display_account_prefix = True`.

**`analytic.mixin`** provides `analytic_distribution` (Json). `_compute_analytic_distribution` uses `account.analytic.distribution.model._get_distribution()` with product, partner, and account prefix as keys.

**`account.analytic.account._unlink_except_account_in_analytic_distribution()`** — prevents deletion of analytic accounts referenced in any `hr.expense.analytic_distribution`.

---

## Cron Jobs

**`ir_cron_send_submitted_expenses_mail`** — weekly
- Runs `_cron_send_submitted_expenses_mail()` → `_send_submitted_expenses_mail()`.
- Batches by company and manager language. Uses `mail.mail.sudo().create()` for batched sending. Skips managers without an email. Version guard (pre-2.1 migration): skips batch email for installations upgrading from earlier versions.

---

## Email Gateway

Configured via `mail_alias_expense`. `message_new()` parses incoming emails:
1. Normalizes `email_from` via `email_normalize()`.
2. Matches to `hr.employee` by `work_email` or `user_id.email`.
3. Parses subject via `_parse_expense_subject()`: extracts product code (first word), price with currency symbol or ISO code, remaining description.
4. Creates expense with parsed amount, product, company currency.
5. Sends confirmation reply.

`_parse_product()`: searches `product_product` with `can_be_expensed=True` and `default_code=ilike` first word.
`_parse_price()`: regex supporting symbol ($) and ISO (USD) formats. Returns longest match to avoid partial extraction.

---

## PDF Report (`hr_expense.report_expense`)

The report iterates over `docs` (expenses) individually — one report per expense, batch-printable. Non-PDF attachments are converted via `report_expense_img` template before merging. `_render_qweb_pdf_prepare_streams()` in `ir_actions_report.py` handles the concatenation: renders base report, finds all linked `ir.attachment` records, appends PDF pages directly or converts images to PDF first, then writes the combined stream.

---

## Odoo 18 → Odoo 19 Breaking Changes

| Area | Odoo 18 | Odoo 19 |
|---|---|---|
| Sheet model | `hr.expense.sheet` was primary | Removed entirely; individual `hr.expense` is primary |
| State machine | XML workflow engine | Explicit Python `action_*` methods |
| Move link | `account_move_line_id` (line) | `account_move_id` (whole move) |
| Multi-currency | Partial support | Full `total_amount_currency` + `currency_rate` with inverses |
| Tax computation | Manual per-line | Delegated to `account.tax` with `special_mode='total_included'` |
| Split mechanic | Ad-hoc | `hr.expense.split` + `hr.expense.split.wizard` |
| Duplicate detection | Basic SQL | SQL + explicit `approve_duplicate` wizard |
| Product cost flag | Implicit | Explicit `product_has_cost` distinguishing fixed vs variable cost |

---

## L4: Performance

### N+1 Query Risks and Mitigations

The hr_expense module has several areas prone to N+1 queries, all of which are mitigated:

**`same_receipt_expense_ids` via `_read_group` on attachment checksums**
- Uses `_read_group` aggregation on `ir.attachment` grouped by `checksum` field with `res_id:array_agg` aggregate. This produces a single SQL query with `GROUP BY checksum` instead of loading attachment records individually. The result is a dictionary mapping checksums to arrays of `res_id` values.
- The `_compute_same_receipt_expense_ids` method then iterates over expenses and looks up pre-computed checksum arrays, avoiding per-expense attachment queries.

**`duplicate_expense_ids` via raw SQL**
- The `_compute_duplicate_expense_ids` method uses a single raw SQL query joining `hr_expense AS he` with itself (`hr_expense AS ex`) to find all duplicates in one pass. The query uses `ARRAY_AGG` to collect all duplicate IDs per matching group.
- The ORM `execute` + `fetchall` pattern bypasses ORM overhead entirely for this multi-record similarity check.

**`nb_attachment` via `_read_group`**
- `_compute_nb_attachment` uses `_read_group` counting `ir.attachment` per `res_id`, producing a single aggregated query. The result is stored in a Python dictionary for O(1) lookup per expense.

**`analytic_distribution` via distribution model**
- `_compute_analytic_distribution` calls `account.analytic.distribution.model._get_distribution()` which is itself a SQL-based distribution model. No per-record iteration occurs.

### Bulk Processing: `_prepare_receipts_vals()` and `_create_company_paid_moves()`

**Grouping by employee (`_prepare_receipts_vals`)**
```python
for employee_sudo, expenses_sudo in self.sudo().grouped('employee_id').items():
    # All expenses for same employee go into one receipt
    move_vals = {...expenses_sudo._prepare_move_vals()...}
    # One Command.create per expense line
    'line_ids': [Command.create(expenses_sudo._prepare_move_lines_vals())]
```
The `grouped('employee_id')` method (added in Odoo 15) produces a Python dictionary grouping expenses by employee without extra queries. Each group produces exactly one `account.move` and N move line `Command.create` calls — N queries for N expenses, but all in a single `create()` call on the move model.

**Company-paid: parallel list unpacking**
```python
move_vals_list, payment_vals_list = zip(*[
    expense._prepare_payments_vals() for expense in company_expense_account
])
payment_moves_sudo = self.env['account.move'].sudo().create(move_vals_list)
```
The `zip(*list)` pattern builds two parallel lists from a generator, then creates all moves and all payments in two bulk `create()` calls. This is O(1) database round-trip per entity type regardless of expense count.

### Currency Rate Computation

**Mono-currency short-circuit**
```python
if expense.is_multiple_currency:
    # full conversion logic
else:
    expense.currency_rate = 1.0
    expense.label_currency_rate = False
    continue  # skip all rate lookups
```
When `currency_id == company_currency_id`, the method returns early with no `res.currency._get_conversion_rate()` call. This avoids a database round-trip per expense on the majority of deployments.

**Locked rate shortcut**
```python
if (
    expense.currency_id != expense._origin.currency_id
    or expense.total_amount_currency != expense._origin.total_amount_currency
    or expense.date != expense._origin.date
):
    expense._set_expense_currency_rate(date_today=date_today)  # DB lookup
else:
    expense.currency_rate = expense.total_amount / expense.total_amount_currency  # in-memory
```
If the currency, amount, and date are unchanged from the origin, the rate is recomputed as the ratio of stored values (no database query). Only a real change triggers a conversion rate lookup.

### `sudo()` in `_create_company_paid_moves()`

Team Approvers (who call `action_post()`) do not have direct `account.move` create rights. The entire move + payment creation block runs under `sudo()`:
```python
moves_sudo = self.env['account.move'].sudo()
payments_sudo = self.env['account.payment'].sudo().create(payment_vals_list)
```
This is safe because the expense record has already been validated (approved state). The `sudo()` avoids a capability check that would fail, not a performance concern.

### Write Amplification Risk

`product.product.write()` triggers `hr.expense` updates when `standard_price` changes:
```python
expenses_sudo = self.env['hr.expense'].sudo().search([
    ('company_id', '=', self.env.company.id),
    ('product_id', 'in', self.ids),
    ('state', '=', 'draft'),
])
for expense_sudo in expenses_sudo:
    expense_sudo.write(expense_vals)
```
If many draft expenses share the same product, this produces one `search()` + N `write()` calls. This is inherent to the design (each expense needs its `price_unit` recalculated). Batch `write()` of the same values across all affected expenses would be more efficient but would lose the per-expense rounding logic.

### Attachment Deep-Copy on Split

When splitting an expense, all attachments are individually deep-copied to each child expense:
```python
for copied_expense in copied_expenses:
    for attachment in attachment_ids:
        attachment.copy({'res_model': 'hr.expense', 'res_id': copied_expense.id})
```
If the original has M attachments and the split creates N children, this produces M*N attachment copies. For typical receipts (1-3 attachments) this is negligible, but large attachment sets on split operations will scale poorly.

---

## L4: Version Change — Migration from Odoo 17/18 to Odoo 19

### The `hr.expense.sheet` Removal

The most significant architectural change in Odoo 19's hr_expense is the complete removal of the `hr.expense.sheet` model. In Odoo 17 and earlier, `hr.expense` records were grouped under an `hr.expense.sheet` (expense report/sheet), which was the unit of submission, approval, and accounting. In Odoo 19:

- **`hr.expense.sheet`** — the model itself is deleted. No new sheets can be created.
- **`hr.expense`** — becomes the standalone unit. Each expense has its own `state`, `approval_state`, and `account_move_id`.
- **`former_sheet_id`** (`Integer`) — retained on `hr.expense` as a migration aid. This stores the ID of the `hr.expense.sheet` record from which the expense originated (if any). It is informational only; Odoo does not use it for any business logic. It enables administrators to audit which original sheet a migrated expense belonged to.

### Migration Script: `migrations/2.1/pre-migrate.py`

The pre-migration script handles one specific concern: mail message subtypes for expense tracking:

```python
# mail_message_subtype records were created with default=True
# which caused expense state change emails to always send
# (subtype.default=True means always notify, ignoring follower rules)
xml_ids = [
    'hr_expense.mt_expense_approved',
    'hr_expense.mt_expense_refused',
    'hr_expense.mt_expense_paid',
    'hr_expense.mt_expense_reset',
    'hr_expense.mt_expense_entry_delete',
    'hr_expense.mt_expense_entry_draft',
]
# SQL UPDATE sets "default" = false for all expense subtypes
```

This ensures migrated databases inherit the pre-Odoo-19 behavior where expense state emails respect the mail follower mechanism rather than always firing.

### What the ORM Migration Does Not Handle

The core migration from `hr.expense.sheet` + `hr.expense.line` to standalone `hr.expense` records is handled by the Odoo framework's automatic model migration. However, the following must be verified manually:

1. **Sheet-level accounting entries** — in Odoo 17, submitting a sheet created a single `account.move` for all line amounts. In Odoo 19, each expense creates its own receipt (own_account) or payment (company_account). Verify that the accounting totals match after migration.

2. **`former_sheet_id` population** — confirm that the framework migration populated this field on all affected records. Query: `SELECT COUNT(*) FROM hr_expense WHERE former_sheet_id != 0` should match the count of old sheet records.

3. **Approval state** — each migrated expense should have `approval_state = 'approved'` if its original sheet was approved, or `approval_state = 'refused'` if refused, etc. Expenses not yet submitted retain `approval_state = False` and `state = 'draft'`.

4. **`account_move_line_id` vs `account_move_id`** — Odoo 17 used `account_move_line_id` (a Many2one to a specific line) for the receipt link. Odoo 19 uses `account_move_id` (Many2one to the whole move). The migration should re-link posted expenses to their original moves. Validate by checking that `account_move_id.state` matches the expected expense `state`.

5. **Unposted sheet lines** — any expense that was on an unsubmitted sheet retains `approval_state = False`. The employee or approver must resubmit it through the Odoo 19 workflow.

### `parse_version` Version Guard

The module uses a version check to avoid duplicate emails during migration:

```python
installed_module_version = self.sudo().env.ref('base.module_hr_expense').latest_version
if expenses_submitted_to_review and parse_version(installed_module_version)[2:] < parse_version('2.1'):
    self._send_submitted_expenses_mail()
```

`parse_version(installed_module_version)[2:]` strips the major version prefix (e.g., `2.0` from `19.0.2.0.0`), comparing only the minor+patch segment. Pre-2.1 means Odoo 17 or earlier. This guard prevents the batch email cron from firing on upgraded databases where expenses were already notified during the Odoo 17 sheet submission process.

### Implications for Custom Modules

Any custom module that extends `hr.expense.sheet` or `hr.expense.line` (the Odoo 17-era line model, which was a separate table from `hr.expense`) must be rewritten:

- **`hr.expense.line` model** — removed entirely. Fields from this model should be moved to `hr.expense` or to a new custom model.
- **`sheet_id` on `hr.expense`** — removed. Use `former_sheet_id` for read-only migration audit.
- **`state` on `hr.expense.sheet`** — workflow no longer exists. Approval logic is now on the individual `hr.expense` record.
- **XML `workflow` transitions** — must be replaced with Python `action_*` method calls. See the Workflow section above.

---

## L4: Security — Access Control Deep Dive

### Three-Dimensional Security Model

The hr_expense module implements security along three independent axes:

| Axis | What it controls | Key field |
|------|-----------------|-----------|
| **Group membership** | What operations are permitted | `res.groups` inheritance chain |
| **Record rules** | Which records are visible | `ir.rule` domain per group |
| **Field-level `is_editable`** | Which fields can be written | Computed `is_editable` boolean |

Critically, record rules filter the recordset before `is_editable` is evaluated — an employee cannot compute `is_editable` on an expense they cannot even see.

### Group Inheritance Chain

```
base.group_user          (Employee)
    └─ group_hr_expense_team_approver  (Team Approver)
            └─ group_hr_expense_user        (All Approver)
                    └─ group_hr_expense_manager (Administrator)
```

Each group adds one permission level. The `implied_ids` mechanism means that granting `group_hr_expense_manager` automatically grants all permissions of lower groups.

### Expense Approver vs. Expense Manager vs. Administrator

These are three distinct concepts often conflated:

| Concept | Definition | Who holds it |
|---------|-----------|-------------|
| **Expense approver** | The `res.users` record that must approve a specific expense | Determined per-expense by `_get_default_responsible_for_approval()` cascade chain: `expense_manager_id` → `department_id.manager_id` → `parent_id.user_id` (team leader). Written to `expense.manager_id` on `action_submit()` |
| **Expense manager** | The user designated on the `hr.employee` record | `employee.expense_manager_id` field. Can be set manually on the employee form or auto-populated from the employee's `parent_id`. Stored and persistent |
| **Administrator** | Member of `group_hr_expense_manager` | System-wide. Can edit all fields on all expenses. In `_compute_is_editable`: `is_hr_admin = self.env.user.has_group('hr_expense.group_hr_expense_manager')` grants unconditional edit rights |

**Approval authority** in `_get_cannot_approve_reason()`:
1. Must be in same company as the expense (`company_id.id in valid_company_ids`).
2. Must be a Team Approver or higher (`is_team_approver` or `is_approver`).
3. Cannot approve their own expense (`expense_employee.user_id != self.env.user`).
4. Must be in the approver chain (designated `expense_manager_id`, department manager, or team leader).

### Record Rule Domains: The Five-Legged OR

The Team Approver record rule uses a five-limb OR domain:
```python
['|', '|', '|', '|',
    ('employee_id.user_id', '=', user.id),                           # own
    ('employee_id.department_id.manager_id.user_id', '=', user.id), # dept mgr
    ('employee_id', 'child_of', user.employee_ids.ids),             # subordinates
    ('employee_id.expense_manager_id', '=', user.id),              # designated
    ('manager_id', '=', user.id)]                                  # current approver
```

This means a Team Approver can see any expense where they are any of: the owner, the department manager of the owner, in the owner's hierarchy, the designated approver on the owner's employee record, or already assigned as the current approver.

### Employee Record Rule: Two-Legged OR

Regular employees (`base.group_user`) have a more restrictive rule:
```python
['|',
    '&', ('employee_id.expense_manager_id', '=', user.id),
         ('state', 'in', ['draft', 'submitted', 'approved', 'refused']),
    '&', ('employee_id.user_id', '=', user.id),
         ('state', '=', 'draft')
]
```

Interpretation:
- An employee who is someone's designated expense manager can see ALL states of that someone's expenses.
- An employee can only see their own expenses in `draft` state. They cannot see their own submitted/approved/posted/paid expenses in the list view — those are only visible to their approver.

This is a common source of confusion: employees expect to see their own submitted expenses in their My Expenses view. The list view uses `base.group_user` permissions, so `state` visibility is restricted. The personal "My Expenses" kanban view uses a specific action with a domain that overrides this.

### Split Wizard Access: Five Parallel Record Rules

The split wizard (`hr.expense.split.wizard`) has five layered record rules, evaluated in order of specificity (most specific first):

| Rule | Group | Condition | Effect |
|------|-------|-----------|--------|
| `ir_rule_hr_expense_split_employee` | `base.group_user` | `state='draft'` AND (`user_id` is owner OR `user_id` is manager) | Own draft expenses only |
| `ir_rule_hr_expense_split_approver` | `group_hr_expense_team_approver` | `state` in `['draft', 'submitted']` AND manager is current user or empty | Approver can split expenses in approval queue |
| `ir_rule_hr_expense_split_user` | `group_hr_expense_user` | `state` in `['draft', 'submitted']` AND (not own expense OR manager is user/empty) | All Approver can split non-own expenses in draft/submitted |
| `ir_rule_hr_expense_split_manager` | `group_hr_expense_manager` | `state` in `['draft', 'submitted']` (no employee condition) | Admin can split anything in draft/submitted |
| `ir_rule_hr_expense_split_accountant` | `account.group_account_invoice` | `state` in `['draft', 'submitted', 'approved']` | Accountant can split up to approved state |

The order of application is from most specific to most general. An expense in `draft` state owned by the current user matches the first three rules simultaneously; the most restrictive (employee) effectively applies.

### `is_editable` Computed Security Field

`is_editable` is a stored-compute (recomputed on write) that gates field-level edits. It is NOT a record rule — it allows the user to see a record but blocks specific field writes:

```python
# write() enforces this:
if any(field in vals for field in {'tax_ids', 'analytic_distribution', 'account_id', 'manager_id'}):
    if any((not expense.is_editable and not self.env.su) for expense in self):
        raise UserError(_("You can't edit this expense."))
```

The following fields can be written even when `is_editable=False`: `state` (via workflow actions), `approval_state` (via approval actions), and system fields. The `is_editable` gate specifically blocks the four fields that affect accounting: taxes, analytic distribution, expense account, and approver assignment.

### Multi-Company Rule

`hr_expense_comp_rule` is a **global** rule (no `groups` attribute) applied to all users:
```python
[('company_id', 'in', company_ids)]
```
This restricts visibility and write access to expenses within the user's allowed company scope. Combined with the group-specific rules above, the complete security model is: `(group_rule OR group_rule OR ...) AND company_rule`.

---

## L4: Payment Integration — Reimbursement Flow

### Two Payment Modes, Two Accounting Paths

The `payment_mode` field determines the entire reimbursement accounting path:

**`payment_mode = 'own_account'` (Employee-paid)**
```
Expense approved (state='approved')
    → action_post()
        → opens hr_expense.post.wizard
            → user selects journal + accounting date
            → _prepare_receipts_vals() creates one in_receipt per employee
            → account.move.line created with expense_id link
            → employee outstanding payable (liability account) credited
            → expense account debited
    → state transitions: 'approved' → 'posted'
    → employee registers payment via account.payment.register
        → action_register_payment() on the receipt
        → payment linked to receipt lines
        → state: 'posted' → 'in_payment' → 'paid'
```

**`payment_mode = 'company_account'` (Company-paid)**
```
Expense approved (state='approved')
    → action_post()
        → _create_company_paid_moves()
            → creates one account.move + one account.payment per expense
            → payment is outbound (company pays the vendor directly)
            → move linked via origin_payment_id on the move
            → state transitions directly to 'paid' (no in_receipt step)
```

The `company_account` path has no separate vendor bill step — the company's payment to the vendor IS the accounting entry.

### `_prepare_receipts_vals()`: Employee Grouping

```python
for employee_sudo, expenses_sudo in self.sudo().grouped('employee_id').items():
    # All own_account expenses for the same employee go into ONE receipt
    return_vals.append({
        **expenses_sudo._prepare_move_vals(),
        'move_type': 'in_receipt',
        'partner_id': employee_sudo.work_contact_id.id,
        'commercial_partner_id': employee_sudo.user_partner_id.id,
        'line_ids': [
            Command.create(expenses_sudo._prepare_move_lines_vals())
            for expenses_sudo in expenses_sudo  # one line per expense
        ],
    })
```

Key behaviors:
- **One receipt per employee**: Multiple approved expenses for the same employee in the same `action_post()` call are consolidated into a single `in_receipt`.
- **`in_receipt` type**: Unlike `in_invoice`, `in_receipt` does not create a vendor bill payable — it is an internal employee reimbursement record.
- **`work_contact_id` as partner**: The employee's work contact partner (not the employee record itself) is used. `work_contact_id` may differ from `user_partner_id` in multi-company setups.
- **`commercial_partner_id = user_partner_id`**: Set to the user's commercial partner to ensure the payable account resolves correctly.

### `_create_company_paid_moves()`: Payment Creation

```python
def _create_company_paid_moves(self):
    # Each company_account expense gets its own move + payment pair
    for expense in company_account_expenses:
        move_vals, payment_vals = expense._prepare_payments_vals()
    payment_moves = self.env['account.move'].sudo().create(move_vals_list)
    payments = self.env['account.payment'].sudo().create(payment_vals_list)
    for payment, move in zip(payments, payment_moves):
        move.update({'origin_payment_id': payment.id, 'journal_id': move.journal_id.id})
```

The payment is the primary accounting entry. The move is a shadow record linked via `origin_payment_id` on the move (not `payment_id`). This allows `account_move_id.origin_payment_id` to resolve from the expense to the payment object.

### `_prepare_payments_vals()`: Move and Payment Structure

For each company_account expense, `_prepare_payments_vals()` returns a two-tuple `(move_vals, payment_vals)`:

**Move lines created:**
1. **Base line** — debits the expense account (`account_id`) with the untaxed amount, applies tax lines, sets `expense_id` on the line.
2. **Tax lines** — each linked tax creates a line debiting the tax account.
3. **Outstanding payment line** — credits the destination account (employee payable) with the full `total_amount` (tax-inclusive), in the employee's currency.

**Payment fields:**
- `payment_type='outbound'` — money leaving the company
- `partner_type='supplier'` — treated as a supplier payment (even though the partner is an employee)
- `partner_id=vendor_id` — the actual vendor, NOT the employee. The company pays the vendor directly.
- `outstanding_account_id` — computed as the expense destination account (employee's payable or credit account)

### `account.payment` Extensions

**`_compute_outstanding_account_id()`**
```python
expense_company_payments = self.filtered(
    lambda payment: payment.expense_ids.payment_mode == 'company_account'
)
for payment in expense_company_payments:
    payment.outstanding_account_id = payment.expense_ids._get_expense_account_destination()
super(AccountPayment, self - expense_company_payments)._compute_outstanding_account_id()
```
For company-paid expense payments, the outstanding account (where the payment is drawn from) is set to the expense destination account. This ensures the payment's bank line debits the correct liability account.

**Write protection**
```python
if self.expense_ids and any(field_name in trigger_fields for field_name in vals):
    raise UserError(_("You cannot do this modification since the payment is linked to an expense."))
```
After a payment is linked to an expense, neither date, amount, partner, nor journal can be changed. This prevents accounting inconsistency — modifying a posted payment would break reconciliation.

### Payment State → Expense State Mapping

The `_compute_state()` method drives expense state from payment state:

| Payment `payment_state` | Expense `state` |
|------------------------|-----------------|
| `not_paid` | `posted` |
| `in_payment` | `in_payment` |
| `partial` + residual > 0 | `in_payment` |
| `partial` + residual = 0 | `paid` |
| `paid` | `paid` |
| `cancel` | `paid` (company already paid) |

The `paid` state when `move.state == 'cancel'` is intentional: cancelled moves for company_account expenses still represent money that left the company. The expense should not revert to `approved`.

### `account.payment.register` Integration

The `account.payment.register` wizard is extended to support expense payments:

**`_get_line_batch_key()` override**
```python
expense = line.move_id.expense_ids.filtered(lambda e: e.payment_mode == 'own_account')
if expense and not line.move_id.partner_bank_id:
    res['partner_bank_id'] = (
        expense.employee_id.sudo().primary_bank_account_id.id
        or line.partner_id.bank_ids[0]
    )
```
When registering a payment against an expense receipt, the wizard pre-fills the employee's primary bank account (from `hr.employee.primary_bank_account_id`) rather than the generic partner bank account. This is critical for correct SEPA/wire payment execution.

**`_init_payments()` override**
```python
for payment, vals in zip(payments, to_process):
    expenses = vals['batch']['lines'].expense_id
    if expenses:
        payment.move_id.line_ids.write({'expense_id': expenses[0].id})
```
After payment creation, the expense_id is back-written to the move lines. This creates the `expense_id` → `account.move.line` → `account.move` → `account.payment` chain, enabling full traceability from expense to payment.

---

## Edge Cases and Failure Modes

1. **No `work_contact_id` on employee** → `_get_expense_account_destination()` raises `UserError`. Must configure the employee's work contact before posting.
2. **Archived payment method line** → `_compute_selectable_payment_method_line_ids` filters `journal_id.active=True`; archived methods are excluded from the domain.
3. **Product `standard_price` changed after submission** → `product.product.write()` only updates `state='draft'` expenses. Posted expenses are unaffected.
4. **Reversing a posted move** → `_reverse_moves()` clears `expense_ids` first. Expense returns to `approved` state (not `draft`) — user must call `action_reset()` to go to `draft`.
5. **`company_account` expense on cancelled move** → `_compute_state` treats `move.state == 'cancel'` as `paid` (shortcut since company already paid).
6. **Auto-validation bypass** → `manager_id == employee.user_id` or no manager at all causes `action_submit()` to call `_do_approve()` directly. Assigning any other approver disables this.
7. **All taxes always price-included** → `_prepare_base_line_for_taxes_computation` always passes `special_mode='total_included'`. Even if the tax definition says `price_include=False`, Odoo treats it as price-included for expenses. This is intentional for employee-facing simplicity.
8. **Pre-2.1 migration email guard** — the batch `_send_submitted_expenses_mail()` is skipped for installations upgrading from pre-2.1 to avoid duplicate emails during migration.
9. **Split rounding** — uses `float_round` UP/DOWN on halves to handle odd cents. The wizard's `split_possible` field validates the sum equals the original via `compare_amounts`.
10. **`parse_version` comparison** — done as `parse_version(installed_version)[2:] < parse_version('2.1')`, comparing only the minor+patch segment.

---

## Related Models Summary

```
hr.expense
  |-- employee_id --> hr.employee
  |     |-- expense_manager_id --> res.users
  |     |-- department_id --> hr.department
  |     |-- work_contact_id --> res.partner (used as vendor on move lines)
  |-- product_id --> product.product (can_be_expensed=True)
  |     |-- product_tmpl_id --> product.template (can_be_expensed, supplier_taxes_id)
  |-- account_id --> account.account (expense account)
  |-- tax_ids --> account.tax (purchase taxes, via expense_tax table)
  |-- account_move_id --> account.move
  |     |-- expense_ids --> hr.expense (inverse)
  |     |-- line_ids --> account.move.line
  |           |-- expense_id --> hr.expense
  |-- attachment_ids --> ir.attachment
  |-- analytic_distribution --> account.analytic.account (Json)
  |-- payment_method_line_id --> account.payment.method.line
  |     |-- journal_id --> account.journal
  |-- vendor_id --> res.partner (actual vendor for company_account mode)
```

---

## Related Documentation

- [[Modules/hr]]
- [[Modules/account]]
- [[Modules/Stock]]
- [[Modules/product]]
- [[Patterns/Workflow Patterns]]
- [[Patterns/Security Patterns]]
- [[Core/Fields]]
- [[Core/API]]
