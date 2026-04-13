---
tags:
  - odoo
  - odoo19
  - modules
  - website
  - social
---

# Website Social

## Overview

| Property | Value |
|----------|-------|
| **Module** | `website_social` |
| **Edition** | **Not present in Odoo 19** — CE or EE |
| **Category** | Website / Social |
| **Summary** | Social media wall/feed integration on website pages |
| **Source** | Does not exist in Odoo 19 source tree |

## L1 — Module Status in Odoo 19

**This module does not exist in Odoo 19**, neither in Community Edition (`odoo/addons/`) nor in Enterprise Edition (`enterprise/`). A comprehensive search across both addons paths found no `website_social` directory or manifest.

This represents a **removal or fundamental redesign** from prior Odoo versions (where `website_social` existed as an EE-only module providing a social media wall/feed block for website pages).

### Historical Context (Pre-Odoo 19)

In Odoo 16 and earlier, `website_social` (EE-only) provided:
- A **social media wall** snippet: an embeddable block displaying live feeds from social networks (Facebook, Twitter/X, LinkedIn) on website pages
- A **social share bar**: per-page buttons to share content on social networks
- Integration with `social_media` (CE module) for social account configuration

In Odoo 18, this module was either **deprecated and removed** or **merged into another module**. The social sharing functionality was refactored into the core `website` module and the CE `social_media` module.

## L2 — Current Odoo 19 Social Media Architecture

In the absence of `website_social`, social media functionality in Odoo 19 is distributed across these modules:

### `social_media` (Community Edition)

The CE `social_media` module (`website_blog`, actually located in `addons/website/static/src/snippets/` or configured via `social_media` in website context) provides:

- Social media account configuration in **Settings > Website > Social Networks**
- Social media links in the website footer
- The `s_social_links` snippet: a "Social Links" block that can be added to any website page

```python
# Source: addons/website/models/website.py
# The website model exposes social media fields:
website_id.social_twitter = fields.Char('Twitter Account')
website_id.social_facebook = fields.Char('Facebook Account')
website_id.social_linkedin = fields.Char('LinkedIn Account')
website_id.social_youtube = fields.Char('YouTube Account')
website_id.social_instagram = fields.Char('Instagram Account')
website_id.social_tiktok = fields.Char('TikTok Account')  # Added in Odoo 19
```

### `mailing` Mass Mailing Social Blocks

The `mass_mailing` module provides social media icon blocks (`s_header_social`, `s_footer_social`) for email templates — see [Modules/mass_mailing_themes](mass_mailing_themes.md) for the themed versions.

### Social Share in Website Pages

The core `website` module in Odoo 19 includes the "Share" button on blog posts and event pages that generates social sharing links (Facebook, Twitter/X, LinkedIn, WhatsApp, Email) without needing a dedicated `website_social` module.

## L3 — Cross-Module Relationships

### Social Media Flow in Odoo 19

```
social_media (CE)
    └── website (CE)
            ├── website_page
            │     └── social_share (built-in)
            ├── website_blog
            │     └── social_share (built-in)
            └── website_event
                  └── social_share (built-in)
```

### Related Modules

| Module | Edition | Relationship |
|--------|---------|--------------|
| `website` | CE | Provides core social sharing links |
| `social_media` | CE | Configures social network account handles |
| `mass_mailing` | CE | Provides email social header/footer snippets |
| `website_blog` | CE | Blog post social sharing |
| `website_event` | CE | Event social sharing |
| `social` | EE | Full social media management/publishing suite |

## L4 — Version Change: Odoo 18 to 19

### What Changed

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| `website_social` module | EE-only, existed | **Removed** — not present |
| Social media wall/feed | Provided by `website_social` (EE) | **Removed** |
| Social share buttons | Via `website_social` | Built into core `website` |
| TikTok account field | Not present | **Added** to `website` model |
| Social links snippet | `s_share` or `s_social_links` | `s_share` (renamed/refined) |

### Impact Assessment

- **Users relying on the social media wall feature**: The embeddable social media feed block from `website_social` is no longer available. Workaround: use third-party social media embed widgets (e.g., Elfsight, Juicer) via the **Custom HTML** (`s_html`) snippet in Odoo Website Builder.
- **Social media account links**: The per-website social network handle configuration remains available via **Settings > Website > Social Networks** (managed by the core `website` model).
- **No data migration needed**: `website_social` had no persistent data models — it only provided UI snippets.

### Recommended Migration Steps

1. Audit all website pages using the old social wall snippet from `website_social`.
2. Replace with a custom HTML widget (e.g., Instagram embed, Twitter timeline embed) via the **Custom HTML** snippet.
3. Ensure social sharing links still work — verify **Settings > Website > Social Networks** is configured.
4. The social share buttons on blog posts and events are unaffected (built into core).

## Related

- [Modules/website](website.md) — Core website builder
- [Modules/social_media](social_media.md) — Social media account configuration
- [Modules/mass_mailing](mass_mailing.md) — Email campaign social snippets
- [Modules/mass_mailing_themes](mass_mailing_themes.md) — Themed email templates with social media headers
