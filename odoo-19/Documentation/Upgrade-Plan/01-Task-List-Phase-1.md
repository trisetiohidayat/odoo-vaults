---
type: phase-checkpoint
phase: 1
title: "Phase 1 — Foundation & Templates"
status: pending
estimated_tasks: 9
created: 2026-04-06
---

# Phase 1 — Foundation & Templates

**Goal:** Establish patterns, templates, and conventions BEFORE building content. This ensures consistency across all modules.

**Dependencies:** None — this phase must be completed first.

---

## Task 1: Create Flow Template ✅ DONE

**File:** `Flows/TEMPLATE-flow.md`
**Status:** Complete (v1.1 — includes 7 enhanced sections)
**Completed:** 2026-04-06
**Sections included:**
- [x] Frontmatter with `type: flow`, `models_touched`, `audience`, `level`
- [x] Overview section
- [x] Trigger Point section
- [x] Complete Method Chain (`1.` → `N.` numbered steps)
- [x] Decision Tree section
- [x] Database State After Completion table
- [x] Error Scenarios table
- [x] Side Effects table
- [x] Security Context table
- [x] Transaction Boundary diagram + table
- [x] Idempotency table
- [x] Extension Points table (with override patterns)
- [x] Reverse / Undo Flow table
- [x] Alternative Triggers table
- [x] Related links section
- [x] Wikilinks to guide and module reference

**Verify:** ✅ Another person can fill in this template for any model using only the Flow Template as guide.

---

## Task 2: Create Business Guide Template ✅ DONE

**File:** `Business/TEMPLATE-guide.md`
**Status:** Complete (v1.1 — enhanced with multiple use cases)
**Completed:** 2026-04-06
**Sections included:**
- [x] Frontmatter with `type: guide`, `module`, `audience`, `level`, `prerequisites`
- [x] Quick Summary + Actor / Module / Use Case / Difficulty header
- [x] Prerequisites Checklist (checkbox format with critical warnings)
- [x] Quick Access table (Flow / Reference / Guide / Configuration links)
- [x] Multiple Use Cases support (table of contents + individual sections)
- [x] Steps with ⚡ System Trigger annotations
- [x] ⚡ Conditional Step annotations (IF/ELSE paths)
- [x] ⚡ Side Effect annotations per step
- [x] Expected Results Checklist
- [x] Optional Steps table (when to do what)
- [x] Common Pitfalls table (numbered, actionable)
- [x] Configuration Deep Dive (advanced options)
- [x] Troubleshooting table
- [x] Related Documentation table
- [x] Wikilinks to flow, module, patterns, and snippets

**Verify:** ✅ Another person can write a guide for any Odoo module using only this template.

---

## Task 3: Create Method Chain Example Snippet ✅ DONE

**File:** `Snippets/method-chain-example.md`
**Status:** Complete (v1.1 — enhanced with 6 additional patterns)
**Completed:** 2026-04-06
**Sections included:**
- [x] Basic chain: `A → B → C`
- [x] Branching: `A ├─► IF: → B; ELSE: → C`
- [x] Multiple conditions: `IF state == 'draft' / 'confirmed' / 'done'`
- [x] Cross-model trigger with module annotation
- [x] Nested side effects
- [x] Error/Exception path: `raise ValidationError()`
- [x] Computed field cascade: `@api.depends` propagation
- [x] State machine transition with pre-checks
- [x] Cron/scheduled action pattern
- [x] Wizard action flow pattern
- [x] **NEW: Extension Point pattern** with super() call
- [x] **NEW: Security Context pattern** with sudo usage
- [x] **NEW: Transaction Boundary diagram** with async distinction
- [x] **NEW: Idempotency pattern** with guard vs non-guard examples
- [x] **NEW: Reverse/Undo pattern** with immutable actions
- [x] **NEW: Cron Trigger pattern** with user context
- [x] Complete usage examples combining all patterns

**Verify:** ✅ Developer can copy-paste and adapt for any method chain documentation.

---

## Task 4: Enhance Core/API.md with Method Chain Notation ✅ DONE

**File:** `Core/API.md`
**Status:** Complete (v1.1 — full rewrite with enhanced sections)
**Completed:** 2026-04-06
**Sections added:**
- [x] Quick Reference table (decorator comparison)
- [x] @api.depends: cascade propagation with multi-level example
- [x] @api.depends: stored vs non-stored distinction
- [x] @api.onchange: cascade chain with return value patterns
- [x] @api.constrains: flow diagram with rollback behavior
- [x] @api.model: security context, use cases, idempotency
- [x] @api.model_create_multi: method chain on batch create
- [x] Security Context Summary table
- [x] Transaction Boundary Summary table
- [x] Common Anti-Patterns table (Odoo 19 deprecated patterns)
- [x] Extension Points Quick Reference table
- [x] Link to Flows/TEMPLATE-flow.md

**Verify:** ✅ Reader understands how decorator chains propagate and when to use each.

---

## Task 5: Enhance Patterns/Workflow Patterns.md with Branching ✅ DONE

