---
Module: base_geolocalize
Version: Odoo 18
Type: Core Extension
Tags: #odoo18, #orm, #fields, #modules, #geolocation
---

# base_geolocalize

GPS geocoding for partner addresses via OpenStreetMap/Nominatim and Google Maps API. Adds `geo.localize()` action on `res.partner` that looks up lat/lon from address fields.

## Module Overview

- **Models extended:** `res.partner`
- **Models created:** `base.geocoder` (abstract), `base.geo_provider`
- **Settings:** `res.config.settings` for provider selection and Google API key
- **Dependency:** `base`
- **External API:** OpenStreetMap Nominatim (default), Google Maps Geocoding API (optional)

---

## Models

### `base.geo_provider`

```python
class GeoProvider(models.Model):
    _name = "base.geo_provider"
    _description = "Geo Provider"

    tech_name = fields.Char(string="Technical Name")
    name = fields.Char()
```

Master table of geocoding providers. Odoo ships with two records: `openstreetmap` and `googlemap`. The active provider is stored in `ir.config_parameter` (`base_geolocalize.geo_provider`).

---

### `base.geocoder` (abstract)

Abstract class providing geocoding API integration.

```python
class GeoCoder(models.AbstractModel):
    _name = "base.geocoder"
    _description = "Geo Coder"
```

**Key methods:**

#### `_get_provider()`

```python
@api.model
def _get_provider(self):
    prov_id = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.geo_provider')
    if prov_id:
        provider = self.env['base.geo_provider'].browse(int(prov_id))
    if not prov_id or not provider.exists():
        provider = self.env['base.geo_provider'].search([], limit=1)
    return provider
```

Returns the configured provider record, falling back to the first available provider.

#### `geo_query_address(street=None, zip=None, city=None, state=None, country=None)`

```python
@api.model
def geo_query_address(self, street=None, zip=None, city=None, state=None, country=None):
    """ Converts address fields into a valid string for querying geolocation APIs. """
    provider = self._get_provider().tech_name
    if hasattr(self, '_geo_query_address_' + provider):
        return getattr(self, '_geo_query_address_' + provider)(...)
    else:
        return self._geo_query_address_default(street=..., city=..., ...)
```

Formats address fields into a query string. Delegates to provider-specific transformations if defined.

**Default format:** `"street, zip city, state, country"` (filtered to non-empty parts)

**Google Maps variant:** Puts country qualifier in front (reverses "Congo, Democratic Republic of the" to "Democratic Republic of the Congo") because Google Maps returns wrong results otherwise.

#### `geo_find(addr, **kw)`

```python
@api.model
def geo_find(self, addr, **kw):
    """Use a location provider API to convert an address string into a latitude, longitude tuple."""
    provider = self._get_provider().tech_name
    try:
        service = getattr(self, '_call_' + provider)
        result = service(addr, **kw)
    except AttributeError:
        raise UserError(_('Provider %s is not implemented...'))
    ...
    return result  # (latitude, longitude) or None
```

Dispatches to the provider's `_call_<name>()` method.

#### `_call_openstreetmap(addr, **kw)`

```python
@api.model
def _call_openstreetmap(self, addr, **kw):
    url = 'https://nominatim.openstreetmap.org/search'
    headers = {'User-Agent': 'Odoo (http://www.odoo.com/contactus)'}
    response = requests.get(url, headers=headers,
                            params={'format': 'json', 'q': addr})
    result = response.json()
    geo = result[0]
    return float(geo['lat']), float(geo['lon'])
```

OpenStreetMap Nominatim integration. Returns `(lat, lon)` tuple. The `User-Agent` header is required by Nominatim's usage policy.

#### `_call_googlemap(addr, **kw)`

```python
@api.model
def _call_googlemap(self, addr, **kw):
    apikey = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {'sensor': 'false', 'address': addr, 'key': apikey}
    result = requests.get(url, params).json()
    geo = result['results'][0]['geometry']['location']
    return float(geo['lat']), float(geo['lng'])
```

Google Maps API. Requires a valid API key with Geocoding API enabled. Raises `UserError` if no key is configured. Returns paid-feature warning in error message since billing is required.

---

### `res.partner` (extension)

```python
class ResPartner(models.Model):
    _inherit = "res.partner"

    date_localization = fields.Date(string='Geolocation Date')
```

**Additional field:**

