---
type: module
module: l10n_latam_invoice_document
tags: [odoo, odoo19, accounting, localization, latam, invoices, documents]
created: 2026-04-06
---

# LATAM Invoice Document Types (`l10n_latam_invoice_document`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Functional |
| **Technical** | `l10n_latam_invoice_document` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | ADHOC SA |
| **Version** | 1.0 |

## Description

In some Latin American countries, including Argentina and Chile, accounting transactions like invoices and vendor bills are classified by document types defined by government fiscal authorities (in Argentina, ARCA; in Chile, SII). These document types carry country-specific rules and sequential numbering that must be enforced for tax compliance.

This module is the base framework intended to be extended by country-specific localizations. It provides:
- The `l10n_latam.document.type` model for defining document types
- Extension of `account.move` with LATAM-specific fields and behaviors
- Journal-level configuration to enable/disable document type usage
- Automatic document type selection and number formatting

### Business Context

In LATAM countries, every invoice must carry a document type code assigned by the tax authority. The document type determines:
- The invoice numbering sequence (separate sequences per document type)
- Which account move types are valid (e.g., debit notes only for vendor bills)
- How the invoice is reported to tax authorities
- The printed report format

### How to Extend This Module

Localizations that need this functionality should:

1. Add this module as a dependency in their `__manifest__.py`
2. Extend the company's `_localization_use_documents()` method to return `True`
3. Create the `l10n_latam.document.type` records for the specific country
4. Each document type record has a `country_id` field linking it to the country

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Core accounting — provides `account.move`, journals |
| `account_debit_note` | Provides debit note support for document types |

## Architecture

### Models

```
l10n_latam.document.type    # Document type master data
    └─ account.move         # Extended with document type selection and numbering

account.journal             # Extended with l10n_latam_use_documents flag
res.company                 # Extended with _localization_use_documents() hook
```

### Document Type Internal Types

| Internal Type | Use Case |
|---------------|----------|
| `invoice` | Customer invoices and vendor bills |
| `credit_note` | Customer refunds and vendor bill reversals |
| `debit_note` | Debit memos to customers or from vendors |
| `all` | Generic document type for any move type |

## Models

### `l10n_latam.document.type`

Master data model for LATAM document types. Each localization creates document type records for their country.

**Inherited from:** `BaseModel` (no mixins)

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Whether the document type is active (default True) |
| `sequence` | Integer | Display ordering priority (default 10) |
| `country_id` | Many2one | Country where this document type is valid (required) |
| `name` | Char | Document type name (required, translatable) |
| `doc_code_prefix` | Char | Prefix for invoice numbers, e.g., `'FA '` produces `'FA 0001-0000001'` |
| `code` | Char | Code used by different localizations |
| `report_name` | Char | Name printed on reports (e.g., `'CREDIT NOTE'`) |
| `internal_type` | Selection | Type mapping to account.move types: `invoice`, `debit_note`, `credit_note`, `all` |

#### Method: `_format_document_number`

Hook for country-specific number formatting and validation:

```python
def _format_document_number(self, document_number):
    """ Method to be inherited by different localizations. The purpose of this
    method is to allow:
    * making validations on the document_number. If it is wrong it should raise
    * format the document_number against a pattern and return it
    """
    self.ensure_one()
    return document_number
```

#### Computed Display Name

```python
@api.depends('code')
def _compute_display_name(self):
    for rec in self:
        name = rec.name
        if rec.code:
            name = f'({rec.code}) {name}'
        rec.display_name = name
```

---

### `account.move` (inherited)

Core invoice journal entry model, extended with LATAM document type and numbering support.

**Extended by:** `l10n_latam_invoice_document`

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `l10n_latam_available_document_type_ids` | Many2many | Computed list of valid document types for this move |
| `l10n_latam_document_type_id` | Many2one | Selected document type (bypass_search_access, index btree_not_null) |
| `l10n_latam_document_number` | Char | The formatted document number (computed/inverse) |
| `l10n_latam_use_documents` | Boolean | Whether this move uses document types (search on journal) |
| `l10n_latam_manual_document_number` | Boolean | Whether numbering is manual vs automatic |
| `l10n_latam_document_type_id_code` | Char | Related code from document type |

#### Database Constraints

Two unique indexes ensure invoice number uniqueness:

```python
_unique_name = models.UniqueIndex(
    "(name, journal_id)"
    " WHERE (state = 'posted' AND name != '/'"
    " AND (l10n_latam_document_type_id IS NULL OR move_type NOT IN ('in_invoice', 'in_refund', 'in_receipt')))",
    "Another entry with the same name already exists.",
)
_unique_name_latam = models.UniqueIndex(
    "(name, commercial_partner_id, l10n_latam_document_type_id, company_id)"
    " WHERE (state = 'posted' AND name != '/'"
    " AND (l10n_latam_document_type_id IS NOT NULL AND move_type IN ('in_invoice', 'in_refund', 'in_receipt')))",
    "Another entry with the same name already exists.",
)
```

