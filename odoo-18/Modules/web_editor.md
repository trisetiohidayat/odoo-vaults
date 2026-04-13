---
Module: web_editor
Version: 18.0
Type: addon
Tags: #web, #editor, #wysiwyg, #snippets, #odoo-editor
---

# web_editor — WYSIWYG Web Editor (Legacy)

## Module Overview

**Category:** Hidden
**Depends:** `bus`, `web`, `html_editor`
**License:** LGPL-3
**Auto-install:** True

The legacy jQuery-based rich text editor for Odoo (now superseded by `html_editor` which is OWL-based). Provides the WYSIWYG editor widget (`Wysiwyg`), snippet system, media dialog, image processing, and the Odoo Editor library. Used throughout the website builder and mass mailing. Auto-installs alongside `html_editor` for backward compatibility.

## Data Files

- `data/data.xml` — Assets definitions and snippet registry defaults
- `data/snippets.xml` — Predefined snippet catalog
- `data/res.config.xml` — Settings configuration
- `views/ir_attachment.xml` — Attachment image crop view
- `views/ir_model_view.xml` — View editor support
- `views/web_editor_templates.xml` — QWeb templates

## Static Assets (web.assets_frontend / web.assets_backend)

| Bundle | Files | Purpose |
|--------|-------|---------|
| `web_editor.assets_all` | all static/**/* | Full bundle |
| `web_editor.assets_snippets_menu` | snippets_menu/**/* | Snippet editor JS (drag/drop, options, menu) |
| `web_editor.wysiwyg_iframe_editor_assets` | iframe_editor_assets/**/* | Full iframe WYSIWYG editor bundle (includes Bootstrap, OWL, odoo-editor) |
| `web_editor.assets_wysiwyg` | wysiwyg/**/* | Main WYSIWYG JS + odoo-editor library |
| `web_editor.backend_assets_wysiwyg` | backend_wysiwyg/**/* | Backend-specific WYSIWYG bundle |
| `web_editor.assets_media_dialog` | media_dialog/**/* | Legacy media dialog components |
| `web_editor.assets_tests_styles` | tests/**/* | Test stylesheet bundle |

### Core Library: Odoo Editor (`static/src/odoo-editor/`)

The `odoo-editor` subdirectory contains the `OdooEditor.js` library (ODT-based contenteditable editor) plus:
- `commands/` — Enter, Tab, Shift-Tab, Delete, ToggleList, Align, etc.
- `tablepicker/` — Table picker dialog
- `powerbox/` — Powerbox (emoji/symbol picker)
- `utils/` — Serialization, sanitization, constants

## Models

### `ir.attachment` (`web_editor.models.models`)

**Inheritance:** `ir.attachment`

**Methods:**

**`_before_image_processing()`**
Returns original attachment ID and binary data before any processing. Used by image modification (crop/resize) to preserve original.

---

### `ir.qweb` (`web_editor.models.ir_qweb`)

**Inheritance:** `ir.qweb`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `asset_version` | Char | Version string for cache-busting on QWeb asset bundles |

**Methods:**

**`_get_asset_version(asset)`**
Returns the `asset_version` string. Falls back to manifest `version` or `1.0`.

---

### `ir.qweb.field.*` (`web_editor.models.ir_qweb_fields`)

**Inheritance:** Various `ir.qweb.field.*` mixins

**Classes:**

- **`ir.qweb.field.image`** — Enhanced with lazy loading, srcset, and SVG fallback support
- **`ir.qweb.field.html`** — Sanitizes HTML via `tools.clean_html()` before rendering

---

### `ir.ui.view` (`web_editor.models.ir_ui_view`)

**Inheritance:** `ir.ui.view`

**Methods:**

**`_get_edit_runtime_theme()`**
Returns the active theme during inline editing. Delegates to `theme_auto_sync` if installed.

**`_get_inherited_chatter_fields(view)`**
Returns list of chatter field names injected into form views.

**`_get_model_definitions(model_names)`**
Returns field definitions (from `_get_view()`) for a list of models. Used by the editor to know what fields are available.

**`_get_archived_fields_data(model_name)`**
Returns field definitions for archived fields on a model.

**`_get_arch_for_web_editor()`**
Returns the editable view arch with `t-name` removed (for WYSIWYG editing).

**`_get_view_by_name()`**
Returns the view ID for a given `(model, name)` pair.

**`_save_view_editor_view(values)`**
Saves view modifications from the WYSIWYG editor. Handles snippet customization, view name, and arch changes.

**`_normalize_html_on_save(html)`**
Normalizes pasted/edited HTML before saving. Applies `html_sanitize()` and processes `<img>` tags.

