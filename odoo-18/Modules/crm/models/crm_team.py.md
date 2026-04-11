# CRM Team - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/crm/models/crm_team.py`
**Lines:** ~736

---

## Model Overview

`crm.team` (internal name `crm.team`) manages sales teams. It handles team-level pipeline configuration, lead assignment (weighted random and round-robin), and integrates with the mail alias system for inbound email processing. Teams own leads, drive stage pipelines, and coordinate member assignments.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required; team display name |
| `active` | Boolean | Archive/unarchive toggle |
| `company_id` | Many2one | `res.company`; multi-company isolation |
| `user_id` | Many2one | Team leader/manager (`res.users`) |
| `member_ids` | One2many | `crm.team.member`; inverse of `crm_team_member.team_id` |
| `lead_ids` | One2many | `crm.lead`; inverse of `crm.lead.team_id` |
| `alias_id` | Many2one | `mail.alias`; inbound email routing (from `mail.alias.mixin`) |
| `alias_name` | Char | Alias email prefix (e.g., "sales-team-a") |
| `alias_domain_id` | Many2one | `mail.alias.domain`; alias domain |
| `alias_defaults` | Text | Default values for created leads (JSON string) |
| `use_leads` | Boolean | Enable lead feature for this team |
| `use_opportunities` | Boolean | Enable opportunity feature |
| `assignment_enabled` | Boolean | Enable automatic lead assignment |
| `assignment_max` | Integer | Maximum leads assigned per round (team-wide cap) |
| `assignment_domain` | Char/JSON | Domain filter for assignable leads |
| `lead_unassigned_count` | Integer | Stored; count of leads without user_id |
| `lead_all_assigned_month_count` | Integer | Stored; all assigned leads in current month |
| `color` | Integer | Kanban color (1-11) |
| `dashboard_graph_model` | Char | Reporting model for dashboard chart |
| `stage_ids` | Many2many | `crm.stage`; stages visible in this team's pipeline |
| `won_stage_ids` | Many2many | `crm.stage`; stages marked as won (computed inverse) |
| `reply_to` | Char | Fallback reply-to address |
| `group_id` | Many2one | `res.groups`; team-specific access group |
| `resource_calendar_id` | Many2one | `resource.calendar`; working hours for scheduling |

---

## Key Methods

### `_alias_get_creation_values()`
Returns dict for creating the `mail.alias` record when team is created:
```python
{
    'alias_parent_thread_id': team.id,
    'alias_parent_model': 'crm.team',
    'alias_defaults': vals.get('alias_defaults', '{}'),
    'alias_name': vals.get('alias_name'),
    'alias_domain_id': vals.get('alias_domain_id'),
}
```
**Trigger:** Super call from `mail.alias.mixin`.
**Edge case:** If `alias_defaults` is not valid JSON, `mail.alias` creation may fail silently and fall back to the alias engine's default behavior.

### `_cron_assign_leads()`
Scheduled action (typically daily) that calls `_action_assign_leads()` on all teams with `assignment_enabled=True`.
**Triggered by:** `ir.cron` with model `crm.team`, method `_cron_assign_leads`.
**Security:** Runs as superuser (`sudo()`) to avoid access rights limitations.

### `_action_assign_leads()`
The core assignment method. Called per team. Does:
1. `_allocate_leads()`: selects leads for assignment.
2. `_assign_and_convert_leads()`: distributes selected leads to team members.

### `_allocate_leads(team, domain=None)`
**Purpose:** Select which unassigned leads to assign to this team.
**Logic:**
1. Search for unassigned leads (`user_id=False`, `team_id=False`) matching the team's `assignment_domain`.
2. If `use_leads=True` and `assignment_max > 0`, cap total assigned leads to `assignment_max`.
3. Apply deduplication: for leads with same `partner_id`, only the most recently modified lead is considered.
4. Return list of lead IDs to assign.

**Deduplication heuristic:**
```python
dedup_map = {lead.partner_id: lead for lead in leads}
```
Only the most recently modified lead per partner survives deduplication.

