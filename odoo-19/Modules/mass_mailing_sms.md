---
uuid: 7e3a2f1c-8d4b-4e6a-9f5c-2b1d0e3a4f7c
module: mass_mailing_sms
tags:
  - odoo
  - odoo19
  - modules
  - marketing
  - sms
  - mass_mailing
  - sms_marketing
  - utm
created: 2026-04-11
updated: 2026-04-14
description: >
  Full SMS marketing module for Odoo 19. Adds the 'sms' mailing type to the mass
  mailing engine, enabling design, sending, and tracking of SMS campaigns. Integrates
  with the SMS IAP gateway for delivery, phone blacklist for opt-out, and the mailing
  contact model for SMS-specific contact lists. Supports A/B testing, link shortening
  with click tracking, and per-recipient unsubscribe via unique trace codes.
---

# Mass Mailing SMS (`mass_mailing_sms`)

> Design, send, and track SMS campaigns using the Odoo mass mailing engine. The `sms` mailing type extends `mailing.mailing` to use the SMS composer and IAP gateway instead of email. Every SMS is traced with a unique code, enabling per-recipient opt-out and click tracking through shortened links.

**Module:** `mass_mailing_sms` | **Path:** `odoo/addons/mass_mailing_sms/` | **Version:** 1.1
**Category:** Marketing/Email Marketing | **Depends:** `portal`, `mass_mailing`, `sms` | **License:** LGPL-3
**Auto-install:** Not set | **Application:** True | **Author:** Odoo S.A.

---

## Overview

`mass_mailing_sms` is the SMS counterpart to the `mail` mailing type in `mass_mailing`. Where email campaigns use SMTP, templates, and the `mailing.trace` model for email tracking, SMS campaigns use the SMS IAP (In-App Purchase) gateway, `sms.template`, and the same `mailing.trace` model extended with SMS-specific fields.

**The two key things this module adds to the mailing engine:**

1. **A new `mailing_type = 'sms'` option** on `mailing.mailing`, which changes the form UI, switches the sending backend from email SMTP to the SMS IAP gateway, and swaps the template engine from `mail.template` to `sms.template`.
2. **Per-recipient tracing via unique trace codes**, which power the unsubscribe link (no email address required) and click tracking through shortened URLs.

---

## Dependency Chain

```
mass_mailing_sms
├── portal              # Portal contact subscription / mailing list opt-in/opt-out via portal
├── mass_mailing        # Core mailing engine: mailing.mailing, mailing.contact, mailing.list,
│                       #   mailing.trace, utm.campaign, link tracker. SMS uses the same models.
└── sms                # SMS gateway: sms.sms, sms.template, sms.composer, phone.blacklist,
                        #   phone validation
```

`mass_mailing_sms` does **not** depend on `phone_blacklist` directly, but `mailing_contact` inherits `mail.thread.phone` which uses the phone blacklist. The SMS blacklist check (`bl_sms`) is performed via SQL join in `mailing_list._get_contact_statistics_joins()`.

---

## Module File Structure

```
mass_mailing_sms/
├── __init__.py
├── __manifest__.py               # depends: portal, mass_mailing, sms
├── models/
│   ├── __init__.py
│   ├── mailing_contact.py         # Extends mailing.contact: adds mobile field
│   ├── mailing_list.py             # Extends mailing.list: SMS contact stats + opt-out logic
│   ├── mailing_mailing.py         # Extends mailing.mailing: SMS mailing type + send logic
│   ├── mailing_trace.py           # Extends mailing.trace: SMS trace fields + failure types
│   ├── sms_sms.py                 # Extends sms.sms: mailing_id + short-link rewrite
│   ├── sms_tracker.py             # Extends sms.tracker: mailing_trace_id + trace updates
│   ├── utm.py                     # Extends utm.campaign: SMS mailing counts + A/B test
│   └── res_users.py               # Extends res.users: systray split (email vs SMS activities)
├── controllers/
│   └── main.py                    # Unsubscribe and click-tracking HTTP routes
├── wizard/
│   ├── __init__.py
│   ├── sms_composer.py            # Extends sms.composer: mass SMS + mailing.trace integration
│   ├── mailing_sms_test.py        # New transient model: test SMS to specific numbers
│   ├── sms_composer_views.xml
│   └── mailing_sms_test_views.xml
├── views/
│   ├── mailing_contact_views.xml   # Adds mobile field to contact form/list
│   ├── mailing_list_views.xml      # Adds SMS contact count, action buttons for SMS
│   ├── mailing_mailing_views.xml   # SMS form view, SMS tab in mailing list
│   ├── mailing_trace_views.xml      # SMS trace list/form views
│   ├── mailing_sms_menus.xml       # Dedicated SMS menus under Marketing
│   ├── utm_campaign_views.xml      # Campaign: SMS mailing count, "Create SMS" action
│   └── mass_mailing_sms_templates_portal.xml  # Portal-accessible SMS templates
├── data/
│   └── utm.xml                   # Creates utm.medium record: 'SMS'
├── report/
│   └── mailing_trace_report_views.xml  # Pivot view for SMS trace analysis
├── demo/
│   ├── mailing_list_contact.xml
│   ├── mailing_subscription.xml
│   ├── mailing_mailing.xml
│   └── mailing_trace.xml
└── tests/                        # test_mailing_*.py (UI, internal, list, retry, A/B, controllers)
```

