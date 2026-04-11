---
Module: gamification_sale_crm
Version: Odoo 18
Type: Extension
Tags: [#odoo, #odoo18, #gamification, #crm, #sales, #kpi, #challenges, #goals]
---

# Gamification Sale CRM Module

**Module:** `gamification_sale_crm`
**Path:** `~/odoo/odoo18/odoo/addons/gamification_sale_crm/`
**Category:** Sales/CRM
**Depends:** `gamification`, `sale_crm`
**Auto-install:** `True`
**License:** LGPL-3

CRM-specific goal definitions and challenges for sales performance tracking. Provides 10 pre-configured goal definitions across sales, invoicing, and lead management, plus 2 starter challenges. Acts as the reference implementation of how gamification extends to CRM/Sales.

---

## Module Role

`gamification_sale_crm` does NOT define new models. It extends the base gamification framework (`gamification.goal.definition`, `gamification.challenge`, `gamification.challenge.line`) with CRM-specific data:

1. **Goal definitions** — 10 definitions targeting `crm.lead`, `sale.order`, `account.invoice.report`
2. **Challenges** — 2 challenges with lines attached to those definitions

The actual goal/challenge models live in the `gamification` base module.

---

## Goal Definitions (Extended)

All goal definitions are loaded via `data/gamification_sale_crm_data.xml`. They use `batch_mode: True` with `batch_user_expression: user.id` — meaning goals are evaluated per-salesperson via grouped SQL queries, not per-record triggers.

### 1. `definition_crm_tot_invoices` — Total Invoiced

```xml
<field name="computation_mode">sum</field>
<field name="monetary">True</field>
<field name="model_id">account.model_account_invoice_report</field>
<field name="field_id">account.field_account_invoice_report__price_subtotal</field>
<field name="field_date_id">account.field_account_invoice_report__invoice_date</field>
<field name="domain">[('state','!=','cancel'),('move_type','=','out_invoice')]</field>
```

**What it measures:** Sum of `price_subtotal` for all non-cancelled customer invoices (`out_invoice`) in the goal period.

**Batch distinctively field:** `invoice_user_id` (the salesperson on the invoice)
**Condition:** `higher` (the higher the invoiced total, the better)

---

### 2. `definition_crm_nbr_new_leads` — New Leads

```xml
<field name="computation_mode">count</field>
<field name="suffix">leads</field>
<field name="model_id">crm.model_crm_lead</field>
<field name="domain">['|', ('type', '=', 'lead'), ('type', '=', 'opportunity')]</field>
<field name="field_date_id">search: create_date on crm.lead</field>
```

**What it measures:** Count of new leads and opportunities by creation date. Excludes cancelled.
**Condition:** `higher`
**Note:** Counts both `lead` and `opportunity` types — a lead converted to opportunity should not penalize the rep.

---

### 3. `definition_crm_lead_delay_open` — Time to Qualify a Lead

```xml
<field name="computation_mode">sum</field>
<field name="condition">lower</field>
<field name="suffix">days</field>
<field name="model_id">crm.model_crm_lead</field>
<field name="field_id">crm.field_crm_lead__day_close</field>
<field name="field_date_id">crm.field_crm_lead__date_closed</field>
<field name="domain">[('type', '=', 'lead')]</field>
```

**What it measures:** Average days to qualify (close) a lead (by `date_closed`). Lower is better.
**Note:** `day_close` is a computed field on `crm.lead` representing days to close.

---

### 4. `definition_crm_lead_delay_close` — Days to Close a Deal

```xml
<field name="computation_mode">sum</field>
<field name="condition">lower</field>
<field name="suffix">days</field>
<field name="model_id">crm.model_crm_lead</field>
<field name="field_id">crm.field_crm_lead__day_open</field>
<field name="field_date_id">crm.field_crm_lead__date_open</field>
<field name="domain">[]</field>
```

**What it measures:** Average days to open/qualify an opportunity. `day_open` field from date open. **No domain filter** — applies to all lead types.
**Condition:** `lower`

---

### 5. `definition_crm_nbr_new_opportunities` — New Opportunities

```xml
<field name="computation_mode">count</field>
<field name="suffix">opportunities</field>
<field name="model_id">crm.model_crm_lead</field>
<field name="field_date_id">crm.field_crm_lead__date_open</field>
<field name="domain">[('type','=','opportunity')]</field>
```

**What it measures:** Count of opportunities with a set `date_open` (opened date).
**Condition:** `higher`

---

### 6. `definition_crm_nbr_sale_order_created` — New Sales Orders

```xml
<field name="computation_mode">count</field>
<field name="suffix">orders</field>
<field name="model_id">sale.model_sale_order</field>
<field name="field_date_id">sale.field_sale_order__date_order</field>
<field name="domain">[('state','not in',('draft', 'sent', 'cancel'))]</field>
```

**What it measures:** Count of confirmed/validated sale orders (excludes draft, sent, cancelled).
**Condition:** `higher`
**Batch distinctively field:** `sale_order.user_id`

---

### 7. `definition_crm_nbr_paid_sale_order` — Paid Sales Orders (count)

```xml
<field name="computation_mode">count</field>
<field name="suffix">orders</field>
<field name="model_id">account.model_account_invoice_report</field>
<field name="domain">[('payment_state','in',('paid', 'in_payment')),('move_type','=','out_invoice')]</field>
```

**What it measures:** Count of fully or partially paid customer invoices.
**Condition:** `higher`

---

### 8. `definition_crm_tot_paid_sale_order` — Total Paid Sales Orders (value)

```xml
<field name="computation_mode">sum</field>
<field name="monetary">True</field>
<field name="model_id">account.model_account_invoice_report</field>
<field name="field_id">account.field_account_invoice_report__price_subtotal</field>
<field name="domain">[('payment_state','in',('paid', 'in_payment')),('move_type','=','out_invoice')]</field>
```

**What it measures:** Total monetary value of paid invoices. **This duplicates `definition_crm_tot_invoices` but filters for `payment_state`**. Use this to reward cash collection rather than invoicing.

---

### 9. `definition_crm_nbr_customer_refunds` — Customer Credit Notes (count)

```xml
<field name="computation_mode">count</field>
<field name="condition">lower</field>
<field name="suffix">invoices</field>
<field name="model_id">account.model_account_invoice_report</field>
<field name="domain">[('state','!=','cancel'),('move_type','=','out_refund')]</field>
```

**What it measures:** Count of credit notes (refunds). Lower is better (fewer refunds = healthier sales).
**Condition:** `lower`

---

### 10. `definition_crm_tot_customer_refunds` — Total Customer Credit Notes (value)

```xml
<field name="computation_mode">sum</field>
<field name="condition">higher</field>
<field name="monetary">True</field>
<field name="model_id">account.model_account_invoice_report</field>
<field name="field_id">account.field_account_invoice_report__price_subtotal</field>
<field name="domain">[('state','!=','cancel'),('move_type','=','out_refund')]</field>
```

**What it measures:** Total value of credit notes (note: `price_subtotal` on refunds is negative). Condition `higher` means goal succeeds when total credit note is "high" (abs value large) — which is counterintuitive. See L4 note below.

---

## Challenges

### Challenge 1: `challenge_crm_sale` — Monthly Sales Targets

**Period:** `monthly`
**Visibility:** `ranking` (leader board)
**Participants:** All `group_sale_salesman` members via domain
**Report frequency:** `weekly`

| Line | Goal Definition | Target |
|------|----------------|--------|
| `line_crm_sale1` | Total Invoiced (`definition_crm_tot_invoices`) | 20,000 |

**Configuration detail:** Single-line challenge targeting invoiced revenue. Ranking visibility means salespeople see a leader board.

---

### Challenge 2: `challenge_crm_marketing` — Lead Acquisition

**Period:** `monthly`
**Visibility:** `ranking`
**Participants:** All `group_sale_salesman` members
**Report frequency:** `weekly`

| Line | Goal Definition | Target | Sequence |
|------|----------------|--------|----------|
| `line_crm_marketing1` | New Leads (`definition_crm_nbr_new_leads`) | 7 | 1 |
| `line_crm_marketing2` | Time to Qualify (`definition_crm_lead_delay_open`) | 15 days | 2 |
| `line_crm_marketing3` | New Opportunities (`definition_crm_nbr_new_opportunities`) | 5 | 3 |

**Configuration detail:** Three-line challenge covering the full pipeline: attract → qualify → convert. All three goals must be reached for the `reward_id` badge to be granted.

---

## Base Models (Extended from `gamification`)

### `gamification.goal.definition` (base)

See [[Modules/Gamification]] for full field list. Key extension points used by this module:

- `computation_mode`: `'count'` (leads, opportunities, orders) or `'sum'` (revenue, credit notes)
- `monetary`: `True` on revenue/credit note definitions
- `batch_mode`: `True` on all CRM definitions — evaluates via grouped SQL per `batch_distinctive_field`
- `condition`: `'higher'` (revenue) or `'lower'` (time metrics, refunds)
- `suffix`: Display unit (`leads`, `opportunities`, `days`, `invoices`)
- `field_date_id`: Date field for period filtering (`create_date`, `date_open`, `date_closed`, `invoice_date`)

### `gamification.challenge` (base)

See [[Modules/Gamification]] for full field list. CRM-specific configuration:

- `period: 'monthly'` — resets goals monthly
- `visibility_mode: 'ranking'` — leader board display
- `user_domain` — restricts to `sales_team.group_sale_salesman`
- `report_message_frequency: 'weekly'` — progress emails every week
- `state: 'inprogress'` (in demo/data) — active on module install

---

## Demo Data

`data/gamification_sale_crm_demo.xml` sets `challenge_crm_sale` state to `inprogress`, automatically triggering goal generation for all matching sales users via `gamification.challenge._generate_goals_from_challenge()`.

---

## L4: How CRM Gamification Works

### Goal Computation Flow

```
gamification.challenge._cron_update()
    → gamification.goal.update_goal()
    → for each goal:
        → reads definition.computation_mode
        → if batch_mode: GROUP BY batch_distinctive_field
        → if count: SELECT COUNT(*) WHERE domain
        → if sum: SELECT SUM(field) WHERE domain
        → updates gamification.goal.current
        → checks if current >= target → state = 'reached'
```

### CRM KPI Categories

| Category | Goals | Direction |
|----------|-------|-----------|
| **Revenue** | Total Invoiced, Paid Invoices Value | higher = better |
| **Pipeline** | New Leads, New Opportunities | higher = better |
| **Speed** | Time to Qualify, Days to Close | lower = better |
| **Quality** | Customer Credit Notes (count+value) | lower = better |

### Multi-dimensional Challenge Design

`challenge_crm_marketing` demonstrates best practice: goals span the full sales cycle with different unit types (count, days). All three must reach target for badge reward, enforcing balanced performance.

### Credit Note Inversion Gotcha

`definition_crm_tot_customer_refunds` uses `condition: higher` with a negative `price_subtotal`. This means the goal succeeds when the credit note value is "higher" (e.g., -5000 is "higher" than -2000 in Python, so larger absolute refunds trigger success). This is likely a design error — `condition: lower` would be more intuitive (lower refund = better). Treat as a demonstration of domain behavior rather than recommended practice.

### Integration with `sale_crm`

Since this module depends on `sale_crm` (which extends `crm.lead` with `sale.order` conversion tracking), goal definitions can reference fields added by `sale_crm` without explicitly depending on them. The actual field resolution happens at goal computation time.

---

## Related Documentation

- [[Modules/Gamification]] — Base gamification models (`gamification.challenge`, `gamification.goal`, `gamification.badge`, `gamification.goal.definition`)
- [[Modules/CRM]] — CRM module being gamified
- [[Modules/Sale]] — Sale order model referenced in goal definitions
- [[Modules/Account]] — Invoice reporting model used for revenue goals