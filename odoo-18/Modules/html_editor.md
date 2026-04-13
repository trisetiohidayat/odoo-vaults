---
Module: html_editor
Version: 18.0
Type: addon
Tags: #html, #editor, #wysiwyg
---

# html_editor — HTML Editor Component and Plugin System

## Module Overview

**Category:** Hidden
**Depends:** `base`, `bus`, `web`
**License:** LGPL-3
**Auto-install:** True

Provides an extensible, maintainable WYSIWYG HTML editor component with a plugin system. This is the core editor used by `web_editor` and other modules. The module defines the backend Odoo-side support for the editor: attachment management, video URL parsing, and server-side controller endpoints.

## Static Assets

The module ships extensive JavaScript and SCSS assets for the editor:
- `html_editor/static/src/**/*` — Editor core (loaded in backend)
- `html_editor/static/lib/cropperjs/**/*` — Image cropping library
- `html_editor/static/src/main/media/media_dialog/**/*` — Media dialog
- `html_editor/static/src/main/link/**/*` — Link popover
- `html_editor/static/src/utils/**/*` — Shared utilities

## Models

### `ir.attachment` (`ir.attachment`)

**Extended Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `local_url` | Char | Computed local URL for the attachment |
| `image_src` | Char | Computed URL for `<img>` src attribute (handles redirects, cache busters) |
| `image_width` | Integer | Computed image width from `datas` |
| `image_height` | Integer | Computed image height from `datas` |
| `original_id` | Many2one (ir.attachment) | Original unoptimized/unresized image |

**Methods:**

**`_compute_local_url()`**
If `url` is set, returns it; otherwise generates `/web/image/{id}?unique={checksum}`.

**`_compute_image_src()`**
Generates the proper `src` URL for HTML embedding. Handles:
- Local URLs starting with `/`
- Redirect-style URLs (`/web/image/{id}-redirect/{name}`)
- Cache-busted URLs (`?unique={checksum[:8]}`)

**`_compute_image_size()`**
Reads image from `datas` via PIL and extracts `width`/`height`.

**`_get_media_info()`**
Returns a dict of values needed by the media dialog: `id`, `name`, `description`, `mimetype`, `checksum`, `url`, `type`, `res_id`, `res_model`, `public`, `access_token`, `image_src`, `image_width`, `image_height`, `original_id`.

**`_can_bypass_rights_on_media_dialog(**attachment_data)`**
Override hook; returns `False` by default. Submodules (e.g., `web_unsplash`) override to allow certain flows.

### `base` (`base`)

**Extended Methods:**

**`_get_view_field_attributes()`**
Adds `sanitize` and `sanitize_tags` to the list of view field attributes (makes these attributes visible to the client-side editor).

### `BaseModel` — `web_update_field_translations` method

This method (in `models/ir_attachment.py`) on `base` enables field-by-field translation updates from the WYSIWYG editor. It strips translations and recomputes them using SHA-256 term hashes.

## Controllers

### `HTML_Editor` (`html_editor.controllers.main`)

**Supported Image Mimetypes:**
`gif`, `jpe`, `jpeg`, `jpg`, `png`, `svg+xml`, `webp`

**Routes:**

| Route | Auth | Methods | Description |
|-------|------|---------|-------------|
| `/html_editor/get_image_info` | user | POST | Returns attachment info from image URL |
| `/web_editor/attachment/add_data` | user | POST | Upload image/file as base64 data |
| `/web_editor/attachment/add_url` | user | POST | Add attachment by URL |
| `/web_editor/modify_image/<attachment>` | user | POST | Create modified copy (crop/resize/filters) |
| `/web_editor/save_library_media` | user | POST | Save media library images as attachments |
| `/web_editor/shape/<module>/<path:filename>` | public | GET | Color-customized SVG shapes |
| `/html_editor/shape/illustration/<id>` | public | GET | Dynamic SVG illustration |
| `/web_editor/video_url/data` | user | JSON | Parse video URL (YouTube, Vimeo, etc.) |
| `/web_editor/generate_text` | user | JSON | AI text generation via OLG IAP |
| `/html_editor/link_preview_external` | public | POST | Fetch OG metadata for external URLs |
| `/html_editor/link_preview_internal` | user | POST | Resolve internal Odoo record URLs |
| `/web_editor/get_ice_servers` | user | JSON | Return ICE server config for WebRTC |
| `/web_editor/bus_broadcast` | user | JSON | Collaboration: broadcast to editor channel |

**Key Methods:**

**`add_data(name, data, is_image, ...)`**
- Validates mimetype for images against `SUPPORTED_IMAGE_MIMETYPES`
- Processes image via `tools.image_process` (resize, quality, verify_resolution)
- Creates attachment; deduplicates via existing attachment matching
- Returns `_get_media_info()` dict

**`modify_image(attachment, ...)`**
- Creates a modified copy with `original_id` set to source
- Handles `alt_data` for WebP/JPEG alternate formats
- Uniquifies URL by inserting attachment ID before filename
- Generates access token for non-public attachments

**`shape(module, filename, **kwargs)`**
- Loads SVG from `static/shapes/` or `ir.attachment` for illustrations
- Applies color palette substitution via `_update_svg_colors()`
- Applies flip/flip-y/flip-xy via inline SVG styles
- Adjusts animation speed via `replace_animation_duration()`
- Returns SVG response with long cache headers

**`generate_text(prompt, conversation_history)`**
- Calls OLG IAP endpoint (`https://olg.api.odoo.com/api/olg/1/chat`)
- Passes `database_id` (UUID) for context
- Handles status responses: `success`, `error_prompt_too_long`, `limit_call_reached`

**`link_preview_external(preview_url)`**
- Uses `link_preview.get_link_preview_from_url()` from mail module
- Strips HTML from `og_description` via lxml

**`link_preview_internal(preview_url)`**
- Resolves internal Odoo action URLs to record metadata
- Supports paths like `/odoo/{action_path}/{id}`
- Returns `display_name` or `link_preview_name` from the record

## Tools (`html_editor/tools.py`)

### `get_video_source_data(video_url)`
Parses a URL and returns `None` or `(platform, video_id, match_obj)` for YouTube, Vimeo, Dailymotion, Instagram, Youku.

### `get_video_url_data(video_url, autoplay, loop, hide_controls, hide_fullscreen, hide_dm_logo, hide_dm_share)`
Returns embed URL, video ID, and params dict for the detected platform:
- YouTube: `rel=0`, `autoplay`, `mute`, `controls`, `loop+playlist`, `fs`
- Vimeo: `autoplay`, `muted`, `autopause=0`, `controls`, `loop`, `h` (hash), `dnt=1`
- Dailymotion: `autoplay`, `mute`, `controls`, `ui-logo`, `sharing-enable`
- Instagram: embed URL only
- Youku: embed URL only

## What It Extends

- `ir.attachment` — image metadata compute fields and media dialog support
- `base` — view field attributes for sanitize settings

## Key Behavior

- `html_editor` is the pure editor engine; `web_editor` wraps it with snippets and WYSIWYG-specific functionality.
- The `original_id` chain on attachments allows reverting to the original image after multiple edits.
- SVG color customization uses palette numbers 1-5 mapped to user-selected colors.
- Video embedding supports the five major platforms; embeds are sanitized and parameterized.

## See Also

- [Modules/Web Editor](modules/web-editor.md) (`web_editor`) — WYSIWYG editor with snippets
- [Modules/Web Unsplash](modules/web-unsplash.md) (`web_unsplash`) — Unsplash image integration
