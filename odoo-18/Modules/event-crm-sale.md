---
Module: event_crm_sale
Version: Odoo 18
Type: Integration
Tags: #odoo #odoo18 #event #crm #sale #leads
---

# event_crm_sale — Event CRM Sale Integration

**Module:** `event_crm_sale`
**Addon Path:** `odoo/addons/event_crm_sale/`
**Depends:** `event_crm`, `event_sale`
**Category:** Marketing/Events
**Auto-install:** Yes
**License:** LGPL-3

Bridges event registration data with the CRM lead engine when registrations originate from a sale order. It extends the lead grouping logic in `event.registration._get_lead_grouping()` so that leads can be grouped by `sale_order_id` (not just by event + create_date), enabling a single lead to aggregate all registrations from one sale order.

---

## Architecture

```
event
  event.registration    — attendee records
  event.lead.rule       — rule: when/how to create leads from registrations

event_sale
  event.registration    + sale_order_id, sale_order_line_id, sale_status
  sale.order.line        + event_id, event_ticket_id, registration_ids

event_crm
  crm.lead               + event_lead_rule_id, event_id, registration_ids[]
  event.registration     + lead_ids[], lead_count
  event.lead.rule        — lead_creation_basis: 'attendee' (per-reg) | 'order' (per-group)

event_crm_sale (THIS MODULE)
  event.registration     + _get_lead_grouping() override for sale_order-based grouping
  event.lead.rule        + XML: show 'Per Order' basis in UI (already supported in model)
```

---

## Full Dependency Tree

```
event
  └─ event.registration
        └─ event.mail / event.mail.registration
        └─ event.event / event.event.ticket
        └─ event.type.mail

event_sale
  └─ event.registration (extends)
        ├─ sale_order_id ──────────────────────── Many2one → sale.order
        ├─ sale_order_line_id ─────────────────── Many2one → sale.order.line
        ├─ sale_status (to_pay/sold/free)
        └─ _synchronize_so_line_values()
  └─ sale.order.line (extends)
        ├─ event_id
        ├─ event_ticket_id
        └─ registration_ids → event.registration

event_crm
  └─ event.registration (extends)
        ├─ lead_ids[] ─────────────────────────── Many2many → crm.lead
        └─ lead_count
        └─ _get_lead_grouping() ───────────────── core grouping by event+create_date
        └─ _apply_lead_generation_rules()
  └─ crm.lead (extends)
        ├─ event_lead_rule_id ─────────────────── Many2one → event.lead.rule
        ├─ event_id ───────────────────────────── Many2one → event.event
        └─ registration_ids[] ─────────────────── Many2many → event.registration
  └─ event.lead.rule
        ├─ lead_creation_basis ───────────────── Selection: 'attendee' | 'order'
        ├─ lead_creation_trigger ──────────────── Selection: 'create' | 'confirm' | 'done'
        └─ _run_on_registrations()

event_crm_sale (THIS MODULE)
  └─ event.registration (extends)
        └─ _get_lead_grouping() ───────────────── EXTENDS: sale_order-based grouping
```

---

## Model Extended: `event.registration` (EXTENDED)

Inherits from `event.registration` via `event_crm/models/event_registration.py`, which extends the base `event` registration model.

### Fields Already Present (from event_sale)

| Field | Type | Description |
|-------|------|-------------|
| `sale_order_id` | Many2one `sale.order` | The sales order this registration is attached to. Ondelete: `cascade`. |
| `sale_order_line_id` | Many2one `sale.order.line` | The specific SO line. Ondelete: `cascade`. |
| `sale_status` | Selection | `to_pay` / `sold` / `free`. Computed from `sale_order_id.state` and `amount_total`. |
| `utm_campaign_id` | Many2one | Synchronized from `sale_order_id.campaign_id`. |
| `utm_source_id` | Many2one | Synchronized from `sale_order_id.source_id`. |
| `utm_medium_id` | Many2one | Synchronized from `sale_order_id.medium_id`. |

### Fields Already Present (from event_crm)

| Field | Type | Description |
|-------|------|-------------|
| `lead_ids` | Many2many `crm.lead` | All leads generated from this registration. |
| `lead_count` | Integer | `# Leads`. `compute_sudo=True`. |

