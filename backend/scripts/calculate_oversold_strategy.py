"""
策略2：ETF超跌策略（危机模式）
算法：计算当前价格与ENE下轨的距离，列出最接近下轨的top10超跌ETF
ENE下轨 = MA10 * (1 - 0.09)

改进方案：
1. 先获取所有场内ETF的前一日成交额
2. 筛选成交额超过1亿的ETF
3. 同类ETF合并（只保留一只）
4. 再进行详细超跌分析
"""

import sys
import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# 全局变量：是否打印调试信息
VERBOSE = False

# 配置
MIN_MONEY_W = 10000  # 最小日均成交额（万元）- 1亿
LOOKBACK_DAYS = 20  # 成交额统计天数
MA_PERIOD = 10  # MA周期
ENE_LOWER_PCT = 0.09  # 下轨偏离度 9%

# 缓存文件路径
VOLUME_CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'volume_cache.json')
HISTORY_CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'history_cache.json')
KLINE_CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'kline_cache.json')
MAX_WORKERS = 20  # 并行请求数

# 内存缓存：K线数据（filter_by_volume 时预取，calculate_oversold_analysis 复用）
_kline_cache = {}


def load_kline_cache() -> Dict:
    """加载K线缓存"""
    try:
        if os.path.exists(KLINE_CACHE_FILE):
            with open(KLINE_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            cache_date = cache.get('_date', '')
            today = datetime.now().strftime('%Y-%m-%d')
            if cache_date == today:
                log(f"K线缓存有效: {len(cache)} 只ETF")
                return cache
            else:
                log("K线缓存过期，重新获取")
    except Exception:
        pass
    return {'_date': datetime.now().strftime('%Y-%m-%d')}


def save_kline_cache(cache: Dict):
    """保存K线缓存"""
    try:
        with open(KLINE_CACHE_FILE, 'w') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass

def log(message: str):
    """打印日志（仅在VERBOSE模式下）"""
    if VERBOSE:
        if not is_quiet:
                    print(message, file=sys.stderr)


def get_all_etf_list() -> List[Dict]:
    """
    获取所有场内ETF列表（主流ETF）
    包含宽基、行业、海外、商品等
    """
    # 完整的ETF列表（100+只）
    all_etfs = [
        # ==================== 宽基指数ETF ====================
        {'code': '510300', 'name': '沪深300ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '510500', 'name': '中证500ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '510050', 'name': '上证50ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '159915', 'name': '创业板ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '588000', 'name': '科创50ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '588080', 'name': '科创50ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '512100', 'name': '中证1000ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '512210', 'name': '中证1000ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '563300', 'name': '中证2000ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '159901', 'name': '深100ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '159919', 'name': '沪深300ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '159922', 'name': '中证500ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '510330', 'name': '沪深300ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '159690', 'name': '创业板ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '159781', 'name': '创业板ETF', 'market': 'sz', 'category': '宽基'},
        {'code': '588200', 'name': '科创50ETF', 'market': 'sh', 'category': '宽基'},
        {'code': '588350', 'name': '科创50ETF', 'market': 'sh', 'category': '宽基'},

        # ==================== 科技类 ====================
        {'code': '512480', 'name': '半导体ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159813', 'name': '半导体芯片ETF', 'market': 'sz', 'category': '科技'},
        {'code': '159995', 'name': '芯片ETF', 'market': 'sz', 'category': '科技'},
        {'code': '159799', 'name': '消费电子ETF', 'market': 'sz', 'category': '科技'},
        {'code': '159861', 'name': '消费电子ETF', 'market': 'sz', 'category': '科技'},
        {'code': '515050', 'name': '5GETF', 'market': 'sh', 'category': '科技'},
        {'code': '515000', 'name': '5GETF', 'market': 'sh', 'category': '科技'},
        {'code': '159511', 'name': '5GETF', 'market': 'sz', 'category': '科技'},
        {'code': '512720', 'name': '计算机ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159852', 'name': '计算机ETF', 'market': 'sz', 'category': '科技'},
        {'code': '515230', 'name': '软件ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159851', 'name': '软件ETF', 'market': 'sz', 'category': '科技'},
        {'code': '516510', 'name': '云计算ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159865', 'name': '云计算ETF', 'market': 'sz', 'category': '科技'},
        {'code': '515040', 'name': '通信ETF', 'market': 'sh', 'category': '科技'},
        {'code': '515880', 'name': '通信ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159511', 'name': '人工智能ETF', 'market': 'sz', 'category': '科技'},
        {'code': '515070', 'name': '人工智能ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159819', 'name': '人工智能ETF', 'market': 'sz', 'category': '科技'},
        {'code': '159660', 'name': '新能源车ETF', 'market': 'sz', 'category': '科技'},
        {'code': '515030', 'name': '新能源车ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159806', 'name': '新能源车ETF', 'market': 'sz', 'category': '科技'},
        {'code': '516390', 'name': '新能源车ETF', 'market': 'sh', 'category': '科技'},
        {'code': '159845', 'name': '电池ETF', 'market': 'sz', 'category': '科技'},
        {'code': '561160', 'name': '电池ETF', 'market': 'sh', 'category': '科技'},

        # ==================== 新能源类 ====================
        {'code': '515790', 'name': '光伏ETF', 'market': 'sh', 'category': '新能源'},
        {'code': '159857', 'name': '光伏ETF', 'market': 'sz', 'category': '新能源'},
        {'code': '516160', 'name': '新能源ETF', 'market': 'sh', 'category': '新能源'},
        {'code': '159875', 'name': '新能源ETF', 'market': 'sz', 'category': '新能源'},
        {'code': '159862', 'name': '光伏龙头ETF', 'market': 'sz', 'category': '新能源'},
        {'code': '562800', 'name': '光伏产业ETF', 'market': 'sh', 'category': '新能源'},
        {'code': '516090', 'name': '双碳ETF', 'market': 'sh', 'category': '新能源'},
        {'code': '560850', 'name': '碳中和ETF', 'market': 'sh', 'category': '新能源'},

        # ==================== 消费类 ====================
        {'code': '512690', 'name': '酒ETF', 'market': 'sh', 'category': '消费'},
        {'code': '159739', 'name': '酒ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159928', 'name': '消费ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159972', 'name': '消费ETF', 'market': 'sz', 'category': '消费'},
        {'code': '515170', 'name': '食品饮料ETF', 'market': 'sh', 'category': '消费'},
        {'code': '159736', 'name': '食品饮料ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159996', 'name': '家电ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159799', 'name': '消费电子ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159967', 'name': '消费电子ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159883', 'name': '家电龙头ETF', 'market': 'sz', 'category': '消费'},
        {'code': '159766', 'name': '旅游ETF', 'market': 'sz', 'category': '消费'},

        # ==================== 医药类 ====================
        {'code': '513120', 'name': '创新药ETF', 'market': 'sh', 'category': '医药'},
        {'code': '159783', 'name': '创新药ETF', 'market': 'sz', 'category': '医药'},
        {'code': '513000', 'name': '创新药ETF', 'market': 'sh', 'category': '医药'},
        {'code': '512010', 'name': '医药ETF', 'market': 'sh', 'category': '医药'},
        {'code': '159938', 'name': '医药卫生ETF', 'market': 'sz', 'category': '医药'},
        {'code': '159729', 'name': '医药ETF', 'market': 'sz', 'category': '医药'},
        {'code': '512010', 'name': '医药ETF', 'market': 'sh', 'category': '医药'},
        {'code': '159729', 'name': '医药ETF', 'market': 'sz', 'category': '医药'},
        {'code': '159883', 'name': '医疗器械ETF', 'market': 'sz', 'category': '医药'},
        {'code': '159765', 'name': '生物科技ETF', 'market': 'sz', 'category': '医药'},
        {'code': '512760', 'name': 'CXO ETF', 'market': 'sh', 'category': '医药'},
        {'code': '159658', 'name': '医疗ETF', 'market': 'sz', 'category': '医药'},
        {'code': '501007', 'name': '卫生ETF', 'market': 'sh', 'category': '医药'},

        # ==================== 金融类 ====================
        {'code': '512000', 'name': '券商ETF', 'market': 'sh', 'category': '金融'},
        {'code': '159841', 'name': '券商ETF', 'market': 'sz', 'category': '金融'},
        {'code': '512880', 'name': '证券ETF', 'market': 'sh', 'category': '金融'},
        {'code': '512570', 'name': '证券公司ETF', 'market': 'sh', 'category': '金融'},
        {'code': '159849', 'name': '证券ETF', 'market': 'sz', 'category': '金融'},
        {'code': '512800', 'name': '银行ETF', 'market': 'sh', 'category': '金融'},
        {'code': '159697', 'name': '银行ETF', 'market': 'sz', 'category': '金融'},
        {'code': '159688', 'name': '银行ETF', 'market': 'sz', 'category': '金融'},
        {'code': '159951', 'name': '银行ETF', 'market': 'sz', 'category': '金融'},
        {'code': '512830', 'name': '银行ETF', 'market': 'sh', 'category': '金融'},
        {'code': '515230', 'name': '银行ETF', 'market': 'sh', 'category': '金融'},

        # ==================== 周期类 ====================
        {'code': '515220', 'name': '煤炭ETF', 'market': 'sh', 'category': '周期'},
        {'code': '515080', 'name': '煤炭ETF', 'market': 'sh', 'category': '周期'},
        {'code': '159865', 'name': '煤炭ETF', 'market': 'sz', 'category': '周期'},
        {'code': '515210', 'name': '钢铁ETF', 'market': 'sh', 'category': '周期'},
        {'code': '515230', 'name': '钢铁ETF', 'market': 'sh', 'category': '周期'},
        {'code': '516790', 'name': '有色金属ETF', 'market': 'sh', 'category': '周期'},
        {'code': '159871', 'name': '有色金属ETF', 'market': 'sz', 'category': '周期'},
        {'code': '159873', 'name': '有色金属ETF', 'market': 'sz', 'category': '周期'},
        {'code': '159981', 'name': '化工ETF', 'market': 'sz', 'category': '周期'},
        {'code': '159877', 'name': '化工ETF', 'market': 'sz', 'category': '周期'},
        {'code': '516970', 'name': '石油ETF', 'market': 'sh', 'category': '周期'},
        {'code': '516830', 'name': '天然气ETF', 'market': 'sh', 'category': '周期'},
        {'code': '510190', 'name': '华宝油气', 'market': 'sh', 'category': '周期'},
        {'code': '159737', 'name': '油气ETF', 'market': 'sz', 'category': '周期'},
        {'code': '513350', 'name': '油气ETF', 'market': 'sh', 'category': '周期'},
        {'code': '511990', 'name': '原油ETF', 'market': 'sh', 'category': '周期'},
        {'code': '162719', 'name': '原油LOF', 'market': 'sz', 'category': '周期'},

        # ==================== 其他类 ====================
        {'code': '512660', 'name': '军工ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159638', 'name': '军工ETF', 'market': 'sz', 'category': '其他'},
        {'code': '512810', 'name': '军工龙头ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159696', 'name': '军工ETF', 'market': 'sz', 'category': '其他'},
        {'code': '512980', 'name': '传媒ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159805', 'name': '传媒ETF', 'market': 'sz', 'category': '其他'},
        {'code': '159867', 'name': '传媒ETF', 'market': 'sz', 'category': '其他'},
        {'code': '512890', 'name': '红利低波ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159725', 'name': '红利ETF', 'market': 'sz', 'category': '其他'},
        {'code': '515080', 'name': '红利ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159706', 'name': '红利ETF', 'market': 'sz', 'category': '其他'},
        {'code': '515210', 'name': '钢铁ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159786', 'name': '基建ETF', 'market': 'sz', 'category': '其他'},
        {'code': '516970', 'name': '基建ETF', 'market': 'sh', 'category': '其他'},
        {'code': '159863', 'name': '房地产ETF', 'market': 'sz', 'category': '其他'},
        {'code': '512200', 'name': '房地产ETF', 'market': 'sh', 'category': '其他'},

        # ==================== 海外ETF ====================
        {'code': '513100', 'name': '纳指ETF', 'market': 'sh', 'category': '海外'},
        {'code': '159941', 'name': '纳指ETF', 'market': 'sz', 'category': '海外'},
        {'code': '513500', 'name': '标普500', 'market': 'sh', 'category': '海外'},
        {'code': '159655', 'name': '标普500', 'market': 'sz', 'category': '海外'},
        {'code': '513300', 'name': '恒生ETF', 'market': 'sh', 'category': '海外'},
        {'code': '159920', 'name': '恒生ETF', 'market': 'sz', 'category': '海外'},
        {'code': '513260', 'name': '恒生科技ETF', 'market': 'sh', 'category': '海外'},
        {'code': '159740', 'name': '恒生科技ETF', 'market': 'sz', 'category': '海外'},
        {'code': '513650', 'name': '德国30', 'market': 'sh', 'category': '海外'},
        {'code': '513050', 'name': '中概互联', 'market': 'sh', 'category': '海外'},
        {'code': '159607', 'name': '中概互联', 'market': 'sz', 'category': '海外'},
        {'code': '513030', 'name': '德国ETF', 'market': 'sh', 'category': '海外'},
        {'code': '164824', 'name': '德国ETF', 'market': 'sz', 'category': '海外'},
        {'code': '513100', 'name': '纳指ETF', 'market': 'sh', 'category': '海外'},

        # ==================== 商品ETF ====================
        {'code': '518880', 'name': '黄金ETF', 'market': 'sh', 'category': '商品'},
        {'code': '159934', 'name': '黄金ETF', 'market': 'sz', 'category': '商品'},
        {'code': '159985', 'name': '豆粕ETF', 'market': 'sz', 'category': '商品'},
        {'code': '159930', 'name': '能源化工', 'market': 'sz', 'category': '商品'},
        {'code': '159981', 'name': '化工ETF', 'market': 'sz', 'category': '商品'},
        {'code': '511220', 'name': '城投债ETF', 'market': 'sh', 'category': '商品'},
        {'code': '511010', 'name': '国债ETF', 'market': 'sh', 'category': '商品'},
        {'code': '159970', 'name': '有色ETF', 'market': 'sz', 'category': '商品'},
    ]

    log(f"ETF列表总数: {len(all_etfs)}")
    return all_etfs


def get_etf_volume(etf_code: str, market: str) -> Optional[float]:
    """
    获取ETF前一日成交额（万元），顺便缓存K线数据供后续复用
    """
    try:
        # 获取最近9天的K线数据（成交额用最后一天，K线缓存给后续分析）
        symbol = f"{market}{etf_code}"
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen=10"

        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                # 缓存K线数据供后续分析复用
                _kline_cache[symbol] = data

                # 最后一天算成交额
                item = data[-1]
                volume = float(item.get('volume', 0))
                close = float(item.get('close', 0))
                money = volume * close / 10000
                return money
    except Exception as e:
        log(f"获取成交额失败 {etf_code}: {e}")
    return None


def load_volume_cache() -> Dict:
    """加载成交额缓存"""
    try:
        if os.path.exists(VOLUME_CACHE_FILE):
            with open(VOLUME_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            # 检查是否当天缓存
            cache_date = cache.get('_date', '')
            today = datetime.now().strftime('%Y-%m-%d')
            if cache_date == today:
                log(f"成交额缓存有效: {len(cache)} 只ETF")
                return cache
            else:
                log("成交额缓存过期，重新获取")
    except Exception:
        pass
    return {'_date': datetime.now().strftime('%Y-%m-%d')}


def save_volume_cache(cache: Dict):
    """保存成交额缓存"""
    try:
        with open(VOLUME_CACHE_FILE, 'w') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass


def get_historical_from_cache(etf_code: str, market: str) -> Optional[List]:
    """从动量策略的history_cache.json读取历史K线（避免重复请求）"""
    try:
        if os.path.exists(HISTORY_CACHE_FILE):
            with open(HISTORY_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            cache_key = f"{market}{etf_code}"  # e.g. "sz159915"
            data_key = f"{market}_{etf_code}"  # e.g. "sz_159915"
            for k in (cache_key, data_key):
                if k in cache and cache[k].get('data'):
                    return cache[k]['data']
    except Exception:
        pass
    return None


def filter_by_volume(etf_list: List[Dict], min_volume: float = 5000) -> List[Dict]:
    """
    筛选成交额超过min_volume的ETF（并行请求 + 缓存）
    """
    # 加载缓存
    volume_cache = load_volume_cache()
    has_cache = len(volume_cache) > 1  # 除了_date还有数据
    
    # 收集需要请求的ETF
    to_fetch = []
    for etf in etf_list:
        key = f"{etf['market']}_{etf['code']}"
        if key in volume_cache:
            etf['volume'] = volume_cache[key]
        else:
            to_fetch.append(etf)
    
    # 并行获取缺失的成交额
    if to_fetch:
        log(f"并行获取 {len(to_fetch)} 只ETF成交额...")
        def fetch_volume(etf):
            volume = get_etf_volume(etf['code'], etf['market'])
            return etf, volume
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_volume, etf): etf for etf in to_fetch}
            for future in as_completed(futures):
                etf, volume = future.result()
                key = f"{etf['market']}_{etf['code']}"
                if volume is not None:
                    volume_cache[key] = volume
                    etf['volume'] = volume
                    log(f"获取: {etf['name']} ({etf['code']}), 成交额: {volume:.0f}万")
                else:
                    log(f"失败: {etf['name']} ({etf['code']})")
        
        save_volume_cache(volume_cache)
    
    # 筛选
    filtered_etfs = [etf for etf in etf_list if etf.get('volume', 0) >= min_volume]
    log(f"\n筛选后ETF数量: {len(filtered_etfs)}")
    return filtered_etfs


def merge_duplicate_etfs(etf_list: List[Dict]) -> List[Dict]:
    """
    合并同类ETF，只保留成交额最大的一只

    规则：
    1. 提取ETF名称中的核心词（去掉"ETF"后缀）
    2. 相同核心词的视为同一类
    3. 保留成交额最大的一只
    """
    log("\n开始合并同类ETF...")

    # 提取核心名称的函数
    def extract_core_name(name: str) -> str:
        # 去掉"ETF"后缀
        core = name.replace('ETF', '')
        # 去掉"华宝"、"国泰"等基金公司前缀（简单处理）
        core = re.sub(r'(华宝|国泰|华夏|易方达|南方|嘉实|广发|华安|银华|富国|华泰柏瑞|信诚|建信|海富通|招商|中欧|景顺长城)', '', core)
        return core.strip()

    # 按核心名称分组
    core_map = {}
    for etf in etf_list:
        core_name = extract_core_name(etf['name'])
        if core_name not in core_map:
            core_map[core_name] = []
        core_map[core_name].append(etf)

    # 每组保留成交额最大的一只
    merged_etfs = []
    for core_name, etfs in core_map.items():
        if len(etfs) > 1:
            # 按成交额降序排序
            etfs.sort(key=lambda x: x.get('volume', 0), reverse=True)
            merged_etfs.append(etfs[0])
        else:
            merged_etfs.append(etfs[0])

    log(f"\n合并后ETF数量: {len(merged_etfs)}")
    return merged_etfs




def get_historical_data(etf_code: str, market: str, count: int = 10) -> pd.DataFrame:
    """获取历史K线数据（优先从各级缓存读取）"""
    try:
        symbol = f"{market}{etf_code}"

        # 1. 优先用内存K线缓存（filter_by_volume 时预取）
        if symbol in _kline_cache and len(_kline_cache[symbol]) >= count:
            data = _kline_cache[symbol]
            df = pd.DataFrame(data[-count:])
            df['date'] = pd.to_datetime(df['day'])
            df['close'] = df['close'].astype(float)
            log(f"内存缓存命中: {etf_code}")
            return df

        # 2. 再从动量策略缓存读取
        cached = get_historical_from_cache(etf_code, market)
        if cached and len(cached) >= count:
            df = pd.DataFrame(cached[-count:])
            df['date'] = pd.to_datetime(df['day'])
            df['close'] = df['close'].astype(float)
            log(f"磁盘缓存命中: {etf_code}")
            return df

        # 3. 缓存不够再从API获取
        if market == 'sz':
            url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz{etf_code}&scale=240&ma=no&datalen={count}"
        else:
            url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh{etf_code}&scale=240&ma=no&datalen={count}"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['day'])
                return df
    except Exception:
        pass
    return pd.DataFrame()


def get_realtime_price(etf_code: str, market: str) -> Optional[float]:
    """获取实时价格"""
    try:
        if market == 'sz':
            url = f"http://qt.gtimg.cn/q=sz{etf_code}"
        else:
            url = f"http://qt.gtimg.cn/q=sh{etf_code}"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            content = response.text.strip()
            if '=' in content and '"' in content:
                data_str = content.split('"')[1]
                fields = data_str.split('~')
                if len(fields) >= 4 and fields[3]:
                    return float(fields[3])
    except Exception:
        pass
    return None


def calculate_oversold_analysis(etf_list: List[Dict]) -> List[Dict]:
    """计算超跌分析（并行请求）"""
    results = []
    
    def analyze_one(etf):
        try:
            historical_df = get_historical_data(etf['code'], etf['market'], count=10)
            if historical_df.empty or len(historical_df) < 10:
                return None
            
            current_price = get_realtime_price(etf['code'], etf['market'])
            if current_price is None:
                return None
            
            # 检查最后一条K线是否包含今天
            closes = historical_df['close'].astype(float)
            today_str = datetime.now().strftime('%Y-%m-%d')
            last_day = str(historical_df['day'].iloc[-1]) if 'day' in historical_df.columns else ''
            
            if last_day.startswith(today_str):
                # 收盘后：K线已包含今天，直接取10日均线
                dynamic_ma10 = closes.sum() / 10
            else:
                # 盘中：K线不含今天，追加今日实时价
                dynamic_ma10 = (closes.sum() + current_price) / 10
            
            lower_band = dynamic_ma10 * (1 - ENE_LOWER_PCT)
            dist_to_lower = (current_price - lower_band) / lower_band * 100
            
            return {
                'code': etf['code'],
                'name': etf['name'],
                'market': etf['market'],
                'current_price': round(current_price, 3),
                'ma10': round(dynamic_ma10, 3),
                'lower_band': round(lower_band, 3),
                'dist_to_lower': round(dist_to_lower, 2),
                'avg_money': round(etf.get('volume', 0), 0),
                'category': etf.get('category', '其他')
            }
        except Exception:
            return None
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(analyze_one, etf) for etf in etf_list]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    results.sort(key=lambda x: x['dist_to_lower'])
    return results


