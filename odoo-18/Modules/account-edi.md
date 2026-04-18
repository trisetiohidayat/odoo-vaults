---
Module: account_edi
Version: Odoo 18
Type: Core/Integration
Tags: #odoo18 #edi #account #e-invoicing #ubl #peppol
---

# account_edi — EDI Core (Electronic Document Exchange)

**Addon path:** `~/odoo/odoo18/odoo/addons/account_edi/`
**Purpose:** Provides the core EDI infrastructure for Odoo's accounting module. Every other EDI format (UBL, Peppol, Factur-X, etc.) inherits from `account.edi.format` and `account.edi.document`. This module handles the document lifecycle, attachment generation, web-service dispatch, and error/retry mechanics.

## Architecture Overview

```
account.move (posted)
    └── account.edi.document (one per (move, format) pair)
            └── account.edi.format (UBL, Peppol, Factur-X, ...)
                    └── ir.attachment (generated XML file)
```

EDI processing is split between synchronous (no web service) and asynchronous (web service) modes. The `_cron_edi_network` cron job drives the async queue.

---

## Model: `account.edi.document`

Electronic document attached to an `account.move`. Represents the state of one EDI format for one invoice.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `move_id` | Many2one `account.move` | Required, cascade delete, indexed |
| `edi_format_id` | Many2one `account.edi.format` | Required |
| `attachment_id` | Many2one `ir.attachment` | System-readable; file generated at post time |
| `state` | Selection | `to_send`, `sent`, `to_cancel`, `cancelled` |
| `error` | Html | Last error message from EDI operation |
| `blocking_level` | Selection | `info`, `warning`, `error` — controls whether the document blocks the cron |
| `name` | Char (related) | Synced from `attachment_id.name` |
| `edi_format_name` | Char (related) | Synced from `edi_format_id.name` |
| `edi_content` | Binary (compute, sudo) | Base64-encoded preview of the EDI file for `to_send`/`to_cancel` states |

### SQL Constraints

```python
'unique_edi_document_by_move_by_format'
'UNIQUE(edi_format_id, move_id)'
# Only one edi document per move per format
```

### Key Methods

#### `_prepare_jobs()`
Groups documents into processing jobs. Documents with the same `(edi_format, state, company_id)` are batched together if the format supports batching. Returns a list of dicts: `{'documents': recordset, 'method_to_call': str}`.

Batching key construction:
```python
batching_key = [edi_format, state, move.company_id]
# + custom_batching_key from move_applicability (if format supports it)
# otherwise: move.id  (no batching — one job per document)
```

#### `_process_job(job)`
Executes a single job. Distinguishes `to_send` vs `to_cancel` flows.

**Post flow** (`to_send`):
```python
with moves._send_only_when_ready():
    edi_result = method_to_call(moves)   # calls format's 'post' method
_postprocess_post_edi_results(documents, edi_result)
```
- If `success is True`: writes `state='sent'`, `error=False`, `blocking_level=False`
- If error present: writes `error` message and `blocking_level` (default: `'error'`)
- If `move_result['attachment']`: replaces `document.sudo().attachment_id`; old orphaned attachment is unlinked

**Cancel flow** (`to_cancel`):
```python
edi_result = method_to_call(moves)
_postprocess_cancel_edi_results(documents, edi_result)
```
- If `success is True`: sets `state='cancelled'`, clears `attachment_id`
- If all formats for the move are cancelled or don't need web services, the move is auto-cancelled (set to draft, then cancelled)
- Orphaned (unlinked) attachments are deleted

#### `_process_documents_no_web_services()`
Called inline during `move._post()`. Filters to formats where `_needs_web_services() = False` and processes immediately. No locking needed.

#### `_process_documents_web_services(job_count=None, with_commit=True)`
Called by cron. Uses `FOR UPDATE NOWAIT` row locking on `account_edi_document` and `account_move` rows to prevent concurrent processing. Commits after each job if `with_commit=True` and more than one job.

Returns the number of remaining jobs; if > 0, retriggers the cron immediately.

