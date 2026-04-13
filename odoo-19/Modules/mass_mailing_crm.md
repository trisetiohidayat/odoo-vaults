---
title: Mass Mailing CRM
category: Marketing/Email Marketing
tags: [odoo, odoo19, mass_mailing, crm, utm, marketing, leads, opportunities, module-documentation]
description: Integration module bridging mass mailing campaigns with CRM lead/opportunity tracking, enabling UTM source attribution and lead counting from marketing emails.
---

# Mass Mailing CRM (`mass_mailing_crm`)

## Module Overview

**Module ID:** `mass_mailing_crm`
**Category:** Marketing/Email Marketing
**Version:** 1.0
**Depends:** `crm`, `mass_mailing`
**License:** LGPL-3
**Auto-install:** `True`
**Author:** Odoo S.A.

**L2: `auto_install=True` rationale:** This flag tells the Odoo module auto-installation system to install `mass_mailing_crm` automatically whenever both `crm` and `mass_mailing` are installed (or installed at the same time). This is correct behavior because the module only activates a previously dormant integration — it has no functional purpose without both parent modules. There is no `data` security CSV file; the module relies on the security groups defined by `crm` and `mass_mailing`. Users without at least read access to `crm.lead` will see the lead count silently omitted in the statistics email (via `has_access('read')`), and the stat button will show "0" due to `sudo()` elevating the query but the result being filtered to zero attributable records.

**L2: No `security/` directory:** `mass_mailing_crm` defines no `ir.model.access` records. All access control is inherited from `crm` (which defines `crm.lead` access rules for `crm.group_crm_manager` and `crm.group_crm_salesman`) and `mass_mailing` (which defines `mailing.mailing` access for `mass_mailing.group_mass_mailing_user`). The marketing user who sends mailings may not have CRM access, which is why `_compute_crm_lead_count` uses `sudo()` and `_prepare_statistics_email_values` silently omits the lead KPI when `has_access('read')` fails.

`mass_mailing_crm` is a lightweight integration module that bridges Odoo's **email marketing** engine (`mass_mailing`) with the **CRM** module (`crm`). Its purpose is dual:

1. Enable mass mailing campaigns to target `crm.lead` records directly (instead of only `mailing.contact` and `res.partner`)
2. Provide statistical feedback — counting how many leads/opportunities were generated from each mailing campaign — displayed both as a stat button on the mailing form and as a KPI in the post-send statistics email

The module is intentionally minimal: it adds only the three extension points that make the cross-module integration possible. All heavy lifting (email sending, lead management, UTM tracking) is delegated to the parent modules.

## Architecture

`mass_mailing_crm` extends three models through classical Odoo inheritance (`_inherit`):

```
mailing.mailing  (mass_mailing)
    └─ inherits MailingMailing  (mass_mailing_crm/models/mailing_mailing.py)
           ├─ + use_leads              Boolean (computed)  -- UI label switcher
           ├─ + crm_lead_count         Integer (computed) -- lead count by source
           ├─ + action_redirect_to_leads_and_opportunities()  -- list/pivot/graph view
           └─ + _prepare_statistics_email_values()            -- KPI injection

crm.lead         (crm)
    └─ inherits CrmLead  (mass_mailing_crm/models/crm_lead.py)
           └─ + _mailing_enabled = True  (class attribute flag)

utm.campaign     (utm)
    └─ inherits UtmCampaign  (mass_mailing_crm/models/utm.py)
           └─ + ab_testing_winner_selection: selection_add 'crm_lead_count'
```

The `mailing.mailing` parent class already inherits from `utm.source.mixin`, giving it `source_id` natively. The `crm.lead` parent class already inherits from `utm.mixin`, giving it `campaign_id`, `source_id`, and `medium_id` natively. The module does not need to add these fields; it only activates the counting and UI integration.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Top-level import (empty) |
| `__manifest__.py` | Module metadata, `auto_install=True`, `depends: ['crm', 'mass_mailing']` |
| `models/__init__.py` | Imports `crm_lead`, `mailing_mailing`, `utm` submodules |
| `models/crm_lead.py` | Sets `_mailing_enabled = True` on `crm.lead` |
| `models/mailing_mailing.py` | Computed fields, action, and email KPI hook |
| `models/utm.py` | Extends A/B testing winner selection |
| `views/mailing_mailing_views.xml` | Injects stat button into `mailing.mailing` form |
| `demo/mailing_mailing.xml` | Creates a sample mailing targeting `crm.lead` |

---

## Model: `CrmLead` — `crm.lead`

**File:** `models/crm_lead.py`

```python
class CrmLead(models.Model):
    _inherit = 'crm.lead'
    _mailing_enabled = True
```

### `_mailing_enabled` Class Attribute

