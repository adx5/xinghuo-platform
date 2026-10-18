import os
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from app.seed_data import INITIAL_RESOURCES

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if SQLALCHEMY_DATABASE_URL:
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DB_PATH = BASE_DIR / "xinshangquan.db"
    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

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

# 🌟 新增：大客户微官网表
class VipClient(Base):
    __tablename__ = "vip_clients"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), comment="公司名称")
    banner_url = Column(Text, comment="轮播图/首屏大图链接(1920x600)")
    slogan = Column(String(200), comment="企业Slogan/口号")
    intro = Column(Text, comment="企业实力介绍")
    gallery_urls = Column(Text, comment="产品图集，多张用逗号分隔")
    cases = Column(Text, comment="合作案例，多条用逗号分隔")
    phone = Column(String(50), comment="联系电话")
    wechat = Column(String(50), comment="微信号")
    ext_link = Column(String(200), comment="官网/抖音链接")
    is_active = Column(Boolean, default=True, comment="是否上架展示")
    sort_order = Column(Integer, default=0, comment="排序权重")

try:
    Base.metadata.create_all(bind=engine)
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
        if db.query(Resource).count() == 0:
            for res_data in INITIAL_RESOURCES:
                db.add(Resource(**res_data))
            db.commit()
    finally:
        db.close()

seed_initial_data()