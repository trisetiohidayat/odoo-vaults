---
type: guide
title: "Quickstart: Employee Setup"
module: hr
audience: business-consultant, hr-manager
level: 2
prerequisites:
  - company_configured
  - departments_created
  - contract_types_configured
  - working_hours_defined
estimated_time: "~5 minutes per employee"
related_flows:
  - "[Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md)"
  - "[Flows/HR/employee-archival-flow](Flows/HR/employee-archival-flow.md)"
source_module: hr
created: 2026-04-06
version: "1.0"
---

# Quickstart: Employee Setup

> **Quick Summary:** Create a new employee record with contract information in Odoo HR module.

**Actor:** HR Manager / HR Officer
**Module:** HR (Employees)
**Difficulty:** ⭐ Easy

---

## Prerequisites Checklist

Before creating employees, ensure the following are configured. Skipping these will cause errors or missing features.

- [ ] **Company configured** — Settings → General Settings → Companies
- [ ] **Departments created** — HR → Configuration → Departments
- [ ] **Job Positions created** — HR → Configuration → Job Positions
- [ ] **Contract Types configured** — HR → Configuration → Contract Types
- [ ] **Working Hours defined** — Settings → Technical → Working Hours
- [ ] **Users with HR access** — Settings → Users → assigned to HR groups

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md) | Full method chain and branching |
| 📖 Module Reference | [Modules/HR](Modules/hr.md) | Complete field and method reference |
| 📋 Related Guide | [Business/HR/leave-management-guide](Business/HR/leave-management-guide.md) | Leave management process |

---

## Use Cases Covered

| # | Use Case | Difficulty |
|---|----------|-----------|
| 1 | Create Employee with PKWT Contract | ⭐ |
| 2 | Create Employee with Freelance Contract | ⭐⭐ |
| 3 | Link Existing User to Employee | ⭐ |

---

## Use Case 1: Create Employee with PKWT Contract

### Scenario
A company needs to hire a new full-time employee under PKWT (Perjanjian Kerja Waktu Tertentu / Fixed-Term Contract) for 12 months.

### Steps

#### Step 1 — Navigate to Employee Creation

Go to: **HR → Employees → Create**

Click the **Create** button.

> **⚡ System Behavior:** New employee form opens with blank fields.

#### Step 2 — Fill Basic Information

| Field | Value | Required | Notes |
|-------|-------|----------|-------|
| **Name** | Full legal name | ✅ Yes | As on ID card |
| **Work Email** | company@domain.com | ✅ Yes | Company email |
| **Department** | Select from list | No | Must exist first |
| **Job Position** | Select from list | No | Must exist first |

> **⚡ System Trigger:** If you link an **existing User** (res.users), Odoo auto-fills Name, Email, Timezone, and Mobile from the user record. No need to fill manually if user already exists.

#### Step 3 — Configure Work Information

| Field | Value | Required | Notes |
|-------|-------|----------|-------|
| **Work Location** | Office | No | home / office / other |
| **Working Hours** | Standard 40h/week | No | Required for attendance |
| **Manager** | Select employee | No | For org chart |

> **⚡ System Trigger:** Working hours determines attendance schedule. If not set, employee won't be tracked in attendance.

#### Step 4 — Configure Contract

Click **Contract** tab or use the contract wizard:

| Field | Value | Required | Notes |
|-------|-------|----------|-------|
| **Contract Type** | PKWT | ✅ Yes | From Contract Types config |
| **Start Date** | YYYY-MM-DD | ✅ Yes | Contract start |
| **End Date** | +12 months | No | PKWT has end date |
| **Wage** | Monthly amount | ✅ Yes | Before tax |

> **⚡ System Trigger:** When **Start Date** is set, Odoo automatically creates an `hr.version` record (contract version) linked to this employee. The employee becomes "in contract" (`is_in_contract = True`).
>
> **⚡ Side Effects:**
> - Resource calendar entry created
> - Employee registered in working hours schedule
> - Attendance tracking activated

#### Step 5 — Save and Verify

Click **Save**.

**Expected Results Checklist:**
- [ ] Employee appears in **HR → Employees** list
- [ ] Employee appears under **Department → Members** tab
- [ ] Work contact created in **Contacts** (res.partner)
- [ ] Resource calendar entry in **Settings → Working Hours**
- [ ] Contract version visible in employee form

#### Step 6 — Optional: Configure Attendance

| Action | Path | Why |
|--------|------|-----|
| Set Barcode/PIN | Personal Info → Attendance | For badge-based check-in |
| Enable Geolocation | Personal Info → Attendance | For mobile check-in |
| Assign Category | Personal Information → Category | For reporting/filtering |

---

## Use Case 2: Create Employee with Freelance Contract

### Scenario
A company needs to hire a freelance consultant without a fixed contract end date.

### Steps

**Follow same steps as Use Case 1, with these differences:**

| Field | Value | Notes |
|-------|-------|-------|
| **Contract Type** | Freelance | Different from PKWT |
| **End Date** | Leave blank | Freelance has no end date |
| **Wage Type** | Hourly | If billing by hour |

> **⚡ System Behavior:** Without End Date, the employee version is always "current" and never expires.

---

## Use Case 3: Link Existing User to Employee

### Scenario
A user account already exists, and you need to link it to an employee record.

### Steps

#### Step 1 — Create Employee with User

When creating employee, click **User** field and select existing user:

> **⚡ System Trigger:** When user is selected:
> - Name auto-filled from user
> - Work Email auto-filled from user
> - Timezone synced from user
> - Mobile synced from user (if available)

#### Step 2 — Verify Link

After saving, verify:
- Employee form shows linked user
- User form shows linked employee
- Employee can access Odoo with their credentials

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Forgot to set contract start date | `is_in_contract = False`, no attendance tracking | Always set Start Date in Contract tab |
| 2 | Wrong company selected | Employee not visible in dashboard | Check company in top-right dropdown |
| 3 | Barcode/PIN not set | Attendance check-in fails | Configure in Personal Info → Attendance |
| 4 | Duplicate barcode | Error on save | Check existing badges in HR → Badges |
| 5 | No working hours set | Employee not in attendance reports | Set calendar in Work Information |
| 6 | Archive without reassigning subordinates | Manager error | Reassign subordinates before archiving |

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|---------|
| Cannot create employee | No HR access rights | Request HR Manager to grant access |
| Contract not saving | Missing required fields | Check Contract Type, Start Date, Wage |
| Employee not in org chart | Wrong department | Edit employee, set department |
| Attendance not tracked | No working hours | Configure calendar in Work Information |
| Work email already exists | Email already used | Use different email or archive existing |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md) | Full method chain for developers |
| 📖 Module Reference | [Modules/HR](Modules/hr.md) | Complete field and method reference |
| 📋 Leave Management | [Business/HR/leave-management-guide](Business/HR/leave-management-guide.md) | Managing employee leave |
| 🔧 Patterns | [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) | Workflow design patterns |