### `_assign_and_convert_leads(lead_ids)`
**Purpose:** Assign leads to team members using round-robin weighted by assignment quota.
**Logic:**
1. Search for team members with `assignment_enabled=True` and `assignment_max > 0`.
2. Sort members by `lead_month_count` ascending (least loaded first).
3. For each lead:
   a. Pop the first team member from the rotation (weighted random if `assignment_domain` differs).
   b. Write `user_id` and `team_id` on the lead.
   c. Populate `lead_day_count` and `lead_month_count` for the member.
4. Re-sort and continue until all leads assigned or quota exhausted.

**Round-robin variant:**
If multiple members exist with the same assignment domain characteristics, leads are distributed evenly.

**Quota exhaustion:** When a member's `lead_month_count >= assignment_max`, they are skipped in rotation.

### `unlink()`
**Special behavior:** Before deleting a team, merges all scoring frequency records from this team into the "no team" scoring frequency table.
**Implementation:** Executes raw SQL `INSERT INTO ... ON CONFLICT (team_id, variable, value) DO UPDATE SET won_count = won_count + excluded.won_count, lost_count = lost_count + excluded.lost_count`.
**Rationale:** Preserves PLS scoring data for leads/opportunities that had no assigned team.

---

## Cross-Model Relationships

### With `crm.lead`
- One team owns many leads.
- `_handle_sales_team_assignment()` on lead changes can reassign lead to a team based on partner's `sale_team_id`.
- Lead assignment cron updates `team_id` and `user_id` on selected leads.

### With `crm.team.member`
- One team has many members.
- Member `assignment_max` drives individual lead quotas.
- Member `assignment_domain` allows per-member filtering (intersected with team domain).

### With `crm.stage`
- Team has many stages (`stage_ids`).
- Won stages are tracked via `won_stage_ids` computed field (inverse of `is_won`).

### With `mail.alias`
- Each team has one alias for inbound email-to-lead conversion.
- Alias domain is required for a functional alias.

### With `crm.lead.scoring.frequency`
- Team-specific scoring frequency table for PLS probability computation.
- Frequency records have `team_id` with `ondelete='cascade'`, so they are deleted when team is deleted.

---

## Edge Cases & Failure Modes

1. **Assignment domain empty string:** Treated as no domain filter (all leads match). If `assignment_domain` is set to a falsy value, the domain defaults to `[]`.
2. **Deduplication loses newer leads:** The deduplication map keeps the most recently modified lead per partner. This means older leads with the same partner are silently dropped from the assignment pool.
3. **No active members with assignment_enabled:** `_assign_and_convert_leads` silently does nothing if no members have `assignment_enabled=True` or all have `lead_month_count >= assignment_max`.
4. **Assignment_max = 0:** Team-level cap of 0 means no leads are assigned (early return).
5. **Member-level quota exhaustion:** Once a member hits `lead_month_count >= assignment_max`, they are skipped. If all members are exhausted, no assignment occurs.
6. **Duplicate scoring frequency merge on team delete:** The SQL `ON CONFLICT` merge relies on `(team_id, variable, value)` being unique. If this constraint is violated, the SQL will fail and team deletion will be blocked.
7. **Team deletion with active leads:** Standard Odoo `unlink` will raise a foreign key error if `crm.lead` records reference the team (no `ondelete` cascade is set on `team_id`).
8. **Lead-to-team reassignment via `_handle_sales_team_assignment`:** Triggered when `partner_id` changes on a lead. It reassigns the team to match the partner's `sale_team_id`, but does NOT reassign the `user_id`.
9. **Alias domain not set:** If `alias_domain_id` is not configured, emails sent to the alias will fail to deliver.
10. **Round-robin bias with multiple rounds:** The method does not persist the rotation state between cron runs. Each cron invocation starts fresh, re-sorting members by `lead_month_count`. This could cause uneven distribution if multiple cron runs occur in the same day.

---

## Security

- Team access is typically controlled via `crm.group_sales_manager` / `crm.group_sales_member` groups.
- The cron assignment runs as superuser to bypass record rules.
- Members can only see leads assigned to them (record rules).
