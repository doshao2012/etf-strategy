#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完全按照聚宽算法实现的ETF动量计算
"""
import numpy as np
import math
import sys
import json
import sqlite3
import requests
import re
from datetime import datetime

# 从配置文件读取数据
CONFIG_FILE = '/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts'
DB_PATH = '/workspace/projects/server/database.sqlite'


def get_realtime_price(market, code):
    """获取实时价格"""
    try:
        url = f"https://qt.gtimg.cn/q={market}{code}"
        response = requests.get(url, timeout=5)
        content = response.text

        # 解析数据
        match = re.search(f'v_{market}{code}="([^"]+)"', content)
        if not match:
            return None

        data_str = match.group(1)
        fields = data_str.split('~')

        return {
            'current': float(fields[3]) if fields[3] else 0,
            'pre_close': float(fields[4]) if fields[4] else 0,
            'change_pct': float(fields[32]) if fields[32] else 0,
        }
    except Exception as e:
        print(f"获取实时价格失败: {e}", file=sys.stderr)
        return None


def get_etf_configs():
    """从数据库读取所有启用的ETF配置"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT code, name
            FROM etf_config
            WHERE isActive = 1
            ORDER BY createdAt ASC
        ''')

        configs = {}
        for row in cursor.fetchall():
            configs[row[0]] = row[1]

        conn.close()
        return configs
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return {}


def load_config():
    """读取配置文件"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # 从数据库获取ETF配置
    etf_configs = get_etf_configs()

    # 提取ETF数据
    etfs = {}

    # 遍历数据库中的所有ETF配置
    for code, name in etf_configs.items():
        pattern = rf"'{code}':\s*(\[[\s\S]*?\])\s*(,|//)"
        match = re.search(pattern, content)
        if match:
            data_str = match.group(1)
            try:
                data = json.loads(data_str)
                etfs[code] = {
                    'code': code,
                    'name': name,
                    'data': data
                }
            except json.JSONDecodeError:
                print(f"警告：无法解析 {name} ({code}) 的数据", file=sys.stderr)
                continue

    return etfs


def get_metrics(etf_info, lookback_days=25, score_threshold=0.0, loss_limit=0.97):
    """
    完全按照聚宽算法实现的动量计算
    """
    try:
        data = etf_info['data']
        if len(data) < lookback_days:
            return None

        # 提取 lookback_days + 1 个数据点（26个）
        data_slice = data[-(lookback_days + 1):]
        prices = np.array([d['close'] for d in data_slice])

        # 判断市场
        code = etf_info['code']
        market = 'sh' if code.startswith('5') else 'sz'
        
        # 获取实时价格并更新最后一条数据
        realtime = get_realtime_price(market, code)
        if realtime and realtime['current'] > 0:
            current_price = realtime['current']
            today_date = datetime.now().strftime('%Y-%m-%d')
            # 更新最后一条数据为实时价格
            data_slice[-1] = {
                'date': today_date,
                'open': realtime['current'],
                'high': realtime['current'],
                'low': realtime['current'],
                'close': realtime['current'],
                'volume': 0
            }
            prices = np.array([d['close'] for d in data_slice])
            # 用API返回的真实涨跌幅
            today_pct = realtime['change_pct']
        else:
            current_price = prices[-1]
            last_close = data_slice[-2]['close'] if len(data_slice) > 1 else prices[-2]
            today_pct = (current_price / last_close - 1) * 100

        # 昨日收盘价
        last_close = data_slice[-2]['close'] if len(data_slice) > 1 else prices[-2]

        # 动量得分 & 稳定性计算
        y = np.log(prices)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)

        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0

        ann_return = math.exp(slope * 250) - 1
        score = ann_return * r_squared

        # 状态判定
        status = "正常"
        ratios = [prices[-1]/prices[-2], prices[-2]/prices[-3], prices[-3]/prices[-4]]
        if min(ratios) < loss_limit:
            status = "⚠️ 跌幅拦截"
            score = -0.01
        elif score < score_threshold:
            status = "分值过低"

        # 预估动量得分
        estimated_prices = prices[1:]
        estimated_prices = np.append(estimated_prices, current_price)
        y_est = np.log(estimated_prices)
        x_est = np.arange(len(y_est))
        slope_est, _ = np.polyfit(x_est, y_est, 1, w=np.linspace(1, 2, len(y_est)))
        ann_return_est = math.exp(slope_est * 250) - 1
        ss_res_est = np.sum(np.linspace(1, 2, len(y_est)) * (y_est - (slope_est * x_est + np.mean(y_est))) ** 2)
        ss_tot_est = np.sum(np.linspace(1, 2, len(y_est)) * (y_est - np.mean(y_est)) ** 2)
        r_squared_est = 1 - ss_res_est / ss_tot_est if ss_tot_est else 0
        estimated_score = ann_return_est * r_squared_est

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
    lookback_days = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    score_threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    loss_limit = float(sys.argv[3]) if len(sys.argv) > 3 else 0.97

    etfs = load_config()

    results = []
    for code, etf_info in etfs.items():
        metrics = get_metrics(etf_info, lookback_days, score_threshold, loss_limit)
        if metrics:
            results.append(metrics)

    results.sort(key=lambda x: x['score'], reverse=True)

    recommend = None
    valid_etfs = [r for r in results if r['score'] >= score_threshold]
    if valid_etfs:
        recommend = valid_etfs[0]['code']

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
