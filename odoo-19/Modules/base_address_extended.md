---
tags:
  - #odoo19
  - #modules
  - #address
---

# base_address_extended

## Overview

**Module:** `base_address_extended`  
**Source:** `odoo/addons/base_address_extended/`  
**Type:** Community Edition (CE)  
**Odoo Version:** 19 CE  
**Dependencies:** `base`, `contacts`  
**License:** LGPL-3  

The `base_address_extended` module enhances the address management capabilities of `res.partner` by:

1. Adding a structured city master table (`res.city`) with zip code support
2. Decomposing the monolithic `street` field into sub-components: `street_name`, `street_number`, `street_number2`
3. Introducing country-level enforcement of city selection from a predefined list
4. Overriding address formatting and onchange behaviors to propagate city/zip/state from `city_id`

---

## L1: Core Extensions to res.partner

### res.city — City Master Table

The module creates a new model `res.city` as a centralized city repository. This differs from the base Odoo behavior where `city` is a free-text Char field.

```
res.city
├── name          Char (required, translateable)
├── zipcode       Char
├── country_id    Many2one → res.country (required)
├── state_id      Many2one → res.country.state (optional, domain-filtered by country)
```

**Key characteristics:**
- `name` is `translate=True` — supports multilingual city names
- `_order = 'name'` — alphabetical default ordering
- `_rec_names_search = ['name', 'zipcode']` — enables searching by either name or zip code in `name_search()`
- `_compute_display_name()` formats display as `"City Name (ZIP)"` when a zipcode exists

**Data ownership:** The `res.city` table is intended to be populated either via localization modules (`l10n_*`) or manually by the administrator. No default data ships with this module.

### res.country — enforce_cities Flag

The module extends `res.country` with a single Boolean field:

```
res.country
└── enforce_cities  Boolean (default: False)
```

When `enforce_cities = True` on a country, the partner form enforces selection of a city from the `res.city` table rather than free-text entry. This is primarily used for countries requiring EDI-compliant city codes.

**View integration:** The `enforce_cities` checkbox is placed in the country form view after `phone_code`, alongside a stat button linking to the city's action.

### res.partner — Street Decomposition

Three new stored computed fields are added to `res.partner`:

```
res.partner (extended)
├── street_name     Char (stored, computed/inverse)
├── street_number    Char (stored, computed/inverse)
├── street_number2   Char (stored, computed/inverse)
├── city_id          Many2one → res.city
└── country_enforce_cities  Boolean (related to country_id.enforce_cities)
```

**How street decomposition works:**

The base Odoo `street` field stores a concatenated string. The `_compute_street_data()` method splits this string using `odoo.tools.street_split()` into its three components. Conversely, `_inverse_street_data()` recombines the three components back into `street` using the pattern:

```
street = street_name + " " + street_number + " - " + street_number2
```

Both operations are bidirectional and stored in the database.

### Address Formatting Override

The `_address_fields()` hook is extended:

```python
@api.model
def _address_fields(self):
    return super()._address_fields() + ['city_id']
```

This ensures `city_id` is included in the list of address fields used by Odoo's address formatting engine (via `res.partner._display_address()`).

---

## L2: Field Types, Defaults, and Constraints

### res.city Field Definitions

| Field | Type | Required | Stored | Default | Notes |
|-------|------|----------|--------|---------|-------|
| `name` | Char | Yes | Yes | — | `translate=True` |
| `zipcode` | Char | No | Yes | — | Zip or postal code |
| `country_id` | Many2one | Yes | Yes | — | `comodel_name='res.country'` |
| `state_id` | Many2one | No | Yes | — | Domain: `country_id` must match |

### res.partner Extended Fields

| Field | Type | Store | Compute | Inverse | Notes |
|-------|------|-------|---------|---------|-------|
| `street_name` | Char | Yes | Yes (`_compute_street_data`) | Yes (`_inverse_street_data`) | Street name component |
| `street_number` | Char | Yes | Yes | Yes | House number |
| `street_number2` | Char | Yes | Yes | Yes | Apartment/door number |
| `city_id` | Many2one | Yes | — | — | Links to `res.city` |
| `country_enforce_cities` | Boolean | Yes | — | — | Related: `country_id.enforce_cities` |

