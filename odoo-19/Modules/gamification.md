---
type: module
module: gamification
tags: [odoo, odoo19, gamification, badge, challenge, goal, karma]
created: 2026-04-06
updated: 2026-04-11
l4: true
source: ~/odoo/odoo19/odoo/addons/gamification/
---

# Gamification Module (`gamification`)

## Overview

**Module:** `gamification`
**Depends:** `mail`
**Category:** Human Resources
**License:** LGPL-3
**Sequence:** 160
**Cron Jobs:** 2

| Cron | Model | Schedule | Method |
|---|---|---|---|
| `Gamification: Goal Challenge Check` | `gamification.challenge` | Daily | `_cron_update()` |
| `Gamification: Karma tracking consolidation` | `gamification.karma.tracking` | Monthly (1st, 4AM) | `_consolidate_cron()` |

The Gamification module provides a framework for evaluating and motivating Odoo users through **goals**, **challenges**, **badges**, and **karma**. It enables organizations to gamify employee engagement by tracking measurable objectives, awarding badges (peer-to-peer or auto-granted), computing karma scores, and managing rank hierarchies based on accumulated karma.

### Module Files

```
gamification/
  models/
    gamification_badge.py            # Badge definitions with grant rules
    gamification_badge_user.py      # Badge award instances
    gamification_challenge.py        # Challenge management + cron logic
    gamification_challenge_line.py   # Goal lines in challenges
    gamification_goal.py             # Individual goal tracking
    gamification_goal_definition.py  # Goal computation templates
    gamification_karma_rank.py       # Karma-based rank tiers
    gamification_karma_tracking.py   # Karma change audit log
    res_users.py                   # Karma/badges on res.users
  wizard/
    grant_badge.py                 # Badge granting wizard
    update_goal.py                 # Manual goal update wizard
  data/
    ir_cron_data.xml               # Scheduled actions
    mail_template_data.xml         # Email templates
    gamification_badge_data.xml    # Default badges
    gamification_challenge_data.xml # Default challenges
    gamification_karma_rank_data.xml
    gamification_karma_rank_demo.xml
    gamification_karma_tracking_demo.xml
  security/
    gamification_security.xml       # Manager group definition
    ir.model.access.csv             # ACL entries
```

---

## Model Architecture

```
gamification.challenge (1)
    ├──< gamification.challenge.line (N)
    │         │
    │         └───> gamification.goal.definition (N)
    │
    ├──< res.users (N)    # participants
    │
    └──< gamification.badge (N)  # reward_id, reward_first_id, etc.

gamification.goal.definition (1)
    └──< gamification.goal (N)
              │
              ├──> res.users (user_id)
              │
              └──> gamification.challenge.line (line_id)

gamification.badge (1)
    └──< gamification.badge.user (N)
              │
              ├──> res.users (user_id = recipient)
              └──> res.users (sender_id = granter)

res.users (1)
    ├──< gamification.karma.tracking (N)
    ├──< gamification.badge.user (N)
    ├──< gamification.karma.rank (1)   # rank_id
    └──< gamification.karma.rank (1)   # next_rank_id
```

---

## `gamification.badge`

**File:** `gamification_badge.py`
**Table:** `gamification_badge`
**Inherits:** `mail.thread`, `image.mixin`

Badge definitions represent achievement tokens. Badges have grant rules that control who can award them, optional monthly sending limits, and optional automatic unlock through goal completion.

### Grant Authorization Constants

```python
CAN_GRANT = 1           # User is allowed to grant
NOBODY_CAN_GRANT = 2    # Badge is challenge-only; no manual granting
USER_NOT_VIP = 3        # User not in authorized list
BADGE_REQUIRED = 4      # User missing required prerequisite badges
TOO_MANY = 5            # Monthly limit exceeded
```

### Fields

#### Identity & Description

| Field | Type | Default | Purpose |
|---|---|---|---|
| `name` | `Char` | required, translate | Badge display name |
| `active` | `Boolean` | `True` | Soft-delete control |
| `description` | `Html` | — | Full badge description (translated, `sanitize_attributes=False`) |
| `level` | `Selection` | `bronze` | Rarity tier: `bronze`, `silver`, `gold` |

#### Grant Authorization Rules

| Field | Type | Default | Purpose |
|---|---|---|---|
| `rule_auth` | `Selection` | `everyone` | Who can grant this badge |
| `rule_auth_user_ids` | `Many2many` | — | Users permitted (when `rule_auth=users`) |
| `rule_auth_badge_ids` | `Many2many` | — | Required badges to grant (when `rule_auth=having`) |

**`rule_auth` options:**

| Value | Meaning |
|---|---|
| `everyone` | Any user can grant |
| `users` | Only users listed in `rule_auth_user_ids` |
| `having` | Only users who own all badges in `rule_auth_badge_ids` |
| `nobody` | No manual granting; only challenges may award this badge |

#### Monthly Sending Limit

| Field | Type | Purpose |
|---|---|---|
| `rule_max` | `Boolean` | Whether monthly sending limit is active |
| `rule_max_number` | `Integer` | Max times one user can send this badge per month |
| `stat_my_monthly_sending` | `Integer` (computed) | How many the current user has sent this month |

#### Relations

| Field | Type | Purpose |
|---|---|---|
| `challenge_ids` | `One2many` | Challenges that use this as `reward_id` |
| `goal_definition_ids` | `Many2many` | Goal definitions that auto-unlock this badge |
| `owner_ids` | `One2many` | All badge-user grant instances |

#### Statistics (Computed)

| Field | Computation Trigger | Purpose |
|---|---|---|
| `granted_count` | `owner_ids` | Total times awarded |
| `granted_users_count` | `owner_ids` | Number of unique users who received it |
| `unique_owner_ids` | `owner_ids` | Recordset of unique owner users |
| `stat_this_month` | `owner_ids.create_date` | Awards this calendar month |
| `stat_my` | `owner_ids.user_id` | Awards to current user, all time |
| `stat_my_this_month` | `owner_ids.user_id + create_date` | Awards to current user this month |
| `stat_my_monthly_sending` | `owner_ids.create_uid + create_date` | Awards sent by current user this month |
| `remaining_sending` | `rule_auth` + `stat_my_monthly_sending` | Remaining sends (0=none, -1=infinite) |

### Methods

#### `_get_owners_info()`

**Decorators:** `@api.depends('owner_ids')`

Executes a raw SQL query joining `res_users` and `gamification_badge_user` via the `mail Followers`-style relation alias `badges` to compute three statistics in one pass. Uses `execute_query` with `SQL.identifier` to safely construct the join alias.

```python
query = Users._search([])  # creates base query with access rules
badge_alias = query.join("res_users", "id", "gamification_badge_user", "user_id", "badges")
```

The `badge_alias` is dynamically computed as a JOIN alias on the `gamification_badge_user` table, which allows the query to respect Odoo's record rules if the calling context has them set. The query returns `badge_id`, `count(*)`, `count(distinct user_id)`, and `array_agg(distinct user_id)` per badge.

**Fallback behavior:** When a badge has never been awarded, the SQL returns no rows for it. The method handles this by tracking a `defaults` dict (`granted_count=0`, `granted_users_count=0`, `unique_owner_ids=[]`) and applying it to any badge not present in the query results. This is critical for newly created badges or badges with no awards.

**L4 Edge Case:** The `unique_owner_ids` aggregation uses `array_agg(distinct res_users.id)` in raw SQL. This is an array type in PostgreSQL and gets deserialized into a Python list when read from the cursor. The result is assigned directly as a Many2many value via `badge.unique_owner_ids = owner_ids`.

#### `_get_badge_user_stats()`

**Decorators:** `@api.depends('owner_ids.badge_id', 'owner_ids.create_date', 'owner_ids.user_id')`

Iterates over all `owner_ids` using Python `sum()` with boolean expressions. First day of month is `date.today().replace(day=1)`. This is entirely in-memory -- no SQL.

