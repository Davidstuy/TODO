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


settings = Settings()

# 保持与老代码相同的导出名，security.py 无需改动
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes