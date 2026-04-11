# Test Sale Purchase EDI UBL (`test_sale_purchase_edi_ubl`)

**Category:** Hidden
**Depends:** `purchase_edi_ubl_bis3`, `sale_edi_ubl`
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Integration test for Electronic Data Interchange (EDI) of sale and purchase orders using the UBL 2.1/BIS Billing 3 format. Tests export of sale orders to UBL XML, import of purchase order UBL XML, and the end-to-end flow of order data through the EDI pipeline.

## Dependencies

| Module | Purpose |
|--------|---------|
| `sale_edi_ubl` | Sale order export/import via UBL |
| `purchase_edi_ubl_bis3` | Purchase order EDI with BIS Billing 3 profile |

## Models

This module has no Python models. It exercises the EDI flow by:
1. Creating sale orders in Odoo
2. Exporting to UBL 2.1 XML format
3. Simulating external EDI receipt (purchase order)
4. Importing the UBL document
5. Verifying field mapping and data integrity
