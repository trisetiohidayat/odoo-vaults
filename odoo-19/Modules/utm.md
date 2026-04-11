# UTM Trackers (`utm`)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `utm` |
| **Category** | Marketing |
| **Depends** | `base`, `web` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | `1.1` |

---

## Purpose

The UTM (Urchin Tracking Module) module provides **marketing attribution infrastructure** for Odoo. It enables tracking of the source, medium, and campaign that generated a lead, opportunity, or sale order. Data flows into business intelligence reports, helping marketing teams understand which campaigns deliver ROI.

---

## Architecture

### Tracking Flow

```
URL param (utm_source) ──► Cookie (odoo_utm_source) ──► Model field (source_id)
URL param (utm_medium)  ──► Cookie (odoo_utm_medium)  ──► Model field (medium_id)
URL param (utm_campaign) ──► Cookie (odoo_utm_campaign) ──► Model field (campaign_id)
```

A visitor clicks a UTM-tagged link (e.g., `https://mycompany.odoo.com/crm/leads/create?utm_source=linkedin&utm_medium=social&utm_campaign=q1_hiring`). Odoo's `ir_http._post_dispatch()` detects the `utm_*` URL parameters and writes them into browser cookies (`odoo_utm_source`, etc.) with a 31-day max-age. When that visitor later fills out a form or when a sales agent creates a lead, `utm.mixin.default_get()` reads the cookies and auto-populates `source_id`, `medium_id`, and `campaign_id` on the new record.

---

## L1 — Models, Fields, and Methods

### 1.1 `utm.mixin` — Core Tracking Mixin

**File:** `~/odoo/odoo19/odoo/addons/utm/models/utm_mixin.py`

Abstract model. Any concrete model that inherits `utm.mixin` gains three Many2one fields and auto-population logic.

#### Fields

| Field | Type | Index | Help |
|-------|------|-------|------|
| `campaign_id` | `many2one('utm.campaign')` | `btree_not_null` | "This is a name that helps you keep track of your different campaign efforts, e.g. Fall_Drive, Christmas_Special" |
| `source_id` | `many2one('utm.source')` | `btree_not_null` | "This is the source of the link, e.g. Search Engine, another domain, or name of email list" |
| `medium_id` | `many2one('utm.medium')` | `btree_not_null` | "This is the method of delivery, e.g. Postcard, Email, or Banner Ad" |

#### `default_get(fields)` — Cookie Auto-Population

```python
@api.model
def default_get(self, fields):
    values = super(UtmMixin, self).default_get(fields)

    # Salesmen are excluded from auto-population.
    # This is a business decision: sales reps should explicitly assign
    # UTM values rather than passively inheriting browser cookies.
    if not self.env.is_superuser() and self.env.user.has_group('sales_team.group_sale_salesman'):
        return values

    for _url_param, field_name, cookie_name in self.env['utm.mixin'].tracking_fields():
        if field_name in fields:
            field = self._fields[field_name]
            value = False
            if request:
                value = request.cookies.get(cookie_name)
            # Convert string name → record via _find_or_create_record
            if field.type == 'many2one' and isinstance(value, str) and value:
                record = self._find_or_create_record(field.comodel_name, value)
                value = record.id
            if value:
                values[field_name] = value
    return values
```

Key behaviors:
- The `self.env['utm.mixin'].tracking_fields()` call is deliberate. It bypasses any override on the concrete model (e.g., `crm.lead`) and always uses `utm.mixin`'s own definition.
- The salesman exclusion check (`sales_team.group_sale_salesman`) means that portal users, superuser calls, and users without the salesman group will get UTM values auto-populated.
- `request.cookies` is a plain dict populated by Odoo's HTTP layer from the `Cookie` HTTP header.

#### `tracking_fields()` — Static Tuple

```python
def tracking_fields(self):
    return [
        ('utm_campaign', 'campaign_id', 'odoo_utm_campaign'),
        ('utm_source',  'source_id',    'odoo_utm_source'),
        ('utm_medium',  'medium_id',    'odoo_utm_medium'),
    ]
```

This method can be overridden by any model that inherits `utm.mixin` to change which URL params map to which fields, but the static tuple defined here is the canonical UTM triple.

#### `_tracking_models()` — Reverse Lookup

```python
def _tracking_models(self):
    fnames = {fname for _, fname, _ in self.tracking_fields()}
    return {
        self._fields[fname].comodel_name
        for fname in fnames
        if fname in self._fields and self._fields[fname].type == "many2one"
    }
```

Returns `{'utm.campaign', 'utm.source', 'utm.medium'}`. Used by `find_or_create_record()` to decide whether to use UTM-specific find-or-create logic.

#### `_find_or_create_record(model_name, name)` — Case-Insensitive Find-or-Create

```python
def _find_or_create_record(self, model_name, name):
    Model = self.env[model_name]
    cleaned_name = name.strip()
    if cleaned_name:
        record = Model.with_context(active_test=False).search(
            [('name', '=ilike', cleaned_name)], limit=1)

    if not record:
        record_values = {'name': cleaned_name}
        if 'is_auto_campaign' in record._fields:
            record_values['is_auto_campaign'] = True
        record = Model.create(record_values)

    return record
```

