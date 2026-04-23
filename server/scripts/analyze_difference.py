#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仔细对比聚宽代码的每个细节
"""
import numpy as np
import math

# 聚宽创业板ETF的结果
jq_score = 1.0589
jq_r_squared = 0.421

# 我的创业板ETF的结果
my_score = 0.5928
my_r_squared = 0.322

print("=" * 80)
print("聚宽 vs 我的代码对比")
print("=" * 80)

print(f"\n聚宽结果:")
print(f"  得分: {jq_score}")
print(f"  R²: {jq_r_squared}")

print(f"\n我的结果:")
print(f"  得分: {my_score}")
print(f"  R²: {my_r_squared}")

print(f"\n差异:")
print(f"  Δ得分: {abs(jq_score - my_score):.6f}")
print(f"  ΔR²: {abs(jq_r_squared - my_r_squared):.6f}")

# 计算聚宽的斜率
jq_ann_return = jq_score / jq_r_squared
jq_slope = math.log(jq_ann_return + 1) / 250

print(f"\n聚宽的斜率推导:")
print(f"  年化收益率 = 得分 / R² = {jq_score} / {jq_r_squared} = {jq_ann_return:.6f}")
print(f"  斜率 = log(年化收益率 + 1) / 250 = log({jq_ann_return + 1}) / 250 = {jq_slope:.6f}")

# 我的斜率
my_ann_return = my_score / my_r_squared
my_slope = math.log(my_ann_return + 1) / 250

print(f"\n我的斜率推导:")
print(f"  年化收益率 = 得分 / R² = {my_score} / {my_r_squared} = {my_ann_return:.6f}")
print(f"  斜率 = log(年化收益率 + 1) / 250 = log({my_ann_return + 1}) / 250 = {my_slope:.6f}")

print(f"\n斜率差异: {abs(jq_slope - my_slope):.6f}")

# 从斜率差异推断数据差异
print(f"\n" + "=" * 80)
print("数据差异分析")
print("=" * 80)

print(f"\n聚宽的斜率 ({jq_slope:.6f}) 比我的斜率 ({my_slope:.6f}) 小")
print(f"这说明聚宽的价格序列增长速度比我的慢")

print(f"\n可能的差异:")
print(f"  1. 数据时间范围不同")
print(f"  2. 数据质量不同（聚宽使用复权价格，我使用前复权价格？）")
print(f"  3. 数据更新时间不同")

print(f"\n" + "=" * 80)
print("聚宽代码中的关键点")
print("=" * 80)

print(f"\n1. 数据获取:")
print(f"   df = get_price(etf, end_date=check_date, frequency='daily',")
print(f"                  fields=['close', 'pre_close'], count=lookback_days + 5)")
print(f"   这行代码获取的是到 check_date（今天）的数据，")
print(f"   包含 close 和 pre_close 字段，共 30 天")

print(f"\n2. 价格提取:")
print(f"   prices = df.iloc[-(lookback_days + 1):]['close'].values")
print(f"   这行代码取最后 26 个 close 价格")

print(f"\n3. 今日涨跌幅:")
print(f"   current_price = prices[-1]")
print(f"   last_close = df.iloc[-1]['pre_close']")
print(f"   today_pct = (current_price / last_close - 1) * 100")

print(f"\n关键点：last_close = df.iloc[-1]['pre_close']")
print(f"   df.iloc[-1] 是整个 DataFrame 的最后一行，")
print(f"   它的 pre_close 字段是昨日收盘价")

print(f"\n而我的代码中:")
print(f"   last_close = data[-2]['close']")
print(f"   data[-2] 是倒数第二行的 close 价格")

print(f"\n这可能就是差异所在！")
print(f"   聚宽使用的是 df.iloc[-1]['pre_close']")
print(f"   我使用的是 data[-2]['close']")

print(f"\n这两个值可能不同！")
print(f"   因为 pre_close 是昨日收盘价，而 data[-2]['close'] 也是昨日收盘价")
print(f"   但如果数据来源不同，这两个值可能不同")

print(f"\n建议:")
print(f"   1. 确认数据源的差异")
print(f"   2. 尝试获取聚宽相同的数据源")
print(f"   3. 或者接受数据源不同导致的差异，但确保算法一致")
