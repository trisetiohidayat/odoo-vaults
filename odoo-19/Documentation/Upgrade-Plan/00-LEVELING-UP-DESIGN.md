---
type: upgrade-design
title: "Vault Leveling Up — From Reference Docs to Master Knowledge Base"
version: 1.0
created: 2026-04-06
status: approved
scope: full-vault
audience: ai-reasoning, developer-onboarding, business-process
---

# Vault Leveling Up Design

## 1. Overview

**Goal:** Transform the Odoo 19 vault from a **reference documentation** (field lists, method tables) into a **Master Knowledge Base** that serves three audiences:

| Audience | Primary Use | Depth |
|----------|-------------|-------|
| AI (Claude) | Deep analysis, debugging, tracing bugs, explaining complex flows | Level 1 |
| Developer | Onboarding, understanding Odoo patterns, implementation guides | Level 2 |
| Business (Consultant/User) | Configuration walkthroughs, process guides, step-by-step | Level 2 |

**Principles:**
- All 608 modules remain documented (Library model)
- Entry point adjusted per installed module (Dashboards/Guides)
- All new content follows standardized formats
- Cross-module flows are centralized, not distributed

---

## 2. Target Depth Levels

### Level 1 — Enhanced Reference (AI-Optimized)

Per-module enhancements to existing docs:
- **Method chains**: Full call sequences from trigger to result
- **Branching logic**: IF/ELSE paths with conditions and outcomes
- **Cross-model triggers**: Effects on related models
- **Error scenarios**: What can go wrong, why, and when
- **Side effects**: Computed fields, constraints, notifications triggered

**Format:** Embedded in `Modules/XXX.md` as `## Flows` section
**Enhanced sections (v1.1):**
- Method Chain (numbered steps)
- Decision Tree
- Database State After Completion
- Error Scenarios
- Side Effects
- **Security Context** — user context, ACL requirements, sudo usage
- **Transaction Boundary** — atomic vs async steps, rollback behavior
- **Idempotency** — behavior on double-run, race conditions
- **Extension Points** — override hooks, super() pattern, deprecated patterns
- **Reverse / Undo Flow** — cancel, reverse, rollback options
- **Alternative Triggers** — cron, onchange, webhook, automated action
**Estimated effort:** 1–2 hours per module (for existing detailed modules)

### Level 2 — Comprehensive Walkthrough (Human-Optimized)

Per-module additions:
- **Use-case walkthroughs**: Step-by-step business scenarios
- **Decision trees**: When to use feature X vs Y
- **Common pitfalls**: What users/developers do wrong
- **Configuration prerequisites**: What must exist before starting
- **Cross-module navigation**: Links to related Flows and Business guides

**Format:** Separate file `Modules/XXX-Guide.md` + `Business/Category/XXX/`
**Estimated effort:** Half-day per module

### Out of Scope (Level 3 — Academy)

Not in current plan:
- Academic deep-dives into ORM internals
- Performance benchmarking per feature
- Security threat modeling per module
- Historical API comparisons across Odoo versions

---

## 3. Vault Structure