---

## L1: Model Inventory

| Model | Type | File | Extends | Description |
|---|---|---|---|---|
| `mailing.contact` | Regular | `models/mailing_contact.py` | `mailing.contact`, `mail.thread.phone` | Contact with a `mobile` Char field. Inherits phone blacklist support. |
| `mailing.list` | Regular | `models/mailing_list.py` | `mailing.list` | Mailing list with `contact_count_sms` and SMS-specific actions. |
| `mailing.mailing` | Regular | `models/mailing_mailing.py` | `mailing.mailing` | The campaign document. `mailing_type = 'sms'` is added here. |
| `mailing.trace` | Regular | `models/mailing_trace.py` | `mailing.trace` | Per-recipient SMS trace. Adds SMS failure types, code, number. |
| `sms.sms` | Regular | `models/sms_sms.py` | `sms.sms` | SMS records linked to a `mailing.mailing`. Adds `mailing_id`, `mailing_trace_ids`. |
| `sms.tracker` | Regular | `models/sms_tracker.py` | `sms.tracker` | Links SMS events to `mailing.trace`. Handles trace status updates on delivery receipts. |
| `utm.campaign` | Regular | `models/utm.py` | `utm.campaign` | Campaign with `mailing_sms_ids` (one2many) and A/B test SMS winner selection. |
| `utm.medium` | Regular | `models/utm.py` | `utm.medium` | Adds `mass_mailing_sms.utm_medium_sms` as a required, undeletable medium. |
| `mailing.sms.test` | Transient | `wizard/mailing_sms_test.py` | — | Test wizard: send SMS to specific phone numbers before launching campaign. |
| `sms.composer` | Regular | `wizard/sms_composer.py` | `sms.composer` | Extends composer with mass-SMS-specific trace creation, opt-out handling, link shortening. |

---

## L2: The `mailing.mailing` — SMS Mailing Type

**File:** `models/mailing_mailing.py`

### Adding the SMS Mailing Type

```python
class MailingMailing(models.Model):
    _inherit = 'mailing.mailing'

    mailing_type = fields.Selection(selection_add=[
        ('sms', 'SMS')
    ], ondelete={'sms': 'set default'})
```

When `mailing_type == 'sms'`, the form switches to the SMS view (defined in `views/mailing_mailing_views.xml`), which hides email fields and shows SMS-specific fields. The `ondelete='set default'` ensures that switching away from SMS resets the field to the next available option (typically `'mail'`).

### SMS-Specific Fields Added by This Module

```python
# 'sms_subject' overrides the 'subject' field helper (string becomes "Title" for SMS)
sms_subject = fields.Char(
    'Title', related='subject',
    readonly=False, translate=False,
    help='For an email, the subject your recipients will see in their inbox.\n'
         'For an SMS, the internal title of the message.')

# Computed from sms_template_id body
body_plaintext = fields.Text(
    'SMS Body', compute='_compute_body_plaintext',
    store=True, readonly=False)

# Template reference
sms_template_id = fields.Many2one('sms.template', string='SMS Template', ondelete='set null')

# IAP credit / account warnings (computed from mailing_trace_ids)
sms_has_insufficient_credit = fields.Boolean(
    'Insufficient IAP credits', compute='_compute_sms_has_iap_failure')
sms_has_unregistered_account = fields.Boolean(
    'Unregistered IAP account', compute='_compute_sms_has_iap_failure')

# Send mode
sms_force_send = fields.Boolean(
    'Send Directly',
    help='Immediately send the SMS Mailing instead of queuing up. Use at your own risk.')

# Opt-out link
sms_allow_unsubscribe = fields.Boolean('Include opt-out link', default=False)

# A/B Testing
ab_testing_sms_winner_selection = fields.Selection(
    related="campaign_id.ab_testing_sms_winner_selection",
    default="clicks_ratio", readonly=False, copy=True)
ab_testing_mailings_sms_count = fields.Integer(related="campaign_id.ab_testing_mailings_sms_count")
```

### `default_get` — Always Keep Archives for SMS

```python
def default_get(self, fields):
    res = super().default_get(fields)
    if fields is not None and 'keep_archives' in fields and res.get('mailing_type') == 'sms':
        res['keep_archives'] = True  # SMS traces are mandatory for tracking
    return res
```

