---
uid: l10n_de
title: Germany - Accounting (l10n_de)
folder: Modules/Finance & Accounting
date: 2026-04-11
version: "4.0"
tags: [l10n, localization, german-accounting, datev, skr03, skr04, gobd, tax-report, hgb, sepa]
description: German accounting localization including SKR03/SKR04 chart of accounts, DATEV integration via l10n_de_datev_code, USt/VSt tax structure, GoBD audit trail enforcement, delivery date auto-set on posting, HGB-compliant balance sheet tag mapping, and SEPA payment support.
related_modules:
  - account
  - l10n_din5008
  - base_iban
  - base_vat
  - account_edi_ubl_cii
---

# l10n_de — Germany Accounting Localization

> **Module**: `l10n_de` | **Version**: 4.0 | **Category**: `Accounting/Localizations/Account Charts`
> **Author**: openbig.org | **License**: LGPL-3 | **Auto-installs with**: `account`
> **Depends**: `base_iban`, `base_vat`, `l10n_din5008`, `account`, `account_edi_ubl_cii`

German accounting localization providing the **SKR03** (Standardkontenrahmen 03) and **SKR04** (Standardkontenrahmen 04) chart of accounts, German tax structure (USt/VSt), GoBD-compliant audit trail, DATEV code support, and SEPA payment format support. SKR03 is used by small-to-medium businesses in the traditional sector; SKR04 is used by larger businesses and industry. Both use 4-digit account codes.

---

## Module Structure

```
l10n_de/
├── __init__.py                       # _post_init_hook → _activate_group_account_secured
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── chart_template.py             # Adds B_II_4 and B_IV BS tags to suspense/transfer accts
│   ├── template_de_skr03.py           # SKR03: 1275 accounts, 243 tax lines, 6 reconcile models
│   ├── template_de_skr04.py           # SKR04: 1193 accounts, 243 tax lines, 6 reconcile models
│   ├── res_company.py                # stnr/widnr fields, stnr validation, audit trail force
│   ├── account_journal.py            # Adds tag_de_asset_bs_B_IV to new liquidity accounts (DE)
│   ├── account_account.py            # Blocks account code changes if move lines exist (DE)
│   ├── account_move.py               # Auto-sets delivery_date on posting (DE sale docs)
│   ├── datev.py                     # l10n_de_datev_code on taxes; tax-rate → income/expense matching
│   └── ir_actions_report.py          # Passes din_header_spacing to QWeb report context
├── data/
│   ├── account_account_tags_data.xml  # Tax report (Steuerbericht) + BS tags (HGB layout)
│   └── template/
│       ├── account.account-de_skr03.csv   # 1275 accounts
│       ├── account.account-de_skr04.csv   # 1193 accounts
│       ├── account.tax-de_skr03.csv       # 243 tax lines (~30 taxes)
│       ├── account.tax-de_skr04.csv      # 243 tax lines
│       ├── account.tax.group-de_skr03.csv
│       ├── account.fiscal.position-de_skr03.csv
│       └── account.fiscal.position-de_skr04.csv
├── views/
│   ├── res_company_views.xml         # Adds l10n_de_stnr + l10n_de_widnr to company form
│   └── account_view.xml              # Adds l10n_de_datev_code to tax form (DE only)
├── wizard/
│   └── account_secure_entries_wizard.xml  # Adds GoBD notice to secure entries wizard
├── migrations/
│   ├── 1.1/post-migrate_update_amls.py   # Re-tag tax tags: 68 → 60
│   ├── 2.0/pre-migrate.py              # Rename BS tags: D→C, C→B, E→D, F→E
│   └── 3.0/pre-migrate.py              # Delete old tax report + lines
└── tests/
    ├── test_account_move.py           # delivery_date auto-set; custom currency rate
    └── test_audit_trail.py           # restrictive_audit_trail lock for DE companies
```

---

## Company-Level Fields (`res.company`)

### `l10n_de_stnr` — SteuerNummer (State Tax Number)

```python
l10n_de_stnr = fields.Char(
    string="St.-Nr.",
    help="Tax number. Scheme: ??FF0BBBUUUUP, e.g.: 2893081508152",
    tracking=True,
)
```

**Visibility**: Only shown when `account_fiscal_country_id` includes `de`:
```xml
<field name="l10n_de_stnr" invisible="%(base.de)d not in account_enabled_tax_country_ids"/>
```

**Validation** — `@api.constrains('state_id', 'l10n_de_stnr')` using `stdnum.de.stnr`:

```
Input: stnr="2893081508152", state_id.name="Bayern"
Step 1: stdnum.de.stnr.to_country_number(stnr, state_name)
        → national_steuer_nummer (state-relative → national conversion)
Step 2: If InvalidComponent raised → "SteuerNummer is not compatible with your state"
Step 3: If InvalidFormat but stnr.is_valid(state_name) → use raw stnr
Step 4: If neither valid → "SteuerNummer is not valid"
Step 5: If country_code != 'DE' → return stnr as-is (no validation)
```

