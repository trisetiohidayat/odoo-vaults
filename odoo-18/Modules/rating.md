# rating - Rating and Feedback System

## Overview

The `rating` module provides a comprehensive rating and feedback system for Odoo. It enables customers to rate services, products, or any record with a 0-5 star rating, and tracks satisfaction metrics over time.

## Module Information

- **Technical Name**: `rating`
- **Location**: `addons/rating/`
- **Depends**: `mail`
- **License**: LGPL-3

---

## Models

### rating.rating

**File**: `models/rating.py`

Core rating model:

```python
class Rating(models.Model):
    _name = "rating.rating"
    _description = "Rating"
    _order = 'write_date desc, id desc'
```

**Rating Value Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `rating` | Float | Rating value (0-5), aggregator="avg" |
| `rating_text` | Selection | top/ok/ko/none (computed) |
| `rating_image` | Binary | Rating icon image (computed) |
| `rating_image_url` | Char | URL to rating icon (computed) |
| `feedback` | Text | Customer feedback comment |

**Reference Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `res_model_id` | Many2one | Target document model (ir.model) |
| `res_model` | Char | Target model name (related) |
| `res_id` | Integer | Target record ID |
| `resource_ref` | Reference | Dynamic reference to record |

**Parent Reference** (for composite ratings):

| Field | Type | Description |
|-------|------|-------------|
| `parent_res_model_id` | Many2one | Parent document model |
| `parent_res_model` | Char | Parent model name |
| `parent_res_id` | Integer | Parent record ID |
| `parent_ref` | Reference | Dynamic parent reference |

**Participant Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `partner_id` | Many2one | Customer who rated |
| `rated_partner_id` | Many2one | Service provider who received rating |

**Metadata Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `message_id` | Many2one | Associated mail.message |
| `is_internal` | Boolean | Visible internally only |
| `consumed` | Boolean | Rating has been submitted |
| `access_token` | Char | Token for rating request |
| `create_date` | Datetime | When rating was created |
| `write_date` | Datetime | Last update date |

**SQL Constraints**:
```python
_sql_constraints = [
    ('rating_range', 'check(rating >= 0 and rating <= 5)',
     'Rating should be between 0 and 5'),
]
```

**Key Computed Methods**:

```python
def _compute_res_name(self):
    """Get display name of rated resource"""
    for rating in self:
        name = self.env[rating.res_model].sudo().browse(rating.res_id).display_name
        rating.res_name = name or f'{rating.res_model}/{rating.res_id}'

def _compute_resource_ref(self):
    """Get reference field for rated record"""
    for rating in self:
        if rating.res_model and rating.res_model in self.env:
            rating.resource_ref = f'{rating.res_model},{rating.res_id or 0}'

def _compute_rating_text(self):
    """Convert numeric rating to text category"""
    for rating in self:
        rating.rating_text = rating_data._rating_to_text(rating.rating)

def _compute_rating_image(self):
    """Get appropriate rating icon based on value"""
    for rating in self:
        filename = f'rating_{threshold}.png'
        rating.rating_image_url = f'/rating/static/src/img/{filename}'
```

**Key Action Methods**:

```python
def reset(self):
    """Reset rating to initial state"""
    for record in self:
        record.write({
            'rating': 0,
            'access_token': record._default_access_token(),
            'feedback': False,
            'consumed': False,
        })

def action_open_rated_object(self):
    """Open the rated record"""
    return {
        'type': 'ir.actions.act_window',
        'res_model': self.res_model,
        'res_id': self.res_id,
    }
```

---

### rating.mixin

**File**: `models/rating_mixin.py`

Abstract mixin for models that support ratings:

