---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #tax
  - #fiscal
  - #partner
---

# base_vat — VAT Number Validation

## Module Overview

| Attribute | Value |
|---|---|
| **Technical Name** | `base_vat` |
| **Version** | `2.0` |
| **Category** | `Accounting/Accounting` |
| **Depends** | `account` |
| **License** | `LGPL-3` |
| **Models Extended** | `res.partner`, `res.company`, `res.config.settings`, `res.country` |
| **Inheritance** | Classic (`_inherit`) |

`base_vat` provides two-tiered VAT/Tax Identification Number (TIN) validation for partner records:

1. **Offline syntax validation** — Per-country format and checksum rules via the `python-stdnum` library (always active, on every partner save).
2. **Online VIES validation** — Live lookup against the EU VIES (VAT Information Exchange System) database, gated by the `vat_check_vies` company toggle.

The module extends `res.partner` with a `vies_valid` tracked field, per-country custom validators, and tight integration with `account` fiscal positions.

---

## Module Structure

```
base_vat/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── res_partner.py          # 827 lines — all VAT logic
│   ├── res_country.py          # has_foreign_fiscal_position
│   ├── res_company.py          # vat_check_vies
│   └── res_config_settings.py  # vat_check_vies wizard mirror
├── views/
│   ├── res_partner_views.xml
│   └── res_config_settings_views.xml
├── tests/
│   └── test_vat_numbers.py
└── i18n/
    └── base_vat.pot (+ 50 .po files)
```

---

## Models

### res.company — Company Settings

**File:** `models/res_company.py`

```python
class ResCompany(models.Model):
    _inherit = 'res.company'

    vat_check_vies = fields.Boolean(string='Verify VAT Numbers')
```

**Field: `vat_check_vies`**
- Type: `Boolean`, stored on `res.company`
- Default: `False`
- Scope: Company-level. Enables live VIES validation for all partners in this company's scope.
- When `True`: `_compute_vies_valid` performs live SOAP calls to the EU VIES service on every partner VAT write.
- When `False` (default): Only offline syntax checks run; `vies_valid` stays `False`.

---

### res.config.settings — Settings Wizard

**File:** `models/res_config_settings.py`

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    vat_check_vies = fields.Boolean(
        related='company_id.vat_check_vies',
        readonly=False,
        string='Verify VAT Numbers'
    )
```

- Type: `Boolean`, related to `res.company.vat_check_vies`
- `readonly=False` allows writing through the settings wizard
- Positioned in the accounting settings form via `views/res_config_settings_views.xml`, inheriting `account.res_config_settings_view_form`

---

### res.country — Foreign Fiscal Position Flag

**File:** `models/res_country.py`

```python
class ResCountry(models.Model):
    _inherit = 'res.country'

    has_foreign_fiscal_position = fields.Boolean(
        compute='_compute_has_foreign_fiscal_position',
        store=True
    )

    @api.depends_context('company')
    def _compute_has_foreign_fiscal_position(self):
        for country in self:
            country.has_foreign_fiscal_position = self.env['account.fiscal.position'].search([
                *self._check_company_domain(self.env.company),
                ('foreign_vat', '!=', False),
                ('country_id', '=', country.id),
            ], limit=1)
```

**Field: `has_foreign_fiscal_position`**
- Type: `Boolean`, computed, stored (`store=True`)
- Depends on: `@api.depends_context('company')`
- Compute logic: `True` if any `account.fiscal.position` record exists for this country with `foreign_vat` set (not `False`), scoped to the current company.
- Purpose: Signals to `_get_vat_required_valid` that this country has a fiscal position requiring valid VAT, even if the country is not in the EU. This enforces VIES validation for non-EU fiscal positions.
- Performance: Stored to avoid a `search()` call per country on every partner or invoice computation.

---

### res.partner — Core VAT Logic

**File:** `models/res_partner.py` (827 lines)

Extends `res.partner` via `_inherit = 'res.partner'`. This class is loaded after `account` extends `res.partner`, so `base_vat`'s overrides of `_run_vat_checks` and `_get_vat_required_valid` take effect after `account`'s stubs.

#### Fields Added / Modified

```python
vies_valid = fields.Boolean(
    string="Intra-Community Valid",
    compute='_compute_vies_valid', store=True, readonly=False,
    tracking=True,
    help='European VAT numbers are automatically checked on the VIES database.',
)
perform_vies_validation = fields.Boolean(
    compute='_compute_perform_vies_validation'
)
country_id = fields.Many2one(inverse="_inverse_vat", store=True)
vat = fields.Char(inverse="_inverse_vat", store=True)
```

**`vies_valid`** — Computed Boolean, stored, tracked
- Compute: `_compute_vies_valid`; depends on `vat` field
- Context dependency: `@api.depends_context('company')`
- When `True`: VIES confirmed this VAT is valid and currently allocated
- When `False`: VIES check failed, was not performed, or was not applicable
- Tracking: Changes post to partner chatter via `tracking=True` (mail.thread integration)

**`perform_vies_validation`** — Computed Boolean, not stored
- Compute: `_compute_perform_vies_validation`; depends on `vat` field
- Context dependency: `@api.depends_context('company')`
- Logic:
  ```python
  to_check = partner.vat
  company_code = self.env.company.account_fiscal_country_id.code
  partner.perform_vies_validation = (
      to_check
      and not to_check[:2].upper() == company_code
      and self.env.company.vat_check_vies
  )
  ```
- Returns `True` only when: VAT is set, VAT prefix differs from company's fiscal country code, and `vat_check_vies=True` on the company
- Used exclusively for UI visibility control (`invisible="not perform_vies_validation"`)

**`vat` and `country_id` inverses**
- Both have `inverse="_inverse_vat"` which triggers `self._check_vat()`
- `store=True` means the formatted/normalized VAT is persisted after every write

---

## Core Validation Method Chain

### `_inverse_vat` → `_check_vat` (account)

```
Partner write / create
    └── _inverse_vat()
          └── _check_vat(validation='error')         [account/models/partner.py]
                └── _run_vat_checks(...)             [base_vat override]
                      ├── _split_vat(vat)
                      ├── EU / EU_PREFIX handling
                      ├── GR → EL normalization
                      ├── _format_vat_number(...)
                      ├── _check_vat_number(...)
                      │     └── check_vat_<cc>() or stdnum.is_valid()
                      ├── double-prefix detection
                      ├── recursive EU check fallback
                      └── _build_vat_error_message(...)
                            └── raises ValidationError on failure
