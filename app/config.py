"""应用配置：从 .env / 环境变量读取，敏感信息不写进代码

优先级：环境变量 > .env 文件 > 代码默认值
字段名与配置项不区分大小写：secret_key ↔ SECRET_KEY
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    secret_key: str  # 没有默认值：没有 SECRET_KEY 时启动直接报错，防止安全配置缺失
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # ---- SMTP 邮件参数（本地默认连 aiosmtpd 调试服务器）----
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    mail_from: str = "noreply@example.com"

    # ---- Celery 消息队列 ----
    celery_broker_url: str = "redis://localhost:6379/0"     # 队列（broker）
    celery_result_backend: str = "redis://localhost:6379/1"  # 任务结果存储（backend）


settings = Settings()

# 保持与老代码相同的导出名，security.py 无需改动
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

SMTP_HOST = settings.smtp_host
SMTP_PORT = settings.smtp_port
SMTP_USERNAME = settings.smtp_username
SMTP_PASSWORD = settings.smtp_password
MAIL_FROM = settings.mail_from

CELERY_BROKER_URL = settings.celery_broker_url
CELERY_RESULT_BACKEND = settings.celery_result_backend