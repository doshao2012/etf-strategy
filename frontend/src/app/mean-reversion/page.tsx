'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { RefreshCw, ArrowLeft, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MeanReversionETF {
  code: string;
  name: string;
  price: number | null;
  todayChange: number | null;
  ma90: number | null;
  ma250: number | null;
  ratioMa90: number | null;
  ratioMa250: number | null;
  signal: string;
  signalLevel: string;
  dataCount: number;
}

interface StrategyResponse {
  code: number;
  data: {
    etfs: MeanReversionETF[];
    timestamp: string;
    summary: {
      total: number;
      strongBuy: number;
      suggestBuy: number;
      strongSell: number;
      suggestSell: number;
      hold: number;
    };
  };
  message: string;
}

const SIGNAL_CONFIG: Record<string, { label: string; bg: string; text: string; icon: any }> = {
  '强烈买入': { label: '强烈买入', bg: 'bg-red-50 border-red-300', text: 'text-red-700', icon: TrendingUp },
  '建议买入': { label: '建议买入', bg: 'bg-orange-50 border-orange-300', text: 'text-orange-700', icon: TrendingUp },
  '强烈卖出': { label: '强烈卖出', bg: 'bg-emerald-50 border-emerald-300', text: 'text-emerald-700', icon: TrendingDown },
  '建议卖出': { label: '建议卖出', bg: 'bg-yellow-50 border-yellow-300', text: 'text-yellow-700', icon: TrendingDown },
  '观察/持有': { label: '观察/持有', bg: 'bg-slate-50 border-slate-200', text: 'text-slate-600', icon: Minus },
  '数据不足': { label: '数据不足', bg: 'bg-gray-100 border-gray-200', text: 'text-gray-500', icon: Minus },
};

function SignalBadge({ signal, level }: { signal: string; level: string }) {
  const config = SIGNAL_CONFIG[signal] || SIGNAL_CONFIG['数据不足'];
  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-semibold ${config.bg} ${config.text} border`}>
      <Icon className="w-4 h-4" />
      {config.label}
    </span>
  );
}

function RatioBar({ ratio, label, color }: { ratio: number | null; label: string; color: string }) {
  if (ratio === null) return <span className="text-slate-400">-</span>;
  // 以100%为基准，range 80%~120%
  const pct = Math.min(Math.max((ratio - 80) / 40 * 100, 5), 100);
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500 w-12 shrink-0">{label}</span>
      <div className="flex-1 bg-slate-100 rounded-full h-2.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-sm font-bold w-16 text-right ${ratio >= 112 ? 'text-red-500' : ratio <= 101 ? 'text-emerald-500' : 'text-slate-700'}`}>
        {ratio.toFixed(2)}%
      </span>
    </div>
  );
}

