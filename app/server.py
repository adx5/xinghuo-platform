import sys
import traceback
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import build_graph
from app.database import SessionLocal, Resource, Lead, get_prefix
from app.vector_store import sync_resources_to_vector_db

app = FastAPI(title="星火引力 - 智能商务撮合 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

workflow_app = build_graph()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ResourceCreate(BaseModel):
    name: str
    industry: str
    region: str
    resource_type: str
    description: str
    is_vip: bool = False

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


@app.post("/api/resources")
def create_resource(resource: ResourceCreate, db: Session = Depends(get_db)):
    db_resource = Resource(**resource.model_dump())
    db.add(db_resource)
    db.commit()
    db.refresh(db_resource)

    # --- 核心修改开始 ---
    prefix = get_prefix(db_resource.industry)

    # 1-30 是假数据，映射到 950-979 区间
    # 31 之后是真实数据，从 0001 开始
    if 1 <= db_resource.id <= 30:
        code_num = 949 + db_resource.id  # 1变950，30变979
    else:
        code_num = db_resource.id - 30  # 31变001，32变002...

    db_resource.resource_code = f"{prefix}{code_num:04d}"
    # --- 核心修改结束 ---

    db.commit()

    sync_resources_to_vector_db()
    return {"message": "资源发布成功", "resource_id": db_resource.id, "resource_code": db_resource.resource_code}

@app.post("/api/match", response_model=MatchResponse)
async def match_requirement(req: MatchRequest):
    if not req.requirement.strip():
        raise HTTPException(status_code=400, detail="需求内容不能为空")
    try:
        init_state = {"raw_requirement": req.requirement, "match_round": 0, "candidates": [], "final_status": "pending"}
        result = workflow_app.invoke(init_state)

        if result["final_status"] == "rejected": msg = "您的需求包含违规信息，已被安全系统拦截。"
        elif result["final_status"] == "exhausted": msg = "暂未找到合适的匹配资源。"
        elif result["final_status"] == "matched": msg = f"成功为您匹配到 {len(result['candidates'])} 个潜在合作伙伴！"
        else: msg = "处理异常"

        return MatchResponse(status=result["final_status"], message=msg, data=result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/resources")
def get_resources(db: Session = Depends(get_db)):
    resources = db.query(Resource).order_by(Resource.is_vip.desc(), Resource.id.desc()).all()
    return {"resources": [
        {
            "id": r.id,
            "resource_code": r.resource_code or f"X{r.id:04d}", # 兜底显示
            "name": r.name,
            "industry": r.industry,
            "region": r.region,
            "resource_type": r.resource_type,
            "description": r.description,
            "is_vip": r.is_vip
        } for r in resources
    ]}


@app.post("/api/leads")
def create_lead(lead: LeadCreate, db: Session = Depends(get_db)):
    db_lead = Lead(**lead.model_dump())
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return {"message": "对接意向提交成功", "lead_id": db_lead.id}


@app.get("/api/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    total_resources = db.query(Resource).count()
    total_leads = db.query(Lead).count()
    total_vip = db.query(Resource).filter(Resource.is_vip == True).count()
    return {"total_resources": total_resources, "total_leads": total_leads, "total_vip": total_vip}

@app.delete("/api/resources/{resource_id}")
def delete_resource(resource_id: int, db: Session = Depends(get_db)):
    db_resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not db_resource: raise HTTPException(status_code=404, detail="资源不存在")
    db.delete(db_resource)
    db.commit()
    sync_resources_to_vector_db()
    return {"message": "资源已删除"}

@app.get("/")
def root(): return {"message": "星火引力 API 正在运行"}