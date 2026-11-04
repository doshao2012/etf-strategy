// ETF Rotation API Client
// Uses environment variable for API base URL

// API 基础 URL - 从环境变量读取，或使用相对路径
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || '').replace(/\/+$/, '');

export interface ETFMetrics {
  code: string;
  name: string;
  score: number;
  estimatedScore?: number;
  rSquared: number;
  price: number;
  todayChange: number;
  status: string;
  slope?: number;
  annualReturn?: number;
}

export interface StrategyResponse {
  code: number;
  data: {
    etfs: ETFMetrics[];
    recommend: string[];
    recommendCode: string | null;
    timestamp: string;
    dataSource: string;
    summary: {
      total: number;
      recommended?: number;
      topPick: string;
      oversoldSignals?: number;
    };
  };
  message: string;
}

// 超跌策略ETF数据
export interface OversoldETF {
  code: string;
  name: string;
  currentPrice: number;
  todayChange: number;
  ma10: number;
  lowerBand: number;
  distanceToLower: number;
  avgMoney: number;
}

export interface OversoldResponse {
  code: number;
  data: {
    etfs: OversoldETF[];
    recommend: string[];
    timestamp: string;
    dataSource: string;
    summary: string;
  };
  message: string;
}

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = API_BASE_URL ? `${API_BASE_URL}${endpoint}` : endpoint;
  const t0 = Date.now();
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    next: { revalidate: 60 },
  });
  const tHead = Date.now();
  const body = await res.json();
  const t1 = Date.now();

  // 浏览器控制台可见：一眼分清"前端请求慢"还是"后端算得慢"。
  // X-Server-Cost 由后端在每个策略接口上回传（服务端计算耗时）。
  const serverCost = res.headers.get('X-Server-Cost');
  console.log(
    `[API] ${endpoint} 总耗时 ${t1 - t0}ms (首字节 ${tHead - t0}ms, 读body ${t1 - tHead}ms)` +
    (serverCost ? ` | 后端计算 ${Number(serverCost) * 1000}ms` : ' | 后端未返回耗时头')
  );

  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }

  return body as T;
}

export function getETFStrategy(): Promise<StrategyResponse> {
  return fetchAPI<StrategyResponse>('/api/strategy/etf-rotation');
}

export function getOversoldStrategy(): Promise<OversoldResponse> {
  return fetchAPI<OversoldResponse>('/api/strategy/oversold');
}

// 均值回归策略
export interface MeanReversionETF {
  code: string;
  name: string;
  price: number;
  todayChange: number;
  ma90: number;
  ma250: number;
  ratioMa90: number;
  ratioMa250: number;
  signal: string;
  signalLevel: string;
  dataCount: number;
}

export interface MeanReversionResponse {
  code: number;
  data: {
    etfs: MeanReversionETF[];
    timestamp: string;
    summary: {
      total: number;
      strongBuy: number;
      suggestBuy: number;
      hold: number;
      suggestSell: number;
      strongSell: number;
    };
  };
  message: string;
}

export function getMeanReversionStrategy(): Promise<MeanReversionResponse> {
  return fetchAPI<MeanReversionResponse>('/api/strategy/mean-reversion');
}

// 美股 QQQ/TQQQ 三轨 MA200 策略
export interface Ma200Line {
  level: number;
  price: number;
  distancePct: number;
}

export interface Ma200StatePoint {
  day: string;
  state: number;
  position: string;
}

export interface Ma200TrendResponse {
  code: number;
  message: string;
  data: {
    symbol: {
      qqq: {
        price: number;
        changePct: number | null;
        ma200: number | null;
        ratio: number | null;
      };
      tqqq: {
        price: number | null;
        changePct: number | null;
      };
    };
    state: {
      current: number;
      currentName: string;
      previous: number;
      previousName: string;
      changed: boolean;
    };
    advice: {
      action: string;
      target: string;
      detail: string;
    };
    lines: {
      lower?: Ma200Line;
      upperExit?: Ma200Line;
      upperEntry?: Ma200Line;
    };
    params: {
      lowerLine: number;
      upperEntry: number;
      upperExit: number;
      maPeriod: number;
    };
    stateHistory: Ma200StatePoint[];
    timestamp: string;
    quoteTime: string;
    isAfterHours: boolean;
    dataSource: string;
    historyUpdated: string;
    realtimeOk: boolean;
    /** 历史日线是否已过期（距最新交易日超过 5 天） */
    historyStale?: boolean;
    /** 最新交易日距今天数 */
    historyAgeDays?: number | null;
    /** 最近一次自动同步历史日线是否成功 */
    historySyncOk?: boolean;
    /** 同步失败原因 */
    historySyncError?: string | null;
  };
}

