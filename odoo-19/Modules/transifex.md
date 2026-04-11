# transifex

**Category:** Hidden/Tools
**Depends:** `base`, `web`
**Author:** Odoo S.A.
**License:** LGPL-3

Adds a "Edit on Transifex" link to Odoo's in-app translation view, speeding up translations of core modules by linking directly to the Transifex project.

## Models

### `transifex.translation` (AbstractModel)
Provides utilities for interacting with Transifex.

- `_get_transifex_projects()`: Caches and returns a dict mapping module names to Transifex project names by parsing `.tx/config` files in addons paths
- `_update_transifex_url(translations)`: For each translation record, computes and sets the Transifex URL based on module name, language, and source string

### `transifex.code.translation`
Stores translatable source strings from Python code (not database terms).

| Field | Type | Description |
|---|---|---|
| `source` | Text | Original source string |
| `value` | Text | Current translation value |
| `module` | Char | Module the term belongs to |
| `lang` | Selection | Target language |
| `transifex_url` | Char (computed) | Direct link to edit on Transifex |

**Key methods:**
- `_get_languages()`: Returns installed languages
- `_load_code_translations()`: Loads all Python code translations from installed modules into the table (runs with row-level locking to prevent duplicates)
- `_open_code_translations()`: Opens the code translations list view
- `reload()`: Clears and reloads all code translations

## Key Features
- Parses `.tx/config` files in all addon paths to map modules to Transifex projects
- Generates direct Transifex edit URLs for both database and Python code translations
- Code translation management: bulk load, view, and reload Python source terms
- Adds a Transifex link in the translation editor toolbar
