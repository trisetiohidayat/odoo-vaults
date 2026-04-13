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
> **Upgrade Status:** [Documentation/Upgrade-Plan/CHECKPOINT-master](documentation/upgrade-plan/checkpoint-master.md) — 76/80 tasks (95%)

---

## Quick Navigation

### Core Framework
- [Core/BaseModel](core/basemodel.md) — ORM foundation
- [Core/Fields](core/fields.md) — Field types
- [Core/API](core/api.md) — Decorators & method chains
- [Core/HTTP Controller](core/http-controller.md) — Web controllers
- [Core/Exceptions](core/exceptions.md) — Error handling

### Business Modules
- [Modules/Sale](modules/sale.md) — Sales
- [Modules/Purchase](modules/purchase.md) — Purchasing
- [Modules/Stock](modules/stock.md) — Inventory
- [Modules/Account](modules/account.md) — Accounting
- [Modules/CRM](modules/crm.md) — CRM
- [Modules/MRP](modules/mrp.md) — Manufacturing
- [Modules/Product](modules/product.md) — Products
- [Modules/HR](modules/hr.md) — Human Resources
- [Modules/Project](modules/project.md) — Project Management
- [Modules/POS](modules/pos.md) — Point of Sale
- [Modules/Helpdesk](modules/helpdesk.md) — Helpdesk
- [Modules/res.partner](modules/res.partner.md) — Partners

---

## Technical Flows (Method Chains)

> *Level 1 — AI-Optimized: Full method call sequences, branching logic, cross-module triggers*

### HR Flows
- [Flows/HR/employee-creation-flow](flows/hr/employee-creation-flow.md) — Employee creation with hr.version
- [Flows/HR/employee-archival-flow](flows/hr/employee-archival-flow.md) — Archive/unarchive with subordinates
- [Flows/HR/leave-request-flow](flows/hr/leave-request-flow.md) — Leave request lifecycle
- [Flows/HR/attendance-checkin-flow](flows/hr/attendance-checkin-flow.md) — Attendance check-in/outs
- [Flows/HR/contract-lifecycle-flow](flows/hr/contract-lifecycle-flow.md) — Contract create/renew/terminate

### Sale Flows
- [Flows/Sale/quotation-to-sale-order-flow](flows/sale/quotation-to-sale-order-flow.md) — Quote to confirmed order
- [Flows/Sale/sale-to-delivery-flow](flows/sale/sale-to-delivery-flow.md) — SO to picking
- [Flows/Sale/sale-to-invoice-flow](flows/sale/sale-to-invoice-flow.md) — SO to invoice

### Stock Flows
- [Flows/Stock/receipt-flow](flows/stock/receipt-flow.md) — Incoming receipt
- [Flows/Stock/delivery-flow](flows/stock/delivery-flow.md) — Outgoing delivery
- [Flows/Stock/internal-transfer-flow](flows/stock/internal-transfer-flow.md) — Multi-step internal transfer
- [Flows/Stock/picking-action-flow](flows/stock/picking-action-flow.md) — Generic picking lifecycle
- [Flows/Stock/quality-check-flow](flows/stock/quality-check-flow.md) — Quality check from picking
- [Flows/Stock/stock-valuation-flow](flows/stock/stock-valuation-flow.md) — Real-time valuation layers

### Purchase Flows
- [Flows/Purchase/purchase-order-creation-flow](flows/purchase/purchase-order-creation-flow.md) — RFQ to PO
- [Flows/Purchase/purchase-order-receipt-flow](flows/purchase/purchase-order-receipt-flow.md) — PO receipt
- [Flows/Purchase/purchase-to-bill-flow](flows/purchase/purchase-to-bill-flow.md) — PO to vendor bill
- [Flows/Purchase/purchase-withholding-flow](flows/purchase/purchase-withholding-flow.md) — Vendor bill with PPh withholding

### Account Flows
- [Flows/Account/invoice-creation-flow](flows/account/invoice-creation-flow.md) — Draft invoice creation
- [Flows/Account/invoice-post-flow](flows/account/invoice-post-flow.md) — Invoice posting
- [Flows/Account/payment-flow](flows/account/payment-flow.md) — Payment registration
- [Flows/Account/edi-invoice-flow](flows/account/edi-invoice-flow.md) — Peppol EDI import/export

### CRM Flows
- [Flows/CRM/lead-creation-flow](flows/crm/lead-creation-flow.md) — Lead from multiple sources
- [Flows/CRM/lead-conversion-to-opportunity-flow](flows/crm/lead-conversion-to-opportunity-flow.md) — Lead to opportunity
- [Flows/CRM/opportunity-win-flow](flows/crm/opportunity-win-flow.md) — Opportunity win/lost
- [Flows/CRM/lead-assignment-flow](flows/crm/lead-assignment-flow.md) — Round-robin lead assignment

### MRP Flows
- [Flows/MRP/bom-to-production-flow](flows/mrp/bom-to-production-flow.md) — BOM to manufacturing order
- [Flows/MRP/production-order-flow](flows/mrp/production-order-flow.md) — Production order execution
- [Flows/MRP/workorder-execution-flow](flows/mrp/workorder-execution-flow.md) — Workorder with quality check

### Project Flows
- [Flows/Project/project-creation-flow](flows/project/project-creation-flow.md) — Project creation with analytics
- [Flows/Project/task-lifecycle-flow](flows/project/task-lifecycle-flow.md) — Task create to done

### POS Flows
- [Flows/POS/pos-session-flow](flows/pos/pos-session-flow.md) — Session open/close with reconciliation
- [Flows/POS/pos-order-to-invoice-flow](flows/pos/pos-order-to-invoice-flow.md) — POS order to invoice

