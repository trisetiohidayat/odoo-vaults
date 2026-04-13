---
uuid: sale-module-v19
module: sale
tags:
  - #odoo
  - #odoo19
  - #modules
  - #sales
created: 2026-04-11
updated: 2026-04-11
# L4 depth escalation: 2026-04-11
author: Roedl
description: Core Sales module - sales orders, quotation workflow, pricing, invoicing
related_modules:
  - sale_management
  - sale_stock
  - sale_project
  - account
  - product
  - stock
see_also:
  - "[Core/BaseModel](Core/BaseModel.md)"
  - "[Core/Fields](Core/Fields.md)"
  - "[Core/API](Core/API.md)"
  - "[Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md)"
---

# Module: sale

> **Core Sales Management** - Handles the complete sales order lifecycle from quotation to invoicing.

**Path:** `/Users/tri-mac/odoo/odoo19/odoo/addons/sale/`
**Vault:** `/Users/tri-mac/Obsidian Vault/Odoo 19/Modules/sale.md`

---

## Overview

The `sale` module is the core sales management module in Odoo. It provides the complete sales workflow including quotation creation, order confirmation, delivery management, and invoicing. The module is extensively used by other modules like `sale_stock`, `sale_management`, `sale_project`, and integrates deeply with `account`, `stock`, and `product` modules.

**Dependencies:** `sales_team`, `account_payment` (which transitively pulls in `account`, `payment`, `portal`), `utm`
**Dependents:** `sale_stock`, `sale_project`, `sale_loyalty`, `sale_renting`, many more
**Category:** `Sales/Sales`
**Version:** `1.2`
**License:** `LGPL-3`

---

## L1: All Models with Fields

### Model: `sale.order`

The primary model representing a sales order or quotation. Inherits from `portal.mixin`, `product.catalog.mixin`, `mail.thread`, `mail.activity.mixin`, `utm.mixin`, and `account.document.import.mixin`.

#### Selection Constants

```python
INVOICE_STATUS = [
    ('upselling', 'Upselling Opportunity'),
    ('invoiced', 'Fully Invoiced'),
    ('to invoice', 'To Invoice'),
    ('no', 'Nothing to Invoice')
]

SALE_ORDER_STATE = [
    ('draft', "Quotation"),
    ('sent', "Quotation Sent"),
    ('sale', "Sales Order"),
    ('cancel', "Cancelled"),
]
```

Note: The `done` state from Odoo 18 was replaced by a `locked` boolean in Odoo 19.

#### Core Identification Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Order reference. Default: "New". Uses `ir.sequence` with code `sale.order`. Indexed with trigram. |
| `company_id` | Many2one | The company. Default: `self.env.company`. Required. |
| `partner_id` | Many2one | Customer. Required. `change_default=True`, `tracking=1`. Tracked via chatter. |
| `state` | Selection | Order status. Default: `draft`. Values: `draft`, `sent`, `sale`, `cancel`. `readonly=True`, `copy=False`, `tracking=3`. |
| `locked` | Boolean | If `True`, order cannot be modified. `default=False`, `copy=False`, `tracking=True`. Replaces Odoo 18 `done` state. |
| `has_archived_products` | Boolean | Computed. True if any line has an inactive product. Triggers warning banner. |
| `pending_email_template_id` | Many2one | `mail.template`. Readonly. Set when email is deferred via async cron. |

#### Date and Reference Fields

| Field | Type | Description |
|-------|------|-------------|
| `date_order` | Datetime | Order date. Required. Default: `Datetime.now()`. Used for creation of draft/sent orders and confirmation date of confirmed orders. Also used as the conversion date for currency rates. |
| `create_date` | Datetime | ORM override. Readonly. Creation timestamp. |
| `validity_date` | Date | Expiration date of quotation. Computed from `company_id.quotation_validity_days`. `store=True`. |
| `commitment_date` | Datetime | Promised delivery date to customer. Overrides product lead times when set. `copy=False`. |
| `client_order_ref` | Char | Customer's purchase order reference. `copy=False`. Used for duplicate order detection. |
| `origin` | Char | Source document reference (e.g., from eCommerce or CRM). |
| `reference` | Char | Payment communication. `copy=False`. Populated by payment provider. |
| `expected_date` | Datetime | Non-stored compute. Delivery date computed from minimum lead time of order lines. `store=False` because it depends on `today()`. Warning issued if `commitment_date < expected_date`. |

#### Online Confirmation Fields

| Field | Type | Description |
|-------|------|-------------|
| `require_signature` | Boolean | Request online signature. Computed from `company_id.portal_confirmation_sign`. `store=True`. |
| `require_payment` | Boolean | Request online payment to confirm. Computed from `company_id.portal_confirmation_pay`. `store=True`. |
| `prepayment_percent` | Float | Percentage of order total required to confirm. Computed from `company_id.prepayment_percent`. `store=True`. Range: 0 < value <= 1.0. |
| `signature` | Image | Customer's signature. Max 1024x1024 pixels. `copy=False`. |
| `signed_by` | Char | Name of person who signed. `copy=False`. |
| `signed_on` | Datetime | Date/time of signing. `copy=False`. |

#### Partner-based Fields (Computed, Storeable)

| Field | Type | Description |
|-------|------|-------------|
| `partner_invoice_id` | Many2one | Invoice address. Computed from `partner_id.address_get(['invoice'])`. `required=True`, `index='btree_not_null'`. |
| `partner_shipping_id` | Many2one | Delivery address. Computed from `partner_id.address_get(['delivery'])`. `required=True`. |
| `fiscal_position_id` | Many2one | Fiscal position. Computed based on partner and shipping address. Triggers `show_update_fpos` warning. |
| `payment_term_id` | Many2one | Payment terms. Inherited from `partner_id.property_payment_term_id`. |
| `preferred_payment_method_line_id` | Many2one | Preferred inbound payment method for this order. From partner property. |
| `pricelist_id` | Many2one | Pricelist. Inherited from `partner_id.property_product_pricelist`. Only recomputed in `draft` state. |
| `currency_id` | Many2one | Currency. From pricelist or falls back to company currency. `ondelete='restrict'`. |
| `currency_rate` | Float | Exchange rate from company currency to order currency. Computed from `res.currency._get_conversion_rate()` using `date_order` date. Digits=0 (integer precision). |
| `note` | Html | Terms and conditions. Computed from company settings (`invoice_terms_html` or `invoice_terms`). Honors partner language. |

#### Sales Team Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | Many2one | Salesperson. Computed from partner's user or current user with `group_sale_salesman`. Domain restricts to internal users in current company. `tracking=2`. |
| `team_id` | Many2one | Sales team. Computed via `crm.team._get_default_team_id()`. `tracking=True`. |

#### Order Lines

| Field | Type | Description |
|-------|------|-------------|
| `order_line` | One2many | Lines in the order. Inverse of `sale.order.line.order_id`. `copy=True`, `bypass_search_access=True`. |

#### Amount Fields (Stored)

| Field | Type | Description |
|-------|------|-------------|
| `amount_untaxed` | Monetary | Untaxed subtotal. Stored. Computed via tax engine. `tracking=5`. |
| `amount_tax` | Monetary | Total tax amount. Stored. Computed via tax engine. |
| `amount_total` | Monetary | Grand total (untaxed + tax). Stored. Computed via tax engine. `tracking=4`. |
| `amount_undiscounted` | Float | Theoretical amount before any discount. Non-monetary (raw float). |
| `amount_to_invoice` | Monetary | Non-stored. Sum of line `amount_to_invoice` fields. |
| `amount_invoiced` | Monetary | Non-stored. Sum of line `amount_invoiced` fields. |

#### Invoicing Fields

| Field | Type | Description |
|-------|------|-------------|
| `invoice_count` | Integer | Number of linked invoices. |
| `invoice_ids` | Many2many | Invoices (both out_invoice and out_refund). |
| `invoice_status` | Selection | Aggregate status from all lines. Values: `upselling`, `invoiced`, `to invoice`, `no`. Stored. |
| `journal_id` | Many2one | Invoicing journal override. Domain `type='sale'`. If unset, lowest-sequence sales journal is used. |

