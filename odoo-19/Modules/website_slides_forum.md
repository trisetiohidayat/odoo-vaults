---
uuid: website-slides-forum-l4-001
module: website_slides_forum
tags:
  - #odoo
  - #odoo19
  - #modules
  - #website
  - #elearning
  - #forum
  - #community
level: L4
description: Full L4 documentation for website_slides_forum — forum Q&A integration for eLearning courses, linking slide.channel to forum.forum with bidirectional sync, privacy propagation, and record-rule security
related_modules:
  - website_slides
  - website_forum
  - forum
  - website_profile
  - gamification
depends_on:
  - website_slides
  - website_forum
created: 2026-04-11
updated: 2026-04-11
---

# website_slides_forum — Forum on Courses (L4 Depth)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Forum on Courses |
| **Technical Name** | `website_slides_forum` |
| **Category** | Website/eLearning |
| **Version** | 1.0 (manifest) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Auto Install** | Yes |
| **Source** | `odoo/addons/website_slides_forum/` |

## Description

The `website_slides_forum` module creates a tight bidirectional integration between `slide.channel` (eLearning courses) and `forum.forum` (community Q&A). When a course is linked to a forum, learners can ask questions, discuss content, and post answers — surfaced directly on the course page and the forum index. The module propagates course visibility into forum access control, syncs the channel's image to the forum, and adds forum-aware record rules to `forum.forum`, `forum.post`, and `forum.tag`.

## Dependencies

| Module | Type | Purpose |
|--------|------|---------|
| `website_slides` | Hard | Course model (`slide.channel`), channel image field, menu structure |
| `website_forum` | Hard | Forum model (`forum.forum`), post model (`forum.post`), tag model (`forum.tag`), forum controller |
| `website` | Transitive | Website routing, page builder |
| `forum` | Transitive | Base forum ORM (`forum.forum`, `forum.post`, `forum.tag`) |
| `website_profile` | Transitive | Profile page integration |
| `gamification` | Transitive | Karma system for posting/voting |

## Architecture

```
slide.channel (website_slides)
        │
        ├── forum_id: Many2one ──────► forum.forum
        │                                 │
        │                                 ├── slide_channel_ids: One2many (inverse)
        │                                 ├── slide_channel_id: computed Many2one
        │                                 │     (first item of slide_channel_ids)
        │                                 ├── visibility: related channel.visibility
        │                                 └── image_1920: computed from channel
        │
        └── forum_total_posts: related forum_id.total_posts
```

The module does **not** define new models. It extends two existing models and adds record rules and templates on top.

---

## Models

### `slide.channel` — Inherited from `website_slides`

**File**: `models/slide_channel.py`

#### Fields Added

| Field | Type | Default | Constraint | Purpose |
|-------|------|---------|------------|---------|
| `forum_id` | `Many2one(forum.forum)` | `False` | `_forum_uniq` unique constraint | Links the course to a dedicated Q&A forum |
| `forum_total_posts` | `Integer` | — (related) | read-only | Displays the total active post count on the course form |

**`forum_id` details**:
- `copy=False`: intentionally not copied when duplicating a channel, as a forum should not automatically follow a duplicated course
- `index='btree_not_null'`: creates a partial index on `forum_id` where it is not null — Odoo 19 uses `'btree_not_null'` syntax for PostgreSQL partial indexes; this avoids indexing null values while keeping lookups fast on active links
- Domain in form view: `[('slide_channel_id', 'in', [id, False])]` — only shows forums that are either unlinked or linked to this specific channel

**`forum_total_posts`** is a plain `related` field:
```python
forum_total_posts = fields.Integer(related="forum_id.total_posts")
```
It reads `forum.forum.total_posts` (a count of active, non-closed posts on the forum). Because it is a related field, no manual recompute is needed — it updates automatically when `forum_id.total_posts` changes. It is **not** stored, so it is always fetched live from the forum.

#### `_forum_uniq` Constraint

```python
_forum_uniq = models.Constraint(
    'unique (forum_id)',
    'Only one course per forum!',
)
```
This is a SQL-level `UNIQUE` constraint enforced at the database. One forum cannot be linked to multiple courses. The inverse direction (one course → one forum) is already guaranteed by the Many2one itself. This constraint prevents the reverse link.

