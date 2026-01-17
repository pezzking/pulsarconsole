"""Service for dispatching notifications to external channels."""

import smtplib
import time
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

from app.core.logging import get_logger
from app.models.notification import Notification
from app.models.notification_channel import ChannelType, NotificationChannel

logger = get_logger(__name__)


@dataclass
class DispatchResult:
    """Result of a notification dispatch attempt."""

    success: bool
    error: str | None = None
    latency_ms: float | None = None


class NotificationDispatcher:
    """Handles sending notifications to external channels."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def dispatch(
        self,
        channel: NotificationChannel,
        config: dict[str, Any],
        notification: Notification,
    ) -> DispatchResult:
        """Dispatch notification to a channel."""
        channel_type = ChannelType(channel.channel_type)

        try:
            if channel_type == ChannelType.WEBHOOK:
                return await self._send_webhook(config, notification)
            elif channel_type == ChannelType.SLACK:
                return await self._send_slack(config, notification)
            elif channel_type == ChannelType.EMAIL:
                return await self._send_email(config, notification)
            else:
                return DispatchResult(
                    success=False,
                    error=f"Unknown channel type: {channel_type}",
                )
        except Exception as e:
            logger.error(
                "Dispatch failed",
                channel=channel.name,
                channel_type=channel.channel_type,
                error=str(e),
            )
            return DispatchResult(success=False, error=str(e))

    async def _send_webhook(
        self,
        config: dict[str, Any],
        notification: Notification,
    ) -> DispatchResult:
        """Send notification via webhook."""
        url = config["url"]
        method = config.get("method", "POST")
        headers = config.get("headers", {})
        timeout = config.get("timeout_seconds", self.timeout)

        payload = {
            "id": str(notification.id),
            "type": notification.type,
            "severity": notification.severity,
            "title": notification.title,
            "message": notification.message,
            "resource_type": notification.resource_type,
            "resource_id": notification.resource_id,
            "created_at": notification.created_at.isoformat(),
        }

        if config.get("include_metadata", True) and notification.extra_data:
            payload["metadata"] = notification.extra_data

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=payload,
                    headers=headers,
                )
                latency = (time.time() - start) * 1000

                if response.status_code >= 400:
                    return DispatchResult(
                        success=False,
                        error=f"HTTP {response.status_code}: {response.text[:200]}",
                        latency_ms=latency,
                    )

                logger.info(
                    "Webhook notification sent",
                    url=url,
                    status=response.status_code,
                    latency_ms=latency,
                )
                return DispatchResult(success=True, latency_ms=latency)
        except httpx.TimeoutException:
            latency = (time.time() - start) * 1000
            return DispatchResult(
                success=False,
                error=f"Request timeout after {timeout}s",
                latency_ms=latency,
            )
        except httpx.RequestError as e:
            latency = (time.time() - start) * 1000
            return DispatchResult(
                success=False,
                error=f"Request error: {e!s}",
                latency_ms=latency,
            )

    async def _send_slack(
        self,
        config: dict[str, Any],
        notification: Notification,
    ) -> DispatchResult:
        """Send notification via Slack webhook."""
        webhook_url = config["webhook_url"]

        # Determine color based on severity
        color_map = {
            "critical": "#dc3545",  # red
            "warning": "#ffc107",  # yellow
            "info": "#17a2b8",  # blue
        }
        color = color_map.get(notification.severity, "#6c757d")

        # Build Slack message with attachments
        fields = [
            {"title": "Severity", "value": notification.severity.upper(), "short": True},
            {"title": "Type", "value": notification.type, "short": True},
        ]

        if notification.resource_type and notification.resource_id:
            fields.append({
                "title": "Resource",
                "value": f"{notification.resource_type}: {notification.resource_id}",
                "short": False,
            })

        payload: dict[str, Any] = {
            "username": config.get("username", "Pulsar Console"),
            "icon_emoji": config.get("icon_emoji", ":bell:"),
            "attachments": [
                {
                    "color": color,
                    "title": notification.title,
                    "text": notification.message,
                    "fields": fields,
                    "footer": "Pulsar Console",
                    "ts": int(notification.created_at.timestamp()),
                }
            ],
        }

        if config.get("channel"):
            payload["channel"] = config["channel"]

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(webhook_url, json=payload)
                latency = (time.time() - start) * 1000

                if response.status_code != 200:
                    return DispatchResult(
                        success=False,
                        error=f"Slack error: {response.text[:200]}",
                        latency_ms=latency,
                    )

                logger.info(
                    "Slack notification sent",
                    channel=config.get("channel", "default"),
                    latency_ms=latency,
                )
                return DispatchResult(success=True, latency_ms=latency)
        except httpx.TimeoutException:
            latency = (time.time() - start) * 1000
            return DispatchResult(
                success=False,
                error="Slack request timeout",
                latency_ms=latency,
            )
        except httpx.RequestError as e:
            latency = (time.time() - start) * 1000
            return DispatchResult(
                success=False,
                error=f"Slack request error: {e!s}",
                latency_ms=latency,
            )

    async def _send_email(
        self,
        config: dict[str, Any],
        notification: Notification,
    ) -> DispatchResult:
        """Send notification via email."""
        start = time.time()

        try:
            # Build email message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{notification.severity.upper()}] {notification.title}"
            msg["From"] = (
                f"{config.get('from_name', 'Pulsar Console')} <{config['from_address']}>"
            )
            msg["To"] = ", ".join(config["recipients"])

            # Plain text body
            text_body = f"""
{notification.title}

