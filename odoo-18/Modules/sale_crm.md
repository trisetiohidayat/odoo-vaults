# sale_crm — Sale CRM

**Tags:** #odoo #odoo18 #sale #crm #opportunity #pipeline
**Odoo Version:** 18.0
**Module Category:** Sale + CRM Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_crm` links CRM leads/opportunities to sale orders, enabling pipeline-to-revenue tracking. It computes quotational activity on opportunities, creates a SO from a lead, and provides dashboards linking revenue to CRM data. It also synchronizes sales team membership with sale order assignment.

**Technical Name:** `sale_crm`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_crm/`
**Depends:** `sale`, `crm`
**Inherits From:** `crm.lead`, `crm.team`, `res.users`, `sale.order`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/crm_lead.py` | `crm.lead` | Sale amount tracking, quotation/SO counts, SO links |
| `models/crm_team.py` | `crm.team` | Dashboard/graph overrides for sales app context |
| `models/res_users.py` | `res.users` | Target sales invoiced field |
| `models/sale_order.py` | `sale.order` | Opportunity link, revenue update on confirm |

---

## Models Reference

### `crm.lead` (models/crm_lead.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `sale_amount_total` | Monetary | Total SO amount for this lead |
| `quotation_count` | Integer | Count of draft/quotation SOs |
| `sale_order_count` | Integer | Count of confirmed SOs |
| `order_ids` | One2many | All SOs linked to this lead |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_sale_amount_total()` | Sums `amount_total` of confirmed SOs, in company currency |
| `_compute_quotation_count()` | Counts SOs with state in 'draft', 'sent', 'negotiation' |
| `_compute_sale_order_count()` | Counts SOs with state 'sale' |
| `_make_quotation()` | Creates new SO from lead using partner data |
| `_make_order()` | Alias for `_make_quotation()` |
| `_opportunity_to_sale_order()` | Converts lead to order: copies partner, line data, tags |
| `_sale_order_count伟()` | Unlink cascade: updates counts after SO unlink |
| `write()` | Updates counts after any SO write |

---

### `crm.team` (models/crm_team.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_graph_title_get()` | Override: returns team name instead of default |
| `_graph_x_query_get()` | Override: uses `date_closed` for X axis in sales app |

---

### `res.users` (models/res_users.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `target_sales_invoiced` | Integer | Personal invoiced sales target |

---

### `sale.order` (models/sale_order.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `opportunity_id` | Many2one | CRM lead/opportunity link |

#### Methods

| Method | Behavior |
|--------|----------|
| `action_confirm()` | Calls `_update_revenues_from_so()` on opportunity |
| `_update_revenues_from_so()` | Recomputes `sale_amount_total` on linked lead |

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

| File | Content |
|------|---------|
| `data/res_config_data.xml` | Sales team config: `target_sales_invoiced` visibility |
| `data/crm_crm_lead_menu.xml` | Menu entries for lead→quotation action |

---

## Critical Behaviors

1. **Revenue on Lead**: `sale_amount_total` on `crm.lead` is the canonical revenue metric for pipeline forecasting. Only confirmed SOs count.

2. **SO Creation from Lead**: `_opportunity_to_sale_order()` converts the lead into a full draft SO, copying the partner, contact info, shipping address, and optionally the lead's line items.

3. **Count Tracking**: Separate counters for `quotation_count` (draft SOs) and `sale_order_count` (confirmed SOs) give sales managers visibility into pipeline stages.

4. **Opportunity→Revenue Sync**: When a SO is confirmed, `_update_revenues_from_so()` recomputes the lead's `sale_amount_total`, keeping the pipeline value in sync with actual confirmed revenue.

---

## v17→v18 Changes

- `_graph_title_get()` and `_graph_x_query_get()` methods added to `crm.team` for improved dashboard rendering in the sales app
- `_update_revenues_from_so()` method added for revenue sync on confirm

---

## Notes

- `sale_crm` is the standard bridge between the CRM pipeline and actual sales orders
- `sale_amount_total` on a lead is used in CRM reporting for revenue forecasting
- The `opportunity_id` on `sale.order` enables bidirectional SO↔lead navigation
- Sales team dashboard overrides ensure correct graph axes when viewing pipeline in the sales app
