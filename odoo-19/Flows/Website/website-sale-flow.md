---
type: flow
title: "Website Sale Flow"
primary_model: sale.order
trigger: "User — Website checkout / Payment confirmed"
cross_module: true
models_touched:
  - sale.order
  - sale.order.line
  - payment.transaction
  - website
  - stock.picking
  - account.move
  - procurement.group
  - mail.mail
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Sale/quotation-to-sale-order-flow](quotation-to-sale-order-flow.md)"
  - "[Flows/Sale/sale-to-delivery-flow](sale-to-delivery-flow.md)"
  - "[Flows/Sale/sale-to-invoice-flow](sale-to-invoice-flow.md)"
related_guides:
  - "[Business/Website/ecommerce-configuration-guide](ecommerce-configuration-guide.md)"
source_module: website_sale
source_path: ~/odoo/odoo19/odoo/addons/website_sale/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Website Sale Flow

## Overview

This flow covers the end-to-end e-commerce checkout process on an Odoo-powered website. A visitor browses the website, adds products to the cart via `website.sale` controllers, proceeds through address and shipping steps, enters payment details, and triggers a chain that creates or confirms a `sale.order`, processes the payment `payment.transaction`, generates a draft invoice `account.move`, and creates a delivery `stock.picking`. The flow is transactional for the order confirmation step, but payment processing and email sending occur outside the transaction boundary.

## Trigger Point

**User action:** Customer clicks **"Add to Cart"** on a product page, initiating the checkout pipeline. The payment confirmation webhook from the payment provider is an alternative trigger that calls `payment.transaction._set_done()`.

Alternative triggers include:
- **Cart quantity update:** Customer changes quantity in cart — triggers `_cart_update_line_quantity()`.
- **Payment webhook:** External provider (Stripe/Midtrans) POSTs to Odoo's `/payment/notify` endpoint.
- **Portal re-order:** Returning customer places the same order from their order history.
- **Express checkout:** One-page checkout skips address/shipping steps.

---

## Complete Method Chain

```
1. website_sale.add_to_cart()  [controller: cart.py]
   └─► 2. sale.order._cart_add(product_id, quantity)
         └─► 3. _cart_find_product_line(product_id, uom_id)
               ├─► FOUND  → 4. _cart_update_line_quantity(line_id, existing_qty + new_qty)
               │             └─► 5. _verify_updated_quantity()
               │             └─► 6. _cart_update_order_line() → write({'product_uom_qty': qty})
               │                   └─► 7. IF qty <= 0: order_line.unlink()
               │
               └─► NOT FOUND → 8. _verify_updated_quantity()
                              └─► 9. _create_new_cart_line()
                                    └─► 10. sale.order.line.create({product_id, product_uom_qty, order_id, ...})
                                          └─► 11. @api.depends('product_uom_qty') → price recomputed
                                          └─► 12. _check_validity() [combo / stock checks]

   └─► 13. _verify_cart_after_update() [tax recalculation]

=== CUSTOMER PROCEEDS TO CHECKOUT ===

14. website_sale.shop_checkout()  [controller: main.py]
    └─► 15. _check_cart_and_addresses() — validates non-empty cart
    └─► 16. _prepare_checkout_page_values() — renders address form

17. website_sale.shop_address()  [POST — address form submitted]
    └─► 18. _prepare_address_update() → sale.order._update_address(partner_id)
          ├─► 19. sale.order.write({'partner_id': partner_id, 'partner_shipping_id': ..., 'partner_invoice_id': ...})
          ├─► 20. fiscal_position_id recomputed via @api.onchange
          │      └─► 21. _recompute_taxes() — taxes updated based on fiscal position
          └─► 22. _recompute_prices() — pricelist prices updated
                └─► 23. request.session[FISCAL_POSITION_CACHE_KEY] = new_fpos.id

=== SHIPPING STEP ===

24. website_sale.shop_checkout()  [delivery method selection]
    └─► 25. _get_delivery_methods() → available delivery.carrier records
    └─► 26. delivery_method.rate_shipment(order) → rate fetched from carrier API
    └─► 27. _set_delivery_method(delivery_method, rate)
          └─► 28. sale.order.write({'carrier_id': carrier_id, 'amount_delivery': price})

=== PAYMENT STEP ===

29. website_sale.shop_payment()  [controller: main.py]
    └─► 30. _get_shop_payment_values() → payment providers rendered
    └─► 31. payment.acquirer.render() → HTML payment form (Stripe/PayPal/Midtrans iframe)

32. Customer submits payment → external provider processes
    └─► 33. payment.transaction.create({
               'acquirer_id': provider_id,
               'partner_id': partner_id,
               'reference': order.name,
               'amount': order.amount_total,
               'currency_id': order.currency_id.id,
               'state': 'draft'
             })
          └─► 34. payment.provider._get_specific_rendering_values() → provider token/keys

35. Payment provider webhook → POST /payment/notify
    └─► 36. payment.transaction._handle_notification(...)
          ├─► 37. IF success:
          │      └─► 38. _set_done() → write({'state': 'done'})
          │            └─► 39. _update_source_transaction_state()
          │            └─► 40. _log_received_message()
          │            └─► 41. sale.order._create_invoices() [if invoice_policy=prepaid]
          │            └─► 42. _send_payment_succeeded_for_order_mail()
          │
          └─► ELSE IF failure:
                 └─► _set_error(message)

=== ORDER CONFIRMATION ===

43. website_sale.shop_payment_validate()  [after successful payment]
    └─► 44. sale.order._validate_order()
          └─► 45. sale.order.action_confirm()  [see: quotation-to-sale-order-flow]
                ├─► 46. procurement.group.create()
                ├─► 47. stock.picking created via procurement
                ├─► 48. sale.order state → 'sale'
                └─► 49. message_post("Order Confirmed", subtype="sale.mt_order_confirmed")
                      └─► mail.notification created + email sent
                └─► 50. _send_order_notification_mail() → mail.mail queued

51. website_sale.shop_payment_confirmation()
    └─► 52. sale.order._create_invoices()  [if not yet created]
    └─► 53. sale.portal_sale_order_image() → rendered confirmation page
```

