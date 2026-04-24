import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const scriptPath = '/workspace/projects/server/scripts/get_etf_config.py';
    const { stdout } = await execAsync(`python3 ${scriptPath} ${id}`);

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
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();

    // 调用 FastAPI 后端服务
    const response = await fetch(`http://localhost:3000/api/etf-config/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '更新失败');
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error: any) {
    console.error('更新ETF配置失败:', error);
    return NextResponse.json(
      { message: error.message || '更新ETF配置失败' },
      { status: 500 }
    );
  }
}

// DELETE - 删除ETF配置
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const scriptPath = '/workspace/projects/server/scripts/delete_etf_config.py';
    const { stdout } = await execAsync(`python3 ${scriptPath} ${id}`);

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
