#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国家队监控：主流宽基 ETF 实时成交额异动预警

思路（刻意保持简单，只做一个"预警器"，不做二次判断）：
    量比 R = 今日累计成交额 ÷ 近 N 日「同一进度」的平均累计成交额

        R >= 2.0        →  显著放量
        1.5 <= R < 2.0  →  放量
        R < 1.5         →  正常

同一指数的多只 ETF 同时放量，比单只放量的可信度高得多，所以按指数分组并给出组内同步度。

为什么用成交额而不是成交量：
    1) 成交量（手）跨品种不可比——同样放量 2 倍，2.5 元的创业板ETF 与 4.2 元的
       沪深300ETF 对应的资金规模完全不同；
    2) 份额拆分/分红除权会让成交量跳变但成交额不变，用成交量会误报；
    3) 成交量含价格波动噪音，实测成交额的量比 CV 在各品种上都更低
       （创业板 0.400 vs 0.457、科创50 0.368 vs 0.437）。

数据链路：
    1) 实时当日：腾讯 minute/query  → 1 分钟一个点，[累计量(手), 累计额(元)]
    2) 历史基准：新浪 30 分钟 K 线   → 每根 bar 自带 amount 字段，datalen 上限 1023 ≈ 128 个交易日
    3) 兜底：    腾讯日线 newfqkline → 分钟线不足时用日线 20 日均额 × 日内累计占比曲线折算

    注意：腾讯的 mkline m30 第 7 个字段【不是】成交额（逐 bar 反推比例漂移，是笔数之类），
    所以历史基准必须走新浪。新浪分钟线成交额与日线官方值分毫不差（190.07 亿对 190.07 亿）。

关键实现细节：
    * 30 分钟 bar 边界正好落在 10:00/10:30/11:00/11:30/13:30/14:00/14:30/15:00 八个整点收盘，
      所以「当前进度」在这 8 个锚点上可以零误差读取真实基准；不在锚点时用累计占比曲线线性插值。
    * 开盘前 15 分钟样本太少、量比失真，不出信号。
    * 14:45 之后基准曲线尾部斜率陡（15:00 那根 bar 的 CV=1.61），改用全天量比更稳。
    * 时区：所有时间一律用北京时间（服务器是 UTC，务必显式转换）。
