---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #event
  - #crm
  - #sale
---

# Event CRM Sale (`event_crm_sale`)

## Module Overview

| Attribute | Value |
|-----------|-------|
| **Technical Name** | `event_crm_sale` |
| **Category** | Marketing/Events |
| **Version** | 1.0 |
| **Depends** | `event_crm`, `event_sale` |
| **Auto-install** | `True` — activates automatically when both dependencies are present |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

**Purpose**: Extends `event_crm`'s lead generation rules to support **order-based grouping** for registrations linked to a sale order. When registrations share the same `sale_order_id` (e.g., multiple attendees registered via one ticket purchase), the module ensures they are grouped into a single lead — one lead per sale order per rule — rather than generating one lead per attendee.

**Why it exists**: `event_crm` alone groups registrations by `(event, create_date)` — adequate for website-driven B2C event registration. However, when `event_sale` is installed, a single `sale.order` can include multiple ticket lines for different attendees, each creating its own `event.registration` record. The `event_crm_sale` module modifies the grouping key so that all registrations tied to the same sales order are consolidated into one lead, which is the expected B2B behavior: one lead per client purchase.

---

## File Structure

```
event_crm_sale/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── event_registration.py   # Core: _get_lead_grouping override
└── views/
    └── event_lead_rule_views.xml  # Form/tree view overrides
```

**Note**: There is no `demo/` directory — the module relies entirely on demo data from its dependencies (`event_crm` and `event_sale`).

---

## L1: Module Dependency Graph

```
event_crm_sale
├── event_crm        (event.registration + crm.lead lead generation rules)
│   └── crm          (crm.lead, sales_team)
│   └── event        (event.event, event.registration base model)
└── event_sale       (sale.order linking, sale_order_id on event.registration)
    └── sale         (sale.order, sale.order.line, UTM fields)
    └── event        (event base models)
```

**Dependency chain depth**:
- `event_crm_sale` → `event_crm` → `event` + `crm`
- `event_crm_sale` → `event_sale` → `sale` + `event`

**What each dependency contributes**:

| Dependency | Contribution |
|-----------|-------------|
| `crm` | `crm.lead` model — target for created leads |
| `event` | `event.registration` base model — the model being extended |
| `event_crm` | `event.lead.rule`, `event.registration._get_lead_grouping()`, lead generation logic |
| `sale` | `sale.order` and UTM fields (`source_id`, `campaign_id`, `medium_id`) on SO |
| `event_sale` | `event.registration.sale_order_id`, `sale_order_line_id` fields |

**Auto-install behavior**: Because `auto_install: True`, the module activates as soon as both `event_crm` and `event_sale` are installed. The `sale` module is a transitive dependency — it is pulled in by `event_sale` — so no separate `sale` check is needed.

---

## L2: Field Types, Defaults, Constraints

### `event.registration` — Fields Inherited from `event_sale`

The module operates on fields already defined by `event_sale` on `event.registration`. No new fields are defined by `event_crm_sale` itself.

#### `sale_order_id` — `fields.Many2one('sale.order')`

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` |
| **Target** | `sale.order` |
| **Ondelete** | `cascade` |
| **Copy** | `False` |
| **Source** | Defined in `event_sale/models/event_registration.py` |

Set when a registration is created from a sale order line (`sale.order.line` with an event ticket). The `sale_order_id` links the registration back to the purchase that generated it. Multiple registrations can share the same `sale_order_id` if the SO has multiple ticket lines.

#### `sale_order_line_id` — `fields.Many2one('sale.order.line')`

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` |
| **Target** | `sale.order.line` |
| **Ondelete** | `cascade` |
| **Index** | `btree_not_null` (composite index where `sale_order_line_id` IS NOT NULL) |
| **Source** | Defined in `event_sale/models/event_registration.py` |

Links to the specific order line (ticket) that generated this registration.

#### `state` — `fields.Selection` with compute + precompute

