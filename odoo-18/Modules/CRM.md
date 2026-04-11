---
Module: crm
Version: Odoo 18
Type: Core
Tags: [crm, sales, leads, opportunity, pipeline, scoring, assignment]
---

# CRM — Customer Relationship Management

Customer Relationship Management core module. Manages the complete lead-to-opportunity lifecycle including predictive lead scoring, round-robin assignment, team-based territories, recurring revenue tracking, and win/loss analytics. Inherits heavily from `mail.thread`, `mail.activity.mixin`, and `utm.mixin`.

**Module path:** `~/odoo/odoo18/odoo/addons/crm/`
**Model count:** ~19 models across `models/` and `report/`
**Key mixins inherited:** `mail.thread.cc`, `mail.thread.blacklist`, `mail.thread.phone`, `mail.activity.mixin`, `utm.mixin`, `format.address.mixin`, `mail.tracking.duration.mixin`

---

## Models

### `crm.lead` — Lead / Opportunity

Core model for both **Leads** (unqualified prospects) and **Opportunities** (qualified deals). Single model with `type` field distinguishing the two. Heavily instrumented with mail thread, phone, blacklist, and activity tracking.

**Inheritance:** `mail.thread.cc` + `mail.thread.blacklist` + `mail.thread.phone` + `mail.activity.mixin` + `utm.mixin` + `format.address.mixin` + `mail.tracking.duration.mixin`
**_primary_email:** `email_from`
**_track_duration_field:** `stage_id`

