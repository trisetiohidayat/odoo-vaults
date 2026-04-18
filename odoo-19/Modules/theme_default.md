---
uuid: 6f7a8b9c-0d1e-2f3a-4b5c-d6e7f8a9b0c1
title: "Default Theme"
status: published
category: Theme
tags:
  - odoo
  - odoo19
  - website
  - theme
  - scss
  - frontend
created: 2024-01-15
modified: 2024-11-20
---

# Default Theme

## Overview

**Module:** `theme_default`
**Category:** Theme
**Version:** 1.0
**Sequence:** 1000 (loads last among themes)
**Depends:** `website`
**Summary:** The foundational website theme providing SCSS design system, layout templates, and snippet configurations used by all Odoo websites without a custom theme
**License:** LGPL-3
**Author:** Odoo S.A.

`theme_default` is a pure styling module — it contains no Python models, no controllers, and no business logic. It is the base theme that Odoo websites fall back to when no child theme is installed. The module provides the complete visual design system including SCSS variables, mixins, typography, color palettes, component styles, and the default layout structure for all website pages. All other Odoo website themes (including custom child themes) inherit from and extend this module's SCSS and templates.

## Architecture

### Module Structure

```
theme_default/
├── __init__.py                      (empty - no Python code)
├── __manifest__.py
├── data/
│   └── generate_primary_template.xml (snippet template generation on install)
└── static/
    ├── description/
    │   ├── icon.png                 (module icon)
    │   ├── cover.png               (theme preview image)
    │   └── theme_default_screenshot.jpg
    └── src/                        (OWL/web assets if any)
```

The module is intentionally minimal. All visual assets and templates are handled through XML data files and SCSS files imported via the website asset pipeline.

### Theme Loading Order

In Odoo's theme system, modules with higher `sequence` values are loaded later. `theme_default` has `sequence: 1000`, ensuring it is processed after all other themes. This means:

1. All other themes (e.g., `theme_bootsnip`, custom themes) can override or extend the SCSS and templates provided by `theme_default`.
2. `theme_default` provides the fallback base styles — if no other theme defines a button style, `theme_default`'s button styles apply.
3. The sequence mechanism ensures that a child theme's `SCSS` file can redefine variables that `theme_default` set as defaults, and the SCSS compilation will use the child's values.

### Relationship to the Website Module

`website` is the only hard dependency. The website module provides the rendering engine, page management, and asset pipeline that consumes `theme_default`'s SCSS and XML templates. Specifically:

- The SCSS compiler (sassc / libsass via the web assets system) processes all SCSS files registered by active themes.
- The QWeb template engine renders `theme_default` XML templates for default page structures.
- The snippet system (`ir.ui.view` with `type='_snippet'`) is registered via the `data/generate_primary_template.xml` file.

## Data File

### `generate_primary_template.xml` — Primary Snippet Template Generation

**File:** `data/generate_primary_template.xml`

```xml
<odoo>
    <!-- Generate primary snippet templates that are not predefined -->
    <function model="ir.module.module" name="_generate_primary_snippet_templates">
        <value eval="[ref('base.module_theme_default')]"/>
    </function>
</odoo>
```

This XML file calls `_generate_primary_snippet_templates` on the `ir.module.module` model, passing the `theme_default` module reference. This function (defined in the `website` module) creates the default snippet templates in the database:

| Snippet Category | Description |
|---|---|
| Paragraph / Text | Rich text content blocks |
| Image + Text | Side-by-side image and text layouts |
| Cover | Full-width hero sections |
| Picture Grid | Masonry or grid image galleries |
| CTA Buttons | Call-to-action button groups |
| Feature List | Icon + text feature displays |
| Team Members | Person/avatar card grids |
| Testimonials | Customer quote carousels |

These snippets are the building blocks that website editors drag onto pages. The function generates them as `ir.ui.view` records with `type='snippet'` so they appear in the snippet palette.

## SCSS Design System

