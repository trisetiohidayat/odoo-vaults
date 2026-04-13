---
type: module
name: sale
version: Odoo 18
models_count: ~15
documentation_date: 2026-04-11
tags: [sale, crm, commerce, quotations]
source: ~/odoo/odoo18/odoo/addons/sale/
---

# Sale

**Module:** `sale` | **Models:** `sale.order`, `sale.order.line`, `sale.order.tag`
**Source:** `~/odoo/odoo18/odoo/addons/sale/`

## Overview

Core sales order / quotation management. Handles the full lifecycle from draft quotation through confirmed sales order, with integrated pricing, invoicing, and delivery coordination.

**Key capabilities:**
- Quotation workflow with email templates
- Pricelist-driven pricing and discounts
- Combo product support (Odoo 18 new)
- Online signature and payment collection
- Automatic order locking on confirmation
- Multi-company support
- Portal integration for customer self-service
- Tax computation with fiscal position mapping
- Early payment discount support

**Depends:** `base`, `product`, `account`, `account_payment`, `analytic_account`, `mail`, `utm`, `portal`, `product_catalog`

## Models

### sale.order

Inherits: `portal.mixin`, `product.catalog.mixin`, `mail.thread`, `mail.activity.mixin`, `utm.mixin`
_order: `date_order desc, id desc`
_check_company_auto: True

**SQL Constraints:**
```python
('date_order_conditional_required',
 "CHECK((state = 'sale' AND date_order IS NOT NULL) OR state != 'sale')",
 "A confirmed sales order requires a confirmation date.")
```

**Database Index:**
```python
create_index(self._cr, 'sale_order_date_order_id_idx', 'sale_order', ["date_order desc", "id desc"])
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Order reference, sequence-generated, trigram indexed |
| `date_order` | Datetime | Order date (creation for draft, confirmation for confirmed) |
| `validity_date` | Date | Quotation expiry (computed from company.quotation_validity_days) |
| `partner_id` | Many2one | Customer (res.partner), required, tracking=1 |
| `partner_invoice_id` | Many2one | Invoice address, computed from partner.address_get |
| `partner_shipping_id` | Many2one | Delivery address, computed from partner.address_get |
| `order_line` | One2many | sale.order.line records, copy=True, auto_join=True |
| `state` | Selection | draft / sent / sale / cancel |
| `locked` | Boolean | Prevents editing when True |
| `amount_total` | Monetary | Total with taxes (stored, compute) |
| `amount_untaxed` | Monetary | Subtotal excl. taxes (stored, compute) |
| `amount_tax` | Monetary | Tax total (stored, compute) |
| `amount_to_invoice` | Monetary | Un-invoiced balance (compute) |
| `amount_invoiced` | Monetary | Already invoiced (compute) |
| `currency_id` | Many2one | Transaction currency |
| `currency_rate` | Float | Exchange rate to company currency (stored) |
| `user_id` | Many2one | Salesperson (res.users), auto-computed from partner |
| `team_id` | Many2one | Sales team (crm.team), computed from user/company |
| `tag_ids` | Many2many | crm.tag for filtering |
| `pricelist_id` | Many2one | Computed from partner |
| `payment_term_id` | Many2one | Computed from partner |
| `fiscal_position_id` | Many2one | Computed with caching |
| `tax_country_id` | Many2one | For tax filtering (fiscal position country or company country) |
| `tax_totals` | Binary | JSON tax summary for frontend, non-exportable |
| `require_signature` | Boolean | Request online signature (computed from company) |
| `require_payment` | Boolean | Request online payment (computed from company) |
| `prepayment_percent` | Float | Prepayment % required (computed from company) |
| `signature` | Image | Customer signature (max 1024x1024, attachment) |
| `signed_by` | Char | Name of person who signed |
| `signed_on` | Datetime | Signature timestamp |
| `client_order_ref` | Char | Customer's PO number |
| `origin` | Char | Source document reference |
| `reference` | Char | Payment reference |
| `commitment_date` | Datetime | Promised delivery date (overrides lead-time-based expected_date) |
| `expected_date` | Datetime | Computed expected delivery, not stored (depends on today()) |
| `is_expired` | Boolean | Quotation expired (validity_date < today and state draft/sent) |
| `journal_id` | Many2one | Invoicing journal (computed) |
| `note` | Html | Terms and conditions (computed from company settings) |
| `campaign_id` | Many2one | UTM campaign (ondelete='set null') |
| `medium_id` | Many2one | UTM medium (ondelete='set null') |
| `source_id` | Many2one | UTM source (ondelete='set null') |
| `invoice_ids` | Many2many | Computed via order_line.invoice_lines |
| `invoice_count` | Integer | Number of invoices (computed) |
| `invoice_status` | Selection | upselling / invoiced / to invoice / no |
| `transaction_ids` | Many2many | payment.transaction records |
| `authorized_transaction_ids` | Many2many | Authorized transactions (computed) |
| `amount_paid` | Float | Sum of done/authorized transaction amounts |
| `duplicated_order_ids` | Many2many | Orders with same partner/date/ref (computed) |
| `has_archived_products` | Boolean | Any line has archived product |
| `show_update_pricelist` | Boolean | Show "Update Prices" button |
| `show_update_fpos` | Boolean | Show fiscal position update warning |
| `partner_credit_warning` | Text | Credit limit warning message |
| `terms_type` | Selection | From company: html or plain text |
| `type_name` | Char | "Quotation" or "Sales Order" (computed) |

#### State Machine

```
draft ──[action_quotation_send]──→ sent
  │                                  │
  │                                  ▼
  └──[action_confirm]──→ sale ──[auto-lock if group_auto_done_setting]──→ locked
                            │
                            └──[action_cancel]──→ cancel
