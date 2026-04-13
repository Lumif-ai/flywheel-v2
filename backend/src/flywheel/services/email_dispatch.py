"""Unified email dispatch that routes to the correct provider.

Routes outbound email to the user's connected email integration:
1. Gmail (via Gmail API) -- if connected
2. Outlook (via Microsoft Graph) -- if connected
3. Resend (noreply@lumif.ai) -- fallback when no integration connected
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import Integration

logger = logging.getLogger(__name__)


async def send_email_as_user(
    db: AsyncSession,
    tenant_id: UUID,
    to: str,
    subject: str,
    body_html: str,
) -> dict:
    """Send an email using the tenant's connected email provider.

    Checks for a connected Gmail or Outlook integration, then routes to
    the appropriate provider. Falls back to Resend if no email integration
    is connected.

    Args:
        db: Async database session.
        tenant_id: Tenant UUID.
        to: Recipient email address.
        subject: Email subject line.
        body_html: HTML body content.

    Returns:
        Dict with provider used and message_id (if available).
    """
    # Look for a connected email integration (Gmail, Gmail-Read, or Outlook)
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.provider.in_(["gmail", "gmail-read", "outlook"]),
            Integration.status == "connected",
        )
    )
    integration = result.scalars().first()

    if integration is not None:
        if integration.provider == "gmail":
            from flywheel.services.google_gmail import send_email_gmail

            message_id = await send_email_gmail(integration, to, subject, body_html)
            await db.commit()  # persist any refreshed credentials
            logger.info(
                "email_sent_as_user provider=gmail to=%s subject=%s msg_id=%s",
                to, subject, message_id,
            )
            return {"provider": "gmail", "message_id": message_id}

        elif integration.provider == "gmail-read":
            from flywheel.services.gmail_read import (
                get_valid_credentials as get_gmail_read_creds,
            )
            import asyncio as _asyncio
            import base64 as _b64
            from email.mime.text import MIMEText as _MIMEText

            # For gmail-read, use the gmail_read module's credential handling.
            # Note: send_email_as_user is for general dispatch. Draft approval
            # uses the dedicated approve endpoint in api/email.py instead.
            # This route is a safety net if dispatch is called with a gmail-read integration.
            creds = await get_gmail_read_creds(integration)

            def _send_raw():
                from googleapiclient.discovery import build as _gbuild
                service = _gbuild("gmail", "v1", credentials=creds)
                msg = _MIMEText(body_html, "html")
                msg["To"] = to
                msg["Subject"] = subject
                raw = _b64.urlsafe_b64encode(msg.as_bytes()).decode()
                return service.users().messages().send(userId="me", body={"raw": raw}).execute()

            result_msg = await _asyncio.to_thread(_send_raw)
            message_id = result_msg.get("id")
            await db.commit()
            logger.info(
                "email_sent_as_user provider=gmail-read to=%s subject=%s msg_id=%s",
                to, subject, message_id,
            )
            return {"provider": "gmail-read", "message_id": message_id}

        elif integration.provider == "outlook":
            from flywheel.services.microsoft_outlook import send_email_outlook

            result_dict = await send_email_outlook(integration, to, subject, body_html)
            await db.commit()  # persist any refreshed credentials
            logger.info(
                "email_sent_as_user provider=outlook to=%s subject=%s",
                to, subject,
            )
            return {"provider": "outlook", "message_id": None, **result_dict}

    # Fallback: send via Resend (noreply@lumif.ai)
    from flywheel.services.email import send_email

    resend_result = await send_email(to, subject, body_html)
    logger.info("email_sent_fallback provider=resend to=%s subject=%s", to, subject)
    return {
        "provider": "resend",
        "message_id": resend_result.get("id") if resend_result else None,
    }