#### Field Inventory

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Opportunity title; required; computed from partner if empty (`_compute_name`) |
| `type` | Selection | `lead` or `opportunity`; default based on `crm.group_use_lead` group |
| `active` | Boolean | Soft delete; default `True`; archiving sets probability=0 |
| `priority` | Selection | `0`=Low, `1`=Medium, `2`=High, `3`=Very High |
| `color` | Integer | Color index for kanban |
| **Ownership** | | |
| `user_id` | Many2one(res.users) | Assigned salesperson; domain `share=False`; triggers `team_id` recompute |
| `team_id` | Many2one(crm.team) | Sales team; computed from user membership (`_compute_team_id`); precompute+store |
| `user_company_ids` | Many2many(res.company) | UX compute: lead's company or all if no company |
| `company_id` | Many2one(res.company) | Operating company; coherent with user/team/partner hierarchy |
| `lead_properties` | Properties | Team-defined custom properties using `team_id.lead_properties_definition` |
| **Pipeline** | | |
| `stage_id` | Many2one(crm.stage) | Pipeline stage; computed from team+type (`_compute_stage_id`); domain filters by team |
| `tag_ids` | Many2many(crm.tag) | Classification tags |
| `date_last_stage_update` | Datetime | Last stage change; auto-updated on stage change |
| `date_open` | Datetime | Assignment date; set when `user_id` assigned (`_compute_date_open`) |
| `day_open` | Float | Days from creation to assignment (`_compute_day_open`) |
| `day_close` | Float | Days from creation to close (`_compute_day_close`) |
| **Revenue** | | |
| `expected_revenue` | Monetary | Expected revenue; currency from `company_currency` |
| `prorated_revenue` | Monetary | `expected_revenue * probability / 100` (`_compute_prorated_revenue`) |
| `recurring_plan` | Many2one(crm.recurring.plan) | Subscription billing cycle |
| `recurring_revenue` | Monetary | Total recurring revenue |
| `recurring_revenue_monthly` | Monetary | `recurring_revenue / recurring_plan.number_of_months` |
| `recurring_revenue_monthly_prorated` | Monetary | Monthly MRR weighted by probability |
| `recurring_revenue_prorated` | Monetary | Total recurring revenue weighted by probability |
| `company_currency` | Many2one(res.currency) | Computed from `company_id` |
| **Probability** | | |
| `probability` | Float | Overall probability; SQL constraint `[0, 100]`; stored; `aggregator="avg"` |
| `automated_probability` | Float | Naive Bayes PLS prediction; computed + stored |
| `is_automated_probability` | Boolean | True when `probability == automated_probability`; indicates auto-synced |
| **Contact** | | |
| `partner_id` | Many2one(res.partner) | Linked customer; check_company |
| `partner_is_blacklisted` | Boolean | Related to `partner_id.is_blacklisted` |
| `partner_email_update` | Boolean | Compute: will lead email update partner? |
| `partner_phone_update` | Boolean | Compute: will lead phone update partner? |
| `is_partner_visible` | Boolean | True if type=opportunity, partner set, or debug mode |
| `contact_name` | Char | First name of contact; computed from partner unless is_company |
| `partner_name` | Char | Company name; computed from `parent_id.name` or partner.name if is_company |
| `function` | Char | Job title; synced from partner |
| `title` | Many2one(res.partner.title) | Contact honorific |
| `email_from` | Char | Primary email; trigram indexed; `_inverse_email_from` writes back to partner |
| `email_normalized` | Char | Inherited from `mail.thread.blacklist`; trigram indexed |
| `email_domain_criterion` | Char | IAP domain search key (`iap_tools.mail_prepare_for_domain_search`); btree_not_null indexed |
| `email_state` | Selection | `correct`/`incorrect`; computed via `mail_validation.mail_validate` |
| `phone` | Char | Phone number; inverse writes back to partner; phone-format validated |
| `mobile` | Char | Mobile; phone-format validated |
| `phone_sanitized` | Char | Inherited from `mail.thread.phone`; digits-only; btree_not_null indexed |
| `phone_state` | Selection | `correct`/`incorrect`; via `phone_validation.phone_parse` |
| `website` | Char | Website; cleaned via `res.partner._clean_website` on write |
| `lang_id` | Many2one(res.lang) | Language; synced from partner |
| `lang_code` | Char | Related to `lang_id.code` |
| `lang_active_count` | Integer | Number of active languages installed |
| **Address** | | |
| `street`, `street2`, `city`, `zip` | Char | Address; computed via `_compute_partner_address_values` |
| `state_id` | Many2one(res.country.state) | State; domain `country_id` |
| `country_id` | Many2one(res.country) | Country |
| **Dates** | | |
| `date_closed` | Datetime | Actual close date; set when probability reaches 100 or lead archived |
| `date_deadline` | Date | Expected closing date; user-set estimate |
| `date_conversion` | Datetime | Conversion date (lead to opportunity) |
| `date_automation_last` | Datetime | Last action date |
| `create_date` | Datetime | Record creation |
| **UTM** | | |
| `campaign_id` | Many2one(utm.campaign) | ondelete='set null' |
| `medium_id` | Many2one(utm.medium) | ondelete='set null' |
| `source_id` | Many2one(utm.source) | ondelete='set null' |
| **Won/Loss** | | |
| `lost_reason_id` | Many2one(crm.lost.reason) | Set when archived/lost; ondelete='restrict' |
| **Statistics** | | |
| `calendar_event_ids` | One2many(calendar.event) | Linked meetings (inverse via `opportunity_id`) |
| `duplicate_lead_ids` | Many2many(crm.lead) | Potential duplicates; computed via email domain, commercial partner, phone |
| `duplicate_lead_count` | Integer | Count of `duplicate_lead_ids` |
| `meeting_display_date` | Date | Next or last meeting date |
| `meeting_display_label` | Char | `"Next Meeting"` / `"Last Meeting"` / `"No Meeting"` |
| `referred` | Char | Referring contact name |

**SQL Constraints:**
```sql
check_probability: probability >= 0 AND probability <= 100
```

**Database indexes:**
- `crm_lead_user_id_team_id_type_index` on `(user_id, team_id, type)`
- `crm_lead_create_date_team_id_idx` on `(create_date, team_id)`
- `email_normalized` trigram
- `email_domain_criterion` btree_not_null
- `phone_sanitized` btree_not_null

#### Computed Field Details

**`_compute_team_id`** — When user changes, recompute team:
- If current `team_id` still contains the new `user_id` (via `member_ids` or `user_id`), keep it
- Otherwise call `crm.team._get_default_team_id(user_id, domain)` using team domain based on `type` (lead→`use_leads`, opp→`use_opportunities`)

