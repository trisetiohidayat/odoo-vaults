---
type: guide
title: "Warehouse Setup Guide"
module: stock
audience: business-consultant, warehouse-manager
level: 2
prerequisites:
  - warehouse_created
  - locations_configured
  - routes_defined
  - picking_types_setup
estimated_time: "~20 minutes"
related_flows:
  - "[Flows/Stock/receipt-flow](Flows/Stock/receipt-flow.md)"
  - "[Flows/Stock/delivery-flow](Flows/Stock/delivery-flow.md)"
  - "[Flows/Stock/internal-transfer-flow](Flows/Stock/internal-transfer-flow.md)"
source_module: stock
created: 2026-04-06
version: "1.0"
---

# Warehouse Setup Guide

> **Quick Summary:** Configure warehouse locations, routes, and picking types for inventory management in Odoo.

**Actor:** Warehouse Manager / Inventory Manager
**Module:** Stock
**Difficulty:** ⭐⭐ Medium

---

## Prerequisites Checklist

- [ ] **Warehouses created** — Inventory → Configuration → Warehouses
- [ ] **Locations configured** — Inventory → Configuration → Locations
- [ ] **Routes defined** — Inventory → Configuration → Routes
- [ ] **Picking Types set up** — Inventory → Configuration → Picking Types
- [ ] **Product Categories** — Inventory → Configuration → Product Categories

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Stock/receipt-flow](Flows/Stock/receipt-flow.md) | Receipt process |
| 🔀 Technical Flow | [Flows/Stock/delivery-flow](Flows/Stock/delivery-flow.md) | Delivery process |
| 📖 Module Reference | [Modules/Stock](Modules/Stock.md) | Complete model reference |

---

## Use Cases Covered

| # | Use Case | Difficulty |
|---|----------|-----------|
| 1 | Single-Warehouse Setup | ⭐ |
| 2 | Multi-Step Delivery (Pick → Pack → Ship) | ⭐⭐ |
| 3 | Multi-Warehouse with Transits | ⭐⭐⭐ |

---

## Use Case 1: Single-Warehouse Setup

### Scenario
A small company with one warehouse receiving and delivering goods directly.

### Steps

#### Step 1 — Create Warehouse

Go to: **Inventory → Configuration → Warehouses → Create**

| Field | Value | Notes |
|-------|-------|-------|
| **Warehouse Name** | Main Warehouse | |
| **Short Name** | WH/M | Used in sequences |
| **Address** | Company address | |
| **Manage Lots/Serial Numbers** | ✅ (if tracking) | For lot-tracked products |
| **Default Reserved Lot** | First lot | |
| **Receive in 1 Step** | ✅ | Goods received directly to stock |

> **⚡ System Trigger:** When warehouse is created, Odoo automatically creates default locations: Physical Locations (WH/Stock), Virtual Locations (WH/Output, WH/Pack), Vendor Location (Virtual/Vendors), Customer Location (Virtual/Customers).

#### Step 2 — Configure Locations

Go to: **Inventory → Configuration → Locations**

Odoo creates these locations by default:

| Location | Type | Purpose |
|---------|------|---------|
| Physical Locations/Stock | internal | Main storage |
| Physical Locations/Output | internal | Before shipping |
| Physical Locations/Pack | internal | Packing area |
| Virtual/Loss | virtual | Inventory adjustments |
| Virtual/Vendors | vendor | Incoming receipts |
| Virtual/Customers | customer | Outgoing deliveries |

#### Step 3 — Set Up Picking Types

Go to: **Inventory → Configuration → Picking Types**

Odoo creates these by default per warehouse:

| Picking Type | Operation Type | Route |
|-------------|---------------|-------|
| Receipts | Incoming | WH/Stock |
| Delivery Orders | Outgoing | WH/Stock |
| Internal Transfers | Internal | WH/Stock |

> **⚡ Side Effects:** Each picking type has a sequence for generating names (e.g., WH/IN/00001, WH/OUT/00001).

---

## Use Case 2: Multi-Step Delivery

### Scenario
Company wants pick → pack → ship process (3 steps).

### Steps

#### Step 1 — Enable Multi-Step Routes

Go to: **Inventory → Configuration → Settings**

Enable: **Multi-Step Routes**

> **⚡ System Trigger:** Enables route configuration at warehouse and product level.

#### Step 2 — Configure Warehouse Routes

Go to: **Inventory → Configuration → Warehouses** → Edit Warehouse

Set:
| Setting | Value |
|---------|-------|
| **Delivery Steps** | Pick, Pack & Ship |
| **Receipt Steps** | Receive in 2 Steps (Input + Stock) OR 1 Step |

#### Step 3 — Verify New Locations Created

Go to: **Inventory → Configuration → Locations**

New locations should be created:

| Location | Type |
|---------|------|
| WH/Input | internal |
| WH/Stock | internal |
| WH/Pack | internal |
| WH/Output | internal |
| WH/Picking | internal |

#### Step 4 — Verify Picking Types Updated

Go to: **Inventory → Configuration → Picking Types**

New picking types added:

| Picking Type | Sequence | Route |
|-------------|---------|-------|
| WH/Input | Input → Stock | WH/Input → WH/Stock |
| WH/Picking | WH → Picking | WH/Stock → WH/Picking |
| WH/Pack | Packing | WH/Packing |
| WH/Output | WH → Output | WH/Output → WH/Customers |
| Delivery Orders | → Customer | Uses WH/Output |

> **⚡ System Trigger:** Route "Pick + Ship" applied automatically. Sale order delivery creates: Picking → Pack → Output → Customer.

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Wrong warehouse selected on SO | Delivery orders created in wrong WH | Always check warehouse on sale order |
| 2 | Missing routes on product | No picking created on confirmation | Set routes on product form |
| 3 | Conflicting picking types | Duplicate pickings | Only one incoming picking type per warehouse |
| 4 | Location not internal | Cannot receive to location | Set location type = "Internal" for storage |
| 5 | Multi-step but no routes | Picking type not created | Verify after enabling multi-step |
| 6 | Wrong sequence prefix | Document numbers confusing | Set custom sequence prefix per picking type |

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|---------|
| Picking not created | No route on product or wrong WH | Check product routes and warehouse on SO |
| Products in wrong location | Wrong destination location | Set location_id on order line |
| Cannot validate picking | Products not available | Check availability in source location |
| Backorder not created | User declined backorder option | Always check "Create Backorder" at done |
| Quants not updating | Product not in tracked location | Check location type and product configuration |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Receipt Flow | [Flows/Stock/receipt-flow](Flows/Stock/receipt-flow.md) | Incoming receipt process |
| 🔀 Delivery Flow | [Flows/Stock/delivery-flow](Flows/Stock/delivery-flow.md) | Outgoing delivery process |
| 🔀 Picking Actions | [Flows/Stock/picking-action-flow](Flows/Stock/picking-action-flow.md) | confirm→assign→done |
| 📖 Module Reference | [Modules/Stock](Modules/Stock.md) | Complete model reference |
