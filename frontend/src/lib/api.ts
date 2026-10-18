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
