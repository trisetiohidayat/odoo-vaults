---
Module: helpdesk
Version: Odoo 18 Enterprise
Type: Business
Tags: [helpdesk, tickets, sla, support, customer-service, rating]
---

# Helpdesk — Ticket Management (Enterprise)

Enterprise-grade helpdesk/ticket management module. Manages customer support tickets with SLA policies, automatic assignment, rating feedback, portal access, and multi-team configurations. Located in the enterprise edition, not the community addons.

**Module path:** `~/odoo/enterprise/18.0-20250812/enterprise/helpdesk/`
**Core models:** `helpdesk.ticket`, `helpdesk.team`, `helpdesk.stage`, `helpdesk.tag`, `helpdesk.sla`, `helpdesk.sla.status`
**Key mixins:** `mail.alias.mixin`, `mail.thread.cc`, `rating.parent.mixin`, `portal.mixin`, `utm.mixin`, `mail.activity.mixin`, `mail.tracking.duration.mixin`
**Important:** Not available in community edition; requires `helpdesk` enterprise module installed.

---

## Models

### `helpdesk.ticket` — Support Ticket

Central model for customer support requests. Single model handles full ticket lifecycle from creation through resolution.

**Inheritance:** `portal.mixin` + `mail.thread.cc` + `utm.mixin` + `rating.mixin` + `mail.activity.mixin` + `mail.tracking.duration.mixin`
**_primary_email:** `partner_email`
**_track_duration_field:** `stage_id`
**_order:** `priority desc, id desc`

