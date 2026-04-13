# IoT Base

## Overview
- **Name:** IoT Base
- **Category:** Hidden
- **Depends:** `web`
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Version:** 1.0

## Description
Base tools required by all IoT related modules. Provides the foundational JavaScript client for discovering and controlling hardware peripherals connected to the Odoo server.

## Key Features
- **Network utilities** - Client-side network discovery for IoT devices
- **Device controller** - JavaScript interface to communicate with hardware peripherals
- **Dummy asset loading** - Ensures `iot_drivers` static assets load on the IoT homepage

## Technical Details

### Assets (web.assets_backend)
```
iot_base/static/src/network_utils/*
iot_base/static/src/device_controller.js
```

### Related Modules
- [Modules/iot_drivers](modules/iot_drivers.md) - The actual device drivers (scales, printers, etc.)

## Notes
- `installable: True` - Can be installed independently
- Only contains frontend (JS) code; no Python models
- The `iot_drivers` module (`installable: False`) is the one that actually drives hardware
