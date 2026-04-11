---
Module: website_partner
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_partner
---

## Overview

Adds partner tags for website customer classification. Tags are used to categorize partners on the customer showcase pages (`/customers`). Tags can be published/unpublished and have Bootstrap color classes.

**Key Dependencies:** `website_customer`

**Python Files:** 1 model file

---

## Models

### res_partner.py — Models (2 inner classes)

**Class 1: `Partner` — res.partner extension**

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `website_tag_ids` | Many2many | Yes | `res.partner.tag` via `res_partner_res_partner_tag_rel` |

**Methods:**

| Method | Description |
|--------|-------------|
| `get_backend_menu_id()` | Returns `contacts.menu_contacts` |

**Class 2: `Tags` — res.partner.tag**

**Inheritance:** `website.published.mixin`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Required, translated |
| `partner_ids` | Many2many | Yes | Partners with this tag |
| `classname` | Selection | Yes | Bootstrap color: `'info'`, `'primary'`, `'success'`, `'warning'`, `'danger'`, default `'info'` |
| `active` | Boolean | Yes | Default True |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `get_selection_class()` | `@api.model` | Returns Bootstrap class choices |
| `_default_is_published()` | `@api.model` | Returns `True` — new tags are published by default |

---

## Security / Data

**Data Files:**
- `data/website_partner_data.xml`: Default partner tags
- `data/website_partner_demo.xml`: Demo partner tags

---

## Critical Notes

- `website.published.mixin` adds `is_published` field and standard website publish toggle
- Tags published by default via `_default_is_published()` so they appear immediately on the website
- `website_tag_ids` on partner enables filtering customers by tag/sector on `/customers` listing page
- No security rules beyond `website.published.mixin` defaults
- v17→v18: No major structural changes
