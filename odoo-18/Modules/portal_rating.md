---
Module: portal_rating
Version: 18.0
Type: addon
Tags: #portal, #rating, #feedback, #publisher-comment
---

# portal_rating — Publisher Comments on Ratings

## Module Overview

**Category:** Portal
**Depends:** `portal`, `rating`
**License:** LGPL-3
**Installable:** True
**Auto-install:** True

Extends the rating system with publisher comments — allowing record owners or administrators to respond to customer ratings. Integrates rating data into the portal message format for display on customer-facing pages. The publisher comment fields are write-protected and require either the website restricted editor group or write access on the rated document.

## Data Files

- `data/rating_templates.xml` — QWeb templates for portal rating display
- `views/portal_chatter_templates.xml` — Portal chatter rating integration templates
- `views/mail_message_view.xml` — Message view with rating thread

## Static Assets

- `portal_rating/static/src/**/*` — Client-side JS/CSS for portal rating display

## Models

### `rating.rating` (`portal_rating.models.rating_rating`)

**Inheritance:** `rating.rating`

Extends ratings with publisher comment fields.

**Fields:**

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `publisher_comment` | Text | Yes | Publisher's response or comment on the rating |
| `publisher_id` | Many2one `res.partner` | Yes | Partner who wrote the publisher comment; indexed `btree_not_null` |
| `publisher_datetime` | Datetime | Yes | When the publisher comment was written; readonly |

**Methods:**

**`create(vals_list)`**
Auto-fills `publisher_id` from `self.env.user.partner_id` and `publisher_datetime` from `Datetime.now()` when `publisher_comment` is provided. Calls `_synchronize_publisher_values()` before write.

**`write(values)`**
Calls `_synchronize_publisher_values(values)` before writing. This ensures `publisher_datetime` and `publisher_id` are auto-set when `publisher_comment` is written.

**`_check_synchronize_publisher_values(values)`**
Security gate for publisher comment writes. Requires EITHER:
1. User has the `website.group_website_restricted_editor` group (website editor), OR
2. User has write access on the rated document (res_id/res_model record)
Raises `AccessError` if neither condition is met.

**`_synchronize_publisher_values(values)`**
Mutates `values` in-place:
- Sets `publisher_datetime = Datetime.now()` if not already provided
- Sets `publisher_id = self.env.user.partner_id.id` if not already provided

---

### `mail.thread` (`portal_rating.models.mail_thread`)

**Inheritance:** `mail.thread`

**Methods:**

**`_get_allowed_message_post_params()`**
Adds `rating_value` to the set of allowed parameters for portal message posting. Enables customers to submit a rating alongside a portal message.

---

### `mail.message` (`portal_rating.models.mail_message`)

**Inheritance:** `mail.message`

**Methods:**

**`_portal_get_default_format_properties_names(options)`**
If `options.get('rating_include')` is True, adds `'rating'` and `'rating_value'` to the default formatted properties set.

**`_portal_message_format(properties_names, options)`**
Portal formatting of messages for customer-facing display:
- If `'rating'` in `properties_names`, searches for linked `rating.rating` records via the `rating_ids` relation
- Formats each rating via `_portal_message_format_rating()`
- Calls `rating_get_stats()` on the rated record (if available) and attaches `rating_stats` to the output

**`_portal_message_format_rating(rating_values)`**
Formats a single rating dict for portal display:
- Sets `publisher_avatar` to the publisher partner's avatar URL (or False)
- Defaults `publisher_comment` to empty string if not present
- Formats `publisher_datetime` via `fields.Datetime.to_format()`
- Extracts `publisher_id` (id) and `publisher_name` (partner name)

---

## Controllers

### `PortalRating` (`portal_rating.controllers.portal_rating`)

Extends `portal.Controller` for portal rating page rendering.

**`__init__()`**
Extends `PORTAL_GRANTED_PERMISSION` with `rating.rating` — grants read access to rating records in portal context.

**`portal_ratings_rating_id(**kwargs)`**
Returns page data for a single rating record: rating data, access token check, and breadcrumbs.

**`_get_rating_page_values(user_id, rating_id, **kwargs)`**
Fetches the rating record with `access_token` validation. Returns rating data + partner info.

**`get_portal_rating_page(auth, **kwargs)`**
Wraps `_get_rating_page` with `@page_render`; renders `portal_rating.page_rating` QWeb template.

---

### `PortalChatter` (`portal_rating.controllers.portal_chatter`)

Extends portal chatter with rating submission support.

**`_portal_chatter_message_allowed_fields()`**
Extends the allowed fields list with `'rating_value'`.

**`_message_format_to_dict(message, properties_names)`**
Formats a message for portal display, optionally including rating data if `'rating_value'` is in `properties_names`.

---

## What It Extends

- `rating.rating` — publisher comment fields and synchronization logic
- `mail.thread` — allowed message post parameters for rating submission
- `mail.message` — portal message format with embedded rating data
- `portal.Controller` — rating page rendering
- `portal.PortalChatter` — rating in portal chatter

---

## Key Behavior

- **Publisher Comment Security**: `_check_synchronize_publisher_values` has a dual-path check: if the `website.group_website_restricted_editor` group exists and the user has it, access is granted. Otherwise, the user must have write access on the rated document's record.
- **Auto-Population**: When `publisher_comment` is set (via `create` or `write`) without an explicit `publisher_id`, the current user's partner is auto-assigned. If no `publisher_datetime` is given, `Datetime.now()` is used.
- **Portal Rating Stats**: `_portal_message_format` calls `rating_get_stats()` on the rated record if that method exists, adding aggregated rating statistics to the formatted message output.
- **Rating Image**: Portal rating display renders a star-based rating using the `rating_value` included in the formatted message properties.
- **Access Token**: Rating pages are accessible via `access_token` (portal share token) without authentication.

---

## See Also

- [[Modules/Rating]] (`rating`) — base rating system
- [[Modules/Portal]] (`portal`) — portal controller base
- [[Modules/Website]] (`website`) — website restricted editor group
