---
type: module
title: "Rental — Equipment Rental & Asset Lease"
description: "Equipment rental management with rental quotations, contracts, asset tracking, and return handling. Extends Sale and Stock modules."
source_path: ~/odoo/odoo19/odoo/addons/rental/
tags:
  - odoo
  - odoo19
  - module
  - rental
  - lease
  - equipment
related_modules:
  - sale
  - stock
  - fleet
created: 2026-04-07
version: "1.0"
---

## Quick Access

### 🔀 Related Flows
- [Flows/Sale/quotation-to-sale-order-flow](Flows/Sale/quotation-to-sale-order-flow.md) — Rental quotation workflow
- [Flows/Sale/sale-to-invoice-flow](Flows/Sale/sale-to-invoice-flow.md) — Rental invoicing
- [Flows/Stock/delivery-flow](Flows/Stock/delivery-flow.md) — Rental product delivery

### 🔗 Related Modules
- [Modules/Sale](Modules/Sale.md) — Rental quotation base
- [Modules/Stock](Modules/Stock.md) — Rental inventory management
- [Modules/Fleet](Modules/Fleet.md) — Vehicle rental tracking

---

## Module Overview

| Property | Value |
|----------|-------|
| **Name** | Rental |
| **Technical Name** | `rental` |
| **Category** | Sales / Rental |
| **Summary** | Equipment rental and asset lease management |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Installable** | Yes (requires `sale` + `stock`) |

### Description

The Rental module extends the Sale and Stock modules to support equipment and asset rental workflows. It allows businesses to:
- Define rental products with pricing per time unit (hour/day/week/month)
- Create rental quotations and contracts
- Track rental inventory separately from sale inventory
- Handle pickup and return of rental assets
- Generate invoices based on rental periods

Rental products can be set with different pricing tiers for short-term vs. long-term rentals, with automatic invoicing at contract milestones.

---

## Key Models

### 1. Rental Order (extends `sale.order`)

Rental orders extend sale orders with rental-specific fields.

**Key Fields:**
- `rental_order_line_ids` — Rental-specific order lines
- `pickup_date` — Scheduled pickup date
- `return_date` — Scheduled return date
- `pickup_location_id` — Pickup warehouse/location
- `return_location_id` — Return warehouse/location

---

### 2. Rental Product (`rental.product.template`)

Defines product as rentable with per-period pricing.

**Key Fields:**
- `rent_ok` — Mark product as available for rent
- `rental_pricing_ids` — Pricing rules per time period
- `preparation_time` — Setup/prep time before rental

**Rental Pricing:**
- Define pricing for `hour`, `day`, `week`, `month` periods
- Set different unit prices per period
- Support for volume-based pricing (qty breaks)

---

### 3. Fleet Vehicle (`fleet.vehicle`)

Vehicles tracked as rental assets.

**Key Fields:**
- `model_id` — Vehicle model
- `license_plate` — License plate
- `state_id` — Vehicle state (available/rented/maintenance)
- `rental_contract_id` — Active rental contract
- `driver_id` — Assigned driver

---

## Common Workflows

### Rental Quotation
1. Go to **Rental → Quotation → Create**
2. Select a rental product — pricing auto-fills based on period
3. Set pickup date and return date
4. Configure rental pricing (hour/day/week/month)
5. Confirm quotation → creates rental order

### Contract Handling
1. On rental order confirmation, stock pickings are created:
   - **Delivery picking**: For rental product pickup
   - Scheduled automatically based on `pickup_date`
2. Track asset status throughout rental period
3. On return date, return picking created

### Return Process
1. Go to **Rental → Returns**
2. Open return picking for the rental order
3. Verify returned items (quantities, condition)
4. Validate picking — rental order completed
5. Generate final invoice for any overages/damages

---

## Related Modules

| Module | Purpose |
|--------|---------|
| [Modules/Sale](Modules/Sale.md) | Rental order base (sale order extension) |
| [Modules/Stock](Modules/Stock.md) | Rental inventory and pickings |
| [Modules/Fleet](Modules/Fleet.md) | Vehicle rental asset tracking |

---

*Source module: `~/odoo/odoo19/odoo/addons/rental/`*
