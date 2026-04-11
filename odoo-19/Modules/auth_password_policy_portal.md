---
type: module
module: auth_password_policy_portal
tags: [odoo, odoo19, auth, security, password, portal]
created: 2026-04-06
---

# Auth Password Policy Portal

## Overview
| Property | Value |
|----------|-------|
| **Name** | Password Policy support for Portal |
| **Technical** | `auth_password_policy_portal` |
| **Category** | Tools |
| **Depends** | `auth_password_policy`, `portal` |
| **License** | LGPL-3 |

## Description
Extends the password policy enforcement to portal users. Applies the same password strength and validation rules defined in `auth_password_policy` to portal (public website) user registration and password change flows.

## Technical Notes
- `models/ir_http.py` — Applies password policy rules at the HTTP layer for portal routes.
