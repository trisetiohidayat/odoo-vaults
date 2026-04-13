# website_profile

> Public user profiles on the website frontend: karma, badges, ranks, reputation, and leaderboard.

**Module**: `website_profile`
**Category**: `Website/Website`
**Depends**: `html_editor`, `website_partner`, `gamification`
**Author**: Odoo S.A.
**License**: LGPL-3
**Version**: 1.0

---

## Overview

The `website_profile` module exposes `res.users` as public-facing profile pages on the website. It layers gamification primitives (karma, badges, ranks, tracking) from `gamification` onto the web-facing side. A user must validate their email before earning karma (initial grant: 3 points). Profiles are gated by `website_published` and a per-website karma threshold (`karma_profile_min`, default 150).

### Dependency Chain

```
website_profile
  ├── gamification          # gamification.badge, gamification.karma.rank, res.users karma fields
  ├── website_partner       # res.partner.website_description field
  ├── html_editor           # Rich-text editing of website_description
  └── website               # website.published.mixin, website model, pager, layout
```

---

## Models

### `res.users` — Extended

> File: `models/res_users.py`

The module extends `res.users` to add profile-specific method overrides for self-access fields, plus email validation and karma initialization.

#### Field Access Overrides

**`SELF_READABLE_FIELDS`** — `property`, returns `super() + ['karma']`
- Adds `karma` to the set of fields the authenticated user can read on their own record via `_is_user()` access rules. Without this, portal users would not be able to read their own karma.

**`SELF_WRITEABLE_FIELDS`** — `property`, returns `super() + ['country_id', 'city', 'website', 'website_description', 'website_published']`
- Adds profile public fields to the writeable set. This allows an authenticated user to edit these fields through the website profile editor without backend access rights.
- `website_published` is included here so users can toggle their own profile visibility.

#### Email Validation Methods

**`_generate_profile_token(user_id, email) → str`**
- Builds a SHA-256 token valid for the current calendar day. The hash inputs are: `(day_start, profile_uuid, user_id, email)`. The `profile_uuid` is stored in `ir.config_parameter` (`website_profile.uuid`) and generated once on first call if absent.
- **Token validity**: One calendar day. Expired tokens will never match on the server side, causing `_process_profile_validation_token` to return `False`.
- **Security note**: The token is aHMAC-equivalent construction using a shared secret UUID, the user ID, and the email. Changing either `user_id` or `email` after sending the token invalidates it.

**`_send_profile_validation_email(**kwargs) → bool`**
- Sends the `website_profile.validation_email` mail template to `self.email`.
- Skips silently if `self.email` is falsy.
- Stores `token_url` into the template context, passed via `send_mail(..., context={'token_url': ...})`.
- Raises `ValidationError` / `except` if `send_mail(..., raise_exception=True)` fails (e.g., SMTP unreachable).
- Returns `True` even if the template is not found (the `if activation_template` guard).
- Sets `request.session['validation_email_sent'] = True` in the controller after calling this method.

**`_process_profile_validation_token(token, email) → bool|int`**
- Regenerates the expected token and compares with the provided token.
- **Second guard**: `self.karma == 0` — This prevents re-granting karma on replayed or double-clicked validation links. If the user already has karma (e.g., from forum participation), the token is still considered valid but karma is not incremented.
- On success: writes `karma = VALIDATION_KARMA_GAIN` (3 points) and returns `True`.
- Returns `False` on token mismatch or if karma is already > 0.

#### Constant

```python
VALIDATION_KARMA_GAIN = 3
```
Value is hardcoded. Changing this has no migration path — any future tokens issued before the change will still resolve based on this constant's value at resolution time.

---

### `gamification.badge` — Extended

> File: `models/gamification_badge.py`

```python
class GamificationBadge(models.Model):
    _name = 'gamification.badge'
    _inherit = ['gamification.badge', 'website.published.mixin']
```