**Type:** Python class attribute (not an Odoo field)
**Value:** `True` (boolean flag)
**Purpose:** Registers `crm.lead` as a valid mailing target model

This is the central mechanism of the module. The `_mailing_enabled` flag is a **mixin-style class attribute** — a Python convention used by `mass_mailing` to discover which models support marketing email campaigns.

The discovery flow:

```
1. mass_mailing loads its models/__init__.py
2. mass_mailing/models/ir_model.py defines is_mailing_enabled on ir.model:

   class IrModel(models.Model):
       _inherit = 'ir.model'

       is_mailing_enabled = fields.Boolean(
           compute='_compute_is_mailing_enabled',
           search='_search_is_mailing_enabled',
       )

       def _compute_is_mailing_enabled(self):
           for model in self:
               model.is_mailing_enabled = getattr(
                   self.env[model.model], '_mailing_enabled', False
               )
```

```
3. mailing.mailing's mailing_model_id field has domain:

   domain="[('is_mailing_enabled', '=', True)]"

   → crm.lead appears in the "Send to" dropdown
```

**L4: `_search_is_mailing_enabled` and the searchable domain:** The `is_mailing_enabled` field on `ir.model` has `search='_search_is_mailing_enabled'`. This custom search method allows the domain `[('is_mailing_enabled', '=', True)]` to be evaluated by searching through `ir.model` records where `getattr(model_instance, '_mailing_enabled', False)` is truthy. Crucially, it only supports `in` and `not in` operators (returning `NotImplemented` for others). The domain operator `=` is internally converted to the `in` operator by Odoo's domain parser for boolean fields with custom search methods, making `= True` functionally equivalent to `in [True]`.

**L4: Model registration order matters for `is_mailing_enabled` display:** The `ir.model` records for `crm.lead` and `mailing.contact` are created when their respective modules are installed. `mass_mailing_crm`'s `auto_install=True` means it installs after both `crm` and `mass_mailing`. By that time, the `ir.model` record for `crm.lead` already exists. The `is_mailing_enabled` computed field on `ir.model` re-evaluates on every read (not stored), so there is no upgrade step needed when `mass_mailing_crm` is installed — `crm.lead` immediately becomes a mailing-enabled model.

Without `_mailing_enabled = True`, the `mailing_model_id` selector would show `crm.lead` as disabled/grayed out, even though it technically could receive emails.

### L3: How `_mailing_enabled` Differs from Fields

`_mailing_enabled` is a Python class attribute, not an `odoo.api` computed field. This distinction matters:

- **No database storage**: No column is created in `crm_lead` table
- **No ORM dependency tracking**: Changes to `_mailing_enabled` do not trigger recomputation
- **Evaluated at runtime**: `getattr(model_instance, '_mailing_enabled', False)` reads the Python class
- **Inheritance-safe**: Subclasses inherit the attribute; `getattr` traverses the MRO

This is the correct pattern for mixin-style flags because it avoids the overhead of field-level tracking for a static configuration value.

### L3: Source Attribution Chain

When a `crm.lead` is created, it inherits three UTM tracking fields from `utm.mixin`:

```python
# utm/models/utm_mixin.py
class UtmMixin(models.AbstractModel):
    campaign_id = fields.Many2one('utm.campaign', 'Campaign',
        index='btree_not_null',
        help="Name that helps track different campaign efforts")
    source_id = fields.Many2one('utm.source', 'Source',
        index='btree_not_null',
        help="Source of the link (e.g. Search Engine, email list)")
    medium_id = fields.Many2one('utm.medium', 'Medium',
        index='btree_not_null',
        help="Method of delivery (e.g. Postcard, Email, Banner Ad)")
```

The UTM fields are populated in `UtmMixin.default_get()` by reading URL parameters (`utm_campaign`, `utm_source`, `utm_medium`) from cookies set by the `ir_http` tracking mechanism. When a lead is created from a tracked link (e.g., from an email campaign), the `source_id` is automatically set to the mailing's UTM source.

Once set, `source_id` persists on the lead throughout its lifecycle — even as it progresses through CRM stages, is converted from Lead to Opportunity, and is won or lost. This makes `source_id` the stable attribution key used by `mass_mailing_crm` for lead counting.

**L4: UTM source auto-creation via `UtmSourceMixin`:** `mailing.mailing` inherits from `utm.source.mixin`, which provides `source_id` as a **required** Many2one field with `ondelete='restrict'`. The mixin overrides `create()` to automatically create a matching `utm.source` record if `source_id` is not explicitly provided — the source name is derived from the mailing's subject line (`_rec_name`). This means that creating a mailing with a subject but no explicit `source_id` automatically provisions a UTM source named after the subject, which then becomes the attribution key for all leads generated from that campaign.

