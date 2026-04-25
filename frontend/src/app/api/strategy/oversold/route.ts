import { NextResponse } from 'next/server';

// API 基础 URL - 从环境变量读取，移除尾随斜杠
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || '').replace(/\/+$/, '');

export async function GET() {
  try {
    // 调用 FastAPI 后端服务
    const response = await fetch(`${API_BASE_URL}/api/strategy/oversold`);
    
    if (!response.ok) {
      throw new Error('获取超跌策略失败');
    }
    
    const result = await response.json();

    // 转换格式
    const rawEtfs = result.data?.etfs || [];
    const etfs = rawEtfs.map((etf: any) => ({
      code: etf.code,
      name: etf.name,
      currentPrice: etf.current_price,
      ma10: etf.ma10,
      lowerBand: etf.lower_band,
      distanceToLower: etf.dist_to_lower,
      avgMoney: etf.avg_money || 0,
    }));

    return NextResponse.json({
      code: 200,
      data: {
        etfs: etfs,
        recommend: etfs.slice(0, 3).map((e: any) => e.name),
        timestamp: new Date().toISOString(),
        dataSource: '真实数据',
        summary: result.data?.summary || `找到 ${etfs.length} 只接近ENE下轨的ETF`,
      },
      message: 'success',
    });
  } catch (error: any) {
    console.error('获取超跌策略失败:', error);
    return NextResponse.json(
      { code: 500, message: error.message || '获取超跌策略失败' },
      { status: 500 }
    );
  }
}
