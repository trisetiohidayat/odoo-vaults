---
date: 2026-04-11
tags:
  - #modules
  - #html-editor
  - #wysiwyg
  - #web-editor
  - #cms
  - #rich-text
  - #sanitization
  - #collaboration
  - #media
  - #snippets
  - #odoo19
---

# html_editor

> Rich text HTML editor component system with WYSIWYG editing, history versioning, collaboration, and media management.

---

## Module Overview

**Category:** Hidden
**Depends:** `base`, `bus`, `web`
**Auto-install:** Yes
**License:** LGPL-3
**Version:** 1.0
**Key architectural role:** Provides the unified Odoo rich text editor (successor to `web_editor`) used across backend and frontend for all `Html` fields.

This module consolidates all HTML editing capabilities into a single extensible framework. It provides the `<html_field>` widget, sanitization pipeline, snippet/template system, field history versioning with diffs, real-time collaboration via WebSocket/bus, video embedding, media library integration, and AI text generation via OLG.

---

## Directory Structure

```
html_editor/
├── __init__.py
├── __manifest__.py                 # Asset bundling (editor, media dialog, history diff)
├── controllers/
│   ├── __init__.py
│   └── main.py                     # All HTTP routes (media, SVG, collaboration, AI, link preview)
├── data/                           # (none)
├── models/
│   ├── __init__.py                 # ir_attachment, ir_http, ir_qweb_fields, ir_ui_view,
│   │                               # ir_websocket, models, test_models, html_field_history_mixin
│   ├── ir_attachment.py            # ir.attachment extended: image_src, local_url, original_id
│   ├── ir_http.py                 # ir.http: editor context flags (?editable, ?translatable)
│   ├── ir_qweb_fields.py           # ir.qweb + 12 field converters (html, image, date, etc.)
│   ├── ir_ui_view.py               # ir.ui.view: save, snippet CRUD, translations
│   ├── ir_websocket.py             # ir.websocket: collaboration channel registration
│   ├── models.py                   # base abstract: adds sanitize/sanitize_tags to field attrs
│   ├── html_field_history_mixin.py # Abstract mixin: JSON patch-based history versioning
│   ├── diff_utils.py               # Pure utility: patch format, apply_patch, generate_comparison
│   └── test_models.py              # html_editor.converter.test (admin-only test fixtures)
├── security/
│   └── ir.model.access.csv         # Admin-only ACLs for test models only
├── static/src/                     # Full JS/CSS editor implementation (OWL components)
└── views/                          # (none — all views are via asset bundles/static)
```

---

## Module Loading

The `models/__init__.py` imports in this order:

```python
from . import ir_attachment      # First: ir.attachment extensions
from . import ir_http            # ir.http extensions (editor context)
from . import ir_qweb_fields    # ir.qweb + field converters
from . import ir_ui_view        # ir.ui.view: view save/snippet (heavy)
from . import ir_websocket      # ir.websocket: collaboration channels

from . import models             # base abstract: field attribute extensions
from . import test_models        # Admin-only test models

from . import html_field_history_mixin  # Mixin: last — applied by consuming modules
```

The `controllers/main.py` is loaded via `__init__.py` at the controller level (separate from models).

**L4 — Load order significance:**
- `ir_attachment` must load before `ir_ui_view` because view saving logic references attachment URLs.
- `ir_http` runs in every HTTP request context — its overhead must remain minimal.
- `html_field_history_mixin` is a mixin designed to be inherited by consuming modules (mail, crm, etc.) rather than used standalone.
- The `test_models` are loaded but only accessible to `base.group_system` (admin-only).

---

## models/

### ir_http.py — `ir.http`

Handles editor-specific URL context parameters (`?editable`, `?edit_translations`, `?translatable`).

**Context keys recognized:** `editable`, `edit_translations`, `translatable`

- `_get_editor_context()` — Reads query-string args and returns dict mapping those keys to `True`. Only sets if not already in context and not already set in request context.

- `_pre_dispatch()` — Calls `_get_editor_context()` and merges into `request.env.context` before routing. Enables editor-aware rendering in controllers.

- `_get_translation_frontend_modules_name()` — Prepends `'html_editor'` to the list of modules whose translations should be loaded on the frontend (for translating snippets/templates).

**L4 — Security:** Editor context flags are read directly from query string. These are not privileged — they only affect rendering mode (editable vs. readonly). Actual write access is enforced by ORM access rights.

**L4 — Performance:** `_get_editor_context()` is called on every HTTP request via `_pre_dispatch`. The implementation is O(1) dict lookup — negligible overhead.

---

### res_config_settings.py — `res.config.settings`

A minimal extension adding two `config_parameter` fields:

```python
# These fields don't create database columns.
# They read/write to ir.config_parameter via the config_parameter key.
# Both require base.group_system (admin) to view or edit.
```

**Purpose:** Allows the html_editor module to store module-specific configuration (e.g., `html_editor.media_library_endpoint`, `html_editor.olg_api_endpoint`) in `ir.config_parameter` without needing a dedicated settings view. The fields are defined here so that `res.config.settings` can expose them if needed by an admin settings page.

**L4 — Why `config_parameter` fields here:** Odoo's pattern for per-module settings that live alongside global system parameters. No separate model/table needed.

