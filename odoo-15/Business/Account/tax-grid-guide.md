# Business/Account/tax-grid-guide.md

# Tax Grid Guide — Odoo 15

## Apa Itu Tax Grid?

Tax Grid adalah sistem di Odoo yang memetakan **tax amounts** dari setiap invoice/journal entry ke **baris-baris di Tax Report**. Ini memungkinkan reporting pajak yang akurat karena setiap transaksi pajak langsung terhubung ke report line yang sesuai.

**Analogi**: Tax Grid seperti spreadsheet pivot table — setiap transaksi pajak adalah data point, dan tax grid me-aggregate data tersebut ke baris-baris report berdasarkan tags.

---

## Komponen Tax Grid

### 1. Tax Tags (`account.account.tag`)

```python
# account.account.tag
class AccountAccountTag(models.Model):
    _name = 'account.account.tag'

    name = fields.Char('Tag Name', required=True)
    applicability = fields.Selection([
        ('accounts', 'Accounts'),
        ('taxes', 'Taxes'),       # ← Bagian dari tax grid
        ('products', 'Products'),
    ])
    tax_negate = fields.Boolean('Negate Tax Balance')
    country_id = fields.Many2one('res.country')
```

**Karakteristik Tax Tag**:
- `applicability = 'taxes'` → tag ini bagian dari tax grid
- `tax_negate = True` → nilai akan di-negate saat di-sum
- `country_id` → tag hanya berlaku untuk negara tertentu

### 2. Tax Report Lines (`account.tax.report.line`)

```python
# account.tax.report.line
class AccountTaxReportLine(models.Model):
    _name = "account.tax.report.line"

    name = fields.Char('Line Name')
    tag_name = fields.Char('Tag Name')
    report_id = fields.Many2one('account.tax.report')
    tag_ids = fields.Many2many('account.account.tag')
```

### 3. Tax Report (`account.tax.report`)

```python
# account.tax.report
class AccountTaxReport(models.Model):
    _name = "account.tax.report"

    name = fields.Char('Report Name')
    country_id = fields.Many2one('res.country')
    line_ids = fields.One2many('account.tax.report.line', 'report_id')
```

---

## Cara Kerja Tax Grid

### Alur Data

```
┌──────────────────────────────────────────────────────────────┐
│                        INVOICE POSTED                         │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    account.move.line (tax line)              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ tax_line_id = account.tax (PPN 11%)                     │ │
│  │ tax_tag_ids = [account.account.tag(+tax_11_output)]     │ │
│  │ balance = 11,000,000 (credit)                          │ │
│  │ account_id = 2200 - VAT Payable                        │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                   TAX REPORT COMPUTATION                     │
│                                                              │
│  SELECT                                                    │
│    tag_id,                                                 │
│    SUM(debit) - SUM(credit) AS balance                     │
│  FROM account_move_line                                    │
│  WHERE tax_tag_ids IN (...)                                │
│  GROUP BY tag_id                                           │
│                                                              │
│  Result:                                                    │
│  ┌──────────────────────┬────────────┐                     │
│  │ Tax Report Line      │ Balance    │                     │
│  ├──────────────────────┼────────────┤                     │
│  │ +tax_11_output       │ 11,000,000 │ ← from invoice      │
│  │ -tax_11_input        │  5,000,000 │ ← from bill         │
│  │ NET PPN (OUTPUT-IN)  │  6,000,000 │ ← formula          │
│  └──────────────────────┴────────────┘                     │
└──────────────────────────────────────────────────────────────┘
```

### Tag Naming Convention

Setiap tax report line dengan `tag_name` otomatis membuat **dua tag**:

| tag_name | Tag Positif | Tag Negatif | Penggunaan |
|----------|-------------|------------|------------|
| `tax_11_output` | `+tax_11_output` | `-tax_11_output` | Invoice/AR |
| `tax_11_input` | `+tax_11_input` | `-tax_11_input` | Bill/AP |
| `tax_0_exempt` | `+tax_0_exempt` | `-tax_0_exempt` | Exempt sales |

**Positive Tags (+)**: Menandakan tax yang harus dibayar (payable)
**Negative Tags (-)**: Menandakan tax yang bisa dikreditkan (receivable/creditable)

---

## Tax Repartition Lines & Tags

Setiap `account.tax` memiliki **repartition lines** yang menentukan ke mana tax posted dan tag apa yang digunakan.