#### Field Inventory

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Subject (required, indexed, tracking) |
| `team_id` | Many2one(helpdesk.team) | Helpdesk team; default via `_default_team_id()`; indexed |
| `use_sla` | Boolean | Related from `team_id.use_sla` (read-only) |
| `description` | Html | Ticket body; `sanitize_attributes=False` |
| `active` | Boolean | Soft delete; default True |
| `tag_ids` | Many2many(helpdesk.tag) | Classification tags |
| `company_id` | Many2one(res.company) | Related from `team_id.company_id`, stored |
| `color` | Integer | Color index |
| `kanban_state` | Selection | `normal` (in progress), `done` (ready), `blocked`; default `normal` |
| `kanban_state_label` | Char | Compute from stage legend; tracking |
| `legend_blocked` | Char | Related from `stage_id.legend_blocked` (readonly) |
| `legend_done` | Char | Related from `stage_id.legend_done` (readonly) |
| `legend_normal` | Char | Related from `stage_id.legend_normal` (readonly) |
| `domain_user_ids` | Many2many(res.users) | Compute: users who can access ticket based on privacy |
| `user_id` | Many2one(res.users) | Assigned agent; computed from team (`_compute_user_and_stage_ids`); stored; tracking |
| `properties` | Properties | Custom ticket properties via `team_id.ticket_properties` |
| `partner_id` | Many2one(res.partner) | Customer; indexed; tracking |
| `partner_ticket_ids` | Many2many(helpdesk.ticket) | All tickets from same commercial partner |
| `partner_ticket_count` | Integer | Number of other tickets from same partner |
| `partner_open_ticket_count` | Integer | Number of other open tickets from same partner |
| `partner_name` | Char | Customer name; computed from partner; stored |
| `partner_email` | Char | Customer email; computed from partner; inverse writes back |
| `partner_phone` | Char | Customer phone; computed from partner; inverse writes back |
| `commercial_partner_id` | Many2one(res.partner) | Related to `partner_id.commercial_partner_id` |
| `closed_by_partner` | Boolean | True if partner closed the ticket via portal |
| `priority` | Selection | `0`=Low, `1`=Medium, `2`=High, `3`=Urgent; tracking |
| `stage_id` | Many2one(helpdesk.stage) | Stage; computed from team + stored; tracking; domain `[('team_ids', '=', team_id)]` |
| `fold` | Boolean | Related from `stage_id.fold` |
| `date_last_stage_update` | Datetime | Last stage change timestamp; copy=False, readonly |
| `ticket_ref` | Char | Sequential reference (e.g. `#00042`); copy=False, readonly, indexed |
| `assign_date` | Datetime | First assignment time; used to compute `assign_hours` |
| `assign_hours` | Float | Working hours from creation to first assignment; compute+store |
| `close_date` | Datetime | Close timestamp; set when entering folded stage |
| `close_hours` | Float | Working hours from creation to close; compute+store |
| `open_hours` | Integer | Current open time in hours (wall-clock, not working); compute+store |
| **SLA** | | |
| `sla_ids` | Many2many(helpdesk.sla) | SLA policies linked via `helpdesk_sla_status`; copy=False |
| `sla_status_ids` | One2many(helpdesk.sla.status) | SLA status lines (reached/failed/ongoing) |
| `sla_reached_late` | Boolean | Any SLA reached late; SQL-computed; store |
| `sla_reached` | Boolean | No SLA exceeded; SQL-computed; store |
| `sla_deadline` | Datetime | Earliest SLA deadline; compute+store |
| `sla_deadline_hours` | Float | Working hours until SLA deadline; compute+store |
| `sla_fail` | Boolean | SLA failed (deadline passed or reached late); compute+search |
| `sla_success` | Boolean | SLA on track (deadline future); compute+search |
| **Portal** | | |
| `website_message_ids` | One2many | Customer emails/comments (email, comment, email_outgoing, auto_comment) |
| **Response metrics** | | |
| `first_response_hours` | Float | Avg aggregator; time to first response |
| `avg_response_hours` | Float | Avg aggregator; average response time |
| `oldest_unanswered_customer_message_date` | Datetime | For SLA computing |
| `answered_customer_message_count` | Integer | `# Exchanges`; avg aggregator |
| `total_response_hours` | Float | Total exchange time in hours; avg aggregator |
| `display_extra_info` | Boolean | True if multi-company user |
| **Team-related** | | |
| `team_privacy_visibility` | Selection | Related from `team_id.privacy_visibility` |
| `use_credit_notes` | Boolean | Related from team (read-only) |
| `use_coupons` | Boolean | Related from team (read-only) |
| `use_product_returns` | Boolean | Related from team (read-only) |
| `use_product_repairs` | Boolean | Related from team (read-only) |
| `use_rating` | Boolean | Related from team (read-only) |
| `is_partner_email_update` | Boolean | Compute: will ticket email update partner? |
| `is_partner_phone_update` | Boolean | Compute: will ticket phone update partner? |

#### Key Computed Fields

**`_compute_user_and_stage_ids`** — On team change:
- If no `user_id`: calls `team_id._determine_user_to_assign()[team.id]`
- If no `stage_id` or stage not in team's stages: calls `team_id._determine_stage()[team.id]`
- Triggered on `team_id` change

**`_compute_partner_ticket_count`** — Search all partner's commercial partner's tickets:
- Counts all tickets in hierarchy minus self
- Splits into total and open counts
- `partner_ticket_ids` = all partner tickets (for "open other tickets" action)

**`_compute_assign_hours`** — Working hours from create to first assignment:
- Uses `team_id.resource_calendar_id.get_work_duration_data()` (honors working hours)
- Only computed if both `assign_date` and `team_id.resource_calendar_id` exist

**`_compute_close_hours`** — Working hours from create to close:
- Same calendar-based computation as `assign_hours`

**`_compute_open_hours`** — Current open duration in hours:
- If closed: `close_date - create_date` (wall clock)
- If open: `now - create_date` (wall clock)
- Not calendar-based (working hours)

**`_compute_sla_reached_late`** — SQL-based computation (requires sudo):
```sql
SELECT ticket_id, COUNT(id) AS reached_late_count
FROM helpdesk_sla_status
WHERE ticket_id IN %s AND (deadline < reached_datetime OR (deadline < %s AND reached_datetime IS NULL))
GROUP BY ticket_id
```
A ticket is marked `reached_late=True` if any SLA status row meets the condition.

