---
Module: mass_mailing_sale
Version: Odoo 18
Type: Integration
Tags: #mass-mailing #sale #marketing #email #utm
---

# Mass Mailing Sale Integration (`mass_mailing_sale`)

## Overview

**Path:** `~/odoo/odoo18/odoo/addons/mass_mailing_sale/`

The `mass_mailing_sale` module bridges the **Mass Mailing** and **Sale** modules. It:

- Enables `sale.order` records to be **recipients of promotional email campaigns** (sets `_mailing_enabled = True`)
- Extends `mailing.mailing` with **sale-specific KPI stat buttons** (Quotations count, Invoiced amount)
- Adds `sale_quotation_count` and `sale_invoiced_amount` to the mailing's **KPI statistics email**
- Extends `utm.campaign` with **"Quotations" and "Revenues" A/B testing winner criteria**
- Ships a demo mailing: "Sale Promotion 1" targeting `sale.order` records

**Depends:** `sale`, `mass_mailing`
**Auto-install:** `True`
**Category:** Hidden (auto-install integration)

---

## Architecture

This module defines **three** Python model extensions:

| Model | File | Role |
|-------|------|------|
| `sale.order` | `models/sale_order.py` | Enables sale orders as mailing recipients + default domain |
| `mailing.mailing` | `models/mailing_mailing.py` | Adds sale KPI buttons + statistics enrichment |
| `utm.campaign` | `models/utm.py` | Adds `sale_quotation_count` and `sale_invoiced_amount` as A/B testing winner criteria |

---

## Models Extended

### `sale.order` (Extended)

**File:** `models/sale_order.py`

```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'
    _mailing_enabled = True

    def _mailing_get_default_domain(self, mailing):
        """ Exclude by default canceled orders when performing a mass mailing. """
        return [('state', '!=', 'cancel')]
```

#### `_mailing_enabled = True`

Same mechanism as in `mass_mailing_crm`: marks `sale.order` as a valid mailing recipient model by setting `is_mailing_enabled = True` on its `ir.model` record. This allows `mailing.mailing`'s `mailing_model_id` domain to include `sale.order`.

#### `_mailing_get_default_domain(mailing)`

**Critical method** — defines the default recipient filter applied when a mailing targets `sale.order`:

```python
def _mailing_get_default_domain(self, mailing):
    return [('state', '!=', 'cancel')]
```

By default, **canceled sale orders are excluded** from receiving promotional emails. This prevents marketing emails from being sent to customers whose orders were canceled. Active, draft, sent, and sale orders are included.

This method is called by the mailing engine's `_get_recipients_domain()` when no explicit `mailing_domain` is set on the mailing.

---

### `mailing.mailing` (Extended)

**File:** `models/mailing_mailing.py`

Extends the base `mailing.mailing` model (from `addons/mass_mailing/models/mailing.py`) with sale-specific computed fields and actions.

#### New Fields Added

| Field | Type | Compute | Description |
|-------|------|---------|-------------|
| `sale_quotation_count` | Integer | `_compute_sale_quotation_count` | Count of non-draft sale orders linked to this mailing's UTM source |
| `sale_invoiced_amount` | Integer | `_compute_sale_invoiced_amount` | Sum of untaxed invoiced amounts from paid invoices linked to this mailing's UTM source |

Both fields are stored as integers (currency-agnostic; formatted at display time).

#### `_compute_sale_quotation_count()`

```python
@api.depends('mailing_domain')
def _compute_sale_quotation_count(self):
    quotation_data = self.env['sale.order'].sudo()._read_group(
        [('source_id', 'in', self.source_id.ids), ('order_line', '!=', False)],
        ['source_id'], ['__count'],
    )
    mapped_data = {source.id: count for source, count in quotation_data}
    for mass_mailing in self:
        mass_mailing.sale_quotation_count = mapped_data.get(mass_mailing.source_id.id, 0)
```

Counts `sale.order` records linked to the mailing's UTM source that have at least one order line (`order_line != False`). This ensures only **real quotations** (with products) are counted, not empty draft orders. Uses `sudo()` and `source_id.ids` for efficient batch computation.

#### `_compute_sale_invoiced_amount()`

```python
@api.depends('mailing_domain')
def _compute_sale_invoiced_amount(self):
    domain = expression.AND([
        [('source_id', 'in', self.source_id.ids)],
        [('state', 'not in', ['draft', 'cancel'])]
    ])
    moves_data = self.env['account.move'].sudo()._read_group(
        domain, ['source_id'], ['amount_untaxed_signed:sum'],
    )
    mapped_data = {source.id: amount_untaxed_signed for source, amount_untaxed_signed in moves_data}
    for mass_mailing in self:
        mass_mailing.sale_invoiced_amount = mapped_data.get(mass_mailing.source_id.id, 0)
```

