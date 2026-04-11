---
Module: website_crm_iap_reveal
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_crm_iap_reveal
---

## Overview

Automatic lead generation from website visitors using IAP (Internal Analytics Platform). Tracks anonymous page views and creates `crm.reveal.view` records. A cron job batches these views and calls the IAP reveal service to enrich visitor data with company/contact information, creating leads automatically.

**Key Dependencies:** `crm`, `website`

**Python Files:** 4 model files

---

## Models

### crm_reveal_rule.py — CRMRevealRule

**Inheritance:** Base (standalone `_name = 'crm.reveal.rule'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Required |
| `active` | Boolean | Yes | Default True |
| `country_ids` | Many2many | Yes | Filter by country (GeoIP) |
| `website_id` | Many2one | Yes | Restrict to specific website |
| `state_ids` | Many2many | Yes | Filter by state |
| `regex_url` | Char | Yes | URL pattern to match (regex) |
| `sequence` | Integer | Yes | Processing order for same URL |
| `industry_tag_ids` | Many2many | Yes | IAP industry criteria |
| `filter_on_size` | Boolean | Yes | Default True — filter by company size |
| `company_size_min` | Integer | Yes | Default 0 |
| `company_size_max` | Integer | Yes | Default 1000 |
| `contact_filter_type` | Selection | Yes | `'role'` or `'seniority'`, required, default `'role'` |
| `preferred_role_id` | Many2one | Yes | IAP role criteria |
| `other_role_ids` | Many2many | Yes | Additional roles |
| `seniority_id` | Many2one | Yes | IAP seniority criteria |
| `extra_contacts` | Integer | Yes | Number of contacts to track (1-5), default 1 |
| `lead_for` | Selection | Yes | `'companies'` or `'people'`, default `'companies'` |
| `lead_type` | Selection | Yes | `'lead'` or `'opportunity'`, default `'opportunity'` |
| `suffix` | Char | Yes | Suffix appended to generated lead name |
| `team_id` | Many2one | Yes | Sales team for generated leads |
| `tag_ids` | Many2many | Yes | Tags for generated leads |
| `user_id` | Many2one | Yes | Salesperson for generated leads |
| `priority` | Selection | Yes | Lead priority |
| `lead_ids` | One2many | Yes | Generated leads |
| `lead_count` | Integer | No | Count of lead-type generated |
| `opportunity_count` | Integer | No | Count of opportunity-type generated |

**SQL Constraints:**
- `limit_extra_contacts`: `extra_contacts BETWEEN 1 AND 5`

**Key Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_compute_lead_count()` | — | Counts leads and opportunities from `lead_ids` |
| `_check_regex_url()` | `@api.constrains` | Validates regex compiles |
| `create()` / `write()` / `unlink()` | — | All clear ORM cache for `_get_active_rules` |
| `action_get_lead_tree_view()` | — | Shows leads only (type=lead) |
| `action_get_opportunity_tree_view()` | — | Shows opportunities only (type=opportunity) |
| `_get_active_rules()` | `@api.model @tools.ormcache()` | Caches all active rules for fast matching; returns dict with country_rules and rules list |
| `_match_url(website_id, url, country_code, state_code, rules_excluded)` | — | Returns matching rules for given context |
| `_process_lead_generation()` | `@api.model` | Cron: processes reveal views, calls IAP service |
| `_unlink_unrelevant_reveal_view()` | `@api.model` | Removes views with IPs already used in recent leads |
| `_get_reveal_views_to_process()` | `@api.model` | SQL query: groups views by IP, returns list of (ip, [rule_ids]) |
| `_prepare_iap_payload(pgv)` | — | Formats payload for IAP reveal service |
| `_get_rules_payload()` | — | Serializes rule criteria for IAP service |
| `_perform_reveal_service(server_payload)` | — | Calls IAP JSON-RPC, creates leads from responses |
| `_iap_contact_reveal(params, timeout)` | — | JSON-RPC call to `iap-services.odoo.com/iap/clearbit/1/reveal` |
| `_create_lead_from_response(result)` | — | Creates lead from IAP response data |
| `_lead_vals_from_response(result)` | — | Formats lead values from IAP company + people data |

---

### crm_reveal_view.py — CRMRevealView

**Inheritance:** Base (standalone `_name = 'crm.reveal.view'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `reveal_ip` | Char | Yes | IP address |
| `reveal_rule_id` | Many2one | Yes | Matching rule, btree_not_null |
| `reveal_state` | Selection | Yes | `'to_process'` or `'not_found'`, default `'to_process'` |
| `create_date` | Datetime | Yes | Creation timestamp, indexed |

**Indexes (raw SQL in `init`):**
- `crm_reveal_view_ip_rule_id`: Unique index on (reveal_rule_id, reveal_ip)
- `crm_reveal_view_state_create_date`: Composite on (reveal_state, create_date)

**Methods:**

| Method | Description |
|--------|-------------|
| `init()` | Creates raw SQL indexes (called at module install) |
| `_clean_reveal_views()` | Deletes old `'not_found'` views older than configured weeks |
| `_create_reveal_view(...)` | Inserts reveal view records via raw SQL; returns updated rules_excluded list |

---

### crm_lead.py — Lead (extension)

**Inheritance:** `crm.lead`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `reveal_ip` | Char | Yes | Original visitor IP |
| `reveal_iap_credits` | Integer | Yes | Credits consumed for this lead |
| `reveal_rule_id` | Many2one | Yes | Rule that generated this lead, btree_not_null |

**Methods:**

| Method | Description |
|--------|-------------|
| `_merge_get_fields()` | Adds `reveal_ip`, `reveal_iap_credits`, `reveal_rule_id` to lead merge fields |

---

### ir_http.py — IrHttp

**Inheritance:** `ir.http`

| Method | Description |
|--------|-------------|
| `_serve_page()` | On page hit: if public user with no existing lead, creates `crm.reveal.view` via `_create_reveal_view()` |

---

## Security / Data

**Access Control (`ir.model.access.csv`):**
- `model_crm_reveal_rule`: Manager full access, Salesman read-only
- `model_crm_reveal_view`: Manager full access, Salesman read-only

**IR Rules (`security/ir_rules.xml`):**
- `ir_rule_crm_reveal_rule_all`: All leads viewable by `group_sale_salesman_all_leads`
- `ir_rule_crm_reveal_rule_salesman`: Personal or global rules for `group_sale_salesman`
- `ir_rule_crm_reveal_view_all`: All views for `group_sale_salesman_all_leads`
- `ir_rule_crm_reveal_view_salesman`: Personal or global views

**Data Files:**
- `data/ir_model_data.xml`: External IDs for reveal rule
- `data/ir_cron_data.xml`: Cron job data for `_process_lead_generation`

---

## Critical Notes

- `_get_active_rules()` is cached with `@tools.ormcache()` — cleared on rule create/write/unlink
- `regex_url` handling: empty=`.*` (all pages), `/` = `.*/$` (homepage only)
- State codes are expanded: rule without state_ids matches any state; specific states are matched with `(country_code, state_code)` tuples
- Cron batch limit: `DEFAULT_REVEAL_BATCH_LIMIT = 25` IPs per run
- `_create_reveal_view` uses raw SQL INSERT with ON CONFLICT DO NOTHING for deduplication
- IAP service endpoint: `https://iap-services.odoo.com/iap/clearbit/1/reveal`
- Reveal views expire after `DEFAULT_REVEAL_VIEW_WEEKS_VALID = 5` weeks
- Leads are deduplicated by `clearbit_id` (`reveal_id`) — won't create duplicate leads for same company
- v17→v18: IAP reveal endpoint changed from Clearbit to generic IAP service; overall architecture similar