**Inheritance rationale**: `gamification.badge` inherits `mail.thread` and `image.mixin` from its parent. Adding `website.published.mixin` brings:
- `website_published` (Boolean, related to `is_published`, `readonly=False`) — allows badge visibility to be toggled per-website or globally.
- `website_publish_button` — a form button rendered by the view XML.
- `is_published` (Boolean, default `False`) — the canonical publication flag.

**Cross-model impact**: Badges with `is_published = True` appear in `/profile/ranks_badges` and on user profile pages. Unpublished badges are hidden but existing `gamification.badge.user` grant records remain.

---

### `website` — Extended

> File: `models/website.py`

```python
class Website(models.Model):
    _inherit = 'website'
    karma_profile_min = fields.Integer(string="Minimal karma to see other user's profile", default=150)
```

**`karma_profile_min`** — `Integer`, default `150`
- Set on the `website` record. Controls whether user A can view user B's profile. Viewed in `WebsiteProfile._check_user_profile_access()`.
- Default of 150 means a new user who validated their email (3 karma) cannot view any other profiles. This protects early-stage community members from seeing high-activity profiles.
- The field is configured in `views/website_views.xml` as a form field inserted after `default_lang_id` in the website configuration form.

---

## Controllers

### `WebsiteProfile` (`controllers/main.py`)

All routes use `website=True` (multi-website aware) and `auth="public"` unless noted.

#### Constants (Class-Level)

```python
_users_per_page = 30   # leaderboard page size
_pager_max_pages = 5   # pager scope
```

---

#### Route: `GET /profile/avatar/<int:user_id>`

**Auth**: `auth="public"` | **Readonly** | **Sitemap**: No

```python
@http.route(['/profile/avatar/<int:user_id>'], type='http', auth="public",
           website=True, sitemap=False, readonly=True)
def get_user_profile_avatar(self, user_id, field='avatar_256', width=0, height=0,
                           crop=False, **post):
```

- `field` must be one of: `image_128`, `image_256`, `avatar_128`, `avatar_256`. Any other value returns HTTP 403 (`werkzeug.exceptions.Forbidden()`).
- `_check_avatar_access()` gates the sudo escalation: returns `True` only if `user.website_published and user.karma > 0`. Otherwise the binary read runs without sudo, which will raise `AccessError` for unpublished users.
- When both `width` and `height` are 0, falls back to `tools.image.image_guess_size_from_field_name(field)`.
- **Security implication**: Avatar access does NOT require `karma_profile_min` — only publication + karma presence. This means any published community member's avatar is publicly accessible.

---

#### Route: `GET /profile/user/<int:user_id>`

**Auth**: `auth="public"` | **Readonly**

```python
def view_user_profile(self, user_id, **post):
```

Access check sequence (via `_check_user_profile_access`):

1. **Own profile**: `user_sudo.id == request.env.user.id` — always granted, no karma check.
2. **Unpublished**: `user.website_published == False` → denial: `"This profile is private!"`.
3. **User does not exist**: raises `request.not_found()` (HTTP 404).
4. **Insufficient karma**: `request.env.user.karma < request.website.karma_profile_min` → denial: `"Not have enough karma to view other users' profile."`.
5. **Granted**: returns `(user_sudo, False)`.

Rendered template: `website_profile.user_profile_main`.

---

#### Route: `POST /profile/user/save` (JSON-RPC)

**Auth**: `auth="user"` | **Methods**: `POST`

```python
def save_edited_profile(self, **kwargs):
```

- Accepts `user_id` in kwargs. Non-owner/non-admin can never edit — the controller only uses `request.env.user` unless `_is_admin()`.
- `_profile_edition_preprocess_values()` maps incoming form keys (`name`, `website`, `email`, `city`, `country_id`, `website_description`, `image_1920`) into a dict.
- Only fields in `user._self_accessible_fields()[1]` (the writeable set) pass through — a whitelist filter.
- Country change guard: `partner_id._can_edit_country()` — once a document is issued for the account (e.g., an invoice), country cannot be changed. Raises `UserError`.
- **Admin override**: If `request.env.user._is_admin()`, the admin can edit any user's profile by passing `user_id`.