```python
# Locks acquired before _process_job:
SELECT * FROM account_edi_document WHERE id IN %s FOR UPDATE NOWAIT
SELECT * FROM account_move WHERE id IN %s FOR UPDATE NOWAIT
SELECT * FROM ir_attachment WHERE id IN %s FOR UPDATE NOWAIT  # if attachments may be unlinked
```

#### `_filter_edi_attachments_for_mailing()`
Returns attachment info for linking into emails. Overridable (e.g., for ZIP files).

```python
# Returns dict:
{'attachment_ids': [attachment_id]}   # existing attachment is linked (no new one created)
{'attachments': [(name, base64_content)]}  # new attachment created on send
```

Returns `{}` if: no attachment, attachment is system-only (no res_model/res_id), or mass-mail mode.

#### `action_export_xml()`
Opens the EDI file preview by returning an `ir.actions.act_url` to `/web/content/account.edi.document/{id}/edi_content`.

---

## Model: `account.edi.format`

Abstract base for EDI format definitions (UBL 2.1, Peppol BIS 3.0, Factur-X, etc.). Each format implementor overrides `_get_move_applicability`, `post`, `cancel`, and optionally `edi_content`.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Display name |
| `code` | Char | Unique identifier, e.g. `'ubl_21'`, `'peppol'` |

### SQL Constraints

```python
'unique_code' 'UNIQUE(code)'
```

### Hook Methods (Override Points)

#### `_get_move_applicability(move) -> dict | None`
Core method. Returns `None` if the format is not applicable. Otherwise returns a dict of callables:

```python
{
    'post': lambda moves: {...},          # called for state='to_send'
    'cancel': lambda moves: {...},       # called for state='to_cancel'
    'post_batching': lambda move: (...),  # optional: custom batching key tuple
    'cancel_batching': lambda move: (...),
    'edi_content': lambda move: b'...'   # optional: content for preview/download
}
```

#### `_needs_web_services() -> bool`
Override `True` for async formats (Peppol, Chorus, etc.). Default `False` (synchronous).

#### `_is_compatible_with_journal(journal) -> bool`
Controls which journals show this format in the "Electronic invoicing" dropdown. Default: `journal.type == 'sale'`.

#### `_is_enabled_by_default_on_journal(journal) -> bool`
If `True`, the format is auto-selected on matching journals at install time.

#### `_check_move_configuration(move) -> list[str]`
Pre-flight validation. Returns a list of error messages. Called before document creation in `move._post()`. If errors exist, posting is blocked with `UserError`.

#### `_prepare_invoice_report(pdf_writer, edi_document)`
Override to embed the EDI attachment into the printed PDF. Called from `ir.actions.report._render_qweb_pdf_prepare_streams`.

### Registration Hook

```python
def _register_hook(self):
    # Runs after all modules are loaded
    # Delays journal EDI recompute if registry not fully loaded
    if hasattr(pool, "_delay_compute_edi_format_ids"):
        del pool._delay_compute_edi_format_ids
        journals = self.env['account.journal'].search([])
        journals._compute_edi_format_ids()
```

On format creation, if any format needs web services, the `ir_cron_edi_network` cron is activated.

---

## Model: `account.move` (Extension)

All EDI state is aggregated here from `edi_document_ids`.

### Added Fields

| Field | Type | Notes |
|-------|------|-------|
| `edi_document_ids` | One2many `account.edi.document` | All EDI docs for this move |
| `edi_state` | Selection (store, compute) | Aggregated: `'sent'` only if ALL WS docs are sent; `'to_cancel'` if ANY is to_cancel; etc. |
| `edi_error_count` | Integer (compute) | Count of docs with non-False `error` |
| `edi_error_message` | Html (compute) | Single error or `"N Electronic invoicing error(s)"` |
| `edi_blocking_level` | Selection (compute) | `'error'` if any error, else `'warning'`, else `'info'` |
| `edi_web_services_to_process` | Text (compute) | Comma-joined format names pending async processing |
| `edi_show_cancel_button` | Boolean (compute) | `True` if posted move has any `sent` doc with a `cancel` method |
| `edi_show_abandon_cancel_button` | Boolean (compute) | `True` if any `to_cancel` doc has a `cancel` method |
| `edi_show_force_cancel_button` | Boolean (compute) | `True` if `_can_force_cancel()` returns True |