SMS mailings **always** keep archives (`keep_archives = True`). This is non-negotiable because the archive holds the `mailing.trace` records, which power the unsubscribe link, click tracking, and delivery statistics. This is enforced in `default_get` rather than in `create()` so the UI also respects it.

### `_compute_medium_id` — Set the SMS UTM Medium

```python
@api.depends('mailing_type')
def _compute_medium_id(self):
    super()._compute_medium_id()
    for mailing in self:
        if mailing.mailing_type == 'sms' and (not mailing.medium_id or mailing.medium_id == self.env['utm.medium']._fetch_or_create_utm_medium('email')):
            mailing.medium_id = self.env['utm.medium']._fetch_or_create_utm_medium("sms", module="mass_mailing_sms").id
        elif mailing.mailing_type == 'mail' and (not mailing.medium_id or mailing.medium_id == self.env['utm.medium']._fetch_or_create_utm_medium("sms", module="mass_mailing_sms")):
            mailing.medium_id = self.env['utm.medium']._fetch_or_create_utm_medium('email').id
```

For SMS-type mailings, the `medium_id` is forced to the `'SMS'` UTM medium (created in `data/utm.xml` as `mass_mailing_sms.utm_medium_sms`). This separates SMS campaign statistics from email statistics in UTM reports. The condition `or ... == email_medium` handles the case where the previous value was email — it gets corrected to SMS.

### `_compute_sms_has_iap_failure` — IAP Error Detection

```python
@api.depends('mailing_trace_ids.failure_type')
def _compute_sms_has_iap_failure(self):
    self.sms_has_insufficient_credit = self.sms_has_insufficient_credit = False
    traces = self.env['mailing.trace'].sudo()._read_group([
        ('mass_mailing_id', 'in', self.ids),
        ('trace_type', '=', 'sms'),
        ('failure_type', 'in', ['sms_acc', 'sms_credit'])
    ], ['mass_mailing_id', 'failure_type'])

    for mass_mailing, failure_type in traces:
        if failure_type == 'sms_credit':
            mass_mailing.sms_has_insufficient_credit = True
        elif failure_type == 'sms_acc':
            mass_mailing.sms_has_unregistered_account = True
```

The IAP credit / account flags are computed by inspecting `mailing.trace` failure types. If any trace has `failure_type = 'sms_credit'`, the mailing shows a banner suggesting the user buys SMS credits. If any trace has `failure_type = 'sms_acc'`, it suggests registering the SMS IAP account.

### `create` — Sync `sms_subject` into `subject` for the Mailing Name

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('mailing_type') == 'sms' and vals.get('sms_subject'):
            vals['subject'] = vals['sms_subject']  # Used as mailing record name
    return super().create(vals_list)
```

The `subject` field is the record's display name and is used in menu items and mailing statistics. For SMS mailings, `sms_subject` is the UI field, and its value is synced into `subject` at creation time.

---

## L3: SMS Send Flow — From `mailing.mailing` to IAP Gateway

The send flow is triggered by `action_send_sms()`, which creates a `sms.composer` in mass mode. The composer handles recipient deduplication, body rendering, and calls the IAP gateway. Traces are created alongside each SMS.

```
User clicks "Send" on SMS mailing
        │
        ▼
mailing.action_send_sms()
  calls: composer = sms.composer.create(composer_values)
        │
        ▼
composer._action_send_sms()          [sms.composer / mass_mailing_sms override]
  ├─ calls: _get_optout_record_ids()     adds SMS opt-out list (from mailing_list)
  ├─ calls: _get_done_record_ids()       adds already-mailed contacts (dedup)
  ├─ calls: _prepare_body_values()       adds link trackers (shortened URLs)
  ├─ calls: _prepare_mass_sms_values()   attaches mailing.trace to each SMS
  ├─ calls: _filter_out_and_handle_revoked_sms_values()  removes canceled, creates cancel traces
  └─ calls: sms.sms._send()             via IAP gateway (sms module)
        │
        ▼
sms.sms._send()  →  IAP API  →  SMS gateway (Twilio / gateway provider)
        │
        ▼
Gateway calls delivery receipt webhook: POST /sms/status
  → sms.tracker._action_update_from_provider_state()
        │
        ▼
sms.tracker._action_update_from_sms_state()
  → _update_sms_traces()         writes trace_status + failure_type on mailing.trace
  → _update_sms_mailings()       sets mailing state to 'sending' / 'done'
```

### `action_send_sms` — Entry Point

```python
def action_send_sms(self, res_ids=None):
    for mailing in self:
        if not res_ids:
            res_ids = mailing._get_remaining_recipients()
        if res_ids:
            composer = self.env['sms.composer'].with_context(active_id=False).create(
                mailing._send_sms_get_composer_values(res_ids)
            )
            composer._action_send_sms()
    return True