```

**Note:** `done` state was removed in Odoo 18. Orders are locked instead of marked done.

#### Methods

##### Lifecycle / Action Methods

| Method | Description |
|--------|-------------|
| `create()` | Sets name via ir.sequence, supports multi-create |
| `copy_data()` | Excludes downpayment lines from duplication |
| `write()` | Validates no pricelist change on confirmed orders; subscribes partner on change |
| `_unlink_except_draft_or_cancel()` | Prevents deletion of sent/confirmed orders |
| `action_confirm()` | Validates all lines have products; subscribes partner; sets state=sale; calls `_action_confirm()` hook; auto-locks if configured; sends confirmation email |
| `_should_be_locked()` | Checks create_uid in `sale.group_auto_done_setting` |
| `_confirmation_error_message()` | Returns error if any line missing product or state not draft/sent |
| `_prepare_confirmation_values()` | Returns `{'state': 'sale', 'date_order': fields.Datetime.now()}` |
| `_action_confirm()` | Hook for extensions (sale_stock: launches procurement) |
| `action_quotation_send()` | Opens mail.compose.message; validates analytic distribution |
| `_find_mail_template()` | Returns email_template_edi_sale for draft/sent; confirmation template for sale |
| `_get_confirmation_template()` | Returns config param `sale.default_confirmation_template` or `mail_template_sale_confirmation` |
| `action_quotation_sent()` | Sets state='sent', subscribes partner |
| `action_draft()` | Resets state, clears signature fields |
| `action_lock()` / `action_unlock()` | Toggle locked flag |
| `action_cancel()` | Shows cancel wizard for non-draft orders; calls `_action_cancel()` |
| `_action_cancel()` | Cancels draft invoices, sets state='cancel' |
| `_show_cancel_wizard()` | Returns True if any non-draft order |
| `action_preview_sale_order()` | Returns portal URL action |
| `action_open_discount_wizard()` | Opens `sale.order.discount` wizard |
| `action_update_taxes()` | Recomputes taxes, posts activity |
| `action_update_prices()` | Recomputes prices, posts activity |
| `_recompute_taxes()` | Triggers `_compute_tax_id()` on lines |
| `_recompute_prices()` | Uses force_price_recomputation context, resets discount, recomputes |

##### Computed / Utility Methods

| Method | Description |
|--------|-------------|
| `_compute_amounts()` | Uses `_prepare_base_line_for_taxes_computation` + `AccountTax._get_tax_totals_summary` |
| `_add_base_lines_for_early_payment_discount()` | Adds extra lines for EPD when payment_term is 'mixed' |
| `_compute_invoice_status()` | Uses read_group on order_line for efficiency |
| `_compute_duplicated_order_ids()` | SQL query to find orders with same partner/date/ref/origin |
| `_fetch_duplicate_orders()` | SQL with safe tuple binding |
| `_compute_expected_date()` | Aggregates line._expected_date(); calls `_select_expected_date()` |
| `_select_expected_date()` | Returns min(dates) by default; sale_stock overrides for 'one' picking_policy |
| `_compute_is_expired()` | Checks validity_date vs today() |
| `_compute_partner_credit_warning()` | Uses `AccountMove._build_credit_warning_message` |
| `_compute_amount_to_invoice()` / `_compute_amount_invoiced()` | Aggregate order_line values |
| `_compute_display_name()` | When `sale_show_partner_name` context set, appends partner.name |
| `_search_invoice_ids()` | Raw SQL for special operators `in`/`=` with value=False |
| `onchange()` | Sets `sale_onchange_first_call` and `res_partner_search_mode` context |
| `_compute_has_archived_products()` | Any line has inactive product |
| `_compute_has_active_pricelist()` | Any active pricelist exists |

##### Onchange Methods

| Method | Description |
|--------|-------------|
| `_onchange_commitment_date()` | Warns if commitment_date < expected_date |
| `_onchange_partner_id_warning()` | Respects partner.sale_warn settings |
| `_onchange_pricelist_id_show_update_prices()` | Sets show_update_pricelist |
| `_onchange_fpos_id_show_update_fpos()` | Sets show_update_fpos |
| `_onchange_company_id()` / `_onchange_company_id_warning()` | Validates and warns on company change |
| `_onchange_order_line()` | Handles combo product line creation from JSON `selected_combo_items` |
| `_onchange_prepayment_percent()` | Clears require_payment if percent cleared |

##### Invoicing

| Method | Description |
|--------|-------------|
| `_prepare_invoice()` | Prepares invoice vals dict; sale_stock adds incoterm/delivery_date |
| `_get_invoiced()` / `_search_invoice_ids()` | Compute invoice_ids and invoice_count |

---

### sale.order.line

Inherits: `analytic.mixin`
_order: `order_id, sequence, id`
_check_company_auto: True

**SQL Constraints:**
```python
('accountable_required_fields',
 "CHECK(display_type IS NOT NULL OR is_downpayment OR (product_id IS NOT NULL AND product_uom IS NOT NULL))",
 "Missing required fields on accountable sale order line.")
