'use client';

import { Card } from '@/components/ui/card';
import type { NationalTeamResponse, NationalTeamEtf, NationalTeamGroup } from '@/lib/api';

type Data = NationalTeamResponse['data'];

// 状态配色。红=显著放量、橙=放量、灰=正常（预警语义，不是涨跌语义）。
const STATE_STYLE: Record<
  string,
  { chip: string; text: string; bar: string; card: string; ring: string }
> = {
  显著放量: {
    chip: 'bg-red-600 text-white ring-red-600',
    text: 'text-red-600',
    bar: 'bg-red-500',
    card: 'bg-gradient-to-br from-red-50 to-white ring-red-200',
    ring: 'ring-red-200',
  },
  放量: {
    chip: 'bg-orange-500 text-white ring-orange-500',
    text: 'text-orange-600',
    bar: 'bg-orange-400',
    card: 'bg-gradient-to-br from-orange-50 to-white ring-orange-200',
    ring: 'ring-orange-200',
  },
  正常: {
    chip: 'bg-white text-slate-500 ring-slate-200',
    text: 'text-slate-600',
    bar: 'bg-slate-200',
    card: 'bg-white ring-slate-200',
    ring: 'ring-slate-200',
  },
  数据不足: {
    chip: 'bg-white text-slate-400 ring-slate-200',
    text: 'text-slate-400',
    bar: 'bg-slate-100',
    card: 'bg-white ring-slate-200',
    ring: 'ring-slate-200',
  },
};

const GROUP_STATE_STYLE: Record<string, string> = {
  显著放量: 'bg-red-600 text-white shadow-sm shadow-red-200',
  放量: 'bg-orange-500 text-white shadow-sm shadow-orange-200',
  正常: 'bg-slate-100 text-slate-500',
  数据不足: 'bg-slate-100 text-slate-400',
};

// 成交额：元 → 亿元
function amtText(v: number | null | undefined) {
  if (v === null || v === undefined) return '-';
  const yi = v / 1e8;
  if (yi >= 100) return `${yi.toFixed(0)} 亿`;
  if (yi >= 10) return `${yi.toFixed(1)} 亿`;
  return `${yi.toFixed(2)} 亿`;
}

function ratioText(r: number | null | undefined) {
  if (r === null || r === undefined) return '-';
  return `${r.toFixed(2)}x`;
}

function pctText(p: number | null | undefined) {
  if (p === null || p === undefined) return '-';
  return `${Math.round(p * 100)}%`;
}

function changeText(p: number | null | undefined) {
  if (p === null || p === undefined) return '-';
  return `${p >= 0 ? '+' : ''}${p.toFixed(2)}%`;
}

// 涨跌幅：A 股习惯 红涨绿跌
function changeCls(p: number | null | undefined) {
  if (p === null || p === undefined) return 'text-slate-400';
  return p > 0 ? 'text-red-500' : p < 0 ? 'text-emerald-500' : 'text-slate-500';
}

function changeBg(p: number | null | undefined) {
  if (p === null || p === undefined) return 'bg-slate-50 text-slate-400';
  return p > 0 ? 'bg-red-50 text-red-600' : p < 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-50 text-slate-500';
}

/* ---------------- 手机端：卡片式 ---------------- */

