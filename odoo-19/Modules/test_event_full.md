# Test Full Event Flow (`test_event_full`)

**Category:** Hidden/Tests
**Depends:** `event`, `event_booth`, `event_crm`, `event_crm_sale`, `event_sale`, `event_sms`, `payment_demo`, `website_event_booth_sale_exhibitor`, `website_event_exhibitor`, `website_event_sale`, `website_event_track`, `website_event_track_live`, `website_event_track_quiz`
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

End-to-end integration test for the full event management flow. Tests frontend and backend event flows including booth management, exhibitor portals, event sales, online event tracks with quizzes, live streaming, SMS confirmations, CRM lead generation from events, and payment processing.

## Dependencies

| Module | Purpose |
|--------|---------|
| `event` | Core event management |
| `event_booth` | Booth/sponsor management |
| `event_crm` | Event registration to CRM lead |
| `event_crm_sale` | Booth orders to CRM |
| `event_sale` | Event ticket sales |
| `event_sms` | SMS from event confirmations |
| `website_event_booth_sale_exhibitor` | Booth online purchase |
| `website_event_exhibitor` | Exhibitor portal |
| `website_event_sale` | Event registration website |
| `website_event_track` | Online track/speaker management |
| `website_event_track_live` | Live streaming integration |
| `website_event_track_quiz` | Quiz evaluation in tracks |
| `payment_demo` | Demo payment provider |

## Models

This module has no Python models. It serves as a meta-package for full-stack event tests.

## Data

- `views/event_registration_templates_reports.xml` — Registration report templates
- `ir_actions_report_data.xml` — Report action definitions

## Test Assets

- `test_event_full/static/src/js/tours/*` — Event flow test tours
- `test_event_full/static/src/js/tests/*` — Unit tests
