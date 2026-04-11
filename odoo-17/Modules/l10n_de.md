---
tags: [odoo, odoo17, module, l10n, localization, germany, datev]
research_depth: medium
---

# L10N DE — Germany Localization

**Source:** `addons/l10n_de/models/`

## Overview

Germany country localization. Provides SKR03 and SKR04 standard chart of accounts, DATEV export support, German tax number fields, delivery date on invoices, and DIN 5008 document layout. The module extends both `res.company` and `account.move` with Germany-specific logic.

## Key Models

### res.company — German Tax Numbers

**File:** `res_company.py`

Extends `res.company` with two tracking fields:

| Field | Type | Description |
|-------|------|-------------|
| `l10n_de_stnr` | Char | SteuerNummer (German tax number), format: `??FF0BBBUUUUP` |
| `l10n_de_widnr` | Char | W-IdNr. (VAT identification number for EU cross-border) |

**Validation:** `_validate_l10n_de_stnr()` (triggered by `@api.constrains`) uses the `stdnum.de.stnr` library to validate the SteuerNummer format, adapting it to the federal state (`state_id.name`) for 13-digit numbers. Raises `ValidationError` if the number is incompatible with the configured state.

**Fiscal country lock:** `write()` prevents changing `account_fiscal_country_id` away from Germany if any `account.move` records already exist for the company.

**`get_l10n_de_stnr_national()`:** Converts the stored SteuerNummer to the national format using `stdnum.de.stnr.to_country_number()`, applying state-specific digit transformations.

### account.move — Delivery Date for German Invoices

**File:** `account_move.py`

Extends `account.move` to show and auto-fill delivery date (`delivery_date`) on German sales invoices.

| Behavior | Description |
|----------|-------------|
| Show delivery date | `_compute_show_delivery_date()` sets `show_delivery_date = True` when `country_code == 'DE'` on sale documents |
| Auto-fill | `_post()` automatically sets `delivery_date = invoice_date` (or today) if not already set on posted German sale invoices |

This supports the German requirement for a delivery/installation date on invoices (Lieferdatum) per §14 UStG (German VAT Act).

## Chart of Accounts

The module provides two chart templates:

| Template | Description |
|----------|-------------|
| `de_skr03` | Standard chart of accounts SKR03 (Schinken-Kontenrahmen 03) — more detailed, 4-digit account classes |
| `de_skr04` | Standard chart of accounts SKR04 (Schinken-Kontenrahmen 04) — alternative classification, 4-digit |

**Template files:**
- `template_de_skr03.py` — SKR03 account definitions
- `template_de_skr04.py` — SKR04 account definitions
- `account_account.py` — account record creation from templates
- `account_journal.py` — journal creation (bank, cash, purchase, sale journals)
- `account_account_tags.py` — tax tags for German balance sheet classification

### `_get_de_res_company()` — Chart Template Data

In `chart_template.py`, this method configures German companies when installing a chart:

```python
{
    self.env.company.id: {
        'external_report_layout_id': 'l10n_din5008.external_layout_din5008',
        'paperformat_id': 'l10n_din5008.paperformat_euro_din',
        'check_account_audit_trail': True,
    }
}
```

Enables:
- `l10n_din5008` report layout (DIN 5008 standard document formatting)
- `l10n_din5008.paperformat_euro_din` paper format (A4 with specific margins)
- Account audit trail (change tracking on accounts)

### `_setup_utility_bank_accounts()`

After setting up bank accounts from the chart template, adds German account tags:
- `account_journal_suspense_account_id` → `tag_de_asset_bs_B_II_4` (Bank assets, current)
- `account_journal_payment_debit_account_id` → `tag_de_asset_bs_B_II_4`
- `account_journal_payment_credit_account_id` → `tag_de_asset_bs_B_II_4`
- `transfer_account_id` → `tag_de_asset_bs_B_IV` (Other receivables/prepayments)

## DATEV Integration

**File:** `datev.py`

DATEV is a German accounting data exchange format used by accountants and tax consultants. The module provides:
- Export format compatibility for DATEV accounting software
- Account number mapping from Odoo account codes to DATEV client account numbers
- See also `l10n_de_audit_trail` module for enhanced audit trail support

## Related Modules

| Module | Purpose |
|--------|---------|
| `l10n_din5008` | DIN 5008 document formatting standard |
| `l10n_de_audit_trail` | Audit trail for German compliance |
| `l10n_eu_oss` | EU One-Stop-Shop VAT reporting for EU cross-border sales |
| `l10n_es_edi_sii` | (Reference) Spanish equivalent for VAT reporting |

## See Also

- [[Modules/account]] — accounting framework
- [[Modules/l10n_din5008]] — German document layout standard