---
uuid: f6a7b8c9-d0e1-2f3a-4b5c-6d7e8f9a0b1c
tags:
  - odoo
  - odoo19
  - modules
  - portal
  - rating
  - customer
  - feedback
  - crm
---

# Portal Rating (`portal_rating`)

## Overview

| Attribute | Value |
|-----------|-------|
| **Module** | `portal_rating` |
| **Category** | Services |
| **Depends** | `portal`, `rating` |
| **Auto-install** | True |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Source** | `odoo/addons/portal_rating/` |

## Description

The `portal_rating` module extends Odoo's [Modules/portal](Modules/portal.md) with **customer rating capabilities** — allowing portal users (customers) to view, submit, and interact with ratings from the customer-facing interface. Ratings are displayed within the portal's chatter widget on records such as helpdesk tickets, project tasks, or any model that mixes in `rating.rating`.

The module works by:
- Extending `rating.rating` with **publisher comment** fields (allowing business users to respond to ratings)
- Extending `mail.message` to **embed rating data** in portal-formatted message records
- Providing **portal-accessible templates and styles** for rendering ratings in the customer portal

## Module Structure

```
portal_rating/
├── __init__.py
├── __manifest__.py
├── models/
│   └── mail_message.py          # mail.message portal extension
└── static/
    └── src/
        ├── scss/
        │   └── portal_rating.scss   # Rating display styles
        ├── xml/
        │   └── portal_chatter.xml   # Portal chatter QWeb templates
        └── interactions/             # Frontend JS interaction components
```

## Architecture

### Dependency Chain

```
rating.rating (core rating framework)
     ↑
     │ (inherits)
     │
mail.message (portal extension)
     ↑
     │ (portal integration)
     │
portal_rating.mail_message (adds rating to portal message format)
     ↑
     │ (customer portal uses)
     │
portal.assets_chatter (frontend bundle)
```

The `portal_rating` module does **not** add models — it only extends existing models from `rating` and `portal` to connect them together.

### Rating Data Flow

```
Portal User                  Odoo Backend                    Database
    │                              │                               │
    │ Submit rating (1-5 stars)     │                               │
    ├─────────────────────────────→│ Create rating.rating ─────────→│
    │                              │                               │
    │ View portal page             │                               │
    │ with chatter widget          │                               │
    ├─────────────────────────────→│                               │
    │                              │ _portal_message_format()      │
    │                              │   → Fetch rating.rating ──────→│
    │                              │   → Format for portal ──────────→│
    │                              │                               │
    │ Display in chatter           │                               │
    │←──────────────────────────────│ JSON response                 │
```

## Models

### `rating.rating` (Extension)

The core `rating.rating` model from the `rating` module is extended with three fields that enable **business users to respond to customer ratings**:

| Field | Type | Description |
|-------|------|-------------|
| `publisher_comment` | Text | The text of the publisher's (business) response to this rating |
| `publisher_id` | Many2one (`res.partner`) | The partner who wrote the publisher comment |
| `publisher_datetime` | Datetime | When the publisher comment was added |

These fields are managed entirely by the `rating` module's `write()` and `create()` methods via the `_synchronize_publisher_values()` hook:

```python
def write(self, vals):
    if 'publisher_comment' in vals:
        vals.update({
            'publisher_datetime': fields.Datetime.now(),
            'publisher_id': self.env.user.partner_id.id,
        })
    return super().write(vals)
```

When `publisher_comment` is set (not just changed), the system:
1. Records the current user as the publisher
2. Records the current datetime as the comment timestamp

### `mail.message` (Extension)

**File:** `models/mail_message.py`

The `mail.message` model is extended to include rating information in portal-formatted message data. This is the bridge between the `rating` system and the `portal` display layer.

#### `_portal_get_default_format_properties_names()`

Extends the list of properties to include when formatting messages for portal display:

```python
def _portal_get_default_format_properties_names(self, options=None):
    properties_names = super()._portal_get_default_format_properties_names()
    if options and options.get('rating_include'):
        properties_names |= {
            'rating',
            'rating_value',
        }
    return properties_names
```

When the portal formatter is called with `options={'rating_include': True}`, it will include rating fields in the output.

#### `_portal_message_format()`

The core formatting method that enriches message data with rating information:

```python
def _portal_message_format(self, properties_names, options=None):
    vals_list = super()._portal_message_format(properties_names, options=options)
    if 'rating' not in properties_names:
        return vals_list

    # Fetch rating records associated with these messages
    related_rating = self.env['rating.rating'].sudo().search_read(
        [('message_id', 'in', self.ids)],
        ["id", "publisher_comment", "publisher_id",
         "publisher_datetime", "message_id"]
    )

    # Map message_id → formatted rating
    message_to_rating = {
        rating['message_id'][0]: self._portal_message_format_rating(rating)
        for rating in related_rating
    }

    for message, values in zip(self, vals_list):
        values["rating_id"] = message_to_rating.get(message.id, {})

        # If the rated model has rating stats, include them
        record = self.env[message.model].browse(message.res_id)
        if hasattr(record, 'rating_get_stats'):
            values['rating_stats'] = record.sudo().rating_get_stats()

    return vals_list
```

Key behaviors:
- Uses `sudo()` to fetch ratings — portal users may not have direct access to rating records
- The `message_id` Many2one field on `rating.rating` links ratings to messages
- If the rated model implements `rating_get_stats()` (e.g., `helpdesk.ticket`), those statistics are included in the response

#### `_portal_message_format_rating()`

Formats a single rating's data for portal JSON output:

```python
def _portal_message_format_rating(self, rating_values):
    # Get publisher avatar URL
    publisher_id = rating_values['publisher_id']
    rating_values['publisher_avatar'] = (
        f'/web/image/res.partner/{publisher_id}/avatar_128/50x50'
        if publisher_id else ''
    )

    # Ensure comment is present
    rating_values['publisher_comment'] = rating_values['publisher_comment'] or ''

    # Format datetime for display
    rating_values['publisher_datetime'] = format_datetime(
        self.env, rating_values['publisher_datetime']
    )

    # Include partner name
    _, publisher_name = rating_values['publisher_id']
    rating_values['publisher_id'] = publisher_id
    rating_values['publisher_name'] = publisher_name

    return rating_values
```

This produces a portal-ready dictionary like:

```python
{
    'id': 42,
    'publisher_comment': 'Thank you for your feedback!',
    'publisher_id': 15,
    'publisher_name': 'Support Team',
    'publisher_avatar': '/web/image/res.partner/15/avatar_128/50x50',
    'publisher_datetime': 'Jan 15, 2024, 10:30 AM',
}
```

## Access Control

### Publisher Comment Permissions

Only authorized users can add publisher comments to ratings. The `rating.rating` model's `_check_synchronize_publisher_values()` method enforces this:

```python
def _check_synchronize_publisher_values(self, values):
    # Access check: either current user is website restricted editor,
    # OR has write access to the rated document
    if 'publisher_comment' in values:
        user = self.env.user
        if not (user.has_group('website.group_website_restricted_editor')
                or self.rating_ids.mapped('res_id')._check_access_rights('write')):
            raise AccessError(...)
```

This ensures:
- Website editors can respond to any rating (across all models)
- Users with write access to a specific record can respond to ratings on that record
- Portal users (customers) cannot add publisher comments

### Rating Visibility