```

`_get_remaining_recipients()` (from `mass_mailing`) returns only undelivered, non-opted-out recipients. The composer is created in context `active_id=False` to prevent the composer from being bound to the current record in the UI context.

### `_send_sms_get_composer_values` — Composer Configuration

```python
def _send_sms_get_composer_values(self, res_ids):
    return {
        'body': self.body_plaintext,
        'template_id': self.sms_template_id.id,
        'res_model': self.mailing_model_real,
        'res_ids': repr(res_ids),
        'composition_mode': 'mass',
        'mailing_id': self.id,
        'mass_keep_log': self.keep_archives,
        'mass_force_send': self.sms_force_send,
        'mass_sms_allow_unsubscribe': self.sms_allow_unsubscribe,
        'use_exclusion_list': self.use_exclusion_list,
    }
```

This method packages everything the SMS composer needs to send in mass mode. The `repr(res_ids)` serializes the ID list as a string because the composer accepts `res_ids` as a string representation for backward compatibility with the old `mail.compose.message` wizard.

### `action_retry_failed_sms` — Retry Failed SMS

```python
def action_retry_failed_sms(self):
    failed_sms = self.env['sms.sms'].sudo().search([
        ('mailing_id', 'in', self.ids),
        ('state', '=', 'error')
    ])
    failed_sms.mapped('mailing_trace_ids').unlink()  # Remove old failure traces
    failed_sms.unlink()                              # Remove failed SMS records
    self.action_put_in_queue()                       # Re-queue the mailing
```

Failed SMS records are deleted and re-created from scratch. The old traces are removed because they contain stale failure information. After cleanup, `action_put_in_queue()` resets the mailing state and re-triggers the send.

---

## L4: `mailing.trace` — SMS Trace Fields and Failure Types

**File:** `models/mailing_trace.py`

```python
class MailingTrace(models.Model):
    _inherit = 'mailing.trace'
    CODE_SIZE = 3  # Short random code for unsubscribe obfuscation

    trace_type = fields.Selection(selection_add=[
        ('sms', 'SMS')
    ], ondelete={'sms': 'set default'})

    # Integer ID avoids dangling FK if sms.sms is deleted
    sms_id_int = fields.Integer(string='SMS ID', index='btree_not_null')

    # Computed: links to the actual sms.sms record if it still exists
    sms_id = fields.Many2one('sms.sms', string='SMS', store=False,
                             compute='_compute_sms_id')

    sms_tracker_ids = fields.One2many('sms.tracker', 'mailing_trace_id',
                                       string='SMS Trackers')
    sms_number = fields.Char('Number')
    sms_code = fields.Char('Code')  # 3-char random code, used in unsubscribe URL
```

**Why `sms_id_int` as Integer instead of Many2one?** The comment in the source explains: `sms.sms` records can be deleted independently from their traces (e.g., when SMS are purged after retention). If `sms_id` were a Many2one, deleting `sms.sms` would cascade-delete the trace. Using an integer ID plus a computed Many2one avoids the FK constraint while still allowing UI display and controller lookups.

### SMS Failure Types

The `failure_type` selection is extended with SMS-specific codes. These are written to `mailing.trace` when the IAP gateway reports delivery failures.

| Failure Type | Meaning | Cause |
|---|---|---|
| `sms_number_missing` | Missing Number | No phone number on the contact |
| `sms_number_format` | Wrong Number Format | Number failed E.164 validation |
| `sms_credit` | Insufficient Credit | IAP account has no SMS credits |
| `sms_country_not_supported` | Country Not Supported | Destination country not supported by gateway |
| `sms_registration_needed` | Country-specific Registration Required | Regulatory registration required |
| `sms_server` | Server Error | SMS provider returned an error |
| `sms_acc` | Unregistered Account | SMS IAP account not registered |
| `sms_blacklist` | Blacklisted | Number in `phone.blacklist` |
| `sms_duplicate` | Duplicate | Number already targeted in this mailing |
| `sms_optout` | Opted Out | Contact opted out of this mailing list |
| `sms_expired` | Expired | Delivery attempt expired (no DLR received) |
| `sms_invalid_destination` | Invalid Destination | Number is not a valid mobile |
| `sms_not_allowed` | Not Allowed | Number type not allowed (e.g., landline) |
| `sms_not_delivered` | Not Delivered | Gateway confirmed delivery failure |
| `sms_rejected` | Rejected | SMS rejected by carrier |
| `twilio_authentication` | Authentication Error | Twilio-specific auth failure |
| `twilio_callback` | Incorrect Callback URL | Twilio callback misconfiguration |
| `twilio_from_missing` | Missing From Number | Twilio "from" number not set |
| `twilio_from_to` | From/To Identical | Sender and recipient number match |

---

## L5: `sms.composer` — Mass SMS Trace Integration

**File:** `wizard/sms_composer.py`

The SMS composer in mass mode (`composition_mode == 'mass'` + `mailing_id` set) is responsible for creating `mailing.trace` records alongside each SMS. The `mass_mailing_sms` override adds:

### `_prepare_mass_sms_trace_values` — Creating Traces Per Recipient

```python
def _prepare_mass_sms_trace_values(self, record, sms_values):
    trace_code = self.env['mailing.trace']._get_random_code()
    trace_values = {
        'mass_mailing_id': self.mailing_id.id,
        'model': self.res_model,
        'res_id': record.id,
        'sms_code': trace_code,
        'sms_number': sms_values['number'],
        'sms_tracker_ids': [Command.create({'sms_uuid': sms_values['uuid']})],
        'trace_type': 'sms',
    }
    if sms_values['state'] == 'error':
        trace_values['failure_type'] = sms_values['failure_type']
        trace_values['trace_status'] = 'error'
    elif sms_values['state'] == 'canceled':
        trace_values['failure_type'] = sms_values['failure_type']
        trace_values['trace_status'] = 'cancel'
    else:
        if self.mass_sms_allow_unsubscribe:
            stop_sms = self._get_unsubscribe_info(
                self._get_unsubscribe_url(self.mailing_id.id, trace_code))
            sms_values['body'] = '%s\n%s' % (sms_values['body'] or '', stop_sms)
    return trace_values