**`_compute_company_id`** — Cascading logic:
1. Invalidate if `user_id` not in user's companies, or `team_id.company_id` mismatched
2. Propose in priority: `team.company_id > user.company_id (intersect with context) > partner.company_id`
3. Void if no team and no user with no partner

**`_compute_probabilities`** — Triggered by `stage_id` or `team_id` or any PLS-safe field:
1. Call `_pls_get_naive_bayes_probabilities()` to get dict of `{lead_id: automated_probability}`
2. For leads that were `active` and had `is_automated_probability=True` (probability was auto-synced), sync `probability = automated_probability`

**`_compute_potential_lead_duplicates`** — Three-pronged search (using `sudo()` + `active_test=False`):
1. **Email domain match:** `email_domain_criterion = ...` (max 21 results)
2. **Commercial partner hierarchy:** `partner_id` child of `commercial_partner_id` (all matches)
3. **Phone match:** `phone_sanitized = ...` (max 21 results)

Threshold: if search returns ≥21 results, return empty recordset (indicates non-selective / non-relevant match).

**`_compute_partner_email_update` / `_compute_partner_phone_update`** — Inverse logic:
- Synced if `partner_id` exists AND email/phone on lead differs from partner
- On lead write: inverse writes back to `partner_id.email` / `partner_id.phone`
- `force_void=False` prevents propagating void lead values to a valid partner

#### Key Methods

**Win/Loss State Machine:**

- **`_handle_won_lost(vals)`** — Called in `create()` and `write()` when `active` or `stage_id` changes:
  - Classifies leads: `leads_reach_won`, `leads_leave_won`, `leads_reach_lost`, `leads_leave_lost`
  - Calls `_pls_increment_frequencies()` for each category with appropriate `from_state`/`to_state`
  - Stage change to `is_won` stage: sets `probability=100, automated_probability=100, date_closed=now`
  - Probability=100 or active=False: sets `date_closed=now`
  - Probability=0 with active=True (lost): `date_closed` cleared

- **`action_set_won()`** — Manual mark-won:
  - Groups leads by their won stage (finds next higher-sequence won stage, or last won stage)
  - Writes `stage_id` + `probability=100` per group
  - Triggers frequency increment via `_handle_won_lost`

- **`action_set_lost()`** — Archive the lead:
  - Calls `action_archive()` → sets `probability=0`
  - Optionally writes `additional_values` (e.g. `lost_reason_id`)
  - Frequency increment via `_handle_won_lost`

- **`toggle_active()`** — Restore archived lead:
  - If reactivated: clears `lost_reason_id`, recomputes probabilities
  - If archived: sets `probability=0, automated_probability=0`

**Stage Management:**

- **`_stage_find(team_id, domain, order, limit)`** — Find best stage for lead:
  - Collects all team_ids from current leads + optional `team_id` param
  - Domain: `team_id` in teams OR `team_id=False`
  - Adds additional domain filters

- **`_read_group_stage_ids`** — Kanban group expansion:
  - Reads team from context `default_team_id`
  - Includes stages for current team (even if folded), plus all-team stages

**Merge:**

- **`_merge_opportunity(user_id, team_id, auto_unlink, max_length=5)`** — Core merge algorithm:
  - Validates ≥2 records; enforces `max_length` unless superuser
  - Sorts by confidence: `type=opportunity > type=lead`, then higher stage sequence, higher probability, newer ID
  - Head = highest confidence; tail = all others
  - `_merge_data()`: text concatenates, m2o takes first-not-null, m2m skipped
  - Address fields: source lead with most non-empty address fields
  - Specific: `description` joins with `<br/><br/>`, `type` = `opportunity` if any opp, `priority` = max, `tag_ids` = union, `lost_reason_id` = first not-null only if probability=0
  - Validates merged stage belongs to target team
  - Transfers messages, activities, attachments, calendar events, active followers (posted last 30 days)
  - Logs merge summary as chatter message via `crm.crm_lead_merge_summary` template
  - Auto-unlink tail with `sudo()` to bypass ACL

**Convert:**

- **`convert_opportunity(partner, user_ids, team_id)`** — Convert lead to opportunity:
  - Sets `type='opportunity'`, `date_conversion=now`, updates partner
  - Calls `_stage_find()` if stage not set
  - Then calls `_handle_salesmen_assignment(user_ids, team_id)`

