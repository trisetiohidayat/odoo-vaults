---
tags:
  - odoo
  - odoo19
  - crm
  - iap
  - website
  - lead-generation
  - modules
---

# website_crm_iap_reveal

> Automatically generate CRM leads from website visitors by identifying their company via IP address using Odoo IAP (Internet Augmented Processing).

## L1 — How Website Form Submission + IAP + CRM Lead Enrichment Works

### End-to-End Flow

```
[Anonymous Website Visitor]
        │
        ▼  (1) Visits Odoo website page
[ir.http._serve_page()]
        │
        ├─ GeoIP lookup: country_code, state_code
        ├─ Read cookie: rule_ids (session exclusions)
        ├─ _create_reveal_view() ──► INSERT crm_reveal_view
        │       (raw SQL, ON CONFLICT DO NOTHING)
        └─ Write cookie: rule_ids (updated)
        │
        ▼  (2) Daily cron triggers
[_process_lead_generation()]
        │
        ├─ _clean_reveal_views()       ──► DELETE old not_found records
        ├─ _unlink_unrelevant_reveal_view() ──► DELETE views whose IP already generated a lead < 6 months ago
        ├─ _get_reveal_views_to_process() ──► SELECT + GROUP BY IP (raw SQL, LIMIT 25)
        ├─ _prepare_iap_payload()      ──► Build {ips, rules} dict
        ├─ _iap_contact_reveal()       ──► JSON-RPC to /iap/clearbit/1/reveal
        │
        ▼  (3) IAP responds
[_perform_reveal_service()]
        │
        ├─ for each result:
        │   ├─ _create_lead_from_response() ──► create crm.lead
        │   └─ unlink crm_reveal_view
        └─ credit_error check → _notify_no_more_credit() if exhausted
```

### Role of Each Module

| Module | Role |
|--------|------|
| `website_crm` | Provides website contact form; `website_form.py` attaches IP to form submissions |
| `iap_crm` | Provides `iap.account` with `'reveal'` service for credit billing |
| `iap_mail` | Provides `iap_mail.enrich_company` template for posting enrichment data |
| `crm_iap_mine` | Provides `crm.iap.lead.helpers.lead_vals_from_response()` to map IAP data to lead fields |
| `website_crm_iap_reveal` | Orchestrates the pipeline: capture → store → process → create |

---

## L2 — Field Types, Defaults, Constraints

### `crm.reveal.rule` Field Inventory

| Field | Type | Default | Constraint | Notes |
|-------|------|---------|-----------|-------|
| `name` | Char | — | `required=True` | Human-readable rule name |
| `active` | Boolean | `True` | — | Clears `_get_active_rules()` cache on write |
| `country_ids` | Many2many `res.country` | empty | — | Empty = all countries. Clears cache on write |
| `website_id` | Many2one `website` | `False` | — | `False` = all websites |
| `state_ids` | Many2many `res.country.state` | empty | — | Restricts within selected countries |
| `regex_url` | Char | empty | `@api.constrains` → valid Python regex | Empty = all pages. Clears cache on write |
| `sequence` | Integer | — | — | Lower = processed first |
| `industry_tag_ids` | Many2many `crm.iap.lead.industry` | empty | — | Empty = no industry filter |
| `filter_on_size` | Boolean | `True` | — | Enable employee-count filtering |
| `company_size_min` | Integer | `0` | — | Minimum employee count |
| `company_size_max` | Integer | `1000` | — | Maximum employee count |
| `contact_filter_type` | Selection [`role`, `seniority`] | `role` | `required=True` | Only used when `lead_for='people'` |
| `preferred_role_id` | Many2one `crm.iap.lead.role` | `False` | — | Maps to IAP `preferred_role` field |
| `other_role_ids` | Many2many `crm.iap.lead.role` | empty | — | Maps to IAP `other_roles` list |
| `seniority_id` | Many2one `crm.iap.lead.seniority` | `False` | — | Used when `contact_filter_type='seniority'` |
| `extra_contacts` | Integer | `1` | `CHECK(extra_contacts BETWEEN 1 AND 5)` | DB-level constraint; IAP service also caps at 5 |
| `lead_for` | Selection [`companies`, `people`] | `companies` | `required=True` | `companies` = company only; `people` = company + contacts |
| `lead_type` | Selection [`lead`, `opportunity`] | `opportunity` | `required=True` | CRM type of created record |
| `suffix` | Char | empty | — | Appended to lead name for visual identification |
| `team_id` | Many2one `crm.team` | `False` | — | Assigned sales team |
| `tag_ids` | Many2many `crm.tag` | empty | — | CRM tags applied to created leads |
| `user_id` | Many2one `res.users` | `False` | — | Assigned salesperson |
| `priority` | Selection | `False` | — | Available priorities from `crm_stage.AVAILABLE_PRIORITIES` |
| `lead_ids` | One2many | — | — | Inverse of `crm.lead.reveal_rule_id` |
| `lead_count` | Integer (computed) | — | — | Count of `type='lead'` records |
| `opportunity_count` | Integer (computed) | — | — | Count of `type='opportunity'` records |

