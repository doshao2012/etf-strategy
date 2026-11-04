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
      实测可回溯到 2026-04 及更早（800~920 只）。→ 可算 60 日分位，但**只能逐日拉**，
      补 60 天就是 60 次请求，因此回补放在独立进程（--backfill）里跑。
    * 深交所：官方「基金规模 - ETF规模」页面有区间导出接口，
      ``www.szse.cn/api/report/ShowReport?CATALOGID=scsj_fund_jjgm&jjlb=ETF&txtStart&txtEnd``
      一次请求（40 自然日）就返回全市场每日规模（约 8000~9000 行 / 260KB），
      60 个交易日只需 3 次请求。**注意**：T 日份额要 T+1 傍晚才更新，
      上午请求 txtEnd=今天 只会返回到前一交易日——所以写入时一律用
      **接口返回的日期字段**做键，绝不能用「今天」，否则会造出连续两天份额相同、
      净申赎恒为 0 的伪数据（见 _prune_fake_szse 兜底）。

    因此本模块的策略是「当日快照 + 按需回补」：
      1. 每次调用先把最近 7~10 天的沪深份额补齐（带限流，正常只一两个请求）
      2. --backfill 独立进程负责把历史补到 60 天以上（沪逐日、深按区间）
      3. 盘中监控（monitor_national_team）传 allow_backfill=False，只读不算，绝不阻塞量比

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
    return fetch_szse_range(None, None)


def fetch_szse_range(start_date, end_date):
    """深交所历史规模（带日期区间，可一次拉全市场多日）。

    这是深交所官方「数据 - 基金数据 - 基金规模 - ETF规模」页面的导出接口
    （www.szse.cn/market/fund/volume/lof/index.html），
    CATALOGID=scsj_fund_jjgm + jjlb=ETF + txtStart/txtEnd。

    实测一次请求（约 11 个交易日）可返回 8000+ 行，覆盖全市场 ETF 每日规模，
    单次约 260KB。日期区间不宜过大，按段拉取更稳。

    返回 {YYYYMMDD: {纯代码: 份额}}，失败返回 {}。
    """
    try:
        import io
        import requests
        import pandas as pd
    except Exception:
        return {}

    url = 'https://www.szse.cn/api/report/ShowReport'
    params = {'CATALOGID': 'scsj_fund_jjgm', 'SHOWTYPE': 'xlsx', 'TABKEY': 'tab1',
              'jjlb': 'ETF', 'random': str(time.time())}
    if start_date:
        params['txtStart'] = _dash(start_date)
    if end_date:
        params['txtEnd'] = _dash(end_date)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                             '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
               'Referer': 'https://www.szse.cn/market/fund/volume/lof/index.html'}
    # 深交所站点抖动大，实测经常首次连接就断，多试几次
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=(5, SZSE_TIMEOUT))
            if r.status_code != 200 or len(r.content) < 5000:
                raise RuntimeError(f'HTTP {r.status_code} / {len(r.content)}B')
            df = pd.read_excel(io.BytesIO(r.content), dtype={'基金代码': str})
            if '基金代码' not in df.columns:
                return {}
            out = {}
            for _, row in df.iterrows():
                code = str(row.get('基金代码', '')).strip().zfill(6)
                day = str(row.get('日期', ''))[:10].replace('-', '')
                # 规模单位是「份」（表头写基金规模(份)）
                sh = _clean_num(row.get('基金规模(份)'))
                if not code or not day or not sh or sh <= 0:
                    continue
                out.setdefault(day, {})[code] = sh
            return out
        except Exception as e:
            if attempt < 3:
                time.sleep(2 + attempt * 2)
                continue
            print(f'[share] 深交所 {start_date}~{end_date} 抓取失败: '
                  f'{type(e).__name__}: {e}', file=sys.stderr)
            return {}
    return {}


def _dash(d):
    """YYYYMMDD → YYYY-MM-DD"""
    return f'{d[:4]}-{d[4:6]}-{d[6:8]}' if d and len(d) == 8 else d


