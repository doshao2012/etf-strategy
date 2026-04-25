#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF动量计算脚本 - 使用新浪/腾讯API获取真实数据
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

def load_config():
    """读取ETF配置文件"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        configs = json.load(f)
    
    etfs = {}
    for item in configs:
        if item.get('isActive', True):
            etfs[item['code']] = {
                'name': item['name'],
                'market': item.get('market', 'sh' if item['code'].startswith('5') else 'sz')
            }
    return etfs

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
        pre_close = float(fields[4]) if fields[4] else 0
        change_pct = float(fields[12]) if fields[12] else 0
        
        return current, change_pct
    except Exception as e:
        print(f"获取实时价格失败: {e}", file=sys.stderr)
        return None, None

def get_historical_prices(market, code, days=30):
    """获取历史K线数据"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 20)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # 使用新浪财经获取历史K线数据
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen={days+30}"
        
        response = requests.get(url, timeout=15)
        content = response.text
        
        if not content or content == 'null':
            return []
        
        data = json.loads(content)
        if not data:
            return []
        
        prices = []
        for item in data[-days:]:
            prices.append(float(item['close']))
        
        return prices
        
    except Exception as e:
        print(f"获取历史数据失败: {e}", file=sys.stderr)
        return []

def calculate_momentum(prices, lookback=25):
    """计算动量得分"""
    if len(prices) < lookback:
        return 0, 0, 0, 0
    
    returns = np.diff(np.log(prices))
    lookback_returns = returns[-lookback:]
    
    # 计算动量
    momentum = np.sum(lookback_returns)
    
    # R² 计算
    x = np.arange(len(lookback_returns))
    y = lookback_returns
    if len(x) > 1:
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        ss_tot = np.sum((y - y_mean) ** 2)
        ss_reg = np.sum((x - x_mean) * (y - y_mean)) ** 2 / np.sum((x - x_mean) ** 2)
        r_squared = ss_reg / ss_tot if ss_tot > 0 else 0
    else:
        r_squared = 0
    
    # 斜率
    slope = momentum / len(lookback_returns) if len(lookback_returns) > 0 else 0
    
    # 年化收益
    annual_return = momentum * (252 / len(lookback_returns)) if len(lookback_returns) > 0 else 0
    
    return momentum, r_squared, slope, annual_return

def main():
    lookback = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    min_r2 = float(sys.argv[2]) if len(sys.argv) > 2 else 0
    r2_weight = float(sys.argv[3]) if len(sys.argv) > 3 else 0.97
    
    # 加载配置
    etf_configs = load_config()
    
    results = []
    for code, info in etf_configs.items():
        name = info['name']
        market = info['market']
        
        # 获取实时价格
        current_price, today_pct = get_realtime_price(market, code)
        
        # 获取历史数据
        prices = get_historical_prices(market, code, 30)
        
        # 如果有历史数据，添加当前价格
        if current_price and current_price > 0 and prices:
            prices.append(current_price)
        
        # 计算动量
        momentum, r_squared, slope, annual_return = calculate_momentum(prices, lookback)
        
        # 计算最终得分
        score = momentum * (r_squared ** r2_weight) if r_squared >= min_r2 else 0
        
        # 判断状态
        if score < 0:
            status = "负动量"
        elif r_squared < min_r2:
            status = "波动过大"
        else:
            status = "正常"
        
        # 近3日单日跌幅超过3%则拦截
        if len(prices) >= 3:
            recent_returns = np.diff(np.log(prices[-3:]))
            if any(r < -0.03 for r in recent_returns):
                status = "近3日跌幅过大"
        
        results.append({
            'code': code,
            'name': name,
            'score': round(score, 4),
            'estimated_score': round(score * 1.02, 4) if score > 0 else round(score * 0.98, 4),
            'r_squared': round(r_squared, 4),
            'price': current_price if current_price else (prices[-1] * 100 if prices else 0),
            'today_pct': round(today_pct, 2) if today_pct else 0,
            'status': status,
            'slope': round(slope, 6),
            'ann_return': round(annual_return, 4),
        })
    
    # 按得分排序
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # 构建推荐
    recommend = None
    for r in results:
        if r['status'] == '正常' and r['score'] > 0:
            recommend = {
                'name': r['name'],
                'code': r['code'],
                'score': r['score'],
                'estimated_score': r['estimated_score'],
            }
            break
    
    output = {
        'data': {
            'etfs': results,
            'recommend': recommend,
            'timestamp': datetime.now().isoformat(),
            'dataSource': '新浪/腾讯财经',
        }
    }
    
    print(json.dumps(output, ensure_ascii=False))

if __name__ == '__main__':
    main()
