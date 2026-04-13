---
title: Account EDI
description: Base module for Electronic Data Interchange in invoicing. Manages EDI document lifecycle, web service processing, error tracking, PDF embedding, and proxy-based asynchronous transmission.
tags: [odoo19, accounting, edi, invoicing, module, pdf-embedding, proxy]
model_count: 10
models:
  - account.edi.document (EDI document per move/format)
  - account.edi.format (EDI format definition interface)
  - account.journal (edi_format_ids, compatible_edi_ids)
  - account.move (edi_state, edi_document_ids, export/cancel methods)
  - account.move.send (extra EDI attachments in email)
  - ir.attachment (prevent unlink of government-sent EDI)
  - ir.actions.report (PDF embedding of EDI)
  - account_edi_proxy_client.user (base proxy user model)
  - account_edi_proxy_client.user (Peppol extension)
  - account.resequence.wizard (blocked for sent EDI)
dependencies:
  - account
  - account_edi_proxy_client (separate addon)
  - account_peppol (extends proxy user)
category: Accounting/Accounting
source: odoo/addons/account_edi/
related_modules:
  - account_edi_proxy_client (proxy HTTP client base)
  - account_peppol (Peppol EDI format)
  - l10n_my_edi (Malaysia MyInvois)
  - l10n_dk_nemhandel (Denmark NemHandel)
created: 2026-04-06
updated: 2026-04-11
---

# Account EDI

**Module:** `account_edi`
**Category:** Accounting / Accounting
**Depends:** `account`
**License:** LGPL-3
**Odoo Version:** 19

---

## Overview

`account_edi` is the foundational Electronic Data Interchange (EDI) framework for Odoo. It provides:

- A **document lifecycle engine** for tracking EDI state per invoice per format
- An **abstract format interface** that country-specific modules implement (Peppol, UBL, Factur-X, etc.)
- **Dual-mode processing**: synchronous (no web service) and asynchronous (via cron + HTTP)
- **Error severity tracking** with blocking levels that control retry behavior
- **PDF report embedding** of EDI attachments into printed invoices
- **Attachment protection** preventing deletion of government-archived documents
- **Proxy-based communication** via `account_edi_proxy_client` for formats requiring secure HTTPS channels

The module is intentionally minimal and serves as a neutral framework. All format-specific logic (UBL generation, Peppol API calls, tax calculations, etc.) lives in dedicated localization modules.

---

## Key Architectural Decisions

### Odoo 18+ Historical Change: `account.edi.document` Model Split

In Odoo 18, the EDI state was **moved from fields on `account.move` into a separate `account.edi.document` model**. This change enables:

- **Multiple EDI formats per move**: One invoice can simultaneously have EDI documents for Peppol (via `account_peppol`), Factur-X (`l10n_fr_facturx`), UBL 2.1 (`l10n_ubl`), etc.
- **Cleaner state machine**: Document state is independent of move state
- **Batching per format**: Jobs are grouped by `edi_format_id`, so sending 50 invoices via Peppol batches into fewer API calls than one call per invoice
- **Separation of concerns**: The document model handles only EDI workflow; the format model handles only generation/transmission

### Dual-Mode Processing

| Mode | `_needs_web_services()` | Processing Trigger | Use Case |
|------|------------------------|-------------------|----------|
| **Synchronous** | `False` | Inline during `_post()` | Local PDF/ZIP generation, USB stick export |
| **Asynchronous** | `True` | Cron job `ir_cron_edi_network` | Peppol, government portals, third-party APIs |

The dual-mode design means Odoo does not block the user's request waiting for an external API. Instead, it queues the job and processes it via cron.

### Three-Tier Error Severity

```
info    → Non-blocking. Cron retries. State remains to_send. Document is "done" at this level.
warning → Semi-blocking. State remains to_send. User should investigate but cron keeps retrying.
error   → Fully blocking. Cron skips these documents entirely. Manual retry required.
```

---

## Module Dependency Tree

```
account
  └── account_edi                              # Core EDI framework (this module)
        ├── account_edi_proxy_client           # Base proxy: auth, HTTP client, RSA key management
        │     └── account_peppol               # Peppol format (adds 'peppol' to proxy_type)
        │     └── l10n_my_edi                  # Malaysia MyInvois
        │     └── l10n_dk_nemhandel            # Denmark NemHandel
        └── [concrete format modules inherit account.edi.format]
```

---

## Models

### 1. `account.edi.document`

**File:** `models/account_edi_document.py`
**Description:** The core document model. Represents a single EDI document for a specific `account.move` and `account.edi.format`. One move can have N EDI documents (one per format).

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `move_id` | `Many2one(account.move)` | required | The invoice/journal entry this EDI document is attached to. `ondelete='cascade'`. Indexed for performance. |
| `edi_format_id` | `Many2one(account.edi.format)` | required | The concrete EDI format that generated this document. |
| `attachment_id` | `Many2one(ir.attachment)` | False | The generated EDI file (XML, PDF, ZIP, etc.). `groups='base.group_system'` -- only admins can see the binary content. |
| `state` | `Selection` | -- | Lifecycle state. Values: `'to_send'` (To Send), `'sent'` (Sent), `'to_cancel'` (To Cancel), `'cancelled'` (Cancelled). |
| `error` | `Html` | False | Human-readable HTML error from the last failed operation. Used directly in UI alerts. |
| `blocking_level` | `Selection` | False | Error severity controlling retry behavior. Values: `'info'` (non-blocking info), `'warning'` (may succeed on retry), `'error'` (fully blocks). |

**Non-stored (related/computed) fields:**

| Field | Type | Compute Decorator | Description |
|-------|------|-------------------|-------------|
| `name` | `Char` (related) | -- | Proxy to `attachment_id.name` for display convenience. |
| `edi_format_name` | `Char` (related) | -- | Proxy to `edi_format_id.name`. |
| `edi_content` | `Binary` | `@api.depends('move_id', 'error', 'state')` | Base64-encoded preview of the EDI file. Runs with `compute_sudo=True`. |

#### Constraints

```python
_unique_edi_document_by_move_by_format = models.Constraint(
    'UNIQUE(edi_format_id, move_id)',
    'Only one edi document by move by format',
)
```

Enforced at database level. A move can only have one EDI document per format, preventing duplicate processing.

#### Computed Field Details

**`_compute_edi_content`** (`@api.depends('move_id', 'error', 'state')`, `compute_sudo=True`):

```python
def _compute_edi_content(self):
    for doc in self:
        res = b''
        if doc.state in ('to_send', 'to_cancel'):
            move = doc.move_id
            config_errors = doc.edi_format_id._check_move_configuration(move)
            if config_errors:
                # Show config errors as base64 text instead of file
                res = base64.b64encode('\n'.join(config_errors).encode('UTF-8'))
            else:
                move_applicability = doc.edi_format_id._get_move_applicability(move)
                if move_applicability and move_applicability.get('edi_content'):
                    res = base64.b64encode(move_applicability['edi_content'](move))
        doc.edi_content = res
```

This method serves two purposes:
1. **Preview**: Shows the user what will be sent (or shows configuration errors preventing generation)
2. **Export**: `action_export_xml()` downloads this content directly from `/web/content/account.edi.document/{id}/edi_content`

