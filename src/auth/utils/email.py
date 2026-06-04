"""Email delivery via SMTP (aiosmtplib).

Uses STARTTLS on port 587 by default, which works with Gmail and most
free SMTP providers.  No paid services or quotas involved.
"""

import logging
import ssl
from email.message import EmailMessage

import aiosmtplib

from src.auth.config import auth_settings
from src.exceptions import AppException

logger = logging.getLogger(__name__)


class EmailDeliveryError(AppException):
    """Raised when the SMTP delivery fails for any reason."""
    status_code = 502
    code = "EMAIL_DELIVERY_FAILED"
    message = "We could not send the verification email. Please try again later."


async def _send(subject: str, body_html: str, to_email: str) -> None:
    """Low-level helper — build and deliver a single email."""
    # Guard: if SMTP credentials are not configured, fail fast with a clear error
    # rather than letting aiosmtplib throw an unhandled exception that would
    # bypass the CORS middleware and show up as a cryptic CORS error on the client.
    if not auth_settings.SMTP_USER or not auth_settings.SMTP_PASSWORD:
        logger.error(
            "SMTP credentials are not configured (SMTP_USER / SMTP_PASSWORD are empty). "
            "Email delivery is disabled."
        )
        raise EmailDeliveryError()

    message = EmailMessage()
    message["From"] = f"{auth_settings.EMAIL_FROM_NAME} <{auth_settings.EMAIL_FROM}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body_html, subtype="html")

    context = ssl.create_default_context()

    try:
        await aiosmtplib.send(
            message,
            hostname=auth_settings.SMTP_HOST,
            port=auth_settings.SMTP_PORT,
            username=auth_settings.SMTP_USER,
            password=auth_settings.SMTP_PASSWORD,
            start_tls=True,
            tls_context=context,
        )
    except aiosmtplib.SMTPException as exc:
        logger.error("SMTP error when sending s to %s: %s", to_email, exc)
        raise EmailDeliveryError() from exc
    except OSError as exc:
        # Covers network-level failures: connection refused, DNS failure, timeout, etc.
        logger.error("Network error when connecting to SMTP server: %s", exc)
        raise EmailDeliveryError() from exc


async def send_otp_email(to_email: str, otp: str, purpose: str) -> None:
    """Send the 6-digit OTP for email verification or password reset."""
    if purpose == "verify_email":
        subject = "Verify your Cardly account"
        action_label = "complete your registration"
    else:
        subject = "Reset your Cardly password"
        action_label = "reset your password"

    body = f"""
    <html><body style="font-family:sans-serif;color:#333">
      <h2>Your one-time code</h2>
      <p>Use the code below to {action_label}.
         It expires in <strong>{auth_settings.OTP_EXP_MINUTES} minutes</strong>.</p>
      <div style="font-size:2rem;letter-spacing:.4rem;font-weight:bold;
                  padding:16px;background:#f4f4f4;display:inline-block;
                  border-radius:8px;margin:8px 0">{otp}</div>
      <p style="color:#888;font-size:.85rem">
        If you didn't request this, you can safely ignore this email.
      </p>
    </body></html>
    """

    await _send(subject=subject, body_html=body, to_email=to_email)
