# CRM Team Member - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/crm/models/crm_team_member.py`
**Lines:** ~86

---

## Model Overview

`crm.team.member` (`crm.team.member`) represents the membership of a user in a sales team. It extends the base membership with lead assignment-specific fields that control how leads are distributed to the member.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `user_id` | Many2one | `res.users`; the team member |
| `crm_team_id` | Many2one | `crm.team`; the team this member belongs to |
| `assignment_enabled` | Boolean | Enable automatic lead assignment for this member |
| `assignment_domain` | Char/JSON | Domain filter; only assign leads matching this domain |
| `assignment_optout` | Boolean | Skip this member in automatic assignment |
| `assignment_max` | Integer | Maximum leads assignable per month to this member |
| `lead_day_count` | Integer | Stored; leads assigned to this member today |
| `lead_month_count` | Integer | Stored; leads assigned to this member this month |

---

## Key Methods

### `_get_lead_from_date()`
**Purpose:** Returns the date from which to count assigned leads.
**Logic:** Returns first day of current month. Used as the base for counting `lead_day_count` and `lead_month_count` resets.

### `_get_assignment_quota()`
**Purpose:** Returns the maximum leads this member can receive.
**Logic:**
1. Start with `self.assignment_max`.
2. Subtract `lead_month_count` (already assigned this month).
3. If multiple member records exist for the same user across different teams, sum all quotas.
4. Returns 0 if opt-out or quota exhausted.

**Edge case:** If `assignment_max` is 0 or negative, no leads are assigned.

### `_constrains_assignment_domain()`
**Constraint on:** `assignment_domain`
**Validation:** Uses `ast.literal_eval` to parse the domain string. Raises `ValidationError` if not a valid domain list.
**Applied as:** `@api.constrains('assignment_domain')`

---

## Edge Cases

1. **Domain parsing with `ast.literal_eval`:** If the domain contains field names not yet existing in the model, no error is raised at assignment time; only domain evaluation fails silently.
2. **Multiple team memberships:** A user in multiple teams has separate member records per team. Assignment quota is tracked per member record, not globally per user.
3. **Quota reset:** No automatic reset mechanism is visible in the model. The `lead_day_count` and `lead_month_count` fields are updated directly by the assignment logic. If these counts become stale (e.g., due to manual edits), assignment may incorrectly skip members.
4. **`assignment_optout`:** When True, the member is excluded from assignment rotation even if `assignment_enabled=True`.