**L4 Edge Case -- Granter vs Recipient:** Two distinct counters are computed:
- `stat_my_this_month` counts records where `o.user_id == self.env.user` (the **recipient**)
- `stat_my_monthly_sending` counts records where `o.create_uid == self.env.user` (the **granter/sender**)

These serve different authorization checks in `_can_grant_badge()`. The recipient's count is for display; the granter's count is what enforces monthly sending limits.

#### `_remaining_sending_calc()`

**Decorators:** `@api.depends('rule_auth', 'rule_auth_user_ids', 'rule_auth_badge_ids', 'rule_max', 'rule_max_number', 'stat_my_monthly_sending')`

Calls `_can_grant_badge()` first. Returns:
- `0` if user cannot grant at all
- `-1` if no monthly limit is set (meaning infinite; UI hides the counter)
- `rule_max_number - stat_my_monthly_sending` otherwise

#### `check_granting()`

Calls `_can_grant_badge()` and raises `UserError` for each non-zero status code. Returns `True` on `CAN_GRANT`. Logs unknown status codes at `ERROR` level (safety valve for future codes).

#### `_can_grant_badge()`

Returns an integer status code. Check order:

1. **Admin bypass:** `self.env.is_admin()` always returns `CAN_GRANT`
2. **`rule_auth='nobody'`:** returns `NOBODY_CAN_GRANT`
3. **`rule_auth='users'`:** returns `USER_NOT_VIP` if current user not in `rule_auth_user_ids`
4. **`rule_auth='having'`:** computes set subtraction `self.rule_auth_badge_ids - all_user_badges` -- if non-empty, user is missing at least one required badge -> `BADGE_REQUIRED`
5. **Monthly limit check:** if `rule_max` and `stat_my_monthly_sending >= rule_max_number` -> `TOO_MANY`
6. **`rule_auth='everyone'`** with no violations -> `CAN_GRANT`

**L4 Edge Case -- Badge superset logic:** The set subtraction `self.rule_auth_badge_ids - all_user_badges` means a user with **more** badges than required still passes. This is intentional: possessing additional badges does not disqualify a granter.

---

## `gamification.badge.user`

**File:** `gamification_badge_user.py`
**Table:** `gamification_badge_user`
**Inherits:** `mail.thread`
**Order:** `create_date desc`
**Rec Name:** `badge_name`

Records the granting of a badge to a specific user. The record links recipient, sender, badge definition, and optionally a challenge that triggered the award.

### Fields

| Field | Type | Required | Ondelete | Purpose |
|---|---|---|---|---|
| `user_id` | `Many2one(res.users)` | Yes | cascade | Badge recipient |
| `user_partner_id` | `Many2one(res.partner)` | — | — | Cached partner (for mail notification) |
| `sender_id` | `Many2one(res.users)` | — | — | User who granted the badge |
| `badge_id` | `Many2one(gamification.badge)` | Yes | cascade | Badge definition |
| `challenge_id` | `Many2one(gamification.challenge)` | — | — | Challenge that triggered the award |
| `comment` | `Text` | — | — | Optional message from sender |
| `badge_name` | `Char` (related) | — | — | Synced from `badge_id.name`, `readonly=False` |
| `level` | `Selection` (related, stored) | — | — | Badge level synced and stored |

### Methods

#### `_send_badge()`

Renders the `gamification.email_template_badge_received` template using `_render_field()` for the badge user's `body_html` field. Sends via `message_notify` to the recipient's partner with subject `"🎉 You've earned the %(badge)s badge!"`. Uses `mail.mail_notification_layout` email layout.

The method iterates `for badge_user in self` -- even though this is called from `_reward_user()` on a single record, the batch design allows bulk badge sending efficiently.

#### `_notify_get_recipients_groups()`

Overridden to disable the access button (`has_button_access=False`) for the `user` group in email notifications. This prevents recipients from clicking through to the badge record from the email.

#### `create()`

**Decorators:** `@api.model_create_multi`

Before creating, calls `badge.check_granting()` on the badge. This is the primary authorization gate. The badge's `check_granting()` reads `stat_my_monthly_sending` (granter's sends) and `rule_auth` rules. If the granter lacks permission, `UserError` is raised before any database write occurs.

#### `_mail_get_partner_fields()`

Returns `['user_partner_id']` to direct Odoo's mail system to route notifications to the user's partner record rather than the user record itself.

---

## `gamification.challenge`

**File:** `gamification_challenge.py`
**Table:** `gamification_challenge`
**Inherits:** `mail.thread`
**Order:** `end_date, start_date, name, id`

A challenge is a timed contest that assigns goals to participants and optionally rewards winners with badges. Challenges can be one-shot (`period=once`) or recurring (`daily`, `weekly`, `monthly`, `yearly`).

### Challenge State Machine

```
draft ──(action_start or start_date reached)──> inprogress ──(end_date passed)──> done
  ^                                                            │
  └──────────(action_check while inprogress)───────────────────┘
```

| State | Description |
|---|---|
| `draft` | Challenge created but not started |
| `inprogress` | Active; goals tracked; cron updates run |
| `done` | Completed; all rewards distributed |

### Fields

#### Identity & Description

| Field | Type | Default | Purpose |
|---|---|---|---|
| `name` | `Char` | required, translate | Challenge title |
| `description` | `Text` | — | Challenge description |
| `state` | `Selection` | `draft` | `draft`, `inprogress`, `done` |
| `manager_id` | `Many2one(res.users)` | `env.uid` | Challenge owner/responsible |
| `challenge_category` | `Selection` | `hr` | Menu visibility: `hr`, `other` |

#### Participants

| Field | Type | Purpose |
|---|---|---|
| `user_ids` | `Many2many(res.users)` | Explicit participant list |
| `user_domain` | `Char` | Domain expression to auto-select participants |
| `user_count` | `Integer` (computed) | Count of active participants |
| `invited_user_ids` | `Many2many(res.users)` | Invited but not yet accepted |

**L4 Edge Case -- `user_domain`:** The default domain (set in `default_get`) is:
```python
f'["&", ("all_group_ids", "in", [{user_group_id.id}]), ("active", "=", True)]'
```
This uses the `all_group_ids` computed field on `res.users` (introduced in Odoo 16) which expands group membership hierarchically -- a user in any child group is also matched. The domain is stored as a Char and evaluated with `ast.literal_eval` in `_get_challenger_users()`.

#### Periodicity

| Field | Type | Default | Purpose |
|---|---|---|---|
| `period` | `Selection` | `once` | `once`, `daily`, `weekly`, `monthly`, `yearly` |
| `start_date` | `Date` | — | When challenge auto-starts |
| `end_date` | `Date` | — | When challenge auto-closes |

#### Goals & Rewards

| Field | Type | Index | Purpose |
|---|---|---|---|
| `line_ids` | `One2many` | — | Goal definitions (challenge lines) |
| `reward_id` | `Many2one` | `btree_not_null` | Badge for every user completing all goals |
| `reward_first_id` | `Many2one` | — | Badge for 1st place |
| `reward_second_id` | `Many2one` | — | Badge for 2nd place |
| `reward_third_id` | `Many2one` | — | Badge for 3rd place |
| `reward_failure` | `Boolean` | — | Reward top performers even if no one completed all goals |
| `reward_realtime` | `Boolean` | `True` | Grant `reward_id` immediately on completion; top-3 only at end |

#### Display & Reporting

| Field | Type | Default | Purpose |
|---|---|---|---|
| `visibility_mode` | `Selection` | `personal` | `personal` or `ranking` |
| `report_message_frequency` | `Selection` | `never` | `never`, `onchange`, `daily`, `weekly`, `monthly`, `yearly` |
| `report_message_group_id` | `Many2one(discuss.channel)` | — | Channel to copy reports |
| `report_template_id` | `Many2one(mail.template)` | `_get_report_template()` | Report template |
| `remind_update_delay` | `Integer` | — | Days before reminding stale manual goals |
| `last_report_date` | `Date` | `today` | Last report sent |
| `next_report_date` | `Date` (computed, stored) | — | Next scheduled report |