{notification.message}

Severity: {notification.severity.upper()}
Type: {notification.type}
Time: {notification.created_at.isoformat()}
"""
            if notification.resource_type and notification.resource_id:
                text_body += (
                    f"\nResource: {notification.resource_type} - {notification.resource_id}"
                )

            # HTML body
            severity_colors = {
                "critical": "#dc3545",
                "warning": "#ffc107",
                "info": "#17a2b8",
            }
            color = severity_colors.get(notification.severity, "#6c757d")

            html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 20px;">
    <div style="border-left: 4px solid {color}; padding-left: 16px; margin-bottom: 20px;">
        <h2 style="margin: 0 0 8px 0; color: #333;">{notification.title}</h2>
        <span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">
            {notification.severity.upper()}
        </span>
    </div>
    <p style="color: #333; line-height: 1.6; margin: 16px 0;">{notification.message}</p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <table style="color: #666; font-size: 12px;">
        <tr><td style="padding-right: 16px;"><strong>Type:</strong></td><td>{notification.type}</td></tr>
        <tr><td style="padding-right: 16px;"><strong>Time:</strong></td><td>{notification.created_at.isoformat()}</td></tr>
"""
            if notification.resource_type and notification.resource_id:
                html_body += f"""
        <tr><td style="padding-right: 16px;"><strong>Resource:</strong></td><td>{notification.resource_type}: {notification.resource_id}</td></tr>
"""
            html_body += """
    </table>
    <p style="color: #999; font-size: 11px; margin-top: 20px;">Sent by Pulsar Console</p>
</body>
</html>
"""

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Send via SMTP
            smtp_host = config["smtp_host"]
            smtp_port = config.get("smtp_port", 587)
            use_tls = config.get("smtp_use_tls", True)

            if use_tls:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(smtp_host, smtp_port)

            try:
                if config.get("smtp_user") and config.get("smtp_password"):
                    server.login(config["smtp_user"], config["smtp_password"])
                server.send_message(msg)
            finally:
                server.quit()

            latency = (time.time() - start) * 1000
            logger.info(
                "Email notification sent",
                recipients=config["recipients"],
                latency_ms=latency,
            )
            return DispatchResult(success=True, latency_ms=latency)

        except smtplib.SMTPAuthenticationError as e:
            latency = (time.time() - start) * 1000
            return DispatchResult(
                success=False,
                error=f"SMTP authentication failed: {e!s}",
                latency_ms=latency,
            )
        except smtplib.SMTPException as e:
            latency = (time.time() - start) * 1000
            return DispatchResult(
                success=False,
                error=f"SMTP error: {e!s}",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return DispatchResult(
                success=False,
                error=f"Email error: {e!s}",
                latency_ms=latency,
            )