**Performance note**: `stdnum.de.stnr` is a pure-Python local library — no network I/O. The validation runs on every `write` that touches the field. For bulk imports, consider using `@api.model` batch validation or bypassing the constraint via `sudo()`.

### `l10n_de_widnr` — Wirtschafts-Identifikationsnummer

```python
l10n_de_widnr = fields.Char(
    string="W-IdNr.",
    help="Business identification number.",
    tracking=True,
)
```

**Visibility**: Only when `country_code == 'DE'` (broader than stnr). The W-IdNr is a 9-digit EU-wide business ID, distinct from the state-relative SteuerNummer. Many German companies have both.

### Fiscal Country Protection — `res.company.write()`

```python
if (
    'account_fiscal_country_id' in vals
    and (german_companies := self.filtered(lambda c: c.account_fiscal_country_id.code == 'DE'))
    and self.env['res.country'].browse(vals['account_fiscal_country_id']).code != 'DE'
    and self.env['account.move'].search_count([('company_id', 'in', german_companies.ids)], limit=1)
):
    raise ValidationError(_("You cannot change the fiscal country."))
```

**L4 edge case**: Once a company with German fiscal country has any posted move, it can never change fiscal country. The `search_count(..., limit=1)` is efficient (early-exit at 1). However, the lock is one-way — there is no upgrade script to unlock it. Manual SQL correction required to change fiscal country post-move creation.

### GoBD Audit Trail Enforcement

```python
@api.depends('country_code')
def _compute_force_restrictive_audit_trail(self):
    super()._compute_force_restrictive_audit_trail()
    for company in self:
        company.force_restrictive_audit_trail |= company.country_code == 'DE'
```

Any company with `country_code == 'DE'` has `force_restrictive_audit_trail = True`, which locks `restrictive_audit_trail = True`. Attempting to disable it via UI raises:
```
UserError: "Can't disable restricted audit trail: forced by localization."
```

**Wizard notice** (`account_secure_entries_wizard.xml`):
> "By securing entries, you make them unchangeable. This is required by law to ensure complete and traceable bookkeeping in accordance with GoBD."

**`post_init_hook`** — `_post_init_hook(env)`:
```python
env['res.groups']._activate_group_account_secured()
```
Activates the `account_secured` group immediately on module installation. If the group activation fails (e.g., the group definition is missing in a custom build), installation proceeds but the secured audit group may not be active — requires manual check.

---

## Chart of Accounts — SKR03 vs SKR04

### Template Data Methods

Both SKR03 and SKR04 use the `@template` decorator pattern on `AccountChartTemplate` to register data for loading via `account.chart.template.try_loading()`.

#### SKR03 — `template_de_skr03.py`

**`_get_de_skr03_template_data()`**:
```python
{
    'code_digits': '4',
    'property_account_receivable_id': 'account_1410',
    'property_account_payable_id': 'account_1610',
    'property_stock_valuation_account_id': 'account_3960',
    'name': 'German Chart of Accounts SKR03',
}
```

**`_get_de_skr03_res_company()`** — sets on `self.env.company`:
```
account_fiscal_country_id: base.de
bank_account_code_prefix: 120
cash_account_code_prefix: 100
transfer_account_code_prefix: 1360
account_default_pos_receivable_account_id: account_1411
income_currency_exchange_account_id: account_2660
expense_currency_exchange_account_id: account_2150
account_journal_early_pay_discount_loss_account_id: account_2130
account_journal_early_pay_discount_gain_account_id: account_2670
account_sale_tax_id: tax_ust_19_skr03
account_purchase_tax_id: tax_vst_19_skr03
expense_account_id: account_3400
income_account_id: account_8400
account_stock_journal_id: inventory_valuation
account_stock_valuation_id: account_7200
```

**`_get_de_skr03_account_account()`** — stock mapping:
```python
{
    'account_7200': {
        'account_stock_expense_id': 'account_3000',
        'account_stock_variation_id': 'account_3955',
    },
}
```

#### SKR04 — `template_de_skr04.py`

**`_get_de_skr04_template_data()`**:
```python
{
    'name': 'German chart of accounts SKR04',
    'code_digits': '4',
    'property_account_receivable_id': 'chart_skr04_1205',
    'property_account_payable_id': 'chart_skr04_3301',
}
```

