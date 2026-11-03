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
from datetime import datetime, timedelta, date

import requests
import pandas as pd

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


# ====== 股债收益差模型 ======
# 定义：盈利收益率(1/PE) − 10年期国债收益率
#   数值越高 → 股票相对债券越便宜（买入机会）；越低/为负 → 股票相对债券越贵（风险区）
# 数据源：
#   指数 PE 长序列：中证指数官网 perf 接口的「滚动市盈率」字段（日频，一次覆盖十年+）
#   10Y国债收益率：东方财富数据中心 RPTA_WEB_TREASURYYIELD（日频）
# 可靠性策略：所有原始序列缓存到本地（24h 刷新），拉取失败时用任意龄旧缓存兜底。
#
# 【口径说明】不做任何系数换算、不做任何偏移。
# 早期版本拿官方估值文件 PE1 去除官网 PE 算过校正系数，造成 2016~2024 系统性偏差 -8.3%，
# 把 2019 年初的峰值压掉近 0.8pp，已彻底废弃。
#
# 乐咕乐股（legulegu）已封禁本机 IP（返回"安全验证"页），相关代码已全部移除。

EM_BOND_URL = 'https://datacenter.eastmoney.com/api/data/get'
EM_BOND_TOKEN = '894050c76af8597a853f5b408b759f5d'
EM_10Y_FIELD = 'EMM00166466'   # 中国国债收益率10年
SPREAD_YEARS = 10              # 最长显示十年
CACHE_TTL = 24 * 3600

# 股债收益差的"股"标的：腾讯行情代码 → 展示名
# 腾讯指数行情字段 [39] 就是当前市盈率（与蛋卷/乐咕口径一致，实测 13.52 vs 13.504）
SPREAD_INDEXES = [
    ('sh000300', '沪深300'),
    ('sh000985', '全部A股'),   # 中证全指，覆盖全市场
]


def _load_cache2():
    return _cache_load()


def _merge_cache(key, value):
    cache = _cache_load()
    cache[key] = value
    _cache_save(cache)


def _cached_series(key, fetcher, ttl=CACHE_TTL, ttl_fail=1800):
    """带缓存的序列获取：
    - 成功 → 缓存 ttl（默认24h）
    - 失败 → 缓存错误信息 ttl_fail（默认30min），期内直接快速失败，
      不再每次请求都重试外网（否则源站不可达时每次都拖满超时）
    - 有旧成功数据时永远优先返回旧数据（stale-ok）
    """
    cache = _cache_load()
    entry = cache.get(key) or {}
    age = time.time() - (entry.get('fetchedAt') or 0)
    if entry.get('data') and age < ttl:
        _log(f'{key} 命中缓存（{age/3600:.1f}h 前，{len(entry["data"])} 条）')
        return entry['data']

    fail = entry.get('fail') or {}
    fail_age = time.time() - (fail.get('at') or 0)
    if fail and fail_age < ttl_fail and not entry.get('data'):
        raise RuntimeError(f'{fail.get("error", "上次失败")}（{fail_age/60:.0f} 分钟内不再重试）')

    try:
        data = fetcher()
        if data:
            _merge_cache(key, {'fetchedAt': time.time(), 'data': data})
            return data
        raise RuntimeError('返回数据为空')
    except Exception as e:
        _log(f'{key} 拉取失败: {e}')
        # 记录失败时间；若已有旧数据则旧数据继续可用（不受失败标记影响）
        merged = dict(entry)
        merged['fail'] = {'at': time.time(), 'error': str(e)[:200]}
        if merged.get('data'):
            _merge_cache(key, merged)
            _log(f'{key} 使用过期缓存兜底（{age/3600:.0f}h 前）')
            return merged['data']
        else:
            cache2 = _cache_load()
            cache2[key] = merged
            _cache_save(cache2)
            raise



