import sys
import traceback
import os
import requests
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Header, File, UploadFile
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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"],
                   allow_headers=["*"])
workflow_app = build_graph()

ADMIN_PASSWORD = "xinghuo2026"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ================= 模型定义 =================
class ResourceCreate(BaseModel):
    name: str
    industry: str
    region: str
    resource_type: str
    description: str
    is_vip: bool = False
    contact_name: str = ""
    contact_phone: str = ""


class ResourceUpdate(BaseModel):
    name: str
    industry: str
    region: str
    resource_type: str
    description: str
    is_vip: bool
    contact_name: str = ""
    contact_phone: str = ""


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


class LeadUpdate(BaseModel):
    client_name: str
    contact_info: str
    address: str = ""
    message: str = ""


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
    address: str = ""
    message: str = ""


class LoginRequest(BaseModel):
    password: str


# ================= 接口 =================
@app.post("/api/admin/login")
def admin_login(req: LoginRequest):
    if req.password == ADMIN_PASSWORD: return {"token": ADMIN_PASSWORD}
    raise HTTPException(status_code=401, detail="密码错误")


@app.post("/api/resources")
def create_resource(resource: ResourceCreate, db: Session = Depends(get_db)):
    db_resource = Resource(**resource.model_dump())
    db.add(db_resource);
    db.commit();
    db.refresh(db_resource)
    prefix = get_prefix(db_resource.industry)
    all_res = db.query(Resource).filter(Resource.resource_code.isnot(None)).all()
    max_num = 0
    for r in all_res:
        code_str = r.resource_code
        if len(code_str) > 1 and code_str[1:].isdigit():
            num = int(code_str[1:])
            if not (950 <= num <= 999) and num > max_num: max_num = num
    db_resource.resource_code = f"{prefix}{max_num + 1:04d}"
    db.commit();
    sync_resources_to_vector_db()
    return {"message": "资源发布成功"}


@app.get("/api/resources")
def get_resources(db: Session = Depends(get_db)):
    resources = db.query(Resource).order_by(Resource.is_vip.desc(), Resource.id.desc()).all()
    return {"resources": [
        {"id": r.id, "resource_code": r.resource_code or f"X{r.id:04d}", "name": r.name, "industry": r.industry,
         "region": r.region, "resource_type": r.resource_type, "description": r.description, "is_vip": r.is_vip,
         "contact_name": r.contact_name or "", "contact_phone": r.contact_phone or ""} for r in resources]}


@app.put("/api/resources/{resource_id}")
def update_resource(resource_id: int, resource: ResourceUpdate, db: Session = Depends(get_db)):
    db_resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not db_resource: raise HTTPException(status_code=404)
    for k, v in resource.model_dump().items(): setattr(db_resource, k, v)
    db.commit();
    sync_resources_to_vector_db()
    return {"message": "更新成功"}


@app.delete("/api/resources/{resource_id}")
def delete_resource(resource_id: int, db: Session = Depends(get_db)):
    db.query(Resource).filter(Resource.id == resource_id).delete()
    db.commit();
    sync_resources_to_vector_db()
    return {"message": "删除成功"}


@app.post("/api/resources/batch_delete")
def batch_delete_resources(data: BatchIds, db: Session = Depends(get_db)):
    db.query(Resource).filter(Resource.id.in_(data.ids)).delete(synchronize_session=False)
    db.commit();
    sync_resources_to_vector_db()
    return {"message": "批量删除成功"}


@app.post("/api/resources/batch_vip")
def batch_update_vip(data: BatchIds, is_vip: bool, db: Session = Depends(get_db)):
    db.query(Resource).filter(Resource.id.in_(data.ids)).update({Resource.is_vip: is_vip}, synchronize_session=False)
    db.commit();
    sync_resources_to_vector_db()
    return {"message": "批量更新成功"}


@app.post("/api/match", response_model=MatchResponse)
async def match_requirement(req: MatchRequest):
    if not req.requirement.strip(): raise HTTPException(status_code=400)
    try:
        init_state = {"raw_requirement": req.requirement, "match_round": 0, "candidates": [], "final_status": "pending"}
        result = workflow_app.invoke(init_state)
        if result["final_status"] == "rejected":
            msg = "您的需求包含违规信息，已被安全系统拦截。"
        elif result["final_status"] == "exhausted":
            msg = "暂未找到合适的匹配资源。"
        elif result["final_status"] == "matched":
            msg = f"成功为您匹配到 {len(result['candidates'])} 个潜在合作伙伴！"
        else:
            msg = "处理异常"
        return MatchResponse(status=result["final_status"], message=msg, data=result)
    except Exception as e:
        traceback.print_exc();
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/leads")
def create_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    db_lead = Lead(**lead.model_dump());
    db.add(db_lead);
    db.commit()
    return {"message": "提交成功"}


@app.get("/api/leads")
def get_leads(db: Session = Depends(get_db)):
    leads = db.query(Lead).order_by(Lead.id.desc()).all()
    return {"leads": [
        {"id": l.id, "resource_id": l.resource_id, "resource_name": l.resource_name, "client_name": l.client_name,
         "contact_info": l.contact_info, "address": l.address or "", "message": l.message} for l in leads]}


