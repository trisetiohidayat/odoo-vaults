---
Module: gamification
Version: Odoo 18
Type: Business
Tags: #gamification, #challenges, #badges, #karma, #goals
---

# gamification — Gamification: Challenges, Goals & Badges

Drives employee engagement through configurable challenges with goals, a badge awarding system, karma-based ranks, and automatic progress tracking.

**Addon path:** `~/odoo/odoo18/odoo/addons/gamification/`

---

## Data Model Overview

```
gamification.challenge (top-level goal set)
    └── gamification.challenge.line (individual goal within challenge)
          └── gamification.goal.definition (how to measure)

gamification.goal (per-user goal instance)
    ├── gamification.challenge.line  (line that spawned it)
    ├── gamification.goal.definition  (definition)
    └── res.users  (assignee)

gamification.badge (awardable badge)
    └── gamification.badge.user (award record)

gamification.karma.rank (rank tiers)
    └── res.users  (rank_id, next_rank_id)

gamification.karma.tracking (karma change log)
    └── res.users
```

---

## `gamification.challenge` — Challenge

A challenge groups one or more goal lines and assigns them to users, with configurable periodicity and rewards. Inherits `mail.thread` for discussion.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translatable |
| `description` | Text | |
| `state` | Selection | `draft`, `inprogress`, `done`; default `draft` |
| `manager_id` | Many2one → `res.users` | Responsible; defaults to current user |
| `user_ids` | Many2many → `res.users` | Direct participants |
| `user_domain` | Char | Domain string; auto-populates `user_ids` via AST evaluation |
| `user_count` | Integer | Compute: SQL count of active participants |
| `period` | Selection | `once`, `daily`, `weekly`, `monthly`, `yearly` |
| `start_date` | Date | Challenge start; triggers `draft → inprogress` |
| `end_date` | Date | Challenge end; triggers `inprogress → done` |
| `invited_user_ids` | Many2many → `res.users` | Suggested-but-not-joined users |
| `line_ids` | One2many → `gamification.challenge.line` | Goals in this challenge; required |
| `reward_id` | Many2one → `gamification.badge` | Badge for users who complete ALL goals |
| `reward_first_id` | Many2one → `gamification.badge` | Top-1 rank badge |
| `reward_second_id` | Many2one → `gamification.badge` | Top-2 rank badge |
| `reward_third_id` | Many2one → `gamification.badge` | Top-3 rank badge |
| `reward_failure` | Boolean | Allow top-N badges even if not all goals reached |
| `reward_realtime` | Boolean | Award `reward_id` immediately when all goals reached; default True |
| `visibility_mode` | Selection | `personal` (individual goals), `ranking` (leaderboard) |
| `report_message_frequency` | Selection | `never`, `onchange`, `daily`, `weekly`, `monthly`, `yearly` |
| `report_message_group_id` | Many2one → `discuss.channel` | Mirror report to a channel |
| `report_template_id` | Many2one → `mail.template` | Default: `gamification.simple_report_template` |
| `remind_update_delay` | Integer | Days before reminding on stale manual goals |
| `last_report_date` | Date | Tracks when last report was sent |
| `next_report_date` | Date | Compute: `last_report_date + offset` |
| `challenge_category` | Selection | `hr` (HR/Engagement menu), `other` (Settings menu) |

### Challenge States

| State | Meaning | Side Effects |
|-------|---------|-------------|
| `draft` | Not started | Users can be added; goals not generated |
| `inprogress` | Active | `_recompute_challenge_users()` + `_generate_goals_from_challenge()` called |
| `done` | Finished | `_check_challenge_reward(force=True)` called; chatter notification posted |

### Period Logic (`start_end_date_for_period()`)

Helper function computes `(start_date, end_date)` tuples:

