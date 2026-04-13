type: module
module: phone_validation
tags: [odoo, odoo19, phone]
created: 2026-04-06
---

# Phone Numbers Validation

## Overview
| Property | Value |
|----------|-------|
| Name | Phone Numbers Validation |
| Technical Name | `phone_validation` |
| Category | Hidden |
| Dependencies | base, mail |

## Description
This module adds the feature of validation and formatting phone numbers according to a destination country. It also adds phone blacklist management through a specific model storing blacklisted phone numbers. It adds mail.thread.phone mixin that handles sanitation and blacklist of records numbers.

## Key Models
| Model | Description |
|-------|-------------|
| phone.blacklist | Blacklisted phone numbers |
| mail.thread.phone | Mixin for phone handling |
| res.partner | Extended with phone validation |

## phone.blacklist
**File:** `models/phone_blacklist.py`
**Inherits:** mail.thread

### Fields
| Field | Type | Description |
|-------|------|-------------|
| number | Char | Phone number (E164 format) |
| active | Boolean | Active status |

### Key Methods
| Method | Description |
|--------|-------------|
| create | Create/activate blacklist entries |
| write | Sanitize phone on write |
| _search_number | Search with sanitization |
| add | Add number to blacklist |
| remove | Remove/deactivate from blacklist |
| phone_action_blacklist_remove | Open removal wizard |

## mail.thread.phone
**File:** `models/mail_thread_phone.py`
**Inherits:** mail.thread

### Fields
| Field | Type | Description |
|-------|------|-------------|
| phone_sanitized | Char | Sanitized phone number |
| phone_sanitized_blacklisted | Boolean | Is sanitized number blacklisted |
| phone_blacklisted | Boolean | Is phone field blacklisted |
| phone_mobile_search | Char | Search field |

### Key Methods
| Method | Description |
|--------|-------------|
| _search_phone_mobile_search | Search phone/mobile fields |
| _compute_phone_sanitized | Compute sanitized number |
| _compute_blacklisted | Check blacklist status |
| _phone_set_blacklisted | Add to blacklist |
| _phone_reset_blacklisted | Remove from blacklist |
| phone_action_blacklist_remove | Open unblacklist wizard |

## PHONE_REGEX_PATTERN Constant
```python
PHONE_REGEX_PATTERN = r'[\s\\./\(\)\-]'
```

## base (extended)
**File:** `models/models.py`
**Inherits:** base

### Key Methods
| Method | Description |
|--------|-------------|
| _phone_get_number_fields | Get phone field names |
| _phone_get_country | Get country for formatting |
| _phone_format | Format phone number |
| _phone_format_number | Apply format to number |

## res.partner (extended)
**File:** `models/res_partner.py`
**Inherits:** mail.thread.phone, res.partner

### Key Methods
| Method | Description |
|--------|-------------|
| _onchange_phone_validation | Validate phone on change |

## Related
- [Modules/sms](Modules/sms.md)
- [Modules/mail](Modules/mail.md)
```

---

```markdown
---