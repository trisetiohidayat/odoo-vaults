---
tags:
  - odoo
  - odoo19
  - website
  - crm
  - lead
  - opportunity
  - contact-form
  - visitor
  - utm
created: 2026-04-06
updated: 2026-04-11
---

# website_crm

## Overview

| Property | Value |
|----------|-------|
| **Name** | Website CRM |
| **Technical** | `website_crm` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Module Path** | `~/odoo/odoo19/odoo/addons/website_crm/` |
| **Version** | `2.1` |
| **Category** | Website / Website |
| **Auto-install** | `True` |
| **Sequence** | 54 |

**Dependencies:** `website`, `crm`

**Description** (from manifest):
> Add capability to your website forms to generate leads or opportunities in the CRM app. Forms have to be customized inside the *Website Builder* in order to generate leads. This module includes contact phone and mobile numbers validation.

### Manifest Data Entries

| File | Purpose |
|------|---------|
| `security/ir.model.access.csv` | Read-only ACLs for `website.visitor` and `website.track` for `sales_team.group_sale_salesman` |
| `data/crm_lead_merge_template.xml` | Extends lead merge summary template to display `visitor_ids` |
| `data/ir_actions_data.xml` | Creates `ir.actions.act_url` to `/contactus` + startup todo action |
| `data/ir_model_data.xml` | Registers `crm.lead` in form builder with field whitelist |
| `views/crm_lead_views.xml` | Page views stat button on lead form |
| `views/website_visitor_views.xml` | Leads stat button + search filter + kanban block on visitor views |
| `views/website_templates_contactus.xml` | Pre-fills contact form fields from `request.params` on re-render |

### Form Builder Field Whitelist (ir_model_data.xml)

The `crm.lead` model is registered with `website_form_key = 'create_lead'` and the following fields are whitelisted for website form builder use:

| Field | Form Editor Type | Required (Editor) | Fill-with Preset |
|-------|-----------------|-------------------|-----------------|
| `contact_name` | `char` | Yes | `name` (user's name) |
| `phone` | `tel` | No | `phone` |
| `email_from` | `email` | Yes | `email` |
| `partner_name` | `char` | Yes | `commercial_company_name` |
| `name` | `char` | Yes (modelRequired) | — |
| `description` | `text` | Yes | — |
| `team_id` | `many2one` | No | — |
| `user_id` | `many2one` | No | — |
| `lead_properties` | `properties` | No | — |

The `modelRequired: True` on `name` makes it required for the lead form type specifically, without modifying the base model's field definition. The `domain` for `team_id` in the form editor is ``'use_opportunities', '=', True`` (not checking `use_leads` — the form editor action is typically used in opportunity-mode contexts). The `user_id` domain restricts to internal users only (`share = False`).

## Architecture

```
Website Visitor Journey
=====================

Anonymous Visitor
      │
      ├── Visits website pages
      │      └── website.track records created
      │
      └── Submits Contact Us form (/crm/lead/create)
                │
                ├── UTM parameters captured (source, medium, campaign)
                ├── website_crm.website_form_input_filter()
                │     ├── Auto-set medium_id from website
                │     ├── Auto-set team_id from website config
                │     ├── Auto-set user_id from website config
                │     └── Determine lead vs opportunity type
                │
                └── website_crm.controller.insert_record()
                      │
                      ├── Link to existing visitor (email match)
                      ├── Create/update website.visitor with lead_ids
                      └── Create crm.lead with visitor_ids

CRM User View
─────────────

crm.lead (with visitor_ids)
      │
      ├── visitor_page_count computed from website_track JOINs
      ├── action_redirect_to_page_views() → website.visitor page history
      ├── Lead merge → all visitor_ids combined
      └── website_hr_recruitment: visitor linked to applicant
```

---

## Models

### crm.lead (Extended)

**File:** `models/crm_lead.py`

Extends `crm.lead` with visitor tracking, page view analytics, and website-aware defaults.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `visitor_ids` | Many2many `website.visitor` | Web visitors who submitted this lead |
| `visitor_page_count` | Integer (computed) | Total page views across all linked visitors |

#### `visitor_page_count` Computation (line 13-30)

```python
@api.depends('visitor_ids.page_ids')
def _compute_visitor_page_count(self):
    mapped_data = {}
    if self.ids:
        self.flush_model(['visitor_ids'])
        self.env['website.track'].flush_model(['visitor_id'])
        sql = """ SELECT l.id as lead_id, count(*) as page_view_count
                    FROM crm_lead l
                    JOIN crm_lead_website_visitor_rel lv
                      ON l.id = lv.crm_lead_id
                    JOIN website_visitor v ON v.id = lv.website_visitor_id
                    JOIN website_track p ON p.visitor_id = v.id
                    WHERE l.id in %s
                    GROUP BY l.id"""
        self.env.cr.execute(sql, (tuple(self.ids),))
        page_data = self.env.cr.dictfetchall()
        mapped_data = {data['lead_id']: data['page_view_count']
                       for data in page_data}
    for lead in self:
        lead.visitor_page_count = mapped_data.get(lead.id, 0)
```

Uses a **direct SQL JOIN** for performance (avoids N+1 across the many2many + page chain). Computed on demand when `visitor_ids` changes.

#### Action Methods

**`action_redirect_to_page_views()`** (line 32-39):
```python
def action_redirect_to_page_views(self):
    visitors = self.visitor_ids
    action = self.env["ir.actions.actions"]._for_xml_id(
        "website.website_visitor_page_action"
    )
    action['domain'] = [('visitor_id', 'in', visitors.ids)]
    if (len(visitors.website_track_ids) > 15
            and len(visitors.website_track_ids.page_id) > 1):
        action['context'] = {'search_default_group_by_page': '1'}
    return action
```
Opens the website visitor page tracking view filtered to the lead's visitors. Enables **group by page** when the visitor has significant browsing history.

#### Merge Override

**`_merge_get_fields_specific()`** (line 41-45):
```python
def _merge_get_fields_specific(self):
    fields_info = super()._merge_get_fields_specific()
    fields_info['visitor_ids'] = lambda fname, leads: [
        (6, 0, leads.visitor_ids.ids)
    ]
    return fields_info
```
When leads are merged, **all visitor records from all leads are combined** into the resulting lead.

#### Form Input Filter

**`website_form_input_filter()`** (line 47-62):

Called by `website.form` controller when processing contact form submissions. Auto-populates UTM and assignment fields:

```python
def website_form_input_filter(self, request, values):
    # Auto-set medium from website (website is the implied medium)
    values['medium_id'] = values.get('medium_id') or \
        self.sudo().default_get(['medium_id']).get('medium_id') or \
        self.env['utm.medium']._fetch_or_create_utm_medium('website').id

    # Auto-set team and user from website config
    values['team_id'] = values.get('team_id') or \
        request.website.crm_default_team_id.id
    values['user_id'] = values.get('user_id') or \
        request.website.crm_default_user_id.id

    # Fallback: if team has a user, assign that user
    if not values['user_id'] and values['team_id'] \
            and not self._is_rule_based_assignment_activated():
        values['user_id'] = self.env['crm.team'].sudo().browse(
            values['team_id']).user_id.id

    # Determine type: lead vs opportunity based on team config
    if values.get('team_id'):
        values['type'] = 'lead' if self.env['crm.team'].sudo().browse(
            values['team_id']).use_leads else 'opportunity'
    else:
        values['type'] = 'lead' if self.env.user.has_group(
            'crm.group_use_lead') else 'opportunity'
    return values
```

Key behaviors:
- **`medium_id`**: Created/fetched from `utm.medium` with name `'website'` — ensures all website leads share the same medium
- **`team_id`**: Pulled from `website.crm_default_team_id` (set in Website Settings)
- **`user_id`**: Pulled from `website.crm_default_user_id` OR falls back to the team's default user
- **`type`**: Respects the team's `use_leads` setting vs the user's personal CRM preferences

---

### website.visitor (Extended)

**File:** `models/website_visitor.py`

Extends `website.visitor` to add the **reverse** many2many to `crm.lead`.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `lead_ids` | Many2many `crm.lead` (added via `crm_lead_view_form` XML) | Leads created from this visitor |

---

### website (Extended)

**File:** `models/website.py`

Adds CRM configuration fields to the website model.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `crm_default_team_id` | Many2one `crm.team` | Default team for website-generated leads |
| `crm_default_user_id` | Many2one `res.users` | Default salesperson for website-generated leads |

#### `_get_crm_default_team_domain()` (line 10-13):

```python
def _get_crm_default_team_domain(self):
    if not self.env.user.has_group('crm.group_use_lead'):
        return [('use_opportunities', '=', True)]
    return [('use_leads', '=', True)]
```
Restricts the team dropdown to teams that match the current user's lead/opportunity mode preference.

---

## Controller

### WebsiteForm (website_crm Controller)

**File:** `controllers/website_form.py`

Inherits `website.controllers.form.WebsiteForm` to add CRM-specific handling during contact form submission.

#### `_get_country()` (line 11-21):

Returns the country for phone number formatting based on visitor data:
1. If visitor has a partner with a country → use partner's country
2. Otherwise, try GeoIP country from request
3. Return empty country record if nothing found

Used by `_handle_website_form()` for phone number internationalization.

#### `_handle_website_form()` (line 24-56):

Phone number normalization and GeoIP state assignment:

```python
def _handle_website_form(self, model_name, **kwargs):
    model_record = request.env['ir.model'].sudo().search([
        ('model', '=', model_name),
        ('website_form_access', '=', True)
    ])
    if model_record:
        try:
            data = self.extract_data(model_record, request.params)
        except:
            pass
        else:
            # Phone number formatting
            record = data.get('record', {})
            phone_fields = request.env[model_name]._phone_get_number_fields()
            country = request.env['res.country'].browse(
                record.get('country_id'))
            contact_country = country if country.exists() \
                else self._get_country()
            for phone_field in phone_fields:
                if not record.get(phone_field):
                    continue
                fmt_number = phone_validation.phone_format(
                    record[phone_field],
                    contact_country.code,
                    contact_country.phone_code,
                    force_format='INTERNATIONAL',
                )
                request.params.update({phone_field: fmt_number})

    # GeoIP state detection for crm.lead
    if model_name == 'crm.lead' and not request.params.get('state_id'):
        geoip_country_code = request.geoip.country_code
        geoip_state_code = request.geoip.subdivisions[0].iso_code \
            if request.geoip.subdivisions else None
        if geoip_country_code and geoip_state_code:
            state = request.env['res.country.state'].search([
                ('code', '=', geoip_state_code),
                ('country_id.code', '=', geoip_country_code)
            ])
            if state:
                request.params['state_id'] = state.id
    return super()._handle_website_form(model_name, **kwargs)
```

Features:
- Phone numbers on leads are auto-formatted to international format using the contact's or visitor's country
- State is auto-detected from GeoIP for leads without a state

#### `insert_record()` (line 58-91):

The key method — creates the CRM lead and links it to the website visitor:

```python
def insert_record(self, request, model_sudo, values, custom, meta=None):
    is_lead_model = model_sudo.model == 'crm.lead'
    if is_lead_model:
        values_email_normalized = tools.email_normalize(
            values.get('email_from'))
        visitor_sudo = request.env['website.visitor']._get_visitor_from_request(
            force_create=True)
        visitor_partner = visitor_sudo.partner_id

        # Smart partner linking: only link if email matches
        if values_email_normalized and visitor_partner \
                and visitor_partner.email_normalized == values_email_normalized:
            values_phone = values.get('phone')
            # Link partner if: no phone conflict, or phones match after formatting
            if values_phone and visitor_partner.phone:
                if values_phone == visitor_partner.phone:
                    values['partner_id'] = visitor_partner.id
                elif (visitor_partner._phone_format('phone')
                      or visitor_partner.phone) == values_phone:
                    values['partner_id'] = visitor_partner.id
            else:
                values['partner_id'] = visitor_partner.id

        # Set company and language from website context
        if 'company_id' not in values:
            values['company_id'] = request.website.company_id.id
        lang = request.env.context.get('lang', False)
        values['lang_id'] = values.get('lang_id') \
            or request.env['res.lang']._get_data(code=lang).id

    result = super().insert_record(...)

    # Link visitor to newly created lead
    if is_lead_model and visitor_sudo and result:
        lead_sudo = request.env['crm.lead'].browse(result).sudo()
        if lead_sudo.exists():
            vals = {'lead_ids': [(4, result)]}
            # Name the visitor after the contact if it has no name yet
            if not visitor_sudo.lead_ids \
                    and not visitor_sudo.partner_id:
                vals['name'] = lead_sudo.contact_name
            visitor_sudo.write(vals)
    return result
```

**Partner linking logic**:
- Only links the visitor's partner to the lead if the **email matches exactly** (normalized)
- Phone is used as a secondary confirmation signal: if both have phones and they match (or format to match), link them
- This prevents linking a visitor's partner account to a lead from a different person who happens to share the same device

**Visitor naming**: If the visitor has no name and no linked partner, the visitor's name is set to the lead's contact name.

---

## Views

### CRM Lead Form Extension

**File:** `views/crm_lead_views.xml`

Adds a **"Page views" stat button** to the lead form (visible only if `visitor_page_count > 0`):

```xml
<button name="action_redirect_to_page_views" type="object"
        class="oe_stat_button" icon="fa-eye"
        invisible="visitor_page_count == 0">
    <field name="visitor_page_count" widget="statinfo"
           string="Page views"/>
</button>
```

### Visitor Action from Lead

The visitor form view gains a **"Leads"** smart button via `crm_lead_action_from_visitor`, showing all leads linked to that visitor.

---

## End-to-End Lead Capture Flow

```
1. Anonymous visitor browses website
      │
      └── website.track records created per page view
           └── linked to website.visitor

2. Visitor submits Contact Us form (website_contactus or /crm/lead/create)
      │
      └── website_crm.website_form_input_filter()
           ├── medium_id = 'website' (created if not exists)
           ├── team_id = website.crm_default_team_id
           ├── user_id = website.crm_default_user_id OR team.user_id
           └── type = lead/opportunity based on team.use_leads
                │
      website_crm.controller._handle_website_form()
           ├── Phone numbers formatted internationally
           └── state_id auto-detected from GeoIP
                │
      website_crm.controller.insert_record()
           ├── Partner linked if email matches visitor's partner
           ├── company_id = website.company_id
           ├── lang_id = visitor's language
           └── crm.lead record created
                │
      Post-create: visitor_sudo.lead_ids → link visitor to lead
           │
3. Sales sees lead in CRM with:
      ├── visitor_ids linked
      ├── visitor_page_count showing total browsing activity
      └── action to view all page history
```

---

## Key Design Decisions

### Why Email Matching for Partner Linking?

Linking the visitor's partner to the lead only on email match prevents a visitor's partner account from being incorrectly linked to a different person's lead (e.g., family sharing a device). Phone numbers serve as a secondary confirmation.

### Why Direct SQL for Page Count?

The `visitor_page_count` uses direct SQL JOINs across `crm_lead` → `crm_lead_website_visitor_rel` → `website_visitor` → `website_track` because the ORM path through `visitor_ids.page_ids` causes severe N+1 on list views with many leads.

### Why website.medium?

All website-generated leads share `medium_id = 'website'` to distinguish them from organic, referral, or direct leads in UTM reporting. This is created automatically via `_fetch_or_create_utm_medium('website')`.

---

## Extension Points

### Custom Website Lead Assignment
Override `website_form_input_filter()` to add custom assignment logic based on form data, visitor characteristics, or A/B test variations.

### Pre-insert Lead Processing
Override `insert_record()` before the `super()` call to modify lead values, add tags, or trigger custom workflows before the record is created.

### Visitor Naming Strategy
Override the visitor naming logic in `insert_record()` to use company name or other fields as the visitor name.

---

## L4: Cross-Model Relationships and Override Patterns

### Visitor-to-Lead Linkage Model

The bidirectional `Many2many` link between `website.visitor` and `crm.lead` is implemented as:

- `crm.lead.visitor_ids`: Many2many → `website.visitor` (defined in `models/crm_lead.py`)
- `website.visitor.lead_ids`: Many2many → `crm.lead` (defined in `views/website_visitor_views.xml` as the inverse)

Both sides share the auto-generated relation table `crm_lead_website_visitor_rel`. The relationship is created at two points:

1. **On lead creation** — `insert_record()` writes `lead_ids = [(4, lead_id)]` on the visitor after the lead is inserted.
2. **On visitor merge** — `_merge_visitor()` copies all leads from the absorbed visitor to the target before the visitor is deactivated.

### `_compute_email_phone()` Override Pattern

This is a chained super-call pattern. The parent `website.visitor` computes `email` and `mobile` from `partner_id`. The website_crm override runs `super()` first (fills from partner), then conditionally fills remaining gaps from linked leads. The pattern is idempotent — calling it multiple times produces the same result.

The visitor's `email` and `mobile` fields are **not** stored on `crm.lead` — they are always computed on the visitor record by joining through `lead_ids`. This means a lead's contact phone is stored on `crm.lead.phone`, but the visitor record's `mobile` may also reflect it.

### `_inactive_visitors_domain()` Pattern

Uses the `Domain` class (Odoo 16+, replacing the old tuples-as-domain syntax) for a clean, type-checked domain expression. The `Domain` object supports `&` (AND) and `|` (OR) operators for composing domains. The resulting domain is `['partner_id', '=', False]` AND `['lead_ids', '=', False]`, meaning visitors that have a partner or any linked lead are always exempt from the visitor cleanup cron.

### Lead Merge Field Propagation

`_merge_get_fields_specific()` returns a `dict` mapping field names to merge-resolution callables. The lambda `(6, 0, leads.visitor_ids.ids)` uses the ORM's `[(6, 0, ids)]` command to replace all linked visitors with the combined set from all merged leads. This runs inside the lead merge process which itself is wrapped in a `sudo()` context.

---

## L4: Failure Modes and Error Handling

### Visitor Creation Without a Partner

`_get_visitor_from_request(force_create=True)` may create a visitor record even for non-browser clients (crawlers, scripts). These ghost visitors have no `partner_id`. The visitor naming logic guards against this: `if not visitor_sudo.lead_ids and not visitor_sudo.partner_id` — if the visitor already has leads or a partner, the visitor's name is not overwritten. This prevents a second lead submission from accidentally overwriting the visitor's name.

### Phone Formatting Failures

`phone_format()` is called with `raise_exception=False`. Malformed numbers (non-numeric characters, incomplete numbers) are returned unchanged rather than raising. This prevents a bot or script submission with a bogus phone number from causing a 500 error on the form.

The `.exists()` check on `country` before calling `phone_format` prevents a crash if the form's `country_id` points to a deleted country record.

### Lead Post-Create Cleanup Guard

After `super().insert_record()` creates the lead, the code calls `lead_sudo.exists()` before linking. This handles the case where a `on_change` or `after_create` workflow hook in a custom module or studio extension deletes or archives the lead immediately after creation. The linking step silently skips in this case — the lead exists in the database but without a visitor link.

### GeoIP State Lookup Edge Cases

The GeoIP state detection uses `request.geoip.subdivisions[0]` — the first subdivision in MaxMind's data. This works for countries with a simple administrative hierarchy but may select the wrong state for countries with complex or multi-level subdivision structures (e.g., countries with states containing territories). If MaxMind data is unavailable or `request.geoip` raises an attribute error (no geoip data), the subdivision lookup silently fails with no state assigned.

### Visitor Cleanup Cron Interaction

Visitors with leads are excluded from the inactive visitor cleanup (via `_inactive_visitors_domain()`). However, if a lead is deleted (not archived, but truly deleted via `unlink()`), the visitor will no longer be protected. The cleanup cron runs on a schedule — if leads are frequently deleted rather than archived, there is a window where a visitor without visible leads could be cleaned up. For typical CRM usage, leads are archived, not deleted, so this is not a practical concern.

### Lead Type Mismatch

If `crm_default_team_id` on a website points to a team where `use_leads = False` but the current user has `crm.group_use_lead`, there is a conflict: the UI dropdown in website settings filters by the current user's preference (`_get_crm_default_team_domain()`), but a backend script writing `crm_default_team_id` directly could write a team that doesn't match. The `website_form_input_filter()` method checks `use_leads` on the actual written team value, so leads will still be created as opportunities in this case. The website setting UI just won't show the mismatched team.

---

## L4: Performance Implications

### `visitor_page_count` SQL vs ORM Computation

The raw SQL for `visitor_page_count` is intentionally direct. An ORM equivalent would be:

```python
# Slow ORM approach (N+1)
for lead in self:
    lead.visitor_page_count = sum(
        v.website_track_ids.search_count([('visitor_id', '=', v.id)])
        for v in lead.visitor_ids
    )
```

The SQL JOIN path traverses `crm_lead → crm_lead_website_visitor_rel → website_visitor → website_track` in a single query with a `GROUP BY`. For a list of 100 leads, this executes 1 query instead of ~100 ORM queries.

The explicit `flush_model()` calls are required because the raw SQL sees the database state directly — without flushing, a newly created visitor link in the current transaction's ORM cache would not be visible to the SQL query.

### Visitor Query Count

The test class `TestWebsiteVisitor` is tagged `is_query_count` indicating it is used for regression testing of query counts. The `_compute_email_phone()` method loops over visitors and leads, but each visitor is processed independently and only for the subset where `partner_id` data is missing. In high-volume scenarios (many anonymous visitors with leads but no partner), this compute could degrade.

### Auto-Install Resolution Overhead

Because `website_crm` is `auto_install: True` with `depends: ['website', 'crm']`, the Odoo module loader must resolve the dependency graph to confirm both dependencies are present before auto-installing. In a fresh install with just `website` and no CRM, `website_crm` will not install. Once `crm` is added, `website_crm` is auto-installed without manual intervention. This is standard Odoo auto-install behavior and carries no meaningful performance overhead.

---

## L4: Security Considerations

### ACL Narrowing for Salespeople

The `ir.model.access.csv` intentionally grants **only read access** to `website.visitor` and `website.track` for `sales_team.group_sale_salesman`. Write and create access is withheld because visitor records are managed by the website system — salespeople should view visitor context for lead intelligence but not modify visitor data. This prevents a salesperson from, for example, clearing a visitor's browsing history or changing the visitor's identity.

### Partner Linking Attack Prevention

The partner auto-link logic in `insert_record()` requires an **email match between the submitted form data and the logged-in session's partner**. This means:
- A portal user cannot inject a different customer's partner_id by submitting the contact form with someone else's email.
- The `values_email_normalized == visitor_partner.email_normalized` check is case-insensitive and strips whitespace.
- Phone-based confirmation is additive — it makes linking more likely when both are present, but the email match is always required.

### Sudoed Operations

Several operations run in `sudo()`:
- `_fetch_or_create_utm_medium('website')` — runs as sudo because the UTM medium may need to be created and the current user may not have create permissions on `utm.medium`.
- `visitor_sudo` operations — the visitor is created/read in sudo to bypass website access restrictions on visitor records.
- `lead_sudo.browse(result).sudo()` — reads the created lead in sudo to link it back to the visitor without triggering record rule restrictions.

The `website_form_input_filter()` also calls `self.sudo()` for `default_get()` on `medium_id`. This is safe because the method only reads default values, never writes data in sudo context.

### Record Rules on `crm.lead`

`website_crm` does not add any record rules. All lead security is governed by `crm` module rules — typically `['|', ('user_id', '=', user.id), ('team_id.member_ids', '=', user.id)]` plus team manager access. Visitors linked to a lead do not gain any CRM access through that link.

---

## L3: Odoo 18 → 19 Historical Changes

---

## L3: Odoo 18 → 19 Historical Changes

### No Breaking API Changes
The module's public interface is stable between Odoo 18 and 19. The following refinements were made:

| Change | Detail |
|--------|--------|
| `flush_model()` calls added before raw SQL | Ensures ORM cache consistency in batch recomputation contexts |
| `lead_properties` added to form builder whitelist | Aligns with Odoo 18 → 19 Json/properties field expansion |
| `_is_rule_based_assignment_activated()` check in `website_form_input_filter()` | Adapts to CRM's rule-based assignment feature (newer versions) |
| `filter_type_lead` visitor search filter added | Better segmentation for anonymous visitors with leads |
| `crm_lead_merge_summary` template extended with visitor display | Merge confirmation UI now shows linked visitors |
| `Domain` class (not tuple syntax) in `_inactive_visitors_domain()` | Aligns with Odoo 16+ domain expression modernization |

### Version History
The module's version string is `'2.1'`. Version 2.0 likely corresponds to the addition of rule-based assignment compatibility and partner link improvements. Version 2.1 adds `lead_properties` support.

---

## Related

- [Modules/website](website.md) — Website framework, visitor tracking, page views
- [Modules/crm](CRM.md) — CRM base module, lead/opportunity model
- [Modules/website_hr_recruitment](website_hr_recruitment.md) — Job applications from website linked to visitors
- [Modules/utm](utm.md) — UTM source, medium, campaign tracking
- [Modules/website_crm_livechat](website_crm_livechat.md) — Live chat lead capture
- [Modules/website_crm_partner_assign](website_crm_partner_assign.md) — Partner geo-localization and lead assignment
- [Modules/survey_crm](survey_crm.md) — Survey-generated leads