**L4: `ondelete='restrict'` consequence:** The `source_id` field on `mailing.mailing` uses `ondelete='restrict'` (inherited from `UtmSourceMixin`). Attempting to delete a `utm.source` record that is linked to any `mailing.mailing` raises a `ValidationError`. This protects the attribution chain — a source cannot be accidentally deleted while active mailings reference it. To delete the source, all linked mailings must first be unlinked or have their `source_id` cleared.

**L4: `name` field is a `related` of `source_id.name`:** The `name` field on `mailing.mailing` is defined as `name = fields.Char(related='source_id.name', readonly=False)` in `UtmSourceMixin`. Setting `readonly=False` means the mailing's own `name` field (the mailing's subject line, inherited from `mail.render.mixin`) can be written independently, but it also means that setting `name` directly on the mailing does not automatically update `source_id.name` — that happens only through `UtmSourceMixin.write()`, which explicitly syncs the name to the source record.

### L3: `mailing.trace` Creation

`mailing.trace` records are created by `mass_mailing`'s email sending engine when a mailing is sent to `crm.lead` recipients. Each trace captures:

```python
# mass_mailing/models/mailing_trace.py
class MailingTrace(models.Model):
    trace_type = fields.Selection([('mail', 'Email')], default='mail')
    model = fields.Char(string='Document model', required=True)  # 'crm.lead'
    res_id = fields.Many2oneReference(string='Document ID')     # lead ID
    mass_mailing_id = fields.Many2one('mailing.mailing')
    campaign_id = fields.Many2one(related='mass_mailing_id.campaign_id', store=True)
    source_id = fields.Many2one(related='mass_mailing_id.source_id')
    trace_status = fields.Selection([
        ('outgoing', 'Outgoing'), ('sent', 'Delivered'),
        ('open', 'Opened'), ('reply', 'Replied'),
        ('bounce', 'Bounced'), ('error', 'Exception'),
    ])
```

The `source_id` on the trace is **related** from `mass_mailing_id.source_id`, so it is automatically populated when the trace is created. This creates the full attribution chain: mailing -> source -> trace -> lead.

---

## Model: `MailingMailing` — `mailing.mailing`

**File:** `models/mailing_mailing.py`

Inherits from `mailing.mailing` (from `mass_mailing`, which inherits from `mail.thread`, `mail.activity.mixin`, `mail.render.mixin`, and `utm.source.mixin`).

### Field: `use_leads`

**Type:** `Boolean` — computed, not stored
**Compute method:** `_compute_use_leads()`
**String:** `'Use Leads'`

```python
def _compute_use_leads(self):
    self.use_leads = self.env.user.has_group('crm.group_use_lead')
```

**Purpose:** Determines whether UI labels should say "Leads" or "Opportunities"

The `crm.group_use_lead` group controls Odoo's pipeline split between Leads and Opportunities. When a user has this group:
- CRM menu shows separate "Leads" and "Opportunities" menus
- All records are labeled "Lead" initially
- Users can convert leads to opportunities

When the user does **not** have this group:
- CRM menu shows only "Opportunities"
- All records are created as Opportunities directly

Since `use_leads` is a compute based on the current user's group membership, it dynamically adapts without needing a stored value. Group membership changes take effect on the next page load (Odoo caches group membership in the session).

**L4: `use_leads` is non-stored — implications:** Because `use_leads` has no `store=True`, it is recomputed on every form load by calling `has_group()` for each record in the recordset. For a single form view, this is one `has_group` RPC call. For a kanban/list view rendering stat buttons on many mailings at once, the compute fires once per record. The field cannot be searched or filtered on. The button's `invisible` attribute evaluates `use_leads` client-side in the view domain, so the label dynamically switches without a server round-trip for already-loaded records.

### Field: `crm_lead_count`

**Type:** `Integer` — computed, not stored
**Compute method:** `_compute_crm_lead_count()`
**String:** `'Leads/Opportunities Count'`

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

**What it counts:** The number of `crm.lead` records whose `source_id` matches the mailing's `source_id`.

**L3: Why `source_id` matching?** A `mailing.mailing` is configured with a `campaign_id` (UTM campaign) and a `source_id` (UTM source). Leads created from that campaign carry that same `source_id`. By matching `source_id`, the count captures all leads attributable to the campaign — regardless of when they were created relative to the mailing's send date.

**L3: Edge case — no `source_id`:** When `self.source_id` is `False` (not set), `self.source_id.ids` returns `[]`. The domain `[('source_id', 'in', [])]` matches no records, so `crm_lead_count` is `0`.