| Attribute | Value |
|-----------|-------|
| **Type** | `Selection` (computed, stored, precomputed) |
| **Source** | Defined in `event_sale/models/event_registration.py` |
| **Compute** | `_compute_registration_status` |
| **Decorators** | `@api.depends('sale_order_id.state', 'sale_order_id.currency_id', 'sale_order_id.amount_total')` |

The `event_sale` override derives the registration state from the sale order state:
- If SO is `cancel` → registration state → `cancel`
- If SO is `sale` and amount > 0 → state → `open`, `sale_status` → `sold`
- If SO is `sale` and amount = 0 → state → `open`, `sale_status` → `free`
- If SO is not yet confirmed → state → `draft`, `sale_status` → `to_pay`

#### UTM Fields (computed, stored)

| Field | Compute | Derives from |
|-------|---------|-------------|
| `utm_campaign_id` | `_compute_utm_campaign_id` | `sale_order_id.campaign_id` |
| `utm_source_id` | `_compute_utm_source_id` | `sale_order_id.source_id` |
| `utm_medium_id` | `_compute_utm_medium_id` | `sale_order_id.medium_id` |

These fields propagate UTM attribution from the sale order to the registration, and from there to the generated lead.

#### `_has_order()` — Method Extension

In `event_sale`, the method returns `True` if the registration has a sale order:
```python
def _has_order(self):
    return super()._has_order() or self.sale_order_id
```
`event_crm_sale` does not override this method.

### `event.lead.rule` — Fields Referenced

| Field | Type | Role in this module |
|-------|------|--------------------|
| `lead_creation_basis` | `Selection([('attendee', 'Per Attendee'), ('order', 'Per Order')])` | Controls whether `event_crm_sale`'s order-based grouping is used |
| `event_lead_rule_id` | `Many2one` on `crm.lead` | Links lead back to the rule that created it |

---

## L3: Cross-Model Integration, Override Patterns, Workflow Triggers

### Cross-Model Data Flow

```
crm.lead (created by event.lead.rule)
    │
    ├── registration_ids ──────────────→ event.registration (many2many)
    │      ├── sale_order_id ────────────→ sale.order (via event_sale)
    │      │      ├── campaign_id ─────────→ utm.campaign
    │      │      ├── source_id ────────────→ utm.source
    │      │      ├── partner_id ───────────→ res.partner
    │      │      └── order_line ───────────→ sale.order.line
    │      │             └── event_ticket_id → event.event.ticket
    │      └── event_id ─────────────────→ event.event
    │
    ├── event_lead_rule_id ────────────→ event.lead.rule
    │      └── lead_creation_basis = 'order' (enables sale-order grouping)
    │
    ├── type ────────────────────────── 'lead' or 'opportunity'
    ├── user_id ──────────────────────── from rule.lead_user_id
    ├── team_id ───────────────────────── from rule.lead_sales_team_id
    └── referred ──────────────────────── event.event.name

event.registration
    ├── sale_order_id ──────────────────→ sale.order
    │      (propagates UTM: campaign_id, source_id, medium_id)
    ├── sale_order_line_id ───────────────→ sale.order.line
    │      (event_id, event_slot_id, event_ticket_id from the line)
    └── utm_* fields (computed from sale_order_id)
```

### Override Pattern: `_get_lead_grouping()`

This is the sole Python override in the module. It extends the base grouping logic defined in `event_crm/models/event_registration.py`.

