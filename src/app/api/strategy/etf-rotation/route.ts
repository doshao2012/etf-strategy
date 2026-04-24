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
    // 先获取最新的市场数据（从腾讯API获取实时价格并更新配置文件）
    const fetchScriptPath = '/workspace/projects/server/scripts/fetch_market_data_from_db.py';
    await execAsync(`python3 ${fetchScriptPath}`);

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
        timestamp: new Date().toISOString(),
        dataSource: '用户配置的真实数据（Python脚本计算）',
        summary: {
          total: pythonResult.data.summary.total,
          recommended: pythonResult.data.summary.valid,
          topPick: recommendData?.name || null,
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
