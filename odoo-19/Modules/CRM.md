---
type: module
module: crm
tags: [odoo, odoo19, crm, leads, opportunity, pipeline, sales, pls, predictive-scoring]
updated: 2026-04-11
version: "4.0"
---

## Quick Access

### Flows (Technical)
- [Flows/CRM/lead-creation-flow](Flows/CRM/lead-creation-flow.md) - Lead from multiple sources
- [Flows/CRM/lead-conversion-to-opportunity-flow](Flows/CRM/lead-conversion-to-opportunity-flow.md) - Lead to Opportunity conversion
- [Flows/CRM/opportunity-win-flow](Flows/CRM/opportunity-win-flow.md) - Mark as won
- [Flows/CRM/lead-assignment-flow](Flows/CRM/lead-assignment-flow.md) - Auto-assignment cron

### Related Modules
- [Modules/Sale](Modules/Sale.md) - Sale order from opportunity
- [Modules/Account](Modules/Account.md) - Revenue tracking
- [Modules/Stock](Modules/Stock.md) - Inventory and delivery
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) - Pipeline stage patterns
- [Modules/UTM](Modules/UTM.md) - Campaign/source tracking
- [Modules/Mail](Modules/Mail.md) - Messaging and notifications
- [Modules/Calendar](Modules/Calendar.md) - Meeting integration

---

## Module Overview

| Property | Value |
|----------|-------|
| **Name** | CRM |
| **Version** | 19.0 |
| **Category** | Sales/CRM |
| **Sequence** | 15 |
| **Summary** | Track leads and close opportunities |
| **Website** | https://www.odoo.com/app/crm |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Application** | Yes |

## Dependencies

```
base_setup ─┬─ sales_team ─── crm.team, crm.tag (shared via sales_team)
            ├─ mail ───────── Messaging and notifications
            ├─ calendar ────── Meeting integration
            ├─ resource ────── Resource scheduling
            ├─ utm ─────────── Campaign/source tracking
            ├─ phone_validation ── Phone number validation
            ├─ digest ──────── KPI email digests
            ├─ web_tour ─────── Interactive tours
            ├─ contacts ─────── Partner contact support
            └─ iap ──────────── (optional) IAP enrichment/mining
```

**L3 Detail:** The `crm` module has a layered dependency structure. `base_setup` provides user/company scaffolding. `sales_team` provides the base `crm.team` model that CRM extends with lead-specific features (assignment, aliasing). `mail` is the heaviest dependency — CRM's `crm.lead` inherits from 5 mail mixins (`mail.thread.cc`, `mail.thread.blacklist`, `mail.thread.phone`, `mail.activity.mixin`, `mail.tracking.duration.mixin`). `utm` provides campaign tracking mixins. Optional IAP modules (`crm_iap_mine`, `crm_iap_enrich`, `website_crm_iap_reveal`) are toggled via `res.config.settings`.

---

## File Structure

```
crm/
├── __manifest__.py              # Version 1.9, 14 data files, JS assets
├── models/
│   ├── __init__.py
│   ├── crm_lead.py              # crm.lead (MAIN model) — ~2888 lines
│   ├── crm_team.py              # crm.team extension + assignment logic
│   ├── crm_team_member.py       # crm.team.member extension
│   ├── crm_stage.py             # Pipeline stages
│   ├── crm_lost_reason.py       # Lost reasons
│   ├── crm_recurring_plan.py    # MRR billing periods
│   ├── crm_lead_scoring_frequency.py  # PLS frequency table + field config
│   ├── calendar.py              # calendar.event extension
│   ├── digest.py                # digest KPI extensions
│   ├── utm.py                  # utm.campaign extension
│   ├── mail_activity.py         # Activity type extensions
│   ├── res_partner.py          # Partner extensions
│   ├── res_config_settings.py   # Settings page
│   ├── res_users.py            # User display extensions
│   └── ir_config_parameter.py   # Config parameter hooks
├── wizard/
│   ├── __init__.py
│   ├── crm_lead_lost.py         # Lost reason wizard
│   ├── crm_lead_to_opportunity.py        # Single lead conversion
│   ├── crm_lead_to_opportunity_mass.py  # Mass conversion
│   ├── crm_merge_opportunities.py        # Merge wizard
│   └── crm_lead_pls_update.py            # PLS rebuild wizard
├── views/
│   ├── crm_lead_views.xml        # Kanban, list, form, search
│   ├── crm_team_views.xml        # Team dashboard
│   ├── crm_stage_views.xml        # Stage configuration
│   ├── crm_lost_reason_views.xml  # Lost reason config
│   ├── crm_recurring_plan_views.xml
│   ├── crm_team_member_views.xml  # Member capacity views
│   ├── calendar_views.xml         # Meeting links
│   ├── digest_views.xml           # KPI widgets
│   ├── res_partner_views.xml       # Partner opportunity tab
│   ├── utm_campaign_views.xml      # UTM campaign links
│   ├── res_config_settings_views.xml
│   ├── mail_activity_views.xml     # Activity kanban
│   ├── mail_activity_plan_views.xml
│   └── crm_menu_views.xml
├── report/
│   ├── crm_activity_report_views.xml
│   └── crm_opportunity_report_views.xml
└── data/
    ├── crm_stage_data.xml         # New, Qualified, Proposition, Won stages
    ├── crm_lost_reason_data.xml   # 3 default lost reasons
    ├── crm_recurring_plan_data.xml # Monthly/Yearly/3yr/5yr plans
    ├── crm_team_data.xml
    ├── ir_cron_data.xml            # ir_cron_crm_lead_assign (inactive by default)
    ├── digest_data.xml
    ├── mail_message_subtype_data.xml
    ├── crm_lead_merge_template.xml
    ├── crm_lead_prediction_data.xml
    ├── crm_tour.xml
    └── demo/
        ├── crm_team_demo.xml
        ├── crm_stage_demo.xml
        ├── crm_lead_demo.xml
        ├── crm_team_member_demo.xml
        └── mail_template_demo.xml
```

---

## Key Models

### 1. crm.lead (Lead/Opportunity)

**File:** `odoo/addons/crm/models/crm_lead.py` (~2888 lines)

Central model representing leads and opportunities. Inherits from multiple mixins for messaging, phone handling, blacklist, activities, UTM tracking, address formatting, and stage duration tracking.

#### Model Definition

```python
class CrmLead(models.Model):
    _name = 'crm.lead'
    _inherit = [
        'mail.thread.cc',              # CC email handling
        'mail.thread.blacklist',       # Email blacklist + email_normalized
        'mail.thread.phone',          # Phone sanitization + phone_sanitized
        'mail.activity.mixin',         # Activity tracking (my_activity_date_deadline)
        'utm.mixin',                  # campaign_id, medium_id, source_id
        'format.address.mixin',       # street, city, zip, state_id, country_id
        'mail.tracking.duration.mixin', # Stage duration tracking
    ]
    _primary_email = 'email_from'     # Blacklist lookup field
    _check_company_auto = True
    _track_duration_field = 'stage_id'
    _order = 'priority desc, id desc'
```

