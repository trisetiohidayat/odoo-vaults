# partner_autocomplete — Company Data Enrichment via IAP

**Module:** `partner_autocomplete`
**Odoo Version:** 18
**Source:** `~/odoo/odoo18/odoo/addons/partner_autocomplete/`

---

## Overview

The `partner_autocomplete` module enriches `res.partner` records with company data retrieved from IAP (Internet Advertising Platform) services. It provides autocomplete suggestions when entering company names or VAT numbers, and can enrich existing partners with logos, industry classifications, website URLs, and social media profiles.

---

## Architecture

### Model Structure

```
res.partner              # Extended with autocomplete/enrichment fields and methods
res.company              # Extended (minor)
res.partner.autocomplete.source  # IAP service configuration
iap.autocomplete.api     # Extended with partner autocomplete RPC methods
ir.http                  # Extended for autocomplete HTTP endpoint
res.partner.autocomplete.sync   # Partner sync tracking (in data)
```

### File Map

| File | Purpose |
|------|---------|
| `models/res_partner.py` | Autocomplete and enrichment methods |
| `models/res_company.py` | Company-level enrichment |
| `models/iap_autocomplete_api.py` | IAP RPC extensions for autocomplete |
| `models/res_partner_autocomplete_sync.py` | Partner sync metadata |
| `models/ir_http.py` | HTTP extensions for autocomplete endpoint |

---

## res.partner — Autocomplete Extension

**Model:** `res.partner`
**Inheritance:** Extends `res.partner`

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `partner_gid` | `Integer` | Global company database ID from the autocomplete service. Used for deduplication |
| `additional_info` | `Char` | Additional metadata returned by the enrichment service |

### Deprecated Methods

The following methods are deprecated since DnB (Dun & Bradstreet) integration replaced the original IAP service:

```python
@api.model
def autocomplete(self, query, timeout=15):
    return []  # Deprecated

@api.model
def enrich_company(self, company_domain, partner_gid, vat, timeout=15):
    return {}  # Deprecated

@api.model
def read_by_vat(self, vat, timeout=15):
    return []  # Deprecated

def check_gst_in(self, vat):
    return False  # Deprecated
```

---

## Autocomplete Methods

### `autocomplete_by_name(query, query_country_id, timeout)`

Search for companies by name:
```python
def autocomplete_by_name(self, query, query_country_id, timeout=15):
    query_country_code = self.env['res.country'].browse(query_country_id).code
    response, _ = self.env['iap.autocomplete.api']._request_partner_autocomplete(
        'search_by_name', {
            'query': query,
            'query_country_code': query_country_code,
        }, timeout=timeout
    )
    # Format and return results
```

Returns a list of formatted company suggestion dicts.

### `autocomplete_by_vat(vat, query_country_id, timeout)`

Search for companies by VAT number:
1. First calls the autocomplete service's `search_by_vat` endpoint
2. Falls back to VIES (VAT Information Exchange System) if the service returns nothing

VIES fallback:
```python
from stdnum.eu.vat import check_vies
vies_result = check_vies(vat, timeout=timeout)
# Parses vies_result['name'], ['address'], ['countryCode']
# Returns formatted dict with name, vat, street, city, zip, country
```

---

## Enrichment Methods

### `enrich_by_duns(duns, timeout)`

Enrich a partner by D-U-N-S number (Dun & Bradstreet identifier):
```python
response, error = self.env['iap.autocomplete.api']._request_partner_autocomplete(
    'enrich_by_duns', {'duns': duns}, timeout=timeout
)
return self._process_enriched_response(response, error)
```

### `enrich_by_gst(gst, timeout)`

Enrich by GST (Goods and Services Tax) number for India and similar jurisdictions.

### `enrich_by_domain(domain, timeout)`

Enrich by company website domain — the most common enrichment trigger:
```python
response, error = self.env['iap.autocomplete.api']._request_partner_autocomplete(
    'enrich_by_domain', {'domain': domain}, timeout=timeout
)
return self._process_enriched_response(response, error)
```

---

## Data Formatting

### `_iap_replace_location_codes(iap_data)`

Converts IAP response location data (country codes, state codes) to Odoo `res.country` and `res.country.state` records:

```python
def _iap_replace_location_codes(self, iap_data):
    # country_code, country_name → res.country
    if country_code := iap_data.pop('country_code', False):
        country = self.env['res.country'].search([['code', '=ilike', country_code]])

    # state_code, state_name → res.country.state
    if state_code := iap_data.pop('state_code', False):
        state = self.env['res.country.state'].search([
            ('country_id', '=', country.id), ('code', '=ilike', state_code)
        ], limit=1)

    # Replace string codes with browse records
    iap_data['country_id'] = {'id': country.id, 'display_name': country.display_name}
    iap_data['state_id'] = {'id': state.id, 'display_name': state.display_name}
    return iap_data
```

### `_iap_replace_industry_code(iap_data)`