```
Odoo 19/
├── 00 - Index.md                          ✅ Existing
├── CLAUDE.md                              ✅ Existing
├── Core/                                  ✅ Existing (Enhanced Reference)
│   ├── BaseModel.md
│   ├── Fields.md
│   ├── API.md
│   ├── HTTP Controller.md
│   └── Exceptions.md
│   + Core/FLOW-compute-derive.md          🆕 Method chain patterns
│
├── Patterns/                              ✅ Existing (Enhanced Reference)
│   ├── Inheritance Patterns.md
│   ├── Security Patterns.md
│   ├── Workflow Patterns.md
│   + Patterns/FLOW-method-chain-patterns.md  🆕 Standard notation guide
│
├── Snippets/                              ✅ Existing
├── Tools/                                 ✅ Existing
├── New Features/                          ✅ Existing
│
├── Modules/                               🔄 Enhanced (3 files per module)
│   │
│   ├── Base/                              Level 1 Enhanced Reference
│   ├── Business/                          Level 2 Enhanced Reference
│   ├── Operational/                       Level 2 Enhanced Reference
│   ├── Integration/                       Level 2 Enhanced Reference
│   ├── Localization/                      Level 1 Enhanced Reference
│   │
│   + Template per module (3 files):
│     ├── XXX.md                           Reference + Level 1 Flows
│     ├── XXX-Guide.md                     Level 2 Quick Reference
│     └── XXX-Data.md                      Condensed data (already condensed)
│
├── Flows/                                 🆕 NEW — Centralized cross-module
│   │
│   ├── TEMPLATE-flow.md                   🆕 Standard flow template
│   ├── HR/
│   │   ├── employee-creation-flow.md
│   │   ├── employee-archival-flow.md
│   │   ├── employee-version-switch-flow.md
│   │   ├── attendance-checkin-flow.md
│   │   └── leave-request-flow.md
│   │
│   ├── Sale/
│   │   ├── quotation-to-sale-order-flow.md
│   │   ├── sale-confirmation-procurement-flow.md
│   │   ├── delivery-creation-flow.md
│   │   └── sale-to-invoice-flow.md
│   │
│   ├── Purchase/
│   │   ├── purchase-request-to-order-flow.md
│   │   ├── purchase-order-receipt-flow.md
│   │   └── purchase-to-bill-flow.md
│   │
│   ├── Stock/
│   │   ├── receipt-flow.md
│   │   ├── delivery-flow.md
│   │   ├── internal-transfer-flow.md
│   │   ├── picking-action-flow.md         (confirm→assign→validate→done)
│   │   └── return-flow.md
│   │
│   ├── Account/
│   │   ├── invoice-creation-flow.md
│   │   ├── invoice-post-flow.md
│   │   ├── payment-flow.md
│   │   ├── bank-reconciliation-flow.md
│   │   └── withholding-tax-flow.md        🆕 l10n_id priority
│   │
│   ├── CRM/
│   │   ├── lead-creation-flow.md
│   │   ├── lead-conversion-to-opportunity-flow.md
│   │   ├── opportunity-win-flow.md
│   │   └── lead-assignment-flow.md
│   │
│   ├── MRP/
│   │   ├── bom-to-production-flow.md
│   │   ├── production-order-flow.md
│   │   ├── workorder-execution-flow.md
│   │   └── byproduct-flow.md
│   │
│   └── Cross-Module/
│       ├── employee-projects-timesheet-flow.md
│       ├── sale-stock-account-flow.md
│       └── purchase-stock-account-flow.md
│
├── Business/                              🆕 NEW — Level 2 Walkthroughs
│   │
│   ├── TEMPLATE-guide.md                  🆕 Standard guide template
│   ├── HR/
│   │   ├── quickstart-employee-setup.md
│   │   ├── attendance-configuration.md
│   │   ├── leave-management-guide.md
│   │   └── payroll-structure-guide.md
│   │
│   ├── Sale/
│   │   ├── sales-process-guide.md
│   │   ├── quotation-best-practices.md
│   │   └── delivery-configuration.md
│   │
│   ├── Stock/
│   │   ├── warehouse-setup-guide.md
│   │   ├── inventory-management-guide.md
│   │   └── valuation-guide.md
│   │
│   ├── Purchase/
│   │   ├── vendor-management-guide.md
│   │   └── purchase-workflow-guide.md
│   │
│   ├── Account/
│   │   ├── chart-of-accounts-guide.md
│   │   ├── invoice-processing-guide.md
│   │   └── payment-management-guide.md
│   │
│   └── Dashboard/
│       ├── installed-modules-dashboard.md  🆕 Dynamic entry point
│       └── recommended-flows.md             🆕 Based on installed modules
│
├── Documentation/
│   ├── Checkpoints/                        ✅ Existing (legacy)
│   └── Upgrade-Plan/                       🆕 NEW — This system
│       ├── 00-LEVELING-UP-DESIGN.md        🆕 This file
│       ├── 01-Task-List-Phase-1.md         🆕 Phase 1 tasks
│       ├── 02-Task-List-Phase-2.md        🆕 Phase 2 tasks
│       ├── 03-Task-List-Phase-3.md        🆕 Phase 3 tasks
│       ├── 04-Task-List-Phase-4.md        🆕 Phase 4 tasks
│       └── CHECKPOINT-master.md            🆕 Progress tracker
│
└── Snippets/
    └── method-chain-example.md             🆕 Copy-paste template
```

