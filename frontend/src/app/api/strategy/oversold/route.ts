import { NextResponse } from 'next/server';
import { gzipSync } from 'node:zlib';

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
    atr20: etf.atr20 ?? null,
    atr20Pct: etf.atr20_pct ?? null,
    avgMoney: etf.avg_money || 0,
    // 近 3 年超跌回溯：T 日碰下轨买入 → T+1~T+3 盘中最大收益
    bt: bt
      ? {
          years: bt.years ?? 3,
          // count 只算已走满 T+3 的，pendingCount 是还没到期的观察中记录
          count: bt.count ?? 0,
          pendingCount: bt.pending_count ?? 0,
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
          // 全部触发明细，按日期倒序；pending = 还没走满 T+3，收益只是当前值
          trades: (bt.trades || []).map((t: any) => ({
            date: t.date,
            buy: t.buy,
            maxRet: t.max_ret ?? null,
            day: t.day ?? null,
            maxDate: t.max_date ?? null,
            pending: !!t.pending,
            elapsed: t.elapsed ?? null,
          })),
        }
      : null,
  };
}

export async function GET(request: Request) {
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

    // etfs 只是给老前端的兼容字段，明细已在 broad/sector 里给过，这里不再重复传
    const etfsSlim = etfs.map((e: any) => ({ ...e, bt: null }));

    const json = JSON.stringify({
      code: 200,
      data: {
        etfs: etfsSlim,
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

    const headers: Record<string, string> = { 'cache-control': 'no-store' };
    const serverCost = response.headers.get('X-Server-Cost');
    if (serverCost) headers['X-Server-Cost'] = serverCost;

    // 20 只标的的全部触发明细后，响应会涨到几十 KB。云服务器出口只有 1~5Mbps，
    // 后端那层 gzip 会被 Next 的 fetch 自动解压掉，压缩必须放在这一跳才生效。
    const acceptEncoding = request.headers.get('accept-encoding') || '';
    if (acceptEncoding.includes('gzip') && json.length > 1024) {
      const gz = gzipSync(Buffer.from(json, 'utf8'), { level: 6 });
      return new Response(gz as unknown as BodyInit, {
        status: 200,
        headers: {
          'content-type': 'application/json; charset=utf-8',
          'content-encoding': 'gzip',
          'vary': 'Accept-Encoding',
          ...headers,
        },
      });
    }

    return new Response(json, {
      status: 200,
      headers: {
        'content-type': 'application/json; charset=utf-8',
        ...headers,
      },
    });
  } catch (error: any) {
    console.error('获取超跌策略失败:', error);
    return NextResponse.json(
      { code: 500, message: error.message || '获取超跌策略失败' },
      { status: 500 }
    );
  }
}
