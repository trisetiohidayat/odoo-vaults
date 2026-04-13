---
uid: sale_crm
title: "sale_crm — Opportunity to Quotation"
date: 2026-04-11
version: 1.0
module: sale_crm
description: Bidirectional link between CRM opportunities and Sale orders. Creates quotations directly from leads/opportunities, tracks revenue, and surfaces sales statistics on the CRM form.
tags:
  - #odoo19
  - #modules
  - #crm
  - #sale
  - #cross-module
---

# sale_crm — Opportunity to Quotation

## Module Overview

| Property | Value |
|---|---|
| Technical name | `sale_crm` |
| Category | `Sales/Sales` |
| Version | `1.0` |
| Depends | `sale`, `crm` |
| Auto-install | `True` (installed automatically when both `sale` and `crm` are present) |
| License | LGPL-3 |
| Author | Odoo S.A. |

## Purpose

`sale_crm` bridges the gap between the CRM and Sale apps. It adds a **"New Quotation"** button on `crm.lead` opportunity forms, wires up a **bidirectional One2many** between opportunities and sale orders, surfaces revenue statistics on the CRM form, and auto-updates `expected_revenue` when confirmed orders exceed the current projection.

It is a thin, focused integration module: no new business logic beyond cross-model linking and revenue tracking.

---

## Architecture

```
crm.lead (opportunity) ───1─── One2many ──M── sale.order
       │                                          │
       └── opportunity_id (Many2one, back-ref) ────┘
```

**Inheritance chain:**
- `crm.lead` is extended via `_inherit = 'crm.lead'` (classic extension)
- `sale.order` is extended via `_inherit = 'sale.order'` (classic extension)
- `crm.team` is extended via `_inherit = 'crm.team'`

---

## Model Reference

### `crm.lead` — Extensions

File: `~/odoo/odoo19/odoo/addons/sale_crm/models/crm_lead.py`

#### Fields Added by sale_crm

##### `sale_amount_total`

```python
sale_amount_total = fields.Monetary(
    compute='_compute_sale_data',
    string="Sum of Orders",
    help="Untaxed Total of Confirmed Orders",
    currency_field='company_currency'
)
```

- **Type**: Monetary (computed, not stored)
- **Currency**: Resolved via `lead.company_currency`
- **Computation**: Sum of `amount_untaxed` for all sale orders linked to this lead, filtered by `_get_lead_sale_order_domain()` (i.e., state `not in ('draft', 'sent', 'cancel')` — only confirmed/sale orders).
- **Currency conversion**: Each order's amount is converted to the lead's company currency using `order.currency_id._convert(order.amount_untaxed, company_currency, order.company_id, order.date_order or today)`.
- **L3 detail**: Because this is computed on every read, it reflects live data from all linked orders. It does not include cancelled or draft quotations. If orders use different currencies, each is independently converted at its own `date_order` rate.

##### `quotation_count`

```python
quotation_count = fields.Integer(
    compute='_compute_sale_data',
    string="Number of Quotations"
)
```

- **Type**: Integer (computed, not stored)
- **Computation**: Count of `order_ids` filtered by `_get_lead_quotation_domain()` → `state in ('draft', 'sent')`. Cancelled orders are excluded.
- **Displayed on**: CRM form as a stat button (`action_view_sale_quotation`)

##### `sale_order_count`

```python
sale_order_count = fields.Integer(
    compute='_compute_sale_data',
    string="Number of Sale Orders"
)
```

- **Type**: Integer (computed, not stored)
- **Computation**: Count of `order_ids` filtered by `_get_lead_sale_order_domain()` → `state not in ('draft', 'sent', 'cancel')`
- **Displayed on**: CRM form as a stat button showing total confirmed order revenue

##### `order_ids`

```python
order_ids = fields.One2many(
    'sale.order', 'opportunity_id',
    string='Orders'
)
```

- **Type**: One2many (inverse of `sale.order.opportunity_id`)
- **L3 detail**: Establishes the bidirectional link. A single opportunity can have many sale orders. The back-reference is `opportunity_id` on `sale.order`.
- **Access**: Users need read access on `sale.order` to see these in the CRM form; ACL is controlled by the standard `sale` access rights.

---

#### `_compute_sale_data`