**`_get_de_skr04_res_company()`**:
```
bank_account_code_prefix: 180
cash_account_code_prefix: 160
transfer_account_code_prefix: 1460
account_default_pos_receivable_account_id: chart_skr04_1206
income_currency_exchange_account_id: chart_skr04_4840
expense_currency_exchange_account_id: chart_skr04_6880
account_journal_early_pay_discount_loss_account_id: chart_skr04_4730
account_journal_early_pay_discount_gain_account_id: chart_skr04_5730
default_cash_difference_income_account_id: chart_skr04_9991   ← SKR04 only
default_cash_difference_expense_account_id: chart_skr04_9994  ← SKR04 only
account_sale_tax_id: tax_ust_19_skr04
account_purchase_tax_id: tax_vst_19_skr04
expense_account_id: chart_skr04_5400
income_account_id: chart_skr04_4400
account_stock_journal_id: inventory_valuation
account_stock_valuation_id: chart_skr04_1000
```

**`_get_de_skr04_account_account()`** — stock mapping:
```python
{
    'chart_skr04_1000': {
        'account_stock_expense_id': 'chart_skr04_5000',
        'account_stock_variation_id': 'chart_skr04_5880',
    },
}
```

**Asymmetry note (L4)**: SKR04 explicitly sets `default_cash_difference_income_account_id` and `default_cash_difference_expense_account_id` (SKR04-specific accounts 9991/9994), while SKR03 relies on inherited `account` module defaults. This reflects SKR04's more comprehensive account structure.

### Utility Account Tag Setup — `_setup_utility_bank_accounts()`

```python
def _setup_utility_bank_accounts(self, template_code, company, template_data):
    super()._setup_utility_bank_accounts(template_code, company, template_data)
    if template_code in ["de_skr03", "de_skr04"]:
        company.account_journal_suspense_account_id.tag_ids = self.env.ref('l10n_de.tag_de_asset_bs_B_II_4')
        company.transfer_account_id.tag_ids = self.env.ref('l10n_de.tag_de_asset_bs_B_IV')
```

Both suspense (bank reconciliation clearing) and transfer (internal clearing) accounts get HGB balance sheet tags:
- `tag_de_asset_bs_B_II_4` — "B II 4 - Sonstige Forderungen" (suspense/clearing accounts)
- `tag_de_asset_bs_B_IV` — "B IV - Kassenbestand, Bundesbankguthaben, Guthaben bei Kreditinstituten und Schecks" (cash and bank balances)

### Liquidity Account Tagging — `account.journal._prepare_liquidity_account_vals()`

```python
def _prepare_liquidity_account_vals(self, company, code, vals):
    res = super()._prepare_liquidity_account_vals(company, code, vals)
    if company.account_fiscal_country_id.code == 'DE':
        tag_ids = res.get('tag_ids', [])
        tag_ids.append((4, self.env.ref('l10n_de.tag_de_asset_bs_B_IV').id))
        res['tag_ids'] = tag_ids
    return res
```

When a new bank or cash journal is created for a German company, its automatically created liquidity account gets `tag_de_asset_bs_B_IV` — meaning newly created German bank accounts appear in the correct cash position of the HGB balance sheet automatically, with no manual tagging required.

### Account Code Change Protection — `account.account.write()`

```python
def write(self, vals):
    if (
        'code' in vals
        and self.env.company.account_fiscal_country_id.code == 'DE'
        and any(
            self.env.company in a.company_ids and a.code != vals['code']
            for a in self
        )
    ):
        if self.env['account.move.line'].search_count([('account_id', 'in', self.ids)], limit=1):
            raise UserError(_("You can not change the code of an account."))
    return super().write(vals)
```

**Scope**: Checks `self.env.company` — multi-company aware. If the account belongs to multiple companies and any one is German, the check applies. The `search_count(..., limit=1)` stops at the first move line, minimizing DB load. Does NOT block code changes for non-DE companies.

---

## Tax Structure

### Tax Groups
- `tax_group_19` — 19% standard rate
- `tax_group_7` — 7% reduced rate
- `tax_group_0` — 0% exempt / intra-community / export

### Key Taxes — SKR03 (~30 taxes total, 243 CSV lines with repartition lines; SKR04 variants exist with `_skr04` suffix)

| Tax ID | Rate | Type | Legal basis | DATEV tag | Tax account | Deduct account |
|--------|------|------|-------------|-----------|-------------|----------------|
| `tax_ust_19_skr03` | 19% | sale | §12 UStG | `89_BASE`/`89_TAX` | 1771 | — |
| `tax_ust_7_skr03` | 7% | sale | §12 UStG | `89_BASE`/`89_TAX` | 1771 | — |
| `tax_vst_19_skr03` | 19% | purchase | §15 UStG | `89_BASE`/`89_TAX` | 1571 | — |
| `tax_vst_7_skr03` | 7% | purchase | §15 UStG | `89_BASE`/`89_TAX` | 1571 | — |
| `tax_eu_19_purchase_skr03` | 19% | purchase | §1a UStG | `89_BASE`/`89_TAX` | 1774 (tax) | 1574 (due) |
| `tax_eu_7_purchase_skr03` | 7% | purchase | §1a UStG | `93_BASE`/`93_TAX` | 1772/1572 | — |
| `tax_eu_19_purchase_no_vst_skr03` | 19% | purchase | §1a(2) UStG | `89_BASE`/`89_TAX` | 1779 | — (no VSt) |
| `tax_eu_sale_skr03` | 0% | sale | §4(1b) UStG | `41` | — | — |
| `tax_export_skr03` | 0% | sale | §4(1a) UStG | `43` | — | — |
| `tax_free_skr03_mit_vst` | 0% | sale | §4 No. 2–7 UStG | `43` | — | — |
| `tax_free_skr03_ohne_vst` | 0% | sale | §4 No. 8–28 UStG | `48` | — | — |
| `tax_import_19_and_payable_skr03` | 19% | purchase | §21(3) UStG | `62` | 1788 (EUSt) | 1588 |

