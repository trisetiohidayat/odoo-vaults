---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #partner
  - #iap
  - #integration
---

# Partner Autocomplete (`partner_autocomplete`)

> Partner Autocomplete via IAP. Enriches `res.partner` and `res.company` records with company data fetched from the Odoo IAP partner-autocomplete service (powered by DnB / GLEIF). Automatically fills company name, address, phone, email, logo, industry, and legal identifiers (VAT, DUNS, GST) when a user types a company name, domain, or VAT number. Requires an IAP account with credits. This module auto-installs when its dependency `iap_mail` is present.

**Module:** `partner_autocomplete` | **Location:** `odoo/addons/partner_autocomplete/` | **Version:** 1.1

---

## Module Structure

```
partner_autocomplete/
├── models/
│   ├── iap_autocomplete_api.py     # HTTP bridge to IAP partner-autocomplete service
│   ├── res_partner.py              # Partner enrichment methods and formatting
│   ├── res_company.py              # Company auto-enrichment on creation
│   ├── res_config_settings.py      # Settings screen with credit status + buy button
│   └── ir_http.py                  # Session info injection (triggers frontend enrichment)
├── static/
│   ├── src/js/
│   │   ├── partner_autocomplete_core.js     # usePartnerAutocomplete() composable
│   │   ├── partner_autocomplete_component.js # PartnerAutoComplete (OWL AutoComplete subclass)
│   │   ├── partner_autocomplete_fieldchar.js # field_partner_autocomplete widget
│   │   ├── partner_autocomplete_many2one.js  # res_partner_many2one widget
│   │   └── web_company_autocomplete.js       # companyAutocompleteService
│   ├── src/xml/
│   │   └── partner_autocomplete.xml  # QWeb templates (dropdown, notifications)
│   ├── src/scss/
│   │   └── partner_autocomplete.scss  # Width styling for autocomplete Char field
│   ├── lib/jsvat.js               # Client-side VAT number validation
│   └── tests/
│       └── partner_autocomplete.test.js  # Frontend QUnit (hoot) tests
├── views/
│   ├── res_company_views.xml         # Injects invisible iap_enrich_auto_done field
│   └── res_config_settings_views.xml # Injects iap_buy_more_credits widget
├── data/
│   └── iap_service_data.xml          # iap.service record definition
├── tests/
│   ├── common.py               # MockIAPPartnerAutocomplete test mixin
│   └── test_res_company.py     # Backend unit tests
└── i18n/                       # 50+ language .po files
```

---

## Dependency Chain

| Module | Type | Role |
|-------|------|------|
| `iap_mail` | Hard dependency | Provides `iap_mail.enrich_company_by_dnb` mail template; required for `enrich_company_message_post()` |
| `iap` | Required by `iap_mail` | IAP account and credit management |
| `base` | Required transitively | `res.partner`, `res.country`, `res.lang`, etc. |
| `web` | Required | OWL framework, registry, services |
| `mail` | Required transitively | Chatter and messaging |

The module declares `auto_install = True`, meaning Odoo will automatically install it when `iap_mail` is installed.

---

## Models

### 1. `iap.autocomplete.api` — IAP Service Abstraction

**File:** `models/iap_autocomplete_api.py`
**Type:** Abstract model (`_name = 'iap.autocomplete.api'`)
**Inheritance:** None — standalone abstract base

This is the central HTTP bridge. All autocomplete and enrichment calls flow through here.

#### Constants

```python
_DEFAULT_ENDPOINT = 'https://partner-autocomplete.odoo.com'
```

The default IAP service URL. Override via `iap.partner_autocomplete.endpoint` ir.config_parameter for self-hosted or alternative endpoints.

```python
COMPANY_AC_TIMEOUT = 5  # defined in res_partner.py, used in res_company.py
```

Timeout (seconds) for company-level enrichment requests (distinct from the default 15s for partner autocomplete).

#### Method: `_contact_iap(self, local_endpoint, action, params, timeout=15)`

**Signature:**
```python
@api.model
def _contact_iap(self, local_endpoint, action, params, timeout=15):
```

**Purpose:** Builds the full IAP request payload and performs the JSON-RPC call.

**Payload enrichment** — before sending, injects server-side parameters:
```python
params.update({
    'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
    'db_version': release.version,            # e.g. '19.0'
    'db_lang': self.env.lang,                 # Current user language
    'account_token': account.sudo().account_token,
    'country_code': self.env.company.country_id.code,
    'zip': self.env.company.zip,
})
```

**Error handling** (returns a 2-tuple):

| Exception / Condition | Returns |
|---|---|
| `modules.module.current_test` | raises `ValidationError('Test mode')` — allows tests to bypass real calls |
| `ValidationError` from iap_jsonrpc | `(False, 'Insufficient Credit')` |
| `ConnectionError`, `HTTPError`, `AccessError`, `UserError` | `(False, str(exception))` |
| `iap_tools.InsufficientCreditError` | `(False, 'Insufficient Credit')` |
| `ValueError` (no token) | `(False, 'No account token')` |
| Normal completion | `(results_dict, False)` |

All exception cases are also logged at WARNING level.

