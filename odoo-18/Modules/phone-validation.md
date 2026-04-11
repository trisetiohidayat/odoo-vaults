---
Module: phone_validation
Version: Odoo 18
Type: Integration
---

# phone_validation — Phone Number Validation and Formatting

## Overview

The `phone_validation` module (`addons/phone_validation/`) provides **E.164 phone number validation, formatting, and blacklist management** across the Odoo ecosystem. It wraps Google's `libphonenumber` library (via the `phonenumbers` Python package) and integrates with `res.partner`, `mail.thread`, and SMS-aware modules.

**Core responsibilities**:
1. Format phone numbers on partner fields (`phone`, `mobile`) via onchange hooks
2. Provide a `mail.thread.phone` mixin for any model to opt into phone sanitization + blacklist checking
3. Maintain a `phone.blacklist` table to suppress SMS delivery to opted-out numbers
4. Inject country-specific formatting rules via region patch files

**Depends**: `base`, `mail`
**Category**: Hidden
**Auto-install**: `True` (installed automatically with `mail`)
**License**: LGPL-3

---

## Module Structure

```
phone_validation/
├── __manifest__.py
├── __init__.py
├── lib/
│   ├── __init__.py
│   ├── phonemetadata.py              # Country metadata overrides
│   └── phonenumbers_patch/           # Country-specific metadata patches
│       ├── __init__.py
│       ├── region_SN.py  (Senegal)
│       ├── region_CO.py  (Colombia)
│       ├── region_IL.py  (Israel)
│       ├── region_MU.py  (Mauritius)
│       ├── region_BR.py  (Brazil)
│       ├── region_PA.py  (Panama)
│       ├── region_KE.py  (Kenya)
│       ├── region_MA.py  (Morocco)
│       └── region_CI.py  (Ivory Coast)
├── tools/
│   ├── __init__.py
│   └── phone_validation.py           # High-level format/validate helpers
├── models/
│   ├── __init__.py
│   ├── models.py                     # BaseModel extension (phone mixin helpers)
│   ├── res_partner.py                # Partner onchange hooks
│   ├── res_users.py                  # Portal user deactivation → blacklist
│   ├── phone_blacklist.py            # phone.blacklist model
│   └── mail_thread_phone.py          # mail.thread.phone mixin
├── wizard/
│   ├── __init__.py
│   └── phone_blacklist_remove.py     # Unblacklist wizard
└── views/
    └── phone_blacklist_views.xml
```

---

## Core Library: `phone_validation/tools/phone_validation.py`

### `phone_parse(number, country_code)`

Parses a raw phone number string using `phonenumbers.parse()`.

```python
def phone_parse(number, country_code):
    # 1. Parse with keep_raw_input=True to accept any format
    phone_nbr = phonenumbers.parse(number, region=country_code or None, keep_raw_input=True)
    # 2. Format to INTERNATIONAL to apply metadata patches
    formatted_intl = phonenumbers.format_number(phone_nbr, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    # 3. Re-parse the formatted number (applies Odoo's country metadata overrides)
    phone_nbr = phonenumbers.parse(formatted_intl, region=country_code or None, keep_raw_input=True)
```

**Validation steps**:
1. **Possible number check** (`is_possible_number`) — catches too-short or too-long digit counts
2. **Invalid country code** — raised separately before digit validation
3. **TOO_LONG fix** — attempts to re-parse with `+` prefix if user omitted it (e.g., `0033...` → `+33...`)
4. **Valid number check** (`is_valid_number`) — confirms the number is valid for the country

Returns a `phonenumbers.PhoneNumber` object. Raises `UserError` on any failure.

### `phone_format(number, country_code, country_phone_code, force_format='INTERNATIONAL', raise_exception=True)`

Formats a phone number according to country rules.

```python
def phone_format(number, country_code, country_phone_code, force_format='INTERNATIONAL'):
    phone_nbr = phone_parse(number, country_code)
    # force_format drives the output:
    #   'E164'          → +33612345678
    #   'INTERNATIONAL' → +33 6 12 34 56 78
    #   'NATIONAL'      → 06 12 34 56 78  (only if country_phone_code matches)
    #   'RFC3966'       → tel:+33-6-12-34-56-78
    return phonenumbers.format_number(phone_nbr, phone_fmt)
```