```python
# account.tax fields
class AccountTax(models.Model):
    _name = 'account.tax'

    invoice_repartition_line_ids = fields.One2many(
        'account.tax.repartition.line',
        'invoice_tax_id',  # FK back to self
        string='Invoice Distribution',
    )
    refund_repartition_line_ids = fields.One2many(
        'account.tax.repartition.line',
        'refund_tax_id',
        string='Refund Distribution',
    )

# account.tax.repartition.line
class AccountTaxRepartitionLine(models.Model):
    _name = 'account.tax.repartition.line'

    tax_id = fields.Many2one('account.tax')
    factor_percent = fields.Float('Percentage', default=100)
    account_id = fields.Many2one('account.account', 'Account')
    tag_ids = fields.Many2many('account.account.tag')
```

### Contoh: PPN 11%

```
account.tax: PPN 11% (Indonesia VAT)

invoice_repartition_line_ids:
┌────┬──────────────┬──────────────┬────────────────────────┐
│ #  │ Type         │ Factor       │ Tag                    │
├────┼──────────────┼──────────────┼────────────────────────┤
│ 1  │ Base         │ 100%         │ +tax_11_output        │
│ 2  │ Tax          │ 100%         │ +tax_11_output        │
└────┴──────────────┴──────────────┴────────────────────────┘

refund_repartition_line_ids:
┌────┬──────────────┬──────────────┬────────────────────────┐
│ #  │ Type         │ Factor       │ Tag                    │
├────┼──────────────┼──────────────┼────────────────────────┤
│ 1  │ Base         │ 100%         │ -tax_11_output        │
│ 2  │ Tax          │ 100%         │ -tax_11_output        │
└────┴──────────────┴──────────────┴────────────────────────┘
```

### Special Cases: Multi-Akun

Dalam beberapa kasus (misalnya PPnBM atau split tax), tax bisa dipecah ke beberapa akun:

```
account.tax: PPN 11% dengan split

invoice_repartition_line_ids:
┌────┬──────────────┬──────────────┬────────────────────────┐
│ #  │ Type         │ Factor       │ Tag                    │
├────┼──────────────┼──────────────┼────────────────────────┤
│ 1  │ Base         │ 100%         │ +tax_11_output        │
│ 2  │ Tax          │ 80%          │ +tax_11_output        │
│ 3  │ Tax          │ 20%          │ +tax_11_other         │
└────┴──────────────┴──────────────┴────────────────────────┘
```

---

## Membuat Tax Grid Report

### Step 1: Buat Tax Report

```
Menu: Accounting → Reporting → Tax Reports → Reports
Action: Create
```

```
account.tax.report:
    name: "Indonesian Tax Report"
    country_id: Indonesia (ID)
```

### Step 2: Buat Report Lines

```
account.tax.report.line:
    name: "PPN Keluaran 11%"
    report_id: Indonesian Tax Report
    tag_name: tax_11_output
    → Otomatis membuat tag +tax_11_output dan -tax_11_output

account.tax.report.line:
    name: "PPN Masukan 11%"
    report_id: Indonesian Tax Report
    tag_name: tax_11_input
    → Otomatis membuat tag +tax_11_input dan -tax_11_input
```

### Step 3: Hubungkan ke Tax

```
account.tax: PPN 11% Penjualan
    invoice_repartition_line_ids:
        - tag_ids: +tax_11_output
    refund_repartition_line_ids:
        - tag_ids: -tax_11_output

account.tax: PPN 11% Pembelian
    invoice_repartition_line_ids:
        - tag_ids: +tax_11_input
    refund_repartition_line_ids:
        - tag_ids: -tax_11_input
```

---

## Formula Lines (Total Lines)

Report lines bisa memiliki formula untuk menghitung totals:

```
account.tax.report.line:
    name: "NET PPN"
    report_id: Indonesian Tax Report
    formula: tax_11_output - tax_11_input
    → Tidak memiliki tag_name, hanya formula
```

**Formula Operators**:
- `+`, `-`, `*`, `/` — arithmetic
- Parentheses for grouping
- Reference ke line codes lain

---

## Carryover (Pemindahan Saldo)

Carryover digunakan untuk memindahkan saldo negatif antar periode.

### Kondisi Carryover

| Method | Description |
|--------|-------------|
| `no_negative_amount_carry_over_condition` | Saldo negatif di-carry ke periode berikutnya |
| `always_carry_over_and_set_to_0` | Selalu carry, reset ke 0 |

### Contoh: Tax Reconciliation

