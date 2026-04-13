---
Module: marketing_card
Version: 18.0
Type: addon
Tags: #marketing_card, #mass_mailing, #website, #social
---

# marketing_card — Dynamic Shareable Marketing Cards

> Generate dynamic shareable cards for social media campaigns. Creates per-record card images (Facebook/Twitter/LinkedIn/OpenGraph) driven by a `mailing.mailing` campaign.

## Module Overview

| Property | Value |
|---|---|
| Category | Marketing/Social Marketing |
| Version | 1.1 |
| Depends | `link_tracker`, `mass_mailing`, `website` |
| Application | Yes |
| License | LGPL-3 |

## What It Extends

- `mail.mailing` / `mailing.mailing` — card campaign binding, per-recipient card URL injection
- `utm.source` — prevents deletion of the internal marketing card UTM source
- `ir.model` — cascades deletion to campaigns when models are uninstalled
- `mail.compose.message` wizard — replaces generic card URLs with per-recipient card URLs
- Website controller — serves card images, previews, and crawler redirects

## Models

### `card.campaign` — Marketing Card Campaign

Inherits: `mail.activity.mixin`, `mail.render.mixin`, `mail.thread`

The central record. Defines a card template, target model, content fields, and manages card generation.

```python
class CardCampaign(models.Model):
    _name = 'card.campaign'
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `name` | Char (required) | Campaign name |
| `active` | Boolean | Active state (default True) |
| `res_model` | Selection (readonly, store) | Target model — hardcoded to `res.partner`, `event.track`, `event.booth`, `event.registration` |
| `card_template_id` | Many2one → `card.template` | Design template |
| `body_html` | Html (related, render_engine="qweb") | QWeb template body |
| `image_preview` | Image (compute, sudo, store) | Preview of the rendered card |
| `link_tracker_id` | Many2one → `link.tracker` | Auto-created link tracker for `target_url` |
| `target_url` | Char | The post/link URL shared by the card |
| `target_url_click_count` | Integer (related `link_tracker_id.count`) | Click count |
| `post_suggestion` | Text | Description below the card + default X/Twitter text |
| `preview_record_ref` | Reference (selection `_get_model_selection`) | Record used for live preview |
| `user_id` | Many2one → `res.users` | Responsible user |
| `tag_ids` | Many2many → `card.campaign.tag` | Campaign tags |
| `mailing_ids` | One2many → `mailing.mailing` | Linked mailings |
| `mailing_count` | Integer (compute) | Number of linked mailings |
| `card_ids` | One2many → `card.card` | Cards generated for this campaign |
| `card_count` | Integer (compute) | Total cards |
| `card_click_count` | Integer (compute) | Cards with share_status in (shared, visited) |
| `card_share_count` | Integer (compute) | Cards with share_status = shared |
| `reward_message` | Html | Thank-you message shown after card click |
| `reward_target_url` | Char | Reward link after card click |
| `request_title` | Char | Request CTA text (default: "Help us share the news") |
| `request_description` | Text | Description of the share request |
| `content_background` | Image | Static background image |
| `content_button` | Char | Button label |
| `content_header` / `_dyn` / `_path` / `_color` | Char / Boolean / Char / Char | Dynamic header configuration |
| `content_sub_header` / `_dyn` / `_path` / `_color` | Char / Boolean / Char / Char | Dynamic sub-header configuration |
| `content_section` / `_dyn` / `_path` | Char / Boolean / Char | Dynamic section configuration |
| `content_sub_section1` / `_dyn` / `_path` | Char / Boolean / Char | Dynamic sub-section 1 |
| `content_sub_section2` / `_dyn` / `_path` | Char / Boolean / Char | Dynamic sub-section 2 |
| `content_image1_path` / `content_image2_path` | Char | Dynamic image field paths |

**Key Methods:**

- `_get_render_fields()` → returns all render-related field names for cache invalidation
- `_check_access_right_dynamic_template()` → bypasses the `group_mail_template_editor` check (security delegated to `card.template`)
- `_compute_image_preview()` → renders `body_html` via wkhtmltoimage at 600x315 into `image_preview`
- `_get_image_b64(record)` → renders card HTML to base64 JPEG using `ir.actions.report._run_wkhtmltoimage`
- `_update_cards(domain, auto_commit=False)` → creates missing `card.card` records and re-renders stale ones in batches of 100
- `_get_card_element_values(record)` → resolves dynamic field values (text, images, dates with timezone) for rendering
- `_fetch_or_create_preview_card()` → gets or creates a non-active preview card
- `_action_share_get_default_body()` → generates default mail body HTML with card snippet
- `create()` → auto-creates a `link.tracker` with the campaign UTM source
- `write()` → marks existing cards as `requires_sync` when render fields change; prevents model change if cards exist

**Actions:**

- `action_view_cards()` → opens card list filtered to this campaign
- `action_view_cards_clicked()` → opens card list with `filter_visited` default
- `action_view_cards_shared()` → opens card list with `filter_shared` default
- `action_view_mailings()` → opens linked mailings
- `action_preview()` → opens card preview in new tab
- `action_share()` → opens mailing.mailing form pre-filled with card campaign

---

### `card.card` — Individual Marketing Card

```python
class MarketingCard(models.Model):
    _name = 'card.card'
    _description = 'Marketing Card'
