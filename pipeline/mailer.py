"""HTML email generation and SMTP dispatch."""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from pipeline.models import ProcessedArticle

logger = logging.getLogger(__name__)


def build_html_email(
    processed: list[ProcessedArticle],
    config: dict,
    run_date: str,
) -> str:
    """Build HTML email body grouped by category."""
    domain = config.get("domain", {})
    categories = config.get("categories", [])
    cat_names = [c["name"] for c in categories] if categories else []

    by_category: dict[str, list[ProcessedArticle]] = {}
    for pa in processed:
        if not pa.ai_result.is_primary:
            continue
        cat = pa.ai_result.category
        by_category.setdefault(cat, []).append(pa)

    ordered_cats = [c for c in cat_names if c in by_category]
    for c in by_category:
        if c not in ordered_cats:
            ordered_cats.append(c)

    article_count = sum(len(v) for v in by_category.values())

    sections = []
    for cat in ordered_cats:
        items = by_category[cat]
        item_html = []
        for pa in items:
            summary_bullets = "".join(
                f"<li>{s}</li>" for s in pa.ai_result.summary
            )
            item_html.append(f"""
            <div style="margin-bottom:16px;padding:12px;background:#f8f9fa;border-radius:6px;">
                <a href="{pa.article.url}" style="color:#1a73e8;font-weight:bold;text-decoration:none;">
                    {pa.article.title}
                </a>
                <div style="color:#666;font-size:12px;margin:4px 0;">
                    {pa.article.source} · {pa.article.published_date}
                </div>
                <ul style="margin:8px 0 0;padding-left:20px;color:#333;">
                    {summary_bullets}
                </ul>
            </div>""")

        sections.append(f"""
        <div style="margin-bottom:24px;">
            <h2 style="color:#1a1a2e;border-bottom:2px solid #1a73e8;padding-bottom:4px;font-size:16px;">
                {cat} ({len(items)})
            </h2>
            {"".join(item_html)}
        </div>""")

    domain_name = domain.get("name", "")
    description = domain.get("description", "")

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:700px;margin:0 auto;padding:20px;">
    <div style="background:#1a1a2e;color:white;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
        <h1 style="margin:0;font-size:20px;">{description}</h1>
        <p style="margin:4px 0 0;opacity:0.8;">{run_date} · {article_count}건</p>
    </div>
    <div style="padding:20px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;">
        {"".join(sections)}
    </div>
    <p style="text-align:center;color:#999;font-size:11px;margin-top:16px;">
        Powered by auto-newsbriefing
    </p>
</body>
</html>"""


def send_email(
    html_body: str,
    config: dict,
    run_date: str,
) -> bool:
    """Send HTML email via SMTP. Returns True on success."""
    email_config = config.get("email", {})
    if not email_config.get("enabled", True):
        logger.info("Email disabled in config")
        return False

    recipients = email_config.get("recipients", [])
    if not recipients:
        logger.warning("No email recipients configured")
        return False

    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP credentials not set, skipping email")
        return False

    sender_name = email_config.get("sender_name", "Auto News Briefing")
    prefix = email_config.get("subject_prefix", "[News Briefing]")
    article_count = html_body.count("background:#f8f9fa")
    subject = f"{prefix} {run_date} ({article_count}건)"

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{sender_name} <{smtp_user}>"
    msg["To"] = smtp_user
    msg["Bcc"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            all_recipients = [smtp_user] + recipients
            server.sendmail(smtp_user, all_recipients, msg.as_string())
        logger.info("Email sent to %d recipients", len(recipients))
        return True
    except (TimeoutError, ConnectionRefusedError, smtplib.SMTPException) as e:
        logger.error("Email send failed: %s", e)
        return False