if __name__ == '__main__':
    import sys
    is_quiet = '--quiet' in sys.argv
    
    if not is_quiet:
        if not is_quiet:
                    print("ETF超跌策略分析", file=sys.stderr)
        if not is_quiet:
                    print("=" * 60, file=sys.stderr)
    
    # 第一步：获取所有ETF列表
    if not is_quiet:
            print("\n第一步：获取所有场内ETF列表", file=sys.stderr)
    all_etfs = get_all_etf_list()
    if not is_quiet:
            print(f"获取到 {len(all_etfs)} 只ETF", file=sys.stderr)
    
    # 第二步：筛选高流动性ETF（并行获取成交额）
    if not is_quiet:
            print("\n第二步：筛选高流动性ETF（成交额 > 1亿）", file=sys.stderr)
    
    volume_cache = load_volume_cache()
    
    # 加载K线缓存（按日期判断有效性，同一天使用缓存避免重复请求）
    _kline_cache = load_kline_cache()
    
    filtered_etfs = []
    to_fetch = []
    for etf in all_etfs:
        key = f"{etf['market']}_{etf['code']}"
        if key in volume_cache:
            etf['volume'] = volume_cache[key]
            filtered_etfs.append(etf)
        else:
            to_fetch.append(etf)
    
    if to_fetch:
        if not is_quiet:
                print(f"并行获取 {len(to_fetch)} 只ETF成交额...", file=sys.stderr)
        def fetch_volume(etf):
            volume = get_etf_volume(etf['code'], etf['market'])
            return etf, volume
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_volume, etf): etf for etf in to_fetch}
            for future in as_completed(futures):
                etf, volume = future.result()
                key = f"{etf['market']}_{etf['code']}"
                if volume is not None and volume >= MIN_MONEY_W:
                    volume_cache[key] = volume
                    etf['volume'] = volume
                    filtered_etfs.append(etf)
        save_volume_cache(volume_cache)
    else:
        # 缓存命中，只需加上volume字段
        for etf in all_etfs:
            key = f"{etf['market']}_{etf['code']}"
            if key in volume_cache:
                etf['volume'] = volume_cache[key]
    
    # 保存K线缓存（按日期判断：同一天直接复用，跨天自动刷新）
    save_kline_cache(_kline_cache)
    
    if not is_quiet:
            print(f"筛选后剩余 {len(filtered_etfs)} 只ETF", file=sys.stderr)
    
    # 第三步：合并同类ETF
    if not is_quiet:
            print("\n第三步：合并同类ETF", file=sys.stderr)
    merged_etfs = merge_duplicate_etfs(filtered_etfs)
    if not is_quiet:
            print(f"合并后剩余 {len(merged_etfs)} 只ETF", file=sys.stderr)
    
    # 第四步：计算超跌分析
    if not is_quiet:
            print("\n第四步：计算超跌分析", file=sys.stderr)
    oversold_etfs = calculate_oversold_analysis(merged_etfs)
    
    # 输出结果（始终输出JSON）
    result = {
        'code': 200,
        'msg': 'success',
        'data': {
            'summary': {
                'total': len(merged_etfs),
                'analyzed': len(oversold_etfs)
            },
            'etfs': oversold_etfs[:10]
        }
    }
    print(json.dumps(result, ensure_ascii=False))
