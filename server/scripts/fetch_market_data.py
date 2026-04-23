#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取ETF二级市场交易数据
"""
import requests
import re
import json
import sys
from datetime import datetime, timedelta

# ETF列表
ETF_LIST = [
    {'code': '159915', 'market': 'sz', 'name': '创业板ETF'},
    {'code': '518880', 'market': 'sh', 'name': '黄金ETF'},
    {'code': '513100', 'market': 'sh', 'name': '纳指ETF'},
    {'code': '511220', 'market': 'sh', 'name': '城投债ETF'},
    {'code': '588000', 'market': 'sh', 'name': '科创50ETF'},
    {'code': '159985', 'market': 'sz', 'name': '豆粕ETF'},
    {'code': '513260', 'market': 'sh', 'name': '恒生科技ETF'},
]

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
            'name': fields[1],
            'current': float(fields[3]) if fields[3] else 0,
            'pre_close': float(fields[4]) if fields[4] else 0,
            'open': float(fields[5]) if fields[5] else 0,
            'change': float(fields[11]) if fields[11] else 0,
            'change_pct': float(fields[12]) if fields[12] else 0,
            'high': float(fields[41]) if len(fields) > 41 and fields[41] else 0,
            'low': float(fields[42]) if len(fields) > 42 and fields[42] else 0,
            'volume': int(fields[6]) if fields[6] else 0,
            'time': fields[30] if len(fields) > 30 else '',
        }
    except Exception as e:
        print(f"获取实时价格失败: {e}", file=sys.stderr)
        return None

def get_historical_data(code, days=30):
    """获取历史K线数据"""
    try:
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)

        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        # 使用新浪财经获取历史K线数据
        market = 'sz' if code.startswith('15') else 'sh'
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen={days+30}"

        response = requests.get(url, timeout=15)
        content = response.text

        # 解析JSON数据
        if not content or content == 'null':
            # 尝试使用备用API
            url2 = f"https://api.finance.163.com/hs/kline/{market}/code/{code}.json"
            response2 = requests.get(url2, timeout=15)
            content2 = response2.json()
            if 'list' in content2:
                return parse_163_data(content2['list'], days)

        return parse_sina_data(content, days)

    except Exception as e:
        print(f"获取历史数据失败: {e}", file=sys.stderr)
        return []

def parse_sina_data(content, days):
    """解析新浪财经数据"""
    try:
        data = json.loads(content)
        if not data:
            return []

        result = []
        for item in data[-days:]:
            result.append({
                'date': item['day'],
                'open': float(item['open']),
                'high': float(item['high']),
                'low': float(item['low']),
                'close': float(item['close']),
                'volume': int(item['volume']),
            })

        return result
    except:
        return []

def parse_163_data(data_list, days):
    """解析网易财经数据"""
    result = []
    for item in data_list[-days:]:
        result.append({
            'date': item[0],
            'open': float(item[1]),
            'close': float(item[2]),
            'high': float(item[3]),
            'low': float(item[4]),
            'volume': int(item[5]),
        })
    return result

def main():
    print("开始获取二级市场实时数据...\n")

    all_data = {}

    for etf in ETF_LIST:
        print(f"正在获取 {etf['name']} ({etf['code']})...")

        # 获取实时价格
        realtime = get_realtime_price(etf['market'], etf['code'])

        if realtime:
            print(f"  实时: {realtime['current']:.4f} ({realtime['change_pct']:+.2f}%)")
        else:
            print(f"  ❌ 实时数据获取失败")
            continue

        # 获取历史数据（需要26个，确保删除今天的数据后还有25个）
        history = get_historical_data(etf['code'], 40)

        if history and len(history) > 0:
            # 获取最后26个历史数据
            history_26 = history[-26:]

            # 拼接实时价格作为第26个数据点
            today_date = datetime.now().strftime('%Y-%m-%d')

            # 检查最后一条历史数据是否是今天的日期，如果是则删除
            if history_26 and history_26[-1]['date'] == today_date:
                history_26 = history_26[:-1]

            today_data = {
                'date': today_date,
                'open': realtime['current'],  # 使用实时价格作为开盘价（简化处理）
                'high': realtime['current'],
                'low': realtime['current'],
                'close': realtime['current'],
                'volume': realtime['volume'],
            }

            # 拼接：25个历史 + 1个实时 = 26个数据
            combined_data = history_26 + [today_data]

            all_data[etf['code']] = combined_data
            print(f"  ✅ 成功！历史数据 {len(history_26)} 天 + 实时价格 = {len(combined_data)} 天")
        else:
            print(f"  ❌ 历史数据获取失败")

        print()

    # 生成配置文件
    if all_data:
        config_content = f"""// ETF二级市场交易数据配置
// 自动生成于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
// 数据来源: 腾讯财经实时行情 + 历史K线

export const REAL_ETF_DATA: {{ [code: string]: PriceDataRow[] }} = {{
"""

        for etf in ETF_LIST:
            code = etf['code']
            if code in all_data:
                # 确保数据是列表而不是嵌套列表
                data = all_data[code]
                if data and isinstance(data, list) and len(data) > 0:
                    # 检查是否有嵌套
                    if isinstance(data[0], list):
                        data = data[0]

                    # 直接序列化为数组（不添加外层方括号）
                    config_content += f"  // {etf['name']} ({code})\n"
                    config_content += f"  '{code}': [\n"
                    for i, item in enumerate(data):
                        item_str = json.dumps(item, ensure_ascii=False)
                        item_str = '    ' + item_str
                        if i < len(data) - 1:
                            item_str += ','
                        config_content += item_str + '\n'
                    config_content += "  ],\n\n"

        config_content += """};

export interface PriceDataRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
"""

        # 写入文件
        with open('/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts', 'w', encoding='utf-8') as f:
            f.write(config_content)

        print(f"✅ 配置文件已更新")
        print(f"✅ 共获取 {len(all_data)} 只ETF的二级市场数据")
    else:
        print("❌ 未能获取任何数据")

if __name__ == "__main__":
    main()
