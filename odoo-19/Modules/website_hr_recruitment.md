---
type: module
module: website_hr_recruitment
tags: [odoo, odoo19, modules, website, hr, recruitment, jobs, applicant]
created: 2026-04-11
updated: 2026-04-11
---

# website_hr_recruitment (L4)

> **Module:** `website_hr_recruitment` | **Path:** `odoo/addons/website_hr_recruitment/` | **Odoo Version:** 19 | **Manifest version:** 1.1

## Overview

Publishes open job positions on the company's public website, enabling candidates to discover, search, filter, and submit applications online. Applications are automatically created as `hr.applicant` records and routed to the recruitment pipeline in the backend. The module provides a rich job detail page with an inline-editable job description, a searchable job board with faceted filters (department, location, contract type, country, industry), and an online application form with client-side duplicate detection and server-side stage assignment.

**Core responsibility:** Bridge the public-facing job board with the internal hiring process, without replacing the backend recruitment pipeline.

---

## Manifest and Dependencies

```python
'depends': [
    'hr_recruitment',   # applicant, job, stage pipeline
    'website_mail',      # website-aware messaging/portal
],
'auto_install': ['hr_recruitment', 'website_mail'],
'category': 'Website/Website',
'sequence': 310,
'application': True,
```

### Dependency Tree

```
website_hr_recruitment
├── hr_recruitment        (applicant, job, stage pipeline)
│   └── hr                (employee, department, contract type)
└── website_mail          (website-aware messaging/portal)
    └── website           (website rendering, SEO, publishing)
        └── mail           (messaging)
```

**Auto-install meaning:** When `website_hr_recruitment` is installed, Odoo automatically installs its dependencies (`hr_recruitment` and `website_mail`) if they are not already present.

---

## Model Architecture

### File Inventory

| File | Model(s) Extended/Created | Role |
|------|--------------------------|------|
| `models/hr_job.py` | `hr.job` (extend) | Website publishing, SEO, search, URL generation |
| `models/hr_applicant.py` | `hr.applicant` (extend) | Form submission validation and stage assignment |
| `models/hr_recruitment_source.py` | `hr.recruitment.source` (extend) | UTM-tagged tracker URL computation |
| `models/hr_department.py` | `hr.department` (extend) | `display_name` compute_sudo for portal access |
| `models/website.py` | `website` (extend) | Jobs search integration, suggested controller |
| `models/website_page.py` | `website.page` (extend) | Cache control for thank-you page |

---

## Core Model: `hr.job` Extension

**File:** `models/hr_job.py` | **Inherits:** `hr.job`, `website.seo.metadata`, `website.published.multi.mixin`, `website.searchable.mixin`

### L1: Model Overview

The `HrJob` class extends `hr.job` with three mixins providing website-specific capabilities:
- `website.seo.metadata` — SEO title/description/meta tags for job pages
- `website.published.multi.mixin` — `is_published` + `website_published` for per-website toggle
- `website.searchable.mixin` — `_search_get_detail` for global website search and faceted filtering

### L2: All Fields with Type, Default, and Constraints

#### Fields Added by This Module

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | `Html` | inherited | Internal job description (translated, `sanitize_attributes=False`, `sanitize_form=False`). The field already existed on `hr.job`; this declaration overrides its sanitization options for the website context — notably `sanitize_form=False` allows raw HTML from WYSIWYG editors without XSS sanitization. `prefetch=False` because it can be large. |
| `website_published` | `Boolean` | `False` | Controls visibility on the public website, independent of the `active` field. `tracking=True` — toggling generates a mail.message on the job record. |
| `website_description` | `Html` | `_get_default_website_description` | Public-facing job page content shown above the fold on `/jobs/{slug}`. Translated field. `sanitize_attributes=False`, `sanitize_form=False`. `prefetch=False`. |
| `job_details` | `Html` | `_get_default_job_details` | Recruitment process details (Time to Answer, Interview Steps, Days to Offer) displayed on the application page. Translated. `sanitize_attributes=False`. |
| `published_date` | `Date` | computed | Date when `website_published` was set to `True`. Stored. Computed on every write to `website_published`. |
| `full_url` | `Char` | computed | Absolute URL combining `get_base_url()` with the relative `website_url`. Used for sharing/copying the job link. |
| `website_url` | `Char` | computed | Relative URL `/jobs/{slug}`. Overrides the mixin's default computation via `_compute_website_url()`. |