### Helper Function: `start_end_date_for_period()`

```python
def start_end_date_for_period(period, default_start_date=False, default_end_date=False):
    today = date.today()
    if period == 'daily':
        return (today, today)
    elif period == 'weekly':
        start = today + relativedelta(weekday=MO(-1))  # Last Monday
        return (start, start + timedelta(days=7))
    elif period == 'monthly':
        start = today.replace(day=1)
        end = today + relativedelta(months=1, day=1, days=-1)
        return (start, end)
    elif period == 'yearly':
        return (today.replace(month=1, day=1), today.replace(month=12, day=31))
    else:  # once
        return (default_start_date, default_end_date)
```

For `weekly`, the end date is exactly 7 days after start, not the upcoming Sunday. This means the period spans Monday to next Monday (exclusive), which can overlap with the next week's period by one day. This is a known artifact of the period calculation.

### Methods

#### `create()`

Evaluates `user_domain` via `_get_challenger_users()` (using `ast.literal_eval`) and adds matching users to `user_ids` via `(4, user.id)` commands before the super call. If `user_ids` is explicitly set in `vals`, both explicit and domain-matched users are included.

#### `write()`

State transition handling:

| Transition | Actions |
|---|---|
| `-> draft` | Raises `UserError` if any goal is `inprogress` |
| `-> inprogress` | Calls `_recompute_challenge_users()` + `_generate_goals_from_challenge()` |
| `-> done` | Calls `_check_challenge_reward(force=True)` |

**L4 Edge Case -- `draft` reset protection:** A challenge cannot be reset to draft if it has any in-progress goals. This prevents accidentally discarding active progress. The check uses `search_count` with `limit=1` (not a full search), optimized for early exit.

#### `_cron_update()`

Class method (can be called directly or by cron). Sets context `commit_gamification=commit` before processing, enabling intermediate DB commits to avoid holding long transactions during batch processing. Steps:

1. Start planned challenges: `state=draft` with `start_date <= today`
2. Close overdue challenges: `state=inprogress` with `end_date < today`
3. Call `_update_all()` on remaining `inprogress` challenges

#### `_update_all()`

Core update engine. Uses raw SQL to find goals needing update based on presence and session validity:

```sql
SELECT gg.id FROM gamification_goal gg
JOIN mail_presence mp ON mp.user_id = gg.user_id
WHERE gg.write_date <= mp.last_presence
  AND mp.last_presence >= now() AT TIME ZONE 'UTC' - interval '%(session_lifetime)s seconds'
  AND gg.closed IS NOT TRUE
  AND gg.challenge_id IN %(challenge_ids)s
  AND (gg.state = 'inprogress'
       OR (gg.state = 'reached' AND gg.end_date >= %(yesterday)s))
```

**L4 Edge Case -- Presence-based filtering:** Goals are only updated for users with a recent `mail_presence` record (within `SESSION_LIFETIME` seconds, default ~60 minutes from `odoo/http.py`). This prevents unnecessary computation for inactive users. Goals in `reached` state are included if their end date is still in the future or yesterday, allowing late closes.

After goal updates:
1. Calls `_recompute_challenge_users()` to sync domain-matched users
2. Calls `_generate_goals_from_challenge()` to create missing goals
3. Per challenge: checks if report is due, or if any goals closed since last report
4. Calls `_check_challenge_reward()` for each challenge

#### `_recompute_challenge_users()`

Compares current `user_ids` against re-evaluated `user_domain`. Users no longer matching the domain are **not automatically removed** -- only new matching users are added. This preserves manually invited and assigned users. No-op for challenges without `user_domain`.

#### `_generate_goals_from_challenge()`

Creates `gamification.goal` for each `(line, user)` without an existing goal for the current period:

1. For each line, SQL finds users who already have a goal for this line/period
2. Computes `participant_user_ids - user_with_goal_ids` to find who needs new goals
3. Users who used to match the domain but no longer do (in `user_with_goal_ids` but not in `participant_user_ids`) have their goals deleted
4. Goals are created with initial `current` value past the threshold:
   - `condition=higher`: `current = min(target - 1, 0)` (just below target)
   - `condition=lower`: `current = max(target + 1, 0)` (just above target)
   This forces immediate recomputation on the first cron run
5. Calls `update_goal()` on all newly created goals
6. If `commit_gamification` in context, commits after each challenge

**L4 Edge Case -- `user_squating_challenge_ids`:** Users who were matched by the domain, received goals, but no longer match (e.g., moved to a different department) have their goals unlinked. This prevents orphaned goals from accumulating.

#### `_check_challenge_reward(force=False)`

Called at the end of each `_update_all()` call and at `state=done` with `force=True`. Processes two reward types:

**1. Completion badge (`reward_id`):**
- Uses `_read_group` to find users with all goals in `reached` state for the current period
- Checks `count == len(challenge.line_ids)` to verify every goal succeeded
- With `reward_realtime=True`: checks if user already received the badge for this challenge (prevents duplicates)
- Without `reward_realtime`: only awards at challenge end (at `challenge_ended`)

**2. Top-N badges (`reward_first_id/second/third`):**
- Only awarded at `challenge_ended` (end of period, not in real-time)
- Uses `_get_topN_users(3)` to determine rankings
- `challenge_ended` is `True` when `force=True` OR `end_date == yesterday`

**L4 Edge Case -- `reward_realtime=False`:** Both completion badge and top-3 are deferred to `challenge_ended`. This means users who complete all goals during a monthly challenge won't receive their completion badge until the end of the month.

**L4 Edge Case -- `reward_failure`:** When `False`, only users who completed every goal appear in the top-N ranking. When `True`, all users are ranked by total completeness, allowing partial completion to be rewarded.

#### `action_start()` / `action_check()`

- **`action_start()`:** Sets `state = 'inprogress'` via `write()`. The `write()` method triggers `_recompute_challenge_users()` and `_generate_goals_from_challenge()`.
- **`action_check()`:** Unlinks all in-progress goals for this challenge, then calls `_update_all()` to regenerate them. Used to force full goal recomputation after editing participants or challenge lines.

#### `action_report_progress()` / `report_progress()`

Manual report dispatch. For `visibility_mode=ranking`: posts to all participants and challenge followers as a `mail.mt_comment` on the challenge record. For `visibility_mode=personal`: sends individual `message_notify` to each user. Optionally copies to `report_message_group_id` channel. Updates `last_report_date` after sending.

#### `accept_challenge()` / `discard_challenge()`

User-facing actions from the invitation UI. Both post a chatter message, then:
- `accept_challenge()`: removes user from `invited_user_ids`, adds to `user_ids`, generates goals
- `discard_challenge()`: removes user from `invited_user_ids` only

#### `action_view_users()`

Returns an `ir.actions.act_window` for `res.users` filtered to `id IN challenge.user_ids`. Used by the `# Users` smart button on challenge form views.

#### `_get_topN_users(n)`

Returns exactly `n` `res.users` records (or `False` for unfilled ranks):

1. Iterates each user and computes `total_completeness`
2. For `condition=higher` goals: `total += 100.0 * current / target_goal` (can exceed 100%)
3. For `condition=lower` goals: `total += 100` if `reached`, else `total += 0` (binary)
4. Sorts by `(all_reached, total_completeness)` descending
5. If `reward_failure=False`: truncates to only `all_reached=True` users using `itertools.takewhile`
6. Uses `itertools.chain` to append `False` values up to `n`, then takes first `n`

Returns tuple: `(first_user, second_user, third_user)`.

#### `_get_serialized_challenge_lines()`

Serializes challenge progress for JS dashboards and reports. In `ranking` mode:
- Sorts goals by `(-completeness, -current)` for `condition=higher` (best first)
- Pads with mock empty goals to always show at least 3 entries for display
- In `personal` mode: returns empty list if user's goal is not in `reached` state

