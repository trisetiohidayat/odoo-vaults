---
tags:
  - #odoo19
  - #modules
  - #accounting
  - #iban
  - #bank-accounts
---

# base_iban — IBAN Bank Accounts

> Validates IBAN format, performs MOD-97 checksum verification, auto-formats IBAN display, and parses IBAN sub-components (BBAN, bank code, branch code, account number) per country-specific template.

---

## Module Facts

| Attribute         | Value                                        |
|-------------------|----------------------------------------------|
| **Technical Name**| `base_iban`                                  |
| **Category**      | Accounting / Accounting                       |
| **Depends**       | `account`, `web`                              |
| **License**       | LGPL-3                                        |
| **Author**        | Odoo S.A.                                     |

**Purpose**: Provides the foundation for IBAN (International Bank Account Number) validation, formatting, and structural parsing across all Odoo modules. It extends `res.partner.bank` with IBAN-aware behavior and adds a live-validation frontend widget.

---

## Architecture

```
base_iban
├── models/
│   ├── __init__.py              # Imports res_partner_bank; re-exports helper functions
│   └── res_partner_bank.py     # ResPartnerBank override + module-level helpers
├── views/
│   ├── partner_view.xml         # Adds widget="iban" to acc_number field in bank form
│   └── setup_wizards_view.xml   # Adds widget="iban" to account.setup.bank.manual.config
├── static/src/
│   ├── components/iban_widget/
│   │   ├── iban_widget.js       # IbanWidget (extends CharField)
│   │   └── iban_widget.xml     # QWeb template: input + validation icons
│   └── tests/
│       ├── base_iban_test_helpers.js
│       ├── iban_widget.test.js
│       └── mock_server/mock_models/res_partner_bank.js
└── data/
    └── res_partner_bank_demo.xml  # 3 demo IBAN bank accounts (BE, SI)
```

### Inheritance Chain

```
res.partner.bank (base)
    └── base_iban: ResPartnerBank  (_inherit)
            └── account: ResPartnerBank  (_inherit + mail.thread)
```

The `account` module's `res.partner.bank` sits on top of the MRO and adds `mail.thread`, activity tracking, `allow_out_payment`, `journal_id`, and QR-code methods. `base_iban` slots in between via `_inherit`, adding only IBAN-specific logic without disturbing the account layer.

---

## Module-Level Helper Functions

All defined at module scope in `models/res_partner_bank.py` — importable and reusable by other modules.

### `normalize_iban(iban)`

```python
def normalize_iban(iban):
    return re.sub(r'[\W_]', '', iban or '')
```

Strips all non-alphanumeric characters (spaces, dashes, underscores) and returns uppercase. Used as the canonical internal representation. Every other function in the module calls this before processing.

**Edge cases**:
- Passes through `None` safely (returns `''`).
- Handles unicode NBSP (`\u00a0`) since Python's `\W` matches it.

### `pretty_iban(iban)`

```python
def pretty_iban(iban):
    try:
        validate_iban(iban)
        iban = ' '.join([iban[i:i + 4] for i in range(0, len(iban), 4)])
    except ValidationError:
        pass
    return iban
```

Re-formats a validated IBAN into groups of 4 characters separated by single spaces: `BE62351007947138` becomes `BE62 3510 0794 7138`. Silently returns the input unchanged if validation fails — so it is safe to call on arbitrary strings.

**Use**: Stored `acc_number` values are always kept in pretty format after successful validation.

### `get_bban_from_iban(iban)`

```python
def get_bban_from_iban(iban):
    return normalize_iban(iban)[4:]
```

