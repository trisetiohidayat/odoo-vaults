---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #mass_mailing
  - #sale
  - #utm
---

# Mass Mailing on Sale Orders (`mass_mailing_sale`)

## Module Overview

| Attribute | Value |
|-----------|-------|
| **Technical Name** | `mass_mailing_sale` |
| **Category** | Marketing/Email Marketing |
| **Version** | 1.0 |
| **Depends** | `sale`, `mass_mailing` |
| **Auto-install** | `True` — activates automatically when both dependencies are present |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

**Purpose**: Bridges the gap between email marketing campaigns and the sale order pipeline by surfacing sale KPIs directly on `mailing.mailing` records and enabling `sale.order` as a valid mass mailing target. Also extends UTM campaign A/B testing with revenue-based winner selection criteria.

**Why it exists**: Without this module, `sale.order` cannot be selected as a mass mailing target, and even if a campaign is sent via another model (e.g., `res.partner`), the attribution back to sale orders and invoices is not visible on the mailing record itself. This module closes that loop by linking the mailing's `source_id` (UTM) to downstream sale and invoice records.

---

## File Structure

```
mass_mailing_sale/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── mailing_mailing.py      # Core extension of mailing.mailing
│   ├── sale_order.py           # Enables sale.order as mailing target
│   └── utm.py                  # Extends utm.campaign A/B testing options
├── views/
│   └── mailing_mailing_views.xml  # Form view stat buttons
└── demo/
    └── mailing_mailing.xml        # Demo mailing record
```

---

## L1: Module Dependency Graph

```
mass_mailing_sale
├── sale              (sale.order, sale.order.line, UTM fields)
└── mass_mailing      (mailing.mailing, utm.source, utm.campaign, utm.medium)
         │
         ├── utm               (utm.campaign, utm.source, utm.medium)
         ├── mass_mailing       (mailing.mailing — core mailing model)
         └── mass_mailing_contacts  (contact opt-out management)
```

**Auto-install chain**: Because `auto_install: True` and dependencies are `sale` and `mass_mailing`, the module activates automatically when both are present — no manual installation required. This makes it a transparent infrastructure module for any sale + marketing deployment.

---

## L2: Field Types, Defaults, Constraints

### `mailing.mailing` — Fields Added

#### `sale_quotation_count` — `fields.Integer` (computed, non-stored)

| Attribute | Value |
|-----------|-------|
| **Type** | `Integer` |
| **Stored** | `False` |
| **Compute** | `_compute_sale_quotation_count` |
| **Decorator** | `@api.depends('mailing_domain')` |
| **UI** | `widget="statinfo"` on `action_redirect_to_quotations` button |

**Domain filter logic**: `('order_line', '!=', False)` is a relational EXISTS filter. Translates to:
```sql
EXISTS (SELECT 1 FROM sale_order_line WHERE order_id = sale_order.id)
```
This ensures only SOs with at least one line item are counted — quotations without products are not meaningful leads. Both draft and canceled SOs are included; only the absence of order lines excludes a record.

**Critical decorator note**: `@api.depends('mailing_domain')` is a general recomputation trigger, not a data dependency. The actual join is on `source_id`. Changing `source_id` without also touching `mailing_domain` may or may not trigger recomputation depending on Odoo's invalidation engine — it is safer to invalidate explicitly or depend on `source_id` directly.

#### `sale_invoiced_amount` — `fields.Integer` (computed, non-stored)

| Attribute | Value |
|-----------|-------|
| **Type** | `Integer` (currency units, not a float) |
| **Stored** | `False` |
| **Compute** | `_compute_sale_invoiced_amount` |
| **Decorator** | `@api.depends('mailing_domain')` |
| **UI** | `widget="statinfo"` on `action_redirect_to_invoiced` button |

**Data**: `amount_untaxed_signed` from `account.move` — currency-aware signed sum. Positive for invoices, negative for refunds and credit notes. The integer truncation discards fractional cents; for practical marketing KPI purposes this is acceptable.

### `sale.order` — Class Attributes Added

