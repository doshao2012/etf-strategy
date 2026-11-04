#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国家队监控：主流宽基 ETF 实时成交量异动预警

思路（刻意保持简单，只做一个"预警器"，不做二次判断）：
    量比 R = 今日累计成交量 ÷ 过去 20 日「同一进度」的中位累计成交量

        R >= 2.0   →  显著放量
        1.5 <= R < 2.0  →  放量
        R < 1.5    →  正常

同一指数的多只 ETF 同时放量，比单只放量的可信度高得多，所以按指数分组并给出组内同步度。

数据链路（全部来自腾讯，无需 key）：
    1) 实时累计量：minute/query      → 1 分钟一个点，当日 241 点
    2) 历史基准：  mkline m30        → 每交易日 8 根 30 分钟 bar，接口上限 320 根 ≈ 41 个交易日
    3) 兜底：      newfqkline day    → m30 不足时用日线 20 日均额 × 日内累计占比曲线折算

关键实现细节：
    * 腾讯 m30 的 bar 边界正好落在 10:00/10:30/11:00/11:30/13:30/14:00/14:30/15:00 八个整点收盘，
      所以「当前进度」在这 8 个锚点上可以零误差读取真实基准；不在锚点时用累计占比曲线线性插值。
    * 开盘前 15 分钟成交量样本太少、量比失真，不出信号。
    * 14:45 之后基准曲线尾部斜率陡（15:00 那根 bar 的 CV=1.61），改用全天量比更稳。
    * 时区：所有时间一律用北京时间（服务器是 UTC，务必显式转换）。