**`_compute_sla_reached`** — SQL-based:
- Count of `sla_status_ids` with `exceeded_hours < 0` (on time or early)

**`_compute_sla_deadline`** — Minimum of all SLA status deadlines:
- Iterates `sla_status_ids` where `reached_datetime` is null and `deadline` exists
- Takes earliest deadline
- `sla_deadline_hours` computed from now to deadline via calendar

**`_compute_sla_fail`** — `sla_deadline < now` OR `sla_reached_late`

**`_compute_sla_success`** — `sla_deadline > now` (on track)

#### Key Methods

**SLA Lifecycle:**

- **`_sla_reset_trigger()`** — Returns `['team_id', 'priority', 'tag_ids', 'partner_id']`
  - Any of these changes triggers SLA re-evaluation

- **`_sla_apply(keep_reached=False)`** — Apply SLA policies:
  - Calls `_sla_find()` to get SLAs per ticket
  - Generates status values via `_sla_generate_status_values()`
  - Unlinks old SLA statuses (keeps reached ones if `keep_reached=True`)
  - Creates new `helpdesk.sla.status` records
  - Called in `create()` (sudo) and in `write()` when SLA triggers change

- **`_sla_find()`** — Match SLA policies to tickets:
  - Groups tickets by key: `(team_id.id, priority, tag_ids, partner_id.id)`
  - For each group: searches SLAs with `team_id=team`, `priority=priority`, `stage_id.sequence >= ticket.stage_id.sequence`
  - Extra domain: partner match via `partner_ids.parent_of/child_of` or empty
  - Filters by tag overlap: `not s.tag_ids or (tickets.tag_ids & s.tag_ids)`
  - Only for teams with `use_sla=True`

- **`_sla_reach(stage_id)`** — Called on stage change:
  - Finds all stages with `sequence <= target_sequence` for ticket's teams
  - Writes `reached_datetime=now` for all unreached SLA statuses in those stages
  - Clears `reached_datetime` for statuses whose stage is no longer relevant

- **`action_open_ratings()`** — Open rating if single, else list view

**Stage & Assignment on Create:**

- **`create()`** — Batch-optimized creation:
  1. Batch-computes team defaults: `_determine_stage()` + `_determine_user_to_assign()` per team
  2. Creates partner if `partner_name` + `partner_email` provided without `partner_id`
  3. Generates `ticket_ref` via `helpdesk.ticket` sequence per company
  4. If stage is folded (closed): sets `close_date=now`
  5. If user assigned: sets `assign_date=now`, `assign_hours=0`
  6. Sets `date_last_stage_update` and `oldest_unanswered_customer_message_date`
  7. Subscribes partners from `email_cc` field (internal users only)
  8. Calls `_portal_ensure_token()` for customer access
  9. Calls `sudo()._sla_apply()`

**Stage Change Logic in `write()`:**
- If new stage is folded: `close_date=now`, `oldest_unanswered_customer_message_date=False`
- If stage not folded: `closed_by_partner=False`, `close_date=False`
- On `stage_id` change: `date_last_stage_update=now`, `kanban_state='normal'` (unless specified)
- SLA triggers: if any trigger field changed → `sudo()._sla_apply(keep_reached=True)`
- If stage reached: `sudo()._sla_reach(stage_id)`
- Post-close: posts SLA timing note via OdooBot (reached/failed)

**Mail Gateway:**

- **`message_new(msg, custom_values)`** — Email-to-ticket:
  - Sets `partner_email`, `partner_name`, `author_id` from email
  - Removes partner if partner.company_id differs from team.company_id
  - Finds/creates partners from `email_cc` addresses (internal users only)
  - Subscribes found partners as followers
  - Calls `_portal_ensure_token()`

- **`message_update(msg)`** — Email reply updates:
  - Splits addresses via `_ticket_email_split()` (filters out team alias)
  - Finds/creates partners, subscribes them

