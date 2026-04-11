---
Module: website_customer
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_customer
---

## Overview

Public customer showcase pages on the website. Partners with website_published=True are listed at `/customers` with tags, partner details, and contact information. Integrates with partner geolocation for map display.

**Key Dependencies:** `website`, `crm`, `website_partner` (indirect)

**Python Files:** 2 model files

---

## Models

### res_partner.py — WebsiteResPartner

**Inheritance:** `res.partner`, `website.seo.metadata`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `website_description` | Html | Yes | Full partner page description, strip_style, translated |
| `website_short_description` | Text | Yes | Short tagline, translated |

**Methods:**

| Method | Description |
|--------|-------------|
| `_compute_website_url()` | Returns `/partners/{slug}` |

---

### website.py — Website

**Inheritance:** `website`

| Method | Description |
|--------|-------------|
| `get_suggested_controllers()` | Adds `('References', '/customers', 'website_customer')` |

---

## Security / Data

**Security Files:**
- `security/ir_rule.xml`: `website_customer_res_partner_tag_public` — public/portal read only for published tags
- `security/ir.model.access.csv`: Standard partner and tag access grants

**Data Files:**
- `data/res_partner_demo.xml`: Demo partners for the customer showcase

---

## Critical Notes

- Partner website pages use `website_seo_metadata` mixin for SEO title/description
- `website_short_description` appears in partner cards on the listing page
- `website_description` is the full page content on `/partners/{slug}`
- Public access to partner data is controlled by `website_published` field
- v17→v18: Minimal changes