export function getMa200TrendStrategy(): Promise<Ma200TrendResponse> {
  return fetchAPI<Ma200TrendResponse>('/api/strategy/ma200-trend');
}

// 创业红利轮动策略：创业板指 / 中证红利 比值择时
export interface CybDividendPoint {
  day: string;
  ratio: number;
  growth: number;
  dividend: number;
  state: string;
}

// 股债收益差
/** 股债收益差分档：按历史分位给曲线染色 */
export type SpreadBand = 'red' | 'yellow' | 'deepblue' | 'skyblue' | 'green';

export interface SpreadBandDef {
  /** 分位下界（含） */
  lo: number;
  /** 分位上界（不含，最后一档含 100） */
  hi: number;
  band: SpreadBand;
  /** 该档对应的贵/便宜语义，如「最便宜」 */
  meaning?: string;
}

export interface SpreadPoint {
  day: string;
  spread: number;
  ep: number;
  y10: number;
  /** 该日差值在当前窗口内的分位（0~100） */
  pct?: number | null;
  /** 分位对应的分档色 */
  band?: SpreadBand | null;
}

export interface SpreadStats {
  mean: number;
  std: number;
  plus1: number;
  minus1: number;
  max: number;
  min: number;
  current: number;
  /** 当前值在当前窗口内的分位 */
  percentile: number;
  samples?: number;
  start?: string;
  end?: string;
  band?: SpreadBand;
  /** 贵/便宜语义，如「偏便宜」 */
  bandMeaning?: string;
}

export interface SpreadPercentileThresholds {
  p10: number;
  p30: number;
  p70: number;
  p90: number;
}

/** 一个时间窗口（10年 / 5年）下的完整数据：分位、分档、统计量都按该窗口自己的样本重算 */
export interface SpreadWindow {
  years: number;
  points: SpreadPoint[];
  stats: SpreadStats;
  percentileThresholds: SpreadPercentileThresholds;
}

export interface SpreadOption {
  key: string;
  name: string;
  points: SpreadPoint[];
  /** 数据来源，如「中证指数官网」 */
  source?: string;
  /** 是否为推算值（非官方直接提供） */
  estimated?: boolean;
  /** 是否包含当日实时数据（盘中刷新 PE） */
  live?: boolean;
  /** 数据滞后交易日数，>0 时前端标注「数据滞后N日」 */
  staleDays?: number;
  /** 该标的实际最新数据日期 */
  latestDay?: string;
  /** 分档定义，前端据此渲染图例 */
  bands?: SpreadBandDef[];
  /** 多窗口数据：10年 / 5年 各自独立算分位 */
  windows?: Record<string, SpreadWindow>;
  /** 兼容字段：等同 windows['10y'] */
  percentileThresholds?: SpreadPercentileThresholds;
  stats: SpreadStats;
}

export interface SpreadData {
  definition: string;
  options: SpreadOption[];
  default: string;
  years: number;
  /** 数据源不可用时的原因（此时 options 为空） */
  error?: string;
}

export interface CybDividendResponse {
  code: number;
  message: string;
  data: {
    growth: {
      symbol: string;
      name: string;
      price: number;
      changePct: number | null;
    };
    dividend: {
      symbol: string;
      name: string;
      price: number;
      changePct: number | null;
    };
    ratio: number;
    day: string;
    state: string;
    stateYesterday: string;
    stateChanged: boolean;
    action: string;
    reason: string;
    percentile: number | null;
    lines: {
      sweepBottom: number;
      opportunity: number;
      watch: number;
      alert: number;
      escapeTop: number;
    };
    stateOrder: string[];
    distribution: Record<string, number>;
    series: CybDividendPoint[];
    params: {
      lookbackYears: number;
      points: number;
    };
    timestamp: string;
    realtimeOk: boolean;
    dataSource: string;
    spread?: SpreadData | null;
  };
}

