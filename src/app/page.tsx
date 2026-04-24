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
import { RefreshCw, Settings, Plus, Pencil, Trash2, Shield } from 'lucide-react';

type StrategyType = 'rotation' | 'oversold';

// 趋势轮动ETF数据
interface RotationETF {
  code: string;
  name: string;
  score: number;
  estimatedScore: number;  // 预估动量得分
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

// 趋势轮动卡片 - 按参考图设计
function RotationCard({ etf, rank }: { etf: RotationETF; rank: number }) {
  const isWarning = etf.status.includes('拦截') || etf.status.includes('过低');

  return (
    <Card className={`mb-3 bg-white border ${isWarning ? 'border-red-400 bg-red-50' : 'border-slate-200'} shadow-sm hover:shadow-md transition-shadow`}>
      <CardContent className="p-4">
        {/* 顶部：序号、名称、代码、状态 */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-slate-500">#{rank}</span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-800">{etf.name}</span>
                <span className="text-xs text-slate-400">{etf.code}</span>
              </div>
            </div>
          </div>
          {etf.status === '正常' ? (
            <span className="px-2 py-0.5 text-xs font-medium bg-emerald-500 text-white rounded">
              正常
            </span>
          ) : (
            <span className="px-2 py-0.5 text-xs font-medium bg-amber-500 text-white rounded">
              {etf.status}
            </span>
          )}
        </div>

        {/* 核心指标：三个小卡片 */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          {/* 动量得分 */}
          <div className="bg-emerald-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">动量得分</p>
            <p className={`text-xl font-bold ${etf.score >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
              {etf.score.toFixed(4)}
            </p>
            <p className={`text-xs font-medium mt-1 ${(etf.estimatedScore || 0) >= 0 ? 'text-emerald-500' : 'text-red-400'}`}>
              预 {(etf.estimatedScore || 0).toFixed(4)}
            </p>
          </div>
          {/* 稳定性 R² */}
          <div className="bg-purple-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">稳定性(R²)</p>
            <p className="text-xl font-bold text-purple-600">
              {etf.rSquared.toFixed(3)}
            </p>
          </div>
          {/* 当前价格 */}
          <div className="bg-orange-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">当前价格</p>
            <p className="text-xl font-bold text-orange-500">
              {etf.price.toFixed(3)}
            </p>
          </div>
        </div>

        {/* 今日涨跌幅 */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-slate-700">今日涨跌幅</span>
          <span className={`text-base font-bold ${etf.todayChange >= 0 ? 'text-red-500' : 'text-emerald-500'}`}>
            {etf.todayChange >= 0 ? '+' : ''}{etf.todayChange}%
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

// 超跌策略卡片
function OversoldCard({ etf, rank }: { etf: OversoldETF; rank: number }) {
  const isNearLower = etf.distanceToLower < 5;

  return (
    <Card className={`mb-3 bg-white border ${isNearLower ? 'border-amber-300 shadow-md' : 'border-slate-200 shadow-sm'} hover:shadow-md transition-shadow`}>
      <CardContent className="p-4">
        {/* 顶部 */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-slate-500">#{rank}</span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-800">{etf.name}</span>
                <span className="text-xs text-slate-400">{etf.code}</span>
              </div>
            </div>
          </div>
          {isNearLower ? (
            <span className="px-2 py-0.5 text-xs font-medium bg-amber-500 text-white rounded">
              接近下轨
            </span>
          ) : (
            <span className="px-2 py-0.5 text-xs font-medium bg-slate-100 text-slate-500 rounded">
              观察中
            </span>
          )}
        </div>

        {/* 核心指标 */}
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="bg-orange-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">当前价格</p>
            <p className="text-xl font-bold text-orange-500">{etf.currentPrice.toFixed(3)}</p>
          </div>
          <div className="bg-emerald-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">ENE下轨</p>
            <p className="text-xl font-bold text-emerald-600">{etf.lowerBand.toFixed(3)}</p>
          </div>
        </div>

        {/* 辅助数据 */}
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">10日均线</p>
            <p className="text-base font-semibold text-slate-700">{etf.ma10.toFixed(3)}</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">距ENE下轨</p>
            <p className={`text-base font-semibold ${isNearLower ? 'text-amber-500' : 'text-slate-700'}`}>
              {etf.distanceToLower.toFixed(2)}%
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SkeletonCard() {
  return (
    <Card className="mb-3 bg-white border border-slate-200 shadow-sm">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Skeleton className="h-6 w-8" />
            <div>
              <Skeleton className="h-5 w-32 mb-1" />
              <Skeleton className="h-3 w-16" />
            </div>
          </div>
          <Skeleton className="h-5 w-12 rounded" />
        </div>
        <div className="grid grid-cols-3 gap-2 mb-4">
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
        </div>
        <Skeleton className="h-5 w-full rounded" />
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

  const handleDelete = async (code: string) => {
    if (!confirm('确定要删除这个ETF吗？')) return;
    setLoading(true);
    try {
      await deleteEtfConfig(code);
      onRefresh();
    } catch (err) {
      alert('删除失败');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (code: string, isActive: boolean) => {
    setLoading(true);
    try {
      await updateEtfConfig(code, { isActive });
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
            <Card key={config.code}>
              <CardContent className="p-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-semibold text-lg">{config.name}</span>
                      <span className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded dark:bg-slate-700 dark:text-slate-300">
                        {config.market.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500">代码: {config.code}</p>
                  </div>

                  <div className="flex flex-col items-end gap-2">
                    <Switch
                      checked={config.isActive}
                      onCheckedChange={(checked) => handleToggle(config.code, checked)}
                      disabled={loading}
                    />
                    <div className="flex gap-2 mt-2">
                      <Button size="sm" variant="outline" onClick={() => handleEdit(config)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleDelete(config.code)}>
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
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white border-b border-slate-200">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-800">ETF轮动策略</h1>
              <p className="text-xs text-slate-400">
                {isOversoldMode ? '超跌策略' : '趋势轮动'}
              </p>
            </div>
            
            <div className="flex items-center gap-2">
              <Select value={currentStrategy} onValueChange={(v) => setCurrentStrategy(v as StrategyType)}>
                <SelectTrigger className="w-[120px] h-9 bg-slate-100 border-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rotation">趋势轮动</SelectItem>
                  <SelectItem value="oversold">超跌策略</SelectItem>
                </SelectContent>
              </Select>

              <button
                onClick={() => setShowConfig(true)}
                className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
                title="ETF配置"
              >
                <Settings className="h-5 w-5 text-slate-500" />
              </button>

              <button
                onClick={fetchData}
                disabled={loading}
                className="p-2 rounded-lg hover:bg-slate-100 transition-colors"
                title="刷新数据"
              >
                <RefreshCw className={`h-5 w-5 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        {/* Content */}
        {loading && !currentData ? (
          <div>
            {[1, 2, 3, 4].map((i) => <SkeletonCard key={i} />)}
          </div>
        ) : error ? (
          <Card className="p-8 text-center border-slate-200">
            <p className="text-red-500 mb-4 font-medium">{error}</p>
            <Button onClick={fetchData} variant="outline">
              重新加载
            </Button>
          </Card>
        ) : (
          <>
            {/* 汇总信息 */}
            <Card className="mb-4 bg-white border border-slate-200 shadow-sm">
              <CardContent className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Shield className="w-5 h-5 text-emerald-500" />
                  <span className="text-sm font-medium text-slate-700">
                    建议持仓
                  </span>
                  <span className="text-sm font-bold text-emerald-600">
                    {(() => {
                      // 趋势轮动：找状态正常且排名第一的
                      if (!isOversoldMode && rotationData?.data.etfs) {
                        const normalEtf = rotationData.data.etfs.find((etf, idx) => 
                          idx === 0 && etf.status === '正常'
                        );
                        return normalEtf ? normalEtf.name : '空仓';
                      }
                      // 超跌策略：使用第一个推荐
                      return isOversoldMode 
                        ? (oversoldData?.data.recommend?.[0] || '空仓')
                        : '空仓';
                    })()}
                  </span>
                </div>
                <span className="text-xs text-slate-400">
                  更新时间: {lastUpdate}
                </span>
              </CardContent>
            </Card>

            {/* ETF 列表 */}
            <div>
              <h2 className="text-sm font-medium text-slate-500 mb-3">
                {isOversoldMode 
                  ? `ENE下轨标的 (${oversoldData?.data.etfs.length || 0})` 
                  : `趋势排名 (${rotationData?.data.etfs.length || 0})`}
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
        <div className="mt-8 text-center text-xs text-slate-400">
          <p>数据仅供参考，不构成投资建议</p>
          <p className="mt-1">市场有风险，投资需谨慎</p>
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
