'use client';

import { useMemo, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea,
} from 'recharts';
import type { CybDividendResponse, CybDividendPoint, SpreadOption, SpreadBand } from '@/lib/api';

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

// 股债收益差分档配色：按历史分位染色。
//
// 方向千万别记反：股债收益差 = 盈利收益率 − 10年国债收益率。
// 差值【越大】= 股票盈利回报远超债券利息 = 股票相对债券【越便宜】。
// 所以分位越低（差值越小）越贵，分位越高越便宜：
//   0~10%  差值最低 → 最贵   → 红
//   10~30% 偏贵             → 黄
//   30~70% 常态             → 深蓝
//   70~90% 偏便宜           → 天蓝
//   90~100% 差值最高 → 最便宜 → 绿
// 颜色只表示"在历史分布里的高低位置"（红=垫底、绿=顶部），贵贱看 cheap 文案。
const SPREAD_BAND_STYLE: Record<SpreadBand, { color: string; label: string; range: string; area: string }> = {
  red: { color: '#dc2626', label: '最贵', range: '0~10%', area: 'rgba(220,38,38,0.07)' },
  yellow: { color: '#eab308', label: '偏贵', range: '10~30%', area: 'rgba(234,179,8,0.07)' },
  deepblue: { color: '#1e40af', label: '常态', range: '30~70%', area: 'rgba(30,64,175,0.05)' },
  skyblue: { color: '#0ea5e9', label: '偏便宜', range: '70~90%', area: 'rgba(14,165,233,0.07)' },
  green: { color: '#16a34a', label: '最便宜', range: '90~100%', area: 'rgba(22,163,74,0.07)' },
};

const SPREAD_BAND_ORDER: SpreadBand[] = ['red', 'yellow', 'deepblue', 'skyblue', 'green'];

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
  // 区间：近 10 年 / 近 5 年
  const [spreadRange, setSpreadRange] = useState<'10y' | '5y'>('10y');
  const spreadOption: SpreadOption | null =
    spread?.options?.find((o) => o.key === spreadKey) || spread?.options?.[0] || null;

  // 关键：10年/5年 各用【自己窗口的样本】算分位与分档，
  // 切换时颜色跟着重算 —— 5年视图展示的是真·近5年分位。
  const spreadView = useMemo(() => {
    if (!spreadOption) return null;
    const w = spreadOption.windows?.[spreadRange] || spreadOption.windows?.['10y'];
    if (w) {
      return {
        pts: w.points,
        stats: w.stats,
        thresholds: w.percentileThresholds,
        years: w.years,
      };
    }
    // 后端没给 windows（老数据兜底）：直接用 points + 顶层 stats
    return {
      pts: spreadOption.points,
      stats: spreadOption.stats,
      thresholds: spreadOption.percentileThresholds,
      years: spreadRange === '5y' ? 5 : 10,
    };
  }, [spreadOption, spreadRange]);

  const spreadChart = useMemo(() => {
    if (!spreadView) return { pts: [] as NonNullable<SpreadOption['points']>, ticks: [] as string[], start: '', end: '' };
    const pts = spreadView.pts;
    const seen = new Set<string>();
    const ticks: string[] = [];
    pts.forEach((p) => {
      const y = p.day.slice(0, 4);
      if (!seen.has(y)) { seen.add(y); ticks.push(p.day); }
    });
    return {
      pts,
      ticks,
      start: pts[0]?.day || '',
      end: pts[pts.length - 1]?.day || '',
    };
  }, [spreadView]);

  // 分档着色关键技巧：把每个点复制成 5 个 y 键（v_red / v_yellow / ...），
  // 只在该点属于当前档时保留数值，其余置 null。
  // recharts 遇到 null 会断线，于是每条 Line 只画出自己那一档的片段，
  // 连接处（band 切换点）用下面的过渡点补齐，视觉上就是一条连续的变色线。
  const bandedPtsSmooth = useMemo(() => {
    const raw = spreadChart.pts.map((p) => {
      const row: Record<string, any> = { ...p };
      SPREAD_BAND_ORDER.forEach((b) => {
        row[`v_${b}`] = p.band === b ? p.spread : null;
      });
      return row;
    });
    // 相邻两点跨档时给前一个 band 补上该点的值，避免出现 1 个交易日宽的白缝
    for (let i = 1; i < raw.length; i++) {
      const prevBand = spreadChart.pts[i - 1].band;
      const curBand = spreadChart.pts[i].band;
      if (prevBand && curBand && prevBand !== curBand) {
        raw[i][`v_${prevBand}`] = spreadChart.pts[i].spread;
      }
    }
    return raw;
  }, [spreadChart.pts]);

  const spreadYDomain = useMemo(() => {
    const st = spreadView?.stats;
    if (!st) return [0, 1] as [number, number];
    const vals = spreadChart.pts.map((p) => p.spread).concat([st.plus1, st.minus1]);
    if (!vals.length) return [0, 1] as [number, number];
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const pad = Math.max((hi - lo) * 0.1, 0.2);
    return [Number((lo - pad).toFixed(2)), Number((hi + pad).toFixed(2))] as [number, number];
  }, [spreadView, spreadChart.pts]);

  // 当前点所在档位
  const curPoint = spreadChart.pts.length ? spreadChart.pts[spreadChart.pts.length - 1] : null;
  const curBand: SpreadBand = (curPoint?.band as SpreadBand) || 'deepblue';
  const curBandStyle = SPREAD_BAND_STYLE[curBand];
  const curStats = spreadView?.stats;

  // 分位阈值：必须给默认值 —— ReferenceArea/ReferenceLine 要直接挂在 ComposedChart 下，
  // 不能放在 {cond && ...} 里（否则 recharts 会丢弃整块）。
  const thr = spreadView?.thresholds ?? { p10: 0, p30: 0, p70: 0, p90: 0 };

  // 分位线标签：自己画 <text>，不用 recharts 的 position ——
  // insideTopLeft/BottomLeft 是按"标签左边缘"定位且不留右侧余量，
  // 放到右边会被 SVG 边界裁掉半个字。
  // 这里左标签贴绘图区左边缘（文字基线在线的下方），右标签贴右边缘（基线在线上方），
  // 再用白描边（paintOrder 保证描边在字下面）保证压在折线上也读得清。
  const pctLabel = (text: string, color: string, side: 'left' | 'right') => (props: any) => {
    const vb = props?.viewBox || {};
    const x0 = Number(vb.x ?? 0);
    const w = Number(vb.width ?? 0);
    const y0 = Number(vb.y ?? 0);
    return (
      <text
        x={side === 'left' ? x0 + 4 : x0 + w + 4}
        y={y0 + (side === 'left' ? 11 : -4)}
        textAnchor="start"
        fontSize={10}
        fill={color}
        stroke="#ffffff"
        strokeWidth={3}
        strokeLinejoin="round"
        style={{ paintOrder: 'stroke' }}
      >
        {text}
      </text>
    );
  };

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

        {/* 状态分布：属于创业/红利比值，紧贴比值图下方 */}
        <div className="mb-4 pt-3 border-t border-slate-100">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500">近 5 年各状态天数分布（创业板指/中证红利）</span>
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

        {/* 股债收益差：数据源不可用时明确提示，而不是静默消失 */}
        {spread && !spreadOption && (
          <div className="mb-4 pt-3 border-t border-slate-100">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-slate-600">
                股债收益差（{spread.definition}）
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
                股债收益差（{spread.definition}）
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
                <span className="w-px h-4 bg-slate-200 mx-0.5" />
                {(['10y', '5y'] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setSpreadRange(r)}
                    className={`px-2 py-0.5 text-xs rounded transition-colors ${
                      spreadRange === r ? 'bg-slate-700 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                    }`}
                  >
                    {r === '10y' ? '近10年' : '近5年'}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-[11px] text-slate-400 mb-2">
              = 盈利收益率(1/PE) − 10年期国债收益率 · 越高代表股票相对债券越便宜 · 当前
              <span className="font-semibold" style={{ color: curBandStyle.color }}>
                {' '}{(curStats?.current ?? 0).toFixed(2)}%{' '}
              </span>
              （近{spreadView?.years ?? 10}年分位 {curPoint?.pct ?? curStats?.percentile ?? '-'}%，
              <span style={{ color: curBandStyle.color }}>{curBandStyle.label}</span>）
              {spreadOption.source && (
                <span className="text-slate-300"> · 数据：{spreadOption.source}{spreadOption.estimated ? '（口径不同）' : ''}</span>
              )}
              {(spreadOption.staleDays ?? 0) > 0 && (
                <span
                  className="ml-1 inline-flex items-center rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 ring-1 ring-amber-200"
                  title={`该标的最近数据为 ${spreadOption.latestDay}，比沪深300 晚 ${spreadOption.staleDays} 个交易日`}
                >
                  数据滞后{spreadOption.staleDays}日
                </span>
              )}
            </p>

            <div className="h-[250px] w-full -ml-2">
              <ResponsiveContainer width="100%" height="100%">
                {/* 必须用 ComposedChart：LineChart 只认 <Line>，会忽略
                    ReferenceArea / ReferenceLine，导致分档色带和 4 条分位虚线全都不渲染。
                    上面那张比值图用的就是 ComposedChart，所以它的阈值线一直正常。 */}
                <ComposedChart data={bandedPtsSmooth} margin={{ top: 6, right: 76, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                  <XAxis
                    dataKey="day"
                    ticks={spreadChart.ticks}
                    tickFormatter={(v: string) => v.slice(0, 4)}
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
                      if (String(name).startsWith('v_')) {
                        const b = String(name).slice(2) as SpreadBand;
                        const st = SPREAD_BAND_STYLE[b] || SPREAD_BAND_STYLE.deepblue;
                        return [`${Number(value).toFixed(2)}%  ${st.label}`, '股债收益差'];
                      }
                      if (name === 'ep') return [`${Number(value).toFixed(2)}%`, '盈利收益率'];
                      if (name === 'y10') return [`${Number(value).toFixed(2)}%`, '10Y国债'];
                      return [value, name];
                    }}
                  />

                  {/* 分位档背景色带（下→上 = 贵→便宜）。
                      写法必须平铺：recharts 只认 ComposedChart 的直接子元素，
                      用 IIFE + Fragment 包裹会被当成非法子节点丢弃（4 条线曾因此完全不显示）。 */}
                  <ReferenceArea y1={spreadYDomain[0]} y2={thr.p10} fill={SPREAD_BAND_STYLE.red.area} />
                  <ReferenceArea y1={thr.p10} y2={thr.p30} fill={SPREAD_BAND_STYLE.yellow.area} />
                  <ReferenceArea y1={thr.p30} y2={thr.p70} fill={SPREAD_BAND_STYLE.deepblue.area} />
                  <ReferenceArea y1={thr.p70} y2={thr.p90} fill={SPREAD_BAND_STYLE.skyblue.area} />
                  <ReferenceArea y1={thr.p90} y2={spreadYDomain[1]} fill={SPREAD_BAND_STYLE.green.area} />

                  {/* 四条分位分割线：p10 红 / p30 黄 / p70 蓝 / p90 天蓝
                      标签一律左右交错（p10、p70 走左下，p30、p90 走右上）：
                      相邻两条线的分位值可能非常接近，比如沪深300 的 p70=5.74 与
                      p90=6.25 只差 0.5，折算到 250px 高的图上不到 12px，
                      四条都靠左会直接叠成一团（标签高 12px）。
                      水平错开是唯一不依赖像素估算、切 10年/5年 与不同标的都成立的办法。 */}
                  <ReferenceLine y={thr.p10} stroke={SPREAD_BAND_STYLE.red.color} strokeDasharray="5 3" strokeWidth={1} strokeOpacity={0.8}
                    label={pctLabel(`10% 分位 ${thr.p10.toFixed(2)}`, SPREAD_BAND_STYLE.red.color, 'left')} />
                  <ReferenceLine y={thr.p30} stroke={SPREAD_BAND_STYLE.yellow.color} strokeDasharray="5 3" strokeWidth={1} strokeOpacity={0.8}
                    label={pctLabel(`30% 分位 ${thr.p30.toFixed(2)}`, SPREAD_BAND_STYLE.yellow.color, 'right')} />
                  <ReferenceLine y={thr.p70} stroke={SPREAD_BAND_STYLE.deepblue.color} strokeDasharray="5 3" strokeWidth={1} strokeOpacity={0.8}
                    label={pctLabel(`70% 分位 ${thr.p70.toFixed(2)}`, SPREAD_BAND_STYLE.deepblue.color, 'left')} />
                  <ReferenceLine y={thr.p90} stroke={SPREAD_BAND_STYLE.skyblue.color} strokeDasharray="5 3" strokeWidth={1} strokeOpacity={0.8}
                    label={pctLabel(`90% 分位 ${thr.p90.toFixed(2)}`, SPREAD_BAND_STYLE.skyblue.color, 'right')} />
                  <ReferenceLine y={0} stroke="#cbd5e1" strokeWidth={1} />

                  {/* 五条分档线，各自只画自己那一段 */}
                  {SPREAD_BAND_ORDER.map((b) => (
                    <Line
                      key={b}
                      type="linear"
                      dataKey={`v_${b}`}
                      stroke={SPREAD_BAND_STYLE[b].color}
                      strokeWidth={2}
                      dot={false}
                      isAnimationActive={false}
                      connectNulls={false}
                    />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* 分档图例 */}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1.5">
              {SPREAD_BAND_ORDER.map((b) => {
                const st = SPREAD_BAND_STYLE[b];
                const isCur = b === curBand;
                return (
                  <span key={b} className={`inline-flex items-center gap-1 text-[11px] ${isCur ? 'font-semibold' : ''}`}
                    style={{ color: isCur ? st.color : '#94a3b8' }}>
                    <span className="inline-block w-3 h-[3px] rounded" style={{ background: st.color }} />
                    {st.range} {st.label}
                    {isCur && <span className="text-slate-400">（当前）</span>}
                  </span>
                );
              })}
            </div>

            {/* 样本区间：分位口径差异全在起点，必须明确标出来 */}
            {spreadView?.stats?.start && (
              <p className="text-[11px] text-slate-400 mt-1">
                分位基于 <span className="text-slate-500 font-medium">{spreadView.stats.start} ~ {spreadView.stats.end}</span>
                {' '}共 <span className="text-slate-500 font-medium">{spreadView.stats.samples}</span> 个交易日
                （近 {spreadView.years} 年）。换个起点分位会明显不同，与其他 App 对比时请先核对区间。
              </p>
            )}

            <p className="text-[11px] text-slate-400 mt-1.5 leading-relaxed">
              差值越大 = 股票盈利回报远超债券利息 = 股票相对债券越便宜。所以
              <span style={{ color: SPREAD_BAND_STYLE.green.color }} className="font-medium">越往上越便宜</span>、
              <span style={{ color: SPREAD_BAND_STYLE.red.color }} className="font-medium">越往下越贵</span>：
              <span style={{ color: SPREAD_BAND_STYLE.red.color }}>红=分位最低的10%（最贵）</span>、
              <span style={{ color: SPREAD_BAND_STYLE.green.color }}>绿=分位最高的10%（最便宜）</span>。
              四条虚线就是 10%/30%/70%/90% 分位对应的差值，切换窗口时它们会一起重算。
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
