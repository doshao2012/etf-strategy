import type { Metadata, Viewport } from 'next';
import './globals.css';

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0f172a' },
  ],
};

const SITE_NAME = '策略金库';
const SITE_DESC =
  '多策略信号台 · A股 / 美股 / 资金面：趋势轮动、均值回归、超跌反弹、美股MA200、市场情绪、国家队监控，多角度给出当前该往哪走。';

export const metadata: Metadata = {
  title: {
    default: SITE_NAME,
    template: `%s | ${SITE_NAME}`,
  },
  description: SITE_DESC,
  keywords: [
    'ETF',
    'ETF轮动',
    '动量策略',
    '均值回归',
    '超跌反弹',
    'ENE下轨',
    '美股MA200',
    '市场情绪',
    '股债收益差',
    '国家队',
    '量化策略',
  ],
  generator: SITE_NAME,
  openGraph: {
    title: SITE_NAME,
    description: SITE_DESC,
    siteName: SITE_NAME,
    locale: 'zh_CN',
    type: 'website',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`antialiased`}>
        {children}
      </body>
    </html>
  );
}
