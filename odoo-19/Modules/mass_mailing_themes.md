---
tags:
  - odoo
  - odoo19
  - modules
  - mass_mailing
  - marketing
---

# Mass Mailing Themes

## Overview

| Property | Value |
|----------|-------|
| **Module** | `mass_mailing_themes` |
| **Edition** | Community Edition |
| **Category** | Marketing / Email Marketing |
| **Summary** | Pre-built email newsletter themes for the mass mailing designer |
| **Version** | `19.0.1.2.0` (manifest: `1.2`) |
| **Depends** | `mass_mailing` |
| **Auto-install** | `True` — installs automatically when `mass_mailing` is installed |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## L1 — What It Does

`mass_mailing_themes` is a **zero-model, pure-UI module** that adds a library of 11 professional email newsletter themes to Odoo's mass mailing email designer. It contributes nothing to the ORM layer (no Python models, no Python logic). Its entire function is to provide QWeb email template definitions and associated image assets.

When a user creates or edits a `mailing.mailing` record and opens the email designer, the theme selector panel shows these additional themes alongside the base themes from `mass_mailing`. Selecting a theme pre-fills the email body with a fully designed layout.

### Auto-install Mechanism

```python
'auto_install': True,
'depends': ['mass_mailing'],
```

Because `auto_install: True` is set, Odoo automatically installs `mass_mailing_themes` whenever the `mass_mailing` module is installed — no manual install needed. This is the standard Odoo auto-install pattern for UI enhancement modules.

## L2 — Field Types, Defaults, Constraints

Since this module has **no Python models**, there are no field definitions, no defaults, and no SQL constraints. All meaningful content is XML data and static assets.

### Data Files

#### `data/ir_attachment_data.xml`

Creates two `ir.attachment` records that store image URLs (type=`url`) as publicly accessible assets used by the Blogging and Training themes:

```xml
<!-- s_tech_default_image.jpg used inside theme_blogging as an SVG shape placeholder -->
<record id="mass_mailing_themes.s_tech_default_image" model="ir.attachment">
    <field name="public" eval="True"/>
    <field name="type">url</field>
    <field name="url">/mass_mailing_themes/static/src/img/theme_blogging/s_tech_default_image.jpg</field>
</record>

<!-- s_default_image_block_image.jpg used inside theme_training -->
<record id="mass_mailing_themes.s_default_image_block_image" model="ir.attachment">
    <field name="public" eval="True"/>
    <field name="url">/mass_mailing_themes/static/src/img/theme_training/s_default_image_block_image.jpg</field>
</record>
```

The `public="True"` flag allows these attachments to be served without authentication — required for email image rendering in email clients.

#### `views/mass_mailing_themes_templates.xml`

This is the core of the module (~1,500 lines). It contains:

1. **Theme registration** — extends `mass_mailing.email_designer_themes` to inject theme selector `<div>` entries.
2. **11 QWeb template definitions** — one `<template id="...">` per theme, each containing the full email body HTML/CSS as QWeb markup.

### Theme Inventory

All themes follow the same QWeb email snippet architecture. Each theme template is prefixed with `theme_` and called via `t-call="mass_mailing_themes.<id>"`.

| Template ID | Title in Designer | Color Scheme | Key Snippets Used |
|------------|-------------------|--------------|-------------------|
| `theme_event_template` | Event Promo | Dark blue (`#1b2421`) | `s_header_social`, `s_media_list`, `s_call_to_action`, `s_footer_social` |
| `theme_blogging_template` | Blogging | Cyan/monochrome (`#36a6d2`) | `s_header_social`, `s_text_image`, `s_media_list`, `s_hr`, `s_footer_social` |
| `theme_coupon_template` | Coupon Code | Dark (`#363730`) | `s_header_logo`, `s_cover`, `s_discount2` (promo code block), `s_call_to_action`, `s_footer_social` |
| `theme_magazine_template` | Magazine | White/red | `s_header_logo`, `s_text_image`, `s_mail_product_list`, `s_hr`, `s_footer_social` |
| `theme_bignews_template` | Big News | Dark (`#2b2b2b`) | `s_cover`, `s_title`, `s_text_block`, `s_footer_social` |
| `theme_promotion_template` | Promotion Program | Teal/white | `s_header_logo`, `s_text_image`, `s_media_list`, `s_call_to_action`, `s_footer_social` |
| `theme_coffeebreak_template` | Coffee break | Warm beige (`#eee9e2`) | `s_header_social`, `s_text_image`, `s_media_list`, `s_hr`, `s_footer_social` |
| `theme_newsletter_template` | Newsletter | White | `s_header_logo`, `s_text_block`, `s_text_image`, `s_hr`, `s_footer_social` |
| `theme_roadshow1_template` | Roadshow Schedule | White | `s_header_social`, `s_text_block`, `s_hr`, `s_footer_social` |
| `theme_roadshow2_template` | Roadshow Follow-up | White | `s_header_social`, `s_text_block`, `s_hr`, `s_footer_social` |
| `theme_training_template` | Training | Light blue (`#dceaff`) | `s_header_social`, `s_text_block`, `s_hr`, `s_footer_social` |

