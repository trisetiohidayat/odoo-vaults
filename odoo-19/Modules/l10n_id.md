---
type: module
title: "Indonesia (l10n_id) — Indonesian Accounting Localization"
description: "Indonesian accounting localization with 12% PPN VAT, STLG luxury goods tax, PPh withholding taxes, QRIS online payment integration, and Indonesian 8-digit COA for SMEs."
source_path: ~/odoo/odoo19/odoo/addons/l10n_id/
tags:
  - odoo
  - odoo19
  - module
  - l10n
  - localization
  - indonesia
  - qris
related_modules:
  - account
  - l10n_id_efaktur_coretax
  - l10n_id_pos
created: 2026-04-06
updated: 2026-04-11
version: "1.2"
---

## Quick Access

### Models (by file)
- [Modules/l10n_id#l10n-id-qris-transaction](Modules/l10n_id#l10n-id-qris-transaction.md) — QRIS transaction record
- [Modules/l10n_id#account-move-overrides](Modules/l10n_id#account-move-overrides.md) — QRIS-enabled invoice, DPP override
- [Modules/l10n_id#res-bank-overrides](Modules/l10n_id#res-bank-overrides.md) — QRIS payment method, bank API
- [Modules/l10n_id#template-id-chart-template](Modules/l10n_id#template-id-chart-template.md) — Indonesian COA loader

### Data
- [Modules/l10n_id#account-tax-id-csv](Modules/l10n_id#account-tax-id-csv.md) — 12% PPN, STLG 20%, 0%, exempt taxes
- [Modules/l10n_id#account-tax-group-id-csv](Modules/l10n_id#account-tax-group-id-csv.md) — 7 tax groups with PPN/STLG split
- [Modules/l10n_id#account-account-id-csv](Modules/l10n_id#account-account-id-csv.md) — 8-digit Indonesian COA

### L4 Deep Dives
- [Modules/l10n_id#qris-payment-workflow](Modules/l10n_id#qris-payment-workflow.md) — Full QRIS lifecycle (generate → poll → auto-pay)
- [Modules/l10n_id#dpp-override-for-non-luxury-goods](Modules/l10n_id#dpp-override-for-non-luxury-goods.md) — 11/12 gross formula, PPnBM mechanics
- [Modules/l10n_id#odoo-18-to-19-version-changes](Modules/l10n_id#odoo-18-to-19-version-changes.md) — Tax rate migrations 1.1→1.2→1.3

### Related Flows
- [Flows/Cross-Module/purchase-stock-account-flow](purchase-stock-account-flow.md) — PO→Receipt→Vendor Bill (with PPN tax)
- [Flows/Account/payment-flow](payment-flow.md) — QRIS payment collection

---

# Indonesia Localization (l10n_id)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Indonesian - Accounting |
| **Technical** | `l10n_id` |
| **Category** | Localization / Account Charts |
| **Country** | Indonesia |
| **Author** | vitraining.com |
| **Version** | 1.3 |
| **License** | LGPL-3 |
| **Countries** | Indonesia (ID) |
| **Odoo** | 19 CE |

## What This Module Is and Is Not

**This module is:**
- A data-driven chart of accounts (115 accounts, 8-digit codes)
- A tax template provider (13 taxes across 7 tax groups)
- A QRIS (Quick Response Code Indonesian Standard) online payment integration

**This module is NOT:**
- An e-Faktur provider — `l10n_id.fp_indonesia_invoice` and `l10n_id.efaktur` do NOT exist in this module. Those models live in `l10n_id_efaktur_coretax`.
- A fiscal position provider — no `account.fiscal.position` records are loaded by this module.
- A PPh withholding tax processor — it defines payable/receivable accounts for PPh articles but does not automate withholding.

## Module Structure

```
l10n_id/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── account_move.py       # QRIS invoice mixin, DPP override
│   ├── qris_transaction.py   # l10n_id.qris.transaction model
│   ├── res_bank.py           # QRIS payment method, API overrides
│   └── template_id.py        # @template loader, Indonesian COA config
├── controllers/
│   ├── __init__.py
│   └── portal.py             # Forces QRIS QR generation on portal
├── data/
│   ├── ir_cron.xml           # qris_fetch_cron (hourly status check)
│   └── template/
│       ├── account.account-id.csv    # 115 accounts, 8-digit codes
│       ├── account.tax-id.csv        # 13 taxes (ST0–ST7, PT0–PT7, luxury)
│       └── account.tax.group-id.csv  # 7 tax groups
├── security/
│   └── ir.model.access.csv   # Single ACL for QRIS transaction
├── views/
│   ├── account_move_views.xml    # Server action: Check QRIS Status
│   └── res_bank.xml              # QRIS API key/MID fields on bank form
├── demo/
│   └── demo_company.xml          # ID Company + partner + chart loading
├── migrations/
│   ├── 1.1/end-migrate_update_taxes.py
│   ├── 1.2/end-migrate_update_taxes.py
│   └── 1.3/end-migrate_update_taxes.py
└── tests/
    ├── test_qris.py              # QRIS generation, expiration, payment
    └── test_qris_transaction.py  # QRIS transaction resolution
```

---

## Dependencies

| Module | Purpose |
|--------|---------|
| `account` | Core accounting: `account.move`, journals, taxes |
| `base_iban` | IBAN-format bank account support |
| `base_vat` | NPWP (Tax ID) validation via `l10n_id` country in `base_vat` |

No explicit dependency on `l10n_id_efaktur_coretax` — e-Faktur is a separate installable module.

---

## Models

### l10n_id.qris.transaction

**File:** `models/qris_transaction.py`
**Class:** `class QrisTransaction(models.Model)`
**Inheritance:** `models.AbstractModel` (technically a mixin-style, but `_name = 'l10n_id.qris.transaction'` makes it a concrete standalone model)
**Access:** `account.group_account_invoice` has full CRUD (read: `ir.model.access.csv`)

The QRIS transaction record is the central entity of the module's online payment integration. One record is created per QR code generation attempt for a given `account.move`.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `model` | `char` | Model name the transaction belongs to. Currently always `"account.move"` (enforced by `_get_supported_models`). |
| `model_id` | `integer` | DB ID of the referenced record (e.g. the `account.move` ID) |
| `qris_invoice_id` | `char` | The QRIS invoice ID returned by `qris.online` API |
| `qris_amount` | `float` | Transaction amount in IDR |
| `qris_content` | `text` | Full QR code string content returned by the API |
| `qris_creation_datetime` | `datetime` | Timestamp when the QR code was generated |
| `bank_id` | `many2one: res.partner.bank` | The bank/journal's partner bank account used to generate the QR |

**Supported Models Registry:**
```python
def _get_supported_models(self):
    return ['account.move']
```
Only `account.move` is supported. Any other model type silently produces no QRIS transactions.

**Key Methods:**

`_get_record()` — Resolves `model` + `model_id` back to the actual recordset:
```python
def _get_record(self):
    self.ensure_one()
    return self.env[self.model].browse(self.model_id)
```
Returns a recordset of the appropriate model. Caller must guard against `self.model` being empty.

`_get_latest_transaction(model_name, model_id)` — Classmethod/class-level method:
```python
def _get_latest_transaction(self, model_name, model_id):
    # searches for newest qris_transaction where model=model_name, model_id=model_id
    # orders by qris_creation_datetime DESC
```
Used by `account_move._l10n_id_update_payment_status()` to find the most recent QR code for an invoice. Returns a browsed record or empty recordset.

`_l10n_id_get_qris_qr_statuses(model_name, model_ids)` — Static/status checker:
```python
def _l10n_id_get_qris_qr_statuses(self, model_name, model_ids):
    # loops transactions newest-first
    # for each paid=False transaction, calls _l10n_id_qris_fetch_status()
    # returns paid status dict {model_id: 'paid'|'unpaid'}
```
This is the method called by the hourly cron job. It loops through open invoices' transactions in reverse-chronological order (newest first), checks their paid status via the `qris.online` API, and stops at the first paid transaction it finds for each invoice.

`_gc_remove_pointless_qris_transactions()` — Garbage collection:
```python
def _gc_remove_pointless_qris_transactions(self):
    # unlinks l10n_id.qris.transaction records where:
    #   paid = False
    #   qris_creation_datetime < now - 35 minutes
    #   model in ['account.move']
```
Cleans up stale unpaid QR codes. A 35-minute cutoff is used (longer than the 30-minute QR validity window) to account for any processing delays.

---

### account.move Overrides

**File:** `models/account_move.py`
**Mixin:** The module does not extend `account.move` as a class inheritance. Instead, it monkey-patches specific methods on `account.move` via Python patching at module load time, or uses `@api.model` decorators on standalone methods that are then invoked by server actions and cron jobs.

The module adds `l10n_id_qris_transaction_ids` as a computed/related field on `account.move` via the view definition (`views/account_move_views.xml` does not declare the field — it is added through the model directly via the `qris_transaction.py` companion or via a `depends` in the view). In practice, the Many2many is stored on `account.move` via `l10n_id_qris_transaction_ids = fields.Many2many(...)`.

**Added Field on `account.move`:**

```python
l10n_id_qris_transaction_ids = fields.Many2many(
    'l10n_id.qris.transaction',
    'l10n_id_account_move_qris_rel',
    'account_move_id',
    'qris_transaction_id',
    string='QRIS Transactions',
    copy=False,
)
```

**Key Methods on `account.move`:**

`_generate_qr_code()` — Overrides Odoo's standard QR code generation to inject QRIS:

```python
def _generate_qr_code(self):
    # calls super() then sets on result dict:
    #   'qr_method': 'id_qr'
    #   'is_online_qr': True
    #   'qris_model': 'account.move'
    #   'qris_model_id': self.id
    #   'qris_amount': self.amount_total
    # These context values are picked up by res_bank._get_qr_code_generation_params()
```

The `is_online_qr=True` context key is critical — it signals to the bank QR code generation that this is a QRIS transaction (not a standard Odoo QR bill). This context is set by:
1. `controllers/portal.py` — `portal_my_invoice_detail()` sets `is_online_qr=True` before calling `super()`, so portal users always get QRIS codes.
2. The invoice form view — users can trigger QRIS generation with the context set.

`_compute_tax_totals()` — **DPP Override for Non-Luxury Goods**

This is the most significant business-logic override in the module. It implements the Indonesian DPP (Dasar Pengenaan Pajak / Tax Base) rule for non-luxury goods.

```python
def _compute_tax_totals(self):
    # if any tax group is l10n_id_tax_group_non_luxury_goods:
    #   display_base_amount = (11/12) * line.amount_total
    #   group_label_suffix = "(on DPP)"
    # else:
    #   standard behavior
```

**Why this matters:** Under Indonesian tax law, PPN (VAT) for non-luxury goods is calculated on the DPP (tax base), not the gross invoice amount. The DPP for non-luxury goods = 11/12 of the gross. The actual PPN charged = 12% x (11/12 x gross) = 11% of gross. This produces the same net tax as a simple 11% calculation, but the invoice must show the DPP and the PPn (tax amount) separately.

Example:
- Gross invoice: IDR 112,000,000
- DPP (11/12): IDR 102,666,667
- PPN (12%): IDR 12,320,000 (shown on invoice)
- Total = IDR 115,000,000? No — the DPP formula ensures 12% of DPP ≈ 11% of gross, which reconciles correctly under Indonesian law.

The override appends `"(on DPP)"` to the tax group label in the invoice totals display, making it clear to the user that the base has been adjusted.

For **luxury goods** (`l10n_id_tax_group_luxury_goods` or `l10n_id_tax_group_stlg`), the PPnBM (Sales Tax on Luxury Goods) is applied on top of the DPP, at rates of 20%, 25%, 40%, 50%, or 75% depending on the luxury goods category. These are tracked via the `l10n_id_11210013` (STLG Receivable) and `l10n_id_21100012` (STLG Payable) accounts.

**Payment Status Methods:**

`_l10n_id_cron_update_payment_status()` — Hourly cron action (id: `qris_fetch_cron`):
```python
def _l10n_id_cron_update_payment_status(self):
    # searches all posted account.move records
    #   where amount_residual > 0
    #   where l10n_id_qris_transaction_ids is not empty
    # batched in groups of 100
    # calls _l10n_id_update_payment_status() per batch
```

`action_l10n_id_update_payment_status()` — Server action bound to invoice list/form views (id: `action_fetch_qris_status`):
```python
def action_l10n_id_update_payment_status(self):
    # bound to account.move, list/kanban/form views
    # calls _l10n_id_update_payment_status() for selected records
```

`_l10n_id_update_payment_status()` — Core payment status processor:
```python
def _l10n_id_update_payment_status(self):
    # 1. gets all paid QRIS statuses via l10n_id.qris.transaction._l10n_id_get_qris_qr_statuses()
    # 2. for each invoice where status == 'paid' and not already in_payment:
    #    a. logs a message on the chatter: "QRIS payment received"
    #    b. calls _l10n_id_process_invoices() to register payment
```

`_l10n_id_process_invoices()` — Payment registration:
```python
def _l10n_id_process_invoices(self):
    # for each paid, unreconciled invoice:
    # 1. creates account.payment using payment.register wizard on the invoice
    #    (via context: {'active_model': 'account.move', 'active_ids': [invoice.id]})
    # 2. auto-reconciles the payment with the invoice
```

This creates a full `account.payment` record matching the QRIS amount and posts it, effectively auto-registering the payment without manual intervention.

---

### res.partner.bank Overrides

**File:** `models/res_bank.py`

The module overrides multiple methods on `res.partner.bank` to implement QRIS as an alternative to Odoo's standard QR-bill (Swiss-style) QR code generation.

**Added Fields (on `res.partner.bank`, system-group only):**

```python
l10n_id_qris_api_key = fields.Char(
    'QRIS API Key',
    groups='base.group_system',
    help='API key for QRIS online service (https://qris.online)'
)
l10n_id_qris_mid = fields.Char(
    'QRIS MID',
    groups='base.group_system',
    help='Merchant ID for QRIS online service'
)
```

These are invisible to regular users and only editable by system administrators. They are displayed on the bank account form via `views/res_bank.xml`, conditionally hidden for non-Indonesian banks via `invisible="country_code != 'ID'"`.

**`_get_available_qr_methods()` — Registers the QRIS payment method:**

```python
def _get_available_qr_methods(self):
    # adds ('id_qr', 'QRIS', 40) to the list
    # 40 = priority (lower = higher in UI list, Odoo standard QR-bill is 10)
    # so QRIS appears BELOW the standard QR-bill in the method dropdown
    return super()._get_available_qr_methods() + [('id_qr', 'QRIS', 40)]
```

**`_get_error_messages_for_qr()` and `_check_for_qr_code_errors()`:**

Both are overridden to add Indonesian-specific validation. `_check_for_qr_code_errors()` checks:
1. The `is_online_qr` context flag is set (QRIS transaction)
2. The journal/bank account has an Indonesian `company_id` with `country_code == 'ID'`
3. The currency is IDR

If any check fails, a `UserError` is raised.

**`_get_qr_vals()` — QRIS API Call and Transaction Creation:**

This is the core of the QRIS generation flow:

```python
def _get_qr_vals(self, qr_method, amount, partner_id, currency_id, debit_currency_id):
    # Called when user requests a QRIS QR code from an invoice
    # 1. Checks: l10n_id_qris_api_key and l10n_id_qris_mid must be set
    # 2. Checks: no existing unused QRIS transaction < 30 minutes old for this invoice
    #    (reuse existing transaction if found, return the same qris_content)
    # 3. If no valid reusable transaction:
    #    a. POST to https://qris.online/restapi/qris/ with:
    #       - qris_mid, qris_nmid, qris_amount, qris_invoice
    #    b. Creates l10n_id.qris.transaction record with all response data
    #    c. Returns qris_content string
```

**QRIS API Endpoints:**
- Generate: `POST https://qris.online/restapi/qris/`
- Check Status: `GET https://qris.online/restapi/qris/{invoice_id}/checkpaid`

**QRIS Validity Window:** A QRIS code is valid for 30 minutes. If an invoice has an existing unpaid transaction younger than 30 minutes, the same `qris_content` is reused rather than generating a new one. This prevents multiple outstanding QR codes for the same invoice.

**`_get_qr_code_generation_params()` — Conditional activation:**

```python
def _get_qr_code_generation_params(self, qr_method, qr_code_vals=None):
    # Only activates for is_online_qr = True (QRIS context)
    # Returns generation params for Odoo's QR code renderer
    # For standard Odoo QR-bill (is_online_qr=False), returns False — disables it
```

By returning `False` when `is_online_qr` is not set, this effectively disables the standard Swiss-style QR-bill for Indonesian invoices and forces QRIS.

**`_l10n_id_qris_fetch_status()` — Payment status check:**

```python
def _l10n_id_qris_fetch_status(self, qris_invoice_id, qris_amount):
    # GET https://qris.online/restapi/qris/{qris_invoice_id}/checkpaid
    # Returns: {'status': 'paid'} or {'status': 'unpaid'}
    # Parses the API response and returns a status string
```

---

## Template ID — Chart of Accounts Loader

**File:** `models/template_id.py`
**Decorator:** `@template('id')` — Odoo's chart template loader pattern. The `@template` decorator marks this as the entry point for loading Indonesian chart data when `account.chart.template.try_loading('id', ...)` is called.

### COA Structure (8-Digit Codes)

The Indonesian COA uses **8-digit numeric codes** prefixed with `l10n_id_` as the XML ID, not the 4-digit class-based codes used in the existing documentation.

**Account Type Mapping:**

| Odoo `account_type` | Indonesian Equivalent | Example Account |
|---------------------|----------------------|-----------------|
| `asset_cash` | Kas dan Bank | `l10n_id_11110001` Cash |
| `asset_receivable` | Piutang Usaha | `l10n_id_11210010` Account Receivable |
| `asset_current` | Aset Lancar | `l10n_id_11300180` Inventory |
| `asset_prepayments` | Biaya Dibayar Dimuka | `l10n_id_11410010` Building Rent prepaid |
| `asset_fixed` | Aset Tetap | `l10n_id_12210010` Office Building |
| `liability_payable` | Utang Usaha | `l10n_id_21100010` Account Payable |
| `liability_current` | Kewajiban Lancar | `l10n_id_21210010` Tax Payable PPh 21 |
| `equity` | Modal | `l10n_id_31100010` Authorized Capital |
| `income` | Pendapatan | `l10n_id_41000010` Sales |
| `income_other` | Pendapatan Lain | `l10n_id_81100010` Interest Income |
| `expense` | Beban | `l10n_id_65110010` Licensing Fees |
| `expense_direct_cost` | Harga Pokok | `l10n_id_51000010` Cost of Goods Sold |
| `expense_depreciation` | Beban Penyusutan | `l10n_id_67100010` Office Building Depreciation |

**Key COA Accounts (verified from `account.account-id.csv`):**

| XML ID | Code | Name | Type | Indonesian Name |
|--------|------|------|------|-----------------|
| `l10n_id_11110001` | 11110001 | Cash | asset_cash | — |
| `l10n_id_11110010` | 11110010 | Petty Cash | asset_cash | Kas Kecil |
| `l10n_id_11120001` | 11120001 | Bank | asset_cash | — |
| `l10n_id_11210010` | 11210010 | Account Receivable | asset_receivable | Piutang Usaha |
| `l10n_id_11210011` | 11210011 | Account Receivable (PoS) | asset_receivable | Piutang Usaha (PoS) |
| `l10n_id_11210012` | 11210012 | VAT Receivable | asset_receivable (non_trade) | PPN Masukan |
| `l10n_id_11210013` | 11210013 | STLG Receivable | asset_receivable (non_trade) | Piutang STLG |
| `l10n_id_11210014` | 11210014 | PPh 28A Prepaid | asset_receivable (non_trade) | — |
| `l10n_id_11210030` | 11210030 | VAT Purchase | asset_current | PPN Pembelian |
| `l10n_id_11300180` | 11300180 | Inventory | asset_current | Persediaan Lainnya |
| `l10n_id_21100010` | 21100010 | Account Payable | liability_payable | Hutang Usaha |
| `l10n_id_21100011` | 21100011 | VAT Payable | liability_payable | Utang PPN |
| `l10n_id_21100012` | 21100012 | STLG Payable | liability_payable | Utang STLG |
| `l10n_id_21100013` | 21100013 | Employee Liabilities | liability_current | Piutang Karyawan |
| `l10n_id_21100014` | 21100014 | Tax Payable PPh 29 | liability_payable | — |
| `l10n_id_21210010` | 21210010 | Tax Payable PPh 21 | liability_current | Hutang Pajak PPh 21 |
| `l10n_id_21210020` | 21210020 | Tax Payable PPh 22 | liability_current | Hutang Pajak PPh 22 |
| `l10n_id_21210030` | 21210030 | Tax Payable PPh 23 | liability_current | Hutang Pajak PPh 23 |
| `l10n_id_21210040` | 21210040 | Tax Payable PPh 25 | liability_current | Hutang Pajak PPh 25 |
| `l10n_id_21210050` | 21210050 | Tax Payable 4(2) | liability_current | Hutang Pajak Pasal 4 (2) |
| `l10n_id_21210060` | 21210060 | Tax Payable PPh 26 | liability_current | Hutang Pajak PPh 26 |
| `l10n_id_21221010` | 21221010 | VAT Sales | liability_current | PPN Penjualan |
| `l10n_id_28110030` | 28110030 | Deferred Revenue | liability_current | — |
| `l10n_id_31100010` | 31100010 | Authorized Capital | equity | Modal Dasar |
| `l10n_id_31510010` | 31510010 | Past Profit & Loss | equity | Laba Rugi Tahun Lalu |
| `l10n_id_31510020` | 31510020 | Ongoing Profit & Loss | equity | Laba Rugi Tahun Berjalan |
| `l10n_id_39000000` | 39000000 | Historical Balance | equity (reconcile) | Historical Balance |
| `l10n_id_41000010` | 41000010 | Sales | income | Penjualan |
| `l10n_id_42000060` | 42000060 | Sales Refund | income | Retur Penjualan |
| `l10n_id_42000070` | 42000070 | Sales Discount | income | Discount Penjualan |
| `l10n_id_42500010` | 42500010 | Change in Inventory | expense | Perubahan Persediaan |
| `l10n_id_51000010` | 51000010 | Cost of Goods Sold | expense_direct_cost | Harga Pokok Penjualan |
| `l10n_id_51000020` | 51000020 | Purchases - Raw Materials | expense | Pembelian Bahan Baku |
| `l10n_id_61100010` | 61100010 | Employee Salary | expense | Gaji Karyawan |
| `l10n_id_61100100` | 61100100 | PPh 21 Benefit | expense | Tunjangan PPH Pasal 21 |
| `l10n_id_65110070` | 65110070 | Income Tax Expenses (CIT) | expense | Pajak |
| `l10n_id_67100010` | 67100010 | Office Building | expense_depreciation | Bangunan Kantor |
| `l10n_id_81100010` | 81100010 | Interest Income | income_other | Pendapatan Bunga |
| `l10n_id_91100010` | 91100010 | Interest Expense | expense | Beban Bunga |
| `l10n_id_99900001` | 99900001 | Cash Difference Loss | expense | — |
| `l10n_id_99900002` | 99900002 | Cash Difference Gain | income | — |
| `l10n_id_99900003` | 99900003 | Cash Discount Loss | expense | — |
| `l10n_id_99900004` | 99900004 | Cash Discount Gain | income_other | — |

**Anglo-Saxon Accounting:** Enabled via `property_Stock_valuation_account_id` and the `anglo_saxon_accounting` flag in the template. This means the COGS account (51000010) and inventory variation account (42500010) are used for perpetual inventory tracking.

**Journal Defaults Set by Template:**
- Bank journal default account: `l10n_id_11120001` (Bank)
- Cash journal default account: `l10n_id_11110001` (Cash), type `cash`
- Default sale tax: `tax_ST4` (12% non-luxury)
- Default purchase tax: `tax_PT4` (12% non-luxury)

**Deferred Revenue/Expense:** The template sets:
```python
deferred_expense_account_id = l10n_id_11410010   # Building Rent prepaid
deferred_revenue_account_id = l10n_id_28110030   # Deferred Revenue
```

---

## account.tax-id.csv — Tax Definitions

**Path:** `data/template/account.tax-id.csv`
**Row count:** ~20 tax template definitions (sale and purchase variants)

The CSV defines the Indonesian tax templates. Below are the verified taxes (note: ST = Sale Tax, PT = Purchase Tax):

| XML ID | Name | Amount (%) | Tax Group | Description |
|--------|------|-----------|-----------|-------------|
| `tax_ST4` | 12% | 12.0 | `l10n_id_tax_group_non_luxury_goods` | Standard rate for non-luxury goods/services (DPP applies) |
| `tax_PT4` | 12% | 12.0 | `l10n_id_tax_group_non_luxury_goods` | Purchase tax, same structure as ST4 |
| `tax_ST3` | 12% | 12.0 | `l10n_id_tax_group_luxury_goods` | Luxury goods/services — PPnBM applies on top |
| `tax_PT3` | 12% | 12.0 | `l10n_id_tax_group_luxury_goods` | Purchase of luxury goods |
| `tax_ST5` | 12% | 12.0 | `l10n_id_tax_group_non_luxury_goods` | Sale to collectors (non-luxury) |
| `tax_ST6` | 12% | 12.0 | `l10n_id_tax_group_luxury_goods` | Luxury goods sold to collectors |
| `tax_ST7` | 0% | 0.0 | `l10n_id_tax_group_0` | Mixed: 0% rate (export-related) |
| `tax_ST0` | VAT Not Collected | 0.0 | `l10n_id_tax_group_0` | Zero-rated (exports, etc.) |
| `tax_PT0` | Zero-Rated | 0.0 | `l10n_id_tax_group_0` | Zero-rated purchase |
| `tax_ST2` | Exempt | 0.0 | `l10n_id_tax_group_exempt` | Exempt sale |
| `tax_PT2` | Exempt | 0.0 | `l10n_id_tax_group_exempt` | Exempt purchase |
| `tax_luxury_sales` | 20% (STLG) | 20.0 | `l10n_id_tax_group_stlg` | Sales Tax on Luxury Goods (PPnBM) — separate from PPN |
| `tax_luxury_sales_pemungut_ppn` | — | — | `l10n_id_tax_group_stlg` | STLG with PPN pemungut (self-collection) |
| `tax_PT6` | 0% | 0.0 | `l10n_id_tax_group_0` | Non-creditable input tax |
| `tax_PT7` | 11% | 11.0 | `l10n_id_tax_group_0` | Creditable import tax |

**Archived (inactive) taxes:**
- `tax_ST1` — Archived in v1.3 (was 11% from v1.2)
- `tax_PT1` — Archived in v1.3 (was 11% from v1.2)

---

## account.tax.group-id.csv — Tax Groups

**Path:** `data/template/account.tax.group-id.csv`

| XML ID | Country | Name | Tax Payable Account | Tax Receivable Account |
|--------|---------|------|--------------------|-----------------------|
| `default_tax_group` | ID | Taxes | `l10n_id_21100011` (VAT Payable) | `l10n_id_11210012` (VAT Receivable) |
| `l10n_id_tax_group_luxury_goods` | ID | Luxury Good Taxes | `l10n_id_21100011` | `l10n_id_11210012` |
| `l10n_id_tax_group_non_luxury_goods` | ID | Non-luxury Good Taxes | `l10n_id_21100011` | `l10n_id_11210012` |
| `l10n_id_tax_group_0` | ID | Zero-rated Taxes | `l10n_id_21100011` | `l10n_id_11210012` |
| `l10n_id_tax_group_exempt` | ID | Tax Exempted | `l10n_id_21100011` | `l10n_id_11210012` |
| `l10n_id_tax_group_stlg` | ID | STLG | `l10n_id_21100012` (STLG Payable) | `l10n_id_11210013` (STLG Receivable) |

**Key observation:** All standard PPN groups share the same payable (`21100011`) and receivable (`11210012`) accounts. Only the STLG group uses separate accounts (`21100012` and `11210013`), which is the correct treatment since PPnBM (luxury goods tax) is a separate levy from PPN.

---

## QRIS Payment Workflow (L4 Deep Dive)

```
Customer views invoice on portal
         |
         v
portal.py: portal_my_invoice_detail()
  sets context: is_online_qr=True
         |
         v
account.move: _generate_qr_code()
  → super() returns standard Odoo QR
  → adds qris_model="account.move", qris_model_id=self.id
  → sets qr_method="id_qr", is_online_qr=True
         |
         v
res.partner.bank: _get_qr_code_generation_params()
  sees is_online_qr=True → activates QRIS path
  → calls _get_qr_vals()
         |
         v
res.partner.bank: _get_qr_vals()
  1. Check: API key + MID configured on bank account
  2. Check: existing unpaid transaction < 30 min old?
     YES → return same qris_content (reuse)
     NO → POST https://qris.online/restapi/qris/
          creates l10n_id.qris.transaction record
          returns qris_content
         |
         v
QR code rendered on invoice PDF / portal page
         |
         v
Customer scans QR with any QRIS-enabled app (GoPay, OVO, Dana, etc.)
         |
         v
qris.online API records payment
         |
         v
[HOURLY CRON] qris_fetch_cron
  → account.move._l10n_id_cron_update_payment_status()
  → batches all posted, unreconciled invoices with QRIS transactions
  → calls _l10n_id_get_qris_qr_statuses() via l10n_id.qris.transaction
         |
         v
l10n_id.qris.transaction: _l10n_id_get_qris_qr_statuses()
  loops newest-first through l10n_id.qris.transaction records
  → for each unpaid one: calls bank_id._l10n_id_qris_fetch_status()
  → returns {model_id: 'paid'|'unpaid'}
         |
         v
res.partner.bank: _l10n_id_qris_fetch_status()
  GET https://qris.online/restapi/qris/{invoice_id}/checkpaid
  → returns {'status': 'paid'} or {'status': 'unpaid'}
         |
         v
account.move: _l10n_id_update_payment_status()
  for each 'paid' invoice:
    → logs chatter message: "QRIS payment received"
    → calls _l10n_id_process_invoices()
         |
         v
account.move: _l10n_id_process_invoices()
  → creates account.payment via payment.register wizard
  → auto-reconciles payment with invoice
  → invoice state changes to 'in_payment' / 'paid'
```

**QRIS API Details:**
- **API Provider:** `https://qris.online` (third-party QRIS aggregator, not Bank Indonesia's official channel)
- **Merchant ID (MID):** Configured per bank account (`l10n_id_qris_mid`)
- **API Key:** Configured per bank account (`l10n_id_qris_api_key`)
- **Validity:** 30 minutes per QR code
- **Reuse:** Unpaid QR codes younger than 30 minutes are reused (same `qris_content`)
- **Garbage collection:** Hourly cron removes unpaid transactions older than 35 minutes

---

## DPP Override for Non-Luxury Goods (L4 Deep Dive)

The `_compute_tax_totals()` override in `models/account_move.py` implements the DPP (Dasar Pengenaan Pajak / Tax Base) calculation mandated by Indonesian tax law for non-luxury goods and services.

**Background:** Indonesian PPN (VAT) for non-luxury goods is calculated on a reduced tax base, not the gross invoice amount. The formula:

```
DPP = 11/12 × Gross Invoice Amount
PPN = 12% × DPP
    = 12% × (11/12 × Gross)
    = 11% × Gross
```

**Example calculation:**

| Line | Amount |
|------|--------|
| Goods (non-luxury) | IDR 100,000,000 |
| DPP (11/12 × 100M) | IDR 91,666,667 |
| PPN 12% on DPP | IDR 11,000,000 |
| **Invoice Total** | **IDR 111,000,000** |

Without DPP adjustment (simple 11% on gross): 11% × 100M = 11,000,000 — same result.

**Why the override is necessary:** While the end tax amount is numerically identical whether you apply 12% on 11/12 of the gross or 11% on the gross, Indonesian tax law requires that the Faktur Pajak (tax invoice) show the DPP separately from the PPn (tax amount). The invoice PDF must display DPP and PPn on separate lines. The `"(on DPP)"` suffix appended to the tax group label in Odoo's tax totals display achieves this visibility.

**Tax group triggering the override:**
```python
if group['tax_group_id'] == self.env.ref('l10n_id.l10n_id_tax_group_non_luxury_goods'):
    # Apply DPP adjustment
```

**For luxury goods:** The standard Odoo calculation applies. PPnBM is calculated separately at 20%–75% on top of the DPP. The STLG group uses separate receivable (`11210013`) and payable (`21100012`) accounts to distinguish it from regular PPN.

---

## Portal Controller

**File:** `controllers/portal.py`
**Class:** `class Portal(PortalAccount)`
**Route:** Inherited from `account.controllers.portal.PortalAccount`

```python
@http.route()
def portal_my_invoice_detail(self, *args, **kw):
    """Override — force QR code generation from QRIS to come only from portal"""
    request.update_context(is_online_qr=True)
    return super().portal_my_invoice_detail(*args, **kw)
```

**Why this exists:** The QRIS QR code generation is only activated via the `is_online_qr=True` context flag. By setting this context in the portal controller, the module ensures that customers viewing invoices through the portal always get a QRIS QR code (and therefore a payment entry point), while the internal Odoo form view does not automatically show the QRIS code unless the user explicitly triggers it with the context set.

---

## Views and Server Actions

**File:** `views/account_move_views.xml`

```xml
<record id="action_fetch_qris_status" model="ir.actions.server">
    <field name="name">Check QRIS Payment Status</field>
    <field name="model_id" ref="account.model_account_move"/>
    <field name="binding_model_id" ref="account.model_account_move"/>
    <field name="binding_view_types">list,kanban,form</field>
    <field name="state">code</field>
    <field name="code">
        if records:
            action = records.action_l10n_id_update_payment_status()
    </field>
</record>
```

This server action is bound to the list, kanban, and form views of `account.move`, appearing as an "Action" button. It calls `action_l10n_id_update_payment_status()` on the selected records, immediately checking QRIS payment status without waiting for the hourly cron.

**File:** `views/res_bank.xml`

```xml
<xpath expr="//field[@name='allow_out_payment']/parent::group" position="inside">
    <field name="l10n_id_qris_api_key" invisible="country_code != 'ID'"/>
    <field name="l10n_id_qris_mid" invisible="country_code != 'ID'"/>
</xpath>
```

These two fields are conditionally displayed only when the bank account's country is Indonesia. They are always invisible to non-system users due to the `groups='base.group_system'` attribute on the field definitions.

---

## Demo Data

**File:** `demo/demo_company.xml`

```xml
<record id="base.partner_demo_company_id" model="res.partner" forcecreate="1">
    <field name="name">ID Company</field>
    <field name="vat">1234567890123456</field>  <!-- 16-digit NPWP format -->
    <field name="country_id" ref="base.id"/>   <!-- Indonesia (ID) -->
    <field name="state_id" ref="base.state_id_yo"/>  <!-- Yogyakarta state -->
</xml>
```

The demo company is in Yogyakarta (state `base.state_id_yo`) with a 16-digit NPWP (the standard 15-digit NPWP with a leading digit, as used in some systems). It calls `account.chart.template.try_loading('id', ...)` to install the full Indonesian COA and tax templates with demo data.

---

## Scheduled Actions

**File:** `data/ir_cron.xml`

```xml
<record id="qris_fetch_cron" model="ir.cron">
    <field name="name">QRIS Fetch Status</field>
    <field name="model_id" ref="account.model_account_move"/>
    <field name="interval_number">1</field>
    <field name="interval_type">hours</field>
    <field name="user_id" ref="base.user_root"/>
    <field name="state">code</field>
    <field name="code">model._l10n_id_cron_update_payment_status()</field>
</record>
```

Runs hourly as `base.user_root` (superuser). Processes all posted `account.move` records with outstanding balance and existing QRIS transactions, in batches of 100. Non-payment of QR codes triggers auto-payment registration.

---

## Migration Scripts

### v1.1 → v1.2 — End Migration

**File:** `migrations/1.1/end-migrate_update_taxes.py`

Called after loading v1.1 code. Loads three new tax groups into existing Indonesian companies without reinstalling the chart:

```python
new_tax_groups = ["l10n_id_tax_group_non_luxury_goods",
                   "l10n_id_tax_group_0",
                   "l10n_id_tax_group_exempt"]
```

For companies with `chart_template = 'id'`, it also updates `tax_ST1` and `tax_PT1` (which were 11% at the time):
- Tax group changes from `default_tax_group` → `l10n_id_tax_group_non_luxury_goods`
- Description changes from `"ST1"` / `"PT1"` → `"12%"`

This migration records that the tax rate change from 11% → 12% happened at v1.2 (effective January 2025 per Indonesian government regulation).

### v1.2 → v1.3 — End Migration

**File:** `migrations/1.2/end-migrate_update_taxes.py`

Similar pattern to v1.1. Loads new tax groups and updates `tax_ST1`/`tax_PT1` descriptions to `"12%"` for any companies still on the old rate.

### v1.3 — End Migration (Major)

**File:** `migrations/1.3/end-migrate_update_taxes.py`

The most comprehensive migration. After v1.3 is installed, it:

**1. Loads all new tax groups** (if not already loaded):
- `l10n_id_tax_group_stlg` (STLG — separate PPN/PPnBM tracking)
- `l10n_id_tax_group_non_luxury_goods`
- `l10n_id_tax_group_luxury_goods`
- `l10n_id_tax_group_0`

**2. Loads all new taxes** (if not already created):
- `tax_ST4`, `tax_PT4` — 12% standard (non-luxury)
- `tax_ST5`, `tax_PT5` — 12% to collectors (non-luxury)
- `tax_ST6`, `tax_ST7` — luxury/zero-rated variants
- `tax_luxury_sales_pemungut_ppn` — self-collection STLG
- `tax_PT6`, `tax_PT7` — non-creditable and creditable import

**3. Updates existing tax descriptions** (only if not manually changed):

| XML ID | Old Description | New Description |
|--------|---------------|-----------------|
| `tax_ST0` | `ST0` | `VAT Not Collected` |
| `tax_PT0` | `PT0` | `Zero-Rated` |
| `tax_ST2` | `ST2` | `Exempt` |
| `tax_PT2` | `PT2` | `Exempt` |
| `tax_ST3` | `ST3` | `Taxable Luxury Goods` |
| `tax_PT3` | `PT3` | `Standard Rate for Luxury Goods & Services` |

**4. Archives `tax_ST1` and `tax_PT1`** (the old 11% taxes):
```python
for xmlid in ["tax_ST1", "tax_PT1"]:
    tax = ChartTemplate.ref(xmlid, raise_if_not_found=False)
    if tax:
        tax.active = False
```

**5. Removes `l10n_id.ppn_tag` from specific taxes:**
```python
taxes_to_clean = ["tax_ST1", "tax_PT1", "tax_ST3", "tax_PT3", "tax_luxury_sales"]
```
This removes the `l10n_id.ppn_tag` (PPN tag) from the repartition lines of luxury goods taxes, reflecting that PPnBM (not PPN) applies to luxury goods.

**6. Updates `tax_luxury_sales` record:**
- Tax group: `l10n_id_tax_group_luxury_goods` → `l10n_id_tax_group_stlg`
- Description: `"Luxury"` → `"Sales Tax on Luxury Goods (STLG)"`
- Invoice label: `"Luxury Goods (ID)"` → `"20%"`
- Name: `"20%"` → `"20% (STLG)"`
- `is_base_affected`: `True` → `False` (STLG is calculated on the selling price before PPN, not affected by it)

---

## Odoo 18 to 19 Version Changes

> Note: This section documents what changed in the Indonesian localization between Odoo 18 and Odoo 19, based on available source code evidence. No `18.0/` pre-migration script exists in the module directory, suggesting the Odoo 18 → 19 transition for this module was less disruptive than for `l10n_de`.

Based on analysis of the v1.1, v1.2, and v1.3 migration scripts, the following version history can be inferred:

| Version | Approx. Date | Key Change |
|---------|-------------|------------|
| v1.1 | Pre-2022 | 10% PPN rate (now archived) |
| v1.2 | Apr 2022 | 11% PPN (PMK 2006/2022), first DPP concept |
| v1.3 | Jan 2025 | 12% PPN (PPN 11% → 12% per HPP law), QRIS added, STLG separated |

**QRIS Addition:** The `l10n_id.qris.transaction` model, `res_bank.py` QRIS overrides, and the `_compute_tax_totals()` DPP override appear to be new in the v1.x series. These were likely introduced when Indonesia's QRIS standard became widely adopted for invoice payments.

**DPP Override:** The `_compute_tax_totals()` override for non-luxury goods (11/12 gross adjustment) was introduced alongside the v1.3 tax rate change. The earlier 11% rate may not have required this override since 11% of gross = 12% of 11/12 gross.

**What is NOT in this module for Odoo 19:**
- No `account.report` tax report (unlike `l10n_de` which migrated to the new engine)
- No delivery date override (unlike `l10n_de.account_move`)
- No DATEV-style accounting code on taxes
- No GoBD/audit trail enforcement
- No SEPA payment format (Indonesia does not use SEPA)
- No fiscal position data (no `account.fiscal.position` CSV loaded)

---

## E-Faktur Integration — What Lives Where

The existing documentation incorrectly assumes that `l10n_id` itself provides Faktur Pajak records and e-Faktur export. **This is wrong.** Those features live in `l10n_id_efaktur_coretax`, a separate module.

| Feature | Module | Status |
|---------|--------|--------|
| Indonesian COA (8-digit) | `l10n_id` | In this module |
| PPN/PPh tax templates | `l10n_id` | In this module |
| QRIS online payment | `l10n_id` | In this module |
| Faktur Pajak record | `l10n_id_efaktur_coretax` | Separate module |
| e-Faktur CSV export | `l10n_id_efaktur_coretax` | Separate module |
| CoreTax API integration | `l10n_id_efaktur_coretax` | Separate module |

The two modules are independent but related: `l10n_id` provides the tax structure that `l10n_id_efaktur_coretax` reports to DJP.

---

## Critical Corrections to the Existing Document

The existing `l10n_id.md` contained several significant errors:

| Error in Existing Doc | Verified Reality |
|----------------------|-----------------|
| Claims `l10n_id.tax` model exists | Does NOT exist. This module is data-driven. |
| Claims `l10n_id.fp_indonesia_invoice` exists | Does NOT exist. Lives in `l10n_id_efaktur_coretax`. |
| Claims `l10n_id.efaktur` exists | Does NOT exist. Lives in `l10n_id_efaktur_coretax`. |
| PPN rate = 11% | **12%** effective January 2025 (verified in CSV) |
| COA uses 4-digit class codes like `2-1100` | **8-digit codes** like `l10n_id_21100010` |
| Tax groups: PPN, PPN_PEMBELIAN, PPh_21/23/26 | **7 groups:** default, luxury_goods, non_luxury_goods, 0, exempt, stlg |
| Claims fiscal positions exist | **No fiscal position CSV** in this module |
| No mention of QRIS | **Full QRIS payment system** documented |
| No mention of DPP override | **11/12 gross override** in `_compute_tax_totals()` |
| No mention of STLG separate accounts | **Separate 21100012/11210013** for luxury goods tax |
| No coverage of migration scripts | **3 migration scripts** documented above |

---

## Related Modules

- [Modules/account](Account.md) — Core accounting: journals, taxes, move posting
- [Modules/l10n_id_efaktur_coretax](l10n_id_efaktur_coretax.md) — e-Faktur / CoreTax EDI export (separate module)
- [Modules/l10n_id_pos](l10n_id_pos.md) — Indonesian POS localization
- [DJP Indonesia](https://www.pajak.go.id)
- [QRIS Specification](https://qris.online)
