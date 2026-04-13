# Product Availability Notifications

## Overview
- **Name**: Product Availability Notifications
- **Category**: Website/Website
- **Depends**: `website_sale_comparison`, `website_sale_wishlist`
- **Summary**: Bridge module enabling product comparison from the wishlist
- **Auto-install**: True

## Overview
This is a bridge/extension module that combines `website_sale_comparison` and `website_sale_wishlist`. It allows users to compare products directly from their wishlist. No additional Python models or controllers — it adds frontend assets that add a "Compare" action to wishlist items.

## Key Features
- Renders an "Add to Compare" button/checkbox in the wishlist page
- Allows quick product comparison without returning to the shop
- Combines the comparison and wishlist user experiences

## Static Assets
- `website_sale_comparison_wishlist/static/src/**/*` - Frontend JS/SCSS for wishlist comparison UI

## Views
- `views/templates.xml` - QWeb templates for wishlist comparison elements

## Related
- [Modules/website_sale_comparison](Modules/website_sale_comparison.md) - Product comparison base
- [Modules/website_sale_wishlist](Modules/website_sale_wishlist.md) - Wishlist base