| Attribute | Value |
|-----------|-------|
| `_mailing_enabled` | Class variable (`True`) — not a field |
| `_mailing_get_default_domain` | Method returning `[('state', '!=', 'cancel')]` |

**Default domain** covers all states: `draft`, `sent`, `sale`, `done`, `waiting`, `confirmed`, `sale_exception`. Only `cancel` is excluded. The logic intent: emailing contacts on canceled orders is counterproductive and potentially embarrassing.

### `utm.campaign` — Field Extended

| Attribute | Value |
|-----------|-------|
| `ab_testing_winner_selection` | Extended via `selection_add` |

Added options:

| Key | Label |
|----|-------|
| `sale_quotation_count` | Quotations |
| `sale_invoiced_amount` | Revenues |

The field was originally defined in `mass_mailing/models/utm_campaign.py` with options like `mail_open`, `mail_click`, `mail_reply`. The `mass_mailing_sale` extension adds revenue-based criteria.

---

## L3: Cross-Model Integration, Override Patterns, Workflow Triggers

### Cross-Model Data Flow

```
mailing.mailing
    │
    ├── source_id ───────────────────────────→ utm.source
    │      (primary join key: links the mailing to all downstream records)
    │
    ├── sale_quotation_count ────────────────→ sale.order (via source_id)
    │      ├── Filter: source_id IN (self.source_id.ids)
    │      ├── Filter: order_line EXISTS (not empty)
    │      └── Aggregate: COUNT grouped by source_id
    │
    ├── sale_invoiced_amount ─────────────────→ account.move (via source_id)
    │      ├── Filter: source_id IN (self.source_id.ids)
    │      ├── Filter: state NOT IN (draft, cancel) [posted only]
    │      └── Aggregate: SUM(amount_untaxed_signed) by source_id
    │
    ├── action_redirect_to_quotations ────────→ sale.report
    │      (reporting model on sale.order.line with product/partner analytics)
    │
    └── action_redirect_to_invoiced ───────────→ account.invoice.report
           (reporting model on account.move.line with journal/date analytics)

sale.order
    ├── source_id ────────────────────────────→ copied from mailing's source
    ├── campaign_id ──────────────────────────→ copied to account.move on invoicing
    └── medium_id ─────────────────────────────→ copied to account.move on invoicing
    (sale/models/account_move.py passes campaign_id, medium_id, source_id
     to invoice via _reverse_moves / _invoice_create)

utm.campaign
    └── ab_testing_winner_selection ───────────→ sale_quotation_count
          adds to base options:                  sale_invoiced_amount
          (A/B test winner criterion: downstream sales KPIs)
```

### Override Patterns

| Location | Pattern | Base method called |
|----------|---------|--------------------|
| `mailing.mailing` | Extends via `_inherit = 'mailing.mailing'` | N/A (adds fields/actions) |
| `mailing.mailing` | Method override | `super()._prepare_statistics_email_values()` |
| `sale.order` | Class attribute override | N/A (`_mailing_enabled = True`) |
| `sale.order` | Method override | `_mailing_get_default_domain(mailing)` |
| `utm.campaign` | Field selection extend | N/A (`selection_add=`) |

### Workflow Triggers

| Trigger | Action | Model affected |
|---------|--------|----------------|
| Mailing state: draft → sending/done | Stat buttons appear (invisible removed) | `mailing.mailing` form view |
| Source ID change on mailing | Both computed fields re-evaluate (via `mailing_domain` depends) | `mailing.mailing` |
| Sale order linked to source_id | `sale_quotation_count` increments | `mailing.mailing` |
| Sale order invoiced and posted | `sale_invoiced_amount` increments | `mailing.mailing` |
| Invoice for linked SO deleted | `sale_invoiced_amount` decrements | `mailing.mailing` |
| Invoice reversed (credit note posted) | `amount_untaxed_signed` negative → net revenue decreases | `mailing.mailing` |
| A/B test schedule reaches deadline | `send_winner_mailing()` uses `sale_invoiced_amount` for ranking | `utm.campaign` |
| Statistics digest email sent | `_prepare_statistics_email_values` injects sale KPIs | `mailing.mailing` |