```python
@api.depends(
    'order_ids.state', 'order_ids.currency_id',
    'order_ids.amount_untaxed', 'order_ids.date_order',
    'order_ids.company_id'
)
def _compute_sale_data(self):
    for lead in self:
        company_currency = lead.company_currency or self.env.company.currency_id
        sale_orders = lead.order_ids.filtered_domain(self._get_lead_sale_order_domain())
        lead.sale_amount_total = sum(
            order.currency_id._convert(
                order.amount_untaxed, company_currency,
                order.company_id, order.date_order or fields.Date.today()
            )
            for order in sale_orders
        )
        lead.quotation_count = len(lead.order_ids.filtered_domain(
            self._get_lead_quotation_domain()
        ))
        lead.sale_order_count = len(sale_orders)
```

- **Dependencies**: Triggers on any change to order state, currency, untaxed amount, date, or company — meaning any order create/write/unlink on a linked opportunity recomputes the lead's stats.
- **Performance**: Since `order_ids` can be large, `filtered_domain` iterates all linked orders. For leads with many orders, consider caching or read_group.
- **Currency conversion at historical rate**: Uses `date_order` as the conversion date, meaning the revenue figure reflects the exchange rate at the time the order was placed, not today's rate.
- **Edge case**: If `lead.company_currency` is falsy (lead has no company set), falls back to `self.env.company.currency_id`. This can produce inconsistent figures in multi-company environments if the fallback differs from the lead's actual currency.

---

#### Domain Helper Methods

##### `_get_action_view_sale_quotation_domain`

```python
def _get_action_view_sale_quotation_domain(self):
    return [('state', 'in', ('draft', 'sent', 'cancel'))]
```

Returns domain for **all non-archived quotations** including cancelled ones. Used in `action_view_sale_quotation()`.

##### `_get_lead_quotation_domain`

```python
def _get_lead_quotation_domain(self):
    return [('state', 'in', ('draft', 'sent'))]
```

Returns domain for **active quotations** (draft or sent, not cancelled).

##### `_get_lead_sale_order_domain`

```python
def _get_lead_sale_order_domain(self):
    return [('state', 'not in', ('draft', 'sent', 'cancel'))]
```

Returns domain for **confirmed sale orders** (everything except draft, sent, and cancelled — covers `sale` and `done` states).

> **L3 nuance**: `done` orders are included in `sale_order_count` and `sale_amount_total`. If an order is manually unlocked and returned to `draft` after confirmation, it disappears from both counts and the revenue total.

---

#### Action Methods

##### `action_sale_quotations_new`

```python
def action_sale_quotations_new(self):
    if not self.partner_id:
        return self.env["ir.actions.actions"]._for_xml_id("sale_crm.crm_quotation_partner_action")
    else:
        return self.action_new_quotation()
```

- **Route**: Called by the "New Quotation" button on the CRM form
- **Logic**: If the lead has no partner, opens the `crm.quotation.partner` wizard (see Wizard section). Otherwise, directly calls `action_new_quotation()`.
- **Invisible condition in XML**: `type == 'lead' or probability == 0 and not active` — button only appears on opportunities (not raw leads) and only if the probability is non-zero or the lead is active.

##### `action_new_quotation`

```python
def action_new_quotation(self):
    action = self.env["ir.actions.actions"]._for_xml_id("sale_crm.sale_action_quotations_new")
    action['context'] = self._prepare_opportunity_quotation_context()
    action['context']['search_default_opportunity_id'] = self.id
    return action
```

- Opens the sale quotation form filtered to this opportunity. Passes context with all lead fields pre-populated (partner, campaign, medium, source, origin, tags, team, user, company).

##### `_prepare_opportunity_quotation_context`

```python
def _prepare_opportunity_quotation_context(self):
    self.ensure_one()
    quotation_context = {
        'default_opportunity_id': self.id,
        'default_partner_id': self.partner_id.id,
        'default_campaign_id': self.campaign_id.id,
        'default_medium_id': self.medium_id.id,
        'default_origin': self.name,
        'default_source_id': self.source_id.id,
        'default_company_id': self.company_id.id or self.env.company.id,
        'default_tag_ids': [(6, 0, self.tag_ids.ids)]
    }
    if self.team_id:
        quotation_context['default_team_id'] = self.team_id.id
    if self.user_id:
        quotation_context['default_user_id'] = self.user_id.id
    return quotation_context
```