---

## `gamification.challenge.line`

**File:** `gamification_challenge_line.py`
**Table:** `gamification_challenge_line`
**Order:** `sequence, id`

Simple join table linking a challenge to a goal definition with a specific target value. Acts as the goal template within a challenge.

| Field | Type | Required | Ondelete | Purpose |
|---|---|---|---|---|
| `challenge_id` | `Many2one` | Yes | cascade | Parent challenge |
| `definition_id` | `Many2one` | Yes | cascade | Goal computation template |
| `sequence` | `Integer` | — | — | Display order |
| `target_goal` | `Float` | Yes | — | Target value to reach |

Related fields from `definition_id`: `name`, `condition`, `suffix`, `monetary`, `full_suffix`. These are `related` fields with `readonly=True`, providing convenience access without joins.

---

## `gamification.goal.definition`

**File:** `gamification_goal_definition.py`
**Table:** `gamification_goal_definition`

Defines how a goal's current value is computed. Other modules (e.g., `website_blog`, `hr_org_chart`) register goal definitions to expose their data to gamification. This is the extension point for third-party gamification.

### Computation Modes

| Mode | Description | Implementation |
|---|---|---|
| `manually` | User enters value via wizard | Wizard + reminder cron |
| `count` | Count records matching domain | `search_count()` |
| `sum` | Sum numeric field on matching records | `_read_group(...aggregate=['field:sum'])` |
| `python` | Execute custom Python code | `safe_eval` with defined context |

### Fields

#### Identity & Value

| Field | Type | Default | Purpose |
|---|---|---|---|
| `name` | `Char` | required, translate | Goal name |
| `description` | `Text` | — | Goal description |
| `monetary` | `Boolean` | `False` | Value in company currency |
| `suffix` | `Char` | — | Unit label (translated), e.g., `reviews` |
| `full_suffix` | `Char` (computed) | — | Currency symbol + suffix |

#### Computation Configuration

| Field | Type | Default | Purpose |
|---|---|---|---|
| `computation_mode` | `Selection` | `manually` | How to compute |
| `display_mode` | `Selection` | `progress` | `progress` (bar) or `boolean` |
| `condition` | `Selection` | `higher` | `higher` or `lower` for success |

#### Model & Field Configuration

| Field | Type | Purpose |
|---|---|---|
| `model_id` | `Many2one(ir.model)` | Target model for count/sum modes |
| `model_inherited_ids` | `Many2many(ir.model)` | Related: inherited models |
| `field_id` | `Many2one(ir.model.fields)` | Field to sum (for `sum` mode) |
| `field_date_id` | `Many2one(ir.model.fields)` | Date field for time filtering |
| `domain` | `Char` | Record filter (user-independent), `user` refers to goal owner |

#### Batch Mode

| Field | Type | Purpose |
|---|---|---|
| `batch_mode` | `Boolean` | Execute in single query per definition instead of per-user |
| `batch_distinctive_field` | `Many2one` | Field distinguishing users (e.g., `user_id`, `partner_id`) |
| `batch_user_expression` | `Char` | Expression resolving to distinctive field value for a user |

#### Action

| Field | Type | Purpose |
|---|---|---|
| `action_id` | `Many2one` | Action to open for manual update |
| `res_id_field` | `Char` | Field on `res.users` containing `res_id` for the action |

### Methods

#### `_check_domain_validity()`

Uses `safe_eval` to parse the domain and `search_count` to validate it. The `user` context inside the domain is `self.env.user.with_user(self.env.user)` -- a browse record of the admin user. Domain expressions can use `user.id`, `user.partner_id.id`, etc. Raises `SyntaxError` with line text or `ValueError`.

Skipped for `computation_mode != 'count' or 'sum'`.

#### `_check_model_validity()`

Validates that `field_id` exists on `model_id` and is stored. Uses `Model._fields.get()` to access field metadata. Raises `UserError` with the specific field name if not found or not stored. Skipped if `field_id` or `model_id` is empty.

#### `create()` / `write()`

Both trigger validation:
- If `computation_mode` in `('count', 'sum')` and `domain` or `model_id` changed: `_check_domain_validity()`
- If `field_id`, `model_id`, or `batch_mode` changed: `_check_model_validity()`

---

## `gamification.goal`

**File:** `gamification_goal.py`
**Table:** `gamification_goal`
**Order:** `start_date desc, end_date desc, definition_id, id`

Individual goal instance for a specific user over a time period.

### Goal State Machine

```
draft ──(action_start)──> inprogress ──(target reached)──> reached
                          │                              ▲
                          ├──(end_date passed)──> failed  │
                          │                              │
                          └──(action_cancel)──> inprogress┘
```

### Fields

#### Identity & Assignment

| Field | Type | Required | Ondelete | Purpose |
|---|---|---|---|---|
| `definition_id` | `Many2one` | Yes | cascade | Goal template |
| `user_id` | `Many2one` | Yes | cascade, bypass_search_access | Goal owner |
| `user_partner_id` | `Many2one` | — | — | Cached partner |
| `line_id` | `Many2one` | — | cascade | Challenge line |
| `challenge_id` | `Many2one` (related, stored, indexed) | — | — | Parent challenge |

`bypass_search_access=True` on `user_id` allows goal searches to bypass access rules for the `res.users` model, which is needed because goals may reference any user regardless of the current user's permissions.

#### Time Period

| Field | Type | Default | Purpose |
|---|---|---|---|
| `start_date` | `Date` | `today` | Goal period start |
| `end_date` | `Date` | — | Goal period end; null = no deadline |

#### Values & State

| Field | Type | Default | Purpose |
|---|---|---|---|
| `target_goal` | `Float` | required | Target to reach |
| `current` | `Float` | `0` | Current measured value |
| `completeness` | `Float` (computed) | — | Percentage 0-100 |
| `state` | `Selection` | `draft` | `draft`, `inprogress`, `reached`, `failed`, `canceled` |
| `closed` | `Boolean` | — | Marks goal as final/closed |
| `to_update` | `Boolean` | — | Flag for batch update |

#### Display & Tracking

| Field | Type | Purpose |
|---|---|---|
| `color` | `Integer` (computed) | Kanban color based on state/dates |
| `remind_update_delay` | `Integer` | Days before reminder |
| `last_update` | `Date` | Last manual update (auto-set on write) |

#### Related from Definition

| Field | Type | Source |
|---|---|---|
| `definition_description` | `Text` | `definition_id.description` |
| `definition_condition` | `Selection` | `definition_id.condition` |
| `definition_suffix` | `Char` | `definition_id.full_suffix` |
| `definition_display` | `Selection` | `definition_id.display_mode` |

### Methods

#### `_get_completion()`

**Decorators:** `@api.depends('current', 'target_goal', 'definition_id.condition')`

For `condition=higher`: `completeness = round(100.0 * current / target, 2)` capped at 100%. For `condition=lower`: `completeness` is either 0 or 100 -- binary, not proportional.

**L4 Edge Cases:**
- `target_goal = 0`: returns 0 (avoids division by zero)
- `condition=lower` with `current < target`: returns 100% (goal met)
- `condition=lower` with `current >= target`: returns 0% (goal not met)

#### `_compute_color()`

**Decorators:** `@api.depends('end_date', 'last_update', 'state')`

Sets kanban color:
- `2` (orange): `end_date < last_update` AND `state == 'failed'` (goal failed early)
- `5` (green): `end_date < last_update` AND `state == 'reached'` (goal reached early)
- `0` (default): all other cases

This highlights early completion or early failure relative to the end date.

#### `_get_write_values(new_value)`

Determines state changes from a new computed value:

```python
result = {'current': new_value}
if new_value == self.current:
    return {}  # no-op
if (condition == 'higher' and new_value >= target) \
   or (condition == 'lower' and new_value <= target):
    result['state'] = 'reached'
elif end_date and today > end_date:
    result['state'] = 'failed'
    result['closed'] = True
return {self: result}  # dict keyed by goal for update_goal()
```