**L3 Detail:** The 7-mixin inheritance chain is carefully designed. `mail.thread.blacklist` provides `email_normalized` and blacklist checking. `mail.thread.phone` provides `phone_sanitized`. Together they enable duplicate detection. `mail.tracking.duration.mixin` writes stage-change timestamps used by the rotting mechanism. `_track_duration_field = 'stage_id'` means the mixin stores how long a lead spends in each stage (used by `_get_rotting_domain`). `_check_company_auto = True` triggers ORM-level company consistency validation on every write.

#### Database Indexes

```python
_user_id_team_id_type_index = models.Index("(user_id, team_id, type)")
_create_date_team_id_idx   = models.Index("(create_date, team_id)")
_default_order_idx          = models.Index("(priority DESC, id DESC) WHERE active IS TRUE")
```

**L4 Performance:** The `_default_order_idx` is a partial index covering only active leads — critical for kanban view performance on large datasets. The `(user_id, team_id, type)` composite index speeds up the most common dashboard queries. The trigram indexes on `name`, `email_from`, `email_normalized` enable fast fuzzy text search via `ilike` (used in duplicate detection).

#### Core Identification Fields

| Field | Type | Index | Description |
|-------|------|-------|-------------|
| `name` | Char | trigram | Opportunity name (computed from contact/company if empty) |
| `type` | Selection | btree | `'lead'` or `'opportunity'`; default from `group_use_lead` |
| `active` | Boolean | - | Soft-delete flag; lost leads set `active=False` |
| `company_id` | Many2one | btree | Multi-company support |

**L3 Detail:** `type` controls whether the record is in "lead" (unqualified) or "opportunity" (qualified) mode. The `default` is dynamic — checks `group_use_lead` group. If user has the group, default is `'lead'`; otherwise `'opportunity'`. This prevents junior users from creating unqualified leads.

**L4 Edge Case:** When `type='lead'`, the `partner_id` field is hidden in the UI unless set or in debug mode (`_compute_is_partner_visible`). This prevents confusion because leads typically don't have a linked customer yet. The `commercial_partner_id` is computed from `partner_id` or `partner_name` via `_compute_commercial_partner_id`.

#### Owner Assignment Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | Many2one | Salesperson (domain: `share=False`), `check_company=True` |
| `team_id` | Many2one | Sales team, computed from user if empty, `ondelete="set null"` |
| `lead_properties` | Properties | Custom team-defined properties, definition from `team_id.lead_properties_definition` |

**L3 Detail:** `team_id` is a computed-stored field with a readonly=False inverse. `_compute_team_id` runs on `user_id` or `type` change. It calls `crm.team._get_default_team_id()` which respects the `use_leads`/`use_opportunities` flag on the team. If the current user is already a member of a team with matching flag, that team is kept.

**L4 Edge Case:** `_compute_team_id` has a subtle check: `if lead.team_id and user in (lead.team_id.member_ids | lead.team_id.user_id): continue` — this preserves the existing team assignment if the user is already a member. Without this, changing `user_id` could incorrectly reassign the team.

**L4 Performance:** `lead_properties` stores arbitrary JSON properties. Each team can define a different schema via `lead_properties_definition`. Reading leads with many properties can be slow — Odoo stores this as a `jsonb` column with GIN indexing by default.

#### Contact Fields

| Field | Type | Index | Description |
|-------|------|-------|-------------|
| `partner_id` | Many2one | btree | Linked partner (check_company=True) |
| `contact_name` | Char | trigram | Contact person name (computed from partner) |
| `partner_name` | Char | trigram | Company name (computed from partner) |
| `email_from` | Char | trigram | Email (inverse setter syncs to partner) |
| `email_normalized` | Char | trigram | Normalized email (from blacklist mixin) |
| `email_domain_criterion` | Char | btree_not_null | IAP-ready domain for duplicate detection |
| `phone` | Char | - | Phone (inverse setter syncs to partner) |
| `phone_sanitized` | Char | btree_not_null | Sanitized phone for matching |
| `function` | Char | - | Job position |
| `website` | Char | - | Website URL (cleaned on write) |
| `lang_id` | Many2one | - | Preferred language |
| `lang_code` | Char | related | Language code |
| `commercial_partner_id` | Many2one | - | Top-level company (for hierarchy) |

**L3 Detail — Email Normalization:** `mail.thread.blacklist` computes `email_normalized` via `tools.email_normalize()`. This strips Gmail dots, plus-addressing, and case differences. The `email_domain_criterion` field uses `iap_tools.mail_prepare_for_domain_search()` for IAP-compatible domain extraction — used in duplicate detection.

**L3 Detail — Phone Sanitization:** `mail.thread.phone` provides `_phone_format()` which formats numbers based on `country_id`. The sanitized form removes spaces, dots, dashes, and normalizes country prefix. Both `email_normalized` and `phone_sanitized` are stored with `btree_not_null` indexes for fast exact-match duplicate lookups.

**L3 Detail — Partner Sync:** When `partner_id` is set, many fields are auto-computed from it (`contact_name`, `partner_name`, `function`, `website`, `lang_id`, address fields). The inverse setters for `email_from` and `phone` write back to `partner_id` using `_get_partner_email_update()` / `_get_partner_phone_update()`. These methods normalize both sides before comparison to avoid spurious updates.

**L4 Edge Case — Partner Sync Guard:** `_get_partner_email_update` uses `force_void=False` in the compute to skip when the lead email is empty. This prevents overwriting a valid partner email with a blank lead email. The inverse setter uses `force_void=False` for the same reason.

**L4 Edge Case — Commercial Partner Matching:** `_compute_commercial_partner_id` has two paths: (1) from `partner_id` → `commercial_partner_id`, (2) from `partner_name` → matching `is_company=True` partner by name. The second path uses `_read_group` with `['id:array_agg']` to avoid N+1 queries.

#### Address Fields (via `format.address.mixin`)

| Field | Type | Description |
|-------|------|-------------|
| `street`, `street2` | Char | Street address |
| `city` | Char | City |
| `state_id` | Many2one | State/Province (domain: `country_id`) |
| `country_id` | Many2one | Country |
| `zip` | Char | ZIP/Postal code |

**L3 Detail:** `format.address.mixin` provides address formatting in emails/reports. All fields are computed from `partner_id` with `readonly=False` — user edits persist because the compute only runs when `partner_id` changes (ORM caches the old value). The `domain` on `state_id` (`'country_id', '=?', country_id`) uses the "overridden" operator to make country optional — if `country_id` is False, all states are shown.

#### Pipeline Fields

| Field | Type | Description |
|-------|------|-------------|
| `stage_id` | Many2one | Pipeline stage, computed from team, domain by team |
| `stage_id_color` | Integer | Related from stage (for export) |
| `priority` | Selection | `'0'` (Low) to `'3'` (Very High) |
| `tag_ids` | Many2many | Tags (crm.tag) |
| `color` | Integer | Color index for kanban |
| `probability` | Float | Win probability (0–100), manual or PLS-driven |
| `automated_probability` | Float | PLS-calculated probability |
| `is_automated_probability` | Boolean | True when probability == automated_probability |
| `won_status` | Selection | `'won'`, `'lost'`, `'pending'` (stored, computed) |
| `lost_reason_id` | Many2one | Reason for losing |
| `date_closed` | Datetime | Close date (set on won or lost) |
| `date_last_stage_update` | Datetime | Last stage change timestamp |