('non_accountable_null_fields',
 "CHECK(display_type IS NULL OR (product_id IS NULL AND price_unit = 0 AND product_uom_qty = 0 AND product_uom IS NULL AND customer_lead = 0))",
 "Forbidden values on non-accountable sale order line.")
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | Many2one | Parent sale.order, required, cascade, indexed |
| `sequence` | Integer | Line ordering, default 10 |
| `display_type` | Selection | line_section / line_note / False |
| `is_configurable_product` | Boolean | Related to product_template_id.has_configurable_attributes |
| `is_downpayment` | Boolean | Marked as down payment (not copied on duplication) |
| `is_expense` | Boolean | Line came from expense/vendor bill |
| `product_id` | Many2one | Product (product.product), domain: sale_ok=True |
| `product_template_id` | Many2one | Computed, editable for configurator (avoids modifying product_id directly) |
| `product_uom_category_id` | Many2one | From product.uom_id.category_id |
| `product_template_attribute_value_ids` | Many2many | Related from product_id |
| `product_custom_attribute_value_ids` | One2many | For product configurator |
| `product_no_variant_attribute_value_ids` | Many2many | No-variant attributes affecting price |
| `is_product_archived` | Boolean | True if product is inactive |
| `name` | Text | Line description (computed from product or manual), required |
| `translated_product_name` | Text | Product display_name in order language |
| `product_uom_qty` | Float | Ordered qty (computed from packaging if set) |
| `product_uom` | Many2one | UOM (computed from product.uom_id) |
| `linked_line_id` | Many2one | Links combo item lines to parent combo line |
| `linked_line_ids` | One2many | Child combo item lines |
| `virtual_id` | Char | Temporary ID before DB save (for pre-save linking) |
| `linked_virtual_id` | Char | Virtual ID of linked line |
| `selected_combo_items` | Char | JSON storage for combo selections (transient) |
| `combo_item_id` | Many2one | Selected combo item (auto-set) |
| `tax_id` | Many2many | Taxes (computed from product, mapped via fiscal_position) |
| `pricelist_item_id` | Many2one | Cached pricelist rule for pricing |
| `price_unit` | Float | Unit price (computed from pricelist), stored |
| `technical_price_unit` | Float | Original computed price before manual overrides |
| `discount` | Float | Discount % (computed from pricelist), stored |
| `price_subtotal` | Monetary | Untaxed subtotal (stored) |
| `price_tax` | Float | Tax amount (stored) |
| `price_total` | Monetary | Taxed total (stored) |
| `price_reduce_taxexcl` | Monetary | Unit price excl. tax after discount |
| `price_reduce_taxinc` | Monetary | Unit price incl. tax after discount |
| `product_packaging_id` | Many2one | Preferred packaging (computed) |
| `product_packaging_qty` | Float | Packaging quantity (computed) |
| `customer_lead` | Float | Lead time in days (computed from product.sale_delay) |
| `qty_delivered_method` | Selection | manual / analytic / stock_move (sale_stock adds) |
| `qty_delivered` | Float | Delivered qty (computed) |
| `qty_invoiced` | Float | Invoiced qty |
| `qty_invoiced_posted` | Float | Invoiced qty from posted invoices only |
| `qty_to_invoice` | Float | Qty to invoice (computed, depends on invoice_policy) |
| `analytic_line_ids` | One2many | Analytic lines via so_line |
| `invoice_lines` | Many2many | Account.move.line records |
| `invoice_status` | Selection | upselling / invoiced / to invoice / no |
| `untaxed_amount_invoiced` | Monetary | Untaxed amount invoiced |
| `amount_invoiced` | Monetary | Total invoiced (signed per direction_sign) |
| `untaxed_amount_to_invoice` | Monetary | Remaining untaxed to invoice |
| `amount_to_invoice` | Monetary | Taxed amount to invoice |
| `product_type` | Selection | Related: product type |
| `service_tracking` | Selection | Related: product service_tracking |
| `product_updatable` | Boolean | Can product be edited (computed) |
| `product_uom_readonly` | Boolean | UOM locked after sale/cancel |
| `tax_calculation_rounding_method` | Selection | Related: company setting |