---

### ir_ui_view.py — `ir.ui.view`

Extensive override of view saving, snippet management, and HTML processing for the CMS/website context.

**Key constants:**

`EDITING_ATTRIBUTES` = `MOVABLE_BRANDING` (from `base.ir_ui_view`) + `['data-oe-type', 'data-oe-expression', 'data-oe-translation-id', 'data-note-id']`

Attributes stripped before saving to prevent editing metadata from being persisted.

**Methods:**

- `_get_cleaned_non_editing_attributes(attributes)` — Removes `EDITING_ATTRIBUTES`, strips `o_editable` from classes, removes `contenteditable="true"`. Preserves all other attributes.

- `save(value, xpath=None)` — Main entry point for saving edited HTML into a view.
  - If `xpath` is `None`: calls `save_embedded_field()` directly (standalone embedded field).
  - Otherwise: iterates embedded fields, transforms them back to `t-field` references, processes `oe_structure` blocks.
  - Handles special footer patch for COW'd mega footer templates.
  - Writes new arch only if `_are_archs_equal()` detects actual change.
  - Sets `noupdate=True` on related model data to prevent future upgrades from overwriting.
  - Copies custom snippet translations via `_copy_custom_snippet_translations()`.

- `extract_embedded_fields(arch)` — XPath: `//*[@data-oe-model != 'ir.ui.view']` — finds all embedded field elements (from other models embedded in the view).

- `extract_oe_structures(arch)` — XPath: `//*[hasclass("oe_structure")][contains(@id, "oe_structure")]` — finds CMS structure placeholders.

- `save_embedded_field(el)` — For embedded field elements: uses the appropriate `ir.qweb.field.*` converter's `from_html()` to parse the rendered HTML back to a field value, then writes to the target record. Handles translation-aware writes.

- `save_oe_structure(el)` — Saves a CMS structure block as a child view (`mode='extension'`), inheriting from the current view, with a deterministic `key` based on the structure ID.

- `_copy_custom_snippet_translations(record, html_field)` — Detects `s_custom_snippet` elements in HTML and copies their translation terms from the snippet definition view into the record's field.

- `_copy_field_terms_translations(records_from, name_field_from, record_to, name_field_to)` — Copies all translation terms from one field to another across all installed languages. Uses `_get_translation_dictionary` to extract terms, merges into existing translations, writes with `check_translations=False` to avoid re-translation. Critical for snippet/template i18n.

- `save_snippet(name, arch, template_key, snippet_key, thumbnail_url)` — Saves user-created custom snippets:
  - Creates a `ir.ui.view` with QWeb arch for the snippet body.
  - Creates a second `ir.ui.view` (mode `extension`) that adds the snippet to the snippet palette via xpath on `//snippets[@id='snippet_custom']`.
  - Snippet key: `{app}.{snippet_key}_{uuid}` — uuid suffix prevents collisions.
  - Handles name deduplication within website domain.

- `rename_snippet(name, view_id, template_key)` — Updates name of snippet view and its addition view.

- `delete_snippet(view_id, template_key)` — Unlinks both the snippet body view and its addition view.

- `_views_get(view_id, ...)` — Returns all views related to a view (called via `t-call`, inherited). Used by translation mechanism, SEO, and optional templates. Respects `no_primary_children` context for hiding primary view extensions.

- `get_related_views(key, bundles=False)` — Gets all views for template `key` filtered by user group access. Uses `active_test=False` to include inactive optional views.

**L4 — Performance & Edge Cases:**
- `save()` parses the arch using `lxml.html.fromstring` with UTF-8 encoding. Malformed HTML from pasted content may raise `ParserError` — caught and re-raised as `ValidationError`.
- `_copy_field_terms_translations` flushes the source field (`flush_model`) and uses `check_translations=True` context to force reading of all language values. This can be slow for large translation dictionaries.
- The special footer patch (`website.footer_copyright_company_name`) handles a COW (Copy-On-Write) edge case where mega footer templates inherit through multiple levels. It modifies the grand-parent view directly via `with_context(no_cow=True)`.
- `save_snippet` uses `Domain` from `odoo.fields` for website-aware name searching — more powerful than standard domain tuples.
- `_are_archs_equal` compares element tag, text, tail, and attrib — not string representation. This prevents spurious writes from attribute ordering differences.

---

### ir_qweb_fields.py — `ir.qweb` and field converters

#### `ir.qweb` (abstract, `_name = 'ir.qweb'`)

QWeb template compiler for snippet directives.

**Methods:**

- `_compile_directive_snippet(el, compile_context, indent)` — processes `t-snippet` directive: sets `t-call`, `t-options` with `snippet-key`, builds wrapper `<div>` with `data-oe-type="snippet"` and `data-oe-snippet-id/key/name/keywords/thumbnail` attributes. Respects `t-forbid-sanitize`, `t-grid-column-span`, `snippet-group`, `group`, `label`, `t-image-preview` attributes.

- `_compile_directive_snippet_call(el, compile_context, indent)` — processes `t-snippet-call`: sets `t-call`, `t-options` with `snippet-key` and `snippet-name`. Used for calling snippets from within templates.

