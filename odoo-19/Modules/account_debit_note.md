---
title: account_debit_note
tags:
  - "#odoo"
  - "#odoo19"
  - "#modules"
  - "#accounting"
description: Debit Notes module - extends account.move with debit note tracking, dedicated sequence numbering, and a wizard for creating debit notes from posted invoices.
---

# account_debit_note

## Module Overview

**Technical Name:** `account_debit_note`
**Category:** Accounting/Accounting
**Version:** 1.0
**License:** LGPL-3
**Author:** Odoo S.A.
**Depends:** `account`
**Installable:** True

### Purpose

The `account_debit_note` module enables the creation of **debit notes** against existing posted invoices. A debit note is a commercial document used in many jurisdictions (especially in countries following invoice-based tax systems such as many Latin American, Asian, and European countries) to increase the amounts of an existing invoice, or in specific cases to cancel a credit note. Unlike a regular invoice, a debit note maintains a formal link back to the original invoice via `debit_origin_id`.

This is the **opposite of a credit note** but differs from a regular reversal because:

- A debit note increases amounts (positive adjustment), while a credit note decreases amounts (negative adjustment)
- A debit note preserves the original invoice's line items (optional via `copy_lines`)
- The original invoice remains posted and is not cancelled
- The `debit_origin_id` field creates a permanent, auditable link between documents

### Module Structure

```
account_debit_note/
├── __init__.py              # Imports models and wizard
├── __manifest__.py          # Module metadata and data files
├── models/
│   ├── __init__.py          # Imports account_move and account_journal
│   ├── account_move.py      # Extends account.move with debit note fields
│   └── account_journal.py   # Extends account.journal with debit_sequence
├── wizard/
│   ├── __init__.py          # Imports account_debit_note
│   ├── account_debit_note.py # Transient wizard model
│   └── account_debit_note_view.xml # Wizard form view
├── views/
│   ├── account_move_view.xml # Extends account.move form with debit UI
│   └── account_journal_views.xml # Adds debit_sequence to journal form
├── security/
│   └── ir.model.access.csv  # ACLs for the wizard model
├── tests/
│   ├── __init__.py          # Imports test module
│   └── test_out_debit_note.py # Unit tests
└── i18n/
    └── account_debit_note.pot # Translation template
```

---

## L1: How Debit Notes Are Created from Invoices

### Debit Note Creation Flow

```
User: Opens posted invoice (out_invoice / in_invoice / out_refund / in_refund)
    └─ Clicks "Debit Note" button (Shift+D hotkey or action button)
        └─ Wizard opens: account.debit.note (transient model)
            ├─ move_ids: pre-filled with the active invoice
            ├─ date: today (default)
            ├─ reason: optional text
            ├─ journal_id: defaults to original invoice's journal
            └─ copy_lines: defaults to False

User: Configures wizard fields
    └─ Clicks "Create Debit Note"

Wizard: create_debit() executes
    ├─ Validates all move_ids (server-side recheck via default_get guard)
    ├─ For each selected move:
    │     ├─ _prepare_default_values() builds the copy() default dict
    │     ├─ move.copy(default=default_values) creates the new record
    │     └─ debit_origin_id is set, line_ids optionally copied
    └─ Returns window action to opened created debit note(s)
```

### Extended: `account.move`

**File:** `models/account_move.py`
**Inheritance:** Classical extension via `_inherit = 'account.move'`

The module adds three fields to the base `account.move` model to track the debit note relationship and provide UI navigation.

#### Fields

##### `debit_origin_id`

```python
debit_origin_id = fields.Many2one(
    'account.move',
    'Original Invoice Debited',
    readonly=True,
    copy=False,
    index='btree_not_null'
)
```

| Attribute | Value | Description |
|-----------|-------|-------------|
| `comodel_name` | `'account.move'` | References the original posted invoice |
| `string` | `'Original Invoice Debited'` | Human-readable label |
| `readonly` | `True` | Cannot be edited manually after creation |
| `copy` | `False` | Not copied when duplicating the move |
| `index` | `'btree_not_null'` | Partial B-tree index for performance on non-null values |

**Purpose:** Establishes a one-directional link from the debit note back to the original invoice that was debited. This is the audit trail anchor for debit note relationships.

**L3 Edge Case - Cross-Model Propagation:** When the debit note is created via `copy(default=...)`, the `debit_origin_id` is the only field explicitly carried over. All other fields (partner, lines, taxes, etc.) are copied according to the copy defaults or the wizard's explicit overrides. The `debit_origin_id` is excluded from `copy=False` but is set in the copy defaults, making it a special case where a normally non-copyable field is explicitly assigned.

**L3 Failure Mode:** If the original invoice is deleted after the debit note is created, the `debit_origin_id` becomes a dangling reference (foreign key to a deleted record). The `index='btree_not_null'` partial index mitigates query performance issues on the non-null values but does not prevent orphaned records. In practice, Odoo's unlink restrictions on `account.move` (which require cancelling posted moves first) prevent orphaned debit note links under normal circumstances.

**L4 Performance - Partial Index:** `index='btree_not_null'` generates `CREATE INDEX ... WHERE debit_origin_id IS NOT NULL` in PostgreSQL. This is smaller than a full index because null values are excluded, making it efficient for the `_get_last_sequence_domain()` queries that filter on `debit_origin_id IS NOT NULL`. It also benefits the One2many inverse reads.

##### `debit_note_ids`

```python
debit_note_ids = fields.One2many(
    'account.move',
    'debit_origin_id',
    'Debit Notes',
    help="The debit notes created for this invoice"
)
```

| Attribute | Value | Description |
|-----------|-------|-------------|
| `comodel_name` | `'account.move'` | The debit note records |
| `inverse_name` | `'debit_origin_id'` | The Many2one on the debit note side |
| `string` | `'Debit Notes'` | Human-readable label |
| `help` | `"The debit notes created for this invoice"` | Tooltip text |

**Purpose:** The inverse side of the `debit_origin_id` relationship. Provides a reverse lookup from the original invoice to all its debit notes. This is a computed/inferred relationship (Odoo derives the One2many from the Many2one inverse), not a stored computed field.