**Endpoint construction:**
```python
base_url = self.env['ir.config_parameter'].sudo().get_param(
    'iap.partner_autocomplete.endpoint', self._DEFAULT_ENDPOINT
)
return iap_tools.iap_jsonrpc(
    base_url + local_endpoint + '/' + action,
    params=params,
    timeout=timeout
)
```

All partner autocomplete calls go to `/api/dnb/1/<action>`.

#### Method: `_request_partner_autocomplete(self, action, params, timeout=15)`

**Signature:**
```python
@api.model
def _request_partner_autocomplete(self, action, params, timeout=15):
```

**Purpose:** Public-facing method wrapping `_contact_iap`. All callers (`res.partner`, `res.company`) use this entry point.

```python
results = self._contact_iap('/api/dnb/1', action, params, timeout=timeout)
```

**Returns:** `tuple[dict|False, str|False]` — (response_data, error_message). The method docstring explicitly declares `tuple[dict, Literal[False]] | tuple[Literal[False], str]`.

**IAP actions consumed by this module:**
- `search_by_name` — autocomplete by company name
- `search_by_vat` — autocomplete by VAT number
- `enrich_by_duns` — full enrichment by DUNS number
- `enrich_by_gst` — full enrichment by GST number (India)
- `enrich_by_domain` — full enrichment by website domain

---

### 2. `res.partner` Extensions

**File:** `models/res_partner.py`
**Type:** Classic inheritance (`_inherit = 'res.partner'`)

No new database fields are added to `res.partner`. All functionality is via methods.

#### Method: `_iap_replace_location_codes(self, iap_data)`

**Signature:**
```python
@api.model
def _iap_replace_location_codes(self, iap_data):
```

**Purpose:** Converts IAP location string data into proper Odoo Many2one record IDs. IAP returns `country_code`, `country_name`, `state_code`, `state_name`; this method converts them to `{'id': X, 'display_name': Y}` format for ORM writes.

**Algorithm:**
1. Extract and pop `country_code`, `country_name`, `state_code`, `state_name` from `iap_data`
2. Search `res.country` by `code` (case-insensitive) matching `country_code`
3. If not found, fall back to search by `name` matching `country_name`
4. If country found, search `res.country.state` by `country_id` + `code` (case-insensitive)
5. If state not found, fall back to `country_id` + `name` (case-insensitive)
6. Replace raw string keys with `{'id': ..., 'display_name': ...}` dicts

**Edge cases:**
- Silently skips if country not found (no error raised)
- State search only happens after successful country lookup
- Handles partial data (country without state)

#### Method: `_iap_replace_industry_code(self, iap_data)`

**Signature:**
```python
@api.model
def _iap_replace_industry_code(self, iap_data):
```

**Purpose:** Converts IAP `industry_code` (DnB UNSPSC numeric code, e.g., `51111001`) into an Odoo `res.partner.industry` record ID.

```python
if industry_code := iap_data.pop('industry_code', False):
    if industry := self.env.ref(f'base.res_partner_industry_{industry_code}', raise_if_not_found=False):
        iap_data['industry_id'] = {'id': industry.id, 'display_name': industry.display_name}
```

Uses `raise_if_not_found=False` so it silently skips unmapped industry codes.

#### Method: `_iap_replace_language_codes(self, iap_data)`

**Signature:**
```python
@api.model
def _iap_replace_language_codes(self, iap_data):
```

**Purpose:** Maps IAP `preferred_language` (e.g., `en_US`, `fr_BE`, `de`) to an installed `res.lang` record code, which sets the partner's `lang` field.

```python
if lang := iap_data.pop('preferred_language', False):
    installed_lang = (
        # Exact match: fr_BE
        self.env['res.lang'].search([('code', '=', lang), ('iso_code', '=', lang)])
        or
        # Generic match: fr (first 2 chars)
        self.env['res.lang'].search(
            [('code', 'ilike', lang[:2]), ('iso_code', 'ilike', lang[:2])], limit=1
        )
    )
    if installed_lang:
        iap_data['lang'] = installed_lang.code
```

**Edge cases:**
- Falls back from `fr_BE` to `fr` if specific locale not installed
- If no match, does nothing silently

#### Method: `_format_data_company(self, iap_data)`

**Signature:**
```python
@api.model
def _format_data_company(self, iap_data):
```

**Purpose:** Master formatter that applies all three `_iap_replace_*` transformations in sequence, then returns the dict ready for `write()`.

```python
self._iap_replace_location_codes(iap_data)
self._iap_replace_industry_code(iap_data)
self._iap_replace_language_codes(iap_data)
return iap_data
```

#### Method: `autocomplete_by_name(self, query, query_country_id, timeout=15)`

**Signature:**
```python
@api.model
def autocomplete_by_name(self, query, query_country_id, timeout=15):
```

**Purpose:** Returns autocomplete suggestions for a company name string.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Company name (minimum 3 characters enforced client-side) |
| `query_country_id` | int\|False | Filter results by country. `False` = use current company country; `0` = worldwide search |
| `timeout` | int | IAP request timeout in seconds |

**Logic:**
1. Normalize `query_country_id`: if `False`, use `self.env.company.country_id.id`
2. Convert country ID to country code via `res.country.browse().code`
3. Call IAP `_request_partner_autocomplete('search_by_name', {query, query_country_code})`
4. Format each result through `_format_data_company()`
5. Return list of suggestion dicts, or empty list on any error

