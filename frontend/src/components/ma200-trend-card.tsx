'use client';

import { Card, CardContent } from '@/components/ui/card';
import { TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react';
import type { Ma200TrendResponse } from '@/lib/api';

type Data = Ma200TrendResponse['data'];

// 建议动作对应的配色
const ACTION_STYLE: Record<string, { bg: string; text: string; icon: typeof TrendingUp }> = {
  买入: { bg: 'bg-red-500', text: 'text-red-500', icon: TrendingUp },
  卖出: { bg: 'bg-emerald-600', text: 'text-emerald-600', icon: TrendingDown },
  换仓: { bg: 'bg-amber-500', text: 'text-amber-500', icon: AlertTriangle },
  持有: { bg: 'bg-blue-500', text: 'text-blue-500', icon: Minus },
  观望: { bg: 'bg-slate-500', text: 'text-slate-500', icon: Minus },
};

// 当前仓位对应配色（红涨绿跌的中国习惯）
const POSITION_STYLE: Record<number, { bg: string; label: string }> = {
  [-1]: { bg: 'bg-slate-400', label: '空仓' },
  1: { bg: 'bg-red-500', label: 'TQQQ 满仓' },
  2: { bg: 'bg-blue-500', label: 'QQQ 满仓' },
};

function pct(v: number | null | undefined) {
  if (v === null || v === undefined) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export default function Ma200TrendCard({ data }: { data: Data }) {
  const { symbol, state, advice, lines, params, stateHistory } = data;
  const ratio = symbol.qqq.ratio;
  const style = ACTION_STYLE[advice.action] || ACTION_STYLE['持有'];
  const Icon = style.icon;

  // ratio 到进度条的横向位置。区间上下界直接用后端下发的三条轨，不写死数字。
  // 左端取 min(0.95, 下轨×0.97)，右端取 max(1.18, 上轨×1.05)，避免盘外行情把指针顶出条外。
  const AXIS_LEFT = Math.min(0.95, params.lowerLine * 0.97);
  const AXIS_RIGHT = Math.max(1.18, params.upperEntry * 1.05);
  const progress = (r: number) =>
    Math.min(Math.max(((r - AXIS_LEFT) / (AXIS_RIGHT - AXIS_LEFT)) * 100, 0), 100);

  return (
    <Card className="mb-3 bg-white border border-slate-200 shadow-sm">
      <CardContent className="p-4">
        {/* 顶部：标的 + 建议动作 */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-800">QQQ / TQQQ 三轨 MA200</span>
              <span className="text-xs text-slate-400">美股</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              {data.dataSource}
              {data.quoteTime ? ` · 行情 ${data.quoteTime}` : ''}
              {data.isAfterHours ? ' · 盘后' : ''}
            </p>
          </div>
          <span className={`px-2.5 py-1 text-xs font-medium ${style.bg} text-white rounded flex items-center gap-1`}>
            <Icon className="w-3.5 h-3.5" />
            {advice.action} {advice.target}
          </span>
        </div>

        {/* 核心指标：价格 / MA200 / 比值 */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
          <div className="bg-orange-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">QQQ 价格</p>
            <p className="text-xl font-bold text-orange-500">{symbol.qqq.price.toFixed(2)}</p>
            <p className={`text-xs font-medium mt-0.5 ${(symbol.qqq.changePct ?? 0) >= 0 ? 'text-red-500' : 'text-emerald-500'}`}>
              {pct(symbol.qqq.changePct)}
            </p>
          </div>

          <div className="bg-purple-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">MA200</p>
            <p className="text-xl font-bold text-purple-600">
              {symbol.qqq.ma200 ? symbol.qqq.ma200.toFixed(2) : '-'}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">{params.maPeriod} 日</p>
          </div>

          <div className="bg-blue-50 rounded-lg p-3 text-center ring-1 ring-blue-200">
            <p className="text-xs text-slate-500 mb-1">比值 QQQ/MA200</p>
            <p className="text-xl font-bold text-blue-600">{ratio ? ratio.toFixed(4) : '-'}</p>
            <p className="text-xs text-slate-400 mt-0.5">策略唯一输入</p>
          </div>

          <div className="bg-slate-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">TQQQ 价格</p>
            <p className="text-xl font-bold text-slate-700">
              {symbol.tqqq.price ? symbol.tqqq.price.toFixed(2) : '-'}
            </p>
            <p className={`text-xs font-medium mt-0.5 ${(symbol.tqqq.changePct ?? 0) >= 0 ? 'text-red-500' : 'text-emerald-500'}`}>
              {pct(symbol.tqqq.changePct)}
            </p>
          </div>
        </div>

        {/* 操作建议 */}
        <div className={`rounded-lg p-3 mb-4 ${advice.action === '卖出' ? 'bg-emerald-50' : advice.action === '买入' ? 'bg-red-50' : advice.action === '换仓' ? 'bg-amber-50' : 'bg-blue-50'}`}>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-slate-700">当前建议</span>
            <span className={`text-sm font-bold ${style.text}`}>
              {advice.action} → {advice.target}
            </span>
            <span className="ml-auto text-xs text-slate-500">
              上一交易日：{state.previousName}
            </span>
          </div>
          <p className="text-xs text-slate-600">{advice.detail}</p>
        </div>

        {/* 三条轨道的位置 */}
        {ratio && (
          <div className="mb-4">
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-slate-500">距各条轨道</span>
              <span className="text-slate-400">比值 {ratio.toFixed(4)}</span>
            </div>

            {/* 可视化轨道条 */}
            <div className="relative h-2.5 bg-slate-100 rounded-full mb-3">
              {/* 下轨以下：清仓区（任何持仓到这里都要清空） */}
              <div className="absolute h-2.5 bg-slate-300 rounded-l-full" style={{ left: 0, width: `${progress(params.lowerLine)}%` }} />
              {/* 下轨 ~ 回落下轨：空仓者买 TQQQ；持 QQQ 者换回 TQQQ */}
              <div className="absolute h-2.5 bg-red-300" style={{ left: `${progress(params.lowerLine)}%`, width: `${progress(params.upperExit) - progress(params.lowerLine)}%` }} />
              {/* 回落下轨 ~ 上轨：滞回带，区间内不交易 */}
              <div className="absolute h-2.5 bg-amber-200" style={{ left: `${progress(params.upperExit)}%`, width: `${progress(params.upperEntry) - progress(params.upperExit)}%` }} />
              {/* 上轨以上：一律持 QQQ */}
              <div className="absolute h-2.5 bg-blue-300 rounded-r-full" style={{ left: `${progress(params.upperEntry)}%`, width: `${100 - progress(params.upperEntry)}%` }} />
              {/* 当前位置指针 */}
              <div className="absolute w-1 h-5 bg-slate-800 rounded -top-1" style={{ left: `${progress(ratio)}%` }} />
            </div>

            {/* 轨道条图例：说清楚每个色块代表什么，尤其是中间那条不是仓位而是"不动" */}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500 mb-3">
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-slate-300 rounded-sm" />{params.lowerLine} 以下 空仓</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-red-300 rounded-sm" />{params.lowerLine}~{params.upperExit} 买 TQQQ</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-amber-200 rounded-sm" />{params.upperExit}~{params.upperEntry} 滞回带 · 不动</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-blue-300 rounded-sm" />{params.upperEntry} 以上 持 QQQ</span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="bg-slate-50 rounded-lg p-2 text-center">
                <p className="text-xs text-slate-500 mb-0.5">下轨 {params.lowerLine}</p>
                <p className="text-sm font-semibold text-slate-700">{lines.lower?.price.toFixed(2)}</p>
                <p className={`text-xs font-medium ${(lines.lower?.distancePct ?? 0) >= 0 ? 'text-slate-500' : 'text-red-500'}`}>
                  距 {(lines.lower?.distancePct ?? 0) >= 0 ? '+' : ''}{lines.lower?.distancePct}%
                </p>
              </div>
              <div className="bg-blue-50 rounded-lg p-2 text-center">
                <p className="text-xs text-slate-500 mb-0.5">Q→T {params.upperExit}</p>
                <p className="text-sm font-semibold text-blue-700">{lines.upperExit?.price.toFixed(2)}</p>
                <p className={`text-xs font-medium ${(lines.upperExit?.distancePct ?? 0) >= 0 ? 'text-blue-500' : 'text-amber-600'}`}>
                  距 {(lines.upperExit?.distancePct ?? 0) >= 0 ? '+' : ''}{lines.upperExit?.distancePct}%
                </p>
              </div>
              <div className="bg-red-50 rounded-lg p-2 text-center">
                <p className="text-xs text-slate-500 mb-0.5">T→Q {params.upperEntry}</p>
                <p className="text-sm font-semibold text-red-600">{lines.upperEntry?.price.toFixed(2)}</p>
                <p className={`text-xs font-medium ${(lines.upperEntry?.distancePct ?? 0) >= 0 ? 'text-red-500' : 'text-slate-400'}`}>
                  距 {(lines.upperEntry?.distancePct ?? 0) >= 0 ? '+' : ''}{lines.upperEntry?.distancePct}%
                </p>
              </div>
            </div>

            {/* 滞回规则说明：澄清"1.06~1.14 持 QQQ"这个常见误读 */}
            <p className="text-[11px] text-slate-500 mt-2.5 leading-relaxed">
              <span className="font-medium text-amber-600">滞回带 {params.upperExit}~{params.upperEntry}</span>
              ：区间内不产生交易。持 TQQQ 的继续持 TQQQ，持 QQQ 的继续持 QQQ，空仓者在此区间会买 TQQQ。
              只有跌破 {params.lowerLine} 才清仓，涨破 {params.upperEntry} 才统一换成 QQQ。
            </p>
          </div>
        )}

        {/* 最近仓位序列 */}
        {stateHistory && stateHistory.length > 0 && (
          <div className="pt-3 border-t border-slate-100">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-slate-500">最近 60 个交易日仓位</span>
              <div className="flex items-center gap-2 text-xs">
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-red-500 rounded-sm" />TQQQ</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-blue-500 rounded-sm" />QQQ</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-slate-300 rounded-sm" />空仓</span>
              </div>
            </div>
            <div className="flex gap-0.5 h-6">
              {stateHistory.slice(-60).map((p) => (
                <div
                  key={p.day}
                  title={`${p.day} ${p.position}`}
                  className={`flex-1 rounded-sm ${p.state === 1 ? 'bg-red-500' : p.state === 2 ? 'bg-blue-500' : 'bg-slate-300'}`}
                />
              ))}
            </div>
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>{stateHistory.slice(-60)[0]?.day}</span>
              <span>{stateHistory[stateHistory.length - 1]?.day}</span>
            </div>
          </div>
        )}

        {/* 实时获取失败提示 */}
        {!data.realtimeOk && (
          <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
            实时价格获取失败，当前显示的是历史收盘价（{data.historyUpdated}）。请稍后刷新重试。
          </div>
        )}
      </CardContent>
    </Card>
  );
}
