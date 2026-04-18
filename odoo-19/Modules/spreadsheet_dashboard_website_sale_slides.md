---
tags: [odoo, odoo19, spreadsheet, dashboard, elearning, website-slides, courses, lms]
---

# spreadsheet_dashboard_website_sale_slides

## Overview

| Property | Value |
|----------|-------|
| Technical Name | `spreadsheet_dashboard_website_sale_slides` |
| Category | Productivity/Dashboard |
| Depends | `spreadsheet_dashboard`, `website_sale_slides` |
| Auto-install trigger | `website_sale_slides` |
| License | LGPL-3 |
| Module type | Data-only (no Python models) |

Provides a pre-configured [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) template named "eLearning" for course managers and content teams. Tracks enrollment, course completion, and revenue from paid online courses sold via the Odoo website. Auto-installs when `website_sale_slides` is active and appears in the Website dashboard group.

## Module Architecture

Pure data module — no Python model code.

```
spreadsheet_dashboard_website_sale_slides/
├── __init__.py               # empty
├── __manifest__.py           # depends on website_sale_slides, auto_install
└── data/
    ├── dashboards.xml        # creates spreadsheet.dashboard record
    └── files/
        ├── elearning_dashboard.json        # live dashboard
        └── elearning_sample_dashboard.json # sample fallback
```

## Dashboard Record Definition

Source: `/data/dashboards.xml`

```xml
<record id="spreadsheet_dashboard_elearning" model="spreadsheet.dashboard">
    <field name="name">eLearning</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_website_sale_slides/data/files/elearning_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('sale.model_sale_order'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_website_sale_slides/data/files/elearning_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_website"/>
    <field name="group_ids"
           eval="[Command.link(ref('website_slides.group_website_slides_manager'))]"/>
    <field name="sequence">200</field>
    <field name="is_published">True</field>
</record>
```

### Record Properties

| Field | Value | Significance |
|-------|-------|--------------|
| `name` | "eLearning" | Dashboard navigation label |
| `dashboard_group_id` | `group_website` | Appears under "Website" section |
| `group_ids` | `website_slides.group_website_slides_manager` | eLearning Managers only |
| `sequence` | 200 | Position within Website group |
| `main_data_model_ids` | `sale.order` | Empty-check model |
| `is_published` | True | Visible immediately |

## Access Control: eLearning Managers

The access group is `website_slides.group_website_slides_manager`, which is specific to the eLearning/Slides module — not the generic Sales Manager group. This means:

- eLearning course instructors with Manager rights can view the dashboard
- General Sales Managers without the eLearning group cannot see it (unless they also have the eLearning Manager role)
- The eCommerce dashboard (sequence 200, same group) uses `sales_team.group_sale_manager` — a different group from this dashboard

This design keeps course analytics separate from general sales visibility, appropriate since course content owners may not be part of the sales team.

## Key Distinction: website_sale_slides

`website_sale_slides` is the bridge between the eLearning system (`website_slides`) and eCommerce (`website_sale`). It enables:
- Selling course access through the online shop
- Granting enrollment upon purchase
- Tracking which courses drive revenue

Without `website_sale_slides`, courses could be free or manually managed — the revenue dimension would be absent. This dashboard specifically targets the paid-course business model.

## Data Sources and KPI Structure

### Primary Model: `sale.order`

The empty-data check uses `sale.order`, meaning the dashboard falls back to sample data only when no sales orders exist at all. This is a broad check — effectively, the sample dashboard is only shown on a completely fresh installation.

The live dashboard filters `sale.order` to course-related purchases by linking through `sale.order.line.product_id` to products that are associated with `slide.channel` (course channels).

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `partner_id` | Many2one | Student/buyer |
| `date_order` | Datetime | Purchase date |
| `website_id` | Many2one | Website the purchase occurred on |
| `amount_total` | Monetary | Purchase revenue |
| `state` | Selection | Confirmed purchases filter |

### eLearning Core Models

| Model | Description | Dashboard Use |
|-------|-------------|---------------|
| `slide.channel` | Course/channel | Course dimension |
| `slide.channel.partner` | Enrollment record | Student counts |
| `slide.slide` | Individual slides/lessons | Content analytics |
| `slide.slide.partner` | Slide completion per student | Completion tracking |
| `gamification.karma.gain` | Karma for engagement | Engagement metrics |

### slide.channel (Courses)

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `name` | Char | Course name |
| `website_id` | Many2one | Which website hosts the course |
| `visibility` | Selection | Public/private/invite |
| `enroll` | Selection | Free/paid/invite-only |
| `members_count` | Integer | Total enrolled students |
| `total_slides` | Integer | Number of lessons |
| `website_published` | Boolean | Visible on website |
| `can_publish` | Boolean | Publishable flag |
| `create_date` | Datetime | Course creation date |

### slide.channel.partner (Enrollment)

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `channel_id` | Many2one | Course |
| `partner_id` | Many2one | Student |
| `completion` | Float | Completion percentage (0-100) |
| `completed` | Boolean | Fully completed flag |
| `last_seen_slide_id` | Many2one | Last accessed lesson |
| `create_date` | Datetime | Enrollment date |