def backfill_szse(payload, days, symbols=None, target_days=PERCENTILE_DAYS):
    """用深交所历史规模接口按区间回补，一次补多天，比逐日探测快得多。

    接口按日期区间返回全市场，所以策略是「大区间分段倒着拉」：
    从今天开始，每段往回 40 个自然日（≈28 个交易日），
    累积到 target_days 天就停。最多 6 段（≈240 自然日），避免被单次调用拖太久。

    symbols：本次关心的标的，用于判断「够不够」。不给就按全市场深市代码数判断。
    """
    sz_codes = [s[2:] for s in (symbols or []) if s.startswith('sz')]

    def _have_days():
        if sz_codes:
            return sum(1 for d in days if any(c in days[d] for c in sz_codes))
        return sum(1 for d in days if _szse_count(days[d]) > 0)

    if _have_days() >= target_days:
        return payload

    end = datetime.now()
    total_added = 0
    for seg in range(6):
        if _have_days() >= target_days:
            break
        start = end - timedelta(days=40)
        s, e = start.strftime('%Y%m%d'), end.strftime('%Y%m%d')
        got = fetch_szse_range(s, e)
        if not got:
            break
        added = 0
        for day, m in got.items():
            # 已经有的日子不覆盖（当日快照可能更完整）
            if _szse_count(days.get(day, {})) > 0:
                continue
            days.setdefault(day, {}).update(m)
            added += 1
        total_added += added
        print(f'[share] 深交所回补 {s}~{e}: +{added} 天（累计 {_have_days()} 天）',
              file=sys.stderr, flush=True)
        if added == 0 and seg >= 1:
            # 连续两段都空，基本可以判定再往前也没数据了
            break
        end = start - timedelta(days=1)

    if total_added:
        meta = payload.setdefault('meta', {})
        meta['lastSzseBackfillTs'] = time.time()
        meta['lastSzseBackfillAdded'] = total_added
        _save(payload)
    return payload


def _szse_count(mapping):
    """该日有多少条深市代码（6 位、以 15/16/18 开头视为深市）"""
    if not mapping:
        return 0
    return sum(1 for c in mapping if c[:2] in ('15', '16', '18'))


def _shift_day(d, offset):
    try:
        return (datetime.strptime(d, '%Y%m%d') + timedelta(days=offset)).strftime('%Y%m%d')
    except Exception:
        return d


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


def _prune_fake_szse(days):
    """清理「份额与前一交易日完全相同」的深市最新一天。

    为什么需要这一步：深交所份额 T+1 傍晚更新，如果程序在披露前请求，
    接口会安静地返回上一个交易日的数据。早期版本把返回值记到了请求日期上，
    造成 T 日和 T-1 日份额一模一样、净申赎恒为 0。
    这里做一次兜底：只检查**最后两个交易日**，若某标的连续两日份额完全相同
    （且非零），说明后一天大概率是伪数据，把该天的深市代码整批删掉。
    """
    ds = sorted(d for d in days if _szse_count(days[d]) > 0)
    if len(ds) < 2:
        return 0
    last, prev = ds[-1], ds[-2]
    cur, old = days.get(last) or {}, days.get(prev) or {}
    same = [c for c in cur
            if c[:2] in ('15', '16', '18') and c in old and cur[c] == old[c]]
    sz_cur = _szse_count(cur)
    if sz_cur == 0:
        return 0
    # 超过 90% 的标的数值完全没动 → 判定为伪数据
    if len(same) / sz_cur > 0.9:
        for c in list(cur):
            if c[:2] in ('15', '16', '18'):
                del cur[c]
        print(f'[share] {last} 深市数据与 {prev} 完全相同（{len(same)}/{sz_cur}），'
              f'判定为未更新，已剔除', file=sys.stderr, flush=True)
        return len(same)
    return 0