### L2: Default HTML Generation

**`_get_default_website_description()`:**
```python
@mute_logger('odoo.addons.base.models.ir_qweb')
def _get_default_website_description(self):
    return self.env['ir.qweb']._render("website_hr_recruitment.default_website_description", raise_if_not_found=False)
```
Renders the QWeb template `website_hr_recruitment.default_website_description` via `ir.qweb._render()`. Falls back silently (`raise_if_not_found=False`) if the template does not exist. The `@mute_logger` suppresses warnings about missing templates in certain install scenarios.

**`_get_default_job_details()`:**
```python
def _get_default_job_details(self):
    return _("""
        <span class="text-muted small">Time to Answer</span>
        <h6>2 open days</h6>
        <span class="text-muted small">Process</span>
        <h6>1 Phone Call</h6>
        <h6>1 Onsite Interview</h6>
        <span class="text-muted small">Days to get an Offer</span>
        <h6>4 Days after Interview</h6>
    """)
```
Returns a hard-coded HTML string (not a template render) with four placeholder sections. This is the content shown on the application submission page below the application form.

### L3: Computed Field Details

#### `_compute_published_date`

```python
@api.depends('website_published')
def _compute_published_date(self):
    for job in self:
        job.published_date = job.website_published and fields.Date.today()
```

Only sets the date when publishing is `True`. Does NOT clear the date when unpublishing — the first publish date is preserved. This is a notable behavior: once set, `published_date` becomes stale if the job is unpublished and later republished.

#### `_compute_website_url`

```python
def _compute_website_url(self):
    super()._compute_website_url()
    for job in self:
        if not job.id:  # Skip new (unsaved) records
            continue
        job.website_url = f'/jobs/{self.env["ir.http"]._slug(job)}'
```

The `if not job.id` guard is critical: `_slug()` will raise an error on `newid` records (phantom records from form context). This override replaces whatever the `website.published.multi.mixin` computes and forces the `/jobs/` prefix path.

#### `_compute_full_url`

```python
@api.depends('website_url')
def _compute_full_url(self):
    for job in self:
        job.full_url = url_join(job.get_base_url(), (job.website_url or '/jobs'))
```

Uses `get_base_url()` to support multi-website deployments where each website has its own domain/root. Falls back to `/jobs` if `website_url` is not yet computed.

#### `_compute_published_date`

```python
@api.depends('website_published')
def _compute_published_date(self):
    for job in self:
        job.published_date = job.website_published and fields.Date.today()
```

Sets the date when publishing is `True`. Does NOT clear the date when unpublishing — the first publish date is preserved.

### L3: Onchange — `_onchange_website_published`

```python
@api.onchange('website_published')
def _onchange_website_published(self):
    if self.website_published:
        self.is_published = True
    else:
        self.is_published = False
```

Bidirectional sync: `website_published` drives `is_published`. The `website.published.multi.mixin` uses `is_published` to determine whether the page is served publicly. This onchange ensures the two stay in sync during manual editing in the backend form.

### L3: Action Methods

**`action_archive()`:**
```python
def action_archive(self):
    self.filtered('active').website_published = False
    return super().action_archive()
```
When a recruiter archives a job, the website publication flag is automatically cleared. Archived jobs are no longer served to public users (via `ir.rule`). However, the `published_date` is NOT cleared (see above).

**`set_open()`:**
```python
def set_open(self):
    self.write({'website_published': False})
    return super().set_open()
```
Reopening a job via `set_open()` (e.g., unblocking after an offer) does NOT automatically republish. The recruiter must explicitly republish — a deliberate separation between recruitment workflow state and website publication state.

