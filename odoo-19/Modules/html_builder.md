---
uuid: c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f
tags:
  - odoo
  - odoo19
  - modules
  - infrastructure
  - website
  - email
  - scss
  - qweb
  - html_editor
---

# HTML Builder (`html_builder`)

## Overview

| Attribute | Value |
|-----------|-------|
| **Module** | `html_builder` |
| **Category** | Uncategorized (Hidden Infrastructure) |
| **Depends** | `base`, `html_editor`, `mail` |
| **Version** | 0.1 |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Source** | `odoo/addons/html_builder/` |

## Description

The `html_builder` module is a **pure frontend infrastructure module** that extends the [Modules/html_editor](html_editor.md) with styles, templates, and rendering logic specifically needed in the **website builder** and **email template editor** contexts. It does not define any database models or business logic.

In essence, `html_builder` acts as a **SCSS/CSS and template asset layer** that enriches the base HTML editor with:

- Website-specific Bootstrap SCSS variables and helper mixins
- Dark mode support via conditional SCSS compilation
- A snippet viewer stylesheet for the "Add Element" dialog
- Email-compatible background styles for mass mailing
- Conditional asset loading based on editing context

This module is an automatic dependency of `website` and `mass_mailing`, but it can also be used by any module that needs HTML rendering in a website-like context.

## Architecture

The module is intentionally minimal — it has **no Python models**, no database tables, and no controllers. Its entire purpose is to define and register asset bundles in `__manifest__.py`. The assets are then automatically loaded when the HTML editor is opened in the appropriate context.

```
html_builder/
├── __init__.py
├── __manifest__.py          # Defines all asset bundles
├── static/
│   ├── src/
│   │   ├── scss/
│   │   │   ├── snippets/
│   │   │   │   └── snippet_viewer.scss    # "Add Element" dialog styles
│   │   │   ├── background.scss             # Website frontend background
│   │   │   └── *.variables.scss            # SCSS variable overrides
│   │   └── snippets/
│   │       └── snippet_viewer.scss        # Same as above (legacy path)
│   └── tests/
│       └── test_html_builder_assets_bundle.py  # Asset bundle tests
└── tests/
    └── test_html_builder_assets_bundle.py
```

## Asset Bundle System

Odoo's asset backend (`odoo.addons.base.models.assetsbundle`) processes XML `<asset>` declarations in manifests. The `html_builder` module uses this system extensively.

### Bundle Composition Directives

Odoo supports five composition directives that control how assets are merged into a bundle:

| Directive | Behavior |
|-----------|----------|
| `('include', 'other.bundle')` | Inlines all assets from another bundle |
| `('prepend', 'path')` | Adds asset at the beginning of the bundle |
| `('after', 'after_id')` | Adds asset after a specific asset |
| `('before', 'before_id')` | Adds asset before a specific asset |
| `('remove', 'path')` | Removes an asset from the bundle |
| `('replace', 'path', 'replacement')` | Replaces an asset with another |

The `html_builder` module uses `include`, `remove`, and `prepend` extensively to compose its bundles.

### Bundle Definitions

#### `web._assets_primary_variables`

```python
'web._assets_primary_variables': [
    'html_builder/static/src/**/*.variables.scss',
],
```

This registers HTML builder's SCSS variable files to be included in the global SCSS variable bundle. Variables here override Bootstrap defaults and define new variables (e.g., brand colors, spacing scales) that both the editor and the website frontend use.

#### `html_builder.assets`

The main editor context bundle — loaded when the HTML editor is active in any context:

```python
'html_builder.assets': [
    ('include', 'web._assets_helpers'),          # Bootstrap helpers
    'html_editor/static/src/scss/bootstrap_overridden.scss',
    'web/static/src/scss/pre_variables.scss',
    'web/static/lib/bootstrap/scss/_variables.scss',
    'web/static/lib/bootstrap/scss/_variables-dark.scss',
    'web/static/lib/bootstrap/scss/_maps.scss',
    'web/static/fonts/fonts.scss',
    'html_builder/static/src/**/*',              # All html_builder assets
    ('remove', 'html_builder/static/src/**/*.edit.*'),  # Remove edit-mode assets
    ('remove', 'html_builder/static/src/**/*.dark.scss'),  # Remove dark assets (loaded separately)
],
```

Key decisions:
- **Includes `_variables.scss` and `_variables-dark.scss`**: Provides Bootstrap 5 SCSS variables
- **Includes Bootstrap maps** (`_maps.scss`): Color maps and utility maps used by Bootstrap's utility classes
- **Removes `*.edit.*` files**: Edit-mode styles are loaded in a separate bundle
- **Removes `*.dark.scss` files**: Dark mode is handled by `web.assets_web_dark`

#### `html_builder.assets_inside_builder_iframe`

Loaded inside the editor's iframe when a user is actively editing a page:

```python
'html_builder.assets_inside_builder_iframe': [
    ('include', 'web._assets_helpers'),
    'web/static/src/scss/bootstrap_overridden.scss',
    'html_builder/static/src/**/*.edit.*',        # Edit-mode specific styles
    'html_editor/static/src/main/chatgpt/chatgpt_plugin.scss',
    'html_editor/static/src/main/link/link.scss',
],
```

These are styles that should only be present when content is being edited (e.g., drag handles, selection highlights, grid overlays).

#### `html_builder.iframe_add_dialog`

Loaded specifically in the "Add Element" (snippet) dialog:

```python
'html_builder.iframe_add_dialog': [
    ('include', 'web._assets_helpers'),
    ('include', 'web._assets_frontend_helpers'),
    'web/static/src/scss/pre_variables.scss',
    'web/static/lib/bootstrap/scss/_variables.scss',
    'web/static/lib/bootstrap/scss/_variables-dark.scss',
    'web/static/lib/bootstrap/scss/_maps.scss',
    'html_builder/static/src/snippets/snippet_viewer.scss',  # Snippet grid styles
],
```

The `snippet_viewer.scss` file styles the snippet thumbnail grid in the "Add Element" dialog, ensuring snippets preview correctly.

#### `web.assets_frontend`

Added to the main frontend page bundle:

```python
'web.assets_frontend': [
    'html_builder/static/src/scss/background.scss',
],
```

The `background.scss` file provides default background styling for website pages rendered outside the editor context.

#### `web.assets_web_dark`

Dark mode styles for the website:

```python
'web.assets_web_dark': [
    'html_builder/static/src/**/*.dark.scss',  # All dark mode SCSS files
],
```

Any SCSS file matching `*.dark.scss` in the html_builder static directory is automatically included in the dark mode bundle. This pattern allows any asset file to have a dark variant simply by naming it with the `.dark.scss` suffix.

## SCSS Variable System

### Bootstrap Variables Override

The html_builder includes Bootstrap's official `_variables.scss` and `_variables-dark.scss`, then provides its own variable overrides that take precedence. The Bootstrap variables system uses `!default` flags, meaning Odoo's overrides are applied after Bootstrap's defaults.

Common overrides include:
- **Brand colors**: Primary, secondary, success, danger, warning, info
- **Spacing scale**: `$spacer` multipliers
- **Border radius**: `$border-radius` and its variants
- **Grid breakpoints**: Responsive breakpoint widths
- **Typography**: Font families, sizes, and weights

### Dark Mode Variables

Odoo's dark mode works by:

1. When dark mode is active, the frontend loads `web.assets_web_dark`
2. This bundle includes `web/static/lib/bootstrap/scss/_variables-dark.scss`
3. And html_builder's `*.dark.scss` files
4. These files redefine Bootstrap variables with dark-appropriate values (e.g., darker backgrounds, lighter text)

## The `mail` Module Dependency

The `html_builder` manifest has `depends: ['base', 'html_editor', 'mail']`. The `mail` dependency exists because the HTML editor is used in two contexts:

| Context | Dependency on `mail` |
|--------|-------------------|
| **Website pages** | No mail dependency needed |
| **Email templates** | Requires `mail` for email rendering infrastructure |

By depending on `mail`, Odoo ensures that when `mass_mailing` is installed, `html_builder` is already available to provide email-compatible styles. Without this dependency, the mass mailing editor might not load html_builder assets in some installation orders.

## Why No Models?

`html_builder` deliberately has no Python models because:

1. **No database footprint**: Installation is instantaneous and requires no migrations
2. **Purely presentational**: All functionality is in CSS/SCSS and asset bundles
3. **Shared infrastructure**: It serves both website and email contexts without needing model-level customization
4. **Automatic activation**: Once in the manifest, assets are automatically loaded — no configuration needed

## Dark Mode Pattern

Odoo 19 introduced a standardized dark mode pattern. Any SCSS file can have a dark variant:

```
mystyle.scss       → Loaded in normal (light) mode
mystyle.dark.scss → Loaded in dark mode
```

The html_builder module uses this pattern extensively. All files matching `**/*.dark.scss` are automatically removed from the main bundle and placed into the dark mode bundle via:

```python
('remove', 'html_builder/static/src/**/*.dark.scss'),
```

And then included via `web.assets_web_dark`.

This allows developers to:
- Write light and dark styles side by side
- Use the same SCSS variable names (set differently in each context)
- Avoid media queries for dark mode entirely — just use Odoo's bundle switching

## Frontend Asset Loading Order

When a website page loads in the HTML editor, the asset loading order is:

1. **`web._assets_primary_variables`** — SCSS variables first (no actual CSS output, just variable definitions)
2. **`html_builder.assets`** — Main editor styles (includes Bootstrap, helpers, variables)
3. **`html_builder.assets_inside_builder_iframe`** — Edit-mode styles (selection UI, drag handles)
4. **`html_builder.iframe_add_dialog`** — Snippet dialog styles (loaded when dialog opens)
5. **`web.assets_frontend`** — Page background styles (loaded outside editor too)

And in dark mode, `web.assets_web_dark` is appended to the end, overriding the dark-sensitive variables.

## Asset Processing Pipeline

```
__manifest__.py
       │
       ↓ (declared in 'assets' key)
odoo.addons.base.models.assetsbundle
       │
       ├── Reads all file paths from the bundle definition
       ├── Applies composition directives (include, prepend, remove)
       ├── Concatenates SCSS files
       ├── Runs SassC compiler on SCSS → CSS
       ├── Minifies CSS (in production)
       ├── Computes bundle checksum (for cache busting)
       └── Outputs <link> tags with versioned URLs
```

The compiled CSS is served at a URL like `/web/assets/1234/html_builder.assets/web.assets_frontend.1.min.css`, where the number is the bundle checksum. This ensures users always get fresh CSS after changes.

## Related

- [Modules/html_editor](html_editor.md) — Core rich text editor (the primary consumer)
- [Modules/website](website.md) — Website builder (primary consumer of html_builder assets)
- [Modules/mass_mailing](mass_mailing.md) — Email campaign editor (uses mail-compatible styles)
- [Modules/web_unsplash](web_unsplash.md) — Unsplash image picker integration
- [Core/Fields](Core/Fields.md) — HTML field type documentation