**Base method** (`event_crm`):
```python
def _get_lead_grouping(self, rules, rule_to_new_regs):
    # Groups registrations by (create_date, event_id)
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
Returns `(existing_lead, group_key, registrations)` tuples where `group_key` is `(create_date, event)`.

**`event_crm_sale` override**:
```python
def _get_lead_grouping(self, rules, rule_to_new_regs):
    so_registrations = self.filtered(lambda reg: reg.sale_order_id)
    grouping_res = super(EventRegistration, self - so_registrations)._get_lead_grouping(rules, rule_to_new_regs)

    if so_registrations:
        related_registrations = self.env['event.registration'].search([
            ('sale_order_id', 'in', so_registrations.sale_order_id.ids)
        ])
        related_leads = self.env['crm.lead'].search([
            ('event_lead_rule_id', 'in', rules.ids),
            ('registration_ids', 'in', related_registrations.ids)
        ])

        for rule in rules:
            rule_new_regs = rule_to_new_regs[rule]
            so_to_regs = defaultdict(lambda: self.env['event.registration'])
            for registration in rule_new_regs & so_registrations:
                so_to_regs[registration.sale_order_id] |= registration

            so_res = []
            for sale_order, registrations in so_to_regs.items():
                registrations = registrations.sorted('id')
                leads = related_leads.filtered(
                    lambda lead: lead.event_lead_rule_id == rule
                    and lead.registration_ids.sale_order_id == sale_order
                )
                so_res.append((leads, sale_order, registrations))
            if so_res:
                grouping_res[rule] = grouping_res.get(rule, list()) + so_res

    return grouping_res
```

**Step-by-step trace**:

| Step | Action | What it does |
|------|--------|--------------|
| 1 | `so_registrations = self.filtered(lambda reg: reg.sale_order_id)` | Splits out registrations that came from a sale order |
| 2 | `super()._get_lead_grouping(...)` for `self - so_registrations` | Calls base grouping for non-sale registrations (grouped by event/date as usual) |
| 3 | `search([('sale_order_id', 'in', ...)])` | Loads ALL registrations sharing any of the same SOs — batch query, not per-registration |
| 4 | `search([('event_lead_rule_id', 'in', ...), ...])` | Loads ALL existing leads for those registrations and rules — one query, not per-rule |
| 5 | `so_to_regs = defaultdict` | Groups the new registrations for this rule by their `sale_order_id` |
| 6 | `for sale_order, registrations in so_to_regs.items()` | Iterates groups |
| 7 | `filtered(...)` | Finds existing lead for this rule + this SO — the update target |
| 8 | Appends `(existing_lead, sale_order, registrations)` to `so_res` | Adds sale-order groups to the result |
| 9 | `grouping_res[rule] = grouping_res.get(rule, []) + so_res` | Merges with base grouping result |

**Grouping key difference**: In the base method, the group key is `(create_date, event)`. In the sale-order override, the group key is the `sale.order` record itself. This is the critical distinction — grouping by SO rather than by event/date.

### Workflow Triggers

| Trigger | Action | Model affected |
|---------|--------|----------------|
| Registration created from SO line | `_synchronize_so_line_values()` from `event_sale` populates `sale_order_id`, `sale_order_line_id`, event fields | `event.registration` |
| SO state → `sale` (confirmed) | `_compute_registration_status()` sets `state = 'open'` | `event.registration` |
| SO state → `cancel` | `_compute_registration_status()` sets `state = 'cancel'` | `event.registration` |
| `event_lead_rule._run_on_registrations()` called | Invokes `_get_lead_grouping()` → if `lead_creation_basis == 'order'`, groups by SO | `event.registration` + `crm.lead` |
| New registrations with same SO and same rule | Existing lead is updated (description appended, `registration_ids` expanded) | `crm.lead` |
| Lead already exists for this rule + SO | Lead is updated, not duplicated | `crm.lead` |
| Rule with `lead_creation_basis == 'attendee'` runs | Base grouping (event/date) is used — `event_crm_sale` does not affect attendee-mode rules | `event.registration` |

### View Overrides

The single XML file contains two view overrides:

#### Tree view — `event_lead_rule_view_tree`

```xml
<xpath expr="//field[@name='lead_creation_basis']" position="attributes">
    <attribute name="column_invisible">False</attribute>