#### Payment Fields

| Field | Type | Description |
|-------|------|-------------|
| `transaction_ids` | Many2many | Payment transactions. `groups='account.group_account_invoice'`. |
| `authorized_transaction_ids` | Many2many | Transactions in `authorized` state. `compute_sudo=True`. |
| `has_authorized_transaction_ids` | Boolean | True if any transaction is authorized. `compute_sudo=True`. |
| `amount_paid` | Float | Sum of `done` and `authorized` transaction amounts. `compute_sudo=True`. Used for prepayment confirmation check. |

#### UTM Fields

| Field | Type | Description |
|-------|------|-------------|
| `campaign_id` | Many2one | UTM Campaign. `ondelete='set null'`. |
| `medium_id` | Many2one | UTM Medium. `ondelete='set null'`. |
| `source_id` | Many2one | UTM Source. `ondelete='set null'`. |

#### Misc Fields

| Field | Type | Description |
|-------|------|-------------|
| `tag_ids` | Many2many | CRM tags. `groups='sales_team.group_sale_salesman'`. |
| `sale_warning_text` | Text | Internal sale warnings. Only populated if user has `sale.group_warning_sale`. Aggregates partner warnings and product warnings. |
| `duplicated_order_ids` | Many2many | Orders with same `partner_id` + `client_order_ref` or `origin` matching another order's `name`. Only computed for `draft` orders. Uses direct SQL query for performance. |

#### Non-stored Computed Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_expired` | Boolean | True if `state in ('draft', 'sent')` and `validity_date < today`. |
| `partner_credit_warning` | Text | Credit limit warning from account module. Only shown in draft/sent states if `account_use_credit_limit` is enabled. Amount converted to company currency using `currency_rate`. |
| `tax_totals` | Binary | Tax totals JSON for frontend display. Uses account tax engine. `exportable=False`. |
| `type_name` | Char | "Quotation" for `draft/sent/cancel`, "Sales Order" for `sale`. |
| `country_code` | Char | Related to `company_id.account_fiscal_country_id.code`. |
| `tax_country_id` | Many2one | Country for tax filtering. If fiscal position has `foreign_vat`, uses that country; otherwise uses `company.account_fiscal_country_id`. `compute_sudo=True`. |
| `tax_calculation_rounding_method` | Selection | Related to `company_id.tax_calculation_rounding_method`. |
| `company_price_include` | Selection | Related to `company_id.account_price_include`. |
| `has_active_pricelist` | Boolean | True if an active pricelist exists for the company. |
| `show_update_pricelist` | Boolean | Store=False. Set True when `pricelist_id` changes on existing draft order. Triggers "Update Prices" button. |
| `show_update_fpos` | Boolean | Store=False. Set True when `fiscal_position_id` changes on existing draft order. Triggers "Update Taxes" button. |

#### DB Index

```python
_date_order_id_idx = models.Index("(date_order desc, id desc)")
```
Optimizes the default order and common date-range queries.

---

### Model: `sale.order.line`

Represents individual lines in a sales order. Inherits from `analytic.mixin`.

#### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | Many2one | Parent order. `required=True`, `ondelete='cascade'`, `index=True`, `copy=False`. |
| `sequence` | Integer | Display order. `default=10`. |
| `display_type` | Selection | Type: `line_section`, `line_subsection`, `line_note`, or `False`. Controls line behavior. Section/Note lines have `product_uom_qty=0` enforced by `create()` override. |
| `is_downpayment` | Boolean | Marks this as a down payment line. Not copied when duplicating SO. |
| `is_expense` | Boolean | True if the line originates from an expense or vendor bill. |
| `company_id` | Many2one | Related from `order_id.company_id`. `store=True`, `index=True`, `precompute=True`. |
| `currency_id` | Many2one | Related from `order_id.currency_id`. `store=True`, `precompute=True`. |
| `order_partner_id` | Many2one | Related from `order_id.partner_id`. `store=True`, `index=True`, `precompute=True`. Used for search/filter. |
| `salesman_id` | Many2one | Related from `order_id.user_id`. `store=True`, `precompute=True`. |
| `state` | Selection | Related from `order_id.state`. `store=True`, `precompute=True`. |
| `tax_country_id` | Many2one | Related from `order_id.tax_country_id`. Used as domain filter for taxes. |

#### Product Fields

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | Many2one | Product variant. Domain: `sale_ok=True`. `change_default=True`, `ondelete='restrict'`, `index='btree_not_null'`. |
| `product_template_id` | Many2one | Product template. Computed from `product_id` but editable (unlike a `related`). Used by product configurator without modifying `product_id`. |
| `product_template_attribute_value_ids` | Many2many | Attribute values selected on the product variant. |
| `product_custom_attribute_value_ids` | One2many | Custom attribute values entered in the product configurator. |
| `product_no_variant_attribute_value_ids` | Many2many | Attribute values from `create_variant='no_variant'` attribute lines. |
| `name` | Text | Line description. Computed from product (`_get_sale_order_line_multiline_description_sale`). `store=True`, `precompute=True`. Honors partner language. |
| `translated_product_name` | Text | Translated product display name using partner language. |
| `categ_id` | Many2one | Product category. Related from `product_id.categ_id`. |
| `is_product_archived` | Boolean | True if `product_id.active == False`. |
| `is_configurable_product` | Boolean | Related to `product_template_id.has_configurable_attributes`. |

#### Quantity Fields

| Field | Type | Description |
|-------|------|-------------|
| `product_uom_qty` | Float | Quantity ordered. `default=1.0`, `digits='Product Unit'`. Computed to `0.0` for `display_type` lines. `store=True`. |
| `product_uom_id` | Many2one | Unit of measure. Computed from product if not set or mismatched. `store=True`. Domain: only `allowed_uom_ids`. |
| `allowed_uom_ids` | Many2many | UOMs allowed for this product. Computed from `product_id.uom_id` and `product_id.uom_ids`. |
| `customer_lead` | Float | Lead time in days. Computed to `0.0` by default. Overridden by sale_stock. Used in `_expected_date()`: `date_order + timedelta(days=customer_lead)`. |

#### Pricing Fields

| Field | Type | Description |
|-------|------|-------------|
| `tax_ids` | Many2many | Account taxes. Computed from product taxes, filtered by company, then mapped through fiscal position. Uses cache for performance. Domain: `type_tax_use='sale'` and `country_id=tax_country_id`. `context={'active_test': False}` so archived taxes are considered. |
| `pricelist_item_id` | Many2one | The pricelist rule used for price/discount computation. Cached on line. |
| `price_unit` | Float | Unit price. Computed from pricelist. Stored. `min_display_digits='Product Price'`. `required=True`. |
| `technical_price_unit` | Float | Shadow field. Stores the manual or last-computed price without triggering recomputation. Compared against `price_unit` via `_compute_price_unit()` to detect manual edits. |
| `discount` | Float | Discount percentage. Computed from pricelist. Stored. `digits='Discount'`. Only non-zero if pricelist rule has discount and `_show_discount()` returns True. |

#### Amount Fields

| Field | Type | Description |
|-------|------|-------------|
| `price_subtotal` | Monetary | Subtotal (untaxed). Stored. Computed via account tax engine. |
| `price_tax` | Float | Tax amount. Stored. `price_total - price_subtotal`. |
| `price_total` | Monetary | Total including tax. Stored. |
| `price_reduce_taxexcl` | Monetary | Unit price after discount, before tax. `price_subtotal / product_uom_qty`. |
| `price_reduce_taxinc` | Monetary | Unit price after discount, after tax. `price_total / product_uom_qty`. |
| `extra_tax_data` | Json | Technical JSON. Stores tax computation details for down payments and global discounts, enabling reversal on final invoice creation. |

#### Delivery Fields