```python
class RatingMixin(models.AbstractModel):
    _name = 'rating.mixin'
    _description = "Rating Mixin"
    _inherit = 'mail.thread'
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `rating_last_value` | Float | Most recent rating value |
| `rating_last_feedback` | Text | Most recent feedback |
| `rating_last_image` | Binary | Most recent rating image |
| `rating_count` | Integer | Total number of ratings |
| `rating_avg` | Float | Average rating (0-5) |
| `rating_avg_text` | Selection | top/ok/ko/none |
| `rating_percentage_satisfaction` | Float | % of "great" ratings |
| `rating_last_text` | Selection | Most recent rating text |

**Key Computed Methods**:

```python
def _compute_rating_last_value(self):
    """Get most recent rating value using SQL for performance"""
    self.env.cr.execute("""
        SELECT array_agg(rating ORDER BY write_date DESC, id DESC) AS ratings, res_id
        FROM rating_rating
        WHERE res_model = %s AND res_id in %s AND consumed = true
        GROUP BY res_id
    """, [self._name, tuple(self.ids)])

def _compute_rating_stats(self):
    """Compute count and average in single query"""
    domain = expression.AND([
        self._rating_domain(),
        [('rating', '>=', rating_data.RATING_LIMIT_MIN)]
    ])
    read_group_res = self.env['rating.rating']._read_group(
        domain, ['res_id'],
        aggregates=['__count', 'rating:avg']
    )

def _search_rating_avg(self, operator, value):
    """Search records by average rating"""

def _compute_rating_avg_text(self):
    """Convert average to text category"""

def _compute_rating_satisfaction(self):
    """Calculate percentage of great ratings"""
```

**Statistical Methods**:

```python
def _rating_domain(self):
    """Get domain for this model's ratings"""
    return [
        '&', '&',
        ('res_model', '=', self._name),
        ('res_id', 'in', self.ids),
        ('consumed', '=', True)
    ]

def _rating_get_repartition(self, add_stats=False, domain=None):
    """Get rating distribution"""
    # Returns dict of {rating_value: count}
    # If add_stats=True: also returns avg and total

def rating_get_grades(self, domain=None):
    """Get grade distribution (great/okay/bad)"""
    # Maps 0-30% -> bad, 31-69% -> okay, 70-100% -> great

def rating_get_stats(self, domain=None):
    """Get detailed statistics"""
    return {
        'avg': ...,
        'total': ...,
        'percent': {1: ..., 2: ..., 3: ..., 4: ..., 5: ...}
    }
```

---

## Rating Data Constants

**File**: `models/rating_data.py`

```python
# Thresholds
RATING_AVG_TOP = 3.66  # Above this = "top"
RATING_AVG_OK = 2.33   # Above this = "ok"
RATING_AVG_MIN = 1     # Above this = "ok"
RATING_LIMIT_SATISFIED = 4  # >= 4 = "great"
RATING_LIMIT_OK = 3    # >= 3 = "okay"
RATING_LIMIT_MIN = 1   # >= 1 = rated

# Text representations
RATING_TEXT = [
    ('top', 'Satisfied'),
    ('ok', 'Okay'),
    ('ko', 'Dissatisfied'),
    ('none', 'No Rating yet'),
]

def _rating_to_text(rating_value):
    """Convert 0-5 to text category"""
    if rating_value >= 4: return 'top'
    if rating_value >= 3: return 'ok'
    if rating_value >= 1: return 'ko'
    return 'none'

def _rating_to_threshold(rating_value):
    """Convert to image threshold (0, 1, 3, 5)"""
    if rating_value >= 4: return 5
    if rating_value >= 3: return 3
    if rating_value >= 1: return 1
    return 0
```

---

## Rating Thresholds

### Image Mapping

| Rating | Image | Label |
|--------|-------|-------|
| 0 | none | No Rating yet |
| 1-2 | 1-star | Dissatisfied |
| 3 | 3-star | Okay |
| 4-5 | 5-star | Satisfied |

### Text Mapping

| Rating | Text | Color |
|--------|-------|-------|
| 0 | No Rating | Gray |
| 1-2 | Dissatisfied | Red |
| 3 | Okay | Orange |
| 4-5 | Satisfied | Green |

---

## Parent Rating Pattern

### Concept
Ratings can be hierarchical:
- Individual line ratings (e.g., task in project)
- Parent rating aggregates child ratings (e.g., project overall)

### Implementation
```python
class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ['rating.mixin']

    project_id = fields.Many2one('project.project')

    def _rating_get_parent_field_name(self):
        """Return field name for parent rating aggregation"""
        return 'project_id'

