"""
ETF 策略服务 - FastAPI 后端
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from etf_config_store import load_configs, get_config_by_id, update_config, create_config, delete_config
import os

app = FastAPI(title="ETF 策略服务", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== 数据模型 ==============

class EtfConfigBase(BaseModel):
    code: str
    name: str
    market: str
    isActive: bool = True


class EtfConfigCreate(EtfConfigBase):
    pass


class EtfConfigUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    market: Optional[str] = None
    isActive: Optional[bool] = None


class EtfConfigResponse(EtfConfigBase):
    id: int
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    class Config:
        from_attributes = True


# ============== ETF 配置管理接口 ==============

@app.get("/api/etf-config", response_model=list[EtfConfigResponse])
def get_etf_configs():
    """获取所有 ETF 配置"""
    return load_configs()


@app.get("/api/etf-config/{id}", response_model=EtfConfigResponse)
def get_etf_config(id: int):
    """获取单个 ETF 配置"""
    config = get_config_by_id(id)
    if not config:
        raise HTTPException(status_code=404, detail="ETF 配置不存在")
    return config


@app.post("/api/etf-config", response_model=EtfConfigResponse, status_code=201)
def create_etf_config(config: EtfConfigCreate):
    """创建 ETF 配置"""
    return create_config(config.model_dump())


@app.patch("/api/etf-config/{id}", response_model=EtfConfigResponse)
def update_etf_config(id: int, config: EtfConfigUpdate):
    """更新 ETF 配置"""
    updated = update_config(id, config.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="ETF 配置不存在")
    return updated


@app.delete("/api/etf-config/{id}", status_code=204)
def delete_etf_config(id: int):
    """删除 ETF 配置"""
    if not delete_config(id):
        raise HTTPException(status_code=404, detail="ETF 配置不存在")
    return None


# ============== 健康检查 ==============

@app.get("/api/health")
def health_check():
    """健康检查"""
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