---

## 4. Content Format Standards

### 4A. Module File (XXX.md) — Enhanced Reference

```markdown
## Quick Access

### 📖 Reference
→ Model & Field tables (existing content)

### 🔀 Flows (Technical)
→ [Flows/xxx-flow](Flows/xxx-flow.md) — method chain + branching

### 📋 How-To Guides (Functional)
→ [Business/Stock/warehouse-setup-guide](Business/Stock/warehouse-setup-guide.md) — step-by-step walkthroughs

---

## [Existing content continues...]

## Flows

### Employee Creation Flow
**Trigger:** `hr.employee` form → Save button / `create()` method
**Model:** `hr.employee`
**Models Touched:** `resource.resource`, `hr.version`, `res.partner`, `mail`

**Chain:**
```
hr.employee.create(vals)
  ├─► [A] IF vals.get('user_id'):
  │      └─► _onchange_user() → sync name, email, tz from res.users
  ├─► [B] resource.resource created via _inherits
  │      └─► _inverse_calendar_id() → cascade to employee
  │            └─► [B1] IF version_id:
  │                  └─► calendar synced from version
  ├─► [C] _create_work_contacts()
  │      └─► res.partner created (work_contact_id)
  ├─► [D] hr.version record auto-created
  │      └─► [D1] IF vals.get('contract_date_start'):
  │            └─► populate from contract template
  │      └─► [D2] current_version_id set = this version
  ├─► [E] _sync_salary_distribution()
  │      └─► [E1] IF bank.allow_out_payment:
  │            └─► _compute_is_trusted_bank_account = False
  ├─► [F] _compute_presence_icon()
  │      └─► _compute_presence_state()
  │            └─► _get_employee_working_now()
  └─► [G] mail.thread:
         └─► partner_ids subscribed, activity planned

Result: Employee active, linked to resource, has version, work contact created
```

**Branching Matrix:**
| Condition | Path | Side Effect |
|-----------|------|-------------|
| `user_id` provided | A → `_onchange_user()` | name, email, tz auto-filled |
| `user_id` empty | skip A | manual entry required |
| `contract_template_id` set | D1 → template applied | wage, type auto-filled |
| `contract_template_id` empty | D1 → skip | manual contract setup |

**Error Scenarios:**
| Trigger | Error | Constraint/Reason |
|---------|-------|-------------------|
| Duplicate barcode | `ValidationError` | `_barcode_uniq = unique(barcode)` |
| User already in same company | `ValidationError` | `_user_uniq = unique(user_id, company_id)` |
| Missing required field | `ValidationError` | ORM `required=True` on name, company_id |
| Missing contract_date_start | version created but inactive | `is_in_contract = False` |

---

### 4B. Flow File (Flows/xxx-flow.md) — Cross-Module Chain

```markdown
---
type: flow
title: "Employee Creation Flow"
primary_model: hr.employee
trigger: User action (HR → Employees → Create)
cross_module: true
models_touched:
  - hr.employee
  - resource.resource
  - hr.version
  - res.partner
  - mail.thread
audience: ai-reasoning, developer
level: 1
---

# Employee Creation Flow

## Overview

Complete end-to-end method chain when a new employee record is created
through the Odoo UI, covering all cross-module triggers and side effects.

## Trigger Point

User: Opens **HR → Employees → Create**, fills form, clicks **Save**.

## Complete Method Chain

