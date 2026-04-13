---
title: website_crm_partner_assign
created: 2026-04-11
updated: 2026-04-11
module: website_crm_partner_assign
tags:
  - #odoo
  - #odoo19
  - #modules
  - #crm
  - #website
  - #geo-localization
  - #partner-assignment
  - #reseller
  - #portal
related_modules:
  - crm
  - base_geolocalize
  - website_partner
  - website_google_map
  - partnership
  - portal
  - account
---

# website_crm_partner_assign

Publish resellers/partners on the website and forward incoming leads to them using geo-localization and partner grade weighting.

## Module Overview

| Property | Value |
|---|---|
| Category | Website/Website |
| Version | 1.2 |
| License | LGPL-3 |
| Author | Odoo S.A. |
| Summary | Publish resellers/partners and forward leads to them |
| Dependencies | `base_geolocalize`, `crm`, `account`, `partnership`, `website_partner`, `website_google_map`, `portal` |

**Core concept**: Partners are assigned a grade/tier with a `partner_weight` that determines assignment probability. Leads are forwarded to nearby partners via a 6-tier geo-escalation algorithm. Partners access assigned leads through the portal to accept or decline them.

---

## Module Dependencies

```
website_crm_partner_assign
├── base_geolocalize          # _geo_localize(), partner_latitude/longitude on res.partner
├── crm                      # crm.lead base model, stages, teams
├── account                  # account.invoice.report for turnover in analytics
├── partnership              # res.partner.grade base model (sequence, name, active)
├── website_partner          # WebsitePartnerPage controller base
├── website_google_map       # GoogleMap controller mixin for partner map
└── portal                   # CustomerPortal, portal user authentication
```

The `partnership` module provides `res.partner.grade` with `sequence`, `name`, `active`, `company_id`, `default_pricelist_id`, `partners_count`. This module extends it with `partner_weight` and `website.published.mixin`.

---

## Model Inventory

### 1. `crm.lead` — CRM Lead / Opportunity (Extended)

Inherits from `crm.lead`. Adds geo-localization fields, partner assignment tracking, and portal write access via explicit method-level ACLs.

#### Fields Added

| Field | Type | Digits | Description |
|---|---|---|---|
| `partner_latitude` | `Float` | `(10, 7)` | Geo latitude of the lead's address (7 decimal places ≈ 1cm precision). |
| `partner_longitude` | `Float` | `(10, 7)` | Geo longitude of the lead's address. |
| `partner_assigned_id` | `Many2one(res.partner)` | — | The partner this lead is forwarded/assigned to. Domain: `[('grade_id','!=',False)]`. `index='btree_not_null'`. `tracking=True`. |
| `partner_declined_ids` | `Many2many(res.partner)` | — | Via `crm_lead_declined_partner`. Partners who have declined — excluded from all future geo searches to prevent assignment loops. |
| `date_partner_assign` | `Date` | — | Last assignment date. Computed: set to today when `partner_assigned_id` is set, cleared otherwise. `store=True`, `copy=True`. |

#### `_compute_date_partner_assign()`

```python
@api.depends("partner_assigned_id")
def _compute_date_partner_assign(self):
    for lead in self:
        if not lead.partner_assigned_id:
            lead.date_partner_assign = False
        else:
            lead.date_partner_assign = fields.Date.context_today(lead)
```

Uses context today for timezone awareness. Triggers on every write to `partner_assigned_id`.

#### `_merge_get_fields()`

Extends the parent CRM lead merge field list:
```python
fields_list += ['partner_latitude', 'partner_longitude', 'partner_assigned_id', 'date_partner_assign']
```
Ensures geo coordinates and assignment data survive lead merging (deduplication).

#### `_prepare_customer_values()`

Copies `partner_latitude`/`partner_longitude` into the new partner when a lead is converted to customer.

#### `_get_partner_email_update(force_void=True)`

Portal users cannot modify the email of a lead if that lead already has a salesman user assigned. Prevents portal users from reassigning leads by changing contact details.

---

### Action Methods

#### `action_assign_partner()`

Entry point for the **Automatic Assignment** button on the CRM form.

```
1. Filter leads WITH country_id  →  assign_partner(partner_id=False)
2. Filter leads WITHOUT country  →  send danger bus notification listing lead names
```

Geo-localization requires a country — without it, `assign_geo_localize()` cannot call `_geo_localize()` because the country name is a required input.

#### `assign_partner(partner_id=False)`

Assignment logic for one or more leads:

