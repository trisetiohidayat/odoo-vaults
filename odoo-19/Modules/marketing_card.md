---
tags:
  - #odoo19
  - #modules
  - #marketing
  - #card
---

# marketing_card

> Generate shareable promotional image cards from any Odoo record. Cards are rendered using QWeb templates converted to images via wkhtmltoimage, then served at public URLs for social media sharing.

**Module**: `marketing_card` | **Path**: `odoo/addons/marketing_card/` | **Version**: 1.1
**Category**: Marketing/Marketing Card | **Depends**: `mailing`, `link_tracker`, `utm` | **License**: LGPL-3

---

## L1: Core Functionality — How Card Campaigns Generate Shareable Images

The `marketing_card` module enables campaign managers to create shareable promotional image cards from any Odoo record. When a recipient shares the card on social media, the card displays personalized content with the record's dynamic data rendered as a PNG image.

**End-to-end flow:**

```
1. Campaign Manager creates card.campaign
   → Selects target model (res.partner, event.track, event.booth, event.registration)
   → Picks card.template (QWeb HTML layout)
   → Sets target_url (the link being promoted)
   → Configures static or dynamic content fields
   ───────────────────────────────────────────
2. Card per recipient is created and rendered
   → card.campaign._update_cards(domain) is called
   → For each matching record: card.card is created/updated
   → QWeb body_html is rendered with record context
   → Rendered HTML → PNG via wkhtmltoimage (600x315px, 2:1 ratio)
   ───────────────────────────────────────────
3. Mass mailing sends personalized emails
   → Each email embeds the recipient's unique card.jpg URL
   → mail_compose_message._prepare_mail_values_dynamic() rewrites
     generic card URLs to per-recipient card URLs
   ───────────────────────────────────────────
4. Recipient shares on social media
   → Social crawler fetches /cards/<slug>/redirect
   → /cards/<slug>/redirect renders OpenGraph meta tags (og:image, og:title)
   → Social platform displays the card as a preview
   ───────────────────────────────────────────
5. Click tracking
   → card.card.share_status: 'shared' (crawler fetch) or 'visited' (direct fetch)
   → link_tracker records clicks on the redirect URL
```

**Key architectural decision:** Cards are pre-rendered images, not dynamic server-side renders. The QWeb → PNG conversion happens once during `_update_cards()` and the resulting PNG is stored as a `Image` field on `card.card`. This means social media crawlers always get a consistent image, and CDN caching of the static `card.jpg` URL is straightforward.

---

## L2: Field Types, Defaults, Constraints

### `card.campaign` — `models/card_campaign.py`

Inherits: `mail.activity.mixin`, `mail.render.mixin`, `mail.thread`

| Field | Type | Default | Stored | Notes |
|-------|------|---------|--------|-------|
| `name` | Char | — | Yes | Required |
| `active` | Boolean | `True` | Yes | |
| `user_id` | Many2one res.users | `self.env.user` | Yes | Campaign owner |
| `res_model` | Selection | — | Yes | Hardcoded: res.partner, event.track, event.booth, event.registration |
| `preview_record_ref` | Reference | — | Yes | Required; preview target |
| `card_template_id` | Many2one card.template | — | Yes | Required |
| `body_html` | Html (render_engine="qweb") | — | No | Related to card_template_id.body; readonly=False |
| `image_preview` | Image | — | Yes | Computed from preview render |
| `target_url` | Char | — | Yes | The link being promoted |
| `link_tracker_id` | Many2one link.tracker | Auto-created | Yes | Auto-created in `create()` with UTM source |
| `content_background` | Image | — | Yes | Per-campaign background override |
| `content_button` | Char | — | Yes | Button label |
| `content_header` | Char | — | Yes | Static header text |
| `content_sub_header` | Char | — | Yes | Static sub-header |
| `content_header_dyn` | Boolean | `False` | Yes | Toggle: use static or dynamic header |
| `content_header_path` | Char | — | Yes | QWeb path for dynamic header (e.g., `partner_id.name`) |
| `content_header_color` | Char | — | Yes | CSS color for header text |
| `content_section` | Char | — | Yes | Static section label |
| `content_sub_section1` | Char | — | Yes | |
| `content_sub_section1_dyn` | Boolean | `False` | Yes | |
| `content_sub_section1_path` | Char | — | Yes | |
| `content_sub_section2` | Char | — | Yes | |
| `content_sub_section2_dyn` | Boolean | `False` | Yes | |
| `content_sub_section2_path` | Char | — | Yes | |
| `content_image1_path` | Char | — | Yes | QWeb path for dynamic image 1 |
| `content_image2_path` | Char | — | Yes | QWeb path for dynamic image 2 |
| `post_suggestion` | Text | — | Yes | Default social media post text |
| `reward_message` | Html | — | Yes | Shown after sharing |
| `reward_target_url` | Char | — | Yes | Post-share reward link |
| `card_count` | Integer | — | Yes | Computed: active cards |
| `card_click_count` | Integer | — | Yes | Computed: visited + shared cards |
| `card_share_count` | Integer | — | Yes | Computed: shared cards |
| `mailing_ids` | One2many mailing.mailing | — | Yes | Campaigns linked to this card campaign |
| `tag_ids` | Many2many card.campaign.tag | — | Yes | |

