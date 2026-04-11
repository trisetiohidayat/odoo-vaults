# mass_mailing - Email Marketing and Mass Mailing

## Overview

The `mass_mailing` module provides comprehensive email marketing capabilities for Odoo. It enables users to create, schedule, and send mass email campaigns to mailing lists with detailed tracking of delivery, opens, clicks, and replies.

## Module Information

- **Technical Name**: `mass_mailing`
- **Location**: `addons/mass_mailing/`
- **Depends**: `link_tracker`, `mail`, `utm`
- **License**: LGPL-3

---

## Models

### mailing.mailing

**File**: `models/mailing.py`

Main mass mailing model:

```python
class MassMailing(models.Model):
    _name = 'mailing.mailing'
    _description = 'Mass Mailing'
    _inherit = ['mail.thread',
                'mail.activity.mixin',
                'mail.render.mixin',
                'utm.source.mixin']
    _order = 'calendar_date DESC'
    _rec_name = "subject"
```

**Email Content Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `subject` | Char | Email subject line (required) |
| `preview` | Char | Preview text (shown in inbox) |
| `body_arch` | Html | Raw HTML body |
| `body_html` | Html | Rendered HTML (QWeb) |
| `is_body_empty` | Boolean | Computed empty check |
| `attachment_ids` | Many2many | Email attachments |
| `email_from` | Char | Sender email address |
| `reply_to` | Char | Reply-to address |

**Scheduling Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `schedule_type` | Selection | 'now' or 'scheduled' |
| `schedule_date` | Datetime | Scheduled send datetime |
| `calendar_date` | Datetime | Actual sent/computed datetime |
| `sent_date` | Datetime | When mailing was sent |

**Status Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `state` | Selection | draft/in_queue/sending/done |
| `color` | Integer | Color index |
| `active` | Boolean | Active status |

**Campaign Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `campaign_id` | Many2one | UTM campaign |
| `medium_id` | Many2one | UTM medium |
| `source_id` | Many2one | UTM source |
| `mailing_type` | Selection | 'mail' (extendable) |

**Recipient Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `mailing_model_id` | Many2one | Target model (ir.model) |
| `mailing_model_name` | Char | Related model name |
| `mailing_domain` | Char | Domain filter |
| `contact_list_ids` | Many2many | Mailing lists |
| `mailing_filter_id` | Many2one | Saved filter |

**A/B Testing Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `ab_testing_enabled` | Boolean | Enable A/B testing |
| `ab_testing_pc` | Integer | Test percentage (0-100) |
| `ab_testing_schedule_datetime` | Datetime | When to run test |
| `ab_testing_winner_selection` | Selection | manual/opened/clicked/replied |
| `ab_testing_is_winner_mailing` | Boolean | Is winner (computed) |

**Statistics Fields** (computed):

| Field | Type | Description |
|-------|------|-------------|
| `mailing_trace_ids` | One2many | All traces |
| `total` | Integer | Total recipients |
| `scheduled` | Integer | Scheduled count |
| `sent` | Integer | Sent count |
| `delivered` | Integer | Delivered count |
| `opened` | Integer | Opened count |
| `clicked` | Integer | Clicked count |
| `replied` | Integer | Replied count |
| `bounced` | Integer | Bounced count |
| `failed` | Integer | Failed count |
| `canceled` | Integer | Canceled count |
| `received_ratio` | Float | Delivery percentage |
| `opened_ratio` | Float | Open percentage |
| `replied_ratio` | Float | Reply percentage |
| `bounced_ratio` | Float | Bounce percentage |
| `clicks_ratio` | Float | Click percentage |

**Key Computed Methods**:

```python
def _compute_total(self):
    """Calculate total recipients, respecting A/B test percentage"""

def _compute_statistics(self):
    """Aggregate trace statistics: sent, delivered, opened, clicked, etc."""

def _compute_email_from(self):
    """Set default sender from user or mail server"""

def _compute_clicks_ratio(self):
    """Calculate unique click ratio from link tracking"""
```

---

### mailing.contact

**File**: `models/mailing_contact.py`

```python
class MassMailingContact(models.Model):
    _name = 'mailing.contact'
    _inherit = ['mail.thread.blacklist']
    _description = 'Mailing Contact'
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Full name (computed from first/last) |
| `first_name` | Char | First name |
| `last_name` | Char | Last name |
| `company_name` | Char | Company name |
| `email` | Char | Email address |
| `list_ids` | Many2many | Mailing lists |
| `subscription_ids` | One2many | Subscription records |
| `opt_out` | Boolean | Opt-out status (computed) |
| `country_id` | Many2one | Country |
| `tag_ids` | Many2many | Tags |

**Key Methods**:

```python
def _compute_name(self):
    """Combine first_name and last_name"""

def _search_opt_out(self, operator, value):
    """Search by opt-out status in active list context"""

def _compute_opt_out(self):
    """Compute opt-out for current mailing list context"""

def add_to_list(self, name, list_id):
    """Create contact and add to list"""
```

---

### mailing.list

**File**: `models/mailing_list.py`

```python
class MassMailingList(models.Model):
    _name = 'mailing.list'
    _description = 'Mailing List'
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | List name (required) |
| `active` | Boolean | Active status |
| `contact_count` | Integer | Total contacts |
| `contact_count_email` | Integer | Contacts with valid email |
| `contact_count_opt_out` | Integer | Opted-out contacts |
| `contact_pct_opt_out` | Float | Opt-out percentage |
| `contact_count_blacklisted` | Integer | Blacklisted contacts |
| `contact_pct_blacklisted` | Float | Blacklist percentage |
| `contact_ids` | Many2many | All contacts |
| `mailing_count` | Integer | Mailings using this list |
| `is_public` | Boolean | Show in preferences |

