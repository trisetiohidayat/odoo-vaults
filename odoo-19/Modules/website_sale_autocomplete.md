---
tags:
  - odoo
  - odoo19
  - modules
  - website
  - ecommerce
  - google
  - address
created: 2026-04-11
description: Real-time address autocomplete on e-commerce checkout using Google Places API, auto-filling street, city, zip, state, and country.
---

# website_sale_autocomplete

## Module Overview

| Attribute     | Value                                                                    |
|---------------|--------------------------------------------------------------------------|
| Directory     | `odoo/addons/website_sale_autocomplete/`                                 |
| Version       | `1.0` (manifest), Odoo CE 19                                            |
| Depends       | `website_sale`, `google_address_autocomplete`                            |
| Category      | `Website/Website`                                                        |
| License       | `LGPL-3`                                                                 |
| Author        | Odoo S.A.                                                                |
| Auto-install  | `True` (installs automatically when both dependencies are present)        |
| Installable   | Yes                                                                      |

**Purpose:** Integrates Google Places API into the website checkout address form (`/shop/address`) to provide real-time address autocomplete. When users type their street address during checkout, the module queries Google Places and presents suggestions. Selecting a suggestion auto-fills all address components (street with number, city, zip, state, country) from Google's structured response.

**Dependency chain:** This module builds on `google_address_autocomplete` (Hidden/Tools), which provides the base `AutoCompleteController`, the `googlePlacesSession` JS singleton, the `FIELDS_MAPPING` translation table, and the Google Places API integration. `website_sale_autocomplete` adds per-website API key routing and the frontend `AddressForm` Interaction.

---

## Module Files

```
website_sale_autocomplete/
├── __init__.py                      # Imports controllers + models
├── __manifest__.py                  # Depends: website_sale, google_address_autocomplete
├── controllers/
│   └── main.py                      # WebsiteSaleAutoCompleteController
├── models/
│   ├── __init__.py                  # Imports website, res_config_settings
│   ├── website.py                    # website.google_places_api_key + has_google_places_api_key()
│   └── res_config_settings.py       # website_google_places_api_key related field
├── views/
│   ├── templates.xml                # Inherits website_sale.address_form_fields
│   └── res_config_settings_views.xml # API key field in website settings UI
├── static/
│   ├── src/
│   │   ├── interactions/
│   │   │   └── address_form.js       # AddressForm Interaction (Odoo 17+)
│   │   └── xml/
│   │       └── autocomplete.xml      # AutocompleteDropDown QWeb template
│   └── tests/
│       └── autocomplete_tour.js      # Tour test: add to cart → checkout → autocomplete
└── tests/
    └── test_ui.py                   # HttpCase test with mocked Google API
```

---

## L1: How Address Autocomplete Works on Website Checkout

At the most fundamental level, this module intercepts the user typing in the **Street Address** field during e-commerce checkout, sends the partial input to Google Places API, and fills in all address components (street, city, zip, state, country) when the user selects a suggestion.

**User activation path:**
1. Install `website_sale_autocomplete` and `google_address_autocomplete` (both dependencies)
2. Go to **Website > Configuration > Settings** (under the relevant website)
3. Locate the **Google Places API Key** field (inside the autocomplete section)
4. Paste the Google Cloud API key, click **Save**
5. Go to `/shop/address` (checkout address step)
6. Type 5+ characters of a known street address
7. The Google-powered dropdown appears
8. Clicking a suggestion auto-fills all address fields

**Architecture at a glance:**

```
User types in <input name="street"> on /shop/address
    │
    ▼
AddressForm Interaction activates
    │  (registered in public.interactions registry)
    │  Selector: .oe_cart .address_autoformat
    │  SelectorHas: input[name='street'][data-autocomplete-enabled='1']
    │
    ▼
onStreetInput() fires (200ms debounced)
    │
    ▼
googlePlacesSession.getAddressPropositions({partial_address: "123 Mai..."})
    │  RPC: POST /autocomplete/address
    │  Session token: UUID (generated once, reused across calls)
    │
    ▼
WebsiteSaleAutoCompleteController._get_api_key(use_employees_key=False)
    │  Returns: website.google_places_api_key (via sudo())
    │
    ▼
google_address_autocomplete: _perform_place_search()
    │  Calls: Google Places Autocomplete API
    │  Returns: [{formatted_address, google_place_id}, ...]
    │
    ▼
AutocompleteDropDown QWeb template rendered
    │  Bootstrap dropdown-menu with "Powered by Google" badge
    │
    ▼
User clicks suggestion
    │
    ▼
googlePlacesSession.getAddressDetails({google_place_id: "ChIJ..."})
    │  RPC: POST /autocomplete/address_full
    │
    ▼
google_address_autocomplete: _perform_complete_place_search()
    │  Calls: Google Places Details API
    │  Translates: address_components → standard_data via FIELDS_MAPPING
    │  Returns: {country: [id,name], state: [id,name], city, zip, street, number, formatted_street_number}
    │
    ▼
AddressForm: onClickAutocompleteResult()
    │  Sets: streetInput.value, cityInput.value, zipInput.value
    │  Sets: countrySelect.value (ID), triggers country change
    │  Sets: stateSelect.value via MutationObserver (waits for options)
```

