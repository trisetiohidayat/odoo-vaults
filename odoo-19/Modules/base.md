---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #base
  - #orm
  - #security
---

# Module: base

## Overview

The `base` module is the foundational Odoo module that defines the core models shared across all Odoo applications. It provides the essential infrastructure for partners, users, companies, currencies, countries, languages, sequences, scheduled actions, system parameters, model metadata, actions, menus, filters, and default values. Every other Odoo module depends (directly or transitively) on `base`.

**Source path**: `~/odoo/odoo19-suqma/odoo/odoo/addons/base/`
**Manifest version**: `1.3`
**Category**: `Hidden`
**Auto-install**: `True` (installed automatically whenever any module depends on it)
**Post-init hook**: `post_init`
**License**: `LGPL-3`

**Key data files loaded**:
- `res_lang_data.xml`, `res.lang.csv` — languages and locales
- `res_country_data.xml`, `res.country.state.csv` — countries and states
- `res_partner_data.xml`, `res_partner_demo.xml` — default partners (including `base.partner_root`)
- `res_company_data.xml` — default company (XML-ID: `base.main_company`)
- `res_users_data.xml`, `res_users_demo.xml` — default users (including `base.user_admin`, `base.public_user`)
- `res_currency_data.xml`, `res_currency_demo.xml` — currencies and rates
- `ir_config_parameter_data.xml`, `ir_cron_data.xml` — system parameters and scheduled actions
- `base_groups.xml`, `base_security.xml`, `ir.model.access.csv` — security (groups, rules, ACLs)
- `base_menus.xml` — root application menus

**Key architectural patterns:**
- `commercial_partner_id` / `_commercial_fields()` for propagating fields through partner hierarchy
- `_inherits` delegation for `res.users` -> `res.partner` (partner stored as `partner_id`)
- `@ormcache` for performance-critical lookups (`cache='stable'`, `cache='groups'`)
- `completion_status` pattern for cron job batch processing with crash recovery
- Record rules via `_check_company_domain` on multi-company models
- `ir.model` / `ir.model.fields` for custom field/model management at runtime
- `SQL.identifier` for all raw SQL to prevent injection
- `CryptContext` wrapper over `passlib.context` for password hashing

---

## 1. res.partner

**Model**: `res.partner`
**Table**: `res_partner`
**Inherits**: `format.address.mixin`, `format.vat.label.mixin`, `avatar.mixin`, `properties.base.definition.mixin`
**Delegates**: `_inherits = {'res.partner': 'partner_id'}` in `res.users`
**Order**: `complete_name ASC, id DESC`
**Check company**: `_check_company_auto = True`, `_check_company_domain = models.check_company_domain_parent_of`
**Rec names search**: `['complete_name', 'email', 'ref', 'vat', 'company_registry']`
**Allow sudo commands**: `False`

### L2 Fields

| Field | Type | Default | Required | Index | Help |
|-------|------|---------|----------|-------|------|
| `name` | Char | - | Conditional | Yes | Contact name; required when `type='contact'` |
| `complete_name` | Char | computed/store | - | Yes | Full hierarchical name |
| `parent_id` | Many2one res.partner | - | - | Yes | Related company (for contact sub-types) |
| `child_ids` | One2many res.partner | - | - | - | Contacts belonging to this company |
| `ref` | Char | - | - | Yes | Internal reference |
| `lang` | Selection | computed | - | - | Language for emails/documents |
| `active_lang_count` | Integer | computed | - | - | Number of installed languages |
| `tz` | Selection | context `tz` | - | - | Timezone |
| `tz_offset` | Char | computed | - | - | Timezone offset string |
| `user_id` | Many2one res.users | - | - | - | Salesperson in charge |
| `vat` | Char | - | - | Yes | Tax Identification Number |
| `same_vat_partner_id` | Many2one res.partner | computed | - | - | Partner sharing same VAT |
| `same_company_registry_partner_id` | Many2one res.partner | computed | - | - | Partner sharing same registry |
| `company_registry` | Char | computed/store | - | `btree_not_null` | Company registry number |
| `company_registry_label` | Char | computed | - | - | Country-specific label for registry |
| `company_registry_placeholder` | Char | computed | - | - | Placeholder text |
| `bank_ids` | One2many res.partner.bank | - | - | - | Bank accounts |
| `website` | Char | - | - | - | Website link |
| `comment` | Html | - | - | - | Internal notes |
| `category_id` | Many2many res.partner.category | - | - | - | Tags |
| `active` | Boolean | `True` | - | - | Record visibility |
| `employee` | Boolean | - | - | - | Employee flag |
| `function` | Char | - | - | - | Job position |
| `type` | Selection | `contact` | - | - | Address type: contact/invoice/delivery/other |
| `type_address_label` | Char | computed | - | - | Localized address type label |
| `street` | Char | - | - | - | Street address |
| `street2` | Char | - | - | - | Street address line 2 |
| `zip` | Char | - | - | - | Postal code |
| `city` | Char | - | - | - | City |
| `state_id` | Many2one res.country.state | - | - | - | State/province |
| `country_id` | Many2one res.country | - | - | - | Country |
| `country_code` | Char | related | - | - | ISO 3166-1 alpha-2 code |
| `partner_latitude` | Float | - | - | - | Geo latitude (10,7) |
| `partner_longitude` | Float | - | - | - | Geo longitude (10,7) |
| `email` | Char | - | - | - | Email address |
| `email_formatted` | Char | computed | - | - | "Name <email@domain>" format |
| `phone` | Char | - | - | - | Phone number |
| `is_company` | Boolean | `False` | - | - | Company flag |
| `is_public` | Boolean | computed/sudo | - | - | Public user (odoobot) |
| `industry_id` | Many2one res.partner.industry | - | - | - | Industry classification |
| `company_type` | Selection | computed | - | - | person/company (interface only) |
| `company_id` | Many2one res.company | - | - | Yes | Owning company (multi-company) |
| `color` | Integer | `0` | - | - | Color index for kanban |
| `user_ids` | One2many res.users | - | - | - | Users linked to this partner |
| `main_user_id` | Many2one res.users | computed | - | - | Most appropriate user when single needed |
| `partner_share` | Boolean | computed/store | - | - | Customer without internal access |
| `contact_address` | Char | computed | - | - | Full formatted address |
| `commercial_partner_id` | Many2one res.partner | computed/store | - | Yes | Topmost commercial entity |
| `commercial_company_name` | Char | computed/store | - | - | Company name from commercial entity |
| `company_name` | Char | - | - | - | Company name for new child |
| `barcode` | Char | - | - | company_dependent | Barcode identifier |
| `self` | Many2one res.partner | computed | - | - | Self-reference for QWeb |
| `application_statistics` | Json | computed | - | - | Stats for apps |

**Constraint**: `CHECK((type='contact' AND name IS NOT NULL) OR (type!='contact'))` - "Contacts require a name"

### L3 Key Methods

**Commercial fields** (`_commercial_fields()`, `_synced_commercial_fields()`, `_company_dependent_commercial_fields()`):
- `_commercial_fields()` returns `['vat']` (synced) + `['company_registry', 'industry_id']` (non-synced) — extended by overrides
- `_company_dependent_commercial_fields()` returns commercial fields marked `company_dependent=True`
- `_commercial_sync_from_company()` syncs from parent commercial entity on `parent_id` change
- `_commercial_sync_to_descendants()` propagates commercial values down the partner tree recursively
- `_company_dependent_commercial_sync()` writes across all companies via `with_company()`

**Address sync** (`_fields_sync()`, `_children_sync()`, `_update_address()`):
- `ADDRESS_FIELDS = ('street', 'street2', 'zip', 'city', 'state_id', 'country_id')`
- `_fields_sync(values)` is called after every `write()` and `create()` — three phases: upstream sync, downstream sync, children sync
- Phase 1 (upstream): copies address from parent to contact when `type='contact'`; copies commercial fields (`vat`) from contact back up to parent
- Phase 2 (downstream): syncs address and commercial fields from company down to children
- `_handle_first_contact_creation()`: if first contact has address but company does not, copies contact address to company
- Context `_partners_skip_fields_sync` suppresses all sync during batch/noupdate loading
- `_get_address_values()` returns empty dict if no address field is set — avoids unnecessary writes