- **L3 detail**: Pre-populates the new quotation with the lead's UTM fields (campaign, medium, source), making sure marketing attribution flows through to the sale order.
- `default_origin` is set to `self.name` — the lead's name becomes the `origin` field on the sale order, useful for cross-referencing.
- `default_tag_ids` uses `(6, 0, ids)` to replace any existing tags on the draft order with the lead's tags.
- **Edge case**: If `self.company_id` is False, `default_company_id` falls back to `self.env.company.id`. In multi-company setups, the user may see a different company pre-selected than the one the lead belongs to.

##### `action_view_sale_quotation`

```python
def action_view_sale_quotation(self):
    self.ensure_one()
    action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations_with_onboarding")
    action['context'] = self._prepare_opportunity_quotation_context()
    action['context']['search_default_draft'] = 1
    action['domain'] = Domain.AND([
        [('opportunity_id', '=', self.id)],
        self._get_action_view_sale_quotation_domain()
    ])
    # If only 1 quotation, open it in form view
    ...
```

- Returns the quotations list view filtered to this opportunity and non-archived states. Auto-opens form view if exactly one quotation exists.

##### `action_view_sale_order`

```python
def action_view_sale_order(self):
    self.ensure_one()
    action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")
    action['context'] = {
        'search_default_partner_id': self.partner_id.id,
        'default_partner_id': self.partner_id.id,
        'default_opportunity_id': self.id,
    }
    action['domain'] = Domain.AND([
        [('opportunity_id', '=', self.id)],
        self._get_lead_sale_order_domain()
    ])
    # If only 1 order, open it in form view
    ...
```

- Returns the confirmed sale orders list view filtered to this opportunity.

---

#### `_merge_get_fields_specific`

```python
def _merge_get_fields_specific(self):
    fields_info = super(CrmLead, self)._merge_get_fields_specific()
    fields_info['order_ids'] = lambda fname, leads: [(4, order.id) for order in leads.order_ids]
    return fields_info
```

