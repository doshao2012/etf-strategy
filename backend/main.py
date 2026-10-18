"""
ETF 策略服务 - FastAPI 后端
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from etf_config_store import load_configs, get_config_by_id, update_config, create_config, delete_config
import os
import sys
import threading
import time

_BOOT_TS = time.time()

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
    threading.Thread(target=_start_warmup, daemon=True).start()


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

# 注意：这里**不做结果缓存**。策略信号直接决定买卖，必须基于最新实时价计算。
# 性能问题改由"进程预热"解决：Python 冷启动 + 导入 pandas/numpy 约 1.5~2 秒，
# 这块固定开销与数据新鲜度无关，可通过常驻 worker 摊掉。
# 详见 scripts/worker_pool.py。


def _log(msg):
    """统一日志出口：带时间戳与线程名，方便和多 worker 的日志对齐。"""
    import time as _t
    print(f"[{_t.strftime('%H:%M:%S')}][{threading.current_thread().name}] {msg}", flush=True)


def _run_script(script_name, args=None, timeout=60):
    """执行策略脚本并解析 JSON 输出。

    优先走常驻 worker 池：解释器与 pandas/numpy 早已加载，单次开销几十毫秒，
    但**每次都真实执行计算、真实读取实时价**，不做任何结果缓存。
    worker 不可用时回退到子进程，保证功能不缺失。
    """
    import json as _json
    import time as _t
    t0 = _t.time()
    try:
        from scripts.worker_pool import run_script
        out = run_script(script_name, args or [], timeout=timeout)
        el = _t.time() - t0
        if out.get('ok'):
            src = out.get('via', '?')
            _log(f"[脚本] {script_name} {el:.3f}s via={src}")
            return _json.loads(out['stdout'])
        _log(f"[脚本×] {script_name} {el:.3f}s via={out.get('via','?')} "
             f"err={(out.get('stderr') or '')[:300]}")
        return {"code": 500, "message": "计算失败", "error": (out.get('stderr') or '')[:2000]}
    except Exception as e:
        _log(f"[池×] {script_name} 不可用，回退子进程: {e}")
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "scripts", script_name)
        r = subprocess.run(
            ["python3", script] + [str(a) for a in (args or [])],
            capture_output=True, text=True, timeout=timeout
        )
        _log(f"[脚本/子进程] {script_name} {_t.time()-t0:.3f}s rc={r.returncode}")
        if r.returncode != 0:
            return {"code": 500, "message": "计算失败", "error": r.stderr}
        return _json.loads(r.stdout)


def _start_warmup():
    """启动预热入口：等策略函数都定义好后，再交给 _warmup_loop 持续保活。"""
    _warmup_loop([
        ('etf-rotation', _compute_etf_rotation),
        ('ma200-trend', _compute_ma200_trend),
        ('mean-reversion', _compute_mean_reversion),
        ('oversold', _compute_oversold),
    ])


def _warmup_loop(jobs, rounds=3):
    """后台预热/保活：让**每一个** worker 都先跑过一遍，全部进入热态。

    只预热进程，**不缓存结果** —— 用户每次请求仍会真实计算并读取最新实时价。

    为什么要跑 rounds 轮：池里的 worker 是多个独立进程，只跑一遍只有其中一个
    变成热的；其余几个仍要在用户请求时才导入 pandas/numpy（实测 0.6~0.8s）。
    轮数取 3（略大于常驻数量），保证启动后每个 worker 都被摸过一遍。
    """
    import time as _t
    _t.sleep(2)
    first = True
    while True:
        n = rounds if first else 1
        for _ in range(n):
            for name, fn in jobs:
                try:
                    t0 = _t.time()
                    fn()
                    print(f"[预热] {name} {_t.time()-t0:.2f}s", flush=True)
                except Exception as e:
                    print(f"[预热] {name} 异常: {e}", flush=True)
        first = False
        _t.sleep(300)



@app.get("/api/strategy/etf-rotation")
def get_etf_rotation_strategy():
    """获取 ETF 轮动策略（实时计算，结果不缓存）"""
    return _trace("etf-rotation", _compute_etf_rotation)


def _compute_etf_rotation():
    try:
        # 动量计算脚本自己会读 history_cache.json（按天缓存），
        # 实时价也由它用腾讯批量接口现拉，不再需要额外的预取脚本。
        # 原来前置的 fetch_market_data_from_db.py 硬编码了旧项目路径
        # （/app/server/...），产出的 etf-real-data.config.ts 无人引用，
        # 却让每次请求多跑一个进程，已移除。
        python_result = _run_script("calculate_momentum_joinquant.py", ["25", "0", "0.97"])
        if python_result.get("code") != 200:
            return python_result

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
    """获取超跌策略（实时计算，结果不缓存）"""
    return _trace("oversold", _compute_oversold)


def _compute_oversold():
    try:
        return _run_script("calculate_oversold_strategy.py", [])
    except Exception as e:
        return {"code": 500, "message": str(e)}


@app.get("/api/strategy/mean-reversion")
def get_mean_reversion_strategy():
    """获取均值回归策略（实时计算，结果不缓存）"""
    return _trace("mean-reversion", _compute_mean_reversion)


def _compute_mean_reversion():
    try:
        return _run_script("calculate_mean_reversion.py", [])
    except Exception as e:
        return {"code": 500, "message": str(e)}


@app.get("/api/strategy/ma200-trend")
def get_ma200_trend_strategy():
    """获取美股 QQQ/TQQQ 三轨 MA200 策略（实时计算，结果不缓存）"""
    return _trace("ma200-trend", lambda: _compute_ma200_trend())


def _compute_ma200_trend():
    try:
        return _run_script("calculate_ma200_trend.py", timeout=30)
    except Exception as e:
        return {"code": 500, "message": str(e)}


def _trace(name, fn):
    """记录单个策略接口的服务端耗时，并在响应头回传（X-Server-Cost）。

    前端可在浏览器 Network 面板直接看到这个头：
    总耗时 - X-Server-Cost = 网络 + Next 转发 + 渲染，一眼就能分清是哪一段慢。
    """
    import time as _t
    from fastapi.responses import JSONResponse
    rss0 = _rss_mb()
    t0 = _t.time()
    _log(f"[请求→] {name}")
    result = fn()
    el = _t.time() - t0
    rss1 = _rss_mb()
    ok = isinstance(result, dict) and result.get('code') == 200
    _log(f"[请求←] {name} 服务端 {el:.3f}s ok={ok} rss={rss1:.0f}MB(Δ{rss1-rss0:+.0f})")
    resp = JSONResponse(content=result)
    resp.headers['X-Server-Cost'] = f'{el:.3f}'
    return resp


def _rss_mb():
    """当前进程常驻内存（MB），用于观察容器是否贴着内存上限。"""
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024
    except Exception:
        return 0.0


# ============== 健康检查 ==============

@app.get("/api/health")
def health_check():
    """健康检查"""
    from datetime import datetime
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/debug/perf")
def debug_perf():
    """线上体检：把 worker 池的实际状态摊开，用来判断"5 秒"卡在哪一层。

    部署后直接 curl 这个接口即可，不需要 SSH 进容器。
    """
    import time as _t
    out = {
        'backend': {
            'pid': os.getpid(),
            'rssMB': round(_rss_mb(), 1),
            'uptimeSec': round(_t.time() - _BOOT_TS, 1),
            'python': sys.version.split()[0],
            'cpuCount': os.cpu_count(),
        },
        'workerPool': {},
        'probe': {},
    }
    try:
        from scripts.worker_pool import get_pool
        p = get_pool()
        alive = [w for w in p.pool if w.alive()]
        out['workerPool'] = {
            'poolLen': len(p.pool),
            'alive': len(alive),
            'size': p.size,
            'max': p.max_size,
            'workers': [{'pid': w.proc.pid, 'alive': w.alive(),
                         'busy': w.lock.locked()} for w in p.pool],
        }
    except Exception as e:
        out['workerPool'] = {'error': repr(e)}

    # 实测一次 MA200：走池子还是重建，耗时多少
    t0 = _t.time()
    try:
        from scripts.worker_pool import run_script
        r = run_script('calculate_ma200_trend.py', [], timeout=30)
        out['probe'] = {
            'script': 'calculate_ma200_trend.py',
            'ok': r.get('ok'),
            'via': r.get('via'),
            'poolElapsed': round(_t.time() - t0, 3),
            'bytes': len(r.get('stdout') or ''),
        }
    except Exception as e:
        out['probe'] = {'error': repr(e), 'elapsed': round(_t.time() - t0, 3)}

    # 数据源直连耗时（区分本地慢还是外网慢）
    for label, url, hdr in [
        ('sina实时', 'https://hq.sinajs.cn/list=gb_qqq,gb_tqqq',
         {'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'}),
    ]:
        t0 = _t.time()
        try:
            import requests
            requests.get(url, headers=hdr, timeout=(3, 8))
            out['probe'][label] = round(_t.time() - t0, 3)
        except Exception as e:
            out['probe'][label] = f'fail {e}'

    return out


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
