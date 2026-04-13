---
title: website_customer
category: website
tags: [odoo19, website, crm, partner, references, customer-directory]
description: Publishes assigned/graded partners as customer references on the public website with filtering, search, and a per-customer detail page.
dependencies:
  - website_partner
  - website_crm_partner_assign
  - website_google_map
---

# website_customer

> **Customer References** — Publish your customers as business references on your website to attract new prospects.

| Property       | Value                         |
|----------------|-------------------------------|
| Category       | Website / Website             |
| Version        | 1.0                           |
| Depends        | `website_crm_partner_assign`, `website_partner`, `website_google_map` |
| Author         | Odoo S.A.                     |
| License        | LGPL-3                        |
| Models         | `res.partner` (extend), `res.partner.tag` (new) |

---

## Module Philosophy

`website_customer` is a **thin orchestration layer**. It does not define its own CRM grade logic, partner weight, or assignment workflow — all of that lives in `website_crm_partner_assign`. Instead, it:

- Extends `res.partner` with `website_tag_ids` for public-facing categorization.
- Creates `res.partner.tag` as a new publishable taxonomy for customer filtering.
- Provides the website controller with URL routing, pagination, and search/filter logic.
- Renders public-facing QWeb templates that compose with `website_partner` blocks.
- Ships a website builder plugin (`CustomerFilterOptionPlugin`) so editors can toggle filter panels on/off.

---

## Models

### `res.partner` — Extended (L2/L3)

**Inherited from:** `website_partner` (which inherits `website.seo.metadata`) and `website_crm_partner_assign`.

**New fields added by this module:**

#### `website_tag_ids` — Many2many `res.partner.tag`

```python
website_tag_ids = fields.Many2many(
    'res.partner.tag',
    'res_partner_res_partner_tag_rel',
    'partner_id', 'tag_id',
    string='Website tags',
)
```

| Aspect       | Detail                                                                                          |
|--------------|------------------------------------------------------------------------------------------------|
| Purpose      | Attaches zero-to-many `res.partner.tag` records to a partner for public-side filtering on `/customers` |
| Storage      | Auto-created relational table `res_partner_res_partner_tag_rel` via Odoo's Many2many convention |
| UI           | Rendered as a `many2many_tags` widget on the partner form, inserted after `website_id` (inherited view) |
| Constraints  | No `required` constraint — partners may have zero tags                                         |

**L3 — Cross-model chain:**

```
website_tag_ids → res.partner.tag → is_published → visible on /customers
```

The controller filters tags with `('website_published', '=', True), ('partner_ids', 'in', partners.ids)` so unpublished tags and tags with no matching partners never appear on the listing page.

**Method overrides:**

```python
def get_backend_menu_id(self):
    return self.env.ref('contacts.menu_contacts').id
```

Returns the standard Contacts menu ID so that when a partner record is opened from the website customer context, the user lands in the Contacts app (not the Website editor).

---

### `res.partner.tag` — New Model (L2/L3/L4)

**Full path:** `models/res_partner.py`

**Inherits:** `website.published.mixin` (provides `is_published`, `website_url`, `website_published` context).

```python
class ResPartnerTag(models.Model):
    _name = 'res.partner.tag'
    _description = 'Partner Tags - These tags can be used on website to find customers by sector, or ...'
    _inherit = ['website.published.mixin']
```

#### Fields

| Field         | Type       | Required | Default     | Description                                                    |
|---------------|------------|----------|-------------|----------------------------------------------------------------|
| `name`        | `Char`     | Yes      | —           | Tag label, translatable (`translate=True`)                     |
| `partner_ids` | `Many2many`| No       | —           | Inverse of `website_tag_ids` on `res.partner`                   |
| `classname`   | `Selection`| Yes      | `'info'`    | Bootstrap color class (`info`, `primary`, `success`, `warning`, `danger`) |
| `is_published`| `Boolean`  | —        | `True` (via `_default_is_published`) | Controls visibility on `/customers` and in tag filter panels |
| `active`      | `Boolean`  | No       | `True`      | Soft-delete / archive toggle                                   |

#### `get_selection_class()` — Selection Method

```python
@api.model
def get_selection_class(self):
    classname = ['info', 'primary', 'success', 'warning', 'danger']
    return [(x, str.title(x)) for x in classname]
```

