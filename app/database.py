import os
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. 优先读取云端注入的 DATABASE_URL (Neon 提供的)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if SQLALCHEMY_DATABASE_URL:
    print("🚀 正在连接 Neon PostgreSQL 云数据库...")
    # 核心修复：兼容处理不同格式的 URL，并强制指定 psycopg2 驱动
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

    engine = create_engine(SQLALCHEMY_DATABASE_URL)
else:
    # 2. 本地开发环境回退到 SQLite
    print("💻 正在连接本地 SQLite 数据库...")
    BASE_DIR = Path(__file__).resolve().parent.parent
    DB_PATH = BASE_DIR / "xinshangquan.db"
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Resource(Base):
    __tablename__ = "resources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True)
    industry = Column(String(50))
    region = Column(String(50))
    resource_type = Column(String(50))
    description = Column(Text)
    is_vip = Column(Boolean, default=False)


class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(String(50))
    resource_name = Column(String(100))
    client_name = Column(String(50))
    contact_info = Column(String(100))
    message = Column(Text)


try:
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表初始化完成")
except Exception as e:
    print(f"❌ 数据库初始化失败: {e}")