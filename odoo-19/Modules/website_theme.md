---
title: website_theme (Theme Customization - website module)
draft: false
tags:
  - #odoo
  - #odoo19
  - #modules
  - #website
  - #theme
  - #customization
  - #view-editor
created: 2026-04-11
description: Theme customization, COW (Copy-on-Write) view mechanism, and visual editor functionality in the Odoo website module.
---

# website_theme

> **Note:** The standalone `website_theme` module **does not exist in Odoo 19**. In Odoo 19, all theme-related functionality is integrated directly into the core `website` module. This documentation covers the theme customization system as implemented in `odoo/addons/website/`.

---

## Overview

In Odoo 19, theme customization is a first-class feature of the `website` module. Key capabilities include:

1. **Copy-on-Write (COW)** for views -- editing a website does not impact others
2. **Visual / Theme Editor** -- live editing of snippets and layouts via drag-and-drop
3. **Theme Configurator** -- guided setup with industry-specific defaults
4. **Dynamic Snippets** -- configurable content blocks with per-theme customizations
5. **Custom CSS/JS per website** -- website-specific asset overrides

---

## Theme Fields on `website`

**File:** `odoo/addons/website/models/website.py`

```python
class Website(models.Model):
    _name = 'website'

    theme_id = fields.Many2one(
        'ir.module.module',
        string='Installed Theme',
        help='Current active theme module'
    )
    custom_code_head = fields.Html(
        'Custom <head> code',
        sanitize=False,
        groups='website.group_website_designer'
    )
    custom_code_footer = fields.Html(
        'Custom end of <body> code',
        sanitize=False,
        groups='website.group_website_designer'
    )
```

### Related Configuration Fields

```python
configurator_done = fields.Boolean(
    help='True if configurator has been completed or ignored'
)
has_social_default_image = fields.Boolean(
    compute='_compute_has_social_default_image',
    store=True
)
custom_blocked_third_party_domains = fields.Text(
    'User list of blocked 3rd-party domains',
    groups='website.group_website_designer',
    translate=False
)
blocked_third_party_domains = fields.Text(
    'List of blocked 3rd-party domains',
    compute='_compute_blocked_third_party_domains'
)
```

---

## Copy-on-Write (COW) Mechanism

### Core Concept

Odoo's website module implements a **Copy-on-Write** pattern for `ir.ui.view` records. When you customize a view for a specific website, Odoo creates a copy of that view rather than modifying the shared template. This ensures that:

- Editing Website A does **not** affect Website B (multi-website isolation)
- Theme updates can still apply to non-customized views
- The original template remains intact for reset operations

### How COW Works

```
User clicks "Edit" on website → System checks if view has website-specific copy
                                     ↓
                              YES: Use existing copy
                              NO:  Create COW copy of the view for this website
                                   (view gets website_id set, arch duplicated)

User modifies and saves → Changes written to the specific (COW'd) view
                          Original template untouched
```

### COW Trigger Points

COW is triggered automatically when:

1. **A website-exclusive layout is needed** -- any website-related write operation on a shared view
2. **Drag-and-drop layout changes** -- snippets moved/resized in the visual editor
3. **Snippet customization** -- changing snippet options, colors, content
4. **View inheritance changes** -- when a child view needs website-specific customization

### COW for View Arch

```python
# The write operation triggers COW if needed:
# 1. Find the original (non-website-specific) view
# 2. Copy it with website_id set to current website
# 3. Apply the customization to the copy
```

### COW for Inheriting Views

When the parent view is COW'd, all its children (inheriting views) are also triggered to COW to maintain the inheritance chain:

```python
# Trigger COW on inheriting views
# For each child view that is not already website-specific:
# → Create a COW copy with same website_id
# → Copy the arch content
```

### View Reset (Hard Reset)

COW views can be "reset" to restore the original template arch:

```python
records.reset_arch(mode='hard')
# This replaces the custom arch with the template's arch
# The COW copy remains but is restored to defaults
```

---

## Visual Editor / Theme Customization

### Routes

**File:** `odoo/addons/website/controllers/main.py`

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/website/theme_customize_data_get` | JSON-RPC | user | Get active customization keys |
| `/website/theme_customize_data` | JSON-RPC | user | Enable/disable views or assets |
| `/website/theme_customize_bundle_reload` | JSON-RPC | user | Reload asset bundles |

### `theme_customize_data_get`

```python
@http.route('/website/theme_customize_data_get', type='jsonrpc',
            auth='user', website=True, readonly=True)
def theme_customize_data_get(self, keys, is_view_data):
    """Get list of active customization keys (view/asset keys)."""
    records = self._get_customize_data(keys, is_view_data)
    return records.filtered('active').mapped('key')
```

### `theme_customize_data`

```python
@http.route('/website/theme_customize_data', type='jsonrpc',
            auth='user', website=True)