**Returns:** `list[dict]` — each dict contains keys like `name`, `city`, `country_id`, `vat`, `phone`, `logo`, `street`, `zip`, `state_id`, etc. Empty list if no results or on error.

#### Method: `autocomplete_by_vat(self, vat, query_country_id, timeout=15)`

**Signature:**
```python
@api.model
def autocomplete_by_vat(self, vat, query_country_id, timeout=15):
```

**Purpose:** Returns autocomplete suggestions for a VAT number, with VIES fallback for EU VAT numbers not in the IAP database.

**Logic flow:**
1. Normalize country ID to country code
2. Call IAP `search_by_vat`
3. If successful: format and return results
4. **VIES fallback** (only when IAP returns no results):
   ```python
   vies_result = check_vies(vat, timeout=timeout)
   if vies_result['valid'] and vies_result['name'] != '---':
       # Parse address into street, zip+city, street2
       address = list(filter(bool, vies_result['address'].split('\n')))
       street = address[0]
       zip_city_record = next(filter(lambda addr: re.match(r'^\d.*', addr), address[1:]), None)
       zip_city = zip_city_record.split(' ', 1) if zip_city_record else [None, None]
       street2 = next((addr for addr in filter(lambda addr: addr != zip_city_record, address[1:])), None)
       return [self._iap_replace_location_codes({
           'name': name, 'vat': vat, 'street': street, 'street2': street2,
           'city': zip_city[1], 'zip': zip_city[0],
           'country_code': vies_result['countryCode'],
       })]
   ```
5. Return empty list if neither IAP nor VIES yields results

**Edge cases:**
- VIES timeout: caught and logged at WARNING level, returns empty
- VIES name `'---'`: treated as "not found in VIES database", returns empty
- Address parsing: handles missing zip/city line gracefully
- VIES parsing assumes EU address format (street on first line, zip+city on one line, street2 on another)

#### Method: `_process_enriched_response(self, response, error)`

**Signature:**
```python
@api.model
def _process_enriched_response(self, response, error):
```

**Purpose:** Normalizes IAP enrichment responses into a consistent dict format used by all three `enrich_by_*` methods.

**Returns dict structure:**

| IAP Response | Returned Keys |
|---|---|
| Success (has `data`) | Formatted company data from `_format_data_company()` |
| Credit error (`response.credit_error`) | `{'error': True, 'error_message': 'Insufficient Credit'}` — data IS still returned |
| API error (`response.error`) | `{'error': True, 'error_message': _('Unable to enrich company (no credit was consumed).')}` |
| Exception `error` | `{'error': True, 'error_message': error}` |

**Key distinction:** `credit_error` means credit was consumed (data may still be useful); `error` means no credit was consumed and the caller should handle gracefully.

#### Method: `enrich_by_duns(self, duns, timeout=15)`

**Signature:**
```python
@api.model
def enrich_by_duns(self, duns, timeout=15):
```

**Purpose:** Full company enrichment by D-U-N-S number (9-digit DnB identifier). Called from JavaScript when user selects an autocomplete suggestion (via `enrich_by_duns` or `enrich_by_gst` depending on query type).

**Returns:** `_process_enriched_response()` result dict.

#### Method: `enrich_by_gst(self, gst, timeout=15)`

**Signature:**
```python
@api.model
def enrich_by_gst(self, gst, timeout=15):
```

**Purpose:** Full company enrichment by GST number (India Goods and Services Tax). Validated client-side via regex patterns (15-character Indian GSTIN format) before being sent.

**Returns:** `_process_enriched_response()` result dict.

#### Method: `enrich_by_domain(self, domain, timeout=15)`

**Signature:**
```python
@api.model
def enrich_by_domain(self, domain, timeout=15):
```

**Purpose:** Full company enrichment by website domain. This is the primary method used by `res.company._enrich()` for automatic enrichment on company creation.

**Returns:** `_process_enriched_response()` result dict.

#### Method: `iap_partner_autocomplete_get_tag_ids(self, unspsc_codes)`

**Signature:**
```python
# TODO remove in master
def iap_partner_autocomplete_get_tag_ids(self, unspsc_codes):
```

**Purpose:** Converts DnB UNSPSC industry codes into Odoo `res.partner.category` (tag) records. Called from JavaScript when creating a partner from an autocomplete suggestion.

**Deprecated:** Marked `TODO remove in master` — will be removed in a future major version.

**Logic:**
```python
if self.env['ir.module.module']._get('product_unspsc').state == 'installed':
    tag_names = self.env['product.unspsc.code']\
        .with_context(active_test=False)\
        .search([('code', 'in', [code for code, __ in unspsc_codes])])\
        .mapped('name')
else:
    tag_names = [name for __, name in unspsc_codes]

tag_ids = self.env['res.partner.category']
for tag_name in tag_names:
    if existing_tag := self.env['res.partner.category'].search([('name', '=', tag_name)]):
        tag_ids |= existing_tag
    else:
        tag_ids |= self.env['res.partner.category'].create({'name': tag_name})
return tag_ids.ids
```