The `theme_default` SCSS defines the foundational design tokens that all child themes can override. While the module itself does not contain a large `static/src/scss/` directory (SCSS is compiled and bundled by the `web` module's asset pipeline), the design tokens are consumed by the website's SCSS compilation system.

### Design Token Architecture

The SCSS framework in Odoo websites follows a token-based design system:

```
SCSS Variables (theme_default)
    └── Color tokens (primary, secondary, success, danger, etc.)
    └── Typography tokens (font families, sizes, weights)
    └── Spacing tokens (margins, paddings in rem units)
    └── Border radius tokens
    └── Shadow tokens
         |
         v
Component SCSS
    └── Buttons, Forms, Cards, Navigation
         |
         v
Child Theme Override
    └── SCSS variables redefined
    └── New component styles
         |
         v
Compiled CSS output
```

### Key SCSS Variables (Consumed from `theme_default`)

| Token Category | Variables | Purpose |
|---|---|---|
| **Colors** | `$o-color-*` (o-bg-primary, o-text-primary, etc.) | Color scheme for components |
| **Typography** | `$o-theme-font-family-*`, `$o-font-size-*` | Font families and size scale |
| **Spacing** | `$o-spacing-*` | Consistent spacing scale |
| **Borders** | `$o-border-*`, `$o-border-radius-*` | Border and corner radius styles |
| **Shadows** | `$o-shadow-*` | Elevation system for cards and modals |

### Bootstrap Integration

Odoo's website SCSS is built on top of Bootstrap's SCSS system. The `theme_default` SCSS imports Bootstrap variables and mixins, then overrides them with Odoo-specific defaults. This means:

- Child themes can use standard Bootstrap variable names (e.g., `$primary`) which map to Odoo's color tokens.
- The Odoo-specific variable prefix `o-` distinguishes Odoo's extensions from vanilla Bootstrap.
- Bootstrap's component styles (buttons, forms, cards) are included but Odoo overrides many of them with custom styles.

### Component Styles

The default theme provides base styles for:

| Component | Description |
|---|---|
| **Buttons** | Primary, secondary, outline, link styles; size variants (sm, lg); icon button styles |
| **Forms** | Input fields, select dropdowns, checkboxes, radio buttons, validation states |
| **Cards** | Default card styling with optional header, footer, and image sections |
| **Tables** | Striped, bordered, hover, and responsive table styles |
| **Navigation** | Navbar, dropdown, breadcrumb, pagination styles |
| **Typography** | Headings (h1-h6), body text, lists, blockquotes, code blocks, inline text utilities |
| **Utilities** | Spacing utilities, color utilities, display utilities, flexbox utilities, text alignment |
| **Modals** | Modal dialog styling, backdrop, animation |
| **Alerts** | Success, info, warning, danger alert banners |
| **Badges** | Label badges, notification counts |
| **Dropzone** | File upload drag-and-drop area styling |

### Snippet Styles

Each snippet (as generated by `_generate_primary_snippet_templates`) has associated SCSS styles defined in the website module or in child themes. The `theme_default` provides base snippet container styles that ensure snippets render correctly before being customized by the website editor.

## Theme Inheritance Pattern

### How Child Themes Extend `theme_default`

A child website theme (e.g., `theme_mybrand`) extends `theme_default` by:

1. **Declaring `theme_default` as a dependency** in `__manifest__.py`:

```python
{
    'name': 'My Brand Theme',
    'depends': ['theme_default', 'website'],
    ...
}
```

2. **Overriding SCSS variables** at the top of the theme's main SCSS file:

```scss
// my_theme/static/src/scss/theme.scss
$o-color-priamry: #1a5f7a;  // Override primary color
$o-theme-font-family: 'Custom Font', sans-serif;
```

3. **Extending QWeb templates** via `inherit_id`:

```xml
<template id="my_custom_hero" inherit_id="theme_default.s_cover">
    <!-- Customizations -->
</template>
```

4. **Adding new snippets** that are not in `theme_default`:

```xml
<template id="s_my_feature" name="My Feature">
    <section class="s_my_feature">
        <!-- Custom snippet content -->
    </section>
</template>
```

### Template Inheritance Chain

```
theme_default
    └── Provides base snippet templates (s_text_block, s_image_text, etc.)
    └── Base layout templates (main_layout, footer)

child_theme
    └── inherits="theme_default" on snippet templates
    └── Overrides colors, fonts, and styles via SCSS
    └── Adds custom snippets

website_editor
    └── Drags snippets onto pages
    └── Customizes content inline
    └── Changes theme per website
```

### SCSS Compilation and Variable Override

Odoo's asset pipeline compiles all SCSS from active themes. The compilation order is:

1. Bootstrap base SCSS
2. `website` module SCSS (global website styles)
3. `theme_default` SCSS (base design tokens and component styles)
4. Active child theme SCSS (variable overrides and custom styles)
5. Website-specific custom SCSS (from the website editor)

Because SCSS variables use `!default`, a child theme's variable assignment takes precedence over `theme_default`'s default value:

```scss
// In theme_default
$o-color-primary: #875A7B !default;

// In child_theme (processed later)
$o-color-primary: #1E88E5;  // Overrides the default
```

## How to Extend the Default Theme

### Creating a Child Theme

A minimal child theme structure:

```
theme_mybrand/
├── __init__.py
├── __manifest__.py          (depends: ['theme_default', 'website'])
├── static/
│   └── src/
│       └── scss/
│           ├── primary_variables.scss  (color, font overrides)
│           └── theme.scss              (main SCSS entry point)
└── views/
    └── templates.xml              (template overrides and new snippets)
```

**`__manifest__.py`:**

```python
{
    'name': 'My Brand Theme',
    'category': 'Theme',
    'depends': ['theme_default', 'website'],
    'data': [
        'views/templates.xml',
    ],
}
```

**`static/src/scss/primary_variables.scss`:**

```scss
// Primary colors
$o-color-priamry: #FF5722;
$o-color-secondary: #607D8B;
$o-color-success: #4CAF50;
$o-color-info: #2196F3;
$o-color-warning: #FFC107;
$o-color-danger: #F44336;

// Typography
$o-theme-font-family-base: 'Roboto', sans-serif;
$o-theme-font-family-heading: 'Montserrat', sans-serif;
```

**`static/src/scss/theme.scss`:**

```scss
// This file is automatically loaded by Odoo's asset pipeline
// Import child theme customizations here
@import 'primary_variables';

// Custom component styles
.s_my_custom_section {
    background-color: $o-color-priamry;
    padding: 3rem 0;
    ...
}
```

### Overriding Snippet Templates

In `views/templates.xml`, extend base snippets:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Override the cover snippet -->
    <template id="s_cover_custom" inherit_id="theme_default.s_cover">
        <xpath expr="//div[hasclass('s_cover')]" position="attributes">
            <attribute name="style">background-color: #f5f5f5;</attribute>
        </xpath>
    </template>

    <!-- Add a new custom snippet -->
    <template id="s_my_hero" name="My Hero">
        <section class="s_my_hero o_colored_level">
            <div class="container">
                <h2>Custom Hero Section</h2>
                <p>...</p>
            </div>
        </section>
    </template>
</odoo>
```

### Adding Custom CSS Classes

Website editors can add custom CSS classes to any snippet via the "Customize" panel in edit mode. These classes can be defined in the child theme's SCSS:

```scss
// Custom class for highlighted sections
.o_highlighted {
    background-color: $o-color-priamry !important;
    color: white !important;

    h1, h2, h3, h4, h5, h6 {
        color: white !important;
    }
}
```

## Template Generation Mechanism

### `_generate_primary_snippet_templates`

This function (in the `website` module, called from `theme_default`'s `data/generate_primary_template.xml`) is invoked when `theme_default` is installed or upgraded. It ensures that default snippet templates exist in the database as `ir.ui.view` records.

The function creates snippets in a disabled state initially, so they appear in the snippet palette for editors but do not render on pages until explicitly placed.

| Snippet | Description |
|---|---|
| `s_text_block` | Basic rich text block |
| `s_image_text` | Image left + text right |
| `s_text_image` | Text left + image right |
| `s_cover` | Full-width hero banner |
| `s_picture` | Single centered image |
| `s_masonry` | Masonry image grid |
| `s_features` | Feature icon grid |
| `s_team_members` | Person cards grid |
| `s_testimonials` | Customer testimonial carousel |
| `s_cta` | Call-to-action banner |
| `s_banner` | Promo banner with buttons |
| `s_product_list` | Product listing grid |
| `s_references` | Logo/client reference grid |

## Images and Branding

### `static/description/`

| File | Purpose |
|---|---|
| `icon.png` | Module icon shown in the Apps > Themes list |
| `cover.png` | Theme preview/cover image in the theme selector UI |
| `theme_default_screenshot.jpg` | Full-page screenshot shown in the website theme preview |

These files are used by Odoo's theme selection UI (accessible from Website > Configuration > Themes). The cover image gives users a preview of the theme's visual style before activation.

## Relationship to Other Themes

### Official Odoo Themes

All official Odoo themes (`theme_bootsnip`, `theme_enark`, etc.) depend on `theme_default` and extend it with additional SCSS, templates, and assets. They do not duplicate the base design system but instead:

- Override SCSS variables to create a distinct visual identity
- Add new snippet templates specific to the theme's use case
- Extend base snippets with theme-specific styling
- Add new snippet options (background colors, layouts, etc.)

### Custom Themes

Custom themes created by partners or developers follow the same pattern: depend on `theme_default` for the base design system and extend it with custom SCSS and templates.

## Performance Notes

- `theme_default` has no Python code, so it imposes zero server-side overhead.
- SCSS is compiled by the web asset pipeline and cached as a compiled CSS file. The compilation only runs when a theme is installed, upgraded, or the SCSS changes.
- The template generation function runs only on module install/upgrade, not on every page load.
- Because `theme_default` is always loaded (it is the fallback), its SCSS should be kept lean. Expensive SCSS should be placed in child themes that are not always active.

## Migration Notes

Key considerations when migrating websites that use `theme_default`:

- The `sequence: 1000` loading order means `theme_default` styles are always processed last in the fallback chain. If a custom theme is uninstalled, the website falls back to `theme_default` automatically.
- Snippet templates generated by `_generate_primary_snippet_templates` are stored as database records. When upgrading from an older version, these records are reconciled to match the current version's snippet definitions.
- If a custom theme's SCSS overrides a variable that no longer exists in `theme_default` after an upgrade, SCSS compilation will produce an error. Always test theme upgrades in a staging environment.

## See Also

- [Modules/website](website.md) — The website module that hosts the theme system
- [Modules/theme_bootsnip](Modules/theme_bootsnip.md) — Example of an official child theme
- [Core/HTTP Controller](HTTP Controller.md) — How website controllers render pages
- [Patterns/Inheritance Patterns](Inheritance Patterns.md) — Odoo's inheritance system for templates and SCSS
