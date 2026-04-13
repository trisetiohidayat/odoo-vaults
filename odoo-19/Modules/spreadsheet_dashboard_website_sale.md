# Spreadsheet Dashboard for eCommerce

## Overview
- **Name**: Spreadsheet dashboard for eCommerce
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for online shop metrics
- **Depends**: `spreadsheet_dashboard`, `website_sale`
- **Auto-install**: Yes (when `website_sale` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](modules/spreadsheet_dashboard.md) template for eCommerce managers showing online sales performance, cart abandonment, and website conversion metrics.

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample eCommerce dashboard record.

## Key Features
- Online order volume and revenue
- Average cart value and conversion rate
- Top-selling products online
- Abandoned cart recovery tracking
- Revenue per website/Sales team
- Auto-installs when `website_sale` is active

## Related
- [Modules/spreadsheet_dashboard](modules/spreadsheet_dashboard.md) — Dashboard framework
- [Modules/website_sale](modules/website_sale.md) — eCommerce/online shop
- [Modules/Sale](modules/sale.md) — Sales management