```
for each lead:
  if no partner_id given:
    partner_id = search_geo_partner()[lead.id]   # auto-match

  if still no partner_id:
    apply tag "No more partner available"         # tag_portal_lead_partner_unavailable
    continue

  assign_geo_localize(latitude, longitude)       # write lat/lon on lead
  if partner.user_id:
    _handle_salesmen_assignment(user_ids)        # reassign lead's salesman
  write partner_assigned_id = partner_id
```

Uses `random.choices()` in `search_geo_partner()` — the same lead run twice may get different partners if multiple candidates exist at the same weight tier.

#### `assign_geo_localize(latitude=False, longitude=False)`

```
if latitude AND longitude passed directly:
    write both fields on lead, return True

for each lead:
    if already has coordinates: skip
    if has country_id:
        result = res.partner._geo_localize(street, zip, city, state.name, country.name)
        if result: write partner_latitude, partner_longitude
```

Important: does NOT pass context to `browse()` — the country name must be in English for the Google Geocoding API to match correctly. Skips leads without country.

#### `search_geo_partner()` — Six-Tier Geo Algorithm

Returns `{lead.id: partner_id}` dict. Escalates through tiers until a match is found:

| Tier | Name | Latitude Box | Longitude Box | Constraint | Notes |
|---|---|---|---|---|---|
| 1 | Small area | `lat ± 2` | `lon ± 1.5` | Same country, `partner_weight > 0`, not declined | ~200 km radius at equator |
| 2 | Medium area | `lat ± 4` | `lon ± 3` | Same country, `partner_weight > 0`, not declined | ~400 km radius |
| 3 | Large area | `lat ± 8` | `lon ± 8` | Same country, `partner_weight > 0`, not declined | ~800 km radius |
| 4 | Country-wide | No box | No box | All partners in country with `partner_weight > 0` | No geo constraint |
| 5 | Global closest | SQL `<->` | SQL `<->` | Any partner with coordinates, weighted | PostgreSQL point-distance |
| Final | Selection | `random.choices(partner_ids, weights)` | — | One partner | Weighted probability |

**Critical details**:
- SQL for tier 5: `point(partner_longitude, partner_latitude) <-> point(%s, %s)` — note the parameter order is `(longitude, latitude)`.
- Uses `ORDER BY distance LIMIT 1` to find the globally nearest partner.
- `partner_weight = 0` partners are excluded from all tiers.
- `partner_declined_ids` is excluded at every tier via `id NOT IN (SELECT partner_id FROM crm_lead_declined_partner WHERE lead_id = lead.id)`.

**Odoo 18→19 change**: Odoo 18 used `random.choice()` (equal probability). Odoo 19 uses `random.choices(partner_ids.ids, partner_ids.mapped('partner_weight'))` for proper weighted probability selection. Higher-weight partners now receive proportionally more leads.

#### `assign_salesman_of_assigned_partner()`

Reassigns the `user_id` on active leads with probability < 100 that have a different assigned partner's user:

```python
for lead in self:
    if lead.active and lead.probability < 100:
        if lead.partner_assigned_id and lead.partner_assigned_id.user_id != lead.user_id:
            leads_by_salesman[lead.partner_assigned_id.user_id.id].append(lead.id)
for salesman_id, lead_ids in leads_by_salesman.items():
    self.browse(lead_ids).write({'user_id': salesman_id})
```

Does NOT trigger mail notifications for the salesman reassignment (writes directly, no `message_track`). Skips won leads (probability = 100).

---

### Portal Methods (auth="user", website=True)

All portal methods are gated by `_assert_portal_write_access()`:

```python
def _assert_portal_write_access(self):
    if (self.env.user._is_portal() and not self.env.su and
        self != self.filtered_domain([('partner_assigned_id', 'child_of',
            self.env.user.commercial_partner_id.id)])):
        raise AccessError(...)
```

Portal users can only write on leads where their commercial partner is a parent of `partner_assigned_id`. All portal write methods use `sudo()` for the actual write since portal ACL is read-only. The comment in the code explicitly warns: **"DO NOT FORWARD PORT ON MASTER — instead crm.lead should implement portal.mixin"** — indicating a planned future migration.

#### `partner_interested(comment=False)`

Called when a portal partner accepts a lead:
```
1. _assert_portal_write_access()
2. Post message "I am interested by this lead." (with optional comment)
3. sudo().convert_opportunity(lead.partner_id)   # convert to oppty with partner
```

#### `partner_desinterested(comment=False, contacted=False, spam=False)`

Called when a portal partner declines a lead:

| Parameter | Effect |
|---|---|
| `contacted=True` | Message: "I have contacted the lead." |
| `contacted=False` | Message: "I have not contacted the lead." |
| `spam=True` | Apply tag "Spam" (`tag_portal_lead_is_spam`) |
| `partner_declined_ids` | Adds all partners in user's commercial hierarchy |

