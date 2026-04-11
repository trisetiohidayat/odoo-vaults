# Module/rating

Customer Rating module. Allows customers to give ratings on records that support rating functionality. Integrated with the mail/chatter system to display ratings and feedback directly in the discussion thread.

**Tags:** `#odoo`, `#odoo19`, `#rating`, `#mail`, `#customer-feedback`, `#portal`

---

## Overview

The `rating` module provides a complete star-rating (0-5) feedback system integrated with Odoo's messaging infrastructure. It enables customers (via portal) or employees to rate records, with feedback displayed in the chatter and aggregated statistics computed automatically.

**Key Architecture Decisions:**
- `rating.rating` is the central model storing all ratings
- Two mixins (`rating.mixin` and `rating.parent.mixin`) add rating statistics to models
- The `consumed` flag distinguishes submitted ratings from pending invitation tokens
- Parent linking via `_rating_get_parent_field_name()` supports hierarchical rating aggregation (e.g., ratings on tasks roll up to parent project)
- Star rating is converted to text labels (`top`/`ok`/`ko`/`none`) via `rating_data` constants

**Module Dependencies:** `mail`

**License:** LGPL-3

---

## rating_data.py - Constants and Utility Functions

**File:** `rating/models/rating_data.py`

This module defines all rating-related constants, thresholds, and pure conversion functions. These constants are shared across all models in the module.

### Rating Threshold Constants

```python
RATING_AVG_TOP = 3.66   # Threshold for "top" average rating label
RATING_AVG_OK = 2.33    # Threshold for "ok" average rating label
RATING_AVG_MIN = 1      # Minimum threshold for "ko" average

RATING_LIMIT_SATISFIED = 4  # Rating >= 4 is "satisfied"
RATING_LIMIT_OK = 3         # Rating >= 3 is "ok"
RATING_LIMIT_MIN = 1        # Rating >= 1 is valid (not "none")

RATING_HAPPY_VALUE = 5      # Star rating: 5 = happy
RATING_NEUTRAL_VALUE = 3    # Star rating: 3 = neutral
RATING_UNHAPPY_VALUE = 1   # Star rating: 1 = unhappy
RATING_NONE_VALUE = 0       # Star rating: 0 = not rated yet
```

### Rating Text Selection (Selection Field Labels)

```python
RATING_TEXT = [
    ('top', 'Happy'),      # Rating 4-5
    ('ok', 'Neutral'),    # Rating 3
    ('ko', 'Unhappy'),    # Rating 1-2
    ('none', 'Not Rated yet'),  # Rating 0
]
```

### Operator Mapping

Used in `_search_rating_avg` methods to support search operators dynamically:

```python
OPERATOR_MAPPING = {
    'in': lambda elem, container: elem in container,
    'not in': lambda elem, container: elem not in container,
    '<': operator.lt,
    '<=': operator.le,
    '>': operator.gt,
    '>=': operator.ge,
}
```

### Conversion Functions

#### `_rating_assert_value(rating_value)`
Asserts that a rating value is between 0 and 5 (inclusive). Used internally to validate inputs before conversion.

#### `_rating_to_grade(rating_value) -> Literal['great', 'okay', 'bad']`
Converts a numeric rating to a satisfaction grade for satisfaction percentage computation:
- `rating >= 4` -> `'great'`
- `rating >= 3` -> `'okay'`
- `rating < 3` -> `'bad'`

Note: The thresholds are different from `_rating_to_text` (which uses `RATING_LIMIT_MIN=1`, returning `'ko'` for ratings 1-2).

#### `_rating_to_text(rating_value) -> Literal['top', 'ok', 'ko', 'none']`
Converts a numeric rating to a human-readable text label for the `rating_text` selection field:
- `rating >= 4` -> `'top'` (Happy)
- `rating >= 3` -> `'ok'` (Neutral)
- `rating >= 1` -> `'ko'` (Unhappy)
- `rating == 0` -> `'none'` (Not Rated yet)

**XSS Prevention:** This function is safe to use in templates since it only returns pre-defined enum values, never raw user input.

#### `_rating_to_threshold(rating_value) -> Literal[0, 1, 3, 5]`
Maps a rating value to discrete image threshold values used for displaying star images. Returns the rounded star value (1, 3, or 5) rather than the raw rating for image selection purposes.

#### `_rating_avg_to_text(rating_avg) -> Literal['top', 'ok', 'ko', 'none']`
Converts an average rating to text label using `float_compare` for precision-safe comparisons:
- `avg >= 3.66` -> `'top'`
- `avg >= 2.33` -> `'ok'`
- `avg >= 1` -> `'ko'`
- `avg < 1` -> `'none'`

Uses `odoo.tools.float_utils.float_compare` with precision 2 for safe float comparison.

---

## rating.py - The Core Rating Model

**File:** `rating/models/rating.py`
**Model:** `rating.rating`
**Inherits:** `BaseModel` (no parent inheritance)

The central model representing a single rating instance. Each rating is attached to a specific record (via `res_model`/`res_id`) and optionally to a parent record (via `parent_res_model`/`parent_res_id`) for hierarchical aggregation.

### Field Definitions

#### Core Identity Fields

```python
res_name = fields.Char(string='Resource name', compute='_compute_res_name', store=True)
```
Computed field storing the `display_name` of the rated resource. `store=True` ensures it can be searched/filtered. Uses `sudo()` to fetch the target record name because the rating user may not have direct access rights to the rated object. Fallback format: `'{model}/{id}'` if name cannot be retrieved.

```python
res_model_id = fields.Many2one('ir.model', 'Related Document Model', index=True, ondelete='cascade')
```
Many2one to `ir.model` representing the model of the rated object. Indexed and cascade-deleted when the ir.model record is deleted.

```python
res_model = fields.Char(string='Document Model',
                       related='res_model_id.model', store=True, index=True, readonly=True)
```
Char storing the model name (e.g., `'sale.order'`), derived from `res_model_id`. Stored and indexed for efficient filtering in `_rating_domain` queries.

```python
res_id = fields.Many2oneReference(string='Document', model_field='res_model', required=True, index=True)
```
`Many2oneReference` field - stores the integer ID of the rated record. The `model_field='res_model'` parameter links this to the model name in `res_model`. Required, indexed.

```python
resource_ref = fields.Reference(
    string='Resource Ref', selection='_selection_target_model',
    compute='_compute_resource_ref', readonly=True)
```
A `Reference` field (dynamic x2one) that allows direct programmatic access to the rated record object. Computed based on `res_model` and `res_id`. If the model is not in `self.env`, returns `None`.

#### Parent Linking Fields

These fields enable hierarchical rating aggregation. For example, task ratings roll up to project ratings.

```python
parent_res_name = fields.Char('Parent Document Name', compute='_compute_parent_res_name', store=True)
parent_res_model_id = fields.Many2one('ir.model', 'Parent Related Document Model',
                                      index=True, ondelete='cascade')
parent_res_model = fields.Char('Parent Document Model', store=True,
                               related='parent_res_model_id.model', index=True, readonly=False)
parent_res_id = fields.Integer('Parent Document', index=True)
parent_ref = fields.Reference(
    string='Parent Ref', selection='_selection_target_model',
    compute='_compute_parent_ref', readonly=True)
```

