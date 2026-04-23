#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动获取并更新所有ETF真实数据
"""
import json
import os
import sys
from fetch_real_etf_data import fetch_etf_from_eastmoney

# ETF列表
ETF_LIST = [
    {'code': '159915', 'name': '创业板ETF'},
    {'code': '518880', 'name': '黄金ETF'},
    {'code': '513100', 'name': '纳指ETF'},
    {'code': '511220', 'name': '城投债ETF'},
    {'code': '588000', 'name': '科创50ETF'},
    {'code': '159985', 'name': '豆粕ETF'},
    {'code': '513260', 'name': '恒生科技ETF'},
]

def main():
    print("开始获取ETF真实数据...\n")

    all_data = {}

    for etf in ETF_LIST:
        print(f"正在获取 {etf['name']} ({etf['code']})...")
        data = fetch_etf_from_eastmoney(etf['code'], 30)

        if data:
            all_data[etf['code']] = data
            latest = data[-1]
            print(f"  ✅ 成功！最新: {latest['date']} 收盘:{latest['close']:.4f} 涨跌:{latest.get('dailyChangePercent', 0):.2f}%")
        else:
            print(f"  ❌ 失败！")
        print()

    # 生成TypeScript配置文件
    config_content = f"""// ETF真实历史数据配置
// 自动生成于: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
// 数据来源: 东方财富基金净值API

export const REAL_ETF_DATA: {{ [code: string]: PriceDataRow[] }} = {{
"""

    for etf in ETF_LIST:
        code = etf['code']
        if code in all_data:
            data_str = json.dumps(all_data[code], ensure_ascii=False, indent=4)
            data_str = data_str.replace('\n', '\n    ')
            config_content += f"  // {etf['name']} ({code})\n"
            config_content += f"  '{code}': [\n    {data_str}\n  ],\n\n"

    config_content += """};

export interface PriceDataRow {
  date: string;        // 日期，格式: 'YYYY-MM-DD'
  open: number;        // 开盘价
  high: number;        // 最高价
  low: number;         // 最低价
  close: number;       // 收盘价
  volume: number;      // 成交量
}
"""

    # 写入配置文件
    config_file = '/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts'
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(config_content)

    print(f"✅ 配置文件已更新: {config_file}")
    print(f"✅ 共获取 {len(all_data)}/{len(ETF_LIST)} 只ETF的真实数据")

if __name__ == "__main__":
    main()