function EtfMobileCard({ etf }: { etf: NationalTeamEtf }) {
  const st = STATE_STYLE[etf.state] || STATE_STYLE['数据不足'];
  const isAlert = etf.state === '放量' || etf.state === '显著放量';

  // 四宫格指标，手机端信息一个不少
  const metrics = [
    { label: '现价', value: etf.price != null ? etf.price.toFixed(3) : '-', cls: 'text-slate-700' },
    { label: '成交额', value: amtText(etf.todayAmount), cls: 'text-slate-700' },
    { label: '量比', value: ratioText(etf.ratio), cls: st.text + ' font-bold' },
    { label: '20日', value: ratioText(etf.ratioSlow), cls: 'text-slate-500' },
    { label: '分位', value: pctText(etf.percentile), cls: 'text-slate-500' },
  ];

  return (
    <div className={`relative rounded-xl ring-1 ${st.card} px-3 py-2.5 overflow-hidden`}>
      {/* 左侧状态色条 */}
      <span className={`absolute left-0 top-0 bottom-0 w-1 ${st.bar}`} />

      {/* 第一行：名称 + 状态 */}
      <div className="flex items-start gap-2 pl-1">
        <div className="min-w-0 flex-1">
          <p className={`text-[13px] font-semibold leading-tight ${isAlert ? 'text-slate-900' : 'text-slate-700'} truncate`}>
            {etf.name}
          </p>
          <p className="text-[10px] text-slate-400 mt-0.5 tracking-wide">{etf.symbol}</p>
        </div>
        <span className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ring-1 ${st.chip}`}>
          {etf.error ? '异常' : etf.state}
        </span>
      </div>

      {/* 第二行：价格 + 涨跌幅 */}
      <div className="mt-2 pl-1 flex items-baseline gap-2">
        <span className="text-lg font-bold text-slate-800 leading-none tabular-nums">
          {etf.price != null ? etf.price.toFixed(3) : '-'}
        </span>
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-semibold tabular-nums ${changeBg(etf.changePct)}`}>
          {changeText(etf.changePct)}
        </span>
      </div>

      {/* 第三行：指标网格（现价已在上面，排除） */}
      <div className="mt-2 pl-1 grid grid-cols-4 gap-1.5">
        {metrics.slice(1).map((m) => (
          <div key={m.label} className="rounded-lg bg-white/70 px-1.5 py-1 text-center ring-1 ring-slate-100">
            <p className="text-[9px] text-slate-400 leading-none mb-1">{m.label}</p>
            <p className={`text-[11px] leading-none tabular-nums ${m.cls}`}>{m.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------------- 桌面端：表格行 ---------------- */

function EtfRow({ etf }: { etf: NationalTeamEtf }) {
  const st = STATE_STYLE[etf.state] || STATE_STYLE['数据不足'];
  return (
    <div className="flex items-center gap-2 px-2 py-1.5 text-xs hover:bg-slate-50/80 transition-colors">
      <div className="w-[132px] shrink-0 pl-1">
        <p className="font-medium text-slate-700 truncate">{etf.name}</p>
        <p className="text-[10px] text-slate-400">{etf.symbol}</p>
      </div>
      <div className="w-[58px] shrink-0 text-right text-slate-600 tabular-nums">
        {etf.price != null ? etf.price.toFixed(3) : '-'}
      </div>
      <div className={`w-[60px] shrink-0 text-right font-medium tabular-nums ${changeCls(etf.changePct)}`} title="今日涨跌幅">
        {changeText(etf.changePct)}
      </div>
      <div className="w-[68px] shrink-0 text-right text-slate-500 tabular-nums" title="今日累计成交额">
        {amtText(etf.todayAmount)}
      </div>
      <div className="w-[48px] shrink-0 text-right font-semibold tabular-nums" title={`量比（成交额口径，vs 近${etf.baseDays ?? 5}日同进度基准）`}>
        <span className={st.text}>{ratioText(etf.ratio)}</span>
      </div>
      <div className="w-[44px] shrink-0 text-right text-[11px] text-slate-400 tabular-nums" title={`vs 近${etf.baseDaysSlow ?? 20}日基准（参考）`}>
        {ratioText(etf.ratioSlow)}
      </div>
      <div className="w-[38px] shrink-0 text-right text-[11px] text-slate-400 tabular-nums" title="同时刻历史分位（近20日，参考）">
        {pctText(etf.percentile)}
      </div>
      <div className="w-[62px] shrink-0 text-right">
        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] ring-1 ${st.chip}`}>
          {etf.error ? '异常' : etf.state}
        </span>
      </div>
    </div>
  );
}

/* ---------------- 分组 ---------------- */

function GroupBlock({ group }: { group: NationalTeamGroup }) {
  const cls = GROUP_STATE_STYLE[group.state] || GROUP_STATE_STYLE['数据不足'];
  const isAlert = group.alertCount > 0;

  return (
    <div className="mb-3 last:mb-0">
      {/* 组头 */}
      <div className="flex items-center gap-2 mb-1.5 px-0.5">
        <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold ${cls}`}>{group.index}</span>
        {isAlert ? (
          <span className="text-[10px] font-medium text-orange-600">
            {group.alertCount}/{group.totalCount} 放量
          </span>
        ) : (
          <span className="text-[10px] text-slate-400">{group.totalCount} 只</span>
        )}
        <span className="text-[10px] text-slate-400 ml-auto tabular-nums">
          均量比 <span className="font-semibold text-slate-500">{ratioText(group.avgRatio)}</span>
        </span>
      </div>

      {/* 手机端：卡片 */}
      <div className="sm:hidden space-y-1.5">
        {group.etfs.map((e) => (
          <EtfMobileCard key={e.symbol} etf={e} />
        ))}
      </div>

      {/* 桌面端：表格 */}
      <div className="hidden sm:block divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white overflow-hidden shadow-sm">
        <div className="flex items-center gap-2 px-2 py-1.5 text-[10px] font-medium text-slate-400 bg-slate-50">
          <div className="w-[132px] shrink-0 pl-1">名称</div>
          <div className="w-[58px] shrink-0 text-right">现价</div>
          <div className="w-[60px] shrink-0 text-right">涨跌幅</div>
          <div className="w-[68px] shrink-0 text-right">成交额</div>
          <div className="w-[48px] shrink-0 text-right">量比</div>
          <div className="w-[44px] shrink-0 text-right">20日</div>
          <div className="w-[38px] shrink-0 text-right">分位</div>
          <div className="w-[62px] shrink-0 text-right">状态</div>
        </div>
        {group.etfs.map((e) => (
          <EtfRow key={e.symbol} etf={e} />
        ))}
      </div>
    </div>
  );
}

/* ---------------- 主卡片 ---------------- */

export default function NationalTeamCard({ data }: { data: Data }) {
  const { summary, groups, thresholds, marketStatus, timestamp, params } = data;

  const headline =
    summary.strongCount > 0
      ? {
          text: `${summary.strongCount} 只显著放量`,
          cls: 'bg-gradient-to-r from-red-600 to-red-500 text-white shadow-sm shadow-red-200',
          dot: 'bg-white',
        }
      : summary.alertCount > 0
      ? {
          text: `${summary.alertCount} 只放量`,
          cls: 'bg-gradient-to-r from-orange-500 to-amber-400 text-white shadow-sm shadow-orange-200',
          dot: 'bg-white',
        }
      : { text: '无放量异动', cls: 'bg-slate-100 text-slate-500', dot: 'bg-slate-400' };

  return (
    <Card className="border-slate-200 shadow-sm">
      <div className="p-3 sm:p-4 space-y-3">
        {/* 顶部：总体状态 */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold ${headline.cls}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${headline.dot} animate-pulse`} />
            {headline.text}
          </span>
          <span className="text-[11px] text-slate-400">
            监控 {summary.totalCount} 只 · {marketStatus}
          </span>
          <span className="text-[10px] text-slate-300 ml-auto tabular-nums" title={timestamp}>
            {timestamp.slice(5, 16)} 更新
          </span>
        </div>

        {/* 阈值说明：小屏改成三个小胶囊 */}
        <div className="flex items-center flex-wrap gap-1.5 text-[10px]">
          <span className="px-2 py-0.5 rounded-md bg-red-50 text-red-600 font-medium ring-1 ring-red-100">
            ≥ {thresholds.strong} 显著放量
          </span>
          <span className="px-2 py-0.5 rounded-md bg-orange-50 text-orange-600 font-medium ring-1 ring-orange-100">
            ≥ {thresholds.alert} 放量
          </span>
          <span className="px-2 py-0.5 rounded-md bg-slate-50 text-slate-500 ring-1 ring-slate-100">
            基准 近{params.baseDaysFast}日同进度
          </span>
        </div>

        {/* 分组列表 */}
        <div className="space-y-3">
          {groups.map((g) => (
            <GroupBlock key={g.index} group={g} />
          ))}
        </div>

        {/* 底注 */}
        <p className="text-[10px] text-slate-400 leading-relaxed pt-1 border-t border-slate-100">
          量比 = 今日累计成交额 ÷ 近{params.baseDaysFast}日同一时刻平均成交额（用成交额而非成交量，
          避免跨品种价格差异与份额拆分失真）。「20日」列为近{params.baseDaysSlow}日基准参考，
          「分位」为同时刻量比在近20日中的排位。分组内多只同时放量更值得关注。
          本卡片仅为预警，请自行二次判断。
        </p>
      </div>
    </Card>
  );
}