</xpath>
```

In the base `event_crm` tree view, `lead_creation_basis` is set to `column_invisible="True"` (hidden by default). This override makes it visible in the tree list view, so users can see at a glance whether rules are configured as Per Attendee or Per Order.

#### Form view — `event_lead_rule_view_form`

```xml
<xpath expr="//group[@name='lead_creation_basis']" position="attributes">
    <attribute name="invisible">0</attribute>
</xpath>
```

In the base `event_crm` form view, the `lead_creation_basis` group (`group[@name='lead_creation_basis']`) is set to `invisible="True"`. This override reveals the group in the form view, allowing users to switch between Per Attendee and Per Order modes. Without this override, the form would be broken for users trying to configure order-based rules — they would see no UI for the field.

---

## L4: Odoo 18 → 19 Version Changes

### No Core API Changes

`event_crm_sale` does not introduce any new fields or change field signatures in Odoo 19. The module structure and the `_get_lead_grouping` override are identical between Odoo 18 and Odoo 19.

### Changes in Supporting Modules (Odoo 18 → 19)

The module's behavior is shaped by changes in its dependencies:

#### `event_sale` — `event.registration.sale_order_id`

In **Odoo 18**, `event_sale` defined `sale_order_id` as a plain stored Many2one. In **Odoo 19**, `event_sale` redefined it as a computed-stored field with a precompute mechanism (`precompute=True`) on the `state` field and used a more sophisticated `_compute_registration_status()` that handles:

- `sale_status` field (`free`, `sold`, `to_pay`) — a new field in Odoo 19
- The `sale_status` is used in the registration summary and determines whether a registration is billable
- The `_compute_field_value()` override on the `state` field triggers `_update_mail_schedulers()` when confirmed

These Odoo 19-specific enhancements on `event_sale` are automatically inherited by `event_crm_sale` through the inheritance chain.

#### `event_crm` — `_get_lead_grouping()` signature

The base method signature (`rules`, `rule_to_new_regs`) is unchanged between Odoo 18 and 19. However, the `rule_to_new_regs` dict structure may have changed slightly as a result of the `event.registration` create/write pipeline changes in Odoo 19.

#### `event_crm` — `event_lead_rule` model

The `lead_creation_basis` field and its `column_invisible="True"` / `invisible="True"` hiding in views is a pattern that existed in Odoo 18. The view overrides in `event_crm_sale` (making the field visible) are identical in both versions.

### What Changed in Odoo 19's `event_crm` That Affects This Module

| Feature | Odoo 18 | Odoo 19 | Impact on `event_crm_sale` |
|---------|---------|---------|---------------------------|
| `event.registration.lead_ids` | Not present | New `Many2many` field | `event_crm_sale` does not use it directly |
| `event_lead_rule.lead_creation_trigger` | `create`, `confirm`, `done` | Same | No change |
| `event_lead_rule.lead_creation_basis` | `attendee`, `order` | Same | No change |
| `_get_lead_grouping()` call site | Called directly from `_apply_lead_generation_rules()` | Same | Compatible |
| `_update_leads()` for order-based leads | Basic implementation | Enhanced with registration description appending | Compatible — `event_crm_sale` adds to the grouping result |

### Summary

The module requires no code changes between Odoo 18 and 19. Its L4 behavior is stable: the override adds sale-order grouping when registrations share a `sale_order_id`, and the two view overrides expose the `lead_creation_basis` field that was intentionally hidden in the base `event_crm` module.

---

## Security Considerations

| Operation | Access | Mechanism |
|-----------|--------|-----------|
| `_get_lead_grouping()` on non-sale registrations | Base method ACL | Base method respects standard record rules |
| `search([('sale_order_id', 'in', ...)])` for related registrations | `.sudo()` not used — respects ACLs | Users can only see registrations they have access to |
| `search([('event_lead_rule_id', 'in', ...), ...])` for related leads | Standard search | Lead visibility controlled by `sales_team.group_sale_salesman` |
| `crm.lead` creation | Via `rule._run_on_registrations()` which calls `.sudo()` | Lead creation runs as superuser (defined in `event_crm`) |
| `crm.lead` update (existing lead) | Same `.sudo()` | Updates run as superuser |

**Key insight**: Unlike `mass_mailing_sale` (which uses `.sudo()` for statistical aggregations), `event_crm_sale`'s `_get_lead_grouping` does not call `.sudo()` for its searches. This means it respects ACLs on `event.registration` and `crm.lead`. Only the actual lead creation/update (`_run_on_registrations()`) in `event_crm` uses `.sudo()`, which is the appropriate pattern: group with ACLs, create/update with elevated privileges.

**Missing registration visibility risk**: If a user lacks access to some registrations linked to a sale order, those registrations are excluded from the grouping query. This means the lead might not include all attendees from the order — a potential data completeness issue in multi-company setups.

---

## Performance Notes

- **Batch query for related registrations** (line 24–26): `self.env['event.registration'].search([('sale_order_id', 'in', ...)]` runs ONE query to load ALL registrations with any of the SOs in `so_registrations.sale_order_id.ids`. This is far more efficient than querying per registration or per SO.
- **Batch query for related leads** (line 27–30): Similarly, all relevant existing leads are loaded in one query.
- **`defaultdict(lambda: self.env[...]`)** pattern (line 36): Avoids per-group initialization overhead for empty groups.
- **No `.sudo()` in searches**: No ACL bypass overhead.
- **`filtered().sorted('id')`** ensures deterministic ordering when merging with the base grouping result (which also sorts by `id`).

---

## Edge Cases and Failure Modes

| Scenario | Behavior | Mitigation |
|----------|----------|-----------|
| Registration with no `sale_order_id` | Base grouping used (event/date) — `event_crm_sale` ignores it | Expected; not a failure |
| Registration with `sale_order_id` but rule has `lead_creation_basis == 'attendee'` | Base grouping used — `event_crm_sale` does not affect attendee-mode rules | Expected; use Per Order basis to activate this module's grouping |
| `sale.order` deleted after registrations are created | `sale_order_id` becomes a deleted (browse) record; `event_crm_sale` filtering (`reg.sale_order_id`) may raise or behave unexpectedly | Cascade delete on `sale_order_id` (`ondelete='cascade'`) means registrations are also deleted if the SO is deleted — no orphaned records |
| Multiple rules with `lead_creation_basis == 'order'` matching the same registrations | Each rule's `grouping_res[rule]` is populated separately; each rule creates or updates its own lead per SO | This is intentional — different rules can create different leads for the same SO (e.g., one for sales team A, one for sales team B) |
| Existing lead found but belongs to a different SO | The `filtered()` on `lead.registration_ids.sale_order_id == sale_order` correctly excludes it | Expected — leads are scoped to their grouping key |
| `registration_ids` on lead: new registrations added to existing lead | `_run_on_registrations()` appends the new registrations to the existing lead's `registration_ids` via `[(4, reg.id)]` | Correct behavior — all registrations for that SO are linked to the same lead |
| SO has 100 attendees (100 registrations) | Single lead created or updated for the SO; description grows with each rule run | For very large groups, the lead description can become very long. Consider using Per Attendee basis for very large orders. |
| Rule with `lead_creation_basis == 'order'` but no SO-linked registrations | Base grouping runs; `so_to_regs` is empty; no sale-order groups added | Expected — the module only activates when registrations have `sale_order_id` |
| `event_crm` not installed | Module cannot install (depends on `event_crm`) | Required dependency — both `event_crm` and `event_sale` must be installed |

---

## Demo Data

The module has no `demo/` directory. It relies on demo data from:
- `event_crm`: demo lead rules and registrations
- `event_sale`: demo sale orders with event tickets

These demo records exercise the full pipeline: SO created → registration linked to SO → lead generation rule runs → lead created per SO.

---

## Tags

`#event_crm_sale` `#sale_order_grouping` `#event_lead_rule` `#per_order_lead` `#event_registration` `#crm_lead` `#event_sale`