```

The `sms_code` (3-char random string) is embedded in the unsubscribe URL: `/sms/{mailing_id}/{trace_code}`. The controller validates that the code matches before allowing opt-out, preventing unauthorized opt-out attempts.

### `_get_unsubscribe_url` and `_get_unsubscribe_info`

```python
def _get_unsubscribe_url(self, mailing_id, trace_code):
    return tools.urls.urljoin(
        self.get_base_url(),
        '/sms/%s/%s' % (mailing_id, trace_code)
    )

@api.model
def _get_unsubscribe_info(self, url):
    return _('STOP SMS: %(unsubscribe_url)s', unsubscribe_url=url)
```

The unsubscribe text is appended to the SMS body: `"STOP SMS: https://yourdb.odoo.com/sms/5/aB3"`. This is the standard SMS opt-out mechanism — no email address or portal account required.

### `_prepare_body_values` — Link Shortening for Click Tracking

```python
def _prepare_body_values(self, records):
    all_bodies = super()._prepare_body_values(records)
    if self.mailing_id:
        tracker_values = self.mailing_id._get_link_tracker_values()
        for sms_id, body in all_bodies.items():
            body = self.env['mail.render.mixin'].sudo()._shorten_links_text(body, tracker_values)
            all_bodies[sms_id] = body
    return all_bodies
```

URLs in the SMS body are replaced with short codes: `https://example.com/promo` becomes `https://yourdb.odoo.com/r/Ab3Cd/s/12345`. When a recipient clicks the short link, `sms_short_link_redirect()` in the controller records the click on the `mailing.trace`.

---

## L6: `mailing.list` — SMS Contact Statistics and Opt-Out

**File:** `models/mailing_list.py`

### `contact_count_sms` — SQL Aggregation

```python
contact_count_sms = fields.Integer(
    compute="_compute_mailing_list_statistics",
    string="SMS Contacts")
```

The compute method is inherited from `mailing.list` (`_compute_mailing_list_statistics`). The `mass_mailing_sms` override adds SQL aggregate strings to `_get_contact_statistics_fields()` and joins to `_get_contact_statistics_joins()`:

```python
def _get_contact_statistics_fields(self):
    values = super()._get_contact_statistics_fields()
    values.update({
        'contact_count_sms': '''
            SUM(CASE WHEN
                (c.phone_sanitized IS NOT NULL
                AND COALESCE(r.opt_out,FALSE) = FALSE
                AND bl_sms.id IS NULL)
            THEN 1 ELSE 0 END) AS contact_count_sms''',
        'contact_count_blacklisted': '''
            SUM(CASE WHEN (bl.id IS NOT NULL OR bl_sms.id IS NOT NULL)
            THEN 1 ELSE 0 END) AS contact_count_blacklisted'''
    })
    return values

def _get_contact_statistics_joins(self):
    return super()._get_contact_statistics_joins() + '''
        LEFT JOIN phone_blacklist bl_sms ON c.phone_sanitized = bl_sms.number and bl_sms.active
    '''
```

**Logic:** A contact is counted as a valid SMS recipient if:
- `phone_sanitized IS NOT NULL` — a valid, E.164-formatted phone number exists
- `opt_out = FALSE` — not opted out of this list
- `bl_sms.id IS NULL` — not in the SMS blacklist (`phone_blacklist`)

The blacklisted count is also updated to include the SMS blacklist (`bl_sms`).

### `_mailing_get_opt_out_list_sms` — List-Level Opt-Out

