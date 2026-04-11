---
Module: website_mass_mailing
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_mass_mailing
---

## Overview

Overrides company social media links to prefer website-specific social media settings. When a company has per-website social media configured, the mass mailing module uses those instead of the global company values.

**Key Dependencies:** `mass_mailing`, `website`

**Python Files:** 1 model file

---

## Models

### res_company.py — ResCompany

**Inheritance:** `res.company`

| Method | Description |
|--------|-------------|
| `_get_social_media_links()` | Extends parent to use current website's social links as fallback before company defaults |

**Behavior:**
- For each social network (Facebook, LinkedIn, Twitter, Instagram, TikTok): checks `website_id.social_*` first, falls back to company-level social link
- Priority: website setting > company default

---

## Critical Notes

- This module ensures mass mailing templates render with website-specific social media links
- The social media links are used in email templates for sharing/preview images
- No new fields on the company model — uses existing `social_*` fields
- v17→v18: No major changes