- `=ilike` (PostgreSQL `ILIKE` with `=` prefix) provides **case-insensitive, anchored** matching. `"LinkedIn Plus"` matches `"linkedin plus"` but NOT `"linkedin"` alone.
- `active_test=False` means archived records are found too — prevents creating duplicates of archived records.
- If `model_name` is `'utm.campaign'` and the model has `is_auto_campaign`, the created record gets `is_auto_campaign = True`.

#### `_get_unique_names(model_name, names)` — Counter-Based Unique Name Generation

```python
@api.model
def _get_unique_names(self, model_name, names):
    # 1. Strip counters from all input names
    names_without_counter = {self._split_name_and_count(name)[0] for name in names}

    # 2. Search DB for all records whose name matches any base name (ilike)
    search_domain = Domain.OR(Domain('name', 'ilike', name) for name in names_without_counter)
    if skip_record_ids:
        search_domain &= Domain('id', 'not in', skip_record_ids)
    existing_names = {vals['name'] for vals in self.env[model_name].search_read(search_domain, ['name'])}

    # 3. Build used counter sets per base name
    used_counters_per_name = {
        name: {
            self._split_name_and_count(existing_name)[1]
            for existing_name in existing_names
            if existing_name == name or existing_name.startswith(f'{name} [')
        } for name in names_without_counter
    }

    # 4. Assign counters to fill gaps
    current_counter_per_name = defaultdict(lambda: itertools.count(1))
    result = []
    for name in names:
        name_without_counter, asked_counter = self._split_name_and_count(name)
        existing = used_counters_per_name.get(name_without_counter, set())
        if asked_counter and asked_counter not in existing:
            count = asked_counter   # respect explicitly given counter if available
        else:
            for count in current_counter_per_name[name_without_counter]:
                if count not in existing:
                    break
        existing.add(count)
        result.append(f'{name_without_counter} [{count}]' if count > 1 else name_without_counter)

    return result
```

Core behaviors:
- Gaps in counter sequences are filled. If `[2]` and `[4]` exist but `[3]` does not, the next `UTM new` becomes `UTM new [3]`.
- The context key `utm_check_skip_record_ids` prevents false positives when renaming a record in-place.
- Explicit counters like `[2]` are accepted if available; otherwise, the next free counter is used.

#### `_split_name_and_count(name)` — Static Parser

```python
@staticmethod
def _split_name_and_count(name):
    name = name or ''
    name_counter_re = r'(.*)\s+\[([0-9]+)\]'
    match = re.match(name_counter_re, name)
    if match:
        return match.group(1), int(match.group(2) or '1')
    return name, 1
```

Edge cases handled:
- `"medium [0]"` → `("medium", 0)` — zero is a valid counter value
- `"medium [x]"` → `("medium [x]", 1)` — non-integer brackets are treated as literal name parts
- `"medium [0"` → `("medium [0", 1)` — malformed brackets don't crash

#### `find_or_create_record(model_name, name)` — Public API (Returns `dict`)

```python
@api.model
def find_or_create_record(self, model_name, name):
    if model_name in self._tracking_models():
        record = self._find_or_create_record(model_name, name)
    else:
        record = self.env[model_name].create({self.env[model_name]._rec_name: name})
    return {'id': record.id, 'name': record.display_name}
```

Used by the frontend (website_links, contact form) to resolve UTM parameters passed as JSON. Returns a plain dict with `id` and `name` rather than a recordset — suitable for JSON-RPC responses.

---

### 1.2 `utm.campaign` — Marketing Campaign

**File:** `~/odoo/odoo19/odoo/addons/utm/models/utm_campaign.py`

#### Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `title` | `char` | Yes | — | `translate=True`; the user-facing display name; `_rec_name` |
| `name` | `char` | Yes | computed | `store=True, compute='_compute_name', precompute=True`; the unique identifier |
| `active` | `boolean` | — | `True` | — |
| `user_id` | `many2one('res.users')` | Yes | `self.env.uid` | Campaign responsible |
| `stage_id` | `many2one('utm.stage')` | Yes | first `utm.stage` record | `copy=False`, `group_expand='_group_expand_stage_ids'` |
| `tag_ids` | `many2many('utm.tag')` | — | — | — |
| `is_auto_campaign` | `boolean` | — | `False` | Flags campaigns auto-created from URL params |
| `color` | `integer` | — | — | Kanban color index |

#### The `title` vs `name` Dual-Field Design

`title` is the `_rec_name` — it appears in dropdown labels and breadcrumb displays. It is translatable so marketing teams in different languages see the campaign in their own language.

`name` is a **stored, computed** field derived from `title` via `_compute_name`. It is the unique identifier used in find-or-create logic. A DB constraint enforces uniqueness.

When creating a campaign with only a `name` (no `title`), `title` is set to `name`. When creating with only `title`, `name` is computed from it.

#### `_compute_name()` — Stored Compute

