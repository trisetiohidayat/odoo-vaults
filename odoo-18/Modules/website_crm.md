# Website CRM Module (website_crm)

## Overview

The `website_crm` module captures leads from website forms and links them to website visitors. It automatically assigns leads to the correct sales team and user based on website configuration, and provides analytics on visitor behavior before lead conversion.

## Key Models

### crm.lead (website_crm Extension)

Extends `crm.lead` with website visitor tracking and website form integration.

**Additional Fields:**
- `visitor_ids`: Many2many - Website visitors linked to this lead
- `visitor_page_count`: Integer - Total page views across all linked visitors (computed via SQL)

**Key Computed Methods:**

- `_compute_visitor_page_count()`: Computed via raw SQL that joins `crm_lead`, `crm_lead_website_visitor_rel`, `website_visitor`, and `website_track` tables. Returns the count of page views across all visitors linked to this lead.
- `_merge_get_fields_specific()`: When merging leads, all visitors from all source leads are combined into the merged lead via the Many2many relation.

**Website Form Integration:**

- `website_form_input_filter(request, values)`: Called by the website form controller before creating a lead from a website contact form.
  - Sets `medium_id`: defaults to the `utm.medium` named "website", fetched or created via `_fetch_or_create_utm_medium()`
  - Sets `team_id`: from `request.website.crm_default_team_id` (configured on the website)
  - Sets `user_id`: from `request.website.crm_default_user_id` (configured on the website)
  - Determines `type`:
    - If a team is specified: uses the team's `use_leads` setting to decide between `lead` and `opportunity`
    - Otherwise: uses the current user's group membership (`crm.group_use_lead`) to decide

**Key Actions:**

- `action_redirect_to_page_views()`: Opens the website track list filtered to all visitors linked to this lead. If there are more than 15 tracked pages and multiple pages, groups by page in the search view.

## Cross-Module Relationships

- **crm**: Base lead/opportunity model
- **website**: Website configuration for default team and user assignment
- **website_visitor**: Visitor records linked to leads; track page view history
- **website_track**: Page view tracking for each visitor

## Edge Cases

1. **Multiple Visitors per Lead**: A single lead can be linked to multiple visitors (e.g., a lead submitted from a shared computer, or a lead that came from multiple tracking sessions). `visitor_page_count` aggregates all page views across all linked visitors.
2. **Visitor Page Count Performance**: The page count is computed via a direct SQL query with a JOIN across 4 tables, avoiding ORM overhead for this performance-critical aggregation.
3. **UTM Medium Auto-Creation**: If no `medium_id` is provided and no default exists, `_fetch_or_create_utm_medium('website')` creates one automatically. This ensures lead source attribution works without manual setup.
4. **Team vs User Defaults**: The website configuration can set both `crm_default_team_id` and `crm_default_user_id`. The team is applied as the primary assignment; the user is applied as the responsible salesperson. This allows websites to route leads to specific teams with default salespeople.
5. **Lead vs Opportunity Routing**: The `use_leads` setting on the assigned team (`crm.team`) determines whether the website form creates a lead or an opportunity. If the team is not specified, the user's group membership is checked.
6. **Lead Merging and Visitors**: When leads are merged, all visitor records from all source leads are combined into the target lead's Many2many relation. No visitor data is lost during the merge.
7. **Website Form Bypass**: The `website_form_input_filter` is called before every website form submission, allowing the website to control lead assignment without modifying the form controller logic. This follows Odoo's template method pattern for website form processing.
8. **Page View Action Grouping**: The `action_redirect_to_page_views` uses a heuristic (more than 15 tracked pages across more than 1 page) to decide whether to apply a `group_by_page` search default, reducing visual clutter for high-volume tracking.