Sums `amount_untaxed_signed` from all `account.move` records (invoices) linked to the mailing's UTM source. Only counts invoices in states **not in `['draft', 'cancel']`** — so paid, open, and posted invoices count. Uses `amount_untaxed_signed` (not `amount_total`) to exclude tax from the revenue figure.

#### `action_redirect_to_quotations()`

```python
def action_redirect_to_quotations(self):
    return {
        'context': {
            'create': False,
            'search_default_group_by_date_day': True,
            'sale_report_view_hide_date': True,
        },
        'domain': [('source_id', '=', self.source_id.id)],
        'help': Markup('<p class="o_view_nocontent_smiling_face">...</p>'),
        'name': _("Sales Analysis"),
        'res_model': 'sale.report',
        'type': 'ir.actions.act_window',
        'view_mode': 'list,pivot,graph,form',
    }
```

Opens the **Sales Analysis** report (`sale.report` model) filtered by the mailing's UTM source. Shows quotations and orders attributed to this mailing as a pivot/graph report. Empty-state message notes that quotations appear when customers add products or sales reps assign the mailing.

#### `action_redirect_to_invoiced()`

```python
def action_redirect_to_invoiced(self):
    domain = expression.AND([
        [('source_id', '=', self.source_id.id)],
        [('state', 'not in', ['draft', 'cancel'])]
    ])
    moves = self.env['account.move'].search(domain)
    return {
        'context': {
            'create': False,
            'edit': False,
            'view_no_maturity': True,
            'search_default_group_by_invoice_date_week': True,
            'invoice_report_view_hide_invoice_date': True,
        },
        'domain': [('move_id', 'in', moves.ids)],
        'name': _("Invoices Analysis"),
        'res_model': 'account.invoice.report',
        'type': 'ir.actions.act_window',
        'view_mode': 'list,pivot,graph,form',
    }
```

Opens the **Invoices Analysis** report (`account.invoice.report` model). Unlike the quotations action which filters by `source_id` directly, this first searches for matching `account.move` records, then filters the report to those invoice IDs. This is because `account.invoice.report` is a read-through report model over `account.move`.

#### `_prepare_statistics_email_values()`

```python
def _prepare_statistics_email_values(self):
    self.ensure_one()
    values = super(MassMailing, self)._prepare_statistics_email_values()
    if not self.user_id:
        return values

    self_with_company = self.with_company(self.user_id.company_id)
    currency = self.user_id.company_id.currency_id
    formated_amount = tools.misc.format_decimalized_amount(
        self_with_company.sale_invoiced_amount, currency
    )

    values['kpi_data'][1]['kpi_col2'] = {
        'value': self.sale_quotation_count,
        'col_subtitle': _('QUOTATIONS'),
    }
    values['kpi_data'][1]['kpi_col3'] = {
        'value': formated_amount,
        'col_subtitle': _('INVOICED'),
    }
    values['kpi_data'][1]['kpi_name'] = 'sale'
    return values
```

Adds two KPI columns to the mailing's periodic statistics email sent to the responsible user:
- **QUOTATIONS**: count of sale orders linked to the mailing's source
- **INVOICED**: formatted revenue amount (currency-aware) from paid invoices

---

### `utm.campaign` (Extended)

**File:** `models/utm.py`

```python
class UtmCampaign(models.Model):
    _inherit = 'utm.campaign'

    ab_testing_winner_selection = fields.Selection(selection_add=[
        ('sale_quotation_count', 'Quotations'),
        ('sale_invoiced_amount', 'Revenues'),
    ])
```

Adds two A/B testing winner criteria:
- **`sale_quotation_count`**: Select the mailing variant that generated the most sale quotations
- **`sale_invoiced_amount`**: Select the mailing variant that generated the most invoiced revenue

These criteria allow marketers to run A/B tests and automatically promote the variant that drives the highest sales performance, not just email engagement metrics (opens, clicks).

---

## View Extension (XML)

**File:** `views/mailing_mailing_views.xml`

Inherits the base mass mailing form view and adds **two stat buttons** before "View Deliveries":