Returns a dict keyed by `self` (the goal record): `{(<goal>,): {values}}`. This is for compatibility with `update_goal()`'s loop structure.

**L4 Edge Case:** The `closed=True` on failure marks the goal as final. A `reached` goal is **not** closed, meaning it can still change state if the value drops below the target.

#### `update_goal()`

The main recomputation engine. Groups goals by `definition_id` for batch processing:

**`manually` mode:** Only calls `_check_remind_delay()` per goal. No value recomputation.

**`python` mode:** Executes `definition.compute_code` via `safe_eval` in exec mode with context:
```python
cxt = {
    'object': goal,       # The goal record itself
    'env': self.env,
    'date': date,
    'datetime': datetime,
    'timedelta': timedelta,
    'time': time,
}
safe_eval(code, cxt, mode="exec")
result = cxt.get('result')
```
Result must be a `float` or `int`. Invalid return logs an ERROR.

**`count` or `sum` (non-batch mode):**
```python
for goal in goals:
    domain = safe_eval(definition.domain, {'user': goal.user_id})
    if goal.start_date and field_date_name:
        domain.append((field_date_name, '>=', goal.start_date))
    if goal.end_date and field_date_name:
        domain.append((field_date_name, '<=', goal.end_date))
    if sum_mode:
        res = Obj._read_group(domain, [], [f'{field_name}:{definition.computation_mode}'])
        new_value = res[0][0] or 0.0
    else:  # count
        new_value = Obj.search_count(domain)
    goals_to_write.update(goal._get_write_values(new_value))
```

**`count` or `sum` (batch mode):**
```python
general_domain = ast.literal_eval(definition.domain)
for goal in goals:
    start, end = goal.start_date, goal.end_date
    subqueries.setdefault((start, end), {}).update({
        goal.id: safe_eval(definition.batch_user_expression, {'user': goal.user_id})
    })
for (start_date, end_date), query_goals in subqueries.items():
    subquery_domain = list(general_domain)
    subquery_domain.append((field_name, 'in', list(set(query_goals.values()))))
    if start_date: subquery_domain.append((field_date_name, '>=', start_date))
    if end_date: subquery_domain.append((field_date_name, '<=', end_date))
    user_values = Obj._read_group(subquery_domain, groupby=[field_name], ...)
```

**L4 Performance:** Batch mode groups users by `(start_date, end_date)` and distinctive field value, reducing N queries to 1 per `(start_date, end_date)` combination. For a monthly challenge with 50 users and 5 definitions, non-batch executes up to 250 queries. Batch mode with uniform dates executes as few as 5 queries (one per definition). The `batch_distinctive_field` (e.g., `user_id`) maps goals to the field on the target model that identifies the responsible user.

#### `_check_remind_delay()`

If `remind_update_delay` is set and `last_update` is more than that many days ago, sends the `gamification.email_template_goal_reminder` template via `message_notify` with `mail.mail_notification_light` layout, then returns `{'to_update': True}`. Returns empty dict if no reminder is due.

**L4 Edge Case:** Reminders are only sent once per goal lifecycle (when transitioning from no reminder to needing one). The `to_update=True` return value sets a flag, but subsequent cron runs will not re-trigger because `last_update` will be updated.

#### `write()`

Overridden to:
1. Always set `last_update = today` on any write
2. Raise `UserError` if modifying `definition_id` or `user_id` on non-draft goals (prevents drag-and-drop in kanban from corrupting goal assignments)
3. If `current` changes and challenge report frequency is `onchange`, trigger `report_progress(subset_goals=user)`

#### `create()`

Passes `no_remind_goal=True` in context to suppress reminder logic during initial goal creation (otherwise new goals would immediately trigger reminders).

#### Action Methods

| Method | Trigger | Behavior |
|---|---|---|
| `action_start()` | Manual button | Sets `state='inprogress'` + calls `update_goal()` |
| `action_reach()` | Manual button | Sets `state='reached'` (may be reset at next cron if value dropped) |
| `action_fail()` | Manual button | Sets `state='failed'`, sets `closed=True` |
| `action_cancel()` | Manual button | Resets `state='inprogress'` (state re-evaluated at next cron) |

`action_reach()` manually marks a goal as completed. The goal is not closed, so the next `update_goal()` call will recompute the actual value and may revert the state if the condition is no longer met.

#### `get_action()`

Priority: action from `definition.action_id` > wizard for `manually` > False. When using action with `res_id_field`, evaluates the field expression against `self.env.user` to get the `res_id` for the window action.

---

## `gamification.karma.tracking`

**File:** `gamification_karma_tracking.py`
**Table:** `gamification_karma_tracking`
**Order:** `tracking_date desc, id desc`

Immutable audit log of all karma changes per user.

### Fields

| Field | Type | Default | Purpose |
|---|---|---|---|
| `user_id` | `Many2one` | required, cascade | User whose karma changed |
| `old_value` | `Integer` | readonly | Karma before change |
| `new_value` | `Integer` | required | Karma after change |
| `gain` | `Integer` (computed) | — | `new_value - old_value` |
| `consolidated` | `Boolean` | — | Whether archived via consolidation |
| `tracking_date` | `Datetime` | `now`, indexed | When change occurred |
| `reason` | `Text` | `Add Manually` | Description |
| `origin_ref` | `Reference` | `res.users,<uid>` | Source record |
| `origin_ref_model_name` | `Selection` (computed, stored) | — | Model name of origin_ref |

### Methods

#### `create()`

- If `old_value` not provided: fills with user's current karma from `karma_per_users` dict (batch-fetched for all users)
- If `gain` is provided (instead of `new_value`): computes `new_value = old_value + gain` and removes `gain` from vals

#### `_consolidate_cron()`

Class method scheduled monthly. Calls `_process_consolidate()` with `from_date = first day of month, 2 months ago`.

#### `_process_consolidate(from_date, end_date=None)`

Archives karma tracking records older than 2 months using a CTE-based SQL INSERT:

```sql
WITH old_tracking AS (
    SELECT DISTINCT ON (user_id) user_id, old_value, tracking_date
      FROM gamification_karma_tracking
     WHERE tracking_date BETWEEN %(from_date)s AND %(end_date)s
       AND consolidated IS NOT TRUE
    ORDER BY user_id, tracking_date ASC, id ASC
)
INSERT INTO gamification_karma_tracking (
    user_id, old_value, new_value, tracking_date, origin_ref,
    consolidated, reason)
SELECT DISTINCT ON (nt.user_id)
       nt.user_id, ot.old_value AS old_value, nt.new_value AS new_value,
       ot.tracking_date AS from_tracking_date,
       %(origin_ref)s AS origin_ref, TRUE,
       %(reason)s
  FROM gamification_karma_tracking AS nt
  JOIN old_tracking AS ot ON ot.user_id = nt.user_id
 WHERE nt.tracking_date BETWEEN %(from_date)s AND %(end_date)s
   AND nt.consolidated IS NOT TRUE
ORDER BY nt.user_id, nt.tracking_date DESC, id DESC
```

After INSERT, unlinks all original non-consolidated records in the period using `skip_karma_computation=True` context.

**L4 Edge Cases:**
- `consolidated=True` records are **excluded** from consolidation, preventing double-archiving
- The consolidated record loses original `origin_ref` and `reason` -- attribution data is destroyed
- `flush_model()` before the SQL ensures pending ORM writes are persisted before raw deletion
- `DISTINCT ON (user_id)` with `ORDER BY tracking_date DESC, id DESC` gives the most recent `new_value` per user
- `ot.old_value AS old_value` gives the oldest `old_value` (first tracking in period)

---

## `gamification.karma.rank`

**File:** `gamification_karma_rank.py`
**Table:** `gamification_karma_rank`
**Inherits:** `image.mixin`
**Order:** `karma_min`

