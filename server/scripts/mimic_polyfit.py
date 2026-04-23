#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接模拟 np.polyfit 的完整实现
"""
import numpy as np
import math

# 模拟数据
prices = np.array([3.225, 3.201, 3.296, 3.335, 3.308, 3.3, 3.349, 3.273, 3.338, 3.303,
                   3.341, 3.228, 3.237, 3.307, 3.263, 3.293, 3.264, 3.182, 3.141, 3.151,
                   3.345, 3.32, 3.437, 3.468, 3.55, 3.511, 3.624, 3.669])

prices = prices[-25:]
y = np.log(prices)
x = np.arange(len(y))
weights = np.linspace(1, 2, len(y))

print("=" * 80)
print("直接模拟 np.polyfit 的完整实现")
print("=" * 80)

# 聚宽方法
slope_jq, intercept_jq = np.polyfit(x, y, 1, w=weights)

# 聚宽的R²计算
ss_res_jq = np.sum(weights * (y - (slope_jq * x + intercept_jq)) ** 2)
ss_tot_jq = np.sum(weights * (y - np.mean(y)) ** 2)
r_squared_jq = 1 - ss_res_jq / ss_tot_jq if ss_tot_jq else 0

# 计算得分
ann_return_jq = math.exp(slope_jq * 250) - 1
score_jq = ann_return_jq * r_squared_jq

print(f"\n【聚宽方法】")
print(f"  斜率: {slope_jq:.10f}")
print(f"  截距: {intercept_jq:.10f}")
print(f"  R²: {r_squared_jq:.10f}")
print(f"  年化收益率: {ann_return_jq:.10f}")
print(f"  动量得分: {score_jq:.10f}")

# 尝试使用 np.polyval 来检查预测值
y_pred_jq = np.polyval([slope_jq, intercept_jq], x)
print(f"\n  预测值（前5个）: {y_pred_jq[:5]}")

# 尝试使用权重平方根
print("\n" + "=" * 80)
print("尝试使用权重平方根")
print("=" * 80)

# 构造范德蒙德矩阵
V = np.vstack([x, np.ones(len(x))]).T

# 使用权重平方根
W_sqrt = np.diag(np.sqrt(weights))

# 构造加权矩阵
V_weighted = W_sqrt @ V
y_weighted = W_sqrt @ y

# 使用最小二乘法
result = np.linalg.lstsq(V_weighted, y_weighted, rcond=None)
slope_sqrt, intercept_sqrt = result[0]

# 计算R²（使用原始权重）
ss_res_sqrt = np.sum(weights * (y - (slope_sqrt * x + intercept_sqrt)) ** 2)
ss_tot_sqrt = np.sum(weights * (y - np.mean(y)) ** 2)
r_squared_sqrt = 1 - ss_res_sqrt / ss_tot_sqrt if ss_tot_sqrt else 0

# 计算得分
ann_return_sqrt = math.exp(slope_sqrt * 250) - 1
score_sqrt = ann_return_sqrt * r_squared_sqrt

print(f"\n【权重平方根方法】")
print(f"  斜率: {slope_sqrt:.10f}")
print(f"  截距: {intercept_sqrt:.10f}")
print(f"  R²: {r_squared_sqrt:.10f}")
print(f"  年化收益率: {ann_return_sqrt:.10f}")
print(f"  动量得分: {score_sqrt:.10f}")

print(f"\n与聚宽对比:")
print(f"  Δslope: {abs(slope_jq - slope_sqrt):.10f}")
print(f"  Δscore: {abs(score_jq - score_sqrt):.10f}")

# 如果还是不一样，尝试直接从 numpy 源码复制实现
print("\n" + "=" * 80)
print("结论")
print("=" * 80)

if abs(slope_jq - slope_sqrt) < 1e-10:
    print("\n✅ 找到了！np.polyfit 使用权重平方根！")
else:
    print(f"\n❌ np.polyfit 的算法仍然未知")
    print(f"\n建议：直接使用 np.linalg.lstsq 或其他标准的加权回归算法")
    print(f"  虽然结果与聚宽代码略有不同，但统计学上可能更正确")
