# Payment AsiaPay (`payment_asiapay`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Payment Provider: AsiaPay |
| **Technical** | `payment_asiapay` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |

## Description
Multi-brand Asian payment provider. AsiaPay operates several regional payment brands (PayDollar, PesoPay, SiamPay, BimoPay) across Hong Kong, Southeast Asia, China, Philippines, Thailand, and more. Supports card payments, local bank transfers, and digital wallets via server-to-server API with secure hash signature verification.

## Coverage
Hong Kong (PayDollar), Philippines (PesoPay), Thailand (SiamPay), Indonesia (BimoPay), and other Asia-Pacific markets

## Technical Notes
- API: AsiaPay payment API (per-brand URLs)
- Brand selection: PayDollar, PesoPay, SiamPay, BimoPay
- Signature: HMAC-SHA1/SHA256/SHA512 with merchant secret key
- Currency: One currency per provider account (from supported set)

## Provider Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `asiapay_brand` | Selection | Brand: `paydollar`, `pesopay`, `siampay`, `bimopay` |
| `asiapay_merchant_id` | Char | Merchant ID for account identification |
| `asiapay_secure_hash_secret` | Char | Secret key for HMAC signature generation |
| `asiapay_secure_hash_function` | Selection | Hash algorithm: `sha1`, `sha256`, `sha512` |

## Models

### `payment.provider` (Extended)
**Key methods:**
- `_get_default_payment_method_codes()` — Returns AsiaPay default payment method codes
- `_asiapay_get_api_url()` — Returns brand-specific API URL based on provider state (production/test) and selected brand
- `_asiapay_calculate_signature(data, incoming)` — Computes HMAC signature using configured hash function and secret; signs concatenated data fields with `|` separator. Separate key sets for incoming (webhook) and outgoing (API) signatures

**Constraints:**
- `_limit_available_currency_ids()` — One currency per AsiaPay account; currency must be in AsiaPay's supported set

## Signature Generation
Outgoing: `merchant_id|merchant_reference|amount|currency|payment_type|secure_hash_secret`
Incoming: merchant_id + reference + status + ... + secure_hash_secret
Uses `hashlib.new(algorithm)` with hex digest output.

## Related
- [Modules/payment](modules/payment.md) — Base payment engine
- [Modules/payment_paymob](modules/payment_paymob.md) — Paymob provider (similar multi-country gateway)
- [Modules/payment_stripe](modules/payment_stripe.md) — Stripe provider