#### Methods

##### Lifecycle / CRUD

| Method | Description |
|--------|-------------|
| `create()` | Resets qty to 0 for display_type lines; handles combo linking; posts chatter message for new sale lines |
| `_add_precomputed_values()` | Sets technical_price_unit from price_unit |
| `write()` | Prevents display_type changes; validates product change; handles qty updates on sale lines; checks locked SO |
| `_check_line_unlink()` | Returns lines that cannot be deleted: confirmed + (invoiced or not downpayment) |
| `_unlink_except_confirmed()` | Raises if confirmed order has non-downpayment line |
| `_get_protected_fields()` | Fields blocked on locked SOs: product_id, name, price_unit, product_uom, product_uom_qty, tax_id, analytic_distribution |
| `_update_line_quantity()` | Posts chatter message; validates consu lines against delivered qty |

##### Pricing

| Method | Description |
|--------|-------------|
| `_get_display_price()` | Returns 0 for combo; delegates to combo item price or _get_display_price_ignore_combo |
| `_get_display_price_ignore_combo()` | Computes from pricelist; handles negative discounts (surcharges not shown) |
| `_get_pricelist_price()` | Calls pricelist_item_id._compute_price() |
| `_get_pricelist_price_before_discount()` | Calls pricelist_item_id._compute_price_before_discount() |
| `_get_product_price_context()` | Delegates to product_id._get_product_price_context() |
| `_reset_price_unit()` | Gets display price, strips taxes via fiscal position, stores in price_unit and technical_price_unit |
| `_get_order_date()` | Returns order_id.date_order |
| `_compute_pricelist_item_id()` | Calls pricelist_id._get_product_rule() |
| `_compute_price_unit()` | Checks manual override (technical_price_unit), invoiced qty, expense policy |
| `_compute_discount()` | Only shows discount if pricelist rule has _show_discount(); copies from parent for combo item lines |