| Period | Start | End |
|--------|-------|-----|
| `daily` | Today | Today |
| `weekly` | Monday of this week | Monday + 7 days |
| `monthly` | 1st of this month | Last day of this month |
| `yearly` | Jan 1 | Dec 31 |
| `once` | `challenge.start_date` | `challenge.end_date` |

### User Domain Resolution

`user_domain` is stored as a domain string and evaluated via `ast.literal_eval()` in `create()` and `write()`. The resulting user set replaces or extends `user_ids`. Used for dynamic participant lists (e.g., all users in a department).

```python
# Example user_domain value stored:
'["&", ("groups_id", "=", "base.group_user"), ("active", "=", True)]'
```

### Key Methods

- `action_start()`: Sets `state = 'inprogress'`.
- `action_check()`: Deletes all `inprogress` goals for this challenge, then calls `_update_all()` — effectively a "re-run" without resetting state.
- `action_report_progress()`: Manually sends reports regardless of schedule.
- `action_view_users()`: Redirects to participant user list.
- `accept_challenge()`: Moves user from `invited_user_ids` to `user_ids`, posts chatter message, generates goals.
- `discard_challenge()`: Removes user from `invited_user_ids`, posts chatter message.
- `_recompute_challenge_users()`: Syncs `user_ids` from `user_domain`; removes users who no longer match domain.
- `_generate_goals_from_challenge()`: For each line and each user, creates a `gamification.goal` if one doesn't exist for the current period. Also deletes goals for users who left the challenge.
- `_check_challenge_reward(force=False)`: Awards badges at challenge end. If `reward_realtime=True`, also awards per-user as goals are reached.
- `_reward_user(user, badge)`: Creates `gamification.badge.user` and sends notification email.
- `_get_topN_users(n)`: Ranks users by (1) all goals reached, (2) total completeness. Returns N records (or `False` for empty ranks).
- `_get_serialized_challenge_lines()`: Returns structured dict for frontend kanban/leaderboard display.

### L4 Notes — Goal Generation Logic

`_generate_goals_from_challenge()` is called on:
1. Challenge start (`state → inprogress`)
2. Every `_update_all()` run (daily cron)
3. User accept/join

For each challenge line, it uses raw SQL to find which users already have a goal for the current period, then creates goals for missing users. Goals for users no longer in the challenge are **deleted** (not just unlinked).

Initial goal `current` value is set just over the threshold to force at least one computation pass.

---

## `gamification.challenge.line` — Challenge Line / Goal Template

A single goal definition within a challenge. Defines the `target_goal` but inherits the measurement logic from its `definition_id`.

| Field | Type | Notes |
|-------|------|-------|
| `challenge_id` | Many2one → `gamification.challenge` | Required, cascade delete |
| `definition_id` | Many2one → `gamification.goal.definition` | Required, cascade delete |
| `sequence` | Integer | Default 1 |
| `target_goal` | Float | Required; the value to reach |
| `name` | Char | Related from `definition_id.name` |
| `condition` | Selection | Related: `higher` or `lower` from definition |
| `definition_suffix` | Char | Related: `suffix` from definition |
| `definition_monetary` | Boolean | Related: `monetary` from definition |
| `definition_full_suffix` | Char | Related: `full_suffix` from definition |

---

## `gamification.goal.definition` — Goal Definition