```
1. hr.employee.create(vals)
   │
   ├─► 2. hr.version.create({
   │       employee_id: self.id,
   │       contract_date_start: vals.get('contract_date_start'),
   │       contract_wage: vals.get('wage'),
   │       ...
   │     })
   │     └─► 3. current_version_id = this record
   │
   ├─► 4. resource.resource.create({
   │       name: vals.get('name'),
   │       type: 'user',
   │       company_id: vals.get('company_id'),
   │       ...
   │     })
   │     └─► 5. resource_id = this record (inverse via _inherits)
   │           └─► 6. _inverse_calendar_id()
   │                 └─► 7. resource_calendar_id synced to employee
   │
   ├─► 8. _create_work_contacts()
   │     └─► 9. res.partner.create({
   │            name: employee.name,
   │            email: employee.work_email,
   │            company_id: employee.company_id,
   │            employee_id: employee.id
   │          })
   │          └─► 10. work_contact_id = this partner
   │
   ├─► 11. IF vals.get('user_id'):
   │      └─► 12. _onchange_user()
   │            ├─► name = user.name
   │            ├─► work_email = user.email
   │            └─► tz = user.tz
   │
   ├─► 13. _sync_salary_distribution()
   │      └─► 14. salary_distribution JSON updated
   │
   ├─► 15. _compute_presence_icon()
   │      └─► 16. _compute_presence_state()
   │            └─► 17. _get_employee_working_now()
   │                  └─► hr_presence_state set
   │
   └─► 18. mail.thread:
          ├─► 19. Message posted: "Employee Created"
          └─► 20. Followers added (HR team members)
```

## Decision Tree

```
Employee Created
│
├─ user_id provided?
│  ├─ YES → _onchange_user() fires
│  │        └─ name, email, tz auto-filled from user
│  └─ NO → manual entry, no auto-sync
│
├─ contract_template_id provided?
│  ├─ YES → _onchange_contract_template_id() fires
│  │        └─ wage, type, calendar auto-filled from template
│  └─ NO → start from blank contract
│
├─ bank_account_ids have allow_out_payment?
│  ├─ YES → is_trusted_bank_account = False (warning)
│  └─ NO → is_trusted_bank_account = True
│
└─ timezone set?
   ├─ YES → used for attendance / presence calculation
   └─ NO → fallback to company's timezone
```

## Database State After Completion

| Table | Record Created | Fields Set |
|-------|--------------|------------|
| `hr_employee` | 1 | name, company_id, resource_id, work_contact_id |
| `hr_version` | 1 | employee_id, contract_date_start, contract_wage |
| `resource_resource` | 1 | name, type, company_id, user_id |
| `res_partner` | 1 | name, email, company_id, employee_id |

## Error Scenarios

| Scenario | Error Raised | Constraint |
|----------|-------------|------------|
| Barcode already exists | `ValidationError: Badge ID already exists` | `_barcode_uniq` |
| Same user + same company | `ValidationError: User already linked` | `_user_uniq` |
| Missing name | `ValidationError: Field 'Name' is required` | ORM required |
| company_id mismatch with user | Warning, not blocking | Soft validation |

## Related

- Walkthrough: [Business/HR/quickstart-employee-setup](Business/HR/quickstart-employee-setup.md)
- Flow: [Flows/HR/employee-archival-flow](Flows/HR/employee-archival-flow.md)
- Module: [Modules/HR](Modules/hr.md)
- Module: [Modules/resource](Modules/resource.md) (resource.resource)
```

---

### 4C. Business Guide (Business/xxx/guide.md) — Walkthrough

```markdown
---
type: guide
title: "Quickstart: Employee Setup"
module: hr
audience: business-consultant
level: 2
prerequisites:
  - Company configured in Settings
  - Departments created (optional but recommended)
  - Contract types configured (HR → Configuration → Contract Types)
---

# Quickstart: Employee Setup

**Actor:** HR Manager
**Module:** HR (Employees)
**Time to complete:** ~5 minutes per employee

## Prerequisites Checklist