##### Description / Naming

| Method | Description |
|--------|-------------|
| `_get_sale_order_line_multiline_description_sale()` | Product description + variant attrs + linked-line info |
| `_get_sale_order_line_multiline_description_variants()` | Handles custom and no_variant attribute descriptions |
| `_get_downpayment_description()` | Generates description based on dp state |
| `_compute_name()` | Generates from product or downpayment; respects language |
| `_compute_product_template_id()` / `_search_product_template_id()` | Product/template bidirectional sync |
| `_compute_display_name()` | Builds "[SO-NAME] - [Description] [additional]" |

##### Tax Computation

| Method | Description |
|--------|-------------|
| `_prepare_base_line_for_taxes_computation()` | Converts to dict for AccountTax generic method |
| `_compute_amount()` | Uses AccountTax._add_tax_details_in_base_line |
| `_compute_tax_id()` | Groups by company, caches results, handles fiscal_position mapping, skips combo |
| `_get_custom_compute_tax_cache_key()` | Hook for custom tax caching (returns empty tuple by default) |

##### Quantities / Delivery

| Method | Description |
|--------|-------------|
| `_compute_customer_lead()` | Sets 0.0 (sale_stock overrides with product.sale_delay) |
| `_compute_qty_delivered_method()` | Sets 'analytic' for is_expense, 'manual' otherwise |
| `_compute_qty_delivered()` | Aggregates analytic line unit_amounts |
| `_get_delivered_quantity_by_analytic()` | Groups AAL by uom and so_line, converts, sums |
| `_compute_qty_invoiced()` / `_compute_qty_invoiced_posted()` | Counts invoice/refund quantities |
| `_get_invoice_lines()` | Filters by accrual_entry_date context if set |
| `_compute_qty_to_invoice()` | Uses invoice_policy; special combo handling |
| `_compute_invoice_status()` | Respects upselling for order-invoiced products delivered over qty |
| `_can_be_invoiced_alone()` | False if product is company.sale_discount_product_id |
| `_is_discount_line()` | True if product in sale_discount_product_id |
| `_compute_untaxed_amount_invoiced()` | Sums posted invoice/refund price_subtotals |
| `_compute_amount_invoiced()` | Uses direction_sign for signed amounts |
| `_compute_untaxed_amount_to_invoice()` | Handles mixed-discount scenarios and tax-included recalculation |
| `_compute_amount_to_invoice()` | unit_price_total * qty_to_invoice |
| `_expected_date()` | order_date + customer_lead |
| `compute_uom_qty()` | Converts qty via product_uom._compute_quantity |

##### Other