**L4 - Performance:** This compute is called on every form display. For moves with many EDI formats, the content generation can be expensive (e.g., generating a Peppol XML requires tax computation, partner lookup, UBL transformation). Format modules cache the result or should be mindful of `edi_content` access patterns.

#### Method Signatures

##### `action_export_xml()`
```python
def action_export_xml(self) -> dict:
    # Returns: {'type': 'ir.actions.act_url', 'url': '/web/content/account.edi.document/{id}/edi_content'}
```
Downloads the EDI content as a file. Used when a user clicks "Download" on an error state document to see what was supposed to be sent.

##### `_prepare_jobs() -> list[dict]`
Groups documents into processing jobs. The batching logic is the core orchestration method.

**Algorithm:**
```
For each (state, edi_flow) in [('to_send', 'post'), ('to_cancel', 'cancel')]:
    documents = self.filtered(lambda d: d.state == state and d.blocking_level != 'error')

    for each document:
        move_applicability = edi_format._get_move_applicability(move) or {}

        batching_key = [edi_format, state, move.company_id]

        if move_applicability.get(f'{edi_flow}_batching'):
            batching_key += list(move_applicability[f'{edi_flow}_batching'](move))
        else:
            batching_key.append(move.id)  # No batching, one job per move

        batch = to_process[batching_key]
        batch['documents'] |= document
        batch['method_to_call'] = move_applicability.get(edi_flow)
```

**Return shape:**
```python
[
    {
        'documents': account.edi.document (batched recordset),
        'method_to_call': callable or None  # None = no-op (success for all)
    },
    ...
]
```

**L3 - Batching Edge Case:** If two invoices go to the same partner via Peppol, and the format provides `post_batching=lambda move: (move.partner_id,)`, they are batched into a single job. This allows the Peppol proxy to group them into one API call.

##### `_process_job(job)`
Executes a single job. Internal -- called by `_process_documents_no_web_services()` or `_process_documents_web_services()`.

**Pre-execution checks:**
```python
documents.edi_format_id.ensure_one()       # All docs same format
documents.move_id.company_id.ensure_one()  # All docs same company
len(set(doc.state for doc in documents)) == 1  # All docs same state
```

The `state` assertion is validated explicitly (not just asserted implicitly) because batching could theoretically group mixed-state documents if the batching key collision is wrong. The ValueError is the guard.

**L4 - `with moves._send_only_when_ready()` context manager:**
When processing send (not cancel) jobs, the `_process_job` wraps the format's `post` method call inside a context manager from `account.move`:
- Moves that are not yet `_is_ready_to_be_sent()` are filtered out of the context manager
- After the method call, any moves that have become ready (e.g., stock moves now in done state) trigger `_action_invoice_ready_to_be_sent()` to fire the `invoice_ready_to_be_sent` activity and send emails
- This is critical for moves that depend on other operations (like picking validation) before they can be sent via EDI

**Post-processing for send flow** (`_postprocess_post_edi_results`):
```python
for document in documents:
    move = document.move_id
    move_result = edi_result.get(move, {})

    if move_result.get('attachment'):
        old_attachment = document.sudo().attachment_id
        document.sudo().attachment_id = move_result['attachment']
        # Unlink old attachment if it was a pure system attachment (no res_model/res_id)
        if not old_attachment.res_model or not old_attachment.res_id:
            attachments_to_unlink |= old_attachment

    if move_result.get('success') is True:
        document.write({'state': 'sent', 'error': False, 'blocking_level': False})
    else:
        document.write({
            'error': move_result.get('error', False),
            'blocking_level': move_result.get('blocking_level', DEFAULT_BLOCKING_LEVEL)
                              if 'error' in move_result else False,
        })
```

**Post-processing for cancel flow** (`_postprocess_cancel_edi_results`):
```python
for document in documents:
    move = document.move_id
    move_result = edi_result.get(move, {})

    if move_result.get('success') is True:
        document.write({
            'state': 'cancelled', 'error': False,
            'attachment_id': False, 'blocking_level': False
        })

        # If ALL EDI documents are cancelled (or non-web-service),
        # and the move is still posted: cancel the move itself
        if move.state == 'posted' and all(
            doc.state == 'cancelled' or not doc.edi_format_id._needs_web_services()
            for doc in move.edi_document_ids
        ):
            move_ids_to_cancel.add(move.id)
    else:
        document.write({
            'error': move_result.get('error', False),
            'blocking_level': move_result.get('blocking_level', DEFAULT_BLOCKING_LEVEL)
                              if move_result.get('error') else False,
        })

# After loop:
invoices.button_draft()
invoices.button_cancel()
```

**L4 - Cancel Cascade Logic:** The cancellation of the move itself (`button_draft()` + `button_cancel()`) only fires when ALL EDI documents for that move are either cancelled or are non-web-service formats. This prevents an invoice from being cancelled in Odoo when a Peppol cancellation is still pending but a local PDF export has already completed.

**L3 - Multi-Step Cancellation:** Some government portals require a cancellation request to be approved asynchronously. The cancel flow is split:
1. User clicks "Request EDI Cancellation" -> state becomes `to_cancel`
2. Cron calls `_process_job` -> format sends cancellation to portal
3. On success -> `state='cancelled'`, then `button_draft()` + `button_cancel()` on the move
4. On failure -> error stored, state remains `to_cancel`, cron retries

##### `_process_documents_no_web_services()`
Called **synchronously** during `_post()`. Filters documents where `_needs_web_services() == False` and processes them inline. No locking needed since it runs in the same transaction as the `_post()` call.

##### `_process_documents_web_services(job_count=None, with_commit=True) -> int`
Called by the cron for asynchronous processing.

**Locking strategy:**
```python
documents.lock_for_update()          # Lock edi_document rows
move_to_lock.lock_for_update()       # Lock account_move rows
attachments_potential_unlink.lock_for_update()  # Lock ir_attachment rows

except LockError:
    _logger.debug('Another transaction already locked documents rows. Cannot process documents.')
    if not with_commit:  # Manual trigger from UI
        raise UserError(_('This document is being sent by another process already. ')) from None
    else:  # Cron auto-mode: skip and let next run pick it up
        continue
```

**L4 - Performance:** Row-level locking prevents two cron workers from processing the same document simultaneously. `with_commit=True` (cron mode) commits after each job so partially-processed work is not lost on crash. `with_commit=False` (UI manual trigger) raises an error instead of skipping. The lock targets three separate tables because the job touches all three.

**L4 - Memory consideration:** For very large document batches (thousands of invoices), `all_jobs` is built in memory before slicing. The `job_count` limit prevents memory exhaustion. Each `method_to_call` processes a recordset; keeping recordsets small prevents PostgreSQL memory bloat from large IN clauses.

**Returns:** Number of jobs NOT processed (so the cron knows if it needs to re-trigger).

##### `_cron_process_documents_web_services(job_count=None)`
Cron entry point. Search criteria:
```python
self.search([
    ('state', 'in', ('to_send', 'to_cancel')),
    ('move_id.state', '=', 'posted'),
    ('blocking_level', '!=', 'error'),
])
```

Filters out `error`-level documents because they require manual intervention. Also filters out non-posted moves (draft/cancelled moves are not relevant).