---

## L2: Field Types, Defaults, Constraints — Google Places API Key

### `website` — Extension

**File:** `models/website.py`

```python
class Website(models.Model):
    _inherit = 'website'

    google_places_api_key = fields.Char(
        string='Google Places API Key',
        groups="base.group_system")

    def has_google_places_api_key(self):
        return bool(self.sudo().google_places_api_key)
```

| Property              | Value                                                                            |
|-----------------------|----------------------------------------------------------------------------------|
| Type                  | `Char`                                                                           |
| Stored                | Yes — column on `website` table                                                  |
| Default               | `False` / empty string                                                           |
| Groups                | `base.group_system` — only System Administrator can view/edit                     |
| `has_google_places_api_key()` | Method; uses `sudo()` to bypass ACL; returns `bool`                        |

**`has_google_places_api_key()` behavior:**
- Uses `sudo()` to bypass record-level ACL — a portal user on the website still needs to check if autocomplete is enabled without needing read access to `base.group_system`
- Returns `True` if key is non-empty; `False` otherwise
- Called from the QWeb template to gate the `data-autocomplete-enabled` attribute
- Also referenced in the `AddressForm` Interaction's `selectorHas` static check

**Performance note:** The `sudo()` call is safe here because the field holds a public-facing API key with no personal data. It avoids granting `base.group_system` read access to portal users.

---

### `res.config.settings` — Extension

**File:** `models/res_config_settings.py`

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    website_google_places_api_key = fields.Char(
        string="Website's Google Places API Key",
        related='website_id.google_places_api_key',
        readonly=False)
```

| Property                           | Value                                                      |
|------------------------------------|------------------------------------------------------------|
| Type                               | `Char` (related field)                                     |
| Related Target                     | `website_id.google_places_api_key`                          |
| `readonly=False` override           | Makes the inherited-readonly related field editable in the form |
| Write-through behavior             | On save, writes directly to `website.google_places_api_key`  |

**`readonly=False` on a related field:** A standard related field inherits `readonly=True` from the base `fields.Char` definition. Setting `readonly=False` overrides this, allowing the field to appear as an editable input in the settings form. On save, Odoo writes through the relation — to the `website_id` record that is always present in the form's context — and then to `website.google_places_api_key`.

---

### Settings UI — `res_config_settings_views.xml`

**File:** `views/res_config_settings_views.xml`

```xml
<record id="res_config_settings_view_form_inherit_autocomplete_googleplaces" model="ir.ui.view">
    <field name="inherit_id" ref="website_sale.res_config_settings_view_form"/>
    <field name="arch" type="xml">
        <xpath expr="//setting[@id='autocomplete_googleplaces_setting']" position="inside">
            <div>
                <div class="content-group row mt16">
                    <label class="col-4" for="website_google_places_api_key" string="API Key"/>
                    <field class="col-6" name="website_google_places_api_key"/>
                </div>
                <div class="mt8">
                    <a target="_blank" href="https://console.cloud.google.com/getting-started">
                        <i class="oi oi-arrow-right"/>
                        Create a Google Project and get a key
                    </a>
                    <br/>
                    <a target="_blank" href="https://console.cloud.google.com/billing">
                        <i class="oi oi-arrow-right"/>
                        Enable billing on your Google Project
                    </a>
                </div>
            </div>
        </xpath>
    </field>
</record>
```

**XPath target:** `//setting[@id='autocomplete_googleplaces_setting']` — this is an existing `<setting>` block defined by `website_sale` in its settings form. The module injects the API key field and help links inside it.

---

## L3: Cross-Model Integration, Override Pattern, Workflow Trigger

### Cross-Model Chain: Website ↔ Google Places API ↔ Partner