| Field | Type | Description |
|-------|------|-------------|
| `date_localization` | Date | Date when geolocation was last performed |

**`write()` override:**

```python
def write(self, vals):
    if any(field in vals for field in ['street', 'zip', 'city', 'state_id', 'country_id']) \
            and not all('partner_%s' % field in vals for field in ['latitude', 'longitude']):
        vals.update({
            'partner_latitude': 0.0,
            'partner_longitude': 0.0,
        })
    return super().write(vals)
```

When address fields change without explicit lat/lon updates, **resets** latitude and longitude to 0.0. This prevents stale geolocation data from persisting after an address edit.

**`_geo_localize(street='', zip='', city='', state='', country='')`**

```python
@api.model
def _geo_localize(self, street='', zip='', city='', state='', country=''):
    geo_obj = self.env['base.geocoder']
    search = geo_obj.geo_query_address(street=street, zip=zip, city=city,
                                       state=state, country=country)
    result = geo_obj.geo_find(search, force_country=country)
    if result is None:
        # Fallback: try city + state + country only (street may be too specific)
        search = geo_obj.geo_query_address(city=city, state=state, country=country)
        result = geo_obj.geo_find(search, force_country=country)
    return result
```

Two-stage geocoding: first attempts full address. If that fails, retries with city/state/country only. Returns `(latitude, longitude)` tuple or None.

**`geo_localize()`**

```python
def geo_localize(self):
    if not self._context.get('force_geo_localize') \
            and (self._context.get('import_file')
                 or any(config[key] for key in ['test_enable', 'test_file', 'init', 'update'])):
        return False
    partners_not_geo_localized = self.env['res.partner']
    for partner in self.with_context(lang='en_US'):
        result = self._geo_localize(partner.street, partner.zip, partner.city,
                                    partner.state_id.name, partner.country_id.name)
        if result:
            partner.write({
                'partner_latitude': result[0],
                'partner_longitude': result[1],
                'date_localization': fields.Date.context_today(partner)
            })
        else:
            partners_not_geo_localized |= partner
    if partners_not_geo_localized:
        self.env.user._bus_send("simple_notification", {
            'type': 'danger',
            'title': _("Warning"),
            'message': _('No match found for %(partner_names)s address(es).',
                         partner_names=', '.join(partners_not_geo_localized.mapped('display_name')))
        })
    return True
```

Geolocates each partner in the recordset. Uses `lang='en_US'` context for all lookups (Odoo's internal language). Skips execution in test mode, init mode, or update mode. Sends a bus notification warning for any partners that could not be geolocated.

---

### `res.config.settings` (extension)

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    geoloc_provider_id = fields.Many2one(
        'base.geo_provider',
        config_parameter='base_geolocalize.geo_provider',
        default=lambda x: x.env['base.geocoder']._get_provider())
    geoloc_provider_techname = fields.Char(related='geoloc_provider_id.tech_name', readonly=True)
    geoloc_provider_googlemap_key = fields.Char(
        string='Google Map API Key',
        config_parameter='base_geolocalize.google_map_api_key',
        help="Visit https://developers.google.com/maps/documentation/geocoding/get-api-key ...")
```

---

## L4 Notes

- **Two-stage fallback:** `_geo_localize()` retries without the street address if the full query returns no results. This handles cases where street addresses are too local or not in Nominatim's database.
- **Language neutral:** Uses `lang='en_US'` for geocoding. Address queries to external APIs should use English names for best results.
- **Zeroing stale coords:** The `write()` override that resets lat/lon on address change is critical — it prevents Odoo from showing a geolocation pin in the wrong location after an address edit.
- **OpenStreetMap Nominatim policy:** Requires a meaningful User-Agent header. Odoo uses `"Odoo (http://www.odoo.com/contactus)"`. Automated scraping without a User-Agent may result in IP blocks.
- **`force_geo_localize` context:** Allows forced geolocation even in test/import modes (bypasses the safety guard).
- **`partner_latitude` / `partner_longitude`:** These fields are defined in the base `res.partner` model itself. `base_geolocalize` only populates them via `geo_localize()`.
- **Google Maps billing:** The error message explicitly notes that Google made geocoding a paid feature requiring billing setup and API key with Geocoding + Maps Static + Maps Javascript APIs enabled.
- **Graceful degradation:** If geocoding fails (network error, no match), the method logs via `_logger` and returns None rather than raising — the `geo_localize()` action handles user feedback.