**`get_backend_menu_id()`:**
```python
def get_backend_menu_id(self):
    return self.env.ref('hr_recruitment.menu_hr_recruitment_root').id
```
Overrides the mixin default to route the website editor "Edit in Backend" button to the Recruitment app menu instead of the Website menu.

### L3: Website Search — `_search_get_detail()`

Implements the `website.searchable.mixin` interface to power the global website search bar (and the `/jobs` page faceted filters).

```python
@api.model
def _search_get_detail(self, website, order, options):
    requires_sudo = False
    domain = [website.website_domain()]  # multi-website scoping

    if country_id:
        domain.append([('address_id.country_id', '=', int(country_id))])
        requires_sudo = True  # country access requires sudo
    if department_id:
        domain.append([('department_id', '=', int(department_id))])
    elif is_other_department:
        domain.append([('department_id', '=', None)])
    if office_id:
        domain.append([('address_id', '=', int(office_id))])
    elif is_remote:
        domain.append([('address_id', '=', None)])
    if contract_type_id:
        domain.append([('contract_type_id', '=', int(contract_type_id))])
    elif is_untyped:
        domain.append([('contract_type_id', '=', None)])

    if requires_sudo and not self.env.user.has_group('hr_recruitment.group_hr_recruitment_user'):
        domain.append([('website_published', '=', True)])

    return {
        'model': 'hr.job',
        'requires_sudo': requires_sudo,
        'base_domain': domain,
        'search_fields': ['name'],
        'fetch_fields': ['name', 'website_url'],
        'mapping': {...},
        'icon': 'fa-briefcase',
    }
```

**Filter behavior:**
- `is_remote=True`: selects jobs where `address_id` is unset (no office = remote-friendly).
- `is_other_department=True`: selects jobs where `department_id` is unset.
- `is_untyped=True`: selects jobs where `contract_type_id` is unset.
- `requires_sudo` is set to `True` only when filtering by `country_id` — the `address_id.country_id` field may not be accessible to public users, so `sudo()` is needed. However, when `sudo()` is used and the user lacks recruitment access, `website_published=True` is explicitly added to prevent leaking unpublished job data.

---

## `hr.applicant` Extension

**File:** `models/hr_applicant.py` | **Inherits:** `hr.applicant`

### Method: `website_form_input_filter(request, values)`

**Signature:** `website_form_input_filter(self, request, values) -> dict`

Called by the `website.form` controller (`WebsiteForm.extract_data()` → `website_form_input_filter()`) just before an `hr.applicant` record is created from a website form submission.

#### Logic

**1. Job validity guard:**
```python
if values.get('job_id'):
    job = self.env['hr.job'].browse(values.get('job_id'))
    if not job.sudo().active:
        raise UserError(_("The job offer has been closed."))
```
Uses `sudo()` because the public website user does not have read access to `hr.job`. Checks `job.active` (not `job.website_published`) — a job could be active but unpublished. The distinction matters: unpublished jobs should reject new applications with the same error message, since re-publishing would create a duplicate applicant.

**2. Stage assignment:**
```python
stage = self.env['hr.recruitment.stage'].sudo().search([
    ('fold', '=', False),
    '|', ('job_ids', '=', False), ('job_ids', '=', values['job_id']),
], order='sequence asc', limit=1)
if stage:
    values['stage_id'] = stage.id
```
- `fold = False`: excludes stages marked as "folded" (typically done/hired/refused stages in the kanban pipeline).
- `job_ids = False OR job_ids = current_job`: prefers job-specific stages over the generic first stage.
- `order = sequence asc, limit=1`: takes the earliest open stage in the pipeline.
- Uses `sudo()` because recruitment stages may not be accessible to public users.

#### Failure Modes

