#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用AKShare获取ETF真实历史数据
"""
import akshare as ak
import sys
import json
from datetime import datetime, timedelta

def get_etf_history(etf_code, days=30):
    """
    获取ETF历史数据

    Args:
        etf_code: ETF代码，如 '518880'
        days: 获取天数

    Returns:
        list: 历史数据列表
    """
    try:
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)  # 多取几天确保数据充足

        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        # 使用东方财富接口获取ETF历史数据
        df = ak.fund_etf_hist_em(
            symbol=etf_code,
            period="daily",
            start_date=start_date_str,
            end_date=end_date_str,
            adjust=""
        )

        if df.empty:
            print(f"ERROR: ETF {etf_code} 无数据", file=sys.stderr)
            return []

        # 取最后days天的数据
        df = df.tail(days)

        # 转换为JSON格式
        result = []
        for idx, row in df.iterrows():
            result.append({
                "date": idx.strftime('%Y-%m-%d'),
                "close": float(row['收盘']),
                "preClose": float(row['开盘']) if len(result) == 0 else float(result[-1]['close']),
                "dailyChangePercent": round((float(row['收盘']) - float(row['开盘'])) / float(row['开盘']) * 100, 2) if len(result) == len(result) else 0
            })

        # 修正涨跌幅计算（使用前一日收盘价）
        for i in range(len(result)):
            if i > 0:
                result[i]['preClose'] = result[i-1]['close']
                result[i]['dailyChangePercent'] = round((result[i]['close'] - result[i]['preClose']) / result[i]['preClose'] * 100, 2)
            else:
                # 第一天，使用当天的开盘价计算
                df_first = df.iloc[0]
                result[i]['dailyChangePercent'] = round((df_first['收盘'] - df_first['开盘']) / df_first['开盘'] * 100, 2)

        return result

    except Exception as e:
        print(f"ERROR: 获取ETF {etf_code} 数据失败: {str(e)}", file=sys.stderr)
        return []

def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_etf_data.py <etf_code> [days]", file=sys.stderr)
        sys.exit(1)

    etf_code = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    data = get_etf_history(etf_code, days)

    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
