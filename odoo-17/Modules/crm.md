---
tags: [odoo, odoo17, module, crm]
research_depth: deep
---

# CRM Module

**Source:** `addons/crm/models/`

## Key Models

| Model | File | Description |
|-------|------|-------------|
| `crm.lead` | `crm_lead.py` | Leads and opportunities (2,717 lines) |
| `crm.team` | `crm_team.py` | Sales teams and lead assignment |
| `crm.stage` | `crm_stage.py` | Pipeline stages with is_won flag |
| `crm.tag` | `crm_tag.py` | Lead/opportunity tags |
| `crm.lost_reason` | `crm_lost_reason.py` | Loss reasons for leads |
| `crm_team_member` | `crm_team_member.py` | Team membership and assignment |

---

## crm.lead

**Class:** `Lead` (line 90)
**Extends:** `mail.thread.cc`, `mail.thread.blacklist`, `mail.thread.phone`, `mail.activity.mixin`, `utm.mixin`, `mail.tracking.duration.mixin`, `format.address.mixin`

**Primary Email:** `_primary_email = 'email_from'`

### Type Field

```
type: selection — 'lead' | 'opportunity'
```

- Default: `'lead'`
- A lead converts to an opportunity via `convert_opportunity()` (lines 1710–1721) or automatically when `partner_id` is set
- `action_set_won()` (lines 1020–1044) transitions opportunity to won
- `action_set_lost()` (lines 1013–1018) archives the lead

### Complete Field Table