**L3 Detail — Stage Domain:** `stage_id` has a domain `['|', ('team_ids', '=', False), ('team_ids', 'in', team_id)']`. Stages without `team_ids` are global (visible to all teams). Stages with `team_ids` are only visible to those teams. The `_read_group_stage_ids` method extends the kanban column expansion to include team-specific stages.

**L3 Detail — Won/Lost Logic:** `won_status` is computed via:
- `'won'` when `probability == 100 AND stage_id.is_won == True`
- `'lost'` when `active == False AND probability == 0`
- `'pending'` otherwise

Note: A lead can have `probability == 100` without being "won" if the stage's `is_won` is False. The constraint `_check_won_validity` enforces that a won-stage lead cannot have probability < 100.

**L4 Edge Case:** A lead in a won stage with `probability` manually lowered to, say, 50% is invalid and blocked by `_check_won_validity`. However, `_check_won_validity` is a `@api.constrains` that only runs on write — it does not prevent `probability` being set directly during creation (handled in `create()` by `_handle_won_lost`).

#### Revenue Fields

| Field | Type | Store | Description |
|-------|------|-------|-------------|
| `expected_revenue` | Monetary | - | Expected revenue |
| `prorated_revenue` | Monetary | Yes | `expected_revenue * probability / 100` |
| `recurring_revenue` | Monetary | - | Recurring revenue value |
| `recurring_plan` | Many2one | - | Billing period (crm.recurring.plan) |
| `recurring_revenue_monthly` | Monetary | Yes | `recurring_revenue / months` |
| `recurring_revenue_monthly_prorated` | Monetary | Yes | `monthly_mrr * probability / 100` |
| `recurring_revenue_prorated` | Monetary | Yes | `recurring_revenue * probability / 100` |
| `company_currency` | Many2one | - | Company currency (computed) |

**L3 Detail:** All monetary fields use `company_currency` which is computed from `company_id`. The `_field_to_sql` override handles monetary aggregations in `read_group` by joining `res.company` to get the correct currency_id per record — critical for multi-company setups where different companies have different currencies.

**L4 Security:** Recurring revenue fields require `group_use_recurring_revenues` group. Without it, the fields are invisible and `copy_data` sets them to 0.

#### Date Tracking Fields

| Field | Type | Store | Description |
|-------|------|-------|-------------|
| `date_open` | Datetime | Yes | When lead was assigned to user |
| `day_open` | Float | Yes | Days from create to date_open (integer days) |
| `day_close` | Float | Yes | Days from create to date_closed |
| `date_deadline` | Date | - | Expected closing date |
| `date_conversion` | Datetime | - | When lead was converted to opportunity |
| `date_automation_last` | Datetime | - | Last automated action |
| `date_last_stage_update` | Datetime | Yes | Last stage change |

**L3 Detail:** `date_open` is set when `user_id` changes to a non-empty value. It is NOT cleared when `user_id` is set to False (explicit unassignment sets `date_open` to False). `day_open` and `day_close` use `abs()` to always be positive.

**L4 Edge Case:** `day_open` and `day_close` use `microsecond=0` on `create_date` before subtraction — this ensures whole-day precision and avoids floating-point rounding issues across timezones.

#### Computed/UX Fields

| Field | Type | Description |
|-------|------|-------------|
| `duplicate_lead_ids` | Many2many | Potential duplicates (email domain + phone + commercial entity) |
| `duplicate_lead_count` | Integer | Duplicate count |
| `calendar_event_ids` | One2many | Linked meetings |
| `meeting_display_date` | Date | Next/last meeting date |
| `meeting_display_label` | Char | "Next Meeting" / "Last Meeting" / "No Meeting" |
| `email_state`, `phone_state` | Selection | Email/phone quality (correct/incorrect) |
| `partner_email_update` | Boolean | Partner email will update on save |
| `partner_phone_update` | Boolean | Partner phone will update on save |
| `is_partner_visible` | Boolean | Partner field visible in UI |
| `user_company_ids` | Many2many | Companies the user can access |

**L3 Detail — Duplicate Detection:** `_compute_potential_lead_duplicates` checks three criteria:
1. Same `email_domain_criterion` (exact domain match, e.g., `@acme.com`)
2. Same `commercial_partner_id` hierarchy (`partner_id child_of commercial_partner_id`)
3. Same `phone_sanitized`

`SEARCH_RESULT_LIMIT = 21` — if a search returns 21+ results, the domain is considered too broad and returns all records (not useful for duplicate detection). The method uses `with_context(active_test=False)` and `sudo()` to ensure all leads are found regardless of record rules.

**L4 Performance:** Duplicate detection runs on every form view load. For large databases, the `SEARCH_RESULT_LIMIT = 21` threshold prevents runaway queries but the live search on each compute can still be slow. Consider adding a dedicated background job to pre-compute duplicates if this becomes a bottleneck.

#### SQL Constraints

```python
_sql_constraints = [
    ('check_probability', "CHECK(probability >= 0 AND probability <= 100)", 'The probability of success must be between 0 and 100.'),
]
```

**`@api.constrains('stage_id', 'probability')`** — `_check_won_validity`: Enforces that leads in `is_won=True` stages must have `probability = 100`. This runs on write and onchange, but not on direct creation (handled by `_handle_won_lost`).

---

### Key Action Methods

#### Win/Loss

**`action_set_lost(lost_reason_id=False)`**
Sets `probability=0`, `active=False` (archive), and optionally `lost_reason_id`. Calls `action_archive()` (super) then `write()`. Triggers `_handle_won_lost` to decrement frequency table.

**`action_set_won()`**
- Unarchives the lead
- Finds the appropriate won stage (next won stage by sequence, or last won stage if beyond all)
- Sets `stage_id` and `probability=100`
- Groups leads by won stage to minimize frequency writes (one write per unique stage)
- Does NOT set `date_closed` — the `write()` hook sets it when `probability >= 100`

**`action_set_automated_probability()`**
Forces probability back to the PLS-calculated value. Resets `is_automated_probability=True`. One-at-a-time (`ensure_one()`).

**`action_set_won_rainbowman()`**
Calls `action_set_won()`, then fetches `_get_rainbowman_message()` and returns a rainbowman effect dict if the message is non-empty.

**`action_unarchive()` / `action_restore()`**
`action_unarchive()` re-activates and clears `lost_reason_id`. `action_restore()` additionally recomputes probability from PLS (since manual override is lost during archive).

#### Conversion

**`convert_opportunity(partner, user_ids=False, team_id=False)`**
Core conversion method. Sets `type='opportunity'`, `date_conversion=now`, and optionally reassigns partner and salespeople.

