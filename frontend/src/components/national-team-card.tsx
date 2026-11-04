'use client';

import { Card, CardContent } from '@/components/ui/card';
import type { NationalTeamResponse, NationalTeamEtf, NationalTeamGroup } from '@/lib/api';

type Data = NationalTeamResponse['data'];

// 状态徽标（预警语义，不是涨跌语义）：红=显著放量、橙=放量、绿=正常
const STATE_BADGE: Record<string, string> = {
  显著放量: 'bg-red-500 text-white',
  放量: 'bg-orange-500 text-white',
  正常: 'bg-emerald-500 text-white',
  数据不足: 'bg-slate-400 text-white',
};

const GROUP_STATE_BADGE: Record<string, string> = {
  显著放量: 'bg-red-500 text-white',
  放量: 'bg-orange-500 text-white',
  正常: 'bg-emerald-500 text-white',
  数据不足: 'bg-slate-400 text-white',
};

// 成交额：元 → 亿元
function amtText(v: number | null | undefined) {
  if (v === null || v === undefined) return '-';
  const yi = v / 1e8;
  if (yi >= 100) return `${yi.toFixed(0)} 亿`;
  if (yi >= 10) return `${yi.toFixed(1)} 亿`;
  return `${yi.toFixed(2)} 亿`;
}

// 净申赎金额：带符号，元 → 亿元
function netText(v: number | null | undefined) {
  if (v === null || v === undefined) return '-';
  const yi = v / 1e8;
  const abs = Math.abs(yi);
  const body = abs >= 100 ? abs.toFixed(0) : abs >= 10 ? abs.toFixed(1) : abs.toFixed(2);
  return `${yi > 0 ? '+' : yi < 0 ? '-' : ''}${body} 亿`;
}

// 净申购份额：带符号，份 → 亿份。
// 和金额并列显示的理由：金额会被价格波动放大/缩小，份额才是申赎行为本身；
// 官方口径（深交所/上交所规模表）给的就是份额，两者一起看才不会被单价迷惑。
function netSharesText(v: number | null | undefined) {
  if (v === null || v === undefined) return '';
  const yi = v / 1e8;
  const abs = Math.abs(yi);
  const body = abs >= 100 ? abs.toFixed(0) : abs >= 10 ? abs.toFixed(1) : abs.toFixed(2);
  return `${yi > 0 ? '+' : yi < 0 ? '-' : ''}${body} 亿份`;
}

// 净申赎配色：净申购=红（资金进场），净赎回=绿（资金离场），A 股习惯
function netCls(v: number | null | undefined) {
  if (v === null || v === undefined) return 'text-slate-400';
  return v > 0 ? 'text-red-500' : v < 0 ? 'text-emerald-600' : 'text-slate-500';
}

function netCellCls(v: number | null | undefined) {
  if (v === null || v === undefined) return 'bg-slate-50 text-slate-400';
  return v > 0 ? 'bg-red-50 text-red-600' : v < 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-50 text-slate-500';
}

// 分位：申购强度越高越红；净赎回一侧走绿色
function pctOfNetText(p: number | null | undefined) {
  if (p === null || p === undefined) return '-';
  return `${Math.round(p * 100)}%`;
}

function pctOfNetCls(p: number | null | undefined, net: number | null | undefined) {
  if (p === null || p === undefined) return 'text-slate-400';
  const isInflow = (net ?? 0) >= 0;
  if (p >= 0.9) return isInflow ? 'text-red-600 font-bold' : 'text-emerald-600 font-bold';
  if (p >= 0.7) return isInflow ? 'text-red-500' : 'text-emerald-500';
  if (p <= 0.1) return isInflow ? 'text-red-400' : 'text-emerald-700 font-bold';
  return 'text-slate-500';
}

// 份额日期 YYYYMMDD → MM-DD
function asOfText(d: string | null | undefined) {
  if (!d || d.length !== 8) return '';
  return `${d.slice(4, 6)}-${d.slice(6, 8)}`;
}