Sets `partner_assigned_id = False`. Removes the partner hierarchy from the lead's mail followers via `message_unsubscribe`.

#### `update_lead_portal(values)`

Allows portal partners to update: `expected_revenue`, `probability`, `priority`, `date_deadline`. Also manages `mail.activity` records — updates the portal user's own activity if it exists, otherwise creates a new activity assigned to the portal user.

#### `update_contact_details_from_portal(values)`

Writes only these fields: `partner_name`, `phone`, `email_from`, `street`, `street2`, `city`, `zip`, `state_id`, `country_id`. Any other field in `values` raises `UserError`.

#### `update_stage_from_portal(stage_id)`

Allows portal users to advance/change the lead stage. Used in the opportunity portal detail page.

#### `create_opp_portal(values)` — `@api.model`

API entry point for portal-based opportunity creation. Access check requires user or commercial partner to have a `grade_id`:

```python
values = {
    'contact_name': values['contact_name'],
    'name': values['title'],
    'description': values['description'],
    'priority': '2',                        # medium priority
    'partner_assigned_id': user.commercial_partner_id.id,
}
lead = self.sudo().create(values)
lead.assign_salesman_of_assigned_partner()
lead.convert_opportunity(lead.partner_id)
```

Tag `tag_portal_lead_own_opp` ("Created by Partner") identifies self-created opportunities.

#### `_get_access_action(access_uid=None, force_website=False)`

Overrides the standard backend form redirect. For **portal users** or when `force_website=True`, returns an `ir.actions.act_url` redirecting to `/my/opportunity/{id}` instead of the backend form. Falls back to `super()` if the user lacks read access.

#### `_mail_get_operation_for_mail_message_operation(message_operation)`

Grants **readonly** mail access to portal users who are the assigned partner. Without this, posting internal notes would require write access to the lead:

```python
assigned = self.filtered(
    lambda lead: lead.partner_assigned_id == self.env.user.partner_id
) if message_operation == "create" else self.browse()
result = super()._mail_get_operation_for_mail_message_operation(message_operation)
result.update(dict.fromkeys(assigned, 'read'))
return result
```

Only affects "create" message operations; other operations return the standard behavior.

#### `write()` — Portal Many2one Access Check

```python
def write(self, vals):
    if self.env.user._is_portal() and not self.env.su:
        for fname, value in vals.items():
            field = self._fields.get(fname)
            if field and field.type == 'many2one':
                self.env[field.comodel_name].browse(value).check_access('read')
    return super().write(vals)
```

When a portal user modifies a many2one field, the target record must pass a read access check. Non-many2one fields (Char, Integer, Date, etc.) are unrestricted for portal users who pass `_assert_portal_write_access()`.

---

### 2. `res.partner` — Contact / Company (Extended)

#### Fields Added

| Field | Type | Description |
|---|---|---|
| `partner_weight` | `Integer` (computed, `store=True`, `tracking=True`) | `grade_id.partner_weight` or 0 if no grade. Stored for use in SQL geo queries. `readonly=False` — can be manually overridden. |
| `grade_sequence` | `Integer` (related, stored) | `grade_id.sequence`. Used in website partner listing sort. |
| `activation` | `Many2one(res.partner.activation)` | Lifecycle stage. `index='btree_not_null'`. `tracking=True`. |
| `date_partnership` | `Date` | Partnership start date. |
| `date_review` | `Date` | Last partner review date. |
| `date_review_next` | `Date` | Next scheduled review. |
| `assigned_partner_id` | `Many2one(res.partner)` | The partner who implemented this partner. `index='btree_not_null'`. |
| `implemented_partner_ids` | `One2many(res.partner, 'assigned_partner_id')` | Inverse of above. |
| `implemented_partner_count` | `Integer` (computed, `store=True`) | Count of published, active implemented partners. |

#### `_compute_partner_weight()`

```python
@api.depends('grade_id.partner_weight')
def _compute_partner_weight(self):
    for partner in self:
        partner.partner_weight = partner.grade_id.partner_weight if partner.grade_id else 0
```

`readonly=False` means it can be manually overridden on individual partners even after the compute runs. `store=True` ensures the SQL geo queries in `search_geo_partner()` do not need to join `res_partner_grade` — they read the denormalized column directly.

#### `_compute_implemented_partner_count()`

Uses `_read_group` (not a loop over IDs):

```python
rg_result = self.env['res.partner']._read_group(
    [('assigned_partner_id', 'in', self.ids),
     ('is_published', '=', True)],
    ['assigned_partner_id'],
    ['__count'],
)
rg_data = {assigned_partner.id: count for assigned_partner, count in rg_result}
```

