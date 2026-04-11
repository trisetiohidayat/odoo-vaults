---
Module: website_crm
Version: Odoo 18
Type: Integration
Tags: #odoo, #odoo18, #crm, #website, #lead-capture, #utm, #gdpr
---

# website_crm — Website Lead Capture

## Overview

| Property | Value |
|---|---|
| Category | Website/Website |
| Depends | `website`, `crm` |
| Auto-install | `True` (when both deps present) |
| Version | 2.1 |
| License | LGPL-3 |
| Source | `addons/website_crm/` |

**Purpose:** Turns website form submissions (Contact Us, custom forms built in Website Builder) into `crm.lead` records, links them to `website.visitor` sessions, and applies website-specific defaults (team, user, UTM medium). Also surfaces visitor page-view history on the lead form.

---

## Architecture

```
website visitor session
        |
        | (Many2many: lead_ids on visitor, visitor_ids on lead)
        v
crm.lead  <-- created by -->  website form controller
                                  |
                                  | form input filter
                                  v
                            website.crm_default_team_id
                            website.crm_default_user_id
                            utm.medium = "website"
```

The module does **not** extend `crm.lead` with new stored fields. It adds two computed fields (`visitor_ids`, `visitor_page_count`) and a form-input filter hook.

---

## Model Extensions

### `crm.lead` — Extended by `website_crm`

**File:** `models/crm_lead.py`

**Added Fields:**

| Field | Type | Description |
|---|---|---|
| `visitor_ids` | `Many2many('website.visitor')` | All website visitors linked to this lead |
| `visitor_page_count` | `Integer` (computed) | Total page views across all linked visitors |

**Field: `visitor_page_count`**

Computed via raw SQL — joins `crm_lead`, `crm_lead_website_visitor_rel`, `website_visitor`, and `website_track` in a single `GROUP BY` query to avoid N+1 ORM overhead:

```python
def _compute_visitor_page_count(self):
    mapped_data = {}
    if self.ids:
        self.flush_model(['visitor_ids'])
        self.env['website.track'].flush_model(['visitor_id'])
        sql = """ SELECT l.id as lead_id, count(*) as page_view_count
                    FROM crm_lead l
                    JOIN crm_lead_website_visitor_rel lv ON l.id = lv.crm_lead_id
                    JOIN website_visitor v ON v.id = lv.website_visitor_id
                    JOIN website_track p ON p.visitor_id = v.id
                    WHERE l.id in %s
                    GROUP BY l.id"""
        self.env.cr.execute(sql, (tuple(self.ids),))
        page_data = self.env.cr.dictfetchall()
        mapped_data = {data['lead_id']: data['page_view_count'] for data in page_data}
    for lead in self:
        lead.visitor_page_count = mapped_data.get(lead.id, 0)
```

**Key Methods:**

- `action_redirect_to_page_views()` — Opens the website track list for all linked visitors. Heuristic: if > 15 tracked pages across > 1 page, applies `search_default_group_by_page` context to reduce visual noise.
- `website_form_input_filter(request, values)` — Template method called by `WebsiteForm.insert_record()` before creating the lead. Applies website defaults:
  - `medium_id` → UTM medium named `"website"` (auto-created if missing)
  - `team_id` → `request.website.crm_default_team_id`
  - `user_id` → `request.website.crm_default_user_id`
  - `type` → `"lead"` or `"opportunity"` based on team's `use_leads` flag or user group membership
- `_merge_get_fields_specific()` — On lead merge, combines all visitors from all source leads into the target lead's `visitor_ids` via `[(6, 0, leads.visitor_ids.ids)]`.

---

### `website.visitor` — Extended by `website_crm`

**File:** `models/website_visitor.py`

**Added Fields:**

| Field | Type | Description |
|---|---|---|
| `lead_ids` | `Many2many('crm.lead')` | Leads created from this visitor's form submissions |
| `lead_count` | `Integer` (computed) | Count of linked leads |

**Key Methods:**

