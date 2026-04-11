# Checkout Newsletter

## Overview
- **Name**: Checkout Newsletter
- **Category**: Website/Website
- **Depends**: `website_sale`, `website_mass_mailing`
- **Summary**: Let new customers sign up for a newsletter during checkout
- **Auto-install**: True

## Key Features
- Adds a newsletter opt-in checkbox to the checkout process
- Subscribes the customer to a mailing list when they complete their order with the newsletter option selected
- Uses the `MassMailController.subscribe_to_newsletter()` method from `website_mass_mailing`
- Configurable per-website newsletter mailing list

## Extended Models

**`website`**
- `newsletter_id` (Many2one `mailing.list`) - Newsletter mailing list for this website

**`res.config.settings`**
- `is_newsletter_enabled` (Boolean) - Toggle newsletter checkbox on/off for the website
- `newsletter_id` (Many2one) - Related newsletter list
- `_compute_is_newsletter_enabled()` - Reads whether the newsletter view is active on the website
- `set_values()` - Activates/deactivates the newsletter view based on the setting

## Extended Controllers

**`WebsiteSale` (extends `website_sale.controllers.main.WebsiteSale`)**
- `_handle_extra_form_data()` - If `newsletter` is in form data and email is present, subscribes the email to the configured mailing list using `MassMailController.subscribe_to_newsletter()`

## Views
- `views/templates.xml` - Newsletter snippet/checkout widget
- `views/res_config_settings_views.xml` - Website settings form view

## Related
- [[Modules/website_sale]] - Base eCommerce
- [[Modules/website_mass_mailing]] - Mass mailing website integration