**Computed stats fields:**
```python
card_count = fields.Integer(compute='_compute_card_stats')
card_click_count = fields.Integer(compute='_compute_card_stats')  # 'visited' + 'shared'
card_share_count = fields.Integer(compute='_compute_card_stats')  # 'shared' only
```

**Constraint — unique campaign+record pair:**
```python
_models.Constraint(
    'unique(campaign_id, res_id)',
    'Each record should be unique for a campaign',
)
```

### `card.card` — `models/card_card.py`

| Field | Type | Default | Stored | Notes |
|-------|------|---------|--------|-------|
| `active` | Boolean | `True` | Yes | Soft delete; preview cards are set inactive |
| `campaign_id` | Many2one card.campaign | — | Yes | Cascade delete |
| `res_model` | Selection | related campaign | No | Computed from campaign |
| `res_id` | Many2oneReference | — | Yes | Record ID; model_field='res_model' |
| `image` | Image | — | Yes | Rendered PNG |
| `requires_sync` | Boolean | `True` | Yes | `True` = needs re-rendering |
| `share_status` | Selection | — | Yes | `shared` (crawler) / `visited` (user) |

**SQL constraint:** `unique(campaign_id, res_id)` — one card per record per campaign.

**URL methods:**
```python
def _get_card_url(self):      # → /cards/<slug>/card.jpg
def _get_redirect_url(self):  # → /cards/<slug>/redirect
def _get_path(self, suffix):  # → /cards/<slug>/<suffix>
    return f'{self.get_base_url()}/cards/{self.env["ir.http"]._slug(self)}/{suffix}'
```

**Garbage collection:**
```python
@api.autovacuum
def _gc_card(self):
    timedelta_days = self.env['ir.config_parameter'].sudo().get_param(
        'marketing_card.card_image_cleanup_interval_days', 60
    )
    if not timedelta_days:
        return
    self.with_context({"active_test": False}).search([
        ('write_date', '<=', datetime.now() - timedelta(days=int(timedelta_days)))
    ]).unlink()
```

Cards default to 60-day retention. Social platforms cache card images, so deleting after 60 days is safe — by then the card has been fetched by social crawlers or is no longer relevant.

### `card.template` — `models/card_template.py`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | Char (translate) | Required | |
| `default_background` | Image | — | Fallback background |
| `body` | Html | — | QWeb template; `sanitize_tags=False`, `sanitize_attributes=False` |
| `primary_color` | Char | `#f9f9f9` | |
| `secondary_color` | Char | `#000000` | |
| `primary_text_color` | Char | `#000000` | |
| `secondary_text_color` | Char | `#ffffff` | |

**Design constants:**
```python
TEMPLATE_DIMENSIONS = (600, 315)  # Twitter/Facebook recommended size
TEMPLATE_RATIO = 40 / 21          # ~1.905:1 ratio
```

**Why `sanitize_tags=False` and `sanitize_attributes=False`?** The template body uses `t-out`, `t-attf`, and `t-if` QWeb directives extensively. Full HTML sanitization would strip these template tags. The field is intentionally unsanitized, but access is restricted to `marketing_card_group_manager` (see L4 Security).

### `mailing.mailing` (Extended) — `models/mailing_mailing.py`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `card_campaign_id` | Many2one card.campaign | — | Index: `btree_not_null` |
| `mailing_model_id` | Many2one ir.model | Compute | Required for card campaigns |
| `card_requires_sync_count` | Integer | Compute | Cards needing re-render |

