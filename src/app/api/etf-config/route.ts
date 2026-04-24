import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// GET - 获取所有ETF配置
export async function GET() {
  try {
    const scriptPath = '/workspace/projects/server/scripts/get_etf_configs.py';
    const { stdout } = await execAsync(`python3 ${scriptPath}`);

    const configs = JSON.parse(stdout);
    
    // 转换为前端需要的格式，添加 id 和 isActive 字段
    const transformedConfigs = configs.map((config: any, index: number) => ({
      id: index + 1,  // 使用索引作为 id
      code: config.code,
      name: config.name,
      market: config.market,
      isActive: true,  // 默认为激活状态
    }));

    return NextResponse.json(transformedConfigs);
  } catch (error: any) {
    console.error('获取ETF配置失败:', error);
    return NextResponse.json(
      { message: '获取ETF配置失败' },
      { status: 500 }
    );
  }
}

// POST - 创建新ETF配置
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { code, name, market, isActive = true } = body;

    if (!code || !name || !market) {
      return NextResponse.json(
        { message: '缺少必要参数' },
        { status: 400 }
      );
    }

    const scriptPath = '/workspace/projects/server/scripts/add_etf_config.py';
    const { stdout } = await execAsync(
      `python3 ${scriptPath} "${code}" "${name}" "${market}" ${isActive ? 1 : 0}`
    );

    const result = JSON.parse(stdout);
    return NextResponse.json(result);
  } catch (error: any) {
    console.error('创建ETF配置失败:', error);
    return NextResponse.json(
      { message: '创建ETF配置失败' },
      { status: 500 }
    );
  }
}
