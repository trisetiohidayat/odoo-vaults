---
Module: base_vat
Version: Odoo 18
Type: Core Extension
Tags: #odoo18, #orm, #fields, #modules, #tax, #fiscal
---

# base_vat

VAT/Tax ID validation for `res.partner` records. Supports country-specific check digit algorithms, VIES online verification for EU VAT numbers, and fiscal position foreign VAT configuration.

## Module Overview

- **Models extended:** `res.partner`, `res.company`
- **Models created:** `account.fiscal.position` (extension)
- **Key dependency:** `stdnum` Python library for VAT number validation
- **VIES service:** `stdnum.eu.vat.check_vies` via SOAP (zeep)
- **Other dependencies:** `dateutil`

---

## Models

### `res.partner` (extension)

```python
class ResPartner(models.Model):
    _inherit = "res.partner"

    vies_valid = fields.Boolean(
        string="Intra-Community Valid",
        compute='_compute_vies_valid', store=True, readonly=False,
        tracking=True,
        help='European VAT numbers are automatically checked on the VIES database.')
    perform_vies_validation = fields.Boolean(
        compute='_compute_perform_vies_validation')
    vies_vat_to_check = fields.Char(
        compute='_compute_vies_vat_to_check')
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `vies_valid` | Boolean | Result of VIES check (computed, stored, tracked) |
| `perform_vies_validation` | Boolean | Whether to show VIES UI indicator |
| `vies_vat_to_check` | Char | Normalized VAT string for VIES check |

**EU country code mapping:**

```python
_eu_country_vat = {'GR': 'EL'}  # Greece uses EL in VAT numbers
_eu_country_vat_inverse = {v: k for k, v in _eu_country_vat.items()}
```

---

## Core Validation Methods

### `check_vat()` (constraint)

```python
@api.constrains('vat', 'country_id')
def check_vat(self):
    if self.env.context.get('no_vat_validation'):
        return
    for partner in self:
        if not partner.vat or len(partner.vat) == 1:
            continue
        country = partner.commercial_partner_id.country_id
        if self._run_vat_test(partner.vat, country, partner.is_company) is False:
            raise ValidationError(...)
```

Validates VAT on partner create/write. Skipped when:
- `no_vat_validation` context key is set (external API imports)
- VAT is single character (used as placeholder)

### `_run_vat_test(vat_number, default_country, partner_is_company=True)`

Attempts two-stage VAT validation:
1. Parses country code prefix, validates with that country
2. Falls back to `default_country` if step 1 fails
3. Returns `False` only if both validations fail (not if country code is unrecognized)

### `simple_vat_check(country_code, vat_number)`

```python
@api.model
def simple_vat_check(self, country_code, vat_number):
    if not country_code.encode().isalpha():
        return False
    check_func = getattr(self, 'check_vat_' + country_code, None)
        or getattr(stdnum.util.get_cc_module(country_code, 'vat'), 'is_valid', None)
    if not check_func:
        return bool(self.env['res.country'].search([('code', '=ilike', country_code)]))
    return check_func(vat_number)
```

First tries a local `check_vat_<cc>` method on the model, then falls back to `stdnum` library. Returns True if no validation is available but country code exists.

### `_split_vat(vat)`

Splits `"DE123456788"` into `('de', '123456788')`. Handles 1-char vs 2-char country codes.

### `_build_vat_error_message(country_code, wrong_vat, record_label)`

Formats a user-facing error message with the expected format from `_ref_vat`.

---

## VIES Validation

### `_compute_vies_vat_to_check()`

Determines if the partner's VAT should be checked against VIES:
- Only EU country codes (or `xi` for Northern Ireland)
- Strips whitespace, prepends country code if missing
- Returns empty string for single-char or non-EU VAT

### `_compute_perform_vies_validation()`

```python
@api.depends_context('company')
@api.depends('vies_vat_to_check')
def _compute_perform_vies_validation(self):
    for partner in self:
        company_code = self.env.company.account_fiscal_country_id.code
        partner.perform_vies_validation = (
            to_check
            and to_check[:2].upper() != _eu_country_vat_inverse.get(company_code, company_code)
            and self.env.company.vat_check_vies  # company-level toggle
        )
```

Shows VIES validity indicator only for **foreign** EU partners when the company has VIES checking enabled.

### `_compute_vies_valid()`

```python
@api.depends('vies_vat_to_check')
def _compute_vies_valid(self):
    if not self.env['res.company'].sudo().search_count([('vat_check_vies', '=', True)]):
        self.vies_valid = False
        return
    for partner in self:
        # ... check via stdnum.eu.vat.check_vies(...)
        vies_valid = check_vies(partner.vies_vat_to_check, timeout=10)
        partner.vies_valid = vies_valid['valid']
