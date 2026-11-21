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
- **算法**: 动态 MA10（盘中用实时价替换最旧一根K线）× (1 - 9%) 得到 ENE 下轨
- **筛选**: 成交额 >= 1 亿；同核心名只保留成交额最大的一只
- **展示**: 分「宽基/商品/债」与「行业/概念」两组，各自按距下轨由近到远取前 10
- **用途**: 危机模式，寻找反弹机会

#### 历史超跌回溯（近 3 年）
- **规则**: T 日盘中最低价 ≤ 下轨即视为买入，成交价 = min(当日开盘价, 下轨)
- **结果**: 统计 T+1 ~ T+3 盘中最高价的最大浮盈，以及它出现在 +1 / +2 / +3 哪一日
- **计数**: 连续触轨按不同交易日分别计入（不做合并），同一波下跌会出现多笔重叠买入
- **口径**: 前复权日线的 high/low 近似盘中；停牌日（low ≤ 0）不计
- **范围**: 只对前端展示的 20 只（两组各前 10）计算，结果缓存 30 分钟

## 开发命令

```bash
# 安装前端依赖
pnpm install

# 启动前端开发服务器（端口5000）
pnpm dev

# 启动后端服务（端口3000）
cd server && pnpm install && pnpm start

# 单独运行超跌策略
cd backend && python3 scripts/calculate_oversold_strategy.py [--quiet]
```

## 超跌策略缓存机制

### 缓存文件
| 文件 | 用途 | 缓存策略 |
|------|------|---------|
| `volume_cache.json` | ETF成交额缓存 | 带 `_date` 标记，跨天自动刷新 |
| `kline_cache.json` | K线数据缓存 | 带 `_date` 标记，跨天自动刷新 |
| `oversold_backtest_cache.json` | 近 3 年超跌回溯结果 | 30 分钟 TTL，7 天未出现自动清理 |

### 判定逻辑
```
load_kline_cache() → 检查 _date == today:
  ├─ 是 → 直接使用缓存，_kline_cache 内存已满
  └─ 否 → 清空，在 get_etf_volume 中重新获取
```

### 数据流
1. `filter_by_volume` → 成交额缓存命中 → 跳过 `get_etf_volume`
2. `_kline_cache` 由 `load_kline_cache()` 预填充（今日缓存）或 `get_etf_volume` 动态填充
3. `calculate_oversold_analysis` → `get_historical_data` → 优先查 `_kline_cache`（内存）→ `history_cache.json` → Sina API
4. MA10 动态调整：K线含今天→直接10日均线；不含→追加 `get_realtime_price` 实时价

### 性能
- 有缓存：~0.7s（53只ETF）
- 无缓存：~15-20s（123次Sina API请求）
- 并行度：ThreadPoolExecutor(20)

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