**File:** `Patterns/Workflow Patterns.md`
**Status:** Complete (v1.1 — full rewrite with branching patterns)
**Completed:** 2026-04-06
**Sections added:**
- [x] Quick Reference table (component comparison)
- [x] Workflow with Pre-Validation (validation flow diagram)
- [x] Workflow with Branching Logic (multiple branch pattern)
- [x] Branching Decision Tree (ASCII diagram)
- [x] Multiple Branching Pattern (picking type example)
- [x] Workflow with Post-Transition Side Effects (execution order)
- [x] Side Effect Execution Order diagram
- [x] Workflow with mail.activity Integration
- [x] Full State Transition Diagram (draft→sent→sale→done→cancel)
- [x] Extension Points table with override patterns
- [x] Error Scenarios table
- [x] Anti-Patterns table (Odoo 19 deprecated patterns)
- [x] Idempotency in Workflows (guard examples)
- [x] Decision Tree Template (copy-paste documentation format)
- [x] Links to Flows/TEMPLATE-flow.md and Core/API.md

**Verify:** ✅ Developer can document any state machine workflow with branching logic.

---

## Task 6: Enhance Modules/HR.md with Level 1 Flows ✅ DONE

**File:** `Modules/HR.md`
**Status:** Complete (v1.1 — major enhancement)
**Completed:** 2026-04-06
**Sections added:**
- [x] Frontmatter with module, tags, version
- [x] Quick Access block (Reference / Flows / Guides / Related links)
- [x] Employee Creation Method Chain (8-step numbered flow)
- [x] Employee Archival Method Chain (7-step numbered flow)
- [x] Error Scenarios table (5 scenarios)
- [x] **NEW: hr.version model section** — Basic Info, Purpose, Key Fields, Key Methods, Version Lifecycle, Extension Point
- [x] **NEW: hr.employee.public section** — Basic Info, Purpose, Fields, Comparison table, Usage Context

**Also completed:**
- [x] `hr.version` section (was Task 7 — merged into Task 6)

**Verify:** ✅ HR.md now serves as complete AI-reference for employee lifecycle.

---

## Task 7: Create hr.version Model Section ✅ MERGED INTO TASK 6

**File:** `Modules/HR.md` (append as new section)
**Action:** Document `hr.version` model (currently inherited by `hr.employee` via `_inherits` but not documented)
**Content:**
- [ ] Basic Info (`_name`, `_description`, `_inherit`)
- [ ] Key Fields table (contract_date_start, contract_date_end, trial_date_end, contract_wage, etc.)
- [ ] Key Methods
- [ ] Relationship to `hr.employee`
- [ ] Link from `hr.employee` section's `_inherits` field

**Verify:** `hr.version` is now documented with same depth as other HR models.

---

## Task 8: Create Module Entry Point Template ✅ DONE

**File:** `Modules/TEMPLATE-module-entry.md`
**Status:** Complete (v1.1)
**Completed:** 2026-04-06
**Sections included:**
- [x] Quick Access block template (Reference / Flows / Guides / Related)
- [x] Full Module Template Structure
- [x] Section 1: Module Info (__manifest__.py template)
- [x] Section 2: Model Documentation template
- [x] Section 3: Method Chains (Level 1) template
- [x] Section 4: Business Flows (Cross-Module) template
- [x] Section 5: Integration Points template
- [x] Section 6: File Structure template
- [x] Checklist for New Module Documentation (Essentials / L1 / L2 / Quality)
- [x] Related Templates links

**Verify:** ✅ This template can guide future module documentation upgrades.

---

## Task 9: Test Templates with Real Module Example ✅ DONE

**Action:** Created real example files using all templates
**Completed:** 2026-04-06
**Files created:**
- [x] `Flows/HR/employee-creation-flow.md` — Real flow using TEMPLATE-flow.md
  - 28-step method chain
  - Decision tree, branching matrix
  - All enhanced sections (security, transaction, idempotency, etc.
  - Extension points, reverse flow, alternative triggers
- [x] `Flows/HR/employee-archival-flow.md` — Real flow using TEMPLATE-flow.md
  - Complete archive/unarchive chain
  - Manager subordinate handling
  - 7-error scenario table
- [x] `Business/HR/quickstart-employee-setup.md` — Real guide using TEMPLATE-guide.md
  - 3 use cases (PKWT, Freelance, Link User)
  - Prerequisites checklist
  - System trigger annotations
  - Troubleshooting table

**Templates verified working:**
- [x] `Flows/TEMPLATE-flow.md` — Successfully used for employee-creation-flow.md
- [x] `Business/TEMPLATE-guide.md` — Successfully used for quickstart-employee-setup.md
- [x] `Modules/TEMPLATE-module-entry.md` — Used as pattern for HR.md enhancement

**Phase 1 templates: VALIDATED ✅**

---

## Phase 1 Completion Criteria

All 9 tasks completed AND:
- [ ] Templates tested by writing one real Flow and one real Guide
- [ ] Templates refined based on testing
- [ ] Phase 1 checkpoint updated with completion date and notes
- [ ] Design doc (`00-LEVELING-UP-DESIGN.md`) updated with Phase 1 status

**Estimated effort:** 1–2 sessions

**Next phase:** [[Documentation/Upgrade-Plan/02-Task-List-Phase-2]]