```
res.config.settings (Settings UI)
    └── website_google_places_api_key (related)
            │
            ▼
website.google_places_api_key (Char field, base.group_system)
    │
    ├── read by: has_google_places_api_key() → gates data-autocomplete-enabled attribute
    │
    ▼
views/templates.xml: QWeb template inheritance
    └── t-att-data-autocomplete-enabled="1 if website.has_google_places_api_key() else 0"
            │
            ▼
DOM: <input name="street" data-autocomplete-enabled="1">
    │
    ▼
AddressForm Interaction (activated if selector + selectorHas both match)
    │
    ├── onStreetInput() → googlePlacesSession.getAddressPropositions()
    │       └── RPC: POST /autocomplete/address
    │               └── WebsiteSaleAutoCompleteController._get_api_key(use_employees_key=False)
    │                       └── request.env['website'].get_current_website().sudo().google_places_api_key
    │
    └── onClickAutocompleteResult() → googlePlacesSession.getAddressDetails()
            └── RPC: POST /autocomplete/address_full
                    └── _perform_complete_place_search()
                            ├── FIELDS_MAPPING: Google types → Odoo fields
                            ├── res.country lookup by ISO code
                            ├── res.country.state lookup by code within country scope
                            └── Returns: {country: [id,name], state: [id,name], city, zip, ...}

Auto-filled into: website_sale checkout form → res.partner record on submit
```

### Override Pattern: `_get_api_key`

**File:** `controllers/main.py`

```python
from odoo.addons.google_address_autocomplete.controllers.google_address_autocomplete import AutoCompleteController

class WebsiteSaleAutoCompleteController(AutoCompleteController):
    def _get_api_key(self, use_employees_key):
        if not use_employees_key:
            return request.env['website'].get_current_website().sudo().google_places_api_key
        return super()._get_api_key(use_employees_key)
```

**Parent:** `google_address_autocomplete.controllers.google_address_autocomplete.AutoCompleteController`

```python
# In google_address_autocomplete/base controller:
def _get_api_key(self, use_employees_key):
    assert request.env.user._is_internal()
    return request.env['ir.config_parameter'].sudo().get_param(
        'google_address_autocomplete.google_places_api_key')
```

| `use_employees_key` | `website_sale_autocomplete` behavior                                 |
|---------------------|----------------------------------------------------------------------|
| `False` (normal flow) | Returns current website's per-site API key via `sudo()`             |
| `True` (employee fallback) | Delegates to `super()` — reads global `ir.config_parameter` key |

**Routing is inherited, not overridden.** The two route endpoints are defined in the parent controller:

| Route                          | Method                          | Calls                                   |
|--------------------------------|---------------------------------|-----------------------------------------|
| `POST /autocomplete/address`   | `_autocomplete_address()`       | `_perform_place_search()` → Google Autocomplete API |
| `POST /autocomplete/address_full` | `_autocomplete_address_full()` | `_perform_complete_place_search()` → Google Details API |

### Workflow Trigger: Address Selection → Partner Update

There is no automatic database write. The workflow is entirely client-side:

```
User types 5+ chars in street field
    │
    ▼
Google Places Autocomplete returns suggestions (list of addresses)
    │
    ▼
User clicks a suggestion
    │
    ▼
Google Places Details API returns structured address components
    │
    ▼
Frontend sets DOM input values:
    - street.value    = formatted_street_number
    - city.value      = city  (or "")
    - zip.value       = zip   (or "")
    - country.value   = res.country.id  (then triggers "change" event)
    │
    ▼
User clicks "Confirm" on checkout form
    │
    ▼
Standard website_sale controller processes /shop/address submission
    └── Creates/updates res.partner with the submitted address fields
```

**The actual `res.partner` write happens in `website_sale`'s checkout controller**, not in this module. This module only populates the form fields client-side.

---

## L4: Odoo 18 to 19 Changes, Security

### Odoo 18 → 19 Changes

No changes specific to `website_sale_autocomplete` were identified between Odoo 18 and Odoo 19. The module's architecture — Interaction system, `googlePlacesSession` RPC singleton, `KeepLast` deduplication, per-website key routing — is consistent across versions.

**Key architectural stability:**
- The **Odoo 17+ Interaction system** (`@web/public/interaction`, `registry.category("public.interactions")`) was introduced in Odoo 17 and remains unchanged in 19
- The `googlePlacesSession` JS singleton, `KeepLast` utility, and `renderAt()` pattern are all stable
- The `FIELDS_MAPPING` in the base `google_address_autocomplete` module has not changed
- The base `AutoCompleteController` routes (`/autocomplete/address`, `/autocomplete/address_full`) are unchanged