```

On form onchange (`@api.onchange`):
```
_onchange_vat()
    └── _check_vat(validation=False)  # format-only, no error raised
```

---

### `_run_vat_checks(self, country, vat, partner_name='', validation='error')`

**Signature:**
```python
@api.model
def _run_vat_checks(self, country, vat, partner_name='', validation='error'):
```

**Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `country` | `res.country` record | — | Partner's country (from `commercial_partner_id.country_id`) |
| `vat` | `str` | — | Raw VAT string as entered by user |
| `partner_name` | `str` | `''` | Used for error message labelling only |
| `validation` | `str` | `'error'` | `'error'` → raise on invalid; `False` → format-only; `'setnull'` → clear on invalid |

**Returns:** `tuple(vat_to_return: str, code_to_check: str)`

**Step-by-step logic:**

**Step 1 — Guard clauses:**
- No `country` or empty `vat` → return unchanged
- Single-character VAT:
  - `'/'` → return as-is (explicit "no valid VAT" sentinel)
  - `validation=False` → return as-is
  - `validation='setnull'` → return `''`
  - `validation='error'` → raise `ValidationError`

**Step 2 — Context bypass:**
- If context has `no_vat_validation` → skip all validation, return formatted VAT immediately

**Step 3 — `_split_vat(vat)`:**
- Returns `(vat_prefix, vat_number)` — first 2 alpha chars as prefix, rest as number (spaces stripped)
- If first 2 chars are not alpha → prefix is `''`

**Step 4 — EU prefix handling:**
- If VAT starts with `EU` (foreign companies trading with non-EU enterprises), and partner country is not in the `base.europe` country group → return unchanged
- `EU_EXTRA_VAT_CODES_INV` mapping: `{'EL': 'GR', 'XI': 'GB'}` inverts `base`'s `EU_EXTRA_VAT_CODES` to convert VAT prefixes back to ISO codes

**Step 5 — `EU_PREFIX` country group logic:**
```python
eu_prefix_country_group = env['res.country.group'].search([('code', '=', 'EU_PREFIX')], limit=1)
country_code = EU_EXTRA_VAT_CODES_INV.get(vat_prefix, vat_prefix)
if country_code in eu_prefix_country_group.country_ids.mapped('code'):
    if 'EU_PREFIX' in country.country_group_codes and vat_prefix:
        vat = vat_number        # strip prefix from VAT string
        prefixed_country = vat_prefix
    else:
        do_eu_check = True     # fall through to recursive EU check
```
Countries in `EU_PREFIX` group (e.g., Norway, Switzerland) have VAT prefixes that differ from their ISO codes. This block handles prefix normalization before validation.

**Step 6 — GR normalization:**
```python
if prefixed_country == 'GR':
    prefixed_country = 'EL'
```
Greece's ISO code `GR` maps to `EL` in VAT contexts (older EU directive notation).

**Step 7 — `_format_vat_number(code_to_check, vat)`:**
- Applied before checksum validation — normalizes separators, casing, country code formats
- Dispatches to local `format_vat_<cc>()` method or falls back to stdnum's `compact()`

**Step 8 — Double-prefix detection:**
```python
double_prefix = prefixed_country and vat_to_return.startswith(prefixed_country + prefixed_country)
```
If `vat_to_return` starts with `BEBE...` (same country code doubled) → fail immediately regardless of checksum.

**Step 9 — `_check_vat_number(code_to_check, vat)`:**
- Dispatches to `self.check_vat_<cc>()` if it exists, otherwise `stdnum.<cc>.vat.is_valid(vat)`

**Step 10 — Recursive EU check fallback:**
- If `do_eu_check=True` and validation failed, retries with the EU country code from `vat_prefix + vat_number`:
  ```python
  return self._run_vat_checks(
      env['res.country'].search([('code', '=', country_code)], limit=1),
      vat_prefix + vat_number,
      partner_name,
      validation
  )
  ```
- Catches `ValidationError` and re-raises with format hint from `_ref_vat`

---

### `_check_vat_number(self, country_code, vat_number)`

```python
@api.model
def _check_vat_number(self, country_code, vat_number):
```

**Returns:** `bool`

Resolution priority:
1. Local method `check_vat_<country_code.lower()>` on `self` if defined
2. stdnum: `stdnum.util.get_cc_module(country_code, 'vat').is_valid(vat_number)`
3. Default: `True` (allow unknown countries silently)

This dual-dispatch design means countries with complex rules get a custom method; all others transparently use stdnum.

---

### `_compute_vies_valid(self)`

```python
@api.depends('vat')
def _compute_vies_valid(self):
    # @api.depends_context('company') — implicit from _compute_perform_vies_validation