Before creating employees, ensure:
- [ ] Company is configured (**Settings → General Settings → Companies**)
- [ ] Departments are created (**HR → Configuration → Departments**)
- [ ] Job Positions are created (**HR → Configuration → Job Positions**)
- [ ] Contract Types exist (**HR → Configuration → Contract Types**)
- [ ] Working Hours (Calendar) configured (**Settings → Technical → Working Hours**)

## Use Case: Create Employee with PKWT Contract

### Step 1 — Navigate
```
HR → Employees → Create
```

### Step 2 — Basic Information
Fill in:
- **Name** *(required)* — Full legal name
- **Work Email** — Company email address
- **Department** — Select from existing departments
- **Job Position** — Select from configured jobs

> **⚡ System Trigger:** If you link a **User** (res.users), Odoo will auto-fill Name, Email, and Timezone from the user record via `_onchange_user()`.
> No need to fill manually if user already exists.

### Step 3 — Work Information
Fill in:
- **Work Location** — Office, Home, or Other
- **Working Hours** — Select calendar (e.g., "Standard 40h/week")
- **Manager** — Select direct manager (optional but recommended)

### Step 4 — Contract Information
Click **Contract** tab or use contract wizard:
- **Contract Type** — PKWT / PKWTT / Freelance / etc.
- **Start Date** *(required)* — Contract start date
- **Wage** — Monthly salary

> **⚡ System Trigger:** When Start Date is set, Odoo automatically creates an `hr.version` record linked to this employee. The employee becomes "in contract" (`is_in_contract = True`).

### Step 5 — Save & Verify
Click **Save**.

**Expected results:**
- Employee appears in **HR → Employees** list
- Employee appears under **Department → Members** tab
- Work contact created in **Contacts** (res.partner)
- Resource calendar created in **Settings → Working Hours**
- Notification sent to HR team members (if mail.thread enabled)

## Common Pitfalls

| Pitfall | Symptom | Solution |
|---------|---------|----------|
| Forgot to set contract start date | Employee has `is_in_contract = False` | Edit employee, set contract date |
| Wrong company selected | Employee not visible in dashboard | Check company_id on employee form |
| Empty barcode/PIN | Attendance via badge fails | Set barcode in **Personal Info → Attendance** |
| No working hours set | Attendance check-in/out not tracked | Configure calendar in **Work Information** |
| Duplicate barcode | Error on save | Check **Personal Info → Identification** |

## Related Documentation

