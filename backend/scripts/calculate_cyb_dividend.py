#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创业红利轮动策略：创业板指 / 中证红利 比值择时

核心思想：创业板指（399006）代表高成长高估值，中证红利（000922）代表低估值高股息。
两者比值 = 市场风险偏好的温度计：
    比值极低 → 成长被杀到极致，红利被抱团 → 反转买入创业板
    比值极高 → 成长泡沫化，红利被抛弃 → 泡沫逃顶

状态划分（纯依据比值，不含持仓滞回，因为该策略是"温度计"而非"仓位机"）：
    < 0.30          抄底
    [0.30, 0.35)    机会
    [0.35, 0.40)    观察（偏冷）
    [0.40, 0.65]    中性
    (0.65, 0.70]    警戒
    > 0.70          逃顶

数据源：腾讯行情
    - 实时：qt.gtimg.cn（指数可批量查询，指数代码无需复权）
    - 历史：proxy.finance.qq.com 日线，单次最多约 2000 根，足够覆盖 5 年

注意：指数在腾讯接口中只有 `day` 字段（无 `qfqday`），与 ETF 不同。
"""
import sys
import json
import os
import time
from datetime import datetime, timedelta

import requests

# ====== 标的定义 ======
GROWTH_SYMBOL = 'sz399006'      # 创业板指
GROWTH_NAME = '创业板指'
DIVIDEND_SYMBOL = 'sh000922'    # 中证红利
DIVIDEND_NAME = '中证红利'

# ====== 阈值（与前端展示、判定表格保持一致，改这里即全局生效）======
LINES = {
    'sweepBottom': 0.30,    # 抄底上限
    'opportunity': 0.35,    # 机会上限
    'watch': 0.40,          # 观察上限
    'alert': 0.65,          # 警戒下限
    'escapeTop': 0.70,      # 逃顶下限
}

# ====== 网络参数 ======
CONNECT_TIMEOUT = 2.0
READ_TIMEOUT = 8.0
HISTORY_DAYS = 1300         # 约 5.2 年交易日，够 5 年曲线 + 余量
POINTS_PER_DAY = 1          # 每日一个点

HISTORY_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'cyb_dividend_cache.json')


def _log(msg):
    """所有日志走 stderr，避免污染 stdout 的 JSON。"""
    print(f"[创业红利] {msg}", file=sys.stderr, flush=True)


# ====== 状态判定 ======

# 状态按"冷热"排序，用于前端着色和描述
STATE_ORDER = ['抄底', '机会', '观察', '中性', '警戒', '逃顶']


def classify(ratio):
    """根据比值给出状态。区间左闭右开，边界值归入更"热"的一侧。

    ratio < 0.30              → 抄底
    0.30 <= ratio < 0.35      → 机会
    0.35 <= ratio < 0.40      → 观察
    0.40 <= ratio <= 0.65     → 中性
    0.65 < ratio <= 0.70      → 警戒
    ratio > 0.70              → 逃顶
    """
    if ratio is None:
        return '数据不足'
    if ratio < LINES['sweepBottom']:
        return '抄底'
    if ratio < LINES['opportunity']:
        return '机会'
    if ratio < LINES['watch']:
        return '观察'
    if ratio <= LINES['alert']:
        return '中性'
    if ratio <= LINES['escapeTop']:
        return '警戒'
    return '逃顶'


def advice_of(state):
    """状态对应的操作建议。"""
    return {
        '抄底': ('重仓买入创业板', '极端低估区，历史上极少出现，逆向分批建仓'),
        '机会': ('分批买入创业板', '成长相对红利已被显著压制，可逐步加仓'),
        '观察': ('偏冷观察', '开始偏离常态，等待更低位置或明确反弹信号'),
        '中性': ('持有 / 不操作', '比值处于历史常态区间，不构成买卖信号'),
        '警戒': ('减仓成长', '成长相对红利偏贵，可逐步降低创业板仓位'),
        '逃顶': ('清仓成长', '极端高估区，成长泡沫化，优先保住利润'),
        '数据不足': ('数据不足', '历史数据不够，无法判定'),
    }.get(state, ('-', '-'))


# ====== 数据获取 ======

def _cache_load():
    try:
        if os.path.exists(HISTORY_CACHE_FILE):
            with open(HISTORY_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _cache_save(cache):
    try:
        with open(HISTORY_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        _log(f'缓存写入失败: {e}')


def fetch_history(symbol, days=HISTORY_DAYS):
    """取指数日线收盘价（按天缓存，当天只拉一次）。

    腾讯接口对指数只返回 `day`（无 `qfqday`），这里做兼容。
    """
    today = datetime.now().strftime('%Y-%m-%d')
    cache = _cache_load()
    cached = cache.get(symbol)
    if cached and cached.get('date') == today and len(cached.get('data') or []) >= min(days, 200):
        _log(f'{symbol} 命中今日缓存 {len(cached["data"])} 条')
        return cached['data']

    url = ('http://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get'
           f'?param={symbol},day,,,{days},qfq')
    t0 = time.time()
    try:
        resp = requests.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        if resp.status_code != 200:
            _log(f'{symbol} 历史接口返回 {resp.status_code}')
            return cached.get('data') if cached else []
        node = resp.json().get('data', {}).get(symbol) or {}
        klines = node.get('qfqday') or node.get('day') or []
        data = [{'day': k[0], 'close': float(k[2])} for k in klines if len(k) >= 3]
        _log(f'{symbol} 拉取 {len(data)} 条 {time.time()-t0:.2f}s')
        if data:
            cache[symbol] = {'date': today, 'data': data}
            _cache_save(cache)
        return data
    except Exception as e:
        _log(f'{symbol} 历史拉取失败: {e}')
        return cached.get('data') if cached else []


def fetch_realtime_batch():
    """一次请求拿回两个指数的实时价。失败返回空 dict，由历史收盘价兜底。"""
    try:
        t0 = time.time()
        resp = requests.get(f'https://qt.gtimg.cn/q={GROWTH_SYMBOL},{DIVIDEND_SYMBOL}',
                            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        resp.encoding = 'gbk'
        out = {}
        for line in resp.text.split(';'):
            line = line.strip()
            if '=' not in line:
                continue
            key = line.split('=')[0].replace('v_', '').strip()
            body = line.split('="', 1)[-1].rstrip('"')
            fields = body.split('~')
            if len(fields) < 33 or not fields[3]:
                continue
            try:
                out[key] = {
                    'price': float(fields[3]),
                    'changePct': float(fields[32]) if fields[32] else None,
                    'quoteTime': fields[30] if len(fields) > 30 else '',
                }
            except ValueError:
                continue
        _log(f'实时行情 {len(out)}/2 {time.time()-t0:.2f}s')
        return out
    except Exception as e:
        _log(f'实时行情失败: {e}')
        return {}


# ====== 主流程 ======

def build():
    gross = fetch_history(GROWTH_SYMBOL)
    div = fetch_history(DIVIDEND_SYMBOL)
    if not gross or not div:
        return {'code': 500, 'message': '指数历史数据获取失败'}

    growth_map = {d['day']: d['close'] for d in gross}
    div_map = {d['day']: d['close'] for d in div}
    common = sorted(set(growth_map) & set(div_map))
    if len(common) < 30:
        return {'code': 500, 'message': f'两指数共同交易日过少（{len(common)}）'}

    # 实时价：仅当交易日与最新K线一致时，覆盖最后一个点（避免用盘中价污染历史）
    rt = fetch_realtime_batch()
    rt_growth = rt.get(GROWTH_SYMBOL)
    rt_div = rt.get(DIVIDEND_SYMBOL)
    live_used = False
    if rt_growth and rt_div:
        today_str = datetime.now().strftime('%Y-%m-%d')
        rt_date = (f'{rt_growth["quoteTime"][:4]}-{rt_growth["quoteTime"][4:6]}-'
                   f'{rt_growth["quoteTime"][6:8]}') if len(rt_growth.get('quoteTime', '')) >= 8 else ''
        # 腾讯的报价时间可能因时区/测试环境而超前，严格用"日期等于今天"来判断
        if rt_date == today_str and common and common[-1] <= today_str:
            growth_map[common[-1]] = rt_growth['price']
            div_map[common[-1]] = rt_div['price']
            live_used = True
            _log(f'实时价已并入 {common[-1]}')

    # 拼接序列
    series = []
    for day in common:
        g = growth_map[day]
        d = div_map[day]
        if not d:
            continue
        r = g / d
        series.append({
            'day': day,
            'ratio': round(r, 4),
            'growth': round(g, 2),
            'dividend': round(d, 2),
            'state': classify(r),
        })

    # 只保留近 5 年（按自然年，往前推 5 年同日）
    if series:
        last_day = datetime.strptime(series[-1]['day'], '%Y-%m-%d')
        cutoff = (last_day - timedelta(days=365 * 5)).strftime('%Y-%m-%d')
        series = [p for p in series if p['day'] >= cutoff]

    current = series[-1]
    state = current['state']
    action, reason = advice_of(state)
    minor_state = classify(series[-2]['ratio']) if len(series) > 1 else state

    # 距各阈值的分位（当前比值在近 5 年的位置）
    ratios = [p['ratio'] for p in series]
    below = sum(1 for v in ratios if v < current['ratio'])
    percentile = round(below / len(ratios) * 100, 1) if ratios else None

    # 各状态出现天数（近 5 年）
    dist = {s: 0 for s in STATE_ORDER}
    for p in series:
        if p['state'] in dist:
            dist[p['state']] += 1

    return {
        'code': 200,
        'message': 'success',
        'data': {
            'growth': {
                'symbol': GROWTH_SYMBOL,
                'name': GROWTH_NAME,
                'price': current['growth'],
                'changePct': rt_growth.get('changePct') if rt_growth else None,
            },
            'dividend': {
                'symbol': DIVIDEND_SYMBOL,
                'name': DIVIDEND_NAME,
                'price': current['dividend'],
                'changePct': rt_div.get('changePct') if rt_div else None,
            },
            'ratio': current['ratio'],
            'day': current['day'],
            'state': state,
            'stateYesterday': minor_state,
            'stateChanged': state != minor_state,
            'action': action,
            'reason': reason,
            'percentile': percentile,
            'lines': LINES,
            'stateOrder': STATE_ORDER,
            'distribution': dist,
            'series': series,
            'params': {
                'lookbackYears': 5,
                'points': len(series),
            },
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'realtimeOk': live_used,
            'dataSource': ('腾讯实时价 + 腾讯指数日线' if live_used
                           else '腾讯指数日线收盘价（实时价未并入）'),
        }
    }


def main():
    t0 = time.time()
    try:
        out = build()
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        out = {'code': 500, 'message': f'计算异常: {e}'}
    _log(f'总耗时 {time.time()-t0:.2f}s')
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
