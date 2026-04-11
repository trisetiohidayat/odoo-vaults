# Test Discuss Full (`test_discuss_full`)

**Category:** Productivity/Discuss
**Depends:** `calendar`, `crm`, `crm_livechat`, `hr_attendance`, `hr_fleet`, `hr_holidays`, `hr_homeworking`, `im_livechat`, `mail`, `mail_bot`, `project_todo`, `website_livechat`, `website_sale`, `website_slides`
**Installable:** True
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Integration test module for the Odoo Discuss (chat/messaging) app with all possible override modules installed. Tests discuss features across multiple apps including calendar integration, CRM livechat, HR, livechat from website, project tasks, and more.

## Dependencies

| Module | Purpose |
|--------|---------|
| `mail` | Core messaging |
| `im_livechat` | Livechat channel |
| `mail_bot` | Odoo Bot integration |
| `calendar` | Calendar integration with events |
| `crm_livechat` | CRM leads from livechat |
| `hr_attendance` | Employee attendance |
| `hr_fleet` | Company vehicles |
| `hr_holidays` | Leave management |
| `hr_homeworking` | Remote work configuration |
| `project_todo` | Task/project management |
| `website_livechat` | Website livechat widget |
| `website_sale` | eCommerce |
| `website_slides` | eLearning/slides |

## Models

This module has no Python models. It is a meta-package for full-stack Discuss integration testing.

## Test Assets

- `test_discuss_full/static/tests/tours/**/*` — Discuss integration test tours