- If no non-folded stage exists for the job, `stage_id` is not set. The `hr.applicant` model defaults will apply (typically the first stage in sequence).
- If the job ID is invalid or the job has been deleted, `browse()` returns an empty recordset. `job.sudo().active` evaluates to `False` (empty recordset), triggering the `UserError`.
- Race condition: between form load and submission, the job could be closed by another user. The `sudo().active` check at submission time guards against this.

#### Security Note

`sudo()` is required throughout because the public website session (`base.group_public`) lacks ACL access to `hr.job`, `hr.recruitment.stage`, and `hr.department`. The `sudo()` call elevates to the Odoo superuser — but the security rules in `website_hr_recruitment_security.xml` only apply when NOT using `sudo()`. Since the check is reading administrative recruitment data, superuser access is appropriate.

---

## `hr.recruitment.source` Extension

**File:** `models/hr_recruitment_source.py` | **Inherits:** `hr.recruitment.source`

### Field: `url` (`Char`, computed)

```python
@api.depends('source_id', 'source_id.name', 'job_id', 'job_id.company_id')
def _compute_url(self):
    for source in self:
        source.url = urls.urljoin(source.job_id.get_base_url(), "%s?%s" % (
            source.job_id.website_url,
            url_encode({
                'utm_campaign': self.env.ref('hr_recruitment.utm_campaign_job').name,
                'utm_medium': source.medium_id.name or self.env['utm.medium']._fetch_or_create_utm_medium('website').name,
                'utm_source': source.source_id.name or None
            }),
        ))
```

**Components:**
- `get_base_url()`: respects multi-website per-company base URL.
- `website_url`: the `/jobs/{slug}` path.
- `utm_campaign`: always the `hr_recruitment.utm_campaign_job` campaign name (a system UTM campaign).
- `utm_medium`: `medium_id.name` if set, otherwise auto-creates/fetches a UTM medium named `'website'` via `_fetch_or_create_utm_medium()`.
- `utm_source`: `source_id.name` (e.g., "LinkedIn", "Indeed", "Referral"). Set to `None` if no source is configured (omitted from query string).

---

## `hr.department` Extension

**File:** `models/hr_department.py`

```python
class HrDepartment(models.Model):
    _inherit = 'hr.department'

    display_name = fields.Char(compute_sudo=True)
```

**Purpose:** Forces `display_name` to compute with `sudo()` via `compute_sudo=True`. By default, `hr.department` records are not accessible to public/portal users. Without this, the job listing page would fail to render department names for anonymous visitors. The `compute_sudo=True` flag causes the field to always compute using the superuser context, bypassing the normal ACL for this specific field only.

---

## `website.page` Extension

**File:** `models/website_page.py` | **Inherits:** `website.page`

### Method: `_allow_to_use_cache(request)`

```python
@api.model
def _allow_to_use_cache(self, request):
    if request.httprequest.path == '/job-thank-you':
        return False
    return super()._allow_to_use_cache(request)
```

The `/job-thank-you` confirmation page must NOT be served from the website page cache. This prevents candidates from seeing another user's confirmation page after submission. The standard `website.page` caching is disabled for this route by returning `False`.

---

## `website` Extension

**File:** `models/website.py` | **Inherits:** `website`

### Method: `get_suggested_controllers()`

```python
def get_suggested_controllers(self):
    suggested_controllers = super(Website, self).get_suggested_controllers()
    suggested_controllers.append((_('Jobs'), self.env['ir.http']._url_for('/jobs'), 'website_hr_recruitment'))
    return suggested_controllers
```

Adds a "Jobs" entry to the website footer suggested controllers list.

### Method: `_search_get_details()`

```python
def _search_get_details(self, search_type, order, options):
    result = super()._search_get_details(search_type, order, options)
    if search_type in ['jobs', 'all']:
        result.append(self.env['hr.job']._search_get_detail(self, order, options))
    return result
```

Appends the `hr.job` search detail to the website's global search. Triggered when `search_type='jobs'` or `search_type='all'` (e.g., from the global search bar).

---

## Controller Overview

The module extends `website.form` (from `website.controllers.form`) to handle job form rendering and submission.

### Key Routes

