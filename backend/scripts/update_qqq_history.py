#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQQ 历史日线自动更新模块

设计沿用趋势轮动策略（calculate_momentum_joinquant.py）的成熟模式：
    1. 数据源：腾讯前复权日线接口（A股/ETF 同源，美股用 usQQQ.OQ / usTQQQ.OQ）
    2. 按天缓存：当天已成功更新过就不再重复请求
    3. 增量追加：只把缺的交易日补进 qqq_history.json，不重建整个文件
    4. 失败降级：任何异常都不抛给调用方，返回结构化结果，策略继续用旧数据跑

用法：
    python3 update_qqq_history.py            # 增量更新
    python3 update_qqq_history.py --force    # 忽略当日缓存，强制重新拉取
    python3 update_qqq_history.py --audit    # 只体检不写入

被 calculate_ma200_trend.py 在每次请求时调用（有当日缓存，实际开销极小）。
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(BASE_DIR, 'qqq_history.json')
UPDATE_META_FILE = os.path.join(BASE_DIR, 'qqq_history_meta.json')

# 腾讯前复权日线：美股需带 .OQ（纳斯达克）后缀，不带后缀只会返回首尾两条
TENCENT_KLINE = 'http://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get'
SYMBOLS = {'qqq': 'usQQQ.OQ', 'tqqq': 'usTQQQ.OQ'}

# 一次拉取的最大条数（实测 600 可稳定返回，足够覆盖 200 日均线 + 冗余校验）
FETCH_COUNT = 600
# 历史文件中至少保留的条数，低于此值视为数据异常
MIN_KEEP = 400
# 距最近交易日超过该天数则告警（美股周末 + 假期，5 个自然日足够）
STALE_DAYS = 5


def _load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, payload):
    """原子写入，避免中途失败把文件写坏"""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def fetch_kline(symbol, count=FETCH_COUNT, retries=2):
    """拉取腾讯前复权日线，返回 [(day, close), ...] 升序；失败返回 []"""
    for attempt in range(retries + 1):
        try:
            r = requests.get(
                TENCENT_KLINE,
                params={'param': f'{symbol},day,,,{count},qfq'},
                timeout=15,
                headers={'User-Agent': 'Mozilla/5.0'},
            )
            if r.status_code != 200:
                raise RuntimeError(f'HTTP {r.status_code}')
            block = r.json().get('data', {}).get(symbol, {})
            # 美股返回 day；部分标的是 qfqday（前复权）
            rows = block.get('qfqday') or block.get('day') or []
            out = []
            for row in rows:
                if len(row) < 3:
                    continue
                try:
                    out.append((row[0], float(row[2])))   # [日期, 开, 收, 高, 低, 量]
                except (ValueError, TypeError):
                    continue
            if out:
                out.sort(key=lambda x: x[0])
                return out
            raise RuntimeError('返回数据为空')
        except Exception as e:
            if attempt >= retries:
                print(f'[update_qqq] 拉取 {symbol} 失败: {e}', file=sys.stderr)
                return []
            time.sleep(1.5 * (attempt + 1))
    return []


def update(force=False, audit_only=False):
    """
    增量更新 qqq_history.json。

    返回 dict：
        updated      是否真的写入
        added        新增的交易日数
        historyUpdated 文件里最新的交易日
        stale        最新交易日距今是否过旧
        staleDays    距今天数
        error        错误信息（成功为 None）
    """
    payload = _load_json(HISTORY_FILE, {})
    hist = payload.get('data', [])
    if not hist:
        return {'updated': False, 'added': 0, 'historyUpdated': '',
                'stale': True, 'staleDays': None, 'error': '历史文件为空或缺失'}

    meta = _load_json(UPDATE_META_FILE, {})
    today = datetime.now().strftime('%Y-%m-%d')

    # 当日已成功更新过 → 直接复用，避免每次请求都打接口
    if not force and meta.get('lastRunDate') == today and meta.get('lastResult') == 'ok':
        last_day = hist[-1]['day']
        return {'updated': False, 'added': 0, 'historyUpdated': last_day,
                'stale': _is_stale(last_day), 'staleDays': _age_days(last_day),
                'error': None, 'cached': True}

    if audit_only:
        last_day = hist[-1]['day']
        return {'updated': False, 'added': 0, 'historyUpdated': last_day,
                'stale': _is_stale(last_day), 'staleDays': _age_days(last_day),
                'error': None, 'audit': True}

    result = {'updated': False, 'added': 0, 'historyUpdated': hist[-1]['day'],
              'stale': False, 'staleDays': None, 'error': None}

    try:
        klines = fetch_kline(SYMBOLS['qqq'])
        if not klines:
            raise RuntimeError('QQQ 日线拉取失败，保留原有历史数据')

        # 校验：新数据的收盘序列必须与旧数据在重叠区间内一致，否则拒绝写入
        # （防止接口口径变化/复权基准调整污染历史）
        # 判定用重叠样本的自身比例，而不是全历史比例 —— 否则少量污染会被稀释掉
        old_map = {it['day']: it['close'] for it in hist}
        overlap = [(d, c) for d, c in klines if d in old_map]
        if len(overlap) >= 5:
            bad = [(d, old_map[d], c) for d, c in overlap if abs(old_map[d] - c) > 0.02]
            if len(bad) > 0:
                raise RuntimeError(
                    f'数据校验未通过：{len(bad)}/{len(overlap)} 个重叠交易日收盘价偏差过大，'
                    f'拒绝写入以避免污染历史')

        last_day = hist[-1]['day']
        new_rows = [{'day': d, 'close': c} for d, c in klines if d > last_day]

        if new_rows:
            hist.extend(new_rows)
            # 安全上限：只在异常膨胀时裁剪，正常增量绝不删除历史
            if len(hist) > 8000:
                hist = hist[-8000:]
            payload['data'] = hist
            payload['updated'] = hist[-1]['day']
            _save_json(HISTORY_FILE, payload)
            result['updated'] = True
            result['added'] = len(new_rows)

        result['historyUpdated'] = hist[-1]['day']
        result['stale'] = _is_stale(hist[-1]['day'])
        result['staleDays'] = _age_days(hist[-1]['day'])

        meta = {'lastRunDate': today, 'lastResult': 'ok',
                'lastRunAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'historyUpdated': hist[-1]['day'], 'added': result['added']}
        _save_json(UPDATE_META_FILE, meta)
        return result

    except Exception as e:
        result['error'] = str(e)
        result['stale'] = _is_stale(hist[-1]['day'])
        result['staleDays'] = _age_days(hist[-1]['day'])
        # 失败也记录，避免同一天内反复重试打爆接口；下次请求会因 lastResult!=ok 再试
        _save_json(UPDATE_META_FILE, {
            'lastRunDate': today, 'lastResult': 'fail',
            'lastRunAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': str(e)[:300]})
        return result


def _age_days(day):
    """最新交易日距今天数（自然日）"""
    try:
        d = datetime.strptime(day, '%Y-%m-%d')
        return (datetime.now() - d).days
    except Exception:
        return None


def _is_stale(day):
    n = _age_days(day)
    return True if n is None else n > STALE_DAYS


if __name__ == '__main__':
    force = '--force' in sys.argv
    audit = '--audit' in sys.argv
    r = update(force=force, audit_only=audit)
    print(json.dumps(r, ensure_ascii=False, indent=2))