**L3 Performance - N+1 Prevention:** The One2many relationship is Odoo's standard inverse relation. Querying `invoice.debit_note_ids` produces a single SQL query due to ORM lazy loading. For batch operations, using `_read_group()` (as in `_compute_debit_count`) is preferred over iterating and accessing the One2many per record.

##### `debit_note_count`

```python
debit_note_count = fields.Integer(
    'Number of Debit Notes',
    compute='_compute_debit_count'
)
```

| Attribute | Value | Description |
|-----------|-------|-------------|
| `string` | `'Number of Debit Notes'` | Label shown in UI |
| `compute` | `'_compute_debit_count'` | Compute method name |
| `type` | `Integer` | Whole number count |

**Purpose:** A cached integer count of how many debit notes exist for each invoice. Displayed as a stat button on the invoice form view.

#### Methods

##### `_compute_debit_count()`

```python
@api.depends('debit_note_ids')
def _compute_debit_count(self):
    debit_data = self.env['account.move']._read_group(
        [('debit_origin_id', 'in', self.ids)],
        ['debit_origin_id'],
        ['__count']
    )
    data_map = {debit_origin.id: count for debit_origin, count in debit_data}
    for inv in self:
        inv.debit_note_count = data_map.get(inv.id, 0.0)
```

**Dependencies:** `debit_note_ids` (the One2many inverse)

**Logic:** Uses `_read_group()` for efficient batch counting instead of iterating and calling `search_count()` per record. The result is a dictionary mapping `debit_origin_id` to count, which is then used to populate the integer field per record.

**L3 Performance Analysis:**

Without `_read_group()`: N+1 query problem. N records would produce N `search_count()` queries.

With `_read_group()`: Single grouped SQL query with `COUNT(*) GROUP BY debit_origin_id`, then O(N) Python loop for assignment. This is the correct Odoo pattern for counting relations.

The `0.0` default (float instead of int) is a minor inconsistency - it should be `0` (integer) for type correctness, but it works because Python's ORM coerces the float to int when storing.

**L3 Edge Case - Empty Recordset:** If `self` is an empty recordset, the loop `for inv in self:` is never entered, and no exception is raised. `_read_group()` on an empty domain `[]` returns an empty list, so `data_map` is `{}`, and all `inv.debit_note_count` remain unset (but the method is only called on non-empty recordsets in practice).

##### `action_view_debit_notes()`

```python
def action_view_debit_notes(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'name': _('Debit Notes'),
        'res_model': 'account.move',
        'view_mode': 'list,form',
        'domain': [('debit_origin_id', '=', self.id)],
    }
```

**Purpose:** Opens a list view filtered to show all debit notes linked to the current invoice. Called from the stat button on the invoice form.

**L3 Edge Case - `ensure_one()`:** The method calls `self.ensure_one()`, so it only operates on a single record. If called on a multi-record recordset, an `AccessError` is raised. The stat button on the form view naturally operates on a single record (the current invoice), so this is safe.

##### `action_debit_note()`

```python
def action_debit_note(self):
    action = self.env.ref('account_debit_note.action_view_account_move_debit')._get_action_dict()
    return action
```

**Purpose:** Launches the "Create Debit Note" wizard. The wizard action (`action_view_account_move_debit`) is defined in `wizard/account_debit_note_view.xml` and is bound to `account.move` via `binding_model_id` and `binding_view_types`.

**L3 Edge Case - `_get_action_dict()`:** This method converts the XML action definition into a Python dictionary. The returned action opens the wizard in `target='new'` (modal) mode. The wizard context carries `active_model='account.move'` and `active_ids` (the selected invoice IDs from the list/kanban view).

##### `_get_last_sequence_domain()`

```python
def _get_last_sequence_domain(self, relaxed=False):
    where_string, param = super()._get_last_sequence_domain(relaxed)
    if self.journal_id.debit_sequence:
        where_string += " AND debit_origin_id IS " + ("NOT NULL" if self.debit_origin_id else "NULL")
    return where_string, param
```

**Purpose:** Overrides the sequence mixin's `_get_last_sequence_domain` to add a filter based on `debit_origin_id` when the journal has `debit_sequence = True`. This ensures debit notes use a separate sequence branch from regular invoices.

**L3 Logic Breakdown:**

```
# If journal.debit_sequence is True:
#   - Debit notes (where self.debit_origin_id IS NOT NULL) look for the last debit note in the sequence
#   - Regular invoices (where self.debit_origin_id IS NULL) look for the last regular invoice
# If journal.debit_sequence is False:
#   - No extra filter; debit notes share the main invoice sequence
```

**L3 Edge Case - `relaxed=True`:** When `relaxed=True` (used for sequence override detection), the parent's domain is already relaxed and the extra `debit_origin_id` filter is still appended. This ensures consistent behavior even when sequence constraints are relaxed.

**L3 SQL Injection Safety:** The code uses `+` string concatenation with hardcoded strings (`"NOT NULL"` / `"NULL"`), not with user-supplied values. The SQL is parameterized via `param` dict from the parent call. The implementation is safe from SQL injection.

##### `_get_starting_sequence()`

```python
def _get_starting_sequence(self):
    starting_sequence = super()._get_starting_sequence()
    if (
        self.journal_id.debit_sequence
        and self.debit_origin_id
        and self.move_type in ("in_invoice", "out_invoice")
    ):
        starting_sequence = "D" + starting_sequence
    return starting_sequence
```

**Purpose:** Prepends a `"D"` prefix to the debit note's sequence number when dedicated debit note sequences are enabled on the journal.

**L3 Logic Breakdown:**

```
# The starting sequence has "D" prefix only when ALL three conditions are met:
# 1. journal.debit_sequence == True
# 2. self.debit_origin_id is set (this IS a debit note)
# 3. move_type is a regular invoice type (out_invoice or in_invoice)
#
# Note: Debit notes of refunds (out_refund, in_refund) do NOT get "D" prefix
# even if debit_sequence is True. This is because refunds already have
# separate handling via the standard refund_sequence feature.
```

