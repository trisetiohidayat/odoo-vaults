---
Module: base_iban
Version: Odoo 18
Type: Core Extension
Tags: #odoo18, #orm, #fields, #modules, #banking, #sepa
---

# base_iban

IBAN (International Bank Account Number) validation and normalization for `res.partner.bank` records. Validates structure, checks digit, and formats IBANs for display.

## Module Overview

- **Model extended:** `res.partner.bank`
- **IBAN template map:** 75+ country codes with structural templates
- **Dependency:** `base`
- **Standard:** ISO 13616, MOD-97 checksum (ISO 7064)

---

## Module-Level Functions

### `normalize_iban(iban)`

```python
def normalize_iban(iban):
    return re.sub(r'[\W_]', '', iban or '')
```

Strips all non-alphanumeric characters (spaces, dashes, underscores) from an IBAN.

### `pretty_iban(iban)`

```python
def pretty_iban(iban):
    """ return iban in groups of four characters separated by a single space """
    try:
        validate_iban(iban)
        iban = ' '.join([iban[i:i + 4] for i in range(0, len(iban), 4)])
    except ValidationError:
        pass
    return iban
```

Formats a valid IBAN with spaces every 4 characters for readability. Returns unformatted on validation failure.

### `get_bban_from_iban(iban)`

```python
def get_bban_from_iban(iban):
    """ Returns the basic bank account number (BBAN) corresponding to an IBAN. """
    return normalize_iban(iban)[4:]
```

Extracts the BBAN (everything after the 4-character country code + check digits).

### `validate_iban(iban)`

```python
def validate_iban(iban):
    iban = normalize_iban(iban)
    if not iban:
        raise ValidationError(_lt("There is no IBAN code."))
    country_code = iban[:2].lower()
    if country_code not in _map_iban_template:
        raise ValidationError(_lt("The IBAN is invalid, it should begin with the country code"))
    iban_template = _map_iban_template[country_code]
    if len(iban) != len(iban_template.replace(' ', '')) or not re.fullmatch("[a-zA-Z0-9]+", iban):
        raise ValidationError(_lt("The IBAN does not seem to be correct..."))
    check_chars = iban[4:] + iban[:4]
    digits = int(''.join(str(int(char, 36)) for char in check_chars))  # BASE 36
    if digits % 97 != 1:
        raise ValidationError(_lt("This IBAN does not pass the validation check..."))
```

Three-step validation:
1. **Presence check:** IBAN must not be empty
2. **Structure check:** Country code must be in template map; length must match template; only alphanumeric allowed
3. **Checksum:** MOD-97 (ISO 7064) — converts to base-36, performs `digits % 97 == 1`

---

## IBAN Template Map

```python
_map_iban_template = {
    'ad': 'ADkk BBBB SSSS CCCC CCCC CCCC',  # Andorra
    'ae': 'AEkk BBBC CCCC CCCC CCCC CCC',  # United Arab Emirates
    'al': 'ALkk BBBS SSSK CCCC CCCC CCCC CCCC',
    'at': 'ATkk BBBB BCCC CCCC CCCC',  # Austria
    # ... 70+ more countries ...
    'de': 'DEkk BBBB BBBB CCCC CCCC CC',  # Germany
    'gb': 'GBkk BBBB SSSS SSCC CCCC CC',  # United Kingdom
    'nl': 'NLkk BBBB CCCC CCCC CC',  # Netherlands
    'us': (absent — US does not use IBAN)
    # ...
}
```

Each template defines the expected structure: `kk` = check digits, `B` = bank code, `S` = branch code, `C` = account number, `k` = check digit. Length validation is done by comparing `len(iban)` against `len(template.replace(' ', ''))`.

---

## Model Extension

### `res.partner.bank` (extension)

```python
class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"
```

**`_get_supported_account_types()` (override)**

Adds `'iban'` as a supported account type alongside the base module's types.

**`retrieve_acc_type(acc_number)` (override)**

```python
@api.model
def retrieve_acc_type(self, acc_number):
    try:
        validate_iban(acc_number)
        return 'iban'
    except ValidationError:
        return super(ResPartnerBank, self).retrieve_acc_type(acc_number)
```

Tries IBAN validation first. Falls back to parent's account type detection.

**`get_bban()`**

```python
def get_bban(self):
    if self.acc_type != 'iban':
        raise UserError(_("Cannot compute the BBAN because the account number is not an IBAN."))
    return get_bban_from_iban(self.acc_number)
```

Extracts BBAN from the stored IBAN.

**`create(vals_list)` (override)**

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

On create: validates IBAN, normalizes and formats. Invalid IBANs are stored as-is.

**`write(vals)` (override)**

Same normalization as `create()`: validates, normalizes, and reformats IBAN on field update.

**`_check_iban()` (constraint)**

```python
@api.constrains('acc_number')
def _check_iban(self):
    for bank in self:
        if bank.acc_type == 'iban':
            validate_iban(bank.acc_number)
```

Validates IBAN on every write when `acc_type == 'iban'`.

**`check_iban(iban='')`**

```python
def check_iban(self, iban=''):
    try:
        validate_iban(iban)
        return True
    except ValidationError:
        return False
```

Convenience method for programmatic IBAN checking.

---

## L4 Notes

- **IBAN validation is deterministic:** No external API calls — all validation is local using the MOD-97 algorithm.
- **BBAN extraction:** The BBAN is the domestic account number portion (after country code + check digits). It is NOT the same as the local account number format — BBAN structure varies by country and is defined by each country's IBAN variant.
- **Normalization on write:** Every time `acc_number` is updated, the module attempts validation and reformatting. If invalid, it is stored exactly as entered.
- **Pretty formatting:** IBANs are stored with spaces every 4 characters (`"DE89 3704 0044 0532 0130 00"`). This is done at `create()` and `write()` time for valid IBANs.
- **`acc_type` detection:** The type is determined by the order: try IBAN first, then fall back to other account types. This means valid IBANs are always typed as `'iban'` even if the partner bank was created with just `acc_number` set.
- **Constraint only on IBAN accounts:** `_check_iban` only fires when `acc_type == 'iban'`. Non-IBAN accounts are not constrained by this module.
- **Country template map coverage:** Includes all countries that have adopted IBAN (originally European, now global). Notably absent: United States, Canada, Australia, China — these do not use IBAN.
- **ISO 13616 MOD-97:** The checksum validation converts each letter to a two-digit number (A=10, B=11... Z=35) using base-36 arithmetic, then checks that the integer is divisible by 97.
