# CRM Lead / Opportunity - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/crm/models/crm_lead.py`
**Lines:** ~2696
**Inherits:** `mail.thread.cc`, `mail.thread.blacklist`, `mail.thread.phone`, `mail.activity.mixin`, `utm.mixin`, `format.address.mixin`

---

## Model Overview

`crm.lead` is the central model for CRM leads and opportunities. It is a massive, multi-role model that handles the entire lead-to-opportunity lifecycle including contact management, UTM tracking, lead scoring, probability computation, duplicate detection, merge operations, stage management, and partner synchronization.

---

## Fields

### Identity & Classification
| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required; used as display name |
| `type` | Selection | `'lead'` or `'opportunity'`; drives UI behavior |
| `active` | Boolean | Soft-delete; archived leads are hidden but not deleted |
| `company_id` | Many2one | `res.company`; multi-company support |
| `lang_id` | Many2one | `res.lang`; stored, used for partner lang sync |

### Contact Fields
| Field | Type | Notes |
|---|---|---|
| `partner_id` | Many2one | `res.partner`; cascades active/test |
| `contact_name` | Char | Deprecated in favor of partner_id.name |
| `partner_name` | Char | Company name (for leads without partner) |
| `email_from` | Char | Used with email_normalize for dedup |
| `email_normalized` | Char | Stored; computed from email_from via `mail.thread.blacklist` |
| `phone` | Char | Free-form; used with phone sanitization |
| `phone_sanitized` | Char | Stored; normalized phone number |
| `phone_state` | Selection | `'correct'`, `'incorrect'`, `'false'` |
| `email_state` | Selection | `'correct'`, `'incorrect'`, `'false'` |
| `street`, `street2`, `city`, `state_id`, `zip`, `country_id` | Address | Inherited from `format.address.mixin` |
| `website` | Char | Parsed via `werkzeug.utils.url_fix` |

### Pipeline Fields
| Field | Type | Notes |
|---|---|---|
| `stage_id` | Many2one | `crm.stage`; ordered by sequence; Kanban-driven |
| `team_id` | Many2one | `crm.team`; drives assignment and notifications |
| `user_id` | Many2one | `res.users`; owner/salesperson |
| `priority` | Selection | `'0'` (low) to `'2'` (high) |
| `lost_reason_id` | Many2one | `crm.lost.reason`; set when lead is lost |
| `date_closed` | Datetime | Set when stage `is_won=True` or explicitly closed |

### Revenue & Probability
| Field | Type | Notes |
|---|---|---|
| `expected_revenue` | Monetary | Company currency; the raw expected revenue |
| `prorated_revenue` | Float | Computed: expected_revenue × probability/100 |
| `probability` | Float | Manual override or auto-computed via PLS |
| `automated_probability` | Float | Computed via Naive Bayes PLS model |
| `is_automated_probability` | Boolean | If True, probability is driven by PLS; user override sets to False |

### UTM Fields (from utm.mixin)
| Field | Type | Notes |
|---|---|---|
| `campaign_id` | Many2one | `utm.campaign` |
| `medium_id` | Many2one | `utm.medium` |
| `source_id` | Many2one | `utm.source` |

### Tagging & Classification
| Field | Type | Notes |
|---|---|---|
| `tag_ids` | Many2many | `crm.tag` |
| `category_id` | Many2one | Deprecated; from `crm.category` |

### Duplicate Tracking
| Field | Type | Notes |
|---|---|---|
| `duplicate_lead_ids` | One2many | Virtual; populated via `_compute_potential_lead_duplicates` |
| `lang_code` | Char | Derived from lang_id.code |

### Partner Synchronization
`PARTNER_FIELDS_TO_SYNC`: List of fields synced to/from `partner_id` on write.
`PARTNER_ADDRESS_FIELDS_TO_SYNC`: Address-specific fields.

### Merge Fields
`CRM_LEAD_FIELDS_TO_MERGE`: Fields merged when opportunities are merged.

---

## Computed Fields

### `_compute_potential_lead_duplicates`
**Trigger:** `partner_id`, `email_normalized`, `phone_sanitized`
**Logic:**
1. If `partner_id` is set: search all leads/opportunities for the same partner.
2. If no partner but email_normalized exists: search leads with matching email_normalized.
3. If no partner/email but phone_sanitized exists: search leads with matching phone_sanitized.
4. Excludes the current record itself.
5. Falls back to loose `email_from ilike` search if normalized search returns nothing.

**Failure modes:**
- If partner has no email, falls back to email search.
- If both partner and email are absent, falls back to phone search.
- Returns empty recordset if no matches.