- **`_track_template(changes)`** — Auto-email on stage change:
  - If `stage_id` changed AND `stage_id.template_id` exists AND ticket has `partner_email` AND (no user, or user != partner, or portal user, or `mail_notify_author` context):
  - Sends `stage_id.template_id` email to customer

- **`_track_subtype(init_values)`** — `stage_id` change → `helpdesk.mt_ticket_stage`

**Customer Partner Sync:**
- `_inverse_partner_email`: writes back to `partner_id.email` if email differs
- `_inverse_partner_phone`: writes back to `partner_id.phone` if phone differs (sudo)

**Portal:**

- `_compute_access_url()` → `/my/ticket/{id}`

**Constraints:**

- **`_check_partner_id_has_the_same_company()`** — Raises `UserError` if partner.company_id differs from ticket.company_id

---

### `helpdesk.team` — Helpdesk Team

Inherits `mail.alias.mixin` + `mail.thread` + `rating.parent.mixin`. Represents a support team with member management, assignment rules, SLA policies, and auto-close configuration.

**_rating_satisfaction_days:** 7 (last 7 days for satisfaction computation)

#### Field Inventory

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Team name (required, translateable) |
| `description` | Html | About team |
| `active` | Boolean | Soft delete |
| `company_id` | Many2one(res.company) | Company; required; default `env.company` |
| `sequence` | Integer | Display order |
| `color` | Integer | Color index |
| `ticket_properties` | PropertiesDefinition | Custom property schema for team tickets |
| `stage_ids` | Many2many(helpdesk.stage) | Stages available to this team; `team_stage_rel` table |
| `auto_assignment` | Boolean | Enable automatic ticket assignment |
| `assign_method` | Selection | `randomly` (equal count) or `balanced` (equal open tickets) |
| `member_ids` | Many2many(res.users) | Team members; domain: `helpdesk.group_helpdesk_user`; default: env.user |
| `privacy_visibility` | Selection | `invited_internal` (private), `internal` (company), `portal` (public); default `portal` |
| `privacy_visibility_warning` | Char | Warning when changing visibility |
| `access_instruction_message` | Char | Help text for access |
| `ticket_ids` | One2many(helpdesk.ticket) | All team tickets |
| `use_alias` | Boolean | Enable email alias; default True |
| `has_external_mail_server` | Boolean | Config param check |
| `allow_portal_ticket_closing` | Boolean | Customers can close their tickets |
| **Website integration** | | |
| `use_website_helpdesk_form` | Boolean | Website form enabled |
| `use_website_helpdesk_livechat` | Boolean | Live chat integration |
| `use_website_helpdesk_forum` | Boolean | Community forum |
| `use_website_helpdesk_slides` | Boolean | eLearning |
| `use_website_helpdesk_knowledge` | Boolean | Knowledge base |
| **Module features** | | |
| `use_helpdesk_timesheet` | Boolean | Time tracking |
| `use_helpdesk_sale_timesheet` | Boolean | Billable time |
| `use_credit_notes` | Boolean | Refunds |
| `use_coupons` | Boolean | Loyalty |
| `use_fsm` | Boolean | Field service |
| `use_product_returns` | Boolean | Returns |
| `use_product_repairs` | Boolean | Repairs |
| `use_twitter` | Boolean | X/Twitter integration |
| `use_rating` | Boolean | Customer ratings |
| `use_sla` | Boolean | SLA policies (default True) |
| `show_knowledge_base` | Boolean | Show knowledge base link |
| **Statistics** | | |
| `unassigned_tickets` | Integer | Tickets with no user, not closed |
| `open_ticket_count` | Integer | Non-folded stage tickets |
| `sla_policy_count` | Integer | SLA policies for this team |
| `ticket_closed` | Integer | Tickets closed in last 7 days |
| `success_rate` | Float | % of SLA met for tickets closed in last 7 days |
| `urgent_ticket` | Integer | Priority=3 (Urgent), non-folded |
| `sla_failed` | Integer | Failed SLA tickets (non-folded) |
| **Auto-close** | | |
| `auto_close_ticket` | Boolean | Auto-close inactive tickets |
| `auto_close_day` | Integer | Inactive days threshold (default 7) |
| `from_stage_ids` | Many2many(helpdesk.stage) | Stages eligible for auto-close |
| `to_stage_id` | Many2one(helpdesk.stage) | Target stage for auto-close |
| `alias_email_from` | Char | Computed alias email for display |
| `resource_calendar_id` | Many2one(resource.calendar) | Working hours (SLA deadline calculation) |