**Parent/child hierarchy** (`address_get()`):
- DFS traversal through descendants stopping at `is_company=True` nodes
- After exhausting descendants, climbs up `parent_id` chain
- Returns first match for each requested address type (`contact`, `invoice`, `delivery`, `other`); falls back to `contact` or self
- `_check_parent_id`: raises `ValidationError` on recursive hierarchy via `_has_cycle()`
- `_check_partner_company`: ensures `company_id` on a company-type partner matches `partner_id.company_id`

**VAT handling** (`_compute_same_vat_partner_id()`):
- EU prefix normalization: `GR->EL`, `GB->XI`; country groups with `EU_PREFIX` checked with and without prefix
- Single-char VAT treated as placeholder (skipped)
- Domain includes `country_id` (nullable) and `company_id` (nullable) for isolation

**Avatar** (`_compute_avatar_*()`):
- Internal users and contacts with `type='contact'` use own `image_*` or initials avatar
- External users (portal/share) use placeholder images by type: company=company.png, delivery=truck.png, invoice=bill.png, other=puzzle.png

**`name_create()` / `find_or_create()`**:
- `name_create()` parses email-format input, extracts name and normalized email via `tools.parse_contact_from_email()`
- `find_or_create()` searches by `email =ilike` (case-insensitive) before creating

### L4 Performance and Security

**Performance**:
- `commercial_partner_id` is stored with B-tree index — avoids recursive `parent_id` traversal on every read
- `company_registry` stored with `btree_not_null` index — allows efficient filtering while still supporting NULL
- `complete_name` is stored and invalidated only when name-related fields change
- `address_get()` uses in-memory DFS with a `visited` set to prevent re-scanning subtrees; deep hierarchies (100+ levels) may cause Python recursion stack overflow
- `_load_records_create()` batch-groups partners by `(commercial_partner_id, parent_id)` and issues one bulk `write()` per group instead of N individual writes
- `main_user_id` uses `with_prefetch()` to leverage prefetch cache from `user_ids` — avoids N+1 when rendering kanban views

**Security**:
- `is_company` write requires `base.group_partner_manager` — implemented via `sudo()` bypass in `write()` only when user has the group; raises `AccessError` otherwise
- Archiving a partner with active linked users raises `RedirectWarning` (not plain `ValidationError`) directing to the user form
- `partner_share` = `True` means no internal user (`share=False`) exists on this partner — used for access decisions
- Barcode uniqueness check (`_check_barcode_unicity`) performs `search_count()` across all partners — use the `company_dependent=True` index on `barcode` to limit scan scope in large datasets
- `_unlink_except_user()` checks for linked active users; non-managers get a plain `ValidationError`, managers get a `RedirectWarning`
- `res.partner` has `_allow_sudo_commands = False` — `sudo()` RPC commands cannot create/update/delete partners without access rights

**Odoo 18 → 19 changes**:
- `commercial_partner_id` made stored and indexed (was computed in Odoo 18)
- `company_registry` made stored (was computed in Odoo 18)
- `_load_records_create()` batch optimization added to reduce N+1 during XML data loading
- `_display_address()` refactored into `_prepare_display_address()` + `_display_address()` for extensibility
- `is_public` field added for odoobot detection

---

## 2. res.users

**Model**: `res.users`
**Table**: `res_users`
**Inherits**: `_inherits = {'res.partner': 'partner_id'}` via delegation
**Order**: `name, login`
**Check company**: `_check_company_auto = True`
**Allow sudo commands**: `False`

### L2 Fields

| Field | Type | Default | Required | Index | Help |
|-------|------|---------|----------|-------|------|
| `partner_id` | Many2one res.partner | - | True | Yes | Associated partner record (`ondelete='restrict'`, `bypass_search_access=True`) |
| `login` | Char | - | True | Yes | Login name (globally unique constraint) |
| `password` | Char | computed | - | - | Encrypted password (write-only, never returned) |
| `new_password` | Char | computed | - | - | Set password (triggers `CryptContext` hash) |
| `signature` | Html | computed/store | - | - | Email signature (auto-populated from name) |
| `active` | Boolean | `True` | - | Yes | User active state |
| `active_partner` | Boolean | related | - | - | Partner active (via sudo) |
| `action_id` | Many2one ir.actions.actions | - | - | - | Home action |
| `login_date` | Datetime | - | - | Yes | Last login timestamp (via `log_ids.create_date`) |
| `lang` | Selection | - | - | - | Language preference |
| `tz` | Selection | - | - | - | Timezone |
| `tz_offset` | Char | computed | - | - | Offset string |
| `email` | Char | inherited | - | - | Email (synced from partner) |
| `group_ids` | Many2many res.groups | `_default_groups()` | - | - | Direct group membership |
| `all_group_ids` | Many2many res.groups | computed/store | - | - | All groups (direct + implied via `all_implied_ids`) |
| `share` | Boolean | computed/store | - | - | Portal user (not internal) |
| `access_token` | Char | - | - | - | Token for non-db auth |
| `device_ids` | One2many res.device | - | - | - | Trusted devices (WebAuthn) |
| `api_key_ids` | One2many res.users.apikeys | - | - | - | API keys |
| `role` | Selection | computed | - | - | group_user/group_system (interface) |
| `company_id` | Many2one res.company | `env.company` | - | Yes | Current working company |
| `company_ids` | Many2many res.company | `env.company.ids` | - | - | All companies user belongs to |
| `res_users_settings_ids` | One2many res.users.settings | - | - | - | User settings records |
| `view_group_hierarchy` | Json | `_default_view_group_hierarchy()` | - | - | Group/privilege/category hierarchy for UI |
| `login_attempts` | Integer | - | - | - | Failed login counter (rate limiting) |
| `lock_validity` | Integer | - | - | - | Account lock validity period (seconds) |

**Constraints**:
- `UNIQUE(login)` — enforced at DB level
- `CHECK(company_id IN company_ids)` — enforced by `_check_user_company`

**`SELF_READABLE_FIELDS`** (portal-accessible on own record):
`'signature', 'company_id', 'login', 'email', 'name', 'image_1920', 'image_1024', 'image_512', 'image_256', 'image_128', 'lang', 'tz', 'tz_offset', 'group_ids', 'partner_id', 'write_date', 'action_id', 'avatar_*', 'share', 'device_ids', 'api_key_ids', 'phone', 'display_name'`

**`SELF_WRITEABLE_FIELDS`** (portal-can-write on own record):
`'signature', 'action_id', 'company_id', 'email', 'name', 'image_1920', 'lang', 'tz', 'api_key_ids', 'phone'`

### L3 Key Methods

**`_inherits` delegation chain**:
- `res.users` stores `partner_id` (Many2one, `ondelete='restrict'`) — partner cannot be deleted while user exists
- Delegated fields: `name`, `email`, `phone`, `image_1920` — writes on user delegate to partner automatically
- `partner_id` has `bypass_search_access=True` — searching for users does not check partner ACLs

**Password hashing** (`CryptContext`, `_crypt_context()`, `MIN_ROUNDS=600_000`):
- Uses `passlib` with PBKDF2 (bcrypt by default); rounds tracked in hash prefix (e.g., `$bcrypt...$`)
- `init()` auto-upgrades plain-text passwords found in DB on server startup — queries all rows where password does not match extended MCF pattern `$[^$]+$[^$]+$.`
- `_set_password()` hashes via `CryptContext.hash()`, stores via raw SQL `UPDATE` to avoid ORM overhead
- `_set_encrypted_password()` asserts the value is not plaintext before storing
- `_crypt_context()` is `@ormcache`d (`cache='stable'`) — instance reused across calls