### `l10n_de_datev_code` — 4-digit DATEV accounting code

```python
# models/datev.py — extends account.tax
l10n_de_datev_code = fields.Char(size=4, help="4 digits code use by Datev", tracking=True)
```

Displayed in the tax form only when `country_code == 'DE'`:
```xml
<field name="l10n_de_datev_code" invisible="country_code != 'DE'"/>
```

Used for German DATEV software export. Common codes: `89` (19% base), `89_BASE`/`89_TAX` (DATEV tag pair for 19% transactions), `93` (7% base), `41` (ICL exempt), `43` (export/exempt), `48` (exempt without credit), `94`/`96` (vehicle acquisition), `61`/`59` (EC sales list), `62` (import VAT).

---

## Fiscal Positions

| Position ID | `auto_apply` | Sequence | Trigger | Key mapping |
|-------------|-------------|----------|---------|-------------|
| `fiscal_position_domestic_skr03` | Yes | 10 | Domestic partner | No change |
| `fiscal_position_non_eu_partner_service_skr03` | No | 60 | Non-EU service supplier | Revenue `account_8400` → `account_8338`; Expense `account_3400` → `account_3125` |
| `fiscal_position_eu_vat_id_partner_skr03` | No | — | EU partner with VAT | → activates IC acquisition taxes |
| `fiscal_position_eu_no_id_partner_skr03` | No | — | EU partner, no VAT | → activates 0% VSt acquisition |
| `fiscal_position_eu_vat_id_partner_service_skr03` | No | — | EU service supplier | → alternative account mapping |

SKR04 has equivalent positions with `_skr04` suffix. All fiscal positions are loaded via `account.fiscal.position-de_skr03.csv` / `_de_skr04.csv` during chart installation.

---

## Delivery Date Auto-Set — `account.move`

```python
# models/account_move.py
@api.depends('country_code', 'move_type')
def _compute_show_delivery_date(self):
    super()._compute_show_delivery_date()
    for move in self:
        if move.country_code == 'DE':
            move.show_delivery_date = move.is_sale_document()

def _post(self, soft=True):
    for move in self:
        if move.country_code == 'DE' and move.is_sale_document() and not move.delivery_date:
            move.delivery_date = move.invoice_date or fields.Date.context_today(self)
    return super()._post(soft)
```

**Trigger**: On `_post()` (journal entry posting) for any German sale document (`out_invoice`, `out_refund`). If `delivery_date` is not set, defaults to `invoice_date` or today.

**Purpose**: Required for German VAT reporting (Steuerbericht) and ELSTER tax authority submissions. The date of supply (Lieferdatum) is a mandatory component of the German tax return (§18 UStG).

**Edge case (L4)**: The check `not move.delivery_date` uses ORM falsy semantics. An explicitly falsy value (empty string from form, `False`) is treated as missing and will be overwritten. Only a truthy date value (actual date) preserves the user-set value.

---

## Product Account Auto-Matching — `product.template._get_product_accounts()`

```python
# models/datev.py
def _get_product_accounts(self):
    result = super(ProductTemplate, self)._get_product_accounts()
    company = self.env.company
    if company.account_fiscal_country_id.code == "DE":
        # Income account: match on tax rate
        if not self.property_account_income_id:
            taxes = self.taxes_id.filtered_domain(self.env['account.tax']._check_company_domain(company))
            if not result['income'] or (result['income'].tax_ids and taxes and taxes[0] not in result['income'].tax_ids):
                result_income = self.env['account.account'].with_company(company).search([
                    *self.env['account.account']._check_company_domain(company),
                    ('internal_group', '=', 'income'),
                    ('tax_ids', 'in', taxes.ids)
                ], limit=1)
                result['income'] = result_income or result['income']
        # Expense account: match on supplier tax rate
        if not self.property_account_expense_id:
            supplier_taxes = self.supplier_taxes_id.filtered_domain(self.env['account.tax']._check_company_domain(company))
            if not result['expense'] or (result['expense'].tax_ids and supplier_taxes and supplier_taxes[0] not in result['expense'].tax_ids):
                result_expense = self.env['account.account'].with_company(company).search([
                    *self.env['account.account']._check_company_domain(company),
                    ('internal_group', '=', 'expense'),
                    ('tax_ids', 'in', supplier_taxes.ids),
                ], limit=1)
                result['expense'] = result_expense or result['expense']
    return result
```