---

## Decision Tree

```
Customer clicks "Add to Cart"
│
├─► Product already in cart?
│  ├─► YES → _cart_find_product_line() finds existing line
│  │        └─► _cart_update_line_quantity() — increase qty
│  └─► NO  → _create_new_cart_line() — create new sale.order.line
│
└─► Checkout flow:
   ├─► Address entered → fiscal position determined → taxes recomputed
   │
   ├─► Shipping selected?
   │  ├─► YES → carrier.rate_shipment() called → delivery price set
   │  └─► NO  → skip (services only)
   │
   ├─► Payment step:
   │  ├─► Payment form rendered (acquirer.render())
   │  ├─► Customer submits → external provider
   │  └─► Webhook received → _handle_notification()
   │     ├─► SUCCESS → _set_done() → _validate_order() → action_confirm()
   │     └─► FAILURE → _set_error() → order remains in draft
   │
   └─► ALWAYS after success:
      └─► sale.order confirmed → stock.picking created → mail.mail sent
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `sale_order` | Updated | `state = 'sale'`, `date_order`, `partner_id`, `fiscal_position_id`, `carrier_id`, `amount_delivery` |
| `sale_order_line` | Created | `order_id`, `product_id`, `product_uom_qty`, `price_unit` |
| `payment_transaction` | Created | `acquirer_id`, `partner_id`, `reference`, `amount`, `state = 'done'` |
| `stock_picking` | Created | `origin = order.name`, `group_id = procurement_group.id`, `state = 'confirmed'` |
| `account_move` | Created (draft or posted) | `move_type = 'out_invoice'`, `invoice_origin = order.name`, `partner_id` |
| `procurement_group` | Created | `name = order.name`, `partner_id`, `move_type` |
| `mail_mail` | Created | `mail_message_id`, `state = 'outgoing'/'sent'`, `is_notification = True` |
| `mail_notification` | Created | `mail_message_id`, `res_partner_id`, `notification_type = 'inbox'/'email'` |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Product out of stock | `UserError` or stock warning banner | `_verify_updated_quantity()` checks `product_type` and `type` field; website shows available qty |
| Payment failed / declined | `_set_error()` on tx | Payment provider returns failure; order stays `draft`; customer redirected to retry |
| Address validation failed | `ValidationError` from fiscal position | Fiscal position computation may fail if country not mapped |
| Cart qty limit exceeded | `UserError: "You cannot add more than X"` | `_verify_updated_quantity()` enforces `max_qty` if set on `product.template` |
| Product not published | `UserError: "Product not available"` | `is_published` check in `_cart_add()` via `_is_add_to_cart_allowed()` |
| Order total is 0 (free order) | No payment needed | `shop_payment_validate()` skips payment check: `if not order.amount_total` |
| Duplicate payment callback | `_handle_notification()` idempotent | Checks `reference` + `tx_id` to avoid double-processing |
| Carrier rate unavailable | `UserError: "No delivery method available"` | `_get_delivery_methods()` returns empty; checkout blocks |
| Unpublished website | HTTP 403 | `website` record's `active` field checked in `ir_http._get_website_from_request()` |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Cart created | `sale.order` | New draft `sale.order` created via `website._create_cart()` on first add |
| Order line created/updated | `sale.order.line` | New line or existing line quantity updated |
| Partner created | `res.partner` | New contact created from address form if `partner_id` is new |
| Fiscal position applied | `account.fiscal.position` | Tax mapping applied based on country/state |
| Delivery price added | `sale.order` | `amount_delivery` field updated with carrier rate |
| Payment transaction recorded | `payment.transaction` | Linked to sale order; state transitions: draft → pending → done |
| Stock reserved (or available) | `stock.quant` | `procurement_group.run()` creates moves; picking state = 'confirmed' or 'assigned' |
| Draft invoice created | `account.move` | `_create_invoices()` creates `out_invoice` in draft state |
| Confirmation email sent | `mail.mail` | `ir.mail_server` sends via SMTP; `mail.mail.state = 'sent'` |
| Followers notified | `mail.followers` | Customer + salesman subscribed via `message_post()` |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `add_to_cart()` | Public/guest (auth='public') | None | Session-based cart via `request.cart`; `sudo()` for line creation |
| `_cart_add()` | `sudo()` on `sale.order` | Public user | Internal ORM uses `sudo()` to create lines |
| `shop_address()` | Public/guest | None | `_prepare_address_update()` uses `sudo()` to write on sale order |
| `_update_address()` | `sudo()` | System | Bypasses ACL to write partner_id and fiscal_position |
| `_recompute_taxes()` | Current user | Read on `account.fiscal.position` | Uses pricelist and fiscal position |
| `shop_payment()` | Public/guest | None | Renders payment form; acquirer context |
| `payment.transaction.create()` | `sudo()` | System | Framework-level record creation |
| `_handle_notification()` | `sudo()` | System | Webhook processing bypasses ACL |
| `_validate_order()` / `action_confirm()` | `sudo()` (internally) | `group_sale_salesman` on button | Portal users can confirm via `sale.portal` |
| `mail.mail.send()` | System | `ir.mail_server` access | Uses configured SMTP server |
| `stock.picking.create()` | `sudo()` | System | Procurement framework |

**Key principle:** The website sale flow deliberately runs as `public` user for browsing and `sudo()` for cart/order operations because website visitors are unauthenticated. Payment and confirmation steps use `sudo()` internally to bypass ACL for framework operations.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside.*

```
Steps 1–13   ✅ INSIDE transaction  — cart add/update atomic
Steps 14–28  ✅ INSIDE transaction  — address/shipping write
Steps 29–34  ✅ INSIDE transaction  — payment tx created (draft)
Steps 35–42  ❌ OUTSIDE transaction — webhook from payment provider
Steps 43–53  ✅ INSIDE transaction  — order confirmation (atomic)
Step 50      ❌ OUTSIDE transaction — mail.mail queued via ir.mail_server
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1–13 (cart add) | ✅ Atomic | Rollback on error — no orphaned lines |
| Steps 14–28 (address/shipping) | ✅ Atomic | Rollback if fiscal position fails |
| `payment.transaction.create()` | ✅ Atomic | Draft tx created; webhook processes async |
| `_handle_notification()` | ❌ Outside transaction | External webhook; retried by provider on failure |
| `_validate_order()` | ✅ Atomic | Rollback if `action_confirm()` fails |
| `_send_order_notification_mail()` | ❌ Async queue | Retried by `ir.mail_server` cron; non-blocking |
| `stock.picking.create()` | ✅ Atomic (via procurement) | Rolled back with transaction |
| `account.move` creation | ✅ Atomic (in `action_confirm()`) | Rolled back on error |

