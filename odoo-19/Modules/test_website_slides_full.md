# Test Website Slides Full

## Overview
| Property | Value |
|----------|-------|
| **Name** | Test Full eLearning Flow |
| **Technical** | `test_website_slides_full` |
| **Category** | Hidden/Tests |
| **Installable** | True |
| **License** | LGPL-3 |

## Description
Tests the complete eLearning certification flow of Odoo. Installs the e-learning, survey, and e-commerce apps and tests the full certification flow including purchase, certification, failure, and success scenarios.

## Dependencies
```
website_sale_slides
website_slides_forum
website_slides_survey
```

## Data
- `data/res_groups_data.xml` - Group definitions for slide access

## Demo Data
- `data/product_demo.xml` - Demo products for eLearning purchases

## Test Assets
- `web.assets_tests` - Tour tests in `test_website_slides_full/static/tests/tours/**/*`

## Purpose
Complete eLearning certification flow testing:
- Course purchase via eCommerce
- Slide completion tracking
- Certification surveys
- Forum participation linked to courses
- Certification pass/fail scenarios
- Membership and access control