Returns `[('info', 'Info'), ('primary', 'Primary'), ...]`. Used by the `classname` Selection field. `str.title(x)` capitalises the first letter — `'info'` becomes `'Info'`.

#### `_default_is_published()` — Default Publisher

```python
def _default_is_published(self):
    return True
```

Newly created tags are **published by default**, unlike most `website.published.mixin` models where the default is `False`. This is a deliberate UX choice: tags are only meaningful in the context of the published customer directory, so a new tag should appear immediately without requiring an extra publish step.

**L3 — Relationship graph:**

```
res.partner.tag (tag)
    ↓ Many2many partner_ids
res.partner (customer)
    ↓ assigned_partner_id (from website_crm_partner_assign)
res.partner (implementer)
    ↓ website_published (from website_partner)
    → visible on /customers
```

**L4 — Performance:**

`partner_ids` is a reverse Many2many (the "other side" of `website_tag_ids`). The `website_published` ir.rule filters records server-side for public/portal users, but internal users see all tags regardless of publication state.

**L4 — Historical note:**

In Odoo 17 and earlier, partner tags were sometimes conflated with `crm.tag` from the CRM module. `website_customer` deliberately maintains a **separate tag model** scoped to customer references, preventing CRM tag pollution of the public directory.

---

### `website` — Extended (L3)

**Full path:** `models/website.py`

```python
class Website(models.Model):
    _inherit = "website"

    def get_suggested_controllers(self):
        suggested_controllers = super(Website, self).get_suggested_controllers()
        suggested_controllers.append((_('References'), self.env['ir.http']._url_for('/customers'), 'website_customer'))
        return suggested_controllers
```

Appends `('References', '/customers', 'website_customer')` to the website's suggested-controllers list. This drives the "References" entry in the website navbar "Build > Customize" menu. `_url_for()` ensures correct routing behind reverse proxies.

---

## Controllers

**File:** `controllers/main.py`

**Parent:** `GoogleMap` (from `website_google_map`) — provides the map iframe endpoint that `opt_country` template invokes via `/google_map`.

### `_references_per_page = 20`

Class constant. Controls how many partner cards appear per page in the listing. Used by `website.pager()` and the `sudo().search()` offset/limit.

### `_get_gmap_domains()` — Map Filter Override

```python
def _get_gmap_domains(self, **kw):
    if kw.get('dom', '') != "website_customer.customers":
        return super()._get_gmap_domains(**kw)
    ...
```

Intercepts the Google Maps iframe domain query. When the map is embedded on the `/customers` page (`dom=website_customer.customers`), it applies the same country/industry filters as the listing controller and requires `assigned_partner_id` to be set (meaning the partner was graded/assigned via CRM partner assign). Falls back to the parent `_get_gmap_domains` for any other map widget on the site.

---

### `sitemap_industry()` — Dynamic Sitemap Generator

```python
def sitemap_industry(env, rule, qs):
    if not qs or qs.lower() in '/customers':
        yield {'loc': '/customers'}
    # ... yields /customers/industry/<slug> for each industry
    # ... yields /customers/country/<slug> for each country with published assigned partners
```

Used as the `sitemap` argument on the main route. Runs with `sudo()` implicitly inside the sitemap framework. Yields one URL per industry and per country that has at least one published partner with an `assigned_partner_id`. The `/customers` root URL is always included.

**L4 — Sitemap security:** The domain includes `('website_published', '=', True)` and `('assigned_partner_id', '!=', False)` so unpublished or unassigned partners are never indexed.

---

### `customers()` — Listing Route

**Route:** `/customers`, `/customers/page/<page>`, `/customers/country/<country>`, `/customers/industry/<industry>`, and all combinations.

**Decorators:** `type='http'`, `auth='public'`, `website=True`, `sitemap=sitemap_industry`.

```python
def customers(self, country=None, industry=None, page=0, **post):
```

#### Domain Construction (L3)

```
domain = [('website_published', '=', True), ('assigned_partner_id', '!=', False)]
```

Every query enforces both conditions. A partner must be **explicitly published** (not just active) **and** must have been assigned a grade via `website_crm_partner_assign`. This is a hard gate — partners that exist in the system but have not been through the partner assignment flow are never shown.

