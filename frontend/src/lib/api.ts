// ETF Rotation API Client
// Uses environment variable for API base URL

// API 基础 URL - 从环境变量读取，或使用相对路径
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || '').replace(/\/+$/, '').replace(/^http:/, 'https:');

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
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    next: { revalidate: 60 },
  });
  
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }
  
  return res.json();
}

export function getETFStrategy(): Promise<StrategyResponse> {
  return fetchAPI<StrategyResponse>('/api/strategy/etf-rotation');
}

export function getOversoldStrategy(): Promise<OversoldResponse> {
  return fetchAPI<OversoldResponse>('/api/strategy/oversold');
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
