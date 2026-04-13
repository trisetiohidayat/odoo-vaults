# IoT Drivers

## Overview
- **Name:** Hardware Proxy
- **Category:** Hidden
- **Depends:** (none - standalone)
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Enables remote use of peripherals connected to the Odoo server. This module only contains the enabling framework; actual device drivers are found in additional IoT modules that must be installed separately.

## Technical Details

### Architecture
This module is **not installable** (`installable: False`). It provides the shared driver infrastructure that other IoT-specific modules depend on.

### Directory Structure
```
iot_drivers/
  cli/            - Command-line interface tools
  controllers/   - HTTP controllers for device communication
  driver.py      - Base driver class
  event_manager.py - Event handling for hardware
  exception_logger.py - Error logging for driver failures
  http.py        - HTTP server for IoT communication
  iot_handlers/  - Hardware protocol handlers
  interface.py   - Device interface definitions
  main.py        - Entry point
  server_logger.py - Server-side logging
  tools/          - Utility functions
  websocket_client.py - WebSocket communication
  webrtc_client.py   - WebRTC for real-time device streams
  static/         - Frontend JS/CSS assets
  views/         - XML view definitions
```

### Key Classes
- **`driver.py`** - Base class for all IoT device drivers
- **`interface.py`** - Defines the interface that hardware drivers must implement
- **`event_manager.py`** - Manages hardware event subscriptions
- **`websocket_client.py`** - WebSocket client for bidirectional device communication
- **`webrtc_client.py`** - WebRTC client for video/audio streams from devices

### Related Modules
- [Modules/iot_base](iot_base.md) - Base frontend JS utilities

## Notes
- Marked `installable: False` - it is a shared framework module
- Actual peripheral support comes from modules like `pos_restaurant` (kitchen printers), etc.
