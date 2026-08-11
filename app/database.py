"""数据库连接：engine + session + FastAPI 依赖注入"""
from sqlmodel import SQLModel, Session, create_engine

# SQLite 数据库文件（相对项目根目录）
DATABASE_URL = "sqlite:///./todo.db"

# connect_args 是 SQLite 多线程访问必需的
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    """启动时调用：根据 SQLModel 模型自动建表"""
    SQLModel.metadata.create_all(bind=engine)


def get_session():
    """FastAPI 依赖：为每个请求提供独立 Session，用完自动关闭"""
    with Session(engine) as session:
        yield session
