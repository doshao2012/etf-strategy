import { NextResponse } from 'next/server';

// API 基础 URL - 从环境变量读取，移除尾随斜杠
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || '').replace(/\/+$/, '').replace(/^http:/, 'https:');

export async function GET() {
  try {
    // 调用 FastAPI 后端服务
    const response = await fetch(`${API_BASE_URL}/api/strategy/etf-rotation`);
    const pythonResult = await response.json();

    if (!pythonResult.data || !pythonResult.data.etfs || pythonResult.data.etfs.length === 0) {
      return NextResponse.json(
        { code: 500, message: '未能获取ETF策略数据' },
        { status: 500 }
      );
    }

    // 转换为前端需要的格式
    const validResults = pythonResult.data.etfs.map((etf: any) => ({
      code: etf.code,
      name: etf.name,
      score: etf.score,
      estimatedScore: etf.estimated_score || etf.score,
      rSquared: etf.r_squared,
      price: etf.price,
      todayChange: etf.today_pct,
      status: etf.status,
      slope: etf.slope,
      annualReturn: etf.ann_return,
    }));

    // 推荐标的（返回完整对象包含预估得分）
    const recommendData = pythonResult.data.recommend;

    return NextResponse.json({
      code: 200,
      data: {
        etfs: validResults,
        recommend: {
          name: recommendData?.name || null,
          code: recommendData?.code || null,
          score: recommendData?.score || null,
          estimatedScore: recommendData?.estimated_score || null,
        },
        lastUpdateTime: new Date().toLocaleString('zh-CN', {
          timeZone: 'Asia/Shanghai',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }),
      },
    });
  } catch (error: any) {
    console.error('获取ETF策略失败:', error);
    return NextResponse.json(
      { code: 500, message: `获取ETF策略失败: ${error.message}` },
      { status: 500 }
    );
  }
}