Defines named rank tiers based on karma thresholds.

### Fields

| Field | Type | Default | Purpose |
|---|---|---|---|
| `name` | `Text` | required, translate | Rank name |
| `description` | `Html` | — | Rank description |
| `description_motivational` | `Html` | — | Phrase shown when user is close to this rank |
| `karma_min` | `Integer` | `1` | Minimum karma to reach this rank |
| `user_ids` | `One2many(res.users)` | — | Users at this rank |
| `rank_users_count` | `Integer` (computed) | — | Count of users |

**SQL Constraint:** `CHECK(karma_min > 0)` -- ranks must have positive thresholds.

### Methods

#### `create()`

After rank creation, calls `_recompute_rank()` for all users with karma >= the minimum among created ranks. Uses `sudo()` to bypass access rights.

#### `write()`

When `karma_min` changes:
1. Records current rank ordering before write
2. After write, compares the new ordering
3. If ordering changed: recomputes for users with karma >= lowest new threshold
4. If ordering unchanged: recomputes only users whose karma falls in the changed range

---

## `res.users` (Gamification Extension)

**File:** `res_users.py`
**Inherits:** `res.users`

Extends `res.users` with karma, badge, and rank fields and methods.

### Fields

| Field | Type | Default | Purpose |
|---|---|---|---|
| `karma` | `Integer` | computed | Total karma (stored) |
| `karma_tracking_ids` | `One2many` | — | Karma change history (admin only: `base.group_system`) |
| `badge_ids` | `One2many` | — | All badges received |
| `gold_badge` | `Integer` (computed) | — | Gold badges count |
| `silver_badge` | `Integer` (computed) | — | Silver badges count |
| `bronze_badge` | `Integer` (computed) | — | Bronze badges count |
| `rank_id` | `Many2one` | — | Current karma rank, `btree_not_null` index |
| `next_rank_id` | `Many2one` | — | Next rank to achieve |

### Methods

#### `create()`

On user creation, if `karma` is passed in `vals`, calls `_add_karma_batch()` with `gain=int(vals['karma'])`, `old_value=0`, `reason='User Creation'`. New users without explicit karma start at 0.

#### `write()`

When `karma` is written directly (e.g., admin changes karma in the UI), computes the delta from current karma and calls `_add_karma_batch()` with `gain=delta`. This ensures every karma change creates a tracking record even when set directly on the field.

#### `_compute_karma()`

**Decorators:** `@api.depends('karma_tracking_ids.new_value')`

Queries `gamification_karma_tracking` for the most recent `new_value` per user:

```sql
SELECT DISTINCT ON (user_id) user_id, new_value
  FROM gamification_karma_tracking
 WHERE user_id = ANY(%(user_ids)s)
 ORDER BY user_id, tracking_date DESC, id DESC
```

Uses `skip_karma_computation` context check to skip entirely during consolidation. After computing, calls `_recompute_rank()`.

**L4 Edge Case:** `DISTINCT ON` requires `ORDER BY user_id` plus `tracking_date DESC, id DESC`. The most recent tracking determines the current karma. Users with no tracking records get `karma = 0`.

#### `_get_user_badge_level()`

**Decorators:** `@api.depends('badge_ids')`

Raw SQL query counting badges per level per user. Resets counts to 0 before counting. Directly assigns to browse records:
```python
self.browse(user_id)['{}_badge'.format(level)] = count
```

The `level` values from the database are `gold`, `silver`, `bronze` but the field names are `gold_badge`, `silver_badge`, `bronze_badge` -- the suffix `_badge` is appended dynamically.

#### `_add_karma_batch(values_per_user)`

Core karma write mechanism. Creates `gamification.karma.tracking` records with `sudo()`:
- `old_value`: current karma or provided override
- `new_value`: `old_value + gain`
- `origin_ref`: `{source._name},{source.id}`
- `reason`: `{reason} ({source_display_name} #{source_id})`

Uses `sudo()` to bypass access control since regular users cannot create `gamification.karma.tracking` records.

#### `_recompute_rank()` / `_recompute_rank_bulk()`

**Per-user mode** (`_recompute_rank`): Iterates ranks from highest to lowest for each user. Efficient for small user sets (< 3x the number of ranks).

**Bulk mode** (`_recompute_rank_bulk`): Iterates ranks from highest to lowest, finding all users in each rank tier in a single search per rank. The domain is complex:

```python
dom = [
    ('karma', '>=', r['karma_min']),
    ('id', 'in', users_todo.ids),
    '|',
        '|', ('rank_id', '!=', rank_id), ('rank_id', '=', False),
        '|', ('next_rank_id', '!=', next_rank_id), ('next_rank_id', '=', False if next_rank_id else -1),
]
```

**L4 Edge Case -- next_rank_id assignment:** The `next_rank_id` is set to the rank immediately above the current one during bulk recomputation. This requires tracking `next_rank_id = r['rank'].id` from the previous iteration of the rank loop (highest to lowest). The comment in the code notes: "wtf, next_rank_id should be a related on rank_id.next_rank_id and life might get easier."

#### `_get_tracking_karma_gain_position(user_domain, from_date, to_date)`

Returns each user's karma gain in the period and their absolute ranking position. Uses a window function:
```sql
SELECT final.user_id, final.karma_gain_total, final.karma_position
FROM (
    SELECT intermediate.user_id, intermediate.karma_gain_total,
           row_number() OVER (ORDER BY intermediate.karma_gain_total DESC) AS karma_position
    FROM (
        SELECT "res_users".id as user_id,
               COALESCE(SUM("tracking".new_value - "tracking".old_value), 0) as karma_gain_total
        FROM %(from_clause)s
        LEFT JOIN "gamification_karma_tracking" as "tracking"
               ON "res_users".id = "tracking".user_id AND "res_users"."active" IS TRUE
        WHERE %(where_clause)s %(date_filter)s
        GROUP BY "res_users".id
    ) intermediate
) final
WHERE final.user_id IN %(user_ids)s
```

Uses `COALESCE(SUM(...), 0)` to handle users with no tracking records in the period. The `INNER JOIN` vs `LEFT JOIN` distinction in the inner query determines whether users with no karma changes are included.

#### `_get_karma_position(user_domain)`

Returns each user's absolute karma ranking within a filtered user set. Uses a window function to number all users by karma descending, then filters to the current recordset:

```sql
SELECT sub.user_id, sub.karma_position
FROM (
    SELECT "res_users"."id" as user_id,
           row_number() OVER (ORDER BY res_users.karma DESC) AS karma_position
    FROM %(from_clause)s
    WHERE %(where_clause)s
) sub
WHERE sub.user_id IN %(user_ids)s
```

Unlike `_get_tracking_karma_gain_position()`, this ranks by **total accumulated karma** (not karma gained in a period). Used for "You are ranked #X on the leaderboard" display.

#### `action_karma_report()`

Window action opening the `gamification.karma.tracking` list view filtered to the current user. Available on the user form via a smart button. Requires `base.group_system` to see tracking data.

#### `_get_next_rank()`

Returns the next rank to achieve for a user. Priority: `next_rank_id` if set, otherwise searches for the lowest-ranked rank above the user's current `rank_id.karma_min`. Used as a fallback for fresh users with karma=0 and no explicit `next_rank_id`.

#### `get_gamification_redirection_data()`

Hook method for other modules (e.g., `forum`) to add redirect buttons in new-rank-reached notification emails. Default returns an empty list. Extending modules override and return `[{url, label}]` pairs.

---

## Wizards

### `gamification.badge.user.wizard` (Transient)

**Purpose:** Allow users to grant a badge to another user via UI dialog.

| Field | Type | Purpose |
|---|---|---|
| `user_id` | `Many2one(res.users)` | Badge recipient |
| `badge_id` | `Many2one(gamification.badge)` | Badge to grant |
| `comment` | `Text` | Optional message |

