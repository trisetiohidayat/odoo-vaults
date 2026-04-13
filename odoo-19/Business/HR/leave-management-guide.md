---
type: guide
title: "Leave Management Guide"
module: hr_holidays
audience: business-consultant, hr-manager
level: 2
prerequisites:
  - hr_leave_types_configured
  - employees_created
  - allocation_requests_set
  - approval_chain_defined
estimated_time: "~15 minutes"
related_flows:
  - "[Flows/HR/leave-request-flow](leave-request-flow.md)"
  - "[Flows/HR/employee-creation-flow](employee-creation-flow.md)"
source_module: hr_holidays
created: 2026-04-06
version: "1.0"
---

# Leave Management Guide

> **Quick Summary:** Configure leave types, manage employee leave requests, and handle leave approvals in Odoo HR.

**Actor:** HR Manager / Employee (requester)
**Module:** HR Holidays
**Difficulty:** ⭐⭐ Medium

---

## Prerequisites Checklist

- [ ] **Leave types configured** — HR → Configuration → Leave Types
- [ ] **Employees created** — HR → Employees
- [ ] **Allocations set** — HR → Allocation → Create
- [ ] **Approval workflow defined** — Leave validation settings
- [ ] **Calendar integrated** — Time Off calendar visible

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/HR/leave-request-flow](leave-request-flow.md) | Leave request lifecycle |
| 🔀 Technical Flow | [Flows/HR/employee-creation-flow](employee-creation-flow.md) | Employee setup |
| 📖 Module Reference | [Modules/HR](HR.md) | HR module reference |

---

## Use Cases Covered

| # | Use Case | Difficulty |
|---|----------|-----------|
| 1 | Employee requests leave | ⭐ |
| 2 | Manager approves leave | ⭐ |
| 3 | Handle leave conflict (overlapping) | ⭐⭐ |

---

## Use Case 1: Employee Requests Leave

### Scenario
Employee submits a leave request for annual leave.

### Steps

#### Step 1 — Submit Leave Request

Go to: **Time Off → My Leaves → Request Leave**

| Field | Value | Required |
|-------|-------|----------|
| **Leave Type** | Annual Leave | ✅ Yes |
| **Start Date** | Request start date | ✅ Yes |
| **End Date** | Request end date | ✅ Yes |
| **Duration** | Auto-computed | Auto |
| **Description** | Optional reason | No |

> **⚡ System Trigger:** When dates are set, Odoo automatically:
> - Checks available allocation balance
> - Checks for conflicting leaves
> - Shows warning if insufficient balance

#### Step 2 — Submit Request

Click **Submit**.

> **⚡ Side Effects:**
> - Leave request created with state = 'confirm'
> - Manager notified via email/activity
> - Calendar blocked for requested dates

---

## Use Case 2: Manager Approves Leave

### Scenario
Manager reviews and approves employee leave request.

### Steps

#### Step 1 — Review Request

Go to: **Time Off → Allocations / My Team's Leaves**

Open the leave request.

Check:
- Employee name and department
- Leave type and dates
- Available allocation balance
- Coverage status (other team members)

#### Step 2 — Approve or Refuse

| Action | Result |
|--------|--------|
| **Approve** | Leave confirmed, balance deducted |
| **Refuse** | Leave rejected, no balance change |
| **Validate** | Same as approve (for multi-step) |

> **⚡ System Trigger:** When approved:
> - state = 'validate'
> - allocation balance deducted
> - calendar event created
> - employee notified

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Approve without checking balance | Negative allocation balance | Always check balance first |
| 2 | Overlapping leaves approved | Double deduction | Check conflicts in calendar |
| 3 | Leave type not configured | Request cannot be submitted | Configure all types in HR → Configuration |
| 4 | No allocation for employee | Request shows 0 days available | Create allocation for each employee |
| 5 | Wrong leave type selected | Wrong balance deducted | Verify leave type before submitting |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/HR/leave-request-flow](leave-request-flow.md) | Full leave request lifecycle |
| 📖 Module Reference | [Modules/HR](HR.md) | HR module reference |
| 📋 Employee Setup | [Business/HR/quickstart-employee-setup](quickstart-employee-setup.md) | Employee creation |