**Credential checking** (`_check_credentials(credential, env)`):
- Supports `password` and `apikey` credential types
- `interactive` key in `env` determines whether WebAuthn/API-key auth is attempted (RPC uses `interactive=False`)
- `_rpc_api_keys_only()` returns `False` by default; overridden by 2FA modules
- On valid password: returns `{'uid', 'auth_method': 'password', 'mfa': 'default'}`
- On valid API key: returns `{'uid', 'auth_method': 'apikey', 'mfa': 'default'}`
- On replacement hash available: calls `_set_encrypted_password()` and clears registry cache + session token
- Rate limiting: `base.login_cooldown_after` (default 10) and `base.login_cooldown_duration` (default 60s) tracked via `login_attempts`

**Session token** (`_compute_session_token(sid)`, `_session_token_hash_compute()`):
- `@tools.ormcache('sid')` — cached per session ID; invalidated when any session-token field changes
- HMAC-SHA256 of session ID using fields `{'id', 'login', 'password', 'active'}` (from `_get_session_token_fields()`)
- `database.secret` from `ir.config_parameter` used as HMAC key base
- `_session_token_get_values()` uses raw SQL via `SQL.identifier` to build column list dynamically — prevents injection
- Override `_get_session_token_query_params()` for additional fields (e.g., `auth_passkey_key_ids` left-join)
- `_legacy_session_token_hash_compute()`: backward-compatible variant without `is not None` guard

**Multi-company** (`_get_company_ids()`, `__accessible_branches()`):
- `_get_company_ids()` cached via `@ormcache('self.id')` — returns IDs of active companies where user is in `user_ids`
- `__accessible_branches()` uses `@ormcache('tuple(self.env.companies.ids)', 'self.id', 'self.env.uid')` — returns all branches of current company accessible to user
- Superuser (id=SUPERUSER_ID) always returns `self.ids` when intersection is empty (cron safety)
- `_all_branches_selected()` checks whether all branches of the root are in `self`

**Identity check** (`@check_identity` decorator, `identitycheck` model):
- 10-minute validity window (not 24h as originally documented in the record — the record stores expiry, the decorator enforces 10mn)
- Creates `res.users.identitycheck` record with JSON-serialized context as request
- Cannot be used outside HTTP request context (`if not request: raise UserError`)
- Session key `identity-check-last` stores Unix timestamp of last successful check

**Group membership** (`has_group()`, `has_groups()`, `_has_group()`, `_get_group_ids()`):
- `@api.readonly` decorator on `has_group()` and `has_groups()` — prevents RPC call from non-owner contexts
- `_get_group_definitions()` cached globally; `_get_group_ids()` cached per user
- `all_group_ids` (stored) = direct groups + all implied groups via `all_implied_ids`; recomputed via `group_ids` trigger
- `has_groups()` accepts comma-separated XML IDs with `!` prefix for negation; checks negatives first for early exit
- `base.group_no_one` only active in debug mode (request session in debug = True)

**User lifecycle** (`create()`, `write()`, `_unlink_except_master_data()`):
- `create()`: auto-creates `res.users.settings` for internal users; generates SVG initials avatar if no image; syncs `partner_id.company_id`
- `write()`: self-editing restricted to `SELF_WRITEABLE_FIELDS`; own company switch restricted to allowed `company_ids`; `SUPERUSER_ID` cannot be activated if deactivated
- `_unlink_except_master_data()`: prevents deleting `base.user_admin`, `base.public_user`, `base.template_portal_user_id`, and `SUPERUSER_ID`
- `_deactivate_portal_user()`: anonymizes login (timestamped placeholder), clears password and API keys, archives, queues for deletion via `res.users.deletion`

### L4 Performance and Security

**Performance**:
- `CryptContext` wrapper instantiated once and cached (`@ormcache`) — avoids repeated passlib initialization overhead
- Session tokens cached per SID — token computation only on first access per server worker
- `_get_company_ids()` cached at user level — called by every request for multi-company record rule evaluation
- `all_group_ids` is stored — `has_group()` lookups are pure cache hits, no computation
- `_default_view_group_hierarchy()` generates Json on each call; not cached at ORM level

**Security**:
- `password` field is `compute`-only (no stored column) — never returned by `read()` unless explicitly accessed in code
- `_check_credentials()` never exposes whether a login exists vs. wrong password (both raise `AccessDenied`)
- `change_password()` requires old password explicitly — prevents session hijacking via remembered sessions
- `_unlink_except_master_data()` runs as `@ondelete(at_uninstall=True)` — enforced even when uninstalling `base`
- `_check_at_least_one_administrator` skipped during module upgrade (`_init_modules` check) to allow removing admin from all groups temporarily
- `_check_disjoint_groups()` uses `_get_user_type_groups()` to detect implied-group conflicts between portal/user/public

**Odoo 18 → 19 changes**:
- `device_ids` (trusted devices for WebAuthn) added
- `identitycheck_validity` added (was fixed 24h in Odoo 18)
- `@api.readonly` added on `has_group()` / `has_groups()` to block non-owner RPC calls
- `_crypt_context()` now uses `MIN_ROUNDS = 600_000` minimum
- `init()` auto-upgrade for plaintext passwords on startup
- `_check_disjoint_groups()` constraint added for implied-group portal/user conflicts
- `role` field added as simplified group_user/group_system interface
- `view_group_hierarchy` Json field added for settings UI

---

## 3. res.company

**Model**: `res.company`
**Table**: `res_company`
**Inherits**: `format.address.mixin`, `format.vat.label.mixin`
**Delegates**: `_inherits = {'res.partner': 'partner_id'}` (company stores its own partner)
**Parent store**: `_parent_store = True`
**Order**: `parent_path, sequence, name, id`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Company name (related to `partner_id.name`, stored) |
| `partner_id` | Many2one res.partner | - | Yes | Associated partner (`index=True`, `ondelete='cascade'` in partner) |
| `parent_id` | Many2one res.company | - | - | Parent company |
| `child_ids` | One2many res.company | - | - | Child companies |
| `all_child_ids` | One2many res.company | - | - | All children including inactive |
| `parent_path` | Char | computed | - | Hierarchical path for ancestry (indexed) |
| `sequence` | Integer | `10` | - | Ordering in company switcher |
| `currency_id` | Many2one res.currency | `_default_currency_id()` | Yes | Default currency |
| `logo` | Binary | `_get_logo()` | - | Company logo (related to `partner_id.image_1920`) |
| `logo_web` | Binary | computed/store | - | 180px-processed logo (not stored in attachments) |
| `uses_default_logo` | Boolean | computed/store | - | True if using Odoo default logo |
| `active` | Boolean | `True` | - | Archive flag |
| `report_header` | Html | - | - | Report tagline |
| `report_footer` | Html | - | - | Report footer |
| `company_details` | Html | - | - | Report header text |
| `is_company_details_empty` | Boolean | computed | - | True if company_details is blank |
| `paperformat_id` | Many2one report.paperformat | `paperformat_euro` | - | Paper format |
| `external_report_layout_id` | Many2one ir.ui.view | - | - | Report layout template |
| `font` | Selection | `Lato` | - | Report font |
| `primary_color` | Char | - | - | Brand primary color |
| `secondary_color` | Char | - | - | Brand secondary color |
| `layout_background` | Selection | `Blank` | - | Report background |
| `layout_background_image` | Binary | - | - | Background image |
| `email` | Char | related/store | - | From partner |
| `phone` | Char | related/store | - | From partner |
| `website` | Char | related/store | - | From partner |
| `vat` | Char | related/store | - | Tax ID from partner |
| `company_registry` | Char | related/store | - | Company registry from partner |
| `bank_ids` | One2many res.partner.bank | related | - | From partner |
| `user_ids` | Many2many res.users | - | - | Users belonging to company |
| `color` | Integer | computed | - | From root company |
| `uninstalled_l10n_module_ids` | Many2many ir.module.module | computed | - | l10n modules ready to install |
| `parent_ids` | Many2many res.company | computed/sudo | - | All ancestors via `parent_path` |
| `root_id` | Many2one res.company | computed/sudo | - | Topmost ancestor |

**Constraints**:
- `UNIQUE(name)` — company name must be globally unique
- `CHECK(active)` — cannot archive if active users exist (via `_check_active`)
- `CHECK` on delegated fields — subsidiary's `currency_id` must equal root's `currency_id` (via `_check_root_delegated_fields`)