def ensure_history(symbols, force_snapshot=False, allow_backfill=True):
    """保证 share_history.json 里有可用的份额序列。

    symbols：本次关心的标的（如 ['sh510300', 'sz159915']），只会为它们所在市场做抓取。
    allow_backfill：是否允许跑历史回补。上交所逐日回补很慢（每个日期一次请求），
        深交所区间接口在站点抖动时单次可能要 30s。所以**盘中监控应传 False**，
        只读本地已有数据；回补由 --backfill 单独进程跑，不拖慢实时预警。
    返回更新后的 payload。
    """
    payload = _load()
    days = payload.setdefault('days', {})
    meta = payload.setdefault('meta', {})

    # 统一日期键格式为 YYYYMMDD（早期版本可能写成 YYYY-MM-DD，这里顺手迁移）
    for k in list(days.keys()):
        if '-' in k:
            days[k.replace('-', '')] = days.pop(k)

    today_dash = datetime.now().strftime('%Y-%m-%d')

    need_sh = any(s.startswith('sh') for s in symbols)
    need_sz = any(s.startswith('sz') for s in symbols)

    # 1) 当日快照：沪深各抓一次，按 SNAPSHOT_MIN_INTERVAL 限流
    #    上交所按日期探测最近几个工作日（份额 T+1 披露）；
    #    深交所走区间接口，顺带就把最近几天补齐了。
    #    注意：这一步即使在 allow_backfill=False 时也要跑——它是「拿到昨天份额」的唯一途径，
    #    但限流 + 只探测 7 天，正常情况下只是一两个 HTTP 请求。
    last_snap = meta.get('lastSnapshotDate', '')
    last_ts = meta.get('lastSnapshotTs', 0)
    fresh_enough = (last_snap == today_dash) and (time.time() - last_ts < SNAPSHOT_MIN_INTERVAL)
    if force_snapshot or not fresh_enough:
        added = 0
        if need_sh:
            sh_codes = _sh_codes_from(symbols)
            for dstr in _recent_trade_dates(7):
                if days.get(dstr) and any(c in days[dstr] for c in sh_codes):
                    continue
                got = fetch_sse_snapshot(dstr)
                if got:
                    days.setdefault(dstr, {}).update(got)
                    added += 1
        if need_sz:
            # 深交所一次性拉最近 10 个自然日，覆盖 T+1 披露窗口。
            # 关键：写入时一律用**接口返回的日期字段**做键，绝不用「今天」。
            # 深交所份额是 T+1 傍晚才更新，上午请求 txtEnd=今天 只会返回到前一交易日，
            # 早前版本误把返回值记到当天，导致连续两天份额完全相同、净申赎恒为 0。
            recent = _recent_trade_dates(10)
            got = fetch_szse_range(min(recent), max(recent)) if recent else {}
            for day, m in got.items():
                before = len(days.get(day) or {})
                days.setdefault(day, {}).update(m)
                if len(days[day]) > before:
                    added += 1
            if got:
                meta['lastSzseSnapshotDay'] = max(got)
        meta['lastSnapshotDate'] = today_dash
        meta['lastSnapshotTs'] = time.time()
        meta['snapshotAdded'] = added
        if added:
            _prune_fake_szse(days)
            _save(payload)

    if not allow_backfill:
        return payload

    # 2) 上交所历史回补：本地不足 PERCENTILE_DAYS 天时按日期补齐
    if need_sh:
        sh_codes = _sh_codes_from(symbols)
        have = sum(1 for d in days if any(c in days[d] for c in sh_codes))
        if have < PERCENTILE_DAYS:
            # 先把已有日期标出来，从最近的日期倒着补，凑够 60 天即止
            target = _recent_trade_dates(BACKFILL_CALENDAR_DAYS)
            todo = [d for d in target if d not in days]
            for dstr in todo:
                got = fetch_sse_snapshot(dstr)
                if not got:
                    continue          # 非交易日 / 未披露，跳过
                days[dstr] = got
                if _count_days_for(days, symbols) >= PERCENTILE_DAYS:
                    break
            meta['lastBackfillTs'] = time.time()
            _save(payload)
            print(f'[share] 上交所回补完成，现有关键标的 {_count_days_for(days, symbols)} 天',
                  file=sys.stderr, flush=True)

    # 3) 深交所历史回补：官方 scsj_fund_jjgm 区间接口，一次能拉一段全市场
    if need_sz:
        before = _count_days_for(days, [s for s in symbols if s.startswith('sz')])
        if before < PERCENTILE_DAYS:
            backfill_szse(payload, days, symbols=symbols)

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
        base['note'] = (f'份额历史仅 {len(series)} 天，不足 2 天无法算变动；'
                        f'请先跑 python3 scripts/etf_share_flow.py --backfill')
        return base

    # 逐日净申赎金额 = Δ份额 × 当日价格
    # 价格用「变动日当天」的收盘价（ETF 净值≈收盘价）。传入的 price_map 是
    # {YYYYMMDD: close}，缺失时用 price_prev 兜底，再缺失就记 None（那天的金额不可信，
    # 不能用 1.0 之类的假价格硬算，会把几亿的申赎算成几百万）。
    # 分位单独在「份额变动」上算：价格日内波动远小于份额量级变化，不影响排序结论，
    # 这样即使没有完整价格序列，分位依然可信。
    price_map = price_map or {}
    nets = []          # [(date, net_shares, price_or_None)]
    for i in range(1, len(series)):
        d, cur = series[i]
        _, prev = series[i - 1]
        delta = cur - prev
        px = price_map.get(d)
        if px is None:
            px = price_today if i == len(series) - 1 else price_prev
        nets.append((d, delta, px))

    latest = nets[-1]
    base['ok'] = True
    base['netShares'] = latest[1]
    base['asOf'] = latest[0]
    # 价格缺失时无法折算金额：份额方向和量级仍可给出，金额标 None 让前端显示「—」
    base['netAmount'] = None if latest[2] is None else latest[1] * latest[2]

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
    # 只要 5 天里有任意一天缺价就整体标 None，避免用部分天数算出偏小的值
    recent5 = nets[-5:]
    if recent5 and all(n[2] is not None for n in recent5):
        base['net5Amount'] = sum(n[1] * n[2] for n in recent5)
    else:
        base['net5Amount'] = None
    base['net5Days'] = len(recent5)

    return base


