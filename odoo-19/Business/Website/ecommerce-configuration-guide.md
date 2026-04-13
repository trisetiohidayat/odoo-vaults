---
type: guide
title: "E-commerce Configuration Guide"
module: website_sale
submodule: website_sale
audience: business-consultant, e-commerce-manager, developer
level: 2
prerequisites:
  - website_configured
  - payment_acquirers_setup
  - shipping_methods_configured
  - products_published
  - company_settings_completed
  - currencies_configured
estimated_time: "~20 minutes"
related_flows:
  - "[Flows/Website/website-sale-flow](Flows/Website/website-sale-flow.md)"
  - "[Flows/Sale/quotation-to-sale-order-flow](Flows/Sale/quotation-to-sale-order-flow.md)"
  - "[Flows/Sale/sale-to-delivery-flow](Flows/Sale/sale-to-delivery-flow.md)"
  - "[Flows/Website/website-sale-flow](Flows/Website/website-sale-flow.md)"
related_guides:
  - "[Modules/website_sale](Modules/website_sale.md)"
  - "[Modules/payment_stripe](Modules/payment_stripe.md)"
  - "[Business/Stock/warehouse-setup-guide](Business/Stock/warehouse-setup-guide.md)"
source_module: website_sale
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# E-commerce Configuration Guide

> **Quick Summary:** This guide walks through the complete configuration of an Odoo e-commerce website — setting up payment providers (Stripe/Midtrans), shipping methods (standard, express, local pickup), and product pages with variants and optional accessories.

**Actor:** E-commerce Manager / IT Administrator
**Module:** Website > Website Sale
**Use Case:** Configure a fully functional e-commerce store with payment processing and delivery options
**Difficulty:** ⭐⭐ Medium

---

## Prerequisites Checklist

Before starting, ensure the following are configured. Skipping these will cause errors or missing features.

- [ ] **Website created** — Website record in `Website > Configuration > Websites`
- [ ] **Company configured** — Company with address, logo, and fiscal country set in `Settings > General > Companies`
- [ ] **Payment acquirers installed** — `payment_stripe`, `payment_midtrans`, or custom providers activated in `Website > Configuration > Payment Providers`
- [ ] **Shipping methods configured** — `delivery.carrier` records created in `Website > Configuration > Shipping Methods`
- [ ] **Products published** — `product.template` records with `is_published = True` and website category assigned
- [ ] **Pricelists set** — `product.pricelist` assigned to website in `Website > Configuration > Pricelists`
- [ ] **Currency configured** — Company's currency matches the website's allowed currencies
- [ ] **Email server configured** — `ir.mail_server` set up for order confirmation emails in `Settings > General > Email`

> **⚠️ Critical:** If payment acquirers are not configured, the checkout will fail at the payment step with a "No payment method available" error. If no shipping methods are configured, the shipping step will be skipped (only for service products).

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Website/website-sale-flow](Flows/Website/website-sale-flow.md) | Full method chain and branching logic |
| 📖 Module Reference | [Modules/website_sale](Modules/website_sale.md) | Complete field and method reference |
| 📋 Related Guide | [Modules/website_sale](Modules/website_sale.md) | Website publishing checklist |
| 🔧 Configuration | [Modules/payment_stripe](Modules/payment_stripe.md) | Payment provider configuration |

---

## Use Cases Covered

This guide covers the following use cases. Jump to the relevant section:

| # | Use Case | Page | Difficulty |
|---|----------|------|-----------|
| 1 | Configure website with payment providers (Stripe/Midtrans) | [#use-case-1-configure-payment-providers](#use-case-1-configure-payment-providers.md) | ⭐⭐ |
| 2 | Set up shipping methods (standard/express/local pickup) | [#use-case-2-configure-shipping-methods](#use-case-2-configure-shipping-methods.md) | ⭐⭐ |
| 3 | Configure product pages with variants and optional accessories | [#use-case-3-configure-product-pages-with-variants](#use-case-3-configure-product-pages-with-variants.md) | ⭐⭐ |

---

## Use Case 1: Configure Payment Providers

*[Stripe and Midtrans configuration — online payment processing]*

### Scenario

A business wants to sell products online and needs to accept credit card and digital wallet payments. The store uses Stripe as the primary payment provider and Midtrans as an alternative for Southeast Asian customers.

### Steps

#### Step 1 — Access Payment Provider Settings

Navigate to: `Website > Configuration > Payment Providers`

> **⚡ System Behavior:** This page lists all available payment providers (acquirers) from the `payment` module. Providers with a green dot are active and shown at checkout.

#### Step 2 — Configure Stripe

Click on **Stripe** provider record.

| Field | Value | Required | Auto-filled |
|-------|-------|----------|------------|
| **State** | `enabled` | ✅ Yes | `disabled` by default |
| **Stripe Publishable Key** | `pk_live_...` | ✅ Yes | — |
| **Stripe Secret Key** | `sk_live_...` | ✅ Yes | — |
| **Stripe Webhook Secret** | `whsec_...` | ✅ Yes | — |
| **Allow express checkout** | ✅ Checked | No | — |
| **Allow payment method types** | `card`, `gpay`, `apple_pay` | No | `card` default |
| **Supported currencies** | USD, EUR, IDR | ✅ Yes | From company |

> **⚡ System Trigger:** When the Stripe keys are saved, Odoo automatically validates the connection via `payment.stripe._stripe_check_credentials()` — if invalid, a red banner appears with the error message.

> **⚡ Side Effect:** Once enabled, Stripe appears as a payment option at `website/shop/payment` step. The `payment.transaction` will be created with `acquirer_id = stripe.id` on the checkout form submission.

#### Step 3 — Configure Midtrans

Click on **Midtrans** provider record (install `payment_midtrans` module first via `Apps`).

| Field | Value | Required | Auto-filled |
|-------|-------|----------|------------|
| **State** | `enabled` | ✅ Yes | `disabled` by default |
| **Client Key** | `VT-client-...` | ✅ Yes | — |
| **Server Key** | `VT-server-...` | ✅ Yes | — |
| **Environment** | `production` / `sandbox` | ✅ Yes | `sandbox` default |
| **Payment methods** | `gopay`, `ovo`, `dana`, `bank_transfer` | No | All available |

> **⚡ System Trigger:** Midtrans uses `payment_midtrans` specific `acquirer_state` fields. When set to `production`, live transactions are processed. The webhook URL is auto-generated: `https://your-domain.com/payment/midtrans/notify`.

#### Step 4 — Configure Payment Flow Options

Navigate: `Website > Configuration > Settings > Sale`

| Field | Value | Notes |
|-------|-------|-------|
| **Require Payment Validation** | ✅ Checked | Orders confirmed only after payment confirmed |
| **Maximum Invoice Outstanding** | `1,000,000` | Max outstanding invoice before blocking |
| **Invoice Payment Terms** | Immediate | Payment terms applied to website orders |
| **Mail Sending** | `by customer` | Order confirmation sent to customer |

#### Step 5 — Set Payment Callback (Webhook)

The payment provider's webhook must point to Odoo's endpoint. For Stripe:

**Stripe Dashboard > Webhooks:**
- Endpoint URL: `https://your-domain.com/payment/stripe/webhook`
- Events: `payment_intent.succeeded`, `payment_intent.payment_failed`

> **⚡ Side Effect:** When the webhook fires, Odoo's `payment.transaction._handle_notification()` processes the payment confirmation. This creates the `payment.transaction` record with `state = 'done'` and triggers `sale.order._validate_order()` → `action_confirm()`.

#### Step 6 — Test Payment Flow

Use Stripe's test mode or Midtrans sandbox:
- Add a product to cart and proceed to checkout
- Select Stripe/Midtrans as the payment method
- Use test card numbers: Stripe test card `4242 4242 4242 4242`
- Complete payment
- Verify `sale.order` state transitions to `sale`
- Verify `payment.transaction` record shows `state = 'done'`

**Expected Results Checklist:**
- [ ] Payment provider shows green "Enabled" status
- [ ] Payment form appears at checkout with provider logo
- [ ] Test transaction creates `payment.transaction` with `state = 'done'`
- [ ] Order confirmation email is sent to customer
- [ ] `sale.order` is automatically confirmed

---

## Use Case 2: Configure Shipping Methods

*[Standard delivery, express delivery, and local pickup]*

### Scenario

The store sells physical products and needs three delivery options: free standard shipping for orders over a threshold, paid express delivery with next-day guarantee, and free local pickup from the warehouse. Each option requires a `delivery.carrier` record with rate computation.

### Steps

#### Step 7 — Access Shipping Method Configuration

Navigate to: `Website > Configuration > Shipping Methods`

Click **New**.

#### Step 8 — Configure Free Standard Shipping (Orders Over $50)

| Field | Value | Required | Notes |
|-------|-------|----------|-------|
| **Name** | `Free Standard Shipping` | ✅ Yes | Shown to customer |
| **Provider** | `Based on Rules` | ✅ Yes | Internal delivery rules |
| **Verification** | `Prod. Amount >= 50` | ✅ Yes | Rule: free if order >= $50 |
| **Free if order amount is at least** | `50.00` | ✅ Yes | Threshold amount |
| **Delivery Product** | `Delivery - Standard` | ✅ Yes | Auto-created product |
| **Website** | Select your website | ✅ Yes | Restricts to this website |
| **Active** | ✅ Checked | ✅ Yes | — |

Click **Save**.

#### Step 9 — Configure Paid Express Delivery (Fixed Rate)

Click **New** again.

| Field | Value | Required | Notes |
|-------|-------|----------|-------|
| **Name** | `Express Delivery (Next Day)` | ✅ Yes | — |
| **Provider** | `Fixed Delivery` | ✅ Yes | Fixed rate regardless of weight |
| **Rate** | `15.00` | ✅ Yes | Fixed $15.00 charge |
| **Delivery Product** | `Delivery - Express` | ✅ Yes | Auto-created |
| **Website** | Select your website | ✅ Yes | — |
| **Active** | ✅ Checked | ✅ Yes | — |

Click **Save**.

#### Step 10 — Configure Local Pickup (Free)

Click **New**.

| Field | Value | Required | Notes |
|-------|-------|----------|-------|
| **Name** | `Local Pickup` | ✅ Yes | — |
| **Provider** | `Local Pickup` | ✅ Yes | In-store pickup option |
| **Delivery Product** | `Local Pickup - Free` | ✅ Yes | $0.00 product |
| **Warehouse** | `Main Warehouse` | ✅ Yes | Pickup location source |
| **Website** | Select your website | ✅ Yes | — |
| **Active** | ✅ Checked | ✅ Yes | — |

Click **Save**.

#### Step 11 — Configure Delivery Based on Rules (Weight-Based)

For products with variable weight, use rule-based delivery:

Click **New**.

| Field | Value | Required | Notes |
|-------|-------|----------|-------|
| **Name** | `Weight-Based Delivery` | ✅ Yes | — |
| **Provider** | `Based on Rules` | ✅ Yes | — |
| **Website** | Select your website | ✅ Yes | — |
| **Active** | ✅ Checked | ✅ Yes | — |

Add rules in the **Rules** tab:

| Condition | Type | Amount | Max Total | Price |
|-----------|------|--------|----------|-------|
| 0–1 kg | Weight | 0–1 | 1.0 | $5.00 |
| 1–5 kg | Weight | 1.01–5.0 | 5.0 | $10.00 |
| >5 kg | Weight | 5.01+ | — | $20.00 |

Click **Save**.

#### Step 12 — Assign Products to Shipping Methods

Navigate to: `Website > Configuration > Shipping Methods`

Each product can be restricted to specific delivery methods:

| Field on Product | Purpose |
|-----------------|---------|
| `website_shipping_method_ids` | Shipping methods available for this product |
| `weight` | Used by weight-based delivery rules |
| `volume` | Used by volume-based delivery rules |

#### Step 13 — Test Shipping Methods

Add a physical product to cart and proceed to checkout:

**Test 1 — Free standard shipping (order >= $50):**
- Add products totaling $60 to cart
- Proceed to checkout → shipping step
- Verify "Free Standard Shipping" is shown as free
- Select it → verify no delivery charge added

**Test 2 — Express delivery (order < $50):**
- Reduce cart to $30
- Proceed to checkout → shipping step
- Verify "Express Delivery (Next Day)" at $15.00 is shown
- Verify "Free Standard Shipping" is shown with $5.00 charge
- Select Express → verify $15.00 added to order total

**Test 3 — Local pickup:**
- Proceed to checkout → shipping step
- Verify "Local Pickup" shown if warehouse is configured
- Select it → verify delivery charge = $0.00

**Expected Results Checklist:**
- [ ] All three shipping methods appear at checkout (context-dependent)
- [ ] Correct price applied for each option
- [ ] Free threshold applied correctly
- [ ] Total order amount reflects selected shipping cost
- [ ] Delivery carrier saved on `sale.order.carrier_id`

---

## Use Case 3: Configure Product Pages with Variants

*[Product variants (size/color) and optional accessories]*

### Scenario

The store sells t-shirts in multiple sizes and colors (variants) and wants to show optional accessories (phone case, screen protector) as "Add-on" suggestions on the product page.

### Steps

#### Step 14 — Set Up Product Attributes (Size, Color)

Navigate to: `Website > Products > Attributes`

Click **New**.

| Field | Value | Notes |
|-------|-------|-------|
| **Name** | `Size` | — |
| **Display Type** | `Radio` | Show as radio buttons on website |
| **Variants Creation Mode** | `Instantly` | Create all combinations |

In the **Attribute Values** tab, add:

| Value | HTML Color | Extra Price |
|-------|-----------|-------------|
| `S` | — | $0.00 |
| `M` | — | $0.00 |
| `L` | — | $0.00 |
| `XL` | — | $2.00 |

Click **Save**.

Create another attribute:

| Field | Value | Notes |
|-------|-------|-------|
| **Name** | `Color` | — |
| **Display Type** | `Color` | Color swatches on website |

In the **Attribute Values** tab:

| Value | HTML Color | Extra Price |
|-------|-----------|-------------|
| `Red` | `#FF0000` | $0.00 |
| `Blue` | `#0000FF` | $0.00 |
| `Black` | `#000000` | $0.00 |

Click **Save**.

#### Step 15 — Create Product with Variants

Navigate to: `Website > Products > Products`

Click **New**.

| Field | Value | Notes |
|-------|-------|-------|
| **Product Name** | `Premium T-Shirt` | — |
| **Product Type** | `Storable Product` | Has stock tracking |
| **Price** | `25.00` | Base price |
| **Cost** | `12.00` | For margin calculation |
| **Internal Reference** | `PTS-001` | SKU |
| **Barcode** | `1234567890` | — |

Click **Save**.

#### Step 16 — Add Attribute to Product

On the product form, go to the **Attributes** tab.

Click **Add a line**:

| Attribute | Create Variants |
|-----------|----------------|
| `Size` | ✅ Checked |

Click **Generate Variants**.

> **⚡ System Behavior:** Odoo creates `product.product` variant records for each size. The product page will show a combination selector. The `sale.order.line` stores the selected `product_id` (variant), not just the `product_template_id`.

Repeat for **Color** attribute.

> **⚡ Side Effect:** After generating variants, you can set variant-specific prices (e.g., XL at +$2.00) by editing each `product.product` record from the Variants subtab.

#### Step 17 — Set Up Optional Accessories (Add-on Products)

On the product form, go to the **Optional Products** tab.

These are products suggested as add-ons when the main product is added to cart.

Click **Add an Optional Product**:

| Product | Extra Price |
|---------|-------------|
| `Phone Case` | $10.00 |
| `Screen Protector` | $5.00 |
| `Earphones` | $25.00 |

> **⚡ System Behavior:** When a customer clicks "Add to Cart" on the main product, a modal appears suggesting optional accessories. Each selected optional product creates a separate `sale.order.line` with `linked_line_id` pointing to the main line.

#### Step 18 — Configure Website Display

Navigate to the product page on the website (`/shop/product/[id]`):

**Test variant selection:**
- Open the product page
- Verify size radio buttons appear
- Verify color swatches appear as colored circles
- Select a combination (e.g., "L" + "Red")
- Verify price updates if applicable (+$2.00 for XL)
- Click "Add to Cart" → optional products modal appears

**Test optional products:**
- Optional products shown in the modal
- Select "Phone Case" → added to cart as linked line
- Verify cart shows two lines: main T-shirt and Phone Case
- Verify phone case line shows `linked_line_id` to T-shirt line

#### Step 19 — Assign Product to Website Category

Navigate: `Website > Products > Product Categories`

Create or select a category (e.g., `Apparel > T-Shirts`).

On the product form, set:

| Field | Value |
|-------|-------|
| **Website Category** | `Apparel > T-Shirts` |

> **⚡ System Trigger:** Products without a website category appear in "All Products" on the shop page. Products with a category appear under the category navigation menu on the website.

#### Step 20 — Publish the Product

On the product form:

| Field | Value | Notes |
|-------|-------|-------|
| **Available on eCommerce** | ✅ Checked | `is_published = True` |
| **Public Category** | `Apparel > T-Shirts` | Shop navigation |
| **Website Sequence** | `1` | Display order in category |

> **⚡ System Behavior:** When `is_published = False`, the product does not appear in the shop search or category listing. The product can still be added via direct URL if known.

**Expected Results Checklist:**
- [ ] Product page shows variant selectors (size + color)
- [ ] Variant combination updates price display correctly
- [ ] "Add to Cart" opens optional products modal
- [ ] Optional products added as linked lines in cart
- [ ] Cart shows main product and optional products separately
- [ ] Product appears in shop category listing
- [ ] All combinations have stock tracked (if inventory enabled)

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Payment provider keys set to test mode in production | Payments not captured; orders remain in draft | Always switch to live keys before going live; test first in sandbox |
| 2 | Webhook URL not accessible from internet | Payment confirmed in provider but Odoo order not confirmed | Test webhook URL is reachable: `curl -X POST https://your-domain.com/payment/[provider]/notify` |
| 3 | Stripe/Midtrans module not installed | Payment provider not visible in `Configuration > Payment Providers` | Install via `Apps`: search `payment_stripe`, `payment_midtrans` |
| 4 | Shipping method not assigned to website | Shipping option not shown at checkout | Always set the `website_ids` field on the delivery.carrier record |
| 5 | Product variants not generated | "No matching product found" error on product page | Click **Generate Variants** after adding attributes |
| 6 | Product not published | 404 error on product page | Set `is_published = True` on the product template |
| 7 | Missing delivery product on carrier | Delivery cost not added to order | Odoo auto-creates a `delivery.product` when the carrier is saved |
| 8 | Currency mismatch | Payment amount shown as 0 or incorrect | Website's `website_pricelist_ids` must include the company's currency |
| 9 | No SMTP server configured | Order confirmation email not sent | Configure `ir.mail_server` in `Settings > General > Email` |
| 10 | Product has no `is_published` and no website category | Product hidden from shop but visible in cart if URL known | Always set both `is_published` and website category for products intended for sale |

---

## Configuration Deep Dive

### Related Configuration Paths

| Configuration | Menu Path | Controls |
|--------------|-----------|----------|
| Payment Providers | `Website > Configuration > Payment Providers` | Acquirers, credentials, state |
| Shipping Methods | `Website > Configuration > Shipping Methods` | Carriers, rates, rules |
| Product Attributes | `Website > Products > Attributes` | Variants, display type, extra prices |
| Product Categories | `Website > Products > Product Categories` | Shop navigation hierarchy |
| Website Settings | `Website > Configuration > Settings` | Checkout flow, confirmation email |
| Pricelists | `Website > Configuration > Pricelists` | Pricing rules per website |
| Currency | `Settings > General > Multi-Currency` | Enabled currencies for website |
| Email Server | `Settings > General > Email > Email Servers` | SMTP for order notifications |

### Advanced Options

| Option | Field Name | Default | Effect When Enabled |
|--------|-----------|---------|-------------------|
| Express Checkout | `express_checkout` | Disabled | One-page checkout via Google/Apple Pay |
| Payment Icons | `payment_icon_ids` | — | Shows card icons next to payment form |
| Custom Confirmation Email | `confirmation_email_template_id` | Default sale order template | Sends custom template on order confirmation |
| Redirect After Payment | `redirect_after_payment` | `/shop/confirmation` | Custom URL post-payment |
| Free Shipping Threshold | `amount_threshold` | None | Free shipping when order >= threshold |
| Shipping by Weight Rules | `price_rule_ids` | — | Complex rate calculation based on weight/volume/destination |
| Allow out-of-stock | `allow_out_of_stock` | True | Continue selling even when stock is 0 |
| Available for Variant Selection | `website_variant_add` | Inline | Show attribute selectors inline or in modal |
| Offer Free Shipping | `fixed_cost` = 0 | — | Removes delivery line from order |

### Shipping Rate Computation Methods

| Method | Source | Use Case |
|--------|--------|---------|
| `Based on Rules` | Internal | Most common — rules based on order amount, weight, or volume |
| `Fixed Delivery` | Internal | Fixed price regardless of order characteristics |
| `Local Pickup` | Internal | No delivery — customer picks up from warehouse |
| `Delivery by USPS/FedEx/DHL` | External API | Real-time carrier rates (requires API credentials) |
| `On Delivery` | None | No automatic rate — customer pays upon delivery |

### Payment Provider State Machine

```
payment.transaction state transitions:
  draft → pending → authorized → done
                  → error → pending (retry)
        → cancel  → draft (retry)
  done  → cancel  → refund (provider-dependent)
```

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| Payment provider not appearing at checkout | Provider state = `disabled` | Go to `Website > Configuration > Payment Providers` → click provider → set state = `enabled` |
| "No shipping method available" at checkout | No `delivery.carrier` assigned to website | Check `website_ids` on each delivery.carrier record |
| Variant selector not showing on product page | Variants not generated | On product form, go to Attributes tab → click **Generate Variants** |
| Optional products not appearing after add to cart | `optional_product_removable` not set | Check the `optional_product_ids` field on the product template |
| Order not auto-confirmed after payment | Webhook not received | Check Stripe/Midtrans webhook logs; verify endpoint URL is public |
| Product not in shop search results | `is_published = False` | Edit product → check "Available on eCommerce" |
| Shipping price is $0.00 for all options | Rate computation returning 0 | Check delivery.carrier rules; verify `fixed_cost` is set |
| Email not sent after order confirmation | SMTP server misconfigured | Test email server: `Settings > General > Email > Email Servers > Test Connection` |
| Cart line shows wrong price | Pricelist not applied | Verify website has correct pricelist in `Website > Configuration > Pricelists` |
| Payment transaction stuck in `pending` | Webhook processing failed | Check `payment.transaction` state; manually trigger `_handle_notification()` or reset to `draft` |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Website/website-sale-flow](Flows/Website/website-sale-flow.md) | Full method chain — for developers |
| 📖 Module Reference | [Modules/website_sale](Modules/website_sale.md) | Complete field and method list |
| 📋 Related Guide | [Modules/website_sale](Modules/website_sale.md) | Website publishing and SEO |
| 🔧 Patterns | [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) | Workflow design patterns |
| 🛠️ Snippets | [Snippets/Model Snippets](Snippets/Model-Snippets.md) | Code snippets for customization |
| 💳 Payment | [Modules/payment_stripe](Modules/payment_stripe.md) | Detailed payment provider setup |
| 🚚 Delivery | [Business/Stock/warehouse-setup-guide](Business/Stock/warehouse-setup-guide.md) | Advanced delivery configuration |
