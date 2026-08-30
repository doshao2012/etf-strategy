#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
均值回归策略：计算ETF相对MA90和MA250的倍数，生成买卖信号
数据获取和更新方式参考动量轮动策略（calculate_momentum_joinquant.py）
"""
import sys
import json
import os
from datetime import datetime

# 从动量策略脚本导入数据获取函数
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calculate_momentum_joinquant import get_historical_prices, get_realtime_price, load_history_cache, save_history_cache

# 策略标的：code, market, name
TARGET_ETFS = [
    {'code': '512890', 'market': 'sh', 'name': '红利低波ETF'},
    {'code': '512040', 'market': 'sh', 'name': '价值ETF'},
    {'code': '513100', 'market': 'sh', 'name': '纳指ETF'},
    {'code': '518880', 'market': 'sh', 'name': '黄金ETF'},
    {'code': '588220', 'market': 'sh', 'name': '科创100ETF'},
]


def get_etf_data(market, code, days=260):
    """获取ETF数据，参考动量策略的load_config"""
    data = get_historical_prices(market, code, days)
    if not data:
        return None, None, None
    current_price, today_pct, _, _ = get_realtime_price(market, code)
    # 仅交易日（周一至周五）才更新实时数据
    if datetime.now().weekday() < 5 and current_price:
        data[-1] = {'day': data[-1]['day'], 'close': current_price, 'high': current_price, 'low': current_price}
    return data, current_price, today_pct


def calculate_ma(closes, period):
    """计算移动平均线"""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def generate_signal(ratio_ma90, ratio_ma250):
    """根据MA倍数生成买卖信号"""
    if ratio_ma90 is None or ratio_ma250 is None:
        return '数据不足', 'gray'
    r90 = ratio_ma90 / 100
    r250 = ratio_ma250 / 100

    both_buy = r90 < 1.01 and r250 < 1.01
    one_buy = r90 < 1.01 or r250 < 1.01
    both_sell = r90 > 1.12 and r250 > 1.12
    one_sell = r90 > 1.12 or r250 > 1.12

    if both_buy:
        return '强烈买入', 'strongBuy'
    elif one_buy and not both_buy and not both_sell:
        return '建议买入', 'suggestBuy'
    elif both_sell:
        return '强烈卖出', 'strongSell'
    elif one_sell and not both_sell:
        return '建议卖出', 'suggestSell'
    else:
        return '观察/持有', 'hold'


def main():
    results = []
    for etf in TARGET_ETFS:
        code = etf['code']
        market = etf['market']
        name = etf['name']

        # 获取数据（参考动量策略：get_historical_prices + get_realtime_price）
        data, current_price, today_pct = get_etf_data(market, code, 260)
        if not data or len(data) < 250:
            results.append({
                'code': code, 'name': name,
                'price': None, 'todayChange': None,
                'ma90': None, 'ma250': None,
                'ratioMa90': None, 'ratioMa250': None,
                'signal': '数据不足', 'signalLevel': 'gray',
                'dataCount': len(data) if data else 0
            })
            continue

        closes = [d['close'] for d in data]
        price = closes[-1]

        # 与动量策略一致：用实时价替换最后一个close
        price_for_ma = current_price if current_price else price

        # 计算MA90和MA250
        ma90 = calculate_ma(closes, 90)
        ma250 = calculate_ma(closes, 250)

        if ma90 is None or ma250 is None:
            results.append({
                'code': code, 'name': name,
                'price': round(price, 3),
                'todayChange': round(today_pct, 2) if today_pct is not None else None,
                'ma90': round(ma90, 3) if ma90 else None,
                'ma250': round(ma250, 3) if ma250 else None,
                'ratioMa90': None, 'ratioMa250': None,
                'signal': '数据不足', 'signalLevel': 'gray',
                'dataCount': len(data)
            })
            continue

        # 计算价格相对MA的倍数（百分比形式）
        ratio_ma90 = round(price_for_ma / ma90 * 100, 2)
        ratio_ma250 = round(price_for_ma / ma250 * 100, 2)

        # 生成信号
        signal, signal_level = generate_signal(ratio_ma90, ratio_ma250)

        results.append({
            'code': code, 'name': name,
            'price': round(price_for_ma, 3),
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