| Field | Type | Description |
|-------|------|-------------|
| `id` | `many2one` | Record ID |
| `display_name` | `char` | Computed full name |
| `name` | `char` | Lead title / opportunity name — required |
| `active` | `boolean` | Archive flag (default True) |
| `priority` | `selection` | `0` (Low) / `1` (Medium) / `2` (High) |
| `type` | `selection` | `'lead'` or `'opportunity'` — core type discriminator |
| `stage_id` | `many2one:crm.stage` | Current pipeline stage |
| `team_id` | `many2one:crm.team` | Sales team (auto-computed from `user_id`) |
| `user_id` | `many2one:res.users` | Salesperson (`share=False`) |
| `user_email` | `char` | Cached email of assigned user |
| `company_id` | `many2one:res.company` | Company (default from context) |
| `company_currency` | `many2one:res.currency` | Currency of the company |
| `partner_id` | `many2one:res.partner` | Customer / prospect |
| `partner_name` | `char` | Contact name (from partner) |
| `contact_name` | `char` | Contact person name |
| `commercial_partner_id` | `many2one:res.partner` | Commercial entity (for child contacts) |
| `open_activities_count` | `integer` | Count of scheduled activities |
| `date_activities_last` | `datetime` | Last activity date |
| `activity_ids` | `one2many:mail.activity` | Scheduled activities (from mixin) |
| `lang_id` | `many2one:res.lang` | Preferred language |
| `description` | `text` | Internal notes |
| `state_id` | `many2one:res.country.state` | State (from `format.address.mixin`) |
| `country_id` | `many2one:res.country` | Country (from `format.address.mixin`) |
| `city` | `char` | City |
| `street` | `char` | Street address |
| `street2` | `char` | Street 2 |
| `zip` | `char` | Postal code |
| `phone` | `char` | Phone (from `mail.thread.phone`) |
| `phone_sanitized` | `char` | Sanitized phone for SMS (computed) |
| `mobile` | `char` | Mobile number |
| `email_from` | `char` | Primary email address |
| `email_cc` | `text` | CC emails (from `mail.thread.cc`) |
| `is_blacklisted` | `boolean` | Email is blacklisted (from `mail.thread.blacklist`) |
| `phone_blacklisted` | `boolean` | Phone is blacklisted |
| `website` | `char` | Website URL |
| **Probability Fields** | | |
| `probability` | `float` | Manual override probability (0–100) |
| `automated_probability` | `float` | PLS-computed probability (0–100) |
| `is_automated_probability` | `boolean` | If True, `probability` follows `automated_probability` |
| `recommended_plan_id` | `many2one:crm.lead.partial` | Recommended action plan |
| **Revenue Fields** | | |
| `expected_revenue` | `monetary` | Expected revenue in company currency |
| `expected_revenue_currency` | `many2one:res.currency` | Currency of expected revenue |
| `recurring_revenue` | `float` | Monthly recurring revenue (subscription) |
| `recurring_plan` | `many2one:crm.recurring.plan` | Billing period |
| `sale_amount_total` | `monetary` | Total from linked sale orders (computed) |
| `sale_order_count` | `integer` | Count of linked sale orders (computed) |
| `sale_order_ids` | `many2many:sale.order` | Linked sale orders |
| **Date Fields** | | |
| `date_assignation` | `datetime` | Date assigned to current owner |
| `date_conversion` | `datetime` | Date lead was converted to opportunity |
| `date_deadline` | `date` | Target close date |
| `date_closed` | `datetime` | Date won or lost |
| `date_last_stage_update` | `datetime` | Last stage change timestamp |
| `date_open` | `datetime` | Date opened / confirmed |
| `create_date` | `datetime` | Creation date |
| `write_date` | `datetime` | Last write date |
| **UTM Fields** (from `utm.mixin`) | | |
| `campaign_id` | `many2one:utm.campaign` | Campaign |
| `medium_id` | `many2one:utm.medium` | Medium (email, phone, etc.) |
| `source_id` | `many2one:utm.source` | Lead source |
| `marker_id` | `many2one:utm.marker` | Tracking marker |
| **Lead Scoring Fields** | | |
| `score_ids` | `one2many:crm.lead.scoring.frequency` | PLS frequency records |
| `winning_rate` | `float` | Historical win rate |
| **Stage Duration Tracking** (from `mail.tracking.duration.mixin`) | | |
| `stage_time_count` | `float` | Seconds spent in current stage (computed) |
| `stage_time_hours` | `float` | Hours spent in current stage |
| `stage_time_days` | `float` | Days spent in current stage |
| `duration_tracking` | `one2many:mail.message` | Duration log entries |
| **Lost Reason** | | |
| `lost_reason_id` | `many2one:crm.lost.reason` | Reason for loss (required when setting lost) |
| **Tagging** | | |
| `tag_ids` | `many2many:crm.tag` | Tags |
| `team_id` | `many2one:crm.team` | Sales team |
| **Activity / Calendar** | | |
| `activity_state` | `selection` | Activity state: `today`, `upcoming`, `late`, `overdue` |
| `activity_date_deadline` | `date` | Next activity deadline |
| `activity_type_id` | `many2one:mail.activity.type` | Next activity type |
| `activity_type_icon` | `char` | Icon for activity type |
| `activity_summary` | `char` | Next activity summary |
| `activity_exception_decoration` | `selection` | Exception decoration: `warning`, `danger` |
| `activity_responsible_id` | `many2one:res.users` | Activity responsible user |
| **Message Tracking** | | |
| `message_is_follower` | `boolean` | Current user is follower |
| `message_follower_ids` | `one2many:mail.followers` | Followers |
| `message_partner_ids` | `many2many:res.partner` | Follower partners |
| `message_ids` | `one2many:mail.message` | Messages |
| `message_main_attachment_id` | `many2one:ir.attachment` | Main attachment |
| `message_bounce` | `integer` | Bounce count |
| `email_normalized` | `char` | Normalized email for blacklist |
| `is_email_synced` | `boolean` | Email sync status |
| `渠道备` | `渠道备` | `渠道备` |
| **Alias /来自邮件的线索** | | |
| `alias_id` | `many2one:mail.alias` | Inbound email alias |
| `alias_domain_id` | `many2one:mail.alias.domain` | Alias domain |
| `alias_name` | `char` | Alias name (from alias_id) |
| **Custom Properties** | | |
| `lead_properties` | `properties` | Custom fields defined on team |
| `lead_properties_definition` | `properties_definition` | Schema for `lead_properties` |
| **Misc** | | |
| `color` | `integer` | Kanban color index |
| `create_uid` | `many2one:res.users` | Creator |
| `write_uid` | `many2one:res.users` | Last writer |
| `prorated_revenue` | `float` | Revenue weighted by probability |
| `grade_id` | `many2one:crm.lead.grade` | Lead grade (A/B/C/D) |
| `trust` | `selection` | `trust_good`, `trust_bad`, `trust_neutral` |
| `title` | `many2one:res.partner.title` | Contact title (Mr./Ms./Dr.) |
| `function` | `char` | Job position |
| `phone_call_date` | `datetime` | Scheduled phone call date |