```python
@api.depends('title')
def _compute_name(self):
    new_names = self.env['utm.mixin'].with_context(
        utm_check_skip_record_ids=self.ids
    )._get_unique_names(self._name, [c.title for c in self])
    for campaign, new_name in zip(self, new_names):
        campaign.name = new_name
```

Uses `precompute=True` to set `name` during the ORM batched write phase, avoiding per-record triggers.

#### `create()` — Dual-Name Normalization

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if not vals.get('title') and vals.get('name'):
            vals['title'] = vals['name']
    new_names = self.env['utm.mixin']._get_unique_names(self._name, [vals.get('name') for vals in vals_list])
    for vals, new_name in zip(vals_list, new_names):
        if new_name:
            vals['name'] = new_name
    return super().create(vals_list)
```

Batch-aware. Normalizes `title`/`name` in both directions and assigns unique counters before ORM `create()`.

#### `_group_expand_stage_ids()` — Kanban Group Expansion

```python
@api.model
def _group_expand_stage_ids(self, stages, domain):
    stage_ids = stages.sudo()._search([], order=stages._order)
    return stages.browse(stage_ids)
```

Odoo Kanban views by default only show stages that have records. This method ensures all `utm.stage` records appear as columns in the Kanban view even if they are empty.

#### Constraint

```python
_unique_name = models.Constraint(
    'UNIQUE(name)',
    'The name must be unique',
)
```

---

### 1.3 `utm.source` — Traffic Source

**File:** `~/odoo/odoo19/odoo/addons/utm/models/utm_source.py`

#### Fields

| Field | Type | Required | Constraint |
|-------|------|----------|-----------|
| `name` | `char` | Yes | `UNIQUE(name)` |

#### `_unlink_except_referral()` — Deletion Protection

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_referral(self):
    utm_source_referral = self.env.ref('utm.utm_source_referral', raise_if_not_found=False)
    for record in self:
        if record == utm_source_referral:
            raise ValidationError(_("You cannot delete the 'Referral' UTM source record."))
```

The `utm.utm_source_referral` record is protected because it is the default source assigned when a partner is referred by an existing customer (via `crm.lead` referral mechanism). Deleting it would break referral attribution.

#### `_generate_name(record, content)` — Auto-Naming for Self-Created Sources

```python
def _generate_name(self, record, content):
    if not content:
        return False
    content = content.replace('\n', ' ')
    if len(content) >= 24:
        content = f'{content[:20]}...'
    create_date = record.create_date or fields.Datetime.today()
    model_description = self.env['ir.model']._get(record._name).name
    return _(
        '%(content)s (%(model_description)s created on %(create_date)s)',
        content=content, model_description=model_description,
        create_date=fields.Date.to_string(create_date),
    )
```

Used by `utm.source.mixin` when a mailing or social post is created without explicitly naming its source. Produces names like `"Summer Promo (Mailing created on 2025-01-15)"`.

---

### 1.4 `utm.source.mixin` — Self-Managed Source Mixin

**File:** `~/odoo/odoo19/odoo/addons/utm/models/utm_source.py`

A **separate** abstract mixin (not to be confused with `utm.mixin`). Used by models like `mailing.mailing` and `social.post` that need to **auto-create and own** their own named UTM sources.

#### Fields

| Field | Type | Required | Ondelete | Notes |
|-------|------|----------|---------|-------|
| `source_id` | `many2one('utm.source')` | Yes | `restrict` | Required — every record must have a source |
| `name` | `char` | — | — | `related='source_id.name', readonly=False` — syncs source name to record name |

#### `create()` — Batch Source Creation

```python
@api.model_create_multi
def create(self, vals_list):
    # Pre-create all needed utm.source records
    utm_sources = self.env['utm.source'].create([
        {
            'name': values.get('name')
            or self.env.context.get('default_name')
            or self.env['utm.source']._generate_name(self, values.get(self._rec_name)),
        }
        for values in vals_list
        if not values.get('source_id')
    ])

    # Backfill source IDs into vals_list
    vals_list_missing_source = [values for values in vals_list if not values.get('source_id')]
    for values, source in zip(vals_list_missing_source, utm_sources):
        values['source_id'] = source.id

    # Remove 'name' before passing to super() — it belongs to utm.source, not the concrete model
    for values in vals_list:
        if 'name' in values:
            del values['name']

    return super().create(vals_list)
```

Key design: `source_id` is **required**. If the caller doesn't provide one, a named source is auto-created. The `name` field on the concrete model is deleted from `vals_list` before the ORM sees it — it belongs to `utm.source.name`, not to the mailing/post model.

#### `write()` — Unique Name Enforcement on Batch Write

```python
def write(self, vals):
    if (vals.get(self._rec_name) or vals.get('name')) and len(self) > 1:
        raise ValueError(_('You cannot update multiple records with the same name.'))
    # Generate name for source_id if rec_name changed
    if vals.get(self._rec_name) and not vals.get('name'):
        vals['name'] = self.env['utm.source']._generate_name(self, vals[self._rec_name])
    if vals.get('name'):
        vals['name'] = self.env['utm.mixin'].with_context(
            utm_check_skip_record_ids=self.source_id.ids
        )._get_unique_names("utm.source", [vals['name']])[0]
    return super().write(vals)
```

