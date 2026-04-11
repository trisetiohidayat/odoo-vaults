---
type: module
module: crm_iap_mine
tags: [odoo, odoo19, crm, iap, lead_mining, lead_generation]
created: 2026-04-06
updated: 2026-04-11
---

# crm_iap_mine — Lead Generation

> Generates CRM leads and opportunities from Dun & Bradstreet (DnB) data via IAP (In-App Purchase), filtered by country, industry, company size, and contact criteria.

```yaml
category: Sales/CRM
version: 1.2
auto_install: True     # auto-installs when iap_crm is present
depends: iap_crm, iap_mail
license: LGPL-3
author: Odoo S.A.
path: odoo/addons/crm_iap_mine/
```

---

## Module Architecture

```
crm_iap_mine/
├── models/
│   ├── crm_lead.py                     # extends crm.lead
│   ├── crm_iap_lead_mining_request.py  # core request model
│   ├── crm_iap_lead_industry.py        # DnB industry taxonomy
│   ├── crm_iap_lead_role.py            # contact role lookup
│   ├── crm_iap_lead_seniority.py       # seniority lookup
│   └── crm_iap_lead_helpers.py         # stateless utility (zero ACL)
├── security/ir.model.access.csv
├── data/
│   ├── crm.iap.lead.industry.csv       # 22 DnB industry records
│   ├── crm.iap.lead.role.csv           # 22 contact roles
│   ├── crm.iap.lead.seniority.csv      # 3 seniority levels
│   ├── mail_template_data.xml          # low-credit notification email
│   └── ir_sequence_data.xml            # LMR/NNN sequence
└── static/src/js/tours/crm_iap_lead.js # onboarding tour step injection
```

### Dependency Chain

```
crm_iap_mine
  └── iap_crm       adds reveal_id, reveal_rule_id on crm.lead
       └── iap       base IAP account + credit system
  └── iap_mail      enrich_company QWeb template (overridden here)
```

The `reveal_id` field (D-U-N-S number or Clearbit ID) on `crm.lead` — defined in `iap_crm` — is the **deduplication key**. Every existing `reveal_id` in the database is passed to the IAP endpoint on each new request so DnB skips already-enriched companies.

---

## crm.lead Extension

**File:** `models/crm_lead.py`

```python
class CrmLead(models.Model):
    _inherit = 'crm.lead'

    lead_mining_request_id = fields.Many2one(
        'crm.iap.lead.mining.request',
        string='Lead Mining Request',
        index='btree_not_null'
    )
```

### Fields

| Field | Type | Index | Purpose |
|---|---|---|---|
| `lead_mining_request_id` | Many2one → `crm.iap.lead.mining.request` | `btree_not_null` | Back-link to the originating mining request. Null for manually created leads. |

### `_merge_get_fields()`

```python
def _merge_get_fields(self):
    return super()._merge_get_fields() + ['lead_mining_request_id']
```

