---
Module: website_crm_partner_assign
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_crm_partner_assign
---

## Overview

Geolocation-based partner assignment for CRM leads. Sales teams define partner grades and activations; the system matches leads to the closest/highest-rated partner based on geo coordinates. Portal partners can view and accept/decline assigned leads through the website interface.

**Key Dependencies:** `crm`, `website_partner`, `google_map` (optional)

**Python Files:** 5 model files

---

## Models

### res_partner_grade.py — ResPartnerGrade

**Inheritance:** `website.published.mixin`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `sequence` | Integer | Yes | Display order |
| `active` | Boolean | Yes | Default True |
| `name` | Char | Yes | Level name, translated |
| `partner_weight` | Integer | Yes | Default 1 — probability for lead assignment (0 = no assignment) |

**Methods:**

| Method | Description |
|--------|-------------|
| `_compute_website_url()` | Returns `/partners/grade/{slug}` |
| `_default_is_published()` | Returns `True` |

---

### res_partner_activation.py — ResPartnerActivation

**Inheritance:** Base (standalone `_name = 'res.partner.activation'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `sequence` | Integer | Yes | — |
| `name` | Char | Yes | Required |
| `active` | Boolean | Yes | Default True |

---

### crm_lead.py — CrmLead

**Inheritance:** `crm.lead`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `partner_latitude` | Float | Yes | Geo latitude (10,7 digits) |
| `partner_longitude` | Float | Yes | Geo longitude (10,7 digits) |
| `partner_assigned_id` | Many2one | Yes | Assigned partner, btree_not_null |
| `partner_declined_ids` | Many2many | Yes | Partners who declined |
| `date_partner_assign` | Date | Yes | Assignment date, computed on write |

**Key Methods:**

| Method | Description |
|--------|-------------|
| `_compute_date_partner_assign()` | Sets to today when `partner_assigned_id` changes |
| `_assert_portal_write_access()` | Portal users can only edit leads assigned to their commercial partner |
| `_get_partner_email_update()` | Portal users cannot update email if partner has a user |
| `write()` | Portal users check read access on all m2o field values |
| `_merge_get_fields()` | Adds geo and assignment fields to lead merge |
| `assign_salesman_of_assigned_partner()` | Copies assigned partner's salesman to lead |
| `action_assign_partner()` | Entry point: warns about leads without country, calls `assign_partner` |
| `assign_partner(partner_id)` | Main logic: searches geo partner, writes assignment |
| `assign_geo_localize()` | Geo-localizes lead from address (via `res.partner._geo_localize`) |
| `search_geo_partner()` | Multi-pass search: narrow area → medium area → wide area → country-wide → closest |
| `partner_interested()` | Partner accepts: posts message, converts to opportunity |
| `partner_desinterested()` | Partner declines: unsubscribes, optionally marks as spam, stores declined |
| `update_lead_portal(values)` | Portal partner updates expected_revenue, probability, priority, deadline, activities |
| `update_contact_details_from_portal(values)` | Portal partner updates partner contact info |
| `create_opp_portal(values)` | Creates new opportunity from portal (with grade check) |
| `_get_access_action()` | Redirects portal users to `/my/opportunity/{id}` instead of backend |
| `_prepare_customer_values()` | Copies geo coordinates to created partner |

**Geo Search Algorithm (`search_geo_partner`):**
1. Same country, lat ±2, lon ±1.5
2. Same country, lat ±4, lon ±3
3. Same country, lat ±8, lon ±8
4. Same country, any distance (partner_weight > 0)
5. Closest partner worldwide using PostGIS distance (`point(longitude, latitude)`)

Selection among candidates uses `random.choices(ids, weights=partner_weights)` — weighted random.

---

### res_partner.py — ResPartner

**Inheritance:** `res.partner`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `partner_weight` | Integer | Yes | Computed from grade, writable |
| `grade_id` | Many2one | Yes | Partner level |
| `grade_sequence` | Integer | No | Related grade sequence, stored |
| `activation` | Many2one | Yes | Activation state, indexed |
| `date_partnership` | Date | Yes | Partnership start date |
| `date_review` | Date | Yes | Last review date |
| `date_review_next` | Date | Yes | Next review date |
| `assigned_partner_id` | Many2one | Yes | Partner who implemented this partner |
| `implemented_partner_ids` | One2many | Yes | Partners this partner has implemented |
| `implemented_partner_count` | Integer | No | Published implemented partners count |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `default_get()` | `@api.model` | Sets lowest grade and activation for partners created from website |
| `_compute_implemented_partner_count()` | `@api.depends(...)` | Counts published implemented partners |
| `_compute_partner_weight()` | `@api.depends('grade_id.partner_weight')` | Copies grade weight |
| `_compute_opportunity_count()` | — | Extends parent to include assigned leads |
| `action_view_opportunity()` | — | Merges origin and assigned lead domains |

---

### website.py — Website

**Inheritance:** `website`

| Method | Description |
|--------|-------------|
| `get_suggested_controllers()` | Adds `('Resellers', '/partners', 'website_crm_partner_assign')` |

---

## Security / Data

**Access Control (`ir.model.access.csv`):**
- `res.partner.grade`: Salesman full access, others read-only
- `res.partner.activation`: User read-only, Manager full access
- `crm.lead` (portal): Portal read-only
- Custom access models for forward-to-partner and assignation

**IR Rules (`security/ir_rule.xml`):**
- `assigned_lead_portal_rule_1`: Portal can read/write leads where `partner_assigned_id` is child of user's commercial partner
- `res_partner_grade_rule_portal_public`: Published grades only for public/portal
- `ir_rule_crm_partner_report_assign_all/salesman`: Lead assignment report rules

**Data Files:**
- `data/res_partner_grade_data.xml`, `res_partner_grade_demo.xml`: Grade data
- `data/res_partner_activation_data.xml`: Activation levels
- `data/crm_lead_demo.xml`, `crm_tag_data.xml`: Demo leads
- `data/mail_template_data.xml`: Email notifications

---

## Critical Notes

- Geo search uses raw SQL `point(longitude, latitude)` for distance calculation — requires PostGIS
- Partners with `partner_weight=0` are never auto-assigned
- Declined partners are stored in `partner_declined_ids` and excluded from future searches for the same lead
- Portal access uses `_assert_portal_write_access()` — raises `AccessError` if lead not assigned to user's commercial partner tree
- `create_opp_portal()` requires the creating user to have a partner grade — prevents unauthorized portal opportunity creation
- `partner_interested()` also calls `convert_opportunity()` on the lead
- v17→v18: `partner_weight` moved to be computed from `grade_id.partner_weight` with writable override; geo search algorithm unchanged