### `crm.reveal.view` Field Inventory

| Field | Type | Default | Index | Notes |
|-------|------|---------|-------|-------|
| `reveal_ip` | Char | — | — | Visitor IP address |
| `reveal_rule_id` | Many2one `crm.reveal.rule` | — | `btree_not_null` | Matching rule; NULL allowed |
| `reveal_state` | Selection [`to_process`, `not_found`] | `to_process` | Yes (composite) | Processing state |
| `create_date` | Datetime | — | Yes (composite) | Capture timestamp |

**Indexes:**
```python
_ip_rule_id = models.UniqueIndex("(reveal_rule_id, reveal_ip)")
# PostgreSQL UNIQUE index; ORM create() does NOT enforce it
# Raw SQL INSERT uses ON CONFLICT DO NOTHING

_state_create_date = models.Index("(reveal_state, create_date)")
# Optimizes: WHERE reveal_state='not_found' AND create_date < X weeks ago
```

### `crm.lead` Extension Fields

| Field | Type | Description |
|-------|------|-------------|
| `reveal_ip` | Char | Original visitor IP address |
| `reveal_iap_credits` | Integer | Credits consumed for this lead |
| `reveal_rule_id` | Many2one `crm.reveal.rule`, indexed `btree_not_null` | Rule that generated this lead |

---

## L3 — Cross-Model Architecture, Override Patterns, Workflow, Failure Modes

### Cross-Model Integration

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │               website_crm_iap_reveal                        │
                    │                                                             │
  website_crm       │  website_form.py                                           │
  ──────────────►  │  WebsiteForm._handle_website_form()                        │
  (contact form)   │    └─► sets request.params['reveal_ip']                  │
                    │                                                             │
  iap_crm           │  crm_reveal_rule.py                                       │
  ──────────────►  │  iap.account.get('reveal')  ──► credit balance             │
                    │  _notify_no_more_credit()  ──► sends notification           │
                    │                                                             │
  iap_mail          │  _create_lead_from_response()                              │
  ──────────────►  │    └─► lead.message_post_with_source('iap_mail.enrich_company') │
                    │                                                             │
  crm_iap_mine      │  crm_reveal_rule.py                                       │
  ──────────────►  │    └─► crm.iap.lead.helpers.lead_vals_from_response()       │
                    │           (maps IAP JSON → crm.lead field vals)            │
                    │                                                             │
  ir.http           │  ir_http.py                                                │
  ──────────────►  │  IrHttp._serve_page()  ──► calls _create_reveal_view()     │
                    │                                                             │
  website.visitor   │  ir_http.py                                                │
  ──────────────►  │  visitor_sudo.lead_ids  ──► skip if lead already exists     │
                    └─────────────────────────────────────────────────────────────┘
```

### Override Patterns

**Pattern 1: Website form enrichment** (`controllers/website_form.py`)
```python
# Extends: WebsiteForm from website_crm
class ContactController(WebsiteForm):
    def _handle_website_form(self, model_name, **kwargs):
        if model_name == 'crm.lead':
            # Attach IP so lead creation via contact form is deduplicated
            request.params['reveal_ip'] = request.httprequest.remote_addr
        return super()._handle_website_form(model_name, **kwargs)
```

**Pattern 2: Lead creation enrichment** (`models/crm_reveal_rule.py`)
```python
# _create_lead_from_response calls:
lead_vals = rule._lead_vals_from_response(result)
# Which delegates to:
lead_vals = self.env['crm.iap.lead.helpers'].lead_vals_from_response(
    self.lead_type, self.team_id.id, self.tag_ids.ids,
    self.user_id.id, company_data, people_data
)
```

**Pattern 3: Cache invalidation** (`models/crm_reveal_rule.py`)
```python
# Clear ORM registry cache when rule-matching fields change:
def write(self, vals):
    fields_set = {'country_ids', 'regex_url', 'active'}
    if set(vals.keys()) & fields_set:
        self.env.registry.clear_cache()  # Flushes _get_active_rules ormcache
    return super().write(vals)
