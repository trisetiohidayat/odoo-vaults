# sale_management — Sale Management

**Tags:** #odoo #odoo18 #sale #management #template #option
**Odoo Version:** 18.0
**Module Category:** Sale / Management & Configuration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_management` adds structured sale order templates and optional product lines to the base sale flow. It enables reusable quotation templates with pre-configured lines, optional products (add-ons offered during quotation), and company-level default template assignment. It also adds digest KPIs for sales performance tracking.

**Technical Name:** `sale_management`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_management/`
**Depends:** `sale`
**Inherits From:** `sale.order`, `sale.order.line`, `sale.order.template`, `sale.order.template.line`, `sale.order.template.option`, `sale.order.option`, `digest.digest`, `res.config.settings`, `res.company`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/sale_order.py` | `sale.order` | Template assignment, optional lines, onchanges, signature/payment config |
| `models/sale_order_line.py` | `sale.order.line` | Optional product name handling |
| `models/sale_order_template.py` | `sale.order.template` | Template model with lines and options |
| `models/sale_order_template_line.py` | `sale.order.template.line` | Template line model |
| `models/sale_order_template_option.py` | `sale.order.template.option` | Optional product on template |
| `models/sale_order_option.py` | `sale.order.option` | Standalone option model, add-to-order action |
| `models/digest.py` | `digest.digest` | Sales KPIs |
| `models/res_config_settings.py` | `res.config.settings` | Template group, company default |
| `models/res_company.py` | `res.company` | Company default template |

---

## Models Reference

### `sale.order.template` (models/sale_order_template.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `active` | Boolean | Template active state |
| `company_id` | Many2one | Per-company templates |
| `name` | Char | Template name |
| `note` | Html | Terms/conditions |
| `sequence` | Integer | Sort order |
| `mail_template_id` | Many2one | Confirmation email template |
| `number_of_days` | Integer | Validity days |
| `require_signature` | Boolean | Require online signature (compute+store) |
| `require_payment` | Boolean | Require online payment (compute+store) |
| `prepayment_percent` | Float | Down payment % (compute+store) |
| `sale_order_template_line_ids` | One2many | Template lines |
| `sale_order_template_option_ids` | One2many | Optional products |
| `journal_id` | Many2one | Down payment journal |

#### Methods

| Method | Behavior |
|--------|----------|
| `_check_company_id()` | Cross-company validation |
| `_check_prepayment_percent()` | % must be 0-100 |
| `write()` | Deactivates old default template when new one is set |
| `_update_product_translations()` | Syncs line name translations |
| `_demo_configure_template()` | Creates sample template data |

---

### `sale.order.template.line` (models/sale_order_template_line.py)

#### Fields

All standard `sale.order.line` fields replicated: `product_id`, `name`, `product_uom_qty`, `product_uom_id`, `price_unit`, `discount`, `sequence`, `layout_category_id`, `customer_lead`, `replenishment_date`

#### Methods

| Method | Behavior |
|--------|----------|
| `_prepare_order_line_values()` | Converts template line to SOL vals |

---

### `sale.order.template.option` (models/sale_order_template_option.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `product_id` | Many2one | Optional product |
| `name` | Char | Compute from product |
| `uom_id` | Many2one | Compute from product |
| `quantity` | Float | Default qty |

#### Methods

| Method | Behavior |
|--------|----------|
| `_prepare_option_line_values()` | Converts template option to `sale.order.option` |

---

### `sale.order.option` (models/sale_order_option.py)

Standalone model representing an optional product attached to a sale order but not part of the main order line list.

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `order_id` | Many2one | Parent sale order |
| `product_id` | Many2one | Optional product |
| `line_id` | Many2one | Optional line (linked SOL) |
| `sequence` | Integer | Display order |
| `name` | Char | Computed from product |
| `uom_id` | Many2one | Computed from product |
| `price_unit` | Float | Computed from product |
| `discount` | Float | Discount % |
| `is_present` | Boolean | Compute+search: linked to existing SOL |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_name()`, `_compute_uom_id()`, `_compute_price_unit()` | From product |
| `_get_values_to_add_to_order()` | Prepares SOL vals for adding option |
| `button_add_to_order()` | Calls `add_option_to_order()` |
| `add_option_to_order()` | Creates SOL from option, unlinks self |

---

### `sale.order` (models/sale_order.py)

#### Additional Fields

| Field | Type | Notes |
|-------|------|-------|
| `sale_order_template_id` | Many2one | Active template (compute+store) |

#### Methods

| Method | Decorators | Behavior |
|--------|-----------|----------|
| `_compute_sale_order_template_id()` | `@api.depends` | Sets template from company default or product category default |
| `_compute_note()` | `@api.onchange` | Loads template note |
| `_compute_require_signature()` | `@api.onchange` | Loads template signature requirement |
| `_compute_require_payment()` | `@api.onchange` | Loads template payment requirement |
| `_compute_prepayment_percent()` | `@api.onchange` | Loads template prepayment % |
| `_compute_validity_date()` | `@api.onchange` | Sets validity date |
| `_compute_journal_id()` | `@api.onchange` | Sets journal |
| `_check_optional_product_company_id()` | `@api.constrains` | Cross-company validation |
| `write()` | — | Handles template change triggering re-computation |
| `_recompute_prices()` | — | Recomputes SOL prices |
| `_can_be_edited_on_portal()` | — | Blocks portal editing if options present |

---

## Security File: `security/sale_management_security.xml`

**Group**: `sale_management.group_sale_order_template`
- ACL `sale.order`: read, write, create (manager), unlink (manager)
- ACL `sale.order.template`: read, write, create, unlink (manager)
- ACL `sale.order.template.line`: read, write, create, unlink (manager)
- ACL `sale.order.template.option`: read, write, create, unlink (manager)
- ACL `sale.order.option`: read, write, create, unlink (manager)

---

## Data Files

| File | Content |
|------|---------|
| `data/sale_order_template_data.xml` | Demo/default template "Product Offer" |
| `data/res_config_demo_data.xml` | Sets `sale_order_template_id` on demo company |

---

## Critical Behaviors

1. **Template Loading via Onchange**: When `sale_order_template_id` is set/changed on a draft SO, onchanges populate note, signature requirement, payment requirement, prepayment percent, validity date, and journal. Lines and options are NOT auto-added — the user must explicitly add them.

2. **Optional Products**: `sale.order.option` is a separate model from `sale.order.line`. Options are shown in the SO but not included in totals until explicitly added. When added, they convert to regular SOLs.

3. **Default Template**: Via `sale_order_template_id` on `res.company`, new sale orders automatically inherit the default template for the company.

4. **Prepayment Percent**: When `require_payment = True` and `prepayment_percent > 0`, a down payment is required before order confirmation (enforced via `sale_online_payment` or manual payment).

5. **Portal Editing Restriction**: `_can_be_edited_on_portal()` blocks portal editing when `sale_order_option_ids` exist (prevents inconsistent state).

---

## v17→v18 Changes

- `journal_id` field added to `sale.order.template` for down payment journal selection
- `_compute_journal_id()` method added
- `_update_product_translations()` added for i18n support
- `_demo_configure_template()` added for template demo data
- Portal edit restriction for options

---

## Notes

- `sale_management` is the prerequisite for `sale_pdf_quote_builder`
- Templates can have both mandatory lines and optional products
- The `sale.order.option` model is a UX pattern — optional products are shown separately until confirmed
- Digest KPIs added: `kpi_all_sale_total`, `kpi_all_sale_total_value` track total invoiced amount
