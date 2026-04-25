import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // 强制生产模式
  poweredByHeader: false,
  // 压缩
  compress: true,
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
