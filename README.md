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

Optional:

- `API_PORT` (default `3005`)
- `ACCESS_TOKEN_TTL_MIN`
- `REFRESH_TOKEN_TTL_DAYS`