| Method | Description |
|--------|-------------|
| `_compute_analytic_distribution()` | Uses account.analytic.distribution.model._get_distribution() |
| `_compute_product_updatable()` | False if downpayment/cancel or sale with qty |
| `_compute_product_uom_readonly()` | True if saved and state is sale/cancel |
| `_compute_product_packaging_id()` / `_compute_product_packaging_qty()` | Packaging suggestion |
| `_check_combo_item_id()` | Validates combo_item matches allowed items and product |
| `_onchange_product_id()` / `_onchange_product_id_warning()` | Reset price; respect sale_line_warn |
| `_onchange_product_packaging_id()` | Warns about packaging qty mismatches |
| `_prepare_invoice_line()` | Builds invoice line vals; combo products use display_type=line_section |
| `_get_invoice_line_sequence()` | Override point for invoice line sequencing |
| `_get_linked_line()` | Returns parent combo line for combo item lines |
| `_get_linked_lines()` | Returns all combo item lines for a combo product |
| `_get_combo_item_display_price()` | Prorates combo product price across items |
| `action_add_from_catalog()` | Delegates to parent order |

---

## Workflow

```
1. Create Quotation     → sale.order created in draft, name via ir.sequence
2. Edit Lines           → Add products; pricing from pricelist
3. Send to Customer      → action_quotation_send() sends email template
   State: draft → sent
4. Customer Accepts      → action_confirm() validates + confirms
   State: sent → sale
   Hook: _action_confirm() (sale_stock launches procurement)
   Auto-lock: if sale.group_auto_done_setting enabled
5. Delivery              → sale_stock: _action_launch_stock_rule() creates pickings
6. Invoice               → action_view_invoice() creates account.move drafts
7. Payment               → Online via payment.transaction
   require_payment: can force payment before confirmation
```

---

## sale_management Extension

**Module:** `sale_management`
**Location:** `~/odoo/odoo18/odoo/addons/sale_management/`

### sale.order.template