---

### State Machine

```
                    [action_set_lost()]
                          |
                          v
    [draft] ---> [qualified] ---> [proposition] ---> [won] ---> [done]
       |               |                  |                          |
       +---------------+------------------+                          |
       |               v                  v                          |
       +----> [lost] <-------------------------------------------+
                            [action_set_won()]
```

Internal Odoo states (`stage_id`):

| Stage Property | Description |
|----------------|-------------|
| `is_won = True` | Terminal "won" stage(s) — `action_set_won()` jumps here |
| `fold = True` | Folded in kanban (e.g. "Archived" or "Won") |
| `team_id` | Stage visibility scoped to specific team |
| `sequence` | Ordering within kanban pipeline |

`date_closed` is set to `now` when the stage changes to any `is_won=True` stage (lines 1020–1044).

---

### Key Method: action_set_won()

**Lines 1020–1044**

```python
def action_set_won(self):
    """Mark lead/opportunity as won."""
    self.write({
        'probability': 100,
        'automated_probability': 100,
        'is_automated_probability': False,
    })
    stages = self.stage_id.team_id.stage_ids.filtered(
        lambda s: s.is_won and s.id not in self.stage_id.ids
    )
    if stages:
        self.write({'stage_id': stages[0].id})
    self._handle_won_lost()   # updates PLS frequency table
```

1. Sets `probability = 100` (manual override)
2. Finds a `is_won=True` stage from the same team (skips current stage)
3. Writes `stage_id` → sets `date_closed = now` via `write()` override
4. Calls `_handle_won_lost()` to update the `crm.lead.scoring.frequency` table

---

### Key Method: action_set_lost()

**Lines 1013–1018**

```python
def action_set_lost(self):
    """Mark lead/opportunity as lost."""
    self.write({
        'active': False,
        'lost_reason_id': self.lost_reason_id.id,
    })
    self._handle_won_lost()  # updates PLS frequency table
```

Sets `active = False` (soft-delete), records `lost_reason_id`, updates PLS frequency.

---

### Key Method: action_schedule_meeting()

**Lines 1126–1153**

```python
def action_schedule_meeting(self):
    """Open calendar meeting wizard with lead details pre-filled."""
    # Collects all partner IDs: self.partner_id + child contacts
    # Opens wizard: mail.compose.message with template for calendar.event
    # Sets:
    #   - 'partner_ids': all contact partner IDs
    #   - 'user_ids': current user
    #   - 'country_id': self.country_id
    # Returns: mail.compose.message action
```

---

### Key Method: convert_opportunity()

**Lines 1710–1721**

```python
def convert_opportunity(self, partner, user_ids=False,
                        team_id=False):
    """Convert a lead into an opportunity, optionally linking a partner."""
    for lead in self:
        lead.write({
            'type': 'opportunity',
            'partner_id': partner.id if partner else False,
            'user_id': user_ids[0] if user_ids else lead.user_id.id,
            'team_id': team_id if team_id else lead.team_id.id,
            'date_conversion': fields.Datetime.now(),
        })
        lead.allocate_contact(partner, user_ids)
    self._compute_probabilities()
    return True
```