Enforces that batch-updating records with the same name is forbidden, since `utm.source` names must be unique and two records can't share one source.

#### `copy_data()` — Counter Increment on Duplicate

```python
def copy_data(self, default=None):
    default = default or {}
    default_name = default.get('name')
    vals_list = super().copy_data(default=default)
    for source, vals in zip(self, vals_list):
        vals['name'] = self.env['utm.mixin']._get_unique_names("utm.source", [default_name or source.name])[0]
    return vals_list
```

Duplicating a mailing increments the source counter. So copying `"Summer Promo"` creates `"Summer Promo [2]"`.

---

### 1.5 `utm.medium` — Delivery Medium

**File:** `~/odoo/odoo19/odoo/addons/utm/models/utm_medium.py`

#### Fields

| Field | Type | Required | Constraint |
|-------|------|----------|-----------|
| `name` | `char` | Yes | `UNIQUE(name)`, `translate=False` |
| `active` | `boolean` | — | `True` |

#### `SELF_REQUIRED_UTM_MEDIUMS_REF` — Protected System Mediums

```python
@property
def SELF_REQUIRED_UTM_MEDIUMS_REF(self):
    return {
        'utm.utm_medium_email': 'Email',
        'utm.utm_medium_direct': 'Direct',
        'utm.utm_medium_website': 'Website',
        'utm.utm_medium_twitter': 'X',
        'utm.utm_medium_facebook': 'Facebook',
        'utm.utm_medium_linkedin': 'LinkedIn',
    }
```

#### `_unlink_except_utm_medium_record()` — Deletion Protection

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_utm_medium_record(self):
    for medium in self.SELF_REQUIRED_UTM_MEDIUMS_REF:
        utm_medium = self.env.ref(medium, raise_if_not_found=False)
        if utm_medium and utm_medium in self:
            raise UserError(_("Oops, you can't delete the Medium '%s'."))
```

Six mediums are load-bearing: they are the standard IAB/Open GRP mediums used by Google Analytics, Facebook Pixel, LinkedIn Insight Tag, etc. Deleting them would break cross-platform attribution.

#### `_fetch_or_create_utm_medium(name, module='utm')` — Normalized Fetch-or-Create

```python
def _fetch_or_create_utm_medium(self, name, module='utm'):
    name_normalized = re.sub(r"[\s|.]", "_", name.lower())
    try:
        return self.env.ref(f'{module}.utm_medium_{name_normalized}')
    except ValueError:
        utm_medium = self.sudo().env['utm.medium'].create({
            'name': self.SELF_REQUIRED_UTM_MEDIUMS_REF.get(
                f'{module}.utm_medium_{name_normalized}', name)
        })
        self.sudo().env['ir.model.data'].create({
            'name': f'utm_medium_{name_normalized}',
            'module': module,
            'res_id': utm_medium.id,
            'model': 'utm.medium',
        })
        return utm_medium
```

Used by the website_link tracking system (`website_links` module) to convert raw medium names from external trackers (e.g., `"Google.AdWords"`) into `utm.medium` records. Normalizes spaces and dots to underscores, then looks up or creates the record.

---

### 1.6 `utm.stage` — Campaign Stage

**File:** `~/odoo/odoo19/odoo/addons/utm/models/utm_stage.py`

#### Fields

| Field | Type | Required | Default | Order |
|-------|------|----------|---------|-------|
| `name` | `char` | Yes | — | `translate=True` |
| `sequence` | `integer` | — | `1` | `_order = 'sequence'` |

ACL: `base.group_user` gets **read-only** access (`perm_read=1, perm_write=0, perm_create=0, perm_unlink=0`). Only `base.group_system` can modify stages. This is intentional — campaign stages are an organizational concern, not a user-editable field.

#### Default Data

The data file `utm_stage_data.xml` creates a single `"New"` stage with `sequence=10` as the system default. Demo data adds additional stages.

---

### 1.7 `utm.tag` — Campaign Tag

**File:** `~/odoo/odoo19/odoo/addons/utm/models/utm_tag.py`

#### Fields

| Field | Type | Required | Constraint |
|-------|------|----------|-----------|
| `name` | `char` | Yes | `UNIQUE(name)`, `translate=True` |
| `color` | `integer` | — | Default `randint(1, 11)` |

#### `_default_color()` — Random Color

```python
def _default_color(self):
    return randint(1, 11)
```

Colors are randomly assigned on creation. Zero color (the default for most integer fields) means "no display in kanban" — distinguishing internal organizational tags from public categorization tags.

#### `_name_uniq` Constraint

```python
_name_uniq = models.Constraint(
    'unique (name)',
    'Tag name already exists!',
)
```

Unlike the soft `UNIQUE(name)` constraint on `utm.source` and `utm.medium` (which goes through `_get_unique_names` to add counters), `utm.tag` enforces **hard uniqueness** — no counter suffixes are appended.

---

### 1.8 `ir.http` UTM Cookie Management

**File:** `~/odoo/odoo19/odoo/addons/utm/models/ir_http.py`

#### `get_utm_domain_cookies()` — Cookie Domain

```python
@classmethod
def get_utm_domain_cookies(cls):
    return request.httprequest.host
