import sys
import traceback
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import build_graph
from app.database import SessionLocal, Resource, Lead, VipClient, get_prefix
from app.vector_store import sync_resources_to_vector_db
from app.region_data import REGIONS_DATA, CORE_CITIES

app = FastAPI(title="星火引力 - 智能商务撮合 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
workflow_app = build_graph()

ADMIN_PASSWORD = "xinghuo2026"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic 模型
class ResourceCreate(BaseModel):
    name: str
    industry: str
    region: str
    resource_type: str
    description: str
    is_vip: bool = False
    contact_name: str = ""   # 🌟 新增
    contact_phone: str = ""  # 🌟 新增

class ResourceUpdate(BaseModel):
    name: str
    industry: str
    region: str
    resource_type: str
    description: str
    is_vip: bool
    contact_name: str = ""   # 🌟 顺手加上
    contact_phone: str = ""  # 🌟 顺手加上

class BatchIds(BaseModel):
    ids: List[int]

class VipClientCreate(BaseModel):
    title: str
    banner_url: str
    slogan: str = ""
    intro: str = ""
    gallery_urls: str = ""
    cases: str = ""
    phone: str = ""
    wechat: str = ""
    ext_link: str = ""
    sort_order: int = 0

class MatchRequest(BaseModel):
    requirement: str
class MatchResponse(BaseModel):
    status: str
    message: str
    data: dict
class LeadCreate(BaseModel):
    resource_id: str
    resource_name: str
    client_name: str
    contact_info: str
    address: str = ""  # 新增
    message: str = ""
class LoginRequest(BaseModel):
    password: str

# ================= 鉴权登录接口 =================
@app.post("/api/admin/login")
def admin_login(req: LoginRequest):
    if req.password == ADMIN_PASSWORD:
        return {"token": ADMIN_PASSWORD}
    raise HTTPException(status_code=401, detail="密码错误")

# ================= 资源接口 =================
@app.post("/api/resources")
def create_resource(resource: ResourceCreate, db: Session = Depends(get_db)):
    db_resource = Resource(**resource.model_dump())
    db.add(db_resource); db.commit(); db.refresh(db_resource)
    prefix = get_prefix(db_resource.industry)
    all_res = db.query(Resource).filter(Resource.resource_code.isnot(None)).all()
    max_num = 0
    for r in all_res:
        code_str = r.resource_code
        if len(code_str) > 1 and code_str[1:].isdigit():
            num = int(code_str[1:])
            if not (950 <= num <= 999) and num > max_num: max_num = num
    db_resource.resource_code = f"{prefix}{max_num + 1:04d}"
    db.commit(); sync_resources_to_vector_db()
    return {"message": "资源发布成功"}

@app.get("/api/resources")
def get_resources(db: Session = Depends(get_db)):
    resources = db.query(Resource).order_by(Resource.is_vip.desc(), Resource.id.desc()).all()
    return {"resources": [{"id": r.id, "resource_code": r.resource_code or f"X{r.id:04d}", "name": r.name, "industry": r.industry, "region": r.region, "resource_type": r.resource_type, "description": r.description, "is_vip": r.is_vip} for r in resources]}

@app.put("/api/resources/{resource_id}")
def update_resource(resource_id: int, resource: ResourceUpdate, db: Session = Depends(get_db)):
    db_resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not db_resource: raise HTTPException(status_code=404)
    for k, v in resource.model_dump().items(): setattr(db_resource, k, v)
    db.commit(); sync_resources_to_vector_db()
    return {"message": "更新成功"}

@app.delete("/api/resources/{resource_id}")
def delete_resource(resource_id: int, db: Session = Depends(get_db)):
    db.query(Resource).filter(Resource.id == resource_id).delete()
    db.commit(); sync_resources_to_vector_db()
    return {"message": "删除成功"}

@app.post("/api/resources/batch_delete")
def batch_delete_resources(data: BatchIds, db: Session = Depends(get_db)):
    db.query(Resource).filter(Resource.id.in_(data.ids)).delete(synchronize_session=False)
    db.commit(); sync_resources_to_vector_db()
    return {"message": "批量删除成功"}

@app.post("/api/resources/batch_vip")
def batch_update_vip(data: BatchIds, is_vip: bool, db: Session = Depends(get_db)):
    db.query(Resource).filter(Resource.id.in_(data.ids)).update({Resource.is_vip: is_vip}, synchronize_session=False)
    db.commit(); sync_resources_to_vector_db()
    return {"message": "批量更新成功"}

# ================= 匹配与线索接口 =================
@app.post("/api/match", response_model=MatchResponse)
async def match_requirement(req: MatchRequest):
    if not req.requirement.strip(): raise HTTPException(status_code=400)
    try:
        init_state = {"raw_requirement": req.requirement, "match_round": 0, "candidates": [], "final_status": "pending"}
        result = workflow_app.invoke(init_state)
        if result["final_status"] == "rejected": msg = "您的需求包含违规信息，已被安全系统拦截。"
        elif result["final_status"] == "exhausted": msg = "暂未找到合适的匹配资源。"
        elif result["final_status"] == "matched": msg = f"成功为您匹配到 {len(result['candidates'])} 个潜在合作伙伴！"
        else: msg = "处理异常"
        return MatchResponse(status=result["final_status"], message=msg, data=result)
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/leads")
def create_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    db_lead = Lead(**lead.model_dump()); db.add(db_lead); db.commit()
    return {"message": "提交成功"}

# 注意：这里补上了 address 字段！
@app.get("/api/leads")
def get_leads(db: Session = Depends(get_db)):
    leads = db.query(Lead).order_by(Lead.id.desc()).all()
    return {"leads": [{"id": l.id, "resource_id": l.resource_id, "resource_name": l.resource_name, "client_name": l.client_name, "contact_info": l.contact_info, "address": l.address or "", "message": l.message} for l in leads]}

@app.get("/api/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    return {"total_resources": db.query(Resource).count(), "total_leads": db.query(Lead).count(), "total_vip": db.query(Resource).filter(Resource.is_vip == True).count()}

# ================= 大客户微官网接口 =================
@app.get("/api/vips")
def get_active_vips(db: Session = Depends(get_db)):
    vips = db.query(VipClient).filter(VipClient.is_active == True).order_by(VipClient.sort_order.desc()).all()
    return {"vips": [{"id": v.id, "title": v.title, "banner_url": v.banner_url} for v in vips]}

@app.get("/api/vips/{vip_id}")
def get_vip_detail(vip_id: int, db: Session = Depends(get_db)):
    v = db.query(VipClient).filter(VipClient.id == vip_id).first()
    if not v: raise HTTPException(status_code=404)
    return {"id": v.id, "title": v.title, "banner_url": v.banner_url, "slogan": v.slogan, "intro": v.intro, "gallery_urls": v.gallery_urls, "cases": v.cases, "phone": v.phone, "wechat": v.wechat, "ext_link": v.ext_link}

@app.get("/api/admin/vips")
def get_all_vips(db: Session = Depends(get_db)):
    vips = db.query(VipClient).order_by(VipClient.sort_order.desc()).all()
    return {"vips": [{"id": v.id, "title": v.title, "banner_url": v.banner_url, "is_active": v.is_active} for v in vips]}

@app.post("/api/admin/vips")
def create_vip(vip: VipClientCreate, db: Session = Depends(get_db)):
    db_vip = VipClient(**vip.model_dump())
    db.add(db_vip); db.commit(); db.refresh(db_vip)
    return {"message": "发布成功", "id": db_vip.id}

@app.delete("/api/admin/vips/{vip_id}")
def delete_vip(vip_id: int, db: Session = Depends(get_db)):
    db.query(VipClient).filter(VipClient.id == vip_id).delete()
    db.commit()
    return {"message": "删除成功"}

@app.put("/api/admin/vips/{vip_id}/toggle")
def toggle_vip(vip_id: int, db: Session = Depends(get_db)):
    v = db.query(VipClient).filter(VipClient.id == vip_id).first()
    if v:
        v.is_active = not v.is_active
        db.commit()
    return {"message": "状态已更新"}

# ================= 地域字典接口 =================
@app.get("/api/regions")
def get_regions():
    return {"regions": REGIONS_DATA, "cities": CORE_CITIES}

@app.get("/")
def root(): return {"message": "星火引力 API 正在运行"}