```

### Workflow Trigger Summary

| Trigger | What Happens | Async/Sync |
|---------|-------------|-----------|
| Public page load | `crm.reveal.view` INSERT via raw SQL | Sync (HTTP request) |
| Daily cron | Full IAP processing pipeline | Async (cron) |
| Contact form submit | `reveal_ip` attached to lead vals | Sync (form handler) |
| Rule write (country/regex/active) | `ormcache` invalidated | Sync |

### Failure Modes

| Failure | Detection | Handling | Recovery |
|---------|-----------|---------|---------|
| IAP credits exhausted | `credit_error: True` in response | `_notify_no_more_credit()`, break loop | Admin buys credits; cron resumes next day |
| IAP timeout / JSON-RPC error | Exception raised in `_iap_contact_reveal()` | Raises `UserError`, transaction rolled back | Views remain `to_process`; next cron run retries |
| IAP returns `not_found` | `not_found: True` in response | `reveal_state = 'not_found'`; kept for cleanup | Auto-cleaned after `reveal.view_weeks_valid` weeks |
| Partial IAP response (broken/missing IPs) | `done_ips` < `all_ips` | Remaining IPs marked `not_found` | Prevents infinite reprocessing loops |
| GeoIP lookup fails | `request.geoip.country_code` is None | `_serve_page` returns early, no reveal record | Visitor silently skipped |
| No IP address | `request.httprequest.remote_addr` is None | `_serve_page` returns early | Visitor silently skipped |
| Visitor already has a lead | `visitor_sudo.lead_ids` exists | `_serve_page` returns early | No duplicate reveal record |
| Regex invalid | `@api.constrains` raises `ValidationError` | Rule cannot be saved | Admin corrects regex pattern |
| Duplicate INSERT race | Two workers INSERT same (rule, IP) | `ON CONFLICT DO NOTHING` silently ignores | Duplicates collapsed by GROUP BY in processing |
| `extra_contacts` > 5 | DB `CHECK` constraint prevents save | `ValidationError` | Admin reduces value |

---

## L4 — Performance, Version Changes, Security

### Performance Analysis

#### Hot Path: `_serve_page()` Per-Request

The synchronous page-view hook runs on **every public page load**. Key optimizations:

| Technique | Mechanism | Impact |
|----------|-----------|--------|
| Rule matching cache | `@tools.ormcache()` on `_get_active_rules()` | Zero DB queries per request after warm-up |
| Raw SQL INSERT | `INSERT ... ON CONFLICT DO NOTHING` | Single round-trip, no ORM overhead |
| Composite DB index | `_state_create_date` on `(reveal_state, create_date)` | Cleanup query scans only `not_found` rows |
| Session cookie dedup | `rule_ids` cookie prevents re-matching same rule in session | Reduces redundant INSERT attempts |
| Cookie type optional | `cookie_type='optional'` | Page still loads if cookies disabled |

**Cost per page view**: 1 cache hit (in-memory dict lookup) + 1 raw SQL INSERT. No ORM queries, no model loads.

#### Cold Path: Cron Batch Processing

| Optimization | Mechanism | Notes |
|-------------|-----------|-------|
| Batch limit | `LIMIT 25` IPs per cron run | Controls credit consumption per run |
| Raw SQL GROUP BY | `SELECT ... GROUP BY reveal_ip` | Single query for entire batch |
| `ORDER BY r.sequence` | SQL-level ordering | Rules processed in priority order without Python sorting |
| Auto-commit | `self.env.cr.commit()` after each batch | Prevents long-running transactions; partial progress persisted |
| IAP timeout | 300s per batch | Prevents cron hanging on slow IAP |

**Query count per cron run** (25 IPs, 3 rules each = 75 views):
- 1 SELECT: `_get_reveal_views_to_process()`
- 1 SELECT: `_prepare_iap_payload()` → rule browse
- 1 JSON-RPC: IAP service call
- Up to 75 INSERTs/UNLINKs: `_create_lead_from_response()`
- Total: ~3 ORM operations + 1 external RPC

#### Registry Cache Clearing

```python
# Called on create/write/unlink that affect matching fields
self.env.registry.clear_cache()
```

`env.registry.clear_cache()` is the **ORM-level cache flush** — it clears all ormcache-decorated methods globally. This is broader than just invalidating `_get_active_rules()`. In multi-worker deployments, each worker maintains its own Python process with its own memory cache; `clear_cache()` only affects the current worker. Rule changes require all workers to process at least one request before their cache is warm again. Alternative: invalidate only the specific cache key using the ormcache invalidate mechanism directly.

### Version Change: Odoo 18 → 19

| Area | Odoo 18 | Odoo 19 | Impact |
|------|---------|---------|--------|
| Cron execution | `ir.cron` with `method` | Same mechanism | No change |
| ORM cache | `@ormcache()` decorator | Same; `clear_cache()` behavior unchanged | No migration needed |
| JSON-RPC | `iap_tools.iap_jsonrpc()` | Same | No change |
| `reveal_view` cleanup | `weeks_valid` config | Same | No change |
| Lead creation | `message_post_with_source` | Same in Odoo 19 | No change |
| View architecture | `<tree>` | `<list>` | Views updated to use `<list>` |
| Field defaults | `default=1` on selection | Same | No change |

The module has no breaking API changes between Odoo 18 and 19. The codebase is identical. Minor view XML changes (`<tree>` → `<list>`) are cosmetic.

### Security Analysis

#### Access Control (ACL)

| ACL Record | Model | Group | CRUD |
|-----------|-------|-------|------|
| `access_crm_reveal_rule_manager` | `model_crm_reveal_rule` | `sales_team.group_sale_manager` | Create, Read, Write, Unlink |
| `access_crm_reveal_rule_salesman` | `model_crm_reveal_rule` | `sales_team.group_sale_salesman` | Read-only |
| `access_crm_reveal_view_manager` | `model_crm_reveal_view` | `sales_team.group_sale_manager` | Create, Read, Write, Unlink |
| `access_crm_reveal_view_salesman` | `model_crm_reveal_view` | `sales_team.group_sale_salesman` | Read-only |

**Design rationale**: View records are internal processing artifacts. Salespeople should not be able to delete or modify them as this could disrupt the reveal pipeline and waste IAP credits.

#### Record Rules

| Rule | Model | Domain | Groups |
|------|-------|--------|--------|
| `ir_rule_crm_reveal_rule_all` | `crm.reveal.rule` | `[(1, '=', 1)]` (all records) | `sales_team.group_sale_salesman_all_leads` |
| `ir_rule_crm_reveal_rule_salesman` | `crm.reveal.rule` | `['\|', ('user_id', '=', user.id), ('user_id', '=', False)]` | `sales_team.group_sale_salesman` |
| `ir_rule_crm_reveal_view_all` | `crm.reveal.view` | `[(1, '=', 1)]` | `sales_team.group_sale_salesman_all_leads` |
| `ir_rule_crm_reveal_view_salesman` | `crm.reveal.view` | `['\|', ('reveal_rule_id.user_id', '=', user.id), ('reveal_rule_id.user_id', '=', False)]` | `sales_team.group_sale_salesman` |

**Record rule path traversal**: `('reveal_rule_id.user_id', '=', user.id)` traverses the Many2one chain `crm.reveal.view → crm.reveal.rule → res.users`. A salesman can only see views whose associated rule is either unassigned (`user_id = False`) or assigned to themselves. This prevents cross-sales-team reveal snooping.

#### IAP Token Security

```python
account = self.env['iap.account'].get('reveal')
params = {
    'account_token': account.sudo().account_token,
    'data': server_payload
}
result = self._iap_contact_reveal(params, timeout=300)
```

The `account_token` is accessed via `sudo()` and passed in the plaintext IAP request. The token is a per-account credential stored in `iap_account`. The IAP service validates the token server-side. No token is stored in the reveal payload — the token is sent directly to the endpoint.

**Exposure surface**: `account_token` appears in Odoo server logs if `logging.DEBUG` is enabled for `odoo.addons.iap`. In production, ensure log level is `INFO` or higher to avoid credential leakage.

#### IP Address Storage

`crm.reveal.view.reveal_ip` stores visitor IP addresses. This is personal data under GDPR. The module does not implement:
- Consent tracking
- Right to erasure for IP records
- Data retention automation beyond 5-week cleanup

**GDPR compliance burden** is on the operator. The module warns users when `lead_for == 'people'` about GDPR obligations for storing personal contact data.

#### No SQL Injection Risk

All user-supplied data in SQL is passed via parameterized queries:
```python
# _create_reveal_view: %s placeholders + tuple params
self.env.cr.execute(query, params)

