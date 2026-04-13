---
tags:
  - #odoo19
  - #modules
  - #iot
  - #infrastructure
---

# iot_box_image

## Overview

| Property | Value |
|----------|-------|
| Module | `iot_box_image` |
| Path | `odoo/addons/iot_box_image/` |
| Category | Hidden / Tools |
| Dependencies | None |
| Key Concept | Docker/IoT box image build infrastructure |

---

## Purpose

This module is **not a runnable Odoo module** -- it provides build tools and configuration files for creating an Odoo IoT Box Docker image. The IoT Box is a small device (often a Raspberry Pi or similar) that connects to Odoo and drives physical hardware like barcode scanners, label printers, and electronic scales in a warehouse or retail environment.

This module is marked `installable: False` and is only used during the Docker image build process.

---

## Module Structure

```
iot_box_image/
├── __init__.py
├── __manifest__.py
├── build_image.sh              # Main build script
├── build_utils/                # Helper scripts during build
│   ├── __init__.py
│   └── ...
├── configuration/              # Configuration files embedded in image
│   ├── __init__.py
│   └── ...
├── overwrite_before_init/      # Files overlaid before Odoo init
├── overwrite_after_init/       # Files overlaid after Odoo init
```

---

## Module Manifest

```python
{
    'name': 'IoT Box Image Build Tools',
    'category': 'Hidden/Tools',
    'summary': 'Build tools for the IoT Box image',
    'installable': False,     # Not installable -- build-time only
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

**Key characteristic:** `installable: False` -- this module cannot be installed in a running Odoo instance. It is only used as part of the Docker build process.

---

## Build Process Overview

The IoT Box image is a Docker container image that runs Odoo in a minimal configuration, optimized for embedded hardware:

1. **Base Image**: Starts from a minimal Python/Odoo base
2. **Configuration**: Copies `configuration/` files (odoo.conf, entrypoint scripts)
3. **Overwrite Before Init**: Overlays files before Odoo initialization
4. **Odoo Install**: Installs required Odoo modules
5. **Overwrite After Init**: Overlays files after initialization (custom configs)
6. **Build Utils**: Installs hardware drivers/utilities

---

## Key Directories

### `build_utils/`

Scripts and utilities used during the build process (before and after Odoo init). These typically include:
- Hardware detection scripts
- Network configuration helpers
- Startup scripts for the IoT service

### `configuration/`

Files that are embedded into the final image:

| File | Purpose |
|------|---------|
| `odoo.conf` | Odoo configuration for IoT Box mode |
| `entrypoint.sh` | Docker entry point script |
| `supervisord.conf` | Process supervisor config |

### `overwrite_before_init/`

Files overlaid onto the filesystem **before** Odoo's initialization step. These replace or patch files in the Odoo installation. Used for:
- Patching Odoo source files for IoT-specific behavior
- Adding custom modules
- Modifying configuration defaults

### `overwrite_after_init/`

Files overlaid **after** Odoo initialization. Used for:
- Final configuration customization
- IoT-specific server actions
- Custom addons final tweaks

---

## IoT Box Architecture

```
┌─────────────────────────────────────────┐
│          IoT Box (Docker Container)     │
├─────────────────────────────────────────┤
│  Odoo instance (lightweight mode)        │
│  └── Connects to main Odoo server       │
│       via longpolling / XML-RPC          │
│                                          │
│  Hardware Interfaces:                   │
│  ├── USB Barcode Scanner                │
│  ├── USB Label Printer (ZPL)            │
│  ├── Electronic Scale                   │
│  ├── Camera (for QR/barcode scanning)   │
│  └── GPIO pins (Raspberry Pi)           │
├─────────────────────────────────────────┤
│  Communication:                          │
│  └── IoT Box connects as dedicated      │
│      device to main Odoo server         │
└─────────────────────────────────────────┘
         ↕
┌─────────────────────────────────────────┐
│         Main Odoo Server                │
│  (Regular Odoo instance)                │
│  └── IoT Box device registered          │
│      via Settings > Devices              │
└─────────────────────────────────────────┘
```

---

## IoT Box Connection

The IoT Box connects to the main Odoo server as a "device":

1. Administrator registers the IoT Box in Odoo (Settings > Devices)
2. The IoT Box stores the server URL and database credentials
3. The IoT Box establishes a persistent connection to the main server
4. Hardware events (scan, print, weigh) are sent to the server as triggers
5. The server responds with actions (print label, display message)

---

## Related Modules

| Module | Role |
|--------|------|
| `iot` | Core IoT device management and hardware drivers |
| `hw_posbox_homepage` | IoT box web interface |
| `hw_drivers` | Hardware driver framework |
| `hw_screen` | Digital signage screen driver |
| `iot_box_image` | (this module) Docker image builder |

---

## Key Notes

- **Not installable**: Cannot be installed via Apps. Only used during Docker image build.
- **Build-time only**: No runtime Python code is executed when this module is "installed".
- **LGPL-3 License**: Unlike most Odoo CE modules which are LGPL-3, this is pure infrastructure.
- **Hidden category**: Does not appear in the Apps list.

---

## Related Documentation

- [Modules/IoT](modules/iot.md) -- IoT device management
- [Modules/Stock](modules/stock.md) -- Barcode scanning, label printing
- [Modules/POS](modules/pos.md) -- Point of Sale hardware integration