**Constraint:** `_check_mailing_domain` — `mailing_model_id` must match `card_campaign_id.res_model`. This prevents sending a card campaign to the wrong model (e.g., sending event.registration cards to a mailing targeting `res.partner`).

**Guard in `action_put_in_queue()` and `action_send_mail()`:** Raises `UserError` if `card_requires_sync_count > 0`. All cards must be rendered before sending.

---

## L3: Cross-Model Relationships, Override Patterns, Workflow Triggers

### Cross-Model Dependency Graph

```
mailing.mailing (mass_mailing)
    ├── card_campaign_id → card.campaign
    │       └── card_template_id → card.template
    │       └── link_tracker_id → link.tracker
    │               └── utm_source → utm.source (utm_source_marketing_card)
    │
    └── card.card (1:1 per recipient)
            ├── campaign_id → card.campaign
            └── res_id → res.partner / event.track / event.booth / event.registration

mailing.mailing._get_recipients_domain()
    └── Extends super() to filter domain to only res_ids with existing card.card records

mail_compose_message (mail)
    └── _prepare_mail_values_dynamic() → rewrites generic card URLs to per-recipient URLs

card.campaign
    └── Inherits: mail.activity.mixin (activity scheduling)
    └── Inherits: mail.render.mixin (QWeb rendering)
    └── Inherits: mail.thread (chatter, message_follower_ids)
```

### `mailing.mailing._get_recipients_domain()` — Extension

```python
def _get_recipients_domain(self):
    domain = super()._get_recipients_domain()
    if self.card_campaign_id:
        res_ids = self.env['card.card'].search_fetch(
            [('campaign_id', '=', self.card_campaign_id.id)], ['res_id']
        ).mapped('res_id')
        domain &= Domain('id', 'in', res_ids)  # Only records with cards
    return domain
```

This filters the mailing's recipient domain to only include records that have a corresponding `card.card`. Without this filter, a mailing targeting 100 partners would fail for any partner that lacks a card — even after `action_update_cards()` is called.

### `mail_compose_message` Wizard — `wizards/mail_compose_message.py`

The wizard extends `mail.compose.message` to handle per-recipient card URLs in outgoing emails.

**Two key override methods:**

**`_prepare_mail_values_dynamic()`** — Replaces generic card template URLs with per-recipient card URLs:
```python
def _prepare_mail_values_dynamic(self, res_ids):
    mail_values_all = super()._prepare_mail_values_dynamic(res_ids)
    if campaign := self.mass_mailing_id.card_campaign_id:
        card_from_res_id = self.env['card.card'].search_fetch(
            [('campaign_id', '=', campaign.id), ('res_id', 'in', res_ids)],
            ['res_id'],
        ).grouped('res_id')

        processed_bodies = self._process_generic_card_url_body([
            (card_from_res_id[res_id], mail_values.get('body_html'))
            for res_id, mail_values in mail_values_all.items()
        ])
        for mail_values, body in zip(mail_values_all.values(), processed_bodies):
            if body is not None:
                mail_values['body'] = body
                mail_values['body_html'] = body
    return mail_values_all
```

**`_process_generic_card_url_body(card_body_pairs)`** — Static regex substitution using `Markup`:
```python
# Generic:  src=".../web/image/card.campaign/<id>/image_preview"
# Per-card: src="/cards/<slug>/card.jpg"

CARD_IMAGE_URL = re.compile(r'src=".*?/web/image/card.campaign/[0-9]+/image_preview"')
CARD_PREVIEW_URL = re.compile(r'href=".*?/cards/[0-9]+/preview"')

def _process_generic_card_url_body(self, card_body_pairs):
    for card, body in card_body_pairs:
        if body:
            body = re.sub(CARD_IMAGE_URL, lambda m: f'src="{card._get_path("card.jpg")}"', body)
            body = re.sub(CARD_PREVIEW_URL, lambda m: f'href="{card._get_path("preview")}"', body)
    return bodies
```

The regex patterns target only the generic `card.campaign/<id>/image_preview` URL (used for the campaign preview) and the `cards/<id>/preview` link. They do not affect other images or links in the email body.

**`_get_done_emails()` override:**
```python
def _get_done_emails(self, mail_values_dict):
    if self.mass_mailing_id.card_campaign_id:
        return []  # No deduplication — every recipient gets their own card
    return super()._get_done_emails(mail_values_dict)
```