```python
def _mailing_get_opt_out_list_sms(self, mailing):
    subscriptions = self.subscription_ids if self else mailing.contact_list_ids.subscription_ids
    opt_out_contacts = subscriptions.filtered(lambda sub: sub.opt_out).mapped('contact_id')
    opt_in_contacts = subscriptions.filtered(lambda sub: not sub.opt_out).mapped('contact_id')
    return list(set(c.id for c in opt_out_contacts if c not in opt_in_contacts))
```

Contacts who are opted out on **at least one** of the mailing's lists but opted in on **at least one other** list are excluded only from the lists they opted out of, not from the entire mailing. A contact who is opted out on all lists is excluded from the entire mailing.

---

## L7: `sms.tracker` — Delivery Receipt Updates

**File:** `models/sms_tracker.py`

The SMS tracker bridges the SMS gateway's delivery receipt (DLR) webhooks to the `mailing.trace` record.

```python
class SmsTracker(models.Model):
    _inherit = "sms.tracker"

    mailing_trace_id = fields.Many2one('mailing.trace', ondelete='cascade',
                                       index='btree_not_null')

    SMS_STATE_TO_TRACE_STATUS = {
        'error': 'error',
        'process': 'process',
        'outgoing': 'outgoing',
        'canceled': 'cancel',
        'pending': 'pending',
        'sent': 'sent',
    }
```

### `_action_update_from_sms_state` — Cascade Update to Traces and Mailings

```python
def _action_update_from_sms_state(self, sms_state, failure_type=False, failure_reason=False):
    super()._action_update_from_sms_state(...)
    trace_status = self.SMS_STATE_TO_TRACE_STATUS[sms_state]
    traces = self._update_sms_traces(trace_status, ...)
    self._update_sms_mailings(trace_status, traces)
```

When the SMS gateway sends a delivery receipt webhook (`/sms/status`), the `sms.tracker` updates the trace status. Then it checks whether the mailing should transition state:

- `trace_status == 'process'`: Mailing state → `'sending'`
- No more `'process'` traces + mailing not `'done'`: Mailing state → `'done'`, `sent_date` is set

### `_update_sms_mailings` — Auto-Close Mailing

```python
def _update_sms_mailings(self, trace_status, traces):
    if trace_status == 'process':
        traces.mass_mailing_id.write({'state': 'sending'})
        return

    mailings_to_mark_done = self.env['mailing.mailing'].search([
        ('id', 'in', traces.mass_mailing_id.ids),
        '!', ('mailing_trace_ids.trace_status', '=', 'process'),
        ('state', '!=', 'done'),
    ])
    if mailings_to_mark_done:
        for mailing in mailings_to_mark_done:
            mailing.write({
                'state': 'done',
                'sent_date': fields.Datetime.now(),
                'kpi_mail_required': not mailing.sent_date
            })
```

The mailing is automatically marked `'done'` when no traces remain in `'process'` state — meaning all delivery receipts have been received (or timed out).

---

## L8: `mailing.contact` — Mobile Field and Phone Blacklist

**File:** `models/mailing_contact.py`

```python
class MailingContact(models.Model):
    _name = 'mailing.contact'
    _inherit = ['mailing.contact', 'mail.thread.phone']

    mobile = fields.Char(string='Mobile')
```

Inheriting `mail.thread.phone` adds the phone blacklist integration:
- The `phone_sanitized` computed field automatically validates and formats the `mobile` field.
- The `phone_blacklist` link allows contacts to be globally blocked from SMS.
- `phone_validation.phone_format()` is used for E.164 normalization.

---

## L9: `utm.campaign` — SMS Mailing on Campaigns

**File:** `models/utm.py`

```python
class UtmCampaign(models.Model):
    _inherit = 'utm.campaign'

    mailing_sms_ids = fields.One2many(
        'mailing.mailing', 'campaign_id',
        domain=[('mailing_type', '=', 'sms')],
        string='Mass SMS',
        groups="mass_mailing.group_mass_mailing_user")
    mailing_sms_count = fields.Integer(
        'Number of Mass SMS', compute="_compute_mailing_sms_count",
        groups="mass_mailing.group_mass_mailing_user")
    ab_testing_mailings_sms_count = fields.Integer(
        "A/B Test Mailings SMS #", compute="_compute_mailing_sms_count")
    ab_testing_sms_winner_selection = fields.Selection([
        ('manual', 'Manual'),
        ('clicks_ratio', 'Highest Click Rate')],
        string="SMS Winner Selection", default="clicks_ratio")
```

The campaign form shows a "SMS Mailings" smart button (count) and "Create SMS" action button. A/B testing for SMS uses the `clicks_ratio` winner selection by default (SMS has no "open" metric, so click rate is the natural proxy).

### UTM Medium Protection

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_utm_medium_sms(self):
    utm_medium_sms = self.env.ref('mass_mailing_sms.utm_medium_sms', raise_if_not_found=False)
    if utm_medium_sms and utm_medium_sms in self:
        raise UserError(_(
            "The UTM medium '%s' cannot be deleted as it is used in some main "
            "functional flows, such as the SMS Marketing.",
            utm_medium_sms.name
        ))