**`action_grant_badge()`:** Prevents self-granting (`uid == user_id`). Creates `gamification.badge.user` with `sender_id = uid`. The badge's `check_granting()` is called during `create()` as the authorization gate.

### `gamification.goal.wizard` (Transient)

**Purpose:** Allow users to manually update their goal's current value.

| Field | Type | Purpose |
|---|---|---|
| `goal_id` | `Many2one(gamification.goal)` | Goal to update |
| `current` | `Float` | New value |

**`action_update_current()`:** Writes new value, clears `to_update`, calls `update_goal()` to recompute state. Returns `False` (closes the wizard popup without a redirect).

---

## Cron Jobs

| Name | Model | Schedule | Action |
|---|---|---|---|
| `Gamification: Goal Challenge Check` | `gamification.challenge` | Daily (no specific time) | `_cron_update()` |
| `Gamification: Karma tracking consolidation` | `gamification.karma.tracking` | Monthly, 1st day 4AM | `_consolidate_cron()` |

The consolidation cron nextcall is set via `relativedelta(day=1, months=1)` from install time, meaning it fires on the 1st of each month at 4AM server time.

---

## Default Data

Installed automatically via `data/` XML files (noupdate).

### Karma Ranks (`gamification_karma_rank_data.xml`)

Five tiers seeded on module install:

| XML ID | Name | `karma_min` |
|---|---|---|
| `gamification.rank_newbie` | Newbie | 1 |
| `gamification.rank_student` | Student | 100 |
| `gamification.rank_bachelor` | Bachelor | 500 |
| `gamification.rank_master` | Master | 2000 |
| `gamification.rank_doctor` | Doctor | 10000 |

`rank_newbie` is the default rank for new users (lowest threshold above 0). Each rank has an SVG image, an HTML description, and a motivational phrase (`description_motivational`) displayed when a user is close to reaching it.

Two `gamification.karma.tracking` seed records also created:
- `base.user_root` → karma 2500, reason "I am the Root!"
- `base.user_admin` → karma 2500, reason "I am the Admin!"

### Default Badges (`gamification_badge_data.xml`)

Four badge definitions seeded:

| XML ID | Name | `rule_auth` | `rule_max` | Notes |
|---|---|---|---|---|
| `gamification.badge_good_job` | Good Job | `everyone` | No | Default peer-to-peer badge |
| `gamification.badge_problem_solver` | Problem Solver | `everyone` | No | |
| `gamification.badge_hidden` | Hidden | `nobody` | — | `active=False`; for challenge rewards |
| `gamification.badge_idea` | Brilliant | `everyone` | Yes, max 2/month | Limited monthly sending |

The `Hidden` badge has `rule_auth=nobody`, meaning it cannot be manually granted and can only be awarded through challenge rewards. The `Brilliant` badge has a monthly limit of 2 per sender.

### Onboarding Challenges (`gamification_challenge_data.xml`)

Two `inprogress` challenges auto-started on install:

**`gamification.challenge_base_discover`** ("Complete your Profile"):
- Participants: all users in `base.group_user` (via `user_domain`)
- Goals: "Set your Timezone" (boolean, count records where `partner_id.tz != False`)
- Period: `once`, visibility: `personal`

**`gamification.challenge_base_configure`** ("Setup your Company"):
- Participants: users in `base.group_erp_manager` (via `user_domain`)
- Goals:
  - "Set your Company Data" (condition=`lower`, target=0 -- satisfied when company name is not `YourCompany`)
  - "Set your Company Logo" (boolean, target=1)
  - "Invite new Users" (boolean, count other users)
- Period: `once`, visibility: `personal`

Both use `report_message_frequency=never` and `challenge_category=other` (appear in Settings menus, not HR menus).

### Demo Data

Demo data (`demo/` XML) populates karma tracking history for realistic leaderboard demos:

- **`base.user_demo`**: 5 backdated tracking records showing progression from 0 → 1000 → 1500 → 2000 → 2050 → 2500 over the past month
- **`base.demo_user0`**: 5 backdated tracking records showing 0 → 5 → 10 → 20 → 25 → 30
- **`base.user_admin`**: 3 backdated records supplementing the noupdate seed (2000 → 2250 → 2500)

The motivational rank phrases for Student, Bachelor, Master, and Doctor ranks are also updated in demo mode to include humorous reward images (mug, wand, hat, unicorn) alongside the motivational text. A `<function name="unlink">` pattern cleans up duplicate seed records during demo data reinstall to prevent double-counting.

### Module-wide

1. **SQL safety:** Multiple methods upgraded from `cr.execute(query % params)` to `execute_query(SQL(...))` with `SQL.identifier` for dynamic column/table names. Affected: `_get_owners_info()`, `_get_tracking_karma_gain_position()`, `_get_karma_position()`.

2. **`mail_presence` table:** The `_update_all()` goal filtering joins on `mail_presence.last_presence`. This table was introduced in Odoo 16+ as part of the presense/online status system. The join uses `SESSION_LIFETIME` from `odoo.http` (imported at module level) to filter out users whose sessions have expired.

3. **`_render_field()`:** Email template rendering switched from `render_template()` to `_render_field()` for XSS-safe rendering.

4. **`ast.literal_eval` for domain:** `_get_challenger_users()` uses `ast.literal_eval` (safe, no code execution risk) instead of `safe_eval` for domain parsing.

### Karma Tracking

5. **Consolidation via CTE:** `_process_consolidate()` rewritten from a Python loop (find oldest, find newest per user, delete intermediate) to a single SQL CTE INSERT. This reduces consolidation time from O(N) queries to O(1) query.

6. **`flush_model()`:** Added `flush_model()` call before raw SQL in consolidation to ensure pending ORM writes are persisted before the raw DELETE.

### Challenge and Goal

7. **`search_fetch`:** `_get_serialized_challenge_lines()` uses `search_fetch` (Odoo 16+) for single-goal retrieval in personal mode, replacing `search` + `read`.

8. **Badge granting validation moved to `create()`:** In Odoo 18, the badge user creation validated granting in the wizard. In Odoo 19, this validation is in the `gamification.badge.user.create()` method itself, making it the single authoritative gate.

9. **`reward_realtime` default:** Changed to `True` by default. This means completion badges are awarded in real-time rather than only at challenge end.

---

## Performance Considerations

### Batch Computation Patterns

The goal system has two key batch patterns that are critical for performance at scale:

**Pattern 1 -- Batch mode (`definition.batch_mode=True`):**
Groups multiple users into a single `_read_group` query. Essential for challenges with many participants. Without batch mode, each `(user, goal_definition)` pair triggers a separate `search_count` or `read_group` query. For a challenge with 100 users and 5 goal definitions, non-batch mode executes up to 500 queries per cron run. Batch mode with uniform dates executes as few as 5 queries.

**Pattern 2 -- Presence-based filtering in `_update_all()`:**
Goals are only updated for users with active sessions (recent `mail_presence` record within `SESSION_LIFETIME`). This prevents wasted computation on inactive users but means inactive users' goal values lag behind reality until they next log in.

### Karma Tracking Consolidation

The monthly consolidation cron deletes old tracking records to keep the table lean. Without it, `gamification_karma_tracking` grows with every karma change, slowing down `_compute_karma()` which uses `DISTINCT ON (user_id)` over the entire table. With 10,000 karma changes per month per user, this query becomes expensive.

### Badge Statistics

`_get_owners_info()` uses a single SQL query with JOIN aliases to compute all three statistics (total count, unique user count, unique owner IDs) in one pass, avoiding N+1 queries.

### Rank Recomputation Heuristic

`_recompute_rank()` uses the heuristic `if len(self) > len(ranks) * 3` to decide between per-user and bulk modes. For a system with 10 ranks and fewer than 30 users, per-user mode is faster. Above 30 users, bulk mode's O(ranks) queries beat per-user's O(users) queries.

## L4 Insights: Odoo 18 → 19 Changes