> **Note:** A `theme_vip/` image directory exists in `static/src/img/` (containing `vip_logo.png`) but is **not referenced** in any QWeb template — it is unused dead code.

### Static Asset Structure

```
mass_mailing_themes/static/src/img/
├── theme_blogging/    # Blogging theme images
│   ├── s_tech_default_image.jpg
│   ├── s_default_image_media_list_*.jpg
│   └── tech_logo.png
├── theme_event/      # Event theme images
│   ├── s_default_image_logo.png
│   └── s_default_image_media_list_*.jpg
├── theme_imgs/       # Thumbnail previews for theme selector panel
│   ├── bignews_thumb.png
│   ├── blogging_thumb.png
│   ├── coffee_break_thumb.png
│   ├── coupon_thumb.png
│   ├── event_thumb.png
│   ├── magazine_thumb.png
│   ├── newsletter_thumb.png
│   ├── promotion_thumb.png
│   ├── roadshow_followup_thumb.png
│   ├── roadshow_schedule_thumb.png
│   └── training_thumb.png
├── theme_newsletter/ # Newsletter theme images
├── theme_promotion/  # Promotion theme images
├── theme_training/   # Training theme images
│   └── s_default_image_block_image.jpg
├── theme_vip/        # (unused)
│   └── vip_logo.png
├── theme_coffeebreak/
├── theme_coupon/
└── theme_magazine/
```

### Common QWeb Patterns in Themes

Each theme template follows the same structure:

```xml
<template id="theme_X_template">
    <!-- CSS design variables injected into .o_mail_wrapper_td -->
    <style id="design-element">
        .o_layout .o_mail_wrapper .o_mail_wrapper_td {
            --h1-color: #36a6d2;
            --btn-primary-background-color: #36a6d2;
        }
    </style>

    <!-- Dynamic variables -->
    <t t-set="now" t-value="datetime.datetime.now()"/>
    <t t-set="website_url_or_none" t-value="(company_id.website) or '#'"/>

    <!-- Header section -->
    <section class="s_header_social ...">
        <!-- Logo + social icons -->
    </section>

    <!-- Body sections (varies per theme) -->
    <section class="s_text_block ..."/>
    <section class="s_media_list ..."/>
    <section class="s_call_to_action ..."/>

    <!-- Footer -->
    <section class="s_footer_social ...">
        <a role="button" href="/unsubscribe_from_list">Unsubscribe</a>
        © <t t-out="now.strftime('%Y')"/> All Rights Reserved
    </section>
</template>
```

Key dynamic values used across all themes:
- `company_id.website` — used for CTA button links
- `datetime.datetime.now()` — used in copyright year
- `/unsubscribe_from_list` — Odoo's built-in mailing list unsubscribe URL

## L3 — Cross-Model, Override Pattern, Workflow Trigger

### Cross-Module Dependencies

| Dependency | Purpose |
|-----------|---------|
| `mass_mailing` | Provides `mailing.mailing` model, email designer, and base `email_designer_themes` template to inherit |

**Dependency chain:**
```
mass_mailing_themes
└── mass_mailing
    ├── mass_mailing_event
    ├── mass_mailing_crm
    ├── mass_mailing_sale
    └── (other mass_mailing_* modules)
```

### Override Pattern

The module uses the **XML view/template inheritance** pattern (not Python `_inherit`). Specifically, it extends the base `mass_mailing.email_designer_themes` QWeb template via `inherit_id`:

