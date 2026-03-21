"""Transactional email delivery via Resend.

Sends magic links, team invites, and export-ready notifications.
Fails gracefully when RESEND_API_KEY is not configured (logs and returns None).
Resend SDK is synchronous -- all calls wrapped in asyncio.to_thread().
"""

from __future__ import annotations

import asyncio
import logging

from flywheel.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html: str) -> dict | None:
    """Send email via Resend. Returns None and logs if Resend is not configured."""
    if not settings.resend_api_key:
        logger.info("email_skipped to=%s subject=%s (no RESEND_API_KEY)", to, subject)
        return None

    import resend

    resend.api_key = settings.resend_api_key
    params: resend.Emails.SendParams = {
        "from": f"Flywheel <noreply@{settings.email_domain}>",
        "to": [to],
        "subject": subject,
        "html": html,
    }
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info("email_sent to=%s subject=%s", to, subject)
        return result
    except Exception:
        logger.exception("email_failed to=%s subject=%s", to, subject)
        return None


async def send_magic_link(to: str, magic_link_url: str) -> dict | None:
    """Send magic link authentication email."""
    html = f"""\
<h2>Sign in to Flywheel</h2>
<p>Click the link below to sign in to your account:</p>
<p><a href="{magic_link_url}" style="display:inline-block;padding:12px 24px;\
background:#E94D35;color:white;text-decoration:none;border-radius:8px;">Sign In</a></p>
<p>This link expires in 1 hour. If you didn't request this, you can safely ignore this email.</p>
"""
    return await send_email(to, "Sign in to Flywheel", html)


async def send_invite_email(
    to: str,
    invite_url: str,
    tenant_name: str,
    inviter_name: str | None = None,
) -> dict | None:
    """Send team invite email."""
    invited_by = f" by {inviter_name}" if inviter_name else ""
    html = f"""\
<h2>You're invited to {tenant_name}</h2>
<p>You've been invited{invited_by} to join <strong>{tenant_name}</strong> on Flywheel.</p>
<p><a href="{invite_url}" style="display:inline-block;padding:12px 24px;\
background:#E94D35;color:white;text-decoration:none;border-radius:8px;">Accept Invite</a></p>
<p>This invitation expires in 7 days.</p>
"""
    return await send_email(to, f"You're invited to {tenant_name} on Flywheel", html)


async def send_export_ready(to: str, download_url: str) -> dict | None:
    """Send notification that tenant data export is ready for download."""
    html = f"""\
<h2>Your data export is ready</h2>
<p>Your Flywheel data export has been generated and is ready for download:</p>
<p><a href="{download_url}" style="display:inline-block;padding:12px 24px;\
background:#E94D35;color:white;text-decoration:none;border-radius:8px;">Download Export</a></p>
<p>This download link expires in 24 hours.</p>
"""
    return await send_email(to, "Your Flywheel data export is ready", html)
