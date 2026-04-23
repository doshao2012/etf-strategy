import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function GET() {
  try {
    const scriptPath = '/workspace/projects/server/scripts/calculate_oversold_strategy.py';
    const { stdout } = await execAsync(`python3 ${scriptPath} --quiet`);

    // 从stdout中提取JSON
    const lines = stdout.trim().split('\n').filter(line => line.trim());
    
    let jsonStr = '';
    for (let i = lines.length - 1; i >= 0; i--) {
      const line = lines[i].trim();
      if (line.startsWith('{') || line.includes('"code"')) {
        jsonStr = lines.slice(i).join('');
        break;
      }
    }

    if (!jsonStr) {
      return NextResponse.json({
        code: 200,
        data: {
          etfs: [],
          recommend: [],
          timestamp: new Date().toISOString(),
          dataSource: '真实数据',
          summary: '未找到JSON格式的输出',
        },
        message: 'success',
      });
    }

    const result = JSON.parse(jsonStr);

    if (!result || result.code !== 200) {
      return NextResponse.json({
        code: 200,
        data: {
          etfs: [],
          recommend: [],
          timestamp: new Date().toISOString(),
          dataSource: '真实数据',
          summary: result.msg || result.message || '计算失败',
        },
        message: 'success',
      });
    }

    // 转换格式
    const etfs = result.data.map((etf: any) => ({
      code: etf.code,
      name: etf.name,
      currentPrice: etf.price,
      ma10: etf.ma10,
      lowerBand: etf.ene_lower,
      distanceToLower: etf.distance_to_lower,
      avgMoney: etf.avg_money || 0,
    }));

    return NextResponse.json({
      code: 200,
      data: {
        etfs: etfs,
        recommend: etfs.slice(0, 3).map((e: any) => e.name),
        timestamp: new Date().toISOString(),
        dataSource: '真实数据',
        summary: `找到 ${etfs.length} 只接近ENE下轨的ETF`,
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