After processing, if jobs remain, triggers itself immediately:
```python
self.env.ref('account_edi.ir_cron_edi_network')._trigger()
```

**L4 - Cron Self-Re-trigger:** This is critical for throughput. With `job_count=20` (default from `data/cron.xml`), if there are 100 jobs, the cron processes 20, commits, and re-triggers itself to run again. This prevents a single cron run from monopolizing database connections while still maintaining resumability.

##### `_filter_edi_attachments_for_mailing()`
Used by the "Send & Print" wizard to attach EDI documents to emails.

| Context | Return |
|---------|--------|
| Single send, attachment is business-linked (`res_model` + `res_id`) | `{'attachment_ids': [attachment_id]}` -- link existing attachment |
| Single send, attachment is system-only | `{'attachments': [(name, datas)]}` -- copy attachment content |
| Mass mail mode | `{}` -- exclude attachments from mass renders (they should not be in the template body) |

**L4 - Email Attachment Design:** The method distinguishes between two attachment modes:
- `attachment_ids` mode: The existing attachment (linked to move) is attached directly to the email. This is more efficient (no duplicate storage).
- `attachments` mode: A copy of the attachment content is packaged as a new inline attachment. Used when the system attachment has no `res_model/res_id` (typically generated but not yet linked).

**L4 - Mass Mail Protection:** In mass mail mode, EDI attachments are intentionally excluded from the email. This is because EDI documents are invoice-specific (one file per invoice) and embedding them in a mass-rendered template body would be incorrect. The attachments would also significantly increase email size for bulk sends.

---

### 2. `account.edi.format`

**File:** `models/account_edi_format.py`
**Description:** Abstract base model defining the EDI format interface. All country-specific and protocol-specific EDI modules (Peppol, Factur-X, UBL, etc.) inherit from this and implement its methods. The model is abstract (no table created directly) but serves as the parent for concrete format records.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Human-readable display name (e.g., "Peppol BIS Billing 3.0", "Factur-X 1.0") |
| `code` | `Char` (required, unique) | Machine-readable identifier (e.g., `'peppol'`, `'facturx'`, `'ubl_2_1'`). Enforced unique at DB level. |

#### Constraints

```python
_unique_code = models.Constraint(
    'unique (code)',
    'This code already exists',
)
```

#### `create()` Hook
When a format record is created:
1. If the ORM registry is not fully loaded (during module install), sets `pool._delay_compute_edi_format_ids = True` to defer journal recalculation (formats from other modules being installed may not yet be registered).
2. Otherwise, recomputes `edi_format_ids` on all journals immediately.
3. If the format's `_needs_web_services()` returns `True`, activates the cron:
   ```python
   self.env.ref('account_edi.ir_cron_edi_network').active = True
   ```

**L4 - Cron Auto-Activation:** The cron is activated lazily -- only when the first web-service format is installed. Before that point, the cron record exists but is inactive (`active=False`). This avoids unnecessary cron invocations on databases without EDI.

#### `_register_hook()` Hook
Executed after the full module registry is loaded. Recomputes journal `edi_format_ids` if the computation was delayed during `create()`.

**L4 - Registry Loading Order:** During module install, the ORM registry is built incrementally. The `_register_hook` fires after all modules in the dependency chain have been loaded. Setting `pool._delay_compute_edi_format_ids = True` during `create()` defers the journal recomputation to this hook, ensuring all format modules have registered their `account.edi.format` records before the journal's `edi_format_ids` is computed.

#### Core Methods (Override Points)

##### `_get_move_applicability(move) -> dict | None`

**The central method of the entire EDI system.** Called once per format per move.

```python
def _get_move_applicability(self, move):
    """Returns:
      None             -> format does not apply to this move
      dict with keys:  -> format applies, dict contains callables
        'post':             callable(moves)   -> send flow
        'cancel':           callable(moves)   -> cancel flow
        'post_batching':    callable(move)    -> extra batching key for send
        'cancel_batching':  callable(move)    -> extra batching key for cancel
        'edi_content':      callable(move)    -> returns raw bytes for preview
    """
    self.ensure_one()
    # Override in concrete format modules
```

**Example (Peppol):**
```python
def _get_move_applicability(self, move):
    if move.move_type not in ('out_invoice', 'out_refund'):
        return None
    if not move.company_id.peppol_eas or not move.company_id.peppol_endpoint:
        return None
    return {
        'post': self._peppol_post_invoice_edi,
        'cancel': self._peppol_cancel_invoice_edi,
        'edi_content': self._peppol_get_edi_content,
        'post_batching': lambda move: (move.partner_id,),
    }
```

**L4 - Performance Implication:** This method is called multiple times per move per format: once during `_post()` (for applicability check), once during `_prepare_jobs()` (for batching key), and once in `_compute_edi_content()` (for preview). Format implementations should keep this method fast (pure read-only checks, no I/O or network calls).

**L3 - Return Value Semantics:** Returning `None` means the format silently skips this move. Returning a dict with only `'cancel'` (no `'post'`) is valid -- supports formats that cannot send but can cancel. This supports partial applicability scenarios like B2C invoices via Peppol (no Peppol reception endpoint available).

##### `_needs_web_services() -> bool`

Returns `False` by default (formats that only generate local files). Override to `True` for formats requiring HTTP communication.

**L4 - Called on class, not instance:** `_needs_web_services()` is a method on the format record. When called from `_process_documents_no_web_services()`, it is called on each format's recordset as a filter. When called from `_cron_process_documents_web_services()`, it is called on all formats in `self.search([])`. Format instances that return `False` are excluded from async processing.

##### `_is_compatible_with_journal(journal) -> bool`

Controls which journals show this format in their settings. Default: `journal.type == 'sale'`. Country modules override for purchase/sale journals as needed.

**L4 - Journal Compatibility Caching:** `_compute_compatible_edi_ids` calls `_is_compatible_with_journal()` for every format/journal combination. Since formats are relatively static, this could be optimized with a cache, but at Odoo 19's scale (tens of formats, hundreds of journals) the computation is negligible.

##### `_is_enabled_by_default_on_journal(journal) -> bool`

Controls pre-selection of the format on new journals. Default: `True`.

##### `_check_move_configuration(move) -> list[str]`

Validates that the move has everything required for EDI generation. Returns a list of error strings. If non-empty:
- `_compute_edi_content` returns these errors as base64 text instead of the file
- `_post()` raises `UserError` immediately, blocking the post

Common validation checks:
- Company has a VAT number
- Company has a country set (for jurisdiction-specific EDI)
- Partner has a VAT number (for B2B EDI)
- Partner has an email address (for Peppol routing)
- Move has at least one line with a tax

**L4 - Fail-Fast Design:** This check is called synchronously during `_post()`. If it returns errors, the move is NOT posted. This is intentional -- the invoice should not be posted if it cannot be sent via EDI. However, this means a configuration error on a single line can block ALL EDI formats for that move.

##### `_prepare_invoice_report(pdf_writer, edi_document)`

Override to add EDI attachment into the printed PDF. Called by `ir.actions.report._render_qweb_pdf_prepare_streams()`.

##### `_format_error_message(error_title, errors) -> str`