- **`_handle_salesmen_assignment(user_ids, team_id)`** — Round-robin assignment:
  - `user_ids` list iterated with step pattern: `lead_ids[idx::steps]`
  - Pass 1: indices 0, step, 2*step... → first user
  - Pass 2: indices 1, 1+step... → second user
  - Avoids ORM overhead by batching with `browse().write()`

**Duplicate Detection:**

- **`_get_lead_duplicates(partner, email, include_lost)`** — Search for duplicates:
  - Normalizes all email addresses from `email_from`
  - OR-match on normalized emails, AND-match on partner_id
  - `include_lost=False`: excludes active=false or is_won stage leads
  - `include_lost=True`: includes archived leads (active_test=False)
  - Active if: active=True AND (no stage OR stage not won)

**Customer Creation:**

- **`_create_customer()`** — Creates partner from lead:
  - If `partner_name` set → creates company (is_company=True)
  - If contact_name → creates contact under that company (or standalone if no company)
  - Parses `email_from` for name if `contact_name` missing
  - Falls back to `name` as contact name

- **`_find_matching_partner(email_only)`** — Searches existing partner:
  - Exact email match first
  - Then ilike on `partner_name` > `contact_name` > `name`

#### L4: Predictive Lead Scoring (Naive Bayes PLS)

**Architecture:** Two-mode system — **Live Increment** (on every won/lost) + **One-Shot Rebuild** (cron, `crm.lead.scoring.frequency` table).

**Frequency Table (`crm.lead.scoring.frequency`):**
- Per `team_id`, per `variable` (field name), per `value` (field value bucket)
- `won_count` and `lost_count` (Float, +0.1 smoothing to avoid zero-frequency)
- Used for both computation and live increment

**Configuration via `ir.config_parameter`:**
- `crm.pls_start_date` — Earliest date for historical lead data inclusion (Char date string)
- `crm.pls_fields` — Comma-separated field names for scoring criteria

**Naive Bayes Computation (`_pls_get_naive_bayes_probabilities`):**
1. Get all lead PLS values (stage_id, team_id, plus configured fields + tag_ids)
2. Build frequency index per team and per `-1` (no-team aggregate)
3. For each lead:
   - Skip if no `stage_id` → probability 0
   - Skip if won stage → probability 100
   - Team lookup: exact team_id or -1 fallback
   - Compute `p_won = team_won / team_total`, `p_lost = team_lost / team_total`
   - For each field/value: multiply `p_won` by `won_count / field_won_total`; multiply `p_lost` by `lost_count / field_lost_total`
   - Tag handling: only counts if `won+lost >= 50` (minimum statistical significance)
   - Final: `probability = s_won / (s_won + s_lost)`, clamped to [0.01, 99.99]
4. Returns `{lead_id: probability}` dict

**Live Increment (`_pls_increment_frequencies`):**
- Called by `_handle_won_lost` BEFORE writing new values (so old state is known)
- For `from_state`: decrement (step=-1); for `to_state`: increment (step=1)
- Stage-specific: won → all stages incremented; lost → current stage and earlier only

**One-Shot Rebuild (`_cron_update_automated_probabilities`):**
- Cron: `crm.ir_cron_crm_lead_assign` (also used for lead assignment)
- TRUNCATEs `crm_lead_scoring_frequency` table, rebuilds from all closed leads
- Updates `automated_probability` + syncs `probability` for leads where both were aligned
- Batch size: compute 50,000 leads at a time; update 5,000 per transaction
- Auto-commits per batch to avoid table locks

#### L4: Lead Assignment — Team Round-Robin

**Trigger:** `crm_team._action_assign_leads()` called by `_cron_assign_leads()` (cron) or `action_assign_leads()` (manual).

**Phase 1: Team Allocation (`_allocate_leads`):**
1. For each team with `assignment_max > 0`, search unassigned leads:
   - `team_id=False AND user_id=False`
   - `stage_id` not won (probability not 0 or 100)
   - `create_date <= now - BUNDLE_HOURS_DELAY` (config: `crm.assignment.delay`, default 0h)
   - Matching `assignment_domain` filter
   - Created in last `creation_delta_days` days (default 7 for cron, 0 for manual)