**L3: Edge case — multiple mailings in batch:** When called on a recordset of N mailings (e.g., loading a list view), `self.source_id.ids` contains up to N IDs. The `_read_group` executes a single SQL query with `WHERE source_id IN (id1, id2, ..., idN) GROUP BY source_id`. The `mapped_data` dictionary then provides O(1) lookups for each mailing. This is the correct batch-optimization pattern.

**L4: SQL trace of the `_read_group`:** The `_read_group` translates to:
```sql
SELECT source_id, COUNT(*) AS __count
FROM crm_lead
WHERE source_id IN (source_id_1, source_id_2, ..., source_id_N)
  AND active = TRUE  -- implicit, unless active_test=False is passed
GROUP BY source_id
ORDER BY source_id
```
The `mapped_data = {source.id: count for source, count in lead_data}` iteration walks the grouped rows returned by `_read_group`. Each row is a `crm.lead` record object for the `source_id` group key (not a scalar integer), so `source.id` is the correct accessor. If a given `source_id` has zero leads, it simply does not appear in the grouped result set — the `mapped_data.get(..., 0)` handles that gracefully.

**L4: What "counting by `source_id`" misses:** The count is keyed purely on `source_id`, not on `campaign_id`. This means if two mailings in the same campaign have different `source_id` values (e.g., "Summer Newsletter" and "Summer Offer" variants within the same UTM campaign), their leads are counted separately. Leads that arrived via website form without a UTM source (source_id is `False`) are never attributed to any mailing. This is the correct semantic behavior — attribution is UTM-source-based, not campaign-based.

**L3: `active_test=False` context:** By default, Odoo's ORM filters out `active=False` records. Setting `active_test=False` includes inactive/archived leads in the count. This is intentional for statistical completeness — archived leads still represent campaign outcomes.

**L3: `sudo()` necessity:** The `sudo()` call elevates the query to superuser. The mailing user may lack read access to `crm.lead` (e.g., a marketing user with `mass_mailing.group_mass_mailing_user` but no CRM group). Without `sudo()`, the query would raise an `AccessError` for users without CRM read rights, making the stat button fail to load.

**L4: Performance analysis:**

| Scenario | SQL Queries | Impact |
|----------|-------------|--------|
| Single mailing, valid source | 1 `GROUP BY` query | Fast |
| 20 mailings in list view | 1 `GROUP BY` query (batched) | Fast |
| 100 mailings, many source IDs | 1 query with large `IN (...)` clause | Acceptable |
| Mailing with no `source_id` | 1 empty-result query | Fast |

The implementation is already optimized for batch scenarios. Potential optimization (L4): Adding `store=True` to `crm_lead_count` and updating via computed trigger would eliminate recomputation on every form load, trading storage for load-time performance. However, for typical usage (a few mailings loaded at a time), the current approach is sufficient.

**L4: Database index usage:** `source_id` on `crm.lead` has `index='btree_not_null'` (set in `utm.mixin`). The `_read_group` query benefits from this index for the `WHERE source_id IN (...)` clause.

### Method: `action_redirect_to_leads_and_opportunities()`

**Returns:** `ir.actions.act_window` (list/pivot/graph view of matching leads)
**Arguments:** `self` — `mailing.mailing` recordset

```python
def action_redirect_to_leads_and_opportunities(self):
    text = _("Leads") if self.use_leads else _("Opportunities")
    helper_header = _("No %s yet!", text)
    helper_message = _(
        "Note that Odoo cannot track replies if they are sent towards email addresses to this database."
    )
    return {
        'context': {
            'active_test': False,
            'create': False,
            'search_default_group_by_create_date_day': True,
            'crm_lead_view_hide_month': True,
        },
        'domain': [('source_id', 'in', self.source_id.ids)],
        'help': Markup('<p class="o_view_nocontent_smiling_face">%s</p><p>%s</p>') % (
            helper_header, helper_message,
        ),
        'name': _("Leads Analysis"),
        'res_model': 'crm.lead',
        'type': 'ir.actions.act_window',
        'view_mode': 'list,pivot,graph,form',
    }
```

**L3: Domain `in` vs `=`:** The domain uses `in` (`[('source_id', 'in', self.source_id.ids)]`) rather than `=` (`[('source_id', '=', self.source_id.id)]`). This handles the batch scenario: when triggered from a list view with multiple mailings selected, `self.source_id.ids` contains multiple source IDs, and the `in` operator shows all leads matching any of those sources. If only one mailing is selected, the behavior is identical to `=`.

**L3: Context flags:**

| Key | Value | Effect |
|-----|-------|--------|
| `active_test: False` | `True` | Include archived leads in the list view |
| `create: False` | `False` | Disable the "Create" button (read-only analysis view) |
| `search_default_group_by_create_date_day: True` | `True` | Pre-group results by creation day, showing lead generation timeline |
| `crm_lead_view_hide_month: True` | `True` | Hide the month-level grouping toggle in the grouped view |

