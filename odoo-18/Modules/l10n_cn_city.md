---
Module: l10n_cn_city
Version: 18.0
Type: l10n/china
Tags: #odoo18 #l10n #accounting #china
---

# l10n_cn_city — China City Data

## Overview
Extension module for [Modules/l10n_cn](Modules/l10n_cn.md) that loads Chinese administrative divisions (provinces/municipalities/autonomous regions, cities, and county-level subdivisions) into Odoo's `res.city` and `res.country` data. Essential for correct Chinese address handling and place-of-supply determinations in GST-equivalent transactions.

## Country
China

## Dependencies
- l10n_cn
- base_address_extended

## Key Models
No custom model classes — purely a data module extending `res.city` and `res.country` records.

## Data Files
- `data/res_city_data.xml` — Chinese city records with state linkage and zipcodes
  - Records cover all provinces with granular city/county data
  - Format: `res.city` records with `state_id`, `country_id` (base.cn), `zipcode`, `name`
  - Examples: `china_city_860700` (Linzhi Region Motuo County, Tibet), `china_city_859700` (Ali Region Rutog County)
- `data/res_country_data.xml` — Additional country data for China context

## City Coverage
Covers all 34 provincial-level administrative divisions of China (23 provinces, 5 autonomous regions, 4 municipalities, 2 special administrative regions). City names include:

- **Tibet/Xizang (base.state_cn_XZ)**: Linzhi (860100–860700), Ali (859000s), Shigatse (857000s)
- **Xinjiang**: Urumqi, Kashgar, Hotan, etc.
- **Other provinces**: All prefecture-level cities with county-level subdivisions

## Installation
Data-only module. Install after `l10n_cn` and `base_address_extended`. No demo data.

## Historical Notes
Version 1.8 (matches `l10n_cn`). Author: Jeffery Chen Fan (jeffery9@gmail.com). Data originates from Chinese government administrative division codes (GB/T 2260 standard).