| Field | Type | Description |
|-------|------|-------------|
| `qty_delivered_method` | Selection | Method: `manual` (default for consu/service) or `analytic` (from expenses). |
| `qty_delivered` | Float | Delivered quantity. `default=0.0`. Computed from analytic lines or set manually. `store=True`, `copy=False`. |

#### Invoicing Fields

| Field | Type | Description |
|-------|------|-------------|
| `qty_invoiced` | Float | Total invoiced quantity (invoices + refunds). Stored. |
| `qty_invoiced_posted` | Float | Invoiced quantity from posted invoices only. |
| `qty_to_invoice` | Float | Computed: `ordered_qty - qty_invoiced` (order policy) or `qty_delivered - qty_invoiced` (delivery policy). Combo lines have special handling. Stored. |
| `invoice_lines` | Many2many | Invoice lines linked to this SO line via `sale_order_line_invoice_rel`. |
| `invoice_status` | Selection | Per-line status: `upselling`, `invoiced`, `to invoice`, `no`. Stored. |
| `untaxed_amount_invoiced` | Monetary | Sum of posted invoice line subtotals minus refunds. |
| `amount_invoiced` | Monetary | Amount invoiced including tax. `compute_sudo=True`. Handles refunds via `direction_sign`. |
| `untaxed_amount_to_invoice` | Monetary | Remaining untaxed amount to invoice. |
| `amount_to_invoice` | Monetary | Remaining amount to invoice including tax. `compute_sudo=True`. |
| `amount_to_invoice_at_date` | Float | Amount to invoice at a specific accrual date. Context-driven. |

#### Analytic Fields

| Field | Type | Description |
|-------|------|-------------|
| `analytic_line_ids` | One2many | Analytic lines linked from expense/vendor bills. Inverse of `account.analytic.line.so_line`. Used by `_compute_qty_delivered` for `analytic` delivery method. |

#### Section/Subsection Fields

| Field | Type | Description |
|-------|------|-------------|
| `parent_id` | Many2one | Parent section or subsection line. Computed via `_compute_parent_id()`. Hierarchy used for collapse/display logic. |
| `collapse_prices` | Boolean | Hide prices of child lines in reports and portal. `copy=True`, `default=False`. |
| `collapse_composition` | Boolean | Hide child lines themselves in reports and portal. `copy=True`, `default=False`. |

#### Linked Lines (Optional/Combo Products)

| Field | Type | Description |
|-------|------|-------------|
| `linked_line_id` | Many2one | Main line this optional line is linked to. `domain=[('order_id','=',order_id)]`, `copy=False`, `index=True`. |
| `linked_line_ids` | One2many | Optional lines linked to this main line. |
| `virtual_id` | Char | Temporary ID for unsaved lines. Used before record has an `id`. |
| `linked_virtual_id` | Char | Links to another line's `virtual_id`. |
| `combo_item_id` | Many2one | Combo item (if product is type `combo`). Read-only in UI. |
| `selected_combo_items` | Char | JSON string storing selected combo items before lines are created. |

#### UX/State Computed Fields

| Field | Type | Description |
|-------|------|-------------|
| `product_type` | Selection | Related to `product_id.type`. |
| `service_tracking` | Selection | Related to `product_id.service_tracking`. |
| `product_updatable` | Boolean | False if: `is_downpayment`, `cancel` state, or `sale` state with locked/lines invoiced or delivered. |
| `product_uom_readonly` | Boolean | True if order is in `sale` or `cancel` state and line has an ID. |
| `sale_line_warn_msg` | Text | Product warning message. Only populated if user has `sale.group_warning_sale`. |

---

### Model: `account.analytic.line` (extension)

| Field | Type | Description |
|-------|------|-------------|
| `so_line` | Many2one | Many2one to `sale.order.line`. Domain: `qty_delivered_method='analytic'`. `index='btree_not_null'`. Added via `analytic.py`. Used for expense-based delivered qty tracking. |

The `account.analytic.applicability` model is also extended to add `('sale_order', 'Sale Order')` to `business_domain` selection, enabling analytic distribution rules to apply to SO lines.

---

### Model: `payment.transaction` (extension)

| Field | Type | Description |
|-------|------|-------------|
| `sale_order_ids` | Many2many | Sales orders linked to this transaction. |
| `sale_order_ids_nbr` | Integer | Count of linked SOs. Computed. |

Key methods:
- `_post_process()`: Main payment post-processing hook. Handles pending (send quotation email), authorized (confirm order), and done (confirm + auto-invoice) states.
- `_check_amount_and_confirm_order()`: Checks if `amount_paid >= prepayment_required_amount` and calls `action_confirm()`.
- `_invoice_sale_orders()`: Creates down payment invoices for partially paid orders and final invoices for fully paid orders.
- `_compute_sale_order_reference()`: Generates payment reference based on provider config (`so_name` or `partner` reference type).

---

## L2: Field Types, Defaults, Constraints, Why Fields Exist

### Field Type Deep Dives

#### `state` Selection — Why Readonly and Copy=False

`sale.order.state` is `readonly=True` because transitions must go through explicit action methods (`action_confirm`, `action_cancel`, `action_draft`, `action_quotation_sent`). This enforces the state machine workflow and ensures all business logic (validation, locking, picking creation) runs at each transition. `copy=False` because copying a state makes no business sense.

#### `technical_price_unit` — Shadow Price Preservation

This field exists because the `price_unit` field is computed and stored. When a user manually sets a price, that value is stored in `technical_price_unit`. On subsequent recomputation, `_compute_price_unit()` compares `technical_price_unit` with `price_unit` via `currency.compare_amounts()`. If they match (no manual change), the price is recomputed from the pricelist. If they differ (manual edit), the price is preserved.

This pattern prevents silent price overwrites when users negotiate custom pricing.

#### `price_unit` Compute Skips

`_compute_price_unit()` skips recomputation when:
1. Line has been invoiced (`qty_invoiced > 0`)
2. Line comes from an expense with cost-based pricing (`product_id.expense_policy == 'cost' and is_expense`)
3. Context has `force_price_recomputation=True` (used by "Update Prices" button)
4. `technical_price_unit` matches `price_unit` (manual price preserved)

#### `product_uom_qty` for Display Types

When a line with `display_type` is created, `create()` forcibly sets `product_uom_qty = 0.0`. This is enforced even if the input value is non-zero, and is part of the `_non_accountable_null_fields` SQL constraint.

#### `discount` — Zero for Manual Prices

The discount is only computed from the pricelist when a pricelist rule exists AND `_show_discount()` returns True. If the user manually edited the price (detected via `technical_price_unit != price_unit`), the discount is not overwritten because the price was set manually. Discount is stored to allow reporting.

#### `tax_ids` Fiscal Position Mapping Cache

Taxes are mapped through the fiscal position in `_compute_tax_ids()`. The result is cached per `(fiscal_position_id, company_id, tuple(tax_ids))` key + a hook `_get_custom_compute_tax_cache_key()` for extensions. This avoids repeated `map_tax()` calls on large orders.

#### `extra_tax_data` — Tax Engine Bridge

This Json field stores raw tax computation results from the account tax engine. For down payments, it enables:
1. Reversal of the down payment tax on the final invoice (`_reverse_quantity_base_line_extra_tax_data`)
2. Proper tax handling when down payment quantity is `-1.0` on final invoice

#### `combo_item_id` Constraint

`_check_combo_item_id()` validates that:
1. `combo_item_id` is among the allowed combo items of the linked line's product template
2. `combo_item_id.product_id` matches the line's `product_id`

This is a `constrains` method (not a simple onchange) because it must fire on write to prevent programming errors.

---

### SQL Constraints