- `_compile_directive_install(el, compile_context, indent)` — processes `t-install`: renders a "Click to install module" snippet. Only visible to `base.group_system` users. Checks `ir.module.module` state.

- `_compile_directive_placeholder(el, compile_context, indent)` — Sets `t-att-placeholder` from `t-placeholder`.

- `_compile_node(el, compile_context, level)` — Injects `data-snippet` and `data-name` attributes on the root node of a snippet template (only on first compilation pass, not inherited/saved snippets).

- `_get_preload_attribute_xmlids()` — Adds `'t-snippet', 't-snippet-call'` to the list of XMLIDs that QWeb preloads. Ensures snippet templates are available without full render.

- `_directives_eval_order()` — Inserts `placeholder`, `snippet`, `snippet-call`, `install` before the `att` directive (so static attributes are preserved before being cleared).

- `_get_template_cache_keys()` — Adds `'snippet_lang'` to cache keys for snippet-specific template caching.

#### Field Converters (all abstract models)

Each converter handles the round-trip: field value → rendered HTML (`attributes()`) and rendered HTML → field value (`from_html()`).

| Converter | Key behavior |
|---|---|
| `ir.qweb.field` | Base: uses `placeholder` option/field attribute, sets `data-oe-translation-state` for translated char/text fields. `from_html`: strips and returns `element.text_content()`. |
| `ir.qweb.field.integer` | `from_html`: strips locale-specific thousands separator before `int()`. |
| `ir.qweb.field.float` | `from_html`: strips locale thousands sep and replaces locale decimal point with `.`. |
| `ir.qweb.field.many2one` | `attributes()`: sets `data-oe-many2one-id/model/domain/allowreset`. `from_html`: writes `many2one_id` to the field, handles reset via `allowreset` flag. |
| `ir.qweb.field.contact` | `attributes()`: sets `data-oe-contact-options` JSON. |
| `ir.qweb.field.date` | `attributes()`: sets `data-oe-original` (ISO), `data-oe-original-with-format` (locale-formatted). For datetime fields: also sets `data-oe-type='datetime'` and delegates to datetime converter. `from_html`: parses using user's `date_format`. |
| `ir.qweb.field.datetime` | `attributes()`: converts UTC value to user's timezone (`tz` context or `user.tz`), formats with `babel.dates.format_datetime`. `from_html`: parses user input, converts back to UTC using the stored `data-oe-original-tz`. Fails gracefully with `logger.warning` if timezone conversion fails. |
| `ir.qweb.field.text` | `from_html`: uses `html_to_text()` utility (converts `<br>`, `<p>`, block elements to newlines). |
| `ir.qweb.field.selection` | `from_html`: matches displayed label text (`v`) to selection key (`k`). Raises `ValueError` if no match. |
| `ir.qweb.field.html` | `attributes()`: sets `data-oe-sanitize` flag based on field's `sanitize`, `sanitize_attributes`, `sanitize_form`, and user's `base.group_sanitize_override` membership. If user can bypass sanitization but field would lose content, sets `data-oe-sanitize-prevent-edition=1` to make the field read-only. **This is the core XSS prevention mechanism.** |
| `ir.qweb.field.image` | `from_html`: extracts `src` from `<img>`. Parses `/web/image/<id>`, `/web/image/<model>/<id>/<field>`, or local/static URLs. Loads and re-encodes via PIL to normalize image data. |
| `ir.qweb.field.monetary` | `from_html`: extracts `<span>` text content and parses as float with locale separators. |
| `ir.qweb.field.duration` | `attributes()`: sets `data-oe-original`. `from_html`: parses float value. |
| `ir.qweb.field.relative` | Inherits formatting from `ir.qweb.field.relative` base, uses datetime for edition. |

#### `html_to_text(element)` utility

Converts HTML with structural elements (`<br>`, `<p>`, block elements) to approximate plain text with newlines.

- `_PADDED_BLOCK = {"p", "h1".."h6"}` — 2 newlines before and after
- `_MISC_BLOCK = {"address", "article", "aside", "audio", "blockquote", "canvas", "dd", "dl", "div", "figcaption", "figure", "footer", "form", "header", "hgroup", "hr", "ol", "output", "pre", "section", "tfoot", "ul", "video"}` — 1 newline before and after
- Collapses whitespace sequences with `re.sub(r'\s+', ' ', text)`
- `<br>` → single newline
- Other tags → inline, preserves tail text

**L4 — Sanitization in `ir.qweb.field.html`:**

The `sanitize` attribute on `Html` fields is the primary XSS prevention mechanism in Odoo. The `attributes()` method sets the `data-oe-sanitize` flag that tells the frontend how to handle the field:

- `sanitize=False`: No sanitization, full HTML allowed (dangerous, admin use only)
- `sanitize=True`: All dangerous tags/scripts stripped via DOMPurify
- `sanitize_form=True`: Form elements (`<form>`, `<input>`) allowed (for email HTML)
- `sanitize_attributes=True`: Certain attributes allowed (`href`, `src` with whitelisted protocols, `style`)
- `sanitize_tags=True`: Even basic formatting tags stripped

The `base.group_sanitize_override` group bypasses sanitization. When a user with this privilege saves content that would be stripped under normal sanitization, the `data-oe-sanitize-prevent-edition=1` flag makes the field read-only in the editor — preventing accidental loss of their bypass-enabled content.