**`_handle_partner_assignment(force_partner_id, create_missing, with_parent)`**
Finds or creates a partner, then links it to the lead. `_create_customer()` creates a `res.partner` from lead fields, handling:
- Company contact vs. individual contact
- Extracting contact name from email if not provided
- Setting `parent_id` if `with_parent` is given
- Syncing address, phone, email, website, lang

**`_handle_salesmen_assignment(user_ids, team_id)`**
Round-robin assignment. With 4 salesmen and 6 leads: S1→L1,L4, S2→L2,L5, S3→L3,L6. Implementation uses Python slice syntax: `lead_ids[idx::steps]`.

#### Duplicate Detection

**`_compute_potential_lead_duplicates()`** — See field table above.

**`_get_lead_duplicates(partner, email, include_lost)`**
Low-level search returning duplicates by email normalized or partner. Used by the merge wizard and assignment. `include_lost=True` allows finding archived lost leads as merge targets.

#### Lead Merge

**`merge_opportunity(user_id, team_id, auto_unlink)`** → `_merge_opportunity()`

Sorts by confidence level (opportunity > lead, higher stage, higher probability, newer), then merges. Key steps:
1. `_sort_by_confidence_level()` — inactive leads last; opportunities ranked above leads; ties broken by stage sequence, probability, then id desc
2. `_merge_data()` — concatenates descriptions, takes first non-null for other scalar fields, takes union for m2m fields
3. `_merge_followers()` — only moves followers who posted in last 30 days (SQL query with date filter)
4. `_merge_dependences_history()` — moves messages (with renamed subjects) and activities
5. `_merge_dependences_attachments()` — moves attachments, renames those with duplicate names
6. `_merge_dependences_calendar_events()` — moves meetings
7. `unlink()` tail opportunities

**L4 Edge Case — Follower Merge:** Only followers who posted a message in the last 30 days are transferred. This prevents mass-notifying inactive followers. The SQL uses `NOW() - INTERVAL '30 DAY'` directly in the query.

**L4 Edge Case — Max Merge Length:** Default `max_length=5` prevents accidentally merging too many records. Superuser bypasses this. The wizard enforces it at UI level.

#### Meeting Actions

**`action_schedule_meeting(smart_calendar=True)`**
Opens calendar with lead context. If `smart_calendar=True`, calls `_get_opportunity_meeting_view_parameters()` to choose mode (week/month) and initial date based on meeting schedule.

**`_get_opportunity_meeting_view_parameters()`**
- 0 meetings → week mode, False date
- 1 meeting → week mode, meeting start date
- Multiple meetings in same week → week mode, earliest start
- Otherwise → month mode, earliest start
- All-day events use raw datetime (not timezone-adjusted)

#### Mail Gateway

**`message_new(msg_dict, custom_values)`**
Called by incoming email via mail gateway. Sets `default_user_id=False` to avoid assigning to root. Extracts subject as name, email_from, partner_id from author. Calls `_assign_userless_lead_in_team()` which assigns to the team leader if rule-based assignment is not active.

**`_message_post_after_hook()`**
After a message is posted, if the lead has an email but no partner, searches for a matching partner by email and auto-links. Only links to leads without a partner and in non-fold stages.

#### PLS Methods