#### Methods

**`action_redirect_to_forum()`**

Signature: `self.env['slide.channel'] -> ir.actions.act_window`

Returns the `forum.post` list action (`website_forum.forum_post_action`) filtered to the current channel's forum:

```python
def action_redirect_to_forum(self):
    self.ensure_one()
    action = self.env["ir.actions.actions"]._for_xml_id("website_forum.forum_post_action")
    action['view_mode'] = 'list'
    action['context'] = {'create': False}
    action['domain'] = [('forum_id', '=', self.forum_id.id)]
    return action
```

- `ensure_one()`: guards against calling this on a recordset of >1 channel — raises if called in a multi-record context
- `view_mode` forced to `'list'`: bypasses any default form/mixed view
- `'create': False` in context: prevents users from creating posts directly from this filtered list — they must use the actual forum UI
- Uses `_for_xml_id` (framework method) rather than `ref()` to resolve the action — handles cases where the action XML ID has been customized or moved

**`create(vals_list)` — Override**

```python
@api.model_create_multi
def create(self, vals_list):
    channels = super().with_context(mail_create_nosubscribe=True).create(vals_list)
    channels.forum_id.privacy = False
    return channels
```

- `@api.model_create_multi`: Odoo 19 style for multi-create; receives a list of vals dicts
- `mail_create_nosubscribe` context: suppresses automatic follower notifications on the new channel record (inherited from parent)
- After channel creation, sets `forum_id.privacy = False` (public) on the newly linked forum — this is the initial state for a freshly created forum link
- `channels.forum_id.privacy` triggers a live write on the forum record

**`write(vals)` — Override**

```python
def write(self, vals):
    old_forum = self.forum_id  # captured BEFORE super() call

    res = super().write(vals)

    if 'forum_id' in vals:
        self.forum_id.privacy = False                     # new forum → public
        if old_forum != self.forum_id:                    # forum was changed
            old_forum.write({
                'privacy': 'private',
                'authorized_group_id': self.env.ref(
                    'website_slides.group_website_slides_officer'
                ).id,
            })
    return res
```

**Failure modes**:
- `self.forum_id` on a channel with no forum returns an empty record — `old_forum != self.forum_id` comparison still works correctly (empty record != new forum)
- If `vals['forum_id']` is set to `False` (unlink), the new forum assignment is skipped; the old forum is left in whatever state it is in (not made private) — this is a potential edge case
- `self.env.ref('website_slides.group_website_slides_officer')` raises `MissingError` if the XML module `website_slides` is not installed — but since `website_slides` is a hard dependency, this is safe
- The write on `old_forum` (making it private) uses the `write()` method so it triggers `mail.thread` notifications and ORM hooks — this may send emails if the forum module has such notifications configured

**Performance note**: The `super().write(vals)` call is unconditional — `forum_id` may or may not be in `vals`. The `old_forum` snapshot is captured before the write to avoid accessing the possibly-changed field value after the write has happened.

---

### `forum.forum` — Inherited from `website_forum`

**File**: `models/forum_forum.py`

#### Fields Added

| Field | Type | Stored | Compute Trigger | Purpose |
|-------|------|--------|----------------|---------|
| `slide_channel_ids` | `One2many(slide.channel, forum_id)` | — | n/a | Inverse of `slide.channel.forum_id`; enables bidirectional access |
| `slide_channel_id` | `Many2one(slide.channel)` | Yes | `slide_channel_ids` | First linked course (computed from One2many) |
| `visibility` | `Selection` | No | related | Mirrors channel visibility into forum form |
| `image_1920` | `Image` | Yes | `slide_channel_id.image_1920` | Syncs course image to forum; `readonly=False` allows manual override |

**`slide_channel_id` computation**:
```python
@api.depends('slide_channel_ids')
def _compute_slide_channel_id(self):
    for forum in self:
        if forum.slide_channel_ids:
            forum.slide_channel_id = forum.slide_channel_ids[0]
        else:
            forum.slide_channel_id = None
```
- `store=True` makes this persistent in the database — avoids recomputation on read
- Takes only the **first** channel if multiple somehow exist (should not happen due to `_forum_uniq` constraint)
- The `_forum_uniq` constraint means there is always at most one channel per forum, so this is effectively always a single value; the `[0]` pattern is defensive

