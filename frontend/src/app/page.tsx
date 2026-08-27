'use client';

import { useState, useEffect } from 'react';
import { getETFStrategy, getOversoldStrategy, getMeanReversionStrategy, getEtfConfigs, updateEtfConfig, createEtfConfig, deleteEtfConfig, type EtfConfig, type MeanReversionETF, type MeanReversionResponse } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { RefreshCw, Settings, Plus, Pencil, Trash2, Shield } from 'lucide-react';

type StrategyType = 'rotation' | 'oversold' | 'meanReversion';

// 趋势轮动ETF数据
interface DailySnapshot {
  day: string;
  price: number;
  change: number;
  score: number;
  rSquared: number;
  annualReturn: number;
}

interface RotationETF {
  code: string;
  name: string;
  score: number;
  estimatedScore: number;  // 预估动量得分
  rSquared: number;
  annualReturn: number;     // 年化收益率（收益得分）
  price: number;
  todayChange: number;
  status: string;
  ma10: number | null;
  ma20: number | null;
  belowMa10: boolean;
  belowMa20: boolean;
  eneUpper: number | null;
  eneLower: number | null;
  eneDistUpper: number | null;
  eneDistLower: number | null;
  eneWarnUpper: boolean;
  eneWarnLower: boolean;
  atr20: number | null;
  fiveDayHigh: number | null;
  atrTwoSupport: number | null;
  atrDistance: number | null;
  atrAlarm: boolean;
  dailyHistory: DailySnapshot[];
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
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  // 操作标签：清仓 > 减仓 > 加仓（优先级）
  const actionTag = etf.belowMa20 || etf.atrAlarm ? '清仓' : etf.belowMa10 || etf.eneWarnUpper ? '减仓' : etf.eneWarnLower ? '加仓' : null;
  const actionTagColor = actionTag === '清仓' ? 'bg-red-500' : actionTag === '减仓' ? 'bg-amber-500' : 'bg-emerald-500';

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
          <div className="flex items-center gap-1.5">
            {actionTag && (
              <span className={`px-2 py-0.5 text-xs font-medium ${actionTagColor} text-white rounded`}>
                {actionTag}
              </span>
            )}
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
        </div>

