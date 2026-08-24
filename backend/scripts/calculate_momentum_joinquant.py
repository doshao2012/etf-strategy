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
from datetime import datetime, timedelta

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'etf_config.json')
# 历史数据缓存文件
HISTORY_CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'history_cache.json')

def get_realtime_price(market, code):
    """获取实时价格及今日最高/最低价（不缓存，每次都获取最新）"""
    try:
        url = f"https://qt.gtimg.cn/q={market}{code}"
        response = requests.get(url, timeout=5)
        content = response.text
        
        match = re.search(f'v_{market}{code}="([^"]+)"', content)
        if not match:
            return None, None, None, None
        
        data_str = match.group(1)
        fields = data_str.split('~')
        
        current = float(fields[3]) if fields[3] else 0
        pre_close = float(fields[4]) if fields[4] else 0
        change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else 0
        today_high = float(fields[33]) if len(fields) > 33 and fields[33] else current
        today_low = float(fields[34]) if len(fields) > 34 and fields[34] else current
        
        return current, change_pct, today_high, today_low
    except Exception as e:
        print(f"获取实时价格失败: {e}", file=sys.stderr)
        return None, None, None, None

def load_history_cache():
    """加载历史数据缓存"""
    try:
        if os.path.exists(HISTORY_CACHE_FILE):
            with open(HISTORY_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_history_cache(cache):
    """保存历史数据缓存"""
    try:
        with open(HISTORY_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"保存历史缓存失败: {e}", file=sys.stderr)

def get_historical_prices(market, code, days=30):
    """获取历史K线数据（按天缓存）"""
    today = datetime.now().strftime('%Y-%m-%d')
    cache_key = f"{market}_{code}"
    
    # 检查缓存
    cache = load_history_cache()
    cached_data = cache.get(cache_key)
    
    if cached_data and cached_data.get('date') == today:
        print(f"使用缓存的历史数据: {code}", file=sys.stderr)
        data = cached_data.get('data', [])
        return [{'day': item['day'], 'close': float(item['close']), 'high': float(item['high']), 'low': float(item['low'])} for item in data[-days:]]
    
    # 从新浪获取历史数据
    try:
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen={days+30}"
        
        response = requests.get(url, timeout=15)
        content = response.text
        
        if not content or content == 'null':
            return []
        
        data = json.loads(content)
        if not data:
            return []
        
        # 保存到缓存
        cache[cache_key] = {'date': today, 'data': data}
        save_history_cache(cache)
        
        # 返回指定天数的数据（含 day、high、low 字段）
        return [{'day': item['day'], 'close': float(item['close']), 'high': float(item['high']), 'low': float(item['low'])} for item in data[-days:]]
        
    except Exception as e:
        print(f"获取历史数据失败: {e}", file=sys.stderr)
        return []

def load_config():
    """从JSON配置读取ETF列表并获取实时数据"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        configs = json.load(f)
    
    etfs = {}
    for item in configs:
        if item.get('isActive', True):
            code = item['code']
            name = item['name']
            market = item.get('market', 'sh' if code.startswith('5') else 'sz')
            
            # 获取历史数据
            data = get_historical_prices(market, code, 35)
            
            # 获取实时价格（含今日高/低价）
            current, today_pct, today_high, today_low = get_realtime_price(market, code)
            if current and current > 0 and data:
                today_str = datetime.now().strftime('%Y-%m-%d')
                if data[-1].get('day', '').startswith(today_str):
                    # 最后一条已经是今天 → 替换为实时数据（盘后修正 / 盘中刷新）
                    data[-1]['close'] = current
                    data[-1]['high'] = max(data[-1]['high'], today_high) if today_high else data[-1]['high']
                    data[-1]['low'] = min(data[-1]['low'], today_low) if today_low else data[-1]['low']
                elif abs(current - data[-1]['close']) > 0.001:
                    # 最后一条不是今天，且价格有变动 → 追加实时数据（新交易日）
                    data.append({'day': today_str, 'close': current,
                                 'high': today_high or current,
                                 'low': today_low or current})
                # 否则：节假日价格不变 → 不追加，保持数据纯净
            
            if data:
                etfs[code] = {
                    'code': code,
                    'name': name,
                    'data': data,
                    'today_pct': today_pct
                }
    
    return etfs

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
        closes = [d['close'] for d in day_data]
        ma10 = round(sum(closes[-10:]) / 10, 4) if len(closes) >= 10 else None
        ma20 = round(sum(closes[-20:]) / 20, 4) if len(closes) >= 20 else None
        history.append({
            'day': day_data[-1]['day'],
            'price': round(prices[-1], 4),
            'score': round(score, 4),
            'rSquared': round(r_squared, 4),
            'annualReturn': round(ann_return, 4),
            'ma10': ma10,
            'ma20': ma20,
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
        last_close = data[-2]['close']  # 昨日收盘价（data[-2]是倒数第二个数据）
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
        elif score < score_threshold:
            status = "分值过低"

        # 3. 预估动量得分
        # 假设明天价格不变，去掉最老的价格，加上当前价格，重新计算
        estimated_prices = np.append(prices[1:], current_price)
        estimated_score, _, _, _ = calculate_momentum(estimated_prices)

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

        # 7. ATR20 & 5日最高价距2倍ATR
        atr20 = None
        atr_two_support = None
        atr_distance = None
        atr_alarm = False
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