**`image_1920` sync logic**:
```python
@api.depends('slide_channel_id', 'slide_channel_id.image_1920')
def _compute_image_1920(self):
    for forum in self.filtered(lambda f: not f.image_1920 and f.slide_channel_id.image_1920):
        forum.image_1920 = forum.slide_channel_id.image_1920
```
- `not f.image_1920`: **only** syncs when the forum has no image — once set manually, it is never overwritten by the channel's image
- `readonly=False` in field definition: allows manual override after auto-sync
- `store=True` makes the synced image persistent
- To reset to channel image after manual override, the user must explicitly clear the field

---

## View Extensions

### `slide.channel` Form View — `slide_channel_views.xml`

**Inheritance target**: `website_slides.view_slide_channel_form`

Two modifications:

1. **Forum button** (inserted after `action_view_ratings` button):
   - Shows `action_redirect_to_forum` as a stat button
   - `invisible="not forum_id"`: button only appears when a forum is linked
   - Widget `widget="statinfo"` displays the integer value of `forum_total_posts`
   - Icon: `fa-comment` (FontAwesome comment icon)

2. **Forum field** (inserted after `allow_comment`):
   ```xml
   <field string="Forum" name="forum_id" domain="[('slide_channel_id', 'in', [id, False])]"/>
   ```
   - Domain restricts the forum selector to forums either unlinked or linked to the current channel (prevents accidentally linking to an already-linked forum)
   - `string="Forum"` overrides the field's human-readable label

### `forum.forum` Form View — `forum_forum_views.xml`

**Inheritance target**: `website_forum.forum_forum_view_form`

| Element | Modification | Condition |
|---------|-------------|-----------|
| `privacy` field | `invisible` | `slide_channel_id` is set — forum privacy is controlled by channel |
| `privacy` field | `required=False` | `slide_channel_id` is set |
| `authorized_group_id` field | `invisible` | `privacy != 'private'` OR `slide_channel_id` is set |
| `authorized_group_id` field | `required` | `privacy == 'private'` AND no `slide_channel_id` |
| `visibility` field | inserted `before` privacy | Shows channel visibility for course-linked forums |
| `slide_channel_id` readonly field | inserted in new `eLearning` group | Visible only when forum is linked to a course |

A new **list view** (`forum_forum_view_tree_slides`, priority 20) adds `slide_channel_id` and `visibility` columns to the tree view for course-linked forums.

A dedicated window action (`forum_forum_action_channel`) opens the forum list filtered to only forums that have at least one linked channel: `[('slide_channel_ids', '!=', 'False')]`.

### `forum.post` Views — `forum_post_views.xml`

**Graph view** `forum_post_view_graph_slides` (model `forum.post`): enables analytics on post creation dates grouped by forum for course discussions.

**Window action** `forum_post_action_channel`: opens forum posts filtered to forums with linked channels `[('forum_id.slide_channel_ids', '!=', 'False')]`, with `search_default_questions=1` to pre-filter to question-type posts (posts without a parent).

---

## Record Rules (ir.rule)

**File**: `security/website_slides_forum_security.xml`

The module adds six record rules — three for `forum.forum`, three for `forum.post`, three for `forum.tag` — mirroring the same group-based pattern with slightly different domain forces that traverse the forum-to-channel join.

### `forum.forum` Rules

| Rule ID | Group | Domain Force |
|---------|-------|-------------|
| `website_slides_forum_public` | `base.group_public` | `('slide_channel_ids.website_published', '=', True)` AND `('slide_channel_ids.visibility', '=', 'public')` |
| `website_slides_forum_signed_in_user` | `base.group_portal` + `base.group_user` | `('slide_channel_ids.website_published', '=', True)` AND (`visibility IN ('public','connected')` OR `is_member = True`) |
| `website_slides_forum_website_slides_officer` | `website_slides.group_website_slides_officer` | `[(1, '=', 1)]` — unrestricted |

### `forum.post` Rules