```xml
<button name="action_redirect_to_quotations"
    type="object"
    icon="fa-pencil-square-o"
    class="oe_stat_button"
    invisible="state == 'draft'">
    <field name="sale_quotation_count" string="Quotations" widget="statinfo"/>
</button>

<button name="action_redirect_to_invoiced"
    type="object"
    icon="fa-dollar"
    class="oe_stat_button"
    invisible="state == 'draft'">
    <field name="sale_invoiced_amount" string="Invoiced" widget="statinfo"/>
</button>
```

Both buttons are hidden in `draft` state and only appear after the mailing has been sent.

---

## Demo Data

**File:** `demo/mailing_mailing.xml`

Creates a demo mailing for testing:

| Field | Value |
|-------|-------|
| `name` | `Sale Promotion 1` |
| `subject` | `Our last promotions, just for you!` |
| `state` | `draft` |
| `mailing_model_id` | `sale.model_sale_order` |
| `mailing_domain` | `[]` (all non-canceled orders, via `_mailing_get_default_domain`) |
| `campaign_id` | `mass_mailing.mass_mail_campaign_1` |
| `source_id` | `sale.utm_source_sale_order_0` |

---

## Sale Order Mailing Domain (L4)

When a mailing targets `sale.order`, the domain determines which orders are recipients:

```python
# Default (from _mailing_get_default_domain)
[('state', '!=', 'cancel')]

# Sent/quotation-stage orders
[('state', 'in', ['sent', 'sale'])]

# Orders from a specific partner
[('partner_id', '=', ref('base.res_partner_3'))]

# Orders with high amount
[('amount_total', '>', 10000)]

# Orders pending payment (sale confirmed, not paid)
[('state', '=', 'sale'), ('invoice_status', '=', 'to_invoice')]

# Orders with specific product
[('order_line.product_id', '=', ref('product.product_product_24'))]
```

The `_mailing_get_default_domain` hook means canceled orders are **always excluded** unless the user explicitly overrides the domain.

---

## Customer Segmentation for Sales Promotions (L4)

The `mass_mailing_sale` module enables powerful **customer segmentation** for promotional campaigns:

### Segmentation Strategies

1. **Order History Segmentation**
   - Customers who ordered product X → tag-based or domain-based list
   - Customers with order > $X → `amount_total` domain filter
   - Customers who haven't ordered in 90 days → date-based filter on `date_order`

2. **Order Status Segmentation**
   - Active quotation recipients → `state = 'sent'`
   - Confirmed order customers → `state = 'sale'`
   - Upsell to existing customers → `order_line.product_id` domain

3. **Campaign Attribution**
   - Every mailing has a `source_id` (UTM source) → automatically linked to all created `sale.order` records
   - Track which mailing generated which orders via `sale.report.source_id`

### Revenue Attribution Flow

```
mailing.mailing
    └── source_id ──→ utm.source (e.g., "Summer Sale 2026")

sale.order (created from customer action)
    └── source_id ──→ same utm.source

account.move (invoiced from sale.order)
    └── source_id ──→ same utm.source (via order)

mailing.mailing
    └── sale_invoiced_amount ──→ SUM(account.move.amount_untaxed_signed)
                                    WHERE source_id = mailing.source_id
```

This creates a **closed-loop attribution** from email campaign to revenue, allowing ROI calculation per mailing.

---

## Comparison: `mass_mailing_crm` vs `mass_mailing_sale`

| Feature | `mass_mailing_crm` | `mass_mailing_sale` |
|---------|-------------------|---------------------|
| Target model | `crm.lead` | `sale.order` |
| Stat button 1 | Leads/Opportunities count | Quotations count |
| Stat button 2 | — | Invoiced amount |
| Default domain | None (all leads) | Exclude canceled |
| A/B criteria | `crm_lead_count` | `sale_quotation_count`, `sale_invoiced_amount` |
| Analysis model | `crm.lead` | `sale.report`, `account.invoice.report` |
| Reply processing | `_mailing_enabled` on `crm.lead` | `_mailing_enabled` on `sale.order` |

---

## Related Documentation

- [Modules/Mass Mailing](mass-mailing.md) — base mass mailing module (`mailing.mailing`, `mailing.trace`)
- [Modules/Sale](sale.md) — base sale module (`sale.order`, order states)
- [Modules/Mass Mailing CRM](mass-mailing-crm.md) — CRM email marketing integration
- [Modules/crm-sms](crm-sms.md) — CRM SMS integration
- [Patterns/Security Patterns](Security Patterns.md) — ir.rule and access control
- [Core/API](API.md) — `@api.depends`, computed fields, `sudo()`