```python
_name = "sale.order.template"
_description = "Quotation Template"
_order = 'sequence, id'
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Template name, required |
| `note` | Html | Terms and conditions (translated) |
| `sequence` | Integer | Ordering |
| `active` | Boolean | Allows hiding without removing |
| `company_id` | Many2one | Multi-company support |
| `mail_template_id` | Many2one | Confirmation email template |
| `number_of_days` | Integer | Quotation validity duration |
| `require_signature` | Boolean | Computed from company.portal_confirmation_sign |
| `require_payment` | Boolean | Computed from company.portal_confirmation_pay |
| `prepayment_percent` | Float | Computed from company.prepayment_percent |
| `sale_order_template_line_ids` | One2many | Template lines |
| `sale_order_template_option_ids` | One2many | Optional add-on products |
| `journal_id` | Many2one | Invoicing journal for SOs using this template |

**Key Methods:**

| Method | Description |
|--------|-------------|
| `_compute_require_signature()` | From company.portal_confirmation_sign |
| `_compute_require_payment()` | From company.portal_confirmation_pay |
| `_compute_prepayment_percent()` | From company.prepayment_percent |
| `_onchange_prepayment_percent()` | Clears require_payment if percent cleared |
| `_check_company_id()` | All products must belong to same company as template |
| `_check_prepayment_percent()` | Validates 0 < percent <= 1.0 when require_payment |
| `_update_product_translations()` | Syncs template line/option names with product descriptions across active languages |
| `_demo_configure_template()` | Sets up demo template with products |

### sale.order.template.line

```python
comodel_name='sale.order.template.line'
inverse_name='sale_order_template_id'
```

Fields: `product_id`, `name`, `description`, `product_uom_qty`, `product_uom_id`, `sequence`

### sale.order.template.option

```python
comodel_name='sale.order.template.option'
inverse_name='sale_order_template_id'
```

Fields: `product_id`, `name`, `description`, `uom_id`, `quantity`, `optional_product_pos` (left/right), `sequence`

### sale.order.option

Used on actual sale orders to track optional products selected from a template.

---

## sale_stock Extension

**Module:** `sale_stock`
**Location:** `~/odoo/odoo18/odoo/addons/sale_stock/`

### sale.order (extension)

**New Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `incoterm` | Many2one | Incoterm (account.incoterms) |
| `incoterm_location` | Char | Incoterm location |
| `picking_policy` | Selection | direct (each picking ASAP) / one (all ready), default direct |
| `warehouse_id` | Many2one | Source warehouse, computed from user/ir.default |
| `picking_ids` | One2many | stock.picking with sale_id |
| `delivery_count` | Integer | Number of delivery orders |
| `delivery_status` | Selection | pending / started / partial / full / False |
| `procurement_group_id` | Many2one | Procurement group for grouped procurement |
| `effective_date` | Datetime | First done picking date |
| `expected_date` | Datetime | Overrides base based on picking_policy |
| `json_popover` | Char | JSON for late picking alert |
| `show_json_popover` | Boolean | Has late picking |

**Key Methods:**

| Method | Description |
|--------|-------------|
| `_init_column()` | SQL init for warehouse_id (avoids reading property before created) |
| `_action_confirm()` | Calls order_line._action_launch_stock_rule() then super() |
| `_action_cancel()` | Cancels draft pickings, logs qty decrease activities |
| `_check_warehouse()` | Validates warehouse for non-consu products |
| `write()` | Updates picking partner on shipping change; logs qty decreases; propagates commitment_date to moves |
| `_compute_warehouse_id()` | Uses ir.default or user._get_default_warehouse_id() |
| `_compute_delivery_status()` | Based on picking states |
| `_compute_effective_date()` | Min date_done of done customer pickings |
| `_compute_picking_ids()` | Sets delivery_count |
| `_compute_json_popover()` | Detects late pickings |
| `_onchange_partner_shipping_id()` | Warns if pickings need partner update |
| `action_view_delivery()` | Returns stock picking action |
| `_get_action_view_picking()` | Builds picking tree/form action |
| `_prepare_invoice()` | Adds invoice_incoterm_id and delivery_date |
| `_log_decrease_ordered_quantity()` | Renders exception template via _log_activity |

### stock.picking (sale_stock extension)

Extends `stock.picking` to link pickings back to sale orders.

| Field / Method | Description |
|----------------|-------------|
| `sale_id` | Many2one, computed from `group_id.sale_id`, stored via inverse |
| `_compute_sale_id()` | Sets from `group_id.sale_id` |
| `_set_sale_id()` | Writes to group_id; creates procurement group if needed |
| `_auto_init()` | Creates `sale_id` column via `create_column` (too slow via ORM) |
| `_action_done()` | After picking done: creates SOLs for unregistered products with qty done, respects invoice_policy |
| `_log_less_quantities_than_expected()` | Logs activity on linked sale orders when qty short |
| `_can_return()` | Overridden to allow returns for sale-linked pickings |

### stock.move (sale_stock extension)

| Field / Method | Description |
|----------------|-------------|
| `sale_line_id` | Many2one, index btree_not_null |
| `_prepare_merge_moves_distinct_fields()` | Adds `sale_line_id` to merge fields |
| `_get_related_invoices()` | Includes posted sale invoices from picking.sale_id |
| `_get_source_document()` | Returns `sale_line_id.order_id` if available |
| `_get_sale_order_lines()` | Returns all SOLs via `_rollup_move_origs/dests` |
| `_assign_picking_post_process()` | Posts mail message linking picking to its sale order |
| `_get_all_related_sm()` | Includes moves with matching sale_line product |

### stock.route (sale_stock extension)

| Field | Description |
|-------|-------------|
| `sale_selectable` | Boolean, allows route selection on sale order lines |

### stock.lot (sale_stock extension)

| Field / Method | Description |
|----------------|-------------|
| `sale_order_ids` | Many2many, computed from done move lines with lots |
| `sale_order_count` | Integer, count of linked sale orders |
| `_compute_sale_order_ids()` | Searches done stock.move.line with lot; traces via sale_line_id.order_id |
| `action_view_so()` | Returns sale order action filtered to linked SOs |

### account.move (sale_stock extension)

Overrides stock-account integration methods.

| Method | Description |
|--------|-------------|
| `_stock_account_get_last_step_stock_moves()` | Returns done stock moves for invoice valuation (includes refund handling) |
| `_get_invoiced_lot_values()` | Computes lot quantities for invoice report; handles returns and refunds |
| `_compute_delivery_date()` | Extends account: sets from max of linked SO effective_dates |
| `_compute_incoterm_location()` | Extends account: sets from first SO incoterm_location |
| `_get_anglo_saxon_price_ctx()` | Passes `move_is_downpayment` context for downpayment refunds |
| `_get_protected_vals()` | Protects `delivery_date` from modification via line write |

### account.move.line (sale_stock extension)

| Method | Description |
|--------|-------------|
| `_sale_can_be_reinvoice()` | False for COGS lines, delegates to super |
| `_stock_account_get_anglo_saxon_price_unit()` | Computes average price from posted COGS lines linked to same SO line; handles refunds and downpayments |

---

## Pricing Flow

```
product_id selected
  → _compute_product_template_id()
  → _compute_name() (product description)
  → _compute_product_uom() (product.uom_id)
  → _compute_pricelist_item_id() (pricelist._get_product_rule())
  → _compute_price_unit() (pricelist_item._compute_price())
  → _compute_discount() (pricelist_item._show_discount() + price comparison)
  → _compute_tax_id() (product taxes mapped via fiscal_position)
  → _compute_amount() (price_subtotal, price_total, price_tax)
  → sale.order: _compute_amounts() (aggregates lines)
