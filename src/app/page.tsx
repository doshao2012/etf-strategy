'use client';

import { useState, useEffect } from 'react';
import { getETFStrategy, getOversoldStrategy, getEtfConfigs, updateEtfConfig, createEtfConfig, deleteEtfConfig, type EtfConfig } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { RefreshCw, TrendingUp, TrendingDown, AlertTriangle, Info, Settings, Plus, Pencil, Trash2, Sparkles, Zap, Clock } from 'lucide-react';

type StrategyType = 'rotation' | 'oversold';

// 趋势轮动ETF数据
interface RotationETF {
  code: string;
  name: string;
  score: number;
  rSquared: number;
  price: number;
  todayChange: number;
  status: string;
}

// 超跌策略ETF数据
interface OversoldETF {
  code: string;
  name: string;
  currentPrice: number;
  ma10: number;
  lowerBand: number;
  distanceToLower: number;
  avgMoney: number;
}

interface RotationResponse {
  code: number;
  data: {
    etfs: RotationETF[];
    recommend: string[];
    recommendCode: string | null;
    timestamp: string;
    dataSource: string;
    summary: {
      total: number;
      recommended: number;
      topPick: string;
    };
  };
  message: string;
}

interface OversoldResponse {
  code: number;
  data: {
    etfs: OversoldETF[];
    recommend: string[];
    timestamp: string;
    dataSource: string;
    summary: string;
  };
  message: string;
}

