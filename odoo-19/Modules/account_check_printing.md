---
type: module
module: account_check_printing
tags: [odoo, odoo19, modules, account, check-printing, payment]
created: 2026-04-06
updated: 2026-04-11
---

# account_check_printing

**Tags:** `#odoo`, `#odoo19`, `#modules`, `#account`, `#check-printing`, `#payment`

## Overview

The `account_check_printing` module is a **base/check-printing foundation module** for Odoo 19. It provides the ORM logic, field definitions, check-number management, stub-line computation, and the pre-numbered-checks wizard for printing payments via check. Country-specific check layout modules (e.g., `l10n_us_check_printing`, `l10n_ca_check_printing`, `l10n_mx_check_printing`) depend on this module and provide the actual QWeb report templates that render the physical check paper layout.

```
Dependency chain:
  account_check_printing (base) <- l10n_<region>_check_printing (report layouts)
                                    ↑
                              account module
```

**Module Metadata:**

| Attribute | Value |
|-----------|-------|
| `_name` | `account_check_printing` |
| Category | `Accounting/Accounting` |
| Depends | `account` |
| License | `LGPL-3` |
| Post-init hook | `create_check_sequence_on_bank_journals` |
| Version | `1.0` |

### File Structure

```
account_check_printing/
├── __init__.py                  # Imports models + wizard; defines post-init hook
├── __manifest__.py              # Module metadata
├── models/
│   ├── __init__.py             # Imports all 5 model files
│   ├── account_journal.py       # account.journal extension (sequencing)
│   ├── account_payment.py       # account.payment extension (check fields + logic)
│   ├── account_payment_method.py # payment.method extension (check_printing code)
│   ├── res_company.py          # res.company extension (layout + margin fields)
│   └── res_config_settings.py  # res.config.settings extension (layout settings)
├── views/
│   ├── account_journal_views.xml    # Journal form: check printing group
│   ├── account_payment_views.xml    # (referenced in manifest)
│   └── res_config_settings_views.xml
├── wizard/
│   ├── print_prenumbered_checks.py  # Wizard for pre-numbered check assignment
│   └── print_prenumbered_checks_views.xml
├── data/
│   └── account_check_printing_data.xml # Payment method + server action definitions
└── tests/
    └── test_print_check.py         # Full test suite
```

---

## L1: How Checks Are Printed

### Check Printing Flow

The check printing workflow spans three distinct stages:

```
Stage 1: Payment Creation
  User creates outbound payment with payment_method = 'check_printing'
  Payment state: 'draft' or 'in_process'
  └─ check_number is assigned (manual sequencing or post-time auto-assignment)

Stage 2: Print Checks
  User clicks "Print Checks" button on payment(s)
  └─ Validates: same journal, check method, not already sent
  └─ Wizard (pre-numbered): prompts for first check number
  └─ Wizard (auto): assigns next sequence number
  └─ Sets is_sent = True on all payments
  └─ Renders QWeb report using selected check_layout

Stage 3: Post-Print
  Payments remain posted (already 'posted' before print)
  is_sent flag indicates checks have been delivered
  Checks can be VOIDED via action_void_check() which resets draft + cancels
```

### `account_payment` Model Extensions

**File:** `models/account_payment.py`

The module extends `account.payment` with five fields, six action methods, and three check-printing report generation methods.

#### Primary Action Methods

| Method | Trigger | Behavior |
|--------|---------|----------|
| `action_post()` | Override | Auto-assigns `check_number` from sequence when `check_manual_sequencing=True` |
| `print_checks()` | Button | Entry point; validates payments, launches wizard or direct print |
| `do_print_checks()` | Wizard / direct | Renders QWeb report; sets `is_sent=True` |
| `action_void_check()` | Button | Resets to draft, then cancels the payment |

#### `print_checks()` Flow