**Rule of thumb:** Payment webhook processing (`_handle_notification`) is fully outside the web request transaction — it runs as a separate HTTP handler and commits independently. This prevents double-payment race conditions but means order confirmation can fail after the payment tx is marked `done`.

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-click "Add to Cart" | Two HTTP requests; `_cart_find_product_line()` deduplicates by product_id+uom_id — only one line updated |
| Add same product twice rapidly | Second add sees first line; `_cart_update_line_quantity()` accumulates quantities |
| Payment webhook called twice | `_handle_notification()` checks `reference` + idempotency — second call is no-op |
| `action_confirm()` re-triggered on confirmed order | Early return: `if self.state != 'quotation': return True` — no-op |
| Re-access confirmation page | `shop_payment_confirmation()` re-fetches order — safe read-only display |
| Duplicate `procurement.group` creation | `procurement.group.create()` is NOT idempotent — new group each time (but only called once from `action_confirm()`) |

**Common patterns:**
- **Idempotent:** `_cart_add()`, `_cart_update_line_quantity()`, `action_confirm()` (state guard), `_handle_notification()` (idempotency key)
- **Non-idempotent:** `sale.order.line.create()` (new record), `procurement.group.create()` (new record each time), `ir.sequence` number consumed

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 5 | `_verify_updated_quantity()` | Stock validation, max qty check | `order_line, product_id, new_qty, uom_id` | Extend to add custom stock rules |
| Step 9 | `_create_new_cart_line()` | Pre/post line creation hook | `product_id, quantity, uom_id` | Add custom line defaults |
| Step 11 | `@api.depends('product_uom_qty')` | Dynamic price recalculation | auto | Computed field triggers on qty change |
| Step 18 | `_update_address()` | Custom address processing | `partner_id, fnames` | Add field sync for custom fields |
| Step 19 | `sale.order.write()` | Pre-address-write hook | vals dict | Add validation before write |
| Step 21 | `_recompute_taxes()` | Tax recalculation override | — | Extend to skip or modify taxes |
| Step 25 | `_get_delivery_methods()` | Filter available carriers | `self` | Override to hide/exclude carriers |
| Step 26 | `rate_shipment()` | Custom rate calculation | `order` | Override on `delivery.carrier` |
| Step 30 | `_get_shop_payment_values()` | Add custom payment options | `order` | Add特约 provider or token |
| Step 38 | `_set_done()` | Post-payment hook | — | Add post-payment processing |
| Step 45 | `_validate_order()` | Pre-confirmation hook | `self` | Extend with `super()` + additional logic |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def _cart_add(self, product_id, quantity):
    # your code