Portal users can typically:
- **View** ratings on records they have portal access to
- **Submit** ratings through the portal (via `rating.rating`'s built-in portal submission mechanism)
- **Not** add publisher comments (only internal users can)

## Frontend Assets

### `portal.assets_chatter` Bundle

The portal chatter widget includes rating assets via the `portal.assets_chatter` bundle:

| Asset | Description |
|-------|-------------|
| `portal_rating.scss` | Styles for rating display in portal |
| `portal_chatter.xml` | QWeb templates for ratings in portal chatter |
| `portal_rating/interactions/**/*` | Frontend JS for rating submission |

### Portal Chatter with Ratings

The portal chatter widget displays:
1. **Rating stars**: Visual 1-5 star display of the rating value
2. **Rating date**: When the rating was submitted
3. **Publisher response**: If a publisher comment exists, it appears below the rating
4. **Publisher avatar and name**: Who responded
5. **Rating statistics**: If available (e.g., average rating, total count)

## Rating Statistics Integration

When the rated model implements `rating_get_stats()`, these statistics are included in the portal message format. This is provided by the `rating` module's mixin system.

### `rating.rating` Mixin

Models that support ratings mix in `rating.rating` (or `rating.parent.rating`):

```python
class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _inherit = ['mail.thread', 'rating.rating']
```

The `rating.rating` mixin provides:
- `rating_ids`: One2many of rating records
- `rating_get_stats()`: Returns average rating, total count, etc.
- Portal-accessible rating submission

When `helpdesk.ticket` is accessed via portal, the `portal_rating` extension automatically includes `rating_stats` in the message data:

```python
if hasattr(record, 'rating_get_stats'):
    values['rating_stats'] = record.sudo().rating_get_stats()
```

## Rating Submission Flow

```
Portal User                    Frontend JS                  Odoo Backend
    │                              │                              │
    │ Click star rating            │                              │
    ├─────────────────────────────→│                              │
    │                              │ POST rating.rating/create ───→│
    │                              │   values: {                   │
    │                              │     res_id: ticket_id,         │
    │                              │     res_model: 'helpdesk.ticket',
    │                              │     rating: 5,                 │
    │                              │     feedback: 'Great service!' │
    │                              │   }                           │
    │                              │←──────────────────────────────│
    │                              │   rating record created       │
    │                              │                              │
    │ View updated chatter         │                              │
    │ with new rating             │                              │
    │←──────────────────────────────│                              │
```

The rating submission itself is handled by the `rating` module's standard mechanism; `portal_rating` only adds the portal display layer.

## Publisher Response Flow

```
Internal User (Helpdesk Agent)        Odoo Backend                    Database
    │                                     │                              │
    │ View ticket with low rating        │                              │
    ├────────────────────────────────────→│                              │
    │                                     │                              │
    │ Add publisher comment               │                              │
    │ "We're sorry to hear..."            │                              │
    ├────────────────────────────────────→│ rating.write({               │
    │                                     │   publisher_comment: '...',   │
    │                                     │   publisher_id: user.partner │
    │                                     │ }) ───────────────────────→│
    │                                     │                              │
    │ Confirm save                       │                              │
    │                                     │                              │
    │                                     │                              │
Portal User (Customer)                 │                              │
    │                                     │                              │
    │ Refresh portal page                 │                              │
    │                                     │                              │
    ├────────────────────────────────────→│                              │
    │                                     │ _portal_message_format()      │
    │                                     │   → Include publisher_comment │
    │                                     │←─────────────────────────────│
    │                                     │                              │
    │ See response in portal chatter     │                              │
    │ with agent avatar and timestamp     │                              │
    │←────────────────────────────────────│                              │
```

## Template Structure

The portal rating templates follow Odoo's standard QWeb pattern. A simplified view of the portal chatter with ratings:

```xml
<!-- Portal chatter with rating -->
<div class="o_portal_chatter">
    <div class="o_rating_message">
        <div class="o_rating_stars">
            <t t-foreach="range(1, 6)" t-as="star">
                <i t-attf-class="fa fa-star#{'s' if star <= rating_value else '-o'}"/>
            </t>
        </div>
        <span class="o_rating_date" t-esc="rating_date"/>

        <t t-if="rating_id.get('publisher_comment')">
            <div class="o_publisher_response">
                <img t-attf-src="{{ rating_id.get('publisher_avatar') }}"
                     class="o_publisher_avatar"/>
                <div class="o_publisher_info">
                    <span class="o_publisher_name"
                          t-esc="rating_id.get('publisher_name')"/>
                    <span class="o_publisher_date"
                          t-esc="rating_id.get('publisher_datetime')"/>
                    <p class="o_publisher_comment"
                       t-esc="rating_id.get('publisher_comment')"/>
                </div>
            </div>
        </t>
    </div>
</div>
```

## Use Cases

The `portal_rating` module enables several customer-facing workflows:

### 1. Helpdesk Ticket Rating

When a helpdesk ticket is closed, customers are invited to rate the service. The rating appears in the portal chatter:

- Customer submits 3 stars with feedback: "Response could be faster"
- Helpdesk agent responds: "Thank you for your feedback. We'll work on improving response times."
- The customer sees the response in the portal

### 2. Project Task Completion Rating

When a project task is marked done, the portal user can rate the task completion:

- Customer rates 5 stars: "Task completed perfectly"
- No publisher comment needed (already satisfied)

### 3. Service Rating with Aggregate Statistics

When viewing a service ticket, the portal shows aggregate rating statistics:

```json
{
  "rating_stats": {
    "avg": 4.2,
    "count": 15,
    "percentage": {
      "5": 60,
      "4": 20,
      "3": 10,
      "2": 5,
      "1": 5
    }
  }
}
```

This helps customers gauge service quality from other customers' experiences.

## Related

- [Modules/rating](Modules/rating.md) — Core rating framework (parent rating, rating mixin, statistics)
- [Modules/portal](Modules/portal.md) — Customer portal access (chatter, message formatting)
- [Modules/mail](Modules/mail.md) — Message and thread system
- [Modules/helpdesk](Modules/helpdesk.md) — Helpdesk module (uses portal ratings extensively)
- [Modules/project](Modules/Project.md) — Project management (uses ratings for task completion)
