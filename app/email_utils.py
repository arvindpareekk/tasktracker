import smtplib
from email.message import EmailMessage

EMAIL_ADDRESS = "2022pceadarvind013@poornima.org"
EMAIL_PASSWORD = "opxx cord oets jsnj"


def send_otp_email(to_email: str, otp: str):
    msg = EmailMessage()
    msg["Subject"] = "Your TaskTracker OTP"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    msg.set_content(f"""
Hello 👋

Your OTP for TaskTracker login is:

🔐 {otp}

This OTP is valid for 5 minutes.
Do not share it with anyone.

– TaskTracker Team
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
