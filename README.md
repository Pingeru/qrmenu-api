# qrmenu-api
QR Menu Builder Backend API

## Business Auth Endpoints
Base path: `/api/v1/business/auth`
-- `POST /register` (name, email, password)
- `POST /login` (email, password)
- `POST /refresh` (refresh_token)
- `PUT /edit` (access_token + fields to update)
- `DELETE /delete` (access_token)

## Client Auth Endpoints
Base path: `/api/v1/client/auth`
- `POST /register` (first_name, last_name, phone_number, email, password)
- `POST /login` (email, password)
- `POST /refresh` (refresh_token)
- `PUT /edit` (access_token + fields to update)
- `DELETE /delete` (access_token)

## Category Endpoints
Base path: `/api/v1/business/categories`
- `POST /` (Authorization: Bearer access_token, name)
- `GET /` (Authorization: Bearer access_token)
- `GET /:category_id` (Authorization: Bearer access_token)
- `PUT /:category_id` (Authorization: Bearer access_token, name)
- `DELETE /:category_id` (Authorization: Bearer access_token)

## Orders Endpoints
Base path: `/api/v1/client/orders`
- `POST /` (Authorization: Bearer access_token, business_id, items)
- `GET /` (Authorization: Bearer access_token)
- `DELETE /:order_id` (Authorization: Bearer access_token)

## Business Orders Endpoints
Base path: `/api/v1/business/orders`
- `GET /` (Authorization: Bearer access_token)
- `PUT /:order_id` (Authorization: Bearer access_token, status)
- `DELETE /:order_id` (Authorization: Bearer access_token)

# Cron Jobs
The "src/cron" folder contains background cleanup jobs started by `run.py` while the API is running.
- Hourly: delete cancelled orders older than 3 hours.
- Weekly (Sunday 03:00 UTC): cleanup orphaned images and records.
- Monthly (day 1, 04:00 UTC): delete orders older than 3 months.

These schedules use cron-style triggers provided by APScheduler.