### Method Extended: `_get_lead_grouping()`

This is the central method overridden by `event_crm_sale`. It changes how registrations are grouped for **order-based lead creation rules**.

#### Parent Implementation (event_crm)

The parent `event.registration._get_lead_grouping()` groups registrations by `(create_date, event)`:

```python
# event_crm/models/event_registration.py
def _get_lead_grouping(self, rules, rule_to_new_regs):
    grouped_registrations = {
        (create_date, event): sub_registrations
        for event, registrations in self.grouped('event_id').items()
        for create_date, sub_registrations in registrations.grouped('create_date').items()
    }
    return dict(
        (rule, [(False, key, (registrations & rule_to_new_regs[rule]).sorted('id'))
                for key, registrations in grouped_registrations.items()])
        for rule in rules
    )
```

Returns tuples of `(existing_lead, group_key, registrations)` where:
- `existing_lead` is always `False` (no update, all new)
- `group_key` is `(create_date, event_id)`
- Registrations are grouped by event and creation timestamp

#### Extended Implementation (event_crm_sale)

```python
def _get_lead_grouping(self, rules, rule_to_new_regs):
    so_registrations = self.filtered(lambda reg: reg.sale_order_id)
    grouping_res = super(EventRegistration, self - so_registrations)._get_lead_grouping(rules, rule_to_new_regs)

    if so_registrations:
        # Batch-fetch related leads in one query to populate cache
        related_registrations = self.env['event.registration'].search([
            ('sale_order_id', 'in', so_registrations.sale_order_id.ids)
        ])
        related_leads = self.env['crm.lead'].search([
            ('event_lead_rule_id', 'in', rules.ids),
            ('registration_ids', 'in', related_registrations.ids)
        ])

        for rule in rules:
            rule_new_regs = rule_to_new_regs[rule]

            # Group registrations by sale_order
            so_to_regs = defaultdict(lambda: self.env['event.registration'])
            for registration in rule_new_regs & so_registrations:
                so_to_regs[registration.sale_order_id] |= registration

            # For each group, find existing lead + prepare result
            so_res = []
            for sale_order, registrations in so_to_regs.items():
                registrations = registrations.sorted('id')  # re-sort after OR composition
                # Find existing lead for this (sale_order, rule) combination
                leads = related_leads.filtered(
                    lambda lead: lead.event_lead_rule_id == rule
                    and lead.registration_ids.sale_order_id == sale_order
                )
                so_res.append((leads, sale_order, registrations))
            if so_res:
                grouping_res[rule] = grouping_res.get(rule, list()) + so_res

    return grouping_res
```

**Purpose**: For registrations that have a `sale_order_id`:
1. Groups them by `sale_order_id` instead of by `(create_date, event_id)`
2. **Looks up existing leads** linked to the same sale order and the same rule (enables lead **update** instead of duplicate creation)
3. Returns `(existing_lead, sale_order, registrations)` tuples for each sale order

**Why batch-fetch**: `self - so_registrations` passes non-SO registrations to the parent for normal grouping. The `related_registrations` and `related_leads` batch lookups populate the ORM cache so subsequent `filtered()` calls on `related_leads` are fast (no N+1).

**Impact on lead creation**: When `event.lead.rule._run_on_registrations()` processes the grouping result and finds a non-empty `existing_lead`, it calls `lead.write()` (update) instead of `crm.lead.create()` (new). This means:
- First registration on an SO → creates a new lead
- Subsequent registrations on the same SO → update the existing lead with additional registration info

---

## Model Extended: `event.lead.rule` — UI Visibility Only

**File:** `views/event_lead_rule_views.xml`

The model `event.lead.rule` (from `event_crm`) already supports `lead_creation_basis = 'order'`. The `event_crm_sale` views simply ensure the "Per Order" option is always visible in the UI:

### XML Changes

**`event_lead_rule_view_tree`** (list view):
- Removes `column_invisible="True"` from `lead_creation_basis` field (it was invisible by default in base `event_crm`)

**`event_lead_rule_view_form`** (form view):
- Removes `invisible="1"` from `group[@name='lead_creation_basis']` (the field group was hidden by default in base `event_crm`)

### The "Per Order" Basis Explained