This disables the mailing's deduplication logic. Normally `mailing.mailing` tracks which email addresses have already received a mailing to avoid sending duplicates. For card campaigns, each recipient has a unique card, so deduplication would incorrectly skip valid recipients who share an email with another target.

### `_update_cards()` — Batch Rendering Pipeline

```python
def _update_cards(self, domain, auto_commit=False):
    TargetModel = self.env[self.res_model]
    res_ids = TargetModel.search(domain).ids
    cards = self.env['card.card'].with_context(active_test=False).search_fetch([
        ('campaign_id', '=', self.id), ('res_id', 'in', res_ids)
    ], ['res_id', 'requires_sync'])
    cards.active = True

    # Create missing cards
    self.env['card.card'].create([
        {'campaign_id': self.id, 'res_id': res_id}
        for res_id in set(res_ids) - set(cards.mapped('res_id'))
    ])

    # Render in batches of 100 with periodic commits
    while cards := self.env['card.card'].search_fetch([
        ('requires_sync', '=', True), ('campaign_id', '=', self.id), ('res_id', 'in', res_ids)
    ], ['res_id'], limit=100):
        if auto_commit and updated_cards:
            self.env.cr.commit()
            self.env['card.card'].invalidate_model(['image'])
        for card in cards.filtered('requires_sync'):
            card.write({
                'image': self._get_image_b64(TargetModel.with_prefetch(cards.mapped('res_id')).browse(card.res_id)),
                'requires_sync': False,
                'active': True,
            })
        updated_cards += cards
    return updated_cards
```

**Batch size: 100.** Large campaigns (thousands of records) would otherwise exhaust memory. Each batch commits to the database and invalidates the ORM cache so the next batch starts fresh.

**`active` reset on preview:** When a campaign manager previews a card (`action_preview()`), that card's `active` is set to `False` so it doesn't count in the mailing's recipient domain. After `action_update_cards()`, it is set back to `True`.

### Controller Routes — `controllers/marketing_card.py`

Three public HTTP routes (all `auth='public'`, `sitemap=False`):

| Route | Auth | Purpose |
|-------|------|---------|
| `/cards/<slug>/card.jpg` | public | Serve JPEG image |
| `/cards/<slug>/preview` | public | Render preview HTML page |
| `/cards/<slug>/redirect` | public | Redirect to target_url, or render OpenGraph for crawlers |

**Crawler detection:**
```python
SOCIAL_NETWORK_USER_AGENTS = (
    'Facebot', 'facebookexternalhit',  # Facebook
    'Twitterbot',                      # Twitter/X
    'LinkedInBot',                    # LinkedIn
    'WhatsApp',                       # WhatsApp
    'Pinterest', 'Pinterestbot',      # Pinterest
)

def _is_crawler(request):
    return any(ua in request.httprequest.user_agent.string for ua in SOCIAL_NETWORK_USER_AGENTS)
```

**Redirect behavior:**
```
Human visits /cards/<slug>/redirect
    → 303 redirect to link_tracker.short_url (or target_url fallback)

Social crawler visits /cards/<slug>/redirect
    → 200 with OpenGraph HTML:
      <meta property="og:image" content="/cards/<slug>/card.jpg">
      <meta property="og:title" content="<post_suggestion>">
      <meta property="og:description" content="<display_name>">
```

**Image route behavior:**
```
Social crawler fetches /cards/<slug>/card.jpg
    → share_status set to 'shared' (counts as a social share)

Human fetches /cards/<slug>/card.jpg
    → share_status set to 'visited'
```

### Override Patterns

| Model | Pattern | What it adds |
|-------|---------|-------------|
| `card.campaign` | Triple mixin | `mail.activity.mixin` + `mail.render.mixin` + `mail.thread` |
| `mailing.mailing` | Classical `_inherit = 'mailing.mailing'` | Fields + domain override + send guards |
| `mail.compose.message` | Classical `_inherit = 'mail.compose.message'` | URL rewriting for per-recipient cards |
| `utm.source` | Classical `_inherit = 'utm.source'` | Deletion protection for `utm_source_marketing_card` |
| `ir.model` | Classical `_inherit = 'ir.model'` | Cascade-delete campaigns when model is uninstalled |

### Workflow Triggers

