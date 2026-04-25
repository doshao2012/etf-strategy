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
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'etf_config.json')
# 缓存文件路径
CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data_cache.json')
# 缓存有效期（秒）- 5分钟内不重复获取数据
CACHE_TTL = 300

def load_cache():
    """加载缓存"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            # 检查缓存是否过期
            if time.time() - cache.get('timestamp', 0) < CACHE_TTL:
                return cache.get('data')
    except:
        pass
    return None

def save_cache(data):
    """保存缓存"""
    try:
        cache_dir = os.path.dirname(CACHE_FILE)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'timestamp': time.time(), 'data': data}, f)
    except Exception as e:
        print(f"保存缓存失败: {e}", file=sys.stderr)

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
        
        # 使用新浪财经获取历史K线数据
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen={days+30}"
        
        response = requests.get(url, timeout=15)
        content = response.text
        
        if not content or content == 'null':
            return []
        
        data = json.loads(content)
        if not data:
            return []
        
        # 返回包含 close 的数据格式
        return [{'close': float(item['close'])} for item in data[-days:]]
        
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
            data = get_historical_prices(market, code, 30)
            
            # 获取实时价格并追加
            current, today_pct = get_realtime_price(market, code)
            if current and current > 0 and data:
                data.append({'close': current})
            
            if data:
                etfs[code] = {
                    'code': code,
                    'name': name,
                    'data': data,
                    'today_pct': today_pct
                }
    
    return etfs

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
        def calculate_momentum(price_data):
            """计算动量得分，复用原始策略公式"""
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
            'slope': round(slope, 6)
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