**Behavior:** Either reuses existing tags or creates new ones. This can lead to tag proliferation with diverse industry codes. Uses `with_context(active_test=False)` so disabled UNSPSC codes are also searched.

#### Method: `_get_view(self, view_id=None, view_type='form', **options)`

**Signature:**
```python
@api.model
def _get_view(self, view_id=None, view_type='form', **options):
```

**Purpose:** Python view override that injects `widget="field_partner_autocomplete"` onto `name`, `vat`, and `duns` fields in the partner form view. This activates the JavaScript autocomplete widget server-side.

```python
if view_type == 'form':
    for node in arch.xpath("//field[@name='name' or @name='vat' or @name='duns']"):
        node.set('widget', 'field_partner_autocomplete')
```

**Same pattern applied in `res.company._get_view()`** for company forms.

**Why Python vs. XML:** Using `_get_view()` ensures the widget is injected regardless of which view definition is loaded (action-based, direct URL, etc.). XML inheritance could miss cases where the view is overridden elsewhere.

#### Method: `enrich_company_message_post(self, data)`

**Signature:**
```python
def enrich_company_message_post(self, data):
```

**Purpose:** Posts a chatter note using the `iap_mail.enrich_company_by_dnb` mail template, recording all enriched company data on the partner record. Called from JavaScript after the partner is saved.

**Template render values:**
```python
company = {
    'phone': self.phone,
    'name': self.name,
    'email': self.email,
    'company_type': data.get('entity_type', ''),
    'vat': self.vat or self.company_registry,
    'website': self.website,
    'logo': self.image_1920,
    'street': self.street,
    'street2': self.street2,
    'zip_code': self.zip,
    'city': self.city,
    'country': self.country_id.name,
    'state': self.state_id.code,
    'tags': data.get('unspsc_codes', ''),
}
```

Called from `partner_autocomplete_fieldchar.js`:
```javascript
await this.orm.call("res.partner", "enrich_company_message_post", [this.props.record.resId, additionalData]);
```

Where `additionalData` contains `entity_type` and `unspsc_codes` from the IAP enrichment response.

---

### 3. `res.company` Extensions

**File:** `models/res_company.py`
**Type:** Classic inheritance (`_inherit = 'res.company'`)

#### Field: `iap_enrich_auto_done`

```python
iap_enrich_auto_done = fields.Boolean('Enrich Done')
```

**Purpose:** Guard flag preventing enrichment loops. Set to `True` after automatic enrichment completes. Rendered `invisible="1"` in the company form view (via `res_company_views.xml`).

**Default:** `False` on new companies.

#### Method: `create(self, vals_list)`

**Signature:**
```python
@api.model_create_multi
def create(self, vals_list):
```

**Purpose:** Overrides company creation to trigger automatic enrichment.

```python
res = super().create(vals_list)
if modules.module.current_test:
    res.sudo().iap_enrich_auto_done = True  # Skip IAP calls in tests
else:
    res.iap_enrich_auto()
return res
```

**Behavior:**
- In test mode: skips enrichment entirely to prevent real IAP calls
- In production: calls `iap_enrich_auto()` on the recordset (handles batch creates)

#### Method: `_get_view(self, view_id=None, view_type='form', **options)`

**Signature:**
```python
@api.model
def _get_view(self, view_id=None, view_type='form', **options):
```

**Purpose:** Same widget injection pattern as `res.partner._get_view()`: injects `field_partner_autocomplete` onto `name`, `vat`, and `duns` fields in the company form view.

#### Method: `iap_enrich_auto(self)`

**Signature:**
```python
def iap_enrich_auto(self):
```

**Purpose:** Entry point for automatic company enrichment. Called from `create()` and from the frontend `companyAutocompleteService`.

**Guard conditions (all must be true):**
1. `self.env.user._is_system()` — only system/admin users can trigger enrichment
2. `self.env.registry.ready` — registry fully initialized (prevents running during module load)
3. `not company.iap_enrich_auto_done` — company not yet enriched

```python
def iap_enrich_auto(self):
    if self.env.user._is_system() and self.env.registry.ready:
        for company in self.filtered(lambda company: not company.iap_enrich_auto_done):
            company._enrich()
        self.iap_enrich_auto_done = True
    return True
```

**Loop protection:** `iap_enrich_auto_done = True` is set on the recordset after processing, so subsequent calls (e.g., via a write operation) are skipped.

**Called from:**
1. `res.company.create()` — automatic on new company creation
2. `companyAutocompleteService.start()` — frontend trigger on page load:
   ```javascript
   if (session.iap_company_enrich) {
       orm.silent.call("res.company", "iap_enrich_auto", [user.activeCompany.id], {});
   }
   ```

#### Method: `_enrich(self)`

**Signature:**
```python
def _enrich(self):
```

**Purpose:** Performs the actual IAP enrichment call and writes data to the company's linked partner record.

**Flow:**
1. `self.ensure_one()` — processes one company at a time
2. Extract domain via `_get_company_domain()`; return `False` if none
3. Call `self.env['res.partner'].enrich_by_domain(company_domain, timeout=COMPANY_AC_TIMEOUT)`
4. If no data or error, return `False`
5. Filter fields: keep only fields that exist on `partner_id` and are either `image_1920` or currently empty:
   ```python
   company_data = {
       field: value
       for field, value in company_data.items()
       if field in self.partner_id._fields
       and value
       and (field == 'image_1920' or not self.partner_id[field])
   }
   ```