---

#### Route: `GET /profile/ranks_badges`

**Auth**: `auth="public"` | **Sitemap**: Yes

```python
def view_ranks_badges(self, **kwargs):
```

- `_prepare_badges_domain()` builds a `Domain` tree: `website_published == True`. If `badge_category` is in kwargs, it adds a condition joining through `challenge_ids.challenge_category`. This allows forum or slides to show only their category's badges.
- `badges = Badge.sudo().search(domain).sorted("granted_users_count", reverse=True)` — sorted by popularity (most-awarded first).
- Ranks are fetched from `gamification.karma.rank` ordered `karma_min DESC` (highest to lowest), only when `badge_category` is NOT set.
- Rendered template: `website_profile.rank_badge_main`.

---

#### Route: `GET /profile/users` and `/profile/users/page/<int:page>`

**Auth**: `auth="public"` | **Sitemap**: Yes

```python
def view_all_users_page(self, page=1, **kwargs):
```

**Base domain**:
```python
dom = [('karma', '>', 1), ('website_published', '=', True)]
```

Note: `karma > 1` (not `> 0`) — users with exactly 1 karma (post-validation) are excluded from the leaderboard. This is an intentional design choice to filter out unestablished accounts.

**Search**: `name ilike search_term` OR `partner_id.commercial_company_name ilike search_term` — allows searching by company name.

**Pagination**: 30 users per page. Pager scope is `min(page_count, 5)` to avoid wide pager bars.

**Top 3 users**: Only on page 1 and when there is no active search term. Displayed as podium cards with rank medals (SVG rank_1.svg / rank_2.svg / rank_3.svg).

**Karma position map** (`_get_position_map`):
- When `group_by` is set (`week`/`month`): calls `_get_user_tracking_karma_gain_position()` which queries `gamification.karma.tracking` filtered by `tracking_date` to compute period-specific karma gain.
- When `group_by` is falsy: calls `users._get_karma_position(position_domain)` which computes total karma ranking using a SQL window function.

**Current user row**: If the authenticated user is published and has karma but is not on the current page, their row is appended below the table so they can always see their own position and karma gain.

---

#### Route: `POST /profile/send_validation_email` (JSON-RPC)

**Auth**: `auth="user"`

```python
def send_validation_email(self, **kwargs):
```

- Guards against the portalbot user: `if request.env.uid != request.website.user_id.id` — the portal bot cannot send validation emails to itself.
- Calls `request.env.user._send_profile_validation_email(**kwargs)`.
- Sets session flag: `request.session['validation_email_sent'] = True`.
- Returns `True`.

---

#### Route: `GET /profile/validate_email`

**Auth**: `auth="public"`

```python
def validate_email(self, token, user_id, email, **kwargs):
```

- Browses the user with sudo and calls `_process_profile_validation_token(token, email)`.
- On success: `request.session['validation_email_done'] = True`.
- Redirects to `redirect_url` kwarg or `/`.

---

#### Route: `POST /profile/validate_email/close` (JSON-RPC)

**Auth**: `auth="public"`

```python
def validate_email_done(self, **kwargs):
```

- Clears both session flags: `validation_email_sent` and `validation_email_done`. Used to dismiss the email validation banner permanently.

---

### `CustomerPortalProfile` (`controllers/portal.py`)

Extends `portal.controllers.portal.CustomerPortal`.

```python
def _validate_address_values(self, address_values, partner_sudo, *args, **kwargs):
```

**Purpose**: If a user changes their email address in the portal account form (`/my/account`), the email validation flow must be reset. The method checks if the incoming `address_values['email']` differs from the current partner email, and if so sets `request.session['validation_email_sent'] = False`.

This ensures that after an email change, the user must re-validate before earning karma again (or before the validation banner is shown as "done").

---

## Views

### `views/gamification_badge_views.xml`

Adds a `website_publish_button` button to the `gamification.badge` form view button box. Enables badge administrators to publish/unpublish badges directly from the backend form.

