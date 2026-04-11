# CRM Stage - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/crm/models/crm_stage.py`
**Lines:** ~51

---

## Model Overview

`crm.stage` (`crm.stage`) is the pipeline stage model. Stages are ordered by sequence and are specific to a team (or shared if `team_id` is False). Each stage can be marked as a winning stage.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required; stage name |
| `sequence` | Integer | Sort order |
| `is_won` | Boolean | Marking leads in this stage as won; sets `date_closed` |
| `requirements` | Text | Optional checklist/requirements shown to salespersons |
| `team_id` | Many2one | `crm.team`; team-specific. False means shared across teams |
| `fold` | Boolean | Folded in Kanban (collapsed stage) |

---

## Key Methods

### `default_get(fields)`
**Special behavior:** Pops `default_team_id` from context before calling `super()`.
**Purpose:** Prevents the default team context from being incorrectly propagated as a field default.

---

## Edge Cases

1. **Shared stages (`team_id=False`):** Available to all teams that don't have their own stage configuration.
2. **Multiple `is_won=True` stages:** Functionally possible but confusing; a lead can only be in one stage at a time.
3. **Team deletion with stages:** If stages are team-specific and the team is deleted, the stages are unlinked (no `ondelete` specification means default restrict behavior — may fail if leads reference the stage).
4. **Stage sequence gaps:** Allowed; stages are ordered by integer sequence value.

---

## Cross-Model Relationships

- **With `crm.lead`:** Stage has many leads via `stage_id`.
- **With `crm.team`:** Team has many stages via `stage_ids`.

---

## Failure Modes

1. **Deleting a stage with leads:** Default Odoo `unlink` will raise a `ForeignKey` constraint error if any `crm.lead` records reference the stage.
2. **Changing `is_won` on a stage with existing leads:** Existing leads in that stage will NOT have their `date_closed` retroactively updated. Only new stage transitions will set `date_closed`.
