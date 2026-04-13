# CRM — Customer Relationship Management

Dokumentasi Odoo 15 untuk CRM module. Source: `addons/crm/models/`

## Models

| Model | File | Description |
|---|---|---|
| `crm.lead` | `crm_lead.py` | Lead / Opportunity |
| `crm.tag` | `crm_tag.py` | Lead Tags |
| `crm.team` | `crm_team.py` | Sales Team |
| `crm.stage` | `crm_stage.py` | Pipeline Stage |
| `crm.lost.reason` | `crm_lost_reason.py` | Lost Reason |
| `crm.lead.scoring.frequency` | `crm_lead_scoring_frequency.py` | Lead Scoring |
| `crm.recurring.plan` | `crm_recurring_plan.py` | Recurring Plans |
| `crm.lead.to.me` | `crm_lead_tome.py` | My Lead Filter |

## CrmLead Fields

```python
class CrmLead(models.Model):
    _name = "crm.lead"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'website.published.mixin',
                'utm.mixin', 'rating.mixin']
```

### Identification Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Lead Subject |
| `partner_id` | Many2one(res.partner) | Customer |
| `partner_name` | Char | Company Name |
| `contact_name` | Char | Contact Name |
| `email_from` | Char | Email |
| `phone` | Char | Phone |
| `mobile` | Char | Mobile |

### Classification Fields

| Field | Type | Description |
|---|---|---|
| `type` | Selection | lead/opportunity |
| `tag_ids` | Many2many(crm.tag) | Tags |
| `team_id` | Many2one(crm.team) | Sales Team |
| `user_id` | Many2one(res.users) | Salesperson |
| `stage_id` | Many2one(crm.stage) | Pipeline Stage |

### Commercial Fields

| Field | Type | Description |
|---|---|---|
| `probability` | Float | Probability (%) |
| `planned_revenue` | Monetary | Expected Revenue |
| `date_closed` | Datetime | Won/Lost Date |
| `expected_close_date` | Date | Expected Closing |

### Address Fields

| Field | Type | Description |
|---|---|---|
| `street` | Char | Street |
| `street2` | Char | Street 2 |
| `city` | Char | City |
| `zip` | Char | ZIP |
| `state_id` | Many2one(res.country.state) | State |
| `country_id` | Many2one(res.country) | Country |

### Lead Quality Fields

| Field | Type | Description |
|---|---|---|
| `priority` | Selection | 0/Low, 1/Medium, 2/High |
| `lost_reason_id` | Many2one(crm.lost.reason) | Lost Reason |
| `active` | Boolean | Active |
| `company_id` | Many2one(res.company) | Company |

### Lead Scoring (IAP)

| Field | Type | Description |
|---|---|---|
| `is_sms_checked` | Boolean | SMS Validated |
| `mail_domain` | Char | Email Domain |
| `campaign_id` | Many2one(crm.tracking.campaign) | Campaign |

### Additional Fields

| Field | Type | Description |
|---|---|---|
| `description` | Text | Internal notes |
| `sale_amount_total` | Monetary | Total from Sales (compute) |
| `lang_id` | Many2one(res.lang) | Language |
| `description` | Html | Notes |

## Lead Types

| Type | Description | Lifecycle |
|---|---|---|
| `lead` | Marketing lead | New → Qualified → Lost |
| `opportunity` | Sales opportunity | New → Won/Lost |

## CrmTeam Fields

```python
class CrmTeam(models.Model):
    _name = "crm.team"
    _description = "Sales Team"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Team name |
| `user_id` | Many2one(res.users) | Team Leader |
| `member_ids` | Many2many(res.users) | Team Members |
| `company_id` | Many2one(res.company) | Company |
| `use_leads` | Boolean | Qualify leads |
| `use_opportunities` | Boolean | Use opportunities |
| `alias_id` | Many2one(mail.alias) | Email alias |

### Default Team Method

```python
@api.model
def _get_default_team_id(self, user_id=None):
    """Get default team for user"""
    if not user_id:
        user_id = self.env.uid
    team = self.search([
        ('member_ids', 'in', [user_id]),
        ('company_id', '=', self.env.company.id),
    ], limit=1)
    return team
```

## CrmStage Fields

```python
class CrmStage(models.Model):
    _name = "crm.stage"
    _description = "Stage"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Stage name |
| `sequence` | Integer | Order |
| `team_id` | Many2one(crm.team) | Team (or global) |
| `is_won` | Boolean | Won stage |
| `is_unwanted` | Boolean | Lost stage |
| `legend_priority` | Char | Priority display |
| `requirements` | Html | Requirements |

## Action Methods

```python
# Convert lead to opportunity
def convert_opportunity(self):
    """Convert lead → opportunity"""
    for lead in self:
        lead.write({
            'type': 'opportunity',
            'partner_id': lead.partner_id.id,
        })
    return True

# Mark as won
def action_set_won(self):
    """Mark opportunity as won"""
    self.write({'stage_id': won_stage_id, 'date_closed': fields.Datetime.now()})

# Mark as lost
def action_set_lost(self):
    """Mark opportunity as lost"""
    self.write({'active': False, 'lost_reason_id': reason_id})

# Schedule activity
def action_schedule_meeting(self):
    """Schedule meeting"""
    return {
        'name': _('Schedule Meeting'),
        'type': 'ir.actions.act_window',
        'res_model': 'calendar.event',
        'view_mode': 'form',
        'target': 'new',
        'context': {'default_res_id': self.id, 'default_res_model': 'crm.lead'},
    }
```

## Lead Scoring Frequency

```python
class CrmLeadScoringFrequency(models.Model):
    _name = "crm.lead.scoring.frequency"
    _description = "Lead Scoring Frequency"
```

Used for predictive lead scoring based on historical data.

## See Also
- [Modules/Sale](Modules/sale.md) — Convert to Sale Order
- [Modules/Project](Modules/project.md) — Create Project
- [Modules/Account](Modules/account.md) — Create Invoice
- [Modules/Product](Modules/product.md) — Products/Services