**Purpose**: German tax law requires each VAT rate to have its own income/expense account. When a product has no explicit account but carries a tax with a specific rate, Odoo searches for an income or expense account tagged with that same tax. Without this, the "different rate tax needs different account" constraint would block invoicing.

**Performance note**: Uses `search([..., limit=1])` — returns first match (non-deterministic if multiple accounts share the same tax tag). In practice, the SKR03/SKR04 chart structure provides exactly one account per rate per type, so this is deterministic. Uses `with_company(company)` to enforce company domain scoping.

**Fallback chain**:
1. Explicit `property_account_income_id` / `property_account_expense_id` on product → used directly (no search)
2. Search for account tagged with the first tax in `taxes_id` / `supplier_taxes_id` → used if found
3. Fall back to result['income']/result['expense'] from `super()` (the standard property accounts)

---

## Reconciliation Models (Auto-created on Chart Load)

Both templates install 6 `account.reconcile.model` records via the `@template('de_skr0x', 'account.reconcile.model')` decorator pattern (not via CSV):

### SKR03

| Model ID | Name | Account | Tax | Description |
|----------|------|---------|-----|-------------|
| `reconcile_3731` | Discount-EK-7% | `account_3731` | `tax_vst_7_skr03` | Purchase cash discount 7% |
| `reconcile_3736` | Discount-EK-19% | `account_3736` | `tax_vst_19_skr03` | Purchase cash discount 19% |
| `reconcile_8731` | Discount-VK-7% | `account_8731` | `tax_ust_7_skr03` | Sale cash discount 7% |
| `reconcile_8736` | Discount-VK-19% | `account_8736` | `tax_ust_19_skr03` | Sale cash discount 19% |
| `reconcile_2401` | Loss of receivables-7% | `account_2401` | `tax_ust_7_skr03` | Bad debt write-off 7% |
| `reconcile_2406` | Loss of receivables-19% | `account_2406` | `tax_ust_19_skr03` | Bad debt write-off 19% |

### SKR04 (accounts in 4xxx/5xxx/6xxx range)

| Model ID | Account |
|----------|---------|
| `reconcile_5731` | `chart_skr04_5731` |
| `reconcile_5736` | `chart_skr04_5736` |
| `reconcile_4731` | `chart_skr04_4731` |
| `reconcile_4736` | `chart_skr04_4736` |
| `reconcile_6931` | `chart_skr04_6931` |
| `reconcile_6936` | `chart_skr04_6936` |

All use `amount_type: percentage`, `amount_string: '100'` (full amount), with associated tax at the same rate.

---

## Tax Report (Steuerbericht) — `account.report`

Defined in `data/account_account_tags_data.xml`, `id = tax_report`:
- **Root**: `account.generic_tax_report`
- **Availability**: `country` (only for DE)
- **Allow foreign VAT**: `True`
- **Columns**: `base` (Steuerpflichtiger Umsatz), `tax` (Umsatzsteuer)
- **Line structure** (HGB §18 UStDV aligned):

| Section | Code | Lines | Description |
|---------|------|-------|-------------|
| A. Taxable supplies | `AGG_DE_19` | `de_tag_81`–`de_tag_86` | 19%/7% domestic sales, other services, self-supplies |
| B. Intra-community acquisitions | `DE_91`–`DE_93` | `de_tax_tag_17`, `de_tax_tag_18` | EU acquisitions with VSt reversal |
| C. Reverse charge services | — | — | Miscellaneous services, §13b UStG |
| D. Corrections | — | — | Credit notes, corrections |
| E. Import VAT | — | `de_tax_tag_19` | §21(3) UStG import sales tax |

**DATEV tag codes used as tax tags**: `89_BASE`/`89_TAX` (19%), `93_BASE`/`93_TAX` (7%), `41` (ICL), `43` (export), `94` (vehicle base), `96` (vehicle tax), `62` (EUSt import).

---

## Balance Sheet Tags — HGB Layout

Tags drive the German balance sheet (Bilanz) and P&L (GuV) report layouts. All have `applicability: accounts`.

### Active (Soll — Assets)

