"""FastAPI 应用：用户注册/登录 + Todo CRUD（JWT 鉴权 + 行级隔离）"""
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from .database import create_db_and_tables, get_session
from .models import Todo, TodoCreate, TodoRead, TodoUpdate, Token, User, UserCreate, UserRead
from .security import create_access_token, get_current_user, hash_password, verify_password


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表，关闭时清理"""
    create_db_and_tables()
    yield


app = FastAPI(
    title="Todo API",
    description="带 JWT 鉴权的待办事项 API",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/")
def read_root():
    return {"message": "Todo API is running"}


# ---------- 公开接口：注册 / 登录 ----------

@app.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, session: Session = Depends(get_session)):
    """注册新用户"""
    existing = session.exec(select(User).where(User.username == user.username)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    db_user = User(username=user.username, hashed_password=hash_password(user.password))
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    """登录：校验用户名密码，返回 JWT"""
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    return Token(access_token=create_access_token(user.id))


# ---------- 用户信息 ----------

@app.get("/users/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户的信息（依赖注入已查好，直接返回即可）"""
    return current_user


# ---------- 受保护接口：需要登录，且只能操作自己的数据 ----------

@app.post("/todos", response_model=TodoRead, status_code=status.HTTP_201_CREATED)
def create_todo(
    todo: TodoCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """创建 todo（归属自动绑定当前用户）"""
    db_todo = Todo.model_validate(todo, update={"user_id": current_user.id})
    session.add(db_todo)
    session.commit()
    session.refresh(db_todo)
    return db_todo


@app.get("/todos", response_model=list[TodoRead])
def list_todos(
    completed: Optional[bool] = None,
    sort: Literal["id", "created_at"] = "id",
    order: Literal["asc", "desc"] = "asc",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """列出当前用户的 todo，支持按完成状态过滤 + 按字段排序"""
    query = select(Todo).where(Todo.user_id == current_user.id)
    if completed is not None:
        query = query.where(Todo.completed == completed)

    # 字符串 → 真实列对象；再动态决定升/降序（select 是惰性的，此时才真正组 SQL）
    column = {"id": Todo.id, "created_at": Todo.created_at}[sort]
    order_column = column.asc() if order == "asc" else column.desc()
    return session.exec(query.order_by(order_column)).all()


def _get_owned_todo(todo_id: int, user_id: int, session: Session) -> Todo:
    """公共封装：查一条属于该用户的 todo，不是自己的就当不存在（404）
    WHERE 同时带 id 和 user_id，天然形成行级隔离"""
    db_todo = session.exec(
        select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id)
    ).first()
    if db_todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    return db_todo


@app.get("/todos/{todo_id}", response_model=TodoRead)
def get_todo(
    todo_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """按 ID 查自己的 todo（别人的返回 404）"""
    return _get_owned_todo(todo_id, current_user.id, session)


@app.patch("/todos/{todo_id}", response_model=TodoRead)
def update_todo(
    todo_id: int,
    todo: TodoUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """更新自己的 todo（只更新客户端传入的字段）"""
    db_todo = _get_owned_todo(todo_id, current_user.id, session)

    for field, value in todo.model_dump(exclude_unset=True).items():
        setattr(db_todo, field, value)

    session.add(db_todo)
    session.commit()
    session.refresh(db_todo)
    return db_todo


@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(
    todo_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """删除自己的 todo"""
    db_todo = _get_owned_todo(todo_id, current_user.id, session)
    session.delete(db_todo)
    session.commit()