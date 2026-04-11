---
Module: website_twitter
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_twitter #twitter
---

## Overview

**Module:** `website_twitter`
**Depends:** `website`
**Location:** `~/odoo/odoo18/odoo/addons/website_twitter/`
**Purpose:** No Python models. Pure website template module for displaying Twitter feeds/blocks. Check `views/` and `static/` for frontend implementation.

## Models

None.

## Security / Data

No Python models, no `ir.model.access.csv`, no data XML files.

## Critical Notes

- This is a frontend-only module. All functionality is in QWeb templates and JavaScript.
- To understand behavior, inspect `views/templates.xml` and `static/` assets in the module directory.