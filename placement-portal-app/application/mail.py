"""
Minimal SMTP mail helper. Points at a local dev SMTP catcher by default
(localhost:1025) so the whole reminder/report pipeline is demoable on your
machine with zero real credentials — matches the statement's "all demos
should be possible on your local machine" requirement. Swap the env vars
for a real account (e.g. Gmail app password) if you ever want it to send
for real outside a demo.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_SENDER = os.environ.get("SMTP_SENDER", "placements@ppa-portal.local")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "false").lower() == "true"


def send_email(to_address, subject, html_body, plain_body=None):
    """
    Sends an email. Never raises — returns True/False — so a mail outage
    never crashes a Celery task; the task's return value already reports
    what happened.
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

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_SENDER, [to_address], msg.as_string())
        return True
    except Exception as exc:
        print(f"[mail] failed to send to {to_address}: {exc}")
        return False