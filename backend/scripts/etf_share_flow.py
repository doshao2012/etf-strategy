#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 一级市场净申赎监控（份额口径）

为什么单独一个模块：
    成交量/成交额是「二级市场」交易，只能间接猜国家队；份额变动是「一级市场」
    的真实申购赎回，ETF 份额增加 = 有资金通过做市商在场外申购、转手卖出，
    这恰恰是汇金/证金这类大资金进场的标准路径（在二级市场直接买会拉高成本）。
    所以份额净申赎比成交量更有信息量：成交量放大可能是散户/量化，
    份额净增 100 亿则必然是机构一级申赎。

数据源现实约束（2026-11 实测）：
    * 上交所：``fund_etf_scale_sse(date='YYYYMMDD')`` 可按任意历史日期取全市场 ETF 份额，
      实测可回溯到 2026-04 及更早（800~920 只）。→ 可直接算 60 日分位。
    * 深交所：``fund_etf_scale_szse()`` **只能取当日快照**，没有日期参数。
      官方每日披露但接口不提供历史。→ 只能每天抓一次存本地，逐步累积。

    因此本模块的策略是「沪深统一按日累积 + 上交所按需回补」：
      1. 每个交易日把沪深全市场份额快照存进 share_history.json（每天一条，只增不改）
      2. 上交所标的若本地历史不足 60 天，自动按日期回补补齐（一次补齐后长期有效）
      3. 深交所标的只能从首次运行那天开始攒，历史不足时明确标注「已累积 N 天」

净申赎金额口径：
    Δ份额 × 当日单位净值。净值优先用「份额变动日的收盘价」（ETF 净值≈收盘价），
    避免再去拉一份净值序列。得到的是近似申赎金额，方向与量级准确，
    绝对值和基金公司口径会有几个百分点的差异（因申赎按 T 日净值、且有现金替代）。

分位计算：
    net 序列 = 每个交易日的 (份额_t - 份额_{t-1}) × 价格_t
    分位 = 历史 net 序列中 ≤ 今日 net 的比例。用「有符号分位」：
            净申购为正、净赎回为负，分位 95% 表示"申购强度超过历史上 95% 的交易日"。
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARE_FILE = os.path.join(BASE_DIR, 'share_history.json')

# 分位窗口：60 个交易日 ≈ 3 个月。太短（20 日）正常调仓也会冲高，太长（250 日）会稀释近期异动。
PERCENTILE_DAYS = 60
# 少于这么多天就不出分位，只显示净申赎金额
MIN_DAYS_FOR_PCT = 20
# 上交所回补的最大天数（60 个交易日 ≈ 85 个自然日，留缓冲）
BACKFILL_CALENDAR_DAYS = 95
# 当日快照落盘的最小间隔（秒）。同一天内反复请求时不必重复抓。
SNAPSHOT_MIN_INTERVAL = 1800
# 单个交易所网络超时
SSE_TIMEOUT = 40
SZSE_TIMEOUT = 60

_HAVE_AK = None


def _ak():
    """懒加载 akshare。它 import 很慢（约 2s），只在真正需要份额时加载。"""
    global _HAVE_AK
    if _HAVE_AK is None:
        try:
            import warnings
            warnings.filterwarnings('ignore')
            import akshare as ak
            _HAVE_AK = ak
        except Exception as e:
            print(f'[share] akshare 不可用: {e}', file=sys.stderr)
            _HAVE_AK = False
    return _HAVE_AK or None


def _load():
    try:
        with open(SHARE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'days': {}, 'meta': {}}


def _save(payload):
    tmp = SHARE_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, SHARE_FILE)


