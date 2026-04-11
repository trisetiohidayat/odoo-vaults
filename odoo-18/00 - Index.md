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
- [[Core/BaseModel]] — ORM foundation
- [[Core/Fields]] — Field types
- [[Core/API]] — Decorators & method chains
- [[Core/HTTP Controller]] — Web controllers
- [[Core/Exceptions]] — Error handling

### Business Modules
- [[Modules/Sale]] — Sales
- [[Modules/Purchase]] — Purchasing
- [[Modules/Stock]] — Inventory
- [[Modules/Account]] — Accounting
- [[Modules/CRM]] — CRM
- [[Modules/MRP]] — Manufacturing
- [[Modules/Product]] — Products
- [[Modules/HR]] — Human Resources
- [[Modules/Project]] — Project Management
- [[Modules/POS]] — Point of Sale
- [[Modules/Helpdesk]] — Helpdesk
- [[Modules/res.partner]] — Partners

---

## Patterns & Development
- [[Patterns/Inheritance Patterns]] — _inherit vs _inherits vs mixin
- [[Patterns/Workflow Patterns]] — State machine + branching decision trees
- [[Patterns/Security Patterns]] — ACL CSV, ir.rule, field groups
- [[Tools/Modules Inventory]] — 304 modules catalog
- [[Tools/ORM Operations]] — search(), browse(), create(), write(), domain operators
- [[Snippets/Model Snippets]] — Copy-paste code templates
- [[Snippets/Controller Snippets]] — HTTP route handlers
- [[Snippets/method-chain-example]] — Method chain notation reference

---

## New in Odoo 18
- [[New Features/What's New]] — What's new in Odoo 18
- [[New Features/API Changes]] — API changes from v17
- [[New Features/New Modules]] — New modules in v18

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

- [[Documentation/Checkpoints/]] — Progress tracking
- [[Research-Log/backlog]] — Pending gaps

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
