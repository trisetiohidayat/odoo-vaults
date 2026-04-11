---
Module: website_hr_recruitment
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_hr_recruitment
---

## Overview

Public-facing job listings and application forms on the website. Jobs are SEO-optimized, searchable, and filterable by department, country, office, and contract type. Applicants can submit through a website form; UTM tracking is embedded in recruitment source URLs.

**Key Dependencies:** `hr_recruitment`, `website`, `utm`

**Python Files:** 5 model files

---

## Models

### hr_job.py — Job

**Inheritance:** `hr.job`, `website.seo.metadata`, `website.published.multi.mixin`, `website.searchable.mixin`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `description` | Html | Yes | Job description (uses prefetch=False for large content) |
| `website_published` | Boolean | Yes | Published on website, tracked |
| `website_description` | Html | Yes | Website-specific description, default QWeb render of `website_hr_recruitment.default_website_description` |
| `job_details` | Html | Yes | Hiring process details shown on submission page |
| `published_date` | Date | Yes | Date of publication, computed from `website_published` |
| `full_url` | Char | No | Absolute URL including base domain |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_get_default_website_description()` | `@mute_logger` | QWeb render of `website_hr_recruitment.default_website_description` |
| `_get_default_job_details()` | — | Returns default hiring process HTML |
| `_compute_full_url()` | `@api.depends('website_url')` | Joins base URL with `website_url` |
| `_compute_published_date()` | `@api.depends('website_published')` | Sets to today when published |
| `_onchange_website_published()` | `@api.onchange('website_published')` | Syncs `is_published` |
| `_compute_website_url()` | — | Returns `/jobs/{slug}` |
| `set_open()` | — | Unpublishes on close |
| `toggle_active()` | — | Unpublishes when deactivated |
| `_search_get_detail(website, order, options)` | `@api.model` | Full-text search with filters: country, department, office, contract type, remote, untyped |

**Search Detail Mapping:**
- `name`: text match
- `website_url`: stored
- `description`: text match (when `displayDescription=True`)

---

### hr_applicant.py — Applicant

**Inheritance:** `hr.applicant`

| Method | Description |
|--------|-------------|
| `website_form_input_filter(request, values)` | Pre-processes form submission: sets applicant name from `partner_name + job`, validates job is active, sets stage from non-folded stages |

---

### hr_department.py — Department

**Inheritance:** `hr.department`

| Field | Type | Notes |
|-------|------|-------|
| `display_name` | Char | Computed with `compute_sudo=True` for portal access |

---

### hr_recruitment_source.py — RecruitmentSource

**Inheritance:** `hr.recruitment.source`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `url` | Char | No | Computed: job's website URL with UTM params appended |

**Method:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_compute_url()` | `@api.depends(...)` | Builds URL: `{base_url}{job.website_url}?utm_campaign={campaign}&utm_medium={medium}&utm_source={source}` |

---

### website.py — Website

**Inheritance:** `website`

| Method | Description |
|--------|-------------|
| `get_suggested_controllers()` | Adds `('Jobs', '/jobs', 'website_hr_recruitment')` |
| `_search_get_details(search_type, order, options)` | Adds `hr.job` search to global website search when `search_type in ['jobs', 'all']` |

---

## Security / Data

**Security File:** `security/website_hr_recruitment_security.xml`

- `hr_job_public`: Public read where `website_published=True`
- `hr_job_portal`: Portal read where `website_published=True`
- `hr_job_officer`: HR Recruitment user reads all jobs
- `hr_department_public`: Public read if department has published jobs OR has children
- HR Recruitment user implied group: `website.group_website_restricted_editor`

**Data Files:**
- `data/config_data.xml`: Default configuration
- `data/hr_job_demo.xml`: Demo job positions

---

## Critical Notes

- Jobs use `website.published.multi.mixin` — multiple websites can publish independently
- `website_published` is tracked (has `tracking=True`) — publishes/unpublishes are logged in the chatter
- Applicant form validation: job must be active (`active=True`) to accept applications
- Stage assignment: picks first non-folded stage matching the job's stages
- UTM tracking: source URLs automatically tagged with `utm_campaign`, `utm_medium`, `utm_source`
- `_search_get_detail` uses `website.website_domain()` for multi-website filtering
- Country filter requires sudo for non-HR users — reinforces `website_published` filter
- v17→v18: `website.published.multi.mixin` replaced single-website `website.published.mixin` for multi-website support; job URL format changed from `/jobs/detail/{id}` to `/jobs/{slug}`
