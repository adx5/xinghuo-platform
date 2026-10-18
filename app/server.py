import sys
import traceback
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import build_graph
from app.database import SessionLocal, Resource, Lead, get_prefix
from app.vector_store import sync_resources_to_vector_db

app = FastAPI(title="星火引力 - 智能商务撮合 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"],
                   allow_headers=["*"])
workflow_app = build_graph()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Pydantic 模型 ---
class ResourceCreate(BaseModel):
    name: str
    industry: str
    region: str
    resource_type: str
    description: str
    is_vip: bool = False


class ResourceUpdate(BaseModel):
    name: str
    industry: str
    region: str
    resource_type: str
    description: str
    is_vip: bool


class BatchIds(BaseModel):
    ids: List[int]


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
    message: str = ""


# --- 资源管理接口 ---

@app.post("/api/resources")
def create_resource(resource: ResourceCreate, db: Session = Depends(get_db)):
    db_resource = Resource(**resource.model_dump())
    db.add(db_resource)
    db.commit()
    db.refresh(db_resource)

    prefix = get_prefix(db_resource.industry)
    all_res = db.query(Resource).filter(Resource.resource_code.isnot(None)).all()
    max_num = 0
    for r in all_res:
        code_str = r.resource_code
        if len(code_str) > 1 and code_str[1:].isdigit():
            num = int(code_str[1:])
            if not (950 <= num <= 999) and num > max_num:
                max_num = num

    code_num = max_num + 1
    db_resource.resource_code = f"{prefix}{code_num:04d}"
    db.commit()
    sync_resources_to_vector_db()
    return {"message": "资源发布成功", "resource_id": db_resource.id, "resource_code": db_resource.resource_code}


@app.get("/api/resources")
def get_resources(db: Session = Depends(get_db)):
    resources = db.query(Resource).order_by(Resource.is_vip.desc(), Resource.id.desc()).all()
    return {"resources": [
        {
            "id": r.id,
            "resource_code": r.resource_code or f"X{r.id:04d}",
            "name": r.name,
            "industry": r.industry,
            "region": r.region,
            "resource_type": r.resource_type,
            "description": r.description,
            "is_vip": r.is_vip
        } for r in resources
    ]}


@app.put("/api/resources/{resource_id}")
def update_resource(resource_id: int, resource: ResourceUpdate, db: Session = Depends(get_db)):
    """编辑资源接口"""
    db_resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not db_resource:
        raise HTTPException(status_code=404, detail="资源不存在")

    db_resource.name = resource.name
    db_resource.industry = resource.industry
    db_resource.region = resource.region
    db_resource.resource_type = resource.resource_type
    db_resource.description = resource.description
    db_resource.is_vip = resource.is_vip
    db.commit()
    sync_resources_to_vector_db()
    return {"message": "资源更新成功"}


@app.delete("/api/resources/{resource_id}")
def delete_resource(resource_id: int, db: Session = Depends(get_db)):
    db_resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not db_resource: raise HTTPException(status_code=404, detail="资源不存在")
    db.delete(db_resource)
    db.commit()
    sync_resources_to_vector_db()
    return {"message": "资源已删除"}


@app.post("/api/resources/batch_delete")
def batch_delete_resources(data: BatchIds, db: Session = Depends(get_db)):
    """批量删除接口"""
    db.query(Resource).filter(Resource.id.in_(data.ids)).delete(synchronize_session=False)
    db.commit()
    sync_resources_to_vector_db()
    return {"message": f"成功删除 {len(data.ids)} 条资源"}


@app.post("/api/resources/batch_vip")
def batch_update_vip(data: BatchIds, is_vip: bool, db: Session = Depends(get_db)):
    """批量更新 VIP 状态接口"""
    db.query(Resource).filter(Resource.id.in_(data.ids)).update({Resource.is_vip: is_vip}, synchronize_session=False)
    db.commit()
    sync_resources_to_vector_db()
    return {"message": f"成功更新 {len(data.ids)} 条资源状态"}


# --- 其他业务接口 ---

@app.post("/api/match", response_model=MatchResponse)
async def match_requirement(req: MatchRequest):
    if not req.requirement.strip(): raise HTTPException(status_code=400, detail="需求内容不能为空")
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
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/leads")
def create_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    db_lead = Lead(**lead.model_dump())
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return {"message": "对接意向提交成功", "lead_id": db_lead.id}


@app.get("/api/leads")
def get_leads(db: Session = Depends(get_db)):
    leads = db.query(Lead).order_by(Lead.id.desc()).all()
    return {"leads": [
        {"id": l.id, "resource_id": l.resource_id, "resource_name": l.resource_name, "client_name": l.client_name,
         "contact_info": l.contact_info, "message": l.message} for l in leads
    ]}


@app.get("/api/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    return {"total_resources": db.query(Resource).count(), "total_leads": db.query(Lead).count(),
            "total_vip": db.query(Resource).filter(Resource.is_vip == True).count()}


@app.get("/")
def root(): return {"message": "星火引力 API 正在运行"}