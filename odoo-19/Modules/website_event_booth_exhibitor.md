# Booths/Exhibitors Bridge

## Overview
- **Name**: Booths/Exhibitors Bridge
- **Category**: Marketing/Events
- **Depends**: `website_event_exhibitor`, `website_event_booth`
- **Summary**: Automatically creates a sponsor when a booth is booked on the website
- **Version**: 1.1
- **Auto-install**: True

## Key Features
- When a booth is confirmed via the website, automatically creates an `event.sponsor` record for the booth renter
- Links the booth to the sponsor record
- Fills in sponsor details (name, email, phone, slogan, description) from booth registration data

## Extended Models

### `event.booth.category` (extended)
- `use_sponsor` (Boolean) - When True, creating a booth automatically creates a sponsor
- `sponsor_type_id` (Many2one `event.sponsor.type`) - Sponsor level to assign
- `exhibitor_type` (Selection) - Sponsor type: `sponsor`, `exhibitor`, `online`
- `_onchange_use_sponsor()` - Auto-fills sponsor type defaults

### `event.booth` (extended)
- `use_sponsor` (Boolean, related to `booth_category_id`)
- `sponsor_type_id` (Many2one, related to `booth_category_id`)
- `sponsor_id` (Many2one `event.sponsor`) - Linked sponsor record
- `sponsor_name`, `sponsor_email`, `sponsor_phone`, `sponsor_subtitle`, `sponsor_website_description`, `sponsor_image_512` - Synced from sponsor
- `action_view_sponsor()` - Opens the related sponsor form view
- `_get_or_create_sponsor()` - Creates or finds existing sponsor for this booth/partner/type combination
- `_action_post_confirm()` - On booth confirmation, calls `_get_or_create_sponsor()`

## Controllers

### `WebsiteEventBoothController` (extends `WebsiteEventController`)

- `_prepare_booth_registration_values()` - Injects sponsor fields into booth registration values
- `_prepare_booth_registration_partner_values()` - Uses sponsor email/name as contact fallback
- `_prepare_booth_registration_sponsor_values()` - Builds sponsor values dict from request params (sponsor_name, sponsor_email, sponsor_phone, sponsor_subtitle, sponsor_website_description, sponsor_image_512)

## Related
- [Modules/website_event_booth](odoo-18/Modules/website_event_booth.md) - Booth registration on website
- [Modules/website_event_exhibitor](odoo-18/Modules/website_event_exhibitor.md) - Event exhibitor pages
- [Modules/event_booth](odoo-17/Modules/event_booth.md) - Booth management backend
