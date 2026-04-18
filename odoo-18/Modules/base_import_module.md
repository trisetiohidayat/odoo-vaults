---
Module: base_import_module
Version: 18.0
Type: addon
Tags: #base, #import, #module, #apps, #zip
---

# base_import_module — ZIP Module Import & Apps Store

## Module Overview

**Category:** Hidden
**Depends:** `base`
**License:** LGPL-3
**Installable:** True
**Auto-install:** True

Allows administrators to import custom ZIP-bundled modules directly from the Odoo web interface without filesystem access. Also integrates with apps.odoo.com for browsing and installing industry/data modules. Modules imported via ZIP are marked `imported=True` and can be uninstalled but not reinstalled via standard upgrade.

## Data Files

- `data/ir_module_module.xml` — Data records for module type selection (official/industries)
- `data/transfers.xml` — Module transfer data
- `security/ir.model.access.csv` — Access control for `base.import.module`
- `views/templates.xml` — Wizard form and list views

## Static Assets (web.assets_backend)

- `base_import_module/static/src/**/*` — Client-side import wizard JS

## Models

### `base_import_module` (`base_import_module.models.base_import_module`)

**Inheritance:** `base.import.module` (standalone, no parent)

Transient model for the ZIP import wizard. Provides a `module_file` binary field and state tracking.

**Fields:**

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `module_file` | Binary | No | .ZIP file containing the module bundle; `attachment=False` |
| `state` | Selection | Yes | `init`, `done`; tracks import progress |
| `import_message` | Text | Yes | Status or error message from import |
| `force` | Boolean | Yes | Force `init` mode even if already installed |
| `with_demo` | Boolean | Yes | Import demo data alongside module data |
| `modules_dependencies` | Text | Yes | Human-readable description of missing dependencies |

**Methods:**

**`import_module()`**
Calls `get_dependencies_to_install_names()`, creates ir.module records for dependencies, then decodes the ZIP, opens a temp directory, and calls `IrModule._import_zipfile()`. Redirects to `/odoo` on completion.

**`get_dependencies_to_install_names()`**
Returns a list of dependency module names that need to be installed before this ZIP can be imported.

**`action_module_open()`**
Returns an action to open the `ir.module.module` list filtered to modules from the import context.

---

### `ir.module.module` (`base_import_module.models.ir_module`)

**Inheritance:** `ir.module.module`

Extends the module management model with ZIP import logic and Apps Store API integration.

**Fields:**

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `imported` | Boolean | Yes | True if module was loaded via ZIP import (vs. filesystem) |
| `module_type` | Selection | Yes | `official` or `industries`; distinguishes Odoo Apps Store categories |

**Methods:**

**`_get_modules_to_load_domain()`** `@api.model`
Extends parent domain to add `('imported', '=', False)` — imported modules are excluded from the module loading system.

**`_get_latest_version(name)`** `@api.depends('name')`
For imported modules: sets `installed_version = latest_version` directly without reading from `__manifest__.py` on disk.

**`_get_icon_image()`** `@api.depends('icon')`
For imported modules: loads icon from `ir.attachment` by matching `url` field instead of filesystem path.

**`_import_module(module, path, force, with_demo)`**
Core import logic:
1. Parses `__manifest__.py` from extracted directory
2. Resolves dependencies against existing installed modules
3. Loads data/demo CSV/XML/SQL files
4. Creates `ir.attachment` for static/ files with `public=True`
5. Processes `ir.asset` entries
6. Loads `.po` translation files
7. Detects Studio-created modules via `_is_studio_custom()`
8. Updates `ir_module_module` record with latest version and `imported=True`

**`_import_zipfile(module_file, force, with_demo)`** `@api.model`
Entry point for ZIP import:
- Validates admin rights (`base.group_system`)
- Checks ZIP format (valid PKzip)
- Extracts modules to temp directory
- Calls `_import_module()` per discovered module
- Returns `(message, module_names)` tuple

**`module_uninstall()`**
Override: permanently deletes the module record for imported modules (not just unlinking). Imported modules cannot be reinstalled from the database.

