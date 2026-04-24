import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// GET - 获取所有ETF配置
export async function GET() {
  try {
    // 调用 FastAPI 后端服务
    const response = await fetch('http://localhost:3000/api/etf-config');
    if (!response.ok) {
      throw new Error('获取ETF配置失败');
    }
    const data = await response.json();
    return NextResponse.json(data);
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

    const scriptPath = '/app/server/scripts/add_etf_config.py';
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