# 🌟 编辑线索接口
@app.put("/api/leads/{lead_id}")
def update_lead(lead_id: int, lead: LeadUpdate, db: Session = Depends(get_db)):
    db_lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not db_lead: raise HTTPException(status_code=404)
    for k, v in lead.model_dump().items(): setattr(db_lead, k, v)
    db.commit()
    return {"message": "线索更新成功"}


@app.get("/api/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    return {"total_resources": db.query(Resource).count(), "total_leads": db.query(Lead).count(),
            "total_vip": db.query(Resource).filter(Resource.is_vip == True).count()}


# ================= 大客户 =================
@app.get("/api/vips")
def get_active_vips(db: Session = Depends(get_db)):
    vips = db.query(VipClient).filter(VipClient.is_active == True).order_by(VipClient.sort_order.desc()).all()
    return {"vips": [{"id": v.id, "title": v.title, "banner_url": v.banner_url, "slogan": v.slogan} for v in vips]}


@app.get("/api/vips/{vip_id}")
def get_vip_detail(vip_id: int, db: Session = Depends(get_db)):
    v = db.query(VipClient).filter(VipClient.id == vip_id).first()
    if not v: raise HTTPException(status_code=404)
    v.view_count = (v.view_count or 0) + 1;
    db.commit()
    return {"id": v.id, "title": v.title, "banner_url": v.banner_url, "slogan": v.slogan, "intro": v.intro,
            "gallery_urls": v.gallery_urls, "cases": v.cases, "phone": v.phone, "wechat": v.wechat,
            "ext_link": v.ext_link}


@app.get("/api/admin/vips")
def get_all_vips(db: Session = Depends(get_db)):
    vips = db.query(VipClient).order_by(VipClient.sort_order.desc()).all()
    return {"vips": [{"id": v.id, "title": v.title, "banner_url": v.banner_url, "is_active": v.is_active,
                      "view_count": v.view_count or 0, "slogan": v.slogan or "", "intro": v.intro or "",
                      "gallery_urls": v.gallery_urls or "", "cases": v.cases or "", "phone": v.phone or "",
                      "wechat": v.wechat or "", "ext_link": v.ext_link or ""} for v in vips]}


@app.post("/api/admin/vips")
def create_vip(vip: VipClientCreate, db: Session = Depends(get_db)):
    db_vip = VipClient(**vip.model_dump());
    db.add(db_vip);
    db.commit();
    db.refresh(db_vip)
    return {"message": "发布成功", "id": db_vip.id}


# 🌟 编辑大客户接口
@app.put("/api/admin/vips/{vip_id}")
def update_vip(vip_id: int, vip: VipClientCreate, db: Session = Depends(get_db)):
    db_vip = db.query(VipClient).filter(VipClient.id == vip_id).first()
    if not db_vip: raise HTTPException(status_code=404)
    for k, v in vip.model_dump().items(): setattr(db_vip, k, v)
    db.commit()
    return {"message": "更新成功"}


@app.delete("/api/admin/vips/{vip_id}")
def delete_vip(vip_id: int, db: Session = Depends(get_db)):
    db.query(VipClient).filter(VipClient.id == vip_id).delete();
    db.commit()
    return {"message": "删除成功"}


@app.put("/api/admin/vips/{vip_id}/toggle")
def toggle_vip(vip_id: int, db: Session = Depends(get_db)):
    v = db.query(VipClient).filter(VipClient.id == vip_id).first()
    if v: v.is_active = not v.is_active; db.commit()
    return {"message": "状态已更新"}


@app.get("/api/regions")
def get_regions(): return {"regions": REGIONS_DATA, "cities": CORE_CITIES}


@app.get("/")
def root(): return {"message": "星火引力 API 正在运行"}


# ==========================================
# 🌟 蜜蜂图床上传接口
# ==========================================
BEEIMG_TOKEN = os.getenv("BEEIMG_TOKEN", "")
BEEIMG_API_URL = "https://www.beeimg.cn/api/v2/upload"


@app.post("/api/admin/upload")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="只允许上传图片文件")

    if not BEEIMG_TOKEN:
        raise HTTPException(status_code=500, detail="后端未配置 BEEIMG_TOKEN")

    file_content = await file.read()

    headers = {
        "Authorization": f"Bearer {BEEIMG_TOKEN}",
        "Accept": "application/json"
    }

    # 🌟 把你刚才抓包看到的真实数字填在这里，比如 "2"
    data = {
            "storage_id":   17
    }

    files = {"file": (file.filename, file_content, file.content_type)}

    try:
        response = requests.post(BEEIMG_API_URL, files=files, data=data, headers=headers, timeout=30)

        # 🌟 关键修复：先尝试解析 JSON，如果图床返回了报错，就把报错完整打印出来
        try:
            res_json = response.json()
        except ValueError:
            # 如果返回的不是 JSON（比如 500 网页），直接抛出图床的原始报错文本
            raise HTTPException(status_code=500, detail=f"图床返回异常，无法解析: {response.text}")

        if response.status_code == 200 and res_json.get("status") == "success":
            return {"url": res_json["data"]["public_url"]}
        else:
            # 把图床具体的报错信息（比如缺什么参数）直接弹给前端
            error_msg = res_json.get("message", "未知错误")
            raise HTTPException(status_code=500, detail=f"图床报错: {error_msg}")

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"连接图床网络异常: {str(e)}")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"系统异常: {str(e)}")