---

### ir_attachment.py — `ir.attachment`

Extends `ir.attachment` with editor-specific computed fields.

**Fields added:**

| Field | Type | Compute | Purpose |
|---|---|---|---|
| `local_url` | `Char` | `_compute_local_url` | Attachment URL for editor rendering. Uses `url` if external, else `/web/image/{id}?unique={checksum}`. |
| `image_src` | `Char` | `_compute_image_src` | Full `src` attribute value for `<img>` tags. Handles URL-encoded names, redirects, cache busters. Only for `SUPPORTED_IMAGE_MIMETYPES`. |
| `image_width` | `Integer` | `_compute_image_size` | Pixel width from `base64_to_image()`. |
| `image_height` | `Integer` | `_compute_image_size` | Pixel height from `base64_to_image()`. |
| `original_id` | `Many2one(ir.attachment)` | — | Reference to the original unoptimized, unresized attachment. Indexed with `btree_not_null`. Used for re-editing images (crop, filters). |

**SUPPORTED_IMAGE_MIMETYPES:**
```python
{'image/gif': '.gif', 'image/jpe': '.jpe', 'image/jpeg': '.jpeg',
 'image/jpg': '.jpg', 'image/png': '.png', 'image/svg+xml': '.svg',
 'image/webp': '.webp'}
```

**Methods:**

- `_get_media_info()` — Returns dict of media dialog values: `id, name, description, mimetype, checksum, url, type, res_id, res_model, public, access_token, image_src, image_width, image_height, original_id`. Used by editor media dialog when selecting existing attachments.

- `_can_bypass_rights_on_media_dialog()` — Hook for modules like `website_forum` to allow portal users to upload images without general attachment creation rights. Override returns `True` to bypass.

**L4 — Security & Edge Cases:**
- `image_src` compute depends on `mimetype, url, name, checksum`. Any change to these triggers recomputation.
- For URL-based attachments by path (`/web/image/<id>-redirect/<name>`), the `unique` query param acts as a cache buster. Static file attachments rely on browser cache with `max-age` headers.
- SVG images are included in supported mimetypes — XSS risk is mitigated by Odoo's sanitizer at the Html field level.
- `image_size` compute wraps PIL calls in `try/except UserError`. Corrupt image data results in `0x0` dimensions, silently.

---

### ir_websocket.py — `ir.websocket`

Extends WebSocket channel building to register editor collaboration channels.

**Channel format:** `editor_collaboration:{model_name}:{field_name}:{res_id}`

**`_build_bus_channel_list(channels)` override:**
- Parses channel strings matching regex `editor_collaboration:(\w+(?:\.\w+)*):(\w+):(\d+)`.
- For each collaboration channel: verifies `read` + `write` access on the record, verifies `read` + `write` access on the specific field.
- Rejects public users (`_is_public()` raises `AccessDenied`).
- Missing records are silently skipped (not broadcast).
- Adds the canonical channel tuple `(db_name, 'editor_collaboration', model_name, field_name, res_id)` to the channel list.

**L4 — Security:**
- This is the gatekeeper for real-time editor collaboration. If access check fails, the channel is not added — no notification is sent to unauthorized users.
- `document.exists()` check prevents broadcasting to deleted records.
- Field-level access control (`_check_field_access`) ensures users can't collaborate on fields they can't write to.

---

### models.py — `base`

Extends `base` (abstract) to add `sanitize` and `sanitize_tags` to the list of field attributes recognized in view definitions (form node attributes).

- `_get_view_field_attributes()` — Adds `'sanitize'` and `'sanitize_tags'` to the keys returned by the base method. This allows these attributes to be read from XML field definitions and applied to the field's view representation.

**L4 — Why this matters:** In XML view definitions, `sanitize="0"` or `sanitize_tags="1"` can be set directly on `<field>` nodes. Without this extension, those attributes would be ignored during field processing. With it, Odoo correctly applies the sanitization rules to the rendered HTML.

---

### html_field_history_mixin.py — `html.field.history.mixin`

Abstract mixin for storing versioned HTML field history using JSON patches. Enables undo/restore UI dialogs.

**Fields:**

| Field | Type | Description |
|---|---|---|
| `html_field_history` | `Json` | Stores patch-based revision history per field. Each entry: `{patch, revision_id, create_date, create_uid, create_user_name}`. Prefetch disabled (raw Json). |
| `html_field_history_metadata` | `Json` (computed) | Read-only view of history without the `patch` payload. Used by history dialog to list revisions without downloading patch data. |

**Methods:**

- `_get_versioned_fields()` — Override to return list of field names to track. Default returns `[]`. Example: `return ['html_description', 'html_manual']`.

- `_compute_metadata()` — Computes `html_field_history_metadata` by iterating `html_field_history` and stripping the `patch` key from each revision. Preserves `revision_id`, `create_date`, `create_uid`, `create_user_name`.