```
print_checks() called on recordset
    │
    ├─ Filter: payment_method_line_id.code == 'check_printing' AND is_sent == False
    │
    ├─ Validation 1: Recordset not empty (UserError if empty)
    │
    ├─ Validation 2: All payments from same journal (UserError if mixed)
    │
    ├─ IF check_manual_sequencing == False (pre-printed checks):
    │     └─ Query DB for last used check_number in journal
    │     └─ Compute next_check_number = last_number + 1 (same digit padding)
    │     └─ Return wizard action (print.prenumbered.checks)
    │         └─ Wizard assigns numbers via print_checks() on wizard
    │
    └─ ELSE (manual sequencing == True, blank stock):
          ├─ Post any draft payments first
          └─ Call do_print_checks() directly
```

#### `do_print_checks()` Flow

```
do_print_checks() called
    │
    ├─ Determine check_layout:
    │     layout = journal_id.bank_check_printing_layout
    │           or company_id.account_check_printing_layout
    │           or 'disabled'
    │
    ├─ IF layout == 'disabled' or empty:
    │     └─ Raise RedirectWarning → Go to Accounting Settings
    │
    ├─ Resolve report action from XML ID:
    │     report_action = env.ref(check_layout, False)
    │     └─ Raises RedirectWarning if report action not found
    │
    ├─ Mark as sent:
    │     payments.write({'is_sent': 'True'})
    │     (String 'True', not boolean True — see L3 notes)
    │
    └─ Return report_action.report_action(self)
          └─ Renders the QWeb report for all payments in recordset
```

### `account_journal` Extensions

**File:** `models/account_journal.py`

#### Fields Added

| Field | Type | Purpose |
|-------|------|---------|
| `check_manual_sequencing` | `Boolean` | Enable pre-printed check mode (blank stock = False) |
| `check_sequence_id` | `Many2one(ir.sequence)` | The dedicated `no_gap` sequence for auto-numbering |
| `check_next_number` | `Char` | Compute/inverse field for next check number display and entry |
| `bank_check_printing_layout` | `Selection` | Per-journal layout override (falls back to company-level) |

#### Dashboard Integration

`_get_journal_dashboard_data_batched()` is overridden to inject `num_checks_to_print` into the journal dashboard kanban. The `action_checks_to_print()` method returns a window action filtered to `payment_method_line_id.code = 'check_printing'`, `state = 'in_process'`, `is_sent = False`. This creates the "X Checks to Print" shortcut on the journal dashboard.

#### Post-Init Hook

The manifest declares `post_init_hook: 'create_check_sequence_on_bank_journals'`. This function (defined in `__init__.py`) runs after module installation and creates check sequences for all existing bank journals that do not yet have one. It does **not** run on upgrade, only on fresh install.

---

## L2: Field Types, Defaults, Constraints

### Field Reference Table

#### On `account.payment`

| Field | Type | Store | Compute | Default | Constraint |
|-------|------|-------|---------|---------|-----------|
| `check_amount_in_words` | `Char` | Yes | Yes (`_compute_check_amount_in_words`) | — | — |
| `check_manual_sequencing` | `Boolean` | Yes | Yes (related to `journal_id`) | `False` | — |
| `check_number` | `Char` | Yes | Yes (`_compute_check_number`) | — | `_constrains_check_number` (digits only) + `_constrains_check_number_unique` |
| `payment_method_line_id` | `Many2one` | Yes | No | — | `index=True` (added) |
| `show_check_number` | `Boolean` | No | Yes (`_compute_show_check_number`) | — | — |
| `check_layout_available` | `Boolean` | No | No | `len(selection) > 1` | — |

#### On `account.journal`

| Field | Type | Store | Compute | Default | Notes |
|-------|------|-------|---------|---------|-------|
| `check_manual_sequencing` | `Boolean` | Yes | No | `False` | User-configurable |
| `check_sequence_id` | `Many2one` | Yes | No | Auto-created | `no_gap` implementation |
| `check_next_number` | `Char` | No | Yes (`_compute_check_next_number`) | `1` or from sequence | `inverse=_inverse_check_next_number` |
| `bank_check_printing_layout` | `Selection` | Yes | Yes (`_get_check_printing_layouts`) | From company | Dynamic selection from company field |