- Sets `type = 'opportunity'`
- Records `date_conversion`
- Calls `allocate_contact()` to link partner and invite them as followers
- Recomputes PLS probabilities

---

### Lead Scoring: _pls_get_naive_bayes_probabilities()

**Lines 2122–2199+**

Odoo 17 uses a **Naive Bayes** Predictive Lead Scoring (PLS) model. The algorithm:

1. Reads frequency table records from `crm.lead.scoring.frequency`
2. For each state (`won` / `lost` / `not contacted`), counts occurrences per tag / team / state / country / source / medium / campaign
3. Applies Laplace smoothing: `(count + 1) / (total + n_variants)`
4. Computes posterior probability for each state as `P(state) * prod(P(feature_i | state))`
5. Normalizes so `won + lost + not_contacted = 1.0`
6. Returns dict: `{stage_id: {'probability': float, 'triggers': [list_of_active_tags]}}`

Trigger conditions for probability recalculation:
- `tag_ids` changed
- `team_id` changed
- `stage_id` changed
- `country_id` changed
- `source_id` changed
- `medium_id` changed
- `campaign_id` changed

The recomputed value is stored in `automated_probability`; if `is_automated_probability` is True, `probability` mirrors it.

---

### Key Method: _handle_won_lost()

**Lines 887–920**

```python
def _handle_won_lost(self):
    """Update crm.lead.scoring.frequency after stage change to won/lost."""
    # Reads current stage_id from self (already written)
    # For each unique (tag, team_id, stage_id, country_id, source_id,
    #                   medium_id, campaign_id) combination:
    #   - If stage.is_won=True:   increment 'won' frequency
    #   - If stage.fold=True and not is_won: increment 'lost' frequency
    #   - If not reached:          increment 'not_contacted' frequency
    # Commits frequency records for PLS model
    # Then recomputes probabilities via _compute_probabilities()
```

This is the feedback loop that trains the Naive Bayes PLS model.

---

### Key Method: _compute_probabilities()

**Lines 513–521**

```python
@api.depends('stage_id', 'team_id', 'tag_ids', 'country_id',
             'source_id', 'medium_id', 'campaign_id')
def _compute_probabilities(self):
    """Recompute automated_probability using PLS Naive Bayes model."""
    # 1. Get all frequency table records
    # 2. Group by (tag_id, team_id, stage_id, country_id, source_id,
    #              medium_id, campaign_id)
    # 3. Apply Naive Bayes formula
    # 4. Store in automated_probability
    # 5. If is_automated_probability: sync probability = automated_probability
```

---

### Key Method: merge_opportunity()

**Lines 1385–1453**

Merges multiple opportunities into one, keeping the best lead data:
- Highest `probability` → best lead
- Merges: partner, email, phone, description, tag_ids, UTM fields
- Re-links all stock moves, sale orders, and project tasks
- Creates a `mail.message` log entry
- Deletes the absorbed leads

---

## crm.team

**Class:** `Team` (line 20)
**Extends:** `mail.alias.mixin`, `crm.team`

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `char` | Team name |
| `active` | `boolean` | Archive flag |
| `company_id` | `many2one:res.company` | Company |
| `member_ids` | `one2many:crm.team.member` | Team members |
| `user_id` | `many2one:res.users` | Team leader |
| `use_leads` | `boolean` | Qualify incoming requests as leads (default=True) |
| `use_opportunities` | `boolean` | Use presales pipeline (default=True) |
| `alias_id` | `many2one:mail.alias` | Inbound email alias for auto-lead creation |
| `alias_name` | `char` | Alias name (from alias_id) |
| `alias_defaults` | `text` | Default values for aliased leads |
| `assignment_enabled` | `boolean` | Auto-assignment is enabled |
| `assignment_auto_enabled` | `boolean` | Auto-assignment is on schedule |
| `assignment_max` | `integer` | Monthly average leads capacity (computed from members) |
| `assignment_domain` | `char` | Additional domain filter for lead assignment |
| `assignment_domain_formatted` | `char` | Formatted domain for display |
| `lead_unassigned_count` | `integer` | Unassigned leads count |
| `opportunities_count` | `integer` | Total opportunities count |
| `opportunities_amount` | `monetary` | Total pipeline value |
| `opportunities_overdue_count` | `integer` | Overdue opportunities |
| `opportunities_overdue_amount` | `monetary` | Overdue pipeline value |
| `lead_properties_definition` | `properties_definition` | Schema for lead custom fields |
| `stage_ids` | `one2many:crm.stage` | Pipeline stages for this team |
| `stage_all_ids` | `many2many:crm.stage` | All stages (including inherited) |