### res.country Field Definition

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `enforce_cities` | Boolean | No | `False` | Triggers city selection enforcement |

### Constraints

No Python (`@api.constrains`) or SQL constraints are defined in this module. Data integrity relies on the ORM's built-in mechanisms.

### onchange Methods

#### `_onchange_city_id()`

When `city_id` changes, the partner's `city`, `zip`, and `state_id` are automatically populated from the selected city record:

```python
@api.onchange('city_id')
def _onchange_city_id(self):
    if self.city_id:
        self.city = self.city_id.name
        self.zip = self.city_id.zipcode
        self.state_id = self.city_id.state_id
    elif self._origin:
        self.city = False
        self.zip = False
        self.state_id = False
```

This is the primary workflow trigger for automatic city/zip population.

#### `_onchange_country_id()`

When `country_id` changes, `city_id` is cleared if the new country differs from the city's country:

```python
@api.onchange('country_id')
def _onchange_country_id(self):
    super()._onchange_country_id()
    if self.country_id and self.country_id != self.city_id.country_id:
        self.city_id = False
```

This prevents inconsistent city-country combinations.

---

## L3: Cross-Model Relationships and Override Patterns

### Cross-Model Diagram

```
res.country                              res.city
┌──────────────────────────┐            ┌──────────────────────┐
│ id                      │──(1)────<──│ country_id           │
│ name                    │            │ state_id             │──(N)─→ res.country.state
│ enforce_cities          │            │ name                 │
│                         │            │ zipcode              │
└─────────────────────────┘            └──────────────────────┘
       │                                       │
       │ (1)                                   │ (N)
       ▼                                       ▼
res.partner                               res.partner
┌──────────────────────────┐            ┌──────────────────────┐
│ country_id ───────────────┼────────────│ city_id              │
│ state_id                 │            │ street_name          │
│ street                   │            │ street_number        │
│ street2                  │            │ street_number2       │
│ city                     │            │ zip                  │
│ zip                      │            └──────────────────────┘
│ city_id ─────────────────┼───────────────────────────────────┘
│ street_name              │   (computed from street)
│ street_number            │   (computed from street)
│ street_number2           │   (computed from street)
└──────────────────────────┘
```

### Override Pattern: _address_fields()

**Hook location:** `res.partner._address_fields()` (inherited from base)

**Purpose:** Returns the list of field names used in address formatting. Adding `city_id` ensures it participates in `name_get()` display and address printing.

**Pattern:**
```python
@api.model
def _address_fields(self):
    return super()._address_fields() + ['city_id']
```

### Override Pattern: _compute_street_data()

**Trigger:** Whenever `street` changes (via write or inverse operation)

**Mechanism:** Delegates to `odoo.tools.street_split()`, which uses regex-based parsing to extract:
- `street_name` — everything before the first space+number sequence
- `street_number` — the first number found
- `street_number2` — everything after the first comma after the number

**Important:** `street_split()` is heuristic-based and may not correctly parse all international address formats.

### Override Pattern: _inverse_street_data()

**Trigger:** When `street_name`, `street_number`, or `street_number2` are written directly

**Mechanism:** Concatenates the three components with spaces and hyphens into `street`

### Child Contact Synchronization

The test `test_child_sync` verifies that when a contact-type child is created with `parent_id`, the `city_id` is automatically propagated. This relies on Odoo's core `res.partner` contact inheritance mechanism, not on explicit code in this module.

---

## L4: Performance Considerations

### Stored Computed Fields

All three street decomposition fields (`street_name`, `street_number`, `street_number2`) are **stored** (`store=True`). This means:

- **Write cost:** When `street` changes, three records are updated (the partner plus two computed columns in the same table). This is efficient.
- **Read cost:** No computation at read time; values are pre-calculated and stored.
- **Database overhead:** Three additional `VARCHAR` columns added to `res_partner` table.