Parent data is populated by `_find_parent_data()` during `create()` and `write()`. The method looks for `_rating_get_parent_field_name()` on the rated record to determine the parent relation field.

#### Rating Value Fields

```python
rating = fields.Float(string="Rating Value", aggregator="avg", default=0)
```
The numeric rating value (0-5). `aggregator="avg"` enables database-level averaging in `_read_group`. Default value is 0 (not rated).

```python
rating_text = fields.Selection(rating_data.RATING_TEXT, string='Rating', store=True,
                               compute='_compute_rating_text', readonly=True)
```
The human-readable text label (`top`/`ok`/`ko`/`none`). Computed from `rating` value via `_compute_rating_text`, stored for efficient search/display. `readonly=True` enforces that it can only be derived, never set directly.

```python
rating_image = fields.Binary('Image', compute='_compute_rating_image')
rating_image_url = fields.Char('Image URL', compute='_compute_rating_image')
```
Binary image and URL for the star icon. Computed from `_get_rating_image_filename()` which maps rating to threshold-based PNG files (`rating_0.png`, `rating_1.png`, `rating_3.png`, `rating_5.png`). Images are stored as base64-encoded PNGs read from `rating/static/src/img/`.

#### Actor Fields (Who rates whom)

```python
rated_partner_id = fields.Many2one('res.partner', string="Rated Operator")
rated_partner_name = fields.Char(related="rated_partner_id.name")
partner_id = fields.Many2one('res.partner', string='Customer')
```
- `rated_partner_id`: The operator (e.g., salesperson, helpdesk agent) being rated. Determined by `_rating_get_operator()` on the rated record (usually via `user_id.partner_id`).
- `partner_id`: The customer/partner who submitted the rating. Determined by `_rating_get_partner()` on the rated record (usually via `partner_id`).

#### Feedback and Metadata

```python
feedback = fields.Text('Comment')
```
Free-text feedback/comment associated with the rating. Stored as plain text.

```python
message_id = fields.Many2one('mail.message', string="Message",
                              index=True, ondelete='cascade')
```
Link to the chatter message where the rating was posted. Cascade-deleted when the message is deleted. Used to correlate ratings with discussion threads.

```python
is_internal = fields.Boolean('Visible Internally Only', readonly=False,
                              related='message_id.is_internal', store=True)
```
Synced from `message_id.is_internal`. Ratings linked to internal notes are also internal. Stored so it can be used in domain filters.

```python
access_token = fields.Char('Security Token', default=_default_access_token)
```
UUID-based security token for public rating submission via portal. Generated via `uuid.uuid4().hex` on default. Reset on `reset()` action.

```python
consumed = fields.Boolean(string="Filled Rating")
```
**Critical flag.** `False` = pending rating invitation (token created but not yet submitted). `True` = rating has been submitted with actual rating value. Only consumed ratings are included in statistics computation.

```python
rated_on = fields.Datetime(string="Rated On")
```
Timestamp when the rating was actually submitted (set when `rating` or `feedback` is first written, not on creation).

```python
create_date = fields.Datetime(string="Submitted on")
```
Standard Odoo `create_date` field, showing when the rating record was created (not necessarily when submitted).

### Database Constraints

```python
_rating_range = models.Constraint(
    'check(rating >= 0 and rating <= 5)',
    'Rating should be between 0 and 5',
)
```
PostgreSQL CHECK constraint ensuring rating values are always valid (0-5).

### Database Indexes

```python
_consumed_idx = models.Index('(res_model, res_id, write_date) WHERE consumed IS TRUE')
_parent_consumed_idx = models.Index('(parent_res_model, parent_res_id, write_date) WHERE consumed IS TRUE')
```
Partial indexes specifically optimized for the most common query patterns: filtering consumed ratings by resource or parent resource, ordered by write date. These partial indexes significantly improve performance for statistics queries.

### Model Attributes

```python
_order = 'write_date desc, id desc'
```
Default ordering: most recently updated ratings first. This ordering also affects `_compute_rating_last_value` which uses `ORDER BY write_date DESC, id DESC` via `array_agg` to get the most recent rating.

