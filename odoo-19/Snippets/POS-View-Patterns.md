---
uuid: pos-view-patterns-snippet-v1
type: snippet
tags: [odoo, odoo19, pos, javascript, owl, frontend, payment]
created: 2026-04-14
---

# POS View Patterns (OWL Components)

Comprehensive guide to POS-specific OWL components and JavaScript patterns in Odoo 19. All POS UI is built with **OWL (Odoo Web Library)** — the reactive component framework introduced in Odoo 15 and refined in Odoo 17+.

## Table of Contents

1. [POS Screen Architecture](#1-pos-screen-architecture)
2. [Product Screen (ProductList)](#2-product-screen-productlist)
3. [Order Screen (Orderline)](#3-order-screen-orderline)
4. [Payment Screen](#4-payment-screen)
5. [Receipt Screen](#5-receipt-screen)
6. [Numpad Component](#6-numpad-component)
7. [Partner Search (ActionPad)](#7-partner-search-actionpad)
8. [Restaurant-Specific Patterns](#8-restaurant-specific-patterns)
9. [JS Service Injection](#9-js-service-injection)
10. [Common Pitfalls](#10-common-pitfalls)

---

## 1. POS Screen Architecture

### OWL Component Structure

Every POS screen is an OWL component. The base class provides lifecycle hooks, service injection, and a reactive state system.

```javascript
// File: point_of_sale/static/src/app/screens/product_screen/product_screen.js

import { Component, onMounted, useState } from "@odoo/owl";
import { usePos } from "@Point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";

export class ProductScreen extends Component {
    // 1. Template reference (QWeb template)
    static template = "point_of_sale.ProductScreen";

    // 2. Child components (sub-components)
    static components = {
        ActionpadWidget,
        Numpad,
        Orderline,
        CategorySelector,
        Input,
        ControlButtons,
        OrderSummary,
        ProductCard,
        BarcodeVideoScanner,
    };

    // 3. Props definition (type checking)
    static props = {
        orderUuid: { type: String },
    };

    setup() {
        // 4. Service injection
        this.pos = usePos();
        this.ui = useService("ui");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.numberBuffer = useService("number_buffer");

        // 5. Reactive state (OWL useState)
        this.state = useState({
            previousSearchWord: "",
            currentOffset: 0,
            quantityByProductTmplId: {},
        });

        // 6. Lifecycle hook
        onMounted(() => {
            this.currentOrder.deselectOrderline();
            this.pos.openOpeningControl();
            this.numberBuffer.reset();
        });
    }
}
```

### Lifecycle Hooks

| Hook | When Called | Use Case |
|-------|-------------|----------|
| `setup()` | Before render | Init state, inject services, register event handlers |
| `onMounted()` | After DOM mounted | Focus elements, trigger initial RPC calls |
| `onWillRender()` | Before each render | Check if screen should switch |
| `onPatched()` | After each patch | Post-render DOM updates |
| `onWillUnmount()` | Before removal | Cleanup timers, remove event listeners |
| `onWillDestroy()` | Before destroy | Final cleanup |

### `props` vs `state`

```javascript
// props — passed IN from parent, NOT reactive internally
//  changing props from within the component has NO effect
static props = {
    orderUuid: String,           // required String
    optionalValue: { type: Number, optional: true },  // optional
    onClick: Function,          // callback prop
    partner: [Object, { value: null }],  // union type
}

// state — internal reactive state
//  Must use useState() for reactivity
setup() {
    this.state = useState({
        selectedLineId: null,
        counter: 0,
    });
    // Mutating state is reactive — triggers re-render
    this.state.counter += 1;
}
```

### Screen Switching via `env.pos.gui`

```javascript
// Navigate to PaymentScreen with a specific order
this.pos.gui.show_screen("PaymentScreen", { orderUuid: order.uuid });

// Navigate back to ProductScreen
this.pos.gui.show_screen("ProductScreen");

// Get current screen
const currentScreen = this.pos.gui.get_current_screen();
// Returns: "ProductScreen", "PaymentScreen", "ReceiptScreen", etc.

// Get router state (for URL sync in embedded POS)
const currentRoute = this.pos.router.state.current;
// Returns: "ProductScreen", "PaymentScreen", etc.
```

### Environment (`env`) and `usePos()`

`usePos()` is a custom hook that returns the POS store (the global `pos` singleton):

```javascript
// usePos is equivalent to:
const pos = useService("pos");

// Access the current order
const order = this.pos.getOrder();

// Access all orders
const orders = this.pos.orders;

// Access models
const products = this.pos.models["product.product"];
const partners = this.pos.models["res.partner"];
```

---

## 2. Product Screen (ProductList)

The ProductScreen displays products in a grid and handles adding them to the order. It is the default POS landing screen.

### Key Component: ProductScreen

```javascript
// File: point_of_sale/static/src/app/screens/product_screen/product_screen.js
// ~250 lines total

export class ProductScreen extends Component {
    static template = "point_of_sale.ProductScreen";
    static components = { ActionpadWidget, Numpad, Orderline, ... };

    setup() {
        this.pos = usePos();
        this.numberBuffer = useService("number_buffer");
        this.state = useState({
            currentOffset: 0,
            quantityByProductTmplId: {},
        });
        this.debouncedSearch = debounce(this._fetchProducts, 300);

        onMounted(() => {
            this.numberBuffer.reset();
        });

        onWillRender(() => {
            // Auto-switch to new order if current is being paid elsewhere
            if (this.currentOrder?.state !== "draft" && !this.isValidatingOrder) {
                this.pos.addNewOrder();
            }
        });
    }

    // Search products with pagination
    async _fetchProducts(searchWord) {
        // RPC to server to search products
        const products = await this.pos.data.searchRead("product.product", [...]);
        this.state.currentOffset += products.length;
    }
}
```

### Product Grid Rendering

Products are rendered via the `ProductCard` component inside a CSS grid:

```xml
<!-- Corresponding QWeb template (simplified) -->
< t t-name="point_of_sale.ProductScreen" >
    <div class="product-screen">
        <!-- Left: Product grid -->
        <div class="product-list">
            <div class="product-list-container">
                <t t-foreach="products" t-as="product">
                    <ProductCard product="product" />
                </t>
            </div>
        </div>
        <!-- Right: Order summary + Numpad -->
        <div class="order-screen">
            <OrderSummary />
            <Numpad />
        </div>
    </div>
</t>
```

### Category Navigation

The `CategorySelector` component provides horizontal scrolling category tabs:

```javascript
// File: point_of_sale/static/src/app/components/category_selector/category_selector.js
export class CategorySelector extends Component {
    static template = "point_of_sale.CategorySelector";

    get categories() {
        return this.pos.models["pos.category"].getAll();
    }

    selectCategory(categoryId) {
        this.pos.searchWord = "";  // Clear search on category change
        this.pos.selectedCategoryId = categoryId;
        // Products will be filtered by this.pos.selectedCategoryId
    }
}
```

### Product Card Component

```javascript
// File: point_of_sale/static/src/app/components/product_card/product_card.js
export class ProductCard extends Component {
    static template = "point_of_sale.ProductCard";
    static props = {
        product: Object,
    };

    // Clicking a product adds it to the order
    async addToOrder() {
        const product = this.props.product;
        const quantity = this.numberBuffer.get() || 1;
        const options = {
            draft: true,
            quantity: quantity,
        };
        await this.pos.getOrder().add_product(product, options);
        this.numberBuffer.reset();
    }
}
```

### Product Search Pattern

```javascript
// Search is triggered via the numberBuffer (numpad input) or search bar
// Debounced to avoid excessive RPC calls
this.debouncedSearch = debounce(async (searchWord) => {
    if (searchWord.length < 3) {
        return;  // Minimum 3 characters
    }
    const domain = [
        "|",
        ["name", "ilike", searchWord],
        ["default_code", "ilike", searchWord],
    ];
    const products = await this.pos.data.searchRead(
        "product.product",
        domain,
        { limit: 100 }
    );
}, 300);
```

---

## 3. Order Screen (Orderline)

The Orderline component renders individual items in the current order. It is used both in the order summary (ProductScreen) and in the ReceiptScreen.

### Orderline Component

```javascript
// File: point_of_sale/static/src/app/components/orderline/orderline.js

export class Orderline extends Component {
    static components = { TagsList };
    static template = "point_of_sale.Orderline";

    static props = {
        line: Object,                    // The pos.order.line record
        class: { type: Object, optional: true },
        showTaxGroupLabels: { type: Boolean, optional: true },
        showTaxGroup: { type: Boolean, optional: true },
        mode: { type: String, optional: true },  // "display" | "receipt"
        basic_receipt: { type: Boolean, optional: true },
        onClick: { type: Function, optional: true },
        onLongPress: { type: Function, optional: true },
    };

    setup() {
        this.root = useRef("root");

        if (this.props.mode === "display") {
            // Click: select line; Long-press (500ms): open edit popup
            useTimedPress(this.root, [
                {
                    type: "release",
                    maxDelay: 500,
                    callback: (event, duration) => {
                        this.props.onClick(event, duration);
                    },
                },
                {
                    type: "hold",
                    delay: 500,
                    callback: (event, duration) => {
                        this.props.onLongPress(event, duration);
                    },
                },
            ]);
        }
    }

    // Reactive getters
    get line() {
        return this.props.line;
    }

    get lineContainerClasses() {
        return {
            selected: this.line.isSelected() && this.props.mode === "display",
            ...this.line.getDisplayClasses(),
        };
    }

    formatCurrency(amount) {
        return formatCurrency(amount, this.pos.currency.id);
    }
}
```

### Quantity Input and Editing

```xml
<!-- Corresponding QWeb template -->
<div t-name="point_of_sale.Orderline" class="orderline"
     t-att-class="props.lineContainerClasses"
     t-on-click="props.onClick"
     t-ref="root">
    <!-- Product info -->
    <div class="product-info">
        <span class="product-name"><t t-esc="line.product_id.display_name"/></span>
        <!-- Tax labels as tags -->
        <TagsList tags="line.taxGroupLabels" />
    </div>
    <!-- Quantity display (editable in display mode) -->
    <div class="qty">
        <span t-if="props.mode !== 'receipt'"
              t-attf-class="qty-tag {{ line.getFullQty() !== line.qty ? 'tagged' : '' }}">
            <t t-esc="line.getFullQty()" />
        </span>
        <span t-if="props.mode === 'receipt'" class="qty-tag">
            <t t-esc="line.getFullQty()" />
        </span>
    </div>
    <!-- Price and total -->
    <div class="price">
        <span class="unit-price"><t t-esc="line.unit" /></span>
        <span class="subtotal"><t t-esc="line.getDisplayPrice()" /></span>
    </div>
</div>
```

### Discount Application Pattern

Discounts are applied via the numpad. The flow:

```javascript
// In ProductScreen, when numpad sends a discount command:
applyDiscount(discountPc) {
    const line = this.currentOrder.getSelectedOrderline();
    if (!line) return;

    // Set discount percentage on the selected line
    line.set_discount(discountPc);

    // Trigger recalculation of line price
    // (done automatically via reactive computed in pos_order_line.js)
}
```

### Tax Computation Display

Taxes are computed on the line and displayed in the receipt:

```javascript
// In Orderline template (receipt mode):
// Each tax group is shown with its amount
<t t-foreach="line.taxGroupAfterFiscalPosition" t-as="tax">
    <div class="tax-line">
        <span><t t-esc="tax.name"/></span>
        <span><t t-esc="tax.amount"/></span>
    </div>
</t>
```

---

## 4. Payment Screen

The PaymentScreen handles payment method selection, payment line management, and order validation.

### PaymentScreen Component

```javascript
// File: point_of_sale/static/src/app/screens/payment_screen/payment_screen.js

export class PaymentScreen extends Component {
    static template = "point_of_sale.PaymentScreen";
    static components = {
        Numpad,
        PaymentScreenPaymentLines,
        PaymentScreenStatus,
        PriceFormatter,
    };
    static props = {
        orderUuid: String,
    };

    setup() {
        this.pos = usePos();
        this.ui = useService("ui");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.hardwareProxy = useService("hardware_proxy");
        this.printer = useService("printer");
        this.numberBuffer = useService("number_buffer");
        this.numberBuffer.use(this._getNumberBufferConfig);

        // Services for payment terminal integration
        this.payment_interface = null;
        this.error = false;

        // Async locking prevents double-submit
        this.validateOrder = useAsyncLockedMethod(this.validateOrder);
        onMounted(this.onMounted);
    }

    onMounted() {
        const order = this.pos.getOrder();
        // Remove payments from deleted payment methods
        for (const payment of order.payment_ids) {
            if (!this.pos.config.payment_method_ids.map(m => m.id).includes(
                payment.payment_method_id.id
            )) {
                payment.delete({ backend: true });
            }
        }
        // Auto-select payment method if only one exists
        if (this.payment_methods_from_config.length == 1 && this.paymentLines.length == 0) {
            this.addNewPaymentLine(this.payment_methods_from_config[0]);
        }
    }
}
```

### Payment Method List

```javascript
// Get payment methods from config, sorted by sequence
get payment_methods_from_config() {
    return this.pos.config.payment_method_ids
        .slice()
        .sort((a, b) => a.sequence - b.sequence);
}

// Add a new payment line for a method
addNewPaymentLine(paymentMethod) {
    const line = this.currentOrder.add_paymentline(paymentMethod);
    this.numberBuffer.reset();
    return line;
}
```

### Payment Status Computations

```javascript
// Computed properties for the payment status banner
get currentOrder() {
    return this.pos.getOrder();
}

get paymentLines() {
    return this.currentOrder.payment_ids;
}

get due() {
    return this.currentOrder.get_total_with_tax() - this.currentOrder.get_paid_total();
}

get change() {
    return Math.max(0, this.currentOrder.get_paid_total() - this.currentOrder.get_total_with_tax());
}

get is_paid() {
    return this.due <= 0.01;  // Allow 1 cent rounding tolerance
}
```

### Partial Payment Pattern

```javascript
// Partial payment: customer pays less than the due amount
// The order stays open until fully paid
async addNewPaymentLine(paymentMethod) {
    const line = this.currentOrder.add_paymentline({
        payment_method_id: paymentMethod.id,
        amount: this.numberBuffer.getFloat() || 0,
    });
    // If this is partial, due remains > 0
    // "validate" button shows only when due <= 0
    return line;
}

// Validate button is only enabled when fully paid
get is_paid() {
    return this.due <= 0.01;
}
```

### Split Payment Pattern

Split payments use multiple payment lines on the same order:

```javascript
// Multiple payment lines — each for a different method
// Example: 50% cash + 50% card
this.currentOrder.add_paymentline({ payment_method_id: cashMethod.id });
this.currentOrder.add_paymentline({ payment_method_id: cardMethod.id });

// Total paid = sum of all payment line amounts
get total_paid() {
    return this.paymentLines.reduce((sum, line) => sum + line.amount, 0);
}
```

---

## 5. Receipt Screen

The ReceiptScreen displays the order receipt after successful payment, with QR code for portal validation.

### OrderReceipt Component

```javascript
// File: point_of_sale/static/src/app/screens/receipt_screen/receipt/order_receipt.js

export class OrderReceipt extends Component {
    static template = "point_of_sale.OrderReceipt";
    static components = { Orderline, OrderDisplay, ReceiptHeader };

    static props = {
        order: Object,
        basic_receipt: { type: Boolean, optional: true },
    };

    // Receipt header data
    get header() {
        return {
            company: this.order.company,
            cashier: _t("Served by %s", this.order.getCashierName()),
            header: this.order.config.receipt_header,
        };
    }

    // QR code for online ticket validation
    get qrCode() {
        const baseUrl = this.order.config._base_url;
        const url = `${baseUrl}/pos/ticket/validate?access_token=${this.order.access_token}`;
        return generateQRCodeDataUrl(url);
    }

    // Filter out change payments from receipt
    get paymentLines() {
        return this.order.payment_ids.filter((p) => !p.is_change);
    }

    formatCurrency(amount) {
        return formatCurrency(amount, this.order.currency.id);
    }
}
```

### Receipt Header

```javascript
// File: point_of_sale/static/src/app/screens/receipt_screen/receipt/receipt_header/receipt_header.js

export class ReceiptHeader extends Component {
    static template = "point_of_sale.ReceiptHeader";

    static props = {
        data: Object,  // { company, cashier, header }
    };

    get vatText() {
        const country = this.props.data.company.country_id;
        if (country?.vat_label) {
            return _t("%(vatLabel)s: %(vatId)s", {
                vatLabel: country.vat_label,
                vatId: country.vat,
            });
        }
    }
}
```

### Receipt Template (QWeb)

```xml
<t t-name="point_of_sale.OrderReceipt">
    <receipt>
        <receipt-header>
            <!-- Company logo, name, address -->
            <img t-att-src="company.logo" class="pos-receipt-logo" />
            <div class="pos-receipt-contact">
                <t t-esc="company.name" />
                <t t-esc="company.partner_id.contact_address" />
            </div>
        </receipt-header>

        <!-- QR Code for online validation -->
        <img t-if="qrCode" t-att-src="qrCode" class="pos-receipt-qrcode" />

        <!-- Order lines -->
        <t t-foreach="order.lines" t-as="line">
            <Orderline line="line"
                       mode="'receipt'"
                       basic_receipt="props.basic_receipt" />
        </t>

        <!-- Subtotal, taxes, total -->
        <div class="total">
            <t t-foreach="order tax">
                <div><t t-esc="tax.name" />: <t t-esc="tax.amount" /></div>
            </t>
            <div class="emphasis"><t t-esc="order.total_with_tax" /></div>
        </div>

        <!-- Payment lines -->
        <div class="payment-methods">
            <t t-foreach="paymentLines" t-as="payment">
                <div>
                    <t t-esc="payment.payment_method_id.name" />:
                    <t t-esc="formatCurrency(payment.amount)" />
                </div>
            </t>
        </div>

        <!-- Barcode -->
        <barcode><t t-esc="order.name" /></barcode>
    </receipt>
</t>
```

### Print Action

```javascript
// Triggering receipt printing from ReceiptScreen
async printReceipt() {
    const result = await this.printer.printFromScreen(
        "point_of_sale.OrderReceipt",
        { order: this.order }
    );
    if (resultsuccessful) {
        // Receipt printed
    }
}
```

---

## 6. Numpad Component

The Numpad is the numeric input widget used for quantity entry, price input, and payment amount entry.

### Numpad Component

```javascript
// File: point_of_sale/static/src/app/components/numpad/numpad.js

export const DECIMAL = {
    get value() {
        return localization.decimalPoint;  // Locale-aware "." or ","
    },
    class: "o_colorlist_item_numpad_color_6",
};

export const BACKSPACE = {
    value: "Backspace",
    text: "\u232B",  // Backspace symbol
    class: "o_colorlist_item_numpad_color_1",
};

export const ZERO = { value: "0" };
export const SWITCHSIGN = { value: "-", text: "+/-" };
export const DEFAULT_LAST_ROW = [SWITCHSIGN, ZERO, DECIMAL];

export function getButtons(lastRow, rightColumn) {
    // Returns button grid: 1-2-3 [rightCol0], 4-5-6 [rightCol1], 7-8-9 [rightCol2], lastRow [rightCol3]
    return [
        { value: "1" }, { value: "2" }, { value: "3" }, ...(rightColumn ? [rightColumn[0]] : []),
        { value: "4" }, { value: "5" }, { value: "6" }, ...(rightColumn ? [rightColumn[1]] : []),
        { value: "7" }, { value: "8" }, { value: "9" }, ...(rightColumn ? [rightColumn[2]] : []),
        ...lastRow, ...(rightColumn ? [rightColumn[3]] : []),
    ];
}

export class Numpad extends Component {
    static template = "point_of_sale.Numpad";
    static props = {
        class: { type: String, optional: true },
        onClick: { type: Function, optional: true },
        buttons: { type: Array, optional: true },
    };

    setup() {
        // If no custom onClick provided, use the numberBuffer service
        if (!this.props.onClick) {
            this.numberBuffer = useService("number_buffer");
            this.onClick = (buttonValue) => this.numberBuffer.sendKey(buttonValue);
        } else {
            this.onClick = this.props.onClick;
        }
    }

    get buttons() {
        return this.props.buttons || getButtons([DECIMAL, ZERO, BACKSPACE]);
    }
}
```

### Enhanced Numpad (POS Payment)

```javascript
// POS payment screen uses an enhanced numpad with +10, +20, +50 quick-add buttons
export function enhancedButtons() {
    return getButtons(DEFAULT_LAST_ROW, [
        { value: "+10" },
        { value: "+20" },
        { value: "+50" },
        BACKSPACE,
    ]);
}

// In PaymentScreen:
this.numberBuffer.use((key) => {
    if (key === "+10") {
        // Add 10 to current amount
        this.currentAmount += 10;
    } else if (key === "+20") {
        this.currentAmount += 20;
    } else if (key === "+50") {
        this.currentAmount += 50;
    } else {
        this.numberBuffer.sendKey(key);
    }
});
```

### Button Event Handling

```javascript
// In QWeb template:
/*
<div class="numpad">
    <t t-foreach="props.buttons" t-as="btn">
        <button t-att-class="btn.class or ''"
                t-on-click="() => this.onClick(btn.value)">
            <t t-esc="btn.text || btn.value" />
        </button>
    </t>
</div>
*/
```

---

## 7. Partner Search (ActionPad)

The ActionPad (also called ActionBar in some contexts) provides quick customer selection and order actions.

### ActionpadWidget Component

```javascript
// File: point_of_sale/static/src/app/screens/product_screen/action_pad/action_pad.js

export class ActionpadWidget extends Component {
    static template = "point_of_sale.ActionpadWidget";
    static components = { SelectPartnerButton, BackButton };

    static props = {
        partner: { type: [Object, { value: null }], optional: true },
        onClickMore: { type: Function, optional: true },
        actionName: String,
        actionToTrigger: Function,
        showActionButton: { type: Boolean, optional: true },
        fastValidate: { type: Function, optional: true },
    };

    setup() {
        this.pos = usePos();
        this.ui = useService("ui");
    }

    get currentOrder() {
        return this.pos.getOrder();
    }

    get showFastPaymentMethods() {
        return (
            this.pos.config.use_fast_payment &&
            this.pos.config.fast_payment_method_ids?.length &&
            this.pos.router.state.current === "ProductScreen"
        );
    }
}
```

### Quick Partner Selection

```javascript
// In ProductScreen, selecting a customer via ActionPad
async selectPartner() {
    // Open partner selection popup
    const { confirmed, payload } = await makeAwaitable(
        this.dialog,
        SelectPartnerPopup,
        { title: "Select Customer" }
    );

    if (confirmed && payload) {
        this.currentOrder.partner_id = payload;
        // Trigger price list update, fiscal position update
        this.currentOrder.updatePricelist();
    }
}

// Create new partner inline
async createPartner(partnerData) {
    const partner = await this.pos.data.create("res.partner", {
        name: partnerData.name,
        phone: partnerData.phone,
        email: partnerData.email,
    });
    this.currentOrder.partner_id = partner;
}
```

### Partner Line Component

```javascript
// File: point_of_sale/static/src/app/screens/partner_list/partner_line/partner_line.js

export class PartnerLine extends Component {
    static template = "point_of_sale.PartnerLine";

    static props = {
        partner: Object,
        onClick: Function,
    };

    get initials() {
        const name = this.props.partner.name || "";
        return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
    }
}
```

---

## 8. Restaurant-Specific Patterns

### Floor Plan Rendering (FloorScreen)

```javascript
// File: pos_restaurant/static/src/app/screens/floor_screen/floor_screen.js
// Extends the base ProductScreen for restaurant mode

export class FloorScreen extends Component {
    static template = "pos_restaurant.FloorScreen";
    static components = { Floor, Table };

    setup() {
        this.pos = usePos();
        // Tables are positioned with x/y coordinates
    }

    get floors() {
        // Group tables by floor
        const floors = {};
        for (const table of this.pos.tables) {
            if (!floors[table.floor_id.id]) {
                floors[table.floor_id.id] = {
                    id: table.floor_id.id,
                    name: table.floor_id.name,
                    tables: [],
                };
            }
            floors[table.floor_id.id].tables.push(table);
        }
        return Object.values(floors);
    }

    selectTable(table) {
        // Switch to ProductScreen with table context
        const order = this.pos.getOrder();
        order.table_id = table;
        this.pos.gui.show_screen("ProductScreen");
    }
}
```

### Table Selection Pattern

```javascript
// pos_restaurant extends pos_order to add table_id
patch(PosOrder.prototype, {
    _initOrderUUID(orderUuid) {
        const order = super._initOrderUUID(...arguments);
        order.table_id = null;  // Set when table is selected
        order.customer_count = 0;
        return order;
    },
});
```

### Split Bill by Seat (SplitBillScreen)

```javascript
// File: pos_restaurant/static/src/app/screens/split_bill_screen/split_bill_screen.js

export class SplitBillScreen extends Component {
    static template = "pos_restaurant.SplitBillScreen";
    static components = { Orderline, OrderDisplay, PriceFormatter };

    setup() {
        this.pos = usePos();
        this.qtyTracker = useState({});  // Track quantity per line uuid
        this.priceTracker = useState({});  // Track price per line uuid
        this.isTransferred = false;

        onWillDestroy(() => {
            // Reset split state on all lines when leaving screen
            this.pos.models["pos.order.line"].map((l) => (l.uiState.splitQty = false));
        });
    }

    // Clicking a line cycles through: 0 -> 1 -> maxQty -> 0
    onClickLine(line) {
        const lines = line.getAllLinesInCombo();  // Handle combo children
        for (const l of lines) {
            const uuid = l.uuid;
            const maxQty = l.getQuantity();
            const currentQty = this.qtyTracker[uuid] || 0;
            // Cycle: 0 -> 1 -> ... -> maxQty -> 0
            const nextQty = currentQty === maxQty ? 0 : currentQty + 1;
            this.qtyTracker[uuid] = Math.min(nextQty, maxQty);
            // Price is proportional to qty
            this.priceTracker[uuid] = (l.prices.total_included / l.qty) * this.qtyTracker[uuid];
        }
    }

    // Create new order from selected lines
    async transferLines() {
        const newOrder = this.pos.addNewOrder();
        for (const [uuid, qty] of Object.entries(this.qtyTracker)) {
            if (qty > 0) {
                const line = this.pos.models["pos.order.line"].find(l => l.uuid === uuid);
                await newOrder.add_product(line.product_id, { quantity: qty });
            }
        }
        this.isTransferred = true;
    }
}
```

### Course Sequencing (OrderCourse)

```javascript
// File: pos_restaurant/static/src/app/models/restaurant_order_course.js
// Lines can be sent in courses

export class RestaurantOrderCourse extends Component {
    static template = "pos_restaurant.OrderCourse";

    // Send only lines in this course to kitchen
    async sendCourse(courseId) {
        const order = this.pos.getOrder();
        for (const line of order.lines) {
            if (line.course_id?.id === courseId) {
                line.is_sent = true;
                await this.pos.data.write("pos.order.line", line.id, {
                    is_sent: true,
                    line_sent_at: fields.Datetime.now(),
                });
            }
        }
    }
}
```

### Restaurant Numpad Override

```javascript
// File: pos_restaurant/static/src/app/components/numpad_dropdown/numpad_dropdown.js
// Restaurant uses a dropdown numpad for course selection

export class NumpadDropdown extends Component {
    static template = "pos_restaurant.NumpadDropdown";

    // Opens course selector after entering quantity
    onQuantityConfirmed(quantity) {
        // Show course selection dropdown
        this.showCourseDropdown = true;
    }
}
```

### Tip Screen Pattern

```javascript
// File: pos_restaurant/static/src/app/screens/tip_screen/tip_screen.js
// Post-payment tip collection

export class TipScreen extends Component {
    static template = "pos_restaurant.TipScreen";

    // Preset tip percentages: 0%, 5%, 10%, custom
    async selectTip(amount) {
        const order = this.pos.getOrder();
        order.tip_amount = amount;
        await order.save();  // Persist tip to order
    }
}
```

---

## 9. JS Service Injection

The POS uses a service-oriented architecture. Components inject services via `useService()`.

### Available Services

| Service Name | Injected Via | Purpose |
|-------------|-------------|---------|
| `pos` | `usePos()` | Global POS store — models, orders, products, config |
| `dialog` | `useService("dialog")` | Open modal popups |
| `notification` | `useService("notification")` | Show toast notifications |
| `ui` | `useService("ui")` | Odoo UI state (block, unblock, isMobile) |
| `number_buffer` | `useService("number_buffer")` | Numpad input management |
| `hardware_proxy` | `useService("hardware_proxy")` | Barcode scanner, scale, printer |
| `printer` | `useService("printer")` | Receipt printing |
| `account_move` | `useService("account_move")` | Invoice generation |
| `pos_bus` | `useService("pos_bus")` | Real-time POS bus for multi-POS sync |
| `router` | `useService("router")` | Screen routing |
| `orm` | `useService("orm")` | ORM-style read/write operations |

### Service Usage Examples

```javascript
// Dialog service — modal popup
const { confirmed, payload } = await makeAwaitable(
    this.dialog,
    TextInputPopup,
    {
        title: "Customer Name",
        placeholder: "Enter name",
    }
);
if (confirmed) {
    await this.pos.data.create("res.partner", { name: payload });
}

// Notification service — toast
this.notification.add("Order saved successfully", {
    type: "info",    // "info" | "warning" | "danger" | "success"
    sticky: false,   // Auto-dismiss vs sticky
});

// ORM service — search
const partners = await this.pos.data.searchRead(
    "res.partner",
    [["customer_rank", ">", 0]],
    ["id", "name", "email", "phone"],
    { limit: 50 }
);

// ORM create
const newPartner = await this.pos.data.create("res.partner", {
    name: "John Doe",
    customer_rank: 1,
});

// ORM write
await this.pos.data.write("res.partner", partnerId, {
    phone: "+123456789",
});

// ORM unlink
await this.pos.data.unlink("res.partner", partnerId);

// Pos Bus — real-time sync between POS instances
this.pos.bus.send("pos.order.changed", {
    order: serializedOrder,
    lines: serializedLines,
});
// Other POS instances listening on this channel receive the update
```

### RPC via `pos.data.call`

```javascript
// Direct RPC call to Odoo model methods
const result = await this.pos.data.call(
    "pos.payment.method",
    "send_dpopay_request",
    [[paymentMethodId]],
    { data: payload, action: "start-transaction" }
);

// With timeout
const result = await this.pos.data.call(
    "pos.order",
    "action_pos_order_paid",
    [orderId],
    {},
    { shadow: false, timeout: 10000 }
);
```

### Registering Custom Payment Methods

```javascript
// File: pos_dpopay/static/src/app/utils/payment/payment_dpopay.js
// Using the payment method registry

import { register_payment_method } from "@point_of_sale/app/services/pos_store";

export class PaymentDPOPay extends PaymentInterface {
    // ... implementation
}

register_payment_method("dpopay", PaymentDPOPay);
```

### POS Store Pattern

```javascript
// pos_store.js registers all services and models at startup
export const posStore = {
    name: "pos",

    dependencies: ["orm", "ui", "notification", "dialog"],

    start(env, { orm, ui, notification, dialog }) {
        const store = {
            models: {},
            orders: [],
            config: {},
            // ... rest of the store
        };
        return store;
    },
};

registry.category("services").add("pos", posStore);
```

---

## 10. Common Pitfalls

### Pitfall 1: Direct State Mutation (Not Reactive)

OWL components use a reactive state system. Direct assignment to state properties does NOT trigger re-renders unless you use `useState()`.

```javascript
// WRONG — this.state is reactive, but direct reassignment is not
this.state = { counter: 0 };  // This breaks reactivity

// WRONG — this.name won't trigger re-render
this.state = { name: "John" };
this.state.name = "Jane";  // Direct mutation of useState object is fine, but:
this.state = { name: "Jane" };  // This breaks reactivity

// CORRECT — mutate the existing state object
this.state = useState({});   // Initialize with useState
this.state.counter = 5;       // Mutate directly — triggers re-render
this.state.items.push(item);  // Mutate arrays/objects — triggers re-render
```

### Pitfall 2: Missing `mount()` in Custom Components

OWL components must be mounted to the DOM. Failing to call `mount()` leaves the component invisible.

```javascript
// WRONG — component created but never mounted
const popup = new TextInputPopup();
await popup.mount(document.body);  // mount() is required

// CORRECT — after mounting, the component renders
await popup.mount(document.body);
popup.state.value = "initial";
// Now visible in the DOM
```

### Pitfall 3: `props` Are Not Reactive Within the Component

Props are passed from parent to child. Changing a prop from within the child component has no effect.

```javascript
// WRONG
setup() {
    this.props.title = "New Title";  // Has no effect on rendering
}

// CORRECT — use state for internal values
setup() {
    this.state = useState({ title: this.props.title });
    this.state.title = "New Title";  // This triggers re-render
}
```

### Pitfall 4: Memory Leaks from Timers and Event Listeners

Always clean up in `onWillUnmount()` or `onWillDestroy()`.

```javascript
setup() {
    this.timer = setInterval(() => this.pollStatus(), 3000);

    onWillUnmount(() => {
        clearInterval(this.timer);      // Clear timers
        this.bus.off("update", this.handler);  // Remove event listeners
    });
}
```

### Pitfall 5: Async Race Conditions

When multiple async operations can happen in sequence, use locks or async-locked methods.

```javascript
// WRONG — double-click can call validateOrder twice
onClickValidate() {
    this.validateOrder();  // No guard against re-entry
}

// CORRECT — useAsyncLockedMethod prevents concurrent execution
setup() {
    this.validateOrder = useAsyncLockedMethod(this.validateOrder);
}

async validateOrder() {
    // This method can only run one instance at a time
    await this.pos.data.call("pos.order", "action_pos_order_paid", [orderId]);
}
```

### Pitfall 6: Using `onMounted` for Reactive Computations

`onMounted` runs once after the first render. If you need reactive behavior, use `useEffect` or computed getters.

```javascript
// WRONG
onMounted(() => {
    this.total = this.currentOrder.get_total_with_tax();  // Stale after order changes
});

// CORRECT — computed getter recalculates on every render
get total() {
    return this.currentOrder.get_total_with_tax();  // Always current
}

// Or use useEffect for side effects
useEffect(() => {
    this.fetchOrderData();
}, () => [this.props.orderId]);
```

### Pitfall 7: Forgetting `ensure_one()` on Recordsets

When working with a single record from a model, use `ensure_one()` to guard against empty or multi-record sets.

```javascript
// In POS models (pos_order.js), methods often operate on single orders
const order = this.pos.getOrder();
order.ensure_one();  // Throws if no order or multiple orders

// In payment terminal code:
const paymentLine = order.getSelectedPaymentline();
if (!paymentLine) return false;
```

### Pitfall 8: Not Using `makeAwaitable` for Dialogs

The POS dialog service returns a Promise when you call it. Use `makeAwaitable` to cleanly await the result.

```javascript
// WRONG — dialog returns a promise but we're not awaiting it
this.dialog.add(ConfirmDialog, { title: "Confirm" });
// Code continues immediately without waiting for user response

// CORRECT — use makeAwaitable to await the user's choice
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

const { confirmed } = await makeAwaitable(
    this.dialog,
    ConfirmDialog,
    { title: "Delete order?", body: "This cannot be undone." }
);
if (confirmed) {
    order.destroy();
}
```

### Pitfall 9: Mixing OWL Component State with POS Model State

OWL component state (`useState`) and POS model state (updates to `pos.models`) are separate reactive systems. Changes to POS models trigger updates in the POS UI, but OWL component state is independent.

```javascript
// POS model updates trigger POS UI updates automatically
this.pos.getOrder().partner_id = partner;  // Order UI updates

// But this doesn't trigger an OWL component re-render
// unless the component specifically reads from the order in a getter
setup() {
    // This getter makes the component reactive to order.partner changes:
    get currentPartner() {
        return this.pos.getOrder().partner_id;
    }
}
```