```

Calls the VIES SOAP service. On failure:
- `OSError`: Connection failed — posts a message to the partner, sets `vies_valid = False`
- `InvalidComponent`: VAT not interpretable by VIES
- `zeep.exceptions.Fault`: VIES service error response

---

## Country-Specific VAT Validators

Custom `check_vat_<cc>()` methods for countries where `stdnum` is insufficient or requires custom logic:

| Country | Method | Notes |
|---------|--------|-------|
| Albania | `check_vat_al()` | Uses `stdnum` + regex for 10-digit format |
| Dominican Republic | `check_vat_do()` | Accepts VAT or Cedula |
| Romania | `check_vat_ro()` | Supports multiple formats (standard, old, 9000-series) |
| Greece | `check_vat_gr()` | Allows test VAT numbers for EDI testing |
| Guatemala | `check_vat_gt()` | Allows test NIT numbers |
| Hungary | `check_vat_hu()` | Supports individual, company, and EU formats |
| Switzerland | `check_vat_ch()` | Custom MOD11 checksum for MWST/TVA/IVA suffixes |
| Ireland | `check_vat_ie()` | Delegates to stdnum |
| Mexico | `check_vat_mx()` | RFC validation with date extraction |
| Norway | `check_vat_no()` | MOD11 checksum, 9 digits, optional MVA suffix |
| Peru | `check_vat_pe()` | MOD11 checksum, 11 digits |
| Philippines | `check_vat_ph()` | 11-17 digits with branch code |
| Russia | `check_vat_ru()` | 10-digit and 12-digit formats with MOD11/MOD10 |
| Turkey | `check_vat_tr()` | TC Kimlik or VKN via stdnum |
| Saudi Arabia | `check_vat_sa()` | ZATCA spec: starts/ends with '3', 15 digits |
| Uruguay | `check_vat_uy()` | RUT with specific checksum |
| Venezuela | `check_vat_ve()` | Multiple TIN types (V, E, C, J, P, G) with checksum |
| India | `check_vat_in()` | GSTIN 15-char regex patterns |
| Japan | `check_vat_t()` | When `country_id.code == 'JP'` |
| Brazil | `check_vat_br()` | CPF or CNPJ via stdnum |
| Costa Rica | `check_vat_cr()` | CEDULA formats (9-12 digits) |
| Germany | `check_vat_de()` | VAT or Steuerummer via stdnum |
| Israel | `check_vat_il()` | IDNr via stdnum |
| Indonesia | `check_vat_id()` | 15/16 digit format with Luhn checksum |
| Vietnam | `check_vat_vn()` | 10-digit (tax ID), 13-digit (branch), 12-digit (CCCD/ciph) |
| Taiwan | `check_vat_tw()` | Custom 8-digit with MOD5 and special 7th-digit rules |

---

## Fiscal Position Extension

### `account.fiscal.position` (extension)

**`adjust_vals_country_id(vals)`**

When `foreign_vat` is set but `country_id` is not, auto-detects the country from the first two characters of the VAT number and assigns it.

**`_validate_foreign_vat()` (constraint)**

Validates that the foreign VAT's country code matches either:
- A country in the fiscal position's `country_group_id`, or
- The fiscal position's own `country_id`

**`_get_vat_valid(delivery, company=None)` (override)**

Extends the fiscal position's VAT validity check. If VIES validation is required for the delivery partner (foreign EU partner with a fiscal position), also requires `delivery.vies_valid` to be True.

---

## L4 Notes

- **`no_vat_validation` context:** Critical for API integrations. External systems (e.g., Shopify connector) may push VAT numbers in formats Odoo cannot validate. Using this context bypasses the constraint.
- **VIES timeout:** 10 seconds. Connection failures are caught and stored as partner messages — they do not block the user.
- **VIES vs simple check:** Simple check (`simple_vat_check`) validates format/check digit locally. VIES validates against the EU's official database — it confirms the business is registered for VAT in that country.
- **`vies_valid` is stored:** The computed value is stored, so it persists without re-querying VIES on every read. It is recomputed when `vies_vat_to_check` changes.
- **Child partner inheritance:** `if partner.parent_id and partner.parent_id.vies_vat_to_check == partner.vies_vat_to_check: partner.vies_valid = partner.parent_id.vies_valid` — child contacts inherit the company's VIES status.
- **Import mode:** During file import (`import_file` context), `_compute_vies_valid` is deferred (via `remove_to_compute`) because VIES calls are too slow for bulk imports.
- **`xi` VAT prefix:** Northern Ireland uses `XI` prefix post-Brexit. This is in `_region_specific_vat_codes` so it triggers VIES checking even though it's not an EU country code.
- **stdnum library:** Odoo uses the `python-stdnum` library for most country validations. The `stdnum.util.get_cc_module(cc, 'vat')` pattern dynamically loads the correct country module.