```

---

## Combo Products (Odoo 18 New)

Combo products allow bundling multiple products with a single price:

- **Combo product line**: `display_type=False`, `is_downpayment=False`, `product_id.type='combo'`
- **`selected_combo_items`**: JSON field storing selected items before creation
- **`_onchange_order_line()`** on parent order processes combo selections:
  - Creates child SOLs for each selected item with `linked_line_id` set
  - `combo_item_id` links child line to its combo item record
- **Discount inheritance**: Child lines copy discount from parent combo line
- **Price prorating**: `_get_combo_item_display_price()` distributes combo product price across items
- **Invoicing**: Combo product line becomes `display_type=line_section` with no price; child lines are actual invoiceable products

---

## Relation to Other Modules

| Relationship | Module | Description |
|-------------|--------|-------------|
| `sale` -> `stock` | sale_stock | Delivery pickings on confirmation |
| `sale` -> `account` | account | Invoices via `_prepare_invoice` |
| `sale` -> `product` | product | Products via product_id; pricing via pricelists |
| `sale` -> `sale_stock` | sale_stock | Warehouse/route/delivery; MTO procurement |
| `sale` -> `sale_management` | sale_management | Quotation templates |
| `sale` -> `crm` | crm | team_id from crm.team; tags from crm.tag |
| `sale` -> `payment` | payment | Online transactions via transaction_ids |
| `sale` -> `portal` | portal | Portal access via portal.mixin |
| `sale` -> `mail` | mail | Chatter and activities |
| `sale` -> `utm` | utm | Campaign/medium/source tracking |
| `sale` -> `product_catalog` | product_catalog | Catalog-based line addition |
| `sale` -> `analytic` | analytic | Analytic distribution on lines |

---

## Module Dependencies

```
sale
├── base
├── product (product.product, product.pricelist, product.pricelist.item)
├── account (account.tax, account.fiscal.position, account.move)
├── account_payment (payment.transaction)
├── analytic_account (account.analytic.line)
├── mail (mail.thread, mail.activity)
├── utm (utm.mixin)
├── portal (portal.mixin)
├── product_catalog (product.catalog.mixin)
└── sale_management (sale.order.template)
    └── sale (circular-safe)

sale_stock
├── sale
├── stock (stock.picking, stock.move, stock.rule, stock.warehouse, procurement.group)
└── delivery (product.packaging)
```

---

## Related

- [Modules/Stock](modules/stock.md)
- [Modules/Account](modules/account.md)
- [Modules/CRM](modules/crm.md)
- [Modules/Payment](modules/payment.md)
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md)
- [Tools/Modules Inventory](tools/modules-inventory.md)