class ProjectProject(models.Model):
    _name = 'project.project'
    _inherit = ['rating.mixin']

    # Automatically aggregates child task ratings
```

### Aggregation
Parent model displays average of all child ratings via `parent_res_model_id` and `parent_res_id` fields on rating records.

---

## Rating Request Flow

### 1. Create Rating Request
```python
def action_rating_request(self, rate_partner_id=None, template_xmlid=None):
    """Send rating request to customer"""
    self.ensure_one()
    template = self.env.ref(template_xmlid)
    template.send_mail(self.id, email_values={
        'email_to': partner.email,
    })
    # Creates mail.message with rating link
```

### 2. Customer Rates
Customer clicks link with access token:
```
/rating/rate/{rating_id}?token={access_token}&rating={value}
```

### 3. Rating Recorded
```python
class RatingController(http.Controller):
    @http.route('/rating/rate/<int:rating_id>', type='http', auth='public')
    def rate(self, rating_id, token, rating_value, **kwargs):
        rating = request.env['rating.rating'].browse(rating_id)
        if rating.access_token == token:
            rating.write({
                'rating': int(rating_value),
                'consumed': True,
            })
```

---

## Rating Parent Mixin

**File**: `models/rating_parent_mixin.py`

```python
class RatingParentMixin(models.AbstractModel):
    """For models that aggregate ratings from children"""
    _name = 'rating.parent.mixin'

    rating_ids = fields.One2many('rating.rating', string='Ratings')
```

---

## Rating Integration Methods

### Models Using Rating Mixin
- `helpdesk.ticket` - Helpdesk tickets
- `project.task` - Project tasks
- `project.project` - Projects
- `hr.expense` - Expense reports
- `appointment.appointment` - Appointments
- `repair.order` - Repair orders

### Star Rating Widget
```xml
<field name="rating_ids" widget="rating"/>
<!-- Renders: ★★★★☆ with hover state -->
```

### Rating Button
```xml
<button name="action_rating_request" string="Request Rating"
        type="object" class="btn-primary"/>
```

---

## Statistics Display

### Form View
```xml
<div class="row mt-4">
    <div class="col-4">
        <field name="rating_avg" widget="percentage"/>
    </div>
    <div class="col-8">
        <field name="rating_count" string="Ratings"/>
    </div>
</div>
```

### Kanban Card
```xml
<div class="o_rating_card">
    <field name="rating_avg_text" widget="badge"/>
    <span t-field="record.rating_avg" t-options='{"float": true}'/>
</div>
```

---

## Satisfaction Calculation

```python
def _compute_rating_satisfaction(self):
    """Calculate % of ratings that are 'great'"""
    # Satisfaction = great / (great + okay + bad) * 100
    # great = rating >= 4
    # okay = rating >= 3
    # bad = rating >= 1
```

---

## Key Features

### 1. Star Rating System
- 0-5 scale with half stars support
- Automatic text categorization
- Icon/label representation

### 2. Rating Statistics
- Average rating (avg)
- Total count
- Satisfaction percentage
- Distribution breakdown

### 3. Parent Aggregation
- Child ratings roll up to parent
- Automatic parent average calculation

### 4. Rating Requests
- Email with access token link
- Unique token per rating request
- Prevent duplicate submissions

### 5. Feedback Collection
- Optional comment/feedback text
- Stored with rating record

### 6. Internal Ratings
- `is_internal` flag for staff-only ratings
- Separate from customer ratings

---

## Extension Points

### 1. Custom Rating Model
```python
class CustomRating(models.Model):
    _name = 'custom.rating'
    _inherit = 'rating.rating'
    # Add custom fields

    type = fields.Selection([('pre', 'Pre-service'), ('post', 'Post-service')])
```

### 2. Custom Grade Calculation
```python
def _compute_rating_satisfaction(self):
    """Custom satisfaction calculation"""
    # Custom logic based on domain knowledge
```

### 3. Rating Trigger
```python
def action_done(self):
    """Trigger rating request when ticket resolved"""
    self.ensure_one()
    if self.partner_id:
        self.sudo().message_post_with_template(
            self.env.ref('module.rating_request_template')
        )
```
