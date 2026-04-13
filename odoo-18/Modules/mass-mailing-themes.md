---
Module: mass_mailing_themes
Version: Odoo 18
Type: Extension
Tags: #odoo18, #mass-mailing, #email, #themes
---

# Mass Mailing Themes Module (`mass_mailing_themes`)

## Overview

**Category:** Marketing/Email Marketing
**Depends:** `mass_mailing`
**Auto-install:** Yes
**License:** LGPL-3
**Version:** 1.2

The `mass_mailing_themes` module provides **11 pre-designed email template themes** for the Odoo email marketing editor. It extends `mass_mailing`'s `email_designer_themes` template with themed QWeb email layouts that users can select when creating a new mass mailing. Each theme is a complete, styled email layout with header, content sections, and footer.

**Important:** This module contains **zero Python model code**. All content is XML data (QWeb templates, ir.attachment records for images). The themes are loaded into the email designer through `inherit_id="mass_mailing.email_designer_themes"` in `views/mass_mailing_themes_templates.xml`.

## How Themes Work in Odoo's Email Designer

When a user opens the email designer in a `mailing.mailing` record, the editor loads theme snippets from `mass_mailing.email_designer_themes`. The `mass_mailing_themes` module extends this template with additional themed layouts using QWeb `t-call` directives.

Each theme entry in the editor:
- Has a `data-name` attribute (theme identifier)
- Has a `title` (human-readable label shown in the editor sidebar)
- Has a `data-img` pointing to a thumbnail preview
- Has a `data-images-info` JSON dict describing which images need to be fetched and in what format
- Calls the corresponding theme template via `<t t-call="mass_mailing_themes.theme_XXXXX_template"/>`

## Theme Inheritance Mechanism

```
mass_mailing / data / mail_mailing_data_form.xml
  └── defines mass_mailing.email_designer_themes template
      └── used by the email designer widget (mass_mailing static/src/js/mailing_m2o_mailing.js)

mass_mailing_themes / views / mass_mailing_themes_templates.xml
  └── <template id="email_designer_themes" inherit_id="mass_mailing.email_designer_themes">
          └── <xpath expr="." position="inside">
                  └── <div data-name="event" ...> <t t-call="..."/> </div>
                  └── <div data-name="newsletter" ...> <t t-call="..."/> </div>
                  └── ... (11 themes total)
```

The `inherit_id` mechanism means the themes automatically appear in the email designer without any Python code.

## Available Themes (11 Total)

### 1. Event Promo (`theme_event_template`)

**data-name:** `event`
**Background:** Dark navy `rgb(43, 59, 88)`
**Fonts:** Sans-serif system fonts
**Palette accent:** `#2b3b58` (dark blue headings)
**Use case:** Conference announcements, virtual events, Odoo Experience

**Structure:** Header with logo/social icons → dark hero section with event teaser text → media list (3 rows with images) → call-to-action banner → footer

**Key images:** Event-themed stock photos, logo placeholder

---

### 2. Newsletter (`theme_newsletter_template`)

**data-name:** `newsletter`
**Background:** White `rgb(255, 255, 255)`
**Fonts:** System defaults
**Palette accent:** `#CE0000` (deep red for headings and primary buttons)
**Use case:** Regular company newsletters, news roundups

**Structure:** Clean editorial layout with strong red typography. Features social media icon links in header, article-style sections.

---

### 3. Training (`theme_training_template`)

**data-name:** `training`
**Background:** Light blue `rgb(220, 234, 255)`
**Fonts:** Lucida Grande / Lucida Sans (overrides all fonts)
**Palette accent:** `rgb(20, 102, 184)` blue, `rgb(67, 128, 219)` primary button, `rgb(255, 152, 0)` secondary button
**Use case:** Training announcements, webinar invites, onboarding emails

---

### 4. Coupon Code (`theme_coupon_template`)

**data-name:** `coupon`
**Background:** Dark charcoal `rgb(36, 37, 48)`
**Fonts:** Georgia / Times serif
**Palette accent:** `#C69678` (warm tan/terracotta for borders and buttons)
**Use case:** VIP discount codes, promotional offers, loyalty rewards

**Structure:** Three-column header (FREE / LOGO / EXCLUSIVE) → coupon banner images → bold "$100 OFF" title section → promo code box with ticket icon → thank-you CTA card → social footer

---

### 5. Coffee Break (`theme_coffeebreak_template`)

**data-name:** `coffeebreak`
**Background:** Warm cream `rgb(238, 233, 226)`
**Fonts:** Georgia serif headings, system body
**Palette accent:** `#543427` (dark coffee brown), `#397B21` (green link color), `#D3C5B1` (light tan buttons)
**Use case:** Casual internal announcements, informal updates, team communications

---

### 6. Blogging (`theme_blogging_template`)

**data-name:** `blogging`
**Background:** White with monospace elements
**Fonts:** Courier New monospace for headings, system body
**Palette accent:** `#36a6d2` (tech cyan), `#adadad` (gray body text)
**Use case:** Tech blog digests, IT news, developer communications

**Structure:** Logo + social icons header → divider → text-image split (hero) → horizontal rule → media list (3 articles with thumbnail + title + excerpt + CTA buttons)

**Note:** This theme is thematically aligned with [Modules/website_blog](website_blog.md) content.

---

### 7. Magazine (`theme_magazine_template`)

**data-name:** `magazine`
**Background:** White with high contrast
**Fonts:** Tahoma/Verdana/Segoe sans-serif
**Palette accent:** `#e3aa25` (gold accent), `#212529` (near-black headings)
**Use case:** Editorial content, product launches, feature stories

