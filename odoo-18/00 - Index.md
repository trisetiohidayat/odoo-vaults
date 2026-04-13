---
type: index
version: 18.0
odoo_release: 18.0 FINAL
source_path: /Users/tri-mac/odoo/odoo18/odoo/addons/
source_extracted: 2026-04-11
modules_documented: 64
modules_total: 606
documentation_date: 2026-04-11
tags: [odoo, odoo18, index]
created: 2026-04-11
updated: 2026-04-11
---

# Odoo 18 Knowledge Graph

## Overview

Knowledge graph untuk codebase **Odoo 18** — memetakan struktur, relasi, dan arsitektur modular. Vault ini menyediakan Level 1 (AI Reasoning) dan Level 2 (Developer + Business Consultant) documentation untuk semua module.

> **Location:** `/Users/tri-mac/odoo/odoo18/odoo/`
> **Total Modules:** 606 in addons (43 core + 563 extended)
> **Version:** 18.0 FINAL
> **Documentation Status:** In Progress — 37/606 documented (Phase 1-3 ✅, Phase 4 starting)

---

## Quick Navigation

### Core Framework
- [Core/BaseModel](BaseModel.md) — ORM foundation
- [Core/Fields](Fields.md) — Field types
- [Core/API](API.md) — Decorators & method chains
- [Core/HTTP Controller](HTTP Controller.md) — Web controllers
- [Core/Exceptions](Exceptions.md) — Error handling

### Business Modules
- [Modules/Sale](sale.md) — Sales
- [Modules/Purchase](purchase.md) — Purchasing
- [Modules/Stock](stock.md) — Inventory
- [Modules/Account](account.md) — Accounting
- [Modules/CRM](CRM.md) — CRM
- [Modules/MRP](mrp.md) — Manufacturing
- [Modules/Product](product.md) — Products
- [Modules/HR](hr.md) — Human Resources
- [Modules/Project](project.md) — Project Management
- [Modules/POS](Modules/pos.md) — Point of Sale
- [Modules/Helpdesk](helpdesk.md) — Helpdesk
- [Modules/res.partner](Modules/res.partner.md) — Partners

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

## New in Odoo 18
- [New Features/What's New](What's New.md) — What's new in Odoo 18
- [New Features/API Changes](API Changes.md) — API changes from v17
- [New Features/New Modules](New Modules.md) — New modules in v18

---

## Documentation Progress

| Phase | Status | Tasks |
|-------|--------|-------|
| Phase 1 Foundation | ✅ Complete | 6/6 |
| Phase 2 Core Business | ✅ Complete | 12/12 |
| Phase 3 Extended Business | ✅ Complete | 15/15 |
| Phase 4 Website & POS | ✅ Complete | 18/18 |
| Phase 5 Integrations | ✅ Complete | 16/16 |
| Phase 6 Localization | Pending | 0/150+ |
| **TOTAL** | **64/606** | **10.5%** |

- [Documentation/Checkpoints/](Documentation/Checkpoints/.md) — Progress tracking
- [Research-Log/backlog](backlog.md) — Pending gaps

---

## Tags

#odoo #odoo18 #orm #web #modules
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