### city_id Indexing

The `city_id` Many2one field creates an implicit index on the foreign key column `city_id` in `res_partner`. This is sufficient for:
- Filtering partners by city
- Joining with `res_city` table

However, for high-volume queries filtering by city + country simultaneously, a composite index may be beneficial.

### Name Search on res.city

The `_rec_names_search = ['name', 'zipcode']` on `res.city` enables Odoo's `name_search()` to match on both city name and zip code. This can generate `ILIKE` queries which are slower on large datasets without a `pg_trgm` GIN index.

### Address Display Computation

The `_compute_display_name()` on `res.city` runs on every city record access where `display_name` is needed. For the common case where `zipcode` is blank, the overhead is minimal. For cities with zipcodes, string concatenation is O(n) in city name length.

---

## L4: Odoo 18 → 19 Changes

### Module Manifest

| Attribute | Odoo 18 | Odoo 19 |
|---|---|---|
| Version | `1.1` | `1.1` |
| Category | `Sales/Sales` | `Sales/Sales` (legacy) |
| Depends | `base`, `contacts` | Same |
| Sequence | `19` | `19` |

The module structure and field definitions are consistent between Odoo 18 and 19. No breaking API changes were introduced.

### `street_number2` Field Name

The field `street_number2` (for apartment/door numbers) was likely introduced or stabilized in Odoo 18/19 as part of the expanded street decomposition support. The `street_split()` tool in Odoo 19 supports extracting this third component.

### `_rec_names_search` Pattern

Odoo 19 formalized the `_rec_names_search` attribute on `res.city` for better `name_search()` integration. This pattern was likely introduced around Odoo 16/17 and is stable in Odoo 19.

### `country_enforce_cities` Related Field

The `country_enforce_cities` related Boolean field on `res.partner` (related to `country_id.enforce_cities`) is used in partner form views to conditionally display either the free-text `city` field or the `city_id` dropdown. This pattern is consistent across Odoo 18→19.

### Views Priority

The partner address form view has `priority="900"` — this is an inherited behavior that ensures the extended view loads after the base view, preventing conflicts. This priority scheme is unchanged.

### Tests

The `TestStreetFields` test class covers:
- `test_partner_create`: Verify street decomposition and recomposition for 9+ patterns
- `test_child_sync`: Verify `city_id` propagates to contact-type children

These tests were present in Odoo 18 and remain unchanged in Odoo 19.

---

## L4: Security Analysis

### Access Control

| Model | Group | Read | Write | Create | Unlink |
|-------|-------|------|-------|--------|--------|
| `res.city` | `base.group_partner_manager` | Yes | Yes | Yes | Yes |
| `res.city` | `base.group_user` | Yes | No | No | No |

Regular users can only read city records; only partner managers can modify the city master data.

### Information Disclosure

No sensitive information is exposed. City and address data are business-administrative in nature.

### SQL Injection Risk

None. All operations use the Odoo ORM, which parameterizes queries automatically.

### XSS Risk

None. No user-provided HTML content is rendered without sanitization in this module.

### Address Data in Partner Chatter

Address changes in `res.partner` are tracked via Odoo's standard audit fields (`write_uid`, `write_date`). No special audit trail for address changes is implemented by this module.

---

## L4: city_id and zip Synchronization Edge Cases

The `city_id` → `city/zip` synchronization is implemented via `_onchange_city_id()`. Key edge cases:

1. **Clearing city_id:** When `city_id` is set to `False`, the `elif self._origin` check ensures that `city`, `zip`, and `state_id` are only cleared if the partner already exists (has `_origin`). On a new partner creation, the `False` branch is skipped to avoid overwriting blank defaults.

2. **Zip code as city identifier:** The `res.city` model's `_compute_display_name()` concatenates name and zip code as `"City (ZIP)"`. This is purely a display feature and does not affect the actual `zipcode` field value.

3. **State from city:** The `city_id.state_id` is propagated to the partner. However, no inverse synchronization exists — changing the partner's `state_id` does not update `city_id`. If a city has multiple states (common in large countries), this can lead to inconsistencies.