### Product Flows
- [Flows/Product/product-creation-flow](flows/product/product-creation-flow.md) — Product creation with variants
- [Flows/Product/pricelist-computation-flow](flows/product/pricelist-computation-flow.md) — Pricelist rule application

### Helpdesk Flows
- [Flows/Helpdesk/ticket-creation-flow](flows/helpdesk/ticket-creation-flow.md) — Ticket creation with SLA
- [Flows/Helpdesk/ticket-resolution-flow](flows/helpdesk/ticket-resolution-flow.md) — Ticket solve/close/rating

### Base/Utility Flows
- [Flows/Base/resource-attendance-flow](flows/base/resource-attendance-flow.md) — Calendar-based attendance
- [Flows/Base/mail-notification-flow](flows/base/mail-notification-flow.md) — message_post to email delivery

### Website Flows
- [Flows/Website/website-sale-flow](flows/website/website-sale-flow.md) — E-commerce cart to confirmation

### Cross-Module Flows
- [Flows/Cross-Module/sale-stock-account-flow](flows/cross-module/sale-stock-account-flow.md) — Sale → Delivery → Invoice → Payment
- [Flows/Cross-Module/purchase-stock-account-flow](flows/cross-module/purchase-stock-account-flow.md) — PO → Receipt → Bill → Payment
- [Flows/Cross-Module/employee-projects-timesheet-flow](flows/cross-module/employee-projects-timesheet-flow.md) — Employee → Project → Timesheet

---

## Business Guides (Walkthroughs)

> *Level 2 — Human-Optimized: Step-by-step configuration and process guides*

### HR Guides
- [Business/HR/quickstart-employee-setup](business/hr/quickstart-employee-setup.md) — Create employee + assign user
- [Business/HR/leave-management-guide](business/hr/leave-management-guide.md) — Leave types, allocation, approval

### Sale Guide
- [Business/Sale/sales-process-guide](business/sale/sales-process-guide.md) — Full quote-to-cash walkthrough

### Stock Guide
- [Business/Stock/warehouse-setup-guide](business/stock/warehouse-setup-guide.md) — Warehouse, locations, routes

### Purchase Guide
- [Business/Purchase/vendor-management-guide](business/purchase/vendor-management-guide.md) — Vendor setup and PO workflow

### Account Guide
- [Business/Account/chart-of-accounts-guide](business/account/chart-of-accounts-guide.md) — Chart of accounts loading
- [Business/Account/l10n-id-tax-guide](business/account/l10n-id-tax-guide.md) — Indonesian PPN & PPh taxes

### Product Guide
- [Business/Product/product-master-data-guide](business/product/product-master-data-guide.md) — Storable, service, kit products

### Project Guide
- [Business/Project/project-management-guide](business/project/project-management-guide.md) — Project + tasks + time tracking

### POS Guide
- [Business/POS/pos-configuration-guide](business/pos/pos-configuration-guide.md) — Session and payment configuration

### Helpdesk Guide
- [Business/Helpdesk/helpdesk-configuration-guide](business/helpdesk/helpdesk-configuration-guide.md) — Teams, stages, SLA policies

### Website Guide
- [Business/Website/ecommerce-configuration-guide](business/website/ecommerce-configuration-guide.md) — Payment + shipping + variants

### Dashboard
- [Business/Dashboard/installed-modules-dashboard](business/dashboard/installed-modules-dashboard.md) — Entry point for all modules

---

## Patterns & Development
- [Patterns/Inheritance Patterns](patterns/inheritance-patterns.md) — _inherit vs _inherits vs mixin
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — State machine + branching decision trees
- [Patterns/Security Patterns](patterns/security-patterns.md) — ACL CSV, ir.rule, field groups
- [Tools/Modules Inventory](tools/modules-inventory.md) — 304 modules catalog
- [Tools/ORM Operations](tools/orm-operations.md) — search(), browse(), create(), write(), domain operators
- [Snippets/Model Snippets](snippets/model-snippets.md) — Copy-paste code templates
- [Snippets/Controller Snippets](snippets/controller-snippets.md) — HTTP route handlers
- [Snippets/method-chain-example](snippets/method-chain-example.md) — Method chain notation reference

---

## New in Odoo 19
- [New Features/What's New](new-features/what's-new.md) — What's new in Odoo 19
- [New Features/API Changes](new-features/api-changes.md) — API changes from v18
- [New Features/New Modules](new-features/new-modules.md) — New modules in v19

---

## Localization
- [Modules/l10n_id](modules/l10n_id.md) — Indonesia (PPN, PPh 21/22/23/26, e-Faktur)
- [Modules/l10n_de](modules/l10n_de.md) — Germany (MwSt 19%, Reverse Charge)
- [Modules/l10n_us](modules/l10n_us.md) — USA (Sales tax, 1099)
- [Modules/l10n_fr](modules/l10n_fr.md) — France (TVA 20%/10%/5.5%, FEC)

---

## Missing Module Entries
- [Modules/iot](modules/iot.md) — IoT box and device management
- [Modules/studio](modules/studio.md) — Studio app builder
- [Modules/knowledge](modules/knowledge.md) — Internal knowledge base
- [Modules/rental](modules/rental.md) — Equipment rental / lease

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

- [Documentation/Upgrade-Plan/CHECKPOINT-master](documentation/upgrade-plan/checkpoint-master.md) — Master tracker
- [Documentation/Upgrade-Plan/00-LEVELING-UP-DESIGN](documentation/upgrade-plan/00-leveling-up-design.md) — Upgrade design document

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