**The `Interaction` base class** from `@web/public/interaction` is the Odoo 17+ frontend component model. It provides:
- `setup()` — called once on activation
- `dynamicContent` — Owl template for declarative event binding
- `waitFor()` — promise wrapper that respects Interaction cancellation
- `debounced()` — utility method used on the `onStreetInput` handler
- `renderAt()` — renders a QWeb template into a DOM target

No changes to these APIs were found between Odoo 18 and 19.

### Security Analysis

| Concern                           | Risk Level | Detail                                                        |
|-----------------------------------|-----------|---------------------------------------------------------------|
| API key exposure                   | LOW        | API key is public-facing by design; scoped/restricted in Google Cloud Console |
| `sudo()` on `google_places_api_key` | SAFE      | Field is non-sensitive (public API key); no PII or credentials |
| `use_employees_key` assertion     | SAFE       | Base `_get_api_key` asserts `_is_internal()` only for `use_employees_key=True` |
| Frontend ID injection             | SAFE       | Backend returns `[id, name]` tuples; frontend uses only `address.country[0]` (ID) for `<select>` value |
| XSS in address fields             | SAFE       | Google Place IDs are opaque tokens; DOM values set as strings not evaluated |
| Session token in URL/headers       | SAFE       | Session token is an opaque UUID; not used for authentication |
| Google ToS compliance             | LOW        | "Powered by Google" badge required and included in dropdown template |
| No database writes by autocomplete | SAFE       | Address saved only when user submits checkout form via standard `website_sale` controller |

**API key exposure — full analysis:**

The per-website API key is readable by any website visitor through two paths:
1. The `has_google_places_api_key()` QWeb call on page load
2. The DOM attribute `data-autocomplete-enabled` (a boolean flag, not the key itself)

The key itself is not exposed client-side in the DOM. In Google Cloud Console, the key should be restricted by HTTP referrer to the Odoo instance domain. This prevents the key from being used from other websites. The key is scoped to the Google Places API only.

**Frontend → Backend ID injection — full analysis:**

The backend `_translate_google_to_standard()` method returns country and state as `[id, name]` tuples:
```python
country = request.env['res.country'].search([('code', '=', short_name.upper())])
standard_data['country'] = [country.id, country.name]
```

The frontend uses only the ID:
```javascript
this.countrySelect.value = address.country[0];  // Odoo res.country.id
```

This ID is only valid within the current Odoo database. No raw SQL or XSS vectors are exposed. The `<select>` element uses Odoo's standard value binding.

**Session token billing security:**
Google session tokens prevent per-keystroke billing. The `KeepLast` frontend deduplication further reduces billable sessions. A user who abandons the page after typing but before selecting leaves an incomplete session — Google may not charge for it. The token is not used for authentication or authorization.

**Google Terms of Service:**
Google requires the "Powered by Google" branding whenever Google data is used in a UI. Odoo enforces this by including `powered_by_google_on_white.png` in the `AutocompleteDropDown` QWeb template served from the `google_address_autocomplete` module's static files.

---

## View Inheritance

### Checkout Address Form — `views/templates.xml`

**File:** `views/templates.xml`

```xml
<template id="website_sale_address_with_autocomplete" inherit_id="website_sale.address_form_fields">
    <input name="street" position="attributes">
        <attribute name="t-att-data-autocomplete-enabled">
            1 if website.has_google_places_api_key() else 0
        </attribute>
    </input>
</template>
```

Inherits from `website_sale.address_form_fields` (the standard Odoo e-commerce address form fields template). Adds `t-att-data-autocomplete-enabled` to the `street` `<input>` element. This creates a two-layer activation gate:
1. `AddressForm` registered in `public.interactions` registry (always present in DOM if module installed)
2. `selectorHas: "input[name='street'][data-autocomplete-enabled='1']"` — only matches if attribute is `'1'`

If no API key is configured, the attribute is `'0'`, the selector does not match, and the Interaction never activates — zero event listeners attached, no performance cost.

---

## Frontend: `AddressForm` Interaction

**File:** `static/src/interactions/address_form.js`

### Registration