**L4: `active_test=False` — intentional consistency with stat button:** The stat button query (`_compute_crm_lead_count`) also uses `active_test=False` via `with_context(active_test=False)`. The action's list view mirrors this with the same context flag, ensuring the count in the stat button exactly matches the number of records visible when the user clicks through. This is important for user trust — if the stat button shows "12" but the linked list only shows "8" active records, it creates confusion.

**L4: `crm_lead_view_hide_month` context flag:** This is a view-specific toggle read by `crm.lead`'s search view. When `True`, it suppresses the month-level grouping option (which exists alongside the day-level grouping pre-selected by `search_default_group_by_create_date_day`). This keeps the view focused on the daily timeline rather than offering a month/day granularity choice, appropriate for a focused analysis view.

**L3: Empty state helper HTML:** The `help` key injects HTML into the view's empty state. This is Odoo's standard pattern for informative empty states (`o_view_nocontent_smiling_face` class triggers the "no content" illustration). The message warns that **Odoo cannot track replies** when sending to internal database addresses — a key limitation users must understand.

**L3: Why replies can't be tracked for internal emails:** When sending to `crm.lead` records whose email addresses are in the same Odoo database (`res.partner`-linked emails), reply emails go through Odoo's incoming mail gateway. The reply-tracking mechanism depends on a unique reply-to address per mailing, which works for external recipients but not for database-internal addresses that route through the standard alias system.

**L4: `markupsafe.Markup` requirement:** The `Markup()` call is mandatory because Odoo 15+ automatically sanitizes HTML rendered in the UI. Wrapping the string in `Markup()` marks it as pre-escaped, preventing double-escaping. Without `Markup()`, the HTML entities would be escaped (`&lt;p&gt;` instead of `<p>`), breaking the empty state display.

**L4: `ensure_one()` not used:** The method does not call `self.ensure_one()`. This is intentional — it allows the action to be called from a list context with multiple mailings selected. When multiple mailings are selected, `self.source_id.ids` spans their sources, and the resulting list view shows all leads matching any selected mailing's campaign source. This is a useful batch analysis feature.

**L4: `view_mode` order significance:** `view_mode='list,pivot,graph,form'` puts list first — Odoo's action system opens the first view by default. Including `form` at the end allows users to drill into any individual lead from the list without an additional click to switch views. The `form` view in this context is the standard `crm.lead` form, not a filtered variant. The `pivot` and `graph` views are available for aggregate analysis, which is the primary purpose of this action.

### Method: `_prepare_statistics_email_values()`

**Returns:** Dictionary of KPI data for the post-send statistics email
**Arguments:** `self` — single `mailing.mailing` record

```python
def _prepare_statistics_email_values(self):
    self.ensure_one()
    values = super()._prepare_statistics_email_values()
    if not self.user_id:
        return values
    if not self.env['crm.lead'].has_access('read'):
        return values
    values['kpi_data'][1]['kpi_col1'] = {
        'value': tools.misc.format_decimalized_number(self.crm_lead_count, decimal=0),
        'col_subtitle': _('LEADS'),
    }
    values['kpi_data'][1]['kpi_name'] = 'lead'
    return values
```

**L3: Hook pattern:** This method uses the **hook pattern** (extends parent return value). It calls `super()._prepare_statistics_email_values()` first, then modifies the returned dictionary. This is safer than replacing the entire method — the parent populates sent/delivered/bounced/open/click KPIs, and this extension adds the lead count.

**L3: `kpi_data` structure:** The parent method builds a fixed 2-element list regardless of `mailing_type`:
- `kpi_data[0]` — **Engagement KPIs**: received ratio, open ratio, reply ratio (populated when `mailing_type == 'mail'`, empty `{}` for SMS)
- `kpi_data[1]` — **Business Benefits KPIs**: initially empty, this is the extension slot `mass_mailing_crm` populates with `kpi_col1`

Each KPI slot is a dictionary with keys: `kpi_fullname` (section title), `kpi_col1/2/3` (individual metric dictionaries each containing `value` and `col_subtitle`), `kpi_action` (optional URL for a CTA), and `kpi_name` (identifies the KPI type for the email template renderer). The parent method pre-builds both slots before returning; `mass_mailing_crm` adds `kpi_col1` to `kpi_data[1]` and sets `kpi_name = 'lead'`.

**L4: `kpi_name` controls QWeb rendering:** The `kpi_name = 'lead'` key is read by the email template (`mass_mailing/mass_mailing_kpi_link`) to conditionally render a leads-specific section. If `kpi_name` were left unset (the parent leaves it absent for the business benefits slot), the template would not render a leads sub-section. Setting it to `'lead'` activates that rendering branch.