#### On `res.company`

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `account_check_printing_layout` | `Selection` | `'disabled'` | Master layout setting |
| `account_check_printing_date_label` | `Boolean` | `True` | CPA-compliant date label |
| `account_check_printing_multi_stub` | `Boolean` | `False` | Allow multi-page stub |
| `account_check_printing_margin_top` | `Float` | `0.25` | Printer margin adjustment (inches) |
| `account_check_printing_margin_left` | `Float` | `0.25` | Printer margin adjustment |
| `account_check_printing_margin_right` | `Float` | `0.25` | Printer margin adjustment |

### Constraints

#### `_constrains_check_number` (field-level)

```python
@api.constrains('check_number')
def _constrains_check_number(self):
    for payment_check in self.filtered('check_number'):
        if not payment_check.check_number.isdecimal():
            raise ValidationError(_('Check numbers can only consist of digits'))
```

Only enforced when `check_number` is non-empty. Permitted values: purely numeric strings only. Whitespace, dashes, leading zeros (e.g., `"00042"`) are valid — `"42"` is also valid. The constraint does not enforce digit count (padding is handled separately).

#### `_constrains_check_number_unique` (record-level, SQL)

```python
@api.constrains('check_number', 'journal_id')
def _constrains_check_number_unique(self):
    # Raw SQL query comparing check_number::BIGINT across posted payments
    # in the same journal, excluding self, and only where check_number is NOT NULL
```

Executed at SQL level for performance. Compares `check_number::BIGINT` (numeric cast) to handle `"00042"` and `"42"` as the same number. Only checks `state = 'posted'` payments in the same journal. This prevents duplicate check numbers at the database level, which is the authoritative enforcement point.

**L3 Key Insight:** The `::BIGINT` cast means `"00042"` and `"42"` are considered duplicates. Padding must be consistent within a journal to avoid false uniqueness violations. The `padding` attribute on `ir.sequence` is used to standardize format: `sequence.padding = len(payment.check_number)`.

### Computed Field: `_compute_check_number`

```python
@api.depends('journal_id', 'payment_method_code')
def _compute_check_number(self):
    for pay in self:
        if pay.journal_id.check_manual_sequencing and pay.payment_method_code == 'check_printing':
            sequence = pay.journal_id.check_sequence_id
            pay.check_number = sequence.get_next_char(sequence.number_next_actual)
        else:
            pay.check_number = False
```

Triggered when the journal or payment method changes. For **manual sequencing** (pre-printed checks), the number is pre-computed from the sequence but not yet committed. For **auto sequencing** (blank stock), `check_number` remains `False` at this stage and is assigned at `action_post()` time.

### Inverse: `_inverse_check_number`

```python
def _inverse_check_number(self):
    for payment in self:
        if payment.check_number:
            sequence = payment.journal_id.check_sequence_id.sudo()
            sequence.padding = len(payment.check_number)
```

Called when the user (or the wizard) writes a check number to the field. The inverse synchronizes the `ir.sequence` padding length to match the written number's digit count. Note that it does **not** set `number_next_actual` — that is handled separately by the wizard.

### Auto-Init Column Creation

```python
def _auto_init(self):
    if not column_exists(self.env.cr, 'account_payment', 'check_number'):
        create_column(self.env.cr, 'account_payment', 'check_number', 'varchar')
    return super()._auto_init()
```

This is the **Odoo 19 pattern** for adding a stored field column in an upgrade-safe way. Rather than requiring a migration script, `create_column()` runs `ALTER TABLE ADD COLUMN IF NOT EXISTS` synchronously during module upgrade initialization. The `return super()._auto_init()` then runs the ORM's own column setup. This avoids `MemoryError` on large databases where the ORM's default field initialization loop would load all records into memory.

---

## L3: Cross-Model Relations, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Model: Account ↔ Check Printing