### slide.slide.partner (Lesson Progress)

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `slide_id` | Many2one | Lesson/slide |
| `partner_id` | Many2one | Student |
| `vote` | Integer | Student rating (1/-1) |
| `completed` | Boolean | Lesson completed |
| `quiz_attempts_count` | Integer | Quiz attempts |

## Key KPIs Tracked

**Revenue from Course Sales**
- Total revenue from paid course purchases
- Revenue per course (top revenue-generating courses)
- Revenue trend over time
- Average course price
- Revenue by website (multi-website setups)

**Enrollment Metrics**
- Total enrollments (`slide.channel.partner` count)
- New enrollments this period
- Enrollments per course
- Free vs. paid enrollment ratio
- Enrollment trend (growing or declining per course)

**Completion Analysis**
- Overall completion rate: `completed_enrollments / total_enrollments × 100`
- Completion rate per course
- Average completion percentage (for in-progress students)
- Students who started but never progressed (completion < 5%)
- Students who completed all lessons

**Lesson-Level Engagement**
- Most viewed slides/lessons
- Lessons with high drop-off rate (many students stop here)
- Lessons with the most quiz retries (indicating difficulty)
- Average vote score per lesson (content quality indicator)

**Student Journey**
- Time from enrollment to completion (completion speed)
- Students who returned after inactivity
- Multi-course students (bought more than one course)
- Certification completion rate (if quiz/certificate system used)

**Content Performance**
- Published vs. unpublished courses
- Courses with low completion rates (may need improvement)
- Courses with zero enrollments (visibility issue or wrong audience)
- Most commented slides (community engagement)

## website_sale_slides Revenue Flow

```
Student visits course page on website
    → Clicks "Buy" or "Enroll"
    → sale.order created (website_id set, course product as line)
    → Payment confirmed
    → sale.order state = 'sale'
    → slide.channel.partner created (enrollment granted)
    → Student can now access course content
```

The critical link: `sale.order.line.product_id` → `slide.channel.product_id` connects the purchase to the course. The dashboard uses this join to attribute revenue to specific courses.

## Free vs. Paid Courses

Odoo supports mixed enrollment policies on courses:
- `enroll = 'free'` → anyone can enroll without payment
- `enroll = 'payment'` → requires purchase through `website_sale`
- `enroll = 'invite'` → restricted, requires invitation

The "eLearning" dashboard focuses on paid courses (`enroll = 'payment'`), where revenue is generated. Free courses appear in enrollment counts but contribute zero revenue.

## Comparison with eCommerce Dashboard

Both the eCommerce and eLearning dashboards use `sale.order` as their primary model and appear at sequence 200 in the Website group:

| Aspect | eCommerce Dashboard | eLearning Dashboard |
|--------|--------------------|--------------------|
| Access group | `group_sale_manager` | `group_website_slides_manager` |
| Product filter | All website products | Course-linked products only |
| Extra models | None from eCommerce | slide.channel, enrollment data |
| Key differentiator | Conversion funnel | Learning progress & completion |

The two dashboards co-exist because they serve different audiences even within the same Website group.

## Auto-Install Behavior

```python
'auto_install': ['website_sale_slides'],
```

`website_sale_slides` is installed when a company both creates online courses (`website_slides`) AND sells them (`website_sale`). This is the LMS-as-a-revenue-stream model. The dashboard auto-installs to give course managers immediate analytics visibility.

## Dependencies Chain

```
spreadsheet_dashboard_website_sale_slides
├── spreadsheet_dashboard   # base framework
└── website_sale_slides     # depends on:
    ├── website_slides      # slide.channel, slide.slide, enrollment
    └── website_sale        # sale.order with website_id, payment
        ├── website         # website model
        └── sale            # sale.order
```

## LMS Analytics Use Cases

**Content optimization**: Identify lessons with high drop-off rates by looking at `slide.slide.partner` completion statistics. A lesson where 60% of students stop may need rewriting or splitting into smaller segments.

**Pricing analysis**: Compare conversion rate (visits → purchases) at different price points across courses. A/B test different prices and track revenue impact.

**Certification reporting**: For courses with `slide.channel.certification = True`, track how many students earn certificates vs. enroll. This is a key metric for compliance or professional development courses.

**Instructor performance**: For multi-instructor platforms, group courses by `channel_id.user_id` (channel responsible) and compare enrollment, completion, and revenue per instructor.

## Customization

1. **Learning path tracking**: If courses have prerequisites, track what percentage of students complete full learning paths
2. **Cohort analysis**: Track enrollment and completion for students who joined in the same month (cohort retention)
3. **Revenue per student**: Compute LTV (lifetime value) for students who purchased multiple courses
4. **Quiz performance**: Add quiz score statistics to identify which assessments are too hard or too easy

## Related Modules

- [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Dashboard framework
- [spreadsheet_dashboard_website_sale](Modules/spreadsheet_dashboard_website_sale.md) — eCommerce analytics (sibling module, same group)
- [spreadsheet_account](Modules/spreadsheet_account.md) — Accounting formulas for revenue integration
- `website_slides` — eLearning platform: slide.channel, slide.slide, enrollment models
- `website_sale_slides` — Paid course access: links course enrollment to sale orders

## Source Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_website_sale_slides/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_website_sale_slides/data/dashboards.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_website_sale_slides/data/files/elearning_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_website_sale_slides/data/files/elearning_sample_dashboard.json`