See dedicated [L4 PLS section](#predictive-lead-scoring-pls.md) below.

---

### 2. crm.team (Sales Team Extension)

**File:** `odoo/addons/crm/models/crm_team.py` (~760 lines)

Extends `crm.team` from `sales_team` with CRM-specific assignment and alias features.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `use_leads` | Boolean | Filter incoming as leads |
| `use_opportunities` | Boolean | Manage pipeline opportunities (default True) |
| `alias_id` | Many2one | Email alias for lead creation |
| `alias_name` | Char | Email prefix (managed via `_alias_get_creation_values`) |
| `alias_defaults` | Text | Default values for alias-created leads |
| `assignment_enabled` | Boolean | Rule-based assignment available (computed) |
| `assignment_auto_enabled` | Boolean | Cron-based auto-assignment active (computed) |
| `assignment_optout` | Boolean | Skip this team in auto-assignment |
| `assignment_max` | Integer | Monthly lead capacity sum of members (computed) |
| `assignment_domain` | Char | Additional filter domain for assignment |
| `lead_properties_definition` | PropertiesDefinition | Custom property schema |
| `lead_unassigned_count` | Integer | Unassigned lead count (computed) |
| `lead_all_assigned_month_count` | Integer | Leads assigned this month (computed) |
| `lead_all_assigned_month_exceeded` | Boolean | Over monthly capacity (computed) |

**L3 Detail — Alias Defaults:** `_alias_get_creation_values()` sets `alias_defaults` to `{'type': 'lead'/'opportunity', 'team_id': id}` based on team flags and user's group membership. The alias model is `crm.lead` so emails to the alias create lead records.

**L3 Detail — Assignment Computation:** `assignment_enabled` checks `crm.lead._is_rule_based_assignment_activated()` which reads `ir.config_parameter` `crm.lead.auto.assignment`. `assignment_auto_enabled` additionally checks if the `ir_cron_crm_lead_assign` cron is active.

#### Lead Assignment Pipeline

**`_cron_assign_leads(force_quota, creation_delta_days=7)`**
Entry point for scheduled assignment. Calls `_action_assign_leads()` on all teams with `assignment_optout=False`.

**`_action_assign_leads(force_quota, creation_delta_days)`**
Two-phase assignment:
1. `_allocate_leads()` — assign unassigned leads to teams (weighted by `assignment_max`)
2. `_assign_and_convert_leads()` — assign team members their quota

Returns `(teams_data, members_data)` for notification.

**`_allocate_leads(creation_delta_days)`**
Weighted random allocation to teams:
- Finds unassigned leads (no team, no user) created within `creation_delta_days`, matching team domain
- Uses weighted random choice proportional to `assignment_max`
- Auto-commits every `BUNDLE_COMMIT_SIZE` (100) records to avoid long transactions
- Deduplicates leads before assignment using `_get_lead_duplicates()`
- Merges duplicates via `_allocate_leads_deduplicate()`
- `max_create_dt` is set to `now() - timedelta(hours=BUNDLE_HOURS_DELAY)` where `BUNDLE_HOURS_DELAY` defaults to 0 (configurable via `crm.assignment.delay`)

Configurable via `ir.config_parameter`:
- `crm.assignment.delay` (hours) — delay before taking leads in assignment (default: 0)
- `crm.assignment.commit.bundle` — batch size before commit (default: 100)

**`_assign_and_convert_leads(force_quota)`**
Round-robin assignment to team members:
- Gets quota per member: `round(assignment_max / 30)` minus leads assigned in last 24h (unless `force_quota=True`)
- Two-pass: first preferred leads (matching `assignment_domain_preferred`), then general leads
- Converts each lead to opportunity during assignment
- Uses `_get_assignment_quota()` per member

**L4 Performance:** Assignment uses `random.choices()` for weighted selection. Leads are fetched in batches via `_read_group` with `['id:array_agg']` aggregation to avoid loading all leads into memory at once. The `auto_commit` flag disables commits during tests (`modules.module.current_test`).

**L4 Edge Case — Preferred Domain:** Members with `assignment_domain_preferred` get first priority on matching leads. Leads matching preferred domain are sorted by probability desc, then by id desc. Members without preferred domain only get leftover leads.

**L4 Edge Case — BUNDLE_HOURS_DELAY:** The delay parameter (default 0 hours) prevents newly created leads from entering the assignment pool immediately. This allows automation rules and other crons to process leads before they are assigned. When `BUNDLE_HOURS_DELAY=0`, leads are eligible immediately.

---

### 3. crm.team.member (Team Member Extension)

**File:** `odoo/addons/crm/models/crm_team_member.py` (~100 lines)

| Field | Type | Description |
|-------|------|-------------|
| `assignment_domain` | Char | Member-specific filter |
| `assignment_domain_preferred` | Char | Priority filter (gets first pick) |
| `assignment_optout` | Boolean | Pause assignment for this member |
| `assignment_max` | Integer | Average monthly capacity (default 30) |
| `lead_day_count` | Integer | Leads assigned in last 24h |
| `lead_month_count` | Integer | Leads assigned in last 30 days |

**`_get_assignment_quota(force_quota)`**
```python
quota = round(assignment_max / 30)  # daily quota
if force_quota:
    return quota
return quota - lead_day_count       # remaining today
```
**L4 Edge Case:** `force_quota=True` ignores today's assignments — used in manual assignment from team form view. The daily quota is `round(max/30)` not `max/30` — rounding means a member with `assignment_max=30` gets 1 lead/day (not 1 lead/day exactly). With `assignment_max=31`, `round(31/30) = round(1.033) = 1`, so still 1 lead/day.

---

### 4. crm.tag (CRM Tag)

**File:** `odoo/addons/sales_team/models/crm_tag.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name (unique, translate) |
| `color` | Integer | Random color 1-11, settable |

SQL Constraint: `unique(name)`. Shared between `sales_team` and `crm`.

---

### 5. crm.stage (Pipeline Stage)

**File:** `odoo/addons/crm/models/crm_stage.py`

```python
AVAILABLE_PRIORITIES = [
    ('0', 'Low'), ('1', 'Medium'), ('2', 'High'), ('3', 'Very High'),
]
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Stage name (translate) |
| `sequence` | Integer | Sort order (lower = earlier) |
| `is_won` | Boolean | Mark as won stage |
| `rotting_threshold_days` | Integer | Days before rotting flag (0=disabled) |
| `requirements` | Text | Internal tooltip requirements |
| `team_ids` | Many2many | Teams using this stage (null=global) |
| `fold` | Boolean | Fold in kanban when empty |
| `color` | Integer | Stage color |

**L3 Detail — `is_won` Write Override:** When `is_won` changes:
- Setting to `True`: updates all leads in that stage to `probability=100`
- Setting to `False`: calls `_compute_probabilities()` on all leads in that stage

This is a bulk ORM operation — on a large database with many leads in a won stage, unmarking a won stage triggers probability recomputation for all those leads.

**L3 Detail — Rotting:** `rotting_threshold_days` integrates with `mail.tracking.duration.mixin`. The mixin tracks when `stage_id` changes. `_get_rotting_domain()` returns leads where:
- `won_status == 'pending'` (not won)
- `type == 'opportunity'`
- Days since `date_last_stage_update` > `rotting_threshold_days`

#### Default Stages (noupdate)

| Name | Sequence | Color | Is Won |
|------|----------|-------|--------|
| New | 1 | 11 (orange) | No |
| Qualified | 2 | 5 (yellow) | No |
| Proposition | 3 | 8 (purple) | No |
| Won | 70 | 10 (green) | Yes |

---

### 6. crm.lost.reason (Lost Reason)

**File:** `odoo/addons/crm/models/crm_lost_reason.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Reason name (translate) |
| `active` | Boolean | Archive support |
| `leads_count` | Integer | Count of leads with this reason (computed) |

**L3 Detail:** `leads_count` uses `with_context(active_test=False)` in `_read_group` to count archived leads too. `action_lost_leads()` opens a filtered list view of all leads (including archived) using that reason.

**Default Reasons:** Too expensive, We don't have people/skills, Not enough stock

---

### 7. crm.recurring.plan (Recurring Revenue Plan)

**File:** `odoo/addons/crm/models/crm_recurring_plan.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Plan name (translate) |
| `number_of_months` | Integer | Duration in months |
| `active` | Boolean | Active status |
| `sequence` | Integer | Display order |

SQL Constraint: `CHECK(number_of_months >= 0)`

**Default Plans:** Monthly (1), Yearly (12), Over 3 years (36), Over 5 years (60)

**L3 Detail:** `recurring_revenue_monthly = recurring_revenue / number_of_months`. Division by zero is guarded by `or 1` in the compute.

---

### 8. crm.lead.scoring.frequency (PLS Frequency Table)

**File:** `odoo/addons/crm/models/crm_lead_scoring_frequency.py`

| Field | Type | Description |
|-------|------|-------------|
| `variable` | Char | Field name (indexed) |
| `value` | Char | Field value (as string) |
| `won_count` | Float | Times won with this value (`digits=(16,1)`) |
| `lost_count` | Float | Times lost with this value (`digits=(16,1)`) |
| `team_id` | Many2one | Sales team (null = global fallback, cascade delete) |

**L3 Detail — Float Counts:** `won_count` and `lost_count` use `digits=(16,1)` Float. The 0.1 smoothing (Laplace smoothing) avoids zero-frequency division. Counts are floats because incrementing by 0.1 is not an integer operation. On TRUNCATE during rebuild, they become true integers.

**L3 Detail — Team Split:** Frequencies are per-team (`team_id`). When a team is deleted, its frequencies are merged into the global (null `team_id`) pool in `unlink()` — values are summed and rounded via `float_round(..., precision_digits=0, rounding_method='HALF-UP')`. This preserves historical data.

---

### 9. crm.lead.scoring.frequency.field (PLS Field Config)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Related from `field_id.field_description` |
| `field_id` | Many2one | `ir.model.fields` for `crm.lead` |
| `color` | Integer | Display color (random 1-11) |

---

### 10. calendar.event Extension

**File:** `odoo/addons/crm/models/calendar.py`

| Field | Type | Description |
|-------|------|-------------|
| `opportunity_id` | Many2one | Linked opportunity (domain: `type='opportunity'`) |

**L3 Detail — Default Context:** `default_get()` checks `default_opportunity_id` in context and sets `res_model`/`res_id` accordingly. `create()` logs a meeting message on the linked opportunity via `log_meeting()`.

**`_is_crm_lead()`** — Helper checking if the current context/defaults target a CRM lead (checks both `res_model` string and `res_model_id`).

---

### 11. res.partner Extension

**File:** `odoo/addons/crm/models/res_partner.py`

| Field | Type | Description |
|-------|------|-------------|
| `opportunity_ids` | One2many | Opportunities linked to this partner |
| `opportunity_count` | Integer | Count of opportunities (recursive up hierarchy) |

**L3 Detail — Recursive Hierarchy Count:** `_compute_opportunity_count` walks the partner hierarchy using `_fetch_children_partners_for_hierarchy()` to count opportunities at all levels (parent and children). Uses `_read_group` aggregation to avoid N+1 queries.

---

## Predictive Lead Scoring (PLS)

**L4 Overview:** PLS uses a Naive Bayes classifier over historical won/lost leads. The frequency table stores, per team, how many times each field value co-occurred with a won vs. lost outcome. Probabilities are computed on-demand or via cron rebuild.

### Naive Bayes Formula

```
P(Won | A, B, ...) = S(Won | A) × S(Won | B) × ... × P(Won) / denominator
```

Where `S(Won | X) = won_count(X) / (won_count(X) + lost_count(X) + 0.1)` (Laplace smoothing)

Final probability: `s_won / (s_won + s_lost)`, clamped to [0.01, 99.99]

### Stage Handling in PLS

- **Won:** All stages are incremented (a lead in stage 3 that won spent time in stages 1, 2, 3)
- **Lost:** Only current stage and previous stages are incremented (a lead lost in stage 3 was eliminated at stage 3, but also passed through 1 and 2)

### Tag Frequency Threshold

Tags with fewer than 50 combined won+lost occurrences are ignored in probability computation. This prevents rare tags from skewing results on small datasets.

### Cron: `_cron_update_automated_probabilities`

Runs in 3 phases:
1. **TRUNCATE** frequency table (SQL, fast) — wrapped in try/except AccessError for cron security
2. **Rebuild** frequencies from all won/lost leads since `pls_start_date` via `_rebuild_pls_frequency_table()`
3. **Recompute** probabilities in batches of 50,000 leads (`PLS_COMPUTE_BATCH_STEP`)

Update batching: `PLS_UPDATE_BATCH_STEP = 5000`. Each batch is a separate transaction to avoid long locks. Uses `float_compare` for safe floating-point comparisons. Groups leads by identical probability value — each unique probability group gets one direct SQL UPDATE.

### Config Parameters

| Parameter | Key | Purpose |
|-----------|-----|---------|
| `crm.pls_start_date` | `crm.pls_start_date` | Only consider leads created after this date |
| `crm.pls_fields` | `crm.pls_fields` | Comma-separated field names for scoring |
| `crm.lead.auto.assignment` | `crm.lead.auto.assignment` | Enable rule-based assignment |

### `_pls_get_safe_fields()` — Field Validation

```python
def _pls_get_safe_fields(self):
    pls_fields_config = self.env['ir.config_parameter'].sudo().get_param('crm.pls_fields')
    pls_fields = pls_fields_config.split(',') if pls_fields_config else []
    pls_safe_fields = [field for field in pls_fields if field in self._fields.keys()]
    return pls_safe_fields
```

**L4 Security:** This method validates that configured field names actually exist on the model. Without this, a malformed `crm.pls_fields` value could cause SQL errors. The fields list is always prefixed with `["stage_id", "team_id"]` by `_pls_get_lead_pls_values()` — these two fields are always included in scoring regardless of config.

### `_pls_get_lead_pls_values()` — Value Extraction

This method builds a dict `{lead_id: {'values': [...], 'team_id': ...}}` mapping each lead to its scored field values. Two paths:

1. **Domain path (batch mode):** Uses direct SQL queries with `_search` and `SELECT id, probability, <fields>` to fetch all leads at once. Tag values are fetched via a separate LEFT JOIN on `crm_tag_rel`. This is used by the cron rebuild for performance.
2. **ORM path (live mode):** Iterates leads one-by-one using the ORM. Used for single-lead updates (onchange, write). Falls back to ORM when no domain is provided.

**L4 Performance:** In batch mode, the SQL query orders by `team_id ASC, id DESC` — this groups leads by team before processing, which aligns with how frequency table lookups are structured (team-specific frequencies first, global fallback second).

### `_pls_update_frequency_table()` — Atomic Updates

For each team, the method issues exactly one UPDATE or CREATE query per unique (field, value) pair across all leads in the batch. It handles both increment and decrement (live mode vs. rebuild mode) via a `step` multiplier. Values below 0.1 are set to exactly 0.1 to maintain Laplace smoothing.

**L4 Edge Case — Frequency Floor:** Every time a count would drop below 0.1, it is clamped to 0.1 instead of going to 0. This prevents division-by-zero in the Naive Bayes formula. During team unlink migration, the same floor applies via `float_compare(new_count, 0.1, 2) == 1` — only values that round to > 0.1 are kept.

---

## Wizard Models

### 1. CrmLeadLost (`crm_lead_lost.py`)

```python
class CrmLeadLost(models.TransientModel):
    lead_ids = fields.Many2many('crm.lead')
    lost_reason_id = fields.Many2one('crm.lost.reason')
    lost_feedback = fields.Html('Closing Note')
```

**`action_lost_reason_apply()`**
- If `lost_feedback` is non-empty, appends it to lead messages via `_track_set_log_message` using Markup-safe HTML
- Calls `lead_ids.action_set_lost(lost_reason_id=...)`
- This triggers `_handle_won_lost` → `_pls_increment_frequencies(from_state='lost')` to decrement the frequency table

**L3 Detail:** `lead_ids` uses `context={'active_test': False}` to allow marking archived leads as lost from the archive view.

### 2. CrmLead2opportunityPartner (`crm_lead_to_opportunity.py`)

Single-lead conversion wizard. Key fields:
- `name`: `'convert'` or `'merge'` (computed from duplicate count)
- `action`: `'create'` or `'exist'`
- `duplicated_lead_ids`: Other leads for the same partner (for merge)
- `force_assignment`: Override existing user assignment

**`action_apply()`** dispatches to `_action_merge()` or `_action_convert()`.

**Merge path:** Calls `merge_opportunity(auto_unlink=False)`, then unlinks tails. Handles the case where the result opportunity is still a lead (converts it).

**Convert path:** Calls `_convert_and_allocate()` → `_convert_handle_partner()` → `_handle_partner_assignment()` → `convert_opportunity()`.

**L3 Detail — `default_get()`:** Supports `active_id/active_model` in addition to `default_lead_id` for flexible window action definitions. Raises `UserError` if the lead is already closed (probability = 100).

### 3. CrmLead2opportunityPartnerMass (`crm_lead_to_opportunity_mass.py`)

Mass conversion wizard extending the single one:
- `lead_tomerge_ids`: Active leads from context (`default=lambda self: active_ids`)
- `user_ids`: Multiple salespeople for round-robin
- `deduplicate`: Boolean to auto-merge duplicates before conversion
- `action='each_exist_or_create'`: Per-lead partner matching via `_find_matching_partner()`
- `force_assignment`: defaults to `False` (different from single wizard)

**`action_mass_convert()`** runs deduplication first (grouping by partner+email, merging groups with 2+ leads), then calls `action_apply()`. The final lead list preserves original `active_ids` ordering for merged leads.

**L3 Detail — Partner Override:** `_convert_handle_partner()` is overridden to always call `_find_matching_partner()` per-lead when `action == 'each_exist_or_create'`, ignoring the wizard's shared `partner_id`.

### 4. CrmMergeOpportunity (`crm_merge_opportunities.py`)

Simple merge wizard. Filters out won opportunities from `default_get`. Calls `merge_opportunity(user_id, team_id)`.

**`default_get()`** uses `won_status != 'won'` filter. Note: this uses the computed `won_status` field, not `probability == 100`, so archived leads with `probability > 0` are still mergeable.

### 5. CrmLeadPlsUpdate (`crm_lead_pls_update.py`)

```python
class CrmLeadPlsUpdate(models.TransientModel):
    pls_start_date = fields.Date(required=True, default=_get_default_pls_start_date)
    pls_fields = fields.Many2many('crm.lead.scoring.frequency.field', default=_get_default_pls_fields)
```

**`action_update_crm_lead_probabilities()`**
- Requires admin (`_is_admin()`)
- Updates `crm.pls_fields` and `crm.pls_start_date` ir.config_parameter
- Triggers `_cron_update_automated_probabilities()` immediately (via `sudo()`)
- Field names are stored as comma-separated string in `crm.pls_fields`

**L3 Detail:** `_get_default_pls_fields()` resolves field names from config back to `crm.lead.scoring.frequency.field` records by searching `ir.model.fields` then joining to the frequency field model.

---

## Key Computed Logic

### Won Status Computation

```python
won_status = 'won'   if probability == 100 and stage_id.is_won
won_status = 'lost'  if active == False and probability == 0
won_status = 'pending' otherwise
```

**L4 Edge Case:** A lead with `probability=100` in a non-won stage is `'pending'`. A lead with `active=False` but `probability>0` is also `'pending'` — the lead is archived but not formally lost.

### Probability Cascade

1. `stage_id` changes → `write()` hook sets `probability=100` if new stage is won
2. `_compute_probabilities()` recalculates from PLS if `is_automated_probability`
3. `_handle_won_lost()` updates frequency table

**L4 Edge Case — Won Stage → Won Stage:** When moving between two won stages, `date_closed` is preserved (not overwritten) — `vals.pop('date_closed', False)`.

### Partner Sync Rules

`PARTNER_ADDRESS_FIELDS_TO_SYNC`: Sync ALL or NONE to avoid mixing addresses. If any address field is set on partner, sync all 6 fields. Otherwise keep lead values.

`PARTNER_FIELDS_TO_SYNC`: Sync `lang`, `phone`, `function`, `website` if set on partner.

---

## Security

### Access Groups

| Group | Access |
|-------|--------|
| `base.group_user` | Basic lead/opportunity CRUD |
| `crm.group_use_lead` | Can create leads (vs. opportunities only) |
| `crm.group_use_recurring_revenues` | Can see recurring revenue fields |
| `sales_team.group_sale_manager` | Full access, lead assignment, team management |
| `sales_team.group_sale_salesman` | Own leads/opportunities |

### Record Rules

Managed via `crm_security.xml` and `ir.model.access.csv`. Key rules:
- Salespeople see their own leads + team leads
- Managers see all leads in their teams

### Multi-Company

- `company_id` on leads enables record-rule filtering by company
- `_check_company_auto = True` on `crm.lead` validates company consistency on partner assignment
- Frequency table is NOT company-scoped — PLS treats all companies together (by design, for statistical relevance)

### L4 Security — PLS Frequency Table

The frequency table (`crm.lead.scoring.frequency`) is **not restricted by company**. This is intentional: PLS requires a minimum sample size for statistical validity, and most Odoo deployments have fewer companies than leads. Company-specific scoring would produce unreliable probabilities on small datasets.

**L4 Security — Cron Access:** The PLS rebuild cron (`_cron_update_automated_probabilities`) wraps the TRUNCATE in a try/except AccessError, re-raising as `UserError` with a readable message. This prevents a poorly timed cron run from causing a hard error visible only in logs.

---

## IAP Enrichment Integration

CRM integrates with IAP services via optional modules:

| Module | Feature |
|--------|---------|
| `crm_iap_enrich` | Auto-enrich leads with company data from email |
| `crm_iap_mine` | Generate new leads based on criteria |
| `website_crm_iap_reveal` | Reveal website visitors as leads |

**L3 Detail — Enrichment Flow:** When `lead_enrich_auto='auto'` (config parameter `crm.iap.lead.enrich.setting`), leads without company data trigger an IAP call on creation. The IAP service returns company info (industry, size, revenue) which populates lead fields. If `lead_enrich_auto='manual'`, enrichment is on-demand only.

**Settings Fields (ResConfigSettings):**
- `module_crm_iap_mine` — Toggle lead generation module
- `module_crm_iap_enrich` — Toggle enrichment module
- `module_website_crm_iap_reveal` — Toggle website reveal module
- `lead_enrich_auto` — `'manual'` or `'auto'`
- `lead_mining_in_pipeline` — Show lead mining button in pipeline

---

## Cron Jobs

| Cron | Model | Schedule | Purpose |
|------|-------|----------|---------|
| `ir_cron_crm_lead_assign` | `crm.team` | Daily (default, inactive) | Lead auto-assignment |
| `_cron_update_automated_probabilities` | `crm.lead` | Manually via wizard or scheduled | PLS rebuild |

The `ir_cron_crm_lead_assign` cron is created in `data/ir_cron_data.xml` but is **inactive by default** (`active=False`). It is activated via Settings → CRM → Rule-Based Assignment → Auto Assignment.

**L4 Performance — Cron Frequency:** The assignment cron defaults to daily but can be changed to "Repeatedly" (e.g., every hour) via `crm_auto_assignment_action` in settings. The `BUNDLE_COMMIT_SIZE` of 100 means the cron auto-commits every 100 leads, preventing long transactions on large databases.

---

## L4 Deep Dive: Lead Assignment Algorithm

The assignment algorithm (`_allocate_leads` + `_assign_and_convert_leads`) uses a weighted random team allocation followed by round-robin member distribution.

**Phase 1 — Team Allocation:**
```
population = [team for team in teams if team.assignment_max > 0]
weights = [team.assignment_max for team in population]
while population:
    team = random.choices(population, weights)[0]
    lead = team.leads[0]  # FIFO from search order
    assign team, deduplicate
    if no more leads for team: remove from population
```

**Phase 2 — Member Assignment:**
```
for team in teams_with_members:
    members = sorted by quota desc (least assigned first)
    for lead in unassigned_leads:
        for member in members (circular):
            if lead matches member.assignment_domain:
                assign lead to member
                if member.quota_exceeded: remove from circular list
```

**L4 Edge Cases:**
- `creation_delta_days=7` means only leads created in the last 7 days are allocated to teams. Older unassigned leads are skipped.
- `BUNDLE_HOURS_DELAY` (default 0) adds a delay before newly created leads are eligible — allows automation rules to run first.
- Duplicate detection before team assignment prevents assigning duplicate leads to different teams.
- `auto_commit` is disabled in test mode (`modules.module.current_test`) to allow transaction rollback.
- The cron deduplicates leads by partner email before assigning, merging groups with 2+ duplicates via `merge_opportunity()` before the final lead list is built.

---

## L4 Deep Dive: Rainbowman Gamification

`_get_rainbowman_message()` triggers on `action_set_won_rainbowman()` and checks multiple achievement conditions in priority order:

1. First deal of the year → "Go, go, go! Congrats for your first deal."
2. Team record (30 days) → "Boom! Team record for the past 30 days."
3. Team record (7 days) → "Yeah! Best deal out of the last 7 days for the team."
4. Personal record (31 days) → "You just beat your personal record for the past 30 days."
5. Personal record (7 days) → "You just beat your personal record for the past 7 days."
6. Fifth deal today → "You're on fire! Fifth deal won today"
7. 3-day winning streak → "You're on a winning streak. 3 deals in 3 days, congrats!"
8. Fastest close in 30 days → "Wow, that was fast. That deal didn't stand a chance!"
9. Direct stage-to-won → "No detours, no delays - from New straight to the win!"
10. First win in country → "You just expanded the map! First win in [country]."
11. First win from UTM source → "Yay, your first win from [source]!"

**L4 Performance:** The method executes a raw SQL query with 12+ aggregated SQL CASE expressions. It runs on every won action. Consider caching at the team/user level if performance becomes an issue.

**L4 Edge Case — Country/Source Expansion:** The "first win" messages (country, UTM source) require `country_id` and `source_id` to be set on the lead. If either is missing, those achievements are skipped silently in the SQL.

---

## L4 Deep Dive: Mail Thread Integration

**`message_new()` override** removes the default author (gateway user = root) when processing incoming emails. This ensures lead assignment is handled by the assignment algorithm or team leader logic, not the mail gateway user.

**`_message_post_after_hook()`** auto-links partners to leads based on email matching after a message is posted via the Suggested Recipient mechanism. This handles the common case where a lead's email is known but no partner record exists.

**Reply-to override (`_notify_get_reply_to`)** routes replies to the sales team's alias instead of the lead's owner, ensuring team-level email handling.

**L4 Edge Case — Suggested Recipient:** The auto-link only works if the incoming email's author has a corresponding `res.partner` record. Unrecognized senders create anonymous leads. The `_find_matching_partner()` call uses `email_normalized` for exact matching.

---

## L4 Deep Dive: Search Ordering with Activities

`search_fetch()` is overridden to support ordering on `my_activity_date_deadline`. The two-step algorithm:

1. **Step 1:** Read group on `mail.activity` to get lead→deadline mapping. Search leads matching domain + having activities, order by deadline.
2. **Step 2:** If limit not reached, search remaining leads (excluding already-scanned IDs) with original domain and ordering.

**L4 Edge Case:** The offset handling calculates `lead_offset = max((offset - len(search_res), 0))`. If the first step returns fewer results than the offset, the second step starts from 0.

**L4 Edge Case — Partial Coverage:** If Step 1 returns exactly `N` results and offset is `N+5`, the second step correctly starts from 0 (all remaining results are "before" the offset in the combined ordering). This is a subtle but correct behavior.

---

## L4 Deep Dive: Team Unlink Frequency Migration

When a `crm.team` is deleted, `unlink()` migrates its PLS frequencies to the global pool:

```python
# For each frequency record of the team:
exist_won_count = float_round(existing.won_count, precision_digits=0, rounding_method='HALF-UP')
exist_lost_count = float_round(existing.lost_count, precision_digits=0, rounding_method='HALF-UP')
add_won_count = float_round(frequency.won_count, precision_digits=0, rounding_method='HALF-UP')
add_lost_count = float_round(frequency.lost_count, precision_digits=0, rounding_method='HALF-UP')
new_won = exist_won_count + add_won_count
new_lost = exist_lost_count + add_lost_count
# Minimum value is 0.1 to maintain Laplace smoothing (float_compare threshold)
match.won_count = new_won if float_compare(new_won, 0.1, 2) == 1 else 0.1
match.lost_count = new_lost if float_compare(new_lost, 0.1, 2) == 1 else 0.1
```

**L4 Detail:** Uses `float_round(..., precision_digits=0, rounding_method='HALF-UP')` instead of Python's built-in `round()` for PostgreSQL-compatible behavior. The `float_compare(new_count, 0.1, 2)` with precision_digits=2 ensures values like 0.1, 0.2, etc. are treated as void-like and clamped to 0.1. This preserves statistical history even when teams are restructured.

---

## L4 Deep Dive: ir.config_parameter → Model Registry Bridge

The `ir.config_parameter` model is extended to trigger model re-setup when `crm.pls_fields` changes:

```python
def write(self, vals):
    result = super().write(vals)
    if any(record.key == "crm.pls_fields" for record in self):
        self.env.flush_all()
        self.env.registry._setup_models__(self.env.cr, ['crm.lead'])
    return result

@api.model_create_multi
def create(self, vals_list):
    records = super().create(vals_list)
    if any(record.key == "crm.pls_fields" for record in records):
        self.env.flush_all()
        self.env.registry._setup_models__(self.env.cr, ['crm.lead'])
    return records

def unlink(self):
    pls_emptied = any(record.key == "crm.pls_fields" for record in self)
    result = super().unlink()
    if pls_emptied and not self.env.context.get(MODULE_UNINSTALL_FLAG):
        self.env.flush_all()
        self.env.registry._setup_models__(self.env.cr, ['crm.lead'])
    return result
```

**L4 Purpose:** PLS field changes modify which fields contribute to scoring. The registry reset (`_setup_models__`) invalidates the model's field cache, ensuring new fields are immediately usable in `_pls_get_safe_fields()` without a server restart. The `MODULE_UNINSTALL_FLAG` check prevents triggering this during module upgrades/uninstalls where the registry is being rebuilt anyway.

**L4 Edge Case — Module Uninstall:** During `base.update_module` (upgrade/uninstall), the registry is rebuilt from scratch, so the model re-setup hook is skipped to avoid redundant work.

---

## L4 Deep Dive: Odoo 18 to 19 PLS Changes

Key changes between Odoo 18 and Odoo 19 in the PLS / CRM module:

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| `team_id` in PLS | Possibly optional | Always included in `pls_fields` via `_pls_get_lead_pls_values()` prefixing `["stage_id", "team_id"]` |
| Frequency count type | Float `digits=(16,1)` | Same — unchanged |
| Batch update constant | `max_leads_per_update` | Renamed to `PLS_UPDATE_BATCH_STEP = 5000` |
| Probability clamp range | [0.01, 99.99] | Same |
| Tag threshold | 50 combined | Same |

**L4 Detail — team_id Always Scored:** In Odoo 19, `_pls_get_lead_pls_values()` always prefixes the PLS field list with `["stage_id", "team_id"]`, making team-specific scoring the default. This means PLS probabilities naturally adapt to team-specific historical win rates.

---

## File Structure Summary

```
Module files: 19 model files + 5 wizard files + 14 XML data/views + 1 manifest
Total Python: ~3,800 lines across models
JavaScript: web/assets_backend (kanban, forecast views)
Reports: crm_activity_report, crm_opportunity_report
```

**Source Module**: `odoo/addons/crm`
**Last Updated**: 2026-04-11