**Smart national fallback**: If `force_format='NATIONAL'` but the number's country code differs from the configured `country_phone_code` (e.g., user entered a US number while company's country is France), it automatically upgrades to `INTERNATIONAL`.

### `phone_get_region_data_for_number(number)`

Returns a dict with detected country info for a number:
```python
{
    'code': 'FR',           # ISO country code
    'national_number': '612345678',
    'phone_code': '33',     # country calling code
}
```

---

## Models

### `base` (AbstractModel) — `phone_validation/models/models.py`

The `phone_validation` module extends `BaseModel` (not a concrete model) to inject phone-helper methods into **every** Odoo model. These are the ORM-level building blocks used by the mixin.

#### `_phone_get_number_fields()` — API method

```python
@api.model
def _phone_get_number_fields(self):
    """ Returns ['mobile', 'phone'] if both exist on the model. """
    return [fname for fname in ('mobile', 'phone') if fname in self]
```

#### `_phone_get_country()` — Country resolution

```python
def _phone_get_country(self):
    """ Get the country to use for formatting. Priority:
    1. Record's own country_id field (via _phone_get_country_field)
    2. Country of any linked mail partner (commercial_partner_id, partner_ids)
    3. Company.country_id (fallback)
    """
```

#### `_phone_get_country_field()` — Configurable country field name

```python
@api.model
def _phone_get_country_field(self):
    if 'country_id' in self:
        return 'country_id'
    return False
```

Override this in models that store country in a non-standard field.

#### `_phone_format(fname=False, number=False, country=False, force_format='E164', raise_exception=False)`

Core formatting method. Accepts either a field name (reads from record) or a direct number string.

```python
# On a res.partner record:
formatted = partner._phone_format(fname='mobile', force_format='E164')
# Direct:
formatted = self._phone_format(number='+33612345678', force_format='NATIONAL')
```

#### `_phone_format_number(...)`

Thin wrapper around `phone_validation.phone_format()` that delegates to the tools library.

---

### `mail.thread.phone` — `phone_validation/models/mail_thread_phone.py`

**Abstract mixin** (`_name = 'mail.thread.phone'`, `_inherit = ['mail.thread']`). Any model can inherit from this to opt into phone sanitization and blacklist tracking.

#### Fields (computed, stored where noted)

| Field | Type | Compute | Description |
|-------|------|---------|-------------|
| `phone_sanitized` | Char | `_compute_phone_sanitized` (store=True) | E.164-stripped number used for comparisons. Stored for performance. |
| `phone_sanitized_blacklisted` | Boolean | `_compute_blacklisted` (store=False) | True if `phone_sanitized` is in `phone.blacklist` |
| `phone_blacklisted` | Boolean | `_compute_blacklisted` (store=False) | True if the `phone` field's number is blacklisted |
| `mobile_blacklisted` | Boolean | `_compute_blacklisted` (store=False) | True if the `mobile` field's number is blacklisted |
| `phone_mobile_search` | Char | `_search_phone_mobile_search` (search) | Virtual search field for phone/mobile combined search |

#### Database Indexes

On `init()`, partial indexes are created for all phone number fields:

- **B-tree index**: `regexp_replace(phone_field, '[\s\\./\(\)\-]', '', 'g')` — covers `=` and `LIKE` with a known prefix
- **GIN trigram index**: Same expression with `gin_trgm_ops` — covers `LIKE`/`ILIKE` with wildcard prefix

#### Key Methods

**`_phone_set_blacklisted()`**
```python
def _phone_set_blacklisted(self):
    return self.env['phone.blacklist'].sudo()._add(
        [r.phone_sanitized for r in self]
    )
```
Adds the sanitized phone number to the blacklist.

**`_phone_reset_blacklisted()`**
```python
def _phone_reset_blacklisted(self):
    return self.env['phone.blacklist'].sudo()._remove(
        [r.phone_sanitized for r in self]
    )
```
Removes from blacklist (archives the record).

**`_search_phone_mobile_search(operator, value)`**
Handles the `phone_mobile_search` virtual field. Normalizes `+`/`00` prefixes before searching so that `+32485112233` finds `0032485112233` and vice versa. Minimum 3 characters required.