```javascript
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class AddressForm extends Interaction {
    static selector = ".oe_cart .address_autoformat";
    static selectorHas = "input[name='street'][data-autocomplete-enabled='1']";

    dynamicContent = {
        "input[name='street']": { "t-on-input.withTarget": this.debounced(this.onStreetInput, 200) },
        ".js_autocomplete_result": { "t-on-click.withTarget": this.onClickAutocompleteResult },
    };
}
registry.category("public.interactions").add("website_sale_autocomplete.address_form", AddressForm);
```

### Setup

```javascript
setup() {
    this.streetAndNumberInput = this.el.querySelector("input[name='street']");
    this.cityInput           = this.el.querySelector("input[name='city']");
    this.zipInput            = this.el.querySelector("input[name='zip']");
    this.countrySelect       = this.el.querySelector("select[name='country_id']");
    this.stateSelect         = this.el.querySelector("select[name='state_id']");
    this.keepLast            = new KeepLast();
}
```

All references are direct DOM queries — no reactive bindings. `this.el` is the element matching `AddressForm.selector` (the `.address_autoformat` form container).

### `onStreetInput()` — Suggestion Flow

```javascript
async onStreetInput(ev, inputEl) {
    const inputContainerEl = inputEl.parentNode;
    if (inputEl.value.length >= 5) {
        this.keepLast.add(
            googlePlacesSession.getAddressPropositions({
                partial_address: inputEl.value,
            }).then((response) => {
                inputContainerEl.querySelector(".dropdown-menu")?.remove();
                this.renderAt("website_sale_autocomplete.AutocompleteDropDown", {
                    results: response.results,
                }, inputContainerEl);
            })
        );
    } else {
        inputContainerEl.querySelector(".dropdown-menu")?.remove();
    }
}
```

**Step-by-step:**
1. If input < 5 chars: silently remove any existing dropdown
2. If input >= 5 chars: call `googlePlacesSession.getAddressPropositions()`
3. `this.keepLast.add(...)` — if another `onStreetInput` fires before this promise resolves, the pending `.then()` is discarded
4. On response: remove old dropdown, render new one via `renderAt()` pointing to `AutocompleteDropDown` QWeb template
5. `response.results` is `[{formatted_address, google_place_id}, ...]`

### `onClickAutocompleteResult()` — Selection and Auto-fill

```javascript
async onClickAutocompleteResult(ev, currentTargetEl) {
    const dropdownEl = currentTargetEl.parentNode;

    // Replace dropdown with spinner
    dropdownEl.innerText = "";
    dropdownEl.classList.add("d-flex", "justify-content-center", "align-items-center");
    const spinnerEl = document.createElement("div");
    spinnerEl.classList.add("spinner-border", "text-warning", "text-center", "m-auto");
    dropdownEl.appendChild(spinnerEl);

    // Fetch full address details
    const address = await this.waitFor(googlePlacesSession.getAddressDetails({
        address: currentTargetEl.innerText,
        google_place_id: currentTargetEl.dataset.googlePlaceId,
    }));

    // Auto-fill street + number
    if (address.formatted_street_number) {
        this.streetAndNumberInput.value = address.formatted_street_number;
    }
    // Auto-fill text fields (clear if no value)
    this.zipInput.value  = address.zip  || "";
    this.cityInput.value = address.city  || "";

    // Auto-fill country (select by Odoo ID)
    if (address.country) {
        this.countrySelect.value = address.country[0];  // [id, name]
        this.countrySelect.dispatchEvent(new Event("change", { bubbles: true }));
    }
    // Auto-fill state (MutationObserver waits for options to load)
    if (address.state) {
        new MutationObserver((entries, observer) => {
            this.stateSelect.value = address.state[0];
            observer.disconnect();
        }).observe(this.stateSelect, { childList: true });
    }
    dropdownEl.remove();
}
```

**State dropdown race condition:** Odoo's country dropdown triggers a re-fetch of states when its value changes asynchronously. The `MutationObserver` watches `stateSelect.childList` (option elements being added/removed). It fires once when the state options are available, sets the correct state value, then immediately disconnects.

**`address.country[0]` and `address.state[0]`:** The backend returns `[id, name]` tuples (standard Odoo name_get format). The frontend uses only the ID for `<select>` value binding.

---

## Backend: `google_address_autocomplete` Core Logic

### `FIELDS_MAPPING` — Google Types → Odoo Fields

**File:** `google_address_autocomplete/controllers/google_address_autocomplete.py`

