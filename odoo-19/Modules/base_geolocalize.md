---
uuid: base_geolocalize-001
tags:
  - odoo
  - odoo19
---

# base_geolocalize

## Overview

**Module:** `base_geolocalize`  
**Source:** `odoo/addons/base_geolocalize/`  
**Type:** Community Edition (CE)  
**Odoo Version:** 19 CE  
**Dependencies:** `base_setup`  
**License:** LGPL-3  

The `base_geolocalize` module provides geocoding and geolocation capabilities for `res.partner` records by:

1. Adding GPS coordinate fields (`partner_latitude`, `partner_longitude`) to partners
2. Providing a configurable abstract geocoder service supporting multiple providers (OpenStreetMap, Google Maps)
3. Enabling address-to-coordinates conversion via a button action
4. Supporting reverse geocoding (coordinates to location string)

**Note:** The coordinate fields (`partner_latitude`, `partner_longitude`) are defined in the `base` module. This module provides the geocoding infrastructure to populate them.

---

## L1: Core Extensions to res.partner

### How Geo-Localization Works

The module adds geolocation capabilities without duplicating the latitude/longitude fields (those live in `base`). Instead, it provides:

1. **Geocoding (forward):** Address → GPS coordinates
   - Uses the `geo_localize()` action method on `res.partner`
   - Calls external geocoding APIs (OpenStreetMap Nominatim or Google Maps)
   - Writes results to `partner_latitude` and `partner_longitude`

2. **Reverse geocoding:** GPS coordinates → Location string
   - Uses `_get_localisation()` method on `base.geocoder`
   - Called via `_call_openstreetmap_reverse()` to reverse geocode
   - Returns formatted string: `"[ZIP] City, Country"`

### base.geo_provider — Provider Configuration

A lightweight model to register available geocoding providers:

```
base.geo_provider
├── tech_name    Char
└── name         Char
```

Two records are created via `data/data.xml`:

| `tech_name` | `name` |
|-------------|--------|
| `openstreetmap` | Open Street Map |
| `googlemap` | Google Place Map |

### base.geocoder — Abstract Geocoder Service

This is an **abstract model** (`_name = 'base.geocoder'`) — it does not create database tables. It provides a service layer for geocoding operations.

**Architecture pattern:** Abstract model as service layer / mixin for geocoding. Any model inheriting from `base.geocoder` gains the geocoding methods.

**Key methods:**

| Method | Purpose |
|--------|---------|
| `_get_provider()` | Returns the configured `base.geo_provider` record |
| `geo_query_address()` | Formats address fields into API query string |
| `geo_find()` | Calls geocoding API, returns `(lat, lon)` tuple |
| `_call_openstreetmap()` | Calls OpenStreetMap Nominatim API |
| `_call_googlemap()` | Calls Google Maps Geocoding API |
| `_call_openstreetmap_reverse()` | Reverse geocoding via Nominatim |
| `_get_localisation()` | Converts lat/lon to location string |

---

## L2: Field Types, Defaults, and Constraints

### res.partner Extended Fields

This module extends `res.partner` with one field:

| Field | Type | Stored | Notes |
|-------|------|--------|-------|
| `date_localization` | Date | Yes | Tracks when geolocation was last computed |

