# API Documentation

**Module:** `api_doc`
**Category:** Hidden
**Depends:** `web`
**Auto-install:** True
**Bootstrap:** True
**License:** LGPL-3

## Overview

Provides a dynamic, in-database API documentation page at `/doc`. The documentation is generated programmatically by introspecting Odoo's models, fields, and methods at runtime. It also includes an interactive playground to call model methods over HTTP with examples in various programming languages.

## Features

- **Dynamic documentation** — Lists all models and their fields/methods from the database.
- **API playground** — Execute methods over HTTP directly from the browser.
- **Multi-language examples** — Code samples in Python, JavaScript, PHP, Ruby, and more.
- **Bootstrap-loaded** — Loads at Odoo startup.

## Technical Notes

- Accessible at `/doc` URL.
- Requires `base.group_system` or API doc access group.
- Assets include OWL framework, Bootstrap SCSS, and custom `api_doc` frontend code.
- Includes a special `api_action.js` for in-form API method execution.
