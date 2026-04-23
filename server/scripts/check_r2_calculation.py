#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新分析聚宽代码的R²计算
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
print("重新分析聚宽代码的R²计算")
print("=" * 80)

# 聚宽方法
slope_jq, intercept_jq = np.polyfit(x, y, 1, w=weights)

# 聚宽的R²计算
ss_res_jq = np.sum(weights * (y - (slope_jq * x + intercept_jq)) ** 2)
ss_tot_jq = np.sum(weights * (y - np.mean(y)) ** 2)
r_squared_jq = 1 - ss_res_jq / ss_tot_jq if ss_tot_jq else 0

print(f"\n【聚宽方法】")
print(f"  斜率: {slope_jq:.6f}")
print(f"  截距: {intercept_jq:.6f}")
print(f"  R²: {r_squared_jq:.6f}")

print(f"\n聚宽代码中的R²计算公式：")
print(f"  ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)")
print(f"  ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)")
print(f"  r_squared = 1 - ss_res / ss_tot")

print(f"\n注意：聚宽代码中使用了 np.mean(y)，而不是加权均值！")
print(f"  np.mean(y) = {np.mean(y):.6f}")
print(f"  加权均值 = {np.sum(weights * y) / np.sum(weights):.6f}")

# 测试：使用加权均值计算R²
mean_y_weighted = np.sum(weights * y) / np.sum(weights)
ss_res_w = np.sum(weights * (y - (slope_jq * x + intercept_jq)) ** 2)
ss_tot_w = np.sum(weights * (y - mean_y_weighted) ** 2)
r_squared_w = 1 - ss_res_w / ss_tot_w if ss_tot_w else 0

print(f"\n【使用加权均值计算R²】")
print(f"  R² = {r_squared_w:.6f}")
print(f"  差异: {abs(r_squared_jq - r_squared_w):.6f}")

# 检查聚宽代码的原始公式
# 聚宽代码：
# ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
# ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
# r_squared = 1 - ss_res / ss_tot if ss_tot else 0

# 这说明聚宽确实使用了 np.mean(y)，而不是加权均值

# 但是，在标准统计学中，加权R²应该使用加权均值

# 让我验证一下，小程序后端是否也应该使用加权均值

print("\n" + "=" * 80)
print("检查小程序后端是否应该使用加权均值")
print("=" * 80)

print("\n小程序后端代码中的R²计算：")
print("  const meanY = sumWY / sumW;  // 加权均值")
print("  ssTot += w * Math.pow(y[i] - meanY, 2);  // 使用加权均值")

print("\n这与聚宽代码不同！")
print("  聚宽使用 np.mean(y)")
print("  小程序使用加权均值")

print(f"\n是否应该修改小程序代码以匹配聚宽代码？")
print(f"  从统计学角度来看，加权R²应该使用加权均值")
print(f"  但是为了与聚宽代码完全一致，应该使用 np.mean(y)")