**L3 Sequence Number Format Example:**

```
# Without debit_sequence:
#   INV/2026/00001  (original invoice)
#   D/INV/2026/00001 (debit note - just the "D" prefix)

# With debit_sequence:
#   INV/2026/00001  (original invoice)
#   INV/2026/00002  (second invoice)
#   D/INV/2026/00001 (debit note - separate branch)
#   D/INV/2026/00002 (second debit note)
```

**L4 Performance - Sequence Gaps:** When `debit_sequence=True`, debits occupy a separate sequence branch. Regular invoices and debit notes interleave correctly without consuming each other's sequence numbers. This prevents sequence number exhaustion in high-volume environments where many debit notes are issued.

**L4 Multi-Company:** The sequence is per-journal, and journals are scoped to companies via `company_id`. Debit notes created in one company do not affect sequences in another company's journal. No special multi-company handling is needed.

##### `_get_copy_message_content()`

```python
def _get_copy_message_content(self, default):
    """Override to handle debit note specific messages."""
    if default and default.get('debit_origin_id'):
        return _('This debit note was created from: %s', self._get_html_link())
    return super()._get_copy_message_content(default)
```

**Purpose:** Customizes the chatter message posted when a debit note is created via the `copy()` operation.

**L3 Logic:** When `copy(default={'debit_origin_id': ...})` is called, the `default` dict contains the `debit_origin_id`. If this is present, the method returns a debit-note-specific message instead of the default duplication message. The `_get_html_link()` method generates an HTML link to the original invoice in the chatter.

**L3 Edge Case - No `debit_origin_id` in defaults:** If the copy is a regular duplication (not a debit note creation), `default` does not contain `debit_origin_id`, so the method falls back to the parent's logic which returns the standard "duplicated from" message.

**L4 Odoo 18 to 19 Change:** `_get_copy_message_content()` was introduced in the refactoring of account.move's copy messaging infrastructure across Odoo 18/19. The debit note override ensures audit trail messages remain correct after the move-copy machinery was rewritten.

---

## L2: Field Types, Defaults, Constraints

### Extended: `account.journal`

**File:** `models/account_journal.py`
**Inheritance:** Classical extension via `_inherit = 'account.journal'`

#### Fields

##### `debit_sequence`

```python
debit_sequence = fields.Boolean(
    string="Dedicated Debit Note Sequence",
    compute="_compute_debit_sequence",
    readonly=False,
    store=True,
    help="Check this box if you don't want to share the same sequence for invoices "
    "and debit notes made from this journal",
)
```

| Attribute | Value | Description |
|-----------|-------|-------------|
| `string` | `'Dedicated Debit Note Sequence'` | Label in journal form |
| `compute` | `'_compute_debit_sequence'` | Default value derivation |
| `readonly` | `False` | User can override the computed default |
| `store` | `True` | Persisted to database |
| `help` | Instructional text | Tooltip for the field |

**Purpose:** Controls whether debit notes created from invoices in this journal get a separate sequence branch (with the "D" prefix) or share the main invoice sequence.

**L3 Default Logic (from `_compute_debit_sequence`):**

```python
@api.depends("type")
def _compute_debit_sequence(self):
    for journal in self:
        journal.debit_sequence = journal.type in ("sale", "purchase")
```

The computed default is `True` for sale and purchase journals (which handle customer invoices, vendor bills, and their refunds). It defaults to `False` for bank, cash, and general journals. Because `readonly=False`, users can override this on a per-journal basis.

**L3 View Invisibility Condition:** In `views/account_journal_views.xml`, the field is hidden unless the journal type is sale or purchase:

```xml
<field name="debit_sequence" invisible="type not in ('sale', 'purchase')"/>
```

This prevents showing the option for journal types where debit notes are not applicable (bank, cash, general).

**L4 Odoo 18 to 19 Change:** In Odoo 18, the `debit_sequence` field was introduced as a new feature parallel to the existing `refund_sequence` field. The compute-and-store pattern with `readonly=False` allows users to toggle it while maintaining a sensible default. The logic is unchanged between Odoo 18 and 19.

**L4 Performance - Stored Compute:** The `store=True` pattern avoids recomputation on every read but means the field value becomes stale if the journal type is changed. This is mitigated by the `readonly=False` design - once a user sets the value, it persists regardless of future type changes. The compute re-activates on type change via the `depends("type")` decorator.

---

### Transient Wizard: `account.debit.note`

**File:** `wizard/account_debit_note.py`
**Model:** `account.debit.note`
**Type:** `transient.model` (extends `models.TransientModel`)

The wizard is the primary user-facing component. It allows selecting one or more posted invoices/credit notes and generating debit notes from them. As a `TransientModel`, it uses the ORM's automatic cleanup mechanism to purge records older than the session, but it is safe to leave wizard records in the database.

#### Wizard Fields

##### `move_ids`

```python
move_ids = fields.Many2many(
    'account.move',
    'account_move_debit_move',
    'debit_id',
    'move_id',
    domain=[('state', '=', 'posted')]
)
```

| Attribute | Value | Description |
|-----------|-------|-------------|
| `comodel_name` | `'account.move'` | Target model |
| `relation` | `'account_move_debit_move'` | Intermediate table name |
| `column1` | `'debit_id'` | Column for this model's ID |
| `column2` | `'move_id'` | Column for the move ID |
| `domain` | `[('state', '=', 'posted')]` | Only posted moves can be selected |
| `type` | `Many2many` | Standard Odoo Many2many |

**Purpose:** Stores the selected invoices/credit notes that will be debited. The `Many2many` allows creating debit notes for multiple invoices in a single wizard run.

**L3 Security - Domain Filter:** The `domain` parameter in the field definition applies a default filter in the UI selector, but the wizard's `default_get()` method performs additional server-side validation (raising `UserError` if non-posted moves are selected). The dual-layer validation ensures both UX friendliness and data integrity.

##### `date`

```python
date = fields.Date(
    string='Debit Note Date',
    default=fields.Date.context_today,
    required=True
)
```