```python
# sale.order
_date_order_conditional_required = models.Constraint(
    "CHECK((state = 'sale' AND date_order IS NOT NULL) OR state != 'sale')",
    'A confirmed sales order requires a confirmation date.',
)

# sale.order.line — Accountable lines (product lines) must have product + uom
_accountable_required_fields = models.Constraint(
    "CHECK(display_type IS NOT NULL OR is_downpayment OR "
    "(product_id IS NOT NULL AND product_uom_id IS NOT NULL))",
    'Missing required fields on accountable sale order line.',
)
# sale.order.line — Non-accountable lines (section/note) must have all product fields null/zero
_non_accountable_null_fields = models.Constraint(
    "CHECK(display_type IS NULL OR (product_id IS NULL AND price_unit = 0 AND "
    "product_uom_qty = 0 AND product_uom_id IS NULL AND customer_lead = 0))",
    'Forbidden values on non-accountable sale order line',
)

# res.company
_check_quotation_validity_days = models.Constraint(
    "CHECK(quotation_validity_days >= 0)",
    'You cannot set a negative number for the default quotation validity.',
)
```

---

## L3: Cross-Model Relationships, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Model Relationship Map

```
sale.order
├── partner_id (res.partner) ────────► address_get() for invoice/delivery addresses
├── company_id (res.company) ────────► currency, quotation_validity_days, portal settings
├── pricelist_id (product.pricelist) ──► currency, price computation
├── fiscal_position_id ──────────────► map_tax(), _get_fiscal_position()
├── payment_term_id ────────────────► early payment discount computation
├── user_id (res.users) ────────────► crm.team computation
├── team_id (crm.team) ─────────────► sales team routing
├── order_line ─────────────────────► sale.order.line (1:N, cascade delete)
│   └── product_id ─────────────────► product.product
│       └── taxes_id ────────────────► account.tax (mapped via fiscal position)
├── invoice_ids ────────────────────► account.move (via invoice_lines on lines)
├── transaction_ids ────────────────► payment.transaction
├── campaign_id, medium_id, source_id ──► utm.campaign, utm.medium, utm.source
├── tag_ids ────────────────────────► crm.tag
└── analytic_distribution ───────────► account.analytic.distribution (on lines)

sale.order.line
├── order_id ───────────────────────► sale.order
├── product_id ─────────────────────► product.product
├── tax_ids ───────────────────────► account.tax (mapped)
├── invoice_lines ─────────────────► account.move.line (M2M via sale_order_line_invoice_rel)
├── analytic_line_ids ─────────────► account.analytic.line (so_line inverse)
├── linked_line_id / linked_line_ids ──► self-referential for optional products
└── combo_item_id ─────────────────► product.combo.item

account.analytic.line
└── so_line ────────────────────────► sale.order.line (domain: qty_delivered_method='analytic')

payment.transaction
└── sale_order_ids ────────────────► sale.order (M2M)
```

### Workflow Triggers

#### Quotation Sent (`action_quotation_sent`)
- Requires `state == 'draft'`. Raises `UserError` otherwise.
- Writes `state = 'sent'`.
- If `mark_so_as_sent` context is set, `message_post()` also transitions draft to sent.

#### Order Confirmation (`action_confirm`)
Triggered by: customer signature, online payment authorization, manual confirmation button, or `_check_amount_and_confirm_order()`.

Steps executed in order:
1. **Validation loop**: `_confirmation_error_message()` checks for missing products and invalid state.
2. **Analytic validation**: `order_line._validate_analytic_distribution()` ensures analytic distribution is complete.
3. **Write confirmation values**: `write(_prepare_confirmation_values())` sets `state='sale'` and `date_order=now()`.
4. **Hook `_action_confirm()`**: Empty in core sale; extended by `sale_stock` to create pickings.
5. **Auto-lock**: If `sale.group_auto_done_setting` is enabled, `action_lock()` is called.
6. **Email**: If `send_email` context, `_send_order_confirmation_mail()` is dispatched (async or sync based on `sale.async_emails` ICP).

#### Cancellation (`action_cancel`)
1. Raises `UserError` if any order is `locked`.
2. Cancels draft invoices via `button_cancel()`.
3. Writes `state = 'cancel'`.

**Failure modes**:
- Cannot cancel locked orders without first unlocking.
- Cancelled invoices remain in draft state; only draft invoices are auto-cancelled.

#### Upsell Activity Creation
When `invoice_status` transitions to `'upselling'` (tracked via `_origin.invoice_status != 'upselling'` in `_compute_field_value`):
- Existing `mail.mail_activity_data_todo` activities are unlinked.
- New activity is scheduled on `order.user_id` or `order.partner_id.user_id`.

### Override Patterns

| Override Method | Purpose | Key Extension Point |
|----------------|---------|--------------------|
| `_action_confirm()` | Post-confirmation side effects | `sale_stock` creates pickings |
| `_prepare_confirmation_values()` | Modify values written on confirm | Add fields to write on confirm |
| `_prepare_invoice()` | Add fields to invoice values | Add UTM, references, custom fields |
| `_get_invoiceable_lines(final)` | Filter lines to invoice | Filter out specific line types |
| `_get_priced_lines()` | Lines used in tax computation | Exclude lines from amounts |
| `_compute_expected_date()` | Compute delivery promise date | `sale_stock` combines pickings |
| `_compute_taxes()` / `_compute_amount()` | Tax computation | Override tax engine behavior |
| `_get_custom_compute_tax_cache_key()` | Cache key for tax mapping | Tax caching extension |
| `_is_delivery()` | Whether line is a delivery line | Used in expected date calc |
| `_get_downpayment_description()` | Description for down payment lines | Custom DP naming |

### Payment Confirmation Flow

```
Customer initiates payment
        │
        ▼
payment.transaction._post_process()
        │
        ├─ state='pending': action_quotation_sent() if draft, send payment email
        │
        ├─ state='authorized': _check_amount_and_confirm_order()
        │                            │
        │                            ▼
        │              Check: amount_paid >= amount_total * prepayment_percent
        │                            │
        │              Yes ──► action_confirm() (send_email=True)
        │              No  ──► _send_payment_succeeded_for_order_mail()
        │
        └─ state='done': _check_amount_and_confirm_order() + auto_invoice
                              │
                              ▼
               sale.automatic_invoice ICP check
                              │
                              ▼
              _invoice_sale_orders() ──► Creates down payment invoice for
               (for partial payments)    partially paid orders, final invoice
                                        for fully paid orders
```

### Invoice Grouping

When `grouped=False` (default), invoices are grouped by:
- `company_id`, `partner_id`, `partner_shipping_id`, `currency_id`, `fiscal_position_id`

Orders sharing all these keys are merged into a single invoice. `ref`, `invoice_origin`, and `payment_reference` are concatenated.

---

## L4: Performance Implications, Odoo 18→19 Changes, Security, Edge Cases

### Performance Implications

#### 1. Trigram Index on `name`
The `index='trigram'` on `sale.order.name` enables fast `ilike` searches in portal and eCommerce. However, trigram indexes are larger than btree indexes. For pure equality searches, btree remains faster.

#### 2. Duplicate Order Detection — Raw SQL
`_fetch_duplicate_orders()` uses a direct SQL query via `execute_query(SQL(...))` to avoid N+1 problems when checking duplicates across large datasets. The ORM-based approach would require multiple joins through `sale_order_line` table.

#### 3. Tax Computation Caching
`_compute_tax_ids()` caches fiscal position mapping results per `(fpos_id, company_id, tax_ids_tuple)` key. For orders with many lines sharing the same fiscal position, this avoids repeated `map_tax()` calls. The cache is per-recordset computation cycle.

#### 4. `_compute_amounts()` — Tax Engine Integration
`AccountTax._add_tax_details_in_base_lines()` and `_round_base_lines_tax_details()` are called on every amount compute. These methods interact with the account tax engine which maintains its own state. For orders with many lines, early payment discount lines (`_add_base_lines_for_early_payment_discount()`) add extra base lines for each SOL.

#### 5. `_get_invoiceable_lines()` — Linear Scan
This method iterates over all order lines and tracks section/subsection context. For very long orders, this is O(n) with constant factors from the display type grouping logic. No optimization is applied.

