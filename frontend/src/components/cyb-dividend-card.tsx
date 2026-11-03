'use client';

import { useMemo, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import {
  ComposedChart, LineChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea,
} from 'recharts';
import type { CybDividendResponse, CybDividendPoint, SpreadOption } from '@/lib/api';

type Data = CybDividendResponse['data'];

// 状态配色：冷（可买）→ 热（要跑）。红涨绿跌的常规不适用于这里，
// 这里表达的是"温度"，所以用蓝→灰→红的渐变语义。
const STATE_STYLE: Record<string, { bg: string; text: string; ring: string; band: string }> = {
  抄底: { bg: 'bg-blue-600', text: 'text-blue-700', ring: 'ring-blue-300', band: 'rgba(37,99,235,0.14)' },
  机会: { bg: 'bg-sky-500', text: 'text-sky-600', ring: 'ring-sky-300', band: 'rgba(14,165,233,0.12)' },
  观察: { bg: 'bg-cyan-500', text: 'text-cyan-600', ring: 'ring-cyan-300', band: 'rgba(6,182,212,0.10)' },
  中性: { bg: 'bg-slate-500', text: 'text-slate-600', ring: 'ring-slate-300', band: 'rgba(148,163,184,0.10)' },
  警戒: { bg: 'bg-orange-500', text: 'text-orange-600', ring: 'ring-orange-300', band: 'rgba(249,115,22,0.12)' },
  逃顶: { bg: 'bg-red-600', text: 'text-red-600', ring: 'ring-red-300', band: 'rgba(220,38,38,0.14)' },
};

function pct(v: number | null | undefined) {
  if (v === null || v === undefined) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export default function CybDividendCard({ data }: { data: Data }) {
  const { growth, dividend, lines, series, stateOrder, distribution } = data;
  const style = STATE_STYLE[data.state] || STATE_STYLE['中性'];
  const spread = data.spread;

  // 曲线区间：默认近 5 年，可切 1 年 / 3 年 / 全部
  const [range, setRange] = useState<'1y' | '3y' | '5y'>('5y');
  const shown = useMemo(() => {
    const years = range === '1y' ? 1 : range === '3y' ? 3 : 5;
    if (!series.length) return series;
    const last = new Date(series[series.length - 1].day).getTime();
    const cutoff = last - years * 365 * 24 * 3600 * 1000;
    return series.filter((p) => new Date(p.day).getTime() >= cutoff);
  }, [series, range]);

  // X 轴刻度：按年显示，避免 1200 个日期挤成一团
  const yearTicks = useMemo(() => {
    const seen = new Set<string>();
    const ticks: string[] = [];
    shown.forEach((p) => {
      const y = p.day.slice(0, 4);
      if (!seen.has(y)) {
        seen.add(y);
        ticks.push(p.day);
      }
    });
    return ticks;
  }, [shown]);

  // 叠加显示：可勾选叠加创业板指 / 中证红利。
  // 两个指数与比值量级差太大（2400 vs 0.43），直接同轴画不了，
  // 统一做「区间起点归一化到 100」——顺带能直观对比三者强弱。
  const [overlay, setOverlay] = useState<{ growth: boolean; dividend: boolean }>({ growth: false, dividend: false });

  type NormPoint = CybDividendPoint & { growthIdx: number; dividendIdx: number; ratioRaw: number; ratioBase: number };

  const shownNorm = useMemo<NormPoint[]>(() => {
    if (!shown.length) return [];
    const baseG = shown[0].growth || 1;
    const baseD = shown[0].dividend || 1;
    const baseR = shown[0].ratio || 1;
    return shown.map((p) => ({
      ...p,
      // 比值保持原始量级（左轴），指数归一化到 100（右轴）
      growthIdx: Number((p.growth / baseG * 100).toFixed(2)),
      dividendIdx: Number((p.dividend / baseD * 100).toFixed(2)),
      ratioRaw: p.ratio,
      ratioBase: baseR,
    }));
  }, [shown]);

  const toggleOverlay = (key: 'growth' | 'dividend') =>
    setOverlay((o) => ({ ...o, [key]: !o[key] }));

  const hasOverlay = overlay.growth || overlay.dividend;

  // 右轴（归一化指数）范围
  const rightDomain = useMemo(() => {
    const vals: number[] = [];
    if (overlay.growth) shownNorm.forEach((p) => vals.push(p.growthIdx));
    if (overlay.dividend) shownNorm.forEach((p) => vals.push(p.dividendIdx));
    if (!vals.length) return undefined;
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const pad = Math.max((hi - lo) * 0.08, 1);
    return [Number((lo - pad).toFixed(1)), Number((hi + pad).toFixed(1))] as [number, number];
  }, [shownNorm, overlay]);

  const yDomain = useMemo(() => {
    if (!shown.length) return [0.25, 0.75] as [number, number];
    const vals = shown.map((p) => p.ratio);
    const lo = Math.min(...vals, lines.sweepBottom);
    const hi = Math.max(...vals, lines.escapeTop);
    const pad = Math.max((hi - lo) * 0.08, 0.02);
    return [Number((lo - pad).toFixed(2)), Number((hi + pad).toFixed(2))] as [number, number];
  }, [shown, lines]);

  const totalDays = Object.values(distribution).reduce((a, b) => a + b, 0);

  // ====== 股债收益差 ======
  const [spreadKey, setSpreadKey] = useState<string>(spread?.default || 'hs300');
  const spreadOption: SpreadOption | null =
    spread?.options?.find((o) => o.key === spreadKey) || spread?.options?.[0] || null;

  const spreadChart = useMemo(() => {
    if (!spreadOption) return { pts: [], ticks: [] as string[] };
    const pts = spreadOption.points.map((p) => ({ ...p }));
    const seen = new Set<string>();
    const ticks: string[] = [];
    pts.forEach((p) => {
      const y = p.day.slice(0, 4);
      if (!seen.has(y)) { seen.add(y); ticks.push(p.day); }
    });
    return { pts, ticks };
  }, [spreadOption]);

  const spreadYDomain = useMemo(() => {
    if (!spreadOption) return [0, 1] as [number, number];
    const s = spreadOption.stats;
    const vals = spreadOption.points.map((p) => p.spread).concat([s.plus1, s.minus1]);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const pad = Math.max((hi - lo) * 0.1, 0.2);
    return [Number((lo - pad).toFixed(2)), Number((hi + pad).toFixed(2))] as [number, number];
  }, [spreadOption]);

  return (
    <Card className="mb-3 bg-white border border-slate-200 shadow-sm">
      <CardContent className="p-4">
        {/* 顶部：标的 + 当前状态 */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-800">创业板指 / 中证红利</span>
              <span className="text-xs text-slate-400">A股 · 比值择时</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              {data.dataSource} · 数据截至 {data.day}
            </p>
          </div>
          <span className={`px-2.5 py-1 text-xs font-medium ${style.bg} text-white rounded flex items-center gap-1`}>
            {data.state}
          </span>
        </div>

        {/* 核心数字 */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
          <div className={`bg-blue-50 rounded-lg p-3 text-center ring-1 ${style.ring}`}>
            <p className="text-xs text-slate-500 mb-1">比值 创业板/红利</p>
            <p className={`text-2xl font-bold ${style.text}`}>{data.ratio.toFixed(4)}</p>
            <p className="text-xs text-slate-400 mt-0.5">
              近 {data.params.lookbackYears} 年分位 {data.percentile ?? '-'}%
            </p>
          </div>

          <div className="bg-slate-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">{growth.name}</p>
            <p className="text-xl font-bold text-slate-700">{growth.price.toFixed(2)}</p>
            <p className={`text-xs font-medium mt-0.5 ${(growth.changePct ?? 0) >= 0 ? 'text-red-500' : 'text-emerald-500'}`}>
              {pct(growth.changePct)}
            </p>
          </div>

          <div className="bg-slate-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">{dividend.name}</p>
            <p className="text-xl font-bold text-slate-700">{dividend.price.toFixed(2)}</p>
            <p className={`text-xs font-medium mt-0.5 ${(dividend.changePct ?? 0) >= 0 ? 'text-red-500' : 'text-emerald-500'}`}>
              {pct(dividend.changePct)}
            </p>
          </div>

          <div className="bg-slate-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">昨日状态</p>
            <p className="text-xl font-bold text-slate-600">{data.stateYesterday}</p>
            <p className="text-xs text-slate-400 mt-0.5">
              {data.stateChanged ? '今日状态有切换' : '状态未变'}
            </p>
          </div>
        </div>

        {/* 操作建议 */}
        <div className={`rounded-lg p-3 mb-4 ${data.state === '逃顶' || data.state === '警戒' ? 'bg-orange-50' : data.state === '抄底' || data.state === '机会' ? 'bg-blue-50' : 'bg-slate-50'}`}>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-slate-700">当前建议</span>
            <span className={`text-sm font-bold ${style.text}`}>{data.action}</span>
          </div>
          <p className="text-xs text-slate-600">{data.reason}</p>
        </div>

        {/* 5 年比值曲线 */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-slate-600">
              比值走势（{shown[0]?.day} ~ {shown[shown.length - 1]?.day}，{shown.length} 个交易日）
            </span>
            <div className="flex items-center gap-1">
              {/* 叠加开关 */}
              <button
                onClick={() => toggleOverlay('growth')}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${
                  overlay.growth ? 'bg-orange-500 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
                title="叠加创业板指（归一化到100，右轴）"
              >
                {overlay.growth ? '✓ ' : '+ '}创业板指
              </button>
              <button
                onClick={() => toggleOverlay('dividend')}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${
                  overlay.dividend ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
                title="叠加中证红利（归一化到100，右轴）"
              >
                {overlay.dividend ? '✓ ' : '+ '}中证红利
              </button>
              <span className="w-px h-4 bg-slate-200 mx-0.5" />
              {(['1y', '3y', '5y'] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  className={`px-2 py-0.5 text-xs rounded transition-colors ${
                    range === r ? 'bg-slate-700 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                  }`}
                >
                  {r === '1y' ? '近1年' : r === '3y' ? '近3年' : '近5年'}
                </button>
              ))}
            </div>
          </div>

          <div className="h-[300px] w-full -ml-2">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={shownNorm} margin={{ top: 6, right: hasOverlay ? 8 : 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                {/* 阈值背景带：越冷越蓝，越热越红 */}
                <ReferenceArea y1={yDomain[0]} y2={lines.sweepBottom} fill={STATE_STYLE['抄底'].band} />
                <ReferenceArea y1={lines.sweepBottom} y2={lines.opportunity} fill={STATE_STYLE['机会'].band} />
                <ReferenceArea y1={lines.opportunity} y2={lines.watch} fill={STATE_STYLE['观察'].band} />
                <ReferenceArea y1={lines.watch} y2={lines.alert} fill={STATE_STYLE['中性'].band} />
                <ReferenceArea y1={lines.alert} y2={lines.escapeTop} fill={STATE_STYLE['警戒'].band} />
                <ReferenceArea y1={lines.escapeTop} y2={yDomain[1]} fill={STATE_STYLE['逃顶'].band} />

                <XAxis
                  dataKey="day"
                  ticks={yearTicks}
                  tickFormatter={(v: string) => v.slice(0, 7)}
                  tick={{ fontSize: 10, fill: '#94a3b8' }}
                  axisLine={{ stroke: '#e2e8f0' }}
                  tickLine={false}
                  minTickGap={20}
                />
                <YAxis
                  domain={yDomain}
                  tick={{ fontSize: 10, fill: '#94a3b8' }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                  tickFormatter={(v: number) => v.toFixed(2)}
                />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
                  labelFormatter={(l: string) => l}
                  formatter={(value: any, name: any) => {
                    if (name === 'ratio') return [Number(value).toFixed(4), '比值'];
                    if (name === 'growthIdx') return [Number(value).toFixed(1), `${growth.name}（起点=100）`];
                    if (name === 'dividendIdx') return [Number(value).toFixed(1), `${dividend.name}（起点=100）`];
                    return [value, name];
                  }}
                />

                {/* 五条阈值线 */}
                <ReferenceLine y={lines.sweepBottom} stroke="#2563eb" strokeDasharray="4 3" strokeWidth={1}
                  label={{ value: `抄底 ${lines.sweepBottom}`, position: 'insideBottomLeft', fontSize: 10, fill: '#2563eb' }} />
                <ReferenceLine y={lines.opportunity} stroke="#0ea5e9" strokeDasharray="4 3" strokeWidth={1}
                  label={{ value: `机会 ${lines.opportunity}`, position: 'insideBottomLeft', fontSize: 10, fill: '#0ea5e9' }} />
                <ReferenceLine y={lines.watch} stroke="#06b6d4" strokeDasharray="4 3" strokeWidth={1}
                  label={{ value: `观察 ${lines.watch}`, position: 'insideBottomLeft', fontSize: 10, fill: '#06b6d4' }} />
                <ReferenceLine y={lines.alert} stroke="#f97316" strokeDasharray="4 3" strokeWidth={1}
                  label={{ value: `警戒 ${lines.alert}`, position: 'insideTopLeft', fontSize: 10, fill: '#f97316' }} />
                <ReferenceLine y={lines.escapeTop} stroke="#dc2626" strokeDasharray="4 3" strokeWidth={1}
                  label={{ value: `逃顶 ${lines.escapeTop}`, position: 'insideTopLeft', fontSize: 10, fill: '#dc2626' }} />

                <Area type="monotone" dataKey="ratio" stroke="none" fill="url(#ratioFill)" fillOpacity={0.18} />
                <defs>
                  <linearGradient id="ratioFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ef4444" />
                    <stop offset="100%" stopColor="#3b82f6" />
                  </linearGradient>
                </defs>
                <Line type="monotone" dataKey="ratio" stroke="#1e293b" strokeWidth={1.6} dot={false} isAnimationActive={false} />

                {/* 叠加线：归一化指数，走右轴 */}
                {hasOverlay && (
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    domain={rightDomain}
                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                    tickFormatter={(v: number) => v.toFixed(0)}
                  />
                )}
                {overlay.growth && (
                  <Line yAxisId={hasOverlay ? 'right' : undefined} type="monotone"
                    dataKey="growthIdx" stroke="#f97316" strokeWidth={1.2} strokeDasharray="1 0"
                    dot={false} isAnimationActive={false} opacity={0.85} />
                )}
                {overlay.dividend && (
                  <Line yAxisId={hasOverlay ? 'right' : undefined} type="monotone"
                    dataKey="dividendIdx" stroke="#059669" strokeWidth={1.2} strokeDasharray="1 0"
                    dot={false} isAnimationActive={false} opacity={0.85} />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 股债收益差：数据源不可用时明确提示，而不是静默消失 */}
        {spread && !spreadOption && (
          <div className="mb-4 pt-3 border-t border-slate-100">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-slate-600">
                股债收益差（{spread.definition}，近 {spread.years} 年）
              </span>
            </div>
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-xs text-amber-700 font-medium mb-1">股债收益差数据暂时拿不到</p>
              <p className="text-[11px] text-amber-600 leading-relaxed">
                数据源（乐咕乐股 / 东方财富）在当前服务器网络下不可达或超时。
                上方比值部分不受影响，可正常使用。
              </p>
              {spread.error && (
                <p className="text-[11px] text-amber-500 mt-1 break-all">诊断：{spread.error}</p>
              )}
            </div>
          </div>
        )}

        {spread && spreadOption && (
          <div className="mb-4 pt-3 border-t border-slate-100">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-slate-600">
                股债收益差（{spread.definition}，近 {spread.years} 年）
              </span>
              <div className="flex items-center gap-1">
                {spread.options.map((o) => (
                  <button
                    key={o.key}
                    onClick={() => setSpreadKey(o.key)}
                    className={`px-2 py-0.5 text-xs rounded transition-colors ${
                      spreadKey === o.key ? 'bg-slate-700 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                    }`}
                  >
                    {o.name}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-[11px] text-slate-400 mb-2">
              = 盈利收益率(1/PE) − 10年期国债收益率 · 越高代表股票相对债券越便宜 · 当前
              <span className={`font-medium ${spreadOption.stats.current > spreadOption.stats.plus1 ? 'text-blue-600' : spreadOption.stats.current < spreadOption.stats.minus1 ? 'text-red-600' : 'text-slate-600'}`}>
                {' '}{spreadOption.stats.current.toFixed(2)}%{' '}
              </span>
              （近{spread.years}年分位 {spreadOption.stats.percentile}%）
            </p>

            <div className="h-[240px] w-full -ml-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={spreadChart.pts} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                  <XAxis
                    dataKey="day"
                    ticks={spreadChart.ticks}
                    tickFormatter={(v: string) => v.slice(0, 4) + '年'}
                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                    axisLine={{ stroke: '#e2e8f0' }}
                    tickLine={false}
                    minTickGap={20}
                  />
                  <YAxis
                    domain={spreadYDomain}
                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                    tickFormatter={(v: number) => v.toFixed(1)}
                  />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
                    labelFormatter={(l: string) => l}
                    formatter={(value: any, name: any) => {
                      if (name === 'spread') return [`${Number(value).toFixed(2)}%`, '股债收益差'];
                      if (name === 'ep') return [`${Number(value).toFixed(2)}%`, '盈利收益率'];
                      if (name === 'y10') return [`${Number(value).toFixed(2)}%`, '10Y国债'];
                      return [value, name];
                    }}
                  />
                  {/* 均值 ±1σ 参考线 */}
                  <ReferenceLine y={spreadOption.stats.plus1} stroke="#2563eb" strokeDasharray="4 3" strokeWidth={1}
                    label={{ value: `+1σ ${spreadOption.stats.plus1.toFixed(2)}`, position: 'insideTopLeft', fontSize: 10, fill: '#2563eb' }} />
                  <ReferenceLine y={spreadOption.stats.mean} stroke="#94a3b8" strokeDasharray="4 3" strokeWidth={1}
                    label={{ value: `均值 ${spreadOption.stats.mean.toFixed(2)}`, position: 'insideTopLeft', fontSize: 10, fill: '#64748b' }} />
                  <ReferenceLine y={spreadOption.stats.minus1} stroke="#dc2626" strokeDasharray="4 3" strokeWidth={1}
                    label={{ value: `-1σ ${spreadOption.stats.minus1.toFixed(2)}`, position: 'insideBottomLeft', fontSize: 10, fill: '#dc2626' }} />
                  <ReferenceLine y={0} stroke="#cbd5e1" strokeWidth={1} />
                  <Line type="monotone" dataKey="spread" stroke="#7c3aed" strokeWidth={1.6} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="text-[11px] text-slate-400">
              高于 +1σ：股票相对债券极便宜（历史级买入区）；低于 -1σ：股票相对债券极贵（风险区）。
              {spreadOption.key === 'allA' && ' 全部A股为月频数据。'}
            </p>
          </div>
        )}

        {/* 状态分布 */}
        <div className="pt-3 border-t border-slate-100">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500">近 5 年各状态天数分布</span>
            <span className="text-xs text-slate-400">{totalDays} 个交易日</span>
          </div>
          <div className="grid grid-cols-6 gap-1.5">
            {stateOrder.map((s) => {
              const st = STATE_STYLE[s] || STATE_STYLE['中性'];
              const days = distribution[s] ?? 0;
              const share = totalDays ? (days / totalDays) * 100 : 0;
              const isCurrent = s === data.state;
              return (
                <div key={s} className={`rounded-lg p-2 text-center ${isCurrent ? 'ring-1 ' + st.ring + ' bg-white' : 'bg-slate-50'}`}>
                  <p className={`text-xs font-medium ${st.text}`}>{s}</p>
                  <p className="text-sm font-semibold text-slate-700">{days}</p>
                  <p className="text-[11px] text-slate-400">{share.toFixed(0)}%</p>
                </div>
              );
            })}
          </div>

          {/* 阈值规则说明 */}
          <p className="text-[11px] text-slate-500 mt-2.5 leading-relaxed">
            阈值：<span className="text-blue-600 font-medium">&lt;{lines.sweepBottom} 抄底</span> ｜
            <span className="text-sky-600 font-medium"> {lines.sweepBottom}~{lines.opportunity} 机会</span> ｜
            <span className="text-cyan-600 font-medium"> {lines.opportunity}~{lines.watch} 观察</span> ｜
            <span className="text-slate-600 font-medium"> {lines.watch}~{lines.alert} 中性</span> ｜
            <span className="text-orange-600 font-medium"> {lines.alert}~{lines.escapeTop} 警戒</span> ｜
            <span className="text-red-600 font-medium"> &gt;{lines.escapeTop} 逃顶</span>
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
