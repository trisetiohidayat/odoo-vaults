# Research-Log/backlog.md

# Backlog — Topics Pending Documentation

## Pending Topics

### Account Module (Odoo 15)

- [ ] **Bank Statement Reconciliation** (`account.bank.statement`) - belum di-detail
- [ ] **Fiscal Position** (`account.fiscal.position`) - fiscal position mapping
- [ ] **Payment Terms** (`account.payment.term`) - detail installment computation
- [ ] **Analytic Accounting** - `account.analytic.account`, `account.analytic.line`, default rules
- [ ] **Currency Management** (`res.currency`) - exchange rates, conversion
- [ ] **Company Fiscal Year Setup** - lock dates, period close
- [ ] **Chart of Accounts Template** (`chart_template`) - how templates work
- [ ] **Account Groups** (`account.group`) - parent grouping
- [ ] **Digest Reports** - scheduled email reports
- [ ] **Mail Thread Integration** - chatter on account moves
- [ ] **Activity Scheduling** - follow-up activities for overdue invoices
- [ ] **Audit Trail / Hash Integrity** - `restrict_mode_hash_table` mechanism
- [ ] **Asset Accounting** (`account.asset`) - separate module but related
- [ ] **Tax Exigibility / CABA** - lebih dalam lagi edge cases

### Cross-Module Flows (Odoo 15)

- [ ] **Purchase Flow** - PO → Receipt → Bill → Payment
- [ ] **Inventory Valuation Flow** - Stock move → Valuation → COGS
- [ ] **Expense Reimbursement Flow** - HR expense → Vendor bill → Payment

### Localization (Odoo 15)

- [ ] **l10n_id** - Indonesia localization (PPN, PPh)
- [ ] Country-specific tax reports

---

## Resolved in This Run (2026-04-13)

- [x] **Tax Grid System** - lengkap dengan contoh dan flow
- [x] **AccountMove fields** - `tax_tag_ids`, `tax_repartition_line_id`, `analytic_account_id`
- [x] **Tax Repartition Lines** - structure dan tag assignment
- [x] **Partial/Full Reconciliation** - models dan flow
- [x] **Cash Basis Accounting** - CABA dengan tax grid
- [x] **AccountReconcileModel** - rule types dan matching
- [x] **Carryover Mechanism** - tax report line carryover

## Notes

- Source: `/Users/tri-mac/project/roedl/odoo15.0-roedl/odoo/addons/account/models/`
- Semua model Utama sudah terdokumentasi di [Modules/Account](Account.md)
- Tax Grid sudah ada dedicated guide di [Business/Account/tax-grid-guide](tax-grid-guide.md)
- Flow sudah ada di [Flows/Account/*](Flows/Account/*.md) dan [Flows/Cross-Module/*](Flows/Cross-Module/*.md)
