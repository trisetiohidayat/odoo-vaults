---
type: guide
title: "Indonesian Tax Guide"
module: l10n_id
submodule: l10n_id_etax
audience: business-consultant, accountant
level: 2
prerequisites:
  - l10n_id_installed
  - chart_of_accounts_loaded
  - tax_groups_configured
  - l10n_id_etax_configured
  - partners_have_npwz_or_nik
estimated_time: "~20 minutes"
related_flows:
  - "[Flows/Account/invoice-creation-flow](odoo-19/Flows/Account/invoice-creation-flow.md)"
  - "[Flows/Purchase/purchase-withholding-flow](odoo-19/Flows/Purchase/purchase-withholding-flow.md)"
  - "[Flows/Account/payment-flow](odoo-19/Flows/Account/payment-flow.md)"
related_guides:
  - "[Business/Account/chart-of-accounts-guide](odoo-19/Business/Account/chart-of-accounts-guide.md)"
source_module: l10n_id
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Indonesian Tax Guide

> **Quick Summary:** This guide covers Indonesia's tax system in Odoo 19, focusing on PPN (Value Added Tax at 11%/12%) and withholding taxes (PPh 21, 22, 23, 26). It explains how Odoo's `l10n_id` and `l10n_id_etax` modules automate tax computation, journal entry splitting, and e-Faktur submission to DJP.

**Actor:** Accountant, Tax Manager, Finance Staff
**Module:** `l10n_id` (Indonesian Localization)
**Use Case:** Configure Indonesian taxes, create tax-compliant invoices, compute withholding, submit e-Faktur
**Difficulty:** ⭐⭐ Medium

---

## Prerequisites Checklist

Before starting, ensure the following are configured. Skipping these will cause errors or missing features.

- [ ] **`l10n_id` module installed** — Enable via Apps → Search "Indonesia" → Install `l10n_id` and `l10n_id_etax`
- [ ] **Indonesian Chart of Accounts loaded** — Settings → Companies → Load Fiscal Data → Select Indonesia (ID: 210)
- [ ] **Tax Groups configured** — PPN (VAT), PPh 21, PPh 22, PPh 23, PPh 26 tax groups must exist in Configuration → Accounting → Tax Groups
- [ ] **l10n_id_etax configured** — Register for e-Faktur with DJP; obtain username/password for Odoo integration
- [ ] **Partners have NPWZ or NIK** — All vendors/sub customers who are Indonesian tax subjects must have `l10n_id_npwz` (for individuals) or NIK/KIMS (for corporate) filled in their contact form
- [ ] **Fiscal Position set** — Company `account_position_id = 'l10n_id.fp_indonesia_invoice'` for automatic tax mapping
- [ ] **Bank account configured in IDR** — All Indonesian transactions must be in Indonesian Rupiah (IDR)

> **Critical:** If the `l10n_id` module is not installed, the Indonesian fiscal position and tax mapping will not be available. All invoices will use the default tax configuration, resulting in incorrect PPN rates.

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Purchase/purchase-withholding-flow](odoo-19/Flows/Purchase/purchase-withholding-flow.md) | Full withholding tax method chain |
| 🔀 Technical Flow | [Flows/Account/edi-invoice-flow](odoo-19/Flows/Account/edi-invoice-flow.md) | Peppol/e-Faktur integration |
| 📖 Module Reference | [Modules/Account](odoo-18/Modules/account.md) | `account.move`, `account.tax` fields |
| 📋 Related Guide | [Business/Account/chart-of-accounts-guide](odoo-19/Business/Account/chart-of-accounts-guide.md) | Indonesian COA structure |
| 🔧 Configuration | [Modules/Account](odoo-18/Modules/account.md) → Tax Configuration | Tax groups, rates, fiscal positions |

---

## Use Cases Covered

This guide covers the following use cases. Jump to the relevant section:

| # | Use Case | Page | Difficulty |
|---|----------|------|-----------|
| 1 | Customer invoice with 12% PPN (VAT) | [#use-case-1-customer-invoice-with-ppn-vat](#use-case-1-customer-invoice-with-ppn-vat.md) | ⭐ |
| 2 | Vendor bill with PPN + PPh 23 withholding | [#use-case-2-vendor-bill-with-ppn-pph-23-withholding](#use-case-2-vendor-bill-with-ppn-pph-23-withholding.md) | ⭐⭐ |
| 3 | PPh 21 employee payment (salary withholding) | [#use-case-3-pph-21-employee-payment-salary-withholding](#use-case-3-pph-21-employee-payment-salary-withholding.md) | ⭐⭐ |
| 4 | Submit e-Faktur to DJP via l10n_id_etax | [#use-case-4-submit-e-faktur-to-djp](#use-case-4-submit-e-faktur-to-djp.md) | ⭐⭐⭐ |

---

## Indonesian Tax System Overview

### Tax Types

Indonesia's main taxes relevant to Odoo transactions:

| Tax Code | Full Name | Rate | Type | Collected From |
|----------|-----------|------|------|---------------|
| **PPN** | Pajak Pertambahan Nilai (VAT) | 11% or 12% | Indirect | Customers (output) / Vendors (input) |
| **PPh 21** | PPh Pasal 21 (Employee) | 5%-35% | Direct | Employee salary |
| **PPh 22** | PPh Pasal 22 (Import/Excise) | 0.25%-10% | Direct | Import, fuel, luxury goods |
| **PPh 23** | PPh Pasal 23 (Service) | 2% (final) / 15% | Direct | Dividends, interest, royalties, services |
| **PPh 26** | PPh Pasal 26 (Foreign) | 20% | Direct | Foreign payment recipients |
| **PPh 4 ayat 2** | PPh Final (Rental/Software) | 10% / 2% | Final | Software license, rental |

### PPN Rate History

| Effective Date | PPN Rate |
|---------------|----------|
| Before 1 April 2022 | 10% |
| 1 April 2022 – 31 March 2024 | 11% |
| 1 April 2024 – 31 Dec 2024 | 12% |
| 1 January 2025 onwards | 12% (standard, with potential increase to 13% planned) |

> **Note:** Odoo's `l10n_id` module automatically uses the correct rate based on the invoice date. Ensure `invoice_date` is set correctly — Odoo does not automatically update tax rates on existing tax definitions.

---

## Tax Configuration Reference

### Tax Groups (Configuration → Accounting → Tax Groups)

| Tax Group | Property Account (Payable) | Property Account (Receivable) | Used For |
|-----------|---------------------------|------------------------------|---------|
| PPN Masukan (VAT In) | `210100` — PPN Masukan | — | Vendor bills (input VAT) |
| PPN Keluaran (VAT Out) | — | `210101` — PPN Keluaran | Customer invoices (output VAT) |
| PPh 21 | `210201` — PPh 21 Payable | — | Employee salary withholding |
| PPh 22 | `210202` — PPh 22 Payable | — | Import duty withholding |
| PPh 23 | `210203` — PPh 23 Payable | — | Service/royalty withholding |
| PPh 26 | `210206` — PPh 26 Payable | — | Foreign payment withholding |

### Tax Definitions (Configuration → Accounting → Taxes)

| Tax Name | Rate | Type | Tax Scope | Tax Group |
|---------|------|------|----------|----------|
| DPT — PPN Barang 12% | 12% | Sale / Purchase | Goods | PPN Masukan/Keluaran |
| DST — PPN Jasa 12% | 12% | Sale / Purchase | Services | PPN Masukan/Keluaran |
| PPh 23 Jasa 15% | 15% | None (withholding) | — | PPh 23 |
| PPh 23 Sewa 10% | 10% | None (withholding) | — | PPh 23 |
| PPh 21 Gaji | 5%-35% | None (withholding) | — | PPh 21 |
| PPh 22 Impor 10% | 10% | None (withholding) | — | PPh 22 |
| PPh 26 Asing 20% | 20% | None (withholding) | — | PPh 26 |

### Fiscal Position: `l10n_id.fp_indonesia_invoice`

When a partner has the Indonesian fiscal position applied, Odoo automatically maps taxes:

| Original Tax | Mapped To | Condition |
|-------------|-----------|-----------|
| PPN Barang (DPT) | PPN Barang 12% (DPT) | Always |
| PPN Jasa (DST) | PPN Jasa 12% (DST) | Always |
| Non-ID tax | No change | Default fallback |

---

## Use Case 1: Customer Invoice with PPN (VAT)

### Scenario

A company invoices a customer for software licensing services (Jasa) worth IDR 50,000,000. PPN (12%) must be added as output tax, and the invoice must be e-Faktur compliant for DJP reporting.

### Method Chain

```
1. account.move.create({
      move_type='out_invoice',
      partner_id=customer_id,
      fiscal_position_id=l10n_id.fp_indonesia_invoice
   })
      │
      ├─► 2. account.move._compute_tax_totals()
      │        └─► 3. account.tax._compute_tax_totals_json()
      │              └─► 4. PPN DST 12% applied: 50_000_000 * 12% = 6_000_000
      │
      ├─► 5. account.move.line created:
      │        ├─► Dr: Accounts Receivable — 56_000_000 (gross + PPN)
      │        └─► Cr: Revenue — 50_000_000
      │              Cr: PPN Keluaran (Output VAT) — 6_000_000
      │
      └─► 6. account.move.action_post()
             └─► 7. l10n_id_etax.account_move → e-Faktur record created
                   └─► 8. Submitted to DJP via l10n_id_etax._submit_efaktur()

Account Impact:
  Dr: piutang usaha (AR)        IDR 56,000,000
  Cr: pendapatan jasa           IDR 50,000,000
  Cr: PPN Keluaran (VAT Payable) IDR  6,000,000
```

### Steps

#### Step 1 — Create Customer Invoice

Navigate to: **Accounting → Customers → Invoices → Create**

Set the following fields:

| Field | Value | Required | Auto-filled |
|-------|-------|----------|-------------|
| **Customer** | Select customer | Yes | — |
| **Invoice Date** | 2026-04-07 | Yes | Today |
| **Fiscal Position** | Indonesia — Invoice | Yes | Auto-set if partner has Indonesian address |
| **Currency** | IDR | Yes | Auto-set if company in ID |

#### Step 2 — Add Invoice Lines

Click **Add a line**:

| Field | Value | Notes |
|-------|-------|-------|
| **Product** | Software License (Jasa) | Service product |
| **Quantity** | 1 | — |
| **Unit Price** | 50,000,000 | IDR |
| **Taxes** | DST — PPN Jasa 12% | Select from dropdown |

> **System Trigger:** When you select the tax, Odoo computes `amount_tax = 50_000_000 * 12% = 6_000_000` and updates the **Tax Totals** section showing: Untaxed: IDR 50,000,000 / Tax: IDR 6,000,000 / **Total: IDR 56,000,000**

> **Fiscal Position Effect:** If the customer has `l10n_id` fiscal position, the 12% rate is confirmed (no further mapping).

#### Step 3 — Review Tax Totals

Scroll to **Other Info → Tax Totals**. Verify:

| Item | Amount |
|------|--------|
| Untaxed Amount | IDR 50,000,000 |
| Tax: PPN Jasa 12% | IDR 6,000,000 |
| **Invoice Total** | **IDR 56,000,000** |

Click **Edit** to adjust if needed.

#### Step 4 — Post and Send

Click **Confirm** (or **Post**).

> **Side Effect:** When the invoice is posted, Odoo:
> - Creates journal entry with PPN Keluaran (Output VAT) as a credit line
> - Creates an `l10n_id_etax.account.move` record for e-Faktur
> - Reduces the Accounts Receivable account by the gross amount

**Expected Results Checklist:**
- [ ] Invoice status changes to **Posted**
- [ ] Journal entry created: Dr AR IDR 56M / Cr Revenue IDR 50M / Cr PPN IDR 6M
- [ ] e-Faktur record available in **Accounting → Vendors → Indonesian E-Faktur**
- [ ] Customer balance updated (AR increased by IDR 56M)
- [ ] Tax report shows PPN Keluaran: IDR 6,000,000

---

## Use Case 2: Vendor Bill with PPN + PPh 23 Withholding

### Scenario

The company receives a vendor bill for consulting services (Jasa Konsultasi) worth IDR 100,000,000 + PPN 12% = IDR 112,000,000 gross. PPh 23 withholding at 15% applies to the service amount (not the PPN), resulting in a net payment of IDR 99,000,000 to the vendor.

**Math:**
- Gross service: IDR 100,000,000
- PPN (12%): IDR 12,000,000
- Gross bill: IDR 112,000,000
- PPh 23 Withholding (15% × 100,000,000): IDR 15,000,000
- **Net payable to vendor**: IDR 112,000,000 - IDR 15,000,000 = **IDR 97,000,000**

### Method Chain

```
1. account.move.create({
      move_type='in_invoice',
      partner_id=vendor_id,
      invoice_line_ids: [{
         product_id: consulting_service,
         price_unit: 100_000_000,
         tax_ids: [(6,0,[DST_12pct_id])],
         withholding_tax_id: PPh_23_15pct_id
      }]
   })
      │
      ├─► 2. account.move._compute_tax_totals()
      │        ├─► 3. PPN 12% computed: 100_000_000 * 12% = 12_000_000
      │        └─► 4. withhold.tax.compute(PPh_23, 100_000_000)
      │              └─► 5. Withholding = 100_000_000 * 15% = 15_000_000
      │
      ├─► 6. account.move.line created (split journal entry):
      │        ├─► Dr: Beban Konsultasi (Expense) — 100_000_000
      │        ├─► Dr: PPN Masukan (VAT Input) — 12_000_000
      │        ├─► Cr: Utang Vendor (Vendor Payable) — 97_000_000
      │        └─► Cr: PPh 23 Payable (Withholding) — 15_000_000
      │
      └─► 7. account.move.action_post()
             └─► 8. Posted journal entry locked

Account Impact:
  Dr: beban konsultasi      IDR 100,000,000  (expense)
  Dr: PPN Masukan           IDR  12,000,000  (input VAT — creditable)
  Cr: utang vendor          IDR  97,000,000  (net payable to vendor)
  Cr: PPh 23 Payable        IDR  15,000,000  (tax withheld — remit to DJP)
```

### Steps

#### Step 1 — Create Vendor Bill

Navigate to: **Accounting → Vendors → Bills → Create**

| Field | Value | Notes |
|-------|-------|-------|
| **Vendor** | Select Indonesian vendor | Must have NPWZ or NIK |
| **Bill Date** | 2026-04-07 | — |
| **Fiscal Position** | Indonesia — Invoice | Auto-set from partner |

#### Step 2 — Add Invoice Line with Both Taxes

Add line:

| Field | Value | Notes |
|-------|-------|-------|
| **Product** | Jasa Konsultasi | Service product |
| **Quantity** | 1 | — |
| **Unit Price** | 100,000,000 | — |
| **Taxes** | DST — PPN Jasa 12% | Click → select |
| **Withholding Tax** | PPh 23 — Jasa 15% | Separate dropdown below taxes |

> **System Trigger:** The **Withholding Tax** field is below the **Taxes** field. It is a **separate field** — withholding is not a tax line, it is a deduction. The tax totals section will now show:
>
> | Item | Amount |
> |------|--------|
> | Untaxed Amount | IDR 100,000,000 |
> | Tax: PPN Jasa 12% | IDR 12,000,000 |
> | **Withholding: PPh 23** | **-IDR 15,000,000** |
> | **Total** | **IDR 97,000,000** |

#### Step 3 — Review Split Journal Entry

Click **View Entry** (before posting) to preview the journal entry:

| Account | Debit (IDR) | Credit (IDR) |
|---------|------------|------------|
| Beban Konsultasi (Expense) | 100,000,000 | — |
| PPN Masukan (VAT Input) | 12,000,000 | — |
| Utang Vendor (Vendor Payable) | — | 97,000,000 |
| PPh 23 Payable (Withholding) | — | 15,000,000 |
| **Total** | **112,000,000** | **112,000,000** |

#### Step 4 — Post Bill

Click **Confirm**.

**Expected Results Checklist:**
- [ ] Bill status → Posted
- [ ] Vendor payable: IDR 97,000,000 (not the gross IDR 112,000,000)
- [ ] PPh 23 Payable: IDR 15,000,000 (separate line)
- [ ] PPN Masukan: IDR 12,000,000 (input VAT — creditable in next VAT return)
- [ ] e-Faktur record created (for PPN)

#### Step 5 — Pay Vendor (Net Amount Only)

Navigate to: **Accounting → Vendors → Bills** → Open bill → **Register Payment**

| Field | Value |
|-------|-------|
| **Amount** | 97,000,000 (auto-filled, net only) |
| **Journal** | Bank IDR |
| **Payment Date** | 2026-04-15 |

> **Critical:** The payment amount is **97,000,000** (net), not 112,000,000. The PPh 23 withholding is remitted separately to DJP.

#### Step 6 — Remit PPh 23 to DJP

Navigate to: **Accounting → Vendors → Bills** → Create a **Manual Entry** or use **Payment** with:
- Payment to: **DJP (tax authority)** (create as a contact)
- Amount: **15,000,000**
- Memo: "Pelunasan PPh Pasal 23 — {vendor_name} — {invoice_number}"

This creates the journal entry:
```
Dr: PPh 23 Payable  —  15,000,000
Cr: Bank            —  15,000,000
```

---

## Use Case 3: PPh 21 Employee Payment (Salary Withholding)

### Scenario

An employee receives a monthly gross salary of IDR 25,000,000. PPh 21 is withheld by the employer based on a progressive tax table. The employee is a permanent employee (Karyawan Tetap) with the status "TK/0" (Tidak Kawin, no dependents). The net salary paid to the employee is the gross salary minus the PPh 21 withholding.

**Simplified PPh 21 calculation (Odoo uses DJP tables):**
- Gross salary: IDR 25,000,000
- PTKP TK/0 (annual): IDR 54,000,000 → monthly: IDR 4,500,000
- Taxable income (monthly): IDR 25,000,000 - IDR 4,500,000 = IDR 20,500,000
- Annual taxable: IDR 20,500,000 × 12 = IDR 246,000,000
- PPh 21 (annual, progressive):
  - IDR 0 - 60M → 5% → IDR 3,000,000
  - IDR 60M - 240M → 15% → IDR 27,000,000
  - IDR 240M - 246M → 25% → IDR 1,500,000
  - **Total annual: IDR 31,500,000 → Monthly: IDR 2,625,000**
- Net salary: IDR 25,000,000 - IDR 2,625,000 = **IDR 22,375,000**

### Configuration Required

Before processing PPh 21 in Odoo, configure:

| Setting | Path | Value |
|---------|------|-------|
| PTKP Code | HR → Configuration → PTKP Codes | TK/0 — IDR 4,500,000/month |
| PPh 21 Tax Table | Accounting → Taxes → l10n_id PPh 21 | DJP 2024 table |
| Salary Rule | HR → Payroll → Salary Rules | Rule: Gross Salary → PPh 21 deduction |
| Cost Center | Accounting → Analytic → Accounts | Payroll Cost Center |

### Steps

#### Step 1 — Process Payroll Run

Navigate to: **HR → Payroll → Payslips → Create**

| Field | Value |
|-------|-------|
| **Employee** | [Employee Name] |
| **Payslip Run** | April 2026 |
| **Contract** | PKWT / Permanent (Karayawan Tetap) |
| **Gross Salary** | 25,000,000 |

The salary rule for PPh 21 automatically computes the withholding based on:
- Employee's `l10n_id_npwp` (NPWP number — required)
- PTKP status from employee record
- DJP PPh 21 tax table

> **System Trigger:** Odoo's PPh 21 salary rule calls `l10n_id.payslip._compute_pph21()` which:
> 1. Reads the DJP PTKP table for the employee's PTKP status
> 2. Applies the progressive rate to the taxable salary
> 3. Returns `amount_withholding = 2,625,000`
> 4. Creates an `account.move.line` Dr: Beban Gaji / Cr: PPh 21 Payable

#### Step 2 — Approve and Post Payroll Journal Entry

Click **Validate Payslip** → **Create Journal Entry**.

Odoo creates:

| Account | Debit (IDR) | Credit (IDR) |
|---------|------------|------------|
| Beban Gaji (Salary Expense) | 25,000,000 | — |
| PPh 21 Payable (Withholding) | — | 2,625,000 |
| Hutang Gaji Karyawan (Salary Payable) | — | 22,375,000 |

#### Step 3 — Pay Net Salary to Employee

Navigate to: **Accounting → Accounting → Payments → Register Payment**
- Amount: IDR 22,375,000 (net salary — no PPh 21)
- Pay to: Employee (as partner, linked to employee record)

#### Step 4 — Remit PPh 21 Monthly (SPT Masa)

Navigate to: **Accounting → Reporting → Tax Report → Indonesia → SPT Masa PPh Pasal 21**

| Field | Value |
|-------|-------|
| **Period** | April 2026 |
| **Tax Type** | PPh Pasal 21 |

Submit to DJP via **l10n_id_etax._submit_spt_masa()**.

---

## Use Case 4: Submit E-Faktur to DJP

### Scenario

After posting customer and vendor invoices with PPN, the accountant must review, validate, and submit the e-Faktur records to DJP through Odoo's `l10n_id_etax` module integration.

### Prerequisites

- [ ] Registered e-Faktur user on DJP DJP Online (https://djponline.pajak.go.id)
- [ ] `l10n_id_etax` configured with DJP credentials in Odoo: **Settings → Accounting → Indonesian E-Faktur**
- [ ] Valid NPWP of both company and counterparty
- [ ] All invoices posted with correct fiscal position

### Method Chain

```
1. l10n_id_etax.account.move._prepare_efaktur_data()
      ├─► 2. Extract: invoice_number, date, partner_npwz, partner_address
      ├─► 3. Extract: total_dpp, total_ppn, total_ppn_bm
      └─► 4. Generate: FK (Faktur Pajak) or FP (Faktur Pabean) record

5. l10n_id_etax.account.move._submit_efaktur()
      ├─► 6. POST to DJP API: /v1/efaktur/invoice
      └─► 7. Receive: approval_code (11-digit),泗
             └─► 8. Update account.move: l10n_efaktur_status = 'approved'

9. l10n_id_etax.account.move._download_efaktur_pdf()
      └─► 10. Download PDF (official DJP format with QR code)
```

### Steps

#### Step 1 — Review Pending E-Faktur

Navigate to: **Accounting → Vendors → Indonesian E-Faktur → Invoice Documents**

Filter by: Status = "Ready to Submit"

Review each record:
- NPWP/NIK of counterparty is filled
- DPP (Taxable Base) and PPN amounts match the invoice
- Tax type (FP or FK) is correct

#### Step 2 — Submit to DJP

Select records → Click **Submit to DJP**.

> **System Behavior:** Odoo calls the DJP API. Approval codes are returned within minutes to 24 hours (async). The status changes from "Ready" to "Submitted" to "Approved" (with approval code).

#### Step 3 — Download E-Faktur PDF

Once approved, click **Download PDF** to get the official DJP e-Faktur document with QR code, which serves as a valid tax invoice in Indonesia.

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Wrong PPN rate (using 10% instead of 12%) | E-Faktur rejected by DJP | Set invoice date after April 2024; verify tax definition rate |
| 2 | Missing NPWZ on vendor | PPh 23 journal entry fails | Always fill `l10n_id_npwz` on Indonesian partners |
| 3 | Paying gross amount (including withholding) | Vendor overpaid; reconciliation mismatch | Pay only the **net** amount shown in "Total" |
| 4 | Forgetting to remit withholding to DJP | Tax audit finding | Set monthly reminder for PPh 21/23/26 SPT Masa submission |
| 5 | Wrong fiscal position on invoice | Tax mapping not applied | Ensure partner has Indonesia fiscal position or set manually |
| 6 | PPN calculated on amount already including PPN | Double tax | Base amount must be exclusive of PPN; Odoo handles this if set correctly |
| 7 | Using service tax code for goods | E-Faktur rejected | DPT (Barang) for goods; DST (Jasa) for services |
| 8 | Missing e-Faktur approval code on invoice | Not valid tax invoice | Always submit via l10n_id_etax before sending invoice to customer |

---

## Configuration Deep Dive

### Related Configuration Paths

| Configuration | Menu Path | Controls |
|--------------|-----------|----------|
| Fiscal Position | Accounting → Configuration → Fiscal Positions | Tax mapping for Indonesia |
| Tax Groups | Accounting → Configuration → Tax Groups | Payable/receivable accounts per tax type |
| Taxes | Accounting → Configuration → Taxes | PPN, PPh 21/22/23/26 rates and scopes |
| Partner NPWZ | Contacts → [Partner] → Indonesian Info | NPWZ/NPWP or NIK for tax identity |
| e-Faktur Settings | Settings → Accounting → Indonesian E-Faktur | DJP API credentials |
| PTKP Codes | HR → Configuration → PTKP Codes | PPh 21 taxable income thresholds |

### Advanced Options

| Option | Field Name | Default | Effect When Enabled |
|--------|-----------|---------|-------------------|
| Auto-submit e-Faktur | `l10n_id_auto_submit` | False | E-Faktur submitted automatically on invoice post |
| PPN 0% for export | `l10n_id_is_ekspor` | False | Exports are 0% PPN; mapped to LKPP |
| PPh 21 auto-calculate | `l10n_id_auto_pph21` | True | Payroll rule computes PPh 21 from DJP table |
| Validate NPWZ on post | `l10n_id_validate_npwz` | True | Blocks posting if vendor missing NPWZ |
| Use NIK instead of NPWZ | `l10n_id_use_nik` | False | Allows 16-digit NIK for individuals below PTKP threshold |

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|---------|
| PPN not appearing on invoice | Fiscal position not set on partner | Set Indonesia fiscal position in partner form |
| Withholding tax field not visible | `l10n_id` module not installed | Install `l10n_id` first |
| PPh 23 journal entry not split | Withholding amount computed as zero | Check: is vendor NPWZ filled? Is rate > 0? |
| E-Faktur status stuck on "Submitted" | DJP API timeout | Retry from E-Faktur list view |
| Wrong PPN rate (10% instead of 12%) | Invoice date before April 2024 | Update invoice date or create new invoice |
| Cannot submit to DJP: "NPWP invalid" | Counterparty NPWZ format wrong | Format: 2 digits + dot + 3 digits + dot + 3 digits + dot + 1 digit + dash + 3 digits + dot + 3 digits (e.g., 01.234.567.8-901.000) |
| PPN Masukan not creditable | Wrong tax group | Ensure PPN Masukan has property_tax_receivable_account_id set |
| Payroll PPh 21 wrong amount | PTKP status wrong on employee | Check HR → Employee → Indonesian Info → PTKP Status |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Purchase/purchase-withholding-flow](odoo-19/Flows/Purchase/purchase-withholding-flow.md) | Full PPh 21/22/23/26 method chain |
| 🔀 Technical Flow | [Flows/Account/edi-invoice-flow](odoo-19/Flows/Account/edi-invoice-flow.md) | e-Faktur + Peppol integration |
| 🔀 Technical Flow | [Flows/Stock/stock-valuation-flow](odoo-19/Flows/Stock/stock-valuation-flow.md) | Landed costs with PPN treatment |
| 📖 Module Reference | [Modules/Account](odoo-18/Modules/account.md) | `account.move`, `account.tax` fields |
| 📋 Related Guide | [Business/Account/chart-of-accounts-guide](odoo-19/Business/Account/chart-of-accounts-guide.md) | Indonesian COA setup |
| 🔧 Patterns | [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) | Tax computation and fiscal positions |
| 🛠️ Snippets | [Snippets/Model Snippets](odoo-18/Snippets/Model Snippets.md) | Code for custom tax computation |