Utility that builds an HTML error message with a bullet list:
```python
bullet_list_msg = ''.join('<li>%s</li>' % html_escape(msg) for msg in errors)
return '%s<ul>%s</ul>' % (error_title, bullet_list_msg)
```

---

### 3. `account.move` (Extension)

**File:** `models/account_move.py`

Extends `account.move` with EDI state tracking, workflow methods, and UI control fields.

#### Added Fields

| Field | Type | Store | Compute Decorator | Description |
|-------|------|-------|-------------------|-------------|
| `edi_document_ids` | `One2many` | stored | -- | Inverse of `account.edi.document.move_id`. All EDI documents for this move. |
| `edi_state` | `Selection` | stored | `@api.depends('edi_document_ids.state')` | Aggregated state across all web-service documents. `False` if no EDI. |
| `edi_error_count` | `Integer` | computed | `@api.depends('edi_document_ids.state')` | Count of documents with errors. |
| `edi_blocking_level` | `Selection` | computed | `@api.depends('edi_error_count', 'edi_document_ids.error', 'edi_document_ids.blocking_level')` | Worst error severity among all documents. |
| `edi_error_message` | `Html` | computed | same as above | Full error HTML (single error) or count message (multiple errors). |
| `edi_web_services_to_process` | `Text` | computed | `@api.depends('edi_document_ids', 'edi_document_ids.state', 'edi_document_ids.blocking_level', 'edi_document_ids.edi_format_id', 'edi_document_ids.edi_format_id.name')` | Comma-separated format names pending processing. |
| `edi_show_cancel_button` | `Boolean` | computed | `@api.depends('edi_document_ids.state')` | Show "Request EDI Cancellation". |
| `edi_show_abandon_cancel_button` | `Boolean` | computed | `@api.depends('edi_document_ids.state')` | Show "Call off EDI Cancellation". |
| `edi_show_force_cancel_button` | `Boolean` | computed | `@api.depends('edi_document_ids.state')` | Show "Force Cancel". |

**L4 - Why `edi_state` is stored (stored computed):** In Odoo 18, `edi_state` was a computed-only field. In Odoo 19, it was changed to `store=True, compute='_compute_edi_state'`. This change was made for performance -- the EDI state must be visible on the invoice list view without triggering a compute on every record. The compute fires on `edi_document_ids.state` changes (document creation, state transitions).

#### Computed Field Logic

**`_compute_edi_state`** (`@api.depends('edi_document_ids.state')`):
Only considers documents whose format returns `True` from `_needs_web_services()`.

```
all_states = set(web_service_docs.mapped('state'))

if all_states == {'sent'}           -> 'sent'
elif all_states == {'cancelled'}    -> 'cancelled'
elif 'to_send' in all_states        -> 'to_send'
elif 'to_cancel' in all_states     -> 'to_cancel'
else                                -> False
```

If a move has only non-web-service EDI documents (e.g., local PDF generation), `edi_state` remains `False`.

**`_compute_edi_error_message`**:
```
0 errors  -> message=None, blocking_level=None
1 error   -> copies error.HTML directly, blocking_level=doc.blocking_level
N errors  -> "N Electronic invoicing error(s)"
            worst blocking level: error > warning > info
```

**`_compute_edi_show_cancel_button`**:
```
True if:
  move.state == 'posted' AND
  any doc where:
    doc.edi_format_id._needs_web_services() == True AND
    doc.state == 'sent' AND
    move_applicability.get('cancel') is truthy
```

**`_compute_edi_show_abandon_cancel_button`**:
Same pattern but checks `doc.state == 'to_cancel'`.

**`_compute_edi_show_force_cancel_button`**:
Delegates to `move._can_force_cancel()` (from `account` base model). The base implementation checks that the move is in a cancellable state and has no payments that would complicate the cancellation.

#### Method Overrides

##### `_edi_allow_button_draft() -> bool`
```python
def _edi_allow_button_draft(self):
    self.ensure_one()
    return not self.edi_show_cancel_button
```
Returns `True` (allowing draft reset) only if the "Request EDI Cancellation" button is NOT shown. This is the single condition that gates `button_draft()`.

##### `_check_edi_documents_for_reset_to_draft() -> bool`
```python
def _check_edi_documents_for_reset_to_draft(self):
    self.ensure_one()
    for doc in self.edi_document_ids:
        move_applicability = doc.edi_format_id._get_move_applicability(self)
        if doc.edi_format_id._needs_web_services() \
            and doc.state in ('sent', 'to_cancel') \
            and move_applicability \
            and move_applicability.get('cancel'):
            return False
    return True
```
Iterates all EDI documents on the move. Returns `False` if any document is web-service, in `sent` or `to_cancel` state, and has a cancel method. This is a more granular check than `_edi_allow_button_draft()` (which only checks the button display flag).

**L4 - Two-Gate Design:** `_edi_allow_button_draft()` and `_check_edi_documents_for_reset_to_draft()` are both called. `_edi_allow_button_draft()` is a fast path using the pre-computed button flag. `_check_edi_documents_for_reset_to_draft()` is the authoritative check called from `_compute_show_reset_to_draft_button()`.

##### `_post(soft=True)` (Override)
Called when posting an invoice. EDI handling:

```python
for move in posted:
    for edi_format in move.journal_id.edi_format_ids:
        move_applicability = edi_format._get_move_applicability(move)

        if move_applicability:
            errors = edi_format._check_move_configuration(move)
            if errors:
                raise UserError(_("Invalid invoice configuration:\n\n%s", '\n'.join(errors)))

            existing_doc = move.edi_document_ids.filtered(lambda x: x.edi_format_id == edi_format)
            if existing_doc:
                existing_doc.sudo().write({'state': 'to_send', 'attachment_id': False})
            else:
                edi_document_vals_list.append({
                    'edi_format_id': edi_format.id,
                    'move_id': move.id,
                    'state': 'to_send',
                })

self.env['account.edi.document'].create(edi_document_vals_list)
posted.edi_document_ids._process_documents_no_web_services()

if not self.env.context.get('skip_account_edi_cron_trigger'):
    self.env.ref('account_edi.ir_cron_edi_network')._trigger()
```

**L4 - Re-posting behavior:** If a move is re-posted (posted again after being reset to draft), the existing EDI documents are NOT deleted. Instead, their state is reset to `to_send` and attachment cleared. This allows re-generation of EDI files with updated data. The document record itself persists (preserving history/audit trail).

**L4 - Performance Note:** The context key `skip_account_edi_cron_trigger` can be used in tests or batch operations to suppress the immediate cron trigger. The cron will still process the documents on its next scheduled run. In high-volume batch posting scenarios, triggering the cron for each of 1000 invoices could create 1000 pending cron events; suppressing the trigger defers to the next scheduled run.

##### `_is_ready_to_be_sent()` (Override)
Extends parent method. Returns `False` if any `edi_document_ids` have `state == 'to_send'`. This prevents the Send & Print wizard from sending the email until EDI documents are processed.

**L3 - Edge Case:** If a move has only non-web-service documents, `_is_ready_to_be_sent()` behavior depends on whether those documents have already been processed synchronously during `_post()`. If they were processed successfully, `state` becomes `sent` and this check passes. If they failed, `state` is `to_send` and the check blocks email sending.

