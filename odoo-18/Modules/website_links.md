---
Module: website_links
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_links
---

## Overview

Extends link tracking for website-aware URL shortening. The shortened URL host is determined by the current website, enabling per-website branded short links.

**Key Dependencies:** `link_tracker`, `website`

**Python Files:** 1 model file

---

## Models

### link_tracker.py — LinkTracker

**Inheritance:** `link.tracker`

| Method | Description |
|--------|-------------|
| `action_visit_page_statistics()` | Opens `short_url+` in new tab for extended stats |
| `_compute_short_url_host()` | Computes `short_url_host`: uses current website base URL if current website equals company website, otherwise uses company base URL |

---

## Security / Data

**Access Control (`ir.model.access.csv`):**
- `model_link_tracker`: Website designer full access
- `model_link_tracker_code`: Website designer full access
- `model_link_tracker_click`: Website designer full access

---

## Critical Notes

- `_compute_short_url_host` enables multi-website link tracking with per-website short domains
- When current website IS the company's main website: uses current website base URL
- When current website is a different website: falls back to company base URL (for link shorteners configured at company level)
- `action_visit_page_statistics` opens the extended statistics view (`+` suffix) rather than the basic tracker URL
- v17→v18: No major changes