def _all_watch_symbols():
    """从 monitor_national_team 里读出全部监控标的，供 --backfill / --check 使用。"""
    try:
        import monitor_national_team as mnt
        out = []
        for grp in mnt.WATCH_GROUPS:
            for s, _n in grp['etfs']:
                if s not in out:
                    out.append(s)
        return out
    except Exception:
        # 读不到就退化成硬编码的宽基清单
        return ['sh510300', 'sh510050', 'sh510500', 'sh588000', 'sh512100',
                'sz159915', 'sz159919', 'sz159949', 'sz159952',
                'sz159845', 'sz159338', 'sz159352', 'sz159361']


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
    elif '--backfill' in sys.argv:
        # 独立回补进程：盘中监控读这份文件，回补在这里慢慢跑，互不阻塞。
        # 建议放 crontab，每天收盘后 / 开盘前各跑一次：
        #   30 8 * * 1-5  cd backend && python3 scripts/etf_share_flow.py --backfill
        syms = _all_watch_symbols()
        print(f'[share] 回补标的 {len(syms)} 只：{",".join(syms[:6])}...',
              file=sys.stderr, flush=True)
        t0 = time.time()
        ensure_history(syms, allow_backfill=True)
        print(json.dumps({**status(), 'costSec': round(time.time() - t0, 1)},
                         ensure_ascii=False, indent=2))
    elif '--check' in sys.argv:
        # 逐只打印净申赎，方便排查深市/沪市某只算不出来
        syms = _all_watch_symbols()
        payload = ensure_history(syms, allow_backfill=True)
        # 取价格序列：与 monitor_national_team 用同一套腾讯日线，避免两处口径不一致
        pmap = {}
        try:
            import monitor_national_team as mnt
            for s in syms:
                try:
                    pmap[s] = mnt._day_close_map(s)
                except Exception:
                    pmap[s] = {}
        except Exception as e:
            print(f'[share] 价格序列不可用: {e}', file=sys.stderr)
        for s in syms:
            r = compute_one(payload, s, price_map=pmap.get(s))
            amt = r['netAmount']
            pct = r['percentile']
            amt_s = f'{amt / 1e8:+8.2f}亿' if amt is not None else '     N/A'
            pct_s = f'{pct * 100:3.0f}%' if pct is not None else '  -'
            print(f'{s}  days={r["days"]:>3}  asOf={r["asOf"]}  '
                  f'net={amt_s}  pct={pct_s}  {r["note"]}')
    elif '--snapshot' in sys.argv:
        p = ensure_history(['sh510300', 'sz159915'], force_snapshot=True, allow_backfill=False)
        print(json.dumps(status(), ensure_ascii=False, indent=2))
