---
Module: crm_iap_mine
Version: 18.0.0
Type: addon
Tags: #odoo18 #crm #iap #lead #enrichment
---

## Overview

IAP-based CRM lead mining. Enriches the Odoo CRM with clearbit-powered company and contact data. Generates leads/opportunities from configurable criteria (country, industry, size, role, seniority) via the IAP reveal service.

**Depends:** `crm`, `iap`

**Key Behavior:** All lead data (company info + contacts) is fetched via IAP. Credits are consumed per company (1 credit) and per contact (1 credit). Maximum 200 leads and 5 contacts per company. Industry/role/seniority filters are stored as reference data linked to external reveal IDs.

---

## Models

### `crm.iap.lead.mining.request` (New)

**Model:** `crm.iap.lead.mining.request`

| Field | Type | Note |
|-------|------|------|
| `name` | Char | Auto-generated sequence, `default='New'` |
| `state` | Selection | `'draft'`, `'error'`, `'done'` |
| `lead_number` | Integer | Number of companies to find (max 200) |
| `search_type` | Selection | `'companies'` or `'people'` |
| `error_type` | Selection | `'credits'` or `'no_result'` (on error state) |
| `lead_type` | Selection | `'lead'` or `'opportunity'` |
| `team_id` | Many2one `crm.team` | Auto-computed from user |
| `user_id` | Many2one `res.users` | Salesperson |
| `tag_ids` | Many2many `crm.tag` | Tags for generated leads |
| `lead_ids` | One2many `crm.lead` | Generated leads (via `lead_mining_request_id`) |
| `lead_count` | Integer (compute) | Count of generated leads |
| `filter_on_size` | Boolean | Enable company size filter |
| `company_size_min/max` | Integer | Size range filter |
| `country_ids` | Many2many `res.country` | Country filter |
| `state_ids` | Many2many `res.country.state` | State filter (whitelist-limited) |
| `available_state_ids` | One2many (compute) | Computed from `country_ids` whitelist |
| `industry_ids` | Many2many `crm.iap.lead.industry` | Industry filter |
| `contact_number` | Integer | Max 5 contacts per company |
| `contact_filter_type` | Selection | `'role'` or `'seniority'` |
| `preferred_role_id` | Many2one `crm.iap.lead.role` | Primary role filter |
| `role_ids` | Many2many `crm.iap.lead.role` | Other role filters |
| `seniority_id` | Many2one `crm.iap.lead.seniority` | Seniority filter |
| `lead_credits` | Char (compute) | Credit cost tooltip for companies |
| `lead_contacts_credits` | Char (compute) | Credit cost tooltip for contacts |
| `lead_total_credits` | Char (compute) | Total credits tooltip |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_tooltip()` | — | Calculates credit costs and tooltip strings |
| `_compute_lead_count()` | — | Counts linked leads via `_read_group` |
| `_compute_team_id()` | — | Auto-assigns team based on user and `lead_type` |
| `_compute_available_state_ids()` | — | Filters states to whitelist countries only |
| `_onchange_available_state_ids()` | — | Clears invalid states on change |
| `_onchange_lead_number()` | — | Clamps to 1–MAX_LEAD (200) |
| `_onchange_contact_number()` | — | Clamps to 1–MAX_CONTACT (5) |
| `_onchange_country_ids()` | — | Clears states when country changes |
| `_prepare_iap_payload()` | dict | Builds reveal service payload; accumulates `reveal_ids` from industry records |
| `_perform_request()` | list/False | Calls `_iap_contact_mining`; handles `InsufficientCreditError` |
| `_iap_contact_mining(params)` | dict | JSON-RPC to `iap/clearbit/2/lead_mining_request` |
| `_create_leads_from_response(result)` | — | Creates leads; posts `iap_mail.enrich_company` template message |
| `_lead_vals_from_response(data)` | dict | Delegates to `CRMHelpers.lead_vals_from_response` |
| `action_draft()` | — | Resets state and name to `'New'` |
| `action_submit()` | — | Generates sequence, performs request, creates leads, transitions state |
| `action_get_lead_action()` | Action | Opens leads list filtered to this request |
| `action_get_opportunity_action()` | Action | Opens opportunities list filtered to this request |
| `action_buy_credits()` | Action | Opens IAP credits URL for `reveal` service |
| `get_empty_list_help()` | str | Returns empty list help message |

**Constants:**
- `MAX_LEAD = 200`
- `MAX_CONTACT = 5`
- `CREDIT_PER_COMPANY = 1`
- `CREDIT_PER_CONTACT = 1`

### `crm.lead` (Inherited)

**Inherited from:** `crm.lead`

| Field | Type | Note |
|-------|------|------|
| `lead_mining_request_id` | Many2one `crm.iap.lead.mining.request` | Source mining request; indexed btree_not_null |

| Method | Returns | Note |
|--------|---------|------|
| `_merge_get_fields()` | list | Includes `lead_mining_request_id` in lead merge |
| `action_generate_leads()` | Action | Opens mining request wizard in modal |

### `crm.iap.lead.helpers` (New, Utility)

**Model:** `crm.iap.lead.helpers`

| Method | Returns | Note |
|--------|---------|------|
| `_notify_no_more_credit(service, model, param)` | — | Sends email to record creators; uses ir.config_parameter to prevent spam |
| `lead_vals_from_response(...)` | dict | Builds full lead vals from clearbit company + people data |
| `_find_state_id(state_code, country_id)` | int/False | Looks up state by code and country |

### `crm.iap.lead.industry` (New)

**Model:** `crm.iap.lead.industry`

| Field | Type | Note |
|-------|------|------|
| `name` | Char | Industry name (translate) |
| `reveal_ids` | Char | Comma-separated reveal IDs from clearbit |
| `color` | Integer | Color index |
| `sequence` | Integer | Sort order |

| Constraint | Note |
|------------|------|
| `unique(name)` | Industry names must be unique |

### `crm.iap.lead.role` (New)

**Model:** `crm.iap.lead.role`

| Field | Type | Note |
|-------|------|------|
| `name` | Char | Role name (translate) |
| `reveal_id` | Char | External clearbit role ID |
| `color` | Integer | Color index |

| Constraint | Note |
|------------|------|
| `unique(name)` | Role names must be unique |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_display_name()` | — | Replaces underscores with spaces and title-cases |

### `crm.iap.lead.seniority` (New)

**Model:** `crm.iap.lead.seniority`

| Field | Type | Note |
|-------|------|------|
| `name` | Char | Seniority name (translate) |
| `reveal_id` | Char | External clearbit seniority ID |

| Constraint | Note |
|------------|------|
| `unique(name)` | Seniority names must be unique |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_display_name()` | — | Replaces underscores with spaces and title-cases |

---

## Critical Notes

- **`_prepare_iap_payload`:** Industry `reveal_ids` are comma-separated strings per record; accumulated into a flat list before sending to reveal service.
- **State ID Whitelist:** `_compute_available_state_ids` filters to countries in `iap_tools._STATES_FILTER_COUNTRIES_WHITELIST` to avoid poor reveal results.
- **Credit Calculation:** `_compute_tooltip` computes total credits as `(CREDIT_PER_COMPANY * lead_number) + (CREDIT_PER_CONTACT * contact_number * lead_number)`.
- **States onchange:** `_onchange_available_state_ids` removes states not in the available set.
