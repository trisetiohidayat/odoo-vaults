# Odoo 18 - hr_expense Module

## Overview

Expense management module. Handles employee expense reports from creation through accounting integration. Supports two payment flows: employee-paid (reimbursement via vendor bill) and company-paid (direct payment to vendor via bank).

## Source Path

`~/odoo/odoo18/odoo/addons/hr_expense/`

## Key Models

### hr.expense (`hr.expense`)

Individual expense line item. Inherits `mail.thread.main.attachment`, `mail.activity.mixin`, `analytic.mixin`.

**Key Fields:**
- `name`: Description (computed from product display name if not set).
- `date`: Expense date, default today.
- `employee_id` (`hr.employee`): Employee who incurred the expense. Domain filters on `filter_for_expense = True`. Defaults to current user.
- `company_id`: Required, from context.
- `product_id` (`product.product`): Expense category. Domain filters on `can_be_expensed = True`.
- `product_description`: HTML from product description field.
- `product_uom_id`: UoM from product's UoM.
- `product_has_cost`: Boolean — product has a non-zero `standard_price`.
- `product_has_tax`: Boolean — product has supplier taxes.
- `quantity`: Number of units, default 1.
- `price_unit`: Computed per unit price. Read-only in non-draft states.
- `total_amount_currency`: Total in expense currency (tax-included).
- `untaxed_amount_currency`: Base amount (pre-tax) in expense currency.
- `tax_amount_currency`: Tax amount in expense currency.
- `total_amount`: Total in company currency (tax-included).
- `tax_amount`: Tax amount in company currency.
- `currency_id`: Expense currency (default: company currency).
- `company_currency_id`: Related to `company_id.currency_id`.
- `is_multiple_currency`: `currency_id != company_currency_id`.
- `currency_rate`: Exchange rate (computed or user-overridden).
- `label_currency_rate`: Display string: `"1 EUR = 1.234567 USD"`.
- `payment_mode`: `own_account` (employee reimbursed) / `company_account` (company pays vendor).
- `vendor_id` (`res.partner`): Vendor/supplier.
- `account_id` (`account.account`): Expense account (computed from product/category).
- `tax_ids`: M2M `account.tax` (purchase taxes). Computed from product's `supplier_taxes_id`.
- `sheet_id` (`hr.expense.sheet`): Parent expense report (inverse).
- `state`: Computed from `sheet_id.state`. `draft` → `reported` → `submitted` → `approved` → `done` / `refused`.
- `is_editable`: Computed from `sheet_id.is_editable`.
- `duplicate_expense_ids`: M2M — same employee+product+amount in period (warning).
- `same_receipt_expense_ids`: M2M — same attachment checksum (warning).
- `description`: Internal notes (not part of thread).
- `attachment_ids`: One2many `ir.attachment`.
- `message_main_attachment_checksum`: Related from main attachment.
- `nb_attachment`: Count of attachments.
- `accounting_date`: Related from `sheet_id.accounting_date`.

**Computed Fields:**
- `_compute_currency_id`: Sets currency from product cost if applicable.
- `_compute_total_amount_currency`: Uses `_prepare_base_line_for_taxes_computation` + `AccountTax` methods. Only computed when `product_has_cost = True`.
- `_compute_tax_amount_currency` / `_compute_tax_amount`: Tax amounts from `AccountTax._add_tax_details_in_base_line`.
- `_compute_total_amount`: Converts total from foreign currency using `currency_rate`.
- `_compute_price_unit`: From `total_amount / quantity` or product price computation.
- `_compute_account_id`: From `product.product_tmpl_id._get_product_accounts()['expense']`.
- `_compute_employee_id`: Defaults to current user's employee.
- `_compute_state`: Derives state from sheet's state + move status.
- `_compute_is_editable`: From `sheet_id.is_editable`.
- `_compute_same_receipt_expense_ids`: Groups by attachment checksum (SQL `ARRAY_AGG`).
- `_compute_duplicate_expense_ids`: SQL query finds same employee+product+amount within 30 days.
- `_compute_currency_rate`: Auto-computes or preserves user override. Inverse sets rate from `total_amount / total_amount_currency`.

**Key Methods:**
- `_inverse_total_amount_currency()`: Sets `price_unit` from `total_amount / quantity`.
- `_inverse_total_amount()`: Full tax recomputation + rate reset when total amount is set directly.
- `_prepare_base_line_for_taxes_computation()`: Standard Odoo tax computation hook.

---

### hr.expense.sheet (`hr.expense.sheet`)

Expense report (batch of expense lines). Inherits `mail.thread.main.attachment`, `mail.activity.mixin`.