##### `button_cancel()` (Override)
```
1. Non-sent docs (to_send): state -> 'cancelled', error cleared
2. Sent docs: state -> 'to_cancel', error cleared
3. Process synchronous cancellations inline
4. Trigger cron for async cancellations
```

##### `button_draft()` (Override)
Blocks draft reset if EDI was sent:
```python
if not move._edi_allow_button_draft():
    raise UserError(_(
        "You can't edit the following journal entry %s because an electronic document "
        "has already been sent. Please use the 'Request EDI Cancellation' button instead.",
        move.display_name))
```
Also clears error fields and unlinks `to_send` documents (since the move is going back to draft, those EDI documents are invalidated).

**L4 - Document Unlink on Draft:** Documents in `to_send` state are explicitly unlinked on `button_draft()`. This is because:
- These documents have never been successfully sent
- The invoice is being reset to draft for editing
- The old EDI documents are no longer relevant and should be replaced with fresh ones on re-post

However, `sent` and `to_cancel` documents are NOT unlinked -- they represent actual transmissions that happened or are pending.

##### `button_cancel_posted_moves()`
Used by the "Request EDI Cancellation" button. Iterates over sent documents with `cancel` applicability and marks them `to_cancel`. Also posts a chatter message on the move.

##### `button_abandon_cancel_posted_posted_moves()`
Reverts `to_cancel` back to `sent`. Used by "Call off EDI Cancellation" button. Posts a chatter message.

##### `button_force_cancel()`
Forces cancellation without waiting for EDI success. Posts a chatter warning listing the formats with pending cancellations, then calls the standard `button_cancel()`.

##### `_get_edi_document(edi_format) -> recordset`
Helper: returns `self.edi_document_ids.filtered(lambda d: d.edi_format_id == edi_format)`. Convenience wrapper used by format modules and UI code.

##### `_get_edi_attachment(edi_format) -> recordset`
Helper: returns `self._get_edi_document(edi_format).sudo().attachment_id`. Shorthand for retrieving the EDI file. Runs with sudo because the attachment has `groups='base.group_system'`.

##### `_message_set_main_attachment_id()` (Override)
Ensures the main attachment is not the EDI XML if there are other attachments. The `filter_xml=True` flag causes the method to skip EDI XML files when choosing the main attachment for the invoice form's chatter display.

##### `button_process_edi_web_services()`
UI button trigger (one invoice at a time). Calls `self.action_process_edi_web_services(with_commit=False)`. Raises `UserError` if the document is being processed by another process.

##### `action_process_edi_web_services(with_commit=True)`
Manual retry from UI. Calls `_process_documents_web_services(with_commit=with_commit)`. `with_commit=False` for UI (raises on conflict); `with_commit=True` for cron.

##### `_retry_edi_documents_error()`
Clears all errors and blocking levels on the move's EDI documents:
```python
self.edi_document_ids.write({'error': False, 'blocking_level': False})
```

##### `action_retry_edi_documents_error()`
Combines `_retry_edi_documents_error()` + `action_process_edi_web_services()`. This is the "Retry" button handler in the invoice form alert banner.

##### `_process_attachments_for_template_post(mail_template)` (Override)
Extends the email template attachment processing. For each move with EDI documents, calls `_filter_edi_attachments_for_mailing()` on each document and merges results into the template's attachment list.

#### Tax Computation Helper

##### `_prepare_edi_tax_details(filter_to_apply=None, filter_invl_to_apply=None, grouping_key_generator=None) -> dict`
Delegates to `_prepare_invoice_aggregated_taxes()` (the same underlying method used for standard invoice tax reports). This is a thin wrapper that EDI format modules call to get tax breakdowns in a standardized structure.

Return structure:
```python
{
    'base_amount': float,          # Total base in company currency
    'tax_amount': float,           # Total tax in company currency
    'base_amount_currency': float, # Total base in foreign currency
    'tax_amount_currency': float,  # Total tax in foreign currency
    'tax_details': {              # Grouped by grouping_key_generator
        grouping_key: {
            'base_amount': float,
            'tax_amount': float,
            'group_tax_details': [list of tax values]
        }
    },
    'tax_details_per_record': {   # Grouped by invoice line
        line_id: {
            'tax_details': {...}
        }
    }
}
```

**L4 - Shared with Reports:** `_prepare_invoice_aggregated_taxes()` is also used by the invoice report engine. This means EDI tax computation and human-readable invoice tax tables share the same underlying data structure, ensuring consistency.

---

### 4. `account.journal` (Extension)

**File:** `models/account_journal.py`

#### Added Fields

| Field | Type | Store | Description |
|-------|------|-------|-------------|
| `edi_format_ids` | `Many2many(account.edi.format)` | stored | Active formats on this journal. Compute + readonly=False allows user edits. |
| `compatible_edi_ids` | `Many2many(account.edi.format)` | computed | All formats compatible with this journal type. Used as domain. |

#### `_compute_compatible_edi_ids`

Filters all registered formats via `_is_compatible_with_journal(journal)`. Result is used as the domain for `edi_format_ids`.

#### `_compute_edi_format_ids`

Determines which formats are auto-selected and which are protected:

```python
for journal in self:
    enabled = formats.filtered(lambda e:
        e._is_compatible_with_journal(journal) and
        (e._is_enabled_by_default_on_journal(journal) or e in journal.edi_format_ids)
    )

    # Protect formats with in-flight documents
    protected = journal.edi_format_ids.filtered(
        lambda e: e.id in protected_edi_format_ids.get(journal.id, set())
    )

    journal.edi_format_ids = enabled | protected
```

The protection SQL query:
```sql
SELECT move.journal_id, ARRAY_AGG(doc.edi_format_id)
FROM account_edi_document doc
JOIN account_move move ON move.id = doc.move_id
WHERE doc.state IN ('to_cancel', 'to_send')
AND move.journal_id IN %s
GROUP BY move.journal_id
```

**L3 - Protection Logic:** If a journal has a format enabled AND there are pending documents for that format, the format cannot be unchecked. This prevents accidentally disabling Peppol while 50 invoices are queued for sending.

**L4 - SQL Efficiency:** The protected formats query is a raw SQL query executed once per batch of journals. For databases with millions of invoices, this query can be slow. An index on `account_edi_document(move_id, state)` is important for this query's performance.

#### `write()` Override
Validates that formats being removed have no pending documents. Formats without web services can have their documents safely deleted; formats with web services raise `UserError`.

**L4 - Partial Document Cleanup:** When removing a format that has pending documents without web services, those documents are unlinked (not just deactivated). This keeps `account.edi.document` clean and prevents zombie records.

---

### 5. `account.move.send` (Extension)

**File:** `models/account_move_send.py`

Extends the Send & Print wizard to include EDI attachments.

##### `_get_mail_attachment_from_doc(doc)`
Returns the document's attachment (via sudo) if it has `res_model` and `res_id`. Returns empty recordset otherwise.

##### `_get_invoice_extra_attachments(move)` (Override)
Extends the parent method. Iterates over `move.edi_document_ids` and appends each EDI attachment to the result, enabling email delivery of EDI files alongside the PDF.

---

### 6. `ir.actions.report` (Extension)