```

**Global VIES guard:**
```python
if not env['res.company'].sudo().search_count([('vat_check_vies', '=', True)]):
    self.vies_valid = False
    return
```
Short-circuits all VIES computation if no company has the feature enabled.

**Per-partner logic:**
1. Empty VAT → `vies_valid = False`
2. Contact inheriting company VAT (`parent_id.vat == partner.vat`) → copies `parent_id.vies_valid` directly (no SOAP call)
3. VIES call: `check_vies(partner.vat, timeout=10)` → `partner.vies_valid = result['valid']`
4. Exceptions:
   - `OSError`: Network/timeout failure → post warning to chatter, set `False`, log warning
   - `InvalidComponent`: VIES could not interpret the VAT number → post warning to chatter, set `False`
   - `zeep.exceptions.Fault`: VIES service error response → post warning with `e.message`, set `False`

The method uses `sudo()` for the global guard but runs as the current user for per-partner checks, ensuring ACLs are respected.

---

### `_compute_perform_vies_validation(self)`

```python
@api.depends_context('company')
@api.depends('vat')
def _compute_perform_vies_validation(self):
```

The `@api.depends_context('company')` is critical — it causes recomputation whenever the active company changes, ensuring correct `account_fiscal_country_id.code` is used.

---

### `_get_vat_required_valid(self, company=None)`

```python
def _get_vat_required_valid(self, company=None):
    # OVERRIDE account
```

Hook extended from `account`. Returns `bool` for fiscal position selection logic.

**Base implementation** (from `account`): Returns `bool(self.vat)`

**Extension** (added by `base_vat`):
```python
if (
    company and company.country_id
    and self.with_company(company).perform_vies_validation
    and (
        'EU' in company.country_id.country_group_codes
        or self.country_id and self.country_id.has_foreign_fiscal_position
    )
):
    vat_required_valid = vat_required_valid and self.vies_valid
```

Enforces VIES validity as a prerequisite for fiscal-position eligibility when:
- Company is in the EU, **or** partner's country has a foreign fiscal position defined
- AND `perform_vies_validation=True` (cross-border + VIES enabled for company)

This hook is called by `account.fiscal.position` selection logic when matching positions to a partner.

---

### `_build_vat_error_message(self, country_code, wrong_vat, record_label)`

```python
@api.model
def _build_vat_error_message(self, country_code, wrong_vat, record_label):
    # OVERRIDE account
```

Builds the `ValidationError` message shown on invalid VAT. Extension points:
- Selects `vat_label` from company's country if `country_id.vat_label` is set
- Appends the expected format hint from `_ref_vat` dictionary

---

### `_onchange_vat(self)`

```python
@api.onchange('vat', 'country_id')
def _onchange_vat(self):
    self._check_vat(validation=False)
```

Fires on form onchange events. Passes `validation=False` which makes `_run_vat_checks` return formatted VAT without raising errors. Provides live normalization feedback (e.g., `CL 760864285` → `76086428-5`) without blocking the user.

---

### `create()` / `write()` — VIES Import Optimization

```python
@api.model_create_multi
def create(self, vals_list):
    res = super().create(vals_list)
    if self.env.context.get('import_file'):
        res.env.remove_to_compute(self._fields['vies_valid'], res)
    return res

def write(self, vals):
    res = super().write(vals)
    if self.env.context.get('import_file'):
        self.env.remove_to_compute(self._fields['vies_valid'], self)
    return res
```

`import_file` context flag suppresses VIES recomputation during bulk data imports. Without this, every imported partner would trigger a live SOAP call to VIES. Always set this context before `base.import` operations.

---

### `_create_contact_parent_company` — VIES Bypass

```python
def _create_contact_parent_company(self):
    new_company = super()._create_contact_parent_company()
    if new_company and self.vies_valid:
        new_company.env.remove_to_compute(self._fields['vies_valid'], new_company)
        new_company.vies_valid = self.vies_valid
    return new_company
