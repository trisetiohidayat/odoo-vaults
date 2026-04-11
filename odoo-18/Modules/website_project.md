---
Module: website_project
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_project #project #website
---

## Overview

**Module:** `website_project`
**Depends:** `project`, `website`
**Location:** `~/odoo/odoo18/odoo/addons/website_project/`
**Purpose:** Exposes project tasks on the website as a portal contact form. Adds customer-facing fields to project tasks for use in website contact forms.

## Models

### `project.task` (website_project/models/project_task.py)

Inherits: `project.task`

| Field | Type | Description |
|---|---|---|
| `email_from` | Char | "Email From" — stores submitter email; used to prevent email loops on auto-reply |
| `partner_name` | Char | "Customer Name"; related to `partner_id.name`; `store=True, readonly=False` |
| `partner_phone` | Char | "Contact Number"; computed from `partner_id.mobile` or `partner_id.phone`; inverse writes back to partner; `store=True, copy=False` |
| `partner_company_name` | Char | "Company Name"; related to `partner_id.company_name`; `store=True, readonly=False` |

| Method | Decorator | Description |
|---|---|---|
| `_compute_partner_phone()` | `@api.depends('partner_id.phone', 'partner_id.mobile')` | Sets `partner_phone` to `mobile` or `phone` (prefers mobile) |
| `_inverse_partner_phone()` | inverse | Writes to `partner_id.mobile` if set; otherwise to `partner_id.phone` |

## Security / Data

No `ir.model.access.csv`. Data: `website_project_data.xml` — demo project/task data.

## Critical Notes

- v17→v18: No breaking changes.
- `email_from` field is specifically to track the submitter's email so Odoo's auto-reply doesn't loop back to the same address.
- `partner_phone` writeback is context-aware: prefers mobile if exists, falls back to phone.
- These fields enable the website contact form (`website_form` style) to pre-populate partner info on task creation.