# qrmenu-api

QR Menu Builder backend API built with Flask + MongoDB.

## Full API Reference

For complete endpoint documentation (purpose, request/response schema, auth rules, query parameters, and examples), see:

- `API_DOCUMENTATION.md`

## Quick Start

Install and run:

```bash
pip install -r requirements.txt
python run.py
```

Default API base URL:

- `http://localhost:3005/api/v1`

## Current Endpoint Groups

- Business auth: `/api/v1/business/auth`
- Client auth: `/api/v1/client/auth`
- Categories: `/api/v1/business/categories`
- Products: `/api/v1/business/products`
- Client orders: `/api/v1/client/orders`
- Business orders: `/api/v1/business/orders`
- Business analytics: `/api/v1/business/analytics`
- Business QR code: `/api/v1/business/qr`
- Public menu page: `/menu/<business_id>`
- Password reset page: `/password-reset`

## Postman Config

Import these files into Postman:

- Collection: `postman/qrmenu-api.postman_collection.json`
- Environment: `postman/qrmenu-api.postman_environment.json`

The collection uses `{{baseUrl}}` and `{{apiVersion}}` and is set up to store tokens and created resource IDs in the selected environment.

Suggested workflow:

1. Import the collection and environment.
2. Select the `qrmenu-api local` environment.
3. Run a business or client register/login request to populate `accessToken` and `refreshToken`.
4. Create a category and product to populate `categoryId` and `productId`.
5. Use the saved IDs for order, analytics, QR code, and public menu requests.

## Latest Changes

- Added business QR code endpoint:
  - `GET /api/v1/business/qr/`
  - Requires a signed-in business and returns a downloadable in-memory PNG QR code
  - QR code content points to `https://qrmenu.dovanay.com/menu/<business_id>`
- Added a public menu landing page:
  - `GET /menu/<business_id>`
  - Serves a static web page that prompts users to download the mobile app
  - Links to `https://github.com/Pingeru/qrmenu-mobile`
- Added business analytics endpoint (`GET /api/v1/business/analytics`)
  - Returns totals and ranking metrics: total orders, revenue, AOV, total items, top/least sold products, top/least sold categories
  - Supports `from` and `to` time filters (default: current month)
- Product listing endpoint is now query-filter based:
  - `GET /api/v1/business/products?category_id=<id>&business_id=<id>&is_active=true`
- Business order listing supports timeline filters:
  - `GET /api/v1/business/orders?from=<iso_or_epoch>&to=<iso_or_epoch>`
  - Default remains last 12 hours
- Business order responses are enriched with:
  - item-level product name/image
  - customer summary (`id`, `name`, `phone`)
- Cascade-safe deletes for business/category/product routes were added to avoid orphaned database/file records.
- Added forgot-password flows for businesses and clients:
  - `POST /api/v1/business/auth/forgot-password`
  - `POST /api/v1/client/auth/forgot-password`
  - Both send a reset email with a link to `https://<host>/password-reset?token=<jwt>`
- Added a hosted password reset page:
  - `GET /password-reset?token=<jwt>`
  - `POST /password-reset`
  - The page renders from `templates/password_reset.html` and updates the account password after token validation.

## Background Cleanup Jobs

`run.py` starts APScheduler jobs while the API process is running:

- Hourly (`minute=0`): delete cancelled orders older than 3 hours
- Weekly (`Sunday 03:00 UTC`): remove orphaned images and inconsistent orders/products/categories

Implementation:

- `src/cron/scheduler.py`
- `src/cron/cleanup_jobs.py`

## Required Environment Variables

- `MONGO_URI`
- `JWT_SECRET`
- `JWT_REFRESH_SECRET`
- `PASSWORD_RESET_TOKEN_TTL_MIN` (default `30`)

Optional:

- `API_PORT` (default `3005`)
- `ACCESS_TOKEN_TTL_MIN`
- `REFRESH_TOKEN_TTL_DAYS`
- `SMTP_HOST`
- `SMTP_PORT` (default `587`)
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS` (default `true`)
- `SMTP_USE_SSL` (default `false`)
- `SMTP_TIMEOUT` (default `10`)
- `APP_NAME` (used in email templates)

