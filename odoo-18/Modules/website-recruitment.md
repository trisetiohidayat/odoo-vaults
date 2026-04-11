---
Module: website_hr_recruitment
Version: Odoo 18
Type: Integration
Tags: [#hr, #recruitment, #website, #portal]
Related: [[Modules/hr-recruitment]]
---

# website_hr_recruitment — Website Job Applications

**Module path:** `odoo/addons/website_hr_recruitment/`
**Depends:** `hr_recruitment`, `website_mail`
**Auto-installs:** `hr_recruitment`, `website_mail`
**Category:** Website/Website

Publishes job positions on the website and captures applications through a public form. Automatically creates `hr.applicant` and `hr.candidate` records from website submissions.

---

## Models

### `hr.job` — Extended (from `hr_recruitment`)

**File:** `addons/website_hr_recruitment/models/hr_job.py`
**Inherit:** `website.seo.metadata`, `website.published.multi.mixin`, `website.searchable.mixin`

#### Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | Html | Job description (full page content, translate, sanitize attributes=False, sanitize_form=False) |
| `website_published` | Boolean | Set to publish on website, tracking=True |
| `website_description` | Html | Public-facing description, default rendered from template `website_hr_recruitment.default_website_description` |
| `job_details` | Html | Process details shown on apply page (Time to Answer, Process, Days to get an Offer), default rendered from `_get_default_job_details()` |
| `published_date` | Date | Auto-set when `website_published` becomes True (store=True) |
| `full_url` | Char | Full public URL, computed via url_join |

#### Key Methods

- `_get_default_website_description()` — QWeb render of `website_hr_recruitment.default_website_description`
- `_get_default_job_details()` — returns hardcoded HTML with "Time to Answer: 2 open days", "Process: 1 Phone Call, 1 Onsite Interview", "Days to get an Offer: 4 Days after Interview"
- `_onchange_website_published()` — onchange: if `website_published=True`, sets `is_published=True`; else sets `is_published=False`
- `_compute_website_url()` — sets `website_url` to `/jobs/{slug(job)}`
- `_compute_full_url()` — computes full URL via `url_join(base_url, website_url or '/jobs')`
- `_compute_published_date()` — sets to today when `website_published` changes
- `toggle_active()` — when archiving a job, automatically unpublishes from website (`website_published=False`)
- `_search_get_detail(website, order, options)` — implements `website.searchable.mixin` for job search; filters by country_id, department_id, office_id, contract_type_id, is_remote, is_other_department, is_untyped; requires sudo for country-based search unless user is recruitment user; maps fields: name (text, match=True), website_url (text), description (text, html, match=True if with_description option); icon: `fa-briefcase`

#### Mixin Behavior

- `website.published.multi.mixin` — adds `is_published`, `website_url`; `website_published` field drives `is_published`
- `website.seo.metadata` — adds SEO fields (meta_title, meta_description, meta_keywords)
- `website.searchable.mixin` — enables global search integration for job listings

---

### `hr.applicant` — Extended (from `hr_recruitment`)

**File:** `addons/website_hr_recruitment/models/hr_applicant.py`

#### `website_form_input_filter(request, values)`

This method is the bridge between the website form and the applicant record. Called by `website.form` controller before record creation.

1. If `partner_name` in values, constructs `name` as `"Partner Name - Job Name"` or `"Partner Name's Application"`
2. If `job_id` in values:
   - Raises `UserError` if job is not active (already closed)
   - Searches for first non-folded stage (`fold=False`, sequence asc) matching the job
   - Sets `stage_id` to that stage
3. Returns modified values dict

---

### `hr.recruitment.source` — Extended (from `hr_recruitment`)

**File:** `addons/website_hr_recruitment/models/hr_recruitment_source.py`

| Field | Type | Description |
|-------|------|-------------|
| `url` | Char | Tracker URL, computed from source_id + job website_url + UTM params |

#### `_compute_url()`

Constructs URL as: `{job.base_url}{job.website_url}?utm_campaign=Job Campaign&utm_medium={medium.name}&utm_source={source.name}`

Uses `utm_campaign_job` ref, medium from source (default website if none), source name. Enables tracking which source drove each application.

---

### `hr.department` — Extended (from `hr`)

**File:** `addons/website_hr_recruitment/models/hr_department.py`

| Field | Type | Description |
|-------|------|-------------|
| `display_name` | Char | Computed with sudo (for portal access), search-enabled |

#### `_compute_display_name()`

`compute_sudo=True` — department names must be readable by public website users who don't have HR access.

---

### `website` — Extended (from `website`)

**File:** `addons/website_hr_recruitment/models/website.py`

- `get_suggested_controllers()` — appends ('Jobs', `/jobs`, `website_hr_recruitment`) to suggested controllers
- `_search_get_details(search_type, order, options)` — adds `hr.job._search_get_detail()` to search results when type is `jobs` or `all`

---

## Controllers

### `website_hr_recruitment` (extends `website.form`)

**File:** `addons/website_hr_recruitment/controllers/main.py`

#### Routes

| Route | Auth | Description |
|-------|------|-------------|
| `/jobs` | public | Job listings with filtering |
| `/jobs/page/<int:page>` | public | Paginated listings |
| `/jobs/detail/<model("hr.job"):job>` | public | Redirects to `/jobs/{slug(job)}` (301) |
| `/jobs/<model("hr.job"):job>` | public | Job detail page |
| `/jobs/apply/<model("hr.job"):job>` | public | Application form page |
| `/jobs/add` | user | Creates new draft job via JSON |
| `/website_hr_recruitment/check_recent_application` | public | AJAX check for duplicates |
| Various compatibility routes | public | Deprecated since Odoo 16.3 |

#### `/jobs` — Job Listings

**Parameters:** country_id, department_id, office_id, contract_type_id, is_remote, is_other_department, is_untyped, page, search, all_countries

**Behavior:**
1. Defaults country to user's geoip country if no filters set and that country has jobs
2. Performs website search with `_search_with_fuzzy("jobs", ...)` for full-text + filter matching
3. Computes cross-country, cross-department, cross-office, cross-employment-type counts for filter sidebar
4. Browses jobs as sudo because address data is restricted
5. Renders `website_hr_recruitment.index` template with jobs, filter counts, pager

**Sorting:** `is_published desc, sequence, no_of_recruitment desc`

#### `/jobs/<model("hr.job"):job>` — Job Detail

Renders `website_hr_recruitment.detail` with job as main_object.

#### `/jobs/apply/<model("hr.job"):job>` — Application Form

Renders `website_hr_recruitment.apply`. Reads session for any validation errors and default values from prior submission attempt.

#### `/jobs/add` — Create Job

Auth: user (not public). Creates a draft job with name "Job Title" and redirects to the edit page at `/jobs/{slug(job)}`.

#### `check_recent_application` — Duplicate Detection

JSON route, auth=public. Checks for recent (last 6 months) applications matching the form field (name/email/phone/linkedin) for the same job. Returns warning messages:
- If refused application exists for same job in last 6 months: "We've found a previous closed application..."
- If ongoing application for same job: "An application already exists for X... Duplicates might be rejected. Contact recruiter."
- If ongoing application for different job with same identifier: "We found a recent application with a similar name..." with option to continue

#### `extract_data(model, values)` — Form Data Processing

**Critical method** for the website form submission pipeline (called by `website.form` controller):
1. If form model is `hr.applicant`, extracts `partner_name`, `partner_phone`, `email_from` from values
2. Determines `company_id` from department or job
3. Searches for existing candidate by email + phone
4. Creates new `hr.candidate` if not found
5. Calls super to continue standard form processing
6. Adds `candidate_id` to the record values before creation

This ensures that website form submissions always create or find a candidate first, then link the applicant to it.

---

## Website Form Pipeline

The complete flow when a candidate applies via the website:

```
/jobs → /jobs/apply/<job> → website.form controller
  → extract_data() creates/finds hr.candidate
  → website_form_input_filter() sets stage_id
  → hr.applicant.create() called
  → CV attachment copy: candidate → applicant
  → recruiter notified of new applicant
```

The `website_form_input_filter` on `hr.applicant` enforces:
- Job must be active (raises if closed)
- Stage set to job's first non-folded stage

---

## SEO / Website Integration

- Jobs appear in website global search via `_search_get_details`
- `website.seo.metadata` mixin adds meta title/description fields per job
- `website.published.multi.mixin` controls visibility based on `website_published`
- Sitemap generated via `sitemap_jobs()` — single entry for `/jobs`
- Job detail pages are sitemap-indexed with `sitemap=True`
- Application form route also sitemap-indexed

---

## Access Control

- Public users can view published jobs and submit applications
- Applicant creation via website does not require backend HR access
- Department display name uses sudo for public access
- Country-based job filtering requires sudo and additional domain constraint to enforce `website_published` unless user is in recruitment group

---

## Template Architecture

- `website_hr_recruitment.index` — job listing page (kanban-style with filters)
- `website_hr_recruitment.detail` — job detail page (full description, apply CTA)
- `website_hr_recruitment.apply` — application form page
- `website_hr_recruitment.default_website_description` — QWeb template for default website description