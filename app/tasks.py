"""Celery 异步任务：broker（队列）和 backend（结果）都使用 Redis"""
import logging

from celery import Celery

from .config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
from .email import send_email

logger = logging.getLogger(__name__)

# Celery 应用：
#   broker  = 消息队列，任务消息放这里，worker 从这里取
#   backend = 任务结果存储，查询任务执行结果用（可省略）
celery_app = Celery(
    "todo",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# 消息序列化用 JSON（跨语言友好、可读）
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="tasks.send_welcome_email")
def send_welcome_email(to_email: str, username: str) -> str:
    """注册后异步发送欢迎邮件（函数体由 worker 进程执行）

    注意：注册接口只调用 send_welcome_email.delay(...)，
    那一步只是把任务消息塞进 Redis 队列就返回了，
    真正执行到这里的是后台的 celery worker 进程。
    """
    logger.info("worker 开始发送欢迎邮件到 %s", to_email)
    send_email(
        to_email,
        subject="欢迎注册 Todo API",
        body=f"Hi {username}，欢迎使用 Todo API！你的账号已注册成功。",
    )
    logger.info("worker 已将邮件发送到 %s", to_email)
    return f"sent to {to_email}"