**`web_search_read(...)`** `@api.model`
Override: routes industries-domain queries to Apps Store API (`APPS_URL/loempia/listdatamodules`).

**`more_info()`**
Returns Apps Store form action for the module (for industries modules).

**`web_read(specification)`** `@api.model`
Override: routes industries modules to Apps Store API for fetching module details.

**`_get_modules_from_apps(...)`** `@api.model`
Calls `POST {APPS_URL}/loempia/listdatamodules`. Maps existing installed module IDs by name. Transforms icon URLs to Odoo CDN.

**`_call_apps(payload)`** `@api.model` `@ormcache`
HTTP POST to `apps.odoo.com` with 5s timeout. Cached to avoid repeated calls.

**`_get_industry_categories_from_apps()`** `@api.model` `@ormcache`
HTTP GET from `apps.odoo.com/loempia/listindustrycategory`. Returns industry category hierarchy.

**`button_immediate_install_app()`**
Downloads module ZIP from `APPS_URL/loempia/download/data_app/{name}/{major_version}`. Creates `base.import.module` wizard record with the downloaded file. Requires admin access.

**`_get_missing_dependencies(zip_data)`** `@api.model`
Returns a human-readable description string and a list of unavailable module names.

**`_get_missing_dependencies_modules(zip_data)`** `@api.model`
Parses all manifests in the ZIP. Returns tuple of `(deps_to_install, not_found_modules)`.

**`search_panel_select_range(field_name)`** `@api.model`
Override: if `category_id` + industry domain, fetches categories from Apps Store API.

**Helper: `_is_studio_custom(path)`**
Scans XML records for `context` dicts containing a `studio` key. Detects Odoo Studio-created modules. Raises `UserError` if Studio is not installed.

---

### `ir.ui.view` (`base_import_module.models.ir_ui_view`)

**Inheritance:** `ir.ui.view`

**Methods:**

**`_validate_custom_views(model)`** `@api.model`
Override: also validates views from imported modules (`m.imported = True`). Groups by `inherit_id` to validate root views first. Returns combined validation result dict.

---

## Controllers

### `base_import_module`

**Routes:**

| Route | Auth | Methods | Description |
|-------|------|---------|-------------|
| `/base_import_module/upload` | admin | POST | Handles ZIP file upload from the import wizard |
| `/base_import_module/confirm_import` | admin | POST | Confirms import after dependency resolution |

---

## Security

**`security/ir.model.access.csv`:**
- `base.import.module`: `base.group_system` (admin only): read/write/create — no unlink

---

## What It Extends

- `ir.module.module` — ZIP import, Apps Store API, imported module lifecycle
- `ir.ui.view` — validation of imported module views
- `base_import_module` transient wizard — upload wizard UI

---

## Key Behavior

- Imported modules are excluded from `_get_modules_to_load_domain` — they exist only as database records, not filesystem entries.
- Imported modules can be uninstalled but NOT upgraded or reinstalled — `module_uninstall()` permanently deletes the record and all associated data.
- Static files are stored as `ir.attachment` records with `public=True` and `res_model='ir.ui.view'`, enabling Odoo's web server to serve them.
- Apps Store API endpoints: `POST /loempia/listdatamodules`, `GET /loempia/download/data_app/{name}/{version}`, `POST /loempia/listindustrycategory` — all proxied through `_call_apps()` with `@ormcache`.
- Studio detection (`_is_studio_custom`): any XML record with a `context` containing a `studio` key triggers this check.
- Knowledge article integration (v18 new): `_import_module` passes `welcome_article` / `knowledge.article` data from the manifest to the module's data loading.
- v17 to v18: `welcome_article` / `knowledge.article` handling added for module welcome articles.

---

## See Also

- [Modules/Base](Modules/base.md) — core Odoo models (ir.module.module, ir.ui.view)
- [Modules/Portal](Modules/portal.md) — portal user access
- Odoo Apps Store (`apps.odoo.com`) — official module marketplace
