---
type: guide
title: "[Guide Title]"
module: module_name
submodule: submodule_name
audience: business-consultant, developer, ai-reasoning
level: 2
prerequisites:
  - prerequisite_1_configured
  - prerequisite_2_setup
  - prerequisite_3_created
estimated_time: "~10 minutes"
related_flows:
  - "[Flows/Module/flow-name](Flows/Module/flow-name.md)"
related_guides:
  - "[Business/Module/other-guide](Business/Module/other-guide.md)"
source_module: module_name
created: YYYY-MM-DD
updated: YYYY-MM-DD
version: "1.1"
---

# [Guide Title]

> **Quick Summary:** [1-sentence executive summary of what this guide covers.]

**Actor:** [Who performs this — HR Manager, Salesperson, Warehouse Staff, etc.]
**Module:** [Primary module name]
**Use Case:** [Brief description of the business scenario]
**Difficulty:** ⭐ Easy / ⭐⭐ Medium / ⭐⭐⭐ Advanced

---

## Prerequisites Checklist

Before starting, ensure the following are configured. Skipping these will cause errors or missing features.

- [ ] **[Prerequisite 1]** — [e.g., "Company configured in Settings → Companies"]
- [ ] **[Prerequisite 2]** — [e.g., "Departments created in HR → Configuration → Departments"]
- [ ] **[Prerequisite 3]** — [e.g., "Contract types set up in HR → Configuration → Contract Types"]
- [ ] **[Prerequisite 4]** — [e.g., "Users assigned to appropriate groups"]
- [ ] **[Prerequisite 5]** — [e.g., "Products with proper routes configured"]

> **⚠️ Critical:** If [specific prerequisite] is missing, the system will [specific error/behavior].

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Sale/sale-to-delivery-flow](Flows/Sale/sale-to-delivery-flow.md) | Full method chain and branching logic |
| 📖 Module Reference | [Modules/Stock](Modules/stock.md) | Complete field and method reference |
| 📋 Related Guide | [Modules/Stock](Modules/stock.md) | Related process walkthrough |
| 🔧 Configuration | [Modules/Stock](Modules/stock.md) | Advanced configuration options |

---

## Use Cases Covered

This guide covers the following use cases. Jump to the relevant section:

| # | Use Case | Page | Difficulty |
|---|----------|------|-----------|
| 1 | [Use case A — e.g., "Create employee with PKWT"] | [#use-case-a-create-employee-with-pkwt](#use-case-a-create-employee-with-pkwt.md) | ⭐ |
| 2 | [Use case B — e.g., "Create employee with freelance contract"] | [#use-case-b-create-employee-with-freelance](#use-case-b-create-employee-with-freelance.md) | ⭐⭐ |
| 3 | [Use case C — e.g., "Renew expiring contract"] | [#use-case-c-renew-expiring-contract](#use-case-c-renew-expiring-contract.md) | ⭐⭐⭐ |

---

## Use Case A: [Descriptive Name]

*[Repeat this block for each use case]*

### Scenario
[Brief description of the business scenario. E.g., "A company needs to hire a new full-time employee under PKWT (Fixed-Term Contract) for 12 months."]

### Steps

#### Step 1 — [Action Name]

Navigate to: `[Menu path — e.g., HR → Employees → Create]`

Click **[Button/Action]**.

> **⚡ System Behavior:** When you navigate here, Odoo [loads/filters/displays] [what happens].

#### Step 2 — Fill Basic Information

| Field | Value | Required | Auto-filled |
|-------|-------|----------|-------------|
| **Name** | [value] | ✅ Yes | — |
| **Work Email** | [value] | ✅ Yes | From linked user |
| **Department** | [value] | No | — |
| **Job Position** | [value] | No | — |

> **⚡ System Trigger:** If you link a **User** (res.users), Odoo auto-fills Name, Email, and Timezone from the user record via [`_onchange_user()`]([Flows/Module/flow#method-chain](flows/module/flow#method-chain.md)).

#### Step 3 — Configure Contract

> **⚡ Conditional Step:**
> - IF [condition A]: Follow path A → [result]
> - ELSE IF [condition B]: Follow path B → [result]
> - ELSE: Follow default path → [result]

Click **[Contract Tab]** and fill:

| Field | Value | Notes |
|-------|-------|-------|
| **Contract Type** | PKWT | From HR → Configuration → Contract Types |
| **Start Date** | [date] | Required for contract activation |
| **End Date** | [date] | 12 months from start |
| **Wage** | [amount] | Monthly salary |

> **⚡ System Trigger:** When **Start Date** is set, Odoo automatically creates an `hr.version` record linked to this employee. The employee becomes "in contract" (`is_in_contract = True`).
>
> **⚡ Side Effect:** When contract is saved, Odoo:
> - Creates resource calendar entry
> - Registers employee in working hours schedule
> - Triggers attendance tracking

#### Step 4 — Save and Verify

Click **Save**.

**Expected Results Checklist:**
- [ ] Employee appears in **HR → Employees** list
- [ ] Employee appears under **Department → Members** tab
- [ ] Work contact created in **Contacts** (res.partner)
- [ ] Resource calendar entry created in **Settings → Working Hours**
- [ ] Notification sent to HR team (if mail.thread enabled)

#### Step 5 — [Optional: Additional Configuration]

| Step | Action | Path | Why |
|------|--------|------|-----|
| 5a | Set barcode/PIN for attendance | Personal Info → Attendance | Required for badge-based check-in |
| 5b | Assign manager | Work Information → Manager | For org chart and approval chain |
| 5c | Add to category/tag | Personal Information → Category | For reporting and filtering |

---

## Use Case B: [Descriptive Name]

*[Template same as Use Case A]*

---

## Use Case C: [Descriptive Name]

*[Template same as Use Case A]*

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | [Common mistake 1] | [Wrong outcome / error] | [Prevention step] |
| 2 | [Common mistake 2] | [Wrong outcome / error] | [Prevention step] |
| 3 | [Common mistake 3] | [Wrong outcome / error] | [Prevention step] |
| 4 | Forgetting to set contract start date | Employee has `is_in_contract = False`, no attendance tracking | Always set Start Date in Contract tab |
| 5 | Wrong company selected | Employee not visible in dashboard, access errors | Check company_id on employee form before saving |

---

## Configuration Deep Dive

*[Optional section — for advanced configuration]*

### Related Configuration Paths

| Configuration | Menu Path | Controls |
|--------------|-----------|----------|
| [Config A] | Settings → General → [path] | [What it controls] |
| [Config B] | [Module] → Configuration → [path] | [What it controls] |

### Advanced Options

| Option | Field Name | Default | Effect When Enabled |
|--------|-----------|---------|-------------------|
| [Option A] | [field_name] | [default] | [Effect description] |

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|---------|
| Employee not appearing in department list | Wrong company_id filter | Switch to correct company in top-right dropdown |
| Attendance not tracked | No working hours set | Configure calendar in Work Information |
| Duplicate barcode error | Barcode already used by another employee | Check HR → Configuration → Employees → Badges |
| Cannot approve own request | Self-approval not allowed by default | Requires `group_hr_manager` or change in settings |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Sale/sale-to-delivery-flow](Flows/Sale/sale-to-delivery-flow.md) | Full method chain — for developers |
| 📖 Module Reference | [Modules/Stock](Modules/stock.md) | Complete field and method list |
| 📋 Related Guide | [Modules/Purchase](Modules/purchase.md) | Related business process |
| 🔧 Patterns | [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) | Workflow design patterns |
| 🛠️ Snippets | [Snippets/Model Snippets](Snippets/Model Snippets.md) | Code snippets for customization |