"""
import sys
import os
import json
import time
from datetime import datetime, timedelta, timezone

import requests

# ============== 阈值（想调就改这里）==============
R_ALERT = 1.5      # ≥ 此值 → 放量
R_STRONG = 2.0     # ≥ 此值 → 显著放量

# ============== 基准参数 ==============
# 量比分母用「近 5 日均值」：贴合当下成交水位。
# 实测教训：10 月下旬以来市场成交水平持续抬升（沪深300ETF 10-21 日均 1415 万手 →
# 11-03 达 4654 万手），20 日中位数会把这个趋势"平均掉"，导致普遍虚报放量
# （18 只里 7 只误报）。5 日均值跟得上水位变化；20 日均值仍保留为参考显示。
BASE_DAYS_FAST = 5
BASE_DAYS_SLOW = 20
M30_MAX_BARS = 320         # 腾讯 m30 接口硬上限，返回 ≈41 个交易日
MIN_BASE_DAYS = 3          # 少于这么多完整交易日就不出量比（直接标数据不足）
OPEN_QUIET_MIN = 15        # 开盘前 N 分钟不出信号
TAIL_SWITCH = '14:45'      # 这个时间之后改用全天量比

# ============== 缓存 ==============
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CACHE_FILE = os.path.join(CACHE_DIR, 'national_team_cache.json')
MINUTE_TTL = 55            # 实时分时缓存秒数（盘中）
BASE_TTL = 4 * 3600        # 历史基准缓存秒数

# ============== 网络 ==============
CONNECT_TIMEOUT = 2.5
READ_TIMEOUT = 8.0
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Referer': 'https://gu.qq.com/',
}
TX_MINUTE = 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/minute/query?code={}'
TX_MKLINE = 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/kline/mkline?param={},m30,,{}'
TX_DAY = 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get?param={},day,,,{},qfq'

# ============== 监控标的 ==============
# 全部为日均成交额 10 亿以上的主流宽基 ETF，按跟踪指数分组。
# 清单是离线核算后固定的（2026-11-04 的 5 日均额），不在运行时动态筛选。
WATCH_GROUPS = [
    {
        'index': '沪深300',
        'etfs': [
            ('sh510300', '沪深300ETF华泰柏瑞'),
            ('sz159919', '沪深300ETF嘉实'),
            ('sh510310', '沪深300ETF易方达'),
            ('sh510330', '沪深300ETF华夏'),
        ],
    },
    {
        'index': '中证A500',
        'etfs': [
            ('sz159338', '中证A500ETF国泰'),
            ('sz159352', '中证A500ETF南方'),
            ('sz159361', '中证A500ETF易方达'),
            ('sh512050', '中证A500ETF华夏'),
        ],
    },
    {
        'index': '中证1000',
        'etfs': [
            ('sh512100', '中证1000ETF南方'),
            ('sz159845', '中证1000ETF华夏'),
            ('sh560010', '中证1000ETF广发'),
        ],
    },
    {
        'index': '科创50',
        'etfs': [
            ('sh588000', '科创50ETF华夏'),
            ('sh588080', '科创50ETF易方达'),
        ],
    },
    {
        'index': '创业板',
        'etfs': [
            ('sz159915', '创业板ETF易方达'),
            ('sz159949', '创业板50ETF华安'),
            ('sz159952', '创业板ETF广发'),
        ],
    },
    {
        'index': '中证500',
        'etfs': [
            ('sh510500', '中证500ETF南方'),
        ],
    },
    {
        'index': '上证50',
        'etfs': [
            ('sh510050', '上证50ETF华夏'),
        ],
    },
]

STATE_ORDER = ['显著放量', '放量', '正常', '数据不足']


def _log(msg):
    print(f"[国家队] {msg}", file=sys.stderr, flush=True)


# ======================================================================
# 时间工具：服务器跑在 UTC，这里统一折算北京时间
# ======================================================================

def bj_now():
    """当前北京时间（naive datetime）。"""
    return datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=8))).replace(tzinfo=None)


def _minutes(hhmm):
    """'HH:MM' → 当日零点起的分钟数。"""
    h, m = hhmm.split(':')
    return int(h) * 60 + int(m)


# A 股交易时段（分钟数）
AM_OPEN, AM_CLOSE = _minutes('09:30'), _minutes('11:30')
PM_OPEN, PM_CLOSE = _minutes('13:00'), _minutes('15:00')
TOTAL_MINUTES = 120 + 120   # 全天 240 个交易分钟


def trade_progress(now):
    """返回 (进度占比, 已过去交易分钟数, 是否在交易时段内)。

    盘前 → (0, 0, False)；盘后 → (1, 240, False)。
    """
    t = now.hour * 60 + now.minute
    if t < AM_OPEN:
        return 0.0, 0, False
    if t <= AM_CLOSE:
        used = t - AM_OPEN + 1
        return used / TOTAL_MINUTES, used, True
    if t < PM_OPEN:
        return 120 / TOTAL_MINUTES, 120, False     # 午休：冻结在上午收盘
    if t <= PM_CLOSE:
        used = 120 + (t - PM_OPEN) + 1
        return used / TOTAL_MINUTES, used, True
    return 1.0, TOTAL_MINUTES, False


def market_status(now):
    """给前端的一句话状态。"""
    t = now.hour * 60 + now.minute
    wd = now.weekday()
    if wd >= 5:
        return '休市'
    if t < AM_OPEN:
        return '未开盘'
    if t <= AM_CLOSE:
        if t < AM_OPEN + OPEN_QUIET_MIN:
            return '开盘观察中'
        return '交易中'
    if t < PM_OPEN:
        return '午休'
    if t <= PM_CLOSE:
        if t >= _minutes(TAIL_SWITCH):
            return '尾盘'
        return '交易中'
    return '已收盘'


# ======================================================================
# 缓存
# ======================================================================

def _cache_read():
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _cache_write(cache):
    """原子写，避免并发读到半截文件。"""
    try:
        tmp = CACHE_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)
    except Exception as e:
        _log(f'缓存写入失败: {e}')


# ======================================================================
# 数据获取
# ======================================================================

def _get_json(url):
    r = requests.get(url, headers=HEADERS,
                     timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    r.raise_for_status()
    return r.json()


def fetch_minute(symbol):
    """当日 1 分钟分时。返回 (日期'YYYY-MM-DD', [(HHMM, 价, 累计量手), ...])。

    腾讯原始格式：'0930 4.086 51874 21195716.00' = 时间 价 累计量(手) 累计额(元)
    """
    j = _get_json(TX_MINUTE.format(symbol))
    node = (j.get('data') or {}).get(symbol) or {}
    md = node.get('data') or {}
    raw = md.get('data') or []
    date = md.get('date') or ''
    if len(date) == 8:
        date = f'{date[:4]}-{date[4:6]}-{date[6:8]}'
    points = []
    for line in raw:
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            points.append((parts[0], float(parts[1]), float(parts[2])))
        except ValueError:
            continue
    return date, points


def fetch_m30(symbol):
    """30 分钟历史 bar。返回 [(日期'YYYY-MM-DD', HHMM, 量手), ...]。"""
    j = _get_json(TX_MKLINE.format(symbol, M30_MAX_BARS))
    node = (j.get('data') or {}).get(symbol) or {}
    bars = node.get('m30') or []
    out = []
    for row in bars:
        if len(row) < 6:
            continue
        ts = str(row[0])
        if len(ts) < 12:
            continue
        try:
            vol = float(row[5])
        except (TypeError, ValueError):
            continue
        out.append((f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}', ts[8:12], vol))
    return out


def fetch_day_vol(symbol, n=25):
    """日线成交量（手），用于兜底的全天均量。返回 [(日期, 量), ...]。"""
    j = _get_json(TX_DAY.format(symbol, n))
    node = (j.get('data') or {}).get(symbol) or {}
    rows = node.get('qfqday') or node.get('day') or []
    out = []
    for row in rows:
        if len(row) < 6:
            continue
        try:
            out.append((row[0], float(row[5])))
        except (TypeError, ValueError):
            continue
    return out


# ======================================================================
# 基准构建
# ======================================================================

SLOTS = ['1000', '1030', '1100', '1130', '1330', '1400', '1430', '1500']


def _median(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def build_base(m30_bars):
    """从 m30 bar 构建基准（近 5 日均值为主，20 日均值为辅）。

    返回 dict：
        cumMedian:  {slot: 近5日各锚点平均累计量}     ← 量比分母（主基准）
        cumSlow:    {slot: 近20日各锚点平均累计量}    ← 参考显示
        ratios:     {slot: 累计量占全天占比}（近5日）
        total:      近5日全天平均量（手）
        totalSlow:  近20日全天平均量
        days:       参与统计的完整交易日数
    """
    by_day = {}
    for day, hhmm, vol in m30_bars:
        by_day.setdefault(day, {})[hhmm] = vol
    # 只取 8 根齐全的交易日（首尾常被截断）
    full = [d for d, m in by_day.items() if all(s in m for s in SLOTS)]
    full.sort()
    fast_days = full[-BASE_DAYS_FAST:]
    slow_days = full[-BASE_DAYS_SLOW:]
    if len(fast_days) < MIN_BASE_DAYS:
        return None

    def cum_avg(days):
        cum = {}
        for i, slot in enumerate(SLOTS):
            vals = [sum(by_day[d][s] for s in SLOTS[:i + 1]) for d in days]
            cum[slot] = sum(vals) / len(vals)
        return cum

    cum = cum_avg(fast_days)
    cum_slow = cum_avg(slow_days) if len(slow_days) > len(fast_days) else cum
    total = cum['1500']
    if total <= 0:
        return None
    return {
        'cumMedian': cum,
        'cumSlow': cum_slow,
        'ratios': {s: cum[s] / total for s in SLOTS},
        'total': total,
        'totalSlow': cum_slow['1500'],
        'days': len(fast_days),
        'daysSlow': len(slow_days),
    }


def base_curve_at(base, now_min):
    """给定当前时刻（含零点分钟数），返回「同进度基准累计量」（近5日均值）。

    在 8 个锚点上直接读真实均值；锚点之间按累计占比线性插值。
    这样比"总均值 × 进度"精确得多——A 股的日内分布极不均匀
    （实测 10:00 就占全天 24.3%，而 11:00-14:00 几乎是一条直线）。
    """
    slots_min = [_minutes(f'{s[:2]}:{s[2:]}') for s in SLOTS]
    cum = base['cumMedian']

    if now_min <= slots_min[0]:
        # 开盘到 10:00 之间：按比例分摊到第一个锚点
        frac = max(0.0, (now_min - AM_OPEN + 1)) / (slots_min[0] - AM_OPEN + 1)
        return cum[SLOTS[0]] * min(frac, 1.0)
    if now_min >= slots_min[-1]:
        return cum[SLOTS[-1]]
    for i in range(len(slots_min) - 1):
        a, b = slots_min[i], slots_min[i + 1]
        if a <= now_min < b:
            frac = (now_min - a) / (b - a)
            return cum[SLOTS[i]] + (cum[SLOTS[i + 1]] - cum[SLOTS[i]]) * frac
    return cum[SLOTS[-1]]


# ======================================================================
# 单个标的计算
# ======================================================================

def classify(r):
    if r is None:
        return '数据不足'
    if r >= R_STRONG:
        return '显著放量'
    if r >= R_ALERT:
        return '放量'
    return '正常'


def _percentile(values, x):
    """x 在 values 中的百分位（0~1）。"""
    if not values:
        return None
    n = len(values)
    below = sum(1 for v in values if v < x)
    equal = sum(1 for v in values if v == x)
    return (below + 0.5 * equal) / n


def analyze_one(symbol, name, now, minute_cache, base_cache):
    """算一只 ETF 的量比。返回结果 dict。"""
    today = now.strftime('%Y-%m-%d')

    # ---- 实时分时（带缓存）----
    mk = minute_cache.get(symbol)
    if not mk or time.time() - mk.get('ts', 0) > MINUTE_TTL:
        try:
            date, points = fetch_minute(symbol)
            mk = {'ts': time.time(), 'date': date, 'points': points}
            minute_cache[symbol] = mk
        except Exception as e:
            _log(f'{symbol} 分时失败: {type(e).__name__}: {e}')
            if not mk:
                return {'symbol': symbol, 'name': name, 'state': '数据不足',
                        'error': f'分时获取失败: {type(e).__name__}'}
    date = mk.get('date') or today
    points = mk.get('points') or []

    price = points[-1][1] if points else None
    today_cum = points[-1][2] if points else 0.0
    last_hhmm = points[-1][0] if points else ''

    # ---- 基准（按日缓存）----
    bk = base_cache.get(symbol)
    if not bk or bk.get('date') != today or time.time() - bk.get('ts', 0) > BASE_TTL:
        try:
            bars = fetch_m30(symbol)
            base = build_base(bars)
            if base:
                base['mode'] = 'm30'
                base['note'] = f"近{base['days']}日均值基准"
            else:
                # 兜底：日线均量 × 日内累计占比（m30 缺失时）
                days = fetch_day_vol(symbol, 25)
                vols = [v for d, v in days if d != today][-BASE_DAYS_FAST:]
                if len(vols) >= MIN_BASE_DAYS:
                    avg = sum(vols) / len(vols)
                    # 无 m30 时只能用经验曲线（全市场通用形状）
                    ratios = {'1000': 0.243, '1030': 0.335, '1100': 0.442,
                              '1130': 0.507, '1330': 0.578, '1400': 0.662,
                              '1430': 0.780, '1500': 1.0}
                    base = {
                        'cumMedian': {s: avg * ratios[s] for s in SLOTS},
                        'cumSlow': dict(base and base.get('cumSlow') or {s: avg * ratios[s] for s in SLOTS}),
                        'ratios': ratios, 'total': avg,
                        'totalSlow': avg, 'days': len(vols), 'daysSlow': len(vols),
                        'mode': 'day_est',
                        'note': f'日线 {len(vols)} 日均量 × 日内曲线（估算）',
                    }
                else:
                    base = None
            bk = {'ts': time.time(), 'date': today, 'base': base}
            base_cache[symbol] = bk
        except Exception as e:
            _log(f'{symbol} 基准失败: {type(e).__name__}: {e}')
            if not bk:
                bk = {'ts': time.time(), 'date': today, 'base': None}

    base = bk.get('base')
    if not base:
        return {'symbol': symbol, 'name': name, 'state': '数据不足',
                'price': price, 'todayVolume': today_cum,
                'error': '历史基准不足'}

    # ---- 计算量比（近5日同进度基准为主，近20日为参考）----
    now_min = now.hour * 60 + now.minute
    tail_mode = now_min >= _minutes(TAIL_SWITCH) and now_min <= PM_CLOSE

    if tail_mode:
        # 尾盘：基准曲线尾部太陡，改用全天量比（今日累计 ÷ 全天均量）
        base_vol = base['total']
        base_vol_slow = base.get('totalSlow') or base['total']
        basis = '全天量比'
    else:
        base_vol = base_curve_at(base, now_min)
        base_vol_slow = base_curve_at(
            {'cumMedian': base.get('cumSlow') or base['cumMedian']}, now_min)
        basis = '同进度量比'

    r = today_cum / base_vol if base_vol > 0 else None
    r_slow = today_cum / base_vol_slow if base_vol_slow > 0 else None

    # ---- 同进度历史分位（近20日逐日复算，参考数字，不参与判定）----
    pct = None
    if base.get('mode') == 'm30':
        hist_ratios = []
        by_day = {}
        for day, hhmm, vol in _base_bars_cache(symbol, base_cache):
            by_day.setdefault(day, {})[hhmm] = vol
        for d, m in by_day.items():
            if len(m) < 8:
                continue
            acc = sum(m[s] for s in SLOTS if _minutes(f'{s[:2]}:{s[2:]}') <= now_min)
            b = base_vol_slow if base_vol_slow > 0 else base_vol
            if b > 0:
                hist_ratios.append(acc / b)
        pct = _percentile(hist_ratios, r_slow if r_slow is not None else r) \
            if r is not None else None

    state = classify(r) if (now_min - AM_OPEN) >= OPEN_QUIET_MIN or market_status(now) in ('午休', '已收盘', '尾盘') else '数据不足'
    if now_min < AM_OPEN + OPEN_QUIET_MIN and now.weekday() < 5:
        state = '数据不足'

    return {
        'symbol': symbol,
        'name': name,
        'date': date,
        'price': price,
        'todayVolume': today_cum,
        'baseVolume': round(base_vol, 0),
        'baseVolumeSlow': round(base_vol_slow, 0) if base_vol_slow else None,
        'ratio': round(r, 3) if r is not None else None,
        'ratioSlow': round(r_slow, 3) if r_slow is not None else None,
        'percentile': round(pct, 3) if pct is not None else None,
        'state': state,
        'basis': basis,
        'lastBar': last_hhmm,
        'baseMode': base.get('mode'),
        'baseNote': base.get('note'),
        'baseDays': base.get('days'),
        'baseDaysSlow': base.get('daysSlow'),
    }


_BARS_CACHE = {}


def _base_bars_cache(symbol, base_cache):
    """为了算历史分位，暂存当日拉到的 m30 原始 bar（不落盘）。"""
    hit = _BARS_CACHE.get(symbol)
    if hit and hit.get('date') == bj_now().strftime('%Y-%m-%d'):
        return hit['bars']
    try:
        bars = fetch_m30(symbol)
        _BARS_CACHE[symbol] = {'date': bj_now().strftime('%Y-%m-%d'), 'bars': bars}
        return bars
    except Exception:
        return []


# ======================================================================
# 主流程
# ======================================================================

def main():
    t0 = time.time()
    now = bj_now()
    status = market_status(now)

    cache = _cache_read()
    minute_cache = cache.get('minute') or {}
    base_cache = cache.get('base') or {}

    groups_out = []
    flat = []
    for grp in WATCH_GROUPS:
        items = []
        for symbol, name in grp['etfs']:
            try:
                row = analyze_one(symbol, name, now, minute_cache, base_cache)
            except Exception as e:
                _log(f'{symbol} 异常: {type(e).__name__}: {e}')
                row = {'symbol': symbol, 'name': name, 'state': '数据不足',
                       'error': str(e)[:120]}
            items.append(row)
            flat.append(row)

        n_strong = sum(1 for x in items if x.get('state') == '显著放量')
        n_alert = sum(1 for x in items if x.get('state') in ('显著放量', '放量'))
        ratios = [x['ratio'] for x in items if x.get('ratio') is not None]
        avg_ratio = round(sum(ratios) / len(ratios), 3) if ratios else None
        if n_strong and n_alert == len(items):
            grp_state = '显著放量'
        elif n_strong >= 1:
            grp_state = '显著放量'
        elif n_alert >= 1:
            grp_state = '放量'
        else:
            grp_state = '正常'
        # 全部标的数据不足时不冒充正常
        if not ratios:
            grp_state = '数据不足'
        groups_out.append({
            'index': grp['index'],
            'state': grp_state,
            'avgRatio': avg_ratio,
            'alertCount': n_alert,
            'strongCount': n_strong,
            'totalCount': len(items),
            'etfs': items,
        })

    groups_out.sort(key=lambda g: (STATE_ORDER.index(g['state']) if g['state'] in STATE_ORDER else 9,
                                   -(g['avgRatio'] or 0)))

    ok_rows = [x for x in flat if x.get('ratio') is not None]
    summary = {
        'strongCount': sum(1 for x in flat if x.get('state') == '显著放量'),
        'alertCount': sum(1 for x in flat if x.get('state') in ('显著放量', '放量')),
        'totalCount': len(flat),
        'maxRatio': round(max((x['ratio'] for x in ok_rows), default=0), 3) if ok_rows else None,
        'avgRatio': round(sum(x['ratio'] for x in ok_rows) / len(ok_rows), 3) if ok_rows else None,
    }

    progress, used_min, in_session = trade_progress(now)
    output = {
        'code': 200,
        'data': {
            'summary': summary,
            'groups': groups_out,
            'thresholds': {'alert': R_ALERT, 'strong': R_STRONG},
            'params': {'baseDaysFast': BASE_DAYS_FAST, 'baseDaysSlow': BASE_DAYS_SLOW,
                       'minBaseDays': MIN_BASE_DAYS},
            'progress': round(progress, 4),
            'usedMinutes': used_min,
            'inSession': in_session,
            'marketStatus': status,
            'quoteDate': flat[0].get('date') if flat else None,
            'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
            'dataSource': '腾讯分时(minute/query) + 30分钟K线(mkline m30) 基准',
            'costMs': int((time.time() - t0) * 1000),
        },
    }

    # 回写缓存（分时与基准分开过期）
    _cache_write({'minute': minute_cache, 'base': base_cache})
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({'code': 500, 'message': f'{type(e).__name__}: {e}'},
                         ensure_ascii=False))
        sys.exit(0)   # 用 JSON 报错，不要非零退出码