```
Periode Q1 2024:
┌─────────────────────────┬────────────┐
│ Line                    │ Balance    │
├─────────────────────────┼────────────┤
│ PPN Keluaran           │ 100,000,000│
│ PPN Masukan            │  80,000,000│
│ NET (K赢-Kmas)         │  20,000,000│ ← positive = harus dibayar
└─────────────────────────┴────────────┘

Periode Q2 2024:
┌─────────────────────────┬────────────┐
│ Line                    │ Balance    │
├─────────────────────────┼────────────┤
│ PPN Keluaran           │ 120,000,000│
│ PPN Masukan            │ 150,000,000│
│ NET (K赢-Kmas)         │ -30,000,000│ ← negative = bisa di-credit
│ Carryover from Q1      │  30,000,000│ ← automatically applied
│ Sisa Kredit Pajak      │       0    │
└─────────────────────────┴────────────┘
```

---

## Cash Basis Accounting (CABA) dengan Tax Grid

Untuk taxes dengan `tax_exigibility = 'on_payment'`:

### On Invoice (Default)

```
Invoice Posted (on_invoice tax)
    │
    └─► Tax recognized immediately
            tax_tag_ids = +tax_11_output
            balance credited to tax payable

    Journal Entry:
    ┌─────────────────────────────────┬───────┬─────────┐
    │ Account                        │ Debit │ Credit  │
    ├────────────────────────────────┼───────┼─────────┤
    │ Expenses                        │ 100,000,000        │
    │ Input VAT                       │  11,000,000        │
    │ Accounts Payable               │        │111,000,000│
    └────────────────────────────────┴───────┴─────────┘
```

### On Payment (CABA)

```
Invoice Posted (on_payment tax)
    │
    └─► Tax NOT recognized yet
            Tax line exists but NOT in tax report
            amount_residual = tax_amount

Payment Made
    │
    └─► Tax recognized via partial reconciliation
            └─► _create_tax_cash_basis_moves()
                    │
                    └─► CABA Entry:
                        ┌─────────────────────────────────┬───────┬─────────┐
                        │ Account                        │ Debit │ Credit  │
                        ├────────────────────────────────┼───────┼─────────┤
                        │ Tax Receivable (base)          │ XXX   │         │
                        │ Tax Payable (base)             │       │ XXX    │
                        └────────────────────────────────┴───────┴─────────┘
```

---

## Debugging Tax Grid Issues

### 1. Tag Tidak Muncul di Report

**Check**:
- [ ] Tax punya `invoice_repartition_line_ids` dengan `tag_ids`?
- [ ] Tag `applicability = 'taxes'`?
- [ ] Tag `country_id` cocok dengan report?
- [ ] Invoice sudah `posted`?

### 2. Nilai Tidak Sesuai

**Check**:
- [ ] `tax_negate` benar? (+ untuk payable, - untuk receivable)
- [ ] Ada partial payment?
- [ ] CABA tax recognized?
- [ ] Ada credit note yang perlu di-refund?

### 3. SQL Debug Query

```sql
-- Check tax tags on move lines
SELECT
    aml.id,
    aml.name,
    aml.debit,
    aml.credit,
    aat.name as tag_name,
    aat.tax_negate
FROM account_move_line aml
JOIN account_move_line_account_tax_rel amlt
    ON aml.id = amlt.account_move_line_id
JOIN account_account_tag aat
    ON aat.id = amlt.account_account_tag_id
WHERE aml.move_id = [move_id]
  AND aat.applicability = 'taxes';
```

---

## Best Practices

1. **Naming Convention**: Gunakan prefix yang konsisten, misal `tax_XX_[input|output]`
2. **Country-Specific**: Selalu set `country_id` untuk menghindari konflik multi-VAT
3. **Formula Lines**: Gunakan untuk perhitungan bersih, bukan manual entry
4. **Carryover Setup**: Atur dengan benar untuk tax reconciliation
5. **Repartition**: Pastikan 100% allocation untuk tax lines

---

## Related Documentation

- [Modules/Account](Account.md) — Core account models
- [Flows/Account/invoice-post-flow](invoice-post-flow.md) — Invoice posting
- [Flows/Account/payment-flow](payment-flow.md) — Payment and CABA
- [Flows/Cross-Module/sale-stock-account-flow](sale-stock-account-flow.md) — Full business cycle

---

**Source**: `addons/account/models/account_tax_report.py`, `addons/account/models/account_account_tag.py`
