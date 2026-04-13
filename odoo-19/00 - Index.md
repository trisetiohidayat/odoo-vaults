---
type: index
version: 19.0
odoo_release: 19.0 FINAL
source_path: /Users/tri-mac/odoo/odoo19/odoo/addons/
source_extracted: 2026-02-14 15:10:14 WIB (UTC+7)
estimated_git_commit: ed839c221479b306f9f600a29491a60a096198f3
github_repo: https://github.com/odoo/odoo
github_branch: 19.0
commit_date: 2026-02-14 09:30:58 UTC (16:30:58 WIB)
modules_documented: 610
modules_total: 608
documentation_date: 2026-04-07
tags: [odoo, odoo19, index]
created: 2026-04-06
updated: 2026-04-07
---

# Odoo 19 Knowledge Graph

## Overview

Knowledge graph untuk codebase **Odoo 19** — memetakan struktur, relasi, dan arsitektur modular. Upgrade vault ke **Master Knowledge Base** menyediakan Level 1 (AI Reasoning) dan Level 2 (Developer + Business Consultant) documentation untuk semua critical module.

> **Location:** `/Users/tri-mac/odoo/odoo19/`
> **Total Modules:** 610 documented / 608 in addons (100% coverage)
> **Version:** 19.0 FINAL
> **Documentation Date:** 2026-04-07
> **Upgrade Status:** [Documentation/Upgrade-Plan/CHECKPOINT-master](CHECKPOINT-master.md) — 76/80 tasks (95%)

---

## Quick Navigation

### Core Framework
- [Core/BaseModel](BaseModel.md) — ORM foundation
- [Core/Fields](Fields.md) — Field types
- [Core/API](API.md) — Decorators & method chains
- [Core/HTTP Controller](HTTP Controller.md) — Web controllers
- [Core/Exceptions](Exceptions.md) — Error handling

### Business Modules
- [Modules/Sale](Sale.md) — Sales
- [Modules/Purchase](Purchase.md) — Purchasing
- [Modules/Stock](Stock.md) — Inventory
- [Modules/Account](Account.md) — Accounting
- [Modules/CRM](CRM.md) — CRM
- [Modules/MRP](MRP.md) — Manufacturing
- [Modules/Product](Product.md) — Products
- [Modules/HR](HR.md) — Human Resources
- [Modules/Project](Project.md) — Project Management
- [Modules/POS](pos.md) — Point of Sale
- [Modules/Helpdesk](helpdesk.md) — Helpdesk
- [Modules/res.partner](res.partner.md) — Partners

---

## Technical Flows (Method Chains)

> *Level 1 — AI-Optimized: Full method call sequences, branching logic, cross-module triggers*

### HR Flows
- [Flows/HR/employee-creation-flow](employee-creation-flow.md) — Employee creation with hr.version
- [Flows/HR/employee-archival-flow](employee-archival-flow.md) — Archive/unarchive with subordinates
- [Flows/HR/leave-request-flow](leave-request-flow.md) — Leave request lifecycle
- [Flows/HR/attendance-checkin-flow](attendance-checkin-flow.md) — Attendance check-in/outs
- [Flows/HR/contract-lifecycle-flow](contract-lifecycle-flow.md) — Contract create/renew/terminate

### Sale Flows
- [Flows/Sale/quotation-to-sale-order-flow](quotation-to-sale-order-flow.md) — Quote to confirmed order
- [Flows/Sale/sale-to-delivery-flow](sale-to-delivery-flow.md) — SO to picking
- [Flows/Sale/sale-to-invoice-flow](sale-to-invoice-flow.md) — SO to invoice

### Stock Flows
- [Flows/Stock/receipt-flow](receipt-flow.md) — Incoming receipt
- [Flows/Stock/delivery-flow](delivery-flow.md) — Outgoing delivery
- [Flows/Stock/internal-transfer-flow](internal-transfer-flow.md) — Multi-step internal transfer
- [Flows/Stock/picking-action-flow](picking-action-flow.md) — Generic picking lifecycle
- [Flows/Stock/quality-check-flow](quality-check-flow.md) — Quality check from picking
- [Flows/Stock/stock-valuation-flow](stock-valuation-flow.md) — Real-time valuation layers

