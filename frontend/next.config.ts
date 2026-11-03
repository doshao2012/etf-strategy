import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // 强制生产模式
  poweredByHeader: false,
  // 压缩
  compress: true,
  // 本地预览：把 /api 转发到后端
  async rewrites() {
    const target = process.env.BACKEND_ORIGIN || 'http://127.0.0.1:3001';
    return [{ source: '/api/:path*', destination: `${target}/api/:path*` }];
  },
  // 允许的开发域名
  allowedDevOrigins: ['*.dev.coze.site', '*.railway.app'],
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*',
        pathname: '/**',
      },
    ],
  },
  // 生产模式优化
  experimental: {
    optimizeCss: false,
  },
};

export default nextConfig;