```

When a contact with `company_name` clicks **Create Company**, the parent's VAT and `vies_valid` are copied directly rather than re-checked. This avoids a redundant VIES call and preserves validation state.

---

## Country-Specific Validators

All custom validators: `check_vat_<country_code>(self, vat) → bool`

| Country | Method | Key Logic |
|---|---|---|
| `al` Albania | `check_vat_al` | Regex `^[JKLM][0-9]{8}[A-Z]$` + length == 10 |
| `br` Brazil | `check_vat_br` | `stdnum.br.cpf.is_valid` OR `stdnum.br.cnpj.is_valid` |
| `ch` Switzerland | `check_vat_ch` | Regex `E([0-9]{9}\|-[0-9]{3}\.[0-9]{3}\.[0-9]{3})( )?(MWST\|TVA\|IVA)$` + MOD11 checksum; English `VAT` abbreviation rejected |
| `cl` Chile | (stdnum only) | Formatted by `format_vat_cl` — strips dots/CL/spaces, adds hyphen before last digit |
| `co` Colombia | (stdnum only) | Formatted by `format_vat_co` |
| `cr` Costa Rica | `check_vat_cr` | Regex `^(?:[1-9]\d{8}\|\d{10}\|[1-9]\d{10,11})$` |
| `de` Germany | `check_vat_de` | `stdnum.de.vat.is_valid` OR `stdnum.de.stnr.is_valid` (Steuernummer) |
| `do` Dominican Rep. | `check_vat_do` | `stdnum.do.vat.is_valid` OR `stdnum.do.cedula.is_valid` |
| `ec` Ecuador | `check_vat_ec` | `clean()` → uppercase, length 10 or 13, all digits only |
| `gr` Greece | `check_vat_gr` | stdnum + hardcoded test range: `047747210`, `047747220`, `047747270`, `117747270`, `127747270` |
| `gt` Guatemala | `check_vat_gt` | stdnum + regex test range `98[0-9]{10}K` + hardcoded `11201220K`, `11201350K` |
| `hu` Hungary | `check_vat_hu` | Three patterns: company (`\d{8}-[1-5]-\d{2}`), individual (`^8\d{9}$`), EU (`^\d{8}$`) |
| `id` Indonesia | `check_vat_id` | 15 or 16 digits; 15-digit undergoes Luhn checksum on first 9 digits; 16-digit with non-zero first digit accepted without checksum |
| `ie` Ireland | `check_vat_ie` | stdnum only (`# TODO: remove in master`) |
| `il` Israel | `check_vat_il` | `stdnum.il.idnr.is_valid` (Luhn algorithm) |
| `in` India | `check_vat_in` | 5 regex variants for Normal/Composite/Casual/UN-ON Body/NRI/TDS/TCS GSTIN |
| `jp` Japan | `check_vat_jp` | stdnum, strips leading `T` before validation |
| `ma` Morocco | `check_vat_ma` | Exactly 8 digits |
| `mx` Mexico | `check_vat_mx` | Regex with embedded date fields (year/month/day); validates date plausibility (1900/2000+ based on year > 30) |
| `no` Norway | `check_vat_no` | 9-digit integer + weighted checksum (3-2-7-6-5-4-3-2), optional `MVA` suffix stripped |
| `pe` Peru | `check_vat_pe` | 11 digits + weighted checksum (5-4-3-2-7-6-5-4-3-2 pattern) |
| `ph` Philippines | `check_vat_ph` | `\d{3}-\d{3}-\d{3}(-\d{3,5})?$`, length 11–17 |
| `ro` Romania | `check_vat_ro` | Three patterns: TIN1 (natural persons), TIN2 (`9000xxxxxxxx`), stdnum CUI/CIF |
| `rs` Serbia | `check_vat_rs` | stdnum with `RS` prefix stripped first |
| `ru` Russia | `check_vat_ru` | 10-digit (single checksum, weight 2-10) or 12-digit (double checksum, weight 7-2-4-10 and 3-7-2-4-10) |
| `sa` Saudi Arabia | `check_vat_sa` | Regex `^3[0-9]{13}3$` — must start and end with `3`, 15 digits (ZATCA specification) |
| `th` Thailand | `check_vat_th` | `stdnum.th.tin.is_valid` |
| `tr` Turkey | `check_vat_tr` | `stdnum.tr.tckimlik.is_valid` (TC Kimlik No) OR `stdnum.tr.vkn.is_valid` (Vergi Kimlik No) |
| `tw` Taiwan | `check_vat_tw` | 8-digit UBN: weighted multiplication (1/2/1/2/1/2/4/1), sum divisible by 5. Updated Feb 2025 to handle exhausted UBN number ranges |
| `ua` Ukraine | `check_vat_ua` | Length of number (after `UA` strip) must be 8, 10, or 12 |
| `uy` Uruguay | `check_vat_uy` | 12 digits, first 2 chars `01–22`, entity code `001`, check digit via weighted sum |
| `ve` Venezuela | `check_vat_ve` | Kind digit (V/E/C/J/P/G), identifier, Luhn-like checksum; 3 format variants |
| `vn` Vietnam | `check_vat_vn` | 10-digit (enterprise), 13-digit (branch `NNNNN-XXX`), 12-digit (CCCD personal ID from Jul 2025) |

### `format_vat_XX` Methods

| Country | Method | Output |
|---|---|---|
| `eu` | `format_vat_eu` | Passthrough — no transformation |
| `ch` | `format_vat_ch` | stdnum format → strips `CH` prefix |
| `cl` | `format_vat_cl` | Uppercase, strip dots/CL/spaces/dashes, add hyphen before last char |
| `co` | `format_vat_co` | stdnum format, strip dots/dashes, add hyphen before last char |
| `hu` | `format_vat_hu` | Compact, then re-add hyphen for company format `xxxxxxxx-y-zz` |
| `sm` | `format_vat_sm` | stdnum compact → strips `SM` prefix |
| `vn` | `format_vat_vn` | stdnum format for 10-digit enterprise, passthrough for others |

---

## EU_EXTRA_VAT_CODES — Prefix Mapping

**Source:** `base` module (`odoo/addons/base/models/res_partner.py`):
```python
EU_EXTRA_VAT_CODES = {
    'GR': 'EL',   # Greece — older EU directive code
    'GB': 'XI',   # United Kingdom (Northern Ireland protocol)
}
```

