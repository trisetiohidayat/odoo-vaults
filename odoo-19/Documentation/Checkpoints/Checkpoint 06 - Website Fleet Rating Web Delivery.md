# Checkpoint 6: Website, Fleet, Rating, Web, Delivery + Extensions

**Date:** 2026-04-06
**Status:** ✅ COMPLETED
**Modules:** 17 modules
**Completed:** 17/17

---

## Completed Files

| Module | Documentation File | Key Content |
|--------|-------------------|-------------|
| web | web.md | base.document.layout, ir.http, session_info, res.users.settings |
| rating | rating.md | rating.rating, rating.mixin, rating.parent.mixin, RATING_TEXT constants |
| fleet | fleet.md | fleet.vehicle, fleet.vehicle.model, fleet.vehicle.log.contract, FUEL_TYPES |
| delivery | delivery.md | delivery.carrier, delivery.price.rule, delivery.zip.prefix |
| sms | sms.md | sms.sms (state: outgoing→process→pending→sent→error), sms.template |
| barcodes | barcodes.md | barcode.nomenclature, barcode.rule, barcode_events_mixin |
| phone_validation | phone_validation.md | phone.blacklist, mail.thread.phone mixin |
| website | website.md | website, website.page, website.menu, website.visitor |
| website_blog | website_blog.md | blog.blog, blog.post (state: active/pending/close), blog.tag |
| website_slides | website_slides.md | slide.channel, slide.slide (slide_type: infographic/quiz/video), slide.channel.partner |
| website_sale | website_sale.md | product.template (website extended), sale.order (website extended), product.public.category |
| website_forum | website_forum.md | forum.forum, forum.post (state: active/pending/close/offensive), karma system |
| website_event | website_event.md | event.event (website extended), website.event.menu |
| website_crm | website_crm.md | crm.lead (website extended), visitor tracking |
| website_hr_recruitment | website_hr_recruitment.md | hr.applicant, hr.job (website extended) |
| website_payment | website_payment.md | payment.provider (website extended), donation transactions |
| website_livechat | website_livechat.md | im_livechat.channel (website extended), chatbot.script |

---

## Key Models Documented

### Web Framework
- `base.document.layout` - Company document layout with live preview
- `ir.http` - Session info, frontend routing
- `res.users.settings` - User preferences, embedded actions

### Rating System
- `rating.rating` - Rating (0-5 stars), access_token, consumed flag
- `rating.mixin` - rating_count, rating_avg, rating_percentage_satisfaction
- `mail.thread` (rating extended) - rating_ids, rating_apply(), rating_send_request()

### Fleet Management
- `fleet.vehicle` - license_plate, vin_sn, driver_id, fuel_type, state_id
- `fleet.vehicle.model` - brand_id, vehicle_type (car/bike), FUEL_TYPES constant
- `fleet.vehicle.log.contract` - state: futur/open/expired/closed, cost_frequency
- `fleet.vehicle.log.services` - service_type_id, state: new/running/done/cancelled

### Delivery
- `delivery.carrier` - delivery_type: base_on_rule/fixed, price_rule_ids, margin
- `delivery.price.rule` - variable: weight/volume/wv/quantity/price, operator, list_price

### Barcodes
- `barcode.nomenclature` - sanitize_ean, sanitize_upc, parse_barcode, UPC_EAN_CONVERSIONS
- `barcode.rule` - pattern, encoding: any/ean13/ean8/upca, type: alias/product

### SMS
- `sms.sms` - state: outgoing/process/pending/sent/error/canceled, failure_type codes

### Website Builder
- `website` - domain, company_id, social links, default_lang_id
- `website.visitor` - partner_id, visit_count, country_id, page_ids
- `website.page` - url, view_id, website_id

### eCommerce (website_sale)
- `sale.order` (website extended) - website_id, cart_recovery_email_sent, is_abandoned_cart
- `product.template` (website extended) - website_published, base_unit_id, accessory_product_ids

### Forum (website_forum)
- `forum.forum` - karma_gen_*, mode: questions/discussions, privacy levels
- `forum.post` - state: active/pending/close/offensive, vote_count, is_correct

### eLearning (website_slides)
- `slide.channel` - rating.mixin, privacy/enroll settings, member_count
- `slide.slide` - slide_type: infographic/quiz/video/article/document/questionnaire/embed

---

## Statistics Update

| Category | Total | This Batch | Cumulative |
|----------|-------|------------|------------|
| Website | 59 | 11 | 11 |
| Point of Sale | 37 | 0 | 1 |
| Other Modules | 43 | 6 | 14 |
| **TOTAL** | **304** | **17** | **57** |

---

## Running Agents (Batch 7 in progress)

- aec0582208ad16850: website_links, website_mail, website_profile, website_social, website_event_track, etc.
- aec681746ec2792af: im_livechat, portal, snailmail, hr_gamification, hr_holidays, hr_expense, etc.
- a45dfb6685673fe08: sale_margin, sale_project, project_account, account_payment, etc.
- a8e6ad5e1d0b1c3a0: stock_account, stock_delivery, mrp_account, google_calendar, etc.
- a1fedb08caec4970c: pos_hr, pos_loyalty, pos_restaurant, account_payment, iap, etc.

---

*Created: 2026-04-06*