```python
FIELDS_MAPPING = {
    'country':                     ['country'],       # ISO country code → res.country.id
    'street_number':               ['number'],         # House number
    'locality':                    ['city'],           # Primary city (e.g., US)
    'postal_town':                ['city'],           # UK / some European countries
    'route':                       ['street'],         # Street name (without number)
    'sublocality_level_1':        ['street2'],        # Sub-locality
    'postal_code':                 ['zip'],           # Postal code
    'administrative_area_level_1': ['state', 'city'], # US states, CA provinces
    'administrative_area_level_2': ['state', 'city'], # US counties
}
FIELDS_PRIORITY = [
    'country', 'street_number', 'locality', 'postal_town',
    'route', 'postal_code', 'administrative_area_level_1',
    'administrative_area_level_2'
]
```

**Priority system:** Google returns address components unordered. Odoo sorts them by `FIELDS_PRIORITY` index before processing. The first value in each mapping list wins — subsequent mappings for the same target are skipped if already assigned. `locality` ranks higher than `postal_town` ranks higher than `administrative_area_level_2`.

### `_translate_google_to_standard()`

```python
def _translate_google_to_standard(self, google_fields):
    standard_data = {}
    for google_field in google_fields:
        fields_standard = FIELDS_MAPPING.get(google_field['type'], [])
        for field_standard in fields_standard:
            if field_standard in standard_data:
                continue
            if field_standard == 'country':
                country = request.env['res.country'].search([
                    ('code', '=', google_field['short_name'].upper())
                ], limit=1)
                standard_data[field_standard] = [country.id, country.name]
            elif field_standard == 'state':
                if 'country' not in standard_data:
                    # Cannot assign state before country — skip
                    continue
                state = request.env['res.country.state'].search([
                    ('code', '=', google_field['short_name'].upper()),
                    ('country_id', '=', standard_data['country'][0])
                ])
                if len(state) == 1:
                    standard_data[field_standard] = [state.id, state.name]
            else:
                standard_data[field_standard] = google_field['long_name']
    return standard_data
```

**Critical ordering:** State cannot be assigned before country — the code explicitly skips if country is not yet in `standard_data`. This protects the state lookup from matching codes that are not unique globally (e.g., "AL" = Alabama in the US, but also used elsewhere).

### `_perform_place_search()` — Suggestion Endpoint

```
Request:  POST /autocomplete/address
          {partial_address: "123 Main", session_id: "uuid", use_employees_key: False}

Google Places Autocomplete API → GET /maps/api/place/autocomplete/json
  ?key=<api_key>
  &fields=formatted_address,name
  &inputtype=textquery
  &types=address
  &input=123+Main
  &sessiontoken=<uuid>

Response: [{formatted_address, google_place_id}, ...]
```

- `types=address` — filters to street addresses only
- `fields=formatted_address,name` — minimizes response payload
- `sessiontoken` — Google session token for billing
- Minimum input check: `google_address_autocomplete.minimal_partial_address_size` (default: `5`) — backend also enforces this
- `TIMEOUT = 2.5` seconds — on timeout, returns `{'results': []}`

### `_perform_complete_place_search()` — Detail Endpoint

```
Request:  POST /autocomplete/address_full
          {address: "123 Main St...", google_place_id: "ChIJ...", session_id: "uuid"}

Google Places Details API → GET /maps/api/place/details/json
  ?key=<api_key>
  &place_id=ChIJ...
  &fields=address_component,adr_address
  &sessiontoken=<uuid>
```

Steps:
1. Fetch `address_components` and `adr_address` from Google
2. Strip `types` array from each component, extract first mapped type
3. Sort by `FIELDS_PRIORITY`
4. Translate via `_translate_google_to_standard()`
5. Handle house number: if Google has it, prefer longer of HTML vs. manual format; if not, use `_guess_number_from_input()`

```python
def _guess_number_from_input(self, source_input, standard_address):
    guessed_house_number = source_input \
        .replace(standard_address.get('zip', ''), '') \
        .replace(standard_address.get('street', ''), '') \
        .replace(standard_address.get('city', ''), '')
    guessed_house_number = guessed_house_number.split(',')[0].strip()
    return guessed_house_number
```

---

## `AutocompleteDropDown` QWeb Template

**File:** `static/src/xml/autocomplete.xml`