**Inverted by `base_vat`:**
```python
EU_EXTRA_VAT_CODES_INV = {v: k for k, v in EU_EXTRA_VAT_CODES.items()}
# {'EL': 'GR', 'XI': 'GB'}
```

Used in `_run_vat_checks` to resolve VAT prefixes back to ISO country codes for stdnum dispatch and country group membership checks.

---

## Context Keys

| Key | Effect |
|---|---|
| `no_vat_validation` | Skip all offline and VIES checks entirely. Use for trusted API integrations only. |
| `import_file` | In `create()` and `write()`: removes `vies_valid` from the compute set via `env.remove_to_compute()`, skipping VIES calls during bulk CSV/XML imports. |
| `company_id` | Used in `_build_vat_error_message` to select the correct company's `vat_label`. |

---

## L4: Performance Considerations

### VIES Network I/O Bottleneck

The most significant performance concern in `base_vat` is the synchronous SOAP call to the EU VIES service on every partner write when `vat_check_vies=True`:

```python
vies_valid = check_vies(partner.vat, timeout=10)
```

| Scenario | Impact | Mitigation |
|---|---|---|
| Single partner save | ~100-500ms per call (network latency) | None — this is intentional for real-time validation |
| Bulk partner creation | N × VIES calls = N × 100-500ms | Set `import_file` context to skip VIES entirely |
| Partner search/browse | No VIES call — `vies_valid` is stored | No action needed |
| Switching active company | `@api.depends_context('company')` invalidates `perform_vies_validation` | Lightweight string ops + company field lookup |

### Global VIES Guard — Critical Optimization

```python
if not env['res.company'].sudo().search_count([('vat_check_vies', '=', True)]):
    self.vies_valid = False
    return
```

This `sudo().search_count()` query runs once per partner in a multi-record `browse()`. For recordsets of 100+ partners, this is a significant overhead because:
- It runs inside `_compute_vies_valid` which is called for every record
- Each call is a separate SQL query (N+1 pattern for the guard check)

**This is a known trade-off**: the guard prevents VIES calls for the common case (no company has VIES enabled), but in multi-company setups where at least one company has VIES enabled, the guard short-circuits only after determining the company has VIES enabled. In practice, since `vies_valid` is stored, subsequent reads are instant.

### Bulk Import Performance

```python
# Good: Suppress VIES during import
env['res.partner'].with_context(import_file=True).load(['vat', 'country_id'], rows)

# Bad: Each row triggers VIES call
env['res.partner'].create(vals_list)  # No context bypass
```

For CSV/XML imports of 10,000+ partner records, always use the `import_file` context. Without it, every record triggers a 10-second timeout VIES call on failure (OSError), compounding latency.

### Contact Inheritance Optimization

```python
if partner.parent_id and partner.parent_id.vat == partner.vat:
    partner.vies_valid = partner.parent_id.vies_valid
    continue  # Skip VIES SOAP call entirely
```

This short-circuit prevents redundant SOAP calls when a contact shares the company's VAT number. The parent-company VAT is assumed to be already validated.

### zeep Import Lazy Loading

```python
def _compute_vies_valid(self):
    # ...
    from odoo.tools import zeep  # noqa: PLC0415  # imported INSIDE the method
    try:
        vies_valid = check_vies(partner.vat, timeout=10)
```

The zeep SOAP client is imported **inside** `_compute_vies_valid`, not at module level. This avoids the overhead of loading the zeep library and all its dependencies (HTTP client, XML parser, WSDL cache) when VIES is disabled. The `# noqa: PLC0415` comment suppresses Pylint's "import not at top of file" warning.

---

## L4: Odoo 18 → 19 Migration Changes

### Module Manifest

| Attribute | Odoo 18 | Odoo 19 |
|---|---|---|
| Version | `1.2` | `2.0` |
| Category | `Accounting/Accounting` | Same |
| Depends | `account` | Same |
| License | `LGPL-3` | Same |

The version increment from `1.2` to `2.0` indicates significant new functionality (likely VIES integration improvements and new country validators).

### VIES Integration Changes

**Odoo 18** used `zeep` for SOAP calls but imported it at module level:
```python
# Odoo 18 (inferred)
from stdnum.eu.vat import check_vies
import zeep  # imported at module top
```

**Odoo 19** moves the zeep import inside the method for lazy loading:
```python
# Odoo 19
from odoo.tools import zeep  # noqa: PLC0415 — imported inside _compute_vies_valid
```

### Ireland Validator Deprecation

```python
# TODO: remove in master
def check_vat_ie(self, vat):
    return stdnum.util.get_cc_module('ie', 'vat').is_valid(vat)
```

The `# TODO: remove in master` comment indicates the Ireland-specific `_ie_check_char()` method was removed in Odoo 19, replacing it with stdnum's implementation. The TODO suggests full stdnum alignment is ongoing.

### Greece Test VAT Ranges

Odoo 19 extends the Greece test VAT range with additional codes:
```python
# Odoo 18 (inferred): smaller range
greece_test_vats = ('047747270', '047747210', '047747220')

# Odoo 19: Extended
greece_test_vats = ('047747270', '047747210', '047747220', '117747270', '127747270')
```

This supports broader EDI testing scenarios.

### Indonesia VAT (January 2024 Format Change)