```xml
<template id="email_designer_themes" inherit_id="mass_mailing.email_designer_themes">
    <xpath expr="." position="inside">
        <!-- Injects theme <div> blocks into the theme selector panel -->
        <div data-name="event" title="Event Promo" ...>
            <t t-call="mass_mailing_themes.theme_event_template"/>
        </div>
        <!-- ... more themes ... -->
    </xpath>
</template>
```

This is the **QWeb template extension** pattern — the base template's `<xpath expr=".">` is where all registered themes' `<div>` entries live. By inserting `<xpath expr="." position="inside">`, the module appends theme entries to the panel without modifying the base template.

### Workflow Trigger

There is no workflow. The module is entirely static. Its only "trigger" is the moment a user opens the email designer in a `mailing.mailing` form — at that point Odoo's web client renders the theme selector, which reads from `mass_mailing.email_designer_themes` (now augmented with this module's entries).

### Extension Points

| Extension Point | How to Extend |
|----------------|---------------|
| Add a new theme | Add a new `<div data-name="...">` entry in the `<xpath expr=".">` block, plus a new `<template id="theme_X_template">` |
| Replace a theme image | Override the `ir.attachment` record in `data/ir_attachment_data.xml` with a new URL |
| Add a new CSS color variable | Insert a new `--variable-name` rule in the `<style id="design-element">` block of the target theme template |

## L4 — Version Change: Odoo 18 to 19

### Changes Identified

#### New Themes Added in Odoo 19

The following themes were **not present** in Odoo 18 (or were significantly restructured):

| Theme | Status in Odoo 19 |
|-------|------------------|
| `theme_event_template` | **New** — Dark blue event promo layout |
| `theme_newsletter_template` | **New** — Standard white newsletter |
| `theme_coupon_template` | **New** — Dark promo/coupon code layout |
| `theme_coffeebreak_template` | **New** — Warm beige coffee break layout |
| `theme_roadshow1_template` | **New** — Roadshow schedule layout |
| `theme_roadshow2_template` | **New** — Roadshow follow-up layout |

#### CSS Variable Architecture

Odoo 18 themes in `mass_mailing` used inline `style` attributes for colors. Odoo 19 introduced CSS custom properties (variables) via the `<style id="design-element">` block — the `--h3-color`, `--btn-primary-background-color`, etc. — which are scoped to `.o_layout .o_mail_wrapper .o_mail_wrapper_td`. This allows the email designer to dynamically recolor themes without touching inline styles.

#### `t-set` + `t-value` vs `t-out`

Odoo 19 QWeb engine prefers `t-out` over `t-esc` for safe output. The themes consistently use:
- `t-set="now" t-value="datetime.datetime.now()"` — sets a computed variable
- `t-out="now.strftime('%Y')"` — renders it safely (replaces older `t-esc`)

#### Social Media Icons

Odoo 19 added **TikTok** icon to the social media header in `theme_event_template`:
```xml
<a title="TikTok" href="https://www.tiktok.com/@odoo">
    <span class="fa fa-tiktok text-white" .../>
</a>
```
This was not present in Odoo 18.

#### Template Inheritance API

The themes use `data-images-info='{"logo": {"format": "png"}, "all": {"module": "mass_mailing_themes"}}'` attribute on each theme `<div>`. This JSON metadata tells the email designer's image insertion tool where to look for default replacement images (`module: mass_mailing_themes`). This API was introduced in Odoo 16+ and is stable in Odoo 19.

### Migration Notes

- **No Python migration needed** — no models to migrate.
- **Static images** should be copied to the new location if the module is manually migrated.
- **QWeb template syntax** is fully compatible between Odoo 18 and 19 — no structural changes required in the XML.
- **New themes** in Odoo 19 simply need to be replicated as new `<template>` entries when backporting to Odoo 18.

## Related

- [Modules/mass_mailing](Modules/mass_mailing.md) — Base module that provides the email designer and `mailing.mailing` model
- [Modules/website_sale_mass_mailing](Modules/website_sale_mass_mailing.md) — Integrates mass mailing themes with e-commerce
- [Modules/mass_mailing_crm](Modules/mass_mailing_crm.md) — CRM-specific mailing features
- [Modules/mass_mailing_sms](Modules/mass_mailing_sms.md) — SMS alongside email campaigns
