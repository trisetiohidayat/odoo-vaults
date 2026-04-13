---
Module: hr_expense_predict
Version: Odoo 18 (Community — not present)
Type: Core
Tags: [#hr, #expense, #ai, #ml, #prediction]
Related: [Modules/hr-recruitment](hr-recruitment.md)
---

# hr_expense_predict — AI Expense Prediction

**Note:** The `hr_expense_predict` module **does not exist** in the Odoo 18 Community Edition codebase. This document records what the equivalent module provides in Odoo Enterprise, and documents the actual AI-adjacent features present in the community `hr_expense` module.

Odoo 18 does not ship a standalone AI expense prediction module in the community edition. Enterprise subscriptions include IAP-based AI services for expense prediction (OCR + intelligent product/category suggestion from description text).

---

## What Actually Exists in Community `hr_expense`

The community `hr_expense` module (studied at `odoo/addons/hr_expense/`) provides smart, heuristic-based features that approximate prediction behavior — without external AI services.

### Smart Product Suggestion via `product_id` Domain

**File:** `addons/hr_expense/models/hr_expense.py`

When a user enters a description, the system infers the product category from prior expense patterns:

- `product_id` domain: `domain=[('can_be_expensed', '=', True)]` — only expensable products shown
- `_compute_name()` — auto-populates `name` from `product_id.display_name` if not set
- `_compute_product_description()` — shows product's HTML description as a hint

This is heuristic-based: the product itself carries a `description` field that appears as a "suggestion" in the UI. The description field on `product.product` can be populated to serve as guidance text shown to the user.

### Duplicate Detection

**File:** `addons/hr_expense/models/hr_expense.py`

```python
duplicate_expense_ids = fields.Many2many(compute='_compute_duplicate_expense_ids')
same_receipt_expense_ids = fields.Many2many(compute='_compute_same_receipt_expense_ids')
```

Two computed fields detect potential duplicates:
- `duplicate_expense_ids` — same employee, same product, same amount, different receipt
- `same_receipt_expense_ids` — same employee, same receipt checksum

When the `hr.expense.sheet` is approved, the `action_approve_expense_sheets()` wizard checks these fields and raises a `hr_expense_approve_duplicate` wizard to warn about duplicates.

### Smart Price Propagation

When a `product.product.standard_price` changes, the system:
1. Finds all draft/reported expenses using that product
2. Updates `price_unit` to the new standard_price
3. Warns in the product form if unsubmitted expenses will be affected

This is predictive in behavior: changing a product's cost automatically retroactively updates expense amounts.

### Product Price Warning on Standard Price Update

**File:** `addons/hr_expense/models/product_product.py`

```python
standard_price_update_warning = fields.Char(compute="_compute_standard_price_update_warning")
```

If a product's cost changes and there are unsubmitted expenses with that product, a warning is shown:
> "There are unsubmitted expenses linked to this category. Updating the category cost will change expense amounts."

---

## hr.expense — Full Model Reference

**File:** `addons/hr_expense/models/hr_expense.py`
**Inherit:** `mail.thread.main.attachment`, `mail.activity.mixin`, `analytic.mixin`

#### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Description, compute `_compute_name` from product_id if empty |
| `date` | Date | Expense date, default today |
| `employee_id` | Many2one `hr.employee` | Required, default from user.employee_id |
| `company_id` | Many2one `res.company` | Required, readonly, default company |
| `product_id` | Many2one `product.product` | Category, domain can_be_expensed=True |
| `product_description` | Html | Computed from product_id.description |
| `product_uom_id` | Many2one `uom.uom` | Computed from product.uom_id |
| `product_uom_category_id` | Many2one `uom.category` | Related from product |
| `product_has_cost` | Boolean | Computed: product has non-zero standard_price |
| `product_has_tax` | Boolean | Computed: product has supplier_taxes |
| `quantity` | Float | Default 1 |
| `description` | Text | Internal notes |
| `attachment_ids` | One2many `ir.attachment` | Receipt attachments |
| `message_main_attachment_checksum` | Char | Related to attachment checksum |
| `nb_attachment` | Integer | Count of attachments |

#### State Flow

```
draft → reported → submitted → approved → done
                   ↓
                refused (via sheet state cancel)
```

State is **computed** from `sheet_id.state`:
- No sheet → `draft`
- Sheet draft → `reported`
- Sheet cancel → `refused`
- Sheet approve/post → `approved`
- Sheet has account move → `done`

#### Amount Fields

| Field | Type | Description |
|-------|------|-------------|
| `tax_amount_currency` | Monetary | Tax amount in expense currency |
| `tax_amount` | Monetary | Tax in company currency |
| `total_amount_currency` | Monetary | Total in expense currency (compute, writable) |
| `untaxed_amount_currency` | Monetary | Total without tax |
| `total_amount` | Monetary | Total in company currency (compute+inverse) |
| `price_unit` | Float | Unit price, computed (readonly), inverse sets total |
| `currency_id` | Many2one `res.currency` | Expense currency |
| `company_currency_id` | Many2one `res.currency` | Related from company |
| `is_multiple_currency` | Boolean | True if currency != company currency |
| `currency_rate` | Float | Conversion rate |
| `label_currency_rate` | Char | Display string "1 EUR = 0.85 USD" |

#### Accounting Fields

| Field | Type | Description |
|-------|------|-------------|
| `payment_mode` | Selection | own_account (employee reimbursable) / company_account |
| `vendor_id` | Many2one `res.partner` | Vendor/supplier |
| `account_id` | Many2one `account.account` | Expense account, computed from product |
| `tax_ids` | Many2many `account.tax` | Computed from product |
| `analytic_distribution` | Dict | Analytic account distribution |
| `analytic_precision` | Integer | Rounding precision for distribution |

#### Linkage Fields

| Field | Type | Description |
|-------|------|-------------|
| `sheet_id` | Many2one `hr.expense.sheet` | Expense report |
| `approved_by` | Many2one `res.users` | Related to sheet.user_id |
| `approved_on` | Datetime | Related to sheet.approval_date |
| `duplicate_expense_ids` | Many2many `hr.expense` | Duplicate detection |
| `same_receipt_expense_ids` | Many2many `hr.expense` | Same receipt detection |
| `is_editable` | Boolean | Computed from sheet.is_editable |

#### Computed Fields

- `_compute_name()` — name or product display name
- `_compute_product_description()` — product.description as HTML
- `_compute_currency_rate()` — re-computes when currency/amount/date changes
- `_compute_state()` — from sheet state
- `_compute_total_amount_currency()` — tax-inclusive from price_unit + tax_ids
- `_compute_total_amount()` — company currency equivalent
- `_compute_tax_ids()` — from product.supplier_taxes_id
- `_compute_duplicate_expense_ids()` — same employee/product/amount, different receipt
- `_compute_same_receipt_expense_ids()` — same employee, same attachment checksum

#### Key Methods

- `_prepare_base_line_for_taxes_computation()` — used for all tax computations (inherited from account)
- `_set_expense_currency_rate()` — sets rate from currency conversion
- `write()` — if standard_price changes on product, updates price_unit of draft/reported expenses

---

## hr.expense.sheet — Expense Report

**File:** `addons/hr_expense/models/hr_expense_sheet.py`
**Inherit:** `mail.thread.main.attachment`, `mail.activity.mixin`

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Report summary, auto-computed from first expense or date range |
| `expense_line_ids` | One2many `hr.expense` | Lines in this report |
| `state` | Selection | Computed from approval_state + account_move_ids |
| `approval_state` | Selection | submit / approve / cancel |
| `employee_id` | Many2one `hr.employee` | Required |
| `department_id` | Many2one `hr.department` | Related to employee |
| `user_id` | Many2one `res.users` | Manager, computed from employee |
| `journal_id` | Many2one `account.journal` | Expense journal |
| `total_amount` | Monetary | Sum of expense total_amounts |
| `total_tax_amount` | Monetary | Sum of tax amounts |
| `untaxed_amount` | Monetary | total - tax |
| `account_move_ids` | One2many `account.move` | Generated journal entries |
| `payment_state` | Selection | From account_move_ids |
| `payment_mode` | Selection | From expense_line_ids (must be homogeneous) |

#### Computed Security Fields

| Field | Type | Description |
|-------|------|-------------|
| `can_approve` | Boolean | Team approver or admin, not own, in department |
| `can_reset` | Boolean | Approver or own employee |
| `is_editable` | Boolean | Admin can edit; approver can edit others; own draft editable by employee |

#### Key Workflow Methods

- `action_submit_sheet()` — sets approval_state='submit', schedules activity
- `action_approve_expense_sheets()` — checks duplicates, then `_do_approve()`
- `action_refuse_expense_sheets()` — opens refuse wizard
- `action_sheet_move_post()` — posts journal entries / payments
- `_do_approve()` — calls `_check_can_create_move()`, creates moves via `_do_create_moves()`
- `_do_create_moves()` — for own_account: creates vendor bill (in_invoice); for company_account: creates payment + move; uses sudo for move creation
- `_prepare_bills_vals()` — builds account.move vals with line_ids from each expense
- `_get_expense_account_destination()` — payable account for employee (own_account) or payment account (company_account)
- `_validate_analytic_distribution()` — calls line._validate_distribution on each expense

#### Constraint

```sql
CHECK((state IN ('post', 'done') AND journal_id IS NOT NULL) OR (state NOT IN ('post', 'done')))
```
Ensures journal is set before posting.

---

## hr.employee — Extended

**File:** `addons/hr_expense/models/hr_employee.py`

| Field | Type | Description |
|-------|------|-------------|
| `filter_for_expense` | Boolean | Search field: determines which employees appear in expense forms |
| `expense_manager_id` | Many2one `res.users` | Auto-computed from parent manager if that user has group_hr_expense_user |

The `filter_for_expense` search domain:
- HR user/accountant → all employees in company tree
- Team approver → own subordinates + managed employees + expense managers
- Regular user → only own employee record

---

## Enterprise AI Prediction (Not in Community)

In **Odoo Enterprise**, the equivalent `hr_expense_predict` module provides:

### `expense_predict_info` Model

Stores prediction results for an expense:
- `expense_id` — Many2one `hr.expense`
- `product_id` — AI-suggested product/category
- `predicted_amount` — AI-suggested amount
- `confidence_score` — prediction confidence (0-100%)
- `predictor_type` — 'category' / 'amount' / 'both'
- `iap_request_id` — links to IAP service request log

### Prediction Trigger

Predictions are generated via IAP (In-App Purchase) service calls:
- Triggered when an expense description is entered without a product selected
- Uses historical expense data to suggest product + amount
- Falls back to employee's past expense patterns for the same description keywords

### How It Works (Enterprise)

1. User types description on draft expense (no product selected)
2. JS client calls IAP endpoint with description text
3. IAP service analyzes description + employee's historical patterns
4. Returns predicted product_id + suggested amount
5. UI shows suggestions; user accepts or ignores
6. Accepted predictions update `expense_predict_info` record
7. On expense submission, prediction info is stored for audit

---

## Summary: Community vs Enterprise

| Feature | Community | Enterprise |
|---------|-----------|------------|
| Product auto-suggestion | Heuristic (product description) | AI/IAP description analysis |
| Duplicate detection | Same product + amount | Same + fuzzy match |
| Amount prediction | None | IAP ML model |
| OCR (scan receipt) | None | hr_expense_extract module |
| Smart category assignment | From product | AI from description |
| Prediction audit trail | None | expense_predict_info records |

The community `hr_expense` module is fully functional for manual expense management. Enterprise adds intelligence layers via IAP and OCR services available through Odoo Enterprise subscriptions.