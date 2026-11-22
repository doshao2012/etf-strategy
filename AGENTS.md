# 策略金库

## 项目概述

多策略信号台，按日给出 A股 / 美股 / 资金面 的可执行信号。目前包含六个策略：

| 策略 | 标的 | 方法论 |
|------|------|--------|
| 趋势轮动 | A股 ETF | 25 日动量 + R² 稳定性加权 |
| 均值回归 | A股 ETF | 偏离均值后的回归 |
| 超跌策略 | A股 ETF | ENE 下轨触轨反弹 |
| 美股MA200趋势 | 美股 ETF | 长期均线定方向 |
| 市场情绪 | A股大盘 / 股债 | 择时指标（含股债收益差分位） |
| 国家队监控 | A股 ETF | 资金面（净申购、放量） |

## 技术栈

- **前端**: Next.js 16 (App Router) + shadcn/ui + Tailwind CSS 4，API 走 `app/api/strategy/*` 代理层
- **后端**: Python FastAPI（`backend/main.py`），策略实现在 `backend/scripts/*.py`，由常驻 worker 池调度
- **数据**: 腾讯 / 东方财富实时行情接口，落盘缓存于 `DATA_DIR`
- **部署**: Docker Compose + systemd timer 自动部署（见 `scripts/autodeploy.sh`）

## 目录结构

```
.
├── frontend/                  # Next.js 前端
│   └── src/
│       ├── app/
│       │   ├── layout.tsx     # 根布局（站点标题/描述在这里改）
│       │   ├── page.tsx       # 全部策略的单页视图
│       │   └── api/strategy/  # 各策略代理层（snake_case → camelCase）
│       └── lib/api.ts         # 前端类型与请求封装
├── backend/
│   ├── main.py                # FastAPI 入口、脚本调度、响应瘦身
│   └── scripts/               # 各策略计算脚本 + worker_pool.py
├── scripts/autodeploy.sh      # 自动部署与回滚
└── docs/                      # 部署、性能排查记录
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/strategy/etf-rotation` | GET | 趋势轮动策略 |
| `/api/strategy/oversold` | GET | 超跌策略（含近 3 年触轨回溯） |
| `/api/strategy/mean-reversion` | GET | 均值回归策略 |
| `/api/strategy/ma200-trend` | GET | 美股 MA200 趋势 |
| `/api/strategy/cyb-dividend` | GET | 市场情绪（股债收益差等） |
| `/api/strategy/national-team` | GET | 国家队监控 |
| `/api/health` | GET | 健康检查，回显 `DEPLOY_SHA` |

## 策略逻辑

### 趋势轮动策略
- **回看周期**: 25 个交易日
- **筛选条件**: 收益得分（年化收益）>= -0.1 且状态正常，才进建议持仓
- **候选池**: 城投债 / 纳指 / 黄金 / 创业板 / 科创50 / 科创100 / 科创200，池外只作分数参考
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
- **未满 T+3**: 最近几天才触发的也列出来（日期标红），收益只算到最新一根 K 线，
  单独用 `pending_count` 计数，不进入胜率/均值/分布统计
- **范围**: 只对前端展示的 20 只（两组各前 10）计算，结果缓存 30 分钟

## 开发命令

```bash
# 安装前端依赖
pnpm install

# 启动前端开发服务器（端口5000）
pnpm dev

# 启动后端服务（端口 3000）
cd backend && pip3 install -r requirements.txt && uvicorn main:app --port 3000

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

1. 行情来自腾讯 / 东方财富公开接口，非交易所直连，极端行情下可能有延迟或断点
2. 数据与信号仅供参考，不构成投资建议
3. 市场有风险，投资需谨慎
