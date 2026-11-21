import { NextResponse } from 'next/server';

// API 基础 URL - 从环境变量读取，移除尾随斜杠；未配置时回退到本地后端
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3000').replace(/\/+$/, '');

// 后端字段是 snake_case，这里统一转成前端的 camelCase
function mapEtf(etf: any) {
  const bt = etf.bt;
  return {
    code: etf.code,
    name: etf.name,
    currentPrice: etf.current_price,
    todayChange: etf.today_pct,
    ma10: etf.ma10,
    lowerBand: etf.lower_band,
    distanceToLower: etf.dist_to_lower,
    avgMoney: etf.avg_money || 0,
    // 近 2 年超跌回溯：T 日碰下轨买入 → T+1~T+3 盘中最大收益
    bt: bt
      ? {
          years: bt.years ?? 2,
          count: bt.count ?? 0,
          winRate: bt.win_rate ?? null,
          avgMax: bt.avg_max ?? null,
          medianMax: bt.median_max ?? null,
          bestMax: bt.best_max ?? null,
          worstMax: bt.worst_max ?? null,
          byDay: (bt.by_day || []).map((d: any) => ({
            day: d.day,
            count: d.count,
            avg: d.avg,
          })),
          recent: (bt.recent || []).map((t: any) => ({
            date: t.date,
            buy: t.buy,
            maxRet: t.max_ret,
            day: t.day,
            maxDate: t.max_date,
          })),
        }
      : null,
  };
}

export async function GET() {
  try {
    // 调用 FastAPI 后端服务
    const response = await fetch(`${API_BASE_URL}/api/strategy/oversold`, {
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error('获取超跌策略失败');
    }

    const result = await response.json();

    const etfs = (result.data?.etfs || []).map(mapEtf);
    // 宽基 / 商品 / 债券 与 行业 / 概念 各自独立排好序，各前 10
    const broad = (result.data?.broad || []).map(mapEtf);
    const sector = (result.data?.sector || []).map(mapEtf);

    const summary = result.data?.summary;

    return NextResponse.json({
      code: 200,
      data: {
        etfs,
        broad,
        sector,
        recommend: etfs.slice(0, 3).map((e: any) => e.name),
        timestamp: new Date().toISOString(),
        dataSource: '真实数据',
        summary:
          summary && typeof summary === 'object'
            ? summary
            : {
                total: etfs.length,
                analyzed: etfs.length,
                broadTotal: broad.length,
                sectorTotal: sector.length,
              },
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
