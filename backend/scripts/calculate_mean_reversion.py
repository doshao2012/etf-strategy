#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
均值回归策略：计算ETF相对MA90和MA250的倍数，生成买卖信号
"""
import sys
import json
import os
import requests
import re
from datetime import datetime

# 策略标的：code, market, name
TARGET_ETFS = [
    {'code': '512890', 'market': 'sh', 'name': '红利低波ETF'},
    {'code': '512040', 'market': 'sh', 'name': '价值ETF'},
    {'code': '513100', 'market': 'sh', 'name': '纳指ETF'},
    {'code': '518880', 'market': 'sh', 'name': '黄金ETF'},
    {'code': '588220', 'market': 'sh', 'name': '科创100ETF'},
]

HISTORY_CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'history_cache.json')

def load_history_cache():
    try:
        if os.path.exists(HISTORY_CACHE_FILE):
            with open(HISTORY_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_history_cache(cache):
    try:
        with open(HISTORY_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"保存历史缓存失败: {e}", file=sys.stderr)

def get_historical_prices(market, code, days=260):
    """获取历史K线数据（按天缓存），需要至少250个交易日"""
    today = datetime.now().strftime('%Y-%m-%d')
    cache_key = f"{market}_{code}"
    cache = load_history_cache()
    cached_data = cache.get(cache_key)

    if cached_data and cached_data.get('date') == today:
        data = cached_data.get('data', [])
        if len(data) >= days:
            return [{'day': item['day'], 'close': float(item['close'])} for item in data[-days:]]

    try:
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen={days+30}"
        response = requests.get(url, timeout=15)
        content = response.text
        if not content or content == 'null':
            return []
        data = json.loads(content)
        if not data:
            return []
        cache[cache_key] = {'date': today, 'data': data}
        save_history_cache(cache)
        return [{'day': item['day'], 'close': float(item['close'])} for item in data[-days:]]
    except Exception as e:
        print(f"获取{code}历史数据失败: {e}", file=sys.stderr)
        return []

def get_realtime_price(market, code):
    """获取实时价格"""
    try:
        url = f"https://qt.gtimg.cn/q={market}{code}"
        response = requests.get(url, timeout=5)
        content = response.text
        match = re.search(f'v_{market}{code}="([^"]+)"', content)
        if not match:
            return None, None
        data_str = match.group(1)
        fields = data_str.split('~')
        current = float(fields[3]) if fields[3] else 0
        change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else 0
        return current, change_pct
    except Exception as e:
        print(f"获取{code}实时价格失败: {e}", file=sys.stderr)
        return None, None

def calculate_ma(closes, period):
    """计算移动平均线"""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period

def generate_signal(ratio_ma90, ratio_ma250):
    """根据MA倍数生成买卖信号"""
    if ratio_ma90 is None or ratio_ma250 is None:
        return '数据不足', 'gray'
    r90 = ratio_ma90 / 100  # 转换回倍数
    r250 = ratio_ma250 / 100

    both_buy = r90 < 1.01 and r250 < 1.01
    one_buy = r90 < 1.01 or r250 < 1.01
    both_sell = r90 > 1.12 and r250 > 1.12
    one_sell = r90 > 1.12 or r250 > 1.12

    if both_buy:
        return '强烈买入', 'red'
    elif one_buy and not both_buy and not both_sell:
        return '建议买入', 'orange'
    elif both_sell:
        return '强烈卖出', 'green'
    elif one_sell and not both_sell:
        return '建议卖出', 'yellow'
    else:
        return '观察/持有', 'gray'

def main():
    results = []
    for etf in TARGET_ETFS:
        code = etf['code']
        market = etf['market']
        name = etf['name']

        # 获取历史数据（至少250个交易日）
        data = get_historical_prices(market, code, 260)
        if len(data) < 250:
            results.append({
                'code': code, 'name': name,
                'price': None, 'todayChange': None,
                'ma90': None, 'ma250': None,
                'ratioMa90': None, 'ratioMa250': None,
                'signal': '数据不足', 'signalLevel': 'gray',
                'dataCount': len(data)
            })
            continue

        # 获取实时价格替换最新收盘价
        current_price, today_pct = get_realtime_price(market, code)
        if current_price:
            data[-1] = {'day': data[-1]['day'], 'close': current_price}

        closes = [d['close'] for d in data]
        price = closes[-1]

        # 计算MA90和MA250
        ma90 = calculate_ma(closes, 90)
        ma250 = calculate_ma(closes, 250)

        if ma90 is None or ma250 is None:
            results.append({
                'code': code, 'name': name,
                'price': round(price, 3), 'todayChange': round(today_pct, 2) if today_pct is not None else None,
                'ma90': round(ma90, 3) if ma90 else None,
                'ma250': round(ma250, 3) if ma250 else None,
                'ratioMa90': None, 'ratioMa250': None,
                'signal': '数据不足', 'signalLevel': 'gray',
                'dataCount': len(data)
            })
            continue

        # 计算价格相对MA的倍数（百分比形式）
        ratio_ma90 = round(price / ma90 * 100, 2)
        ratio_ma250 = round(price / ma250 * 100, 2)

        # 生成信号
        signal, signal_level = generate_signal(ratio_ma90, ratio_ma250)

        results.append({
            'code': code, 'name': name,
            'price': round(price, 3),
            'todayChange': round(today_pct, 2) if today_pct is not None else None,
            'ma90': round(ma90, 3),
            'ma250': round(ma250, 3),
            'ratioMa90': ratio_ma90,
            'ratioMa250': ratio_ma250,
            'signal': signal,
            'signalLevel': signal_level,
            'dataCount': len(data)
        })

    output = {
        'code': 200,
        'message': 'success',
        'data': {
            'etfs': results,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total': len(results),
                'strongBuy': len([r for r in results if r['signal'] == '强烈买入']),
                'suggestBuy': len([r for r in results if r['signal'] == '建议买入']),
                'strongSell': len([r for r in results if r['signal'] == '强烈卖出']),
                'suggestSell': len([r for r in results if r['signal'] == '建议卖出']),
                'hold': len([r for r in results if r['signal'] == '观察/持有']),
            }
        }
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()