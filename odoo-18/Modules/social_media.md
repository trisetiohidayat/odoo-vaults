---
Module: social_media
Version: 18.0
Type: addon
Tags: #social_media #website #company
---

# social_media

Social media integration. Adds social media account fields to the company form for display on websites.

## Module Overview

**Category:** Hidden
**Depends:** `base`
**Version:** 0.1
**License:** LGPL-3

## What It Does

Extends `res.company` to add seven social media URL fields. The fields are rendered in the website footer by the `website` module using the base view's `social_media` group. Primarily a data/front-end support module consumed by `website`.

## Extends

### `res.company` (Extended)

| Field | Type | Description |
|-------|------|-------------|
| `social_twitter` | Char | X (Twitter) account URL |
| `social_facebook` | Char | Facebook account URL |
| `social_github` | Char | GitHub account URL |
| `social_linkedin` | Char | LinkedIn account URL |
| `social_youtube` | Char | YouTube account URL |
| `social_instagram` | Char | Instagram account URL |
| `social_tiktok` | Char | TikTok account URL |

## Data

| File | Purpose |
|------|---------|
| `views/res_company_views.xml` | Extends `base.view_company_form` to add the social media group inside the existing `social_media` group |
| `demo/res_company_demo.xml` | Demo company with social media URLs |

## Key Details

- No Python code; pure model extension
- The 7 fields are stored as plain Char (URL strings)
- Designed to be extended by other modules or used directly by the website footer template

---

*See also: [Modules/website](website.md), [Modules/base](base.md)*