#### Key Methods

**Group/Feature Management:**

- **`_check_sla_group()`** — Called on create/write:
  - If any team has `use_sla=True` and user lacks `helpdesk.group_use_sla`: adds implied group
  - Activates inactive SLAs for SLA teams
  - If team removed SLA and no other SLA team: removes implied group, clears users

- **`_check_rating_group()`** — Similar: activates rating email template when enabled

- **`_check_auto_assignment_group()`** — Adds `group_auto_assignment` when enabled

- **`_check_modules_to_install()`** — On create/write:
  - Detects enabled features via `_get_field_modules()` mapping
  - Calls `button_immediate_install()` on pending modules

- **`_get_field_modules()`** — Maps feature fields to module names:
  ```
  use_website_helpdesk_form → website_helpdesk
  use_website_helpdesk_livechat → website_helpdesk_livechat
  use_website_helpdesk_forum → website_helpdesk_forum
  use_website_helpdesk_slides → website_helpdesk_slides
  use_website_helpdesk_knowledge → website_helpdesk_knowledge
  use_helpdesk_timesheet → helpdesk_timesheet
  use_helpdesk_sale_timesheet → helpdesk_sale_timesheet
  use_credit_notes → helpdesk_account
  use_product_returns → helpdesk_stock
  use_product_repairs → helpdesk_repair
  use_coupons → helpdesk_sale_loyalty
  use_fsm → helpdesk_fsm
  ```

**Dashboard — `retrieve_dashboard()`:**

Returns dict with:
- `helpdesk_target_closed/rating/success`: user targets
- `today` / `7days`: closed ticket counts, SLA counts, ratings, success rates
- `my_all` / `my_high` / `my_urgent`: agent's open ticket stats (count, avg hours, failed SLA count)
- `rating_enable`, `success_rate_enable`: feature flags

Uses `search_read` + `_read_group` for ticket stats. Falls back to demo data if no tickets exist.

**Ticket Assignment — `_determine_user_to_assign()`:**

Called during ticket creation to pick initial assignee:

1. Get working users for next 7 days via `_get_working_users_per_first_working_day()`
2. Find first batch of users whose first working day is nearest to today
3. `assign_method='randomly'`: round-robin based on last assigned user in team
4. `assign_method='balanced'`: pick user with fewest open tickets
5. Falls back to `env['res.users']` (empty record) if no members

**Stage Determination — `_determine_stage()`:**

- For each team: searches stages with `team_ids` containing team, ordered by `sequence`, limit 1

**Privacy Visibility:**

- **`_change_privacy_visibility(new_visibility)`** — On change to `portal`: subscribes ticket partners as followers. On change from `portal`: unsubscribes portal users from team and tickets.

**Auto-Close Cron — `_cron_auto_close_tickets()`:**

1. Reads all teams with `auto_close_ticket=True` and `to_stage_id` set
2. For each: computes `threshold_date = today - auto_close_day`
3. Finds open tickets in those teams
4. Filters: `write_date <= threshold_date` AND (no `from_stage_ids` OR stage in `from_stage_ids`)
5. Writes `stage_id = to_stage_id`

**Alias Handling:**

- `_alias_get_creation_values()`: sets `alias_model_id = helpdesk.ticket`, defaults `team_id`
- `_ensure_unique_email_alias()`: appends `-2`, `-3` suffix if alias exists

---

