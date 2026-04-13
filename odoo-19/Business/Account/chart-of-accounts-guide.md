---
type: guide
title: "Chart of Accounts Guide"
module: account
audience: business-consultant, accountant
level: 2
prerequisites:
  - company_configured
  - fiscal_year_opened
  - localization_applied
estimated_time: "~30 minutes"
related_flows:
  - "[Flows/Account/invoice-creation-flow](invoice-creation-flow.md)"
  - "[Flows/Account/invoice-post-flow](invoice-post-flow.md)"
  - "[Flows/Account/payment-flow](payment-flow.md)"
source_module: account
created: 2026-04-06
version: "1.0"
---

# Chart of Accounts Guide

> **Quick Summary:** Configure the chart of accounts, account types, and fiscal positions for accounting in Odoo.

**Actor:** Accountant / Finance Manager
**Module:** Accounting
**Difficulty:** ⭐⭐ Medium

---

## Prerequisites Checklist

- [ ] **Company configured** — Settings → General → Companies
- [ ] **Fiscal year opened** — Accounting → Configuration → Fiscal Years
- [ ] **Localization applied** — Use country-specific localization (l10n_*) for auto-setup
- [ ] **Chart of accounts loaded** — Accounting → Configuration → Charts of Accounts

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Account/invoice-creation-flow](invoice-creation-flow.md) | Invoice creation |
| 🔀 Technical Flow | [Flows/Account/invoice-post-flow](invoice-post-flow.md) | Invoice posting |
| 🔀 Technical Flow | [Flows/Account/payment-flow](payment-flow.md) | Payment registration |
| 📖 Module Reference | [Modules/Account](Account.md) | Complete model reference |

---

## Use Cases Covered

| # | Use Case | Difficulty |
|---|----------|-----------|
| 1 | Load Standard Chart of Accounts | ⭐ |
| 2 | Create Custom Account | ⭐⭐ |
| 3 | Configure Fiscal Position | ⭐⭐ |

---

## Use Case 1: Load Standard Chart of Accounts

### Scenario
Apply a standard country-specific chart of accounts using Odoo's localization.

### Steps

#### Step 1 — Install Localization

Go to: **Settings → Apps**

Search and install: `l10n_[country_code]` (e.g., l10n_id for Indonesia, l10n_us for USA)

> **⚡ System Trigger:** Localization module installs:
> - Chart of accounts
> - Tax templates
> - Fiscal positions
> - Account sequences

#### Step 2 — Apply Chart of Accounts

Go to: **Accounting → Configuration → Charts of Accounts**

Click: **Setup your company's accounting** / **Load**

Select:
- **Country**: [Your country]
- **Chart of Accounts**: Standard / Revised / Custom
- **Chart Template**: [Default selection]

> **⚡ Side Effects:**
> - Accounts created in the system
> - Taxes created from templates
> - Fiscal positions created
> - Opening entries configuration available

#### Step 3 — Configure Bank Accounts

Go to: **Accounting → Configuration → Journals**

For each bank account:
| Field | Value |
|-------|-------|
| **Name** | Bank account name |
| **Type** | Bank |
| **Account Receivable** | Select receivable account |
| **Account Payable** | Select payable account |

---

## Use Case 2: Create Custom Account

### Scenario
Create a custom account for a specific expense category.

### Steps

#### Step 1 — Create Account

Go to: **Accounting → Configuration → Accounts → Create**

| Field | Value | Required |
|-------|-------|----------|
| **Code** | 6-digit code | ✅ Yes |
| **Name** | Account name | ✅ Yes |
| **Account Type** | Expense | ✅ Yes |
| **Tags** | Optional | No |

> **⚡ Important:** Account Type determines:
> - Where account appears (Balance Sheet / P&L)
> - Debit/Credit behavior
> - Allow reconciliation setting

#### Step 2 — Configure Account Type

| Account Type | Nature | Example |
|-------------|--------|---------|
| Receivable | Asset | Customer invoices |
| Payable | Liability | Vendor bills |
| Revenue | Income | Sales accounts |
| Expense | Cost | Purchases, utilities |
| Bank | Asset | Bank accounts |
| Cash | Asset | Petty cash |
| Equity | Capital | Retained earnings |

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Wrong account type | Account not in correct report | Always select correct type |
| 2 | Duplicate account codes | Accounting errors | Use unique codes |
| 3 | Posting to inactive account | Error on save | Always verify account is active |
| 4 | Wrong reconciliation account | Unbalanced entries | Select correct receivable/payable |
| 5 | Forgetting fiscal position | Wrong taxes on invoices | Always set for foreign vendors |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Invoice Creation | [Flows/Account/invoice-creation-flow](invoice-creation-flow.md) | Invoice creation |
| 🔀 Invoice Posting | [Flows/Account/invoice-post-flow](invoice-post-flow.md) | Post invoice |
| 🔀 Payments | [Flows/Account/payment-flow](payment-flow.md) | Register payment |
| 📖 Module Reference | [Modules/Account](Account.md) | Complete model reference |