- `_compute_lead_count()` — Trivial `len(visitor.lead_ids)`.
- `_compute_email_phone()` — **Extends parent.** After the parent compute fills email/mobile from `partner_id`, this override fills remaining gaps from the most recent lead's `email_normalized` / `mobile` / `phone`. Runs only for visitors still missing email or mobile.
- `_check_for_message_composer()` — **Extends parent.** If parent returns False but `lead_ids` exist, sorts leads by confidence level, maps to partner, creates partner assignment if missing, returns `True` so the composer opens on the lead.
- `_inactive_visitors_domain()` — **Extends parent.** Visitors with `lead_ids` are excluded from the inactive-visitor cleanup cron (i.e., they are always considered active and are never auto-deleted).
- `_merge_visitor(target)` — On visitor merge, moves all `lead_ids` from absorbed visitor to the main visitor before calling `super()`.
- `_prepare_message_composer_context()` — **Extends parent.** If visitor has no `partner_id` but has `lead_ids`, returns composer context pointing to the highest-confidence lead and its partner.

**L4 — Visitor Lifetime and Cleanup:**

Visitors linked to leads are **immune to the inactive-visitor cleanup cron** (`_inactive_visitors_domain` adds `('lead_ids', '=', False)` to the domain). This prevents accidental data loss. When two visitors are merged, their leads follow the primary visitor.

---

### `website` — Extended by `website_crm`

**File:** `models/website.py`

**Added Fields:**

| Field | Type | Domain |
|---|---|---|
| `crm_default_team_id` | `Many2one('crm.team')` | Dynamic: `use_leads=True` if user in `crm.group_use_lead`, else `use_opportunities=True` |
| `crm_default_user_id` | `Many2one('res.users')` | `share = False` (internal users only) |

These fields are configured per-website in Website > Configuration > Settings. They drive the `website_form_input_filter` defaults.

---

## Controller: `website_form.py`

### `WebsiteForm` (extends `website.controllers.form.WebsiteForm`)

**`GET /contactus`** — The Contact Us form is rendered by Website Builder. On submit, this controller intercepts.

**`_get_country()` — Phone Formatting Context:**

```
GeoIP country_code → res.country.search
    OR visitor_partner.country_id
    OR request.env.company.country_id
```

Returns the country used to format phone numbers in `E.164 International` format via `phone_validation.phone_format()`.

**`_handle_website_form(model_name, **kwargs)` — Phone + GeoIP State:**

For all `crm.lead` form submissions:
1. Looks up phone number fields via `crm.lead._phone_get_number_fields()` and formats each number using the country from `_get_country()`.
2. If no `state_id` was submitted and GeoIP subdivision is available, auto-populates `state_id` by searching `res.country.state` by `iso_code` + country `code`.

**`insert_record(request, model, values, custom, meta=None)` — Lead Creation + Visitor Linking:**

1. If model is `crm.lead`:
   - Extracts `email_normalized` from `values['email_from']`.
   - Gets or creates the current `website.visitor` via `_get_visitor_from_request(force_create=True)`.
   - **Partner matching:** If the visitor has a `partner_id` AND the email normalized matches the partner's normalized email, writes `partner_id` onto the lead (only if partner phone matches form phone, or form has no phone, or partner has no phone — prevents overwriting existing partner phone with different numbers).
   - Sets `company_id` to the website's company.
   - Sets `lang_id` from the request context.
2. After `super().insert_record()` creates the lead, if the model was `crm.lead` and a visitor exists: links the visitor to the lead via `lead_ids = [(4, result)]`. If the visitor has no leads and no partner, also copies the contact name to the visitor's name.

**L4 — Visitor-to-Lead Matching Flow:**

```
Visitor (with partner_id)
  email_normalized matches form email
    → lead.partner_id = visitor.partner_id
    → lead.linked to visitor
  email_normalized does NOT match
    → lead created without partner_id
    → lead still linked to visitor
```

---

## Views

### Lead Form (Extended)

**View ID:** `crm_lead_view_form` (inherits `crm.crm_lead_view_form`)

Adds a stat button after "Schedule Meeting":

```xml
<button name="action_redirect_to_page_views" type="object"
        class="oe_stat_button" icon="fa-tags"
        invisible="visitor_page_count == 0">
    <field name="visitor_page_count" widget="statinfo" string="Page views"/>
</button>
```

### Visitor Views (Extended)

Four view extensions:

1. **Visitor Form** — Adds "Leads" stat button (same pattern as above) with `lead_count`.
2. **Visitor List** — Adds `lead_count` column after `page_ids`.
3. **Visitor Search** — Adds `filter_type_lead` filter: `[('partner_id', '=', False), ('lead_ids', '!=', False)]`. Modifies `filter_type_visitor` to exclude visitors with leads: `[('partner_id', '=', False), ('lead_ids', '=', False)]`.
4. **Visitor Kanban** — Adds `lead_count` display in the kanban card footer.