export function getCybDividendStrategy(): Promise<CybDividendResponse> {
  return fetchAPI<CybDividendResponse>('/api/strategy/cyb-dividend');
}

// ===== 国家队监控 =====

export interface NationalTeamEtf {
  symbol: string;
  name: string;
  date: string;
  price: number | null;
  /** 昨收价 */
  prevClose: number | null;
  /** 今日涨跌幅 %（红涨绿跌） */
  changePct: number | null;
  /** 今日累计成交额（元） */
  todayAmount: number;
  /** 近5日同进度基准成交额（元） */
  baseAmount: number | null;
  /** 近20日同进度基准成交额（元） */
  baseAmountSlow: number | null;
  /** 量比（vs 近5日基准，基于成交额） */
  ratio: number | null;
  /** 量比（vs 近20日基准，参考） */
  ratioSlow: number | null;
  /** 同时刻历史分位 0~1（参考） */
  percentile: number | null;
  state: string;
  basis: string;
  lastBar: string;
  baseMode?: string;
  baseNote?: string;
  baseDays?: number;
  baseDaysSlow?: number;
  error?: string;

  /** 一级市场最新一日净申赎金额（元，正=净申购，负=净赎回）。份额 T+1 披露 */
  netAmount?: number | null;
  /** 近 5 日累计净申赎金额（元） */
  net5Amount?: number | null;
  /** 净申赎在一级市场近 60 日中的分位 0~1（0.95 = 申购强度超过历史 95% 的交易日） */
  netPercentile?: number | null;
  /** 净申赎对应的份额日期 YYYYMMDD */
  netAsOf?: string | null;
  /** 实际参与分位计算的交易日数 */
  netDays?: number | null;
  /** 数据不足时的说明（如深市需累积） */
  netNote?: string;
}

export interface NationalTeamGroup {
  index: string;
  state: string;
  avgRatio: number | null;
  alertCount: number;
  strongCount: number;
  totalCount: number;
  etfs: NationalTeamEtf[];
}

export interface NationalTeamResponse {
  code: number;
  message: string;
  data: {
    summary: {
      strongCount: number;
      alertCount: number;
      totalCount: number;
      maxRatio: number | null;
      avgRatio: number | null;
      /** 全样本合计净申赎（元，正=净申购） */
      netTotal: number | null;
      /** 全样本近 5 日累计净申赎（元） */
      netTotal5: number | null;
      netInflowCount: number;
      netOutflowCount: number;
      /** 有净申赎数据的标的数（深市可能为 0） */
      netCount: number;
    };
    groups: NationalTeamGroup[];
    thresholds: { alert: number; strong: number };
    params: {
      baseDaysFast: number;
      baseDaysSlow: number;
      minBaseDays: number;
      netPctDays: number;
      netMinDays: number;
    };
    progress: number;
    usedMinutes: number;
    inSession: boolean;
    marketStatus: string;
    quoteDate: string | null;
    /** 份额数据最新日期 YYYYMMDD */
    shareAsOf: string | null;
    /** 份额历史累积天数 */
    shareDays: number | null;
    timestamp: string;
    dataSource: string;
    costMs: number;
  };
}

export function getNationalTeam(): Promise<NationalTeamResponse> {
  return fetchAPI<NationalTeamResponse>('/api/strategy/national-team');
}

// ETF配置相关API
export interface EtfConfig {
  id: number;
  code: string;
  name: string;
  market: string;
  isActive: boolean;
}

export async function getEtfConfigs(): Promise<EtfConfig[]> {
  return fetchAPI<EtfConfig[]>('/api/etf-config');
}

export async function createEtfConfig(data: { code: string; name: string; market: string }): Promise<EtfConfig> {
  return fetchAPI<EtfConfig>('/api/etf-config', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateEtfConfig(id: number, data: { code?: string; name?: string; market?: string; isActive?: boolean }): Promise<EtfConfig> {
  return fetchAPI<EtfConfig>(`/api/etf-config/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteEtfConfig(id: number): Promise<void> {
  await fetchAPI<void>(`/api/etf-config/${id}`, {
    method: 'DELETE',
  });
}
