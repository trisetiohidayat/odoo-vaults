---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #documents
  - #enterprise
---

# documents (Documents App)

## Module Overview

**Module Name:** `documents`  
**Type:** Enterprise (EE-only)  
**Location:** `enterprise/.../documents/`  
**Version:** 1.4  
**Category:** Productivity/Documents  
**License:** OEEL-1  
**Application:** Yes (appears in Apps menu)

**Summary:** The Documents app provides a centralized document management system built on top of Odoo's attachment infrastructure. It allows users to collect, organize, tag, share, and track documents across the entire ERP.

**Key Value Proposition:**
- Folder-based document organization with hierarchy
- Tag-based categorization with color coding
- Automatic document creation when attachments are linked to business records
- Granular access control per document or per folder
- Public link sharing with configurable view/edit permissions
- Activity tracking and deadline management on documents
- Mail alias support for direct document upload via email

**Dependencies:** `base`, `mail`, `portal`, `web_enterprise`, `attachment_indexing`, `digest`

---

## Architecture

### Design Philosophy

The `documents` module is built as a **wrapper around `ir.attachment`**, not a replacement. Each `documents.document` record owns a single `ir.attachment` record via the `attachment_id` field. This means:
- The actual binary/file data lives in `ir.attachment`
- Documents inherit all ir.attachment capabilities (storage, versioning, etc.)
- The documents layer adds: folder hierarchy, tags, access control, sharing, workflow

```
ir.attachment (binary storage)
    │
    │ 1-to-1 via attachment_id
    ▼
documents.document (management layer)
    ├── folder hierarchy (parent/child)
    ├── tags (many2many)
    ├── access control (folder + document level)
    ├── sharing (public links)
    └── activities (mail.activity)
```

### Mixin Pattern: `documents.mixin`

Any Odoo model can be extended with `documents.mixin` to automatically create a `documents.document` record whenever an attachment is linked to that model. This is how Documents integrates with Sale Orders, Purchase Orders, HR Contracts, etc.

The mixin provides overridable hooks:

| Method | Purpose |
|--------|---------|
| `_get_document_vals()` | Return vals to create the document record |
| `_get_document_owner()` | Who owns the document |
| `_get_document_folder()` | Which folder to place the document |
| `_get_document_tags()` | Default tags to apply |
| `_get_document_partner()` | Related partner |
| `_get_document_access_ids()` | Explicit partner access list |
| `_check_create_documents()` | Whether to create a document |

---

## Key Models

### 1. `documents.document` (Main Model)

The central model. Inherits `mail.thread`, `mail.activity.mixin`, and `mail.alias.mixin.optional`.

**Table:** `documents_document` (not to be confused with `ir_attachment`)

#### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `attachment_id` | Many2one `ir.attachment` | The actual file storage (1:1, cascade delete) |
| `datas` | Binary (related) | File content, proxied from attachment |
| `name` | Char | Document name (synced from attachment, translatable) |
| `file_extension` | Char | e.g. `pdf`, `xlsx` (computed/inversible) |
| `mimetype` | Char (related) | MIME type from attachment |
| `file_size` | Integer | File size in bytes |
| `checksum` | Char (related) | MD5 checksum |
| `type` | Selection | `binary` (file), `url` (link), `folder` |
| `active` | Boolean | Soft delete support |
| `sequence` | Integer | Manual ordering within folder |

#### Document Content Fields

| Field | Type | Description |
|-------|------|-------------|
| `url` | Char | External URL (for type=`url`) |
| `description` | Text | Attachment description |
| `thumbnail` | Binary | Preview image (auto-generated for images/PDFs) |
| `thumbnail_status` | Selection | `present`, `error`, `client_generated`, `restricted` |
| `is_multipage` | Boolean | True for multi-page PDFs |
| `previous_attachment_ids` | Many2many `ir.attachment` | Version history |

#### Relationship Fields

| Field | Type | Description |
|-------|------|-------------|
| `folder_id` | Many2one `documents.document` | Parent folder (for type=`folder`) |
| `children_ids` | One2many `documents.document` | Contents of a folder |
| `parent_path` | Char | Materialized path for hierarchy queries |
| `tag_ids` | Many2many `documents.tag` | Categorization tags |
| `partner_id` | Many2one `res.partner` | Associated contact |

#### Access Control Fields

| Field | Type | Description |
|-------|------|-------------|
| `owner_id` | Many2one `res.users` | Document owner |
| `access_via_link` | Selection | `view`, `edit`, `none` — permission for public link |
| `access_internal` | Selection | `view`, `edit`, `none` — permission for internal users |
| `is_access_via_link_hidden` | Boolean | Hide link access from parent folder inheritance |
| `access_ids` | One2many `documents.access` | Per-partner explicit access |
| `user_permission` | Selection (computed) | Current user's effective permission |
| `document_token` | Char | UUID token for sharing (unique) |
| `access_token` | Char (computed) | Public-facing token (`token + "o" + hex_id`) |