### State Machine for `edi_state`

```
All WS docs state={'sent'}        → edi_state='sent'
All WS docs state={'cancelled'}   → edi_state='cancelled'
'to_send' in states              → edi_state='to_send'
'to_cancel' in states             → edi_state='to_cancel'
(all cancelled, no WS)           → edi_state=False
```

### Key Method: `_post()` (Override)

The most important integration point. Called when a move is posted.

```python
def _post(self, soft=True):
    posted = super()._post(soft=soft)          # persist the move first
    for move in posted:
        for edi_format in move.journal_id.edi_format_ids:
            move_applicability = edi_format._get_move_applicability(move)
            if not move_applicability:
                continue
            # Validate before creating doc
            errors = edi_format._check_move_configuration(move)
            if errors:
                raise UserError("Invalid invoice configuration:\n" + '\n'.join(errors))
            # Create or reset doc to 'to_send'
            existing = move.edi_document_ids.filtered(lambda x: x.edi_format_id == edi_format)
            if existing:
                existing.sudo().write({'state': 'to_send', 'attachment_id': False})
            else:
                edi_document_vals_list.append({
                    'edi_format_id': edi_format.id,
                    'move_id': move.id,
                    'state': 'to_send',
                })
    self.env['account.edi.document'].create(edi_document_vals_list)
    posted.edi_document_ids._process_documents_no_web_services()
    self.env.ref('account_edi.ir_cron_edi_network')._trigger()  # async formats
    return posted
```

### Key Method: `button_cancel()` (Override)

```python
def button_cancel(self):
    res = super().button_cancel()
    # Non-sent docs → cancelled immediately
    self.edi_document_ids.filtered(lambda d: d.state != 'sent') \
        .write({'state': 'cancelled', 'error': False, 'blocking_level': False})
    # Sent docs → marked for cancellation (async)
    self.edi_document_ids.filtered(lambda d: d.state == 'sent') \
        .write({'state': 'to_cancel', 'error': False, 'blocking_level': False})
    self.edi_document_ids._process_documents_no_web_services()
    self.env.ref('account_edi.ir_cron_edi_network')._trigger()
    return res
```

### Key Method: `button_draft()` (Override)

```python
def button_draft(self):
    # BLOCKS if any sent EDI doc has a cancel method (can't undo sent government documents)
    if not move._edi_allow_button_draft():
        raise UserError("You can't edit... an electronic document has already been sent...")
    res = super().button_draft()
    self.edi_document_ids.write({'error': False, 'blocking_level': False})
    self.edi_document_ids.filtered(lambda d: d.state == 'to_send').unlink()
    return res
```

### `_retry_edi_documents_error_hook()`
Empty hook for subclasses to clean up state before retry. E.g., `account_peppol` clears `peppol_move_state`.

### `_prepare_edi_tax_details()`
Wraps `_prepare_invoice_aggregated_taxes()` with EDI-specific signature. Accepts `filter_to_apply`, `filter_invl_to_apply`, `grouping_key_generator`. Returns tax amounts grouped by tax or custom key, plus per-line breakdown.

---

## Model: `account.journal` (Extension)

### Added Fields

| Field | Type | Notes |
|-------|------|-------|
| `edi_format_ids` | Many2many `account.edi.format` | Active formats on this journal; domain filtered to `compatible_edi_ids` |
| `compatible_edi_ids` | Many2many (compute) | Formats that `_is_compatible_with_journal(journal)` returns True |

### `write()` Override — Deactivation Guard