```
res.company (global settings)
    account_check_printing_layout     ──→ ir.actions.report (QWeb layout)
    account_check_printing_margin_*   ──→ passed as context to QWeb template
    account_check_printing_date_label  ──→ passed as context to QWeb template

account.journal (per-journal settings)
    check_manual_sequencing ──→ controls check_number assignment strategy
    check_sequence_id       ──→ ir.sequence (no_gap)
    bank_check_printing_layout ──→ per-journal override of company layout

account.payment (transactional records)
    check_number      ──→ displayed on printed check
    check_amount_in_words ──→ amount spelled out (currency.amount_to_text)
    show_check_number ──→ UI visibility flag
    is_sent          ──→ tracks print status (string 'True'/'False')
    payment_method_line_id.code == 'check_printing' ──→ identifies check payments

ir.sequence
    implementation='no_gap' ──→ prevents sequence gaps
    padding ──→ synced from check_number length
    number_next_actual ──→ incremented at action_post() time
```

### Payment Method Registration

**File:** `data/account_check_printing_data.xml`

```xml
<record id="account_payment_method_check" model="account.payment.method">
    <field name="name">Checks</field>
    <field name="code">check_printing</field>
    <field name="payment_type">outbound</field>
</record>
```

This `account.payment.method` record with `code='check_printing'` is the anchor. The `account_payment_method` model defines the method, and journal outbound payment method lines are linked to it. The `account_payment_method.py` model file extends `_get_payment_method_information()` to tag the method:

```python
res['check_printing'] = {'mode': 'multi', 'type': ('bank',)}
```

- `mode='multi'`: Multiple payments can be batched in a single print run.
- `type=('bank',)`: Only available on bank journals.

### Override Pattern: `action_post()`

```python
def action_post(self):
    payment_method_check = self.env.ref('account_check_printing.account_payment_method_check')
    for payment in self.filtered(lambda p: p.payment_method_id == payment_method_check
                                  and p.check_manual_sequencing):
        sequence = payment.journal_id.check_sequence_id
        payment.check_number = sequence.next_by_id()
    return super(AccountPayment, self).action_post()
```

The override intercepts `action_post()` for payments with the check payment method AND manual sequencing enabled. It calls `sequence.next_by_id()` to assign the next check number **before** calling `super()`. The `next_by_id()` method is called outside of any transaction-aware locking on the payment itself — the `no_gap` sequence implementation handles concurrency at the sequence level.

**Key design note:** For `check_manual_sequencing=False` (pre-printed checks), the number is never auto-assigned in `action_post()`. The wizard handles number assignment at print time.

### Failure Mode: Out-of-Sequence Check Numbers

**Scenario:** User enters a starting number in the pre-numbered check wizard that is **below** the last used number.

```python
def _inverse_check_next_number(self):
    for journal in self:
        next_num = int(journal.check_next_number)
        if next_num < journal.check_sequence_id.number_next_actual:
            raise ValidationError(_(
                "The last check number was %s. In order to avoid a check being rejected "
                "by the bank, you can only use a greater number.",
                journal.check_sequence_id.number_next_actual
            ))
```

The inverse on `journal.check_next_number` validates against the sequence's current `number_next_actual`. This prevents back-dating the sequence. However, this only applies to the **journal configuration field**, not to the wizard. The wizard uses the **last payment's `check_number`** (not the sequence) to compute the next number:

```python
last_check_number = (self.env.cr.fetchone() or (False,))[0]
next_check_number = f'{int(last_check_number) + 1:0{number_len}}'
```

If a payment's `check_number` was manually edited after posting (not via the journal config), the wizard could still assign a duplicate. The SQL uniqueness constraint catches this at the field level.

### Failure Mode: Voided Checks

`action_void_check()` resets a check payment to draft and then cancels it:

```python
def action_void_check(self):
    self.action_draft()
    self.action_cancel()
```

**Consequence:** Cancellation of a check payment does **not** automatically release the sequence number. The number is consumed from the `no_gap` sequence even if the check is voided. This is intentional — bank processing systems may have already received the check image, so voiding should not make the number available for reuse. If re-use is needed, administrators must manually adjust `journal.check_next_number` to the desired value after cancellation.

### Failure Mode: Pre-Printed Check Reprint