4. **Country change clears city:** The `_onchange_country_id()` clears `city_id` when the country changes to a different country. This prevents storing a city from country A while displaying country B. However, if the user selects the same country (even if it was re-selected), `city_id` is NOT cleared because `self.country_id != self.city_id.country_id` evaluates to `False`.

5. **Multiple states per city:** A `res.city` can have only one `state_id`. For countries where cities span multiple states (e.g., large metropolitan areas), this creates a limitation: the `res.city` must pick one state, or the `state_id` field must be left blank. If left blank, the partner's `state_id` will be cleared when `city_id` is selected.

6. **Empty city name:** The `name` field on `res.city` is required. But `zipcode` is optional. A city record with no zipcode will display as just the city name.

---

## L4: EDI / City Code Compatibility

The module's primary stated purpose is to support Electronic Data Interchange (EDI) systems that require standardized city codes. In this context:

- `res.city` acts as a code table (similar to `res.country.state`)
- The `name` field may store either the human-readable city name or a code depending on localization implementation
- The `zipcode` field provides the postal code mapping

This design is intentionally minimal. For full EDI compliance, specialized localization modules (`l10n_*`) typically extend this further with additional city/country codes (e.g., UN/LOCODE, NUTS codes).

---

## L4: Extension Points for Customization

1. **Override `_onchange_city_id()`:** To add additional field propagation beyond `city`, `zip`, `state_id` (e.g., `country_id` from the city record)
2. **Override `_inverse_street_data()`:** To customize how street components are concatenated (e.g., different separator for specific countries)
3. **Extend `res.city`:** Add fields like `l10n_code`, `population`, `timezone` for localization modules
4. **Override `street_split()` logic:** To handle non-Western address formats that the default regex parser cannot handle
5. **Override `_address_fields()`:** To add additional fields to the address formatting engine
6. **Add validation on `enforce_cities`:** Country-level enforcement could be extended to raise `ValidationError` if a partner without `city_id` is saved for a country with `enforce_cities=True`

---

## L4: Related Views Detail

### res.city Views
- **Tree view:** Editable at top level (batch city creation/editing)
- **Search view:** Searches by `name` or `zipcode` (`ilike` filter on both)
- **Action:** `action_res_city_tree` — accessible from country form button and menu

### res.partner Address Form
- **Priority 900:** The `address_street_extended_form` view has `priority="900"` ensuring it overrides the base partner form for address input
- **Dual display mode:** The form shows either free-text `city` or `city_id` dropdown depending on `country_enforce_cities`
- **Inline layout:** Street components are rendered in a single flex row with `street_name` (flex: 3), `street_number` (flex: 1), and `street_number2` (flex: 1)

### View Inheritance Pattern

The partner form inheritance uses `position="replace"` with `t-if="country_enforce_cities"` to conditionally swap between free-text and dropdown modes. This is done through the view architecture rather than in Python.

---

## Models Inventory

| Model | File | Type | Notes |
|-------|------|------|-------|
| `res.city` | `models/res_city.py` | `Base` | New model created by this module |
| `res.country` | `models/res_country.py` | `Extension` | Adds `enforce_cities` |
| `res.partner` | `models/res_partner.py` | `Extension` | Adds street fields + onchanges |

---

## Tests

| Test Class | Test Method | Purpose |
|------------|-------------|---------|
| `TestStreetFields` | `test_partner_create` | Verify street decomposition and recomposition for 9+ patterns |
| `TestStreetFields` | `test_child_sync` | Verify `city_id` propagates to contact-type children |

---

## Related Documentation

- [Core/BaseModel](Core/BaseModel.md) — ORM foundation
- [Modules/res.partner](Modules/res.partner.md) — Base partner model
- [Modules/base_geolocalize](Modules/base_geolocalize.md) — Geolocation extension for partners
- [Patterns/Inheritance Patterns](odoo-18/Patterns/Inheritance Patterns.md) — `_inherit` vs `_inherits`