| Trigger | Action | Description |
|---------|--------|-------------|
| `card.campaign` created | `create()` | Auto-creates `link.tracker` with UTM source |
| `card.campaign` written | `write()` | Sets `requires_sync=True` on all linked cards |
| `preview_record_ref` changed | `_compute_image_preview` | Re-renders preview image |
| `action_update_cards()` | `_update_cards()` | Batch-creates cards and renders images |
| `action_launch()` (mailing) | `_check_mailing_domain` | Validates model match + all cards synced |
| `mailing.mailing` sent | `_prepare_mail_values_dynamic` | Rewrites generic URLs to per-recipient URLs |
| Cron / autovacuum | `_gc_card()` | Deletes old card records |

---

## L4: Version Odoo 18→19 Changes, Security Analysis, Deep Design

### Version Odoo 18 → Odoo 19 Changes

**No breaking changes** between Odoo 18 and Odoo 19 for `marketing_card`. The module was introduced in Odoo 16 as a new feature and has remained structurally stable through versions 17, 18, and 19.

Key elements that remain unchanged:
- The four allowed target models (`res.partner`, `event.track`, `event.booth`, `event.registration`) — no new models were added in Odoo 19
- The `card.campaign` model structure with `mail.render.mixin` inheritance
- The `card.card` SQL constraint `unique(campaign_id, res_id)`
- The batch size of 100 in `_update_cards()`
- The 60-day garbage collection default
- The template dimensions `600x315`
- The `_check_mailing_domain` constraint checking model match
- The `card_requires_sync_count` gating mechanism

What changed in Odoo 19 core dependencies that indirectly affect `marketing_card`:
- `mailing.mailing._get_recipients_domain()` in Odoo 19 may have changed internal behavior — the `marketing_card` override correctly re-fetches the filtered domain from scratch rather than relying on super() internals
- Odoo 19's `mail.render.mixin` uses `render_engine="qweb"` (already used in Odoo 18) — no migration needed

### Security Analysis

#### Field Access Control on Dynamic Paths

The most significant security concern is the `content_*_path` fields that allow campaign managers to specify QWeb field paths into arbitrary records. These paths could potentially access fields the manager should not see.

**Mitigation layers:**

1. **`_check_access_right_dynamic_template()` override:**
   `mail.render.mixin` normally renders template fields using `sudo()` to avoid ACL issues. `marketing_card` overrides this to run as the **current user**, enforcing standard record rules during rendering:
   ```python
   def _check_access_right_dynamic_template(self):
       # Render as current user, not superuser
       return self.env[self.res_model].check_access_rights('read', raise_exception=False)
   ```

2. **`test_campaign_field_paths` test:** Creates a `res.country.state` record with a restrictive `ir.rule` that only allows system users to read it. Verifies that:
   - A marketing card user **can** render accessible fields
   - A marketing card user **cannot** render fields restricted by `ir.rule`
   - Only a `system_admin` user can render restricted fields
   - The `_get_image_b64` call for restricted records produces **no render output** (silently fails)

3. **`body_html` write protection:** `body_html` is defined as a related field to `card_template_id.body` with `readonly=False`. The `_unrestricted_rendering = True` flag on the render engine would normally allow any user to write to it. `marketing_card` overrides `_check_access_right_dynamic_template` to prevent this:
   ```python
   # Asserts that all render_engine fields are related to card.template (not stored on campaign),
   # not stored on the campaign itself, and readonly=False only because they are template-related.
   # If one render field doesn't fulfil this, the _unrestricted_rendering = True must be
   # reconsidered.
   self.assertTrue(all(
       field.related_field.model_name == 'card.template'
       and not field.store
       and not field.readonly  # readonly=False here means "template-related"
       for field in CardCampaign._fields.values() if hasattr(field, 'render_engine')
   ))
   ```

4. **Manager cannot write to `card.template`:** `card_template_id.has_access('write')` returns `False` for `marketing_card_group_manager`. Managers can assign any template to a campaign but cannot modify template QWeb bodies. This prevents template injection.

#### SQL Injection and Path Traversal

- **`content_*_path` fields:** These are used as QWeb `t-out` attribute paths (e.g., `t-out="record.field_id.name"`). The path is injected into a QWeb rendering context, not directly into SQL. QWeb uses a sandboxed evaluation environment — arbitrary Python cannot be executed. The path traversal is bounded to the record's fields.
- **`res_id` on `card.card`:** Stored as an integer via `Many2oneReference`. No string interpolation into domains.
- **URL slugs:** Cards are accessed by slug (`ir.http._slug()`) or integer ID. The `_get_card_from_url()` helper normalizes slugs and raises `BadRequest()` for invalid IDs. The card is `exists()`-checked before use.