#### `_auto_init` — Column Creation

The module creates the `l10n_latam_document_type_id` column without triggering the compute method on installation (to avoid memory issues on large datasets):

```python
def _auto_init(self):
    if not column_exists(self.env.cr, "account_move", "l10n_latam_document_type_id"):
        create_column(self.env.cr, "account_move", "l10n_latam_document_type_id", "int4")
    return super()._auto_init()
```

The compute method only runs on draft invoices, so the column is populated when invoices are edited.

#### Key Compute Methods

**`_compute_l10n_latam_use_documents`** — Determines if the move's journal uses document types:
```python
@api.depends('journal_id')
def _compute_l10n_latam_use_documents(self):
    for rec in self:
        rec.l10n_latam_use_documents = rec.journal_id.l10n_latam_use_documents and rec.move_type != 'in_receipt'
```

**`_compute_l10n_latam_available_document_types`** — Computes valid document types based on move type, partner, and company country:
```python
@api.depends('journal_id', 'partner_id', 'company_id', 'move_type', 'debit_origin_id')
def _compute_l10n_latam_available_document_types(self):
    self.l10n_latam_available_document_type_ids = False
    for rec in self.filtered(lambda x: x.journal_id and x.l10n_latam_use_documents and x.partner_id):
        rec.l10n_latam_available_document_type_ids = self.env['l10n_latam.document.type'].search(
            rec._get_l10n_latam_documents_domain())
```

**`_compute_l10n_latam_document_type`** — Auto-selects first available document type for draft invoices:
```python
@api.depends('l10n_latam_available_document_type_ids')
def _compute_l10n_latam_document_type(self):
    for rec in self.filtered(lambda x: x.state == 'draft'
           and (not x.posted_before if x.move_type in ['out_invoice', 'out_refund'] else True)):
        document_types = rec.l10n_latam_available_document_type_ids._origin
        if rec.debit_origin_id:
            document_types = document_types.filtered(lambda x: x.internal_type == 'debit_note')
        if rec.l10n_latam_document_type_id not in document_types:
            rec.l10n_latam_document_type_id = document_types and document_types[0].id
```

**`_compute_l10n_latam_document_number`** — Extracts the document number from the full name:
```python
@api.depends('name')
def _compute_l10n_latam_document_number(self):
    recs_with_name = self.filtered(lambda x: x.name and x.name != "/")
    for rec in recs_with_name:
        name = rec.name
        doc_code_prefix = rec.l10n_latam_document_type_id.doc_code_prefix
        if doc_code_prefix and name:
            name = name.split(" ", 1)[-1]
        rec.l10n_latam_document_number = name
    remaining = self - recs_with_name
    remaining.l10n_latam_document_number = False
```

#### Onchange Methods

**`_inverse_l10n_latam_document_number`** — When user sets the document number, formats it and updates the name:
```python
@api.onchange('l10n_latam_document_type_id', 'l10n_latam_document_number', 'partner_id')
def _inverse_l10n_latam_document_number(self):
    for rec in self.filtered(lambda x: x.l10n_latam_document_type_id):
        if not rec.l10n_latam_document_number:
            rec.name = False
        else:
            l10n_latam_document_number = rec.l10n_latam_document_number
            if not rec._skip_format_document_number():
                l10n_latam_document_number = rec.l10n_latam_document_type_id._format_document_number(
                    rec.l10n_latam_document_number)
            if rec.l10n_latam_document_number != l10n_latam_document_number:
                rec.l10n_latam_document_number = l10n_latam_document_number
            rec.name = "%s %s" % (rec.l10n_latam_document_type_id.doc_code_prefix, l10n_latam_document_number)
```

**`_onchange_l10n_latam_document_type_id`** — When document type changes on a draft, resets the name to recompute it:
```python
@api.onchange('l10n_latam_document_type_id')
def _onchange_l10n_latam_document_type_id(self):
    if (self.l10n_latam_use_documents and self.l10n_latam_document_type_id
          and not self.l10n_latam_manual_document_number and self.state == 'draft' and not self.posted_before):
        self.name = False
        self._compute_name()
```

#### Name Computation Overrides

**`_compute_name`** — Changes how the move name is generated when using documents:
```python
@api.depends('l10n_latam_document_type_id')
def _compute_name(self):
    without_doc_type = self.filtered(lambda x: x.l10n_latam_use_documents and not x.l10n_latam_document_type_id)
    manual_documents = self.filtered(lambda x: x.l10n_latam_use_documents and x.l10n_latam_manual_document_number)
    (without_doc_type + manual_documents.filtered(lambda x: not x.name)).name = False
    # Group by document type for sequence assignment
    group_by_document_type = defaultdict(self.env['account.move'].browse)
    for move in (self - without_doc_type - manual_documents):
        group_by_document_type[move.l10n_latam_document_type_id.id] += move
    for group in group_by_document_type.values():
        super(AccountMove, group)._compute_name()
```

