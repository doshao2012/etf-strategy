'use client';

import { useState, useEffect } from 'react';
import { getETFStrategy, getOversoldStrategy, type ETFMetrics, type StrategyResponse } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { RefreshCw, TrendingUp, TrendingDown, AlertTriangle, Info, ChevronDown } from 'lucide-react';

type StrategyType = 'rotation' | 'oversold';

function ETFCard({ etf, rank }: { etf: ETFMetrics; rank: number }) {
  const isPositive = etf.todayChange >= 0;
  const isRecommended = rank === 1 && etf.status === '正常';
  const isWarning = etf.status.includes('拦截') || etf.status.includes('过低');
  const isOversold = etf.status === '超跌信号';

  return (
    <Card className={`mb-3 ${isRecommended ? 'border-green-500 shadow-lg' : ''} ${isWarning ? 'border-orange-300' : ''}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge variant={isRecommended ? 'default' : 'secondary'} className={isRecommended ? 'bg-green-500' : ''}>
              #{rank}
            </Badge>
            <CardTitle className="text-lg">{etf.name}</CardTitle>
            <span className="text-sm text-muted-foreground">{etf.code}</span>
          </div>
          <div className={`flex items-center gap-1 ${isPositive ? 'text-red-500' : 'text-green-500'}`}>
            {isPositive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
            <span className="font-bold">{isPositive ? '+' : ''}{etf.todayChange}%</span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-muted-foreground">动量得分</p>
            <p className={`text-2xl font-bold ${etf.score >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {etf.score.toFixed(4)}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">稳定性 R²</p>
            <p className="text-2xl font-bold">{etf.rSquared.toFixed(3)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">当前价格</p>
            <p className="text-xl font-semibold">¥{etf.price.toFixed(3)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">年化收益</p>
            <p className={`text-xl font-semibold ${(etf.annualReturn || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {((etf.annualReturn || 0) * 100).toFixed(2)}%
            </p>
          </div>
        </div>
        
        {/* Status */}
        <div className="mt-3 flex items-center gap-2">
          {isRecommended && (
            <Badge className="bg-green-500">推荐持有</Badge>
          )}
          {isOversold && (
            <Badge className="bg-orange-500">超跌信号</Badge>
          )}
          {isWarning && (
            <Badge variant="destructive">
              <AlertTriangle className="h-3 w-3 mr-1" />
              {etf.status}
            </Badge>
          )}
          {!isRecommended && !isOversold && !isWarning && (
            <Badge variant="outline">{etf.status}</Badge>
          )}
        </div>
        
        {/* Recommendation Badge */}
        {isRecommended && (
          <div className="mt-3 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
            <p className="text-sm font-medium text-green-700 dark:text-green-400">
              当前最优选择
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StrategySkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4, 5, 6, 7].map((i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-6 w-32" />
              <Skeleton className="h-6 w-20" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function ETFRotationPage() {
  const [strategyData, setStrategyData] = useState<StrategyResponse | null>(null);
  const [oversoldData, setOversoldData] = useState<StrategyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const [currentStrategy, setCurrentStrategy] = useState<StrategyType>('rotation');

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const [strategy, oversold] = await Promise.all([
        getETFStrategy(),
        getOversoldStrategy(),
      ]);
      
      setStrategyData(strategy);
      setOversoldData(oversold);
      setLastUpdate(new Date().toLocaleTimeString('zh-CN'));
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  const currentData = currentStrategy === 'rotation' ? strategyData : oversoldData;
  const isOversoldMode = currentStrategy === 'oversold';

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">ETF轮动策略</h1>
              <p className="text-sm text-muted-foreground">智能轮动 · 趋势追踪</p>
            </div>
            
            <div className="flex items-center gap-3">
              {/* Strategy Selector */}
              <Select value={currentStrategy} onValueChange={(v) => setCurrentStrategy(v as StrategyType)}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rotation">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-4 w-4" />
                      趋势轮动
                    </div>
                  </SelectItem>
                  <SelectItem value="oversold">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4" />
                      超跌策略
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>

              {/* Refresh Button */}
              <button
                onClick={fetchData}
                disabled={loading}
                className="p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <RefreshCw className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        {/* Info Banner */}
        <Card className="mb-6 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
          <CardContent className="py-3 flex items-center gap-2">
            <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
            <p className="text-sm text-blue-700 dark:text-blue-400">
              基于25日动量得分筛选，R²稳定性加权，配合3%跌幅风控拦截
            </p>
          </CardContent>
        </Card>

        {/* Content */}
        {loading && !currentData ? (
          <StrategySkeleton />
        ) : error ? (
          <Card className="p-6 text-center">
            <p className="text-red-500 mb-4">{error}</p>
            <button
              onClick={fetchData}
              className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90"
            >
              重试
            </button>
          </Card>
        ) : (
          <>
            {/* Summary Card */}
            <Card className={`mb-6 text-white ${isOversoldMode ? 'bg-gradient-to-r from-orange-500 to-amber-600' : 'bg-gradient-to-r from-green-500 to-emerald-600'}`}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm opacity-90">
                      {isOversoldMode ? '超跌信号' : '当前推荐'}
                    </p>
                    <p className="text-2xl font-bold">
                      {isOversoldMode
                        ? `${currentData?.data.summary.oversoldSignals || 0} 个`
                        : currentData?.data.summary.topPick}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm opacity-90">更新时间</p>
                    <p className="text-sm">{lastUpdate}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* ETF List */}
            <div className="space-y-3">
              {currentData?.data.etfs.map((etf, index) => (
                <ETFCard key={etf.code} etf={etf} rank={index + 1} />
              ))}
            </div>
          </>
        )}

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-muted-foreground">
          <p>数据仅供参考，不构成投资建议</p>
          <p className="mt-1">市场有风险，投资需谨慎</p>
        </div>
      </main>
    </div>
  );
}