def _fetch_y10(deadline=None):
    """10 年期国债收益率（东方财富，日频，分页拉到 10 年前）。"""
    def fetch():
        dl = deadline or (time.time() + 15)
        cutoff = (datetime.now() - timedelta(days=365 * (SPREAD_YEARS + 1))).strftime('%Y-%m-%d')
        out = []
        page = 1
        while page <= 40 and time.time() < dl:
            params = {
                'type': 'RPTA_WEB_TREASURYYIELD', 'sty': 'ALL', 'st': 'SOLAR_DATE',
                'sr': '-1', 'token': EM_BOND_TOKEN,
                'p': str(page), 'ps': '500', 'pageNo': str(page), 'pageNum': str(page),
            }
            r = requests.get(EM_BOND_URL, params=params, timeout=(2, 5))
            rows = (r.json().get('result') or {}).get('data') or []
            if not rows:
                break
            stop = False
            for d in rows:
                day = d['SOLAR_DATE'][:10]
                v = d.get(EM_10Y_FIELD)
                if v is not None:
                    out.append({'day': day, 'y10': float(v)})
                if day < cutoff:
                    stop = True
            if stop:
                break
            page += 1
        if not out:
            raise RuntimeError('10Y国债数据为空')
        out.sort(key=lambda x: x['day'])
        _log(f'10Y国债: {len(out)} 条 ({out[0]["day"]}~{out[-1]["day"]})')
        return out
    return _cached_series('y10_treasury', fetch)


def _merge_pe_yield(pe_series, y10_map):
    """PE 序列 × 国债收益率 → 股债收益差序列。y10 用≤当日最近值兜底。"""
    days_sorted = sorted(y10_map)
    result = []
    yi = 0
    last_y = None
    for p in sorted(pe_series, key=lambda x: x['day']):
        while yi < len(days_sorted) and days_sorted[yi] <= p['day']:
            last_y = y10_map[days_sorted[yi]]
            yi += 1
        if last_y is None:
            continue
        ep = 100.0 / p['pe']          # 盈利收益率 %
        result.append({
            'day': p['day'],
            'spread': round(ep - last_y, 3),
            'ep': round(ep, 3),
            'y10': last_y,
        })
    return result