# CORRECT — extends with super()
def _cart_add(self, product_id, quantity, **kwargs):
    res = super()._cart_add(product_id, quantity, **kwargs)
    # your additional code
    return res
```

**Odoo 19 specific hooks:**
- `_cart_find_product_line()` can be overridden to change line-matching logic for custom products
- `_update_address()` can be extended to handle custom partner field mappings
- `payment.transaction._handle_notification()` is the main extension point for custom payment providers
- `_get_shop_payment_values()` on the controller can be extended via `_extend_shop_payment_values()`

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct workflow engine calls (deprecated — use `action_*` methods)
- Overriding `action_confirm()` without calling `super()` — breaks procurement/picking chain

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `add_to_cart()` | `sale.order.line.unlink()` | Remove line manually or set qty=0 | Only affects cart; no financial impact |
| `action_confirm()` | `action_cancel()` | `sale.order.action_cancel()` | Cancels pickings and stock moves if not `done` |
| `action_cancel()` | `action_draft()` | `sale.order.action_draft()` | Resets to `quotation`; pickings must be `cancel` |
| `stock.picking` created | `action_cancel()` on picking | `stock.picking.action_cancel()` | Only if not `done`; unreserves quants |
| `account.move` draft invoice | `unlink()` | `account.move.unlink()` | Only in `draft` state |
| Posted invoice | `action_reverse()` | Creates credit note | Original invoice immutable; credit note new record |
| Payment captured | Refund via acquirer | `payment.transaction.refund()` | Depends on provider support |
| Free order (no tx) | `action_cancel()` | Manual | No financial entry to reverse |

**Important:** This flow is **partially reversible**:
- Cart changes are trivially reversible by editing or clearing the cart
- `action_confirm()` cancellation triggers `stock.picking.action_cancel()` which unreserves stock
- Paid payment transactions may require a refund through the payment provider (not automatic)
- `action_cancel()` does NOT automatically cancel a paid invoice — invoice reversal is manual

---

## Alternative Triggers

> *All the ways this flow can be initiated.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `add_to_cart()` — "Add to Cart" button | Interactive (website) | Manual |
| User action | `shop_address()` — address form | Interactive (website) | Manual |
| User action | `shop_payment()` — payment form | Interactive (website) | Manual |
| Webhook | `POST /payment/notify` | Payment provider server | On payment event |
| Cron scheduler | `sale.order._cron_auto_confirm()` | Server | Configurable |
| Portal | `sale.portal()` controller | Authenticated customer | On portal confirmation |
| Express checkout | `process_express_checkout()` | Google/Apple Pay | Manual |
| Automated action | `base.automation` rule | On cart state change | On rule match |

---

## Related

- [Modules/Sale](Sale.md) — Sale module reference
- [Modules/website_sale](website_sale.md) — Website sale module reference
- [Flows/Sale/quotation-to-sale-order-flow](quotation-to-sale-order-flow.md) — Sale order confirmation flow
- [Flows/Sale/sale-to-delivery-flow](sale-to-delivery-flow.md) — Delivery creation from confirmed order
- [Flows/Sale/sale-to-invoice-flow](sale-to-invoice-flow.md) — Invoice creation from sale order
- [Business/Website/ecommerce-configuration-guide](ecommerce-configuration-guide.md) — E-commerce setup guide
- [Patterns/Workflow Patterns](Workflow Patterns.md) — Workflow pattern reference
- [Core/API](API.md) — @api decorator patterns
