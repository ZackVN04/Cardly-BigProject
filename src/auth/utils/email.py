"""Email delivery via SMTP (aiosmtplib).

Uses STARTTLS on port 587 by default, which works with Gmail and most
free SMTP providers.  No paid services or quotas involved.
"""

import ssl
from email.message import EmailMessage

import aiosmtplib

from src.auth.config import auth_settings
from src.auth.constants import OTP_PURPOSE_VERIFY_EMAIL


async def _send(subject: str, body_html: str, to_email: str) -> None:
    """Low-level helper — build and deliver a single email."""
    message = EmailMessage()
    message["From"] = f"{auth_settings.EMAIL_FROM_NAME} <{auth_settings.EMAIL_FROM}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body_html, subtype="html")

    context = ssl.create_default_context()

    await aiosmtplib.send(
        message,
        hostname=auth_settings.SMTP_HOST,
        port=auth_settings.SMTP_PORT,
        username=auth_settings.SMTP_USER,
        password=auth_settings.SMTP_PASSWORD,
        start_tls=True,
        tls_context=context,
    )


async def send_otp_email(to_email: str, otp: str, purpose: str) -> None:
    """Send the 6-digit OTP for email verification or password reset."""
    if purpose == OTP_PURPOSE_VERIFY_EMAIL:
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
