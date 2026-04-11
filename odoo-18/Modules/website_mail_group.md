---
Module: website_mail_group
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_mail_group
---

## Overview

Adds a "Go to Website" action to mail groups, linking the community discussion platform to the public-facing website group page.

**Key Dependencies:** `mail_group`, `website`

**Python Files:** 1 model file

---

## Models

### mail_group.py — MailGroup

**Inheritance:** `mail.group`

| Method | Description |
|--------|-------------|
| `action_go_to_website()` | Returns URL action to `/groups/{slug}` |

---

## Critical Notes

- Single method override — the module primarily adds QWeb templates and controller for the group website page
- No new fields or security rules beyond the base `mail.group` model
- v17→v18: No structural changes