A payment with `is_sent=True` cannot be reprinted via the standard "Print Checks" action because the button's filter includes `is_sent=False`. However, users can still:
1. Go to the payment form directly
2. Use the QWeb report action manually (via Reports menu)
3. Or: use `action_void_check()` to reset, then reprint

The module does **not** provide a dedicated "reprint" mechanism. This is by design — reprinting a check that has already been marked as sent requires careful accounting controls.

### Workflow Trigger Chain

```
User: Register Payment
    └─ account.payment.create() with payment_method_line_id = check_printing method
        └─ state: 'draft', is_sent: False, check_number: False

User: Post Payment (action_post)
    ├─ IF check_manual_sequencing: check_number = sequence.next_by_id()
    └─ state: 'posted'

User: Print Checks (print_checks)
    ├─ Validation: same journal, not sent
    ├─ IF pre-printed: wizard → assigns check_number to all payments
    └─ do_print_checks() → is_sent = 'True' (string), QWeb report rendered

User: Void Check (action_void_check)
    └─ action_draft() → action_cancel()
        └─ state: 'cancelled', check_number: preserved (not reset)
```

---

## L4: Performance, Version Changes, Security, Check Layout, Reprint

### Performance

#### N+1 Query Analysis in `_check_make_stub_pages()`

The stub page generation iterates over reconciled invoices for each payment. For grouped payments covering N invoices:

```
Query 1: Get term lines (account_receivable/payable)
Query 2: Get matched_debit_ids (joined to move_id)
Query 3: Get matched_credit_ids (joined to move_id)
Additional: currency conversion per partial if multi-currency
```

For a batch of payments where each is reconciled with multiple invoices, the ORM's lazy loading means each payment's `_check_make_stub_pages()` may trigger multiple queries. The `_check_get_pages()` method calls `_check_make_stub_pages()` per payment, so N payments = N × (multiple queries).

**Optimization path:** `_check_make_stub_pages()` is called during QWeb report rendering, not in transactional code. For reports covering 50+ payments, consider:
- Enabling `multi_stub` (company setting) to reduce stub line count per page
- Rendering reports in smaller batches

#### Check Number Field Storage

The `check_number` field is stored as `varchar` in the database (not integer) to accommodate:
- Leading zeros: `"00042"` vs `"42"`
- Variable padding lengths
- Alphanumeric formats in some country-specific layouts

The SQL uniqueness constraint casts to `BIGINT` for comparison: `payment.check_number::BIGINT = other_payment.check_number::BIGINT`. This means `"00042"` and `"42"` are duplicates. The `padding` attribute on the sequence is used to enforce consistent format within a journal.

#### `is_sent` as String, Not Boolean

```python
self.write({'is_sent': 'True'})
```

The `is_sent` field (inherited from `account.payment`) is stored as a `Char` with values `'True'` / `'False'` (strings), not boolean. The ORM stores booleans correctly when written as `True`, but the string `'True'` is also stored. This is a **historical artifact** from how the field was first implemented. The filter `('is_sent', '=', False)` in Odoo's domain language means `is_sent == False` (boolean `False`), which works correctly because the ORM coerces the comparison.

### Odoo 18 to Odoo 19 Changes

| Feature | Change |
|---------|--------|
| `check_number` column creation | Odoo 19 introduced `_auto_init()` + `create_column()` pattern to avoid MemoryError on large DBs |
| `payment_method_line_id` index | Added `index=True` in Odoo 19 to speed up check payment queries |
| `_get_aml_default_display_name_list()` | Extended in Odoo 19 to include check_number in the account move line name when present |
| `check_layout_available` field | Added in Odoo 18/19 to detect whether any check layout is available |
| `multi_stub` company setting | Added in Odoo 18/19 as a configurable option |
| `_check_build_page_info()` | Added `company: self.company_id.name` and `currency: self.currency_id` to page info dict |
| Branch/company sequence isolation | Test added in Odoo 19 confirming `check_sequence_id` is company-scoped |