| Attribute | Value | Description |
|-----------|-------|-------------|
| `string` | `'Debit Note Date'` | Label in the wizard form |
| `default` | `fields.Date.context_today` | Defaults to current date |
| `required` | `True` | Must be specified |

**Purpose:** The effective date of the debit note. Used as `invoice_date` on the generated debit note (when the original is an invoice). Passed as the `date` in `_prepare_default_values()`.

##### `reason`

```python
reason = fields.Char(string='Reason')
```

**Purpose:** An optional text field for documenting why the debit note was issued. Appended to the debit note's reference field (`ref`) as `"<original_name>, <reason>"`.

##### `journal_id`

```python
journal_id = fields.Many2one(
    'account.journal',
    string='Use Specific Journal',
    help='If empty, uses the journal of the journal entry to be debited.'
)
```

| Attribute | Value | Description |
|-----------|-------|-------------|
| `comodel_name` | `'account.journal'` | Journal model |
| `string` | `'Use Specific Journal'` | Label in the form |
| `help` | Instructional text | Explains the fallback behavior |

**Purpose:** Allows overriding the journal used for the debit note. If not specified, the debit note uses the same journal as the original invoice.

**L3 Journal Filtering - Domain computed by context:** In the wizard form XML:

```xml
<field name="journal_id" domain="[('type', '=', journal_type)]"/>
```

The `journal_type` is a computed field that determines whether sale or purchase journals should be shown based on the selected moves' types.

##### `copy_lines`

```python
copy_lines = fields.Boolean(
    "Copy Lines",
    help="In case you need to do corrections for every line, it can be in handy to copy them. "
         "We won't copy them for debit notes from credit notes."
)
```

**Purpose:** Controls whether the original invoice's line items are copied to the debit note. When `True`, the debit note starts with the same product lines as the original, allowing for corrections per line. When `False` (default), the debit note has no lines and must be populated manually.

**L3 Invisibility Rule:** The `copy_lines` field is hidden in the wizard form when the selected moves are refunds:

```xml
<field name="copy_lines" invisible="move_type in ['in_refund', 'out_refund']"/>
```

