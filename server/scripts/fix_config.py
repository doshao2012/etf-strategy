#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复配置文件中的双重嵌套问题
"""
import re
import json

with open('/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到所有ETF的数据部分
pattern = r"'(\d{6})':\s*\[\s*(\[.*?\])\s*\],"

def fix_nesting(match):
    code = match.group(1)
    data_str = match.group(2)
    print(f"处理 {code}...")
    try:
        data = json.loads(data_str)
        # 如果第一个元素是列表，说明有嵌套
        if data and isinstance(data[0], list):
            print(f"  检测到嵌套，解包...")
            data = data[0]
        # 重新格式化
        formatted = json.dumps(data, ensure_ascii=False, indent=4)
        formatted = formatted.replace('\n', '\n    ')
        return f"  // 处理后的数据\n  '{code}': [\n    {formatted}\n  ],"
    except Exception as e:
        print(f"  错误: {e}")
        return match.group(0)

content = re.sub(pattern, fix_nesting, content, flags=re.DOTALL)

# 写回文件
with open('/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ 配置文件已修复")