#### 6. Precompute=True on All Computed Fields
The sale module precomputes as many fields as possible (`precompute=True` on most computed-stored fields) to reduce write-time cascades. This is a deliberate trade-off: faster writes at the cost of slightly slower reads on first save. The comment in the code explicitly notes this is a performance optimization.

#### 7. `sale_order_line_invoice_rel` Join Table
Invoice line linkage uses a dedicated M2M table (`sale_order_line_invoice_rel`). Invoice search in `_search_invoice_ids()` uses raw SQL with `array_agg` for performance when searching by invoice ID.

### Odoo 18 → 19 Breaking Changes

#### 1. `done` State Replaced by `locked` Boolean
```python
# Odoo 18
SALE_ORDER_STATE = [
    ('draft', "Quotation"), ('sent', "Quotation Sent"),
    ('sale', "Sales Order"), ('done', "Locked"), ('cancel', "Cancelled"),
]

# Odoo 19
SALE_ORDER_STATE = [
    ('draft', "Quotation"), ('sent', "Quotation Sent"),
    ('sale', "Sales Order"), ('cancel', "Cancelled"),
]
# locked is now a separate boolean field
```
**Migration impact**: Any code checking `state == 'done'` must be updated to check `locked == True`. The `done`→`cancel` transition no longer exists.

#### 2. Tax Computation Engine Migration
Odoo 19 delegates all tax computation to `account.tax`:
- `_prepare_base_line_for_taxes_computation()` converts a SOL to a dict format expected by the account tax engine.
- `AccountTax._add_tax_details_in_base_lines()` populates tax details in-place.
- `AccountTax._round_base_lines_tax_details()` rounds per line.
- `AccountTax._get_tax_totals_summary()` returns aggregated totals.

This change means:
- `price_subtotal` is no longer computed as `price_unit * qty * (1 - discount/100)`. It comes from `tax_details['total_excluded_currency']`.
- Down payment tax data is stored in `extra_tax_data` and reversed on final invoice creation.
- Global discounts now use `special_type='global_discount'` in the base line.

**Migration impact**: Custom modules overriding `_compute_amount()` or `_compute_amounts()` may need to adopt the tax engine pattern.

#### 3. `_is_confirmation_amount_reached()` Replaces Simple Payment Check
In Odoo 18, online payment confirmed an order as long as any amount was paid. In Odoo 19, the payment must reach `amount_total * prepayment_percent` (controlled by `company.prepayment_percent`). The default is `1.0` (100%), meaning full payment is required by default.

**Migration impact**: If you relied on automatic confirmation on any payment, you must now configure `prepayment_percent` or call `action_confirm()` manually.

#### 4. `require_payment` No Longer Auto-enabled
Odoo 18 had `portal_confirmation_pay` defaulting to True in some configurations. In Odoo 19, `portal_confirmation_pay` defaults to `False`. Online payment must be explicitly enabled.

#### 5. Async Email Sending
The `sale.async_emails` ICP controls whether order confirmation emails are sent via a cron job (`sale.send_pending_emails_cron`) instead of synchronously. This prevents timeouts on bulk confirmations.

#### 6. Combo Product Support
Odoo 19 introduces `combo` product type support in the sale module core:
- `combo_item_id`, `selected_combo_items`, `linked_virtual_id` fields.
- `_onchange_order_line()` handles combo item line creation/deletion.
- Combo lines have `price_unit=0` (display price comes from combo product).
- `_get_combo_item_display_price()` prorates the combo product's price across its items.

#### 7. `_prepare_base_line_for_taxes_computation()` Hook
This method was introduced in Odoo 19 to bridge sale line fields to the account tax engine. It handles:
- Normal lines: standard base line dict
- Global discount lines: adds `special_type='global_discount'`
- Down payment lines: adds `special_type='down_payment'`

### Security Considerations

#### 1. Locked Order Protection
Locked orders cannot have these fields modified (enforced via `_get_protected_fields()` + `ir.model.fields` lookup):
- `product_id`, `name`, `price_unit`, `product_uom_id`, `product_uom_qty`, `tax_ids`, `analytic_distribution`, `discount`

The exception: `name` **can** be modified on a locked order if ALL modified lines are down payments (`is_downpayment`).

#### 2. Access Rights for Invoice Creation
Salespersons without `account.group_account_invoice` write access can still trigger invoice creation through `_create_account_invoices()` which runs in `sudo()`. This is intentional — salespeople can invoice from SO without having direct account move creation rights.

#### 3. Credit Limit Check
`_compute_partner_credit_warning()` converts the order's total to company currency before checking against the partner's credit limit. The `amount_to_invoice` from SOs is factored into `credit_to_invoice` on the partner via `_compute_credit_to_invoice()` in `res_partner.py`.

#### 4. Analytic Distribution Validation
`_validate_analytic_distribution()` is called before sending quotation and before confirming. This prevents confirming an order without required analytic distribution on lines.

#### 5. Multi-company
Orders and lines are protected by `_check_company_auto = True` and the `_check_order_line_company_id` constraint. Products from other companies cannot be added to an order.

#### 6. Portal Access
`portal.mixin` integration provides access URLs (`/my/orders/<id>`) and access control. UTM source/campaign/medium are tracked on SO but not enforced for access.

### Edge Cases

#### 1. Down Payment + Final Invoice
When a final invoice is created (`final=True`) for an order that has down payment lines:
- Down payment lines have `quantity = -1.0` and reversed `extra_tax_data`
- This effectively subtracts the down payment from the final invoice totals
- The down payment's invoice line uses the account from the original down payment invoice

#### 2. Combo Product Lines — Invoice as Section
Combo product lines are invoiced as a `line_section` (display_type only) rather than a product line. The section header shows `"{combo_product.name} x {qty}"`. Combo item lines (the actual products) are not individually invoiced; their price is embedded in the combo product's price.

#### 3. Refund Increases `qty_invoiced` Negatively
`_prepare_qty_invoiced()` adds invoice quantities with `direction_sign`: positive for invoices, negative for refunds. A refund line with quantity 5 reduces `qty_invoiced` by 5, potentially making `qty_to_invoice` larger than `product_uom_qty`.

#### 4. `is_expired` — Only for Draft/Sent
An order in `sale` or `cancel` state is never considered expired, even if `validity_date` has passed. The validity date is only a quotation expiration mechanism.

#### 5. `_has_to_be_signed()` / `_has_to_be_paid()` — Portal Conditions
These methods gate the portal quotation acceptance buttons:
- `_has_to_be_signed()`: requires `require_signature`, `not signature`, `not is_expired`, `state in ['draft','sent']`
- `_has_to_be_paid()`: requires `require_payment`, `amount_total > 0`, `not _is_confirmation_amount_reached()`, `not is_expired`, `state in ['draft','sent']`

#### 6. `only_prepaid_line` / `is_all_rows_have_valid_product` / `has_available_pricelist`
These fields mentioned in the prompt do not exist in the Odoo 19 core sale module. They may exist in `sale_management` or be specific implementation fields. `has_available_pricelist` is similar to `has_active_pricelist` (which does exist). Check `sale_management` module for template-related fields.

#### 7. `amount_net_tax` / `user_company_works_pacakge`
These fields do not exist in Odoo 19 core sale. `amount_net_tax` may be computed as `amount_untaxed` — the net tax amount (excluding tax) is the untaxed subtotal. `user_company_works_package` appears to be a mistyping or non-existent field.

#### 8. Pricelist Change on Confirmed Order
`write()` explicitly prevents changing `pricelist_id` on a confirmed order:
```python
if 'pricelist_id' in vals and any(so.state == 'sale' for so in self):
    raise UserError(_("You cannot change the pricelist of a confirmed order !"))
```

#### 9. Early Payment Discount with Mixed Tax Computation
When `payment_term_id.early_pay_discount_computation == 'mixed'`:
- `_add_base_lines_for_early_payment_discount()` creates extra base lines representing the discount
- Taxes are computed on the discounted amount, matching account module behavior
- This requires extra processing in `_compute_amounts()` but is accurate for reporting