**L3 detail:** When the lead merge wizard (`crm.lead`'s `_merge_get_fields`) combines two leads from the same mining request, `lead_mining_request_id` is listed as a "preserved" field — the merged record retains the link to the originating request. This allows reporting on merged lead provenance.

### `action_generate_leads()`

```python
def action_generate_leads(self):
    return {
        "name": _("Need help reaching your target?"),
        "type": "ir.actions.act_window",
        "res_model": "crm.iap.lead.mining.request",
        "target": "new",
        "views": `False, "form"`,
        "context": {"is_modal": True},
    }
```

Patched into the header of all four `crm.lead` list/kanban views (`crm_case_tree_view_oppor`, `crm_case_tree_view_leads`, `view_crm_lead_kanban`, `crm_case_kanban_view_leads`). `is_modal: True` in the context signals the request form to show a simplified footer with "Generate Leads" and "Cancel" buttons instead of the full header/status bar.

---

## `crm.iap.lead.mining.request` — Core Model

**File:** `models/crm_iap_lead_mining_request.py`

A single record = one lead generation campaign. All fields are user-configured except computed/readonly ones.

### Constants

```python
DEFAULT_ENDPOINT = 'https://iap-services.odoo.com'
MAX_LEAD = 200          # hard cap enforced in _onchange_lead_number
MAX_CONTACT = 5        # hard cap enforced in _onchange_contact_number
CREDIT_PER_COMPANY = 1  # 1 IAP credit per company
CREDIT_PER_CONTACT = 1  # 1 IAP credit per contact per company
```

At maximum settings: 200 companies × (1 + 5) = **1,200 credits** per request.

### Field Summary — Identity & State

| Field | Type | Default | Purpose |
|---|---|---|---|
| `name` | Char (readonly after submit) | `New` | Assigned from sequence `crm.iap.lead.mining.request` (prefix `LMR`, padding 3). Cleared back to `New` on `action_draft()`. |
| `state` | Selection | `draft` | `draft` → `done` or `error`. Controls all `readonly` attributes in the form view. |
| `error_type` | Selection (readonly) | — | Sub-error when `state='error'`: `credits` (IAP insufficient balance) or `no_result` (valid query, no matches). |

### Field Summary — Volume & Target

| Field | Type | Default | Notes |
|---|---|---|---|
| `lead_number` | Integer | `3` | Clamped 1–200 by `_onchange_lead_number`. |
| `search_type` | Selection | `companies` | `companies` (company data only); `people` (companies + contact enrichment). Controls whether contact filter fields are visible. |

### Field Summary — Lead/Opportunity Assignment

| Field | Type | Default | Notes |
|---|---|---|---|
| `lead_type` | Selection | `_default_lead_type` | Respects `crm.group_use_lead`: if user prefers leads, defaults to `lead`, else `opportunity`. |
| `team_id` | Many2one `crm.team` | computed | Auto-assigned via `_compute_team_id`. Domain: `use_opportunities=True` (or `use_leads=True` if `lead_type='lead'`). |
| `user_id` | Many2one `res.users` | current user | Salesperson assigned to all generated leads. |
| `tag_ids` | Many2many `crm.tag` | `[]` | Tags applied to every generated lead via `[(6, 0, tag_ids)]`. |
| `lead_ids` | One2many `crm.lead` | — | Back-link: `crm.lead.lead_mining_request_id = self.id`. |
| `lead_count` | Integer (computed) | — | Uses `_read_group` aggregation for efficiency: `[('lead_mining_request_id', 'in', self.ids)]` grouped by request. |

### Field Summary — Company Filters

| Field | Type | Default | Notes |
|---|---|---|---|
| `filter_on_size` | Boolean | `False` | Toggles `company_size_min/max` visibility and includes them in IAP payload. |
| `company_size_min` | Integer | `1` | Clamped: must be ≥1 and ≤ `company_size_max`. |
| `company_size_max` | Integer | `1000` | Clamped: must be ≥ `company_size_min`. |
| `country_ids` | Many2many `res.country` | user's company country | Required. Changing this resets `state_ids` to `[]`. |
| `state_ids` | Many2many `res.country.state` | `[]` | Optional sub-country filter. Domain-restricted to `available_state_ids` (whitelist). |
| `available_state_ids` | One2many (computed) | — | Not stored. Used for domain on `state_ids` and onchange sanitisation. |
| `industry_ids` | Many2many `crm.iap.lead.industry` | `[]` | Required. Maps to DnB codes via `reveal_ids`. |

### Field Summary — Contact Filters (search_type='people')

| Field | Type | Default | Notes |
|---|---|---|---|
| `contact_number` | Integer | `10` | Max contacts per company. Clamped 1–5. |
| `contact_filter_type` | Selection | `role` | `role` (preferred/other job titles) or `seniority` (C-suite/VP/manager). |
| `preferred_role_id` | Many2one `crm.iap.lead.role` | — | Primary role sent as `preferred_role` in payload. Required when `contact_filter_type='role'`. |
| `role_ids` | Many2many `crm.iap.lead.role` | — | Additional acceptable roles sent as `other_roles` list. |
| `seniority_id` | Many2one `crm.iap.lead.seniority` | — | Used when `contact_filter_type='seniority'`. Maps to `seniority` in payload. |

### Field Summary — Credit Preview (computed, readonly)

| Field | Type | Computed by | Purpose |
|---|---|---|---|
| `lead_credits` | Char | `_compute_tooltip` | `"N credits will be consumed to find M companies."` |
| `lead_contacts_credits` | Char | `_compute_tooltip` | Full explanation of contact credit cost. |
| `lead_total_credits` | Char | `_compute_tooltip` | Total: `"This makes a total of N credits for this request."` |

`_compute_tooltip` runs as an `@api.onchange` on `lead_number` and `contact_number`, recomputing in real time as the user adjusts sliders/spinners.

---

### State Machine

```
[draft] --action_submit()--> [done]
                           or [error]
                               |-- error_type = 'credits'    (InsufficientCreditError)
                               |-- error_type = 'no_result'  (empty data returned)
[error] --action_draft()---> [draft]   (resets name to "New", clears error_type)
[error] --action_submit()--> [done] or [error]  (retry)
```

**`action_submit()` branching:**

| Context | On Success | On Error |
|---|---|---|
| Modal (`is_modal=True`) | Returns re-open of same record in edit mode | Re-opens same record (error banner visible) |
| Non-modal (direct form) | Navigates to lead/opportunity list | Returns `False` (form reloads with error banner) |

On success, dispatches via `action_get_lead_action()` (for `lead` type) or `action_get_opportunity_action()` with domain `[('id', 'in', self.lead_ids.ids), ('type', '=', 'lead'/'opportunity')]`.

---

### `_prepare_iap_payload()`

Builds the JSON body sent to DnB. Key logic — **industry ID flattening**:

```python
all_industry_ids = [
    reveal_id.strip()
    for reveal_ids in self.mapped('industry_ids.reveal_ids')
    for reveal_id in reveal_ids.split(',')
]
payload['industry_ids'] = all_industry_ids
```

Each `crm.iap.lead.industry` stores comma-separated DnB codes (e.g., `"Consumer Discretionary"` → `"30,155"`). The comprehension flattens to a single flat list: `['30', '155', '33', ...]`. The IAP endpoint receives this list as `industry_ids`.

**State sub-filtering:**

```python
'countries': [{
    'code': country.code,
    'states': self.state_ids.filtered(lambda state: state in country.state_ids).mapped('code'),
} for country in self.country_ids]
```

States are grouped under their parent country. Only states belonging to a selected country appear in the payload.

---

### `_perform_request()` — IAP RPC

```python
def _perform_request(self):
    self.error_type = False
    server_payload = self._prepare_iap_payload()
    reveal_account = self.env['iap.account'].get('reveal')
    dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
    reveal_ids = [
        lead['reveal_id'] for lead in
        self.env['crm.lead'].search_read([('reveal_id', '!=', False)], ['reveal_id'])
    ]
    params = {
        'account_token': reveal_account.sudo().account_token,
        'db_uuid': dbuuid,
        'query': server_payload,
        'db_version': release.version,
        'db_lang': self.env.lang,
        'country_code': self.env.company.country_id.code,
        'reveal_ids': reveal_ids,  # deduplication: skip these IDs
    }
    response = self._iap_contact_mining(params, timeout=300)
```

**Endpoint:** `https://iap-services.odoo.com/api/dnb/1/search_by_criteria`
**Timeout:** 300 seconds

Three failure modes:

| Exception | `error_type` | `state` | Credits consumed? | UI Action |
|---|---|---|---|---|
| `InsufficientCreditError` | `credits` | `error` | No | Show "Buy credits" button |
| No `data` in response | `no_result` | `error` | No | Prompt to broaden filters |
| Other `Exception` | — | stays `draft` | — | Propagates as `UserError` |

---

### `_compute_available_state_ids()` — State Data Quality Caveat

**L4 critical edge case.** This method filters which countries expose a state-level filter to the UI.

```python
countries = lead_mining_request.country_ids.filtered(
    lambda country: country.code in iap_tools._STATES_FILTER_COUNTRIES_WHITELIST
)
```

Many countries have catastrophically poor state-level coverage in the DnB database. Belgium, for example, has state data for only ~11% of companies. If a user adds Belgium + a state filter, ~89% of eligible companies are silently discarded.

The whitelist (keyed by ISO country code, e.g. `US`, `CA`, `AU`, `IN`) is maintained in `iap_tools`. Only countries on this whitelist have their states offered as filtering options.

On every `onchange` of `available_state_ids`, any previously selected state that falls outside the whitelist is pruned:

```python
self.state_ids -= self.state_ids.filtered(
    lambda state: (state._origin.id or state.id) not in self.available_state_ids.ids
)
```

`state._origin.id` handles both new unsaved records and records loaded from DB.

---

### `_compute_team_id()`

```python
team_domain = [('use_leads', '=', True)] if mining.lead_type == 'lead' \
              else [('use_opportunities', '=', True)]
team = self.env['crm.team']._get_default_team_id(user_id=user.id, domain=team_domain)
```

Respects the `use_leads`/`use_opportunities` flags on `crm.team`. If the current `user_id` is already a member of a team matching the lead type, that team is retained — no silent reassignment.

---

## `crm.iap.lead.industry`

**File:** `models/crm_iap_lead_industry.py`

Industry taxonomy mapped to DnB industry classification codes (UNSPSC-based). 22 records pre-loaded.

| Field | Type | Constraints | Purpose |
|---|---|---|---|
| `name` | Char (required, translate) | `unique(name)` | Display name, e.g. `"Consumer Discretionary"`, `"Software & Services"` |
| `reveal_ids` | Char (required) | — | Comma-separated DnB numeric codes, e.g. `"30,155"` |
| `color` | Integer | — | Tag color for `many2many_tags` widget |
| `sequence` | Integer | — | Sort order; also orders `_order = 'sequence, id'` |

The DB-level `unique(name)` constraint prevents duplicate industry names during CSV import.

**Pre-loaded industries (22 total):**

| Industry | DnB codes |
|---|---|
| Consumer Discretionary | `30,155` |
| Consumer Staples | `33` |
| Banks & Insurance | `69,157` |
| Media | `86` |
| Real Estate | `114` |
| Transportation | `136` |
| Energy & Utilities | `138` |
| Materials | `148` |
| Telecommunication Services | `149` |
| Consumer Services | `150,151` |
| Retailing | `152` |
| Food, Beverage & Tobacco | `153,154` |
| Diversified Financials | `158,159` |
| Health Care Equipment & Services | `160` |
| Pharma, Biotech & Life Sciences | `161` |
| Capital Goods | `162` |
| Commercial & Professional Services | `163` |
| Software & Services | `165` |
| Technology Hardware & Equipment | `166` |
| Construction Materials | `167` |
| Independent Power Producers | `168` |
| Automobiles & Components | `238` |
| Consumer Durables & Apparel | `239` |

---

## `crm.iap.lead.role`

**File:** `models/crm_iap_lead_role.py`

Job title/role filter for contact enrichment. 22 roles pre-loaded.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `name` | Char (required, translate) | `unique(name)` | Stored as underscore-case slug: `"information_technology"`, `"human_resources"` |
| `reveal_id` | Char (required) | — | Lowercase DnB role identifier: `"CEO"`, `"finance"`, `"sale"` |
| `color` | Integer | — | Tag color |

```python
def _compute_display_name(self):
    for role in self:
        role.display_name = (role.name or '').replace('_', ' ').title()
```

Transforms `"information_technology"` → `"Information Technology"` for UI display.

**Roles (22):** CEO, Communications, Consulting, Customer Service, Education, Engineering, Finance, Founder, Health Professional, Human Resources, Information Technology, Legal, Marketing, Operations, Owner, President, Product, Public Relations, Real Estate, Recruiting, Research, Sale

---

## `crm.iap.lead.seniority`

**File:** `models/crm_iap_lead_seniority.py`

Contact seniority filter. 3 levels pre-loaded.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `name` | Char (required, translate) | `unique(name)` | Stored as lowercase slug: `"executive"`, `"director"`, `"manager"` |
| `reveal_id` | Char (required) | — | Lowercase DnB seniority identifier |

Same title-case `_compute_display_name()` as `crm.iap.lead.role`.

**Levels (3):** `director`, `executive`, `manager`

---

## `crm.iap.lead.helpers` — Utility Model

**File:** `models/crm_iap_lead_helpers.py`

Stateless model providing shared lead-creation logic. Has **zero ACL** (no group, `perm_read=0`).

### `_notify_no_more_credit()`

```python
def _notify_no_credit(self, service_name, model_name, notification_parameter):
    already_notified = self.env['ir.config_parameter'].sudo().get_param(
        notification_parameter, False
    )
    if already_notified:
        return
    # send email to all record creators...
    self.env['ir.config_parameter'].sudo().set_param(notification_parameter, True)
```

**Spam protection:** Before sending a low-credit notification email, checks a sentinel `ir.config_parameter`. If set, skips. On first trigger, sends the `lead_generation_no_credits` template to all creators of relevant records (using `model_name` to find records) and then sets the sentinel to prevent hourly spam.

### `lead_vals_from_response()`

Maps a raw DnB JSON response dict to `crm.lead` `create()` values.

```python
def lead_vals_from_response(self, lead_type, team_id, tag_ids, user_id,
                            company_data, people_data):
```

| DnB response key | `crm.lead` field | Fallback / Notes |
|---|---|---|
| `duns` | `reveal_id` | Primary ID; `clearbit_id` is fallback |
| `name` / `domain` | `name` | `name` preferred; domain as fallback |
| `name` | `partner_name` | Same source |
| `domain` | `website` | Prepended with `https://` |
| `email[]` (first) | `email_from` | |
| `phone` / `phone_numbers[]` (first) | `phone` | `phone` key preferred |
| `street` / `location` | `street` | `location` is DnB fallback |
| `street2` | `street2` | |
| `city` | `city` | |
| `zip` / `postal_code` | `zip` | `zip` key preferred |
| `country_code` | `country_id` | Resolved via `res.country` search by code |
| `state_code` + `country_id` | `state_id` | Via `_find_state_id()` |

When `people_data` is non-empty (i.e., `search_type='people'`), the first contact's data **overrides** the company email and populates `contact_name` and `function`:

```python
if people_data:
    lead_vals.update({
        'contact_name': people_data[0]['full_name'],
        'email_from': people_data[0]['email'],
        'function': people_data[0]['title'],
    })
```

The full `people_data` list is passed separately to the `iap_mail.enrich_company` template for display in the enriched-company chatter card.

---

## Credit Economics

```
Cost per request (search_type='companies'):
  N credits  (N = lead_number, max 200)

Cost per request (search_type='people'):
  N credits  (companies)  +  (N × K) credits  (contacts)
  = N(1 + K)  where K = contact_number (max 5)

Max credits per request: 200 × (1 + 5) = 1,200 credits
```

Tooltip computation (`_compute_tooltip`):

```python
company_credits = CREDIT_PER_COMPANY * record.lead_number
contact_credits = CREDIT_PER_CONTACT * record.contact_number
total_contact_credits = contact_credits * record.lead_number
# lead_contacts_credits shows: contact_credits * company_credits (not total_contact_credits)
# This is a display of per-company × per-contact to help users understand the math.
```

---

## Security Model

**File:** `security/ir.model.access.csv`

| Model | Group | R | W | C | D |
|---|---|---|---|---|---|
| `model_crm_iap_lead_industry` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |
| `model_crm_iap_lead_role` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |
| `model_crm_iap_lead_seniority` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |
| `model_crm_iap_lead_mining_request` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |
| `model_crm_iap_lead_helpers` | — (no group) | 0 | 0 | 0 | 0 |

Only `group_sale_manager` can create/edit/delete mining requests and taxonomy lookups. Regular salespeople can view existing requests and click "Generate Leads" (the action is allowed; the button is gated by `groups="sales_team.group_sale_manager"` in the view).

The `lead_type` field (lead vs opportunity toggle) is additionally gated by `groups="crm.group_use_lead"` — hidden if the system uses opportunities-only mode.

---

## UI Integration

### Button Injection

"Generate Leads" (`o_button_generate_leads`) is patched into:
- `crm.crm_case_tree_view_oppor` (opportunity list)
- `crm.crm_case_tree_view_leads` (lead list)
- `crm.view_crm_lead_kanban` (opportunity kanban)
- `crm.crm_case_kanban_view_leads` (lead kanban)

Button visibility: always rendered (`display="always"`) but hidden when `active_model != 'crm.lead'` or `crm_lead_view_list_short` context is set (e.g., in a sub-list widget).

### Form View Field Gating

When `state == 'done'`, all input fields are `readonly="state == 'done'"`. The user must `action_draft()` to reset before re-running. This prevents accidental double-submission.

### QWeb Template Override

`crm_iap_mine` extends `iap_mail.enrich_company` via QWeb xpath, adding:
- **VAT number** display
- **Full address** block (street, city, zip, state, country)
- **Website** link
- **Industry tags** (UNSPSC codes as colored badges)
- **Contacts table** (shown only when `people_data` is present): name, email, phone for each contact discovered by DnB.

### Menu Path

```
CRM > Configuration > Lead Generation > Lead Mining Requests
```

### Onboarding Tour

The JS tour patches `crm_tour` (the main CRM onboarding) to insert steps between "Drag to Won" and "Opportunity view", guiding the user to click the Generate Leads button, pick an industry, and submit.

---

## L4 Performance, Edge Cases & Historical Notes

### Odoo 18 → 19 Changes

| Area | Change |
|---|---|
| `MAX_CONTACT` | Reduced to **5** (was higher in earlier versions). Enforced via `_onchange_contact_number`. |
| State filtering | Whitelist mechanism introduced (task-2471703). Countries with <15% state coverage in DnB are excluded from state filtering to prevent 90%+ result loss silently. |
| Version | `1.0` → `1.2` |

### Performance Considerations

- **`reveal_ids` collection:** `_perform_request()` calls `self.env['crm.lead'].search_read([('reveal_id', '!=', False)], ['reveal_id'])` with **no pagination or domain limit**. On databases with millions of leads, this fetches all reveal IDs into memory before every request. O(n) with the full lead table size.
- **Batch lead creation:** `_create_leads_from_response()` uses a single `env['crm.lead'].create(lead_vals_list)` for up to 200 records — efficient. Post-creation message posting iterates per-lead.
- **IAP timeout:** 300-second timeout on `iap_jsonrpc`. Long DnB queries (e.g., broad industry + country + no state) may hit this limit and raise a generic `UserError`.
- **`_compute_lead_count()`:** Uses `_read_group` with `['lead_mining_request_id']` as groupby and `['__count']` — far more efficient than `search_count` per record in a loop.

### Edge Cases

| Scenario | Behaviour |
|---|---|
| Empty IAP response | `error_type='no_result'`, state=`'error'`, no credits consumed, prompt to broaden filters |
| Insufficient IAP credits | `state='error'`, `error_type='credits'`, buy-credits button shown, no leads created |
| Non-whitelisted country + state pre-selected | `_onchange_available_state_ids` prunes invalid states on next form interaction |
| Lead merge | `lead_mining_request_id` preserved in merged record via `_merge_get_fields` extension |
| DnB response has no `name` but has `domain` | Domain becomes the lead `name` |
| `search_type='people'` but `people_data` is empty | Lead created with company-level data only; `contact_name`/`function` not set |
| `is_modal=True` + `state='error'` after submit | Modal re-opens in edit mode so error banner is visible (no navigation) |
| `name == 'New'` on submit | Sequence assigned; if sequence is exhausted/missing, falls back to `New` (translated) |
| Industry with multi-code `reveal_ids` | Each code included separately in payload — broadens search to multiple DnB sectors |

### Security Considerations

- **`crm.iap.lead.helpers` zero ACL:** This model is purely programmatic. Its `@api.model` methods execute with the security context of the calling code.
- **Endpoint override:** `reveal.endpoint` in `ir.config_parameter` allows pointing to a sandbox/test DnB service — useful for development and Odoo internal testing.
- **`account_token` exposure:** The IAP account token is passed to the external DnB endpoint. It is fetched from `iap.account` which stores it encrypted at the DB level.
- **`dbuuid` + `db_version`:** Sent to IAP for service-side logging, abuse detection, and version compatibility checks. Not used for access control.

---

## Cross-Module Integration Map

| Module | Role | Key interaction |
|---|---|---|
| `iap_crm` | Adds `reveal_id` to `crm.lead` | `reveal_id` used as deduplication key and DnB identifier |
| `iap_mail` | `enrich_company` template | `crm_iap_mine` overrides template to add contacts table and full address |
| `iap` | Base IAP account + credit ledger | `iap.account.get('reveal')`, `InsufficientCreditError` |
| `crm` | Base CRM | `crm.lead`, `crm.team`, `crm.tag` |
| `sales_team` | Team model | `group_sale_manager` ACL gate, team assignment |
| `mail` | Chatter + templates | `message_post_with_source()`, mail template send |

---

## Related

- [[Modules/iap_crm]] — Base IAP CRM (reveal_id on crm.lead)
- [[Modules/iap_mail]] — IAP enrichment mail template base
- [[Modules/crm_iap_enrich]] — Separate module for email-domain-based lead enrichment
- [[Modules/crm]] — Base CRM model
