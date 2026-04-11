# theme_default

Odoo 19 Website/Theme Module

## Overview

`theme_default` is the **default website theme** for Odoo. It provides the base SCSS/CSS styling, layout templates, and visual design system used as the foundation for all Odoo website pages.

## Module Details

- **Category**: Theme
- **Depends**: `website`
- **Sequence**: 1000 (loads last among themes)
- **Version**: 1.0
- **Author**: Odoo S.A.
- **License**: LGPL-3

## Functionality

- Provides base SCSS variables and mixins for Odoo's website design system.
- Includes common layout templates (header, footer, page structures).
- Supplies default snippet configurations and visual defaults.
- The theme that renders when no custom theme is selected.
- `generate_primary_template.xml` — Generates the initial website content/template when a new website is created.

## Technical Notes

- This is a pure theme/styling module — no Python models.
- All assets are frontend (SCSS/CSS/images).
- Serves as the base from which custom website themes inherit.
