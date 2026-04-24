#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 JSON 文件读取 ETF 配置并获取市场数据，生成配置文件
"""
import sys
import requests
import json
import re
import os
from datetime import datetime

# 配置文件路径
CONFIG_FILE = '/app/server/etf_config.json'
CONFIG_OUTPUT_PATH = '/app/server/src/modules/strategy/etf-real-data.config.ts'


def get_etf_configs():
    """从 JSON 文件读取所有启用的 ETF 配置"""
    try:
        if not os.path.exists(CONFIG_FILE):
            print(f"Error: {CONFIG_FILE} not found", file=sys.stderr)
            return []
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            all_configs = json.load(f)
        
        # 只返回启用的配置
        configs = [c for c in all_configs if c.get('isActive', True)]
        return [{'code': c['code'], 'market': c['market'], 'name': c['name']} for c in configs]
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return []


def get_realtime(market, code):
    """从腾讯财经获取实时价格"""
    try:
        url = f"https://qt.gtimg.cn/q={market}{code}"
        response = requests.get(url, timeout=5)
        content = response.text

        match = re.search(f'v_{market}{code}="([^"]+)"', content)
        if not match:
            return None

        fields = match.group(1).split('~')
        raw_date = fields[30] if len(fields) > 30 else datetime.now().strftime('%Y%m%d%H%M%S')
        if len(raw_date) >= 8:
            formatted_date = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        else:
            formatted_date = datetime.now().strftime('%Y-%m-%d')

        return {
            'current': float(fields[3]) if fields[3] else 0,
            'pre_close': float(fields[4]) if fields[4] else 0,
            'date': formatted_date,
        }
    except Exception as e:
        print(f"获取实时价格失败 {market}{code}: {e}", file=sys.stderr)
        return None


def get_historical_data(market, code, count=26):
    """从新浪财经获取历史K线数据"""
    try:
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen={count+10}"
        response = requests.get(url, timeout=10)
        data = json.loads(response.text)

        if not data or len(data) == 0:
            return []
        
        # 删除今天的数据（避免重复）
        today = datetime.now().strftime('%Y-%m-%d')
        data = [d for d in data if d.get('day', '')[:10] != today]
        
        # 只取最近 count 个
        data = data[-count:] if len(data) >= count else data
        
        return data
    except Exception as e:
        print(f"获取历史数据失败 {market}{code}: {e}", file=sys.stderr)
        return []


def generate_config():
    """生成配置文件"""
    configs = get_etf_configs()
    if not configs:
        print("错误：未找到任何ETF配置", file=sys.stderr)
        sys.exit(1)
    
    print(f"找到 {len(configs)} 个 ETF 配置")
    
    output_lines = []
    output_lines.append("// ETF 实时数据配置文件")
    output_lines.append("// 自动生成，请勿手动修改")
    output_lines.append(f"// 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output_lines.append("")
    output_lines.append("export const ETF_MARKET_DATA = {")

    for config in configs:
        code = config['code']
        market = config['market']
        name = config['name']
        
        print(f"处理 {name} ({market}{code})...")
        
        # 获取历史数据
        historical = get_historical_data(market, code, 26)
        price_data = []
        
        for item in historical:
            price = float(item.get('close', 0))
            date = item.get('day', '')[:10]
            if price > 0 and date:
                price_data.append({'date': date, 'price': price})
        
        # 获取实时数据
        realtime = get_realtime(market, code)
        if realtime:
            today = datetime.now().strftime('%Y-%m-%d')
            price_data.append({
                'date': today,
                'price': realtime['current'],
                'isRealtime': True
            })
        
        if price_data:
            output_lines.append(f"  '{code}': {{")
            output_lines.append(f"    name: '{name}',")
            output_lines.append(f"    data: [")
            
            for item in price_data:
                date = item['date']
                price = item['price']
                if item.get('isRealtime'):
                    output_lines.append(f"      {{ date: '{date}', price: {price}, volume: 0 }},")
                else:
                    output_lines.append(f"      {{ date: '{date}', price: {price} }},")
            
            output_lines.append("    ],")
            output_lines.append("  },")
            print(f"  {name}: {len(price_data)} 条数据")
        else:
            print(f"  {name}: 无数据")

    output_lines.append("};")
    output_lines.append("")
    
    # 确保目录存在
    os.makedirs(os.path.dirname(CONFIG_OUTPUT_PATH), exist_ok=True)
    
    with open(CONFIG_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    print(f"\n配置文件已生成: {CONFIG_OUTPUT_PATH}")


if __name__ == '__main__':
    generate_config()