The `partner_latitude` and `partner_longitude` fields are defined in `base` (in `base` module's `res.partner` definition) — not created by this module.

### res.config.settings Extended Fields

| Field | Type | Config Parameter | Notes |
|-------|------|-------------------|-------|
| `geoloc_provider_id` | Many2one | `base_geolocalize.geo_provider` | Selected geocoding provider |
| `geoloc_provider_techname` | Char | — | Related to provider tech name (readonly) |
| `geoloc_provider_googlemap_key` | Char | `base_geolocalize.google_map_api_key` | Google Maps API key |

### Constraints

No explicit Python or SQL constraints in this module.

### Address Write Reset Logic

When any address-related field is modified, the module automatically resets coordinate values to `0.0`:

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

This ensures coordinates are always consistent with the current address. If coordinates are intentionally preserved during address edits, both `partner_latitude` and `partner_longitude` must be explicitly included in the write values.

---

## L3: Cross-Model Relationships and Override Patterns

### Cross-Model Diagram

```
ir.config_parameter                 base.geo_provider
┌─────────────────────────────────┐  ┌─────────────────────────┐
│ base_geolocalize.geo_provider    │  │ id                      │
│ base_geolocalize.google_map_key  │  │ tech_name               │
└─────────────────────────────────┘  │ name                    │
                                     └─────────────────────────┘
                                            │
                                            │ (1)
                                            ▼
                                     base.geocoder (abstract)
                                     ┌──────────────────────────────────┐
                                     │ _get_provider()                  │
                                     │ geo_query_address()              │
                                     │ geo_find()                       │
                                     │ _call_openstreetmap()  ──────► OSM Nominatim API
                                     │ _call_googlemap()       ──────► Google Geocoding API
                                     │ _get_localisation()              │
                                     └──────────────────────────────────┘
                                            │ ▲
                                            │ │ (inheritance)
                                            ▼ │
res.partner                                                  res.config.settings
┌──────────────────────────────────┐       ┌──────────────────────────────────┐
│ geo_localize()  ────────────────►│──────►│ geoloc_provider_id               │
│ _geo_localize()                  │       │ geoloc_provider_googlemap_key   │
│ date_localization                │       └──────────────────────────────────┘
│ partner_latitude  (from base)    │
│ partner_longitude (from base)    │
└──────────────────────────────────┘
```

### Override Pattern: geo_localize() Method

This is the primary action method on `res.partner`. It:

1. Checks execution context to avoid running during import, testing, or before registry is ready
2. Forces `lang='en_US'` for consistent API queries (geocoding APIs expect English addresses)
3. Calls `_geo_localize()` for each partner in the recordset
4. Writes `partner_latitude`, `partner_longitude`, `date_localization` on success
5. Sends a bus notification listing partners that could not be geolocated

```python
def geo_localize(self):
    # Skip if: importing, testing, or registry not ready
    if not self.env.context.get('force_geo_localize') and (
        self.env.context.get('import_file')
        or modules.module.current_test
        or not self.env.registry.ready
    ):
        return False

    partners_not_geo_localized = self.env['res.partner']
    for partner in self.with_context(lang='en_US'):
        result = self._geo_localize(partner.street, partner.zip, ...)
        if result:
            partner.write({...})
        else:
            partners_not_geo_localized |= partner

    if partners_not_geo_localized:
        self.env.user._bus_send("simple_notification", {...})
    return True
```

### Override Pattern: _geo_localize()

Internal method that performs the actual geocoding:

```python
@api.model
def _geo_localize(self, street='', zip='', city='', state='', country=''):
    geo_obj = self.env['base.geocoder']
    search = geo_obj.geo_query_address(street=street, zip=zip, city=city, ...)
    result = geo_obj.geo_find(search, force_country=country)
    if result is None:
        # Retry without street number for better match
        search = geo_obj.geo_query_address(city=city, state=state, country=country)
        result = geo_obj.geo_find(search, force_country=country)
    return result
```

**Fallback mechanism:** If full address geocoding fails, it retries with only city/state/country. This handles cases where the street address is not found but the city is.

### Workflow Trigger

Geolocation is triggered **manually** via a button on the partner form (`geo_localize` button), not automatically. The button is conditionally displayed:
- "Compute based on address" — shown when `partner_latitude = 0` and `partner_longitude = 0`
- "Refresh Localization" — shown when coordinates are already set

### Provider-Specific Address Formatting

The `_geo_query_address_googlemap()` method handles a special case for Google's API:

```python
def _geo_query_address_googlemap(self, ...):
    # Google's geocoder performs better with country qualifier in front
    # e.g., 'Congo, Democratic Republic of the' → 'Democratic Republic of the Congo'
    if country and ',' in country and (country.endswith(' of') or country.endswith(' of the')):
        country = '{1} {0}'.format(*country.split(',', 1))
    return self._geo_query_address_default(...)
```

---

## L4: Performance, Version Changes, Security, and Deep Details

### Performance Considerations

#### External API Calls — The Primary Bottleneck

The `geo_find()` method makes **synchronous HTTP requests** to external geocoding services. This is the most critical performance concern:

**OpenStreetMap Nominatim:**
- Free, no API key required
- Rate limited: 1 request/second (enforced by usage policy, not code)
- No SLA guarantee
- Latency: typically 100–500ms per request

**Google Maps Geocoding API:**
- Requires API key with billing enabled
- Rate limits depend on plan
- Latency: typically 50–200ms per request
- Error handling includes specific billing-related error messages

**Batch operations:** Geolocating many partners triggers one API call per partner. For large batch operations, consider:
- Implementing a queue with rate limiting
- Using the geonames_id approach (reverse geocoding with pre-computed datasets) for better performance

#### Test Environment Restrictions

Reverse geocoding (`_call_openstreetmap_reverse`) is explicitly **blocked during tests**:

```python
if tools.config['test_enable'] or modules.module.current_test:
    raise UserError(_("OpenStreetMap calls disabled in testing environment."))
```

This prevents external HTTP calls during automated testing.

#### User-Agent Requirements

OpenStreetMap Nominatim requires a User-Agent header identifying the client:

```python
headers = {'User-Agent': 'Odoo (http://www.odoo.com/contactus)'}
```

This is non-configurable and may cause issues if multiple Odoo instances share the same User-Agent.

### Odoo 18 → 19 Changes

#### New: _get_localisation() Method (Odoo 19)

A new reverse geocoding method was added in Odoo 19:

```python
def _get_localisation(self, latitude, longitude):
    # Try geoip from request first
    city = request.geoip.city.name
    country_code = request.geoip.country_code

    if not (city and country_code):
        # Fallback to OpenStreetMap reverse geocoding
        result = self._call_openstreetmap_reverse(latitude, longitude)
        if result and (address := result.get("address")):
            country_code = address.get("country_code")
            city = (address.get("city_district") or
                    address.get("town") or
                    address.get("village") or
                    address.get("city"))
            postcode = address.get("postcode")

    country = self.env["res.country"].search([("code", "=", country_code.upper())])
    return f"{postcode or ''} {city or ''} {country.name or 'Unknown'}"
```

This enables getting a human-readable location string from coordinates, useful for display in dashboards.

#### Notification Bus Change

Odoo 19 uses `_bus_send()` for user notifications instead of the older `raise UserError` pattern for multiple partners. This provides a non-blocking notification mechanism.

#### API Error Handling

Error handling was refined to catch and log specific API failure modes, including Google's billing-related errors with detailed messages.

### Security Analysis

#### API Key Storage

Google Maps API key is stored as an `ir.config_parameter` (system parameter):

- Key: `base_geolocalize.google_map_api_key`
- Storage: `ir_config_parameters` table (database)
- Visibility: Only visible in Settings UI for users with Settings access
- Risk: If compromised, attacker could use the Google Maps API under the organization's billing

**Recommendation:** Restrict Google Maps API key to specific domains and IP addresses in the Google Cloud Console.

#### Information Disclosure

Geolocation coordinates can reveal sensitive location information:
- Partner home address coordinates
- Business premises coordinates
- Home office locations of employees

**ACL:** `partner_latitude` and `partner_longitude` should be protected with appropriate access groups if sensitive.

#### API Request Privacy

The Odoo server's IP address is exposed to OpenStreetMap and Google servers when making geocoding requests. The partner's full address is sent as a query parameter.

#### No SQL Injection Risk

All database operations use the Odoo ORM. API queries use parameterized HTTP GET parameters.

#### No XSS Risk

All returned data is processed server-side. The `_get_localisation()` result is returned as a string.

### geonames_id for Reverse Geocoding (Design Gap)

A notable absence in this module is a `geonames_id` field on partners or cities for efficient reverse geocoding. The current approach requires an API call for every reverse geocoding operation.

**Workaround:** Localization modules can extend `res.city` with a `geonames_id` field, then override `_get_localisation()` to use a local geonames database lookup instead of an external API call. This significantly improves performance for high-volume scenarios.

### Reverse Geocoding Return Value

The `_call_openstreetmap_reverse()` method returns the **full JSON response** from Nominatim, not just an address string. The response structure includes:

```json
{
  "place_id": 123,
  "lat": "37.386",
  "lon": "-122.084",
  "display_name": "123 Main St, City, State, Country",
  "address": {
    "road": "Main St",
    "city": "City",
    "state": "State",
    "country": "Country",
    "postcode": "12345",
    "city_district": "...",
    "town": "...",
    "village": "..."
  }
}
```

The `_get_localisation()` method intelligently extracts `city_district`, `town`, `village`, or `city` in that priority order to handle variations in Nominatim's responses across regions.

### Configuration Architecture

```
Settings → General Settings → Localization
    └── Geolocation section
            ├── API: [OpenStreetMap / Google Place Map]  (Many2one)
            └── Google Map API Key: [................]  (visible only when Google selected)
```

The `geoloc_provider_id` defaults to the first `base.geo_provider` record (typically OpenStreetMap) if no preference is configured.

### Extension Points

1. **Add a new geocoding provider:** Define `_call_providername()` and `_geo_query_address_providername()` on `BaseGeocoder` or any inheriting model
2. **Override `_get_localisation()`:** For cached or local reverse geocoding using geonames database
3. **Override `geo_localize()`:** For batch processing with rate limiting and progress tracking
4. **Add `geonames_id` to `res.city`:** For efficient city-based reverse geocoding without API calls
5. **Override `write()` reset logic:** To preserve coordinates during address edits (include both lat/lon in vals)

---

## Models Inventory

| Model | File | Type | Notes |
|-------|------|------|-------|
| `base.geo_provider` | `models/base_geocoder.py` | `Base` | Provider registry |
| `base.geocoder` | `models/base_geocoder.py` | `Abstract` | Geocoding service layer |
| `res.partner` | `models/res_partner.py` | `Extension` | Adds `geo_localize()`, `date_localization` |
| `res.config.settings` | `models/res_config_settings.py` | `Extension` | Provider config fields |

## Tests

| Test Class | Tag | Test Method | Purpose |
|-----------|-----|-------------|---------|
| `TestGeoLocalize` | `external`, `-standard` | `test_default_openstreetmap` | Verify OpenStreetMap geocoding works end-to-end |
| `TestGeoLocalize` | `external`, `-standard` | `test_googlemap_without_api_key` | Verify Google Maps raises error without API key |
| `TestPartnerGeoLocalization` | `-at_install`, `post_install` | `test_geo_localization_notification` | Verify warning notification sent when geolocation fails |

**Important:** The `TestGeoLocalize` tests are tagged `external` meaning they make real HTTP calls to external services. They are excluded from standard test runs (`-standard`).

---

## Related Documentation

- [Core/BaseModel](Core/BaseModel.md) — ORM foundation, abstract models
- [Modules/res.partner](Modules/res.partner.md) — Base partner model
- [Modules/base_address_extended](Modules/base_address_extended.md) — Address structure extension
- [Core/HTTP Controller](Core/HTTP Controller.md) — For understanding `request.geoip`
- [Modules/Stock](Modules/Stock.md) — Uses geolocation for warehouse routing
