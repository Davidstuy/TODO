"""SQLModel 模型定义：User / Todo + 外键一对多关系"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


# ---------- User ----------

class UserCreate(SQLModel):
    """注册请求体"""
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class UserRead(SQLModel):
    """用户响应体：绝不包含 hashed_password"""
    id: int
    username: str


class User(SQLModel, table=True):
    """用户表（users）"""
    __tablename__ = "users"  # 避免 PostgreSQL 中 user 是保留字

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str

    todos: List["Todo"] = Relationship(back_populates="user")


class Token(SQLModel):
    """登录成功返回的 JWT"""
    access_token: str
    token_type: str = "bearer"


# ---------- Todo ----------

class TodoBase(SQLModel):
    """所有模型的公共字段"""

    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    completed: bool = False


class TodoCreate(TodoBase):
    """创建请求体：只包含客户端能传的字段"""

    pass


class TodoUpdate(SQLModel):
    """更新请求体：所有字段都可选，只更新传入的字段"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None


def utcnow() -> datetime:
    """返回无时区的 UTC 当前时间（SQLite 存标准格式）"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TodoRead(TodoBase):
    """响应体：包含 id、归属用户和创建时间，但不暴露关系对象"""
    id: int
    user_id: Optional[int] = None
    created_at: datetime


class Todo(TodoBase, table=True):
    """真正的数据库表模型"""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    # default_factory=：每次创建实例时执行 utcnow()，而不是 import 时算一次
    created_at: datetime = Field(default_factory=utcnow)

    user: Optional["User"] = Relationship(back_populates="todos")