#### ACL Groups

| Group | Access |
|-------|--------|
| `marketing_card.marketing_card_group_manager` | Full CRUD on campaigns, templates, cards |
| `marketing_card.marketing_card_group_user` | Read campaigns; create campaigns; edit own campaigns |
| Public (unauthenticated) | Read card.jpg, preview, redirect routes |

The public routes are intentionally unauthenticated because social media crawlers must be able to fetch card images without session cookies. Rate limiting at the web server level is recommended for production deployments.

#### CSRF on Public Routes

All three public routes use `sitemap=False` and `website=True`. Odoo's CSRF protection is disabled for `website=True` routes. This is correct: the routes are designed to be fetched by external crawlers that will not have Odoo's CSRF tokens.

### QWeb Rendering Internals

**Template rendering pipeline:**
```
1. card.campaign._get_image_b64(record)
       ↓
2. card.campaign._render_field('body_html', record.ids, add_context={'card_campaign': self})
       ↓ (via mail.render.mixin)
3. QWeb engine evaluates body_html with context:
     - object = record (the target Odoo record)
     - card_campaign = self (the campaign)
     - values = card_campaign._get_card_element_values(record)
       ↓
4. QWeb produces HTML string
       ↓
5. ir.actions.report._run_wkhtmltoimage([html_string], 600, 315, 'jpg')
       ↓
6. Binary PNG returned → base64.b64encode → stored in card.card.image
```

**`_get_card_element_values(record)` — Dynamic field resolution:**

```python
def _get_card_element_values(self, record):
    result = {}
    # Image fields: read raw bytes from the path
    for key, path in [('image1', content_image1_path), ('image2', content_image2_path)]:
        if path:
            field_model, field_name = path.rsplit('.', 1)
            target = record if field_model == record._name else record[field_model]
            result[key] = base64.b64encode(target[field_name]) if target[field_name] else False

    # Text fields: resolve path or use static value
    for text_key in ['header', 'sub_header', 'section', 'sub_section1', 'sub_section2']:
        dyn_enabled = getattr(self, f'content_{text_key}_dyn')
        dyn_path = getattr(self, f'content_{text_key}_path', False)
        if dyn_enabled and dyn_path:
            result[text_key] = self._get_card_render_value(record, dyn_path)
        else:
            result[text_key] = getattr(self, f'content_{text_key}', False)

    # DateTime fields: translate to user's or record's timezone
    # (test_fetch_datetime verifies Europe/Brussels shows +2h, Asia/Tokyo shows +9h)
    return result
```

**`_get_card_render_value(record, path)` — Security boundary:**

The method uses `record.env.sudo(record)` to read the target record with elevated privileges for following the path. However, `_check_access_right_dynamic_template` ensures the **current user** has at least read access to `res_model` before any sudo'd rendering occurs.

### Cross-Module Dependency Deep Dive

```
marketing_card
    ├── mailing (mass_mailing)
    │       mailing.mailing — extended with card_campaign_id, card_requires_sync_count
    │       mailing.trace — automatically created when card campaign is sent
    │       mail.compose.message — wizard extended for per-recipient card URLs
    │       mail.render.mixin — used for QWeb rendering (overridden security)
    │
    ├── link_tracker
    │       link_tracker — auto-created per campaign
    │       link_tracker.click — records redirects (target_url clicks)
    │
    ├── utm
    │       utm.source — protected: utm_source_marketing_card cannot be deleted
    │       utm.campaign — not directly used
    │
    └── website
            ir.http — _slug() for card URLs
            /cards/<slug>/card.jpg — public image route
            /cards/<slug>/preview — public preview route
            /cards/<slug>/redirect — public redirect/OpenGraph route
```

**Why `utm` is required, not optional:** Every `link_tracker` created by the campaign automatically assigns `utm_source_marketing_card`. This UTM source lets marketing analytics attribute all card-driven traffic to the marketing card module. If `utm` were not a dependency, traffic from card links would appear as "direct" in analytics.

### Extension Points for Custom Implementations