- `write(vals)` — **Critical override.** On any write to a versioned field:
  1. Captures pre-write content for each versioned field (`rec_db_contents`).
  2. Calls `super().write(vals)` first — ensures diff is computed on **sanitized** data (sanitization happens in `HtmlField.convert_to_column_insert`).
  3. Detects which fields actually changed (`new_content != old_content`).
  4. For each changed field: generates a `generate_patch(new_content, old_content)` patch, assigns a sequential `revision_id`, prepends to history array with creation metadata.
  5. Calls `super().write()` a second time to persist the updated `html_field_history` Json.
  6. Truncates history to `_html_field_history_size_limit` (default **300** revisions per field).
  7. **Validation:** Raises `ValidationError` if any versioned field does not have `sanitize=True`. Unsanitized HTML is a security risk in stored version history.

- `html_field_history_get_content_at_revision(field_name, revision_id)` — Reconstructs field content as of `revision_id` by applying all patches from `revision_id` through HEAD in reverse. Returns plain HTML string.

- `html_field_history_get_comparison_at_revision(field_name, revision_id)` — Returns HTML comparison (marked with `<added>`/`<removed>` tags) between current content and restored content at `revision_id`. Uses `diff2html` bundle for rendering.

- `html_field_history_get_unified_diff_at_revision(field_name, revision_id)` — Returns unified diff string (standard `diff -u` format) between current and restored content.

**Class-level constant:** `_html_field_history_size_limit = 300`

**L4 — Performance & Edge Cases:**
- Each write to a versioned record triggers a **second `super().write()` call** inside the loop. For multi-record writes, this is inside a `for rec in self` loop. If writing 100 records with 3 versioned fields, this could cause up to 300 writes. In practice, HTML fields are rarely bulk-written.
- The Json field is stored directly on the record's table. With 300 revisions stored as JSON, row size can become significant. Consider partitioning history into a separate table for high-volume use cases.
- `apply_patch` operates on content split by `<` character (LINE_SEPARATOR). This means patch indexes are relative to the post-sanitization HTML structure. If sanitization changes between Odoo versions, stored patches may not apply correctly.
- Historical patches store content including any custom data attributes. Patches should be stable as long as sanitization rules don't change.
- When `install_module` context key is set, history divergence checking is skipped — prevents errors during module upgrades that update HTML content.

---

### diff_utils.py — Patch Engine

Custom patch format for HTML diff/versioning. Not a model — pure utility module.

**Patch Format:**
```
+@4:<p>ab</p><p>cd</p>
+@4,15:<p>ef</p><p>gh</p>
-@32
-@125,129
R@523:<b>sdf</b>
```
Format: `<op>@<start>[,<end>][:<content>]`. Operations applied in **reverse order** to preserve index stability.

**Functions:**

| Function | Purpose |
|---|---|
| `generate_patch(new, old)` | Generates forward patch to reverse `new` back to `old`. Uses `difflib.SequenceMatcher.get_grouped_opcodes()`. |
| `apply_patch(initial, patch)` | Applies patch operations to `initial` content. Returns patched HTML. |
| `generate_comparison(new, old)` | Produces HTML with `<added>` and `<removed>` tags for visual diff display. |
| `generate_unified_diff(new, old)` | Standard unified diff (like `diff -u`). Used by history dialog diff tab. |
| `_patch_generator(new, old)` | Core iterator yielding patch operation strings via SequenceMatcher. |
| `_indent(content)` | Wraps HTML in `<document>` and uses BeautifulSoup prettify for readable diff output. |
| `_remove_html_attribute(html, attrs)` | Strips `data-last-history-steps` attribute before diffing (prevents false divergence detection). |

**HTML_ATTRIBUTES_TO_REMOVE = ["data-last-history-steps"]** — This attribute stores collaboration step IDs; it must be stripped before computing diffs or patches to prevent false divergence.

**L4 — Edge Cases:**
- `apply_patch` splits by `<` (opening tag character). HTML entities like `&lt;` or `&#60;` that contain `<` will cause index misalignment. However, sanitization converts entities to literal characters, so this is controlled.
- `generate_comparison` has logic to handle "ghost opening tags" — cases where only attributes change (e.g., `<p class="x">` to `<p class="y">`). The function flags those lines as `delete_me>` (removed later) to avoid spurious diff noise.
- `UNNECESSARY_REPLACE_FIXER` regex: `<added>abc</added><removed>abc</removed>` collapses to `abc`. This handles cases where tag attributes change but content is identical.

---

### test_models.py — Test fixtures

Not for production. Two models used for converter testing:

**`html_editor.converter.test`:**
```python
char, integer, float, numeric, many2one, binary, date, datetime,
selection_str, html, text  # all standard fields
```

**`html_editor.converter.test.sub`:**
```python
name  # simple related record
```

Both require `base.group_system` (admin-only access as per `ir.model.access.csv`).

---

## controllers/main.py — HTTP Endpoints

### Media Management

| Route | Auth | Method | Purpose |
|---|---|---|---|
| `/web_editor/attachment/add_data` | user | POST | Upload image/data attachment. Applies `image_process()` with resize, quality. Deduplicates by checksum. |
| `/web_editor/attachment/add_url` | user | POST | Add external URL as attachment. Validates MIME type via HEAD request. |
| `/web_editor/attachment/remove` | user | DELETE | Remove attachment if not used in any view. Returns blocked views. |
| `/web_editor/get_image_info` | user | GET | Get attachment info by `src` URL for re-editing (crop/filter). |
| `/web_editor/modify_image/<attachment>` | user | POST | Create modified copy (crop, resize, format conversion) with `original_id` link. Stores WebP/JPEG alternates in `alt_data`. |

