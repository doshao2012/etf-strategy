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
import { RefreshCw, TrendingUp, TrendingDown, AlertTriangle, Info, Settings, Plus, Pencil, Trash2 } from 'lucide-react';

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

// 趋势轮动卡片
function RotationCard({ etf, rank }: { etf: RotationETF; rank: number }) {
  const isPositive = etf.todayChange >= 0;
  const isRecommended = rank === 1 && etf.status === '正常';
  const isWarning = etf.status.includes('拦截') || etf.status.includes('过低');

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
          <div className="col-span-2">
            <p className="text-sm text-muted-foreground">当前价格</p>
            <p className="text-xl font-semibold">¥{etf.price.toFixed(3)}</p>
          </div>
        </div>
        
        <div className="mt-3 flex items-center gap-2">
          {isRecommended && (
            <Badge className="bg-green-500">推荐持有</Badge>
          )}
          {isWarning && (
            <Badge variant="destructive">
              <AlertTriangle className="h-3 w-3 mr-1" />
              {etf.status}
            </Badge>
          )}
          {!isRecommended && !isWarning && (
            <Badge variant="outline">{etf.status}</Badge>
          )}
        </div>
        
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

// 超跌策略卡片
function OversoldCard({ etf, rank }: { etf: OversoldETF; rank: number }) {
  const isNearLower = etf.distanceToLower < 5;
  
  return (
    <Card className={`mb-3 ${isNearLower ? 'border-orange-500 shadow-lg' : ''}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge variant={isNearLower ? 'default' : 'secondary'} className={isNearLower ? 'bg-orange-500' : ''}>
              #{rank}
            </Badge>
            <CardTitle className="text-lg">{etf.name}</CardTitle>
            <span className="text-sm text-muted-foreground">{etf.code}</span>
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">距ENE下轨</p>
            <p className={`text-xl font-bold ${isNearLower ? 'text-orange-500' : 'text-gray-600'}`}>
              {etf.distanceToLower.toFixed(2)}%
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-muted-foreground">当前价格</p>
            <p className="text-2xl font-bold">¥{etf.currentPrice.toFixed(3)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">ENE下轨</p>
            <p className="text-2xl font-bold text-green-600">¥{etf.lowerBand.toFixed(3)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">10日均线</p>
            <p className="text-xl font-semibold">¥{etf.ma10.toFixed(3)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">日均成交额</p>
            <p className="text-xl font-semibold">{(etf.avgMoney / 10000).toFixed(0)}万</p>
          </div>
        </div>
        
        {isNearLower && (
          <div className="mt-3 p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg border border-orange-200 dark:border-orange-800">
            <p className="text-sm font-medium text-orange-700 dark:text-orange-400 flex items-center gap-1">
              <AlertTriangle className="h-4 w-4" />
              接近ENE下轨，关注反弹机会
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SkeletonCard() {
  return (
    <Card className="mb-3">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-40" />
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
  );
}

// ETF配置内容 - 按照小程序版本样式
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
    if (!confirm('确定要删除这个ETF配置吗？')) return;
    setLoading(true);
    try {
      await deleteEtfConfig(id);
      onRefresh();
    } catch (e) {
      console.error('删除失败', e);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (id: number, isActive: boolean) => {
    setLoading(true);
    try {
      await updateEtfConfig(id, { isActive });
      onRefresh();
    } catch (e) {
      console.error('更新失败', e);
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
    } catch (e) {
      console.error('操作失败', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="p-4">
        <div className="mb-4 flex justify-between items-center">
          <h2 className="text-xl font-bold">ETF配置管理</h2>
          <Button onClick={handleAdd} size="sm">
            <Plus className="h-4 w-4 mr-1" />
            添加ETF
          </Button>
        </div>

        {configs.length === 0 ? (
          <div className="text-center py-8 text-gray-500">暂无ETF配置</div>
        ) : (
          <div className="space-y-3">
            {configs.map((config) => (
              <Card key={config.id}>
                <CardContent className="p-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="font-semibold text-lg">{config.name}</span>
                        <span className="text-xs bg-blue-100 text-blue-600 px-2 py-1 rounded">
                          {config.market.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600">代码: {config.code}</p>
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
      </div>

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
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadConfigs = async () => {
    try {
      const data = await getEtfConfigs();
      setConfigs(data);
    } catch (e) {
      console.error('加载配置失败', e);
    }
  };

  useEffect(() => {
    fetchData();
  }, [currentStrategy]);

  useEffect(() => {
    loadConfigs();
  }, []);

  const isOversoldMode = currentStrategy === 'oversold';
  const currentData = isOversoldMode ? oversoldData : rotationData;

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
            
            <div className="flex items-center gap-2">
              <Select value={currentStrategy} onValueChange={(v) => setCurrentStrategy(v as StrategyType)}>
                <SelectTrigger className="w-[120px]">
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

              <button
                onClick={() => setShowConfig(true)}
                className="p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <Settings className="h-5 w-5" />
              </button>

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
              {isOversoldMode 
                ? '基于ENE布林下轨策略，寻找超跌反弹机会' 
                : '基于25日动量得分筛选，R²稳定性加权，配合3%跌幅风控拦截'}
            </p>
          </CardContent>
        </Card>

        {/* Content */}
        {loading && !currentData ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => <SkeletonCard key={i} />)}
          </div>
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
                      {isOversoldMode ? 'ENE下轨Top10' : '当前推荐'}
                    </p>
                    <p className="text-2xl font-bold">
                      {isOversoldMode 
                        ? `${currentData?.data.etfs.length || 0} 只` 
                        : (rotationData?.data.summary.topPick || '暂无')}
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
        <div className="mt-8 text-center text-sm text-muted-foreground">
          <p>数据仅供参考，不构成投资建议</p>
          <p className="mt-1">市场有风险，投资需谨慎</p>
        </div>
      </main>

      {/* 配置弹窗 */}
      <Dialog open={showConfig} onOpenChange={setShowConfig}>
        <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>ETF配置管理</DialogTitle>
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
