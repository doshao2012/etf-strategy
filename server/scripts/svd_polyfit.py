#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 SVD 方法实现 np.polyfit 的算法
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
print("使用 SVD 方法实现 np.polyfit")
print("=" * 80)

# 参考 np.polyfit 的实现
# np.polyfit 使用加权最小二乘法，但可能使用 SVD 来解线性方程组

# 构造范德蒙德矩阵
V = np.vstack([x, np.ones(len(x))]).T

# 构造权重矩阵
W = np.diag(weights)

# 构造加权范德蒙德矩阵
V_weighted = np.sqrt(W) @ V
y_weighted = np.sqrt(W) @ y

# 使用 SVD 解最小二乘问题
U, s, Vh = np.linalg.svd(V_weighted, full_matrices=False)

# 计算伪逆
s_inv = np.zeros_like(s)
s_inv[s > 1e-10] = 1.0 / s[s > 1e-10]
V_weighted_pinv = Vh.T @ np.diag(s_inv) @ U.T

# 解
p_svd = V_weighted_pinv @ y_weighted
slope_svd, intercept_svd = p_svd[0], p_svd[1]

print(f"\n【SVD 方法】:")
print(f"  斜率: {slope_svd:.10f}")
print(f"  截距: {intercept_svd:.10f}")

# 对比
slope_np, intercept_np = np.polyfit(x, y, 1, w=weights)
print(f"\n【np.polyfit】:")
print(f"  斜率: {slope_np:.10f}")
print(f"  截距: {intercept_np:.10f}")

print(f"\n差异:")
print(f"  Δslope: {abs(slope_svd - slope_np):.10f}")
print(f"  Δintercept: {abs(intercept_svd - intercept_np):.10f}")

# 尝试其他方法
print("\n" + "=" * 80)
print("尝试其他方法")
print("=" * 80)

# 方法2：使用 np.linalg.lstsq
p_lstsq, residuals, rank, s = np.linalg.lstsq(V_weighted, y_weighted, rcond=None)
slope_lstsq, intercept_lstsq = p_lstsq[0], p_lstsq[1]
print(f"\n【np.linalg.lstsq】:")
print(f"  斜率: {slope_lstsq:.10f}")
print(f"  截距: {intercept_lstsq:.10f}")
print(f"  Δslope vs polyfit: {abs(slope_lstsq - slope_np):.10f}")

# 方法3：使用 QR 分解
Q, R = np.linalg.qr(V_weighted)
p_qr = np.linalg.solve(R, Q.T @ y_weighted)
slope_qr, intercept_qr = p_qr[0], p_qr[1]
print(f"\n【QR 分解】:")
print(f"  斜率: {slope_qr:.10f}")
print(f"  截距: {intercept_qr:.10f}")
print(f"  Δslope vs polyfit: {abs(slope_qr - slope_np):.10f}")

# 方法4：使用 cholesky 分解
try:
    L = np.linalg.cholesky(V_weighted.T @ V_weighted)
    z = np.linalg.solve(L, V_weighted.T @ y_weighted)
    p_chol = np.linalg.solve(L.T, z)
    slope_chol, intercept_chol = p_chol[0], p_chol[1]
    print(f"\n【Cholesky 分解】:")
    print(f"  斜率: {slope_chol:.10f}")
    print(f"  截距: {intercept_chol:.10f}")
    print(f"  Δslope vs polyfit: {abs(slope_chol - slope_np):.10f}")
except np.linalg.LinAlgError:
    print(f"\n【Cholesky 分解】: 矩阵不是正定的")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)

all_methods = [
    ("SVD", abs(slope_svd - slope_np)),
    ("lstsq", abs(slope_lstsq - slope_np)),
    ("QR", abs(slope_qr - slope_np)),
]

all_methods.sort(key=lambda x: x[1])
print(f"\n最接近 np.polyfit 的方法: {all_methods[0][0]}")
print(f"差异: {all_methods[0][1]:.10f}")

if all_methods[0][1] < 1e-10:
    print(f"\n✅ 找到了 np.polyfit 的算法！")
else:
    print(f"\n❌ 所有方法都与 np.polyfit 有差异！")
    print(f"可能 np.polyfit 使用了特殊的优化或归一化方法。")

# 尝试直接查看 numpy 的源码
print(f"\n" + "=" * 80)
print("检查 np.polyfit 的权重归一化")
print("=" * 80)

# 检查 np.polyfit 是否对权重进行了归一化
weights_normalized = weights / np.sum(weights)
slope_norm, intercept_norm = np.polyfit(x, y, 1, w=weights_normalized)
print(f"\n使用归一化权重:")
print(f"  斜率: {slope_norm:.10f}")
print(f"  Δslope vs polyfit: {abs(slope_norm - slope_np):.10f}")

# 检查是否使用了权重的平方
weights_sqrt = np.sqrt(weights)
slope_sqrt, intercept_sqrt = np.polyfit(x, y, 1, w=weights_sqrt)
print(f"\n使用 sqrt(weights):")
print(f"  斜率: {slope_sqrt:.10f}")
print(f"  Δslope vs polyfit: {abs(slope_sqrt - slope_np):.10f}")

# 检查是否使用了权重的平方根的平方
weights_sqrt2 = np.sqrt(np.sqrt(weights))
slope_sqrt2, intercept_sqrt2 = np.polyfit(x, y, 1, w=weights_sqrt2)
print(f"\n使用 sqrt(sqrt(weights)):")
print(f"  斜率: {slope_sqrt2:.10f}")
print(f"  Δslope vs polyfit: {abs(slope_sqrt2 - slope_np):.10f}")
