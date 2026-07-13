import os
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_SENDER = os.environ.get("SMTP_SENDER", "placements@ppa-portal.local")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "false").lower() == "true"
PORTAL_URL = os.environ.get("PORTAL_URL", "http://localhost:5000")


def send_email(to_address, subject, html_body, plain_body=None, max_retries=2, retry_delay=3):
    """
    Sends an email, retrying transient SMTP failures (Mailpit still
    starting, a dropped connection) before giving up. Still never
    raises — returns True/False — so a mail outage never crashes a
    Celery task.
    """
    if not to_address:
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_SENDER
    msg["To"] = to_address
    msg["Subject"] = subject
    if plain_body:
        msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    attempt = 0
    while attempt <= max_retries:
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                if SMTP_USE_TLS:
                    server.starttls()
                if SMTP_USER:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_SENDER, [to_address], msg.as_string())
            return True
        except Exception as exc:
            attempt += 1
            print(f"[mail] attempt {attempt} failed to send to {to_address}: {exc}")
            if attempt <= max_retries:
                time.sleep(retry_delay)
    return False


def wrap_email_html(title, body_html, cta_label=None, cta_url=None):
    """Shared branded wrapper so every reminder/report looks consistent."""
    cta = ""
    if cta_label and cta_url:
        cta = (
            f'<p style="margin-top:24px"><a href="{cta_url}" '
            f'style="background:#0f6e56;color:#fff;padding:10px 18px;'
            f'border-radius:6px;text-decoration:none;display:inline-block">{cta_label}</a></p>'
        )
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#1f1f1f">
      <div style="background:#0f6e56;padding:16px 24px">
        <span style="color:#fff;font-size:18px;font-weight:bold">Placement Portal</span>
      </div>
      <div style="padding:24px;border:1px solid #e5e5e5;border-top:none">
        <h2 style="margin-top:0">{title}</h2>
        {body_html}
        {cta}
      </div>
      <p style="font-size:12px;color:#888;padding:12px 24px">
        You're receiving this because you have an active account on the Placement Portal.
      </p>
    </div>
    """