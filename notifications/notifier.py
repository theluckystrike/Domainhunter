"""Notification system for pipeline alerts via Slack and email.

NASA Rule 1: Every function under 60 lines.
NASA Rule 2: No global mutable state.
"""
from __future__ import annotations

from typing import Any

import httpx
import structlog

from config.constants import HTTP_TIMEOUT_SECONDS
from config.settings import Settings
from models.verdict import DomainVerdict, VerdictType

logger = structlog.get_logger(__name__)


class Notifier:
    """Send pipeline alerts via Slack webhook and Resend email."""

    def __init__(self, settings: Settings) -> None:
        assert isinstance(settings, Settings), "settings must be a Settings instance"
        assert settings is not None, "settings must not be None"
        self._slack_url: str = settings.slack_webhook_url
        self._alert_email: str = settings.alert_email
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_SECONDS,
        )

    async def send_slack(self, message: str) -> bool:
        """Post a message to the configured Slack webhook.

        Args:
            message: Text message to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        assert isinstance(message, str), "message must be a string"
        assert len(message) > 0, "message must not be empty"

        if not self._slack_url:
            logger.info("slack_not_configured", action="skip")
            return False

        try:
            resp = await self._client.post(
                self._slack_url,
                json={"text": message},
            )
            resp.raise_for_status()
            logger.info("slack_sent", length=len(message))
            return True
        except Exception as exc:
            logger.error("slack_send_failed", error=str(exc))
            return False

    async def send_pipeline_summary(
        self,
        run_id: str,
        counts: dict[str, int],
        verdicts: list[DomainVerdict],
    ) -> bool:
        """Send a pipeline run summary to Slack.

        Args:
            run_id: Unique pipeline run identifier.
            counts: Dict of stage name -> result count.
            verdicts: List of final domain verdicts.

        Returns:
            True if sent successfully, False otherwise.
        """
        assert isinstance(run_id, str) and len(run_id) > 0, "run_id required"
        assert isinstance(counts, dict), "counts must be a dict"

        buy_now = [v for v in verdicts if v.verdict == VerdictType.BUY_NOW]
        watch = [v for v in verdicts if v.verdict == VerdictType.WATCH]

        lines: list[str] = [
            f"*Domain Hunter Pipeline Complete*  `{run_id[:8]}`",
            "",
            f"Scout: {counts.get('scout', 0)} candidates",
            f"Sentinel: {counts.get('sentinel', 0)} vetted",
            f"Archivist: {counts.get('archivist', 0)} verified",
            f"SPECTRE: {counts.get('spectre', 0)} scored",
            f"ORACLE: {counts.get('oracle', 0)} verdicts",
            "",
        ]

        if buy_now:
            lines.append(f"*BUY NOW ({len(buy_now)}):*")
            for idx, v in enumerate(buy_now):
                if idx >= 20:
                    break
                lines.append(f"  {v.domain} | Score: {v.final_score:.1f} | DA: {v.domain_authority}")
            lines.append("")

        if watch:
            lines.append(f"*WATCH ({len(watch)}):*")
            for idx, v in enumerate(watch):
                if idx >= 20:
                    break
                lines.append(f"  {v.domain} | Score: {v.final_score:.1f} | DA: {v.domain_authority}")

        if not buy_now and not watch:
            lines.append("No actionable domains found this run.")

        message = "\n".join(lines)
        return await self.send_slack(message)

    async def send_buy_alert(self, verdict: DomainVerdict) -> bool:
        """Send an immediate alert for a BUY_NOW verdict.

        Args:
            verdict: DomainVerdict with BUY_NOW verdict.

        Returns:
            True if sent successfully, False otherwise.
        """
        assert isinstance(verdict, DomainVerdict), "verdict must be a DomainVerdict"
        assert verdict.verdict == VerdictType.BUY_NOW, "must be a BUY_NOW verdict"

        message = (
            f":rotating_light: *BUY NOW ALERT* :rotating_light:\n\n"
            f"*Domain:* `{verdict.domain}`\n"
            f"*Score:* {verdict.final_score:.1f}/100\n"
            f"*DA:* {verdict.domain_authority}\n"
            f"*Referring Domains:* {verdict.referring_domains:,}\n"
            f"*SPECTRE Score:* {verdict.spectre_score:.1f}\n"
            f"*Estimated Value:* ${verdict.estimated_value_usd:,.0f}\n"
            f"*Years Active:* {verdict.years_active:.1f}\n\n"
            f"*Reasoning:*\n{verdict.reasoning}\n\n"
            f"*Strengths:* {', '.join(verdict.strengths[:5])}\n"
            f"*Risks:* {', '.join(verdict.weaknesses[:5])}"
        )

        slack_ok = await self.send_slack(message)
        email_ok = await self._send_email_alert(verdict)
        return slack_ok or email_ok

    async def _send_email_alert(self, verdict: DomainVerdict) -> bool:
        """Send email alert for a BUY_NOW domain via Resend.

        Args:
            verdict: DomainVerdict with BUY_NOW verdict.

        Returns:
            True if sent successfully, False otherwise.
        """
        assert isinstance(verdict, DomainVerdict), "verdict must be a DomainVerdict"
        assert verdict.verdict == VerdictType.BUY_NOW, "must be BUY_NOW"

        if not self._alert_email:
            logger.info("email_not_configured", action="skip")
            return False

        try:
            import resend
            resend.Emails.send({
                "from": "Domain Hunter <alerts@domainhunter.dev>",
                "to": [self._alert_email],
                "subject": f"BUY NOW: {verdict.domain} (Score: {verdict.final_score:.0f})",
                "html": (
                    f"<h2>{verdict.domain}</h2>"
                    f"<p><b>Score:</b> {verdict.final_score:.1f}/100</p>"
                    f"<p><b>DA:</b> {verdict.domain_authority}</p>"
                    f"<p><b>Value:</b> ${verdict.estimated_value_usd:,.0f}</p>"
                    f"<p><b>Reasoning:</b> {verdict.reasoning}</p>"
                ),
            })
            logger.info("email_sent", domain=verdict.domain, to=self._alert_email)
            return True
        except Exception as exc:
            logger.error("email_send_failed", error=str(exc))
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        assert self._client is not None, "client must exist to close"
        assert isinstance(self._client, httpx.AsyncClient), "client must be AsyncClient"
        await self._client.aclose()
