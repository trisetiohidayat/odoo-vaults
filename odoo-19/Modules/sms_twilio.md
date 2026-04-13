---
tags:
  - #odoo19
  - #modules
  - #sms
  - #twilio
---

# SMS Twilio Module

**Module:** `sms_twilio`
**Path:** `~/odoo/odoo19/odoo/addons/sms_twilio/`
**Odoo Version:** 19.0
**Category:** Hidden/Tools
**Dependencies:** `sms`
**Edition:** Community Edition

## Overview

The `sms_twilio` module provides Twilio as an SMS provider for Odoo's SMS messaging system. It extends the base `sms` module with Twilio-specific API integration, allowing users to send SMS messages through Twilio's infrastructure instead of Odoo's own IAP (In-App Purchase) SMS service.

**Note:** This module exists in the Community Edition (CE), unlike many Twilio integrations in other ERPs which may be Enterprise-only.

## Module Structure

```
sms_twilio/
├── models/
│   ├── res_company.py           # Company Twilio settings
│   ├── res_config_settings.py    # Settings form
│   ├── sms_sms.py               # SMS record extension
│   ├── sms_composer.py          # Composer extension
│   ├── sms_tracker.py           # SMS tracking extension
│   ├── mail_notification.py     # Notification extension
│   └── sms_twilio_number.py      # Twilio phone numbers
├── controllers/
│   └── controllers.py           # Status callback endpoint
├── tools/
│   ├── sms_twilio.py            # Twilio API wrapper
│   └── sms_api.py               # SMS API extension
├── wizard/
│   └── sms_twilio_account_manage.py  # Account management
└── tests/
    ├── test_sms_twilio.py
    └── test_sms_twilio_controller.py
```

## Architecture

### Provider Pattern

Odoo's SMS system uses a provider abstraction. The `sms` module provides an abstract SMS API, and providers like `sms_twilio` implement the actual sending via their API.

```
┌─────────────────────────────────────────┐
│            sms.sms (Base Model)          │
│  - Holds SMS records                     │
│  - Determines provider via company        │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│        sms_twilio (Provider)              │
│  - Extends sms_sms                       │
│  - _split_by_api() routes to Twilio     │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         Twilio REST API                  │
│  - POST /2010-04-01/Accounts/.../Messages│
└─────────────────────────────────────────┘
```

### Key Classes

| Class | Purpose |
|-------|---------|
| `sms.sms` | Base SMS model (from `sms` module) |
| `sms_twilio.sms.sms` | Twilio-extended SMS |
| `res.company` | Extended with Twilio fields |
| `sms_twilio.tools.sms_twilio` | Twilio API wrapper |
| `sms_twilio.tools.sms_api` | Odoo SMS API wrapper |

## Company Configuration

### Twilio Fields on res.company

The module adds Twilio-specific fields to `res.company`:

```python
# Inherited from sms module
sms_provider = fields.Selection([
    ('twilio', 'Twilio'),
    ('sms', 'SMS Gateway (IAP)'),
])

# Twilio-specific fields (from sms module)
sms_twilio_account_sid = fields.Char('Twilio Account SID')
sms_twilio_auth_token = fields.Char('Twilio Auth Token')
sms_twilio_number_ids = fields.One2many('sms.twilio.number', 'company_id')
```

### sms.twilio.number Model

Stores available Twilio phone numbers per company:

```python
class SmsTwilioNumber(models.Model):
    _name = 'sms.twilio.number'
    _description = 'Twilio Number'

    name = fields.Char('Phone Number')
    country_id = fields.Many2one('res.country', 'Country')
    company_id = fields.Many2one('res.company')
```

**Selection Logic:** When sending SMS, the system picks a Twilio number based on:
1. Match country of recipient phone number
2. Fall back to first available number

## SMS Sending Flow

### 1. SMS Record Creation

```python
# Via composer or direct create
sms = env['sms.sms'].create({
    'number': '+1234567890',
    'body': 'Your OTP is 123456',
    'partner_id': partner.id,
})
```

### 2. Provider Routing

The `_split_by_api()` method routes SMS to the correct provider:

```python
def _split_by_api(self):
    """Override to handle twilio or IAP choice per company"""
    sms_by_company = defaultdict(...)
    for sms in self:
        company = sms._get_sms_company()
        if company.sms_provider == "twilio":
            # Route to Twilio
            yield TwilioSMSApi(...), company_sms
        else:
            # Route to IAP
            yield from super()._split_by_api()
```

### 3. Twilio API Call

The `SmsApi` class sends via Twilio:

```python
def _send_sms_twilio(self, twilio_account_sid, twilio_auth_token, from_numbers, to_numbers, body):
    """Send SMS via Twilio REST API"""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_account_sid}/Messages.json"
    
    for from_number in from_numbers:
        data = {
            'To': to_number,
            'From': from_number.name,
            'Body': body,
        }
        response = requests.post(url, data=data, auth=(twilio_account_sid, twilio_auth_token))
```

### 4. Status Callback

Twilio can notify Odoo of delivery status:

```python
def get_twilio_status_callback_url(company, uuid):
    base_url = company.get_base_url()
    return url_join(base_url, f'/sms_twilio/status/{uuid}')
```

When Twilio delivers (or fails) an SMS, it POSTs to this URL, and the controller updates the `sms.sms` record.

## Configuration

### Settings Path

`Settings > General Settings > SMS Provider`

### Required Configuration

1. **Twilio Account SID**: Found in Twilio Console
2. **Twilio Auth Token**: Found in Twilio Console
3. **Twilio Phone Numbers**: Add numbers purchased in Twilio

### Optional Configuration

- **SMS Sender Name**: For branded messages (if supported)

## Twilio API Integration

### Authentication

Twilio uses HTTP Basic Auth with Account SID as username and Auth Token as password:

```python
import base64
auth = base64.b64encode(
    f"{account_sid}:{auth_token}".encode()
).decode()
```

### API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `POST /Accounts/{SID}/Messages.json` | Send SMS |
| `GET /Accounts/{SID}/Messages/{SID}.json` | Check status |

### Number Selection

```python
def get_twilio_from_number(company, to_number):
    """Pick best Twilio number for destination"""
    country_code = phone_validation.phone_get_country_code_for_number(to_number)
    from_numbers = company.sms_twilio_number_ids
    
    if not from_numbers or not country_code:
        return from_numbers[:1]
    
    # Prefer numbers for same country
    return from_numbers.sorted(
        lambda rec: rec.country_code == country_code,
        reverse=True,
    )[0]
```

## Controller Endpoints

### Status Callback

**Route:** `/sms_twilio/status/<uuid>`

Handles Twilio's delivery status webhook:

```python
@http.route('/sms_twilio/status/<string:uuid>', type='http', auth='none', csrf=False)
def status_callback(self, uuid, **post):
    """Handle Twilio delivery status webhook"""
    # Update sms.sms record based on status
    # 'sent', 'delivered', 'failed', 'undelivered'
```

### Requirements
- `auth='none'` - No Odoo authentication (Twilio calls this)
- `csrf=False` - Twilio cannot provide CSRF token

## Failure Types

The module extends `sms.sms` failure types:

```python
failure_type = fields.Selection(selection_add=[
    ('twilio_authentication', 'Authentication Error'),
    ('twilio_callback', 'Incorrect callback URL'),
    ('twilio_from_missing', 'Missing From Number'),
    ('twilio_from_to', 'From / To identical'),
])
```

## Wizard: Account Management

The module provides a wizard for managing Twilio numbers:

```python
class SmsTwilioAccountManage(models.TransientModel):
    _name = 'sms.twilio.account.manage'
    
    def action_save_twilio_account(self):
        """Save Twilio credentials to company"""
        company = self.env.company
        company.sms_twilio_account_sid = self.account_sid
        company.sms_twilio_auth_token = self.auth_token
```

## Dependencies

| Module | Purpose |
|--------|---------|
| `sms` | Base SMS functionality and model |
| `phone_validation` | Phone number parsing and country detection |

## Security

### Configuration Storage
- Twilio credentials stored in `res.company` records
- `sms_twilio_auth_token` should be treated as sensitive

### Callback Security
- Uses HMAC signature verification when available
- Status callback validated against known SMS UUIDs

## Testing

The module includes comprehensive tests:

```python
# tests/test_sms_twilio.py
class TestSmsTwilio(TestSmsCommon):
    
    @users('admin')
    @mute_logger('odoo.addons.sms.models.sms_sms')
    def test_sms_send_twilio(self):
        """Test sending via Twilio"""
        ...
    
    @users('admin')
    @mute_logger('odoo.addons.sms.models.sms_sms')
    def test_sms_send_twilio_from_number(self):
        """Test number selection"""
        ...
```

## Differences from IAP SMS

| Aspect | Twilio | IAP SMS |
|--------|--------|---------|
| Cost | Pay Twilio directly | Odoo credits |
| Sender ID | Purchased numbers | Odoo shared numbers |
| Delivery reports | Webhook callback | Polling |
| International | Per-country pricing | Included |
| Custom sender | Yes (numbers) | Limited |

## See Also

- [Modules/sale_margin](Modules/sale_margin.md) - Margin calculation (another CE extension module)
- [Core/API](Core/API.md) - External API patterns
- [Tools/ORM Operations](Tools/ORM-Operations.md) - SMS sending via ORM
