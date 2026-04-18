---
type: module
module: transifex
tags: [odoo, odoo19, transifex, i18n, translation, internationalization, tx]
created: 2026-04-14
uuid: e5c8f3a2-7d9b-4f1e-8a2c-6d3e5f7b1a4c
---

# Transifex Integration (`transifex`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Transifex Integration |
| **Technical** | `transifex` |
| **Category** | Hidden / Tools |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 19.0 |
| **Depends** | `base`, `web` |

The `transifex` module connects Odoo's in-app translation editor to the Transifex translation management platform. It provides a direct "Edit on Transifex" link for every translatable term in the Odoo interface, enabling professional translators and translation agencies to work directly in Transifex without needing access to the Odoo backend. The module parses Transifex configuration files in Odoo's addon directories, generates direct edit URLs for each translatable term, and manages a local cache of Python code translation strings in a dedicated database table.

This module serves two distinct audiences: Odoo developers who manage translations, and translation teams who use Transifex as their primary translation workspace. For developers, it provides visibility into which terms belong to which Transifex project. For translators, it eliminates the need to search for terms manually in the Transifex interface.

## Architecture

### Design Philosophy

The module operates at the intersection of two translation systems: Odoo's internal translation mechanism (which stores database terms in `ir.translation` and Python terms via `CodeTranslations`) and Transifex's external translation management platform. It does not replace either system; instead it creates a bridge by generating URL links that take a translator directly to the correct term in Transifex.

The module uses a two-model architecture:

1. **`transifex.translation`** (AbstractModel): A mixin-like utility model that provides shared methods for parsing Transifex configuration and generating URLs. This model is never instantiated as a database record.

2. **`transifex.code.translation`** (Model): A concrete database-backed model that stores translatable source strings extracted from Python code, enabling Transifex URL generation for terms that are not stored in `ir.translation`.

### Module Structure

```
transifex/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── models.py
│   ├── transifex_translation.py   # AbstractModel: URL generation
│   └── transifex_code_translation.py  # Concrete model: code terms
└── security/
    └── ir.model.access.csv
```

### Transifex Configuration Files

Transifex projects are configured using `.tx/config` files in the root of each addon directory. These files follow the Transifex CLI configuration format and map local module names to Transifex project slugs.

Example `.tx/config` format:

```ini
[main]
host = https://www.transifex.com
[odoo-19.sale]
file_filter = sale/i18n/<lang>.po
source_file = sale/i18n/en_US.po
type = PO
```

The module supports both the old-style format (`odoo-16.sale`) and the new colon-delimited format (`o:odoo:p:odoo-19:r:sale`).

## Models

### `transifex.translation` (AbstractModel)

**File:** `transifex/models/transifex_translation.py`

This abstract model provides utility methods for interacting with Transifex. It is never instantiated as a database record; instead, its methods are called by other models (primarily `transifex.code.translation`) or by the web controller.

#### `_get_transifex_projects()` — Configuration Parser

```python
@tools.ormcache()
def _get_transifex_projects(self):
    tx_config_file = ConfigParser()
    projects = {}
    for addon_path in odoo.addons.__path__:
        for tx_path in (
                opj(addon_path, '.tx', 'config'),
                opj(addon_path, pardir, '.tx', 'config'),
        ):
            if isfile(tx_path):
                tx_config_file.read(tx_path)
                for sec in tx_config_file.sections()[1:]:  # Skip [main]
                    if len(sec.split(":")) != 6:
                        # Old format: 'odoo-16.sale'
                        tx_project, tx_mod = sec.split(".")
                    else:
                        # New format: 'o:odoo:p:odoo-16:r:sale'
                        _, _, _, tx_project, _, tx_mod = sec.split(':')
                    projects[tx_mod] = tx_project
    return projects
```

**How it works:**

