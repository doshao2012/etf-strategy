#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
美股 QQQ/TQQQ 三轨 MA200 策略

规则（只看一个数）：
    ratio = QQQ 价格 / QQQ 的 MA200（200 日收盘均线）

    空仓时：ratio >= 1.14 → 持 QQQ ｜ ratio >= 1.01 → 持 TQQQ ｜ 否则继续空仓
    持TQQQ：ratio <  1.01 → 清仓    ｜ ratio >= 1.14 → 换 QQQ  ｜ 否则不动
    持 QQQ：ratio <  1.01 → 清仓    ｜ ratio <  1.06 → 换 TQQQ ｜ 否则不动

数据来源：
    - 历史日线：本地 qqq_history.json（QQQ 复权收盘，含 3900+ 交易日，够算 MA200）
    - 实时价格：新浪财经 gb_ 接口（免费、无需 key、含盘前盘后）
        https://hq.sinajs.cn/list=gb_qqq,gb_tqqq  需带 Referer

所有阈值集中在此文件顶部，便于调参。
"""
import sys
import os
import json
import re
import time
from datetime import datetime

import requests

# ============== 策略参数 ==============
LOWER_LINE = 1.01    # 下轨：跌破清仓 / 站上买入 TQQQ
UPPER_ENTRY = 1.14   # 上轨（高）：涨破此线换成 QQQ
UPPER_EXIT = 1.06    # 上轨（低）：从 QQQ 回落到此线以下换回 TQQQ
MA_PERIOD = 200      # 均线周期

# 历史数据文件
HISTORY_FILE = os.path.join(os.path.dirname(__file__), '..', 'qqq_history.json')

# 实时行情数据源（按顺序尝试，第一个成功即用）

# 源 1：新浪（境内网络通常最快，但部分机房 IP 会被吊住 5 秒后断开）
SINA_URL = 'https://hq.sinajs.cn/list=gb_qqq,gb_tqqq'
SINA_HEADERS = {
    'Referer': 'https://finance.sina.com.cn',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# 源 2：腾讯（美股用 usQQQ / usTQQQ，注意不带 .OQ 后缀）
# 字段：[1]名称 [2]代码 [3]当前价 [30]报价时间 [32]涨跌幅%
TENCENT_URL = 'https://qt.gtimg.cn/q=usQQQ,usTQQQ'
TENCENT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# 超时设置：连接 1.5s / 读取 2s。
# 实测（线上日志）新浪会「先吊住 5 秒再断开」，原来的 (3, 5) 等于每次白白干等 5 秒；
# 这里压短，不通就立刻换下一个源。
CONNECT_TIMEOUT = 1.5
READ_TIMEOUT = 2.0

# 失败冷却：某个源刚失败过，这段时间内不再尝试，直接用下一个源
SOURCE_COOLDOWN = 180
_SOURCE_FAIL_TS = {}

# 状态常量
STATE_EMPTY = -1
STATE_TQQQ = 1
STATE_QQQ = 2

STATE_NAME = {
    STATE_EMPTY: '空仓',
    STATE_TQQQ: '持 TQQQ',
    STATE_QQQ: '持 QQQ',
}


def load_history():
    """加载 QQQ 历史收盘价"""
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        data = payload.get('data', [])
        return [{'day': it['day'], 'close': float(it['close'])} for it in data], payload.get('updated', '')
    except Exception as e:
        print(f"加载历史数据失败: {e}", file=sys.stderr)
        return [], ''


def _empty_result():
    return {
        'qqq': None, 'tqqq': None,
        'qqq_change_pct': None, 'tqqq_change_pct': None,
        'quote_time': '',
        'is_after_hours': False,
    }


def _in_cooldown(name):
    ts = _SOURCE_FAIL_TS.get(name)
    return bool(ts) and (time.time() - ts) < SOURCE_COOLDOWN


def _fetch_sina():
    """新浪源。返回 (解析结果 dict, 失败原因 or None)"""
    resp = requests.get(SINA_URL, headers=SINA_HEADERS,
                        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    resp.encoding = 'gbk'
    text = resp.text
    result = _empty_result()

    # 关键校验：被拒绝时新浪会返回极短的空响应（实测 9 字节），
    # 这种"200 但没数据"会被当成成功，导致前端拿不到价格还不报错。
    found = 0
    for symbol in ('qqq', 'tqqq'):
        match = re.search(r'var hq_str_gb_%s="([^"]*)"' % symbol, text)
        if not match:
            continue
        fields = match.group(1).split(',')
        if len(fields) < 36:
            continue
        try:
            last = float(fields[1])            # 最新价（盘后时段为盘后价）
            change_pct = float(fields[2])      # 涨跌幅%
            regular_close = float(fields[21])  # 常规时段收盘
            after_chg_pct = float(fields[23])  # 盘后涨跌幅
            close_time = fields[25]            # 常规收盘时间(EDT)，如 Oct 16 04:00PM EDT
            result[symbol] = last
            result['%s_change_pct' % symbol] = round(change_pct, 2)
            result.setdefault('regular_close', {})[symbol] = regular_close
            result.setdefault('after_chg_pct', {})[symbol] = round(after_chg_pct, 2)
            if not result['quote_time']:
                # 新浪给的是北京时间
                result['quote_time'] = f"{fields[3]} (北京)"
            # 若盘后涨跌幅不为 0 且常规已收盘，视为盘后时段
            if 'PM' in close_time and after_chg_pct != 0:
                result['is_after_hours'] = True
            found += 1
        except (ValueError, IndexError) as e:
            print(f"解析 {symbol} 行情失败: {e}", file=sys.stderr)

    if found == 0:
        return None, f'响应无有效数据（{len(text)}B）'
    return result, None


def _fetch_tencent():
    """腾讯源。美股用 usQQQ / usTQQQ（不带 .OQ 后缀）。

    字段：[1]名称 [2]代码 [3]当前价 [30]报价时间(北京时间) [32]涨跌幅%
    """
    resp = requests.get(TENCENT_URL, headers=TENCENT_HEADERS,
                        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    text = resp.content.decode('gbk', errors='ignore')
    result = _empty_result()

    found = 0
    for key, symbol in (('usQQQ', 'qqq'), ('usTQQQ', 'tqqq')):
        match = re.search(r'v_%s="([^"]*)"' % key, text)
        if not match:
            continue
        fields = match.group(1).split('~')
        if len(fields) < 33:
            continue
        try:
            last = float(fields[3])
            change_pct = float(fields[32])
            result[symbol] = last
            result['%s_change_pct' % symbol] = round(change_pct, 2)
            if not result['quote_time']:
                # 腾讯给的是美东收盘时间（如 2026-10-16 16:00:02），
                # 新浪给的是北京时间。这里统一加标注，避免前端显示歧义。
                result['quote_time'] = f"{fields[30]} (美东)"
            found += 1
        except (ValueError, IndexError) as e:
            print(f"解析腾讯 {key} 失败: {e}", file=sys.stderr)

    if found == 0:
        return None, f'响应无有效数据（{len(text)}B）'
    return result, None


# 数据源优先级：新浪优先（境内通常最快），失败立即换腾讯
SOURCES = (('新浪', _fetch_sina), ('腾讯', _fetch_tencent))


def fetch_realtime():
    """获取 QQQ / TQQQ 实时价格。

    多源回退 + 短超时 + 失败冷却：
      - 线上实测新浪会把请求吊住 5 秒再断开（read timeout），
        原来 (3,5) 的超时等于每次白等 5 秒，页面自然卡 5 秒；
      - 现在每个源最多等 1.5+2 秒，不通立刻换下一个；
      - 失败过的源冷却 3 分钟，避免每次切换 tab 都先撞一次墙。
    """
    t_all = time.time()
    for name, fn in SOURCES:
        if _in_cooldown(name):
            print(f"[MA200计时] {name} 冷却中，跳过", file=sys.stderr, flush=True)
            continue
        t0 = time.time()
        try:
            result, err = fn()
            el = time.time() - t0
            if err:
                _SOURCE_FAIL_TS[name] = time.time()
                print(f"[MA200计时] {name} 无效 {el:.3f}s: {err}（冷却 {SOURCE_COOLDOWN}s）",
                      file=sys.stderr, flush=True)
                continue
            print(f"[MA200计时] {name} 成功 {el:.3f}s "
                  f"QQQ={result.get('qqq')} TQQQ={result.get('tqqq')}",
                  file=sys.stderr, flush=True)
            result['source'] = name
            return result
        except Exception as e:
            el = time.time() - t0
            _SOURCE_FAIL_TS[name] = time.time()
            print(f"[MA200计时] {name} 失败 {el:.3f}s: {e}（冷却 {SOURCE_COOLDOWN}s）",
                  file=sys.stderr, flush=True)

    print(f"[MA200计时] 所有数据源均不可用，总耗时 {time.time()-t_all:.3f}s",
          file=sys.stderr, flush=True)
    return _empty_result()
    return result


def calc_ma(values, period):
    """简单移动平均（末尾 period 个）"""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def run_state_machine(history, current_price=None):
    """
    跑完整状态机，返回每日状态序列与当前状态。
    若提供 current_price，则用它替换/追加最后一天的价格，得到"实时判断"。
    """
    closes = [it['close'] for it in history]
    days = [it['day'] for it in history]

    # 用实时价覆盖最后一天（同一天收盘后覆盖，或盘中估值）
    today = datetime.now().strftime('%Y-%m-%d')
    if current_price:
        if days and days[-1] == today:
            closes[-1] = current_price
        elif not days or days[-1] < today:
            days.append(today)
            closes.append(current_price)

    n = len(closes)
    states = [STATE_EMPTY] * n
    st = STATE_EMPTY
    for i in range(n):
        if i + 1 < MA_PERIOD:
            states[i] = st
            continue
        ma = sum(closes[i + 1 - MA_PERIOD:i + 1]) / MA_PERIOD
        r = closes[i] / ma
        if st == STATE_EMPTY:
            if r >= UPPER_ENTRY:
                st = STATE_QQQ
            elif r >= LOWER_LINE:
                st = STATE_TQQQ
        else:
            if r < LOWER_LINE:
                st = STATE_EMPTY
            elif st == STATE_TQQQ:
                if r >= UPPER_ENTRY:
                    st = STATE_QQQ
            elif st == STATE_QQQ:
                if r < UPPER_EXIT:
                    st = STATE_TQQQ
        states[i] = st

    return days, closes, states


def build_advice(prev_state, state_now, ratio):
    """根据状态变化生成操作建议"""
    if state_now == prev_state:
        action = '持有' if state_now != STATE_EMPTY else '观望'
        target = STATE_NAME[state_now]
        detail = '维持当前仓位，无需操作'
    else:
        target = STATE_NAME[state_now]
        if state_now == STATE_EMPTY:
            action = '卖出'
            detail = f'ratio {ratio:.4f} 跌破下轨 {LOWER_LINE}，清空仓位'
        elif prev_state == STATE_EMPTY:
            action = '买入'
            detail = (f'ratio {ratio:.4f} 站上下轨 {LOWER_LINE}，买入 TQQQ'
                      if state_now == STATE_TQQQ else
                      f'ratio {ratio:.4f} 直接冲上 {UPPER_ENTRY}，买入 QQQ')
        elif state_now == STATE_QQQ:
            action = '换仓'
            detail = f'ratio {ratio:.4f} 涨破 {UPPER_ENTRY}，TQQQ 换成 QQQ（降杠杆防守）'
        else:
            action = '换仓'
            detail = f'ratio {ratio:.4f} 回落至 {UPPER_EXIT} 以下，QQQ 换回 TQQQ（加杠杆）'
    return action, target, detail


def distance_to(ratio, line):
    """当前值距离某条线的百分比"""
    return round((ratio - line) / line * 100, 2)


def main():
    # 历史日线同步：默认只读缓存状态，不在请求路径上联网拉数据。
    # 原因 —— 前端每次切 tab 都会调这个脚本，如果在这里联网，
    # 一旦数据源不通就要等满超时（腾讯 5s×2 重试 + 新浪 8s），页面会卡十几秒。
    # 真正的更新由后端后台线程（每 6 小时一次）和 update_qqq_history.py 负责。
    # 需要立即同步时传 --sync。
    _T = time.time()
    update_info = {}
    try:
        from update_qqq_history import update as update_history
        if '--sync' in sys.argv:
            update_info = update_history(force=True)
        else:
            # 只读取新鲜度，不发网络请求
            from update_qqq_history import audit_only_status
            update_info = audit_only_status()
        if update_info.get('error'):
            print(f"历史数据同步提示: {update_info['error']}", file=sys.stderr)
    except Exception as e:
        print(f"历史数据状态读取异常（继续使用现有数据）: {e}", file=sys.stderr)
    print(f"[MA200计时] 历史状态检查 {time.time()-_T:.3f}s", file=sys.stderr, flush=True)
    _T = time.time()

    history, hist_updated = load_history()
    print(f"[MA200计时] 读历史文件 {time.time()-_T:.3f}s ({len(history)} 条)", file=sys.stderr, flush=True)
    _T = time.time()
    if len(history) < MA_PERIOD:
        print(json.dumps({
            'code': 500,
            'message': f'历史数据不足（{len(history)} < {MA_PERIOD}）',
            'data': None,
        }, ensure_ascii=False))
        return

    rt = fetch_realtime()
    print(f"[MA200计时] 实时行情 {time.time()-_T:.3f}s", file=sys.stderr, flush=True)
    _T = time.time()
    current_price = rt.get('qqq')
    tqqq_price = rt.get('tqqq')

    # 历史收盘（不含实时）算 MA200
    hist_closes = [it['close'] for it in history]
    ma200_hist = calc_ma(hist_closes, MA_PERIOD)

    # 用实时价跑一遍状态机
    days, closes, states = run_state_machine(history, current_price)
    state_now = states[-1]
    state_prev = states[-2] if len(states) > 1 else state_now

    # 实时 MA200（若实时价已并入）
    ma200_live = calc_ma(closes, MA_PERIOD)
    price_now = closes[-1]
    ratio = price_now / ma200_live if ma200_live else None

    # 若实时价缺失，退回用历史最后一天
    if current_price is None:
        price_now = hist_closes[-1]
        ma200_live = ma200_hist
        ratio = price_now / ma200_live if ma200_live else None

    action, target, detail = build_advice(state_prev, state_now, ratio or 0)

    # 计算各条轨道的具体价格位置（便于实操挂单）
    lines = {}
    if ma200_live:
        lines = {
            'lower': {'level': LOWER_LINE, 'price': round(ma200_live * LOWER_LINE, 2),
                      'distancePct': distance_to(ratio, LOWER_LINE)},
            'upperExit': {'level': UPPER_EXIT, 'price': round(ma200_live * UPPER_EXIT, 2),
                          'distancePct': distance_to(ratio, UPPER_EXIT)},
            'upperEntry': {'level': UPPER_ENTRY, 'price': round(ma200_live * UPPER_ENTRY, 2),
                           'distancePct': distance_to(ratio, UPPER_ENTRY)},
        }

    # 历史状态序列（最近 120 个交易日，用于前端画仓位带）
    recent = min(120, len(days))
    state_history = [
        {'day': days[i], 'state': states[i], 'position': STATE_NAME[states[i]]}
        for i in range(len(days) - recent, len(days))
    ]

    output = {
        'code': 200,
        'message': 'success',
        'data': {
            'symbol': {
                'qqq': {
                    'price': round(price_now, 2),
                    'changePct': rt.get('qqq_change_pct'),
                    'ma200': round(ma200_live, 2) if ma200_live else None,
                    'ratio': round(ratio, 4) if ratio else None,
                },
                'tqqq': {
                    'price': round(tqqq_price, 2) if tqqq_price else None,
                    'changePct': rt.get('tqqq_change_pct'),
                },
            },
            'state': {
                'current': state_now,
                'currentName': STATE_NAME[state_now],
                'previous': state_prev,
                'previousName': STATE_NAME[state_prev],
                'changed': state_now != state_prev,
            },
            'advice': {
                'action': action,
                'target': target,
                'detail': detail,
            },
            'lines': lines,
            'params': {
                'lowerLine': LOWER_LINE,
                'upperEntry': UPPER_ENTRY,
                'upperExit': UPPER_EXIT,
                'maPeriod': MA_PERIOD,
            },
            'stateHistory': state_history,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'quoteTime': rt.get('quote_time', ''),
            'isAfterHours': rt.get('is_after_hours', False),
            'dataSource': f"{rt.get('source', '无')}实时价 + 本地历史日线",
            'historyUpdated': hist_updated,
            'realtimeOk': current_price is not None,
            # 历史数据新鲜度：供前端判断是否需要提示"数据过期"
            'historyStale': bool(update_info.get('stale')),
            'historyAgeDays': update_info.get('staleDays'),
            'historySyncOk': update_info.get('error') is None,
            'historySyncError': update_info.get('error'),
        },
    }

    print(f"[MA200计时] 计算 {time.time()-_T:.3f}s", file=sys.stderr, flush=True)
    _T = time.time()
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"[MA200计时] 输出 {time.time()-_T:.3f}s", file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