#### Blacklist Search (`_search_phone_sanitized_blacklisted`)

Uses a SQL JOIN to find records whose `phone_sanitized` matches an active blacklist entry:
```sql
SELECT m.id FROM phone_blacklist bl
JOIN res_partner m ON m.phone_sanitized = bl.number AND bl.active
```

**L4 — How the blacklist check works end-to-end**:
1. When a partner is created/updated, `_compute_phone_sanitized` runs and stores the E.164-stripped version in `phone_sanitized`.
2. When any code queries `phone_sanitized_blacklisted`, `_compute_blacklisted` loads all blacklisted numbers and checks membership.
3. Because `phone_sanitized` is stored, the blacklist check is fast (no re-formatting on every access).
4. SMS marketing code (in `sms` module) checks `phone_sanitized_blacklisted` before sending.

#### Blacklist Action Button

`phone_action_blacklist_remove()` — Opens the `phone.blacklist.remove` wizard. Checks access rights before opening.

---

### `phone.blacklist` — `phone_validation/models/phone_blacklist.py`

Stores phone numbers that must not receive SMS marketing messages.

```python
class PhoneBlackList(models.Model):
    _name = 'phone.blacklist'
    _inherit = ['mail.thread']     # Full tracking history
    _description = 'Phone Blacklist'
    _rec_name = 'number'
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `number` | Char (required) | The blacklisted phone number. **Must be E.164 formatted.** Stored sanitized. |
| `active` | Boolean (default=True) | Inactive records are "dormant" blacklist entries — not matched in queries |

#### Constraints

```python
_sql_constraints = [
    ('unique_number', 'unique (number)', 'Number already exists')
]
```

#### Key Methods

**`create(values)` — Smart create**:
- Sanitizes all input numbers using `_phone_format` before storing
- If a number already exists but is inactive, **reactivates** it instead of creating a duplicate
- Returns the union of created + reactivated records (preserves original order)

**`write(values)` — Sanitize on update**:
- Re-sanitizes the `number` field if changed

**`_condition_to_sql(alias, fname, operator, value, query)` — Domain sanitization**:
- Automatically sanitizes search values when filtering by `number` field
- So searching `('number', '=', '+33612345678')` finds `0033612345678` equivalents

**`add(number, message=None)`** / **`_add(numbers, message=None)`**:
- Adds numbers to blacklist
- Posts a chatter message (via `mail.thread`) if a message is provided
- Returns all affected records

**`remove(number, message=None)`** / **`_remove(numbers, message=None)`**:
- **Archives** the blacklist entry (sets `active = False`) instead of deleting
- Posts a chatter note explaining the reason
- If the number was never blacklisted, creates a new inactive entry as a record of the removal request

**`action_add()`**:
- RPC-action button: re-adds the number to the blacklist from a previously unblacklisted record

#### ACLs

| ACL | Group | Permissions |
|-----|-------|-------------|
| `access_phone_blacklist_system` | `base.group_system` | Full CRUD |
| No public access | — | No read/write |

**L4 — Why no public read**: Phone blacklist entries should not be enumerable by non-admin users. The `phone_sanitized_blacklisted` computed field on partners is visible to `base.group_user`, but the underlying blacklist data is admin-only.

---

### `res.partner` — `phone_validation/models/res_partner.py`

Extends the base partner with **automatic phone formatting on field entry**.

```python
class Partner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner']

    @api.onchange('phone', 'country_id', 'company_id')
    def _onchange_phone_validation(self):
        if self.phone:
            self.phone = self._phone_format(fname='phone', force_format='INTERNATIONAL') or self.phone

    @api.onchange('mobile', 'country_id', 'company_id')
    def _onchange_mobile_validation(self):
        if self.mobile:
            self.mobile = self._phone_format(fname='mobile', force_format='INTERNATIONAL') or self.mobile