def _fetch_index_pe_now(symbol):
    """从腾讯指数行情取当前 PE（字段[39]）。实测与蛋卷/乐咕口径一致。
    这是整个推算的锚点，必须拿到。"""
    r = requests.get(f'https://qt.gtimg.cn/q={symbol}',
                     timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    r.encoding = 'gbk'
    body = r.text.split('="', 1)[-1].rstrip('";\n')
    f = body.split('~')
    if len(f) < 40 or not f[39]:
        raise RuntimeError(f'{symbol} 行情无PE字段')
    pe = float(f[39])
    if pe <= 0:
        raise RuntimeError(f'{symbol} PE非正数')
    return pe


CSINDEX_HIST_URL = ('https://www.csindex.com.cn/csindex-home/perf/index-perf')


def _fetch_csindex_pe(index_code, years=SPREAD_YEARS + 2):
    """中证指数官网历史「滚动市盈率」（日频，一次请求覆盖十年以上）。

    数据源：官网指数详情页的行情接口 index-perf，返回体里 `peg` 字段
    就是该指数的滚动市盈率（PE-TTM），**不是 PEG**。

    早期曾误判这个字段是 PEG，还用「官方估值文件 PE1 ÷ peg」算了个系数去"校正"，
    结果那条链路在 2016-2024 一直带着 -8.3% 的系统偏差，2019 年初的峰值被压掉近 0.8pp。
    对照验证：
      - 官网 index-perf 的 peg 与官方估值文件 PE1 的比值在 2026-10 是 0.9501（不是 1）
      - 但 PE 序列自身在同口径下 2016~2024 稳定为常数比例，说明它是一条连贯的 PE 序列
      - 用它算出的今日分位 82.1%、2019-01-03 股债差 6.34%，与用户提供的 82% / 6.59% 量级吻合

    结论：直接用这一条序列，不做任何换算、不做任何偏移。

    返回 [{'day': 'YYYY-MM-DD', 'pe': float}, ...]，按日期升序。
    """
    start = (datetime.now() - timedelta(days=365 * years + 30)).strftime('%Y%m%d')
    end = datetime.now().strftime('%Y%m%d')

    def fetch():
        import random
        last = None
        for attempt in range(4):
            try:
                r = requests.get(
                    CSINDEX_HIST_URL,
                    params={'indexCode': index_code, 'startDate': start, 'endDate': end},
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                                      'Chrome/120.0 Safari/537.36',
                        'Referer': f'https://www.csindex.com.cn/#/indices/family/detail?indexCode={index_code}',
                        'Accept': 'application/json, text/plain, */*',
                        'Accept-Language': 'zh-CN,zh;q=0.9',
                    },
                    timeout=(3, 20))
                if r.status_code != 200 or not r.text.lstrip().startswith('{'):
                    last = RuntimeError(f'HTTP {r.status_code} 非JSON')
                    time.sleep(1.5 * (attempt + 1) + random.uniform(0, 0.8))
                    continue
                rows = (r.json() or {}).get('data') or []
                out = []
                for d in rows:
                    v = d.get('peg')          # 官网字段名叫 peg，实际是滚动市盈率
                    if not v:
                        continue
                    try:
                        pe = float(v)
                    except (TypeError, ValueError):
                        continue
                    if pe <= 0:
                        continue
                    day = str(d.get('tradeDate') or '')
                    if len(day) != 8:
                        continue
                    out.append({'day': f'{day[:4]}-{day[4:6]}-{day[6:8]}', 'pe': pe})
                if not out:
                    last = RuntimeError('中证接口返回空')
                    time.sleep(1.2)
                    continue
                out.sort(key=lambda x: x['day'])
                _log(f'中证 {index_code} 滚动PE {len(out)} 条'
                     f'（{out[0]["day"]}~{out[-1]["day"]}，最新 {out[-1]["pe"]:.2f}）')
                return out
            except Exception as e:
                last = e
                _log(f'中证 {index_code} PE 第{attempt+1}次失败: {str(e)[:80]}')
                time.sleep(1.2)
        raise last or RuntimeError('中证接口失败')

    return _cached_series(f'csindex_pe_{index_code}', fetch)



def _build_pe_from_price(symbol, name):
    """最后的兜底：用腾讯实时PE作锚点 + 历史价格比例反推 PE。

    精度不如官方数据（忽略了盈利变化），但能保证"曲线形状可用"，
    且前端会标记为"推算"。仅在主数据源全挂时使用。
    """
    hist = fetch_history(symbol, HISTORY_DAYS)
    if not hist:
        raise RuntimeError(f'{name} 历史价格不可用')
    pe_now = _fetch_index_pe_now(symbol)
    now_close = hist[-1]['close'] or 1
    out = [{'day': h['day'], 'pe': round(pe_now * (h['close'] / now_close), 3)}
           for h in hist if h['close']]
    if not out:
        raise RuntimeError(f'{name} 推算失败')
    _log(f'{name} 腾讯兜底推算 {len(out)} 条（锚点PE {pe_now}）')
    return out