Defines **how** a goal is measured. This is the core abstraction: a definition describes a computation over a model that returns a scalar. Examples: count of `crm.lead` with `state='won'`, sum of `sale.order.amount_total` for the user.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required |
| `description` | Text | |
| `monetary` | Boolean | Target is in company currency; shows currency symbol |
| `suffix` | Char | Unit label (e.g., "leads", "hours") |
| `full_suffix` | Char | Compute: currency symbol + suffix |
| `computation_mode` | Selection | `manually` (user enters value), `count` (auto count), `sum` (auto sum), `python` (custom code) |
| `display_mode` | Selection | `progress` (0–100% bar), `boolean` (done/not-done) |
| `model_id` | Many2one → `ir.model` | Target model for count/sum |
| `model_inherited_ids` | Many2many | Related: inherited models of `model_id` |
| `field_id` | Many2one → `ir.model.fields` | Field to sum (for `sum` mode); must be stored |
| `field_date_id` | Many2one → `ir.model.fields` | Date field for temporal filtering (`date` or `datetime`) |
| `domain` | Char | Filter domain; supports `user` variable for user-specific filtering |
| `batch_mode` | Boolean | Execute in batch (single SQL) vs per-user |
| `batch_distinctive_field` | Many2one → `ir.model.fields` | Field that distinguishes users in batch (e.g., `user_id`, `partner_id`) |
| `batch_user_expression` | Char | Expression evaluated per goal to get value for `batch_distinctive_field` |
| `compute_code` | Text | Python code; must set `result` variable; `object` = goal record |
| `condition` | Selection | `higher` (bigger is better), `lower` (smaller is better) |
| `action_id` | Many2one → `ir.actions.act_window` | Action to open from goal kanban card |
| `res_id_field` | Char | Field name on `res.users` containing `res_id` for the action |

### Domain Variable: `user`

In non-batch mode, the domain can reference `user` as a browse record:

```python
[('user_id', '=', user.id), ('state', '=', 'done')]
```

In batch mode, the domain is static and the `batch_distinctive_field` handles per-user partitioning.

### Validation

- `create()` / `write()`: Calls `_check_domain_validity()` for `count`/`sum` modes — does a dummy `search_count()` to validate.
- `_check_model_validity()`: Validates that `field_id` exists and is stored.

---

## `gamification.goal` — Individual Goal Instance

A per-user, per-period tracking record. Spawned by challenge lines.

| Field | Type | Notes |
|-------|------|-------|
| `definition_id` | Many2one → `gamification.goal.definition` | Required, cascade delete |
| `user_id` | Many2one → `res.users` | Required, `auto_join=True`, cascade delete |
| `line_id` | Many2one → `gamification.challenge.line` | Cascade delete |
| `challenge_id` | Many2one | Related from `line_id.challenge_id`; stored; indexed |
| `start_date` | Date | Default: today |
| `end_date` | Date | No end = always active |
| `target_goal` | Float | Required |
| `current` | Float | Current measured value; default 0 |
| `completeness` | Float | Compute: `0–100%`; respects `condition` |
| `state` | Selection | `draft`, `inprogress`, `reached`, `failed`, `canceled` |
| `to_update` | Boolean | Marked True after reminder |
| `closed` | Boolean | Closed goal (final state marker) |
| `remind_update_delay` | Integer | Days before reminder |
| `last_update` | Date | Last manual update; used for reminder logic |

### Goal States

| State | Meaning | Triggers |
|-------|---------|---------|
| `draft` | Not started | Initial; moved to `inprogress` by `action_start()` |
| `inprogress` | Active tracking | Normal state |
| `reached` | Target met | `_get_write_values()` when `current >= target_goal` (higher) or `<=` (lower) |
| `failed` | End date passed without reaching | `_get_write_values()` when `end_date < today` and not reached |
| `canceled` | Removed from challenge | Manual; reset to `inprogress` by `action_cancel()` |

### `completeness` Computation

```python
if condition == 'higher':
    completeness = 100.0 if current >= target else 100.0 * current / target
else:  # lower
    completeness = 100.0 if current < target else 0.0
```

### Key Methods

- `update_goal()`: Main recomputation method. Dispatches by `computation_mode`:
  - **`manually`**: Only checks reminder delay.
  - **`python`**: Executes `compute_code` with `object = goal`, sets `result`; expects numeric.
  - **`count`**: `Obj.search_count(domain + temporal clauses)`.
  - **`sum`**: `Obj._read_group(..., aggregates=[f'{field_name}:sum'])`; falls back to count if field not numeric.
