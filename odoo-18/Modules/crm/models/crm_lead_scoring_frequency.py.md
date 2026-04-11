# CRM Lead Scoring Frequency - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/crm/models/crm_lead_scoring_frequency.py`
**Lines:** ~24

---

## Model Overview

Two models for the Predictive Lead Scoring (PLS) system:

### `crm.lead.scoring.frequency` — Lead Scoring Frequency

Stores won/lost counts per field value per team, used to compute Naive Bayes probabilities for lead scoring.

| Field | Type | Notes |
|---|---|---|
| `variable` | Char | Field name (e.g., `stage_id`, `tag_ids`, `team_id`) |
| `value` | Char | Field value (e.g., stage ID as string) |
| `won_count` | Float | Number of leads won with this variable=value. Stored as Float with +0.1 to avoid zero |
| `lost_count` | Float | Number of leads lost with this variable=value. Stored as Float with +0.1 to avoid zero |
| `team_id` | Many2one | `crm.team`; team-specific scoring. `ondelete='cascade'` |

**Design note:** `won_count` and `lost_count` are stored as Float (not Integer) with a +0.1 offset applied in code to avoid zero-frequency problems in the Naive Bayes computation. This means the stored value is always >= 0.1.

### `crm.lead.scoring.frequency.field` — Scoring Frequency Field Configuration

Configures which `crm.lead` fields are used as features in PLS computation.

| Field | Type | Notes |
|---|---|---|
| `field_id` | Many2one | `ir.model.fields`; restricted to `crm.lead` model |
| `name` | Char | Related description from `field_id.field_description` |

---

## Edge Cases

1. **`+0.1 offset:** The offset is applied in the `_pls_update_frequency_table()` method in `crm_lead.py`. The stored database value includes this offset, so queries directly on the table will see fractional counts.
2. **`team_id` cascade delete:** When a team is deleted, all frequency records for that team are deleted via `ondelete='cascade'`.
3. **"No team" scoring:** Frequency records with `team_id=False` (null) store the default scoring behavior for leads without a team. These records are NOT deleted when any team is deleted.
4. **Variable=value format:** The `variable` stores the field name (e.g., `"stage_id"`) and `value` stores the field value as a string (e.g., `"5"` for the stage with ID 5). This means multiple records can exist for the same field with different values.
5. **Frequency table merge on team delete:** In `crm_team.py`, the `unlink()` method uses raw SQL to merge team frequencies into the "no team" frequency before deletion. This is done as a raw SQL `INSERT ... ON CONFLICT DO UPDATE` to avoid triggering ORM write methods.
