import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ code: string }> }
) {
  try {
    const { code } = await params;
    const scriptPath = '/workspace/projects/server/scripts/get_etf_config.py';
    const { stdout } = await execAsync(`python3 ${scriptPath} "${code}"`);

    const config = JSON.parse(stdout);
    if (!config) {
      return NextResponse.json(
        { message: 'ETF配置不存在' },
        { status: 404 }
      );
    }
    return NextResponse.json(config);
  } catch (error: any) {
    console.error('获取ETF配置失败:', error);
    return NextResponse.json(
      { message: '获取ETF配置失败' },
      { status: 500 }
    );
  }
}

// PATCH - 更新ETF配置
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ code: string }> }
) {
  try {
    const { code } = await params;
    const body = await request.json();

    const scriptPath = '/workspace/projects/server/scripts/update_etf_config.py';
    const args = [
      `"${code}"`,
      body.code ? `"${body.code}"` : 'null',
      body.name ? `"${body.name}"` : 'null',
      body.market ? `"${body.market}"` : 'null',
      body.isActive !== undefined ? (body.isActive ? '1' : '0') : 'null'
    ];

    const { stdout } = await execAsync(`python3 ${scriptPath} ${args.join(' ')}`);

    const result = JSON.parse(stdout);
    return NextResponse.json(result);
  } catch (error: any) {
    console.error('更新ETF配置失败:', error);
    return NextResponse.json(
      { message: '更新ETF配置失败' },
      { status: 500 }
    );
  }
}

// DELETE - 删除ETF配置
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ code: string }> }
) {
  try {
    const { code } = await params;
    const scriptPath = '/workspace/projects/server/scripts/delete_etf_config.py';
    const { stdout } = await execAsync(`python3 ${scriptPath} "${code}"`);

    const result = JSON.parse(stdout);
    return NextResponse.json(result);
  } catch (error: any) {
    console.error('删除ETF配置失败:', error);
    return NextResponse.json(
      { message: '删除ETF配置失败' },
      { status: 500 }
    );
  }
}