```

Sets the cookie domain to the HTTP `Host` header value, making it available across subdomains.

#### `_set_utm(response)` — Write UTM Cookies

```python
@classmethod
def _set_utm(cls, response):
    response = Response.load(response)
    domain = cls.get_utm_domain_cookies()
    for _url_param, _field_name, cookie_name in request.env['utm.mixin'].tracking_fields():
        if url_parameter in request.params and request.cookies.get(cookie_name) != request.params[url_parameter]:
            response.set_cookie(
                cookie_name, request.params[url_parameter],
                max_age=31 * 24 * 3600, domain=domain, cookie_type='optional'
            )
```

Only writes the cookie if the incoming URL param differs from the current cookie value. This prevents overwriting an existing tracking cookie with a new URL param from an internal navigation link.

`cookie_type='optional'` means the cookie is subject to GDPR consent banners — it is not set without user consent if the website has a cookie consent banner configured.

#### `_post_dispatch(response)` — Hook

```python
@classmethod
def _post_dispatch(cls, response):
    cls._set_utm(response)
    super()._post_dispatch(response)
```

Called after every Odoo HTTP response, including XHR/fetch requests from the backend. UTM cookies are set even for AJAX calls (e.g., form submissions from the website), ensuring that after a lead form is submitted, the cookies are still persisted for subsequent page loads.

---

## L2 — Field Types, Defaults, Constraints, Indexes

### Index Strategy: `btree_not_null`

```python
campaign_id = fields.Many2one('utm.campaign', index='btree_not_null', ...)
source_id = fields.Many2one('utm.source', index='btree_not_null', ...)
medium_id = fields.Many2one('utm.medium', index='btree_not_null', ...)
```

`btree_not_null` is a PostgreSQL partial index that only indexes non-null values:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS model_camp_idx
ON model USING btree (campaign_id)
WHERE campaign_id IS NOT NULL;
```

This is more compact than a full btree index because many records have no UTM attribution (null values are common in historical data). Queries filtering on non-null UTM fields use the index directly; null-value rows are excluded from the index entirely.

### Default Values

| Model | Field | Default |
|-------|-------|---------|
| `utm.campaign` | `active` | `True` |
| `utm.campaign` | `user_id` | `self.env.uid` |
| `utm.campaign` | `stage_id` | first `utm.stage` record by `sequence` |
| `utm.medium` | `active` | `True` |
| `utm.tag` | `color` | `randint(1, 11)` |
| `utm.stage` | `sequence` | `1` |

### Constraints

| Model | Constraint | Type |
|-------|-----------|------|
| `utm.campaign` | `UNIQUE(name)` | Hard DB constraint |
| `utm.source` | `UNIQUE(name)` | Hard DB constraint (but counter suffixes allow near-unique display) |
| `utm.medium` | `UNIQUE(name)` | Hard DB constraint |
| `utm.tag` | `UNIQUE(name)` | Hard DB constraint (no counter suffix) |
| `utm.source` | `_unlink_except_referral` | `ondelete` guard — prevents deleting `utm_source_referral` |
| `utm.medium` | `_unlink_except_utm_medium_record` | `ondelete` guard — prevents deleting 6 system mediums |

### `ondelete='restrict'` vs `ondelete='cascade'`

`source_id` on `utm.source.mixin` uses `ondelete='restrict'`. If you try to delete a `utm.source` that is still referenced by a mailing or social post, the ORM raises an error rather than silently nullifying the reference.

---

## L3 — Cross-Model, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Model: UTM ↔ Tracked Models

`utm.mixin` is inherited by:

| Module | Model | Purpose |
|--------|-------|---------|
| `crm` | `crm.lead` | Track lead/opportunity origin |
| `sale` | `sale.order` | Track which campaign generated a quote/sale |
| `website_blog` | `blog.post` | Track blog post traffic sources (via `website` module) |
| `website_slides` | `slide.channel` | Track course enrollment sources |
| `event` | `event.registration` | Track event registration sources |
| `survey` | `survey.user_input` | Track survey response sources |
| `website_sale` | `sale.order` (override) | eCommerce order attribution |
| `mass_mailing` | `mailing.mailing` | Uses `utm.source.mixin`, not `utm.mixin` |
| `social` | `social.post` | Uses `utm.source.mixin`, not `utm.mixin` |

**Important:** `mass_mailing.mailing` and `social.social.post` use `utm.source.mixin` (which has a **required** `source_id`) rather than `utm.mixin`. This is because mailings and social posts create their own named UTM sources that are owned by the mailing/post itself.

### Override Pattern: `tracking_fields()`

```python
# In utm.mixin (canonical)
def tracking_fields(self):
    return [
        ('utm_campaign', 'campaign_id', 'odoo_utm_campaign'),
        ('utm_source',   'source_id',   'odoo_utm_source'),
        ('utm_medium',    'medium_id',   'odoo_utm_medium'),
    ]
```