| Route | Auth | Purpose |
|-------|------|---------|
| `GET /jobs` | public | Job listing with faceted filters |
| `GET /jobs/{slug}` | public | Job detail page |
| `GET /jobs/apply/{slug}` | public | Application form |
| `POST /website/form/hr.applicant` | public | Form submission |
| `GET /job-thank-you` | public | Confirmation page (never cached) |
| `GET /jobs/add` | user | Creates job and redirects to website editor |
| `/website_hr_recruitment/check_recent_application` | public (jsonrpc) | Client-side duplicate detection |

---

## Cross-Model Relationships

### Models Extended and Their Roles

| Model | Extension | What It Adds |
|-------|-----------|--------------|
| `hr.job` | Classic `_inherit` | Website fields, SEO, search, URL, actions |
| `hr.applicant` | Classic `_inherit` | Form validation, stage assignment |
| `hr.recruitment.source` | Classic `_inherit` | UTM-tagged tracker URL |
| `hr.department` | Classic `_inherit` | `compute_sudo=True` on `display_name` |
| `website.page` | Classic `_inherit` | Cache bypass for thank-you page |
| `website` | Classic `_inherit` | Search integration, suggested controller |

### External Model Dependencies

| Model | Relationship | Purpose |
|-------|-------------|---------|
| `res.country` | `address_id.country_id` | Country filter on job listings |
| `hr.department` | `department_id` | Department filter |
| `hr.recruitment.stage` | `stage_id` | Stage assignment on form submission |
| `utm.medium` | `medium_id` | UTM medium for source tracking |
| `utm.source` | `source_id` | UTM source for recruitment channel |

---

## Security Model

### Record Rules (`website_hr_recruitment_security.xml`)

| Rule | Model | Group | Domain | Operations |
|------|-------|-------|--------|------------|
| `hr_job_public` | `hr.job` | `base.group_public` | `website_published = True` | read only |
| `hr_job_portal` | `hr.job` | `base.group_portal` | `website_published = True` | read only |
| `hr_job_officer` | `hr.job` | `hr_recruitment.group_hr_recruitment_user` | `(1, '=', 1)` (all) | read only |
| `hr_department_public` | `hr.department` | `base.group_public` | <code>&#124; jobs_ids.website_published=True, child_ids not empty</code> | read only |

**`hr_department_public` domain interpretation:** A department is visible to public users if either:
- It has at least one published job (`jobs_ids.website_published = True`), OR
- It has child departments (regardless of job publication status)

This ensures the department filter on the job listing page is functional without exposing all internal departments.

### Implied Groups

```xml
<record id="hr_recruitment.group_hr_recruitment_user" model="res.groups">
    <field name="implied_ids" eval="[(4, ref('website.group_website_restricted_editor'))]"/>
</record>
```

The `hr_recruitment.group_hr_recruitment_user` group (HR Recruitment Officer) automatically gains the `website.group_website_restricted_editor` capability. This allows recruitment officers to use the website editor to modify job page content without being full website administrators.

### ACL CSV

```
access_hr_job_public_public   hr.job.public   hr.model_hr_job  base.group_public   1 0 0 0
access_hr_job_public_portal   hr.job.public   hr.model_hr_job  base.group_portal   1 0 0 0
access_hr_job_public_employee  hr.job.public   hr.model_hr_job  base.group_user    1 0 0 0
access_hr_department_public   hr.department.public hr.model_hr_department base.group_public 1 0 0 0
```

`base.group_user` (internal employees) gets read access to `hr.job` via this CSV, even though they are not covered by the XML record rules (which only target `base.group_public`, `base.group_portal`, and `hr_recruitment.group_hr_recruitment_user`).

### Form Builder Whitelist (`data/config_data.xml`)

The `hr.applicant` model is configured with:
- `website_form_key`: `'apply_job'` — the form action identifier
- `website_form_access`: `True` — allows public form submissions
- `website_form_label`: `'Apply for a Job'`