#### 10. Duplicate Name Handling
If `ir.sequence.next_by_code()` returns the same "New" value for multiple concurrent creates, the unique constraint on `name` will cause one to fail. The ORM handles the retry internally.

---

## Wizard: `sale.advance.payment.inv`

Creates down payment invoices or regular invoices from sales orders. Transient model.

| Field | Type | Description |
|-------|------|-------------|
| `advance_payment_method` | Selection | `delivered` (regular invoice), `percentage` (DP %), `fixed` (DP fixed). |
| `count` | Integer | Number of selected orders. |
| `sale_order_ids` | Many2many | Orders to invoice. |
| `has_down_payments` | Boolean | True if any selected order already has DP lines. |
| `deduct_down_payments` | Boolean | Default True. If True, final invoice deducts previously invoiced DP amounts. |
| `amount` | Float | Percentage for `percentage` DP. |
| `fixed_amount` | Monetary | Fixed amount for `fixed` DP. |
| `currency_id` | Many2one | Order currency. Only set when `count == 1`. |
| `company_id` | Many2one | Order company. Only set when `count == 1`. |
| `amount_invoiced` | Monetary | Already invoiced amount across all selected orders. |
| `consolidated_billing` | Boolean | Default True. Groups invoices by partner+addresses. |

**Key business methods:**
- `_create_invoices()`: Dispatches to `sale_orders._create_invoices()` for regular invoices, or creates DP-specific invoice via `AccountTax._prepare_down_payment_lines()`.
- `_prepare_down_payment_invoice_values()`: Uses `order._prepare_invoice()` plus DP-specific line values.
- `_get_down_payment_account()`: Falls back to `downpayment` account then `income` account from product.

---

## Wizard: `sale.order.discount`

Applies discounts to a sale order. Transient model.

| Field | Type | Description |
|-------|------|-------------|
| `discount_type` | Selection | `sol_discount` (per-line %), `so_discount` (global %), `amount` (fixed amount). |
| `discount_percentage` | Float | Percentage (0-1 range enforced by constraint). |
| `discount_amount` | Monetary | Fixed amount. |

**Behavior:**
- `sol_discount`: Writes `discount` field directly on all non-display-type lines.
- `so_discount` or `amount`: Creates new SO lines via `AccountTax._prepare_global_discount_lines()`.
  - Uses `company.sale_discount_product_id` (auto-created as service if not set).
  - Sets `extra_tax_data` with `special_type='global_discount'`.
  - Creates separate lines per tax group if multiple tax combinations exist.

---

## Cron Jobs

| Cron | Model | Purpose | Frequency |
|------|-------|---------|-----------|
| `sale.send_pending_emails_cron` | `sale.order` | Sends deferred order confirmation emails. Triggered when `sale.async_emails` is enabled and `pending_email_template_id` is set. |
| `sale.send_invoice_cron` | `payment.transaction` | Retries sending invoices not ready at posting time. Only active if `sale.automatic_invoice` is enabled. Runs on transactions with `last_state_change >= 2 days ago`. |

---

## Key Extension Hooks for Customization

| Hook Method | When Called | Override Pattern |
|-------------|------------|-----------------|
| `_action_confirm()` | After state changes to `sale` | Call `super()`, then add side effects |
| `_prepare_confirmation_values()` | Before `write()` on confirm | Return dict, merge into write vals |
| `_get_invoiceable_lines(final)` | In `_create_invoices()` | Filter lines, preserve section logic |
| `_prepare_invoice()` | Before invoice creation | Add fields to invoice vals dict |
| `_compute_expected_date()` | On expected_date compute | Combine lead times, handle delivery |
| `_create_upsell_activity()` | When invoice_status == 'upselling' | Schedule activity on user |
| `_add_base_lines_for_early_payment_discount()` | In `_compute_amounts()` | Add EPD base lines |
| `_get_custom_compute_tax_cache_key()` | In tax cache lookup | Add extension-specific cache keys |
| `_is_delivery()` | In expected date computation | Mark lines as non-delivery |
| `_get_downpayment_description()` | In name computation | Custom DP naming |
| `_get_product_catalog_order_data()` | In catalog display | Add price warnings |

---

## Portal Integration

Customers can:
1. View quotations and orders via `/my/orders/<id>`
2. Sign orders online (if `require_signature`, not yet signed, not expired)
3. Pay orders online (if `require_payment`, not fully paid, not expired)
4. Download invoices
5. Track delivery status (via `sale_stock`)

Access token is generated via `portal.mixin._portal_ensure_token()`. Portal access uses the access URL pattern `/my/orders/{order.id}`.

The `_notify_get_recipients_groups()` method customizes the portal button title based on state and payment status:
- "Sign & Pay Quotation" — requires both signature and payment
- "Accept & Sign Quotation" — signature only
- "Accept & Pay Quotation" — payment only
- "View Quotation" — neither required

---

## SQL Tables

| Table | Notes |
|-------|-------|
| `sale_order` | Main table. `name` has trigram index. `_date_order_id_idx` composite index. |
| `sale_order_line` | Lines. `_order = 'order_id, sequence, id'`. Constraints enforce accountable/non-accountable field rules. |
| `sale_order_line_invoice_rel` | M2M join table for invoice line linkage. |
| `sale_order_transaction_rel` | M2M join table for payment transaction linkage. |
| `sale_order_tag_rel` | M2M join table for CRM tag linkage. |

---

## L3 Expanded: Cross-Module Integration Details

### Sale ↔ Stock: Delivery Creation (via `sale_stock`)

When `sale_stock` is installed, `sale.order._action_confirm()` is extended:

```python
# From: sale_stock/models/sale_order.py
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _action_confirm(self):
        self.order_line._action_launch_stock_rule()
        return super()._action_confirm()
```

`stock.rule._action_launch_stock_rule()` creates `stock.picking` records for each line. The picking type is determined by the warehouse (`order_id.warehouse_id`). If no warehouse is set on the order, it falls back to `company.warehouse_id`.

**Failure mode — Product out of stock:**
The procurement is created but the picking remains in `assigned` or `waiting` state depending on `procurement.group` availability. If the product has `route_ids` configured (e.g., "Drop Shipping"), the rule may create a purchase order instead of a picking. Stock availability warnings do NOT block order confirmation — they only create a warning banner on the SO form via `has_archived_products`-style logic.

### Sale ↔ Account: Invoice Creation (`_create_invoices()`)

```python
# sale_order.py — invoice creation dispatches to account.move
sale_orders._create_invoices(grouped=False, final=False)
```

`account.move` is created with `move_type='out_invoice'`. The invoice date comes from `_prepare_invoice()`:
- `invoice_date`: `fields.Date.context_today(self, self.invoice_date)`
- `invoice_origin`: `self.name` (the SO reference)
- `ref`: `self.reference` (payment ref from online payment)

**Invoice grouping**: When `grouped=True`, multiple SOs share one invoice. Grouping keys are `(company_id, partner_id, partner_shipping_id, currency_id, fiscal_position_id)`. The `ref`, `invoice_origin`, and `payment_reference` fields are concatenated.

### Sale ↔ CRM: Quotations from CRM (via `crm`)

When a SO is created from a CRM opportunity (`crm.lead`):
- `origin` field is set to the lead's name
- UTM fields (`campaign_id`, `medium_id`, `source_id`) are populated from the lead
- `team_id` is set from the lead's team

The `crm.lead._action_new_quotation()` method creates the SO and links it back via `order_ids`.

### Sale ↔ Project: Task Creation (via `sale_project`)

`sale_project` overrides `sale.order.line._compute_invoice_status()` and `product_id.service_tracking` fields:
- `service_tracking='task'`: Creates a project task per line on `action_confirm()`
- `service_tracking='project_only'`: Creates project and task template only, no per-line task
- `service_tracking='no'`: No project/task integration