#### Search Filter

```python
if search_value:
    domain += [
        '|', '|',
        ('name', 'ilike', search_value),
        ('website_description', 'ilike', search_value),
        ('industry_id.name', 'ilike', search_value),
    ]
```

Three-field OR search across name, full HTML description, and industry name.

#### Tag Filter

```python
if tag_id:
    tag_id = request.env['ir.http']._unslug(tag_id)[1] or 0
    domain += [('website_tag_ids', 'in', tag_id)]
```

Applied as a standard `in` domain against the `website_tag_ids` Many2many. Note: `_unslug()` returns `(name, id)` tuple; only the ID is used.

#### Industry / Country Group Counts

`_read_group` is called **before** the country/industry filter is appended to the domain. This gives accurate counts for the sidebar filter panel showing "all industries that have matching partners for the current filters (minus this specific industry)."

**L3 — Group count trick:** The industries sidebar always shows the **total** across all matching partners for the current filters (country filter applied but not industry filter), so the count reflects how many partners would be available for each industry when no industry is selected.

#### Country Fallback

```python
if country:
    if country_groups and country.id not in (country.id for country, __ in country_groups):
        fallback_all_countries = True
        country = None  # display all, filtered by industry only
```

If a user navigates directly to `/customers/country/france` but no published partner exists for France, Odoo shows an alert banner (`fallback_all_countries`) and renders all countries instead of showing an empty result.

#### Tag Search in Template

```python
tags = Tag.search([
    ('website_published', '=', True),
    ('partner_ids', 'in', partners.ids)
], order='classname, name ASC')
```

Tags are restricted to only those whose `partner_ids` intersect with the **currently displayed partners** (not the full search domain). This means the tag filter panel on page 2 may show fewer tags than page 1 if page 2's partners have different tags.

#### Values Passed to Template

| Key                    | Type     | Description                                                         |
|------------------------|----------|---------------------------------------------------------------------|
| `countries`            | `list`   | `[{country_id: (id, name), country_id_count: n}, ...]`              |
| `industries`           | `list`   | Same structure as countries                                          |
| `partners`             | `recordset` | Paginated `res.partner` records (with `sudo()`)                  |
| `pager`                | `dict`   | Website pager dict with `offset`, `limit`, `page`, etc.             |
| `post`                 | `dict`   | Raw `request.params` (search query, tag_id, etc.)                   |
| `search_path`          | `str`    | `"?key=val&..."` for preserving filters across pager links           |
| `tag` / `tags`         | `record` | Selected tag (or False), all visible tags                            |
| `google_maps_api_key`  | `str`    | From `website.google_maps_api_key` — controls map option visibility  |
| `fallback_all_countries` | `bool` | Triggers the "no results for country" alert banner                    |

---

### `customers_detail()` — Partner Detail Route

**Route:** `/customers/<partner_id>`

**Decorators:** `type='http'`, `auth='public'`, `website=True`.

```python
def customers_detail(self, partner_id, **post):
```

1. Unslugs the `partner_id` to get the integer ID.
2. Browses with `sudo()` and checks `partner.exists() and partner.website_published`.
3. If the slug in the URL does not match `ir.http._slug(partner)`, issues a **301 redirect** to the canonical URL (slug-based). This is critical for SEO — duplicate content from old-style numeric URLs is consolidated.
4. If the partner does not exist or is not published, raises `not_found()` (404).

**L4 — Security:** No ACL check beyond `website_published`. Any public user can view any published partner. The `sudo()` is safe here because all displayed fields are either public by design or gated by the `website_published` check.

**L4 — SEO implication:** The `sitemap_industry` function only generates `/customers/<industry-slug>` and `/customers/country/<country-slug>` URLs. Individual partner detail URLs are discovered via internal linking in the listing cards, not via XML sitemap.

---

## Views and Templates

### Backend Views (`views/res_partner_views.xml`)

#### `view.res.partner.form.website.tags` — Form Extension

Inserts `website_tag_ids` after `website_id` on the partner form. Inherits from `website_partner.view_partners_form_website`.

#### `view_partner_tag_form` — Tag Form

