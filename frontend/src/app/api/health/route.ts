import { NextResponse } from 'next/server';

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3000').replace(/\/+$/, '');

// 健康检查必须反映「后端是否活着」，不能自己直接回 {status:'ok'}。
// 原来这里是硬编码返回 ok：前端容器还在、后端已经 500 时，80 端口的
// /api/health 照样 200，自动化部署的健康检查形同虚设。
// 现在转发到后端，顺带把线上 commit 透出来（由 scripts/autodeploy.sh 写入镜像）。
export async function GET() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(8000),
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    console.error('健康检查失败:', error?.message || error);
    return NextResponse.json(
      { status: 'degraded', backend: 'unreachable' },
      { status: 503 },
    );
  }
}
