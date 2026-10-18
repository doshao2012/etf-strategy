"""
ETF 策略服务 - FastAPI 后端
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from etf_config_store import load_configs, get_config_by_id, update_config, create_config, delete_config
import os
import threading
import time

app = FastAPI(title="ETF 策略服务", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _qqq_history_daemon():
    """后台守护线程：定期补齐 QQQ/TQQQ 历史日线。

    与轮动策略的"按天缓存"一致，每天只需成功一次；这里每 6 小时检查一次，
    即使当天某次失败，后续也会自动重试，无需人工干预。
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
    while True:
        try:
            from update_qqq_history import update as update_history
            r = update_history()
            if r.get('error'):
                print(f"[历史同步] 失败: {r['error']}", flush=True)
            elif r.get('updated'):
                print(f"[历史同步] 新增 {r['added']} 个交易日，最新 {r['historyUpdated']}", flush=True)
        except Exception as e:
            print(f"[历史同步] 异常: {e}", flush=True)
        time.sleep(6 * 3600)


@app.on_event("startup")
def _start_qqq_history_sync():
    if os.environ.get('DISABLE_HISTORY_SYNC') == '1':
        return
    threading.Thread(target=_qqq_history_daemon, daemon=True).start()
    threading.Thread(target=_warmup_strategies, daemon=True).start()


def _warmup_strategies():
    """启动后预热各策略缓存，然后转入后台定期刷新。

    每个策略都是一次"新起 Python 进程 + 导入 pandas/numpy + 联网"，
    冷启动约 1.5~2 秒。启动时就跑一遍，用户首次打开页面便能命中缓存；
    之后由 _refresh_cache_forever 持续保活，避免缓存过期后撞上冷启动。
    """
    import time as _t
    _t.sleep(2)   # 让 uvicorn 先把服务挂起来
    jobs = [
        ('etf-rotation', _compute_etf_rotation),
        ('ma200-trend', _compute_ma200_trend),
        ('mean-reversion', _compute_mean_reversion),
        ('oversold', _compute_oversold),
    ]
    for name, fn in jobs:
        try:
            t0 = _t.time()
            data = fn()
            if isinstance(data, dict) and data.get('code') == 200:
                _STRATEGY_CACHE[name] = {'ts': _t.time(), 'data': data}
                print(f"[预热] {name} 完成 {_t.time()-t0:.2f}s", flush=True)
            else:
                print(f"[预热] {name} 未成功: {str(data)[:120]}", flush=True)
        except Exception as e:
            print(f"[预热] {name} 异常: {e}", flush=True)
    print("[预热] 全部完成，转入后台定期刷新", flush=True)
    _refresh_cache_forever(jobs)


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


# ============== ETF 策略接口 ==============

# 策略结果缓存：避免"切 tab 就重跑一遍子进程 + 联网"。
# 策略信号按日更新，缓存有效期给得比较宽；后台线程每 REFRESH_INTERVAL 秒
# 主动刷新一次，用户任何时候打开都能命中缓存，不会撞上冷启动。
_STRATEGY_CACHE = {}
STRATEGY_CACHE_TTL = 600        # 缓存视为"可用"的最长时间
REFRESH_INTERVAL = 300          # 后台刷新间隔（秒）


def _cached(key, producer):
    import time as _t
    hit = _STRATEGY_CACHE.get(key)
    now = _t.time()
    if hit and (now - hit['ts']) < STRATEGY_CACHE_TTL:
        data = dict(hit['data'])
        # 标记数据来自缓存，便于排查
        if isinstance(data, dict):
            data['_cached'] = True
            data['_cacheAgeSec'] = round(now - hit['ts'], 1)
        return data
    data = producer()
    if isinstance(data, dict) and data.get('code') == 200:
        _STRATEGY_CACHE[key] = {'ts': now, 'data': data}
    return data