**L4 — `_attachment_create` flow:**
1. Validates name (strips `.bmp` extension to avoid mimetype mismatch)
2. For URL attachments: issues `HEAD` request to validate MIME type before saving
3. Checks `_can_bypass_rights_on_media_dialog` — allows portal users to upload via sudo if overridden
4. Deduplicates by checksum (`get_existing_attachment`) — avoids re-uploading identical images
5. For non-public attachments, generates access token via `sudo()` so the uploader can still view their image

**L4 — `modify_image` alt_data:** When an image is modified (cropped, resized), the client sends `alt_data` with `image/webp` and/or `image/jpeg` variants. These are stored as separate attachment records linked to the main attachment, enabling srcset-based responsive images.

### SVG Shapes & Color Customization

| Route | Auth | Purpose |
|---|---|---|
| `/web_editor/shape/<module>/<path:filename>` | public | Return color-customized SVG (shapes/illustrations). Supports flip (`?flip=x/y/xy`) and animation speed (`?shapeAnimationSpeed`). |
| `/web_editor/image_shape/<img_key>/<module>/<filename>` | public | Wrap image in SVG mask/shape. Extracts image dimensions, sets SVG size, inlines image as base64. |

`_update_svg_colors(options, svg)` — Parses color options (`c1..c5` keys) and SVG palette mapping. Supports hex, RGBA, and `o-color-1..5` theme color references (resolves against bundle CSS). Rejects invalid colors with `BadRequest`.

`replace_animation_duration(shape_animation_speed, svg)` — Modifies CSS `animation-duration`, SVG `dur` attributes, and `--animation_ratio` CSS variable by the speed ratio. Speed > 0 speeds up (duration / (1 + speed)), speed < 0 slows down (duration / (1 - speed)).

**L4 — SVG Color Resolution for `o-color-N`:** When a user picks a theme color (`o-color-1` through `o-color-5`), the server reads the compiled CSS from `web.assets_frontend` bundle and searches for `--o-color-N: <value>`. This requires the bundle to be compiled first — it works on the frontend but the server-side lookup in `_update_svg_colors` requires the same asset compilation.

### Media Library

| Route | Auth | Purpose |
|---|---|---|
| `/html_editor/media_library_search` | user | Proxy to Odoo's media library API. Passes `dbuuid` for entitlement check. |
| `/web_editor/save_library_media` | user | Download media library assets as attachments. Creates dynamic SVG attachments for SVGs with color placeholders. |

**L4 — Media library endpoint:** The `html_editor.media_library_endpoint` config parameter (default: `https://media-api.odoo.com`) controls the media library source. `dbuuid` is sent for usage tracking/ entitlement checks. Downloads use `SUPERUSER_ID` to bypass attachment ACLs.

### AI Text Generation

`/web_editor/generate_text` — Calls OLG (Odoo Language Generation) API via IAP. Passes `prompt`, `conversation_history`, and `database_id`. Handles error responses: `error_prompt_too_long`, `limit_call_reached`, generic error. **Requires IAP credit.**

**L4 — IAP timeout and fallback:** `iap_jsonrpc` is called with `timeout=30`. `AccessError` is caught and re-raised as "Oops, it looks like our AI is unreachable!" — providing a user-friendly message for IAP service failures.

### Collaboration

| Route | Auth | Purpose |
|---|---|---|
| `/web_editor/bus_broadcast` | user | Broadcast editor collaboration event to all subscribers of the field's channel. Checks read+write access on record and field. |
| `/web_editor/get_ice_servers` | user | Proxy to `mail.ice.server` for WebRTC peer connection establishment. |

**L4 — `bus_broadcast` access control:** This endpoint verifies `read` + `write` access on the record and field before broadcasting. This is the same check as `ir_websocket._build_bus_channel_list` but enforced at the broadcast level — defense in depth.

### Link Previews

| Route | Auth | Purpose |
|---|---|---|
| `/html_editor/link_preview_external` | public | Fetch OGP metadata from external URL. Returns `og_description` (HTML-decoded). |
| `/html_editor/link_preview_internal` | user | Resolve internal Odoo URLs to record descriptions. Supports `/odoo/<model>/<id>`, `/web/<action>/<id>`, `/@/<model>/<id>` path formats. Falls back to external preview for non-matching paths. |

**L4 — Internal link preview resolution:** The `link_preview_internal` method handles three URL formats:
- `/odoo/<model>/<id>` — Direct model record URL (e.g., `/odoo/sale.order/123`)
- `/web/<action>/<id>` — Window action URL (e.g., `/web/action/123`)
- `/@/<model>/<id>` — "At" notation (e.g., `/@/sale.order/123`)

For `/web/<action>` paths, it resolves the action's `res_model` and fetches the record's `description`, `link_preview_name`, or `display_name`. Falls back to external OGP fetch for unrecognized paths.

---

## tools.py — Utility Functions

### Video Embedding

`get_video_source_data(video_url)` — Detects platform from URL. Returns `('platform', video_id, regex_match)` or `None`. Supports: **youtube, vimeo, dailymotion, instagram, facebook**.