```python
def write(self, vals):
    if vals.get('edi_format_ids'):
        old_edi_format_ids = self.edi_format_ids
        res = super().write(vals)
        diff_edi_format_ids = old_edi_format_ids - self.edi_format_ids
        documents = self.env['account.edi.document'].search([
            ('move_id.journal_id', 'in', self.ids),
            ('edi_format_id', 'in', diff_edi_format_ids.ids),
            ('state', 'in', ('to_cancel', 'to_send')),
        ])
        if documents.filtered(lambda d: d.edi_format_id._needs_web_services()):
            raise UserError("Cannot deactivate (%s) on this journal because not all documents are synchronized")
        if documents:
            documents.unlink()  # only unlinks non-WS format docs
        return res
    return super().write(vals)
```

Key insight: Formats needing web services **cannot be deactivated** if pending documents exist. Non-WS format documents are silently deleted.

---

## Model: `ir.actions.report` (Extension)

### `_render_qweb_pdf_prepare_streams()` Override

Embeds EDI XML attachments into the printed invoice PDF at the point of rendering.

```python
if invoice.is_sale_document() and invoice.state != 'draft':
    to_embed = invoice.edi_document_ids
    for edi_document in to_embed:
        edi_document.edi_format_id._prepare_invoice_report(writer, edi_document)
```

The EDI attachment is added to the PDF writer via the format's `_prepare_invoice_report` method.

---

## Model: `ir.attachment` (Extension)

### `_unlink_except_government_document()`

Prevents deletion of EDI attachments linked to documents with web-service formats:

```python
linked_edi_formats_ws = linked_edi_documents.edi_format_id.filtered(lambda edi_format: edi_format._needs_web_services())
if linked_edi_formats_ws:
    raise UserError("You can't unlink an attachment being an EDI document sent to the government.")
```

Also fires on `at_uninstall=False` (not just module uninstall), so government EDI files are protected permanently.

---

## Model: `account.move.send` (Extension)

### `_get_mail_attachment_from_doc(doc)`
Returns the `ir.attachment` from the EDI document if it is user-linked (has `res_model` and `res_id`). System-only attachments are skipped.

### `_get_invoice_extra_attachments(move)`
EXTENDS base `account`. Iterates `move.edi_document_ids`, appending each doc's attachment via `_get_mail_attachment_from_doc`. Result is included in the email composition wizard.

---

## Wizard: `ReSequenceWizard` (Extension)

The invoice resequence wizard is blocked if any of the target moves have EDI documents that are both `sent` and use a web service:

```python
def resequence(self):
    edi_sent_moves = self._frozen_edi_documents()
    if edi_sent_moves:
        raise UserError("The following documents have already been sent and cannot be resequenced: ...")
    return super().resequence()

def _frozen_edi_documents(self):
    return self.move_ids.edi_document_ids.filtered(
        lambda d: d.edi_format_id._needs_web_services() and d.state == "sent"
    )
```

---

## EDI Processing Flow

```
1. POST INVOICE
   move._post()
   └─> For each journal EDI format:
           edi_format._get_move_applicability(move)
           ├─> [NOT applicable] → skip
           └─> [applicable] → _check_move_configuration(move)
                               ├─> [errors] → UserError, block post
                               └─> [ok] → create account.edi.document (state='to_send')
   └─> edi_document_ids._process_documents_no_web_services()
           └─> _prepare_jobs() → _process_job() inline
                   └─> format's 'post' method (synchronous)
                       └─> write state='sent', create ir.attachment
   └─> ir_cron_edi_network._trigger()
           └─> async formats queued for cron

2. CRON RUN (ir_cron_edi_network)
   account.edi.document._cron_process_documents_web_services()
   └─> search documents with state in ('to_send', 'to_cancel'), move.state='posted', blocking_level!='error'
   └─> FOR UPDATE NOWAIT locks
   └─> _process_job() per batch
           └─> format's 'post' or 'cancel' method (async, e.g. Peppol API call)

3. CANCEL INVOICE
   move.button_cancel()
   └─> non-sent docs → state='cancelled'
   └─> sent docs → state='to_cancel'
   └─> _process_documents_no_web_services()
   └─> ir_cron_edi_network._trigger()

4. RETRY
   move.action_retry_edi_documents_error()
   └─> _retry_edi_documents_error_hook()  ← override point
   └─> write error=False, blocking_level=False
   └─> action_process_edi_web_services()
```

