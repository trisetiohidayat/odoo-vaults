# Test Website (`test_website`)

## Overview
- **Name:** Website Test
- **Category:** Hidden (Test Module)
- **Summary:** Website module install/uninstall/upgrade tests
- **Depends:** `web_unsplash`, `website`, `theme_default`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Overview

Test module for Odoo's website functionality. Contains models, controllers, and tour tests for website install/uninstall cycles, page management, snippets, forms, multilingual routing, and more. Not installable in production.

## Models

### `website` (Extension)
- `name_translated` — Translated website name field.

### `test.model` — SEO + Publishing + Searchable
Inherits: `website.seo.metadata`, `website.published.mixin`, `website.searchable.mixin`.
- `name` — Char, required, translatable
- `submodel_ids` — One2many to `test.submodel`
- `website_description` — Html field with translatable/sanitize settings
- `tag_id` — Many2one to `test.tag`
- `_search_get_detail()` — Search mapping for website search: searches `name`, `submodel_ids.name`, `submodel_ids.tag_id.name`.
- `open_website_url()` — Returns website client action for `/test_model/{id}`.

### `test.submodel`
- `name` — Char
- `test_model_id` — Many2one to `test.model`
- `tag_id` — Many2one to `test.tag`

### `test.tag`
- `name` — Char

### `test.model.multi.website` — Multi-website Publishing
Inherits `website.published.multi.mixin`. Has `website_id` with `ondelete='cascade'`.

### `test.model.exposed` — SEO + Publishing
Inherits `website.seo.metadata`, `website.published.mixin`.

## Controllers

### `website.TestController`
Route handlers for test pages (e.g., controller page rendering, form handling, etc.).

## Test Coverage

- `test_controller_args.py` — Controller argument passing
- `test_custom_snippet.py` — Custom snippet behavior
- `test_error.py` — Error page handling
- `test_form.py` — Website form submission
- `test_fuzzy.py` — Fuzzy search
- `test_image_upload_progress.py` — Image upload with progress
- `test_is_multilang.py` — Multi-language URL routing
- `test_media.py` — Media library tests
- `test_menu.py` — Website menu management
- `test_multi_company.py` — Multi-company website access
- `test_page.py` — Page rendering and management
- `test_page_manager.py` — Page manager operations
- `test_performance.py` — Performance benchmarks
- `test_qweb.py` — QWeb template rendering
- `test_redirect.py` — Redirect rules
- `test_reset_views.py` — View reset during module operations
- `test_restricted_editor.py` — Restricted editor mode
- `test_session.py` — Session management
- `test_settings.py` — Website settings
- `test_snippet_background_video.py` — Background video snippet
- `test_systray.py` — Systray icons on website
- `test_theme_ir_asset.py` — Theme asset loading
- `test_translation.py` — Website translations
- `test_views_during_module_operation.py` — View behavior during install/upgrade/uninstall
- `test_website_controller_page.py` — Controller page tests
- `test_website_field_sanitize.py` — Field sanitization
- `test_website_page_properties.py` — Page properties

## Demo Data
- `data/test_website_demo.xml`

## Related
- [Modules/website](odoo-18/Modules/website.md)