1. **Add a new supported model:**
   Override `_get_model_selection()` in a custom module:
   ```python
   def _get_model_selection(self):
       selection = super()._get_model_selection()
       selection.append(('crm.lead', 'Lead'))
       return selection
   ```
   Then override `_get_card_element_values()` to provide field paths relevant to that model.

2. **Custom card dimensions:**
   Override `TEMPLATE_DIMENSIONS` in `card.template`:
   ```python
   # In custom module
   CARD_TEMPLATE = self.env['card.template'].browse(template_id)
   width, height = 1200, 630  # LinkedIn recommended
   ```

3. **Override rendering to use a different image service:**
   Override `_get_image_b64()` to call an external image rendering API instead of wkhtmltoimage.

4. **Disable garbage collection:**
   Set `marketing_card.card_image_cleanup_interval_days = 0` via `ir.config_parameter`. Useful during testing or when card images need indefinite retention.

### Performance Considerations

- **Prefetching in batch rendering:** `_update_cards()` uses `TargetModel.with_prefetch(cards.mapped('res_id'))` to batch-fetch target records in a single query, then browses individual records for each card. This avoids N individual record fetches.
- **Image storage:** Card images are stored as `Image` (base64) in the database. Each 600x315 JPEG is typically 15-50 KB. A campaign with 10,000 recipients stores 150-500 MB of image data. Consider compressing images or storing only a URL reference in high-volume deployments.
- **No CDN configuration:** The module serves images directly from the Odoo server. High-traffic card campaigns may benefit from a reverse proxy caching `/cards/*/card.jpg`.
- **Query count in `test_campaign_send_mailing`:** 54 queries for sending 5 personalized emails — acceptable for a transactional email flow.

---

## Data Flow

```
Campaign Manager creates card campaign
        │
        ▼
  Selects model (e.g., event.registration)
  Chooses card template and target URL
        │
        ▼
  Configures dynamic fields (e.g., partner_id.name as header)
        │
        ▼
  Creates or schedules mass mailing
        │
        ▼
  Before sending: action_update_cards()
  ─ Creates card.card for each recipient ──────────►
  ─ Renders QWeb template → PNG via wkhtmltoimage ─►
        │
        ▼
  Mailing sent with card image embedded
  (mail_compose_message rewrites generic → per-recipient URLs)
        │
        ▼
  Recipients share on social media
  Social platform fetches /cards/<slug>/redirect (OpenGraph)
  Social platform fetches /cards/<slug>/card.jpg (image)
        │
        ▼
  link_tracker records click → card_share_count / card_click_count
```

---

## Key Technical Patterns

### QWeb Rendering with Dynamic Fields

The card campaign uses `mail.render.mixin` to render QWeb templates. Dynamic field values are injected via rendering context:

```python
self._render_field('body_html', record.ids, add_context={'card_campaign': self})[record.id]
```

The template accesses `card_campaign.content_header`, etc., and resolves dynamic paths via `_get_card_element_values()`.

### Link Tracking

Every campaign auto-creates a `link.tracker` record with a UTM source `marketing_card.utm_source_marketing_card`:

```python
def create(self, vals_list):
    utm_source = self.env.ref('marketing_card.utm_source_marketing_card', raise_if_not_found=False)
    link_trackers = self.env['link.tracker'].sudo().create([{
        'url': vals.get('target_url') or self.env['card.campaign'].get_base_url(),
        'title': vals['name'],
        'source_id': utm_source.id if utm_source else None,
        ...  # campaign_id, medium_id set via vals
    } for vals in vals_list])
    return super().create([{**vals, 'link_tracker_id': lt}
                          for vals, lt in zip(vals_list, link_trackers)])
```

### Protected UTM Source

```python
def _unlink_except_utm_source_marketing_card(self):
    utm_source = self.env.ref('marketing_card.utm_source_marketing_card', raise_if_not_found=False)
    if utm_source and utm_source in self:
        raise exceptions.UserError(_(
            "The UTM source '%s' cannot be deleted as it is used to promote marketing cards campaigns."
        ))
```

---

## Related Documentation

- [Modules/Mail](Modules/Mail.md) — Mailing and email management
- [Modules/mass_mailing](Modules/mass_mailing.md) — Mass mailing features
- [Core/API](Core/API.md) — QWeb rendering, mail.render.mixin
- [Modules/link_tracker](Modules/link_tracker.md) — Click tracking, UTM sources
