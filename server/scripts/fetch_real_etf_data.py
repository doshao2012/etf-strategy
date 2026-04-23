#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从东方财富基金净值API获取真实ETF数据
"""
import requests
import re
import json
import sys
from datetime import datetime, timedelta

def fetch_etf_from_eastmoney(etf_code, days=30):
    """
    从东方财富基金净值API获取ETF数据

    Args:
        etf_code: ETF代码
        days: 获取天数

    Returns:
        list: 价格数据列表
    """
    try:
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 30)

        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        # 请求东方财富基金净值数据API
        url = f"https://fundf10.eastmoney.com/F10DataApi.aspx?type=lsjz&code={etf_code}&page=1&per={days+10}&sdate={start_date_str}&edate={end_date_str}"

        print(f"Fetching: {url}", file=sys.stderr)

        response = requests.get(url, timeout=15)
        response.encoding = 'utf-8'

        if response.status_code != 200:
            print(f"ERROR: HTTP {response.status_code}", file=sys.stderr)
            return []

        content = response.text

        # 提取表格行数据
        rows = re.findall(r'<tr>(.*?)</tr>', content, re.DOTALL)

        data = []
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row)
            if len(cells) >= 3:
                # 提取日期、净值、增长率
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', cells[0])
                nav_match = re.search(r'([\d.]+)', cells[1])
                growth_match = re.search(r'([\d.-]+)%', cells[2])

                if date_match and nav_match:
                    date = date_match.group(1)
                    nav = float(nav_match.group(1))

                    # 解析日增长率
                    daily_change = 0
                    if growth_match:
                        daily_change = float(growth_match.group(1))

                    # 检查日期范围
                    date_obj = datetime.strptime(date, '%Y-%m-%d')
                    if date_obj >= start_date:
                        data.append({
                            'date': date,
                            'open': nav,
                            'high': nav,
                            'low': nav,
                            'close': nav,
                            'volume': 0
                        })

        # 按日期排序
        data.sort(key=lambda x: x['date'])

        # 限制数量
        result = data[-days:]

        # 重新计算涨跌幅（基于净值变化）
        for i in range(1, len(result)):
            result[i]['dailyChangePercent'] = round(
                ((result[i]['close'] - result[i-1]['close']) / result[i-1]['close']) * 100, 2
            )

        if result:
            result[0]['dailyChangePercent'] = round(
                ((result[0]['close'] - result[0]['open']) / result[0]['open']) * 100, 2
            )

        return result

    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return []

def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_real_etf_data.py <etf_code> [days]", file=sys.stderr)
        print("Example: python fetch_real_etf_data.py 518880 30", file=sys.stderr)
        sys.exit(1)

    etf_code = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    data = fetch_etf_from_eastmoney(etf_code, days)

    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