```xml
<t t-name="website_sale_autocomplete.AutocompleteDropDown">
    <div t-attf-class="dropdown-menu position-relative #{results.length ? 'show' : ''}">
        <a class="dropdown-item js_autocomplete_result"
           t-foreach="results" t-as="result" t-key="result_index"
           t-att-data-google-place-id="result['google_place_id']">
            <t t-out="result['formatted_address']"/>
        </a>
        <img class="ms-auto pe-1"
             src="/google_address_autocomplete/static/src/img/powered_by_google_on_white.png"
             alt="Powered by Google"/>
    </div>
</t>
```

| Attribute                    | Value                                                                                      |
|------------------------------|--------------------------------------------------------------------------------------------|
| `dropdown-menu` + `show`     | Conditional Bootstrap class — dropdown hidden when no results                                |
| `position-relative`          | Positions dropdown relative to input's parent (requires Bootstrap `position: relative`)  |
| `js_autocomplete_result`      | CSS class used as `t-on-click` event target in `dynamicContent`                            |
| `data-google-place-id`        | Data attribute set from `result['google_place_id']` — read on click via `dataset` API      |
| `t-out` (not `t-esc`)        | Raw string output of formatted address                                                       |
| "Powered by Google" image     | Required by Google ToS; served from `google_address_autocomplete` static files              |

---

## Session Token and API Billing

**Session token lifecycle:**

```
generateUUID()  →  "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
                    (called once on first getAddressPropositions)

getAddressPropositions()  →  session_id = current UUID
                               POST /autocomplete/address
                                 ?sessiontoken=<uuid>

getAddressPropositions()  →  session_id = same UUID  (2nd query)
                               POST /autocomplete/address
                                 ?sessiontoken=<uuid>

getAddressDetails()  →  session_id = same UUID  (Place Details)
                               POST /autocomplete/address_full
                                 ?sessiontoken=<uuid>
                               current = null  ← session token consumed
```

**Google billing:** Google charges per session (not per keystroke) when session tokens are used. A session = all Autocomplete queries + one Details query within one UUID. `KeepLast` frontend deduplication further reduces billable sessions by cancelling in-flight requests.

---

## Tour Test

**File:** `static/tests/autocomplete_tour.js` (loaded via `web.assets_tests`)

```javascript
registry.category("web_tour.tours").add('autocomplete_tour', {
    url: '/shop',
    steps: () => [
        ...tourUtils.addToCart({ productName: "A test product", expectUnloadPage: true }),
        tourUtils.goToCart(),
        tourUtils.goToCheckout(),
        { trigger: 'input[name="street"]', run: "edit This is a test" },
        { trigger: '.js_autocomplete_result' },
        { trigger: 'input[name="street"]', run: "fill add more" },
        { trigger: ".dropdown-menu .js_autocomplete_result:first:contains(result 0)", run: "click" },
        { trigger: "input[name=street]:value(/^42 A fictional Street$/)" },
        { trigger: 'input[name="city"]:value(/^A Fictional City$/)' },
        { trigger: 'input[name="zip"]:value(/^12345$/)' },
    ]
});
```

**File:** `tests/test_ui.py` — sets up the mock:

```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.product = cls.env['product.product'].create({
        'name': 'A test product',
        'website_published': True,
        'list_price': 1
    })

def test_autocomplete(self):
    with patch.object(AutoCompleteController, '_perform_complete_place_search',
                      lambda *a, **kw: {
                          'country': [self.env['res.country'].search([('code', '=', 'USA')]).id, 'United States'],
                          'state': [self.env['res.country.state'].search([('country_id.code', '=', 'USA')])[0].id, 'Alabama'],
                          'zip': '12345',
                          'city': 'A Fictional City',
                          'street': 'A fictional Street',
                          'number': 42,
                          'formatted_street_number': '42 A fictional Street'
                      }), \
            patch.object(AutoCompleteController, '_perform_place_search',
                        lambda *a, **kw: {
                            'results': [{'formatted_address': f'Result {x}', 'google_place_id': MOCK_GOOGLE_ID} for x in range(5)]
                        }):
        self.env['website'].get_current_website().google_places_api_key = MOCK_API_KEY
        self.start_tour('/shop/address', 'autocomplete_tour')
```

---

## Performance Considerations

| Concern                       | Detail                                                                       |
|-------------------------------|-------------------------------------------------------------------------------|
| Frontend event cost           | Zero until `data-autocomplete-enabled='1'` is on the DOM; Interaction dormant until selector matches |
| Debounce                      | 200ms debounce on `input` event prevents per-keystroke API calls             |
| `KeepLast` deduplication      | Cancels in-flight `getAddressPropositions` promise callbacks                   |
| Dropdown DOM                  | Old dropdown removed before new one rendered; always single dropdown in DOM     |
| Backend timeout               | 2.5s hard timeout on all Google API calls; on timeout, returns `{'results': []}` |
| State dropdown refresh        | `MutationObserver` disconnects immediately after state is set                  |
| No database writes             | Autocomplete reads only `res.country` and `res.country.state` for lookups     |

