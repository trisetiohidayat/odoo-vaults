---
type: module
module: auth_password_policy_signup
tags: [odoo, odoo19, auth, security, password, signup]
created: 2026-04-06
---

# Auth Password Policy Signup

## Overview
| Property | Value |
|----------|-------|
| **Name** | Password Policy support for Signup |
| **Technical** | `auth_password_policy_signup` |
| **Category** | Hidden/Tools |
| **Depends** | `auth_password_policy`, `auth_signup` |
| **License** | LGPL-3 |

## Description
Applies password policy validation during the user signup process (via `auth_signup`). Ensures that passwords entered during self-registration meet the strength requirements defined in `auth_password_policy`.

## Technical Notes
- `models/ir_http.py` — Applies password policy rules during signup HTTP flows.
