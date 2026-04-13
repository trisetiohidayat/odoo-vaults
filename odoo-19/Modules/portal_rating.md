# Portal Rating

## Overview

- **Category**: Services
- **Depends**: `portal`, `rating`
- **License**: LGPL-3
- **Auto-install**: Yes

Adds customer rating capabilities to the [Modules/portal](modules/portal.md) (customer portal). Integrates ratings directly into the portal's discuss/chatter widget, allowing portal users to see and submit ratings from the customer-facing interface.

## Models

### `rating.rating` (Extended)

| Field | Type | Description |
|-------|------|-------------|
| `publisher_comment` | Text | Comment added by the publisher (business) on a rating. |
| `publisher_id` | Many2one (res.partner) | Partner who wrote the publisher comment. |
| `publisher_datetime` | Datetime | When the publisher comment was added. |

| Method | Description |
|--------|-------------|
| `create(vals_list)` | Calls `_synchronize_publisher_values()` before creating. |
| `write(vals)` | Calls `_synchronize_publisher_values()` before writing. |
| `_check_synchronize_publisher_values()` | Access control: either current user is in `website.group_website_restricted_editor`, or has write access to the rated document. Raises `AccessError` otherwise. |
| `_synchronize_publisher_values(values)` | When `publisher_comment` is set, auto-fills `publisher_datetime` (now) and `publisher_id` (current user). Also calls access check. |

### `mail.message` (Extended)

| Method | Description |
|--------|-------------|
| `_portal_get_default_format_properties_names(options)` | EXTENDS `mail` — Adds `'rating'` and `'rating_value'` to returned properties when `options.get('rating_include')` is truthy. |
| `_portal_message_format(properties_names, options)` | When `'rating'` is in `properties_names`, fetches the associated `rating.rating` record (by `message_id`) and formats it for frontend display. Also includes `rating_stats` from `rating_get_stats()` if available on the model. |
| `_portal_message_format_rating(rating_values)` | Formats a single rating's values for portal display: sets `publisher_avatar` URL, formats `publisher_datetime`, includes publisher name/comment. |

## Key Features

1. **Portal chatter integration**: Ratings are embedded in the portal chatter widget via `portal.assets_chatter` bundle.
2. **Publisher comments**: Business users can respond to ratings; the response is shown in the portal with publisher avatar and timestamp.
3. **Stats in portal**: If the rated model implements `rating_get_stats()`, those statistics are included in the portal message format.
4. **Access control**: Only users with website editor rights or write access to the document can add publisher comments.

## Assets

- `portal_rating/static/src/scss/portal_rating.scss` — Styling for portal rating display.
- `portal_rating/static/src/xml/portal_chatter.xml` — QWeb templates for portal chatter with ratings.
- `portal_rating/static/src/interactions/**/*` — Frontend interaction components.
- `portal.assets_chatter` bundle — Includes chatter frontend assets.
- `portal.assets_chatter_style` bundle — Includes rating styles.

## Related

- [Modules/rating](modules/rating.md) — Core rating framework (rating mixin, parent rating).
- [Modules/portal](modules/portal.md) — Portal customer access and chatter.
- [Modules/mail](modules/mail.md) — Message/thread system.