# _get_reveal_views_to_process: LIMIT with parameterized int
self.env.cr.execute(query, [batch_limit])
```

The `regex_url` is validated via `re.compile()` in `@api.constrains`, which raises `ValueError` for invalid patterns before any SQL is executed.

---

## Security Model Summary

| Aspect | Design Decision |
|--------|----------------|
| `crm.reveal.rule` write access | Restricted to `group_sale_manager` only |
| `crm.reveal.view` write access | Restricted to `group_sale_manager` only |
| Salesman read on views | Allowed; filtered by rule ownership |
| IAP token exposure | Stored server-side; sent via HTTPS JSON-RPC |
| SQL injection | Mitigated by parameterized queries + regex validation |
| Personal data (IP) | Stored; no GDPR automation; operator responsibility |
| Lead attribution | Preserved through merge via `_merge_get_fields()` |

---

## IAP Credit Management

### Credit Consumption

| Action | Credits Consumed |
|--------|-----------------|
| IP processed (company found or not) | 1 credit |
| Each extra contact (`lead_for='people'`, `extra_contacts>0`) | 1 credit each |

Example: A rule with `lead_for='people'` and `extra_contacts=3` consumes **4 credits per identified company** (1 base + 3 contacts).

### No-Credit Notification Throttling

```python
if result.get('credit_error'):
    self.env['crm.iap.lead.helpers']._notify_no_more_credit(
        'reveal', self._name, 'reveal.already_notified'
    )
    return False