```

One card per `(campaign_id, res_id)` pair.

**Fields:**

| Field | Type | Description |
|---|---|---|
| `campaign_id` | Many2one → `card.campaign` (required) | Parent campaign |
| `res_model` | Selection (related, compute) | Target model (computed from campaign, frozen once set) |
| `res_id` | Many2oneReference | ID of the target record |
| `image` | Image | Rendered JPEG card image |
| `requires_sync` | Boolean | Whether the image needs re-rendering (default True on create) |
| `share_status` | Selection(`shared`, `visited`) | Tracking state |
| `active` | Boolean | Active state (default True) |

**SQL Constraints:** `unique(campaign_id, res_id)`

**Key Methods:**

- `_compute_display_name()` → display name = target record's `display_name`
- `_compute_res_model()` → freezes `res_model` from campaign on first write
- `_gc_card()` → `@api.autovacuum` — deletes cards older than `marketing_card.card_image_cleanup_interval_days` (default 60 days)
- `_get_card_url()` → `/cards/{id}/card.jpg`
- `_get_redirect_url()` → `/cards/{id}/redirect`
- `_get_path(suffix)` → builds full URL: `{base_url}/cards/{slug}/{suffix}`

---

### `card.template` — Card Design Template

```python
class CardCampaignTemplate(models.Model):
    _name = 'card.template'
    _description = 'Marketing Card Template'
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `name` | Char (required) | Template name |
| `default_background` | Image | Default background |
| `body` | Html (sanitize_tags=False, sanitize_attributes=False) | QWeb template body |
| `primary_color` / `secondary_color` | Char (defaults `#f9f9f9` / `#000000`) | Background colors |
| `primary_text_color` / `secondary_text_color` | Char (defaults `#000000` / `#ffffff`) | Text colors |

Template dimensions: **600 x 315 px** (2:1 ratio, Twitter/Meta recommended).

---

### `card.campaign.tag` — Campaign Tags

```python
class CardCampaignTag(models.Model):
    _name = 'card.campaign.tag'
```

**Fields:** `name` (required, unique), `color` (Integer, random 1–11)

---

### Extensions

**`mailing.mailing`** (`_inherit = 'mailing.mailing'`):

| Field | Type | Description |
|---|---|---|
| `card_campaign_id` | Many2one → `card.campaign` | Linked card campaign |
| `card_requires_sync_count` | Integer (compute) | Cards needing sync before send |

- `_check_mailing_domain()` → `@constrains` — card campaign model must match mailing target model
- `action_put_in_queue()` / `action_send_mail()` → blocks if `card_requires_sync_count > 0`
- `action_update_cards()` → batch-updates cards via `campaign._update_cards()`
- `_get_recipients_domain()` → adds `res_id IN existing_card_res_ids` filter so mailings only target records with cards

**`utm.source`** extension: prevents deletion of `utm_source_marketing_card` via `@api.ondelete(at_uninstall=False)`.

**`ir.model`** extension: cascades `@api.ondelete(at_uninstall=False)` to delete `card.campaign` records when their model is removed.

---

## Wizard: `mail.compose.message`

Extends the standard mail composer to replace generic card URLs with per-recipient card URLs before sending.

- `_prepare_mail_values_dynamic(res_ids)` → calls super then for each mail replaces generic `/web/image/card.campaign/N/image_preview` src and `/cards/N/preview` href with card-specific `card._get_path('card.jpg')` and `card._get_path('preview')`
- `_get_done_emails()` → returns empty list for card mailings (each recipient gets a different card image, so no deduplication)
- `_process_generic_card_url_body(card_body_pairs)` → regex substitution of generic URLs per card

---

## Website Controller Routes

### `GET /cards/<card_slug>/card.jpg` and `/cards/<int:card_id>/card.jpg`

- Auth: public
- Sets `share_status = 'shared'` if crawler
- Serves card JPEG image

### `GET /cards/<card_slug>/preview` and `/cards/<int:card_id>/preview`

- Auth: public
- Sets `share_status = 'visited'` if not already set
- Renders `marketing_card.card_campaign_preview` QWeb template

### `GET /cards/<card_slug>/redirect` and `/cards/<int:card_id>/redirect`

- Auth: public
- **Crawler behavior:** renders `marketing_card.card_campaign_crawler` (OpenGraph tags with card image + `post_suggestion`)
- **Normal behavior:** redirects to `campaign.link_tracker_id.short_url` or `campaign.target_url`

---

## Security

- `security/marketing_card_groups.xml` — access rights for card models
- `security/ir.model.access.csv` — ACL for `card.campaign`, `card.card`, `card.template`, `card.campaign.tag`
- `mail.render.mixin._unrestricted_rendering = True` — rendering bypasses standard template editor checks; access controlled via `card.template` (admin-only)

## See Also

- [Modules/Mass Mailing](Modules/Mass-Mailing.md) — `mass_mailing` base
- [Modules/Website](Modules/Website.md) — `website` base
- [Modules/Link Tracker](Modules/Link-Tracker.md) — `link_tracker` for short URLs
- [New Features/What's New](New-Features/What's-New.md) — Odoo 18 marketing_card changes
