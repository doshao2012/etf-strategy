#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证权重计算是否一致
"""
import numpy as np

n = 25

# 聚宽的权重计算
weights_joinquant = np.linspace(1, 2, n)

# 小程序的权重计算
weights_nestjs = [1 + (i / (n - 1)) for i in range(n)]

print("权重对比（前5个和后5个）：")
print("=" * 60)
print(f"聚宽权重: {weights_joinquant[:5]} ... {weights_joinquant[-5:]}")
print(f"小程序权重: {weights_nestjs[:5]} ... {weights_nestjs[-5:]}")
print()

print("最大差异:")
max_diff = max(abs(wj - wn) for wj, wn in zip(weights_joinquant, weights_nestjs))
print(f"{max_diff:.15f}")
print()

if max_diff < 1e-10:
    print("✅ 权重计算完全一致！")
else:
    print("❌ 权重计算有差异！")

print("\n\n手动验证回归参数...")
print("=" * 60)

# 模拟数据
y = np.log([3.225, 3.201, 3.296, 3.335, 3.308, 3.3, 3.349, 3.273, 3.338, 3.303,
            3.341, 3.228, 3.237, 3.307, 3.263, 3.293, 3.264, 3.182, 3.141, 3.151,
            3.345, 3.32, 3.437, 3.468, 3.55, 3.511, 3.624, 3.669])

# 使用最后25个点
y = y[-25:]
x = np.arange(len(y))
w = weights_joinquant

# 聚宽方法
slope_jq, intercept_jq = np.polyfit(x, y, 1, w=w)
print(f"聚宽方法: slope={slope_jq:.6f}, intercept={intercept_jq:.6f}")

# 手动计算方法1（标准公式）
sumW = np.sum(w)
sumWX = np.sum(w * x)
sumWY = np.sum(w * y)

meanX = sumWX / sumW
meanY = sumWY / sumW

numerator = np.sum(w * (x - meanX) * (y - meanY))
denominator = np.sum(w * (x - meanX) ** 2)
slope_manual1 = numerator / denominator
intercept_manual1 = meanY - slope_manual1 * meanX

print(f"手动方法1: slope={slope_manual1:.6f}, intercept={intercept_manual1:.6f}")

# 手动计算方法2（直接最小二乘）
# 最小化 sum(w * (y - (m*x + b))^2)
# 对m求偏导: sum(2*w*(y - (m*x + b))*(-x)) = 0
# 对b求偏导: sum(2*w*(y - (m*x + b))) = 0
# => sum(w*x*y) - m*sum(w*x^2) - b*sum(w*x) = 0
# => sum(w*y) - m*sum(w*x) - b*sum(w) = 0

sumWXY = np.sum(w * x * y)
sumWX2 = np.sum(w * x * x)
sumWX = np.sum(w * x)
sumWY = np.sum(w * y)

# 从两个方程解出m和b
# sumWXY - m*sumWX2 - b*sumWX = 0
# sumWY - m*sumWX - b*sumW = 0

# 用克莱姆法则
det = sumWX2 * sumW - sumWX * sumWX
if abs(det) > 1e-10:
    slope_manual2 = (sumWXY * sumW - sumWX * sumWY) / det
    intercept_manual2 = (sumWX2 * sumWY - sumWX * sumWXY) / det
    print(f"手动方法2: slope={slope_manual2:.6f}, intercept={intercept_manual2:.6f}")
else:
    print(f"无法使用方法2（行列式为0）")

print("\n差异对比:")
print(f"聚宽 vs 手动1: slope差异={abs(slope_jq - slope_manual1):.10f}, intercept差异={abs(intercept_jq - intercept_manual1):.10f}")