### L3 Key Methods

**Delegated fields** (`_get_company_root_delegated_field_names()`):
- Returns `['currency_id']` — all branches must share the root company's currency
- Form view makes these fields `readonly="parent_id != False"` via `_get_view()` override
- `write()` propagates delegated field changes from root down to all branches using `child_of` domain
- Branch currency changes are silently ignored (root value takes precedence)

**Root delegation constraint** (`_check_root_delegated_fields`):
- `@api.constrains` on `[currency_id] + [parent_id]` — triggers when `currency_id` or `parent_id` changes
- Raises `ValidationError` if branch currency differs from root currency

**Address delegation**: `street`, `street2`, `city`, `zip`, `state_id`, `country_id` are `compute`d from `partner_id` with inverse setters that write back to the partner

**Multi-company access** (`__accessible_branches()`):
- `@ormcache('tuple(self.env.companies.ids)', 'self.id', 'self.env.uid')` — key includes all companies in current user's `company_ids` to handle multi-company switch
- Returns branches of `self` that intersect with `self.env.companies` (the user's current allowed companies)
- Superuser fallback: if intersection empty, returns `self.ids` (superuser always has access)
- `_all_branches_selected()`: compares `self` against `search([('id', 'child_of', root_id)])` — used for whole-company actions

**Country-based l10n** (`_compute_uninstalled_l10n_module_ids`):
- Raw SQL finds uninstalled `auto_install` modules whose `country_ids` match this company's `country_id`
- Excludes modules with unmet `auto_install_required` dependencies
- `install_l10n_modules()` deferred until registry is ready (`ready or not initialising`)

**Copy prevention**: `copy()` raises `UserError` — companies cannot be duplicated; must create new

### L4 Performance and Security

**Performance**:
- `parent_ids` and `root_id` computed via string split of `parent_path` — avoids recursive SQL; only valid if `parent_path` is indexed (it is)
- `logo_web` stored via `store=True` — avoids re-processing avatar on every report render
- `uninstalled_l10n_module_ids` uses raw SQL with `ARRAY_AGG` + `GROUP BY` — single query for all countries, not one per company
- `cache_invalidation_fields()` returns `{'active', 'sequence'}` — these fields trigger registry cache clear on change, affecting menu visibility and company switcher

**Security**:
- `write()` prevents changing `parent_id` after creation — company hierarchy is immutable
- `_check_active()` prevents archiving a company that has active users (`company_id` pointing to it) — protects operational continuity
- Public user per company (`_get_public_user()`): each company gets a unique `public-user@company-{id}.com` login; prevents cross-company data leakage in public pages

**Odoo 18 → 19 changes**:
- `company_details` field added for report header text
- `layout_background` and `layout_background_image` added for report customization
- `_get_company_root_delegated_field_names()` made overridable (was hardcoded)
- `all_child_ids` added for accessing inactive branches
- `uninstalled_l10n_module_ids` SQL rewritten to use `module_country` table (new in 19)
- `_all_branches_selected()` method added for whole-company action guards

---

## 4. res.currency

**Model**: `res.currency`
**Table**: `res_currency`
**Order**: `name`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Currency name |
| `symbol` | Char | - | Yes | Currency symbol |
| `full_name` | Char | - | - | Full descriptive name |
| `code` | Char | - | - | ISO 4217 code |
| `decimal_places` | Integer | computed | - | Computed from rounding |
| `rounding` | Float | `0.01` | - | Rounding factor |
| `rate` | Float | computed | - | Current rate |
| `rate_text` | Char | computed | - | Formatted rate string |
| `active` | Boolean | `True` | - | Active |
| `position` | Selection | `after` | - | Symbol position: before/after amount |
| `currency_unit_label` | Char | - | - | Unit label |
| `currency_subunit_label` | Char | - | - | Subunit label |
| `is_current_company_currency` | Boolean | computed | - | Is current company currency |

### L3 Key Methods

**Rate computation** (`_compute_current_rate()`):
- Uses context `to_currency` (default: company currency), `date`, `company`
- Falls back to most recent rate if no rate for given date
- `amount_to_text()` uses `num2words` library for amount-to-words conversion
- `amount_to_currency()` converts amounts between currencies

**Auto group management**:
- Active count > 1: activates `group_multi_currency` on `base.group_user`
- Active count <= 1: deactivates the group

---

## 5. res.country

**Model**: `res.country`
**Table**: `res_country`
**Order**: `name`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Country name |
| `code` | Char | - | Yes | ISO 3166-1 alpha-2 (2-char) |
| `address_format` | Text | - | - | Format string for printing |
| `address_view_id` | Many2one ir.ui.view | - | - | Custom address form |
| `phone_code` | Char | - | - | Country calling code |
| `country_group_ids` | Many2many res.country.group | - | - | Groups (EU, etc.) |
| `name_position` | Selection | `after` | - | Position of country name |
| `vat_label` | Char | - | - | Label for VAT field |
| `flag` | Char | computed | - | Emoji flag |
| `image_url` | Char | computed | - | PNG flag image URL |

**Special country code mappings** (post-Brexit/post-colonial):
- French territories (`GF`, `GP`, `MQ`, `RE`, `BL`, `MF`, `PF`, `TF`) map to `FR`
- `GB` -> `XI` (Northern Ireland post-Brexit, `EU_EXTRA_VAT_CODES`)
- `IM` -> `GB` (Isle of Man)
- `JE`, `GG` -> `GB` (Jersey, Guernsey)

**`ResCountryState`**:

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `country_id` | Many2one res.country | - | Yes | Parent country |
| `name` | Char | - | Yes | State name |
| `code` | Char | - | Yes | State code |

---

## 6. res.lang

**Model**: `res.lang`
**Table**: `res_lang`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Display name |
| `code` | Char | - | Yes | Locale code (e.g., `en_US`) |
| `iso_code` | Char | - | - | ISO 639-1 code |
| `url_code` | Char | - | Yes | URL-safe code |
| `active` | Boolean | - | - | Active |
| `direction` | Selection | `ltr` | - | ltr or rtl |
| `date_format` | Selection | `%m/%d/%Y` | Yes | Date format pattern |
| `time_format` | Selection | `%H:%M:%S` | Yes | Time format |
| `week_start` | Selection | `7` | Yes | First day of week (1=Mon) |
| `grouping` | Selection | `[3,0]` | Yes | Separator grouping |
| `decimal_point` | Char | `.` | Yes | Decimal separator |
| `thousands_sep` | Char | `,` | Yes | Thousands separator |
| `flag_image` | Image | - | - | Custom flag image |
| `flag_image_url` | Char | computed | - | Flag image URL |

### L3 Key Methods

**Caching architecture** (`LangData`, `LangDataDict`):
- `LangData`: readonly dict-like accessing field values like a `res.lang` record
- `LangDataDict`: dict of `LangData` indexed by language key; missing keys return dummy `LangData`
- `CACHED_FIELDS`: `['id', 'name', 'code', 'iso_code', 'url_code', 'active', 'direction', 'date_format', 'time_format', 'week_start', 'grouping', 'decimal_point', 'thousands_sep', 'flag_image_url']`
- `_get_active_by()`: `@ormcache('field', cache='stable')` returns `LangDataDict` indexed by field
- `_get_fields_cached()`: `@ormcache('model_name', 'self.env.lang', cache='stable')` for field metadata

**Translation loading** (`_activate_lang()`, `_activate_and_install_lang()`, `_create_lang()`):
- `_create_lang()` uses `locale.localeconv()` for number separators
- `_activate_and_install_lang()` calls `_update_translations()` on module install
- `_register_hook()` logs error if no language is active

---

## 7. ir.sequence

**Model**: `ir.sequence`
**Table**: `ir_sequence`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Sequence name |
| `code` | Char | - | - | Code for referencing via `next_by_code()` |
| `implementation` | Selection | `standard` | - | standard=PostgreSQL, no_gap=row-locking |
| `active` | Boolean | `True` | - | Active |
| `prefix` | Char | - | - | Prefix pattern (supports strftime placeholders) |
| `suffix` | Char | - | - | Suffix pattern |
| `number_next` | Integer | `1` | - | Next number to use |
| `number_next_actual` | Integer | computed | - | Current next (from PostgreSQL) |
| `number_increment` | Integer | `1` | - | Increment step |
| `padding` | Integer | `0` | - | Zero-padding width |
| `company_id` | Many2one res.company | `env.company` | - | Company scope |
| `use_date_range` | Boolean | `True` | - | Enable per-year subsequences |
| `date_range_ids` | One2many ir.sequence.date_range | - | - | Per-date-range numbers |

### L3 Implementation Variants

**`standard` implementation**:
- Uses PostgreSQL native sequences (`CREATE SEQUENCE ir_sequence_%03d START WITH n INCREMENT BY i`)
- `_create_sequence()` / `_drop_sequences()` manage DB sequence lifecycle on `create()` / `unlink()`
- `write()` calls `_alter_sequence()` to adjust `START WITH` or `INCREMENT BY` in-flight
- `next_by_id()` issues `SELECT nextval('ir_sequence_%03d')` — gap-free and atomic at DB level
- `_predict_nextval()` reads `last_value`, `increment_by`, `is_called` from `pg_sequences` (PG 10+) or the sequence table directly

**`no_gap` implementation**:
- No PostgreSQL sequence created — uses `number_next` field with `SELECT ... FOR UPDATE NOWAIT` row locking
- `_update_nogap()`: flushes `number_next`, locks the row, increments, invalidates cache
- Higher contention under concurrency; `FOR UPDATE NOWAIT` raises `psycopg2.errors.LockNotAvailable` on contention
- `_predict_nextval()` still works for display purposes

**Date ranges** (`ir.sequence.date_range`):
- `_create_date_range_seq(date)`: creates year-long range; extends backward/forward from existing ranges
- PostgreSQL sequence named `ir_sequence_%03d_%03d` per date range
- On range exhaustion: returns `False` from `_next()` (caller creates new range)

**Prefix/suffix interpolation** (`_get_prefix_suffix()`):
- Supports: `year`, `month`, `day`, `y` (2-digit), `doy` (day of year), `woy` (week of year), `weekday`, `h24`, `h12`, `min`, `sec`, `isoyear`, `isoy`, `isoweek`
- Prefixes: `range_*` (from `date_range` context), `current_*` (from `datetime.now()`)
- Invalid format raises `UserError` — caught at display time, not sequence consumption time
- Context vars: `ir_sequence_date`, `ir_sequence_date_range` override effective/range dates

**Multi-company resolution** (`next_by_code()`):
- Searches `code` matching, with `company_id IN (current_company, False)` ordered by `company_id DESC`
- Current company sequence takes precedence over fallback `company_id=False` sequence
- Returns `False` (not an error) if no sequence found — caller should handle gracefully

### L4 Performance and Security

**Performance**:
- `standard` sequences are the fastest option — PostgreSQL `nextval()` is atomic and lock-free
- `no_gap` sequences cause row-level lock contention on `res_users` (or the sequence table row) — avoid under high-concurrency invoice numbering
- `number_next_actual` reads from live PostgreSQL sequence — displayed value may lag if another transaction consumed nextval but did not commit
- `_alter_sequence()` called on every `write()` even if values unchanged — acceptable given rarity
- Date ranges reduce contention by scoping sequences per year; each range is an independent PostgreSQL sequence

**Security**:
- `implementation` change between `standard` and `no_gap` drops or creates PostgreSQL sequences — ensure no in-flight transactions when switching
- `company_id` on sequences is advisory — `next_by_code()` respects it but `next_by_id()` does not enforce
- SQL injection: `seq_name` in `_create_sequence()` is formatted via `%` — safe because it's constructed as `"ir_sequence_%03d" % seq.id` (numeric), not user input
- All other SQL uses `SQL.identifier()` for table/column names

**Odoo 18 → 19 changes**:
- `_predict_nextval()` uses `pg_sequences` catalog view (PG 10+) instead of `last_value` from `pg_class`
- PostgreSQL version check `server_version < 100000` for backward compat
- `use_date_range` default changed to `True` (was `False` in older versions)

---

## 8. ir.config_parameter

**Model**: `ir.config_parameter`
**Table**: `ir_config_parameter`
**Order**: `key`
**Allow sudo commands**: `False`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `key` | Char | - | Yes | Parameter key (dot-notation, unique) |
| `value` | Text | - | - | Parameter value (any string including newlines) |

**Constraint**: `UNIQUE(key)` at DB level

### L3 Key Methods

**Caching** (`_get_param(key)`):
- `@ormcache('key', cache='stable')` bypasses ORM field dependencies entirely
- Directly executes `SELECT value FROM ir_config_parameter WHERE key = %s` via raw SQL
- `flush_model(['key', 'value'])` called before the query — ensures cached writes are persisted
- Cache invalidation: `create()`, `write()`, `unlink()` all call `registry.clear_cache('stable')`

**`get_param(key, default=False)`**:
- Returns cached value or `default` if key absent — does NOT create a record
- Calls `check_access('read')` on empty browse record — validates user has read access

**`set_param(key, value)`**:
- Returns previous value or `False` — enables caller to detect changes
- `value is False or None`: deletes the parameter (calls `unlink()`)
- `value is not None and str(value) != old`: writes new value (triggers cache clear)
- No-op if value unchanged — avoids creating unnecessary write records

**Default parameters** (`_default_parameters`):
| Key | Default value |
|-----|---------------|
| `database.secret` | `str(uuid.uuid4())` — HMAC key for session tokens |
| `database.uuid` | `str(uuid.uuid1())` — database identity |
| `database.create_date` | `fields.Datetime.now` — installation timestamp |
| `web.base.url` | `http://localhost:<http_port>` — base URL for redirects |
| `base.login_cooldown_after` | `10` — failed attempts before cooldown |
| `base.login_cooldown_duration` | `60` — cooldown duration in seconds |

**Key conventions**:
- `database.secret`: auto-generated on DB creation; changing it invalidates all active session tokens
- `web.base.url`: used for email links, OAuth redirects, embedded Odoo URLs
- `database.is_neutralized`: marks neutralized (demo/prod) databases
- `base.template_auto_generate`: controls partner/company auto-creation from templates

**Lifecycle** (`@api.ondelete(at_uninstall=False)`):
- `unlink_default_parameters()` raises `ValidationError` if attempting to delete default parameters
- `write()` validates that `_default_parameters` keys are not renamed

### L4 Performance and Security

**Performance**:
- The `@ormcache` bypasses ORM entirely — no field prefetching, no access rights check per row, no `__get__()` overhead
- `get_param()` is called by hundreds of computed fields (e.g., `has_group()` checks debug mode via ICP); the cache is critical
- Cache is process-local (per worker) — does not share across gunicorn workers; safe because writes invalidate all caches

**Security**:
- `_allow_sudo_commands = False` — RPC `sudo()` commands cannot modify config parameters without access rights
- `database.secret` is the HMAC key for session tokens — exposing it allows session hijacking
- `web.base.url` is used to generate redirect URIs — ensure it matches actual server URL to prevent open redirect
- `write()` validates that protected keys are not renamed — prevents malicious modules from masquerading as system parameters

---

## 9. ir.property

**Model**: `ir.property`
**Table**: `ir_property`

This model stores default values and property definitions that vary by company or record context. It is the backend for Odoo's "Default" functionality and property fields.

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Property name (matches field name on target model) |
| `res_id` | Char | - | - | Record XML-ID or `model,id` reference (NULL=global default) |
| `company_id` | Many2one res.company | - | - | Company scope (NULL=all companies) |
| `fields_id` | Many2one ir.model.fields | - | Yes | Target field definition |
| `type` | Char | - | Yes | Value type: `char`, `integer`, `float`, `boolean`, `binary`, `many2one`, `date`, `datetime` |
| `value` | Text | - | - | Stored value (for scalar types) |
| `value_reference` | Char | - | - | Stored reference for relational types (`res.partner,3`) |
| `value_integer` | Integer | - | - | Integer value |
| `value_float` | Float | - | - | Float value |
| `value_binary` | Binary | - | - | Binary value |
| `value_text` | Text | - | - | Text value |
| `value_datetime` | Datetime | - | - | Datetime value |
| `value_id` | Many2one | - | - | Relational value (polymorphic via `model` stored in `type` context) |

### L3 Key Methods

**Property storage**:
- Each scalar type stored in its own column (`value_integer`, `value_float`, etc.)
- Relational types (`many2one`) stored as `value_reference` string (`'res.partner,5'`)
- `value_reference` parsed via `models.parse_value_reference()` for ORM access

**Property resolution** (`_get_property_value()`):
- Searches by `name`, `fields_id`, `company_id` (NULL match first), then `res_id` (specific record over global)
- Company-specific values override global defaults
- Record-specific values override company defaults

**Performance**: Properties are resolved at read time; no caching at the property layer — the calling model's field definition caches the resolved value via `company_dependent=True` on the field.

---

## 10. ir.cron

**Model**: `ir.cron`
**Table**: `ir_cron`
**Inherits**: `_inherits = {'ir.actions.server': 'ir_actions_server_id'}` (delegation)
**Order**: `cron_name, id`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `ir_actions_server_id` | Many2one ir.actions.server | - | Yes | Server action (delegate, `ondelete='restrict'`) |
| `cron_name` | Char | computed | - | Name synced from server action |
| `user_id` | Many2one res.users | `self.env.user` | - | Scheduler user |
| `active` | Boolean | `True` | - | Active |
| `interval_number` | Integer | `1` | - | Repeat interval |
| `interval_type` | Selection | `months` | - | minutes/hours/days/weeks/months |
| `nextcall` | Datetime | `fields.Datetime.now` | Yes | Next planned execution |
| `lastcall` | Datetime | - | - | Previous execution time |
| `priority` | Integer | `5` | - | 0=highest, 10=lowest |
| `failure_count` | Integer | `0` | - | Consecutive failure counter |
| `first_failure_date` | Datetime | - | - | First failure timestamp |

**Constraint**: `CHECK(interval_number > 0)`

### L3 Key Methods

**Job acquisition** (`_acquire_one_job()`):
- Uses `FOR NO KEY UPDATE SKIP LOCKED` to prevent two workers processing same job
- `NO KEY UPDATE` avoids conflict with FK references to `ir_cron`
- `SKIP LOCKED` allows immediate skip if job already locked by another worker

**CompletionStatus pattern**:
- `FULLY_DONE`: job completed normally; rescheduled after `interval_number` + `interval_type`
- `PARTIALLY_DONE`: processed some but not all; rescheduled ASAP via `ir_cron_trigger`
- `FAILED`: failed; may auto-deactivate if thresholds exceeded

**Failure tracking** (`_update_failure_count()`):
- Thresholds: `MIN_FAILURE_COUNT_BEFORE_DEACTIVATION=5`, `MIN_DELTA_BEFORE_DEACTIVATION=7 days`
- Both must be exceeded to auto-deactivate
- Counter and date reset on `FULLY_DONE`/`PARTIALLY_DONE`

**Progress API** (`_add_progress()`, `_commit_progress()`):
- Creates `ir.cron.progress` record per cron batch iteration
- Progress committed to DB within cron loop to support crash recovery
- `_run_job()` loops up to `MIN_RUNS_PER_JOB=10` times or `MIN_TIME_PER_JOB=10` seconds

**Trigger system** (`IrCronTrigger`, `_trigger()`, `_trigger_list()`):
- `ir.cron.trigger`: `cron_id`, `call_at` (datetime, index btree)
- `nextcall <= NOW()` OR `call_at <= NOW()` in `ir_cron_trigger` -> job is ready
- `_trigger(at)`: schedules at specific time(s); defaults to immediately
- `ODOO_NOTIFY_CRON_CHANGES` env var: wake cron workers via `pg_notify`

---

## 11. ir.model

**Model**: `ir.model`
**Table**: `ir_model`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Model description |
| `model` | Char | `x_` | Yes | Model name |
| `order` | Char | `id` | Yes | SQL ORDER BY clause |
| `info` | Text | - | - | Model docstring |
| `field_id` | One2many ir.model.fields | - | Yes | Custom fields |
| `inherited_model_ids` | Many2many ir.model | computed | - | Parent models |
| `state` | Selection | `manual` | - | base or manual |
| `access_ids` | One2many ir.model.access | - | - | ACLs |
| `rule_ids` | One2many ir.rule | - | - | Record rules |
| `abstract` | Boolean | - | - | Abstract model |
| `transient` | Boolean | - | - | Transient model |
| `modules` | Char | computed | - | Installed modules |
| `view_ids` | One2many ir.ui.view | computed | - | Views |
| `count` | Integer | computed | - | Record count |
| `fold_name` | Char | - | - | Kanban fold field |

**Constraint**: `UNIQUE(model)` — "Each model must have a unique name"

### L3 Key Methods

**Custom model lifecycle**:
- `create()`: calls `_setup_models__()` then `init_models()` to create DB table
- `unlink()`: removes fields, cron jobs, ir.model.data, drops table, then reloads registry
- `write()`: restricts modifying `model`, `state`, `abstract`, `transient`
- `_drop_table()`: handles views (`DROP VIEW`) vs tables (`DROP TABLE CASCADE`)
- `_instanciate_attrs()`: returns model attrs from custom model data for registry

**Model reflection** (`_reflect_model_params()`, `_reflect_models()`):
- Uses `upsert_en()` for efficient insert-or-update of model metadata
- XML-ID generation: `model_xmlid(module, model_name)` -> `module.model_model_name`

---

## 12. ir.model.fields

**Model**: `ir.model.fields`
**Table**: `ir_model_fields`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | `x_` | Yes | Field name |
| `model` | Char | - | Yes | Model name |
| `model_id` | Many2one ir.model | - | Yes | Parent model |
| `field_description` | Char | `` | Yes | Field label |
| `help` | Text | - | - | Help text |
| `ttype` | Selection | - | Yes | Field type |
| `selection` | Char | computed | - | Deprecated selection values |
| `selection_ids` | One2many ir.model.fields.selection | - | - | Selection options |
| `related` | Char | - | - | Related field path |
| `relation` | Char | - | - | Comodel name |
| `relation_field` | Char | - | - | Inverse field |
| `relation_table` | Char | - | - | M2M relation table |
| `column1` | Char | - | - | M2M column 1 |
| `column2` | Char | - | - | M2M column 2 |
| `required` | Boolean | - | - | Required |
| `readonly` | Boolean | - | - | Readonly |
| `index` | Boolean | - | - | Database index |
| `store` | Boolean | `True` | - | Stored in DB |
| `copied` | Boolean | computed | - | Copied on duplicate |
| `translate` | Selection | - | - | Translation mode |
| `company_dependent` | Boolean | - | - | Company dependent |
| `size` | Integer | - | - | Size for char fields |
| `state` | Selection | `manual` | - | base or manual |
| `on_delete` | Selection | `set null` | - | On delete for many2one |
| `domain` | Char | `[]` | - | Domain expression |
| `group_expand` | Boolean | - | - | Expand groups in kanban |
| `groups` | Many2many res.groups | - | - | Restrict to groups |
| `compute` | Text | - | - | Compute code |
| `depends` | Char | - | - | Compute dependencies |
| `sanitize*` | Boolean | various | - | HTML sanitization settings |

### L3 Key Methods

**Manual field lifecycle**:
- `write()`: if field is `manual`, sets `state='base'`, renames DB column
- `_prepare_update()`: returns fields that depend on this field (for cascade updates)
- `_drop_column()`: drops DB column for manual fields on uninstall

**Field instanciation** (`_instanciate_attrs()`):
- Returns field kwargs from `ir.model.fields` metadata
- For `many2one`: sets `comodel_name`, `ondelete`, `domain`, `group_expand`
- For `one2many`: requires inverse field to exist in comodel
- For `many2many`: computes relation/column names via `_custom_many2many_names()`
- For `html`: extracts sanitization settings

**Cache** (`_all_manual_field_data()`, `_get_fields_cached()`):
- `_all_manual_field_data()`: `@ormcache(cache='stable')` — all manual fields in one query
- `_get_fields_cached()`: `@ormcache('model_name', 'self.env.lang', cache='stable')` — cached field metadata with translations

---

## 13. ir.actions.actions

**Model**: `ir.actions.actions`
**Table**: `ir_actions`
**Order**: `name, id`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Action name |
| `type` | Char | - | Yes | Action type |
| `xml_id` | Char | computed | - | External ID |
| `path` | Char | - | - | URL path |
| `help` | Html | - | - | Help text |
| `binding_model_id` | Many2one ir.model | - | - | Contextual action model |
| `binding_type` | Selection | `action` | - | action or report |
| `binding_view_types` | Char | `list,form` | - | Views to bind to |

**Constraints**:
- `UNIQUE(path)` — path must be unique
- Path pattern: lowercase alphanumeric, underscore, dash; cannot start with `m-` or `action-`; cannot be `new`

### L3 Key Methods

**Bindings** (`get_bindings()`, `_get_bindings()`):
- `@tools.ormcache('model_name', 'self.env.lang')` on `_get_bindings()`
- Filters by user group membership and model access
- Returns `frozendict` for security
- Clears cache on action create/write/unlink

---

## 14. ir.actions.act_window

**Model**: `ir.actions.act_window`
**Table**: `ir_act_window`
**Inherits**: `ir.actions.actions`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `view_id` | Many2one ir.ui.view | - | - | Default view |
| `domain` | Char | - | - | Domain expression |
| `context` | Char | `{}` | Yes | Context dict |
| `res_id` | Integer | - | - | Record ID for form view |
| `res_model` | Char | - | Yes | Target model |
| `target` | Selection | `current` | - | current/new/fullscreen/main |
| `view_mode` | Char | `list,form` | Yes | Comma-separated view modes |
| `mobile_view_mode` | Char | `kanban` | - | Mobile first mode |
| `usage` | Char | - | - | Action usage |
| `view_ids` | One2many ir.actions.act_window.view | - | - | View order/modes |
| `views` | Binary | computed | - | Ordered view list |
| `limit` | Integer | `80` | - | Default list page size |
| `group_ids` | Many2many res.groups | - | - | Restrict to groups |
| `search_view_id` | Many2one ir.ui.view | - | - | Custom search view |
| `embedded_action_ids` | One2many ir.embedded.actions | computed | - | Embedded actions |
| `filter` | Boolean | - | - | Persist filter |
| `cache` | Boolean | `True` | - | Enable data caching |

---

## 15. ir.actions.server

**Model**: `ir.actions.server`
**Table**: `ir_act_server`
**Inherits**: `ir.actions.actions`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | computed/store | - | Action name |
| `usage` | Selection | `ir_actions_server` | - | ir_actions_server or ir_cron |
| `state` | Selection | - | Yes | code/object_write/object_create/object_copy/webhook/multi |
| `model_id` | Many2one ir.model | - | Yes | Target model |
| `code` | Text | - | - | Python code (group: base.group_system) |
| `webhook_url` | Char | - | - | Webhook POST URL |
| `webhook_field_ids` | Many2many ir.model.fields | - | - | Fields to include in webhook |
| `sequence_id` | Many2one ir.sequence | - | - | Sequence for sequence evaluation |
| `ir_cron_ids` | One2many ir.cron | - | - | Scheduled action records |

### L3 Key Methods

**Runner pattern** (`_get_runner()`, `run()`, `_run()`):
- Looks for `_run_action_{state}` or `_run_action_{state}_multi` methods
- `_run_action_webhook()`: POST to webhook URL with 1s timeout; `@postcommit` sends after DB commit; `@postrollback` cancels on rollback

---

## 16. ir.ui.menu

**Model**: `ir.ui.menu`
**Table**: `ir_ui_menu`
**Parent store**: `_parent_store = True`
**Order**: `sequence, id`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Menu label |
| `active` | Boolean | `True` | - | Visible |
| `sequence` | Integer | `10` | - | Ordering |
| `child_id` | One2many ir.ui.menu | - | - | Child menus |
| `parent_id` | Many2one ir.ui.menu | - | - | Parent menu |
| `parent_path` | Char | - | - | Path for ancestry |
| `group_ids` | Many2many res.groups | - | - | Group restriction |
| `complete_name` | Char | computed | - | Full path |
| `web_icon` | Char | - | - | Icon specifier |
| `web_icon_data` | Binary | - | - | Icon image |
| `action` | Reference | - | - | Action reference |

### L3 Key Methods

**Visibility** (`_visible_menu_ids()`, `_filter_visible_menus()`):
- `@tools.ormcache('frozenset(self.env.user._get_group_ids())', 'debug')` — key includes user's group set
- Disables `base.group_no_one` in production mode (debug only)
- Marks ancestors visible when descendant is visible

**Menu tree** (`load_menus()`, `load_menus_root()`):
- `@tools.ormcache('self.env.uid', 'self.env.lang', 'debug')`
- Fetches `web_icon_data` from `ir.attachment`

---

## 17. ir.filters

**Model**: `ir.filters`
**Table**: `ir_filters`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Filter name |
| `user_ids` | Many2many res.users | - | - | Shared users (empty=global) |
| `domain` | Text | `[]` | Yes | Domain expression |
| `context` | Text | `{}` | Yes | Context dict |
| `sort` | Char | `[]` | Yes | Sort criteria JSON |
| `model_id` | Selection | - | Yes | Target model |
| `is_default` | Boolean | - | - | Default filter |
| `action_id` | Many2one ir.actions.actions | - | - | Action scope |
| `embedded_action_id` | Many2one ir.embedded.actions | - | - | Embedded action scope |
| `embedded_parent_res_id` | Integer | - | - | Parent record scope |
| `active` | Boolean | `True` | - | Active |

---

## 18. ir.default

**Model**: `ir.default`
**Table**: `ir_default`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `field_id` | Many2one ir.model.fields | - | Yes | Target field |
| `user_id` | Many2one res.users | - | - | User scope (NULL=all users) |
| `company_id` | Many2one res.company | - | - | Company scope (NULL=all companies) |
| `condition` | Char | - | - | Condition expression |
| `json_value` | Char | - | Yes | JSON-encoded default value |

### L3 Key Methods

**Default resolution** (`_get_model_defaults()`):
- `@tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name', 'condition')`
- Order: `d.user_id, d.company_id, d.id` — highest priority wins per field
- Priority: user-specific > company-specific > global

**Cache invalidation**: `create()`, `write()`, `unlink()` call `registry.clear_cache()` and `invalidate_all()`

---

## 19. ir.model.data

**Model**: `ir.model.data`
**Table**: `ir_model_data`
**Order**: `name, module`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | External ID name |
| `module` | Char | - | Yes | Module name |
| `model` | Char | - | Yes | Model name |
| `res_id` | Integer | - | Yes | Record ID |
| `noupdate` | Boolean | `False` | - | No update on module upgrade |
| `reference` | Char | computed | - | Full XML reference |

### L3 Key Methods

**XML-ID resolution**:
- `get_object()` / `_xmlid_to_obj()`: resolves XML ID to record
- `_update_xmlids()`: creates or updates XML-ID records
- `models_to_check()`: custom models needing XML-ID updates

**Loading** (`_load_records()`):
- `noupdate=True`: skips if record with `external_id` exists
- Custom models (starting with `x_`) loaded via `create()` instead of `upsert()`

---

## 20. ir.actions.act_window.view

**Model**: `ir.actions.act_window.view`
**Table**: `ir_act_window_view`

### L2 Fields

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `sequence` | Integer | - | - | View priority |
| `view_id` | Many2one ir.ui.view | - | - | Target view |
| `view_mode` | Selection | - | Yes | View type |
| `act_window_id` | Many2one ir.actions.act_window | - | Yes | Parent action |
| `multi` | Boolean | - | - | Not on form right toolbar |

**Constraint**: `UNIQUE(act_window_id, view_mode)`

---

## 21. ir.actions.act_url

**Model**: `ir.actions.act_url`
**Table**: `ir_act_url`
**Inherits**: `ir.actions.actions`

---

## 22. ir.actions.act_window_close

**Model**: `ir.actions.act_window_close`
**Table**: `ir_actions`

Readable fields include: `effect`, `infos` (used by action_service)

---

## 23. ir.actions.todo

**Model**: `ir.actions.todo`
**Table**: `ir_actions_todo`

### L3 Key Methods

**State management**:
- `ensure_one_open_todo()`: when todo opens, marks all others as `done` (by sequence order)
- On unlink: preserves `base.open_menu` todo and redirects to `base.action_client_base_menu`

---

## 24. res.partner.industry

**Model**: `res.partner.industry`
**Table**: `res_partner_industry`
**Order**: `name, id`

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Industry name (translate=True) |
| `full_name` | Char | - | - | Full name |
| `parent_id` | Many2one res.partner.industry | - | - | Parent industry |
| `child_ids` | One2many res.partner.industry | - | - | Child industries |
| `active` | Boolean | `True` | - | Active |

---

## 25. res.partner.category

**Model**: `res.partner.category`
**Table**: `res_partner_category`
**Parent store**: `_parent_store = True`
**Order**: `name, id`

| Field | Type | Default | Required | Help |
|-------|------|---------|----------|------|
| `name` | Char | - | Yes | Tag name (translate=True) |
| `color` | Integer | `randint(1,11)` | - | Kanban color |
| `parent_id` | Many2one res.partner.category | - | - | Parent tag |
| `child_ids` | One2many res.partner.category | - | - | Child tags |
| `active` | Boolean | `True` | - | Active |
| `parent_path` | Char | - | - | Path for ancestry |
| `partner_ids` | Many2many res.partner | - | - | Partners in category |

---

## Cross-Model Patterns

### Multi-Company Domain Checking

Several models use `_check_company_domain` or `_check_company_auto`:
- `res.partner`: `_check_company_domain = models.check_company_domain_parent_of` — validates partner is in same company tree as parent
- `res.users`: `_check_company_auto = True` — auto-fills `company_id` on write

### Record Rule for Multi-Company

`ir.rule` records define record-level access:
- `model_id`: references `ir.model`
- `domain`: Python domain expression evaluated with `user` in context
- `groups`: restricts rule to specific groups
- `perm_read/write/create/unlink`: operation flags

### @ormcache Patterns

| Method | Cache key | Purpose |
|--------|---------|---------|
| `_visible_menu_ids()` | `(frozenset(group_ids), debug)` | Menu visibility per user |
| `_get_active_by()` (lang) | `(field,)` | Language data by field |
| `_get_fields_cached()` (model) | `(model_name, lang)` | Field metadata with translations |
| `_all_manual_field_data()` | `()` | All manual field data |
| `_get_model_defaults()` | `(uid, company_id, model, condition)` | Default values |
| `_get_bindings()` | `(model_name, lang)` | Action bindings per model |
| `_get_group_definitions()` | `()` | All group relationships for `has_group()` |
| `load_menus()` | `(uid, lang, debug)` | Full menu tree |
| `_get_param()` (ICP) | `(key,)` | System parameter values |
| `_crypt_context()` | `()` | Password hashing context |
| `_compute_session_token()` | `(sid,)` | Session token per session ID |
| `__accessible_branches()` (company) | `(tuple(company_ids), self.id, uid)` | Accessible branches |
| `_get_company_ids()` (user) | `(self.id,)` | Active companies for user |

### Commercial Fields Architecture

The commercial fields system in `res.partner` is the canonical Odoo delegation-with-sync pattern:

1. `commercial_partner_id` computed as topmost ancestor that is a company (or self); stored for performance
2. `_commercial_fields()` returns list of fields managed by commercial entity
3. `_synced_commercial_fields()` returns `['vat']` — these sync UPSTREAM (contact -> parent) when changed
4. Non-synced commercial fields (`company_registry`, `industry_id`) sync DOWNSTREAM only
5. `_fields_sync(values)` called after every `write()` — three-phase sync: upstream, downstream, children
6. `_company_dependent_commercial_sync()` propagates company-dependent values across all companies via `with_company()`

### Session Token Security

Session tokens use HMAC-SHA256 with `database.secret`:
- Fields: `id`, `login`, `password`, `active`
- Raw SQL via `SQL.identifier` prevents injection
- `@ormcache('sid')` — cached per session ID, invalidated when any field changes
- Used by web controllers for session validation

### Cron Progress API

The cron progress system enables batch job recovery:

1. `_add_progress()` creates `ir.cron.progress` record at batch start
2. `_commit_progress(processed, remaining)` updates counts and commits within loop
3. On crash: next cron run reads last progress record, continues where left off
4. `CompletionStatus` determines reschedule behavior
5. `IrCronTrigger` provides immediate scheduling without waiting for nextcall

### SQL Helpers in ir.model

The `ir.model` module provides reusable SQL helpers:
- `upsert_en()`: PostgreSQL upsert with translation handling
- `select_en()`: select with translation columns
- `query_insert()`: batch insert returning IDs
- `query_update()`: update by selectors returning IDs
- All use `SQL.identifier()` for safe SQL construction

---

## Version History

| Version | Change |
|---------|--------|
| 18.0 -> 19.0 | `ir.cron` progress API redesigned with `completion_status` pattern |
| 18.0 -> 19.0 | `ir.actions.server` webhook state added with async POST (1s timeout, postcommit) |
| 18.0 -> 19.0 | `commercial_partner_id` made stored/indexed (was computed in Odoo 18) |
| 18.0 -> 19.0 | `@api.readonly` decorator added for `has_group()` and `has_groups()` |
| 18.0 -> 19.0 | `ir.ui.menu` `load_menus()` reworked with `app_id` hierarchy |
| 18.0 -> 19.0 | `res.partner` `company_registry` made stored |
| 18.0 -> 19.0 | `ir.filters` `embedded_action_id` and `embedded_parent_res_id` added |
| 18.0 -> 19.0 | `IrActionsServer` `allowed_states` field added (Json computed) |
| 18.0 -> 19.0 | `res.users` `device_ids` and `identitycheck_validity` added |
| 18.0 -> 19.0 | `IrActionsAct_Window` `mobile_view_mode` and `embedded_action_ids` added |
| 18.0 -> 19.0 | `IrActionsAct_Window` `cache` field for action-level data caching |
| 18.0 -> 19.0 | `res.lang` `flag_image` and `flag_image_url` added |
| 18.0 -> 19.0 | `res.company` `company_details`, `layout_background` added |
| 18.0 -> 19.0 | `res.company` `_get_company_root_delegated_field_names()` made overridable |
| 18.0 -> 19.0 | `res.users` `_check_disjoint_groups()` constraint for implied-group conflicts |
| 18.0 -> 19.0 | `res.users` `role` field as simplified group_user/group_system interface |
| 18.0 -> 19.0 | `res.users` `view_group_hierarchy` Json field for settings UI |
| 18.0 -> 19.0 | `res.users` plaintext password auto-upgrade on startup via `init()` |
| 18.0 -> 19.0 | `res.users` `MIN_ROUNDS = 600_000` added for password hashing |
| 18.0 -> 19.0 | `ir.sequence` `_predict_nextval()` uses `pg_sequences` catalog (PG 10+) |
| 18.0 -> 19.0 | `ir.sequence` `use_date_range` default changed to `True` |
| 18.0 -> 19.0 | `res.partner` `_load_records_create()` batch optimization for XML loading |
| 18.0 -> 19.0 | `res.partner` `is_public` field added for odoobot detection |
| 18.0 -> 19.0 | `res.company` `_all_branches_selected()` added for whole-company guards |
| 18.0 -> 19.0 | `res.company` `uninstalled_l10n_module_ids` SQL rewritten for `module_country` table |
