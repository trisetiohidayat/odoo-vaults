---
Module: base_address_extended
Version: Odoo 18
Type: Core Extension
Tags: #odoo18, #orm, #fields, #modules, #address
---

# base_address_extended

Enhanced address fields for `res.partner` with structured street splitting, `city_id` city selection, and country-level enforcement.

## Module Overview

- **Models extended:** `res.partner`, `res.country`, `res.city`
- **Key pattern:** Splitting freeform `street` text into `street_name`, `street_number`, `street_number2` sub-fields
- **Dependency:** `base`

---

## Models

### `res.country` (extension)

```python
class Country(models.Model):
    _inherit = 'res.country'

    enforce_cities = fields.Boolean(
        string='Enforce Cities',
        help="Check this box to ensure every address created in that country has a 'City' "
             "chosen in the list of the country's cities.")
```

**Key field:**

| Field | Type | Description |
|-------|------|-------------|
| `enforce_cities` | Boolean | When `True`, the UI forces selection from `res.city` list instead of free-text `city` |

---

### `res.city`

City master data with zip code and state linkage.

```python
class City(models.Model):
    _name = 'res.city'
    _description = 'City'
    _order = 'name'
    _rec_names_search = ['name', 'zipcode']

    name = fields.Char("Name", required=True, translate=True)
    zipcode = fields.Char("Zip")
    country_id = fields.Many2one(comodel_name='res.country', string='Country', required=True)
    state_id = fields.Many2one(
        comodel_name='res.country.state',
        string='State',
        domain="[('country_id', '=', country_id)]"
    )
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | City name, translateable |
| `zipcode` | Char | Postal code |
| `country_id` | Many2one | Country reference (required) |
| `state_id` | Many2one | State/province within the country |

**Computed:** `display_name` — formats as `"City Name (zipcode)"` when zipcode is present.

**Search fields:** `name`, `zipcode` (via `_rec_names_search`)

---

### `res.partner` (extension)

Extends `res.partner` with structured address fields and city selection.

```python
class Partner(models.Model):
    _inherit = ['res.partner']

    street_name = fields.Char(
        'Street Name',
        compute='_compute_street_data', inverse='_inverse_street_data',
        store=True)
    street_number = fields.Char(
        'House',
        compute='_compute_street_data', inverse='_inverse_street_data',
        store=True)
    street_number2 = fields.Char(
        'Door',
        compute='_compute_street_data', inverse='_inverse_street_data',
        store=True)

    city_id = fields.Many2one(comodel_name='res.city', string='City ID')
    country_enforce_cities = fields.Boolean(related='country_id.enforce_cities')
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `street_name` | Char | Parsed street name (compute + inverse, stored) |
| `street_number` | Char | House number (compute + inverse, stored) |
| `street_number2` | Char | Door/apartment suffix (compute + inverse, stored) |
| `city_id` | Many2one | `res.city` selection |
| `country_enforce_cities` | Boolean | Related from country — triggers city list vs free-text toggle |

---

## Methods

### `_address_fields()` (override)

```python
def _address_fields(self):
    return super()._address_fields() + ['city_id']
```

Adds `city_id` to the list of address fields used by Odoo's address formatting templates.

### `_inverse_street_data()`

```python
def _inverse_street_data(self):
    """ update self.street based on street_name, street_number and street_number2 """
    for partner in self:
        street = ((partner.street_name or '') + " " + (partner.street_number or '')).strip()
        if partner.street_number2:
            street = street + " - " + partner.street_number2
        partner.street = street
```

Writes back the combined `street` from parsed sub-fields:
- `"StreetName HouseNumber"`
- `"StreetName HouseNumber - DoorNumber"` if `street_number2` is set.

### `_compute_street_data()`

```python
@api.depends('street')
def _compute_street_data(self):
    """Splits street value into sub-fields.
    Recomputes the fields of STREET_FIELDS when `street` of a partner is updated"""
    for partner in self:
        partner.update(tools.street_split(partner.street))
```

Splits the freeform `street` value into `street_name`, `street_number`, `street_number2` using `odoo.tools.street_split`. Triggered whenever `street` changes.

### `_get_street_split()`

```python
def _get_street_split(self):
    self.ensure_one()
    return {
        'street_name': self.street_name,
        'street_number': self.street_number,
        'street_number2': self.street_number2
    }
```

Returns sub-field dict (used by address formatting templates).

### `_onchange_city_id()`

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

When the user selects a city from the dropdown, auto-fills `city`, `zip`, and `state_id` from the `res.city` record. Clears those fields if the city is deselected.

---

## View Inheritance

The module adds two XML views (priority 900) that override `base.view_partner_form`:

**`address_street_extended_form`** — Adds structured street sub-fields (street_name, street_number, street_number2) as a flex row in edit mode. In read mode, shows the combined `street` field. Hides freeform `city` when `country_enforce_cities` is active.

**`address_street_extended_city_form`** — Inherits the base partner form to insert `city_id` selection before the freeform `city` field, only visible when the country has `enforce_cities = True`.

## L4 Notes

- **Street splitting algorithm** (`tools.street_split`): Handles house numbers, bis/ter suffixes, fractions, and apartment indicators. Implementation is in `odoo/tools/__init__.py`.
- **City list vs free text**: The `city_id` / freeform `city` toggle is driven entirely by `country_id.enforce_cities`. When `True`, the `city_id` dropdown appears and the freeform `city` becomes invisible.
- **Address formatting**: Odoo's address template in `report_layout` calls `_address_fields()` to gather fields to render. Adding `city_id` here ensures it participates in formatted address prints.
- **Multi-company**: No multi-company concerns — `res.city` is global master data.
- **Performance**: `street_name`, `street_number`, `street_number2` are **stored computed fields**, meaning they persist to the DB and avoid re-computation on every read. They are recomputed only when `street` changes.
