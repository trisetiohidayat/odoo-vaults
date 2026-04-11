---
Module: website_crm_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_crm_sms
---

## Overview

Bridges website visitors and CRM leads for SMS outreach. When a visitor has no partner but has leads with matching phone numbers, the SMS composer is made available and pre-filled with the lead as the target.

**Key Dependencies:** `website_crm`, `crm`, `sms`

**Python Files:** 1 model file

---

## Models

### website_visitor.py — WebsiteVisitor

**Inheritance:** `website.visitor`

| Method | Description |
|--------|-------------|
| `_check_for_sms_composer()` | Extends parent: additionally checks if visitor has leads with matching phone numbers |
| `_prepare_sms_composer_context()` | Extends parent: if no partner but has leads, uses the highest-confidence matching lead as SMS target |

**Logic:**
1. If visitor has no partner: look at `lead_ids` for leads where `mobile` or `phone` matches visitor's mobile
2. Sort matching leads by confidence level (most probable first)
3. If found: return SMS composer context with `default_res_model='crm.lead'`, `default_res_id=lead.id`, `number_field_name='mobile'/'phone'`

---

## Critical Notes

- This module enables SMS sending directly from the visitor profile even without partner linkage
- The `crm.lead` model has a `_sort_by_confidence_level` method used to rank leads
- Works together with `website_crm` which creates the `lead_ids` field on visitors
- No new fields — purely behavioral extensions
- v17→v18: No major changes