The `account_check_printing_layout` field on `res.company` uses `selection_add` in country-specific modules (e.g., `l10n_us_check_printing`) rather than defining all possible layouts in the base module. The base module only defines `('disabled', 'None')`.

### Security

#### ACL Model: `account.payment`

The base `account.payment` model is protected by `account`'s standard ACLs. The check printing module does **not** add additional ACL records. Access to check printing is controlled by:

1. **Payment method visibility:** The `check_printing` payment method is only available on **bank journals**. Users without access to bank journals cannot create check payments.

2. **Print action:** The server action bound to the "Print Checks" button is restricted to `account.group_account_user`:
   ```xml
   <field name="group_ids" eval="[(4, ref('account.group_account_user'))]"/>
   ```

3. **Journal dashboard:** The "Checks to Print" shortcut on the journal kanban requires read access to `account.payment`.

4. **Report access:** The QWeb report action respects the `report.layout` access rights. Users must have read access to the payment record to render the report.

5. **Check number uniqueness constraint:** Enforced at the database level across all companies (via `journal_id` filter). A user in Company A cannot accidentally assign the same check number as Company B if they share the same journal (which they should not, under multi-company record rules).

#### SQL Injection Safety

The `check_next_number` inverse validates with regex before writing:
```python
if not re.match(r'^[0-9]+$', journal.check_next_number):
    raise ValidationError(_('Next Check Number should only contains numbers.'))
```
The SQL uniqueness query uses parameterized queries via the ORM:
```python
'ids': tuple(payment_checks.ids)
```
Both implementations are safe from SQL injection.

#### XSS and CSRF

The check printing module does not contain any user-input rendering in Python code. The QWeb report templates (in country-specific modules) use `t-esc` for safe HTML escaping of check amounts, partner names, and dates. Custom layout implementations must use `t-esc` (not `t-raw`) for all dynamic content.

### Check Layout: Pre-Printed vs Blank Stock

| Aspect | Pre-Printed (Manual Sequencing) | Blank Stock (Auto Sequencing) |
|--------|----------------------------------|-------------------------------|
| `check_manual_sequencing` | `True` | `False` |
| Check numbers | Pre-printed on paper stock | Printed by Odoo via QWeb |
| Number assignment | Wizard assigns at print time | `action_post()` assigns automatically |
| Sequence gaps | Can occur if voided checks consume numbers | Managed by `no_gap` sequence |
| `check_next_number` field | Visible in journal config | Hidden in journal config |
| Layout requirement | Any layout (number not printed) | Must have check layout selected |
| Stub lines | Always included | Always included |

The **pre-printed mode** (`check_manual_sequencing=True`) is for companies using commercial check stock with pre-printed check numbers. The wizard prompts for the starting number matching the first check in the print batch. Each subsequent check in the batch gets the next sequential number.

The **blank stock mode** (`check_manual_sequencing=False`) is for companies printing both the check and the number. The `no_gap` sequence ensures sequential numbering without gaps (within a transaction-level guarantee).

### Reprint Mechanism

The module provides **no explicit reprint action**. The intended reprint flow is:

```
Option A: Direct Report Access
  1. Go to Accounting → Reports → [Check Layout Report]
  2. Select the payment(s) from the wizard
  3. Print the report directly

Option B: Reset and Reprint
  1. Click "Void Check" on the payment (action_void_check)
     └─ Payment state: cancelled; check_number: preserved
  2. Re-register a new payment with the same details
  3. The new payment gets the next check number
  4. Print the new check

Option C: Manual Number Override (exceptional)
  1. Edit the payment's check_number field directly
  2. Set is_sent back to False if needed (via DB or shell)
  3. Print again
```

**Important:** Once `is_sent=True`, the standard "Print Checks" button action filters the payment out. This is intentional to prevent accidental double-sending. Option A bypasses this guard and is the recommended reprint method for pre-printed checks where the physical check was misprinted but the number is correct.

### Check Number INT32 Limit

The module enforces that check numbers cannot exceed `MAX_INT32 = 2147483647`:

```python
if next_num > MAX_INT32:
    raise ValidationError(_(
        "The check number you entered (%(num)s) exceeds the maximum allowed value..."
    ))
```

