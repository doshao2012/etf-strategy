#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动修复配置文件
"""
with open('/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts', 'r', encoding='utf-8') as f:
    lines = f.readlines()

result = []
skip_next_bracket = False

for i, line in enumerate(lines):
    # 检测到 "'code': [" 后面紧接着 '[' 的情况
    if line.strip().startswith("'") and ':' in line and '[' in line:
        # 检查下一行是否是独立的 '['
        if i + 1 < len(lines) and lines[i + 1].strip() == '[':
            # 跳过下一行的 '['
            skip_next_bracket = True
            result.append(line)
            continue

    # 如果需要跳过 '['
    if skip_next_bracket and line.strip() == '[':
        skip_next_bracket = False
        continue

    result.append(line)

# 写回文件
with open('/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts', 'w', encoding='utf-8') as f:
    f.writelines(result)

print("✅ 配置文件已修复")
