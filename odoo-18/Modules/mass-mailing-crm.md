---
Module: mass_mailing_crm
Version: Odoo 18
Type: Integration
Tags: #mass-mailing #crm #marketing #email #utm
---

# Mass Mailing CRM Integration (`mass_mailing_crm`)

## Overview

**Path:** `~/odoo/odoo18/odoo/addons/mass_mailing_crm/`

The `mass_mailing_crm` module bridges the **Mass Mailing** and **CRM** modules. It:

- Enables `crm.lead` records to be **recipients of email marketing campaigns** (sets `_mailing_enabled = True`)
- Adds **CRM statistics buttons** to the `mailing.mailing` form view (Leads/Opportunities count, linked to the CRM lead analysis)
- Extends `mailing.mailing` with computed **CRM KPI fields** that appear in the mailing dashboard
- Extends `utm.campaign` with a **`crm_lead_count` A/B testing winner criterion**
- Ships a demo mailing: "Lead Recall" targeting `crm.lead` records

**Depends:** `crm`, `mass_mailing`
**Auto-install:** `True`
**Category:** Hidden (auto-install integration)

---

## Architecture

This module defines **three** Python model extensions:

| Model | File | Role |
|-------|------|------|
| `crm.lead` | `models/crm_lead.py` | Enables lead records as mailing recipients |
| `mailing.mailing` | `models/mailing_mailing.py` | Adds CRM KPI buttons + statistics enrichment |
| `utm.campaign` | `models/utm.py` | Adds `crm_lead_count` as A/B testing winner criterion |

---

## Models Extended

### `crm.lead` (Extended)

**File:** `models/crm_lead.py`

```python
class CrmLead(models.Model):
    _inherit = 'crm.lead'
    _mailing_enabled = True
```

This single line does two things:

1. **Marks `crm.lead` as a valid mailing recipient model** — sets `is_mailing_enabled = True` on the corresponding `ir.model` record, which allows `mailing.mailing`'s `mailing_model_id` domain to include `crm.lead`
2. **Enables mailing tracking on leads** — the `_mailing_enabled` class attribute is checked by the mass mailing engine when processing replies and unsubscribes

#### How `_mailing_enabled` Is Used

The `mailing.mailing` model has a `mailing_model_id` Many2one field with domain `is_mailing_enabled = True`. Setting `_mailing_enabled = True` on the `crm.lead` model class causes the ORM to set this flag on the `ir.model` record for `crm.lead` on module load (via `ir.model._register_hook()`).

Once enabled, all `crm.lead` records can be selected as recipients in a mailing's `mailing_domain`, and reply emails from leads can be processed by the mailing trace system.

---

### `mailing.mailing` (Extended)

**File:** `models/mailing_mailing.py`

Extends the base `mailing.mailing` model (defined in `addons/mass_mailing/models/mailing.py`) with CRM-specific computed fields and actions.

#### New Fields Added

| Field | Type | Compute | Description |
|-------|------|---------|-------------|
| `use_leads` | Boolean | `_compute_use_leads` | True if current user is in `crm.group_use_lead` group. Controls "Leads" vs "Opportunities" label in the KPI button |
| `crm_lead_count` | Integer | `_compute_crm_lead_count` | Count of `crm.lead` records whose `source_id` matches this mailing's UTM source |

#### `_compute_use_leads()`

```python
def _compute_use_leads(self):
    self.use_leads = self.env.user.has_group('crm.group_use_lead')
```

Simply checks the current user's group membership. This is a **per-record compute** (not `search()` based), so it re-evaluates based on the current user viewing the form.

#### `_compute_crm_lead_count()`

```python
def _compute_crm_lead_count(self):
    lead_data = self.env['crm.lead'].with_context(active_test=False).sudo()._read_group(
        [('source_id', 'in', self.source_id.ids)],
        ['source_id'], ['__count'],
    )
    mapped_data = {source.id: count for source, count in lead_data}
    for mass_mailing in self:
        mass_mailing.crm_lead_count = mapped_data.get(mass_mailing.source_id.id, 0)
```

Counts all `crm.lead` records (active and inactive) linked to the mailing's `source_id` (UTM source). Uses `_read_group` for efficient SQL aggregation. Note:
- Only counts records where `source_id` is set — if no UTM source is linked, count is 0
- Uses `sudo()` with `active_test=False` to count archived leads too (important for historical analysis)
- Runs on the `source_id.ids` set — all visible mailings in the page compute at once

#### `action_redirect_to_leads_and_opportunities()`

```python
def action_redirect_to_leads_and_opportunities(self):
    # ...
    return {
        'context': {
            'active_test': False,
            'create': False,
            'search_default_group_by_create_date_day': True,
            'crm_lead_view_hide_month': True,
        },
        'domain': [('source_id', 'in', self.source_id.ids)],
        'help': Markup('<p class="o_view_nocontent_smiling_face">...</p>'),
        'name': _("Leads Analysis"),
        'res_model': 'crm.lead',
        'type': 'ir.actions.act_window',
        'view_mode': 'list,pivot,graph,form',
    }
```

Opens the CRM lead list/pivot/graph view filtered to all leads sharing the mailing's UTM source(s). The empty-state helper message warns that replies cannot be tracked if the mailing was sent to external addresses.

#### `_prepare_statistics_email_values()`

