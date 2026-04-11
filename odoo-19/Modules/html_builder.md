# HTML Builder

## Overview

- **Module**: `html_builder`
- **Category**: Uncategorized (Hidden infrastructure)
- **Summary**: Generic HTML builder for website and mass mailing
- **Source**: `odoo/addons/html_builder/`
- **Depends**: `base`, `html_editor`, `mail`
- **Version**: 0.1

## Description

This addon contains a generic HTML builder application designed to be used by the website builder and mass mailing editor. It provides the rendering infrastructure (SCSS, templates) that allows the `html_editor` to function inside the website context and email templates.

## Architecture

This is an **asset and rendering infrastructure** module - it does not define models. It extends the asset bundles of `html_editor` with website-specific styles and rendering logic.

### Asset Bundles

| Bundle | Purpose |
|--------|---------|
| `html_builder.assets` | Main editor assets in builder context |
| `html_builder.assets_inside_builder_iframe` | Edit mode inside iframe |
| `html_builder.iframe_add_dialog` | Add element dialog styles |
| `web._assets_primary_variables` | SCSS variables |
| `web.assets_frontend` | Frontend background styles |
| `web.assets_web_dark` | Dark mode styles |

### Key Features

- Provides SCSS variables and mixins for the HTML editor in website context
- Adds `background.scss` for frontend
- Handles snippet viewer styles for the add-element dialog
- Dark mode support via `*.dark.scss` files
- Integrates with `mail` module for email layout compatibility

## Dependencies

- `html_editor` - The core editor component and plugin system
- `mail` - Email template integration
- `base` - Base Odoo functionality

## Asset Loading Strategy

Uses `('include', ...)`, `('prepend', ...)`, `('after', ...)`, and `('remove', ...)` directives to compose asset bundles:
- Includes Bootstrap SCSS variables and helpers
- Removes `.edit.*` files from read-only context
- Removes `.dark.scss` from main bundle (loaded separately)

## Related

- [[Modules/html_editor]] - Core rich text editor
- [[Modules/website]] - Website builder (primary consumer)
- [[Modules/mass_mailing]] - Email campaign editor

## Notes

- This module is technically a dependency of `website` and `mass_mailing`
- No database models - purely frontend asset infrastructure
- The `mail` dependency exists because the HTML builder is used in email template editing