### Purchase Flows
- [Flows/Purchase/purchase-order-creation-flow](purchase-order-creation-flow.md) — RFQ to PO
- [Flows/Purchase/purchase-order-receipt-flow](purchase-order-receipt-flow.md) — PO receipt
- [Flows/Purchase/purchase-to-bill-flow](purchase-to-bill-flow.md) — PO to vendor bill
- [Flows/Purchase/purchase-withholding-flow](purchase-withholding-flow.md) — Vendor bill with PPh withholding

### Account Flows
- [Flows/Account/invoice-creation-flow](invoice-creation-flow.md) — Draft invoice creation
- [Flows/Account/invoice-post-flow](invoice-post-flow.md) — Invoice posting
- [Flows/Account/payment-flow](payment-flow.md) — Payment registration
- [Flows/Account/edi-invoice-flow](edi-invoice-flow.md) — Peppol EDI import/export

### CRM Flows
- [Flows/CRM/lead-creation-flow](lead-creation-flow.md) — Lead from multiple sources
- [Flows/CRM/lead-conversion-to-opportunity-flow](lead-conversion-to-opportunity-flow.md) — Lead to opportunity
- [Flows/CRM/opportunity-win-flow](opportunity-win-flow.md) — Opportunity win/lost
- [Flows/CRM/lead-assignment-flow](lead-assignment-flow.md) — Round-robin lead assignment

### MRP Flows
- [Flows/MRP/bom-to-production-flow](bom-to-production-flow.md) — BOM to manufacturing order
- [Flows/MRP/production-order-flow](production-order-flow.md) — Production order execution
- [Flows/MRP/workorder-execution-flow](workorder-execution-flow.md) — Workorder with quality check

### Project Flows
- [Flows/Project/project-creation-flow](project-creation-flow.md) — Project creation with analytics
- [Flows/Project/task-lifecycle-flow](task-lifecycle-flow.md) — Task create to done

### POS Flows
- [Flows/POS/pos-session-flow](pos-session-flow.md) — Session open/close with reconciliation
- [Flows/POS/pos-order-to-invoice-flow](pos-order-to-invoice-flow.md) — POS order to invoice

### Product Flows
- [Flows/Product/product-creation-flow](product-creation-flow.md) — Product creation with variants
- [Flows/Product/pricelist-computation-flow](pricelist-computation-flow.md) — Pricelist rule application

### Helpdesk Flows
- [Flows/Helpdesk/ticket-creation-flow](ticket-creation-flow.md) — Ticket creation with SLA
- [Flows/Helpdesk/ticket-resolution-flow](ticket-resolution-flow.md) — Ticket solve/close/rating

### Base/Utility Flows
- [Flows/Base/resource-attendance-flow](resource-attendance-flow.md) — Calendar-based attendance
- [Flows/Base/mail-notification-flow](mail-notification-flow.md) — message_post to email delivery

### Website Flows
- [Flows/Website/website-sale-flow](website-sale-flow.md) — E-commerce cart to confirmation

### Cross-Module Flows
- [Flows/Cross-Module/sale-stock-account-flow](sale-stock-account-flow.md) — Sale → Delivery → Invoice → Payment
- [Flows/Cross-Module/purchase-stock-account-flow](purchase-stock-account-flow.md) — PO → Receipt → Bill → Payment
- [Flows/Cross-Module/employee-projects-timesheet-flow](employee-projects-timesheet-flow.md) — Employee → Project → Timesheet

---

## Business Guides (Walkthroughs)

> *Level 2 — Human-Optimized: Step-by-step configuration and process guides*

### HR Guides
- [Business/HR/quickstart-employee-setup](quickstart-employee-setup.md) — Create employee + assign user
- [Business/HR/leave-management-guide](leave-management-guide.md) — Leave types, allocation, approval

### Sale Guide
- [Business/Sale/sales-process-guide](sales-process-guide.md) — Full quote-to-cash walkthrough

### Stock Guide
- [Business/Stock/warehouse-setup-guide](warehouse-setup-guide.md) — Warehouse, locations, routes

### Purchase Guide
- [Business/Purchase/vendor-management-guide](vendor-management-guide.md) — Vendor setup and PO workflow

### Account Guide
- [Business/Account/chart-of-accounts-guide](chart-of-accounts-guide.md) — Chart of accounts loading
- [Business/Account/l10n-id-tax-guide](l10n-id-tax-guide.md) — Indonesian PPN & PPh taxes