```

The SMS medium cannot be deleted, even at uninstall. This is critical because existing SMS mailings and traces reference this medium — deleting it would break UTM reporting for all historical SMS campaigns.

---

## L10: Unsubscribe and Click-Tracking Controllers

**File:** `controllers/main.py`

### Route 1: `/sms/<mailing_id>/<trace_code>` — Initial Unsubscribe Page

```
GET /sms/5/aB3?sms_number=+6281234567890
```

The `blacklist_page` controller:
1. Validates `mailing_id` exists and `trace_code` matches a `mailing.trace` for this mailing.
2. Parses `sms_number` from the query string (passed from the carrier when the recipient replies STOP).
3. Sanitizes the number using phone validation with country code from GeoIP or company country.
4. If the number is valid and matches a trace, redirects to the confirmation page. Otherwise, renders an error page.

### Route 2: `/sms/<mailing_id>/unsubscribe/<trace_code>` — Confirm Opt-Out

```
GET /sms/5/unsubscribe/aB3?sms_number=+6281234567890
```

The `blacklist_number` controller:
1. Finds the matching trace.
2. If the mailing has contact lists, sets `opt_out = True` on the `mailing.subscription` record.
3. If the mailing targets a model directly (not a contact list), adds the number to `phone.blacklist`.
4. Logs the action on the trace and mailing.
5. Renders a confirmation page showing which lists the contact was opted out of.

### Route 3: `/r/<code>/s/<sms_id_int>` — Click Tracking Redirect

```
GET /r/Ab3Cd/s/12345
```

The `sms_short_link_redirect` controller:
1. Looks up `mailing.trace` by `sms_id_int`.
2. Calls `link.tracker.click` to record the click with IP, country, and `mailing_trace_id`.
3. Looks up the original URL from the `link.tracker` code.
4. Issues a 301 redirect to the original URL.

---

## L11: Practical Examples

### Example 1: Create and Send an SMS Campaign Programmatically

```python
# Find or create an SMS template
template = env['sms.template'].create({
    'name': 'Welcome SMS',
    'model_id': env['ir.model']._get('mailing.list').id,
    'body': 'Hi {{object.name}}, thanks for subscribing! Visit {{data.url}}',
})

# Create an SMS mailing
mailing = env['mailing.mailing'].create({
    'subject': 'Welcome!',
    'mailing_type': 'sms',
    'sms_template_id': template.id,
    'mailing_model_id': env['ir.model']._get('mailing.list').id,
    'contact_list_ids': [(4, mailing_list_id)],
    'sms_allow_unsubscribe': True,
})

# Send immediately (force_send)
mailing.write({'sms_force_send': True})
mailing.action_send_sms()

# Or send with queuing (default)
mailing.action_put_in_queue()
# Cron job mail_scheduler will call _action_send_mail() which calls action_send_sms()
```

### Example 2: Get SMS Statistics After a Campaign

```python
mailing = env['mailing.mailing'].browse(mailing_id)

# Read trace statistics
traces = env['mailing.trace'].search([
    ('mass_mailing_id', '=', mailing.id),
    ('trace_type', '=', 'sms'),
])

sent = traces.filtered(lambda t: t.trace_status in ('outgoing', 'process', 'pending', 'sent'))
delivered = traces.filtered(lambda t: t.trace_status == 'sent')
failed = traces.filtered(lambda t: t.trace_status == 'error')
clicked = traces.filtered(lambda t: t.trace_status in ('sent', 'sent') and t.links_click_datetime)

print(f"Sent: {len(sent)}, Delivered: {len(delivered)}, Failed: {len(failed)}")
```

### Example 3: Handle Delivery Receipt Webhook

```python
# When the SMS gateway calls POST /sms/status with a Twilio DLR payload:
# {
#   "MessageSid": "SM...",
#   "MessageStatus": "delivered" | "failed",
#   "ErrorCode": "30003" | ...
# }

# The sms module's webhook controller parses the payload and calls:
# sms.tracker._action_update_from_provider_error() or _action_update_from_sms_state()

# This cascades to:
# 1. Update mailing.trace.trace_status → 'sent' or 'error'
# 2. If last trace updated: mailing.mailing.state → 'done'
```

### Example 4: Retry Failed SMS in a Mailing

```python
mailing = env['mailing.mailing'].browse(mailing_id)

# Retry failed SMS for this mailing
failed_count = env['sms.sms'].sudo().search_count([
    ('mailing_id', '=', mailing.id),
    ('state', '=', 'error'),
])
print(f"Failed SMS: {failed_count}")