```

**L4 — How formatting is applied**:
1. User types a phone number in the `phone` or `mobile` field
2. On exiting the field (or changing country), the onchange fires
3. `_phone_format` is called with `force_format='INTERNATIONAL'`
4. The field value is **replaced** with the formatted version (e.g., `06 12 34 56 78` → `+33 6 12 34 56 78`)
5. If formatting fails (invalid number, no country), the original value is kept

**Why INTERNATIONAL and not E.164**: The `INTERNATIONAL` format (`+33 6 12 34 56 78`) is human-readable while still standardized. E.164 is used internally (in `phone_sanitized` and `phone.blacklist`) for storage and comparison.

---

### `res.users` — `phone_validation/models/res_users.py`

Extends `res.users` to **auto-blacklist phone numbers when a portal user self-deletes**.

```python
class Users(models.Model):
    _inherit = 'res.users'

    def _deactivate_portal_user(self, **post):
        """Blacklist the phone of the user after deleting it."""
        numbers_to_blacklist = {}
        if post.get('request_blacklist'):
            for user in self:
                for fname in self._phone_get_number_fields():  # mobile, phone
                    number = user._phone_format(fname=fname)
                    if number:
                        numbers_to_blacklist[number] = user

        super()._deactivate_portal_user(**post)  # deactivates the user first

        if numbers_to_blacklist:
            # Add to phone.blacklist and post tracking message
            ...
```

**L4 — Portal self-deletion flow**:
1. Portal user goes to `/my/security` → "Deactivate Account"
2. Confirms with password
3. Controller calls `request.env.user._deactivate_portal_user(request_blacklist=True)`
4. All phone numbers on the user's partner record are formatted and added to `phone.blacklist`
5. A chatter message logs which admin user triggered the blacklisting

---

## Wizard: `phone.blacklist.remove`

**File**: `wizard/phone_blacklist_remove.py`

```python
class PhoneBlacklistRemove(models.TransientModel):
    _name = 'phone.blacklist.remove'
    _description = 'Remove phone from blacklist'

    phone = fields.Char(string="Phone Number", readonly=True, required=True)
    reason = fields.Char(name="Reason")

    def action_unblacklist_apply(self):
        message = Markup('<p>Unblock Reason: %s</p>') % _(self.reason)
        return self.env['phone.blacklist']._remove([self.phone], message=message)
```

Opens from the partner's "Remove from blacklist" action button. Calls `_remove()` which archives the entry and posts the reason as a note.

---

## Country-Specific Patches: `lib/phonenumbers_patch/`

Odoo's `phonenumbers_patch/` directory contains **metadata overrides** for countries where Google's `libphonenumber` library has incorrect or outdated data. Each file (`region_XX.py`) patches the `phonenumbers` library's internal metadata for that country.

**Patched countries**: Senegal (SN), Colombia (CO), Israel (IL), Mauritius (MU), Brazil (BR), Panama (PA), Kenya (KE), Morocco (MA), Ivory Coast (CI).

**Why patches are needed**: Phone number rules change (new area codes, carrier portability, regulatory changes). Google updates `libphonenumber` periodically, but Odoo may ship with an older version. These patch files correct specific known issues without requiring a library upgrade.

---

## Format Types Reference

| Format | Example | Use Case |
|--------|---------|----------|
| `E164` | `+33612345678` | Internal storage, SMS sending, blacklist keys |
| `INTERNATIONAL` | `+33 6 12 34 56 78` | User-facing display, partner form |
| `NATIONAL` | `06 12 34 56 78` | Domestic display (only when country matches) |
| `RFC3966` | `tel:+33-6-12-34-56-78` | URI schemes, tel: links |

---

## Integration Points

| Module | Integration |
|--------|------------|
| `mail` | Inherits from `mail.thread`, uses mail tracking |
| `sms` | Checks `phone_sanitized_blacklisted` before sending; depends on phone_validation |
| `portal` | Portal users can be blacklisted on account deletion |
| `contacts` | The contacts app uses `res.partner` which has phone formatting |

---

## SMS Flow: How Blacklist Blocks SMS

```
sms composer → sms.send() → _phone_sanitrized_blacklist check
                                     ↓
                            phone.blacklist lookup
                                     ↓
                         if found and active: skip sending
```

The actual SMS sending logic (in `sms` module) calls `_phone_set_blacklisted()` when a recipient opts out, and checks `phone_sanitized_blacklisted` before every batch send.

---

## Tags

`#odoo` `#odoo18` `#modules` `#phone` `#sms` `#blacklist` `#E164` `#mail.thread`