Whitelisted fields for the public form builder:
- `email_from` — applicant's email address
- `partner_name` — applicant's full name
- `partner_phone` — phone number
- `job_id` — the job being applied to
- `department_id` — applicant's preferred department
- `linkedin_profile` — LinkedIn URL
- `applicant_properties` — custom applicant properties (typed data)

---

## Business Flow

```
1. Setup: HR recruiter creates job in backend
   → name, description, department, address_id, contract_type_id
   → website_published = False (draft state)

2. Publish: HR recruiter enables website_published
   → is_published syncs to True via onchange
   → published_date is set to today
   → Job appears on /jobs listing page
   → Sitemap updated

3. Candidate searches /jobs
   → GeoIP country auto-detected if no explicit filter
   → Faceted filters applied (department, office, contract type, country, industry)
   → Fuzzy search on job name/description

4. Candidate opens /jobs/{slug}
   → Job detail page rendered (website_description, job_details)
   → Inline WYSIWYG editing available for recruitment officers

5. Candidate applies (/jobs/apply/{slug} → /website/form/hr.applicant)
   a. Client-side: focusout triggers duplicate check RPC
      → /website_hr_recruitment/check_recent_application
      → Shows warning if same job ongoing/refused in 6 months
      → Shows soft warning if similar application exists for other jobs
   b. Server-side: website_form_input_filter runs
      → Validates job.active == True
      → Assigns first non-folded recruitment stage
   c. hr.applicant record created with stage, job_id, applicant data
   d. Confirmation page /job-thank-you shown (never cached)

6. HR reviews in backend kanban
   → Standard hr_recruitment pipeline: New → Interview → Offer → Hired
   → Mail templates sent automatically (if configured)

7. Job closed/archived
   → action_archive() sets website_published = False
   → ir.rule blocks public access
   → Job disappears from /jobs listing
```

---

## Duplicate Detection Endpoint

### Route: `website_hr_recruitment/check_recent_application`

**Auth:** public | **Type:** jsonrpc

Client-side duplicate detection endpoint. Called via RPC from the frontend `HrRecruitmentForm` interaction on `focusout` events (name, email, phone, LinkedIn fields).

**Domain logic:**
- Searches for applicants matching the given field value (`partner_name`, `email_normalized`, `partner_phone`, or `linkedin_profile`).
- Scopes to the current website (`job_id.website_id in [website.id, False]`).
- Includes both ongoing and recently refused applications:
  - Ongoing: `application_status = 'ongoing'`
  - Refused within 6 months: `application_status = 'refused' AND active = False AND create_date >= 6 months ago`

**Three response tiers:**
1. **Refused in last 6 months for same job**: Hard warning — "Please consider before applying in order not to duplicate efforts."
2. **Ongoing application for same job**: Hard warning — "An application already exists... Duplicates might be rejected." Includes recruiter contact info if available.
3. **Ongoing application for a different job**: Soft warning — "We found a recent application with a similar name, email, phone number. You can continue if it's not a mistake."
4. **No match**: `{ 'message': None }` — no warning shown.

**Performance note:** The `Domain.AND([field_domain, status_domain])` syntax uses Odoo's `Domain` class for safe domain construction. The `grouped('application_status')` groups results in Python (not SQL) to avoid post-processing complexity.

---

## Performance Considerations

| Area | Issue | Mitigation |
|------|-------|------------|
| `_jobs_per_page * 50` pre-fetch | Controller fetches 600 jobs to compute filter counters, then slices to 12 | For installations with >600 published jobs per website, filter counters will be undercounted. Known trade-off to avoid N+1 queries. |
| `prefetch=False` on `Html` fields | `description` and `website_description` set `prefetch=False` | Avoids loading large HTML content in list views |
| `compute_sudo=True` on `display_name` of `hr.department` | Avoids sudo/switch context on every render | Department names render correctly for anonymous visitors |
| `/job-thank-you` caching | Page explicitly excluded from website page cache | Prevents cross-user data leakage |
| UTM URL computation | `_compute_url` depends on multiple related fields | `@api.depends` ensures automatic recomputation on changes |