- Batch mode (`count`/`sum`): Single SQL per `(start_date, end_date)` bucket; uses `_read_group` for aggregation; maps back to goals by `batch_distinctive_field`.
- `_get_write_values(new_value)`: Returns dict of field updates including state transitions.
- `action_start()` / `action_reach()` / `action_fail()` / `action_cancel()`: Manual state transitions.
- `get_action()`: Returns action to update goal — either linked `action_id` (with optional `res_id_field` lookup) or opens `gamification.goal.wizard` for manual goals.

### `write()` Side Effects

- Sets `last_update = today` on every write.
- If `current` changes and `report_message_frequency == 'onchange'`, calls `challenge_id.report_progress()` for that user.

---

## `gamification.badge` — Badge Definition

A badge that users can earn. Inherits `mail.thread` and `image.mixin`.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required, translatable |
| `active` | Boolean | Soft-delete |
| `description` | Html | |
| `level` | Selection | `bronze`, `silver`, `gold` |
| `rule_auth` | Selection | `everyone`, `users` (whitelist), `having` (requires badges), `nobody` (challenge-only) |
| `rule_auth_user_ids` | Many2many → `res.users` | Whitelist for `users` mode |
| `rule_auth_badge_ids` | Many2many → `gamification.badge` | Required badges for `having` mode |
| `rule_max` | Boolean | Monthly sending limit toggle |
| `rule_max_number` | Integer | Max sends per month per user |
| `challenge_ids` | One2many → `gamification.challenge` | Challenges that award this badge |
| `goal_definition_ids` | Many2many → `gamification.goal.definition` | Goals that auto-unlock this badge |
| `owner_ids` | One2many → `gamification.badge.user` | Award records |
| `granted_count` | Integer | Total awards (compute SQL) |
| `granted_users_count` | Integer | Unique users awarded (compute SQL) |
| `unique_owner_ids` | Many2many → `res.users` | Compute: list of unique badge holders |
| `stat_this_month` | Integer | Awards this calendar month |
| `stat_my` | Integer | Current user's awards total |
| `stat_my_this_month` | Integer | Current user's awards this month |
| `stat_my_monthly_sending` | Integer | Current user's sends this month |
| `remaining_sending` | Integer | Compute: remaining sends allowed (0/-1/unlimited) |

### Granting Authorization: `_can_grant_badge()`

Returns a status code:

| Code | Constant | Meaning |
|------|----------|---------|
| 1 | `CAN_GRANT` | User can grant |
| 2 | `NOBODY_CAN_GRANT` | `rule_auth='nobody'` |
| 3 | `USER_NOT_VIP` | User not in `rule_auth_user_ids` |
| 4 | `BADGE_REQUIRED` | User lacks `rule_auth_badge_ids` |
| 5 | `TOO_MANY` | Monthly limit exceeded |

Admin (`is_admin()`) always returns `CAN_GRANT`.

### `check_granting()`

Called before creating a `gamification.badge.user` record (in `badge_user.create()`). Raises `UserError` for non-grantable cases.

---

## `gamification.badge.user` — Badge Award Record

Tracks when a badge was awarded to a user.

| Field | Type | Notes |
|-------|------|-------|
| `user_id` | Many2one → `res.users` | Recipient; required, cascade delete |
| `sender_id` | Many2one → `res.users` | Who awarded it |
| `badge_id` | Many2one → `gamification.badge` | Required, cascade delete |
| `challenge_id` | Many2one → `gamification.challenge` | Optional: which challenge triggered the award |
| `comment` | Text | Optional comment |
| `badge_name` | Char | Related from `badge_id.name` |
| `level` | Selection | Related from `badge_id.level` |

### Key Methods

- `_send_badge()`: Sends `gamification.email_template_badge_received` email notification.
- `create()`: Calls `badge_id.check_granting()` before creating — raises if user cannot grant this badge type.

---

## `gamification.karma.rank` — Karma Rank