---

## L4: Odoo 18 → 19 Version Changes

### Module Birth

`mass_mailing_sale` did not exist in Odoo 18. It was introduced in Odoo 19 specifically to fill the integration gap between `mass_mailing` and `sale`. This means there is no prior version to migrate from — it is a new module in Odoo 19.

### API Changes in Odoo 19 That This Module Depends On

#### `kpi_data` Restructuring in Statistics Email

In **Odoo 18**, the digest email KPI section used the `digest` module's legacy KPI mechanism with arbitrary KPI names. In **Odoo 19**, the structure was reorganized into a `kpi_data` list with explicitly indexed columns:

| Index | Base content label | Base content |
|-------|-------------------|---------------|
| `kpi_data[0]` | "Engagement on N mailings Sent" | Email-level metrics (received, opened, replied) |
| `kpi_data[1]` | "Business Benefits on N mailings Sent" | Initially empty columns |

`mass_mailing_sale` directly populates `kpi_data[1]` — this is the only section it touches. The base `mass_mailing` intentionally leaves this section empty so downstream modules like this one can fill it.

#### `sale.report` and `account.invoice.report` Context Keys

Both reporting models existed in Odoo 18, but their context key names and default view behaviors changed. The keys used in `mass_mailing_sale`:

| Context key | Purpose | Odoo 18 | Odoo 19 |
|-------------|---------|---------|---------|
| `sale_report_view_hide_date` | Hide date filter in search | May not exist | New in 19 |
| `invoice_report_view_hide_invoice_date` | Hide invoice date filter | May not exist | New in 19 |
| `search_default_group_by_date_day` | Default group-by for sales | Odoo 18 pattern | Changed |
| `search_default_group_by_invoice_date_week` | Default group-by for invoices | Odoo 18 pattern | Changed |

These context keys are consumed by the views themselves (`sale_report_view_search` and `account_invoice_report_view_search`), not by the model. The module sets them to suppress redundant filters when the user opens the analysis view with default grouping already applied.

#### A/B Testing Winner Selection Criteria

In **Odoo 18**, A/B testing winner criteria were limited to email engagement metrics (`mail_open`, `mail_click`, `mail_reply`). Odoo 19 introduced a framework extension point via `ab_testing_winner_selection selection_add` that allows modules like `mass_mailing_sale` to inject revenue-based criteria. The mechanism:

1. `utm.campaign.ab_testing_winner_selection` selection is extended by `mass_mailing_sale`
2. When `send_winner_mailing()` runs, it calls `_get_ab_testing_winner_selection()` on each mailing
3. If the value is a non-manual string, it sorts mailings by that field
4. The first record wins

This is a new integration point in Odoo 19 that did not exist in 18.

#### `sale.report` as Reporting Model

`sale.report` is a `report` model (a read-group based reporting model built on `sale.order.line`). It provides aggregated sales analytics at product/partner/salesperson granularity. The `action_redirect_to_quotations` method targets this model rather than `sale.order` directly — this provides richer analytics without custom SQL. This is a standard Odoo 19 reporting pattern.

### No Migration Needed

Since this module did not exist in Odoo 18, there is no migration script needed. However, if upgrading a database from Odoo 18 to 19 where a custom module previously filled this gap, that custom module should be replaced with `mass_mailing_sale`. The field names (`sale_quotation_count`, `sale_invoiced_amount`) should match if a migration is planned.

---

## Security Considerations

| Operation | Access | Mechanism |
|-----------|--------|-----------|
| `_compute_sale_quotation_count` | `.sudo()` | Reads `sale.order` via `_read_group` as superuser — bypasses per-record ACLs |
| `_compute_sale_invoiced_amount` | `.sudo()` | Reads `account.move` via `_read_group` as superuser — bypasses per-record ACLs |
| `action_redirect_to_quotations` | Standard ACL | Opens `sale.report` with `create=False` — user needs read access on reporting models |
| `action_redirect_to_invoiced` | Standard ACL | Opens `account.invoice.report` with `edit=False` — user needs read access |
| `_prepare_statistics_email_values` | Owner's company | Uses `self.user_id.company_id` for currency — multi-company safe |

