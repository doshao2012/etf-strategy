#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF动量计算脚本 - 使用JSON配置
"""
import numpy as np
import math
import sys
import json
import os
from datetime import datetime, timedelta

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'etf_config.json')

def load_config():
    """读取ETF配置文件"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        configs = json.load(f)
    
    # 只返回启用的ETF
    etfs = {}
    for item in configs:
        if item.get('isActive', True):
            etfs[item['code']] = item['name']
    return etfs

def get_etf_price(code):
    """获取ETF价格数据（模拟）"""
    import random
    # 生成随机数据用于演示
    np.random.seed(hash(code) % 1000)
    days = 30
    prices = []
    base_price = 1.0
    
    for i in range(days):
        change = np.random.normal(0.001, 0.02)
        base_price *= (1 + change)
        prices.append(base_price)
    
    return prices

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
    for code, name in etf_configs.items():
        prices = get_etf_price(code)
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
        
        results.append({
            'code': code,
            'name': name,
            'score': round(score, 4),
            'estimated_score': round(score * 1.02, 4),
            'r_squared': round(r_squared, 4),
            'price': round(prices[-1] * 100, 2) if prices else 0,
            'today_pct': round((prices[-1] / prices[-2] - 1) * 100, 2) if len(prices) > 1 else 0,
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
            'dataSource': '模拟数据',
        }
    }
    
    print(json.dumps(output, ensure_ascii=False))

if __name__ == '__main__':
    main()