Rank tiers based on accumulated karma points.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Text | Required, translatable |
| `description` | Html | |
| `description_motivational` | Html | Shown on user profile |
| `karma_min` | Integer | Required, `CHECK(karma_min > 0)` |
| `user_ids` | One2many → `res.users` | Users at this rank |
| `rank_users_count` | Integer | Compute: count of users at this rank |

### Rank Recomputation

`_recompute_rank()` runs after every karma change. Two algorithms:
- **Per-user** (for small sets): loops users, finds highest matching rank.
- **Bulk** (`_recompute_rank_bulk`): loops ranks, finds users at/below each threshold — more efficient for large user sets.

When rank changes, `_rank_changed()` sends `mail_template_data_new_rank_reached` email (skipped in install mode to avoid spam).

---

## `gamification.karma.tracking` — Karma Change Log

Append-only audit trail of karma changes.

| Field | Type | Notes |
|-------|------|-------|
| `user_id` | Many2one → `res.users` | Indexed, cascade delete |
| `old_value` | Integer | Karma before change |
| `new_value` | Integer | Karma after change |
| `gain` | Integer | Compute: `new_value - old_value` |
| `consolidated` | Boolean | True for records created by consolidation cron |
| `tracking_date` | Datetime | Default: now; indexed |
| `reason` | Text | Description of change |
| `origin_ref` | Reference → `res.users` | Source user (who triggered the change) |
| `origin_ref_model_name` | Selection | Compute: `origin_ref._name` |

### `create()` — Old Value Auto-Fill

If `old_value` is not provided, the user's current karma is fetched and used as `old_value`. If `gain` is provided alongside `old_value`, `new_value` is computed automatically.

### Consolidation: `_process_consolidate()`

A cron runs `_consolidate_cron()` monthly (2 months ago). Consolidation:
1. Finds oldest `old_value` and newest `new_value` per user in the period
2. Creates one consolidated record per user
3. Deletes all intermediate records

This keeps the table lean while preserving the running karma total.

---

## `res.users` Extension

Gamification extends `res.users` with engagement metrics:

| Field | Type | Notes |
|-------|------|-------|
| `karma` | Integer | Compute+store from `gamification.karma.tracking` |
| `karma_tracking_ids` | One2many → `gamification.karma.tracking` | Full karma history |
| `badge_ids` | One2many → `gamification.badge.user` | Badges received |
| `gold_badge` | Integer | Count of gold-level badges |
| `silver_badge` | Integer | Count of silver-level badges |
| `bronze_badge` | Integer | Count of bronze-level badges |
| `rank_id` | Many2one → `gamification.karma.rank` | Current rank |
| `next_rank_id` | Many2one → `gamification.karma.rank` | Next rank to aim for |

### Karma Methods

- `_add_karma(gain, source, reason)`: Add karma to a single user.
- `_add_karma_batch(values_per_user)`: Bulk karma addition; creates tracking records with proper `old_value`/`new_value`.
- `_get_tracking_karma_gain_position(user_domain)`: Returns karma gain ranking with date range support.
- `_get_karma_position(user_domain)`: Returns total karma ranking.
- `_get_next_rank()`: Returns the next rank (by `karma_min`) above current rank.
- `action_karma_report()`: Opens karma tracking list view filtered to this user.

### Karma Tracked on Write

When `karma` is written directly on a user, `_add_karma_batch()` is called with the delta.

---

## Goal Computation: Batch vs Individual (L4)

### Non-Batch Mode (Per-User SQL)

For each goal:
```python
domain = safe_eval(definition.domain, {'user': goal.user_id})
if start_date and field_date_name:
    domain += [(field_date_name, '>=', start_date)]
if end_date and field_date_name:
    domain += [(field_date_name, '<=', end_date)]
if sum_mode:
    new_value = Obj._read_group(domain, [], [f'{field}:sum'])[0][0]
else:
    new_value = Obj.search_count(domain)
```

