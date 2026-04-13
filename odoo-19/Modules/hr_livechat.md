# HR Livechat

## Overview
- **Category:** Human Resources
- **Depends:** `hr`, `im_livechat`
- **Version:** 1.0
- **License:** LGPL-3
- **Auto-install:** Yes

## Description
Bridge module between HR and Livechat. Displays livechat channel statistics (mail channel history, member history, reporting) in the HR app, specifically linked to the employee who initiated the livechat session.

## Key Features
- Links livechat sessions to the employee who handled them.
- Shows channel statistics and reporting from livechat in the HR context.

## Data

### Views
- `views/discuss_channel_views.xml` - Links discuss channels to employees
- `views/im_livechat_channel_member_history_views.xml` - Member session history
- `views/im_livechat_report_channel_views.xml` - Livechat reporting views

## How It Works
When an internal user participates in a livechat session, the system records the channel member history linked to that user's employee record. This allows HR managers to view livechat activity per employee through the reporting views.

## Related
- [Modules/im_livechat](Modules/im_livechat.md) - Live chat channels and chatbot scripts
- [Modules/HR](Modules/HR.md) - Employee management
