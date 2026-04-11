---
tags: [odoo, odoo17, module, sale_management]
---

# Sale Management Module

**Source:** `addons/sale_management/models/`

## Key Models

| Model | File | Description |
|-------|------|-------------|
| `` `sale.order.template` `` | `sale_order_template.py` | Quotation/contract template |
| `` `sale.order.template.line` `` | `sale_order_template_line.py` | Lines within a template |
| `` `sale.order.template.option` `` | `sale_order_template_option.py` | Optional products on a template |
| `` `sale.order.option` `` | `sale_order_option.py` | Optional products on a live order |

## sale.order.template

Pre-defined quotation templates used to quickly generate structured `` `sale.order` `` records. Common use cases: recurring contracts, structured proposals, terms-and-conditions-bound quotes.

### Key Fields

- `` `name` `` — Template display name
- `` `note` `` — HTML terms and conditions (`` `translate=True` ``)
- `` `mail_template_id` `` — `` `mail.template`` `` sent on order confirmation
- `` `number_of_days` `` — Validity duration; Odoo sets `` `validity_date` `` on the generated SO
- `` `require_signature` `` — Online signature required to auto-confirm (`` `portal_confirmation_sign` `` on company)
- `` `require_payment` `` — Online payment required to auto-confirm (`` `portal_confirmation_pay` ``)
- `` `prepayment_percent` `` — If `` `require_payment` `` is set, specifies how much must be paid upfront (0 < value <= 1.0)
- `` `sale_order_template_line_ids` `` — One2many of `` `sale.order.template.line` ``
- `` `sale_order_template_option_ids` `` — One2many of `` `sale.order.template.option` ``
- `` `journal_id` `` — Invoicing journal for orders created from this template
- `` `company_id` `` — Multi-company constraint

### Constraints

- `` `_check_company_id()` `` — All products in lines and options must belong to the same company as the template
- `` `_check_prepayment_percent()` `` — Only enforced when `` `require_payment` `` is true

### Template Application

A `` `sale.order` `` can be generated from a template, creating both the order header (with `` `require_signature/payment` `` settings copied) and line records. Optional products appear on the quotation as `` `sale.order.option` `` records that the customer can accept.

## sale.order.template.line

A product line within a quotation template. Mirrors `` `sale.order.line` `` structure:

- `` `product_id` `` — Product
- `` `name` `` — Description (auto-filled from product via `` `_compute_name()` ``, translatable)
- `` `product_uom_id` `` — Unit of measure
- `` `product_uom_qty` `` — Quantity
- `` `discount` `` — Line discount
- `` `sequence` `` — Display order

## sale.order.template.option

Optional products attached to a template — shown to the customer as add-ons on the quotation. When the customer accepts an option, `` `sale.order.option.add_option_to_order()` `` converts it into a `` `sale.order.line` ``.

## sale.order.option

Live optional products attached to a `` `sale.order` `` (not just the template). Created when a quotation is generated from a template that has optional lines.

### Key Fields

- `` `order_id` `` — Parent `` `sale.order` ``
- `` `product_id` `` — Optional product
- `` `quantity` ``, `` `uom_id` ``, `` `price_unit` ``, `` `discount` `` — Line values (all computed from product on change)
- `` `line_id` `` — Set when the option has been accepted (links to the resulting `` `sale.order.line` ``)
- `` `is_present` `` — True if the product is already in the order (prevents duplicate addition)

### Adding to Order

`` `button_add_to_order()` `` / `` `add_option_to_order()` `` creates the corresponding `` `sale.order.line` `` and sets `` `line_id`` `` to prevent double-adding. The `` `sale.order` `` is checked via `` `_can_be_edited_on_portal()` `` — confirmed orders cannot accept new options.

## See Also

- [[Modules/sale]] — base `` `sale.order`` `` and `` `sale.order.line` ``
- [[Modules/website_sale]] — e-commerce quotation flow
