---
Module: website_event_crm
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_crm
---

## Overview

Creates CRM leads from website event registrations. When visitors register for events through the website, this module captures the visitor and their language preference into the lead values for sales follow-up.

**Key Dependencies:** `event_sale`, `website_event`, `crm`

**Python Files:** 1 model file

---

## Models

### event_registration.py — EventRegistration

**Inheritance:** `event.registration`

| Method | Description |
|--------|-------------|
| `_get_lead_description_registration(line_suffix)` | Extends parent to include registration question/answer data in lead description |
| `_get_lead_description_fields()` | Adds `registration_answer_ids` to description fields |
| `_get_lead_values(rule)` | Enriches lead values with `visitor_ids` and `lang_id` from the registering visitor |

---

## Security / Data

No dedicated security XML files.

**Data Files:**
- `data/event_crm_demo.xml`: Demo event registrations linked to leads

---

## Critical Notes

- `_get_lead_values` only adds visitor context if `self.visitor_id` exists
- Registration answers (from `event.question` surveys) are formatted as bullet points in the lead description
- `visitor_ids` field on `crm.lead` creates the visitor-to-lead link used by `website_crm_livechat` for session tracking
- `lang_id` on the lead helps sales team respond in the visitor's language
- v17→v18: Lead description formatting changed to use `markupsafe.Markup` for safe HTML in descriptions