"""
import sys
import os
import json
import time
import concurrent.futures as _fut
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
# 新浪 datalen：20 日基准 × 8 根 = 160，取 168 留一根缓冲（≈21 个交易日）。
# 不拉满接口上限 1023 根——18 只标的每次都传 1000+ 条纯属浪费（27KB vs 21KB/只）。
SINA_MAX_BARS = 168
SINA_BARS_LIMIT = 1023    # 接口硬上限（实测 2048 会报错），仅作记录
MIN_BASE_DAYS = 3          # 少于这么多完整交易日就不出量比（直接标数据不足）
OPEN_QUIET_MIN = 15        # 开盘前 N 分钟不出信号
TAIL_SWITCH = '14:45'      # 这个时间之后改用全天量比

# ============== 缓存 ==============
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CACHE_FILE = os.path.join(CACHE_DIR, 'national_team_cache.json')
MINUTE_TTL = 55            # 实时分时缓存秒数（盘中）
# 历史基准按「日」缓存，不按小时。
# 基准是「近 N 日的 30 分钟 bar 累计额」，一天只变一次（收盘后），盘中完全不变；
# 原来设 4 小时 TTL，盘中会整批过期一次、18 只同时重拉新浪，白白慢几秒。
# 现在只要 date 是今天且已落盘，就直接复用——和超跌/轮动策略一样吃本地缓存。
BASE_TTL = 24 * 3600
# 并发拉取线程数。18 只标的之间毫无依赖，串行纯粹是排队等网络：
# 单只约 440ms（分时 + 基准两个请求），串行 18 只 ≈ 6.6s，并发后 ≈ 0.9s。
MAX_WORKERS = 10

# ============== 网络 ==============
CONNECT_TIMEOUT = 2.5
READ_TIMEOUT = 8.0
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Referer': 'https://gu.qq.com/',
}
# 腾讯：当日 1 分钟分时（[累计量(手), 累计额(元)]）+ 日线兜底
TX_MINUTE = 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/minute/query?code={}'
TX_DAY = 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get?param={},day,,,{},qfq'
# 腾讯：批量行情（一次请求多只，主数据路径）
TX_QUOTE_BATCH = 'https://qt.gtimg.cn/q='

# 新浪：30 分钟 K 线，自带 amount（元）。
# 这是唯一能拿到分钟级成交额的免费源（腾讯 m30 没有 amount 字段）。
SINA_KLINE = ('https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService'
              '.getKLineData?symbol={}&scale=30&ma=no&datalen=' + str(SINA_MAX_BARS))
SINA_HEADERS = {
    'User-Agent': HEADERS['User-Agent'],
    'Referer': 'https://finance.sina.com.cn/',
}
# 新浪批量行情：腾讯 qt.gtimg.cn 不通时的第二源（例如某些机房到腾讯的链路被限）
SINA_QUOTE = 'https://hq.sinajs.cn/list={}'

# 报价新鲜度阈值（分钟）。盘中报价时间落后超过这个数，就不认为拿到的
# "今日累计成交额"还是今天的——宁可显示「无数据」，也不能把 0 当成"没放量"。
# 这个阈值存在的理由：2026-11-05 线上出现过分时接口从 09:30 起全部失败、
# 页面却一路显示「今日成交额 0.00 亿 / 量比 0.00x / 状态：正常」的事故，
# 看起来像"今天特别冷清"，实际是数据源断了，属于最坏的一种误导。
QUOTE_STALE_MIN = 12

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


def fetch_quotes_batch(symbols):
    """批量行情：一次请求拿全部标的的现价/涨跌/成交额。

    https://qt.gtimg.cn/q=sh510300,sz159915,...  返回 GBK 文本，每行一只。

    字段（~ 分隔）：
        [1] 名称   [3] 现价   [4] 昨收   [32] 涨跌幅%
        [33] 最高  [34] 最低   [36] 成交量(手)  [37] 成交额(万元)
        [30] 报价时间 YYYYMMDDHHMMSS

    这是本策略的主数据路径：18 只标的 1 个请求搞定，替代原来 18 次
    minute/query（一次只能查一只）。已验证 [37] 与分时累计额完全一致
    （沪深300ETF：1,256,222 万 = 125.62 亿）。

    返回 {symbol: {'price','prevClose','changePct','amount','volume','quoteTime'}}
    """
    out = {}
    if not symbols:
        return out
    url = TX_QUOTE_BATCH + ','.join(symbols)
    r = requests.get(url, headers=HEADERS, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    r.encoding = 'gbk'
    if r.status_code != 200:
        raise RuntimeError(f'批量行情 HTTP {r.status_code}')
    for line in r.text.strip().split('\n'):
        if '="' not in line:
            continue
        head, body = line.split('="', 1)
        symbol = head.replace('v_', '').strip()
        fields = body.rstrip('";').split('~')
        if len(fields) < 38:
            continue

        def _f(idx):
            try:
                return float(fields[idx])
            except (TypeError, ValueError, IndexError):
                return None

        amt_wan = _f(37)
        out[symbol] = {
            'name': fields[1],
            'price': _f(3),
            'prevClose': _f(4),
            'changePct': _f(32),
            'volume': _f(36),
            'amount': amt_wan * 1e4 if amt_wan is not None else None,   # 万元 → 元
            'quoteTime': fields[30] if len(fields) > 30 else '',
        }
    return out


def _parse_quote_time(s):
    """'20261105161455' → naive 北京时间（与 bj_now() 同口径）。解析不了返回 None。"""
    if not s or len(s) < 12:
        return None
    try:
        return datetime.strptime(s[:14].ljust(14, '0'), '%Y%m%d%H%M%S')
    except Exception:
        return None


def quote_stale_reason(now, quote_time):
    """判断报价是否已经过期。返回 '' 表示新鲜，否则返回给人看的原因。

    三种过期形态，线上都真实出现过：
      1) 报价日期不是今天 —— 整段数据都是昨天的，最常见；
      2) 盘中报价时间停住 —— 数据源中途挂了，值一直停在断点（11-05 事故就是这种：
         从 09:30 起接口全失败，页面显示"今日成交额 0.00 亿、状态正常"）；
      3) 收盘后报价还停在 15:00 之前 —— 说明收盘数据没送到。
    """
    dt = _parse_quote_time(quote_time)
    if dt is None:
        return '行情快照缺少时间戳'
    status = market_status(now)
    # 周末/盘前没有"今天的行情"这回事，最后交易日的数据就是最新数据
    if status in ('休市', '未开盘'):
        return '' if (now.date() - dt.date()).days <= 5 else f'行情停留在 {dt.strftime("%m-%d %H:%M")}'
    if dt.date() < now.date():
        return f'行情停留在 {dt.strftime("%m-%d %H:%M")}'
    if dt > now + timedelta(minutes=3):
        return ''          # 服务器时钟略快于行情源，不算过期
    age = (now - dt).total_seconds() / 60
    if status in ('交易中', '开盘观察中', '午休', '尾盘'):
        if age > QUOTE_STALE_MIN:
            return f'行情已 {age:.0f} 分钟未更新（停在 {dt.strftime("%H:%M")}）'
        return ''
    if status == '已收盘':
        # 收盘后要求报价时间至少到 15:00，否则今天这根 K 线还没走完
        if dt.strftime('%H%M') < '1500':
            return f'行情停在 {dt.strftime("%H:%M")}，今日收盘数据未到'
        return ''
    return ''              # 其余状态不判过期


def _fetch_sina_quotes(symbols):
    """新浪批量行情（备用源）。一次请求拿全部标的。

    https://hq.sinajs.cn/list=sh510300,sz159919
    返回 GBK：var hq_str_sh510300="名称,今开,昨收,现价,最高,最低,...,成交量(股),成交额(元),...,日期,时间,状态";

    和腾讯的差别：新浪给的是**股**和**元**（腾讯是手和万元），字段位置也不同，
    所以单独解析、统一成同一套结构，上层完全无感。
    """
    out = {}
    if not symbols:
        return out
    r = requests.get(SINA_QUOTE.format(','.join(symbols)), headers=SINA_HEADERS,
                     timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    r.encoding = 'gbk'
    if r.status_code != 200:
        raise RuntimeError(f'新浪行情 HTTP {r.status_code}')
    for line in r.text.strip().split('\n'):
        if 'hq_str_' not in line or '="' not in line:
            continue
        head, body = line.split('="', 1)
        symbol = head.split('hq_str_')[-1].strip()
        f = body.rstrip('";').split(',')
        if len(f) < 32 or not f[0]:
            continue

        def _f(idx):
            try:
                return float(f[idx])
            except (TypeError, ValueError, IndexError):
                return None

        price, prev = _f(3), _f(2)
        chg = None
        if price is not None and prev:
            chg = (price / prev - 1) * 100
        qt = (f[30].replace('-', '') + f[31].replace(':', '')) if f[30] else ''
        out[symbol] = {
            'name': f[0],
            'price': price,
            'prevClose': prev,
            'changePct': chg,
            'volume': _f(8),
            'amount': _f(9),
            'quoteTime': qt,
        }
    return out


def fetch_quotes(symbols):
    """取批量行情，返回 (quotes, 源名, 失败原因)。

    两个源任一成功即返回；都失败返回 ({}, '', 原因)，由上层降级成"数据不足"，
    **绝不静默退回 0**——0 会被前端读成"今天没成交"。
    """
    errs = []
    try:
        q = fetch_quotes_batch(symbols)
        if q:
            return q, '腾讯', ''
        errs.append('腾讯返回空')
    except Exception as e:
        errs.append(f'腾讯 {type(e).__name__}: {str(e)[:70]}')
    try:
        q = _fetch_sina_quotes(symbols)
        if q:
            return q, '新浪', ''
        errs.append('新浪返回空')
    except Exception as e:
        errs.append(f'新浪 {type(e).__name__}: {str(e)[:70]}')
    return {}, '', '；'.join(errs)


def fetch_minute(symbol):
    """当日 1 分钟分时（兜底用：批量行情失败时才走这里）。

    返回 (日期'YYYY-MM-DD', [(HHMM, 价, 累计量手, 累计额元), ...], 涨跌幅%, 昨收价)

    腾讯原始格式：'0930 4.086 51874 21195716.00' = 时间 价 累计量(手) 累计额(元)
    累计额是可用的——已验证 15:00 的累计额与日线官方成交额完全一致。
    涨跌幅来自同响应的 qt 节点：[4]=昨收、[32]=涨跌幅%，不必额外请求。
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
        if len(parts) < 4:
            continue
        try:
            points.append((parts[0], float(parts[1]), float(parts[2]), float(parts[3])))
        except ValueError:
            continue

    # 涨跌幅：qt 节点字段 [4]=昨收 [32]=涨跌幅%
    change_pct = None
    prev_close = None
    qt = (node.get('qt') or {}).get(symbol) or []
    if len(qt) > 32:
        try:
            prev_close = float(qt[4])
        except (TypeError, ValueError):
            prev_close = None
        try:
            change_pct = float(qt[32])
        except (TypeError, ValueError):
            # 兜底：用现价/昨收 现算
            if prev_close and points:
                change_pct = (points[-1][1] / prev_close - 1) * 100
    return date, points, change_pct, prev_close


