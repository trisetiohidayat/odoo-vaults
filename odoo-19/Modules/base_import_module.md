# Base Import Module (`base_import_module`)

**Category:** Hidden/Tools
**Depends:** `web`
**Installable:** True
**Auto-install:** True
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Allows authorized users to import a custom Odoo module (ZIP file) containing `.xml` data files and static assets. Provides a UI for uploading and installing module packages that are not from the official Odoo Apps.

## Models

### `base.import.module` (TransientModel)
Wizard for importing module ZIP files.

**Methods:**
- `import_module()` — Handles ZIP upload and extraction; calls `ir.module.module._import_zipfile()`.
- `get_dependencies_to_install_names()` — Returns list of module dependencies that need to be installed.
- `action_module_open()` — Opens the installed module in the Apps list.

### `ir.module.module` (Extension)
Extends module management with import and ZIP upload capabilities.

**Key Methods:**
- `_import_module(module, path, force=False, with_demo=False)` — Imports a module from a filesystem path. Reads XML files, CSV data, demo data. Handles manifest, security files, views, and QWEB templates. Updates translations.
- `_import_zipfile(module_file, force=False, with_demo=False)` — Unzips a module archive, validates manifest, calls `_import_module()` for extraction, then creates/upgrades the module record.
- `_get_imported_module_names()` — Returns names of modules imported from ZIP (vs. loaded from addons path).
- `_get_missing_dependencies(zip_data)` — Parses ZIP manifest to find dependencies not currently installed.
- `_get_missing_dependencies_modules(zip_data)` — Returns `ir.module.module` records for missing dependencies.
- `button_immediate_install_app()` — Installs a module from import wizard.
- `_load_module_terms(modules, langs, overwrite)` — Loads translation terms from CSV/XML files into `ir.translation`.
- `_get_imported_module_translations_for_webclient(module, lang)` — Returns imported module translations in a format usable by the web client.
- `_extract_resource_attachment_translations(module, lang)` — Extracts translations from attachment filenames.
- `_get_latest_version()` — Fetches latest module version from Apps. Used for comparing against imported version.
- `_get_icon_image()` — Returns base64-encoded module icon image.
- `web_search_read(...)` / `web_read(...)` — JSON-RPC methods for module list view.
- `_get_modules_from_apps(fields, module_type, module_name, domain, limit, offset)` — Fetches module info from Odoo Apps store.
- `_call_apps(payload)` — Makes RPC call to Odoo Apps service.
- `_get_industry_categories_from_apps()` — Fetches industry category list from Apps.
- `more_info()` — Returns additional info about a module from Apps.
- `search_panel_select_range(field_name)` — Provides field values for search panel.
- `_get_modules_to_load_domain()` — Returns domain for modules to load on the frontend.

### `ir.http` (Extension)
Extends translations delivery to include imported module translations.

### `ir.ui.view` (Extension)
Validates custom views imported from ZIP.

- `_validate_custom_views(model)` — Performs safety checks on custom QWeb view XML.