#### Activity / Workflow Fields

| Field | Type | Description |
|-------|------|-------------|
| `lock_uid` | Many2one `res.users` | User who locked the document |
| `request_activity_id` | Many2one `mail.activity` | Deadline/approval activity |
| `requestee_partner_id` | Many2one `res.partner` | Assigned reviewer |
| `create_activity_option` | Boolean | Enable activity creation on upload |
| `create_activity_type_id` | Many2one `mail.activity.type` | Activity type |
| `create_activity_user_id` | Many2one `res.users` | Activity assignee |

#### Link-to-Record Fields

| Field | Type | Description |
|-------|------|-------------|
| `res_model` | Char | Model the document is linked to |
| `res_id` | Many2oneReference | ID of linked record |
| `res_name` | Char | Display name of linked record |
| `shortcut_document_id` | Many2one `documents.document` | Source document for shortcuts |
| `shortcut_ids` | One2many `documents.document` | Shortcuts pointing to this document |

#### Key Computed Fields

- `_compute_access_token`: `{document_token}o{id_in_hex}`
- `_compute_access_url`: `/odoo/documents/{access_token}`
- `_compute_user_permission`: Resolves effective permission (owner > access_ids > folder > internal)
- `_compute_is_favorited`: Whether current user favorited this document
- `_compute_file_size`: File size from attachment (or shortcut target)
- `_compute_user_folder_id`: Virtual "MY" / "SHARED" / "COMPANY" folder classification
- `_compute_thumbnail`: Auto-generates image previews

#### Key Methods

```python
# Locking
def action_lock(self): ...
def action_unlock(self): ...

# Sharing
def _get_share_url(self): ...  # Returns the public share URL
def _send_share_document(self, partners, **kwargs): ...

# Activity
def action_create_activity(self): ...

# Download
def _get_download_url(self): ...
```

---

### 2. `documents.folder` (Implicit in `documents.document`)

Folders are simply `documents.document` records with `type = 'folder'`. The folder tree is implemented via:
- `folder_id` (Many2one to `documents.document`) — parent folder
- `children_ids` (One2many reverse) — child contents
- `parent_path` (materialized path, e.g. `1/2/5/`) — for efficient `child_of` queries
- `_parent_store = True` — automatic materialized path maintenance

Folders also carry inherited access control settings. Folder permissions cascade to all children unless overridden.

---

### 3. `documents.tag`

**Table:** `documents_tag`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required, translate) | Tag name |
| `sequence` | Integer | Ordering |
| `color` | Integer | Random color 1-11 |
| `document_ids` | Many2many `documents.document` | Documents with this tag |

**Constraint:** Tag names must be unique.

---

### 4. `documents.access`

Manages per-document, per-partner explicit access grants. This is the record that gets created when you share a document with specific partners.

**Table:** `documents_access`

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | Many2one `documents.document` | Target document |
| `partner_id` | Many2one `res.partner` | Partner being granted access |
| `role` | Selection | `view` or `edit` |
| `last_access_date` | Datetime | Last time this partner accessed the document |
| `expiration_date` | Datetime | Auto-removal of access |

**Constraints:**
- Unique `(document_id, partner_id)`
- Either `role` or `last_access_date` must be set

**Key Method:**
```python
def _gc_expired(self):  # @api.autovacuum
    # Deletes records where expiration_date <= now (batched, 1000 at a time)
```

---

### 5. `documents.mixin` (Abstract)

Not a table — an abstract model (`_name = 'documents.mixin'`) that other models inherit to get automatic document creation.

**Inherited by modules:** `account.move`, `sale.order`, `purchase.order`, `hr.contract`, and many more via bridge modules (e.g., `documents_hr`, `documents_account`, etc.)

---

### 6. `ir.attachment` Extensions

`documents` extends `ir.attachment` with:

```python
document_ids = fields.One2many('documents.document', 'attachment_id')

def _create_document(self, vals):
    # When attachment is linked to a documents.mixin record,
    # automatically creates a documents.document
    return True

@api.model_create_multi
def create(self, vals_list):
    # Hooks _create_document after attachment creation
```

Also handles PDF split operations:
```python
def _pdf_split(self, new_files=None, open_files=None):
    # Creates new ir.attachment records from split PDF pages
```

---

## Access Control System

### Permission Resolution Order

`user_permission` on `documents.document` is computed as follows (in priority order):

1. **System admin** (`group_documents_system`) → always `edit`
2. **Document owner** (`owner_id == current_user`) → `edit`
3. **Explicit access** via `documents.access` → `view` or `edit`
4. **Internal user rights** (`access_internal`) → if user is internal (not portal/share)
5. **Link access via parent folder** → if `access_via_link != 'none'` and not hidden
6. **No access** → `none`

### Folder-Level vs Document-Level

- **Folder-level**: Set `access_internal`, `access_via_link`, `access_ids` on the folder document — all children inherit
- **Document-level**: Override on individual documents to break inheritance