### `_compute_probabilities`
**Trigger:** `stage_id`, `team_id`, `tag_ids`, `lead_properties` (via PLS model)
**Logic:**
- Uses team-specific PLS scoring frequency table (`crm.lead.scoring.frequency`).
- Naive Bayes: P(won|X) = product of frequency-based scores per field value.
- Falls back to `team_id.probability_depends_on` fields if defined.
- Returns 0.0 if no scoring data available.
- Handles team-less leads by searching no-team scoring frequencies.

**Stored:** Yes. Recomputed on stage/tag/team change via `_on_lead_stage_updated` and `_on_lead_tag_updated`.

### `_compute_prorated_revenue`
**Trigger:** `expected_revenue`, `probability`
**Logic:** `prorated_revenue = expected_revenue * probability / 100.0`
Simple proportional revenue based on win probability.

### `_compute_day_open`, `_compute_day_close`
**Trigger:** `create_date`, `date_closed`, `active`
**Logic:** Number of days since creation (open) or until closure (close).

### `_compute_date_deadline`
**Trigger:** `activity_ids`
**Logic:** Latest `date_deadline` of all activities on the lead.

---

## Constants

```python
CLOSED_STATES = {'won', 'lost'}
CRM_LEAD_FIELDS_TO_MERGE = [
    'partner_id', 'country_id', 'lang_id', 'mobile', 'phone',
    'email_from', 'email_cc', 'website', 'street', 'street2',
    'city', 'state_id', 'zip', 'description', 'tag_ids',
    'contact_name', 'partner_name', 'phone_sanitized',
    'function', 'title', 'company_name', 'company_id',
]
PARTNER_FIELDS_TO_SYNC = [
    'phone', 'mobile', 'email', 'website', 'street',
    'street2', 'city', 'state_id', 'country_id', 'lang_id',
]
PARTNER_ADDRESS_FIELDS_TO_SYNC = [
    'street', 'street2', 'city', 'state_id', 'zip', 'country_id',
]
```

---

## Key Methods

### `write(vals)`
**Handles:**
- Stage change: triggers `_on_lead_stage_updated()` for PLS recalculation.
- `stage_id.is_won=True`: sets `date_closed` to now if not already set; cascades to sub-leads.
- `active=False`: sets `lost_reason_id` if not already set.
- `user_id` change: unsubscribes old owner, subscribes new owner, clears `date_last_stage_update`.
- Partner sync: calls `_on_lead_partner_changed()` to sync fields to partner record.
- `tag_ids` change: triggers `_on_lead_tag_updated()` for PLS recalculation.
- Probability override: sets `is_automated_probability=False`.
- `partner_id` change: calls `_handle_sales_team_assignment()` to reassign team.

**Cross-model triggers:**
- Partner write: updates partner's `sale_team_id` to match `team_id`.
- Stage mail template: triggers email notification on stage change.
- Track template: sends email if stage has `mail_template_id`.

### `_on_lead_stage_updated()`
**Triggered by:** `write()` when `stage_id` changes.
**Actions:**
1. Recomputes probability via PLS.
2. Cascades `is_won` to child/sub-leads if stage is won.
3. Calls `_stage_related_recompute()` for stage-specific fields.

### `_handle_won_lost()`
**Triggered by:** `write()` when `stage_id.is_won=True`.
**Actions:**
- Sets `date_closed` if not already set.
- Cascades won state to all sub-leads.

### `_merge_opportunity(record_to_merge)`
**Purpose:** Merges multiple opportunities into one (record_to_merge into self).
**Merge fields:** All fields in `CRM_LEAD_FIELDS_TO_MERGE`.
**Duplicate handling:** Removes duplicate links between merged records.
**Message:** Posts a merge notification message.
**Sub-leads:** Moves sub-leads of `record_to_merge` to `self`.
**Attachments:** Moves attachments from `record_to_merge` to `self`.
**Activity history:** Moves activities (unlink old, create new links).
**Followers:** Subscribes followers of `record_to_merge` to `self`.
**Constraint:** Cannot merge leads of different types.

### `_get_lead_duplicates(partner=None, email=None, include_lost=False)`
**Purpose:** Find potential duplicate leads.
**Search order:**
1. Email-normalized search (most precise).
2. Falls back to loose email_from search.
3. Includes partner-matched leads.
**Filters:** Excludes won stages unless `include_lost=True`.

