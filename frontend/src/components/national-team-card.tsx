'use client';

import { Card } from '@/components/ui/card';
import type { NationalTeamResponse, NationalTeamEtf, NationalTeamGroup } from '@/lib/api';

type Data = NationalTeamResponse['data'];

// 状态配色。红=显著放量、橙=放量、灰=正常（预警语义，不是涨跌语义）。
const STATE_STYLE: Record<string, { chip: string; text: string; row: string }> = {
  显著放量: { chip: 'bg-red-100 text-red-700 ring-red-300', text: 'text-red-600', row: 'bg-red-50/60' },
  放量: { chip: 'bg-orange-100 text-orange-700 ring-orange-300', text: 'text-orange-600', row: 'bg-orange-50/50' },
  正常: { chip: 'bg-slate-100 text-slate-500 ring-slate-200', text: 'text-slate-500', row: '' },
  数据不足: { chip: 'bg-slate-100 text-slate-400 ring-slate-200', text: 'text-slate-400', row: '' },
};

const GROUP_STATE_STYLE: Record<string, string> = {
  显著放量: 'bg-red-600 text-white',
  放量: 'bg-orange-500 text-white',
  正常: 'bg-slate-100 text-slate-500',
  数据不足: 'bg-slate-100 text-slate-400',
};

function volText(v: number | null | undefined) {
  if (v === null || v === undefined) return '-';
  const yi = v / 1e8;         // 手 → 亿手不直观，改为显示万手
  const wan = v / 1e4;
  if (wan >= 1000) return `${(wan / 1e4).toFixed(2)} 亿手`;
  return `${wan.toFixed(0)} 万手`;
}

function ratioText(r: number | null | undefined) {
  if (r === null || r === undefined) return '-';
  return `${r.toFixed(2)}x`;
}

function pctText(p: number | null | undefined) {
  if (p === null || p === undefined) return '-';
  return `${Math.round(p * 100)}%`;
}

function EtfRow({ etf, thresholds }: { etf: NationalTeamEtf; thresholds: { alert: number; strong: number } }) {
  const st = STATE_STYLE[etf.state] || STATE_STYLE['数据不足'];
  return (
    <div className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs ${st.row}`}>
      <div className="w-[130px] shrink-0">
        <p className="font-medium text-slate-700 truncate">{etf.name}</p>
        <p className="text-[10px] text-slate-400">{etf.symbol}</p>
      </div>
      <div className="w-[64px] shrink-0 text-right text-slate-600">
        {etf.price != null ? etf.price.toFixed(3) : '-'}
      </div>
      <div className="w-[70px] shrink-0 text-right text-slate-500" title="今日累计成交量">
        {volText(etf.todayVolume)}
      </div>
      <div className="w-[48px] shrink-0 text-right font-semibold" title={`量比（vs 近${etf.baseDays ?? 5}日同进度基准）`}>
        <span className={st.text}>{ratioText(etf.ratio)}</span>
      </div>
      <div className="w-[44px] shrink-0 text-right text-[11px] text-slate-400" title={`vs 近${etf.baseDaysSlow ?? 20}日基准（参考）`}>
        {ratioText(etf.ratioSlow)}
      </div>
      <div className="w-[40px] shrink-0 text-right text-[11px] text-slate-400" title="同时刻历史分位（近20日，参考）">
        {pctText(etf.percentile)}
      </div>
      <div className="w-[64px] shrink-0 text-right">
        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] ring-1 ${st.chip}`}>
          {etf.error ? '异常' : etf.state}
        </span>
      </div>
    </div>
  );
}

function GroupBlock({ group, thresholds }: { group: NationalTeamGroup; thresholds: { alert: number; strong: number } }) {
  const cls = GROUP_STATE_STYLE[group.state] || GROUP_STATE_STYLE['数据不足'];
  return (
    <div className="mb-2 last:mb-0">
      <div className="flex items-center gap-2 mb-1 px-1">
        <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${cls}`}>{group.index}</span>
        {group.alertCount > 0 && (
          <span className="text-[10px] text-slate-400">
            {group.alertCount}/{group.totalCount} 放量
          </span>
        )}
        <span className="text-[10px] text-slate-300 ml-auto">均量比 {ratioText(group.avgRatio)}</span>
      </div>
      <div className="divide-y divide-slate-100 rounded border border-slate-100 bg-white">
        {/* 表头 */}
        <div className="flex items-center gap-2 px-2 py-1 text-[10px] text-slate-400 bg-slate-50 rounded-t">
          <div className="w-[130px] shrink-0">名称</div>
          <div className="w-[64px] shrink-0 text-right">现价</div>
          <div className="w-[70px] shrink-0 text-right">累计量</div>
          <div className="w-[48px] shrink-0 text-right">量比</div>
          <div className="w-[44px] shrink-0 text-right">20日</div>
          <div className="w-[40px] shrink-0 text-right">分位</div>
          <div className="w-[64px] shrink-0 text-right">状态</div>
        </div>
        {group.etfs.map((e) => (
          <EtfRow key={e.symbol} etf={e} thresholds={thresholds} />
        ))}
      </div>
    </div>
  );
}

export default function NationalTeamCard({ data }: { data: Data }) {
  const { summary, groups, thresholds, marketStatus, timestamp, params } = data;

  const headline =
    summary.strongCount > 0
      ? { text: `${summary.strongCount} 只显著放量`, cls: 'bg-red-600 text-white' }
      : summary.alertCount > 0
      ? { text: `${summary.alertCount} 只放量`, cls: 'bg-orange-500 text-white' }
      : { text: '无放量异动', cls: 'bg-slate-200 text-slate-600' };

  return (
    <Card className="border-slate-200">
      <div className="p-4 space-y-3">
        {/* 顶部：总体状态 */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2.5 py-1 rounded text-xs font-semibold ${headline.cls}`}>
            {headline.text}
          </span>
          <span className="text-[11px] text-slate-400">
            监控 {summary.totalCount} 只 · {marketStatus}
          </span>
          <span className="text-[10px] text-slate-300 ml-auto" title={timestamp}>
            {timestamp.slice(5, 16)} 更新
          </span>
        </div>

        {/* 阈值说明 */}
        <div className="flex items-center gap-3 text-[10px] text-slate-400">
          <span>量比 ≥ {thresholds.strong} 显著放量</span>
          <span>≥ {thresholds.alert} 放量</span>
          <span className="ml-auto">基准：近{params.baseDaysFast}日同进度均值</span>
        </div>

        {/* 分组列表 */}
        {groups.map((g) => (
          <GroupBlock key={g.index} group={g} thresholds={thresholds} />
        ))}

        {/* 底注 */}
        <p className="text-[10px] text-slate-400 leading-relaxed">
          量比 = 今日累计成交量 ÷ 近{params.baseDaysFast}日同一时刻平均量；「20日」列为
          近{params.baseDaysSlow}日基准参考，「分位」为同时刻量比在近20日中的排位。
          分组内多只同时放量更值得关注。本卡片仅为预警，请自行二次判断。
        </p>
      </div>
    </Card>
  );
}