### `helpdesk.stage` — Pipeline Stage

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Soft delete; deactivating archives all tickets |
| `name` | Char | Stage name (required, translateable) |
| `description` | Text | Internal requirements (translateable) |
| `sequence` | Integer | Ordering (not exported) |
| `fold` | Boolean | Folded in kanban (considered closed) |
| `team_ids` | Many2many(helpdesk.team) | Teams using this stage; `team_stage_rel` |
| `template_id` | Many2one(mail.template) | Email sent to customer on reaching this stage |
| `legend_blocked` | Char | Red kanban label (default: "Blocked") |
| `legend_done` | Char | Green kanban label (default: "Ready") |
| `legend_normal` | Char | Grey kanban label (default: "In Progress") |
| `ticket_count` | Integer | Compute: count of tickets in this stage |

**`write()`**: Deactivating a stage deactivates all its tickets.

**`toggle_active()`**: If stage has tickets when reactivated, opens wizard to unarchive them.

**`action_unlink_wizard()`**: Creates delete wizard if stage has tickets from any team.

**`action_open_helpdesk_ticket()`**: Opens ticket list filtered to this stage.

---

### `helpdesk.tag` — Ticket Tags

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name (required, unique, case-insensitive via `=ilike`) |
| `color` | Integer | Color index (1-11) |

**SQL Constraint:** `name_uniq` — unique name.

**`name_create()`**: Case-insensitive duplicate check; returns existing tag if name matches.

---

### `helpdesk.sla` — SLA Policy Definition

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Policy name (required, indexed, translateable) |
| `description` | Html | Policy description |
| `active` | Boolean | Soft delete |
| `team_id` | Many2one(helpdesk.team) | Team (required) |
| `tag_ids` | Many2many(helpdesk.tag) | Optional tag filter |
| `stage_id` | Many2one(helpdesk.stage) | Target stage (minimum stage to reach) |
| `exclude_stage_ids` | Many2many(helpdesk.stage) | Stages not counted toward SLA time |
| `priority` | Selection | Minimum priority to match (`TICKET_PRIORITY`) |
| `partner_ids` | Many2many(res.partner) | Customer filter |
| `company_id` | Many2one(res.company) | Related from team; stored |
| `time` | Float | Maximum working hours to reach target (required) |
| `ticket_count` | Integer | Compute: count of non-folded tickets with this SLA |

**`default_get()`**: Pre-fills `team_id` and `stage_id` (defaults to first folded/closing stage of team).

**`_compute_display_name()`**: If context `with_team_name`: appends `f"- {team.name}"`.

**`action_open_helpdesk_ticket()`**: Opens tickets with this SLA.

---

### `helpdesk.sla.status` — SLA Status Per Ticket

Technical model linking tickets to SLA policies. Not meant to be edited directly; managed by `_sla_apply()` and `_sla_reach()`.