### Batch Mode (Single SQL)

Groups all goals for the same `(start_date, end_date)` into one query:

```python
general_domain = ast.literal_eval(definition.domain)
for (start_date, end_date), query_goals in subqueries.items():
    subquery_domain = [field_name, 'in', list(set(query_goals.values()))]
    if start_date: subquery_domain.append((date_field, '>=', start_date))
    if end_date: subquery_domain.append((date_field, '<=', end_date))
    if sum_mode:
        user_values = Obj._read_group(subquery_domain, groupby=[field_name], aggregates=[f'{field}:sum'])
    else:
        user_values = Obj._read_group(subquery_domain, groupby=[field_name], aggregates=['__count'])
    # Map back: field_value → goal → write_values
```

Batch mode is dramatically more efficient for challenges with many users and simple domain conditions.

---

## Challenge Reward Flow (L4)

```
_cron_update()  [daily]
    └─ _update_all()
          ├─ Goal.update_goal()  [all inprogress/reached goals]
          ├─ _recompute_challenge_users()
          ├─ _generate_goals_from_challenge()
          └─ _check_challenge_reward()
                ├─ reward_id (badge for completing all goals)
                │     └─ If reward_realtime: awarded per-user as goals reach state=reached
                └─ If end_date reached (or force=True):
                      ├─ reward_first/second/third_id (top 3)
                      └─ Chatter post: challenge finished + winner list
```

### Top-N Ranking Algorithm

1. Iterate all users with goals for the current period
2. For each user: check if all goals are `reached`; compute `total_completeness`
3. Sort by `(all_reached, total_completeness)` descending
4. If `reward_failure=False`: keep only fully successful users
5. Return first N; pad with `False` for empty ranks

---

## Badge Granting Workflow (L4)

1. **Manual grant**: User clicks "Grant Badge" → `gamification.badge.user.create()` → `check_granting()` validates → `_send_badge()` emails recipient.
2. **Challenge award**: `_check_challenge_reward()` → `_reward_user()` → creates `gamification.badge.user` with `challenge_id` set.
3. **Automatic unlock**: `goal_definition_ids` on badge — when a goal definition is marked reached, an external module hook triggers badge awarding (not automatic in base gamification; this is a design hook for downstream modules).

---

## Cron Jobs

| Model | Method | Schedule | Purpose |
|-------|--------|----------|---------|
| `gamification.challenge` | `_cron_update()` | Daily | Start/close scheduled challenges; update all in-progress goals; send reports |
| `gamification.karma.tracking` | `_consolidate_cron()` | Monthly | Consolidate 2-month-old tracking records |

---

## Related Files

- Model: `~/odoo/odoo18/odoo/addons/gamification/models/gamification_challenge.py`
- Model: `~/odoo/odoo18/odoo/addons/gamification/models/gamification_challenge_line.py`
- Model: `~/odoo/odoo18/odoo/addons/gamification/models/gamification_goal.py`
- Model: `~/odoo/odoo18/odoo/addons/gamification/models/gamification_goal_definition.py`
- Model: `~/odoo/odoo18/odoo/addons/gamification/models/gamification_badge.py`
- Model: `~/odoo/odoo18/odoo/addons/gamification/models/gamification_badge_user.py`
- Model: `~/odoo/odoo18/odoo/addons/gamification/models/gamification_karma_rank.py`
- Model: `~/odoo/odoo18/odoo/addons/gamification/models/gamification_karma_tracking.py`
- Model: `~/odoo/odoo18/odoo/addons/gamification/models/res_users.py`
- Demo data: `~/odoo/odoo18/odoo/addons/gamification/data/gamification_badge_data.xml`
- Demo data: `~/odoo/odoo18/odoo/addons/gamification/data/gamification_challenge_data.xml`
- Demo data: `~/odoo/odoo18/odoo/addons/gamification/data/gamification_karma_rank_demo.xml`