---

### L3: Failure Modes

#### 1. Partner Address Changes Mid-Process

When `partner_invoice_id` or `partner_shipping_id` changes on a confirmed order:
- The change IS allowed (no lock check on address fields)
- `fiscal_position_id` may change as a consequence (computed from new address)
- `show_update_fpos` is set to True, triggering "Update Taxes" button
- No automatic tax update occurs — user must manually click "Update Taxes"

If `partner_id` itself changes (not just addresses):
- `pricelist_id` is recomputed (but blocked on sale state: `write()` raises error)
- Fiscal position is recomputed
- `show_update_fpos` is triggered

#### 2. Stock Availability at Confirmation

`sale_stock._action_confirm()` does NOT block on stock availability. Pickings are created in `assigned` state if products are available, `waiting` if not. The order can be fully invoiced and paid before any product is delivered.

#### 3. Product Archived After Order Confirmed

`has_archived_products` is a computed warning field (not a blocker). A line with an archived product:
- `is_product_archived = True` on the SOL
- `sale_line_warn_msg` displays the warning
- No prevention of invoicing or further processing

---

## L4 Expanded: Security, Performance, Extra Features

### L4: Security — Readonly Fields After Confirmation

After an order moves to `sale` state:

| Field | State | Can Be Edited? |
|-------|-------|---------------|
| `partner_id` | sale | No — `write()` prevents any change on confirmed orders |
| `pricelist_id` | sale | No — raises `UserError` in `sale.order.write()` |
| `date_order` | sale | No — conditional SQL constraint: `state='sale' implies date_order IS NOT NULL` |
| `order_line.product_id` | sale | Only if `locked=False` |
| `order_line.price_unit` | sale | Only if `locked=False` and `qty_invoiced == 0` |
| `order_line.product_uom_qty` | sale | Only if `locked=False` and not fully delivered |
| `order_line.discount` | sale | Only if `locked=False` |
| `order_line.tax_ids` | sale | Only if `locked=False` |
| `partner_invoice_id` | sale | Yes — address changes are always allowed |
| `partner_shipping_id` | sale | Yes — address changes are always allowed |
| `fiscal_position_id` | sale | Yes — but triggers `show_update_fpos` warning |

The locked protection is enforced via `_get_protected_fields()` which queries `ir.model.fields` with `group_id` matching the lock group. Lines with `is_downpayment=True` have an exception: their `name` can be edited even on locked orders.

**Important**: Unlike `state`, the `locked` boolean does NOT make fields readonly via the field definition. Protection is enforced only in `write()` via `_get_protected_fields()`. If you access the recordset directly in Python code (e.g., `order.order_line.write({...})`), the lock is bypassed unless you call `order._check_lock()` first.

### L4: Performance — Line Computation (Taxes, Discounts, Delivery Cost)

#### Tax Computation Flow per Line

`SaleOrderLine._compute_tax_ids()`:
1. Groups all lines by `company_id` to batch `with_company()` calls
2. For each line with a `product_id`, fetches `product_id.taxes_id`
3. Filters taxes by company via `_filter_taxes_by_company()`
4. If no taxes or no product, sets `tax_ids = False`
5. Otherwise, calls `fiscal_position.map_tax(taxes)` with result cached per `(fpos_id, company_id, tax_tuple)` + `_get_custom_compute_tax_cache_key()`

Cache invalidation: The cache lives for the duration of one `_compute_tax_ids()` call cycle (a fresh `defaultdict` per invocation). On the next compute (e.g., after a write), a new cache is built.

#### Discount Computation

`SaleOrderLine._compute_discount()`:
1. Checks if `pricelist_item_id` exists — without a pricelist rule, discount is always `0.0`
2. If rule has `compute_price='formula'` and `percent_price` is set, discount = `percent_price`
3. If rule has `compute_price='formula'` and `fixed_discount` is set, discount is computed proportionally
4. Discount is only non-zero if `_show_discount()` returns True (checks `pricelist_item_id.sequence <= 1`)
5. Manual prices: if `technical_price_unit != price_unit` (detected via `has_manual_price()`), discount is NOT recomputed — preserved from manual edit

#### Delivery Cost (via `sale_stock`)

`sale_stock` adds `is_delivery` flag to lines. Delivery lines have `display_type=False` but are excluded from tax totals by `_get_priced_lines()` which filters out `_is_delivery()` lines. Delivery lines are still included in `amount_total` via a separate `_add_delivery_line()` method on the order.

#### `_get_priced_lines()` — What Gets Taxed

Only lines where:
- `display_type == False` (no sections/notes)
- NOT a delivery line (not `_is_delivery()`)
- NOT a global discount line (`special_type != 'global_discount'`)

Down payment lines ARE included in `_get_priced_lines()` but use `special_type='down_payment'` in their tax base line.

### L4: Odoo 18 → 19 Additional Changes

#### 8. `show_update_pricelist` UX Field

Introduced in Odoo 19 to handle the pricelist change UX:

- `show_update_pricelist = True` (store=False) is set when:
  - The order has lines AND
  - The new `pricelist_id != _origin.pricelist_id` AND
  - The order is in `draft` state (onchange: `_onchange_pricelist_id_show_update_prices()`)
  - `sale_management._onchange_partner_id()` also triggers this when template is auto-reapplied

- When True, a banner appears with an "Update Prices" button
- Clicking "Update Prices" calls `action_update_prices()` which:
  1. Calls `_get_update_prices_lines()` (hook: filter lines to update)
  2. Invalidates `pricelist_item_id` cache
  3. Forces recompute of `price_unit` with `force_price_recomputation=True` context
  4. Resets `discount = 0.0` then recomputes discount from pricelist
  5. Sets `show_update_pricelist = False`

#### 9. `show_update_fpos` UX Field

Triggered by `_onchange_fpos_id_show_update_fpos()` when fiscal position changes on a draft/sent order with lines. The "Update Taxes" button calls `action_update_taxes()` which:
1. Calls `lines._compute_tax_ids()` to remap taxes
2. Sets `show_update_fpos = False`

#### 10. Down Payment Invoice Reversal on Final Invoice

When `final=True` is passed to `_create_invoices()` (regular invoice, not DP):
- For each DP line: creates an inverse line with `quantity = -1.0`
- Uses `extra_tax_data` (stored JSON) to reverse the tax amounts
- The reversal line uses the same account as the original DP invoice line

#### 11. `commitment_date` vs `expected_date`

- `commitment_date`: User-set promised delivery date. Stored. `copy=False`.
- `expected_date`: Computed from minimum `customer_lead` across lines + `date_order`. Non-stored (depends on `today()`).

When `commitment_date` is set, `expected_date` is not recomputed and the commitment date is used for picking scheduling instead. If `commitment_date < expected_date`, a warning is issued via `_compute_expected_date()`.

---

## L3+ L4: sale_management Extension (`sale.order` via `_inherit`)

The `sale_management` module adds `sale_order_template_id` to `sale.order`. This is a `_inherit` extension, not a new model.

### `sale.order` Fields Added by `sale_management`

| Field | Type | Notes |
|-------|------|-------|
| `sale_order_template_id` | Many2one | Quotation template. `check_company=True`, `store=True`, `readonly=False`. Domain restricts to company. |

### Template Auto-Application Logic

On **unsaved** orders, `company_id.sale_order_template_id` (from `res.company`) is auto-applied via `_compute_sale_order_template_id()` (triggered by `_onchange_company_id()`).

On unsaved orders with no manual modifications, `_onchange_partner_id()` re-applies the template if partner changes (only if `sale_order_template_id` already set and lines match).

### `sale_order_template_id` Onchange

`_onchange_sale_order_template_id()`:
1. Clears existing `order_line`
2. Creates new lines from template via `_prepare_order_line_values()` for each `sale.order.template.line`
3. First real line is given `sequence=-99` to prevent page-break mixing on multi-page templates
4. Uses partner language for template description (`with_context(lang=partner_id.lang)`)