2. For each lead: compute duplicates via `_get_lead_duplicates()`
3. Weighted random: teams selected proportional to `assignment_max`
4. For each selected lead:
   - `_allocate_leads_deduplicate()`: assigns team, merges duplicates
   - Duplicates merged via `_merge_opportunity()` with `auto_unlink=True`, `max_length=0`
   - Master lead receives team assignment

**Phase 2: Salesperson Assignment (`_assign_and_convert_leads`):**
1. Per team: sort members by quota (ascending) — members with fewer leads get more
2. Per lead sorted by `(-probability, id)`:
   - Find first member with `assignment_domain` matching lead (literal_eval)
   - Call `convert_opportunity()` with member's user_id
   - Quota check: if remaining quota > 0, append member back to list (round-robin)
3. Auto-commits every 100 leads

**Cron Configuration:** `crm.ir_cron_crm_lead_assign` runs daily by default. Config parameter `crm.assignment.commit.bundle` (default 100) controls commit size.

#### L4: Rainbowman Celebration

**`_get_rainbowman_message()`** — Triggered when a deal is marked won:
- SQL query for current year won deals
- Checks: first deal ever, team 30-day record, team 7-day record, personal 30-day record, personal 7-day record
- Message returned with SVG sprite URL for rainbow animation

#### Mail Thread Integration

- `_creation_subtype()` → `crm.mt_lead_create`
- `_track_subtype()`: `stage_id` (won)→`crm.mt_lead_won`, `lost_reason_id`→`crm.mt_lead_lost`, `stage_id`→`crm.mt_lead_stage`, `active`→`crm.mt_lead_restored`/`crm.mt_lead_lost`
- `_notify_get_recipients_groups()`: adds salesman actions (Convert/Mark Won/Mark Lost) based on type
- `_notify_get_reply_to()`: uses team alias if available
- `message_new()`: strips `default_user_id` for mail gateway (assigns automatically)
- `_message_post_after_hook()`: auto-links new partner if email matches after message post

---

### `crm.team` — Sales Team

Inherits `mail.alias.mixin` + `crm.team` (base). Represents a sales team with member management and lead assignment.

**Key Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Team name |
| `use_leads` | Boolean | Filter incoming as leads (qualification flow) |
| `use_opportunities` | Boolean | Manage pipeline opportunities (default True) |
| `alias_id` | Many2one(mail.alias) | Email gateway for this team |
| `alias_defaults` | Char | Eval'd dict for new leads from email |
| `member_ids` | Many2many(res.users) | Active members (inherits `crm.team.member`) |
| `crm_team_member_ids` | One2many(crm.team.member) | Full member record with assignment config |
| `assignment_enabled` | Boolean | Config param `crm.lead.auto.assignment` enabled |
| `assignment_auto_enabled` | Boolean | Cron `crm.ir_cron_crm_lead_assign` active |
| `assignment_optout` | Boolean | Skip this team in auto-assignment |
| `assignment_max` | Integer | Sum of all members' `assignment_max` |
| `assignment_domain` | Char | Additional filter for lead allocation |
| `lead_properties_definition` | PropertiesDefinition | Custom properties schema for leads |
| **Dashboard computes** | | |
| `lead_unassigned_count` | Integer | Leads with no user |
| `lead_all_assigned_month_count` | Integer | Leads assigned this month (sum of members) |
| `lead_all_assigned_month_exceeded` | Boolean | Count > assignment_max |
| `opportunities_count` | Integer | Active opportunities (probability<100) |
| `opportunities_amount` | Monetary | Total expected revenue |
| `opportunities_overdue_count` | Integer | Overdue opportunities |
| `opportunities_overdue_amount` | Monetary | Overdue expected revenue |

**Key Methods:**