// 沪深披露时点不同（沪 T 日盘后、深 T+1 傍晚），两端日期不一致时显示成区间。
// 注意措辞：这里说的是「份额的日期」，不是金额的日期——金额由相邻两日份额差算出，
// 早前写成「11-04 份额」紧挨着金额，容易被误读成「11-04 的金额」。
function asOfRange(min: string | null | undefined, max: string | null | undefined) {
  if (!max) return '';
  if (!min || min === max) return `份额 ${asOfText(max)}`;
  return `份额 ${asOfText(min)}~${asOfText(max)}`;
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

// 量比所处区间的配色：与预警规则一致
function ratioCellBg(r: number | null | undefined) {
  if (r == null) return 'bg-slate-50 text-slate-400';
  if (r >= 2.0) return 'bg-red-50 text-red-600 ring-1 ring-red-300';
  if (r >= 1.5) return 'bg-orange-50 text-orange-600 ring-1 ring-orange-300';
  return 'bg-emerald-50 text-emerald-600';
}

/* ---------------- 单只 ETF 卡片（对齐趋势轮动设计语言） ---------------- */

function EtfCard({ etf, rank }: { etf: NationalTeamEtf; rank: number }) {
  const isAlert = etf.state === '放量' || etf.state === '显著放量';
  const badge = STATE_BADGE[etf.error ? '数据不足' : etf.state] || STATE_BADGE['数据不足'];

  return (
    <Card className={`mb-3 bg-white border ${isAlert ? 'border-orange-300 shadow-md' : 'border-slate-200 shadow-sm'} hover:shadow-md transition-shadow`}>
      <CardContent className="p-4">
        {/* 顶部：序号、名称、代码、状态 */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-lg font-bold text-slate-500">#{rank}</span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-800 truncate">{etf.name}</span>
                <span className="text-xs text-slate-400 shrink-0">{etf.symbol}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <span className={`px-2 py-0.5 text-xs font-medium rounded ${badge}`}>
              {etf.error ? '异常' : etf.state}
            </span>
          </div>
        </div>

        {/* 二级市场指标：四宫格（现价 / 涨跌幅 / 成交额 / 量比） */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2">
          <div className="bg-slate-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">现价</p>
            <p className="text-xl font-bold text-slate-700 tabular-nums">
              {etf.price != null ? etf.price.toFixed(3) : '-'}
            </p>
          </div>
          <div className={`rounded-lg p-3 text-center tabular-nums ${changeCls(etf.changePct).includes('red') ? 'bg-red-50' : changeCls(etf.changePct).includes('emerald') ? 'bg-emerald-50' : 'bg-slate-50'}`}>
            <p className="text-xs text-slate-500 mb-1">今日涨跌幅</p>
            <p className={`text-xl font-bold tabular-nums ${changeCls(etf.changePct)}`}>
              {changeText(etf.changePct)}
            </p>
          </div>
          <div className="bg-blue-50 rounded-lg p-3 text-center">
            <p className="text-xs text-slate-500 mb-1">今日成交额</p>
            <p className="text-xl font-bold text-blue-600 tabular-nums">{amtText(etf.todayAmount)}</p>
          </div>
          <div className={`rounded-lg p-3 text-center ${ratioCellBg(etf.ratio)}`}>
            <p className="text-xs text-slate-500 mb-1">量比</p>
            <p className={`text-xl font-bold tabular-nums ${ratioCellBg(etf.ratio).split(' ')[1]}`}>
              {ratioText(etf.ratio)}
            </p>
          </div>
        </div>

        {/* 一级市场：净申赎（份额口径，T+1 披露）。与上方量比是两条独立证据线 */}
        <div className="rounded-lg ring-1 ring-slate-200 bg-white overflow-hidden mb-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-50 border-b border-slate-100">
            <span className="text-[10px] font-medium text-slate-500">一级市场净申赎</span>
            {etf.netAsOf && (
              <span className="text-[9px] text-slate-400 tabular-nums">
                份额日 {asOfText(etf.netAsOf)}
              </span>
            )}
            <span className="ml-auto text-[9px] text-slate-300">T+1 披露 · 非实时</span>
          </div>
          {etf.netAmount === null || etf.netAmount === undefined ? (
            <div className="px-2.5 py-2 text-[10px] text-slate-400">
              {etf.netNote || '暂无份额数据'}
            </div>
          ) : (
            <div className="grid grid-cols-3 divide-x divide-slate-100">
              <div className="px-2 py-1.5 text-center">
                <p className="text-[9px] text-slate-400 mb-0.5">当日</p>
                <p className={`text-sm font-bold tabular-nums ${netCls(etf.netAmount)}`}>
                  {netText(etf.netAmount)}
                </p>
                {etf.netShares !== null && etf.netShares !== undefined && (
                  <p className="text-[9px] text-slate-400 tabular-nums mt-0.5">
                    {netSharesText(etf.netShares)}
                  </p>
                )}
              </div>
              <div className="px-2 py-1.5 text-center">
                <p className="text-[9px] text-slate-400 mb-0.5">近5日累计</p>
                <p className={`text-sm font-bold tabular-nums ${netCls(etf.net5Amount)}`}>
                  {netText(etf.net5Amount)}
                </p>
                {etf.net5Shares !== null && etf.net5Shares !== undefined && (
                  <p className="text-[9px] text-slate-400 tabular-nums mt-0.5">
                    {netSharesText(etf.net5Shares)}
                  </p>
                )}
              </div>
              <div className="px-2 py-1.5 text-center">
                <p className="text-[9px] text-slate-400 mb-0.5">
                  份额分位{etf.netDays ? `(${etf.netDays}日)` : ''}
                </p>
                <p className={`text-sm font-bold tabular-nums ${pctOfNetCls(etf.netPercentile, etf.netAmount)}`}>
                  {pctOfNetText(etf.netPercentile)}
                </p>
                <p className="text-[9px] text-slate-400 mt-0.5">越高越异常</p>
              </div>
            </div>
          )}
        </div>

        {/* 参考指标：20日基准量比 + 历史分位 */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">20日基准</span>
            <span className="font-semibold text-slate-700 tabular-nums">{ratioText(etf.ratioSlow)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">成交额分位</span>
            <span className="font-semibold text-slate-700 tabular-nums">{pctText(etf.percentile)}</span>
          </div>
          <span className="text-slate-400 text-[10px]">
            基准：近{etf.baseDays ?? 5}日同进度均额
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

/* ---------------- 分组 ---------------- */

function GroupBlock({ group, rankOffset }: { group: NationalTeamGroup; rankOffset: number }) {
  const badge = GROUP_STATE_BADGE[group.state] || GROUP_STATE_BADGE['数据不足'];
  return (
    <div className="mb-1">
      {/* 组头：与轮动页"趋势排名 (N)"标题同级的小节标题 */}
      <div className="flex items-center gap-2 mb-2 px-1">
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${badge}`}>{group.index}</span>
        {group.alertCount > 0 && (
          <span className="text-xs text-orange-600 font-medium">
            {group.alertCount}/{group.totalCount} 放量
          </span>
        )}
        <span className="text-xs text-slate-400">({group.totalCount})</span>
        <span className="text-xs text-slate-400 ml-auto tabular-nums">
          均量比 <span className="font-semibold text-slate-600">{ratioText(group.avgRatio)}</span>
        </span>
      </div>
      {group.etfs.map((e, i) => (
        <EtfCard key={e.symbol} etf={e} rank={rankOffset + i + 1} />
      ))}
    </div>
  );
}

/* ---------------- 主组件：汇总头 + 分组卡片列表 ---------------- */

export default function NationalTeamCard({ data }: { data: Data }) {
  const { summary, groups, marketStatus, timestamp, shareAsOf, shareAsOfMin, shareDays } = data;

  return (
    <div>
      {/* 更新时间（放量状态与规则说明已在页面顶部汇总卡里，这里不重复） */}
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-sm font-medium text-slate-500">
          放量 {summary.alertCount + summary.strongCount} / {summary.totalCount} · {marketStatus}
        </span>
        <span className="text-xs text-slate-400 tabular-nums" title={timestamp}>
          {timestamp.slice(5, 16)} 更新
        </span>
      </div>

      {/* 一级市场合计：全样本当日与近 5 日净申赎 */}
      {summary.netTotal !== null && summary.netTotal !== undefined && (
        <div className="mb-3 mx-1 rounded-lg bg-gradient-to-r from-slate-50 to-white ring-1 ring-slate-200 px-3 py-2">
          <div className="flex items-center flex-wrap gap-x-3 gap-y-1">
            <span className="text-[10px] font-medium text-slate-500">一级市场合计净申购</span>
            <span className={`text-sm font-bold tabular-nums ${netCls(summary.netTotal)}`}>
              {netText(summary.netTotal)}
            </span>
            {summary.netSharesTotal !== null && summary.netSharesTotal !== undefined && (
              <span className="text-[10px] text-slate-400 tabular-nums">
                {netSharesText(summary.netSharesTotal)}
              </span>
            )}
            {summary.netTotal5 !== null && (
              <span className="text-[10px] text-slate-400">
                近5日 <span className={`font-semibold tabular-nums ${netCls(summary.netTotal5)}`}>{netText(summary.netTotal5)}</span>
                {summary.netSharesTotal5 !== null && summary.netSharesTotal5 !== undefined && (
                  <span className="tabular-nums"> / {netSharesText(summary.netSharesTotal5)}</span>
                )}
              </span>
            )}
            <span className="text-[10px] text-slate-400">
              净申购 {summary.netInflowCount} / 净赎回 {summary.netOutflowCount}
            </span>
            <span className="ml-auto text-[9px] text-slate-400 tabular-nums" title={`覆盖 ${summary.netCount} 只`}>
              {asOfRange(shareAsOfMin, shareAsOf)}
              {shareDays ? ` · 累积 ${shareDays} 日` : ''}
            </span>
          </div>
        </div>
      )}

      {groups.map((g, gi) => {
        const rankOffset = groups.slice(0, gi).reduce((n, x) => n + x.etfs.length, 0);
        return <GroupBlock key={g.index} group={g} rankOffset={rankOffset} />;
      })}
    </div>
  );
}