**File:** `models/ir_actions_report.py`

##### `_render_qweb_pdf_prepare_streams()` (Override)

Embeds EDI attachments into the printed invoice PDF:

```python
if self._is_invoice_report(report_ref) and invoice.is_sale_document() and invoice.state != 'draft':
    to_embed = invoice.edi_document_ids
    for edi_document in to_embed:
        edi_document.edi_format_id._prepare_invoice_report(writer, edi_document)
```

**Conditions:**
- Only runs for single-invoice PDF renders (`len(res_ids) == 1`)
- Only for sale documents that are posted (not draft)
- Only if there are EDI documents to embed

**L3 - PDF Embedding Pattern:** The format's `_prepare_invoice_report` uses the `OdooPdfFileWriter` to merge the EDI file (typically XML) into the PDF as an embedded file/attachment. This allows the printed PDF to contain the machine-readable EDI as a file annotation, satisfying legal requirements in some jurisdictions.

**L4 - Performance (PDF Merge):** PDF merging is I/O intensive. The stream is read into memory, parsed with `OdooPdfFileReader`, cloned into `OdooPdfFileWriter`, and serialized back. For bulk PDF generation (e.g., batch printing 100 invoices), this overhead accumulates. The single-invoice check (`len(res_ids) == 1`) ensures bulk printing skips EDI embedding for efficiency, which is generally acceptable since bulk print is for internal use.

---

### 7. `ir.attachment` (Extension)

**File:** `models/ir_attachment.py`

##### `_unlink_except_government_document()` (`@api.ondelete(at_uninstall=False)`)

Prevents deletion of EDI attachments that have been sent to government portals:

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_government_document(self):
    linked_edi_documents = self.env['account.edi.document'].sudo().search([
        ('attachment_id', 'in', self.ids)
    ])
    linked_edi_formats_ws = linked_edi_documents.edi_format_id.filtered(
        lambda edi_format: edi_format._needs_web_services()
    )
    if linked_edi_formats_ws:
        raise UserError(_("You can't unlink an attachment being an EDI document sent to the government."))
```

**L3 - On Unlink Protection:** The `at_uninstall=False` parameter means this check is **not** bypassed during module uninstall, protecting data integrity even when removing `account_edi`. Regular (non-EDI) attachments linked to `account.edi.document` records can still be deleted if their format doesn't need web services.

**L4 - Search Scope:** The search uses `('attachment_id', 'in', self.ids)` which is an `IN` query. If many attachments are being deleted simultaneously (e.g., during module uninstall or a large cleanup), this could be slow. The sudo access is necessary because `account.edi.document` ACLs may restrict access.

---

### 8. `account_edi_proxy_client.user` (Base Proxy User Model)

**File:** `account_edi_proxy_client/models/account_edi_proxy_user.py`
**Module:** `account_edi_proxy_client` (separate addon, sibling to `account_edi`)

The base proxy model for EDI formats requiring secure HTTP communication through Odoo's IAP proxy infrastructure. Extended by `account_peppol`, `l10n_my_edi`, `l10n_dk_nemhandel`, etc.

#### Design Rationale

EDI formats like Peppol require:
1. **Mutual TLS / certificate authentication** with the access point
2. **Message encryption** (documents are encrypted with the receiver's public key)
3. **Identification** via structured IDs (EAS + Endpoint for Peppol)
4. **Proxy routing** (Odoo's IAP proxy handles network complexity)

The `account_edi_proxy_client.user` model encapsulates all of this. The Odoo proxy server acts as a relay:
- Sender -> Odoo Proxy -> Receiver
- Receiver -> Odoo Proxy -> Sender

This avoids each Odoo instance needing a direct internet connection and custom TLS configuration.

#### Fields

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `active` | `Boolean` | -- | Soft-delete flag. Archived users are inactive. |
| `id_client` | `Char` | -- | UUID assigned by the proxy server at registration. Used in all API calls. |
| `company_id` | `Many2one(res.company)` | -- | Company this proxy user belongs to. |
| `edi_identification` | `Char` | -- | Format-specific ID (e.g., `0208:12345678` for Peppol with EAS=0208). Typically the VAT number. |
| `private_key_id` | `Many2one(certificate.key)` | -- | RSA private key for decrypting received documents. Public key was sent to proxy during registration. |
| `refresh_token` | `Char` | `base.group_system` | HMAC secret for authenticating API requests. Admin-only visibility. |
| `is_token_out_of_sync` | `Boolean` | -- | Flagged when the token was superseded by another database (e.g., after restore from backup). |
| `token_sync_version` | `Integer` | -- | Counter incremented each time the token is re-synced. Used to detect desync. |
| `proxy_type` | `Selection` | -- | Type of proxy service. Base model has **no values** -- child modules add their own (e.g., `('peppol', 'PEPPOL')`). |
| `edi_mode` | `Selection` | -- | Operating mode: `'prod'` (production), `'test'` (test infrastructure), `'demo'` (simulated responses). |

#### Constraints

```python
_unique_id_client = models.Constraint(
    'unique(id_client)',
    "This id_client is already used on another user."
)
_unique_active_company_proxy = models.UniqueIndex(
    '(company_id, proxy_type, edi_mode) WHERE (active IS TRUE)',
    "This company has an active user already created for this EDI type"
)
```

The unique index ensures a company cannot have multiple active proxy users of the same type and mode (e.g., two active Peppol users in production).

#### Registration Flow

##### `_register_proxy_user(company, proxy_type, edi_mode) -> self`

1. Generate RSA key pair: `company_id._generate_rsa_private_key(name=f"{proxy_type}_{edi_mode}_{company.id}.key")`
2. Get `edi_identification` from `_get_proxy_identification(company, proxy_type)`
3. Call proxy server: `POST /iap/account_edi/2/create_user` with `dbuuid`, `company_id`, `edi_identification`, `public_key`, `proxy_type`
4. Server returns `{'id_client': '...', 'refresh_token': '...'}`
5. Create local record with the private key (stored locally) and refresh token (stored locally)

#### Authentication: `OdooEdiProxyAuth`

**File:** `account_edi_proxy_client/models/account_edi_proxy_auth.py`

A `requests.auth.AuthBase` subclass. Signs every outgoing request with:

| Header | Value |
|--------|-------|
| `odoo-edi-client-id` | `id_client` |
| `odoo-edi-timestamp` | Unix timestamp |
| `odoo-edi-signature` | HMAC-SHA256(refresh_token, message) **OR** RSA signature(private_key, message) |
| `odoo-edi-signature-type` | `'hmac'` or `'asymmetric'` |

Message format: `timestamp|path|id_client|query_params_sorted|body_sorted`

**L4 - Security:** HMAC tokens expire after 24 hours to limit damage from token theft. The asymmetric (RSA) signature is used only for the token resync flow, which happens when a database is duplicated without neutralization.

#### Key Methods

##### `_make_request(url, params, auth_type='hmac') -> dict`

Makes an authenticated JSON-RPC 2.0 request to the proxy:

```python
def _make_request(self, url, params=None, *, auth_type='hmac'):
    payload = {
        'jsonrpc': '2.0', 'method': 'call',
        'params': params or {}, 'id': uuid.uuid4().hex,
    }

    if self.edi_mode == 'demo':
        raise AccountEdiProxyError("block_demo_mode", "Can't access the proxy in demo mode")

    res = requests.post(
        url, json=payload, timeout=DEFAULT_TIMEOUT,
        headers={'content-type': 'application/json'},
        auth=OdooEdiProxyAuth(user=self, auth_type=auth_type)
    )
    res.raise_for_status()
    response = res.json()

    proxy_error = response['result'].pop('proxy_error', False)
    if proxy_error:
        if proxy_error['code'] == 'refresh_token_expired':
            self._renew_token()
            self.env.cr.commit()
            return self._make_request(url, params, auth_type='hmac')
        if proxy_error['code'] == 'no_such_user':
            self.sudo().active = False
        if proxy_error['code'] == 'invalid_signature':
            raise AccountEdiProxyError(...)
        raise AccountEdiProxyError(proxy_error['code'], proxy_error['message'])

    return response['result']