`get_video_url_data(video_url, autoplay, loop, hide_controls, hide_fullscreen, hide_dm_logo, hide_dm_share, start_from)` — Returns:
```python
{'platform': str, 'embed_url': str, 'video_id': str, 'params': dict}
# or {'error': True, 'message': '...'}
```

Platform-specific behavior:
- **YouTube:** Sets `rel=0` (no related videos from other channels), adds `enablejsapi=1` for mobile autoplay, uses `playlist={id}` for loop.
- **Vimeo:** Sets `dnt=1` (Do Not Track), uses `autopause=0` when muted autoplay.
- **DailyMotion:** Uses `geo.dailymotion.com` player for geo-restriction compliance.
- **Instagram:** Returns oEmbed embed URL.
- **Facebook:** Constructs Facebook plugins video URL.

`get_video_embed_code(video_url)` — Returns complete `<iframe>` HTML string with responsive classes and `allow` attributes. Returns `None` for invalid URLs.

`get_video_thumbnail(video_url)` — Fetches thumbnail from platform APIs:
- YouTube: `img.youtube.com/vi/{id}/0.jpg` — always available.
- Vimeo: oEmbed JSON API — requires network call.
- DailyMotion: `dailymotion.com/thumbnail/video/{id}` — requires network call.
- Instagram: `instagram.com/p/{id}/media/?size=t` — requires network call.

Uses `image_process()` on fetched data to normalize format. All requests have 10-second timeout; failures silently return `None`.

### History Divergence Detection

`handle_history_divergence(record, html_field_name, vals)` — Called during `write()` to detect concurrent edit conflicts in collaboration mode.

- Reads `data-last-history-steps` attribute from incoming HTML and server HTML.
- If server's last step ID is not in incoming's history IDs, raises `ValidationError`: "The document was already saved from someone with a different history..."
- Sends `bus.bus` notification with `last_step_id` for real-time collaboration awareness.
- Skipped when `install_module` context is set (no divergence checks during upgrades).
- Strips the `data-last-history-steps` attribute from the saved HTML after extracting the step ID.

**L4 — Collaboration Architecture:**
The collaboration system uses a three-part mechanism:
1. **IrWebsocket:** Registers per-field collaboration channels on connect (`_build_bus_channel_list`).
2. **IrHttp:** Extracts `?editable` flags from URL for frontend context.
3. **handle_history_divergence:** Validates incoming edits against stored history step IDs and broadcasts step updates via `bus.bus`.

---

## Security (`security/ir.model.access.csv`)

```csv
access_html_editor_converter_test,access_html_editor_converter_test,
  model_html_editor_converter_test,base.group_system,1,1,1,1
access_html_editor_converter_test_sub,access_html_editor_sub,
  model_html_editor_converter_test_sub,base.group_system,1,1,1,1
```

Both test models are **admin-only** (no portal/user access). No production models are defined in `html_editor` itself — it extends existing ones. The `ir.attachment`, `ir.ui.view`, and `ir.websocket` models use their existing access rules from base/web.

**L4 — No production ACLs defined:** This is intentional. `html_editor` does not introduce new record types — it only extends existing models (`ir.attachment`, `ir.ui.view`). Those models have their own ACLs defined in `base` and `web`. The test models need explicit admin-only ACLs because test models are not covered by automatic access rules.

---

## Asset Bundles

```python
html_editor.assets_editor        # Core editor JS/CSS (excludes dark theme SCSS)
html_editor.assets_history_diff  # diff2html library for history comparison UI
html_editor.assets_media_dialog  # Media dialog component (shared backend/frontend)
html_editor.assets_readonly     # Readonly HTML viewer + embedded components
html_editor.assets_image_cropper # CropperJS + WebGL image filter
html_editor.assets_prism         # Syntax highlighting (prismjs)
html_editor.assets_prism_dark   # Dark theme prism
```

SCSS hierarchy:
```
web._assets_primary_variables  →  html_editor.variables.scss       # Bootstrap variable overrides
web._assets_secondary_variables → secondary_variables.scss         # Extended palette
web._assets_backend_helpers    → bootstrap_overridden_backend.scss # Backend-specific overrides
web._assets_frontend_helpers  → bootstrap_overridden.scss         # Frontend-specific overrides
web.report_assets_common       → base_style, bootstrap_overridden, html_editor.common  # PDF reports
```

**L4 — Asset inheritance:** The `assets_editor` bundle is the canonical bundle that includes all core editor components. It is included in `web.assets_backend`. The `assets_media_dialog` and `assets_readonly` bundles are included in both `web.assets_frontend` and `web.assets_backend` — this allows the media dialog to work in both contexts without duplicating the JS.

---

## Odoo 18 → 19 Changes