**L3: Permission guard with `has_access()`:** The `has_access('read')` check is a proper ACL check, not just a sudo escalation. It verifies whether the mailing's `user_id` (the responsible user who receives the statistics email) has read access to `crm.lead`. If not, the lead count is silently omitted — the email is still sent with the standard email KPIs, just without the lead count.

**L4: Contrast with `sudo()` in `_compute_crm_lead_count`:** The stat button uses `sudo()` because it serves the current user's view of the mailing form — the current user should see the total count. The statistics email uses `has_access()` because it is delivered to `user_id` — that specific user's ACL should be respected.

**L3: `ensure_one()` pattern:** The method calls `self.ensure_one()` because the KPI statistics email is sent one email per mailing (batched per responsible user). Processing multiple mailings at once would be complex and is not a supported use case for this method.

**L4: `format_decimalized_number`:** This Odoo utility formats large numbers with locale-appropriate separators and compact notation (e.g., `1,234` or `12.3K` for very large numbers). Setting `decimal=0` means no decimal places — the lead count is displayed as a whole number, which is appropriate for count statistics.

---

## Model: `UtmCampaign` — `utm.campaign`

**File:** `models/utm.py`

Inherits from `utm.campaign` (which is in turn provided by `mass_mailing`, not `utm`). Extends the A/B testing winner selection criterion.

### Field: `ab_testing_winner_selection`

**Type:** `Selection` — inherited field, extended via `selection_add`
**String:** `'Winner Selection'` (inherited from parent)

```python
ab_testing_winner_selection = fields.Selection(
    selection_add=[('crm_lead_count', 'Leads')]
)
```

**Parent options (from `mass_mailing/models/utm_campaign.py`):**
```python
ab_testing_winner_selection = fields.Selection([
    ('manual', 'Manual'),
    ('opened_ratio', 'Highest Open Rate'),
    ('clicks_ratio', 'Highest Click Rate'),
    ('replied_ratio', 'Highest Reply Rate'),
], default='opened_ratio')
```

**This module adds:** `('crm_lead_count', 'Leads')`

**L3: `selection_add` pattern:** The `selection_add` parameter is Odoo's safe mechanism for extending Selection fields across modules. Instead of redefining the entire selection list (which would overwrite other modules' additions), `selection_add` appends new options to the existing list. This pattern was introduced in Odoo 13 and is the standard approach in Odoo 19.

**L3: A/B testing winner determination flow:**

1. User creates an A/B test campaign with multiple mailing variants
2. Each variant is assigned a different `ab_testing_pc` (percentage of recipients)
3. All variants are sent
4. The `utm.campaign._cron_process_mass_mailing_ab_testing()` cron runs (scheduled daily)
5. It finds campaigns where `ab_testing_schedule_datetime <= now` and `ab_testing_winner_selection != 'manual'`
6. For each campaign, it calls `action_send_winner_mailing()` on the winning variant
7. The winning variant is selected based on `ab_testing_winner_selection`

When `ab_testing_winner_selection = 'crm_lead_count'`, the winner is the mailing variant whose `source_id` generated the most `crm_lead_count` leads.

**L4: How `mass_mailing` resolves the `crm_lead_count` winner criterion:** The `mass_mailing` module's `action_send_winner_mailing()` method calls `_get_ab_testing_winner_selection()` on the winning mailing candidate, which returns `{'value': 'crm_lead_count', 'description': 'Leads'}`. It then sorts sibling mailings by the value of `ab_testing_winner_selection` using `sorted(..., 'crm_lead_count', reverse=True)`. Because `crm_lead_count` is a field on `mailing.mailing`, this resolves to sorting by `crm_lead_count` descending — which is computed via `_compute_crm_lead_count`. Therefore, `mass_mailing_crm` does not need to override any A/B testing logic; the field it adds to `mailing.mailing` is sufficient for the ORM-level sorting to work.

**L4: `selection_add` conflict avoidance:** `selection_add` only works reliably when modules that extend the same Selection field use it in their own `__manifest__.py` load order. If two modules both try to `selection_add` the same key (`'crm_lead_count'`), Odoo raises a validation error at startup. No such conflict exists in the standard distribution.

**L4: Performance of A/B testing with `crm_lead_count`:** The winner determination uses the same `_compute_crm_lead_count` mechanism, which runs one efficient `_read_group` per campaign's source(s). For A/B tests with 2-5 variants, this is lightweight. The cron processes campaigns daily, not per-send, so performance is not a concern.

---

## View Extension

**File:** `views/mailing_mailing_views.xml`

```xml
<xpath expr="//button[@id='button_view_delivered']" position="before">
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
</xpath>
```

