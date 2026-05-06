# qrmenu-api
QR Menu Builder Backend API

## Business Auth Endpoints
Base path: `/api/v1/business/auth`
- `POST /register` (name, email, password, qr_base_url)
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