### Template Override Points

| Method | What It Does |
|--------|-------------|
| `_compute_require_signature()` | If template set, overrides company default |
| `_compute_require_payment()` | If template set, overrides company default |
| `_compute_prepayment_percent()` | If template requires payment, uses template percentage |
| `_compute_validity_date()` | Sets `validity_date = today + number_of_days` from template |
| `_compute_journal_id()` | Uses template's journal if set |
| `_compute_note()` | Uses template's HTML note if not empty |
| `_get_confirmation_template()` | Returns template's `mail_template_id` if set |
| `action_confirm()` | Sends template's mail_template_id when confirming from backend |

---

## L3+ L4: `sale.order.template` (sale_management)

This is a standalone model in `sale_management/models/sale_order_template.py`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Template display name. Required. |
| `note` | Html | Terms and conditions. `translate=True` (translatable). |
| `sequence` | Integer | Ordering for template list. Default 10. |
| `active` | Boolean | Allows hiding without deleting. Default True. |
| `company_id` | Many2one | Template company scope. `default=lambda self: self.env.company`. |
| `mail_template_id` | Many2one | Email template for confirmation. Domain: `model='sale.order'`. |
| `number_of_days` | Integer | Validity duration in days. Used by `_compute_validity_date()`. |
| `require_signature` | Boolean | Computed from `company_id.portal_confirmation_sign`. |
| `require_payment` | Boolean | Computed from `company_id.portal_confirmation_pay`. |
| `prepayment_percent` | Float | Computed from company. Only used if `require_payment=True`. |
| `sale_order_template_line_ids` | One2many | Template lines. `copy=True`. |
| `journal_id` | Many2one | Invoicing journal override. Company-dependent. |

### Constraints

`_check_company_id()`: Prevents a shared template (no `company_id`) from containing products that are restricted to a specific company.

### `sale.order.template.line` (sale_management)

| Field | Type | Description |
|-------|------|-------------|
| `sale_order_template_id` | Many2one | Parent template. |
| `name` | Char | Line description. |
| `sequence` | Integer | Line order. |
| `product_id` | Many2one | Product. `sale_ok=True` enforced by domain. |
| `product_uom_qty` | Float | Default quantity. |
| `product_uom_id` | Many2one | UoM. |
| `discount` | Float | Default discount. |
| `company_id` | Many2one | Related from template. `store=True`, `index=True`. |

The `_prepare_order_line_values()` method converts a template line to a `sale.order.line` dictionary, mapping product/UOM/qty/discount directly. Tax IDs are NOT copied from template lines — they are recomputed from the product on the actual SO via `_compute_tax_ids()`.

---

## L4: Complete Action Method Reference

| Method | Args | Returns | When Called |
|--------|------|---------|------------|
| `action_confirm()` | — | `True` | Confirm button, payment authorized, customer signed |
| `_action_confirm()` | — | — | Hook after state='sale', no return value. Extended by sale_stock to launch procurement |
| `action_draft()` | — | `write()` dict | Cancel/sent → draft. Clears signature fields. |
| `action_quotation_send()` | — | `mail.compose.message` wizard | Send by email button |
| `action_quotation_sent()` | — | `True` | Internal state update (no email sent) |
| `action_lock()` | — | `True` | Sets `locked=True`. Called automatically when `group_auto_done_setting` enabled |
| `action_unlock()` | — | `True` | Sets `locked=False`. Available after confirm |
| `action_cancel()` | — | `write()` dict | Cancel button. Fails if locked. Cancels draft invoices then sets state=cancel |
| `action_preview_sale_order()` | — | `ir.actions.act_url` | Opens portal URL for the order |
| `action_update_taxes()` | — | `True` | Triggers tax recompute on lines. Posts chatter message. |
| `action_update_prices()` | — | `True` | Triggers price+discount recompute. Posts chatter message. |
| `action_open_business_doc()` | — | `ir.actions.act_window` | Opens related invoices, deliveries, or project tasks |
| `action_view_invoice()` | invoices | `ir.actions.act_window` | Jump to invoice list/form. Falls back to create wizard if no invoices. |
| `action_open_discount_wizard()` | — | `ir.actions.act_window` | Opens `sale.order.discount` wizard form |
| `_send_order_confirmation_mail()` | — | — | Sends confirmation email via `_send_order_notification_mail()` |
| `_action_cancel()` | — | `write()` dict | Internal cancel. Called by `action_cancel()` after draft invoice cancellation |

---

## L4: Key SQL Constraints and Indexes Reference

### Sale Order Table (`sale_order`)

```sql
-- Composite index for default ordering
CREATE INDEX sale_order_date_order_id_idx ON sale_order (date_order DESC, id DESC);

-- Trigram index for portal/eCommerce name search
-- Applied via: name = fields.Char(index='trigram', ...)
CREATE INDEX sale_order_name_trgm_idx ON sale_order USING gin (name gin_trgm_ops);

-- Conditional constraint: confirmed orders must have a date_order
ALTER TABLE sale_order ADD CONSTRAINT sale_order_date_order_conditional_required
    CHECK (state != 'sale' OR date_order IS NOT NULL);

-- Unique name via ir.sequence (not a DB constraint; ORM enforces retry on collision)
```

### Sale Order Line Table (`sale_order_line`)

```sql
-- Non-accountable lines (section/note) must have null/zero product fields
ALTER TABLE sale_order_line ADD CONSTRAINT sale_order_line_non_accountable_null_fields
    CHECK (display_type IS NULL OR (
        product_id IS NULL AND price_unit = 0 AND
        product_uom_qty = 0 AND product_uom_id IS NULL AND customer_lead = 0
    ));

-- Accountable lines must have product + uom
ALTER TABLE sale_order_line ADD CONSTRAINT sale_order_line_accountable_required_fields
    CHECK (display_type IS NOT NULL OR is_downpayment OR (
        product_id IS NOT NULL AND product_uom_id IS NOT NULL
    ));
```

### Company Table Constraint (sale module extends `res.company`)

```sql
-- Quotation validity days cannot be negative
ALTER TABLE res_company ADD CONSTRAINT res_company_check_quotation_validity_days
    CHECK (quotation_validity_days >= 0);
```

---

## L3+ L4: Line Qty Tracking Deep Dive

### Three Qty Fields and Their Differences

| Field | Stored | Compute Method | Used For |
|-------|--------|----------------|---------|
| `product_uom_qty` | Yes | User input (or template default) | The ordered quantity. Used in `qty_to_invoice` calculation. |
| `qty_delivered` | Yes | Manual (`qty_delivered_method='manual'`) or analytic sum | Delivery status. Invoicing policy uses this. |
| `qty_invoiced` | Yes | Sum of invoice line quantities (with sign: negative for refunds) | Determines if price can be changed. |
| `qty_to_invoice` | Yes | Computed. For `sale_s delivered`: `qty_delivered - qty_invoiced`. For `sale_s order`: `product_uom_qty - qty_invoiced`. |

### `qty_invoiced_posted` vs `qty_invoiced`

- `qty_invoiced`: Includes quantities from draft, posted, and cancelled invoices
- `qty_invoiced_posted`: Only posted invoices. Used for reporting accuracy.

### `qty_delivered_at_date` and `qty_invoiced_at_date`

Non-stored computed fields that take an optional `accrual_date` context:
```python
@api.depends_context('accrual_date')
def _compute_qty_delivered_at_date(self):
    for line in self:
        if self.env.context.get('accrual_date'):
            # Historical delivered qty at date
```

These are used by the account module's aged payables/receivables reports.

### Combo Lines Special Handling

For `product_type='combo'` lines:
- `qty_to_invoice = qty_delivered` (delivery policy is always used, even if SO has `sale_delivery` policy)
- `qty_delivered = 1.0` after confirmation (combo is always fully delivered)
- The combo item lines (actual products) are not individually invoiced — their price is embedded in the combo product price
