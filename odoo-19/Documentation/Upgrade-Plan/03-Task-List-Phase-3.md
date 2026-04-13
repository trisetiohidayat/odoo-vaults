---
type: phase-checkpoint
phase: 3
title: "Phase 3 — Tier 2: Operational Modules"
status: pending
estimated_tasks: 22
depends_on: Phase 2
created: 2026-04-06
---

# Phase 3 — Tier 2: Operational Modules

**Goal:** Complete Flows and Business guides for operational modules (CRM, MRP, HR sub-modules).

---

## CRM Module

### Task CRM-1: Create Lead Creation Flow
**File:** `Flows/CRM/lead-creation-flow.md`
**Content:**
- [ ] Lead creation methods: manual, website form, email alias, import
- [ ] `_onchange_partner_id()` cascade
- [ ] `partner_id` creation from lead
- [ ] Stage assignment based on team
- [ ] Assignment rules (`crm.lead.assignment.rule`)
- [ ] UTM source/campaign tracking populated
- [ ] Error scenarios

### Task CRM-2: Create Lead Conversion Flow
**File:** `Flows/CRM/lead-conversion-to-opportunity-flow.md`
**Content:**
- [ ] `action_convert_opportunity()` method chain
- [ ] Partner assignment / creation
- [ ] Opportunity stage default
- [ ] Lead data preserved vs merged
- [ ] Sale order link created (if applicable)
- [ ] Activity planned post-conversion
- [ ] Error scenarios

### Task CRM-3: Create Opportunity Win Flow
**File:** `Flows/CRM/opportunity-win-flow.md`
**Content:**
- [ ] Stage → Won transition
- [ ] `mail.activity` completion
- [ ] Revenue recorded
- [ ] `crm.lead.scoring.frequency` updated (PLS)
- [ ] Cross-module: opportunity → sale order
- [ ] Won notification / celebration automation
- [ ] Error scenarios

### Task CRM-4: Create Sales Team Assignment Flow
**File:** `Flows/CRM/lead-assignment-flow.md`
**Content:**
- [ ] `crm.lead.assignment.rule` evaluation
- [ ] Round-robin vs workload-based
- [ ] Auto-assignment cron job chain
- [ ] Territory matching
- [ ] `action_assign()` method chain
- [ ] Assignment notification
- [ ] Error scenarios

### Task CRM-5: Enhance Modules/CRM.md — Add Flow Links
**File:** `Modules/CRM.md`
**Update:**
- [ ] Quick Access block
- [ ] Pipeline workflow section → link to relevant flows
- [ ] Method-to-flow mapping

---

## MRP Module

### Task MRP-1: Create BOM to Production Flow
**File:** `Flows/MRP/bom-to-production-flow.md`
**Content:**
- [ ] `mrp.bom` structure (product + components + operations)
- [ ] `mrp.production` creation from BOM
- [ ] Workorder generation based on routing
- [ ] `action_confirm()` → stock moves created for components
- [ ] `action_assign()` → material reservation
- [ ] Production readiness → `ready_to_produce` state
- [ ] Error scenarios

### Task MRP-2: Create Production Order Execution Flow
**File:** `Flows/MRP/production-order-flow.md`
**Content:**
- [ ] `action_build()` → production started
- [ ] Component consumption: `stock.move` done
- [ ] Workorder execution: `mrp.workorder` progression
- [ ] `action_finish()` → production done
- [ ] Finished product receipt: `stock.move` to finished location
- [ ] Byproduct creation
- [ ] Scrap handling
- [ ] Cross-module: MRP ↔ Stock

### Task MRP-3: Create Workorder Execution Flow
**File:** `Flows/MRP/workorder-execution-flow.md`
**Content:**
- [ ] Workorder start
- [ ] Time tracking (manual / automatic)
- [ ] Component consumption per operation
- [ ] Quality check trigger at operation
- [ ] Workorder completion
- [ ] Next operation started (if sequential)
- [ ] Cross-module: MRP ↔ Quality