When `lead_creation_basis = 'order'`:
- All registrations from the same `sale_order_id` are grouped into a **single lead**
- The lead's `partner_id` is the SO's `partner_id`
- The lead's `description` lists all attendees from the SO
- If the SO already has a lead from a previous registration, subsequent registrations update that lead instead of creating a new one (via `_get_lead_grouping` override)

---

## How Leads Are Created: Full Flow

```
1. Registration created (event_sale: from SO line)
   └─ event.registration.create()
         └─ event_crm: _apply_lead_generation_rules()
               └─ event_crm_sale: _get_lead_grouping()
                     ├─ Registrations WITH sale_order_id → grouped by sale_order_id
                     │     └─ Existing lead found? → UPDATE lead
                     │     └─ No existing lead? → CREATE new lead
                     └─ Registrations WITHOUT sale_order_id → grouped by (create_date, event)
                           └─ CREATE new lead per group
```

### Registration → Lead Value Mapping

`event.registration._get_lead_values(rule)` (from `event_crm`) populates lead values:

```python
lead_values = {
    'type': rule.lead_type,
    'user_id': rule.lead_user_id.id,
    'team_id': rule.lead_sales_team_id.id,
    'tag_ids': rule.lead_tag_ids.ids,
    'event_lead_rule_id': rule.id,
    'event_id': self.event_id.id,
    'referred': self.event_id.name,
    'registration_ids': self.ids,
    'campaign_id': self._find_first_notnull('utm_campaign_id'),
    'source_id': self._find_first_notnull('utm_source_id'),
    'medium_id': self._find_first_notnull('utm_medium_id'),
}
lead_values.update(self._get_lead_contact_values())
```

For order-based leads, `_get_lead_contact_values()` picks up `sale_order_id.partner_id` as the primary contact.

---

## L4: How Order-Based Lead Aggregation Works

### The `rule_to_new_regs` Dictionary

Passed by `_run_on_registrations()`: `{rule: registrations_matching_rule}`. Each rule gets its subset of registrations.

### Sale Order Grouping Advantage

The key difference between `attendee` and `order` grouping:

| Aspect | Per Attendee | Per Order (with event_crm_sale) |
|--------|-------------|----------------------------------|
| Grouping key | `(create_date, event_id)` | `sale_order_id` |
| Lead per SO | Many (one per registration) | One (all registrations together) |
| Partner | Registration-specific | SO-level partner |
| Use case | B2C events, individual tickets | B2B events, group tickets |

### Existing Lead Update Logic

In `event.lead.rule._run_on_registrations()`:

```python
for (toupdate_leads, group_key, group_registrations) in rule_group_info[rule]:
    if toupdate_leads:
        additionnal_description = group_registrations._get_lead_description(_("New registrations"), line_counter=True)
        for lead in toupdate_leads:
            lead.write({
                'description': "%s<br/>%s" % (lead.description, additionnal_description),
                'registration_ids': [(4, reg.id) for reg in group_registrations],
            })
    elif group_registrations:
        lead_vals_list.append(group_registrations._get_lead_values(rule))
```

- If `toupdate_leads` exists (from `event_crm_sale`'s grouping): appends new registrations to existing lead's description and `registration_ids`
- Otherwise: creates a new lead

### Synchronization on Registration Updates

When a registration is updated (e.g., partner change), `event.registration.write()` calls `_update_leads()`:

```python
# event_crm/models/event_registration.py
leads_order = registration.lead_ids.filtered(
    lambda lead: lead.event_lead_rule_id.lead_creation_basis == 'order'
)
for lead in leads_order:
    if new_vals.get('partner_id'):
        lead_values.update(lead.registration_ids._get_lead_contact_values())
        if new_vals['partner_id'] != lead.partner_id.id:
            lead_values['description'] = (lead.description or '') + "<br/>" + ...
    if lead_values:
        lead.write(lead_values)
```

For order-based leads, only a `partner_id` change triggers a full contact and description update. This preserves the lead while reflecting the latest registration data.

---

## See Also

- [Modules/CRM](CRM.md) — crm.lead model, lead pipeline
- [Core/API](API.md) — @api.depends, @api.onchange, @api.constrains
- `event_crm` — base event-to-lead automation
- `event_sale` — sale order integration for event registrations
