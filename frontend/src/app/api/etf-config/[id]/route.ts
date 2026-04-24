import { NextRequest, NextResponse } from 'next/server';

// API 基础 URL - 从环境变量读取
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';

// GET - 获取单个 ETF 配置
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const response = await fetch(`${API_BASE_URL}/api/etf-config/${id}`);
    
    if (!response.ok) {
      return NextResponse.json(
        { message: 'ETF配置不存在' },
        { status: 404 }
      );
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

// PATCH - 更新 ETF 配置
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();

    // 调用 FastAPI 后端服务
    const response = await fetch(`${API_BASE_URL}/api/etf-config/${id}`, {
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