6. Convert `state_id` and `country_id` from display dict to raw ID via `_enrich_extract_m2o_id()`
7. Write filtered data to `self.partner_id`

**Critical behavior:** Enrichment writes to `self.partner_id` (the company's associated contact record), not to the company record itself. `image_1920` is always overwritten even if a logo already exists.

**Returns:** `True` on success, `False` on failure.

#### Method: `_enrich_extract_m2o_id(self, iap_data, m2o_fields)`

**Signature:**
```python
def _enrich_extract_m2o_id(self, iap_data, m2o_fields):
```

**Purpose:** Converts Many2one display-name dicts from IAP (e.g., `{'id': 42, 'display_name': 'Germany'}`) into bare IDs (`42`) before writing.

**Used for:** `'state_id'` and `'country_id'` fields.

#### Method: `_get_company_domain(self)`

**Signature:**
```python
def _get_company_domain(self):
```

**Purpose:** Extracts the company domain for IAP lookup. Priority: email domain > website domain.

```python
# Priority 1: email
company_domain = email_domain_extract(self.email) if self.email else False
if company_domain and company_domain not in iap_tools._MAIL_PROVIDERS:
    return company_domain

# Priority 2: website
company_domain = url_domain_extract(self.website) if self.website else False
if not company_domain or company_domain in ['localhost', 'example.com']:
    return False

return company_domain
```

**Excluded domains (via `iap_tools._MAIL_PROVIDERS`):** Gmail, Yahoo, Hotmail, Outlook, and other free email providers are excluded so email addresses like `info@gmail.com` do not trigger enrichment attempts.

**Domain extraction test cases:**

| Input | Output |
|---|---|
| `website='http://www.info.proximus.be/faq/test'` | `'proximus.be'` |
| `email='info@waterlink.be'` | `'waterlink.be'` |
| `email=False, website=False` | `False` |
| `email='at@'` (invalid format) | `False` |
| `website='http://superFalsyWebsiteName'` | `False` |
| `website='http://www.example.com/biniou'` | `False` |
| `website='http://localhost:8069/~guido/Python.html'` | `False` |
| `website='http://runbot.odoo.com'` | `'odoo.com'` |
| `website='http://www.cwi.nl:80/~guido/Python.html'` | `'cwi.nl'` |

---

### 4. `res.config.settings` Extensions

**File:** `models/res_config_settings.py`
**Type:** Classic inheritance (`_inherit = 'res.config.settings'`)

#### Field: `partner_autocomplete_insufficient_credit`

```python
partner_autocomplete_insufficient_credit = fields.Boolean(
    'Insufficient credit',
    compute="_compute_partner_autocomplete_insufficient_credit"
)
```

**Computed logic:**
```python
def _compute_partner_autocomplete_insufficient_credit(self):
    self.partner_autocomplete_insufficient_credit = (
        self.env['iap.account'].get_credits('partner_autocomplete') <= 0
    )
```

**Display:** Rendered via the `iap_buy_more_credits` widget in `res_config_settings_views.xml`, which shows a buy credits button when this is `True`.

#### Method: `redirect_to_buy_autocomplete_credit(self)`

**Signature:**
```python
def redirect_to_buy_autocomplete_credit(self):
```

**Returns:**
```python
{
    'type': 'ir.actions.act_url',
    'url': self.env['iap.account'].get_credits_url('partner_autocomplete'),
    'target': '_new',
}
```

---

### 5. `ir.http` Extensions

**File:** `models/ir_http.py`
**Type:** Classic inheritance (`_inherit = 'ir.http'`)

#### Method: `session_info(self)`

**Signature:**
```python
def session_info(self):
```

**Purpose:** Injects `iap_company_enrich` flag into the web client session info.

```python
session_info = super().session_info()
if session_info.get('is_admin'):
    session_info['iap_company_enrich'] = not self.env.user.company_id.iap_enrich_auto_done
return session_info
```

**Conditional:** Only applies for admin users. The enrichment flag is `True` when `iap_enrich_auto_done` is `False` (not yet enriched).

---

## Frontend Architecture

The frontend uses OWL 2.x components and a composable hook pattern.

### `usePartnerAutocomplete()` — Core Composable

**File:** `partner_autocomplete_core.js`
**Type:** Functional composable (returns an object of functions, not a component)

This is the central logic layer. It manages all IAP interactions and does not render anything.

**Exported API:**
```javascript
return { autocomplete, getCreateData, removeUselessFields };
```

**Internal functions:**

**`autocomplete(value, queryCountryId)`** — Entry point for search suggestions
- Determines if input is a VAT number (via `jsvat.js`) or GST number (via regex)
- Calls `getSuggestions()` with appropriate ORM method
- Returns array of suggestion objects

**`isVATNumber(value)`** — Validates VAT number format using `checkVATNumber()` from `jsvat.js` (loaded asynchronously in `onWillStart`). `sanitizeVAT()` strips non-alphanumeric characters first.

**`isGSTNumber(value)`** — Validates Indian GSTIN (15-character) via 5 regex patterns:
- Normal/Composite/Casual: `\d{2}[a-zA-Z]{5}\d{4}[a-zA-Z][1-9A-Za-z][Zz1-9A-Ja-j][0-9a-zA-Z]`
- UN/ON Body: `\d{4}[A-Z]{3}\d{5}[UO]N[A-Z0-9]`
- NRI: `\d{4}[a-zA-Z]{3}\d{5}NR[0-9a-zA-Z]`
- TDS: `\d{2}[a-zA-Z]{4}[a-zA-Z0-9]\d{4}[a-zA-Z][1-9A-Za-z][DK][0-9a-zA-Z]`
- TCS: `\d{2}[a-zA-Z]{5}\d{4}[a-zA-Z][1-9A-Za-z]C[0-9a-zA-Z]`

**`getSuggestions(value, isVAT, queryCountryId)`** — ORM call
- Uses `KeepLast` concurrency utility to cancel stale requests
- Calls `autocomplete_by_name` or `autocomplete_by_vat` based on input type
- Optimization: caches `lastNoResultsQuery` to skip empty-result queries (non-VAT only)

**`getCreateData(company, fieldsToKeep)`** — Fetches enrichment data
- Calls `enrich_by_gst` if query is GST, else `enrich_by_duns`
- On credit error: shows `InsufficientCreditNotification` with buy credits link
- On token error: shows `AccountTokenMissingNotification` with config link
- Returns `{ company: data, logo: logo_url, isEnrichAccessible: bool }`

**`removeUselessFields(company, fieldsToKeep)`** — Cleans company data dict before writing, removing fields not present in the form to avoid "Field_changed" validation errors.

### `PartnerAutoComplete` — OWL AutoComplete Subclass

**File:** `partner_autocomplete_component.js`
**Extends:** `@web/core/autocomplete/autocomplete`

```javascript
export class PartnerAutoComplete extends AutoComplete {
    static template = "partner_autocomplete.PartnerAutoComplete";
    setup() {
        super.setup();
        this.shouldSearchWorldwide = false;
    }
}
```

**Override: `loadOptions(options, request)`** — Passes `shouldSearchWorldwide` flag to the options function.

**Override: `searchWorldwide(ev)`** — Toggles `shouldSearchWorldwide = true`, closes and reopens dropdown with `queryCountryId=0` (worldwide search). The "Search Worldwide" option appears in the dropdown when results exist and the search is not already worldwide.

### `PartnerAutoCompleteCharField` — Char Field Widget

**File:** `partner_autocomplete_fieldchar.js`
**Widget registered:** `field_partner_autocomplete`
**Extends:** `CharField`

```javascript
export const partnerAutoCompleteCharField = {
    ...charField,
    component: PartnerAutoCompleteCharField,
};
registry.category("fields").add("field_partner_autocomplete", partnerAutoCompleteCharField);
```

**Behavior:**
- Renders `PartnerAutoComplete` only for company-type partners (`company_type === 'company'` OR `resModel !== 'res.partner'`)
- Does NOT render for individual contacts (`company_type === 'individual'`)
- On suggestion selection: fetches enrichment data, sets logo, filters fields, updates record, saves and posts chatter message for `res.partner`

**Search condition:** Requires minimum 3 characters via `validateSearchTerm(request)`.

### `PartnerAutoCompleteMany2one` — Many2one Field Widget

**File:** `partner_autocomplete_many2one.js`
**Widget registered:** `res_partner_many2one`

Replaces `Many2One` for partner fields. Uses custom `PartnerMany2XAutocomplete` that swaps the base `AutoComplete` for `PartnerAutoComplete`.

**On selection:** Opens the standard many2one creation modal with all company data pre-filled as `default_*` context values. `onRecordSaved` callback updates the parent_id field with the newly created partner's ID.

**Hidden when** `canCreate === False` (i.e., `no_create=True` in field options).

### `companyAutocompleteService` — Company Auto-enrichment Service

**File:** `web_company_autocomplete.js`
**Service name:** `partner_autocomplete.companyAutocomplete`

Registered as a web service. On startup, checks `session.iap_company_enrich` and triggers enrichment for the active company.

```javascript
start(env, { orm }) {
    if (session.iap_company_enrich) {
        orm.silent.call("res.company", "iap_enrich_auto", [user.activeCompany.id], {});
    }
}
```

Uses `silent.call` — failures generate no user-visible error.

### QWeb Templates

**File:** `static/src/xml/partner_autocomplete.xml`

Key templates:
- `partner_autocomplete.PartnerAutoComplete` — extends `web.AutoComplete`, adds "Search Worldwide" option
- `partner_autocomplete.PartnerAutoCompleteCharField` — extends `web.CharField`, conditionally renders autocomplete
- `partner_autocomplete.PartnerAutoCompleteMany2XField` — extends `web.Many2XAutocomplete`, replaces AutoComplete
- `partner_autocomplete.DropdownOption` — renders company name + city/country
- `partner_autocomplete.InsufficientCreditNotification` — buy credits link
- `partner_autocomplete.AccountTokenMissingNotification` — set token link
- `partner_autocomplete.PartnerAutoCompleteMany2one` — Many2one widget with autocomplete slot

---

## Data Files

### `data/iap_service_data.xml`

```xml
<record id="iap_service_partner_autocomplete" model="iap.service">
    <field name="name">Partner Autocomplete</field>
    <field name="technical_name">partner_autocomplete</field>
    <field name="description">Automatically enrich your contact base with corporate data.</field>
    <field name="unit_name">Enrichments</field>
    <field name="integer_balance">True</field>
</record>
```

- `integer_balance="True"`: credits displayed as whole numbers
- `unit_name="Enrichments"`: display name for credit consumption unit

---

## Views

### `views/res_company_views.xml`

```xml
<xpath expr="//field[@name='company_registry']" position="after">
    <field name="iap_enrich_auto_done" invisible="1"/>
</xpath>
```

Ensures `iap_enrich_auto_done` is in the view so it can be written by `_enrich()`.

### `views/res_config_settings_views.xml`

```xml
<setting id="partner_autocomplete" position="inside">
    <widget name="iap_buy_more_credits" service_name="partner_autocomplete" hide_service="1"/>
</setting>
```

Injects the credit buy widget into the general settings screen. `hide_service="1"` hides the service name label.

---

## Assets (Manifest)

```python
'assets': {
    'web.assets_backend': [
        'partner_autocomplete/static/src/scss/*',
        'partner_autocomplete/static/src/js/*',
        'partner_autocomplete/static/src/xml/*',
    ],
    'web.jsvat_lib': [  # Loaded before main bundle
        'partner_autocomplete/static/lib/**/*',
    ],
    'web.assets_unit_tests': [
        'partner_autocomplete/static/tests/**/*',
    ],
}
```

**Key observations:**
- `web.jsvat_lib` loads before the main bundle, ensuring `checkVATNumber()` is available before field rendering
- `web.assets_backend` loads the entire SCSS/JS/XML package on every backend page (small footprint)
- Unit test assets are loaded only during test runs

---

## L3: Escalation Topics

### Three Enrichment Paths

The module has **three distinct enrichment paths** that can overlap:

**Path 1: Automatic company creation enrichment**
```
res.company.create() → iap_enrich_auto() → _enrich() → enrich_by_domain(domain)
```
- Triggered on every new company (unless in test mode)
- Uses `_get_company_domain()` to extract domain from email or website
- Writes to the company's `partner_id` record
- Guarded by `_is_system()` and `registry.ready`

**Path 2: Manual partner form autocomplete + enrichment**
```
User types company name/VAT in partner form
  → field_partner_autocomplete widget activates
  → autocomplete_by_name/vat RPC
  → User selects suggestion
  → getCreateData() → enrich_by_duns/gst
  → record.update() + enrich_company_message_post()
```
- Triggered on demand via user interaction
- Requires minimum 3 characters
- VIES fallback for EU VAT not in IAP

**Path 3: Frontend company enrichment on page load**
```
session_info() → iap_company_enrich=True
  → companyAutocompleteService.start()
  → res.company.iap_enrich_auto()
```
- Only runs for admin users
- Only runs if `iap_enrich_auto_done=False`
- Uses `silent.call` (failures are invisible to user)

### VIES Fallback Logic

`autocomplete_by_vat` has a cascading fallback:

1. **Primary:** IAP `search_by_vat` — enriched data (name, address, logo, industry)
2. **Fallback:** VIES (European Commission free service) — basic data (name, address)
3. **None:** empty list

VIES is used because not all EU companies are in the DnB database. VIES requires valid EU VAT format input (enforced client-side via `jsvat.js`).

### Field Overwrite Protection

The `_enrich()` field filtering is critical:
```python
company_data = {field: value for field, value in company_data.items()
                if field in self.partner_id._fields
                and value
                and (field == 'image_1920' or not self.partner_id[field])}
```

This means:
- Only fields that exist on `res.partner` are written (prevents ORM errors)
- `image_1920` is ALWAYS overwritten (logo refresh)
- All other fields are only written if currently empty (preserves manual edits)

This is important in multi-company scenarios where enrichment data may be less complete than manually entered data.

### UNSPSC Tag Proliferation Risk

`iap_partner_autocomplete_get_tag_ids` creates `res.partner.category` records on-the-fly from DnB industry codes. With diverse industry codes, this can create many tags. The method is marked deprecated (`TODO remove in master`), suggesting this behavior will be redesigned or removed.

### Company-Partner Dualism

In Odoo, every `res.company` record has a corresponding `res.partner` record (`company.partner_id`). Enrichment writes to the partner, not the company. This means:
- The company form shows the enriched partner data via `partner_id` display
- Partner search/autocomplete operates on the enriched partner record
- Company-specific fields (like `company_registry`) are NOT overwritten by IAP data

---

## L4: Performance, Security, and Version History

### Performance Considerations

1. **`KeepLast` concurrency:** `partner_autocomplete_core.js` uses `KeepLast` to cancel in-flight autocomplete requests when the user continues typing, preventing stale results.

2. **No-results query caching:** For name searches (non-VAT), if a query returns no results, subsequent queries that start with the cached query return empty immediately. This avoids redundant IAP calls.

3. **Debounce:** Client-side has a 250ms debounce before sending requests (visible in tests via `advanceTime(250)`).

4. **`silent.call` for company enrichment:** Uses `orm.silent.call` for the frontend company enrichment trigger, so network failures don't generate error notifications.

5. **Lazy library loading:** `jsvat.js` is loaded on demand in `onWillStart()`, not eagerly at module load.

6. **Python view overrides:** `_get_view()` in Python applies the widget injection on every form view load. XML inheritance would also apply on every load, but Python approach ensures consistent behavior across all view load paths.

### Security Considerations

1. **System user guard:** `iap_enrich_auto()` checks `_is_system()`, preventing regular users from manually triggering enrichment.

2. **Registry ready check:** Prevents enrichment from running during module loading, avoiding transaction timing issues.

3. **Credit system enforcement:** All IAP methods use the standard Odoo IAP credit system. `InsufficientCreditError` is caught and returns an error dict rather than crashing.

4. **No raw SQL:** All database operations use the ORM. No `cr.execute()` calls present.

5. **Input sanitization:**
   - VAT numbers sanitized client-side: `value.replace(/[^A-Za-z0-9]/g, '')`
   - Country codes derived from existing `res.country` records (validated)
   - Domain extraction uses established Odoo tools (`email_domain_extract`, `url_domain_extract`)

6. **Admin-only session flag:** `iap_company_enrich` is only set for admin users.

7. **QWeb auto-escaping:** All user content rendered via `t-esc` (auto-escaped). No raw HTML injection points.

8. **No PII in logs:** IAP requests include `db_uuid` and `db_version` but not partner-specific data in log messages.

### Odoo 18 to Odoo 19 Changes

**Widget registration pattern:**
Odoo 19 uses the new field description object pattern instead of string-based registration:

```javascript
// Odoo 19 pattern
export const partnerAutoCompleteCharField = {
    ...charField,
    component: PartnerAutoCompleteCharField,
};
registry.category("fields").add("field_partner_autocomplete", partnerAutoCompleteCharField);
```

The `buildM2OFieldDescription()` function (used by the Many2one widget) is an Odoo 17+ pattern refined in 19.

**OWL 2.x patterns:** The module uses OWL's static components, `useChildRef`, `useInputField` hooks, and `<t t-set-slot>` for slot composition.

**Test framework:** Frontend tests use `hoot` (Odoo's JavaScript testing framework), with `expect`, `test`, `mountView`, `onRpc`, and `preloadBundle` helpers. Backend tests use the established `TransactionCase` pattern.

**Session info:** The `session_info()` method in `ir_http.py` is the standard Odoo 16+ mechanism for passing server state to the frontend. The `is_admin` flag is provided by the base `ir.http` model.

---

## Testing

### Backend Tests (`tests/test_res_company.py`)

Uses `TransactionCase` with `MockIAPPartnerAutocomplete` mixin. Covers:
- `_enrich()` returns `False` when no email/website is set
- `_enrich()` returns `True` and sets country when email is set
- `_get_company_domain()` domain extraction from email and website URLs
- Excludes free email providers (gmail, yahoo, etc.)
- Excludes localhost and example.com
- Handles malformed URLs gracefully

### Frontend Tests (`tests/partner_autocomplete.test.js`)

Uses Odoo's `hoot` testing framework with `expect`, `test`, `mountView`, `onRpc`, `preloadBundle`. Covers:
- Autocomplete hidden for `company_type = 'individual'`
- Autocomplete shown for `company_type = 'company'` (name field)
- VAT field autocomplete (validates VAT format, triggers on valid VAT)
- Minimum 3-character search requirement
- "Search Worldwide" option appears when country-filtered results exist
- Many2one field autocomplete for `parent_id`
- Pre-filling of partner form fields on suggestion selection
- `canCreate` control (no autocomplete when `no_create=True`)
- Error handling (insufficient credit, token missing)
- Clear on click-out behavior
- Unset partner many2one field

### Mock Pattern (`tests/common.py`)

`MockIAPPartnerAutocomplete` patches `IapAutocompleteApi._contact_iap` with a context manager that returns simulated IAP responses. Allows tests to run without real IAP credentials or network access. Only `enrich_by_domain` action is currently mocked.

---

## Configuration Checklist

To use this module:

- [ ] `partner_autocomplete` module installed (auto-installs with `iap_mail`)
- [ ] IAP account with technical name `partner_autocomplete` exists
- [ ] Sufficient credits in the IAP account
- [ ] `iap_mail` module installed (dependency)
- [ ] For automatic company enrichment: admin user creates company with email or website set
- [ ] For manual enrichment: user types 3+ characters in `name`, `vat`, or `duns` field on a company-type partner form

---

## Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| No autocomplete suggestions | No IAP account or credits | Configure IAP account, buy credits |
| VIES lookup fails | VAT not in EU format | Use IAP search by name instead |
| Company not enriched on creation | Not admin or registry not ready | Verify user is admin, ensure full Odoo boot completed |
| "Search Worldwide" not appearing | Query returned results AND country is set | Expected: option only shows when country-filtered results exist |
| Partner form fields not pre-filled | Field not present in form view | Add field to the partner form view XML |
| Tag creation creates too many tags | IAP returns many UNSPSC codes | Expected behavior; method is deprecated and will be removed |
| Enrichment loops despite guard | `iap_enrich_auto_done` not persisted | Check view has `iap_enrich_auto_done` field present (invisible) |