Converts IAP industry codes to Odoo industry references:
```python
if industry_code := iap_data.pop('industry_code', False):
    if industry := self.env.ref(f'base.res_partner_industry_{industry_code}', raise_if_not_found=False):
        iap_data['industry_id'] = {'id': industry.id, 'display_name': industry.display_name}
```

### `_iap_replace_language_codes(iap_data)`

Sets the partner's `lang` field from the IAP `preferred_language` code:
```python
if lang := iap_data.pop('preferred_language', False):
    installed_lang = (
        self.env['res.lang'].search([('code', '=', lang), ('iso_code', '=', lang)])
        or self.env['res.lang'].search([('code', 'ilike', lang[:2])], limit=1)
    )
    iap_data['lang'] = installed_lang.code
```

### `_format_data_company(iap_data)`

Runs all three formatting methods in sequence, returning a normalized data dict ready for partner field mapping.

---

## Enrichment Response Processing

### `_process_enriched_response(response, error)`

Interprets the IAP service response and builds a result dict:

```python
def _process_enriched_response(self, response, error):
    if response and response.get('data'):
        result = self._format_data_company(response.get('data'))
    else:
        result = {}

    if response and response.get('credit_error'):
        result.update({'error': True, 'error_message': 'Insufficient Credit'})
    elif response and response.get('error'):
        result.update({'error': True, 'error_message': 'Unable to enrich company (no credit was consumed).'})
    elif error:
        result.update({'error': True, 'error_message': error})

    return result
```

Key behavior: `error` vs `credit_error` — if the service returns a `credit_error`, credits were NOT consumed (the error occurred before billing). This distinction is important for UI feedback to users.

---

## Tag Integration

### `iap_partner_autocomplete_add_tags(unspsc_codes)`

Creates partner categories from UNSPSC industry classification codes returned by the enrichment service:

```python
def iap_partner_autocomplete_add_tags(self, unspsc_codes):
    # Try Odoo's product_unspsc translation first
    if self.env['ir.module.module']._get('product_unspsc').state == 'installed':
        tag_names = self.env['product.unspsc.code'].search([('code', 'in', [...])]).mapped('name')
    else:
        # Use English names from IAP
        tag_names = [unspsc_name for __, unspsc_name in unspsc_codes]

    # Create or reuse partner categories
    for tag_name in tag_names:
        tag_ids |= self.env['res.partner.category'].search_or_create({'name': tag_name})
    return tag_ids.ids
```

---

## IAP RPC Layer

The actual HTTP calls to the IAP service are in `iap_autocomplete_api.py` via `_request_partner_autocomplete(endpoint, params, timeout)` which calls into `iap.autocomplete.api`'s base `_iap_request()` method.

---

## Widget Integration

### `_get_view(view_id, view_type, **options)`

Overrides the partner form view to add the autocomplete widget to `name` and `vat` fields:

```python
def _get_view(self, view_id=None, view_type='form', **options):
    arch, view = super()._get_view(view_id, view_type, **options)
    if view_type == 'form':
        for node in arch.xpath("//field[@name='name' or @name='vat']"):
            node.set('widget', 'field_partner_autocomplete')
    return arch, view
```

This activates the JavaScript-side autocomplete widget that calls `autocomplete_by_name()` or `autocomplete_by_vat()` as the user types.

---

## Key Design Decisions

1. **Format conversion:** IAP services return standardized codes (ISO country codes, IANA language codes, industry codes), and the module converts these to Odoo's record IDs before returning data. This allows the enriched data to be directly written to partner fields.

2. **VIES fallback:** When the IAP autocomplete service doesn't find a company by VAT, it falls back to the EU's VIES service for VAT number validation and basic company info. This provides a free, authoritative data source for EU companies without consuming IAP credits.

3. **Credit error vs. regular error:** The distinction is critical for UX. A `credit_error` means the user has no credits but should NOT be charged. A regular `error` means something went wrong with the request. Both are surfaced differently in the UI.

4. **`partner_gid` for deduplication:** The global company database ID prevents the same company from being enriched multiple times with conflicting data. If `partner_gid` is already set, subsequent enrichments can be compared or skipped.

5. **Language code matching:** The `_iap_replace_language_codes()` method tries exact ISO code matching first, then falls back to the language family prefix (e.g., `fr_BE` → `fr`). This handles regional language codes gracefully.

6. **Deprecated methods retained:** The old `autocomplete()`, `enrich_company()`, and `read_by_vat()` methods return empty/deprecated values rather than being removed, ensuring backward compatibility with any custom code that might reference them.

---

## Notes

- The module requires an active IAP account with credits for the `partner_autocomplete` service. Credits are consumed per enrichment request.
- The enrichment is typically triggered from the partner form when a website domain is entered, or when the autocomplete widget is used.
- `iap_autocomplete_api.py` extends the base `iap.autocomplete.api` model with the `_request_partner_autocomplete()` RPC method that encodes the database UUID and account token.
- The `field_partner_autocomplete` widget is implemented in JavaScript (`web/static/src/js/...`) and is not covered in this Python documentation.