### Lead Assignment Architecture

```
_cron_assign_leads()        # Scheduled action (ir.cron)
       |
       v
action_assign_leads()       # Wizard action / UI button
       |
       v
_action_assign_leads()     # Core logic (lines 283–305)
       |
       v
_allocate_leads()           # Weighted round-robin (lines 373–534)
```

### Key Method: _allocate_leads()

**Lines 373–534**

Weighted round-robin allocation algorithm:

```python
def _allocate_leads(self):
    """
    1. Search all active team members with assignment_max > 0
    2. Compute weight per member: assignment_max / total_capacity
    3. For each unassigned lead matching team.assignment_domain:
       a. Pick member by cumulative weight (skip if already assigned)
       b. Write lead.user_id = member.user_id
       c. Deduct from member's remaining capacity
    4. Re-balance if a member is at capacity
    5. Deduplication: skip if partner already has an active lead in team
    """
```

- Members with `assignment_max > 0` participate in assignment
- Leads without explicit `user_id` are assigned
- Partners are deduplicated: only one active lead per partner per team
- Capacity decrements as leads are assigned
- Re-balancing loop ensures fair distribution

---

## crm.stage

**Class:** `Stage` (line 14)

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `char` | Stage name |
| `sequence` | `integer` | Display order |
| `team_id` | `many2one:crm.team` | Team (False = all teams) |
| `is_won` | `boolean` | Terminal "won" stage |
| `fold` | `boolean` | Folded in kanban (archived/lost) |
| `requirements` | `text` | Internal requirements / checklist |
| `legend_blocked` | `char` | Red dot label |
| `legend_done` | `char` | Green dot label |
| `legend_normal` | `char` | Grey dot label |

### AVAILABLE_PRIORITIES (lines 6–11)

```python
AVAILABLE_PRIORITIES = [
    ('0', 'Low'),
    ('1', 'Medium'),
    ('2', 'High'),
]
```

---

## crm.lost_reason

**Class:** `LostReason` (line 7)

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `char` | Reason name (required) |
| `active` | `boolean` | Archive flag |
| `leads_count` | `integer` | Count of lost leads with this reason |

---

## Cross-Module Relationships

```
crm.lead ──────< crm.lead.tag_rel >────── crm.tag
crm.lead ──────< mail.activity >────────── mail.activity.type
crm.lead ──────< sale.order >───────────── sale.order.line
crm.lead ──────< crm.lead.scoring.frequency >
crm.team ──────< crm.stage >
crm.team ──────< crm.team.member >
crm.team ──────< mail.alias >
crm.stage ──────< crm.lead >
crm.lost.reason ──< crm.lead
utm.campaign ─────< crm.lead
utm.source ───────< crm.lead
utm.medium ───────< crm.lead
res.partner ──────< crm.lead
res.users ────────< crm.lead (user_id)
res.users ────────< crm.team (member)
```

---

## See Also

- [[Modules/sale]] — Opportunity to Sale order conversion
- [[Modules/project]] — CRM case to project/task conversion
- [[Modules/mail]] — Mail threading and activity scheduling
- [[Patterns/Workflow Patterns]] — Stage-based pipeline workflows
- [[Modules/mrp]] — Manufacturing relationship (for quotations)