1. **File scanning**: The method iterates over all addon paths registered in `odoo.addons.__path__` (which includes both Odoo's built-in addons and custom addon directories). For each path, it looks for `.tx/config` in two locations:
   - Directly in the addon directory: `<addon_path>/.tx/config`
   - One level up (parent directory): `<addon_path>/../.tx/config`

2. **ConfigParser**: Uses Python's standard `configparser.ConfigParser` to read the INI-style configuration file.

3. **Section parsing**: Each section (excluding `[main]`) represents a module-to-project mapping. The method handles two formats:
   - **Old format**: `odoo-16.sale` — split by `.`, the first part is the project slug, the second is the module name.
   - **New format**: `o:odoo:p:odoo-19:r:sale` — split by `:`, the fourth segment is the project slug, the sixth is the module name.

4. **ORM cache**: The `@tools.ormcache()` decorator caches the result for the lifetime of the process. This is safe because `.tx/config` files are not expected to change during runtime.

5. **Result**: A dictionary mapping each module name to its Transifex project slug: `{'sale': 'odoo-16', 'purchase': 'odoo-16', 'crm': 'odoo-16'}`.

#### `_update_transifex_url()` — URL Generator

```python
def _update_transifex_url(self, translations):
    base_url = self.env['ir.config_parameter'].sudo().get_param(
        'transifex.project_url')
    if not base_url:
        return
    base_url = base_url.rstrip('/')

    res_langs = self.env['res.lang'].search([])
    lang_to_iso = {l.code: l.iso_code for l in res_langs}
    if not lang_to_iso:
        return

    projects = self._get_transifex_projects()
    if not projects:
        return

    for translation in translations:
        if not translation['source'] or translation['lang'] == 'en_US':
            continue

        lang_iso = lang_to_iso.get(translation['lang'])
        if not lang_iso:
            continue

        project = projects.get(translation['module'])
        if not project:
            continue

        source = werkzeug.urls.url_quote_plus(
            translation['source'][:50]
            .replace("\n", "")
            .replace("'", "\\'"))
        source = f"'{source}'" if "+" in source else source
        translation['transifex_url'] = (
            f"{base_url}/{project}/translate/"
            f"#{lang_iso}/{translation['module']}/42"
            f"?q=text%3A{source}"
        )
```

**How it works:**

1. **Base URL from config**: Reads the Transifex project URL from the system parameter `transifex.project_url` (e.g., `https://www.transifex.com/odoo`). This is configurable via Odoo's system parameters screen.

2. **Language mapping**: Creates a dictionary mapping Odoo's language codes (`fr_BE`, `es_AR`) to ISO language codes (`fr`, `es`) that Transifex uses in its URLs.

3. **Per-translation processing**: For each translation record (or dict), the method:
   - Skips English source terms (`lang == 'en_US'`) — these are the source language, not translatable.
   - Skips entries with no source string.
   - Skips entries whose module has no corresponding Transifex project.
   - Truncates the source string to 50 characters for URL length safety.

4. **URL construction**: The generated URL format is:
   ```
   https://www.transifex.com/{project}/translate/#{lang_iso}/{module}/42?q=text%3A{source}
   ```
   The `42` is a placeholder resource ID required by Transifex's URL format. The `q=text%3A` parameter performs a text search in Transifex to locate the exact term.

5. **In-place update**: The method modifies the `translation` dict or record in place by setting `translation['transifex_url']`. This avoids creating new objects.

### `transifex.code.translation` (Concrete Model)

**File:** `transifex/models/transifex_code_translation.py`

This model stores translatable source strings extracted from Python files. Unlike database terms (stored in `ir.translation`), Python code terms are not stored in the database by default — they are loaded from `.po` files at runtime. This model creates a persistent cache of those terms, enabling the Transifex URL feature to work for code terms as well as database terms.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `source` | Text | The original English source string from Python code |
| `value` | Text | The current translated value (from the database, not from `.po`) |
| `module` | Char | The Odoo module the term belongs to |
| `lang` | Selection | Target language code |
| `transifex_url` | Char (computed) | Direct link to edit this term in Transifex |

#### `_load_code_translations()` — Bulk Loading

```python
def _load_code_translations(self, module_names=None, langs=None):
    try:
        # Row-level lock prevents concurrent inserts for the same module/lang
        self.env.cr.execute(
            f'LOCK TABLE {self._table} IN EXCLUSIVE MODE NOWAIT')

        if module_names is None:
            module_names = self.env['ir.module.module'].search(
                [('state', '=', 'installed')]).mapped('name')
        if langs is None:
            langs = [lang for lang, _ in self._get_languages()
                     if lang != 'en_US']

        # Get already-loaded translations to avoid duplicates
        self.env.cr.execute(
            f'SELECT DISTINCT module, lang FROM {self._table}')
        loaded_code_translations = set(self.env.cr.fetchall())

        # Build insert values for missing (module, lang) combinations
        create_value_list = [
            {
                'source': src,
                'value': value,
                'module': module_name,
                'lang': lang,
            }
            for module_name in module_names
            for lang in langs
            if (module_name, lang) not in loaded_code_translations
            for src, value in
                CodeTranslations._get_code_translations(
                    module_name, lang, lambda x: True).items()
        ]

        self.sudo().create(create_value_list)
    except psycopg2.errors.LockNotAvailable:
        return False

    return True
```

**Key design decisions:**

1. **Row-level locking**: Uses `LOCK TABLE ... IN EXCLUSIVE MODE NOWAIT` to prevent concurrent inserts for the same `(module, lang)` combination. If another process is already loading, `LockNotAvailable` is caught and the method returns `False` gracefully.

2. **Incremental loading**: Only loads translations for `(module, lang)` combinations not already in the table. This makes the method safe to call multiple times — subsequent calls only add newly installed modules or languages.

3. **CodeTranslations extraction**: Uses `CodeTranslations._get_code_translations()` (from `odoo.tools.translate`) to extract translatable terms from Python `.py` files. This reads the module's `.po` file for the given language.

4. **`sudo()` for creation**: The insert is performed with elevated privileges because the code translation loading is a system-level operation not tied to a specific user's access rights.

5. **Excludes en_US**: The default language (`en_US`) is excluded because it is the source language, not a translation target.

#### `_open_code_translations()` — UI Entry Point

```python
def _open_code_translations(self):
    self._load_code_translations()
    return {
        'name': 'Code Translations',
        'type': 'ir.actions.act_window',
        'res_model': 'transifex.code.translation',
        'view_mode': 'list',
    }
```

This method loads all code translations and then opens the list view of the `transifex.code.translation` model. It is typically called from a menu item or a button in the web interface. The list view displays all code terms alongside their Transifex edit URLs, enabling a translator to click directly through to Transifex for each term.

#### `reload()` — Cache Refresh

```python
@api.model
def reload(self):
    self.env.cr.execute(f'DELETE FROM {self._table}')
    return self._load_code_translations()
```

This method clears all code translation records and reloads them from scratch. It is useful after installing a new module or updating `.po` files, when the in-database cache needs to be refreshed.

## Transifex URL Generation Flow

```
Translator opens Code Translations list view
    ↓
transifex.code.translation records displayed
    ↓
transifex.code.translation._compute_transifex_url()
    ↓
transifex.translation._update_transifex_url() called
    ↓
1. Read transifex.project_url from ir.config_parameter
2. Parse .tx/config files → {module: project_slug} dict
3. Map lang code → ISO code (fr_BE → fr)
4. Build URL:
   https://www.transifex.com/{project}/translate/#{iso}/{module}/42?q=text%3A{source}
    ↓
URL displayed in list view; clicking opens Transifex editor at the exact term
```

## Database vs. Code Translations

Odoo stores translations in two fundamentally different ways:

### Database Translations (`ir.translation`)

Terms defined in XML files (field labels, view strings, menu items) are stored in `ir.translation` as database records. These are immediately editable through Odoo's web-based translation editor (**Settings > Translations > Application Terms**). For these terms, the Transifex URL is generated directly in the translation editor without needing the `transifex.code.translation` model.

### Code Translations (Python terms)

Terms hard-coded in Python files (e.g., `_('Submit')` or `_t('Cancel')`) are loaded from `.po` files at runtime and are not stored in the database by default. The `transifex.code.translation` model creates a persistent in-database cache of these terms, enabling Transifex URL generation for code terms.

```
Python: order.state = 'sale'
           ↓
      _('Sale Order')  ← translatable term
           ↓
   CodeTranslations._get_code_translations()
           ↓
   .po file: msgid "Sale Order", msgstr "Bon de Commande"
           ↓
   transifex.code.translation record stored in database
           ↓
   Transifex URL generated pointing to "Sale Order" term
```

## Configuration

### Setting the Transifex Project URL

1. Navigate to **Settings > Technical > System Parameters**.
2. Create or edit the parameter with key `transifex.project_url`.
3. Set the value to your Transifex organization URL, e.g., `https://www.transifex.com/odoo`.

### Using the Translation Editor

1. **For database terms**: Go to **Settings > Translations > Application Terms**. Each row includes a **Transifex** link if the `transifex.project_url` is configured.

2. **For code terms**: Go to **Settings > Translations > Code Translations** (or use the menu item created by the module). The list view shows all Python terms with their Transifex edit links.

## Business Impact

### Faster Translation Workflow

Professional translation agencies typically manage Odoo translations through Transifex, where they can use translation memory, glossaries, and quality checks. Without this module, translators must search for each term manually in Transifex. With it, a single click takes them directly to the exact term, reducing lookup time significantly.

### Translation Quality

The 50-character truncation in URL generation ensures that partial string matches are handled correctly. Common Odoo patterns (e.g., `"Cancelled: %s"`) are searchable by their distinctive prefix, helping translators find contextually relevant existing translations.

### Module-Specific Translation Tracking

By mapping modules to Transifex projects, the module enables granular tracking of translation progress per module. This is useful for Odoo Partners who maintain custom modules with their own Transifex projects.

## Related

- [Core/API](API.md) — API decorators: `@api.model`, `@api.depends`
- [Patterns/Inheritance Patterns](Inheritance Patterns.md) — How Odoo extends models
- [Modules/web](Modules/web.md) — Web controller layer
- [Modules/base](Modules/base.md) — Base module: translations, languages