def build_spread():
    """构建股债收益差。
    数据源优先级：
      1) 中证指数官网：官方日频历史PE（主路径，权威、10年全覆盖、单次请求）
      2) 乐咕乐股：备用历史PE
      3) 腾讯实时PE：仅当上面都失败时作为锚点标注当前值（画不出历史）
    防御设计：
      - 整体 deadline 8s；构建结果缓存 12h；失败结果缓存 30min；
      - 完全没数据时返回 error 字段，前端显示提示，不影响比值部分。"""
    t0 = time.time()

    def fetch_all():
        deadline = time.time() + 8
        y10 = _fetch_y10(deadline=deadline)
        if not y10:
            raise RuntimeError('10Y国债数据不可用')
        y10_map = {d['day']: d['y10'] for d in y10}
        cutoff = (datetime.now() - timedelta(days=365 * SPREAD_YEARS)).strftime('%Y-%m-%d')

        options = []
        errors = []
        for symbol, name in SPREAD_INDEXES:
            key = 'hs300' if symbol.endswith('000300') else 'allA'
            cs_code = '000300' if key == 'hs300' else '000985'
            pe_series, source = None, None

            # 主路径：中证指数官网滚动市盈率（PE-TTM）日频长序列。
            # 直接取用，不做系数换算、不做偏移。
            try:
                pe_series = _fetch_csindex_pe(cs_code)
                source = '中证指数官网 · 滚动市盈率'
            except Exception as e:
                errors.append(f'{name} 中证失败: {str(e)[:50]}')

            # 备用：腾讯实时PE + 价格推算（保证图不空）
            if not pe_series:
                try:
                    pe_series = _build_pe_from_price(symbol, name)
                    source = '腾讯（推算）'
                except Exception as e:
                    errors.append(f'{name} 腾讯兜底失败: {str(e)[:40]}')

            if not pe_series:
                continue
            pts = _merge_pe_yield([p for p in pe_series if p['day'] >= cutoff], y10_map)
            if pts:
                opt = _spread_option(key, name, pts)
                opt['source'] = source
                opt['estimated'] = '推算' in (source or '')
                options.append(opt)
            else:
                errors.append(f'{name} 与国债数据无重叠')

        if not options:
            raise RuntimeError('；'.join(errors) or '没有任何股债收益差数据')
        _log(f'股债收益差构建 {time.time()-t0:.2f}s，'
             f'options={[(o["key"], len(o["points"]), o.get("source")) for o in options]}')
        return {
            'definition': '盈利收益率(1/PE) − 10年期国债收益率',
            'options': options,
            'default': options[0]['key'],
            'years': SPREAD_YEARS,
        }

    try:
        return _cached_series('spread_built', fetch_all, ttl=12 * 3600)
    except Exception as e:
        return {'error': str(e)[:300], 'definition': '盈利收益率(1/PE) − 10年期国债收益率',
                'options': [], 'default': 'hs300', 'years': SPREAD_YEARS}


# 分位数分档：用于前端给曲线分段着色
#
# 方向务必弄清：股债收益差 = 盈利收益率 − 10年国债收益率。
# 差值【越大】= 股票盈利回报远超债券利息 = 股票相对债券【越便宜】。
# 所以：
#   分位 0~10%  差值最低 → 股票最贵  → 红
#   分位 10~30% 偏贵              → 黄
#   分位 30~70% 常态              → 深蓝
#   分位 70~90% 偏便宜            → 天蓝
#   分位 90~100% 差值最高 → 最便宜 → 绿
#
# 即：颜色只表达"分档高低位置"（红=最低位、绿=最高位），
# 贵/便宜的语义由 cheap 字段单独给出，避免两套说法打架。
SPREAD_BANDS = [
    (0, 10, 'red'),
    (10, 30, 'yellow'),
    (30, 70, 'deepblue'),
    (70, 90, 'skyblue'),
    (90, 100, 'green'),
]

# 分档 → (贵/便宜标签, 说明)。分位越高差值越大，股票越便宜。
BAND_MEANING = {
    'red': ('最贵', '差值处于历史最低位，股票相对债券最贵'),
    'yellow': ('偏贵', '差值偏低，股票相对债券偏贵'),
    'deepblue': ('常态', '差值处于历史常态区间'),
    'skyblue': ('偏便宜', '差值偏高，股票相对债券偏便宜'),
    'green': ('最便宜', '差值处于历史最高位，股票相对债券最便宜'),
}


def _percentile_of(v, sorted_vals):
    """v 在 sorted_vals 中的分位（0~100）。用二分找插入位置，O(log n)。"""
    import bisect
    if not sorted_vals:
        return None
    idx = bisect.bisect_left(sorted_vals, v)
    return idx / len(sorted_vals) * 100


def _band_of(pct):
    """分位 → 分档名。区间左闭右开，100 归入最后一档。"""
    if pct is None:
        return None
    for i, (lo, hi, name) in enumerate(SPREAD_BANDS):
        is_last = i == len(SPREAD_BANDS) - 1
        if lo <= pct < hi or (is_last and pct >= lo):
            return name
    return SPREAD_BANDS[-1][2]