| HGB Section | Tag ID Pattern | Description |
|-------------|----------------|-------------|
| A I | `tag_de_asset_bs_A_I_1` to `_4` | Intangible fixed assets: concessions, goodwill, prepayments, internally generated |
| A II 1 | `tag_de_asset_bs_A_II_1` | Land and buildings |
| A II 4 | `tag_de_asset_bs_A_II_4` | Advance payments + assets under construction |
| A III 1–6 | `tag_de_asset_bs_A_III_1` to `_6` | Financial assets: shares in affiliates, loans, participations, securities |
| B I 1–4 | `tag_de_asset_bs_B_I_1` to `_4` | Inventories: raw materials, WIP, finished goods, prepayments |
| B II 1 | `tag_de_asset_bs_B_II_1` | Trade receivables (FOR) |
| B II 2 | `tag_de_asset_bs_B_II_2` | Receivables from affiliated companies |
| B II 3 | `tag_de_asset_bs_B_II_3` | Receivables from participating companies |
| **B II 4** | `tag_de_asset_bs_B_II_4` | **Other receivables — suspense accounts land here** |
| B III 1–2 | `tag_de_asset_bs_B_III_1` to `_2` | Securities, shares (current financial assets) |
| **B IV** | `tag_de_asset_bs_B_IV` | **Cash and bank — all liquidity accounts tagged here** |
| C | `tag_de_asset_bs_C` | Prepaid expenses (Rechnungsabgrenzungsposten) |
| D | `tag_de_asset_bs_D` | Deferred tax assets (aktive latente Steuern) |
| E | `tag_de_asset_bs_E` | Active difference from asset offsetting |

### Passive (Haben — Equity & Liabilities)

| HGB Section | Tag ID Pattern | Description |
|-------------|----------------|-------------|
| A I | `tag_de_liabilities_bs_A_I` | Subscribed capital (Gezeichnetes Kapital) |
| A II | `tag_de_liabilities_bs_A_II` | Capital reserve (Kapitalrücklage) |
| A III 1–4 | `tag_de_liabilities_bs_A_III_1` to `_4` | Reserves: legal, related-company shares, statutory, other |
| A IV | `tag_de_liabilities_bs_A_IV` | Profit/loss carried forward (Gewinnvortrag/Verlustvortrag) |
| A V | `tag_de_liabilities_bs_A_V` | Net profit/loss for the year |
| **B 1** | `tag_de_liabilities_bs_B_1` | **Pension provisions** |
| **B 2** | `tag_de_liabilities_bs_B_2` | **Tax provisions** |
| **B 3** | `tag_de_liabilities_bs_B_3` | **Other provisions** |
| C 1–8 | `tag_de_liabilities_bs_C_1` to `_8` | Liabilities: bonds, bank debt, prepayments received, trade payables, bills, affiliate debt, participation debt, other (taxes, social security) |
| D | `tag_de_liabilities_bs_D` | Deferred income (Rechnungsabgrenzungsposten) |
| E | `tag_de_liabilities_bs_E` | Deferred tax liabilities (passive latente Steuern) |

### Migration 2.0 — Tag Renumbering

Version 2.0 pre-migration renames all balance sheet tags to reflect updated HGB classification (effective from the 2016 Bilanzrecht Modernisierungsgesetz — BilMoG):
```
C_1 → B_1, C_2 → B_2, C_3 → B_3  (liabilities C → B)
D_1 → C_1, D_2 → C_2, ... D_8 → C_8  (liabilities D → C)
E → D  (liabilities E → D)
F → E  (liabilities F → E)
```

The migration is idempotent — checks `if cr.rowcount:` before renaming and returns early if already done.

---

## Report Layout Override — `ir.actions.report`

```python
def _get_rendering_context(self, report, docids, data):
    data = super()._get_rendering_context(report, docids, data)
    data['din_header_spacing'] = report.get_paperformat().header_spacing
    return data
```

Passes `din_header_spacing` from the paper format into the QWeb report rendering context. Used by `l10n_din5008.external_layout_din5008` to correctly position the letterhead on printed documents (DIN 5008 standard for German business letters).

---

## SEPA Payment Format

German companies predominantly use SEPA (Single Euro Payments Area) payment formats for both bank transfers and direct debits. The `l10n_de` module itself does not define SEPA-specific payment methods or export configurations — those are provided by the core `account` module. However, `l10n_de` influences SEPA payments in two important ways:

### SEPA Direct Debit (SEPA-Lastschrift)

When a German company receives SEPA direct debit payments from customers, the correct bank account must be configured for the SEPA DD mandate. The `l10n_de` module, through its dependency on `base_iban`, ensures German IBANs are validated correctly. A German company's bank account used for SEPA DD must have the correct `tag_de_asset_bs_B_IV` (B IV cash and bank balances) tag set automatically via `account.journal._prepare_liquidity_account_vals()`.

### SEPA Credit Transfer (SEPA-Überweisung)

When making outgoing SEPA credit transfers, the payment method is configured in the accounting journal. The `account_finance_export` module (in the `account` module) provides SEPA pain.001.001.03 XML export. German-specific considerations:
- **Bank account**: Must be IBAN format (DE country code + 22 digits)
- **Creditor identifier**: German companies collecting SEPA direct debits need a Gläubiger-Identifikationsnummer (creditor ID)
- **Reference**: SEPA requires ISO 20022-compliant remittance information; the `l10n_de` delivery date mechanism feeds into invoice metadata that can be included in SEPA payment references

