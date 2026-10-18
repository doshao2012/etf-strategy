import { NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3000';

export async function GET() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/strategy/ma200-trend`, {
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error(`后端返回 ${response.status}`);
    }

    const data = await response.json();

    if (data.code !== 200) {
      throw new Error(data.message || '策略计算失败');
    }

    return NextResponse.json({
      code: 200,
      message: 'success',
      data: data.data,
    });
  } catch (error: any) {
    console.error('MA200 趋势策略接口错误:', error);
    return NextResponse.json(
      { code: 500, message: error.message || '获取策略失败', data: null },
      { status: 500 }
    );
  }
}