- **L3 detail**: Extends the lead merge operation (CRM's "merge opportunities" feature) to include all sale orders from all leads being merged into the resulting lead record.
- Uses command `(4, order.id)` — equivalent to `link` — to attach each order without modifying or duplicating it.
- **Security note**: When merging opportunities, all their associated sale orders are consolidated under the merge target. If orders from two opportunities go to the same partner, they both remain valid — no automatic partner reassignment occurs here.

---

#### `_update_revenues_from_so`

```python
def _update_revenues_from_so(self, order):
    for opportunity in self:
        if (
            (opportunity.expected_revenue or 0) < order.amount_untaxed
            and order.currency_id == opportunity.company_id.currency_id
        ):
            opportunity.expected_revenue = order.amount_untaxed
            opportunity._track_set_log_message(
                _('Expected revenue has been updated based on the linked Sales Orders.')
            )
```

- **Trigger**: Called from `sale.order.action_confirm()` for each order with a linked opportunity.
- **Condition**: Updates `expected_revenue` only if:
  1. The order's `amount_untaxed` exceeds the current `expected_revenue` (or `expected_revenue` is 0)
  2. The order's currency **exactly matches** the opportunity's company's currency (no conversion)
- **L4 / currency mismatch behavior**: If the order uses a different currency, `expected_revenue` is NOT updated. This is a deliberate design choice — cross-currency orders are not auto-promoted because Odoo 19 does not have exchange-rate awareness for the lead's `expected_revenue` field. This is confirmed by the test: orders in INR do not update a lead whose company is in USD.
- **Logging**: Calls `_track_set_log_message` to append a note to the opportunity's chatter when revenue is auto-updated.
- **Performance**: Called within `action_confirm`, which is already a heavy transaction. The `_track_set_log_message` write is a separate database write. In high-volume confirmation scenarios, this adds one extra `write()` per confirmed order.

---

### `sale.order` — Extensions

File: `~/odoo/odoo19/odoo/addons/sale_crm/models/sale_order.py`

#### Fields Added by sale_crm

##### `opportunity_id`

```python
opportunity_id = fields.Many2one(
    'crm.lead',
    string='Opportunity',
    check_company=True,
    index='btree_not_null',
    domain="[('type', '=', 'opportunity'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]"
)
```

- **Type**: Many2one to `crm.lead`
- **Index**: `btree_not_null` — creates a partial index on all non-null rows. Speeds up queries filtering on confirmed opportunities without penalizing null values.
- **Domain**: Restricts selection to records where `type == 'opportunity'` (not raw leads) and company matches (or the opportunity has no company).
- **check_company**: Enforces inter-record company consistency via Odoo's `check_company_context` mechanism.
- **L3 detail**: This field is **optional** on `sale.order`. A sale order can exist without a linked opportunity. The field enables the back-reference `order_ids` on `crm.lead`.

#### View Injection

In `views/sale_order_views.xml`, `opportunity_id` is injected **after** the `origin` field on the sale order form, with two variants:

```xml
<!-- Salesmen see tag_ids in context -->
<field name="opportunity_id" groups="sales_team.group_sale_salesman" context="{
    'default_tag_ids': tag_ids,
    ...
}"/>
<!-- Non-salesmen (e.g., admin) see no tag_ids -->
<field name="opportunity_id" groups="!sales_team.group_sale_salesman" context="{
    ...
}"/>
```

The tag context is only passed to users in the `sales_team.group_sale_salesman` group.

---

#### `action_confirm` Override

```python
def action_confirm(self):
    res = super(SaleOrder, self.with_context(
        {k: v for k, v in self.env.context.items() if k != 'default_tag_ids'}
    )).action_confirm()
    for order in self:
        order.opportunity_id._update_revenues_from_so(order)
    return res
```

- **Context sanitization**: Before calling `super().action_confirm()`, strips `default_tag_ids` from the context. This prevents tag IDs from leaking into downstream computations (e.g., stock moves) that might incorrectly interpret them.
- **Post-confirmation revenue update**: After each order in `self` is confirmed, calls `_update_revenues_from_so` on its linked opportunity.
- **L4 nuance**: If the order has no `opportunity_id` (`order.opportunity_id` is a recordset of size 0), the call to `_update_revenues_from_so` is a no-op (iterates over empty recordset). No error is raised.
- **Bulk confirmation**: If multiple orders are confirmed in one transaction (e.g., via `action_confirm` on a recordset), each triggers a separate opportunity revenue check. This means a lead's `expected_revenue` can be updated multiple times in one transaction if multiple orders for the same opportunity are confirmed together.
- **Edge case**: Confirmed orders that are later cancelled do **not** automatically reduce `expected_revenue`. Odoo does not reverse the auto-update. The sales manager must manually adjust the `expected_revenue` field.

---

### `crm.team` — Extensions

File: `~/odoo/odoo19/odoo/addons/sale_crm/models/crm_team.py`

#### `_compute_dashboard_button_name`

```python
def _compute_dashboard_button_name(self):
    super(CrmTeam, self)._compute_dashboard_button_name()
    teams_with_opp = self.filtered(lambda team: team.use_opportunities)
    if self.env.context.get('in_sales_app'):
        teams_with_opp.update({'dashboard_button_name': _("Sales Analysis")})
```

- When viewed inside the **Sales app** (`in_sales_app` context is set), and the team has opportunities enabled, the dashboard button label is changed from the inherited CRM label to **"Sales Analysis"**.
- `use_opportunities` is a field on `crm.team` that controls whether the team tracks pipeline opportunities.

#### `action_primary_channel_button`

```python
def action_primary_channel_button(self):
    if self.env.context.get('in_sales_app') and self.use_opportunities:
        return self.env["ir.actions.actions"]._for_xml_id("sale.action_order_report_so_salesteam")
    return super(CrmTeam, self).action_primary_channel_button()
```

- When in the Sales app with opportunities enabled, clicking the dashboard button opens the **Sales Analysis** report (`sale.action_order_report_so_salesteam`), which is a BI-style report showing sales performance by team.
- Falls back to the parent implementation (CRM pipeline view) in all other contexts.

---

## Wizard: `crm.quotation.partner`

File: `~/wizard/crm_opportunity_to_quotation.py`
Model: `crm.quotation.partner` (TransientModel)

### Purpose

Displayed when a lead has no partner and the user clicks "New Quotation". Asks whether to create a partner, use an existing one, or skip linking a partner entirely.

### Fields

#### `action`

```python
action = fields.Selection([
    ('create', 'Create a new customer'),
    ('exist', 'Link to an existing customer'),
    ('nothing', 'Do not link to a customer')
], string='Quotation Customer', required=True)
```

#### `lead_id`

```python
lead_id = fields.Many2one('crm.lead', "Associated Lead", required=True)
```

#### `partner_id`

```python
partner_id = fields.Many2one('res.partner', 'Customer')
```

- Only required/visible when `action == 'exist'`

### `default_get` Logic

```python
@api.model
def default_get(self, fields):
    result = super().default_get(fields)
    active_model = self.env.context.get('active_model')
    if active_model != 'crm.lead':
        raise UserError(_('You can only apply this action from a lead.'))
    lead = False
    if result.get('lead_id'):
        lead = self.env['crm.lead'].browse(result['lead_id'])
    elif 'lead_id' in fields and self.env.context.get('active_id'):
        lead = self.env['crm.lead'].browse(self.env.context['active_id'])
    if lead:
        result['lead_id'] = lead.id
        partner_id = result.get('partner_id') or lead._find_matching_partner().id
        if 'action' in fields and not result.get('action'):
            result['action'] = 'exist' if partner_id else 'create'
        if 'partner_id' in fields and not result.get('partner_id'):
            result['partner_id'] = partner_id
    return result
```

- **L3 detail**: Pre-selects `action` based on whether the lead already has a matching partner found via `lead._find_matching_partner()`. If a match exists, defaults to `'exist'`; otherwise defaults to `'create'`.
- The wizard can also be called with `default_action: 'nothing'` via context to skip partner assignment entirely (used in tests).

### `action_apply`

```python
def action_apply(self):
    self.ensure_one()
    if self.action == 'create':
        self.lead_id._handle_partner_assignment(create_missing=True)
    elif self.action == 'exist':
        self.lead_id._handle_partner_assignment(
            force_partner_id=self.partner_id.id,
            create_missing=False
        )
    return self.lead_id.action_new_quotation()
```

- **Three branches**:
  - `create`: Calls `_handle_partner_assignment(create_missing=True)` — creates a new partner from the lead's contact data, then proceeds to quotation.
  - `exist`: Forces assignment to `self.partner_id`, no creation, then proceeds.
  - `nothing`: Does nothing to partner assignment (no `_handle_partner_assignment` call), proceeds directly to quotation with no partner.
- **Always returns** the result of `self.lead_id.action_new_quotation()`, opening the sale quotation form with the lead's context pre-populated.

---

## Security

### ACL CSV

File: `security/ir.model.access.csv`

```
access_crm_quotation_partner,access.crm.quotation.partner,
  model_crm_quotation_partner,sales_team.group_sale_salesman,1,1,1,0
```

- The wizard `crm.quotation.partner` is accessible only to users in `sales_team.group_sale_salesman`.
- `perm_unlink = 0`: TransientModel records are automatically cleaned up by the Odoo cron job (`ir.cron`), so explicit unlink rights are not needed.
- **No additional ACL** for `crm.lead` or `sale.order` modifications — `sale_crm` relies on the base `crm` and `sale` access rights. Users must have write access on `crm.lead` to set `opportunity_id` on a sale order, and write access on `sale.order` to link/unlink opportunities.

---

## Uninstall Hook

```python
def uninstall_hook(env):
    teams = env['crm.team'].search([('use_opportunities', '=', False)])
    teams.write({'use_opportunities': True})
```

File: `__init__.py`

- When `sale_crm` is uninstalled, any `crm.team` that had `use_opportunities = False` (opportunities feature disabled) will have it re-enabled.
- **Purpose**: `sale_crm`'s UI and code assume opportunities are enabled on teams. If the module is removed, those teams would otherwise show broken or missing buttons in the Sales app dashboard. Re-enabling `use_opportunities` restores the standard CRM pipeline view for those teams.

---

## Data Files

### `data/crm_lead_merge_summary_inherit_sale_crm`

Inherits the QWeb template `crm.crm_lead_merge_summary` (used in the lead merge wizard) to add a **Sale Orders section** to the merge summary:

```xml
<div t-if="lead.order_ids">
    <div class="fw-bold">Sale Orders</div>
    <ul>
        <li t-foreach="lead.order_ids" t-as="order" t-esc="order.name"/>
    </ul>
</div>
```

- Lists the names of all sale orders linked to the lead being merged. Allows the user to see the downstream impact before merging.

### View Modifications

#### CRM Lead Form (`crm_lead_views.xml`)

| Element | Change | Detail |
|---|---|---|
| `New Quotation` button | Inserted before `action_set_won_rainbowman` | Visible only for opportunities (`type == 'lead'` is False) and non-zero probability or active leads |
| `action_set_won_rainbowman` button | Removed `oe_highlight` class | Deprioritized visually; New Quotation becomes the primary action |
| `action_schedule_meeting` button | Stat button added after | Shows `quotation_count` with `fa-pencil-square-o` icon |
| Stat button for orders | Added after meeting button | Shows `sale_amount_total` monetary widget + `sale_order_count`; only visible when `sale_order_count > 0` and `type != 'lead'` |

#### Sale Order Form (`sale_order_views.xml`)

| Element | Change |
|---|---|
| `opportunity_id` field | Injected after `origin` field |
| `crm.crm_lead_opportunities` action | Added `needaction_menu_ref` context (quotation notification badge) |
| `mail_activity_type_action_config_sales` action | Extended domain to include `sale.order` as an activity host model |
| `sale_order_menu_quotations_crm` menu | New menu item under `crm.crm_menu_sales` → "My Quotations" linking to `sale.action_quotations` |

---

## Cross-Module Integration Map

```
crm_lead_merge_summary (QWeb template)
        ↑ inherits
crm_lead_views.xml ──stat buttons──→ sale_amount_total, quotation_count, sale_order_count
                                      action_sale_quotations_new ──wizard──→ crm.quotation.partner
                                                                         ├── create_missing=True  → creates res.partner from lead
                                                                         └── force_partner_id    → links existing res.partner
                                                                              └── action_new_quotation() → sale.order (pre-populated)

sale_order_views.xml ──opportunity_id──→ crm.lead (via _prepare_opportunity_quotation_context)
action_confirm ──→ _update_revenues_from_so ──→ crm.lead.expected_revenue + _track_set_log_message

crm_team ──dashboard button──→ sale.action_order_report_so_salesteam (Sales Analysis report)
```

---

## Edge Cases and Failure Modes

| Scenario | Behavior |
|---|---|
| Lead has no partner, user clicks "New Quotation" | Opens `crm.quotation.partner` wizard instead of directly creating a quotation |
| Sale order confirmed with different-currency than lead's company | `expected_revenue` is NOT updated (strict currency equality check) |
| Confirmed order later cancelled | `expected_revenue` remains at the elevated value; must be manually adjusted |
| Order linked to opportunity, then `opportunity_id` cleared | `sale_amount_total` and counts recompute; `expected_revenue` is NOT reset |
| Lead merged with another lead | All `order_ids` from both leads are consolidated on the merge target via `(4, id)` commands |
| User without `group_sale_salesman` edits a sale order | `opportunity_id` field visible but context does not include `default_tag_ids` |
| `sale_crm` uninstalled | `use_opportunities` re-enabled on teams where it was False; all other data (orders, leads, links) preserved |
| Opportunity with no `company_id` linked to multi-company order | Currency fallback uses `self.env.company.currency_id` in `_compute_sale_data` |

---

## Odoo 18 → 19 Changes

No significant behavioral changes to `sale_crm` were introduced in the Odoo 18→19 transition. The module's implementation is stable across versions.

- Module version: `1.0` (unchanged)
- Auto-install: `True`
- No deprecations or removals noted in the Odoo 19 changelog for this module

---

## Related

- [Modules/sale](Modules/sale.md) — Core sale order module (`sale.order`, quotation lifecycle)
- [Modules/crm](Modules/crm.md) — Core CRM module (`crm.lead`, lead/opportunity lifecycle, merge logic)
- [Modules/sales_team](Modules/sales_team.md) — CRM sales team module (contains `crm.team` base model)
