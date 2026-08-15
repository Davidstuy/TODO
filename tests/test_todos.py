"""JWT 鉴权版接口测试：注册/登录/鉴权/行级隔离 + 5 个 CRUD + 异步欢迎邮件"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app import models  # 确保建表前模型已注册到 SQLModel.metadata
from app.models import Todo, utcnow
from app.tasks import celery_app

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_session():
    with Session(test_engine) as session:
        yield session


app.dependency_overrides[get_session] = override_get_session


@pytest.fixture(autouse=True)
def reset_db():
    """每个测试前建表、测试后清空"""
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(autouse=True)
def eager_celery(monkeypatch):
    """让 Celery 测试不依赖 Redis 和 worker：
    1) eager 模式：.delay() 同步内联执行任务体
    2) 把真实 SMTP 发信换成记录器，避免测试真的去连 SMTP 服务器
    """
    celery_app.conf.task_always_eager = True

    recorded = {"emails": []}

    def fake_send_email(to_email, subject, body):
        recorded["emails"].append({"to_email": to_email, "subject": subject, "body": body})

    monkeypatch.setattr("app.tasks.send_email", fake_send_email)
    monkeypatch.setattr("app.email.send_email", fake_send_email)
    return recorded


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """注册并登录一个用户，返回带 Bearer token 的请求头"""
    client.post(
        "/register", json={"username": "alice", "email": "alice@example.com", "password": "secret123"}
    )
    resp = client.post("/login", data={"username": "alice", "password": "secret123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------- 注册 / 登录 ----------

def test_register(client, eager_celery):
    resp = client.post(
        "/register", json={"username": "bob", "email": "bob@example.com", "password": "secret123"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "bob"
    assert body["email"] == "bob@example.com"
    assert "id" in body
    assert "hashed_password" not in body  # 密码哈希绝不能返回给客户端

    # created_at 应自动填充，且是刚刚创建的时间
    created_at = datetime.fromisoformat(body["created_at"])
    age = datetime.now(timezone.utc).replace(tzinfo=None) - created_at
    assert 0 <= age.total_seconds() < 5

    # 注册成功应触发异步欢迎邮件（eager 模式下已被内联执行）
    assert len(eager_celery["emails"]) == 1
    assert eager_celery["emails"][0]["to_email"] == "bob@example.com"
    assert "欢迎" in eager_celery["emails"][0]["subject"]


def test_register_invalid_email(client):
    resp = client.post(
        "/register", json={"username": "bob", "email": "这不是邮箱", "password": "secret123"}
    )
    assert resp.status_code == 422  # EmailStr 自动校验，非法邮箱被拒


def test_register_duplicate_username(client):
    client.post("/register", json={"username": "bob", "email": "bob@example.com", "password": "secret123"})
    resp = client.post("/register", json={"username": "bob", "email": "other@example.com", "password": "another99"})
    assert resp.status_code == 400  # 重名拦截
    assert "already registered" in resp.json()["detail"]


def test_register_duplicate_email(client):
    client.post("/register", json={"username": "bob", "email": "bob@example.com", "password": "secret123"})
    resp = client.post("/register", json={"username": "lee", "email": "bob@example.com", "password": "secret123"})
    assert resp.status_code == 400  # 邮箱唯一约束


def test_login_success(client):
    client.post("/register", json={"username": "bob", "email": "bob@example.com", "password": "secret123"})
    resp = client.post("/login", data={"username": "bob", "password": "secret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]  # 非空即视为签发了 JWT


def test_login_wrong_password(client):
    client.post("/register", json={"username": "bob", "email": "bob@example.com", "password": "secret123"})
    resp = client.post("/login", data={"username": "bob", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/login", data={"username": "nobody", "password": "secret123"})
    assert resp.status_code == 401  # 与密码错误返回一致，防止账号枚举


# ---------- 鉴权拦截 ----------

def test_todos_require_token(client):
    assert client.get("/todos").status_code == 401
    assert client.post("/todos", json={"title": "x"}).status_code == 401
    assert client.get("/todos/1").status_code == 401
    assert client.patch("/todos/1", json={"completed": True}).status_code == 401
    assert client.delete("/todos/1").status_code == 401


def test_invalid_token_rejected(client):
    resp = client.get("/todos", headers={"Authorization": "Bearer not.a.valid.token"})
    assert resp.status_code == 401


# ---------- 5 个 CRUD（带 token） ----------

def test_create_todo(client, auth_headers):
    resp = client.post(
        "/todos", json={"title": "学 SQLModel", "description": "写 Todo API"}, headers=auth_headers
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "学 SQLModel"
    assert body["description"] == "写 Todo API"
    assert body["completed"] is False
    assert body["id"] == 1
    assert body["user_id"] == 1  # 归属自动绑定当前用户

    # created_at 应被自动填充，且是刚刚创建的时间（几秒以内）
    created_at = datetime.fromisoformat(body["created_at"])
    age = datetime.now(timezone.utc).replace(tzinfo=None) - created_at
    assert 0 <= age.total_seconds() < 5
    assert age.total_seconds() >= 0


def test_list_own_todos(client, auth_headers):
    client.post("/todos", json={"title": "第一件事"}, headers=auth_headers)
    client.post("/todos", json={"title": "第二件事", "completed": True}, headers=auth_headers)

    resp = client.get("/todos", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2


def test_get_todo_by_id(client, auth_headers):
    created = client.post("/todos", json={"title": "查我"}, headers=auth_headers).json()

    resp = client.get(f"/todos/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "查我"

    missing = client.get("/todos/9999", headers=auth_headers)
    assert missing.status_code == 404


def test_update_todo(client, auth_headers):
    created = client.post("/todos", json={"title": "旧标题"}, headers=auth_headers).json()
    todo_id = created["id"]

    resp = client.patch(
        f"/todos/{todo_id}", json={"completed": True, "title": "新标题"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "新标题"
    assert body["completed"] is True
    assert body["description"] is None  # 未传入的字段保持原样


def test_delete_todo(client, auth_headers):
    created = client.post("/todos", json={"title": "待删除"}, headers=auth_headers).json()
    todo_id = created["id"]

    resp = client.delete(f"/todos/{todo_id}", headers=auth_headers)
    assert resp.status_code == 204

    gone = client.get(f"/todos/{todo_id}", headers=auth_headers)
    assert gone.status_code == 404


# ---------- 行级隔离 ----------

def _register_and_login(client, username, password="secret123"):
    client.post(
        "/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    resp = client.post("/login", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_list_only_shows_own_todos(client):
    alice_headers = _register_and_login(client, "alice")
    bob_headers = _register_and_login(client, "bob")

    client.post("/todos", json={"title": "alice 的①"}, headers=alice_headers)
    client.post("/todos", json={"title": "alice 的②"}, headers=alice_headers)
    client.post("/todos", json={"title": "bob 的①"}, headers=bob_headers)

    alice_items = client.get("/todos", headers=alice_headers).json()
    bob_items = client.get("/todos", headers=bob_headers).json()
    assert [t["title"] for t in alice_items] == ["alice 的①", "alice 的②"]
    assert [t["title"] for t in bob_items] == ["bob 的①"]


def test_user_cannot_access_others_todo(client):
    alice_headers = _register_and_login(client, "alice")
    bob_headers = _register_and_login(client, "bob")

    created = client.post(
        "/todos", json={"title": "alice 的秘密"}, headers=alice_headers
    ).json()
    todo_id = created["id"]

    # bob 查/改/删 alice 的 todo → 统一 404（装作不存在）
    assert client.get(f"/todos/{todo_id}", headers=bob_headers).status_code == 404
    assert client.patch(f"/todos/{todo_id}", json={"completed": True}, headers=bob_headers).status_code == 404
    assert client.delete(f"/todos/{todo_id}", headers=bob_headers).status_code == 404

    # alice 自己的数据完好无损
    assert client.get(f"/todos/{todo_id}", headers=alice_headers).status_code == 200
    assert client.get("/todos", headers=alice_headers).json() != []


# ---------- 练习 2：/users/me ----------

def test_get_me(client, auth_headers):
    resp = client.get("/users/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "alice"
    assert "created_at" in body  # 练习 1 的 User.created_at 也随响应返回

    assert client.get("/users/me").status_code == 401  # 未登录 401


# ---------- 练习 3：过滤 + 排序 ----------

def test_filter_by_completed(client, auth_headers):
    client.post("/todos", json={"title": "未完成"}, headers=auth_headers)
    client.post("/todos", json={"title": "已完成", "completed": True}, headers=auth_headers)

    done = client.get("/todos?completed=true", headers=auth_headers).json()
    todo = client.get("/todos?completed=false", headers=auth_headers).json()
    assert [t["title"] for t in done] == ["已完成"]
    assert [t["title"] for t in todo] == ["未完成"]


def test_sort_todos(client, auth_headers):
    early = client.post("/todos", json={"title": "早"}, headers=auth_headers).json()
    late = client.post("/todos", json={"title": "晚"}, headers=auth_headers).json()

    # 直接改库，让两行 created_at 明确相差一天（避免微秒级偶然相等导致排序不稳定）
    with Session(test_engine) as s:
        later = s.get(Todo, late["id"])
        later.created_at = utcnow() + timedelta(days=1)
        s.add(later)
        s.commit()

    desc = client.get("/todos?sort=created_at&order=desc", headers=auth_headers).json()
    assert [t["title"] for t in desc] == ["晚", "早"]

    asc = client.get("/todos?sort=created_at&order=asc", headers=auth_headers).json()
    assert [t["title"] for t in asc] == ["早", "晚"]


def test_invalid_sort_value_rejected(client, auth_headers):
    resp = client.get("/todos?sort=title", headers=auth_headers)
    assert resp.status_code == 422  # Literal 类型自动校验非法值