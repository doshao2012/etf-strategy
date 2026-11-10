import { NextResponse } from 'next/server';
import { gzipSync } from 'node:zlib';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3000';

export async function GET(request: Request) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/strategy/cyb-dividend`, {
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error(`后端返回 ${response.status}`);
    }

    const data = await response.json();

    if (data.code !== 200) {
      throw new Error(data.message || '策略计算失败');
    }

    const headers: Record<string, string> = {};
    const serverCost = response.headers.get('X-Server-Cost');
    if (serverCost) headers['X-Server-Cost'] = serverCost;

    // 这个接口的响应体是全局最大的一个：瘦身后仍有 ~250KB（十年日频点位）。
    // 云服务器公网出口只有 1~5Mbps，明文要传 3~4 秒，页面看起来就像卡住了。
    // 后端虽然也开了 gzip，但 Next 这一跳的 fetch 会自动解压再转发，等于白做
    // —— 压缩必须发生在离浏览器最近的一层才有意义。
    const json = JSON.stringify({ code: 200, message: 'success', data: data.data });
    const acceptEncoding = request.headers.get('accept-encoding') || '';

    if (acceptEncoding.includes('gzip') && json.length > 1024) {
      const gz = gzipSync(Buffer.from(json, 'utf8'), { level: 6 });
      return new Response(gz as unknown as BodyInit, {
        status: 200,
        headers: {
          'content-type': 'application/json; charset=utf-8',
          'content-encoding': 'gzip',
          'vary': 'Accept-Encoding',
          'cache-control': 'no-store',
          ...headers,
        },
      });
    }

    return new Response(json, {
      status: 200,
      headers: {
        'content-type': 'application/json; charset=utf-8',
        'cache-control': 'no-store',
        ...headers,
      },
    });
  } catch (error: any) {
    console.error('创业红利轮动策略接口错误:', error);
    return NextResponse.json(
      { code: 500, message: error.message || '获取策略失败', data: null },
      { status: 500 }
    );
  }
}
