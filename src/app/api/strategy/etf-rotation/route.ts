import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

const CONFIG = {
  lookbackDays: 25,
  scoreThreshold: 0.0,
  lossLimit: 0.97,
};

export async function GET() {
  try {
    // 调用 Python 脚本计算动量得分
    const scriptPath = '/workspace/projects/server/scripts/calculate_momentum_joinquant.py';
    const { stdout } = await execAsync(
      `python3 ${scriptPath} ${CONFIG.lookbackDays} ${CONFIG.scoreThreshold} ${CONFIG.lossLimit}`
    );

    const pythonResult = JSON.parse(stdout);

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

    const recommended = validResults
      .filter((r: any) => r.score >= CONFIG.scoreThreshold && r.status === '正常')
      .map((r: any) => r.name);

    return NextResponse.json({
      code: 200,
      data: {
        etfs: validResults,
        recommend: recommended,
        recommendCode: pythonResult.data.recommend,
        timestamp: new Date().toISOString(),
        dataSource: '用户配置的真实数据（Python脚本计算）',
        summary: {
          total: pythonResult.data.summary.total,
          recommended: pythonResult.data.summary.valid,
          topPick: recommended[0] || null,
        },
      },
      message: 'success',
    });
  } catch (error: any) {
    console.error('获取ETF策略失败:', error);
    return NextResponse.json(
      { code: 500, message: error.message || '获取ETF策略失败' },
      { status: 500 }
    );
  }
}