Only published partners count toward the sort ranking on the website listing.

#### `_get_contact_opportunities_domain()`

```python
all_partners = self._fetch_children_partners_for_hierarchy().ids
return ['|', ('partner_assigned_id', 'in', all_partners),
        ('partner_id', 'in', all_partners)]
```

Fetches the full contact hierarchy to return all leads where this partner (or any of its child contacts) is either the assigned partner or the customer.

#### `_compute_opportunity_count()` — Override

Replaces the standard count with hierarchy-aware accumulation. Uses `_read_group` then walks up `parent_id` for both `partner_assigned_id` and `partner_id` chains. The `seen_partners` set prevents double-counting when hierarchies overlap.

**Performance**: The hierarchy walk is O(depth) per partner in the result set. For deep hierarchies (5+ levels), this could generate significant Python-level iterations. The warmup test confirms 4 queries for 4 contacts — the standard target.

#### `default_get(fields)` — Override

When context key `partner_set_default_grade_activation` is present (set by the CRM form's `partner_assigned_id` widget), auto-selects the lowest-sequence grade and activation as defaults. This ensures newly created partners are immediately visible in the assignment dropdown:

```python
if 'grade_id' in fields and not default_vals.get('grade_id'):
    default_vals['grade_id'] = self.env['res.partner.grade'].search([], order='sequence', limit=1).id
if 'activation' in fields and not default_vals.get('activation'):
    default_vals['activation'] = self.env['res.partner.activation'].search([], order='sequence', limit=1).id
```

---

### 3. `res.partner.grade` — Partner Tier/Level (Extended from `partnership`)

Inherits from `partnership.res_partner.grade` and `website.published.mixin`.

**Base model fields** (from `partnership`):
- `sequence` (Integer, default=10) — sort order
- `active` (Boolean, default=True)
- `name` (Char, translate=True)
- `company_id` (Many2one)
- `default_pricelist_id` (Many2one)
- `partners_count` (computed via `_read_group`)
- `partners_label` (related to `company_id.partnership_label`)

**Fields added by this module**:

| Field | Type | Default | Description |
|---|---|---|---|
| `partner_weight` | `Integer` | `1` | Assignment probability weight. `0 = never assigned`. |
| `is_published` | Boolean | `True` (via `_default_is_published()`) | Website publishing. Inherited from `website.published.mixin`. |
| `website_url` | Char (computed) | `"/partners/grade/{slug}"` | Grade listing page URL. |

#### `_compute_website_url()`

```python
def _compute_website_url(self):
    super(ResPartnerGrade, self)._compute_website_url()
    for grade in self:
        grade.website_url = "/partners/grade/%s" % (self.env['ir.http']._slug(grade))
```

Overrides the `website.published.mixin` default URL to point to the grade-filtered partners page.

#### Portal ACL

Portal and public users have read-only access to grades where `website_published = True` (via `ir.rule`). Writes require `base.group_user` at minimum.

---

### 4. `res.partner.activation` — Partner Lifecycle Stage (New)

Simple ordered classification model.

| Field | Type | Default | Notes |
|---|---|---|---|
| `sequence` | `Integer` | — | Sort order. Used in `default_get` for lowest-sequence auto-selection. |
| `name` | `Char` (required) | — | Stage name. |
| `active` | `Boolean` | `True` | Supports archiving. |

**Access**: `base.group_user` → read/write; `base.group_partner_manager` → CRUD.

---

### 5. `crm.lead.forward.to.partner` — Lead Forward Wizard (Transient)

Transient model (`_transient_max_hours=1`). Wizard for sending leads to partners via email.

| Field | Type | Description |
|---|---|---|
| `forward_type` | `Selection` | `'single'` (manual pick) or `'assigned'` (geo-auto). Default: context `forward_type` or `'single'`. |
| `partner_id` | `Many2one(res.partner)` | Required when `forward_type == 'single'`. |
| `assignation_lines` | `One2many(crm.lead.assignation)` | Visible when `forward_type == 'assigned'`. |
| `body` | `Html` | Email body, pre-loaded from template `email_template_lead_forward_mail`. |

#### `default_get(fields)`

In **mass_mail mode**: calls `search_geo_partner()` on active leads to pre-fill auto-assignments. In **single mode**: reads each lead's existing `partner_assigned_id` and pre-selects the first lead's partner in the `partner_id` field.

#### `action_forward()`

```python
def action_forward(self):
    # 1. Validate email on all target partners (raises UserError if missing)
    # 2. Group leads by target partner
    # 3. For each partner:
    #    - Check if partner's contacts have portal access
    #    - Send email_template_lead_forward_mail with partner context
    #    - Write partner_assigned_id + user_id on leads
    #    - Subscribe partner to lead's mail thread
```

Uses context `mail_auto_subscribe_no_notify=1` to suppress mail.autosubscribe notifications on the `write()` call.

**Context keys used**:

| Key | Value | Effect |
|---|---|---|
| `default_composition_mode` | `'mass_mail'` | Switches to geo-assignment mode |
| `hide_forward_type` | `True` | Hides the forward type selector (from form view button) |
| `default_partner_ids` | `[partner_assigned_id]` | Pre-populates partner in single mode |
| `mail_auto_subscribe_no_notify` | `1` | Suppresses mail.autosubscribe notifications on `write()` |

---

### 6. `crm.lead.assignation` — Assignation Line (Transient)

One2many child of the forward wizard.

| Field | Type | Notes |
|---|---|---|
| `forward_id` | `Many2one` | Parent wizard. |
| `lead_id` | `Many2one(crm.lead)` | Readonly. |
| `lead_location` | `Char` | `"Country, City"`. |
| `partner_assigned_id` | `Many2one(res.partner)` | User-editable in the wizard. |
| `partner_location` | `Char` | `"Country, City"`. |
| `lead_link` | `Char` | Portal URL `/my/{type}/{id}`. |

`@api.onchange('lead_id')` populates `lead_location`. `@api.onchange('partner_assigned_id')` populates `partner_location`.

---

### 7. `crm.partner.report.assign` — Partnership Analysis Report (Auto=False)

SQL view model. Read-only analytics combining partner data with invoice turnover and lead counts.

| Field | Type | Description |
|---|---|---|
| `partner_id` | `Many2one(res.partner)` | Partner record. |
| `grade_id` | `Many2one(res.partner.grade)` | Partner's grade. |
| `activation` | `Many2one(res.partner.activation)` | Partner's lifecycle stage. |
| `user_id` | `Many2one(res.users)` | Salesperson on the partner record. |
| `date_review` | `Date` | Latest partner review date. |
| `date_partnership` | `Date` | Partnership start date. |
| `country_id` | `Many2one(res.country)` | Inherited from first child contact with a country. |
| `nbr_opportunities` | `Integer` | Count of `crm.lead` records where `partner_assigned_id = this partner`. |
| `turnover` | `Float` | Sum of posted `out_invoice` + `out_refund` amounts from `account.invoice.report`. |
| `date` | `Date` | Invoice date from the joined invoice report. |

#### SQL Query Design

```sql
SELECT
    COALESCE(2 * i.id, 2 * p.id + 1) AS id,   -- unique composite key
    p.id as partner_id,
    (SELECT country_id FROM res_partner a
     WHERE a.parent_id = p.id AND country_id IS NOT NULL LIMIT 1) AS country_id,
    p.grade_id, p.activation, p.date_review, p.date_partnership, p.user_id,
    (SELECT count(id) FROM crm_lead WHERE partner_assigned_id = p.id) AS nbr_opportunities,
    i.price_subtotal AS turnover,
    i.invoice_date AS date
FROM res_partner p
LEFT JOIN (account_invoice_report) i
    ON i.partner_id = p.id
   AND i.move_type IN ('out_invoice', 'out_refund')
   AND i.state = 'posted'
```

**Design decisions**:
- `COALESCE(2*i.id, 2*p.id+1)` ensures unique IDs — all rows share the same model but come from two sources (partner rows and invoice rows). Doubling the IDs prevents collision.
- `country_id` subquery gets the first child contact's country — partners themselves may not have a country set.
- The `nbr_opportunities` is a correlated subquery executed per partner row — O(n) queries. Acceptable for small partner counts.

#### `_depends`

```python
_depends = {
    'account.invoice.report': ['invoice_date', 'partner_id', 'price_subtotal', 'state', 'move_type'],
    'crm.lead': ['partner_assigned_id'],
    'res.partner': ['activation', 'country_id', 'date_partnership', 'date_review',
                    'grade_id', 'parent_id', 'user_id'],
}
```

---

## Controller Routes

### Portal Routes (`auth="user"`, `website=True`)

#### `WebsiteAccount` (extends `CustomerPortal`)

**`/my/leads`** and **`/my/leads/page/<int:page>`**
- Domain: `('partner_assigned_id', 'child_of', user.commercial_partner_id.id), ('type', '=', 'lead')`
- Sort options: `create_date desc` (default), `name`, `contact_name`
- Date range filter supported
- Access check: `CrmLead.has_access('read')` — returns 0 if no read access

**`/my/opportunities`** and **`/my/opportunities/page/<int:page>`**
- Domain: `('partner_assigned_id', 'child_of', user.commercial_partner_id.id), ('type', '=', 'opportunity')`
- Filter options: all / no activities / overdue / today / future / won / lost
- Sort options: create_date, name, contact_name, expected_revenue, probability, stage
- Pager uses `CrmLead.sudo()._search(domain)` to count — bypasses ACL for count but applies domain in the actual search via `('id', 'in', leads_sudo)`

**`/my/lead/<lead>`** — Lead detail page, renders `portal_my_lead`. Returns 404 if `type != 'lead'`.

**`/my/opportunity/<opp>`** — Opportunity detail page. Pre-loads:
- Current user's activity on the lead: `opp.sudo().activity_ids.filtered(lambda a: a.user_id == request.env.user)`
- Available stages (non-won, applicable to lead's team): `crm.stage` with `is_won != True`
- Activity types: `mail.activity.type` records
- Country/state lists for the contact update form

#### `_prepare_home_portal_values(counters)`

Adds `lead_count` and `opp_count` to the portal dashboard. Both use `has_access('read')` to check whether to show a count or 0.

---

### Website Routes (`auth="public"`, `website=True`)

#### `WebsiteCrmPartnerAssign` (extends `WebsitePartnerPage`, `GoogleMap`)

**`/partners`** — Public partner directory with all filters.

**`/partners/grade/<grade>`** — Filter by grade.

**`/partners/country/<country>`** — Filter by country. If no partners exist for that country, sets `fallback_all_countries = True`.

**`/partners/grade/<grade>/country/<country>`** — Combined filter.

**`/partners/<slug>` (detail)** — Individual partner detail page. Checks `website_published` or editor access. Redirects to `/partners/<slug>` if the slug doesn't match the partner's current slug.

#### Sorting

```python
order="grade_sequence ASC, implemented_partner_count DESC, complete_name ASC, id ASC"
```

Better grades (lower sequence number) → more implementations → alphabetical tiebreak.

#### Geo-IP Country Auto-Selection

```python
if not country and not country_all:
    if request.geoip.country_code:
        country = country_obj.search([('code', '=', request.geoip.country_code)], limit=1)
```

If the geo-ip country has no partners, `fallback_all_countries = True` and the country selector is pre-selected to "All Countries".

#### Industry Filter

Partners are filtered by `implemented_partner_ids.industry_id` — shows only partners who have implemented at least one customer in the selected industry. Industry options come from `res.partner.industry` (sudo).

#### `_get_gmap_domains(**kw)`

Extends `website_google_map` to support the `website_crm_partner_assign.partners` map domain, filtering by grade and country. Non-editor users only see published grades.

---

## Security

### Access Control Lists

| ACL | Model | Group | R W C D |
|---|---|---|---|
| `access_crm_partner_report` | `crm.partner.report.assign` | `sales_team.group_sale_salesman` | 1 0 0 0 |
| `access_res_partner_grade_portal` | `res.partner.grade` | `base.group_portal` | 1 0 0 0 |
| `access_res_partner_grade_public` | `res.partner.grade` | `base.group_public` | 1 0 0 0 |
| `access_res_partner_activation_user` | `res.partner.activation` | `base.group_user` | 1 0 0 0 |
| `partner_access_crm_lead` | `crm.lead` | `base.group_portal` | 1 0 0 0 |
| `access_crm_lead_forward_to_partner` | `crm.lead.forward.to.partner` | `sales_team.group_sale_salesman` | 1 1 1 0 |
| `access_crm_lead_assignation` | `crm.lead.assignation` | `sales_team.group_sale_salesman` | 1 1 1 0 |

### IR Rules

| Rule | Model | Groups | Domain |
|---|---|---|---|
| `assigned_lead_portal_rule_1` | `crm.lead` | `base.group_portal` | `('partner_assigned_id', 'child_of', user.commercial_partner_id.id)` — read only |
| `res_partner_grade_rule_portal_public` | `res.partner.grade` | portal + public | `('website_published', '=', True)` — read only |
| `ir_rule_crm_partner_report_assign_all` | `crm.partner.report.assign` | `sales_team.group_sale_salesman_all_leads` | `(1, '=', 1)` — all records |
| `ir_rule_crm_partner_report_assign_salesman` | `crm.partner.report.assign` | `sales_team.group_sale_salesman` | `'|', ('user_id', '=', user.id), ('user_id', '=', False)` |

### Portal Write Gate

All portal write operations use explicit `_assert_portal_write_access()` checks rather than `portal.mixin`. The code comment explicitly warns: **"DO NOT FORWARD PORT ON MASTER — instead crm.lead should implement portal.mixin"** — indicating a planned future migration.

### `sudo()` Usage in Portal Methods

Both `partner_interested()` and `partner_desinterested()` use `sudo()` when writing to the lead. `sudo()` is required because the portal user does not have write access to `crm.lead` — they only have access via the business logic gate. Importantly, `sudo()` does **not** bypass record rules (ir.rules), so security domain filtering is still enforced.

### Website Public Routes

The `/partners` and `/partners/<slug>` routes use `auth="public"` — accessible without login. However, unpublished partners are filtered out for non-editor users:
```python
if not request.env.user.has_group('website.group_website_restricted_editor'):
    domain += [('grade_id.website_published', '=', True)]
```

---

## Tags Used for Lead Lifecycle

| XML ID | Name | Color | Applied When |
|---|---|---|---|
| `website_crm_partner_assign.tag_portal_lead_partner_unavailable` | "No more partner available" | 3 (yellow) | Geo-search found no partner for this lead |
| `website_crm_partner_assign.tag_portal_lead_is_spam` | "Spam" | 3 (yellow) | Partner declined as spam |
| `website_crm_partner_assign.tag_portal_lead_own_opp` | "Created by Partner" | 4 (blue) | Partner creates opportunity via portal |

---

## Performance Considerations

### Geo-Search Loop Complexity

`search_geo_partner()` calls `Partner.search()` up to 5 times per lead (tier escalation). Each search is a separate DB query. For batch assignment of N leads, this generates up to 5N queries. The hot path for large batches should use a single SQL query with window functions to find the nearest partner per lead.

### Degree-to-km Approximation

Methods 1-3 use rectangular bounding boxes (`lat ± n`, `lon ± m`). 1 degree latitude ≈ 111 km. At ±2° latitude: ~444 km. The longitude degree varies with latitude — at 45° it is ~79 km. This is a rough bounding-box search, not a true geodesic circle — partners at corners of the bounding box could be ~300 km away.

### PostgreSQL `<->` Distance Operator

Method 6 uses the cube-based point distance operator: `sqrt((lon2-lon1)^2 + (lat2-lat1)^2)`. This is not geodesic-correct (ignores Earth's curvature), but it is fast and accurate enough for typical business use cases. The ORM does not natively support distance queries — raw SQL is required.

### Report Model Subquery Performance

The `nbr_opportunities` is a correlated subquery executed per partner row — O(n) subqueries where n = number of partners with data. Acceptable for small partner counts; may need review for databases with thousands of partners.

### Portal Pager Security Pattern

```python
leads_sudo = CrmLead.sudo()._search(domain)
domain = [('id', 'in', leads_sudo)]
```

Uses `sudo()._search()` to bypass record rules for the count, then applies `('id', 'in', ...)` as a security domain in the actual search. This is the standard Odoo pattern for portal search with security — two queries per page load, but record rules are still enforced.

### `all_group_ids` Loop in Wizard

For each partner in mass forward, the code iterates over child contacts checking `portal_group.id in [g.id for g in contact.user_ids[0].all_group_ids]`. `all_group_ids` is a cached compute — this is fast, but the loop over partner contacts could add up for large partner networks.

---

## Odoo 18 to 19 Changes

| Area | Odoo 18 | Odoo 19 | Impact |
|---|---|---|---|
| Partner selection | `random.choice()` — equal probability | `random.choices(weights=partner_weight)` — weighted | Higher-weight partners receive more leads |
| `portal.mixin` | Available but not used | Still manual `_assert_portal_write_access()` | Planned migration noted in code comment |
| View XML | `<tree>` element | `<list>` element | Cosmetic XML update |
| `http.route` | — | `readonly=True` attribute on sitemap route | No functional change |
| SQL construction | String interpolation | `SQL` object in `_table_query` | Parameterized, safe |
| `Domain.OR()` | Classic tuple domains | `Domain.OR()` in `_get_partners_values` | Modern ORM API |
| Lead portal redirect | `_get_access_action()` | Same (still manual) | No change |

The most meaningful behavioral change is the weighted random selection — it was introduced in Odoo 19 and changes the load-distribution across partners.

---

## Edge Cases

1. **Lead without country**: `action_assign_partner()` separates these and sends a bus notification. They never reach geo-localization.

2. **All partners declined**: After all partners in range are in `partner_declined_ids`, all 5 search tiers return empty, then tier 6 (global closest) is attempted. If still empty, the "No more partner available" tag is applied.

3. **Partner with no `grade_id`**: `partner_weight = 0`. Excluded from all geo search tiers. The `partner_assigned_id` domain also excludes them.

4. **Partner with no `user_id`**: `assign_partner()` checks `if partner.user_id:` before calling `_handle_salesmen_assignment()`. The lead keeps its existing `user_id`.

5. **Multi-company**: `partner_assigned_id` domain: `[('company_id', '=', False), ('company_id', '=', company_id)]`. Leads can only be assigned to partners in the same company or those with no company.

6. **Merged leads**: All geo and assignment fields are included in the merge field list.

7. **Portal without grade**: `create_opp_portal()` raises `AccessDenied()` if neither the portal user nor their commercial partner has a `grade_id`.

8. **Deep hierarchy traversal**: `_compute_opportunity_count()` walks up `parent_id` chains for both `partner_id` and `partner_assigned_id`. In organizations with deep hierarchies (5+ levels), this could generate significant Python-level iterations per partner in the portal dashboard.

9. **Portal URL sharing**: An assigned partner could share the `/my/opportunity/<id>` URL with unauthorized users. The `_get_access_action()` method checks `user.share` and `access_uid` — if the accessing user is not the portal user, standard form view access rules apply.

---

## Views

### CRM Lead Form View — "Assigned Partner" Page

Inherits `crm.crm_lead_view_form`. Adds a new notebook page (positioned after all existing pages):

```
Assigned Partner
├── Geolocation: [latitude] N/S [longitude] E/W
├── Assigned Partner: [Many2one domain: grade_id != False]
│   └── Context: {'partner_set_default_grade_activation': 1}
├── [Automatic Assignment] button → action_assign_partner()
└── [Send Email] button (visible when partner_assigned_id set)
    └── Opens crm_lead_forward_to_partner_act in single mode
```

The context on the Many2one widget auto-selects the lowest-grade partner when creating a new partner from the form.

### CRM Lead All Views

All analysis views (pivot, graph, forecast) add `partner_latitude` and `partner_longitude` as **invisible** fields to preserve them in the view's data scope.

### Partner Form View

Inherits `base_geolocalize.view_crm_partner_geo_form` (the partner geo tab). Adds above the geo location tab:

```
Partner Activation          Partner Review
├─ activation               ├─ date_review
├─ partner_weight           ├─ date_review_next
                            └─ date_partnership
```

Also adds `assigned_partner_id` (only visible to `base.group_no_one`).

### Partner Grade Form View

Inherits `partnership.view_partner_grade_form`. Adds the `partner_weight` field and the `website_redirect_button` for `is_published`.

---

## File Structure

```
website_crm_partner_assign/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py                 # WebsiteAccount + WebsiteCrmPartnerAssign
├── models/
│   ├── __init__.py
│   ├── crm_lead.py             # Geo-assignment, portal methods
│   ├── res_partner.py          # Partner weight, activation, hierarchy
│   ├── res_partner_activation.py
│   ├── res_partner_grade.py    # Weight + website.published.mixin
│   └── website.py              # get_suggested_controllers override
├── report/
│   ├── __init__.py
│   ├── crm_partner_report.py   # Auto=False SQL report
│   └── crm_partner_report_view.xml
├── wizard/
│   ├── __init__.py
│   ├── crm_forward_to_partner.py
│   └── crm_forward_to_partner_view.xml
├── views/
│   ├── crm_lead_views.xml
│   ├── res_partner_views.xml
│   ├── res_partner_grade_views.xml
│   ├── res_partner_activation_views.xml
│   ├── website_crm_partner_assign_templates.xml
│   └── partner_assign_menus.xml
├── security/
│   ├── ir.model.access.csv
│   └── ir_rule.xml
└── data/
    ├── crm_lead_merge_template.xml     # Lead merge summary override
    ├── crm_tag_data.xml                # 3 CRM tags
    ├── mail_template_data.xml          # email_template_lead_forward_mail
    ├── res_partner_activation_data.xml
    ├── res_partner_demo.xml
    ├── crm_lead_demo.xml
    └── res_partner_grade_demo.xml      # Publishes default grades from partnership
```

---

## Related

- [Modules/CRM](modules/crm.md) — CRM module
- [Modules/website_partner](modules/website_partner.md) — Partner page base
- [Modules/website_google_map](modules/website_google_map.md) — Google Maps on website
- [Modules/partnership](modules/partnership.md) — Partnership management (res.partner.grade base)
- [Modules/portal](modules/portal.md) — Customer portal authentication
- [Modules/base_geolocalize](modules/base_geolocalize.md) — Google Geocoding service (`_geo_localize()`)
- [Modules/website_crm](modules/website_crm.md) — Website CRM lead capture
- [Modules/website_crm_iap_reveal](modules/website_crm_iap_reveal.md) — IP-based lead generation from website visits
