---
type: phase-checkpoint
phase: 4
title: "Phase 4 — Tier 3: Supporting Modules"
status: pending
estimated_tasks: 16
depends_on: Phase 3
created: 2026-04-06
---

# Phase 4 — Tier 3: Supporting Modules

**Goal:** Complete Flows and guides for supporting business modules.

---

## Product Module

### Task Prod-1: Create Product Creation Flow
**File:** `Flows/Product/product-creation-flow.md`
**Content:**
- [ ] `product.template` creation
- [ ] `product.product` variants auto-generated (if configurable)
- [ ] `_onchange_product_template_id()` cascade
- [ ] Seller prices populated from `product.supplierinfo`
- [ ] Route assignment
- [ ] Pricelist item auto-created (if template)
- [ ] Error scenarios

### Task Prod-2: Create Product Pricelist Flow
**File:** `Flows/Product/pricelist-computation-flow.md`
**Content:**
- [ ] `product.pricelist.item` rule evaluation order
- [ ] `_compute_price()` method chain
- [ ] Price computation: base price → discount → surcharge
- [ ] Multi-currency handling
- [ ] B2B vs B2C pricelist differences
- [ ] Error scenarios

### Task Prod-3: Create Product Business Guide
**File:** `Business/Product/product-master-data-guide.md`
**Content:**
- [ ] Product category hierarchy
- [ ] Product vs template vs variant
- [ ] Route configuration
- [ ] Pricelist setup
- [ ] Common pitfalls

---

## Project Module

### Task Proj-1: Create Project Creation Flow
**File:** `Flows/Project/project-creation-flow.md`
**Content:**
- [ ] Project creation from template or blank
- [ ] Stage initialization
- [ ] Task template auto-generation (if template)
- [ ] Team / member assignment
- [ ] Timesheet admin configuration
- [ ] Error scenarios

### Task Proj-2: Create Task Lifecycle Flow
**File:** `Flows/Project/task-lifecycle-flow.md`
**Content:**
- [ ] Task creation from sale order line (cross-module)
- [ ] Stage progression
- [ ] Timesheet logging
- [ ] Subtask management
- [ ] Project milestone tracking
- [ ] Task completion → revenue recognition
- [ ] Error scenarios

### Task Proj-3: Create Project Business Guide
**File:** `Business/Project/project-management-guide.md`
**Content:**
- [ ] Project setup walkthrough
- [ ] Task creation and assignment
- [ ] Timesheet logging guide
- [ ] Project billing (time & material)
- [ ] Common pitfalls

---

## POS Module

### Task POS-1: Create POS Session Flow
**File:** `Flows/POS/pos-session-flow.md`
**Content:**
- [ ] POS session opening → cash control
- [ ] Order creation → `pos.order`
- [ ] Payment line → `pos.payment`
- [ ] `action_pos_order_paid()` → order confirmed
- [ ] Session closing → cash reconciliation
- [ ] End-of-day reporting
- [ ] Error scenarios

### Task POS-2: Create POS Order to Invoice Flow
**File:** `Flows/POS/pos-order-to-invoice-flow.md`
**Content:**
- [ ] POS order → invoice creation
- [ ] Customer selection → fiscal position applied
- [ ] Multi-payment handling
- [ ] Cash rounding
- [ ] Cross-module: POS ↔ Account

### Task POS-3: Create POS Business Guide
**File:** `Business/POS/pos-configuration-guide.md`
**Content:**
- [ ] POS configuration walkthrough
- [ ] Payment method setup
- [ ] Product configuration for POS
- [ ] Daily closing procedure
- [ ] Common pitfalls

---

## Quality Module

### Task Qual-1: Create Quality Check Flow
**File:** `Flows/Quality/quality-check-flow.md`
**Content:**
- [ ] Quality check triggered from stock move
- [ ] Check types: pass/fail, measure, picture
- [ ] `quality.alert` creation on failure
- [ ] Block/unblock production based on result
- [ ] Corrective action tracking
- [ ] Cross-module: Quality ↔ Stock ↔ MRP
- [ ] Error scenarios

### Task Qual-2: Enhance Quality Module Documentation
**File:** `Modules/quality.md` (create if not exists or enhance)
**Content:**
- [ ] Quick Access block
- [ ] Quality check model documentation
- [ ] Quality alert model documentation
- [ ] Flow link to quality-check-flow

---

## Helpdesk Module

### Task Help-1: Create Ticket Creation Flow
**File:** `Flows/Helpdesk/ticket-creation-flow.md`
**Content:**
- [ ] Ticket creation: portal, email, website
- [ ] Email alias → ticket auto-creation
- [ ] Team assignment based on category
- [ ] SLA policy evaluation
- [ ] Customer notification
- [ ] Error scenarios

### Task Help-2: Create Ticket Resolution Flow
**File:** `Flows/Helpdesk/ticket-resolution-flow.md`
**Content:**
- [ ] Assignment to agent
- [ ] Stage progression
- [ ] Time tracking
- [ ] Solution recorded
- [ ] Customer feedback / rating
- [ ] Knowledge base article suggestion
- [ ] Cross-module: Helpdesk ↔ Project (if escalates)
- [ ] Error scenarios

### Task Help-3: Create Helpdesk Business Guide
**File:** `Business/Helpdesk/helpdesk-configuration-guide.md`
**Content:**
- [ ] Team and member setup
- [ ] SLA configuration
- [ ] Email alias setup
- [ ] Ticket workflow stages
- [ ] Common pitfalls

---

## Phase 4 Completion Criteria

All 16 tasks completed AND:
- [ ] All Tier 3 module files updated with Quick Access blocks
- [ ] Wikilinks verified
- [ ] Phase 4 checkpoint updated

**Estimated effort:** 3–4 sessions

**Next phase:** [Documentation/Upgrade-Plan/05-Task-List-Phase-5](odoo-19/Documentation/Upgrade-Plan/05-Task-List-Phase-5.md)