- Technical Flow: [Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md)
- Guide: [Business/HR/leave-management-guide](Business/HR/leave-management-guide.md)
- Module: [Modules/HR](Modules/hr.md)
- Module: [Modules/HR](Modules/hr.md)
```

---

## 5. Module Priority Tiers

Modules are organized into tiers based on business impact and complexity:

### Tier 1 — Critical Business Modules (Priority: First)
| Module | Files to Create | Notes |
|--------|----------------|-------|
| `hr` | Flows: 5, Business: 4 | Foundation for other HR modules |
| `sale` | Flows: 4, Business: 3 | Core revenue process |
| `stock` | Flows: 5, Business: 3 | Core logistics |
| `purchase` | Flows: 3, Business: 2 | Core procurement |
| `account` | Flows: 5, Business: 3 | Core finance |

### Tier 2 — Integration & Operational Modules (Priority: Second)
| Module | Files to Create | Notes |
|--------|----------------|-------|
| `crm` | Flows: 4, Business: 2 | Revenue pipeline |
| `mrp` | Flows: 4, Business: 2 | Manufacturing |
| `hr_holidays` | Flows: 3, Business: 2 | Leave management |
| `hr_attendance` | Flows: 2, Business: 2 | Attendance tracking |
| `hr_contract` | Flows: 2, Business: 2 | Contract management |

### Tier 3 — Supporting Modules (Priority: Third)
| Module | Files to Create | Notes |
|--------|----------------|-------|
| `product` | Flows: 2, Business: 2 | Master data |
| `project` | Flows: 3, Business: 2 | Project management |
| `mrp_subproducting` | Flows: 1 | MRP extension |
| `quality` | Flows: 2, Business: 1 | Quality control |
| `helpdesk` | Flows: 3, Business: 2 | Customer support |

### Tier 4 — Enhancement & Add-on Modules (Priority: Fourth)
| Module | Files to Create | Notes |
|--------|----------------|-------|
| `sale_margin` | Flows: 1 | Margin analysis |
| `stock_account` | Flows: 2 | Inventory valuation |
| `pos` | Flows: 3, Business: 2 | Point of Sale |
| `account_edi` | Flows: 2 | Electronic invoicing |
| `website_sale` | Flows: 3, Business: 2 | E-commerce |

### Tier 5 — Utilities & Localization (Priority: Last)
| Module | Files to Create | Notes |
|--------|----------------|-------|
| `base` | Flows: 1 | Core utilities |
| `mail` | Flows: 2 | Communication |
| `resource` | Flows: 1 | Resource planning |
| `l10n_id` | Flows: 2, Business: 2 | Indonesian localization |
| Other l10n_* | Flows: 0-1 | Minimal for data modules |

---

## 6. Phase Breakdown

| Phase | Scope | Estimated Tasks | Priority |
|-------|-------|----------------|----------|
| **Phase 1** | Core patterns & Templates | ~8 tasks | Foundation |
| **Phase 2** | Tier 1 Modules (5 modules) | ~25 tasks | Critical business |
| **Phase 3** | Tier 2 Modules (5 modules) | ~20 tasks | Operational |
| **Phase 4** | Tier 3 Modules (5 modules) | ~15 tasks | Supporting |
| **Phase 5** | Tier 4 & 5 + Gap Filling | ~20 tasks | Enhancement |

**Total estimated tasks: ~88 tasks across 5 phases**

---

## 7. Checkpoint System

New checkpoint files in `Documentation/Upgrade-Plan/`:

```
Documentation/Upgrade-Plan/
├── 01-Task-List-Phase-1.md   — Foundation: patterns, templates
├── 02-Task-List-Phase-2.md   — Tier 1 modules
├── 03-Task-List-Phase-3.md   — Tier 2 modules
├── 04-Task-List-Phase-4.md   — Tier 3 modules
├── 05-Task-List-Phase-5.md   — Tier 4, 5, gaps
└── CHECKPOINT-master.md      — Progress tracker (all phases)
```

Each phase checkpoint follows this format:

```markdown
# Phase 1 — Foundation & Templates

## Goals
- [x] Create TEMPLATE-flow.md
- [ ] Create TEMPLATE-guide.md
- [ ] Create method-chain-example.md
- [ ] Enhance Core/API.md with method chain notation
- [ ] Enhance Patterns/Workflow Patterns.md

## Completion: 1/5 (20%)

## Notes
[Session notes, decisions made, blockers]
```

---

## 8. Success Criteria

This upgrade is complete when:

1. **AI Reasoning Test:**
   > "Explain the complete employee creation flow, including all cross-module effects and possible error scenarios."
   → AI can answer from vault docs alone, without source code lookup.

2. **Developer Onboarding Test:**
   > "I need to create a custom module that extends hr.employee. Walk me through what happens when an employee is created."
   → Developer can follow flow doc + reference doc to understand full picture.

3. **Business Consultant Test:**
   > "How do I set up an employee with a PKWT contract in Odoo?"
   → Consultant can follow step-by-step guide without needing technical knowledge.

---

## 9. Open Decisions (Delegated to Implementer)

| Decision | Option | Recommendation |
|----------|--------|----------------|
| Flows file naming | `module-action-flow.md` vs `module_action_flow.md` | Hyphen-separated: `employee-creation-flow.md` |
| Module files: 3 vs 2 files | `XXX.md + XXX-Guide.md + XXX-Data.md` vs `XXX.md + XXX-Guide.md` | Start with 2, add Data if needed |
| Existing condensed files | Keep as-is vs upgrade all | Keep as-is (low business impact) |
| Localization flows | Per-country vs global l10n flow | Global first, l10n_id as pilot |

---

*Document status: Approved — ready for implementation*
*Next: Invoke writing-plans skill to create implementation plan*
