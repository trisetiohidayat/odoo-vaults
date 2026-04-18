---
title: Testing Guide
description: Comprehensive guide for testing Odoo 19 applications — test framework, fixtures, patterns, mocking, coverage, performance testing, and tour tests
tags: [odoo, odoo19, testing, unit-tests, integration-tests, qunit, tdd]
created: 2026-04-14
---

# Testing Guide

> **Prerequisite reading:** [Core/BaseModel](../Core/BaseModel.md) for model test setup, [Core/API](../Core/API.md) for API decorators, [Patterns/Workflow Patterns](../Patterns/Workflow Patterns.md) for testing state transitions

---

## Table of Contents

1. [Test Location & Structure](#1-test-location--structure)
2. [Test Class Structure](#2-test-class-structure)
3. [Test Fixtures](#3-test-fixtures)
4. [Running Tests](#4-running-tests)
5. [Common Test Patterns](#5-common-test-patterns)
6. [Mocking](#6-mocking)
7. [Test Coverage](#7-test-coverage)
8. [Performance Tests](#8-performance-tests)
9. [Tour Tests](#9-tour-tests)
10. [CI/CD Integration](#10-cicd-integration)
11. [Test Maintenance](#11-test-maintenance)

---

## 1. Test Location & Structure

### 1.1 Module Test Directory

Every Odoo module that contains tests follows a strict structure:

```
module_name/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── vendor.py
├── views/
│   └── vendor_views.xml
├── controllers/
│   └── vendor_controller.py
├── security/
│   └── ir.model.access.csv
├── data/
│   └── demo_data.xml
├── demo/
│   └── demo_vendor.xml
└── tests/
    ├── __init__.py                      # REQUIRED — registers test modules
    ├── common.py                        # Shared fixtures (optional but recommended)
    ├── test_vendor_model.py             # Unit tests for model logic
    ├── test_vendor_workflow.py          # Workflow/state machine tests
    ├── test_vendor_api.py               # HTTP controller tests (HttpCase)
    ├── test_vendor_constraints.py       # Constraint validation tests
    └── test_vendor_report.py            # Report generation tests
```

### 1.2 The `tests/__init__.py` Registration

This file is the critical link between Odoo's test discovery system and your test modules. Without it, tests will not run:

```python
# tests/__init__.py
# Each test file must be imported here
from . import test_vendor_model
from . import test_vendor_workflow
from . import test_vendor_api
from . import test_vendor_constraints
from . import common  # if it contains test classes
```

### 1.3 Test Module Pattern in `__manifest__.py`

In Odoo 19, tests are automatically discovered from the `tests/` directory. The manifest can optionally reference test data files:

```python
# __manifest__.py
{
    'name': 'Vendor Management',
    'version': '19.0.1.0.0',
    'author': 'Roedl',
    'depends': ['base', 'account', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/vendor_views.xml',
        'data/init_data.xml',
    ],
    'demo': [
        'demo/demo_vendor.xml',
    ],
    # No need to list individual test files in manifest
    # Odoo 12+ auto-discovers tests/tests/*.py
    'installable': True,
    'application': True,
}
```

### 1.4 XML Test Data

Odoo supports YAML-based test definitions for data-driven testing. XML test files in the `tests/` directory are loaded during test runs:

```xml
<!-- tests/test_data.xml -->
<odoo>
    <data noupdate="1">
        <!-- Test data that persists across tests -->
        <record id="test_partner" model="res.partner">
            <field name="name">Test Vendor</field>
            <field name="email">test@vendor.com</field>
            <field name="supplier_rank">1</field>
        </record>
    </data>
</odoo>
```

---

## 2. Test Class Structure

### 2.1 `TransactionCase` — Unit Tests

`TransactionCase` is the workhorse of Odoo testing. Each test method runs inside its own database transaction that is rolled back after the test completes. This guarantees isolation between tests.

```python
from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class TestVendorModel(TransactionCase):
    """
    Unit tests for vendor model CRUD and business logic.

    Test class naming convention:
    - Test<ModelName> for model tests
    - Test<Feature>Workflow for workflow tests
    - Test<ModelName>Constraints for constraint tests
    """

    def setUp(self):
        """
        setUp() runs before EACH test method.
        Use for test data creation that is reused across methods.
        """
        super(TestVendorModel, self).setUp()

        # Create a test vendor used by all test methods
        self.vendor = self.env['res.partner'].create({
            'name': 'Test Vendor Company',
            'email': 'test@vendor.com',
            'phone': '+1234567890',
            'supplier_rank': 1,
            'country_id': self.env.ref('base.id').id,
        })

        # Create a test product
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
            'list_price': 150.00,
            'standard_price': 80.00,
        })

        _logger.info("Test setup complete for %s", self._class.__name__)

    # ===== CRUD TESTS =====

    def test_vendor_create(self):
        """Test vendor creation with valid data."""
        vendor = self.env['res.partner'].create({
            'name': 'New Vendor',
            'email': 'new@vendor.com',
            'supplier_rank': 1,
        })
        self.assertTrue(vendor.id, "Vendor should be created")
        self.assertEqual(vendor.name, 'New Vendor')
        self.assertEqual(vendor.supplier_rank, 1)
        self.assertTrue(vendor.active, "Vendor should be active by default")
        _logger.info("test_vendor_create passed")

    def test_vendor_read(self):
        """Test reading vendor fields."""
        vendor = self.env['res.partner'].browse(self.vendor.id)
        self.assertEqual(vendor.name, 'Test Vendor Company')
        self.assertEqual(vendor.email, 'test@vendor.com')

    def test_vendor_write(self):
        """Test updating vendor fields."""
        self.vendor.write({'phone': '+9876543210'})
        self.vendor.invalidate_recordset()
        self.assertEqual(self.vendor.phone, '+9876543210')

    def test_vendor_unlink(self):
        """Test deleting a vendor."""
        vendor_id = self.vendor.id
        self.vendor.unlink()
        # Verify deletion
        deleted = self.env['res.partner'].browse(vendor_id)
        self.assertFalse(deleted.exists(), "Vendor should be deleted")

    # ===== BUSINESS LOGIC TESTS =====

    def test_vendor_invoice_creation(self):
        """Test creating a vendor bill/invoice."""
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 10,
                'price_unit': 150.00,
            })],
        })

        self.assertTrue(invoice.id, "Invoice should be created")
        self.assertEqual(invoice.partner_id, self.vendor)
        self.assertEqual(len(invoice.invoice_line_ids), 1)
        self.assertEqual(invoice.amount_total, 1500.00)

    def test_vendor_invoice_post_and_pay(self):
        """Test posting invoice and registering payment."""
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 5,
                'price_unit': 200.00,
            })],
        })

        # Post the invoice
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.payment_state, 'not_paid')

        # Register payment
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'journal_id': self.env['account.journal'].search([
                ('type', '=', 'bank')
            ], limit=1).id,
        })._create_payments()

        # Verify payment
        self.assertEqual(invoice.payment_state, 'paid')

    def test_vendor_credit_note(self):
        """Test vendor credit note (in_refund)."""
        refund = self.env['account.move'].create({
            'move_type': 'in_refund',
            'partner_id': self.vendor.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 2,
                'price_unit': 150.00,
            })],
        })

        self.assertTrue(refund.id)
        self.assertEqual(refund.move_type, 'in_refund')

        refund.action_post()
        self.assertEqual(refund.state, 'posted')

    # ===== COMPUTED FIELD TESTS =====

    def test_vendor_computed_total_invoiced(self):
        """Test computed field for total invoiced amount."""
        # Create and post an invoice
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 10,
                'price_unit': 100.00,
            })],
        })
        invoice.action_post()

        # Refresh vendor to recompute
        self.vendor.invalidate_recordset()
        self.vendor.refresh()

        # Check computed value
        total = self.vendor.total_invoiced
        self.assertEqual(total, 1000.00,
                        f"Expected total invoiced=1000, got {total}")

    # ===== CONSTRAINT TESTS =====

    def test_vendor_email_format_validation(self):
        """Test that invalid email format raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.vendor.write({'email': 'not-an-email'})

    def test_vendor_duplicate_email_constraint(self):
        """Test that duplicate email across vendors raises error."""
        # Create first vendor
        self.env['res.partner'].create({
            'name': 'Vendor 1',
            'email': 'same@email.com',
            'supplier_rank': 1,
        })

        # Second vendor with same email should fail
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'Vendor 2',
                'email': 'same@email.com',
                'supplier_rank': 1,
            })

    def test_vendor_required_name(self):
        """Test that empty name raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': '',
                'supplier_rank': 1,
            })

    # ===== SEARCH/DOMAIN TESTS =====

    def test_vendor_name_search(self):
        """Test name_search functionality."""
        partners = self.env['res.partner'].name_search('Test')
        partner_ids = [p[0] for p in partners]
        self.assertIn(self.vendor.id, partner_ids,
                     "Vendor should be found by name search")

    def test_vendor_search_by_email(self):
        """Test searching vendor by email."""
        vendors = self.env['res.partner'].search([
            ('email', '=', 'test@vendor.com'),
            ('supplier_rank', '>', 0),
        ])
        self.assertIn(self.vendor.id, vendors.ids)

    # ===== ARCHIVE/STATE TESTS =====

    def test_vendor_archive(self):
        """Test archiving a vendor."""
        self.vendor.write({'active': False})
        active = self.env['res.partner'].search([
            ('id', '=', self.vendor.id),
            ('active', '=', True),
        ])
        self.assertEqual(len(active), 0, "Archived vendor should not appear in active search")
```

### 2.2 `@tagged` Decorator — Test Categorization

Odoo uses `@tagged` to categorize tests, enabling selective test runs:

```python
from odoo.tests import TransactionCase, tagged

# All standard tests — run with --test-tags
@tagged('standard', '-custom')
class TestStandardFeatures(TransactionCase):
    pass

# Custom tests — run only with --test-tags=custom
@tagged('custom', '-standard')
class TestCustomFeatures(TransactionCase):
    pass

# Tests requiring enterprise
@tagged('enterprise')
class TestEnterpriseFeatures(TransactionCase):
    pass

# Tests that should not run at install time
@tagged('-at_install', 'post_install')
class TestPostInstall(TransactionCase):
    """Tests that require the full Odoo environment to be set up."""

    def setUp(self):
        super().setUp()
        # These tests run AFTER all modules are installed
        # Use for integration testing with full UI

    def test_full_workflow(self):
        """Test complete workflow with all modules loaded."""
        pass

# Multiple tags
@tagged('stock', 'inventory', ' warehouse')
class TestInventoryManagement(TransactionCase):
    pass
```

**Tag patterns:**
- `standard` — tests included in default test run
- `custom` — custom module tests
- `at_install` — run at module installation time (default)
- `post_install` — run after installation is complete
- `-standard` — exclude from standard runs
- `enterprise` — requires Enterprise Edition

### 2.3 `at_install` vs `post_install`

| Aspect | `at_install` (default) | `post_install` |
|--------|----------------------|----------------|
| When it runs | During module upgrade/install | After all modules installed |
| Environment state | Minimal — just this module | Full Odoo environment |
| Speed | Faster | Slower |
| Use for | Unit tests, model logic | Integration tests, UI tests |
| Access to UI | No | Yes |
| Cron jobs available | No | Yes |

```python
# DEFAULT — at_install
class TestVendorModel(TransactionCase):
    # Runs when module is installed
    # Fast, focused on model logic
    def test_crud(self):
        pass

# POST-INSTALL — for UI/integration testing
@tagged('post_install', '-at_install')
class TestVendorUI(TransactionCase):
    # Runs after full Odoo setup
    # Use for HttpCase, tour tests
    def test_form_renders(self):
        pass
```

### 2.4 `SingleTransactionCase`

`SingleTransactionCase` runs all test methods in a single transaction that commits after each method. This is faster for integration tests but risks test inter-dependence:

```python
from odoo.tests import SingleTransactionCase, tagged

@tagged('integration', 'slow')
class TestVendorIntegration(SingleTransactionCase):
    """
    Integration tests that run all methods in one transaction.
    Useful for testing a complete workflow across multiple operations.
    """

    @classmethod
    def setUpClass(cls):
        """Class-level setup — runs once before all test methods."""
        super().setUpClass()

        # Create shared test data
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Integration Vendor',
            'email': 'integration@vendor.com',
            'supplier_rank': 1,
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Integration Product',
            'type': 'product',
        })

        # Data persists across all test methods
        _logger.info("Integration test class setup complete")

    def test_01_create_vendor(self):
        """First test — creates data."""
        self.assertTrue(self.vendor.id)

    def test_02_create_invoice(self):
        """Second test — uses data from test_01."""
        # Vendor from setUpClass persists
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_date': fields.Date.today(),
        })
        self.assertTrue(invoice.id)
        # Store invoice ID for next test
        self.invoice_id = invoice.id

    def test_03_post_invoice(self):
        """Third test — uses invoice from test_02."""
        invoice = self.env['account.move'].browse(self.invoice_id)
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')

    def tearDown(self):
        """Runs after each test method (after commit)."""
        super().tearDown()
```

### 2.5 `HttpCase` — Controller and UI Tests

`HttpCase` launches a full HTTP server and simulates browser requests, enabling testing of controllers, web pages, and interactive UI flows:

```python
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user
import json


@tagged('api', 'http', '-standard')
class TestVendorAPI(HttpCase):
    """HTTP tests for REST API endpoints."""

    def setUp(self):
        """Set up authenticated test user."""
        super(TestVendorAPI, self).setUp()

        # Create test user for API calls
        self.user = new_test_user(
            self.env,
            login='api_test_user',
            groups='base.group_user',
            name='API Test User',
        )

        # Create test vendor
        self.vendor = self.env['res.partner'].create({
            'name': 'HTTP Test Vendor',
            'email': 'http@test.com',
            'supplier_rank': 1,
        })

    def test_api_vendor_list(self):
        """Test GET /api/vendors endpoint."""
        response = self.url_open('/api/vendors')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('vendors', data)

        # Verify our vendor is in the list
        vendor_ids = [v['id'] for v in data['vendors']]
        self.assertIn(self.vendor.id, vendor_ids)

    def test_api_vendor_get(self):
        """Test GET /api/vendors/<id> endpoint."""
        response = self.url_open(f'/api/vendors/{self.vendor.id}')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['name'], 'HTTP Test Vendor')
        self.assertEqual(data['email'], 'http@test.com')

    def test_api_vendor_create(self):
        """Test POST /api/vendors endpoint."""
        payload = {
            'name': 'New API Vendor',
            'email': 'newapi@vendor.com',
            'phone': '+1234567890',
        }

        response = self.url_open(
            '/api/vendors',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )

        self.assertEqual(response.status_code, 201)

        data = response.json()
        self.assertEqual(data['name'], 'New API Vendor')
        self.assertIn('id', data)

        # Verify it was created in DB
        created = self.env['res.partner'].search([
            ('email', '=', 'newapi@vendor.com')
        ])
        self.assertTrue(created)

    def test_api_vendor_update(self):
        """Test PUT /api/vendors/<id> endpoint."""
        payload = {'name': 'Updated API Vendor'}

        response = self.url_open(
            f'/api/vendors/{self.vendor.id}',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )

        self.assertEqual(response.status_code, 200)

        # Verify update persisted
        self.vendor.invalidate_recordset()
        self.assertEqual(self.vendor.name, 'Updated API Vendor')

    def test_api_vendor_delete(self):
        """Test DELETE /api/vendors/<id> endpoint."""
        vendor_id = self.vendor.id

        response = self.url_open(
            f'/api/vendors/{vendor_id}',
            method='DELETE'
        )

        self.assertEqual(response.status_code, 200)

        # Verify deletion
        deleted = self.env['res.partner'].browse(vendor_id)
        self.assertFalse(deleted.exists())

    def test_api_authentication_required(self):
        """Test that unauthenticated requests are rejected."""
        # Logout first
        self.session.logout()

        response = self.url_open('/api/vendors')
        # Should redirect to login or return 401
        self.assertIn(response.status_code, [401, 302, 403])

    def test_api_error_handling(self):
        """Test API returns proper error format."""
        # Create with missing required field
        payload = {'name': 'No Email Vendor'}  # email missing

        response = self.url_open(
            '/api/vendors',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )

        # Should return error, not crash
        self.assertIn(response.status_code, [400, 422])

        data = response.json()
        self.assertIn('error', data)
```

---

## 3. Test Fixtures

### 3.1 `setUpClass` — Class-Level Fixtures

Use `setUpClass` when you need test data that persists across all test methods. This is more efficient than creating data in each `setUp()`:

```python
from odoo.tests import TransactionCase
from odoo import fields


class TestVendorFixtures(TransactionCase):
    """
    Fixtures for vendor testing.
    Uses setUpClass for class-level data that doesn't change between tests.
    """

    @classmethod
    def setUpClass(cls):
        """Create test data once for all test methods."""
        super().setUpClass()

        # === CURRENCIES ===
        cls.currency_usd = cls.env.ref('base.USD')
        cls.currency_eur = cls.env.ref('base.EUR')

        # === COMPANIES ===
        cls.company = cls.env['res.company'].create({
            'name': 'Test Company A',
            'currency_id': cls.currency_usd.id,
        })

        # === PARTNERS (VENDORS) ===
        cls.vendor1 = cls.env['res.partner'].create({
            'name': 'Primary Test Vendor',
            'email': 'primary@test.com',
            'phone': '+1111111111',
            'supplier_rank': 1,
            'company_id': cls.company.id,
        })

        cls.vendor2 = cls.env['res.partner'].create({
            'name': 'Secondary Test Vendor',
            'email': 'secondary@test.com',
            'phone': '+2222222222',
            'supplier_rank': 1,
            'company_id': cls.company.id,
        })

        # === PRODUCTS ===
        cls.product_a = cls.env['product.product'].create({
            'name': 'Product A',
            'type': 'product',
            'list_price': 100.00,
            'standard_price': 60.00,
        })

        cls.product_b = cls.env['product.product'].create({
            'name': 'Product B',
            'type': 'product',
            'list_price': 200.00,
            'standard_price': 120.00,
        })

        # === ACCOUNTS ===
        cls.expense_account = cls.env['account.account'].search([
            ('user_type_id', '=', cls.env.ref('account.data_account_type_expenses').id),
        ], limit=1)

        # === JURNAL ===
        cls.journal = cls.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

    # Now all test methods can use cls.vendor1, cls.vendor2, etc.
    # without recreating them in each method

    def test_vendor1_can_create_invoice(self):
        invoice = self._create_invoice(cls.vendor1, cls.product_a)
        self.assertTrue(invoice.id)

    def test_vendor2_can_create_invoice(self):
        invoice = self._create_invoice(cls.vendor2, cls.product_b)
        self.assertTrue(invoice.id)

    def _create_invoice(self, vendor, product):
        """Helper method available to all test methods."""
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': vendor.id,
            'invoice_date': fields.Date.today(),
            'journal_id': self.journal.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'quantity': 5,
                'price_unit': product.list_price,
                'account_id': self.expense_account.id,
            })],
        })
```

### 3.2 Shared Test Base Classes

For large test suites, create a shared base class that all tests inherit from:

```python
# tests/common.py
from odoo.tests import TransactionCase
from odoo import fields


class TestVendorCommon(TransactionCase):
    """
    Base class for all vendor tests.
    Provides shared fixtures and helper methods.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create company
        cls.company = cls.env['res.company'].create({
            'name': 'Test Company',
            'currency_id': cls.env.ref('base.USD').id,
        })

        # Create vendors
        cls.vendor = cls._create_vendor('Test Vendor', 'test@vendor.com')
        cls.vendor_inactive = cls._create_vendor('Inactive Vendor', 'inactive@vendor.com')
        cls.vendor_inactive.write({'active': False})

        # Create products
        cls.product = cls._create_product('Test Product', 100.0)
        cls.product2 = cls._create_product('Test Product 2', 200.0)

        # Get expense account
        cls.expense_account = cls.env['account.account'].search([
            ('user_type_id', '=', cls.env.ref('account.data_account_type_expenses').id),
        ], limit=1)

        # Get purchase journal
        cls.purchase_journal = cls.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', cls.company.id),
        ], limit=1) or cls.env['account.journal'].search([
            ('type', '=', 'purchase'),
        ], limit=1)

    @classmethod
    def _create_vendor(cls, name, email):
        return cls.env['res.partner'].create({
            'name': name,
            'email': email,
            'supplier_rank': 1,
        })

    @classmethod
    def _create_product(cls, name, price):
        return cls.env['product.product'].create({
            'name': name,
            'type': 'product',
            'list_price': price,
        })

    def _create_invoice(self, vendor, product, qty=1, price=None):
        """Factory method for creating test invoices."""
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': vendor.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'quantity': qty,
                'price_unit': price or product.list_price,
            })],
        })

    def _create_confirmed_invoice(self, vendor, product, qty=1):
        """Factory method for posted invoices."""
        invoice = self._create_invoice(vendor, product, qty)
        invoice.action_post()
        return invoice
```

Then use it in test files:

```python
# tests/test_vendor_workflow.py
from .common import TestVendorCommon


class TestVendorWorkflow(TestVendorCommon):
    """Workflow tests using shared fixtures from common."""

    def test_confirm_and_pay_invoice(self):
        """Test complete invoice workflow."""
        invoice = self._create_confirmed_invoice(self.vendor, self.product)
        self.assertEqual(invoice.state, 'posted')

        # Register payment
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'journal_id': self.purchase_journal.id,
        })._create_payments()

        self.assertEqual(invoice.payment_state, 'paid')
```

### 3.3 `@mute_logger` — Suppressing Expected Errors

Use `@mute_logger` to suppress log messages from code being tested, keeping test output clean:

```python
from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestVendorWithWarnings(TransactionCase):
    """Tests that intentionally trigger warnings logged by the model."""

    @mute_logger('odoo.addons.my_module.models.vendor')
    def test_warning_logged_but_test_should_pass(self):
        """Code logs a warning but operation succeeds."""
        # The vendor model logs a warning when quantity exceeds threshold
        # but still proceeds — test should pass without seeing the warning
        vendor = self.vendor
        vendor.create_invoice_large_qty(quantity=10000)

    @mute_logger('odoo.addons.base.models.res_partner')
    def test_deprecated_api_warning(self):
        """Test code that uses deprecated API — warning suppressed."""
        # Using deprecated method that logs a warning
        vendor = self.vendor
        result = vendor._deprecated_method()
        self.assertEqual(result, expected_value)

    # Mute multiple loggers
    @mute_logger('odoo.addons.account.models', 'odoo.models')
    def test_multiple_loggers_muted(self):
        """Multiple loggers can be muted at once."""
        pass
```

### 3.4 Demo Data in Tests

```python
# Use demo data for integration tests
class TestWithDemoData(TransactionCase):
    """Tests that rely on module demo data."""

    def setUp(self):
        super().setUp()
        # Load demo data for this module
        self.env['ir.module.module'].search([
            ('name', '=', 'my_module'),
        ]).demo_data_load()

    def test_with_demo_partners(self):
        """Test with demo data partners."""
        demo_partner = self.env.ref('base.res_partner_1')
        self.assertTrue(demo_partner.exists())
```

---

## 4. Running Tests

### 4.1 Basic Test Execution

```bash
# Run all tests for a single module
./odoo-bin -c odoo19.conf -d roedl -i vendor_module --test-enable

# Run tests for already-installed module
./odoo-bin -c odoo19.conf -d roedl -u vendor_module --test-enable

# Run specific test file
./odoo-bin -c odoo19.conf -d roedl -u vendor_module --test-tags vendor_module.test_vendor_model

# Run tests with specific tags
./odoo-bin -c odoo19.conf -d roedl -u vendor_module --test-tags custom

# Exclude certain tags
./odoo-bin -c odoo19.conf -d roedl -u vendor_module --test-tags "-standard"

# Run all standard tests across all modules
./odoo-bin -c odoo19.conf -d roedl --test-tags standard --test-enable
```

### 4.2 Test Tag Syntax Reference

| Flag | Effect |
|------|--------|
| `--test-tags` | Filter which tests to run |
| `module` | Run all tests in module |
| `module.class` | Run specific test class |
| `module.class.method` | Run specific test method |
| `+tag` | Include tests with tag |
| `-tag` | Exclude tests with tag |
| Multiple tags | Comma-separated |

**Examples:**
```bash
# Run all tests in vendor_module
--test-tags vendor_module

# Run only custom-tagged tests
--test-tags custom

# Run everything EXCEPT standard tests
--test-tags "-standard"

# Run standard and custom tests
--test-tags standard,custom

# Run specific class
--test-tags vendor_module.test_vendor_model

# Run specific method
--test-tags vendor_module.test_vendor_model.test_vendor_create
```

### 4.3 Odoo Shell Test Runner

```bash
# Run tests via Odoo shell (for CI/CD)
./odoo-bin shell -c odoo19.conf -d roedl --db-filter=roedl

# In shell:
import logging
logging.getLogger('odoo.tests').setLevel(logging.INFO)

# Run specific test
from tests.test_vendor_model import TestVendorModel
import unittest
suite = unittest.TestLoader().loadTestsFromTestCase(TestVendorModel)
unittest.TextTestRunner(verbosity=2).run(suite)
```

### 4.4 pytest Integration

For projects that prefer pytest, Odoo can be integrated via `odoo-unittest` or direct `unittest` execution:

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

```python
# conftest.py for pytest
import pytest
from odoo.tests import TransactionCase


@pytest.fixture(scope='module')
def env():
    """Provide Odoo environment for pytest."""
    # Initialize Odoo environment
    import odoo
    odoo.cli.config
    # Return env for tests
    pass


@pytest.fixture
def vendor(env):
    """Factory fixture for test vendors."""
    return env['res.partner'].create({
        'name': 'Pytest Vendor',
        'email': 'pytest@vendor.com',
        'supplier_rank': 1,
    })


# Run with: pytest tests/ -v
```

### 4.5 Debugging Test Failures

```bash
# Run single test with full output
./odoo-bin -c odoo19.conf -d roedl -u vendor_module \
  --test-tags vendor_module.test_vendor_model.test_vendor_create \
  --stop-on-failure

# Enable SQL logging during tests
./odoo-bin -c odoo19.conf -d roedl -u vendor_module \
  --test-enable \
  --log-level debug_sql

# Run tests that match a pattern
./odoo-bin -c odoo19.conf -d roedl -u vendor_module \
  --test-tags "vendor_module,custom" \
  --log-level info

# Verbose output with test names
./odoo-bin -c odoo19.conf -d roedl -u vendor_module \
  --test-enable \
  --log-level test
```

---

## 5. Common Test Patterns

### 5.1 CRUD Testing Pattern

```python
def test_create_partner(self):
    """Test partner creation with all fields."""
    partner = self.env['res.partner'].create({
        'name': 'Test Partner',
        'email': 'test@partner.com',
        'phone': '+1234567890',
        'street': '123 Test Street',
        'city': 'Test City',
        'zip': '12345',
        'country_id': self.env.ref('base.id').id,
        'supplier_rank': 1,
    })
    self.assertTrue(partner.id)
    self.assertEqual(partner.name, 'Test Partner')

def test_read_partner(self):
    """Test reading partner with specific fields."""
    partner = self.env['res.partner'].browse(self.partner.id)
    data = partner.read(['name', 'email', 'phone'])[0]
    self.assertEqual(data['name'], 'Test Partner')
    self.assertEqual(data['email'], 'test@partner.com')

def test_write_partner(self):
    """Test updating partner."""
    self.partner.write({'phone': '+9999999999', 'city': 'New City'})
    self.partner.invalidate_recordset()
    self.assertEqual(self.partner.phone, '+9999999999')
    self.assertEqual(self.partner.city, 'New City')

def test_unlink_partner(self):
    """Test deleting partner."""
    pid = self.partner.id
    self.partner.unlink()
    self.assertFalse(self.env['res.partner'].browse(pid).exists())
```

### 5.2 `assertRecordValues()` — Efficient Assertion

Odoo provides `assertRecordValues()` for efficient batch assertion:

```python
def test_assert_record_values(self):
    """Test assertRecordValues() pattern."""
    # Create records
    vendors = self.env['res.partner'].create([{
        'name': f'Vendor {i}',
        'email': f'vendor{i}@test.com',
        'supplier_rank': 1,
    } for i in range(3)])

    # Assert on multiple records at once
    vendors.assertRecordValues([
        {'name': 'Vendor 0', 'email': 'vendor0@test.com'},
        {'name': 'Vendor 1', 'email': 'vendor1@test.com'},
        {'name': 'Vendor 2', 'email': 'vendor2@test.com'},
    ])

    # Works with subset of fields
    vendors[:2].assertRecordValues([
        {'name': 'Vendor 0'},
        {'name': 'Vendor 1'},
    ])
```

### 5.3 Testing State Machine Transitions

```python
def test_order_state_transitions(self):
    """Test complete sale order state workflow."""
    # Initial state: draft
    order = self.env['sale.order'].create({
        'partner_id': self.partner.id,
        'order_line': [(0, 0, {
            'product_id': self.product.id,
            'product_uom_qty': 5,
            'price_unit': 100.00,
        })],
    })

    self.assertEqual(order.state, 'draft')

    # draft → sent
    order.action_quotation_send()
    self.assertEqual(order.state, 'sent')

    # sent → sale
    order.action_confirm()
    self.assertEqual(order.state, 'sale')

    # sale → done
    order.action_done()
    self.assertEqual(order.state, 'done')

def test_invalid_transition_rejected(self):
    """Test that invalid state transitions raise errors."""
    order = self.create_confirmed_order()

    # Cannot go from 'done' back to 'draft' directly
    # The method should raise UserError
    with self.assertRaises(UserError):
        order.action_draft()
```

### 5.4 Testing Computed Fields

```python
def test_computed_field_amount_untaxed(self):
    """Test computed amount_untaxed field."""
    order = self.env['sale.order'].create({
        'partner_id': self.partner.id,
        'order_line': [
            (0, 0, {'product_id': self.product.id, 'product_uom_qty': 2, 'price_unit': 100.00}),
            (0, 0, {'product_id': self.product2.id, 'product_uom_qty': 3, 'price_unit': 50.00}),
        ],
    })

    # 2 * 100 + 3 * 50 = 350
    self.assertEqual(order.amount_untaxed, 350.00)

    # Change a line — should recompute
    order.order_line[0].write({'product_uom_qty': 5})
    order.invalidate_recordset()

    # 5 * 100 + 3 * 50 = 650
    self.assertEqual(order.amount_untaxed, 650.00)
```

### 5.5 Testing Onchanges

```python
def test_onchange_partner_id(self):
    """Test onchange fills default values when partner changes."""
    order = self.env['sale.order'].new({
        'partner_id': self.partner.id,
    })

    # Trigger onchange
    order.onchange_partner_id()

    # Check that related fields are auto-filled
    self.assertEqual(order.partner_invoice_id, self.partner)
    self.assertEqual(order.partner_shipping_id, self.partner)
    self.assertTrue(order.payment_term_id)

def test_onchange_product_id(self):
    """Test onchange fills product details."""
    order_line = self.env['sale.order.line'].new({
        'product_id': self.product.id,
        'order_id': self.order.id,
    })

    # Trigger onchange
    order_line.onchange_product_id()

    # Check product details are filled
    self.assertEqual(order_line.name, self.product.name)
    self.assertTrue(order_line.product_uom)
```

### 5.6 Testing Workflows with Wizards

```python
def test_wizard_confirm_invoice(self):
    """Test invoice confirmation via wizard."""
    invoice = self.create_draft_invoice()

    # Open confirmation wizard
    wizard = self.env['account.move.confirm'].create({})
    wizard.action_confirm()

    self.assertEqual(invoice.state, 'posted')

def test_wizard_cancel_with_reason(self):
    """Test cancellation with reason wizard."""
    invoice = self.create_posted_invoice()

    # Open cancellation wizard
    wizard = self.env['account.move.cancel'].create({})
    wizard.write({
        'reason': 'Duplicate invoice',
    })
    wizard.action_cancel()

    self.assertEqual(invoice.state, 'cancel')
```

---

## 6. Mocking

### 6.1 Using `unittest.mock` for External Calls

```python
from unittest import mock
from odoo.tests import TransactionCase


class TestVendorMocking(TransactionCase):
    """Tests with mocking for external service calls."""

    @mock.patch('odoo.addons.vendor_module.models.vendor.requests.post')
    def test_send_notification(self, mock_post):
        """Test that notification is sent to external service."""
        # Configure mock
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'ok'}
        mock_post.return_value = mock_response

        # Execute method
        vendor = self.vendor
        result = vendor._send_notification()

        # Verify mock was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], 'https://api.example.com/notify')

        # Verify result
        self.assertTrue(result)

    @mock.patch('odoo.addons.vendor_module.models.vendor.ExternalService')
    def test_external_service_integration(self, mock_service_class):
        """Test integration with external service class."""
        # Mock the external service
        mock_instance = mock.Mock()
        mock_instance.get_balance.return_value = 1000.00
        mock_service_class.return_value = mock_instance

        # Test
        vendor = self.vendor
        balance = vendor._get_external_balance()

        self.assertEqual(balance, 1000.00)
        mock_instance.get_balance.assert_called_once_with(vendor.ref)

    @mock.patch.object
    def test_method_with_decorator(self, mock_method):
        """Mock a method on the model itself."""
        vendor = self.vendor

        # Mock the helper method
        with mock.patch.object(vendor, '_get_default_category', return_value=1):
            result = vendor._compute_category()
            self.assertEqual(result, 1)
```

### 6.2 Mocking ORM Methods

```python
from unittest import mock


class TestVendorORMMock(TransactionCase):
    """Mock ORM methods for isolated testing."""

    @mock.patch('odoo.addons.vendor_module.models.vendor.env')
    def test_cascading_create(self, mock_env):
        """Test that creating a vendor triggers related creates."""
        # Setup mock to capture calls
        mock_vendor_model = mock.Mock()
        mock_vendor_model.create.return_value = mock.Mock(id=1)
        mock_env.__getitem__.return_value = mock_vendor_model

        # Call the method that creates vendor
        result = self._create_vendor_with_defaults('Test')

        # Verify create was called
        mock_vendor_model.create.assert_called_once()
```

### 6.3 `mock.patch.object` Pattern

```python
from unittest import mock
from odoo.tests import TransactionCase


class TestWithMockPatchObject(TransactionCase):
    """Using mock.patch.object for method-level mocking."""

    def test_send_email_with_mock(self):
        """Test email sending without actually sending email."""
        vendor = self.vendor

        # Mock the mail sending method
        with mock.patch.object(
            vendor.env['mail.mail'],
            'send',
            return_value=True
        ) as mock_send:
            result = vendor.action_send_statement()

            # Verify send was called
            self.assertTrue(result)
            mock_send.assert_called_once()

    def test_webhook_delivery_mock(self):
        """Test webhook delivery without network calls."""
        vendor = self.vendor

        with mock.patch('requests.post') as mock_post:
            mock_post.return_value = mock.Mock(status_code=200)

            result = vendor._deliver_webhook()

            self.assertTrue(result)
            mock_post.assert_called_with(
                vendor.webhook_url,
                json=mock.ANY,
                timeout=10
            )
```

### 6.4 Patching at Module Level

```python
import logging

# Module-level patch for module-level functions
from unittest import mock

# For functions imported at module level
# e.g., from my_module.utils import some_function


class TestModuleLevelPatches(TransactionCase):

    @mock.patch('odoo.addons.vendor_module.models.vendor.some_function')
    def test_with_module_level_patch(self, mock_func):
        """Patch a function at module level."""
        mock_func.return_value = 'mocked_value'

        # Call method that uses the function
        result = self.vendor._get_external_value()

        self.assertEqual(result, 'mocked_value')
        mock_func.assert_called_once()
```

---

## 7. Test Coverage

### 7.1 Enabling Coverage

```bash
# Install coverage
pip install coverage

# Run tests with coverage
coverage run --source=vendor_module \
  ./odoo-bin -c odoo19.conf -d roedl \
  -u vendor_module --test-enable

# Generate report
coverage report

# Generate HTML report
coverage html -d coverage_html

# Generate XML for CI
coverage xml -o coverage.xml
```

### 7.2 Coverage Configuration

```ini
# .coveragerc or setup.cfg
[run]
source = vendor_module
omit =
    tests/*
    */migrations/*
    */__init__.py
    */__manifest__.py

[report]
precision = 2
show_missing = True
skip_covered = False

# Exclude specific patterns
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    pass
    logging.debug
    _logger.debug

[html]
directory = coverage_html
```

### 7.3 Coverage Analysis Output

```python
# After running tests with coverage, analyze results:
# report_vendor_tests.py
import coverage
from coverage import Coverage

cov = Coverage()
cov.load()
report = cov.report()

# Find uncovered lines
missing = cov.analysis('vendor_module.models.vendor')
print(f"Uncovered lines: {missing[1]}")

# Generate per-module breakdown
data = cov.get_data()
measurements = data.measured_files()
for filepath in measurements:
    print(f"{filepath}: {len(measurements[filepath])} statements")
```

### 7.4 Critical Path Coverage

Focus coverage on these areas first (in order of priority):

1. **Business logic in model methods** — workflows, state transitions
2. **Constraints** — `@api.constrains` validation rules
3. **Computed fields** — calculation logic
4. **Wizards** — multi-step data processing
5. **Security** — ACL and record rules

```python
# Identify critical paths for coverage:
# 1. Identify all public methods in model
# 2. Test each public method
# 3. Cover all branches in if/else
# 4. Cover all exception paths

def test_critical_path_coverage(self):
    """Ensure all branches of critical method are tested."""
    vendor = self.vendor

    # Branch 1: active partner
    vendor.active = True
    result = vendor._compute_credit_limit()
    self.assertEqual(result, 1000.00)

    # Branch 2: inactive partner
    vendor.active = False
    result = vendor._compute_credit_limit()
    self.assertEqual(result, 0.00)  # Inactive = no credit
```

---

## 8. Performance Tests

### 8.1 Basic Performance Timing

```python
import time
from odoo.tests import TransactionCase


class TestVendorPerformance(TransactionCase):
    """Performance tests for vendor operations."""

    def test_create_vendor_performance(self):
        """Test that vendor creation completes within acceptable time."""
        start = time.perf_counter()

        for i in range(100):
            self.env['res.partner'].create({
                'name': f'Perf Vendor {i}',
                'email': f'perf{i}@test.com',
                'supplier_rank': 1,
            })

        elapsed = time.perf_counter() - start

        # 100 creates should take less than 5 seconds
        self.assertLess(elapsed, 5.0,
            f"Creating 100 vendors took {elapsed:.2f}s (should be < 5s)")

        print(f"Create performance: {elapsed:.3f}s for 100 records")

    def test_search_performance(self):
        """Test search performance at scale."""
        # Create test data
        vendors = self.env['res.partner'].create([{
            'name': f'Search Vendor {i}',
            'email': f'search{i}@test.com',
            'supplier_rank': 1,
        } for i in range(1000)])

        start = time.perf_counter()
        result = self.env['res.partner'].search([
            ('supplier_rank', '>', 0),
            ('name', 'ilike', 'Vendor'),
        ])
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.5,
            f"Search of 1000 vendors took {elapsed:.3f}s")
        print(f"Search performance: {elapsed:.4f}s for {len(vendors)} records")

    def test_compute_performance(self):
        """Test computed field performance."""
        # Create orders with lines
        orders = self.env['sale.order'].create([{
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': i + 1,
                'price_unit': 100.00,
            })],
        } for i in range(100)])

        start = time.perf_counter()
        for order in orders:
            _ = order.amount_total
        elapsed = time.perf_counter() - start

        print(f"Computed {len(orders)} order totals in {elapsed:.4f}s")
        self.assertLess(elapsed, 2.0)
```

### 8.2 Batch Performance Testing

```python
def test_batch_write_performance(self):
    """Test batch write performance."""
    vendors = self.env['res.partner'].create([{
        'name': f'Batch Vendor {i}',
        'email': f'batch{i}@test.com',
        'supplier_rank': 1,
    } for i in range(100)])

    start = time.perf_counter()
    vendors.write({'phone': '+1234567890'})
    elapsed = time.perf_counter() - start

    print(f"Batch write of {len(vendors)} records: {elapsed:.4f}s")
    self.assertLess(elapsed, 1.0)

def test_bulk_invoice_creation(self):
    """Test creating multiple invoices in batch."""
    invoices_vals = [{
        'move_type': 'in_invoice',
        'partner_id': self.vendor.id,
        'invoice_date': fields.Date.today(),
        'invoice_line_ids': [(0, 0, {
            'product_id': self.product.id,
            'quantity': 1,
            'price_unit': 100.00,
        })],
    } for _ in range(50)]

    start = time.perf_counter()
    invoices = self.env['account.move'].create(invoices_vals)
    elapsed = time.perf_counter() - start

    print(f"Created {len(invoices)} invoices in {elapsed:.3f}s")
    self.assertEqual(len(invoices), 50)
```

### 8.3 N+1 Query Performance Check

```python
from odoo.sql_db import Cursor


class QueryCounter:
    """Context manager for counting SQL queries."""

    def __init__(self, cr):
        self.cr = cr
        self.count = 0
        self._original_execute = cr.execute

    def __enter__(self):
        def counting_execute(query, params=None):
            self.count += 1
            return self._original_execute(query, params)

        self.cr.execute = counting_execute
        return self

    def __exit__(self, *args):
        self.cr.execute = self._original_execute


def test_no_n_plus_one_in_vendor_list(self):
    """Test that listing vendors doesn't produce N+1 queries."""
    # Create test vendors with invoices
    for i in range(10):
        vendor = self.env['res.partner'].create({
            'name': f'Vendor {i}',
            'email': f'v{i}@test.com',
            'supplier_rank': 1,
        })
        self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': vendor.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 100.00,
            })],
        })

    # Count queries when reading vendor list
    with QueryCounter(self.cr) as counter:
        vendors = self.env['res.partner'].search([
            ('supplier_rank', '>', 0),
            ('id', 'in', [self.env['res.partner'].search([], limit=10).ids]),
        ])
        # Read with necessary fields
        data = vendors.read(['name', 'email', 'total_invoiced'])

    print(f"Query count for 10 vendors: {counter.count}")
    # Should be < 5 queries, not 10+ (which would be N+1)
    self.assertLess(counter.count, 5,
        f"Expected < 5 queries, got {counter.count} (possible N+1)")
```

---

## 9. Tour Tests

### 9.1 Portal Tour Framework

Tours are automated UI tests that simulate user interactions. Odoo uses `odoo_tour.tour()` to define tour steps:

```python
# tests/test_vendor_tour.py
from odoo.tests import HttpCase, tagged


@tagged('e2e', 'tour', '-standard')
class TestVendorPortalTour(HttpCase):
    """End-to-end tour tests for portal UI."""

    def test_vendor_portal_dashboard_tour(self):
        """Test the vendor portal dashboard tour."""
        # Create and login as vendor user
        vendor_user = self.env['res.users'].create({
            'login': 'portal_vendor',
            'name': 'Portal Vendor User',
            'email': 'portal@vendor.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })

        vendor_partner = self.env['res.partner'].create({
            'name': 'Portal Vendor',
            'email': 'portal@vendor.com',
            'supplier_rank': 1,
            'user_ids': [(6, 0, [vendor_user.id])],
        })

        # Login as vendor user
        self.authenticate('portal_vendor', 'portal_vendor')

        # Run tour
        self.phantom_js(
            '/my',
            "odoo.tour.run('vendor_portal_dashboard', 'test')",
            "odoo.tour.tours.vendor_portal_dashboard",
            login='portal_vendor',
        )
```

### 9.2 Defining Tours in JavaScript

Tours are defined in JavaScript and registered via `web.Tour`:

```javascript
// static/src/js/vendor_tour.js
odoo.define('vendor_module.tour', function (require) {
    'use strict';

    var core = require('web.core');
    var tour = require('web.Tour');

    tour.register('vendor_portal_dashboard', {
        url: '/my',
        steps: [
            {
                title: "Welcome to Vendor Portal",
                content: "Welcome to the vendor portal dashboard. Let's take a tour.",
                trigger: '.o_portal_wrap',
            },
            {
                title: "View Invoice List",
                content: "Click on 'My Invoices' to see your invoices.",
                trigger: 'a[href*="/my/invoices"]',
            },
            {
                title: "Check Invoice Details",
                content: "Click on an invoice to view details.",
                trigger: 'tr.o_data_row:first',
            },
            {
                title: "Download PDF",
                content: "Click the Download PDF button.",
                trigger: 'button[data-download-pdf]',
            },
        ],
    });
});
```

### 9.3 Python Tour Tests

For testing without full browser automation, use `HttpCase` with direct URL testing:

```python
from odoo.tests import HttpCase, tagged
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@tagged('e2e', '-standard')
class TestVendorE2E(HttpCase):
    """E2E tests using HttpCase (no browser automation)."""

    def test_portal_access_vendor_invoices(self):
        """Test vendor can access their invoices via portal."""
        # Setup: create vendor user and invoice
        vendor_user = self._create_portal_user()
        invoice = self._create_vendor_invoice()

        # Login as vendor
        self.authenticate(vendor_user.login, vendor_user.login)

        # Access portal invoices
        response = self.url_open('/my/invoices')
        self.assertEqual(response.status_code, 200)

        # Parse response for invoice content
        content = response.text
        self.assertIn(invoice.name, content)

    def test_portal_invoice_pdf_download(self):
        """Test vendor can download invoice PDF."""
        vendor_user = self._create_portal_user()
        invoice = self._create_posted_invoice()

        self.authenticate(vendor_user.login, vendor_user.login)

        # Get PDF
        response = self.url_open(f'/my/invoices/{invoice.id}/pdf')
        self.assertEqual(response.status_code, 200)
        self.assertIn('pdf', response.headers.get('Content-Type', ''))
```

---

## 10. CI/CD Integration

### 10.1 GitHub Actions Workflow

```yaml
# .github/workflows/odoo-tests.yml

name: Odoo Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: odoo_test
          POSTGRES_USER: odoo
          POSTGRES_PASSWORD: odoo
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.10
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install coverage

      - name: Create Odoo config
        run: |
          cat > odoo_test.conf << EOF
          [options]
          db_host = localhost
          db_port = 5432
          db_user = odoo
          db_password = odoo
          db_name = odoo_test
          addons_path = ./odoo/addons,./custom_addons
          log_level = info
          EOF

      - name: Create test database
        run: |
          psql -h localhost -U odoo -c "CREATE DATABASE odoo_test;" || true

      - name: Run Odoo tests with coverage
        run: |
          coverage run \
            --source=custom_addons \
            --omit="tests/*" \
            ./odoo/odoo-bin \
            -c odoo_test.conf \
            -d odoo_test \
            --test-enable \
            --test-tags standard \
            --stop-after-init

      - name: Generate coverage report
        run: |
          coverage report --precision=2
          coverage xml -o coverage.xml

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          fail_ci_if_error: false

      - name: Upload test results
        if: always()
        run: |
          # Save test logs for debugging
          find . -name "*.log" -exec echo "=== {} ===" \; -exec cat {} \; >> test-results.log

      - name: Check coverage threshold
        run: |
          coverage report --data-file=.coverage | tee coverage_summary.txt
          # Fail if coverage is below threshold
          python scripts/check_coverage.py --min 70

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Run flake8
        run: |
          pip install flake8
          flake8 custom_addons --max-line-length=120 --extend-ignore=E501,W503

      - name: Run pylint
        run: |
          pip install pylint
          pylint custom_addons --disable=all --enable=E,F --max-line-length=120
```

### 10.2 GitLab CI Configuration

```yaml
# .gitlab-ci.yml

stages:
  - lint
  - test

variables:
  ODOO_VERSION: "19.0"
  POSTGRES_DB: "odoo_test"
  POSTGRES_USER: "odoo"
  POSTGRES_PASSWORD: "odoo"

lint:
  stage: lint
  image: python:3.10
  before_script:
    - pip install flake8 pylint
  script:
    - flake8 custom_addons --max-line-length=120
    - pylint custom_addons --disable=all --enable=E,F

test_odoo:
  stage: test
  image: odoo:19.0
  services:
    - postgres:15
  variables:
    POSTGRES_DB: $POSTGRES_DB
    POSTGRES_USER: $POSTGRES_USER
    POSTGRES_PASSWORD: $POSTGRES_PASSWORD
  script:
    - pip install coverage
    - coverage run ./odoo-bin -c odoo.conf -d test_db --test-enable --test-tags standard --stop-after-init
    - coverage report
  coverage: '/TOTAL.*\s+(\d+%)$/'
  artifacts:
    when: always
    paths:
      - coverage.xml
      - test-results.log
```

### 10.3 Docker-based Test Runner

```dockerfile
# Dockerfile.test
FROM odoo:19.0

# Install test dependencies
RUN pip install coverage pytest

# Copy custom addons
COPY custom_addons /mnt/extra-addons

# Run tests
CMD ["bash", "-c", "coverage run ./odoo-bin -c /etc/odoo/odoo.conf -d test_db --test-enable --test-tags custom --stop-after-init && coverage report"]
```

---

## 11. Test Maintenance

### 11.1 Test Organization Best Practices

```python
# Recommended test file organization:

# tests/test_vendor_model.py
# 1. Imports
# 2. Test class definition
# 3. setUp / setUpClass
# 4. Test methods in logical groups:
#    a. Creation tests (test_create_*)
#    b. Update tests (test_write_*)
#    c. Deletion tests (test_unlink_*)
#    d. Business logic tests (test_*_action)
#    e. Constraint tests (test_*_constraint)
#    f. Search tests (test_*_search)

# Name test methods descriptively:
# test_vendor_create_with_valid_email
# test_vendor_create_with_invalid_email_raises_validation_error
# test_vendor_action_confirm_with_no_lines_raises_error
```

### 11.2 Test Review Checklist

Before committing tests, verify:

- [ ] Test names are descriptive (not `test_1`, `test_2`)
- [ ] Each test has a single assertion focus
- [ ] Test data is created in `setUp()` or `setUpClass()`
- [ ] Test cleans up after itself (or relies on transaction rollback)
- [ ] Mocks are properly patched and restored
- [ ] Performance tests have meaningful thresholds
- [ ] Error cases are tested (`with self.assertRaises()`)
- [ ] Edge cases are covered (empty, zero, very large values)
- [ ] No hardcoded IDs or demo data references that could break

### 11.3 Regular Test Maintenance Schedule

| Interval | Task |
|----------|------|
| Daily | Review failed test notifications from CI |
| Weekly | Add tests for new features |
| Weekly | Update tests affected by changed code |
| Monthly | Refactor slow tests |
| Monthly | Remove obsolete tests |
| Quarterly | Review coverage and set new targets |
| Quarterly | Update test documentation |

### 11.4 Handling Test Flakiness

```python
# Flaky test patterns and fixes:

# PROBLEM: Timing-dependent test
def test_async_notification(self):
    # Race condition — notification may not be processed yet
    result = vendor._check_notification_sent()
    self.assertTrue(result)  # May fail intermittently

# FIX: Wait for async processing
def test_async_notification(self):
    vendor._send_notification_async()

    # Wait for queue job to complete
    with self.env.cr.savepoint():
        processed = self.env['mail.notification'].search([
            ('res_partner_id', '=', vendor.id),
        ])
        max_wait = 10
        while not processed and max_wait > 0:
            time.sleep(1)
            max_wait -= 1
            processed = self.env['mail.notification'].search([
                ('res_partner_id', '=', vendor.id),
            ])

    self.assertTrue(processed)


# PROBLEM: External service dependency
def test_external_api_call(self):
    result = vendor._call_external_api()  # Fails if service down

# FIX: Mock external service
@mock.patch('requests.get')
def test_external_api_call(self, mock_get):
    mock_get.return_value = mock.Mock(
        status_code=200,
        json=lambda: {'balance': 1000}
    )
    result = vendor._call_external_api()
    self.assertEqual(result, 1000)
```

---

## Related Links

- [Core/BaseModel](../Core/BaseModel.md) — Model inheritance, CRUD operations
- [Core/API](../Core/API.md) — API decorators, onchange, depends
- [Patterns/Workflow Patterns](../Patterns/Workflow Patterns.md) — State machine testing patterns
- [Tools/Debugging-Guide](Debugging-Guide.md) — Debugging test failures
- [Core/Fields](../Core/Fields.md) — Field types for test assertions
- [Core/Exceptions](../Core/Exceptions.md) — Exception types in test assertions