```

**Error handling:**
- `refresh_token_expired`: Auto-renew and retry once
- `no_such_user`: Soft-delete the local proxy user record
- `invalid_signature`: Indicates database duplication (see token out-of-sync below)

**L4 - Request Timeout:** `DEFAULT_TIMEOUT` (likely 30 seconds) applies to all proxy requests. For batch operations (sending many invoices in one API call), the timeout may need to be larger. Format modules that implement batch sending should be aware of this constraint.

##### `_renew_token()`

```python
def _renew_token(self):
    self.lock_for_update()
    response = self._make_request(self._get_server_url() + '/iap/account_edi/1/renew_token')
    self.sudo().refresh_token = response['refresh_token']
```

Called when a `refresh_token_expired` error is received. Acquires a row lock to prevent race conditions between cron workers.

##### `_decrypt_data(data, symmetric_key) -> bytes`

Decryption flow for received documents:
1. Proxy sends: `{document: base64(fernet_encrypted(content)), enc_key: base64(rsa_encrypted(fernet_key))}`
2. RSA-decrypt the symmetric key with local private key
3. Fernet-decrypt the content with the symmetric key
4. Return raw document bytes

#### Token Out-of-Sync (Database Duplication) Handling

When a database is restored from backup or copied without neutralization:
1. The proxy server has one `refresh_token` but two databases are using it
2. Requests from both databases create race conditions
3. The server detects this via signature mismatches

**Detection:** `_needs_web_services()` format calls raise `AccountEdiProxyError` with `invalid_signature` code.

**Resolution:**
- `_mark_connection_out_of_sync()`: Sets `is_token_out_of_sync=True`, clears `refresh_token`
- `_peppol_out_of_sync_reconnect_this_database()`: Uses RSA signature (not HMAC) to re-authenticate and get a new token
- `_peppol_out_of_sync_disconnect_this_database()`: If the connection was superseded (another database won), archives the user and resets company configuration

---

### 9. Peppol-specific Proxy User (`account_peppol`)

**File:** `account_peppol/models/account_edi_proxy_user.py`
**Model:** `Account_Edi_Proxy_ClientUser` (extends `account_edi_proxy_client.user`)

Adds Peppol-specific business logic. See [Modules/account_peppol](odoo-17/Modules/account_peppol.md) for full documentation.

Key additions:
- `proxy_type` extended with `('peppol', 'PEPPOL')`
- CRON jobs: `_cron_peppol_get_new_documents`, `_cron_peppol_get_message_status`, `_cron_peppol_get_participant_status`, `_cron_peppol_webhook_keepalive`
- Business methods: `_peppol_import_invoice`, `_peppol_get_new_documents`, `_peppol_get_message_status`, `_peppol_deregister_participant`

---

### 10. `account.resequence.wizard` (Extension)

**File:** `wizard/account_resequence.py`

Prevents invoice number resequencing when EDI has been sent:

```python
def _frozen_edi_documents(self):
    return self.move_ids.edi_document_ids.filtered(
        lambda d: d.edi_format_id._needs_web_services() and d.state == "sent"
    )

def resequence(self):
    edi_sent_moves = self._frozen_edi_documents()
    if edi_sent_moves:
        raise UserError(_("The following documents have already been sent and cannot be resequenced: %s")
            % ", ".join(set(edi_sent_moves.move_id.mapped('name'))))
    return super().resequence()
```

**L3 - Scope:** Only `sent` documents block resequencing. `to_cancel` documents do not block (cancellation is pending, not yet confirmed). Non-web-service documents do not block (they are local only).

---

## Cron Jobs

| Cron | Model | Code | Interval | Active Default | Purpose |
|------|-------|------|----------|----------------|---------|
| `ir_cron_edi_network` | `account.edi.document` | `_cron_process_documents_web_services(job_count=20)` | Daily | **No** (activated on first WS format create) | Processes all pending async EDI documents |

The cron processes up to **20 jobs** per invocation. If more jobs remain, it re-triggers itself immediately via `_trigger()`. This design:
- Prevents a single cron run from holding database connections for too long
- Allows incremental progress on large EDI queues
- Provides natural resumability on server restart

**L4 - Cron Data File (`data/cron.xml`):** The cron is defined with `noupdate="1"`, meaning it is created on first install and preserved across upgrades. The `active=False` default ensures the cron does not run until a web-service format is installed.

---

## Views

### `account_edi_document_views.xml`
Defines a list view for `account.edi.document` with color coding:
- `decoration-info="blocking_level == 'info'"` -- blue for info-level
- `decoration-warning="blocking_level == 'warning'"` -- yellow for warning
- `decoration-danger="blocking_level == 'error'"` -- red for error

### `account_move_views.xml`
Extends the invoice form and list views:

**Form view additions:**
- "Request EDI Cancellation" button (after `button_cancel`)
- "Call off EDI Cancellation" button
- Alert banners (info/warning/danger) for EDI status between header and notebook
- "Process now" button in the "will soon be sent" banner
- "Force Cancel" button in the error alert
- "Retry" button in the error alert
- EDI status field (after `journal_div`)
- EDI Documents notebook page (hidden when no EDI documents, restricted to technical users)

**List view additions (sale invoices, sale refunds, purchase refunds, bills):**
- `edi_state` column (optional, hidden by default)
- `edi_blocking_level` column (optional, hidden)
- `edi_error_message` column (optional, hidden)
- Color coding matching blocking level

**Search view additions:**
- Group by `edi_state` filter
- `edi_to_process` filter: `domain="[('edi_state', 'in', ['to_send', 'to_cancel'])]"`

**L4 - Access Control on View:** The EDI Documents page is restricted to `base.group_no_one` (the technical features group, typically only administrators). Regular accounting users see the alerts and state columns but not the raw EDI document list.

### `account_journal_views.xml`
Adds `edi_format_ids` checkbox widget to the journal form, inside a group with `name='group_edi_config'` that is hidden when `compatible_edi_ids` is empty.

---

## Security Model

### Access Control (CSV)

| ID | Model | Group | R | W | C | D |
|----|-------|-------|---|---|---|---|
| `access_account_edi_format_readonly` | `model_account_edi_format` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_account_edi_format_group_invoice` | `model_account_edi_format` | `account.group_account_invoice` | 1 | 1 | 1 | 1 |
| `access_account_edi_document_readonly` | `model_account_edi.document` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_account_edi_document_group_invoice` | `model_account_edi.document` | `account.group_account_invoice` | 1 | 1 | 1 | 1 |

**Key points:**
- Regular users can **read** EDI state (via `edi_state`, `edi_error_count`, `edi_error_message` on `account.move`)
- Only `account.group_account_invoice` users can **create/write/delete** EDI documents
- The `attachment_id` binary content is `groups='base.group_system'` -- only admin can see the raw file
- The `refresh_token` on proxy users is `groups='base.group_system'` -- only admin can see the API secret

### Attachment Protection
Government-archived EDI attachments cannot be deleted even by administrators (via the ORM). This is enforced at the `ondelete` level via `_unlink_except_government_document`.

---

## Workflow Diagrams

### Send Flow

```
User clicks "Post"
      │
      ▼