Override to customize URL parameter names:

```python
class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def tracking_fields(self):
        # Add a custom utm_partner parameter
        return super().tracking_fields() + [
            ('utm_partner', 'partner_id', 'odoo_utm_partner'),
        ]
```

**Limitation noted in source:** Because `utm.mixin` is an `AbstractModel`, overriding `tracking_fields()` on a concrete model (e.g., `crm.lead`) will NOT be respected by `default_get()` calls that use `self.env['utm.mixin'].tracking_fields()`. The mixin itself always uses its own definition.

### Override Pattern: `utm.mixin` Inheritance Chain

```python
# Classic _inherit — adds fields to existing model
class CrmLead(models.Model):
    _inherit = 'crm.lead'
    # campaign_id, source_id, medium_id added to crm.lead
```

```python
# Prototype _inherit — creates new combined model (rare for UTM)
class SaleOrderTracked(models.Model):
    _inherit = ['sale.order', 'utm.mixin']
    # Creates a new model with all sale.order fields + UTM fields
```

### Workflow Trigger: URL-Based Attribution

```
1. User clicks: https://site.com/crm/leads/create?utm_source=linkedin&utm_medium=social
2. Browser → GET /crm/leads/create?utm_source=linkedin&...
3. Odoo ir_http._post_dispatch() fires
4. For each param matching tracking_fields():
   - request.cookies.get('odoo_utm_source') == 'linkedin'? No.
   - Write cookie: 'odoo_utm_source=linkedin', max_age=31 days
5. User fills form and submits → POST /crm/leads
6. crm.lead.default_get(['campaign_id', 'source_id', 'medium_id'])
7. request.cookies.get('odoo_utm_source') → 'linkedin'
8. _find_or_create_record('utm.source', 'linkedin') → finds or creates record
9. source_id = <linkedin_record.id>
10. Lead created with source_id set
```

### Workflow Trigger: Cookie Decay

UTM cookies expire after 31 days (`max_age=31 * 24 * 3600`). After the expiry window, a returning visitor's session no longer carries UTM attribution. The original campaign/source/medium can still be looked up via the stored `source_id`/`campaign_id`/`medium_id` on the record.

### Workflow Trigger: Server-Side Assignment

Sales agents can manually set UTM fields on records. Since UTM cookies are not written when `request.params` lacks the URL parameter, a manual assignment does NOT overwrite existing cookies. This allows backfilling attribution from CRM tools or import processes.

### Workflow Trigger: `utm.source.mixin` — Self-Generated Sources

```
1. Marketing creates a Mailng: "Summer Sale 2025"
2. mailing.mailing.create() fires
3. utm.source.mixin.create():
   - No source_id in vals → auto-create utm.source
   - _generate_name() → "Summer Sale 2025 (Mailing created on 2025-01-15)"
   - utm.source record created with that name
   - vals['source_id'] = new_source.id
   - vals.pop('name')  # remove name from mailing vals
4. Mailing created with source_id pointing to its own source
```

### Failure Mode: Cookie Blocked (Safari ITP, Brave, Incognito)

If the browser blocks cookies (e.g., Safari Intelligent Tracking Prevention, Brave shields), the `request.cookies` dict will be empty on the subsequent POST. The `default_get()` returns empty values for all UTM fields. The record is created without UTM attribution. This is silent — no error is raised.

**Mitigation:** For high-value tracking (paid campaigns), use URL parameters directly in the form action or pass them as hidden form fields that persist through the POST without relying on cookies.

### Failure Mode: Salesman Group Bypass

`default_get()` explicitly skips UTM auto-population for users in `sales_team.group_sale_salesman`. This means:

- A salesman filling out a lead form gets **no** auto-populated UTM values.
- But a superuser RPC call (e.g., from a mobile app or integration) DOES get UTM values auto-populated because `self.env.is_superuser()` is `True`.
- A portal user submitting a website form DOES get auto-populated UTM values.

### Failure Mode: `_find_or_create_record` Race Condition

Under high concurrency, two concurrent requests could both execute `search()` and find no record, then both attempt `create()`. The first `create()` succeeds; the second fails with a DB unique constraint violation (`UNIQUE(name)` on `utm.source`/`utm.medium`/`utm.campaign`).

**Mitigation:** The ORM's `create()` wraps in a database savepoint. The second request's `create()` would raise `IntegrityError` and roll back. The client would receive an error response. This is rare in practice for UTM records (the name collision window is milliseconds).

### Failure Mode: Archived Record Found

`_find_or_create_record` uses `with_context(active_test=False)`, so archived records are found. This is intentional — it prevents creating duplicates of archived campaigns. However, if the archived campaign's `stage_id` was deleted, the lead creation could fail because `stage_id` has `ondelete='restrict'`.

**Mitigation:** The default `stage_id` on `utm.campaign` falls back to the first available `utm.stage` record if the target one is deleted. But if ALL stages are deleted (unlikely), campaign creation would fail with a foreign key constraint error.

