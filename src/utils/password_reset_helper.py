import os
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

import jwt
from flask import current_app, render_template, request

from src.utils.auth_helper import JWT_ALGORITHM, create_access_token

PASSWORD_RESET_PURPOSE = "password_reset"
PASSWORD_RESET_ACCOUNT_TYPES = {"business", "client"}
PASSWORD_RESET_TOKEN_TTL_DEFAULT_MIN = 30


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_request_origin() -> str:
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.headers.get("X-Forwarded-Host", request.host)
    return f"{proto}://{host}"


def build_password_reset_url(reset_token: str) -> str:
    return f"{get_request_origin()}/password-reset?{urlencode({'token': reset_token})}"


def get_password_reset_ttl_minutes() -> int:
    raw_value = os.getenv("PASSWORD_RESET_TOKEN_TTL_MIN", str(PASSWORD_RESET_TOKEN_TTL_DEFAULT_MIN))
    try:
        ttl_minutes = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("Invalid PASSWORD_RESET_TOKEN_TTL_MIN") from exc

    if ttl_minutes <= 0:
        raise RuntimeError("Invalid PASSWORD_RESET_TOKEN_TTL_MIN")
    return ttl_minutes


def get_account_display_name(account_doc: dict, account_type: str) -> str:
    if account_type == "business":
        return (account_doc.get("name") or account_doc.get("email") or "there").strip()

    first_name = (account_doc.get("first_name") or "").strip()
    last_name = (account_doc.get("last_name") or "").strip()
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    return full_name or (account_doc.get("email") or "there").strip()


def get_account_label(account_type: str) -> str:
    if account_type == "business":
        return "business account"
    return "client account"


def create_password_reset_token(subject_id: str, account_type: str) -> str:
    if account_type not in PASSWORD_RESET_ACCOUNT_TYPES:
        raise ValueError("Invalid account type")

    ttl_minutes = get_password_reset_ttl_minutes()
    return create_access_token(
        subject_id,
        f"password_reset_{account_type}",
        ttl_minutes=ttl_minutes,
        purpose=PASSWORD_RESET_PURPOSE,
        extra_payload={
            "account_type": account_type,
        },
    )


def decode_password_reset_token(token: str) -> dict:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("Missing JWT_SECRET")

    payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    if payload.get("purpose") != PASSWORD_RESET_PURPOSE:
        raise jwt.InvalidTokenError("Invalid token payload")

    account_type = payload.get("account_type")
    user_type = payload.get("user_type") or ""
    if not account_type and user_type.startswith("password_reset_"):
        account_type = user_type.removeprefix("password_reset_")

    if account_type not in PASSWORD_RESET_ACCOUNT_TYPES:
        raise jwt.InvalidTokenError("Invalid token payload")

    expected_user_type = f"password_reset_{account_type}"
    if user_type != expected_user_type:
        raise jwt.InvalidTokenError("Invalid token payload")

    if not payload.get("sub"):
        raise jwt.InvalidTokenError("Invalid token payload")

    payload["account_type"] = account_type
    return payload


def _deliver_password_reset_email(
    *,
    recipient_email: str,
    subject: str,
    reset_url: str,
    html_body: str,
    text_body: str,
) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        raise RuntimeError("Missing SMTP_HOST")

    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_timeout = float(os.getenv("SMTP_TIMEOUT", "10"))
    except ValueError as exc:
        raise RuntimeError("Invalid SMTP configuration") from exc

    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL") or smtp_username or "no-reply@localhost"
    use_ssl = _parse_bool(os.getenv("SMTP_USE_SSL"), False)
    use_tls = False if use_ssl else _parse_bool(os.getenv("SMTP_USE_TLS"), True)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = recipient_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=smtp_timeout) as server:
                if smtp_username and smtp_password:
                    server.login(smtp_username, smtp_password)
                server.send_message(message)
            return

        with smtplib.SMTP(smtp_host, smtp_port, timeout=smtp_timeout) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise RuntimeError("Unable to send password reset email") from exc


def send_password_reset_email(account_doc: dict, account_type: str) -> str:
    if account_type not in PASSWORD_RESET_ACCOUNT_TYPES:
        raise ValueError("Invalid account type")

    recipient_email = (account_doc.get("email") or "").strip()
    if not recipient_email:
        raise RuntimeError("Missing recipient email")

    recipient_name = get_account_display_name(account_doc, account_type)
    reset_token = create_password_reset_token(str(account_doc["_id"]), account_type)
    reset_url = build_password_reset_url(reset_token)
    app_name = os.getenv("APP_NAME")
    if not app_name:
        app_name = current_app.config.get("APP_NAME", "QR Menu")

    html_body = render_template(
        "password_reset_email.html",
        app_name=app_name,
        recipient_name=recipient_name,
        account_label=get_account_label(account_type),
        reset_url=reset_url,
        expires_minutes=get_password_reset_ttl_minutes(),
    )
    text_body = (
        f"Hello {recipient_name},\n\n"
        f"We received a request to reset the password for your {get_account_label(account_type)}.\n"
        f"Use the link below to reset your password:\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )

    _deliver_password_reset_email(
        recipient_email=recipient_email,
        subject="Reset your password",
        reset_url=reset_url,
        html_body=html_body,
        text_body=text_body,
    )
    return reset_url