def theme_customize_data(self, is_view_data, enable=None, disable=None,
                         reset_view_arch=False):
    """Enable and/or disable views/assets.

    :param is_view_data: True = "ir.ui.view", False = "ir.asset"
    :param enable: list of keys to activate
    :param disable: list of keys to deactivate
    :param reset_view_arch: restore default template after disabling
    """
    if disable:
        records = self._get_customize_data(disable, is_view_data) \
                     .filtered('active')
        if reset_view_arch:
            records.reset_arch(mode='hard')
        records.write({'active': False})

    if enable:
        records = self._get_customize_data(enable, is_view_data)
        records.filtered(lambda x: not x.active).write({'active': True})
```

### `theme_customize_bundle_reload`

```python
@http.route('/website/theme_customize_bundle_reload', type='jsonrpc',
            auth='user', website=True, readonly=True)
def theme_customize_bundle_reload(self):
    """Reload asset bundles and return their unique URLs."""
    return {
        'web.assets_frontend': request.env['ir.qweb']._get_asset_link_urls(
            'web.assets_frontend',
            request.session.debug
        ),
    }
```

---

## Theme Configurator

### Configurator Snippets

**File:** `models/website.py`

```python
def get_theme_configurator_snippets(self, theme_name):
    """Prepare and return configurator snippets by fetching theme snippets
    and theme-specific snippet customizations.

    Returns dict of {snippet_key: {customization_options}}"""
```

This method merges:
- Theme-specific default snippet configs from the theme's manifest
- Customization options defined per theme

### Recommended Themes

```python
def configurator_recommended_themes(self, industry_id, palette, result_nbr_max=3):
    """Fetch theme recommendations for the configurator based on industry.
    Returns list of themes with SVG preview processed with the selected palette."""
    domain = Module.get_themes_domain()
    domain = Domain.AND([[('name', '!=', 'theme_default')], domain])
    client_themes = Module.search(domain).mapped('name')
    # RPC to Odoo server for theme recommendations...
```

---

## Dynamic Snippet Preconfiguration

**File:** `models/website.py`

```python
def _preconfigure_snippet(self, snippet, el, customizations):
    """Apply default configuration values to a snippet element before rendering.
    
    Ensures dynamic snippets have their required classes/attributes set.
    Handles: filter_xmlid, template_key, class modifications, data attributes, styles."""
```

### What `_preconfigure_snippet` Does

1. **Filter configuration**: `data-filter-id`, `data-number-of-records` from filter XMLID
2. **Template selection**: `data-template-key` for dynamic template selection
3. **Class modifications**: Add/remove CSS classes (e.g., `o_colored_level`)
4. **Data attributes**: Any `data-*` attributes from defaults or customizations
5. **Style injection**: Inline styles from customization
6. **Background options**: Color, image, shape backgrounds

### `_set_background_options`

Applies background customizations to snippet elements:
- Color: Sets `o_cc` class with color number
- Image: Adds `oe_img_bg o_bg_img_center` classes + style
- Shape: Applies shape-related styles

---

## Default Theme Module

**File:** `odoo/addons/theme_default/`

```python
{
    'name': 'Default Theme',
    'description': 'Default website theme',
    'category': 'Theme',
    'sequence': 1000,
    'version': '1.0',
    'depends': ['website'],
    'data': ['data/generate_primary_template.xml'],
    'images': [
        'static/description/cover.png',
        'static/description/theme_default_screenshot.jpg',
    ],
}
```

`theme_default` is the starter theme. It provides base templates and a `generate_primary_template.xml` that creates default page structures when a new website is initialized.

---

## Related Modules

| Module | Purpose |
|--------|---------|
| `website` | Core website + all theme customization features |
| `theme_default` | Default starter theme |
| `mass_mailing_themes` | Email template themes |
| `website_sale` | E-commerce with theme-compatible templates |
| `website_blog` | Blog with theme-compatible templates |
| `website_slides` | E-learning with theme-compatible templates |

---

## Key Concepts

- **COW (Copy-on-Write)**: The mechanism that isolates website customizations. Every view write can trigger a copy if the view is shared across websites.
- **Theme Configurator**: The setup wizard that recommends themes and configures default snippets based on industry
- **Dynamic Snippets**: Snippets that pull live data (e.g., latest products, blog posts) with configurable display options
- **Snippet Preconfiguration**: Process that applies default styles, classes, and data attributes to snippets before rendering
- **View Key**: A string identifier (e.g., `website.layout`, `website.s_homepage`) used to reference views for enable/disable operations in the theme editor
- **Hard Reset**: Restoring a customized view's arch to the original template, while keeping the website-specific copy
- **Asset Bundle Reload**: Mechanism to refresh CSS/JS bundles without restarting the server

---

## Differences from Older Odoo

In **Odoo 15 and earlier**, there was a separate `website_theme` module that handled:
- Theme installation and switching
- Theme preview
- COW management for theme assets

In **Odoo 16+**, this was consolidated into the core `website` module. The `theme_id` field on `website` now references `ir.module.module` directly, and all COW logic is part of the website model's write operations.

## Tags

#odoo #odoo19 #modules #website #theme #customization #view-editor #COW