```python
_rec_name = 'res_name'
```
The record name for display purposes is the resource name (the rated object's name).

### Method Signatures

#### `_default_access_token(self) -> str`
Class method (`@api.model`) returning a new UUID hex string for the `access_token` field default. Called each time a new rating record is created (via `reset()` or on new rating creation).

#### `_selection_target_model(self) -> list[tuple]`
Returns all available models in the system (`ir.model` records) for populating the `Reference` selection dropdown for `resource_ref` and `parent_ref` fields.

#### `_compute_res_name(self)`
Computes the `display_name` of the rated resource. Uses `sudo()` because the rating user may lack direct read access to the rated object. Falls back to `'{model}/{id}'` format if the name cannot be retrieved. The `store=True` on the field triggers automatic recomputation when `res_model` or `res_id` changes.

#### `_compute_resource_ref(self)`
Sets `resource_ref` to the dynamic reference string `'model_name,id'` if the model is available in the environment, otherwise `None`.

#### `_compute_parent_ref(self)`
Same pattern as `_compute_resource_ref` but for the parent reference.

#### `_compute_parent_res_name(self)`
Computes parent resource display name similarly to `_compute_res_name`.

#### `_get_rating_image_filename(self) -> str`
Returns the PNG filename for the star image based on the current rating threshold: `'rating_0.png'`, `'rating_1.png'`, `'rating_3.png'`, or `'rating_5.png'`.

#### `_compute_rating_image(self)`
Reads the star PNG image from `rating/static/src/img/` using `file_open` with extension filter `('.png',)`. Sets both `rating_image_url` (path string) and `rating_image` (base64 binary). Catches `OSError` gracefully, setting both to `False` if the file is missing. The `rating_image_url` is used in HTML rendering via email templates (`mail_notification_light` layout) while `rating_image` is for binary display in form views.

#### `_compute_rating_text(self)`
Maps the numeric `rating` value to the text enum via `rating_data._rating_to_text()`.

#### `create(vals_list) -> recordset`
Multi-create method. For each vals dict: if `res_model_id` and `res_id` are provided, auto-fills parent data via `_find_parent_data()`. If `rating` or `feedback` is being set, populates `rated_on` timestamp to record submission time.

#### `write(vals) -> bool`
Standard write. Same parent-data and `rated_on` logic as `create()`.

#### `unlink(self) -> bool`
Overridden to also delete associated chatter messages. Uses `OPW-2181568` reference indicating a historical security fix. Calls `mail.message.unlink()` for all messages linked to these ratings before calling `super().unlink()`.

#### `_find_parent_data(values: dict) -> dict`
Determines the parent resource for a rating. Looks for `_rating_get_parent_field_name()` method on the rated record model. If found, reads the parent model and ID, then returns dict with `parent_res_model_id` and `parent_res_id`. Returns empty dicts if no parent field exists. This is called automatically during `create()` and `write()` when `res_model_id` and `res_id` are present.

#### `reset(self) -> bool`
Resets a rating to its initial unconsumed state: sets `rating=0`, generates a new `access_token`, clears `feedback`, sets `consumed=False`. This enables the same token to be reused for a new rating invitation.

#### `action_open_rated_object(self) -> dict`
Returns an `ir.actions.act_window` to open the rated record (using `res_model` and `res_id`). Uses `ensure_one()` since it is typically called on a single rating.

#### `_classify_by_model(self) -> dict`
Classifies ratings into groups by their `res_model` for efficient batch processing. Returns a dict: `{res_model: {'ratings': recordset, 'record_ids': [ids]}}`. Only includes ratings that have both `res_model` and `res_id` set. Useful for batch computation of rating statistics across multiple records of different models.

#### `_to_store_defaults(target) -> list[str]`
Returns default fields for the `Store` (mail Discuss API): `["rating", "rating_image_url", "rating_text"]`. Used when publishing rating data through the mail notification store.

---

## rating_mixin.py - Rating Statistics Mixin

**File:** `rating/models/rating_mixin.py`
**Model:** `rating.mixin` (Abstract)
**Inherits:** `mail.thread`

Abstract mixin that adds rating statistics to any model that inherits from `mail.thread`. Use this mixin on models that users rate directly (e.g., `sale.order`, `helpdesk.ticket`, `project.task`).

### Field Definitions

#### Core Statistics Fields

```python
rating_last_value = fields.Float(
    'Rating Last Value',
    groups='base.group_user',
    compute='_compute_rating_last_value',
    compute_sudo=True,
    store=True,
    aggregator="avg"
)
```
The most recent rating value for each record. `store=True` for database performance. `compute_sudo=True` runs the computation as superuser because rating data may not be accessible to all users. `aggregator="avg"` enables efficient read_group averaging. The aggregation is somewhat redundant here since only one value is returned per record.

**Performance Note (L4):** This field uses raw SQL with `array_agg` to efficiently fetch the most recent rating in a single query per model, bypassing ORM `_read_group`. See `_compute_rating_last_value` for details.

```python
rating_last_feedback = fields.Text(
    'Rating Last Feedback',
    groups='base.group_user',
    related='rating_ids.feedback'
)
```
Related field pointing to the `feedback` of the latest rating in `rating_ids`. Uses the One2many ordering from `_order` on `rating.rating` (`write_date desc, id desc`) so the first record is the most recent.

```python
rating_last_image = fields.Binary(
    'Rating Last Image',
    groups='base.group_user',
    related='rating_ids.rating_image'
)
```
Related field for the star image of the most recent rating.

```python
rating_last_text = fields.Selection(
    string="Rating Text",
    groups='base.group_user',
    related="rating_ids.rating_text"
)
```
Related field for the text label of the most recent rating.

#### Aggregation Fields

```python
rating_count = fields.Integer(
    'Rating count',
    compute="_compute_rating_stats",
    compute_sudo=True
)
```
Count of consumed ratings with rating >= 1 for this record.

```python
rating_avg = fields.Float(
    "Average Rating",
    groups='base.group_user',
    compute='_compute_rating_stats',
    compute_sudo=True,
    search='_search_rating_avg'
)
```
Average rating value (consumed ratings >= 1 only). Has a search method for filtering records by average rating. `compute_sudo=True` ensures statistics are visible even to users without direct rating access.

```python
rating_avg_text = fields.Selection(
    rating_data.RATING_TEXT,
    groups='base.group_user',
    compute='_compute_rating_avg_text',
    compute_sudo=True
)
```
Text label for the average rating. Uses `float_compare` with precision 2 against thresholds (3.66, 2.33, 1).

```python
rating_percentage_satisfaction = fields.Float(
    "Rating Satisfaction",
    compute='_compute_rating_satisfaction',
    compute_sudo=True
)
```
Percentage of "great" ratings (>= 4 stars). Returns `-1` when there are no ratings (indicating "no data" rather than 0%).

### Method Signatures

#### `_compute_rating_last_value(self)`
**Performance-critical method (L4).** Uses raw SQL with `array_agg` instead of ORM `_read_group` to get the most recent rating per record. The reason: `_read_group` does not support `ORDER BY` within aggregate functions, but `array_agg` with `ORDER BY` is needed to get the latest rating value efficiently in a single query.

```python
self.flush_model(['rating_ids'])
self.env['rating.rating'].flush_model(['consumed', 'rating'])
if not self.ids:
    self.rating_last_value = 0
    return
self.env.cr.execute("""
    SELECT
        array_agg(rating ORDER BY write_date DESC, id DESC) AS "ratings",
        res_id as res_id
    FROM "rating_rating"
    WHERE
        res_model = %s
    AND res_id in %s
    AND consumed = true
    GROUP BY res_id""", [self._name, tuple(self.ids)])
read_group_raw = self.env.cr.dictfetchall()
rating_by_res_id = {e['res_id']: e['ratings'][0] for e in read_group_raw}
for record in self:
    record.rating_last_value = rating_by_res_id.get(record.id, 0)
```

Key points:
- `flush_model()` ensures the rating data is synced to the database before raw SQL query
- Parameterized SQL prevents SQL injection (uses `%s` with tuple, not string formatting)
- `ORDER BY write_date DESC, id DESC` within `array_agg` ensures array[0] is the most recent
- Falls back to `0` if no ratings exist for a record

#### `_compute_rating_stats(self)`
Computes both `rating_count` and `rating_avg` in a single `_read_group` call using the `Domain` API for normalization. Filters to `consumed=True` and `rating >= RATING_LIMIT_MIN (1)`. Uses `['__count', 'rating:avg']` aggregates.

#### `_search_rating_avg(self, operator, value)`
Search method enabling filtering records by their average rating value. Uses `OPERATOR_MAPPING` to support operators (`>`, `>=`, `<`, `<=`, `=`, `!=`). Executes a `sudo()._read_group` to find matching record IDs.

**Edge Case (L3):** If the operator is not in `OPERATOR_MAPPING`, returns `NotImplemented` which causes the search to silently fail (Odoo returns no results). Valid operators are: `in`, `not in`, `<`, `<=`, `>`, `>=`.

#### `_compute_rating_avg_text(self)`
Computes the average rating text label from `rating_avg` via `_rating_avg_to_text()`.

#### `_compute_rating_satisfaction(self)`
Computes satisfaction percentage separately from `_compute_rating_stats` because it requires a different `_read_group` aggregation (grouping by rating value to count grade distribution). Uses `_rating_to_grade()` to classify each rating value into 'great'/'okay'/'bad'.

#### `write(vals) -> bool`
Overridden to synchronize rating metadata when the rated record changes:
1. If `_rec_name` field (usually `name`) changes, triggers recomputation of `res_name` on all linked ratings via `add_to_compute`
2. If the parent relation field changes, updates `parent_res_id` on all linked ratings via `write()`

Uses `self.sudo()` to access potentially inaccessible ratings.

#### `_rating_get_parent_field_name(self) -> str|None`
Returns the name of the parent relation field on the implementing model. Override in subclasses to enable parent linking (e.g., return `'project_id'` on `project.task`). Default returns `None` (no parent).

#### `_rating_domain(self) -> Domain`
Returns the normalized domain for selecting ratings related to the current model:
```python
Domain([('res_model', '=', self._name), ('res_id', 'in', self.ids), ('consumed', '=', True)])
```
This is the base domain for all statistics computations. Subclasses may override to add filters.

#### `_rating_get_repartition(add_stats=False, domain=None) -> dict`
Computes the distribution of ratings by value (1-5 stars). Returns a dict mapping rating values to counts. If `add_stats=True`, also includes `avg` and `total`. Uses `float_round` to round ratings to 1 decimal place before counting.

#### `rating_get_grades(domain=None) -> dict`
Returns grade distribution (`{'great': N, 'okay': N, 'bad': N}`) based on rating value classification. The grade thresholds are different from text thresholds: `>= 4` = great, `>= 3` = okay, `< 3` = bad.

#### `rating_get_stats(domain=None) -> dict`
Returns comprehensive statistics: `avg`, `total`, `percent` (distribution in percentage for values 1-5). Computed by calling `_rating_get_repartition(add_stats=True)`.

#### `_rating_get_stats_per_record(domain=None) -> dict`
Computes per-record statistics. Returns a dict mapping `res_id` to `{"total", "avg", "percent": {1: pct, 2: pct, 3: pct, 4: pct, 5: pct}}`. Uses `read_group` with `groupby=['res_id', 'rating']` to efficiently fetch all records in one query.

#### `_allow_publish_rating_stats(self) -> bool`
Override to allow/disallow publishing rating statistics. Default returns `False`. When `True`, statistics are published in the mail Discuss store (see `mail_message.py`'s `_to_store`).

---

## rating_parent_mixin.py - Parent-level Aggregation Mixin

**File:** `rating/models/rating_parent_mixin.py`
**Model:** `rating.parent.mixin` (Abstract)
**Inherits:** `BaseModel` (no parent inheritance)

Abstract mixin for parent-level rating aggregation. Use this on models that serve as containers for rateable child records (e.g., `project.project` aggregates ratings from `project.task`).

### Class Attributes

```python
_rating_satisfaction_days = False  # or an integer like 30
```
If set to an integer, limits satisfaction computation to ratings created/updated within the last N days. If `False`, all ratings are included. This allows "recent satisfaction" tracking without manual data cleanup.

**L4 — Implementation Detail:** The time window filter uses `write_date` (not `create_date`) of the rating record. This means that if a customer updates their feedback, the rating's `write_date` is refreshed and it re-enters the recent window. This is intentional: re-submitted ratings should be counted in the "recent" metric as they reflect active engagement. However, it also means that a stale rating that is merely touched (no actual change) will incorrectly be counted as recent. Subclasses like `project.project` do not override this attribute, so they include all historical ratings.

### Field Definitions

```python
rating_ids = fields.One2many(
    'rating.rating', 'parent_res_id',
    string='Ratings',
    bypass_search_access=True,
    groups='base.group_user',
    domain=lambda self: [('parent_res_model', '=', self._name)]
)
```
One2many to ratings linked via `parent_res_id`. Key parameters:
- `bypass_search_access=True`: Allows searching ratings even if the user lacks direct access to rating records
- `groups='base.group_user'`: Only visible to internal users (not portal/public)
- `domain`: Automatically filters to ratings where `parent_res_model` matches the current model

**L4 — `bypass_search_access=True` and the Portal Inconsistency:** There is a subtle security vs. UX trade-off here. `rating_ids` on `rating.parent.mixin` has `bypass_search_access=True` but is restricted to `base.group_user`. Portal users (without `base.group_user`) will not see the `rating_ids` field at all, so the bypass has no effect for them. However, internal users (with `base.group_user`) benefit: they can browse the parent record's rating_ids even if they don't have direct `rating.rating` model permissions (which would be an unusual configuration). The real purpose is to allow the ORM to resolve `parent.rating_ids` in computed fields without triggering ACL errors, regardless of how the `rating.rating` access rights are configured.

```python
rating_percentage_satisfaction = fields.Integer(
    "Rating Satisfaction",
    compute="_compute_rating_percentage_satisfaction",
    compute_sudo=True,
    store=False,
    help="Percentage of happy ratings"
)
```
Integer (0-100) representing percentage of ratings >= 4 stars. `store=False` because it is computed from `rating_ids`. Returns `-1` when there are no ratings (distinct from 0%).

```python
rating_count = fields.Integer(
    string='# Ratings',
    compute="_compute_rating_percentage_satisfaction",
    compute_sudo=True
)
```
Total count of consumed ratings >= 1.

```python
rating_avg = fields.Float(
    'Average Rating',
    groups='base.group_user',
    compute='_compute_rating_percentage_satisfaction',
    compute_sudo=True,
    search='_search_rating_avg'
)
```
Average rating across all child ratings. Has a search method.

```python
rating_avg_percentage = fields.Float(
    'Average Rating (%)',
    groups='base.group_user',
    compute='_compute_rating_percentage_satisfaction',
    compute_sudo=True
)
```
Average rating expressed as a percentage (divide by 5). Useful for progress bar widgets.

### Method Signatures

#### `_compute_rating_percentage_satisfaction(self)`
Computes `rating_count`, `rating_percentage_satisfaction`, `rating_avg`, and `rating_avg_percentage` from all consumed child ratings. Uses `_read_group` with `groupby=['parent_res_id', 'rating']` to efficiently aggregate.

The computation:
1. Builds domain with optional time filter based on `_rating_satisfaction_days`
2. Executes `_read_group` to get rating distribution per parent
3. Classifies each rating into 'great'/'okay'/'bad' using `_rating_to_grade()`
4. Computes satisfaction: `great_count * 100 / total_count`
5. Computes average: `sum(rating * count) / total_count`

#### `_search_rating_avg(self, operator, value)`
Search method for filtering parent records by average rating. Uses `sudo()._read_group` with the aggregation `['rating:avg']` to find parents whose average rating matches the criteria. Returns `NotImplemented` for unsupported operators (same as `rating.mixin`).

---

## mail_thread.py - Rating Integration with Mail Thread

**File:** `rating/models/mail_thread.py`
**Model:** `mail.thread` (Inherited)

Extends `mail.thread` to add rating support. The `rating.mixin` inherits from `mail.thread`, so models inheriting from `rating.mixin` automatically get these rating-enhanced thread capabilities.

### Field Definitions

```python
rating_ids = fields.One2many(
    'rating.rating', 'res_id',
    string='Ratings',
    groups='base.group_user',
    domain=lambda self: [('res_model', '=', self._name)],
    bypass_search_access=True
)
```
One2many to ratings attached directly to this record (via `res_id`). Same parameters as `rating.parent.mixin`'s `rating_ids`. This is the inverse side of the `rating.rating.res_id` reference.

**L4 — `bypass_search_access=True`:** This flag allows users to view and search rating records even if they lack direct read access to the `rating.rating` model (e.g., portal users can see ratings in the chatter thread without needing `base.group_user`). It does not bypass record-level ACLs — only model-level access checks for search/browse operations. This is critical for the portal rating flow where public users must be able to browse ratings attached to their records.

### Method Signatures

#### `unlink(self)`
Overridden to cascade-delete all ratings linked to the deleted record. Executes as `super().unlink()` first (to benefit from parent model deletion cascades), then searches and deletes all ratings where `res_model` matches and `res_id` is in the deleted record IDs. Uses `sudo()` because rating records may not be directly accessible to the current user.

**L4 — Cascade Isolation:** The `sudo()` call ensures that even if the current user lacks direct `rating.rating` read permissions, the cascade deletion still executes. Without `sudo()`, attempting to search for ratings in a record the user can access (e.g., via portal) but without `base.group_user` would raise `AccessError`. Note that this does not bypass record rules — it bypasses only ACL model-level checks.

**L4 — Missing `_get_message_create_ignore_field_names`:** This override on `mail.thread` adds `rating_id` to the set of field names that `message_post` should ignore when creating messages. Without this, Odoo would attempt to write `rating_id` as a regular field on `mail.message`, causing an error since `rating_id` is not a direct column on that model. This is a counterpart to `_get_allowed_message_params`, which instead whitelists `rating_value` as an allowed parameter.

#### `_rating_apply_get_default_subtype_id(self) -> int`
Returns the XML ID of the default message subtype (`mail.mt_comment`). Used when posting rating messages to the chatter.

#### `_rating_get_operator(self) -> res.partner`
Returns the partner being rated. Default implementation: if the record has a `user_id` field with a linked partner, returns that partner. Otherwise returns an empty recordset. Override to customize (e.g., assign ticket to agent and rate the agent).

#### `_rating_get_partner(self) -> res.partner`
Returns the partner submitting the rating. Default implementation: if the record has a `partner_id` field, returns that partner. Otherwise returns an empty recordset. Override for custom identification (e.g., contact person on a project).

#### `_rating_get_access_token(self, partner=None) -> str`
**Rating Invitation Flow.** Returns the access token for rating this record. If a rating token already exists for the given partner (and is not yet consumed), returns that token. Otherwise creates a new rating record with a fresh token.

```python
def _rating_get_access_token(self, partner=None):
    self.check_access('read')  # Access check before any operation
    if not partner:
        partner = self._rating_get_partner()
    rated_partner = self._rating_get_operator()
    # Find existing unconsumed rating for this partner
    rating = next(
        (r for r in self.rating_ids.sudo()
         if r.partner_id.id == partner.id and not r.consumed),
        None)
    if not rating:
        # Create new rating invitation
        rating = self.env['rating.rating'].sudo().create({
            'partner_id': partner.id,
            'rated_partner_id': rated_partner.id,
            'res_model_id': self.env['ir.model']._get_id(self._name),
            'res_id': self.id,
            'is_internal': False,
        })
    return rating.access_token
```

**Security Note (L4):** This method is typically called from templates (`check_access('read')` is performed). Uses `sudo()` for creating the rating since portal users may need to trigger this flow. The caller (template) should perform proper access checks before calling this method.

#### `rating_send_request(self, template, lang=False, force_send=True)`
Sends a rating request email using a mail template. Posts as a `mail.mt_note` subtype (not a comment). Supports:
- `lang`: Language override for the template
- `force_send`: If `True`, sends immediately; if `False`, uses the mail queue cron (recommended for bulk operations)

```python
def rating_send_request(self, template, lang=False, force_send=True):
    if lang:
        template = template.with_context(lang=lang)
    self.with_context(mail_notify_force_send=force_send).message_post_with_source(
        template,
        email_layout_xmlid='mail.mail_notification_light',
        force_send=force_send,
        subtype_xmlid='mail.mt_note',
    )
```

The template typically includes a link like `/rate/{access_token}/<star_value>` to allow the customer to rate without logging in.

#### `rating_apply(self, rate, token=None, rating=None, feedback=None, subtype_xmlid=None, notify_delay_send=False)`
**The Rating Submission Handler.** Processes a rating submission (either via token or direct record reference).

**Parameters:**
- `rate` (float, required): Rating value 0-5
- `token` (str, optional): Access token to fetch the rating record. If provided, `rating` parameter is ignored
- `rating` (record, optional): Direct rating record to update
- `feedback` (str, optional): Free-text feedback
- `subtype_xmlid` (str, optional): Mail message subtype
- `notify_delay_send` (bool, optional): If `True`, delays the notification email by 2 hours so the user can change their feedback

**Workflow:**
1. Validates `rate` is between 0 and 5
2. If `token` provided, searches for rating by `access_token`
3. Writes `rating`, `feedback`, `consumed=True` on the rating record
4. If the model inherits from `mail.thread`, posts a message to the chatter with the rating image and feedback formatted as HTML
5. If `notify_delay_send=True`, schedules the notification for 2 hours later via `scheduled_date`

**Chatter Integration (L3):**
When posting to chatter, the body is constructed using `markupsafe.Markup` for safe HTML injection:
```python
rating_body = markupsafe.Markup(
    "<img src='%s' alt=':%s/5' style='width:18px;height:18px;float:left;margin-right: 5px;'/>%s"
) % (rating.rating_image_url, rate, feedback)
```
The star image URL is injected directly (controlled by Odoo, not user input). The feedback is converted from plain text to HTML via `tools.plaintext2html`.

**Failure Mode (L3):** If the rating model does not inherit from `mail.thread` (i.e., not in `self.env.registry['mail.thread']`), the method silently skips the chatter update and only updates the rating record.

**L4 — `notify_delay_send` and Scheduled Notifications:** When `notify_delay_send=True`, the notification email is scheduled for 2 hours in the future (`fields.Datetime.now() + timedelta(hours=2)`) via the `scheduled_date` parameter on `message_post`. This allows the customer to return to the page within 2 hours and change their rating/feedback before the notification fires. The mechanism uses Odoo's mail scheduler: the `mail.mail` record is created immediately but the `send` cron defers delivery until the scheduled time. If the customer modifies their rating before the deadline, the scheduled mail is automatically superseded by the new rating update (Odoo cancels pending scheduled mails for the same thread).

**L4 — Rating Reset via `_message_update_content`:** When a user sets `rating_value=False` in `_message_update_content`, the rating linked to that message is fully unlinked (not just cleared). This enables the "delete rating" use case from within the message editor. The unlink cascades to remove the `mail.message` record itself per the `rating.rating.unlink()` override.

**XSS Prevention (L4):** The `feedback` parameter is processed through `tools.plaintext2html()` which converts plain text to safe HTML (escapes special characters, converts newlines to `<br>`). Direct HTML injection via feedback is not possible because `plaintext2html` sanitizes the input.

#### `message_post(self, **kwargs)`
Extended to support inline rating creation from message posting. If `rating_value` is passed in kwargs:
1. Extracts `rating_value` from kwargs
2. Converts HTML body to plain text for the rating feedback
3. Creates a `rating.rating` record linked to the current record
4. Sets `consumed=True` (ratings from message posts are immediately consumed)
5. Links the rating to the posted message via `rating_id` kwarg

The `partner_id` on the rating is set to `self.env.user.partner_id.id` (the posting user).

#### `_message_post_after_hook(self, message, msg_values)`
Overridden to link a rating to its message if the rating author matches the message author and they are on the same record. This correlation enables the `mail.message.rating_id` computation.

```python
# sudo: rating.rating - can link rating to message from same author and thread
rating = self.env["rating.rating"].browse(msg_values.get("rating_id")).sudo()
same_author = rating.partner_id and rating.partner_id == message.author_id
if same_author and rating.res_model == message.model and rating.res_id == message.res_id:
    rating.message_id = message.id
```

**L4 — Purpose of `same_author` Check:** The `same_author` condition ensures that only ratings authored by the message sender are linked to that message. This prevents ratings from other partners (e.g., a supervisor's reply with their own rating) from being incorrectly associated with the customer's original message. The `sudo()` is safe here because the author validation ensures the rating belongs to the same commercial partner chain.

#### `_message_update_content(self, message, /, *, body, rating_value=None, **kwargs)`
Extended to support updating rating content along with message content:
- If `rating_value` is provided, updates the rating's rating value and feedback
- If `rating_value` is explicitly `False`, removes and deletes the rating linked to the message

#### `_get_allowed_message_params(self)`
Extended to include `rating_value` in allowed message parameters.

#### `_get_message_create_ignore_field_names(self)`
Extended to ignore the `rating_id` parameter when creating messages to prevent it from being treated as a regular field.

---

## mail_message.py - Rating in Mail Messages

**File:** `rating/models/mail_message.py`
**Model:** `mail.message` (Inherited)

Extends `mail.message` to add rating-related computed fields and rating data publishing in the Discuss store.

### Field Definitions

```python
rating_ids = fields.One2many("rating.rating", "message_id", string="Related ratings")
```
One2many to ratings linked to this message via `message_id`.

```python
rating_id = fields.Many2one("rating.rating", compute="_compute_rating_id")
```
Computed single-rating field. Returns the consumed rating with the latest `create_date` from `rating_ids`. If no consumed rating exists, returns `False`.

```python
rating_value = fields.Float(
    'Rating Value',
    compute='_compute_rating_value',
    compute_sudo=True,
    store=False,
    search='_search_rating_value'
)
```
Computed rating value (0 if no rating). Has a search method.

### Method Signatures

#### `_compute_rating_id(self)`
Filters `rating_ids` for consumed ratings, sorts by `create_date DESC`, and takes the first one as `rating_id`.

#### `_compute_rating_value(self)`
Returns `rating_id.rating` or `0.0`.

#### `_search_rating_value(self, operator, operand)`
Search method for searching messages by rating value. Uses `sudo()._search` on `rating.rating` with the constraint `message_id != False` and `consumed = True`. Supports negative operators by returning `NotImplemented`.

**Edge Case (L3):** If the operator is `in` and `0` is in the operand, the search returns messages that have no rating OR a rating of 0. This is achieved by combining the domain with `Domain("rating_ids", "=", False)` using OR.

#### `_to_store_defaults(self, target) -> list`
Adds `rating_id` (with `sudo=True`) and `"record_rating"` to the default store fields for the mail Discuss API.

**L4 — `sudo=True` Rationale:** The `sudo=True` on `Store.One("rating_id", sudo=True)` allows any guest or portal user to receive the `rating_id` in the store response, even without direct `rating.rating` read access. This is safe because `rating_id` only exposes the rating's integer ID — not the rating value itself. The actual rating data (rating, feedback) is gated by `rating_ids` being hidden from non-group_user users via `groups='base.group_user'`.

#### `_to_store(self, store: Store, fields, **kwargs)`
Extended to include rating statistics (`rating_avg`, `rating_count`, `rating_stats`) in the store when:
1. The thread model is a subclass of `rating.mixin`
2. The current user has read access to `rating_avg` field (checked via `_has_field_access`)

If `_allow_publish_rating_stats()` returns `True`, per-record statistics from `_rating_get_stats_per_record()` are included as a `rating_stats` attribute.

**L4 — Discuss API Integration:** This method is part of Odoo's "Store" architecture for the Discuss (mail/chatter) real-time API. When the web client fetches thread data (via `/mail/chatter_fetch` or similar RPC calls), `_to_store()` is invoked to serialize thread data into the response. Rating statistics are conditionally included based on `_allow_publish_rating_stats()`. By default this returns `False`, so rating stats are NOT published to the Discuss store. Module-specific overrides (e.g., in `helpdesk`, `project`) set this to `True` when they want to display rating dashboards in the chatter. The `_has_field_access` check ensures that even if a user can read the thread, they cannot see rating statistics unless they also have `base.group_user` access to the `rating_avg` field.

#### `_is_empty(self)`
Extended: a message is considered empty only if both the superclass check passes AND there is no rating linked to it. This affects the "non-empty message" domain used in portal thread fetching.

**L4 — Why Ratings Make Messages Non-Empty:** In the portal thread fetching flow (`/mail/chatter_fetch`), Odoo excludes messages that are "empty" (no body, no attachment, no subtype). A rating-only message (rating submitted without feedback text) must not be considered empty, otherwise the rating would disappear from the portal chatter view. The override ensures that even a rating with no feedback text body is treated as a valid, displayable message in the portal thread.

---

## Controllers

### main.py - Rating HTTP Controller

**File:** `rating/controllers/main.py`

The `Rating` HTTP controller handles the public rating submission flow:

#### `/rate/<string:token>/<int:rate>` (GET)
The old direct rating submission URL. **Changed in Odoo 16+ (L4).**

**Historical Security Issue:** This route previously accepted GET requests that would immediately consume the rating and send notifications. Email crawlers (like Gmail's preview bot) would crawl these URLs when rendering emails, accidentally consuming ratings and triggering notification emails to rated operators.

**Current Behavior:** The GET request no longer consumes the rating. It only renders the rating submission form page. The actual rating submission requires a POST to `/rate/<token>/submit_feedback`.

**L4 — `rate` URL Parameter Validation:** The `rate` parameter is typed as `<int:rate>` in the route definition, meaning Odoo's werkzeug routing automatically validates that it is an integer before the handler runs. However, the handler additionally validates that the rate must be one of `{1, 3, 5}` (the three discrete star values). Passing `2` or `4` results in a `ValueError`, not a 404. This discrete set is enforced because the star images only exist for these three values (via `_rating_to_threshold`).

```python
@http.route('/rate/<string:token>/<int:rate>', type='http', auth="public", website=True)
def action_open_rating(self, token, rate, **kwargs):
    if rate not in (RATING_HAPPY_VALUE, RATING_NEUTRAL_VALUE, RATING_UNHAPPY_VALUE):
        raise ValueError(...)  # Validates rate is 1, 3, or 5 only
    rating, record_sudo = self._get_rating_and_record(token)
    # Validates that the current user is related to the rated partner
    if not request.env.user._is_public() and \
            request.env.user.partner_id.commercial_partner_id != rating.partner_id.commercial_partner_id:
        return request.render('rating.rating_external_page_invalid_partner', {...})
    # Renders the feedback submission form
    return request.env['ir.ui.view']._render_template('rating.rating_external_page_submit', {
        'rating': rating, 'token': token,
        'rate_names': {...},
        'rate': rate,
    })
```

**Security Check:** If an authenticated (non-public) user tries to access a rating not intended for them (their commercial partner does not match the rated partner), the page renders an "invalid partner" error instead of the rating form. This prevents users from accessing ratings intended for other customers.

#### `/rate/<string:token>/submit_feedback` (POST/GET)
Handles actual rating submission.

```python
@http.route(['/rate/<string:token>/submit_feedback'], type="http", auth="public",
            methods=['post', 'get'], website=True)
def action_submit_rating(self, token, rate=0, **kwargs):
    rating, record_sudo = self._get_rating_and_record(token)
    if request.httprequest.method == "POST":
        rate = int(rate)
        # Validates rate is 1, 3, or 5
        if rate not in (RATING_HAPPY_VALUE, RATING_NEUTRAL_VALUE, RATING_UNHAPPY_VALUE):
            raise ValueError(...)
        record_sudo.rating_apply(rate, rating=rating, feedback=kwargs.get('feedback'),
                                subtype_xmlid=None)
    # GET requests render the "view" page (shows current rating status)
    return request.env['ir.ui.view']._render_template('rating.rating_external_page_view', {
        'web_base_url': rating.get_base_url(),
        'rating': rating,
    })
```

**POST vs GET behavior:**
- `POST`: Validates the rate, calls `rating_apply()` on the rated record, marks rating as consumed
- `GET` (with existing consumed rating): Renders the "view" page showing the submitted rating

#### `_get_rating_and_record(self, token) -> tuple`
Internal helper that fetches the rating by token (via `sudo()`) and the rated record. Raises `werkzeug.exceptions.NotFound()` if either the rating or the record does not exist. Uses `sudo()` because public users need to access the rating.

**Security:** The `sudo()` usage is limited to fetching the rating and record existence. Subsequent access checks (commercial partner validation) are performed after fetching.

### portal_thread.py - Inherited from portal module

**File:** `rating/controllers/portal_thread.py`

```python
class PortalChatter(portal_thread.PortalChatter):
    pass
```

A thin passthrough class that inherits from `portal_thread.PortalChatter` in the `portal` module. No own methods. Its sole purpose is to make the `portal` module's `PortalChatter` available within the `rating` addon's controller namespace (`http.Controller` registry), enabling Odoo's routing system to resolve controllers from the `rating` module when the `portal` module is installed but the `rating` module is explicitly included in the controller resolution path.

See [[Modules/portal]] for full documentation on the portal controller. Key routes used by the rating flow:

- `/mail/avatar/mail.message/<int>/author_avatar/<int>w x <int>h`: Serves message author avatars
- `/mail/chatter_fetch`: Fetches messages for a portal thread (supports token-based access), includes rating data via `mail.message._to_store()`
- `/portal/chatter_init`: Initializes portal chatter store data, includes rating statistics when `_allow_publish_rating_stats()` returns `True`

### rating/main.py - Rating HTTP Controller

**File:** `rating/controllers/main.py`

The `Rating` controller handles the public rating submission flow via two routes:

---

## Views

### rating_rating_views.xml

#### Tree View
Displays ratings in a list with optional columns, color-coded badge for `rating_text`, and no create/edit actions (read-only display).

#### Form View
Two-column layout showing document reference, parent holder, rated operator, partner, star image (via binary widget), rating text badge, `rated_on` timestamp, and feedback text. `consumed` field is hidden from regular users (`groups='base.group_no_one'`).

#### Kanban Views
Two kanban templates:
1. **Card kanban** (`rating_rating_view_kanban`): Side-by-side image and details
2. **Stars kanban** (`rating_rating_view_kanban_stars`): Large numeric rating with filled/half/empty star icons using JavaScript computation (`Math.round`, `Math.floor`, `Math.ceil`)

#### Pivot View
Pivot table with `rated_partner_id` as rows, `rated_on` as columns, and `rating` as measure. Used for analyzing rating distribution over time.

#### Graph View
Simple bar graph of ratings over time (by `rated_on`).

#### Search View
Predefined filters:
- "My Ratings": Ratings where the rated operator is a user linked to the current user
- "Happy/Neutral/Unhappy": Filter by `rating_text`
- Date filters: Last 7/30/365 days
- Group by: Rated Operator, Customer, Rating text, Resource, Month

### mail_message_views.xml

Adds a "Ratings" page to the mail.message form view, showing linked rating records.

---

## Security

### ir.model.access.csv

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_rating_user,rating.rating.user,rating.model_rating_rating,base.group_user,1,1,1,0
access_rating_public,rating.rating.public,rating.model_rating_rating,base.group_public,0,0,0,0
access_rating_portal,rating.rating.portal,rating.model_rating_rating,base.group_portal,0,0,0,0
rating_rating_access_system,rating.rating.access.system,rating.model_rating_rating,base.group_system,1,1,1,1
```

**Key Points:**
- Internal users (`base.group_user`): Full create/write/read access (no delete)
- Portal and public users: No access at all
- System/administrators (`base.group_system`): Full access including delete

This means only employees (or sudo'd operations) can create ratings. Portal users interact with ratings exclusively through the public HTTP controller, which uses `sudo()` internally.

### Field-Level Security

Several fields on `rating.rating` and mixin models use `groups='base.group_user'`:
- `rating_ids` on `rating.parent.mixin`
- `rating_avg`, `rating_count`, `rating_last_value`, `rating_avg_text`, `rating_last_text`, `rating_last_feedback`, `rating_last_image` on `rating.mixin`
- `rating_avg`, `rating_avg_percentage` on `rating.parent.mixin`

These fields are hidden from portal and public users, ensuring rating statistics are only visible to internal users.

---

## Static Assets (Frontend)

### Star PNG Images
**Path:** `rating/static/src/img/`

Four discrete star images map rating values to visual states:

| File | Threshold | Meaning |
|------|-----------|---------|
| `rating_0.png` | Rating 0 (none) | Not yet rated |
| `rating_1.png` | Rating 1 (unhappy) | Unhappy / bad |
| `rating_3.png` | Rating 3 (neutral) | Neutral / okay |
| `rating_5.png` | Rating 5 (happy) | Happy / satisfied |

The `_rating_to_threshold()` function maps 4-star ratings to `rating_5.png` (since 4 >= 3, it maps to the "satisfied" image). This means there is no `rating_4.png` file — a 4-star rating displays as a 5-star (happy) image. This is by design: the visual set only includes three discrete icons (unhappy/neutral/happy), with the threshold determining which is shown.

### Web Assets (JavaScript)
**Paths registered in manifest:**
- `rating/static/src/core/common/**/*` — shared components loaded by both frontend and backend
- `rating/static/src/core/web/**/*` — backend-specific (web client) components

These implement the interactive star-rating widget used in form views and the chatter thread. Key behaviors: half-star support, keyboard navigation, and mobile touch events.

### SCSS (Stylesheet)
**Path:** `rating/static/src/scss/rating_templates.scss`

QWeb template styles for the portal rating submission pages rendered by `rating_templates.xml`. Loaded via `web.assets_frontend` to style the `/rate/<token>/submit_feedback` pages.

### Asset Bundles
The manifest registers assets into multiple bundles:
- `web.assets_backend` — ratings in the internal web client
- `web.assets_frontend` — ratings in public website/portal pages
- `mail.assets_public` — ratings visible in public mail threads
- `portal.assets_chatter` — ratings in the portal chatter component

This separation ensures that portal users load only the frontend assets, while internal users get the full backend components.

---

## Module Structure

```
rating/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── main.py              # Rating HTTP controller (/rate/ routes)
│   └── portal_thread.py     # Passthrough → portal.PortalChatter
├── models/
│   ├── __init__.py
│   ├── rating.py            # rating.rating model
│   ├── rating_data.py       # Constants and conversion functions
│   ├── rating_mixin.py      # rating.mixin (per-record statistics)
│   ├── rating_parent_mixin.py  # rating.parent.mixin (aggregation)
│   ├── mail_thread.py       # mail.thread extensions
│   └── mail_message.py      # mail.message extensions
├── views/
│   ├── rating_rating_views.xml   # rating.rating list/form/kanban/pivot/graph/search
│   ├── rating_templates.xml      # QWeb portal submission/view pages
│   └── mail_message_views.xml    # mail.message form inheritance
├── security/
│   └── ir.model.access.csv  # ACL for rating.rating model
└── static/
    ├── src/
    │   ├── core/            # JS components (common + web)
    │   ├── img/              # Star PNG files (0/1/3/5)
    │   └── scss/             # Portal page styles
    └── tests/                # JavaScript unit tests
```

---

## Usage Patterns

### Adding Rating to a Model

To enable rating on a model (e.g., `helpdesk.ticket`), inherit from `rating.mixin`:

```python
class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _inherit = ['mail.thread', 'rating.mixin']
    # ... fields ...
```

Override `_rating_get_parent_field_name()` if the model has a parent (e.g., `helpdesk.team`):

```python
def _rating_get_partner(self):
    if self.partner_id:
        return self.partner_id
    return self.env['res.partner']
```

### Sending a Rating Request

```python
# In a ticket action method
template = self.env.ref('helpdesk.rating_ticket_request_mail')
self.rating_send_request(template, force_send=True)
```

### Submitting a Rating Programmatically

```python
# Internal rating without token
ticket.rating_apply(rate=5, feedback='Great support!')
```

### Rating Reset Pattern

```python
# Get the rating
rating = self.env['rating.rating'].search([('res_model', '=', 'sale.order'),
                                           ('res_id', '=', order.id),
                                           ('consumed', '=', True)], limit=1)
rating.reset()  # Resets rating, generates new access token
```

---

## Performance Characteristics (L4)

### Query Efficiency

1. **`_compute_rating_last_value`**: Single raw SQL query with `array_agg` and `GROUP BY res_id` fetches all records in one database round trip, avoiding N+1.

2. **Partial Indexes**: `_consumed_idx` and `_parent_consumed_idx` are partial indexes on `WHERE consumed IS TRUE`. These indexes are significantly smaller than full-table indexes since only consumed ratings are indexed.

3. **`_read_group` for Aggregations**: All other statistics use `_read_group` with aggregation functions (`avg`, `count`), which translates to efficient SQL GROUP BY queries.

4. **`store=True` on Statistics**: `rating_last_value`, `rating_avg`, `rating_count` etc. are stored fields. This means:
   - Statistics are computed once (on rating create/write) and cached
   - List views can display statistics without recomputation
   - The tradeoff is write-time overhead vs. read-time efficiency

### Caching

- `rating_image` is computed from static PNG files; consider adding HTTP cache headers if serving many ratings
- `rating_last_value` is stored, so it only recomputes when a rating is created/updated

### Write-time Side Effects

When a rated record is updated:
1. `rating_ids.write({'res_name': ...})` is triggered via `add_to_compute` (recomputes stored field on related ratings)
2. If parent field changes, all child ratings get `parent_res_id` updated via `write()`

For records with many ratings, these operations can be expensive. Consider using batch operations if bulk updating records with many ratings.

---

## Historical Changes (Odoo 18 to Odoo 19)

### GET Rating URL Removed (Security Fix)

In Odoo 15/16, the route `/rate/<token>/<int:rate>` would accept GET requests that immediately consumed the rating and sent notifications. **Email crawlers** (Gmail, Outlook) would crawl these URLs when rendering email previews, inadvertently consuming ratings and triggering notification emails to rated operators.

**Fix:** The GET route now renders the submission form without consuming the rating. Users must explicitly submit the form (POST) to confirm their rating. This change prevents accidental rating consumption by automated systems.

### `access_token` GET Parameter Removed

Similarly, the ability to pass `access_token` as a GET parameter was removed from various internal flows to prevent email crawler issues.

---

## Odoo 19-Specific Changes (L4)

### New `notify_delay_send` Parameter in `rating_apply`
Added in Odoo 18/19: The `notify_delay_send` parameter enables delayed notification emails. When `True`, the chatter notification email is scheduled for delivery 2 hours later, allowing customers to revise their rating within the grace period. This reduces notification email spam for customers who immediately change their mind.

### New `_rating_get_stats_per_record` Method
Added in Odoo 19: Returns per-record rating statistics including `total`, `avg`, and `percent` (rating value distribution). Previously, computing per-record stats required manual iteration. This method uses a single `_read_group` call with `groupby=['res_id', 'rating']` for batch efficiency.

### Discuss Store API Integration (`mail.message._to_store`)
The `mail.message` model was updated in Odoo 17+ to support the new "Store" architecture for real-time web client updates. Rating statistics are conditionally published to the store via `_to_store()`. The `_allow_publish_rating_stats()` gate on `rating.mixin` controls whether stats are published — modules like `helpdesk` override this to `True` to display rating dashboards in the chatter sidebar.

### New `rated_on` Field (Odoo 18+)
The `rated_on` field was added to track the precise timestamp of rating submission. Previously, `write_date` was used as a proxy. The dedicated field avoids confusion when ratings are created but not yet consumed (invitation tokens have a creation date but no submission date).

### New `rating_avg_text` and `rating_last_text` Fields (Odoo 18+)
These computed selection fields convert numeric ratings to text labels (`top`/`ok`/`ko`/`none`) for use in kanban badge widgets without requiring JavaScript logic in the view layer.

### `resource_ref` and `parent_ref` Reference Fields (Odoo 17+)
Dynamic `Reference` (x2one-like) fields that provide direct record references as `'{model},{id}'` strings. Enables UI widgets (like the "Open Document" button in the rating kanban card) to navigate directly to the rated resource.

### `rating_avg_percentage` Field on `rating.parent.mixin` (Odoo 18+)
Added `rating_avg_percentage = rating_avg / 5` as a 0-100 float suitable for progress bar widgets in parent-level dashboards (e.g., project satisfaction progress bars).

---

## Tests

### test_security.py — ACL Enforcement
**File:** `rating/tests/test_security.py`

Verifies that only employees (`base.group_user`) can create and write `rating.rating` records. Portal and public users must raise `AccessError` on direct model access. This test confirms the ACL configuration in `ir.model.access.csv` is correctly applied.

### test_controller.py — Rating Flow and Partner Validation
**File:** `rating/tests/test_controller.py`

Tests the full rating submission flow including:
- **GET `/rate/<token>/submit_feedback`**: Returns 200 OK for valid token (shows rating view page)
- **Commercial Partner Validation**: A demo user cannot access a rating intended for another company's partner — the page renders `"You cannot rate this"` instead of the feedback form
- **Same-company Portal User**: A portal user whose `commercial_partner_id` matches the rated partner CAN access and consume the rating
- **Unauthenticated Access**: Public users can access the rating view page (no partner validation applies)

---

## Related Documentation

- [[Core/API]] - API decorators used in rating models
- [[Modules/mail]] - Mail thread and message system integration
- [[Modules/portal]] - Portal controller for public rating access
- [[Modules/helpdesk]] - Example module using rating functionality
- [[Modules/project]] - Example of parent-level rating aggregation
