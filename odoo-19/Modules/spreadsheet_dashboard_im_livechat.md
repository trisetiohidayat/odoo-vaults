# Spreadsheet Dashboard for Live Chat

## Overview
- **Name**: Spreadsheet dashboard for live chat
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for live chat and customer messaging metrics
- **Depends**: `spreadsheet_dashboard`, `im_livechat`
- **Auto-install**: Yes (when `im_livechat` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](modules/spreadsheet_dashboard.md) template for customer service managers to track live chat performance. Data is sourced from `im_livechat.channel`, `mail.message`, and session records from [Modules/im_livechat](modules/im_livechat.md).

This is a **data-only module**: contains `data/livechat_ongoing_sessions_actions.xml` (action buttons for live sessions) and `data/dashboards.xml` (sample dashboard record).

## Key Features
- Chat session volume and response time metrics
- Operator/agent performance tracking
- Satisfaction ratings from chat surveys
- Peak hours and channel breakdown
- Auto-installs when `im_livechat` is active

## Related
- [Modules/spreadsheet_dashboard](modules/spreadsheet_dashboard.md) — Dashboard framework
- [Modules/im_livechat](modules/im_livechat.md) — Live chat channels and chatbot scripts
- [Modules/mail](modules/mail.md) — Messaging and notifications
