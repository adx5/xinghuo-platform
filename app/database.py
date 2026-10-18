import os
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker

# 导入数据
from app.seed_data import INITIAL_RESOURCES

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if SQLALCHEMY_DATABASE_URL:
    print("🚀 正在连接 Neon PostgreSQL 云数据库...")
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
else:
    print("💻 正在连接本地 SQLite 数据库...")
    BASE_DIR = Path(__file__).resolve().parent.parent
    DB_PATH = BASE_DIR / "xinshangquan.db"
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Resource(Base):
    __tablename__ = "resources"
    id = Column(Integer, primary_key=True, index=True)
    resource_code = Column(String(20), unique=True, index=True, nullable=True)
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
    # 自动检测并添加 resource_code 字段（兼容老数据库）
    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT resource_code FROM resources LIMIT 1"))
        except Exception:
            print("🔧 检测到旧数据库，正在添加 resource_code 字段...")
            conn.execute(text("ALTER TABLE resources ADD COLUMN resource_code VARCHAR(20)"))
            conn.commit()
    print("✅ 数据库表初始化完成")
except Exception as e:
    print(f"❌ 数据库初始化失败: {e}")


def get_prefix(industry):
    if any(k in industry for k in ["本地", "餐饮", "生活"]): return "L"
    if any(k in industry for k in ["传媒", "广告", "媒体"]): return "M"
    if any(k in industry for k in ["汽车", "新能源"]): return "C"
    if any(k in industry for k in ["食品", "快消", "酒水"]): return "F"
    if any(k in industry for k in ["金融", "投资", "财税"]): return "I"
    if any(k in industry for k in ["农业", "农产品"]): return "A"
    if any(k in industry for k in ["技术", "外包", "IT"]): return "T"
    if any(k in industry for k in ["企业", "营销", "咨询"]): return "B"
    return "X"


def seed_initial_data():
    db = SessionLocal()
    try:
        current_count = db.query(Resource).count()

        # 如果没数据，引用外部文件里的 30 条数据进行播种
        if current_count == 0:
            print("🌱 检测到数据库为空，正在注入资源...")
            for res_data in INITIAL_RESOURCES:
                db.add(Resource(**res_data))
            db.commit()
            current_count = db.query(Resource).count()

        # 检查是否有资源缺少 resource_code，自动补齐
        missing_code = db.query(Resource).filter(Resource.resource_code == None).all()
        if missing_code:
            print(f"🔧 正在为 {len(missing_code)} 条历史资源补齐编码...")
            for res in missing_code:
                prefix = get_prefix(res.industry or "未知")
                res.resource_code = f"{prefix}{res.id:04d}"
            db.commit()
            print("✅ 历史数据编码补齐完成！")

    except Exception as e:
        print(f"❌ 数据操作失败: {e}")
    finally:
        db.close()


seed_initial_data()