// 趋势轮动卡片 - 现代化设计
function RotationCard({ etf, rank }: { etf: RotationETF; rank: number }) {
  const isPositive = etf.todayChange >= 0;
  const isRecommended = rank === 1 && etf.status === '正常';
  const isWarning = etf.status.includes('拦截') || etf.status.includes('过低');

  // 排名颜色
  const rankColors = [
    'bg-gradient-to-br from-amber-400 to-orange-500 text-white',
    'bg-gradient-to-br from-slate-300 to-slate-400 text-slate-800',
    'bg-gradient-to-br from-amber-600 to-amber-700 text-white',
  ];

  return (
    <div className={`
      relative overflow-hidden rounded-2xl transition-all duration-300 hover:scale-[1.01] hover:shadow-xl
      ${isRecommended 
        ? 'bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/30 border-2 border-emerald-200 dark:border-emerald-800' 
        : 'bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700'}
    `}>
      {/* 顶部装饰条 */}
      {isRecommended && (
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-400 via-teal-400 to-cyan-400" />
      )}

      <div className="p-4">
        {/* 头部：排名 + 名称 + 涨跌幅 */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            {/* 排名徽章 */}
            <div className={`
              w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm shadow-lg
              ${rank <= 3 ? rankColors[rank - 1] : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300'}
            `}>
              #{rank}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-lg">{etf.name}</h3>
                {isRecommended && (
                  <Sparkles className="w-4 h-4 text-emerald-500 animate-pulse" />
                )}
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">{etf.code}</p>
            </div>
          </div>

          {/* 涨跌幅 */}
          <div className={`
            flex items-center gap-1.5 px-3 py-1.5 rounded-full font-bold
            ${isPositive 
              ? 'bg-red-50 dark:bg-red-950/50 text-red-600 dark:text-red-400' 
              : 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400'}
          `}>
            {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            <span>{isPositive ? '+' : ''}{etf.todayChange}%</span>
          </div>
        </div>

        {/* 数据指标 */}
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3 text-center">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">动量得分</p>
            <p className={`text-lg font-bold ${etf.score >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
              {etf.score >= 0 ? '+' : ''}{etf.score.toFixed(3)}
            </p>
          </div>
          <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3 text-center">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">稳定性 R²</p>
            <p className="text-lg font-bold text-slate-700 dark:text-slate-200">
              {etf.rSquared.toFixed(3)}
            </p>
          </div>
          <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3 text-center">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">当前价格</p>
            <p className="text-lg font-bold text-slate-700 dark:text-slate-200">
              ¥{etf.price.toFixed(3)}
            </p>
          </div>
        </div>

        {/* 状态标签 */}
        <div className="flex items-center gap-2">
          {isRecommended ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500 text-white rounded-full text-xs font-medium">
              <Zap className="w-3 h-3" />
              当前最优选择
            </div>
          ) : isWarning ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 text-white rounded-full text-xs font-medium">
              <AlertTriangle className="w-3 h-3" />
              {etf.status}
            </div>
          ) : (
            <div className="px-3 py-1.5 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-full text-xs">
              {etf.status}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// 超跌策略卡片
function OversoldCard({ etf, rank }: { etf: OversoldETF; rank: number }) {
  const isNearLower = etf.distanceToLower < 5;

  const rankColors = [
    'bg-gradient-to-br from-amber-400 to-orange-500 text-white',
    'bg-gradient-to-br from-slate-300 to-slate-400 text-slate-800',
    'bg-gradient-to-br from-amber-600 to-amber-700 text-white',
  ];

  return (
    <div className={`
      relative overflow-hidden rounded-2xl transition-all duration-300 hover:scale-[1.01] hover:shadow-xl
      ${isNearLower 
        ? 'bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-950/30 dark:to-amber-950/30 border-2 border-orange-200 dark:border-orange-800' 
        : 'bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700'}
    `}>
      {/* 顶部装饰条 */}
      {isNearLower && (
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-orange-400 via-amber-400 to-yellow-400" />
      )}

      <div className="p-4">
        {/* 头部 */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`
              w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm shadow-lg
              ${rank <= 3 ? rankColors[rank - 1] : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300'}
            `}>
              #{rank}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-lg">{etf.name}</h3>
                {isNearLower && (
                  <AlertTriangle className="w-4 h-4 text-orange-500 animate-pulse" />
                )}
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">{etf.code}</p>
            </div>
          </div>

          {/* 距ENE下轨 */}
          <div className="text-right">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">距ENE下轨</p>
            <p className={`text-lg font-bold ${isNearLower ? 'text-orange-500' : 'text-slate-600 dark:text-slate-300'}`}>
              {etf.distanceToLower.toFixed(2)}%
            </p>
          </div>
        </div>

        {/* 数据指标 */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3">
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-slate-500 dark:text-slate-400">当前价格</span>
              <span className="text-lg font-bold text-slate-700 dark:text-slate-200">
                ¥{etf.currentPrice.toFixed(3)}
              </span>
            </div>
          </div>
          <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3">
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-slate-500 dark:text-slate-400">ENE下轨</span>
              <span className="text-lg font-bold text-emerald-600">
                ¥{etf.lowerBand.toFixed(3)}
              </span>
            </div>
          </div>
          <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3">
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-slate-500 dark:text-slate-400">10日均线</span>
              <span className="font-semibold text-slate-700 dark:text-slate-200">
                ¥{etf.ma10.toFixed(3)}
              </span>
            </div>
          </div>
          <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-3">
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-slate-500 dark:text-slate-400">日均成交</span>
              <span className="font-semibold text-slate-700 dark:text-slate-200">
                {(etf.avgMoney / 10000).toFixed(0)}万
              </span>
            </div>
          </div>
        </div>

        {/* 提示 */}
        {isNearLower && (
          <div className="flex items-center gap-2 px-3 py-2 bg-orange-100 dark:bg-orange-950/50 rounded-xl">
            <AlertTriangle className="w-4 h-4 text-orange-600 dark:text-orange-400" />
            <span className="text-sm font-medium text-orange-700 dark:text-orange-300">
              接近ENE下轨，关注反弹机会
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <Card className="mb-3 overflow-hidden">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Skeleton className="h-10 w-10 rounded-xl" />
            <div>
              <Skeleton className="h-5 w-32 mb-1" />
              <Skeleton className="h-3 w-20" />
            </div>
          </div>
          <Skeleton className="h-8 w-20 rounded-full" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-3 mb-3">
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-16 rounded-xl" />
        </div>
        <Skeleton className="h-8 w-24 rounded-full" />
      </CardContent>
    </Card>
  );
}

// ETF配置内容
function ConfigDialogContent({
  configs,
  onRefresh,
}: {
  configs: EtfConfig[];
  onRefresh: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [showDialog, setShowDialog] = useState(false);
  const [editingConfig, setEditingConfig] = useState<EtfConfig | null>(null);
  const [formData, setFormData] = useState({
    code: '',
    market: 'sz',
    name: '',
    isActive: true,
  });

  const handleAdd = () => {
    setEditingConfig(null);
    setFormData({ code: '', market: 'sz', name: '', isActive: true });
    setShowDialog(true);
  };

  const handleEdit = (config: EtfConfig) => {
    setEditingConfig(config);
    setFormData({
      code: config.code,
      market: config.market,
      name: config.name,
      isActive: config.isActive,
    });
    setShowDialog(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除这个ETF吗？')) return;
    setLoading(true);
    try {
      await deleteEtfConfig(id);
      onRefresh();
    } catch (err) {
      alert('删除失败');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (id: number, isActive: boolean) => {
    setLoading(true);
    try {
      await updateEtfConfig(id, { isActive });
      onRefresh();
    } catch (err) {
      alert('更新失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.code || !formData.name) {
      alert('请填写完整信息');
      return;
    }
    setLoading(true);
    try {
      if (editingConfig) {
        await updateEtfConfig(editingConfig.id, formData);
      } else {
        await createEtfConfig(formData);
      }
      setShowDialog(false);
      onRefresh();
    } catch (err) {
      alert(editingConfig ? '修改失败' : '添加失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="mb-4 flex justify-end">
        <Button size="sm" onClick={handleAdd}>
          <Plus className="h-4 w-4 mr-1" />
          添加ETF
        </Button>
      </div>

      {configs.length === 0 ? (
        <div className="text-center py-8 text-slate-500">暂无ETF配置</div>
      ) : (
        <div className="space-y-3">
          {configs.map((config) => (
            <Card key={config.id}>
              <CardContent className="p-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-semibold text-lg">{config.name}</span>
                      <span className="text-xs bg-blue-100 text-blue-600 px-2 py-1 rounded dark:bg-blue-900/50 dark:text-blue-300">
                        {config.market.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400">代码: {config.code}</p>
                  </div>

                  <div className="flex flex-col items-end gap-2">
                    <Switch
                      checked={config.isActive}
                      onCheckedChange={(checked) => handleToggle(config.id, checked)}
                      disabled={loading}
                    />
                    <div className="flex gap-2 mt-2">
                      <Button size="sm" variant="outline" onClick={() => handleEdit(config)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleDelete(config.id)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingConfig ? '修改ETF' : '添加ETF'}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">ETF代码</label>
              <Input
                className="mt-1"
                placeholder="例如: 159915"
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value })}
              />
            </div>

            <div>
              <label className="text-sm font-medium">交易市场</label>
              <div className="mt-1 flex gap-2">
                <Button
                  variant={formData.market === 'sz' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFormData({ ...formData, market: 'sz' })}
                >
                  深交所 (SZ)
                </Button>
                <Button
                  variant={formData.market === 'sh' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFormData({ ...formData, market: 'sh' })}
                >
                  上交所 (SH)
                </Button>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">ETF名称</label>
              <Input
                className="mt-1"
                placeholder="例如: 创业板ETF"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>

            <div>
              <label className="text-sm font-medium">状态</label>
              <div className="mt-1 flex gap-2">
                <Button
                  variant={formData.isActive ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFormData({ ...formData, isActive: true })}
                >
                  激活
                </Button>
                <Button
                  variant={!formData.isActive ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFormData({ ...formData, isActive: false })}
                >
                  停用
                </Button>
              </div>
            </div>

            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowDialog(false)}
              >
                取消
              </Button>
              <Button className="flex-1" onClick={handleSubmit} disabled={loading}>
                {editingConfig ? '保存' : '添加'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function ETFRotationPage() {
  const [rotationData, setRotationData] = useState<RotationResponse | null>(null);
  const [oversoldData, setOversoldData] = useState<OversoldResponse | null>(null);
  const [configs, setConfigs] = useState<EtfConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const [currentStrategy, setCurrentStrategy] = useState<StrategyType>('rotation');
  const [showConfig, setShowConfig] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      if (currentStrategy === 'rotation') {
        const rotation = await getETFStrategy();
        setRotationData(rotation as RotationResponse);
      } else {
        const oversold = await getOversoldStrategy();
        setOversoldData(oversold as OversoldResponse);
      }
      setLastUpdate(new Date().toLocaleTimeString('zh-CN'));
    } catch (err: any) {
      console.error('获取数据失败:', err);
      setError(err.message || '获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadConfigs = async () => {
    try {
      const data = await getEtfConfigs();
      setConfigs(data);
    } catch (err) {
      console.error('获取配置失败:', err);
    }
  };

  useEffect(() => {
    fetchData();
    loadConfigs();
  }, [currentStrategy]);

  const isOversoldMode = currentStrategy === 'oversold';
  const currentData = isOversoldMode ? oversoldData : rotationData;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-900 dark:via-slate-900 dark:to-indigo-950">
      {/* Header */}
      <header className="sticky top-0 z-20 backdrop-blur-xl bg-white/70 dark:bg-slate-900/70 border-b border-slate-200/50 dark:border-slate-700/50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Logo */}
              <div className={`
                w-10 h-10 rounded-xl flex items-center justify-center
                ${isOversoldMode 
                  ? 'bg-gradient-to-br from-orange-400 to-amber-500' 
                  : 'bg-gradient-to-br from-emerald-400 to-teal-500'}
              `}>
                {isOversoldMode ? (
                  <AlertTriangle className="w-5 h-5 text-white" />
                ) : (
                  <TrendingUp className="w-5 h-5 text-white" />
                )}
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-slate-800 to-slate-600 dark:from-white dark:to-slate-300 bg-clip-text text-transparent">
                  ETF轮动策略
                </h1>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {isOversoldMode ? '超跌反弹 · 危机模式' : '趋势追踪 · 智能轮动'}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-1">
              <Select value={currentStrategy} onValueChange={(v) => setCurrentStrategy(v as StrategyType)}>
                <SelectTrigger className="w-[110px] h-9 bg-slate-100 dark:bg-slate-800 border-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rotation">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-emerald-500" />
                      趋势轮动
                    </div>
                  </SelectItem>
                  <SelectItem value="oversold">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-orange-500" />
                      超跌策略
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>

              <button
                onClick={() => setShowConfig(true)}
                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                title="ETF配置"
              >
                <Settings className="h-5 w-5 text-slate-600 dark:text-slate-400" />
              </button>

              <button
                onClick={fetchData}
                disabled={loading}
                className={`
                  p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors
                  ${loading ? 'opacity-50' : ''}
                `}
                title="刷新数据"
              >
                <RefreshCw className={`h-5 w-5 text-slate-600 dark:text-slate-400 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        {/* 策略说明 Banner */}
        <Card className={`
          mb-6 overflow-hidden border-0 shadow-lg
          ${isOversoldMode 
            ? 'bg-gradient-to-r from-orange-500 to-amber-500' 
            : 'bg-gradient-to-r from-emerald-500 to-teal-500'}
        `}>
          <CardContent className="py-3 px-4 flex items-center justify-between">
            <div className="flex items-center gap-3 text-white">
              <Info className="h-5 w-5 opacity-90" />
              <p className="text-sm font-medium">
                {isOversoldMode 
                  ? '基于ENE布林下轨策略，寻找超跌反弹机会' 
                  : '基于25日动量得分筛选，R²稳定性加权，配合3%跌幅风控拦截'}
              </p>
            </div>
            <div className="flex items-center gap-1.5 text-white/80 text-xs">
              <Clock className="h-3 w-3" />
              <span>{lastUpdate}</span>
            </div>
          </CardContent>
        </Card>

        {/* Content */}
        {loading && !currentData ? (
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => <SkeletonCard key={i} />)}
          </div>
        ) : error ? (
          <Card className="p-8 text-center border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-100 dark:bg-red-900/50 flex items-center justify-center">
              <AlertTriangle className="w-8 h-8 text-red-500" />
            </div>
            <p className="text-red-600 dark:text-red-400 mb-4 font-medium">{error}</p>
            <Button onClick={fetchData} variant="outline" className="border-red-200 dark:border-red-800">
              重新加载
            </Button>
          </Card>
        ) : (
          <>
            {/* 汇总卡片 */}
            <Card className={`
              mb-6 text-white border-0 shadow-xl overflow-hidden
              ${isOversoldMode 
                ? 'bg-gradient-to-br from-orange-600 via-amber-600 to-orange-500' 
                : 'bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-500'}
            `}>
              {/* 装饰背景 */}
              <div className="absolute inset-0 opacity-10">
                <div className="absolute -top-24 -right-24 w-64 h-64 bg-white rounded-full blur-3xl" />
                <div className="absolute -bottom-32 -left-32 w-80 h-80 bg-white rounded-full blur-3xl" />
              </div>
              
              <CardContent className="py-6 relative">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm opacity-90 mb-1">
                      {isOversoldMode ? 'ENE下轨标的' : '当前推荐'}
                    </p>
                    <p className="text-3xl font-bold">
                      {isOversoldMode 
                        ? `${currentData?.data.etfs.length || 0} 只` 
                        : (rotationData?.data.summary.topPick || '暂无')}
                    </p>
                    {!isOversoldMode && rotationData && (
                      <p className="text-sm opacity-75 mt-1">
                        共 {rotationData.data.summary.total} 只 | 推荐 {rotationData.data.summary.recommended} 只
                      </p>
                    )}
                  </div>
                  <div className="text-right">
                    {isOversoldMode ? (
                      <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur flex items-center justify-center">
                        <AlertTriangle className="w-7 h-7" />
                      </div>
                    ) : (
                      <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur flex items-center justify-center">
                        <Sparkles className="w-7 h-7" />
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* ETF 列表 */}
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                {isOversoldMode ? (
                  <>
                    <AlertTriangle className="w-5 h-5 text-orange-500" />
                    超跌标的
                  </>
                ) : (
                  <>
                    <TrendingUp className="w-5 h-5 text-emerald-500" />
                    趋势排名
                  </>
                )}
              </h2>
              
              {isOversoldMode ? (
                (oversoldData?.data.etfs || []).map((etf, index) => (
                  <OversoldCard key={etf.code} etf={etf} rank={index + 1} />
                ))
              ) : (
                (rotationData?.data.etfs || []).map((etf, index) => (
                  <RotationCard key={etf.code} etf={etf} rank={index + 1} />
                ))
              )}
            </div>
          </>
        )}

        {/* Footer */}
        <div className="mt-10 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-100 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 text-sm">
            <span>数据仅供参考，不构成投资建议</span>
            <span className="text-slate-300 dark:text-slate-600">|</span>
            <span>市场有风险，投资需谨慎</span>
          </div>
        </div>
      </main>

      {/* 配置弹窗 */}
      <Dialog open={showConfig} onOpenChange={setShowConfig}>
        <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="w-5 h-5" />
              ETF配置管理
            </DialogTitle>
          </DialogHeader>
          <ConfigDialogContent
            configs={configs}
            onRefresh={() => {
              loadConfigs();
              fetchData();
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