---

## Odoo 18 → 19 Migration Changes

| Change | Before (Odoo 18) | After (Odoo 19) | Impact |
|--------|-----------------|-----------------|--------|
| `website_published` tracking | No tracking | `tracking=True` added | Toggling generates mail.message on job record |
| `application_status` field | Used `state` field | Uses `application_status = 'ongoing'` / `'refused'` | These values come from `hr_recruitment` module which added `application_status` in Odoo 18 as a replacement for deprecated `state` field |
| UTM medium auto-creation | Required manual configuration | `_fetch_or_create_utm_medium('website')` auto-creates | No more blank UTM medium if not configured |
| `is_published` / `website_published` separation | Consistent pattern | `website_published` drives `is_published` via onchange | Consistent with other Odoo 18→19 website modules |

---

## Edge Cases

- **No address (remote jobs):** Jobs with `address_id=False` are classified as remote. The `is_remote=True` filter matches these. The template renders "Remote" as the location widget fallback.
- **No department:** `is_other_department=True` matches jobs with no department. These are shown as a separate filter group in the UI.
- **Job closed between page load and submission:** The `website_form_input_filter()` check with `sudo().active` catches this race condition.
- **Spam/duplicate submission:** The `check_recent_application` endpoint prevents most accidental duplicates client-side; the backend creates the record regardless (the warning is advisory, not blocking).
- **Deleted job after application:** Once an `hr.applicant` is created with a `job_id`, deleting the job does not cascade-delete the applicant. The applicant remains in the system with a dangling `job_id` reference.
- **`newid` record in `_compute_website_url`:** The `if not job.id` guard prevents `_slug()` from raising an error when rendering a new (unsaved) job in the form before `is_published` is computed.
- **`published_date` staleness:** When a job is unpublished and later republished, `published_date` retains the original first-publish date and is not updated.

---

## Extension Points

| Hook | Model | Purpose |
|------|-------|---------|
| `website_form_input_filter` | `hr.applicant` | Validate job, assign stage on website submission |
| `_onchange_website_published` | `hr.job` | Sync `is_published` with `website_published` |
| `_compute_website_url` | `hr.job` | Set job page URL `/jobs/{slug}` |
| `_search_get_detail` | `hr.job` | Power website search with faceted filters |
| `action_archive` | `hr.job` | Auto-unpublish on archive |
| `get_suggested_controllers` | `website` | Add Jobs to website footer |
| `_allow_to_use_cache` | `website.page` | Disable caching for thank-you page |

---

## Key File Paths

- `hr.job` extension: `~/odoo/odoo19/odoo/addons/website_hr_recruitment/models/hr_job.py`
- `hr.applicant` extension: `~/odoo/odoo19/odoo/addons/website_hr_recruitment/models/hr_applicant.py`
- `hr.recruitment.source` extension: `~/odoo/odoo19/odoo/addons/website_hr_recruitment/models/hr_recruitment_source.py`
- `website` extension: `~/odoo/odoo19/odoo/addons/website_hr_recruitment/models/website.py`
- Controller: `~/odoo/odoo19/odoo/addons/website_hr_recruitment/controllers/main.py`
- Security: `~/odoo/odoo19/odoo/addons/website_hr_recruitment/security/website_hr_recruitment_security.xml`

---

## Related Documentation

- [Modules/hr_recruitment](Modules/hr_recruitment.md) — Backend recruitment pipeline, applicant management, stages
- [Modules/HR](Modules/HR.md) — Departments, employees, contract types
- [Modules/Website](Modules/Website.md) — Website pages, SEO, multi-website, sitemap
- [Modules/website_mail](Modules/website_mail.md) — Website-aware messaging and portal
- [Core/API](Core/API.md) — @api.depends, @api.onchange, sudo() behavior
- [Patterns/Security Patterns](Patterns/Security-Patterns.md) — ir.rule, ACL CSV, implied groups