- **`_compute_assignment_enabled`** — Reads `crm.lead.auto.assignment` config param + checks cron active state
- **`_constrains_assignment_domain`** — Validates domain by executing `crm.lead.search(domain, limit=1)`; raises `ValidationError` if malformed
- **`write()`** — Updates alias_name/defaults when `use_leads`/`use_opportunities` change
- **`unlink()`** — Migrates `crm.lead.scoring.frequency` records to `team_id=False` before deletion; rounded counts preserved with minimum 0.1
- **`_alias_get_creation_values()`** — Sets alias_model_id to `crm.lead`; defaults `type` based on `group_use_lead` + `use_leads`; defaults `team_id` to self

**Lead Assignment Actions:**

- `action_assign_leads()` — Manual trigger with notification
- `_action_assign_leads(force_quota, creation_delta_days)` — Permission-checked (manager/system only)
- `_allocate_leads(creation_delta_days)` — Team-level allocation
- `_allocate_leads_deduplicate(leads, duplicates_cache)` — Assign + merge duplicates
- `_assign_and_convert_leads(force_quota)` — Member-level distribution

**CRM Dashboard Graph Overrides:**

- `_graph_get_model()` → `crm.lead` when `use_opportunities`
- `_graph_date_column()` → `create_date`
- `_graph_y_query()` → `count(*)`
- `_extra_sql_conditions()` → `type LIKE 'opportunity'`
- `_compute_dashboard_button_name()` → `"Pipeline"` label

---

### `crm.team.member` — Team Member Assignment

Inherits `crm.team.member` (base). Extends team membership with lead assignment capacity.

**Key Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | Many2one(res.users) | Member user |
| `crm_team_id` | Many2one(crm.team) | Parent team |
| `assignment_enabled` | Boolean | Related from team |
| `assignment_domain` | Char | Filter for leads assignable to this member |
| `assignment_optout` | Boolean | Skip this member in auto-assignment |
| `assignment_max` | Integer | Average monthly lead capacity (default 30) |
| `lead_day_count` | Integer | Leads assigned in last 24h |
| `lead_month_count` | Integer | Leads assigned in last 30 days |

**`_get_assignment_quota(force_quota)`**:
- Daily quota = `assignment_max / 30`, rounded
- `force_quota=True` (manual action): returns full daily quota
- `force_quota=False` (cron): returns `daily_quota - lead_day_count` (remaining capacity)

---

### `crm.stage` — Pipeline Stage

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Stage name (required, translateable) |
| `sequence` | Integer | Ordering; lower is earlier |
| `is_won` | Boolean | Marks as won stage; used by `_handle_won_lost` and `action_set_won` |
| `requirements` | Text | Internal requirements tooltip text |
| `team_id` | Many2one(crm.team) | Team-specific stage; other teams cannot see |
| `fold` | Boolean | Folded in kanban when empty |
| `team_count` | Integer | Compute: total teams (UX only) |

**`_compute_team_count`** — `search_count([])` on `crm.team` (no domain). Used in kanban header.

**`default_get`**: strips `default_team_id` from context to avoid creating team-specific stage.

**`_read_group_stage_ids`**: returns stages for current team: `(id in stages) OR (team_id=False) OR (team_id=default_team_id AND fold=False)`.

---

### `crm.lost.reason` — Lost Reason Master Data

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Description (required, translateable) |
| `active` | Boolean | Soft delete |
| `leads_count` | Integer | Compute via `_read_group` with `active_test=False` |

**`_compute_leads_count`** — Uses `with_context(active_test=False)` to count archived leads too.

**`action_lost_leads()`** — Returns act_window for `crm.lead` filtered by this reason.

---

### `crm.lead.scoring.frequency` — Predictive Lead Scoring Frequency Table

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `variable` | Char | Field name (indexed) — e.g. `stage_id`, `team_id`, `country_id`, `tag_id` |
| `value` | Char | Field value as string — e.g. `1`, `12`, `True` |
| `won_count` | Float | Won frequency (0.1 smoothing offset applied) |
| `lost_count` | Float | Lost frequency (0.1 smoothing offset applied) |
| `team_id` | Many2one(crm.team) | Team-specific; ondelete='cascade' |

**Design notes:**
- Float used for `won_count`/`lost_count` because 0.1 increments are added (not integers) to avoid zero-frequency
- When team deleted: frequencies merged into `team_id=False` records; void-like records (both < 0.1) skipped
- Value column stores string representation for cross-field uniformity

---

