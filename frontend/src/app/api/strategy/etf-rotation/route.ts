import { NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3000';

function formatDate(date: string): string {
  const d = new Date(date);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export async function GET() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/strategy/etf-rotation`, {
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error(`后端返回 ${response.status}`);
    }

    const pythonResult = await response.json();

    if (pythonResult.code !== 200) {
      throw new Error(pythonResult.message || '策略计算失败');
    }

    // 转换字段命名规范（snake_case → camelCase）
    const etfs = (pythonResult.data.etfs || []).map((etf: any) => ({
      code: etf.code,
      name: etf.name,
      score: etf.score ?? 0,
      estimatedScore: etf.estimated_score ?? 0,
      rSquared: etf.r_squared ?? 0,
      annualReturn: etf.ann_return ?? 0,
      price: etf.price ?? 0,
      todayChange: etf.today_pct ?? 0,
      status: etf.status || '未知',
      ma10: etf.ma10 ?? null,
      ma20: etf.ma20 ?? null,
      belowMa10: etf.below_ma10 ?? false,
      belowMa20: etf.below_ma20 ?? false,
      eneUpper: etf.ene_upper ?? null,
      eneLower: etf.ene_lower ?? null,
      eneDistUpper: etf.ene_dist_upper ?? null,
      eneDistLower: etf.ene_dist_lower ?? null,
      eneWarnUpper: etf.ene_warn_upper ?? false,
      eneWarnLower: etf.ene_warn_lower ?? false,
      atr20: etf.atr20 ?? null,
      fiveDayHigh: etf.five_day_high ?? null,
      atrTwoSupport: etf.atr_two_support ?? null,
      atrDistance: etf.atr_distance ?? null,
      atrAlarm: etf.atr_alarm ?? false,
      dailyHistory: etf.daily_history || [],
    }));

    // 推荐标的（返回完整对象包含预估得分）
    const recommendData = pythonResult.data.recommend;

    return NextResponse.json({
      code: 200,
      message: 'success',
      data: {
        etfs,
        recommend: pythonResult.data.recommend || [],
        recommendCode: pythonResult.data.recommend_code || null,
        timestamp: new Date().toISOString(),
        dataSource: '快照数据',
        summary: {
          total: pythonResult.data.summary?.total || 0,
          recommended: pythonResult.data.summary?.valid || 0,
          topPick: recommendData?.name || '',
        },
      },
    });
  } catch (error: any) {
    console.error('ETF策略接口错误:', error);
    return NextResponse.json(
      { code: 500, message: error.message || '获取策略失败', data: null },
      { status: 500 }
    );
  }
}