### `_sort_by_confidence_level(reverse=False)`
**Purpose:** Sort leads by win likelihood.
**Heuristics:**
1. Active (not lost) leads first.
2. Opportunities > Leads.
3. Higher stage sequence first.
4. Higher priority first.
5. More recent `date_last_stage_update` first.

### `action_set_won()`
**Purpose:** Mark opportunity as won.
**Steps:**
1. Write `stage_id` to team's won stage.
2. Write `probability=100`.
3. Write `date_closed=now` if not set.
4. Cascades to sub-opportunities.
5. Returns True.

### `action_set_lost()`
**Purpose:** Mark opportunity as lost.
**Steps:**
1. Write `active=False`.
2. Write `lost_reason_id` from parameter or wizard.
3. Cascades to sub-opportunities.

### `_action_set_automated_probability()`
**Purpose:** Reset probability to PLS-computed value.
**Effect:** Sets `is_automated_probability=True` and recomputes `probability`.

### `action_save_retract()`
**Purpose:** Toggle probability between manual value and automated value.

### `_get_stage_on_change()`
**Returns:** Team-specific stage (or default) for lead type.

### `_get_related_partners()`
**Returns:** Set of partner records related to this lead (via partner_id and message_partner_ids).

### `copy_data(default=None)`
**Special behavior:** Appends " (copy)" to name; clears `lost_reason_id`, `date_closed`, `duplicate_lead_ids`.

---

## Cross-Model Relationships

### With `crm.team`
- `team_id`: Assigned sales team; drives team-specific stage selection and lead routing.
- `user_id` change triggers `_handle_sales_team_assignment()` which can reassign team based on partner's `sale_team_id`.

### With `res.partner`
- `partner_id`: Customer contact; synchronized fields on write.
- Partner sync on lead write (`_on_lead_partner_changed`).
- Duplicate detection uses partner_id as primary signal.

### With `crm.stage`
- `stage_id`: Pipeline stage; drives Kanban view and probability.
- Stage change triggers PLS probability recalculation.

### With `crm.tag`
- `tag_ids`: Classification tags; tag changes trigger PLS recalculation.
- Scoring frequency is tracked per tag per team.

### With `utm.campaign`, `utm.medium`, `utm.source`
- UTM tracking for lead source attribution.
- PLS model uses UTM fields as features.

### With `crm.lead.scoring.frequency`
- Team-specific scoring frequency table.
- Updated via `_pls_update_frequency_table()` on stage transitions.
- Stores won/lost counts per field value for PLS probability computation.

---

## Edge Cases & Failure Modes

1. **Lead without partner or email:** Duplicate detection falls through from email to phone search.
2. **Won stage reassignment:** If a won stage is moved to a lower sequence, existing won opportunities do NOT automatically update their `date_closed`; only new transitions set it.
3. **Sub-lead cascade:** When parent lead is marked won/lost, all sub-leads are cascaded. However, sub-leads of sub-leads are NOT recursively cascaded (only direct children).
4. **Merge and attachments:** Attachments are moved via SQL (`attachment_ids.write({'res_model': ...})`). If the attachment record has ir.rule restrictions, this could silently skip records.
5. **Probability reset on stage change:** `_on_lead_stage_updated()` always recomputes probability even if manual override was set; the flag `is_automated_probability` controls whether the manual value or computed value is shown.
6. **Multi-company:** `company_id` is set from context or current user's company; leads without company are visible across all companies (if no company context).
7. **Blacklist integration:** `mail.thread.blacklist` mixin handles email blacklist checks; `_search_is_blacklisted()` detects bounced emails.
8. **Lead scoring with no frequency data:** Returns 0.0 probability if no scoring frequency records exist for the team.
9. **Merge constraints:** Cannot merge a lead with an opportunity of a different type (raises `UserError`).
10. **Portal access:** Lead is accessible to portal if `partner_id` matches the portal user's partner.

---

## Security

- Record rules likely restrict access by `user_id`, `team_id`, and `company_id`.
- Portal access: partners can see their own leads/opportunities.
- Unlink: checks `unlink` access rights.
- `mail.thread.cc` mixin: handles CC email notifications.

---

## Mail Thread Integration

- Inherits `mail.thread.cc`: supports CC field in notifications.
- Inherits `mail.thread.phone`: phone number formatting and sanitization.
- Inherits `mail.thread.blacklist`: email blacklist checking.
- `_track_template()`: sends email on stage change if stage has `mail_template_id`.
- `_creation_message()`: notification on lead creation.
- `_notify_get_reply_to()`: uses team's alias if available.
- `_message_auto_subscribe_followers()`: subscribes new owner on `user_id` write.