def _clean_num(v):
    """份额可能是 '1,234,567' 或 1.23e9，统一成 float"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(',', '').strip())
    except Exception:
        return None


# ---------------- 抓取 ----------------

def fetch_sse_snapshot(date_str=None):
    """上交所全市场 ETF 份额。date_str='YYYYMMDD'，None 表示最近披露日。

    重要：akshare 的 fund_etf_scale_sse() 默认参数写死成 '20250115'，
    不带参数调用会拿到一年前的旧数据（而且经常因页面结构变化直接抛 KeyError）。
    所以这里**必须**显式传日期，绝不能用无参调用。

    返回 {纯代码(6位): 份额(份)}，失败返回 {}。
    """
    if not date_str:
        # 没给日期就取最近一个已披露的工作日（份额 T+1 披露，往前找几天）
        for d in _recent_trade_dates(7):
            got = fetch_sse_snapshot(d)
            if got:
                return got
        return {}

    ak = _ak()
    if not ak:
        return {}
    try:
        df = ak.fund_etf_scale_sse(date=date_str)
    except Exception:
        # 非交易日/尚未披露时 akshare 内部会抛 KeyError，属预期，静默跳过
        return {}
    if df is None or len(df) == 0:
        return {}
    if '基金代码' not in df.columns or '基金份额' not in df.columns:
        return {}
    out = {}
    for _, row in df.iterrows():
        code = str(row.get('基金代码', '')).strip().zfill(6)
        sh = _clean_num(row.get('基金份额'))
        if code and sh and sh > 0:
            out[code] = sh
    return out


def fetch_szse_snapshot():
    """深交所全市场 ETF 份额（仅当日快照，无历史）。

    返回 {纯代码(6位): 份额(份)}，失败返回 {}。
    akshare 的实现对 bytes 处理有 bug，这里自己抓 xlsx。
    """
    try:
        import io
        import requests
        import pandas as pd
    except Exception:
        return {}
    url = 'https://fund.szse.cn/api/report/ShowReport'
    params = {'SHOWTYPE': 'xlsx', 'CATALOGID': '1000_lf', 'TABKEY': 'tab1',
              'random': str(time.time())}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                             '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
               'Referer': 'https://fund.szse.cn/'}
    # 深交所站点抖动大，实测经常首次连接就断，多试几次
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=(5, SZSE_TIMEOUT))
            if r.status_code != 200 or len(r.content) < 5000:
                raise RuntimeError(f'HTTP {r.status_code} / {len(r.content)}B')
            df = pd.read_excel(io.BytesIO(r.content), dtype={'基金代码': str})
            out = {}
            for _, row in df.iterrows():
                code = str(row.get('基金代码', '')).strip().zfill(6)
                sh = _clean_num(row.get('当前规模(份)'))
                if code and sh and sh > 0:
                    out[code] = sh
            return out
        except Exception as e:
            if attempt < 2:
                time.sleep(2 + attempt * 2)
                continue
            print(f'[share] 深交所抓取失败: {type(e).__name__}: {e}', file=sys.stderr)
            return {}
    return {}


# ---------------- 累积与回补 ----------------

def _recent_trade_dates(n_days):
    """近 n_days 个自然日里的工作日（跳过周末；节假日由抓取结果为空自然过滤）"""
    out = []
    d = datetime.now()
    for i in range(n_days):
        day = d - timedelta(days=i)
        if day.weekday() < 5:
            out.append(day.strftime('%Y%m%d'))
    return out


def ensure_history(symbols, force_snapshot=False):
    """保证 share_history.json 里有可用的份额序列。

    symbols：本次关心的标的（如 ['sh510300', 'sz159915']），只会为它们所在市场做抓取。
    返回更新后的 payload。
    """
    payload = _load()
    days = payload.setdefault('days', {})
    meta = payload.setdefault('meta', {})

    # 统一日期键格式为 YYYYMMDD（早期版本可能写成 YYYY-MM-DD，这里顺手迁移）
    for k in list(days.keys()):
        if '-' in k:
            days[k.replace('-', '')] = days.pop(k)

    today = datetime.now().strftime('%Y%m%d')
    today_dash = datetime.now().strftime('%Y-%m-%d')

    need_sh = any(s.startswith('sh') for s in symbols)
    need_sz = any(s.startswith('sz') for s in symbols)

    # 1) 当日快照：等价于"把最近几天缺失的交易日补齐"。
    #    份额是 T 日盘后披露、T+1 才可查，所以不限死在"今天"这个键上——
    #    统一用「最近 N 个工作日」逐个探测，谁有数据就按那个日期落库，
    #    天然完成 T+1 对齐，也不会把上一交易日的数据误记到今天。
    last_snap = meta.get('lastSnapshotDate', '')
    last_ts = meta.get('lastSnapshotTs', 0)
    fresh_enough = (last_snap == today_dash) and (time.time() - last_ts < SNAPSHOT_MIN_INTERVAL)
    if force_snapshot or not fresh_enough:
        added = 0
        for dstr in _recent_trade_dates(7):
            if dstr in days and days[dstr]:
                continue                     # 已有，跳过
            got = {}
            if need_sh:
                got.update(fetch_sse_snapshot(dstr))
            if got:
                days[dstr] = got
                added += 1
        # 深交所没有历史接口，只能"今天抓一次存今天"，靠天数累积
        if need_sz and today not in days:
            sz = fetch_szse_snapshot()
            if sz:
                days[today] = sz
                added += 1
        meta['lastSnapshotDate'] = today_dash
        meta['lastSnapshotTs'] = time.time()
        meta['snapshotAdded'] = added
        if added:
            _save(payload)

    # 2) 上交所历史回补：本地不足 PERCENTILE_DAYS 天时按日期补齐
    if need_sh:
        sh_codes = _sh_codes_from(symbols)
        have = sum(1 for d in days if any(c in days[d] for c in sh_codes))
        if have < PERCENTILE_DAYS:
            backfilled = 0
            tried = 0
            for dstr in _recent_trade_dates(BACKFILL_CALENDAR_DAYS):
                if dstr in days:
                    continue
                tried += 1
                got = fetch_sse_snapshot(dstr)
                if not got:
                    continue          # 非交易日 / 未披露，跳过
                days[dstr] = got
                backfilled += 1
                if _count_days_for(days, symbols) >= PERCENTILE_DAYS:
                    break
            if backfilled:
                meta['lastBackfillTs'] = time.time()
                meta['lastBackfillAdded'] = backfilled
                _save(payload)
            print(f'[share] 回补 {backfilled} 天（尝试 {tried} 个日期）', file=sys.stderr)

    return payload


def _sh_codes_from(symbols):
    return [s[2:] for s in symbols if s.startswith('sh')]


def _count_days_for(days, symbols):
    codes = [s[2:] for s in symbols]
    return sum(1 for d in days if any(c in days[d] for c in codes))


# ---------------- 计算 ----------------

def compute_one(payload, symbol, price_today=None, price_prev=None, price_map=None):
    """算一只 ETF 的净申赎金额与分位。

    symbol: 'sh510300' / 'sz159915'
    price_today / price_prev: 今日与昨日收盘价，价格缺失时的兜底。
    price_map: {YYYYMMDD: 收盘价}，用于把历史每一日的份额变动换算成金额（推荐传）。
    返回 dict：
        ok            是否有可用数据
        netAmount     最新一日净申赎金额（元，正=净申购）
        netShares     最新一日净申赎份额（份）
        net5Amount    近 5 日累计净申赎金额（元）
        percentile    该净申赎在近 N 日中的分位（0~1）
        days          实际用于计算的交易日数
        asOf          最新份额对应的日期（YYYYMMDD）
        note          说明（数据不足时给出原因）
    """
    code = symbol[2:]
    days = payload.get('days') or {}

    # 取出这只 ETF 有份额的所有日期，升序
    series = []
    for d in sorted(days):
        v = days[d].get(code)
        if v:
            series.append((d, v))

    base = {'ok': False, 'netAmount': None, 'netShares': None, 'percentile': None,
            'days': len(series), 'asOf': series[-1][0] if series else None,
            'note': ''}

    if len(series) < 2:
        base['note'] = f'份额历史仅 {len(series)} 天（深市需每天累积）'
        return base

    # 逐日净申赎金额 = Δ份额 × 当日价格
    # 价格用「变动日当天」的收盘价（ETF 净值≈收盘价）。传入的 price_map 是
    # {YYYYMMDD: close}，没有该日价格时才退回 price_today / 1.0 兜底。
    # 分位单独在「份额变动」上算：价格日内波动远小于份额量级变化，不影响排序结论，
    # 这样即使没有完整价格序列，分位依然可信。
    price_map = price_map or {}
    nets = []          # [(date, net_shares, price_used)]
    for i in range(1, len(series)):
        d, cur = series[i]
        _, prev = series[i - 1]
        delta = cur - prev
        px = price_map.get(d)
        if px is None:
            px = price_today if i == len(series) - 1 else (price_prev or 1.0)
        nets.append((d, delta, px))

    latest = nets[-1]
    base['ok'] = True
    base['netShares'] = latest[1]
    base['netAmount'] = latest[1] * latest[2]
    base['asOf'] = latest[0]

    # 分位：近 PERCENTILE_DAYS 天的净申赎份额，看今日排在第几
    window = [n[1] for n in nets[-PERCENTILE_DAYS:]]
    if len(window) >= MIN_DAYS_FOR_PCT:
        cur = latest[1]
        le = sum(1 for v in window if v <= cur)
        base['percentile'] = le / len(window)
        base['days'] = len(window)
    else:
        base['note'] = f'分位需 {MIN_DAYS_FOR_PCT} 天，当前 {len(window)} 天'

    # 近 5 日累计净申赎（更能看出持续性，单日易受单笔大额干扰）
    recent5 = nets[-5:]
    base['net5Amount'] = sum(n[1] * n[2] for n in recent5)
    base['net5Days'] = len(recent5)

    return base


def status():
    """给后台/调试用：看看本地攒了多少天"""
    payload = _load()
    days = payload.get('days') or {}
    return {'days': len(days), 'meta': payload.get('meta') or {},
            'first': min(days) if days else None,
            'last': max(days) if days else None}


if __name__ == '__main__':
    if '--status' in sys.argv:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    elif '--snapshot' in sys.argv:
        p = ensure_history(['sh510300', 'sz159915'], force_snapshot=True)
        print(json.dumps(status(), ensure_ascii=False, indent=2))