Enriches the **KPI dashboard email** (sent to the mailing's responsible user) with a CRM-specific KPI:

```python
values['kpi_data'][1]['kpi_col1'] = {
    'value': tools.misc.format_decimalized_number(self.crm_lead_count, decimal=0),
    'col_subtitle': _('LEADS'),
}
values['kpi_data'][1]['kpi_name'] = 'lead'
```

Adds a "LEADS" column to the mailing's internal statistics email alongside the standard email metrics (sent, opened, replied, etc.).

---

### `utm.campaign` (Extended)

**File:** `models/utm.py`

```python
class UtmCampaign(models.Model):
    _inherit = 'utm.campaign'
    ab_testing_winner_selection = fields.Selection(selection_add=[('crm_lead_count', 'Leads')])
```

Adds `crm_lead_count` as a new A/B testing winner criterion for CRM-linked campaigns. When a campaign has multiple mailing variants (A/B test), Odoo can automatically select the winner based on which variant generated the most CRM leads.

The base `ab_testing_winner_selection` field (from `mass_mailing`) has options like `opened_ratio`, `clicks_ratio`, etc. This module adds `crm_lead_count` to let marketers optimize for lead generation volume.

---

## View Extension (XML)

**File:** `views/mailing_mailing_views.xml`

Inherits the base mass mailing form view (`mass_mailing.view_mail_mass_mailing_form`) and adds a **stat button** before the "View Deliveries" button:

```xml
<button name="action_redirect_to_leads_and_opportunities"
    type="object"
    icon="fa-star"
    class="oe_stat_button"
    invisible="state == 'draft'">
    <div class="o_field_widget o_stat_info">
        <field name="use_leads" invisible="1"/>
        <span class="o_stat_value"><field nolabel="1" name="crm_lead_count"/></span>
        <span class="o_stat_text" invisible="not use_leads">Leads</span>
        <span class="o_stat_text" invisible="use_leads">Opportunities</span>
    </div>
</button>
```

The button:
- Is **hidden when mailing is in `draft` state** — only appears after sending
- Shows **"Leads" or "Opportunities"** based on whether the current user has the leads feature enabled
- Navigates to `crm.lead` list filtered by the mailing's UTM source

---

## Demo Data

**File:** `demo/mailing_mailing.xml`

Creates a demo mailing record for testing:

| Field | Value |
|-------|-------|
| `name` | `Lead Recall` |
| `subject` | `We want to hear from you!` |
| `state` | `draft` |
| `mailing_model_id` | `crm.model_crm_lead` |
| `mailing_domain` | `[]` (all leads) |
| `campaign_id` | `mass_mailing.mass_mail_campaign_1` |
| `source_id` | `utm.utm_source_mailing` |

The HTML body template greets the lead by `{{ object.name }}` and includes company contact info.

---

## How Lead Reply Email Creates CRM Records

When a mailing is sent to `crm.lead` records and a reply is received:

1. The **incoming email server** (POP/IMAP) or **IAP webhook** delivers the reply to Odoo's mail gateway
2. The reply's `In-Reply-To` or `References` headers are matched to the original `mailing.trace` record
3. The `mailing.trace` record is updated: `trace_status` set to `reply`
4. If the reply contains a **new email address not in the database**, the mass mailing module can create a new `crm.lead` from it (configurable via `mailing.mailing.mailing_on_mailing_list` / `create_new_lead_from_reply`)

The `_mailing_enabled = True` flag on `crm.lead` tells the mailing trace system that this model supports the full mailing reply tracking loop.

---

## UTM Tracking Flow

```
mailing.mailing
    ├── campaign_id ──→ utm.campaign (A/B testing, lead counting)
    ├── source_id ───→ utm.source   (per-mailing tracking)
    └── medium_id ───→ utm.medium   (set to "Email")

crm.lead
    ├── campaign_id ← links lead to the campaign
    ├── source_id   ← links lead to the specific mailing/source
    └── medium_id   ← identifies email as the origin channel
```

The `source_id` link is the critical join: counting `crm_lead_count` on `mailing.mailing` and counting mailing traces both use `source_id` as the join key. This allows the system to attribute leads back to the exact mailing that generated them.

---

## L4: Mailing Domain for CRM Leads

When creating a mailing targeting `crm.lead`, the `mailing_domain` field (stored, computed, readonly=False) filters which leads receive the email:

```python
# Example domains for crm.lead mailing
[('type', '=', 'lead')]                      # Leads only
[('stage_id', '=', ref('crm.stage_lead1'))] # Specific stage
[('team_id', '=', ref('crm.salesteam_1'))]  # Specific team
[('country_id', '=', ref('base.be'))]        # Specific country
[('tag_ids', 'in', [ref('crm.crm_tag_1')])] # With specific tag
```

The domain is evaluated server-side with `search_count()` to compute the `mailing.mailing.total` (expected recipients).

---

## Related Documentation

- [Modules/Mass Mailing](mass-mailing.md) — base mass mailing module (`mailing.mailing`, `mailing.trace`)
- [Modules/CRM](CRM.md) — base CRM module (`crm.lead`, UTM mixin)
- [Modules/Mass Mailing Sale](mass-mailing-sale.md) — sale order email marketing tracking
- [Modules/crm-sms](crm-sms.md) — CRM SMS integration
- [Core/Fields](Fields.md) — Many2one, computed fields, `store=True` behavior
