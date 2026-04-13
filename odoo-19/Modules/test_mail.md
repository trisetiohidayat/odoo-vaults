# Test Mail (`test_mail`)

## Overview
- **Name:** Mail Tests
- **Category:** Hidden (Test Module)
- **Summary:** Performance and feature tests for mail module
- **Depends:** `mail`, `test_orm`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Overview

Test module providing mock/target models for Odoo's mail testing suite. Contains test models, test data, and extensive test cases. Not installable in production; used only in Odoo's automated test runs.

This module defines many test models used across the mail test ecosystem:

## Test Models

### `mail.test.simple` — Simple Chatter
Minimal model inheriting only `mail.thread`. Used to test basic message posting.

### `mail.test.simple.unnamed` — Simple No-Name
`mail.thread` model without a `name` field; tests rec_name handling.

### `mail.test.simple.main.attachment` — Main Attachment Support
Extends `mail.test.simple` with `mail.thread.main.attachment` mixin.

### `mail.test.simple.unfollow` — Unfollow Enabled
`mail.thread` with `_partner_unfollow_enabled = True`, allows non-internal users to use unfollow links.

### `mail.test.alias.optional` — Optional Alias Mixin
Tests `mail.alias.mixin.optional` with an optional `alias_id` field.

### `mail.test.gateway` — Mail Gateway Target
`mail.thread.blacklist` model with `_primary_email = 'email_from'`. Used for mail gateway tests and performance benchmarks.

### `mail.test.gateway.company` — Gateway with Company
Extends gateway model with a `company_id` field.

### `mail.test.gateway.main.attachment` — Gateway with Main Attachment
Gateway + main attachment management.

### `mail.test.gateway.groups` — Channel-like Gateway
`mail.thread.blacklist` + `mail.alias.mixin`, flat thread. Tests group/channel email handling.

### `mail.test.track` — Tracking Model
Tests field tracking with `tracking=True` on fields. Supports `track_fields_tofilter` to exclude specific fields from tracking display.

### `mail.test.activity` — Activity Model
`mail.thread` + `mail.activity.mixin`. Action methods: `action_start()` schedules activity, `action_close()` closes it.

### `mail.test.composer.mixin` — Invite-like Composer
`mail.composer.mixin` target model with `render_model = 'mail.test.composer.source'`.

### `mail.test.composer.source` — Composer Source Model
`mail.thread.blacklist` with `customer_id` field.

### `mail.test.lead` — Lead-like Model
Full lead model: `mail.thread.blacklist` + `mail.thread.cc` + `mail.activity.mixin`.
- `_mail_defaults_to_email = True` — uses `email_from` as primary
- `_get_customer_information()` — enriches with `lang`, `name`, `phone`
- `_message_post_after_hook()` — auto-links partner if email matches

### `mail.test.ticket` — Ticket-like Model
Complex model for ticket/chatter testing:
- Tracking templates on `customer_id` and `datetime`
- Custom `_notify_get_recipients_groups()` activates portal and customer buttons
- Custom `_creation_subtype()` and `_track_subtype()` based on `container_id`
- `_get_customer_information()` maps `phone_number` to phone

**Variants:**
- `mail.test.ticket.el` — Exclusion-list enabled (blacklist)
- `mail.test.ticket.mc` — Multi-company with container-level reply-to
- `mail.test.ticket.partner` — MC + blacklist + state-based tracking

### `mail.test.container` — Project-like with Alias
`mail.thread` + `mail.alias.mixin` with `_mail_post_access = 'read'`.
Alias targets `mail.test.ticket`. Used as parent/container for tickets.

**Variant:** `mail.test.container.mc` — Multi-company container.

### `mail.performance.thread` — Performance Test Thread
Simple model for performance benchmarking of mail.thread features.

### `mail.performance.thread.recipients` — Performance Recipients
Performance model with `_primary_email` and `tracking=1` on `user_id`.

### `mail.performance.tracking` — Multi-tracking Performance
Multiple `tracking=True` fields on one model for tracking performance tests.

### `mail.test.field.type` — Field Type Conflict Test
Tests that default `type` values don't conflict with attachment or lead types during gateway processing.

### `mail.test.lang` — Lang-based Chatter
Tests translations with lang-aware notification groups.

### `mail.test.track.all` — Track All Field Types
Comprehensive tracking test: all field types with tracking numbers. Also tests `properties` and `properties_parent_id`.

### `mail.test.track.compute` — Computed Field Tracking
Tests tracking on related/computed fields.

### `mail.test.track.duration.mixin` — Tracking Duration
Uses `_track_duration_field = 'customer_id'` to test duration tracking.

### `mail.test.rotting.resource` — Rotting Implementation
Tests rotting (staleness) based on stage: `_get_rotting_domain()` excludes `done=True` and `stage_id.no_rot=True`.

### `mail.test.track.groups` — Group-restricted Tracking
Tracking with `groups="base.group_user"` on some fields.

### `mail.test.track.monetary` — Monetary Field Tracking
Tests tracking on `Monetary` fields with currency.

### `mail.test.track.selection` — Selection Field Tracking

### `mail.test.multi.company` — Multi-company with Main Attachment
`mail.thread.main.attachment` with `company_id`.

### `mail.test.multi.company.read` — Read Access Posting
Same as above but with `_mail_post_access = 'read'` — can post messages with read-only access.

### `mail.test.multi.company.with.activity` — Multi-company Activity

### `mail.test.nothread` — No-thread Model
Not inheriting from `mail.thread` but implements `_mail_get_partner_fields()`.

### `mail.test.access` — Access Control Test
Tests ACLs: `access` field controls whether public/logged/followers/internal/admin can access. Used for ir.rule testing.

### `mail.test.access.custo` — Custom Access Operation
Tests `_mail_get_operation_for_mail_message_operation()` to customize message creation/read based on `is_locked`.

### `mail.test.access.public` — Public Access Model
`mail.thread` with public read/write access for guest testing.

### `mail.test.recipients` — CC Thread Model
`mail.thread.cc` with computed `customer_email`/`customer_phone` from `customer_id`.

### `mail.test.thread.customer` — Thread Customer
Extends `mail.test.recipients` with `_mail_thread_customer = True`.

### `mail.test.properties` — Properties in Mail
Tests `mail.thread` with `Properties` field and `PropertiesDefinition`.

## Test Data Files
- `data/test_mail_data.xml` — Test fixtures
- `data/mail_template_data.xml` — Mail templates
- `data/subtype_data.xml` — Mail subtypes

## Related
- [Modules/mail](modules/mail.md)
- [Modules/mass_mailing](modules/mass_mailing.md)
- [Modules/base_automation](modules/base_automation.md)