### Product Guide
- [Business/Product/product-master-data-guide](product-master-data-guide.md) — Storable, service, kit products

### Project Guide
- [Business/Project/project-management-guide](project-management-guide.md) — Project + tasks + time tracking

### POS Guide
- [Business/POS/pos-configuration-guide](pos-configuration-guide.md) — Session and payment configuration

### Helpdesk Guide
- [Business/Helpdesk/helpdesk-configuration-guide](helpdesk-configuration-guide.md) — Teams, stages, SLA policies

### Website Guide
- [Business/Website/ecommerce-configuration-guide](ecommerce-configuration-guide.md) — Payment + shipping + variants

### Dashboard
- [Business/Dashboard/installed-modules-dashboard](installed-modules-dashboard.md) — Entry point for all modules

---

## Patterns & Development
- [Patterns/Inheritance Patterns](Inheritance Patterns.md) — _inherit vs _inherits vs mixin
- [Patterns/Workflow Patterns](Workflow Patterns.md) — State machine + branching decision trees
- [Patterns/Security Patterns](Security Patterns.md) — ACL CSV, ir.rule, field groups
- [Tools/Modules Inventory](Modules Inventory.md) — 304 modules catalog
- [Tools/ORM Operations](ORM Operations.md) — search(), browse(), create(), write(), domain operators
- [Snippets/Model Snippets](Model Snippets.md) — Copy-paste code templates
- [Snippets/Controller Snippets](Controller Snippets.md) — HTTP route handlers
- [Snippets/method-chain-example](method-chain-example.md) — Method chain notation reference

---

## New in Odoo 19
- [New Features/What's New](What's New.md) — What's new in Odoo 19
- [New Features/API Changes](API Changes.md) — API changes from v18
- [New Features/New Modules](New Modules.md) — New modules in v19

---

## Localization
- [Modules/l10n_id](l10n_id.md) — Indonesia (PPN, PPh 21/22/23/26, e-Faktur)
- [Modules/l10n_de](l10n_de.md) — Germany (MwSt 19%, Reverse Charge)
- [Modules/l10n_us](l10n_us.md) — USA (Sales tax, 1099)
- [Modules/l10n_fr](l10n_fr.md) — France (TVA 20%/10%/5.5%, FEC)

---

## Missing Module Entries
- [Modules/iot](iot.md) — IoT box and device management
- [Modules/studio](studio.md) — Studio app builder
- [Modules/knowledge](knowledge.md) — Internal knowledge base
- [Modules/rental](rental.md) — Equipment rental / lease

---

## Upgrade Progress

| Phase | Status | Tasks |
|-------|--------|-------|
| Phase 1 Foundation | ✅ Complete | 9/9 |
| Phase 2 Tier 1 (Sale/Stock/PO/Acct/HR) | ✅ Complete | 27/27 |
| Phase 3 Tier 2 (CRM/MRP/HR2/Cross) | ✅ 86% | 12/14 |
| Phase 4 Tier 3 (Prod/Proj/POS/Qual/Help) | ✅ Complete | 14/14 |
| Phase 5 Enhancements | ✅ 88% | 14/16 |
| **TOTAL** | **✅ 95%** | **76/80** |

- [Documentation/Upgrade-Plan/CHECKPOINT-master](CHECKPOINT-master.md) — Master tracker
- [Documentation/Upgrade-Plan/00-LEVELING-UP-DESIGN](00-LEVELING-UP-DESIGN.md) — Upgrade design document

---

## Tags

#odoo #odoo19 #orm #web #modules
#sale #purchase #stock #account #crm #mrp
#ai-reasoning #method-chain #level1 #level2

---

## Graph Connections

```mermaid
graph LR
    BM[BaseModel] --> F[Fields]
    BM --> API[API]
    BM --> HTTP[HTTP Controller]
    F --> API
    API --> HTTP
    S[Sale] --> ST[Stock]
    S --> A[Account]
    ST --> A
    P[Purchase] --> ST
    MRP --> ST
    HR --> Proj[Project]
    Proj --> TS[Timesheet]
    TS --> A
    CRM --> S
    S --> Inv[Invoice]
    Inv --> A
```