def fetch_m30_amount(symbol):
    """30 分钟历史 bar（含成交额）。返回 [(日期'YYYY-MM-DD', HHMM, 额元), ...]。

    走新浪 CN_MarketDataService.getKLineData：每根 bar 直接给 amount（元）。
    已验证聚合值与日线官方成交额分毫不差（沪深300ETF 11-03: 190.07 亿）。
    """
    r = requests.get(SINA_KLINE.format(symbol), headers=SINA_HEADERS,
                     timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    r.raise_for_status()
    rows = r.json() or []
    out = []
    for row in rows:
        day = str(row.get('day') or '')
        if len(day) < 16:
            continue
        try:
            amt = float(row.get('amount') or 0)
        except (TypeError, ValueError):
            continue
        if amt <= 0:
            continue
        out.append((day[:10], day[11:13] + day[14:16], amt))
    return out


def fetch_day_amount(symbol, n=25):
    """日线成交额（万元 → 元），用于分钟线不足时兜底。返回 [(日期, 额元), ...]。"""
    j = _get_json(TX_DAY.format(symbol, n))
    node = (j.get('data') or {}).get(symbol) or {}
    rows = node.get('qfqday') or node.get('day') or []
    out = []
    for row in rows:
        if len(row) < 9:
            continue
        try:
            out.append((row[0], float(row[8]) * 1e4))   # 万元 → 元
        except (TypeError, ValueError):
            continue
    return out


def _day_close_map(symbol):
    """近 90 个交易日的收盘价 {YYYYMMDD: close}，用于把份额变动换算成金额。

    只用腾讯一条日线请求，带按日缓存（收盘价一天只变一次），
    18 只标的首日各花 ~60ms，之后全部命中缓存。
    """
    today = bj_now().strftime('%Y%m%d')
    hit = _DAY_CLOSE_CACHE.get(symbol)
    if hit and hit.get('date') == today:
        return hit['map']
    out = {}
    try:
        j = _get_json(TX_DAY.format(symbol, 120))
        node = (j.get('data') or {}).get(symbol) or {}
        rows = node.get('qfqday') or node.get('day') or []
        for row in rows:
            if len(row) < 3:
                continue
            try:
                out[str(row[0]).replace('-', '')] = float(row[2])   # [日期, 开, 收, ...]
            except (TypeError, ValueError):
                continue
    except Exception as e:
        _log(f'{symbol} 日线收盘失败: {type(e).__name__}: {e}')
    if out:
        _DAY_CLOSE_CACHE[symbol] = {'date': today, 'map': out}
    return out


_DAY_CLOSE_CACHE = {}


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
    """从 30 分钟 bar 构建基准（近 5 日均值为主，20 日均值为辅）。

    入参 bar 的第三元素是成交额（元）。
    返回 dict：
        cumMedian:  {slot: 近5日各锚点平均累计额}     ← 量比分母（主基准）
        cumSlow:    {slot: 近20日各锚点平均累计额}    ← 参考显示
        ratios:     {slot: 累计额占全天占比}（近5日）
        total:      近5日全天平均额（元）
        totalSlow:  近20日全天平均额
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

    # 逐日累计序列（每项是 8 个锚点的累计额），供历史分位直接复用，
    # 避免算分位时再拉一遍新浪数据。
    day_cum = []
    for d in slow_days:
        row = []
        for i, s in enumerate(SLOTS):
            row.append(sum(by_day[d][x] for x in SLOTS[:i + 1]))
        day_cum.append(row)

    return {
        'cumMedian': cum,
        'cumSlow': cum_slow,
        'ratios': {s: cum[s] / total for s in SLOTS},
        'total': total,
        'totalSlow': cum_slow['1500'],
        'days': len(fast_days),
        'daysSlow': len(slow_days),
        'dayCum': day_cum,
    }


def base_curve_at(base, now_min):
    """给定当前时刻（含零点分钟数），返回「同进度基准累计成交额」（近5日均值）。

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


def analyze_one(symbol, name, now, quotes, minute_cache, base_cache):
    """算一只 ETF 的量比。返回结果 dict。

    quotes: fetch_quotes() 的批量结果（主路径，缺这一项时才回落到单只分时）。
    """
    today = now.strftime('%Y-%m-%d')

    q = quotes.get(symbol) or {}
    date = today
    price = q.get('price')
    today_cum = q.get('amount') or 0.0        # 累计成交额（元）
    change_pct = q.get('changePct')
    prev_close = q.get('prevClose')
    last_hhmm = ''
    qt = q.get('quoteTime') or ''
    if len(qt) >= 12:
        last_hhmm = qt[8:12]
        date = f'{qt[:4]}-{qt[4:6]}-{qt[6:8]}'

    # ---- 批量行情没拿到这只时，才单独拉分时（兜底，走缓存）----
    if not q or today_cum <= 0:
        mk = minute_cache.get(symbol)
        if not mk or time.time() - mk.get('ts', 0) > MINUTE_TTL:
            try:
                d, points, chg, prev = fetch_minute(symbol)
                mk = {'ts': time.time(), 'date': d, 'points': points,
                      'changePct': chg, 'prevClose': prev}
                minute_cache[symbol] = mk
            except Exception as e:
                _log(f'{symbol} 分时兜底失败: {type(e).__name__}: {e}')
                if not mk:
                    return {'symbol': symbol, 'name': name, 'state': '数据不足',
                            'error': f'行情获取失败: {type(e).__name__}'}
        points = mk.get('points') or []
        if points:
            date = mk.get('date') or today
            price = points[-1][1]
            today_cum = points[-1][3]
            last_hhmm = points[-1][0]
            # 分时只给 HHMM，拼上快照日期才能判断这份数据是哪天的
            qt = f"{date.replace('-', '')}{last_hhmm}00" if last_hhmm else qt
        change_pct = mk.get('changePct')
        prev_close = mk.get('prevClose')

    # ---- 新鲜度闸门：过期就把数字清空，绝不让 0 冒充"今天没成交" ----
    stale = quote_stale_reason(now, qt)
    if stale:
        return {'symbol': symbol, 'name': name, 'date': date,
                'price': None, 'prevClose': None, 'changePct': None,
                'todayAmount': None, 'baseAmount': None, 'baseAmountSlow': None,
                'ratio': None, 'ratioSlow': None, 'percentile': None,
                'state': '数据不足', 'error': stale, 'quoteStale': True,
                'basis': '', 'lastBar': last_hhmm,
                'baseMode': None, 'baseNote': None,
                'baseDays': None, 'baseDaysSlow': None}
    if today_cum <= 0:
        # 时间戳是新鲜的但成交额还是 0（刚开盘还没撮合完）：
        # 这时候算出来必然是 0.00x，画在页面上会被读成"成交极度萎缩"。
        return {'symbol': symbol, 'name': name, 'date': date,
                'price': price, 'prevClose': prev_close,
                'changePct': round(change_pct, 2) if change_pct is not None else None,
                'todayAmount': None, 'baseAmount': None, 'baseAmountSlow': None,
                'ratio': None, 'ratioSlow': None, 'percentile': None,
                'state': '数据不足', 'error': '今日暂无成交额', 'quoteStale': False,
                'basis': '', 'lastBar': last_hhmm,
                'baseMode': None, 'baseNote': None,
                'baseDays': None, 'baseDaysSlow': None}

    # ---- 基准（按日缓存）----
    bk = base_cache.get(symbol)
    if not bk or bk.get('date') != today or time.time() - bk.get('ts', 0) > BASE_TTL:
        try:
            bars = fetch_m30_amount(symbol)
            base = build_base(bars)
            if base:
                base['mode'] = 'm30'
                base['note'] = f"近{base['days']}日均值基准"
            else:
                # 兜底：日线均额 × 日内累计占比（分钟线缺失时）
                days = fetch_day_amount(symbol, 25)
                amts = [v for d, v in days if d != today][-BASE_DAYS_FAST:]
                if len(amts) >= MIN_BASE_DAYS:
                    avg = sum(amts) / len(amts)
                    # 无分钟线时只能用经验曲线（全市场通用形状）
                    ratios = {'1000': 0.243, '1030': 0.335, '1100': 0.442,
                              '1130': 0.507, '1330': 0.578, '1400': 0.662,
                              '1430': 0.780, '1500': 1.0}
                    slow_map = {s: avg * ratios[s] for s in SLOTS}
                    base = {
                        'cumMedian': dict(slow_map),
                        'cumSlow': dict(slow_map),
                        'ratios': ratios, 'total': avg,
                        'totalSlow': avg, 'days': len(amts), 'daysSlow': len(amts),
                        'mode': 'day_est',
                        'note': f'日线 {len(amts)} 日均额 × 日内曲线（估算）',
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
                'price': price, 'todayAmount': today_cum,
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
    # 直接用建基准时就已算好的逐日累计序列，不再第二次拉新浪。
    # （原来这里会重新 fetch 一遍全量 bar，每只多花 ~100ms，18 只就是 1.8 秒）
    pct = None
    if base.get('mode') == 'm30':
        hist_ratios = []
        for day_acc in base.get('dayCum') or []:
            acc = 0.0
            for i, s in enumerate(SLOTS):
                if _minutes(f'{s[:2]}:{s[2:]}') <= now_min:
                    acc = day_acc[i]
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
        'prevClose': prev_close,
        'changePct': round(change_pct, 2) if change_pct is not None else None,
        'todayAmount': today_cum,
        'baseAmount': round(base_vol, 0),
        'baseAmountSlow': round(base_vol_slow, 0) if base_vol_slow else None,
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
    """为了算历史分位，暂存当日拉到的 30 分钟原始 bar（不落盘）。"""
    hit = _BARS_CACHE.get(symbol)
    if hit and hit.get('date') == bj_now().strftime('%Y-%m-%d'):
        return hit['bars']
    try:
        bars = fetch_m30_amount(symbol)
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

    symbols = [(s, n) for grp in WATCH_GROUPS for s, n in grp['etfs']]

    # ---- 主路径：一次批量请求拿全部标的的现价/涨跌/成交额（腾讯→新浪双源）----
    quotes, quote_src, quote_err = fetch_quotes([s for s, _ in symbols])
    _log(f'批量行情 {len(quotes)}/{len(symbols)} 只，源={quote_src or "无"}  {quote_err}')

    # ---- 并发计算：18 只标的互相独立，串行只是排队等网络 ----
    def _work(pair):
        symbol, name = pair
        try:
            return symbol, analyze_one(symbol, name, now, quotes,
                                       minute_cache, base_cache)
        except Exception as e:
            _log(f'{symbol} 异常: {type(e).__name__}: {e}')
            return symbol, {'symbol': symbol, 'name': name, 'state': '数据不足',
                            'error': str(e)[:120]}

    rows_by_symbol = {}
    with _fut.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for symbol, row in ex.map(_work, symbols):
            rows_by_symbol[symbol] = row

    # ---- 一级市场净申赎（份额口径，T+1 披露）----
    # 与量比完全独立的一条线：量比看二级市场成交，净申赎看一级市场真实申购赎回。
    # 份额数据由 etf_share_flow 负责抓取/累积/回补，这里的失败一律降级为 None，
    # 绝不影响量比主逻辑（份额源不可用是很常见的，深交所站点尤其不稳）。
    #
    # 放在行情算完之后：换算金额要用「变动日的收盘价」，而收盘价的最终来源是
    # analyze_one（批量行情挂了还有分时兜底）。原来在行情之前算、只认批量行情，
    # 结果行情源一断，份额明明算得出来，金额却整列变 None。
    share_map = {}
    share_asof = None
    share_asof_min = None
    share_days = None
    try:
        import etf_share_flow as _sf
        payload = _sf.ensure_history([s for s, _ in symbols], allow_backfill=False)
        # 价格序列：历史日从日线补（只对 sh 有全量历史），最后一日优先用现价
        for s, _ in symbols:
            try:
                pm = _day_close_map(s)
                row = rows_by_symbol.get(s) or {}
                res = _sf.compute_one(payload, s, price_today=row.get('price'),
                                      price_map=pm)
                share_map[s] = res
            except Exception as e:
                _log(f'{s} 净申赎计算失败: {type(e).__name__}: {e}')
        if share_map:
            asofs = [v.get('asOf') for v in share_map.values() if v.get('asOf')]
            share_asof = max(asofs) if asofs else None
            # 沪深披露时点不同：上交所 T 日盘后就有，深交所 T+1 傍晚才更新，
            # 所以同一次监控里两端 asOf 会差一天，单独给出最早那天，前端显示成区间。
            share_asof_min = min(asofs) if asofs else None
            ds = [v.get('days') for v in share_map.values() if v.get('days')]
            share_days = max(ds) if ds else None
        _log(f'净申赎 {len(share_map)} 只，asOf={share_asof}')
    except Exception as e:
        _log(f'净申赎模块失败（降级为无数据）: {type(e).__name__}: {e}')

    groups_out = []
    flat = []
    for grp in WATCH_GROUPS:
        # 按 WATCH_GROUPS 原顺序取回，组内顺序稳定
        items = [rows_by_symbol.get(s) or {
            'symbol': s, 'name': n, 'state': '数据不足', 'error': '未返回'}
            for s, n in grp['etfs']]
        # 挂上净申赎（一级市场份额口径，T+1 披露）
        # 金额和份额一起给：金额=Δ份额×收盘价，会被单价放大；
        # 份额才是申赎行为本身，也是交易所官方口径，两个并列才能对照。
        for it in items:
            sf = share_map.get(it.get('symbol')) or {}
            it['netAmount'] = round(sf['netAmount'], 0) if sf.get('netAmount') is not None else None
            it['netShares'] = round(sf['netShares'], 0) if sf.get('netShares') is not None else None
            it['net5Amount'] = round(sf['net5Amount'], 0) if sf.get('net5Amount') is not None else None
            it['net5Shares'] = round(sf['net5Shares'], 0) if sf.get('net5Shares') is not None else None
            it['netPercentile'] = sf.get('percentile')
            it['netAsOf'] = sf.get('asOf')
            it['netDays'] = sf.get('days')
            it['netNote'] = sf.get('note') or ''
        flat.extend(items)

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
    # 份额是官方口径、永远算得出来；金额要靠「变动日收盘价」折算，行情源一断就没有。
    # 所以合计条以份额为准统计覆盖数与净申购/净赎回只数，金额缺了就留空，
    # 不能让金额缺失把整条汇总一起拖没（那正是 11-05 页面上汇总区消失的原因）。
    share_rows = [x for x in flat if x.get('netShares') is not None]
    net_rows = [x for x in share_rows if x.get('netAmount') is not None]
    summary = {
        'strongCount': sum(1 for x in flat if x.get('state') == '显著放量'),
        'alertCount': sum(1 for x in flat if x.get('state') in ('显著放量', '放量')),
        'totalCount': len(flat),
        'maxRatio': round(max((x['ratio'] for x in ok_rows), default=0), 3) if ok_rows else None,
        'avgRatio': round(sum(x['ratio'] for x in ok_rows) / len(ok_rows), 3) if ok_rows else None,
        # 一级市场：全样本合计净申赎（正=净申购）
        'netTotal': round(sum(x['netAmount'] for x in net_rows), 0) if net_rows else None,
        'netTotal5': round(sum(x['net5Amount'] for x in net_rows), 0) if net_rows else None,
        # 份额合计：与金额并列，用于对照「金额大到底是申赎多还是单价高」
        'netSharesTotal': (round(sum(x['netShares'] for x in share_rows), 0)
                           if share_rows else None),
        'netSharesTotal5': (round(sum(x['net5Shares'] for x in share_rows
                                      if x.get('net5Shares') is not None), 0)
                            if share_rows else None),
        'netInflowCount': sum(1 for x in share_rows if x['netShares'] > 0),
        'netOutflowCount': sum(1 for x in share_rows if x['netShares'] < 0),
        'netCount': len(share_rows),
    }

    progress, used_min, in_session = trade_progress(now)
    stale_rows = [x for x in flat if x.get('quoteStale')]
    # 报价时间取全体最新的一条，作为"这批行情到底停在几点"的单一证据
    quote_minutes = [x.get('lastBar') for x in flat if x.get('lastBar')]
    output = {
        'code': 200,
        'data': {
            'summary': summary,
            'groups': groups_out,
            'thresholds': {'alert': R_ALERT, 'strong': R_STRONG},
            'params': {'baseDaysFast': BASE_DAYS_FAST, 'baseDaysSlow': BASE_DAYS_SLOW,
                       'minBaseDays': MIN_BASE_DAYS,
                       'netPctDays': 60, 'netMinDays': 20},
            'progress': round(progress, 4),
            'usedMinutes': used_min,
            'inSession': in_session,
            'marketStatus': status,
            'quoteDate': flat[0].get('date') if flat else None,
            # 行情链路自检：源是谁、失败原因、有多少只是因为过期被清空。
            # 页面据此显示红色提示条——「数据没拿到」必须比「数据是 0」更显眼。
            'quoteSource': quote_src or None,
            'quoteError': quote_err or None,
            'quoteStaleCount': len(stale_rows),
            'quoteStaleNote': stale_rows[0].get('error') if stale_rows else None,
            'quoteLastBar': max(quote_minutes) if quote_minutes else None,
            'shareAsOf': share_asof,
            'shareAsOfMin': share_asof_min,
            'shareDays': share_days,
            'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
            'dataSource': '腾讯/新浪批量行情(现价+成交额) + 新浪30分钟额基准',
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