1. **Module rename:** `web_editor` → `html_editor`. All routes are aliased (`/web_editor/*` and `/html_editor/*` both work).
2. **SVG dynamic color:** The color customization system for SVG shapes was extended with a palette mapping system supporting `o-color-N` theme references.
3. **History mixin:** The `html_field_history_mixin` was introduced or significantly extended in 19 as the basis for the history/restore dialog.
4. **WebP image support:** Full support for WebP format in image attachment processing (`get_webp_size`, format conversion).
5. **Collaboration channel security:** Field-level access control in WebSocket channel registration (`_check_field_access` for both `read` and `write`).
6. **Dynamic SVG illustrations:** Media library dynamic SVGs with color parameters via `/html_editor/shape/illustration/{slug}`.
7. **AI text generation:** OLG integration via `/web_editor/generate_text` for AI-assisted writing.
8. **Link preview internal:** Enhanced internal link preview resolution supporting action-path URLs.
9. **Sanitization metadata in branding:** `data-oe-sanitize-prevent-edition` flag for fields that would lose content under sanitization, with `base.group_sanitize_override` bypass.
10. **OWL-based frontend:** The entire editor UI (components, plugins, fields) is now implemented as OWL components — a rewrite from the previous jQuery/Backbone architecture.

---

## Cross-Module Integration

| Module | Integration Point |
|---|---|
| `mail` | Uses `ir.qweb.field.html` for rendering email body fields. Collaboration bus channels shared with mail gateway. |
| `website` | `ir.ui.view` save/snippet system is the CMS editing engine. `save_oe_structure`, custom snippet saving, website-specific snippet palette. |
| `website_sale` / `sale` | Email templates (`mail.template` models) use `ir.qweb.field.html` converters. |
| `web` | Provides the field widget, asset bundles, DOMPurify sanitization library. |
| `bus` | Real-time collaboration via `bus.bus`. `ir.websocket` registers collaboration channels. |
| `iap` | AI text generation via `iap_tools.iap_jsonrpc`. |
| `link_preview` (`mail` addon) | Link preview metadata fetching for internal/external URLs. |
| `stock` / `mrp` | Email notifications with rich text descriptions. |
| `base` | `sanitize` and `sanitize_tags` field attributes, `base.group_sanitize_override` group. |

---

## Key Edge Cases & Failure Modes

1. **Patch index corruption:** If HTML sanitization rules change between Odoo versions, stored JSON patches (with indexes based on the previous sanitized structure) may fail to apply correctly. The `html_field_history` becomes unreadable but the current field value remains intact.

2. **Sanitization mismatch on restore:** `html_field_history_get_content_at_revision` restores content by applying patches. The restored content is then subject to current sanitization rules on write — old content with disallowed tags will be silently stripped.

3. **Video thumbnail network dependency:** `get_video_thumbnail()` makes HTTP requests to YouTube/Vimeo/DailyMotion/Instagram APIs. Failures are silent (`contextlib.suppress`). This is a soft dependency — missing thumbnails do not break the editor.

4. **Image dimension compute on malformed images:** `_compute_image_size` wraps PIL calls in `try/except UserError`. Corrupt image data results in `0x0` dimensions, silently.

5. **Collaboration channel ghost subscriptions:** `IrWebsocket._build_bus_channel_list` silently skips records that don't exist (`document.exists()`). However, if a user had previously subscribed to a channel for a since-deleted record, the bus may retain that subscription in memory until the WebSocket connection is closed.

6. **Memory pressure from large HTML fields with history:** A single `Html` field with 300 revisions stored as JSON can consume significant memory during `write()`. The entire history is loaded, patched, truncated, and written back in a single operation.

7. **SVG animation speed regex edge cases:** The CSS animation regex (`CSS_ANIMATION_RULE_REGEX`) may not match all animation shorthand formats. Animations using non-standard syntax will not have their duration modified.

8. **Snippet name deduplication:** `save_snippet` uses `name LIKE 'name%'` for the website domain. This can match unintended snippets if names share prefixes. The `_find_available_name` helper handles collisions but the LIKE query is broad.

9. **Translation copy across large records:** `_copy_field_terms_translations` reads all language values of both source and target fields. For records with very long HTML content, this can generate large translation dictionaries consuming significant memory during the copy operation.

10. **OLG API rate limiting:** `generate_text` has a 30-second timeout and handles `limit_call_reached` explicitly. The IAP credit system is the gating mechanism, but there's no local rate limiting.

11. **Timezone conversion failures:** `IrQwebFieldDatetime.from_html` catches all exceptions during timezone conversion and logs a warning, then proceeds. This means an invalid timezone stored in `data-oe-original-tz` will silently fall back to UTC, potentially corrupting datetime values.

12. **XSS in unsanitized Html fields:** Any model that uses `Html(sanitize=False)` and stores user-submitted content is vulnerable to stored XSS. The editor itself does not prevent this — the consuming module must enforce sanitization.

---

## Related Documentation

- [Core/Fields](Core/Fields.md) — Html field type, `sanitize`, `sanitize_attributes`, `sanitize_form`, `sanitize_tags` attributes
- [Core/API](Core/API.md) — `@api.depends`, `@api.onchange` for computed field patterns
- [Tools/ORM Operations](Tools/ORM-Operations.md) — `write()`, domain operators, recordset behavior
- [Patterns/Inheritance Patterns](Patterns/Inheritance-Patterns.md) — `_inherit` vs mixin patterns (this module uses mixins extensively)
- [Modules/Website](Modules/Website.md) — CMS/snippet architecture, `save_snippet` integration
- [Modules/Mail](Modules/Mail.md) — Email template rendering, `ir.qweb.field.html` usage