**Key integration point**: The `l10n_de_datev_code` on taxes has no direct relationship with SEPA formats — DATEV codes are for accounting export, while SEPA pain.001 is the bank payment export format. Both serve German regulatory requirements but are independent systems.

---

## Version Changes: Odoo 18 → 19

The transition from Odoo 18 to 19 had significant impact on `l10n_de`. The changes reflect Odoo's shift from the older `l10n_de.tax.report` (the legacy Steuerbericht built with the old `account.report` engine) to the new `account.report`-native tax report, plus BS tag structural updates.

### What Changed

| Aspect | Odoo 18 (`l10n_de` v2.x) | Odoo 19 (`l10n_de` v3.x) |
|--------|--------------------------|--------------------------|
| **Tax report engine** | `l10n_de.tax.report` (legacy) + `account_account_tags_data.xml` with many static tax report lines | `account.generic_tax_report` as root; new `l10n_de.tax_report` (`account.report`) with tax-tags-based dynamic expressions |
| **Tax report columns** | Three columns: balance, base, tax | Reduced to two columns: base + tax (balance column removed) |
| **Tax report lines** | ~100+ static line definitions with fixed expression IDs | Dynamic via `tax_tags` engine; uses sign-aware `-XX_BASE` / `-XX_TAX` formulas |
| **BS tag names** | Old naming scheme: `tag_de_liabilities_bs_C_1`, `tag_de_liabilities_bs_D_1`, etc. | New HGB BilMoG names: `tag_de_liabilities_bs_B_1` through `E` |
| **Tag migration** | None (pre-2.0) | `2.0/pre-migrate.py` renames all ir_model_data tag records |

### Migration 3.0 (Odoo 18 → 19)

The `3.0/pre-migrate.py` is the critical migration for upgrading from Odoo 18-era l10n_de:

```python
def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    tax_report = env.ref("l10n_de.tax_report", raise_if_not_found=False)
    balance_column = env.ref('l10n_de.tax_report_balance', raise_if_not_found=False)
    report_lines = [f"l10n_de.tax_report_de_tax_tag_{btw}" for btw in ["17","18","19","31","46","55","64"]]
        + [f"l10n_de.tax_report_de_tag_{btw}" for btw in
           ["01","02","17","18","19","25","26","27","31","33","34","36","37","46","47","71","74","80","85","96","98"]]

    if balance_column:
        cr.execute("DELETE FROM account_report_column WHERE id = %s", (balance_column.id,))
    if report_line_ids:
        cr.execute("DELETE FROM account_report_line WHERE id IN %s", (report_line_ids,))
    if tax_report:
        cr.execute("UPDATE account_report_line SET code = NULL WHERE report_id = %s", (tax_report.id,))
```

This migration:
1. **Deletes** the legacy `tax_report_balance` column from the old report
2. **Deletes** ~28 stale tax report line records (`de_tax_tag_*` and `de_tag_*`)
3. **Nulls** the `code` field on remaining lines to avoid conflicts with the new `tax_tags`-based expressions

**Note**: The `account_account_tags_data.xml` defines the new report (`l10n_de.tax_report`) which loads with fresh XML on module upgrade. The migration cleans up the old report's orphaned records that would otherwise conflict.

### What Did NOT Change

- SKR03/SKR04 chart data (CSV files) are unchanged between Odoo 18 and 19
- Company fields (`l10n_de_stnr`, `l10n_de_widnr`) are unchanged
- GoBD audit trail enforcement is unchanged
- Delivery date auto-set logic is unchanged
- Product account auto-matching is unchanged
- Liquidity account auto-tagging is unchanged

---

## Migrations Summary

| Migration | Type | Action |
|-----------|------|--------|
| `1.1` → `1.2` | `post-migrate` | Re-tag AML tax tags: code `68` → `60`. Runs raw SQL on `account_account_tag_account_move_line_rel` for performance on large tables. Reason: tax report line 68 was removed from official German tax return. |
| `2.0` → `3.0` | `pre-migrate` | Rename all balance sheet tag ir_model_data records (D→C, C→B, E→D, F→E). Idempotent via `cr.rowcount` check. Delete `tag_de_liabilities_bs_F` from ir_model_data before rename to avoid FK conflicts. Handles already-upgraded databases via early-return guard. |
| `3.0` → current | `pre-migrate` | Delete old `tax_report` report and its line/column records. Purge stale `de_tax_tag_*` and `de_tag_*` report line IDs. Clear `code` from remaining lines. |

---

## Cross-Module Integration

