"""JWT 鉴权版接口测试：注册/登录/鉴权/行级隔离 + 5 个 CRUD"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app import models  # 确保建表前模型已注册到 SQLModel.metadata

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


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """注册并登录一个用户，返回带 Bearer token 的请求头"""
    client.post("/register", json={"username": "alice", "password": "secret123"})
    resp = client.post("/login", data={"username": "alice", "password": "secret123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------- 注册 / 登录 ----------

def test_register(client):
    resp = client.post("/register", json={"username": "bob", "password": "secret123"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "bob"
    assert "id" in body
    assert "hashed_password" not in body  # 密码哈希绝不能返回给客户端


def test_register_duplicate_username(client):
    client.post("/register", json={"username": "bob", "password": "secret123"})
    resp = client.post("/register", json={"username": "bob", "password": "another99"})
    assert resp.status_code == 400  # 重名拦截
    assert "already registered" in resp.json()["detail"]


def test_login_success(client):
    client.post("/register", json={"username": "bob", "password": "secret123"})
    resp = client.post("/login", data={"username": "bob", "password": "secret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]  # 非空即视为签发了 JWT


def test_login_wrong_password(client):
    client.post("/register", json={"username": "bob", "password": "secret123"})
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
    client.post("/register", json={"username": username, "password": password})
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