### `crm.lead.scoring.frequency.field` — Configurable PLS Fields

Registry of fields available for predictive lead scoring computation.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Related `ir.model.fields.field_description` |
| `field_id` | Many2one(ir.model.fields) | Domain: `model_id.model = 'crm.lead'`; ondelete='cascade' |

Configured via Settings > CRM > Predictive Lead Scoring fields selection.

---

### `crm.recurring.plan` — Subscription Billing Plans

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Plan name (translateable) |
| `number_of_months` | Integer | Billing cycle length (>=0 constraint) |
| `active` | Boolean | Soft delete |
| `sequence` | Integer | Ordering |

Used to compute `recurring_revenue_monthly = recurring_revenue / number_of_months`.

---

### `crm.activity.report` — CRM Activity Pivot Analysis

**Type:** `base.models.ir_actions_report`? No — this is a manual SQL view.

**`_name:** `crm.activity.report`
**`_auto:** `False` (manual `init()`)

**View definition (SQL):**
```sql
SELECT m.id, l.create_date AS lead_create_date, l.date_conversion,
       l.date_deadline, l.date_closed, m.subtype_id, m.mail_activity_type_id,
       m.author_id, m.date, m.body, l.id AS lead_id, l.user_id, l.team_id,
       l.country_id, l.company_id, l.stage_id, l.partner_id, l.type AS lead_type,
       l.active
FROM mail_message m
JOIN crm_lead l ON m.res_id = l.id
WHERE m.model = 'crm.lead' AND m.mail_activity_type_id IS NOT NULL
```

**Fields:** date, lead_create_date, date_conversion, date_deadline, date_closed, author_id, user_id, team_id, lead_id, body, subtype_id, mail_activity_type_id, country_id, company_id, stage_id, partner_id, lead_type, active, tag_ids (m2m from lead).

Supports pivot, graph, and list views grouped by user, team, stage, country, etc.

---

## Wizard Models

### `crm.lead.to.opportunity` — Lead-to-Opportunity Convert Wizard

Located in `wizard/` directory. Standard O2M wizard for selecting action per lead.

### `crm.lead.to.opportunity.mass` — Bulk Lead Convert

Handles multi-record batch conversion.

### `crm.lead.lost` — Mark Lost Wizard

Sets `lost_reason_id` on the lead.

### `crm.merge.opportunities` — Merge Wizard

Pre-selects leads to merge via `_sort_by_confidence_level`.

### `crm.lead.pls.update` — PLS Rebuild Wizard

Triggers `_rebuild_pls_frequency_table()` and `_update_automated_probabilities()`.

---

## Cron Jobs

| Cron | Model | Action | Interval |
|------|-------|--------|----------|
| `crm.ir_cron_crm_lead_assign` | `crm.team` | `_cron_assign_leads()` | Daily (configurable) |
| (embedded in probability cron) | `crm.lead` | `_cron_update_automated_probabilities()` | Scheduled via PLS cron |

---

## Security

Access groups:
- `crm.group_use_lead` — See leads (as opposed to pure opportunities)
- `crm.group_use_recurring_revenues` — See recurring revenue fields
- `sales_team.group_sale_salesman` — Basic salesman
- `sales_team.group_sale_manager` — Manager (can trigger assignment)

---

## Code Paths

| File | Description |
|------|-------------|
| `addons/crm/models/crm_lead.py` | Main lead/opportunity model |
| `addons/crm/models/crm_team.py` | Sales team + assignment logic |
| `addons/crm/models/crm_team_member.py` | Member assignment quotas |
| `addons/crm/models/crm_stage.py` | Stage model |
| `addons/crm/models/crm_lost_reason.py` | Lost reason + leads_count |
| `addons/crm/models/crm_lead_scoring_frequency.py` | Frequency table + field registry |
| `addons/crm/models/crm_recurring_plan.py` | Billing cycle plans |
| `addons/crm/models/res_config_settings.py` | PLS config fields |
| `addons/crm/report/crm_activity_report.py` | Activity pivot view |
| `addons/crm/wizard/` | All wizard models |
| `addons/crm/data/` | Sequences, actions, demo data |
| `addons/crm/security/ir.model.access.csv` | ACL entries |