**`save_silently`** `@api.model`
Flag: suppresses `UserError` raises during save, returning error dict instead.

---

### `ir.attachment` — Multiple Image Attachments (`web_editor.models.models`)

**Inheritance:** `ir.attachment`

**Methods:**

**`_inverse_checked_attachments()`**
Writes `res_model`, `res_id`, `public`, `res_field` on the inverse attachments for a multi-image attachment field.

**`_filter_protected_attachments()`**
Returns attachments that are protected (cannot be deleted) because they are used by a protected attachment field.

---

### `ir.attachment` — Crop/Image Processing (`web_editor.models.models`)

**Inheritance:** `ir.attachment`

**Methods:**

**`_apply_image_processing(attachment, values)`**
Applies resize/crop/filter transformations to image attachment. Uses `tools.image_process()` for resize.

**`_crop_image_attachment(attachment, attachment_data)`**
Crops image attachment with provided coordinates (x, y, width, height, angle).

---

### `ir.http` (`web_editor.models.ir_http`)

**Inheritance:** `ir.http`

**Methods:**

**`_get_translation_frontend_modules_name()`**
Adds `'web_editor'` to the list of modules for frontend translation extraction.

---

### `ir.websocket` (`web_editor.models.ir_websocket`)

**Inheritance:** `ir.websocket`

**Methods:**

**`updated_changes(model, ...)`**
Broadcasts field update notifications to all sessions editing the same record in WYSIWYG mode. Called when an editable field value changes.

---

### `ir.actions.act_window` (`web_editor.models.ir_actions`)

**Inheritance:** `ir.actions.act_window`

**Methods:**

**`_get_readonly_params(params)`**
Returns readonly view context params (view_id, domain, context).

**`_set_editor_view_values(values, ctx)`**
Injects editor-mode view values into action context.

---

## Controllers

### `WebEditor` (`web_editor.controllers.main`)

**Routes:**

| Route | Auth | Methods | Description |
|-------|------|---------|-------------|
| `/web_editor/attach` | user | POST | Attach uploaded file to current document |
| `/web_editor/get_image_info` | user | POST | Get image dimensions/info from URL |
| `/web_editor/insert_field_button` | user | JSON | Insert dynamic field button into HTML |
| `/web_editor/get_needaction_access` | user | JSON | Check needaction (unread) access for model |

---

## Tools (`web_editor/tools.py`)

### `clean_html(html)`
Sanitizes and normalizes HTML using `lhtml` and `tools.clean_html()`. Wraps content in `<p>` if no block element is present. Handles CDN URLs, shape images, icon fonts, and snippets.

### `thumbnail(model, field, id, width, height)`
Generates a thumbnail image for a record's HTML field. Used by snippet drag-and-drop previews.

---

## Snippet Registry

Snippets are registered via `data/snippets.xml` and the JS snippet menu system. Key snippet categories:
- Content blocks (headers, paragraphs, images, galleries)
- Dynamic content (record lists, dynamic buttons)
- Interactive elements (tabs, accordions, carousels)

## What It Extends

- `ir.attachment` — image processing, crop, multiple attachments
- `ir.qweb` — asset versioning
- `ir.qweb.field.*` — HTML sanitization and image lazy loading
- `ir.ui.view` — WYSIWYG save and editing methods
- `ir.http` — translation module registration
- `ir.websocket` — live collaboration broadcast
- `ir.actions.act_window` — editor view context

---

## Key Behavior

- `web_editor` is the legacy jQuery editor — `html_editor` is the modern OWL replacement.
- Auto-installs alongside `html_editor` for backward compatibility with existing website and mass mailing content.
- The `odoo-editor` library (inside `static/src/odoo-editor/`) is the core contenteditable engine, inspired by ODT (OpenDocument Text) format.
- Snippet drag-and-drop uses the `assets_snippets_menu` bundle; the WYSIWYG itself uses `assets_wysiwyg`.
- Image processing (crop/resize) is stored on the attachment as `original_id` chain, preserving the ability to revert to original.
- `_normalize_html_on_save` applies `html_sanitize()` to all HTML before writing to the database, preventing XSS.
- Snippets XML can reference `data-snippet="..."` attributes for snippet-specific options rendering.
- v17 to v18: `html_editor` became the primary editor; `web_editor` maintained for backward compatibility.

---

## See Also

- [Modules/html_editor](html_editor.md) — Modern OWL-based editor (current)
- [Modules/web_unsplash](web_unsplash.md) — Unsplash image integration
- [Modules/theme_default](theme_default.md) — Default website theme
- [Modules/mass_mailing](mass_mailing.md) — Mass mailing editor