**Key Fields:**
- `name`: Report summary, required.
- `expense_line_ids`: One2many to `hr.expense`.
- `state`: Computed from approval + accounting state. Options: `draft` → `submit` → `approve` → `post` → `done` / `cancel`.
- `approval_state`: `submit` / `approve` / `cancel`. Controls visibility of approval actions.
- `approval_date`: When final approval occurred.
- `employee_id`: Employee who owns the report.
- `department_id`: Related from `employee_id.department_id`.
- `user_id`: Expense approver — computed from `employee_id.expense_manager_id` or `employee_id.parent_id.user_id`.
- `total_amount`: Sum of line `total_amount` fields.
- `untaxed_amount`: `total_amount - total_tax_amount`.
- `total_tax_amount`: Sum of line `tax_amount` fields.
- `amount_residual`: From `account_move_ids` residual amount.
- `currency_id`: Company currency (or first line's currency if multi-currency sheet).
- `is_multiple_currency`: Any line has different currency from company.
- `payment_mode`: Related from `expense_line_ids.payment_mode`.
- `employee_journal_id`: Purchase journal for own_account mode (default: company `expense_journal_id`).
- `journal_id`: Computed — `employee_journal_id` for own_account, `payment_method_line_id.journal_id` for company_account.
- `payment_method_line_id`: Payment method for company_account mode.
- `selectable_payment_method_line_ids`: Computed — company allowed methods or all outbound methods in company hierarchy.
- `account_move_ids`: Inverse to `account.move.expense_sheet_id`.
- `attachment_ids`: Aggregated from expense line attachments.

**Computed Fields:**
- `_compute_amount`: Sum of line totals and taxes.
- `_compute_from_account_move_ids`: Derives `amount_residual` and `payment_state` from moves. For company_account, moves are not relevant until reversed.
- `_compute_state`: Complex — derives from `approval_state` + `account_move_ids` + `payment_state`.
- `_compute_can_approve` / `_compute_can_reset`: Role-based button visibility.
- `_compute_is_editable`: `True` in draft/submit/approve states for authorized users.
- `_compute_journal_id`: Switches between employee journal and payment journal.
- `_compute_product_ids`: M2M of distinct products in lines.

**Key Methods:**
- `_do_create_moves()`: Creates accounting entries. For `own_account`: creates vendor bill (account.move with type `in_invoice`). For `company_account`: creates payment (account.payment).
- `_prepare_bills_vals()`: Builds `account.move` vals with line items — one line per expense (with analytic distribution).
- `_get_expense_account_destination()`: Determines payable account for the vendor bill.
- `_prepare_payments_vals()`: Builds `account.payment` vals for company-account payments.
- `action_submit_sheet()`: Transitions `approval_state` to `submit`.
- `action_approve()`: Transitions `approval_state` to `approve`, sets `approval_date`.
- `action_refuse(reason)`: Transitions `approval_state` to `cancel`, cascades to expense lines.
- `action_print_expenses()`: Returns report action for `hr_expense.report_hr_expense`.
- `action_split_expense()`: Wizard to split multi-line expense into separate sheets.

**SQL Constraints:**
- `journal_id_required_posted`: `journal_id IS NOT NULL` when state is `post` or `done`.

## Cross-Model Relationships

| Model | Field | Purpose |
|-------|-------|---------|
| `hr.expense` | `sheet_id` | Parent expense report |
| `hr.expense` | `employee_id` | Expense owner |
| `hr.expense` | `product_id` | Expense category + account |
| `hr.expense` | `tax_ids` | Tax computation |
| `hr.expense` | `analytic_distribution` | Cost center (from `analytic.mixin`) |
| `hr.expense.sheet` | `account_move_ids` | Accounting entries created |
| `hr.expense.sheet` | `expense_line_ids` | Lines in this report |
| `hr.expense.sheet` | `journal_id` | Accounting journal |
| `account.move` | `expense_sheet_id` | Reverse link from vendor bill |

## Edge Cases & Failure Modes

1. **Multi-currency expense**: `currency_rate` can be manually overridden. When overridden, `total_amount` is computed from `total_amount_currency * currency_rate`. Inverse of `total_amount` resets rate.
2. **Product without cost**: `product_has_cost = False` → `total_amount_currency` is user-editable directly (not computed). Inverse sets `price_unit`.
3. **Duplicate detection**: SQL query matches `employee_id + product_id + same amount` within 30-day window. Uses `ARRAY_AGG` for efficient grouping.
4. **Same receipt detection**: Groups by attachment checksum. `same_receipt_expense_ids` removes self from result.
5. **No product selected**: `account_id` falls back to product category's expense account via `property_account_expense_categ_id`.
6. **Company-account payment**: No vendor bill created. Payment is created directly via `account.payment`. Journal is from `payment_method_line_id`.
7. **Own-account reimbursement**: Creates vendor bill on employee partner. Employee journal used. Bill must be posted and paid.
8. **Sheet state derivation**: `_compute_state()` has complex logic: if no `approval_state` → draft; if cancel → cancel; if moves exist → post/done based on payment_state; otherwise → approval_state.
9. **Mixed payment modes**: All lines in a sheet must have the same `payment_mode`. Single selection on the sheet form.

## Security Groups

- `hr_expense.group_hr_expense_user`: Can submit own expenses, view own reports.
- `hr_expense.group_hr_expense_team_approver`: Can approve team expenses.
- `hr_expense.group_hr_expense_manager`: Full access (edit any expense in approved state).

## Workflow

```
Employee creates expense line (draft)
        ↓
Employee submits expense line
        ↓
Line state: draft → reported
        ↓
Employee submits expense report (sheet)
        ↓
Sheet state: draft → submit
        ↓
Manager/Officer approves report
        ↓
Sheet state: submit → approve
Line state: reported → approved
        ↓
        (own_account)
        ↓
Creates account.move (vendor bill)
on employee's partner
        ↓
Bill posted
        ↓
Sheet state: approve → post
        ↓
Bill paid (reimbursement)
        ↓
Sheet state: post → done

        (company_account)
        ↓
Creates account.payment
directly to vendor
        ↓
Payment posted
        ↓
Sheet state: approve → post → done
```

## Integration Points

- **hr**: Uses `hr.employee`, `hr.department` for employee filtering and approval chains.
- **account**: Creates `account.move` (vendor bills) and `account.payment`. Uses `account.tax` for tax computation.
- **product**: Expense categories from `product.product` with `can_be_expensed = True`.
- **analytic**: `analytic_distribution` field from `analytic.mixin` for cost center assignment.
- **mail**: Threading and activity mixins.