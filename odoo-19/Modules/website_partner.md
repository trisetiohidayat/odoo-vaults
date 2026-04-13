# Website Partner

## Overview
- **Name**: Website Partner
- **Category**: Website/Website
- **Depends**: `website`
- **Summary**: Partner directory on the website with SEO and publication controls
- **Version**: 0.1

## Models

### `res.partner` (extended)
- `website_description` (Html) - Full partner description for the website
- `website_short_description` (Text) - Short description/bio
- `is_published` (Boolean) - Controls visibility on the website
- `_compute_website_url()` - Sets URL to `/partners/<slug>`
- `_track_subtype()` - Notifies on `is_published` changes

## Controllers

### `WebsitePartnerPage`

**Routes:**
- `GET /partners/<partner_id>` - Public partner detail page
  - Supports slug redirection
  - Checks `website_published` flag or website restricted editor access
  - Renders `website_partner.partner_page` template

## Related
- [Modules/website_customer](modules/website_customer.md) - Customer references (depends on this)
- [Modules/website](modules/website.md) - Website builder
