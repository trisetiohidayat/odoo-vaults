# Spreadsheet Dashboard for eLearning

## Overview
- **Name**: Spreadsheet dashboard for eLearning
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for online course and slide engagement metrics
- **Depends**: `spreadsheet_dashboard`, `website_sale_slides`
- **Auto-install**: Yes (when `website_sale_slides` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [[Modules/spreadsheet_dashboard]] template for eLearning managers and course instructors to track enrollment, completion rates, and revenue from paid courses sold via the website.

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample eLearning dashboard record.

## Key Features
- Course enrollment and completion rates
- Revenue from sold courses (via `website_sale_slides`)
- Member engagement metrics (slide views, time spent)
- Certification completion tracking
- Revenue per course and per instructor
- Auto-installs when `website_sale_slides` is active

## Related
- [[Modules/spreadsheet_dashboard]] — Dashboard framework
- [[Modules/website_slides]] — eLearning courses and slides
- [[Modules/website_sale_slides]] — Course sales via website