        {/* 日期切换：最近10个交易日 */}
        {etf.dailyHistory && etf.dailyHistory.length > 0 && (
          <div className="mb-3">
            <div className="flex items-center gap-1 overflow-x-auto pb-1">
              {etf.dailyHistory.map((d, i) => (
                <button
                  key={d.day}
                  onClick={() => setSelectedDay(selectedDay === i ? null : i)}
                  className={`px-2 py-1 text-xs rounded whitespace-nowrap shrink-0 transition-colors ${
                    selectedDay === i
                      ? 'bg-blue-500 text-white'
                      : i === 0
                      ? 'bg-blue-100 text-blue-700 font-medium'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {d.day.slice(5)}
                </button>
              ))}
            </div>
            {selectedDay !== null && (
              <div className="mt-2 p-2 bg-blue-50 rounded border border-blue-200 text-xs">
                <div className="flex items-center gap-3 mb-1.5">
                  <span className="font-medium text-blue-800">{etf.dailyHistory[selectedDay].day} 快照</span>
                  <span className="text-blue-600">价: {etf.dailyHistory[selectedDay].price.toFixed(3)}</span>
                  <button onClick={() => setSelectedDay(null)} className="ml-auto text-blue-500 hover:text-blue-700">返回当前</button>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div><span className="text-slate-500">得分</span> <span className="font-medium">{(etf.dailyHistory[selectedDay].score ?? 0).toFixed(4)}</span></div>
                  <div><span className="text-slate-500">R²</span> <span className="font-medium">{(etf.dailyHistory[selectedDay].rSquared ?? 0).toFixed(3)}</span></div>
                  <div><span className="text-slate-500">收益</span> <span className="font-medium">{(etf.dailyHistory[selectedDay].annualReturn ?? 0).toFixed(4)}</span></div>
                  <div><span className="text-slate-500">涨跌幅</span> <span className={`font-medium ${(etf.dailyHistory[selectedDay].change ?? 0) >= 0 ? 'text-red-500' : 'text-emerald-500'}`}>{etf.dailyHistory[selectedDay].change > 0 ? '+' : ''}{(etf.dailyHistory[selectedDay].change ?? 0).toFixed(2)}%</span></div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 核心指标：四个小卡片 */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
          {/* 动量得分 */}
          <div className="bg-emerald-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">动量得分</p>
            <p className={`text-xl font-bold ${(etf.score ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
              {(etf.score ?? 0).toFixed(4)}
            </p>
            <p className={`text-xs font-medium mt-1 ${(etf.estimatedScore ?? 0) >= 0 ? 'text-emerald-500' : 'text-red-400'}`}>
              预 {((etf.estimatedScore) ?? etf.score ?? 0).toFixed(4)}
            </p>
          </div>
          {/* 收益得分（年化收益率） */}
          <div className="bg-blue-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">收益得分</p>
            <p className={`text-xl font-bold ${(etf.annualReturn ?? 0) >= 0 ? 'text-blue-600' : 'text-red-500'}`}>
              {(etf.annualReturn ?? 0).toFixed(4)}
            </p>
            <p className="text-xs text-slate-400 mt-1">R²=1</p>
          </div>
          {/* 稳定性 R² */}
          <div className="bg-purple-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">稳定性(R²)</p>
            <p className="text-xl font-bold text-purple-600">
              {(etf.rSquared ?? 0).toFixed(3)}
            </p>
          </div>
          {/* 当前价格 */}
          <div className="bg-orange-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">当前价格</p>
            <p className="text-xl font-bold text-orange-500">
              {(etf.price ?? 0).toFixed(3)}
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

        {/* 均线 */}
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100">
          <div className="flex items-center gap-3 text-xs">
            <span className="text-slate-500">MA10</span>
            <span className={`font-semibold ${etf.belowMa10 ? 'text-red-500' : 'text-slate-700'}`}>
              {etf.ma10 != null ? etf.ma10.toFixed(3) : '-'}
            </span>
            {etf.belowMa10 && <span className="text-red-400">⚠️ 低于MA10</span>}
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="text-slate-500">MA20</span>
            <span className={`font-semibold ${etf.belowMa20 ? 'text-red-500' : 'text-slate-700'}`}>
              {etf.ma20 != null ? etf.ma20.toFixed(3) : '-'}
            </span>
            {etf.belowMa20 && <span className="text-red-400">⚠️ 低于MA20</span>}
          </div>
        </div>

        {/* ENE 轨道 */}
        <div className="mt-2 pt-2 border-t border-slate-100">
          <div className="grid grid-cols-2 gap-2">
            <div className={`rounded-lg p-2 text-center ${etf.eneWarnUpper ? 'bg-red-50 ring-1 ring-red-300' : 'bg-slate-50'}`}>
              <p className="text-xs text-slate-500 mb-1">ENE上轨</p>
              <p className="text-base font-bold text-red-500">
                {etf.eneUpper != null ? etf.eneUpper.toFixed(3) : '-'}
              </p>
              {etf.eneDistUpper != null && (
                <p className={`text-xs font-medium mt-0.5 ${etf.eneWarnUpper ? 'text-red-500' : 'text-slate-400'}`}>
                  距上轨 {etf.eneDistUpper > 0 ? '+' : ''}{etf.eneDistUpper}%
                  {etf.eneWarnUpper && ' ⚠️触轨'}
                </p>
              )}
            </div>
            <div className={`rounded-lg p-2 text-center ${etf.eneWarnLower ? 'bg-emerald-50 ring-1 ring-emerald-300' : 'bg-slate-50'}`}>
              <p className="text-xs text-slate-500 mb-1">ENE下轨</p>
              <p className="text-base font-bold text-emerald-600">
                {etf.eneLower != null ? etf.eneLower.toFixed(3) : '-'}
              </p>
              {etf.eneDistLower != null && (
                <p className={`text-xs font-medium mt-0.5 ${etf.eneWarnLower ? 'text-emerald-600' : 'text-slate-400'}`}>
                  距下轨 {etf.eneDistLower > 0 ? '+' : ''}{etf.eneDistLower}%
                  {etf.eneWarnLower && ' 💎超跌'}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* ATR 风控 */}
        {etf.atr20 !== null && (
          <div className="border-t border-slate-100 pt-2 mt-2">
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg bg-slate-50 p-2 text-center">
                <p className="text-xs text-slate-500 mb-1">ATR20</p>
                <p className="text-sm font-semibold text-slate-700">{etf.atr20.toFixed(4)}</p>
              </div>
              <div className="rounded-lg bg-slate-50 p-2 text-center">
                <p className="text-xs text-slate-500 mb-1">5日最高</p>
                <p className="text-sm font-semibold text-slate-700">{etf.fiveDayHigh?.toFixed(3)}</p>
              </div>
              <div className={`rounded-lg p-2 text-center ${etf.atrAlarm ? 'bg-red-50 ring-1 ring-red-300' : 'bg-slate-50'}`}>
                <p className="text-xs text-slate-500 mb-1">2倍ATR支撑</p>
                <p className="text-sm font-semibold text-slate-700">{etf.atrTwoSupport?.toFixed(3)}</p>
                {etf.atrDistance !== null && (
                  <p className={`text-xs font-medium mt-0.5 ${etf.atrAlarm ? 'text-red-600' : 'text-emerald-600'}`}>
                    {etf.atrAlarm ? '⚠️ 已跌破' : '↗ 支撑上'}{' '}
                    <span className={etf.atrAlarm ? 'text-red-500' : 'text-emerald-500'}>
                      {etf.atrDistance >= 0 ? '+' : ''}{etf.atrDistance.toFixed(2)}%
                    </span>
                  </p>
                )}
              </div>
            </div>
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
            <p className="text-xl font-bold text-orange-500">{(etf.currentPrice ?? 0).toFixed(3)}</p>
          </div>
          <div className="bg-emerald-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">ENE下轨</p>
            <p className="text-xl font-bold text-emerald-600">{(etf.lowerBand ?? 0).toFixed(3)}</p>
          </div>
        </div>

        {/* 辅助数据 */}
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">10日均线</p>
            <p className="text-base font-semibold text-slate-700">{(etf.ma10 ?? 0).toFixed(3)}</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">距ENE下轨</p>
            <p className={`text-base font-semibold ${isNearLower ? 'text-amber-500' : 'text-slate-700'}`}>
              {(etf.distanceToLower ?? 0).toFixed(2)}%
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// 均值回归策略卡片
function MeanReversionCard({ etf, rank }: { etf: MeanReversionETF; rank: number }) {
  const signalColors: Record<string, string> = {
    'strongBuy': 'bg-green-600',
    'suggestBuy': 'bg-emerald-500',
    'hold': 'bg-slate-400',
    'suggestSell': 'bg-red-500',
    'strongSell': 'bg-red-700',
  };
  const signalIcons: Record<string, string> = {
    strongBuy: '⬆',
    suggestBuy: '↑',
    hold: '—',
    suggestSell: '↓',
    strongSell: '⬇',
  };

  const ratioBarColor = (ratio: number) => {
    if (ratio < 101) return 'bg-emerald-500';
    if (ratio > 112) return 'bg-red-500';
    return 'bg-blue-500';
  };

  return (
    <Card className="mb-3 bg-white border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        {/* 顶部：名称、代码、信号 */}
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
          <span className={`px-2 py-0.5 text-xs font-medium ${signalColors[etf.signalLevel] || 'bg-slate-400'} text-white rounded`}>
            {signalIcons[etf.signalLevel] || ''} {etf.signal}
          </span>
        </div>

        {/* 价格 */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-slate-500">当前价格</span>
          <span className="text-xl font-bold text-slate-800">{(etf.price ?? 0).toFixed(3)}</span>
        </div>

        {/* MA90 倍数 */}
        {etf.ma90 != null && etf.ratioMa90 != null ? (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-slate-500">MA90 = {etf.ma90.toFixed(3)}</span>
            <span className={`text-sm font-bold ${etf.ratioMa90 >= 101 ? 'text-red-500' : 'text-emerald-500'}`}>
              {etf.ratioMa90.toFixed(2)}%
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2.5">
            <div
              className={`h-2.5 rounded-full ${ratioBarColor(etf.ratioMa90)}`}
              style={{ width: `${Math.min(etf.ratioMa90 / 1.2, 100)}%` }}
            />
          </div>
        </div>
        ) : (
          <div className="mb-3 text-sm text-slate-400">MA90: 数据不足</div>
        )}

        {/* MA250 倍数 */}
        {etf.ma250 != null && etf.ratioMa250 != null ? (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-slate-500">MA250 = {etf.ma250.toFixed(3)}</span>
            <span className={`text-sm font-bold ${etf.ratioMa250 >= 101 ? 'text-red-500' : 'text-emerald-500'}`}>
              {etf.ratioMa250.toFixed(2)}%
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2.5">
            <div
              className={`h-2.5 rounded-full ${ratioBarColor(etf.ratioMa250)}`}
              style={{ width: `${Math.min(etf.ratioMa250 / 1.2, 100)}%` }}
            />
          </div>
        </div>
        ) : (
          <div className="mb-3 text-sm text-slate-400">MA250: 数据不足</div>
        )}

        {/* 今日涨跌幅 */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-100">
          <span className="text-sm text-slate-500">今日涨跌幅</span>
          <span className={`text-base font-bold ${(etf.todayChange ?? 0) >= 0 ? 'text-red-500' : 'text-emerald-500'}`}>
            {(etf.todayChange ?? 0) >= 0 ? '+' : ''}{etf.todayChange ?? 0}%
          </span>
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
                      <span className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded dark:bg-slate-700 dark:text-slate-300">
                        {config.market.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500">代码: {config.code}</p>
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
  const [meanReversionData, setMeanReversionData] = useState<MeanReversionResponse | null>(null);
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
      } else if (currentStrategy === 'oversold') {
        const oversold = await getOversoldStrategy();
        setOversoldData(oversold as OversoldResponse);
      } else {
        const mr = await getMeanReversionStrategy();
        setMeanReversionData(mr as MeanReversionResponse);
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
  const isMeanReversionMode = currentStrategy === 'meanReversion';
  const currentData = isMeanReversionMode ? meanReversionData : (isOversoldMode ? oversoldData : rotationData);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white border-b border-slate-200">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-800">ETF轮动策略</h1>
              <p className="text-xs text-slate-400">
                {isMeanReversionMode ? '均值回归' : isOversoldMode ? '超跌策略' : '趋势轮动'}
              </p>
            </div>
            
            <div className="flex items-center gap-2">
              <Select value={currentStrategy} onValueChange={(v) => setCurrentStrategy(v as StrategyType)}>
                <SelectTrigger className="w-[120px] h-9 bg-slate-100 border-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rotation">趋势轮动</SelectItem>
                  <SelectItem value="meanReversion">均值回归</SelectItem>
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
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  {isMeanReversionMode ? (
                    <div className="flex items-center gap-2">
                      <Shield className="w-5 h-5 text-emerald-500" />
                      <span className="text-sm font-medium text-slate-700 mr-2">
                        信号分布
                      </span>
                      {(() => {
                        const etfs = meanReversionData?.data.etfs || [];
                        const counts = { '强烈买入': 0, '建议买入': 0, '观察/持有': 0, '建议卖出': 0, '强烈卖出': 0 };
                        etfs.forEach(e => { if (e.signal in counts) (counts as Record<string, number>)[e.signal]++; });
                        return (
                          <div className="flex gap-2 text-xs">
                            {Object.entries(counts).map(([k, v]) => {
                              const colors: Record<string, string> = { '强烈买入': 'text-red-600', '建议买入': 'text-orange-500', '观察/持有': 'text-slate-500', '建议卖出': 'text-yellow-600', '强烈卖出': 'text-green-600' };
                              return <span key={k} className={`${colors[k] || 'text-slate-500'} font-medium`}>{k} {v}</span>;
                            })}
                          </div>
                        );
                      })()}
                    </div>
                  ) : (
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
                  )}
                  <span className="text-xs text-slate-400">
                    更新时间: {lastUpdate}
                  </span>
                </div>
                {/* 规则说明 */}
                {isMeanReversionMode ? (
                  <div className="bg-slate-50 rounded-lg p-3 text-xs text-slate-600 space-y-1">
                    <p className="font-medium text-slate-700 mb-1">操作规则：</p>
                    <div className="grid grid-cols-5 gap-1.5">
                      <div className="bg-red-50 rounded p-2">
                        <p className="font-medium text-red-600 text-xs">强烈买入</p>
                        <p className="text-slate-500 text-[11px] leading-relaxed">MA90和MA250<br/>均低于1.01倍</p>
                      </div>
                      <div className="bg-orange-50 rounded p-2">
                        <p className="font-medium text-orange-500 text-xs">建议买入</p>
                        <p className="text-slate-500 text-[11px] leading-relaxed">MA90或MA250<br/>低于1.01倍</p>
                      </div>
                      <div className="bg-slate-50 rounded p-2">
                        <p className="font-medium text-slate-500 text-xs">观察/持有</p>
                        <p className="text-slate-500 text-[11px] leading-relaxed">介于1.01倍<br/>至1.12倍之间</p>
                      </div>
                      <div className="bg-yellow-50 rounded p-2">
                        <p className="font-medium text-yellow-600 text-xs">建议卖出</p>
                        <p className="text-slate-500 text-[11px] leading-relaxed">MA90或MA250<br/>高于1.12倍</p>
                      </div>
                      <div className="bg-green-50 rounded p-2">
                        <p className="font-medium text-green-600 text-xs">强烈卖出</p>
                        <p className="text-slate-500 text-[11px] leading-relaxed">MA90和MA250<br/>均高于1.12倍</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="bg-slate-50 rounded-lg p-3 text-xs text-slate-600 space-y-1">
                    <p className="font-medium text-slate-700 mb-1">操作规则：</p>
                    <div className="grid grid-cols-4 gap-2">
                      <div className="bg-red-50 rounded p-2">
                        <p className="font-medium text-red-600 text-xs">清仓</p>
                        <p className="text-slate-500 text-[11px] leading-relaxed">
  当日大跌<br/>跌破20日线<br/>分数不是第一<br/>ATR止盈
</p>
                      </div>
                      <div className="bg-amber-50 rounded p-2">
                        <p className="font-medium text-amber-600 text-xs">减仓</p>
                        <p className="text-slate-500 text-[11px] leading-relaxed">
  跌破10日线<br/>ENE上限
</p>
                      </div>
                      <div className="bg-emerald-50 rounded p-2">
                        <p className="font-medium text-emerald-600 text-xs">加仓</p>
                        <p className="text-slate-500 text-[11px] leading-relaxed">
  ENE下限
</p>
                      </div>
                      <div className="bg-blue-50 rounded p-2">
                        <p className="font-medium text-blue-600 text-xs">分数上限</p>
                        <p className="text-slate-500 text-[11px] leading-relaxed">
  保守选择3<br/>按照95%上限
</p>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* ETF 列表 */}
            <div>
              <h2 className="text-sm font-medium text-slate-500 mb-3">
                {isMeanReversionMode
                  ? `均值回归 (${meanReversionData?.data.etfs.length || 0})`
                  : isOversoldMode 
                  ? `ENE下轨标的 (${oversoldData?.data.etfs.length || 0})` 
                  : `趋势排名 (${rotationData?.data.etfs.length || 0})`}
              </h2>
              
              {isMeanReversionMode ? (
                (() => {
                  const sorted = [...(meanReversionData?.data.etfs || [])].sort((a, b) => {
                    const order: Record<string, number> = { strongBuy: 0, suggestBuy: 1, hold: 2, suggestSell: 3, strongSell: 4 };
                    return (order[a.signalLevel] ?? 99) - (order[b.signalLevel] ?? 99);
                  });
                  return sorted.map((etf, index) => (
                    <MeanReversionCard key={etf.code} etf={etf} rank={index + 1} />
                  ));
                })()
              ) : isOversoldMode ? (
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