### Failure Mode: `utm.source.mixin` Required `source_id`

Since `source_id` is `required=True` on `utm.source.mixin`, any model using this mixin cannot have records created without a source. This is a **design choice**: mailings and social posts must always have attribution. However, it means that `_vals.pop('name')` before `super().create()` would cause an error if neither `source_id` nor a name is provided.

---

## L4 — Performance, Odoo 18→19 Changes, Security, Propagation

### Performance

#### N+1 Query Risk on `tracking_fields()` Iteration

`default_get()` calls `tracking_fields()` as a method on every field population. For each of the 3 UTM fields, if the value is a string, it calls `_find_or_create_record()` which does a `search()` followed optionally by `create()`. This is **not an N+1 problem** in the traditional sense — it's at most 3 queries per record creation. The real cost is the `search([('name', '=ilike', ...)])` with `active_test=False`, which must scan the `utm.source`/`utm.medium`/`utm.campaign` tables.

For high-volume form submissions (e.g., thousands of webinar signups per minute), the `utm.source` table can become a hot spot. The `name` field should have a **functional index** for `=ilike` queries, but PostgreSQL's `=ilike` is case-insensitive and cannot use a standard btree index without `citext` extension.

**Optimization in Odoo 19:** The `_tracking_models()` method caches the comodel names set, avoiding repeated `_fields` lookups.

#### `btree_not_null` Index Efficiency

UTM fields on large tables (e.g., `crm.lead` with millions of rows) benefit from `btree_not_null`. Most historical leads have null UTM values. The partial index only stores rows where the field is set, keeping the index small and fast for targeted queries.

```sql
-- Example: Query for leads from a specific campaign
SELECT id, name FROM crm_lead
WHERE campaign_id = 42 AND active = true;
-- Uses: model_camp_idx WHERE campaign_id IS NOT NULL
```

#### `_get_unique_names` and Batch Creation

The `_get_unique_names` method is called with `model_name` and the full `vals_list` names before `super().create()`. It does a single `search_read()` per unique base name (deduplicated set), then assigns counters. This is O(1) database round-trips regardless of batch size.

#### UTM Propagation Through Pipeline

In CRM and Sale, UTM fields do **not** automatically propagate from a lead to the opportunity to the sale order. Each record type independently records its own `source_id`/`medium_id`/`campaign_id`. However:

- **CRM automations** can copy UTM fields from lead to opportunity via server actions.
- **Sale order from CRM** (one22sale pattern): when a sale order is created from a lead, the UTM fields are preserved because the `sale.order` model inherits `utm.mixin` and the conversion process copies field values.
- **Portal lead creation**: `crm.lead` is created via `website_crm_partner_assign` or `crm_livechat`, which triggers `default_get()` with cookies set by the website.

### Odoo 18 → 19 Changes

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| `utm.mixin` | `default_get` checked `request.httprequest` directly | Uses `request.cookies.get()` dict (same behavior, cleaner API) |
| `utm.mixin` | `_tracking_models()` not present | Added — enables `find_or_create_record()` to distinguish UTM models |
| `utm.source.mixin` | Not present | New in Odoo 19 — extracted from `mailing.mailing` logic to be reusable by `social.post` |
| `utm.campaign` | `name` was a plain `Char` with `unique=True` constraint | `name` is now stored-computed with `_compute_name` and `_get_unique_names` for counter suffixes |
| `utm.medium` | `_fetch_or_create_utm_medium` normalized using `re.sub(r"[\s_]")` | Now also normalizes `.` → `_` (e.g., `Google.AdWords` → `utm_medium_google_adwords`) |
| `utm.campaign` | `_group_expand_stage_ids` used `sudo()` | Still uses `sudo()` — Kanban group expansion requires reading all stages regardless of ACL |
| Cookie handling | `_set_utm` set cookies on every matching param | Now checks `request.cookies.get(cookie_name) != request.params[url_parameter]` before writing — avoids redundant cookie writes |
| `_get_unique_names` | Not present in Odoo 18 | Added in Odoo 19 — centralizes counter-based name uniqueness for all UTM models |
| `utm.tag` `color` | Hardcoded random default | Now uses `_default_color()` method — easier to override |

### Security

#### ACL Matrix

| Model | `base.group_user` | `base.group_system` |
|-------|:-----------------:|:-------------------:|
| `utm.campaign` | read, write, create | + unlink |
| `utm.source` | read, write, create | + unlink |
| `utm.medium` | read, write, create | + unlink |
| `utm.stage` | **read only** | full access |
| `utm.tag` | **read only** | full access |

**Key insight:** `utm.stage` and `utm.tag` are read-only for regular employees. This prevents marketing team members from arbitrarily changing campaign stages or adding tags without admin access.

#### Deletion Guards (Soft Security)

The `_unlink_except_*` methods use `@api.ondelete(at_uninstall=False)`. The `at_uninstall=False` parameter means these guards are **active at runtime but bypassed during module uninstall**. This is critical for clean uninstall: when `utm` is uninstalled, the `ondelete` constraints are dropped and records can be deleted without triggering the guard. During normal operation, the guard prevents breaking referential integrity.