`<form>` with `name`, `classname`, `is_published`, `active` fields in a 4-column group.

#### `view_partner_tag_list` — Tag List (editable bottom)

`<list editable="bottom">` showing all tags. `active` is `column_invisible="True"` (soft-delete column hidden by default).

#### `action_partner_tag_form`

Window action pointing to `res.partner.tag`. Placed as a sub-menu of `contacts.res_partner_menu_config` with `sequence="2"`, so it appears as "Website Tags" under the Contacts configuration menu.

---

### Website Templates (`views/website_customer_templates.xml`)

#### `website_customer.index` — Customer Listing Page

Main listing rendered via `request.render("website_customer.index", values)`. Displays:

- Bootstrap card grid (3 columns desktop, 4 on xl, 1 on mobile).
- Each card: avatar image, display name, `website_short_description`, industry badge.
- Search bar (`GET` form — search term preserved in `search_path`).
- Off-canvas filter accordion on mobile; dropdown filters on desktop (enabled via template options).
- "No results" empty state with link back to `/customers`.
- `website.pager` at the bottom.

#### `website_customer.opt_country` — Map Option

Injects a modal map button into the search bar when `google_maps_api_key` is set. When activated, the modal shows a Google Maps iframe loaded from `/google_map?dom=website_customer.customers&...`. The iframe src is constrained to 1000 partner markers via `&limit=1000`.

#### `website_customer.opt_industry_list` — Industry Dropdown (priority 20)

Adds a desktop dropdown "Filter by industry" before the search bar. Uses the `industries` list built in the controller.

#### `website_customer.opt_country_list` — Country Dropdown (priority 30)

Same pattern for countries.

#### `website_customer.opt_tag_list` — Tag Badges (priority 40)

Inserts a badge row below the filter bar. Badges use the tag's `classname` for color (`text-bg-info`, `text-bg-danger`, etc.). The "All" badge clears the tag filter.

#### `website_customer.details` — Partner Detail Page

Wraps `website_partner.partner_detail` and injects two sidebars:

- `left_column`: `implemented_by_block` — shows the partner's `assigned_partner_id` with avatar and link.
- `right_column`: `references_block` — shows all `implemented_partner_ids` (other partners implemented by this same partner) that are `website_published`.

Calls `website_partner.partner_detail` (from `website_partner` module) which renders the standard partner contact card (address, email, phone, map). The `references_block` adds a "References" section below the contact details.

#### `website_customer.references_block` — References Sub-block

```python
t-if="any(p.website_published for p in partner.implemented_partner_ids)"
```

Only renders if at least one `implemented_partner_id` is published. Iterates published references and shows avatar, name, industry badge, and `website_short_description`.

#### `website_customer.references_block_href` — Cross-module Override

Inherits `website_crm_partner_assign.references_block` (used in the CRM partner assign portal) and replaces the static span links with `/customers/<slug>` links, redirecting to the public customer page instead of the internal portal view.

---

## Static Assets (Website Builder Plugin)

**Path:** `static/src/website_builder/`

| File | Type | Description |
|------|------|-------------|
| `customer_filter_option.js` | OWL Component | `CustomerFilterOption` extends `BaseOptionComponent`. Attaches to `main` elements that have the `.o_wcrm_filters_top` bar. Requires `website.group_website_designer` group. On `onWillStart`, fetches the Google Maps API key and shows the "Show Map" option conditionally. |
| `customer_filter_option_plugin.js` | HTML Editor Plugin | Registers the OWL component as a builder option via the `website-plugins` registry. |
| `customer_filter_option.xml` | QWeb template | Defines the four toggle checkboxes: Countries Filter, Industry Filter, Tags Filter, Show Map (conditional on Google Maps key). |

**Plugin selector:** `main:not(:has(#oe_structure_website_crm_partner_assign_layout_1)):has(.o_wcrm_filters_top)`

This means the option panel appears when the page has the filter bar (`.o_wcrm_filters_top`) and does **not** have the CRM layout block (avoiding double-rendering on pages that use the CRM assign layout).

---

## Security

### ACL (`security/ir.model.access.csv`)