The `check_vat_id` validator was enhanced in Odoo 18→19 to support the new 15/16 digit format introduced January 2024:
- Old format: 15 digits with Luhn checksum
- New format: 16 digits without mandatory checksum if first digit is non-zero
- Both formats accepted

### Taiwan UBN (February 2025 Update)

Odoo 19 added updated Taiwan UBN validation logic to handle the February 2025 change where exhausted UBN number ranges now use a division-by-5 checksum instead of division-by-10:
```python
logic_multiplier = [1, 2, 1, 2, 1, 2, 4, 1]
```

### Vietnam VAT (CCCD Format Support)

Odoo 19 added 12-digit CCCD (Citizen Identification Card) support for Vietnam, anticipating the July 2025 transition from 13-digit format to 12-digit national ID as the personal tax identifier.

### Stored `vies_valid` vs Non-Stored

In Odoo 18, `vies_valid` may not have been stored. Odoo 19 explicitly stores it:
```python
vies_valid = fields.Boolean(
    compute='_compute_vies_valid', store=True, readonly=False, tracking=True
)
```

Storing `vies_valid` means:
- VIES results are persisted — no re-query on every read
- `_get_vat_required_valid` can rely on `vies_valid` without triggering recomputation
- Import of partner data with pre-validated VAT numbers is possible

### `_create_contact_parent_company` Override

Odoo 19 explicitly handles `vies_valid` propagation when creating a company from a contact. This may not have existed in Odoo 18, meaning each newly created company would trigger a fresh VIES query.

---

## L4: Security Analysis

### VIES is Informational, Not Blocking

Unlike syntactic validation (which raises `ValidationError`), VIES failures only set `vies_valid=False`. This design choice:
- Allows partners with temporarily unreachable VAT numbers to still be saved
- Prevents VIES service outages from blocking business operations
- Relies on downstream fiscal position logic (`_get_vat_required_valid`) to enforce VIES requirements when truly needed

### VIES Network Dependency

```python
except (OSError, InvalidComponent, zeep.exceptions.Fault) as e:
    if partner._origin.id:
        msg = ""
        if isinstance(e, OSError):
            msg = _("Connection with the VIES server failed...")
        elif isinstance(e, InvalidComponent):
            msg = _("The VAT number %s could not be interpreted...")
        elif isinstance(e, zeep.exceptions.Fault):
            msg = _('The request... VIES service has responded: %s', e.message)
        partner._origin.message_post(body=msg)
    partner.vies_valid = False
```

VIES failures are surfaced in partner chatter (message_post), giving administrators visibility without blocking saves. The `_origin.id` guard prevents message posting on new records that haven't been committed.

### SOAP Fault Surface Area

ZEOP faults (`zeep.exceptions.Fault`) expose the raw VIES service error message in user-facing UI text. While not a direct security vulnerability, malformed VIES responses could theoretically display unexpected content. The message is wrapped in a standard `_()` translation call, providing a layer of sanitization.

### `no_vat_validation` Context — Bypass Risk

```python
if not validation or self.env.context.get('no_vat_validation'):
    return vat_to_return, code_to_check
```

This context key bypasses ALL validation. It is safe when used programmatically for trusted API integrations, but could be exploited if exposed through a user-facing form. The `no_vat_validation` context should **never** be set globally.

### VIES Data Privacy

VIES queries transmit VAT numbers to `ec.europa.eu`. Per EU GDPR considerations:
- VAT numbers are not typically considered sensitive PII
- The VIES system is a public EU tax authority service
- No other partner data is transmitted — only the VAT number
- Logs should be reviewed for VAT number leakage (the code logs `partner.vat` on failure)

### ACL and Access Rights

`vies_valid` has `tracking=True`, meaning changes to this field are recorded in the partner's chatter. This provides an audit trail:
- Who changed the VAT number
- When it was validated or invalidated
- Any VIES service errors

### Test Isolation

Tests mock `check_vies` to avoid live VIES calls and network dependency in CI:
```python
# Mocked in tests
with patch('odoo.addons.base_vat.models.res_partner.check_vies') as mock_vies:
    mock_vies.return_value = {'valid': True}
```

---

## L4: VIES SOAP Architecture

### How VIES Validation Works

```
Partner write (vat_check_vies=True)
    └─ _inverse_vat()
        └─ _check_vat()                    [account]
            └─ _run_vat_checks()           [base_vat] — offline syntax check
                └─ (passes) → VAT stored
    └─ _compute_vies_valid                  [base_vat] — online check
        └─ (global guard: any company has vat_check_vies=True?)
            └─ No → return (skip)
            └─ Yes → check_vies(vat, timeout=10)  [stdnum.eu.vat]
                └─ zeep SOAP client → ec.europa.eu
                    ├─ valid=True  → partner.vies_valid = True
                    ├─ valid=False → partner.vies_valid = False
                    └─ OSError/InvalidComponent/Fault → partner.vies_valid = False + message_post
```

### zeep SOAP Client Details

```python
from stdnum.eu.vat import check_vies
```

`check_vies` from stdnum is a thin wrapper around zeep. It:
1. Constructs a SOAP envelope with the VAT number
2. Sends POST to `http://ec.europa.eu/taxation_customs/vies/services/checkVatService`
3. Parses the XML response for `<valid>True/False</valid>`
4. Returns `{'valid': bool, 'name': str, 'address': str}` on success

### Timeout Handling

```python
check_vies(partner.vat, timeout=10)
```