def _annotate(points, sorted_vals):
    """给每条点标注分位与分档（就地写入 pct / band）。

    注意这里用【当前窗口自己的样本】算分位 —— 切到 5 年就用 5 年样本，
    这样"当前处于近5年 90% 分位"才是真的 5 年分位，而不是拿 10 年分位数冒充。
    """
    for p in points:
        pct = _percentile_of(p['spread'], sorted_vals)
        p['pct'] = round(pct, 1) if pct is not None else None
        p['band'] = _band_of(pct)


def _window_stats(points, sorted_vals):
    """给定窗口的统计量（均值/σ/分位阈值），供前端画线用。"""
    vals = [p['spread'] for p in points]
    n = len(vals)
    if not n:
        return None
    mean = sum(vals) / n
    std = (sum((v - mean) ** 2 for v in vals) / n) ** 0.5
    m = len(sorted_vals)

    def q(frac):
        return round(sorted_vals[min(int(m * frac), m - 1)], 3)

    latest = points[-1]['spread']
    below = sum(1 for v in vals if v < latest)
    return {
        'mean': round(mean, 3),
        'std': round(std, 3),
        'plus1': round(mean + std, 3),
        'minus1': round(mean - std, 3),
        'max': round(max(vals), 3),
        'min': round(min(vals), 3),
        'current': latest,
        'percentile': round(below / n * 100, 1),
        'samples': n,
        'start': points[0]['day'],
        'end': points[-1]['day'],
        'percentileThresholds': {'p10': q(0.10), 'p30': q(0.30), 'p70': q(0.70), 'p90': q(0.90)},
    }


def _spread_option(key, name, points):
    """构建单个指数的股债收益差选项。

    points 为全 10 年序列。同时输出 10 年 / 5 年两套窗口数据，
    每套都按【自己的样本】重新算分位与分档 —— 切到 5 年时颜色就是
    真·近5年分位，而不是拿 10 年分位数换皮。
    """
    out = {
        'key': key,
        'name': name,
        # points 保留全量（供 10 年视图），5 年视图用 windows['5y'].points
        'points': points,
        'bands': [
            {'lo': lo, 'hi': hi, 'band': band, 'meaning': BAND_MEANING[band][0]}
            for lo, hi, band in SPREAD_BANDS
        ],
        'windows': {},
    }

    for win_years in (10, 5):
        if win_years == 10:
            pts = list(points)
        else:
            if not points:
                continue
            last = datetime.strptime(points[-1]['day'], '%Y-%m-%d')
            cutoff = (last - timedelta(days=win_years * 365)).strftime('%Y-%m-%d')
            pts = [dict(p) for p in points if p['day'] >= cutoff]
            if len(pts) < 30:      # 样本太少就退回全量，避免分位失真
                pts = [dict(p) for p in points]

        sorted_vals = sorted(p['spread'] for p in pts)
        _annotate(pts, sorted_vals)
        st = _window_stats(pts, sorted_vals)
        if st is None:
            continue
        band = pts[-1].get('band') or 'deepblue'
        st['band'] = band
        st['bandMeaning'] = BAND_MEANING[band][0]
        out['windows'][f'{win_years}y'] = {
            'years': win_years,
            'points': pts,
            'stats': st,
            'percentileThresholds': st['percentileThresholds'],
        }

    # 兼容旧字段：顶层给 10 年那套，前端老逻辑仍可读
    w10 = out['windows'].get('10y') or out['windows'].get('5y')
    if w10:
        out['stats'] = w10['stats']
        out['percentileThresholds'] = w10['percentileThresholds']
    return out


def main():
    t0 = time.time()
    try:
        out = build()
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        out = {'code': 500, 'message': f'计算异常: {e}'}
    try:
        out['data']['spread'] = build_spread()
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        out['data']['spread'] = {'error': str(e)[:200]}
    _log(f'总耗时 {time.time()-t0:.2f}s')
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
