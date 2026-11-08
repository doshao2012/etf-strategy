#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完全按照聚宽算法实现的ETF动量计算
"""
import numpy as np
import math
import sys
import json
import os
import requests
import re
import time
from datetime import datetime, timedelta

# 配置文件路径
# 运行时数据目录：Docker 里由 ETF_DATA_DIR 指向持久卷（否则每次重建容器数据全丢），
# 裸机运行不设该变量，仍落在 backend/ 下。
DATA_DIR = os.environ.get('ETF_DATA_DIR') or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(DATA_DIR, 'etf_config.json')
# 历史数据缓存文件
HISTORY_CACHE_FILE = os.path.join(DATA_DIR, 'history_cache.json')

_REALTIME_PREFETCH = {}

# K线接口熔断：proxy.finance.qq.com 在部分网络下不可达（但 qt.gtimg.cn 通），
# 不通时每只都要等满超时，10 只就是 100 多秒。连续失败 2 只就熔断 5 分钟，
# 期间直接用本地旧缓存，等下一次请求再探一次。
_KLINE_NET_FAILS = 0
_KLINE_NET_DEAD_UNTIL = 0.0
_KLINE_TIMEOUT = 8


def prefetch_realtime(codes):
    """批量预取实时行情，一次请求拿回所有标的。

    原来每只 ETF 单独请求一次，10 只就是 10 次串行往返（本地 1.3s，线上更久）。
    腾讯支持 q=sh512890,sz159915,... 批量查询，一次即可。
    """
    global _REALTIME_PREFETCH
    if not codes:
        return
    try:
        syms = ','.join(f"{m}{c}" for m, c in codes)
        response = requests.get(f"https://qt.gtimg.cn/q={syms}", timeout=6)
        content = response.text
        cache = {}
        for sym, data_str in re.findall(r'v_(\w+)="([^"]*)"', content):
            if not data_str:
                continue
            try:
                fields = data_str.split('~')
                current = float(fields[3]) if fields[3] else 0
                change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else 0
                today_high = float(fields[33]) if len(fields) > 33 and fields[33] else current
                today_low = float(fields[34]) if len(fields) > 34 and fields[34] else current
                trade_time = fields[30] if len(fields) > 30 and fields[30] else ''
                trade_date = (f'{trade_time[:4]}-{trade_time[4:6]}-{trade_time[6:8]}'
                              if len(trade_time) >= 8 else '')
                cache[sym] = (current, change_pct, today_high, today_low, trade_date)
            except (ValueError, IndexError):
                continue
        _REALTIME_PREFETCH = cache
        print(f"批量预取实时行情: {len(cache)}/{len(codes)} 只", file=sys.stderr)
    except Exception as e:
        print(f"批量预取实时行情失败: {e}", file=sys.stderr)
        _REALTIME_PREFETCH = {}


def get_realtime_price(market, code):
    """获取实时价格及今日最高/最低价。

    优先用 prefetch_realtime 的批量结果，避免逐只串行请求；
    未预取到时才回退到单只请求。
    """
    key = f"{market}{code}"
    if key in _REALTIME_PREFETCH:
        return _REALTIME_PREFETCH[key]
    try:
        url = f"https://qt.gtimg.cn/q={market}{code}"
        response = requests.get(url, timeout=5)
        content = response.text
        
        match = re.search(f'v_{market}{code}="([^"]+)"', content)
        if not match:
            return None, None, None, None, None
        
        data_str = match.group(1)
        fields = data_str.split('~')
        
        current = float(fields[3]) if fields[3] else 0
        pre_close = float(fields[4]) if fields[4] else 0
        change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else 0
        today_high = float(fields[33]) if len(fields) > 33 and fields[33] else current
        today_low = float(fields[34]) if len(fields) > 34 and fields[34] else current
        # 腾讯时间字段（索引30），格式 YYYYMMDDHHMMSS
        trade_time = fields[30] if len(fields) > 30 and fields[30] else ''
        trade_date = f'{trade_time[:4]}-{trade_time[4:6]}-{trade_time[6:8]}' if len(trade_time) >= 8 else ''
        
        return current, change_pct, today_high, today_low, trade_date
    except Exception as e:
        print(f"获取实时价格失败: {e}", file=sys.stderr)
        return None, None, None, None, None

def load_history_cache():
    """加载历史数据缓存（损坏时不再静默吞掉）"""
    try:
        if os.path.exists(HISTORY_CACHE_FILE):
            with open(HISTORY_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        # 原来这里是裸 except: pass。文件被写坏时缓存全部静默消失，
        # 所有 K 线被迫重拉，表现是"某天突然整个策略打不开"，且没有任何线索。
        print(f"⚠ history_cache.json 读取失败（{type(e).__name__}: {e}），"
              f"本次按空缓存处理", file=sys.stderr)
    return {}

def save_history_cache(cache):
    """保存历史数据缓存（原子写）。

    原来是直接 open('w') 覆盖写。本脚本跑在常驻 worker 池的**多个进程**里，
    并发落盘一旦交错，history_cache.json 就是半截 JSON；下次 load 被 except
    吞掉返回 {}，全部缓存静默作废、所有 K 线被迫重拉——撞上数据源限流就整页 500。
    改成先写 pid 专属临时文件再 os.replace（同文件系统内是原子的）。
    """
    try:
        tmp = f'{HISTORY_CACHE_FILE}.tmp.{os.getpid()}'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(tmp, HISTORY_CACHE_FILE)
    except Exception as e:
        print(f"保存历史缓存失败: {e}", file=sys.stderr)

def _rows_of(data, days):
    """统一成 {day, close, high, low} 列表"""
    return [{'day': it['day'], 'close': float(it['close']),
             'high': float(it['high']), 'low': float(it['low'])}
            for it in data[-days:]]


def get_historical_prices(market, code, days=30):
    """获取历史K线数据（按天缓存 + 旧缓存兜底）。

    缓存策略：
      1. 当天已拉过 → 直接用（省一次往返）
      2. 否则联网拉腾讯，成功就写缓存
      3. **联网失败时退回上一次成功拉到的缓存**（不管它是哪天）

    第 3 条是关键：周末、节假日、数据源临时限流时，K 线历史并不会变，
    拿两三天前的缓存算动量完全成立。原实现失败就直接 return []，
    十只标的全空 → 接口只剩一句「未能获取ETF策略数据」，
    2026-11-08（周日）整页打不开就是这么来的。
    """
    today = datetime.now().strftime('%Y-%m-%d')
    cache_key = f"{market}_{code}"

    cache = load_history_cache()
    cached = cache.get(cache_key) or {}
    cached_rows = cached.get('data') or []
    cached_date = cached.get('date') or ''

    if cached_date == today and len(cached_rows) >= days:
        print(f"使用缓存的历史数据: {code}", file=sys.stderr)
        return _rows_of(cached_rows, days)

    global _KLINE_NET_FAILS, _KLINE_NET_DEAD_UNTIL
    if (_KLINE_NET_DEAD_UNTIL and time.time() < _KLINE_NET_DEAD_UNTIL
            and len(cached_rows) >= days):
        return _rows_of(cached_rows, days)

    symbol = f"{market}{code}"
    url = (f"http://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get"
           f"?param={symbol},day,,,{days + 30},qfq")
    err = ''
    try:
        response = requests.get(url, timeout=_KLINE_TIMEOUT)
        if response.status_code != 200:
            err = f'HTTP {response.status_code}'
        else:
            result = response.json()
            node = (result.get('data') or {}).get(symbol) or {}
            # 部分 ETF（如新上市）没有前复权数据，降级用不复权
            klines = node.get('qfqday') or node.get('day') or []
            if not klines:
                err = '返回数据为空'
            else:
                data = [{'day': k[0], 'close': k[2], 'high': k[3],
                         'low': k[4], 'open': k[1], 'volume': k[5]}
                        for k in klines]
                cache[cache_key] = {'date': today, 'data': data}
                save_history_cache(cache)
                _KLINE_NET_FAILS = 0
                return _rows_of(data, days)
    except Exception as e:
        err = f'{type(e).__name__}: {e}'

    _KLINE_NET_FAILS += 1
    if _KLINE_NET_FAILS >= 2:
        _KLINE_NET_DEAD_UNTIL = time.time() + 300
        print(f"⚠ K线接口连续失败 {_KLINE_NET_FAILS} 次，熔断 5 分钟，"
              f"期间只用本地缓存", file=sys.stderr)

    if len(cached_rows) >= days:
        print(f"⚠ {code} 拉取失败（{err}），用 {cached_date} 的旧缓存兜底"
              f"（{len(cached_rows)} 条）", file=sys.stderr)
        return _rows_of(cached_rows, days)

    print(f"获取历史数据失败 {code}: {err}", file=sys.stderr)
    return []


def load_config():
    """加载ETF配置和基金数据"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    etfs = {}
    config_path = os.path.join(script_dir, '..', 'etf_config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    # 批量预取实时行情：一次请求拿回所有标的，
    # 避免下面循环里逐只串行请求（10 只就是 10 次网络往返）
    prefetch_realtime([(it['market'], it['code']) for it in config])

    for item in config:
        code = item['code']
        market = item['market']
        name = item['name']
        data = get_historical_prices(market, code, 35)
        if not data:
            continue
        current_price, today_pct, today_high, today_low, trade_date = get_realtime_price(market, code)
        # 仅当腾讯API日期与K线最新日期一致时（即当天有交易数据），才更新实时数据
        if current_price and trade_date and data[-1]['day'] == trade_date:
            # K线已有今日数据，更新收盘价
            data[-1] = {'day': data[-1]['day'], 'close': current_price, 'high': today_high or data[-1]['high'], 'low': today_low or data[-1]['low']}
        elif current_price and trade_date and trade_date > data[-1]['day']:
            # 腾讯日期比K线最新日期更新（如节后第一天），追加今日K线
            data.append({'day': trade_date, 'close': current_price, 'high': today_high or current_price, 'low': today_low or current_price})
        etfs[code] = {'code': code, 'name': name, 'data': data, 'today_pct': today_pct}
    fund_data = get_fund_nav_data(35)
    fund_current, fund_pct = get_fund_realtime()
    if fund_data:
        fund_trade_date = fund_data[-1]['day']
        if fund_current and fund_current > 0 and fund_trade_date == today_str:
            fund_data[-1] = {'day': fund_data[-1]['day'], 'close': fund_current, 'high': fund_current, 'low': fund_current}
        elif fund_current and fund_current > 0 and fund_trade_date > today_str:
            fund_data.append({'day': trade_date, 'close': fund_current, 'high': fund_current, 'low': fund_current})
        else:
            fund_pct = None
        etfs[FUND_CODE] = {'code': FUND_CODE, 'name': FUND_NAME, 'data': fund_data, 'today_pct': fund_pct}
    return etfs

# ====== 场外基金数据源（微盘股替代） ======
FUND_CODE = '023350'
FUND_NAME = '诺安多策略混合C'

def get_fund_nav_data(days=35):
    """从天天基金获取基金净值数据（自动翻页获取全部）"""
    today = datetime.now().strftime('%Y-%m-%d')
    cache_key = f'fund_{FUND_CODE}'
    cache = load_history_cache()
    cached = cache.get(cache_key)
    if cached and cached.get('date') == today:
        return [{'day': d['day'], 'close': float(d['close']), 'high': float(d['close']), 'low': float(d['close'])} for d in cached['data'][-days:]]
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://fund.eastmoney.com/'}
        s = requests.Session()
        s.headers.update(headers)
        s.get(f'https://fund.eastmoney.com/{FUND_CODE}.html', timeout=10)
        # 翻页获取全部数据
        all_data = []
        page = 1
        while True:
            url = f'https://api.fund.eastmoney.com/f10/lsjz?fundCode={FUND_CODE}&pageIndex={page}&pageSize=100'
            r = s.get(url, headers=headers, timeout=10)
            result = r.json()
            if not result.get('Data') or not result['Data'].get('LSJZList'):
                break
            items = result['Data']['LSJZList']
            if not items:
                break
            for item in items:
                close = float(item['DWJZ'])
                if close > 0:
                    all_data.append({'day': item['FSRQ'], 'close': close, 'high': close, 'low': close})
            page += 1
        if not all_data:
            print(f'基金{FUND_CODE}数据获取失败', file=sys.stderr)
            return []
        all_data.reverse()
        cache[cache_key] = {'date': today, 'data': all_data}
        save_history_cache(cache)
        return [{'day': d['day'], 'close': float(d['close']), 'high': float(d['close']), 'low': float(d['close'])} for d in all_data[-days:]]
    except Exception as e:
        print(f'基金{FUND_CODE}数据获取失败: {e}', file=sys.stderr)
        return []

def get_fund_realtime():
    """从天天基金获取基金实时估值"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://fund.eastmoney.com/'}
        url = f'https://fundgz.1234567.com.cn/js/{FUND_CODE}.js'
        r = requests.get(url, headers=headers, timeout=5)
        text = r.text.strip()
        if text.startswith('jsonpgz('):
            data = json.loads(text[8:-2])
            return float(data.get('gsz', 0) or 0), float(data.get('gszzl', 0) or 0)
        return None, None
    except Exception as e:
        return None, None


def calculate_momentum(price_data):
    """计算动量得分：线性加权回归 + R²稳定性"""
    y = np.log(price_data)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    
    # R² 稳定性
    ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0
    
    # 综合得分 = 年化(slope*250转指数) * R²
    ann_return = math.exp(slope * 250) - 1
    score = ann_return * r_squared
    return score, r_squared, ann_return, slope

def get_daily_history(data, lookback_days=25):
    """计算最近10个交易日每日快照：收益得分、MA10、MA20等"""
    history = []
    total = len(data)
    for i in range(10):
        end_idx = -i if i > 0 else total
        start_idx = end_idx - lookback_days - 1
        # 转正索引判断是否有效
        s = start_idx if start_idx >= 0 else total + start_idx
        e = end_idx if end_idx >= 0 else total + end_idx
        if s < 0 or s >= e:
            break
        day_data = data[s:e]
        prices = np.array([d['close'] for d in day_data])
        score, r_squared, ann_return, _ = calculate_momentum(prices)
        prev_close = day_data[-2]['close'] if len(day_data) >= 2 else day_data[-1]['close']
        change = round((prices[-1] / prev_close - 1) * 100, 2) if prev_close else 0
        history.append({
            'day': day_data[-1]['day'],
            'price': round(prices[-1], 4),
            'change': change,
            'score': round(score, 4),
            'rSquared': round(r_squared, 4),
            'annualReturn': round(ann_return, 4),
        })
    return history

def get_metrics(etf_info, lookback_days=25, score_threshold=0.0, loss_limit=0.97):
    """
    完全按照聚宽算法实现的动量计算

    注意：prices 是 lookback_days + 1 个数据点（26个），动量计算使用全部数据

    Args:
        etf_info: ETF信息字典，包含code、name和data
        lookback_days: 动量计算周期（默认25）
        score_threshold: 策略买入阈值（默认0.0）
        loss_limit: 近3日单日跌幅限制（默认0.97，即3%）

    Returns:
        dict: 包含动量得分、稳定性、价格、涨跌幅、状态等
    """
    try:
        data = etf_info['data']
        if len(data) < lookback_days + 1:
            return None

        # 1. 基础数据提取
        # 关键：提取 lookback_days + 1 个数据点（26个）
        # 注意：这里 prices 包含26个数据，全部用于动量计算
        data_slice = data[-(lookback_days + 1):]
        prices = np.array([d['close'] for d in data_slice])  # 26个数据点

        current_price = prices[-1]  # 最后一个数据作为当前价格
        # 优先使用腾讯财经的实时涨跌幅（更准确），否则用K线数据计算
        today_pct = etf_info.get('today_pct')
        if today_pct is None:
            last_close = data[-2]['close']  # 昨日收盘价
            today_pct = (current_price / last_close - 1) * 100  # 今日涨跌幅

        # 2. 动量得分 & 稳定性计算 (线性加权回归)
        # 使用全部26个数据点进行动量计算
        score, r_squared, ann_return, slope = calculate_momentum(prices)

        # 3. 状态判定
        status = "正常"
        # 风控：检查最后3个单日跌幅
        ratios = [prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]]
        if min(ratios) < loss_limit:
            status = "⚠️ 跌幅拦截"
            score = -0.01
        elif ann_return < -0.05:
            status = "分值过低"

        # 3. 预估动量得分 & 预估收益得分
        # 假设明天价格不变，去掉最老的价格，加上当前价格，重新计算
        estimated_prices = np.append(prices[1:], current_price)
        estimated_score, _, estimated_ann_return, _ = calculate_momentum(estimated_prices)

        # 4. 均线计算（直接用 data 中已有的收盘价）
        all_closes = [d['close'] for d in data]
        ma10 = float(np.mean(all_closes[-10:])) if len(all_closes) >= 10 else None
        ma20 = float(np.mean(all_closes[-20:])) if len(all_closes) >= 20 else None

        # 5. ENE 轨道 (N=10, M1=11, M2=9)
        # MA10 × 1.11 = 上轨, MA10 × 0.91 = 下轨
        ma10_ene = float(np.mean(all_closes[-10:])) if len(all_closes) >= 10 else None
        if ma10_ene is not None:
            ene_upper = round(ma10_ene * 1.11, 3)
            ene_lower = round(ma10_ene * 0.91, 3)
            ene_dist_upper = round((ene_upper - current_price) / current_price * 100, 2)
            ene_dist_lower = round((current_price - ene_lower) / current_price * 100, 2)
            ene_warn_upper = ene_dist_upper <= 1.0
            ene_warn_lower = ene_dist_lower <= 1.0
        else:
            ene_upper = ene_lower = ene_dist_upper = ene_dist_lower = None
            ene_warn_upper = ene_warn_lower = False

        # 7. ATR20 & 5日最高价距 2 倍 / 3 倍 ATR
        atr20 = None
        atr_two_support = None
        atr_three_support = None
        atr_distance = None
        atr_alarm = False
        atr_three_distance = None
        atr_three_alarm = False
        five_day_high = None
        if len(data) >= 21 and all('high' in d and 'low' in d for d in data):
            tr_values = []
            for i in range(1, len(data)):
                h = data[i]['high']
                l = data[i]['low']
                pc = data[i-1]['close']
                tr = max(h - l, abs(h - pc), abs(l - pc))
                tr_values.append(tr)
            if len(tr_values) >= 20:
                atr20 = round(float(np.mean(tr_values[-20:])), 4)
                highs_5 = [d['high'] for d in data[-5:]]
                five_day_high = round(max(highs_5), 3)
                atr_two_support = round(five_day_high - 2 * atr20, 3)
                atr_distance = round((current_price - atr_two_support) / current_price * 100, 2)
                atr_alarm = bool(current_price < atr_two_support)
                # 3 倍 ATR 支撑：从同一高点再往下多减一个 ATR，位置更低、更宽松
                atr_three_support = round(five_day_high - 3 * atr20, 3)
                atr_three_distance = round((current_price - atr_three_support) / current_price * 100, 2)
                atr_three_alarm = bool(current_price < atr_three_support)

        return {
            'code': etf_info['code'],
            'name': etf_info['name'],
            'score': round(score, 4),
            'estimated_score': round(estimated_score, 4),
            'r_squared': round(r_squared, 3),
            'price': round(current_price, 3),
            'today_pct': round(today_pct, 2),
            'status': status,
            'ann_return': round(ann_return, 4),
            'estimated_ann_return': round(estimated_ann_return, 4),
            'slope': round(slope, 6),
            'ma10': round(ma10, 3) if ma10 is not None else None,
            'ma20': round(ma20, 3) if ma20 is not None else None,
            'below_ma10': bool(ma10 is not None and current_price < ma10),
            'below_ma20': bool(ma20 is not None and current_price < ma20),
            'ene_upper': ene_upper,
            'ene_lower': ene_lower,
            'ene_dist_upper': ene_dist_upper,
            'ene_dist_lower': ene_dist_lower,
            'ene_warn_upper': bool(ene_warn_upper),
            'ene_warn_lower': bool(ene_warn_lower),
            'atr20': atr20,
            'five_day_high': five_day_high,
            'atr_two_support': atr_two_support,
            'atr_distance': atr_distance,
            'atr_alarm': bool(atr_alarm),
            'atr_three_support': atr_three_support,
            'atr_three_distance': atr_three_distance,
            'atr_three_alarm': bool(atr_three_alarm),
            'closes': [{'day': d['day'], 'close': d['close']} for d in data_slice[-10:]],
            'daily_history': get_daily_history(data, lookback_days)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None

def main():
    """主函数"""
    # 参数
    lookback_days = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    score_threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    loss_limit = float(sys.argv[3]) if len(sys.argv) > 3 else 0.97

    # 加载数据
    etfs = load_config()

    # 计算所有ETF的指标
    results = []
    for code, etf_info in etfs.items():
        metrics = get_metrics(etf_info, lookback_days, score_threshold, loss_limit)
        if metrics:
            results.append(metrics)

    # 按得分排序
    results.sort(key=lambda x: x['score'], reverse=True)

    # 找出得分最高的ETF
    recommend = None
    valid_etfs = [r for r in results if r['score'] >= score_threshold]
    if valid_etfs:
        recommend = valid_etfs[0]['code']

    # 输出结果
    # 一只都没算出来时必须说清原因。原来照样返回 code=200 + 空 etfs，
    # 上层只能回一句笼统的「未能获取ETF策略数据」，看不出是数据源挂了还是配置空了。
    if not results:
        output = {
            'code': 500,
            'message': (f'未能获取ETF策略数据：{len(etfs)} 只标的的历史K线全部为空'
                        f'（腾讯K线接口不可用，且本地无可用缓存）。'
                        f'配置数 {len(etfs)}，请检查 history_cache.json 与网络'),
            'data': None,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    output = {
        'code': 200,
        'message': 'success',
        'data': {
            'etfs': results,
            'recommend': recommend,
            'summary': {
                'total': len(results),
                'valid': len(valid_etfs),
                'filtered': len([r for r in results if r['status'] != '正常'])
            }
        }
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