---

## L4: Adding a Custom EDI Format

To implement a new EDI format (e.g., a national e-invoicing standard):

### Step 1: Create the Format Record

In `data/`, `noupdate=True`:
```python
env['account.edi.format'].create({
    'name': 'My Format',
    'code': 'my_format',
})
```

### Step 2: Implement the Format Class

```python
from odoo import models

class AccountEdiMyFormat(models.Model):
    _name = 'account.edi.my_format'
    _inherit = 'account.edi.format'
    _description = 'My National Format'

    def _is_compatible_with_journal(self, journal):
        return journal.type == 'sale'

    def _needs_web_services(self):
        return True  # or False for synchronous

    def _get_move_applicability(self, move):
        # Only for sale invoices
        if move.move_type not in ('out_invoice', 'out_refund'):
            return
        return {
            'post': lambda moves: moves._my_format_generate_edi(),
            'cancel': lambda moves: moves._my_format_cancel_edi(),
            'post_batching': lambda move: (move.partner_id.id,),
            'edi_content': lambda move: move._my_format_generate_edi_content(),
        }
```

### Step 3: Implement Generation Methods on `account.move`

```python
def _my_format_generate_edi(self):
    # Must return dict: {move: {'success': True, 'attachment': ir_attachment}}
    result = {}
    for move in self:
        content = move._my_format_generate_edi_content()
        attachment = self.env['ir.attachment'].create({
            'name': f'{move.name}_myformat.xml',
            'raw': content,
            'type': 'binary',
            'res_model': 'account.move',
            'res_id': move.id,
        })
        result[move] = {'success': True, 'attachment': attachment}
    return result

def _my_format_generate_edi_content(self):
    # Return bytes (XML content)
    ...
```

### Step 4: Attachment Naming Convention

```
UBL 2.1:    {InvoiceName}_ubl_21.xml
Peppol:     {InvoiceName}_peppol.xml
Factur-X:   {InvoiceName}_xfacturx.pdf
Custom:     {InvoiceName}_myformat.xml
```

Attachment `res_model='account.move'` and `res_id=move.id` makes it visible to the UI and email composer.

### Step 5: Register Document Types with Peppol (if applicable)

If your format extends Peppol's document type list, call in `_post_init_hook`:

```python
AccountEdiProxyClientUser._peppol_auto_register_services('my_module')
```

On uninstall:
```python
AccountEdiProxyClientUser._peppol_auto_deregister_services('my_module')
```

---

## Cron: `ir_cron_edi_network`

- **Trigger:** Manual trigger after `_post()`, `button_cancel()`, or retry actions
- **Search domain:** `state IN ('to_send', 'to_cancel') AND move_id.state='posted' AND blocking_level!='error'`
- **Batch size:** Controlled by `job_count` param (default 50)
- **Retrigger:** If jobs remain after batch, cron is retriggered immediately

---

## Related Models

| Model | Module | Role |
|-------|--------|------|
| `account_edi_proxy_client.user` | `account_edi_proxy_client` | Holds auth tokens for web-service EDI (Peppol, Chorus) |
| `account.move` | `account` | The primary document; extensions in `account_edi`, `account_peppol`, etc. |
| `account.journal` | `account` | Holds `edi_format_ids` Many2many |
| `account_edi_proxy_client.user` | `account_peppol` | Extends with Peppol-specific crons and methods |
| `peppol.registration` | `account_peppol` | Onboarding wizard for Peppol participants |

---

## See Also

- [Modules/account-peppol](Modules/account-peppol.md) — Peppol e-invoicing via Odoo's Access Point
- [Modules/Account](Modules/account.md) — Core accounting, `account.move` lifecycle
- [Core/Fields](Core/Fields.md) — How Many2one, One2many, Binary fields work
