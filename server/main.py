"""
ETF 策略服务 - FastAPI 后端
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
from datetime import datetime

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

# Railway 持久化存储路径
DB_PATH = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/app/server") + "/database.sqlite"


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


# ============== 数据库辅助函数 ==============

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_config(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "market": row["market"],
        "isActive": bool(row["isActive"]),
        "createdAt": row["createdAt"] if "createdAt" in row.keys() else None,
        "updatedAt": row["updatedAt"] if "updatedAt" in row.keys() else None,
    }


# ============== ETF 配置管理接口 ==============

@app.get("/api/etf-config", response_model=list[EtfConfigResponse])
def get_etf_configs():
    """获取所有 ETF 配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM etf_config ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [row_to_config(row) for row in rows]


@app.get("/api/etf-config/{id}", response_model=EtfConfigResponse)
def get_etf_config(id: int):
    """获取单个 ETF 配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM etf_config WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="ETF 配置不存在")
    return row_to_config(row)


@app.post("/api/etf-config", response_model=EtfConfigResponse, status_code=201)
def create_etf_config(config: EtfConfigCreate):
    """创建 ETF 配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cursor.execute(
            """INSERT INTO etf_config (code, name, market, isActive, createdAt, updatedAt)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (config.code, config.name, config.market, 1 if config.isActive else 0, now, now),
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM etf_config WHERE id = ?", (new_id,))
        row = cursor.fetchone()
        conn.close()
        return row_to_config(row)
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="ETF 代码已存在")


@app.patch("/api/etf-config/{id}", response_model=EtfConfigResponse)
def update_etf_config(id: int, config: EtfConfigUpdate):
    """更新 ETF 配置"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查是否存在
    cursor.execute("SELECT * FROM etf_config WHERE id = ?", (id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="ETF 配置不存在")

    # 构建更新语句
    updates = []
    values = []
    if config.code is not None:
        updates.append("code = ?")
        values.append(config.code)
    if config.name is not None:
        updates.append("name = ?")
        values.append(config.name)
    if config.market is not None:
        updates.append("market = ?")
        values.append(config.market)
    if config.isActive is not None:
        updates.append("isActive = ?")
        values.append(1 if config.isActive else 0)

    if updates:
        updates.append("updatedAt = ?")
        values.append(datetime.now().isoformat())
        values.append(id)
        sql = f"UPDATE etf_config SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(sql, values)
        conn.commit()

    # 返回更新后的数据
    cursor.execute("SELECT * FROM etf_config WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    return row_to_config(row)


@app.delete("/api/etf-config/{id}", status_code=204)
def delete_etf_config(id: int):
    """删除 ETF 配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM etf_config WHERE id = ?", (id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="ETF 配置不存在")
    cursor.execute("DELETE FROM etf_config WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return None


# ============== 健康检查 ==============

@app.get("/api/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