**`_table:** `helpdesk_sla_status`
**_order:** `deadline ASC, sla_stage_id`

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `ticket_id` | Many2one(helpdesk.ticket) | Ticket; required, cascade delete |
| `sla_id` | Many2one(helpdesk.sla) | SLA policy; required, cascade delete |
| `sla_stage_id` | Many2one(helpdesk.stage) | Related from `sla_id.stage_id`; stored (for search in `_sla_reach`) |
| `deadline` | Datetime | Computed deadline; `compute_sudo=True` |
| `reached_datetime` | Datetime | When ticket reached target stage |
| `status` | Selection | `failed`/`reached`/`ongoing`; compute+sudo; search-enabled |
| `color` | Integer | 1=failed, 10=reached, 0=ongoing |
| `exceeded_hours` | Float | Working hours exceeded (negative = early); compute+sudo; stored |

**`_compute_deadline()`** — Calendar-based deadline computation:
1. Start from ticket `create_date`
2. If `sla_id.exclude_stage_ids` set and ticket in excluded stage: `deadline=False`
3. Compute working days: `floor(time / hours_per_day)` using team calendar
4. `plan_days()` to get deadline date
5. Preserve creation time-of-day on deadline
6. Add remaining hours via `plan_hours()`
7. Handle freezed hours in excluded stages via `_get_freezed_hours()`
8. If creation time is after working hours end: set deadline to midnight
9. If in excluded stage at creation: deadline=False

**`_get_freezed_hours()`** — Tracks time spent in excluded stages:
- Searches `mail.tracking.value` for stage_id changes
- Sums working hours between each tracking line
- Adds current time if still in excluded stage

**`_compute_status()`**:
- `reached_datetime` set: `status = 'reached'` if `reached_datetime < deadline` else `'failed'`
- No `reached_datetime`: `status = 'ongoing'` if `deadline > now` else `'failed'`

**`_search_status()`** — Domain operator support:
- `failed`: `['|', '&', ('reached_datetime', '=', True), ('deadline', '<=', 'reached_datetime'), '&', ('reached_datetime', '=', False), ('deadline', '<=', now)]`
- `reached`: `['&', ('reached_datetime', '=', True), ('reached_datetime', '<', 'deadline')]`
- `ongoing`: `['|', ('deadline', '=', False), '&', ('reached_datetime', '=', False), ('deadline', '>', now)]`
- Negative operators transform to union of other states

**`_compute_exceeded_hours()`** — Working hours between deadline and reach time:
- Positive = late, Negative = early
- Uses `get_work_duration_data()` from team calendar

---

## Digest Extension

**`digest.digest`** extended with:
- `kpi_helpdesk_tickets_closed` (Boolean toggle)
- `kpi_helpdesk_tickets_closed_value` (Integer compute via `_calculate_company_based_kpi`)
- `_compute_kpi_helpdesk_tickets_closed_value()` — requires `helpdesk.group_helpdesk_user` access check
- KPI action links to `helpdesk_team_dashboard_action_main`

---

## Wizard Models

### `helpdesk.stage.delete.wizard`

Handles stage deletion. Two contexts:
1. **Unarchive tickets** (from `toggle_active`): reassigns tickets when reactivating
2. **Delete stage** (from `action_unlink_wizard`): reassigns tickets to alternative stage, then deletes

### Other wizards

Located in `wizard/` directory. Handles bulk operations, ticket merging, etc.

---

## Cron Jobs

| Cron | Model | Action |
|------|-------|--------|
| `helpdesk.ir_cron_auto_close_ticket` | `helpdesk.team` | `_cron_auto_close_tickets()` — toggled active based on `auto_close_ticket` field |

---

## Security

Access groups:
- `helpdesk.group_helpdesk_user` — Basic agent/technician
- `helpdesk.group_use_sla` — SLA policy management (implied from `group_helpdesk_user` when `use_sla=True`)
- `helpdesk.group_use_rating` — Rating feature (implied when `use_rating=True`)
- `helpdesk.group_auto_assignment` — Auto-assignment (implied when `auto_assignment=True`)
- Portal access: `portal.portal` + privacy visibility settings

---

## Code Paths

| File | Description |
|------|-------------|
| `enterprise/helpdesk/models/helpdesk_ticket.py` | Core ticket model (931 lines) |
| `enterprise/helpdesk/models/helpdesk_team.py` | Team + dashboard + assignment (1020 lines) |
| `enterprise/helpdesk/models/helpdesk_stage.py` | Stage model + delete wizard triggers |
| `enterprise/helpdesk/models/helpdesk_tag.py` | Tag model |
| `enterprise/helpdesk/models/helpdesk_sla.py` | SLA policy definition |
| `enterprise/helpdesk/models/helpdesk_sla_status.py` | SLA status per ticket |
| `enterprise/helpdesk/models/digest.py` | Digest KPI extension |
| `enterprise/helpdesk/models/res_partner.py` | Partner extensions |
| `enterprise/helpdesk/models/res_users.py` | User extensions |
| `enterprise/helpdesk/wizard/` | Wizard models |
| `enterprise/helpdesk/report/` | Reporting models (if any) |