### Link Sharing

When a document is shared via link:
1. A unique `document_token` (UUID) is generated
2. `access_token` = `{token}o{id_in_hex}`
3. Public URL: `/odoo/documents/{access_token}`
4. Link permission controlled by `access_via_link` (`view` / `edit` / `none`)

---

## Document Workflow

```
Upload / Create
      │
      ▼
documents.document created
  (linked to ir.attachment via attachment_id)
      │
      ├── Assign to folder (folder_id)
      ├── Apply tags (tag_ids)
      ├── Set owner (owner_id)
      └── Configure access
              │
              ├── Folder inheritance (default)
              ├── Explicit partner access (access_ids)
              └── Public link (access_via_link)
                      │
                      ▼
              Share URL generated
              (document.access_url)
                      │
                      ▼
              Track activity / set deadline
              (request_activity_id)
```

### User Folder Virtual Folders

The document tree presents several "virtual" root folders to users:

| `user_folder_id` value | Meaning |
|------------------------|---------|
| `"MY"` | User's personal root — `folder_id=False AND owner_id=current_user` |
| `"COMPANY"` | Company root — `folder_id=False AND owner_id=False` |
| `"SHARED"` | Shared with me — has direct `access_ids` but no folder access |
| `"RECENT"` | Recently accessed via link |
| `"TRASH"` | Inactive (soft-deleted) documents |
| Integer | Specific folder ID |

---

## Key Business Features

### 1. Automatic Document Creation

When an attachment is added to a record that inherits `documents.mixin`, a `documents.document` is automatically created with:
- Folder from `_get_document_folder()`
- Owner from `_get_document_owner()`
- Tags from `_get_document_tags()`
- Access rights from `_get_document_access_ids()`

### 2. Document Sharing

Documents can be shared in three ways:
1. **Public link** — anyone with the URL can access (controlled by `access_via_link`)
2. **Partner sharing** — explicit access granted to partners (via `documents.access`)
3. **Email invite** — sends signup invitation to partner (using `documents.access._get_member_signup_token()`)

### 3. Activity Tracking

Documents can have deadline/approval activities attached via `request_activity_id`. This integrates with the Odoo Discuss/Activity system.

### 4. Mail Alias

Documents with `type = 'folder'` can have an email alias. Emails sent to the alias create attachments in that folder directly.

### 5. Shortcuts

Documents can have shortcuts (similar to Windows shortcuts) that point to other documents. Shortcuts can share across folders without duplicating the file.

---

## Integration Points

| Model | Integration | Description |
|-------|-------------|-------------|
| `ir.attachment` | Inheritance | Documents wrap attachments |
| `mail.thread` | Inheritance | Message threads on documents |
| `mail.activity.mixin` | Inheritance | Activity tracking |
| `mail.alias.mixin.optional` | Inheritance | Email-to-document |
| `res.partner` | `partner_id`, `access_ids` | Contact linking, access grants |
| `res.users` | `owner_id`, `favorited_ids` | Ownership, favorites |
| `res.company` | `company_id` | Multi-company document isolation |
| `documents.mixin` consumers | Auto-create | sale, purchase, account, hr bridge modules |

---

## Important Behaviors

### File Extension Sync

`file_extension` is inversible — setting it on a document updates the name of all shortcuts pointing to it:
```python
def _inverse_file_extension(self):
    (record | record.shortcut_ids).file_extension = file_extension
```

### Attachment Constraint

Only one `documents.document` can exist per `ir.attachment`:
```python
_attachment_unique = models.Constraint(
    'unique (attachment_id)',
    "This attachment is already a document",
)
```

### No Self-Reference

Documents cannot link to themselves or other documents as `res_model = 'documents.document'`:
```python
@api.constrains('res_model')
def _check_res_model(self):
    if self.filtered(lambda d: d.res_model == 'documents.document'):
        raise ValidationError(_('A document can not be linked to itself...'))
```

### Thumbnail Generation

Thumbnails are auto-generated server-side for images and PDFs. Client-side (browser) generated thumbnails are flagged with `thumbnail_status = 'client_generated'`.

---

## Demo Data

On installation, demo documents are loaded from `demo/documents_document_demo.xml`, including sample folders, documents, and tags.

---

## Related Modules

| Module | Purpose |
|--------|---------|
| `documents_account` | Bridges documents with account.move attachments |
| `documents_hr` | Bridges documents with HR records |
| `documents_spreadsheet` | Spreadsheet documents in Documents |
| `documents_sign` | DocuSign integration |
| `documents_product` | Product document management |
| `documents_project` | Project task attachments |

---

## See Also

- [Core/Fields](core/fields.md) — Binary fields, Many2many relations
- [Patterns/Security Patterns](patterns/security-patterns.md) — Access control design
- [Core/API](core/api.md) — Computed fields, @api.depends
- [Modules/Account](modules/account.md) — Document-account integration
