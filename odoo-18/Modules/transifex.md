---
Module: transifex
Version: 18.0
Type: addon
Tags: #translation #transifex #i18n
---

# transifex

Transifex integration for Odoo translation management. Adds links from the in-app translation dialog to the Transifex online editor.

## Module Overview

**Category:** Hidden/Tools
**Depends:** `base`, `web`
**License:** LGPL-3

## What It Does

This module bridges Odoo's in-app code translation view with the Transifex web platform:

- Reads `.tx/config` files in addon directories to map modules to Transifex projects
- Stores all code translations (`_lt()` terms) in a `transifex.code.translation` table
- Adds a globe icon to each translatable term in the translation dialog linking directly to its Transifex edit page
- Runs a weekly cron job (`ir.cron`) to reload code translations from Transifex

## Models

### `transifex.translation` (AbstractModel)

Reads `.tx/config` files to build a `{module_name: tx_project_name}` map. The `_update_transifex_url()` method constructs Transifex edit URLs for each translation term using the project name, language ISO code, and the first 50 characters of the source term.

### `transifex.code.translation` (Model)

| Field | Type | Description |
|-------|------|-------------|
| `source` | Text | Original code string |
| `value` | Text | Translated value |
| `module` | Char | Module the term belongs to |
| `lang` | Selection | Language code |
| `transifex_url` | Char | Computed link to Transifex |

The `reload()` method clears the table and re-populates it from code translations (`CodeTranslations._get_code_translations`). The `_load_code_translations()` method uses table locking to safely handle concurrent installs.

## Extends

- `web` — translation dialog frontend (extended via `TranslationDialog` OWL template extension)
- `base` — config parameters, language data

## Data

| File | Purpose |
|------|---------|
| `data/transifex_data.xml` | `ir.config_parameter` with Transifex project URL + weekly `ir.cron` |
| `views/code_translation_views.xml` | List view for code translations (with Transifex column), search view, and server action/menu |
| `security/ir.model.access.csv` | ACLs for `transifex.code.translation` |

## Static Assets (Web)

| File | Description |
|------|-------------|
| `static/src/views/reload_code_translations_views.js` | OWL `ListController` subclass that calls `transifex.code.translation.reload()` on button click, then reloads the page |
| `static/src/views/fields/translation_dialog.xml` | Extends `web.TranslationDialog` OWL template to append a globe icon with `transifex_url` if set |

## Key Details

- The cron runs every 7 days by default
- Translations are only linked for non-English (`lang != 'en_US'`)
- Custom modules (those without `.tx/config` entries) are skipped from Transifex URL generation

---

*See also: [Core/HTTP Controller](Core/HTTP-Controller.md) (translation route), Odoo documentation on i18n*
