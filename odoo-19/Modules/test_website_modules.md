# Website Modules Test (`test_website_modules`)

**Category:** Hidden
**Depends:** `theme_default`, `website`, `website_blog`, `website_event_sale`, `website_slides`, `website_livechat`, `website_crm_iap_reveal`, `website_sale_comparison`, `website_sale_wishlist`
**Installable:** True
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Integration test module for website business code when multiple website extension modules are installed simultaneously. Allows testing website business logic (blog, events, eLearning, livechat, CRM reveal, eCommerce wishlists and comparisons) in a full-stack scenario.

## Dependencies

| Module | Purpose |
|--------|---------|
| `website` | Core website |
| `theme_default` | Default theme |
| `website_blog` | Blog / news |
| `website_event_sale` | Event registration on website |
| `website_slides` | eLearning platform |
| `website_livechat` | Livechat on website |
| `website_crm_iap_reveal` | Visitor tracking and lead generation |
| `website_sale_comparison` | Product comparison feature |
| `website_sale_wishlist` | Customer wishlists |

## Models

This module has no Python models. It is a meta-package enabling full-stack website tests with all major website sub-modules installed.

## Test Assets

- `test_website_modules/static/tests/**/*` — Website integration test tours