# Retry
mailing.action_retry_failed_sms()
```

---

## L12: IAP SMS Gateway — How Credits Are Consumed

The SMS IAP gateway (`sms` module) communicates with Odoo's In-App Purchase service to send SMS. Credits are deducted per SMS segment (each 160 characters = 1 segment for GSM-7 encoding, 70 characters for UCS-2).

```
User clicks "Send" on SMS mailing
        │
        ▼
sms.composer._action_send_sms()
  calls: env.company._get_sms_api_class()(env)._send_sms_batch(...)
        │
        ▼
SMS IAP API endpoint: https://sms-api.odoo.com/v1/send
  Body: { 'numbers': [...], 'content': '...', 'model': 'sms.sms', ... }
  Auth header: Bearer {IAP_APP_SECRET}
        │
        ▼
Gateway processes → deducts credits → forwards to carrier (Twilio)
        │
        ▼
Delivery receipt webhook: POST /sms/status
  → sms.tracker updates → mailing.trace updated
```

The `sms_has_insufficient_credit` and `sms_has_unregistered_account` banners on the mailing form give users a heads-up before they send. Clicking "Buy SMS Credits" opens the IAP credit purchase page.

---

## L13: A/B Testing for SMS

SMS A/B testing follows the same structure as email A/B testing (defined in `mass_mailing`):

```python
ab_testing_sms_winner_selection = fields.Selection(related="campaign_id.ab_testing_sms_winner_selection",
    default="clicks_ratio", readonly=False, copy=True)
```

**SMS winner selection only supports `clicks_ratio`** (unlike email which also has `opens_ratio`). This is because SMS has no equivalent to email open tracking — there is no "read receipt" for SMS. Click rate (tracked via shortened links) is the only measurable engagement metric.

```python
# Cron: _cron_process_mass_mailing_ab_testing (utm.campaign)
# Runs daily, checks if any A/B test window has closed
for campaign in ab_testing_campaign:
    ab_testing_mailings = campaign.mailing_sms_ids.filtered(lambda m: m.ab_testing_enabled)
    if ab_testing_mailings.filtered(lambda m: m.state == 'done'):
        ab_testing_mailings.action_send_winner_mailing()
```

---

## L14: Version Changes Odoo 18 to 19

| Aspect | Odoo 18 | Odoo 19 | Impact |
|---|---|---|---|
| `sms_subject` field | Char with related | Same | Unchanged |
| `body_plaintext` compute | `store=False` | `store=True, readonly=False` | Now storable |
| `sms_force_send` | Present | Present | Unchanged |
| `sms_allow_unsubscribe` default | `False` | `False` | Unchanged |
| `sms_tracker.mailing_trace_id` | Added | Present | New in Odoo 18/19 |
| `sms_id_int` instead of Many2one | New pattern | Stable | FK-safe trace linkage |
| `link_tracker.click` with `mailing_trace_id` | Present | Present | Click tracking per trace |
| `ab_testing_sms_winner_selection` | `clicks_ratio` only | Same | Stable |
| Unsubscribe via carrier reply (STOP SMS) | Via carrier | Via carrier + portal | Stable |
| IAP SMS gateway | Twilio + others | Same | Stable |
| `keep_archives` default for SMS | `True` | `True` | Enforced in `default_get` |

---

## Security Analysis

| Concern | Risk | Assessment |
|---|---|---|
| SMS sent to wrong numbers | HIGH | `sms_number` sanitized via `phone_validation.phone_format()` with country code before sending |
| Opt-out bypass via URL manipulation | MEDIUM | Unsubscribe requires matching `trace_code` (3-char) + `mailing_id` + valid phone number |
| Click tracking leaks recipient IP | LOW | IP stored on `link.tracker.click`; not exposed to end users |
| Spam / unsolicited SMS | MEDIUM | Requires IAP account registration; carrier enforces regulatory compliance |
| SMS body injection | LOW | Body is plain text; no HTML rendering |
| Trace code collision | LOW | 3-char alphanumeric = 60M combinations; checked against DB unique constraint implicitly |
| SMS sent after opt-out | MEDIUM | `mailing_list._mailing_get_opt_out_list_sms()` excluded before send; phone_blacklist also checked by IAP gateway |

---

## See Also

- [Modules/mass_mailing](mass_mailing.md) — Email marketing base: `mailing.mailing`, `mailing.contact`, `mailing.trace`, A/B testing
- [Modules/sms](sms.md) — SMS gateway: `sms.sms`, `sms.template`, `sms.composer`, IAP integration, phone validation
- [Modules/portal](portal.md) — Customer portal: contact subscription to mailing lists
- [New Features/What's New](New Features/What's New.md) — Odoo 19 changes across all modules
- [New Features/API Changes](New Features/API Changes.md) — Json field, @api.model_create_multi, deprecations
- [Core/API](Core/API.md) — `@api.depends`, `@api.onchange`, `@api.constrains`, `@api.model` decorator patterns
- [Patterns/Security Patterns](Patterns/Security Patterns.md) — ACL CSV, ir.rule, field groups, CSRF