def _refresh_cache_forever(jobs):
    """后台定期刷新策略缓存，保证接口永远命中缓存。

    每个策略跑一次要新起进程并导入 pandas/numpy（约 1.5~2 秒）。
    如果等缓存过期后由用户请求触发，用户就会撞上这段冷启动；
    改为后台主动刷新，用户侧始终是内存读取。
    """
    import time as _t
    while True:
        _t.sleep(REFRESH_INTERVAL)
        for name, fn in jobs:
            try:
                t0 = _t.time()
                data = fn()
                if isinstance(data, dict) and data.get('code') == 200:
                    _STRATEGY_CACHE[name] = {'ts': _t.time(), 'data': data}
                    print(f"[刷新] {name} {_t.time()-t0:.2f}s", flush=True)
            except Exception as e:
                print(f"[刷新] {name} 异常: {e}", flush=True)


@app.get("/api/strategy/etf-rotation")
def get_etf_rotation_strategy():
    """获取 ETF 轮动策略（60 秒内复用缓存，避免重复跑子进程）"""
    return _cached('etf-rotation', _compute_etf_rotation)


def _compute_etf_rotation():
    import subprocess
    import json
    
    try:
        # 获取最新市场数据
        fetch_script = os.path.join(os.path.dirname(__file__), "scripts", "fetch_market_data_from_db.py")
        subprocess.run(["python3", fetch_script], capture_output=True, timeout=60)
        
        # 计算动量得分
        calc_script = os.path.join(os.path.dirname(__file__), "scripts", "calculate_momentum_joinquant.py")
        result = subprocess.run(
            ["python3", calc_script, "25", "0", "0.97"],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode != 0:
            return {"code": 500, "message": "计算失败", "error": result.stderr}
        
        python_result = json.loads(result.stdout)
        
        if not python_result.get("data", {}).get("etfs"):
            return {"code": 500, "message": "未能获取ETF策略数据"}
        
        return {
            "code": 200,
            "data": python_result["data"]
        }
    except Exception as e:
        return {"code": 500, "message": str(e)}


@app.get("/api/strategy/oversold")
def get_oversold_strategy():
    """获取超跌策略（60 秒内复用缓存）"""
    return _cached('oversold', _compute_oversold)


def _compute_oversold():
    import subprocess
    import json

    try:
        script = os.path.join(os.path.dirname(__file__), "scripts", "calculate_oversold_strategy.py")
        result = subprocess.run(
            ["python3", script],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode != 0:
            return {"code": 500, "message": "计算失败", "error": result.stderr}
        
        return json.loads(result.stdout)
    except Exception as e:
        return {"code": 500, "message": str(e)}


@app.get("/api/strategy/mean-reversion")
def get_mean_reversion_strategy():
    """获取均值回归策略（60 秒内复用缓存）"""
    return _cached('mean-reversion', _compute_mean_reversion)


def _compute_mean_reversion():
    import subprocess
    import json

    try:
        script = os.path.join(os.path.dirname(__file__), "scripts", "calculate_mean_reversion.py")
        result = subprocess.run(
            ["python3", script],
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode != 0:
            return {"code": 500, "message": "计算失败", "error": result.stderr}
        
        return json.loads(result.stdout)
    except Exception as e:
        return {"code": 500, "message": str(e)}


@app.get("/api/strategy/ma200-trend")
def get_ma200_trend_strategy():
    """获取美股 QQQ/TQQQ 三轨 MA200 策略（60 秒内复用缓存）"""
    return _cached('ma200-trend', _compute_ma200_trend)


def _compute_ma200_trend():
    import subprocess
    import json

    try:
        script = os.path.join(os.path.dirname(__file__), "scripts", "calculate_ma200_trend.py")
        result = subprocess.run(
            ["python3", script],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            return {"code": 500, "message": "计算失败", "error": result.stderr}

        return json.loads(result.stdout)
    except Exception as e:
        return {"code": 500, "message": str(e)}


# ============== 健康检查 ==============

@app.get("/api/health")
def health_check():
    """健康检查"""
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/data-health")
def data_health():
    """数据新鲜度体检：QQQ 历史日线是否及时更新"""
    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
        from update_qqq_history import update as update_history
        r = update_history(audit_only=True)
        return {"code": 200, "data": r}
    except Exception as e:
        return {"code": 500, "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