```

The `'reveal.already_notified'` key in `ir.config_parameter` acts as a **one-shot flag**: once set to `True`, `_notify_no_more_credit()` will not send again until the parameter is reset. In `_perform_reveal_service()`, the parameter is reset only when IAP returns a successful non-credit-error response:

```python
self.env['ir.config_parameter'].sudo().set_param('reveal.already_notified', False)
```

This prevents credit-exhausted notifications from spamming admins on every cron run.

---

## Key Odoo IAP Pattern

```
[HTTP Request]  →  lightweight tracker insert (sync, fast, zero latency)
        │
        ▼
[Cron Job]      →  batch collect → IAP JSON-RPC call (async, batched, credit-efficient)
        │
        ▼
[IAP Response]  →  lead create + mail message post (async)
```

**Why batch?** Each IAP call costs credits. Processing 25 IPs in one call is more efficient than 25 individual calls. Auto-commit between batches ensures partial progress is not lost if the cron is interrupted.

---

## File Structure

```
website_crm_iap_reveal/
├── __init__.py
├── __manifest__.py                    # v1.1, LGPL-3, category: Sales/CRM
├── controllers/
│   ├── __init__.py
│   └── website_form.py               # Overrides WebsiteForm._handle_website_form
├── models/
│   ├── __init__.py
│   ├── crm_lead.py                   # crm.lead: reveal_ip, reveal_rule_id, _merge_get_fields
│   ├── crm_reveal_rule.py            # Rule config, IAP payload, cron, lead creation
│   ├── crm_reveal_view.py            # Tracker INSERT (raw SQL), cleanup
│   └── ir_http.py                    # _serve_page hook
├── data/
│   ├── ir_cron_data.xml              # Daily cron: _process_lead_generation()
│   └── ir_model_data.xml             # formbuilder_whitelist for reveal_ip
├── security/
│   ├── ir_rules.xml                   # Record rules for reveal_rule and reveal_view
│   └── ir.model.access.csv           # ACL: manager CRUD, salesman read-only
├── views/
│   ├── crm_lead_views.xml            # Form field groups + pivot/graph fields
│   ├── crm_reveal_views.xml          # Rule form/list/search + view form/list + actions
│   ├── crm_menus.xml                 # Menu items
│   └── res_config_settings_views.xml  # IAP buy credits widget
└── tests/
    ├── common.py                      # MockIAPReveal with IAP simulation
    └── test_lead_reveal.py           # Tests: normal, credit_error, jsonrpc_exception, no_result
```

---

## Menu Structure

| Menu | Parent | Action | Groups |
|------|--------|--------|--------|
| Visits to Leads Rules | CRM > Lead Generation | `crm_reveal_rule_action` | All CRM users |
| Lead Generation Views | CRM > Reporting | `crm_reveal_view_action` | `base.group_no_one` (technical debug only) |

---

## Related Documentation

- [Modules/iap_crm](Modules/iap_crm.md) — IAP account integration and credit management
- [Modules/crm_iap_mine](Modules/crm_iap_mine.md) — Industry/role/seniority master data; `lead_vals_from_response()` helper
- [Modules/iap_mail](Modules/iap_mail.md) — `iap_mail.enrich_company` mail template for posting enrichment data
- [Modules/website_crm](Modules/website_crm.md) — Website contact form; used by the controller override
- [Modules/crm](Modules/CRM.md) — CRM base module
- [Core/API](Core/API.md) — `@api.model`, `@api.constrains`, `@tools.ormcache` usage in this module
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Cron-based batch pipeline pattern
