// ETF Rotation API Client
// Uses relative paths - requests are proxied through the Next.js server

export interface ETFMetrics {
  code: string;
  name: string;
  score: number;
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

async function fetchAPI<T>(endpoint: string): Promise<T> {
  const res = await fetch(endpoint, {
    next: { revalidate: 60 }, // Revalidate every 60 seconds
  });
  
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }
  
  return res.json();
}

export function getETFStrategy(): Promise<StrategyResponse> {
  return fetchAPI<StrategyResponse>('/api/strategy/etf-rotation');
}

export function getOversoldStrategy(): Promise<StrategyResponse> {
  return fetchAPI<StrategyResponse>('/api/strategy/oversold');
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
  return fetchAPI<void>(`/api/etf-config/${id}`, {
    method: 'DELETE',
  });
}