**Key Methods**:

```python
def _compute_mailing_list_statistics(self):
    """Compute all contact statistics in one pass"""

def _mailing_get_default_domain(self, mailing):
    """Get domain for mailing recipients"""

def _mailing_get_opt_out_list(self, mailing):
    """Get list of opted-out email addresses"""

def action_send_mailing(self):
    """Open mailing form with this list as default"""

def action_view_contacts(self):
    """Open contact list view"""

def action_merge(self, src_lists, archive):
    """Merge mailing lists, handling duplicates"""
```

---

### mailing.trace

**File**: `models/mailing_trace.py`

Tracks individual email statistics:

```python
class MailingTrace(models.Model):
    _name = 'mailing.trace'
    _description = 'Mailing Statistics'
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `trace_type` | Selection | Type: 'mail' |
| `mail_mail_id` | Many2one | Related mail.mail |
| `email` | Char | Recipient email |
| `message_id` | Char | RFC 2392 Message-ID |
| `model` | Char | Target model |
| `res_id` | Integer | Target record ID |
| `mass_mailing_id` | Many2one | Parent mailing |
| `sent_datetime` | Datetime | When sent |
| `open_datetime` | Datetime | When opened |
| `reply_datetime` | Datetime | When replied |
| `trace_status` | Selection | Status: outgoing/sending/pending/sent/open/reply/bounce/error/cancel |
| `failure_type` | Selection | Error type |
| `failure_reason` | Text | Error details |
| `links_click_ids` | One2many | Click records |

**Trace Status Values**:
- `outgoing`: Queued for sending
- `sending`: Currently being processed
- `pending`: Sent, awaiting delivery confirmation
- `sent`: Delivered successfully
- `open`: Opened by recipient
- `reply`: Recipient replied
- `bounce`: Bounced (invalid/undeliverable)
- `error`: Delivery failed
- `cancel`: Canceled (opted out, blacklisted)

**Key Methods**:

```python
def set_sent(self, domain=None):
    """Mark as sent with timestamp"""

def set_opened(self, domain=None):
    """Mark as opened"""

def set_clicked(self, domain=None):
    """Record link click"""

def set_replied(self, domain=None):
    """Mark as replied"""

def set_bounced(self, domain=None, bounce_message=False):
    """Mark as bounced with reason"""

def set_failed(self, domain=None, failure_type=False):
    """Mark as failed with error type"""

def set_canceled(self, domain=None):
    """Mark as canceled"""
```

---

### mailing.subscription

**File**: `models/mailing_subscription.py`

Links contacts to mailing lists with subscription info:

```python
class Subscription(models.Model):
    _name = 'mailing.subscription'
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `contact_id` | Many2one | Mailing contact |
| `list_id` | Many2one | Mailing list |
| `opt_out` | Boolean | Opted out from this list |
| `unsubscription_date` | Datetime | When opted out |

---

## A/B Testing Flow

1. **Setup**: Enable `ab_testing_enabled`, set `ab_testing_pc` (e.g., 10%)
2. **Split**: System divides recipients, sends to test group only
3. **Compare**: After `ab_testing_schedule_datetime`, compare metrics:
   - `opened_ratio`: Open rate
   - `replied_ratio`: Reply rate
4. **Winner Selection**: Based on `ab_testing_winner_selection`:
   - `manual`: User picks winner
   - `opened_ratio`: Highest open rate
   - `replied_ratio`: Highest reply rate
5. **Send**: Winner mailing sent to remaining recipients

---

## Blacklist Integration

The `mail.thread.blacklist` mixin automatically:
- Checks email against `mail.blacklist`
- Sets `message_bounce` on repeated bounces
- Allows opt-out per-contact

---

## Link Tracking

Automatic link tracking via `link_tracker`:
- Replaces URLs with tracked versions
- Records clicks per recipient
- Updates `clicked` count and `links_click_ids`

---

## Key Workflows

### Send Mass Mailing
1. Create `mailing.mailing` with content and recipients
2. Set `schedule_type='now'` or `schedule_date`
3. System creates `mailing.trace` records
4. `mailing.trace` updated as emails are sent/delivered/opened

### Manage Subscriptions
1. Contact subscribes via list or website
2. `mailing.subscription` created
3. User can opt-out via unsubscribe link
4. `opt_out=True` prevents future sends

### Import Contacts
1. Use import wizard from mailing list
2. Create/update `mailing.contact` records
3. Subscribe to selected lists

---

## Statistics Tracking

### Counters Flow
```
Recipients -> Outgoing -> Sent -> Delivered -> Opened -> Replied
                    \          \         \          \
                     Canceled   Bounced    Clicked    Failed
```

### Performance Metrics
- **Delivery Rate**: `delivered / (sent - canceled) * 100`
- **Open Rate**: `opened / delivered * 100`
- **Click Rate**: `clicked / delivered * 100`
- **Reply Rate**: `replied / delivered * 100`
- **Bounce Rate**: `bounced / sent * 100`

---

## Extension Points

1. **Mailing Types**: Extend `mailing_type` for SMS, etc.
2. **Recipient Models**: Add models via `is_mailing_enabled` flag
3. **Statistics**: Override `_compute_statistics` for custom metrics
4. **Filters**: Create `mailing.filter` for reusable domains
