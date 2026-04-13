# Spreadsheet Dashboard for eLearning

## Overview
- **Name**: Spreadsheet dashboard for eLearning
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for online course and slide engagement metrics
- **Depends**: `spreadsheet_dashboard`, `website_sale_slides`
- **Auto-install**: Yes (when `website_sale_slides` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md) template for eLearning managers and course instructors to track enrollment, completion rates, and revenue from paid courses sold via the website.

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample eLearning dashboard record.

## Key Features
- Course enrollment and completion rates
- Revenue from sold courses (via `website_sale_slides`)
- Member engagement metrics (slide views, time spent)
- Certification completion tracking
- Revenue per course and per instructor
- Auto-installs when `website_sale_slides` is active

## Related
- [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md) — Dashboard framework
- [Modules/website_slides](website_slides.md) — eLearning courses and slides
- [Modules/website_sale_slides](website_sale_slides.md) — Course sales via website
