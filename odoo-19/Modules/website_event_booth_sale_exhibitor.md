# website_event_booth_sale_exhibitor

Odoo 19 Events/Marketing Module

## Overview

`website_event_booth_sale_exhibitor` is a **bridge module** between `website_event_booth_exhibitor` (event exhibitor management) and `website_event_booth_sale` (booth sales on the website). It ensures that when exhibitors book and pay for booths on the website, their sponsor information is correctly captured.

## Module Details

- **Category**: Marketing/Events
- **Depends**: `website_event_exhibitor`, `website_event_booth_sale`
- **Version**: 1.0
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Auto-install**: Yes

## Key Components

### Models

#### `event.booth.registration` (Inherited)

Extends the booth registration with sponsor fields for the paid exhibitor workflow:

| Field | Type | Description |
|---|---|---|
| `sponsor_name` | Char | Sponsor/company name |
| `sponsor_email` | Char | Sponsor contact email |
| `sponsor_phone` | Char | Sponsor contact phone |
| `sponsor_subtitle` | Char | Slogan or tagline |
| `sponsor_website_description` | Html | Rich-text sponsor description |
| `sponsor_image_512` | Image | Sponsor logo (512px) |

**Key Methods:**
- `_get_fields_for_booth_confirmation()` — Extends parent to include all sponsor fields in booth confirmation.

## Usage

When a visitor reserves and pays for a booth on the website:
1. Booth registration form includes exhibitor/sponsor fields.
2. Upon confirmation, sponsor data is stored on `event.booth.registration`.
3. Exhibitor appears in the event's sponsor management.

## Relationship to Other Modules

| Module | Role |
|---|---|
| `website_event_exhibitor` | Exhibitor management and sponsor profiles |
| `website_event_booth_sale` | Booth reservation and payment on website |
| `website_event_booth_sale_exhibitor` | Bridge — paid booths carry exhibitor data |
