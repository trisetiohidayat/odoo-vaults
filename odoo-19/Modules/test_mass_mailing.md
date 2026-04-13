# Test Mass Mailing (`test_mass_mailing`)

## Overview
- **Name:** Mass Mail Tests
- **Category:** Marketing/Email Marketing (Test Module)
- **Summary:** Feature and performance tests for mass mailing
- **Depends:** `mass_mailing`, `mass_mailing_sms`, `sms_twilio`, `test_mail`, `test_mail_sms`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Overview

Test module for mass mailing features. Extends `test_mail` with models specifically designed to test mass mailing, SMS, blacklist behavior, link tracking, and performance. Not installable in production.

## Test Models

### `mailing.test.blacklist` — Blacklist Testing
`mail.thread.blacklist` with `_primary_email = 'email_from'`. Used for blacklist add/remove behavior tests.

### `mailing.test.performance` — Performance Benchmark
Large-recordset test model for performance measurements of mass mailing operations.

### `mailing.test.simple` — Simple Mailing Model
`mail.thread` for basic mailing flow testing.

## Test Coverage

The module includes tests covering:
- `test_blacklist.py` — Blacklist creation, management, unesco from mailing
- `test_blacklist_behavior.py` — Blacklist exclusion in mailing targeting
- `test_blacklist_mixin.py` — `mail.thread.blacklist` mixin behavior
- `test_link_tracker.py` — Link tracking in email mailings
- `test_link_tracker_sms.py` — Link tracking in SMS mailings
- `test_mail_composer.py` — Mass mail composer tests
- `test_mailing.py` — Core mailing campaign tests
- `test_mailing_server.py` — Mail server handling tests
- `test_mailing_sms.py` — SMS mailing tests
- `test_mailing_statistics.py` — Mailing statistics computation
- `test_mailing_statistics_sms.py` — SMS statistics
- `test_mailing_test.py` — General mailing test utilities
- `test_performance.py` — Performance test suite
- `test_sms_controller.py` — SMS web controller tests
- `test_utm.py` — UTM tracking in mailings

## Related
- [Modules/mass_mailing](modules/mass_mailing.md)
- [Modules/mail](modules/mail.md)
