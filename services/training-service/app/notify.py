from __future__ import annotations

import logging
import os
import smtplib
import textwrap
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_SUCCESS_COLOR = "#16a34a"
_FAILURE_COLOR = "#dc2626"
_BG_COLOR = "#f1f5f9"
_CARD_COLOR = "#ffffff"
_TEXT_COLOR = "#1e293b"
_MUTED_COLOR = "#64748b"
_CODE_BG = "#0f172a"
_CODE_FG = "#e2e8f0"
_BORDER_COLOR = "#e2e8f0"


def _format_error_html(error: str) -> str:
    """Return an HTML snippet that presents the error clearly.

    CalledProcessError messages embed the full shell command (very long).
    We surface the exit code and trim the command to keep it readable.
    """
    raw = error.strip()

    # Detect subprocess.CalledProcessError pattern and reformat
    exit_code: str | None = None
    short_cmd: str | None = None
    detail: str = raw

    if "returned non-zero exit status" in raw:
        # Extract exit code
        import re
        m = re.search(r"returned non-zero exit status (\d+)", raw)
        if m:
            exit_code = m.group(1)
        # Extract command (between "Command '" and "' returned")
        cmd_m = re.search(r"Command '(.+?)' returned non-zero", raw, re.DOTALL)
        if cmd_m:
            cmd_full = cmd_m.group(1)
            # Show first 200 chars of command
            short_cmd = textwrap.shorten(cmd_full, width=200, placeholder="…")
            detail = f"Exit status {exit_code} — command failed."

    parts: list[str] = []

    if exit_code:
        parts.append(
            f'<div style="margin-bottom:12px;">'
            f'<span style="background:{_FAILURE_COLOR};color:#fff;'
            f'padding:3px 10px;border-radius:4px;font-size:13px;font-weight:600;">'
            f"Exit status {exit_code}</span></div>"
        )

    parts.append(
        f'<p style="margin:0 0 10px;color:{_TEXT_COLOR};font-size:14px;">'
        f"{detail}</p>"
    )

    if short_cmd:
        parts.append(
            f'<p style="margin:0 0 6px;font-size:12px;color:{_MUTED_COLOR};'
            f'font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Command</p>'
            f'<pre style="margin:0 0 14px;padding:10px 14px;background:{_CODE_BG};'
            f"color:{_CODE_FG};border-radius:6px;font-size:12px;line-height:1.5;"
            f'overflow-x:auto;white-space:pre-wrap;word-break:break-all;">'
            f"{_html_escape(short_cmd)}</pre>"
        )

    # Full raw error in a collapsible-style block
    truncated = raw if len(raw) <= 1200 else raw[:1200] + "\n\n[truncated]"
    parts.append(
        f'<p style="margin:0 0 6px;font-size:12px;color:{_MUTED_COLOR};'
        f'font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Full message</p>'
        f'<pre style="margin:0;padding:10px 14px;background:{_CODE_BG};'
        f"color:{_CODE_FG};border-radius:6px;font-size:11px;line-height:1.6;"
        f'overflow-x:auto;white-space:pre-wrap;word-break:break-all;">'
        f"{_html_escape(truncated)}</pre>"
    )

    return "\n".join(parts)


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_html(
    job_id: str,
    status: str,
    metrics: dict | None,
    error: str | None,
    timestamp: str,
) -> str:
    is_success = status == "succeeded"
    accent = _SUCCESS_COLOR if is_success else _FAILURE_COLOR
    status_label = "SUCCEEDED" if is_success else "FAILED"
    icon = "✅" if is_success else "❌"

    # ── Metrics section ────────────────────────────────────────────────────────
    metrics_html = ""
    if metrics:
        rows = ""
        for k, v in metrics.items():
            val = f"{v:.4f}" if isinstance(v, float) else _html_escape(str(v))
            rows += (
                f"<tr>"
                f'<td style="padding:8px 12px;border-bottom:1px solid {_BORDER_COLOR};'
                f"color:{_MUTED_COLOR};font-size:13px;white-space:nowrap;\">{_html_escape(k)}</td>"
                f'<td style="padding:8px 12px;border-bottom:1px solid {_BORDER_COLOR};'
                f"color:{_TEXT_COLOR};font-size:13px;font-weight:600;"
                f'font-family:monospace;">{val}</td>'
                f"</tr>"
            )
        metrics_html = f"""
        <div style="margin-bottom:24px;">
          <p style="margin:0 0 10px;font-size:12px;color:{_MUTED_COLOR};
             font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Metrics</p>
          <table style="width:100%;border-collapse:collapse;border-radius:8px;
             overflow:hidden;border:1px solid {_BORDER_COLOR};">
            {rows}
          </table>
        </div>"""

    # ── Error section ──────────────────────────────────────────────────────────
    error_html = ""
    if error:
        error_html = f"""
        <div style="margin-bottom:24px;">
          <p style="margin:0 0 10px;font-size:12px;color:{_FAILURE_COLOR};
             font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Error details</p>
          <div style="padding:14px 16px;background:#fff5f5;border-left:4px solid {_FAILURE_COLOR};
               border-radius:0 6px 6px 0;">
            {_format_error_html(error)}
          </div>
        </div>"""

    # ── Job info row ───────────────────────────────────────────────────────────
    job_info_html = f"""
        <div style="margin-bottom:24px;padding:14px 16px;background:{_BG_COLOR};
             border-radius:8px;">
          <table style="width:100%;border-collapse:collapse;">
            <tr>
              <td style="padding:4px 0;width:110px;color:{_MUTED_COLOR};font-size:13px;">Job ID</td>
              <td style="padding:4px 0;color:{_TEXT_COLOR};font-size:13px;
                 font-family:monospace;">{job_id}</td>
            </tr>
            <tr>
              <td style="padding:4px 0;color:{_MUTED_COLOR};font-size:13px;">Finished</td>
              <td style="padding:4px 0;color:{_TEXT_COLOR};font-size:13px;">{timestamp}</td>
            </tr>
          </table>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CV Platform — Training Job {status_label}</title>
</head>
<body style="margin:0;padding:0;background:{_BG_COLOR};font-family:-apple-system,
  BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:{_BG_COLOR};min-height:100vh;">
    <tr><td align="center" style="padding:32px 16px;">

      <!-- Card -->
      <table width="600" cellpadding="0" cellspacing="0"
             style="max-width:600px;width:100%;background:{_CARD_COLOR};
             border-radius:12px;overflow:hidden;
             box-shadow:0 1px 3px rgba(0,0,0,.08),0 4px 12px rgba(0,0,0,.05);">

        <!-- Header -->
        <tr>
          <td style="background:{accent};padding:28px 32px;">
            <p style="margin:0 0 4px;font-size:12px;color:rgba(255,255,255,.75);
               letter-spacing:0.08em;text-transform:uppercase;font-weight:600;">
              CV Platform · Training Service
            </p>
            <p style="margin:0;font-size:22px;font-weight:700;color:#fff;">
              {icon}&nbsp; Job {status_label}
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 32px;">
            {job_info_html}
            {metrics_html}
            {error_html}

            <p style="margin:0;font-size:12px;color:{_MUTED_COLOR};
               border-top:1px solid {_BORDER_COLOR};padding-top:16px;">
              This is an automated message from CV Platform.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _build_plain(
    job_id: str,
    status: str,
    metrics: dict | None,
    error: str | None,
    timestamp: str,
) -> str:
    lines = [
        f"CV Platform — Training Job {status.upper()}",
        "=" * 48,
        f"Job ID  : {job_id}",
        f"Status  : {status.upper()}",
        f"Finished: {timestamp}",
        "",
    ]
    if metrics:
        lines.append("METRICS")
        lines.append("-" * 24)
        for k, v in metrics.items():
            val = f"{v:.4f}" if isinstance(v, float) else str(v)
            lines.append(f"  {k}: {val}")
        lines.append("")
    if error:
        lines.append("ERROR")
        lines.append("-" * 24)
        lines.append(error[:1200])
    return "\n".join(lines)


def send_job_notification(
    job_id: str,
    status: str,
    metrics: dict | None = None,
    error: str | None = None,
    to_addr_override: str | None = None,
) -> None:
    """Send an HTML email notification when a training job finishes.

    No-ops silently if NOTIFY_SMTP_PASSWORD or NOTIFY_EMAIL_TO are not set.
    Never raises — notification failures must not affect the job outcome.
    ``to_addr_override`` lets callers set a per-job recipient that takes
    precedence over the NOTIFY_EMAIL_TO env var.
    """
    to_addr = to_addr_override or os.getenv("NOTIFY_EMAIL_TO")
    smtp_host = os.getenv("NOTIFY_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("NOTIFY_SMTP_PORT", "587"))
    smtp_user = os.getenv("NOTIFY_SMTP_USER")
    smtp_password = os.getenv("NOTIFY_SMTP_PASSWORD")

    if not (to_addr and smtp_user and smtp_password):
        return

    icon = "✅" if status == "succeeded" else "❌"
    subject = f"{icon} [CV Platform] Training job {status}: {job_id[:8]}"
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    html_body = _build_html(job_id, status, metrics, error, timestamp)
    plain_body = _build_plain(job_id, status, metrics, error, timestamp)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
        logger.info(
            "notify.email_sent job_id=%s status=%s to=%s", job_id, status, to_addr
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("notify.email_failed job_id=%s error=%s", job_id, exc)