**`.sudo()` rationale**: Both compute methods aggregate counts and sums across potentially large record sets. Running as superuser ensures aggregation succeeds regardless of calling user's record-level ACLs. This is an acceptable pattern for informational statistical fields that expose no per-record detail.

**Multi-company limitation**: The `.sudo()` calls aggregate across all companies — they do not respect company scoping. In multi-company setups, a user could see revenue figures from companies they do not have access to. This is a known limitation; the statistical nature (no per-record detail exposed) makes it acceptable.

---

## Performance Notes

- **Batch computation**: Both compute methods run a single `_read_group` query per mailing batch, mapping all `source_id.ids` at once. O(1) database round-trips regardless of how many mailings are on screen — critical for list view rendering.
- **Missing indexes**: `source_id` on `sale_order` and `account_move` is not indexed in the base schema. On large datasets, composite partial indexes improve performance:
  ```sql
  CREATE INDEX IF NOT EXISTS sale_order_source_id_idx ON sale_order(source_id) WHERE state != 'cancel';
  CREATE INDEX IF NOT EXISTS account_move_source_id_idx ON account_move(source_id) WHERE state = 'posted';
  ```
- **A/B winner selection**: `sorted('sale_invoiced_amount', reverse=True)` triggers one `_read_group` per mailing variant. With 2–5 variants this is acceptable.
- **`Domain.AND` overhead**: Negligible — it is a thin normalization wrapper.

---

## Edge Cases and Failure Modes

| Scenario | Behavior | Mitigation |
|----------|----------|-----------|
| Mailing has no `source_id` | Both computed fields return `0` — stat buttons work but always show zero | Always set `source_id` when creating the mailing |
| `source_id` changed after mailing is sent | Computed fields re-evaluate using new source | Avoid changing `source_id` post-send |
| Account move reversed (credit note posted) | `amount_untaxed_signed` is negative → net revenue decreases | Expected and correct behavior |
| `sale.report` model not installed | `ValidationError` at action execution | `sale` is a hard dependency — always present |
| No `user_id` on mailing | `_prepare_statistics_email_values` returns early; sale KPIs omitted from email | Set the **Responsible** field on the mailing |
| Mailing in `draft` state | Stat buttons hidden (`invisible="state == 'draft'"`) | Normal — wait for mailing to be sent |
| Multi-company: mailing by User A, invoices in Company B | `.sudo()` reads all companies — cross-company data leak in KPI | Known limitation; avoid cross-company mailings |
| A/B test with revenue criterion on millions of records | `sorted()` triggers recompute of `sale_invoiced_amount` per variant | Negligible for typical 2–5 variant A/B tests |
| SO converted to invoice but invoice deleted | `sale_invoiced_amount` decreases — correct, reflects only existing invoices | Expected behavior |

---

## Demo Data

| Field | Value |
|-------|-------|
| **ID** | `mass_mail_sale_order_0` |
| **Model** | `mailing.mailing` |
| **Subject** | "Our last promotions, just for you!" |
| **State** | `draft` |
| **Owner** | `base.user_admin` |
| **Campaign** | `mass_mail_campaign_1` |
| **Source** | `sale.utm_source_sale_order_0` |
| **Target model** | `sale.model_sale_order` |
| **Reply-to** | `{{ object.company_id.email }}` |

In the email template body, `object` refers to the `sale.order` record. The `object.name` renders the SO reference, `object.company_id.email` provides the reply-to address, and `object.company_id.name/phone/website` are used in the footer. This allows each email to be semi-personalized to the specific sale order context — `object` is bound at send time for each recipient.

---

## Tags

`#mass_mailing_sale` `#sale_order_mailing` `#utm_campaign` `#ab_testing` `#sale_quotation_count` `#sale_invoiced_amount` `#mailing_statistics` `#sale_report` `#account_invoice_report`