This limit exists because the SQL uniqueness constraint casts `check_number` to `BIGINT`, but the inverse validation and sequence `number_next_actual` use Python `int`. More importantly, bank systems and check processing software often have their own limits. The test `test_print_great_pre_number_check` explicitly verifies that `2147483647` and `2147483648` are accepted at the ORM level (Python int is unbounded), while `2147483649` in `test_number_exceeds_int32_limit` is blocked in the journal config.

---

## Views and UI

### Journal Form Extension

**File:** `views/account_journal_views.xml`

The "Check Printing" group is inserted inside the `outbound_payment_settings` page, inside the `outgoing_payment` group. It is conditionally invisible unless the journal type is `bank` AND `check_printing` is in the selected payment method codes:

```xml
<group string="Check Printing"
       invisible="',check_printing,'.lower() not in (selected_payment_method_codes or '').lower() or type != 'bank'">
```

Fields shown: `check_manual_sequencing`, `check_next_number` (conditional), `bank_check_printing_layout`.

### Dashboard Kanban Extension

The kanban view on the journal dashboard shows a "X Checks to print" link when `num_checks_to_print > 0`. This is populated by the dashboard batch query:
```python
('payment_method_line_id.code', '=', 'check_printing'),
('state', '=', 'in_process'),
('is_sent', '=', False),
```

### Payment List View

The "Print Checks" server action is bound to `account.payment` via `binding_model_id` and `binding_view_types: list,kanban`. It appears in the Actions menu on the payment list/kanban views for payments with `payment_method_line_id.code == 'check_printing'`.

---

## Wizard: `print.prenumbered.checks`

**File:** `wizard/print_prenumbered_checks.py`

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `next_check_number` | `Char` (required) | Must be numeric only |

### Validation

```python
@api.constrains('next_check_number')
def _check_next_check_number(self):
    if not re.match(r'^[0-9]+$', check.next_check_number):
        raise ValidationError(...)
```

### Print Logic

```python
def print_checks(self):
    check_number = int(self.next_check_number)
    number_len = len(self.next_check_number or "")
    payments = self.env['account.payment'].browse(self.env.context['payment_ids'])

    # Post any draft payments
    payments.filtered(lambda r: r.state == 'draft').action_post()

    # Mark as sent
    payments.filtered(lambda r: r.state == 'in_process' and not r.is_sent).write({'is_sent': True})

    # Assign sequential numbers
    for payment in payments:
        payment.check_number = '%0{}d'.format(number_len) % check_number
        check_number += 1

    return payments.do_print_checks()
```

Key behaviors:
- Draft payments are posted first (auto-sequencing is bypassed for pre-printed mode)
- All payments in the batch get sequential numbers in the order they appear in the recordset
- The number format matches the digit length of the wizard's `next_check_number` (e.g., `00042` for a 5-digit starting number)

---

## Tests (`tests/test_print_check.py`)

The test suite covers:

| Test | Coverage |
|------|----------|
| `test_in_invoice_check_manual_sequencing` | Grouped payment from vendor bills; check number, amount_in_words, stub pages |
| `test_out_refund_check_manual_sequencing` | Grouped payment from customer refunds; same assertions |
| `test_multi_currency_stub_lines` | Foreign currency partial payment; stub line amounts and currencies |
| `test_in_invoice_check_manual_sequencing_with_multiple_payments` | Non-grouped payments; each gets sequential number |
| `test_check_label` | `name` field on move line includes `"Checks - {number}"` format |
| `test_print_great_pre_number_check` | `2147483647` and `2147483648` accepted; sequence increments |
| `test_print_check_with_branch` | Multi-company: branch can print checks without access error |
| `test_draft_invoice_payment_check_printing` | Draft invoice payment with `payment_account_id=None` |
| `test_multiple_payments_check_number_uniqueness` | Grouped payments; two distinct check numbers assigned |
| `test_number_exceeds_int32_limit` | `2147483648` blocked at journal `check_next_number` inverse |