This is because debit notes created from credit notes are always created with empty lines (the refund's lines represent a reduction, so copying them as-is would be incorrect). This is enforced in `_prepare_default_values()`:

```python
if not self.copy_lines or move.move_type in [('in_refund', 'out_refund')]:
    default_values['line_ids'] = [(5, 0, 0)]
```

##### `move_type`

```python
move_type = fields.Char(compute="_compute_from_moves")
```

**Purpose:** A computed field (not stored) that determines the type of the selected moves. Used for conditional UI display (e.g., hiding `copy_lines` for refunds) and for passing context to the resulting action.

**L3 Logic:**

```python
@api.depends('move_ids')
def _compute_from_moves(self):
    for record in self:
        move_ids = record.move_ids
        record.move_type = (
            move_ids[0].move_type
            if len(move_ids) == 1
            or not any(m.move_type != move_ids[0].move_type for m in move_ids)
            else False
        )
```

The `move_type` is set to the first move's type if all selected moves have the same type. If moves of different types are selected, `move_type` is `False`. This drives the `journal_type` computation and the `copy_lines` visibility.

##### `journal_type`

```python
journal_type = fields.Char(compute="_compute_journal_type")
```

**Purpose:** Determines the required journal type (`sale` or `purchase`) based on the selected moves. Used to filter the journal selector in the wizard form.

**L3 Logic:**

```python
@api.depends('move_type')
def _compute_journal_type(self):
    for record in self:
        record.journal_type = (
            record.move_type in ['in_refund', 'in_invoice']
            and 'purchase'
            or 'sale'
        )
```

- `in_invoice` and `in_refund` (vendor bills and vendor credit notes) require **purchase** journals.
- `out_invoice` and `out_refund` (customer invoices and customer credit notes) require **sale** journals.

##### `country_code`

```python
country_code = fields.Char(related='move_ids.company_id.country_id.code')
```

**Purpose:** A related field to the company's country code. This is used for country-specific localization adjustments in future versions or for display purposes. Currently, it is primarily available for potential use in QWeb templates or conditional logic.

#### Wizard Methods

##### `default_get()`

```python
@api.model
def default_get(self, fields):
    res = super().default_get(fields)
    move_ids = self.env['account.move'].browse(
        self.env.context['active_ids']
    ) if self.env.context.get('active_model') == 'account.move' else self.env['account.move']

    if any(move.state != "posted" for move in move_ids):
        raise UserError(_('You can only debit posted moves.'))
    elif any(move.debit_origin_id for move in move_ids):
        raise UserError(_("You can't make a debit note for an invoice that is already linked to a debit note."))
    elif any(move.move_type not in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund'] for move in move_ids):
        raise UserError(_("You can make a debit note only for a Customer Invoice, a Customer Credit Note, a Vendor Bill or a Vendor Credit Note."))

    res['move_ids'] = [(6, 0, move_ids.ids)]
    return res
```

**Purpose:** Called when the wizard is opened from an invoice. Pre-populates the wizard with the selected moves and validates them.

**L3 Validation Chain (server-side enforcement):**

```
1. Posted State Check:
   - Ensures the invoice has been posted (state == 'posted')
   - Rationale: Draft invoices can simply be edited directly; debit notes are for adjusting posted documents

2. No Existing Debit Note Check:
   - Prevents creating debit notes on invoices that already have a debit_origin_id set
   - Rationale: Chained debit notes (debit of a debit) are not supported; each invoice can only be debited once
   - L3 Edge Case: If a user wants to debit again, they must create a debit note from the existing debit note instead

3. Move Type Check:
   - Only allows out_invoice, in_invoice, out_refund, in_refund
   - Rationale: Debit notes are only meaningful for invoices and their refunds; other move types (entries, receipts) are excluded
```

**L3 Edge Case - Mixed Move Types:** If multiple moves are selected and some pass/fail the type check, the `any()` function will raise `UserError` on the first violation. All selected moves must pass all validation checks for the wizard to open.

**L3 Edge Case - Empty `active_ids`:** If `active_ids` is empty or `active_model` is not `'account.move'`, `move_ids` becomes an empty recordset. The validation checks iterate over an empty recordset without error, so `res['move_ids'] = [(6, 0, [])]` is returned. The wizard opens with an empty selection, and `create_debit()` would return an empty action.

**L4 Multi-Company / Record Rules:** The `browse()` call respects record rules scoped to the current company. If the user selects moves from a company they do not have read access to, the `browse()` returns those records but subsequent field access may raise `AccessError`. This is consistent with standard Odoo ACL enforcement.

##### `_prepare_default_values()`

```python
def _prepare_default_values(self, move):
    if move.move_type in ('in_refund', 'out_refund'):
        type = 'in_invoice' if move.move_type == 'in_refund' else 'out_invoice'
    else:
        type = move.move_type

    default_values = {
        'ref': '%s, %s' % (move.name, self.reason) if self.reason else move.name,
        'date': self.date or move.date,
        'invoice_date': move.is_invoice(include_receipts=True) and (self.date or move.date) or False,
        'journal_id': self.journal_id and self.journal_id.id or move.journal_id.id,
        'invoice_payment_term_id': None,
        'debit_origin_id': move.id,
        'move_type': type,
    }

    if not self.copy_lines or move.move_type in [('in_refund', 'out_refund')]:
        default_values['line_ids'] = [(5, 0, 0)]

    return default_values
```

**Purpose:** Builds the `default` dictionary passed to `move.copy()` for each selected invoice.

**L3 Field-by-Field Analysis:**

| Field | Value | Notes |
|-------|-------|-------|
| `ref` | `"<name>, <reason>"` or `"<name>"` | Reason appended to reference |
| `date` | Wizard date or original date | Debit note's accounting date |
| `invoice_date` | Same as `date` if original is invoice | Invoice date for tax reporting |
| `journal_id` | Wizard's journal or original journal | Override or inherit |
| `invoice_payment_term_id` | `None` | Payment terms not copied (debit is separate) |
| `debit_origin_id` | `move.id` | The audit link to original invoice |
| `move_type` | `"in_invoice"` or `"out_invoice"` | Debit of refund becomes invoice |
| `line_ids` | `[(5, 0, 0)]` (empty) | Only if `copy_lines=False` or original is refund |

**L3 Type Reversal Logic for Refunds:**

```
# When debiting a refund (out_refund or in_refund):
#   out_refund (customer credit note)  -->  out_invoice (customer debit note)
#   in_refund  (vendor credit note)    -->  in_invoice  (vendor debit note)
#
# The debit note effectively cancels the credit note by reversing its effect.
# This is the "cancel a credit note" use case mentioned in the module description.
```

**L3 The `invoice_payment_term_id = None` Decision:**

Setting `invoice_payment_term_id` to `None` is deliberate. A debit note is a separate commercial document that may require different payment terms from the original invoice. Additionally, the `copy()` operation on `account.move` does not automatically set payment terms, so explicitly clearing it avoids inheriting stale or incorrect payment terms from the original.

**L4 Tax and Fiscal Localization:** The `invoice_date` field is set to the wizard's date for tax reporting purposes. This is critical for jurisdictions where the tax point date determines the tax period (e.g., many EU countries, Brazil, India). If the wizard date falls in a different fiscal period than the original invoice, the debit note will be recorded in the correct period.

**L4 Currency Handling:** The `copy()` method copies `currency_id` from the original move. No explicit currency handling is present. If the original invoice is in a foreign currency, the debit note inherits the same currency, keeping amounts consistent for reconciliation purposes.

**L4 Sequence Assignment Timing:** The sequence number is assigned by the sequence mixin when the record is created (after `copy()` completes and the transaction commits). The `_get_last_sequence_domain()` override ensures the debit note finds the correct preceding sequence number at creation time. This is safe for concurrent debit note creation because each creation uses `SELECT FOR UPDATE`-style locking within the sequence assignment transaction.

##### `create_debit()`

```python
def create_debit(self):
    self.ensure_one()
    new_moves = self.env['account.move']
    for move in self.move_ids.with_context(include_business_fields=True):  # copy sale/purchase links
        default_values = self._prepare_default_values(move)
        new_move = move.copy(default=default_values)
        new_moves |= new_move

    action = {
        'name': _('Debit Notes'),
        'type': 'ir.actions.act_window',
        'res_model': 'account.move',
        'context': {'default_move_type': default_values['move_type']},
    }
    if len(new_moves) == 1:
        action.update({
            'view_mode': 'form',
            'res_id': new_moves.id,
        })
    else:
        action.update({
            'view_mode': 'list,form',
            'domain': [('id', 'in', new_moves.ids)],
        })
    return action
```

**Purpose:** The wizard's main action method. Iterates over all selected moves, creates debit notes via `copy()`, and returns the appropriate window action to navigate to the created records.

**L3 Loop Logic:** The method loops over `self.move_ids` and uses the `|=` recordset accumulation operator to collect all created moves. Note that `default_values` is overwritten on each iteration, so `action['context']` uses the values from the last move. This is acceptable because `journal_type` and `move_type` are uniform across all moves in a single-journal batch (enforced by the wizard's domain filter).

**L3 `ensure_one()`:** Enforces single wizard invocation. The UI binds the action to list/kanban views, so this is always a single wizard instance. If called programmatically on a multi-record wizard, an `AccessError` is raised.

**L4 Performance - Batch Creation:** Creating debit notes for N invoices in a single wizard invocation results in N `move.copy()` calls. Each `copy()` is a full ORM create + write operation with line duplication. For large batches, consider:
- Line duplication (`copy_lines=True`) multiplies the number of line records created
- The transaction holds locks on the sequence until commit
- Consider breaking large batches into smaller groups

**L4 `include_business_fields=True` Context:** The context key `include_business_fields=True` is passed to `copy()`. This ensures business fields (like `partner_id`, `invoice_line_ids`, `sale_line_ids` links, `purchase_id` on the inverse side) are included in the copy. Without this context, only technical fields are copied and the debit note loses its commercial relationships.

**L3 Edge Case - Empty `move_ids`:** If the wizard was opened without any valid moves (e.g., empty `active_ids`), the `for` loop never executes and `new_moves` remains an empty recordset. The returned action has `view_mode: 'list,form'` and `domain: [('id', 'in', [])]`, which shows an empty list. This is a graceful no-op.

**L4 Reconciliation After-Creation:** The created debit notes are independent posted documents. They are not automatically reconciled with the original invoice. Users must manually create reconciliation entries via the reconciliation widget if needed. This is intentional: debit notes and original invoices may have different amounts, line structures, or tax treatments.

---

## L3: Cross-Model Relations, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Model: Account ↔ Debit Note Flow

```
account.move (original invoice)
    └─ debit_origin_id (Many2one) ──────────────────────────────────┐
    └─ debit_note_ids (One2many) ───┐                               │
                                   │ inverse                        │
                                   ▼                               │
account.move (debit note)          ┌───────────────────────────────┘
    debit_origin_id ───────────────┘
    move_type: inverted if original was refund

account.journal
    └─ debit_sequence (Boolean) ──→ controls _get_last_sequence_domain() filter
                                    and _get_starting_sequence() "D" prefix

account.debit.note (wizard)
    └─ move_ids (Many2many) ──────→ selected invoices to debit
    └─ journal_id (Many2one) ──────→ journal for debit notes
```

### Workflow Trigger: Debit Note Creation from Invoice

```
Original invoice posted (state = 'posted')
    │
    ├─ "Debit Note" button visible (in_invoice, out_invoice, in_refund, out_refund)
    │
    └─ Wizard opens
          ├─ Validates: posted, not already debited, valid move type
          ├─ Creates copy() with debit_origin_id set
          │     ├─ Type: inverts for refunds
          │     ├─ Reference: appended with reason
          │     ├─ Date: wizard's date (for tax period correctness)
          │     └─ Lines: empty by default (optional copy)
          │
          └─ Returns to debit note (state = draft)
                ├─ User edits debit note (lines, amounts)
                └─ User posts debit note (action_post)
```

### Override Patterns

1. **`_get_last_sequence_domain()`** — adds SQL filter for `debit_origin_id IS NOT NULL/NULL` when `journal.debit_sequence = True`
2. **`_get_starting_sequence()`** — prepends `"D"` prefix to debit note sequence
3. **`_get_copy_message_content()`** — replaces duplication message with debit note origin link in chatter

### Failure Modes

| Scenario | Behavior | Mitigation |
|----------|----------|------------|
| Deleting original invoice after debit note is created | Creates orphaned `debit_origin_id` reference | Odoo's unlink guard on posted moves prevents this |
| Debit note created from a draft invoice | `UserError: You can only debit posted moves` in `default_get()` | Users must post the invoice first |
| Debit note from an already-debited invoice | `UserError: You can't make a debit note for an invoice already linked to a debit note` | User must create debit note from the existing debit note |
| Mixed move types in wizard | `move_type` computed as `False`, `journal_type` falls back to `'sale'` | Mixed-type batches may show incorrect journal filter |
| Zero `active_ids` | Wizard opens with empty `move_ids`; `create_debit()` is a no-op | UI normally prevents this |
| Foreign currency invoice | Debit note inherits currency | Correct for reconciliation |
| Debit note date in different fiscal period | Recorded in the new period via `date`/`invoice_date` | Correct for tax reporting |
| Concurrent debit note creation | Sequence locking prevents gaps/double-assignment | Safe for multi-user |
| Bank/cash journal selected in wizard | Not possible — `journal_type` filter limits to sale/purchase | Correct by design |
| Credit note debit (refund reversal) | Type is reversed: `out_refund` becomes `out_invoice` | Correct — the debit note cancels the credit note |
| Large batch (50+ invoices) | N individual `copy()` calls within one transaction | May cause long transaction; consider batching |

---

## L4: Version Changes, Security, Journaling of Debit Notes

### Odoo 18 to Odoo 19 Changes

| Feature | Change |
|---------|--------|
| `debit_sequence` field | Introduced in Odoo 18, unchanged in Odoo 19 |
| `_get_copy_message_content()` | Method added/refined in Odoo 18/19 copy messaging refactor |
| `index='btree_not_null'` | Partial index pattern was introduced in Odoo 18/19 for ORM-level index optimization |
| Wizard hotkey | `data-hotkey="shift+d"` on the Debit Note button for quick keyboard access |
| Filter views | All three filter extensions (move, invoice, line) are new or significantly enhanced in Odoo 18/19 compared to earlier versions |
| `_get_starting_sequence()` | `"D"` prefix was formalized in Odoo 18 when `debit_sequence` was added |
| `move_type` computation | The `False` fallback for mixed-type batches was made explicit in Odoo 18/19 |

**Overall:** The module is stable across Odoo 18 and 19 with minimal structural changes, reflecting mature functionality.

**L4 Localization Note:** The `country_code` field on the wizard (related to `move_ids.company_id.country_id.code`) was added to support country-specific debit note requirements. Some jurisdictions mandate specific debit note numbering, reference formats, or tax treatment. This field provides the hook for localization modules to conditionally adjust behavior based on the company's country.

**L4 Sequence Per-Journal vs Per-Company:** The `debit_sequence` feature operates at the **journal level** (not company level). This means:
- A sale journal with `debit_sequence=True` gives debit notes a separate `"D"` prefixed branch
- A purchase journal with `debit_sequence=True` gives vendor debit notes a separate branch
- Different journals within the same company can have different `debit_sequence` settings
- The `ir.sequence` for each journal is created with `company_id` set, scoping it to the journal's company

### Security

#### Access Control (`security/ir.model.access.csv`)

```
"id","name","model_id:id","group_id:id","perm_read","perm_write","perm_create","perm_unlink"
"access_account_debit_note_user","account_debit_note_group_invoice","model_account_debit_note","account.group_account_invoice",1,1,1,0
```

| Permission | Value | Meaning |
|-----------|-------|---------|
| `perm_read` | 1 | Users with `account.group_account_invoice` can read wizard records |
| `perm_write` | 1 | Users can write wizard records (e.g., set date, reason) |
| `perm_create` | 1 | Users can create wizard records (opening the wizard) |
| `perm_unlink` | 0 | Transient wizard records are auto-cleaned by Odoo; no manual unlink |

**L4 Why No `unlink`:** Transient models are automatically purged by the `ir.autovacuum` model based on `transient_expire_seconds` (default: 7 days, configurable via system parameter `ir_autovacuum.transient_expire_seconds`). Manual unlink ACL is correctly set to 0 because transient records should never need manual deletion.

**L3 Field-Level ACL:** The wizard's `move_ids` field is restricted by the domain `[('state', '=', 'posted')]` and by the user's ACL on `account.move`. Users who cannot read a particular invoice will not be able to select it, and the `default_get()` validation will skip inaccessible records silently (the `browse()` call may return fewer records than `active_ids` if record rules filter them out). In practice, this means the debit note wizard respects existing invoice-level ACLs.

**L3 Button Group Restriction:** The Debit Note button on the invoice form requires `account.group_account_invoice`. This is the same group required for posting invoices and creating credit notes, ensuring only accounting staff can issue debit notes.

**L4 Audit Trail Security:** The `debit_origin_id` field is `readonly=True`, preventing users from manually unlinking a debit note from its origin. This preserves the audit trail. Additionally, `copy=False` prevents accidental duplication that could break the audit chain.

**L4 SQL Injection Safety:** Both `_get_last_sequence_domain()` and the wizard's SQL-safe operations use parameterized queries. The sequence domain override uses hardcoded SQL fragments (`"NOT NULL"` / `"NULL"`), which are safe. No user-supplied values are concatenated into SQL strings.

**L4 Record Rule Interaction:** When debit notes are created, they are subject to the standard `account.move` record rules. If record rules restrict which moves a user can see (e.g., multi-company, department-level restrictions), the same restrictions apply to debit notes created from those moves. The `debit_origin_id` link remains valid even if record rules would normally filter out the original invoice — the debit note itself is accessible if the user has rights to it.

### Journaling of Debit Notes

Debit notes in Odoo are `account.move` records with specific `move_type` values. Understanding how they flow through the journal is critical for correct accounting treatment.

#### Journal Entry Classification

| Original Type | Debit Note Type | Journal Behavior |
|-------------|----------------|-----------------|
| `out_invoice` (customer invoice) | `out_invoice` (customer debit note) | Same sale journal; affects accounts receivable |
| `in_invoice` (vendor bill) | `in_invoice` (vendor debit note) | Same purchase journal; affects accounts payable |
| `out_refund` (customer credit note) | `out_invoice` (customer debit note) | Same sale journal; cancels the credit note effect |
| `in_refund` (vendor credit note) | `in_invoice` (vendor debit note) | Same purchase journal; cancels the credit note effect |

**Key insight:** Debit notes of credit notes (refunds) have their **type inverted back to an invoice**. This is the "cancel a credit note" use case: a credit note reduced a vendor payable or customer receivable, and the debit note restores or increases it.

#### Accounting Impact

When a debit note is **posted**, it creates journal entries that affect:

- **Customer debit note (`out_invoice`):**
  - Debit: Accounts Receivable (the same receivable account as the original invoice)
  - Credit: Revenue or relevant adjustment account
  - The receivable is increased/created, reversing the effect of any credit note

- **Vendor debit note (`in_invoice`):**
  - Debit: Expense or relevant adjustment account
  - Credit: Accounts Payable (the same payable account as the original bill)
  - The payable is increased/created, reversing the effect of any credit note

The **accounts receivable/payable lines** use the same account as the original invoice because `copy()` preserves the account assignments from the original move lines. This ensures the receivable/payable balance correctly reflects the total owed to/from the partner across the original invoice and all debit/credit notes.

#### Journal Sequence and Numbering

The `_get_last_sequence_domain()` and `_get_starting_sequence()` overrides work with the journal's `ir.sequence` to produce debit note numbers. There are two modes:

**Mode 1: Shared sequence (`debit_sequence=False`, default)**
```
Original:  INV/2026/00001
Debit:     INV/2026/00002   (shares sequence with regular invoices)
```
Debit notes are numbered consecutively with regular invoices. The `debit_origin_id` field distinguishes them in queries and reporting, but numbering is interleaved.

**Mode 2: Dedicated sequence (`debit_sequence=True`, sale/purchase journals)**
```
Original:  INV/2026/00001
Second:    INV/2026/00002
Debit:     D/INV/2026/00001  (separate "D" branch)
Second debit: D/INV/2026/00002
```
The `"D"` prefix on debit notes makes them immediately distinguishable in reports and bank statements. Regular invoices and debit notes consume separate sequence branches.

**L4 Why "D" Prefix Only for Regular Invoices:** The `"D"` prefix is only prepended when `move_type in ("in_invoice", "out_invoice")`. Debit notes of refunds (where the type is inverted to an invoice type) also pass this condition, so they do get the `"D"` prefix. The exclusion is implicit: refund-type debit notes are type-corrected to invoice types in `_prepare_default_values()`, so they also enter the `"D"` prefix logic.

#### Reconciliation After Posting

After a debit note is posted, it can be reconciled with the original invoice using Odoo's manual reconciliation widget (`account.reconciliation.widget`). This is the key step for proper receivable/payable management:

- Customer invoice + debit note + payment = net balance
- Vendor bill + debit note + payment = net balance

**L4 Reconciliation is Not Automatic:** The wizard does not automatically reconcile the debit note with the original invoice because:
1. Debit notes often have different amounts (adjustments for different line items)
2. Tax treatment may differ between the original and the debit note
3. The debit note may need to be partially reconciled with multiple invoices

Users must manually reconcile via the reconciliation widget, which creates `account.partial.reconcile` records linking the move lines.

#### Tax Reporting Considerations

The `invoice_date` field on the debit note (set to the wizard's `date`) determines the tax reporting period. In many jurisdictions:
- Tax is due based on the invoice date (invoice-based VAT systems like EU)
- The debit note's date determines the adjustment period (Brazil, India, etc.)
- The original invoice remains unchanged; the debit note is a separate adjustment document

**L4 Tax Engine Interaction:** The `account.move.line` records copied from the original (when `copy_lines=True`) carry their original tax IDs. If the debit note has different lines or amounts, the tax computation engine recalculates taxes based on the new values and dates. Tax reports that aggregate by period will include the debit note in the period matching the wizard's date, independent of the original invoice's period.

#### Filter Views for Debit Note Reporting

The module adds three search filters to help identify and report on debit notes:

| Filter | View | Domain |
|--------|------|--------|
| `debit_note_filter` | `account.move` search | `[('debit_origin_id', '!=', False)]` |
| `debit_note_filter` | `account.move.line` search | `[('move_id.debit_origin_id', '!=', False)]` |
| `debit_note_filter` | Invoice selection search | `[('debit_origin_id', '!=', False)]` |

**L4 Filter Performance:** The filter on `move_id.debit_origin_id` in the line search view requires a join from `account_move_line` to `account_move` to evaluate. On large databases, this can be slow. The `btree_not_null` partial index on `debit_origin_id` helps but does not eliminate the join cost. For high-volume environments, consider adding a stored boolean field `is_debit_note` on `account.move.line` that mirrors `debit_origin_id IS NOT NULL`, enabling an index-only scan.

---

## Views and UI

### Wizard Form (`wizard/account_debit_note_view.xml`)

The wizard form has two columns:
- **Left group:** `reason`, `date`, `copy_lines` (conditional)
- **Right group:** `journal_id` (domain-filtered by computed `journal_type`)

**Hotkeys:**
- `Ctrl+Q` / `Q`: Create Debit Note (`create_debit`)
- `Ctrl+X` / `X`: Cancel (built-in `special='cancel'`)

The wizard opens in modal mode (`target='new'`) and is bound to `account.move` via `binding_model_id` and `binding_view_types`. It appears in the "Action" menu when one or more posted invoices/credit notes are selected in the list or kanban view.

### Invoice Form Extension (`views/account_move_view.xml`)

**Stat Button:** The `action_view_debit_notes` button is only visible when `debit_note_count > 0`. This avoids showing an empty stat button.

```xml
<button type="object" class="oe_stat_button" name="action_view_debit_notes"
        icon="fa-plus" invisible="debit_note_count == 0">
```

**Debit Note Button:** A primary action button next to the Reverse button, visible only for posted invoices and refunds:

```xml
<button name="action_debit_note" string='Debit Note'
        type='object' groups="account.group_account_invoice"
        invisible="move_type not in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund') or state != 'posted'"
        data-hotkey="shift+d"/>
```

Hotkey `Shift+D` opens the debit note wizard directly from the keyboard.

**Invisible `debit_origin_id`:** The original invoice debited field is shown on the debit note itself but hidden on the original invoice (where it is always `False`).

### Filter Views

Three filter views extend their respective search views:
- `view_account_move_filter_debit`: Adds "Debit Note" filter to the move search
- `view_account_invoice_filter_debit`: Adds "Debit Notes" filter to the invoice selection search
- `view_account_move_line_filter_debit`: Adds "Debit Note" filter to the move line search (uses `move_id.debit_origin_id` path)

All use the same domain: `[('debit_origin_id', '!=', False)]`.

**L4 Filter Performance:** The filter on `move_id.debit_origin_id` in the line search view requires a join from `account_move_line` to `account_move` to evaluate. On large databases, this can be slow. The `btree_not_null` partial index on `debit_origin_id` helps but does not eliminate the join cost.

---

## Wizard Lifecycle

**Creation:** Transient model records are created when the wizard form is opened (via `action_view_account_move_debit`).
**Population:** `default_get()` is called to pre-populate `move_ids` from `active_ids`.
**User Input:** User fills in date, reason, journal (optional), and copy_lines (optional).
**Execution:** `create_debit()` calls `move.copy()` for each selected invoice.
**Cleanup:** The wizard record is left as a stale transient. Odoo's autovacuum process purges it after `transient_expire_seconds` (default: 7 days, configurable via system parameter `ir_autovacuum.transient_expire_seconds`).

---

## Edge Cases and Failure Modes

| Scenario | Behavior | Mitigation |
|----------|----------|------------|
| Deleting original invoice after debit note is created | Creates orphaned `debit_origin_id` reference | Odoo's unlink guard on posted moves prevents this under normal use |
| Debit note created from a draft invoice | `UserError: You can only debit posted moves` in `default_get()` | Users must post the invoice first |
| Debit note from an already-debited invoice | `UserError: You can't make a debit note for an invoice already linked to a debit note` | User must create debit note from the existing debit note |
| Mixed move types in wizard | `move_type` computed as `False`, `journal_type` falls back to `'sale'` | Mixed-type batches may show incorrect journal filter; users should batch by type |
| Zero `active_ids` | Wizard opens with empty `move_ids`; `create_debit()` is a no-op | UI normally prevents this (wizard opened from context menu) |
| Foreign currency invoice | Debit note inherits currency | Correct — amounts remain comparable for reconciliation |
| Debit note date in different fiscal period | Recorded in the new period via `date`/`invoice_date` | Correct for tax reporting in period-based tax systems |
| Concurrent debit note creation | Sequence locking prevents gaps/double-assignment | Safe for multi-user environments |
| Bank/cash journal selected in wizard | Not possible — `journal_type` filter limits to sale/purchase | Correct by design |
| Credit note debit (refund reversal) | Type is reversed: `out_refund` becomes `out_invoice` | Correct — the debit note cancels the credit note |
| Large batch (50+ invoices) | N individual `copy()` calls within one transaction | May cause long transaction; consider batching |

---

## Tests (`tests/test_out_debit_note.py`)

| Test | Coverage |
|------|----------|
| `test_00_debit_note_out_invoice` | Creates debit note from posted customer invoice with `copy_lines=True`; verifies: 2 lines copied, `move_type` preserved, state is draft |
| `test_10_debit_note_in_refund` | Creates debit note from posted vendor refund with default options; verifies: no lines copied, `move_type` inverted to `in_invoice`, state is draft |
