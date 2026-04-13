---
type: phase-checkpoint
phase: 5
title: "Phase 5 — Tier 4 & 5: Enhancements, Localization & Gap Filling"
status: pending
estimated_tasks: 18
depends_on: Phase 4
created: 2026-04-06
---

# Phase 5 — Tier 4 & 5: Enhancements, Localization & Gap Filling

**Goal:** Complete remaining modules, fill gaps, and finalize documentation.

---

## Tier 4: Integration & Add-on Modules

### Task T4-1: Create Account EDI/Peppol Flow
**File:** `Flows/Account/edi-invoice-flow.md`
**Content:**
- [ ] Invoice post → EDI document generated
- [ ] Peppol participant ID lookup
- [ ] UBL/XML document structure
- [ ] Transmission to Peppol network
- [ ] Acknowledgment / error handling
- [ ] Status tracking
- [ ] Cross-module: Account ↔ EDI ↔ Peppol
- [ ] Error scenarios
**Priority:** High (regulatory importance in many countries)

### Task T4-2: Create Website Sale Flow
**File:** `Flows/Website/website-sale-flow.md`
**Content:**
- [ ] Product published on website
- [ ] Cart management
- [ ] Checkout process → `sale.order` created
- [ ] Payment provider integration
- [ ] Order confirmation email
- [ ] Cross-module: Website ↔ Sale ↔ Payment
- [ ] Error scenarios

### Task T4-3: Create Website Sale Business Guide
**File:** `Business/Website/ecommerce-configuration-guide.md`
**Content:**
- [ ] Product website configuration
- [ ] Payment provider setup
- [ ] Shipping methods
- [ ] Terms and conditions
- [ ] Common pitfalls

### Task T4-4: Create Stock Valuation Flow
**File:** `Flows/Stock/stock-valuation-flow.md`
**Content:**
- [ ] Stock move done → valuation entry created
- [ ] FIFO / AVCO / Standard price computation
- [ ] Anglo-Saxon vs Continental valuation
- [ ] Landed cost integration
- [ ] Inventory adjustment → stock.valuation.layer
- [ ] Cross-module: Stock ↔ Account
- [ ] Error scenarios

### Task T4-5: Enhance Modules/web.md — Add Flow Links
**File:** `Modules/web.md`
**Update:**
- [ ] Quick Access block
- [ ] Document layout → link to web widget flows (if any)

---

## Tier 5: Utilities, Base & Localization

### Task T5-1: Create Core Resource/Attendance Mixin Flow
**File:** `Flows/Base/resource-attendance-flow.md`
**Content:**
- [ ] `resource.resource` creation
- [ ] Calendar assignment
- [ ] Attendance computation from calendar
- [ ] Leave allocation → resource leaves
- [ ] Error scenarios

### Task T5-2: Create Mail Thread Notification Flow
**File:** `Flows/Base/mail-notification-flow.md`
**Content:**
- [ ] `mail.message` creation
- [ ] Follower notification
- [ ] Email notification generation
- [ ] Inbox notification
- [ ] Notification preferences respected
- [ ] Error scenarios

### Task T5-3: Enhance Modules/l10n_id.md — Full Level 2
**File:** `Modules/l10n_id.md`
**Action:** Upgrade from current 88 lines to full reference
**Content:**
- [ ] Quick Access block
- [ ] Complete Indonesian tax structure:
    - [ ] PPN 11% / 12% computation
    - [ ] PPnBM (luxury tax)
    - [ ] Withholding tax: PPh 21, 22, 23, 26
    - [ ] Faktur Pajak format and numbering
    - [ ] DJP e-Faktur integration
- [ ] Flow: Tax computation on invoice
- [ ] Flow: Faktur Pajak issuance
- [ ] Flow: Withholding tax deduction
- [ ] Common pitfalls for Indonesian localization
- [ ] Related: [Modules/Account](Modules/account.md), [Modules/Purchase](Modules/purchase.md), [Modules/Sale](Modules/sale.md)