The 10-second timeout is set on the zeep transport layer. An `OSError` (timeout or network unreachable) sets `vies_valid=False` and posts a warning. This means slow/unreachable VIES does not block partner saves.

### VIES Rate Limiting

The EU VIES service has rate limits per IP. For high-volume Odoo instances:
- Odoo does not implement client-side rate limiting for VIES
- Multiple concurrent partner writes can trigger burst VIES calls
- Consider implementing a queue_job-based VIES checker for high-volume scenarios

---

## L4: Fiscal Position Integration (`_get_vat_required_valid`)

### The `_get_vat_required_valid` Hook

This method is the bridge between VAT validation and tax automation:

```python
def _get_vat_required_valid(self, company=None):
    # Called by: account.fiscal.position._compute_business_fields()
    # Returns: bool — whether this partner's VAT must be VIES-validated for fiscal position selection
```

**Call chain:**
```
account.move (invoice creation)
    └─ _lines._compute_tax_ids()
        └─ fiscal_position._compute_business_fields()
            └─ partner._get_vat_required_valid(company)
                └─ (if True) → partner.vies_valid must be True
```

### Fiscal Position Selection Logic

When `account.fiscal.position` records have `use_company_vat_on_vies_validation=True` (introduced in account module), the selection algorithm:

1. Matches `fiscal_position.country_id` against partner's country
2. If `foreign_vat` is set, checks if partner's VAT starts with the fiscal position's country code
3. Calls `_get_vat_required_valid` to determine if VIES validity is a prerequisite
4. If VIES validity is required but `vies_valid=False`, the fiscal position is **not applied**

This prevents incorrect tax rates from being applied when a foreign partner's VAT cannot be confirmed via VIES.

---

## L4: Edge Cases

| Scenario | Behavior |
|---|---|
| VAT = `'/'` (single slash) | Accepted as explicit "no valid VAT" sentinel. Other single chars raise `ValidationError` |
| Partner has no country | No validation performed, any VAT string accepted as-is |
| Double country prefix (`BEBE...`) | Validation fails immediately, regardless of checksum |
| Greece VAT (`GR` prefix) | Normalized to `EL` internally. Both accepted on input; output always `EL` |
| Contact with same VAT as parent company | Copies `parent_id.vies_valid` without VIES call |
| Indonesia 16-digit VAT | Accepted without checksum if first digit is non-zero. 15-digit undergoes Luhn check on first 9 digits |
| Norway with `MVA` suffix | Suffix stripped before validation; `MVA` is informational only |
| Taiwan UBN (Feb 2025 update) | Division-by-5 checksum for new UBN ranges; division-by-5 also if 7th digit is 7 with alternative sum |
| Uruguay RUT | Prefix `UY` stripped, validated as 12-digit RUT with entity code `001` |
| Guatemala test range | `98XXXXXXXXXXK` + `11201220K`, `11201350K` accepted without stdnum |
| Greece test range | `0477472XX` accepted without stdnum (EDI integration testing) |
| Chile VAT reformatting | `CL 760864285` → `76086428-5` on save (hyphen added, all separators/prefix stripped) |
| `create_company()` from contact | Copies `vies_valid=True` to new company without re-querying VIES |
| VIES enabled but company has no `account_fiscal_country_id` | `perform_vies_validation=False` → no VIES enforcement |
| Switzerland without `MWST/TVA/IVA` suffix | Rejected even though `VAT` is more commonly known internationally |
| `no_vat_validation` context during normal form save | Validation still runs because `_inverse_vat()` is triggered by the inverse, not the context |
| VIES called on partner without `vat` | Short-circuits immediately: `if not partner.vat: partner.vies_valid = False; continue` |
| VIES called on archived company | `sudo().search_count()` includes archived companies if the user has access |

---

## Views

**`views/res_partner_views.xml`** (priority 15, inherits `base.view_partner_form`):
```xml
<field name="vat" class="oe_inline"/>
<div name="vat_vies_container">
    <field name="vat"/>                      <!-- moved into container -->
    <field name="vies_valid" invisible="not perform_vies_validation"/>
</div>
```
- Adds `vies_valid` badge inline next to the VAT field, visible only when VIES is relevant
- Changes label to `"Tax ID"` via `<label for="vat" string="Tax ID"/>`

**`views/res_config_settings_views.xml`** (inherits `account.res_config_settings_view_form`):
```xml
<setting id="vies_service_setting"
         title="If this checkbox is ticked, the default fiscal position that applies
                will depend upon the output of the verification by the European VIES Service."
         documentation="/applications/finance/accounting/taxation/taxes/vat_validation.html">
    <field name="vat_check_vies"/>
</setting>
```
- Positioned after the EU service setting
- Includes a link to the official Odoo documentation on VAT validation

---

## Test Coverage

**File:** `tests/test_vat_numbers.py`

Test classes:
- `TestStructure` — Standard test suite (all tests pass without network access)
- `TestStructureVIES` — VIES live tests, tagged `-standard`, `external` (skipped in normal CI via `@tagged('-standard', 'external')`)

Key test cases:

| Test | What it validates |
|---|---|
| `test_peru_ruc_format` | 11-digit RUC with check digit; invalid length raises |
| `test_vat_country_difference` | MX partner with MX VAT stored as-is without reformatting |
| `test_missing_company_country` | VIES not enforced when company has no country set |
| `test_parent_validation` | Contact inherits parent `vies_valid` without VIES re-check |
| `test_vat_syntactic_validation` | Country mismatch raises; no country → allow all |
| `test_vat_eu` | `EU` prefix accepted for non-EU partner countries |
| `test_nif_de` | German Steuernummer (`201/123/12340`) accepted alongside VAT |
| `test_rut_uy` | Uruguay RUT with hyphens/spaces/prefix normalization |
| `test_vat_vn` | 10/12/13-digit Vietnam formats |
| `test_vat_tw` | Taiwan UBN with Feb 2025 logic |
| `test_gr_changes` | Greece `GR` → `EL` normalization |
| `test_no_vies_revalidation_when_creating_company_from_contact` | `create_company()` copies `vies_valid` |
| `test_vat_notEU_with_EU_vat` | Non-EU partner with valid EU VAT number |
| `test_cl_hyphen` | Chile VAT reformatting (`CL 760864285` → `76086428-5`) |
| `test_co_hyphen` | Colombia NIT reformatting (`213.123.4321` → `213123432-1`) |

---

## Cross-Module Integration

### `account`

`base_vat` overrides two stubs left by `account/models/partner.py`:

**`_run_vat_checks`**: Replaces `account`'s no-op stub that returned `(vat, country_code)` unchanged. This override is the primary entry point for all VAT validation.

**`_get_vat_required_valid`**: Extends `account`'s base hook (which returns `bool(self.vat)`) to add VIES-dependent validity for EU and foreign-fiscal-position scenarios. This is the link between VAT validation and `account.fiscal.position` auto-selection.

**`_build_vat_error_message`**: Injects country-specific format hints from `_ref_vat` into error messages.

**`_check_vat`**: Provided by `account`, calls `_run_vat_checks` and has the `vat != partner.vat` guard.

### `base`

- Imports `EU_EXTRA_VAT_CODES` (`GR→EL`, `GB→XI`) for prefix normalization
- Extends `res.company` with `vat_check_vies`
- `_create_contact_parent_company` in `base` is overridden to propagate `vies_valid`

### `stdnum` Library

All country validators delegate to `python-stdnum`. Key modules used:

| stdnum module | Purpose |
|---|---|
| `stdnum.eu.vat.check_vies` | Live VIES SOAP lookup |
| `stdnum.util.get_cc_module(cc, 'vat')` | Per-country VAT validator and formatter |
| `stdnum.util.clean` | Strips separators from VAT strings |
| `stdnum.luhn` | Luhn checksum algorithm (ID, IL, VN, UY, etc.) |
| `stdnum.exceptions` | `InvalidComponent`, `InvalidChecksum`, `InvalidFormat` |
| `stdnum.br.cpf` / `stdnum.br.cnpj` | Brazil |
| `stdnum.de.stnr` | German Steuernummer |
| `stdnum.tr.tckimlik` / `stdnum.tr.vkn` | Turkish tax IDs |

---

## Critical Design Decisions (L4 Summary)

1. **VIES is informational, not blocking**: Unlike syntactic validation (which raises `ValidationError`), VIES failures only set `vies_valid=False`. This design allows partners with temporarily unreachable VAT numbers to still be saved. Downstream logic (e.g., invoice fiscal position selection via `_get_vat_required_valid`) enforces VIES requirements when needed.

2. **No VIES debouncing**: `_compute_vies_valid` runs synchronously on every partner write. For high-volume import scenarios, always set `import_file` context to suppress VIES calls.

3. **`EU_PREFIX` country group**: Countries like Norway (NO), Switzerland (CH), and Iceland (IS) are not in the EU but have VAT number prefixes that are validated by EU-country-specific rules. The `EU_PREFIX` country group + `EU_EXTRA_VAT_CODES_INV` mapping handles these. Adding a new country to `EU_PREFIX` in a localization module automatically activates prefix-stripping logic in `base_vat`.

4. **`has_foreign_fiscal_position` stored**: Computing this per-country per-company on every partner or invoice operation would be expensive. Stored with `@api.depends_context('company')` for company-change invalidation.

5. **`GR` → `'EL'` normalization**: Greece's ISO code is `GR` but its VAT directive prefix is `EL`. Both are accepted on input, and output is always normalized to `EL`. This single substitution touches every Greece-related VAT string.

6. **VIES result is contact→company inheritable**: When a contact shares a VAT number with its parent company, the VIES result is copied rather than re-checked. This avoids redundant SOAP calls and ensures that child contacts of a validated company are immediately marked valid.

7. **zeep import inside method**: `from odoo.tools import zeep` is imported inside `_compute_vies_valid` rather than at module top level. This avoids a heavy SOAP client import in all environments when VIES is disabled.

8. **Test mocking**: `TestStructureVIES` patches `check_vies` with the real stdnum implementation, but `TestStructure` mocks it with a constant-returning function so all tests run without network access.

---

## Related Documentation

- [Core/BaseModel](core/basemodel.md) — ORM foundation, `_inherit` patterns
- [Modules/Account](modules/account.md) — Fiscal position integration, `account.move` tax computation
- [Core/Fields](core/fields.md) — `tracking=True`, `store=True`, `readonly=False` field attributes
- [Modules/base_iban](modules/base_iban.md) — Analogous bank account validation module
- [Patterns/Inheritance Patterns](patterns/inheritance-patterns.md) — `_inherit` vs `_inherits`