#### Sequence Control

**`_deduce_sequence_number_reset`** — Never resets sequence for document-type moves:
```python
@api.model
def _deduce_sequence_number_reset(self, name):
    if self.l10n_latam_use_documents:
        return 'never'
    return super()._deduce_sequence_number_reset(name)
```

**`_get_last_sequence_domain`** — Disables anti-regex constraint for document-type moves:
```python
def _get_last_sequence_domain(self, relaxed=False):
    no_anti_regex = False
    if self.l10n_latam_use_documents:
        no_anti_regex = True
    where_string, param = super()._get_last_sequence_domain(
        self.with_context(no_anti_regex=no_anti_regex))._get_last_sequence_domain(relaxed)
    return where_string, param
```

#### Constraints

**`_check_l10n_latam_documents`** — Validates posted invoices have document types and numbers:
```python
@api.constrains('state', 'l10n_latam_document_type_id')
def _check_l10n_latam_documents(self):
    validated_invoices = self.filtered(lambda x: x.l10n_latam_use_documents and x.state == 'posted')
    without_doc_type = validated_invoices.filtered(lambda x: not x.l10n_latam_document_type_id)
    if without_doc_type:
        raise ValidationError(_(
            'The journal require a document type but not document type has been selected on invoices %s.',
            without_doc_type.ids
        ))
    without_number = validated_invoices.filtered(
        lambda x: not x.l10n_latam_document_number and x.l10n_latam_manual_document_number)
    if without_number:
        raise ValidationError(_(
            'Please set the document number on the following invoices %s.',
            without_number.ids
        ))
```

**`_check_invoice_type_document_type`** — Validates document type is compatible with move type:
```python
@api.constrains('move_type', 'l10n_latam_document_type_id')
def _check_invoice_type_document_type(self):
    for rec in self.filtered('l10n_latam_document_type_id.internal_type'):
        internal_type = rec.l10n_latam_document_type_id.internal_type
        invoice_type = rec.move_type
        if internal_type in ['debit_note', 'invoice'] and invoice_type in ['out_refund', 'in_refund']:
            raise ValidationError(_('You can not use a %s document type with a refund invoice', internal_type))
        elif internal_type == 'credit_note' and invoice_type in ['out_invoice', 'in_invoice']:
            raise ValidationError(_('You can not use a %s document type with a invoice', internal_type))
```

#### Post Validation

**`_post`** — Blocks receipt types with document types:
```python
def _post(self, soft=True):
    for rec in self.filtered(lambda x: x.l10n_latam_use_documents and (not x.name or x.name == '/')):
        if rec.move_type in ('in_receipt', 'out_receipt'):
            raise UserError(_('We do not accept the usage of document types on receipts yet.'))
    return super()._post(soft)
```

## Business Flows

### Invoice Numbering Flow

1. User creates invoice in a LATAM journal
2. `l10n_latam_use_documents` is computed from journal settings
3. Available document types computed based on partner country and move type
4. If draft, document type auto-selected (first available)
5. If auto-numbering → sequence assigns name on post (e.g., `FA 0001-0000001`)
6. If manual numbering → user enters document number → name constructed from prefix + number

### Document Type Selection Logic

The available document types depend on:
- **Move type**: `out_invoice`/`in_invoice` → `invoice` or `debit_note`; `out_refund`/`in_refund` → `credit_note`
- **Debit origin**: If linked to a debit note, only `debit_note` types available
- **Company country**: Document type must match company's fiscal country

```python
def _get_l10n_latam_documents_domain(self):
    self.ensure_one()
    internal_types = []
    invoice_type = self.move_type
    if invoice_type in ['out_refund', 'in_refund']:
        internal_types = ['credit_note']
    elif invoice_type in ['out_invoice', 'in_invoice']:
        internal_types = ['invoice', 'debit_note']
    if self.debit_origin_id:
        internal_types = ['debit_note']
    internal_types += ['all']
    return [('internal_type', 'in', internal_types),
            ('country_id', '=', self.company_id.account_fiscal_country_id.id)]
```

## Technical Notes

- **No receipt support**: `in_receipt` and `out_receipt` move types cannot use document types
- **Manual vs automatic**: Purchase journals use manual numbering; sale journals typically use sequences
- **Number format**: Document number formatting is delegated to the localization via `_format_document_number`
- **Partner-based uniqueness**: Vendor bills are unique per partner + document type + company
- **Prefix stripping**: The prefix is stripped when displaying the document number separately

## Related

- [Modules/Account](Account.md) - Core accounting module
- [Modules/l10n_latam_check](l10n_latam_check.md) - LATAM check management
- [Patterns/Workflow Patterns](Workflow Patterns.md) - State machine patterns