### Contact Form Template

**File:** `views/website_templates_contactus.xml`

Standard Website Builder Contact Us form template. The `crm.lead` model is registered with `website_form_access = True` and `website_form_default_field_id = description` so the form can post to it.

---

## Security

**File:** `security/ir.model.access.csv`

| ID | Model | Group | R | W | C | D |
|---|---|---|---|---|---|---|
| `access_website_visitor_salesman` | `website.visitor` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 |
| `access_website_track_salesman` | `website.track` | `sales_team.group_sale_salesman` | 1 | 0 | 0 | 0 |

Salespeople can **read** visitors and tracks linked to their leads but cannot write or delete them.

---

## Website Form Builder Whitelist

**File:** `data/ir_model_data.xml`

The following `crm.lead` fields are whitelisted for Website Builder form creation:

```
contact_name, description, email_from, name, partner_name,
phone, team_id, user_id, lead_properties
```

Fields like `partner_id`, `visitor_ids`, `stage_id`, `probability` are intentionally excluded.

---

## Data Records

**File:** `data/ir_model_data.xml`

`ir.model` record for `crm.lead`:
```python
website_form_key = 'create_lead'
website_form_default_field_id = 'field_crm_lead__description'
website_form_access = True
website_form_label = 'Create an Opportunity'
```

**File:** `data/ir_actions_data.xml`

On module install, opens the Contact Us page via `ir.actions.todo` → `base.open_menu` chain.

**File:** `data/crm_lead_merge_template.xml`

Email template used when a lead is merged (not viewed — standard Odoo merge mechanism).

---

## GDPR / Privacy Notes

The module captures:
- Website visitor email/phone via the contact form → stored on `crm.lead.email_from` / `phone`
- Visitor session data (page views) linked via `visitor_ids` Many2many

**GDPR compliance considerations:**
- `website.visitor` records are subject to the inactive-visitor cleanup cron, but visitors with leads are protected from deletion (see `_inactive_visitors_domain`).
- Form submissions create `crm.lead` records — the standard CRM data retention policies apply.
- No explicit GDPR consent field is added by this module. Consent capture is the responsibility of the website's cookie banner / privacy policy page (handled by `website` base module or custom code).
- Partner matching (`visitor.partner_id` → `lead.partner_id`) can link form submissions to existing contacts — ensure your website's cookie consent logic accounts for this.

---

## Enrichment vs Reveal Distinction

| Feature | Module | Mechanism |
|---|---|---|
| Lead Enrichment (email-based) | `crm_iap_enrich` | Enriches lead with company data from Clearbit-like IAP service using email domain |
| Lead Reveal (website tracking) | `crm_iap_lead_enrich_domain` (website_crm_iap) | Reveals company info when anonymous visitor fills a form (uses visitor IP + domain) |
| Website Lead Capture | `website_crm` | Creates lead from form, links to visitor session |

`website_crm` itself does **not** call any IAP service. It only captures and links. The `reveal_id` field on `crm.lead` (from `iap_crm`) tracks the reveal request.

---

## Key L4 Insights

1. **Visitor lifetime is lead-aware** — The `_inactive_visitors_domain` override ensures visitors tied to leads survive cleanup, preventing orphaned lead-visitor links.
2. **Partner matching is conservative** — Phone number comparison before writing `partner_id` prevents accidentally assigning the wrong partner when the form phone differs from the partner's stored phone.
3. **GeoIP state auto-fill** — If the visitor's IP resolves to a known region, the lead's `state_id` is set automatically, improving lead routing accuracy.
4. **Batching in `insert_record`** — Visitor creation (`force_create=True`) is done once before `super()` call; linking is done after — ensuring the visitor exists even if lead creation fails partially.
5. **No credit consumption** — Unlike `crm_iap_enrich`, this module performs no IAP calls. It is free to use.
6. **Merge safety** — The `_merge_visitor` override on `website.visitor` moves leads to the primary visitor before ORM deletion, preventing orphaned leads.
7. **Recurring revenues group** — The `lead_count` computed field and related UI elements are gated by `sales_team.group_sale_salesman` — external portal users see no CRM visitor data.