Returns the Basic Bank Account Number — all characters after the 2-letter country code and 2 check digits. **Note**: BBAN is not the same as the domestic account number; the mapping between BBAN and domestic format varies by country (see [ecbs.org](http://www.ecbs.org/iban.htm)).

**Example**: `DE89370400440532013000` → stripped to `DE89370400440532013000` → `370400440532013000` (everything after `DE89`)

**Failure mode**: Returns garbage if the input is not a valid IBAN — always call `validate_iban` first.

### `get_iban_part(iban, number_kind)`

```python
def get_iban_part(iban, number_kind)
```

Decomposes an IBAN into sub-components using country-specific template masks.

#### Supported `number_kind` values

| Kind               | Mask Char | Meaning                                    |
|--------------------|-----------|--------------------------------------------|
| `'bank'`           | `B`       | National bank identifier code               |
| `'branch'`         | `S`       | Branch code                                |
| `'account'`        | `C`       | Account number                             |
| `'check'`          | `k`       | ISO 7064 MOD-97 check digits (global)      |
| `'check_national'` | `K`       | National check digits (e.g. Italy)         |
| `'account_type'`   | `T`       | Account type (Bulgaria, Guatemala)         |
| `'balance_account'`| `A`       | Balance Account Number (Belarus)           |
| `'fiscal_code'`   | `F`       | Tax ID / Kennitala (Iceland)              |
| `'reserved'`       | `R`       | Reserved zero (Turkey)                     |

#### Algorithm

1. Normalizes the IBAN (strip whitespace, uppercase).
2. Extracts 2-letter country code: `country_code = iban[:2].lower()`.
3. Looks up `_map_iban_template[country_code]`, strips spaces, removes country code prefix from both template and IBAN (`[2:]`).
4. Zips the remaining characters with the template mask; returns characters where the mask matches `mask_char`.

**Example** — Italy:

```
iban = 'IT60X0542811101000000123456'
template = 'ITkk KBBB BBSS SSSC CCCC CCCC CCC'

get_iban_part(iban, 'bank')   → '05428'
get_iban_part(iban, 'branch') → '11101'
get_iban_part(iban, 'account') → '000000123456'
```

**Returns `False`** if `number_kind` is not in `iban_part_map` or if the country code has no template entry.

### `validate_iban(iban)`

```python
def validate_iban(iban)
```

Full IBAN validation with three checks:

| Step | Check                         | Failure Message                                              |
|------|-------------------------------|-------------------------------------------------------------|
| 1    | Non-empty                     | `"There is no IBAN code."`                                  |
| 2    | Country code in map (75 countries) | `"The IBAN is invalid, it should begin with the country code"` |
| 3    | Length matches template + alphanumeric | Template shown with sample format                        |
| 4    | MOD-97 checksum: `digits % 97 == 1` | `"This IBAN does not pass the validation check, please verify it."` |

#### MOD-97 Algorithm Detail

```python
check_chars = iban[4:] + iban[:4]        # Move first 4 chars to end
digits = int(''.join(str(int(char, 36)) for char in check_chars))  # Base 36: A=10...Z=35
if digits % 97 != 1:
    raise ValidationError(...)
```

- `int(char, 36)` converts each IBAN character to its base-36 numeric value (`0-9` → itself, `A-Z` → `10-35`).
- This large integer is the result of treating the rearranged IBAN as a base-36 number.
- ISO 13616 mandates remainder `1` for a valid IBAN.
- The check catches all single-character transposition errors and most other errors.

**Performance**: For a 34-character max IBAN, the integer can be ~155 bits. Modern Python handles this in microseconds. No DB queries involved.

---

## `_map_iban_template` — Country Templates

`75 countries` mapped. Template notation: `kk` = check digits, `B` = bank code, `S` = branch code, `C` = account number, `K` = national check digits.

### Full Country List

| Code | Country                    | Length | Code | Country                    | Length |
|------|---------------------------|--------|------|---------------------------|--------|
| AD   | Andorra                    | 24     | LV   | Latvia                    | 21     |
| AE   | United Arab Emirates       | 23     | MC   | Monaco                    | 27     |
| AL   | Albania                    | 28     | MD   | Moldova                   | 24     |
| AT   | Austria                    | 20     | ME   | Montenegro                | 22     |
| AZ   | Azerbaijan                 | 28     | MK   | Macedonia                 | 19     |
| BA   | Bosnia and Herzegovina     | 20     | MR   | Mauritania                | 27     |
| BE   | Belgium                    | 16     | MT   | Malta                     | 31     |
| BG   | Bulgaria                   | 22     | MU   | Mauritius                 | 30     |
| BH   | Bahrain                    | 22     | NL   | Netherlands               | 18     |
| BR   | Brazil                     | 29     | NO   | Norway                    | 15     |
| BY   | Belarus                    | 28     | OM   | Oman                      | 23     |
| CH   | Switzerland                | 21     | PK   | Pakistan                  | 24     |
| CR   | Costa Rica                 | 22     | PL   | Poland                    | 28     |
| CY   | Cyprus                     | 28     | PS   | Palestinian Territories   | 29     |
| CZ   | Czech Republic             | 24     | PT   | Portugal                  | 25     |
| DE   | Germany                    | 22     | QA   | Qatar                     | 29     |
| DK   | Denmark                    | 18     | RO   | Romania                   | 24     |
| DO   | Dominican Republic         | 28     | RS   | Serbia                    | 22     |
| EE   | Estonia                    | 20     | SA   | Saudi Arabia              | 24     |
| ES   | Spain                      | 24     | SE   | Sweden                    | 24     |
| FI   | Finland                    | 18     | SI   | Slovenia                  | 19     |
| FO   | Faroe Islands              | 18     | SK   | Slovakia                  | 24     |
| FR   | France                     | 27     | SM   | San Marino                | 27     |
| GB   | United Kingdom             | 22     | TN   | Tunisia                   | 24     |
| GE   | Georgia                    | 22     | TR   | Turkey                    | 26     |
| GI   | Gibraltar                  | 23     | UA   | Ukraine                   | 29     |
| GL   | Greenland                  | 18     | VG   | Virgin Islands (UK)       | 24     |
| GR   | Greece                     | 27     | XK   | Kosovo                    | 20     |
| GT   | Guatemala                  | 28     |      |                           |        |
| HR   | Croatia                    | 21     |      |                           |        |
| HU   | Hungary                    | 28     |      |                           |        |
| IE   | Ireland                    | 22     |      |                           |        |
| IL   | Israel                     | 23     |      |                           |        |
| IS   | Iceland                    | 26     |      |                           |        |
| IT   | Italy                      | 27     |      |                           |        |
| JO   | Jordan                     | 30     |      |                           |        |
| KW   | Kuwait                     | 30     |      |                           |        |
| KZ   | Kazakhstan                 | 20     |      |                           |        |
| LB   | Lebanon                    | 28     |      |                           |        |
| LI   | Liechtenstein               | 21     |      |                           |        |
| LT   | Lithuania                  | 20     |      |                           |        |
| LU   | Luxembourg                 | 20     |      |                           |        |

**Iceland note**: The map key is `'is'` (ISO 3166-1 alpha-2), but the template comment uses `FSkk` (the CBSO code). The template itself correctly produces a 26-character IBAN with a `F` slot for the Kennitala (Icelandic personal/company ID).

---

## `ResPartnerBank` — Model Override

**File**: `models/res_partner_bank.py`
**Inheritance**: `_inherit = "res.partner.bank"`

Extends the base `res.partner.bank` from the `base` module (with `account`'s version stacked above it in the MRO).

### Fields Added

No new fields are added to the model. All IBAN behavior is implemented through method overrides.

### Method Overrides

#### `_get_supported_account_types()`

```python
@api.model
def _get_supported_account_types(self):
    rslt = super(ResPartnerBank, self)._get_supported_account_types()
    rslt.append(('iban', self.env._('IBAN')))
    return rslt
```

Registers `'iban'` as a supported account type alongside the base `'bank'` type. The base model returns `[('bank', 'Normal')]`; this appends the IBAN option. The `acc_type` computed field (from the base model) calls `retrieve_acc_type()` to determine the type per record.

#### `retrieve_acc_type(acc_number)`

```python
@api.model
def retrieve_acc_type(self, acc_number):
    try:
        validate_iban(acc_number)
        return 'iban'
    except ValidationError:
        return super(ResPartnerBank, self).retrieve_acc_type(acc_number)
```

Attempts IBAN validation first. If it passes, returns `'iban'`. Falls back to the parent's `retrieve_acc_type` (which returns `'bank'` by default). This is the Odoo ORM's plugin-style dispatch: the account type is inferred from the number format, not from a user-selected field.

**Performance**: One regex substitution (`normalize_iban`) + one MOD-97 integer operation — no DB round-trip. Fast even on large recordset writes.

#### `get_bban()`

```python
def get_bban(self):
    if self.acc_type != 'iban':
        raise UserError(self.env._("Cannot compute the BBAN because the account number is not an IBAN."))
    return get_bban_from_iban(self.acc_number)
```

Instance method wrapper around the module-level `get_bban_from_iban`. Raises `UserError` (not `ValidationError`) — appropriate for a user-facing action triggered by a button, not a constraint violation.

#### `create(vals_list)` — Auto-Formatting on Write

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('acc_number'):
            try:
                validate_iban(vals['acc_number'])
                vals['acc_number'] = pretty_iban(normalize_iban(vals['acc_number']))
            except ValidationError:
                pass
    return super(ResPartnerBank, self).create(vals_list)
```

**Behavior**:
- If `acc_number` looks like a valid IBAN, it is normalized then pretty-printed before being written.
- If validation fails, the raw value is written unchanged — no error is raised.
- This means users can paste IBANs with or without spaces; storage is always normalized and formatted.

**Concurrency**: Runs before `super().create()`, so the formatted value is what gets persisted by the parent.

#### `write(vals)` — Auto-Formatting on Update

```python
def write(self, vals):
    if vals.get('acc_number'):
        try:
            validate_iban(vals['acc_number'])
            vals['acc_number'] = pretty_iban(normalize_iban(vals['acc_number']))
        except ValidationError:
            pass
    return super(ResPartnerBank, self).write(vals)
```

Identical logic to `create`. If `acc_number` is `False` or `None` (e.g., user cleared the field), `vals.get('acc_number')` is falsy and the IBAN logic is skipped entirely.

#### `_check_iban()` — `@api.constrains`

```python
@api.constrains('acc_number')
def _check_iban(self):
    for bank in self:
        if bank.acc_type == 'iban':
            validate_iban(bank.acc_number)
```

Constraint runs on every ORM write and create for records where `acc_type == 'iban'`. This is the ultimate safeguard — even if auto-formatting in `create`/`write` passed silently, a malformed IBAN stored in the DB will be caught on next write.

**Performance**: `@api.constrains` is evaluated in Python after the database write. For bulk imports of 10,000+ records, pre-validating with `validate_iban` before import is significantly faster than relying solely on constraints.

#### `check_iban(iban='')`

```python
def check_iban(self, iban=''):
    try:
        validate_iban(iban)
        return True
    except ValidationError:
        return False
```

Public RPC method callable from the frontend (used by the web widget). Returns a boolean instead of raising — suitable for JavaScript consumption. Called from the widget as:

```javascript
await this.orm.call("res.partner.bank", "check_iban", [[], iban])
```

The empty `[]` is the record IDs (irrelevant since this is an `@api.model` implicit method).

---

## Frontend: IBAN Web Widget

### `IbanWidget` — Component

**File**: `static/src/components/iban_widget/iban_widget.js`

```javascript
export const DELAY = 400;

export class IbanWidget extends CharField {
    static template = "base_iban.iban";
    setup() {
        super.setup();
        this.state = useState({ isValidIBAN: null });
        this.orm = useService("orm");
        this.validateIbanDebounced = useDebounced(async (ev) => {
            const iban = ev.target.value;
            if (!iban) {
                this.state.isValidIBAN = null;
            } else if (!/[A-Za-z]{2}.{3,}/.test(iban)) {
                this.state.isValidIBAN = false;   // Fast pre-check fails
            } else {
                this.state.isValidIBAN = await this.orm.call(
                    "res.partner.bank", "check_iban", [[], iban]
                );
            }
        }, DELAY);  // 400ms
    }
}
```

**Debounce strategy** (400ms):
1. User types → `input` event fires → debounced call.
2. If IBAN is empty → `null` (no icon shown).
3. If IBAN fails quick regex `/[A-Za-z]{2}.{3,}/` (2 letters + at least 3 more chars) → `false` immediately, no RPC.
4. If regex passes → RPC to `check_iban` server method → `true`/`false`.

**Why the regex pre-check**: Avoids a server round-trip for strings that are obviously not IBANs (e.g., `abc`, `12345`). Keeps the UI responsive.

**Icon behavior**:
- `isValidIBAN === true` → green check (`fa-check`, text-success)
- `isValidIBAN === false` → red cross (`fa-times`, text-danger, title tooltip)
- `isValidIBAN === null` → no icon

### Template — `base_iban.iban`

**File**: `static/src/components/iban_widget/iban_widget.xml`

```xml
<t t-name="base_iban.iban" t-inherit="web.CharField">
    <xpath expr="//input" position="attributes">
        <attribute name="class" add="o_iban_input_with_validator" separator=" "/>
        <attribute name="t-on-input">validateIbanDebounced</attribute>
        <attribute name="t-on-focus">validateIbanDebounced</attribute>
        <attribute name="t-on-blur">(ev) => { this.state.isValidIBAN = null; }</attribute>
    </xpath>
    <xpath expr="//input" position="after">
        <!-- conditional check/cross icons based on state.isValidIBAN -->
    </xpath>
</t>
```

- `t-on-blur` clears the icon on field exit — no persistent indicator after editing.
- `t-on-focus` re-validates on re-focus (e.g., tabbing back into the field).
- The check/cross icons are appended after the input element directly in the DOM.

### Widget Registration

```javascript
export const ibanWidget = { ...charField, component: IbanWidget };
registry.category("fields").add("iban", ibanWidget);
```

Registered as field widget `"iban"`. Applied to `acc_number` fields via XML in both `partner_view.xml` and `setup_wizards_view.xml`.

---

## Views

### `partner_view.xml` — Bank Account Form

Inherits from `account.view_partner_bank_form_inherit_account`. Patches `acc_number` field with `widget="iban"`.

### `setup_wizards_view.xml` — Bank Account Setup Wizard

Inherits from `account.setup_bank_account_wizard`. Patches `acc_number` field with `widget="iban"` on the `account.setup.bank.manual.config` wizard (used in the initial accounting setup / chart of accounts wizard).

---

## Demo Data

**File**: `data/res_partner_bank_demo.xml` (noupdate)

Three demo IBAN bank accounts created in demo:

| XML ID                          | acc_number          | Country | Partner         |
|---------------------------------|---------------------|---------|----------------|
| `bank_iban_asustek`             | `BE39103123456719`  | BE      | ASUS Computer   |
| `bank_iban_china_export`        | `SI56191000000123438` | SI    | China Export    |
| `bank_iban_main_partner`        | `BE61310126985517`  | BE      | Main Partner    |

All are Belgian (`BE`) or Slovenian (`SI`) IBANs, linked to existing demo banks (`base.bank_bnp`, `base.bank_ing`).

---

## Cross-Module Integration

### `account` Module (`account/models/res_partner_bank.py`)

The `account` module's version of `res.partner.bank` sits at the top of the MRO and provides:
- `has_iban_warning` — flag when IBAN country differs from partner country (computed from `sanitized_acc_number[:2]`).
- `has_money_transfer_warning` — flags Wise (`967`), Paynovate (`977`), PPS EU SA (`974`) by bank code position `[4:7]`.
- `allow_out_payment` — trust flag for outgoing payments, locked after first use.
- `duplicate_bank_partner_ids` — detects if the same `sanitized_acc_number` appears for multiple partners in the same company (SQL `ARRAY_AGG` query).
- `journal_id` — links to `account.journal` for bank journals.

`base_iban` is completely compatible with all of the above — it does not override any of these fields or methods.

### `account_qr_code_sepa` Module

Uses `res.partner.bank` (with IBAN) to generate SEPA QR codes. Requires `acc_type == 'iban'`.

### `l10n_*` Modules

Several localization modules extend `res.partner.bank` or `res.bank`:
- `l10n_ch` (Switzerland) — Swiss-specific bank number formats.
- `l10n_br` (Brazil) — CNPJ/CPF validation.
- `l10n_au`, `l10n_ar`, etc. — All override `retrieve_acc_type` and `_get_supported_account_types`, following the same extension pattern as `base_iban`.

---

## L4: Performance Analysis

| Operation                  | Cost                      | Notes                                      |
|---------------------------|---------------------------|--------------------------------------------|
| `validate_iban`            | O(n) string + one `int()` | n ≤ 34 chars; sub-microsecond              |
| `create`/`write` IBAN check | Same as above           | No DB queries                              |
| `_check_iban` constraint  | Same + Python loop        | Per-record after DB write                 |
| `check_iban` RPC (widget) | Network + validate        | Debounced 400ms; minimal impact           |
| `get_iban_part`           | O(n) zip + join           | n ≤ 34 chars; sub-microsecond             |

**Bulk import risk**: For imports of 10,000+ records, the `@api.constrains` decorator incurs a Python-side post-write check per record. Pre-validating with `validate_iban` before import is significantly faster.

**Stored pretty format**: After successful validation, `create()` and `write()` store the IBAN in grouped 4-character format. This means:
- **Read performance**: No re-formatting on display — the stored value is already pretty
- **Search**: Search matches on the formatted string (e.g., `BE62 3510...` matches `BE623510...`)
- **Database size**: IBANs of max 34 chars in grouped format = 41 chars stored (with spaces)

---

## L4: Odoo 18 → 19 Changes

### Lazy Translation

```python
from odoo.tools import LazyTranslate
_lt = LazyTranslate(__name__)
```

Odoo 19 uses `LazyTranslate` to defer translation lookup until needed (avoids importing all locales at module load time). This is used for `_lt()` calls within module-level helper functions like `validate_iban`.

### Frontend Regex Pre-check

The widget's `/[A-Za-z]{2}.{3,}/` pre-check avoids unnecessary server RPCs for obviously non-IBAN strings — a UX performance improvement. This pre-check was likely present in Odoo 18 but the regex pattern is more explicit in Odoo 19.

### Test Infrastructure

Odoo 19 uses the `@odoo/hoot` test framework with `advanceTime(DELAY)` for debounce testing. The test flow covers: empty field, invalid IBAN, valid IBAN, save, and re-edit.

### Iceland Template

`'is'` key with `FSkk` template comment was already present in Odoo 18 — no structural change.

### `create`/`write` Patterns

Consistent use of `@api.model_create_multi` and `vals_list` iteration, aligned with Odoo 19 API conventions. Both methods iterate over `vals_list` rather than using the older `super()` approach for bulk operations.

### Widget Event Flow

The Odoo 19 web client changed how field events propagate. The `IbanWidget` handles `t-on-blur` to clear the validation indicator, ensuring no stale icons persist after the user leaves the field.

---

## L4: Security Considerations

1. **IBAN checksum is not a security feature** — MOD-97 validates format integrity, not authorization. A syntactically valid IBAN can still belong to a scammer. The `account` module's `allow_out_payment` / `group_validate_bank_account` mechanism is the actual anti-fraud control.

2. **`acc_number` is stored in plain text** — IBANs are not encrypted at rest. The unique constraint is on `sanitized_acc_number`, so duplicate detection works across spaces and case differences.

3. **`check_iban` RPC is callable by any authenticated user** with read access to `res.partner.bank`. It is a pure computation with no side effects, so this is acceptable.

4. **`_check_iban` constraint runs post-write** — It does not prevent the write atomically. Concurrent writes could store an invalid IBAN between the time of the write and the constraint check. The `create`/`write` pre-validation (which `base_iban` performs) is the primary guard.

5. **IBAN strings appear in server logs** on `ValidationError` — IBANs are not GDPR-sensitive in the EU (they are account identifiers, not financial data per se), but some organizations may consider them PII.

6. **No XSS risk** — The `pretty_iban` output is alphanumeric plus spaces; no HTML injection vectors.

---

## Edge Cases

| Scenario                                        | Behavior                                                              |
|-------------------------------------------------|-----------------------------------------------------------------------|
| IBAN with lowercase letters                     | Accepted; `normalize_iban` uppercases everything                      |
| IBAN with spaces/dashes                         | Stripped before validation; stored without them                       |
| Empty `acc_number` in `create`/`write`          | IBAN logic skipped; base model handles empty check                    |
| IBAN of unknown country (e.g., `XX12...`)       | `ValidationError` — "should begin with country code"                  |
| IBAN with wrong length for its country          | `ValidationError` — shows correct template format                     |
| IBAN passing length but failing MOD-97          | `ValidationError` — "does not pass validation check"                  |
| Calling `get_bban()` on non-IBAN account        | `UserError` — "Cannot compute BBAN because account number is not an IBAN" |
| Calling `pretty_iban()` on invalid IBAN         | Returns input unchanged (silently)                                    |
| Very long input (e.g., `DE` + 100 chars)        | Fails length check against 22-character `DE` template                 |
| Unicode IBAN (e.g., pasted from PDF with smart quotes) | Non-ASCII letters fail `[a-zA-Z0-9]+` regex step 3               |

---

## Related Documentation

- [Core/Fields](Core/Fields.md) — Field types used in `res.partner.bank` (`Char`, `Selection`, `Many2one`)
- [Core/API](Core/API.md) — `@api.constrains`, `@api.model_create_multi`, `@api.depends` patterns
- [Modules/Account](Modules/Account.md) — `account.res.partner.bank` extension (trust flags, QR codes)
- [Modules/account_qr_code_sepa](Modules/account_qr_code_sepa.md) — SEPA QR code generation
- [Modules/base_vat](Modules/base_vat.md) — VAT validation (analogous to IBAN validation)
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — State machine patterns (IBAN accounts use `acc_type` as a type discriminator, not a workflow state)