| Rule ID | Group | Domain Force |
|---------|-------|-------------|
| `website_slides_forum_public_post` | `base.group_public` | `('forum_id.slide_channel_ids.website_published', '=', True)` AND `('forum_id.slide_channel_ids.visibility', '=', 'public')` |
| `website_slides_forum_post_signed_in_user` | `base.group_portal` + `base.group_user` | `('forum_id.slide_channel_ids.website_published', '=', True)` AND (`visibility IN ('public','connected')` OR `is_member = True`) |
| `website_slides_forum_website_slides_officer_post` | `website_slides.group_website_slides_officer` | `[(1, '=', 1)]` — unrestricted |

### `forum.tag` Rules

| Rule ID | Group | Domain Force |
|---------|-------|-------------|
| `website_slides_forum_public_tag` | `base.group_public` | `('forum_id.slide_channel_ids.website_published', '=', True)` AND `('forum_id.slide_channel_ids.visibility', '=', 'public')` |
| `website_slides_forum_tag_signed_in_user` | `base.group_portal` + `base.group_user` | `('forum_id.slide_channel_ids.website_published', '=', True)` AND (`visibility IN ('public','connected')` OR `is_member = True`) |
| `website_slides_forum_website_slides_officer_tag` | `website_slides.group_website_slides_officer` | `[(1, '=', 1)]` — unrestricted |

### Security Design Notes

**Visibility propagation**: Unlike the forum's own `privacy` field (which is hidden in the UI for course-linked forums), access control is delegated entirely to the channel's `website_published` and `visibility` fields. The forum's `privacy` field value is irrelevant for course-linked forums — it is always overridden by the record rules.

**Portal vs public**: Signed-in portal users and internal users share the same rule, which grants broader access (`connected` visibility plus `is_member`). Public users (no login) are restricted to published public channels only.

**Officer bypass**: `group_website_slides_officer` always has unrestricted access via `[(1, '=', 1)]` — this includes viewing private channels and their forums, moderation of posts, etc.

**Edge case — unpublished channel**: When a channel is unpublished (`website_published = False`), the `website_published = True` condition in all rules fails for all non-officer users, making all linked forum content (posts, tags) invisible. This is intentional.

**Performance implication**: Each record rule traverses a One2many join (`slide_channel_ids`) and then accesses channel fields. With many forums and channels, these rules can be slow on large datasets — particularly the `signed_in_user` rule which has three conditions and a OR branch.

**ACL Entry**: `access_forum_forum_website_slides_officer` grants `website_slides.group_website_slides_officer` read+write on `forum.forum` (no create/unlink). This is more restrictive than the base forum ACL which may grant portal users read access.

---

## Controller

**File**: `controllers/main.py`

Class: `WebsiteSlidesForum(WebsiteSlides)`

Extends the `website_slides` controller by overriding one method:

### `_prepare_user_profile_parameters(**post)`

```python
def _prepare_user_profile_parameters(self, **post):
    post = super()._prepare_user_profile_parameters(**post)
    if post.get('channel_id'):
        channel = request.env['slide.channel'].browse(int(post.get('channel_id')))
        if channel.forum_id:
            post.update({
                'forum_id': channel.forum_id.id,
                'no_forum': False
            })
        else:
            post.update({'no_forum': True})
    return post
```

**Purpose**: When rendering a user's profile page from a course context (`?channel_id=<id>` in query params), the controller injects the linked forum into the profile page parameters so the forum's recent activity is shown alongside the course activity.

**Call chain**: `website_profile` controller calls `_prepare_user_profile_parameters`, which is overridden by `WebsiteSlides` (in `website_slides`) and now by `WebsiteSlidesForum`.

| Parameter | Purpose |
|-----------|---------|
| `forum_id` | Passed to `website_forum` controller to include forum activity in profile |
| `no_forum` | Suppresses forum-related UI elements when no forum is linked |

**Edge cases**:
- `post.get('channel_id')` may be a string or None — `int(...)` raises `ValueError` if the string is non-numeric; wrapped by `post.get('channel_id')` check first
- `channel` is browsed fresh from request params — not trusted from the session; if the channel does not exist, `browse()` returns an empty record and `channel.forum_id` is falsy
- The method mutates `post` in place then returns it — the calling code (`website_profile`) reads the final dict

---

## Website Templates

**File**: `views/website_slides_templates.xml`

### `course_main` (inherits `website_slides.course_main`)

Injects a **Forum nav link** into the channel header navigation bar after the review tab:

```xml
<li class="nav-item" t-if="not invite_preview
    and (channel.is_member or channel.visibility == 'public')
    and channel.forum_id">
    <a t-att-href="'/forum/%s' % (slug(channel.forum_id))"
       class="nav-link" target="new">Forum</a>
</li>
```

- `invite_preview`: hides the forum link in invitation preview mode (where the recipient has limited access)
- `channel.is_member or channel.visibility == 'public'`: mirrors the same visibility check used in record rules — forum link is only shown when the user can actually access the forum
- `target="new"`: opens in a new tab — forum is a separate page from the course page

### `slide_fullscreen` (inherits `website_slides.slide_fullscreen`)

Injects a **forum button** into the fullscreen slide viewer toolbar:

```xml
<a t-if="(channel.is_member or channel.visibility == 'public')
    and slide.channel_id.forum_id"
   id="fullscreen_forum_button"
   class="d-flex align-items-center px-3"
   t-attf-href="/forum/#{slug(slide.channel_id.forum_id)}"
   target="new" title="Forum">
    <i class="fa fa-comments"/><span class="ms-1 d-none d-md-inline-block">Forum</span>
</a>
```

- Hidden on mobile (`d-none d-md-inline-block` on the label) — only icon shown on small screens
- Uses `slide.channel_id.forum_id` (slide-level channel lookup) rather than `channel.forum_id` to handle the fullscreen context correctly
- `target="new"`: same as course page link

---

## Forum Templates

**File**: `views/forum_forum_templates.xml`

### `website_slides_forum_index` (inherits `website_forum.forum_all`)

Splits the global forum index page into two sections:
```python
courses_discussions = forums.filtered(lambda f: f.slide_channel_id)
regular_forums = forums - courses_discussions
```
- `regular_forums` rendered first via `forum_all_all_entries`
- `courses_discussions` rendered second with a "Check out our courses" CTA button appended

### `website_slides_forum_breadcrumb` (inherits `website_forum.forum_model_nav`)

Sets `breadcrumb_kind = 'slides'` when the forum is course-linked, then injects a two-segment breadcrumb: `[Course Name] → Forum` (on single forum view) or just the course link (on list/edit views). The forum name itself becomes the clickable root item.

### `forum_all_all_entries` (inherits `website_forum.forum_all_all_entries`)

Sets `forum_badge = 'Course'` as a CSS label for course-linked forums in the list display, and appends the "Check out our courses" CTA after the list.

---

## Menu Structure

**File**: `views/website_slides_menu_views.xml`

Under the `website_slides` root menu, adds:

```
Forum (website_slides_menu_forum)
  ├── Forums        → forum_forum_action_channel     (sequence 1)
  └── Posts         → forum_post_action_channel       (sequence 2)
```

Both sub-menu items are filtered to course-linked content:
- Forums action: `[('slide_channel_ids', '!=', 'False')]`
- Posts action: `[('forum_id.slide_channel_ids', '!=', 'False')]`

This gives course officers a dedicated section in the backend sidebar for managing course forums and posts without seeing general website forums.

---

## Settings Integration

**File**: `views/res_config_settings_views.xml`

**Inheritance target**: `website_slides.res_config_settings_view_form` (priority 20)

Inserts a "Manage Forums" button inside the `website_slide_install_website_slides_forum` setting block that opens the forum list action. This allows administrators to jump directly to course forums from the Odoo Settings → Websites → eLearning configuration page.

---

## Demo Data

**File**: `data/slide_channel_demo.xml` (`noupdate=1`)

Links two demo channels from `website_slides` to newly created forums:
- `slide_channel_demo_0_gard_0` (Gardening course) → forum `forum_forum_demo_channel_0` ("Basics of Gardening")
- `slide_channel_demo_2_gard2` (Trees course) → forum `forum_forum_demo_channel_2` ("Trees, Wood and Gardens")

Also creates two demo posts:
- A question on the Gardening forum (admin user), created 31 days ago
- An answer reply to that question (admin user)
- A question on the Trees forum (demo user)

---

## Auto-Install Behavior

The module is marked `auto_install: True`. When Odoo upgrades all modules or installs `website_slides_forum` as a dependency of another auto-install module, the `noupdate=1` demo data (`data/slide_channel_demo.xml`) ensures that existing demo courses are linked to newly created forums.

