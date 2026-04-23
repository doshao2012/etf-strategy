# ETF轮动策略 - 网页版

## 项目概述

基于微信小程序 ETF 轮动策略的移动端适配网页版本。

## 技术栈

- **前端框架**: Next.js 16 (App Router)
- **UI组件**: shadcn/ui + Tailwind CSS 4
- **后端**: NestJS (独立服务，端口 3000)
- **数据**: 模拟数据（用于预览）

## 目录结构

```
.
├── src/
│   ├── app/
│   │   ├── layout.tsx          # 根布局
│   │   ├── page.tsx           # ETF策略主页
│   │   └── globals.css        # 全局样式
│   ├── components/ui/         # shadcn/ui 组件库
│   ├── lib/
│   │   └── api.ts             # API客户端
│   └── server.ts              # 自定义服务入口（含API代理）
├── server/                    # NestJS 后端
│   ├── src/
│   │   └── modules/strategy/  # 策略模块
│   └── package.json
└── .coze                      # Coze CLI 配置
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/strategy/etf-rotation` | GET | 趋势轮动策略 |
| `/strategy/oversold` | GET | 超跌策略 |

## 策略逻辑

### 趋势轮动策略
- **回看周期**: 25 个交易日
- **筛选条件**: 动量得分 >= 0.0
- **稳定性**: R² 加权
- **风控**: 近3日单日跌幅超过3%则拦截

### 超跌策略
- **触发条件**: 近期跌幅 > 3% 且 RSI < 40
- **用途**: 危机模式，寻找反弹机会

## 开发命令

```bash
# 安装前端依赖
pnpm install

# 启动前端开发服务器（端口5000）
pnpm dev

# 启动后端服务（端口3000）
cd server && pnpm install && pnpm start
```

## ETF 品种

| 代码 | 名称 | 类型 |
|------|------|------|
| 159915 | 创业板ETF | 股票 |
| 518880 | 黄金ETF | 商品 |
| 513100 | 纳指ETF | 海外 |
| 511220 | 城投债ETF | 债券 |
| 588000 | 科创50ETF | 股票 |
| 159985 | 豆粕ETF | 商品 |
| 513260 | 恒生科技ETF | 海外 |

## 注意事项

1. 当前使用模拟数据，需接入真实数据源才能用于实际投资决策
2. 数据仅供参考，不构成投资建议
3. 市场有风险，投资需谨慎