**Structure:** Multi-column editorial layout with cover image, article teasers, and magazine-style hierarchy.

---

### 8. Big News (`theme_bignews_template`)

**data-name:** `bignews`
**Background:** Light gray `rgb(200-200-200 range)`
**Fonts:** Italic serif headings
**Palette accent:** `#BA0013` (bold red)
**Use case:** Major announcements, company relocations, urgent news

**Structure:** Simple centered header logo → bold italic headline → cover image → CTA section → social links

---

### 9. Promotion Program (`theme_promotion_template`)

**data-name:** `promotion`
**Background:** Black/white high contrast
**Fonts:** System bold defaults
**Palette accent:** `#000000` for buttons/headings
**Use case:** Product promotions, seasonal sales, clearance events

**Structure:** Header text/social bar → promotional content with borders → CTA buttons → unsubscribe footer

---

### 10. Roadshow Schedule (`theme_roadshow1_template`)

**data-name:** `roadshow1`
**Background:** White
**Fonts:** System defaults
**Palette accent:** `#35979c` (teal)
**Use case:** City-by-city event tour invitations, in-person roadshow registrations

**Structure:** Hero title → event details text → registration CTA → event map placeholder → footer. Contains `[date]`, `[time]`, `[city]` placeholders for manual editing.

---

### 11. Roadshow Follow-up (`theme_roadshow2_template`)

**data-name:** `roadshow2`
**Background:** White
**Fonts:** System defaults
**Palette accent:** `#35979c` (teal, same as roadshow1)
**Use case:** Post-event thank-you emails, photo sharing, feedback collection

**Structure:** Event thank-you headline → photo gallery with placeholder links → feedback CTA → footer

---

## Image Resources

### `data/ir_attachment_data.xml`

Defines public URL attachments for theme images not bundled as static files:

```xml
<record id="mass_mailing_themes.s_tech_default_image" model="ir.attachment">
    <field name="public" eval="True"/>
    <field name="name">s_tech_default_image.jpg</field>
    <field name="type">url</field>
    <field name="url">/mass_mailing_themes/static/src/img/theme_blogging/s_tech_default_image.jpg</field>
</record>

<record id="mass_mailing_themes.s_default_image_block_image" model="ir.attachment">
    <field name="public" eval="True"/>
    <field name="name">s_default_image_block_image.jpg</field>
    <field name="type">url</field>
    <field name="url">/mass_mailing_themes/static/src/img/theme_training/s_default_image_block_image.jpg</field>
</record>
```

These are used by the blogging and training themes for their default header images.

---

## L4: Theme Switching and Email Rendering

### How Theme Switching Works

1. User creates a new `mailing.mailing` record
2. User clicks "Select Theme" in the email designer sidebar
3. The editor widget (in `mass_mailing` JS) renders `mass_mailing.email_designer_themes`
4. QWeb inheritance merges in all `<div>` blocks from `mass_mailing_themes.email_designer_themes`
5. Each theme `<div>` has `data-name`, `title`, `data-img` — these are used to render theme thumbnails
6. When a user selects a theme, the editor replaces the current email body with the selected theme's `<t t-call>` content

### Rendering Pipeline

```
mailing_mailing.create()
  → body_arch is set to the selected theme's rendered QWeb template
  → theme template uses company_id, now (datetime), website_url_or_none
  → all <img> src values point to /mass_mailing_themes/static/src/img/...
  → mail_preview renders body_html using mail.mail_thread template
```

### Dynamic Values in Themes

Each theme template sets several `t-set` variables at the top:

```python
t-set="now" t-value="datetime.datetime.now()"       # Current datetime for copyright year
t-set="website_url_or_none" t-value="(company_id.website) or '#'"
t-set="future_date" t-value="(datetime.date.today() + datetime.timedelta(days=30))"
```

These are used inline: `<t t-out="now.strftime('%Y')"/>`, `<t t-att-href="website_url_or_none"/>`, etc.

### Styling Approach

Each theme embeds a `<style id="design-element">` block that overrides default email snippet styles. Email-compatible CSS (inline styles via `style="..."` attributes) is used throughout for maximum email client compatibility (Gmail, Outlook, Apple Mail). The style block provides theme-level defaults that snippet elements inherit.

### Email Client Compatibility Notes

- Themes use **inline styles** extensively (e.g., `style="background-color: rgb(43, 59, 88) !important;"`)
- Table-based layouts via Bootstrap grid classes (`container`, `row`, `col-lg-*`) for Outlook compatibility
- `!important` flags used to override user-applied snippet styles when a theme is first applied
- No external CSS files — all styles are embedded in the email HTML

---

## How `mailing.mailing` Uses Themes

The `mailing.mailing` model (from `mass_mailing` module) has:
- `body_arch` — raw XML/QWeb of the email body
- `theme_id` (if `mass_mailing_themes` installed, theme selection may be available as a UI option)
- The theme selection UI is part of the WYSIWYG editor in the mass mailing form

When the user selects a theme, the editor calls the corresponding QWeb template and stores the result in `body_arch`. The theme choice is **not stored separately** — only the rendered output is kept. Switching themes again replaces the entire body.

---

## Relationship to `mailing.theme` Model

The prompt mentioned a `mailing.theme` model. In Odoo 18, there is **no `mailing.theme` model** in this module or in `mass_mailing`. Theme management is entirely template-driven via QWeb inheritance, not via ORM records. The themes are defined as `ir.ui.view` template records (QWeb templates), not as `mailing.theme` model instances.

If there were a `mailing.theme` model in a future version or in enterprise, it would likely store:
- Theme name/identifier
- Thumbnail image
- Default template QWeb content
- Style preset configurations