**L3: Button placement:** The button is placed before `button_view_delivered` (the standard stat showing delivery count). The `oe_stat_button` class renders it as a KPI tile in the form header, consistent with the sent/delivered/opened/clicked stat buttons.

**L3: Dynamic label switching:** Two `<span>` elements with conditional `invisible` attributes:
- `invisible="not use_leads"` — shows "Leads" when `use_leads = True`
- `invisible="use_leads"` — shows "Opportunities" when `use_leads = False`

This dual-span pattern is the standard Odoo approach for context-dependent labels.

**L3: `invisible="state == 'draft'"`:** The button is hidden when the mailing is in draft state. This is appropriate because:
- In draft state, `source_id` may not be set yet
- Recipients have not been determined, so lead count is meaningless
- The button would show `0` before sending, which is uninformative

**L4: `use_leads` field is hidden but present:** `<field name="use_leads" invisible="1"/>` is necessary to load the field's value into the view's rendering context. Without this, the `invisible="not use_leads"` condition would fail because the field value would not be available in the view's domain evaluation scope.

---

## Demo Data

**File:** `demo/mailing_mailing.xml`

The demo creates a sample mailing that targets `crm.lead`:

```xml
<record id="mass_mail_lead_0" model="mailing.mailing">
    <field name="name">Lead Recall</field>
    <field name="subject">We want to hear from you!</field>
    <field name="state">draft</field>
    <field name="user_id" ref="base.user_admin"/>
    <field name="schedule_date" eval="(DateTime.today() + relativedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S')"/>
    <field name="campaign_id" ref="mass_mailing.mass_mail_campaign_1"/>
    <field name="source_id" ref="utm.utm_source_mailing"/>
    <field name="mailing_model_id" ref="crm.model_crm_lead"/>
    <field name="mailing_domain">[]</field>
    <field name="reply_to_mode">new</field>
    <field name="reply_to">{{ object.company_id.email }}</field>
    <!-- HTML body template -->
</record>
```

Key observations:
- `mailing_model_id = crm.model_crm_lead` — explicitly targets `crm.lead`
- `mailing_domain = []` — targets all leads (subject to record rules)
- `reply_to_mode = 'new'` — replies route to the company's catch-all address
- The HTML body uses `{{ object.company_id.email }}` (QWeb template syntax) for dynamic reply-to
- Demo data has `noupdate="1"` — it is not re-installed on module upgrades, preserving any manual changes made to the demo mailing after first install

**L4: `reply_to` using QWeb in XML demo:** The `reply_to` field contains the QWeb expression `{{ object.company_id.email }}`. In the demo context, `object` resolves to the `mailing.mailing` record being created. During email rendering (in `mailing.mailing._prepare_email_values()`), this expression is evaluated in the QWeb context where `object` is bound to the current record. The `company_id` is taken from the `mailing.mailing` record — which in demo is populated from `base.user_admin`'s default company. This is a safe demo pattern; in production, the `reply_to` would typically be set to a dedicated catch-all alias rather than a user email.

**L4: `state = 'draft'` in demo:** The demo mailing is created in `'draft'` state, not `'scheduled'` or `'done'`. This means the stat button (`invisible="state == 'draft'"`) would not be visible for the demo record. The `schedule_date` is set 5 days in the future, so the demo mailing is never auto-sent during normal usage — it serves only as an illustration of the form configuration.

---

## L4: Complete Lead Attribution Pipeline

Understanding how `mass_mailing_crm` integrates into the broader marketing-to-sales flow:

```
Phase 1: Campaign Setup
  Marketing User creates a mass mailing
    mailing.campaign_id = utm.campaign (e.g., "Summer Campaign")
    mailing.source_id = utm.source    (e.g., "Email Newsletter")
    mailing.mailing_model_id = crm.model_crm_lead  ← mass_mailing_crm enables this
    mailing.mailing_domain = [...]   (filter criteria for leads)

Phase 2: Email Sending (mass_mailing engine)
  For each crm.lead in mailing_domain:
    1. Generate individual email (render body with lead data via QWeb)
    2. Create mail.mail record
    3. Create mailing.trace record:
         - model = 'crm.lead'
         - res_id = lead.id
         - mass_mailing_id = mailing.id
         - campaign_id = mailing.campaign_id.id   (inherited via related field)
         - source_id = mailing.source_id.id        (inherited via related field)

Phase 3: Lead Attribution (website or external channel)
  External visitor clicks tracked link in email
  → Redirects through ir_http tracking
  → UTM parameters captured in cookies
  → website_crm or crm_iap creates crm.lead:
       - campaign_id = utm.campaign from cookie (matching Phase 1 campaign)
       - source_id = utm.source from cookie       (matching Phase 1 source)
       - medium_id = utm.medium from cookie       (matching Phase 1 medium)

Phase 4: Lead Counting (mass_mailing_crm)
  _compute_crm_lead_count runs on mailing form load:
    SELECT source_id, COUNT(*)
    FROM crm_lead
    WHERE source_id IN (mailing.source_id)
    GROUP BY source_id
  → crm_lead_count = count of attributable leads
  → Displayed in stat button

Phase 5: Lead Analysis (user action)
  User clicks stat button
  → action_redirect_to_leads_and_opportunities()
  → Opens crm.lead list with domain [source_id = mailing.source_id]
  → User can analyze leads in list/pivot/graph views

Phase 6: A/B Testing Winner (optional cron)
  utm.campaign._cron_process_mass_mailing_ab_testing()
  → For each completed A/B campaign with crm_lead_count winner criterion:
  → Compare crm_lead_count across all variants
  → Send winning variant to remaining recipients
```

