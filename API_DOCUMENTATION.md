# QR Menu API Documentation

This document describes the full HTTP API exposed by `qrmenu-api`, including endpoint purpose, authentication rules, request parameters, and response behavior.

- Base URL (local default): `http://localhost:3005`
- API version prefix: `/api/v1`
- Content type: `application/json` unless stated otherwise

## Table of Contents

- [Authentication Model](#authentication-model)
- [Error Format](#error-format)
- [Business Auth](#business-auth)
- [Client Auth](#client-auth)
- [Categories](#categories)
- [Products](#products)
- [Client Orders](#client-orders)
- [Business Orders](#business-orders)
- [Business Analytics](#business-analytics)
- [Business QR](#business-qr)
- [Public Menu Page](#public-menu-page)
- [Background Cleanup Jobs](#background-cleanup-jobs)
- [Environment Variables](#environment-variables)

## Authentication Model

Protected endpoints require an access token from login/register.

Recommended:

- Header: `Authorization: Bearer <access_token>`

Also supported by middleware:

- JSON body key: `access_token`

Refresh endpoints require `refresh_token` in request JSON.

## Error Format

Typical error body:

```json
{"error": "Human readable message"}
```

Common status codes:

- `400` invalid/missing fields
- `401` missing/invalid/expired token
- `403` user type has no permission
- `404` resource not found
- `409` uniqueness conflict (e.g., email already used)
- `500` database or server configuration error

---

## Business Auth

Base path: `/api/v1/business/auth`

### `POST /register`

Create a business account.

Request JSON:

```json
{
  "name": "Coffee House",
  "email": "owner@example.com",
  "password": "Password123!"
}
```

Success `201`:

```json
{
  "business": {
    "_id": "...",
    "name": "Coffee House",
    "email": "owner@example.com"
  },
  "access_token": "...",
  "refresh_token": "..."
}
```

### `POST /login`

Login with business credentials.

Request JSON:

```json
{
  "email": "owner@example.com",
  "password": "Password123!"
}
```

Success `200` returns same shape as register.

### `POST /refresh`

Generate a new access token using refresh token.

Request JSON:

```json
{"refresh_token": "..."}
```

Success `200`:

```json
{"access_token": "..."}
```

### `PUT /edit`

Update business profile fields.

Auth: business access token required.

Allowed JSON fields (any subset):

- `name`
- `email`
- `password`

Success `200`:

```json
{"business": {"_id": "...", "name": "...", "email": "..."}}
```

### `DELETE /delete`

Delete business account.

Auth: business access token required.

Behavior:

- Cascades cleanup to child entities:
  - business categories
  - products under those categories
  - remaining business products
  - business orders

Success `200`:

```json
{"message": "Business deleted"}
```

---

## Client Auth

Base path: `/api/v1/client/auth`

### `POST /register`

Create a client account.

Request JSON:

```json
{
  "first_name": "Ali",
  "last_name": "Veli",
  "phone_number": "5551234567",
  "email": "ali@example.com",
  "password": "Password123!"
}
```

Success `201`:

```json
{
  "user": {
    "_id": "...",
    "first_name": "Ali",
    "last_name": "Veli",
    "phone_number": "5551234567",
    "email": "ali@example.com"
  },
  "access_token": "...",
  "refresh_token": "..."
}
```

### `POST /login`

Login as client.

Request JSON:

```json
{"email": "ali@example.com", "password": "Password123!"}
```

Success `200` returns same shape as register.

### `POST /refresh`

Refresh client access token.

Request JSON:

```json
{"refresh_token": "..."}
```

Success `200`:

```json
{"access_token": "..."}
```

### `PUT /edit`

Update client profile.

Auth: client access token required.

Allowed JSON fields (any subset):

- `first_name`
- `last_name`
- `phone_number`
- `email`
- `password`

### `DELETE /delete`

Delete client account.

Auth: client access token required.

Success `200`:

```json
{"message": "User deleted"}
```

---

## Categories

Base path: `/api/v1/business/categories`

### `POST /`

Create category for signed-in business.

Auth: business access token required.

Request JSON:

```json
{"name": "Hot Drinks"}
```

Success `201`:

```json
{
  "category": {
    "_id": "...",
    "business_id": "...",
    "name": "Hot Drinks",
    "created_at": "..."
  }
}
```

### `GET /`

List categories.

Auth:

- Optional. If request contains a valid business token, results are filtered to that business.
- Without token, returns all categories.

Success `200`:

```json
{"categories": [{"_id": "...", "business_id": "...", "name": "...", "created_at": "..."}]}
```

### `GET /<category_id>`

Get one category by id.

Auth:

- Optional. If authenticated as business, category must belong to that business.

### `PUT /<category_id>`

Update category.

Auth: business access token required.

Request JSON (supported):

```json
{"name": "Updated name"}
```

### `DELETE /<category_id>`

Delete category.

Auth: business access token required.

Behavior:

- Cascades to products in this category and their image files.

Success `200`:

```json
{"message": "Category deleted"}
```

---

## Products

Base path: `/api/v1/business/products`

### `POST /`

Create product.

Auth: business access token required.

Supports:

- `application/json`
- `multipart/form-data` (for image upload)

Required fields:

- `name`
- `category_id`
- `price`

Optional fields:

- `description`
- `is_active` (default `true`)
- `image` (multipart file)

Example JSON request:

```json
{
  "name": "Latte",
  "description": "Double shot",
  "category_id": "...",
  "price": 120,
  "is_active": true
}
```

Success `201`:

```json
{"product": {"_id": "...", "business_id": "...", "category_id": "...", "name": "...", "description": "...", "price": 120.0, "image_path": "http://.../static/images/...", "is_active": true, "created_at": "..."}}
```

### `GET /`

List products with optional URL filters.

Query parameters (all optional):

- `category_id` (ObjectId)
- `business_id` (ObjectId)
- `is_active` (`true|false|1|0|yes|no`)

Examples:

- `/api/v1/business/products`
- `/api/v1/business/products?category_id=<id>`
- `/api/v1/business/products?business_id=<id>&is_active=true`

Success `200`:

```json
{"products": [{"_id": "...", "name": "...", "image_path": "http://...", "is_active": true, "...": "..."}]}
```

### `PUT /<product_id>`

Update product fields and/or image.

Auth: business access token required.

Updatable fields:

- `name`
- `description`
- `category_id`
- `price`
- `is_active`
- `image` (multipart)

### `DELETE /<product_id>`

Delete product.

Auth: business access token required.

Behavior:

- Deletes DB entry
- Deletes all image files that start with `<product_id>_`

Success `200`:

```json
{"message": "Product deleted"}
```

---

## Client Orders

Base path: `/api/v1/client/orders`

### `POST /`

Create order as client.

Auth: client access token required.

Request JSON:

```json
{
  "business_id": "...",
  "items": [
    {"product_id": "...", "quantity": 2},
    {"product_id": "...", "quantity": 1}
  ]
}
```

Validation:

- products must exist
- all products must belong to `business_id`
- quantity must be positive integer

Success `201` returns order with calculated totals.

### `GET /`

List signed-in client orders.

Auth: client access token required.

### `DELETE /<order_id>`

Client cancels own order.

Auth: client access token required.

Rules:

- only order owner can cancel
- status must be `placed`
- endpoint sets status to `cancelled` (does not hard-delete)

---

## Business Orders

Base path: `/api/v1/business/orders`

### `GET /`

List orders for signed-in business, enriched with customer and product info.

Auth: business access token required.

Query parameters:

- `from` (optional, ISO8601 or epoch seconds)
- `to` (optional, ISO8601 or epoch seconds)

Default behavior:

- no `from`/`to`: last 12 hours
- only `from`: `to` defaults to now
- only `to`: `from = to - 12 hours`

Order item shape includes product details:

```json
{
  "product_id": "...",
  "product_name": "Latte",
  "product_image": "http://.../static/images/...",
  "quantity": 2,
  "price_at_purchase": 120
}
```

Order also includes customer block:

```json
{"customer": {"id": "...", "name": "Ali Veli", "phone": "..."}}
```

### `PUT /<order_id>`

Update order status.

Auth: business access token required.

Request JSON:

```json
{"status": "preparing"}
```

Allowed statuses:

- `placed`
- `preparing`
- `ready`
- `cancelled`

### `DELETE /<order_id>`

Hard-delete order owned by business.

Auth: business access token required.

---

## Business Analytics

Base path: `/api/v1/business/analytics`

### `GET /`

Returns business analytics summary for a time range.

Auth: business access token required.

Query parameters:

- `from` (optional, ISO8601 or epoch seconds)
- `to` (optional, ISO8601 or epoch seconds)

Default behavior:

- no `from`/`to`: current month (`month_start` to now)
- only `from`: `to` defaults to now
- only `to`: `from` defaults to current month start

Response fields:

- `from`, `to`
- `total_orders`
- `total_revenue`
- `average_order_value`
- `total_items`
- `top_categories` (populated category entries + sold stats)
- `top_products` (populated product entries + sold stats)
- `least_sold_products` (same shape)
- `least_sold_category` (same shape)

Example response shape:

```json
{
  "from": "2026-06-01T00:00:00+00:00",
  "to": "2026-06-01T12:00:00+00:00",
  "total_orders": 21,
  "total_revenue": 4120.0,
  "average_order_value": 196.19,
  "total_items": 53,
  "top_categories": [
    {
      "category": {"_id": "...", "business_id": "...", "name": "Hot Drinks", "created_at": "..."},
      "sold_quantity": 28,
      "sold_revenue": 2330.0
    }
  ],
  "top_products": [
    {
      "product": {"_id": "...", "name": "Latte", "image_path": "http://...", "...": "..."},
      "sold_quantity": 12,
      "sold_revenue": 1440.0
    }
  ],
  "least_sold_products": [...],
  "least_sold_category": {
    "category": {"_id": "...", "name": "Desserts", "...": "..."},
    "sold_quantity": 1,
    "sold_revenue": 90.0
  }
}
```

---

## Business QR

Base path: `/api/v1/business/qr`

### `GET /`

Generate a QR code for the logged-in business.

Auth: business access token required.

Behavior:

- Builds the URL `https://qrmenu.dovanay.com/menu/<business_id>`
- Generates a PNG QR code in memory using `qrcode` + Pillow
- Returns the PNG as a downloadable file

Success `200`:

- Response content type: `image/png`
- Response body: QR code PNG bytes

---

## Public Menu Page

Base path: `/menu/<business_id>`

### `GET /menu/<business_id>`

Serve the public landing page that is encoded in the business QR code.

Auth: none.

Behavior:

- Returns a static HTML page from the `static` folder
- Displays the message `Download our mobile app`
- Links to `https://github.com/Pingeru/qrmenu-mobile`

Success `200`:

- Response content type: `text/html`

---

## Background Cleanup Jobs

Background jobs are started by `run.py` through APScheduler while the API process is alive.

- Hourly (`minute=0`): delete cancelled orders older than 3 hours
- Weekly (`Sunday 03:00 UTC`): orphan cleanup
  - remove image files not referenced by any product
  - remove orders whose `business_id` or `user_id` points to missing records
  - remove products with invalid/mismatched business/category links
  - remove categories pointing to missing businesses

Implementation files:

- `src/cron/scheduler.py`
- `src/cron/cleanup_jobs.py`

---

## Environment Variables

Common variables used by API:

- `API_PORT` (default: `3005`)
- `MONGO_URI`
- `JWT_SECRET` (access token secret)
- `JWT_REFRESH_SECRET` (refresh token secret)
- `ACCESS_TOKEN_TTL_MIN`
- `REFRESH_TOKEN_TTL_DAYS`

For security and compatibility with modern PyJWT checks, keep JWT secrets at least 32+ characters (recommended much longer).

