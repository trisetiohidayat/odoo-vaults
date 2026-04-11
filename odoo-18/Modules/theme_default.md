---
Module: theme_default
Version: 18.0
Type: addon
Tags: #theme #website
---

# theme_default

The default Odoo website theme.

## Module Overview

**Category:** Theme
**Depends:** `website`
**Sequence:** 1000 (loaded last among themes)
**License:** LGPL-3

## What It Does

Provides the default website theme with standard layout styles, snippet templates, and visual defaults. It triggers `_generate_primary_snippet_templates` on module installation to seed default snippet content.

## Extends

- `website` — website builder framework

## Data

| File | Purpose |
|------|---------|
| `data/generate_primary_template.xml` | Calls `_generate_primary_snippet_templates` on install |

## Static Assets

- `static/description/cover.png` — theme cover image
- `static/description/theme_default_screenshot.jpg` — theme screenshot

## Key Details

- No Python code; pure theme/data module
- Has `images` declared in manifest for theme store display

---

*See also: [[Modules/website]]*