account.move._post()
      │
      ├─ For each edi_format in journal.edi_format_ids:
      │    ├─ _get_move_applicability(move) -> dict?
      │    ├─ _check_move_configuration(move) -> errors[]?
      │    │    └─ If errors: raise UserError (BLOCKED)
      │    └─ Create account.edi.document (state='to_send')
      │
      ├─ _process_documents_no_web_services()
      │    └─ For each doc where _needs_web_services()==False:
      │         └─ _process_job() -> generate file inline -> state='sent'
      │
      └─ ir_cron_edi_network._trigger()
           │
           ▼
      Cron fires
           │
           ▼
      _cron_process_documents_web_services()
           │
           ├─ _prepare_jobs() -> batch by format/company/state
           │
           └─ For each job:
                ├─ lock_for_update() on doc + move + attachment
                ├─ _process_job()
                │    └─ with moves._send_only_when_ready():
                │         Format's 'post' callable generates + sends
                └─ _postprocess_post_edi_results()
                     ├─ success -> state='sent', attachment linked
                     ├─ warning/info -> state='to_send', error stored, retry
                     └─ error -> state='to_send', blocking_level='error', SKIPPED
```

### Cancel Flow

```
User clicks "Request EDI Cancellation"
      │
      ▼
button_cancel_posted_moves()
      │
      ├─ edi_document_ids.filtered(state=='sent').write(state='to_cancel')
      │
      ├─ _process_documents_no_web_services()
      │    └─ For synchronous formats: cancel inline
      │
      └─ ir_cron_edi_network._trigger()
           │
           ▼
      Cron fires
           │
           ▼
      _process_job() for cancel flow
           │
           ├─ Format's 'cancel' callable sends cancellation to portal
           └─ _postprocess_cancel_edi_results()
                ├─ success=True:
                │    ├─ state='cancelled', attachment_id=False
                │    └─ If all docs cancelled + move is posted:
                │         button_draft() -> button_cancel() on move
                └─ success=False:
                     state='to_cancel', error stored, retry
```

---

## Extension Pattern: Adding a New EDI Format

```python
# In your_module/models/my_format.py
from odoo import models

class MyFormatEdi(models.Model):
    _inherit = 'account.edi.format'

    code = 'my_format'
    name = 'My Custom EDI Format'

    # === Journal Compatibility ===

    def _is_compatible_with_journal(self, journal):
        # Show this format on sale and some purchase journals
        return journal.type in ('sale', 'purchase')

    # === Applicability ===

    def _get_move_applicability(self, move):
        if move.move_type not in ('out_invoice', 'out_refund'):
            return None
        if not move.partner_id.vat:
            return None  # Or return a dict with a 'cancel' but no 'post'
        return {
            'post': self._my_format_post,
            'cancel': self._my_format_cancel,
            'edi_content': self._my_format_content,
            'post_batching': lambda m: (m.partner_id.country_id,),
        }

    # === Generation ===

    def _my_format_content(self, move):
        # Return raw bytes for preview
        return self._generate_edi_file(move)

    def _my_format_post(self, moves):
        result = {}
        for move in self.env['account.move'].browse(moves.ids):  # ensure individual records
            try:
                file_data = self._generate_edi_file(move)
                attachment = self.env['ir.attachment'].create({
                    'name': f'{move.name}_edi.xml',
                    'raw': file_data,
                    'res_model': 'account.move',
                    'res_id': move.id,
                })
                result[move] = {'success': True, 'attachment': attachment}
            except Exception as e:
                result[move] = {
                    'error': str(e),
                    'blocking_level': 'error',
                }
        return result

    def _my_format_cancel(self, moves):
        return {move: {'success': True} for move in moves}

    # === Helpers ===

    def _generate_edi_file(self, move):
        # Your EDI generation logic here
        tax_details = move._prepare_edi_tax_details()
        return b'<MyFormat>...</MyFormat>'

    # === PDF Embedding ===

    def _prepare_invoice_report(self, pdf_writer, edi_document):
        # Add this format's attachment as embedded file
        pass
```

**L4 - Critical Implementation Notes:**
- The `post` method receives a **recordset** of moves, not a single move. It should iterate and handle each individually.
- Return a dict keyed by `move` record (not move ID), with `{'success': True, 'attachment': attachment}` or `{'error': 'message', 'blocking_level': 'error'}`.
- Never raise exceptions from the `post`/`cancel` callables -- catch them and return an error result instead. An unhandled exception will crash the cron worker.
- `attachment` values should be `ir.attachment` records created with `res_model='account.move'` and `res_id=move.id` so they are considered business-linked and not auto-deleted.

---

## Odoo 18 to Odoo 19 Changes

| Change | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| Document model | `account.edi.document` introduced in Odoo 18 | Same; `edi_state` on `account.move` is now stored (previously computed only) |
| Async processing | `_cron_process_documents` | Renamed `_cron_process_documents_web_services`, `job_count` parameter |
| Attachment linking | Manual | Improved cleanup of orphaned attachments on re-generation |
| Peppol integration | Separate `account_peppol` module | Same, but with improved token out-of-sync handling |
| Proxy auth | HMAC only | Added asymmetric (RSA) auth for token resync |
| `edi_format_ids` on journal | Computed only | Stored with readonly=False (user can edit) |
| `_send_only_when_ready` context | Not used | Wraps the `post` method call in `_process_job` for dependent operations |
| `button_process_edi_web_services` | Not present | New UI trigger for manual single-invoice processing |
| `action_retry_edi_documents_error` | Not present | New "Retry" button in error alert banner |
| `edi_show_force_cancel_button` | Not present | New force cancel option for stuck cancellations |

---

## Related Documentation

- [Modules/Account](odoo-18/Modules/account.md) -- Invoice and journal entry management
- [Modules/account_peppol](odoo-17/Modules/account_peppol.md) -- Peppol EDI format (extends proxy user)
- [Modules/account_edi_proxy_client](odoo-18/Modules/account_edi_proxy_client.md) -- Base proxy HTTP client and auth
- [Core/API](odoo-18/Core/API.md) -- `@api.depends`, `@api.model`, `@api.constrains`
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) -- State machine patterns in Odoo
- [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) -- `search()`, `browse()`, `write()` with domain operators
- [New Features/API Changes](odoo-18/New Features/API Changes.md) -- Changes from Odoo 18 to 19