| ID | Model | Groups | Read | Write | Create | Unlink |
|----|-------|--------|------|-------|--------|--------|
| `res_partner_tag_sale_manager_public` | `model_res_partner_tag` | `base.group_public` | 1 | 0 | 0 | 0 |
| `res_partner_tag_sale_manager_portal` | `model_res_partner_tag` | `base.group_portal` | 1 | 0 | 0 | 0 |
| `res_partner_tag_sale_manager_employee` | `model_res_partner_tag` | `base.group_user` | 1 | 0 | 0 | 0 |
| `res_partner_tag_sale_manager_edition` | `model_res_partner_tag` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |

**Interpretation:** Public/portal/employee users can **read** tags (needed for the filter UI). Only **Sale Manager** users can create, edit, or delete tags. This mirrors the CRM-heavy nature of the module — tags are a marketing/sales operation, not an individual user preference.

### Record Rule (`security/ir_rule.xml`)

```xml
<field name="domain_force">[('website_published', '=', True)]</field>
<field name="groups" eval="[(4, ref('base.group_public')), (4, ref('base.group_portal'))]"/>
```

Applied to `res.partner.tag` for `base.group_public` and `base.group_portal`. Internal users (employees) are **not** subject to this rule and can see all tags regardless of `is_published`.

**L4 — Security edge case:** The ir.rule uses `website_published` (the computed/concurrency-safe field from `website.published.mixin`), not `is_published` directly. If the mixin's `is_published` → `website_published` compute fails (e.g., a write is in-progress), the rule may return an empty set, hiding all tags from public users temporarily.

---

## Cross-Module Integration Map

```
website_partner
  └── res.partner: website_description, website_short_description,
                   is_published, website_url, _track_subtype, _compute_website_url
      └── website_crm_partner_assign
            └── res.partner: assigned_partner_id (Many2one → partner),
                             implemented_partner_ids (One2many ← partner),
                             implemented_partner_count (computed)
                └── website_customer
                      ├── res.partner: website_tag_ids (Many2many → res.partner.tag)
                      ├── res.partner.tag (new model, website.published.mixin)
                      └── website: get_suggested_controllers → adds "References" /customers
```

```
website_google_map
  └── GoogleMap controller mixin
        └── website_customer
              └── WebsiteCustomer(GoogleMap): _get_gmap_domains, /customers map iframe src
```

---

## Key Odoo 18 → 19 Changes

- **OWL-based website builder plugin** (`customer_filter_option.js`): In Odoo 18, website builder options were defined in XML via `website.snippet` overrides. Odoo 19 introduced the HTML editor plugin registry (`website-plugins`) and OWL-based `BaseOptionComponent`. This module uses the new pattern.
- **Bootstrap 5 / OWL class names**: Template classes like `text-bg-info`, `btn-close`, `offcanvas`, `accordion` indicate a full Bootstrap 5 migration in the templates.
- **`list_as_website_content` parameter** on `@http.route`: New parameter that marks the route as website content, enabling CMS features (editor, versioning) without manual `website.published.mixin` inheritance on the controller.

---

## Performance Considerations

| Area | Issue | Mitigation |
|------|-------|------------|
| `_read_group` on `customers()` | Two separate `_read_group` calls (industry + country) over the full domain before pagination | Counts are needed for sidebar; unavoidable but scoped to published+assigned partners only |
| Tag search with `partner_ids in partners.ids` | N+1 risk if `partners.ids` is large (20 items) | Limit is 20 per page; `Tag.search()` with `in` is a single SQL `WHERE` |
| Google Maps iframe `limit=1000` | 1000 markers in one iframe may be slow on low-bandwidth | Hard cap; map is an optional UX enhancement (template option) |
| `sitemap_industry` with `_read_group` over all countries | Yields one URL per country with published partners | Could be large for global installs; no lazy pagination in sitemap |
| `sudo()` throughout listing | All partner data bypasses record rules | Safe because `website_published=True` is already enforced in the domain |

---

## Related Modules

- [Modules/website_partner](modules/website_partner.md) — Base partner website features (descriptions, is_published, SEO metadata)
- [Modules/website_crm_partner_assign](modules/website_crm_partner_assign.md) — CRM partner grading and assignment (grades, weights, assigned_partner_id, implemented_partner_ids)
- [Modules/website_google_map](modules/website_google_map.md) — Google Maps embedding on website pages