The `super().with_context(mail_create_nosubscribe=True).create(vals_list)` call in `create()` means that any course created programmatically (not just through demo data) will have its forum automatically set to public on channel creation.

---

## Cross-Module Integration Map

```
website_slides                    website_slides_forum              website_forum
─────────────────                 ──────────────────               ──────────────
slide.channel                     slide.channel                     forum.forum
  forum_id (new) ────────────────────►  slide_channel_ids              total_posts
  forum_total_posts ───────────────────► (related)                     privacy
  action_redirect_to_forum() ───────────► forum_post_action            image_1920
                                                                        slide_channel_id
slide.channel.create() ───────────────► sets forum.privacy=False
slide.channel.write() ───────────────► sets new forum.privacy=False
                                      old forum → privacy='private'
                                                        authorized_group_id
                                                         = slides_officer

slide.channel.create() ───────────────► super(mail_create_nosubscribe)

slide.channel menu ───────────────────► website_slides_menu_forum
                                          ├── Forums
                                          └── Posts

WebsiteSlides controller ───────────► WebsiteSlidesForum
  _prepare_user_profile_parameters ────► + forum_id / no_forum params

slide.course_main template ────────────► + Forum nav link
slide.slide_fullscreen template ────────► + Forum button in toolbar

forum_all template ────────────────────► splits course vs regular forums
forum_model_nav template ──────────────► course-aware breadcrumbs
```

---

## Performance Considerations

1. **Record rules with One2many joins**: All six `ir.rule` records traverse `slide_channel_ids` (One2many) to reach channel fields. In PostgreSQL, this generates a subquery join. On databases with thousands of channels and forums, these rules should be reviewed — consider adding an index on `slide.channel.forum_id` (which the `index='btree_not_null'` on `forum_id` partially covers).

2. **Non-stored `forum_total_posts`**: Related field read live from `forum.forum.total_posts` on every form render. `forum.forum.total_posts` is a cached computed field in the `forum` module — it counts posts on the forum each time a post is created/closed. This is acceptable for single-record reads but may cause N+1 issues when rendering a list of channels.

3. **`store=True` on computed fields**: `slide_channel_id` (forum.forum) and `image_1920` (forum.forum) are stored, reducing read-time computation. However, `image_1920` is stored only when auto-synced from the channel; once manually overridden, the manual value is stored, and further channel image changes do not propagate unless the forum image is cleared.

4. **Image sync on create**: The `with_context(mail_create_nosubscribe=True)` on channel create may suppress important notifications for other modules listening on channel creation — but this is inherited behavior from the parent `website_slides` module.

---

## Edge Cases

| Scenario | Behavior |
|----------|---------|
| Channel created without a forum | No forum-related fields populated; forum button hidden |
| Forum unlinked from channel (`forum_id = False`) | Forum remains accessible at the forum level; record rules still apply to that forum's `slide_channel_ids` (now empty), making content visible only to officers |
| Forum changed to a different channel | Old forum set to `privacy='private'`, `authorized_group_id=slides_officer`; new forum set to public; posts on the old forum remain but are now restricted |
| Channel unpublished | All forum posts, tags, and forum itself become inaccessible to non-officers — `website_published=False` fails the record rule condition |
| Channel deleted with linked forum | No cascade delete; the forum remains but with no linked channel (`slide_channel_ids` becomes empty); record rules for non-officers then deny access |
| Forum manually set to private in UI | The form view hides the privacy field for course-linked forums (`invisible="slide_channel_id"`); attempting to set it via API directly (bypassing the UI) is possible but the record rules still use channel visibility |
| Empty `channel_id` in profile URL params | Method safely skips forum injection (`if post.get('channel_id')` guard) |
| Non-numeric `channel_id` in URL | `int()` raises `ValueError` — caught implicitly by the `if post.get('channel_id')` guard being falsy for non-numeric strings |

---

## Related Modules

- [Modules/website_slides](odoo-18/Modules/website_slides.md) — Course management, channel model, slide content
- [Modules/website_forum](odoo-18/Modules/website_forum.md) — Forum controller, post model, karma system
- [forum](forum.md) — Base forum ORM, post, tag models
- [Modules/website_profile](odoo-18/Modules/website_profile.md) — Profile page controller (call chain for `_prepare_user_profile_parameters`)