### `views/website_views.xml`

Extends the website configuration form (at `website.view_website_form`) to insert `karma_profile_min` after `default_lang_id`.

### `views/website_profile.xml`

Primary QWeb template file. Key templates:

| Template ID | Purpose |
|---|---|
| `user_profile_main` | Single user profile page wrapper |
| `user_profile_header` | Banner with avatar, name, rank, location |
| `user_profile_content` | Sidebar (rank, karma, badges) + tabbed content |
| `user_profile_sub_nav` | Breadcrumb nav with Forum/Courses back-link |
| `profile_next_rank_card` | SVG circular progress toward next rank |
| `user_badges` | Badge collection grid for a user |
| `email_validation_banner` | Dismissible alert banners for email validation states |
| `rank_badge_main` | Ranks and badges gallery page |
| `badge_content` | Badge listing rows (image, description, granted count) |
| `users_page_main` | Leaderboard page wrapper |
| `users_page_header` | Header with rank-by period selector |
| `top3_user_card` | Podium cards for top 3 users |
| `all_user_card` | Table row for leaderboard user |
| `profile_access_denied` | Access denial page |

---

## Security

### Access Control (`security/ir.model.access.csv`)

```csv
id,name,model_id/id,group_id/id,perm_read,perm_write,perm_create,perm_unlink
gamification_karma_rank_access_restricted_editor,gamification.karma.rank.access.website.restricted_editor,
  gamification.model_gamification_karma_rank,website.group_website_restricted_editor,1,1,1,1
```

Grants full CRUD on `gamification.karma.rank` to `website.group_website_restricted_editor`. This is a minimal ACL — the restricted editor can manage rank definitions.

### Karma-Based Profile Access

The karma gate (`karma_profile_min`, default 150) applies only to viewing **other users'** profiles. A user can always view their own. This is enforced in Python (controller), not in the ORM or record rules, so it is bypassable with direct API calls.

### Avatar Access (No Karma Gate)

Avatars are served with a lower bar: `website_published AND karma > 0`. This means an unpublished user with 0 karma cannot have their avatar accessed, but a user with karma who is published can. There is no karma threshold on avatars.

### Email Validation Replay Protection

`_process_profile_validation_token` guards against replay with `self.karma == 0`. However, once a user has earned karma from another source (forum, courses), subsequent email validation tokens will validate but NOT grant additional karma. The token itself is still considered "valid" for the purpose of the email verification banner UX — the banner is only cleared by the `validate_email_done` session call.

---

## Performance

### Leaderboard (`/profile/users`)

- **Position computation**: Two separate code paths.
  - `group_by` off: single SQL window query (`_get_karma_position`) scanning all `res_users` rows matching `user_domain`. With millions of users this can be expensive; Odoo's implementation uses `DISTINCT ON` with `ORDER BY karma DESC` — the query planner can use the `karma` index on `res_users`.
  - `group_by` period: joins `gamification_karma_tracking` filtered by `tracking_date::DATE` against the date range. With no index on `tracking_date`, this degrades linearly with tracking table size. Odoo ships `gamification` without an index on `tracking_date` in the base module.

- **Karma computation** (`_compute_karma` in `gamification/models/res_users.py`): Uses `DISTINCT ON (user_id) ... ORDER BY user_id, tracking_date DESC, id DESC` — the `id DESC` tiebreaker ensures stable ordering when multiple tracking entries share the same `tracking_date`. This requires an index on `(user_id, tracking_date DESC, id DESC)` to be efficient at scale.

- **Badge counts in leaderboard**: `len(user.badge_ids)` is called per user in Python in `_prepare_all_users_values()`. This loads the full `gamification.badge.user` relation in memory. For a 30-user page this is acceptable; for bulk exports it is not.

### Avatar Route

`/profile/avatar/<id>` calls `_get_image_stream_from` which triggers Odoo's binary image resizing pipeline. With `crop=True` or non-zero dimensions, this generates a resized image on the fly (cached after first request). The route is marked `readonly=True` so it bypasses ORM access checks during image fetch.