```
l10n_de
├── account                    # Core: journal entries, move posting, tax engine, audit trail
│   └── account.chart.template → template_de_skr03/04 load via @template decorators
├── l10n_din5008             # Paper format (paperformat_euro_din), external layout
│   ├── paperformat_euro_din → referenced as paperformat_id in SKR company defaults
│   └── external_layout_din5008 → external_report_layout_id for DE companies
├── base_iban                 # German IBAN structure validation
├── base_vat                  # German VAT number format validation
└── account_edi_ubl_cii       # EU EDI invoice format for intracommunity transactions
```

The dependency on `account_edi_ubl_cii` enables the EU intra-community acquisition/supply EDI workflow (EN 16931 / EU e-invoicing mandate). German companies subject to the mandatory B2G e-invoicing requirement (E-Rechnungspflicht, mandatory from January 2025 for B2G) would use this EDI layer.

---

## Test Coverage

**`test_audit_trail.py`** — `TestAuditTrailDE` (extends `AccountTestInvoicingHttpCommon`):
```python
def test_audit_trail_setting(self):
    assert company.country_id.code == 'DE'
    assert company.account_fiscal_country_id.code == 'DE'
    assert company.restrictive_audit_trail == True
    with assertRaisesRegex(UserError, "Can't disable restricted audit trail"):
        company.restrictive_audit_trail = False
```

**`test_account_move.py`** — `TestAccountMoveDE` (extends `AccountTestInvoicingCommon`):

```python
@freeze_time('2025-01-01')
def test_missing_invoice_delivery_date(self):
    # Creates out_invoice with no delivery_date
    # After action_post(): delivery_date == invoice_date == '2025-01-01'
    move.action_post()
    assert move.delivery_date == fields.Date.from_string('2025-01-01')

def test_out_invoice_custom_currency_rate_with_missing_delivery_date(self):
    # Requires l10n_hu_edi installed (Hungarian EDI module)
    # Tests: balances are correct with custom invoice_currency_rate=5
    # Confirms delivery_date defaults correctly even with non-standard rate
    move.action_post()
    assert line_values match expected balances
```

---

## Key Design Decisions & Edge Cases

1. **Delivery date auto-set is idempotent**: Only fires when `not move.delivery_date`. Explicit falsy values (empty string, `False`) trigger overwrite. Only a truthy date value is preserved.

2. **Product account search is fallback-only**: Runs only when `property_account_income_id` / `property_account_expense_id` are unset. Explicit product-level account assignments take absolute priority.

3. **Fiscal country lock is one-way**: No upgrade path to unlock. Companies with moves cannot change fiscal country. Manual SQL required for correction (not recommended).

4. **Tag migration is idempotent-safe**: The 2.0 pre-migration checks `cr.rowcount` and returns early on re-run. If tags are already renamed, no further changes occur. The migration also guards against re-running on already-upgraded databases by checking for existing `tag_de_liabilities_bs_B_1`.

5. **SKR04 missing some inherited defaults**: `default_cash_difference_income/expense_account_id` are explicitly set in SKR04 template but not in SKR03 (inherited from `account` defaults). This asymmetry reflects the more comprehensive nature of SKR04.

6. **Audit trail group activation failure is silent**: If `_activate_group_account_secured()` fails, module installation continues. Admin must manually verify the group is active after install.

7. **No DATEV export action in this module**: `l10n_de_datev_code` provides the data, but the actual DATEV export action (writing the `.csv`/`.asc` file) is in the `account` module's standard export functionality, not in `l10n_de` itself.

8. **SEPA payment format is not defined in this module**: SEPA export (pain.001 XML) is handled by the `account` module's payment export system. `l10n_de` only ensures correct IBAN validation and liquidity account tagging.

9. **Odoo 18→19 tax report migration is destructive**: The `3.0` pre-migration deletes the old report's column and many report line records. This is intentional but means the old report structure cannot be recovered after upgrade without a database restore.

---

## Related Documentation

- [Modules/Account](Modules/account.md) — Core accounting: journal entries, move posting, tax engine, audit trail
- [Modules/l10n_din5008](Modules/l10n_din5008.md) — German document layout: paperformat, letterhead standard
- [Modules/Stock](Modules/stock.md) — Inventory valuation, stock moves, stock accounts
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — GoBD compliance, ir.rule, ACL CSV, audit trail
- [New Features/API Changes](odoo-18/New Features/API Changes.md) — Odoo 18→19 changes in l10n localization framework
- [Flows/Cross-Module/purchase-stock-account-flow](Flows/Cross-Module/purchase-stock-account-flow.md) — PO→Receipt→Vendor Bill with German VAT
- [DATEV Software Partner Portal](https://www.datev.de/web/en/home.html)
- [GoBD Guidelines (German)](https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Weitere-Themen/2016-10-27-GoBD-Grunds%C3%A4tze-zur-Ordnungsm%C3%A4%C3%9Figkeit.html)