### Task MRP-4: Enhance Modules/MRP.md — Add Flow Links
**File:** `Modules/MRP.md`
**Update:**
- [ ] Quick Access block
- [ ] Manufacturing steps → link to production-order-flow
- [ ] Workorder lifecycle → link to workorder-execution-flow

---

## HR Sub-Modules (hr_holidays, hr_attendance, hr_contract)

### Task HR2-1: Create Leave Request Flow
**File:** `Flows/HR/leave-request-flow.md`
**Content:**
- [ ] Leave request creation
- [ ] Validation: overlapping, insufficient balance
- [ ] Manager approval chain
- [ ] State transition: draft → confirm → approve / refuse
- [ ] Calendar event auto-created
- [ ] Accrual computation
- [ ] Error scenarios

### Task HR2-2: Create Attendance Record Flow
**File:** `Flows/HR/attendance-record-flow.md`
**Content:**
- [ ] Check-in via barcode, geolocation, kiosk
- [ ] Attendance record creation
- [ ] Late detection based on working hours
- [ ] Overtime computation
- [ ] Attendance regularization
- [ ] Error scenarios

### Task HR2-3: Create Contract Lifecycle Flow
**File:** `Flows/HR/contract-lifecycle-flow.md`
**Content:**
- [ ] Contract creation from template
- [ ] Contract start → version activation
- [ ] Contract end → version deactivation
- [ ] Contract renewal → new version
- [ ] Trial period management
- [ ] Wage adjustment
- [ ] Error scenarios

### Task HR2-4: Create HR Payroll Structure Guide
**File:** `Business/HR/payroll-structure-guide.md`
**Content:**
- [ ] Salary structure types
- [ ] Wage computation rules
- [ ] Contract type configuration
- [ ] Common pitfalls

### Task HR2-5: Enhance Modules/hr_holidays.md — Add Flow Links
**File:** `Modules/hr_holidays.md`
**Update:**
- [ ] Quick Access block
- [ ] Leave workflow → link to leave-request-flow

---

## Cross-Module Flows (Tier 2)

### Task CM-1: Create Employee → Project → Timesheet Flow
**File:** `Flows/Cross-Module/employee-projects-timesheet-flow.md`
**Content:**
- [ ] Employee created → resource created
- [ ] Resource added to project → project member
- [ ] Timesheet record creation
- [ ] Time tracked on task → timesheet line
- [ ] Billing: timesheet → sale order line
- [ ] Cross-module: HR ↔ Project ↔ Sale
- [ ] Error scenarios

### Task CM-2: Create Sale → Stock → Account Cross Flow
**File:** `Flows/Cross-Module/sale-stock-account-flow.md`
**Content:**
- [ ] Sale order confirmed → procurement triggered
- [ ] Procurement → stock picking created
- [ ] Picking validated → quant updated
- [ ] Delivery validated → invoiceable
- [ ] Invoice created → posted
- [ ] Payment received → reconciled
- [ ] Full end-to-end chain across 3 module categories
- [ ] Error scenarios

### Task CM-3: Create Purchase → Stock → Account Cross Flow
**File:** `Flows/Cross-Module/purchase-stock-account-flow.md`
**Content:**
- [ ] Purchase order confirmed
- [ ] Receipt created → products received
- [ ] Receipt validated → quant updated
- [ ] Vendor bill created from receipt
- [ ] Bill posted → accounting entries
- [ ] Payment made → reconciled
- [ ] Full end-to-end chain across 3 module categories
- [ ] Error scenarios

---

## Phase 3 Completion Criteria

All 22 tasks completed AND:
- [ ] All cross-module flows reviewed for consistency
- [ ] Wikilinks verified between all Tier 2 files
- [ ] Phase 3 checkpoint updated

**Estimated effort:** 4–5 sessions

**Next phase:** [Documentation/Upgrade-Plan/04-Task-List-Phase-4](04-Task-List-Phase-4.md)