---

## Gamification Integration (Cross-Module Reference)

All gamification karma fields are defined in `gamification/models/res_users.py` and inherited here:

| Field | Type | Notes |
|---|---|---|
| `karma` | `Integer` | Computed from `gamification.karma.tracking.new_value`, stored |
| `karma_tracking_ids` | `One2many` → `gamification.karma.tracking` | Karma change history, `groups="base.group_system"` |
| `badge_ids` | `One2many` → `gamification.badge.user` | All badges earned by the user |
| `gold_badge` | `Integer` | Count of gold-level badges |
| `silver_badge` | `Integer` | Count of silver-level badges |
| `bronze_badge` | `Integer` | Count of bronze-level badges |
| `rank_id` | `Many2one` → `gamification.karma.rank` | Current rank |
| `next_rank_id` | `Many2one` → `gamification.karma.rank` | Next rank to achieve |

Rank is automatically recomputed by `_compute_karma()` (which calls `_recompute_rank()`). This is triggered on every karma tracking insert. See `[Modules/gamification](gamification.md)` for full details.

---

## Email Validation Workflow

```
1. User registers / logs into website
2. profile page shows "not verified" banner (karma == 0)
3. User clicks "Send validation email" → POST /profile/send_validation_email
4. _send_profile_validation_email() generates token + sends email
5. User clicks link in email → GET /profile/validate_email?token=&user_id=&email=
6. _process_profile_validation_token() verifies token
   - Token matches AND karma == 0 → karma += 3
   - Otherwise → silent no-op, redirects to /
7. Banner updated via session flags
8. User can dismiss banner → POST /profile/validate_email/close
```

If the user changes their email via `/my/account`, `CustomerPortalProfile._validate_address_values()` resets the session flags, causing the validation banner to reappear.

---

## Static Assets

| Path | Purpose |
|---|---|
| `static/src/img/badge_bronze.svg` | Fallback bronze badge image |
| `static/src/img/badge_silver.svg` | Fallback silver badge image |
| `static/src/img/badge_gold.svg` | Fallback gold badge image |
| `static/src/img/rank_1.svg` | Gold medal for #1 position |
| `static/src/img/rank_2.svg` | Silver medal for #2 position |
| `static/src/img/rank_3.svg` | Bronze medal for #3 position |
| `static/src/scss/website_profile.scss` | Profile page styling |

---

## Tests

### `TestWebsiteProfile` (`tests/test_website_profile.py`)

- `test_prepare_url_from_info` — Verifies `_prepare_url_from_info()` correctly detects referer URLs pointing to `/forum` and `/slides` and returns the appropriate label.
- `test_save_change_description` — Browser tour test: creates a user with karma=100, website_published=True, then opens the profile page and edits the `website_description`.

### `TestWebsiteProfileTechnicalPage` (`tests/test_website_profile_technical_page.py`)

- `test_load_website_profile_technical_pages` — Checks that both public routes (`/profile/users`, `/profile/ranks_badges`) are technically reachable (no routing errors, HTTP 200).

---

## Odoo 18 → 19 Changes

- **New dependency**: `html_editor` added in Odoo 19. The `website_description` field (from `website_partner`) now uses the HTML editor for rich-text editing. In Odoo 18, this used the older `mail.compose.mixin`-style editor.
- **Controller rename**: `CustomerPortal` extension path changed from `portal.portal` to `portal.controllers.portal` (module path refactor).
- **`website.published.mixin` on badges**: This inheritance was introduced or confirmed in the 19 refactor — `gamification.badge` did not previously have website publishing capabilities.

---

## Related Documentation

- [Modules/website_partner](website_partner.md) — `res.partner.website_description` field
- [Modules/gamification](gamification.md) — Karma tracking, ranks, badges
- [Core/API](API.md) — `@api.depends`, `@api.model`, computed fields
- [Core/Fields](Fields.md) — Field types used across these models