export default function MeanReversionPage() {
  const [data, setData] = useState<StrategyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/strategy/mean-reversion');
      const json = await res.json();
      if (json.code !== 200) {
        throw new Error(json.message || '获取数据失败');
      }
      setData(json);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const summary = data?.data?.summary;
  const etfs = data?.data?.etfs || [];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      <div className="max-w-2xl mx-auto px-4 py-6">
        {/* 顶部导航 */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <a
              href="/"
              className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              返回
            </a>
            <h1 className="text-xl font-bold text-slate-800">均值回归策略</h1>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            disabled={loading}
            className="gap-1"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>

        {/* 策略说明 */}
        <Card className="mb-4 bg-white border-slate-200">
          <CardContent className="p-4">
            <div className="text-xs text-slate-500 space-y-1">
              <p><strong className="text-slate-700">策略逻辑：</strong>价格相对MA90和MA250的倍数</p>
              <p>• <span className="text-emerald-600 font-medium">两均线均&lt;1.01倍</span> → 强烈买入</p>
              <p>• <span className="text-orange-600 font-medium">其一均线&lt;1.01倍</span> → 建议买入</p>
              <p>• <span className="text-red-600 font-medium">两均线均&gt;1.12倍</span> → 强烈卖出</p>
              <p>• <span className="text-yellow-600 font-medium">其一均线&gt;1.12倍</span> → 建议卖出</p>
              <p>• 其他 → 观察/持有</p>
            </div>
          </CardContent>
        </Card>

        {/* 错误提示 */}
        {error && (
          <Card className="mb-4 bg-red-50 border-red-200">
            <CardContent className="p-4">
              <p className="text-sm text-red-600">获取数据失败: {error}</p>
              <Button variant="outline" size="sm" onClick={fetchData} className="mt-2">
                重试
              </Button>
            </CardContent>
          </Card>
        )}

        {/* 加载骨架 */}
        {loading && !data && (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <Card key={i} className="bg-white border-slate-200">
                <CardContent className="p-4">
                  <div className="animate-pulse space-y-3">
                    <div className="h-5 bg-slate-200 rounded w-1/3" />
                    <div className="h-8 bg-slate-200 rounded w-1/2" />
                    <div className="h-4 bg-slate-200 rounded w-3/4" />
                    <div className="h-4 bg-slate-200 rounded w-2/3" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* ETF列表 */}
        {!loading && etfs.length === 0 && !error && (
          <Card className="bg-white border-slate-200">
            <CardContent className="p-8 text-center text-slate-500">
              暂无数据
            </CardContent>
          </Card>
        )}

        <div className="space-y-3">
          {etfs.map((etf) => {
            const config = SIGNAL_CONFIG[etf.signal] || SIGNAL_CONFIG['数据不足'];
            const borderColor = etf.signalLevel === 'red' ? 'border-red-300' :
              etf.signalLevel === 'orange' ? 'border-orange-300' :
              etf.signalLevel === 'green' ? 'border-emerald-300' :
              etf.signalLevel === 'yellow' ? 'border-yellow-300' : 'border-slate-200';

            return (
              <Card key={etf.code} className={`bg-white border-2 ${borderColor} shadow-sm hover:shadow-md transition-shadow`}>
                <CardContent className="p-4">
                  {/* 头部：名称、代码、信号 */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-800">{etf.name}</span>
                      <span className="text-xs text-slate-400">{etf.code}</span>
                    </div>
                    <SignalBadge signal={etf.signal} level={etf.signalLevel} />
                  </div>

                  {/* 当前价格 */}
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-2xl font-bold text-slate-800">
                      {etf.price != null ? etf.price.toFixed(3) : '-'}
                    </span>
                    {etf.todayChange != null && (
                      <span className={`text-sm font-medium ${etf.todayChange >= 0 ? 'text-red-500' : 'text-emerald-500'}`}>
                        {etf.todayChange >= 0 ? '+' : ''}{etf.todayChange}%
                      </span>
                    )}
                  </div>

                  {/* MA90 和 MA250 倍数 */}
                  <div className="space-y-2">
                    <RatioBar
                      ratio={etf.ratioMa90}
                      label="MA90"
                      color={etf.ratioMa90 != null && etf.ratioMa90 <= 101 ? 'bg-emerald-400' :
                        etf.ratioMa90 != null && etf.ratioMa90 >= 112 ? 'bg-red-400' : 'bg-blue-400'}
                    />
                    <RatioBar
                      ratio={etf.ratioMa250}
                      label="MA250"
                      color={etf.ratioMa250 != null && etf.ratioMa250 <= 101 ? 'bg-emerald-400' :
                        etf.ratioMa250 != null && etf.ratioMa250 >= 112 ? 'bg-red-400' : 'bg-blue-400'}
                    />
                  </div>

                  {/* MA数值 */}
                  <div className="flex items-center gap-4 mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500">
                    <span>MA90: {etf.ma90 != null ? etf.ma90.toFixed(3) : '-'}</span>
                    <span>MA250: {etf.ma250 != null ? etf.ma250.toFixed(3) : '-'}</span>
                    {etf.dataCount > 0 && <span className="ml-auto">数据: {etf.dataCount}天</span>}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* 底部汇总 */}
        {summary && (
          <div className="mt-4 p-3 bg-white rounded-lg border border-slate-200 text-xs text-slate-500 flex items-center justify-between">
            <span>共 {summary.total || 0} 只标的</span>
            <div className="flex items-center gap-3">
              {summary.strongBuy > 0 && <span className="text-red-600 font-medium">强烈买入 {summary.strongBuy}</span>}
              {summary.suggestBuy > 0 && <span className="text-orange-600 font-medium">建议买入 {summary.suggestBuy}</span>}
              {summary.hold > 0 && <span className="text-slate-500">持有 {summary.hold}</span>}
              {summary.suggestSell > 0 && <span className="text-yellow-600 font-medium">建议卖出 {summary.suggestSell}</span>}
              {summary.strongSell > 0 && <span className="text-emerald-600 font-medium">强烈卖出 {summary.strongSell}</span>}
            </div>
            <span>{data?.data?.timestamp?.slice(5, 16) || ''}</span>
          </div>
        )}
      </div>
    </div>
  );
}