---

## L4: Odoo 18 to Odoo 19 Changes

### `_mailing_enabled` Mechanism (Unchanged)

The `_mailing_enabled = True` class attribute pattern predates Odoo 18 and is unchanged. This is a stable, supported API that `mass_mailing` uses to enumerate mailing-capable models.

### `fields.Selection(selection_add=[...])` (Stable Since Odoo 13)

The `selection_add` pattern for extending Selection fields was introduced in Odoo 13 and is the standard approach in Odoo 19. It replaced the older pattern of fully overriding the selection definition, which would break module compatibility.

### `markupsafe.Markup` for HTML Helper (Odoo 15+)

The `action_redirect_to_leads_and_opportunities` method wraps the helper HTML in `Markup()`:

```python
from markupsafe import Markup
helper_header = _("No %s yet!", text)
helper_message = _("Note that Odoo cannot track replies...")
return {
    'help': Markup('<p class="o_view_nocontent_smiling_face">%s</p><p>%s</p>') % (
        helper_header, helper_message,
    ),
}
```

This became necessary in Odoo 15 when Odoo introduced automatic HTML sanitization in the web client. Strings rendered in the UI are automatically HTML-escaped by default. `Markup()` marks a string as pre-escaped, preventing the framework from double-escaping the HTML tags.

### `_read_group` over `search_count` (Optimization Trend)

The use of `_read_group` for aggregate counting (instead of multiple `search_count` calls) is consistent with Odoo 19's performance optimization philosophy. A single `GROUP BY` query is significantly faster than N separate `COUNT(*)` queries.

### UTM `find_or_create_record` Improvements

The `utm.mixin` received improvements in `_find_or_create_record` and `_get_unique_names` methods in recent versions. The `_find_or_create_record` method now correctly handles:
- Case-insensitive matching (`=ilike` instead of `=`)
- Auto-campaign creation via `is_auto_campaign` flag
- Unique name generation with automatic counters

The `mass_mailing_crm` module benefits from these improvements passively — leads created through tracked campaigns will have properly named UTM sources.

### `active_test=False` Context (Stable)

Using `active_test=False` to include archived records in statistics has been standard since Odoo 12 and remains the pattern in Odoo 19.

### `ensure_one()` in Action Methods (Best Practice)

The `_prepare_statistics_email_values()` method uses `self.ensure_one()`, which became a best practice recommendation in Odoo 14+ for methods that process single records. This prevents accidental batch processing that would produce incorrect KPI emails.

---

## L4: Performance Summary

| Operation | Queries | Notes |
|-----------|---------|-------|
| `_compute_crm_lead_count` (single) | 1 `GROUP BY` | Single SQL, uses `source_id` index |
| `_compute_crm_lead_count` (batch) | 1 `GROUP BY` | Batched, same efficiency |
| `action_redirect_to_leads_and_opportunities` | 0 direct | Returns action; CRM search executes in client |
| `_prepare_statistics_email_values` | 1 `has_access` check | Lightweight permission lookup |
| Stat button render | 1 `_read_group` | Triggered by view rendering |

The module is performance-neutral. The only database query that runs on every mailing form load is the `_read_group` count, which is a single optimized SQL query. No `store=True` fields means no recomputation triggers.

---

## Related Documentation

- [Modules/mass_mailing](Modules/mass_mailing.md) — Parent mass mailing module
- [Modules/CRM](Modules/CRM.md) — CRM module providing `crm.lead`
- [Modules/UTM](Modules/utm.md) — UTM tracking (campaigns, sources, mediums)
- [Core/API](Core/API.md) — ORM API decorators used
- [Patterns/Inheritance Patterns](Patterns/Inheritance Patterns.md) — `_inherit` vs mixin class attribute patterns
- [Modules/res.partner](Modules/res.partner.md) — Partner model that is also a mailing target
