---
title: "__manifest__.py Schema — Complete Field Reference"
date: 2026-04-15
tags: [odoo, odoo19, manifest, schema, fields, __manifest__, reference]
type: concept
sources: 1
synced_from: odoo-minimal
sync_date: 2026-04-17
source_path: wiki/concepts/manifest-schema.md
---


# `__manifest__.py` Schema — Complete Field Reference

## Overview

Dokumentasi lengkap semua **manifest fields** yang digunakan di Odoo 19. Analisis dilakukan dengan `ast.literal_eval` terhadap 632 modules.

**Source**: `~/odoo/odoo19/odoo/addons/` — 632 manifest files

## Required Fields

| Field | Usage | Description |
|-------|-------|-------------|
| `name` | **632** | Human-readable module name |
| `author` | **632** | Author name |
| `license` | **632** | License identifier (LGPL-3, OEEL-1, GPL-3, etc.) |
| `depends` | 623 | List of dependency module names |

## Common Fields

| Field | Usage | Description |
|-------|-------|-------------|
| `category` | 627 | Module category (Hidden, Administration, etc.) |
| `description` | 513 | Long description (reST formatted) |
| `version` | 532 | Module version (must match Odoo version) |
| `data` | 537 | List of data file paths (XML/CSV) |
| `demo` | 245 | List of demo data file paths |
| `auto_install` | 383 | `True`/`False`/list — see [auto-install-mechanism](auto-install-mechanism.md) |
| `summary` | 313 | Short one-line summary |
| `assets` | 275 | Web asset bundles (SCSS, JS, XML) |
| `installable` | 253 | `True`/False — show in Apps list |
| `countries` | 147 | Country-specific modules (ISO codes) |
| `website` | 143 | Documentation/support URL |
| `sequence` | 115 | Sort order in Apps list |
| `icon` | 101 | Custom module icon path |
| `application` | 34 | `True` if this is a top-level app |

## Lifecycle Hooks

| Field | Usage | Description |
|-------|-------|-------------|
| `post_init_hook` | 87 | Python function called after install |
| `uninstall_hook` | 57 | Python function called before uninstall |
| `pre_init_hook` | 5 | Python function called before install |

```python
# post_init_hook example
def post_init_hook(cr, registry):
    # Runs after module install
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ir.config_parameter'].set_param('my_key', 'my_value')

# uninstall_hook example
def uninstall_hook(cr, registry):
    # Runs before module uninstall
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ir.config_parameter'].sudo().get_param('my_key')
```

## Special Fields

| Field | Usage | Description |
|-------|-------|-------------|
| `external_dependencies` | 5 | System packages (pip, apt) |
| `bootstrap` | 3 | Load translations before login (web, api_doc, ?) |
| `images` | 2 | Screenshots for Apps list |
| `maintainer` | 2 | Maintainer info |
| `new_page_templates` | 1 | Website page templates |
| `configurator_snippets` | 1 | Setup wizard snippets |
| `url` | 1 | Project URL |

## `auto_install` Detail

```python
# 3 forms:
'auto_install': True      # Install when ALL deps satisfied
'auto_install': False     # Never auto-install (manual)
'auto_install': ['account']  # Install when ANY dep satisfied

# Count by form (approximate):
# True: ~241 modules
# list: ~142 modules
# (383 total)
```

See [auto-install-mechanism](auto-install-mechanism.md) for full detail.

## `assets` Bundle System

```python
'assets': {
    'web.assets_backend': [
        'module/static/src/**/*.js',
        'module/static/src/**/*.scss',
        ('include', 'other.module/assets'),
        ('after', 'other/file.scss', 'module/file.scss'),
        ('before', 'other/file.js', 'module/file.js'),
        ('replace', 'other/file.js', 'module/file.js'),
        ('remove', 'some/file.scss'),
    ],
}
```

**Bundle types**:
- `web.assets_backend` — Backend JavaScript/CSS
- `web.assets_frontend` — Frontend JavaScript/CSS
- `web.assets_unit_tests` — Test assets
- `html_editor.assets_media_dialog` — Media dialog extension
- `api_doc.assets` — API doc specific assets

**Directives**:
- `include` — Load after base bundle
- `after` — Insert after specific asset
- `before` — Insert before specific asset
- `replace` — Replace an asset entirely
- `remove` — Remove an asset from bundle

## `external_dependencies`

```python
'external_dependencies': {
    'python': ['requests', 'Pillow'],
    'bin': ['wkhtmltopdf', 'gs'],
}
```

These are checked at install time — if the dependency is missing, install fails.

## `countries` Field

```python
'countries': ['id', 'my', 'th']  # Indonesia, Malaysia, Thailand
```

Only show this module in Apps for users in these countries. Used for localization modules.

## Version Format

```python
'version': '1.0'           # Simple version
'version': '19.0.1.0.0'    # Odoo 19 format
```

Version must match Odoo's major version for the module to load.

## `bootstrap` Field

Only 3 modules use `bootstrap=True`:

```python
# web/__manifest__.py
'bootstrap': True,  # Loads translations for login screen

# api_doc/__manifest__.py
'bootstrap': True,  # For doc client translations
```

`bootstrap=True` makes Odoo load the module's translations early enough to be available on the login screen.

## Relasi dengan Konsep Lain

- [auto-install-mechanism](auto-install-mechanism.md) — auto_install field detail
- [module-loading-sequence](module-loading-sequence.md) — when data files load
- [ir-module-module-deep-dive](ir-module-module-deep-dive.md) — ir.module.module model
- [odoo-minimal-installation](odoo-minimal-installation.md) — bootstrap field enables /doc before login