### Task T5-4: Create Indonesian Localization Business Guide
**File:** `Business/Account/l10n-id-tax-guide.md`
**Content:**
- [ ] Tax configuration walkthrough
- [ ] Journal setup for PPN
- [ ] Customer/vendor tax configuration
- [ ] Invoice with PPN step-by-step
- [ ] Withholding tax on purchase step-by-step
- [ ] Faktur Pajak reporting
- [ ] Common pitfalls

### Task T5-5: Create l10n_id Purchase Flow
**File:** `Flows/Purchase/purchase-withholding-flow.md` (l10n_id focus)
**Content:**
- [ ] PO → receipt → vendor bill flow
- [ ] Withholding tax auto-computation (PPh 22/23)
- [ ] Tax journal entries
- [ ] E-SPT integration notes
- [ ] Cross-module: Purchase ↔ Account ↔ l10n_id

### Task T5-6: Update Other Key l10n Files (Basic Enhancement)
**Files:** `Modules/l10n_de.md`, `Modules/l10n_us.md`, `Modules/l10n_fr.md`
**Action:** Add Quick Access block + minimal flow links
**Content:**
- [ ] Quick Access block pointing to parent Account module flows
- [ ] Country-specific tax notes if materially different from standard
- [ ] Link to [Modules/Account](Modules/account.md) for generic flows
- [ ] Note about localization scope

---

## Gap Filling Tasks

### Task Gap-1: Create Missing Module Files
**Action:** Create module documentation files for any important modules not yet documented
**Potential gaps (verify against Modules Inventory):**
- [ ] `Modules/iot.md` — IoT / hardware
- [ ] `Modules/studio.md` — Studio customization
- [ ] `Modules/knowledge.md` — Knowledge management
- [ ] `Modules/rental.md` — Rental management
- [ ] `Modules/purchase_requisition.md` — Purchase requisitions
- [ ] Verify and create for any other high-impact missing modules

### Task Gap-2: Verify All Cross-Module Links
**Action:** Systematic link verification across all phases
**Content:**
- [ ] All wikilinks from Flow → Flow, Flow → Module, Flow → Guide
- [ ] All wikilinks from Module Quick Access → relevant Flows and Guides
- [ ] All wikilinks from Guide → relevant Flows and Modules
- [ ] No broken `[link](link.md)` references
- [ ] Update `Tools/ORM Operations.md` with cross-model examples if missing

### Task Gap-3: Create Master Index Update
**File:** `00 - Index.md`
**Action:** Update vault landing page to reflect new structure
**Content:**
- [ ] Quick navigation to `Flows/` directory
- [ ] Quick navigation to `Business/` directory
- [ ] Quick navigation to `Documentation/Upgrade-Plan/`
- [ ] Tier overview table
- [ ] Progress indicator (current phase)

### Task Gap-4: Create Entry Point Dashboard
**File:** `Business/Dashboard/installed-modules-dashboard.md`
**Action:** Create dynamic entry point for users based on installed modules
**Content:**
- [ ] Table of contents by module category
- [ ] Quick links to relevant flows per module
- [ ] Quick links to relevant guides per module
- [ ] Link to `Modules Inventory` for full module list

---

## Phase 5 Completion Criteria

All 18 tasks completed AND:
- [ ] All 608 modules have at least a minimal Quick Access block
- [ ] All key business flows documented
- [ ] All cross-module links verified
- [ ] Index page updated
- [ ] Dashboard entry point created
- [ ] Phase 5 checkpoint updated
- [ ] Master checkpoint (`CHECKPOINT-master.md`) marked 100%

**Estimated effort:** 3–4 sessions

**Final deliverable:** [Documentation/Upgrade-Plan/CHECKPOINT-master](Documentation/Upgrade-Plan/CHECKPOINT-master.md)
