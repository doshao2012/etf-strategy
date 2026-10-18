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
from datetime import datetime

import requests

# ============== 策略参数 ==============
LOWER_LINE = 1.01    # 下轨：跌破清仓 / 站上买入 TQQQ
UPPER_ENTRY = 1.14   # 上轨（高）：涨破此线换成 QQQ
UPPER_EXIT = 1.06    # 上轨（低）：从 QQQ 回落到此线以下换回 TQQQ
MA_PERIOD = 200      # 均线周期

# 历史数据文件
HISTORY_FILE = os.path.join(os.path.dirname(__file__), '..', 'qqq_history.json')

# 新浪实时行情（美股代码前缀 gb_）
SINA_URL = 'https://hq.sinajs.cn/list=gb_qqq,gb_tqqq'
SINA_HEADERS = {
    'Referer': 'https://finance.sina.com.cn',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

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


def fetch_realtime():
    """获取 QQQ / TQQQ 实时价格（新浪接口，GBK 编码）"""
    result = {
        'qqq': None, 'tqqq': None,
        'qqq_change_pct': None, 'tqqq_change_pct': None,
        'quote_time': '',
        'is_after_hours': False,
    }
    try:
        resp = requests.get(SINA_URL, headers=SINA_HEADERS, timeout=8)
        resp.encoding = 'gbk'
        text = resp.text
    except Exception as e:
        print(f"获取实时行情失败: {e}", file=sys.stderr)
        return result

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
                result['quote_time'] = fields[3]
            # 若盘后涨跌幅不为 0 且常规已收盘，视为盘后时段
            if 'PM' in close_time and after_chg_pct != 0:
                result['is_after_hours'] = True
        except (ValueError, IndexError) as e:
            print(f"解析 {symbol} 行情失败: {e}", file=sys.stderr)
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
    history, hist_updated = load_history()
    if len(history) < MA_PERIOD:
        print(json.dumps({
            'code': 500,
            'message': f'历史数据不足（{len(history)} < {MA_PERIOD}）',
            'data': None,
        }, ensure_ascii=False))
        return

    rt = fetch_realtime()
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
            'dataSource': '新浪财经实时价 + 本地历史日线',
            'historyUpdated': hist_updated,
            'realtimeOk': current_price is not None,
        },
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
