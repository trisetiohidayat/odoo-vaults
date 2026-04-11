---
title: POS Stripe
description: Integrates Stripe terminal (card present) with the Point of Sale. Handles payment intent creation, terminal pairing, and manual capture for tips.
tags: [odoo19, pos, payment, stripe, module]
model_count: 1
models:
  - pos.payment.method (stripe_serial_number, payment intent methods)
dependencies:
  - point_of_sale
  - payment_stripe
category: Sales/Point of Sale
source: odoo/addons/pos_stripe/
created: 2026-04-06
---

# POS Stripe

## Overview

**Module:** `pos_stripe`
**Category:** Sales/Point of Sale
**Depends:** `point_of_sale`, `payment_stripe`
**License:** LGPL-3

Integrates Stripe terminal (card present / in-store payments) with the Odoo Point of Sale. Uses the Stripe Connect API for terminal connection tokens and `payment_intents` with `manual capture` for tip adjustment.

## Key Features

- Stripe terminal integration via Stripe API
- Payment intent creation with `card_present` payment method type
- Manual capture for tip adjustment (capture amount can exceed authorized amount)
- Terminal serial number management
- Connection token fetching for terminal pairing
- AUD/CAD regional overrides (Interac, capture method preferences)
- Redirect to Stripe provider settings via `action_stripe_key()`

## Models

### pos.payment.method (inherited)

| Field | Type | Description |
|-------|------|-------------|
| `stripe_serial_number` | Char | Terminal serial number, e.g., `WSC513105011295` |

**Key Methods:**
- `_get_payment_terminal_selection()` — adds `('stripe', 'Stripe')` to terminal options
- `_load_pos_data_fields()` — sends `stripe_serial_number` to POS frontend
- `_check_stripe_serial_number()` — validates uniqueness of serial number across payment methods
- `_get_stripe_payment_provider()` — searches for `payment.provider` with code `stripe` for the current company
- `stripe_connection_token()` — RPC to fetch Stripe Terminal connection token for onboarding
- `_stripe_calculate_amount()` — converts amount to Stripe's smallest currency unit (rounds by currency `rounding`)
- `stripe_payment_intent()` — creates a Stripe `payment_intent` with `card_present` type and `capture_method=manual`; supports AUD/Interac and CAD/Interac regional overrides
- `stripe_capture_payment()` — captures a payment intent; allows over-capture for tips by specifying `amount_to_capture`
- `action_stripe_key()` — opens the Stripe payment provider form view

## Payment Flow

1. **Terminal pairing:** POS calls `stripe_connection_token()` to get a connection token from Stripe
2. **Payment intent:** POS calls `stripe_payment_intent(amount)` to create a payment intent; receives `client_token`
3. **Terminal capture:** POS uses Stripe Terminal SDK with `client_token` to collect card from hardware
4. **Authorization:** Stripe authorizes the payment on the terminal
5. **Capture:** POS calls `stripe_capture_payment(paymentIntentId, amount)` — where `amount` includes the tip — to capture funds

## Manual Capture for Tips

The module uses `capture_method=manual` on payment intents. This allows:
- Pre-authorization at the base amount
- Subsequent capture at a higher amount (base + tip)
- The `stripe_capture_payment()` method sends `amount_to_capture` in Stripe's smallest currency unit

## Source Files

- `models/pos_payment_method.py` — Stripe terminal integration, payment intent creation/capture