#### Access Controls for `utm.mixin` on Tracked Models

When a model like `crm.lead` inherits `utm.mixin`, the UTM fields are subject to the **tracked model's ACL**, not `utm`'s ACL. A user with CRM read access can see UTM fields on leads even if they don't have access to the `utm.campaign` record itself — the `many2one` field displays the campaign name (with read ACL on `utm.campaign`), and the field is readable even if the linked record is inaccessible (displays as a broken Many2one).

#### Portal User Access

Portal users do **not** have access to `utm.campaign`, `utm.source`, or `utm.medium` models by default. When a portal user creates a lead via the website (which triggers `default_get()` with UTM cookies), the UTM fields are populated server-side as the **superuser context** — the portal user's ACL does not block the auto-population because `default_get()` runs with the model's default access rights and the cookie reading is a server-side operation.

#### CSRF and UTM Parameters

UTM URL parameters are **not** CSRF-sensitive. They are passively read from `request.params` and written to cookies. No state modification occurs from the UTM param values themselves. The `_find_or_create_record()` method uses `name.strip()` to sanitize input, preventing injection in the `name` field, and the name is stored as a plain `Char` field without `eval()` or raw SQL.

### Propagation Through Pipeline — Detailed

#### Lead → Opportunity

`crm.lead` converts to `crm.lead`.win and spawns a `sale.order`. The UTM fields are on `crm.lead` itself, not on a related model. When the opportunity is won, the conversion to sale order (via `sale.order.line` from `crm.lead` lines) does **not** automatically copy UTM fields to `sale.order` — the `sale.order` model independently inherits `utm.mixin`, but the conversion action (`action_new_quoted()`) does not call `write({'campaign_id': self.campaign_id.id, ...})`.

**This is the key architectural gap:** UTM attribution can be lost at the lead→opportunity→sale transition unless:
1. A CRM studio automation copies UTM fields from lead to sale order.
2. The salesperson manually copies the UTM values.
3. The `website_sale` module (eCommerce) creates `sale.order` via the website cart, which triggers `default_get()` with fresh cookies — fresh attribution, not carried over from the original lead.

#### `utm.source.mixin` Propagation

Mailing and social posts using `utm.source.mixin` create their own source. When a contact clicks a tracked link in a mailing and fills a form:

1. The click records in the mailing's `link_tracker_click` table (from `link_tracker` module).
2. The contact fills the form → `crm.lead` created with UTM cookies from the mailing click URL.
3. The `source_id` on the lead points to the **campaign's auto-created source**, not the mailing's `utm.source.mixin` source.

The two UTM systems (`utm.mixin` for leads/orders and `utm.source.mixin` for mailings/posts) are **separate attribution chains**. They connect through the campaign (both reference `campaign_id`), but the lead's `source_id` is the campaign's marketing source, not the mailing's own source.

#### Campaign Dashboard Attribution

CRM and Sale reports group by `campaign_id` to show revenue per campaign. The `crm.crm_opportunity_report` (pipeline analysis) and `sale.report` (sales analysis) both have `campaign_id` available for grouping. Because `utm.campaign.is_auto_campaign = True` is set on auto-created campaigns (from `_find_or_create_record`), analysts can filter out automatically generated campaigns vs. deliberately created marketing campaigns.

---

## Default Data

Installed via `data/` files (loaded on module install, `noupdate=1` for sources and mediums):

### Default Mediums (9 records)
`Website`, `Phone`, `Direct`, `Email`, `Banner`, `X`, `Facebook`, `LinkedIn`, `Television`, `Google.AdWords`

### Default Sources (10 records)
`Search engine`, `Lead Recall`, `Newsletter`, `Facebook`, `X`, `LinkedIn`, `Monster`, `Glassdoor`, `Craigslist`, `Referral` (protected from deletion)

### Default Stages
`"New"` (sequence=10) — created in non-demo data to prevent crashes when creating campaigns before stages exist

### Default Tags
`"Marketing"` (color=1)

---

## Test Coverage

**File:** `~/odoo/odoo19/odoo/addons/utm/tests/test_utm.py`

| Test | Coverage |
|------|----------|
| `test_campaign_automatic_name` | `title` → `name` derivation, counter on duplicate title |
| `test_find_or_create_record` | Exact match, creation, duplicate marks ` [2]`, archived record finding |
| `test_fetch_or_create_medium` | Normalization, `ir.model.data` creation, case insensitivity |
| `test_find_or_create_record_case` | Case insensitivity, strip spaces, anchored matching |
| `test_find_or_create_with_archived_record` | `active_test=False` behavior |
| `test_name_generation` | Counter increment, gap filling, ` [0]` handling, batch creation |
| `test_name_generation_duplicate_marks` | Explicit `[2]` respect, `[8]` input, batch with gaps |
| `test_split_name_and_count` | Regex parsing edge cases |

All tests run as `@tagged("utm", "post_install", "-at_install")` — post-install only, not at install time, because UTM models need the full Odoo environment to be fully initialized.