The gamification module received targeted improvements in Odoo 19, primarily around badge security, real-time rewards, and SQL safety:

### Badge Granting Authorization

**Authorization gate moved from wizard to `gamification.badge.user.create()`**: In Odoo 18, badge granting was validated in the wizard's `action_grant_badge()`. In Odoo 19, this validation is centralized in the `gamification.badge.user` model's `create()` method itself, with `badge.check_granting()` as the single authoritative gate. This prevents any code path (wizard, API, or direct `sudo()` write) from bypassing granting rules unless `check_granting()` is explicitly called. This is a significant security hardening change — programmatic badge grants must now call `check_granting()` explicitly or the badge creation will raise `UserError`.

### Challenge Completion Rewards

**`reward_realtime` changed to `True` by default**: The `reward_realtime` field on `gamification.challenge` defaults to `True` in Odoo 19, meaning the completion badge (`reward_id`) is awarded immediately when a user reaches all goals, rather than only at the end of the challenge period. Previously (Odoo 18), the default was `False`, deferring all badge awards to `challenge_ended`. This changes the user experience significantly for periodic challenges — users see immediate gratification rather than waiting until the end of the period.

### SQL Query Safety

**`execute_query(SQL(...))` with `SQL.identifier`**: Methods that build dynamic SQL now use `execute_query(SQL(...))` with `SQL.identifier` for dynamic column and table names. This was migrated across `_get_owners_info()`, `_get_tracking_karma_gain_position()`, and `_get_karma_position()`. This is part of Odoo's broader security initiative to prevent SQL injection through field names, replacing the older `cr.execute(query % params)` pattern.

### Karma Consolidation

**CTE-based consolidation**: `_process_consolidate()` was rewritten from a Python loop (iterating through all records per user) to a single CTE-based SQL INSERT. This was introduced in Odoo 18/19 as part of performance hardening for the karma tracking table, which can grow large in active deployments.

### Presence-Based Goal Filtering

**`mail_presence` join in `_update_all()`**: Goal updates are now filtered to only users with a recent `mail_presence` record (within `SESSION_LIFETIME`). This is an Odoo 16+ feature that gates goal computation to active sessions, preventing unnecessary work for inactive users. The `mail_presence` table was introduced in Odoo 16 as part of the online status system.

---

## Security

### Access Control

The manager role is mapped to `base.group_erp_manager` (not a custom gamification group). Portal users have read-only access to goals, challenges, and challenge lines.

| Model | Group | R | W | C | D |
|---|---|---|---|---|---|
| `gamification.challenge` | `base.group_user` | Yes | No | No | No |
| `gamification.challenge` | `base.group_erp_manager` | Yes | Yes | Yes | Yes |
| `gamification.challenge.line` | `base.group_user` | Yes | No | No | No |
| `gamification.challenge.line` | `base.group_erp_manager` | Yes | Yes | Yes | Yes |
| `gamification.goal` | `base.group_user` | Yes | Yes | No | No |
| `gamification.goal` | `base.group_portal` | Yes | Yes | No | No |
| `gamification.goal` | `base.group_erp_manager` | Yes | Yes | Yes | Yes |
| `gamification.goal.definition` | `base.group_user` | Yes | No | No | No |
| `gamification.goal.definition` | `base.group_portal` | Yes | No | No | No |
| `gamification.goal.definition` | `base.group_erp_manager` | Yes | Yes | Yes | Yes |
| `gamification.badge` | `base.group_user` | Yes | No | No | No |
| `gamification.badge` | `base.group_public` | Yes | No | No | No |
| `gamification.badge` | `base.group_erp_manager` | Yes | Yes | Yes | Yes |
| `gamification.badge.user` | `base.group_user` | Yes | Yes | Yes | No |
| `gamification.badge.user` | `base.group_portal` | Yes | Yes | Yes | No |
| `gamification.badge.user` | `base.group_public` | Yes | No | No | No |
| `gamification.badge.user` | `base.group_erp_manager` | Yes | Yes | Yes | Yes |
| `gamification.karma.tracking` | *(no public group)* | No | No | No | No |
| `gamification.karma.tracking` | `base.group_system` | Yes | Yes | Yes | Yes |
| `gamification.karma.rank` | *(all groups)* | Yes | No | No | No |
| `gamification.karma.rank` | `base.group_system` | Yes | Yes | Yes | Yes |
| `gamification.goal.wizard` | `base.group_user` | Yes | Yes | Yes | No |
| `gamification.badge.user.wizard` | `base.group_user` | Yes | Yes | Yes | No |

### Record Rules (`ir.rule`)

Four record rules govern goal visibility:

**`goal_user_visibility`** (applies to `base.group_user` and `base.group_portal`):
```
domain_force: [
    '|',
        ('user_id', '=', user.id),
        '&',
            ('challenge_id.user_ids', 'in', user.id),
            ('challenge_id.visibility_mode', '=', 'ranking')]
```
A user can read/write goals where:
1. They are the goal owner (`user_id = user.id`), OR
2. They are a participant of the challenge AND the challenge uses `visibility_mode = ranking` (leader board)

**`goal_gamification_manager_visibility`** (applies to `base.group_erp_manager`):
```
domain_force: [(1, '=', 1)]
```
Full access to all goals without restriction.

**`goal_global_multicompany`** (applies to all users via default scope):
```
domain_force: [('user_id.company_id', 'in', company_ids)]
```
Multicompany safety: goals are only visible if the goal owner's company is in the current user's allowed companies.

### Key Security Points

- **`karma_tracking_ids`** restricted to `base.group_system` (Administrators). Regular users cannot see karma change history.
- **`gamification.karma.tracking`** model has no public access at all (`perm_read=0` for blank group). Only `base.group_system` can read/write.
- **Badge grant authorization** is enforced at the `gamification.badge.user` `create()` level via `badge.check_granting()`. Programmatic `sudo()` writes can bypass this if not called explicitly. Always call `check_granting()` when granting badges programmatically.
- **`user_id` on goals** uses `bypass_search_access=True` to allow goals to reference any user regardless of the current user's access rights to `res.users`.
- **Goal assignment protection:** `write()` on goals raises `UserError` if `definition_id` or `user_id` is changed on non-draft goals, preventing kanban drag-and-drop from corrupting goal assignments.
- **`gamification.badge.user` is writeable by all regular users** (`perm_write=1` for `base.group_user`) -- but the `create()` method enforces granting rules, so unauthorized writes raise `UserError`. Portal users can also create badge user records.

---

## Gamification vs Sale Target Comparison

| Aspect | Gamification | Sale Target (`sale_commission`) |
|---|---|---|
| **Scope** | Generic -- any model can register goal definitions | Sales-specific |
| **Badge awarding** | Peer-to-peer or auto via challenge | Auto at quota |
| **Karma** | Full history tracking with consolidation | Not present |
| **Ranking** | Top-N in challenge or cumulative karma | Not present |
| **Periodicity** | Built-in: daily, weekly, monthly, yearly | Manual period management |
| **Cron-driven** | Daily `_cron_update()` processes all challenges | Triggered by invoice validation |
| **Batch computation** | Yes -- batch mode and presence filtering | Typically per-record |
| **Peer granting** | Yes -- badges can be sent between users | No |
| **Goal definitions** | Extensible via `gamification.goal.definition` | Hardcoded per product/salesperson |

The gamification module is designed as a generic platform. Domain-specific modules (e.g., `hr_org_chart`, `website_blog`) register their own goal definitions to expose business metrics to the gamification engine without modifying this module.

---

## Related

- [Modules/mail](Modules/mail.md) -- Email notifications, mail.thread, message_notify
- [Modules/digest](Modules/digest.md) -- Periodic digest reports
- [Modules/HR](Modules/hr.md) -- Employee management
- [Core/API](Core/API.md) -- ORM decorators, safe_eval, domain evaluation
- [Core/Fields](Core/Fields.md) -- Field types used in gamification
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) -- ACL and record rules in gamification
