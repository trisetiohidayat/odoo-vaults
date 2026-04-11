---
Module: l10n_es_pos_tbai
Version: 18.0
Type: l10n/spain-pos-tbai
Tags: #odoo18 #l10n #spain #pos #tbai #basque #lroe
---

# l10n_es_pos_tbai -- Spanish POS TicketBAI

## Overview
Bask Country (Euskadi) TicketBAI compliance for Point of Sale. TicketBAI is the mandatory electronic invoice system for the Basque Country (Araba/Álava, Gipuzkoa, Bizkaia). This module integrates TicketBAI signature requirements into the POS order flow.

## Country
Spain (Basque Country / Euskal Herria)

## Dependencies
- l10n_es_pos
- l10n_es_edi_tbai_pos (or equivalent TBai POS integration)

## Key Models
No Python model files — primarily XML translations and configuration for TicketBAI POS integration with Spanish POS.

## Data Files
- `i18n/l10n_es_pos_tbai.pot`: Translation template
- `i18n/es.po`: Spanish translations

## Historical Notes
- Version 18.0 in Odoo 18
- TicketBAI is mandatory in the Basque Country for all businesses
- LROE (Libro Registro de Operaciones con Terceros) is the underlying reporting format
- This module extends the base Spanish POS with TicketBAI-specific fields and workflows
