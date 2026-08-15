"""SMTP 发信模块：只负责真正把邮件发给 SMTP 服务器

本地开发连 aiosmtpd 调试服务器（把邮件打印到控制台），
生产环境换真实 SMTP 配置（QQ/163/阿里云邮件等），代码零改动。
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import MAIL_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME


def send_email(to_email: str, subject: str, body: str) -> None:
    """发送一封纯文本邮件"""
    message = MIMEMultipart("alternative")
    message["From"] = MAIL_FROM
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        server.ehlo()
        if SMTP_USERNAME:  # 调试服务器无需认证
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(MAIL_FROM, [to_email], message.as_string())