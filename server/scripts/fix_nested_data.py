#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复配置文件中的双重嵌套问题
"""
import json

# 读取配置文件
with open('/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到数据部分并修复双重嵌套
import re

# 查找所有 'XXXX': [[...]] 模式，替换为 'XXXX': [...]
pattern = r"'(\d{6})':\s*\[\s*\["
content = re.sub(pattern, r"'\1': [", content)

# 修复结束的 ]]
content = re.sub(r"\]\s*\],\s*\n", "],\n", content)

# 写回文件
with open('/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 已修复双重嵌套问题")