---

## Edge Cases and Failure Modes

| Failure Mode                                | Behavior                                                                                              |
|--------------------------------------------|-------------------------------------------------------------------------------------------------------|
| No API key configured                      | `has_google_places_api_key()` returns `False`; `data-autocomplete-enabled='0'`; checkout works normally |
| API key invalid or quota exceeded          | Google returns `error_message`; logged server-side; silently returns `{'results': []}` to frontend    |
| Google API timeout (2.5s)                 | `requests.get()` raises `TimeoutError`; caught and logged; returns `{'results': []}`                    |
| Address not in Google database             | `_guess_number_from_input()` extracts house number from raw input; address reconstructed manually      |
| Country not in Odoo's `res.country`        | `short_name` → no match; country dropdown not auto-filled; state skipped (protected by country check) |
| State not in Odoo for matched country      | State code → no match; state dropdown not auto-filled                                                   |
| User clears input below 5 chars            | No API call; old dropdown removed                                                                     |
| Race: user clicks while request in flight  | `KeepLast` cancels pending `getAddressPropositions` before starting `getAddressDetails`                  |
| Race: country changes, result selected, states not yet loaded | `MutationObserver` waits for `childList` on `stateSelect` before setting value                         |
| Abbreviated street from Google             | Compares HTML-extracted vs. manual format; uses longer (more complete) string                         |
| Multiple city-like types from Google        | `FIELDS_PRIORITY` sorts `locality` > `postal_town` > `administrative_area_level_2`; first wins        |

---

## Configuration

1. **Google Cloud Console setup:**
   - Create a project at `console.cloud.google.com`
   - Enable **Places API** and **Maps JavaScript API**
   - Create credentials (API key)
   - (Recommended) Set HTTP referrer restrictions to the Odoo instance domain
   - Enable billing (required for Places API to work, even on free tier)

2. **Odoo configuration:**
   - Go to **Website > Configuration > Settings** for the target website
   - Locate the **Google Places API Key** field inside the autocomplete section
   - Paste the API key
   - Click **Save**

3. **Verification:**
   - Go to `/shop/address` (checkout address step)
   - Type 5+ characters of a known street address
   - The Google-powered dropdown should appear
   - Clicking a suggestion should auto-fill all address fields

---

## Cross-Module Integration

| Module                        | Integration Point                                               | Direction    |
|-------------------------------|----------------------------------------------------------------|--------------|
| `website_sale`                | `website_sale.address_form_fields` QWeb template               | Inherits template |
| `website_sale`                | `.oe_cart .address_autoformat` selector (checkout DOM structure) | Reads DOM     |
| `google_address_autocomplete`  | `AutoCompleteController` (routes `/autocomplete/address*`)   | Inherits controller |
| `google_address_autocomplete`  | `googlePlacesSession` JS singleton (RPC client)                | Imports and calls |
| `google_address_autocomplete`  | `powered_by_google_on_white.png` static asset                  | References image |
| `google_address_autocomplete`  | `google_places_api_key` from `ir.config_parameter` as fallback | Fallback in `super()._get_api_key()` |
| `res.country`                 | Looked up by ISO code during address detail translation         | Read-only search |
| `res.country.state`           | Looked up by state code scoped to country                      | Read-only search |
| `base`                        | `base.group_system` used for field-level ACL on API key       | ACL reference |

---

## Related

- [Modules/website_sale](odoo-18/Modules/website_sale.md) — E-commerce checkout and address form
- [Modules/google_address_autocomplete](odoo-19/Modules/google_address_autocomplete.md) — Base Google address autocomplete module (`googlePlacesSession`, `AutoCompleteController`, `FIELDS_MAPPING`, session token handling)
- [Modules/partner_autocomplete](odoo-18/Modules/partner_autocomplete.md) — Partner contact auto-fill using different providers (not Google)
- [Modules/base_geolocalize](odoo-17/Modules/base_geolocalize.md) — Geocoding from partner address
- [Modules/website_sale_delivery](odoo-19/Modules/website_sale_delivery.md) — Delivery method selection (depends on correct country/state being set by autocomplete)
